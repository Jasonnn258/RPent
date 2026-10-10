#!/usr/bin/env python3
"""P1 可复现离线性能 Benchmark(Phase C;零 API/零 GPU/零 episode)。

三个独立可重复的测量面,全部走生产代码路径:

1. planner_mock_api:ApiAgentLoop + FunctionModel 合成延迟(常数/长尾
   两种)× 工具模式(单工具/双工具/思考+工具),用 ApiLatencyProbe 的
   逐请求记录出 p50/p90/p95;附客户端份额(wall − 合成延迟)与
   token 不重复累计守卫(反例:重复累计会让 per-request tokens 单调
   等于累计值)。
2. kill_grace:3 个忽略 SIGTERM 的组内 daemon,扫 P1_KILL_GRACE_S
   等效宽限 {2s, 6s},量化"宽限 30→5 每被终止集省 ~25s"的口径。
3. gpu_sampler_audit:合成 nvidia-smi 输出驱动 _gpu_sampler 的 pgid
   过滤/异常容错(垃圾行跳过、查询超时回退保守基线 n=1、他人 pgid
   不计入)—— 不依赖本机 GPU 状态,可复现。

输出 artifacts/p1_perf/benchmark.json;REPEATS 次重复取中位数与极差。
"""
from __future__ import annotations

import asyncio
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT = REPO / "artifacts" / "p1_perf"
REPEATS = 3
N_REQUESTS = 12


def _pct(sorted_xs: list, p: float) -> float:
    return sorted_xs[min(len(sorted_xs) - 1, int(p * len(sorted_xs)))]


def _stats(xs: list) -> dict:
    s = sorted(xs)
    return {"n": len(s), "p50": round(_pct(s, 0.50), 3),
            "p90": round(_pct(s, 0.90), 3), "p95": round(_pct(s, 0.95), 3),
            "max": round(s[-1], 3), "min": round(s[0], 3)}


# ---------------------------------------------------------------------------
# 1. Planner mock API
# ---------------------------------------------------------------------------

class _Sink:
    def emit(self, *_a, **_k):
        pass


def _toolkit_stub():
    def get_tools_spec():
        return [
            {"name": "echo", "description": "echo",
             "input_schema": {"type": "object",
                              "properties": {"v": {"type": "string"}}}},
            {"name": "finish", "description": "finish",
             "input_schema": {"type": "object"}},
        ]

    calls: list[str] = []

    def execute_tool(name, kwargs):
        calls.append(name)
        is_finish = name == "finish"
        result = {"ok": True, "tool": name}
        return SimpleNamespace(
            result=result,
            content_blocks=[{"type": "text",
                             "text": json.dumps(result)}],
            is_finish=is_finish,
        )

    return SimpleNamespace(get_tools_spec=get_tools_spec,
                           execute_tool=execute_tool), calls


def _mock_model(delays: list[float], mode: str):
    """delays: 每请求合成'服务端'延迟;末请求调 finish 收口,总请求数=len(delays)。"""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.usage import RequestUsage

    state = {"i": 0}

    async def fn(messages, info) -> ModelResponse:
        i = state["i"]
        state["i"] += 1
        await asyncio.sleep(delays[i])
        u = RequestUsage(input_tokens=1000 + i, output_tokens=50 + i)
        last = i == len(delays) - 1
        parts = []
        if mode == "think_then_tool" and not last:
            parts.append(TextPart(content="plan " * 100))
        parts.append(ToolCallPart(
            tool_name="finish" if last else "echo", args="{}"))
        return ModelResponse(parts=parts, usage=u)

    return FunctionModel(fn)


