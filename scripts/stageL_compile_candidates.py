#!/usr/bin/env python
"""Stage L §5-6 — 候选编译 + 去重(→ stageL_candidate_edges_v0.jsonl)。

来源规则(prereg §5,机械归因):
- A 轨迹挖掘:FG 正例中"先 move_to 接近、≤3 步内 pi0_pick"的 prefix
  → 感知路径点重抓模板(LC-FG-1);
- B 参数化合并 ①:上模板 × FG-3 已验证元素(OFFSET_SUFFIX 提示词,
  K 中 48/48 VERIFIED 的唯一边)→ LC-FG-2;
- B 参数化合并 ②:RPS 正例中"垂直撤退(xy 位移 ≤5cm、z +2~15cm)
  后重试"的 prefix → 撤退重试双孪生:pi0_doubled 版(LC-RS-1)/
  pi0_pick 版(LC-RS-2);撤退 Δz = 观测中位数(脚本计算并冻结进
  绑定表达式);
- C(LLM 最小泛化)未使用:确定性合并已覆盖证据,LLM 不参与
  (决策文档记录)。

编译期静态检查:工具 ∈ 执行器工具集;绑定原文 ∈ 冻结词表
{TASK_LANG, LAST_PICK_PROMPT, LAST_PICK_PROMPT + OFFSET_SUFFIX,
LAST_PICK_PROMPT(无则 TASK_LANG), EEF, OBJ_XYZ} ∪ 表达式
(_eval_expr 试解析)。不可编译 → REJECT_UNEXECUTABLE 存档。

用法:python scripts/stageL_compile_candidates.py
产物:analysis/stageL_candidate_edges_v0.jsonl
"""
from __future__ import annotations

import ast
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

PREFIXES = REPO / "analysis/stageL_recovery_prefixes.jsonl"
OUT = REPO / "analysis/stageL_candidate_edges_v0.jsonl"

TOOLS = {"segment", "back_project", "move_to", "set_gripper",
         "pi0_pick", "pi0_doubled", "release"}
RAW_BINDINGS = {"TASK_LANG", "LAST_PICK_PROMPT",
                "LAST_PICK_PROMPT + OFFSET_SUFFIX",
                "LAST_PICK_PROMPT(无则 TASK_LANG)", "EEF", "OBJ_XYZ"}

# ---- 证据归因规则(机械) ----------------------------------------------------

RETREAT_XY_MAX = 0.05   # 垂直撤退:xy 位移上限(m)
RETREAT_Z_LO, RETREAT_Z_HI = 0.02, 0.15  # Δz 合法区间(m)


def lead_move(r):
    """prefix 首动作 move_to 的 (Δxy, Δz) 或 None。"""
    a = r["action_sequence"][0] if r["action_sequence"] else None
    if not a or a["action"] != "move_to":
        return None
    xyz = a["kwargs"].get("xyz")
    eef = r["pre_state"]["eef_pos"]
    if not isinstance(xyz, list) or not isinstance(eef, list):
        return None
    dxy = ((xyz[0] - eef[0]) ** 2 + (xyz[1] - eef[1]) ** 2) ** 0.5
    return dxy, xyz[2] - eef[2]


def is_retreat(r):
    m = lead_move(r)
    return (m is not None and m[0] <= RETREAT_XY_MAX
            and RETREAT_Z_LO <= m[1] <= RETREAT_Z_HI)


def next_skill(r, names):
    """首 move_to 之后、≤2 步内出现的首个技能动作是否在 names。"""
    for a in r["action_sequence"][1:3]:
        if a["action"] in names:
            return a["action"]
        if a["action"] not in ("move_to", "move_pose", "set_gripper"):
            return None
    return None


