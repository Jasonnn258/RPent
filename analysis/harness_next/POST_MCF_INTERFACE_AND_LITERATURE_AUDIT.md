# RPent PAEG — Post-MCF Evidence Interface & Novelty Audit

> 2026-10-09 | **独立、只读的后续研究评审**，基线 RPent `97f79ca3b7f47ab1bb2a58c22636f1d039a0c7f1` (其中 METHOD_SPEC v0.2.1 来源 `17a2991`)。
> 阅读：`analysis/harness_next/{METHOD_SPEC,NOVELTY_REVIEW,METHOD_CONSISTENCY_REPORT}.md`、`analysis/harness_h0/{HARNESS_OPPORTUNITY_REVIEW,DIRECTION1_PREAUTH_REVIEW}.md`、`analysis/stageR_prereg.md` 与冻结 Stage R 终报。
> **没有**执行实验、离线统计、预注册、修改运行代码或更改 Stage R 标签。Stage R §36 Hard STOP 和 S1-DEV0 暂停继续有效。
> 本文件区分 **[R] 本仓确实写了什么**、**[F] 外部论文可读全文中实际支持什么**、**[S-ext] 先前已核实的外部源码**与 **[I] 本次独立推论或修订建议**。只对可核实的内容作出判断。

## 1. 裁决与最小结论

**总体：PAEG v0.2.1 的科学问题/概念对象继续 GO；声明“方法所有接口均自洽”需要 REVISE；H0 Direction 1 仍 HOLD、未获授权。**

MCF 确实修复了 B1-B4 的主要定义缺陷，不能抹去该轮工作。然而，再次核对跨章节**输出能否满足输入合法性、何种证据进入何种权限、规则是否封闭**时，出现四处新的规范一致性问题。它们在正式校准之前应予处理，不需要任何新 rollout 或数据分析。

## 2. 新的接口问题（有原文位置与最小反例）

### I1 — Runtime 使用了仅离线才存在的证据

- **[R] METHOD_SPEC §5.6**：`observed_execution_prefix` 是 Runtime 唯一的合法本次执行输入；`offline_replay_cohort` 的 SAME/POLICY 8+8 仅可供离线统计与审计。§5.3 的 E/A/P/U 冻结分类需要完整 8+8，因此不能在线产出。
- **[R] METHOD_SPEC §8.2 行约 1011-1018**：矩阵行“`双臂全败(0/8+0/8)+修复证据`”对 `REPORT_FAILURE` 标为 ✅（Runtime 资格）。§9.3 同样据此写 `REPORT_FAILURE=ALLOW`。
- **[I] 冲突**：一条 Runtime 决策路径引用了 Runtime 不允许/不可能消费的离线证据。即使仅是“资格规范”，该资格须带出“离线反事实证据下的回顾性条件资格”，不可冒充执行时刻资格。
- **最小修订**：将 `Runtime-available evidence` 与 `Offline research-only / Evolution-candidate evidence` 作为静态类型；§8.2 对“完整双臂”行的 Runtime 单元格设 `NOT_APPLICABLE_OFFLINE_ONLY`，或另立独立的 `RETROSPECTIVE_ELIGIBILITY`，不能用同一 ALLOW。§9.3 同步更正，在线 REPORT_FAILURE 只可基于合法前缀形成且未被授权的新规则依然保持 `UNRESOLVED`。

### I2 — Evolution Gate 伪代码允许绕开 D2 授权白名单

- **[R] METHOD_SPEC §7.1/§7.3**：`causal_grade` 的默认值 = `UNIDENTIFIED`，`repairability` 默认 = `UNKNOWN`。
- **[R] METHOD_SPEC §7.5 D2（约 941-945 行）**：`PROPOSE_REVIEW` 的条件含 `persistence=P` **且** `repairability=EVIDENCE_FOR_CANDIDATE_REVIEW` **且** `causal_grade ≥ MODERATE`。
- **[R] METHOD_SPEC §6.3（约 645-658 行）**：代码仅在 `repairability=NO_HEADROOM_IN_TESTED_RETRY_ACTIONS` 时 ABSTAIN，仅在 `causal_grade == DESCRIPTIVE` 时 QUARANTINE，其余直接 `return PROPOSE_REVIEW`。
- **[I] 最小反例**：给出 P 型、`evidence_mass=SUFFICIENT`、`repairability=UNKNOWN`、`causal_grade=UNIDENTIFIED`，逐行执行 §6.3 伪代码得到 `PROPOSE_REVIEW`；但 §7.5 D2 明文**不授权**。
- **最小修订**：§6.3 必须按 D2 显式正向检查 `repairability == EVIDENCE_FOR_CANDIDATE_REVIEW` 和 `causal_grade∈{MODERATE,STRONG}`。其他值一律 `QUARANTINE/ABSTAIN`（两者须明确语义差别）。`causal_grade` 的 UNKNOWN/UNIDENTIFIED 不得以“!=DESCRIPTIVE”漏洞越级。

