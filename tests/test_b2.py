"""Unit tests for B2 — Evidence-Sufficient State-Transition Verification.

Simulates the tool stream of episodes against the real TransitionVerifier
(rpent/memory/stv.py) and asserts on three-way verdicts, directed
observations, the bounded OBSERVE->REASON escalation, the OC-PICK
false-positive catch, latency events, forbidden-substring hygiene, and
the api_loop gate wiring.
"""

from __future__ import annotations

import json

import pytest

from rpent.memory.stv import (
    FULLY_CLOSED_EPS,
    MAX_OBSERVE_ROUNDS,
    NEVER_CLOSED_TOL,
    TransitionVerifier,
)

FORBIDDEN = ("fail", "error", "could not", "no object")


class FakeTracker:
    """Phase stand-in mirroring PhaseTracker.current_phase()."""

    def __init__(self, phase="P_init"):
        self.phase = phase

    def current_phase(self):
        return self.phase


def verifier(task="7", phase="P_init"):
    return TransitionVerifier(tracker=FakeTracker(phase), task=task)


def result(**fields):
    return json.dumps(fields)


def seg(label, xyz, step=0, found=True):
    return json.dumps(
        {"found": found, "step": step, "camera": "agentview",
         "world_xyz": list(xyz) if found else None}
    )


def driver(eef, grip_q, terminated=False):
    return json.dumps(
        {"step": 0, "task_language": "x",
         "state": {"robot0_eef_pos": list(eef),
                   "robot0_eef_quat": [0, 0, 0, 1],
                   "robot0_gripper_qpos": list(grip_q),
                   "object_names": ["mug"]},
         "libero_terminated": terminated}
    )


def check_line_hygiene(line):
    low = (line or "").lower()
    for tok in FORBIDDEN:
        assert tok not in low, f"injected line contains forbidden {tok!r}: {line}"


# ------------------------------------------------------------------ GRASP

def test_grasp_strong_proprioception_still_needs_object_evidence():
    """Blocked-apart fingers + lift is NOT confirmable alone (calibration:
    true/false hold opening distributions overlap) — observe, then the
    object riding with the gripper confirms."""
    v = verifier(phase="P_grasp")
    v.observe_result("segment", {"prompt": "red mug"}, seg("red mug", (0.4, 0.2, 0.85)))
    line = v.observe_result(
        "pi0_pick", {"prompt": "pick the red mug"},
        result(success=True, min_gripper_opening=0.035,
               final_gripper_opening=0.035, peak_lift_m=0.08,
               libero_terminated=False),
    )
    assert line and "Observe once" in line  # never confirm proprioception-only
    check_line_hygiene(line)
    assert v.n_uncertain == 1
    v.observe_result("view_driver_state", {}, driver((0.41, 0.21, 0.95), [-0.02, -0.02]))
    line = v.observe_result("segment", {"prompt": "red mug"},
                            seg("red mug", (0.41, 0.21, 0.93)))
    assert line and "CONFIRMED" in line and "do not re-grasp" in line
    check_line_hygiene(line)
    snap = v.snapshot(success=True)
    assert snap["n_confirmed_success"] == 1
    assert snap["uncertain_resolutions"]["resolved_success"] == 1


def test_grasp_never_closed_is_recover():
    v = verifier(phase="P_grasp")
    line = v.observe_result(
        "pi0_pick", {"prompt": "pick"},
        result(success=False, min_gripper_opening=0.09,
               final_gripper_opening=0.09, peak_lift_m=0.0,
               libero_terminated=False),
    )
    assert line and "NOT established" in line and "Recover" in line
    check_line_hygiene(line)
    assert v.n_failure == 1


def test_grasp_pin_shut_false_positive_caught():
    """The B1 heldout failure mode: gripper closed on nothing (min opening
    ~0), B1 would say MATCHED; B2 must demand observation and then confirm
    FAILURE when the object stayed on its support."""
    v = verifier(phase="P_grasp")
    pre = v.observe_result("segment", {"prompt": "red mug"},
                           seg("red mug", (0.40, 0.20, 0.85)))
    assert pre is None
    line = v.observe_result(
        "pi0_pick", {"prompt": "pick the red mug"},
        result(success=True, min_gripper_opening=0.001,
               final_gripper_opening=0.001, peak_lift_m=0.07,
               libero_terminated=False),
    )
    # B1's check (min_gripper_opening < 0.03 or success) would MATCH here.
    assert line and "Observe once" in line
    check_line_hygiene(line)
    assert v.n_uncertain == 1 and v.n_observe_directives == 1
    # The directed observation: object still at the support position.
    line2 = v.observe_result("segment", {"prompt": "red mug"},
                             seg("red mug", (0.40, 0.21, 0.85)))
    assert line2 and "NOT established" in line2
    check_line_hygiene(line2)
    assert v.false_positive_caught == 1
    snap = v.snapshot(success=False)
    assert snap["uncertain_resolutions"]["resolved_failure"] == 1


