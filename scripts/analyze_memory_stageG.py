#!/usr/bin/env python3
"""Stage G analysis — CVPR validation of progress-gated procedural recall.

Reads stages g1-g4 rows (tier glm-5.3-flash) from outcome_validation_runs.csv
plus per-episode memory_events.jsonl / states.json / run.log, and emits:

  analysis/stageG_G{1,2,3,4}_runs.csv   per-episode tables (deliverable §26)
  analysis/stageG_results.json          machine-readable everything
  analysis/stageG_summary.md            TABLE 1-4 + verdict stats (§20-24)

Arms (pre-registered, stageG_subset_manifest.md):
  G1  M0=memB1  M1=memB2  M2=memO2                 (full 145-cell grid/arm)
  G2  T0=memB1 T1=memB2 T2=trigT2 T3=trigT3 T4=memO2 (trigger behavior)
  G3  A=memB2 B=memB3 C=memO2 D=memO3               (45-cell subset/arm)
  G4  {NAIVE,PROGRESS} x {1X,2X,MAX}                (45-cell subset/arm)

Stats pre-registered (§7 / manifest §4): McNemar exact p on paired flips,
paired bootstrap 95% CI (10,000 resamples), macro (per-task mean) AND
micro (pooled) — macro CI uses the task as the resampling cluster.
Infra rows (infra_crash/infra_timeout/infra_missing) are counted in a
separate column and NEVER enter SR denominators or pairs.

Usage: python scripts/analyze_memory_stageG.py [--stages g1,g2]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import analyze_memory_stageB as sb  # noqa: E402
import analyze_memory_stageC as sc  # noqa: E402
import memory_stagec2_benchmark as c2  # noqa: E402

OVPM = REPO / "logs" / "ovpm_exp"
RUNS_CSV = REPO / "analysis" / "outcome_validation_runs.csv"
TIER = "glm-5.3-flash"
BOOT_N = 10_000
RNG_SEED = 20260920  # fixed: bootstrap CIs must reproduce

INFRA = ("infra_crash", "infra_timeout", "infra_missing")

# ---------------------------------------------------------------- grids
G_SUITES = ["libero_object_task", "libero_goal_task", "libero_10_task"]
G_TASKS_BY_SUITE = {
    "libero_object_task": list(range(10)),
    "libero_goal_task": list(range(10)),
    "libero_10_task": [1, 2, 3, 4, 5, 6, 7, 8, 9],
}
G_SUBSET_BY_SUITE = {
    "libero_object_task": [0, 3, 7],
    "libero_goal_task": [0, 3, 7],
    "libero_10_task": [1, 3, 7],
}
G_SEEDS = range(1, 6)

# arm label -> (stage, cond); T0/T1/T4/A/C/1X reuse the G1 rows
ARMS = {
    "M0": ("g1", "memB1"), "M1": ("g1", "memB2"), "M2": ("g1", "memO2"),
    "T0": ("g1", "memB1"), "T1": ("g1", "memB2"),
    "T2": ("g2", "trigT2"), "T3": ("g2", "trigT3"), "T4": ("g1", "memO2"),
    "A": ("g1", "memB2"), "B": ("g3", "memB3"),
    "C": ("g1", "memO2"), "D": ("g3", "memO3"),
    "N1X": ("g1", "memB2"), "N2X": ("g4", "bank2xB"),
    "NMX": ("g4", "bankmxB"), "P1X": ("g1", "memO2"),
    "P2X": ("g4", "bank2xP"), "PMX": ("g4", "bankmxP"),
}

# arm label -> class-agnostic trigger? (T2 timer / T3 generic signal fire
# with no symptom class; alignment/coverage for them ignores class family)
CLASS_AGNOSTIC = {"T2", "T3"}

PHASE_BUCKET = {"P_look": "PERCEPTION", "P_grasp": "PICK",
                "P_transport": "MOVE", "P_place": "PLACE",
                "P_verify": "PREDICATE"}


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- loading

def load_rows():
    """[(stage,cond,suite,task,seed)] -> row; repeats collapsed to r1."""
    rows = {}
    for r in sb.csv_dict():
        if r["tier"] != TIER or int(r["repeat"]) != 1:
            continue
        if r["stage"] not in ("g1", "g2", "g3", "g4"):
            continue
        k = (r["stage"], r["cond"], r["suite"], int(r["task"]),
             int(r["seed"]))
        rows[k] = r
    return rows


def arm_rows(rows, arm, subset=False):
    """Rows for one arm keyed (suite, task, seed), restricted to the grid.

    Returns (cells, infra) — `infra` counts every infra-classified row so
    §7's separate bookkeeping survives the SR exclusion.
    """
    stage, cond = ARMS[arm]
    out, infra = {}, collections.Counter()
    for (st, c, su, t, s), r in rows.items():
        if st != stage or c != cond:
            continue
        if subset and (su not in G_SUBSET_BY_SUITE or t not in
                       G_SUBSET_BY_SUITE[su] or s not in G_SEEDS):
            continue
        if not subset and (su not in G_TASKS_BY_SUITE or t not in
                           G_TASKS_BY_SUITE[su] or s not in G_SEEDS):
            continue
        if r["result"] in INFRA:
            infra[(su, t, s)] = r["result"]
            continue
        out[(su, t, s)] = r
    return out, infra


def ep_events(r):
    p = Path(r["dir"]) / "memory_events.jsonl"
    evs = []
    if p.exists():
        for line in p.read_text(errors="replace").splitlines():
            if line.strip():
                try:
                    evs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return evs


def ep_turns(r):
    mx = 0
    try:
        for ln in (Path(r["dir"]) / "run.log").read_text(
                errors="replace").splitlines():
            m = re.search(r"=== turn (\d+)/", ln)
            if m:
                mx = max(mx, int(m.group(1)))
    except OSError:
        pass
    return mx


def cls_of(arm, e):
    if arm in CLASS_AGNOSTIC:
        return None
    if ARMS[arm][1] == "memO2" or ARMS[arm][1] == "memO3":
        return sc.o2_cls_of_event(e)
    return c2.t0_fire_class(e.get("trigger_reason", ""))


# ---------------------------------------------------------------- stats

def mcnemar_exact(b, c):
    """Two-sided exact McNemar p = 2*P(X<=min(b,c)), X~Bin(b+c,.5)."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_boot(cells, va, vb, n=BOOT_N, seed=RNG_SEED):
    """95% CI of mean(vb-va) resampling paired cells; micro level."""
    rng = random.Random(seed)
    diffs = [vb[k] - va[k] for k in cells]
    if not diffs:
        return None
    out = []
    for _ in range(n):
        s = sum(diffs[rng.randrange(len(diffs))]
                for _ in range(len(diffs))) / len(diffs)
        out.append(s)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def macro_boot(pairs_by_task, n=BOOT_N, seed=RNG_SEED):
    """95% CI of the macro (per-task mean of paired diffs); tasks are the
    resampling clusters."""
    rng = random.Random(seed)
    per_task = [sum(v) / len(v) for v in pairs_by_task.values() if v]
    if not per_task:
        return None
    out = []
    for _ in range(n):
        out.append(sum(per_task[rng.randrange(len(per_task))]
                       for _ in range(len(per_task))) / len(per_task))
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def sr_stats(cells_rows):
    """micro/macro/per-suite/per-task SR + turns/wall/fires means."""
    rs = list(cells_rows.values())
    if not rs:
        return {"n": 0}
    succ = [r["result"] == "success" for r in rs]
    by_task = collections.defaultdict(list)
    by_suite = collections.defaultdict(list)
    for (su, t, s), r in cells_rows.items():
        by_task[(su, t)].append(r["result"] == "success")
        by_suite[su].append(r["result"] == "success")
    turns = [ep_turns(r) for r in rs]
    walls = [float(r["wall_s"] or 0) for r in rs]
    return {
        "n": len(rs),
        "SR_micro": round(sum(succ) / len(succ), 3),
        "SR_macro": round(sum(sum(v) / len(v) for v in by_task.values())
                          / len(by_task), 3),
        "SR_by_suite": {su: round(sum(v) / len(v), 3)
                        for su, v in sorted(by_suite.items())},
        "turns_mean": round(sum(turns) / len(turns), 1),
        "wall_mean_s": round(sum(walls) / len(walls), 1),
    }


