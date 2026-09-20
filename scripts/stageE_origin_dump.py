#!/usr/bin/env python3
"""Stage E2 driver — origin extraction over the frozen 134 C1 points.

Reconstructs the decision action exactly like C1's build_primary_points
(b2 event action, else the frozen row's last_action — the latter is not
stored in the queries dump, so coverage of b2.action is checked), extracts
{surface, origin, missing, evidence, confidence} + window, and writes
analysis/stageE_origin_dump.jsonl for the audit-set annotation (E2b).

Usage: python scripts/stageE_origin_dump.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from memory_stagec1_benchmark import EpisodeCtx, _norm  # noqa: E402
from stageE_origin import (extract_origin, raw_trace_query,  # noqa: E402
                           failure_origin_query, origin_event_phrase,
                           key_window)

QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"
OUT = REPO / "analysis" / "stageE_origin_dump.jsonl"


def load_points():
    return [json.loads(l) for l in QUERIES.read_text().splitlines() if l.strip()]


def main() -> None:
    pts = load_points()
    ctxs: dict[str, EpisodeCtx] = {}
    rows = []
    miss_action = 0
    no_decision = 0
    for p in pts:
        ep = p["episode"]
        if ep not in ctxs:
            ctxs[ep] = EpisodeCtx(ep)
        ctx = ctxs[ep]
        b2e = ctx.b2.get(p["turn"]) or {}
        action = _norm(b2e.get("action") or "")
        if not action:
            miss_action += 1
            continue
        o = extract_origin(ctx, p["turn"], action, p["class"])
        if ctx.find_tool(p["turn"], action) is None:
            no_decision += 1
        # window with phrases for audit readability
        window, _dec = key_window(ctx, p["turn"], action)
        phrases = []
        for kind, st, tn, name, r, extra in window:
            if name == "move_run":
                d0, d1 = extra.get("d_first"), extra.get("d_last")
                ph = (f"move_run x{extra.get('n')}"
                      + (f" dist {d0:.3f}->{d1:.3f}"
                         if d0 is not None and d1 is not None else ""))
            else:
                ph = f"{name}: {origin_event_phrase(r, name)}"
            phrases.append(f"  step{st:>3} t{tn:<3} {ph}")
        q0 = p["queries"]["Q0_POOR"]
        rows.append({
            "set": p["set"], "class": p["class"], "gold": p["gold"],
            "episode": ep, "turn": p["turn"], "tl": p["tl"],
            "action": action, "phase": b2e.get("phase", ""),
            "surface": o["surface"], "origin": o["origin"],
            "missing": o["missing"], "evidence": o["evidence"],
            "confidence": o["confidence"],
            "window": phrases, "n_window": len(phrases),
            "q_E2_RAW_TRACE": raw_trace_query(q0, ctx, p["turn"], action),
            "q_E3_FAILURE_ORIGIN": failure_origin_query(q0, o),
        })
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(rows)
    print(f"points {len(pts)} -> rows {n}  (no b2 action: {miss_action}, "
          f"no decision tool: {no_decision})")
    for key in ("surface", "origin", "missing", "confidence"):
        c = Counter(r[key] for r in rows)
        print(f"{key:12s}", dict(c.most_common()))
    # the headline phenomenon: surface != PERCEPTION but origin == PERCEPTION
    perc_cls = [r for r in rows if r["class"] == "perception"]
    sf = Counter(r["surface"] for r in perc_cls)
    og = Counter(r["origin"] for r in perc_cls)
    print(f"\nperception-class n={len(perc_cls)}  surface={dict(sf)}  "
          f"origin={dict(og)}")
    join = Counter((r["surface"], r["origin"]) for r in rows)
    print("\nsurface x origin (all rows):")
    for (s, o), k in join.most_common(12):
        print(f"  {s:11s} x {o:11s} {k}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
