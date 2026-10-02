#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §4-§6 — O-A 离线恢复来源审计(descriptive,不作 confirmatory 证据)。

对象:Stage N 的 24 个 failure snapshots 的源 episode(Full Planner 轨迹)。
对每个 case 审计 t_failure(=t0,Stage N 已核验的 genuine failure)到
t_recovery 之间 Full Planner 实际做了什么。

数据源:
- states.json:逐步 command/result/state(物理状态与技能调用)
- transcript_*.json:GLM planner 全对话(turns、tool calls、文本)

行为计数(全部确定性规则,零 LLM):
- primitive_count_to_recovery / planner_turns_to_recovery
- observation_count(view/segment/back_project 等)与 grounding_update_count
  (segment/back_project,来自 transcript 工具调用)
- subgoal_change_count(窗口内 pick/doubled prompt 与失败 prompt 不同的次数)
- skill_family_change_count(动作族切换次数)
- repertoire 标记:是否用了 pi0_doubled / move_pose(local recovery 词汇表外)

恢复时刻(分开记录,不合并):
- t_hold(FG 族):失败后首个 min_gripper_opening<0.03 且 peak_lift_m≥0.05
  的 pick(≈ "object lifted AND follows EEF" 的 states.json 可观测代理)
- t_task_done:失败后首个 libero_terminated=True(ground truth 任务完成)

机制标签(多标签,descriptive):
SAMPLING_LIKE / CONDITIONING_CHANGE / SEQUENCE_COMPOSITION /
DYNAMIC_REPLANNING / RESET_REALIGNMENT / UNRESOLVED

