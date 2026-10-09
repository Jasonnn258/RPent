# H0 Direction 1 · Stage 2B Analysis-Plan Gate Review

> 2026-10-09 | **研究文档独立审阅（无分析执行）**。
> 本轮对“go on”的执行范围：**Stage 2B 正式预注册方案审查与冻结准备**，未将其扩展为正式冻结、统计实验、分析脚本实现、rollout、训练或控制器授权。
> 主要交付：`H0_OE_STAGE2B_ANALYSIS_PLAN_CANDIDATE.md`（仍为 `DRAFT_FOR_FREEZE_REVIEW`）及对 Stage 2A 三文档的 `dev-r1-fix` 来源追溯补注。
> 方法来源：`analysis/stageR_prereg.md`、`analysis/STAGE_R_FINAL_REPORT.md`、`H0_OE_STAGE1_RESEARCH_PROTOCOL.md`、`H0_OE_STAGE2A_{FIELD_PROVENANCE_AUDIT,PREREG_DRAFT,GATE_REVIEW}.md`，此前 PAEG v0.2.2 的 evidence firewall。
> **未执行**：任何 result-sensitive 代码或读取/估计 `stable/acquisition` outcome 的数值分布、模型拟合、bootstrap、数据驱动阈值或新 trial。下列审核是源文档/数学接口的**规则审查**，不是模型性能验收。

## 1. 结论

**Stage 2B 方案设计交付：GO_FOR_SEPARATE_FREEZE_APPROVAL_REVIEW（附严格科学限定）**。

它只表示“已有一份可供用户决定是否正式冻结的候选分析计划”，并不表示计划已经正式预注册、模型已识别、预测效果已验证或能支持 N1 的原创算法主张。

**算法创新性状态：NOT_ESTABLISHED**。候选 M1 是经典 Beta-Binomial 事件异质性模型；在没有合法在线物理 outcome 作为预测输入、没有新的外部评估 cohort 的前提下，即便 M1 更准也只能支持**当前失败事件重建分布中的经典统计建模价值**，不能把它标成新的 embodied harness 机制。

## 2. 源文档发现：dev-r1-fix 精确解释额外 DEV checkpoint

Stage 2A 已确认 R1 480 个 CSV 唯一键与 checkpoint 逐键一致，同时有四条额外 `R0_DEV` SAME 记录。

本轮重新审阅 `analysis/STAGE_R_FINAL_REPORT.md §9`（附录 deviation 原文）发现：

- `dev-r1-fix(2026-10-08 05:59)` 载明 R1 首启误把 collect ledger 行号当作 included 序号，8 个 DEV 事件误入 R1 队列；05:01 停止时多跑 **4 trial**，且**CPS 日志保留越轨 trial 作为审计**。
- 本地用户实际检查发现恰有 `r09/SAME/1,2,3` 和 `r12/SAME/1` 四条额外 checkpoint；冻结 manifest 将两事件都标为 `R0_DEV`。
- **来源层级可从** `DEV_WRITE_ORIGIN_NOT_VERIFIED` **提升到** `DEV_R1_STARTUP_DEVIATION_DOCUMENTED`，有冻报对应说明；仍未做额外的日志字节级/写入时刻核验，不能声称它们在同一毫秒精确形成。
- 所有资产原字节保留，绝对不删除四条 DEV 日志、不把它们送入 R1 正式统计。
- Stage 2A 三份审计与预注册草案保留原历史“当时未验证”行，并**追加**该新来源结论，保证来源审计可追溯。

## 3. 拟冻结方案的核心技术审查

| 审查项 | Stage 2B 候选内容 | 结果 |
|---|---|---|
| 科学对象 | 只测 `entered stable FALSE_GRASP` 后独立重建 `S_pre` 的未来成功预测，非自然重试/Skill edit | PASS |
| 唯一主终点 | SAME 臂前两次冻结 STABLE 全败时预测第三次，`Y_{SAME,3}`；不把 E/P 全16试后视标签作为独立真值 | PASS（定义层） |
| baseline M0 | 留一事件，其余23个 event+当前留出事件已知的**两次失败**，共享 `q` 做 Beta(1,1) 更新 | PASS（公平信息接入） |
| baseline M1 | 同一 LOEO 训练事件拟合 `Beta(alpha,beta)` 混合率；留出事件只以已发生两失败更新其 `q_e` | PASS（候选模型，假设未经数据检验） |
| 评价 | 完整 event 留一、唯一主指标 Brier loss 的 event-level paired 差 | PASS（设计） |
| 小样本推断 | 固定 OOF `Δ_e` 的事件 bootstrap **不含模型重拟合不确定性**；明确只能描述，不能作名义显著性/算法通过的证明 | PASS WITH LIMITATIONS |
| OE1a | ACQ/STABLE 同源、嵌套，作为合同分歧描述；不主张独立假阳率 | PASS |
| OE3a | k=0/1/3 与 RESAMPLE 为同一预测 family 的探索报告；不伪称第二个独立方法 | PASS |
| M2/在线授权 | 没有时间戳或随机化；sim-only truth 不进 Runtime/Evolution | PASS（禁止越界） |
| 原始 cohort | 正式 R1 24 event、SAME/RESAMPLE 各8，CPS DEV 多余4条按 manifest role 拦截 | PASS（结构资格） |
| 数值门/模型拟合 | 候选 `eligible N≥12` 是保守报告门，**没有功效证明**；候选超参网格未运行，正式冻结须承担不确定性 | OPEN BEFORE FREEZE |
| 独立算法创新 | 只有 M0/M1 经典统计，没有新合法代理或不同于 M1 的 PAEG 统计机制、没有外部盲测数据 | **NOT_ESTABLISHED** |

