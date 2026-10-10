#!/usr/bin/env python3
"""P1 Temporal Proxy Lab v1: archived A0 within-skill temporal persistence.

A new empirical L1 test of a potential reference-horizon artifact:
FGONLY (frozen A0) is an ANY-time predicate. A proxy-positive moment need
not persist to the final within-skill measurement.

Allowed: OFFLINE, read-only, existing 187 episode Stage R traces and
EERD A online/audit/metadata views; no sim, GPU, inference, model calls.
Strictly separated outputs: raw target pose is consumed AUDIT-ONLY to score
temporal proxy status, NEVER as decision-visible features. No per-case IDs,
target poses, paths, audit truth values or raw trace are persisted/output.
Terminal FGONLY is a separate exploratory derivative; DO NOT overwrite A0.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import load_data, SRC, ROOT
from p1_pick_gate_lab import gates
from research_package_a import collect, fg_only, label_reference

PROTOCOL = "RPENT_P1_TEMPORAL_PROXY_LAB_V1"
OUT = ROOT / "artifacts" / "p1_temporal_proxy_lab"

def temporal_trace(points, statuses):
    """Audit-only temporal reference decomposition; first measurement is base.

    'last valid sample' is not a substitute for a missing final_meas.
    If true final is unavailable, end status is UNKNOWN, not the last good
    sample silently used as return-time physical truth.
    """
    if not isinstance(points, list) or not points or len(points) != len(statuses):
        raise ValueError("Missing or misaligned points/statuses")
    base = points[0]
    ids = base.get("obj_of_interest") if isinstance(base, dict) else None
    if not isinstance(ids, list) or not ids or not isinstance(ids[0], str):
        raise ValueError("No valid target identity for audit-only trace")
    target = ids[0]
    values = [fg_only(p, base, target) if status == "VALID" else None
              for p, status in zip(points, statuses)]
    if any(v is not None and type(v) is not bool for v in values):
        raise ValueError("Invalid proxy evaluation")
    any_positive = any(v is True for v in values)
    terminal = values[-1]
    if any_positive:
        cls = ("EVER_POS_TERMINAL_POS" if terminal is True else
               "EVER_POS_TERMINAL_NEG" if terminal is False else
               "EVER_POS_TERMINAL_UNKNOWN")
    else:
        cls = ("EVER_NEGATIVE_COMPLETE" if all(v is False for v in values) else
               "EVER_NEGATIVE_INCOMPLETE")
    true_indices = [i for i, v in enumerate(values) if v is True]
    # Count contiguous True suffix at the actual final_meas, not the most
    # recent available point when the final measurement is unknown.
    trailing = 0
    for v in reversed(values[1:]):
        if v is not True:
            break
        trailing += 1
    end_window = values[-min(3,len(values)-1):] if len(values)>1 else []
    return {
        "class": cls,
        "frozen_any_positive": any_positive,
        "terminal": "POSITIVE" if terminal is True else
                    "NEGATIVE" if terminal is False else "UNKNOWN",
        "n_measured": len(values),
        "n_valid": sum(v is not None for v in values),
        "n_positive": len(true_indices),
        "first_positive_frac": (
            round(true_indices[0] / (len(values)-1), 4)
            if true_indices and len(values) > 1 else None),
        "last_positive_frac": (
            round(true_indices[-1] / (len(values)-1), 4)
            if true_indices and len(values) > 1 else None),
        "trailing_positive_nonbase": trailing,
        "last_3_all_positive": bool(len(end_window)==3 and
                                   all(v is True for v in end_window)),
    }

def _counter(rows, getter):
    return dict(sorted(Counter(getter(r) for r in rows).items()))

def aggregate(records):
    """Inputs are in-memory audited records joined to frozen A0 primary.

    Values kept in memory never leave as case-level values; output is
    aggregated by task, tool flag and 3-bit gate pattern.
    """
    if len(records)!=206:
        raise ValueError("Expected frozen 206 PRIMARY samples")
    result = {
        "protocol":PROTOCOL,
        "scope":"RETROSPECTIVE_WITHIN_SKILL_WEAK_PROXY_ONLY",
        "n_primary":206,
        "n_episodes":len({r["episode_id"] for r in records}),
        "task_n":_counter(records, lambda r:r["task"]),
        "frozen_any_reference":_counter(
            records, lambda r:"POSITIVE" if r["proxy"]["frozen_any_positive"] else "NEGATIVE"),
        "all_temporal_classes":_counter(records, lambda r:r["proxy"]["class"]),
        "by_tool_proxy_group":[],
        "by_task":{},
        "by_task_gate_failure":{},
        "contract":[
            "The existing FGONLY reference is true if ANY archived within-skill point satisfies a kinematic condition.",
            "Terminal FGONLY is evaluated separately at the final_meas of the same skill; NOT subsequent held-object truth.",
            "No online model, policy or tool is given target positions or audit-only temporal labels.",
            "Comparisons are descriptive, retrospective, within the same 206 quota-stopped A0 calls.",
            "Failure-group geometry explanations may be confounded by task and target; no causal explanation without an intervention.",
        ],
    }
    for task in sorted({r["task"] for r in records}):
        taskrows=[r for r in records if r["task"]==task]
        result["by_task"][task]={
            "n":len(taskrows),
            "temporal_classes":_counter(taskrows,lambda r:r["proxy"]["class"]),
        }
        fn_rows=[r for r in taskrows if r["flag"] is False and r["proxy"]["frozen_any_positive"]]
        result["by_task_gate_failure"][task]={
            "n_proxy_FN":len(fn_rows),
            "gate_pattern_class":dict(sorted(Counter(
                (r["gate_pattern"],r["proxy"]["class"]) for r in fn_rows
            ).items(),key=lambda kv:kv[0])),
            "only_D_missing_fn":{
                "n":sum(r["gate_pattern"]=="011" for r in fn_rows),
                "temporal_classes":_counter(
                    [r for r in fn_rows if r["gate_pattern"]=="011"],
                    lambda r:r["proxy"]["class"]),
            },
        }
        # JSON object keys cannot be tuples, convert explicit pair keys.
        result["by_task_gate_failure"][task]["gate_pattern_class"]=[
            {"gates_D_L_Gfinal":p,"temporal_class":cl,"n":n}
            for (p,cl),n in sorted(Counter((r["gate_pattern"],r["proxy"]["class"]) for r in fn_rows).items())
        ]
    for flag in (True,False):
        for frozen_pos in (True,False):
            xs=[r for r in records if r["flag"] is flag and
                r["proxy"]["frozen_any_positive"] is frozen_pos]
            result["by_tool_proxy_group"].append({
                "tool_flag":"TRUE" if flag else "FALSE",
                "frozen_proxy":"POSITIVE" if frozen_pos else "NEGATIVE",
                "n":len(xs),
                "temporal_classes":_counter(xs,lambda r:r["proxy"]["class"]),
                "terminal_FGONLY":_counter(xs,lambda r:r["proxy"]["terminal"]),
                "n_last3_all_positive":sum(r["proxy"]["last_3_all_positive"] for r in xs),
                "n_trailing_positive_ge3":sum(r["proxy"]["trailing_positive_nonbase"]>=3 for r in xs),
                "n_terminal_unknown":sum(r["proxy"]["terminal"]=="UNKNOWN" for r in xs),
            })
    fn=[r for r in records if r["flag"] is False and r["proxy"]["frozen_any_positive"]]
    result["proxy_false_negative_temporal"]={
        "n":len(fn),
        "terminal_FGONLY":_counter(fn,lambda r:r["proxy"]["terminal"]),
        "n_any_proxy_positive_but_terminal_negative":sum(
            r["proxy"]["class"]=="EVER_POS_TERMINAL_NEG" for r in fn),
        "n_any_proxy_positive_but_terminal_unknown":sum(
            r["proxy"]["class"]=="EVER_POS_TERMINAL_UNKNOWN" for r in fn),
        "n_last3_all_positive":sum(r["proxy"]["last_3_all_positive"] for r in fn),
        "n_trailing_positive_ge3":sum(r["proxy"]["trailing_positive_nonbase"]>=3 for r in fn),
    }
    if result["frozen_any_reference"] != {"NEGATIVE":49,"POSITIVE":157}:
        raise ValueError("Frozen A0 proxy reference counts changed")
    if result["proxy_false_negative_temporal"]["n"]!=56:
        raise ValueError("Frozen A0 proxy FN denominator changed")
    return result

def run(root=ROOT, src=SRC):
    from research_package_a import source_paths
    frozen=load_data(src,strict=True)
    expected={(r["episode_id"],r["step_idx"]):r for r in frozen}
    qa=json.loads((src/"schema_qa.json").read_text(encoding="utf-8"))
    provenance, _, original, errors=collect(root)
    if errors:
        raise ValueError(f"Frozen trace parser reports {len(errors)} schema problems")
    if provenance != qa.get("source_sha256"):
        raise ValueError("Source hashes do not match sealed A0 schema_qa.json")
    joined=[]
    for item in original:
        key=(item["episode_id"],item["step_idx"])
        if key not in expected:
            # Terminal-involved excluded from original PRIMARY, but not lost.
            continue
        if item["result"].get("libero_terminated") is not False:
            raise ValueError("Unexpected terminal in frozen PRIMARY")
        row=expected[key]
        if item["result"].get("success") is not row["tool_report"]["success"]:
            raise ValueError("Original tool flag differs from A-online")
        p=temporal_trace(item["points"],item["point_status"])
        if p["frozen_any_positive"] != row["reference"]:
            raise ValueError("Temporal ANY does not reproduce frozen FGONLY A0 reference")
        if label_reference(item["points"],item["point_status"]) != (
                "POSITIVE" if row["reference"] else "NEGATIVE"):
            raise ValueError("Reference function mismatch")
        gbits=gates(row["tool_report"])
        if gbits is None:
            raise ValueError("Missing tool gate diagnostics")
        pat="".join("1" if gbits[k] else "0" for k in ("D","L","G_final"))
        joined.append({"episode_id":key[0],"task":row["task"],
                       "flag":row["tool_report"]["success"],
                       "gate_pattern":pat,"proxy":p})
    if len(joined)!=len(frozen) or len({r["episode_id"] for r in joined})!=175:
        raise ValueError("Frozen join is incomplete or duplicates")
    return aggregate(joined), provenance

def main():
    pa=argparse.ArgumentParser(description=__doc__)
    pa.add_argument("--input",type=Path,default=SRC)
    pa.add_argument("--output",type=Path,default=OUT)
    args=pa.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/"artifacts").resolve()):
        pa.error("Output must stay within private gitignored artifacts")
    if args.output.resolve()==args.input.resolve():
        pa.error("Refuse to overwrite frozen A0 export")
    data,provenance=run(root=ROOT,src=args.input)
    # Summaries only. Hash ledger and all source assets already validated
    # against the frozen schema_qa file, which itself is not modified.
    data["source_alignment"]="MATCHES_A0_SEALED_SCHEMA_SHA256"
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/"temporal_proxy_v1.json"
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "protocol":data["protocol"],"n_primary":data["n_primary"],
        "n_episodes":data["n_episodes"],
        "proxy_false_negative_temporal":data["proxy_false_negative_temporal"],
        "by_task_gate_failure":data["by_task_gate_failure"],
        "by_tool_proxy_group":data["by_tool_proxy_group"],
        "output_path":str(target),
        "warning":"Same-skill kinematic proxy persistence, NOT physically independent held-grasp truth",
    },ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
