#!/usr/bin/env python3
"""Stage C2 — Progress-Aware Trigger offline benchmark (design frozen in
analysis/memory_stageC2_design.md).

T0 = #49's recorded fires (memory_events.jsonl, verbatim).  T1 = frozen
progress-aware rules replayed per tool result over the official 60 memB2/memB3
episodes.  Ground truth = Stage B SHOULD moments on the SAME denominator
(all 60 episodes, 50 moments) + a deterministic progress_state labeler.

Usage: python scripts/memory_stagec2_benchmark.py
"""
from __future__ import annotations

import collections
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import analyze_memory_stageB as sb  # noqa: E402
from memory_stagec1_benchmark import EpisodeCtx, _grip_open  # noqa: E402

OVPM = REPO / "logs" / "ovpm_exp"
PRIMITIVES = ("pi0_pick", "pi0_doubled", "move_to", "move_pose", "release",
              "set_gripper", "rotate_wrist", "rotate_pitch")

COOLDOWN_TURNS = 2
CAP_PER_EPISODE = 6
MOVE_EPS = 0.005          # 5 mm minimum eef progress toward commanded target
MOVE_ARRIVED = 0.03       # residual at/under which a move counts as arrived
LIFT_OK = 0.05            # m of ascent that counts as a real lift
GRIP_OPEN_DELTA = 0.02    # gripper span increase that counts as release


def official_episodes() -> dict[str, str]:
    out = {}
    for r in sb.csv_dict():
        if r["stage"] == "memB" and r["cond"] in ("memB2", "memB3") \
                and int(r["repeat"]) == 1:
            out[r["dir"].rsplit("/", 1)[-1]] = r["cond"]
    return out


# ------------------------------------------------------- corrected moments
# Erratum (2026-09-18): analyze_memory_stageB.should_retrieve_moments checks
# `_pick_class(name, ...) == "pi0_pick"` but states.json pick results are
# named "pick" — every grasp/pick_verify SHOULD moment was silently missing
# from the Stage B ground truth (37 grasp + 11 pick_verify events in the
# official 60 memB episodes).  This wrapper normalizes the name so the C2
# denominator is correct; the Stage B report gets an erratum note (its task /
# ranking layers are unaffected — T0 fired no pick-rule fires either).
def corrected_moments(ep_dir: Path):
    """should_retrieve_moments with the pick-name fix."""
    out = []
    try:
        states = json.load(open(Path(ep_dir) / "states.json"))
    except (OSError, json.JSONDecodeError):
        states = []
    s2t = sb._step_to_turn(Path(ep_dir) / "run.log")
    steps = sorted(s2t)
    for e in states:
        r = e.get("result") or {}
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except json.JSONDecodeError:
                continue
        name = r.get("name") or (e.get("command") or {}).get("action", "")
        name = {"pick": "pi0_pick", "doubled": "pi0_doubled"}.get(name, name)
        cls = sb._pick_class(name, r)
        if not cls:
            continue
        st = e.get("step_idx")
        if st not in s2t and steps:
            st = min(steps, key=lambda s: abs(s - (st or 0)))
        out.append((s2t.get(st, 0), name, cls))
    for p in sorted((Path(ep_dir) / "segments").glob("segment_*.json")):
        try:
            seg = json.load(open(p))
        except (OSError, json.JSONDecodeError):
            continue
        if seg.get("found") is False:
            m = re.search(r"segment_(\d+)", p.name)
            st = int(m.group(1)) if m else 0
            t = s2t.get(st, min(steps, key=lambda s: abs(s - st)) if steps
                        else 0)
            out.append((t, "segment", "perception"))
    return sorted(out)


def t0_fire_class(reason: str) -> str:
    """T0 fire class with one refinement vs sb._cls_of_event: the T4
    'repeated failed picks' reason is a GRASP signal, not recovery."""
    if reason.startswith("repeated_no_progress") \
            and "failed picks" in reason:
        return "grasp"
    return sb._cls_of_event({"trigger_reason": reason})


# ------------------------------------------------------------------ labeler
def dist(a, b):
    if not a or not b or len(a) < 3 or len(b) < 3:
        return None
    return math.dist(a[:3], b[:3])


