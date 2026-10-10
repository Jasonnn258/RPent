#!/usr/bin/env python3
"""P1 Module Lab / L1: ablate small decision rules on frozen Package-A views.

NO simulator, robot, online policy, GPU, neural training or file mutation.
A_online_eligible features are passed alone to all rule implementations;
A_audit_only reference is joined ONLY in offline scoring. metadata task_id
is used solely for grouping/analysis. The reference is WITHIN-SKILL FGONLY,
NOT probe-end grasp truth or future task success.

Primary results are PRE-SPECIFIED fixed arms, not posthoc best-grid models.
Secondary threshold perturbations measure sensitivity only. Never select
a 'winner' on this same dataset and claim heldout performance.

Usage:
  python3 analysis/research_context/p1_offline_module_lab.py \
    --input artifacts/research_package_a \
    --output artifacts/p1_module_lab
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "artifacts" / "research_package_a"
OUT = ROOT / "artifacts" / "p1_module_lab"
PROTOCOL = "RPENT_P1_OFFLINE_MODULE_LAB_V1"
REFERENCE = "IN_SKILL_ACQ_FGONLY_V1"
VIEWS = ("EERD_A_online_eligible.jsonl", "EERD_A_audit_only.jsonl",
         "EERD_A_reconstruction_metadata.jsonl")
# Fixed presets use thresholds already present in P1/VE01 source contracts:
# 0.060m frozen D2 gap; 0.0035m VE01 exploratory floor; 0.050m tool lift.
PRESETS = {
    "F0_tool_flag": ("flag",),
    "C0_always_false": ("const", False),
    "C1_always_true": ("const", True),
    "G0_min_gap_060": ("gap", "min_gripper_opening", .060),
    "G1_min_gap_0035": ("gap", "min_gripper_opening", .0035),
    "G2_final_gap_0035": ("gap", "final_gripper_opening", .0035),
    "L0_peak_lift_050": ("lift", .050),
    "A0_gap060_AND_lift050": ("and", ("gap", "min_gripper_opening", .060), ("lift", .050)),
    "A1_gap0035_AND_lift050": ("and", ("gap", "min_gripper_opening", .0035), ("lift", .050)),
    "O0_gap0035_OR_lift050": ("or", ("gap", "min_gripper_opening", .0035), ("lift", .050)),
    "R0_flag_OR_min_gap0035": ("or", ("flag",), ("gap", "min_gripper_opening", .0035)),
    "R1_flag_OR_lift050": ("or", ("flag",), ("lift", .050)),
    "R2_flag_OR_gap0035_AND_lift050": ("or", ("flag",),
                                        ("and", ("gap", "min_gripper_opening", .0035),
                                                 ("lift", .050))),
}
GAP_GRID = (.002, .0035, .005, .015, .03, .06)
LIFT_GRID = (.02, .03, .05, .07)
# No fitted threshold, and NO optimization on audit labels.
GROUP_BOOTSTRAP = 1000

def jl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1 << 20), b""):
            h.update(buf)
    return h.hexdigest()

def load_data(src, strict=True):
    d = {name: jl(src / name) for name in VIEWS}
    if strict and any(len(d[name]) != 235 for name in VIEWS):
        raise ValueError("Expected frozen Package A: 235 rows in each view")
    def index(rows):
        out = {}
        for r in rows:
            key = (r.get("episode_id"), r.get("step_idx"))
            if not isinstance(key[0], str) or type(key[1]) is not int or key in out:
                raise ValueError("Invalid/duplicate view join key")
            out[key] = r
        return out
    audit = index(d[VIEWS[1]])
    meta = index(d[VIEWS[2]])
    if set(audit) != set(meta):
        raise ValueError("Misaligned audit/metadata views")
    rows = []
    source_keys = set()
    for online in d[VIEWS[0]]:
        key = (online.get("episode_id"), online.get("step_idx"))
        if key in source_keys or key not in audit:
            raise ValueError("Missing/duplicate online key")
        source_keys.add(key)
        ref, m = audit[key], meta[key]
        rep = online.get("tool_report")
        if (not isinstance(rep, dict) or type(rep.get("success")) is not bool or
                ref.get("flag") is not rep["success"] or
                ref.get("visibility") != "research_audit_truth" or
                online.get("visibility") != "observed_execution_prefix"):
            raise ValueError("Online/audit feature contract or flag mismatch")
        if ref.get("outcome_contract") != REFERENCE:
            raise ValueError("Unexpected reference contract")
        if ref.get("reference") not in ("POSITIVE", "NEGATIVE", "UNKNOWN"):
            raise ValueError("Bad reference label")
        if type(ref.get("terminal_involved")) is not bool:
            raise ValueError("No terminal exclusion field")
        if ref["terminal_involved"]:
            continue
        if ref["reference"] == "UNKNOWN":
            raise ValueError("Frozen primary reference UNKNOWN; cannot score")
        task = m.get("task_id")
        if task is None:
            raise ValueError("Missing task grouping metadata")
        rows.append({
            "episode_id": key[0], "step_idx": key[1], "task": str(task),
            # Critically, ONLY copied from the physically separated online view.
            "tool_report": rep,
            # Audit label is attached to an evaluation envelope, never
            # passed into signal() or predict().
            "reference": ref["reference"] == "POSITIVE",
        })
    if source_keys != set(audit):
        raise ValueError("Incomplete A online/audit join")
    if strict:
        if len(rows) != 206:
            raise ValueError("Frozen A primary must contain 206 picks")
        mat = Counter((r["tool_report"]["success"], r["reference"]) for r in rows)
        if (mat[(True, True)], mat[(True, False)],
            mat[(False, True)], mat[(False, False)]) != (101, 2, 56, 47):
            raise ValueError("A0 frozen baseline confusion mismatch")
    return rows

def signal(kind, report, *args):
    if kind == "flag":
        return report.get("success") if type(report.get("success")) is bool else None
    if kind == "const":
        return args[0]
    key = "peak_lift_m" if kind == "lift" else args[0]
    threshold = args[0] if kind == "lift" else args[1]
    value = report.get(key)
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        return None
    if kind == "lift":
        return value >= threshold
    if kind == "gap":
        return value <= threshold
    raise ValueError("Unexpected signal")

def predict(spec, online_report):
    kind = spec[0]
    if kind == "and":
        a, b = predict(spec[1], online_report), predict(spec[2], online_report)
        if a is False or b is False:
            return False
        return None if a is None or b is None else True
    if kind == "or":
        a, b = predict(spec[1], online_report), predict(spec[2], online_report)
        if a is True or b is True:
            return True
        return None if a is None or b is None else False
    return signal(kind, online_report, *spec[1:])

def confusion(rows, spec):
    tp = fp = fn = tn = abstain = 0
    for row in rows:
        pred = predict(spec, row["tool_report"])
        if pred is None:
            abstain += 1
            pred = False  # predeclared default-to-retry for scoring
        y = row["reference"]
        if pred and y: tp += 1
        elif pred and not y: fp += 1
        elif not pred and y: fn += 1
        else: tn += 1
    return {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "abstain": abstain}

def metrics(cm):
    n = cm["n"]
    p = cm["tp"] + cm["fn"]
    q = cm["tn"] + cm["fp"]
    sensitivity = cm["tp"]/p if p else None
    specificity = cm["tn"]/q if q else None
    bacc = (sensitivity + specificity)/2 if sensitivity is not None and specificity is not None else None
    return {**cm,
            "balanced_accuracy": round(bacc, 6) if bacc is not None else None,
            "agreement": round((cm["tp"]+cm["tn"])/n, 6) if n else None,
            "proxy_false_accept_rate": round(cm["fp"]/q, 6) if q else None,
            "proxy_positive_recall": round(sensitivity, 6) if sensitivity is not None else None,
            "coverage": round((n-cm["abstain"])/n, 6) if n else None}

def score(rows, specs):
    return {name: metrics(confusion(rows, spec)) for name, spec in specs.items()}

def delta_vs_flag(rows, spec, repeats=GROUP_BOOTSTRAP, seed=20261010):
    """Episode-level paired resampling; describes sample uncertainty only."""
    eps = defaultdict(list)
    for row in rows:
        eps[row["episode_id"]].append(row)
    keys = sorted(eps)
    rng = random.Random(seed)
    differences = []
    for _ in range(repeats):
        sampled = [r for _ in range(len(keys)) for r in eps[rng.choice(keys)]]
        a = metrics(confusion(sampled, spec))["balanced_accuracy"]
        b = metrics(confusion(sampled, PRESETS["F0_tool_flag"]))["balanced_accuracy"]
        if a is not None and b is not None:
            differences.append(a-b)
    differences.sort()
    if not differences:
        return {"n_valid": 0, "interval": None}
    return {"n_valid": len(differences),
            "interval": [round(differences[int(.025*(len(differences)-1))], 6),
                         round(differences[int(.975*(len(differences)-1))], 6)]}

def sensitivity_grid(rows):
    specs = {}
    for t in GAP_GRID:
        for l in LIFT_GRID:
            g, lift = ("gap", "min_gripper_opening", t), ("lift", l)
            for operator in ("and", "or"):
                specs[f"{operator}_gap{t:g}_lift{l:g}"] = (operator, g, lift)
    return score(rows, specs)

def leave_one_task_out_selection(rows):
    """Select among FIXED candidate modules on the other two tasks only.

    This is an offline exploratory module-selection experiment. No threshold
    fitting or online changes; held-out task labels never enter selection.
    There are only three tasks, so transfer estimates are highly unstable.
    """
    tasks = sorted({r["task"] for r in rows})
    if len(tasks) < 2:
        return {"status": "UNESTIMABLE_LESS_THAN_TWO_TASKS"}
    candidates = {k: v for k, v in PRESETS.items() if not k.startswith("C")}
    folds = []
    pooled = Counter()
    for heldout in tasks:
        train = [r for r in rows if r["task"] != heldout]
        test = [r for r in rows if r["task"] == heldout]
        trained = score(train, candidates)
        def key(name):
            m = trained[name]
            ba = m["balanced_accuracy"] if m["balanced_accuracy"] is not None else -1
            far = m["proxy_false_accept_rate"] if m["proxy_false_accept_rate"] is not None else 1
            return (-ba, far, m["abstain"], name)
        chosen = min(candidates, key=key)
        test_result = metrics(confusion(test, candidates[chosen]))
        base_test = metrics(confusion(test, PRESETS["F0_tool_flag"]))
        for k in ("tp", "fp", "fn", "tn", "abstain", "n"):
            pooled[k] += test_result[k]
        folds.append({
            "heldout_task": heldout, "n_training": len(train),
            "n_heldout": len(test), "selected_module": chosen,
            "training_module_bacc": trained[chosen]["balanced_accuracy"],
            "test_selected": test_result, "test_flag_baseline": base_test,
            "delta_test_bacc_vs_flag": (
                round(test_result["balanced_accuracy"]-base_test["balanced_accuracy"], 6)
                if test_result["balanced_accuracy"] is not None
                and base_test["balanced_accuracy"] is not None else None),
        })
    pooled_m = metrics(dict(pooled))
    base_pooled = metrics(confusion(rows, PRESETS["F0_tool_flag"]))
    return {
        "status": "EXPLORATORY_CROSS_TASK_MODULE_SELECTION",
        "folds": folds, "pooled_test_selected": pooled_m,
        "pooled_test_baseline": base_pooled,
        "delta_pooled_balacc": (
            round(pooled_m["balanced_accuracy"]-base_pooled["balanced_accuracy"], 6)
            if pooled_m["balanced_accuracy"] is not None
            and base_pooled["balanced_accuracy"] is not None else None),
        "caution": "Three nonindependent task folds only. Module selection learns from TRAIN audit proxy labels OFFLINE; no training of neural weights, no deployment and no confirmatory generalization.",
    }

def evaluate(rows):
    overall = score(rows, PRESETS)
    tasks = sorted({r["task"] for r in rows})
    per_task = {t: score([r for r in rows if r["task"] == t], PRESETS) for t in tasks}
    target = ["G0_min_gap_060", "G1_min_gap_0035", "G2_final_gap_0035",
              "L0_peak_lift_050", "A1_gap0035_AND_lift050",
              "O0_gap0035_OR_lift050", "R0_flag_OR_min_gap0035",
              "R1_flag_OR_lift050", "R2_flag_OR_gap0035_AND_lift050"]
    intervals = {k: delta_vs_flag(rows, PRESETS[k]) for k in target}
    baseline = overall["F0_tool_flag"]
    comparisons = {}
    for name, met in overall.items():
        comparisons[name] = {
            "delta_balanced_accuracy_vs_flag": (
                round(met["balanced_accuracy"]-baseline["balanced_accuracy"], 6)
                if met["balanced_accuracy"] is not None else None),
            "delta_proxy_fp_vs_flag": met["fp"]-baseline["fp"],
            "delta_proxy_fn_vs_flag": met["fn"]-baseline["fn"],
        }
    return {"protocol": PROTOCOL, "research_status": "EXPLORATORY_NO_POLICY_TRAINING",
            "n_primary": len(rows), "n_episodes": len({r["episode_id"] for r in rows}),
            "n_tasks": len(tasks), "task_n": dict(Counter(r["task"] for r in rows)),
            "fixed_arms": overall, "delta_vs_tool_flag": comparisons,
            "per_task": per_task,
            "leave_one_task_out_module_selection": leave_one_task_out_selection(rows),
            "paired_episode_cluster_delta_balacc_95": intervals,
            "threshold_sensitivity_grid": sensitivity_grid(rows),
            "limitations": [
                "A0 frozen reference is within-skill FGONLY pose-following, not probe-time or future held object",
                "No module selection, parameter fitting, new rollout, training or policy intervention",
                "Accuracy and FP/FN measure agreement with FGONLY only; equal-time physical labels unavailable",
                "Threshold grid is exploratory on the same cohort; no heldout causal generalization",
                "Leave-one-task-out uses TRAIN audit proxy only to choose fixed module family and reports outcomes on separate tasks; no neural optimization",
                "Always-positive control is critical for reference class imbalance",
                "Confidence intervals are episode-cluster bootstrap descriptive uncertainty only",
                "Offline audit reference is joined only for scoring; no audit-only features enter prediction",
            ]}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=SRC)
    ap.add_argument("--output", type=Path, default=OUT)
    a = ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        ap.error("Output must stay in private gitignored artifacts")
    if a.output.resolve() == a.input.resolve():
        ap.error("Do not overwrite sealed Package A export")
    rows = load_data(a.input, strict=True)
    result = evaluate(rows)
    result["source_sha256"] = {name: digest(a.input/name) for name in VIEWS}
    a.output.mkdir(parents=True, exist_ok=True)
    out = a.output/"module_lab_v1.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "protocol": result["protocol"], "n_primary": result["n_primary"],
        "n_episodes": result["n_episodes"], "task_n": result["task_n"],
        "fixed_arms": result["fixed_arms"],
        "delta_vs_tool_flag": result["delta_vs_tool_flag"],
        "module_report_path": str(out),
        "reference_limit": "Same-skill FGONLY proxy, NOT held-grasp truth",
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
