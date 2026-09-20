#!/usr/bin/env python3
"""Stage F — build typed Activation Signatures for the 61 Global Memory cards.

Hypothesis H-F: provenance is observable but not lexically addressable; give
each card a machine-addressable activation signature (failure_origin /
missing_prerequisites / failure_surface / phase / action_family) INDEPENDENT
of its body text.

Sources (card-own material ONLY — title/kind/applies_when/symptom/Why/
How_to_apply/Falsify/evidence.cells -> task_only records -> recipes):

  ACTIVATION channel = title + applies_when + symptom bullets
    (frontmatter fields that literally say WHEN the card should fire)
  REMEDY channel    = How-to-apply / Why body paragraphs (remedy_family only)

LEAKAGE FIREWALL: reads only resources/libero/{global,task_only}. Must not
open any Stage A/C1/C3/D/E query, gold, or ranking artifact. Enforced by
construction: the only paths opened live under RES/.

Canonical prerequisite IDs are the FROZEN Stage F ontology
(analysis/stageF_prerequisite_ontology.md):
  PREREQ_1 perception output unusable          (family PERCEPTION)
  PREREQ_2 object displacement evidence absent (family GRASP)
  PREREQ_3 displacement evidence ambiguous     (family GRASP)
  PREREQ_4 final relation / settling unconfirmed (family PLACE)
  PREREQ_5 directed observation never ran      (process, cross-cutting)

Empty field = genuinely unspecified (not forced). Output:
analysis/memory_activation_signatures_v1.json

Usage: python scripts/build_activation_signatures.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RES = REPO / "resources" / "libero"
GLOBAL = RES / "global"
TASK_ONLY = RES / "task_only"
OUT = REPO / "analysis" / "memory_activation_signatures_v1.json"

# ---------------------------------------------------------- frozen vocabularies
# Locus = where the activating PROBLEM sits (failure condition), distinct from
# the mechanism that remedies it. Matched on the ACTIVATION channel only.
LOCUS = {
    "PERCEPTION": [
        "wrong-mask", "wrong instance", "wrong object", "wrong can",
        "wrong duplicate", "wrong target", "wrong surface", "wrong side",
        "misground", "low-score-segment", "sam3", "text segmentation",
        "segment prompt", "brand noun", "same box for different prompts",
        "duplicate", "look-alike", "visually identical", "disambiguation",
        "disambiguate", "back_project returns", "back_project captured",
        "back_project", "stale coordinates", "wrist views",
        "segmentation outlier", "cannot see", "cannot tell", "occluded",
        "which compartment", "which pocket", "ambiguous compartment",
        "choose +y", "semantic identity", "relation target", "region/pixel",
        "reads as", "segment the wrong", "selects the wrong",
    ],
    "GRASP": [
        "missed grasp", "pick miss", "never closes", "will not close",
        "not fully closed", "contacts without lifting", "but no lift",
        "no lift", "no-lift", "grabbed air", "grabbing air", "grabbed nothing",
        "success false", "success:false", "success_flag", "pick_false",
        "false negative", "grasp slips", "close slips", "slips off",
        "ungrasped", "contact-only", "gripper stays open", "gripper reopens",
        "descent stalls", "over the shoulder", "partially engages",
        "judge-by-grip", "visibly moved or held", "grasps stall",
        "closure fails", "grasp never",
    ],
    "TRANSPORT": [
        "carry stalls", "carry slip", "carry-past-lift", "reach wall",
        "osc stall", "eef moved sideways", "eef moved far", "eef jumped",
        "moved the eef", "drifts", "drifted", "drift", "horizontal carry",
        "long carry", "swing", "hangs beyond", "unreachable eef",
    ],
    "PLACE": [
        "release false", "release_false", "release-false", "release not",
        "release opens the gripper", "release did not", "unreleased",
        "nonterminal", "not firing", "did not fire", "never fires",
        "wont fire", "wont terminate", "predicate", "terminated",
        "termination", "perched", "rim catch", "rim-perched", "wedged",
        "settle", "settles", "settling", "seat", "seated", "tipped",
        "falls back", "rolls out", "rolls away", "lands outside",
        "lands in the wrong", "dropped into the wrong", "displaced",
        "stalls high", "cannot-descend", "rogue place", "placement misses",
        "miss the", "shoved", "snagged", "back into", "falls off",
        "re-hooks", "extracts it", "look correct but", "fail despite",
    ],
    "PREDICATE": [
        "predicate", "terminated", "termination", "nonterminal",
        "not firing", "did not fire", "never fires", "wont fire",
        "wont terminate", "success flag",
    ],
    "RECOVERY": [
        "repick", "regrasp", "re-approach", "retry", "corrective",
        "near miss", "near-miss", "near_miss", "after miss", "spatially qualified",
    ],
}
# Surface vocabulary: where the phenomenon EXPOSES (adds PREDICATE timing).
SURFACE_EXTRA = {
    "PREDICATE": ["predicate", "terminated", "termination", "success flag",
                  "eef proximity"],
}
# Prerequisite vocabularies (what unmet prerequisite the card addresses).
PREREQ = {
    "PREREQ_1": LOCUS["PERCEPTION"],
    "PREREQ_2": LOCUS["GRASP"],
    "PREREQ_3": [],            # address-side never distinguishes 2 vs 3
    "PREREQ_4": LOCUS["PLACE"] + LOCUS["PREDICATE"],
    "PREREQ_5": ["verify", "confirm", "observe", "visual check",
                 "before acting", "before release", "check before"],
}
# Remedy channel -> remedy_family.
REMEDY = {
    "PERCEPTION": ["point prompt", "point-prompt", "segment", "mask",
                   "agentview", "inspect", "observe", "look", "visual"],
    "GRASP": ["regrip", "firm the grip", "close", "grip"],
    "TRANSPORT": ["yaw", "pitch", "rotate", "recenter", "offset", "move",
                  "translate", "retreat high"],
    "PLACE": ["release", "settle", "seat", "contact", "descend", "drop",
              "retreat", "insert", "perch"],
    "RECOVERY": ["repick", "regrasp", "retry", "retreat", "corrective",
                 "re-approach", "back off"],
    "PREDICATE": ["wait", "predicate"],
}
PHASE_OF = {"PERCEPTION": [], "GRASP": ["P_grasp"], "TRANSPORT": ["P_transport"],
            "PLACE": ["P_place", "P_verify"], "PREDICATE": ["P_verify"],
            "RECOVERY": []}
ACTION_OF = {
    "pick": ["pi0_pick", "pi0_doubled"], "grasp": ["pi0_pick"],
    "release": ["release"], "settle": ["release"], "retreat": ["release"],
    "segment": ["segment"], "prompt": ["segment", "back_project"],
    "mask": ["segment"], "back_project": ["back_project"],
    "rotate": ["rotate_wrist"], "yaw": ["rotate_wrist"],
    "move": ["move_to", "move_pose"], "carry": ["move_pose"],
    "transport": ["move_pose"], "repick": ["pi0_pick"],
    "regrasp": ["pi0_pick"], "grip": ["set_gripper"],
}
EXCERPT_MAX = 110


def excerpt(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:EXCERPT_MAX] + ("…" if len(s) > EXCERPT_MAX else "")


def parse_card(path: Path) -> dict:
    """Frontmatter (id/kind/title/applies_when multi-line/symptom/cells) +
    body Why/How-to-apply/Falsify paragraphs."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    fm, body = text.split("---", 2)[1], text.split("---", 2)[2]
    lines = fm.splitlines()
    card = {"id": path.stem, "symptom": [], "cells": [], "applies_when": ""}
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(id|kind|title|applies_when):\s*(.*)$", ln)
        if m and m.group(1) == "applies_when":
            val = [m.group(2).strip()]
            i += 1
            while i < len(lines) and lines[i].startswith(("  ", "\t")):
                val.append(lines[i].strip())
                i += 1
            card["applies_when"] = " ".join(v for v in val if v)
            continue
        if m:
            card[m.group(1)] = m.group(2).strip().strip('"')
        elif ln.startswith("symptom:"):
            i += 1
            while i < len(lines) and re.match(r"^\s*- ", lines[i]):
                card["symptom"].append(lines[i].strip()[2:].strip())
                i += 1
            continue
        elif ln.strip() == "cells:":
            i += 1
            while i < len(lines) and re.match(r"^\s*- ", lines[i]):
                v = lines[i].strip()[2:].strip()
                if re.match(r"^[a-z0-9]+_[a-z]+_t\d+_s\d+$", v):
                    card["cells"].append(v)
                i += 1
            continue
        i += 1
    card.setdefault("kind", "")
    for tag, key in (("**Why:**", "why"), ("**How to apply:**", "how"),
                     ("**Falsify:**", "falsify")):
        idx = body.find(tag)
        if idx >= 0:
            end = min((p for p in (body.find(t, idx + len(tag))
                                   for t in ("**Why:**", "**How to apply:**",
                                             "**Falsify:**", "**Related:**"))
                       if p > 0), default=len(body))
            card[key] = body[idx + len(tag):end].strip()
    return card


