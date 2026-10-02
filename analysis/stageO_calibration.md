# Stage O K_ROLLOUT 校准记录(prereg §8 附录 B 内容源)

- 日期:2026-10-02T06:31:28.412996
- 校准子集(N 池,排除出 O-B,合法):['snap_00', 'snap_01', 'snap_06', 'snap_02', 'snap_03', 'snap_04']
- 每快照 O1 式独立采样 16 次(重放 step≤t0 最后一条 Pi0.5 族命令,逐字重执行)

| snapshot | family | action | prompt | k/N | p̂(16) |
|---|---|---|---|---|---|
| snap_00 | FALSE_GRASP | pi0_pick | pick up the bowl on the stove | 0/16 | 0.000 |
| snap_01 | FALSE_GRASP | pi0_pick | pick up the black bowl | 0/16 | 0.000 |
| snap_06 | FALSE_GRASP | pi0_pick | pick up the black bowl on the cookie box | 0/16 | 0.000 |
| snap_02 | RELEASE_PREDICATE_STALL | pi0_pick | pick up the bowl on the stove | 0/16 | 0.000 |
| snap_03 | RELEASE_PREDICATE_STALL | pi0_pick | pick up the black patterned bowl | 0/16 | 0.000 |
| snap_04 | RELEASE_PREDICATE_STALL | pi0_pick | pick up the black patterned bowl | 0/16 | 0.000 |

稳定性(median|p̂(K)−p̂(2K)|,冻结阈值 ≤0.10):
- K=4: 0.000
- K=6: 0.000
- K=8: 0.000

**K_ROLLOUT = 8**(默认(数据退化或无 K 满足);退化=True)

bootstrap 95% CI(每快照 p̂16,seed=20261002):
- snap_00: [0.000, 0.000]
- snap_01: [0.000, 0.000]
- snap_06: [0.000, 0.000]
- snap_02: [0.000, 0.000]
- snap_03: [0.000, 0.000]
- snap_04: [0.000, 0.000]
