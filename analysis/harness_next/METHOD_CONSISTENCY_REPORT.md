# METHOD_CONSISTENCY_REPORT — v0.2.1 一致性收敛报告

> 2026-10-09 | Method Consistency Finalization 轮交付物。
> 审查基线:`V02_INDEPENDENT_REVIEW.md`(独立复审,commit `431ddda`,
> 判定 REVISE);修订对象:`METHOD_SPEC.md` v0.2 → **v0.2.1**(commit
> `cc7e0d3` → 本轮)、`NOVELTY_REVIEW.md` v0.2 → **v0.2.1**。
> 性质:**纯研究文档修订**。零实验、零 rollout、零统计分析、零运行代码
> 改动、零预注册;Stage R §36 Hard STOP 保持生效,S1-DEV0 保持用户暂停。
> Stage R 冻结标签 **E14 / A1 / P5 / U4 原样保留**,本轮不做任何重分类、
> 不伪称重分析。

## 1. 结论(TL;DR)

**裁决:GO(规范层自洽性修订完成)——但"独立研究贡献"的准确表述是
"研究问题 + 概念契约"成立,"已证明的算法创新"不成立(依赖未做的定标)。**

- 独立复审的四个必修项 B1-B4 与五条附加边界,已全部在 METHOD_SPEC v0.2.1
  落地(逐项对照见 §2-§3,验收例见 §4);
- Zetta 对照更正(B6):其演化验证已有 exact McNemar 统计门,对照差异
  精确化为**统计对象不同**(候选改善验证 vs 失败持续性证据资格);
- N1 重构(B7):Reliability-Aware Persistence Evidence Qualification;
  经典统计方法如实标注为已有工具,不包装为首次提出;
- 下一步(定标 H0 方向 1、任何在线接线、U4 复核)均**超出本轮授权**,
  须用户另行批准——与本报告裁决无冲突:GO 的对象是"方法逻辑收敛已完成",
  不是"研究程序已完成"。

## 2. 必修项 B1-B4:原文缺陷 → v0.2.1 修复

### B1:E/A 分类重叠;κ_E 尝试数/成功数混用;DETERMINING 误作事后标签

| | 内容 |
|---|---|
| v0.2 原文缺陷 | §5.3:E = `n≥κ_min ∧ ∃y_i=1`(任一臂出现过成功)、A = `SAME 全 0 ∧ POLICY 存在 1`——**A 可推出 E**,类不互斥且 `classify_persistence` 无冲突优先级;κ_E 摇摆于"尝试数 n≥2"与"成功数 same≥2";DETERMINING 被列为第五个事后标签;末段暗示 Stage R U4 需按 v0.2 语义复核重分类 |
| v0.2.1 修复(METHOD_SPEC §5.3 重写) | ①事后标签**回归 Stage R 冻结四类**,以**臂内成功数**定义并显式判定顺序 E→A→P→U:E: s_SAME≥s_E(2/8);A: s_SAME=0 ∧ s_POLICY≥s_A;P: 双臂全 0 ∧ 覆盖 n_arm;U: 显式补集(s_SAME=1 或 s_SAME=0∧s_POLICY=1);②DETERMINING 重定位为**过程状态**(双臂未观测齐全/序列不可信),只存在于在线判断与中间步,非事后标签;③κ 槽位拆为**成功次数(s_E/s_A)与臂覆盖数(n_arm)**两个独立量纲;④**撤销 U4 重分类暗示**(任何重分类须另立批准的分析);⑤§7.1/§7.3/§7.2 R4/附录 A 同步(过程状态语义贯穿) |
| 验收例(复审 B1 要求,逐例可判) | `SAME 0/8 ∧ POLICY 2/8` → **A,不属于 E** ✓;`SAME 1/8` → **U,不自动 E** ✓;`SAME 2/8` → **E** ✓;`SAME 0/8 ∧ POLICY 1/8` → U ✓;双臂 0/8+0/8 → P ✓;不足 8+8 前缀 → **DETERMINING(过程状态/evidence state)** ✓ |

### B2:M0 未检验却称"被拒绝";单次失败≠零信息;runs 非 M1 充分统计;队列选择未声明

| | 内容 |
|---|---|
| v0.2 原文缺陷 | §5.5 写"'M0 被拒绝'是 Stage R h(k) 数据确证的事实"(无正式检验;h(k) 分母随连败筛选、单位=event-arm、不可把 pooled trials 当独立 N);§5.0/§7.2 把单次失败写成"零信息";§5.5 称 runs 是"M1 充分统计载体"(应为 (n_s,n_f));队列以已观察 FALSE_GRASP 选取的条件未声明 |
| v0.2.1 修复(METHOD_SPEC §5.0/§5.5/§7.2 R1b/R2) | ①M0/M1/M2 全部改标**假设层**;h(k) 低观察值改称**观察性迹象**,并写明分母筛选与单位问题,"拒绝/接受"表述须待获批检验;②在线档 NO_INFORMATION 改名 **INSUFFICIENT_FOR_DECISION**,附贝叶斯注:单次失败使 p(q_e\|y_1=0) 后验下移——档义是"不足以授权"而非"零信息";③充分统计更正:**(n_success, n_failure)** 才是 M1 充分统计,重排不产生额外后验信息;顺序增量只在 M2 层;"决策消费顺序"≠"顺序携带超计数信息";④新增**队列选择条件**段:原初失败是入选条件不计入 PE;外推域限"已失败为条件"的未来事件 |
| 三者严格区分(复审验收) | 现象 = h(k) 观察值(k=4: 1/17;k=8: 0/11 [D]);统计假设 = M0/M1/M2;是否完成检验 = **全部为否**(§5.5 "如实登记"明文) ✓ |

