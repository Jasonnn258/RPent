# H0 Direction 1 — Outcome Evidence Calibration
## Stage 1 Research Protocol & Identifiability Design (DRAFT · NOT FROZEN)

> 日期：2026-10-09 · 用户明确批准范围：**阶段一研究协议与可辨识性设计**，本文件为可审阅研究协议草案，**并非正式预注册、阈值冻结或执行授权**。
>
> 研究分支：\`research/pre-ovpm-20260905\`；起始版本 \`e9f186e\`（PAEG v0.2.2）；依据 \`analysis/harness_h0/{HARNESS_OPPORTUNITY_REVIEW,DIRECTION1_PREAUTH_REVIEW}.md\`、\`analysis/harness_next/{METHOD_SPEC,EVIDENCE_INTERFACE_REPAIR_REPORT}.md\`、\`analysis/stageR_prereg.md\`、\`analysis/STAGE_R_FINAL_REPORT.md\`。
>
> **本阶段约束**：仅研究文档与理论设计；不打开/检索原始 trial CSV 行，不做数据统计、拟合、功效运算、模拟、置换检验或任何实验；不产出、冻结正式预注册/分析代码；不执行 rollout、env boot、Pi0.5、训练、修改控制器。Stage R §36 Hard STOP 与 S1-DEV0 ON_HOLD 保持。Stage R E14/A1/P5/U4 维持原样。

## 0. 核心问题、作用域与目标降级纪律

**研究问题**：在 \`FALSE_GRASP@Pi0.5@LIBERO\` 的**已失败事件**中，对同一个 \`S_pre\` 使用冻结 PREFIX_REPLAY 得到的、有限次数重复执行的**科学测量**，能多大程度支持：

1. 两种物理 outcome 契约的分歧和时间上的证据可靠性（OE1）；
2. 在**事件难度异质性**下的后续一次稳定成功概率（OE2）；
3. 给定前缀证据时，对**未来尚未观察到的重复执行结果**的预测/弃权资格（OE3）？

三者是**不同 estimand**。本研究**不**直接识别“真实技能缺陷”“修改技能能否修复”“执行下一步是否值得冒物理风险”，也不以此直接授权 Runtime/Evolution Gate。

**原 H0 草案须作四项受约束修订**（\`DIRECTION1_PREAUTH_REVIEW.md\` G1–G4）：

- **G1**：不得用 STABLE 作为接受信号，又用同一 STABLE 标签作独立真值来计算虚假的低假阳率；
- **G2**：不得把同一 8+8 完整结果定义的 E/P 事后标签当作其前缀的独立分类金标准；
- **G3**：不得把与同质 iid 边际率的差异叫作超出异质 iid 的新时序效应；
- **G4**：不得把冻结 \`S_pre\` 的重试分布等同于自然 \`S_post\` 的在线恢复，更不能推出 Skill 编辑效果。

**可辨识性输出**统一采用：
- \`DESCRIPTIVE_IDENTIFIABLE\`：已有文档指出相应同源 outcome 测量在档，可以**原则上**定义描述性 estimand；但未经字段级复核，不保证数据已经满足全部分析条件；
- \`CONDITIONAL_IDENTIFIABLE\`：需要额外的字段、时间戳、非特权/独立结果或可核实采样假设；现在尚无证据证明已满足；
- \`NOT_IDENTIFIABLE\`：按**当前已知**观测契约无法独立验证该命题；应降级为描述性分歧/预测问题，不能用更换指标名来冒充识别；
- \`OUT_OF_SCOPE\`：不同实验分布/新反事实、实施或控制器研究。

这些是**仅依据已有报告与契约的设计性评估**，不是打开数据后的鉴别结果。

## 1. 已有实证资产与禁止的外推

Stage R 冻结口径（引用既有报告，不是本阶段新复算）：

| 对象 | 已有依据与限制 |
|---|---|
| 采样事件 | \`R1\` 24 个 cohort 事件；起点是已发生 \`FALSE_GRASP\` 的 nominal pick，原初失败**仅为入选条件**，不能再次作为 trial |
| 双臂 | SAME \`a_fail\` ×8，POLICY（Pi0.5 重采样）×8，均从冻结 \`S_pre\` 使用 PREFIX_REPLAY **分别重建**，非连续状态演变；NATURAL \`S_post\` ×4 **只描述** |
| 主要结局 | \`STABLE_RECOVERY\`：Stage Q/R 冻结稳定契约；\`ACQUISITION\` 陪报；两者分歧是研究底物，不能改写旧契约 |
| 后验标签 | E: SAME≥2/8；A: SAME=0/8 & POLICY≥2/8；P: 两臂全0/8；U: 其余。分布 E14/A1/P5/U4；此为 **16 次结果定义的事后描述类，不是隐藏真值** |
| 已知限制 | P 的 5 个事件全部 t9；只有 24 个独立事件簇；不得视 384 个双臂 trial 为独立事件 |
| 重建契约 | Stage R 前缀仪器哈希一致性 32/32（R0），不是执行完全相同或跨时间可交换性的保证；Stage Q snapshot transition-class 10/14 **不是** Stage R PREFIX 的 \`ρ\` |
| 时间与权限 | 完整 8+8 标签离线才可获得；sim check_success/object poses 等研究真值仅作审计，不能作为线上或 Evolution 授权输入 |

基础量的文献适用域只到当前任务族；Stage R 报告中 \`ACQ−STABLE\` 的 SAME +34.4pp/POLICY +37.5pp 是**两个总体接受率差**，不是自动等于条件假阳率或独立未来失败概率。以前的 \`h(k)\` 不可冒称独立统计检验。

## 2. 研究对象、抽样单位与事件时间

设事件 \`e\` 条件于入选 \`S_e = {已发生一次稳定 FALSE_GRASP 且 provenance 完整}\`，臂 \`a∈{SAME,POLICY}\`，冻结动作起点 \`S_pre(e)\`，重复 trial \`j=1,…,8\`：

- \`A_eaj∈{0,1}\`：该 trial 满足 **原始 ACQUISITION** 契约；
- \`Y_eaj∈{0,1}\`：该 trial 满足 **原始 STABLE_RECOVERY** 契约；
- \`T_eaj\`：trial 执行及观测时间、结果时间（是否可从在档字段辨识：**待字段级核验**）；
- \`X_eaj^legal(t)\`：真实执行时点 \`t\` 前 Agent **合法可得**的观测/代理，不能事后用 sim 私有字段回填；
- \`Z_eaj^{audit}\`：仿真真值与 state hash 等，仅科学研究审计；
- \`R_eaj\`：重建条件与 fidelity 元数据（字段可得性和方法可比性**待核验**）。

**独立性层次**：
- 独立研究事件单位为 \`e\`，不同臂与试次来自同一 \`e\`，具有配对/层次结构；
- 同一事件在 \`S_pre\` 重置后的 trial 是否**条件 iid**是 M1 的建模假设，不能由 32/32 仪器哈希自动推出；
- \`t3,t5,t9\` 任务分层不均，P 全部 t9，不能用“总 trial 数 384”虚增独立样本；
- 任何参数学习/超参数选择都应限制在训练事件内，不能从评估事件的未来 suffix 获取信息。

**时间区分**：物理事件时间、代理判定到达时间、重建实验次序以及“第 \`j\` 次尝试”是四种不同时间。Stage R 冻结 \`S_pre\`，trial 次序不等价于机器人连续失败后的实际状态轨迹。

## 3. H-OE1 → OE1：双契约分歧 vs 独立验证错误

### 3.1 可以诚实定义的描述性 estimand（优先）

针对每种臂 \`a\`，定义在入选 \`S_e\` 下的 attempt 分布：

\[
D_a = E[A_{eaj}-Y_{eaj}\mid S_e,a],
\]
\[
D_a^{discord} = P(A_{eaj}=1,Y_{eaj}=0\mid S_e,a),
\]
\[
Q_a^{discord} = P(Y_{eaj}=0\mid A_{eaj}=1,S_e,a).
\]

其中 \`D_a\` 是**两种接受率的差**，与联合分歧 \`D_a^{discord}\` 不总相等（除非有额外的契约蕴含关系且经验证）。\`Q_a^{discord}\` 是 ACQ 已满足条件下 STABLE 未满足的**同 trial 条件分歧**，只能命名为 \`CONTRACT_DISAGREEMENT\`，不可称为独立 \`false_positive_rate\`。

文档级资格：\`D_a\` 与同源契约分歧是 \`DESCRIPTIVE_IDENTIFIABLE\` 候选（H0 已说明双布尔序列在档），其精确联合统计/缺失分母/契约嵌套关系须在**以后获批的数据字典审查**核实。先前的 +34.4pp/+37.5pp 不给 \`Q_a^{discord}\` 赋值。

### 3.2 独立的“误报已稳定/已修复”能否测量？

若想讨论 \`false_acceptance\`，必须**另有**：
1. \`acceptance_signal(t)\`：决策时已合法观察的证据/代理；
2. \`reference_outcome(t,t+H)\`：独立于判定信号构造的、预设窗口 \`H\` 内未来结果；
3. \`verification_horizon H\`：在看结果前固定的时间范围；
4. \`source_separation\`：参考结果不是把相同 \`STABLE\` 标签再读一次，也不使用其验证时点之前不可得的输入冒充决策时证据。

若没有独立延后窗口/标签：\`FALSE_ACCEPTANCE_OF_REPAIR = NOT_IDENTIFIABLE\`；
只报告“既有两契约的分歧”或“参考真值与**合法代理**分歧（条件满足时）”。H0 原稿的 \`ACQ≥30%\` 和 \`STABLE<10%\` 作为正式 FPR 假设**撤回、改为待证明可辨识性的议题**，不得未经验证转写为新数值门。

OE1 与“技能已修复/已掌握”无直接等价关系：重建的执行稳定恢复 ≠ skill edit 因果修复。

## 4. H-OE2 → OE2：异质性后验、后续重试与时序依赖

### 4.1 优先 estimand：已失败条件下下一次重建尝试

对臂 \`a\`、\`k=0,…,7\`：

\[
h_a(k+1)=P(Y_{ea,k+1}=1\mid Y_{ea,1:k}=0,\; S_e,a),
\]

是**重建 \`S_pre\` 再次执行的条件成功概率**，不等于从 \`S_post\` 真正继续执行的自然恢复机会。后续要比较预测分布时可以引入个体 \`q_{ea}\` 的后验预测，但这里**不拟合或报告数值**。

### 4.2 三层统计解释，禁止因果越级

| 模型层 | 内容 | 能否从旧 \`h(k)\` 直接宣告？ |
|---|---|---|
| M0 同质 iid | 所有事件一个固定 \`q\`，历史对下一试次无效 | **不能**，未做正式比较/区间 |
| M1 事件异质、条件 iid | \`q_{ea}∼F_a\`（必要时按 task 分层）；历史失败更新后验、低 \`q\` 事件进入幸存风险集 | **理论上可产生递减 \`h(k)\`**；不能据此声称真实时间漂移 |
| M2 试次排序有额外信息 | 相同成功/失败计数的不同排列仍有剩余预测信息（环境漂移/采样机制/真实非可交换性） | **必须另有验证**，有限每臂8次可能低功效 |

在 M1 中，固定 \`q\` 下的似然只依赖成功/失败计数；失败游程\`k\`能更新后验是因为积累了 \`k\` 个失败、且事件筛选，而**不是排序凭空新增信息**。

未来研究若比较 M0/M1/M2，必须保留 task/event-arm 层次；不能只比 pooled \`q≈.30\`。若未来做 event 内 sham 置换，应明确它是在**条件于计数的顺序可交换性**层次检查：不可拒绝不等于 M2 不存在，拒绝也未必证明物理累积失败机制。

### 4.3 模型预测的可辨识边界

- 在原始 trial 顺序可靠、每臂8次完整时，\`h_a(k+1)\` 的**经验描述**在原则上可复用现存数据，资格 \`DESCRIPTIVE_IDENTIFIABLE\`，正式估计仍需后来批准；
- 关于 \`F_a\` 的稳定估计、事件难度泛化/外推、M2 时间因果，属于 \`CONDITIONAL_IDENTIFIABLE\`，受 n=24、事件选择与重建机制限制；
- **不可将“预测性下降”直接授权 runtime STOP**：本协议研究的是离线重建 trial，不是在线连续动作或真实恢复。

## 5. H-OE3 → OE3：以未来 trial 为目标的证据充分性，不用事后 E/P 作为 oracle

### 5.1 应废止的目标

旧说法“由前 \`k\` 次预测完整16试得出的 E/P，并以其准确率决定最小试数 \`n^*\`”会把**预测证据本身**用于构造标签。尤其 P 是“完整双臂0/8”，在只观察前缀时无法成为独立的“本质持久”真值。

**保留** Stage R 冻结 E/A/P/U 作为描述性分层，**不**重分类或当作独立、潜在不可恢复真值。若以 E/P 分层作图，也必须承认后视选择，不能称无泄漏预测。

### 5.2 可讨论的后续结果 estimand（待下一阶段预注册）

对于同一个事件与同一臂，给定**截止 \`k\` 的合法观测前缀**，目标取自**严格未来的未见序列**：

\[
r_{a,k,m}=P(\exists j∈\{k+1,\ldots,k+m\}:Y_{eaj}=1
      \mid Y_{ea,1:k}=0,S_e,a),
\]

\`m≥1\` 且 \`k+m≤8\`。更保守的初始对象是 \`m=1\`（下一次重建尝试）。
结果中 \`ACQ/STABLE\` 两契约可各自定义一个目标，但需事先指定主要成功契约为 **Stage R frozen STABLE**，ACQ 只陪报；禁止根据看见的预测效果切换主要契约。

**数据使用纪律**：
- 对评估事件，预测只看 \`1..k\`，目标只来自 \`k+1..k+m\`；研究者知道 Stage R 总体报告 ≠ 新验证集是盲测；
- 模型族/先验/门槛若由已有数据决定，训练/选型必须**按完整 event 分组**，不能同一个 event 的后缀进入其前缀预测的参数拟合；
- 有限的 event 数和同一事件多个相似前缀导致结果强相关，误差单位仍为事件；
- 不能在已见结果后选最好 \`k,m\` 并称“预注册最优 \`n^*\`”。在正式审批阶段需按数据可用性预先锁定 estimand、候选 \`k\` 集合、评价规则与停止准则。

### 5.3 “证据足够”须绑定具体决策损失和适用域

候选抽象输出（不是控制命令）：
- \`INSUFFICIENT_FOR_DECISION\`：预测区间太宽或信号不可消费；
- \`SUFFICIENT_FOR_RETROSPECTIVE_RISK_DESCRIPTION\`：能对**已测 S_pre 重建分布**给出范围有限的描述/预测；
- \`EVIDENCE_NOT_TRANSFERABLE_TO_RUNTIME\`：只有离线真值、没有在线可得同域输入；
- \`NOT_IDENTIFIABLE\`：没有可分离的未来参考或数据/样本无法支持设定目标。

“几次才够”的 \`n^*\` 需指定具体误判代价、范围/覆盖要求与可接受不确定性；在没有独立验证及代价界定之前，**不要填任何数值**。即使离线预测合格，也不产生 \`REPORT_FAILURE\`/自动止损/技能晋升权限。

资格：未来 trial 目标若原始试次顺序、前缀/后缀配对存在，研究性回顾预测 \`CONDITIONAL_IDENTIFIABLE\`；泛化到真实在线 \`S_post\` 决策 \`OUT_OF_SCOPE\`；无泄漏 E/P latent 分类 \`NOT_IDENTIFIABLE\`。

## 6. 数据字典与权限审核清单（**尚未逐行/逐列检查**）

这是以后批准的**只读字段审查前置**，本阶段不得把假设打勾当作已核实。

| 需要核对的字段/元数据 | 目的 | 如缺失的降级 |
|---|---|---|
| \`event_id\`、任务 t3/t5/t9、selection/collect 记录 | 定义事件簇、已失败条件与样本外推 | 无法配对→预测估计 STOP |
| \`arm\`、重复 \`trial_index\`、执行顺序 | 单臂前缀/后缀、sham 有效性 | 顺序不可靠→只做计数描述、M2 NOT_IDENTIFIABLE |
| 冻结 \`ACQUISITION\`/\`STABLE\` 的逐 trial 结局 | OE1 分歧、OE2/3 结果 | 缺一则相关子问题停止 |
| \`stable\` 源自哪个测量时点、\`ACQ\` 是否为同源函数 | OE1 防自证与时间分离 | 无独立未来结果→独立 FP NOT_IDENTIFIABLE |
| \`S_pre\` provenance、PREFIX replay hash/实验次序 | 重建可比性、漂移/混淆 | 不可归一→只描述，不作强预测 |
| \`S_post\` NATURAL provenance、与 SAME/POLICY 差异 | 报告 out-of-scope 边界 | 不能转成在线推论（即使有） |
| \`visibility\`、sim-only truth 与 legally-observed outcome 的来源 | PAEG Gate 的字段级 firewall | Evolution eligibility 记 NOT_AVAILABLE |
| INFRA flag、缺失与修复记录 | 错误记录与非随机缺失 | 不可修复→按事先停规中止该目标 |

**本轮的证据级别**：H0 报告记录 CSV 在档与布尔列结构，但本次并未打开 CSV 检查列、时间与源可见性，所以清单中所有依赖现场核验的结论均标 **TO_VERIFY**。尤其当前未证明存在合法 Evolution outcome 和未来独立 reference outcome。

## 7. 后续协议冻结之前的必需登记项（此处只列字段、**不设置数值**）

1. **独立 estimand**：OE1 为描述分歧还是独立参考误报；OE2 下一次重建重试还是排序依赖；OE3 未来 suffix 预测还是已冻结 E/P 事后分层。
2. **参考数据结构**：decision-time 代理、物理真值和 future reference 的来源、时戳、合法性与互相重叠情况。
3. **验证方式**：事件级整体隔离的训练/评估分割、前缀/后缀锁定、task 层次、重复使用同一事件的关联校正、已知 Stage R 聚合结果导致的回顾性选择偏差。
4. **统计对照**：constant-q（M0）、event-/task-heterogeneous exchangeable-q（M1）、顺序剩余效应（M2），不偷换零假设。
5. **预指定主要结局/误差**：STABLE 为 primary，ACQ secondary；准确定义区间、校准误差/预测损失、拒判规则；阈值与样本约束由下一审批阶段确定，不能抄旧报告的 p 值或有利门。
6. **容量与失败条件**：24 event，P 全 t9，事件×臂分母；只读数据可用性和 bootstrap/不确定性方案，统计能力不足时明确 \`INCONCLUSIVE\`。
7. **STOP 逻辑**：独立参考缺失/OE1 独立 FP 停止；顺序无效/OE2 M2 停止；目标含前缀泄漏/OE3 该目标停止；必须新 rollout/在线策略数据才可答时整分支停。
8. **预注册冻结流程**：后续获批才可创建并审核冻结预注册/脚本哈希；此文件的状态始终是 \`DRAFT_NOT_PREREGISTERED\`。原数据已被 Stage R 分析过，不可声称“未观察过任何结果的盲预注册”。

任何新数据评估/统计检验/编写或执行分析脚本、数值门/功效验证及实际 \`α\` 与先验选择仍需要单独授权；Stage R 已冻结规则永远不重写。

## 8. Stage 1 文档 Gate 与可执行结论

**准入条件**（以研究文档论证检查，而非计算实验结果）：
- [x] 三个 OE estimand 按“同源契约描述 / 异质性条件未来重试 / 前缀→未来后缀”分别定义；
- [x] G1–G4 各有可能识别的最小对象与不能识别时的降级；
- [x] Stage R 事后 TYPE 与 \`S_pre\` vs \`S_post\` 隔离；
- [x] 输入权限、模拟真值与外推边界；
- [x] 模型层 M0/M1/M2 与 held-out 目标；
- [x] 只设计研究协议，无阈值冻结、脚本、计算或 rollout；
- [ ] **数据字段/时间切分的实际存在性仍待获批验证**；
- [ ] **新研究的可重复定标/算法贡献仍未成立**；
- [ ] **正式预注册及 H0 离线执行授权仍未获得**。

**阶段一预期裁决**：\`GO_FOR_PREREG_REVIEW_ONLY\`，表示协议内容可以提交下一审批，不等于 \`GO_FOR_STATISTICAL_EXECUTION\`。若未来字段审查证明不存在独立结果/有效顺序，需要缩窄 OE1/OE3，不得自行采集新 trial 补齐。

