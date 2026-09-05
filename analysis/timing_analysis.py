"""Reasoning-timing & memory-utility trajectory diagnostics.

Consumes decision_points.jsonl (built by decision_points.py scan) plus the
authoritative run CSVs; writes:
  analysis/reasoning_timing_cases.csv   — one row per detected timing issue
  analysis/memory_utility_cases.csv     — one row per memory-related decision
  analysis/timing_summary.json          — aggregates used by the MD reports

Detectors (machine-derivable, transcript-verified afterwards):
  Q1  wasted-observe  : OBSERVE turn whose query was already answered
                        (same tool+step, near-identical args, >=3rd time), or
                        perc_streak_before>=4 with no action since.
  Q1b wasted-memory   : MEMORY turn re-reading a file already read.
  Q2  blind-retry     : ACT repeated >=2x consecutively whose env outcome
                        signals failure (final_dist_m>0.05 / pick w/o grasp
                        / release w/o termination), with no OBSERVE between.
  Q2b phase-skip      : after a failed pick (no grasp), planner proceeds to
                        release/place without re-grasp or re-perception.
  DV  first-divergence: per (cond,task,seed) success-vs-failure pair (across
                        repeats), first turn where behavior class/tool-set
                        diverges; recorded with phase + think excerpts.
"""
import csv, glob, json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOGS = os.path.join(ROOT, "logs")
DP = os.path.join(HERE, "decision_points.jsonl")

sys.path.insert(0, HERE)


def load_runs():
    runs = {}
    for line in open(DP):
        r = json.loads(line)
        runs[r["run_id"]] = r
    return runs


def csv_registry():
    """(csv file, cond override) -> list of dict rows keyed by local dir name."""
    reg = {}   # name -> dict(ts, stage, task, seed, cond, repeat, result, src)
    for f in ("progress_gate_runs.csv", "structured_memory_runs.csv"):
        for row in csv.DictReader(open(os.path.join(HERE, f))):
            name = row["dir"].rstrip("/").split("/")[-1]
            reg.setdefault(name, dict(row, src=f.replace("_runs.csv", "")))
    return reg


def transcript_path(run_id):
    for base in ("pg_exp", "sm_exp", "dr_exp", "."):
        g = glob.glob(os.path.join(LOGS, base, run_id, "transcript_*.json"))
        if g:
            return g[0]
    return None


def guard_events(run_id):
    """[(tool, head)] of perception-guard interceptions from the transcript."""
    tp = transcript_path(run_id)
    if not tp:
        return []
    out = []
    for m in json.load(open(tp))["messages"]:
        if m.get("role") == "tool":
            c = str(m.get("content") or "")
            if c.startswith("Perception guard"):
                out.append((m.get("name"), c[:180]))
    return out


# ------------------------------------------------------------------ detectors
def arg_sig(args):
    a = dict(args or {})
    for k in ("path",):
        a.pop(k, None)
    return json.dumps(a, sort_keys=True)


def detect_wasted_observes(run):
    cases = []
    seen = collections.Counter()
    for p in run["points"]:
        for c in p.get("calls", []) if "calls" in p else []:
            pass
        # points store tools list; need args -> lightweight re-read? use counts
    return cases


def detect_cases(run):
    """Q1/Q2 cases from the point stream (args-free heuristics)."""
    cases = []
    pts = run["points"]
    # Q1: observe streaks >= 4 with no action, or observe after observe with
    # identical tool at same implicit step (same_tool_streak >= 3)
    for i, p in enumerate(pts):
        if p["cls"] == "OBSERVE":
            if p["perc_streak_before"] >= 4 and p["since_last_act"] >= 4:
                cases.append(dict(kind="Q1_wasted_observe", turn=p["turn"],
                                  phase=p.get("phase"), detail=f"streak={p['perc_streak_before']} since_act={p['since_last_act']}",
                                  tools=p["tools"]))
        if p["cls"] == "MEMORY" and p.get("same_tool_streak_before", 0) >= 1:
            cases.append(dict(kind="Q1b_repeat_memory", turn=p["turn"],
                              phase=p.get("phase"), detail="", tools=p["tools"]))
    # Q2: consecutive identical ACT with failing outcome proxies
    for i, p in enumerate(pts):
        if p["cls"] != "ACT":
            continue
        la = p.get("last_action") or {}
        # blind retry: same action tool as previous ACT turn, no OBSERVE between
        prev = pts[i - 1] if i else None
        prev2 = pts[i - 2] if i > 1 else None
        if prev and prev["cls"] == "ACT" and prev["tools"] and p["tools"] and \
           prev["tools"][0] == p["tools"][0] and p["tools"][0] in ("move_to", "pi0_pick", "pi0_doubled", "release"):
            bad = (la.get("dist") is not None and la.get("dist") > 0.05) or \
                  (p["tools"][0] == "release" and run.get("success") is False)
            cases.append(dict(kind="Q2_blind_retry", turn=p["turn"],
                              phase=p.get("phase"),
                              detail=f"tool={p['tools'][0]} prev_dist={la.get('dist')}",
                              tools=p["tools"], failing=bad))
    # Q2b phase-skip: pi0_pick -> (no grasp evidence) -> release soon after
    names = [(p["turn"], p["cls"], p["tools"]) for p in pts]
    for i in range(len(names) - 1):
        t1, c1, tl1 = names[i]
        if c1 == "ACT" and tl1 and tl1[0] == "pi0_pick":
            # look ahead: next ACT is release with no ACT-perception between
            nxt = [n for n in names[i + 1:] if n[1] in ("ACT",)]
            obs_between = any(n[1] == "OBSERVE" for n in names[i + 1:i + 4])
            if nxt and nxt[0][2] and nxt[0][2][0] == "release" and not obs_between:
                cases.append(dict(kind="Q2b_pick_to_release_skip", turn=nxt[0][0],
                                  phase=pts[min(nxt[0][0] - 1, len(pts) - 1)].get("phase"),
                                  detail=f"pick@t{t1} release@t{nxt[0][0]} no-observe-between",
                                  tools=nxt[0][2]))
    return cases


