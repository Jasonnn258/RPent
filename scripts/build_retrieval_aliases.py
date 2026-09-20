#!/usr/bin/env python3
"""Stage D Step 1 — build runtime-observable retrieval aliases for Memory Cards.

Hypothesis (user spec, 2026-09-20): perception retrieval fails because the cards
never carried the vocabulary the robot actually emits at runtime. This script
adds retrieval-only aliases derived EXCLUSIVELY from each card's own material:

  R1  symptom bullets            (card frontmatter, verbatim)
  R3a observable field harvest   (task_only/{cell}.json: pick_result strings,
                                  visual_confirmation, localization string
                                  leaves incl. rejected_segment_prompts /
                                  uncertainty, failure_history, perception*,
                                  final_state.note, notes, contact_result;
                                  long prose is sentence-filtered by a frozen
                                  marker wordlist)
  R5  recipe prompts             (task_only/{cell}_recipe.jsonl segment/
                                  back_project prompts; perception-kind cards
                                  only — the prompt text is what the robot
                                  actually issued)

DELIBERATE V1 CHOICE: no hand-written phrase grammar / regex table. Every alias
is a verbatim (whitespace/case-normalised, <=12-token-truncated) quote from a
source field, so each one is traceable to {source_cell, source_field,
source_excerpt} and investigator degrees of freedom are minimised.

LEAKAGE FIREWALL: this script reads ONLY resources/libero/{global,task_only}.
It must not import or open any Stage A/C1 test-query artifact (that would be
reverse-engineering aliases from the benchmark). Enforced by construction:
the only paths opened live under RES/.

Output: analysis/retrieval_aliases_v1.json
  {version, generated, policy{...}, cards: [{memory_id, kind, source_cells,
   retrieval_aliases: [str], alias_sources: [{alias, source_cell,
   source_field, source_excerpt}]}]}

Usage: python scripts/build_retrieval_aliases.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RES = REPO / "resources" / "libero"
GLOBAL = RES / "global"
TASK_ONLY = RES / "task_only"

# ---- frozen policy constants (audit-reported, not tuned on any test set) ----
ALIAS_MAX_TOKENS = 12          # spec: terse observable phrases
GLOBAL_CAP = 8                 # spec: 0-8 aliases per card
R1_CAP = 6                     # symptom bullets per card
R3_STRATEGY_CAP = 2            # sentences harvested from strategy_notes
R3_REJECT_CAP = 2              # rejected_segment_prompts entries per entry-key
R5_CAP = 2                     # recipe prompts (perception cards only)
COMPACT_MAX_CHARS = 90         # strings this short are taken whole
EXCERPT_MAX_CHARS = 140

# Frozen observable-marker wordlist for sentence-filtering long prose. All are
# generic robot-runtime vocabulary; none is task- or test-specific.
MARKERS = frozenset("""
success false true held holding opening lift lifted stall stalled predicate
occluded occludes segment segmented segmentation mask masked prompt prompted
gripper terminated carried carry drift drifted wrong distractor duplicate
hover hovering slide slipped slip snag snagged roll rolled tip tipped collide
collision wall rim liner perched grasp grabbed descend descent retreat
relocate coordinates pixel pixels back_project
""".split())

CELL_RE = re.compile(r"^[a-z0-9]+_[a-z]+_t\d+_s\d+$")


# ------------------------------------------------------------- card parsing
def parse_card(path: Path) -> dict:
    """Minimal frontmatter parse: id/kind/title/applies_when/symptom/cells."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    fm = text.split("---", 2)[1]
    card: dict = {"id": path.stem, "symptom": [], "cells": []}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(id|kind|title):\s*(.+)$", ln)
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
                if CELL_RE.match(v):
                    card["cells"].append(v)
                i += 1
            continue
        i += 1
    card.setdefault("kind", "")
    return card


