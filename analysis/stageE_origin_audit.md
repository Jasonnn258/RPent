# Stage E2b — Failure-Origin Audit Set 结果(2026-09-20)

一句话结论:**确定性提取器在 54 条 primary 审计行上 origin accuracy 47/52 =
90.4%(门槛 ≥80% PASS),surface 52/52,missing 44/52;UNKNOWN 率仅 2/54;
代价是 10/10 hardneg 健康时刻也被赋予了 origin(交给检索 hardneg 门槛检验)。**

## 0. 构成与流程

- 样本:17 perception 全收 + 分层抽样(predicate_timing 12 / pick_verify 8 /
  recovery 10 / grasp 7)+ hardneg 10 = **64 行**(seed 20260920,按
  (episode, turn) 排序后抽样)。
- **防循环纪律**:标注工作表只含可观测量(原语窗口短语 + b2 events 原文),
  不含检测器输出;gold 先标完,之后才 join 检测器结果算一致率。
- 标注政策(逐行写入 gold 文件 `policy` 字段):origin = 近窗口内**最上游**
  的有观测支撑的未满足家族(前置链 PERCEPTION→GRASP→TRANSPORT→PLACE);
  surface 锚定决策动作自身家族;hardneg = 无失败进行中 → origin=NONE。
  标注者可看的通道与检测器相同:b2 verdicts/missing_evidence、原语返回、
  segment/back_project 回执。
- 产物:`analysis/stageE_audit_worksheet.jsonl`(可观测量工作表)、
  `analysis/stageE_origin_gold.jsonl`(gold + auditor_note + policy)、
  `analysis/stageE_origin_dump.jsonl`(134 点全量提取器输出)。

## 1. 关键观测(标注过程中确立)

**b2 verifier 的 missing_evidence 是全库固定 5 短语**(76 episodes/939 events
普查,无其他字符串):

| 短语 | 次数 | 家族归属 |
|---|---|---|
| the directed observation never ran | 108 | 进程性(不指向前置条件,只进 EVIDENCE) |
| object displacement: … move with the gripper | 99 | GRASP / OBJECT_MOVES_WITH_GRIPPER |
| object displacement does not clearly separate held vs left | 60 | GRASP / OBJECT_MOVES_WITH_GRIPPER |
| final relation: object at rest at the intended place location | 45 | PLACE / CONFIRMED_SETTLED_TARGET_RELATION |
| observation produced no usable object position | 28 | PERCEPTION / VALID_TARGET_LOCALIZATION |

perception 类 17 行的时间结构完全同构:grasp 尝试 displacement 未决(上游
t-8~-3)→ 最近 turn "no usable object position" → 决策(动作 pi0_pick,
phase P_grasp)。即 **17/17 surface=GRASP 而 origin=PERCEPTION**——Stage D
"perception 时刻 query 只叙述 pick"的结构性事实,在 origin 层被完整还原。

## 2. 检测器 vs gold(54 primary 行)

| 指标 | 结果 |
|---|---|
| origin accuracy(非 UNKNOWN,n=52) | **47/52 = .904**(门槛 ≥.80 **PASS**) |
| surface accuracy | 52/52 = 1.000 |
| missing-prerequisite accuracy | 44/52 = .846 |
| UNKNOWN 率 | 2/54 = 3.7%(recovery 首事件,窗口空) |

混淆(gold→detector):TRANSPORT→NONE×2、GRASP→NONE×1(先前失败已自愈、
当前失败无上游未决——检测器 healthy 分支过宽);PERCEPTION→PLACE×1
(#17:segment found=False 在原语窗口里,但 b2 层只有 release 短语,layer-1
短路没做原语层交叉检查)。

gold 分布:PERCEPTION 20 / GRASP 24 / PLACE 6 / TRANSPORT 4;missing 以
OBJECT_MOVES_WITH_GRIPPER(22)与 VALID_TARGET_LOCALIZATION(18)为主。

## 3. hardneg 观察(单列,不计入 accuracy)

检测器在 10/10 健康决策点上输出了非 NONE origin(PLACE×6、GRASP×3、
PERCEPTION×1)——因为 b2 的验证短语在健康 episode 的窗口里同样存在
(例如 release 前 final-relation 恒为 pending)。gold=NONE。这不是提取器
错误(那些短语确实未决),而是"验证未决"与"失败起源"在健康时刻不可
区分——**其检索后果由 E2c 的 hardneg irr 门槛(恶化 ≤5pp)裁定**。

## 4. 结论

Gate 6(failure-origin estimation reliability)**PASS**:在线可观测量足以
把 failure origin 识别到 90% 准确,尤其 17/17 perception 案例的
origin=PERCEPTION/surface=GRASP 结构被检测器完整复现(标注独立确认)。
提取器输出可信,进入 E2c 四臂检索对照。
