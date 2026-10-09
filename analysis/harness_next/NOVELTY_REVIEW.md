# NOVELTY_REVIEW — 独创性审计与收缩判定

> 2026-10-09 | 版本 v0.1 | 配套 `METHOD_SPEC.md`(同日)。
> 任务:对照最接近的公开工作(重点 Zetta、EmbodiSkill、CheckVLA、RegenHarness;
> 侧翼 SHAPER、SkillOpt、SafeManip、VASO、CommitFlow),判定 PAEG 各组件的
> 不可替代性;**发现先例即主动收缩创新声明**(用户指令与提案 §4 收缩条款)。
>
> **本轮核验方法与等级**:
> - **[S] 源码级**:Zetta、EmbodiSkill、SkillOpt(S0 期 REFERENCE_CODE_AUDIT 完成,
>   本轮引用其结论);
> - **[P-abs] 摘要级全文**:RegenHarness(arXiv 2609.27612)、CheckVLA(2607.26789)、
>   CommitFlow(2609.21908)、SafeManip(2605.12386)、VASO(2606.05395)——
>   **本轮新增**:五篇 arXiv 摘要页全文逐句核验(此前仅有提案表格级 [P] 描述);
> - **[P] 出版页级**:SHAPER(2608.11350)。
> - 摘要级核验的含义:确认机制存在性与概述,**不等同全文对齐**——凡结论依赖
>   "论文全文中不含 X"的判断,均标注残余风险(§6)。
> - 跨基准数字不可直接比较;所有外部结果按原作者报告表述。

---

## 0. 审计结论(TL;DR)

**提案的三条候选创新,经五篇新核验后:一条核心保持(C2)、两条按预设条款收缩
(C1、C3)。方法整体仍具备可辩护的独立空间,但其表述必须从"提出双门/时效声明"
收窄为"物理执行随机性下的失败持续性证据学 + 决策分层授权语义的统计特化"。**

1. **C2(Persistence-Aware Attribution)= 核心创新,保持**。九个工作无一给出
   "随机物理执行下,有限重复失败证据对持续性与可修复性的统计语义"。
   EmbodiSkill 的 defect/lapse 分流在概念上最近,但判据是 LLM 反思式、无证据量
   概念、无重建保真处理;RegenHarness 有执行记录驱动的演化治理但无统计化
   持续性分析 [P-abs]。
2. **C1(Decision-Dependent Eligibility)= 按条款收缩**。CheckVLA 已做
   conformal 校准的干预风险阈值(单决策类型)[P-abs];RegenHarness 已有
   identity/version-bound commit gate 骨架 [P-abs];Zetta 已有 Loop1/Loop3 双
   时间尺度的工程分离 [S]。**"有两个门"与"校准过的门槛"均非空白**。收缩后
   C1 = "同一证据面对不同决策类型的充分性差异作为形式对象(授权单调性、
   abstain 一等公民、错误代价不对称的定性偏序)"。
3. **C3(Temporal Claims)= 按条款收缩**。版本化事实(RegenHarness)、
   LTLf 时序谓词(SafeManip)、commitment 维持监控(CommitFlow)、进度证据
   保留(CheckVLA keyframe bank)均已有 [P-abs]。收缩后 C3 = "物理窗口失效
   语义(time-to-validity、不可继承、撤销不追溯)与决策授权的耦合",仅作为
   C2 的信息底座,不单独主张。

---

## 1. 重点对照一:Zetta(arXiv 2608.16590)[S-源码级 + P-项目页]

### 1.1 机制摘要

三时间尺度闭环:Loop1 Critic-Governed Action Loop(action 频率,代码化 critic
监控物理状态、偏离触发 recovery);Loop2 Candidate Optimization(失败 rollout
按最早可观测分歧聚类、因果诊断、生成候选 critic/recovery);Loop3
Validation-Gated Skill Update(历史回归 + held-out 泛化门 → 版本化 skill
memory)。LIBERO-Pro 90.8%(+56.3pt)。源码级确认:critic_runtime.py 的运行时
监控、role1_recovery.py 的恢复与配对同 seed 重放 [S]。

### 1.2 与 PAEG 逐组件对照

| PAEG 组件 | Zetta 对应物 | 判定 |
|---|---|---|
| 证据等级 L0-L3 | 无(critic 输出=代码化条件是否触发) | 空白 ✓ |
| Claim 时效/撤销 | 无(critic 是即时判断,无声明账本) | 空白 ✓ |
| E/A/P/U 持续性分类 | Loop2 的失败聚类(启发式,LLM 辅助) | 概念近、机制异 |
| 归因克制/UNKNOWN | 无(聚类必须产出候选) | 空白 ✓ |
| 重建保真降级 | 无(shadow replay 式配对重放直接用作对照) | 空白 ✓ |
| Runtime/Evolution 分层 | Loop1 vs Loop3(工程分离) | **结构先例,让渡** |
| 验证门 | Loop3 held-out 门(工程 k 轮对比) | **先例,让渡** |
| SAME 配对重放 | role1 的 paired same-seed [S] | **技术先例,让渡** |

