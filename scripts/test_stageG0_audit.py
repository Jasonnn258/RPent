#!/usr/bin/env python3
"""Stage G0 causal-audit unit tests (no GPU, no network).

Covers the audit contract before any G0 episode runs:
  A  v1_per_result: frozen-rules identity + signal preservation + queue/
     drop-on-cooldown + cap + first-primitive gate
  B  QUERY_MODE common/native: the trigger reason never enters the query
     under common (lexical text AND the Q3 reason term)
  C  Q3 queued-result regression: structured scorer reads the TRIGGER
     result A, never a later result B
  D  motion_stuck correctness: 5+1 scenarios (same-target stall fires;
     progress no-fire; cross-target no-fire; non-move primitive resets;
     large displacement no-fire; phase transition resets)
  E  attempt logging: EMPTY retrieval writes an event, injects nothing
  F  extra-bank namespaced ids: cross-directory stems never collide;
     global ids and their scoring untouched

Usage: python scripts/test_stageG0_audit.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpent.memory.retrieval import (  # noqa: E402
    COOLDOWN_BOUNDARIES, MAX_TRIGGERS_PER_EPISODE, DecisionMemory,
)

REPO = Path(__file__).resolve().parent.parent


class FakeTracker:
    def __init__(self):
        self.phase = "P_transport"

    def current_phase(self):
        return self.phase

    def recovery_pending(self):
        return False


def set_env(**kv):
    for k, v in kv.items():
        os.environ[k] = v


def clear_env(*keys):
    for k in keys:
        os.environ.pop(k, None)


G0_ENV_KEYS = ("RPENT_MEMORY_TRIGGER", "RPENT_MEMORY_QUERY_MODE",
               "RPENT_MEMORY_RANK", "RPENT_MEMORY_EXTRA_BANK",
               "RPENT_MEMORY_PERIODIC_N", "RPENT_MSTUCK_K",
               "RPENT_MSTUCK_MOVE_M", "RPENT_MSTUCK_PROG_M")


def fresh(mode, tracker=None, **env):
    clear_env(*G0_ENV_KEYS)
    set_env(**env)
    return DecisionMemory(tracker or FakeTracker(), mode=mode)


def feed(dm, results, boundaries):
    fires = []
    for name, data in results:
        dm.on_tool_result(name, json.dumps(data), False)
    for t in boundaries:
        r = dm.turn_boundary(t)
        if r:
            fires.append(r[1])
    return fires


def res_move(eef, fd, tgt=(0.5, 0.5, 1.0)):
    return ("move_to", {"final_eef_pos": list(eef), "final_dist_m": fd,
                        "target_xyz": list(tgt), "success": True})


# ---------------------------------------------------------------- A
def test_rules_identity():
    """Same single-result sequences -> IDENTICAL v1 / v1_per_result
    trigger reasons (the rules are one function, verbatim)."""
    tl = {"task_language": "put the alphabet soup in the basket"}
    cases = [
        [("pi0_pick", {"success": False, **tl})],
        [("pi0_doubled", {"success": False, **tl})],
        [("move_to", {"final_dist_m": 0.2, "final_eef_pos": [0, 0, 1],
                      "target_xyz": [0.5, 0.5, 1], **tl})],
        [("move_to", {"error": "rpc", **tl})],
        [("pi0_pick", {"success": True, "diagnostics":
                       {"post_min_ascent_m": 0.01}, **tl})],
        [("segment", {"found": False, **tl})],
        [("move_to", {"success": True, "final_dist_m": 0.01,
                      "final_eef_pos": [0, 0, 1],
                      "target_xyz": [0.5, 0.5, 1], **tl}),
         ("move_to", {"success": True, "final_dist_m": 0.01,
                      "final_eef_pos": [0, 0, 1.1],
                      "target_xyz": [0.5, 0.5, 1], **tl}),
         ("move_to", {"success": True, "final_dist_m": 0.01,
                      "final_eef_pos": [0, 0, 1.2],
                      "target_xyz": [0.5, 0.5, 1], **tl})],
    ]
    for i, results in enumerate(cases):
        v1 = fresh("v1")
        v1.task_language = "put the alphabet soup in the basket"
        pr = fresh("v1_per_result")
        pr.task_language = "put the alphabet soup in the basket"
        f_v1 = feed(v1, results, [1, 2, 3])
        f_pr = feed(pr, results, [1, 2, 3])
        r_v1 = [e["trigger_reason"] for e in f_v1]
        r_pr = [e["trigger_reason"] for e in f_pr]
        assert r_v1 == r_pr, f"case {i}: v1={r_v1} v1_per_result={r_pr}"
        print(f"  A.identity case {i}: {r_v1}")


def test_signal_preservation():
    """v1 loses the hit when a later benign result overwrites it;
    v1_per_result keeps it. This difference is the audit's subject."""
    tl = {"task_language": "put the alphabet soup in the basket"}
    seq = [("pi0_pick", {"success": False, **tl}),
           ("move_to", {"success": True, "final_dist_m": 0.01,
                        "final_eef_pos": [0, 0, 1],
                        "target_xyz": [0.5, 0.5, 1]})]
    v1 = fresh("v1")
    v1.task_language = "put the alphabet soup in the basket"
    f_v1 = feed(v1, seq, [1, 2, 3])
    pr = fresh("v1_per_result")
    pr.task_language = "put the alphabet soup in the basket"
    f_pr = feed(pr, seq, [1, 2, 3])
    assert f_v1 == [], f"v1 should stay silent, got {f_v1}"
    assert len(f_pr) == 1 and f_pr[0]["trigger_reason"].startswith(
        "primitive_failure: pi0_pick"), f_pr
    assert f_pr[0]["trigger_mode"] == "v1_per_result"
    print("  A.preservation: v1=0 fires, v1_per_result=1 fire (pick fail)")