def paired_sr(rows_a, rows_b):
    """Paired flips / McNemar / bootstrap CIs for arm_b minus arm_a."""
    common = sorted(set(rows_a) & set(rows_b))
    va = {k: rows_a[k]["result"] == "success" for k in common}
    vb = {k: rows_b[k]["result"] == "success" for k in common}
    b = sum(1 for k in common if vb[k] and not va[k])   # a-fail b-success
    c = sum(1 for k in common if va[k] and not vb[k])
    diff = (sum(vb.values()) - sum(va.values())) / len(common) if common \
        else None
    by_task = collections.defaultdict(list)
    for k in common:
        by_task[k[:2]].append(float(vb[k]) - float(va[k]))
    return {
        "n_pairs": len(common),
        "flips_a_only_success": c, "flips_b_only_success": b,
        "diff_micro": round(diff, 3) if diff is not None else None,
        "mcnemar_p": round(mcnemar_exact(b, c), 5)
        if mcnemar_exact(b, c) is not None else None,
        "ci95_micro": [round(x, 3) for x in paired_boot(common, va, vb)]
        if common else None,
        "ci95_macro_cluster": [round(x, 3) for x in macro_boot(by_task)]
        if by_task else None,
    }


# ---------------------------------------------------------------- triggers

def trigger_stats(arm, rows, moments_cache):
    """Precision / recall / false-recall per arm (§6 mechanism metrics).

    Classed arms (v1/progress) align same-family within a 0..3-turn window
    (frozen Stage B/C convention). T2/T3 fires carry no symptom class by
    design, so their alignment/coverage ignore the class family — reported
    as `prec_agnostic` alongside the strict per-family numbers.
    """
    tot_mom = covered = covered_any = tot_fire = aligned = aligned_any = 0
    per_ep_fires = per_ep_unnec = []
    phase_unnec = collections.Counter()
    for k, r in sorted(rows.items()):
        ep = Path(r["dir"]).name
        if ep not in moments_cache:
            moments_cache[ep] = c2.corrected_moments(Path(r["dir"]))
        mom = moments_cache[ep]
        fires = ep_events(r)
        per_ep_fires.append(len(fires))
        tot_fire += len(fires)
        unnec = 0
        for e in fires:
            cls = cls_of(arm, e)
            aligned_any += any(0 <= e["turn"] - t <= 3 for t, _a, c in mom)
            if cls is None:
                aligned += any(0 <= e["turn"] - t <= 3
                               for t, _a, c in mom)
            else:
                aligned += sb._aligns(e["turn"], cls, mom)
            ok = any(0 <= e["turn"] - t <= 3 and sb._same_family(cls, c)
                     for t, _a, c in mom) if cls is not None else \
                any(0 <= e["turn"] - t <= 3 for t, _a, c in mom)
            if not ok:
                unnec += 1
                phase_unnec[PHASE_BUCKET.get(e.get("phase", ""),
                                             "unknown")] += 1
        per_ep_unnec.append(unnec)
        for t, _a, cls in mom:
            tot_mom += 1
            covered_any += any(0 <= e["turn"] - t <= 3 for e in fires)
            covered += any(cls_of(arm, e) is not None and
                           0 <= e["turn"] - t <= 3 and
                           sb._same_family(cls_of(arm, e), cls)
                           for e in fires)
    n = len(rows)
    return {
        "episodes": n,
        "should_moments": tot_mom,
        "recall_strict": round(covered / tot_mom, 3) if tot_mom else None,
        "recall_agnostic": round(covered_any / tot_mom, 3)
        if tot_mom else None,
        "fires": tot_fire,
        "fires_per_ep": round(tot_fire / n, 2) if n else None,
        "precision": round(aligned / tot_fire, 3) if tot_fire else None,
        "false_recall_per_ep": round(sum(per_ep_unnec) / n, 3)
        if n else None,
        "unnecessary_by_phase": dict(phase_unnec),
    }


