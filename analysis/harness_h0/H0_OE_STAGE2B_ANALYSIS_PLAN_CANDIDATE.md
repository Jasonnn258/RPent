# H0 Direction 1 — Stage 2B Retrospective Analysis Plan Candidate

> 2026-10-09 · **DRAFT_FOR_FREEZE_REVIEW · NOT FROZEN · NOT EXECUTABLE**。
> 用户本轮“go on”按上一条衔接约定仅批准 **Stage 2B 正式预注册方案审查与冻结准备**。**没有**批准创建正式冻结预注册、运行代码、模型拟合/结果统计、生成新 rollout、在线控制或 S1。阶段完成后再次等待正式冻结审批。
> 研究基线：RPent `research/pre-ovpm-20260905` 的 `70afa95`（Stage 2A 收官前）、`analysis/stageR_prereg.md`、`analysis/STAGE_R_FINAL_REPORT.md` 以及 `H0_OE_STAGE2A_{FIELD_PROVENANCE_AUDIT,PREREG_DRAFT,GATE_REVIEW}.md`。
> 性质：**针对已经完成且部分汇总结果公开的 Stage R 数据集，拟定后续分析计划**。不能称为 outcome-blind 的前瞻性预注册，也不能叫独立 holdout test。本文件提出的数值、模型和停规都是**候选决策（candidate）**，须另行批准冻结后才可用于执行。

## 1. 研究对象和不可突破的边界

**样本、事件与筛选**

- 只取冻结 `analysis/stageR_manifest.csv` 中 `role == R1_COHORT` 的 **24 个 event**，不因其表现或 Stage R 类型筛选；冻结 `event_id` 是事件连接唯一来源。
- 对每个事件只用 `SAME:trial=1..8` 与 `RESAMPLE:trial=1..8` 的原有结果。两臂每次都从冻结 `S_pre` 独立重建；`NATURAL` 来自 `S_post`，仅独立描述，不参与拟议预测模型。
- checkpoint JSONL 中的额外四条 `r09/SAME/1..3`、`r12/SAME/1` 属 `R0_DEV`；冻结 Stage R 终报 §9 **dev-r1-fix** 已记录 R1 首次错误纳入 DEV 并在 05:01 停止、多执行四条、保存 CPS 审计。**任何分析都不得追加 DEV 到 R1 样本**，不删除原 JSONL。
- 原初稳定 FALSE_GRASP 用于**入组条件**，不是一个新的独立试次；事件是相关性与重采样的统计单位，不能把 384 个双臂 trial 视作 384 个独立事件。
- 使用冻结字段 `stable` 作为研究性 `Y_{eaj}` (primary physical outcome contract)，`acquisition` 作为 secondary contract。它们同源于仿真 cps，`stable⇒acquisition`，并非独立物理监督信号。
- 数据不含合法 runtime “过去 k 次稳定恢复真值”的在线通道；研究分析允许 audit-only 标签作为**离线研究对象**，但绝不能将它们包装为 Runtime/Evolution Gate 合法输入。

**不允许回答**：在线 `S_post` 连续恢复、真实机器人风险、Skill edit repairability、latent E/P 类型、时间因果、任何名为“独立修复假阳率”的效果。此前冻结 E14/A1/P5/U4 原样保留、仅引用 Stage R 终报。

## 2. 研究问题重组：一个主比较、两项陪报

| 层级 | 研究对象 | 本文的定位 | 何种结论被禁止 |
|---|---|---|---|
| **Primary: OE2a/P** | 发生 SAME 前两次重试失败后，预测同一事件的**第三次独立重建重试**是否 stable；比较事件异质性模型 M1 对同质模型 M0 的增量回顾预测 | 唯一提议正式比较、有符号的主指标 | 改善就叫“PAEG 新算法”或证明时序依赖 |
| **Secondary descriptive: OE1a/D** | 两种**同源嵌套**成功契约在 SAME 和 RESAMPLE 的 trial 内分歧 | 现有 Stage R ACQ−STABLE 结果的预先定义分解和正确表述 | 独立 false-positive/“已修复”识别能力 |
| **Secondary/exploratory: OE3a/E** | 对不同失败前缀 k，研究第 k+1 个重建试次的预测/弃权资格；与主比较共享数据和预测框架 | 结果相关，**不另作为第二个独立显著性主结果** | 在已经公开的完整 E/P 事后标签上计算无泄漏准确率、给出最小必需重试次数 n* |
| **STOP: OE1b/M2-causal** | 独立物理误报率、失败导致物理状态恶化的时序因果 | 当前**不可识别** | 绕过来源/时间 Gate 造新真值 |

