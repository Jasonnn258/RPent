# H0 · Stage 2F Decision Surface & Future-Horizon Consistency Review

> 2026-10-09 | **READ-ONLY SOURCE/METHOD REVIEW · NO OUTCOME COMPUTATION**  
> Reviewed source branch head before this report: `5adb5293085e8e969fa015a9171849fef0ce1a19`.  
> This is an **append-only independent review** of `H0_OE_STAGE2E_PROXY_TIMELINE_GATE.md`, not a change to its historical findings or an amendment to frozen `H0-OE-STAGE2C-20261009-V1`.  
> Sources: `robots/libero/toolkit.py:41-110`, `robots/libero/tools.py:151-166,201-270,904-949,1604-1650`, `scripts/stageP_rt.py:172-221`, `scripts/stageQ_rt.py:186-221,223-302`, `scripts/stageR_rt.py:199-223`, `scripts/stageR1_run.py:137-157,164-226` and the Stage 2E Gate report.  
> **Evidence distinction**: source-level structural facts are verified from GitHub; Stage 2E's `484` private-checkpoint findings are **taken as reported in its document**, not independently rerun here. No private CPS values or outcome statistics were accessed.

## 0. Executive verdict

**STAGE2E_GATE_REQUIRES_QUALIFICATION_BEFORE_ANY_NUMERIC_PROXY_STUDY.**

Three central reasons:

1. **The chosen `candidate-post` cut is not a current Planner decision boundary.** Source shows that the normal `LiberoToolkit._step()` calls a primitive until it returns, then calls `dump_state` and `view_driver_state` to deliver the new state to the Planner. The Stage R `candidate-post` checkpoint is recorded inside an experiment-specific candidate + hold-through procedure. Its limited proprioception may be physically obtainable to the executor, but no current production Planner decision occurs there. **Therefore the proposed two-point proxy is an experimental early-execution feature, not an empirically recorded Planner-decision proxy.**
2. **The documented continuation length has an off-by-one inference.** With `cps = [base, post, post, cont_1, ..., cont_N, tail]`, `L=N+4`; the Stage 2E report states `L_min=11` (NATURAL), so the *reported* minimum continuation count is **N=7**, rather than the reported `N∈[8,23]`. Maximum `L=27` implies `N=23`. The unique continuation checkpoints occupy zero-based indices **3..N+2**; tail is **N+3**. The proposed `index 3..N` must not be executed as written. These are arithmetic deductions from the reported lengths, not new data measurements.
3. **Continuation length can be outcome-related**. `run_continuation_hold()` latches its proprio success without breaking, **but does break** on `episode_terminated` or `episode_truncated` (`stageQ_rt.py:186-221`). The sentence “hold-through guarantees future-window length is unaffected by success” is too strong. A completed shorter trajectory can be the result of task termination; shorter available follow-up does not automatically equal physical failure or missing-at-random censoring.

Consequently, the Stage 2E structural conclusion should be read as:
`RETROSPECTIVE_EARLY_EXECUTION_PROXY_STRUCTURE_POSSIBLE / TRUE_PLANNER_DECISION_PROXY_NOT_EVALUABLE_FROM_THESE_CPS / INDEPENDENT_GENERALIZATION_NOT_ESTABLISHED`.

## 1. Decision surfaces: identify the actor, time, and actually delivered information

| Surface | Real source/interface | What exists | Valid claim |
|---|---|---|---|
| **D0 — pre-primitive Planner** | `LiberoToolkit._step` before calling `self._primitives.<name>` | Previously completed tool state/images and command arguments | Existing Planner-visible decision surface, but no current Stage R-specific future outcome pairing established |
| **D1 — candidate-post, internal executor** | Stage R `exec_from_current`: `execute_chunk` → `checkpoint(post)` → `run_continuation_hold` | Experiment-internal data at a physical chunk boundary; Stage2E reported `eef/grip` present | A *hypothetical* intra-skill decision/observation cut, **not** current Planner-visible delivery |
| **D2 — primitive-return Planner** | `_step` waits for `pi0_pick` to return, then `dump_state` / `view_driver_state` | Actual tool output including success/diagnostics, state and images | Actual Planner decision surface, but the Stage R CPS do not persist equivalent `pi0_pick` output or a fresh post-return hold window |
| **D3 — simulator audit observer** | `sim_measurement`, `check_success`, Stage Q/R CPS | Privileged object/goal truth | Offline target/audit only; prohibited for Runtime/Evolution decision-time input |

