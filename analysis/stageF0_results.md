# Stage F0 结果报告:Oracle Typed Routing(2026-09-20)

一句话结论:**给 Memory 挂类型化激活地址(失败起源/缺失前置条件/相位/
动作族)后,感知类金卡 17/17 都能被路由进 14 张卡的小桶(寻址本身成立,
G3 过),但桶内仍用冻结词面打分器排序时感知依旧 0/17(金卡与 query 词面
交集为空,17/17 matched_terms=∅);同时溯源型地址把 21/30 个 predicate
时刻、12/30 个 recovery 时刻系统性错型(b2 当时的待决问题是位移证据,
而有用的卡在讲最终关系),把原本 .967 的强类砍到 .300。按预注册判定树:
G1 挂 + G3 过 → TYPED ADDRESS UPPER BOUND INSUFFICIENT → STOP,F1/F2 不跑。**

## 0. 设计回顾(预注册,零事后自由度)

134 个 C1 冻结决策点;query 固定为部署版贫 query(E0_POOR);卡侧 =
`memory_activation_signatures_v1.json`(58/61 卡有类型,审计见
`stageF_signature_audit.md`);地址侧 = Stage E 冻结提取器输出按本体 §3
canonical 化(origin/missing→PREREQ_1/2/4、phase、action)。四臂唯一变量
= 候选集(A0 全库 / A1 origin / A2 +prereq / A3 +phase+action,兼容规则
见 `stageF_router_rules.md`,跑前冻结)。桶内排序一律 = 部署词面打分
(raw overlap、>0 截断、同分 id 降序)。

**G0 回归锚:A0 逐位复现 C1(R@1 .233 / R@3 .575 / R@5 .592 / MRR
.418 / irr@3 .425,perception 0/17,hardneg 14/14)PASS。**

## 1. 主表(120 gold 点)

| 臂 | 候选集均值 | R@1 | R@3 | MRR | perception | 路由召回(金卡在桶) |
|---|---|---|---|---|---|---|
| A0_LEXICAL(锚) | 61 | .233 | **.575** | .418 | 0/17 | 1.0(平凡) |
| A1_ORIGIN | 22.1 | .067 | .375 | .240 | 0/17 | .725 |
| A2_ORIGIN_PREREQ | 22.1 | .067 | .375 | .240 | 0/17 | .725 |
| A3_TYPED_FULL | 17.1 | .075 | .383 | .250 | 0/17 | .717 |

按类 R@3(A0→A2):pick_verify .944→1.000、predicate_timing .967→**.300**、
recovery .200→**.000**、grasp 0→0、perception 0→0。
A2 分类路由召回:pick_verify 36/36、grasp 7/7、perception **17/17**、
predicate_timing **9/30**、recovery **18/30**。
hardneg:any_top3 全臂 14/14,NO_MATCH 从不触发(任务名词总能在桶内
撞上某卡 >0)。

## 2. 两个失败机制(都在预注册框架内定位)

**(a) 感知:寻址成功,桶内排序失明(IN_BUCKET_RANK_FAIL,预注册预期命中)**
A2 感知桶 = 14 卡,金卡 17/17 在内;但金卡与 query 的 token 交集 17/17
为空 → >0 截断后金卡永不出列,R@3=0。桶内 Top-3 被**同三张卡** deterministic
占据(libero-in-predicate-fires-while-grasped / contact-skill-state-change /
near-goal-contact-regrasp,靠 state/contact 类泛词得分)。即:类型化路由
把"该问谁"的问题解决了,"怎么排序"仍卡在冻结词面通道——与 Stage D/E
的表示瓶颈结论在同一堵墙上。

**(b) release 时刻:溯源地址系统性错型(预注册未单列,如实归档)**
predicate/recovery 类的 30+30 个决策点里,地址 origin=GRASP、prereq=
PREREQ_2(missing="object displacement … move with the gripper")——这是
b2 verifier 在 planner 想 release 时**待决的位移问题**;而金卡
(predicate-fires-after-gripper-retreat 等 4 张 + recovery 3 张)的类型是
PLACE/PREREQ_4(讲放后的最终关系)。桶是全库子集,金卡不在桶里 ⇒ 排名
只能掉不能升:强类被砍 .967→.300。Stage E 审计里人工标注的 origin 与
提取器 90% 一致——即**连"正确"的溯源标签也与 remedy 卡的类型不匹配**:
"失败从哪来" ≠ "哪族的卡能救"。

