#!/usr/bin/env python3
"""Stage C1 — Query Sufficiency offline benchmark (design frozen in
analysis/memory_stageC1_design.md; run AFTER reading it, not before).

H1: online retrieval fails partly because the query does not describe what
is physically happening.  Three deterministic query templates — Q0_POOR
(#49 online text, verbatim replay incl. its known T4-reason quirk),
Q1_EXECUTION (phase/action/result triple), Q2_STATE_GROUNDED (Q1 + online
state block + failure_locus) — against the SAME frozen lexical retriever
(#49 Q0_FIXED).  Retriever, Memory bank and candidate set are identical
across arms; only the query text varies.  No LLM summarization anywhere.

Eval sets:
  primary  : Stage A SHOULD_RETRIEVE=YES rows (120, gold via Stage A map)
  hardneg  : Stage A hard_negative rows (14, gold=[] — retreat cards must
             NOT enter top-3)
  secondary: #49 aligned fires (gold via analyze_memory_stageB rules)

Usage: python scripts/memory_stagec1_benchmark.py [--dump]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

QUERIES = REPO / "analysis" / "memory_retrieval_queries.jsonl"
OVPM = REPO / "logs" / "ovpm_exp"

PRIMITIVES = ("pi0_pick", "pi0_doubled", "move_to", "move_pose", "release",
              "set_gripper", "rotate_wrist", "rotate_pitch")
PERCEPTION = ("segment", "back_project", "detect")

RETREAT_CARDS = ["predicate-fires-after-gripper-retreat",
                 "predicate-gated-by-eef-proximity-retreat-clear",
                 "open-retreat-settles-container", "basket-release-retreat-settle",
                 "basket-insertion-open-retreat"]

# ---------------------------------------------------------------- episode ctx


def _step_to_turn(run_log: Path) -> dict[int, int]:
    out: dict[int, int] = {}
    turn = 0
    try:
        for ln in run_log.read_text(errors="replace").splitlines():
            m = re.search(r"=== turn (\d+)/", ln)
            if m:
                turn = int(m.group(1))
                continue
            tm = re.search(r"\[tool<\] (\w+): ", ln)
            if tm:
                sm = re.search(r'"step": (\d+)', ln[tm.end():tm.end() + 60])
                if sm:
                    out.setdefault(int(sm.group(1)), turn)
    except OSError:
        pass
    return out


def _norm(name: str) -> str:
    return {"pick": "pi0_pick", "doubled": "pi0_doubled",
            "back_project": "back_project"}.get(name, name)


class EpisodeCtx:
    """Online-observable per-episode record (states / segments / b2 / turns)."""

    def __init__(self, ep: str):
        d = OVPM / ep
        self.ep = ep
        self.states = []
        try:
            self.states = json.load(open(d / "states.json"))
        except (OSError, json.JSONDecodeError):
            pass
        self.s2t = _step_to_turn(d / "run.log")
        # perception results are NOT in states.json — merge segment jsons as
        # pseudo tool results keyed by source_step
        self.segments = []
        try:
            for p in sorted((d / "segments").glob("segment_*.json")):
                s = json.load(open(p))
                m = re.search(r"segment_(\d+)", p.name)
                s["_step"] = int(m.group(1)) if m else int(s.get("source_step", 0))
                self.segments.append(s)
        except (OSError, json.JSONDecodeError):
            pass
        self.b2 = {}
        try:
            for ln in (d / "b2_events.jsonl").read_text().splitlines():
                if ln.strip():
                    e = json.loads(ln)
                    self.b2[e["turn"]] = e
        except (OSError, json.JSONDecodeError):
            pass

    def tl(self) -> str:
        for e in self.states:
            if e.get("task_language"):
                return str(e["task_language"])
        return ""

    def tool_stream(self):
        """[(step, turn, name, result_dict)] — primitives + perception."""
        out = []
        for e in self.states:
            r = e.get("result") or {}
            if isinstance(r, str):
                try:
                    r = json.loads(r)
                except json.JSONDecodeError:
                    r = {}
            name = _norm(r.get("name") or (e.get("command") or {}).get("action", ""))
            st = e.get("step_idx")
            if name:
                out.append((st, self.s2t.get(st, 0), name, r, e))
        for s in self.segments:
            out.append((s["_step"], self.s2t.get(s["_step"], 0), "segment",
                        {"found": s.get("found"),
                         "world_error": s.get("world_error")}, None))
        return sorted(out, key=lambda x: (x[0] is None, x[0]))

    def find_tool(self, turn: int, action: str):
        """States entry whose result name matches the decision action at or
        before the decision turn (b2 events fire on the reacting turn)."""
        want = _norm(action)
        cands = [t for t in self.tool_stream()
                 if t[1] <= turn and t[2] == want and t[4] is not None]
        if not cands:
            cands = [t for t in self.tool_stream()
                     if t[1] <= turn and t[4] is not None]
        return cands[-1] if cands else None


# ------------------------------------------------- #49 frozen trigger replay
class TriggerReplay:
    """Verbatim mirror of retrieval.py `_trigger_reason` state machine over an
    offline tool stream (T6 needs the live tracker — absent offline, 0 fires
    in #49; T7 phase transitions approximated by b2 phase changes)."""

    def __init__(self, ctx: EpisodeCtx):
        self.ctx = ctx
        self.recent: list[str] = []
        self.picks_failed = 0
        self.release_open = False
        self.phase_steps = 0
        self.last_phase = ""
        self.reasons: list[tuple[int, int, str, str, dict]] = []
        phase_by_turn = {t: e.get("phase", "") for t, e in ctx.b2.items()}
        for step, turn, name, r, _e in ctx.tool_stream():
            ph = phase_by_turn.get(turn, self.last_phase)
            if ph and ph != self.last_phase:
                self.last_phase = ph
                self.phase_steps = 0
            if name in PRIMITIVES:
                self.recent.append(name)
                self.recent = self.recent[-6:]
                self.phase_steps += 1
                if name == "pi0_pick" and r.get("success") is False:
                    self.picks_failed += 1
                if name == "release":
                    self.release_open = not r.get("libero_terminated", False)
            reason = self._reason(name, r, False)
            self.reasons.append((step, turn, name, reason, r))

    def _reason(self, name, data, is_error):
        if name == "pi0_pick" and data.get("success") is False:
            return "primitive_failure: pi0_pick reports no grasp"
        if name == "pi0_doubled" and data.get("success") is False:
            return "primitive_failure: contact skill did not terminate task"
        if name in ("move_to", "move_pose") and isinstance(
                data.get("final_dist_m"), (int, float)) \
                and data["final_dist_m"] > 0.03:
            return (f"primitive_failure: move stopped short "
                    f"({data['final_dist_m']:.3f} m residual)")
        if is_error:
            return f"primitive_failure: {name} returned error"
        if name == "pi0_pick" and data.get("success") is True:
            lift = (data.get("diagnostics") or {}).get("post_min_ascent_m")
            if isinstance(lift, (int, float)) and 0.0 <= lift < 0.05:
                return "pick_ambiguous: pick reports success but barely lifted"
        if name in PRIMITIVES and self.release_open \
                and not data.get("libero_terminated", False) and name != "release":
            return ("predicate_stalled: actions continue after release but "
                    "the task predicate has not fired")
        if len(self.recent) >= 3 and len(set(self.recent[-3:])) == 1:
            return f"repeated_no_progress: {name} x3 in a row"
        if self.picks_failed >= 2:
            return "repeated_no_progress: repeated failed picks"
        if name in PERCEPTION:
            if data.get("found") is False:
                return "perception_insufficient: segmentation found no mask"
            if data.get("world_error"):
                return f"perception_insufficient: {data['world_error']}"
        if self.phase_steps >= 8:
            return "phase_stalled: no phase transition across 8+ actions"
        return None

    def reason_at(self, turn: int, name: str) -> str:
        """First non-None frozen-rule reason at-or-after the decision point's
        tool result (within 3 stream entries) — what #49 would have fired for
        this situation (cooldown/cap ignored: text, not firing, is measured)."""
        idx = next((i for i, e in enumerate(self.reasons)
                    if e[1] == turn and e[2] == name), None)
        if idx is None:
            idx = next((i for i, e in enumerate(self.reasons) if e[1] >= turn), 0)
        for e in self.reasons[idx:idx + 3]:
            if e[3]:
                return e[3]
        return ""


# ------------------------------------------------------------- state block
def _round3(x):
    return round(float(x), 3) if isinstance(x, (int, float)) else None


def _grip_open(qpos) -> float:
    try:
        return round(sum(abs(q) for q in qpos), 3)
    except TypeError:
        return None


def state_facts(ctx: EpisodeCtx, step, action: str, r: dict, b2e: dict | None,
                entry: dict | None = None):
    """Derive the frozen Q2 facts + failure_locus from online-observable
    fields only (states.json pre-state / result dict / prior segments / b2
    semantic fields).

    Amendment (2026-09-18, pre-run fix): the b2 verifier's
    pre_state_summary.eef is a STALE constant (home pose, verified 0.3-0.46m
    off the true pre-state across episodes) — PRE eef/gripper come from the
    matched states.json entry's own `state` instead. b2 contributes only the
    semantic fields states.json lacks (held / last_transport_target).
    """
    pre = (b2e or {}).get("pre_state_summary") or {}
    held_pre = pre.get("held")
    held = {True: "true", False: "false"}.get(held_pre, "unknown")
    st = (entry or {}).get("state") or {}
    if st.get("robot0_eef_pos"):
        pre_eef = [round(x, 2) for x in st["robot0_eef_pos"]]
        pre_grip = _grip_open(st.get("robot0_gripper_qpos")) or "unknown"
    else:  # secondary set fallback: b2 numbers (stale-eef caveat in doc)
        pre_eef = [round(x, 2) for x in (pre.get("eef") or [])]
        pre_grip = _round3(pre.get("gripper_opening")) or "unknown"
    post_eef = [round(x, 3) for x in (r.get("final_eef_pos") or [])] or "unknown"
    # post gripper/predicate from the NEXT states entry (post-execution)
    nxt = [e for e in ctx.states
           if isinstance(e.get("step_idx"), int)
           and isinstance(step, int) and e["step_idx"] > step]
    post_grip = _grip_open((nxt[0].get("state") or {}).get("robot0_gripper_qpos")) \
        if nxt else "unknown"
    predicate = r.get("libero_terminated")
    if predicate is None and nxt:
        predicate = nxt[0].get("libero_terminated")
    # last perception before the point
    segs = [s for s in ctx.segments
            if isinstance(step, int) and s["_step"] <= step] or \
           [s for s in ctx.segments]
    last_seg = segs[-1] if segs else None
    detected = {True: "true", False: "false"}.get(
        last_seg.get("found")) if last_seg else None
    if detected is None:
        detected = "true" if pre.get("objects") else "unknown"
    # lift evidence
    lift = (r.get("diagnostics") or {}).get("post_min_ascent_m") \
        if isinstance(r.get("diagnostics"), dict) else None
    if isinstance(lift, (int, float)):
        lifted = "true" if lift >= 0.05 else "false"
    elif held_pre is True:
        lifted = "true"
    else:
        lifted = "unknown"
    moves_with = held
    # last commanded transport target: last move command before the point
    # (states.json `command.xyz` — online-true; b2 value only as fallback)
    tgt = []
    if isinstance(step, int):
        for e in ctx.states:
            si, cmd = e.get("step_idx"), e.get("command") or {}
            if isinstance(si, int) and si <= step and cmd.get("action") in (
                    "move_to", "move_pose") and cmd.get("xyz"):
                tgt = [round(x, 3) for x in cmd["xyz"]]
    tgt = tgt or [round(x, 3) for x in (pre.get("last_transport_target") or [])]
    obj = (last_seg or {}).get("world_xyz") or []
    if tgt and obj:
        dobj = round(sum((a - b) ** 2 for a, b in zip(obj, tgt)) ** 0.5, 3)
        obj_rel = f"near({dobj}m)" if dobj <= 0.05 else f"far({dobj}m)"
    else:
        obj_rel = "unknown"
    if tgt and pre_eef:
        deef = round(sum((a - b) ** 2 for a, b in zip(pre_eef, tgt)) ** 0.5, 3)
        eef_near = f"true({deef}m)" if deef <= 0.05 else f"false({deef}m)"
    else:
        eef_near = "unknown"
    delta = (b2e or {}).get("observed_change") if b2e else None
    if not delta and r:
        delta = r.get("observed_change") or None
    missing = (b2e or {}).get("missing_evidence") or []

    # ---- failure_locus (frozen rule order, task-free)
    fd = final_dist = r.get("final_dist_m")
    locus = "UNKNOWN"
    if detected == "false" or any("no usable object position" in str(m).lower()
                                  for m in missing):
        locus = "PERCEPTION"
    elif action == "pi0_pick" and (r.get("success") is False
                                   or lifted == "false"):
        locus = "GRASP"
    elif action in ("move_to", "move_pose") and isinstance(fd, (int, float)) \
            and fd > 0.03:
        locus = "TRANSPORT"
    elif action == "release" or (b2e or {}).get("phase", "") in ("P_place",
                                                                "P_verify"):
        if obj_rel.startswith("far"):
            locus = "PLACE"
        elif obj_rel.startswith("near") and predicate is False:
            locus = "PREDICATE"
    facts = {
        "PRE": f"eef={pre_eef} gripper_opening={pre_grip} held={held}",
        "POST": f"eef={post_eef} gripper_opening={post_grip} "
                f"predicate={predicate}",
        "DELTA": delta or "unknown",
        "OBJECT_DETECTED": detected, "OBJECT_LIFTED": lifted,
        "OBJECT_MOVES_WITH_GRIPPER": moves_with,
        "PREDICATE": {True: "true", False: "false"}.get(predicate, "unknown"),
        "OBJECT_TARGET_RELATION": obj_rel, "EEF_NEAR_TARGET": eef_near,
        "LOCUS": locus,
    }
    return facts


# ------------------------------------------------------------- query builds
def prim_result(action: str, r: dict) -> str:
    if action in ("pi0_pick", "pi0_doubled"):
        return str(r.get("success")).lower() if r.get("success") is not None \
            else "unknown"
    if action in ("move_to", "move_pose"):
        return f"final_dist_m={r.get('final_dist_m')}"
    if action == "release":
        return f"libero_terminated={r.get('libero_terminated')}"
    if action in PERCEPTION:
        return f"found={r.get('found')}"
    return "error" if r.get("is_error") else "ok"


def build_queries(phase, action, r, tl, facts, reason):
    keys = ("success", "libero_terminated", "final_dist_m", "found",
            "world_error", "min_gripper_opening")
    fields = {k: r[k] for k in keys if k in r}
    q0 = (f"phase={phase}; last action={action}; result fields={fields}; "
          f"task: {tl[:110]} | {reason or '(no trigger signal)'}")
    q1 = f"PHASE={phase} ACTION={action} RESULT={prim_result(action, r)}" \
         f" | task: {tl[:110]}"
    q2 = (f"{q1}\nPRE: {facts['PRE']}\nPOST: {facts['POST']}\n"
          f"DELTA: {facts['DELTA']}\n"
          f"FACTS: OBJECT_DETECTED={facts['OBJECT_DETECTED']} "
          f"OBJECT_LIFTED={facts['OBJECT_LIFTED']} "
          f"OBJECT_MOVES_WITH_GRIPPER={facts['OBJECT_MOVES_WITH_GRIPPER']} "
          f"PREDICATE={facts['PREDICATE']} "
          f"OBJECT_TARGET_RELATION={facts['OBJECT_TARGET_RELATION']} "
          f"EEF_NEAR_TARGET={facts['EEF_NEAR_TARGET']}\n"
          f"LOCUS: {facts['LOCUS']}")
    return {"Q0_POOR": q0, "Q1_EXECUTION": q1, "Q2_STATE_GROUNDED": q2}


# ------------------------------------------------------- frozen lexical rank
class Lexical:
    """Verbatim #49 `_q0_fixed` scoring (untruncated ordering kept for
    R@5/MRR; the top-3 cut itself is the deployed behavior)."""

    def __init__(self):
        self.cards = load_cards()
        self.index = load_index()
        self.ids = sorted(self.cards)

    def rank(self, q: str, tl: str) -> list[str]:
        qt = toks(q) | toks(tl)
        scored = sorted(
            ((len(qt & (toks(self.index.get(c, self.cards[c]["title"]))
                        | toks(c.replace("-", " ")))), c) for c in self.ids),
            reverse=True)
        return [c for _s, c in scored]


# ------------------------------------------------------------------ metrics
def _pos_list(lex: Lexical, q: str, tl: str) -> list[str]:
    """Frozen lexical ordering, >0-overlap cut kept (deployment semantics:
    cards with zero token overlap are never returned)."""
    order = lex.rank(q, tl)
    qt = toks(q) | toks(tl)
    return [c for c in order
            if len(qt & (toks(lex.index.get(c, lex.cards[c]["title"]))
                         | toks(c.replace("-", " ")))) > 0]


def metrics(points, lex: Lexical, arms):
    """points: [{class, gold(list|None=hardneg), queries{arm:q}, tl}]"""
    out = {}
    for arm in arms:
        per: dict[str, collections.Counter] = \
            collections.defaultdict(collections.Counter)
        for p in points:
            pos = _pos_list(lex, p["queries"][arm], p["tl"])
            top3 = pos[:3]
            c = per[p["class"]]
            c["n"] += 1
            if p["gold"] is None:  # hard negative: retreat must stay out
                c["retreat_in_top3"] += bool(set(top3) & set(RETREAT_CARDS))
                continue
            g = set(p["gold"])
            c["R@1"] += bool(top3 and top3[0] in g)
            c["R@3"] += bool(set(top3) & g)
            c["R@5"] += bool(set(pos[:5]) & g)
            c["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                              if x in g), 0.0)
            c["empty_top3"] += not top3
            c["irrelevant@3"] += bool(top3) and not set(top3) & g
        rows = {}
        for cls, c in sorted(per.items()):
            n = c["n"]
            rows[cls] = {
                "n": n,
                "R@1": round(c["R@1"] / n, 3),
                "R@3": round(c["R@3"] / n, 3),
                "R@5": round(c["R@5"] / n, 3),
                "MRR": round(c["MRR"] / n, 3),
                "empty_top3": c["empty_top3"],
                "irrelevant@3": round(c["irrelevant@3"] / n, 3),
                "retreat_in_top3": c["retreat_in_top3"],
            }
        allc: collections.Counter = collections.Counter()
        for p in points:
            allc["n"] += 1
            pos = _pos_list(lex, p["queries"][arm], p["tl"])
            top3 = pos[:3]
            if p["gold"] is None:
                allc["retreat_in_top3"] += bool(set(top3)
                                                & set(RETREAT_CARDS))
                continue
            g = set(p["gold"])
            allc["R@1"] += bool(top3 and top3[0] in g)
            allc["R@3"] += bool(set(top3) & g)
            allc["R@5"] += bool(set(pos[:5]) & g)
            allc["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                                 if x in g), 0.0)
            allc["empty_top3"] += not top3
            allc["irrelevant@3"] += bool(top3) and not set(top3) & g
        n = allc["n"]
        rows["ALL"] = {
            "n": n,
            "R@1": round(allc["R@1"] / n, 3),
            "R@3": round(allc["R@3"] / n, 3),
            "R@5": round(allc["R@5"] / n, 3),
            "MRR": round(allc["MRR"] / n, 3),
            "empty_top3": allc["empty_top3"],
            "irrelevant@3": round(allc["irrelevant@3"] / n, 3),
            "retreat_in_top3": allc["retreat_in_top3"],
        }
        out[arm] = rows
    return out


# --------------------------------------------------------------------- main
def build_primary_points():
    rows = [json.loads(l) for l in open(QUERIES)]
    ctxs: dict[str, EpisodeCtx] = {}
    replays: dict[str, TriggerReplay] = {}
    tl_cache: dict[str, str] = {}
    points, skipped = [], []
    for r in rows:
        if not (r["should_retrieve"] == "YES"
                or r.get("hard_negative_for")):
            continue
        ep = r["episode"]
        if ep not in ctxs:
            ctxs[ep] = EpisodeCtx(ep)
            replays[ep] = TriggerReplay(ctxs[ep])
            tl_cache[ep] = ctxs[ep].tl()
        ctx, rep = ctxs[ep], replays[ep]
        b2e = ctx.b2.get(r["turn"])
        action = _norm((b2e or {}).get("action") or r.get("last_action", ""))
        found = ctx.find_tool(r["turn"], action)
        if not found:
            skipped.append((ep, r["turn"], "no tool result"))
            continue
        step, _turn, name, res, _entry = found
        reason = rep.reason_at(_turn, name)
        facts = state_facts(ctx, step, name, res, b2e, entry=_entry)
        gold = r["gold_memory_ids"] if r["should_retrieve"] == "YES" else None
        points.append({
            "set": "hardneg" if gold is None else "primary",
            "class": r["class"], "gold": gold,
            "episode": ep, "turn": r["turn"],
            "tl": tl_cache[ep],
            "queries": build_queries(r.get("phase") or (b2e or {}).get("phase", ""),
                                     name, res, tl_cache[ep], facts, reason),
            "reason": reason, "locus": facts["LOCUS"],
        })
    return points, skipped


def build_secondary_points(lex: Lexical):
    """#49 aligned fires: reuse the Stage B annotation pipeline."""
    import analyze_memory_stageB as sb
    events = sb.load_events()
    moments = {d.name: sb.should_retrieve_moments(d)
               for d in sorted(OVPM.glob("*_memB[23]_*")) if d.is_dir()}
    sb.annotate_gold(events, moments)
    ctxs, replays, tls = {}, {}, {}
    points = []
    for ep, evs in events.items():
        for e in evs:
            if not (str(e.get("gold_note", "")).startswith("class=")
                    or str(e.get("gold_note", "")).startswith("hard_negative")):
                continue
            if ep not in ctxs:
                ctxs[ep] = EpisodeCtx(ep)
                replays[ep] = TriggerReplay(ctxs[ep])
                tls[ep] = ctxs[ep].tl()
            ctx = ctxs[ep]
            action = _norm(e.get("last_action") or "")
            found = ctx.find_tool(e["turn"], action)
            if not found:
                continue
            step, _turn, name, res, _entry = found
            reason = e.get("trigger_reason") or replays[ep].reason_at(
                e["turn"], name)
            facts = state_facts(ctx, step, name, res, None, entry=_entry)
            gold = e.get("gold_memory_ids")
            if gold == [] and str(e.get("gold_note", "")).startswith("hard_neg"):
                gold = None  # retreat cards must stay out
            points.append({
                "set": "secondary", "class": e.get("gold_note", "").split("=")[-1]
                if gold else "hard_negative",
                "gold": gold, "episode": ep, "turn": e["turn"],
                "tl": e.get("task_language") or tls[ep],
                "queries": build_queries(e.get("phase") or "", name, res,
                                         e.get("task_language") or tls[ep],
                                         facts, reason),
                "reason": reason, "locus": facts["LOCUS"],
            })
    return points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()
    lex = Lexical()
    arms = ["Q0_POOR", "Q1_EXECUTION", "Q2_STATE_GROUNDED"]

    points, skipped = build_primary_points()
    print(f"primary+hardneg points: {len(points)} (skipped {len(skipped)})")
    for s in skipped[:10]:
        print("  skip:", s)

    yes = [p for p in points if p["set"] == "primary"]
    hn = [p for p in points if p["set"] == "hardneg"]
    res = {
        "primary": metrics(yes, lex, arms),
        "hardneg": metrics(hn, lex, arms),
    }
    # locus distribution (does failure_locus add discrimination?)
    res["locus_by_class"] = {
        cls: dict(collections.Counter(p["locus"] for p in yes
                                      if p["class"] == cls))
        for cls in sorted({p["class"] for p in yes})}

    try:
        sec = build_secondary_points(lex)
        gold_sec = [p for p in sec if p["gold"]]
        hn_sec = [p for p in sec if not p["gold"]]
        res["secondary_gold"] = metrics(gold_sec, lex, arms) if gold_sec else {}
        res["secondary_hardneg"] = metrics(hn_sec, lex, arms) if hn_sec else {}
        res["secondary_n"] = {"gold": len(gold_sec), "hardneg": len(hn_sec)}
    except Exception as exc:  # noqa: BLE001 — secondary is best-effort
        print("secondary set failed:", exc)
        res["secondary_n"] = {"error": str(exc)}

    # perception-17 special (spec: report hit counts per arm)
    perc = [p for p in yes if p["class"] == "perception"]
    res["perception17_hits"] = {}
    for arm in arms:
        h1 = h3 = 0
        for p in perc:
            pos = _pos_list(lex, p["queries"][arm], p["tl"])
            g = set(p["gold"])
            h1 += bool(pos and pos[0] in g)
            h3 += bool(set(pos[:3]) & g)
        res["perception17_hits"][arm] = {"R@1": h1, "R@3": h3, "n": len(perc)}

    out = REPO / "analysis" / "memory_stageC1_results.json"
    json.dump(res, open(out, "w"), indent=2, ensure_ascii=False)
    print("wrote", out)

    if args.dump:
        dump = REPO / "analysis" / "memory_stageC1_queries.jsonl"
        with open(dump, "w") as f:
            for p in points:
                f.write(json.dumps(p, ensure_ascii=False, default=str) + "\n")
        print("wrote", dump)

    # console summary
    for name in ("primary", "hardneg"):
        print(f"\n== {name} ==")
        for arm in arms:
            a = res[name][arm]["ALL"]
            print(f"  {arm:18s} R@1={a['R@1']} R@3={a['R@3']} R@5={a['R@5']} "
                  f"MRR={a['MRR']} empty={a['empty_top3']} "
                  f"irr@3={a['irrelevant@3']} retreat_in_top3="
                  f"{a['retreat_in_top3']}")
    print("\n== perception-17 hits ==")
    print(json.dumps(res["perception17_hits"], indent=1))
    print("\n== locus by class ==")
    print(json.dumps(res["locus_by_class"], indent=1))

    # pre-registered gate
    q0r = res["primary"]["Q0_POOR"]["ALL"]["R@3"]
    q2r = res["primary"]["Q2_STATE_GROUNDED"]["ALL"]["R@3"]
    delta = round(q2r - q0r, 3)
    print(f"\nGATE: Q2-Q0 R@3 delta = {delta} "
          f"({'pass (>=0.10)' if delta >= 0.10 else 'check subsets'})")


if __name__ == "__main__":
    main()
