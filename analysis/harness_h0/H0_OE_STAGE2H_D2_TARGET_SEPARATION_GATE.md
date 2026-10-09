# H0 · Stage 2H — D2 Decision Time, Same-skill Criterion, and Future Outcome Separation

> 2026-10-09 | **READ-ONLY INDEPENDENT SOURCE REVIEW; NO EXPERIMENT / NO NEW STATISTICS.**
>
> Baseline: `7d988b02c4d78b00d78e9a2a9d6c56576e8445d5`; critical review of `H0_OE_STAGE2G_VANILLA_EPISODE_D2_ASSET_REVIEW.md`.  
> Reviewed tracked sources: `robots/libero/toolkit.py:59-111`, `robots/libero/tools.py:201-275`, `rpent/utils/rtrace.py:67-159`, `scripts/stageR_collect.py:72-169`, `scripts/stageQ_rt.py:223-260`, and frozen `analysis/stageR_prereg.md`.  
> The **reported** local counts (187 original episodes, 24 R1 event episodes, and 6,979 timestamped records) are taken from Stage2G and **not independently re-read or recomputed** in this review. Earlier results and audits remain snapshots and are not overwritten.

## 0. Verdict

**`STAGE2G_D2_ASSET_FINDING_ACCEPTED / TARGET_TIME_SEMANTICS_REVISE / D2_TOOL_VERDICT_CONCURRENT_CRITERION_ONLY / FUTURE_PLANNER_OUTCOME_POLICY_COUPLED / NO_ANALYSIS_AUTHORIZED`**

The discovery of original Planner tool returns is valuable. Three scientific claims in Stage2G need narrowing before a new study:

1. **Same-skill `rtrace` acquisition/terminal measurement is a contemporaneous or retrospective reference, not a time-separated outcome following a D2 decision.** The instrument measures throughout the tool call; its `final_meas` is collected by `rtrace.end_step` **after the primitive function returned but before `dump_state` and `view_driver_state` send the tool result to Planner**, with no intervening action. Thus the `final_meas.t` appearing later than the primitive's Python return is not sufficient for “future retention after Planner saw the flag”.
2. **Vanilla `pi0_pick` does not implement Stage Q/R's hold-through continuation.** It early-returns when its kinematic success predicate is reached. Reusing `stageQ_rt.stable` on the available in-skill `meas` sequence cannot establish the same post-pick hold-horizon contract; its `check_success` shortcut is also not an independent retained-grasp oracle. A study can define an in-skill `ACQ`-like retrospective criterion, but it must NOT silently call it Stage R stable recovery or future post-return retention.
3. **“187 episodes include final success/fail classes” does not prove that archived `pi0_pick.result.success` contains both classes.** Episode-end classification and per-pick tool flag are different variables; their positivity, denominators, alignment and presence remain **UNVERIFIED** until a separately authorized data-value analysis. An artifact-availability audit is not a validated 2x2 evaluation cohort.

**Current useful object: a candidate retrospective same-skill tool-verdict validity audit; scientific novelty remains `NOT_ESTABLISHED`.**

## 1. Actual execution and evidence arrival order

Source-verified path:

```text
Planner calls pi0_pick tool
   |
   +- LiberoToolkit._step: rtrace.begin_step (pre)
   +- LiberoPrimitives.pi0_pick:
   |    multiple Pi0.5 chunk execution calls; rtrace.log_env_call before each chunk
   |    in-skill meas are captured BEFORE the corresponding chunk
   |    pick decides its success flag and RETURNS (may early-stop)
   +- LiberoToolkit._step: result_dict = returned pick dictionary
   +- rtrace.end_step:
   |    extra final_meas of current state, then post snapshot and timestamp
   |    **no new physical action** between pick return and final_meas
   +- dump_state(step_idx, log={command,result,elapsed_s})
   +- view_driver_state(step_idx) produced and returned to Planner
   |
Planner can now make the next decision D2
   |
   +- future Planner primitive(s), according to observed behavior
```

