"""Unit tests for Outcome-Validated Procedural Memory (OVP-M, arm B).

Simulates the tool stream of full episodes against the real v2 rules
document and asserts on verdict computation, zero-turn injection content,
latency events, counters, and the api_loop gate wiring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpent.memory.ovpm import (
    OutcomeValidator,
    load_contracts,
    parse_contracts,
)
from rpent.memory.structured import PhaseTracker, load_rules

V1_PATH = Path("analysis/structured_rules_v1.json")
V2_PATH = Path("analysis/structured_rules_v2.json")


@pytest.fixture(scope="module")
def contracts():
    return load_contracts(V2_PATH)


@pytest.fixture(scope="module")
def rules():
    return load_rules(V2_PATH)


class FakeTracker:
    """Phase stand-in mirroring PhaseTracker.current_phase()."""

    def __init__(self, phase="P_init"):
        self.phase = phase

    def current_phase(self):
        return self.phase


def validator(contracts, task="7", phase="P_init"):
    v = OutcomeValidator(contracts, tracker=FakeTracker(phase), task=task)
    return v


def result(**fields):
    return json.dumps(fields)


# ---------------------------------------------------------------- document

def test_v2_phases_identical_to_v1():
    v1 = json.loads(V1_PATH.read_text())
    v2 = json.loads(V2_PATH.read_text())
    assert v2["phases"] == v1["phases"], "v2 must not touch the frozen rules"


def test_v2_has_expected_contracts(contracts):
    ids = {c.id for c in contracts}
    assert ids == {
        "OC-MOVE", "OC-PICK", "OC-RELEASE", "OC-RELEASE-T9",
        "OC-DOUBLED", "OC-SETGRIP", "OC-VERIFY", "OC-STATE-PLACE",
    }


def test_task9_prefers_scoped_release_contract(contracts):
    v9 = validator(contracts, task="9", phase="P_place")
    c = v9._contract_for("release", "P_place")
    assert c.id == "OC-RELEASE-T9"
    v7 = validator(contracts, task="7", phase="P_place")
    assert v7._contract_for("release", "P_place").id == "OC-RELEASE"


def test_parse_rejects_unknown_tool():
    with pytest.raises(ValueError):
        parse_contracts({"outcome_contracts": [
            dict(id="X", tool="nope", expected_outcome="e",
                 verify={"kind": "no_exception"}, on_match="m",
                 on_mismatch="r"),
        ]})


def test_parse_rejects_unknown_kind():
    with pytest.raises(ValueError):
        parse_contracts({"outcome_contracts": [
            dict(id="X", tool="release", expected_outcome="e",
                 verify={"kind": "oracle_gt"}, on_match="m", on_mismatch="r"),
        ]})


def test_parse_rejects_forbidden_substrings():
    with pytest.raises(ValueError):
        parse_contracts({"outcome_contracts": [
            dict(id="X", tool="release", expected_outcome="e",
                 verify={"kind": "released"}, on_match="m",
                 on_mismatch="it failed"),
        ]})


# ------------------------------------------------------------ verdict math

def test_pick_matched_via_success(contracts):
    v = validator(contracts, phase="P_grasp")
    line = v.observe_result("pi0_pick", {}, result(success=True,
                                                   min_gripper_opening=0.09))
    assert line is not None and "MATCHED" in line and "Commit" in line


def test_pick_matched_via_tight_grip(contracts):
    v = validator(contracts, phase="P_grasp")
    line = v.observe_result("pi0_pick", {}, result(success=False,
                                                   min_gripper_opening=0.01))
    assert line is not None and "MATCHED" in line


def test_pick_mismatch(contracts):
    v = validator(contracts, phase="P_grasp")
    line = v.observe_result("pi0_pick", {}, result(success=False,
                                                   min_gripper_opening=0.08))
    assert "MISMATCH (1st)" in line


def test_pick_uncertain_when_fields_missing(contracts):
    v = validator(contracts, phase="P_grasp")
    assert v.observe_result("pi0_pick", {}, "not json") is None
    assert v.n_uncertain == 1
    assert v.observe_result("pi0_pick", {}, result(chunks_used=3)) is None
    assert v.n_uncertain == 2


def test_tool_exception_is_mismatch(contracts):
    v = validator(contracts, phase="P_grasp")
    line = v.observe_result("pi0_pick", {}, '{"error": "boom"}', is_error=True)
    assert "MISMATCH" in line


def test_release_threshold(contracts):
    v = validator(contracts, phase="P_place")
    ok = v.observe_result("release", {}, result(peak_gripper_opening=0.08,
                                                libero_terminated=False))
    bad = v.observe_result("release", {}, result(peak_gripper_opening=0.02,
                                                 libero_terminated=False))
    assert "MATCHED" in ok and "MISMATCH" in bad


def test_move_advisory_contract_silent_on_match(contracts):
    v = validator(contracts, phase="P_transport")
    assert v.observe_result("move_to", {}, result(final_dist_m=0.005)) is None
    assert v.n_matched == 1  # counted, not injected
    bad = v.observe_result("move_to", {}, result(final_dist_m=0.12))
    assert "MISMATCH" in bad and "R3" in bad


def test_verify_reads_nested_log_result(contracts):
    v = validator(contracts, phase="P_verify")
    payload = json.dumps({"libero_terminated": None,
                          "log": {"result": {"libero_terminated": True}}})
    line = v.observe_result("view_driver_state", {}, payload)
    assert "MATCHED" in line and "finish" in line


def test_set_gripper_silent_until_terminated(contracts):
    v = validator(contracts, phase="P_place")
    assert v.observe_result("set_gripper", {}, result(libero_terminated=False)) is None
    line = v.observe_result("set_gripper", {}, result(libero_terminated=True))
    assert "MATCHED" in line


def test_no_verdict_outside_contract_phase(contracts):
    v = validator(contracts, phase="P_look")
    assert v.observe_result("view_driver_state", {},
                            result(libero_terminated=True)) is None
    assert v.observe_result("pi0_pick", {}, result(success=True)) is None


def test_injected_lines_avoid_tracker_tripwords(contracts):
    v = validator(contracts, phase="P_place")
    lines = [
        v.observe_result("release", {}, result(peak_gripper_opening=0.01)),
        v.observe_result("release", {}, result(peak_gripper_opening=0.01)),
        v.observe_result("pi0_doubled", {}, result(success=False)),
    ]
    for line in lines:
        if line:
            assert "fail" not in line and "error" not in line


# ------------------------------------------------------- injection throttle

def test_commit_hint_once_per_phase(contracts):
    v = validator(contracts, phase="P_grasp")
    assert v.observe_result("pi0_pick", {}, result(success=True)) is not None
    assert v.observe_result("pi0_pick", {}, result(success=True)) is None


def test_finish_target_commit_repeats(contracts):
    """The verify-stall killer: every confirmed termination re-nudges finish."""
    v = validator(contracts, phase="P_verify")
    first = v.observe_result("view_driver_state", {},
                             result(libero_terminated=True))
    second = v.observe_result("view_driver_state", {},
                              result(libero_terminated=True))
    assert first is not None and second is not None


def test_consecutive_mismatch_escalates(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    second = v.observe_result("pi0_pick", {}, result(success=False,
                                                     min_gripper_opening=0.09))
    assert "MISMATCH (2nd)" in second
    assert "discouraged" in second


# ------------------------------------------------------------------ latency

def test_perception_does_not_close_recovery(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    v.observe_result("back_project", {}, result(xyz=[0.1, 0.2, 0.3]))
    v.observe_result("segment", {}, result(mask=1))
    snap = v.snapshot(success=False)
    assert snap["n_mismatched"] == 1
    # recovery still open at episode end => unclosed, no latency
    assert snap["recovery_events"][0]["closed_by"] == "unclosed"


def test_strategy_switch_closes_recovery(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    v.observe_result("rotate_wrist", {}, result(final_yaw=0.5))
    snap = v.snapshot(success=False)
    ev = snap["recovery_events"][0]
    assert ev["closed_by"] == "switch" and ev["latency_steps"] == 1
    assert snap["mismatch_escalations"] == 1


def test_same_tool_resolution_closes_recovery(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    v.observe_result("pi0_pick", {}, result(success=True))
    snap = v.snapshot(success=False)
    assert snap["recovery_events"][0]["closed_by"] == "same_tool_resolved"
    assert snap["repeated_same_strategy_after_mismatch"] == 0


def test_repeated_same_strategy_counted(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.09))
    snap = v.snapshot(success=False)
    assert snap["repeated_same_strategy_after_mismatch"] == 1


def test_commit_closes_on_phase_advance(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=True))
    v._tracker.phase = "P_place"  # phase advanced (tracker recomputed)
    v.observe_result("move_to", {}, result(final_dist_m=0.01))
    snap = v.snapshot(success=True)
    assert snap["commit_events"][0]["closed_by"] == "phase_advanced"
    assert snap["commit_events"][0]["latency_steps"] == 1


def test_finish_closes_open_events(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=True))
    v.observe_result("finish", {"status": "success"}, result(status="success"))
    snap = v.snapshot(success=True)
    assert snap["commit_events"][0]["closed_by"] == "finish"


def test_turn_boundary_hint_throttled(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=True))
    v.observe_result("segment", {}, result(mask=1))  # step +1: no hint yet
    assert v.turn_boundary_hint() is None
    v.observe_result("view_driver_state", {}, result(step=2))  # step +2
    hint = v.turn_boundary_hint()
    assert hint is not None and "verified MATCHED" in hint
    assert v.turn_boundary_hint() is None  # once per open commit


def test_snapshot_means(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    v.observe_result("pi0_pick", {}, result(success=True))
    snap = v.snapshot(success=True)
    assert snap["n_matched"] == 1 and snap["n_mismatched"] == 1
    assert snap["recovery_latency_mean"] == 1.0
    assert snap["commit_latency_mean"] is None  # still open -> unclosed


# ------------------------------------------------------------ api_loop gate

def test_gate_off_returns_none(monkeypatch):
    from rpent.planner.api_loop import _new_outcome_validator
    monkeypatch.delenv("RPENT_OVPM", raising=False)
    assert _new_outcome_validator(object()) is None


def test_gate_needs_tracker(monkeypatch):
    from rpent.planner.api_loop import _new_outcome_validator
    monkeypatch.setenv("RPENT_OVPM", "1")
    assert _new_outcome_validator(None) is None


def test_gate_on_builds_validator(monkeypatch):
    from rpent.planner.api_loop import _new_outcome_validator
    monkeypatch.setenv("RPENT_OVPM", "1")
    monkeypatch.setenv("RPENT_OVPM_CONTRACTS", str(V2_PATH))
    v = _new_outcome_validator(FakeTracker("P_place"))
    assert v is not None and len(v._contracts) == 8


def test_missing_contracts_file_is_noop(monkeypatch, tmp_path):
    from rpent.planner.api_loop import _new_outcome_validator
    monkeypatch.setenv("RPENT_OVPM", "1")
    monkeypatch.setenv("RPENT_OVPM_CONTRACTS", str(tmp_path / "nope.json"))
    v = _new_outcome_validator(FakeTracker("P_place"))
    assert v is not None and v._contracts == []


def test_gate_without_structured_memory_tracker_none(monkeypatch):
    """RPENT_OVPM=1 but no tracker (RPENT_STRUCTURED_MEMORY unset) => off."""
    from rpent.planner.api_loop import _new_phase_tracker, _new_outcome_validator
    monkeypatch.delenv("RPENT_STRUCTURED_MEMORY", raising=False)
    monkeypatch.setenv("RPENT_OVPM", "1")
    tracker = _new_phase_tracker(max_turns=40)
    assert tracker is None
    assert _new_outcome_validator(tracker) is None


# ----------------------------------------------- integration with PhaseTracker

def test_end_to_end_t7_stall_episode(contracts, rules):
    """t7 place_stall shape: place matches, verify matches, model stalls. The
    verify contract must keep re-nudging finish, and no recovery may open."""
    tracker = PhaseTracker([r for r in rules if r.applies_to_task("7")],
                           task="7", max_turns=40)
    v = OutcomeValidator(contracts, tracker=tracker, task="7")
    stream = [
        ("view_driver_state", result(step=0), False),           # P_look
        ("back_project", result(xyz=[0.1, 0.2, 0.3]), False),
        ("move_to", result(final_dist_m=0.01), False),          # P_transport
        ("pi0_pick", result(success=True, min_gripper_opening=0.01), False),
        ("move_to", result(final_dist_m=0.008), False),
        ("release", result(peak_gripper_opening=0.09,
                           libero_terminated=True), False),     # P_place->P_verify
        ("view_driver_state", result(libero_terminated=True,
                                     log={"result": {}}), False),
        ("view_driver_state", result(libero_terminated=True,
                                     log={"result": {}}), False),  # stall
        ("finish", result(status="success"), False),
    ]
    finish_nudges = 0
    for name, text, is_err in stream:
        tracker.on_tool_call(name, {})
        line = v.observe_result(name, {}, text, is_error=is_err)
        tracker.on_tool_result(name, text if line is None
                               else text + "\n\n" + (line or ""), is_err)
        if line and "finish" in line:
            finish_nudges += 1
    snap = v.snapshot(success=True)
    assert finish_nudges >= 3, "release-match + each verified state must nudge"
    assert snap["n_mismatched"] == 0
    assert snap["commit_events"][-1]["closed_by"] == "finish"


def test_end_to_end_t9_place_fail_recovers(contracts, rules):
    """t9 place_fail shape: release under-places, contract escalates to
    pi0_doubled, which terminates the task."""
    tracker = PhaseTracker([r for r in rules if r.applies_to_task("9")],
                           task="9", max_turns=40)
    v = OutcomeValidator(contracts, tracker=tracker, task="9")
    stream = [
        ("view_driver_state", result(step=0), False),
        ("back_project", result(xyz=[0.2, 0.1, 0.3]), False),
        ("move_to", result(final_dist_m=0.01), False),
        ("pi0_pick", result(success=True, min_gripper_opening=0.01), False),
        ("move_to", result(final_dist_m=0.009), False),
        ("release", result(peak_gripper_opening=0.02), False),  # under-place
        ("pi0_doubled", result(success=True, libero_terminated=True), False),
        ("finish", result(status="success"), False),
    ]
    escalate_lines = []
    for name, text, is_err in stream:
        tracker.on_tool_call(name, {})
        line = v.observe_result(name, {}, text, is_error=is_err)
        if line and name == "release":
            escalate_lines.append(line)
        tracker.on_tool_result(name, text if line is None
                               else text + "\n\n" + (line or ""), is_err)
    snap = v.snapshot(success=True)
    # task9 scoped contract: mismatch advice must point at pi0_doubled (R5)
    assert any("pi0_doubled" in l for l in escalate_lines)
    ev = snap["recovery_events"][0]
    assert ev["closed_by"] == "switch" and ev["latency_steps"] == 1
    assert snap["mismatch_escalations"] == 1


# ------------------------------------------------------- arm C commit gate

def test_commit_mode_ctx_after_matched(contracts):
    v = validator(contracts, phase="P_verify")
    v.observe_result("view_driver_state", {}, result(libero_terminated=True))
    assert v.commit_mode_ctx() == {
        "target": "finish", "tool": "view_driver_state", "step": 1}


def test_commit_mode_ctx_phase_target(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=True))
    assert v.commit_mode_ctx() == {
        "target": "P_place", "tool": "pi0_pick", "step": 1}


def test_commit_mode_ctx_once_per_event(contracts):
    v = validator(contracts, phase="P_verify")
    v.observe_result("view_driver_state", {}, result(libero_terminated=True))
    assert v.commit_mode_ctx() is not None
    # the open event consumed its commit turn: no repeat until a NEW
    # verified match (self-correcting — later boundaries run full REASON)
    assert v.commit_mode_ctx() is None


def test_commit_mode_ctx_new_event_rearms(contracts):
    v = validator(contracts, phase="P_verify")
    v.observe_result("view_driver_state", {}, result(libero_terminated=True))
    assert v.commit_mode_ctx() is not None
    v.observe_result("view_driver_state", {}, result(libero_terminated=True))
    ctx = v.commit_mode_ctx()
    assert ctx is not None and ctx["step"] == 2


def test_commit_mode_ctx_blocked_by_open_recovery(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=True))  # opens commit
    v._tracker.phase = "P_transport"
    v.observe_result("move_to", {}, result(final_dist_m=0.12))  # mismatch
    assert v.commit_mode_ctx() is None  # recovery pending -> full REASON
    # perception is diagnosis, not recovery: must NOT rearm commit mode
    v.observe_result("view_driver_state", {}, result(step=3))
    assert v.commit_mode_ctx() is None


def test_commit_mode_ctx_blocked_by_last_error(contracts):
    v = validator(contracts, phase="P_verify")
    v.observe_result("view_driver_state", {}, result(libero_terminated=True))
    v.observe_result("read_image", {}, '{"error": "file not found"}',
                     is_error=True)
    assert v.commit_mode_ctx() is None  # anomalous: full REASON agent
    # a later clean result clears the error flag
    v.observe_result("view_driver_state", {}, result(libero_terminated=True))
    assert v.commit_mode_ctx() is not None


def test_commit_mode_ctx_advisory_match_not_eligible(contracts):
    v = validator(contracts, phase="P_transport")
    v.observe_result("move_to", {}, result(final_dist_m=0.005))  # advisory
    assert v.commit_mode_ctx() is None  # no next_phase -> no commit turn


def test_commit_mode_ctx_mismatch_invalidates_same_tool_commit(contracts):
    v = validator(contracts, phase="P_grasp")
    v.observe_result("pi0_pick", {}, result(success=True))
    v.observe_result("pi0_pick", {}, result(success=False,
                                             min_gripper_opening=0.08))
    assert v.commit_mode_ctx() is None
