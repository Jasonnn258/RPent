# Stage N1 结果 — CLOSED-LOOP OPTION vs FIXED_MACRO(§4-§5)

- rollouts:有效 144(M=72 O=72);INFRA_ABORT 快照 0;manifest 快照 24
- 完整快照(6 行)24/24


## 1. 主指标

| 指标 | M | O | Δ(快照配对) | Δ(pooled) |
|---|---|---|---|---|
| validated_recovery | 0.0% | 0.0% | **+0.0pp** | +0.0pp |
| harm | 1.4% | 2.8% | **+1.4pp** | +1.4pp |

- rescue 快照:∅→ rescue_rate = 0.0%
- feedback_harm 快照(汇报不进门):['snap_01', 'snap_15']
- realization_rate(O)=65.3%(47/72)
- mechanism split:delta_realized=+0.0pp (n=47) / delta_not=+0.0pp (n=25)

## 2. 五门判定(§5 逐字)

| 门 | 实测 | 判定 |
|---|---|---|
| 1 Δrecovery ≥ 15pp | +0.0pp | FAIL |
| 2 Δharm ≤ 3pp | +1.4pp | PASS |
| 3 rescue_rate ≥ 10% | 0.0% (0/24) | FAIL |
| 4 realization_rate ≥ 20% | 65.3% | PASS |
| 5 delta_realized ≥ delta_not + 10pp | +0.0pp (+0.0 vs +0.0) | FAIL |

**判定:CLOSED-LOOP FEEDBACK NOT SUPPORTED**

## 3. 分解(描述性)

| 臂×procedure | recovery | harm | n |
|---|---|---|---|
| M P1_RPS_REPICK | 0% | 0% | 36 |
| M P2_FG_RETRY | 0% | 3% | 36 |
| O P1_RPS_REPICK | 0% | 0% | 36 |
| O P2_FG_RETRY | 0% | 6% | 36 |

end_reason 分布:M:MACRO_DONE=72 / O:CARRY_END=25 / O:HOLD_END=8 / O:RETRY_DONE=39

O 臂 realized 按 rule_id(计数,同一 rollout 可多条):R2_pose_update=36 / R3_retry=36 / R3_retry_end=11

源 episode 最终 terminated/success(完整 planner 预算,对照):23/24 —— 快照态可恢复性成立,0% recovery 属于宏预算内不可恢复,而非通道损坏或不可恢复态。

按 tercile recovery(M→O):
- S:M 0% → O 0% (n=24/24)
- M:M 0% → O 0% (n=24/24)
- L:M 0% → O 0% (n=24/24)
