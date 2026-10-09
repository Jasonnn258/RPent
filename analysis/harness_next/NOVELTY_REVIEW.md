# NOVELTY_REVIEW — 独创性审计与收缩判定

> 2026-10-09 | 版本 **v0.2.2**(Post-MCF evidence interface 修订)| 配套
> `METHOD_SPEC.md`(同日 v0.2.1)。
> v0.1 见 git `adf5d18`;v0.2 见 git `cc7e0d3`(Zetta 源码重核 + N1 收缩,
> 变更日志 §0.1);v0.2.1 按 `V02_INDEPENDENT_REVIEW.md`(commit `431ddda`)
> 做两处更正:①Zetta 演化验证已有 exact McNemar 统计门(gating.py 源码级,
> 修订 v0.2 的"工程门槛"表述)并明确其与 PAEG 的**统计对象差异**;②N1
> 重构为 Reliability-Aware Persistence Evidence Qualification 框架,经典
> 统计方法(Beta-Binomial、异质性建模、序贯停止)如实标注为**已有方法**,
> 不得包装为首次提出的算法。变更日志 §0.2。
> 任务:对照最接近的公开工作(重点 Zetta、EmbodiSkill、CheckVLA、RegenHarness;
> 侧翼 SHAPER、SkillOpt、SafeManip、VASO、CommitFlow),判定 PAEG 各组件的
> 不可替代性;**发现先例即主动收缩创新声明**(用户指令与提案 §4 收缩条款)。
>
> **本轮核验方法与等级**:
> - **[S] 源码级**:Zetta、EmbodiSkill、SkillOpt(S0 期 REFERENCE_CODE_AUDIT 完成,
>   本轮引用其结论);
> - **[S-ext] 外部仓库源码级(v0.2 新增)**:Zetta main 分支 tarball
>   (codeload.github.com,2026-10-09 下载),对 `zetta/evolution/` 模块
>   逐文件核验 unresolved/inconclusive 机制——v0.1 的"归因克制空白✓"判定
>   即在此级被推翻;
> - **[P-abs] 摘要级全文**:RegenHarness(arXiv 2609.27612)、CheckVLA(2607.26789)、
>   CommitFlow(2609.21908)、SafeManip(2605.12386)、VASO(2606.05395)——
>   v0.1 轮新增:五篇 arXiv 摘要页全文逐句核验(此前仅有提案表格级 [P] 描述);
> - **[P] 出版页级**:SHAPER(2608.11350)。
> - 摘要级核验的含义:确认机制存在性与概述,**不等同全文对齐**——凡结论依赖
>   "论文全文中不含 X"的判断,均标注残余风险(§9)。源码级核验同理:
>   Zetta 论文全文未读(残余风险 R5,§9)。
> - 跨基准数字不可直接比较;所有外部结果按原作者报告表述。

---

## 0. 审计结论(TL;DR)

**提案的三条候选创新,经五篇新核验后:一条核心保持(C2)、两条按预设条款收缩
(C1、C3)。方法整体仍具备可辩护的独立空间,但其表述必须从"提出双门/时效声明"
收窄为"物理执行随机性下的失败持续性证据学 + 决策分层授权语义的统计特化"。
v0.2 追加:Zetta 源码重核推翻 v0.1 的"归因克制空白"判定,N1 再收缩一次
("允许 abstain"的立场让渡,"abstain 的统计学判据"保留为核心)。**
**v0.2.1 追加:①Zetta gating.py 核验出 exact McNemar 配对门——"演化验证的
正式统计检验"亦让渡,对照差异精确化为统计对象不同(候选改善验证 vs
持续性证据资格,§1.3);②N1 重构为 Reliability-Aware Persistence
Evidence Qualification:经典统计工具如实标注为已有,创新限定在
"物理重建不确定性 + 双契约证据资格 + 已测分布限定 + 层间白名单"的
机制组合;H0 方向 1 定标未做之前,支持的是研究问题与概念契约,
不是已证明的算法。**

1. **C2(Persistence-Aware Attribution)= 核心创新,保持(v0.2 再收缩表述)**。
   九个工作无一给出"随机物理执行下,有限重复失败证据对持续性与可修复性的
   统计语义"。EmbodiSkill 的 defect/lapse 分流在概念上最近,但判据是 LLM
   反思式、无证据量概念、无重建保真处理;RegenHarness 有执行记录驱动的演化
   治理但无统计化持续性分析 [P-abs];**Zetta(v0.2 核验)已有 unresolved/
   inconclusive 的克制出口 [S-ext],但其 unresolved 由 LLM 定性判断产生,
   无证据量函数、无异质性/选择效应分析、无连败信息价值的统计处理**——
   C2 的核心收缩为"持续性分类与 abstain 的**统计学判据**",而非"允许弃权"。
2. **C1(Decision-Dependent Eligibility)= 按条款收缩(v0.2 表述更新)**。
   CheckVLA 已做 conformal 校准的干预风险阈值(单决策类型)[P-abs];
   RegenHarness 已有 identity/version-bound commit gate 骨架 [P-abs];
   Zetta 已有 Loop1/Loop3 双时间尺度的工程分离 [S]。**"有两个门"与"校准过
   的门槛"均非空白**。收缩后 C1 = "同一证据面对不同决策类型的充分性差异
   作为形式对象(**代价对齐偏序**(v0.2:取代"授权单调性",METHOD_SPEC
   §6.4)、abstain 一等公民、错误代价不对称的定性偏序)"。
3. **C3(Temporal Claims)= 按条款收缩(不变)**。版本化事实(RegenHarness)、
   LTLf 时序谓词(SafeManip)、commitment 维持监控(CommitFlow)、进度证据
   保留(CheckVLA keyframe bank)均已有 [P-abs]。收缩后 C3 = "物理窗口失效
   语义(闭窗终态不可否定、不可继承、撤销不追溯)与决策授权的耦合",仅作为
   C2 的信息底座,不单独主张。

