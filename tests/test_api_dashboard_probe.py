"""Dashboard 路径 ApiLatencyProbe 遥测测试(B1 补齐,零 API)。

_solve_dashboard 自 2026-10-10 起与终端 _solve 一样接 probe;本测试直接
驱动 _ApiDashboardSession._run_agent(真实 FunctionModel Agent + 桩
control),验证:
- 逐请求 begin→tool_node 计时记录齐(请求数 == 脚本数;含纯文本收尾
  请求 —— 它同样流经 CallToolsNode);
- end_node 只在尾请求未被 tool_node 收口时兜底(finish_if_pending 无
  操作安全);
- 探测文件不落任何载荷文本。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.usage import RequestUsage

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rpent.planner.api_loop import _ApiDashboardSession, _ApiRunObserver  # noqa: E402
from rpent.utils.api_latency_probe import ApiLatencyProbe  # noqa: E402


class _Sink:
    def emit(self, *_a, **_k):
        pass


def _agent(script: list[str | None]) -> Agent:
    counter = [0]

    async def fn(messages, info: AgentInfo) -> ModelResponse:
        idx = counter[0]
        counter[0] += 1
        u = RequestUsage(input_tokens=500 * (idx + 1), output_tokens=7)
        item = script[idx]
        if item is None:
            return ModelResponse(parts=[TextPart(content="done")], usage=u)
        return ModelResponse(
            parts=[ToolCallPart(tool_name=item, args="{}")], usage=u)

    def echo(v: str = "x") -> str:
        return "ok"

    return Agent(FunctionModel(fn), instructions="t", tools=[echo])


class _StubControl:
    """_run_agent 触碰到的 control 面:end/tool_completed/complete。"""

    ended = False

    def end(self):
        self.ended = True

    async def tool_completed(self, session):
        pass

    async def complete(self, session):
        pass


def test_dashboard_session_records_probe(tmp_path, monkeypatch):
    art = REPO / "artifacts" / "p1_perf" / "_probe_dash_test.jsonl"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.unlink(missing_ok=True)
    monkeypatch.setenv("RPENT_API_LATENCY_LOG", str(art))
    probe = ApiLatencyProbe.from_env(repo=REPO)
    assert probe is not None

    script = ["echo", "echo", None]
    observer = _ApiDashboardSession.__mro__  # noqa: B018 - import sanity
    obs = _ApiRunObserver(dashboard_events=_Sink(), messages=[], max_turns=10)
    session = _ApiDashboardSession(
        agent=_agent(script),
        control=_StubControl(),
        observer=obs,
        max_turns=10,
        no_images=True,
        latency_probe=probe,
    )

    async def scenario():
        assert await session._run_agent("go")

    asyncio.run(scenario())

    recs = [json.loads(x) for x in
            art.read_text(encoding="utf-8").splitlines() if x.strip()]
    tool_recs = [r for r in recs if r["outcome"] == "tool_node"]
    # 文本收尾响应同样流经 CallToolsNode(无工具可执行),所以每个模型
    # 请求恰在 tool_node 收口一条 —— 与终端路径口径一致
    assert len(tool_recs) == len(script), recs
    for i, r in enumerate(tool_recs):
        assert r["model_node_elapsed_s"] >= 0.0
        assert r["request_input_tokens"] == 500 * (i + 1)
    raw = art.read_text(encoding="utf-8")
    assert "echo" not in raw and "go" not in raw
    art.unlink(missing_ok=True)