def test_grasp_pin_shut_rescued_by_observation():
    """Same suspicious closure, but the object DID move with the gripper —
    B2 resolves to CONFIRMED_SUCCESS instead of blocking."""
    v = verifier(phase="P_grasp")
    v.observe_result("segment", {"prompt": "red mug"},
                     seg("red mug", (0.40, 0.20, 0.85)))
    v.observe_result(
        "pi0_pick", {"prompt": "pick the red mug"},
        result(success=True, min_gripper_opening=0.002,
               final_gripper_opening=0.002, peak_lift_m=0.07,
               libero_terminated=False),
    )
    v.observe_result("view_driver_state", {},
                     driver((0.41, 0.21, 0.95), [-0.001, 0.001]))
    line = v.observe_result("segment", {"prompt": "red mug"},
                            seg("red mug", (0.41, 0.21, 0.94)))
    assert line and "CONFIRMED" in line
    check_line_hygiene(line)
    assert v.uncertain_resolutions["resolved_success"] == 1
    assert v.false_positive_caught == 0


def test_grasp_no_lift_stays_uncertain_then_reason():
    """Closure + no ascent and an object displacement in the ambiguous band
    (between stay-tol and move-tol): no observation resolves it -> bounded
    OBSERVE x2 then REASON."""
    v = verifier(phase="P_grasp")
    v.observe_result("segment", {"prompt": "mug"}, seg("mug", (0.4, 0.2, 0.85)))
    line = v.observe_result(
        "pi0_pick", {"prompt": "pick"},
        result(success=False, min_gripper_opening=0.03,
               final_gripper_opening=0.03, peak_lift_m=0.01,
               libero_terminated=False),
    )
    assert line and "Observe once" in line
    # round 1: inconclusive (0.035 m — between stay-tol and move-tol)
    line = v.observe_result("segment", {"prompt": "mug"},
                            seg("mug", (0.435, 0.2, 0.85)))
    assert line and "Observe once" in line
    # round 2: still inconclusive -> REASON
    line = v.observe_result("segment", {"prompt": "mug"},
                            seg("mug", (0.435, 0.2, 0.851)))
    assert line and "Reason explicitly" in line
    check_line_hygiene(line)
    assert v.n_reason_escalations == 1
    assert v.uncertain_resolutions["resolved_reason"] == 1
    assert v._pending is None


def test_grasp_segment_not_found_escalates():
    v = verifier(phase="P_grasp")
    v.observe_result("segment", {"prompt": "mug"}, seg("mug", (0.4, 0.2, 0.85)))
    v.observe_result(
        "pi0_pick", {"prompt": "pick"},
        result(success=True, min_gripper_opening=0.001,
               final_gripper_opening=0.001, peak_lift_m=0.06,
               libero_terminated=False),
    )
    line = v.observe_result("segment", {"prompt": "mug"},
                            seg("mug", (0, 0, 0), found=False))
    assert line and "Observe once" in line  # round 1: no usable position
    line = v.observe_result("segment", {"prompt": "mug"},
                            seg("mug", (0, 0, 0), found=False))
    assert line and "Reason explicitly" in line


# ------------------------------------------------------------------- PLACE

def test_place_gripper_did_not_open_is_recover():
    v = verifier(phase="P_place")
    line = v.observe_result(
        "release", {},
        result(peak_gripper_opening=0.02, start_gripper_opening=0.03,
               final_gripper_opening=0.03, libero_terminated=False),
    )
    assert line and "NOT established" in line
    check_line_hygiene(line)


def test_place_confirmed_near_transport_target():
    v = verifier(phase="P_place")
    v.observe_result("move_to", {"xyz": [0.5, 0.3, 0.9]},
                     result(final_dist_m=0.01, libero_terminated=False))
    line = v.observe_result(
        "release", {},
        result(peak_gripper_opening=0.08, start_gripper_opening=0.03,
               final_gripper_opening=0.08, libero_terminated=False),
    )
    assert line and "Observe once" in line
    line = v.observe_result("segment", {"prompt": "mug"},
                            seg("mug", (0.52, 0.31, 0.86)))
    assert line and "CONFIRMED" in line
    check_line_hygiene(line)
    assert v.uncertain_resolutions["resolved_success"] == 1