### 1.3 判定

Zetta 回答"闭环 critic-recovery 演化**是否有效**"(90.8%);PAEG 回答"其依赖的
outcome 证据**何时才可信**"。**必须让渡的声明**:"双时间尺度分离"、"配对同
seed 重放对照技术"、"held-out 晋升门"均不得列为 PAEG 创新。**保持的差异**:
Zetta 的门是工程门槛(k 轮成功率对比),无证据充分性的形式语义、无 abstain、
无证据量定标——PAEG 恰好为其 Loop2/Loop3 提供其缺失的输入质量学。
互补而非竞争,与 H0 审计结论一致。

---

## 2. 重点对照二:EmbodiSkill(arXiv 2605.10332)[S-源码级]

### 2.1 机制摘要

Skill-aware reflection 将失败区分为 Skill Defect(技能本身错,触发技能正文
更新)与 Execution Lapse(执行偶发失手,不触发更新);版本化手册;主要在
ALFWorld/EmbodiedBench。

### 2.2 与 PAEG 对照

| 维度 | EmbodiSkill | PAEG |
|---|---|---|
| 分类对象 | defect vs lapse 二分 | E/A/P/U 四类 + repairability 独立轴 |
| 判据来源 | LLM 轨迹反思 | 预注册统计序列(重复实验证据) |
| 所需证据量 | 未处理(一次反思即分流) | 一等对象(evidence_mass + κ 槽位) |
| 无法归因时 | 必须分到两类之一 | U 类显式 abstain(实证:U 型 4/24 [D]) |
| 随机性处理 | 无(单轨迹语义判断) | 核心(边际率、连败结构 vs iid) |

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
| **C2-a** 持续性四分类 E/A/P/U | ◐ | ◐(二分) | ○ | ○ | ○ | ◐(lapse 保护区) | ○ | ○ | ○ |
| **C2-b** 有限重复证据量语义 | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ◐(论及 trace 证据不足) | ○ |
| **C2-c** 重建保真降级 | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| **C2-d** repairability 解耦 | ○ | ○ | ○ | ◐(bounded recovery 预算) | ○ | ○ | ○ | ○ | ○ |
| **C1'** 分层授权语义(单调性+abstain) | ◐(工程双环) | ○ | ◐(单门校准) | ◐(commit 骨架) | ○ | ◐(晋升门) | ○ | ◐(形式门) | ◐(hold back) |
| **C3'** 物理时间有效性语义 | ○ | ○ | ○(keyframe 非授权) | ◐(版本化) | ○ | ○ | ◐(LTLf 时序) | ◐(时序规约) | ◐(maintain 条件) |
| ~~已弃用~~ "校准决策门槛" | ○ | ○ | **●** | ○ | ○ | ○ | ○ | ○ | ○ |
| ~~已弃用~~ "commit gate/版本化" | ◐ | ○ | ○ | **●** | ○ | ◐ | ○ | ○ | ○ |
| ~~已弃用~~ "双时间尺度门" | **●** | ○ | ○ | ◐ | ○ | ○ | ○ | ○ | ○ |
| ~~已弃用~~ "defect/lapse 思想" | ○ | **●** | ○ | ○ | ○ | **●** | ○ | ○ | ○ |

读法:C2 行全 ○/◐ 且核心四格(C2-a/b/c 对全部)无 ●——收缩后的创新核成立;
C1'/C3' 每行均有 ◐——只能以"收缩后形态"主张(见 §7)。

---

## 7. 收缩后的最终创新声明(三条,均待概念评审,非实测)

**N1(核心)= 随机物理执行下的失败持续性证据学(C2)**

> 在边际成功率随机、单次成败证据力弱的执行栈上,给出"有限重复失败证据 →
> 持续性分类(E/A/P/U)→ 归因声称强度封顶 → 可修复性独立评估"的完整统计
> 语义,含连败时序结构的信息量、双采样臂的动作特异性排除、重建保真不足的
> 因果降级。最近邻(EmbodiSkill 二分/VASO trace 不足论述/RegenHarness 记录
> 驱动 RSI)均不含该语义。RPent 实证底物:E/P 完美分离、h(k) vs iid 偏离、
> 双臂对照、restore 一致率 [D]。

**N2(支撑)= 决策类型×证据强度的分层授权语义(C1 收缩后)**

> 同一 append-only 证据面,对不同时间尺度的决策(立即判定 vs 长期更新候选)
> 给出充分性判定,形式化为授权单调偏序 + abstain 一等公民 + 错误代价不对称的
> 定性处理。不以"存在两个门"或"门槛经过校准"为创新(分别为 Zetta/
> RegenHarness 与 CheckVLA 先例);创新在门族的**形式关系**与**共享证据面的
> 两视角读取**(撤销不追溯的运行时/演化不对称)。

**N3(底座)= 物理窗口有效性语义(C3 收缩后)**

