#!/usr/bin/env python3
"""Stage G0.5 injection-mode unit tests (no GPU, no network).

Covers the §18/§19 regression contract BEFORE any G0.5 episode runs:
  1  default (no env) = byte-identical historical behavior; explicit
     full reproduces the frozen _block() bitwise (P4 = g0D reuse)
  2  reason_only (P1): no retrieval runs, block = frozen F2 text
  3  generic_refresh (P2): no retrieval, block = frozen F3 text verbatim
  4  memory_only (P3): retrieval runs, neutral F4 header + card lines
     IDENTICAL to _block()'s, reason absent everywhere
  5  none (P0): fire logged, retrieval NOT_RUN, nothing injected
  6  cooldown/cap semantics survive under no-injection modes
  7  env cross-validation fails fast (QUERY_REASON / BLOCK_REASON /
     undeclared mode combinations)

Usage: python scripts/test_stageG05_injection.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpent.memory.retrieval import (  # noqa: E402
    DecisionMemory, GENERIC_REFRESH_BLOCK, MEMORY_CONTEXT_HEADER,
    _reason_only_block,
)

REPO = Path(__file__).resolve().parent.parent


class FakeTracker:
    def __init__(self):
        self.phase = "P_transport"

    def current_phase(self):
        return self.phase

    def recovery_pending(self):
        return False


G05_ENV_KEYS = ("RPENT_MEMORY_TRIGGER", "RPENT_MEMORY_QUERY_MODE",
                "RPENT_MEMORY_RANK", "RPENT_MEMORY_EXTRA_BANK",
                "RPENT_MEMORY_INJECTION_MODE", "RPENT_MEMORY_QUERY_REASON",
                "RPENT_MEMORY_BLOCK_REASON")

TL = {"task_language": "put the alphabet soup in the basket"}
FAIL_PICK = [("pi0_pick", {"success": False, **TL})]


def fresh(**env):
    for k in G05_ENV_KEYS:
        os.environ.pop(k, None)
    os.environ["RPENT_MEMORY_TRIGGER"] = "v1_per_result"
    for k, v in env.items():
        os.environ[k] = v
    dm = DecisionMemory(FakeTracker(), mode="v1_per_result")
    dm.task_language = TL["task_language"]
    return dm


def fire(dm):
    """One failed pick then boundaries -> exactly one flushed fire."""
    dm.on_tool_result(FAIL_PICK[0][0], json.dumps(FAIL_PICK[0][1]), False)
    out = None
    for t in (1, 2, 3):
        out = dm.turn_boundary(t)
        if out is not None:
            break
    assert out is not None, "expected one fire"
    return out


def stub_cards(dm, n=3):
    ids = dm.ids[:n]
    dm._q0_fixed = lambda q: (ids, ids)  # noqa: E731
    return ids


# --------------------------------------------------------------------- tests
def test_default_and_full_bitwise():
    """No-env default and explicit full are byte-identical (P4 basis),
    holding the query mode constant on both sides."""
    dm0 = fresh(RPENT_MEMORY_QUERY_MODE="common")
    blk0, ev0 = fire(dm0)
    assert ev0["injection_mode"] == "full"
    dmd = fresh(RPENT_MEMORY_QUERY_MODE="common",
                RPENT_MEMORY_INJECTION_MODE="full")
    blkd, evd = fire(dmd)
    assert blkd == blk0, "explicit full must reproduce default bitwise"
    assert evd["injection_mode"] == "full"
    # and the historical shape: _block(reason, top3) reconstruction
    top = ev0["top3_memories"]
    assert blk0 == dm0._block(ev0["trigger_reason"], list(top)), \
        "full-mode block must equal the frozen _block() call bitwise"
    assert blk0.startswith("[DECISION-POINT MEMORY RECALL] ")
    assert f"trigger: {ev0['trigger_reason']}" in blk0
    print("  1.full bitwise: default == explicit full == _block() "
          f"({len(blk0.split())} tokens)")


def test_reason_only():
    dm = fresh(RPENT_MEMORY_INJECTION_MODE="reason_only",
               RPENT_MEMORY_QUERY_MODE="common")

    def _boom(q):
        raise AssertionError("P1 must not run retrieval")

    dm._q0_fixed = _boom
    blk, ev = fire(dm)
    reason = ev["trigger_reason"]
    assert blk == _reason_only_block(reason)
    assert blk == ("[DECISION-POINT CHECK]\n"
                   f"trigger reason: {reason}\n"
                   "Re-evaluate the next action using the latest observable "
                   "state.")
    assert "applies_when" not in blk and "REORIENTATION" not in blk
    assert ev["injection_mode"] == "reason_only"
    assert ev["retrieval_status"] == "NOT_RUN"
    assert ev["retrieval_empty"] is None
    assert ev["retrieval_latency_ms"] == 0.0
    assert ev["top3_memories"] == []
    assert ev["retrieval_tokens"] == len(blk.split())
    print(f"  2.reason_only: F2 exact, no retrieval ({reason})")


def test_generic_refresh():
    dm = fresh(RPENT_MEMORY_INJECTION_MODE="generic_refresh",
               RPENT_MEMORY_QUERY_MODE="common")

    def _boom(q):
        raise AssertionError("P2 must not run retrieval")

    dm._q0_fixed = _boom
    blk, ev = fire(dm)
    assert blk == GENERIC_REFRESH_BLOCK
    assert blk.startswith("[DECISION-POINT REORIENTATION]\n")
    assert len(GENERIC_REFRESH_BLOCK.split("\n")) == 5  # frozen line count
    assert ev["trigger_reason"] not in blk          # no reason anywhere
    assert "applies_when" not in blk                 # no cards
    assert ev["retrieval_status"] == "NOT_RUN"
    assert ev["injection_mode"] == "generic_refresh"
    print("  3.generic_refresh: F3 verbatim, task-independent, no reason")


def test_memory_only():
    dm = fresh(RPENT_MEMORY_INJECTION_MODE="memory_only",
               RPENT_MEMORY_QUERY_MODE="common",
               RPENT_MEMORY_BLOCK_REASON="0")
    ids = stub_cards(dm)
    blk, ev = fire(dm)
    assert ev["injection_mode"] == "memory_only"
    assert ev["retrieval_status"] == "MATCH"
    assert ev["top3_memories"] == list(ids)
    lines = blk.split("\n")
    assert "\n".join(lines[:2]) == MEMORY_CONTEXT_HEADER
    # card lines identical to _block()'s for the same top-3
    hist = dm._block(ev["trigger_reason"], list(ids))
    assert lines[2:] == hist.split("\n")[2:], \
        "F4 card rendering must equal _block()'s bitwise"
    assert ev["trigger_reason"] not in blk           # no reason anywhere
    assert "MEMORY RECALL" not in blk
    print(f"  4.memory_only: F4 header + {len(ids)} cards, cards bitwise "
          "match _block(), reason absent")


def test_none_mode():
    dm = fresh(RPENT_MEMORY_INJECTION_MODE="none",
               RPENT_MEMORY_QUERY_MODE="common")

    def _boom(q):
        raise AssertionError("P0 must not run retrieval")

    dm._q0_fixed = _boom
    dm.on_tool_result(FAIL_PICK[0][0], json.dumps(FAIL_PICK[0][1]), False)
    outs = [dm.turn_boundary(t) for t in (1, 2, 3)]
    assert all(o is None for o in outs), outs
    assert len(dm.events) == 1
    ev = dm.events[0]
    assert ev["injection_mode"] == "none"
    assert ev["retrieval_status"] == "NOT_RUN"
    assert ev["trigger_fired"] is True
    assert "retrieval_tokens" not in ev        # nothing injected
    print("  5.none: fire logged NOT_RUN, nothing injected, returns None")


def test_cooldown_cap_under_none():
    dm = fresh(RPENT_MEMORY_INJECTION_MODE="none",
               RPENT_MEMORY_QUERY_MODE="common")
    dm.on_tool_result(FAIL_PICK[0][0], json.dumps(FAIL_PICK[0][1]), False)
    dm.turn_boundary(1)
    dm.on_tool_result(FAIL_PICK[0][0], json.dumps(FAIL_PICK[0][1]), False)
    dm.turn_boundary(2)   # inside cooldown (2 boundaries) -> DROPPED
    assert len(dm.events) == 1, dm.events
    dm.on_tool_result(FAIL_PICK[0][0], json.dumps(FAIL_PICK[0][1]), False)
    dm.turn_boundary(3)
    dm.turn_boundary(4)
    dm.turn_boundary(5)
    assert len(dm.events) == 2, dm.events
    print("  6.cooldown/cap: honored under none-mode instrumentation")


def test_env_validation():
    def expect_valueerror(**env):
        try:
            fresh(**env)
        except ValueError:
            return
        raise AssertionError(f"expected ValueError for {env}")

    # undeclared mode value
    expect_valueerror(RPENT_MEMORY_INJECTION_MODE="bogus")
    # injection modes are pre-registered for v1_per_result only
    try:
        for k in G05_ENV_KEYS:
            os.environ.pop(k, None)
        os.environ["RPENT_MEMORY_TRIGGER"] = "v1"
        os.environ["RPENT_MEMORY_INJECTION_MODE"] = "reason_only"
        DecisionMemory(FakeTracker(), mode="v1")
    except ValueError:
        pass
    else:
        raise AssertionError("v1 + reason_only must fail fast")
    # QUERY_REASON contradicts QUERY_MODE
    expect_valueerror(RPENT_MEMORY_QUERY_REASON="1",
                      RPENT_MEMORY_QUERY_MODE="common")
    # BLOCK_REASON=0 belongs to memory_only only
    expect_valueerror(RPENT_MEMORY_BLOCK_REASON="0")
    expect_valueerror(RPENT_MEMORY_BLOCK_REASON="0",
                      RPENT_MEMORY_INJECTION_MODE="reason_only")
    # consistent combos construct fine
    fresh(RPENT_MEMORY_QUERY_REASON="1")           # native default
    fresh(RPENT_MEMORY_QUERY_REASON="0",
          RPENT_MEMORY_QUERY_MODE="common")
    fresh(RPENT_MEMORY_QUERY_MODE="common",
          RPENT_MEMORY_INJECTION_MODE="memory_only",
          RPENT_MEMORY_BLOCK_REASON="0")
    print("  7.env validation: all contradictions fail fast")


if __name__ == "__main__":
    test_default_and_full_bitwise()
    test_reason_only()
    test_generic_refresh()
    test_memory_only()
    test_none_mode()
    test_cooldown_cap_under_none()
    test_env_validation()
    print("ALL G0.5 INJECTION TESTS GREEN")
