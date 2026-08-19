"""Unit tests for Structured Memory + Dual-Route Reasoning (SM2).

Covers the Fast/Slow decider (DualRouter), the PhaseTracker surface it reads
(last_is_error / recovery_pending / last_pick_success / moves_since_pick /
finish_called), the Fix A counter scoping, and the ``_merge_into_tail`` resume
mechanism used to carry a fast summary / pending block into the next model run.

``drive`` mirrors the api_loop integration: before each model turn the router
decides; a Fast action executes zero-arg with no LLM call (feeding the tracker
via on_tool_call/on_tool_result and observe_fast), otherwise the scripted model
action runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.usage import RunUsage

from rpent.memory.dual_route import DualRouter, FastAction
from rpent.memory.structured import PhaseTracker, load_rules
from rpent.planner.api_loop import _merge_into_tail

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


def _default_fast_result(action: FastAction) -> dict:
    if action.name == "view_driver_state":
        return {
            "result": {"libero_terminated": False, "episode_truncated": False},
            "text": "vds ok",
            "is_error": False,
        }
    if action.name == "release":
        return {"result": {"libero_terminated": False}, "text": "released", "is_error": False}
    if action.name == "finish":
        return {
            "result": {
                "_finish": True,
                "status": action.args["status"],
                "summary": action.args["summary"],
            },
            "text": "finish",
            "is_error": False,
        }
    raise AssertionError(f"no result stub for {action.name}")


def drive(router, tracker, model_actions, max_turns=40, fast_result_fn=None):
    """Run the dual-route loop against a scripted model.

    model_actions: list of (name, args, result_text, is_error) executed on Slow
    turns. Fast actions are synthesized through ``fast_result_fn``. Returns
    (taken, total_steps) where taken is a list of ("fast"/"slow", name).
    """
    fast_result_fn = fast_result_fn or _default_fast_result
    taken = []
    total_steps = 0
    i = 0
    while True:
        # decide() runs before every model turn — including once more after the
        # last scripted action, so a trailing Fast action (e.g. release after the
        # final move_to, or the P_verify vds chain) is still captured.
        action = router.decide(
            total_steps=total_steps, max_turns=max_turns, tracker=tracker
        )
        if action is not None:
            taken.append(("fast", action.name))
            total_steps += 1
            tracker.on_tool_call(action.name, action.args)
            res = fast_result_fn(action)
            tracker.on_tool_result(action.name, res["text"], res["is_error"])
            router.observe_fast(action, res["result"])
            if action.name == "finish":
                break
            continue
        if i >= len(model_actions):
            break
        name, args, text, is_error = model_actions[i]
        i += 1
        taken.append(("slow", name))
        total_steps += 1
        tracker.on_tool_call(name, args)
        tracker.on_tool_result(name, text, is_error)
        if name == "finish":
            break
    return taken, total_steps


def grasp_ok_moved(rules, task="7"):
    """Tracker state: P_grasp, last grasp ok, one move after the pick."""
    tr = PhaseTracker(rules_for(rules, task), task=task)
    for name in ("back_project", "move_to"):
        tr.on_tool_call(name, {})
    tr.on_tool_call("pi0_pick", {})
    tr.on_tool_result("pi0_pick", "grasped object", False)
    tr.on_tool_call("move_to", {})
    return tr


# ------------------------------------------------------------- budget gate
def test_budget_exhausted_fast_finish_failure(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    router = DualRouter()
    a = router.decide(total_steps=40, max_turns=40, tracker=tr)
    assert isinstance(a, FastAction)
    assert a.name == "finish" and a.kind == "budget_finish"
    assert a.args["status"] == "failure"
    assert "budget" in a.summary.lower()


def test_no_budget_finish_after_finish_called(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    tr.on_tool_call("finish", {})
    router = DualRouter()
    a = router.decide(total_steps=40, max_turns=40, tracker=tr)
    assert a is None
    assert router.slow_reason == "not_fast_eligible"


# -------------------------------------------------------------- last_error
def test_last_error_forces_slow(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    tr.on_tool_call("back_project", {})
    tr.on_tool_result("back_project", "error: boom", is_error=True)
    router = DualRouter()
    a = router.decide(total_steps=1, max_turns=40, tracker=tr)
    assert a is None
    assert router.slow_reason == "last_error"


# ---------------------------------------------------------- pending_rule
def test_pending_rule_forces_slow(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    for _ in range(7):  # R1 (consecutive_perception_ge 7) pending at P_look
        tr.on_tool_call("back_project", {})
    router = DualRouter()
    a = router.decide(total_steps=10, max_turns=40, tracker=tr)
    assert a is None
    assert router.slow_reason == "pending_rule"


def test_pending_rule_preempts_release_gate(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    for _ in range(3):
        tr.on_tool_call("back_project", {})
    for _ in range(3):  # R4 (pick_calls_ge 3) pending at P_grasp
        tr.on_tool_call("pi0_pick", {})
        tr.on_tool_result("pi0_pick", "ok", False)
    tr.on_tool_call("move_to", {})  # moves_since_pick = 1, grasp ok
    router = DualRouter()
    a = router.decide(total_steps=10, max_turns=40, tracker=tr)
    assert a is None
    assert router.slow_reason == "pending_rule"


# ------------------------------------------------------------ P_verify chain
def test_p_verify_first_decide_returns_vds(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    # two placements -> P_verify
    for name in ("back_project", "move_to", "pi0_pick", "release", "pi0_doubled"):
        tr.on_tool_call(name, {})
    router = DualRouter()
    a = router.decide(total_steps=5, max_turns=40, tracker=tr)
    assert isinstance(a, FastAction)
    assert a.name == "view_driver_state" and a.kind == "p_verify_view"


def test_p_verify_chain_finishes_when_terminated(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    router = DualRouter()
    model_actions = [
        ("back_project", {}, "ok", False),
        ("move_to", {}, "ok", False),
        ("pi0_pick", {}, "ok", False),
        ("move_to", {}, "ok", False),  # -> fast release fires here
        ("pi0_doubled", {}, "ok", False),  # -> P_verify
    ]

    def fr(action):
        if action.name == "view_driver_state":
            return {
                "result": {"libero_terminated": True, "episode_truncated": False},
                "text": "terminated",
                "is_error": False,
            }
        return _default_fast_result(action)

    taken, _ = drive(router, tr, model_actions, fast_result_fn=fr)
    assert ("fast", "view_driver_state") in taken
    assert ("fast", "finish") in taken
    assert taken[-1] == ("fast", "finish")
    assert router._vds_terminated is True


def test_p_verify_chain_slows_when_unterminated(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    router = DualRouter()
    model_actions = [
        ("back_project", {}, "ok", False),
        ("move_to", {}, "ok", False),
        ("pi0_pick", {}, "ok", False),
        ("move_to", {}, "ok", False),
        ("pi0_doubled", {}, "ok", False),
    ]
    taken, _ = drive(router, tr, model_actions)
    assert ("fast", "view_driver_state") in taken
    assert ("fast", "finish") not in taken
    assert router.slow_reason == "p_verify_unterminated"


# ------------------------------------------------------------ release gate
def test_release_gate_fires(rules):
    tr = grasp_ok_moved(rules)
    router = DualRouter()
    a = router.decide(total_steps=5, max_turns=40, tracker=tr)
    assert isinstance(a, FastAction)
    assert a.name == "release" and a.kind == "release"
    assert a.args == {}


def test_release_gate_requires_successful_pick(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    for name in ("back_project", "move_to"):
        tr.on_tool_call(name, {})
    tr.on_tool_call("pi0_pick", {})
    tr.on_tool_result("pi0_pick", "could not find object", False)  # failed
    tr.on_tool_call("move_to", {})
    a = DualRouter().decide(total_steps=5, max_turns=40, tracker=tr)
    assert a is None


def test_release_gate_requires_move_after_pick(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    for name in ("back_project", "move_to"):
        tr.on_tool_call(name, {})
    tr.on_tool_call("pi0_pick", {})
    tr.on_tool_result("pi0_pick", "grasped object", False)
    # no move after the pick -> moves_since_pick == 0
    a = DualRouter().decide(total_steps=4, max_turns=40, tracker=tr)
    assert a is None


def test_release_gate_requires_phase_in_grasp_place(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    for _ in range(3):
        tr.on_tool_call("back_project", {})  # P_look, no pick
    a = DualRouter().decide(total_steps=3, max_turns=40, tracker=tr)
    assert a is None


def test_release_gate_respects_enable_release(rules):
    tr = grasp_ok_moved(rules)
    a = DualRouter(enable_release=False).decide(total_steps=5, max_turns=40, tracker=tr)
    assert a is None


def test_single_grasp_single_release(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    router = DualRouter()
    model_actions = [
        ("back_project", {}, "ok", False),
        ("move_to", {}, "ok", False),
        ("pi0_pick", {}, "ok", False),
        ("move_to", {}, "ok", False),
    ]
    taken, total = drive(router, tr, model_actions)
    assert taken[-1] == ("fast", "release")
    # the grasp is consumed by the release -> no second fast release
    a2 = router.decide(total_steps=total, max_turns=40, tracker=tr)
    assert a2 is None
    assert tr.last_pick_success is None


# --------------------------------------------------- PhaseTracker surface
def test_moves_since_pick_increments_and_resets(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    tr.on_tool_call("move_to", {})
    assert tr.moves_since_pick == 1
    tr.on_tool_call("move_to", {})
    assert tr.moves_since_pick == 2
    tr.on_tool_call("pi0_pick", {})  # the CALL does not reset
    assert tr.moves_since_pick == 2
    tr.on_tool_result("pi0_pick", "grasped", False)  # the RESULT resets
    assert tr.moves_since_pick == 0


def test_last_is_error_reflects_result(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    tr.on_tool_result("move_to", "ok", False)
    assert tr.last_is_error is False
    tr.on_tool_result("move_to", "error", True)
    assert tr.last_is_error is True


def test_release_result_clears_pick_success(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    tr.on_tool_call("pi0_pick", {})
    tr.on_tool_result("pi0_pick", "ok", False)
    assert tr.last_pick_success is True
    tr.on_tool_result("release", "released", False)
    assert tr.last_pick_success is None


def test_recovery_pending_is_pure(rules):
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    for _ in range(7):
        tr.on_tool_call("back_project", {})
    assert tr.recovery_pending() == "R1"
    # no side effects: no fired rule, no turn recorded, no injection
    assert tr._fired == []
    assert tr._turns_used == 0
    assert tr.snapshot()["injections"] == 0
    assert tr.recovery_pending() == "R1"


def test_slow_reasons_accumulate(rules):
    router = DualRouter()
    tr = PhaseTracker(rules_for(rules, "7"), task="7")
    router.decide(total_steps=1, max_turns=40, tracker=tr)
    assert router.slow_reasons == ["not_fast_eligible"]
    router.decide(total_steps=2, max_turns=40, tracker=tr)
    assert router.slow_reasons == ["not_fast_eligible", "not_fast_eligible"]


# ------------------------------------------------------------ Fix A (R8)
def test_non_memory_read_does_not_bump_r8(rules):
    tr = PhaseTracker(rules_for(rules, "0"), task="0")
    calls = (
        [("read_text_file", {"path": "robots/libero/guides/strict_hybrid.md"})] * 11
        + [("move_to", {})]
    )
    run_chain(tr, calls)
    assert "R8" not in tr._fired
    assert tr.snapshot()["counters"]["read_text_file_calls"] == 0
    assert tr._mem_reads == []


def test_memory_read_bumps_r8(rules):
    tr = PhaseTracker(rules_for(rules, "0"), task="0")
    calls = (
        [("read_text_file", {"path": "resources/libero/memory/MEMORY.md"})] * 11
        + [("move_to", {})]
    )
    run_chain(tr, calls)
    assert "R8" in tr._fired
    assert tr.snapshot()["counters"]["read_text_file_calls"] == 11
    assert len(tr._mem_reads) == 11


# ---------------------------------------------------------- _merge_into_tail
def test_merge_into_tail_empty_history():
    h = _merge_into_tail([], "hello")
    assert len(h) == 1
    assert isinstance(h[0], ModelRequest)
    assert h[0].parts[0].content == "hello"


def test_merge_into_tail_appends_to_tail_request():
    base = ModelRequest(parts=[UserPromptPart(content="seed")])
    h = _merge_into_tail([base], "fast summary")
    assert len(h) == 1
    ups = [p for p in h[0].parts if isinstance(p, UserPromptPart)]
    assert [p.content for p in ups] == ["seed", "fast summary"]


def test_merge_into_tail_preserves_prefix_and_adds_request():
    first = ModelRequest(parts=[UserPromptPart(content="seed")])
    bare_end = ModelResponse(parts=[TextPart(content="I am done.")])
    h = _merge_into_tail([first, bare_end], "pending block")
    assert h[0] is first
    assert len(h) == 3
    assert isinstance(h[-1], ModelRequest)
    assert h[-1].parts[0].content == "pending block"


# ------------------------------------------------- token accounting across runs
def _mk_response(run_id: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content="hi")], run_id=run_id)


class _Sink:
    def __init__(self):
        self.events = []

    def emit(self, ev):
        self.events.append(ev)


def _mk_usage(requests, inp, out, cache_read=0, cache_write=0) -> RunUsage:
    return RunUsage(
        requests=requests,
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


def test_usage_accum_single_run_multiple_turns():
    """Non-dual-route: one graph run, run.usage cumulative -> per-turn delta."""
    from rpent.planner.api_loop import _ApiRunObserver, _usage_delta

    obs = _ApiRunObserver(dashboard_events=_Sink(), messages=[], max_turns=40)
    r1 = _mk_response("run-a")
    r2 = _mk_response("run-a")  # same run, later turn
    obs.observe_response(r1, _mk_usage(1, 100, 10, 5, 3))
    obs.observe_response(r2, _mk_usage(2, 160, 20, 9, 6))
    # cumulative: turn2 totals, not turn2-only
    assert obs._usage_accum.requests == 2
    assert obs._usage_accum.input_tokens == 160
    assert obs._usage_accum.output_tokens == 20
    assert obs._usage_accum.cache_read_tokens == 9
    # delta helper correctness
    d = _usage_delta(_mk_usage(2, 160, 20, 9, 6), _mk_usage(1, 100, 10, 5, 3))
    assert (d.requests, d.input_tokens, d.output_tokens, d.cache_read_tokens) == (1, 60, 10, 4)


def test_usage_accum_dual_route_many_runs():
    """Dual-route: fresh run per turn -> totals summed across runs."""
    from rpent.planner.api_loop import _ApiRunObserver

    obs = _ApiRunObserver(dashboard_events=_Sink(), messages=[], max_turns=40)
    for i in range(1, 5):  # 4 one-turn runs
        obs.observe_response(_mk_response(f"run-{i}"), _mk_usage(i, 100, 10, 0, 0))
    assert obs._usage_accum.requests == 10  # 1+2+3+4
    assert obs._usage_accum.input_tokens == 400


def test_usage_accum_reset_on_new_run_id():
    """A fresh run_id must reset the in-run baseline (not delta off the old run)."""
    from rpent.planner.api_loop import _ApiRunObserver

    obs = _ApiRunObserver(dashboard_events=_Sink(), messages=[], max_turns=40)
    obs.observe_response(_mk_response("run-1"), _mk_usage(5, 500, 50, 0, 0))  # old run
    obs.observe_response(_mk_response("run-2"), _mk_usage(1, 100, 10, 0, 0))  # new run
    # new run's first turn counts its whole usage, not the delta to the old run
    assert obs._usage_accum.input_tokens == 600
    assert obs._usage_accum.requests == 6
