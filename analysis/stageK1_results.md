# Stage K1 结果(TEST 单触,3-seed 集成)

| 指标 | B0 | B1 | B2 | B3 |
|---|---|---|---|---|
| verified_auroc | 0.889 | 0.823 | 0.823 | 0.826 |
| verified_auprc | 0.521 | 0.293 | 0.293 | 0.280 |
| verified_brier | 0.069 | 0.111 | 0.104 | 0.092 |
| verified_nll | 0.193 | 0.293 | 0.271 | 0.298 |
| verified_ece | 0.054 | 0.175 | 0.167 | 0.088 |
| harm_auroc | 0.662 | 0.176 | 0.446 | 0.628 |
| harm_auprc | 0.071 | 0.031 | 0.045 | 0.061 |
| top1_best_recall | 0.250 | 0.250 | 0.250 | 0.250 |
| pairwise_acc | 0.500 | 0.714 | 0.500 | 0.571 |
| regret_verified | 0.000 | 0.000 | 0.000 | 0.000 |
| regret_harm | 0.062 | 0.062 | 0.062 | 0.062 |
| ens_std_mean | 0.004 | 0.014 | 0.009 | 0.022 |

## §9 资格门

```json
{
 "brier_rel_improve": 0.0657,
 "pairwise_gain": -0.2143,
 "regret_rel": 0.0,
 "g1_wm_vs_static": false,
 "g2_harm_auroc": false,
 "g3_oracle_beats_static": true,
 "families_nonneg": true,
 "PASS": false
}
```

**判定:FAIL → WORLD MODEL NOT JUSTIFIED → STOP(禁入 K2)**

注:MCS 族结构缺位(K0 决策文档三证据),族条款按 FG/RPS 解读。