# Stage F — B2 Prerequisite Ontology(2026-09-20,FROZEN)

来源:**代码全量普查(`rpent/memory/stv.py`)+ 冻结日志普查(76 study
episodes / 939 b2 events)**,非手写回忆。本文件在任何 Stage F benchmark
之前冻结;后续禁止新增类别。

## 0. 代码 → 日志交叉核对

`stv.py` 中 `missing_evidence` 共有 **8** 个可发射字符串(`grep -n
missing_evidence rpent/memory/stv.py` 行号可复核):

| 代码行 | 字符串 | 冻结日志出现? |
|---|---|---|
| 669 | object displacement: has the target left its original support and does it now move with the gripper? | ✅ 99 次 |
| 766 | final relation: object at rest at the intended place location | ✅ 45 次 |
| 953 | whether the residual matters for the next step | ❌ 0 次 |
| 995 | the directed observation never ran | ✅ 108 次 |
| 1033 | object position after opening | ❌ 0 次 |
| 1056 | observation produced no usable object position | ✅ 28 次 |
| 1092 | object displacement does not clearly separate held vs left | ✅ 60 次 |
| 1117 | object rest position vs the intended location | ❌ 0 次 |

**Ontology 只为日志中实际出现的 5 种建 canonical ID**(它们构成 134 冻结
决策点 provenance 的全部观测基础)。代码可发而日志未现的 3 种
(wrist 残差 / 开爪后位置 / 放置静止位歧义)**一律按 UNKNOWN 寻址**,
不建 ID——与"后续禁止新增类别"一致。

## 1. Canonical IDs(6 类,含 UNKNOWN)

| ID | 原始 verifier phrase(逐字) | 中文含义 | 适用 primitive family |
|---|---|---|---|
| **PREREQ_1** | `observation produced no usable object position` | 观测没有产出可用的物体世界位置 | PERCEPTION |
| **PREREQ_2** | `object displacement: has the target left its original support and does it now move with the gripper?` | 物体位移证据缺失:目标是否离开原支撑面并随夹爪移动 | GRASP |
| **PREREQ_3** | `object displacement does not clearly separate held vs left` | 位移证据歧义:无法区分持住与遗留 | GRASP |
| **PREREQ_4** | `final relation: object at rest at the intended place location` | 最终关系未确认:物体是否静止在预定放置位 | PLACE |
| **PREREQ_5** | `the directed observation never ran` | 过程性:请求的定向观测未执行(planner 抢跑) | 横切(验证纪律,作用于当前 phase 的家族) |
| **UNKNOWN** | (无 / 上述之外的代码字符串 / 提取器无法判断) | 前置条件不可判定 | — |

## 2. 语义范围(冻结时的显式决定)

- **PREREQ_1 的范围** = "感知输出不可用"族:无可用世界位置(**或**分割/
  接地不可用——wrong-instance / below-min_score 场景)。依据:该短语在
  pending `object_position` 轮发出(stv.py:1056),根因是观测通道失败;
  Stage E 人工审计中 2 例 `USABLE_SEGMENTATION` gold 归并到此 ID。
- **PREREQ_2 / PREREQ_3 是同一缺失证据的严格/宽松两种读法**(同一
  displacement 问题在 judge 与 pending 轮的两种措辞)。Stage E 冻结提取器
  已将二者归并为 OBJECT_MOVES_WITH_GRIPPER。**路由兼容规则:PREREQ_2 ↔
  PREREQ_3 互通**(详见 `stageF_router_rules.md`)。
- **PREREQ_5 是过程信号**,不指认具体家族:地址侧保留原 phase 上下文;
  卡片侧仅当其内容明确主张"先观测、再行动/再判定"时才标注此 ID。
- 提取器 fallback 曾用的 OBJOECT_HELD / ARRIVED_AT_TARGET 类命名
  (Stage E 审计 gold 中 6 例)在 6 类空间内**无对应 ID → 按UNKNOWN 寻址**,
  原名记入 oracle 地址 note 字段。

## 3. 与 Stage E 提取器输出的映射(地址侧)

| Stage E extractor `missing` | → canonical |
|---|---|
| VALID_TARGET_LOCALIZATION | PREREQ_1 |
| USABLE_SEGMENTATION(人工 gold 2 例) | PREREQ_1 |
| OBJECT_MOVES_WITH_GRIPPER(短语 2 或 3) | PREREQ_2(3 归并,地址不区分) |
| CONFIRMED_SETTLED_TARGET_RELATION | PREREQ_4 |
| OBJECT_HELD / OBJECT_HELD_EVIDENCE / ARRIVED_AT_TARGET | UNKNOWN |
| (无) | UNKNOWN |

**FROZEN at 2026-09-20,benchmark 前定稿;此后不新增类别。**
