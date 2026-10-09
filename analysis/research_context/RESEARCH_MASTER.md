# RPent / Harness VLA — RESEARCH_MASTER

> 稳定研究上下文（初版 2026-10-09）。**这是研究路线与已验证边界的入口，不是实验报告或冻结协议。**
>
> 知识依据：`analysis/harness_next/METHOD_SPEC.md` v0.2.2、`NOVELTY_REVIEW.md` v0.2.2、Stage R 冻结协议与 H0 Stage2E–2I 审查、2026-10-09 用户提出的四张 Harness VLA 研究框架图及本次研究讨论。
> 有争议的数字与事实以原始实验报告为准；任何新的 Stage2J 及后续报告需**先审查，再**进入本入口。
>
> 阅读顺序：本文件（长期稳定）→ `CURRENT_STATE.md`（最新状态）→ `DECISION_LOG.md`（为何这样决策）→ 原始方法与实验文档。
> 更新规则：只有研究问题/边界/优先级发生有证据支持的实质变化时才修订本文件；不得把候选方向改写为已验证结论。

## 1. 总研究问题与边界

**核心问题：具身 Agent/Harness 应在何时、依据何种合法证据，判定物理动作的成功/失败、采取额外验证或恢复，并决定哪些经验有资格供未来任务复用？**

在具身执行里必须区分：
- **物理结果（Outcome）**：取得目标物体、持续持握、达成任务目标，随时间/观测窗口变化；
- **证据（Evidence）**：Planner 能实际收到的视觉/proprio/tool result，以及与之严格隔离、仅供科学评价的 sim 真值；
- **声明（Claim）**：一个限定目标、时间窗、证据质量、可撤销性和消费权限的判断；
- **决策资格（Eligibility）**：证据是否足以支持某类当前决策或长期更新候选；
- **实际控制收益（Effect）**：只有比较改变后的闭环行为才能证明验证/恢复策略的收益。

三条研究纪律：
1. 证据合法性、时间切点、动作干预、评价标签与实验因果对象必须分别定义；`offline_evaluation_only` 不得变成在线工具输入。
2. 失败持续性 ≠ 因果故障归因 ≠ 方案可修复性；任何跨层推断必须有证据、可辨识性和明确定义。
3. “数据能配对/实验能出数字” ≠ “有独立方法创新/可部署收益”。允许 `UNKNOWN`、`ABSTAIN` 和 STOP。

## 2. 现有方法学基线（PAEG）

权威规范：`analysis/harness_next/METHOD_SPEC.md` v0.2.2；独创性核验：`analysis/harness_next/NOVELTY_REVIEW.md`。它们目前是**仅规范层：未实现、未定标、未验证部署效果**。

四个对象：
1. **Outcome State**：区分 `GraspContact`、`Lifted`、`Held(o,W)`、`TaskSatisfied` 等物理判据及各自时间窗；
2. **Evidence Claim**：合法证据来源、L0 工具报告至 L3 持续多源证据的假设性等级、开窗/闭窗、五态生命周期、可信范围；
3. **Failure Persistence / PA-Attr**：在 SAME 与 POLICY/RESAMPLE 试验中研究有限重复和异质性；四类事后失败标签与在线信息不足判断不可混淆；不可从持久失败直接推“技能缺陷”；
4. **Decision Eligibility**：Runtime Gate / Evolution Gate 对不同决策分别设授权资格；Evolution 只允许合法 outcome 证据，研究审计真值不自动可用于进化。

可见性层级（任何新数据集继承）：
`observed_execution_prefix`、`cross_episode_history`、`offline_replay_cohort`、`research_audit_truth`、`reconstruction_metadata`。
数据资产字段必须保存 provenance、event_time、visibility、outcome_contract；聚合和记忆写回不改变字段权限。

已存在的相关先例包括 CheckVLA、Zetta、RegenHarness、EmbodiSkill、VASO 等；不能单靠“闭环验证 / 支持弃权 / 双门 / 记忆版本化 / 统计门控”声称独创。可能研究空间是**具有物理重建误差、失败持续性异质性、证据合法性与验证成本约束的决策资格/主动证据获取机制**，其新颖性仍须经严格消融验证。

## 3. 已有 RPent 数据：可用对象与不能宣称的对象

### 3.1 原始 vanilla Planner 执行资产
截至 Stage2I 用户回传的结构扫描：
- 187 个 ledger episode 目录，187/187 的 `states.json` 与 `stageR_trace.jsonl` 在盘；
- 186 episode 含 `pi0_pick`，共 235 次原始 pick；235/235 通过 V1 返回字典与 trace 的**字段/时间结构配对**；
- 总计 2,859 条 pick chunk 动作记录；脚本检查了逐 chunk `meas` 和 terminal `final_meas` 的外层字段。
- **未证实** 235 次调用的正负类别支持、FG 目标位姿字段可构造性或标签误报/漏报率；235 是相关调用数，独立抽样单位要考虑 episode 聚类。

