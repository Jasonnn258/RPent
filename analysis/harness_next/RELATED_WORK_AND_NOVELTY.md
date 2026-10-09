# RPent 下一阶段：相关工作与创新边界（研究设计；不含实验方案）

> 更新：2026-10-09 | 状态：research proposal / literature positioning，非通过实验证实的贡献。
> 项目基线：RPent `fddf5fd`；`analysis/STAGE_R_FINAL_REPORT.md`、`STAGE_Q_FINAL_REPORT.md`、`analysis/memory_s0/{MEMORY_NECESSITY_AUDIT,RPENT_CAPABILITY_AUDIT,REFERENCE_CODE_AUDIT}.md`。
> 所有外部结果按原作者报告表述；跨基准数值不可直接比较。源码级检查仅限本轮确实阅读过的 Zetta、EmbodiSkill、SkillOpt 公开仓库；其余按论文摘要/项目页标为 [P]。不得将拟议机制写成已完成的 RPent 能力。

## 1. 研究动机（内部已测证据）

- Stage R：24 个失败事件分成 E=14（execution-ephemeral）、P=5（policy-persistent，均 t9）、A=1（action-specific）、U=4（unresolved）；均为该队列与预注册定义下的分类。平均 `q_same=.302`，`q_policy=.323`，增益约 2.1pp，不能声称重新采样显著优于原动作重放。
- Stage R：acquisition 与 stable 结果差 SAME +34.4pp、POLICY +37.5pp。一个“抓到”的事件并不保证后续稳定。
- Stage Q：restore 的 transition-class 一致率 10/14=.769，低于 .90 资格门；涉及恢复态物理反事实的推断标记 APPROXIMATE。不可把反复回放当完美的因果根因证明。
- Stage H：Graph 表征在既定预注册下 NOT SUPPORTED，且强泛型基线领先卡片和图。S0：当前任务族 9 个决策点审计不支持“Memory 必要性”；不外推至所有任务。
- 因此，**已有证据支持“物理执行结果不稳定且误读成本可能较高”的动机，不支持“某个新 Critic/Skill 更新方法有效”的结论。**

## 2. 文献竞争边界

| 工作 | 已有方法、能力边界 | 可参考而不能据为原创的部分 | 来源等级 |
|---|---|---|---|
| Zetta ζ (2026) | Frozen VLA；action-frequency critic、rollout-level diagnosis / recovery proposal、validation-gated skill evolution；Role1 独占高层动作批准；shadow replay + paired same-seed + heldout 晋升 | 高频 Critic、Recovery、三个时间尺度和受控 Skill Promotion | [S] README、`robots/libero/critic_runtime.py`、`role1_recovery.py`，另 [P] arXiv |
| EmbodiSkill (2026) | Skill-aware reflection 区分 skill defect / execution lapse，针对性更新正文与附录；公开实现主要指向 ALFWorld/EmbodiedBench | “执行失误≠技能缺陷”、根据轨迹反思演化 | [S] README + RPent S0 代码审计；[P] arXiv |
| SkillOpt (2026) | Frozen agent 的外部文本 Skill 可优化；候选编辑经过验证集 acceptance/rejection；有跨轮更新纪律 | Skill 文本作为可优化参数、heldout 晋升、拒绝缓冲 | [S] README + RPent S0 审计 |
| SHAPER (2026) | 联合演化外部 Skill 和 context-code harness，保持模型参数冻结 | “联合优化 Harness 本身” | [P] arXiv 2608.11350 |
| RegenHarness (2026) | Proposal / dispatch / observation / verification / commitment / bounded recovery；版本化事实、role isolation、commit gate、可回退 Harness RSI | Evidence-gated commitment / provenance / versioning / 自修改门 | [P] arXiv 2609.27612 |
| CheckVLA (2026) | action-conditioned world model + conformal risk calibration，长序列执行期干预，延迟感知修复 | 动作条件化、校准风险阈值、事件式记忆 | [P] arXiv 2607.26789 |
| SafeManip (2026) | LTLf 有限轨迹监控，抓取/释放稳定性等时序安全契约 | 把时间谓词和稳定性监控作为“全新方法” | [P] arXiv 2605.12386 |
| VASO (2026) | 形式化 Skill Contract / model checking / counterexample 驱动的 Skill 修订 | Formal contract 和验证后技能修订 | [P] arXiv 2606.05395 |
| CommitFlow (2026) | Semantic Commitment Monitor 对照阶段条件、local correction 与 gain calibration | 语义提交门 / 未满足前置条件时阻断后续动作 | [P] arXiv 2609.21908 |