## 0.1 v0.1 → v0.2 变更日志

| # | v0.1 判定 | v0.2 更正 | 依据 |
|---|---|---|---|
| 1 | §1.2 "归因克制/UNKNOWN:无(聚类必须产出候选),空白✓" | **错误,推翻**:Zetta 有 unresolved group(聚类视觉证据不支持共同机制时返回 unresolved 组而非 fallback 合并,stages.py:92)、inconclusive diagnosis 终态(lifecycle.py:3456)、no_actionable_cluster_diagnosis campaign 终态、inconclusive gate 不能 pass(models.py:731) | [S-ext] 源码行号级 |
| 2 | §1.2 "重建保真降级:无,空白✓" | **部分推翻**:Zetta shadow replay 不完整时"retained as inconclusive evidence"(不前向填充、不丢弃)——已是"保真不足→降级证据用法"的定性机制;但无定量保真阈值(ρ*)与系统降档规则 | [S-ext] shadow_replay.py |
| 3 | §1.3/§7 "PAEG 保持的差异:无 abstain、无证据量定标" | 前半句作废(Zetta 有克制出口);后半句加强:Zetta 源码自证"Confidence ranks hypotheses but is not evidence from a live intervention"(lifecycle.py:2577)且 `confidence_is_not_an_authorization_gate` 默认 0——**Zetta 自己承认其置信度不是证据、默认不作授权门**,这为"证据力的统计定标"空白提供了对方源码级的锚点 | [S-ext] |
| 4 | §7 N1 "含连败时序结构的信息量" | 措辞收紧为"连败信息的分层解释(M0/M1/M2,异质性选择效应 vs 真时序)"——v0.1 的"h(k)<iid ⟹ 连败史携带超信息"是过度解读 | METHOD_SPEC §5.5 |
| 5 | §7 N2 "授权单调偏序" | 改"代价对齐偏序 + 不可逆性约束"(v0.1 全局单调性被自身矩阵违反,已废弃) | METHOD_SPEC §6.4 |

## 0.2 v0.2 → v0.2.1 变更日志(Method Consistency Finalization)

按 `V02_INDEPENDENT_REVIEW.md`(commit `431ddda`)§3-4 更正:

| # | v0.2 表述 | v0.2.1 更正 | 依据 |
|---|---|---|---|
| 1 | §1.2/§1.3 将 Zetta Loop3 held-out 门描述为"工程 k 轮对比",未提其统计检验 | **Zetta `zetta/evolution/gating.py` 已实现 `one_sided_exact_mcnemar`(精确配对二项检验,单侧 P[X≥wins])+ 增益/成功率/无安全回退复合门**,且为预注册两阶段测试;不得再称"Zetta 无统计判据/没有正式统计门"。真正的差异是**统计对象不同**:它检验"候选是否相对父代改善"(候选改善验证门),PAEG 建立的是"失败持续性证据何时足以支持分类/弃权/授权"(证据资格);两者互补而非空白对照 | [S-ext] gating.py:12(one_sided_exact_mcnemar)、:202(evaluate_paired_gate)、:320-350(heldout 复合门) |
| 2 | §7 N1 表述为"失败持续性与弃权的统计学判据",未区分经典统计方法与新的应用对象 | 重构为 **Reliability-Aware Persistence Evidence Qualification**:经典方法(Beta-Binomial、异质性建模、序贯停止、稳健先验集)全部如实标注为已有工具,创新声明收窄到**新机制组合**(物理状态重建的不确定性 + 双契约 outcome 证据资格 + 已测动作分布限定 + 层间推导白名单),不宣称"首次 Beta-Binomial/首次序贯/首次双门/首次 inconclusive" | 复审 §4;经典文献三条(1971 序贯停止 / 异质 Beta-Binomial / robust sets-of-priors,见 §7) |
| 3 | §7 N2 含"不可逆性约束(不可逆决策门槛≥一切可逆决策)" | METHOD_SPEC v0.2.1 已删除 A2b 全称命题(改为决策三档建模);N2 表述同步删除该引用 | METHOD_SPEC §6.4 |

---

---

## 0.3 v0.2.2: Evidence Authorization Interface Repair 与外部原文边界

> 来源: `POST_MCF_INTERFACE_AND_LITERATURE_AUDIT.md` 与
> `EVIDENCE_INTERFACE_REPAIR_REPORT.md`。此节是**追加核验**,
> 不回写 v0.1-v0.2.1 的历史审计结果。

1. **来源可见性 ≠ 统计信息量**:完整 SAME/POLICY 8+8 是冻结
   `S_pre` 的离线研究证据,不保证在线 Runtime 可用;若 E/A/P/U
   标签依赖仅审计 sim 真值,就不能拿来驱动 Evolution candidate gate。
   “证据统计上强”与“证据有决策使用权”须分开证明。
2. **接口自洽性已修订(v0.2.2)**:进化门修复 UNIDENTIFIED/UNKNOWN
   可能越过 D2 的反例;单次成功不再绕过 Stage R 冻结 E 判据;
   仅离线 P 案例不再赋 Runtime `REPORT_FAILURE=ALLOW`。
   这些是必要的规范正确性修复,**不能自动宣称算法创新**。
3. **CheckVLA [F:论文 HTML 方法与限制段]**:
   https://arxiv.org/html/2607.26789
   其 conformal 校准针对“nominal-success 条件下,episode 第一次
   不必要干预”的概率,以相同冻结流程下校准/部署 exchangeability
   为前提;不覆盖失败召回、修复后安全、重复干预或分布偏移。
   这证明“限定保证对象/有效前提”的方法思想已有先例,
   不能为 PAEG 独占。
4. **VASO [F:论文 HTML 方法与 Failure Case]**:
   https://arxiv.org/html/2606.05395
   其形式验证依赖 proposition-aligned labeling function 的正确性,
   作者给出忽略速度第三维而得到虚假安全验证的具体反例。
   这证明物理信号→命题映射保真性是成熟先例;
   PAEG 的 L0–L3/claim 契约只有在聚焦物理 reset、双 outcome 合同与
   合法消费权限的独特交互时才有条件讨论创新。
