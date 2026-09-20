# Stage F — Activation Signature 审计(2026-09-20,benchmark 前冻结)

对象:`analysis/memory_activation_signatures_v1.json`(61 卡,由
`scripts/build_activation_signatures.py` 生成)。本审计在 **任何 F0 检索
打分之前**完成;通过后 sidecar 冻结,benchmark 只读。

## 1. 覆盖与桶分布

- 61/61 卡有签名记录;**58 卡有 failure_origin**,3 卡 origin/prereq/surface
  全空(诚实 UNKNOWN,见 §3)。
- (origin, prereq) 桶:PLACE/PREREQ_4 n=34、PERCEPTION/PREREQ_1 n=14、
  GRASP/PREREQ_2 n=11、TRANSPORT/PREREQ_2 n=9、PERCEPTION/PREREQ_4 n=7、
  PLACE/PREREQ_1 n=7、RECOVERY/PREREQ_4 n=5、其余 ≤2。
- 相对全库 61 卡:perception 寻址空间 61→14(4.4x),displacement 组
  61→19,final-relation 组 61→34。

## 2. 词表迭代史(全部发生在任何检索打分之前,如实披露)

- **v1(宽名词词表)**:GRASP 用 grasp/grip/hold/pick 等泛名词、PLACE 用
  container/basket/bowl 等容器名词 → 61/61 全有 origin(强制覆盖嫌疑),
  桶退化(PREREQ_4 49 卡、PREREQ_2 42 卡),held 状态词把放置期卡错标成
  GRASP。**废弃**。
- **v2(现象锚点词表,冻结版)**:锚点改为卡片自述的**失败现象短语**
  ("contacts without lifting"、"release false"、"predicate not firing"、
  "wrong instance"…),GRASP 不再被状态词(held)或容器名词触发。
- v2 后人工复核发现的 3 个锚点缺口(hangs beyond / re-hooks / fail
  despite)与 1 条规则补充(TRANSPORT→PREREQ_2)见 §3-4,随即补齐后
  重新生成,即冻结版。全程只读 `resources/libero/{global,task_only}`,
  未打开任何 Stage A/C/D/E 的 query/gold/ranking 文件(防火墙由脚本
  构造保证:打开的路径只有 RES/)。

## 3. 空签名卡逐张裁决(6 张初检无 origin → 3 修复 3 保留)

| 卡 | 裁决 |
|---|---|
| held-offset-rotation-reach | 补锚点 "hangs beyond"/"unreachable eef" → TRANSPORT/PREREQ_2(卡自述"correctly grasped object hangs beyond the EEF") |
| reverse-entry-corridor-clearance | 补锚点 "re-hooks"/"extracts it" → PLACE/PREREQ_4(retreat 勾出已放物 = final relation 被破坏) |
| right-front-perimeter-contact | 补锚点 "fail despite" → PLACE/PREREQ_4("bands fail despite clean object placement" = 放置看似正确但任务未决) |
| contact-skill-state-change | **保留空**:任务型卡(fixture 状态切换技能路由),无失败现象学,UNKNOWN 诚实 |
| object-frame-box-to-basket | **保留空**:任务型卡(盒入篮放置框架),无失败现象学 |
| pi0-prepositioned-simple-basket | **保留空**:信任策略先验卡("Pi0 learned place may already match"),无失败现象学 |

## 4. 规则决定(冻结,理由记录)

1. **PREDICATE 只做 surface 不做 origin**:地址侧(Stage E 提取器/b2 短语)
   从不发射 PREDICATE origin;若卡片带 PREDICATE-only origin 将永远不可
   寻址(死值)。词表上 PREDICATE 锚点(predicate/terminated/nonterminal/
   not firing…)同时存在于 PLACE 词表 → 这些卡获得 PLACE origin +
   PREDICATE surface。
2. **TRANSPORT 卡并入 PREREQ_2(2↔3 组)**:本体 §2 已冻结 PREREQ_2↔3
   互通(位移证据缺失/歧义)。carry 打滑/漂移/触墙正是"物体是否随夹爪
   移动"成为悬案的时刻;补救(regrip 或 recenter)都属于该地址的合法
   候选。9 张 TRANSPORT 卡由此可寻址。
3. **PREREQ_5 仅 1 卡命中**(flat-box-rigid-bowl-seat):词表要求
   verify/confirm/observe 类词与 before/not-yet/never 同现,卡自述同时
   满足者极少——保守如实,不放宽。

## 5. 可疑命中复核(逐张读过 applies_when)

- **libero-in-predicate-fires-while-grasped** 的 PERCEPTION 来自
  "destination among several **look-alikes** is uncertain" → 判定**正确**
  (目的地歧义是 grounding 问题),保留 PERCEPTION+PLACE 双址。
- **knob-side-front-zone** 的 PERCEPTION 来自 "wrong **surface**";
  主锚 "look correct but remain nonterminal" → PLACE/PREDICATE 正确。
  双址保留,此处披露。
- **near-goal-contact-regrasp** 的 PERCEPTION 来自 symptom 中
  "**duplicate**"(场景含重复物);卡主体是 nonterminal 后 regrasp →
  PLACE+RECOVERY 正确。双址保留,perception 桶因此 +1(14 卡),
  此处披露。
- **place-order-never-carry-over-placed-object** 仅 "tipped" 命中 PLACE:
  现象是后续 carry 推倒已放物 → 最终关系被破坏,PREREQ_4 判定可辩护,
  保留。

## 6. 区分度检查(桶内)

- 主桶桶内 (phase, action_family) 组合数:PERCEPTION/PREREQ_1 14 卡 12
  组、GRASP/PREREQ_2 11 卡 10 组、PLACE/PREREQ_4 34 卡 15 组。
- **action_family 是弱区分器**:recipe_actions 取卡内全部 cell 的原语并集,
  多数卡都含 pi0_pick/release/move(全库同集倾向)。full-signature
  (origin+prereq+phase+action) 完全相同的卡 29 张/11 组,最大组 8 张
  (均在 PLACE/PREREQ_4)。
- **后果(预注册预期)**:typed address 的作用是**粗筛**(61→14/19/34);
  桶内排序按冻结协议仍由词面打分器完成。已知 Stage E 结论——perception
  query 与卡索引行词面交集为空、>0 截断 → **A1/A2/A3 的 perception
  Recall@3 预期仍为 0/17,失败模式预期 = IN_BUCKET_RANK_FAIL(桶内排序失明,
  非路由失败)**。F0 的主读数因此是 **gold routing recall**(gold 是否进入
  路由后小候选集)与 non-perception 类在桶内是否保持;此预期写入 F0 协议,
  防止事后归因自由度。

## 7. 泄露检查

- 生成脚本只打开 `resources/libero/global/*.md` 与
  `resources/libero/task_only/*`(脚本内路径常量可见);未 import 任何
  Stage A-E 产物。
- 签名字段全部来自卡自有文本(标题/applies_when/symptom/How-to-apply/
  Why/自身 recipe 日志),无 reward、无 ground-truth success、无人工
  事后归因注入。
- 本审计(§3/§5)读了卡片原文逐张复核;未读任何测试 query。

**结论:通过冻结。** sidecar `memory_activation_signatures_v1.json` 自本文件
落盘起只读;F0 benchmark 仅消费。
