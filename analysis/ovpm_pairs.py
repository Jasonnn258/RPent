#!/usr/bin/env python3
"""§5 paired analysis — outcome_validation_pairs.csv (plan §8 deliverable).

Pairs armA (SM1) vs armB (A+OVP-M) runs by (task, seed, repeat) from
outcome_validation_runs.csv (stage filter), then classifies each pair by the
first measurable divergence and the B-arm verdict metrics. Class set (from
the plan): correct commit / premature commit / correct recovery /
recovery-too-late / unnecessary reasoning / insufficient reasoning /
memory mismatch / perception-execution failure — grounded here in observable
signals (env outcomes, [ovpm] counters, milestone streams), never benchmark
GT. Pairs the classifier cannot ground land in "other-*" buckets for manual
review — they are REPORTED, never silently dropped.

Usage: python analysis/ovpm_pairs.py [--stage dev] [--csv PATH]
"""
import argparse
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sanity_tier_selection import load_events, classify_mechanism  # noqa: E402

RUNS_CSV = os.path.join(HERE, "outcome_validation_runs.csv")
PAIRS_CSV = os.path.join(HERE, "outcome_validation_pairs.csv")

FIELDS = [
    "task", "seed", "repeat",
    "a_result", "b_result", "a_mech", "b_mech",
    "a_turns", "b_turns", "a_wall", "b_wall",
    "b_matched", "b_mismatched", "b_escalations",
    "b_commit_ev", "b_recovery_ev",
    "b_commit_lat", "b_recovery_lat", "b_repeat_same",
    "flip", "class", "divergence",
]


def turns_of(row):
    ev = load_events(row["dir"])
    return len({e["turn"] for e in ev["events"]}) if ev else ""


def div_of(row_a, row_b):
    """First milestone divergence between the two transcripts (a=success side
    convention from pairing_analysis is not assumed here — just locate it)."""
    import pairing_analysis as pa  # noqa: E402
    ta, tb = load_events(row_a["dir"]), load_events(row_b["dir"])
    if not ta or not tb:
        return "missing-transcript"
    ms_a = pa.milestones(ta)
    ms_b = pa.milestones(tb)
    for i in range(max(len(ms_a), len(ms_b))):
        xa = ms_a[i] if i < len(ms_a) else None
        xb = ms_b[i] if i < len(ms_b) else None
        if xa is None or xb is None or xa["m"] != xb["m"]:
            ma = xa["m"] if xa else "END"
            mb = xb["m"] if xb else "END"
            return f"milestone-set@{i}:{ma}/{mb}"
        if xa["out"] != xb["out"]:
            return (f"outcome@{xa['m']}:"
                    f"hold={xa['out'].get('hold')}/term={xa['out'].get('term')}"
                    f" vs hold={xb['out'].get('hold')}/term={xb['out'].get('term')}")
    return "milestones-identical"


def classify_pair(a, b, div, a_turns, b_turns):
    """Map the observable signals onto the plan's class set."""
    esc = int(b.get("ovpm_mismatch_escalations") or 0)
    rlat = b.get("ovpm_recovery_latency_mean") or ""
    rlat_ok = rlat != "" and float(rlat) <= 2.0
    rep = int(b.get("ovpm_repeated_same_strategy") or 0)
    cmit = int(b.get("ovpm_commit_events") or 0)
    if a["result"] == "success" and b["result"] == "success":
        try:
            faster = (float(b["wall_s"]) < float(a["wall_s"]) - 60
                      or int(b_turns) < int(a_turns) - 2)
        except (ValueError, TypeError):
            faster = False
        return "both-success" + ("+faster" if faster else "")
    if a["result"] != "success" and b["result"] == "success":
        if esc >= 1 and rlat_ok:
            return "correct recovery"
        if esc >= 1:
            return "recovery-late-but-ok"
        if cmit >= 1:
            return "correct commit"
        return "other-rescue (manual review)"
    if a["result"] == "success" and b["result"] != "success":
        # B regressed: did it stop repeating a strategy that used to work,
        # or commit past a mismatch?
        if div.startswith("outcome@release"):
            return "perception-execution failure"
        if rep >= 1:
            return "insufficient reasoning (repeat after mismatch)"
        if cmit >= 1 and str(b_turns) != "" and int(b_turns) <= 15:
            return "premature commit"
        return "other-regression (manual review)"
    # both fail
    if rep >= 1:
        return "strategy repetition persists"
    if esc >= 1 and not rlat_ok:
        return "recovery-too-late"
    return "both-fail-same-class"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="dev")
    ap.add_argument("--csv", default=RUNS_CSV)
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.csv))
            if r["stage"] == args.stage and r["cond"] in ("armA", "armB")
            and r["result"] not in ("infra_crash", "infra_timeout")]
    by = {}
    for r in rows:
        by.setdefault((r["task"], r["seed"], r["repeat"]), {})[r["cond"]] = r

    out = []
    for (task, seed, rep), ab in sorted(by.items()):
        if "armA" not in ab or "armB" not in ab:
            continue  # incomplete pair — infra rows excluded upstream
        a, b = ab["armA"], ab["armB"]
        div = div_of(a, b)
        pair = {
            "task": task, "seed": seed, "repeat": rep,
            "a_result": a["result"], "b_result": b["result"],
            "a_mech": classify_mechanism(load_events(a["dir"])),
            "b_mech": classify_mechanism(load_events(b["dir"])),
            "a_turns": turns_of(a), "b_turns": turns_of(b),
            "a_wall": a["wall_s"], "b_wall": b["wall_s"],
            "b_matched": b.get("ovpm_n_matched", ""),
            "b_mismatched": b.get("ovpm_n_mismatched", ""),
            "b_escalations": b.get("ovpm_mismatch_escalations", ""),
            "b_commit_ev": b.get("ovpm_commit_events", ""),
            "b_recovery_ev": b.get("ovpm_recovery_events", ""),
            "b_commit_lat": b.get("ovpm_commit_latency_mean", ""),
            "b_recovery_lat": b.get("ovpm_recovery_latency_mean", ""),
            "b_repeat_same": b.get("ovpm_repeated_same_strategy", ""),
            "divergence": div,
        }
        pair["flip"] = ("A-fail->B-succ" if (a["result"] != "success"
                                             and b["result"] == "success")
                        else "A-succ->B-fail" if (a["result"] == "success"
                                                  and b["result"] != "success")
                        else "none")
        pair["class"] = classify_pair(a, b, div, pair["a_turns"],
                                      pair["b_turns"])
        out.append(pair)

    with open(PAIRS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} pairs -> {PAIRS_CSV}")
    from collections import Counter
    for k, v in Counter(p["class"] for p in out).most_common():
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