def label_stream(ctx: EpisodeCtx):
    """[(step, turn, name, result, label)] — frozen progress_state labeler."""
    entries = []  # (step, turn, name, result, pre_state, post_span)
    states = [e for e in ctx.states if isinstance(e.get("step_idx"), int)]
    by_step = {e["step_idx"]: e for e in states}
    ordered = sorted(states, key=lambda e: e["step_idx"])
    stream = ctx.tool_stream()
    out = []
    # indices for next/prev primitive lookups
    prim_idx = [i for i, t in enumerate(stream) if t[2] in PRIMITIVES]
    for i, (step, turn, name, r, _e) in enumerate(stream):
        if name not in PRIMITIVES and name not in ("segment", "back_project"):
            continue
        entry = by_step.get(step) if isinstance(step, int) else None
        pre_st = (entry or {}).get("state") or {}
        pre_eef = pre_st.get("robot0_eef_pos")
        pre_span = _grip_open(pre_st.get("robot0_gripper_qpos"))
        nxt = next((e for e in ordered if e["step_idx"] > step), None) \
            if isinstance(step, int) else None
        post_span = _grip_open((nxt or {}).get("state", {}).get(
            "robot0_gripper_qpos")) if nxt else None

        label = "AMBIGUOUS"
        diag = r.get("diagnostics") if isinstance(r.get("diagnostics"), dict) \
            else {}
        if name in ("move_to", "move_pose"):
            fd = r.get("final_dist_m")
            tgt = (entry or {}).get("command", {}).get("xyz")
            dpre = dist(pre_eef, tgt) if tgt else None
            if not isinstance(fd, (int, float)):
                label = "AMBIGUOUS"
            elif fd <= MOVE_ARRIVED or (dpre is not None
                                        and dpre - fd > MOVE_EPS):
                label = "PROGRESSING"
            elif dpre is None:
                label = "STALLED"  # no progress evidence (frozen fallback)
            else:
                label = "STALLED"
        elif name == "pi0_pick":
            lift = diag.get("post_min_ascent_m")
            if r.get("success") is True and isinstance(lift, (int, float)):
                label = "PROGRESSING" if lift >= LIFT_OK else "STALLED"
            elif r.get("success") is False:
                nxt_prim = next((j for j in prim_idx if j > i), None)
                nxt_fail = False
                if nxt_prim is not None:
                    nr = stream[nxt_prim][3]
                    nxt_fail = nr.get("name") == "pi0_pick" \
                        and nr.get("success") is False
                label = "STALLED" if nxt_fail else "AMBIGUOUS"
            else:
                label = "AMBIGUOUS"
        elif name == "release":
            if r.get("libero_terminated") is True:
                label = "PROGRESSING"
            elif isinstance(pre_span, float) and isinstance(post_span, float):
                label = "PROGRESSING" if post_span - pre_span > GRIP_OPEN_DELTA \
                    else "STALLED"
            else:
                label = "AMBIGUOUS"
        elif name == "pi0_doubled":
            if r.get("success") is True or r.get("libero_terminated") is True:
                label = "PROGRESSING"
            else:
                prev = next((j for j in prim_idx if j < i), None)
                prev_fail = prev is not None and (
                    stream[prev][3].get("success") is False)
                label = "STALLED" if prev_fail else "AMBIGUOUS"
        elif name in ("segment", "back_project"):
            if r.get("found") is True:
                label = "PROGRESSING"
            elif r.get("found") is False or r.get("world_error"):
                label = "STALLED"
        out.append((step, turn, name, r, label))
    return out