def ranking_stats(arm, rows, moments_cache):
    """relevant@1/@3 / irrelevant@3 / irrelevant-injection-per-ep.

    Same frozen Stage C pipeline: gold ids only for class-aligned fires
    (annotate_gold_arm), hard-negative = predicate fire on failed episode.
    T2/T3 have no class -> gold annotation impossible; returns None fields.
    """
    if arm in CLASS_AGNOSTIC:
        return {"note": "class-agnostic trigger: no gold annotation"}
    events = {}
    for k, r in sorted(rows.items()):
        ep = Path(r["dir"]).name
        if ep not in moments_cache:
            moments_cache[ep] = c2.corrected_moments(Path(r["dir"]))
        evs = ep_events(r)
        if evs:
            events[ep] = evs
    cls_fn = lambda e: cls_of(arm, e)  # noqa: E731
    sc.annotate_gold_arm(events, moments_cache, cls_fn)
    rl = sc.ranking_layer(events)
    # irrelevant injection / episode: an injection that carried no relevant
    # card = unnecessary fire OR aligned-but-gold-missing-from-top3
    irr = 0
    tot = 0
    for ep, evs in events.items():
        for e in evs:
            tot += 1
            gold = e.get("gold_memory_ids")
            if gold is None or (gold and not set(e["top3_memories"])
                                & set(gold)):
                irr += 1
    n = len(rows)
    lats = [e.get("retrieval_latency_ms") or 0
            for evs in events.values() for e in evs]
    return {
        **{k: v for k, v in rl.items()},
        "irrelevant_injection_per_ep": round(irr / n, 3) if n else None,
        "injections_per_ep": round(tot / n, 2) if n else None,
        "latency_mean_ms": round(sum(lats) / len(lats), 2) if lats else None,
    }