5. **核验深度边界**:以上两篇只核验所述 HTML 原文方法/局限/失败例章节;
   Zetta 源码先例继续标 [S-ext];RegenHarness 与 Zetta 本轮仍未成功
   核验论文全文,不得据其摘要/源码缺乏某术语断言全文没有统计方法。

**收缩后定位**：N1=Reliability-Aware Persistence Evidence Qualification
仍是研究问题候选;“抽象权限/校准/条件保证本身新颖”的表述让渡。
需要先证明真实可消费信号与独立结果目标可获得,再考虑离线定标;
这次文档修订没有实验验证新算法。

---

## 1. 重点对照一:Zetta(arXiv 2608.16590)[S-源码级 + P-项目页 + S-ext-v0.2]

### 1.1 机制摘要

三时间尺度闭环:Loop1 Critic-Governed Action Loop(action 频率,代码化 critic
监控物理状态、偏离触发 recovery);Loop2 Candidate Optimization(失败 rollout
按最早可观测分歧聚类、因果诊断、生成候选 critic/recovery);Loop3
Validation-Gated Skill Update(历史回归 + held-out 泛化门 → 版本化 skill
memory)。LIBERO-Pro 90.8%(+56.3pt)。源码级确认:critic_runtime.py 的运行时
监控、role1_recovery.py 的恢复与配对同 seed 重放 [S]。

**v0.2 补充(本轮 [S-ext] 新核验,修正 v0.1 的重大遗漏)**:Zetta 的演化
模块(`zetta/evolution/`)内置一套**不可归因的处理机制**,v0.1 曾误判为
"聚类必须产出候选、无归因克制"。实际机制(源码行号级):

1. **unresolved group**(`stages.py:92`):聚类 prompt 明示"If the visual
   evidence cannot support a common mechanism, return an unresolved group
   rather than merging on a fallback label"——视觉证据不支持共同机制时,
   返回 unresolved 组而非强行贴标签合并;
2. **inconclusive diagnosis 终态**(`lifecycle.py:3456`):
   `_diagnosis_is_inconclusive` 判定 root_cause 以 "inconclusive" 开头的
   诊断;campaign 可终结于 `no_actionable_cluster_diagnosis`;
3. **inconclusive gate 不能 pass**(`models.py:731-732`):门证据不足时
   的语义是"不通过"(区别于"失败");
4. **provisional authorization**(`lifecycle.py:3874+`):inconclusive 诊断下
   允许"Auditably test a strong leading hypothesis without relabeling
   diagnosis"——不重贴标签地测试一个可证伪候选,配 relaxed timeboxed gates;
5. **不完整 shadow replay → inconclusive evidence**(`shadow_replay.py`):
   重放不完整时不前向填充、不丢弃,保留为"inconclusive evidence for the
   online gate";
6. **置信度非证据的显式注释**(`lifecycle.py:2577-2579`):
   "Confidence ranks hypotheses but is not evidence from a live
   intervention";策略参数 `provisional_min_diagnosis_confidence` 默认 0,
   `confidence_is_not_an_authorization_gate`——置信度默认**不**作为授权门,
   仅排序假设,且若启用须显式预注册。

### 1.2 与 PAEG 逐组件对照(v0.2 修订版)

| PAEG 组件 | Zetta 对应物 | 判定 |
|---|---|---|
| 证据等级 L0-L3 | 无(critic 输出=代码化条件是否触发;聚类证据分层为确定性 medoid 优先的定性预算) | 空白 ✓ |
| Claim 时效/撤销 | 无(critic 是即时判断,无声明账本) | 空白 ✓ |
| DETERMINING/E/A/P/U 持续性分类(v0.2.1:E/A/P/U 事后四类 + DETERMINING 过程状态,Stage R 冻结口径) | Loop2 的失败聚类(启发式,LLM 辅助)+ unresolved group | 概念近、机制异;**unresolved≈U 类的定性版(v0.2)** |
| 归因克制/abstain 的**设计立场** | **有**:unresolved group / inconclusive 终态 / inconclusive gate(v0.1 误判"无") | **先例,让渡(v0.2 核心更正)** |
| 归因克制的**统计学判据**(证据量函数/异质性后验/连败信息价值/κ 定标) | **无**:unresolved 由 LLM 视觉证据判断产生;源码自证 confidence 非证据且默认不作门 | **空白 ✓(N1 收缩后的核心)** |
| 重建保真降级 | **部分有**:不完整 shadow replay → 保留为 inconclusive evidence(定性);无定量阈值 ρ*、无系统降档规则 | 部分让渡;定量语义保持 ◐ |
| Runtime/Evolution 分层 | Loop1 vs Loop3(工程分离) | **结构先例,让渡** |
| 验证门 | Loop3 held-out 门:**exact McNemar 配对检验 + 增益/成功率/无安全回退复合门**(v0.2.1 更正:非单纯"k 轮对比"的工程门槛) | **先例,让渡;且含正式统计检验** |
| SAME 配对重放 | role1 的 paired same-seed [S] | **技术先例,让渡** |

### 1.3 判定(v0.2.1 修订)

Zetta 回答"闭环 critic-recovery 演化**是否有效**"(90.8%);PAEG 回答"其依赖的
outcome 证据**何时才可信**"。

**v0.2.1 Zetta 统计门更正([S-ext],`zetta/evolution/gating.py`)**:v0.2 曾把
Zetta 的 Loop3 held-out 门描述为"工程 k 轮对比"——**不准确**。源码核实:
`one_sided_exact_mcnemar`(gating.py:12)实现精确配对二项检验
(P[X ≥ candidate_wins],X~Binomial(discordant, 0.5));`evaluate_paired_gate`
(gating.py:202)按 seed+bundle sha256 逐对绑定并断言 divergence/intervention
一致;held-out 晋升门(gating.py:320-350)= p<α ∧ gain≥min ∧ success_rate≥min
∧ 无安全回退,模块 docstring 自称 "preregistered two-stage test"。**因此不得
声称"Zetta 无统计判据/没有正式统计门"**。正确的对照是**统计对象差异**:

