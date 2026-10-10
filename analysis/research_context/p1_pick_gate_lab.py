#!/usr/bin/env python3
"""P1 Pick-Gate Lab v1 — empirical dissection of existing pi0_pick logic.

Exploratory L1 only. Study task-dependent disagreements of a fixed
within-skill FGONLY proxy, NEVER infer held-object truth or control effects.

The actual pi0_pick code has THREE gates: descent>=0.10m,
post-minimum ascent>=0.05m, final gripper opening<0.06m.
A prior two-gate AND arm omitted the descent requirement and used the
MINIMUM (rather than FINAL) gripper opening. We quantify each difference
using the frozen 206 PRIMARY EERD rows. Terminal-summary recomputation
is a diagnostic, not necessarily a reproduction of every chunk decision.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import (
    PROTOCOL as LAB0_PROTOCOL, PRESETS, confusion, digest, load_data,
    metrics, VIEWS, ROOT, SRC
)

PROTOCOL = "RPENT_P1_PICK_GATE_L1_V1"
OUT = ROOT/"artifacts"/"p1_pick_gate_lab"
# Frozen original pi0_pick defaults, see robots/libero/tools.py:205-264.
D_THRESHOLD = .10
L_THRESHOLD = .05
G_THRESHOLD = .06

def _value(rep, name):
    value = rep.get(name)
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return float(value)

def gates(rep):
    """Decision-visible tool-return diagnostics only: no audit labels."""
    if not isinstance(rep, dict):
        return None
    diag = rep.get("diagnostics")
    if not isinstance(diag, dict):
        return None
    descent = _value(diag, "descent_m")
    lift = _value(rep, "peak_lift_m")
    g_final = _value(rep, "final_gripper_opening")
    g_min = _value(rep, "min_gripper_opening")
    # Negative values are invalid physical measurement for these magnitudes.
    if any(v is None or v < 0 for v in (descent, lift, g_final, g_min)):
        return None
    return {
        "D": descent >= D_THRESHOLD,
        "L": lift >= L_THRESHOLD,
        "G_final": g_final < G_THRESHOLD,
        "G_min": g_min < G_THRESHOLD,
    }

def predict(preset, rep):
    bits = gates(rep)
    if bits is None:
        return None
    if preset == "F0_tool_flag":
        return rep.get("success") if type(rep.get("success")) is bool else None
    mapping = {
        "D_only": ("D",), "L_only": ("L",), "Gfinal_only": ("G_final",),
        "Gmin_only": ("G_min",),
        "D_AND_L": ("D", "L"),
        "D_AND_Gfinal": ("D", "G_final"),
        "L_AND_Gfinal": ("L", "G_final"),
        "L_AND_Gmin": ("L", "G_min"),
        "D_AND_L_AND_Gfinal": ("D", "L", "G_final"),
        "D_AND_L_AND_Gmin": ("D", "L", "G_min"),
    }
    return all(bits[k] for k in mapping[preset])

ARMS = ("F0_tool_flag", "D_only", "L_only", "Gfinal_only", "Gmin_only",
        "D_AND_L", "D_AND_Gfinal", "L_AND_Gfinal", "L_AND_Gmin",
        "D_AND_L_AND_Gfinal", "D_AND_L_AND_Gmin")

def score(rows, arm):
    tp = fp = fn = tn = abstain = 0
    for r in rows:
        pred = predict(arm, r["tool_report"])
        if pred is None:
            abstain += 1
            pred = False  # fail closed, unknown signal => not automatic accept
        actual = r["reference"]
        if pred and actual: tp += 1
        elif pred and not actual: fp += 1
        elif not pred and actual: fn += 1
        else: tn += 1
    return metrics({"n":len(rows), "tp":tp, "fp":fp, "fn":fn, "tn":tn,
                    "abstain":abstain})

def scan(rows):
    if len(rows) != 206:
        raise ValueError("Expected EXACT frozen A0 206 PRIMARY rows")
    by_task = defaultdict(list)
    patterns = Counter()
    patterns_by_task = defaultdict(Counter)
    mismatches = Counter()
    eligible = 0
    for row in rows:
        task = row["task"]
        by_task[task].append(row)
        b = gates(row["tool_report"])
        if b is None:
            mismatches["missing_or_invalid_gate_fields"] += 1
            continue
        eligible += 1
        pattern = "".join("1" if b[k] else "0" for k in ("D", "L", "G_final"))
        flag = row["tool_report"]["success"]
        label = "PROXY_POS" if row["reference"] else "PROXY_NEG"
        fg = "FLAG_T" if flag else "FLAG_F"
        patterns[(pattern, fg, label)] += 1
        patterns_by_task[task][(pattern, fg, label)] += 1
        implied = all(b[k] for k in ("D", "L", "G_final"))
        if implied != flag:
            mismatches["terminal_gate_and_tool_flag_disagree"] += 1
        # Distinguish minimum gripper opening from final opening.
        if b["G_min"] != b["G_final"]:
            mismatches["min_vs_final_grip_flag_disagree"] += 1
    result = {
        "protocol": PROTOCOL,
        "status": "EXPLORATORY_TOOL_RETURN_COMPONENT_ABLATION",
        "n_primary": len(rows), "n_gate_fields_eligible": eligible,
        "n_episodes": len({r["episode_id"] for r in rows}),
        "task_n": {k: len(v) for k,v in sorted(by_task.items())},
        "gate_thresholds": {"descent_m_gte": D_THRESHOLD,
                            "post_min_lift_m_gte": L_THRESHOLD,
                            "final_gripper_opening_lt": G_THRESHOLD},
        "gate_integrity": dict(mismatches),
        "overall": {arm: score(rows, arm) for arm in ARMS},
        "per_task": {task: {arm: score(taskrows, arm) for arm in ARMS}
                     for task,taskrows in sorted(by_task.items())},
        "pattern_distributions": [
            {"gates_D_L_Gfinal": p, "tool_flag": f, "fgonly_proxy": y, "n": n}
            for (p,f,y),n in sorted(patterns.items())
        ],
        "patterns_by_task": {
            task: [
                {"gates_D_L_Gfinal":p, "tool_flag":f, "fgonly_proxy":y, "n":n}
                for (p,f,y),n in sorted(cnt.items())
            ]
            for task,cnt in sorted(patterns_by_task.items())
        },
        "limitations": [
            "FGONLY is a WITHIN-SKILL pose-follow proxy, not independent grasp or future retention truth",
            "Tool success may have been determined at an earlier chunk; end-of-call gate diagnostic is not guaranteed to reconstruct original sequential condition",
            "Diagnostic descent_m is rounded and is not independent of flag construction",
            "This is pre-existing observational task data, not new arm interventions",
            "This experiment measures source of threshold-rule disagreement, not evidence-driven control benefits",
        ],
    }
    result["flag_false_by_task"] = {
        task: {
            "n_tool_failures": sum(not r["tool_report"]["success"] for r in rs),
            "proxy_positive_among_failures": sum(
                not r["tool_report"]["success"] and r["reference"] for r in rs),
            "proxy_negative_among_failures": sum(
                not r["tool_report"]["success"] and not r["reference"] for r in rs),
        } for task,rs in sorted(by_task.items())
    }
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=SRC)
    p.add_argument("--output", type=Path, default=OUT)
    a=p.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        p.error("Output must be in gitignored artifacts")
    if a.output.resolve() == a.input.resolve():
        p.error("Output cannot overwrite frozen EERD input")
    rows=load_data(a.input,strict=True)
    out=scan(rows)
    out["source_sha256"]={name:digest(a.input/name) for name in VIEWS}
    a.output.mkdir(parents=True,exist_ok=True)
    path=a.output/"gate_lab_v1.json"
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "protocol": out["protocol"],
        "n_primary":out["n_primary"],
        "n_gate_fields_eligible":out["n_gate_fields_eligible"],
        "gate_integrity":out["gate_integrity"],
        "flag_false_by_task":out["flag_false_by_task"],
        "overall":out["overall"],
        "per_task":out["per_task"],
        "pattern_distributions":out["pattern_distributions"],
        "output_path":str(path),
        "truth_limit":"Only same-skill FGONLY proxy; no physical contact/held labels",
    },ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
