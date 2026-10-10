#!/usr/bin/env python3
"""P1 Return-Time Triage Robustness v1 (read-only L1 supplementary checks).

Pre-registered descriptive robustness analysis for the triage lab round,
requested alongside the main experiment: does the Top20%/40% selective gain
depend on a few episodes or on a single task? No arm, threshold or budget is
modified here; the frozen triage lab arms/scores are reused verbatim.

Checks:
1. Episode-cluster bootstrap of precision@budget (failures cluster mildly:
   103 rows / 79 episodes). Median + percentile interval per arm.
2. Leave-one-episode-out jackknife of precision@budget: max single-episode
   influence, worst-case precision.
3. Expected task composition of the fractional top-K sets (single-task
   dependence check) and per-task score-level medians (cross-task score
   stationarity check).

Aggregate-only output: no episode ids, no poses, no case-level values.
Exit-time FGONLY remains a kinematic weak proxy, NOT grasp truth.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import ROOT, SRC
from p1_return_time_triage_lab import (
    ARMS, RATIOS, build_rows, priority, topk_expected)

PROTOCOL = "RPENT_P1_RETURN_TIME_TRIAGE_ROBUSTNESS_V1"
OUT = ROOT / "artifacts" / "p1_return_time_triage_lab"
SEED = 20261013
BOOT = 1000


def frac_selected_mix(rows, arm, ratio, dim):
    """Fractional top-K expected selection counts along an aggregate dim."""
    import math
    if dim not in ("task", "gate_pattern"):
        raise ValueError("Unapproved aggregate dimension")
    k = math.ceil(ratio * len(rows))
    groups = defaultdict(list)
    for r in rows:
        groups[priority(arm, r["legal"])].append(r)
    sel = Counter()
    pos = Counter()
    remain = k
    for score in sorted(groups, reverse=True):
        if remain <= 0:
            break
        grp = groups[score]
        fraction = min(remain, len(grp)) / len(grp)
        for r in grp:
            key = r["task"] if dim == "task" else r["legal"]["gate_pattern"]
            sel[key] += fraction
            if r["exit_proxy_positive"]:
                pos[key] += fraction
        remain -= min(remain, len(grp))
    return {"selected": dict(sorted(sel.items())),
            "selected_proxy_positive": dict(sorted(pos.items()))}


def bootstrap_precision(rows, arm, ratio=.20, repeats=BOOT, seed=SEED):
    """Episode-cluster resample; precision@budget quantiles per arm."""
    rng = random.Random(seed)
    by_ep = defaultdict(list)
    for r in rows:
        by_ep[r["episode_id"]].append(r)
    episodes = sorted(by_ep)
    precs = []
    for _ in range(repeats):
        sample = []
        for _ in episodes:
            sample.extend(by_ep[rng.choice(episodes)])
        precs.append(topk_expected(sample, arm, ratio)["precision_at_budget"])
    precs.sort()
    n = len(precs)
    return {
        "arm": arm, "budget_ratio": ratio, "repeats": repeats, "seed": seed,
        "median": round(statistics.median(precs), 4),
        "p2_5": round(precs[int(.025 * n)], 4),
        "p97_5": round(precs[min(n - 1, int(.975 * n))], 4),
        "min": round(precs[0], 4),
    }


def jackknife_episodes(rows, arm, ratio=.20):
    """Leave-one-episode-out precision@budget; worst single-episode pull."""
    base = topk_expected(rows, arm, ratio)["precision_at_budget"]
    # 按行索引剔除,避免内容相同的不同失败行被 dict 相等性一起误删。
    by_ep = defaultdict(list)
    for i, r in enumerate(rows):
        by_ep[r["episode_id"]].append(i)
    loos = []
    for eps in by_ep.values():
        drop = set(eps)
        rest = [r for i, r in enumerate(rows) if i not in drop]
        if not rest:
            continue
        loos.append(topk_expected(rest, arm, ratio)["precision_at_budget"])
    return {
        "arm": arm, "budget_ratio": ratio, "full_precision": round(base, 4),
        "n_episodes": len(by_ep),
        "max_abs_delta": round(max(abs(v - base) for v in loos), 4)
        if loos else None,
        # 直接取 LOO 值的 min/max,不用 base±delta 组合(对称 fixture 下才碰巧等价)
        "min_leave_one_out_precision": round(min(loos), 4) if loos else None,
        "max_leave_one_out_precision": round(max(loos), 4) if loos else None,
    }


def score_levels(rows):
    """Per-task median frozen scores; cross-task score stationarity check."""
    out = {}
    for task in sorted({r["task"] for r in rows}):
        sub = [r for r in rows if r["task"] == task]
        entry = {"n": len(sub)}
        for arm in ("LIFT_MINUS_GAP", "PEAK_LIFT"):
            for label, want in (("exit_proxy_positive", True),
                                ("exit_proxy_positive", False)):
                vals = [priority(arm, r["legal"]) for r in sub
                        if r[label] is want]
                name = arm + ("_pos" if want else "_neg")
                entry[name] = round(statistics.median(vals), 4) if vals else None
        out[task] = entry
    return out


def run():
    rows = build_rows()
    return {
        "protocol": PROTOCOL,
        "mode": "DESCRIPTIVE_ROBUSTNESS_NO_TUNING",
        "n_failures": len(rows),
        "n_episodes": len({r["episode_id"] for r in rows}),
        "episode_size_histogram": dict(sorted(Counter(
            Counter(r["episode_id"] for r in rows).values()).items())),
        "bootstrap_precision_budget20": [
            bootstrap_precision(rows, arm, .20) for arm in ARMS],
        "bootstrap_precision_budget40_LIFT_MINUS_GAP":
            bootstrap_precision(rows, "LIFT_MINUS_GAP", .40),
        "jackknife_budget20": [jackknife_episodes(rows, arm, .20)
                               for arm in ARMS],
        "topk_task_composition": {
            f"LIFT_MINUS_GAP_top_{round(100*b)}pct":
                frac_selected_mix(rows, "LIFT_MINUS_GAP", b, "task")
            for b in RATIOS},
        "topk_pattern_composition": {
            f"LIFT_MINUS_GAP_top_{round(100*b)}pct":
                frac_selected_mix(rows, "LIFT_MINUS_GAP", b, "gate_pattern")
            for b in RATIOS},
        "per_task_score_levels": score_levels(rows),
        "contract": [
            "Frozen triage arms/scores/budgets reused verbatim; nothing tuned.",
            "Bootstrap/jackknife describe episode-clustered sample uncertainty only.",
            "Aggregate-only output; no episode ids, poses, or case-level values.",
        ],
    }


def main():
    pa = argparse.ArgumentParser(description=__doc__)
    pa.add_argument("--out", type=Path, default=OUT)
    args = pa.parse_args()
    if not args.out.resolve().is_relative_to((ROOT / "artifacts").resolve()):
        pa.error("Output must stay inside private gitignored artifacts/")
    result = run()
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "robustness_v1.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "protocol": result["protocol"],
        "n_failures": result["n_failures"],
        "n_episodes": result["n_episodes"],
        "episode_size_histogram": result["episode_size_histogram"],
        "bootstrap_precision_budget20": result["bootstrap_precision_budget20"],
        "jackknife_budget20_LIFT_MINUS_GAP":
            [j for j in result["jackknife_budget20"]
             if j["arm"] == "LIFT_MINUS_GAP"],
        "topk_task_composition": result["topk_task_composition"],
        "per_task_score_levels": result["per_task_score_levels"],
        "output": str(target),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
