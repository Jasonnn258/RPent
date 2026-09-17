# Stage B1 设计 + B0 兼容性审计(2026-09-17)

上游:Stage A 结论(`memory_stageA_results.md`)—— ACCESS 100% 断 / TRIGGER 0/120 /
RANK Q3 R@3 0.592。本轮**不做 executable 强执行**(Q3 检索错误率仍高,强执行会把
retrieval error 与 adoption error 混在一起),只做 soft 注入的四臂在线对比。

## B0 复用兼容性审计(结论:可复用,限 t3/t5)

B0 = 历史行为(错路径 prompt + 开局浏览 + 无决策时检索)。

| 项 | armA 历史(候选 B0) | 本轮 memB | 兼容 |
|---|---|---|---|
| 模型/端点 | anthropic:glm-5.3-flash @ open.bigmodel.cn/api/anthropic | 同 | ✓ |
| max-turns / max-tokens | 40 / **24576**(09-15/16 批) | 40 / 24576 | ✓ |
| SM1 / 其他 gate | RPENT_STRUCTURED_MEMORY=1,无 OVPM/OVPM2/REASON/DUAL | 同(memB0 同 armA) | ✓ |
| 代码 | commit ≤ 3edd0bd | HEAD | ✓(见下) |
| suite/seeds | libero_spatial_task s1-10 r1 | 同 | ✓ |

代码漂移核验:armA 批(09-06 dev / 09-07 heldout / 09-08 stage1 / **09-15,16 stage1 补跑**)
与当前 HEAD 之间只有 OVP-M/B2 系列提交;其中 cc4be82(api_loop B2 接线)与
3edd0bd(stv.py)全部 gated 于 RPENT_OVPM2,arms A/B 路径不变(commit message 明示,
diff 复核);prompt 文件自 09-06 起无改动。**09-06/07/08 批没有 --max-tokens 24576**
(f2c8592 之前启动),故只有 **09-15/16 批(t2/t3/t5, 37 集)严格可比**。

**B0 构成**:t3/t5 ← 09-15/16 armA stage1 行(stage1 CSV 行,直接配对);
t9 无可比行(老 t9 批全在 09-06)→ 补跑 memB0 × t9 × s1-10(10 集,配置=armA)。

## 臂与 env

| 臂 | env(在 SM1=1 之上) | 回答 |
|---|---|---|
| memB0 | (无,=armA) | B0 基线(t9 补跑) |
| memB1 | RPENT_MEMORY_ACCESS_FIX=1 | 修路径本身 |
| memB2 | + RPENT_MEMORY_TRIGGER=1, RANK=Q0_FIXED | 决策时触发+词面 |
| memB3 | + RPENT_MEMORY_TRIGGER=1, RANK=Q3 | 决策时触发+结构化 |

任务:t3(五类全)/ t5(predicate+pick)/ t9(perception diagnostic);
seeds 1-10,r1。新集 = 3×10×3 + 10 = 100。

## Trigger(冻结 v1,B2/B3 完全一致)

评估时机:每个 turn boundary,只看"自上一 boundary 以来新到的工具结果";
仅回答"现在是否该查长期 Memory",不决定查哪条。
冷却:触发后 2 个 boundary 内不再触发;每集上限 6 次;第一个 primitive 动作前不触发;
memory 文件工具不触发。

| 规则 | 信号(全部 harness 可见,无 task id) |
|---|---|
| T1 primitive_failure | pi0_pick/pi0_doubled success=false;move_to/move_pose final_dist_m>0.03;工具 is_error |
| T2 pick_ambiguous | pi0_pick success=true 但 post_min_ascent_m<0.05 |
| T3 predicate_stalled | release 后 libero_terminated 未置真且后续仍有动作 |
| T4 repeated_no_progress | 同一 primitive 连续 ≥3 次;或累计 ≥2 次 pick 失败 |
| T5 perception_insufficient | segment found=false / back_project world_error |
| T6 recovery_pending | SM1 recovery 规则 precondition 满足未处理 |
| T7 phase_stalled | 同 phase 内 ≥8 个 primitive 动作无迁移 |