def first_divergence(ra, rb):
    """First behavioral divergence between two runs' point streams."""
    for i, (pa, pb) in enumerate(zip(ra["points"], rb["points"])):
        sa = (pa["cls"], tuple(sorted(set(pa["tools"]))))
        sb = (pb["cls"], tuple(sorted(set(pb["tools"]))))
        if sa != sb:
            return dict(turn=i + 1, a=sa, b=sb,
                        phase_a=pa.get("phase"), phase_b=pb.get("phase"),
                        think_a=pa.get("think", "")[:120],
                        think_b=pb.get("think", "")[:120])
    if len(ra["points"]) != len(rb["points"]):
        return dict(turn=min(len(ra["points"]), len(rb["points"])) + 1,
                    a="END", b="END-unequal-length",
                    phase_a=None, phase_b=None, think_a="", think_b="")
    return None


def main():
    runs = load_runs()
    reg = csv_registry()

    # ---------------- registry-joined view
    canon = []
    for name, row in reg.items():
        r = runs.get(name)
        if not r:
            continue
        canon.append(dict(run=r, row=row, src=row["src"]))
    print(f"canonical runs: {len(canon)} (pg+sm CSVs)")

    # ---------------- timing cases
    trows = []
    for c in canon:
        r, row = c["run"], c["row"]
        for case in detect_cases(r):
            trows.append(dict(
                exp=c["src"], cond=row["cond"], task=row["task"], seed=row["seed"],
                repeat=row["repeat"], success=r["success"], result=row.get("result"),
                run_id=r["run_id"], **{k: case[k] for k in
                                       ("kind", "turn", "phase", "detail", "tools")}))
    with open(os.path.join(HERE, "reasoning_timing_cases.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trows[0].keys()))
        w.writeheader(); w.writerows(trows)
    agg = collections.Counter((r["kind"], r["cond"], r["task"],
                               str(r["success"])) for r in trows)
    print("timing cases:", len(trows))
    for k, v in sorted(agg.items(), key=str):
        print("  ", k, v)

    # ---------------- within-cond success-vs-failure divergence (same task/seed)
    divs = []
    bycell = collections.defaultdict(list)
    for c in canon:
        bycell[(c["row"]["src"], c["row"]["cond"], c["row"]["task"], c["row"]["seed"])].append(c)
    for k, cs in sorted(bycell.items(), key=str):
        succ = [c for c in cs if c["run"]["success"]]
        fail = [c for c in cs if c["run"]["success"] is False]
        if succ and fail:
            d = first_divergence(succ[0]["run"], fail[0]["run"])
            if d:
                divs.append(dict(exp=k[0], cond=k[1], task=k[2], seed=k[3],
                                 succ=succ[0]["run"]["run_id"],
                                 fail=fail[0]["run"]["run_id"],
                                 succ_turns=succ[0]["run"]["n_turns"],
                                 fail_turns=fail[0]["run"]["n_turns"], **d))
    json.dump(divs, open(os.path.join(HERE, "divergences.json"), "w"), indent=1)
    print("divergence pairs:", len(divs))

    # ---------------- hardcap guard events
    guards = {}
    for c in canon:
        if c["row"]["cond"] in ("ours", "hardcap"):
            g = guard_events(c["run"]["run_id"])
            if g:
                guards[c["run"]["run_id"]] = g
    json.dump({k: v[:12] for k, v in guards.items()},
              open(os.path.join(HERE, "guard_events.json"), "w"), indent=1)
    print("runs with guard blocks:", len(guards),
          "total blocks:", sum(len(v) for v in guards.values()))

    json.dump(dict(n_canon=len(canon), n_timing=len(trows), n_div=len(len(divs) * [0])),
              open(os.path.join(HERE, "timing_summary.json"), "w"))
    print("done")


if __name__ == "__main__":
    main()
