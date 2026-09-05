"""Paired-suite comparison: spatial_task vs spatial_swap, goal_task vs goal_swap.

For every (task, seed) pair, takes the LATEST run in each suite and extracts:
- success (libero_terminated on last states.json entry)
- turns, tool calls, perception/action counts, max redundant perception run,
  first-action turn, env steps
- a primary failure reason (perception_loop / grasp_fail / placement_fail /
  reach_plan_fail / max_turns / infra_timeout / infra_crash)

Aggregates per suite AND per paired (task,seed) row so "same task/seed, which
perturbation is harder" can be read directly.

Usage: python analysis/compare_suites.py [--out analysis/suite_comparison.csv]
"""
import os, re, glob, json, sys, csv
from collections import Counter, defaultdict

LOGS = "/vla_test/yjx/workspace/RPent/logs"
PERCEPTION = {"segment", "read_image", "back_project", "view_driver_state",
              "view_camera_meta", "read_depth"}
ACTIONS = {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
           "set_gripper", "rotate_wrist", "rotate_pitch", "rotate_roll",
           "back_project_action"}
PRIMITIVES = {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
              "set_gripper", "rotate_wrist", "rotate_pitch"}


def parse_turns(run_dir):
    """Return (turns, tool_calls) where tool_calls is [(tool, args), ...]."""
    rl = os.path.join(run_dir, "run.log")
    if not os.path.exists(rl):
        return [], []
    calls = []
    for line in open(rl, errors="ignore"):
        m = re.search(r"\[tool>\] (\w+)\((.*)\)$", line.strip())
        if m:
            calls.append((m.group(1), m.group(2)))
    # turns = count of "=== turn N/ ===" markers
    n_turns = 0
    for line in open(rl, errors="ignore"):
        if re.search(r"=== turn (\d+)/\d+ ===", line):
            n_turns += 1
    return n_turns, calls


def load_states(run_dir):
    sf = os.path.join(run_dir, "states.json")
    if not os.path.exists(sf):
        return None, None, None
    try:
        st = json.load(open(sf))
    except Exception:
        return None, None, None
    if not isinstance(st, list) or not st:
        return None, None, None
    last = st[-1]
    return st, last, last.get("libero_terminated")


def command_seq(states):
    """List of (action, result) from states.json command logs."""
    seq = []
    for entry in states:
        c = entry.get("command")
        if not c or not isinstance(c, dict):
            continue
        seq.append((c.get("action"), entry.get("result")))
    return seq


def classify_failure(states, n_turns, calls, terminated):
    rl_txt = ""
    # we pass run_dir via closure-less design; recompute markers below
    if terminated:
        return "success"
    # infra / budget signals come from run.log markers — read here
    return None  # filled by caller


def analyze(run_dir):
    n_turns, calls = parse_turns(run_dir)
    names = [t for t, _ in calls]
    states, last, terminated = load_states(run_dir)
    rl = os.path.join(run_dir, "run.log")
    rl_txt = open(rl, errors="ignore").read() if os.path.exists(rl) else ""

    n_perc = sum(1 for n in names if n in PERCEPTION)
    n_act = sum(1 for n in names if n in ACTIONS)
    max_redundant = cur = 0
    for n in names:
        cur = cur + 1 if n in PERCEPTION else 0
        max_redundant = max(max_redundant, cur)
    first_act_turn = None
    # first_action_turn approximated by position of first action in calls
    for i, n in enumerate(names):
        if n in ACTIONS:
            first_act_turn = i + 1
            break
    n_env_steps = max((len(states) - 1) if states else 0, 0)

    seq = command_seq(states) if states else []

    # ---------- failure reason ----------
    reason = "success" if terminated else "unknown"
    if not terminated:
        if "API planner timed out" in rl_txt:
            reason = "infra_timeout"
        elif not states:
            reason = "infra_crash"
        elif "reached max_turns" in rl_txt or (n_turns >= 40):
            # reached budget — attribute to the furthest stage reached
            acts = [a for a, _ in seq]
            if not acts:
                reason = "perception_loop"
            elif "release" in acts or "pi0_doubled" in acts:
                reason = "placement_fail"
            elif any(a == "pi0_pick" for a in acts):
                # was pick attempted+failed, or pick loop without release
                pick_res = [r for a, r in seq if a == "pi0_pick"]
                failed_pick = any(isinstance(r, dict) and r.get("success") is False
                                  for r in pick_res)
                reason = "grasp_fail" if failed_pick else "placement_fail"
            elif "move_to" in acts or "move_pose" in acts:
                reason = "reach_plan_fail"
            else:
                reason = "perception_loop"
        elif n_turns == 0 and not names:
            reason = "infra_crash"
        else:
            # ended without explicit max_turns/timeout marker
            acts = [a for a, _ in seq]
            if not acts:
                reason = "perception_loop"
            else:
                reason = "early_stop"

    return dict(
        run=os.path.basename(run_dir.rstrip("/")),
        n_turns=n_turns,
        n_calls=len(calls),
        perc=n_perc,
        act=n_act,
        perc_ratio=round(n_perc / max(len(calls), 1), 2),
        max_redundant_perc=max_redundant,
        first_action_call=first_act_turn,
        n_env_steps=n_env_steps,
        success=bool(terminated),
        reason=reason,
    )