**研究贡献判据**：即使 M1 比 M0 好，也只是已知混合 Bernoulli/层次建模在受限数据上的经验适用性；若没有超越经典统计的**新增合法物理证据资格机制 + 独立评价**，N1 的“原创算法已验证”必须输出 **NOT_ESTABLISHED**。

## 3. Primary OE2a/P：候选完整分析规格（供将来批准冻结）

### 3.1 单位、输入、目标与条件风险集

- **唯一主臂**：`a=SAME`。POLICY/RESAMPLE 作为 Secondary replication，防止按有利臂选择主终点。
- **固定主时点候选**：`k=2`，即只有 `Y_{e,SAME,1}=0` 且 `Y_{e,SAME,2}=0` 的正式 R1 事件才进入主风险集；预测 `Y_{e,SAME,3}`。
- **主预测问题**：`p_e = P(Y_{e,SAME,3}=1 | Y_{e,SAME,1:2}=0, entered_FG, arm=SAME)`。这里的前两次是**S_pre 重建 trial**，不是自然 S_post 恢复、连续物理状态恶化，也没有逐 trial 独立性保证。
- 事件风险集大小和 task 构成仅在未来获授权运行时才能据原始 outcome 算出；此时**不计算、不填入任何结果数值**。
- 选择 k=2 是本草案事先明确的**候选**，不是已经冻结的协议，亦不是从结果筛选的最优 k。主结果不能事后换成 k=3 或 POLICY 只因为结果更好。

### 3.2 M0 同质 Bernoulli：训练事件内估计 pooled success

在每一个完整事件留一验证折 `e`，对其余 `23` 个事件、SAME 臂全部冻结 K=8 个结果，用固定弱平滑：

\[
\hat p_{0,-e}=\frac{1+\sum_{j\ne e}\sum_{t=1}^{8}Y_{j,\mathrm{SAME},t}}{2+8\times23}.
\]

这里加 1/2 对应 `Beta(1,1)` 先验的平滑预测；**固定的 pooled q** 不从被预测事件的前两次失败更新，因为 M0 假定同质 q。它是弱但合法的预测基线，不可被称为真实世界的充分模型。

### 3.3 M1 事件异质、条件 iid：Beta-Binomial 候选

对每个事件-臂的潜在重建成功率，假定
\[
q_{ea}\sim \mathrm{Beta}(\alpha_a,\beta_a),\quad
Y_{eaj}\mid q_{ea}\overset{\mathrm{cond}}{\sim}\mathrm{Bernoulli}(q_{ea}).
\]

- **限定候选参数族**：\(\alpha=\mu\tau,\ \beta=(1-\mu)\tau\)；
  \(\mu\in\{0.05,0.10,\ldots,0.95\}\)，
  \(\tau\in\{0.5,1,2,4,8,16,32,64,128\}\)。
- 对每个留一折，只用另外 23 个训练事件 SAME 臂 8 次结果，最大化按 event 相加的 Beta-Binomial **边际对数似然**，挑选 \(\mu,\tau\)；若并列，先选更大的 \(\tau\)，再选较小的 \(\mu\)。网格是**冻结准备候选**，尚未得到审批，更未拟合。
- 因前两次已失败，留出事件对下一次试次的预测为
  \[
  \hat p_{1,-e}^{(2)}=\frac{\hat\alpha_{-e}}{\hat\alpha_{-e}+\hat\beta_{-e}+2}.
  \]
  只允许使用留出事件的前两次 outcome 以更新当前事件条件后验，绝不能读取当前事件 Y3..Y8 或完整 E/A/P/U 类型。
- 若边际拟合不可定义或数值不稳定：标记 `M1_FIT_FAILED`，预定报告失败/弃权；不允许在看到误差后临时换更优模型并当作预注册分析。

**约束**：该模型是**已有标准混合模型**，并且会从“入组后两次失败”进行后验选择；即使其结果优于 M0 也不能证明 trial 顺序提供计数之外的增量信息，亦不能证明物理环境正在退化。

### 3.4 预测损失、交叉拟合、聚类不确定性