**Consequence:** separating legal *field types* is necessary but insufficient for a claim that “the Planner could have made this prediction at the reported cut”. One must also establish **delivery timing and actor**. `grip` and `eef` may be legal proprioception in principle, yet those particular CPS records were not presented to the Planner as a completed tool response at D1.

Two defensible study names:
- `EXPERIMENTAL_INTRA_SKILL_KINEMATIC_PROXY` for D1, **sim-only, never call it observed Planner evidence**.
- `PLANNER_RETURN_OUTCOME_EVIDENCE` for D2, **currently no matched successor labels / exact return flags in the audited Stage R assets**; requires separately verified data or future instrumentation.

## 2. Source-consistent CPS indexing: prevent silent target/window errors

From `stageQ_rt.exec_from_current`:

```text
index 0        base        (before candidate)
index 1        post        (after candidate)
index 2        post        (replicate begins at same post)
index 3        cont_1      (first new continuation chunk)
...
index N+2      cont_N
index N+3      tail        (post-loop zero-action remeasurement)
L = N + 4
N = L - 4
```

The Stage 2E source report says 484 records, `L_min=11`, `L_max=27`, no empty continuation. Therefore, **conditional on that report**, `N∈[7,23]`; even if the shortest recorded NATURAL trial is excluded from the R1 SAME/RESAMPLE analysis, **arm-specific N minimum must be stated explicitly** before choosing fixed H. Stage2E separately reports SAME minimum `L=17` (N=13) and RESAMPLE minimum `L=18` (N=14); these are *reported* structure counts, not independently audited here.

For a fixed relative horizon `H≥1`, the actual future checkpoint is `cps[2+H]`, defined only if `N≥H`. A strict fixed-H window is `cps[3:3+H]` in Python slicing, which excludes the duplicated post at index 2 and the tail at `N+3`.  
No “T seconds” claim is supported by the current CPS. For varying H and early stop, denominators and censoring must be declared before evaluation.

The Stage2E phrase “tail is zero-information” applies to **the audited object/pose/check-success fields** and the zero-action source path; do not assert that every serialized bookkeeping field has identical bytes without checking.

## 3. Outcome-related stopping and outcome construct choice

In `run_continuation_hold`, two early-stop paths can shorten the follow-up despite removal of early-stop on the kinematic proxy:
- `episode_terminated` — may be associated with actual task success;
- `episode_truncated` — execution-limit/termination condition and must not be conflated with failed grasp.

The originally suggested `Y_FUTURE_FG_CONFIRM` (“any confirmation in indices 3..N”) measures **any future observed confirmation in a variable-length period**, not a fixed-horizon risk. A different length can change its probability even without any real competence difference.

Distinguish future endpoints before any new preregistration:
- **future task predicate at fixed H**: audit-only `check_success` at `cps[2+H]` *where observed*; task satisfaction, not retained grasp;
- **future physical hold across fixed H**: prespecified relation between object and EEF in future `cps[3:3+H]`, independent of a single `any(check_success)` shortcut; retained-grasp construct, not task completion;
- **ever confirmed before stop**: varying-window descriptive outcome, never pass off as fixed-H retention.

For insufficient `N`, report **termination type + horizon observability** separately. Do not set outcome=0, condition away successful early termination, or forward-fill post-terminal states. A legitimate fixed-H analysis might choose a horizon whose availability was established in a structure-only pass, but it still requires an independently frozen estimand and the original retrospective/nonblind disclosure.

