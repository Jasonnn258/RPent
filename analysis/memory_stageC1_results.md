# Stage C1 结果:Query Sufficiency 离线 benchmark(2026-09-18)

设计(预注册模板+locus 规则)见 `memory_stageC1_design.md`;机器可读全量
`memory_stageC1_results.json`,逐点 query `memory_stageC1_queries.jsonl`。

## 一句话判定

**QUERY ENRICHMENT NOT SUPPORTED(在冻结词面 retriever 下)。** 把在线真实可得的
执行三元组和物理状态块加进 query,R@3 只 +1.7pp(0.575→0.592),perception 17 例
三臂全 0 命中,硬负例错误 retreat 卡 14/14→14/14 没有任何减少。瓶颈不在 query 缺
状态,而在词面检索的**两侧词表不相交**:状态侧词汇(LOCUS/FACTS:perception、
transport、detected、far…)在 61 张卡的索引文本里几乎不存在(perception 0/61、
transport 0/61),加进 query 也无处可匹配。

## 主表(primary,Stage A SHOULD_RETRIEVE=YES,n=120;同一冻结词面 retriever)

| query 臂 | R@1 | R@3 | R@5 | MRR | irrelevant@3 | empty |
|---|---|---|---|---|---|---|
| Q0_POOR(#49 原文重放) | .233 | .575 | .592 | .418 | .425 | 0 |
| Q1_EXECUTION(三元组) | .192 | **.242** | .308 | .278 | .758 | 0 |
| Q2_STATE_GROUNDED(状态块) | .275 | .592 | .608 | .458 | .408 | 0 |

按 class 的 R@3(Q0 / Q1 / Q2):

| class | n | Q0 | Q1 | Q2 |
|---|---|---|---|---|
| pick_verify | 36 | .944 | .000 | .972 |
| predicate_timing | 30 | .967 | .767 | **1.000** |
| recovery | 30 | .200 | .200 | .200 |
| perception | 17 | .000 | .000 | .000 |
| grasp | 7 | .000 | .000 | .000 |

## 三个特别问题(预注册)

1. **perception 17 例命中数:Q0/Q1/Q2 = 0 / 0 / 0。** 状态块已给出
   OBJECT_DETECTED=false、LOCUS=PERCEPTION,但 gold 卡(point-prompt-after-text-
   misground 等)的索引词表是 {point, prompts, masks, segmentation, look-alike,
   duplicate…},与状态词汇零交集——检索器从词面上"看不见"这件事。
2. **硬负例 retreat-in-Top3:Q0=14/14,Q2=14/14(无改善);Q1=8/14 但其代价是
   整体 R@3 崩到 .242,不是可用 trade。** 更丰富的 query 没有把错误 retreat 卡
   挤出去——release+集失败的情形里,query 无论怎么加状态,词面仍命中 retreat 卡
   的高频词(release/predicate/settle)。
3. **failure_locus 提供新信息吗?** 作为**标签**有完美区分(perception 17/17→
   PERCEPTION,grasp 6/7→GRASP,recovery 15/30→TRANSPORT,predicate 10/30→
   PLACE,pick_verify 28/36→UNKNOWN);作为**query 词汇**对词面检索器不可用
   (PERCEPTION/TRANSPORT token 在卡侧 0/61,GRASP 13/61,PREDICATE 15/61)。
   即:locus 是对的信号,载体(词面)接不住。

## Q1 为什么反而更差(重要机制发现)

Q0 的 discriminative 信号几乎全部来自 **trigger reason 短语本身**
("pick_ambiguous…lifted"、"predicate_stalled…")与 task 名词——这些词与卡索引
行天然共词。Q1 把它们换成电报式三元组(PHASE=P_grasp ACTION=pi0_pick
RESULT=false),词面交集骤减,R@3 .575→.242。**在词面检索下,"更结构化"和
"更可检索"是两回事;query 丰富度只有落在卡侧词表内才变成信号。**

## 次集(#49 对齐火,gold 14 + 硬负例 11)

Q0 R@3 = **0.571,与 #49 在线实测逐位一致**(构造管道忠实性通过);Q2 = 0.571
(零变化);硬负例 retreat Q0=11/11、Q2=11/11。在线真实事件上复现主集结论。

## 在线失败类(recovery/grasp)为什么救不回来

recovery(near-miss 纠正类,= #49 RETRIEVAL_WRONG 4 集的同类)三臂全部 0.200:
状态块确实表达了"物体距目标 far(0.36m)、已 release、未进位",但 near-miss 卡
(near-miss-corrective-pick 等)与 generic pick/predicate 卡在 task 词重叠上同分,
靠 tie-break(卡名字典序)进不了 Top-3。**症状/状态文本与"物理近失"之间没有
词面桥梁——这坐实了 Stage A/B 的结构性结论:该瓶颈在检索器表示,不在 query
充分性。**

## 仪器记录(不影响判定)

- b2 verifier 的 `pre_state_summary.eef` 是**陈旧常量**(恒为 home 位,实测偏差
  0.3-0.46m)——Q2 的 PRE 改用 states.json 匹配 entry 的真实 pre-state;b2 仅
  保留 held/last_transport_target(后者也改为优先取 states 的最后 move command)。
  修正前后主表数字不变(坐标 token 本来就不与卡词表相交)。
- Q0 reason 重放忠实包含 #49 的 T4 reason 命名 bug(当前工具名 vs 重复 primitive
  名)——那就是在线真实文本;离线 T6 无信号(在线 0 火)、T7 phase 迁移用 b2
  phase 近似(在线仅 2/94 火)。
- join 完整性:134/134 decision points 成功 join 回源集工具结果,0 跳过。

## Go/No-Go(预注册门槛)

- Q2 vs Q0 R@3 提升 **+1.7pp < 10pp**;perception 命中无改善(0→0);硬负例
  retreat 无改善(14→14)。
- **→ QUERY ENRICHMENT NOT SUPPORTED。Q2 模板不冻结、不带进在线。**
- C3 推论:若 C2(progress trigger)过门槛,在线只跑单变量 O0 vs O2
  (progress trigger + POOR query);若 C2 也不过,不跑在线。

## C1 必答问题(用户 10 问的 C1 子集)

1. Q0/Q1/Q2 的 R@1/R@3?→ 见主表(.233/.575、.192/.242、.275/.592)。
2. richer query 真改善检索吗?→ 否(+1.7pp,门槛内视为零);改善只出现在本来
   就接近满分的 predicate_timing/pick_verify。
3. perception 17 例仍全 0?→ 是,三臂全 0,词表不相交是根因。
4. failure_locus 提供新区分信息?→ 作为标签完美区分,作为词面 query 不可用
   (卡侧 0 命中)。