### I3 — 案例/伪代码仍保留了已废弃的分类和因果措辞

- **[R] METHOD_SPEC §5.3**：冻结 E 需 SAME 臂至少成功 2/8；A 需 SAME 0/8、POLICY ≥2/8；群体 contrast≈0 不排除事件级动作影响(§5.2)。
- **[R] §7.2 R1a 约 794-799 行**：`n≥2 且任意一次成功 → failure_class=E`，仍沿用 v0.2 的旧规则，与 §5.3 冲突；单次 POLICY 成功也不能自动判 E。
- **[R] §9.3 P 案例约 1124-1132 行**：用“`contrast` 近零 → **排除**动作特异性”，并在 `ρ<ρ*` 的重建不确定性下直接给 `causal_grade=MODERATE`，而没有显式的有效干预/对照资格论证。
- **[I] 最小修订**：R1a 仅陈述“观察到某种翻盘”，**不得**直接赋冻结 E 类；必须满足完整 Stage R 同臂成功数与覆盖。P 案例只能说当前数据未观察到在已测两臂之间的成功差异；`causal_grade` 若没有独立有效性证据默认 `UNIDENTIFIED`，重建保真只是上限/降级条件。

### I4 — Evolution 可消费的离线重放数据与 sim 真值防火墙界限不清

- **[R] METHOD_SPEC §5.6 约 579-597 行**：`offline_replay_cohort` 例示“任意时刻 check_success、逐物体位姿”，同时写“可供 Evolution 离线统计”；紧接着又明确 `offline_evaluation_only` 的仿真真值**连 Evolution 门也不得消费**。§3.1 用 `check_success` 及 object z 作为离线真值判据。
- **[I] 数据类型矛盾/歧义**：离线 replay 原始包中哪些字段可成为“合法 Evolution evidence”，哪些仅允许科学研究审计，尚没有字段级界线；如果 E/P label 实际由仅审计真值计算，不能在同一通道直接传入 Evolution。
- **最小修订**：将 replay 来源拆为 `research_audit_truth`、`legally_observed_rollout_outcomes` 和 `reconstruction_metadata` 三种互斥可见性类型；若实际日志无法提供不依赖特权字段的正当 Evolution outcome，必须输出 `NOT_AVAILABLE` 并暂停该门，不能对其重新贴合法标签。这里是**接口规范提案**，并不声称现有日志已经满足该拆分。

## 3. 外部文献进一步验证的保证边界

### F1. CheckVLA [F：论文 HTML 方法及边界章节原文核验]

出处：https://arxiv.org/html/2607.26789，正文 “Calibrated Risk Triggering” 与 Appendix D/P。

- 方法中风险阈值使用**彼此分离**的正常执行拟合池、校准轨迹以及锁定评估；给出的保证对象是 `P(发生首次不必要干预 | nominal success) ≤ α`，并且**要求校准与部署轨迹在相同冻结管线下可交换**。
- 作者明确说明这个概率保证**不**涵盖失败召回、干预后的安全、重复干预、分布漂移或跨 sim-to-real 转移。报告把 false-intervention calibration 和 alarm usefulness 分开。
- **PAEG 应主动让渡**：conditional guarantee、分组切分防泄漏、明确 guarantee scope、保留历史 keyframe 的理念均有先例。新问题如存在，只能落在 `S_pre` 重建下的重复失败证据相较自然 `S_post` 的**可比性**、双契约及可授权消费范围，而不是“首次声明保证需条件”。

### F2. VASO [F：论文 HTML 方法及失败案例章节原文核验]

出处：https://arxiv.org/html/2606.05395，§4.2 “Guarantee and Assumption” 与 Appendix C “Failure Case”。