def test_queue_drop_and_cap():
    tl = {"task_language": "put the alphabet soup in the basket"}
    # drop-on-cooldown: second queued fire inside cooldown is DROPPED
    pr = fresh("v1_per_result")
    pr.task_language = "put the alphabet soup in the basket"
    fails = [("pi0_pick", {"success": False, **tl})]
    f1 = feed(pr, fails, [1])
    assert len(f1) == 1
    pr.on_tool_result("pi0_pick", json.dumps({"success": False, **tl}),
                      False)
    r = pr.turn_boundary(2)          # 1 boundary since trigger < 2
    assert r is None and len(pr.events) == 1, "cooldown must DROP the queue"
    # cap: 6 fires per episode, 7th queued fire dropped at flush
    pr2 = fresh("v1_per_result")
    pr2.task_language = "put the alphabet soup in the basket"
    n = 0
    for b in range(1, 30):
        pr2.on_tool_result("pi0_pick",
                           json.dumps({"success": False, **tl}), False)
        if pr2.turn_boundary(b):
            n += 1
    assert n == MAX_TRIGGERS_PER_EPISODE, f"cap not enforced: {n}"
    print(f"  A.drop-on-cooldown + cap: {n} fires then silent")


def test_first_primitive_gate():
    tl = {"task_language": "put the alphabet soup in the basket"}
    pr = fresh("v1_per_result")
    pr.task_language = "put the alphabet soup in the basket"
    f = feed(pr, [("segment", {"found": False, **tl})], [1, 2])
    assert f == [], "no eval before the first primitive (v1 gate)"
    f = feed(pr, [("move_to", {"success": True, "final_dist_m": 0.01,
                               "final_eef_pos": [0, 0, 1],
                               "target_xyz": [0.5, 0.5, 1], **tl}),
                  ("segment", {"found": False, **tl})], [3, 4])
    assert len(f) == 1 and f[0]["trigger_reason"].startswith(
        "perception_insufficient"), f
    print("  A.gate: perception-before-primitive silent; after, fires")