## 3. 门槛判定(预注册于 `stageF_router_rules.md` §4)

| # | 门槛 | 实测 | 判 |
|---|---|---|---|
| G0 | A0 复现 C1 锚 | 逐位一致 | ✅ |
| G1 | A1/A2/A3 任一 perception R@3 ≥ 10/17 | 0/17(全臂) | ❌ |
| G2 | 该臂 overall ≥ A0−3pp 且 non-perc 降 ≤3pp | .375 vs .575(−20pp) | ❌ |
| G3 | A2/A3 perception 路由召回 ≥ 15/17 | 17/17 | ✅ |
| G4 | hardneg 恶化 ≤5pp | 1.0→1.0 | ✅(名义) |

判定树命中"G1 挂但 G3 过"分支 → **TYPED ADDRESS UPPER BOUND
INSUFFICIENT(IN_BUCKET_RANK_FAIL 归因 + §2b 地址错型归档)→ 协议 STOP**:
不跑 F1(oracle 都不过,automatic router 无意义)、不跑 F2 在线、本轮
不引入 learned relevance scorer(`stageF_router_rules.md` §4 预注册的
进入条件不满足——oracle 路由本身未表现出收益)。

## 4. 附带观察

- **A1 ≡ A2**(桶 22.1、指标全同):地址侧 origin×prereq 近乎确定
  (GRASP→P2、PLACE→P4、PERCEPTION→P1,见 rules §1 联合分布),prereq
  在 origin 之外几乎不带来新信息。
- **A3 作用微弱**(.375→.383):phase/action 兼容只在边际上收紧桶
  (22.1→17.1),救不回错型的基底桶。
- **hardneg 无净化**:类型化路由没有带来 NO_MATCH 收益——桶内总有卡
  与任务名词词面重叠,安全门 G4 只是名义通过。

## 5. 结论

Stage F 的研究问题——provenance 换成**类型化地址**(结构化字段匹配而非
词面相似)能否救回检索——在 oracle 上界处得到否定:

1. **可寻址性成立**:61→14 的感知桶、金卡 17/17 在内(G3 过)。卡侧
   签名质量足够(3 张真任务型卡诚实 UNKNOWN)。
2. **上界不足**:冻结词面桶内排序对感知全盲(0/17),且溯源地址在
   release 时刻与 remedy 卡类型系统性错位(predicate 9/30 进桶),
   净效果 overall −20pp。要在感知上兑现寻址收益,必须同时换掉桶内
   排序通道;而"溯源≠补救族"的错型说明地址键本身也应包含
   surface/相位信息——这两条都超出本轮冻结清单(与 Stage E §6 结论
   相同:必须换检索通道本身)。
3. **不进 F1/F2**:门控协议 STOP;Memory Study 的可执行正结论仍止于
   Stage C(Progress-Gated Retrieval,SR .733→.852)。

## 6. 诚实声明

- 跑前冻结:本体(`stageF_prerequisite_ontology.md`)、签名 sidecar
  (`memory_activation_signatures_v1.json` + `stageF_signature_audit.md`)、
  路由规则与门槛(`stageF_router_rules.md`)全部在本次运行之前落盘;
  F0 运行后零改动、零重跑。
- 词表迭代(宽名词→现象锚点)发生在签名审计阶段(打分前),已在
  audit §2 披露;未读任何测试 query(防火墙由脚本构造保证)。
- §2b 的"地址错型"机制是**看结果后**才定位的——它不改变任何预注册
  判定(判定树按 G1/G3 走),只作为机制解释归档;未据此加跑任何新臂
  (如 surface-typed 地址)。该未测方向仅记为 future work。

产物:`scripts/build_activation_signatures.py`、
`scripts/memory_stageF0_benchmark.py`、
`analysis/memory_activation_signatures_v1.json`、
`analysis/stageF_signature_audit.md`、`analysis/stageF_router_rules.md`、
`analysis/stageF0_results.{json,md}`、`analysis/stageF0_mechanism.jsonl`。
