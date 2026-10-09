# PAEG Method Design v0.2 — 独立复审与后续研究任务

> 日期：2026-10-09
> 审查基线：RPent `cc7e0d37bfa33b7d82354ac0a3faa235d666b446` (Method Design v0.2)，同步仓 `d23c80a`。
> 性质：**独立、只读方法论与新文档审查**；不修改既有 Method/Novelty 源文件，不定标、不设计实验、不运行 rollout、不修改 Verifier/Planner/Critic/Recovery/训练与环境。Stage R §36 Hard STOP 生效，S1-DEV0 暂停。
> 注意：本审查对 v0.2 原作者的 GO(有条件) 是独立复审结果，**不替代原有 `METHOD_V02_REVIEW.md`**。

## 1. 结论

**REVISE（方法规范的小范围阻断修订）/ GO（研究问题与方向仍值得保留）**。

已经修复：事后标签与部分执行证据混用、初始连败过度解读、L1-L4 分层、全局 Evolution>Runtime 公理、跨窗历史撤销、Zetta 无 inconclusive 的错误判断。

然而，v0.2 仍留有互斥分类、模型证据、因果等级、权限规则等问题。故 **不可把原 `GO(有条件)` 解读为算法规范已通过审查或已获 H0 定标授权**。

## 2. 必修的四个问题（附原文定位、后果、明确修法）

### B1：E 与 A 判据重叠；κ_E 与“成功次数”混用

- `METHOD_SPEC §5.3` (v0.2 行 365-370)：E = `n≥κ_min ∧ ∃y_i=1`（任一臂成功）；A = `SAME 全零 ∧ POLICY 存在1 ∧ |contrast|≥δ`。由 A 可推出 E，分类无法互斥；`§7.3` 的 `classify_persistence(PE)` 未定义冲突优先级。
- `§5.3` 末尾说 `κ_E=2` 可对齐 Stage R `same≥2/8`，但 `n≥2`（尝试次数）不是 `successes_same≥2`（成功次数）。
- **修订要求**：把 `legacy_stageR_label` 完整维持为冻结定义（E same≥2/8，A same0 & policy≥2/8，P both0/8，U otherwise），并明确四者互斥且适用于 **8+8 的完整事后双臂**。`DETERMINING` 应是尚未观测齐全的 **过程状态**，非五类事后标签。若另创 PAEG 自有分类须更名、写出排他顺序、证明全域覆盖，禁止在未复审既有数据前静默“重分类 U4”。
- **验收**：例 `SAME 0/8, POLICY 2/8` 必然 A，且不属于 E；`SAME 1/8` 不得自动 E；`SAME 2/8` 为 Stage R E；不足 8+8 的前缀输出 `DETERMINING` 或明确的 evidence state。

### B2：M0 拒绝、单次“零信息”与 M1 统计对象未对齐

- `§5.5` 约行 431-433 的“**M0 被拒绝是 Stage R h(k) 数据确证事实**”无正式检验；目前只有观察性对比，且 `h(k)` 的分母随连败筛选事件，样本单位是 event，不可把 pooled Bernoulli trial 当独立 N。
- `§5.0` 行 304-305 / `§7.2` 行 663-671 将单次失败写为“零证据/零信息”。对随机 `q_e~F`，一次失败通常会改变 `p(q_e | y_1=0)`；只能说**不足以支持指定的决策授权**，不能说数学上零信息。
- `§5.5` 行 463-465 把连败游程称为 M1 的充分统计载体。固定事件 `q_e`、条件 iid 时，混合 Bernoulli 的后验取决于 `n_success,n_failure`，有些 sequential 决策需要当前 run，但相同 `n_success,n_failure` 的序列仅重排不构成额外后验信息。需要区分“记录游程”和“声称顺序有增量信息”。
- Stage R 研究队列本身以 **已观察到 FALSE_GRASP** 选取，正式叙述须明确样本选择条件，避免错误地重复计入初始失败或外推到任意新 episode。
- **修订要求**：M0/M1/M2 都保留为假设层，不在尚未获批的离线分析之前宣称 M0 被拒绝；将在线输出 `NO_INFORMATION` 更名为 `INSUFFICIENT_FOR_DECISION` 或明确它只是决策资格等级。
- 科学定位：M1 下后验预测和决策阈值是传统统计/决策理论，N1 若要保留新颖性须更明确界定“物理重建可靠性 + 双契约证据资格 + 栈内外适用域”新机制。

### B3：causal_grade 默认 STRONG 不成立；SAME/POLICY 关联不能自动排除动作特异性

- `§7.3` 行 735 `STRONG if not uses_replay(e) else downgrade(meta.rho)` 把“未使用重放”误作为“因果强证据”；即使原生观测再清晰，也可能完全不能识别根因。
- `§5.2` 行 346-347、`§7.3` 行 722-724 将近零对比写为“排除动作特异性”不充分；群体平均近零可以掩盖事件异质性，且有限次数对 `contrast` 不确定性很大。
- `§7.5` 虽禁止 L1→L3，但上面的伪代码可独立输出 POLICY/ENVIRONMENT/EXECUTION_NOISE 以及 STRONG，不严密。
- **修订要求**：`causal_grade` 默认 `DESCRIPTIVE/UNIDENTIFIED`；提升只能依赖独立列举的、满足有效性要求的干预/比较证据，并区分 `reconstruction_fidelity`、`execution_stochasticity`、`causal_identifiability`。在没有此类有效证据时 `causal_hypothesis=UNKNOWN`；SAME/POLICY 差的含义先收缩为“已测条件下的动作分布关联”，不做强排除。
- **验收**：只有单次原生观测/没有 replay 的事件不得得到 STRONG；群体差均值接近 0 不得自动判“动作选择无影响”。