| | Zetta gating | PAEG 资格层 |
|---|---|---|
| 统计对象 | 候选 vs 父代的**改善验证**(配对成功率差,同 seed 配对) | 失败持续性**证据资格**(有限重复证据何时足以分类/弃权/授权) |
| 零假设 | 候选不优于父代(单侧配对) | M0 同质 iid / M1 异质 iid(§5.5,均未检验) |
| 输入数据 | 候选与父代的 rollout 对 | 同一失败事件的 SAME/POLICY 重试臂 + 观测前缀 |
| 结论 | 晋升/不晋升(演化动作) | 分类/弃权/授权资格(不作演化动作) |

即:Zetta 已占"**候选改善的统计验证门**"席位;PAEG 的空白在"**执行失败
持续性证据的统计资格**"——后者在候选还不存在时(无候选可配对)就要判定
"该失败是否值得进入候选流程"。两者互补,PAEG 不再以"对方无统计门"立论。

**必须让渡的声明(v0.2 扩充,v0.2.1 追加统计门)**:
- "双时间尺度分离"、"配对同 seed 重放对照技术"、"held-out 晋升门"(v0.1 已让渡);
- **"演化验证的正式统计检验"(v0.2.1 追加让渡)**——exact McNemar 配对门
  已实现且预注册(见上),PAEG 不得声称"给演化流程首次引入统计门";
- **"允许分不出来/unresolved/inconclusive 的克制立场"(v0.2 新让渡)**——Zetta
  已把"允许 inconclusive"做成了工程语义(终态、门、campaign 出口);
- "不完整重放不作对照"(v0.2 新让渡)——shadow replay 的 inconclusive 保留
  已是该思想的定性实现。

**保持的差异(v0.2 收缩后)**:Zetta 的 unresolved/inconclusive 是 **LLM 定性
判断驱动的工程出口**——何时返回 unresolved 由聚类 prompt 的视觉检视决定,
无证据量概念、无异质性(选择效应)分析、无连败信息价值的统计解释;其源码
自己承认"Confidence ranks hypotheses but is not evidence from a live
intervention"且默认不作授权门 [S-ext]。PAEG/N1 的独立空间因此精确化为:
**把"分不出来"从工程裁量变成统计对象**——证据量函数(evidence_mass 与 κ)、
异质性混合下的连败后验(§5.5 M1)、abstain 的可证伪充分性判据(何时必须
弃权 vs 何时证据已足)、重建保真的定量降级(ρ*)。仍为互补关系:PAEG 可
为 Zetta 式系统的 unresolved/inconclusive 出口提供统计学判据,与 H0 审计
结论一致。

---

## 2. 重点对照二:EmbodiSkill(arXiv 2605.10332)[S-源码级]

### 2.1 机制摘要

Skill-aware reflection 将失败区分为 Skill Defect(技能本身错,触发技能正文
更新)与 Execution Lapse(执行偶发失手,不触发更新);版本化手册;主要在
ALFWorld/EmbodiedBench。

### 2.2 与 PAEG 对照

| 维度 | EmbodiSkill | PAEG |
|---|---|---|
| 分类对象 | defect vs lapse 二分 | E/A/P/U 四类(Stage R 冻结)+ DETERMINING 过程状态 + repairability 独立轴 |
| 判据来源 | LLM 轨迹反思 | 预注册统计序列(重复实验证据) |
| 所需证据量 | 未处理(一次反思即分流) | 一等对象(evidence_mass + κ 槽位;单次失败=DETERMINING 非瞬态) |
| 无法归因时 | 必须分到两类之一 | U 类显式 abstain(实证:U 型 4/24 [D];注:克制立场本身 Zetta 亦有 [S-ext],PAEG 差异在判据) |
| 随机性处理 | 无(单轨迹语义判断) | 核心(边际率、连败结构的 M0/M1/M2 分层解释) |

### 2.3 判定

**概念先例让渡**:"执行偶发失败 ≠ 技能缺陷、不应触发技能更新"的思想属于
EmbodiSkill(及 SkillOpt 的 EXECUTION_LAPSE 保护区 [S]),PAEG 不得声称首次
提出该区分。**保持的差异**:该区分的**统计证据学**——分流所需最小证据量、
连败史的预测信息、E/P 完美分离的实证结构(E 14/14 vs P 5/5 [D])、
repairability 与 persistence 的解耦——九个工作均未涉及。这是 C2 的最硬资产。

---

## 3. 重点对照三:CheckVLA(arXiv 2607.26789)[P-abs 本轮新核验]

### 3.1 摘要级机制(逐句核验)

冻结 VLA 的执行期验证:单独训练的冻结 action-conditioned world model;
**conformally calibrated risk threshold 界定 episode 级"不必要首次干预"概率并
决定何时干预**;超出幅度控制改写后缀保留多少被替换 chunk;latency-aware
hard prefixing;**event-driven keyframe bank 跨修复保留先前进度证据**。
RoboCasa365 36.1% vs 27.6%;matched 5% 假警下 timely recall 77.9% vs
48.6%(observation-only)vs 37.9%(action-shuffled)。

### 3.2 撞车判定(这是本轮最重要的收缩触发)

| PAEG 声明(候选形态) | CheckVLA 已有 | 判定 |
|---|---|---|
| "校准的决策门槛" | conformal 校准的干预风险阈值,episode 级 FPR 控制 | **撞车,弃用** |
| "执行期证据驱动干预时机" | 何时干预 = 阈值决定 | **撞车,弃用** |
| "跨修复保留进度证据" | keyframe bank | 部分重叠(它是保留,非可撤销授权) |
| 决策**分层**(runtime vs evolution) | 无(单决策类型:intervene) | 空白 ✓ |
| 失败持续性归因 | 无(处理 deviation 检测,非失败会否持续) | 空白 ✓ |
| 有限重复证据统计 | 无 | 空白 ✓ |
| 方法路线 | 学习式 world model(§36 禁类) | 不同(PAEG train-free 符号/统计) |