# ---------------------------------------------------------------- stages

def analyze_g1(rows, mc):
    arms = ["M0", "M1", "M2"]
    out = {"sr": {}, "pairs": {}, "trigger": {}, "ranking": {},
           "per_task": {}, "infra": {}}
    for a in arms:
        rr, infra = arm_rows(rows, a)
        out["sr"][a] = sr_stats(rr)
        out["infra"][a] = len(infra)
        out["trigger"][a] = trigger_stats(a, rr, mc)
        out["ranking"][a] = ranking_stats(a, rr, mc)
        per = {}
        for su, t in {(k[0], k[1]) for k in rr}:
            rs = [r for k, r in rr.items() if k[0] == su and k[1] == t]
            per[f"{su}_t{t}"] = round(
                sum(1 for r in rs if r["result"] == "success") / len(rs), 2)\
                if rs else None
        out["per_task"][a] = per
    for a, b in (("M1", "M2"), ("M0", "M2"), ("M0", "M1")):
        ra, _ = arm_rows(rows, a)
        rb, _ = arm_rows(rows, b)
        out["pairs"][f"{a}_vs_{b}"] = paired_sr(ra, rb)
    return out


def analyze_g2(rows, mc):
    out = {"trigger": {}, "ranking": {}, "sr": {}}
    for a in ["T0", "T1", "T2", "T3", "T4"]:
        rr, _ = arm_rows(rows, a)
        out["trigger"][a] = trigger_stats(a, rr, mc)
        out["ranking"][a] = ranking_stats(a, rr, mc)
        out["sr"][a] = sr_stats(rr)
    return out


def analyze_g3(rows, mc):
    out = {"cells": {}, "sr": {}, "effects": {}, "ranking": {}}
    armdata = {}
    for a in ["A", "B", "C", "D"]:
        rr, _ = arm_rows(rows, a, subset=True)
        armdata[a] = rr
        out["sr"][a] = sr_stats(rr)
        out["ranking"][a] = ranking_stats(a, rr, mc)
        out["cells"][a] = len(rr)
    for a, b in (("A", "B"), ("A", "C"), ("A", "D"), ("C", "D"),
                 ("B", "D")):
        out["effects"][f"{a}_vs_{b}"] = paired_sr(armdata[a], armdata[b])
    # Timing Effect (mean Progress-NAive across retrievers) vs Ranking
    # Effect (mean Strong-Lexical across triggers), paired bootstrap CIs.
    common = sorted((set(armdata["A"]) & set(armdata["B"])
                     & set(armdata["C"]) & set(armdata["D"])))

    def v(a, k):
        return armdata[a][k]["result"] == "success"

    if common:
        tim = {k: float(v("C", k)) - float(v("A", k))
               + float(v("D", k)) - float(v("B", k)) for k in common}
        rnk = {k: float(v("B", k)) - float(v("A", k))
               + float(v("D", k)) - float(v("C", k)) for k in common}
        # each dict holds the SUM of the two simple effects (mean = /2)
        out["effects"]["timing_vs_ranking"] = {
            "n_cells": len(common),
            "timing_effect": round(sum(tim.values()) / len(common) / 2, 3),
            "ranking_effect": round(sum(rnk.values()) / len(common) / 2, 3),
            "timing_ci95": [round(x / 2, 3) for x in paired_boot(
                common, {k: 0.0 for k in common}, tim)],
            "ranking_ci95": [round(x / 2, 3) for x in paired_boot(
                common, {k: 0.0 for k in common}, rnk)],
        }
    return out


