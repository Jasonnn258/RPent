#!/usr/bin/env python3
"""Stage E2 — Failure-Origin extraction (deterministic, family-level rules).

FAILURE ORIGIN (per user spec): "the earliest precondition, observable from
the execution trace, that was not met" — NOT philosophical causation.

Inputs per decision point: EpisodeCtx (states.json results, segment jsons,
b2_events.jsonl) — all runtime-observable. NO simulator hidden state, no
final success, no future.

Window: backwards from the decision event to min(last phase transition,
last 5 key events). Key events = perception (segment/back_project), picks
(pi0_pick/pi0_doubled), release; consecutive move/gripper/rotate calls are
compressed into one MOVE_RUN.

Primitive-family preconditions (ONLY family-level, no task-specific rules):

  PERCEPTION output  : USABLE_SEGMENTATION (found), VALID_TARGET_LOCALIZATION
                       (found but world position invalid)
  GRASP precondition : valid target localization; output: OBJECT_HELD_EVIDENCE
                       (success + peak_lift_m >= LIFT_T = 0.05, the recipes'
                       own lift_thresh)
  TRANSPORT precond  : object held; output: IMPROVING_OBJECT_TARGET_RELATION
                       (run's final_dist decreasing)
  RELEASE / PREDICATE: CONFIRMED_SETTLED_TARGET_RELATION + EEF_CLEAR (release
                       done but predicate false, eef still near target)

Query templates (head = frozen C1 Q0 text, tail swapped — the ONLY variable):
  E2_RAW_TRACE       "... | RAW-TRACE: t16 pi0_pick success=True ...; ..."
  E3_FAILURE_ORIGIN  "... | SURFACE=GRASP; ORIGIN=PERCEPTION; MISSING=...;
                       EVIDENCE=..."

TEMPLATE-FREEZE DISCIPLINE: EVIDENCE strings are VERBATIM runtime
observables only (b2 missing_evidence phrases, receipt fields mode/prompt/
world_error, primitive numbers). No synonyms, no vocabulary added toward
any card. Templates were fixed after surveying the observable vocabulary
(b2's 5-phrase set, receipt field names) and BEFORE any retrieval scoring
run; the single 4-arm benchmark run happens on the frozen templates.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from memory_stagec1_benchmark import EpisodeCtx, _norm  # noqa: E402

LIFT_T = 0.05          # recipes' own lift_thresh (family constant)
DIST_PROGRESS_T = 0.01  # 1 cm improvement across a move run
PERCEPTION_TOOLS = ("segment", "back_project", "detect")
MOVE_TOOLS = ("move_to", "move_pose", "set_gripper", "rotate_wrist",
              "rotate_pitch")

SURFACE_BY_ACTION = {
    "pi0_pick": "GRASP", "pi0_doubled": "GRASP",
    "segment": "PERCEPTION", "back_project": "PERCEPTION", "detect": "PERCEPTION",
    "release": "PREDICATE",
    "move_to": "TRANSPORT", "move_pose": "TRANSPORT",
}
SURFACE_BY_CLASS = {"predicate_timing": "PREDICATE", "recovery": "RECOVERY",
                    "perception": "PERCEPTION", "grasp": "GRASP",
                    "pick_verify": "GRASP"}


def _res_num(r: dict, k: str):
    v = r.get(k)
    return v if isinstance(v, (int, float)) else None


def classify_surface(action: str, phase: str, cls: str) -> str:
    a = _norm(action or "")
    if a in SURFACE_BY_ACTION:
        if a in ("move_to", "move_pose") and "transport" not in (phase or ""):
            return "RECOVERY"
        return SURFACE_BY_ACTION[a]
    return SURFACE_BY_CLASS.get(cls, "UNKNOWN")


# ------------------------------------------------------------- window build
def key_window(ctx: EpisodeCtx, turn: int, action: str, max_events: int = 5):
    """[(kind, step, turn, name, result, extra)] — compressed, chronological,
    strictly before the decision event, bounded by the last phase change."""
    found = ctx.find_tool(turn, action)
    if not found:
        return [], None
    dstep, _dturn, dname, dres, _e = found
    phase_by_turn = {t: e.get("phase", "") for t, e in ctx.b2.items()}
    stream = [t for t in ctx.tool_stream() if (t[0] is not None
                                               and t[0] < dstep)]
    # compress move runs
    comp = []
    for st, tn, name, r, e in stream:
        if name in PERCEPTION_TOOLS or name in ("pi0_pick", "pi0_doubled",
                                                "release"):
            comp.append(("KEY", st, tn, name, r, {}))
        elif name in MOVE_TOOLS and comp and comp[-1][0] == "RUN":
            prev = comp[-1]
            comp[-1] = ("RUN", prev[1], prev[2], "move_run",
                        prev[4],
                        {"n": prev[5].get("n", 0) + 1,
                         "d_first": prev[5].get("d_first",
                                                _res_num(r, "final_dist_m")),
                         "d_last": _res_num(r, "final_dist_m")})
        elif name in MOVE_TOOLS:
            comp.append(("RUN", st, tn, "move_run", r,
                         {"n": 1, "d_first": _res_num(r, "final_dist_m"),
                          "d_last": _res_num(r, "final_dist_m")}))
    # phase boundary: drop events before the last phase change if that keeps
    # at least one event (spec: min(last transition, last 5 events))
    dphase = phase_by_turn.get(turn, "")
    if dphase:
        last_change = None
        for i in range(1, len(comp)):
            p_prev = phase_by_turn.get(comp[i - 1][2], "")
            p_cur = phase_by_turn.get(comp[i][2], "")
            if p_cur and p_prev and p_cur != p_prev:
                last_change = i
        if last_change is not None and len(comp) - last_change >= 1:
            comp = comp[last_change:]
    window = comp[-max_events:]
    return window, (dstep, dname, dres, phase_by_turn.get(turn, ""))


# ------------------------------------------------------------- perception ok
def perception_status(r: dict):
    """(ok, missing, phrase) for a perception pseudo-result."""
    found = r.get("found")
    werr = r.get("world_error")
    if found is False:
        return (False, "USABLE_SEGMENTATION",
                f"segmentation found={found}"
                + (f" ({werr})" if werr else ""))
    if found and werr:
        return (False, "VALID_TARGET_LOCALIZATION",
                f"segment found but {werr}")
    if found:
        return (True, "", "segmentation found with world position")
    return (None, "", "segmentation result unavailable")


# ------------------------------------------------------- b2 evidence layer
# The runtime B2 verifier emits a FIXED 5-phrase missing_evidence vocabulary
# (surveyed over all 76 study episodes: no other strings occur). Each phrase
# names an unmet observable prerequisite of exactly one primitive family.
B2_PHRASE_FAMILY = [
    ("no usable object position",
     ("PERCEPTION", "VALID_TARGET_LOCALIZATION")),
    ("object displacement",
     ("GRASP", "OBJECT_MOVES_WITH_GRIPPER")),
    ("final relation",
     ("PLACE", "CONFIRMED_SETTLED_TARGET_RELATION")),
]
# "the directed observation never ran" is process commentary (a check was
# skipped), not a named prerequisite — carried into EVIDENCE only.
FAMILY_ORDER = ["PERCEPTION", "GRASP", "TRANSPORT", "PLACE"]


def b2_window(ctx: EpisodeCtx, turn: int, max_turns: int = 5):
    """b2 events at turns <= decision (state of knowledge AT the decision),
    last `max_turns` distinct turns, chronological."""
    turns = sorted(t for t in ctx.b2 if t <= turn)[-max_turns:]
    return [(t, ctx.b2[t]) for t in turns]


def _classify_phrase(p: str):
    for key, fam in B2_PHRASE_FAMILY:
        if key in p:
            return fam
    return None


# ------------------------------------------------------------- origin rules
def extract_origin(ctx: EpisodeCtx, turn: int, action: str, cls: str):
    """Returns dict(surface, origin, missing, evidence, confidence, window).

    Layer 1 (primary): B2 missing_evidence phrases inside the window — the
    verifier's own runtime words for the unmet prerequisite. Origin = the
    most UPSTREAM family present (prerequisites flow PERCEPTION -> GRASP ->
    TRANSPORT -> PLACE), ties broken by earliest turn.
    Layer 2 (fallback): primitive-result rules (lift / terminated / distance
    / segment pseudo-results)."""
    window, dec = key_window(ctx, turn, action)
    dphase = (ctx.b2.get(turn) or {}).get("phase", dec[3] if dec else "")
    surface = classify_surface(action, dphase, cls)
    base = {"surface": surface, "window":
            [(k, s, t, n) for k, s, t, n, _r, _x in window]}
    if dec is None:
        return {**base, "origin": "UNKNOWN", "missing": "",
                "evidence": "no tool result at decision point",
                "confidence": "LOW"}
    dstep, dname, dres, _ = dec

    fam_hits: dict[str, tuple[int, str]] = {}   # family -> (turn, phrase)
    skipped: list[str] = []
    for t, ev in b2_window(ctx, turn):
        for p in (ev.get("missing_evidence") or []):
            fam = _classify_phrase(p)
            if fam is None:
                skipped.append(f"t{t} {p}")
                continue
            f, miss = fam
            if f not in fam_hits or t < fam_hits[f][0]:
                fam_hits[f] = (t, f"t{t} b2 missing: {p}")
    if fam_hits:
        f0 = min(fam_hits, key=lambda f: FAMILY_ORDER.index(f))
        _t0, ev0 = fam_hits[f0]
        evidence = ev0
        # append the origin family's own verbatim observable, if any
        if f0 == "PERCEPTION":
            obs = perception_observables(ctx, turn, dstep)
            bad = [p for _t, p in obs
                   if "found=False" in p or "no position" in p or "err=" in p]
            if bad:
                evidence += f"; {bad[-1]}"
        elif f0 == "GRASP":
            for kind, st, tn, name, r, _x in reversed(window):
                if name in ("pi0_pick", "pi0_doubled"):
                    lift = _res_num(r, "peak_lift_m")
                    evidence += (f"; {name} success={r.get('success')}"
                                 + (f" peak_lift={lift:.3f}"
                                    if lift is not None else ""))
                    break
        elif f0 == "PLACE":
            for kind, st, tn, name, r, _x in reversed(window):
                if name == "release":
                    evidence += f"; release terminated={r.get('libero_terminated')}"
                    break
        if skipped:
            evidence += f"; also [{'; '.join(skipped[-2:])}]"
        missing = next(m for _k, (ff, m) in B2_PHRASE_FAMILY if ff == f0)
        return {**base, "origin": f0, "missing": missing,
                "evidence": evidence, "confidence": "HIGH"}

    # ---- layer 2: primitive fallback
    loc_valid: bool | None = None
    loc_missing, loc_phrase = "", ""
    held = False
    origin = missing = evidence = ""
    conf = "LOW"
    healthy = True

    for kind, st, tn, name, r, extra in window:
        ph = (ctx.b2.get(tn) or {}).get("phase", "")
        if name in PERCEPTION_TOOLS:
            ok, miss, phrase = perception_status(r)
            if ok is False:
                loc_valid, loc_missing, loc_phrase = False, miss, phrase
                healthy = False
            elif ok:
                loc_valid = True
        elif name in ("pi0_pick", "pi0_doubled"):
            if loc_valid is False and not held and not origin:
                origin = "PERCEPTION"
                missing = loc_missing
                evidence = (f"{loc_phrase} at step {st}; planner proceeded; "
                            f"pi0_pick success={r.get('success')}")
                conf = "HIGH"
                healthy = False
            lift = _res_num(r, "peak_lift_m")
            held_now = bool(r.get("success")) and lift is not None \
                and lift >= LIFT_T
            if held_now:
                held = True
            elif not origin:
                origin = "GRASP"
                missing = "OBJECT_HELD_EVIDENCE"
                lift_s = f"{lift:.3f}" if lift is not None else "n/a"
                evidence = (f"pi0_pick success={r.get('success')} "
                            f"peak_lift={lift_s} below lift threshold")
                conf = "MEDIUM"
                healthy = False
        elif name == "move_run":
            if "transport" in ph and not held and not origin:
                origin = "GRASP"
                missing = "OBJECT_HELD"
                evidence = "transport moves without prior hold evidence"
                conf = "MEDIUM"
                healthy = False
            elif "transport" in ph and not origin:
                d0, d1 = extra.get("d_first"), extra.get("d_last")
                if d0 is not None and d1 is not None \
                        and d1 > d0 - DIST_PROGRESS_T:
                    origin = "TRANSPORT"
                    missing = "IMPROVING_OBJECT_TARGET_RELATION"
                    evidence = (f"{extra.get('n')} transport moves with "
                                f"distance {d0:.3f}->{d1:.3f} not improving")
                    conf = "MEDIUM"
                    healthy = False
        elif name == "release":
            if not r.get("libero_terminated") and not origin:
                origin = "PLACE"
                missing = "CONFIRMED_SETTLED_TARGET_RELATION"
                evidence = ("release done; predicate false; "
                            "eef still near target")
                conf = "MEDIUM"
                healthy = False

    if not origin:
        if not window:
            origin, missing = "UNKNOWN", ""
            evidence = "no prior key events in window"
            conf = "LOW"
        elif healthy:
            origin = "NONE"
            missing = ""
            evidence = "prerequisites met so far; progress normal"
            conf = "HIGH"
        else:  # healthy flag lost but no origin assigned (shouldn't happen)
            origin, missing = "UNKNOWN", ""
            evidence = "window inconsistent"
            conf = "LOW"
    return {**base, "origin": origin, "missing": missing,
            "evidence": evidence, "confidence": conf}


# ------------------------------------------------------- run.log receipts
_RECEIPT_CACHE: dict[str, list] = {}


def tool_receipts(ep: str) -> list:
    """[(turn, name, fields)] for back_project/segment receipts in run.log.
    The logger truncates long lines, so fields are regex-extracted, not
    json-parsed."""
    if ep in _RECEIPT_CACHE:
        return _RECEIPT_CACHE[ep]
    out = []
    try:
        turn = None
        for ln in (REPO / "logs" / "ovpm_exp" / ep / "run.log").read_text(
                errors="replace").splitlines():
            m = re.search(r"=== turn (\d+)/", ln)
            if m:
                turn = int(m.group(1))
                continue
            tm = re.search(r"\[tool<\] (back_project|segment): ", ln)
            if tm and turn is not None:
                body = ln[tm.end():]
                f: dict = {"turn": turn, "name": tm.group(1)}
                for key in ("mode", "camera", "found"):
                    km = re.search(rf'"{key}": ("?[\w-]+"?)', body)
                    if km:
                        f[key] = km.group(1).strip('"')
                pm = re.search(r'"prompt": "([^"]{0,90})', body)
                if pm:
                    f["prompt"] = pm.group(1)
                em = re.search(r'"world_error": "([^"]{0,90})', body)
                if em:
                    f["world_error"] = em.group(1)
                f["has_position"] = bool(
                    re.search(r'"(world_xyz|center_xyz)"', body))
                out.append((turn, tm.group(1), f))
    except OSError:
        pass
    _RECEIPT_CACHE[ep] = out
    return out


def perception_observables(ctx: EpisodeCtx, turn: int, dstep) -> list:
    """Verbatim perception observations before the decision point:
    [(turn_or_None, phrase)]. Sources: segment pseudo-results with _step <
    dstep, and back_project receipts at turns <= decision turn."""
    out = []
    for s in ctx.segments:
        st = s.get("_step")
        if st is None or dstep is None or not st < dstep:
            continue
        ph = f"segment mode={s.get('mode')} prompt='{str(s.get('prompt'))[:70]}'"
        ph += f" found={s.get('found')}"
        if s.get("world_error"):
            ph += f" err='{str(s['world_error'])[:70]}'"
        out.append((None, ph))
    for t, name, f in tool_receipts(ctx.ep):
        if t > turn or name != "back_project":
            continue
        pos = "ok" if f.get("has_position") else "no position"
        out.append((t, f"back_project {f.get('camera','')} {pos}"))
    return out[-3:]


# ------------------------------------------------------------- query build
def _head(q0: str) -> str:
    return q0.split(" | ")[0]


def raw_trace_query(q0: str, ctx: EpisodeCtx, turn: int, action: str) -> str:
    """E2_RAW_TRACE: last key events (primitives + perception observables +
    b2 verification phrases), verbatim, compressed. NO interpretation."""
    window, dec = key_window(ctx, turn, action)
    dstep = dec[0] if dec else None
    events: list[tuple] = []
    for kind, st, tn, name, r, extra in window[-5:]:
        if name in PERCEPTION_TOOLS:
            continue
        if name in ("pi0_pick", "pi0_doubled"):
            lift = _res_num(r, "peak_lift_m")
            events.append((tn, f"{name} success={r.get('success')}"
                          + (f" peak_lift={lift:.3f}" if lift is not None
                             else "")))
        elif name == "release":
            events.append((tn, f"release terminated="
                          f"{r.get('libero_terminated')}"))
        else:
            d0, d1 = extra.get("d_first"), extra.get("d_last")
            events.append((tn, f"move_run x{extra.get('n')}"
                          + (f" dist {d0:.3f}->{d1:.3f}"
                             if d0 is not None and d1 is not None else "")))
    for t, ph in perception_observables(ctx, turn, dstep):
        events.append((t if t is not None else 0, ph))
    for t, ev in b2_window(ctx, turn):
        for p in (ev.get("missing_evidence") or []):
            events.append((t, f"verify missing: {p}"))
    events.sort(key=lambda x: x[0])
    parts = [f"t{t} {txt}" for t, txt in events[-6:]]
    trace = "; ".join(parts) if parts else "(no prior events)"
    return f"{_head(q0)} | RAW-TRACE: {trace}"


def failure_origin_query(q0: str, o: dict) -> str:
    block = (f"SURFACE={o['surface']}; ORIGIN={o['origin']}"
             + (f"; MISSING={o['missing']}" if o["missing"] else "")
             + (f"; EVIDENCE={o['evidence'][:240]}" if o["evidence"] else ""))
    return f"{_head(q0)} | {block}"


def origin_event_phrase(r: dict, name: str) -> str:
    """Compact observable outcome phrase for one event (audit display)."""
    if name in PERCEPTION_TOOLS:
        _, miss, phrase = perception_status(r)
        return phrase
    if name in ("pi0_pick", "pi0_doubled"):
        lift = _res_num(r, "peak_lift_m")
        g = _res_num(r, "min_gripper_opening")
        return (f"success={r.get('success')}"
                + (f" peak_lift={lift:.3f}" if lift is not None else "")
                + (f" min_opening={g:.3f}" if g is not None else ""))
    if name == "release":
        return f"libero_terminated={r.get('libero_terminated')}"
    return json_phrase(r)


def json_phrase(r: dict) -> str:
    s = str({k: r.get(k) for k in ("success", "libero_terminated",
                                   "final_dist_m", "found", "world_error",
                                   "peak_lift_m", "min_gripper_opening")
             if k in r})
    return s[:160]
