# Stage N0 测量资格结果(§10 盲审 agreement + §11 双门)

- 机器:analyzer v2(确定性零 LLM,冻结于 DEVELOPMENT 阶段后)
- 人工:45 卷盲审,仅凭卷宗作答,先落盘后比对(commit 61f968f 先于本脚本运行)
- 样本:N=45(seed=20261002;eligible=124;q_D=45 q_I=0 q_U=0,deviation #5)

## 1. 混淆矩阵(人工 × 机器,N=45)

| 人工 \ 机器 | DEPENDENT | UNRESOLVED | INDEPENDENT | 合计 |
|---|---|---|---|---|
| DEPENDENT | 45 | 0 | 0 | 45 |
| UNRESOLVED | 0 | 0 | 0 | 0 |
| INDEPENDENT | 0 | 0 | 0 | 0 |
| 合计 | 45 | 0 | 0 | 45 |

## 2. 主指标

- **overall agreement**(human-resolved 上)= 45/45 = **1.000**
- **false_independent** = #(H=D ∧ M=I)/#(H=D) = 0/45 = **0.000**
- **false_dependent** = n/a(#(H=I)=0,人工侧无独立段)
- human-resolved = 45/45;人工 UNRESOLVED = 0;机器 UNRESOLVED = 0
- 机器侧结构说明:审计池 45/45 为 machine-DEPENDENT(eligible∩I=0,prereg deviation #5),
  false_independent 门的分子分母均来自 H=D 列,机器-I 方向本轮未被审计检验;
  其方向正确性仅有 dev 阶段全量 5 段 census(4 同意 + 1 存疑 rotate_wrist)作旁证。

## 3. 双门判定(§11)

| 门 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| overall agreement | ≥ 90% | 100.0% | PASS |
| false_independent | ≤ 5% | 0.0% | PASS |
| human-resolved | ≥ 30 | 45 | PASS |

**N0 测量资格门:PASS** → 允许进入 N1(闭环反馈验证)

## 4. 分歧明细(span / 数值链重放)

- **零分歧**:45/45 人工 DEPENDENT 与机器 DEPENDENT 一致,无需重放。

## 5. 描述性补充(非门输入)

- 人工 dependency_type 分布:observation_gate=27 / pose_update=17 / target_grounding=1
- 同意段上人工 type ∈ 机器 dependency_types:43/45;仅机器侧含:2
- 按族 agreement:FALSE_GRASP=20/20 / MOVE_CONTACT_STALL=2/2 / RELEASE_PREDICATE_STALL=23/23
- 按长度三分位 agreement:L=14/14 / M=15/15 / S=16/16
