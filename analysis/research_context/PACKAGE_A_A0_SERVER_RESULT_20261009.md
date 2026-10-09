# Research Package A — A0 Server Result and Interpretation (2026-10-09)

> **Source status: USER-REPORTED SERVER RESULT**, subsequently cross-checked against the committed `research_package_a.py` metric definitions and frozen Stage2J-v2 contract; **this report does not independently access the private server files**.  
> Run: `bash analysis/research_context/run_package_a.sh` on `/workspace/yjx/workspace/RPent`; checked-out commit shown by the user's `git pull`: `30f2a1e`.  
> Protocol ID: `RPENT-PACKAGE-A-STAGE2J-V2-EERD-V01-20261009`.  
> Frozen execution contract: `analysis/harness_h0/H0_OE_STAGE2J_FROZEN_V2_PACKAGE_A.md`.  
> **The original results and pre-outcome Python code must remain immutable for audit**. All numerics below are reported from the user's terminal, including already-computed episode-cluster bootstrap intervals. No raw trajectories, credentials, private episode locations or audit-only labels are uploaded into Git.

## 1. Execution gate and data readiness

| Item | Reported actual result |
|---|---|
| Synthetic regression suite | `3 tests OK`, 0.073 sec |
| Git checkout | fast-forward `304be11..30f2a1e`; executable at pre-run HEAD `30f2a1e` |
| Stage1 schema gate | **PASS** |
| Original episodes / episodes with pick | 187 / 186 |
| Pick calls / eligible picks | 235 / 235 |
| Pick chunk actions / valid measurement points | 2,859 / 3,094 (= chunks + one terminal per call) |
| A0 outcome gate | **PASS** |
| PRIMARY = eligible picks with `result.libero_terminated=False` | **206** |
| Terminal-related excluded from PRIMARY | 29 (=235−206); they remain part of original A data frame |
| Reference UNKNOWN | **0** on eligible picks; 206/206 PRIMARY decidable |
| Frozen R1 B QA | **PASS**, 24 failure events, 480 trials, zero reported problems |

**EERD internal artifact implication**: the approved executable writes A online/audit/metadata views and B audit/metadata views into gitignored `artifacts/research_package_a/` only when applicable gates pass; it also generates `EERD_DATA_CARD.md`. Thus the user's run reports that materialization code completed; this chat did **not** inspect the server files or their row-level hashes independently. The eight G-QA gates are partly checked by the current executable but not all audited via standalone exhaustive checks; avoid claiming general-purpose dataset publication.

## 2. Corrected confusion matrix (CRITICAL: raw JSON key naming trap)

The executable's `stats()` serializes `(tool_flag, reference_state)` keys, e.g. `false_positive` means **flag=False, reference=POSITIVE**, NOT conventional false positive; similarly `true_negative` means **flag=True, reference=NEGATIVE**, which actually **is** conventional false positive.

Correct meaning, reference=`IN_SKILL_ACQ_FGONLY_V1` (within-skill pose following only):

| Original tool flag | Reference POSITIVE | Reference NEGATIVE | Row total |
|---|---:|---:|---:|
| `result.success=True` | **101** (conventional TP) | **2** (conventional FP) | 103 |
| `result.success=False` | **56** (conventional FN) | **47** (conventional TN) | 103 |
| Column total | 157 | 49 | **206** |

**Immutable raw mappings**:
- raw `table.true_positive = 101` → TP;
- raw `table.true_negative = 2` → **FP**;
- raw `table.false_positive = 56` → **FN**;
- raw `table.false_negative = 47` → TN.

All follow-up research must use the corrected table or explicitly refer to `flag_reference` coordinate keys. Original `a0_result.json` is preserved and must **not** be modified in place.

## 3. Primary A0 descriptive results

| Quantity | User-reported estimate | Episode-cluster bootstrap 95% (10,000) | Meaning |
|---|---:|---|---|
| `R_accept = P(FGONLY NEGATIVE \| success=True)` | **2/103 = 1.94%** | **0–4.85%** | Tool reports success but within-skill FG proxy never confirms |
| `R_miss = P(FGONLY POSITIVE \| success=False)` | **56/103 = 54.37%** | **45.26–64.29%** | Tool reports failure despite an in-skill FG proxy confirmation |
| Raw tool/reference concordance | **148/206 = 71.84%** | **65.88–77.56%** | Not physical task success accuracy |
| Always-True FGONLY baseline | **157/206 = 76.21%** | not supplied | More raw agreement here than the real tool by **4.37 percentage points** |
| Always-False FGONLY baseline | **49/206 = 23.79%** | not supplied | Class prevalence is highly asymmetric in reference |
| Cohen's κ | **0.43689** | not supplied | Descriptive prevalence-adjusted concordance |
| Tool-flag TRUE / FALSE counts | 103 / 103 | — | Flag marginal itself is balanced; proxy prevalence is not |
| FGONLY POSITIVE / NEGATIVE | 157 / 49 | — | Within-skill proxy positivity 76.21% |
| Wilson naive interval (NOT cluster robust) | Concordance 65.35–77.54% | — | Cluster-bootstrap interval should be preferred |