### 为什么不能把一个 LOEO bootstrap 叫作“确认性显著性”？

每个 LOEO 的 `p_{-e}` 都由重叠的 23 个训练事件拟合，因此每个 `Δ_e` 并非严格相互独立。对已拟合预测的 `Δ_e` 简单做事件 bootstrap 并**不会**自动传播训练模型拟合误差，样本数也只有 24；更何况研究者在 Stage R 已公布汇总结果后才提出这一比较。

因此候选计划只允许 `M1_LOWER_OBSERVED_BRIER_IN_RETROSPECTIVE_COHORT`、负向或 `INCONCLUSIVE` 的描述性裁决。若将来需要严格的主假设检验，必须**先单独批准更完整的推断设计，冻结后才能运行**；不能看到差值后补做检验。

### 为什么主终点选择 SAME/k=2？

这是 Stage 2B **候选设计选点**，不是由后续未运行的模型优劣决定，更不是 Stage R 原预注册的独立随机 TEST。SAME 考察在固定动作分布下的有限失败证据；k=2 避免“一次失败就强分类”，但可能造成过小风险集。当前只引用已公开的 Stage R 分析，没有重新读取试次成败分布。若届时符合主风险集的事件数低于保守下限（候选12），**按草案直接报告描述性不足**，不得因样本少改成有利 k。

### 需要主动承认的三类“负贡献”

1. **OE1a 的已知性**：原 Stage R 就有 ACQ−STABLE 差，数学恒等关系来自同一测量和蕴含，不能宣称首次发现假阳率。
2. **OE2a/OE3a 的标准性**：heterogeneous Bernoulli / Beta-Binomial、前缀条件预测、留一事件评价均为经典方法。若 M1 优于 M0，结论是条件风险建模获有限**回顾性**经验支持。
3. **证据授权仍无合法在线代理**：若必须使用 sim `check_success`/pose 才获得 Y，它仍是研究真值；PAEG 的 Runtime/Evolution Gate 的部署可行性和任何技能修复效果均没有被评估，正面 N1 论文 claim 必须 HOLD。

## 4. 五项冻结前强制审阅与选择

**F1. 结局与集合**：固定使用 SAME `k=2, Y3`、`role=R1_COHORT`、首次 FG 仅做入组条件，NATURAL/DEV 不进预测。用户应决定是否继续推进**仅能回答此窄问题**的分析；不能越过证据作用域。

**F2. 指标与推断定位**：Brier 主 loss 与差值可作为唯一主要**描述性**比较，固定 OOF event-bootstrap 不能写严格显著性。若用户需要确认性统计保证，应在冻结前重新设计、不可事后改名。

**F3. 模型公平与敏感性**：M0 与 M1 都能使用留出事件 k=2 已知失败；M1 的候选超参网格、边界拟合失败规则、task 混合限制需在用户决定冻结时一次性签收。本轮没有代码实现/运行。

**F4. 负面门与功效**：`eligible N≥12` 是粗保守指标，仅控制“不足样本仍夸大结论”的表述，**不是**事前 power guarantee；如果未来研究者希望严谨的显著性结论，必须在冻结前审查是否有足够样本，绝不通过改变 K 或重新挑事件救结果。

**F5. 用户授权与独立验证**：需独立批准正式冻结的研究计划（可能新建只读 freeze artifact、记录实际数据/脚本 SHA）；真正的任何结果统计/拟合、分析脚本执行、模拟仍需另一次批准。任何新 rollout、Pi0.5 模型或 Control/Evolution 实施均不在此线的授权范围。

## 5. 本次只读/写入审计与交付

- 已核对 Stage R §9 deviation、Stage R 预注册 §5–§8/§36、Stage 2A 数据键审计和本阶段预注册候选的数学定义；
- 新增 `analysis/harness_h0/H0_OE_STAGE2B_ANALYSIS_PLAN_CANDIDATE.md` 与本 `H0_OE_STAGE2B_GATE_REVIEW.md`；
- 追加 Stage 2A 三文档的 DEV 来源追溯补注（不覆盖旧原始审计结论）；
- **零统计**：没有读取试次的 `stable`/ `acquisition` 作为效果计算、没有生成训练/统计脚本、没有模型拟合/样本 bootstrap、没有 env boot/rollout/训练；
- 原冻结 E14/A1/P5/U4、Stage R §36 Hard STOP、S1-DEV0 ON_HOLD 不改变。

**阶段性裁决**：Stage 2B 方案候选已完成，可提交用户进行**另行正式冻结决策**。当前状态仍是 `DRAFT_FOR_FREEZE_REVIEW`。算法创新 `NOT_ESTABLISHED`，实验/定标 `HOLD`。
