#!/usr/bin/env python3
"""P1 L1 Task9 D-only CONDITIONAL discriminability (pre-specified 19 rows).

Question: after conditioning on task9 AND gate pattern 011, do frozen legal
terminal scores distinguish 11 exit-positive vs 8 transient FGONLY proxies?
This is a conditional analysis, not a new online policy or a grasp verifier.

Scores: same fixed arms in p1_return_time_triage_lab, no fitting or search.
Evaluate fixed k=4 (20%) and k=8 (40%) within the 19-row subgroup.
Quantify null via exact hypergeometric tail for observed binary hit count at
fixed k (if no ties) and a 10,000-label-permutation Monte Carlo diagnostic
for continuous score rankings. Also run leave-one-episode-out ranges.

Caveats: conditional subgroup was identified from earlier results; all p-values
are exploratory, not independent confirmation, and FGONLY exit is a
same-skill kinematic proxy, not a physical held/contact reference.
No private samples, raw poses, IDs, paths or case-level scores are output.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import ROOT
from p1_return_time_triage_lab import build_rows, priority, topk_expected

PROTOCOL="RPENT_P1_T9_DONLY_CONDITIONAL_DISCRIMINATION_V1"
OUT=ROOT/"artifacts"/"p1_return_time_triage_lab"
ARMS=("UNTARGETED","PEAK_LIFT","FINAL_GAP","LIFT_MINUS_GAP","D_ONLY_THEN_LIFT")
BUDGETS=(4,8)
SEED=20261010
N_PERM=10000

def task9_donly(rows):
    sub=[r for r in rows if r["task"]=="9" and r["legal"]["gate_pattern"]=="011"]
    if len(sub)!=19 or sum(r["exit_proxy_positive"] for r in sub)!=11:
        raise ValueError("Frozen Task9 D-only 19/11 cohort mismatch")
    return sub

def score_k(rows,arm,k):
    if not rows or not 0<k<=len(rows):
        raise ValueError("Invalid top-k")
    return topk_expected(rows,arm,k/len(rows))["expected_selected_proxy_positive"]

def permutation_test(rows,arm,k,repeats=N_PERM,seed=SEED):
    """Fixed ranks, permuted audit labels. No score fitting.

    One-sided >= expected selected positives. For tied score groups,
    topk_expected uses fractional selection rather than unstable row IDs.
    """
    actual=score_k(rows,arm,k)
    rng=random.Random(seed)
    labels=[r["exit_proxy_positive"] for r in rows]
    count=0
    for _ in range(repeats):
        shuffled=labels[:]
        rng.shuffle(shuffled)
        sample=[{**r,"exit_proxy_positive":y}
                for r,y in zip(rows,shuffled)]
        val=score_k(sample,arm,k)
        if val>=actual-1e-8:
            count+=1
    return {"observed_proxy_positives":actual,
            "random_expected_proxy_positives":round(k*sum(labels)/len(rows),6),
            "n_permutations":repeats,
            "one_sided_permutation_p_exploratory":round((count+1)/(repeats+1),5)}

def leave_episode_out(rows,arm,k):
    by_ep=defaultdict(list)
    for i,r in enumerate(rows):
        by_ep[r["episode_id"]].append(i)
    vals=[]
    for indices in by_ep.values():
        sub=[r for j,r in enumerate(rows) if j not in indices]
        if len(sub)<k:continue
        vals.append(score_k(sub,arm,k)/k)
    return {
        "n_episodes":len(by_ep),"n_leave_one_out":len(vals),
        "precision_min":round(min(vals),6) if vals else None,
        "precision_max":round(max(vals),6) if vals else None,
        "precision_full":round(score_k(rows,arm,k)/k,6),
    }

def evaluate(rows):
    sub=task9_donly(rows)
    result={
        "protocol":PROTOCOL,
        "reference":"EXIT_TIME_FGONLY_KINEMATIC_PROXY_NOT_HELD_TRUTH",
        "cohort":"TASK9_AND_PATTERN_011_AND_ORIGINAL_PICK_FALSE",
        "n":len(sub),"positive":11,"negative":8,
        "n_episodes":len({r["episode_id"] for r in sub}),
        "budgets":{},
        "limitations":[
          "The 19-row subgroup was discovered during prior L1 research: exploratory, not confirmatory p-values",
          "Reference remains FGONLY exit-time within-skill kinematics, not grasp truth",
          "One-sided permutation null is exchangeability within already-selected subgroup, not random assigned action effects",
          "At n=19 Monte Carlo precision is coarse and power is weak",
          "Task ID is used to identify an offline diagnostic subgroup, not passed to priority()",
          "No new simulator, training, future evaluation, online policy or action",
        ],
    }
    for k in BUDGETS:
        result["budgets"][str(k)]={
            arm:{
                "topk":topk_expected(sub,arm,k/len(sub)),
                "label_permutation":permutation_test(sub,arm,k),
                "leave_episode_out":leave_episode_out(sub,arm,k),
            } for arm in ARMS
        }
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    if not a.out.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        p.error("Output must remain under gitignored artifacts/")
    rows=build_rows()
    result=evaluate(rows)
    a.out.mkdir(parents=True,exist_ok=True)
    file=a.out/"task9_conditional_v1.json"
    file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"protocol":result["protocol"],"n":result["n"],
      "n_episodes":result["n_episodes"],"budgets":result["budgets"],
      "report_path":str(file),
      "limit":"Exploratory FGONLY proxy discriminability; no independent grasp truth"},
       ensure_ascii=False,indent=2))

if __name__=="__main__":main()