- **独立训练/评估隔离**：`leave-one-event-out` 共 24 个折；每折以剩余 23 个**完整事件**拟合 M0/M1，留出事件只用于前缀条件与下一次 trial 评价。禁止 trial 行级 random split、用留出事件未来 suffix 选择模型、先看总体 Brier 再调超参。
- 对有效主风险集事件，\(\ell_m(e)=(Y_{e,\mathrm{SAME},3}-\hat p_{m,-e})^2\)，事件级差 \(\Delta_e=\ell_0(e)-\ell_1(e)\)。**唯一主指标候选** \(\bar\Delta=\operatorname{mean}_{e\in\mathcal E_{\mathrm{eligible}}}\Delta_e\)，正值代表 M1 平均 Brier loss 较小；不得将已发表 Stage R 的 h(k) 当独立新证据。
- **拟议不确定性**：在完成 24 折的 out-of-fold 预测后，对**有效 event** 的成对 \(\Delta_e\) 进行 event-level bootstrap（提议 10,000 次，seed=20261007，和既有 Stage R 稳定规则相容），取 2.5%/97.5% 百分位区间；仅作为**小样本探索性不确定性**，避免无条件宣称严格 95% coverage。
- **拟议方向门**：只有 95% 事件级 bootstrap 区间的下界大于 0，且满足下列风险集/完整性最低条件，才可写 `PREDICTIVE_ADVANTAGE_OBSERVED_IN_RETROSPECTIVE_COHORT`；否则 `INCONCLUSIVE` 或 `NOT_SUPPORTED`，不能将 0 纳入区间的结果说成“证实没有改善”。所有门槛均**尚未冻结**，不自动批准统计检验。
- **提前完整性门**：如果有效主风险集事件少于候选阈值 **12** 个（为保守报告纪律设定的下限，**不是经功效分析得出的科学阈值**）、或任何正式 R1 主 trial 结果/主键缺失，主比较降级为 `DESCRIPTIVE_ONLY / INCONCLUSIVE`，不能事后换 k 或补新 rollout 来救结果。

### 3.5 必须报告的负面结果

主风险集有效 event 数；按 task 的分布（t3/t5/t9）；M0 与 M1 两套 out-of-fold 预测损失；差值和事件级不确定性；拟合失败次数；后验/网格边界警告；是否存在仅 t9 驱动的表面优势。task 层样本太少，分 task 只描述，不许事后按任务选正结果当整体突破。

## 4. OE1a/D：同源物理 outcome 契约分歧（陪报，不再检验旧 gap）

基于相同合法 R1 cohort 的每臂 8 次试验，保持 primary `Y=STABLE`，secondary `A=ACQ`：

\[
d_a=\mathbb E[A-Y\mid \mathrm{entered\_FG},a],\quad
q^{\mathrm{discord}}_a=P(A=1,Y=0\mid\mathrm{entered\_FG},a),\quad
r_a=P(Y=0\mid A=1,\mathrm{entered\_FG},a).
\]

- 源码 `stageQ_rt.py` 给出 `stable⇒acquisition`，所以在这批相同试次中 `d_a=q^{discord}_a` **按定义严格相等**，无需为两者做“显著性一致”检验。
- 允许在**未来另外获批的数据运行**中按 event 聚类给出描述性差值/条件比例与区间（分母为零则 `NOT_ESTIMABLE`），但已发布 `SAME +34.4pp`、`POLICY +37.5pp` 是同一数据的旧结果；不能当作新结果、独立假阳率或 N1 新算法证据。
- 不再保留 H0 老版本的 `≥30%` / `<10%` 修复误报率主张。此项**descriptive only**，无新的 GO 显著性门。

## 5. OE3a/E：前缀→未来后缀回顾性预测（共享同一 primary family）

与 OE2a/P **共享** M0/M1 两模型和逐事件留一评价，不能再把 OE3 作为第二项独立模型创新：

- 候选 `k`：`0,1,3`（`k=2` 已是主比较），未来目标统一 `Y_{k+1}`，不采用 `m>1` 的多点成功目标作为确认性指标。
- 每种臂 SAME、RESAMPLE 分别报告风险集与 Brier；按事件整体分组，并按冻结的 `role=R1_COHORT` 区分正式试次；源头仅是研究真值，不能进入执行门控。
- 这些 k/arm 指标全部**exploratory**，无多个显著性门，不得选“最好 k”、拟合 k-dependent 复杂模型后声称找到最小稳定试数 `n^*`。若尝试画连续 hazard 或预测损失曲线，需注明相邻 k 的风险集不同且相关、事件间异质/幸存筛选影响结果。
- RESAMPLE 结果仅作为敏感性/外推到已测试另一**动作分布**的支持证据。由于每个事件固定先 SAME 再 RESAMPLE，不能把同一事件内动作差看作无混杂随机配对因果效果。
- 如果合格未来 trial 或有效事件过少，输出 `INCONCLUSIVE`；不为了展示结果而增加新环境数据。