### 3.2 Stage R 失败持久性资产
- 24 个按冻结条件选择的 FALSE_GRASP 失败事件；Stage R 的 R1 正式试验 480 次、另有 4 条 DEV CPS 需排除；
- SAME/RESAMPLE/NATURAL 每 trial 按指定重建机制执行，**不能当成同一真实物理轨迹里的连续多次重试**；
- ACQ/STABLE 使用仿真特权信息，分别对应取得与特定 continuation 下持续保持的不同操作契约；不是原工具成功标记、也不是在线合法证据。
- 样本任务族窄、失败事件有入组选取、重建误差与固定协议局限，不构成独立前瞻/真实机器人泛化证据。

### 3.3 研究候选数据集
**工作名：Embodied Evidence Reliability Dataset（EERD）v0.1，尚未正式发布。**
- A / Execution Evidence：逐 episode / skill / chunk 的合法前缀、原始工具报告、仅离线可见的同技能物理审计参考；
- B / Failure Persistence：带原始 event/arm/trial/protocol、重建保真、特权 outcome 的冻结试验；
- 可扩展 C / Active Verification Decision：未来增加固定验证预算、随机/配对策略和真实决策后续结果，现有数据尚不支持充分构建。

所有条目建议保存 `episode_id`、`event_id`、`skill_id`、`decision_boundary`、`evidence_source`、`availability_time`、`visibility`、`outcome_contract`、`action_condition`、`reconstruction_status`、`reference_source`、`split_group`。按 episode/event 分组切分，防止同事件多臂进入训练和评测两侧。

## 4. 研究机会路线（是候选优先级，未获新执行授权）

| 阶段 | 科学问题 | 已有资产与缺口 | 最强可允许主张 |
|---|---|---|---|
| **P0 Evidence Dataset & Reliability Audit** | 工具说“成功”与真实取得的对应关系？是否存在有效、无泄漏的评价？ | 现有 235 配对仅结构 PASS；物理参考、类别支持待核实 | 单栈、同技能、回顾性的有限一致性 |
| **P1 Evidence-Aware Active Verification & Recovery**（优先方法候选） | 何时值得额外观察、何时继续/恢复，能否以有限成本降低错误完成？ | 需要真正决策时的合法证据、验证动作与不同策略下的未来结局 | 在冻结 VLA/预算下实测闭环收益，基线和对照已固定 |
| **P2 Evidence-Governed Harness Evolution**（长期） | 哪些经验可进入记忆/技能更新，过期或错误经验如何安全撤销？ | 需要多个任务/阶段、经验消费痕迹、独立更新后的回归验证 | 跨任务收益、负迁移和更新成本可比较 |

PA-Attr、Evidence Claim、Runtime/Evolution Gate 是这些问题的共享接口；世界模型、Graph Memory、Skill Library、SFT/RL/OPD 属候选实现手段，不能先于问题和有效评价而变成既定研究贡献。

## 5. 判别研究价值的统一标准

每个研究提案至少写明：
1. **可证伪假设**：比最强相关已有基线多解决什么明确失效模式？
2. **决策面**：哪个 agent 在哪个时刻实际能收到什么信息？
3. **对象与标注**：取得 vs 持握 vs 任务完成；同技能审计 vs 返回后未来；时间窗定义与删失。
4. **对照/隔离**：按 episode/event 分组、尽量配对/随机化，避免阈值后验选择与共享真值循环引用。
5. **实验评价**：错误完成率、物理任务收益、额外观测与动作成本、失败恢复、abstain、负迁移及区间估计。
6. **创新边界**：对照 CheckVLA、Zetta、RegenHarness、VASO 等已覆盖的方法；结果仅支持被实际测量的对象。

## 6. 不变量

- Stage R `analysis/stageR_prereg.md` §36 **HARD STOP** 持续有效；S1-DEV0 保持 **ON_HOLD**。
- 不擅自实现或运行在线 verifier/recovery/controller/Planner redesign、rollout、训练、技能演化；新实验要独立立项、预注册和显式批准。
- Stage2C 冻结协议、Stage2D 结果、Stage R 原始数据只读；新定义必须版本化，禁止改写历史结果。
- 此 Master 不代表用户已批准 P1/P2 方案实施。

## 7. 维护流程

新对话或 Coding Agent 工作之前：先读本文件、`CURRENT_STATE.md`、`DECISION_LOG.md` 和相关源报告。每轮完成后只更新 CURRENT_STATE；出现真正改变研究选择的证据时追加 DECISION_LOG；Master 仅经审查后有意识更新。状态必须区分 `VERIFIED` / `REPORTED` / `INFERENCE` / `PROPOSED` / `BLOCKED`。

**一句话基线：让具身执行结果有物理证据、证据有合法边界、决策有成本意识、经验有更新资格。**