def hits(text: str, vocab: list[str]) -> list[str]:
    t = text.lower()
    return [w for w in vocab if w in t]


def recipe_actions(cells: list[str]) -> list[str]:
    """Primitive families actually present in the card's own recipe logs."""
    acts = set()
    for cell in cells:
        p = TASK_ONLY / f"{cell}_recipe.jsonl"
        if not p.exists():
            continue
        try:
            for ln in p.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                m = re.search(r'"action":\s*"(\w+)"', ln)
                if m:
                    acts.add(m.group(1))
        except OSError:
            pass
    return sorted(acts)


def signature(card: dict) -> dict:
    act = " | ".join([card.get("title", ""), card.get("applies_when", "")]
                     + card.get("symptom", []))
    how = card.get("how", "") + " " + card.get("why", "")

    ev: list[dict] = []
    origins, prereqs, surfaces = [], [], []

    for fam, vocab in LOCUS.items():
        if fam == "PREDICATE":
            continue   # predicate anchors also live in PLACE; surface-only
        h = hits(act, vocab)
        if h:
            origins.append(fam)
            ev.append({"field": "activation", "match": sorted(set(h))[:4],
                       "excerpt": excerpt(act)})
    for fam, vocab in SURFACE_EXTRA.items():
        h = hits(act, vocab)
        if h and fam not in origins:
            surfaces.append(fam)
            ev.append({"field": "activation(surface)", "match": sorted(set(h)),
                       "excerpt": excerpt(act)})
    surfaces = sorted(set(surfaces) | (set(origins) - {"RECOVERY"}))

    if "PERCEPTION" in origins:
        prereqs.append("PREREQ_1")
    if "GRASP" in origins or "TRANSPORT" in origins:
        # displacement-evidence group (PREREQ_2 <-> PREREQ_3 interchangeable
        # per ontology §2): a drifted/stalled carry is exactly the moment
        # "does the object move with the gripper" becomes the open question.
        prereqs.append("PREREQ_2")
    if "PLACE" in origins or "PREDICATE" in origins:
        prereqs.append("PREREQ_4")
    if hits(act, PREREQ["PREREQ_5"]) and hits(act, ["before", "not yet",
                                                    "never"]):
        prereqs.append("PREREQ_5")
        ev.append({"field": "activation(verify-discipline)",
                   "match": "verify/confirm + before/not-yet", "excerpt":
                   excerpt(act)})

    remedies = sorted({fam for fam, vocab in REMEDY.items() if hits(how, vocab)})

    phases = sorted({ph for fam in origins + surfaces
                     for ph in PHASE_OF.get(fam, [])})
    acts = set(recipe_actions(card.get("cells", [])))
    for w, prims in ACTION_OF.items():
        if w in act.lower() or w in how.lower():
            acts.update(prims)

    return {
        "memory_id": card["id"],
        "kind": card.get("kind", ""),
        "failure_origin": sorted(set(origins)),
        "missing_prerequisites": sorted(set(prereqs)),
        "failure_surface": surfaces,
        "phase": phases,
        "action_family": sorted(acts),
        "remedy_family": remedies,
        "source_cells": card.get("cells", []),
        "annotation_evidence": ev,
    }


