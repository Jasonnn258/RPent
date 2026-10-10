#!/usr/bin/env python3
"""P1 Planner 请求级归因:只用 DEV1A 既有 run.log,零新 episode/零 API。

每个 model 请求(= 图里的 ModelRequestNode)在日志上的边界:
- 开始:上一轮最后一个 [tool<](或首轮 [prompt]/agent 启动)之后
- 结束:"=== turn N ===" 行(CallToolsNode yield 时打,工具尚未执行)

因此 model_node_wall(N) = ts(=== turn N) − ts(上一事件行),秒级分辨率。
这恰好等于远端 probe(ApiLatencyProbe)将来逐请求记录的口径 —— 本脚本
用历史日志先给出 8 集 × 全部轮次的分布,回答"76.1% 残差里多少是
model 请求墙钟(客户端观测,含网络/排队/生成)"。

同时从 [usage] 行(单 run 内累计)取逐轮 delta:
- 每轮 requests delta >1 → 检出隐藏重试
- in/out token 逐轮分布、cache_read/cache_write 是否非零(GLM 端点
  是否真的回报缓存命中;非零才有"真实缓存",否则只是参数开了)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "artifacts" / "p1_dev1a"
OUT = REPO / "artifacts" / "p1_perf"

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ")
_TURN = re.compile(r"=== turn (\d+)/(\d+) ===")
_USAGE = re.compile(r"\[usage\] in=(\S+) out=(\S+) cache_read=(\S+) "
                    r"cache_write=(\S+) requests=(\S+)")
_TOOL_O = re.compile(r"\[tool>\] (\w+)\(")
_TOOL_C = re.compile(r"\[tool<] (\w+):")
_ERR = re.compile(r"agent run failed|timed out|usage limit|RetryError|"
                  r"ModelHTTPError|APIConnectionError")

NA = "None"


def _i(v: str) -> int | None:
    return None if v == NA else int(v)


def parse(runlog: Path) -> dict:
    ts = None
    turns: list[dict] = []
    cur: dict | None = None
    last_anchor = None          # 上一事件行时间(model 请求的起点)
    prev_usage = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0,
                  "requests": 0}
    usage_lines = 0
    errors: list[str] = []
    open_tools: dict[str, list] = defaultdict(list)
    tool_wall = 0.0
    for line in runlog.read_text(encoding="utf-8", errors="replace") \
            .splitlines():
        m = _TS.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        mu = _USAGE.search(line)
        if mu:
            usage_lines += 1
            u = {"in": int(mu.group(1)), "out": int(mu.group(2)),
                 "cache_read": _i(mu.group(3)), "cache_write": _i(mu.group(4)),
                 "requests": int(mu.group(5))}
            if cur is not None and "usage" not in cur:
                # 累计值 → 本轮 delta(单 run 内累计口径)
                cur["usage"] = {
                    k: u[k] - prev_usage[k] for k in
                    ("in", "out", "cache_read", "cache_write", "requests")}
                prev_usage = u
            continue
        mt = _TURN.search(line)
        if mt:
            if cur is not None:
                turns.append(cur)
            cur = {"turn": int(mt.group(1)),
                   "t_turn": ts,
                   "model_node_wall_s": (ts - last_anchor).total_seconds()
                   if last_anchor else None}
            continue
        mo = _TOOL_O.search(line)
        if mo:
            open_tools[mo.group(1)].append(ts)
            continue
        mc = _TOOL_C.search(line)
        if mc and open_tools[mc.group(1)]:
            t0 = open_tools[mc.group(1)].pop(0)
            tool_wall += (ts - t0).total_seconds()
            last_anchor = ts           # 工具结束 = 下一请求可能起点
            continue
        if _ERR.search(line):
            errors.append(line[:160])
        # [prompt]/[model]/[think]/[phase]/[usage] 之外的首个事件行也移动锚点
        if ("[prompt]" in line or "[phase]" in line) and cur is None:
            last_anchor = ts
    if cur is not None:
        turns.append(cur)
    return {"turns": turns, "tool_wall_s": tool_wall,
            "usage_lines": usage_lines, "errors": errors}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in (ROOT / "run_log.jsonl").read_text(
            encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("ev") == "episode_measure":
            rows.append(e)

    per_ep = []
    all_walls = []
    all_din, all_dout = [], []
    extra_requests = 0
    cache_nonzero = 0
    frozen_eps = 0
    for m in rows:
        key = m["key"]
        ep_dirs = sorted(d for d in (ROOT / "runs").glob(f"{key}_*")
                         if d.is_dir())
        if not ep_dirs:
            continue
        r = parse(ep_dirs[-1] / "run.log")
        walls = [t["model_node_wall_s"] for t in r["turns"]
                 if t["model_node_wall_s"] is not None]
        # 首轮的 wall 不可靠(锚点=[prompt],但之后还有环境 spawn 等噪声)
        # → 首轮单独标记,不进分布
        walls_rest = walls[1:]
        usage = [t["usage"] for t in r["turns"] if "usage" in t]
        # 冻结检测:历史 api_loop 观察者 bug(rpent#api_loop observe_response
        # 存活对象引用)让 [usage] 从第 2 个请求起逐字重复 —— 冻结集的
        # 逐轮 token delta 不可用,只有前两行可信
        frozen = _frozen_from(usage)
        # 冻结前 log 行是真累计(request1/2),逐轮 delta 都可用;
        # 冻结后的行逐字重复,delta 恒 0 → 全部丢弃
        usable = usage if frozen is None else usage[:frozen]
        din = [u["in"] for u in usable]
        dout = [u["out"] for u in usable]
        req_delta_gt1 = sum(1 for u in usage if u["requests"] > 1)
        cz = sum(1 for u in usage
                 if (u["cache_read"] or 0) > 0 or (u["cache_write"] or 0) > 0)
        extra_requests += sum(u["requests"] - 1 for u in usage
                              if u["requests"] > 1)
        cache_nonzero += cz
        frozen_eps += 1 if frozen is not None else 0
        all_walls += walls_rest
        all_din += din
        all_dout += dout
        per_ep.append({
            "key": key,
            "n_turns": len(r["turns"]),
            "model_node_wall_total_s": round(sum(walls), 1),
            "model_node_wall_first_turn_s": walls[0] if walls else None,
            "model_node_wall_rest": _stats(walls_rest),
            "tool_wall_s": round(r["tool_wall_s"], 1),
            "usage_turns": len(usage),
            "usage_frozen_from_turn": frozen,
            "tokens_in_usable_deltas": _stats(din),
            "tokens_out_usable_deltas": _stats(dout),
            "requests_delta_gt1_turns": req_delta_gt1,
            "cache_nonzero_turns": cz,
            "errors": r["errors"],
        })

    result = {
        "n_episodes": len(per_ep),
        "aggregate": {
            "model_node_wall_all_s": round(sum(all_walls), 1),
            "model_node_wall_per_request": _stats(all_walls),
            "tokens_in_per_request": _stats(all_din),
            "tokens_out_per_request": _stats(all_dout),
            "hidden_retry_requests_total": extra_requests,
            "cache_nonzero_turns_total": cache_nonzero,
        },
        "per_episode": per_ep,
        "caveats": [
            "时间戳秒级分辨率;单轮 wall 含网络+服务端排队+生成+客户端图开销",
            "首轮 wall 锚点=[prompt](含环境 spawn 后噪声),不进分布只留档",
            "[usage] 为单 run 累计值,delta=本轮;requests delta>1 即隐藏重试",
            "口径与 ApiLatencyProbe(model-node wall)一致,可互相校验",
            "历史 [usage] 从第 2 个请求起冻结(api_loop observe_response 存活引用"
            " bug,2026-10-10 已修):逐请求 token 只有每集前 2 个请求可用,"
            "其余 UNMEASURABLE_FROM_EXISTING_LOGS;wall 分布不受影响",
        ],
    }
    out = OUT / "planner_requests.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"aggregate": result["aggregate"],
                      "ep0": per_ep[0] if per_ep else {}},
                     ensure_ascii=False, indent=1)[:1500])
    print(f"[planner-req] -> {out}")
    return 0


def _stats(xs: list) -> dict:
    if not xs:
        return {"n": 0}
    s = sorted(xs)

    def pct(p):
        return s[min(len(s) - 1, int(p * len(s)))]
    return {"n": len(s), "sum": round(sum(s), 1),
            "p50": round(pct(0.50), 2), "p90": round(pct(0.90), 2),
            "p95": round(pct(0.95), 2), "max": round(s[-1], 2)}


def _frozen_from(deltas: list[dict]) -> int | None:
    """检测历史 [usage] 冻结:返回首个"delta 全零且此后全零"的轮索引。

    修复前的观察者把活引用存成基线,第 2 个观测点起 delta 恒 0。逐轮
    delta 全零在真实跑里不可能(in>0 是每请求必然),所以首个全零轮
    即冻结起点;None = 未冻结(修复后日志)。
    """
    zero_from = None
    for i, d in enumerate(deltas):
        if all((d[k] or 0) == 0 for k in
               ("in", "out", "cache_read", "cache_write")) and d["requests"] == 0:
            zero_from = i
            break
    return zero_from


if __name__ == "__main__":
    raise SystemExit(main())
