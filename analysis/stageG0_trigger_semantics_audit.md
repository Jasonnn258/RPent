# Stage G0 — Trigger Evaluation Semantics Audit (§A)

_written 2026-09-20, before any G0 run. Source of truth:
`rpent/memory/retrieval.py` @ commit (G0-audit)._

The Stage C comparison v1 vs progress changed **two things at once**:
the trigger RULES (T1-T7 → R1-R5) and the **signal buffering semantics**
(last-result-at-boundary → per-result queue). G0 splits them with the
experimental mode `v1_per_result` (frozen v1 rules + progress buffering).

## Six-way semantics table

| # | dimension | v1 (frozen, TRIGGER=1) | v1_per_result (G0-A) | progress (frozen C2) | T2 periodic | T3 motion_stuck |
|---|---|---|---|---|---|---|
| 1 | result evaluation timing | at TURN BOUNDARY, only the LAST result since previous boundary (`_fresh_result` + `_last_result`); ≤1 evaluation per boundary | at EACH tool result arrival (`_v1pr_observe`) | at EACH tool result arrival (`_progress_observe`) | none (boundary count % N==0) | per move-result window |
| 2 | signal overwrite | any later result overwrites `_last_result` — a hit on A is LOST if B arrives before the boundary, whatever B is | none: hit queued at arrival; first hit wins until flush (single-slot queue) | none: first-hit single-slot queue | n/a | window; queued fire on k-th stalled same-target move |
| 3 | cooldown behavior | `boundaries_since_trigger < 2` → evaluation SKIPPED but `_last_result`/`_fresh_result` untouched → the SAME result can re-fire at a later boundary = **DEFER** | flush-time check → queued fire **DROPPED** (progress semantics) | **DROP** (frozen C2) | boundary check (N=6 > 2 → never binds) | **DROP** at flush |
| 4 | first-primitive gate | YES at boundary (`saw_primitive`) | YES at EVAL time (result arrival) | **NONE** (C2 offline replay had none) | YES (skip ticks before first primitive) | implicit (window only fills from move results) |
| 5 | queue/drop/defer | no queue; cooldown defers; cap drops; empty retrieval drops the fire (pre-G0-E: silently, post-G0-E: logged event, no injection) | queue → flush at next boundary; drop-on-cooldown; drop-at-cap; EMPTY logged no-injection | same | no queue (immediate boundary fire) | queue → flush; drop-on-cooldown; EMPTY logged |
| 6 | max-trigger semantics | `triggers_fired >= 6` → skip evaluation; counter never resets → episode-permanent | same check at FLUSH; queued fire dropped | same at flush | same (fires at boundaries 6,12,…,36 max) | same at flush |

## The two confounds G0 removes

- **A → B (v1_original → v1_per_result)**: rules identical (T1-T7 body is
  VERBATIM — `_trigger_reason` now delegates to `_v1_rules_for(name,
  data, is_error)`, the same function `v1_per_result` calls at result
  arrival). Only buffering differs ⇒ **signal preservation effect**.
  Residual timing differences inherent to the split (recorded, not
  hidden): T6 `tracker.recovery_pending()` and T7 `phase_steps >= 8` are
  read at result-arrival time in B but at boundary time in v1;
  `picks_failed`/`release_open`/`recent_primitives` are identical because
  the trigger result itself is the last update in both.
- **B → C (v1_per_result → progress)**: buffering identical (shared
  `_flush_boundary`, drop-on-cooldown, single-slot queue). Only rule
  content differs (T1-T7 vs R1-R5) ⇒ **progress-rule effect**.

## WHEN/WHAT coupling (§B) and the Q3 state fix (§C)

- Historical query = `observation_summary + " | " + trigger_reason` ⇒
  changing the trigger changed WHAT was retrieved, not only WHEN.
  `RPENT_MEMORY_QUERY_MODE=common` restricts the query to
  {phase, trigger-result action, trigger-result fields, task_language}
  (the observation summary already carries exactly these four); the
  reason stays in the event log but enters NEITHER the lexical query
  text NOR the Q3 `W_SYMPTOM` reason term. `native` = byte-identical
  historical behavior (default).
- `_q3` signature is now explicit — `(q, reason_toks, obs_text, action,
  phase)` — all structured terms from the result the trigger fired on.
  Historical bug: structured rescoring read `self._obs_summary()` /
  `self.last_primitive` / `self.last_phase` (flush-time state = possibly
  a LATER result). Weights/pool size/encoder/phase map untouched.
  **Declared deviation**: progress+Q3 native now uses the queue-time
  phase (was flush-time); affects only future runs — recorded Stage C
  data is not re-run or modified.

## G0-D motion_stuck hardening (baseline correctness, not OURS tuning)

Window entries are `(eef, final_dist_m, target_key)`; `final_dist_m`
progress is compared ONLY within one commanded target (3-decimal
`target_xyz` key). Resets: non-move primitive interleaved, commanded
target changed, `target_xyz` missing (no progress anchor), phase
transition (checked at boundary). No PICK/PLACE/PERCEPTION logic added.
Missing `final_dist_m` (None): cannot verify progress — displacement
evidence alone stands (kept from the frozen DEV calibration).
