# Stage Q1 — State×Candidate Factorial 结果

生成:2026-10-06T02:37:19.968914 | prereg §7/§8/§10 | K=4 R_Q=2 HOLD_MIN_POINTS=4

事件(完整四 cell):DEV 5/TEST 8;A_fail probe = NOT_RECOVERABLE(transcript 无 chunk 级动作,不执行不进 gate)。

## 四 cell 恢复率(TEST pooled,事件等权)

| cell | ACQUISITION | STABLE | ACQ−STABLE |
|---|---|---|---|
| PP | 0.688 | 0.391 | +0.297 |
| PO | 0.750 | 0.578 | +0.172 |
| OP | 0.828 | 0.547 | +0.281 |
| OO | 0.766 | 0.516 | +0.250 |

## 效应(TEST pooled;bootstrap by snapshot 10k)

| 效应 | ACQUISITION (LOO) CI | STABLE (LOO) CI | 门 |
|---|---|---|---|
| EXECUTION-STATE(H_QB) | +0.000 (-0.045) [-0.242,+0.172] | +0.078 (+0.036) [-0.062,+0.227] | ≥0.15,LOO 同(H_QD LOO>0) |
| CANDIDATE-SOURCE(H_QC) | +0.078 (+0.036) [-0.047,+0.195] | +0.047 (+0.009) [-0.070,+0.164] | ≥0.15,LOO 同(H_QD LOO>0) |
| INTERACTION(H_QD) | -0.125 (-0.179) [-0.344,+0.094] | -0.219 (-0.321) [-0.484,+0.062] | ≥0.15,LOO 同(H_QD LOO>0) |

## H_QA / TRANSIENT(TEST)

- PP stable>0 事件率 = 1.000(门 ≥0.70);
- |OO_STABLE − PP_STABLE| = 0.125(门 ≤0.10);
- TRANSIENT_GAP(ACQ−STABLE):PP=+0.297, PO=+0.172, OP=+0.281, OO=+0.250(任一 ≥0.15 → H_QE 机制性重要)。

## DEV sanity(陪报)

- exec_stable +0.325, cand_stable +0.125, int_stable -0.300;PP stable 率 0.325。
