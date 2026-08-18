"""Progress Gate experiment: metrics extraction, aggregates, stage gates.

Reads analysis/progress_gate_runs.csv (one row per completed episode; columns:
ts, stage, suite, task, seed, cond, repeat, dir, wall_s, result) and computes
per-condition metrics by re-parsing each run dir:
  success, turns, planner_calls (API requests), tokens (in+out+cache),
  perception calls, max redundant perception run, action calls, env steps,
  failure reason.

Writes:
  analysis/progress_gate_summary.md   — condition aggregates + stage gates
  analysis/progress_gate_ablation.csv — P1 (baseline vs hardcap vs ours) rows

CLI: python progress_gate_analysis.py            # write summary from runs.csv
     python progress_gate_analysis.py --gates    # print gate decisions (json)
"""
import csv, os, re, glob, json, sys, datetime, statistics, collections

ROOT = "/hw-tbo/yjx/workspace/RPent"
LOGS = os.path.join(ROOT, "logs")
RUNS_CSV = os.path.join(ROOT, "analysis", "progress_gate_runs.csv")
SUMMARY_MD = os.path.join(ROOT, "analysis", "progress_gate_summary.md")
ABLATION_CSV = os.path.join(ROOT, "analysis", "progress_gate_ablation.csv")

PERCEPTION = {"segment", "read_image", "back_project", "view_driver_state",
              "view_camera_meta", "read_depth"}
ACTIONS = {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
           "set_gripper", "rotate_wrist", "rotate_pitch", "rotate_roll",
           "back_project_action"}

_USAGE_RE = re.compile(r"\[usage\] in=([0-9]+) out=([0-9]+) cache_read=([0-9]+) cache_write=([0-9]+) requests=([0-9]+)")
_TURN_RE = re.compile(r"=== turn (\d+)/\d+ ===")
_TOOL_RE = re.compile(r"\[tool>\] (\w+)\(")


def _states(d):
    p = os.path.join(d, "states.json")
    if not os.path.exists(p):
        return None, None
    try:
        st = json.load(open(p))
    except Exception:
        return None, None
    if not isinstance(st, list) or not st:
        return None, None
    return st, st[-1].get("libero_terminated")


def analyze_dir(d):
    """Return metric dict for one run dir (or None if unusable)."""
    rl = os.path.join(d, "run.log")
    n_turns = 0
    calls = []
    usage_last = None
    first_ts = last_ts = None
    if os.path.exists(rl):
        for line in open(rl, errors="ignore"):
            m = _TURN_RE.search(line)
            if m:
                n_turns += 1
            m2 = _TOOL_RE.search(line)
            if m2:
                calls.append(m2.group(1))
            mu = _USAGE_RE.search(line)
            if mu:
                usage_last = tuple(int(x) for x in mu.groups())
            mts = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", line)
            if mts:
                if first_ts is None:
                    first_ts = mts.group(1)
                last_ts = mts.group(1)
    st, term = _states(d)
    if st is None:
        return None
    names = calls
    n_perc = sum(1 for n in names if n in PERCEPTION)
    n_act = sum(1 for n in names if n in ACTIONS)
    maxred = cur = 0
    for n in names:
        cur = cur + 1 if n in PERCEPTION else 0
        maxred = max(maxred, cur)
    first_act = next((i + 1 for i, n in enumerate(names) if n in ACTIONS), None)
    reason = classify_reason(d, st, term, n_turns, rl)
    wall = None
    if first_ts and last_ts:
        try:
            f = datetime.datetime.strptime(first_ts, "%Y-%m-%d %H:%M:%S")
            l = datetime.datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
            wall = (l - f).total_seconds()
        except Exception:
            pass
    return dict(
        success=bool(term),
        turns=n_turns,
        planner_calls=usage_last[4] if usage_last else None,
        tokens=(usage_last[0] + usage_last[1] + usage_last[2] + usage_last[3]) if usage_last else None,
        perc=n_perc, act=n_act,
        maxred=maxred, first_act=first_act,
        env_steps=max(len(st) - 1, 0),
        reason=reason, wall_s=wall,
    )


def classify_reason(d, st, term, n_turns, rl):
    txt = open(rl, errors="ignore").read() if os.path.exists(rl) else ""
    if term:
        return "success"
    if "API planner timed out" in txt:
        return "infra_timeout"
    if not st:
        return "infra_crash"
    seq = [(e.get("command", {}).get("action")) for e in st if e.get("command")]
    acts = [a for a in seq if a]
    if "reached max_turns" in txt or n_turns >= 40:
        if not acts:
            return "perception_loop"
        if "release" in acts or "pi0_doubled" in acts:
            return "placement_fail"
        if "pi0_pick" in acts:
            return "grasp_fail"
        if "move_to" in acts or "move_pose" in acts:
            return "reach_plan_fail"
        return "perception_loop"
    if not acts:
        return "perception_loop" if names_present(st) else "infra_crash"
    return "early_stop"


def names_present(st):
    return any(e.get("command") for e in st)


