"""API loop usage 计账与 model-node 计时边界的离线端到端测试(零 API)。

背景(2026-10-10 性能轮发现):DEV1A 生产 run.log 的 [usage] 行从第 2 个
请求起完全冻结(in/out/requests 不再增长),而轮次与工具调用一直在推进。
本文件用 FunctionModel(无网络)复现/定位:

1. 单一 agent.iter 多轮工具循环里,run.usage 是否每请求递增;
2. _ApiRunObserver 的累计口径与逐轮 delta 是否正确;
3. ApiLatencyProbe 的 begin/finish 边界是否恰好覆盖 model 请求执行
  (begin=ModelRequestNode yield,finish=CallToolsNode yield,工具不在内);
4. per-response RequestUsage(远端 probe 记的)与 run.usage(累计)的区别。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from pydantic_ai.models.function import AgentInfo

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rpent.planner.api_loop import ApiAgentLoop, _ApiRunObserver  # noqa: E402

MODEL_DELAY_S = 0.05


def _toolkit_stub(n_scripted: int):
    """最小 toolkit:echo 工具 + finish;记录调用序列。"""
    calls: list[tuple[str, dict]] = []

    def get_tools_spec():
        return [
            {"name": "echo", "description": "echo",
             "input_schema": {"type": "object",
                              "properties": {"v": {"type": "string"}}}},
            {"name": "finish", "description": "finish",
             "input_schema": {"type": "object",
                              "properties": {"status": {"type": "string"}}}},
        ]

    def execute_tool(name, kwargs):
        calls.append((name, dict(kwargs)))
        is_finish = name == "finish"
        result = {"ok": True, "tool": name}
        if is_finish:
            result["status"] = kwargs.get("status", "success")
        return SimpleNamespace(
            result=result,
            content_blocks=[{"type": "text",
                             "text": json.dumps(result)}],
            is_finish=is_finish,
        )

    tk = SimpleNamespace(get_tools_spec=get_tools_spec,
                         execute_tool=execute_tool)
    return tk, calls


def _scripted_model(script: list[str], usage_log: list[RequestUsage]):
    """FunctionModel:依次返回 script 中的工具调用;None=纯文本收尾;
    每次请求睡固定延迟。"""

    async def fn(messages, info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(MODEL_DELAY_S)
        idx = len(usage_log)
        u = RequestUsage(input_tokens=1000 * (idx + 1),
                         output_tokens=10 * (idx + 1))
        usage_log.append(u)
        if script[idx] is None:
            from pydantic_ai.messages import TextPart

            return ModelResponse(parts=[TextPart(content="done")], usage=u)
        return ModelResponse(
            parts=[ToolCallPart(tool_name=script[idx], args="{}")],
            usage=u,
        )

    return FunctionModel(fn)


class _Sink:
    def emit(self, *_a, **_k):
        pass


def _solve(model, toolkit, max_turns=10):
    loop = ApiAgentLoop(model, max_tokens=512,
                        dashboard_events=_Sink(), timeout_s=30)
    return loop.solve(
        system_prompt="test", user_message="go", toolkit=toolkit,
        max_turns=max_turns)


def test_run_usage_increments_every_request():
    """单 run 多轮:run.usage.requests 应每请求 +1(生产日志冻结=bug 证据)。

    直接驱动 Agent.iter(不走 ApiAgentLoop,隔离库行为):
    """
    script = ["echo"] * 4 + [None]
    usage_log: list[RequestUsage] = []
    model = _scripted_model(script, usage_log)

    async def drive():
        def echo(v: str = "x") -> str:
            return "ok"

        def finish(status: str = "success") -> str:
            return "done"

        agent = Agent(model, instructions="t",
                      tools=[echo, finish])
        seen = []
        async with agent.iter("go") as run:
            async for node in run:
                if Agent.is_call_tools_node(node):
                    seen.append((node.model_response.usage.requests,
                                 run.usage.requests,
                                 int(run.usage.input_tokens or 0)))
                    async with node.stream(run.ctx):
                        pass
        return seen

    seen = asyncio.run(drive())
    assert [s[1] for s in seen] == [1, 2, 3, 4, 5], seen


def test_api_loop_stats_and_probe_records(tmp_path, monkeypatch):
    """ApiAgentLoop 全链路:finish 正常、stats/累计口径、probe 逐请求记录。

    probe 记录数 == API 请求数;每条 latency ≥ MODEL_DELAY_S(计时边界
    覆盖请求执行);outcome 全为 tool_node;usage 为 per-response 值
    (1000/2000/...,不是累计,不是重复累计)。
    """
    script = ["echo"] * 3 + ["finish"]
    usage_log: list[RequestUsage] = []
    tk, calls = _toolkit_stub(len(script))
    model = _scripted_model(script, usage_log)

    probe_path = tmp_path / "probe.jsonl"
    monkeypatch.setenv("RPENT_API_LATENCY_LOG", str(probe_path))
    # probe 目标必须落在仓库 artifacts/ 下:借 tmp 会拒 → 直接指仓库内
    art = REPO / "artifacts" / "p1_perf" / "_probe_test.jsonl"
    art.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("RPENT_API_LATENCY_LOG", str(art))
    try:
        result = _solve(model, tk)
        assert result.error is None, result.error
        assert result.finish_result and result.finish_result.get("_finish")
        assert [c[0] for c in calls] == script

        # probe:每请求一条
        recs = [json.loads(x) for x in
                art.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(recs) == len(script), recs
        for i, r in enumerate(recs):
            assert r["outcome"] == "tool_node"
            assert r["model_node_elapsed_s"] >= MODEL_DELAY_S * 0.8
            # per-response RequestUsage,非累计、非重复
            assert r["request_input_tokens"] == 1000 * (i + 1)
            assert r["request_output_tokens"] == 10 * (i + 1)
        # 原始载荷绝不落盘
        raw = art.read_text(encoding="utf-8")
        assert "echo" not in raw and "go" not in raw
    finally:
        art.unlink(missing_ok=True)
        monkeypatch.delenv("RPENT_API_LATENCY_LOG", raising=False)


def test_api_loop_usage_accum_matches_requests():
    """ApiAgentLoop stats:total requests 必须 == 脚本请求数(生产冻结回归锚)。"""
    script = ["echo"] * 3 + ["finish"]
    usage_log: list[RequestUsage] = []
    tk, calls = _toolkit_stub(len(script))
    model = _scripted_model(script, usage_log)
    result = _solve(model, tk)
    stats = result.stats
    assert stats["requests"] == len(script), stats
    assert stats["total_input_tokens"] == 1000 + 2000 + 3000 + 4000, stats
