"""Stage H — Graph 触发器运行时管线(H1 三臂共享)。

职责:维护原语结果历史 → 以与 §1 基准抽取器
(scripts/build_stageH0_failure_states.episode_counters)**完全同语义**的计数器
构造白名单事实 → 过冻结 interpreter 得 active node → 失败节点即排队触发。

零 LLM、零未来信息:输入只有当条结果 payload 的白名单字段;计数器由
历史重算(与离线基准逐点一致性由 scripts/replay_stageH1_trigger.py 校验)。
"""
from __future__ import annotations

from typing import Any

from rpent.graph.schema import load_graph
from rpent.graph.state_interpreter import interpret
from rpent.graph.retriever import legal_edges
from rpent.graph.render import render_block

#: 四个失败节点(§2 图;触发即"真实可观测物理失败状态成立")
FAILURE_NODES = frozenset({
    "FALSE_GRASP", "MOVE_STALL", "CONTACT_STALL",
    "RELEASE_PREDICATE_STALL",
})

#: 节点 → 基准家族(邻接抑制按家族键,镜像抽取器 last_fam_step;
#: MOVE_STALL 与 CONTACT_STALL 同属 MOVE_CONTACT_STALL)
NODE_FAMILY = {
    "FALSE_GRASP": "FALSE_GRASP",
    "MOVE_STALL": "MOVE_CONTACT_STALL",
    "CONTACT_STALL": "MOVE_CONTACT_STALL",
    "RELEASE_PREDICATE_STALL": "RELEASE_PREDICATE_STALL",
}

#: 结果 payload 中被保留的事实键(白名单子集 + 感知可用性)
_KEPT_FIELDS = (
    "success", "libero_terminated", "peak_lift_m",
    "min_gripper_opening", "final_gripper_opening", "final_dist_m",
    "found", "world_error",
)

MOVE_TOL = 0.03   # ovpm.py:50 冻结值(与基准抽取器同)
GRIP_OPEN = 0.05  # ovpm.py:49


def keep_fields(data: dict[str, Any]) -> dict[str, Any]:
    """结果 payload → 白名单事实键(其余键结构性丢弃)。"""
    return {k: data[k] for k in _KEPT_FIELDS if data.get(k) is not None}


def counters_from_history(hist: list[tuple[str, dict[str, Any]]]) -> dict:
    """截至最新一条的 SM1 风格计数器 —— 逐语句镜像基准
    episode_counters(steps, i=len-1):consec_move_stall(连续未到位 move)+
    move_win_first_dist(3-move 窗口首残差,趋势判据)、
    release_open/actions_since_release(最近一次 release)、
    prior_pick_success(i 之前最近一次 pi0_pick 的 success)。"""
    i = len(hist) - 1
    run_dists: list[float] = []  # 从最新向前的连续停滞 move 残差(逆序)
    for j in range(i, -1, -1):
        name, f = hist[j]
        if name not in ("move_to", "move_pose"):
            break
        d = f.get("final_dist_m")
        if isinstance(d, (int, float)) and d >= MOVE_TOL:
            run_dists.append(d)
        else:
            break
    consec_stall = len(run_dists)
    move_win_first = run_dists[2] if consec_stall >= 3 else None
    release_open = False
    since_rel = None
    prior_pick = None
    for j in range(i, -1, -1):
        name, f = hist[j]
        if name == "release" and since_rel is None:
            since_rel = i - j
            g = f.get("final_gripper_opening")
            release_open = isinstance(g, (int, float)) and g > GRIP_OPEN
        if name == "pi0_pick" and prior_pick is None and j < i:
            prior_pick = f.get("success")
    return {"consec_move_stall": consec_stall,
            "move_win_first_dist": move_win_first,
            "release_open": release_open,
            "actions_since_release": since_rel,
            "prior_pick_success": prior_pick}


def node_from_history(hist: list[tuple[str, dict[str, Any]]]) -> str:
    """历史 → active node(interpreter 唯一运行时入口)。"""
    if not hist:
        return ""
    name, f = hist[-1]
    facts = {**f, **counters_from_history(hist)}
    return interpret(facts, name)


class GraphTrigger:
    """DecisionMemory mode="graph" 的触发状态机。

    邻接抑制精确镜像基准抽取器(scripts/build_stageH0_failure_states.
    extract_points):按**基准家族键**记 last_fam_step,`last >= i-1` 即
    延续(skip 时不更新 —— 长停滞串里每隔一步可再触发,与基准同 quirk);
    step 序只计 actuation 原语(states.json 词汇,感知步不进序;基准的
    init 记录使两侧整体差一个常数位移,不改变邻接关系)。
    冲刷/冷却/上限沿用冻结的 per-result 冲刷语义;graph_block 注入时
    渲染 active node 的合法出边。
    """

    def __init__(self) -> None:
        self.hist: list[tuple[str, dict[str, Any]]] = []
        self.step_idx = -1               # actuation 原语序(0-based)
        self.last_fam_step: dict[str, int] = {}
        self.pending: dict[str, Any] | None = None  # 排队中的 {node, facts}
        self._graph = None  # 惰性加载冻结图

    @property
    def graph(self):
        if self._graph is None:
            self._graph = load_graph()
        return self._graph

    def observe(self, name: str, data: dict[str, Any],
                is_primitive: bool) -> tuple[str, dict[str, Any]] | None:
        """一条结果到达:更新历史,失败家族**新点**成立则返回 (node, facts)。
        pending 由调用方(DecisionMemory)在实际排队时写入 —— 队列已满时
        本 hit 被丢弃,pending 不被覆盖(保证渲染与排队触发一致)。"""
        if not is_primitive:
            return None  # states.json 只记 actuation;感知步不进 step 序
        self.step_idx += 1
        self.hist.append((name, keep_fields(data)))
        node = node_from_history(self.hist)
        if node not in FAILURE_NODES:
            return None
        # 基准证据步过滤:REL 的延续态(interpreter 规则 4,开爪后任意
        # 动作)是合法状态标签但不构成新证据 —— 基准 REL 点只落在
        # release 步,触发器同构(其余三家族的证据规则本就 action 门控)。
        if node == "RELEASE_PREDICATE_STALL" and name != "release":
            return None
        fam = NODE_FAMILY[node]
        if self.last_fam_step.get(fam, -99) >= self.step_idx - 1:
            return None  # 同家族邻接延续:镜像基准的 skip(不更新)
        self.last_fam_step[fam] = self.step_idx
        _, f = self.hist[-1]
        return node, {**f, **counters_from_history(self.hist)}

    def render_guidance(self) -> tuple[str, list[str]]:
        """graph_block 注入内容:active node + guard 过滤后的合法出边。"""
        assert self.pending is not None, "render 只在排队触发后调用"
        node, facts = self.pending["node"], self.pending["facts"]
        edges = legal_edges(self.graph, node, facts)
        return render_block(self.graph, node, edges), [e.id for e in edges]
