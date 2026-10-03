# Stage P0 Decision — Candidate Replay Qualification

生成:2026-10-03T15:06:42.415613 | runner:scripts/stageP_replay.py
| prereg:analysis/stageP_prereg.md §5 | 数据:Stage O 8 FG 快照(§33 discovery 许可)

## P0 四条件(§5)

1. **identity 明确**:candidate := 首个 [5,7] action chunk(stageP_candidate_interface.md §3,实现事实 file:line 全引)
2. **可执行前冻结**:16 candidate 全部执行前生成并落盘`analysis/stageP_candidates_p0.jsonl`(frozen_ts 先于任何 chunk 执行)
3. **replay PASS**:(下表)
4. **candidate+固定 continuation 有可定义 outcome**:§4 契约已冻结(测量点/标签优先级);Stage O O1 同快照全 attempt 结果(discovery)佐证 outcome 分布非退化

## Replay 结果

- candidate 数:16(要求 ≥12)
- 有效 replay 行:48 | infra 行:0
- transition-class agreement:**1.0000**(48/48)(gate ≥95%)
- success/failure flags agreement:**0.9583**(46/48)(gate ≥95%)
- 数值指纹(end EE pose + 目标位移 max|Δ| 跨 replay,另报非 gate):**非逐位相等:16/16 candidate 非零(max 见下表;dev-P1:亚毫米系统性单调漂移,详见判定节)**
- per-candidate 最差 transition agreement:1.000 | 最差 flags agreement:0.333

## Per-candidate(最差 agreement 与指纹)

| snapshot | cand | n_valid | transition | flags | fingerprint |
|---|---|---|---|---|---|
| osnap_00 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 7.77e-04 |
| osnap_00 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 7.64e-04 |
| osnap_01 | 1 | 3 | 3/3(1.000) | 1/3(0.333) | 3.54e-04 |
| osnap_01 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 3.92e-04 |
| osnap_02 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 2.96e-04 |
| osnap_02 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 1.98e-04 |
| osnap_03 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 3.75e-04 |
| osnap_03 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 3.83e-04 |
| osnap_04 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 5.08e-04 |
| osnap_04 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 4.80e-04 |
| osnap_05 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 6.29e-04 |
| osnap_05 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 5.98e-04 |
| osnap_06 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 6.51e-04 |
| osnap_06 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 6.87e-04 |
| osnap_07 | 1 | 3 | 3/3(1.000) | 3/3(1.000) | 4.72e-05 |
| osnap_07 | 2 | 3 | 3/3(1.000) | 3/3(1.000) | 1.34e-04 |

## 判定

**P0 PASS** —— transition 与 flags 双 agreement ≥95%(prereg §5 冻结 gate 口径),candidate ≥12。CANDIDATE_INTERFACE:QUALIFIED,可进 P1。

## dev-P1 — 指纹期望证伪 + gate 公式修正(裁决留痕)

1. **数值指纹非逐位相等(prereg §5 的"预期 0.0"被证伪)**:同一 frozen chunk 从同一 restore 态执行 3 次,end EE pose 与目标位移呈 **≤7.8e-4 m 的系统性单调漂移**(90 个逐列增量中 89 个同号),非随机噪声。机制假说:flat state(qpos/qvel/act/time)不含 MuJoCo 求解器 warm-start/接触历史,restore 后前向积分依赖未恢复的求解历史;J0 的"restore 逐位精确"仅覆盖读回,不覆盖重执行。
2. **对判定体系的影响**:标签/分类阈值(FG 契约 0.03 m、HARM 0.03/0.08 m、chunk class 0.015/0.03 m)比漂移大 20-400 倍,类级 agreement(transition 48/48、flags 46/48)直接吸收之;唯一翻转(osnap_01 cand1 的 flag_gripper_closed)是夹爪开口恰在 0.06 阈值邻域的边界敏感,量级与漂移一致。
3. **gate 公式修正**:runner 首版误把指纹折进 pass 条件(严于预注册),自动判 FAIL;按 prereg §5 冻结文本(gate = 双 agreement,指纹"另报")修正为 PASS。数据 CSV 零改动,裁决只用已冻结数据。P1 设计含义:candidate 间比较的物理量级安全,但**贴阈值的 flag 在 ~1e-3 m 邻域内不可靠**,P2 特征禁依赖单一阈值邻域内的 flag。