### 3.3 判定

CheckVLA 坐实了"**统计校准的单决策门槛**"先例。收缩执行:PAEG 的 C1 表述
从"提出证据充分性门槛"改为"**决策类型×证据类型的分层授权语义**"——
CheckVLA 校准的是一个门,PAEG 形式化的是门族之间的偏序(授权单调性)与
共享证据面的两视角读取。同时如实记录:CheckVLA 的 conformal 方法是未来
PAEG 常数定标可借鉴的技术(其本身不构成 PAEG 先例,因对象不同)。

---

## 4. 重点对照四:RegenHarness(arXiv 2609.27612)[P-abs 本轮新核验]

### 4.1 摘要级机制(逐句核验)

明确区分 model proposal / controller termination / verified completion;
model loop + agent loop(dispatch、observation、verification、commitment、
bounded recovery);四角色隔离上下文;**versioned memory 区分 observed facts 与
accepted task progress**;**identity- and version-bound commit gate 控制对
trusted task state 的更新**;duplicate-dispatch 控制、resource leases、
recovery budgets;上报完成前检查原始目标;RSI 协议:execution records motivate
候选修改(context rules / task templates / routing / recovery policies),
fixed regression checks + release authorization 管接受,versioned
rollout/rollback;不改模型权重、不削弱 commit gate;真机四足部署;
"completion depends on execution history rather than endpoint proximity alone"。

### 4.2 撞车判定(触发提案 §4 预设收缩条款 1)

| PAEG 声明(候选形态) | RegenHarness 已有 | 判定 |
|---|---|---|
| proposal/termination/completion 三分 | 摘要首句即此三分 | **撞车,弃用** |
| "observed facts ≠ accepted progress" 分离 | versioned memory 的核心区分 | **撞车,弃用** |
| 更新提交门 | identity/version-bound commit gate | **骨架撞车** |
| 版本化/回滚治理 | versioned rollout/rollback + regression checks | **撞车,弃用** |
| bounded recovery 预算 | recovery budgets | 先例,让渡 |
| 失败持续性统计(E/A/P/U、连败、双臂对照) | 摘要层未见 | **空白 ✓(核心)** |
| 证据等级/时效/撤销的时间语义 | 版本化 ≠ 时效化(无 time-to-validity、无物理窗口失效) | **空白 ✓** |
| "决策类型×证据强度"的充分性语义 | commit gate 是身份/版本控制,非充分性分级 | **空白 ✓(C1 收缩后形态)** |
| 随机执行下的有限重复证据 | 摘要层未见(真机单次任务流叙事) | **空白 ✓** |
| 重建保真降级 | 摘要层未见 | 空白 ✓ |

### 4.3 判定

**收缩条款 1 正式触发**:RegenHarness 已覆盖"一般 Evidence Eligibility 的
工程骨架"(提案 §6 预设:"如果 RegenHarness、VASO、CommitFlow 已覆盖一般
Evidence Eligibility,核心创新缩小到 physical persistence × decision-specific
thresholds")。执行该收缩:

- C1 从"决策分层门设计"降为"**物理持续性 × 决策特定证据强度的统计语义**"
  ——与 RegenHarness 的差异不在门的存在,在门输入的**证据质量学**;
- C3 的版本化/提交/回滚部分全部让渡;保留的仅是**物理时间语义**
  (time-to-validity、不可继承、撤销不追溯)——RegenHarness 的版本化事实
  是标识符维度的有效性控制,PAEG 的是物理窗口维度的有效性控制,方向不同;
- **C2 地位反而增强**:RegenHarness 的 RSI 由 execution records 驱动候选修改,
  但摘要层没有任何"失败持续性的统计处理"——它的证据面假设记录是可靠的,
  PAEG 恰好研究"记录里的失败信号何时可信"。

---

## 5. 侧翼对照(SHAPER / SkillOpt / SafeManip / VASO / CommitFlow)

**SHAPER** [P]:冻结模型自任 planner+optimizer,联合演化 skills 与 context-code
harness。占据"冻结模型自优化 harness"席位;无证据学组件。无新收缩。

**SkillOpt** [S]:文本 Skill 可优化 + held-out 晋升 + 拒绝缓冲。占据"候选编辑
验证治理"席位。无新收缩。

**SafeManip** [P-abs 本轮新核验]:LTLf 有限轨迹时序安全模板(含 grasp
stability / release stability 八类),rollout→符号谓词迹→monitor,定位为
**评测层**。收缩执行:**"把抓取稳定性形式化为时序谓词"不得列为 PAEG 创新**;
PAEG 的 STABLE 契约与之同思想(且 RPent 双契约先于本轮已知该工作 [P])。
差异:SafeManip 评测量"是否违反谓词",PAEG 治理"证据何时授权决策"——
前者是真值监控,后者是证据充分性。

**VASO** [P-abs 本轮新核验]:skill = 形式化 semantic contract(model checking
接口 + planner 接口);反例 → textual gradient → 更新技能合同,权重冻结;
97.2% 形式规约合规。**关键摘要原话**:既有信号"provide only trace-level
evidence: they show that a skill worked on sampled executions, not that
skill-induced plans satisfy temporal safety contracts under untested
conditions"——**"trace 级证据不足以信任技能"的动机论述属于 VASO,让渡**。
差异:VASO 的解答是**形式验证**(二值合规,反例驱动);PAEG 的解答是**随机
物理执行下的经验证据统计**(连续证据量、显式 UNKNOWN)。两者处理"信任技能"
的不同失败模式:VASO 管未测条件下的逻辑违规,PAEG 管已测条件下的随机性与
归因歧义。

