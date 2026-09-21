# Stage G0.5 — Pre-registration (committed BEFORE any implementation/run)

_written 2026-09-21 ~03:1x. User directive: 先写本文件 → 先 commit → 之后零修改。
Question this stage answers: 当前线上增益究竟主要来自什么 —
(A) real long-term memory content / (B) trigger reason shown to planner /
(C) generic decision-point reorientation / (D) reason×memory interaction.
NOT progress timing (G0 already showed WHEN does not dominate)._

## 0. Configuration-mismatch check against historical G0-D (§7 demanded)

G0-D's exact definition (stage g0 / cond g0D, frozen in 9f048af):

- trigger = `v1_per_result` (frozen T1-T7 verbatim, per-result eval,
  drop-on-cooldown, single-slot queue, cap 6, cooldown 2)
- retrieval query = `QUERY_MODE=common` = phase + trigger-result action +
  trigger-result fields + task_language — **trigger reason NOT in the
  query text and Q3 reason term = {}** (proven by
  scripts/test_stageG0_audit.py §B/§C, green at commit time)
- ranking = Q0_FIXED lexical over the original 61-card global bank
- planner block = `[DECISION-POINT MEMORY RECALL] (turn N; trigger: R)` +
  fixed framing line + top-3 cards (reason IS planner-visible)
- grid = libero_spatial_task × {t3,t5,t9} × s1-10 × r1, tier glm-5.3-flash,
  EVAL_TURNS=40, osmesa, soft injection, access fix

The user's P4 requirement — same trigger, NEUTRAL query without reason,
reason + real Top-3 in planner context — **matches g0D on every field**.
No mismatch. No STOP. P4 = the 30 existing g0D rows, REUSED, not rerun.

## 1. Reuse audit (§6/§8) — the honest accounting

| arm | reusable? | reason | source |
|---|---|---|---|
| P4 full | YES, strict | every field matches (§0 above) | 30 g0D rows |
| P0 none | NO | no historical arm ever ran the trigger instrumented with ZERO injection (all mem* arms inject; B0 baselines never run the trigger) | fresh 30 |
| P1/P2/P3 | NO | new injection modes | fresh 30 each |

**Total new episodes = 120** (not the ≤90 ceiling estimated assuming P0
reuse). This is the "否则诚实重跑" branch of §8. Grid per arm:
libero_spatial_task × {t3,t5,t9} × s1-10 × r1, tier glm-5.3-flash.

## 2. The five arms (§6)

All five share: trigger `v1_per_result` (channel 1 identical, fires logged),
v1_per_result per-result capture, cooldown 2 / cap 6 / max-trigger frozen,
Q0_FIXED ranking + original 61-card bank for any arm that retrieves,
planner / Pi0.5 / SAM3 / primitives / turn budget 40 / temperature /
timeout / system prompt identical. ONLY the post-trigger planner context
(channel 3) differs. All memory-retrieving arms use the SAME NEUTRAL QUERY.

| arm | cond | retrieval query | planner-visible injection |
|---|---|---|---|
| P0_NO_INTERVENTION | g05P0 | not run | none |
| P1_REASON_ONLY | g05P1 | not run | reason block (text F2) |
| P2_GENERIC_REFRESH | g05P2 | not run | frozen reorientation text (F3) |
| P3_MEMORY_ONLY | g05P3 | NEUTRAL (common) | neutral header + top-3 cards (F4) |
| P4_FULL_D | g0D (reuse) | NEUTRAL (common) | recall header + reason + top-3 cards |

### Frozen texts (verbatim, byte-frozen after this commit)