## Retrieval(冻结)

- **Q0_FIXED**:MEMORY.md 索引行 + 文件名词面 token 交集,>0 取 top3(Stage A 移植)。
- **Q3**:bge-small-en-v1.5(本地 CPU,与 Stage A 同编码器)语义 top-20 →
  结构化 rerank,权重 2.0/0.6/0.4/0.5/0.4 与 Stage A 完全一致。**禁止依在线结果调权**。
- 注入:top-3 卡(title/applies_when/How to apply/Falsify)+ soft 措辞
  ("context, not an instruction"),走 SM1 同款 throttled injection 通道。
- 在线 query 构造(仅 harness 可见字段):phase / last_action / 触发原因 /
  结果关键字段(success、libero_terminated、final_dist_m、found…) / task_language。
  与离线 schema 的差异(无 B2 verdict 字段)如实记录。

## 事件记录

每集 `memory_events.jsonl`(spec §6 全字段);planner_next_action / followed_top1 /
followed_any_top3 / verification_result / gold_memory_ids 一律**事后标注**,
运行时不可见。调度器 CSV 加 mem_triggers / mem_latency_mean_ms / mem_top1s。

## 指标与判定(分析脚本 analyze_memory_stageB.py)

五层:Task(SR/turns/wall)→ Trigger(count/coverage/unnecessary/overhead)→
Ranking(online relevant@1/@3、irrelevant@3,事后 gold)→ Adoption
(followed_top1 / followed_any_top3 / retrieved-but-ignored)→ Outcome
(helped/neutral/harmful,配对 + verification 事后判)。

失败分解:ACCESS_FAIL / TRIGGER_MISS / RETRIEVAL_WRONG / RETRIEVED_BUT_IGNORED /
MEMORY_WRONG / EXECUTION_FAIL / NO_RELEVANT_MEMORY / SUCCESS。
核心问题:B3 中"正确 Memory 已进 Top-1/3 但 Planner 未采用"的量。
最终判定:TRIGGER / RANKING / BOTH / NEITHER SUPPORTED + EXECUTABLE MEMORY NEXT: YES/NO。

## 纪律

不修 Q3 权重、不修 Global Memory、不加 task-specific rule、不加 perception feature、
不强制执行、不换 planner、不 rerun-until-success;infra 失败重试 ≤3 单独记录;
所有 attempts 保留。perception 类只记录不修(failure-locus 字段只进分析)。

## Smoke 记录(2026-09-17)

- **attempt 1**(dir `20260917-04:35:40_..._memB3_..._t3_s1_r1`,保留在盘):全链路
  验证通过(access fix 生效、turn 15/34 两次 phase_stalled 触发、Q3 在线排序、soft
  注入后 planner 在 thinking 中逐卡自主裁决)。但 finalize 有 instrumentation bug:
  PhaseTracker.current_phase 是方法而非属性,retrieval.py 少写括号 → 绑定方法进了
  event 的 phase 字段,json.dumps 崩溃,memory_events.jsonl 写空,2 个事件丢失,
  CSV 行 mem_triggers=0。**已修**(加括号 + finalize dumps 加 default=str 保险)。
  该行已从 CSV 删除、该格用修复后代码重跑(这是仪器故障替换,不是
  rerun-until-success:旧 attempt 的 policy_fail 结果保留在盘,新跑任何结果都算数)。
  副作用:绑定方法文本曾污染 Q3 query(`<bound method ...>` 进了 query 字符串)
  且 W_PHASE 加分永远不触发 —— 即 attempt 1 的排序略失真,重跑后为正确行为。
- T4 `repeated_no_progress`(同 primitive 连续 ≥3)按冻结规格保留:waypoint 式
  连续 move_to 是正常行为也会触发 —— 这不是 bug,是 Trigger 层
  `fires_without_should_signal`(unnecessary)指标要量化的对象。
