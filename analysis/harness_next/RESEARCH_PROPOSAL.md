# RPent 下一阶段研究定位与路线决策（Research Proposal）

> 2026-10-09 | 版本：v0.1 研究设计 / 未冻结、未测试 | 路径：`analysis/harness_next/`。
> 本文件是**候选研究方向的实质论证**，不包含实验方案、实现任务或新方法收益。所有声称的原创点都是待核验假设。
> 配套：`RELATED_WORK_AND_NOVELTY.md`、`ARCHITECTURE_PROPOSAL.md`。

## Executive decision

**方向建议：HOLD S1 Twin-Swap DEV0；PRIORITIZE Persistence-Aware Evidence Governance for Self-Evolving Embodied Harnesses。**

- S1 memory v2.1 完整保留。暂缓 P-1 新 BDDL/包缓存注册、P-2 Twin-Swap 前缀录制、P-3 专用 runner，且不自行批准后续 DEV/TEST。
- 不将 S0 的 `MEMORY NECESSITY NOT SUPPORTED` 外推到新任务族：它只评价原 t3/t5/t9 决策点。
- 原 Stage R §36 Hard STOP 生效；本提案**不改写** Stage Q/R/H 的判定，不开启 recovery、classifier、verifier、world model、planner 变更、SFT/RL 等。
- 下一步仅评议本研究定位、创新边界和架构的科学性；是否投入实施需另行批准。

## 1. Motivation / Problem

机器人动作具有执行随机性，观测与物理事实之间有间隔，工具返回“success”也未必能支持“稳定成功”或“完成任务”。同一个失败事实可用于当前停止/重试的讨论，却未必足够支持将 Skill 修改作为永久知识。

RPent **已观察**：Stage R 24 个失败事件中 E14、P5（均 t9）、A1、U4；acquisition−stable gap 同动作 34.4pp、重采样 37.5pp；Stage Q restore class-level 一致性 10/14。因此核心难题是**证据强度的层级与适用范围**。不能把这些结果解释成“新 Harness 提升成功率”的直接证据。

**Research Question**

> Under stochastic physical execution and imperfect observations, what evidence is sufficient to authorize an embodied harness's immediate runtime judgment versus a durable skill/harness update?

简称：**同一份物理证据，什么时候可以被用于哪一种决策？**

## 2. 核心 Insight

**Evidence sufficiency is action- and timescale-dependent.**

同一抓取片段里：
- t1 物体刚离桌面 → 可以支持 acquisition 暂时成立，不能证明 stable；
- t1-t2 持续保持 → 可支持有限时间窗口的 stable claim，下一秒仍有失效可能；
- t3 物体放在目标处、且观测证据充分 → 才可能支持任务完成；
- n 个重复失败的 evidence → 在明确采样条件下推断 persistence，但不足以证明 Skill 原理有缺陷或可被修改。

因此错误不只来自 Critic 的漏检/误报，还来自**把低强度证据使用在高影响决策上**。

## 3. 三个互相支撑的核心创新候选（Research Hypotheses）

**I. Temporal Evidence Claims**
将状态声明显式关联 `validity horizon`、支持证据、来源可见性、`PROVISIONAL/CONFIRMED/CONTRADICTED/EXPIRED/UNKNOWN`。论文级新意仅在于物理状态可撤销/有期限与后续决策权限的耦合，不声称首次引入 evidence ledger / temporal monitor。

**II. Persistence-Aware Attribution**
显式区分 observation、失败重复性、动作特异性、策略持续性和 repairability；当重复试验受状态重建偏差影响时降低声称的因果强度。与 EmbodiSkill 的“execution lapse / skill defect”分流相比，候选增量是**量化有限物理重复证据及其适用边界**，尚需更严密 novelty audit。

**III. Decision-Dependent Evidence Eligibility**
复用一个证据面，但以 Runtime Gate 与 Evolution Gate 分开判定。Runtime Gate 管当前执行结果可否被消费；Evolution Gate 管跨 Episode 经验能否进入候选更新审查。只有独立验证与晋升授权后才可能改变长期技能。双门设计本身已有先例，候选原创点在于其由持续性与证据质量驱动、决策层级明确。