**F2 — P1 block** (per fire; `{reason}` = the trigger's reason string):

```
[DECISION-POINT CHECK] (turn {turn})
trigger reason: {reason}
Re-evaluate the next action using the latest observable state.
```

No recovery strategy, no memory, no history, no task advice.

**F3 — P2 block** (per fire; task-independent, no reason, no cards):

```
[DECISION-POINT REORIENTATION]
Re-evaluate the task goal, the latest observable execution result, and the current scene before choosing the next action.
Do not assume the previous action succeeded.
Base the next primitive on the latest observable evidence rather than blindly continuing the previous plan.
Do not apply any specific recovery strategy unless supported by the current state.
```

**F4 — P3 block** (per fire; `{cards}` = exactly the current `_block()`
card rendering: `i. [id] title / applies_when[:220] / How to apply[:280] /
Falsify[:160]`, unchanged):

```
[DECISION-POINT MEMORY CONTEXT]
These past experiences may or may not be relevant. Judge them against the current observable state.
{cards}
```

No reason anywhere in P3 — not in query (common mode), not in block.

**P4 block** = g0D's existing `_block()` output, unchanged: recall header
with `(turn N; trigger: R)`, fixed framing line, same card rendering.

Note (declared, per-spec): P4−P3 swaps BOTH the title line (recall+reason
vs neutral context) AND the framing line ("judge each card against the
current scene state; ignore what does not apply" vs "may or may not be
relevant. Judge them against the current observable state") — the two
framings are semantically parallel "judge against current state"
instructions, so the contrast isolates reason-presence, not instruction
presence. Both texts are user-frozen; neither may be re-worded.

**Neutral query (§5)** = the frozen `QUERY_MODE=common` composition from
G0: phase + trigger-result action + trigger-result fields + task_language.
Reason logged in the event but never scored, never in the query.

## 3. Event capture (§3)

v1_per_result per-result capture in ALL arms (engineering constant).
Every fire logs an event with: turn, phase, reason, trigger_mode,
query_mode, injection_mode ∈ {none, reason_only, generic_refresh,
memory_only, full}, retrieval_status ∈ {OK, EMPTY, NOT_RUN} (P0/P1/P2 =
NOT_RUN — recorded, never counted as EMPTY), top3 ids, latency (0 for
NOT_RUN), attempt fields. P0 runs full trigger instrumentation.

## 4. Metrics

**Primary (§10)**: SR (valid episodes; infra excluded and counted openly).
Every contrast reports paired wins/losses/ties, McNemar exact p, paired
bootstrap 95% CI (10k, seed 20260920), macro task-cluster CI, and effect
size (diff_micro + flip counts). Direction-finding: point estimates and
flips carry the reading; significance is context, never the sole verdict.

**Recovery (§11)**: POST-INTERVENTION RECOVERY@3 = within ≤3 primitives
after an intervention, observable task/physical progress appears, using
the EXISTING frozen progress definitions (`c2.corrected_moments` /
progress predicates — NO redesign). Also per arm: phase transition within
3 primitives, repeated-failure count, planner turns after intervention,
episode outcome. P0's "intervention" for bookkeeping = its logged fires
(alignment windows identical), so recovery@3 columns are computable for
all five arms.

**Mechanism context (reported, secondary)**: fires/ep, precision, false/ep
(identical trigger ⇒ should be statistically indistinguishable across
arms; gross divergence = implementation contamination → stop and audit).

**Tokens/latency (§16)**: per arm — extra context tokens injected per
episode, planner input tokens per turn, planner calls, wall time, trigger
count.

**relevance@3 (§17)**: recorded for P3/P4 only; explicitly NOT primary
(G0-D showed low rel@3 does not block high SR).

## 5. Primary contrasts (§12) — exactly six, no more

1. REASON EFFECT: P1 − P0
2. GENERIC REFRESH: P2 − P0
3. MEMORY CONTENT: P3 − P0
4. REASON GIVEN MEMORY: P4 − P3
5. MEMORY GIVEN REASON: P4 − P1
6. INTERACTION: (P4 − P3) − (P1 − P0)

The Stage C/G0 total gain is NOT additively decomposed from these.

## 6. Factor-labeling rule (§13)

CLEAR POSITIVE FACTOR requires ALL of: SR ≥ +8pp vs P0 AND ≥ +3 net
paired wins vs P0 AND ≥ 2/3 tasks non-negative. If the top-2 arms sit
within 5pp of each other → label MIXED/INTERACTION, and the ONLY
extension permitted is P0 + those top-2 arms to 60 cells (seeds 1-20);
no new arm, no reworded arm.

## 7. Decision tree (§14) — pre-committed

- **CASE A**: P2 ≈ P3/P4 > P0 → primary gain = generic context refresh;
  next = compare Periodic / Motion-Stuck / Progress triggers under the
  same generic block; paper direction = Decision-Point Context
  Intervention.
- **CASE B**: P3/P4 ≫ P2/P1 → memory content mainline (retrieval/ranking
  work justified).
- **CASE C**: P1 ≈ P4 ≫ P2/P3 → execution-diagnostic cue (reason text)
  is the active ingredient.
- **CASE D**: P4 ≫ all singles → reason×memory interaction; WHEN and WHAT
  cannot be designed independently.
- **CASE E**: all effects small/unstable → G0-D .900 was likely
  small-sample noise; enlarge sample, make NO new claim.

## 8. Infra discipline (§20)

8 workers (429 cap), scheduler resume-safe via completed_keys, service/
network failures NEVER policy fails, auto-retry ≤3 with infra bookkeeping,
no rerun of genuine policy failures, known fingerprints (0-turn /
API connection error) classified per existing protocol. Background logs
on the persistent volume only.

## 9. Regression requirements (§18/§19)

- No frozen surface modified: v1 rules, progress rules, Q0, Q3, Global
  Memory, card texts, `_block()` default output.
- New env knobs ONLY: `RPENT_MEMORY_INJECTION_MODE`
  ∈ {full, memory_only, reason_only, generic_refresh, none} (default
  full = byte-identical historical behavior for every existing mode);
  `RPENT_MEMORY_QUERY_REASON` (0/1) as explicit alias of QUERY_MODE;
  `RPENT_MEMORY_BLOCK_REASON` (0/1, default 1) for P3's neutral header.
- Tests before any episode: (a) all existing G0 audit tests green (v1/
  progress/Q3/motion_stuck semantics unchanged); (b) default no-env run
  reproduces the historical `_block()` string byte-for-byte; (c) each
  mode renders exactly its frozen text above; (d) P0/P1/P2 events carry
  retrieval_status=NOT_RUN. → analysis/stageG05_regression_audit.md,
  committed before the run.

## 10. Outputs (§21)

stageG05_campaign_pause.md ✓(written at pause) · stageG05_reason_flow_audit.md
✓ · this file · stageG05_regression_audit.md · stageG05_runs.csv ·
stageG05_events.jsonl · stageG05_results.md · stageG05_direction_decision.md.
Analyzer = scripts/analyze_memory_stageG05.py (P4 loads g0D rows via the
reuse map; no new stats methodology — reuses analyze_memory_stageG frozen
stats verbatim).

## 11. Stop condition (§23)

After G0.5 completes: STOP. Do NOT auto-resume G1-G4.
stageG05_direction_decision.md goes to the user; the user confirms the
direction before any next stage runs. The 8 in-flight g1 orphans at pause
time finish naturally and are adopted into the CSV (nothing discarded).
