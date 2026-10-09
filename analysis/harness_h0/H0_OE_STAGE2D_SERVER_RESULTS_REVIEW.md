# H0 · Stage 2D Server-Returned Results Review

> 2026-10-09 · **READ-ONLY SCIENTIFIC REVIEW OF USER-RETURNED TERMINAL OUTPUT**  
> Protocol: `H0-OE-STAGE2C-20261009-V1` (frozen file Git blob `97dc0bc93bae857620554a7c2571c5b0b55b5528`).  
> Analysis script Git blob: `e8916f3f58084f186715a7de00cd450f060592c7`.  
> Source data commit: `10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a`.  
> User-reported server execution: `research/pre-ovpm-20260905`, fast-forward to `a1a78f5`.  
> **Evidence status: SERVER_RETURNED_PREFLIGHT_PASS / SERVER_RETURNED_ANALYSIS_PASS / MATCHES_PINNED_GITHUB_RESULTS.** This review did not access the server or independently attest the saved `/tmp/` result file.

## 1. Execution and provenance review

The user pasted the actual server terminal transcript for the Runbook's two-phase procedure: six synthetic `unittest` cases all `ok`; `--preflight` returned `preflight=PASS`, `input_hashes=PASS_ALL_PINNED_BLOBS`, cohort 24, and trial counts SAME 192 / RESAMPLE 192 / NATURAL 96; `--run` returned `APPROVED_OFFLINE_RUN` with the same pinned protocol and script blob. Server environment as **reported**: CPython 3.11.16, Linux 5.15.0-88-generic x86_64 / glibc 2.35, Python stdlib `random.Random` / MT19937.

Compared with `H0_OE_STAGE2D_PINNED_GITHUB_RESULTS.md` (Python 3.13.5 pure-function reproduction), primary Brier values, paired delta, descriptive percentile endpoints, task distribution, OE1a contract disagreement, OE3a exploratory results, boundary fold counts, and the negative authorization flags agree at the printed precision. This closes the **user-returned server-preflight pending item** from the prior report; that prior dated report remains an accurate snapshot of what had **not yet** run when written. It must not be edited retroactively.

**Scope of confirmation:** received stdout and GitHub source were reviewed. The saved local `/tmp/h0_oe_stage2d_approved_result.json` is not itself copied, signed, hashed, or independently inspected here. No additional execution or formal independent server audit is claimed.

## 2. Frozen primary OE2a — SAME, k=2 -> Y3

| Item | Returned value |
|---|---:|
| Eligible event N | **12 / 24** (the frozen reporting minimum, no margin) |
| Task counts | t3=1, t5=5, t9=6 |
| LOEO M0 mean Brier | 0.1608288063980685 |
| LOEO M1 mean Brier | 0.14791666666666667 |
| Mean paired difference (M0−M1) | **+0.01291213973140185** |
| 10,000 fixed-OOF paired event-bootstrap **descriptive** interval | **[-0.06156028368794325, +0.06409826514637089]** |
| M1 SAME boundary-grid folds | 0 |
| Frozen status string | `M1_LOWER_OBSERVED_BRIER_IN_RETROSPECTIVE_COHORT` |

Interpretation: a **small favorable observed retrospective difference** for M1, with a broad descriptive interval crossing zero. The pinned GitHub report additionally recorded only 2/12 third-attempt stable successes in this risk set (not independently re-counted in this server JSON). The LOEO folds overlap in 23/24 training events; this fixed-OOF bootstrap does not refit parameters, has no nominal frequentist coverage guarantee, and is not a confirmatory hypothesis test. This is an analysis freeze written after Stage R aggregate results had already been publicized, **not** an outcome-blind prospective registration or an independent external test. These observations do **not** establish model superiority, an optimal retry count, M2 sequence dependence, or N1 novel algorithm performance.

## 3. Secondary / exploratory — not independent evidence of novelty

**OE1a:** SAME acquisition=0.6458333333, stable=0.3020833333, same-source contract disagreement=0.34375, conditional disagreement given acquisition=0.5322580645. RESAMPLE acquisition=0.6979166667, stable=0.3229166667, same-source disagreement=0.375, conditional=0.5373134328. `STABLE => ACQUISITION` is part of the frozen implementation; these paired same-source labels are **not** independent physical false-acceptance ground truth.

**OE3a paired mean Brier deltas, M0−M1:**

| Arm | k=0 | k=1 | k=2 | k=3 |
|---|---:|---:|---:|---:|
| SAME | +0.00406 (N24) | -0.01851 (N18) | +0.01291 (N12, primary) | +0.03727 (N10) |
| RESAMPLE | +0.00129 (N24) | -0.01114 (N20) | -0.04844 (N13) | +0.07065 (N7) |

Direction varies by arm and selected failure prefix; conditioning changes which events remain at risk. Do not choose a favorable k after observing these values, or interpret the contrasts as continuous-in-time physical degradation. Trial execution independently reconstructs `S_pre` each time. No valid inference to natural sequential `S_post` retries.

## 4. Scientific gate

- `scientific_scope=RETROSPECTIVE_INTERNAL_VALIDATION_ONLY`
- `causal_grade=UNIDENTIFIED`
- `oe1b_independent_reference=NOT_IDENTIFIABLE_ON_AUDITED_SOURCES`
- `novel_algorithm_established=false`
- `runtime_evolution_eligibility=NOT_AUTHORIZED`
- Stage R §36 Hard STOP unchanged; S1-DEV0 ON_HOLD unchanged.

**Verdict: STAGE2D_SERVER_OUTPUT_REVIEWED / OBSERVED_WEAK_RETROSPECTIVE_SIGNAL / SCIENTIFIC_GO_NOT_ESTABLISHED / NO_RUNTIME_OR_EVOLUTION_AUTHORIZATION.**

The outcome estimates are computed from simulator-side `stable/acquisition` truth. They do not show that a runtime agent could legally observe the same prefix or that a future independent reference outcome exists. Thus a better simulated Brier score alone would not make this model consumable by a Runtime or Evolution Gate.

## 5. Next research question (proposal only; no execution authorization)

Prioritize **evidence eligibility and identifiability** over fitting another small-sample predictor to the same 24 published events:

1. Perform a source-level, read-only audit of the existing Planner-visible RGB / proprioception / tool-history surfaces versus Stage Q/R simulator audit-truth measurements. For each potential outcome proxy, record physical observation time, evidence arrival time, visibility, dependencies, and what it can actually attest.
2. Check whether any existing non-privileged, decision-time proxy has a **future, time-separated reference** that is not a copy/relabeling of the same simulator contract. If absent, mark independent calibration `NOT_IDENTIFIABLE`; do not fabricate proxy values or reuse STABLE as both acceptance and truth.
3. Specify the minimal **new** evaluation design needed for a future independently approved phase, separately addressing state reconstruction validity, within-event dependence, task mix, event-level sample size, and deployment transfer. Any newly collected data, experiment, training, controller/verifier/recovery implementation, or unfreezing Stage R §36 requires separate authorization.

No Stage2C frozen methods, Stage R data/assets, scripts, S1, VLA or control code were changed in producing this review. This file is an append-only interpretation of the returned terminal output; it is not a new experiment, a revised preregistration, or permission for execution.