Evidence time is not only a `t` numeric timestamp. Distinguish the physical sampling instant, instrumentation timestamp, **tool-result delivery / Planner-decision availability**, and any later physical transition.

`rtrace` logs wall-clock `time.time()` for each record, but a later wall-clock `final_meas` taken with no environment step is **not a future held-grasp test**. `states.json` stores legal primitive-return fields and state; it is **not demonstrated to contain the entire Planner information history**, e.g. all inspection-tool `segment` outputs or other earlier returned observations/conversation. `view_driver_state` output itself is a legal projection, not a transcript completeness proof.

## 2. Define estimands by decision/time surface

| Identifier | Prediction/signal time | Reference data | What can be claimed | Current qualification |
|---|---|---|---|---|
| **A0: SAME_SKILL_TOOL_VERDICT_CRITERION** | Pick tool return flag at D2 | All in-skill privileged audit measurements incl. final state, from execution that has already occurred | Retrospective concordance/error structure between kinematic tool verdict and in-skill acquisition-like physical criterion | **Potentially identifiable** in original episodes; per-pick class presence / usable paired records NOT verified |
| **A1: POST_RETURN_RETENTION** | D2 after tool result is delivered | Fixed future object-held horizon **after** D2, with predefined observation policy and outcome source | Whether a grasp remains held after the tool returns | **Not established** by in-skill `meas` or `final_meas`; surviving next steps are Planner-selected interventions |
| **B0: OBSERVED_POLICY_FUTURE** | D2 after a failed pick | Future episode result under actually observed Planner actions | Policy-coupled natural-history association/prediction conditional on the observed policy | Limited retrospective estimand if time cuts/outcome validity checked; **not** intrinsic persistence or action-free retention |
| **B1: FIXED_POLICY_COUNTERFACTUAL** | D2 after a failed pick | Future result under a standard, identical specified continuation / intervention | Causal or policy-independent effect of evidence | **Not identifiable** from uncontrolled post-D2 Planner behavior; requires separate design/data and approval |

Source-aware categories:

- `A0` can compare `pi0_pick.result.success` with an explicitly versioned **`IN_SKILL_ACQ_AUDIT`** computed on that skill's `rtrace` checkpoints. It is criterion-concordance, **not prediction into the future**. Labels use privileged sim state for audit only.
- `STABLE_RECOVERY` in Stage Q/R was defined under its own continuation/hold protocol. Vanilla pick can stop on proprio success before any uniform post-success observation window. Do **not** treat this as a drop-in independently measured reference for `A0` or `A1`.
- If `A0` uses a reference whose `check_success` branch is also reflected by a tool's terminal flag, there is a **shared task-predicate dependency**. This must be documented, including subgroup descriptions if separately permitted; no independent physical false-positive/negative guarantees.
- `B0` future outcome is genuinely later in physical time but is a function of the Planner's intervening selected actions. It cannot be used to isolate the persistent-failure state or the effect of switching a future decision policy.

## 3. Data qualification pitfalls before any A0 preregistration

The Stage2G report says 187 episodes have both final `success` and `policy_fail` classifications. This does not establish any of:

1. How many episodes include `pi0_pick` and a full matched privileged in-skill record;
2. Whether `pi0_pick.result.success=True` **and** `False` are both represented among eligible paired calls;
3. Whether `rtrace.meas` and `final_meas` are present and correctly attached for *all* relevant pick calls, not only the 24 R1 selected events;
4. How many pick calls are within each episode, whether calls with `episode_terminated` expose overlapping verdict and reference logic;
5. Whether the tail of the original pick provides a predefined retained-grasp observation interval after the returned verdict (source suggests the answer is NO).

Prior R1 selected cases were explicitly chosen for `pi0_pick success=False` and absence of acquisition over that failed skill; no estimate of classifier discrimination can use only that cohort. A full-corpus data-value qualification would itself change the prior zero-statistics scope and must be independently authorized.