def _run_planner_case(delay_pattern: str, mode: str) -> dict:
    """一次完整 ApiAgentLoop.solve;返回逐请求 probe 记录。"""
    import os

    from rpent.planner.api_loop import ApiAgentLoop

    art = OUT / "_bench_probe.jsonl"
    art.unlink(missing_ok=True)
    key = "RPENT_API_LATENCY_LOG"
    old = os.environ.get(key)
    os.environ[key] = str(art)
    try:
        delays = ([0.05] * N_REQUESTS if delay_pattern == "const50ms"
                  else [0.03] * (N_REQUESTS - 2) + [0.3, 0.5])
        model = _mock_model(delays, mode)
        tk, _ = _toolkit_stub()
        loop = ApiAgentLoop(model, max_tokens=512,
                            dashboard_events=_Sink(), timeout_s=120)
        result = loop.solve(system_prompt="bench", user_message="go",
                            toolkit=tk, max_turns=N_REQUESTS + 2)
        assert result.error is None, result.error
        recs = [json.loads(x) for x in
                art.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(recs) == len(delays), (len(recs), len(delays))
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old
        art.unlink(missing_ok=True)
    return {"recs": recs, "delays": delays}


def planner_mock_api() -> dict:
    out = {}
    for pattern in ("const50ms", "tail"):
        for mode in ("plain", "think_then_tool"):
            walls, client_shares, toks = [], [], []
            for _ in range(REPEATS):
                r = _run_planner_case(pattern, mode)
                recs = r["recs"]
                walls += [x["model_node_elapsed_s"] for x in recs]
                client_shares += [
                    max(x["model_node_elapsed_s"] - d, 0)
                    for x, d in zip(recs, r["delays"])]
                # 反例守卫:per-request tokens 必须是 per-response 值
                # (1000+i 单调 +1),累计复读会让它线性爆炸
                toks += [x["request_input_tokens"] for x in recs]
            assert all(t < 1000 + N_REQUESTS + 2 for t in toks), \
                "per-request tokens 疑似累计复读"
            out[f"{pattern}/{mode}"] = {
                "request_wall_s": _stats(walls),
                "client_share_s": _stats(client_shares),
            }
    return out


# ---------------------------------------------------------------------------
# 2. kill grace 扫描
# ---------------------------------------------------------------------------

_DAEMON = (
    "import signal, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "time.sleep(300)\n"
)


def kill_grace() -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "p1_dev1a_run", REPO / "scripts" / "p1_dev1a_run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    out = {}
    for grace in (2.0, 6.0):
        walls = []
        for _ in range(REPEATS):
            code = (
                "import subprocess, sys, time\n"
                f"for _ in range(3):\n"
                f"    subprocess.Popen([sys.executable, '-c', {_DAEMON!r}])\n"
                "time.sleep(0.6)\n"
            )
            proc = subprocess.Popen([sys.executable, "-c", code],
                                    start_new_session=True)
            proc.wait(timeout=10)     # leader 退出,3 个 daemon 留在组内
            t0 = time.monotonic()
            how = runner._kill_pg(proc.pid, grace_s=grace)
            walls.append(time.monotonic() - t0)
            assert how == "SIGTERM_then_SIGKILL", how
        out[f"grace_{grace}s"] = {
            "kill_wall_s": _stats(walls),
            "note": "3 个 SIGTERM 忽略 daemon;wall≈grace+SIGKILL 到位时间",
        }
    return out


# ---------------------------------------------------------------------------
# 3. GPU 采样器审计(合成 nvidia-smi 输出)
# ---------------------------------------------------------------------------

def gpu_sampler_audit() -> dict:
    import importlib.util
    import threading

    spec = importlib.util.spec_from_file_location(
        "p1_dev1a_run", REPO / "scripts" / "p1_dev1a_run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    import os

    # runner 传的 pgid==子进程 pid(start_new_session);本进程没有
    # new session,所以取自己真实的 pgrp,/proc/<pid>/stat 第 5 字段
    my_pid = os.getpid()
    with open(f"/proc/{my_pid}/stat", "rb") as f:
        my_pgid = int(f.read().decode().split()[4])
    other_line = "GPU-OTHER,999999\n"
    out = {}

    def _sample(fake_stdout: str | None, *, fail: bool = False) -> dict:
        calls = {"n": 0}

        def fake_run(cmd, **kw):
            calls["n"] += 1
            if fail:
                raise subprocess.TimeoutExpired(cmd, 1)
            return SimpleNamespace(stdout=fake_stdout)

        orig_run = subprocess.run
        subprocess.run = fake_run          # type: ignore[assignment]
        try:
            stop = threading.Event()
            acc = {}

            def target():
                acc.update(runner._gpu_sampler(my_pgid, stop))

            th = threading.Thread(target=target, daemon=True)
            th.start()
            time.sleep(runner.GPU_SAMPLE_S * 1.5)
            stop.set()
            th.join(timeout=runner.GPU_SAMPLE_S * 2)
            return acc
        finally:
            subprocess.run = orig_run

    # 正例:本 pgid 占 2 张卡(同 pid 双 uuid)+ 他人 1 条不计入
    fake = f"GPU-A,{my_pid}\nGPU-B,{my_pid}\n{other_line}"
    acc = _sample(fake)
    out["two_gpus_matched"] = {
        "max_gpu_count": acc["max_gpu_count"],
        "expect": 2,
        "pass": acc["max_gpu_count"] == 2,
    }
    # 反例:垃圾行/空输出 → 回退保守基线 1
    acc = _sample("garbage line\n,,\nGPU-X,notapid\n")
    out["garbage_falls_back_to_one"] = {
        "max_gpu_count": acc["max_gpu_count"],
        "expect": 1,
        "pass": acc["max_gpu_count"] == 1,
    }
    # 反例:nvidia-smi 超时 → 保守基线 1,不抛
    acc = _sample(None, fail=True)
    out["timeout_falls_back_to_one"] = {
        "max_gpu_count": acc["max_gpu_count"],
        "expect": 1,
        "pass": acc["max_gpu_count"] == 1,
    }
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    result = {
        "protocol": "RPENT_P1_OFFLINE_BENCHMARK_V1",
        "repeats": REPEATS,
        "planner_mock_api": planner_mock_api(),
        "kill_grace": kill_grace(),
        "gpu_sampler_audit": gpu_sampler_audit(),
        "wall_s": round(time.time() - t0, 1),
        "caveats": [
            "共享开发机单进程运行,绝对值含机器噪声;对比请用同一批运行",
            "合成延迟≠真实 GLM 端点延迟,只标定客户端路径与计时口径",
            "kill_grace 的 daemon 数固定 3;真实组的 vla/env/sam3 行为可能不同",
        ],
    }
    out = OUT / "benchmark.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1)[:2400])
    print(f"[bench] -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
