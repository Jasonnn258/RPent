# Stage Q1 Decision — State×Candidate Factorial

生成:2026-10-06T02:37:19.970520 | 门 = 0.15(15pp) | 判据:STABLE 主、ACQUISITION 陪报;统计单位 = event

| 假设 | 检验 | 值 | LOO | 判定 |
|---|---|---|---|---|
| H_QB 物理预置 | exec-state effect(STABLE) | +0.078 | +0.036 | NOT SUPPORTED |
| H_QC 动作后置 | cand-source effect(STABLE) | +0.047 | +0.009 | NOT SUPPORTED |
| H_QD 交互 | interaction(STABLE) | -0.219 | -0.321 | NOT SUPPORTED |
| H_QA 随机重采样 | PP stable 出现率 1.000(≥0.70) ∧ |OO−PP|=0.125(≤0.10) | | | NOT SUPPORTED |

TRANSIENT_GAP(TEST):PP=+0.297, PO=+0.172, OP=+0.281, OO=+0.250;任一 ≥0.15 → H_QE 机制性重要(本次 是)。

**措辞约束(Q0 gate,prereg §5)**:restore-sensitivity 已判 RESTORE-SENSITIVE DYNAMICS(transition-class 一致率 0.769<0.90) → 本文件所有 restored-state 因果拆分结论标 **APPROXIMATE**,禁称精确 physics counterfactual;不可解释部分按 §12 记 UNOBSERVED/CONTACT-HISTORY DYNAMICS MAY CONTRIBUTE。

Q2 触发条件:exec-state(STABLE)≥0.15 或 H_QB SUPPORTED → 本次值 +0.078、gate 未过 → **不触发**(prereg §11)。