def load_runs():
    if not os.path.exists(RUNS_CSV):
        return []
    rows = list(csv.DictReader(open(RUNS_CSV)))
    for r in rows:
        m = analyze_dir(r["dir"]) if os.path.isdir(r["dir"]) else None
        r["m"] = m
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def gates(rows):
    """Decide P1 (hardcap) and P2 (generalize) from P0 baseline-vs-ours."""
    p0 = [r for r in rows if r["stage"] == "P0" and r["m"]]
    bl = [r for r in p0 if r["cond"] == "baseline"]
    og = [r for r in p0 if r["cond"] == "ours"]
    if not bl or not og:
        return None
    sbl = sum(r["m"]["success"] for r in bl) / len(bl)
    sog = sum(r["m"]["success"] for r in og) / len(og)
    turns_bl = mean([r["m"]["turns"] for r in bl])
    turns_og = mean([r["m"]["turns"] for r in og])
    red_bl = mean([r["m"]["maxred"] for r in bl])
    red_og = mean([r["m"]["maxred"] for r in og])
    tok_bl = mean([r["m"]["tokens"] for r in bl])
    tok_og = mean([r["m"]["tokens"] for r in og])
    p1 = sog >= sbl - 0.10  # no obvious negative effect
    eff_gain = (turns_og is not None and turns_bl is not None and turns_og < turns_bl * 0.85) or \
               (red_og is not None and red_bl is not None and red_og < red_bl * 0.85) or \
               (tok_og is not None and tok_bl is not None and tok_og < tok_bl * 0.85)
    p2 = (sog >= sbl) or (sog >= sbl - 0.05 and eff_gain)
    return dict(
        n_bl=len(bl), n_og=len(og),
        sr_bl=round(sbl, 3), sr_og=round(sog, 3),
        turns_bl=turns_bl, turns_og=turns_og,
        red_bl=red_bl, red_og=red_og,
        tok_bl=tok_bl, tok_og=tok_og,
        p1=p1, p2=p2,
    )


def write_summary(rows, gate=None):
    lines = ["# Progress Gate 实验结果\n"]
    lines.append(f"_updated {datetime.datetime.now().isoformat(timespec='seconds')}_\n")
    lines.append(f"completed episodes: {len(rows)}\n")
    by_stage = collections.defaultdict(list)
    for r in rows:
        by_stage[r["stage"]].append(r)
    for stage in ("P0", "P1", "P2"):
        sr = by_stage[stage]
        if not sr:
            continue
        lines.append(f"## {stage}\n")
        lines.append(f"| cond | n | SR | turns | planner | tokens | perc | act | maxred |\n")
        lines.append("|---|---|---|---|---|---|---|---|---|\n")
        for cond in ("baseline", "ours", "hardcap"):
            rr = [r for r in sr if r["cond"] == cond]
            if not rr:
                continue
            m = [r["m"] for r in rr if r["m"]]
            sr_c = sum(x["success"] for x in m) / len(m) if m else 0
            lines.append(
                f"| {cond} | {len(m)} | {sr_c:.0%} | {mean([x['turns'] for x in m])} | "
                f"{mean([x['planner_calls'] for x in m])} | {mean([x['tokens'] for x in m])} | "
                f"{mean([x['perc'] for x in m])} | {mean([x['act'] for x in m])} | "
                f"{mean([x['maxred'] for x in m])} |\n"
            )
        # failure taxonomy
        for cond in ("baseline", "ours", "hardcap"):
            rr = [r["m"] for r in sr if r["cond"] == cond and r["m"]]
            if not rr:
                continue
            rc = collections.Counter(x["reason"] for x in rr)
            lines.append(f"  {cond} reasons: " + ", ".join(
                f"{k}:{v/len(rr):.0%}" for k, v in rc.most_common()) + "\n")
        lines.append("\n")
    if gate:
        lines.append("## Stage gates\n")
        lines.append(f"- P1 (proceed to hardcap ablation): **{gate['p1']}**"
                     f"  (SR ours {gate['sr_og']:.0%} vs baseline {gate['sr_bl']:.0%}, "
                     f"rule: ours >= baseline - 10pp)\n")
        lines.append(f"- P2 (generalize to 4 suites): **{gate['p2']}**"
                     f"  (turns {gate['turns_og']} vs {gate['turns_bl']}, "
                     f"red {gate['red_og']} vs {gate['red_bl']})\n")
    with open(SUMMARY_MD, "w") as f:
        f.write("\n".join(lines))
    return SUMMARY_MD


def write_ablation(rows):
    """P1: paired baseline vs hardcap vs ours on t0/t7/t9."""
    p1 = [r for r in rows if r["stage"] in ("P0", "P1") and r["m"]]
    cols = ["stage", "suite", "task", "seed", "cond", "repeat", "dir",
            "success", "turns", "planner_calls", "tokens", "perc", "act",
            "maxred", "env_steps", "reason", "wall_s"]
    with open(ABLATION_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in p1:
            m = r["m"]
            w.writerow({c: r.get(c) for c in cols if c not in ("success", "turns", "planner_calls", "tokens", "perc", "act", "maxred", "env_steps", "reason", "wall_s")} | {c: m.get(c) for c in ("success", "turns", "planner_calls", "tokens", "perc", "act", "maxred", "env_steps", "reason", "wall_s")})
    return ABLATION_CSV


def main():
    rows = load_runs()
    gate = gates(rows) if "--gates" not in sys.argv or True else None
    write_summary(rows, gate)
    write_ablation(rows)
    print(f"runs={len(rows)} -> {SUMMARY_MD}, {ABLATION_CSV}")
    if "--gates" in sys.argv:
        print(json.dumps(gate, ensure_ascii=False))


if __name__ == "__main__":
    main()