# ---------------------------------------------------------------- B
def test_query_mode():
    tl = {"task_language": "put the alphabet soup in the basket"}
    stalled = [("move_to", {"final_eef_pos": [0.1, 0.2, 1.0],
                            "final_dist_m": 0.2, "success": True,
                            "target_xyz": [0.5, 0.5, 1.0], **tl})]
    seen = {}

    def spy_factory(dm):
        orig = DecisionMemory._q0_fixed

        def spy(q):
            seen.setdefault("q", []).append(q)
            return orig(dm, q)
        return spy

    nat = fresh("progress", RPENT_MEMORY_RANK="Q0_FIXED")
    nat.task_language = "put the alphabet soup in the basket"
    nat._q0_fixed = spy_factory(nat)
    feed(nat, stalled, [1, 2])
    assert any("move_stalled_no_progress" in q for q in seen["q"]), \
        "native query must contain the reason (historical behavior)"
    seen.clear()

    com = fresh("progress", RPENT_MEMORY_RANK="Q0_FIXED",
                RPENT_MEMORY_QUERY_MODE="common")
    com.task_language = "put the alphabet soup in the basket"
    com._q0_fixed = spy_factory(com)
    evs = feed(com, stalled, [1, 2])
    assert evs, "common query must still fire the trigger"
    for q in seen["q"]:
        assert "move_stalled" not in q and "no_progress" not in q, q
        assert "phase=" in q and "last action=" in q and "task:" in q, q
    assert "trigger_reason" in evs[0] and evs[0]["query_mode"] == "common"
    # Q3 reason term under common = empty set (spy on _q3)
    com3 = fresh("progress", RPENT_MEMORY_RANK="Q3",
                 RPENT_MEMORY_QUERY_MODE="common")
    com3.task_language = "put the alphabet soup in the basket"
    cap = {}
    orig_q3 = DecisionMemory._q3
    com3._q3 = (lambda q, rt, obs, act, ph:
                cap.update(rt=rt, q=q) or ([], []))
    feed(com3, stalled, [1, 2])
    assert cap["rt"] == set(), "Q3 reason term must be empty under common"
    assert "stalled" not in cap["q"], cap["q"]
    print("  B.query_mode: native keeps reason in query; common strips it "
          "(lexical + Q3 term), event still logs the reason")


# ---------------------------------------------------------------- C
def test_q3_reads_trigger_result_not_later():
    """Fire queued on failing move A; pi0_pick B arrives later; the
    flush must rescore against A only."""
    tl = {"task_language": "put the alphabet soup in the basket"}
    dm = fresh("progress", RPENT_MEMORY_RANK="Q3")
    dm.task_language = "put the alphabet soup in the basket"
    dm._embedder = _FakeEmbedder()          # no network / model load
    cap = {}
    orig_q3 = DecisionMemory._q3

    def spy(q, rt, obs, act, ph):
        cap.update(q=q, obs=obs, act=act, ph=ph)
        return orig_q3(dm, q, rt, obs, act, ph)

    dm._q3 = spy
    dm.on_tool_result("move_to", json.dumps(
        {"final_eef_pos": [0.1, 0.2, 1.0], "final_dist_m": 0.2,
         "target_xyz": [0.5, 0.5, 1.0], "success": True, **tl}), False)
    dm.on_tool_result("pi0_pick", json.dumps(
        {"success": True, "diagnostics": {"post_min_ascent_m": 0.3},
         **tl}), False)
    r = dm.turn_boundary(1)
    assert r is not None, "queued fire on A must flush"
    assert cap["act"] == "move_to", f"action from B leaked: {cap['act']}"
    assert "0.2" in cap["obs"] and "move_to" in cap["obs"], cap["obs"]
    assert "pi0_pick" not in cap["obs"], cap["obs"]
    # _q3 must not consult flush-time state at all
    boom = RuntimeError("must not be called")
    dm2 = fresh("progress", RPENT_MEMORY_RANK="Q3")
    dm2.task_language = "put the alphabet soup in the basket"
    dm2._obs_summary = lambda: (_ for _ in ()).throw(boom)
    dm2.last_primitive = "pi0_pick"
    fake = _FakeEmbedder()
    dm2._embedder = fake
    top, _c = dm2._q3("q", {"stalled"}, "phase=P_transport; last "
                       "action=move_to; result fields={'final_dist_m': 0.2}",
                      "move_to", "P_transport")
    assert top, "explicit-state _q3 must work with params only"
    print("  C.q3_state: structured terms all from trigger result A "
          "(action/obs/phase); _obs_summary never consulted")


