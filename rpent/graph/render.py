"""Stage H — Graph 渲染:active node + legal edges -> planner 注入块。

结构与 F3/F4 先例一致(G0.5/G0.6 注入块风格)。渲染禁忌(镜像 B2
纪律,PhaseTracker pick 启发式会 grep 特定词):渲染文本不得包含
"fail"/"error"/"could not"/"no object" 子串 —— 节点/边文本一律用
中性表述;evidence_id(可能含 banned 子串)永不渲染。
"""
from __future__ import annotations

from rpent.graph.schema import Graph

_BANNED = ("fail", "error", "could not", "no object")

# 节点 -> planner 可读的一行描述(中性词汇,与 YAML desc 对齐但去黑名单词)
NODE_LABELS = {
    "PRE_GRASP": "grasp not yet attempted (localizing/approaching)",
    "GRASP_CHECK": "grasp reported but physical evidence pending",
    "GRASP_CONFIRMED": "grasp physically established (lift evidence)",
    "FALSE_GRASP": "grasp not established (no lift evidence or reported otherwise)",
    "MOVE_PROGRESS": "transport progressing or arrived",
    "MOVE_STALL": "transport stalled (residual not decreasing)",
    "CONTACT_STALL": "contact skill did not conclude the task",
    "PLACE_CHECK": "holding object above placement region",
    "RELEASE_PREDICATE_STALL": "gripper opened but task predicate not yet fired",
    "UNCERTAIN": "observable evidence insufficient — needs a targeted look",
    "DONE": "task predicate fired",
}

_HEADER = "[STATE-GRAPH GUIDANCE]"


def render_block(graph: Graph, active_node: str,
                 legal: list, evidence: dict | None = None) -> str:
    """渲染当前节点引导块。legal 为空时退化为节点状态 + 观察提示
    (绝不渲染整图)。"""
    lines = [
        _HEADER,
        f"active state: {active_node} — {NODE_LABELS.get(active_node, '')}",
        "Legal next strategies for this state (context, not an order — "
        "judge against the current scene):",
    ]
    for i, e in enumerate(legal, 1):
        lines.append(
            f"{chr(64 + i)}. [{e.id}] {e.action_family}\n"
            f"   expected: {e.expected_transition}\n"
            f"   verify by: {_fmt_verifier(e.verifier)}\n"
            f"   if expected change absent: {e.falsify or 're-evaluate state'}"
        )
    if not legal:
        lines.append(
            "No legal strategy for this state — take one targeted "
            "observation, then re-evaluate.")
    block = "\n".join(lines)
    # 防线:渲染产物硬校验禁词(结构上 evidence_id 不进 render,这里兜底)
    low = block.lower()
    assert not any(b in low for b in _BANNED), \
        f"rendered block contains banned substring: {[b for b in _BANNED if b in low]}"
    return block


def _fmt_verifier(verifier: dict) -> str:
    parts = []
    for k, spec in (verifier or {}).items():
        if spec is True:
            parts.append(f"{k} == True")
        elif isinstance(spec, dict):
            for op, x in spec.items():
                sym = {"gte": ">=", "lte": "<=", "lt": "<", "gt": ">",
                       "delta_lt": "delta <"}.get(op, op)
                parts.append(f"{k} {sym} {x}")
        else:
            parts.append(f"{k} = {spec}")
    return "; ".join(parts) or "task predicate / latest observable result"
