# Stage G0 — Causal Implementation Audit Manifest (pre-registered)

_written 2026-09-20, BEFORE the G0-H development run. Commit of code +
tests + manifests precedes any G0 episode (user-mandated order)._

Goal: confirm the final CVPR experiment compares ONLY the declared
variables. Stage C's v1→progress (.733→.852 on DEV) changed rule content
AND signal buffering at once; historical queries also coupled the trigger
reason into retrieval (WHEN changed WHAT). G0 splits both.

## Frozen throughout G0 (violations = stop)

- Progress trigger R1-R5, thresholds, cooldown semantics — untouched.
- v1 trigger T1-T7 — untouched (`_trigger_reason` delegates verbatim to
  `_v1_rules_for`; unit battery proves identity).
- Q3 weights / pool size / encoder / phase map — untouched.
- Global 61 cards, MEMORY.md, extra-bank page contents — untouched.
- Final-test suites (object/goal/10) — NOT TOUCHED in G0. DEV suite only.
- Historical Stage C rows/results — reused as-is, never re-run or edited.
- No threshold may be adjusted against ANY benchmark outcome.

## §H Development five-arm comparison (pre-registered grid)

DEV suite (`libero_spatial_task`) × tasks {t3, t5, t9} × seeds s1-s10 × r1,
tier `glm-5.3-flash` (the frozen tier of every memory arm).

| arm | trigger | query mode | rows | source |
|---|---|---|---|---|
| A | v1_original (frozen) | native | 30 | REUSE memB2 stage rows (code+config identical: TRIGGER=1, Q0_FIXED, native default) |
| B | v1_per_result (G0-A) | native | 30 | fresh `--stage g0 --conds g0B` |
| C | progress (frozen C2) | native | 30 | REUSE memO2 stage rows (27 valid / 3 infra_missing, Stage C accounting) |
| D | v1_per_result | common | 30 | fresh `--conds g0D` |
| E | progress | common | 30 | fresh `--conds g0E` |

Fresh workload: 90 episodes (~5.5 h at 16 workers). All five arms share
Q0_FIXED ranking, access fix, soft injection, EVAL_TURNS=40, osmesa.

Causal contrasts:
- **A→B**: signal preservation alone (rules identical, buffering differs).
- **B→C**: progress rule content alone (buffering identical, shared flush).
- **B→D and C→E**: query composition alone (trigger identical; common
  query = phase + trigger-result action + trigger-result fields +
  task_language; reason logged but never scored).
- A vs (D,E) additionally removes both confounds at once.

Reuse legitimacy for A/C: for Q0_FIXED + native the v1 code path builds the
same query string as the historical runs; G0-E attempt logging and the Q3
explicit-state fix do not touch Q0_FIXED/native behavior (regression-tested;
deviations are declared in stageG0_trigger_semantics_audit.md).

Pre-registered metrics (report ALL, no cherry-picking):
1. SR per arm (valid episodes; infra_missing excluded, counted openly).
2. Paired flips A→B→C and B→D, C→E (same task+seed cell, McNemar exact;
   paired bootstrap 10k, seed 20260920 — same stats frozen in
   scripts/analyze_memory_stageG.py).
3. Trigger precision / recall vs Stage A gold decision points (strict
   same-family alignment; T2/T3-style agnostic alignment reported
   separately), false triggers per episode.
4. Retrieval-empty rate, retrieval count per episode, relevant@3.

This is a causal audit, NOT a significance hunt: point estimates + paired
flips carry the interpretation; p-values are context.

## §I Go/No-Go gates for G1-G4 (all four must hold)

1. **Mechanism gate**: progress (C) still shows positive mechanism gain vs
   v1_per_result (B) on SR and/or paired flips — i.e. the progress RULES,
   not just buffering, carry part of the Stage C effect.
2. **WHEN>WHAT gate**: under common query, progress's advantage (E vs D)
   is not fully eliminated. If it vanishes, Stage C's gain was substantially
   query-composition (the reason text feeding retrieval), and the claim
   "progress-gated WHEN beats baseline WHEN" must be re-explained before
   any final suite runs.
3. **Q3 regression test passes** (scripts/test_stageG0_audit.py §C — queued
   fire rescored against the trigger result, never a later result).
4. **motion_stuck tests pass** (§D five scenarios + phase/missing-target
   resets).

Decision rules (pre-committed):
- Both 1 and 2 hold → launch G1 final-test suites unchanged.
- 1 holds, 2 fails → launch allowed ONLY with the claim rewritten from
  "Progress Gate alone" to "Reliable event capture + progress-aware
  gating"; WHEN/WHAT wording removed from the paper's mechanism section;
  human reviews the rewrite before G1 starts.
- 1 fails (Stage C gain mostly from per-result buffering) → same claim
  rewrite as above AND Stage C's mechanism narrative must be re-derived
  from the A/B contrast; no final-suite run until the rewritten claim is
  human-approved.

Verdict doc: `analysis/stageG0_verdict.md` (written after §H, gates
answered in order, each with the numbers that decided it).

## Implementation audit trail (all committed before the run)

- `rpent/memory/retrieval.py` — v1_per_result mode (§A), QUERY_MODE
  common/native (§B), `_q3` explicit-state signature (§C), motion_stuck
  same-target hardening (§D), attempt logging with
  retrieval_status/retrieval_empty/trigger_fired (§E), namespaced
  extra-bank ids `extra::<dir>::<stem>` (§F).
- `rpent/planner/api_loop.py` — gate accepts v1_per_result; log line
  carries rank/mode/query.
- `scripts/ovpm_exp.py` — conds g0B/g0D/g0E, stage g0 (DEV grid, defaults
  t3/t5/t9 × s1-10 × r1).
- `scripts/test_stageG0_audit.py` — §A-F unit battery (must pass before
  the run; also gate 3/4 of §I).
- `analysis/stageG0_trigger_semantics_audit.md` — six-way semantics table
  + declared deviations.
- `scripts/audit_stageG_extra_bank.py` →
  `analysis/stageG_extra_bank_audit.md` (+ .json) — §F counts, §G
  representation statistics (report-only; representation differences are
  flagged as risk, never redesigned without a human decision).