def norm_alias(s: str) -> str:
    """Normalise a verbatim source string into a terse alias phrase."""
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"[\[\](){}'\"`]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower().rstrip(".,;:")
    toks = s.split()
    return " ".join(toks[:ALIAS_MAX_TOKENS])


def excerpt(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:EXCERPT_MAX_CHARS] + ("…" if len(s) > EXCERPT_MAX_CHARS else "")


# ------------------------------------------------------------- R3a harvest
def harvest_strings(obj, path_prefix: str, out: list, reject_budget: dict):
    """Walk a task_only JSON value; collect (source_field, raw_string) pairs.

    Compact strings (<=COMPACT_MAX_CHARS) are kept whole; longer prose is
    sentence-split and only sentences carrying a MARKER word are kept.
    Numeric / list-of-number leaves are skipped (coordinates are not phrases).
    """
    if isinstance(obj, str):
        if len(obj) <= COMPACT_MAX_CHARS and len(obj) >= 8:
            out.append((path_prefix, obj))
        else:
            for sent in re.split(r"(?<=[.;])\s+|\n", obj):
                sent = sent.strip()
                w = re.findall(r"[a-zA-Z0-9]+", sent.lower())
                if 4 <= len(w) <= 30 and MARKERS & set(w):
                    out.append((path_prefix, sent))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float, bool)) or v is None:
                continue
            if k == "object_names" or k.startswith("robot0_"):
                continue  # scene inventory / robot state, not phenomenon text
            if isinstance(v, list) and v and all(
                    isinstance(x, (int, float)) for x in v):
                continue  # pixel / xyz arrays
            if k == "rejected_segment_prompts" and isinstance(v, list):
                used = 0
                for item in v:
                    if isinstance(item, str) and used < R3_REJECT_CAP:
                        out.append((f"{path_prefix}.{k}", item))
                        used += 1
                reject_budget[path_prefix] = used
                continue
            harvest_strings(v, f"{path_prefix}.{k}", out, reject_budget)
    elif isinstance(obj, list):
        for n, item in enumerate(obj):
            if isinstance(item, (str, dict)):
                harvest_strings(item, f"{path_prefix}[{n}]", out, reject_budget)


R3_FIELD_ORDER = [  # intake priority; sub-caps via caps dict below
    ("pick_result", 3),
    ("localization", 4),
    ("failure_history", 3),
    ("perception_summary", 2),
    ("perception", 2),
    ("perception_table", 2),
    ("contact_result", 2),
    ("final_state", 2),
    ("notes", 2),
    ("strategy_notes", R3_STRATEGY_CAP),
]


def r3_harvest(cell: str) -> list[tuple[str, str]]:
    """(source_field, raw) observable strings from task_only/{cell}.json."""
    p = TASK_ONLY / f"{cell}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: list[tuple[str, str]] = []
    for field, cap in R3_FIELD_ORDER:
        if field not in data:
            continue
        got: list[tuple[str, str]] = []
        harvest_strings(data[field], field, got, {})
        if not got:
            continue
        if field == "strategy_notes":
            got = got[:cap]
        # dedupe within field, keep order, apply cap
        seen: set[str] = set()
        picked: list[tuple[str, str]] = []
        for f, s in got:
            key = norm_alias(s)
            if key and key not in seen:
                seen.add(key)
                picked.append((f, s))
            if len(picked) >= cap:
                break
        out.extend((f"{cell}:{f}", s) for f, s in picked)
    return out


def r5_prompts(cell: str) -> list[tuple[str, str]]:
    """Distinct perception prompts actually issued in the recipe stream."""
    p = TASK_ONLY / f"{cell}_recipe.jsonl"
    if not p.exists():
        return []
    seen: list[str] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                cmd = json.loads(line)
            except json.JSONDecodeError:
                continue
            if cmd.get("action") in ("segment", "back_project") \
                    and isinstance(cmd.get("prompt"), str):
                pr = cmd["prompt"].strip()
                if pr and pr.lower() not in seen:
                    seen.append(pr.lower())
    except OSError:
        pass
    return [(f"{cell}:recipe", f"segmentation prompt: {pr}")
            for pr in seen[:R5_CAP]]


