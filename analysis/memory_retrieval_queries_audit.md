# Stage A-1 数据集说明 — memory_retrieval_queries.jsonl(2026-09-17)

生成器:`scripts/build_memory_retrieval_queries.py`(seed=17,确定性可复现)。
规格见 `memory_stageA_design.md`。**280 行 = 120 YES + 120 NO + 40 UNCERTAIN**;
UNCERTAIN 不进主评估。

## 数据源

- 事件主源:`b2_verification_events.jsonl`(1341 条,armB2 libero_spatial_task 全量)
- episode 结局:`b2_runs.csv` 的 `dir` 列 basename 做 join(不用 stage/task 重构 ——
  CSV 里 stage 实际值是 dev2/stage1,首次实现用 dev/stage1 导致 join 全空、
  predicate_timing 类为 0,已修)
- 任务语言:各 episode `states.json[0].task_language`
- 卡片:resources/libero/global/ 61 张(frontmatter + How to apply + Falsify)

**全部 decision point 来自同一 suite(libero_spatial_task,碗→盘子)**。
这是 armB2 的实际覆盖范围;跨 suite 泛化不在本数据集内,结论表述时要带此背景。

## 类定义与配额(配额按实际池子校准)

| 类 | 标签 | 判据 | 池 | 入选 |
|---|---|---|---|---|
| predicate_timing | YES | release UNCERTAIN + episode 最终成功(物体确实在目标处 → retreat 卡适用,case A) | 37 | 30 |
| pick_verify | YES | pi0_pick UNCERTAIN(非 perception 型) | 238 | 36 |
| grasp | YES | pi0_pick CONFIRMED_FAILURE("no closure") | 7 | **7(全部)** |
| recovery | YES | move/move_pose FAILURE 短距 或 pi0_doubled FAILURE | 45 | 30 |
| perception | YES | UNCERTAIN + missing_evidence 含 "observation produced no usable object position" | 36 | 17 |
| routine_success | NO | CONFIRMED_SUCCESS 非 release,按 (action,phase,task) 分层 | 754 | 84 |
| terminal_release | NO | release CONFIRMED_SUCCESS | 61 | 20 |
| hard_negative | NO | release UNCERTAIN + episode 最终失败(物体没到目标 → retreat 卡 Falsify 成立,case B),禁排 5 张 retreat 卡 | 14 | **14(全部)** |
| no_card_mechanical | NO | release CONFIRMED_FAILURE(gripper 没开,库内无卡) | 2 | **2(全部)** |

grasp/hard_negative/no_card_mechanical 是全量:池子就这么大,配额不虚标。

## 标注审计中发现并修正的三个错误

1. **容器卡门控误配**:predicate_timing 曾按任务语言含 "bowl" 加
   `flat-box-rigid-bowl-seat`,但 spatial_task 里碗是**被夹对象**、放置目标是盘子;
   该卡 applies_when 是"把扁平物放进/放上碗"→ 从 gold 移除。basket/drawer 卡
   因本 suite 无此类任务自然不触发。
2. **hard negative 判据错误**(最重要):最初用"后续 6 事件内有 CONFIRMED_FAILURE",
   14 个里有 8 个其实 episode 最终成功(短暂 re-pick 失败后恢复)→ 按规格 case A
   它们应是 predicate_timing YES。修正为**以 episode 最终结局为标注权威**
   (labeling 证据,允许;不作在线特征),forward failure 只作佐证注记。
3. **结局 join 键**:stage 重构与 CSV 实际值(dev2)不符 → 改用 dir basename。

## 四项 gold 确认(每个 positive)

1. 卡先于决策存在:库静态,成立;2. applies_when 与状态一致:策划类映射 +
   容器/对象条件过滤;3. How to apply 有意义:expected_use 按类绑定
   (RETREAT/OBSERVE/RETRY/RECOVER);4. Falsify 未成立:hard negative 类
   显式记录 Falsify 成立的禁排卡(hard_negative_for)。
   `auto_audit` 字段记录四项;`audited=True` 表示过了本文件描述的规则审计。

## 已知局限(报告时要带)

- 单 suite(spatial_task 碗→盘子);`is_source_episode` 几乎全 False
  (evidence.cells 来自其他 suite/早期 episode)。
- pre_state_summary.eef 跨事件恒为同值(疑似陈旧)→ 只进 observation_summary
  原文,不参与任何判据;hard negative 判据因此用最终结局而非 eef 距离。
- gold 是"策划规则映射"产物:五类 → 核心卡 + 条件卡。规则已对照卡片
  applies_when 逐条核过(见上文修正记录),但不是人工逐点标注;
  Stage A-3 报告时按规格口径描述为"自动候选 + 规则审计"。
- UNCERTAIN 40 条另存(release UNCERTAIN 但结局未知等),不进评估。
