"""Turn-level failure analysis for LIBERO t0/t7/t9.

Parses run.log into per-turn tool-call sequences and computes:
- perception vs action call counts + ratio
- redundant perception (longest run of perception calls with no action between)
- retries (same action name used >1x)
- grounding signals (segment calls whose prompt mentions the target noun, found/score)
- outcome (success / policy-fail / infra)

Writes analysis/failure_analysis_t0_t7_t9.csv (one row per sampled run).
"""
import os, re, glob, json, sys, csv

LOGS = "/hw-tbo/yjx/workspace/RPent/logs"
PERCEPTION = {"segment", "read_image", "back_project", "view_driver_state", "view_camera_meta", "read_depth"}
ACTIONS = {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release", "set_gripper", "rotate_pitch", "rotate_yaw", "rotate_roll", "back_project_action"}

def parse_turns(run_dir):
    """Return list of turns; each turn is list of (tool, args_json_str)."""
    rl = os.path.join(run_dir, "run.log")
    if not os.path.exists(rl):
        return [], None
    turns, cur = [], None
    for line in open(rl, errors="ignore"):
        m = re.search(r"=== turn (\d+)/\d+ ===", line)
        if m:
            cur = int(m.group(1)); turns.append([])
            continue
        m2 = re.search(r"\[tool>\] (\w+)\((.*)\)$", line.strip())
        if m2 and cur is not None:
            turns[-1].append((m2.group(1), m2.group(2)))
    # outcome
    txt = open(rl, errors="ignore").read()
    if "FINISH called" in txt and '"status": "success"' in txt: outcome = "success"
    elif "FINISH called" in txt: outcome = "finish_no_success"
    elif "reached max_turns" in txt: outcome = "max_turns"
    elif "API planner timed out" in txt: outcome = "infra_timeout"
    else: outcome = "unknown"
    return turns, outcome

def target_nouns(task_language):
    # crude: nouns that appear in both task_language and segment prompts matter most;
    # we just return a few common target words by heuristic.
    low = (task_language or "").lower()
    words = ["bowl","plate","bottle","rack","mug","stove","pan","drawer","cabinet",
             "cookie","ramekin","basket","sauce","ketchup","milk","bowl ","cup","can"]
    return [w for w in words if w in low]

def analyze(run_dir, task_language):
    turns, outcome = parse_turns(run_dir)
    flat = [t for turn in turns for t in turn]
    names = [t[0] for t in flat]
    n_perc = sum(1 for n in names if n in PERCEPTION)
    n_act = sum(1 for n in names if n in ACTIONS)
    n_other = len(names) - n_perc - n_act
    # redundant: longest consecutive perception run (no action in between)
    max_redundant = cur_red = 0
    for n in names:
        if n in PERCEPTION:
            cur_red += 1; max_redundant = max(max_redundant, cur_red)
        else:
            cur_red = 0
    # retries: action names used >1
    from collections import Counter
    ac = Counter(n for n in names if n in ACTIONS)
    retried = {k: v for k, v in ac.items() if v > 1}
    # grounding: segment calls mentioning target noun
    nouns = target_nouns(task_language)
    seg_calls = [(i, t[1]) for i, t in enumerate(flat) if t[0] == "segment"]
    ground_hits = 0
    for i, args in seg_calls:
        if any(n in (args or "").lower() for n in nouns):
            ground_hits += 1
    # first action turn
    first_act_turn = next((ti for ti, turn in enumerate(turns) if any(t[0] in ACTIONS for t in turn)), None)
    n_turns = len(turns)
    return dict(
        run=os.path.basename(run_dir.rstrip("/")),
        n_turns=n_turns, n_calls=len(names),
        perc=n_perc, act=n_act, other=n_other,
        perc_ratio=round(n_perc/max(len(names),1), 2),
        max_redundant_perc=max_redundant,
        retried=";".join(f"{k}x{v}" for k, v in retried.items()) or "-",
        ground_seg_hits=ground_hits,
        first_action_turn=first_act_turn,
        outcome=outcome,
    )

def pick_samples(task, k_ok, k_fail):
    """Pick diverse (suite,task,seed) samples across suites."""
    seen = {}
    for suite in ["goal_swap","spatial_task","goal_task","spatial"]:
        for d in glob.glob(f"{LOGS}/*_libero_{suite}_t{task}_s*/"):
            b = os.path.basename(d.rstrip("/"))
            m = re.match(r".*_libero_"+suite+r"_t(\d+)_s(\d+)$", b)
            if not m: continue
            sd = int(m.group(2))
            sf = os.path.join(d, "states.json")
            term = None
            if os.path.exists(sf):
                try:
                    st = json.load(open(sf))
                    if isinstance(st, list) and st: term = st[-1].get("libero_terminated")
                except: pass
            if term is None: continue
            key = (suite, sd)
            if key in seen:  # keep latest
                pass
            seen[key] = (d, term, b)
    # build per-outcome lists, keep distinct suites
    oks = [v for v in seen.values() if v[1] is True][:k_ok]
    fails = [v for v in seen.values() if v[1] is False][:k_fail]
    return oks, fails

def task_language_of(run_dir):
    sf = os.path.join(run_dir, "states.json")
    try:
        st = json.load(open(sf))
        if st: return st[0].get("task_language", "")
    except: pass
    return ""

def main():
    out = []
    for task, k_ok, k_fail in [(7, 5, 5), (0, 5, 5), (9, 5, 5)]:
        oks, fails = pick_samples(task, k_ok, k_fail)
        for d, term, b in oks + fails:
            tl = task_language_of(d)
            r = analyze(d, tl)
            r["task"] = task
            r["label"] = "success" if term else "fail"
            out.append(r)
    # write CSV
    path = "/hw-tbo/yjx/workspace/RPent/analysis/failure_analysis_t0_t7_t9.csv"
    cols = ["task","label","run","outcome","n_turns","n_calls","perc","act","other",
            "perc_ratio","max_redundant_perc","retried","ground_seg_hits","first_action_turn"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c) for c in cols})
    print(f"wrote {len(out)} rows -> {path}")
    # quick summary
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(list))
    for r in out:
        agg[(r["task"], r["label"])]["ratio"].append(r["perc_ratio"])
        agg[(r["task"], r["label"])]["red"].append(r["max_redundant_perc"])
        agg[(r["task"], r["label"])]["act"].append(r["act"])
    for k in sorted(agg):
        v = agg[k]
        avg = lambda x: round(sum(x)/len(x), 2)
        print(f"t{k[0]} {k[1]}: perc_ratio={avg(v['ratio'])}, max_redundant={avg(v['red'])}, act_calls={avg(v['act'])}")

if __name__ == "__main__":
    main()
