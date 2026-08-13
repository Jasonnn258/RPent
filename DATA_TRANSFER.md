# RPent / Harness VLA — Data Transfer & Experiment Report

Generated: 2026-08-13 ~10:10 (local). The unattended run finished at the 10:30
final-stop window. This file is the handoff: what was done, what's missing, and
how to continue on a new server.

## 1. Environment / config (reproducibility)

- **Planner**: Kimi K3 (`anthropic:kimi-k3` via DWAI gateway, vision-capable) — this
  is what the full benchmark used. DeepSeek v4-flash was only used for the very
  first end-to-end smoke test (text-only, `--no-images`).
- **VLA**: Pi0.5 (`RLinf-Pi05-LIBERO-130-fullshot-SFT`), checkpoint at
  `/hw-tbo/yjx/checkpoints/RLinf-Pi05-LIBERO-130-fullshot-SFT` (7.0G).
- **SAM3**: `sam3.pt` at `/hw-tbo/yjx/checkpoints/sam3/sam3.pt` (3.3G).
- **GPU note**: the run started on **4× V100-32GB**, then the node switched to
  **2× A800-80GB** near the end. All code paths are GPU-count agnostic (see
  `gap_fill.sh` GPU-subset config).
- **Key source changes** (git `8234589`):
  - `robots/libero/tools.py`: `release` → `pi0_doubled` routing hook behind
    `RPENT_FORCE_DOUBLED=1` (baseline unchanged when unset).
  - `robots/libero/prompts/system.py`: Rule 2e perception budget.
  - `gap_fill.sh` / `gap_supervisor.sh` / `ablate_t9_doubled.sh` / `data_guardian.sh`.
- **Setup recipe** (glibc 2.27 host): see `SETUP_NOTES.md` (torch 2.6.0 override,
  mesa/xvfb software EGL, hf-mirror/ModelScope download sources).

## 2. What was completed

### Suites / tasks / seeds (latest-per-seed libero_terminated)
| suite | success/total | SR | complete tasks |
|---|---|---|---|
| libero_spatial | 48/97 | 49% | 9/10 |
| libero_goal_task | 52/80 | 65% | 7/10 |
| libero_goal_swap | 37/76 | 49% | 7/10 |
| libero_spatial_task | 5/12 | 42% | 0/10 (bootstrap only) |
| libero_spatial_swap | 6/10 | 60% | 0/10 (bootstrap only) |

- Full 11-seed (seed0 bootstrap + seed1..10 eval) completed for: spatial t0-t3,t5-t9;
  goal_task t1,t2,t4,t5,t7,t8,t9; goal_swap t1,t2,t4,t6,t7,t8,t9.
- **spatial_task / spatial_swap are INCOMPLETE** — only seed0 bootstrap (and a few
  eval seeds) ran before the time window + GPU switch. Their SR numbers above are
  on tiny sample sizes and are NOT final.

### t9 causal ablation (forced pi0_doubled)
- Baseline (goal_swap t9): **1/11 = 9.1%**.
- Ablation (RPENT_FORCE_DOUBLED=1, seeds 1-10): **1/10 = 10%**.
- **Conclusion: forced pi0_doubled does NOT significantly help t9.**
- Root cause insight: most failed t9 runs stall in **perception loops**
  (redundant `back_project`/`read_image`, max_redundant 16-22) and never reach the
  placement stage — so the placement primitive choice is not the binding
  constraint. Only seed 5 reached placement and, with 31 forced-doubled calls,
  succeeded. This corroborates `analysis/failure_analysis_t0_t7_t9.md`: t9's high
  perception ratio is a **symptom of grounding uncertainty / recovery failure**,
  not a cause.

## 3. Failure taxonomy (from analysis)

1. **F1 perception loop** — consecutive perception calls with no action (t9 dominant).
2. **F2 re-localization loop** — `move_to` retried ≥7× (t7/t0 failures).
3. **F3 execution-precision retry** — `pi0_pick`/`pi0_doubled` ≥3× (t9/t0).
4. **F4 over-reading memory** — `read_text_file` ≥10× (t0).
5. **F5 infra** — API timeout / crash (non-deterministic).
Bootstrap failures (goal_task t0/t3/t6, goal_swap t0/t3/t5, spatial t4) also skip
entire-task evals — a structural gap, not a per-seed failure.

## 4. Archive

- `artifacts/final_export/` (941M, 1143 files): benchmark_summary.csv,
  t9 ablation csv, failure analysis (md+csv), gap_fill.csv, harness_report.jsonl,
  all scheduler scripts, and 12 t9 ablation raw run dirs.
  - **SHA256 manifest**: `f1555c916ff9d9100397492acb96061dd9a02b5260aa1549b80179b2e6647fd6`
    (of the sorted per-file sha256 list).
- Full per-run logs: `logs/` (36G) — not archived wholesale (large images/videos);
  key artifacts are in final_export.

## 5. Git

- HEAD: `d8b38aa` (plus hourly `bench: status snapshot` commits by data_guardian).
- Feature commit: `8234589` (ablation + scheduler + analysis + Rule 2e).
- **Not pushed**: `git push` to `origin` (RLinf/RPent) times out — no GitHub
  credentials configured on this host. Push manually once auth is set up.

## 6. How to continue on a new server

1. Provision a host with glibc>=2.28 (preferred) or follow `SETUP_NOTES.md` for
   glibc 2.27. `git clone https://github.com/RLinf/RPent` + `pip install -e ".[full]"`.
2. Download checkpoints (ModelScope for sam3; hf-mirror with
   `HF_HUB_DISABLE_XET=1` for Pi0.5) — see `SETUP_NOTES.md` §3.
3. Copy `artifacts/final_export/` (analysis + scripts + summaries).
4. To finish the incomplete suites:
   `echo "0 1 2 3" > /tmp/gap_gpu_config && nohup bash gap_supervisor.sh &`
   — gap_fill auto-detects missing seeds (bootstrap+eval) and skips recorded
   policy failures.
5. To reproduce the t9 ablation: `bash ablate_t9_doubled.sh 1 10 <gpus>`.

## 7. What would be lost if this server vanished now

- **Checkpoints** (`/hw-tbo/yjx/checkpoints/`, ~10.3G): Pi0.5 + SAM3 weights —
  re-downloadable from HF/ModelScope, but slow.
- **Full `logs/` (36G)**: per-run images/videos/transcripts beyond what's in
  `final_export`. Only the 12 ablation runs + CSVs are archived; the remaining
  ~1500 run dirs (with episode.mp4, states.json, transcripts) would be lost.
- **memory/resources** (`resources/libero/memory/`, results_*_pert): bootstrap
  memory + recipes — re-derivable from logs but lossy.

## 8. Next best step (recommended, not implemented)

The most decision-relevant experiment is **finishing spatial_task / spatial_swap
evals** (the Task-redirection vs Position-swap comparison pair), which is the only
incomplete formal suite with research value. Do NOT expand to object/libero_10/90.
