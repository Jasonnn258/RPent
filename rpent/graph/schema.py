"""Stage H — Frozen Local State-Transition Graph:schema 与校验。

Graph v0(rpent/resources/libero/graph_v0.yaml)是只读冻结件:
node = 抽象可观测物理/执行状态;edge = 可执行恢复/继续策略。
本模块 fail-fast:YAML 笔误(未知字段、悬空 target、guard 用了
非白名单事实键、非 frozen 状态)在加载期暴露,而不是 episode 中途。

泄露防火墙:schema 层强制 guard/verifier 的谓词键 ⊆ OBSERVABLE_FACT_KEYS
(runtime 可观测词汇,见 state_interpreter);渲染层(render.py)从
结构上拿不到 analysis_only 字段。
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

import yaml

#: runtime 可观测事实键白名单 —— guard/verifier 只允许引用这些。
#: 与 SM1 tracker 计数器 + primitive 结果字段一一对应
#: (audit §2;零 GT、零未来字段)。
OBSERVABLE_FACT_KEYS = frozenset({
    # 最近一条 primitive 结果字段(ovpm._fields_from_payload 词汇)
    "success",                 # 技能自报成功(True/False/None)
    "libero_terminated",       # 任务谓词
    "peak_lift_m",             # 抓取抬升物证
    "min_gripper_opening",     # 手爪开合
    "final_gripper_opening",
    "final_dist_m",            # move 残差
    "found",                   # 感知可用性
    "world_error",
    "descent_done",            # pi0_pick 下降段物证(result.diagnostics)
    "eef_z",                   # 末端 z(states.robot0_eef_pos[2],本体感知)
    # 解释器/SM1 风格计数器(runtime 可算)
    "target_localized",        # 最近一次定位是否给出坐标
    "consec_move_stall",       # 连续停滞 move 数(residual >= MOVE_TOL)
    "consec_pick_fails",       # 连续未成抓取数
    "release_open",            # 已开爪
    "actions_since_release",   # 开爪后步数
    "prior_pick_success",      # 上一次抓取结果(True/False/None)
})

#: guard/verifier 谓词操作符(值侧)。
PRED_OPS = frozenset({
    "true", "false", "gte", "lte", "lt", "gt", "isnull", "notnull",
    "delta_lt",
})

EDGE_FIELDS = frozenset({
    "id", "source_state", "action_family", "guard", "expected_transition",
    "target_state", "verifier", "falsify", "fallback", "evidence",
    "status", "utility",
})
NODE_FIELDS = frozenset({"desc", "terminal"})
EDGE_STATUSES = frozenset({"frozen", "candidate"})
UTILITIES = frozenset({"unknown"})  # v0 只允许 unknown(禁止人工先验)


@dataclasses.dataclass(frozen=True)
class Node:
    id: str
    desc: str
    terminal: bool


@dataclasses.dataclass(frozen=True)
class Edge:
    id: str
    source_state: str
    action_family: str
    guard: dict[str, Any]
    expected_transition: str
    target_state: str
    verifier: dict[str, Any]
    falsify: str
    fallback: str
    evidence: str
    status: str
    utility: str


@dataclasses.dataclass(frozen=True)
class Graph:
    version: str
    nodes: dict[str, Node]
    edges: list[Edge]

    def out_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source_state == node_id]

    def edge(self, edge_id: str) -> Edge | None:
        return next((e for e in self.edges if e.id == edge_id), None)


def _check_pred(pred: dict[str, Any], where: str) -> None:
    for key, spec in (pred or {}).items():
        if key not in OBSERVABLE_FACT_KEYS:
            raise ValueError(
                f"{where}: fact key {key!r} 不在 runtime 可观测白名单内")
        if isinstance(spec, dict):
            for op in spec:
                if op not in PRED_OPS:
                    raise ValueError(f"{where}: 未知谓词操作符 {op!r}")


def load_graph(path: str | os.PathLike | None = None) -> Graph:
    """加载并 fail-fast 校验 graph YAML。"""
    if path is None:
        # 冻结件随 git 走(resources/ 整体 gitignore,不放可复现性工件;
        # 线上可用 RPENT_GRAPH_FILE 覆盖)
        path = Path(__file__).resolve().parents[2] / "analysis" \
            / "graph_v0.yaml"
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    assert raw.get("meta", {}).get("version"), "meta.version 缺失"

    nodes: dict[str, Node] = {}
    for nid, spec in (raw.get("nodes") or {}).items():
        unknown = set(spec) - NODE_FIELDS
        if unknown:
            raise ValueError(f"node {nid}: 未知字段 {sorted(unknown)}")
        nodes[nid] = Node(id=nid, desc=spec.get("desc", ""),
                          terminal=bool(spec.get("terminal", False)))

    edges: list[Edge] = []
    seen_ids: set[str] = set()
    for spec in raw.get("edges") or []:
        unknown = set(spec) - EDGE_FIELDS
        if unknown:
            raise ValueError(f"edge {spec.get('id')}: 未知字段 {sorted(unknown)}")
        e = Edge(
            id=spec["id"], source_state=spec["source_state"],
            action_family=spec["action_family"],
            guard=spec.get("guard") or {},
            expected_transition=spec.get("expected_transition", ""),
            target_state=spec["target_state"],
            verifier=spec.get("verifier") or {},
            falsify=spec.get("falsify", ""),
            fallback=spec.get("fallback", ""),
            evidence=spec.get("evidence", ""),
            status=spec.get("status", "candidate"),
            utility=spec.get("utility", "unknown"),
        )
        if e.id in seen_ids:
            raise ValueError(f"edge id 重复: {e.id}")
        seen_ids.add(e.id)
        if e.source_state not in nodes:
            raise ValueError(f"edge {e.id}: source_state {e.source_state!r} 不存在")
        if e.target_state not in nodes:
            raise ValueError(f"edge {e.id}: target_state {e.target_state!r} 不存在")
        if e.status not in EDGE_STATUSES:
            raise ValueError(f"edge {e.id}: status {e.status!r} 非法")
        if e.utility not in UTILITIES:
            raise ValueError(f"edge {e.id}: utility {e.utility!r} 非法(v0 只允许 unknown)")
        if e.fallback and e.fallback not in seen_ids \
                and e.fallback not in {s["id"] for s in raw.get("edges") or []}:
            raise ValueError(f"edge {e.id}: fallback {e.fallback!r} 不存在")
        _check_pred(e.guard, f"edge {e.id}.guard")
        _check_pred(e.verifier, f"edge {e.id}.verifier")
        edges.append(e)

    # 结构完整性:每个非 terminal 节点至少 1 条出边;terminal 可为 0。
    for nid, node in nodes.items():
        if not node.terminal and not any(e.source_state == nid for e in edges):
            raise ValueError(f"node {nid}: 非终态但零出边")

    return Graph(version=str(raw["meta"]["version"]), nodes=nodes, edges=edges)
