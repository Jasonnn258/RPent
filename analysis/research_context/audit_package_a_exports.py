#!/usr/bin/env python3
"""Independent, read-only post-run QA for EERD-A/B artifacts (L1 only).

Does not recalculate FGONLY, read original raw traces, or modify sealed A0.
Reads only the PRIVATE output directory created by research_package_a.py.
Writes corrected *display-only* confusion-matrix view and QA ledger.

Usage: python3 analysis/research_context/audit_package_a_exports.py \
    --output artifacts/research_package_a
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

PROTOCOL = "RPENT-PACKAGE-A-STAGE2J-V2-EERD-V01-20261009"
VIEWS = {
    "A_online": "EERD_A_online_eligible.jsonl",
    "A_audit": "EERD_A_audit_only.jsonl",
    "A_metadata": "EERD_A_reconstruction_metadata.jsonl",
    "B_audit": "EERD_B_audit_only.jsonl",
    "B_metadata": "EERD_B_reconstruction_metadata.jsonl",
}


def jl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def keys_recursive(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from keys_recursive(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_recursive(item)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1 << 20), b""):
            h.update(buf)
    return h.hexdigest()


def assess(output, script_path=None):
    qa = json.loads((output / "schema_qa.json").read_text(encoding="utf-8"))
    a0 = json.loads((output / "a0_result.json").read_text(encoding="utf-8"))
    data = {key: jl(output / fname) for key, fname in VIEWS.items()}
    failures = []
    checks = Counter()

    def check(cond, label):
        checks[label] += 1
        if not cond:
            failures.append(label)

    check(qa.get("protocol") == PROTOCOL and a0.get("protocol") == PROTOCOL,
          "protocol_matched")
    check(qa.get("gate") == "PASS" and a0.get("gate") == "PASS",
          "schema_and_a0_gates_pass")
    if script_path is not None:
        check(qa.get("analysis_script_sha256") == digest(script_path),
              "sealed_analysis_code_hash_matched")
    check(len(data["A_online"]) == len(data["A_audit"]) == len(data["A_metadata"]) == 235,
          "A_view_row_counts_235")
    a_ids = lambda key: [(r["episode_id"], r["step_idx"]) for r in data[key]]
    a_keys = [a_ids(x) for x in ("A_online", "A_audit", "A_metadata")]
    check(all(len(set(keys)) == len(keys) for keys in a_keys), "A_each_view_unique")
    check(set(a_keys[0]) == set(a_keys[1]) == set(a_keys[2]), "A_view_join_integrity")
    check(len(set(r["episode_id"] for r in data["A_online"])) <= 186, "A_episode_count_upper_bound")
    check(all(r.get("visibility") == "observed_execution_prefix" for r in data["A_online"]),
          "A_online_visibility")
    online_forbidden = {"check_success", "obj_of_interest", "reference",
                        "research_audit_truth", "acquisition", "stable_fg",
                        "source_episode_id", "reconstruction_quality"}
    check(all(not (set(keys_recursive(r)) & online_forbidden) for r in data["A_online"]),
          "A_online_no_privileged_keys")
    check(all(r.get("visibility") == "research_audit_truth" for r in data["A_audit"]),
          "A_audit_visibility")

    tool_by_key = {(r["episode_id"], r["step_idx"]): r["tool_report"]["success"]
                   for r in data["A_online"]}
    check(all(tool_by_key.get((r["episode_id"], r["step_idx"])) is r["flag"]
              for r in data["A_audit"]), "A_tool_report_flag_unchanged")
    check(all(r["reference"] in ("POSITIVE", "NEGATIVE", "UNKNOWN")
              for r in data["A_audit"]), "A_reference_state_valid")

    primary = [r for r in data["A_audit"] if not r["terminal_involved"]]
    check(len(primary) == a0.get("n_primary") == 206,
          "A_primary_206_and_terminal_exclusion")
    check(sum(r["reference"] == "UNKNOWN" for r in data["A_audit"]) ==
          a0.get("reference_unknown") == 0, "A_reference_unknown_zero")

    # Standard confusion-matrix convention: flag=True is the prediction;
    # reference POSITIVE is the audit label. The original table serialized
    # flag-reference coordinates as e.g. "false_positive" (NOT conventional FN).
    tp = sum(r["flag"] is True and r["reference"] == "POSITIVE" for r in primary)
    fp = sum(r["flag"] is True and r["reference"] == "NEGATIVE" for r in primary)
    fn = sum(r["flag"] is False and r["reference"] == "POSITIVE" for r in primary)
    tn = sum(r["flag"] is False and r["reference"] == "NEGATIVE" for r in primary)
    check(tp + fp + fn + tn == len(primary), "A_conventional_confusion_sum")
    original = (a0.get("primary_descriptive") or {}).get("table", {})
    check((tp, fp, fn, tn) == (
        original.get("true_positive", 0),
        original.get("true_negative", 0),
        original.get("false_positive", 0),
        original.get("false_negative", 0)), "A_original_coordinate_mapping")
    check((tp, fp, fn, tn) == (101, 2, 56, 47), "A_expected_user_reported_cells")

    b_audit, b_meta = data["B_audit"], data["B_metadata"]
    check(len(b_audit) == len(b_meta) == 480, "B_view_row_counts_480")
    b_id = lambda r: (r["event_id"], r["arm"], r["trial"])
    b_keys = [[b_id(r) for r in coll] for coll in (b_audit, b_meta)]
    check(set(b_keys[0]) == set(b_keys[1]), "B_view_join_integrity")
    check(len(set(b_keys[0])) == len(b_keys[0]), "B_event_arm_trial_unique")
    by_event_arm = Counter((r["event_id"], r["arm"]) for r in b_meta)
    b_events = set(r["event_id"] for r in b_meta)
    check(len(b_events) == 24, "B_events_24")
    check(all(by_event_arm[(e, arm)] == n
              for e in b_events for arm, n in (
                  ("SAME", 8), ("RESAMPLE", 8), ("NATURAL", 4))),
          "B_each_event_8_8_4")
    check(all(r.get("source_episode_id") in
              {x["episode_id"] for x in data["A_online"]}
              for r in b_meta), "B_source_episode_maps_to_A")
    b_forbidden = {"stable", "acquisition", "check_success", "cps", "research_audit_only"}
    check(all(not (set(keys_recursive(r)) & b_forbidden) for r in b_meta),
          "B_metadata_audit_field_isolation")
    check(all(set(keys_recursive(r)) & {"stable", "acquisition"} for r in b_audit),
          "B_audit_contains_frozen_outcomes")
    check(a0.get("b_dataset", {}).get("status") == "PASS", "B_reported_gate_pass")

    c = {
        "protocol": PROTOCOL,
        "gate": "PASS" if not failures else "HOLD",
        "failures": failures,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "counts": {
            "A_pick_rows": len(data["A_audit"]), "A_primary_rows": len(primary),
            "A_label_unknown": sum(r["reference"] == "UNKNOWN" for r in data["A_audit"]),
            "B_trials": len(b_audit), "B_parent_events": len(b_events),
        },
        "conventional_confusion": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "metrics_display_only": {
            "tool_positive_precision_to_FGONLY": tp / (tp + fp) if tp + fp else None,
            "tool_negative_miss_risk_to_FGONLY": fn / (fn + tn) if fn + tn else None,
            "sensitivity_to_FGONLY": tp / (tp + fn) if tp + fn else None,
            "specificity_to_FGONLY": tn / (tn + fp) if tn + fp else None,
        },
        "warning": "This is independent export QA and corrected display, NOT new pre-registered outcomes analysis. "
                   "FGONLY remains a within-skill pose-following proxy.",
    }
    return c


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    script_path = Path(__file__).with_name("research_package_a.py")
    result = assess(out, script_path if script_path.exists() else None)
    # Write only supplemental QA in the already-private output directory.
    (out / "PACKAGE_A_EXPORT_QA.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    t = result["conventional_confusion"]
    rows = [
        "# Package A — conventional confusion-matrix display (post-hoc label correction only)",
        "",
        "| Original tool flag | FGONLY POSITIVE | FGONLY NEGATIVE |",
        "|---|---:|---:|",
        f"| True | {t['TP']} (TP) | {t['FP']} (FP) |",
        f"| False | {t['FN']} (FN) | {t['TN']} (TN) |",
        "",
        "**This view does not change the original sealed A0 result or its metrics.**",
        "FGONLY is a retrospective within-skill proxy, not a future grasp/hold label.",
        f"Artifact QA gate: **{result['gate']}**.",
        "",
    ]
    (out / "A0_CORRECTED_CONFUSION_DISPLAY.md").write_text(
        "\n".join(rows), encoding="utf-8")
    print(json.dumps({
        "gate": result["gate"], "checks_passed": result["checks_passed"],
        "checks_total": result["checks_total"], "failures": result["failures"],
        "counts": result["counts"], "conventional_confusion": t
    }, ensure_ascii=False, indent=2))
    if result["gate"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
