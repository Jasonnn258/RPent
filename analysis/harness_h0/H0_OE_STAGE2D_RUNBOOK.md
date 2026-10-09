# H0 Direction 1 · Stage 2D Authorized Offline Analysis Runbook

> 2026-10-09 | **User approved Stage 2D** by answering “授权” to the prior explicit Stage 2D approval request. Authorization includes restricted **existing-data offline analysis**, not new environment/robot rollouts, simulator boot, training, skill editing, or online controller integration.
>
> Stage 2C frozen v1 remains unchanged: `H0_OE_STAGE2C_FROZEN_PREREG.md`, protocol Git blob `97dc0bc93bae857620554a7c2571c5b0b55b5528` at creation commit `118d98ccc774ba63f6ad06ab6cd69df8697195b3`.
>
> **Current stage status: ANALYZER_IMPLEMENTED_AND_SYNTHETIC_QA_PASSED / SERVER_PREFLIGHT_AND_REAL_RESULT_PENDING.** No one has yet executed this analyzer against the user’s server Stage R outcomes in the current conversation. Do not mark statistical results as available.

## 1. Artifacts locked for the authorized run

| Item | Path | Git blob SHA-1 |
|---|---|---|
| Offline analyzer | `scripts/h0_oe_stage2d_offline.py` | `e8916f3f58084f186715a7de00cd450f060592c7` |
| Synthetic-only regressions | `scripts/test_h0_oe_stage2d_offline.py` | `824c96be60038ee2a06f427646e653b2069c8794` |
| Frozen protocol | `analysis/harness_h0/H0_OE_STAGE2C_FROZEN_PREREG.md` | `97dc0bc93bae857620554a7c2571c5b0b55b5528` |
| Frozen source baseline | Git commit | `10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a` |

The analyzer is standard-library Python only; it imports no RPent runtime/VLA/Libero modules, invokes only `git rev-parse --verify` for read-only provenance, and prints JSON on stdout. It **does not modify any experimental file**.

## 2. Server command — safe two-phase execution

**Precondition:** user must use the real RPent clone that owns the pinned Git objects; do not copy around/replace CSV files merely to satisfy a hash.

```bash
cd /workspace/yjx/workspace/RPent

# If the auto-sync has not brought the approved analyzer commit, fast-forward this research branch.
git status -sb
git branch --show-current
git pull --ff-only origin research/pre-ovpm-20260905

# Synthetic-only QA (zero Stage R outcome access).
python3 -m unittest -v scripts/test_h0_oe_stage2d_offline.py

# Phase A: hashes + event/arm/trial structural integrity ONLY.
python3 scripts/h0_oe_stage2d_offline.py \
  --repo . \
  --preflight \
  --expected-script-blob e8916f3f58084f186715a7de00cd450f060592c7

# Phase B: only when Phase A emitted preflight=PASS and all synthetic tests passed.
# Authorized pure offline result calculation; no simulation/VLA.
set -o pipefail
python3 scripts/h0_oe_stage2d_offline.py \
  --repo . \
  --run \
  --expected-script-blob e8916f3f58084f186715a7de00cd450f060592c7 \
  | tee /tmp/h0_oe_stage2d_approved_result.json
```

The analysis result is stored **outside the repository**, at `/tmp/h0_oe_stage2d_approved_result.json`, for review. Avoid `git add .`: untracked Stage R assets and backup files must not be included. If the branch shown by `git branch --show-current` is **not** `research/pre-ovpm-20260905`, **STOP** rather than pull into an unexpected branch. Do not bypass `STOP_*` statuses by downloading/overwriting pinned data, changing SHA constants, or ignoring failure output.

The preflight verifies: checked script Git blob, pinned frozen protocol blob, pinned Git source commit-to-file associations, current local file bytes as Git blobs, manifest selection of exactly 24 R1 events, and 192/192/96 trial key integrity. It does **not** use the extra four DEV checkpoint entries for outcome modeling.

## 3. Results interpretation

Primary:`primary_oe2a` includes eligible event N, task counts, LOEO mean Brier(M0/M1), and `mean_delta_m0_minus_m1`. Positive delta means M1 lower **observed retrospective** loss, not confirmed new algorithm or causal time persistence. When `eligible_event_n < 12`, report `INCONCLUSIVE_DESCRIPTIVE_ONLY_SMALL_RISK_SET` and **no bootstrap interval**.

`descriptive_bootstrap_percentile_interval` is deliberately **not** a formal 95% coverage claim: LOEO fits share training events; resampling their fixed paired losses does not refit model parameters. This analysis is retrospective internal validation using already published Stage R data, not a fresh blind test.

`secondary_oe1a` = same-source ACQ/STABLE contract disagreement, not independent physical false-positive rate. `exploratory_oe3a` = other failed prefixes/RESAMPLE, not a second independent confirmatory claim. `novel_algorithm_established=false` and `runtime_evolution_eligibility=NOT_AUTHORIZED` are invariant regardless of predictive performance.

## 4. Stop discipline

- Any mismatch of protocol/blob/data/script SHA or missing pinned Git commit -> **STOP**, do not recompute with newer data.
- Missing/duplicate R1 event-arm-trial keys, invalid success labels or contract nesting -> **STOP** and inspect without modifying source data.
- M1 fit failure -> **STOP / M1_FIT_FAILED**, do not broaden grid after observing performance.
- The user's returned results should be reviewed before generating an official results report or changing research direction. Do not claim successful execution while only code and test artifacts exist.
- No Stage R §36 or S1 DEV0 permission changes. No rollout, env boot, training, Recovery/Verifier or skill evolution execution.

## 5. Synthetic-only validation already performed

In an isolated Python 3.13 environment, the **same exact script Git blob** `e8916f3...` passed Python `py_compile` and the **same exact test file Git blob** `824c96...` passed six synthetic `unittest` cases covering M0 fair prefix conditioning, M1 valid Beta fit, deterministic descriptive bootstrap, Brier calculation, strict outcome label parsing, and event-trial structural duplication STOP. These **do not validate real data**.

**Handoff gate**: once the user sends preflight JSON and run JSON (or a STOP message), independently audit the result against `H0_OE_STAGE2C_FROZEN_PREREG.md` and produce `H0_OE_STAGE2D_RESULTS_REVIEW.md` with careful scientific caveats; do not alter the frozen v1.