def test_place_dropped_far_from_target():
    v = verifier(phase="P_place")
    v.observe_result("move_to", {"xyz": [0.5, 0.3, 0.9]},
                     result(final_dist_m=0.01, libero_terminated=False))
    v.observe_result("release", {},
                     result(peak_gripper_opening=0.08,
                            final_gripper_opening=0.08,
                            libero_terminated=False))
    v.observe_result("view_driver_state", {}, driver((0.5, 0.3, 0.9), [0.04, 0.04]))
    line = v.observe_result("segment", {"prompt": "mug"},
                            seg("mug", (0.1, -0.2, 0.86)))
    assert line and "NOT established" in line
    assert v.n_failure == 1


def test_terminated_short_circuits_to_commit():
    v = verifier(phase="P_place")
    line = v.observe_result(
        "release", {},
        result(peak_gripper_opening=0.08, libero_terminated=True),
    )
    assert line and "CONFIRMED" in line and "finish" in line


# --------------------------------------------------------------- TRANSPORT

def test_transport_arrival_and_miss():
    v = verifier(phase="P_transport")
    line = v.observe_result("move_to", {"xyz": [0.5, 0.3, 0.9]},
                            result(final_dist_m=0.01, libero_terminated=False))
    assert line and "CONFIRMED" in line
    line = v.observe_result("move_to", {"xyz": [0.6, 0.3, 0.9]},
                            result(final_dist_m=0.12, libero_terminated=False))
    assert line and "NOT established" in line and "re-localize" in line
    check_line_hygiene(line)


# ---------------------------------------------------------------- CONTACT

def test_contact_success_and_miss():
    v = verifier(phase="P_place")
    line = v.observe_result("pi0_doubled", {"prompt": "place"},
                            result(success=True, libero_terminated=True))
    assert line and "CONFIRMED" in line
    line = v.observe_result("pi0_doubled", {"prompt": "place"},
                            result(success=False, libero_terminated=False))
    assert line and "NOT established" in line


# ---------------------------------------------------- bounded control flow

def test_pending_overtaken_by_next_action():
    """Planner proceeds without the directed observation: recorded, cleared,
    and the next action is judged normally."""
    v = verifier(phase="P_grasp")
    v.observe_result("pi0_pick", {"prompt": "pick"},
                     result(success=True, min_gripper_opening=0.001,
                            final_gripper_opening=0.001, peak_lift_m=0.06,
                            libero_terminated=False))
    line = v.observe_result("move_to", {"xyz": [0.5, 0.3, 0.9]},
                            result(final_dist_m=0.01, libero_terminated=False))
    assert line and "CONFIRMED" in line
    assert v.uncertain_resolutions["overtaken"] == 1
    assert v._pending is None


def test_turn_boundary_hint_escalates_stalled_pending():
    v = verifier(phase="P_grasp")
    v.observe_result("pi0_pick", {"prompt": "pick"},
                     result(success=True, min_gripper_opening=0.001,
                            final_gripper_opening=0.001, peak_lift_m=0.06,
                            libero_terminated=False))
    # planner idles in unrelated tools — no action, no directed observation
    hints = []
    for _ in range(6):
        hints.append(v.turn_boundary_hint())
        v.observe_result("view_camera_meta", {}, result(note="calibration"))
    escalated = [h for h in hints if h is not None]
    assert escalated and "Reason explicitly" in escalated[0]
    hint = escalated[0]
    check_line_hygiene(hint)
    assert v.turn_boundary_hint() is None  # one-shot


def test_rotate_quiet_success_and_loud_failure():
    v = verifier(phase="P_transport")
    line = v.observe_result("rotate_wrist", {"target_yaw": 1.0},
                            result(final_err=0.01, libero_terminated=False))
    assert line is None  # quiet success: no behavior change needed
    evs = [e for e in v.events if e["action"] == "rotate_wrist"]
    assert evs and evs[0]["verdict"] == "CONFIRMED_SUCCESS"
    line = v.observe_result("rotate_wrist", {"target_yaw": 1.0},
                            result(final_err=0.15, libero_terminated=False))
    assert line and "NOT established" in line


# ------------------------------------------------------------ hygiene/io

def test_all_injected_lines_avoid_forbidden_substrings():
    """End-to-end stream mixing every verdict kind."""
    v = verifier(phase="P_grasp")
    lines = []
    v.observe_result("segment", {"prompt": "mug"}, seg("mug", (0.4, 0.2, 0.85)))
    lines.append(v.observe_result(
        "pi0_pick", {"prompt": "p"},
        result(success=True, min_gripper_opening=0.001,
               final_gripper_opening=0.001, peak_lift_m=0.06,
               libero_terminated=False)))
    lines.append(v.observe_result("segment", {"prompt": "mug"},
                                  seg("mug", (0.4, 0.2, 0.85))))
    lines.append(v.observe_result(
        "pi0_pick", {"prompt": "p"},
        result(success=False, min_gripper_opening=0.09,
               final_gripper_opening=0.09, peak_lift_m=0.0,
               libero_terminated=False)))
    lines.append(v.observe_result("move_to", {"xyz": [0.5, 0.3, 0.9]},
                                  result(final_dist_m=0.2,
                                         libero_terminated=False)))
    lines.append(v.observe_result("release", {},
                                  result(peak_gripper_opening=0.01,
                                         libero_terminated=False)))
    for line in lines:
        check_line_hygiene(line)