输出:analysis/stageO_offline_recovery_audit.csv / .md
"""
from __future__ import annotations

import csv
import io
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANI = REPO / "analysis/stageN1_split_manifest.csv"
OUT_CSV = REPO / "analysis/stageO_offline_recovery_audit.csv"
OUT_MD = REPO / "analysis/stageO_offline_recovery_audit.md"

ACTION_TOOLS = {"move_to", "pi0_pick", "pi0_doubled", "set_gripper",
                "release", "rotate_wrist", "rotate_pitch", "move_pose"}
GROUNDING_TOOLS = {"segment", "back_project"}
OBS_TOOLS = {"view_driver_state", "view_camera_meta", "read_image",
             "view_wrist_image"} | GROUNDING_TOOLS

FAMILY = {
    "move_to": "approach", "pi0_pick": "pick", "pi0_doubled": "doubled",
    "move_pose": "place", "set_gripper": "gripper", "release": "gripper",
    "rotate_wrist": "realign", "rotate_pitch": "realign",
}
HOLD_CLOSED = 0.03
HOLD_LIFT = 0.05

FIELDS = [
    "case_id", "task", "seed", "failure_family", "procedure", "t0",
    "episode_total_steps", "source_recovered",
    # 失败时刻物理状态 / grounding
    "fail_eef_pos", "fail_gripper_qpos", "fail_pick_target_xyz",
    "fail_pick_min_opening", "fail_pick_peak_lift",
    # 恢复时刻
    "t_hold", "t_task_done", "t_recovery_window_end",
    # Full Planner 行为
    "changed_target_reference", "changed_target_pose", "changed_subgoal",
    "resampled_same_skill", "called_different_skill", "used_multistep_sequence",
    "observation_conditioned_replan", "retreat_realign", "returned_nominal",
    "used_pi0_doubled", "used_move_pose",
    # 计数
    "primitive_count_to_recovery", "planner_turns_to_recovery",
    "observation_count", "grounding_update_count", "subgoal_change_count",
    "skill_family_change_count",
    # 机制标签 / 亚型
    "mechanism_labels", "subtype", "held_raw_flag", "inferred_held_at_failure",
    "recovery_action_sequence",
]


def read_manifest() -> list[dict]:
    with open(MANI, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def load_case(m: dict) -> dict:
    ed = Path(m["episode_dir"])
    steps = sorted(json.load(open(ed / "states.json")),
                   key=lambda s: s.get("step_idx", 0))
    tfiles = list(ed.glob("transcript_*.json"))
    trans = json.load(open(tfiles[0])) if tfiles else None
    return {"steps": steps, "transcript": trans}


def transcript_timeline(trans: dict | None) -> list[dict]:
    """transcript → 按序事件流(action 工具与观察工具,带 turn 序号)。

    action 工具与 states.json 命令 1:1(已抽验),观察工具只在此出现。
    """
    events = []
    if not trans:
        return events
    for ti, msg in enumerate(trans.get("messages", [])):
        if msg.get("role") != "assistant" or not isinstance(
                msg.get("content"), list):
            continue
        for b in msg["content"]:
            if b.get("type") != "tool_use":
                continue
            name = b.get("name") or ""
            if name in ACTION_TOOLS:
                events.append({"turn": ti, "kind": "action", "tool": name,
                               "input": b.get("input") or {}})
            elif name in OBS_TOOLS:
                events.append({"turn": ti, "kind": "obs", "tool": name,
                               "input": b.get("input") or {}})
    return events


def audit_case(m: dict) -> dict:
    data = load_case(m)
    steps, events = data["steps"], transcript_timeline(data["transcript"])
    by_idx = {s.get("step_idx"): s for s in steps}
    t0 = int(m["t0"])
    fail_step = by_idx.get(t0) or {}
    fail_cmd = fail_step.get("command") or {}
    fail_res = fail_step.get("result") or {}
    fail_state = fail_step.get("state") or {}

    # --- 恢复时刻 -------------------------------------------------------
    cont = [s for s in steps if (s.get("step_idx") or 0) > t0]
    t_task_done = t_hold = None
    for s in cont:
        idx = s.get("step_idx")
        r = s.get("result") or {}
        c = s.get("command") or {}
        if t_hold is None and c.get("action") == "pi0_pick":
            mo, pl = r.get("min_gripper_opening"), r.get("peak_lift_m")
            if (mo is not None and pl is not None
                    and mo < HOLD_CLOSED and pl >= HOLD_LIFT):
                t_hold = idx
        if t_task_done is None and (
                r.get("libero_terminated") is True
                or s.get("libero_terminated") is True):
            t_task_done = idx
            break
    recovered = t_task_done is not None
    t_end = t_task_done if recovered else (cont[-1]["step_idx"] if cont else t0)
    window = [s for s in cont if (s.get("step_idx") or 0) <= (t_end or t0)]

    # --- 窗口内行为 ------------------------------------------------------
    fail_prompt = fail_cmd.get("prompt") or ""
    fail_action = fail_cmd.get("action") or ""
    prompts, actions, families = [], [], []
    for s in window:
        c = s.get("command") or {}
        a = c.get("action")
        if not a:
            continue
        actions.append(a)
        families.append(FAMILY.get(a, "other"))
        if a in ("pi0_pick", "pi0_doubled"):
            prompts.append(c.get("prompt") or "")

    # transcript 窗口:发出 step t0+1 的 turn 到发出 t_end 的 turn
    # (action 事件与 states 命令 1:1 → 用序号切)
    act_events = [e for e in events if e["kind"] == "action"]
    # 找 t0 之后第一个动作事件在 act_events 中的下标
    start_j = None
    # 重放前缀命令数 = t0(第 1..t0 个动作事件);窗口 = 第 t0+1 个起
    n_prefix = sum(1 for s in steps
                   if (s.get("step_idx") or 0) <= t0 and s.get("command"))
    # 1:1 校验失败时保守置 None(计数记 -1)
    ok_map = len(act_events) == sum(1 for s in steps if s.get("command"))
    obs_count = gr_count = -1
    turns_to_rec = -1
    if ok_map:
        j0 = n_prefix  # 0-based:第 n_prefix+1 个动作事件
        n_win = len([s for s in window if s.get("command")])
        win_events = [e for e in events if e["kind"] == "obs" or True]
        # 重新按事件流切:从第 j0 个 action 事件开始到第 j0+n_win-1 个
        jend = j0 + max(n_win - 1, 0)
        # 用全局事件序(含 obs)定位窗口边界 turn
        seq_actions = 0
        turn_start = turn_end = None
        for e in events:
            if e["kind"] == "action":
                seq_actions += 1
                if seq_actions == j0 + 1:
                    turn_start = e["turn"]
                if seq_actions == jend + 1:
                    turn_end = e["turn"]
                    break
        if turn_start is not None:
            turn_end = turn_end if turn_end is not None else (
                events[-1]["turn"] if events else turn_start)
            in_win = [e for e in events
                      if turn_start <= e["turn"] <= turn_end]
            obs_count = sum(1 for e in in_win if e["kind"] == "obs")
            gr_count = sum(1 for e in in_win
                           if e["tool"] in GROUNDING_TOOLS)
            turns_to_rec = len({e["turn"] for e in in_win})

    # 行为标记(全部确定性)
    changed_subgoal = any(p != fail_prompt for p in prompts)
    resampled = fail_action in ("pi0_pick", "pi0_doubled") and any(
        a == fail_action for a in actions)
    called_diff_skill = any(
        a not in (fail_action,) for a in actions
        if FAMILY.get(a, "other") not in ("gripper",))
    # retreat/realign:窗口首个非 gripper 动作是 realign,或 move_to 抬升
    eef0 = fail_state.get("robot0_eef_pos") or [None, None, None]
    retreat = False
    for s in window:
        c = s.get("command") or {}
        if FAMILY.get(c.get("action") or "", "other") == "realign":
            retreat = True
            break
        if c.get("action") == "move_to":
            xyz = c.get("xyz") or []
            if len(xyz) == 3 and eef0[2] is not None and (
                    float(xyz[2]) > float(eef0[2]) + 0.05):
                retreat = True
            break
    multistep = len(actions) >= 3 and len(set(families)) >= 2
    # observation-conditioned replan:窗口内先有观察、后发生
    # prompt 变化或技能族切换
    dyn = False
    if ok_map and obs_count > 0 and (changed_subgoal or len(set(families)) > 1):
        dyn = True
    returned_nominal = recovered and not changed_subgoal and not resampled
    # changed_target_reference:prompt 中出现不同的目标物措辞(词面级)
    def _objs(p: str) -> set[str]:
        stop = {"pick", "up", "the", "on", "and", "place", "put", "in",
                "to", "a", "an", "bowl", "plate", "stove"}
        return {w for w in p.lower().split() if w not in stop and len(w) > 2}
    changed_ref = bool(prompts and fail_prompt and any(
        _objs(p) - _objs(fail_prompt) for p in prompts))
    # changed_target_pose:连续 move_to 的 xy 变化指向重新定位(非 retreat)
    changed_pose = False
    mt = [s for s in window
          if (s.get("command") or {}).get("action") == "move_to"]
    if len(mt) >= 1 and fail_action == "pi0_pick":
        # 失败 pick 后重新给出与失败 eef 不同的 approach 目标
        for s in mt:
            xyz = (s.get("command") or {}).get("xyz") or []
            if len(xyz) == 3 and eef0[0] is not None:
                if abs(float(xyz[0]) - float(eef0[0])) > 0.015 or abs(
                        float(xyz[1]) - float(eef0[1])) > 0.015:
                    changed_pose = True
                break

    labels = []
    n_same_retry = sum(1 for p in prompts if p == fail_prompt)
    if n_same_retry >= 1 and (t_hold is not None or recovered):
        labels.append("SAMPLING_LIKE")
    if changed_subgoal or changed_ref:
        labels.append("CONDITIONING_CHANGE")
    if multistep:
        labels.append("SEQUENCE_COMPOSITION")
    if dyn:
        labels.append("DYNAMIC_REPLANNING")
    if retreat:
        labels.append("RESET_REALIGNMENT")
    if not labels:
        labels.append("UNRESOLVED")

    # --- 确定性亚型(arm 构造用画像)------------------------------------
    # 持有推断用物理恒真规则:任务经放置/释放路径完成且窗口内零重抓
    # ⇒ t0 时必然已持有(放下的是某个东西)。
    # t0 pick 自身的 min_gripper_opening<0.03 只是"爪闭合",无法区分
    # 闭空与持物(snap_00 闭空后重抓才成功),只作 raw 字段保留。
    held_raw = (fail_res.get("min_gripper_opening") is not None
                and fail_res["min_gripper_opening"] < HOLD_CLOSED)
    repick = "pi0_pick" in actions
    doubled = "pi0_doubled" in actions
    place_path = any(a in ("release", "pi0_doubled", "move_pose")
                     for a in actions)
    inferred_held = (m["family"] == "FALSE_GRASP" and recovered
                     and place_path and not repick)
    if m["family"] == "FALSE_GRASP":
        if inferred_held:
            subtype = "FG_HELD_AND_PLACE(失败即持有→直接放置/释放)"
        elif repick:
            subtype = "FG_RESAMPLE_REPICK(重新定位+重抓)"
        else:
            subtype = "FG_OTHER"
    else:
        if repick:
            subtype = "RPS_REPICK(重抓重放)"
        elif doubled:
            subtype = "RPS_PROCEED_DOUBLED(直接换位技能)"
        elif recovered and len(actions) <= 1:
            subtype = "RPS_SINGLE_STEP(单步即成)"
        else:
            subtype = "RPS_OTHER"

    return {
        "case_id": m["snapshot_id"], "task": m["task"], "seed": m["seed"],
        "failure_family": m["family"], "procedure": m["procedure"],
        "t0": t0, "episode_total_steps": len(steps),
        "source_recovered": recovered,
        "fail_eef_pos": json.dumps([round(float(x), 3) for x in eef0]
                                   if eef0[0] is not None else None),
        "fail_gripper_qpos": json.dumps(
            [round(float(x), 4) for x in fail_state.get(
                "robot0_gripper_qpos", [])] or None),
        "fail_pick_target_xyz": json.dumps(fail_res.get("target_xyz")),
        "fail_pick_min_opening": fail_res.get("min_gripper_opening"),
        "fail_pick_peak_lift": fail_res.get("peak_lift_m"),
        "t_hold": t_hold, "t_task_done": t_task_done,
        "t_recovery_window_end": t_end,
        "changed_target_reference": changed_ref,
        "changed_target_pose": changed_pose,
        "changed_subgoal": changed_subgoal,
        "resampled_same_skill": resampled,
        "called_different_skill": called_diff_skill,
        "used_multistep_sequence": multistep,
        "observation_conditioned_replan": dyn,
        "retreat_realign": retreat,
        "returned_nominal": returned_nominal,
        "used_pi0_doubled": "pi0_doubled" in actions,
        "used_move_pose": "move_pose" in actions,
        "primitive_count_to_recovery": len([a for a in actions]),
        "planner_turns_to_recovery": turns_to_rec,
        "observation_count": obs_count,
        "grounding_update_count": gr_count,
        "subgoal_change_count": sum(1 for i, p in enumerate(prompts)
                                    if p != fail_prompt),
        "skill_family_change_count": sum(
            1 for i in range(1, len(families))
            if families[i] != families[i - 1]),
        "mechanism_labels": "|".join(labels),
        "subtype": subtype,
        "held_raw_flag": held_raw,
        "inferred_held_at_failure": inferred_held,
        "recovery_action_sequence": " ".join(
            f"{FAMILY.get(a, a)}" for a in actions) or "(none)",
    }


def main() -> int:
    mani = read_manifest()
    rows = [audit_case(m) for m in mani]

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    # ---- 汇总 -----------------------------------------------------------
    rec = [r for r in rows if r["source_recovered"]]
    labels = Counter()
    for r in rec:
        for l in r["mechanism_labels"].split("|"):
            labels[l] += 1
    fam_first = defaultdict(Counter)
    for r in rec:
        # 每族的主导叙事:用标签组合的简化画像
        fam_first[r["failure_family"]][
            "used_pi0_doubled" if r["used_pi0_doubled"] else
            ("resampled" if r["resampled_same_skill"] else "other")
        ] += 1

    out = io.StringIO()
    w = out.write
    w("# Stage O O-A — 离线恢复来源审计(§4-§6,descriptive)\n\n")
    w(f"- 对象:Stage N 24 个 failure snapshots 的源 episode(Full Planner)\n")
    w(f"- 源 episode 最终恢复:{len(rec)}/24;"
      f"未恢复 1 例({[r['case_id'] for r in rows if not r['source_recovered']]})\n")
    w(f"- 全部字段为确定性规则计算(零 LLM);机制标签多标签,descriptive\n\n")

    w("## 1. 逐 case 表(恢复窗口内 Full Planner 行为)\n\n")
    w("| case | family | t0→done | prims | turns | obs | ground | "
      "subgoalΔ | famΔ | doubled | move_pose | resample | retreat | labels |\n")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        span = (f"{r['t0']}→{r['t_task_done']}"
                if r["source_recovered"] else f"{r['t0']}→(未恢复)")
        w(f"| {r['case_id']} | {r['failure_family'][:12]} | {span} "
          f"| {r['primitive_count_to_recovery']} "
          f"| {r['planner_turns_to_recovery']} "
          f"| {r['observation_count']} | {r['grounding_update_count']} "
          f"| {r['subgoal_change_count']} | {r['skill_family_change_count']} "
          f"| {'✓' if r['used_pi0_doubled'] else '·'} "
          f"| {'✓' if r['used_move_pose'] else '·'} "
          f"| {'✓' if r['resampled_same_skill'] else '·'} "
          f"| {'✓' if r['retreat_realign'] else '·'} "
          f"| {r['mechanism_labels']} |\n")

    w("\n## 2. 机制标签分布(仅 23 个恢复 case,多标签)\n\n")
    for k, v in labels.most_common():
        w(f"- {k}: {v}/23\n")

    w("\n## 3. 确定性亚型分布(arm 构造输入)\n\n")
    subs = Counter((r["failure_family"], r["subtype"]) for r in rows)
    for (fam, sub), v in sorted(subs.items()):
        w(f"- {fam} / {sub}:{v}\n")
    fg = [r for r in rows if r["failure_family"] == "FALSE_GRASP"]
    w(f"\n- FALSE_GRASP t0 爪闭合(min_o<{HOLD_CLOSED},raw,闭空/持物不可分):"
      f"{sum(1 for r in fg if r['held_raw_flag'])}/{len(fg)}\n")
    w(f"- FALSE_GRASP 持有推断(物理恒真:放置完成且零重抓):"
      f"{sum(1 for r in fg if r['inferred_held_at_failure'])}/{len(fg)}"
      f" ⇒ 这部分'失败'是验证器假阴性,非物理抓空\n")

    w("\n## 4. 关键 repertoire 观察\n\n")
    w(f"- 使用 pi0_doubled(Stage N local recovery 词汇表外):"
      f"{sum(1 for r in rec if r['used_pi0_doubled'])}/23\n")
    w(f"- 使用 move_pose:{sum(1 for r in rec if r['used_move_pose'])}/23\n")
    w(f"- resample 同一 skill 同一 prompt:"
      f"{sum(1 for r in rec if r['resampled_same_skill'])}/23\n")
    w(f"- 改变 subgoal/prompt:"
      f"{sum(1 for r in rec if r['changed_subgoal'])}/23\n")
    w(f"- 恢复窗口内含观察调用:"
      f"{sum(1 for r in rec if (r['observation_count'] or 0) > 0)}/23\n")
    w(f"- 恢复前先 retreat/realign:"
      f"{sum(1 for r in rec if r['retreat_realign'])}/23\n")
    w("\n> O-A 只用于理解与 arm 构造;O-B confirmatory 证据独立采集(§3)。\n")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(out.getvalue())
    print(out.getvalue())
    print(f"已写入 {OUT_CSV} / {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