class _FakeEmbedder:
    """Deterministic stand-in: cosine similarity ~ token overlap."""
    def embed(self, texts):
        return [frozenset(t.lower().split()) for t in texts]

    @staticmethod
    def cos(a, b):
        inter = len(set(a) & set(b))
        return inter / (len(set(a) | set(b)) + 1e-9)


# ---------------------------------------------------------------- D
def test_motion_stuck():
    T = (0.5, 0.5, 1.0)
    # 1. same-target stalled moves -> fire
    dm = fresh("motion_stuck")
    dm.task_language = "put the alphabet soup in the basket"
    f = feed(dm, [res_move([0.10, 0.20, 1.00], 0.30, T),
                  res_move([0.1005, 0.2005, 1.0005], 0.2995, T),
                  res_move([0.101, 0.201, 1.001], 0.299, T)], [1])
    assert len(f) == 1 and "same-target" in f[0]["trigger_reason"], f
    assert f[0]["trigger_mode"] == "motion_stuck"
    print("  D.1 same-target stall fires")
    # 2. same-target progressing -> no fire
    dm = fresh("motion_stuck")
    dm.task_language = "put the alphabet soup in the basket"
    f = feed(dm, [res_move([0.10, 0.20, 1.00], 0.30, T),
                  res_move([0.1005, 0.2005, 1.0005], 0.28, T),
                  res_move([0.101, 0.201, 1.001], 0.26, T)], [1])
    assert f == [], f
    print("  D.2 same-target progress no fire")
    # 3. different targets -> no cross-target comparison, no fire
    dm = fresh("motion_stuck")
    dm.task_language = "put the alphabet soup in the basket"
    f = feed(dm, [res_move([0.10, 0.20, 1.00], 0.30, T),
                  res_move([0.1005, 0.2005, 1.0005], 0.2995, (0.6, 0.5, 1)),
                  res_move([0.101, 0.201, 1.001], 0.299, T)], [1])
    assert f == [], f
    print("  D.3 cross-target no fire")
    # 4. move-pick-move -> pick resets the window
    dm = fresh("motion_stuck")
    dm.task_language = "put the alphabet soup in the basket"
    seq = [res_move([0.10, 0.20, 1.00], 0.30, T),
           ("pi0_pick", {"success": True}),
           res_move([0.1005, 0.2005, 1.0005], 0.2995, T),
           res_move([0.101, 0.201, 1.001], 0.299, T)]
    f = feed(dm, seq, [1])
    assert f == [], f
    # control: without the pick the same 3 moves fire (test 1)
    print("  D.4 non-move primitive resets window")
    # 5. large EEF movement -> no fire
    dm = fresh("motion_stuck")
    dm.task_language = "put the alphabet soup in the basket"
    f = feed(dm, [res_move([0.10, 0.20, 1.00], 0.30, T),
                  res_move([0.20, 0.30, 1.00], 0.299, T),
                  res_move([0.30, 0.40, 1.00], 0.298, T)], [1])
    assert f == [], f
    print("  D.5 large displacement no fire")
    # 6. phase transition resets the window
    trk = FakeTracker()
    dm = fresh("motion_stuck", trk)
    dm.task_language = "put the alphabet soup in the basket"
    dm.on_tool_result(*_rt(res_move([0.10, 0.20, 1.00], 0.30, T)))
    dm.on_tool_result(*_rt(res_move([0.1005, 0.2005, 1.0005], 0.2995, T)))
    assert len(dm._mstuck_win) == 2
    trk.phase = "P_place"
    dm.turn_boundary(1)                       # phase transition boundary
    assert dm._mstuck_win == [], "phase change must reset the window"
    print("  D.6 phase transition resets window")
    # 7. missing target_xyz -> reset (no progress anchor)
    dm = fresh("motion_stuck")
    dm.task_language = "put the alphabet soup in the basket"
    dm.on_tool_result(*_rt(res_move([0.10, 0.20, 1.00], 0.30, T)))
    dm.on_tool_result("move_to", json.dumps(
        {"final_eef_pos": [0.1005, 0.2005, 1.0005], "final_dist_m": 0.2995,
         "success": True}), False)            # no target_xyz
    assert dm._mstuck_win == [], "missing target must reset the window"
    print("  D.7 missing target resets window")


