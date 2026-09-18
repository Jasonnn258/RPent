# Stage C1 设计:Query Sufficiency 离线 benchmark(2026-09-18)

上游:Stage B1 结论(`memory_stageB_results.md`)——B2/B3 的在线 query 过于贫瘠,
结构化排序对词面零增益;73% 误触发是 trigger 缺 progress 维度。用户拆成两个独立
假设,本轮先离线分别验证:

- **H1(本轮)**:在线检索失败部分因为 query 没有描述"机器人当前实际发生了什么"。
  只加入在线真实可得的执行/状态字段,即使仍用便宜词面检索,相关 Memory recall 也应提高。
- H2(C2,另行):action repetition ≠ no progress,真正该查 Memory 的条件是实际物理
  进展偏离预期。

**冻结纪律**:固定 retriever 只变 query;禁止换 embedding model / 换 retriever /
LLM reranker / 修改 Memory 内容 / LLM 自动总结 query。三种 query 全部由代码模板
确定性构造。

## 数据集

| 集 | n | 来源 | 用途 |
|---|---|---|---|
| 主集 YES | 120 | Stage A `memory_retrieval_queries.jsonl`(pick_verify 36 / predicate_timing 30 / recovery 30 / perception 17 / grasp 7),每行 join 回源集 `b2_events.jsonl`(episode,turn)拿 pre_state_summary / observed_change / missing_evidence,join 回 `states.json` 拿该 step 的完整 result dict | R@k / MRR / irrelevant@3 按 class 拆分 |
| 硬负例 | 14 | 同文件 should=NO 且 hard_negative_for 非空(release UNCERTAIN + 集失败 → retreat 卡族被 Stage A 规则证伪,gold=[]) | retreat 卡是否进 Top-3(越少越好) |
| 次集 #49 对齐火 | 25 | #49 memB2/B3 `memory_events.jsonl` 中与 SHOULD 时刻对齐的事件(14 gold + 11 hard-negative,`analyze_memory_stageB.annotate_gold` 同规则) | 在线真实 query 上的同题复测;状态字段取自该集 states.json/segments(memB 无 b2_events) |

#49 的 69 个未对齐火不是 SHOULD 点,不进 C1 指标(那是 C2 的对象)。

## 三种 query(确定性模板,冻结)

设该 decision point 的:phase、action(=last primitive)、result dict、task_language、
b2 pre_state_summary(eef/gripper_opening/held/last_transport_target)、observed_change、
最后一个 segment 的 found/world_xyz。

**Q0_POOR** —— 逐字复现 #49 在线 `_query_text`(retrieval.py `_obs_summary` 格式
+ `_trigger_reason` 输出;reason 由 #49 冻结规则在该 tool result 上重放得出,
**含已知 T4 reason 命名 bug 的忠实复现**——那就是 #49 在线真实发出的文本):

```
phase={phase}; last action={action}; result fields={success/libero_terminated/
final_dist_m/found/world_error/min_gripper_opening 中存在者}; task: {tl[:110]}
| {reason}
```

**Q1_EXECUTION** —— 仅加执行三元组(phase/action/primitive_result),无状态:

```
PHASE={phase} ACTION={action} RESULT={prim_result} | task: {tl[:110]}
```

prim_result:pi0_pick/pi0_doubled→success 布尔;move_to/move_pose→final_dist_m;
release→libero_terminated;segment/back_project→found;其余→error/ok。

**Q2_STATE_GROUNDED** —— Q1 + 在线可得状态块(全部来自 b2 verifier 当时的
pre_state_summary、states.json result、segments 观测;**禁 simulator privileged
state,禁集结局**):

```
PHASE=.. ACTION=.. RESULT=.. | task: ..
PRE: eef=[x,y,z] gripper_opening=g held=true/false/unknown
POST: eef=[x,y,z] gripper_opening=g predicate=true/false
DELTA: {observed_change}
FACTS: OBJECT_DETECTED=t/f/unk OBJECT_LIFTED=t/f/unk OBJECT_MOVES_WITH_GRIPPER=t/f/unk
  PREDICATE=t/f OBJECT_TARGET_RELATION=near(0.04m)/far(0.12m)/unk
  EEF_NEAR_TARGET=t(0.02m)/f/unk
LOCUS: {PERCEPTION|GRASP|TRANSPORT|PLACE|PREDICATE|UNKNOWN}
```

派生规则(冻结):
- OBJECT_DETECTED:该点之前最后一个 segment found 值;无 segment→unknown
- OBJECT_LIFTED:pick diagnostics post_min_ascent_m≥0.05→true,<0.05→false;
  否则 held=true→true,held=false/unk→unknown
- OBJECT_MOVES_WITH_GRIPPER:held 非空按 held;null→unknown
- PREDICATE:该点 libero_terminated
- OBJECT_TARGET_RELATION / EEF_NEAR_TARGET:最后 segment world_xyz / pre-eef 对
  last_transport_target 距离,阈值 0.05m;无目标→unk

**failure_locus 判定规则(冻结,按序取第一个命中;task-free):**

1. OBJECT_DETECTED=false,或 missing_evidence 含 "no usable object position" → PERCEPTION
2. action=pi0_pick 且 (RESULT=false 或 OBJECT_LIFTED=false) → GRASP
3. action∈{move_to,move_pose} 且 final_dist_m>0.03 → TRANSPORT
4. action=release(或 phase=P_place/P_verify):OBJECT_TARGET_RELATION=far→PLACE;
   near 且 PREDICATE=false→PREDICATE;unk→UNKNOWN
5. 其余 → UNKNOWN

(正字法注:规格原文 PREDIATE 为笔误,按 PREDICATE 实现。)

## Retriever(冻结)

`_q0_fixed` 逐字移植(#49 词面:query token ∪ task token 与 MEMORY.md 索引行
∪ 文件名 token 的交集大小,>0 取 top-3,tie 按卡名逆字典序);tokenizer/STOP/
load_cards/load_index 直接 import `rpent.memory.retrieval`,三组 query 完全同一
实现、同一 Memory bank、同一候选全集。top-k<3 时按实际返回数计(词面无交集→
0 张,这正是 Stage A perception 0-hit 的现象)。

## 指标与门槛

只在 SHOULD_RETRIEVE=YES 上:Recall@1/@3/@5、MRR、irrelevant@3(=Top-3 无 gold),
按 perception/grasp/transport(place)/predicate/pick_verify/recovery 拆分;
17 个 perception cases 的 Q0/Q1/Q2 命中数单列;硬负例:RETREAT_CARDS 进 Top-3
比例(应随 query 变丰富而下降)。次集 #49 对齐火同表单列。

**Go/No-Go(预注册)**:
- Q2 vs Q0 的 Recall@3 无实质提升(主集 <10pp)**且** perception 命中与硬负例
  retreat-in-top3 也无改善 → QUERY ENRICHMENT NOT SUPPORTED,不进在线;
- Q2 明显提升(≥10pp,或 perception 17 例从 0 命中到有实质命中且硬负例不恶化)
  → 冻结 Q2 模板,C3 在线阶段禁改。

## 已知限制(如实报告,不修)

- Q0 reason 重放不含 T6(recovery_pending 需要在线 tracker;离线无对应信号,
  T6 在 #49 实测 0 火,无影响)与 T7 的 phase 迁移用 b2 phase 近似(tracker 不在;
  T7 在线仅 2/94 火)。
- #49 次集的 Q2 状态块无 b2 pre_state_summary(memB 无 OVPM2),held 用
  gripper qpos 推断(|qpos|<0.01 视为闭合),documented。
