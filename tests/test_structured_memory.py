"""Unit tests for Structured Global Memory v1 (schema + PhaseTracker engine).

These simulate the tool stream of a full episode and assert on phase
transitions, rule firing, injection content, and offline metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpent.memory.schema import PHASES, validate
from rpent.memory.structured import PhaseTracker, load_rules

RULES_PATH = Path("analysis/structured_rules_v1.json")


@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES_PATH)


def rules_for(rules, task):
    return [r for r in rules if r.applies_to_task(task)]


def run_chain(tracker, calls):
    """Feed (tool_name, args) pairs; inject+return the blocks produced."""
    blocks = []
    for i, (name, args) in enumerate(calls):
        tracker.on_tool_call(name, args)
        block = tracker.current_block(i + 1)
        if block is not None:
            tracker.mark_injected()
            blocks.append((i + 1, block))
    return blocks


# ---------------------------------------------------------------- schema
def test_validate_rejects_bad_phase():
    with pytest.raises(ValueError):
        validate({"phase": "P_nope", "trigger": "x"})


def test_validate_rejects_unknown_predicate_key():
    raw = {
        "id": "X", "phase": "P_look", "trigger": "t",
        "precondition": {"perception_calls_ge": 3},
        "expected_result": "e", "success_check": {},
        "failure_pattern": "f", "recovery": "r", "next_phase": "n",
        "scope": "GLOBAL",
    }
    with pytest.raises(ValueError):
        validate(raw)


def test_validate_rejects_missing_fields():
    with pytest.raises(ValueError):
        validate({"id": "X", "phase": "P_look"})


def test_rules_document_has_expected_ids(rules):
    assert {r.id for r in rules} == {"R1", "R3", "R4", "R5", "R6", "R7", "R8", "R9"}


def test_r5_is_task9_scoped(rules):
    t9 = rules_for(rules, "9")
    t7 = rules_for(rules, "7")
    assert any(r.id == "R5" for r in t9)
    assert not any(r.id == "R5" for r in t7)


# ------------------------------------------------------------- phase model
def test_phase_sequence_monotonic(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    calls = [("back_project", {})] * 3 + [("move_to", {})] + [("pi0_pick", {})]
    run_chain(tr, calls)
    seq = tr.snapshot()["phase_sequence"]
    assert seq[0] == "P_init"
    assert tr.current_phase() == "P_grasp"
    # strictly forward: each subsequent phase is >= previous in PHASE_ORDER
    from rpent.memory.schema import PHASE_ORDER
    assert all(PHASE_ORDER[a] <= PHASE_ORDER[b] for a, b in zip(seq, seq[1:]))


def test_phase_verify_after_two_placements(rules):
    tr = PhaseTracker(rules_for(rules, "9"), task="9")
    calls = [
        ("segment", {}), ("back_project", {}), ("move_to", {}),
        ("pi0_pick", {}), ("release", {}), ("pi0_doubled", {}),
    ]
    run_chain(tr, calls)
    assert tr.current_phase() == "P_verify"


# ---------------------------------------------------------------- R1 (F1)
def test_r1_fires_on_perception_loop(rules):
    tr = PhaseTracker(rules_for(rules, "9"), task="9")
    calls = [("back_project", {})] * 8 + [("move_to", {})]
    run_chain(tr, calls)
    assert tr._fired[0] == "R1"
    # recovery succeeded: an action followed the fire
    snap = tr.snapshot()
    assert snap["recovery_success"]["R1"] is True


# ---------------------------------------------------------------- R3 (F2)
def test_r3_fires_on_move_to_loop_and_recovers(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    calls = [("back_project", {})] * 3 + [("move_to", {})] * 8 + [("pi0_pick", {})]
    run_chain(tr, calls)
    assert "R3" in tr._fired
    assert tr._fired_detail["R3"]["fired_turn"] == 10  # 7th move_to
    assert tr.snapshot()["recovery_success"]["R3"] is True


# ---------------------------------------------------------------- R4 (F3)
def test_r4_fires_on_grasp_retry(rules):
    tr = PhaseTracker(rules_for(rules, "9"), task="9")
    calls = (
        [("segment", {})] * 3 + [("back_project", {})] * 2
        + [("move_to", {})] + [("pi0_pick", {})] * 4
    )
    run_chain(tr, calls)
    assert "R4" in tr._fired


# ---------------------------------------------------------------- R5 (t9)
def test_r5_fires_on_t9_single_release(rules):
    tr = PhaseTracker(rules_for(rules, "9"), task="9")
    calls = [
        ("segment", {}), ("back_project", {}), ("move_to", {}),
        ("pi0_pick", {}), ("set_gripper", {}), ("release", {}),
    ]
    run_chain(tr, calls)
    assert "R5" in tr._fired
    # recovery succeeded only once the planner follows with pi0_doubled
    assert tr.snapshot()["recovery_success"]["R5"] is False
    tr.on_tool_call("pi0_doubled", {})
    assert tr.snapshot()["recovery_success"]["R5"] is True


def test_r5_does_not_fire_if_doubled_already_used(rules):
    tr = PhaseTracker(rules_for(rules, "9"), task="9")
    calls = [
        ("segment", {}), ("back_project", {}), ("move_to", {}),
        ("pi0_pick", {}), ("pi0_doubled", {}),
    ]
    run_chain(tr, calls)
    assert "R5" not in tr._fired


# ---------------------------------------------------------------- R6
def test_r6_fires_on_placement_loop(rules):
    tr = PhaseTracker(rules_for(rules, "0"), task="0")
    calls = (
        [("segment", {})] + [("back_project", {})] * 2 + [("move_to", {})]
        + [("pi0_pick", {})] + [("pi0_doubled", {})] * 3 + [("finish", {})]
    )
    run_chain(tr, calls)
    assert "R6" in tr._fired
    snap = tr.snapshot()
    assert snap["recovery_success"]["R6"] is True  # left P_place, called finish


# ---------------------------------------------------------------- R7
def test_r7_fires_at_verify_and_prompts_finish(rules):
    tr = PhaseTracker(rules_for(rules, "0"), task="0")
    calls = [
        ("back_project", {}), ("move_to", {}), ("pi0_pick", {}),
        ("release", {}), ("pi0_doubled", {}),
    ]
    blocks = run_chain(tr, calls)
    assert "R7" in tr._fired
    # last block (at P_verify) carries the R7 recovery text
    last = blocks[-1][1]
    assert "R7" in last and "finish(status='success')" in last


# ---------------------------------------------------------------- R8 (F4)
def test_r8_fires_on_over_reading(rules):
    tr = PhaseTracker(rules_for(rules, "0"), task="0")
    calls = (
        [("read_text_file", {"path": "resources/libero/memory/MEMORY.md"})] * 11
        + [("move_to", {})]
    )
    run_chain(tr, calls)
    assert "R8" in tr._fired
    assert tr.snapshot()["recovery_success"]["R8"] is True


def test_mem_reads_tracked(rules):
    tr = PhaseTracker(rules_for(rules, "0"), task="0")
    run_chain(
        tr,
        [("read_text_file", {"path": "resources/libero/memory/MEMORY.md"})] * 3,
    )
    assert len(tr._mem_reads) == 3
    assert "MEMORY.md" in tr._mem_reads[0]


# ---------------------------------------------------------------- R9 (budget)
def test_r9_fires_near_budget_end(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7", max_turns=40)
    calls = [("read_text_file", {"path": "x"})] * 38 + [("finish", {})]
    run_chain(tr, calls)
    assert "R9" in tr._fired
    assert tr._fired_detail["R9"]["fired_turn"] == 35  # 40 - 5 left
    assert tr.snapshot()["recovery_success"]["R9"] is True


def test_r9_does_not_fire_on_short_success(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    calls = [("back_project", {})] * 3 + [("move_to", {})] + [("pi0_pick", {})]
    run_chain(tr, calls)
    assert "R9" not in tr._fired


# --------------------------------------------------------- injection hygiene
def test_injection_throttled_to_phase_changes(rules):
    """Repeated same-phase calls without threshold crossings produce no block."""
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    calls = [("back_project", {})] * 6  # all P_look, below R1 threshold
    blocks = run_chain(tr, calls)
    assert len(blocks) == 1  # only the P_init -> P_look transition
    assert blocks[0][1].startswith("[CURRENT PHASE: P_look]")


def test_injection_contains_recovery_text(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    calls = [("back_project", {})] * 3 + [("move_to", {})] * 8
    blocks = run_chain(tr, calls)
    r3_block = next(b for t, b in blocks if "R3" in b)
    assert "Stop repositioning" in r3_block
    assert len(r3_block.split()) <= 400


def test_snapshot_schema(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    run_chain(tr, [("back_project", {})] * 3 + [("move_to", {})])
    snap = tr.snapshot(success=True)
    assert snap["rules_ver"] == "v1"
    assert snap["task"] == "7"
    for key in (
        "phase_entries", "phase_sequence", "injections",
        "injection_tokens_approx", "fired_rules", "fired_detail",
        "recovery_success", "counters", "mem_reads", "final_phase",
        "finish_called", "success",
    ):
        assert key in snap
    assert snap["counters"]["move_to_calls"] == 1
