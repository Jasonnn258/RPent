#!/usr/bin/env python3
"""VE-v0.1.1 independent, conservative offline eligibility audit.

Research extension to (NOT replacement of) frozen VE-v0.1.
Only reads pre-existing evidence_claims JSON, never accesses simulator,
object truth, future audit, private camera buffers or control actions.

Purpose: make the distinctions "gap plateau" vs physical contact, and
"nearest rendered surface to EEF" vs TARGET OBJECT contact explicit.

Caveat: No positive held-grasp labels are available for VE-v0.1.
Every action in this prototype is advisory/offline; RETRY+ESCALATE and
RETRY+ABSTAIN are not new executed control branches.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

DEFAULT_CLAIMS = Path("/workspace/yjx/rpent_data/p1_dev0/ve01/evidence_claims.json")
DEFAULT_OUT = Path("/workspace/yjx/rpent_data/p1_dev0/ve01/safe_arms_v011.json")

def _finite_number(value):
    return type(value) in (float, int) and math.isfinite(value)

FORBIDDEN_FIELDS = {
    "check_success", "sim_measurement", "sim_measurement_obs",
    "audit_only", "research_audit_truth", "reference",
    "reference_state", "object_world_pos", "target_pos",
    "reconstruction_metadata", "stable_fg", "acquisition",
    "obj_of_interest",
}

def _contains_privileged_keys(value):
    if isinstance(value, dict):
        return any(k in FORBIDDEN_FIELDS or _contains_privileged_keys(v)
                   for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_privileged_keys(v) for v in value)
    return False

def _refuse(reason):
    return {
        "eligible": False,
        "decision": "RETRY+ABSTAIN",
        "state": "INVALID_OR_INSUFFICIENT_EVIDENCE",
        "reason": reason,
        "object_contact": "UNKNOWN",
        "held_grasp": "UNKNOWN",
        "evidence_level": "NONE",
    }

def assess(claim: dict) -> dict:
    """Fail closed and avoid converting raw sensor features to object contact.

    Source validity and timestamp must be checked BEFORE other fields.
    The presence of a depth-derived world map is geometry, not automatically
    identification of the specific target; the nearest surface could be the
    robot, table, background, a target, or a depth artifact.
    """
    if not isinstance(claim, dict):
        return _refuse("MALFORMED_CLAIM")
    if _contains_privileged_keys(claim):
        return _refuse("PRIVILEGED_FIELD_IN_CLAIM")
    if claim.get("validity") != "VALID":
        return _refuse("INVALID_SOURCE_OR_PROVENANCE")
    if str(claim.get("freshness") or "").startswith("STALE"):
        return _refuse("STALE_POST_OBSERVATION")
    if (claim.get("inter_finger_content") or {}).get("claim") != "ABSTAIN":
        return _refuse("INTER_FINGER_CONTENT_NOT_VALIDATED")

    prop = claim.get("proprio_closure")
    if not isinstance(prop, dict):
        return _refuse("MISSING_PROPRIO_EVIDENCE")
    pre = prop.get("pre_gap_m")
    post = prop.get("post_gap_m")
    if not _finite_number(pre) or not _finite_number(post) or pre < 0 or post < 0:
        return _refuse("MISSING_OR_NONFINITE_GRIPPER_GAP")
    closure = prop.get("closure_class")
    # Recalculate the historic VE01 *discretization*, only to verify input
    # consistency. These cutoffs are fit to the same five cases and are
    # not calibrated mechanical ground truth.
    if post <= .0035:
        expected_closure = "CLOSED_TO_FLOOR"
    elif post <= .0043:
        expected_closure = "AMBIGUOUS"
    else:
        expected_closure = "STALLED_ABOVE_FLOOR"
    if closure != expected_closure:
        return _refuse("GAP_AND_REPORTED_CLOSURE_DISAGREE")

    camera = claim.get("visual_camera_motion")
    if not isinstance(camera, dict) or type(camera.get("camera_motion_flag")) is not bool:
        return _refuse("UNVERIFIABLE_CAMERA_QUALITY")
    if camera["camera_motion_flag"]:
        image_status = "IMAGE_CHANGE_UNATTRIBUTABLE"
    else:
        image_status = "IMAGE_NOT_GLOBALLY_FLAGGED"
    # Motion guard is a heuristic, not proof of depth parallax. Good camera
    # quality never alone proves the object is within gripper fingers.

    geo = claim.get("geometric_context") or {}
    distance = geo.get("dist_min_m") if geo.get("usable") is True else None
    if _finite_number(distance) and 0 <= distance < .005:
        geometry = "SURFACE_NEAR_EEF_IDENTITY_UNKNOWN"
    elif _finite_number(distance) and distance >= 0:
        geometry = "SURFACE_OBSERVED_IDENTITY_UNKNOWN"
    else:
        geometry = "GEOMETRY_UNAVAILABLE"

    if closure == "STALLED_ABOVE_FLOOR":
        # A small observed gap change over 10 commands cannot distinguish
        # contact vs motor effort/servo state vs mechanical limits vs errors.
        # Historical floor inferred from three nearby examples, not an
        # independently certified gripper force/travel curve.
        state = "GAP_PLATEAU_CAUSE_UNKNOWN"
        action = "RETRY+ESCALATE"
        source = "PROPRIO_PLATEAU_ONLY"
    elif closure == "CLOSED_TO_FLOOR":
        # Thin-rim contacts with the gripper fully closed remain possible.
        state = "NEAR_MIN_GAP_OBJECT_PRESENCE_UNKNOWN"
        action = "RETRY"
        source = "PROPRIO_FLOOR_RANGE_ONLY"
    else:
        state = "CLOSURE_UNRESOLVED"
        action = "RETRY+ABSTAIN"
        source = "PROPRIO_UNKNOWN"

    return {
        "eligible": True,
        "decision": action,
        "state": state,
        "reason": "No validated probe-time held-object outcome",
        "object_contact": "UNKNOWN",
        "held_grasp": "UNKNOWN",
        "evidence_level": source,
        "image_quality": image_status,
        "geometry": geometry,
        "geometry_limit": ("Nearest EEF distance has NO target-instance/"
                           "robot-self mask; no fingertip contact claim permitted"),
        "inference_limit": ("A near-minimal gap and 10-step plateau are sensor "
                            "patterns, not independent physical contact labels"),
    }

def summarize(claims):
    if not isinstance(claims, list) or len(claims) != 5:
        raise ValueError("Expected exactly 5 already-frozen VE-v0.1 probe claims")
    names = [c.get("case") for c in claims if isinstance(c, dict)]
    if len(names) != 5 or len(set(names)) != 5:
        raise ValueError("Missing/duplicate case identifiers")
    rows = [{"case": c["case"], **assess(c)} for c in claims]
    counters = {
        "decision": dict(Counter(row["decision"] for row in rows)),
        "state": dict(Counter(row["state"] for row in rows)),
        "evidence_level": dict(Counter(row["evidence_level"] for row in rows)),
        "geometry": dict(Counter(row.get("geometry", "UNKNOWN") for row in rows)),
    }
    return {
        "protocol": "VE01.1_SAFETY_REINTERPRETATION_NONCAUSAL",
        "n_cases": 5,
        "eligible": sum(r["eligible"] for r in rows),
        "claim_holding_positive": 0,
        "independently_verified_object_contact": 0,
        "audit_truth_used": False,
        "counts": counters,
        "rows": rows,
        "limits": [
            "Source VE01 is exploratory and calibrated on the same five cases",
            "Zero positive held-grasp ground truth; cannot calculate accuracy",
            "World-point distance is not a target-instance contact classifier",
            "Gap plateau is a possible contact cue; cause remains unverified",
            "All decision outputs are offline advisory actions, never executed",
        ],
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    if args.out.resolve() == args.claims.resolve():
        p.error("Never overwrite original VE01 evidence claims")
    if not args.out.resolve().is_relative_to(Path("/workspace/yjx/rpent_data/p1_dev0/ve01").resolve()):
        p.error("Output must stay in the private VE01 derived-data directory")
    claims = json.loads(args.claims.read_text(encoding="utf-8"))["claims"]
    report = summarize(claims)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "protocol": report["protocol"],
        "n_cases": report["n_cases"],
        "eligible": report["eligible"],
        "counts": report["counts"],
        "claim_holding_positive": report["claim_holding_positive"],
        "independently_verified_object_contact": report["independently_verified_object_contact"],
        "audit_truth_used": False,
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