- VASO 的 plan-level model checking 把执行映射到命题 `L_sk`；作者明确承认**形式保证依赖 proposition alignment 正确**。
- 论文给了一个具体反例：把三维速度范数错误写成只使用水平分量，导致自动验证通过、实际速度超限。这是“更强的上层验证器也会在底层证据错误时给出虚假保证”的实证逻辑例子。
- **PAEG 应主动让渡**：把 `观测到的物理信号→语义谓词` 映射可信性作为保证前提，本身已有成熟先例。不能把“任何证据支持都有前提”作为自己的算法创新；可以研究**VLA 执行随机性、状态重建不完美及双物理 outcome 合同共同存在时**如何限定证据资格，但目前尚无实证结果。

### F3. 另外两项：Zetta / RegenHarness

- Zetta 已由此前 `NOVELTY_REVIEW.md` [S-ext] 核对源码，包括 unresolved/inconclusive、paired gate 和 exact McNemar。论文摘要：https://arxiv.org/abs/2608.16590。
- RegenHarness **本轮只重新核对摘要**：其 identity/version-bound commit、observed facts vs accepted progress 和监督/验证/恢复角色分离已经先例化。摘要：https://arxiv.org/abs/2609.27612。
- **本轮未成功读取上述两篇完整论文**，故不能据此主张“其全文没有物理持续性统计方法”。尤其不能把摘要/源码缺少某个术语当作缺乏机制的确证。

## 4. 对 N1 独创性的进一步收缩

保留工作名 **Reliability-Aware Persistence Evidence Qualification**。三个层次应分清：

1. **研究问题**（仍 GO）：已发生物理失败的场景中，多少、何种来源的执行证据足以支持什么类型的预测/审查资格？适用域限于已失败的 FALSE_GRASP@Pi0.5@libero_spatial 等已测条件。
2. **已有工具/先例**：可交换混合、序贯统计、门槛校准、abstain、时序证据、形式命题、版本化证据和受限授权均已有先例（经典统计 + CheckVLA/VASO/Zetta/RegenHarness 等）；重新组合并不自动产生原创算法。
3. **真正待证明的贡献候选**：物理 reset/fidelity 不可靠时证据可比性的形式化，ACQ vs STABLE 合同差异对决策风险的影响，按合法来源与决定类型限定 `predictive vs causal vs repairability` 的授权资格。需要后续另获授权的数据研究才能判断增量是否超出规范集成。

**直接结论**：不增加新 Agent、Critic、Verifier 或 Harness loop；先保证四层数据可得性/授权接口没有“研究真值偷渡”，之后才有意义讨论是否值得运行 H0 Direction 1。现有 H0 科学预审 G1-G4 保留，不能用本文件代替预注册/审批。

## 5. 下一步实际可执行工作（研究文档，无实验）

任务名：**PAEG Evidence Authorization Interface Repair**。

- 修订 `METHOD_SPEC.md` §5.6、§6.2/6.3、§7.2/7.5、§8.2、§9.3，**最小修复 I1-I4**，避免大规模扩展架构。
- 如影响创新声明，只同步修订 `NOVELTY_REVIEW.md`，新增一份小型 `EVIDENCE_INTERFACE_REPAIR_REPORT.md` 逐例证明接口合法。
- **验收反例 1**：完整离线 SAME/POLICY 双臂证据不能直接使 Runtime `REPORT_FAILURE=ALLOW`。
- **验收反例 2**：`P,SUFFICIENT,UNKNOWN,UNIDENTIFIED` 不能得到 `PROPOSE_REVIEW`。
- **验收反例 3**：`SAME0/8,POLICY1/8` 不能在任何规范段落被判 E；只用一次成功不能以 Stage R 口径判 E。
- **验收反例 4**：`offline_evaluation_only` 的 sim 真值即使出现在 replay 文件中，也不能通过 Evolution Gate。
- 完成研究文档后可以提交文档、审查 fast-forward 并发布研究分支。**未经单独批准，禁止**执行 H0 方向 1 定标/预注册/统计脚本、运行环境/VLA/rollout、训练、修改执行代码、解禁 §36 或 S1。

**本次状态**：评审结论与交付提示已给出；接口修订尚未执行，也不宣称问题已修复。