> 时效声明的物理失效条件(time-to-validity、不可继承、撤销不追溯)及其与
> 决策授权的耦合。不以 ledger/版本化/时序谓词/维持监控为创新(分别为
> RegenHarness/SafeManip/CommitFlow 先例);仅作为 N1/N2 的信息底座存在,
> 不单独主张。

---

## 8. 三要素判定(用户指令第 6 点)

### 8.1 明确的研究问题?——**是**

RQ("同一份物理证据,何时可授权何种决策")可操作:METHOD_SPEC 已把它分解为
MQ1-MQ4 且每个子问题有对应形式对象与接口(§0 表)。可证伪性来自:N1 的
分类规则与证据量语义可在既有底物上检验一致性(未来离线工作),N2 的单调性
是可违反的不变量(若实证中 Evolution 门槛低于 Runtime,公理 A2 被证伪)。

### 8.2 独立方法创新?——**有条件成立**

- 成立部分:N1 在九工作对照中无 ● 级撞车,且有 RPent 独有数据底物;
- 条件部分:N2/N3 均为收缩后形态,单独不可辩;方法整体的新颖性集中在 N1,
  N2/N3 是其决策接口与信息底座——这与提案"以 Persistence-Aware Attribution
  为主线"的定位一致,本轮审计支持该定位;
- **最脆弱点**:若 RegenHarness 或 VASO 论文全文(本轮仅摘要级)内含统计化
  证据强度语义(摘要未显示但正文可能有),N1 需进一步收窄至"双采样臂动作
  特异性排除 + 重建保真降级"两个最具体的机制。已登记为残余风险 R1。

### 8.3 逻辑自洽的整体架构?——**基本自洽,两处已知张力**

接口闭环检查:Outcome State(物理)→ Evidence Claim(观测化)→ Persistence/
Attribution(跨尝试)→ Eligibility(决策)——四层单向数据流 + 审计横向,
每层输入是下层的显式输出(METHOD_SPEC §1 图);三公理在四层各有落点
(A1→L0-L3,A2→单调性,A3→U/abstain)。

**张力 1(如实)**:temporal aliasing 下 `Held` 类 claim 可能长期滞留
PROVISIONAL/UNKNOWN(METHOD_SPEC §10.4-2)——运行时授权在低频观测栈上
表达力受限。这不是矛盾(克制是特性),但意味着 C3' 的运行时半边在当前
观测粒度上部分空转,价值集中于演化半边。
**张力 2(如实)**:双门语义与 §36 的边界依赖"规范 vs 实现"区分——
REPORT_FAILURE=ALLOW 输出的是判定资格而非控制指令;若用户未来要求在线
接线,需重新过 §36 审查。该张力是制度性的,不是逻辑缺陷。

### 8.4 综合判定

**方法具备明确研究问题(是)、有条件的独立创新(N1 核心成立)、基本自洽的
架构(两处张力已如实登记)。可以进入用户概念评审;任何实现/实验/定标仍需
按 §36 与提案 §7 另行立项授权。**

---

## 9. 残余风险登记

| # | 风险 | 缓解 |
|---|---|---|
| R1 | RegenHarness/VASO/CheckVLA 全文含摘要未显示的统计证据语义 → N1 进一步收窄 | 若获全文再核;摘要级结论全部标注 [P-abs];收缩条款已预设两级退化路径 |
| R2 | N1 的实证底物窄(P 型 5 事件全 t9、单模型单栈 [D]) | 方法文档已限定 scope=FALSE_GRASP@Pi0.5@libero_spatial 族;外推声明禁令写入 METHOD_SPEC §10.4 |
| R3 | "统计分类规则 vs 学习式 classifier" 的 §36 边界判断存在解释空间 | 规则全部显式预注册、阈值显式槽位、零拟合;在线用途明示需另立授权(METHOD_SPEC §10.1) |

## 附录:本轮核验文献清单

| 工作 | arXiv | 核验等级 | 本轮动作 |
|---|---|---|---|
| Zetta | 2608.16590 | [S]+[P] | 引用 S0/H0 既有结论 |
| EmbodiSkill | 2605.10332 | [S]+[P] | 引用 S0 既有结论 |
| SkillOpt | 2605.23904 | [S] | 引用 S0 既有结论 |
| SHAPER | 2608.11350 | [P] | 引用 H0 既有结论 |
| **RegenHarness** | **2609.27612** | **[P-abs]** | **本轮摘要全文核验(2026-09-23 v1)** |
| **CheckVLA** | **2607.26789** | **[P-abs]** | **本轮摘要全文核验(2026-07-29 v1)** |
| **SafeManip** | **2605.12386** | **[P-abs]** | **本轮摘要全文核验(2026-05-12 v1)** |
| **VASO** | **2606.05395** | **[P-abs]** | **本轮摘要全文核验(2026-06-03 v1)** |
| **CommitFlow** | **2609.21908** | **[P-abs]** | **本轮摘要全文核验(2026-09-18 v1)** |