def analyze_g4(rows, mc):
    out = {"by_trigger": {}, "ranking": {}}
    groups = {"NAIVE": ["N1X", "N2X", "NMX"],
              "PROGRESS": ["P1X", "P2X", "PMX"]}
    for trig, arms in groups.items():
        out["by_trigger"][trig] = {}
        for a in arms:
            rr, _ = arm_rows(rows, a, subset=True)
            out["by_trigger"][trig][a] = sr_stats(rr)
            out["by_trigger"][trig][a]["bank_size"] = \
                122 if "2X" in a else (127 if "MX" in a else 61)
            out["ranking"][a] = ranking_stats(a, rr, mc)
    return out


# ---------------------------------------------------------------- writers

def write_stage_csv(rows, stage, path):
    """Per-episode deliverable table for one stage."""
    fieldnames = ["arm", "stage", "cond", "suite", "task", "seed", "result",
                  "success", "infra", "turns", "wall_s", "fires", "unnec",
                  "aligned", "moments", "latency_mean_ms", "top1s"]
    out = []
    for arm, (st, cond) in sorted(ARMS.items()):
        if st != stage:
            continue
        for (stg, c, su, t, s), r in rows.items():
            if stg != stage or c != cond:
                continue
            evs = ep_events(r)
            mc = {}
            ep = Path(r["dir"]).name
            mc[ep] = c2.corrected_moments(Path(r["dir"]))
            mom = mc[ep]
            unnec = aligned = 0
            for e in evs:
                cls = cls_of(arm, e)
                ok = (any(0 <= e["turn"] - t2 <= 3 for t2, _a, _c in mom)
                      if cls is None else
                      sb._aligns(e["turn"], cls, mom))
                aligned += bool(ok)
                unnec += not ok
            lats = [e.get("retrieval_latency_ms") or 0 for e in evs]
            out.append({
                "arm": arm, "stage": stg, "cond": c, "suite": su,
                "task": t, "seed": s, "result": r["result"],
                "success": int(r["result"] == "success"),
                "infra": int(r["result"] in INFRA),
                "turns": ep_turns(r), "wall_s": r["wall_s"],
                "fires": len(evs), "unnec": unnec, "aligned": aligned,
                "moments": len(mom),
                "latency_mean_ms": round(sum(lats) / len(lats), 1)
                if lats else "",
                "top1s": ";".join(str(e.get("top1_memory", ""))
                                  for e in evs),
            })
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(sorted(out, key=lambda r: (r["arm"], r["suite"],
                                               r["task"], r["seed"])))
    return len(out)


