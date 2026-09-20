#!/usr/bin/env python3
"""Stage D Step 2 — alias audit statistics for analysis/stageD_alias_audit.md.

Reads the frozen sidecar plus (for the LEAKAGE CHECK ONLY, which is its whole
job) the C1 frozen query dump. Produces every number quoted in the audit md:

  coverage / layer / source-field / length distributions
  cross-card collision pre-check (alias tokens shared across many cards)
  leakage check: >=3-token contiguous overlap alias vs any test query text

Usage: python scripts/audit_stageD_aliases.py
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SIDE = json.loads((REPO / "analysis" / "retrieval_aliases_v1.json").read_text())
QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"

# Stage A class families (card-id -> family) — reporting only.
FAMILY = {
    "predicate_timing": """predicate-fires-after-gripper-retreat
predicate-gated-by-eef-proximity-retreat-clear open-retreat-settles-container
basket-release-retreat-settle basket-insertion-open-retreat
libero-in-predicate-fires-while-grasped low-pose-settle-regrasp
low-contact-seat-after-release near-goal-contact-regrasp near-target-repick
near-miss-corrective-pick learned-contact-after-near-placement
libero10-left-right-sign-verify-empirically caddy-back-is-near-robot-pocket
named-compartment-via-front-back-pair right-front-perimeter-contact
knob-side-front-zone drawer-top-contact-before-release""".split(),
    "pick_verify": """pi0-pick-carries-past-lift-judge-by-grip can-pick-visual-confirmation
visual-over-pick-heuristic pi0-pick-may-place-at-trained-left""".split(),
    "grasp": """moka-pot-grasp-the-handle-not-the-body pi0-grasp-tall-mug-by-handle
open-side-bowl-grasp pick-before-contact-skill-keeps-wrist-clean
pregrasp-yaw-recenter spatial-qualified-repick held-offset-rotation-reach
post-grasp-yaw-offset remeasure-loaded-offset-before-descent""".split(),
    "recovery": """co-vary-pitch-clears-yawed-reach-wall rotate-wrist-90deg-drifts-eef-recenter-after
held-contact-container-insertion closed-gripper-container-insertion
support-assisted-axis-reorientation support-guided-weak-hook-translation
container-slide-axis-toward-fixture-body probe-container-floor-by-stall-height
retreat-high-before-lateral-near-lined-basket reverse-entry-corridor-clearance
avoid-full-task-prompt-after-miss leaned-contact-before-policy-push
high-drop-over-cavity flat-box-basket-interior-drop flat-box-rigid-bowl-seat
rim-perch-contact-seat pitched-side-grasp-overedge-release
basket-two-cans-wedge-not-stack boxes-tolerate-stacking-in-basket
object-frame-box-to-basket pi0-prepositioned-simple-basket
place-order-never-carry-over-placed-object contact-skill-state-change""".split(),
    "perception": """sam3-brand-noun-can-collision brand-label-over-segmentation
box-vs-can-lid-wrist-disambiguation point-prompt-after-text-misground
relation-anchored-wrist-refine relation-selected-identical-object
verify-duplicate-semantics""".split(),
}
CID2FAM = {c: f for f, cs in FAMILY.items() for c in cs}


def toks(s: str) -> set[str]:
    STOP = {"the", "and", "for", "with", "that", "this", "was", "are", "not",
            "but", "its", "into", "from", "over", "after", "before", "did",
            "does", "you", "your", "when", "which", "than", "then", "all",
            "any", "can", "may", "must", "should", "would", "will", "has",
            "have", "had", "been", "being", "were", "onto", "upon", "via"}
    return {w for w in re.findall(r"[a-z0-9]+", s.lower())
            if w not in STOP and len(w) > 2}


def ngrams(t: list[str], n: int = 3) -> set[tuple[str, ...]]:
    return {tuple(t[i:i + n]) for i in range(len(t) - n + 1)}


def main() -> None:
    cards = SIDE["cards"]
    fam_of = lambda c: CID2FAM.get(c["memory_id"], "other")

    # ---- coverage / layers / lengths
    per_fam = collections.Counter()
    n_alias_per_fam = collections.Counter()
    layer = collections.Counter()
    field_src = collections.Counter()
    lens = []
    for c in cards:
        per_fam[fam_of(c)] += 1
        n_alias_per_fam[fam_of(c)] += len(c["retrieval_aliases"])
        lens.append(len(c["retrieval_aliases"]))
        for s in c["alias_sources"]:
            f = s["source_field"]
            layer["R1_symptom" if f == "symptom" else
                  ("R5_recipe" if "recipe" in f else "R3a_field")] += 1
            key = f.split(":")[-1].split(".")[0].split("[")[0]
            field_src["symptom" if f == "symptom" else
                      ("recipe" if "recipe" in f else key)] += 1
    print("== cards per family ==", dict(per_fam))
    print("== aliases per family ==", dict(n_alias_per_fam))
    print("== layer distribution ==", dict(layer))
    print("== source fields ==", dict(field_src.most_common()))
    print(f"== per-card aliases min/mean/max = {min(lens)} / "
          f"{sum(lens)/len(lens):.2f} / {max(lens)}; total {sum(lens)}")
    al_lens = [len(s["alias"].split()) for c in cards
               for s in c["alias_sources"]]
    print(f"== alias token length min/mean/max = {min(al_lens)} / "
          f"{sum(al_lens)/len(al_lens):.2f} / {max(al_lens)}")

    # ---- collision pre-check: alias tokens appearing across many cards
    tok2cards = collections.defaultdict(set)
    for c in cards:
        at = set()
        for s in c["alias_sources"]:
            at |= toks(s["alias"])
        for t in at:
            tok2cards[t].add(c["memory_id"])
    shared = sorted(((len(v), t) for t, v in tok2cards.items()), reverse=True)
    print("== tokens present in >=8 cards' aliases (top 25) ==")
    for n, t in shared[:25]:
        if n >= 8:
            print(f"   {n:2d}  {t}")

    # ---- leakage check: >=3-token contiguous overlap with C1 query texts
    qtexts = []
    for line in QUERIES.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            qtexts.append((r["episode"], r["turn"], r["class"],
                           " ".join(r["queries"].values()) + " " + r["tl"]))
    qgrams = collections.Counter()
    qtok_lists = []
    for ep, tu, cl, txt in qtexts:
        tl = [w for w in re.findall(r"[a-z0-9]+", txt.lower()) if len(w) > 2]
        qtok_lists.append((ep, tu, cl, tl))
        for g in ngrams(tl):
            qgrams[g] += 1
    hits = []
    for c in cards:
        for s in c["alias_sources"]:
            at = [w for w in re.findall(r"[a-z0-9]+", s["alias"]) if len(w) > 2]
            for g in ngrams(at):
                if g in qgrams:
                    hits.append((c["memory_id"], s["alias"], " ".join(g),
                                 qgrams[g],
                                 [f"{ep}@{tu}/{cl}" for ep, tu, cl, tl
                                  in qtok_lists
                                  if g in {tuple(tl[i:i+3])
                                           for i in range(len(tl)-2)}][:3]))
    print(f"\n== leakage: aliases sharing a 3-gram with a test query: "
          f"{len(hits)} ==")
    for cid, alias, g, n, where in hits:
        print(f"   [{cid}] alias='{alias}' 3gram='{g}' x{n} in {where}")


if __name__ == "__main__":
    main()