论文与仓库：
- https://arxiv.org/abs/2608.16590 / https://github.com/air-embodied-brain/Zetta-Embodiment
- https://arxiv.org/abs/2605.10332 / https://github.com/air-embodied-brain/EmbodiSkill
- https://arxiv.org/abs/2605.23904 / https://github.com/microsoft/SkillOpt
- https://arxiv.org/abs/2608.11350 (SHAPER)
- https://arxiv.org/abs/2609.27612 (RegenHarness)
- https://arxiv.org/abs/2607.26789 (CheckVLA)
- https://arxiv.org/abs/2605.12386 (SafeManip)
- https://arxiv.org/abs/2606.05395 (VASO)
- https://arxiv.org/abs/2609.21908 (CommitFlow)

## 3. 缺口分析：哪里可能还有可发表的独立贡献？

### 已被相关工作覆盖，不宜作为主创新

1. “冻结 VLA + critic + recovery + heldout”与 Zetta 重叠。
2. “将失败分成执行 lapse / skill defect”与 EmbodiSkill 重叠。
3. “证据提交门 + 版本化记忆 + 可回退更新”与 RegenHarness 重叠。
4. “chunk 异常预测、置信阈值、时序稳定检查”与 CheckVLA/SafeManip 重叠。
5. “Graph/Memory 增强一般会变好”既缺 RPent 本地前提，又已有多项负结果。

### 拟议的新机制（均为待证实的创新候选）

**C1. Decision-dependent evidence sufficiency（决策依赖的证据充分性）**：
同一事件证据分别对“当前是否继续动作”“是否报告技能完成”“是否允许长效 Skill/Harness 更新”给出不同授权判定，且允许显式 Unknown/Abstain。新意不能停留在两个 Gate 的工程拆分；需要把不同错误代价、证据时效、估计不确定性写入明确的判断语义。

**C2. Persistence-aware causal humility（持续性证据与归因克制）**：
将一次失败的观测事实、失败再次出现的经验概率、动作特异性/策略持续性以及“改变 Skill 能否改善”的可修复性严格分开。禁止从“多次失败”直接推理“策略错误”或“永久 Skill 需要修改”；状态重建保真不足时降级对因果的声称。差异化核心：Stage R 已有失败持续性实证基础，而相关工作常把诊断后的错误分类直接交给技能更新器；此判断需后续更细文献核验。

**C3. Temporal and retractable outcome claims（时效化、可撤销的执行声明）**：
“acquired”“stable-grasp”“task-completed”“skill-defect”分别带时间窗口、可观察支持、适用决策和失效条件；证据被反驳或过期须降级而非永久继承。版本化/提交协议已由他人提出，因此本项要突出物理不稳定下的 *time-to-validity* 与 *decision eligibility*，而不主张首次提出 ledger。

**C1+C2+C3 的互相依赖**：C3 管证据对象，C2 管失败持续性及归因不确定，C1 管何种证据可驱动何种级别的系统行为。任一模块单独构成的论文新意暂未确立。

## 4. 独创性风险及必须保留的科学边界

- 相关工作若已经形式化“长期更新比即时干预需要更强证据”，C1 需降级为系统设计基础，聚焦 C2 的统计/因果语义。
- “Outcome Belief”目前仅是概念名称；没有经过校准的后验分布就不应自称 Bayesian confidence。可先采用有证据指向的状态和 uncertainty metadata。
- Stage R 是特定 t3/t5/t9 失败队列；P 类全部 t9。不能宣称跨环境、跨模型通用。
- Stage Q 的 snapshot restore 敏感性意味着动作重放可以提供有限机制证据，但不是精确的 counterfactual oracle。
- 运行时只能消费 agent 可合法观察的数据；`sim_measurement`、`check_success`、BDD L/实例真值只进入**离线审计与评价**，不允许变相泄漏。
- 目前没有新模型、新 Harness 的实验收益，严禁将候选创新改写为实测贡献。

## 5. 结论（仅是研究方向判定）

**优先论证“Persistence-aware decision-dependent evidence governance”**，将 Evidence Contract 视为信息底座、Persistence-aware attribution 视为最有 RPent 特征的候选机制、Runtime/Evolution Eligibility 视为核心决策接口。是否有发表级创新须等待概念充分形式化与竞争工作更严格对齐；目前不进入实验设计。

**S1 twin-swap**：暂停为候选分支，保留 v2.1、审批规格与既有证据；不执行 P-1/P-2/P-3。
