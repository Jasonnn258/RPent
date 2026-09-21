# Stage G — Campaign Safe Pause (G0.5 §1)

_pause ordered by the user 2026-09-21 (~02:5x): 暂停 G1-G4, 先归因.
Nothing was killed mid-episode, no log deleted, no result reset._

## Timeline

- 02:44-02:55 — G1 memB1 (libero_object_task t0/t1) episodes starting
  under the sequential campaign launcher (`.gap_run/stageG_campaign.log`,
  scheduler PID 4192204, bash 4192195, 8 workers).
- 03:01:56 — `kill -TERM` sent to scheduler + wrapper bash ONLY. No
  episode process was signaled. Queued tasks stopped with the scheduler.
- 03:0x-03:3x — the 9 in-flight memB1 episodes continued to natural
  completion (2 had already been recorded by the scheduler before the
  TERM; 7 finished as orphans and were adopted below).

## G1 results existing at pause (all preserved)

CSV `analysis/outcome_validation_runs.csv`, stage g1, tier
glm-5.3-flash, cond memB1, libero_object_task, r1 — 9 cells recorded:

| cell | result | source |
|---|---|---|
| t0_s1 | policy_fail | orphan 02:44:35 (adopted post-exit 03:36) |
| t0_s2 | success | scheduler row |
| t0_s3 | success | adopted orphan 02:47:35 |
| t0_s4 | success | adopted orphan 02:49:05 |
| t0_s5 | success | adopted orphan 02:50:35 |
| t1_s1 | success | adopted orphan 02:50:47 |
| t1_s2 | success | orphan 02:52:05 (adopted post-exit 03:36) |
| t1_s3 | success | adopted orphan 02:53:35 |
| t1_s4 | success | adopted orphan 02:55:05 |

FINAL: 9 cells, 8 success / 1 policy_fail. Adoption procedure: dirname →
(stage/tier/cond/suite/task/seed/repeat), result = pg.classify_dir,
wall_s = newest-file mtime − dirname ts, rc left empty (orphan exit code
not capturable), metric_fields(dir) appended by the scheduler's own
append_run. (A 10th g1 row — memB1 libero_spatial_task t7_s1 — is the
pre-campaign #73 DEV smoke, predating the launcher.)

## Adoption incident (honest record, corrected)

The first adoption pass was too greedy: it also matched 14 stale
2026-09-17 memB1 DEV-smoke dirs (pre-G1 debugging, never part of the
campaign) and — worse — adopted the two STILL-RUNNING episodes as
policy_fail. Corrected within minutes by rewriting the CSV: 14 stale
rows deleted (they were mislabeled stage=g1; the true pre-G1 smoke is
visible in the smoke-stage rows and DEV suite only), the two live
episodes' premature rows deleted and re-adopted only after process exit.
Final state audited above; no analyzer ever read the transient bad rows
(no analysis ran in between).

## Where everything lives

- G1 campaign log: `.gap_run/stageG_campaign.log` (sequential
  g1→g2→g3→g4 launcher, killed at scheduler level)
- G1 scheduler stdout: `.gap_run/g1_super.log` (same file family)
- Episode dirs: `logs/ovpm_exp/20260921-02:4*:*,02:5*:*` (memB1,
  libero_object_task t0/t1)
- G0 results (complete, 90/90): stage g0 rows in the same CSV;
  analysis/stageG0_results.{json,md}, stageG0_verdict.md
- G2-G4: never started (queued in the killed launcher). No orphan, no
  data loss — smoke-stage rows from #73 are unrelated DEV smokes.

## State of the frozen campaign (for whoever resumes)

G1 grid: 3 arms × (object t0-9 + goal t0-9 + 10 t1-9) × s1-5 × r1 =
435 cells/arm target; at pause only memB1 t0/t1 partially covered
(9 cells). G2-G4 grids unchanged in `scripts/ovpm_exp.py` + committed
manifests. Resume decision belongs to the user AFTER G0.5's
direction_decision (§23: no auto-resume).
