#!/usr/bin/env python3
"""Read-only independent outcome/label-time availability audit for frozen DEV0.

Separate three constructs:
  probe_time_contact / probe_time_held / future_task_success.
The last may be recorded as audit-only after an unequal future window; it is
neither of the first two. Do not infer target identity from a wrist world map.

Inputs: immutable sealed P1-DEV0 manifest + per-episode event JSONL only.
Does NOT load image pixels, sim measurement values, contact forces, positions,
model weights, tools, envs or any private source beyond event envelopes.

Summaries are metadata ONLY, written beneath gitignored artifacts/p1_dev0/.
No retrospective action outcomes or simulator control are created.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = Path("/workspace/yjx/rpent_data/p1_dev0")
OUT = REPO / "artifacts/p1_dev0/ve01_label_time_audit.json"

def _events(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

# Reconcile the *recorded event schema* rather than manufacturing a zero
# label count. The audit is scoped to probe event envelopes only; it cannot
# establish absence from unrelated historical outputs or raw simulator state.
PROBE_FIELDS = {
    "ev", "arm", "probe_args", "result", "env_steps_start", "env_steps_end",
    "env_steps_cost", "wall_s", "post_legal", "post_frames",
    "visible_to_planner", "t",
}
PROBE_ARG_FIELDS = {"gripper", "steps"}
PROBE_RESULT_FIELDS = {"name", "gripper", "steps", "libero_terminated"}
PROBE_LEGAL_FIELDS = {
    "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos",
    "gripper_gap", "eef_z",
}
PROBE_FRAME_FIELDS = {"name", "path", "bytes", "sha256", "err"}


def probe_schema_unexpected_paths(probe):
    """Inspect nested KEY NAMES only; return schema paths, never sensor values."""
    unknown = []
    if not isinstance(probe, dict):
        return ["probe:not_dict"]
    unknown += ["probe." + k for k in probe if k not in PROBE_FIELDS]
    for field, allowed in (
        ("probe_args", PROBE_ARG_FIELDS),
        ("result", PROBE_RESULT_FIELDS),
        ("post_legal", PROBE_LEGAL_FIELDS),
    ):
        payload = probe.get(field)
        if not isinstance(payload, dict):
            unknown.append(field + ":missing_or_not_dict")
        else:
            unknown += [field + "." + k for k in payload if k not in allowed]
    frames = probe.get("post_frames")
    if not isinstance(frames, list):
        unknown.append("post_frames:not_list")
    else:
        for frame in frames:
            if not isinstance(frame, dict):
                unknown.append("post_frames:not_dict")
            else:
                unknown += ["post_frames." + k
                            for k in frame if k not in PROBE_FRAME_FIELDS]
    return sorted(set(unknown))


def audit(manifest, root):
    if len(manifest) != 24 or len({row["episode_key"] for row in manifest}) != 24:
        raise ValueError("require the full preregistered 24-cell DEV0 manifest")
    if any(row.get("arm") not in ("D0", "D1", "D2", "D3") for row in manifest):
        raise ValueError("nonpreregistered arm in allocation")

    counter = Counter()
    window_kinds = Counter()
    records = []
    violations = []
    for row in manifest:
        key, arm = row["episode_key"], row["arm"]
        evs = _events(root / "runs" / key / "p1_dev0_events.jsonl")
        if not evs:
            counter["no_event_file"] += 1
            continue
        counter["started_with_events"] += 1
        ev = {}
        for item in evs:
            ev.setdefault(item.get("ev"), []).append(item)
        for name in ("trigger", "probe", "audit"):
            if len(ev.get(name, [])) > 1:
                violations.append(f"{key}:multiple_{name}")
        triggers = ev.get("trigger") or []
        if not triggers:
            counter["started_not_triggered"] += 1
            continue
        counter["triggered"] += 1
        trigger = triggers[0]
        probes = ev.get("probe") or []
        audits = ev.get("audit") or []
        if bool(probes) != (arm != "D0"):
            violations.append(f"{key}:unexpected_probe_presence_for_arm")
        if not audits:
            counter["trigger_without_followup_audit"] += 1
            records.append({"episode_key": key, "arm": arm, "probe": bool(probes),
                            "probe_time_held": "UNLABELLED",
                            "probe_time_contact": "UNLABELLED",
                            "future_outcome": "AUDIT_MISSING"})
            continue
        ar = audits[0]
        typ = ar.get("kind", "UNKNOWN")
        window_kinds[typ] += 1
        outcome = ar.get("audit_only") or {}
        # Only presence, never the boolean or low-dimensional sim values.
        has_future_task = isinstance(outcome.get("check_success"), bool)
        if has_future_task:
            counter["later_task_success_observed"] += 1

        aligned_probe = False
        if probes:
            counter["probed"] += 1
            probe = probes[0]
            counter["probe_event_schemas_inspected"] += 1
            unexpected = probe_schema_unexpected_paths(probe)
            if unexpected:
                counter["probe_events_with_unreviewed_fields"] += 1
                # Aggregate only; no field names/values or private paths in
                # output. Unknown keys may encode time-aligned outcome truth.
                violations.append(f"{key}:unreviewed_probe_schema_fields")
            else:
                counter["probe_events_matching_known_schema"] += 1
            probe_end = probe.get("env_steps_end")
            followup_step = ar.get("env_steps_at_audit")
            if (type(probe_end) is int and type(followup_step) is int and
                    followup_step > probe_end):
                counter["followup_audit_strictly_after_probe"] += 1
            elif type(probe_end) is not int or type(followup_step) is not int:
                counter["probe_followup_timing_missing"] += 1
            else:
                violations.append(f"{key}:audit_not_after_probe")
            # Audited sim fields are captured only by _take_audit at the
            # future skill boundary/early end. Even equality of steps does
            # NOT yield a contact/grasp oracle without an explicit contract.
            aligned_probe = False
            # There is no verified independently measured held/contact oracle
            # in this *known* event schema. A new/unreviewed field blocks PASS
            # instead of being silently counted as an absent label.

        overshoot = ar.get("overshoot_env_steps")
        if typ == "FIXED_HORIZON":
            if type(overshoot) in (int, float) and overshoot >= 0:
                counter["future_horizon_at_or_after_target"] += 1
            else:
                violations.append(f"{key}:invalid_fixed_horizon_offset")
        elif typ == "EPISODE_END":
            if type(overshoot) in (int, float) and overshoot < 0:
                counter["early_episode_end_below_target"] += 1
            else:
                counter["episode_end_timing_not_early"] += 1
        else:
            violations.append(f"{key}:unrecognized_audit_kind")
        records.append({
            "episode_key": key, "arm": arm,
            "probe": bool(probes),
            "probe_time_contact": "UNLABELLED",
            "probe_time_held": "UNLABELLED",
            "probe_audit_time_aligned": aligned_probe,
            "future_outcome": ("LATER_TASK_SUCCESS_AUDIT_ONLY" if has_future_task
                               else "TASK_SUCCESS_FIELD_ABSENT"),
            "future_audit_kind": typ,
            "future_window_same_for_all": False,
        })

    # Do not hide the pilot's other 18 or 19 episodes in a 5-only denominator.
    counter["allocated"] = len(manifest)
    # These are verified *in-schema reference counts*, not statements about
    # every possible saved simulator file or yet-uninspected data source.
    counter["with_probe_time_held_reference"] = 0
    counter["with_probe_time_contact_reference"] = 0
    counter.setdefault("probe_events_with_unreviewed_fields", 0)
    counter.setdefault("probe_events_matching_known_schema", 0)
    expected_cohort = (
        counter["started_with_events"] == 21
        and counter["started_not_triggered"] == 15
        and counter["triggered"] == 6
        and counter["probed"] == 5
        and counter["probe_event_schemas_inspected"] == 5
        and counter["probe_events_matching_known_schema"] == 5
        and counter["probe_events_with_unreviewed_fields"] == 0
        and counter["no_event_file"] == 3
        and counter["later_task_success_observed"] == 6
        and counter["trigger_without_followup_audit"] == 0
    )
    gate = ("NO_EXPLICIT_PROBE_LABEL_IN_RECOGNIZED_EVENT_SCHEMA"
            if expected_cohort and not violations
            else "HOLD_EVENT_INTEGRITY_OR_PROBE_MISSING")
    return {
        "protocol": "VE01.1_FROZEN_DEV0_LABEL_TIME_AVAILABILITY",
        "gate": gate,
        "counts": dict(sorted(counter.items())),
        "audit_window_kinds": dict(sorted(window_kinds.items())),
        "integrity_violations": violations,
        "records": records,
        "scientific_contract": {
            "probe_time_contact": "UNLABELLED_IN_RECOGNIZED_PROBE_EVENT_SCHEMA; raw sim and other sidecar sources not exhaustively inspected",
            "probe_time_held": "UNLABELLED_IN_RECOGNIZED_PROBE_EVENT_SCHEMA; raw sim and other sidecar sources not exhaustively inspected",
            "scope": "Fields of existing P1-DEV0 probe JSONL records only. Unexpected fields force HOLD pending schema review; do not infer universal absence of historical physical labels.",
            "later_task_success": "Only the future audit-only env.check_success (when present), at first skill boundary >= H or at early episode end",
            "geometric_world_map": "Nearest visible 3D surface has no object-instance/self segmentation or target-identity guarantee",
            "offline_reference_limit": "Future-task flag, tool flag and Planner think text cannot substitute for probe-time contact/held ground truth",
            "research_implication": "Only source/temporal validity and exploratory noncausal decisions are currently evaluable, not held/contact precision or recall",
        },
    }

def main():
    from p1_dev0_posthoc_audit import verified_manifest
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-root", type=Path, default=RUNS)
    p.add_argument("--manifest", type=Path,
                   default=REPO / "artifacts/p1_dev0/manifest.jsonl")
    p.add_argument("--seal", type=Path,
                   default=REPO / "artifacts/p1_dev0/manifest.sha256.json")
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    if not args.out.resolve().is_relative_to((REPO / "artifacts").resolve()):
        p.error("Output must remain under gitignored artifacts/")
    data = audit(verified_manifest(args.manifest, args.seal), args.out_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        "protocol": data["protocol"], "gate": data["gate"],
        "counts": data["counts"],
        "audit_window_kinds": data["audit_window_kinds"],
        "integrity_violations": data["integrity_violations"],
        "scientific_contract": data["scientific_contract"],
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