def _rt(nr):
    return nr[0], json.dumps(nr[1]), False


# ---------------------------------------------------------------- E
def test_attempt_logging():
    tl = {"task_language": "put the alphabet soup in the basket"}
    dm = fresh("progress", RPENT_MEMORY_RANK="Q0_FIXED")
    dm.task_language = "put the alphabet soup in the basket"
    dm._q0_fixed = lambda q: ([], [])        # force EMPTY retrieval
    dm.on_tool_result("move_to", json.dumps(
        {"final_eef_pos": [0.1, 0.2, 1.0], "final_dist_m": 0.2,
         "target_xyz": [0.5, 0.5, 1.0], "success": True, **tl}), False)
    r = dm.turn_boundary(1)
    assert r is None, "EMPTY retrieval must not inject"
    assert len(dm.events) == 1, "EMPTY retrieval must still log the attempt"
    e = dm.events[0]
    assert e["trigger_fired"] is True
    assert e["retrieval_status"] == "EMPTY" and e["retrieval_empty"] is True
    assert e["top3_memories"] == [] and e["ranked_memory_ids"] == []
    # MATCH case carries the same fields flipped (deterministic top via stub)
    dm2 = fresh("progress", RPENT_MEMORY_RANK="Q0_FIXED")
    dm2.task_language = "put the alphabet soup in the basket"
    dm2._q0_fixed = lambda q: (dm2.ids[:1], dm2.ids)
    dm2.on_tool_result("move_to", json.dumps(
        {"final_eef_pos": [0.1, 0.2, 1.0], "final_dist_m": 0.2,
         "target_xyz": [0.5, 0.5, 1.0], "success": True, **tl}), False)
    r2 = dm2.turn_boundary(1)
    assert r2 is not None
    e2 = dm2.events[-1]
    assert e2["retrieval_status"] == "MATCH" and \
        e2["retrieval_empty"] is False and e2["trigger_fired"] is True
    print("  E.attempts: EMPTY logged w/o injection; MATCH carries fields")


# ---------------------------------------------------------------- F
def test_extra_bank_namespace():
    gids = set(DecisionMemory(FakeTracker()).cards)  # 61 global ids
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td) / "bankA", Path(td) / "bankB"
        a.mkdir(), b.mkdir()
        # invented tokens only -> no global card can tie on the query below
        body = "zorblax qwopui frobnicate procedure text"
        page = f"---\ntask_language: {body}\n---\n{body}"
        (a / "page_x.md").write_text(page)
        (b / "page_x.md").write_text(page)       # SAME stem, other dir
        (a / "page_y.md").write_text(page)
        dm = fresh("progress", RPENT_MEMORY_EXTRA_BANK=f"{a}:{b}")
        ids = set(dm.ids)
        assert "extra::bankA::page_x" in ids and \
            "extra::bankB::page_x" in ids, sorted(ids)[-3:]
        assert len(dm.ids) == 61 + 3, dm.ids
        assert gids <= ids, "global ids must be untouched"
        top, cand = dm._q0_fixed("task: zorblax qwopui frobnicate")
        assert len(cand) == 64
        assert top and all(t.startswith("extra::") for t in top), top
        assert all("bankA" not in t or t.startswith("extra::bankA")
                   for t in dm.ids)
    print("  F.namespace: cross-dir stems coexist; global ids intact; "
          "stem tokens drive scoring")


def main():
    test_rules_identity()
    test_signal_preservation()
    test_queue_drop_and_cap()
    test_first_primitive_gate()
    test_query_mode()
    test_q3_reads_trigger_result_not_later()
    test_motion_stuck()
    test_attempt_logging()
    test_extra_bank_namespace()
    clear_env(*G0_ENV_KEYS)
    print("ALL G0 AUDIT TESTS PASS")


if __name__ == "__main__":
    main()
