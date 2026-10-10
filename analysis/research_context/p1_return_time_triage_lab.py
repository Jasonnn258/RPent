#!/usr/bin/env python3
"""P1 Return-Time Triage Lab v1 (read-only L1, no simulator or training).

Research question: given frozen historical pi0_pick tool FAILURE, can
decision-visible terminal diagnostics prioritize *review*, using the same
skill-exit FGONLY proxy as a weak offline reference?

All rankings use ONLY documented tool_report fields (no target positions,
contact truth, fg_only/reference values, task ID, seed or episode ID).
Target pose and EEF pose from Stage R are read ONLY for a sealed, audit-side
endpoint reference reconstruction. Nothing here recommends CONTINUE.

Fixed scores; NO fitted thresholds/weights, posthoc optimizer, or neural
training. Focus on entire n=103 failure population, plus task strata and
t9 pattern011 split. Tied scores have fractional top-K expectation so no
episode identities/metadata can influence tie breaks.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import ROOT, SRC, load_data, VIEWS, digest
from p1_pick_gate_lab import gates
from p1_temporal_proxy_lab import temporal_trace
from research_package_a import collect, label_reference

PROTOCOL = "RPENT_P1_RETURN_TIME_TRIAGE_L1_V1"
OUT = ROOT / "artifacts" / "p1_return_time_triage_lab"
RATIOS = (.20, .40)
ARMS = (
    "UNTARGETED",
    "D_ONLY_PATTERN",
    "PEAK_LIFT",
    "FINAL_GAP",
    "LIFT_MINUS_GAP",
    "D_ONLY_THEN_LIFT",
)
# All dimensions are frozen original tool success thresholds, not tuned on
# the return-time FGONLY labels. 2.0 is solely a lexicographic rank band.
LIFT_THRESH, GAP_THRESH = .05, .06


def legal_view(report):
    """Only features actually in the tool-return projection may be used."""
    if not isinstance(report, dict):
        raise ValueError("Invalid online tool report")
    d = report.get("diagnostics")
    if not isinstance(d, dict):
        raise ValueError("Missing decision-visible diagnostics")
    names = ("descent_m", "peak_lift_m", "final_gripper_opening",
             "min_gripper_opening", "start_eef_z")
    values = {}
    for k in names:
        value = d.get(k) if k in ("descent_m", "start_eef_z") else report.get(k)
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError("Missing, negative, or nonfinite legal feature")
        values[k] = float(value)
    g = gates(report)
    if g is None:
        raise ValueError("Gate predicate undefined in decision-visible report")
    values["gate_pattern"] = "".join("1" if g[k] else "0"
                                     for k in ("D", "L", "G_final"))
    return values


def priority(arm, legal):
    """No audit label/task/episode metadata argument is accepted."""
    if arm == "UNTARGETED":
        return 0.
    if arm == "D_ONLY_PATTERN":
        return float(legal["gate_pattern"] == "011")
    if arm == "PEAK_LIFT":
        return legal["peak_lift_m"]
    if arm == "FINAL_GAP":
        return -legal["final_gripper_opening"]
    if arm == "LIFT_MINUS_GAP":
        return legal["peak_lift_m"] / LIFT_THRESH - (
            legal["final_gripper_opening"] / GAP_THRESH)
    if arm == "D_ONLY_THEN_LIFT":
        # The clipped continuous contribution < 1.0 guarantees a strict
        # ordering of D-only over non-D-only candidates, without fitting.
        lift_score = min(legal["peak_lift_m"] / LIFT_THRESH, 2.) / 3.
        return float(legal["gate_pattern"] == "011") + lift_score
    raise ValueError("Unknown triage arm")


def topk_expected(rows, arm, ratio, label_key="exit_proxy_positive"):
    """Fractional tied-score selection avoids false precision and ID leakage.

    rows: [{"legal": ..., "exit_proxy_positive": bool}, ...] only.
    A tied block crossing k gets equal fractional selection per item.
    """
    if not 0 < ratio <= 1:
        raise ValueError("Invalid budget ratio")
    if not rows:
        raise ValueError("Cannot rank empty sample")
    n = len(rows)
    if label_key not in ("exit_proxy_positive", "ever_proxy_positive"):
        raise ValueError("Unapproved audit reference")
    if any(type(r.get(label_key)) is not bool for r in rows):
        raise ValueError("Missing true/false audit-side proxy")
    k = math.ceil(ratio * n)
    groups = defaultdict(list)
    for r in rows:
        groups[priority(arm, r["legal"])].append(r[label_key])
    remain = k
    selected_pos = 0.
    selected_neg = 0.
    for score in sorted(groups, reverse=True):
        if remain <= 0:
            break
        g = groups[score]
        alloc = min(remain, len(g))
        fraction = alloc / len(g)
        positive = sum(g)
        selected_pos += fraction * positive
        selected_neg += fraction * (len(g) - positive)
        remain -= alloc
    assert remain == 0
    positives = sum(r[label_key] for r in rows)
    prevalence = positives / n
    precision = selected_pos / k
    return {
        "n": n, "k": k, "n_proxy_positive": positives,
        "prevalence": round(prevalence, 6),
        "expected_selected_proxy_positive": round(selected_pos, 6),
        "expected_selected_proxy_negative": round(selected_neg, 6),
        "precision_at_budget": round(precision, 6),
        "proxy_positive_recall_at_budget": (
            round(selected_pos / positives, 6) if positives else None),
        "precision_lift_over_prevalence": (
            round(precision / prevalence, 6) if prevalence else None),
        "tie_policy": "FRACTIONAL_EXPECTATION",
    }


def build_rows(root=ROOT, src=SRC):
    """Join frozen A0 to audit-only endpoint labels without exposing poses."""
    online = load_data(src, strict=True)
    expected = {(r["episode_id"], r["step_idx"]):r for r in online}
    qa = json.loads((src / "schema_qa.json").read_text(encoding="utf-8"))
    if qa.get("gate") != "PASS":
        raise ValueError("Sealed schema QA is not PASS")
    provenance,_,trace,errors = collect(root)
    if errors:
        raise ValueError("Frozen original trace has schema problems")
    if provenance != qa.get("source_sha256"):
        raise ValueError("Original trace hashes mismatch sealed A0")
    rows = []
    for item in trace:
        key = (item["episode_id"],item["step_idx"])
        if key not in expected:
            continue  # A0 excluded terminal pick rows
        e = expected[key]
        report = e["tool_report"]
        if item["result"].get("success") is not report["success"]:
            raise ValueError("Mismatch original tool flag")
        label = "POSITIVE" if e["reference"] else "NEGATIVE"
        if label_reference(item["points"],item["point_status"]) != label:
            raise ValueError("Frozen A0 any-time proxy reference changed")
        p = temporal_trace(item["points"],item["point_status"])
        if p["frozen_any_positive"] is not e["reference"]:
            raise ValueError("Recomputed FGONLY ANY mismatch")
        if p["terminal"] == "UNKNOWN":
            raise ValueError("Missing final_meas endpoint; cannot silently exclude")
        if report["success"] is True:
            continue  # only previously failed tool outcomes can be triaged
        rows.append({
            # Only legal tool features feed priority().
            "legal": legal_view(report),
            # Audit reference is used ONLY after scores are computed.
            "exit_proxy_positive": p["terminal"]=="POSITIVE",
            "ever_proxy_positive": p["frozen_any_positive"],
            # Episode/task identifiers only for aggregate grouping/counts,
            # never accepted by the scoring function or output.
            "episode_id":e["episode_id"], "task":e["task"],
        })
    if len(rows)!=103 or len({r["episode_id"] for r in rows}) < 1:
        raise ValueError("Original A0 tool-failure denominator altered")
    if sum(r["exit_proxy_positive"] for r in rows)!=26:
        raise ValueError("Return-time proxy positive denominator altered")
    if sum(r["ever_proxy_positive"] for r in rows)!=56:
        raise ValueError("Frozen any-time proxy positive denominator altered")
    return rows


def summarize(rows):
    if (len(rows)!=103 or sum(r["exit_proxy_positive"] for r in rows)!=26
            or sum(r.get("ever_proxy_positive",False) for r in rows)!=56):
        raise ValueError("Frozen tool-failure and reference mismatch")
    tasks = sorted(set(r["task"] for r in rows))
    if tasks != ["3","5","9"]:
        raise ValueError("Frozen task set changed")
    def block(sample, label="exit_proxy_positive"):
        return {
            arm:{f"budget_{round(100*b)}pct":topk_expected(
                    sample,arm,b,label_key=label)
                 for b in RATIOS}
            for arm in ARMS
        }
    by_task={task:block([r for r in rows if r["task"]==task]) for task in tasks}
    by_task_any={task:block([r for r in rows if r["task"]==task],
                             "ever_proxy_positive") for task in tasks}
    t9=[r for r in rows if r["task"]=="9" and r["legal"]["gate_pattern"]=="011"]
    return {
        "protocol":PROTOCOL,
        "mode":"EXPLORATORY_L1_REVIEW_PRIORITY_NO_ACTIONS",
        "population":"FROZEN_A0_PRIMARY_PI0_PICK_FLAG_FALSE",
        "n_failures":len(rows),
        "n_episodes":len({r["episode_id"] for r in rows}),
        "n_exit_proxy_positive":sum(r["exit_proxy_positive"] for r in rows),
        "n_exit_proxy_negative":sum(not r["exit_proxy_positive"] for r in rows),
        "n_ever_proxy_positive":sum(r["ever_proxy_positive"] for r in rows),
        "task_n":dict(sorted(Counter(r["task"] for r in rows).items())),
        "arms":list(ARMS),
        "global":block(rows),
        "per_task":by_task,
        "reference_horizon_control":{
            "global_any_time":block(rows, "ever_proxy_positive"),
            "per_task_any_time":by_task_any,
            "note":"Fixed identical score and review budget; ONLY audit reference horizon changes (any-time vs terminal).",
        },
        "task9_D_only_subgroup":{
            "n":len(t9),
            "terminal_pos":sum(r["exit_proxy_positive"] for r in t9),
            "within_subgroup":block(t9) if t9 else None,
            "within_subgroup_any_time":block(t9,"ever_proxy_positive") if t9 else None,
        },
        "important_limits":[
            "Scores are fixed and predeclared; no audit label used for training, scoring, threshold selection or tie-break.",
            "A0 original flag-F cases only; topK means prioritized review, NEVER physical CONTINUE or proof of held-object.",
            "Reference is terminal FGONLY kinematic proxy, from same skill in immutable Stage R; no independent contact/held truth.",
            "Skill tool-return fields include z-lift/descent metrics closely related to kinematic FGONLY; reference leakage via shared construct possible.",
            "Three tasks and 103 selected tool-failure cases; retrospective rank results cannot prove cross-task or causal benefits.",
            "Subgroup Task9 D-only n=19 may not support meaningful separation; no posthoc fitting on this sample.",
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,default=SRC)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    if not args.out.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        p.error("Output must stay inside private gitignored artifacts/")
    if args.out.resolve()==args.input.resolve():
        p.error("Do not overwrite frozen A0 inputs")
    rows=build_rows(src=args.input)
    result=summarize(rows)
    result["input_sha256"]={name:digest(args.input/name) for name in VIEWS}
    args.out.mkdir(parents=True,exist_ok=True)
    output=args.out/"triage_v1.json"
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf-8")
    print(json.dumps({
        "protocol":result["protocol"],
        "n_failures":result["n_failures"],
        "n_exit_proxy_positive":result["n_exit_proxy_positive"],
        "n_ever_proxy_positive":result["n_ever_proxy_positive"],
        "budget20_anytime_global":{k:v["budget_20pct"] for k,v in
            result["reference_horizon_control"]["global_any_time"].items()},
        "task_n":result["task_n"],
        "budget20_global":{k:v["budget_20pct"] for k,v in result["global"].items()},
        "task9_D_only_subgroup":result["task9_D_only_subgroup"],
        "output":str(output),
        "reference_limit":"Exit-time FGONLY kinematic proxy, NOT independent grasp truth",
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