### B4：A2b 仍是错误的全球证据强度排序；需按决策结果定义风险

- `§6.4` 行 587-598：所有不可逆决策的 MinStrength 高于所有可逆决策。该全称命题不合理：`PROPOSE_REVIEW` 通常可撤销，`CONTINUE` 也可能引发不可逆的物理后果。不同事件错误代价未必能被单个 L0-L3 序数统一排序。
- 文档将 `PROPOSE_REVIEW` 视为难以撤销的跨 episode 动作，但其明确只提名候选、无自动技能晋升；应与真正 `PROMOTE/DEPLOY` 分开。
- **修订要求**：保留 `A2a` 为“在错误后果和可比较证据可明确排序的决策对上，给出局部充分性约束”；删除 `A2b` 全称命题或严格限定到已证明可比的具体动作。将物理损害风险与候选审查成本分别建模。
- **验收**：任意未证明代价和观察证据类型可比的两项决策，不得写为形式不变量。

## 3. 其他值得同时修订的边界（非主阻断）

1. **在线 vs 离线可获得性**：Stage R 的 SAME/POLICY 8+8 是特定冻结状态下离线多次重建；在线普通 episode 往往没有这些重复/反事实样本。区分 `observed_execution_prefix`、`offline_replay_cohort`、`cross_episode_history`。Runtime Gate 不能把离线 privileged labels 读成在线输入。
2. **Claim 迟到证据**：`§4.3` “闭窗 CONFIRMED 后任何未来事件均不得修改”需要区分物理事件发生在窗口后（不能改变历史）和 **晚到的、但事件时间戳在闭窗内** 的传感器/审计证据（可能推翻之前不充分的判断）。保留旧声明 append-only，生成 superseding 版本，严格禁止以 t3 的滑落改变 t1-t2 的真实发生事实。
3. **可修复性轴**：同分布重试零成功只能提供 `NO_HEADROOM_IN_TESTED_RETRY_ACTIONS`，不能证明“技能编辑无 headroom”。`§6.3` 的 `NO_LOCAL_HEADROOM_OBSERVED→ABSTAIN` 需明确只对何种候选修改生效；避免把最值得研究的 P 型误锁死。
4. **Zetta 统计先例**：Zetta `zetta/evolution/gating.py` 已实现 paired gate 的 `one_sided_exact_mcnemar`，故不能称“Zetta 无统计判据/没有正式统计门”；准确差异是**它用于候选改善验证的统计门，与 PAEG 想要建立的执行失败持续性证据资格是不同统计对象**。
5. **强度不确定性**：L2=“两个独立通道”须核对条件依赖；同一分割模型派生的 EEF/质心特征可能相关，数量多不等于独立；这是 Evidence Claim 信号可信性的风险。

## 4. 核心创新应怎样继续收敛？

当前支持的是一个**研究问题 + 一组概念契约**，并非已证明新算法。主线建议用：

> **Reliability-Aware Persistence Evidence Qualification**：
> 在有限重复执行、具有条件异质性与状态重建不确定性的场景中，明确什么证据足以支持“已测试动作分布内的失败风险”、“是否需要 abstain”和“哪类决策可以消费证据”。观测的预测可信度、因果归因与修改后可修复性各自独立。

创新空白不是“首次定义 inconclusive”、“首次二 Gate”、“首次 Beta-Binomial/顺序检验”。需要阐明相对经典统计方法及 Zetta/CheckVLA/RegenHarness 的具体增量。相关基础：
- https://pubsonline.informs.org/doi/10.1287/opre.19.4.970 (1971, sequential stopping)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10962580/ (heterogeneous Beta-Binomial)
- https://arxiv.org/abs/1602.01650 (robust reliability / sets of priors)
- https://github.com/air-embodied-brain/Zetta-Embodiment/blob/main/zetta/evolution/gating.py (statistical paired gates)

## 5. 下一步有权限做与禁止做的事

**下一阶段名称**：Method Consistency Finalization（针对性方法逻辑收敛）。

**执行权限**：可复读既有资料，修订 `METHOD_SPEC.md` 和 `NOVELTY_REVIEW.md` 的方法定义，形成 `METHOD_CONSISTENCY_REPORT.md`，全部为研究文档。

**禁止**：不得设计或运行 H0 Direction 1 数据定标/预注册/新统计检验，不得运行 rollout、修改 Stage R 数据标签、写入 classifier/critic/verifier/recovery、改控制器、模型训练、启动 S1-DEV0。未来“纯离线分析”亦必须在用户明确批准后再做。

**验收**：
- B1-B4 各有原文前后差异、反例及修正后可逐例判定的接口；
- Stage R 冻结类型 E14/A1/P5/U4 保持原口径，不伪称重分析；
- M0/M1/M2 现象、统计假设、是否完成检验三者严格区分；
- Online vs Offline 证据可得性与 Simulator Firewall 显式；
- `NOVELTY_REVIEW` 不宣称基于 `未做的概率定标` 已完成算法创新；
- 完成后只做小范围研究文档提交，报告 SHA 与安全检查结果，等待下一阶段审批。

**当前判断**：`REVISE` 方法规范；**保留 N1 研究主线**，待该轮自洽性修订完成再决定是否另行批准 H0 方向 1。
