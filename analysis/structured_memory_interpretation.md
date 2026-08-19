# Structured Global Memory v1 — Interpretation & caveats

_2026-08-18, after full paired run (baseline 33 / structured 30, t0/t7/t9 libero_spatial_task seeds 1-10)._

## Hypothesis check

| claim | outcome |
|---|---|
| SR improves | ✅ +9pp overall (55%→63%); +15/+5/+6 per task |
| planner turns ↓ | ✅ 36.97→32.87 (−4.1) |
| perception calls ↓ | ✅ 22.45→17.77 (−4.68) |
| max redundant loops ↓ | ✅ 9.21→6.23 (−2.98) |
| tokens ↓ | ✅ 3.17M→2.54M (−20%) |
| recovery success ↑ / fail ↓ | ✅ +0.5 / −0.44 |
| fewer wrong-phase jumps | ⚠️ ambiguous — see below |
| fewer repeated memory reads | ⚠️ baseline already ~1.2, no headroom |

## Anomaly 1 — off_phase_actions UP (+3.39, 7.24→10.63): progression-depth confound, mostly

Per-phase off_phase, normalized by # runs reaching that phase:

| phase | baseline off/run | structured off/run | n_reach base/str |
|---|---|---|---|
| P_look | 0.94 | 1.00 | 33/30 |
| P_transport | 1.00 | 0.97 | 31/30 |
| P_grasp | 5.29 | 5.14 | 31/29 |
| P_place | 0.52 | 1.35 | 25/26 |
| P_verify | 0.00 | 8.44 | 0/9 |

- The +80 off_phase delta is **76 from P_verify alone**. Baseline **never** reaches P_verify (0/33); structured reaches it 9/30. FORBIDDEN[P_verify] bans every tool except `finish`, so merely reaching P_verify guarantees off-phase calls. This is deeper task progression, not wrong-phase jumping.
- Same-phase rates for P_look/P_transport/P_grasp are statistically identical → the structured arm does **not** jump phases more.
- P_place 0.52→1.35 is the one genuine same-phase rise. Root causes: ~⅓ is legit two-stage `pi0_doubled` repositioning (an R5 artifact), ~⅔ is re-navigation loops in stalled runs (t0s4/t7s3/t7s4 = 4-6 move_to each) — the same F2-style loop the rules target, appearing at the place step. Mild caveat, not a headline regression.

**Conclusion: off_phase_actions as defined is confounded by progression depth; the increase is not evidence of more wrong-phase jumps.**

## Anomaly 2 — R8 (over-reading) fires 0.03→0.07/run, but never on real memory reads

**编号勘误**：SM1 报告里 "R7 fired 0.3/run" 实为 **R8 的 9 个触发**（=9 条到达 P_verify 的 run，深度驱动；报告表格中 R7=0→0.3、R8=0.03→0.07 各自正确）。R7 = P_verify→finish，R8 = over-reading（`read_text_file_calls_ge:10`）。

R8 的计数器把 **所有** `read_text_file` 调用都计入。在 firing runs 里读取的是：
- `robots/libero/guides/*.md` (strict_hybrid / pro_hybrid / env_calibration)
- `resources/libero/results_spatial_pert/*.json` + `*.jsonl` (prior-run recipes)

…不是 memory 目录。实际 memory reads 两臂都 ~1.2/run。**R8 从未因真实 memory 过度阅读触发** — 这是一个对着错误计数器触发的假阳性守卫。修复（已落地为 SM2 的 Fix A）：把计数器收窄到 memory-dir 路径，R8 只统计 `memory/` 下的读取；SM1 实验本身无影响（触发一次注入 "stop over-reading"，无害），但使 `n_fired`/`R8` 列失去信息量。

## Bonus finding — final_phase depth ≠ success

| final_phase | structured success/fail | baseline success/fail |
|---|---|---|
| P_grasp | 2/1 | 0/6 |
| P_place | 13/4 | 16/9 |
| P_verify | 4/5 | 0/0 |

Structured runs go deeper (P_verify 30% vs 0%, baseline stuck at P_place 76%), but reaching P_verify is not sufficient for success (4/9) — the second-release state is reached, yet placement/gripper still wrong. The SR gain comes from **fewer redundant loops** (−2.98 maxred, −4.68 perc), not from reaching P_verify.

## Known infra bug (non-affecting)

`scripts/structured_memory_exp.py` `append_run` 曾把 CSV header 写成**第一行** row 的 keys。因为 reused-baseline rows 没有 `structured_metrics.json`，header 是 11 个基础列，metric 列（injections/fired_rules/mem_reads/…）被**静默丢弃**。分析脚本用 `replay_run` 确定性重算全部指标（tests 已交叉核对），结果不受影响 —— 但 runs CSV 不自描述。**已修复（Fix B）**：显式 `RUN_FIELDNAMES` 在首次写入前固定 header，SM2 的 `dual_route_exp.py` 同样处理。

## Bottom line

Structured Global Memory v1 delivers the efficiency goal (−20% tokens, −4.7 perception calls, −3.0 maxred, fewer failed recoveries) and +9pp SR, with no evidence of increased wrong-phase jumps once the P_verify depth confound is accounted for. The only real caveats are the mild P_place re-navigation rise and the R7 trigger scope.
