#!/usr/bin/env python3
"""Stage G0-H causal-audit analyzer (DEV five-arm, pre-registered).

Arms (analysis/stageG0_manifest.md §H), all glm-5.3-flash,
libero_spatial_task x {t3,t5,t9} x s1-10 x r1:

  A v1_original+native    = REUSE stage memB / cond memB2 (30 rows)
  B v1_per_result+native  = stage g0 / cond g0B
  C progress+native       = REUSE stage memC / cond memO2 (27 valid)
  D v1_per_result+common  = stage g0 / cond g0D
  E progress+common       = stage g0 / cond g0E

Contrasts: A->B buffering only; B->C rule content only; B->D / C->E query
composition only. Stats (McNemar exact, paired bootstrap 10k seed 20260920,
macro cluster CI) reuse scripts/analyze_memory_stageG.py verbatim — no new
methodology is introduced at analysis time.

Usage: python scripts/analyze_memory_stageG0.py
Writes: analysis/stageG0_results.json + analysis/stageG0_results.md
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import analyze_memory_stageB as sb  # noqa: E402
import analyze_memory_stageC as sc  # noqa: E402
import memory_stagec2_benchmark as c2  # noqa: E402
from analyze_memory_stageG import (  # noqa: E402
    ep_events, ep_turns, macro_boot, mcnemar_exact, paired_boot,
)

TIER = "glm-5.3-flash"
SUITE = "libero_spatial_task"
TASKS = (3, 5, 9)
SEEDS = range(1, 11)
INFRA = ("infra_crash", "infra_timeout", "infra_missing")

G0_ARMS = {
    "A": ("memB", "memB2"),
    "B": ("g0", "g0B"),
    "C": ("memC", "memO2"),
    "D": ("g0", "g0D"),
    "E": ("g0", "g0E"),
}
# symptom class per trigger FAMILY (query mode does not change the class)
PROGRESS_FAMILY = {"C", "E"}

CONTRASTS = [("A", "B"), ("B", "C"), ("B", "D"), ("C", "E"), ("A", "E"),
             ("A", "C")]


def log(msg):
    print(msg, flush=True)


def load_g0_rows():
    """rows[(stage,cond,suite,task,seed)] for the three source stages."""
    rows = {}
    for r in sb.csv_dict():
        if r["tier"] != TIER or int(r["repeat"]) != 1:
            continue
        if r["stage"] not in ("memB", "memC", "g0"):
            continue
        if r["suite"] != SUITE or int(r["task"]) not in TASKS:
            continue
        if int(r["seed"]) not in SEEDS:
            continue
        k = (r["stage"], r["cond"], r["suite"], int(r["task"]),
             int(r["seed"]))
        # keep the LATEST row per cell (memB0 supplement overlaps armA
        # t9 — irrelevant here; memB2/memO2/g0* conds are unique per cell)
        rows[k] = r
    return rows


def arm_rows(rows, arm):
    stage, cond = G0_ARMS[arm]
    out, infra = {}, collections.Counter()
    for (st, c, su, t, s), r in rows.items():
        if st != stage or c != cond:
            continue
        if r["result"] in INFRA:
            infra[(t, s)] = r["result"]
            continue
        out[(t, s)] = r
    return out, infra


# ------------------------------------------------------------- cls / moments
def cls_of_event(arm, e):
    if arm in PROGRESS_FAMILY:
        return sc.o2_cls_of_event(e)
    return c2.t0_fire_class(e.get("trigger_reason", ""))


def corrected_moments(r, cache):
    ep = Path(r["dir"]).name
    if ep not in cache:
        cache[ep] = c2.corrected_moments(Path(r["dir"]))
    return cache[ep]


# ---------------------------------------------------------------- stats
def sr_stats(cells):
    rs = list(cells.values())
    if not rs:
        return {"n": 0}
    by_task = collections.defaultdict(list)
    for (t, s), r in cells.items():
        by_task[t].append(r["result"] == "success")
    turns = [ep_turns(r) for r in rs]
    return {
        "n": len(rs),
        "SR_micro": round(sum(r["result"] == "success" for r in rs)
                          / len(rs), 3),
        "SR_macro": round(sum(sum(v) / len(v) for v in by_task.values())
                          / len(by_task), 3),
        "SR_by_task": {t: round(sum(v) / len(v), 3)
                       for t, v in sorted(by_task.items())},
        "turns_mean": round(sum(turns) / len(turns), 1),
    }


def paired_sr(ra, rb):
    common = sorted(set(ra) & set(rb))
    va = {k: ra[k]["result"] == "success" for k in common}
    vb = {k: rb[k]["result"] == "success" for k in common}
    b = sum(1 for k in common if vb[k] and not va[k])
    c = sum(1 for k in common if va[k] and not vb[k])
    diff = (sum(vb.values()) - sum(va.values())) / len(common) if common \
        else None
    by_task = collections.defaultdict(list)
    for k in common:
        by_task[k[0]].append(float(vb[k]) - float(va[k]))
    p = mcnemar_exact(b, c)
    return {
        "n_pairs": len(common),
        "flips_a_only_success": c, "flips_b_only_success": b,
        "diff_micro": round(diff, 3) if diff is not None else None,
        "mcnemar_p": round(p, 5) if p is not None else None,
        "ci95_micro": [round(x, 3) for x in paired_boot(common, va, vb)]
        if common else None,
        "ci95_macro_cluster": [round(x, 3) for x in macro_boot(by_task)]
        if by_task else None,
    }


def trigger_stats(arm, rows, mcache):
    tot_mom = covered = covered_any = tot_fire = aligned = aligned_any = 0
    per_ep_fires, per_ep_false = [], []
    phase_false = collections.Counter()
    for k, r in sorted(rows.items()):
        mom = corrected_moments(r, mcache)
        fires = ep_events(r)
        per_ep_fires.append(len(fires))
        tot_fire += len(fires)
        n_false = 0
        for e in fires:
            cls = cls_of_event(arm, e)
            near = [c for t, _a, c in mom if 0 <= e["turn"] - t <= 3]
            aligned_any += bool(near)
            aligned += bool(near) if cls is None \
                else sb._aligns(e["turn"], cls, mom)
            ok = (any(sb._same_family(cls, c) for c in near)
                  if cls is not None else bool(near))
            if not ok:
                n_false += 1
                phase_false[e.get("phase") or "unknown"] += 1
        per_ep_false.append(n_false)
        for t, _a, cls in mom:
            tot_mom += 1
            covered_any += any(0 <= e["turn"] - t <= 3 for e in fires)
            covered += any(cls_of_event(arm, e) is not None
                           and 0 <= e["turn"] - t <= 3
                           and sb._same_family(cls_of_event(arm, e), cls)
                           for e in fires)
    n = len(rows)
    return {
        "episodes": n,
        "should_moments": tot_mom,
        "recall_strict": round(covered / tot_mom, 3) if tot_mom else None,
        "recall_agnostic": round(covered_any / tot_mom, 3) if tot_mom
        else None,
        "fires": tot_fire,
        "fires_per_ep": round(tot_fire / n, 2) if n else None,
        "precision": round(aligned / tot_fire, 3) if tot_fire else None,
        "false_per_ep": round(sum(per_ep_false) / n, 3) if n else None,
        "false_by_phase": dict(phase_false),
    }


def retrieval_stats(arm, rows, mcache):
    """relevant@k + EMPTY-rate + count (G0-E attempt logging fields)."""
    events = {}
    for k, r in sorted(rows.items()):
        evs = ep_events(r)
        if evs:
            events[Path(r["dir"]).name] = evs
    cls_fn = lambda e: cls_of_event(arm, e)  # noqa: E731
    sc.annotate_gold_arm(events, mcache, cls_fn)
    rl = sc.ranking_layer(events)
    empties = total = 0
    for evs in events.values():
        for e in evs:
            total += 1
            if e.get("retrieval_empty") is not None:
                empties += bool(e["retrieval_empty"])
            else:                            # historical rows (arm A)
                empties += not e.get("top3_memories")
    n = len(rows)
    return {
        **{k: v for k, v in rl.items()},
        "retrieval_count_per_ep": round(total / n, 2) if n else None,
        "retrieval_empty_rate": round(empties / total, 3) if total else None,
    }


# ---------------------------------------------------------------- main
def main():
    rows = load_g0_rows()
    mcache = {}
    res = {"arms": {}, "contrasts": {}, "infra": {}}
    for arm in G0_ARMS:
        rr, infra = arm_rows(rows, arm)
        res["arms"][arm] = {
            "label": G0_ARMS[arm],
            "n_rows": len(rr),
            "infra": {f"t{t}_s{s}": v for (t, s), v in sorted(
                infra.items())},
            "sr": sr_stats(rr),
            "trigger": trigger_stats(arm, rr, mcache),
            "retrieval": retrieval_stats(arm, rr, mcache),
        }
        log(f"arm {arm} {G0_ARMS[arm]}: n={len(rr)} "
            f"SR={res['arms'][arm]['sr'].get('SR_micro')}")
    for a, b in CONTRASTS:
        ra, _ = arm_rows(rows, a)
        rb, _ = arm_rows(rows, b)
        res["contrasts"][f"{a}->{b}"] = paired_sr(ra, rb)
        log(f"contrast {a}->{b}: {res['contrasts'][f'{a}->{b}']}")

    # ---- §I gates (numbers only; verdict doc is written by hand after
    # review, this prints the pre-registered quantities)
    b_c = res["contrasts"].get("B->C", {})
    d_e = res["contrasts"].get("D->E", {})
    gates = {
        "gate1_mechanism_C_vs_B": {
            "rule": "progress SR gain vs v1_per_result > 0 (diff_micro or "
                    "paired flips b>c)",
            "diff_micro": b_c.get("diff_micro"),
            "flips_b_only(C)": b_c.get("flips_b_only_success"),
            "flips_c_only(B)": b_c.get("flips_a_only_success"),
        },
        "gate2_common_query_E_vs_D": {
            "rule": "progress advantage not fully gone under common query "
                    "(E vs D diff_micro > 0, or flips favor E)",
            "diff_micro": d_e.get("diff_micro"),
            "flips_e_only": d_e.get("flips_b_only_success"),
            "flips_d_only": d_e.get("flips_a_only_success"),
            "note": "manifest pairs this as C->E removing the query "
                    "confound within progress; E vs D is the WHEN contrast "
                    "under common query",
        },
        "gate2b_progress_query_cost_C_vs_E": {
            "diff_micro": res["contrasts"].get("C->E", {}).get("diff_micro"),
            "note": "common query's cost inside the progress family",
        },
        "gate3_q3_regression": "see scripts/test_stageG0_audit.py "
                               "(must be green at verdict time)",
        "gate4_mstuck": "see scripts/test_stageG0_audit.py §D",
    }
    res["gates"] = gates

    (REPO / "analysis" / "stageG0_results.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str))

    md = ["# Stage G0 — DEV five-arm causal audit results\n",
          "_generated by scripts/analyze_memory_stageG0.py; arms/grids/"
          "contrasts pre-registered in stageG0_manifest.md BEFORE the run._\n",
          "## TABLE 1 — arms\n",
          "| arm | trigger | query | n | SR micro | SR macro | fires/ep | "
          "prec | recall strict | empty rate | ret/ep |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    names = {"A": "v1_original", "B": "v1_per_result", "C": "progress",
             "D": "v1_per_result", "E": "progress"}
    qm = {"A": "native", "B": "native", "C": "native", "D": "common",
          "E": "common"}
    for arm in G0_ARMS:
        d = res["arms"][arm]
        s, tg, rt = d["sr"], d["trigger"], d["retrieval"]
        md.append(
            f"| {arm} | {names[arm]} | {qm[arm]} | {d['n_rows']} | "
            f"{s.get('SR_micro')} | {s.get('SR_macro')} | "
            f"{tg.get('fires_per_ep')} | {tg.get('precision')} | "
            f"{tg.get('recall_strict')} | {rt.get('retrieval_empty_rate')} "
            f"| {rt.get('retrieval_count_per_ep')} |")
    md += ["\nSR by task: " + json.dumps(
        {a: res["arms"][a]["sr"].get("SR_by_task") for a in G0_ARMS},
        ensure_ascii=False), "",
           "infra (excluded, counted openly): " + json.dumps(
               {a: len(res["arms"][a]["infra"]) for a in G0_ARMS}), "",
           "## TABLE 2 — pre-registered contrasts (b minus a)\n",
           "| contrast | n | diff micro | b-only succ | a-only succ | "
           "McNemar p | CI95 micro | CI95 macro |",
           "|---|---|---|---|---|---|---|---|"]
    for k, v in res["contrasts"].items():
        md.append(f"| {k} | {v['n_pairs']} | {v['diff_micro']} | "
                  f"{v['flips_b_only_success']} | "
                  f"{v['flips_a_only_success']} | {v['mcnemar_p']} | "
                  f"{v['ci95_micro']} | {v['ci95_macro_cluster']} |")
    md += ["\n## TABLE 3 — trigger mechanism\n",
           "| arm | should moments | recall strict | recall agnostic | "
           "precision | false/ep | false by phase |",
           "|---|---|---|---|---|---|---|"]
    for arm in G0_ARMS:
        tg = res["arms"][arm]["trigger"]
        fbp = json.dumps(tg.get("false_by_phase"), ensure_ascii=False)
        md.append(f"| {arm} | {tg.get('should_moments')} | "
                  f"{tg.get('recall_strict')} | {tg.get('recall_agnostic')} "
                  f"| {tg.get('precision')} | {tg.get('false_per_ep')} | "
                  f"{fbp} |")
    md += ["\n## TABLE 4 — retrieval quality\n",
           "| arm | relevant@1 | relevant@3 | irrelevant@3 | ret/ep | "
           "empty rate |", "|---|---|---|---|---|---|"]
    for arm in G0_ARMS:
        rt = res["arms"][arm]["retrieval"]
        md.append(f"| {arm} | {rt.get('relevant@1')} | "
                  f"{rt.get('relevant@3')} | "
                  f"{rt.get('irrelevant@3')} | "
                  f"{rt.get('retrieval_count_per_ep')} | "
                  f"{rt.get('retrieval_empty_rate')} |")
    md += ["\n## §I gate quantities\n",
           "```json", json.dumps(gates, indent=2, ensure_ascii=False),
           "```", "",
           "Gates 3/4 = scripts/test_stageG0_audit.py §C/§D must be green "
           "at verdict time. Verdict: analysis/stageG0_verdict.md."]
    (REPO / "analysis" / "stageG0_results.md").write_text(
        "\n".join(md), encoding="utf-8")
    log("wrote analysis/stageG0_results.{json,md}")


if __name__ == "__main__":
    main()
