#!/usr/bin/env python3
"""P1 性能拆解:只用已有 DEV1A pilot 日志,零新 episode/零 GPU。

数据源(全部只读):
- artifacts/p1_dev1a/runs/<key>_b57ce6c9/run.log   每行带秒级时间戳
- artifacts/p1_dev1a/runs/<key>/p1_dev1a_events.jsonl  hook 事件(unix t)
- artifacts/p1_dev1a/run_log.jsonl                 runner 侧每集墙钟

拆分口径(受日志分辨率限制,如实标注):
- init_env_model: agent cmd → 首个 [prompt](env/vla/sam3 构建与加载)
- main_loop: 首个 [prompt] → run.log 最后一条
  - planner_api ≈ main_loop − Σtool(tool> → 对应 tool< 的间隔)
  - tool 时长按工具名分桶(pi0_pick 含 推理+chunk步进+渲染+落盘,
    由离线微基准另行拆分,见 p1_perf_microbench.py)
- probe: hook 事件(probe/probe_done)墙钟 + 快照 rpc_wall_ms 合计
- teardown: runner 墙钟 − (末条日志 − t_cmd);被 kill 集含 SIGTERM 宽限
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
_TOOL_O = re.compile(r"\[tool>\] (\w+)\(")
_TOOL_C = re.compile(r"\[tool<] (\w+):")
_USAGE = re.compile(r"\[usage\] in=(\d+) out=(\d+) cache_read=(\d+) "
                    r"cache_write=(\d+) requests=(\d+)")


def _t(line: str):
    m = _TS.match(line)
    if not m:
        return None, None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), m.group(1)


def parse_runlog(runlog: Path) -> dict:
    t_cmd = t_prompt = None
    daemons = []
    opens = defaultdict(list)      # name -> [start_dt, ...](并行工具调用)
    tools = []                     # (name, seconds)
    usage = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0,
             "requests": 0, "lines": 0}
    turns = 0
    last = None
    for line in runlog.read_text(encoding="utf-8", errors="replace") \
            .splitlines():
        ts, _ = _t(line)
        if ts is None:
            continue
        last = ts
        if "physical agent cmd" in line:
            t_cmd = ts
        elif "spawned (pid" in line:
            daemons.append(ts)
        elif "[prompt]" in line and t_prompt is None:
            t_prompt = ts
        elif "=== turn " in line:
            turns += 1
        else:
            mo = _TOOL_O.search(line)
            if mo:
                opens[mo.group(1)].append(ts)
                continue
            mc = _TOOL_C.search(line)
            if mc:
                name = mc.group(1)
                # 配对:同名的最早未闭合 tool>(并行调用按 FIFO)
                if opens[name]:
                    t0 = opens[name].pop(0)
                    tools.append((name, (ts - t0).total_seconds()))
            mu = _USAGE.search(line)
            if mu:
                usage["lines"] += 1
                for k, v in zip(("in", "out", "cache_read", "cache_write",
                                 "requests"), mu.groups()):
                    usage[k] += int(v)
    return {"t_cmd": t_cmd, "t_prompt": t_prompt, "daemons": daemons,
            "last": last, "turns": turns, "tools": tools, "usage": usage}


def parse_events(key: str) -> dict:
    f = ROOT / "runs" / key / "p1_dev1a_events.jsonl"
    if not f.is_file():
        return {}
    evs = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        evs[e.get("ev")] = e
    return evs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    measures = {}
    for line in (ROOT / "run_log.jsonl").read_text(
            encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("ev") == "episode_measure":
            measures[e["key"]] = e

    rows = []
    for key in sorted(measures):
        m = measures[key]
        ep_dirs = sorted(d for d in (ROOT / "runs").glob(f"{key}_*")
                         if d.is_dir())
        runlog = ep_dirs[-1] / "run.log" if ep_dirs else None
        if runlog is None or not runlog.is_file():
            continue
        r = parse_runlog(runlog)
        evs = parse_events(key)
        t_cmd, t_prompt, last = r["t_cmd"], r["t_prompt"], r["last"]
        runner_wall = float(m["wall_s"])
        init_s = (t_prompt - t_cmd).total_seconds() if t_prompt else None
        loop_s = (last - t_prompt).total_seconds() if t_prompt else None
        tool_by = defaultdict(float)
        for name, dur in r["tools"]:
            tool_by[name] += dur
        tool_total = sum(tool_by.values())
        # 被杀集:last 之后到 runner 停表 = kill+宽限;自然集=收尾落盘+退出
        teardown_s = runner_wall - ((last - t_cmd).total_seconds())
        probe_wall = None
        snap_ms = 0.0
        if "probe" in evs:
            probe_wall = round(evs["probe_done"]["t"] - evs["trigger"]["t"], 1)
            for s in evs["probe"].get("audit_snapshots", {}).values():
                seq = []
                if isinstance(s, dict) and "snap" not in s:
                    seq = [s]
                elif isinstance(s, dict):
                    seq = [s.get("snap", {})]
                for snap in seq:
                    if isinstance(snap, dict):
                        snap_ms += float(snap.get("rpc_wall_ms") or 0)
            for ls in evs["probe"].get("audit_snapshots", {}) \
                    .get("lift_samples", []):
                snap_ms += float(ls.get("snap", {}).get("rpc_wall_ms") or 0)
        rows.append({
            "key": key,
            "runner_wall_s": round(runner_wall, 1),
            "init_env_model_s": init_s,
            "main_loop_s": round(loop_s, 1) if loop_s else None,
            "planner_api_est_s": round(loop_s - tool_total, 1)
            if loop_s else None,
            "tool_total_s": round(tool_total, 1),
            "tool_by_name_s": {k: round(v, 1)
                               for k, v in sorted(tool_by.items(),
                                                  key=lambda x: -x[1])},
            "turns": r["turns"],
            "planner_usage": r["usage"],
            "probe_wall_s": probe_wall,
            "snapshot_rpc_ms_total": round(snap_ms, 1),
            "teardown_s": round(teardown_s, 1),
            "terminated_by": m.get("terminated_by"),
        })

    agg = defaultdict(float)
    for row in rows:
        for k in ("runner_wall_s", "init_env_model_s", "main_loop_s",
                  "planner_api_est_s", "tool_total_s", "teardown_s"):
            if row.get(k) is not None:
                agg[k] += row[k]
        for name, v in row["tool_by_name_s"].items():
            agg[f"tool:{name}"] += v
    total = agg["runner_wall_s"]
    summary = {k: {"total_s": round(v, 1),
                   "pct": round(100 * v / total, 1)}
               for k, v in sorted(agg.items(), key=lambda x: -x[1])}
    result = {"n_episodes": len(rows), "aggregate": summary,
              "per_episode": rows,
              "caveats": [
                  "时间戳秒级分辨率;planner_api=主循环−工具时长(含少量日志间隙)",
                  "pi0_pick 时长 = 推理+chunk步进+渲染+落盘 之和,内部拆分见微基准",
                  "teardown(被杀集)含 ~30s SIGTERM 宽限(runner 计入墙钟)",
              ]}
    out = OUT / "perf_breakdown.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"n": len(rows), "aggregate": summary},
                     ensure_ascii=False, indent=1))
    print(f"[perf] -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