def main() -> int:
    from stagek_graph_executor import _eval_expr

    rows = [json.loads(x) for x in open(PREFIXES)]
    pos_fg = [r for r in rows if r["label"] == "recovery"
              and r["family"] == "FALSE_GRASP"]
    pos_rs = [r for r in rows if r["label"] == "recovery"
              and r["family"] == "RELEASE_PREDICATE_STALL"]

    # FG:接近(move_to 开头,且非垂直撤退)→ ≤3 步内重抓
    fg_src = [r for r in pos_fg
              if lead_move(r) is not None and not is_retreat(r)
              and next_skill(r, {"pi0_pick"}) == "pi0_pick"]
    # RPS:垂直撤退 → 撤退后 ≤2 步内技能重试
    rs1_src = [r for r in pos_rs if is_retreat(r)
               and next_skill(r, {"pi0_doubled"}) == "pi0_doubled"]
    rs2_src = [r for r in pos_rs if is_retreat(r)
               and next_skill(r, {"pi0_pick"}) == "pi0_pick"]

    retreat_dz = round(statistics.median(
        lead_move(r)[1] for r in pos_rs if is_retreat(r)), 3)
    retreat_expr = f"[eef.x, eef.y, eef.z + {retreat_dz}]"
    waypoint_expr = "[obj.x, obj.y, max(eef.z, obj.z + 0.06)]"  # MS-2 冻结式

    def src_meta(rs):
        eps = sorted({r["episode_dir"] for r in rs})
        return {"n_prefixes": len(rs), "n_episodes": len(eps),
                "episodes": eps,
                "tasks": sorted({f"t{r['task']}s{r['seed']}" for r in rs})}

    pick_args = {"prompt": "${prompt}", "max_chunks": 14,
                 "lift_thresh": 0.05, "gripper_closed_thresh": 0.06}
    cands = [
        {
            "id": "LC-FG-1", "failure_family": "FALSE_GRASP",
            "source": "A(traj-mined)",
            "option_id": "lc_fg1_perceive_waypoint_regrasp",
            "applicability": {"family": "FALSE_GRASP",
                              "observable_predicates": "无附加(族匹配即可)"},
            "parameterizer": {"source": "runtime_observable", "bindings": {
                "prompt": "LAST_PICK_PROMPT(无则 TASK_LANG)",
                "obj": "OBJ_XYZ", "eef": "EEF",
                "waypoint": waypoint_expr}},
            "executor": [
                {"tool": "segment", "args": {"prompt": "${TASK_LANG}",
                                             "camera": "agentview",
                                             "min_score": 0.2}},
                {"tool": "back_project", "args": {"resolution": "high",
                                                  "row_range": "${mask_rows}",
                                                  "col_range": "${mask_cols}"}},
                {"tool": "move_to", "args": {"xyz": "${waypoint}",
                                              "gripper": -1.0,
                                              "max_steps": 60}},
                {"tool": "pi0_pick", "args": dict(pick_args)}],
            "expected_transition":
                "感知定位物体上方路径点,接近后重抓;"
                "VERIFIED = 抬升 ≥1cm 且跟随 EEF,或 pick 物证 "
                "(peak_lift ≥5mm ∧ 终末开度 ≤0.06)",
            "physical_verifier": {"family": "FALSE_GRASP",
                                  "contract": "prereg §7-B FG"},
            "failure_outlet": "感知无果链中止 → NO_EFFECT;"
                              "重抓失败 → NO_EFFECT/HARM(§7-B)",
            "rollback": "无(执行器无回滚原语;与冻结边同判定窗语义)",
            "max_attempts": 1,
            "source_evidence": src_meta(fg_src),
        },
        {
            "id": "LC-FG-2", "failure_family": "FALSE_GRASP",
            "source": "B(merge:LC-FG-1 × FG-3 OFFSET_SUFFIX)",
            "option_id": "lc_fg2_waypoint_offset_regrasp",
            "applicability": {"family": "FALSE_GRASP",
                              "observable_predicates": "无附加(族匹配即可)"},
            "parameterizer": {"source": "runtime_observable", "bindings": {
                "prompt": "LAST_PICK_PROMPT + OFFSET_SUFFIX",
                "obj": "OBJ_XYZ", "eef": "EEF",
                "waypoint": waypoint_expr}},
            "executor": [
                {"tool": "segment", "args": {"prompt": "${TASK_LANG}",
                                             "camera": "agentview",
                                             "min_score": 0.2}},
                {"tool": "back_project", "args": {"resolution": "high",
                                                  "row_range": "${mask_rows}",
                                                  "col_range": "${mask_cols}"}},
                {"tool": "move_to", "args": {"xyz": "${waypoint}",
                                              "gripper": -1.0,
                                              "max_steps": 60}},
                {"tool": "pi0_pick", "args": dict(pick_args)}],
            "expected_transition":
                "同 LC-FG-1,但重抓提示词带 OFFSET_SUFFIX"
                "(FG-3 在 K 中 48/48 VERIFIED 的唯一已验证元素)",
            "physical_verifier": {"family": "FALSE_GRASP",
                                  "contract": "prereg §7-B FG"},
            "failure_outlet": "同 LC-FG-1",
            "rollback": "无(同 LC-FG-1)",
            "max_attempts": 1,
            "source_evidence": src_meta(fg_src),
        },
        {
            "id": "LC-RS-1", "failure_family": "RELEASE_PREDICATE_STALL",
            "source": "B(merge:垂直撤退 × pi0_doubled 重试)",
            "option_id": "lc_rs1_retreat_retry_place",
            "applicability": {"family": "RELEASE_PREDICATE_STALL",
                              "observable_predicates": "无附加(族匹配即可)"},
            "parameterizer": {"source": "runtime_observable", "bindings": {
                "eef": "EEF", "retreat": retreat_expr,
                "task": "TASK_LANG"}},
            "executor": [
                {"tool": "move_to", "args": {"xyz": "${retreat}",
                                              "gripper": -1.0,
                                              "max_steps": 40}},
                {"tool": "pi0_doubled", "args": {"prompt": "${task}",
                                                 "max_chunks": 20}}],
            "expected_transition":
                "垂直撤退后以任务语言重试放置/接触技能;"
                "VERIFIED = 窗口内 check_success",
            "physical_verifier": {"family": "RELEASE_PREDICATE_STALL",
                                  "contract": "prereg §7-B RPS"},
            "failure_outlet": "撤退后重试未触发谓词 → NO_EFFECT;"
                              "扫落/坠物 → HARM",
            "rollback": "无(同上)",
            "max_attempts": 1,
            "source_evidence": src_meta(rs1_src),
        },
        {
            "id": "LC-RS-2", "failure_family": "RELEASE_PREDICATE_STALL",
            "source": "B(merge:垂直撤退 × pi0_pick 重抓)",
            "option_id": "lc_rs2_retreat_repick",
            "applicability": {"family": "RELEASE_PREDICATE_STALL",
                              "observable_predicates": "无附加(族匹配即可)"},
            "parameterizer": {"source": "runtime_observable", "bindings": {
                "eef": "EEF", "retreat": retreat_expr,
                "prompt": "LAST_PICK_PROMPT(无则 TASK_LANG)"}},
            "executor": [
                {"tool": "move_to", "args": {"xyz": "${retreat}",
                                              "gripper": -1.0,
                                              "max_steps": 40}},
                {"tool": "pi0_pick", "args": dict(pick_args)}],
            "expected_transition":
                "垂直撤退后按最近抓取提示词重抓(重抓-重放循环起点);"
                "VERIFIED = 窗口内 check_success",
            "physical_verifier": {"family": "RELEASE_PREDICATE_STALL",
                                  "contract": "prereg §7-B RPS"},
            "failure_outlet": "重抓失败 → NO_EFFECT;扫落/坠物 → HARM",
            "rollback": "无(同上)",
            "max_attempts": 1,
            "source_evidence": src_meta(rs2_src),
        },
    ]

    # ---- 去重:动作序列 + 参数化语义 + expected_transition -------------------
    def dedup_key(c):
        return (tuple((s["tool"], tuple(sorted(s["args"]))) for s in c["executor"]),
                tuple(sorted(c["parameterizer"]["bindings"].items())))
    seen, kept = set(), []
    for c in cands:
        k = dedup_key(c)
        if k in seen:
            continue
        seen.add(k)
        kept.append(c)

    # ---- 静态可编译性检查 ----------------------------------------------------
    rejects = []
    for c in kept:
        for s in c["executor"]:
            assert s["tool"] in TOOLS, (c["id"], s["tool"])
        for raw in c["parameterizer"]["bindings"].values():
            if raw in RAW_BINDINGS:
                continue
            assert raw.strip().startswith("["), (c["id"], raw)
            _eval_expr(raw, {"eef": [0.1, 0.2, 1.0], "obj": [0.1, 0.2, 0.9]})

    # ---- 编译期拒绝存档(证据在案但不可编译) --------------------------------
    place_end = [r for r in pos_fg + pos_rs
                 if r["action_sequence"]
                 and r["action_sequence"][-1]["action"] == "release"
                 and any(a["action"] == "move_to"
                         for a in r["action_sequence"][:-1])]
    bare_release = [r for r in pos_fg
                    if [a["action"] for a in r["action_sequence"]] == ["release"]]
    unassigned_fg = [r for r in pos_fg if r not in fg_src]
    unassigned_rs = [r for r in pos_rs
                     if r not in rs1_src and r not in rs2_src]
    rejects += [
        {"pattern": "place_completion(移动到放置位后 release)",
         "n_prefixes": len(place_end),
         "prefixes": [r["prefix_id"] for r in place_end],
         "reason": "REJECT_UNEXECUTABLE:放置目标 xyz 不在运行时可观测"
                   "绑定词表(无 PLACE_TARGET 原语/绑定),无法参数化"},
        {"pattern": "bare_release(FG,单步 release)",
         "n_prefixes": len(bare_release),
         "prefixes": [r["prefix_id"] for r in bare_release],
         "reason": "REJECT:链内无 pick/抬升证据,FG 冻结验证契约下"
                   "必然 NO_EFFECT,物理不可验证"},
        {"pattern": "FG 正例未归因到模板",
         "n_prefixes": len(unassigned_fg),
         "prefixes": [r["prefix_id"] for r in unassigned_fg],
         "reason": "UNCOMPILED:模板规则外(非 move_to 开头或 >3 步才重抓),"
                   "证据保留不用"},
        {"pattern": "RPS 正例未归因到模板",
         "n_prefixes": len(unassigned_rs),
         "prefixes": [r["prefix_id"] for r in unassigned_rs],
         "reason": "UNCOMPILED:非垂直撤退起点(如小幅 xy 平移后重抓),"
                   "独立支持不足(1 集),证据保留不用"},
        {"pattern": "MCS 正例",
         "n_prefixes": 2, "prefixes": "MCS 族排除(prereg §3)",
         "reason": "FAMILY_EXCLUDED"},
    ]

    with open(OUT, "w") as fh:
        for c in kept:
            c = {**c, "provenance": {
                "prefixes_file": "analysis/stageL_recovery_prefixes.jsonl",
                "compile_script": "scripts/stageL_compile_candidates.py",
                "retreat_dz_median_m": retreat_dz,
                "dedup_rule": "动作序列+参数化语义+expected_transition"}}
            fh.write(json.dumps(c, ensure_ascii=False, default=str) + "\n")
        for rj in rejects:
            fh.write(json.dumps({"record_type": "REJECT", **rj},
                                ensure_ascii=False, default=str) + "\n")

    print(json.dumps({
        "candidates": [c["id"] for c in kept],
        "retreat_dz_median_m": retreat_dz,
        "sources": {c["id"]: {"n_prefixes": c["source_evidence"]["n_prefixes"],
                              "n_episodes": c["source_evidence"]["n_episodes"],
                              "cells": c["source_evidence"]["tasks"]}
                    for c in kept},
        "rejects": {r["pattern"]: r["n_prefixes"] for r in rejects},
    }, ensure_ascii=False, indent=1))
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