## 6. 遗留风险、假设与负面 STOP

| 编号 | 数据/方法限制 | 预期的正式输出 |
|---|---|---|
| S1 | cohort 混入 R0 DEV 四条 checkpoint | **STOP 数据资格**，只能用 role=R1_COHORT；现有键对账已证明 R1 480 完整 |
| S2 | 单一 R1 event 的未来 trial 被同折拟合或 M1 超参网格修改基于留出真值 | **STOP 预测验证**，不得声明交叉验证结果 |
| S3 | 有效主风险集 N 较小、M1 边际拟合失稳、区间过宽/零在区间内 | **INCONCLUSIVE/DESCRIPTIVE_ONLY**，可报告负面不许换主目标 |
| S4 | 仅同源 `stable/acquisition`，没有独立合法 reference | **OE1b NOT_IDENTIFIABLE**；不可计算真正的修复假阳率 |
| S5 | 固定三臂顺序、同一 S_pre 重建且无绝对时刻 | **M2 causality NOT_IDENTIFIABLE**；不可推断物理退化 |
| S6 | 模型使用 sim-only outcome，想接入 Runtime/Evolution 或改 Skill | **STOP OUT OF SCOPE**；研究结果不可作为在线授权 |
| S7 | 24 事件已公开汇总，内部验证/选择偏差无法消除 | **RETROSPECTIVE_INTERNAL_VALIDATION_ONLY**，任何结果都不能称独立外部测试 |
| S8 | M1 比 M0 有限样本预测更好 | **STANDARD_STATISTICS_APPLICABILITY**，不等价于 PAEG/N1 新算法证明 |

## 7. 冻结之前必须再次独立审阅的五项决策

1. **Primary 比较**：是否接受 SAME/k=2/third trial、`eligible N≥12` 的设计？该阈值没有功效证明，低功效或不可区分时应停止“成功显著”诉求，不能调数据来过门。
2. **M1 适合度**：24 event 在 task 混合、不同 event 难度下用独立 arm-specific Beta-Binomial 的假设是否足够？网格/边界/留一折需要以合法模拟或理论方法审阅；此阶段**未运行任何模型模拟**。
3. **评价与推断**：是否允许把 event bootstrap 95% 下界>0 用作**回顾性支持**标记，而不称严格检验？若希望更强 confirmatory 保证，须另找未披露外部 cohort，本阶段不可补采。
4. **研究创新风险**：如果只复现混合 Bernoulli 选择效应，N1 是否进一步收缩为证据可比性/授权规范？本研究**没有能评估合法在线授权改善的 outcome/样本**，必须允许独创性结果为 NEGATIVE/NOT_ESTABLISHED。
5. **实际冻结与运行**：此计划不属于冻结版；需要用户再次明确批准**创建正式只读封存的预注册文件**，且未来任何统计执行需再单独批准。不得偷偷用 README/旧 Stage R 脚本替代冻结审批。

## 8. 版本、数据/脚本审计及权限 Ledger

本文件属 `DRAFT_FOR_FREEZE_REVIEW`。数据来源 pinned to `analysis/stageR_manifest.csv`、
`analysis/stageR_same_action_rollouts.csv`、`analysis/stageR_resample_rollouts.csv`、`analysis/STAGE_R_FINAL_REPORT.md`；
严格使用 `role=R1_COHORT`，不能因 trial 结果做 exclusions。可在**未来独立批准的冻结阶段**记录 SHA、锁定模型超参数网格与统计代码哈希；本轮没有写分析代码/生成冻结 artifact，不能假设这些哈希已签收。

冻结 `Stage R E14/A1/P5/U4` 与原成功契约不改；R0/R1 的 DEV 修复与四条 CPS 额外审计记录在 `STAGE_R_FINAL_REPORT.md §9`；Stage R §36 Hard STOP 和 S1-DEV0 ON_HOLD 不变。

**最终状态：待独立评审的分析计划候选；本文件不是冻结预注册、更不是实验许可。**
