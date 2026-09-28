"""Stage H — Graph Retriever:active node -> legal outgoing edges。

只暴露:active node、observable evidence、legal outgoing edges(含
guard/expected/falsify 摘要)。**不**把整张图塞进 prompt。
guard 评估 = 确定性谓词求值(同一谓词词汇),不满足的边不进 legal 集。
"""
from __future__ import annotations

from typing import Any

from rpent.graph.schema import Graph
from rpent.graph.state_interpreter import observe

MOVE_TOL = 0.03


def _eval_pred(pred: dict[str, Any], f: dict[str, Any]) -> bool:
    """谓词求值:键=事实键;值=True/False 精确匹配、数值比较、或
    {op: x} 操作符形式。全部确定性。"""
    for key, spec in pred.items():
        v = f.get(key)
        if spec is True:
            if v is not True:
                return False
        elif spec is False:
            # 约定:false 谓词 = 明确为 False 或尚无信息(None)
            # (如 target_localized 在首步感知前是 None,语义即"未定位")
            if v is True:
                return False
        elif spec is None:
            if v is not None:
                return False
        elif isinstance(spec, dict):
            for op, x in spec.items():
                if op == "gte":
                    if not (isinstance(v, (int, float)) and v >= x):
                        return False
                elif op == "lte":
                    if not (isinstance(v, (int, float)) and v <= x):
                        return False
                elif op == "lt":
                    if not (isinstance(v, (int, float)) and v < x):
                        return False
                elif op == "gt":
                    if not (isinstance(v, (int, float)) and v > x):
                        return False
                elif op == "isnull":
                    if v is not None:
                        return False
                elif op == "notnull":
                    if v is None:
                        return False
                else:
                    raise ValueError(f"未知谓词操作符 {op!r}")
        else:
            raise ValueError(f"谓词值类型非法: {key}={spec!r}")
    return True


def legal_edges(graph: Graph, active_node: str,
                facts: dict[str, Any] | None) -> list:
    """active node 的合法出边(guard 全过的)。guard 空字典 = 恒真。"""
    f = observe(facts)
    return [e for e in graph.out_edges(active_node)
            if _eval_pred(e.guard, f)]


def transition_summary(edge) -> dict[str, Any]:
    """edge 的 runtime 视图(渲染/路由共用的最小字段)。"""
    return {
        "edge_id": edge.id,
        "action_family": edge.action_family,
        "expected_transition": edge.expected_transition,
        "verifier": edge.verifier,
        "falsify": edge.falsify,
        "fallback": edge.fallback or None,
    }