# ------------------------------------------------------------------- T1
def t1_fires(ctx: EpisodeCtx):
    """Frozen progress-aware rules, per tool result.  [(turn, cls, note)]"""
    labeled = label_stream(ctx)
    fires = []
    last_fire_turn = -10
    consecutive_pick_fails = 0
    prev_prim_failed = False
    for step, turn, name, r, _label in labeled:
        if name == "pi0_pick":
            consecutive_pick_fails = consecutive_pick_fails + 1 \
                if r.get("success") is False else 0
        fire = None
        diag = r.get("diagnostics") if isinstance(r.get("diagnostics"), dict) \
            else {}
        if name in ("segment", "back_project") \
                and (r.get("found") is False or r.get("world_error")):
            fire = ("perception", "R1 no usable observation")
        elif name in ("move_to", "move_pose"):
            fd = r.get("final_dist_m")
            if isinstance(fd, (int, float)) and fd > MOVE_ARRIVED:
                entry = next((e for e in ctx.states
                              if isinstance(e.get("step_idx"), int)
                              and e["step_idx"] == step), None)
                tgt = (entry or {}).get("command", {}).get("xyz")
                pre_st = (entry or {}).get("state") or {}
                dpre = dist(pre_st.get("robot0_eef_pos"), tgt) if tgt else None
                if dpre is None or dpre - fd <= MOVE_EPS:
                    fire = ("recovery_transport",
                            f"R2 residual {fd:.3f} no progress")
        elif name == "pi0_pick":
            lift = diag.get("post_min_ascent_m")
            if r.get("success") is True and isinstance(lift, (int, float)) \
                    and lift < LIFT_OK:
                fire = ("pick_verify", "R3 reported lift missing physically")
            elif r.get("success") is False and consecutive_pick_fails >= 2:
                fire = ("grasp", "R3 2nd+ consecutive failed pick")
        elif name == "pi0_doubled" and r.get("success") is False \
                and r.get("libero_terminated") is not True:
            if prev_prim_failed:
                fire = ("recovery_doubled", "R4 recovery changed nothing")
        elif name == "release" and r.get("libero_terminated") is not True:
            fire = ("predicate_open", "R5 expected predicate progress missing")
        # infra: cooldown / cap (first-primitive gate trivially satisfied —
        # fires only happen on primitive/perception results)
        if fire and (turn - last_fire_turn) >= COOLDOWN_TURNS \
                and len(fires) < CAP_PER_EPISODE:
            fires.append((turn, fire[0], fire[1], name))
            last_fire_turn = turn
        if name in PRIMITIVES:
            prev_prim_failed = r.get("success") is False or (
                name in ("move_to", "move_pose")
                and isinstance(r.get("final_dist_m"), (int, float))
                and r["final_dist_m"] > MOVE_ARRIVED)
    return fires, labeled


# ---------------------------------------------------------------- metrics
def trigger_metrics(fires_by_ep, moments_by_ep):
    tot_mom = covered = 0
    tot_fire = aligned = 0
    for ep, mom in moments_by_ep.items():
        fires = fires_by_ep.get(ep, [])
        tot_fire += len(fires)
        for t, _a, c in mom:
            tot_mom += 1
            covered += any(0 <= ft - t <= 3 and sb._same_family(fc, c)
                           for ft, fc, *_ in fires)
        for ft, fc, *_ in fires:
            aligned += sb._aligns(ft, fc, mom)
    prec = aligned / tot_fire if tot_fire else None
    rec = covered / tot_mom if tot_mom else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
    return {"moments": tot_mom, "covered": covered,
            "recall": round(rec, 3) if rec is not None else None,
            "fires": tot_fire, "aligned": aligned,
            "precision": round(prec, 3) if prec is not None else None,
            "F1": round(f1, 3) if f1 is not None else None}


