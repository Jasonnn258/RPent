#!/usr/bin/env python3
"""§1 sanity tier selection — PRE-REGISTERED criteria (plan keen-swinging-dove).

Reads analysis/outcome_validation_runs.csv (stage=sanity), reclassifies every
run with the diagnostics-era milestone taxonomy (no_pick / grasp_fail /
place_stall / place_fail / success — same logic as the 303-run diagnostic
table), then applies the criteria fixed BEFORE seeing the data:

  ① failure-form fidelity (primary): per task, the dominant failure mechanism
     must match the diagnostic baseline — t7 -> place_stall, t0/t9 ->
     place_fail — and grasp_fail must stay marginal (<20% of failures).
     Score = number of tasks reproduced (0-3).
  ② SR in usable band: tier SR within [15%, 85%] (not floor, not ceiling).
  ③ tie -> flagship glm-5.3.

Output: stdout tables + analysis/sanity_tier_selection.md.

Usage: python analysis/sanity_tier_selection.py [--csv PATH]
"""
import argparse
import csv
import glob
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS_CSV = os.path.join(HERE, "outcome_validation_runs.csv")
OUT_MD = os.path.join(HERE, "sanity_tier_selection.md")

# diagnostic baseline (303-run table, reasoning_timing_failure_analysis.md §1)
EXPECTED_DOMINANT = {0: "place_fail", 7: "place_stall", 9: "place_fail"}
GRASP_FAIL_MAX_SHARE = 0.20
SR_BAND = (0.15, 0.85)
MECHANISMS = ["no_pick", "grasp_fail", "place_stall", "place_fail", "success"]


# ------------------------------------------------------------------ transcript

def load_events(outdir):
    """Milestone events from a run dir; reuses pairing_analysis parsing."""
    import sys
    sys.path.insert(0, HERE)
    import pairing_analysis as pa

    tl = glob.glob(os.path.join(outdir, "transcript_*.json"))
    if not tl:
        return None
    t = json.load(open(tl[0]))
    # arm B appends "[ovpm] ..." lines AFTER the result JSON — strip before
    # pa-style parsing so json.loads still sees a clean blob
    res = {}
    for m in t["messages"]:
        if m.get("role") == "tool":
            res[m.get("tool_call_id")] = m.get("content")
    events, turn = [], 0
    for m in t["messages"]:
        if m.get("role") != "assistant":
            continue
        turn += 1
        for p in (m.get("content") or []):
            if isinstance(p, dict) and p.get("type") == "tool_use":
                events.append(dict(turn=turn, name=p.get("name"),
                                   args=p.get("input") or {}, cid=p.get("id")))
    for e in events:
        c = res.get(e["cid"])
        s = c if isinstance(c, str) else json.dumps(c)
        if s.startswith("Perception guard") or '"perception_blocked"' in s[:120]:
            e["outcome"] = {"guard": True}
            continue
        s_clean = "\n".join(ln for ln in s.splitlines()
                            if not ln.lstrip().startswith("[ovpm]"))
        try:
            d = json.loads(s_clean)
        except Exception:
            e["outcome"] = {}
            continue
        log = d.get("log") or {}
        r = log.get("result") or {}
        o = {}
        if e["name"] == "pi0_pick":
            o = dict(kind="pick", pick_success=r.get("success"),
                     min_grip=r.get("min_gripper_opening"))
        elif e["name"] == "pi0_doubled":
            o = dict(kind="doubled", pick_success=r.get("success"),
                     min_grip=r.get("min_gripper_opening"))
        elif e["name"] == "release":
            o = dict(kind="release", term=r.get(
                "libero_terminated", d.get("libero_terminated")))
        elif e["name"] == "move_to":
            o = dict(kind="move")
        elif e["name"] == "set_gripper":
            o = dict(kind="gripper", term=r.get("libero_terminated"))
        elif e["name"] == "finish":
            o = dict(kind="finish", status=e["args"].get("status"))
        if d.get("libero_terminated"):
            o["term"] = True
        e["outcome"] = o
    fin = t.get("finish") or {}
    return dict(events=events, success=bool(fin.get("status") == "success"))


def holds(o):
    if not o or o.get("kind") not in ("pick", "doubled"):
        return None
    if o.get("pick_success") is True:
        return True
    mg = o.get("min_grip")
    if mg is not None and mg < 0.03:
        return True
    if mg is not None and mg >= 0.03 and o.get("pick_success") is False:
        return False
    return None


def classify_mechanism(ev):
    """Same milestone taxonomy as the 303-run diagnostic table.

    Success ground truth = env predicate fired (any tool result with
    libero_terminated=true) OR agent finish=success — the agent may never
    call finish after a terminating action (seen: t0 s6 finish=None with 5
    term-bearing results), so finish alone undercounts SR.
    """
    if ev is None:
        return "missing"
    term_any = any(e["outcome"].get("term") is True for e in ev["events"])
    if ev["success"] or term_any:
        return "success"
    picks = [e for e in ev["events"] if e["outcome"].get("kind") in ("pick",
                                                                     "doubled")]
    places = [e for e in ev["events"]
              if e["outcome"].get("kind") in ("release", "doubled", "gripper")]
    if not picks:
        return "no_pick"
    if not any(holds(e["outcome"]) for e in picks):
        return "grasp_fail"
    if not places:
        return "place_stall"
    return "place_fail"