**CommitFlow** [P-abs 本轮新核验]:semantic commitments = 阶段必须 establish
**or maintain** 的物理条件;SCM 对照状态证据,不满足则 hold back 依赖动作;
局部纠错 + 最小修正强度。收缩执行:**"维持条件的运行时监控与 hold back
语义"不得列为 PAEG 创新**(SCM 先例);PAEG 的 Runtime HOLD 语义与其部分
同构。差异:CommitFlow 是**监控-纠错闭环实现**(§36 禁的实现类),无证据
分级、无持续性、无演化侧;PAEG 只做资格判定语义且不实现纠错器。

---

## 6. 组件×工作撞车矩阵(总表)

PAEG 拟议组件(收缩后编号)× 九工作。●=已占据 ◐=部分重叠 ○=空白。

| 组件 | Zetta | EmbodiSkill | CheckVLA | RegenHarness | SHAPER | SkillOpt | SafeManip | VASO | CommitFlow |
|---|---|---|---|---|---|---|---|---|---|
| **C2-a** 持续性四分类 E/A/P/U(+DETERMINING 过程状态;v0.2.1 回归 Stage R 冻结口径) | ◐(unresolved group≈U 定性版,v0.2) | ◐(二分) | ○ | ○ | ○ | ◐(lapse 保护区) | ○ | ○ | ○ |
| **C2-b** 有限重复证据量/abstain 的统计学判据 | ○(源码自证 confidence 非证据 [S-ext]) | ○ | ○ | ○ | ○ | ○ | ○ | ◐(论及 trace 证据不足) | ○ |
| **C2-c** 重建保真定量降级(ρ* 阈值+降档规则) | ◐(inconclusive 保留,定性;v0.2) | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| **C2-d** repairability 解耦 | ○ | ○ | ○ | ◐(bounded recovery 预算) | ○ | ○ | ○ | ○ | ○ |
| **C1'** 分层授权语义(代价对齐+abstain) | ◐(工程双环+inconclusive gate+exact McNemar 配对门,v0.2.1) | ○ | ◐(单门校准) | ◐(commit 骨架) | ○ | ◐(晋升门) | ○ | ◐(形式门) | ◐(hold back) |
| **C3'** 物理时间有效性语义 | ○ | ○ | ○(keyframe 非授权) | ◐(版本化) | ○ | ○ | ◐(LTLf 时序) | ◐(时序规约) | ◐(maintain 条件) |
| ~~已弃用~~ "校准决策门槛" | ○ | ○ | **●** | ○ | ○ | ○ | ○ | ○ | ○ |
| ~~已弃用~~ "commit gate/版本化" | ◐ | ○ | ○ | **●** | ○ | ◐ | ○ | ○ | ○ |
| ~~已弃用~~ "双时间尺度门" | **●** | ○ | ○ | ◐ | ○ | ○ | ○ | ○ | ○ |
| ~~已弃用~~ "defect/lapse 思想" | ○ | **●** | ○ | ○ | ○ | **●** | ○ | ○ | ○ |
| ~~已弃 v0.2~~ "允许 abstain/unresolved 的克制立场" | **●**(unresolved/inconclusive 终态与门) | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| ~~已弃 v0.2~~ "不完整重放不作对照" | **●**(shadow replay inconclusive 保留) | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |

读法(v0.2):C2 行全 ○/◐ 且无 ●——收缩后的创新核仍成立,但 v0.2 后 C2-a/
C2-c 的 Zetta 列从 ○ 升为 ◐(克制立场与定性降级已被占),**核心资产进一步
集中到 C2-b(abstain 的统计学判据:证据量函数、异质性后验、连败信息价值)
与 C2-d**;C1'/C3' 每行均有 ◐——只能以"收缩后形态"主张(见 §7)。

---

## 7. 收缩后的最终创新声明(v0.2.1 重构版,均待概念评审,非实测)

**N1(核心)= Reliability-Aware Persistence Evidence Qualification
(C2,v0.2.1 重构:可靠性感知的持续性证据资格)**

> **研究对象**:在有限重复执行、条件异质性、状态重建不确定性并存的物理
> 执行栈上,明确**什么证据足以支持**①"已测动作分布内的失败风险"判断、
> ②弃权(abstain)、③哪类决策可以消费该证据。观测的预测可信度、因果
> 归因、修改后可修复性是**三个独立命题**(层间白名单,§7.5)。
>
> **与经典统计方法的关系(v0.2.1 显式化,不得回避)**:本框架用到的
> 统计工具全部是已有的——
> - 序贯停止/决策(Operations Research 19 类序贯检验传统,
>   pubsonline.informs.org/doi/10.1287/opre.19.4.970,1971);
> - 异质 Beta-Binomial / 可交换混合的后验与预测(pmc.ncbi.nlm.nih.gov/
>   articles/PMC10962580);
> - 稳健可靠性 / 先验集(arxiv.org/abs/1602.01650)。
> **N1 不宣称"首次提出 Beta-Binomial 建模"、"首次序贯决策"、"首次
> 定义 inconclusive"、"首次双门"、"首次统计检验演化候选"(后者 Zetta
> exact McNemar 已占,§1.3)**。创新声明收窄到**这些工具未曾作为对象的
> 新机制组合**:
>
> 1. **物理状态重建的不确定性作为证据资格的一等输入**(C2-c):离线
>    重放/重采样是 RESTORE-SENSITIVE 动力学上的近似反事实(transition-class
>    一致率 .769<.90 [D]),任何消费重试臂证据的统计结论必须携带重建
>    保真降级(ρ* 阈值 + causal_grade 降档 + APPROXIMATE)——经典可靠性
>    统计假设"同一单元的重复观测可比",物理重放打破该假设,这一断裂
>    是 PAEG 的独立问题;
> 2. **双契约 outcome 证据资格**(ACQ vs STABLE,gap ~35pp [D]):证据
>    资格判定显式绑定"用什么判据判成功",契约选择进入统计对象而非
>    工程细节——经典方法不处理"成功谓词本身有 35pp 摆动"的资格问题;
> 3. **已测动作分布限定**(SAME/POLICY 双臂):所有持续性结论限定在
>    已测动作分布内,跨策略族外推被白名单显式禁止(X1)——把"分布内
>    资格"与"分布外声称"的类型分离作为形式对象;
> 4. **证据量与弃权的可证伪判据**(C2-b,保留自 v0.2):单次失败分辨力
>    不足以授权(INSUFFICIENT_FOR_DECISION——非零信息亦非瞬态)、分流
>    所需最小证据量(槽位 + evidence_mass 序数)、证据边际价值随 n 衰减
>    (C_pol(4)=C_pol(8)×89% [D]);Zetta 源码自证其置信度"ranks
>    hypotheses but is not evidence" [S-ext];
> 5. **层间推导白名单**(关联/持续性/因果/可修复四层,X1-X4 禁则——
>    禁止由重复失败推出 Skill Defect)。
>
> **v0.2 让渡(v0.2.1 全部保留)**:"允许 abstain/unresolved 的设计立场"
> (Zetta unresolved group/inconclusive 终态 [S-ext]);"不完整重放不作
> 对照"(Zetta shadow replay inconclusive 保留 [S-ext]);"执行偶发≠技能
> 缺陷的思想"(EmbodiSkill [S]);**"演化验证的统计检验"**(Zetta exact
> McNemar 配对门,v0.2.1 追加)。
> RPent 实证底物:E/P 完美分离、h(k) 条件化观察值、双臂对照、restore
> 一致率 [D]。**边界**:M0/M1/M2 均为假设层且未检验,κ/n_arm 槽位未定标
> ——N1 是"研究问题 + 概念契约"的规范化,**不是已证明的算法**;其统计
> 实质内容依赖 H0 方向 1 获批后的离线定标(未做,见 R4)。