### Mandatory A0 eligibility definitions for a future **candidate** protocol

- Freeze `eligible_episode`, `eligible_pick`, missing/infra/early-terminated behavior, per-episode cluster unit, and a full provenance join by episode/step before outcome inspection.
- Pre-register a **single physical construct** (`IN_SKILL_ACQ_AUDIT` or more limited explicitly defined alternative) with a reproducible provenance path, including the exact `check_success` shortcut, and refrain from claiming time-delayed independent stability.
- Distinguish tool flag vs physical reference vs terminal task status; never use `result.success` to build the privileged reference or use privileged reference to reconstruct a decision-time proxy.
- Clearly state `ACQ_like` is computed on original vanilla in-skill checkpoints, not identical to the Stage R repeated-`S_pre` frozen STABLE protocol.
- Account for selection of 3 tasks, 121–190 seeds, stop-on-quota and run completion statuses; “187 episodes” is a bounded collection process, not a random universal LIBERO sample.
- Declare retrospective exploratory status and that prior analysis of Stage R outcomes is public. No post-hoc thresholds or nominal independent held-out test claims.

## 4. Decision gate and contribution assessment

**A0 retrospective concordance** could be worthwhile if the practical question is “When the current Planner receives `pick.success`, how often does that agree with the actual *in-skill* acquisition criterion?”. This helps quantify an already identified evidence-interface mismatch in this specific RPent stack. It does not introduce a new statistical estimator, new controller, or validated repair method.

**A1/B1 (post-return hold and fixed intervention)** require a new, valid reference/observation design; the current `final_meas` cannot meet that claim. Original episode D2 returns can pair with later states for **B0 natural-history description**, but continuation decisions depend on the tool result, so it is not an independent hold-validation target.

Gate table:

| Gate | Result | Action |
|---|---|---|
| G-D2 source/return provenance | PASS at source level | Preserve reported Stage2G finding |
| G-TIME physical future after Planner return | FAIL for same-skill `final_meas`; CONDITIONAL for next actions | Ban “future after verdict” A0 title |
| G-CRITERION STABLE semantic equivalence | FAIL without Stage Q/R hold continuation | Rename to in-skill ACQ-like / new research-only version |
| G-COHORT binary class / joined record eligibility | NOT VERIFIED on all-pick population | **No numeric A0 performance claim** |
| G-DEPENDENCE episode termination/flag | SHARED CONTRACT RISK | Cannot label independent FPR |
| G-RUNTIME/EVO | NOT AUTHORIZED | No new execution authorization |

**Recommendation:** perform one **structure-only all-corpus per-pick provenance and eligibility review** before approving any new A0 numeric preregistration. That review should not inspect `result.success` **values** or raw outcome prevalences under the current scope; it may inspect action/measurement key presence, event/skill alignment, joint-record availability and time ordering. If it finds missing or non-alignable records, STOP. If complete, only then decide whether to fund the modest, retrospective `A0` study. If no distinct method/mechanism follows, closing H0 after an explicit negative novelty verdict remains scientifically sound.

## 5. Authorization and immutable history

This file is an append-only scientific-review increment. No original `H0_OE_STAGE2G_VANILLA_EPISODE_D2_ASSET_REVIEW.md` text altered, and no prior Stage R/Stage 2C frozen assets, Stage 2D analysis scripts or results, runtime/tool interfaces, inference, simulator, rollout, model training, or skill evolution were changed.  
Existing Stage R §36 Hard STOP, S1-DEV0 ON_HOLD, `E14/A1/P5/U4` and `runtime_evolution_eligibility=NOT_AUTHORIZED` remain.

**Final: `STAGE2H_SOURCE_REVIEW_COMPLETE / A0_CONCORDANCE_ONLY / A1_POST_RETURN_RETENTION_UNSUPPORTED / B0_POLICY_COUPLED / A0_COHORT_QUALIFICATION_PENDING / NO_NEW_EXECUTION_AUTHORIZED`.**