# ------------------------------------------------------------------- main
def build() -> dict:
    cards_out = []
    n_alias = 0
    for path in sorted(GLOBAL.glob("*.md")):
        card = parse_card(path)
        if not card.get("kind"):
            continue
        cid = card["id"]
        sources: list[dict] = []
        seen_tokens: list[frozenset] = []

        def add(alias: str, cell: str | None, field: str, raw: str,
                reserve_r5: bool = False):
            a = norm_alias(alias)
            cap = (GLOBAL_CAP - R5_CAP) if reserve_r5 else GLOBAL_CAP
            # hygiene: an alias must carry at least one real word — numeric
            # residue like "12+1+1+1" is not a retrieval phrase
            if not a or len(sources) >= cap \
                    or not re.search(r"[a-z]{3,}", a):
                return
            t = frozenset(a.split())
            if not t or t in seen_tokens:
                return
            if any(t <= prev for prev in seen_tokens):
                return  # token-subset of an existing alias: no new signal
            seen_tokens.append(t)
            sources.append({
                "alias": a,
                "source_cell": cell,
                "source_field": field,
                "source_excerpt": excerpt(raw),
            })

        # perception cards reserve their last slots for R5 recipe prompts,
        # but only when those cells actually issued perception prompts
        r5_pool = ([(cell, f, raw) for cell in card["cells"]
                    for f, raw in r5_prompts(cell)]
                   if card["kind"] == "perception" else [])
        reserve = bool(r5_pool)

        # R1 — symptom bullets (card-intrinsic observable phrases)
        for sym in card["symptom"][:R1_CAP]:
            add(sym, None, "symptom", sym, reserve_r5=reserve)

        # R3a — observable field harvest from each evidence cell
        for cell in card["cells"]:
            for field, raw in r3_harvest(cell):
                add(raw, cell, field, raw, reserve_r5=reserve)

        # R5 — recipe prompts, perception cards only
        for cell, field, raw in r5_pool:
            add(raw, cell, field, raw)

        n_alias += len(sources)
        cards_out.append({
            "memory_id": cid,
            "kind": card["kind"],
            "source_cells": card["cells"],
            "retrieval_aliases": [s["alias"] for s in sources],
            "alias_sources": sources,
        })

    return {
        "version": "retrieval_aliases_v1",
        "generated": "2026-09-20",
        "policy": {
            "layers": ["R1:symptom<=5", "R3a:task_only-field-harvest",
                       "R5:recipe-prompts<=2-perception-only"],
            "global_cap_per_card": GLOBAL_CAP,
            "alias_max_tokens": ALIAS_MAX_TOKENS,
            "compact_max_chars": COMPACT_MAX_CHARS,
            "marker_wordlist": sorted(MARKERS),
            "no_hand_written_phrase_grammar": True,
            "sources_read": ["resources/libero/global/*.md",
                             "resources/libero/task_only/*.json",
                             "resources/libero/task_only/*_recipe.jsonl"],
            "leakage_firewall": ("script never reads Stage A/C1/C3 query or "
                                 "failure artifacts; aliases are frozen after "
                                 "audit; no test-driven iteration"),
        },
        "n_cards": len(cards_out),
        "n_aliases_total": n_alias,
        "cards": cards_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "analysis"
                                         / "retrieval_aliases_v1.json"))
    args = ap.parse_args()
    doc = build()
    Path(args.out).write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n_empty = sum(1 for c in doc["cards"] if not c["retrieval_aliases"])
    print(f"cards={doc['n_cards']} aliases={doc['n_aliases_total']} "
          f"empty_cards={n_empty} -> {args.out}")


if __name__ == "__main__":
    main()
