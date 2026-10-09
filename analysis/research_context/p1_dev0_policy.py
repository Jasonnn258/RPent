"""P1-DEV0 decision contract, pure and testable; NO simulator or privileged truth.

This module specifies what EACH arm is allowed to consume and return.
It intentionally does not claim an outcome or actuate robots. A runner
must implement branch actions and return-time horizons consistently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Arm = Literal["D0", "D1", "D2", "D3"]
Decision = Literal["RETRY", "CONTINUE_CAUTION", "ABSTAIN"]

# These are proposed pilot rules, not calibrated performance guarantees.
GRIP_THRESHOLD = 0.06
LIFT_THRESHOLD = 0.03
MAX_EVIDENCE_AGE_STEPS = 3


@dataclass(frozen=True)
class LegalEvidence:
    # Only values from the true Planner-visible D2 boundary/probe snapshot.
    arm: Arm
    tool_success: bool
    terminal: bool
    truncated: bool
    pre_eef_z: float | None
    post_eef_z: float | None
    post_gripper_gap: float | None
    age_env_steps: int | None
    probe_performed: bool
    visual_frame_available: bool
    budget_remaining_env_steps: int


@dataclass(frozen=True)
class DecisionRecord:
    decision: Decision
    rationale_code: str
    evidence_sources: tuple[str, ...]
    visibility: str = "observed_execution_prefix"


def choose(e: LegalEvidence) -> DecisionRecord:
    """Run on legal data, never on rtrace object pose/check_success.

    D0 and D1 use identical decision *logic*; D1's probe may change physics
    but the probe's observation must remain MASKED from the first decision.
    D2 = static gripper threshold; D3 = bounded multi-evidence claim.
    """
    if e.arm not in ("D0", "D1", "D2", "D3"):
        raise ValueError("invalid prereg arm")
    if e.terminal or e.truncated or e.tool_success is not False:
        raise ValueError("policy called outside eligible false-pick D2")
    if e.arm in ("D0", "D1"):
        return DecisionRecord("RETRY", "BLIND_RETRY_FIXED",
                              ("tool_result.success",))
    if not e.probe_performed:
        raise ValueError("D2/D3 decision requires an actual recorded probe")
    if e.budget_remaining_env_steps < 1:
        return DecisionRecord("ABSTAIN", "BUDGET_EXHAUSTED",
                              ("budget",))
    if e.post_gripper_gap is None:
        return DecisionRecord("ABSTAIN", "PROPRIO_MISSING",
                              ("state.robot0_gripper_qpos",))
    if e.arm == "D2":
        if e.post_gripper_gap < GRIP_THRESHOLD:
            return DecisionRecord("CONTINUE_CAUTION", "STATIC_GRIP_CLOSED",
                                  ("state.robot0_gripper_qpos",))
        return DecisionRecord("RETRY", "STATIC_GRIP_OPEN",
                              ("state.robot0_gripper_qpos",))
    # D3: deliberately conservative, no object pose or check_success.
    # visual_frame_available means a fresh frame exists; this pilot contract
    # does NOT interpret its pixels or verify that an object is actually held.
    if e.age_env_steps is None or e.age_env_steps > MAX_EVIDENCE_AGE_STEPS:
        return DecisionRecord("ABSTAIN", "STALE_OR_UNTIMED_EVIDENCE",
                              ("observation_timestamp",))
    if e.pre_eef_z is None or e.post_eef_z is None or not e.visual_frame_available:
        return DecisionRecord("ABSTAIN", "INSUFFICIENT_MULTI_SOURCE",
                              ("state.robot0_eef_pos", "wrist_rgb"))
    if e.post_gripper_gap < GRIP_THRESHOLD and \
            e.post_eef_z - e.pre_eef_z >= LIFT_THRESHOLD:
        return DecisionRecord("CONTINUE_CAUTION", "LEGAL_PROPRIO_PLUS_VISIBILITY_HEURISTIC",
                              ("tool_result.success", "state.robot0_gripper_qpos",
                               "state.robot0_eef_pos", "wrist_rgb"))
    return DecisionRecord("RETRY", "LEGAL_EVIDENCE_NOT_ENOUGH",
                          ("tool_result.success", "state.robot0_gripper_qpos",
                           "state.robot0_eef_pos", "wrist_rgb"))


def deny_privileged_payload(payload: dict) -> None:
    """Fail closed if audit-only/physical ground truth enters a policy payload."""
    forbidden = {
        "check_success", "obj_of_interest", "research_audit_truth",
        "reference", "reference_state", "stable_fg", "acquisition",
        "reconstruction_metadata", "sim_measurement", "target_pos",
        "object_world_pos",
    }
    def walk(value):
        if isinstance(value, dict):
            for key, v in value.items():
                if key in forbidden:
                    raise ValueError("PRIVILEGED_POLICY_INPUT:" + key)
                walk(v)
        elif isinstance(value, (tuple, list)):
            for item in value:
                walk(item)
    walk(payload)
