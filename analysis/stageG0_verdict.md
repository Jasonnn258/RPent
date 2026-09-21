# Stage G0 — Verdict (§I four gates, causal audit answer)

_written 2026-09-21 02:2x, after the G0-H DEV run completed 90/90
(zero infra_missing; the 6 morning 429-timeouts all retried successfully;
14→8 worker incident accounted below). Gates pre-registered in
stageG0_manifest.md §I BEFORE the run; no threshold was tuned against any
outcome. n=30/arm, all CIs cross zero except A→D (touches 0 from above) —
by design this audit reads POINT ESTIMATES + paired flips, p-values are
context, not verdicts._

## The numbers

| arm | trigger | query | SR | fires/ep | precision | false/ep | rel@3 |
|---|---|---|---|---|---|---|---|
| A | v1_original | native | .733 | 1.63 | .265 | 1.20 | .571 |
| B | v1_per_result | native | .767 | 1.57 | .128 | 1.37 | .667 |
| C | progress | native | .852 | 0.48 | **1.000** | 0 | .889 |
| D | v1_per_result | common | **.900** | 2.20 | .121 | 1.93 | .400 |
| E | progress | common | .800 | 0.30 | **1.000** | 0 | .833 |

Paired contrasts (b minus a): A→B **+.033** (6v5, p=1.0) | B→C **+.037**
(4v3, p=1.0) | B→D **+.133** (6v2, p=.29) | C→E **−.037** (4v5) |
D→E **−.100** (3v6) | A→D **+.167** (7v2, p=.18, CI [0.0, .367]) |
A→C +.111 (historical Stage C, unchanged).

## Gate answers (in pre-registered order)

1. **Mechanism gate (C vs B): PASS, weakly.** Progress rules still add
   positive gain over v1_per_result under native query (+.037 paired,
   4v3 flips; raw micro +.085). The rules carry real signal beyond
   buffering — but only ~1/3…2/3 of Stage C's +11pp; buffering alone is
   +3pp.
2. **WHEN>WHAT gate (E vs D): FAIL.** Under the common query, progress's
   advantage is not merely gone — it is REVERSED (−.100, 3v6). The
   progress family's edge in Stage C was substantially query composition
   (its descriptive reason text fed retrieval better content), not
   superior timing.
3. **Q3 regression test: PASS** (scripts/test_stageG0_audit.py §C green
   at verdict time).
4. **motion_stuck tests: PASS** (§D, 7 scenarios green).

**Pre-committed decision rule fires: 1 holds + 2 fails → G1-G4 may launch
ONLY with the claim rewritten; a human must review the rewrite BEFORE any
final-suite episode runs.**

## What actually explains Stage C (the re-explanation the audit demanded)

The audit decomposes A→C (+11pp) into three previously-conflated pieces:

- **Event capture (buffering)**: +3pp (A→B). Not zero, not the story.
- **Progress rule content**: +4pp paired (B→C) — but see next point.
- **Query composition (the hidden confound)**: the reason text entered the
  retrieval query with OPPOSITE signs per family — removing it from the
  v1 family's query is worth **+13pp** (B→D, the largest single mover),
  while removing it from progress costs −4…−5pp (C→E). The v1 reason
  strings are failure-mode labels that bias lexical retrieval toward
  failure-symptom cards; the progress reason strings are richer
  state descriptions that genuinely helped retrieval. Stage C compared
  "better rules AND better queries" against "worse rules AND worse
  queries" and attributed all of it to the gate.

## The D-arm paradox (flagged observation, NOT a new claim)

The best arm (D, .900) has the noisiest trigger (2.2 fires/ep, precision
.121, false 1.93/ep) and the worst retrieval relevance (rel@3 .400) —
while both precision-1.0 arms sit lower (.852/.800). Whatever helps in D,
it is not "retrieving the right card at the right moment". Candidate
readings (to be tested by the ALREADY-PLANNED arms, no new triggers):
frequent soft context injection acts as periodic re-orientation for the
planner — exactly the hypothesis G2's T2_PERIODIC baseline was designed
to adjudicate, now with sharply higher prior. This is also consistent
with Stage C's earlier finding that injection content mattered less than
expected.

## Claim rewrite (proposed, pending human review)

- OLD: "A progress-aware memory gate (better WHEN) drives the Stage C
  .733→.852 gain; decision-point recall beats baseline recall."
- NEW: "**Reliable event capture + soft decision-point context injection**
  drives the gain: per-result event capture preserves signals (+3pp) and
  frequent soft context at decision points helps the planner re-orient
  (+13pp when the query stops biasing retrieval); progress-aware rule
  content adds a smaller further gain (+4pp). Timing alone (WHEN) does
  not dominate query composition (WHAT) — the two interact."
- WHEN/WHAT superiority wording is REMOVED from the mechanism section;
  Stage C's numbers are reported with the confound decomposition above.
- memO2/progress arms remain in G1 unchanged (they are the deployed
  configuration and the audit does not modify frozen arms); the D
  configuration becomes a REPORTED observation feeding G2, not a new arm.

## Incident bookkeeping (run integrity)

- 08:08 launch 14 workers (GPU5 occupied by another user → 7 GPUs);
  10:00 GLM 429 rate-limiting confirmed by direct probe (2/3 rejected);
  6 healthy episodes died at the 3600s planner timeout (all t3) and were
  auto-requeued (≤3 retry discipline); 10:06 restart at 8 workers
  (resume-safe), post-restart walls 1052-2002s, zero further timeouts;
  run completed 22:24. Final: 90/90 recorded, 0 infra_missing, 0 retries
  exhausted.
- Arm purity verified on ALL events (47 g0B / 66 g0D / 9 g0E):
  trigger_mode and query_mode match the declared arm everywhere; zero
  contamination.
- A/C reuse rows reproduce Stage C's published numbers exactly (SR .733 /
  .852; trigger profile 1.63 fires@.265 vs 0.48@1.0) — the reuse chain is
  byte-consistent with the historical runs.

## Required before G1 (blocking)

Human review of the claim rewrite above (approve / edit / reject).
G1-G4 grids, arms, and analyzers stay exactly as committed (2c67cbd,
c6bed6b, 3f5adff, 9f048af, 0f836ca) — G2's T2/T3 baselines now carry
additional explanatory weight.
