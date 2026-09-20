#!/usr/bin/env python3
"""Stage G0 §F + §G extra-bank audit (REPORT-ONLY, frozen representations).

§F (bank accounting): for every suite x bank used by G4 — requested files,
loaded entries (readable, non-duplicate namespaced id), duplicate stems,
actual unique entries, bank size after the global 61. These numbers are the
G4 x-axis; nothing here edits a bank or a global card.

§G (representation audit): token statistics of the RETRIEVAL-FACING
representation (index line = title + how_to/body, exactly what the loader
builds) for global cards vs extra pages: token count mean/median, vocabulary
size, and the query-overlap distribution against the 134 frozen Stage C1
Q0_POOR queries. NO redesign: if the distributions differ badly we report
the risk and stop (human decision required).

Usage: python scripts/audit_stageG_extra_bank.py
Writes:  analysis/stageG_extra_bank_audit.md + .json
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

BANKS_ROOT = REPO / "analysis" / "stageG_banks"
SUITES = ["libero_object_task", "libero_goal_task", "libero_10_task",
          "libero_spatial_task"]
BANK_KINDS = ["bank_2x", "bank_max"]
C1_QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"
OUT_MD = REPO / "analysis" / "stageG_extra_bank_audit.md"
OUT_JSON = REPO / "analysis" / "analysis_stageG_extra_bank_audit.json"


def extra_index_line(p: Path) -> tuple[str, str]:
    """Mirror DecisionMemory._load_extra_bank: (cid, index line)."""
    import re
    text = p.read_text(encoding="utf-8")
    fm, _, body = text.partition("\n---")
    title = p.stem.replace("_", " ")
    m = re.search(r"^task_language:\s*(.+)$", fm, re.M)
    if m:
        title = m.group(1).strip()[:120]
    how_to = re.sub(r"\s+", " ", body).strip()[:400]
    cid = f"extra::{p.parent.name}::{p.stem}"
    return cid, (title + " " + how_to)[:600]


def main() -> None:
    cards = load_cards()
    gindex = load_index()
    assert len(cards) == 61, f"global cards changed: {len(cards)}"
    gids = sorted(cards)

    rows = []
    stem_seen: dict[str, list[str]] = {}
    extra_lines_all: dict[str, str] = {}
    for su in SUITES:
        for bk in BANK_KINDS:
            d = BANKS_ROOT / su / bk
            requested = sorted(d.glob("*.md")) if d.is_dir() else []
            loaded, unreadable = 0, 0
            lines: dict[str, str] = {}
            for p in requested:
                try:
                    cid, line = extra_index_line(p)
                except OSError:
                    unreadable += 1
                    continue
                if cid in lines:      # cannot happen within one dir; safety
                    continue
                lines[cid] = line
                stem_seen.setdefault(p.stem, []).append(f"{su}/{bk}")
                loaded += 1
            extra_lines_all.update(lines)
            rows.append({
                "suite": su, "bank": bk, "requested": len(requested),
                "loaded": loaded, "unreadable": unreadable,
                "unique_entries": len(lines),
                "bank_size_total": 61 + len(lines),
            })
            assert loaded == len(requested), \
                f"{su}/{bk}: loaded {loaded} != requested {len(requested)}"

    dup_stems = {s: v for s, v in stem_seen.items() if len(v) > 1}

    # ---- §G representation statistics -------------------------------
    def stats(lines: dict[str, str]) -> dict:
        ntoks = [len(toks(v)) for v in lines.values()]
        vocab = set().union(*(toks(v) for v in lines.values())) \
            if lines else set()
        return {
            "n": len(lines),
            "tok_mean": round(statistics.mean(ntoks), 1) if ntoks else 0,
            "tok_median": statistics.median(ntoks) if ntoks else 0,
            "tok_min": min(ntoks) if ntoks else 0,
            "tok_max": max(ntoks) if ntoks else 0,
            "vocab_size": len(vocab),
            "vocab": vocab,
        }

    gs = stats(gindex)
    es = stats(extra_lines_all)

    # query-overlap distribution: for each frozen C1 Q0_POOR query, how many
    # of its tokens appear somewhere in the global vocab vs extra vocab
    # (report-only; identical construction for both sides).
    queries = []
    if C1_QUERIES.exists():
        with open(C1_QUERIES) as f:
            for ln in f:
                if ln.strip():
                    r = json.loads(ln)
                    queries.append(r.get("queries", {}).get("Q0_POOR", ""))

    def overlap_dist(vocab: set[str]) -> dict:
        ov = [len(toks(q) & vocab) / max(len(toks(q)), 1) for q in queries]
        return {
            "n_queries": len(ov),
            "mean": round(statistics.mean(ov), 3) if ov else None,
            "median": round(statistics.median(ov), 3) if ov else None,
            "p90": round(sorted(ov)[int(0.9 * (len(ov) - 1))], 3)
            if ov else None,
            "zero_overlap_rate": round(
                sum(1 for v in ov if v == 0) / len(ov), 3) if ov else None,
        }

    g_ov, e_ov = overlap_dist(gs["vocab"]), overlap_dist(es["vocab"])

    payload = {
        "global_cards": 61,
        "banks": rows,
        "duplicate_stems_across_banks": dup_stems,
        "representation": {
            "global": {k: v for k, v in gs.items() if k != "vocab"},
            "extra": {k: v for k, v in es.items() if k != "vocab"},
            "query_overlap_global": g_ov,
            "query_overlap_extra": e_ov,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    md = ["# Stage G0 — Extra-Bank Audit (§F counts + §G representation)\n",
          "_written before any G4 run; report-only. Banks and global cards "
          "are frozen; no representation redesign is made or implied here._\n",
          "## §F Bank accounting\n",
          "| suite | bank | requested | loaded | unreadable | unique "
          "entries | bank size (61 global + extra) |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['suite']} | {r['bank']} | {r['requested']} | "
                  f"{r['loaded']} | {r['unreadable']} | "
                  f"{r['unique_entries']} | {r['bank_size_total']} |")
    md += ["\nNamespaced ids `extra::<dir>::<stem>`: every loaded entry is "
           "unique by construction; duplicate STEMS across different bank "
           "directories stay distinct ids (regression-tested in "
           "scripts/test_stageG0_audit.py §F).\n",
           f"- duplicate stems across all audited banks: "
           f"{len(dup_stems)}"
           + (f" — {json.dumps(dup_stems, ensure_ascii=False)}" if dup_stems
              else " (none)"),
           "- global card count check: 61 (asserted; ids untouched)\n",
           "## §G Representation statistics (retrieval-facing index line)\n",
           "| set | n | tok mean | tok median | tok min | tok max | "
           "vocab size |",
           "|---|---|---|---|---|---|---|"]
    for name, s in (("global (61)", gs), ("extra (all banks)", es)):
        md.append(f"| {name} | {s['n']} | {s['tok_mean']} | "
                  f"{s['tok_median']} | {s['tok_min']} | {s['tok_max']} | "
                  f"{s['vocab_size']} |")
    md += ["\nQuery-overlap distribution vs the 134 frozen C1 Q0_POOR "
           "queries (fraction of query tokens present in the set's "
           "vocabulary):\n",
           "| set | n queries | mean | median | p90 | zero-overlap rate |",
           "|---|---|---|---|---|---|"]
    for name, o in (("global", g_ov), ("extra", e_ov)):
        md.append(f"| {name} | {o['n_queries']} | {o['mean']} | "
                  f"{o['median']} | {o['p90']} | {o['zero_overlap_rate']} |")
    md += ["\n**Interpretation rule (frozen)**: this section is a RISK "
           "REPORT only. If extra representations are systematically "
           "shorter/longer or their query-overlap profile differs strongly "
           "from the globals, the G4 confound is flagged in the G4 report "
           "and NO format change is made without a human decision.\n"]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {OUT_MD.name} + {OUT_JSON.name}")
    for r in rows:
        print(f"  {r['suite']}/{r['bank']}: req={r['requested']} "
              f"loaded={r['loaded']} bank_size={r['bank_size_total']}")
    print(f"  dup stems: {len(dup_stems)} | global tok med "
          f"{gs['tok_median']} vs extra {es['tok_median']} | "
          f"overlap zero-rate g={g_ov['zero_overlap_rate']} "
          f"e={e_ov['zero_overlap_rate']}")


if __name__ == "__main__":
    main()