Derived directly from the user-reported counts (descriptive only):
- `P(flag=True | FGONLY POSITIVE) = 101/157 = 64.33%` (sensitivity to this proxy);
- `P(flag=False | FGONLY NEGATIVE) = 47/49 = 95.92%` (specificity to this proxy);
- `P(FGONLY POSITIVE | flag=True) = 101/103 = 98.06%`;
- `P(FGONLY NEGATIVE | flag=False) = 47/103 = 45.63%`.
- This shows **relative conservatism of the original kinematic pick-success heuristic versus the FGONLY pose-following reference**; it does **not** establish 56 actually grasped-and-held physical successes. Original tool checks descent ≥0.10m, post-min ascent ≥0.05m and grip gap <0.06, while FGONLY checks target lift ≥0.03m and XY EEF-follow ≤0.10m. The two targets differ mechanically and temporally.

### Critical interpretation boundaries

1. **Within-skill existence ≠ return-time holding**: FGONLY POSITIVE means there was **at least one sampled moment** satisfying the object pose-following proxy; it does not prove the object was still acquired when `result.success` was delivered, nor that it stayed held after Planner next acted. Hence the 56 mismatches do not yet justify automatically treating `success=False` as success or skipping recovery.
2. **Cost-asymmetric decision**: always-positive wins *raw concordance*, yet would have accepted 49 reference negatives; never use it as a proposed runtime policy. Its only legitimate role is a majority-class descriptive control.
3. **No prospective causal benefit**: collected pick results are observational, multiple picks share episodes, 3 tasks and quota stopping limit external validity. P1 requires independently evaluated D2 outcome windows, verification action costs and equal-budget strategy comparisons.
4. **No statistical generalization claim**: cluster bootstrap measures within-frame uncertainty, not independent tasks or unbiased sampling from all LIBERO.
5. **No silent metric substitution**: do not re-run A0 with new thresholds or reinterpret the reported 71.84% as an overall grasp success rate. Any corrected *presentation* should leave the original sealed result untouched.

## 4. Immediate research consequence for P1 (hypothesis, NOT established)

Prioritize the **false-negative-side disagreement as a verification-decision target**:

> For a `pi0_pick.success=False` return, can a legal, low-cost D2 verification action distinguish (i) transient in-skill object lift without retained grasp, (ii) genuine retained acquisition, and (iii) false/no acquisition, better than blind retry under equal total action/observation budget?

This directly uses the measured **56/103 conditional discrepancy** as an observed motivation, **not as expected intervention effect or power-analysis effect size**. Future C cohort must record **post-return, post-verification horizon** and a genuinely independent evaluation contract; R1 reconstructed failure events do not supply those future outcomes.

Potential strong baselines: immediate retry, always verify, fixed/scheduled verify, tool-failure heuristic, static calibrated verifier, random-budget-matched verify. Measure task completion/false completion, unnecessary retry, verification cost, abstention/coverage, and heldout task generalization. **All new sim/rollout or runtime intervention still L2-HOLD**; Research Package A did not grant those powers.

## 5. Current status and next actions

- **GO**: Research Package A Stage1 structure, A0 outcome, and B frozen trial basic QA **reported PASS**; EERD v0.1 **internal baseline artifacts produced by completed pipeline**, subject to fuller independent file/QA inspection before publication.
- **STOP**: No need to rerun the same A0 descriptive statistics to chase a different number. Do not edit sealed A0 code merely to fix presentation labels.
- **HOLD**: Public benchmark release, online consumption of research truth, L2 C cohort simulation or verification/recovery wiring.
- **NEXT under already approved L1**: safe audit of exported file counts, source hashes, view separation and A/B leak-free grouping; reclassify Package A as fully closed only when those are confirmed. A report-only display correction may be added as a separate postprocessing tool without changing the sealed source or metrics.
- **FUTURE L2**: prospective D2 verification/cost study requires a single new bounded protocol, budget and user approval.

**Status: `PACKAGE_A_A0_SERVER_PASS / MISMATCH_CORRECTED_SEMANTICS / EERD_INTERNAL_DATA_REPORTED_CREATED / FULL_DATASET_QA_PENDING / P1_FUTURE_L2_HOLD`.**
