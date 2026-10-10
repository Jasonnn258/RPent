#!/usr/bin/env python3
"""DEV1A G1/G2 audit-only operational contact/retention reference.

Pure mock-testable research code, not a simulator adapter or online verifier.
No source of truth is invented: all object/geom IDs, contact pairs, and poses
must come from the live simulator at the SAME env tick. If unavailable,
reject/return UNKNOWN. Do not substitute gripper gap, nearest depth surface,
tool success or plan text.

DEV1A D-041 has max 0.02 m safeguarded vertical lift. Any resulting "held"
labels are simulator operational labels ONLY; not independent real-world grasps.
"""
from __future__ import annotations

import math
from typing import Any

CONTACTS = ("BILATERAL", "SINGLE", "NONE", "UNKNOWN")
RETENTION = ("RETAINED", "NOT_RETAINED", "UNKNOWN")
# Predeclared for feasibility only, never adapted to measured cases:
MIN_OBJECT_LIFT_M = .010
MAX_RELATIVE_TRANSLATION_M = .010
MIN_VALID_LIFT_SAMPLES = 3


def _vec3(value):
    if not isinstance(value, (list,tuple)) or len(value)!=3:
        return None
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in value):
        return None
    return tuple(float(x) for x in value)


def _geom_ids(value):
    if not isinstance(value, list) or not value:
        return None
    if any(type(v) is not int or v<0 for v in value):
        return None
    out=set(value)
    return out if len(out)==len(value) else None


def _pairs(value):
    if not isinstance(value,list):
        return None
    result=set()
    for item in value:
        if not isinstance(item,(list,tuple)) or len(item)!=2:
            return None
        a,b=item
        if type(a) is not int or type(b) is not int or a<0 or b<0:
            return None
        result.add((min(a,b),max(a,b)))
    return result


def _touches(pairs, left, right):
    return any(tuple(sorted((a,b))) in pairs for a in left for b in right)


def validate_snapshot(snap: Any):
    """Validate atomic audit snapshot; no missing contact list accepted.

    All four *_env_step fields must equal. This is a *structural* same-tick
    test; the live adapter must prove reads do not advance the sim.
    """
    if not isinstance(snap,dict):
        return False
    steps=("env_step","contact_env_step","pose_env_step","image_env_step")
    if any(type(snap.get(k)) is not int or snap[k]<0 for k in steps):
        return False
    if len({snap[k] for k in steps}) != 1:
        return False
    if not isinstance(snap.get("target_instance"),str) or not snap["target_instance"]:
        return False
    geoms={k:_geom_ids(snap.get(k)) for k in
           ("target_geom_ids","left_finger_geom_ids",
            "right_finger_geom_ids","support_geom_ids")}
    if any(v is None for v in geoms.values()):
        return False
    allsets=list(geoms.values())
    if any(a & b for i,a in enumerate(allsets) for b in allsets[i+1:]):
        return False
    if _pairs(snap.get("contacts")) is None:
        return False
    if _vec3(snap.get("target_pos")) is None or _vec3(snap.get("eef_pos")) is None:
        return False
    return True


def contact_state(snap):
    """Classify target-specific simultaneous left/right finger contact.

    The environment's geom IDs must be independently verified upstream.
    'NONE' requires a valid full contact snapshot, not just a missing field.
    """
    if not validate_snapshot(snap):
        return {"contact":"UNKNOWN", "supported":"UNKNOWN",
                "reason":"MISSING_OR_UNALIGNED_SIM_CONTACT_TRUTH"}
    pairs=_pairs(snap["contacts"])
    target=set(snap["target_geom_ids"])
    l=set(snap["left_finger_geom_ids"])
    r=set(snap["right_finger_geom_ids"])
    support=set(snap["support_geom_ids"])
    lc=_touches(pairs,l,target)
    rc=_touches(pairs,r,target)
    cls="BILATERAL" if lc and rc else ("SINGLE" if lc or rc else "NONE")
    supported=_touches(pairs,target,support)
    return {"contact":cls, "supported":supported, "reason":None}


