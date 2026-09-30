#!/usr/bin/env python
"""Stage L §4 — L0 recovery-prefix 挖掘(离线,只读 DISCOVERY 侧)。

对 L_DISCOVERY_DEV 34 集的全部 fire(与 H/K 同一代码路径 replay_fires):
- 正例:fire 后不限窗找首个 validating action(H 冻结契约:pi0_pick
  success ∧ peak_lift ≥ 0.005,或集终止),prefix = fire+1 … 该步(含),
  label = recovery;prefix 记录完整 command dict(工具 + 参数),
  供 §5 候选编译直接使用;
- 负例:无 validating action,prefix = 后 ≤10 动作,label = no_recovery;
- 挖掘仅为选源;在线真值一律以 §7 双验证 + §9 执行为准(prereg §4)。

用法:python scripts/stageL_mine_prefixes.py
产物:analysis/stageL_recovery_prefixes.jsonl
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

MANIFEST = REPO / "analysis/stageL_split_manifest.csv"
OUT = REPO / "analysis/stageL_recovery_prefixes.jsonl"
NEG_CAP = 10  # 负例 prefix 上限(prereg §4)


def gripper_mean(q):
    """双指 qpos → 标量开度(executor measure 同义)。"""
    if not isinstance(q, (list, tuple)) or len(q) != 2:
        return None
    return float(sum(q) / 2)


def obs_state(step):
    """fire 时刻 runtime 可观测状态(EEF/夹爪;states.json 无物体位姿)。"""
    st = step.get("state") or {}
    return {
        "eef_pos": st.get("robot0_eef_pos"),
        "eef_quat": st.get("robot0_eef_quat"),
        "gripper_qpos": st.get("robot0_gripper_qpos"),
        "gripper_opening": gripper_mean(st.get("robot0_gripper_qpos")),
        "object_names": st.get("object_names"),
        "task_language": step.get("task_language"),
    }


def result_subset(r):
    """验证相关的 result 字段(可观测子集)。"""
    keys = ("success", "peak_lift_m", "final_gripper_opening",
            "min_gripper_opening", "chunks_used", "final_dist_m")
    return {k: r[k] for k in keys if k in r}


def last_pick_prompt(steps, i):
    """fire 前最近一次 pi0_pick 的 prompt(observable,FG-3 绑定同源)。"""
    for s in reversed(steps[:i + 1]):
        cmd = s.get("command") or {}
        if cmd.get("action") == "pi0_pick":
            return cmd.get("prompt")
    return None


def main() -> int:
    from analyze_stageH1 import NODE_FAMILY, fire_validated, replay_fires

    rows = list(csv.DictReader(open(MANIFEST)))
    disc = [r for r in rows if r["role"] == "L_DISCOVERY_DEV"]

    out = []
    for m in disc:
        ep = m["episode_dir"]
        steps = json.loads((Path(ep) / "states.json").read_text())
        fires = replay_fires(steps)
        for f in fires:
            i, node = f["step_idx"], f["node"]
            fam = NODE_FAMILY[node]
            # fire 后动作步(完整 step,保 command kwargs)
            post = [s for s in steps[i + 1:]
                    if (s.get("command") or {}).get("action")]
            first_val = None
            for j, s in enumerate(post):
                a = s["command"]["action"]
                if fire_validated(node, [(a, s.get("result") or {},
                                          bool(s.get("libero_terminated")))]):
                    first_val = j
                    break
            if first_val is not None:  # 正例 prefix
                pref = post[:first_val + 1]
                last = pref[-1]
                out.append({
                    "prefix_id": f"{Path(ep).name}#f{i}", "episode_dir": ep,
                    "task": int(m["task"]), "seed": int(m["seed"]),
                    "fire_step": i, "node": node, "family": fam,
                    "legal_edges": f["edges"],
                    "pre_state": obs_state(steps[i]),
                    "last_pick_prompt": last_pick_prompt(steps, i),
                    "failing_action": {
                        "action": (steps[i].get("command") or {}).get("action"),
                        "kwargs": {k: v for k, v in
                                   (steps[i].get("command") or {}).items()
                                   if k != "action"},
                        "result": result_subset(steps[i].get("result") or {})},
                    "action_sequence": [
                        {"step_idx": s["step_idx"],
                         "action": s["command"]["action"],
                         "kwargs": {k: v for k, v in s["command"].items()
                                    if k != "action"}}
                        for s in pref],
                    "terminal_state": {
                        **obs_state(last),
                        "result": result_subset(last.get("result") or {}),
                        "libero_terminated": bool(last.get("libero_terminated"))},
                    "verified_transition": {
                        "type": "term" if last.get("libero_terminated")
                        else "pick_lift",
                        "offset": first_val,
                        "action": last["command"]["action"]},
                    "label": "recovery", "prefix_len": len(pref),
                    "episode_sr": bool(steps[-1].get("libero_terminated")),
                })
            else:  # 负例 prefix(截断)
                pref = post[:NEG_CAP]
                last = pref[-1] if pref else steps[i]
                out.append({
                    "prefix_id": f"{Path(ep).name}#f{i}", "episode_dir": ep,
                    "task": int(m["task"]), "seed": int(m["seed"]),
                    "fire_step": i, "node": node, "family": fam,
                    "legal_edges": f["edges"],
                    "pre_state": obs_state(steps[i]),
                    "last_pick_prompt": last_pick_prompt(steps, i),
                    "failing_action": {
                        "action": (steps[i].get("command") or {}).get("action"),
                        "kwargs": {k: v for k, v in
                                   (steps[i].get("command") or {}).items()
                                   if k != "action"},
                        "result": result_subset(steps[i].get("result") or {})},
                    "action_sequence": [
                        {"step_idx": s["step_idx"],
                         "action": s["command"]["action"],
                         "kwargs": {k: v for k, v in s["command"].items()
                                    if k != "action"}}
                        for s in pref],
                    "terminal_state": {
                        **obs_state(last),
                        "result": result_subset(last.get("result") or {}),
                        "libero_terminated": bool(last.get("libero_terminated"))},
                    "verified_transition": None,
                    "label": "no_recovery",
                    "prefix_len": len(pref),
                    "episode_sr": bool(steps[-1].get("libero_terminated")),
                    "truncated_at_neg_cap": len(post) > NEG_CAP,
                })

    with open(OUT, "w") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    # ---- 摘要 ----------------------------------------------------------------
    import collections
    pos = [r for r in out if r["label"] == "recovery"]
    seq_pat = collections.Counter(
        tuple(a["action"] for a in r["action_sequence"]) for r in pos)
    print(json.dumps({
        "prefixes": len(out),
        "positives": len(pos),
        "by_family_label": {f"{fam}/{lab}": n for (fam, lab), n in
                            sorted(collections.Counter(
                                (r["family"], r["label"]) for r in out).items())},
        "pos_prefix_len": {
            "min": min((r["prefix_len"] for r in pos), default=0),
            "max": max((r["prefix_len"] for r in pos), default=0),
            "mean": round(sum(r["prefix_len"] for r in pos) / len(pos), 2)
            if pos else 0},
        "verified_transition_types": dict(collections.Counter(
            r["verified_transition"]["type"] for r in pos)),
        "pos_action_patterns_top": [
            {"pattern": " -> ".join(p), "n": n}
            for p, n in seq_pat.most_common(10)],
    }, ensure_ascii=False, indent=1))
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