def write_summary_md(res, rows):
    p = REPO / "analysis" / "stageG_summary.md"
    L = ["# Stage G — CVPR Validation: Progress-Gated Procedural Recall",
         "", f"_generated {__import__('datetime').datetime.now():%F %T}_",
         ""]
    if "g1" in res:
        L += ["## TABLE 1 (G1 cross-suite, 3 arms x 145 cells)", "",
              "| arm | n | SR micro | SR macro | by-suite object/goal/10 | "
              "turns | wall_s | fires/ep | prec | false-recall/ep | irr "
              "inj/ep | relevant@3 | infra |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for a in ("M0", "M1", "M2"):
            s, t, k = res["g1"]["sr"][a], res["g1"]["trigger"][a], \
                res["g1"]["ranking"][a]
            L.append(
                f"| {a} | {s.get('n', 0)} | {s.get('SR_micro')} | "
                f"{s.get('SR_macro')} | {'/'.join(str(v) for v in s.get('SR_by_suite', {}).values())} | "
                f"{s.get('turns_mean')} | {s.get('wall_mean_s')} | "
                f"{t.get('fires_per_ep')} | {t.get('precision')} | "
                f"{t.get('false_recall_per_ep')} | "
                f"{k.get('irrelevant_injection_per_ep')} | "
                f"{k.get('relevant@3')} | {res['g1']['infra'][a]} |")
        L += ["", "### paired (b − a)", "",
              "| pair | n | a-only | b-only | diff | McNemar p | CI95 micro "
              "| CI95 macro(cluster) |", "|---|---|---|---|---|---|---|---|"]
        for pair, d in res["g1"]["pairs"].items():
            L.append(f"| {pair} | {d['n_pairs']} | "
                     f"{d['flips_a_only_success']} | "
                     f"{d['flips_b_only_success']} | {d['diff_micro']} | "
                     f"{d['mcnemar_p']} | {d['ci95_micro']} | "
                     f"{d['ci95_macro_cluster']} |")
    if "g2" in res:
        L += ["", "## TABLE 2 (G2 trigger baselines, mechanism focus)", "",
              "| arm | prec | false-recall/ep | recall strict | recall "
              "agnostic | fires/ep | unnecessary by phase |", "|---|---|---|---|---|---|---|"]
        for a in ("T0", "T1", "T2", "T3", "T4"):
            t = res["g2"]["trigger"][a]
            L.append(f"| {a} | {t.get('precision')} | "
                     f"{t.get('false_recall_per_ep')} | "
                     f"{t.get('recall_strict')} | {t.get('recall_agnostic')}"
                     f" | {t.get('fires_per_ep')} | "
                     f"{t.get('unnecessary_by_phase')} |")
    if "g3" in res:
        L += ["", "## TABLE 3 (G3 Timing x Ranking 2x2, 45 cells/arm)", "",
              "| arm | n | SR micro | relevant@3 | irr inj/ep |",
              "|---|---|---|---|---|"]
        for a in ("A", "B", "C", "D"):
            s = res["g3"]["sr"][a]
            k = res["g3"]["ranking"][a]
            L.append(f"| {a} | {s.get('n', 0)} | {s.get('SR_micro')} | "
                     f"{k.get('relevant@3')} | "
                     f"{k.get('irrelevant_injection_per_ep')} |")
        tvr = res["g3"]["effects"].get("timing_vs_ranking")
        if tvr:
            L += ["", f"Timing Effect {tvr['timing_effect']} CI95 "
                 f"{tvr['timing_ci95']}; Ranking Effect "
                 f"{tvr['ranking_effect']} CI95 {tvr['ranking_ci95']} "
                 f"(n={tvr['n_cells']})"]
    if "g4" in res:
        L += ["", "## TABLE 4 (G4 memory-scale, real distractors, 45 "
              "cells/arm)", "",
              "| trigger | bank | n | SR micro | fires/ep | irr inj/ep | "
              "relevant@3 | latency ms |", "|---|---|---|---|---|---|---|---|"]
        for trig, arms in (("NAIVE", ("N1X", "N2X", "NMX")),
                           ("PROGRESS", ("P1X", "P2X", "PMX"))):
            for a in arms:
                s = res["g4"]["by_trigger"][trig][a]
                k = res["g4"]["ranking"][a]
                L.append(f"| {trig} | {s.get('bank_size')} | {s.get('n', 0)}"
                         f" | {s.get('SR_micro')} | "
                         f"{k.get('injections_per_ep')} | "
                         f"{k.get('irrelevant_injection_per_ep')} | "
                         f"{k.get('relevant@3')} | "
                         f"{k.get('latency_mean_ms')} |")
    total = sum(1 for r in rows.values())
    L += ["", f"rows seen (all g-stages, incl. infra): {total}", ""]
    p.write_text("\n".join(L), encoding="utf-8")
    log(f"wrote {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="g1,g2,g3,g4",
                    help="comma list among g1,g2,g3,g4 (analyze what exists)")
    args = ap.parse_args()
    wanted = args.stages.split(",")

    rows = load_rows()
    log(f"loaded {len(rows)} g-stage rows")
    mc = {}  # moments cache shared across arms/stages
    res = {}
    if "g1" in wanted:
        res["g1"] = analyze_g1(rows, mc)
        n = write_stage_csv(rows, "g1",
                            REPO / "analysis" / "stageG_G1_runs.csv")
        log(f"G1 csv rows: {n}")
    if "g2" in wanted:
        res["g2"] = analyze_g2(rows, mc)
        n = write_stage_csv(rows, "g2",
                            REPO / "analysis" / "stageG_G2_runs.csv")
        log(f"G2 csv rows: {n}")
    if "g3" in wanted:
        res["g3"] = analyze_g3(rows, mc)
        n = write_stage_csv(rows, "g3",
                            REPO / "analysis" / "stageG_G3_runs.csv")
        log(f"G3 csv rows: {n}")
    if "g4" in wanted:
        res["g4"] = analyze_g4(rows, mc)
        n = write_stage_csv(rows, "g4",
                            REPO / "analysis" / "stageG_G4_runs.csv")
        log(f"G4 csv rows: {n}")

    outp = REPO / "analysis" / "stageG_results.json"
    json.dump(res, open(outp, "w"), indent=2, ensure_ascii=False,
              default=str)
    log(f"wrote {outp}")
    write_summary_md(res, rows)
    log(json.dumps({k: (list(v.get("sr", {}).get("M0", {}).keys())[:3]
                        if k == "g1" else "ok") for k, v in res.items()}))


if __name__ == "__main__":
    main()