### B3:causal_grade 默认 STRONG 无理;群体 contrast≈0 不能排除事件级动作影响

| | 内容 |
|---|---|
| v0.2 原文缺陷 | §7.3 `STRONG if not uses_replay(e)`(未用重放 ≠ 因果强);§5.2/§7.3 把近零 contrast 写成"排除动作特异性"(群体平均可掩盖事件级;有限次数不确定性大);§7.5 禁 L1→L3 但伪代码可独立输出 POLICY/ENVIRONMENT/STRONG |
| v0.2.1 修复(METHOD_SPEC §5.2/§7.1/§7.3/§7.5 X3 注) | ①causal_grade 枚举改为 **{UNIDENTIFIED(默认), DESCRIPTIVE, MODERATE, STRONG}**;提升只能依赖独立列举的、满足有效性要求的干预/对照证据;②伪代码 Layer 4 重写为**三轴分离**(reconstruction_fidelity / execution_stochasticity / causal_identifiability),`not uses_replay → STRONG` 废弃,ρ<ρ* 保留为降档封顶;③contrast 收缩为"**已测条件下动作分布关联(群体平均)**",事件级不能排除——r129(SAME 0/8 而 POLICY 5/8 [D])写入反例;④causal_grade=UNIDENTIFIED 时 causal_hypothesis 强制 UNKNOWN,消除绕过白名单的独立出口 |
| 验收例 | 只有单次原生观测/无 replay 的事件 → causal_grade=UNIDENTIFIED,**不得 STRONG** ✓;群体 contrast 均值≈0 → 只输出"平均关联弱",**不得判"动作选择无影响"** ✓ |

### B4:A2b"不可逆≥一切可逆"仍是过宽全称

| | 内容 |
|---|---|
| v0.2 原文缺陷 | §6.4 A2b:∀不可逆决策门槛 ≥ ∀可逆决策——PROPOSE_REVIEW 实际只提名、可撤销;CONTINUE 可引发不可逆物理后果;单一 L0-L3 序数统一排序所有代价 |
| v0.2.1 修复(METHOD_SPEC §0 公理 A2/§6.4/§8.2) | ①**删除 A2b**;A2a 收缩为"错误后果 ∧ 证据类型均可明确排序的决策对"上的局部约束;②**决策三档建模**:候选审查(PROPOSE_REVIEW 等,可撤销)/正式部署(PROMOTE-DEPLOY,不在本方法授权内,属 Zetta Loop3 等工程环)/不可逆物理动作(物理损害风险**单独建模**,不与审查成本同序);③跨档比较是具体分析结论而非形式不变量,须逐对论证登记;④§8.2 代价表 PROPOSE_REVIEW 行改"可撤销",检验段改为仅 A2a 可对症 |
| 验收例 | 任意未证明代价与证据类型可比的两决策,不再写为形式不变量 ✓;物理损害风险与候选审查成本分开建模 ✓ |

## 3. 附加边界(边1-边5)修复对照

| # | 复审边界 | v0.2.1 落地(METHOD_SPEC) |
|---|---|---|
| 边1 | 在线/离线可得性 | **新增 §5.6**:observed_execution_prefix / offline_replay_cohort / cross_episode_history 三分层;Runtime 门只读前缀;事后标签结构上不可能在线产出;offline 层内部 Simulator Firewall 持续有效(真值判据连 Evolution 门也不得消费) |
| 边2 | 闭窗晚到窗口内证据 | **§4.3 新增段**:区分物理事件时间 vs 证据到达时间;晚到但时间戳 ∈ 窗内的证据生成 superseding 版本(append-only);t3 物理事件永远不能改变 t1-t2 事实 |
| 边3 | retry headroom ≠ skill 编辑 headroom | **§5.4 更名** NO_LOCAL_HEADROOM_OBSERVED → **NO_HEADROOM_IN_TESTED_RETRY_ACTIONS** + 三条语义限定;**§6.3** ABSTAIN 显式限定"仅对重试类候选",技能编辑类通道保持开放(UNKNOWN),不锁死 P 型 |
| 边4(=B6) | Zetta exact McNemar | NOVELTY_REVIEW §1.2/§1.3/§6/§0.2 更正 + 统计对象对照表(见 §5) |
| 边5 | L2 通道条件依赖 | **§4.2 新增"通道独立性风险"**(同源派生特征不独立,数量≠独立性)+ **§10.4 局限 8** 登记;逐对审计归 H0 方向 1,未执行 |