def main():
    official = official_episodes()
    print(f"official episodes: {len(official)}")

    # T0 = recorded #49 fires
    events = sb.load_events()
    t0_by_ep = {}
    for ep, evs in events.items():
        if ep in official:
            t0_by_ep[ep] = [(e["turn"], t0_fire_class(e.get("trigger_reason",
                                                            "")),
                             e.get("trigger_reason", "")) for e in evs]

    moments, t1_by_ep, labels_by_ep = {}, {}, {}
    mom_cls = collections.Counter()
    for ep in official:
        ctx = EpisodeCtx(ep)
        moments[ep] = corrected_moments(OVPM / ep)
        for _t, _a, c in moments[ep]:
            mom_cls[c] += 1
        fires, labeled = t1_fires(ctx)
        t1_by_ep[ep] = fires
        labels_by_ep[ep] = labeled
    print("corrected moments by class:", dict(mom_cls),
          "total", sum(mom_cls.values()))

    t0m = trigger_metrics(t0_by_ep, moments)
    t1m = trigger_metrics(t1_by_ep, moments)
    print("T0:", json.dumps(t0m))
    print("T1:", json.dumps(t1m))

    # fires/episode + zero-fire episodes
    for tag, fb in (("T0", t0_by_ep), ("T1", t1_by_ep)):
        counts = [len(fb.get(ep, [])) for ep in official]
        print(f"{tag}: fires/ep={sum(counts)/len(counts):.2f} "
              f"zero-fire eps={sum(1 for c in counts if not c)}")

    # T0 unnecessary fires under the CORRECTED GT: eliminated by T1?
    t0_unnec = [(ep, e["turn"], t0_fire_class(e.get("trigger_reason", "")))
                for ep, evs in events.items() if ep in official
                for e in evs
                if not sb._aligns(e["turn"], t0_fire_class(
                    e.get("trigger_reason", "")), moments[ep])]
    print(f"T0 unnecessary fires (corrected GT): {len(t0_unnec)}")
    elim = same_cls_elim = 0
    for ep, turn, cls in t0_unnec:
        t1 = t1_by_ep.get(ep, [])
        if not any(abs(ft - turn) <= 1 for ft, _c, _n, _a in t1):
            elim += 1
        if not any(abs(ft - turn) <= 1 and sb._same_family(fc, cls)
                   for ft, fc, _n, _a in t1):
            same_cls_elim += 1
    print(f"T0 unnecessary fires: {len(t0_unnec)}; eliminated by T1 "
          f"(any-class): {elim}, (same-class): {same_cls_elim}")

    # progress-label layer
    lab_all = collections.Counter()
    fires_on = collections.Counter()
    for ep, labeled in labels_by_ep.items():
        lab_lookup = {}
        for step, turn, name, r, lab in labeled:
            lab_lookup[(turn, name)] = lab
            lab_all[lab] += 1
        for ft, fc, note, fname in t1_by_ep.get(ep, []):
            lab = lab_lookup.get((ft, fname))
            fires_on[lab or "nolabel"] += 1
        for ft, fc, reason in t0_by_ep.get(ep, []):
            pass
    n = sum(lab_all.values())
    print("label distribution:", dict(lab_all),
          {k: round(v / n, 3) for k, v in lab_all.items()})
    print("T1 fires by label of firing event:", dict(fires_on))

    # T0 T4 waypoint false alarms: T4 fires whose preceding move chain was
    # PROGRESSING
    t4_total = t4_waypoint = 0
    for ep, evs in events.items():
        if ep not in official:
            continue
        lab = labels_by_ep[ep]
        moves_lab = [(turn, l) for _s, turn, nm, _r, l in lab
                     if nm in ("move_to", "move_pose")]
        for e in evs:
            if not (e.get("trigger_reason") or "").startswith(
                    "repeated_no_progress"):
                continue
            t4_total += 1
            prior = [l for t, l in moves_lab if e["turn"] - 2 <= t <= e["turn"]]
            if prior and all(p == "PROGRESSING" for p in prior):
                t4_waypoint += 1
    print(f"T0 T4 fires: {t4_total}, on all-PROGRESSING move chains "
          f"(waypoint false alarms): {t4_waypoint}")

    # STALLED detection by T1 (label-space recall)
    stalled_tot = stalled_fired = 0
    for ep, labeled in labels_by_ep.items():
        fires = t1_by_ep.get(ep, [])
        for step, turn, name, r, lab in labeled:
            if lab != "STALLED":
                continue
            stalled_tot += 1
            stalled_fired += any(ft == turn for ft, _c, _n, fn in fires
                                 if fn == name)
    print(f"STALLED events: {stalled_tot}, T1 fired on the event itself: "
          f"{stalled_fired}")

    # pre-registered gate
    gate_prec = t1m["precision"] is not None and t1m["precision"] >= 0.50
    drop = (t0m["recall"] - t1m["recall"]) if t0m["recall"] and t1m["recall"] \
        else None
    gate_rec = drop is not None and drop <= 0.10
    print(f"GATE: T1 precision {t1m['precision']} (>=0.50: {gate_prec}); "
          f"recall drop {round(drop, 3) if drop is not None else None} "
          f"(<=0.10: {gate_rec}) -> "
          f"{'PASS' if gate_prec and gate_rec else 'FAIL'}")

    out = REPO / "analysis" / "memory_stageC2_results.json"
    json.dump({"T0": t0m, "T1": t1m,
               "t0_unnecessary": len(t0_unnec), "eliminated_any": elim,
               "eliminated_same_cls": same_cls_elim,
               "labels": dict(lab_all), "t1_fires_by_label": dict(fires_on),
               "t4_total": t4_total, "t4_waypoint_false_alarm": t4_waypoint,
               "stalled_events": stalled_tot, "stalled_fired": stalled_fired,
               "gate": {"precision_ok": gate_prec, "recall_drop": drop,
                        "recall_ok": gate_rec,
                        "pass": bool(gate_prec and gate_rec)}},
              open(out, "w"), indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