**Reference construction nuance:** a future label may legitimately use a *frozen pre-action object-position reference* as a physical coordinate baseline, provided this privileged baseline is confined to the research target and never leaks into the proxy; however it then needs to be described as a *future-measured target relative to a predeclared reference*, not “label uses only future raw values”. Avoid a blanket ban that makes displacement physically undefined.

## 4. The proposed two-point proxy cannot be identified as original pick success

The Stage2E candidate:
`accept := (base_z - post_z ≥ d*) AND (grip_post < 0.06)`.

This is a **descent/closure-at-candidate-post** indicator. The actual `pi0_pick` success in `robots/libero/tools.py:201-270` additionally requires **descent then ascent**, a maintained post-minimum peak, and its original pick entry state. Choosing `d*=0.05` by borrowing the pick's `lift_thresh=0.05` changes that threshold's physical meaning (lift vs descent). Such a proxy may still have a predictive association with later success, but it cannot be named `pick_success`, `grasp_accepted`, or an implementation-equivalent pick verifier.

Suggested narrow name: `D1_DESCENT_CLOSURE_EARLY_FEATURE`. Define it as **feature**, not a success verdict, unless a separately justified decision semantics is frozen. Avoid tuning `d*` on the same published R1 outcomes.

## 5. Revised research prioritization and STOP/GO rules

**Priority 1: Resolve claim eligibility (zero statistics, no rollout).**

| Gate | What to establish | Current status |
|---|---|---|
| **S — Decision surface** | Is the state actually delivered to Planner at the cut? | D1: **NO**; D2: real boundary, but not paired with Stage R future target |
| **H — Horizon** | Exact H/index and termination/censoring semantics | Off-by-one and stopping claim require correction |
| **P — Proxy semantics** | Is the feature a genuine returned tool verdict or a research-only motion feature? | **Research-only**, original pick flag unavailable/nonequivalent |
| **Y — Outcome construct** | Fixed-H success vs stable hold vs any-confirmed clearly separated | **UNFROZEN**, requires prospective choice prior to any new numerical analysis |
| **V — Validation and provenance** | No future input leakage, event-held-out, existing data disclosed retrospective; no actual online claim | Conditional retrospective at D1; independent generalization **not established** |

**Priority 2: Only if a future user-approved study values a narrow descriptive result**, formulate a new, separately frozen D1 *early-execution* proxy target with fixed-H/censor rules and event-level evaluation. Otherwise archive D1, because it is not yet directly actionable by the present Planner and may only add another stack-specific retrospective descriptive number.

**Priority 3: If the research goal is a genuine Embodied Harness decision claim**, first design a future D2 instrumented prospective data cohort that logs the exact Planner-visible tool-return state and a precommitted future window. Such collection or runtime interface changes exceed present Stage R §36 and require explicit fresh approval. Do not claim that a good D1 number justifies changing the runtime.

## 6. Integrity and authorization

- All conclusions here are source/document review and arithmetic deductions. No private checkpoint scan, statistics, newly fitted models, experimental execution, policy/controller edit, skill evolution or training.
- Frozen Stage R `E14/A1/P5/U4` remains untouched; Stage2C protocol and Stage2D results untouched; Stage R §36 Hard STOP and S1-DEV0 ON_HOLD remain.
- Stage2E `H0_OE_STAGE2E_PROXY_TIMELINE_GATE.md` remains a historical snapshot; this addendum clarifies three overclaims and one interval/physical-semantics error without modifying it.
- Novel algorithm claim remains `NOT_ESTABLISHED`; `causal_grade=UNIDENTIFIED`; `runtime_evolution_eligibility=NOT_AUTHORIZED`.

**Final verdict: `STAGE2F_SOURCE_REVIEW_COMPLETE / D1_EARLY_PROXY_ONLY / D2_REAL_PLANNER_CLAIM_HOLD / FUTURE_HORIZON_SPEC_UNFROZEN / NO_NEW_EXECUTION_AUTHORIZED`.**
