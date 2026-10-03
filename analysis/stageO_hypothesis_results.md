# Stage O 假设判定与 first-source 分析(§27-§30)

- 生成:2026-10-03T09:42:32.939479(确定性 analyzer,零 LLM)
- 快照 12 个(可测量 12;init 退化 0:无;零有效 boot 0:无)| K_ROLLOUT=8 | reference OK=7
- rollout 行 480(infra_abort 36 = 7.5%;§12 门 <2%)
## First-source 分布(spec §28 P(Ox first))

- **TASK_RECOVERY 契约版**:O1_POLICY_SUPPORT=5, REFERENCE_UNAVAILABLE=2, NO_SOURCE_FOUND=2, O4_REPLANNING=1, O4_REPLANNING_BELOW_UNTESTED=1, O3_FIXED_SEQUENCE=1
- **POLICY_REENTRY 版**:NO_SOURCE_FOUND=6, REFERENCE_UNAVAILABLE=4, O1_POLICY_SUPPORT=1, O4_REPLANNING_BELOW_UNTESTED=1
- **RECOVERY 并集版**:O1_POLICY_SUPPORT=6, REFERENCE_UNAVAILABLE=2, O4_REPLANNING_BELOW_UNTESTED=1, NO_SOURCE_FOUND=1, O3_FIXED_SEQUENCE=1, O4_REPLANNING=1

## Δ 配对(task 结局,paired by snapshot)

- Δ01: n=10 mean=+0.263 (正 8 / 负 1)
- Δ12: n=2 mean=+0.000 (正 0 / 负 0)
- Δ23: n=1 mean=+0.250 (正 1 / 负 0)
- Δ34: n=4 mean=-0.188 (正 1 / 负 3)

## 假设判定(独立,§30)

- H_A POLICY SUPPORT:**SUPPORTED**(O1 达标快照 5 个:['osnap_00', 'osnap_01', 'osnap_06', 'osnap_08', 'osnap_10'];Δ01 正/负 = 8/1)
- H_B CONDITIONING:**NOT SUPPORTED**(O1 未达标而 O2 达标:0 个:无)
- H_C FIXED SEQUENCE:**INCONCLUSIVE**(O2 未达标而 O3 达标:2 个:['osnap_00', 'osnap_07'])
- H_D REPLANNING:**INCONCLUSIVE**(O3 未达标而 O4 达标:2 个:['osnap_02', 'osnap_03'];state-dependent 证据 8 条)
- H_E SKILL DEFICIT:**NOT WRITABLE(O1/O2/O3 存在达标快照;§30 限定条件不满足)**

## REALIGNMENT_FIRST(§31;成功 rollout 内)

- O0: 15/15(100%)
- O1: 0/66(0%)
- O2: 0/0
- O3: 3/11(27%)
- O4: 0/8(0%)
- reference traces: 3/7

## Reentry 早于 task recovery(§31 讨论输入)

- reentry 达标而 task 未达标的 (snapshot, arm) 对:2 个:[('osnap_02', 'O1'), ('osnap_02', 'O3')]

## O1/O2 best_of_N(checkpoints 1/4/8/16 均值)

- O1: [0.455, 0.386, 0.364, 0.375]
- O2: [0.0, 0.0, 0.0, 0.0]

## 预算账(§20/§33;均值 [p90])

| arm | n | prims | pi05 | turns | wall_s |
|---|---|---|---|---|---|
| O0 | 84 | 4.1 [5.0] | 1.2 [2.0] | — | 40.0 [52.6] |
| O1 | 176 | 1.0 [1.0] | 1.0 [1.0] | — | 16.2 [22.4] |
| O2 | 32 | 1.0 [1.0] | 1.0 [1.0] | — | 18.9 [21.3] |
| O3 | 32 | 2.8 [4.0] | 0.2 [1.0] | — | 14.7 [27.8] |
| O4 | 72 | 1.0 [3.0] | 0.0 [0.0] | 15.4 [16.0] | 475.9 [704.0] |

## Wilson 95% CI(每 arm×snapshot task 结局)

- O0: osnap_00[0.00,0.32] osnap_01[0.00,0.32] osnap_02[0.00,0.32] osnap_03[0.00,0.32] osnap_04[0.00,0.32] osnap_05[0.00,0.32] osnap_06[0.00,0.32] osnap_07[0.00,0.32] osnap_08[0.15,0.85] osnap_10[0.68,1.00] osnap_11[0.31,0.86]
- O1: osnap_00[0.81,1.00] osnap_01[0.51,0.90] osnap_02[0.07,0.43] osnap_03[0.01,0.28] osnap_04[0.03,0.36] osnap_05[0.01,0.28] osnap_06[0.51,0.90] osnap_07[0.00,0.19] osnap_08[0.64,0.97] osnap_09[0.00,0.19] osnap_10[0.14,0.56]
- O2: osnap_07[0.00,0.19] osnap_09[0.00,0.19]
- O3: osnap_00[0.68,1.00] osnap_02[0.00,0.32] osnap_05[0.02,0.47] osnap_07[0.07,0.59]
- O4: osnap_00[0.02,0.47] osnap_02[0.14,0.69] osnap_03[0.07,0.59] osnap_04[0.00,0.32] osnap_05[0.00,0.32] osnap_06[0.00,0.32] osnap_07[0.02,0.47] osnap_09[0.02,0.47] osnap_11[0.00,0.32]
