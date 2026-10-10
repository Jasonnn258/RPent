#!/usr/bin/env python3
"""P1 L1 incremental-information ablation: how much is the CONTINUOUS
return-time score worth *after conditioning* on its task/gate composition?

This is a retrospective decomposition of the ALREADY fixed and executed
LIFT_MINUS_GAP score; NO new score, policy, threshold, simulation or training.

Question: Top20% exit-FGONLY precision .81 (17/21) versus global random
baseline .252 can arise from (i) choosing gate 011, (ii) selecting tasks with
high proxy prevalence, (iii) useful ordering WITHIN matched task/gate groups.
Compute the expectation for a random selector with the exact SAME selected
fractional quotas within each task x gate pattern; compare observed 17 to it.

The matched random controls use audit labels only to compute retrospective
EXPECTED reference prevalence. No labels are provided to priority() and no
future online selector is trained. Results are descriptive, not confirmatory.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import ROOT, SRC, VIEWS, digest
from p1_return_time_triage_lab import (
    ARMS, RATIOS, build_rows, priority, topk_expected
)

PROTOCOL = "RPENT_P1_TRIAGE_INCREMENTAL_L1_V1"
OUT = ROOT / "artifacts" / "p1_return_time_triage_lab"
SEED = 20261010
N_BOOT = 500

def select_weights(rows, arm, ratio):
    """Fractional top-k selector using legal tool-return scores ONLY."""
    if not rows or not 0 < ratio <= 1:
        raise ValueError("Invalid selection population/budget")
    k = math.ceil(len(rows)*ratio)
    groups = defaultdict(list)
    for i,r in enumerate(rows):
        groups[priority(arm, r["legal"])].append(i)
    weights = [0.] * len(rows)
    left = k
    for value, idxs in sorted(groups.items(),reverse=True):
        if left <= 0:
            break
        take = min(left, len(idxs))
        for i in idxs:
            weights[i] = take / len(idxs)
        left -= take
    if left or not math.isclose(sum(weights),k,abs_tol=1e-9):
        raise ValueError("Fixed-budget selector violated mass constraint")
    return weights

def group_key(row, mode):
    if mode == "global":
        return ("ALL",)
    if mode == "gate":
        return (row["legal"]["gate_pattern"],)
    if mode == "task":
        return (row["task"],)
    if mode == "task_gate":
        return (row["task"], row["legal"]["gate_pattern"])
    raise ValueError("Unapproved control matching")

def decompose(rows, arm="LIFT_MINUS_GAP", ratio=.20,
              reference="exit_proxy_positive"):
    """Describe global, gate, task and matched task×gate random controls.

    Returns a single aggregate object, never raw case IDs, scores or labels.
    """
    if reference not in ("exit_proxy_positive", "ever_proxy_positive"):
        raise ValueError("Unapproved reference")
    if any(type(r.get(reference)) is not bool for r in rows):
        raise ValueError("Unvalidated audit references")
    weights = select_weights(rows,arm,ratio)
    k = sum(weights)
    labels = [float(r[reference]) for r in rows]
    observed = sum(w*y for w,y in zip(weights,labels))
    result = {"arm":arm, "ratio":ratio, "n":len(rows),
              "k":round(k,6),
              "n_proxy_positive":sum(labels),
              "expected_selected_positive":round(observed,6),
              "precision":round(observed/k,6),
              "matched_controls":{}}
    for control in ("global","gate","task","task_gate"):
        cells = defaultdict(list)
        for i,r in enumerate(rows):
            cells[group_key(r,control)].append(i)
        expected = 0.
        selected_cells = 0
        for idxs in cells.values():
            cell_selected = sum(weights[i] for i in idxs)
            if not cell_selected:
                continue
            selected_cells += 1
            prevalence = sum(labels[i] for i in idxs)/len(idxs)
            expected += cell_selected*prevalence
        result["matched_controls"][control] = {
            "selected_proxy_positive_under_random":round(expected,6),
            "expected_precision":round(expected/k,6),
            "incremental_positive_over_random":round(observed-expected,6),
            "delta_precision":round((observed-expected)/k,6),
            "n_selected_cells":selected_cells,
        }
    # Cross-check fixed top-k weights against the existing benchmark.
    baseline = topk_expected(rows,arm,ratio,label_key=reference)
    if abs(result["expected_selected_positive"] -
           baseline["expected_selected_proxy_positive"])>1e-5:
        raise ValueError("TopK score/tie semantics differ from frozen triage")
    return result

def grouped_bootstrap(rows, arm="LIFT_MINUS_GAP", ratio=.20,
                      n_boot=N_BOOT, seed=SEED):
    """Episode-cluster descriptive uncertainty of matched conditional gain."""
    by_ep=defaultdict(list)
    for r in rows:
        by_ep[r["episode_id"]].append(r)
    eps=sorted(by_ep)
    rng=random.Random(seed)
    samples=[]
    for _ in range(n_boot):
        dataset=[r for _ in eps for r in by_ep[rng.choice(eps)]]
        d=decompose(dataset,arm,ratio)["matched_controls"]
        samples.append(d["task_gate"]["delta_precision"])
    samples.sort()
    return {
        "n_valid":len(samples), "n_source_episodes":len(eps),
        "seed":seed,
        "median":round(samples[len(samples)//2],6) if samples else None,
        "p2_5":round(samples[int(.025*(len(samples)-1))],6) if samples else None,
        "p97_5":round(samples[int(.975*(len(samples)-1))],6) if samples else None,
        "frac_gt_zero":round(sum(v>0 for v in samples)/len(samples),6)
                       if samples else None,
        "warning":"Descriptive episode bootstrap; not a pre-registration or prospective generalization proof",
    }

def summarize(rows, boot_repeats=N_BOOT):
    if len(rows)!=103 or len({r["episode_id"] for r in rows})!=79:
        raise ValueError("Frozen A0 tool-failure 103 rows / 79 episodes mismatch")
    if sum(r["exit_proxy_positive"] for r in rows)!=26 or sum(
            r["ever_proxy_positive"] for r in rows)!=56:
        raise ValueError("Frozen terminal/any-time proxy counts mismatch")
    if sorted({r["task"] for r in rows}) != ["3","5","9"]:
        raise ValueError("Unexpected task set")
    primary={}
    for arm in ("LIFT_MINUS_GAP","D_ONLY_PATTERN","PEAK_LIFT"):
        primary[arm]={}
        for ratio in RATIOS:
            primary[arm][f"budget_{round(ratio*100)}pct"]={
                "terminal":decompose(rows,arm,ratio,"exit_proxy_positive"),
                "any_time":decompose(rows,arm,ratio,"ever_proxy_positive"),
            }
    strata={}
    for task in ("3","5","9"):
        sample=[r for r in rows if r["task"]==task]
        strata[task] = decompose(sample,"LIFT_MINUS_GAP",.20)
    subset=[r for r in rows
            if r["task"]=="9" and r["legal"]["gate_pattern"]=="011"]
    if len(subset)!=19 or sum(r["exit_proxy_positive"] for r in subset)!=11:
        raise ValueError("Frozen Task9 D-only n=19/11 mismatch")
    t9=decompose(subset,"LIFT_MINUS_GAP",.20)
    result={
        "protocol":PROTOCOL,
        "status":"OFFLINE_INCREMENTAL_INFORMATION_EXPLORATORY",
        "scientific_question":"Incremental ranking benefit within matched task and gate pattern, over cohort/gate composition alone",
        "n_failures":len(rows),
        "n_episodes":len({r["episode_id"] for r in rows}),
        "n_terminal_proxy_pos":26,"n_anytime_proxy_pos":56,
        "fixed_arm_ablations":primary,
        "within_task_LMG":strata,
        "task9_D_only_LMG":t9,
        "episode_cluster_bootstrap_LMG_terminal_top20_task_gate_increment":
            grouped_bootstrap(rows,n_boot=boot_repeats),
        "limitations":[
            "Conditioning task×gate uses audit-only reference prevalence for ANALYSIS, not ranking; no oracle label goes to score.",
            "This is a retrospective standardization, not a learned selector or a causal intervention.",
            "Any apparent within-cell incremental gain may be small/noisy at 103 cases and t9 D-only n19.",
            "All held positives are weak kinematic FGONLY reference at same-skill terminal time; not independent held-object truth.",
            "No training, no new simulator episodes, no online Runtime or policy modification.",
            "Repeated score inspection risks posthoc researcher degrees of freedom; results only exploratory.",
        ],
    }
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",type=Path,default=SRC)
    ap.add_argument("--out",type=Path,default=OUT)
    args=ap.parse_args()
    if not args.out.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        ap.error("Output must stay in gitignored artifacts/")
    if args.out.resolve()==args.input.resolve():
        ap.error("Do not overwrite frozen inputs")
    rows=build_rows(root=ROOT,src=args.input)
    data=summarize(rows)
    data["source_sha256"]={name:digest(args.input/name) for name in VIEWS}
    args.out.mkdir(parents=True,exist_ok=True)
    file=args.out/"incremental_v1.json"
    file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                    encoding="utf-8")
    p=data["fixed_arm_ablations"]["LIFT_MINUS_GAP"]["budget_20pct"]
    print(json.dumps({
        "protocol":PROTOCOL,
        "n_failures":data["n_failures"],"n_episodes":data["n_episodes"],
        "LMG_top20_terminal":p["terminal"],
        "LMG_top20_any":p["any_time"],
        "LMG_top20_by_task":data["within_task_LMG"],
        "Task9_D_only":data["task9_D_only_LMG"],
        "episode_bootstrap_incremental":
            data["episode_cluster_bootstrap_LMG_terminal_top20_task_gate_increment"],
        "file":str(file),
        "scope":"Exploratory FGONLY proxy, no physical held-grasp or policy effect",
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