**N2(支撑)= 决策类型×证据强度的分层授权语义(C1 收缩后,v0.2 表述更新)**

> 同一 append-only 证据面,对不同时间尺度的决策(立即判定 vs 长期更新候选)
> 给出充分性判定,形式化为**代价对齐偏序**(门槛随错误代价非递减,仅在
> "错误后果与证据类型均可比"的决策对上成立;v0.2 取代 v0.1 的全局授权
> 单调性——后者被自身授权矩阵违反;v0.2.1 又删除 A2b"不可逆≥一切可逆"
> 全称,改候选审查/正式部署/不可逆物理动作三档建模,METHOD_SPEC §6.4)+
> abstain 一等公民。不以"存在两个门"、"门槛经过校准"、"允许 inconclusive
> 门"(v0.2,Zetta [S-ext])、"演化验证有统计门"(v0.2.1,Zetta exact
> McNemar)为创新;创新在门族门槛的**代价对齐形式关系**与**共享证据面的
> 两视角读取**(撤销不追溯的运行时/演化不对称)。

**N3(底座)= 物理窗口有效性语义(C3 收缩后,不变)**

> 时效声明的物理失效条件(闭窗终态不可被未来事件否定、不可继承、撤销不
> 追溯)及其与决策授权的耦合。不以 ledger/版本化/时序谓词/维持监控为创新
> (分别为 RegenHarness/SafeManip/CommitFlow 先例);仅作为 N1/N2 的信息
> 底座存在,不单独主张。

---

## 8. 三要素判定(用户指令第 6 点)

### 8.1 明确的研究问题?——**是**

RQ("同一份物理证据,何时可授权何种决策")可操作:METHOD_SPEC 已把它分解为
MQ1-MQ4 且每个子问题有对应形式对象与接口(§0 表)。可证伪性来自:N1 的
分类规则与证据量语义可在既有底物上检验一致性(未来离线工作),N2 的代价
对齐是可违反的不变量(若实证中某高代价决策的门槛低于低代价决策且无结构
理由,公理 A2a 被证伪;v0.2 的局部形式使该检验比 v0.1 的全局命题更精确)。

### 8.2 独立方法创新?——**有条件成立(v0.2 收窄后评估)**

- 成立部分:N1(v0.2 形态:abstain 的统计学判据 + 异质性/选择效应分析)
  在九工作对照中仍无 ● 级撞车,且有 RPent 独有数据底物;Zetta 源码级核验
  [S-ext] 反向加强了 C2-b 的空白判定(对方自证 confidence 非证据);
- 条件部分:N2/N3 均为收缩后形态,单独不可辩;方法整体的新颖性集中在 N1,
  N2/N3 是其决策接口与信息底座——这与提案"以 Persistence-Aware Attribution
  为主线"的定位一致;
- v0.2 收窄的代价:Zetta 占据克制立场后,N1 中"允许弃权"的表述价值归零,
  创新声明完全落在**判据的统计学内容**上——这使 N1 对"判据是否真有独立
  内容"更敏感:M1/M2 分层、κ 定标、白名单推导必须在未来工作中给出可检验
  的实质,否则 N1 退化为对 Zetta 工程出口的重新叙述;
- **v0.2.1 边界(经典统计非创新)**:N1 的统计工具(Beta-Binomial、异质性
  建模、序贯停止、稳健先验)均为已有方法——独立贡献的成立**不依赖**这些
  工具本身,而依赖其应用对象的新机制组合(重建不确定性/双契约资格/分布
  限定/白名单,§7 N1);据此,凡"未做的概率定标"(H0 方向 1 未批)之前,
  N1 一律表述为"研究问题 + 概念契约",**不宣称已完成算法创新**;
- **最脆弱点(更新)**:①RegenHarness 或 VASO 论文全文(仅摘要级)内含
  统计化证据强度语义(R1,保留);②Zetta 论文全文(源码已核、论文未读)
  若把 unresolved 的判据数学化(R5),N1 需再收缩至"重建不确定性 + 双臂
  对照 + 层间白名单";③若"重建保真作为证据资格输入"在可靠性统计文献
  中已有成熟处理(R6),N1 的第 1 项机制需再核。

