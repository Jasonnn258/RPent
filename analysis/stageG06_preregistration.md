# Stage G0.6 — Pre-registration(扩样确认;commit 先于任何 episode)

_承接 G0.5(MIXED/INTERACTION + CASE E:效应小且不稳)。本轮 = 严格扩样
确认,零新机制、零 prompt/trigger/Memory/指标修改(冻结证明见
stageG06_freeze_audit.md;seed 选择见 stageG06_seed_manifest.md)。_

## 1. 研究问题(只有三个)

- **RQ1**:P2 − P0(Generic Refresh 是否真的优于不干预)
- **RQ2**:P4 − P0(Full Memory 是否真的优于不干预)
- **RQ3**(最重要):P4 − P2(真实长期 Memory 内容是否比固定 Generic
  Refresh 提供额外收益)

不回答 WHEN>WHAT;不讨论 Q0/Q3、Jev、Memory Evolution、Skill Admission
(全部暂停)。

## 2. 设计

三臂 P0/P2/P4,DEV 网格 libero_spatial_task × {t3,t5,t9} × s1-s20 × r1 =
每臂 60 matched cells。s1-s10 = G0.5 原行原判(不重跑、不重采样);
s11-s20 = 新集(初始状态 disjointness 已实测)。总新增 90 集。

## 3. 主指标与统计(§7)

Primary = episode SR;严格 paired(task,seed)。报告 success count、SR、
paired W/L/T、McNemar exact p、paired bootstrap 95% CI(10k,seed 20260920,
与 G0.5 同一冻结实现)。主对比恰三个:P2-P0、P4-P0、P4-P2。

## 4. Practical 阈值(§8)

**8pp**(60 cells 下 ≈ 5 个 episode)。显著性与 effect size 都报,但方向
判断优先级 = effect size + paired flips + task consistency,不以 2-3 集
波动建 claim。

## 5. 任务一致性(§9)

分报 t3/t5/t9。机制被认为有稳定方向需 ≥2/3 任务非负;不接受"只靠 t3
拉高 overall 宣称全局有效"。

## 6. 机制与成本指标(§10/§11/§12)

- recovery@3 等 = G0.5 冻结定义,原样复用:recovery@3、time/primitives-
  to-recovery、phase transition within 3、repeated failures after
  intervention、planner turns after intervention、episode success。
- 成本:injected tokens/ep、planner input tokens、planner calls、wall、
  trigger count;保留 P2(~112)vs P4(~765)最终统计;若 P2≈P4 on
  success,计算 token/latency/cost reduction ratio。
- rel@1/@3 继续记录,**仅诊断**(G0.5 已证 P3 rel 更高但 SR 更低)。

## 7. 判定树(§13,预注册,结果出来后机械套用)

- **CASE A CONTEXT REORIENTATION**:P2−P0 ≥ +8pp ∧ P4−P2 < +8pp ∧
  P2/P4 ≥2/3 任务非负 → 主增益 = GENERIC DECISION-POINT REORIENTATION;
  下一阶段冻结 P2 文本,比较触发时机(Periodic/Motion-Stuck/Progress/
  Event-based),研究 WHEN TO REORIENT 而非 WHICH MEMORY。
- **CASE B MEMORY-SPECIFIC VALUE**:P4−P2 ≥ +8pp ∧ P4−P0 > 0 ∧ recovery
  指标不与该方向明显冲突 → PROCEDURAL MEMORY HAS INDEPENDENT VALUE;
  才允许恢复 Intervention-Aligned Retrieval / Jev utility / Embodied
  Admission / Memory Evolution。
- **CASE C LOCAL RECOVERY ONLY**:P2≈P4 on SR 但 P4 recovery@3 明显高于
  P2 且 P4 recovery latency/primitive count 更低 → MEMORY LOCAL-RECOVERY
  EFFECT: SUPPORTED;MEMORY FINAL-SUCCESS EFFECT: NOT SUPPORTED;后续
  Memory 研究目标改为 local recovery efficiency。
- **CASE D NO ROBUST EFFECT**:P0/P2/P4 全部两两差异 <8pp 且 paired 无
  稳定方向 → G0/G0.5 高数字 = high baseline + small-sample variation;
  停止三任务上的 Memory/Refresh patching;下一阶段找更有区分度的
  hard evaluation set。
- **CASE E GENERIC > MEMORY**:P2−P4 ≥ +8pp → MEMORY CONTAMINATION/
  DISTRACTION 成为主要候选解释;Decision-Point Context Reorientation
  优先;Memory retrieval 降级为负结果/analysis。
- **CASE F MIXED**:top 差异仍在 ±8pp 内但不同任务方向明显不同 →
  TASK-CONDITIONAL EFFECT;不做 global claim;先分析哪些 failure/task
  family 对 Refresh/Memory 响应不同。

多 CASE 同时满足时按上述顺序 A>B>C>D>E>F 取第一个全条件匹配者;
边界情形(恰好 =8pp)计入满足该侧条件。

## 8. recovery@3 特别检查(§14,60 cells 上必答)

1. P4 recovery@3 是否仍高于 P2?
2. 差异来自哪个任务?
3. recovery@3 提升是否最终转换成 SR?
4. 若不转换:是后续再次失败,还是任务已近成功上限(t5/t9 封顶)?

## 9. 运行纪律(§15/§16)

90 集全部完成后再分析;不因中途任一臂领先提前停止;唯一允许的提前停止
= 严重 infrastructure failure。429/API timeout 记录+重试+不算 policy
failure;infra 指纹(0-turn/connection error/outage)单独分类;genuine
policy failure 不重跑;最终 0 unresolved infra cells 或明确记录
infra_missing。8 workers(沿用 G0/G0.5)。

## 10. 产物(§17/§18)

stageG06_freeze_audit.md ✓ · stageG06_seed_manifest.md ✓ · 本文 ·
stageG06_runs.csv · stageG06_events.jsonl · stageG06_results.md(含
§18 两张表:臂表 Arm|Success|SR|recovery@3|tokens/ep|turns|walltime;
对比表 Comparison|ΔSR|paired W/L|McNemar p|bootstrap 95% CI)·
stageG06_direction_decision.md。

## 11. 完成后(§19/§20)

十问作答 → direction_decision.md → **STOP**。不自动恢复 G1、不启动 G2、
不调用 Jev、不设计 Memory Evolution、不加新臂。本轮唯一目的 = 确认
G0.5 的方向,不是追求更高 SR。
