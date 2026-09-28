#!/usr/bin/env python3
"""Stage H1 graph-trigger unit tests (no GPU, no network).

Covers the stageH1_prereg.md §3(a) regression contract BEFORE any H1 episode:
  1  FG 触发 + 基准邻接 quirk(连败 pick:第1步触发、第2步抑制、第3步再触发)
  2  MOVE_STALL 窗口规则:2 个远距 move 不触发;3 个不降触发;3 个在降不触发
  3  REL:release 证据步触发;set_gripper 延续步(interpreter 规则 4)不触发
  4  graph_block 注入:STATE-GRAPH 头 + 合法边 + 事件带 graph_node/edges
  5  H1-P2 臂:注入 = GENERIC_REFRESH_BLOCK 逐字节(= g05P2 内容)
  6  H1-CARD 臂:注入 = _memory_only_block(top3) 逐字节(= g05P3 内容)
  7  冲刷语义:冷却内的排队触发被丢弃(冻结语义,不推迟)
  8  env 守卫:graph 只配 H1 三注入模式;graph_block 不配 v1_per_result

Usage: python scripts/test_stageH1_trigger.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpent.memory.retrieval import (  # noqa: E402
    DecisionMemory, GENERIC_REFRESH_BLOCK, MEMORY_CONTEXT_HEADER,
)

REPO = Path(__file__).resolve().parent.parent
PASS = FAIL = 0


class FakeTracker:
    def current_phase(self):
        return "P_transport"

    def recovery_pending(self):
        return False


ENV_KEYS = ("RPENT_MEMORY_TRIGGER", "RPENT_MEMORY_INJECTION_MODE",
            "RPENT_MEMORY_QUERY_MODE", "RPENT_MEMORY_RANK",
            "RPENT_MEMORY_QUERY_REASON", "RPENT_MEMORY_BLOCK_REASON")
TL = {"task_language": "put the alphabet soup in the basket"}


def fresh(injection="graph_block"):
    """graph 触发 + 指定注入模式的干净 DecisionMemory(H1 臂 env)。"""
    for k in ENV_KEYS:
        os.environ.pop(k, None)
    os.environ.update({
        "RPENT_MEMORY_TRIGGER": "graph",
        "RPENT_MEMORY_INJECTION_MODE": injection,
        "RPENT_MEMORY_QUERY_MODE": "common",
        "RPENT_MEMORY_RANK": "Q0_FIXED",
        "RPENT_MEMORY_QUERY_REASON": "0",
        **({"RPENT_MEMORY_BLOCK_REASON": "0"}
           if injection == "memory_only" else {}),
    })
    dm = DecisionMemory(FakeTracker(), mode="graph")
    dm.task_language = TL["task_language"]
    return dm


def step(dm, i, name, result, term=False):
    """喂一步(结果 + boundary),返回本步注入块(或 None)。"""
    dm.on_tool_result(name, json.dumps({**result, **TL,
                                        "libero_terminated": term}), False)
    return dm.turn_boundary(i + 1)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def t1_fg_adjacency():
    print("1 FALSE_GRASP 触发 + 邻接 quirk")
    dm = fresh()
    out0 = step(dm, 0, "pi0_pick", {"success": False})
    check("首败 pick 触发", out0 is not None
          and out0[1]["graph_node"] == "FALSE_GRASP")
    out1 = step(dm, 1, "pi0_pick", {"success": False})
    check("紧邻第 2 败 pick 抑制(基准 skip)", out1 is None)
    out2 = step(dm, 2, "pi0_pick", {"success": False})
    check("第 3 败 pick 再触发(skip-不更新 quirk)", out2 is not None)


def t2_move_window():
    print("2 MOVE_STALL 窗口规则")
    dm = fresh()
    check("2 个远距 move 不触发",
          step(dm, 0, "move_to", {"final_dist_m": 0.12}) is None
          and step(dm, 1, "move_to", {"final_dist_m": 0.11}) is None)
    dm = fresh()
    out = None
    for i, d in enumerate([0.10, 0.11, 0.12]):
        out = step(dm, i, "move_to", {"final_dist_m": d})
    check("3 个不降远距 move 在窗口完成步触发",
          out is not None and out[1]["graph_node"] == "MOVE_STALL")
    dm = fresh()
    out = None
    for i, d in enumerate([0.12, 0.11, 0.10]):
        out = step(dm, i, "move_to", {"final_dist_m": d})
    check("3 个在降 move(有进展)不触发", out is None)


def t3_rel_evidence_only():
    print("3 REL 证据步触发 / 延续步不触发")
    dm = fresh()
    out = step(dm, 0, "release", {"final_gripper_opening": 0.08})
    check("release 开爪未触发谓词 → 触发 REL",
          out is not None
          and out[1]["graph_node"] == "RELEASE_PREDICATE_STALL")
    out1 = step(dm, 1, "set_gripper", {})
    check("延续步(set_gripper,规则 4 标签)不触发", out1 is None)
    dm = fresh()
    check("release 未开爪不触发",
          step(dm, 0, "release", {"final_gripper_opening": 0.02}) is None)


def t4_graph_block_content():
    print("4 graph_block 注入内容")
    dm = fresh()
    out = step(dm, 0, "pi0_pick", {"success": False})
    blk, ev = out
    check("头 = [STATE-GRAPH GUIDANCE]", blk.startswith("[STATE-GRAPH"))
    check("含合法边 id", "FG-" in blk)
    check("事件带 graph_node / graph_legal_edges",
          ev["graph_node"] == "FALSE_GRASP" and len(ev["graph_legal_edges"]) > 0)
    check("事件 reason = graph:state=...",
          ev["trigger_reason"] == "graph:state=FALSE_GRASP")
    check("retrieval NOT_RUN", ev["retrieval_status"] == "NOT_RUN")
    banned = ("fail", "error", "could not", "no object")
    check("无 B2 违禁词", not any(b in blk.lower() for b in banned))


def t5_p2_arm():
    print("5 H1-P2 臂内容逐字节")
    dm = fresh(injection="generic_refresh")
    out = step(dm, 0, "pi0_pick", {"success": False})
    check("注入 = GENERIC_REFRESH_BLOCK 逐字节",
          out is not None and out[0] == GENERIC_REFRESH_BLOCK)


def t6_card_arm():
    print("6 H1-CARD 臂内容逐字节")
    dm = fresh(injection="memory_only")
    ids = dm.ids[:3]
    dm._q0_fixed = lambda q: (ids, ids)  # noqa: E731 - 打桩排序
    out = step(dm, 0, "pi0_pick", {"success": False})
    check("触发并注入卡片", out is not None)
    blk, ev = out
    want = dm._memory_only_block(ev["top3_memories"])
    check("注入 = _memory_only_block(top3) 逐字节(= g05P3 渲染)",
          blk == want and blk.startswith(MEMORY_CONTEXT_HEADER))
    check("reason 不进 query/正文(generic 词表无 graph 词汇)",
          "graph:state" not in blk)


def t7_cooldown():
    print("7 冷却丢弃(冻结冲刷语义)")
    dm = fresh()
    step(dm, 0, "pi0_pick", {"success": False})       # 触发并冲刷
    out = step(dm, 1, "pi0_doubled", {"success": False})  # 排队 CONTACT
    check("冷却内的第 2 家族触发被丢弃(不推迟)", out is None)
    out2 = None
    for i, (n, r) in enumerate([("move_to", {"final_dist_m": 0.01}),
                                ("move_to", {"final_dist_m": 0.01}),
                                ("pi0_doubled", {"success": False})]):
        out2 = step(dm, i + 2, n, r)
    check("冷却过后同类证据可再触发", out2 is not None
          and out2[1]["graph_node"] == "CONTACT_STALL")


def t8_env_guards():
    print("8 env 守卫")
    for inj in ("full", "reason_only", "none"):
        try:
            fresh(injection=inj)
            check(f"graph + {inj} 拒绝", False)
        except ValueError:
            check(f"graph + {inj} 拒绝", True)
    for k in ENV_KEYS:
        os.environ.pop(k, None)
    os.environ.update({"RPENT_MEMORY_TRIGGER": "v1_per_result",
                       "RPENT_MEMORY_INJECTION_MODE": "graph_block",
                       "RPENT_MEMORY_QUERY_MODE": "common",
                       "RPENT_MEMORY_RANK": "Q0_FIXED",
                       "RPENT_MEMORY_QUERY_REASON": "0"})
    try:
        DecisionMemory(FakeTracker(), mode="v1_per_result")
        check("graph_block + v1_per_result 拒绝", False)
    except ValueError:
        check("graph_block + v1_per_result 拒绝", True)


if __name__ == "__main__":
    for t in (t1_fg_adjacency, t2_move_window, t3_rel_evidence_only,
              t4_graph_block_content, t5_p2_arm, t6_card_arm, t7_cooldown,
              t8_env_guards):
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