# ------------------------------------------------------------------ aggregate

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=RUNS_CSV)
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.csv))
            if r["stage"] == "sanity"]
    tiers = sorted({r["tier"] for r in rows})
    per = defaultdict(Counter)       # (tier, task) -> mechanism counts
    seen = Counter()                 # (tier, task) -> n valid rows
    problems = []
    for r in rows:
        if r["result"] in ("infra_crash", "infra_timeout"):
            # planner-hang / crash artifacts: partial transcripts would pollute
            # the failure-form distribution (usually no_pick) — report, exclude
            problems.append((r["tier"], r["task"], r["seed"], r["result"]))
            continue
        if r["result"] == "success":
            # env predicate fired (states.json libero_terminated) — ground
            # truth. The transcript can be EMPTY on this path: when a
            # post-success wrap-up planner call hangs to the 2400s timeout,
            # the dump keeps only the initial user message (seen: flash t7
            # s6/s8/s10 — env terminated at step 8, transcript 1 message).
            per[(r["tier"], int(r["task"]))]["success"] += 1
            seen[(r["tier"], int(r["task"]))] += 1
            continue
        mech = classify_mechanism(load_events(r["dir"]))
        per[(r["tier"], int(r["task"]))][mech] += 1
        seen[(r["tier"], int(r["task"]))] += 1

    # ---------------- table 1: mechanism distribution (diagnostic layout)
    L = ["# §1 sanity — tier selection (pre-registered)", "",
         f"_runs: {len(rows)} rows over tiers {tiers}; criteria fixed in plan "
         "keen-swinging-dove §1 BEFORE data: ① failure-form fidelity "
         "(t7→place_stall, t0/t9→place_fail dominant, grasp_fail<20%) ② SR "
         "band 15–85% ③ tie→flagship glm-5.3._", "",
         "## Mechanism distribution (per tier/task, n=10 seeds)", ""]
    hdr = ("| tier | task | no_pick | grasp_fail | place_stall | place_fail "
           "| success | SR |")
    L += [hdr, "|---|---|---|---|---|---|---|---|"]
    for tier in tiers:
        for task in sorted({t for (ti, t) in per if ti == tier}):
            c = per[(tier, task)]
            n = seen[(tier, task)]
            L.append(f"| {tier} | t{task} | {c['no_pick']} | {c['grasp_fail']} "
                     f"| {c['place_stall']} | {c['place_fail']} "
                     f"| {c['success']} | {c['success']}/{n} |")

    # ---------------- criteria
    score = {}
    for tier in tiers:
        fids, grasp_ok = [], True
        for task, exp in EXPECTED_DOMINANT.items():
            c = per.get((tier, task))
            if not c:
                fids.append(None)
                continue
            fails = sum(c[m] for m in
                        ("no_pick", "grasp_fail", "place_stall", "place_fail"))
            if fails == 0:
                fids.append(None)       # no failures to compare forms on
                continue
            dom = Counter({m: c[m] for m in
                           ("no_pick", "grasp_fail", "place_stall",
                            "place_fail")}).most_common(1)[0][0]
            fids.append(dom == exp)
            if c["grasp_fail"] / fails > GRASP_FAIL_MAX_SHARE:
                grasp_ok = False
        n_succ = sum(per[(tier, t)]["success"]
                     for (ti, t) in per if ti == tier)
        n_tot = sum(seen[(ti, t)] for (ti, t) in seen if ti == tier)
        sr = n_succ / max(n_tot, 1)
        score[tier] = dict(
            fidelity=sum(1 for f in fids if f is True),
            fidelity_detail=[{0: "t0", 7: "t7", 9: "t9"}[t] +
                             ("=" if f else ("≠" if f is False else "?"))
                             for t, f in zip(EXPECTED_DOMINANT, fids)],
            grasp_ok=grasp_ok, sr=sr, sr_in_band=SR_BAND[0] <= sr <= SR_BAND[1])

    # ---------------- decision
    def key(t):
        s = score[t]
        return (s["fidelity"], int(s["grasp_ok"]), int(s["sr_in_band"]),
                1 if t == "glm-5.3" else 0)

    best = max(tiers, key=key) if tiers else None
    L += ["", "## Pre-registered criteria", "",
          "| tier | ① fidelity (of 3) | grasp_fail<20% | SR | SR in band |",
          "|---|---|---|---|---|"]
    for t in tiers:
        s = score[t]
        L.append(f"| {t} | {s['fidelity']} ({' '.join(s['fidelity_detail'])}) "
                 f"| {'✓' if s['grasp_ok'] else '✗'} | {s['sr']:.0%} "
                 f"| {'✓' if s['sr_in_band'] else '✗'} |")
    L += ["", f"**Selected tier: `{best}`** "
          f"(① fidelity → ② SR band → ③ flagship tie-break, in that order).",
          ""]
    if problems:
        L += ["## Infra rows (excluded from distributions — planner hangs/crashes, "
              "retried up to 3x by the scheduler)", ""]
        L += [f"- {p}" for p in problems] + [""]
    L += ["---", "_Failure-form sanity gate: if NEITHER tier reproduces the "
          "diagnostic failure forms (fidelity < 2/3 both), STOP per plan and "
          "report — taxonomy drift invalidates the B/C comparison._"]

    out = "\n".join(L)
    print(out)
    with open(OUT_MD, "w") as f:
        f.write(out + "\n")
    print(f"\nwritten: {OUT_MD}")


if __name__ == "__main__":
    main()
