#!/usr/bin/env python3
"""P1 客户端开销分解:模型延迟为零时,一个 planner 轮次还剩多少墙钟?

问题(Phase A.6):历史 model_node_wall p50=8s 里,除网络+服务端生成外,
客户端侧(pydantic-ai 图推进/请求序列化/ProcessHistory 图片剪枝/
事件流)占多少?无法在真实 GLM 端点上分离(服务端不回细分指标),
但可以用 FunctionModel(sleep=0)测出客户端开销的**上界**:
真实请求的客户端开销 ≤ 本脚本测得的零延迟墙钟(同为请求构造+图推进
路径,只是不经过网络)。

三个维度,均离线、零 API、不碰 episode:
- TURNS:固定 4MB 历史图片预算,轮次 4/16/48(历史长度增长的影响)
- IMAGES:固定轮次,逐轮新到图片字节数 0 / 256KB(≈一张 512 PNG)
  / 1MB(≈一张 1024 PNG)
- THINKING:轮次固定,响应含 0 / 4KB thinking 文本(序列化/日志路径)

对照:真实 p50=8s、p90=33s(artifacts/p1_perf/planner_requests.json)。
输出 artifacts/p1_perf/client_overhead.json。
"""
from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from types import SimpleNamespace

import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pydantic_ai import Agent, BinaryContent  # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel, AgentInfo  # noqa: E402
from pydantic_ai.usage import RequestUsage  # noqa: E402

OUT = REPO / "artifacts" / "p1_perf"
REPEATS = 3


async def _drive(n_turns: int, img_bytes: int, thinking_chars: int) -> float:
    """跑一个 agent.iter;返回模型请求节点累计墙钟(纯客户端路径)。

    计时口径与 ApiLatencyProbe 相同:yield(ModelRequestNode) →
    yield(下一节点) = 请求构造+ProcessHistory+模型调用(此处零延迟)
    +图推进;工具执行在 CallToolsNode 内,不计入。
    图片注入:echo 工具返回 BinaryContent(模拟 read_image),让
    _prune_history_images 在后续请求构造时走真实 4MB 预算剪枝路径。
    """
    counter = [0]

    async def fn(messages, info: AgentInfo) -> ModelResponse:
        idx = counter[0]
        counter[0] += 1
        parts = []
        if thinking_chars:
            parts.append(TextPart(content="t" * thinking_chars))
        if idx < n_turns - 1:
            parts.append(ToolCallPart(tool_name="echo", args="{}"))
        else:
            parts.append(TextPart(content="done"))
        return ModelResponse(
            parts=parts,
            usage=RequestUsage(input_tokens=14000, output_tokens=100),
        )

    def echo(v: str = "x"):
        if img_bytes:
            from pydantic_ai import ToolReturn

            return ToolReturn(
                return_value="shot.png",
                content=[BinaryContent(data=b"\x89PNG" + b"i" * (img_bytes - 4),
                                       media_type="image/png")],
            )
        return "ok"

    from pydantic_ai.capabilities import ProcessHistory

    from rpent.planner.api_loop import _prune_history_images

    agent = Agent(
        FunctionModel(fn),
        instructions="perf-client-overhead",
        tools=[echo],
        capabilities=[ProcessHistory(processor=_prune_history_images)],
    )

    t_model_nodes = 0.0
    n_requests = 0
    async with agent.iter("go") as run:
        prev_ts = None
        prev_was_model = False
        async for node in run:
            now = time.perf_counter()
            if prev_was_model and not Agent.is_model_request_node(node):
                # 模型请求节点已执行完(零延迟)→ 纯客户端开销
                t_model_nodes += now - prev_ts
                n_requests += 1
            prev_ts = now
            prev_was_model = Agent.is_model_request_node(node)
            if Agent.is_call_tools_node(node):
                async with node.stream(run.ctx):
                    pass
    assert n_requests == n_turns, (n_requests, n_turns)
    return t_model_nodes


def _run_case(n_turns: int, img_bytes: int, thinking_chars: int) -> dict:
    walls = []
    total_walls = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        w = asyncio.run(_drive(n_turns, img_bytes, thinking_chars))
        total_walls.append(time.perf_counter() - t0)
        walls.append(w)
    per_turn_ms = [w / n_turns * 1000 for w in walls]
    return {
        "n_turns": n_turns,
        "img_bytes_per_turn": img_bytes,
        "thinking_chars": thinking_chars,
        "model_node_client_wall_ms_per_turn": {
            "median": round(statistics.median(per_turn_ms), 2),
            "min": round(min(per_turn_ms), 2),
            "max": round(max(per_turn_ms), 2),
        },
        "full_run_wall_s": round(statistics.median(total_walls), 2),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    # 历史长度轴:无图片、无 thinking 基线
    for turns in (4, 16, 48):
        cases.append(_run_case(turns, 0, 0))
    # 图片轴:固定 16 轮,每轮 256KB / 1MB
    for img in (256 * 1024, 1024 * 1024):
        cases.append(_run_case(16, img, 0))
    # thinking 轴:16 轮 × 4KB
    cases.append(_run_case(16, 0, 4096))
    result = {
        "protocol": "RPENT_P1_CLIENT_OVERHEAD_V1",
        "method": (
            "FunctionModel sleep=0:模型节点墙钟=纯客户端路径(图推进+请求构造"
            "+ProcessHistory 剪枝+流事件),为真实请求客户端开销的上界"
        ),
        "reference_real_model_node_wall": {"p50_s": 8, "p90_s": 33, "p95_s": 56},
        "cases": cases,
        "caveats": [
            "共享开发机单进程测量,绝对值有噪声;看数量级与趋势",
            "不含网络/服务端排队/生成(这正是要分离出去的部分)",
            "与生产差异:工具为本地 echo(真实工具还会加各自耗时,但不计在"
            "模型节点内);历史图片为合成 PNG 字节",
        ],
    }
    out = OUT / "client_overhead.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    for c in cases:
        print(json.dumps(c, ensure_ascii=False))
    print(f"[client-overhead] -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
