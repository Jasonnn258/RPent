#!/usr/bin/env python3
"""P1 L1 label-blind budget allocation over frozen 103 tool failures.

Motivation: prior "task×gate-matched 14.48/21" is a RETROSPECTIVE
standardization control, holding the original LMG score's selected cell
quotas fixed. It is NOT a separately deployable zero-fitted policy.

Here we define genuinely explicit, label-blind batch allocators:
  GATE_ONLY (existing comparator): globally prefer gate pattern 011
  TASK_EQUAL_GATE:  equal slots per 3 tasks, gate011-first inside each task
  TASK_PROP_GATE:   quotas proportional to candidate pool n/task, same gate
  RANDOM:           all cases tied
  LMG_FROZEN:       pre-existing continuous-score comparator.

Task identity is included from A0 reconstruction metadata. The runtime
decision-time availability/legal status of a task ID and the availability
of a complete batch queue have NOT been proven. Treat TASK_* as offline
batch-allocation designs, not legitimate online policies until verified.

All selectors take ONLY task/group or frozen legal tool diagnostics; audit
FGONLY reference is read ONLY after weights are fixed for scoring.
No case IDs or individual scores/labels in outputs. No fitting, new rollouts,
physical control or L2. Frozen data/analysis remain unchanged.

Run tests then:
 python3 analysis/research_context/p1_label_blind_quota_lab.py
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import ROOT, SRC
from p1_return_time_triage_lab import build_rows
from p1_triage_incremental_lab import select_weights

PROTOCOL = "RPENT_P1_LABEL_BLIND_BATCH_QUOTA_L1_V1"
OUT = ROOT / "artifacts" / "p1_return_time_triage_lab"
BUDGETS = (.20, .40)
METHODS = ("RANDOM", "GATE_ONLY", "TASK_EQUAL_GATE",
           "TASK_PROP_GATE", "LMG_FROZEN")

def hamilton_quota(capacities, k, mode):
    """Explicit largest-remainder allocation, label/score-free.

    Predeclared deterministic tie handling by *task name* applies only to
    slot COUNTS. Within a tied-score task/gate cell, selection is uniform
    expectation and never uses episode IDs.
    """
    tasks = sorted(capacities)
    if not tasks or any(type(capacities[t]) is not int or
                        capacities[t] < 0 for t in tasks):
        raise ValueError("Invalid capacities")
    if type(k) is not int or k < 0 or k > sum(capacities.values()):
        raise ValueError("Invalid quota budget")
    if mode not in ("equal", "proportional"):
        raise ValueError("Invalid quota mode")
    if k == 0:
        return {t: 0 for t in tasks}
    # Equal quotas are water-filled under capacity caps; proportional
    # quotas use remaining feasible capacities after each integer floor.
    quotas = {t: 0 for t in tasks}
    while sum(quotas.values()) < k:
        eligible = [t for t in tasks if quotas[t] < capacities[t]]
        if not eligible:
            raise ValueError("Unallocated budget with exhausted cells")
        # Recompute desired average share (equal) or desired proportional
        # total share. This avoids overshooting capacity-constrained tasks.
        if mode == "equal":
            chosen = min(eligible, key=lambda t:(quotas[t],t))
        else:
            total = sum(capacities.values())
            chosen = max(eligible, key=lambda t:(
                k * capacities[t] / total - quotas[t], -tasks.index(t)))
        quotas[chosen] += 1
    if sum(quotas.values()) != k:
        raise AssertionError("Quota mass mismatch")
    return quotas

def _gate_first_weights(rows, indices, k):
    if k < 0 or k > len(indices):
        raise ValueError("Invalid in-cell budget")
    weights = {}
    remain = k
    # This is a fixed, Boolean, decision-visible ranking. No label, score
    # magnitude, episode ID or per-task outcome prevalence is accessed.
    for desired in ("011", "__other__"):
        ids = [i for i in indices if
               (rows[i]["legal"]["gate_pattern"] == "011") ==
               (desired == "011")]
        if not ids:
            continue
        take = min(remain, len(ids))
        if take:
            w = take / len(ids)
            weights.update({i:w for i in ids})
            remain -= take
        if remain == 0:
            break
    if remain:
        raise ValueError("Could not allocate gate-preferring slots")
    return weights

def weights_for(rows, method, ratio):
    if not rows or not 0 < ratio <= 1:
        raise ValueError("Invalid ratio/population")
    n = len(rows)
    k = math.ceil(n * ratio)
    if method == "LMG_FROZEN":
        return select_weights(rows, "LIFT_MINUS_GAP", ratio)
    if method == "RANDOM":
        return [k / n] * n
    if method == "GATE_ONLY":
        w = _gate_first_weights(rows, list(range(n)), k)
        return [w.get(i, 0.) for i in range(n)]
    if method in ("TASK_EQUAL_GATE", "TASK_PROP_GATE"):
        groups = defaultdict(list)
        for i, row in enumerate(rows):
            task = row.get("task")
            if task not in ("3","5","9"):
                raise ValueError("Unrecognized task metadata")
            groups[task].append(i)
        if set(groups) != {"3","5","9"}:
            raise ValueError("Missing task in batch allocation")
        capacities = {t: len(ids) for t,ids in groups.items()}
        quota = hamilton_quota(capacities, k,
                               "equal" if method=="TASK_EQUAL_GATE"
                               else "proportional")
        ws = {}
        for task,ids in groups.items():
            ws.update(_gate_first_weights(rows, ids, quota[task]))
        result = [ws.get(i,0.) for i in range(n)]
    else:
        raise ValueError("Unknown selector")
    if abs(sum(result)-k)>1e-8 or any(not 0<=v<=1 for v in result):
        raise ValueError("Selector violated fixed budget or weight range")
    return result

def report(rows, method, ratio, reference="exit_proxy_positive"):
    if reference not in ("exit_proxy_positive","ever_proxy_positive"):
        raise ValueError("Unapproved evaluation reference")
    if any(type(r.get(reference)) is not bool for r in rows):
        raise ValueError("Invalid audit-side reference")
    w = weights_for(rows, method, ratio)
    k = sum(w)
    y = [r[reference] for r in rows]
    hits = sum(a*bool(b) for a,b in zip(w,y))
    prev = sum(y)/len(rows)
    task_mix = {}
    for task in ("3","5","9"):
        subset=[i for i,r in enumerate(rows) if r["task"]==task]
        task_mix[task]={
            "n":len(subset),
            "allocated_slots":round(sum(w[i] for i in subset),6),
            "expected_proxy_pos":round(sum(w[i]*y[i] for i in subset),6),
            "ref_positive":sum(y[i] for i in subset),
        }
    return {
        "method":method,"reference":reference,"n":len(rows),"k":round(k,6),
        "n_reference_positive":sum(y),
        "expected_proxy_pos":round(hits,6),
        "expected_proxy_neg":round(k-hits,6),
        "precision_at_budget":round(hits/k,6),
        "unconditional_prevalence":round(prev,6),
        "enrichment":round((hits/k)/prev,6) if prev else None,
        "task_mix":task_mix,
    }

def evaluate(rows):
    if (len(rows)!=103 or len({r["episode_id"] for r in rows})!=79 or
        sum(r["exit_proxy_positive"] for r in rows)!=26 or
        sum(r["ever_proxy_positive"] for r in rows)!=56):
        raise ValueError("Frozen 103/79/26/56 denominators changed")
    if dict(Counter(r["task"] for r in rows)) != {"3":21,"5":30,"9":52}:
        raise ValueError("Frozen task distribution changed")
    result={"protocol":PROTOCOL, "status":"L1_OFFLINE_BATCH_ALLOCATION_ONLY",
            "n_tool_failures":103,"n_episodes":79,
            "budget_results":{},
            "method_contract":{
              "GATE_ONLY":"Decision-visible gate 011 first; tie = uniform expectation",
              "TASK_EQUAL_GATE":"Label-blind batch slots equally across named tasks; gate011 first per task",
              "TASK_PROP_GATE":"Label-blind batch slots proportional to observed batch counts; gate011 first per task",
              "RANDOM":"All candidates tied; equal expected selection mass",
              "LMG_FROZEN":"Previously frozen continuous legal score; NOT a newly trained model",
            },
            "limits":[
              "Task metadata comes from A0 reconstruction_metadata, NOT directly from A-online; runtime legal visibility has not been established.",
              "TASK_* need a known pool and batched budget allocation: cannot silently claim online sequential eligibility.",
              "Prior task×gate matched 14.48 positives uses the LMG-selected composition and audit prevalences; it is a retrospective matched control, NOT a separately specified algorithm.",
              "Selection weights are label-blind; labels enter ONLY evaluation at terminal/any FGONLY weak proxy.",
              "This test is repeated on the same 103 retrospective data; no independent cohort, physical held-grasp truth, or causal intervention.",
              "Do not select a top method from these results for deployment; no new L2 simulation authorized.",
            ]}
    for ratio in BUDGETS:
        key=f"top_{round(ratio*100)}pct"
        result["budget_results"][key]={
          method:{
            "terminal":report(rows,method,ratio),
            "anytime":report(rows,method,ratio,"ever_proxy_positive")
          } for method in METHODS
        }
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    if not args.out.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        p.error("Output must stay under private gitignored artifacts")
    rows=build_rows(src=SRC)
    data=evaluate(rows)
    args.out.mkdir(parents=True,exist_ok=True)
    dest=args.out/"label_blind_quota_v1.json"
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                    encoding="utf-8")
    print(json.dumps({"protocol":data["protocol"],
      "n_tool_failures":data["n_tool_failures"],
      "top20_terminal":{name:v["terminal"] for name,v in
          data["budget_results"]["top_20pct"].items()},
      "output":str(dest),
      "status":"No online legal-task claim; batch-only L1 proxy ranking"},
      ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
