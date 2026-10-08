# Stage R 六假设判定(prereg §10 预注册门)

生成:2026-10-08T08:59:57
cohort 事件数:24(统计单位 = event;全部指标 under FALSE_GRASP and current Pi0.5/runtime)

## 总体统计

- q_same:mean=0.302 (boot95% [0.193,0.417]) median=0.250; fraction q>0 = 18/24
- q_policy:mean=0.323 (boot95% [0.229,0.422]) median=0.125; fraction q>0 = 19/24
- TYPE 分布:E=14 A=1 P=5 U=4
- STRONG_PERSISTENT@8 占比:20.8%
- Retryability@8:SAME≥1 18/24;SAME≥2 14;POLICY≥1 19;POLICY≥2 16
- C(k) POLICY:1:0.167 2:0.458 4:0.708 8:0.792
- h(k) POLICY:1:0.167(n=24) 2:0.350(n=20) 4:0.000(n=7) 8:0.000(n=5)
- pooled ACQ−STABLE gap:SAME=0.344 POLICY=0.375
- NATURAL(陪报,不入 C(k)):mean q_nat=0.323

## 六判定

| 假设 | 判定 | 依据 |
|---|---|---|
| EPHEMERAL_FAILURES_EXIST | SUPPORTED | TYPE E 事件数 = 14 |
| ACTION_SPECIFIC_FAILURES_EXIST | INCONCLUSIVE | TYPE A 事件数 = 1 |
| POLICY_PERSISTENT_FAILURES_EXIST | SUPPORTED | TYPE P 事件数 = 5 |
| ONE_SHOT_FAILURE_IS_INFORMATIVE | INCONCLUSIVE | median q_policy=0.125 落在中间带 |
| RETRY_GAIN_SATURATES_EARLY | INCONCLUSIVE | C(8)−C(4)=0.083 落在中间带 |
| TRANSIENT_SUCCESS_REPLICATES | SUPPORTED | pooled ACQ−STABLE gap: SAME=0.344 POLICY=0.375(任一 ≥.15) |

## 措辞纪律(prereg §10)

0/K 只写 persistent@8,禁写"绝对不可恢复";禁写"most failures are stochastic" / "same-action retry is sufficient" / "persistent failures need learning"(spec §32 强结论门槛)。

