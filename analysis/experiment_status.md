# 实验状态

_updated 2026-08-18T11:04:00_

window: 2026-08-19 00:00 (stop-new: 2026-08-18 23:00) — 窗口外补跑数据已标注

completed: 270 episodes (90×3 conds) + 20 t37e evals

gpus idle: [0, 1, 2, 3]


## SR by stage/cond (from result column)

- P0 / baseline: 40/90 (44%)
- P0 / ours: 38/90 (42%)
- P1 / hardcap: 42/90 (47%)

## P1 hardcap ablation（完整 3×30，t9 为窗口外补跑 2026-08-18 10:49 完成）

| task | baseline | hardcap | ours |
|------|----------|---------|------|
| t0 | 13/30 (43%) | 16/30 (53%) | 12/30 (40%) |
| t7 | 11/30 (37%) | 16/30 (53%) | 10/30 (33%) |
| t9 | 16/30 (53%) | 10/30 (33%) | 16/30 (53%) |

hardcap 整体 47% ≈ baseline 44%，但增益集中在 t0/t7（均 53%）；t9 上 hardcap 反而显著低于 baseline（33% vs 53%），streak=6 硬上限无一致增益。

## Gate 判定（P0 复核 2026-08-18 10:49）

- p1=True：sr_og (42%) >= sr_bl (47%) - 0.10 ✓
- p2=False：sr_og < sr_bl 且无效率增益（turns/red/tok 均未 < 0.85×baseline）
- 结论：hypothesis NOT supported；scheduler 已置 phase=DONE

## t37e evals（spatial t3/t7，重定义后 20/20 完成，t3 s5-s10 补跑 2026-08-18 11:03）

- t3: 3/10 (30%) — success: s1, s4, s5
- t7: 5/10 (50%) — success: s1, s2, s6, s7, s10