def main() -> None:
    cards = []
    for p in sorted(GLOBAL.glob("*.md")):
        c = parse_card(p)
        if c.get("id"):
            cards.append(c)
    sigs = [signature(c) for c in cards]
    doc = {
        "version": "v1",
        "generated": "2026-09-20",
        "policy": {
            "activation_channel": "title+applies_when+symptom",
            "remedy_channel": "how_to_apply+why",
            "locus_vocab": LOCUS, "prereq_vocab_keys": sorted(PREREQ),
            "remedy_vocab": REMEDY,
            "ontology": "analysis/stageF_prerequisite_ontology.md (frozen)",
            "empty_field_means": "unspecified — never forced",
            "firewall": "reads only resources/libero/{global,task_only}",
        },
        "cards": sigs,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    n_org = sum(1 for s in sigs if s["failure_origin"])
    n_pre = sum(1 for s in sigs if s["missing_prerequisites"])
    n_sur = sum(1 for s in sigs if s["failure_surface"])
    print(f"cards {len(sigs)}: with origin {n_org}, with prereq {n_pre}, "
          f"with surface {n_sur}, with neither {sum(1 for s in sigs if not s['failure_origin'] and not s['missing_prerequisites'])}")
    from collections import Counter
    print("prereq -> n cards:", dict(Counter(
        p for s in sigs for p in s["missing_prerequisites"])))
    print("origin -> n cards:", dict(Counter(
        o for s in sigs for o in s["failure_origin"])))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
