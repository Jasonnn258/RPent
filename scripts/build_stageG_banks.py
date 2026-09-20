#!/usr/bin/env python3
"""Stage G4 — build the memory-scale distractor banks (mechanical, frozen).

Rules (analysis/stageG_subset_manifest.md §3, pre-registered):
  pool   = resources/libero/suite/*.md EXCLUDING pages of the run suite's
           own grid (prefix "suite_{run_suite}_")
  bank_2x= the first 61 pool pages by sorted filename  (61+61 = 122 entries)
  bank_max = all pool pages                            (61+65/66 entries)
Selection is by sort order only — no content inspection, no fake cards,
no edits to the 61 global cards. Pages are SYMLINKED (single source of
truth); the runtime loader reads them via RPENT_MEMORY_EXTRA_BANK.

Usage: python scripts/build_stageG_banks.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "resources" / "libero" / "suite"
OUT_ROOT = REPO / "analysis" / "stageG_banks"
# registry suite name -> page-grid prefix (the libero_10 family's pages are
# named "suite_libero10_..." without the underscore)
RUN_SUITES = {"libero_object_task": "suite_libero_object_task_",
              "libero_goal_task": "suite_libero_goal_task_",
              "libero_10_task": "suite_libero10_task_"}


def build(run_suite: str, prefix: str) -> dict:
    pool = sorted(p for p in SRC.glob("suite_*.md")
                  if not p.name.startswith(prefix))
    out = {}
    for name, sel in (("bank_2x", pool[:61]), ("bank_max", pool)):
        d = OUT_ROOT / run_suite / name
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.md"):
            old.unlink()   # idempotent rebuild
        for p in sel:
            os.symlink(p.resolve(), d / p.name)
        out[name] = len(sel)
    return out


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"missing {SRC}")
    for su, prefix in RUN_SUITES.items():
        got = build(su, prefix)
        assert not any(p.name.startswith(prefix)
                       for p in (OUT_ROOT / su / "bank_max").glob("*.md"))
        print(f"{su}: bank_2x +{got['bank_2x']} pages (total 61+"
              f"{got['bank_2x']}={61 + got['bank_2x']}), "
              f"bank_max +{got['bank_max']} (total {61 + got['bank_max']})")
    print("wrote", OUT_ROOT)


if __name__ == "__main__":
    main()