### 8.3 逻辑自洽的整体架构?——**基本自洽(v0.2+v0.2.1 修复后,两处已知张力)**

接口闭环检查:Outcome State(物理)→ Evidence Claim(观测化)→ Persistence/
Attribution(跨尝试)→ Eligibility(决策)——四层单向数据流 + 审计横向,
每层输入是下层的显式输出(METHOD_SPEC §1 图);三公理在四层各有落点
(A1→L0-L3,A2→代价对齐,A3→U/abstain 判据)。

**v0.2 自洽性修复**(用户指令 1-5 对应的内在错误已全部消除):单次失败
误标 E(§5.0/§5.3)、h(k) 过度解读(§5.5)、PA-Attr 层次混杂(§7.1/§7.5)、
全局单调性自相矛盾(§6.4)、闭窗 claim 被未来事件否定(§4.1/§4.4/§9.2)。
**v0.2.1 修复(独立复审 B1-B4)**:E/A 判据重叠与 DETERMINING 误作事后
标签(§5.3 回归冻结四类)、"M0 已被拒绝"无检验支撑与 runs 充分统计误述
(§5.0/§5.5)、causal_grade 默认 STRONG 与群体 contrast 排除式读法
(§5.2/§7.3)、A2b 不可逆全称(§6.4 三档化)。修复后的规范层无已知内在
矛盾(独立复审判定 REVISE 的四个必修项均已落地,验收见
METHOD_CONSISTENCY_REPORT.md)。

**张力 1(如实,保留)**:temporal aliasing 下 `Held` 类 claim 可能长期滞留
PROVISIONAL/UNKNOWN(METHOD_SPEC §10.4-2)——运行时授权在低频观测栈上
表达力受限。这不是矛盾(克制是特性),但意味着 C3' 的运行时半边在当前
观测粒度上部分空转,价值集中于演化半边。
**张力 2(如实,保留)**:双门语义与 §36 的边界依赖"规范 vs 实现"区分——
REPORT_FAILURE=ALLOW 输出的是判定资格而非控制指令;若用户未来要求在线
接线,需重新过 §36 审查。该张力是制度性的,不是逻辑缺陷。

### 8.4 综合判定

**方法具备明确研究问题(是)、有条件的独立创新(N1 核心成立,v0.2.1 收敛
为 Reliability-Aware Persistence Evidence Qualification——支持的是研究问题
与概念契约,不是已证明的算法;统计实质内容依赖未做的定标)、修复后自洽的
架构(v0.2 五处 + v0.2.1 四处内在错误已消除,两处外部张力如实登记)。
可以进入用户概念评审;任何实现/实验/定标仍需按 §36 与提案 §7 另行立项
授权。**

---

## 9. 残余风险登记(v0.2 更新)

| # | 风险 | 缓解 |
|---|---|---|
| R1 | RegenHarness/VASO/CheckVLA 全文含摘要未显示的统计证据语义 → N1 进一步收窄 | 若获全文再核;摘要级结论全部标注 [P-abs];收缩条款已预设两级退化路径 |
| R2 | N1 的实证底物窄(P 型 5 事件全 t9、单模型单栈 [D]) | 方法文档已限定 scope=FALSE_GRASP@Pi0.5@libero_spatial 族;外推声明禁令写入 METHOD_SPEC §10.4 |
| R3 | "统计分类规则 vs 学习式 classifier" 的 §36 边界判断存在解释空间 | 规则全部显式预注册、阈值显式槽位、零拟合;在线用途明示需另立授权(METHOD_SPEC §10.1) |
| R4(v0.2) | N1 的统计学判据若未来无实质内容(定标工作未做、M1/M2 检验未执行),创新退化为对 Zetta 工程出口的重述 | H0 方向 1(H-OE2/H-OE3)获批后执行定标;在获得实质内容前,N1 声明保持"待概念评审,非实测"措辞 |
| R5(v0.2) | Zetta 论文全文(未读)含 unresolved 判据的数学化表述 | 源码级结论标注 [S-ext] 并注明论文未读;若获论文再核;发生则 N1 收缩至重建不确定性+双臂+白名单 |
| R6(v0.2.1) | N1 被误读为"首次提出 Beta-Binomial/序贯/异质性算法"(经典方法包装风险);或可靠性统计文献已处理"测量系统不可靠时资格判定" | §7 v0.2.1 已显式标注三条经典文献并声明不宣称首次;机制组合(重建保真/双契约/分布限定/白名单)逐项可单独收缩,任何一项被占即降级该项表述 |

## 附录:本轮核验文献清单

| 工作 | arXiv | 核验等级 | 本轮动作 |
|---|---|---|---|
| Zetta | 2608.16590 | [S]+[P]+[S-ext] | **v0.2:main 分支源码重核**(evolution 模块 unresolved/inconclusive 六项机制,行号级;见 §1.1);**v0.2.1:gating.py exact McNemar 配对门核验**(one_sided_exact_mcnemar@12/evaluate_paired_gate@202/heldout 复合门@320-350);论文全文未读(R5) |
| EmbodiSkill | 2605.10332 | [S]+[P] | 引用 S0 既有结论 |
| SkillOpt | 2605.23904 | [S] | 引用 S0 既有结论 |
| SHAPER | 2608.11350 | [P] | 引用 H0 既有结论 |
| **RegenHarness** | **2609.27612** | **[P-abs]** | **本轮摘要全文核验(2026-09-23 v1)** |
| **CheckVLA** | **2607.26789** | **[P-abs]** | **本轮摘要全文核验(2026-07-29 v1)** |
| **SafeManip** | **2605.12386** | **[P-abs]** | **本轮摘要全文核验(2026-05-12 v1)** |
| **VASO** | **2606.05395** | **[P-abs]** | **本轮摘要全文核验(2026-06-03 v1)** |
| **CommitFlow** | **2609.21908** | **[P-abs]** | **本轮摘要全文核验(2026-09-18 v1)** |