## 4. 复审 §5 验收清单逐条核对

| 验收要求 | 结果 |
|---|---|
| B1-B4 各有原文前后差异、反例及修正后可逐例判定的接口 | ✓ §2 各表(每项含 v0.2 原文缺陷 / 修复 / 验收例) |
| Stage R 冻结类型 E14/A1/P5/U4 保持原口径,不伪称重分析 | ✓ METHOD_SPEC §5.3 明文"原样保留,本规范不改判任何事件";U4 重分类暗示已撤销;§10.4-7 同步 |
| M0/M1/M2 现象、统计假设、是否完成检验三者严格区分 | ✓ §2 B2 表末行(现象/假设/检验=否 三行分列) |
| Online vs Offline 证据可得性与 Simulator Firewall 显式 | ✓ METHOD_SPEC §5.6(新表+三规则)、§10.2 |
| NOVELTY_REVIEW 不宣称基于未做的概率定标已完成算法创新 | ✓ NOVELTY_REVIEW §7 N1 边界段、§8.2 v0.2.1 边界、§0 TL;DR、R6 |
| 只做小范围研究文档提交,报告 SHA 与安全检查结果 | ✓ 本轮仅 3 个文档(2 改 1 增);SHA 与敏感检查见 §7 |

## 5. Zetta 对照更正(B6)与 N1 重构(B7)

**B6**:v0.2 把 Zetta Loop3 held-out 门写成"工程 k 轮对比"——不准确。
源码级核验([S-ext],`zetta/evolution/gating.py`):`one_sided_exact_mcnemar`
(line 12,精确配对二项单侧检验)、`evaluate_paired_gate`(line 202,seed+
bundle sha256 逐对绑定 + divergence/intervention 断言)、held-out 复合门
(line 320-350:p<α ∧ gain ∧ success_rate ∧ 无安全回退),docstring 自称
"preregistered two-stage test"。已让渡"演化验证的正式统计检验"先例;
差异精确化为**统计对象**:Zetta 检验"候选 vs 父代是否改善"(候选还不存在
时无从检验),PAEG 建立"失败持续性证据何时足以支持分类/弃权/授权"(候选
产生**之前**的证据资格)。两者互补。

**B7**:N1 重构为 **Reliability-Aware Persistence Evidence Qualification**:
有限重复执行 + 条件异质性 + 状态重建不确定性下,什么证据足以支持已测动作
分布内的失败风险判断/弃权/哪类决策可消费证据。经典方法如实标注(1971
序贯停止, informs.org;异质 Beta-Binomial, PMC10962580;robust
reliability/先验集, arXiv 1602.01650),**不宣称首次 Beta-Binomial/首次
序贯/首次 inconclusive/首次双门/首次统计门**。创新收窄到机制组合:
①物理状态重建不确定性作为证据资格一等输入(RESTORE-SENSITIVE 动力学
破坏"同一单元重复观测可比"假设);②双契约 outcome 证据资格(ACQ/STABLE
~35pp 摆动进入统计对象);③已测动作分布限定(分布内资格与分布外声称的
类型分离);④层间推导白名单。预测可信度/因果归因/可修复性三命题独立。

**独立研究贡献是否成立**:**有条件成立**——研究问题明确可操作、概念契约
无已知内在矛盾、九工作对照(经 Zetta 统计门让渡后)仍无 ● 级撞车的
空白集中在"持续性证据资格的统计学内容";但该内容的实质(定标/检验)
依赖 H0 方向 1 获批后的离线工作,**当前支持的是问题与契约,不是已证明的
算法**(R4/R6 登记此依赖)。

## 6. 本轮明确未做的事(边界重申)

1. 未运行任何 H0 方向 1 定标、预注册、新统计检验(复审 §5 禁令);
2. 未运行 rollout、未改执行代码、未启动 S1-DEV0、未训练模型;
3. 未调整 Stage R 冻结规则与 E14/A1/P5/U4 标签;
4. 未读 Zetta/RegenHarness/VASO 论文全文(残余风险 R1/R5 保持);
5. M1 拟合/sham 检验/κ·n_arm 定标/L2 通道独立性审计——全部登记为
   未执行,属未来另行授权的工作。

## 7. 变更文件与提交信息

| 文件 | 变更 | 规模 |
|---|---|---|
| `analysis/harness_next/METHOD_SPEC.md` | v0.2 → v0.2.1(§0.2 变更日志 + B1-B4/边1-3/边5 共 24 处修订) | 1069 → 1252 行 |
| `analysis/harness_next/NOVELTY_REVIEW.md` | v0.2 → v0.2.1(§0.2 变更日志 + B6/B7 共 14 处修订) | 380 → 526 行 |
| `analysis/harness_next/METHOD_CONSISTENCY_REPORT.md` | 新增(本文件) | 本轮 |

提交:单 commit,仅上述三个研究文档;敏感检查(密钥/原始日志/大文件)
与 fast-forward 推送结果见 git 记录(见汇报);不触碰 §36。
