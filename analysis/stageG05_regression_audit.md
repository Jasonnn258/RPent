# Stage G0.5 — Regression & Implementation Audit (§18/§19)

_written 2026-09-21 03:2x, BEFORE any g05 episode. Code committed together
with this doc; preregistration (e613a41) precedes all of it._

## What changed (and only this)

`rpent/memory/retrieval.py`:

1. Module constants: `INJECTION_MODES`, `_NO_RETRIEVAL_MODES`,
   `GENERIC_REFRESH_BLOCK` (F3), `MEMORY_CONTEXT_HEADER` (F4 header),
   `_reason_only_block()` (F2). Texts byte-frozen per preregistration §2.
2. `__init__`: `RPENT_MEMORY_INJECTION_MODE` (default `full`) +
   fail-fast validation (undeclared value; injection mode combined with
   any trigger other than `v1_per_result`) + explicit alias knobs
   `RPENT_MEMORY_QUERY_REASON` / `RPENT_MEMORY_BLOCK_REASON`
   cross-validated against the modes they mark.
3. `_flush_boundary`: P0/P1/P2 branch (`_fire_without_retrieval`) placed
   AFTER the cap/cooldown checks and queued-fire pop — trigger
   instrumentation, cooldown, cap, drop-on-cooldown identical in every
   arm; retrieval itself skipped. P3 branch at the block render only.
   Events now carry `injection_mode` on every fire.
4. `_memory_only_block` / `_fire_without_retrieval` — new methods,
   deliberate siblings; the frozen `_block()` is untouched.

`scripts/ovpm_exp.py`: conds `g05P0..g05P3` (= g0D env + injection
knobs only), stage `g05` (grid t3/t5/t9 × s1-10 × r1, DEV suite,
flash tier), argparse choices.

Nothing else. v1 rules, progress rules, Q0, Q3, Global Memory, card
texts, `_block()`, api_loop, planner, Pi0.5, SAM3: untouched.

## Regression evidence (§19)

`scripts/test_stageG05_injection.py` — 7/7 GREEN:

1. default (no env) == explicit `full`, bitwise, at fixed QUERY_MODE;
   and `== _block(reason, top3)` reconstruction — the P4-reuse basis.
2. `reason_only`: retrieval provably not called (stub raises); block =
   F2 exact; event `retrieval_status=NOT_RUN`, `retrieval_empty=None`,
   latency 0, top3 [], tokens counted.
3. `generic_refresh`: block = F3 verbatim (5 frozen lines); reason and
   cards absent.
4. `memory_only`: retrieval runs (`MATCH`, top3 recorded); header = F4;
   card lines BITWISE equal `_block()`'s for the same top-3; reason
   string absent from the entire block.
5. `none`: returns None (api_loop's None path = no injection); event
   logged with NOT_RUN; no retrieval_tokens field.
6. cooldown + drop-on-cooldown honored under none-mode (fires capped,
   instrumentation only).
7. env contradictions all fail fast: bogus mode value; injection mode
   on non-v1_per_result triggers; QUERY_REASON vs QUERY_MODE conflict;
   BLOCK_REASON=0 outside memory_only.

`scripts/test_stageG0_audit.py` — ALL SECTIONS GREEN after the change
(§A v1 identity, §B query modes, §C Q3 queued-result, §D motion_stuck,
§E attempt logging, §F namespaced ids): the historical paths are
regression-identical.

## Channel table (as implemented)

| arm | trigger | retrieval | planner block | event signature |
|---|---|---|---|---|
| P0 g05P0 | v1_per_result | NOT_RUN | none | injection_mode=none, NOT_RUN |
| P1 g05P1 | v1_per_result | NOT_RUN | F2(reason) | injection_mode=reason_only, NOT_RUN |
| P2 g05P2 | v1_per_result | NOT_RUN | F3 | injection_mode=generic_refresh, NOT_RUN |
| P3 g05P3 | v1_per_result | common query, Q0_FIXED | F4 + cards | injection_mode=memory_only, MATCH/EMPTY |
| P4 g0D reuse | v1_per_result | common query, Q0_FIXED | _block() reason+cards | historical g0D events (no injection_mode field ≡ full) |

Analyzer treats a missing `injection_mode` as `full` (historical rows).

## Remaining pre-run checklist

- [x] both test batteries green (this file, above)
- [x] prereg committed before implementation (e613a41)
- [ ] implementation + tests + this audit committed BEFORE first episode
- [ ] 1-episode smoke per new arm adopted into its grid cell (t3_s1_r1)
- [ ] campaign pause doc finalized after orphan adoption (§1)
