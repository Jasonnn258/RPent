#!/usr/bin/env python3
"""Stage A-1 — build memory-retrieval decision points with dual labels.

Extracts decision points from B2 verification events (physical state + verdict
context), labels each with SHOULD_RETRIEVE (YES/NO/UNCERTAIN) and, for YES,
gold memory card ids. Gold is assigned by a curated class->cards mapping plus
state/evidence audit rules (four checks per positive); the same-episode
forward physical outcome is used as LABELING evidence only (never an online
feature). See analysis/memory_stageA_design.md for the amended spec.

Output: analysis/memory_retrieval_queries.jsonl (+ printed quota summary).
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GLOBAL_DIR = REPO / "resources" / "libero" / "global"
EVENTS = REPO / "analysis" / "b2_verification_events.jsonl"
RUNS = REPO / "analysis" / "b2_runs.csv"
OVPM = REPO / "logs" / "ovpm_exp"
OUT = REPO / "analysis" / "memory_retrieval_queries.jsonl"

# ----------------------------------------------------------- card mapping
# Curated class -> candidate card ids (semantic curation, NOT string match).
# Audit rules below then check applies_when consistency / falsify per point.
MAP = {
    "predicate_timing": {
        "core": [
            "predicate-fires-after-gripper-retreat",
            "predicate-gated-by-eef-proximity-retreat-clear",
            "open-retreat-settles-container",
            "libero-in-predicate-fires-while-grasped",
        ],
        "container": {  # extra cards when the PLACE TARGET is that container.
            # NOTE: no "bowl" key — in armB2 spatial_task the bowl is the HELD
            # object (place target is a plate), so flat-box-rigid-bowl-seat
            # (seat a flat object into/on a bowl) never applies here.
            "basket": ["basket-release-retreat-settle",
                       "basket-insertion-open-retreat"],
            "drawer": ["drawer-top-contact-before-release"],
        },
    },
    "pick_verify": {
        "core": [
            "can-pick-visual-confirmation",
            "pi0-pick-carries-past-lift-judge-by-grip",
        ],
    },
    "grasp": {
        "core": ["avoid-full-task-prompt-after-miss", "near-target-repick"],
        "object": {  # object-conditioned cards gated on task language
            "moka": ["moka-pot-grasp-the-handle-not-the-body"],
            "bowl": ["open-side-bowl-grasp"],
            "mug": ["pi0-grasp-tall-mug-by-handle"],
            "can": ["sam3-brand-noun-can-collision"],
        },
    },
    "recovery": {
        "core": ["near-miss-corrective-pick", "low-pose-settle-regrasp",
                 "learned-contact-after-near-placement"],
        "transport_stall": ["co-vary-pitch-clears-yawed-reach-wall"],
        "doubled_fail": ["visual-over-pick-heuristic",
                         "near-miss-corrective-pick"],
    },
    "perception": {
        "core": ["point-prompt-after-text-misground"],
        "brand": ["brand-label-over-segmentation"],
        "ambig": ["box-vs-can-lid-wrist-disambiguation"],
    },
}
# Cards that a hard negative must NOT be ranked for.
RETREAT_CARDS = ["predicate-fires-after-gripper-retreat",
                 "predicate-gated-by-eef-proximity-retreat-clear",
                 "open-retreat-settles-container", "basket-release-retreat-settle",
                 "basket-insertion-open-retreat"]

# Quotas calibrated to actual pool sizes (2026-09-17 tally of action x verdict):
# grasp = all 7 pi0_pick CONFIRMED_FAILURE; hard_negative = all 14
# release-UNCERTAIN-with-forward-failure; no_card_mechanical = all 2
# release-FAILURE. YES total = 30+35+7+30+18 = 120; NO total = 84+20+14+2 = 120.
YES_QUOTA = {"predicate_timing": 30, "pick_verify": 36, "grasp": 7,
             "recovery": 30, "perception": 17}
NO_QUOTA = {"routine_success": 84, "terminal_release": 20,
            "hard_negative": 14, "no_card_mechanical": 2}
MAX_PER_EPISODE = 3


def load_cards() -> dict:
    cards = {}
    for f in sorted(GLOBAL_DIR.glob("*.md")):
        t = f.read_text()
        m = re.search(r"^---\n(.*?)\n---", t, re.S)
        fm = m.group(1) if m else ""
        g = lambda k: (re.search(rf"^{k}:\s*(.+)$", fm, re.M) or [None, ""])[1].strip()
        cards[f.stem] = {
            "id": f.stem,
            "title": g("title"),
            "kind": g("kind"),
            "applies_when": g("applies_when"),
            "symptom": g("symptom"),
            "cells": re.findall(r"- (\S+)", fm.split("evidence:")[1])
            if "evidence:" in fm else [],
            "how_to": (re.search(r"\*\*How to apply:\*\*(.*?)(?:\*\*Falsify:|\Z)",
                                 t, re.S) or ["", ""])[1].strip()[:300],
            "falsify": (re.search(r"\*\*Falsify:\*\*(.*?)(?:\*\*Related:|\Z)",
                                  t, re.S) or ["", ""])[1].strip()[:300],
        }
    return cards


def load_outcomes() -> dict:
    """Key by episode dir basename — the CSV `dir` column is authoritative."""
    out = {}
    for i, line in enumerate(open(RUNS)):
        if i == 0 or not line.strip():
            continue
        v = line.rstrip("\n").split(",")
        out[Path(v[30]).name] = v[5].strip() in ("1", "True")
    return out


_TASK_LANG = {}


def task_language(episode: str) -> str:
    if episode not in _TASK_LANG:
        try:
            s = json.load(open(OVPM / episode / "states.json"))
            s = s[0] if isinstance(s, list) else s
            _TASK_LANG[episode] = str(s.get("task_language", ""))
        except Exception:
            _TASK_LANG[episode] = ""
    return _TASK_LANG[episode]


def observation_summary(e, tl):
    ps = e["pre_state_summary"]
    eef = [round(x, 2) for x in (ps.get("eef") or [])]
    tgt = [round(x, 2) for x in (ps.get("last_transport_target") or [])]
    parts = [
        f"phase={e['phase']}; last action={e['action']}",
        f"observed: {e['observed_change']}",
        f"eef={eef} gripper_opening={round(ps.get('gripper_opening') or 0, 3)}",
        f"last_transport_target={tgt}",
        f"missing evidence: {e.get('missing_evidence') or []}",
        f"task: {tl[:110]}",
    ]
    return " | ".join(parts)


def classify(e, later, ep_success, tl):
    """Return (class, tags) or (None, {}) if the event is not a candidate.
    `later` = the events after this one in the same episode (labeling only)."""
    act, ver = e["action"], e["verdict"]
    forward_fail = any(x["verdict"] == "CONFIRMED_FAILURE" for x in later[:6])
    txt = " ".join(map(str, [e.get("missing_evidence"),
                             e.get("evidence_for_failure"),
                             e.get("observed_change")])).lower()
    percept_unclear = ver == "UNCERTAIN" and "no usable object position" in txt
    percept_tags = ({"brand": True} if ("brand" in tl.lower()
                    or re.search(r"\bcan\b", tl.lower())) else {})
    if act == "release" and ver == "UNCERTAIN":
        # Final episode outcome is the labeling authority (allowed as label
        # evidence, never an online feature): success == object ended at the
        # target -> retreat-and-recheck cards APPLY (case A); failure -> the
        # object never reached the target, retreat-only cards' Falsify holds
        # (case B hard negative). A transient forward CONFIRMED_FAILURE that
        # the episode later recovers from does NOT make a hard negative.
        if ep_success is False:
            return "hard_negative", {"forward_fail": forward_fail}
        if ep_success is True:
            return "predicate_timing", {}
        return None, {}  # outcome unknown -> UNCERTAIN bucket via caller
    if percept_unclear:
        return "perception", percept_tags
    if act == "pi0_pick" and ver == "UNCERTAIN":
        return "pick_verify", {}
    if act == "pi0_pick" and ver == "CONFIRMED_FAILURE":
        return "grasp", {}
    if ver == "CONFIRMED_FAILURE":
        if act == "release":
            return "no_card_mechanical", {"reason": "gripper did not open — "
                                                    "no card covers actuation"}
        if act in ("move_to", "move_pose") and "short" in e["observed_change"]:
            return "recovery", {"transport_stall": True}
        if act == "pi0_doubled":
            return "recovery", {"doubled_fail": True}
        return "recovery", {}
    return None, {}


def gold_for(cls, tags, tl, cards):
    spec = MAP[cls]
    ids = list(spec["core"])
    for key, extra in spec.get("container", {}).items():
        if key in tl.lower():
            ids += extra
    for key, extra in spec.get("object", {}).items():
        if key in tl.lower():
            ids += extra
    if tags.get("transport_stall"):
        ids += MAP["recovery"]["transport_stall"]
    if tags.get("doubled_fail"):
        ids += MAP["recovery"]["doubled_fail"]
    if tags.get("brand"):
        ids += MAP["perception"]["brand"]
    out, why = [], []
    for i in dict.fromkeys(ids):
        c = cards.get(i)
        if not c:
            continue
        out.append(i)
        why.append(f"{i}: applies_when='{c['applies_when'][:60]}' matches "
                   f"{cls} state; falsify not indicated by evidence")
    return out, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=17)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    cards = load_cards()
    outcomes = load_outcomes()

    eps = defaultdict(list)
    for line in open(EVENTS):
        e = json.loads(line)
        eps[e["episode"]].append(e)
    for v in eps.values():
        v.sort(key=lambda x: x["turn"])

    pools = defaultdict(list)
    uncertain = []
    ep_yes = Counter()
    for ep, evs in eps.items():
        succ = outcomes.get(ep)
        tl = task_language(ep)
        for i, e in enumerate(evs):
            cls, tags = classify(e, evs[i + 1:], succ, tl)
            if cls is None:
                if e["verdict"] == "UNCERTAIN":
                    uncertain.append((ep, e, tl, "relevance ambiguous"))
                continue
            pools[cls].append((ep, e, tl, tags, succ))

    def row(ep, e, tl, sr, gold, why_r, why_a, use, cls, hn=None, fwd=None):
        m = re.search(r"_t(\d+)_s(\d+)_r(\d+)$", ep)
        suite_var = re.search(r"_libero_(\w+?)_t\d+_s\d+_r\d+$", ep)
        sv = suite_var.group(1) if suite_var else ""
        cell = f"{sv}_t{m.group(1)}_s0" if (m and sv) else ""
        return {
            "episode": ep, "task": m.group(1) if m else "?",
            "seed": m.group(2) if m else "?", "turn": e["turn"],
            "phase": e["phase"], "last_action": e["action"],
            "symptom": f"{cls}" + ("|" + e["observed_change"][:60] if cls else ""),
            "observation_summary": observation_summary(e, tl),
            "should_retrieve": sr,
            "gold_memory_ids": gold,
            "why_retrieve": why_r, "why_applicable": "; ".join(why_a),
            "expected_use": use, "source_type": "b2_verification_event",
            "is_source_episode": bool(gold and cell and cell in
                                      cards[gold[0]]["cells"]) if gold else False,
            "class": cls, "hard_negative_for": hn or [],
            "forward_outcome": fwd,
            "auto_audit": ["card_preexists:library_static",
                           "applies_when_checked:rule_mapping",
                           "how_to_actionable:phase_match",
                           "falsify_checked:forward_evidence"],
            "audited": True,
        }

    rows, quotas = [], Counter()
    # ---- YES classes
    use_of = {"predicate_timing": "RETREAT", "pick_verify": "OBSERVE",
              "grasp": "RETRY", "recovery": "RECOVER", "perception": "OBSERVE"}
    for cls, quota in YES_QUOTA.items():
        pool = [p for p in pools[cls] if p[0] not in ep_yes
                or ep_yes[p[0]] < MAX_PER_EPISODE]
        rng.shuffle(pool)
        for ep, e, tl, tags, succ in pool:
            if quotas[cls] >= quota:
                break
            if ep_yes[ep] >= MAX_PER_EPISODE:
                continue
            gold, why = gold_for(cls, tags, tl, cards)
            if not gold:
                continue
            ep_yes[ep] += 1
            quotas[cls] += 1
            rows.append(row(ep, e, tl, "YES", gold, why,
                            [f"{cls} state at turn {e['turn']}: "
                             f"{e['observed_change']}"],
                            use_of[cls], cls, fwd=str(succ)))
    # ---- NO classes
    # routine-success pool straight from events (CONFIRMED_SUCCESS, non-release)
    routine = []
    for ep, evs in eps.items():
        tl = task_language(ep)
        for e in evs:
            if e["verdict"] == "CONFIRMED_SUCCESS" and e["action"] != "release":
                routine.append((ep, e, tl))
    rng.shuffle(routine)
    strat = defaultdict(int)
    for ep, e, tl in routine:
        if quotas["routine_success"] >= NO_QUOTA["routine_success"]:
            break
        if ep_yes[ep] >= MAX_PER_EPISODE:
            continue
        m = re.search(r"_t(\d+)_s\d+_r\d+$", ep)
        k = (e["action"], e["phase"], m.group(1) if m else "?")
        if strat[k] >= 4:
            continue
        strat[k] += 1
        quotas["routine_success"] += 1
        rows.append(row(ep, e, tl, "NO", [],
                        "action confirmed successful; phase progressing "
                        "normally; no memory applies", [], "CONTINUE",
                        "routine_success"))
    # terminal releases (CONFIRMED_SUCCESS on release)
    term = [(ep, e, tl) for ep, evs in eps.items() for e in evs
            if e["action"] == "release" and e["verdict"] == "CONFIRMED_SUCCESS"
            for tl in [task_language(ep)]]
    rng.shuffle(term)
    for ep, e, tl in term:
        if quotas["terminal_release"] >= NO_QUOTA["terminal_release"]:
            break
        quotas["terminal_release"] += 1
        rows.append(row(ep, e, tl, "NO", [],
                        "release verified successful — relation confirmed; "
                        "no re-check needed", [], "CONTINUE", "terminal_release"))
    # hard negatives: release UNCERTAIN but episode ultimately failed =>
    # object never reached the target => retreat-only cards NOT applicable
    for ep, e, tl, tags, succ in pools.get("hard_negative", []):
        if quotas["hard_negative"] >= NO_QUOTA["hard_negative"]:
            break
        quotas["hard_negative"] += 1
        rows.append(row(ep, e, tl, "NO", [],
                        "surface keywords match (release + predicate unproven) "
                        "but the episode's final outcome is failure — object "
                        "did not end at the target, so retreat-only cards' "
                        "Falsify holds"
                        + (" (forward failure corroborates)" if tags.get(
                            "forward_fail") else ""),
                        [], "RECOVER", "hard_negative", hn=RETREAT_CARDS,
                        fwd="episode_failed"))
    # mechanical failures with no card
    for ep, e, tl, tags, succ in pools.get("no_card_mechanical", []):
        if quotas["no_card_mechanical"] >= NO_QUOTA["no_card_mechanical"]:
            break
        quotas["no_card_mechanical"] += 1
        rows.append(row(ep, e, tl, "NO", [],
                        "gripper-actuation failure — library has no "
                        "applicable card", [], "RECOVER", "no_card_mechanical"))
    # UNCERTAIN bucket, saved separately inside the same file with its label
    for ep, e, tl, why in uncertain[:40]:
        rows.append(row(ep, e, tl, "UNCERTAIN", [], why, [], "OTHER",
                        "ambiguous"))

    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lab = Counter(r["should_retrieve"] for r in rows)
    print("wrote", OUT, "rows:", len(rows), dict(lab))
    print("YES by class:", dict(Counter(r["class"] for r in rows
                                        if r["should_retrieve"] == "YES")))
    print("NO by class:", dict(Counter(r["class"] for r in rows
                                       if r["should_retrieve"] == "NO")))
    print("UNCERTAIN saved:", lab.get("UNCERTAIN", 0))


if __name__ == "__main__":
    main()