def latest_map(suite, task):
    """Return {(task,seed): (dir, term)} for the newest run of each seed."""
    m = {}
    for d in glob.glob(f"{LOGS}/*_libero_{suite}_t{task}_s*/"):
        b = os.path.basename(d.rstrip("/"))
        mm = re.match(r".*_libero_" + suite + r"_t(\d+)_s(\d+)$", b)
        if not mm:
            continue
        sd = int(mm.group(2))
        if (task, sd) not in m or d > m[(task, sd)][0]:
            m[(task, sd)] = (d, None)
    # attach term
    for k in m:
        d, _ = m[k]
        _, last, term = load_states(d)
        m[k] = (d, bool(term))
    return m


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "analysis/suite_comparison.csv"
    pairs = [("spatial_task", "spatial_swap"), ("goal_task", "goal_swap")]
    rows = []
    for sa, sb in pairs:
        # paired rows on common (task,seed)
        for t in range(10):
            ma, mb = latest_map(sa, t), latest_map(sb, t)
            common = set(ma) & set(mb)
            for (task, sd) in sorted(common):
                da, _ = ma[(task, sd)]
                db, _ = mb[(task, sd)]
                ra, rb = analyze(da), analyze(db)
                rows.append({
                    "pair": f"{sa} vs {sb}", "suite_a": sa, "suite_b": sb,
                    "task": t, "seed": sd,
                    "a_success": ra["success"], "b_success": rb["success"],
                    "a_turns": ra["n_turns"], "b_turns": rb["n_turns"],
                    "a_perc": ra["perc"], "b_perc": rb["perc"],
                    "a_act": ra["act"], "b_act": rb["act"],
                    "a_red": ra["max_redundant_perc"], "b_red": rb["max_redundant_perc"],
                    "a_steps": ra["n_env_steps"], "b_steps": rb["n_env_steps"],
                    "a_reason": ra["reason"], "b_reason": rb["reason"],
                    "a_ratio": ra["perc_ratio"], "b_ratio": rb["perc_ratio"],
                })
    cols = ["pair", "suite_a", "suite_b", "task", "seed",
            "a_success", "b_success", "a_turns", "b_turns", "a_perc", "b_perc",
            "a_act", "b_act", "a_red", "b_red", "a_steps", "b_steps",
            "a_ratio", "b_ratio", "a_reason", "b_reason"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # -------- aggregate report --------
    print(f"wrote {len(rows)} paired rows -> {out}\n")
    for sa, sb in pairs:
        sub = [r for r in rows if r["pair"] == f"{sa} vs {sb}"]
        n = len(sub)
        if not n:
            continue
        a_ok = sum(r["a_success"] for r in sub)
        b_ok = sum(r["b_success"] for r in sub)
        both = sum(r["a_success"] and r["b_success"] for r in sub)
        a_only = sum(r["a_success"] and not r["b_success"] for r in sub)
        b_only = sum(r["b_success"] and not r["a_success"] for r in sub)
        print(f"===== {sa} vs {sb}  ({n} common task/seed) =====")
        print(f"  success: {sa}={a_ok}/{n} ({a_ok/n:.0%})   {sb}={b_ok}/{n} ({b_ok/n:.0%})")
        print(f"  both={both}  {sa}-only={a_only}  {sb}-only={b_only}")
        def avg(key, f):
            vals = [f(r) for r in sub if f(r) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None
        for side, sfx in ((sa, "a"), (sb, "b")):
            print(f"    {side}: mean turns={avg(f'{sfx}_turns', lambda r: r[f'{sfx}_turns'])}"
                  f" perc={avg(f'{sfx}_perc', lambda r: r[f'{sfx}_perc'])}"
                  f" act={avg(f'{sfx}_act', lambda r: r[f'{sfx}_act'])}"
                  f" maxred={avg(f'{sfx}_red', lambda r: r[f'{sfx}_red'])}"
                  f" steps={avg(f'{sfx}_steps', lambda r: r[f'{sfx}_steps'])}")
        for side, sfx in ((sa, "a"), (sb, "b")):
            rc = Counter(r[f"{sfx}_reason"] for r in sub)
            tot = sum(rc.values())
            dist = ", ".join(f"{k}:{v/tot:.0%}" for k, v in rc.most_common())
            print(f"    {side} reasons: {dist}")
        print()


if __name__ == "__main__":
    main()
