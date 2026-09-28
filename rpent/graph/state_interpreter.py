"""Stage H — State Interpreter v0(确定性规则:可观测事实 -> active node)。

零 LLM:同一输入永远同一节点;输入只接受 OBSERVABLE_FACT_KEYS 白名单
内的键(多余键直接丢弃 —— 结构上杜绝 hidden/future 字段进入)。
UNKNOWN/UNCERTAIN 允许显式输出:规则都不命中即 UNCERTAIN。

规则按优先级排列(先失败家族、后正常流);阈值全部来自冻结常数
(B2/ovpm:GRIP_OPEN=0.05、MOVE_TOL=0.03、抬升物证下限 0.005)。
"""
from __future__ import annotations

from typing import Any

from rpent.graph.schema import OBSERVABLE_FACT_KEYS

GRIP_OPEN = 0.05     # ovpm.py:49 冻结值
MOVE_TOL = 0.03      # ovpm.py:50 冻结值
LIFT_OK = 0.005      # 抓取物证下限(B2 紧握误报校准同阈值)

# 解释器需要的历史计数的默认值(runtime 由调用方喂入;
# 离线基准由抽取器写入 pre-state)。
_DEFAULTS: dict[str, Any] = {
    "success": None,
    "libero_terminated": None,
    "peak_lift_m": None,
    "min_gripper_opening": None,
    "final_gripper_opening": None,
    "final_dist_m": None,
    "found": None,
    "world_error": None,
    "descent_done": None,
    "eef_z": None,
    "target_localized": None,
    "consec_move_stall": 0,
    "move_win_first_dist": None,  # 3-move 停滞窗口的首残差(趋势判据)
    "consec_pick_fails": 0,
    "release_open": False,
    "actions_since_release": None,
    "prior_pick_success": None,
}


def observe(facts: dict[str, Any] | None) -> dict[str, Any]:
    """白名单过滤 + 默认值补齐 —— 解释器的唯一合法输入形式。"""
    f = dict(_DEFAULTS)
    for k, v in (facts or {}).items():
        if k in OBSERVABLE_FACT_KEYS:
            f[k] = v
    return f


def interpret(facts: dict[str, Any] | None, last_action: str = "") -> str:
    """可观测事实 -> active node(确定性;优先级先失败后正常)。
    last_action = 最近 primitive 名,由调用方显式传入(不在事实
    白名单内,避免与结果字段混淆)。"""
    f = observe(facts)
    action = last_action or ""

    # 0) 任务谓词已触发 -> DONE(env 官方标志)
    if f["libero_terminated"] is True:
        return "DONE"
    # 1) 感知不可用 -> UNCERTAIN(显式输出)
    if f["found"] is False or f["world_error"]:
        return "UNCERTAIN"
    # 2) 失败家族(按最近 primitive;判据与基准抽取器逐语句同构 ——
    #    MOVE_STALL = 3-move 窗口全未到位且残差不下降,consec>=2 的
    #    单纯远距 move 是 MOVE_PROGRESS)
    if action == "pi0_pick":
        if f["success"] is False:
            return "FALSE_GRASP"
        if f["success"] is True:
            lift = f["peak_lift_m"]
            if isinstance(lift, (int, float)) and lift < LIFT_OK:
                return "FALSE_GRASP"  # 自报成功但无物证 = 假握
            return "GRASP_CONFIRMED" if isinstance(lift, (int, float)) \
                else "GRASP_CHECK"
    if action == "pi0_doubled" and f["success"] is False:
        return "CONTACT_STALL"
    if action == "release" and f["release_open"] is True:
        return "RELEASE_PREDICATE_STALL"  # 开爪成功但谓词未触发(规则 0 未命中)
    if action in ("move_to", "move_pose"):
        d = f["final_dist_m"]
        if isinstance(d, (int, float)):
            wf = f["move_win_first_dist"]
            if f["consec_move_stall"] >= 3 and isinstance(wf, (int, float)) \
                    and d >= wf - 1e-4:
                return "MOVE_STALL"  # 3 连 move 未到位且残差不降(基准窗口)
            return "MOVE_PROGRESS"  # 到位 / 在途 / 残差在降 = 有进展
    # 3) 放置准备:持物(上次抓取有物证)且未开爪
    if f["prior_pick_success"] is True and f["release_open"] is not True:
        return "PLACE_CHECK"
    # 4) 开爪后任意后续动作仍无谓词 -> 释放停滞延续
    # (状态标签语义;H1 触发器只在 release 证据步触发 —— 见 pipeline)
    if f["release_open"] is True and isinstance(
            f["actions_since_release"], int):
        return "RELEASE_PREDICATE_STALL"
    # 5) 尚无抓取尝试 -> 预抓取
    if f["prior_pick_success"] is None:
        return "PRE_GRASP"
    # 6) 兜底:显式 UNCERTAIN
    return "UNCERTAIN"


def node_label(facts: dict[str, Any] | None, last_action: str) -> str:
    """带最近 primitive 名的判定入口(runtime 侧统一走这里)。"""
    return interpret(facts, last_action)
