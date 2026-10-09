# RPent Research Agent Instructions

This repository contains frozen historical experiments and a long-running Harness VLA research program.

## Always load research context first

1. `analysis/research_context/RESEARCH_MASTER.md`: stable research questions, limitations and goals.
2. `analysis/research_context/CURRENT_STATE.md`: current HEAD-independent status, blockers and next action.
3. `analysis/research_context/DECISION_LOG.md`: durable evidence-backed decisions.
4. `analysis/research_context/RESEARCH_AUTHORIZATION.md`: **scope-limited** authorization boundaries; check the actual current user instruction as well.
5. Relevant frozen original protocol/report before using any historical measurement.

## The current approved work package

Research Package A is approved for **L1 existing-data offline research**: source field qualification, A0 same-skill outcome/FGONLY descriptive analysis, EERD v0.1 internal materialization, offline QA and reporting. Its pre-outcome protocol lock is `analysis/harness_h0/H0_OE_STAGE2J_FROZEN_V2_PACKAGE_A.md`. Entry point is `bash analysis/research_context/run_package_a.sh` **only on the server with private traces**, after reviewing inputs and ensuring the existing run is not active.

Do not assume that a file existing on GitHub implies its experimental data exists here. Do not claim tests/statistics passed unless they were actually executed with visible results. Do not upload `artifacts/research_package_a/` or any private raw/derived audit data to Git.

Stage R §36 HARD STOP and S1-DEV0 ON_HOLD continue to forbid **new rollout, simulator collection, Runtime/Planner/controller/verifier/retry wiring, training, production or deployment** without a new explicit L2/L3 stage authorization. The L1 package approval is not a permanent broad license to do unrelated future experiments.

## Research behavior

- Separate VERIFIABLE_FACT / REPORTED_SERVER_RESULT / INFERENCE / PROPOSAL.
- Respect decision-time visibility: privileged sim truth is audit-only and never legal online input or evolution evidence.
- The Stage R 480 rebuilt trials are correlated within 24 selected failures, not 480 independent sequential retries.
- Retrospective flag/FGONLY agreement is **not** future physical holding or a prospective intervention effect.
- Keep source files and frozen protocols immutable. If results contradict a pre-registered gate, STOP the affected experiment instead of silently changing thresholds or metrics.
- Prefer finishing a meaningful stage to creating more document-only sub-stages. Update CURRENT_STATE after substantive progress, DECISION_LOG for significant decisions; MASTER only when core directions truly change.