## 4. 架构主线（概念）

```text
Frozen VLA + Existing Planner
    ↓ legal sensor/action/tool stream
Evidence Ingestion & Provenance Firewall
    ↓
Temporal Outcome Claims (+ time horizon, Unknown)
    ↓
Persistence/Attribution Layer (+ uncertainty, reconstruction fidelity)
    ↓
Dual Evidence Eligibility
    ├─ Runtime: observe / hold / allow forward progress (proposal only)
    └─ Evolution: quarantine / candidate review / abstain
    ↓ [future separate authorization]
Validated Harness Evolution: critic / skill / context candidates
```

此处 `Outcome Belief` 暂指证据约束的状态声明；没有独立校准的概率后验前不使用 Bayes/confidence 保证措辞。防火墙：模拟器隐藏物体坐标和 `check_success` 只供离线科学审计，不能进入 Planner/Critic 在线动作决策信息面。

## 5. 研究机会与替代路线比较

| 方向 | RPent 动机与已有基础 | 主要风险 | 当前建议 |
|---|---|---|---|
| Persistence-aware Evidence Governance | Stage Q/R 的时序稳定与失败持续性；现有 tool logs、sim 离线评价与 B2 框架 | 可能与 RegenHarness/CheckVLA 的局部机制重叠，尚无行为 headroom 验证 | **第一优先：方法论、创新、架构论证** |
| Outcome-grounded Skill Evolution | 可借鉴 Zetta、SkillOpt 验证与回退 | 新 Skill 的改善与故障根因目前无直接支持；Stage R STOP | **第二层长期候选** |
| Historical Memory / Twin-Swap S1 | 清晰的专门历史依赖任务和可审计 S1 v2.1 | 需新 BDDL/prefix/runner，且原任务族无 memory 必要证据 | **暂停保留** |
| General Graph Memory / world model | 理论可能有大空间 | Stage H 的 Graph 表征未过门，缺明确任务必要性；成本高 | 不优先 |
| Re-implement Zetta critic/recovery loop | 公开代码可复用 | 创新重合，可能复刻已知系统 | 不立项为独立创新 |

## 6. 当前可交付的研究论证 VS 尚未获证之处

**已具备：** 原始实验报告与源码线索、跨工作竞争表、方法论、三项候选创新、四层架构及信息权限边界。

**尚未具备：** 原创性最终确证、各工作同规模/同条件效果对比、合法在线传感器对上述全部状态的可辨识性、无改进基线的 Headroom、新架构的任何定量收益。

**不开展：** 新实验预注册、样本/门槛设计、rollout、模型训练、物理工具改造、恢复策略、自动 Skill 修改、重判 Stage R。

## 7. 用户审阅的研究决策点

1. 是否同意 **Persistence-Aware Evidence Governance** 作为下一阶段研究定位，而非立刻将它称为“已证明创新”？
2. 三个候选贡献中，是否将 **Persistence-Aware Attribution** 确认为研究主线，另外两项作为支撑，而不是平铺三个系统模块？
3. S1 是否维持 `ON_HOLD`，不执行 P-1/P-2/P-3，直到新的明确批准？
4. 进一步工作若需从“架构论证”升级到实现/实验，须单独立项并明确与 Stage R Hard STOP 的隔离边界。

## 8. 参考与审计入口

- 内部：`analysis/STAGE_R_FINAL_REPORT.md`, `STAGE_Q_FINAL_REPORT.md`, `analysis/STAGE_H_FINAL_REPORT.md`, `analysis/memory_s0/MEMORY_NECESSITY_AUDIT.md`.
- 外部：`RELATED_WORK_AND_NOVELTY.md` 逐文献原文链接，`ARCHITECTURE_PROPOSAL.md` 逐层责任与数据契约。
