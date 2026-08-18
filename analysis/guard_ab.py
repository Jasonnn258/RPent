"""A/B comparison: original rule vs repeated-perception guard.

Baseline (original): latest run in logs/*_libero_spatial_task_t{task}_s{seed}/
Intervention (guard): .gap_run/guard_exp/spatial_task_t{task}_s{seed}/

Metrics per run (from compare_suites.analyze): success, turns, perc, act,
max_redundant_perc, first_action_call, n_env_steps, failure reason.

Usage: python analysis/guard_ab.py [--out analysis/guard_ab.csv]
"""
import os, sys, glob, re, csv
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_suites import analyze, load_states, parse_turns

LOGS = "/hw-tbo/yjx/workspace/RPent/logs"
EXPDIR = "/hw-tbo/yjx/workspace/RPent/.gap_run/guard_exp"
SUITE = "libero_spatial_task"
KEY = "spatial_task"
TASKS = (0, 7, 9)
SEEDS = list(range(1, 11))


def latest_original(task, seed):
    cands = sorted(glob.glob(f"{LOGS}/*_libero_{KEY}_t{task}_s{seed}/"))
    # exclude guard-exp runs just in case (they live outside logs/ anyway)
    return cands[-1] if cands else None


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "analysis/guard_ab.csv"
    rows = []
    for task in TASKS:
        for seed in SEEDS:
            orig = latest_original(task, seed)
            guard = f"{EXPDIR}/{KEY}_t{task}_s{seed}"
            if not orig or not os.path.exists(os.path.join(guard, "states.json")):
                continue
            ro, rg = analyze(orig), analyze(guard)
            rows.append({
                "task": task, "seed": seed,
                "orig_run": os.path.basename(orig.rstrip("/")),
                "guard_run": os.path.basename(guard.rstrip("/")),
                "orig_success": ro["success"], "guard_success": rg["success"],
                "orig_turns": ro["n_turns"], "guard_turns": rg["n_turns"],
                "orig_perc": ro["perc"], "guard_perc": rg["perc"],
                "orig_act": ro["act"], "guard_act": rg["act"],
                "orig_red": ro["max_redundant_perc"], "guard_red": rg["max_redundant_perc"],
                "orig_first": ro["first_action_call"], "guard_first": rg["first_action_call"],
                "orig_steps": ro["n_env_steps"], "guard_steps": rg["n_env_steps"],
                "orig_reason": ro["reason"], "guard_reason": rg["reason"],
            })
    cols = ["task", "seed", "orig_run", "guard_run",
            "orig_success", "guard_success", "orig_turns", "guard_turns",
            "orig_perc", "guard_perc", "orig_act", "guard_act",
            "orig_red", "guard_red", "orig_first", "guard_first",
            "orig_steps", "guard_steps", "orig_reason", "guard_reason"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    n = len(rows)
    print(f"wrote {n} paired rows -> {out}\n")
    if not n:
        return
    def frac(pred):
        return sum(1 for r in rows if pred(r)) / n
    print(f"===== {SUITE} t{TASKS} seeds1-10: original vs guard ({n} pairs) =====")
    for side, p in (("orig", "original"), ("guard", "guard")):
        ok = sum(r[f"{side}_success"] for r in rows)
        turns = round(sum(r[f"{side}_turns"] for r in rows) / n, 1)
        perc = round(sum(r[f"{side}_perc"] for r in rows) / n, 1)
        act = round(sum(r[f"{side}_act"] for r in rows) / n, 1)
        red = round(sum(r[f"{side}_red"] for r in rows) / n, 1)
        first = round(sum((r[f"{side}_first"] or n) for r in rows) / n, 1)
        steps = round(sum(r[f"{side}_steps"] for r in rows) / n, 1)
        print(f"  {p}: SR={ok}/{n} ({ok/n:.0%})  turns={turns}  perc={perc}  "
              f"act={act}  maxred={red}  first_action_call={first}  env_steps={steps}")
    # pair-level win/loss
    both = sum(r["orig_success"] and r["guard_success"] for r in rows)
    none = sum((not r["orig_success"]) and (not r["guard_success"]) for r in rows)
    guard_win = sum((not r["orig_success"]) and r["guard_success"] for r in rows)
    guard_lose = sum(r["orig_success"] and (not r["guard_success"]) for r in rows)
    print(f"  both={both} neither={none} guard-wins={guard_win} guard-loses={guard_lose}")
    for side, label in (("orig", "original"), ("guard", "guard")):
        rc = Counter(r[f"{side}_reason"] for r in rows)
        print(f"  {label} reasons: " + ", ".join(f"{k}:{v/n:.0%}" for k, v in rc.most_common()))
    # per-task SR
    for t in TASKS:
        tr = [r for r in rows if r["task"] == t]
        a = sum(r["orig_success"] for r in tr); b = sum(r["guard_success"] for r in tr)
        print(f"  t{t}: original {a}/{len(tr)}  guard {b}/{len(tr)}")


if __name__ == "__main__":
    main()