def retention_state(close_end, lift_samples):
    """Simulator-operational retained status: never infer from contact alone.

    Use minimum 3 successive *measured* lift-window snapshots with strictly
    increasing simulator step. All snapshots must represent one target and
    each have independently resolved target/finger/support IDs.
    """
    if not validate_snapshot(close_end) or not isinstance(lift_samples,list) or \
            len(lift_samples)<MIN_VALID_LIFT_SAMPLES:
        return {"retained":"UNKNOWN", "reason":"INSUFFICIENT_ALIGNED_AUDIT"}
    series=[close_end]+lift_samples
    if any(not validate_snapshot(p) for p in series):
        return {"retained":"UNKNOWN", "reason":"INCOMPLETE_SIM_CONTACT"}
    steps=[p["env_step"] for p in series]
    if any(b<=a for a,b in zip(steps,steps[1:])):
        return {"retained":"UNKNOWN", "reason":"INVALID_TEMPORAL_ORDER"}
    ids={p["target_instance"] for p in series}
    if len(ids)!=1:
        return {"retained":"UNKNOWN", "reason":"TARGET_ID_SWITCH"}
    # Contact metadata must represent the SAME bodies across each timestamp.
    for key in ("target_geom_ids","left_finger_geom_ids",
                "right_finger_geom_ids","support_geom_ids"):
        if any(set(p[key])!=set(close_end[key]) for p in lift_samples):
            return {"retained":"UNKNOWN", "reason":"GEOM_MAPPING_CHANGED"}
    statuses=[contact_state(p) for p in lift_samples]
    if any(s["contact"]=="UNKNOWN" for s in statuses):
        return {"retained":"UNKNOWN", "reason":"UNKNOWN_CONTACT"}
    start=_vec3(close_end["target_pos"])
    finish=_vec3(lift_samples[-1]["target_pos"])
    obj_lift=finish[2]-start[2]
    # Relative translation drift is assessed over the *lift window*, not
    # versus close_end alone; the gripper may legitimately move while lifting.
    relative=[
        tuple(o-e for o,e in zip(_vec3(p["target_pos"]),_vec3(p["eef_pos"])))
        for p in lift_samples
    ]
    anchor=relative[0]
    max_drift=max(math.dist(anchor,v) for v in relative)
    has_support=any(s["supported"] for s in statuses)
    all_bilateral=all(s["contact"]=="BILATERAL" for s in statuses)
    if has_support:
        return {"retained":"NOT_RETAINED","reason":"TARGET_STILL_SUPPORTED"}
    if obj_lift>=MIN_OBJECT_LIFT_M and all_bilateral and \
            max_drift <= MAX_RELATIVE_TRANSLATION_M:
        return {"retained":"RETAINED","reason":"SIM_OPERATIONAL_CONTACT_AND_MOTION"}
    if all(s["contact"]=="NONE" for s in statuses) or \
            obj_lift < MIN_OBJECT_LIFT_M:
        return {"retained":"NOT_RETAINED","reason":"NO_GRASP_CONTACT_OR_LIFT"}
    return {"retained":"UNKNOWN","reason":"AMBIGUOUS_CONTACT_OR_DRIFT"}


def prohibit_audit_leak(legal_record):
    """Fail closed on unknown fields, including recursively nested oracle keys.

    legal evidence contains strictly envelopes of stamped visual/proprio
    observations; do not let server truth flow into Planner/Memory/Tool.
    """
    keys={"env_step","rgb_sha256","wrist_sha256","gripper_gap",
          "eef_pos","eef_quat","source","fresh","validity"}
    if not isinstance(legal_record,dict) or set(legal_record)-keys:
        raise ValueError("UNAPPROVED_LEGAL_EVIDENCE_FIELD")
    if (type(legal_record.get("env_step")) is not int or
            not isinstance(legal_record.get("source"),str) or
            legal_record.get("fresh") is not True or
            legal_record.get("validity")!="VALID"):
        raise ValueError("INVALID_OR_STALE_LEGAL_EVIDENCE")
    if _vec3(legal_record.get("eef_pos")) is None:
        raise ValueError("MISSING_EEF_POSE")
    for key in ("rgb_sha256","wrist_sha256"):
        v=legal_record.get(key)
        if type(v) is not str or len(v)!=64 or any(ch not in "0123456789abcdef" for ch in v):
            raise ValueError("MISSING_FRESH_IMAGE_HASH")
    return True
