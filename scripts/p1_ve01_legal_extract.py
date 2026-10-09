#!/usr/bin/env python3
"""VE-v0.1 合法观测提取器(只读,Phase 2/3 底座)。

从 P1-DEV0 已有 21 个 episode 的本地数据中提取**仅合法观测**(决策时可见)
构成逐 pick 对照表:
  - recipe_*.jsonl : pi0_pick 调用指令(步号由 run.log 回填)
  - run.log        : [tool<] pi0_pick 返回的 step + [think] 的 success/peak_lift
                     (工具旗标与 planner 叙述都是决策时可见的合法信息)
  - states.json    : 每 planner step 末端 robot0_gripper_qpos → gap=|q0-q1|
  - p1_dev0_events.jsonl : 触发/pre_legal/probe post_legal(仅 5 例有 probe)

明确不读:audit_only 真值(check_success/sim_measurement/物体坐标)不进本表。
审计真值仅在 Phase 3 评价列单独由事件文件附带,不作为任何臂的特征输入。

输出:artifacts/p1_dev0/ve01/legal_calibration.json + 控制台摘要。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

RUNS = "/workspace/yjx/rpent_data/p1_dev0/runs"
OUT_DEFAULT = "/workspace/yjx/rpent_data/p1_dev0/ve01/legal_calibration.json"

STEP_RE = re.compile(r'\[tool<\] pi0_pick:.*?"step":\s*(\d+)')
TOOL_OPEN_RE = re.compile(r"\[tool>\] pi0_pick\(")
SUCCESS_RE = re.compile(r"success:\s*(true|false|TRUE|FALSE)", re.I)
# t3 风格:"pi0_pick reports success: descent done..." / "reports failure"
REPORTS_OK_RE = re.compile(r"pi0_pick reports success", re.I)
REPORTS_BAD_RE = re.compile(r"pi0_pick reports (failure|fals)|reports success: false", re.I)
PEAK_RE = re.compile(r"peak_lift\s*([0-9]+\.?[0-9]*)")
# t3 叙述风格 "peak lift 0.073m"(带空格)
PEAK2_RE = re.compile(r"peak lift\s*([0-9]+\.?[0-9]*)")


def peak_of(line: str) -> float | None:
    m = PEAK_RE.search(line) or PEAK2_RE.search(line)
    return float(m.group(1)) if m else None


def gap_of(rec_state: dict) -> float | None:
    """由 robot0_gripper_qpos 计算 gap=|q0-q1|(与 p1_dev0_policy 口径一致)。"""
    q = rec_state.get("robot0_gripper_qpos")
    if isinstance(q, (list, tuple)) and len(q) == 2:
        try:
            return abs(float(q[0]) - float(q[1]))
        except (TypeError, ValueError):
            return None
    return None


def parse_episode_runlog(runlog_path: str) -> list[dict]:
    """解析 run.log,重建每次 pi0_pick 的 {step_idx, success, peak_lift}。"""
    picks: list[dict] = []
    pending_step: int | None = None
    with open(runlog_path, errors="replace") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if TOOL_OPEN_RE.search(ln):
            # 向后找 tool< 行拿 step 号
            j = i + 1
            step = None
            while j < len(lines) and j < i + 20:
                m = STEP_RE.search(lines[j])
                if m:
                    step = int(m.group(1))
                    break
                if TOOL_OPEN_RE.search(lines[j]):
                    break
                j += 1
            # 再向后找最近的 success think 行(属于本次返回的解读)
            k = j if step is not None else i + 1
            succ = None
            peak = None
            while k < len(lines) and k < (j if step is not None else i) + 8:
                lnk = lines[k]
                ms = SUCCESS_RE.search(lnk)
                if ms:
                    succ = ms.group(1).lower() == "true"
                elif REPORTS_BAD_RE.search(lnk):
                    succ = False
                elif REPORTS_OK_RE.search(lnk):
                    succ = True
                if succ is not None:
                    peak = peak_of(lnk)
                    if peak is None and k + 1 < len(lines):
                        # peak_lift 偶尔在下一行
                        peak = peak_of(lines[k + 1])
                    break
                k += 1
            if step is not None:
                picks.append(
                    {"step_idx": step, "success": succ, "peak_lift": peak}
                )
            i = k if k > i else i + 1
        else:
            i += 1
    return picks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    episodes = []
    for ev_path in sorted(glob.glob(f"{RUNS}/p1dev0_*/p1_dev0_events.jsonl")):
        key = os.path.basename(os.path.dirname(ev_path))
        events = [json.loads(l) for l in open(ev_path)]
        by_ev = {}
        for e in events:
            by_ev.setdefault(e.get("ev", "?"), e)
        init = by_ev.get("init", {})
        arm = init.get("arm")

        # episode 输出目录(带时间戳)
        ep_dirs = sorted(glob.glob(f"{RUNS}/{key}_*"))
        ep_dir = next((d for d in ep_dirs if os.path.isdir(d)), None)
        picks = []
        states_by_step = {}
        if ep_dir:
            rl = os.path.join(ep_dir, "run.log")
            if os.path.exists(rl):
                picks = parse_episode_runlog(rl)
            sp = os.path.join(ep_dir, "states.json")
            if os.path.exists(sp):
                for rec in json.load(open(sp)):
                    states_by_step[rec.get("step_idx")] = rec.get("state", {})

        for p in picks:
            st = states_by_step.get(p["step_idx"], {})
            p["end_gap"] = gap_of(st)
            p["end_eef_z"] = (
                st.get("robot0_eef_pos", [None, None, None])[2]
                if isinstance(st.get("robot0_eef_pos"), list)
                and len(st["robot0_eef_pos"]) == 3
                else None
            )

        # 触发/probe 合法观测(如有)
        trig = by_ev.get("trigger")
        probe = by_ev.get("probe")
        rec = {
            "episode_key": key,
            "arm": arm,
            "n_picks": len(picks),
            "picks": picks,
            "trigger": None,
            "probe": None,
        }
        if trig:
            rec["trigger"] = {
                "step_idx": trig.get("step_idx"),
                "env_steps": trig.get("env_steps"),
                "tool_success": trig.get("trigger"),
                "pre_legal": trig.get("pre_legal"),
            }
        if probe:
            rec["probe"] = {
                "env_steps_start": probe.get("env_steps_start"),
                "post_legal": probe.get("post_legal"),
            }
        episodes.append(rec)

    # ---- 摘要 ----
    all_picks = [(ep["episode_key"], p) for ep in episodes for p in ep["picks"]]
    with_flag = [(k, p) for k, p in all_picks if p["success"] is not None]
    ok_gaps = [p["end_gap"] for _, p in with_flag if p["success"] and p["end_gap"]]
    bad_gaps = [p["end_gap"] for _, p in with_flag if not p["success"] and p["end_gap"]]

    def stats(xs):
        if not xs:
            return None
        xs = sorted(xs)
        return {
            "n": len(xs),
            "min": round(xs[0], 4),
            "p25": round(xs[len(xs) // 4], 4),
            "med": round(xs[len(xs) // 2], 4),
            "p75": round(xs[3 * len(xs) // 4], 4),
            "max": round(xs[-1], 4),
        }

    summary = {
        "n_episodes": len(episodes),
        "n_picks_total": len(all_picks),
        "n_picks_with_flag": len(with_flag),
        "n_flag_true": sum(1 for _, p in with_flag if p["success"]),
        "n_flag_false": sum(1 for _, p in with_flag if not p["success"]),
        "end_gap_when_flag_true": stats(ok_gaps),
        "end_gap_when_flag_false": stats(bad_gaps),
    }
    out = {"summary": summary, "episodes": episodes}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nwrote {args.out}")

    # 逐 probe 合法 gap 打印(Phase 1/3 用)
    for ep in episodes:
        if ep["probe"]:
            pl = ep["probe"]["post_legal"] or {}
            pr = ep["trigger"]["pre_legal"] if ep["trigger"] else {}
            print(
                f"probe {ep['episode_key']}: pre_gap={pr.get('gripper_gap'):.5f} "
                f"post_gap={pl.get('gripper_gap'):.5f} "
                f"dz={pl.get('eef_z', 0) - pr.get('eef_z', 0):+.5f}"
            )


if __name__ == "__main__":
    main()