def test_event_log_fields(tmp_path, monkeypatch):
    """Every emitted event carries the full spec field set."""
    from rpent.utils import logging as rlog

    monkeypatch.setattr(rlog, "get_output_dir", lambda: str(tmp_path))
    v = verifier(task="0")
    v.observe_result("pi0_pick", {"prompt": "p"},
                     result(success=True, min_gripper_opening=0.001,
                            final_gripper_opening=0.001, peak_lift_m=0.06,
                            libero_terminated=False))
    raw = (tmp_path / "b2_events.jsonl").read_text().strip().splitlines()
    assert raw
    ev = json.loads(raw[0])
    for field in (
        "episode", "task", "seed", "repeat", "turn", "phase",
        "pre_state_summary", "action", "expected_change", "observed_change",
        "evidence_for_success", "evidence_for_failure", "missing_evidence",
        "verdict", "next_decision", "confidence", "verification_source",
        "rule_template",
    ):
        assert field in ev, f"missing {field}"
    assert ev["rule_template"] == "GRASP"
    assert ev["b1_style_would_match"] is True
    assert ev["verdict"] == "UNCERTAIN"


def test_latency_events_close_on_phase_advance_and_switch():
    v = verifier(phase="P_transport")
    # arrival = confirmed success -> commit event opens
    v.observe_result("move_to", {"xyz": [0.5, 0.3, 0.9]},
                     result(final_dist_m=0.01, libero_terminated=False))
    v._tracker.phase = "P_place"  # phase advanced -> commit closes
    # a miss = confirmed failure -> recovery event opens (same tool stays open)
    v.observe_result("move_to", {"xyz": [0.6, 0.3, 0.9]},
                     result(final_dist_m=0.2, libero_terminated=False))
    # a different action tool -> recovery closes as strategy switch
    v.observe_result("release", {},
                     result(peak_gripper_opening=0.08, libero_terminated=False))
    snap = v.snapshot(success=False)
    assert snap["commit_events"] and snap["commit_events"][0]["closed_by"] == \
        "phase_advanced"
    assert snap["recovery_events"]
    assert snap["recovery_events"][0]["closed_by"] == "switch"


def test_snapshot_counts():
    v = verifier()
    v.observe_result("pi0_pick", {"prompt": "p"},
                     result(success=True, min_gripper_opening=0.001,
                            final_gripper_opening=0.001, peak_lift_m=0.06,
                            libero_terminated=False))
    snap = v.snapshot(success=False)
    assert snap["b2"] is True
    assert snap["n_uncertain"] == 1
    assert snap["uncertain_resolutions"]["unresolved"] == 1


# ------------------------------------------------------------------ gates

def test_gate_off_by_default(monkeypatch):
    from rpent.planner import api_loop

    monkeypatch.delenv("RPENT_OVPM2", raising=False)
    monkeypatch.delenv("RPENT_OVPM", raising=False)
    assert api_loop._new_b2_verifier(object()) is None


def test_gate_requires_tracker(monkeypatch):
    from rpent.planner import api_loop

    monkeypatch.setenv("RPENT_OVPM2", "1")
    assert api_loop._new_b2_verifier(None) is None


def test_gate_independent_of_arm_b(monkeypatch):
    """RPENT_OVPM (arm B) must not activate B2, and vice versa."""
    from rpent.planner import api_loop

    monkeypatch.setenv("RPENT_STRUCTURED_MEMORY", "1")
    monkeypatch.setenv("RPENT_OVPM", "1")
    monkeypatch.delenv("RPENT_OVPM2", raising=False)
    assert api_loop._new_b2_verifier(object()) is None

    monkeypatch.delenv("RPENT_OVPM", raising=False)
    monkeypatch.setenv("RPENT_OVPM2", "1")
    v = api_loop._new_b2_verifier(object())
    assert isinstance(v, TransitionVerifier)


# ------------------------------------------------------------- thresholds

def test_threshold_sanity():
    """The suspicious band and B1's tight-grip threshold must overlap —
    that overlap is precisely the false-positive class B2 re-checks."""
    assert FULLY_CLOSED_EPS < 0.03  # pin-shut is inside B1's MATCHED zone
    assert NEVER_CLOSED_TOL > 0.05  # B1's released threshold, different axis
    assert MAX_OBSERVE_ROUNDS == 2
