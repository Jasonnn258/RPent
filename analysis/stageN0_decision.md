# Stage N0 决策文档(§12)

日期:2026-10-01 | 判定对象:轨迹级 control-dependency 测量资格

## 输入

- analyzer v2(确定性零 LLM,≥6 检测器 A′-F′,DEVELOPMENT 失败模式开发后冻结)
- 45 卷盲审(seed=20261002,manifest sha256=
  2390cf39f095cf5414a8b7f1b6c91d176a0090fb55147f832caf99b4c52aa947,
  卷宗生成先于人工作答 commit)
- 人工作答冻结 commit 61f968f(先落盘后比对)
- 指标计算 scripts/stageN0_agreement.py → analysis/stageN0_measurement_results.md

## 结果

| 门 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| overall agreement | ≥ 90% | 45/45 = 100% | PASS |
| false_independent | ≤ 5% | 0/45 = 0% | PASS |
| human-resolved | ≥ 30 | 45 | PASS |

零分歧;人工 dependency_type(observation_gate 27 / pose_update 17 /
target_grounding 1)在 43/45 段上落入机器 dependency_types 集合。

## 结构性限制(随判定如实记录,不改变门结论)

1. 审计池 45/45 为 machine-DEPENDENT(eligible∩INDEPENDENT=0,
   prereg deviation #5)。false_independent 门的分子分母均来自 H=D 列,
   **机器-I 方向本轮未被正式审计检验**;旁证仅 dev 阶段全量 5 段
   machine-I census(4 同意 + 1 存疑 rotate_wrist eef-position 通道,
   已记 limitation #6)。
2. 本测量资格成立的准确表述:在 DEPENDENT 富集的恢复段上,analyzer v2
   与人工盲审完全一致;INDEPENDENT 方向的特异性未经 45 卷级检验。

## 决策

**N0 = PASS → 解锁 N1(闭环反馈验证)。**

N1 前置纪律:
- 本判定与 measurement_results 一并 commit 后才允许任何 N1 代码;
- N1 按预注册 §14-20 执行,FIXED_MACRO(M)vs CLOSED_LOOP_OPTION(O)
  matched 对比,五门全过才判 SUPPORTED;
- 任一门 FAIL → 按 §13/§20 措辞 STOP,不进入启发式重测循环。
