# Persistence-Aware Evidence Governance — 方法规范(METHOD_SPEC)

> 2026-10-09 | 版本 **v0.2.1**(Method Consistency Finalization 轮)/ 未实现、未测试、未定标。
> v0.1 见 git `adf5d18`;v0.2 见 git `cc7e0d3`(修订记录:§0.1 与
> `METHOD_V02_REVIEW.md`);v0.2.1 按 `V02_INDEPENDENT_REVIEW.md`(commit
> `431ddda`)的 B1-B4 与附加边界做最小修订,逐项映射见 §0.2 与
> `METHOD_CONSISTENCY_REPORT.md`。
> 本文件将 `RESEARCH_PROPOSAL.md` / `ARCHITECTURE_PROPOSAL.md` 的概念架构收敛为
> 形式化方法:四个核心对象的形式定义、Persistence-Aware Attribution 算法机制、
> 双门协同语义、三个代表性场景的机制推演。
>
> **边界声明(全程有效)**:
> - 只做研究论证与方法设计。**不含实验设计、指标定义、消融方案、样本量计算**。
> - 不修改任何运行代码,不执行 S1-DEV0,不训练模型。**Stage R §36 Hard STOP 保持生效**。
> - 文中所有阈值常数(κ、τ、θ、ρ* 等)均为**语义槽位**,标注"待定标":其数值确定
>   属未来离线校准工作(H0 审计方向 1 的范畴),须另行预注册与批准,本文不预设任何数值。
> - 文中引用的 Stage Q/R 数字全部是**既有观测的引用 [D]**(出典见文末表),不是本文
>   设计的新测量。
> - 证据等级惯例:**[S]** 本仓源码级 / **[D]** 本仓实验数据级 / **[P]** 外部论文摘要级 /
>   **[S-ext]** 外部仓库源码级(Zetta,2026-10-09 v0.2 核验)。
>   外部对照的深核结论在同目录 `NOVELTY_REVIEW.md`。

## 0.1 v0.1 → v0.2 变更日志(方法论阻断修复)

| # | v0.1 缺陷 | v0.2 修复 | 位置 |
|---|---|---|---|
| 1 | 单次失败被归为 E 类("保守方向"),把"无证据"误当"瞬态"证据 | **事后标签与在线持续性判断分离**;类集增加 DETERMINING(证据积累中,默认态);E 需"序列内出现过成功" | §5.0, §5.3, §9.1 |
| 2 | h(k) 偏离 iid 被表述为"连败史携带超出独立抽样的信息",混淆同质/异质 iid | 引入**三层解释框架**(同质 iid / 异质 iid 选择效应 / 非可交换),明确连败记录何时提供额外信息 | §5.5 |
| 3 | PA-Attr 的 failure_class 与 causal_grade 输出层中,统计关联/持续性/因果/可修复四层边界不清;P 类隐含向 Skill Defect 滑动 | 输出显式四字段;P 语义收窄为"已测动作分布下的持续性",**显式禁止 P→Skill Defect / P→可修复 推导** | §7.1, §7.2, §7.5 |
| 4 | 公理 A2 全局单调性("Evolution 门≥一切 Runtime 门")与自身授权矩阵矛盾(ARCHIVE 零门槛 < REPORT_FAILURE 高门槛) | 替换为**局部代价对齐公理 + 不可逆性约束**;授权矩阵补错误代价轴 | §0, §6.4, §8.2 |
| 5 | claim 状态机允许未来事件改写已闭窗历史(CONTRADICTED 破坏"曾经确认"的终态) | 区分**闭窗(回看性)/开窗(前瞻性)** claim;闭窗终态不可被未来事件否定;只有前瞻授权可失效 | §4.1, §4.3, §4.4, §9.2 |
| 6 | NOVELTY_REVIEW 称 Zetta"聚类必须产出候选、无归因克制"——与源码不符 | Zetta 源码级更正:unresolved group / inconclusive 诊断终态 / inconclusive gate / "confidence 非证据"注释;N1 相应收窄(见 NOVELTY_REVIEW v0.2) | NOVELTY_REVIEW.md §1, §7 |

## 0.2 v0.2 → v0.2.1 变更日志(Method Consistency Finalization)

按 `V02_INDEPENDENT_REVIEW.md`(独立复审,commit `431ddda`)的 B1-B4 与
附加边界做**最小修订**;Stage R 冻结结论(E14/A1/P5/U4)原口径保留:

| # | 复审问题 | v0.2.1 修复 | 位置 |
|---|---|---|---|
| B1 | E 与 A 判据重叠(v0.2 的 E=∃成功 可由 A 推出);κ_E 尝试数与成功数混用;DETERMINING 被当成第五个事后标签 | **事后标签回归 Stage R 冻结四类**(E/A/P/U 完整定义,互斥,适用于 8+8 完整双臂,含判定顺序);DETERMINING 重定位为**过程状态**(证据未观测齐全),非事后标签;撤销 v0.2 对 U4 重分类的暗示;κ 槽位语义改为"成功次数"与"臂覆盖数"两个独立量 | §5.3 |
| B2 | "M0 被拒绝是确证事实"无正式检验;单次失败被写成"零信息";runs 被称为 M1 充分统计载体(应为 (n_s,n_f));队列选择条件未声明 | M0/M1/M2 全部改标**假设层**;观察迹象与已检验事实分离;在线档 NO_INFORMATION 改名 **INSUFFICIENT_FOR_DECISION**(决策资格等级,非信息量声明;单次失败贝叶斯下修非零信息);runs 语义修正((n_s,n_f) 才是 M1 充分统计,顺序信息只在 M2 有增量);新增队列选择条件与外推域声明 | §5.0, §5.5 |
| B3 | causal_grade 默认 STRONG(未用重放≠因果强);群体 contrast≈0 被写成"排除动作特异性"(群体平均可掩盖事件级,有限次数不确定性大) | causal_grade 默认 **UNIDENTIFIED**;三轴分离(reconstruction_fidelity / execution_stochasticity / causal_identifiability);SAME/POLICY 差收缩为"已测条件下动作分布关联",事件级不能排除(r129 反例:SAME 0/8 而 POLICY 5/8 [D]) | §5.2, §7.3, §7.5 |
| B4 | A2b"一切不可逆≥一切可逆"仍是全称排序(PROPOSE_REVIEW 实际可撤销;CONTINUE 可引发不可逆物理后果) | **删除 A2b 全称命题**;A2a 收缩为"错误后果与证据类型可明确排序的决策对上的局部约束";决策分三档分别建模(候选审查 / 正式部署 / 不可逆物理动作) | §6.4, §8.2 |
| 边1 | 在线 episode 通常没有离线 8+8 重复/反事实样本 | 新增**证据可得性分层**:observed_execution_prefix / offline_replay_cohort / cross_episode_history;Runtime 门不得把离线特权标签读作在线输入 | §5.6 |
| 边2 | 闭窗 CONFIRMED 后"任何未来事件不修改"未区分晚到的窗口内证据 | 区分**物理事件时间**与**证据到达时间**:晚到但时间戳在窗内的证据可生成 superseding 版本(append-only),t3 事件仍不能改变 t1-t2 事实 | §4.3 |
| 边3 | retry 零 headroom ≠ skill 编辑零 headroom;ABSTAIN 可能锁死 P 型 | NO_LOCAL_HEADROOM_OBSERVED 改名 **NO_HEADROOM_IN_TESTED_RETRY_ACTIONS**,ABSTAIN 显式限定只对已测重试动作类候选生效 | §5.4, §6.3 |
| 边5 | L2"两通道一致"未核对条件依赖 | 登记为证据可信性风险(同源派生通道不独立) | §4.2, §10.4 |

(Zetta exact McNemar 更正与 N1 重新判断在 NOVELTY_REVIEW v0.2.1。)

---

## 0. 方法定位:从 RQ 到方法约束

**研究问题(RESEARCH_PROPOSAL §1)**:

> Under stochastic physical execution and imperfect observations, what evidence is
> sufficient to authorize an embodied harness's immediate runtime judgment versus a
> durable skill/harness update?
> (同一份物理证据,什么时候可以被用于哪一种决策?)

本方法(PAEG, Persistence-Aware Evidence Governance)把它分解为四个方法子问题,
每个子问题对应一个形式对象:

| 子问题 | 形式对象 | 本文章节 |
|---|---|---|
| MQ1:物理执行的结果状态如何被时间索引地表达,而不退化为 episode 级单点标签? | **Outcome State**(§3) | 物理侧本体 |
| MQ2:不完美观测对结果状态的支持如何被表达为有时效、可撤销、分等级的声明? | **Evidence Claim**(§4) | 认知侧声明 |
| MQ3:随机执行下,失败重复性的有限证据支持何种归因声称,何时必须克制? | **Failure Persistence + PA-Attr 算法**(§5,§7) | 跨尝试统计 |
| MQ4:什么强度的证据允许授权哪一层级的决策(立即行动 vs 长期更新候选)? | **Decision Eligibility 双门**(§6,§8) | 决策接口 |

**三条设计公理**(贯穿全部形式化,后续每个定义都可追溯到其中):

- **A1(证据分层)**:证据不是布尔量。工具报告、单通道代理、多通道一致、窗口持续
  是不同等级;等级决定可用性,不可越级使用。
- **A2(代价对齐授权)**:一个决策所需的最低证据强度,随其**错误代价**(而非
  门类标签)非递减——且该偏序**只在"错误后果与证据类型均可明确排序"的
  决策对上成立(局部约束,非全局排序)**;决策按候选审查/正式部署/不可逆
  物理动作三档分别建模,跨档比较须逐对论证,不是形式不变量(形式化见 §6.4)。
  *(v0.2.1 修订:原 v0.1 全局单调性被自身授权矩阵违反(ARCHIVE 零门槛 <
  REPORT_FAILURE 高门槛);v0.2 的 A2b"不可逆 ≥ 一切可逆"仍是过宽全称
  ——PROPOSE_REVIEW 实际可撤销,CONTINUE 可引发不可逆物理后果——v0.2.1
  删除 A2b,改三档建模,详见 §6.4。)*
- **A3(归因克制)**:当证据不足以区分竞争性解释时,输出 UNKNOWN/ABSTAIN 而非
  最相似假设。克制输出是一等公民,不是失败状态。
  *(v0.2 注:该立场的**设计先例**已存在——Zetta 的 unresolved group /
  inconclusive diagnosis 终态 [S-ext],RegenHarness 的 proposal/termination/
  completion 三分 [P]。本方法的独立主张不在"允许克制",而在克制的**统计学
  判据**:证据量/异质性结构/连败信息价值何时足以支撑何种分类与授权,见
  §5.5 与 NOVELTY_REVIEW v0.2。)*

**方法层立场(与 §36 的边界,展开见 §10.1)**:本方法输出的是**资格判定语义**
(某证据状态是否足以支持某类决策),不是在线控制器。把任何门接进执行环、实现
自动止损/自动重试策略,属于 §36 禁区(adaptive retry controller / escalation
policy),须另立授权。本文全部内容为规范层(specification)。

---

## 1. 形式框架总览

```text
            物理侧                        认知侧 / 治理侧
┌─────────────────────────┐
│ 物理轨迹 σ(t)(真值,离线可查) │
│  ▲ 真值判据(仅离线审计)      │
│  │                        │      ┌──────────────────────────┐
│  ▼ 证据判据(在线合法观测)    │      │ [层4] Decision Eligibility │
┌─────────────────────────┐ claim  │   Runtime Gate  Evolution Gate│
│ [层1] ObservationEvent   │──────▶│            ▲               │
│ (visibility 硬隔离)       │       │            │ attribution   │
└─────────────────────────┘       │  ┌─────────┴────────────┐  │
                                  │  │ [层3] AttributionStatement│
┌─────────────────────────┐       │  │   (PA-Attr 算法输出)   │  │
│ [层2] EvidenceClaim      │───────┼─▶│         ▲              │  │
│  五态生命周期 + 时效       │ claims │  ┌──────┴───────────┐  │  │
│  (撤销不追溯/不可继承)     │───────┼─▶│ [层2'] Failure     │  │  │
└─────────────────────────┘       │  │ Persistence(跨尝试) │  │  │
                                  │  └────────────────────┘  │  │
                                  └──────────────────────────┘
```

数据流自下而上单向;唯一允许的"横向"是审计(append-only audit trail)。
防火墙规则:`visibility=offline_evaluation_only` 的事件(逐物体位姿、任意时刻
check_success、BDDL 真值、state_hash)**永远不进入层 2-4 的在线信息面**,
只用于离线科学审计(env_server.py:282-301 防火墙的延续)[S]。

---

## 2. 预备:执行记录结构

形式化建立在以下记录原语上(全部对应 RPent 既有产物,无新采集):

- **episode**:一次任务执行,含任务 id τ、初始状态 s_0、时间轴 [0, T]。
- **attempt(尝试)**:一个 skill 目标的一次执行单元。Stage R 的 SAME/POLICY/NATURAL
  臂即同一 (event, 采样条件) 下的 attempt 序列 a_1..a_n [D]。
- **measurement point(测量点)**:观测可用的时刻。在线测量点 = 技能边界
  (states.json dump 粒度)[S];离线测量点 = 任意时刻(仪器)。
- **observation stream(观测流)**:O(t) = {RGB/depth/wrist 图像, EEF pos/quat,
  gripper_qpos, 工具输出, 自身历史}. 在线合法集(与 H0 §3 清单一一对应)[S]。

**attempt 的结果**记为三元组而非单布尔:

```
outcome(a) = (acquired(a), stable(a), terminated_normally(a))
```

其中 acquired = 窗口内首次取得、stable = 取得后所有测量点保持、terminated =
episode 终止单点。这个三元组化直接来自 Stage Q 双契约的教训:ACQ−STABLE gap
SAME +34.4pp / POLICY +37.5pp [D]——"成功"的单数用法在物理上是错的。

---

## 3. 形式化 I:Outcome State(物理侧本体)

### 3.1 结果谓词族(双轨判据)

对物体 o、任务目标 g、时刻 t(或窗口 W):

| 谓词 | 语义 | 真值判据(离线专属) | 证据判据(在线合法) |
|---|---|---|---|
| `GraspContact(o,t)` | 末端与 o 力闭合接触 | 接触/位姿重叠(sim_measurement) | gripper_qpos 收敛至闭合 + 分割 mask 与爪部重合 |
| `Lifted(o,t)` | o 离开支撑面 | obj z > z_surface | EEF z 上升 + o 的分割质心上移 + 夹爪保持闭合 |
| `Held(o,W)` | 窗口 W 内持续持有 | 位姿始终在爪内 | Lifted 证据在 W 内逐测量点保持(代理序列) |
| `At(o,g,t)` | o 位于目标区域 | 目标谓词真值(BDDL 判分) | 分割质心落入指令描述区域 |
| `TaskSatisfied(τ,t)` | 任务谓词全满足 | check_success(任意时刻,CPS) | episode_terminated(仅单点) |

**设计要点**:

1. **谓词是分时对象**。`Held(o,W)` 的语义随 W 扩大而变强——这正是 STABLE 契约
   (首中后全测量点保持)的抽象 [D]。
2. **双轨判据的分离即防火墙**。方法运行在证据判据上;真值判据只在离线审计中
   评估证据判据的假阳/假阴结构(H0 方向 1 的定标对象)。
3. **证据判据不完备是常态而非异常**:H0 已确认"物体是否还在爪中"在线无直接
   通道 [S],只能靠代理合取。谓词的可满足性因此必须在 claim 层显式携带
   (§4 的 UNKNOWN 态)。

### 3.2 任务级结果自动机(OUTCOME_AUTOMATON)

```text
NOT_BEGUN → IN_PROGRESS:
    ACQUIRING ⇄ ACQUIRED† → HOLDING† → PLACING → PLACED†
                  † 可逆状态(物理上可倒退)
TERMINAL: TASK_COMPLETE | FAILED(kind)
    FAILED 的 kind ∈ FAIL_KIND =
      { GRASP_MISS        抓空:未取得 GraspContact
        SLIP_LOST         滑落:曾 ACQUIRED,持有窗口内失去
        WRONG_OBJECT      错物:取得非目标对象
        PLACEMENT_ERROR   放置偏差:曾 PLACED 但 At 不满足
        PREDICATE_UNMET   终态谓词不满足,机制未解释
        UNEXPLAINED       观测不足以归类
      }
```

**与单点标签的关键差异**:episode 终止单点(在线唯一的成败信号 [S])在这个
自动机里只是 `TERMINAL` 的一个采样;`ACQUIRED → ACQUIRING` 的倒退边
(SLIP_LOST)在单点标签下不可见——而它正是 TRANSIENT_SUCCESS 现象的物理来源
(ACQ−STABLE ~35pp [D])。

### 3.3 决策接口

Outcome State 本身不可直接查询(真值侧);上层只能通过 Evidence Claim(§4)
的投影查询它。这个"只能透过声明看状态"的间接性是方法的核心结构:**物理状态
与认知声明之间永远隔着证据等级**。

---

## 4. 形式化 II:Evidence Claim(认知侧声明)

### 4.1 声明结构

```text
claim c = ⟨ cid,
            pred ∈ P,            §3.1 谓词模板之一
            args,                (o, W, ...) 谓词参数
            window_type,         RETROSPECTIVE(闭窗) | PROSPECTIVE(开窗)
            valid_from, valid_until,     时间窗
            E_sup ⊆ ObservationEvent,   支持事件集(带 provenance)
            level ∈ {L0, L1, L2, L3},   证据等级
            status ∈ {PROVISIONAL, CONFIRMED, CONTRADICTED, EXPIRED, UNKNOWN},
            scope ⊆ DECISION_TYPES      本声明被授权参与的决策类型
          ⟩
```

**闭窗/开窗二分(v0.2 新增,修正时间逻辑)**:

- **RETROSPECTIVE(闭窗,回看性)**:窗口 [t1,t2] 已结束,claim 断言的是
  "该窗口内发生过/持续过某状态"(如 `Held(o,[t1,t2])`、`GraspContact(o,t1)`)。
  其终态由**窗口内**的证据决定,一经确定**不可被未来事件改变**。
- **PROSPECTIVE(开窗,前瞻性)**:claim 断言的是"某状态预期将持续到未来"
  (如 `Maintained(o, t2→)`、持有保持到放置点)。未来反证可以否定它。
- 谓词模板决定 window_type:事件型谓词(`GraspContact`)与定窗谓词(`Held(o,W)`
  的 W 为有限闭区间)生成闭窗 claim;持续型谓词(`Held-until`、任务级保持)
  生成开窗 claim。二者可以同主语共存:**"t1-t2 期间持有过"(闭窗,终态历史事实)
  与"现在还持有"(开窗,可被未来否定)是两个不同的 claim**。

### 4.2 证据等级(单调,不可越级)

| 等级 | 定义 | 例 |
|---|---|---|
| **L0_TOOL_REPORT** | 工具/技能返回值,无独立物理证据 | pick() 的 success flag |
| **L1_SINGLE_PROXY** | 单通道传感器代理满足判据 | gripper_qpos 闭合 |
| **L2_CONCORDANT** | ≥2 独立通道一致 | 夹爪闭合 + 分割质心随 EEF 上移 |
| **L3_SUSTAINED** | 窗口内逐测量点保持的 L2 | Held(o,W) 全窗一致 |

依据:工具 success ≠ 物理成功(ARCHITECTURE_PROPOSAL 机制 1);视觉富、结构贫、
成败单点的观测不对称 [S][D] 使 L2 需要跨通道合取才可达。

**通道独立性风险(v0.2.1,边 5)**:L2 的"≥2 独立通道"须核对**条件
依赖**——同一分割模型派生的特征(EEF 侧质心 vs 爪部 mask)可能共享
误差源,通道数量多不等于独立证据多。等级定义保持"独立"为必要条件;
条件依赖对 L2 可信性的影响登记为证据可信性风险(§10.4 局限 8),通道
误差独立性的逐对审计属 H0 方向 1 范畴,未执行。

### 4.3 五态生命周期与转换规则

```text
                    ┌──────────── 新证据到达(等级≥L1,判据部分满足)
                    ▼
              PROVISIONAL ──── 窗口内 L3 持续 ────▶ CONFIRMED
                 │   │                                │
                 │   └─ 反证事件 ──▶ CONTRADICTED ◀────┘
                 │       闭窗:反证落在窗口内(时间戳 ∈ W)
                 │       开窗:反证发生在 t ≤ now 的持续期内
                 ▼
              EXPIRED ◀──── valid_until 过且无 L3 续期 ──── (所有非 CONTRADICTED 态)
                 ▲
              UNKNOWN ◀──── 判据不可满足:观测缺口 / 时间混叠 / 代理失效
```

完整转换表:

| from | 触发 | to | 语义 |
|---|---|---|---|
| ∅ | 支持事件 ≥L1 到达 | PROVISIONAL | 初步支持,授权受限(scope 受限) |
| PROVISIONAL | 窗口内达到 L3 并保持 | CONFIRMED | 窗口内可作强授权 |
| PROVISIONAL/CONFIRMED | **闭窗**:反证事件(≥L1,时间戳落在该 claim 自己的窗口 W 内) | CONTRADICTED | 当前授权即刻失效;历史记录保留并标 superseded |
| PROVISIONAL/CONFIRMED | **开窗**:持续证据链在 now 之前断裂(如 GRASP_LOST 观测) | CONTRADICTED | 前瞻授权即刻失效;**同主语的既有闭窗 claim 不受影响** |
| PROVISIONAL/CONFIRMED | valid_until 到期且无 L3 续期 | EXPIRED | 不再授权;不构成反证 |
| 任意 | 判据可满足性破坏(缺口/混叠) | UNKNOWN | 一等公民:显式承认"不知道" |
| (终态) | **任何未来事件**(闭窗 claim 已达 CONFIRMED/DISMISSED 类终态后) | **无转换** | **闭窗终态不可被未来事件否定**(v0.2 修正:未来事件只能作用于开窗 claim 或生成新 claim) |

**迟到窗口内证据(v0.2.1 新增,边 2:物理事件时间 ≠ 证据到达时间)**:
上表"未来事件不修改闭窗终态"中的"未来"指**物理事件发生在窗口之后**。
另一类情形是:证据**到达**得晚,但其记录的**物理事件时间戳落在闭窗内**
(低频审计管线晚到的分割结果、离线复核发现的窗口内反证)。此时旧声明
保留(append-only),系统生成 **superseding 版本**修正此前基于不充分
证据的判断——被修正的是"我们对 t1-t2 的认知",不是 t1-t2 的物理事实。
两条边界同时成立:①晚到但窗口内时间戳的证据可以 supersede 旧声明
(证据到达时序在后的修正权);②物理事件时间戳 > t2 的事件(t3 滑落)
**永远不能**改变"t1-t2 期间发生过什么"。

### 4.4 时间语义(本方法对 C3 的落实)

1. **时间局部性**:claim 只授权其窗口内的决策。`CONFIRMED(Held(o,[t1,t2]))`
   对 t3>t2 的决策无授权力。
2. **不可继承**:新窗口需新证据。CONFIRMED 不自动延拓——防"永久持有"谬误
   (物理持有每一秒都可能失效;ACQ−STABLE gap 是其统计表现 [D])。
3. **闭窗终态不可否定**(v0.2 新增):RETROSPECTIVE claim 的终态是
   **历史事实**,不可被未来事件改写。"t1-t2 期间持有过"一旦 CONFIRMED,
   t3 的滑落**不能**把它改成 CONTRADICTED——t3 的滑落属于未来,只能作用于
   开窗 claim(`Maintained(o,t2→)`)。混淆这两者是 v0.1 的时态逻辑错误
   (场景 B 推演曾犯,§9.2 已改)。
4. **撤销不追溯**:CONTRADICTED 撤销的是**未来授权**,不抹除**历史证据价值**——
   曾 CONFIRMED 的事件在 Evolution 层的统计中仍然有效(它是"瞬态成功"的实证
   材料)。这两个方向的不对称是双门协同(§8)的基础。

### 4.5 决策接口(查询原语)

```python
# 上层允许的全部查询(只读)
c.active(t)          # t 时刻有效:status ∈ {PROVISIONAL, CONFIRMED} 且 t ∈ 窗口
c.authorizes(t, d)   # t 时刻对决策类型 d 有授权:d ∈ scope 且等级≥d 的最低要求
c.was_confirmed(W)   # 历史查询(Evolution 层统计用)
c.grade()            # (level, status) 二元组
ledger.active_set(t) # 当前全部 active claims 的快照(只增不删,append-only)
```

---

## 5. 形式化 III:Failure Persistence(跨尝试统计)

### 5.0 两个不同的判断对象(v0.2 新增,修正概念混用)

Failure Persistence 框架里有**两个时间尺度不同、输出类型不同**的判断对象,
v0.1 曾把它们混在同一个四分类里使用,导致"单次失败被标为 E"的概念错误。
v0.2 起显式区分:

| | **事后标签(ex-post label)** | **在线持续性判断(online persistence judgment)** |
|---|---|---|
| 时点 | 事件窗口结束后,基于完整 attempt 序列回看 | 执行中,基于已积累的部分证据 |
| 输入 | PE(e) 的全部 n 次 attempt | PE(e) 的前 k 次(k 在增长中) |
| 输出 | **分类**(四类,§5.3,Stage R 冻结口径) | **证据等级**(三档,序数),不输出类别 |
| 用途 | Evolution 层统计、benchmark 标签 | Runtime 层"下一步证据是否支持失败将持续"的评估 |
| 语义 | "这个事件(在观测完毕后)属于哪一类" | "到目前为止,证据对'失败会持续'的支持有多强" |

**在线判断的三档**(v0.2.1 更名:这是**决策资格等级**,不是信息量声明;
序数,数值边界是定标槽位,同 κ):

```text
INSUFFICIENT_FOR_DECISION   已观测证据不足以支持任何持续性方向的决策授权。
  (n=1 必然落此档。注:单次失败在贝叶斯意义上并非零信息——
   对异质先验 q_e~F,一次失败使后验 p(q_e|y_1=0) 向低端移动;
   该档说的是"移动量不足以支撑决策",不是"零信息"。)
SUPPORTS_PERSISTENCE   连败长度 ≥ κ_info 且后续 attempt 全败:
  失败持续的(异质性后验)支持度上升(§5.5 M1 层)
SUPPORTS_EPHEMERALITY  序列中出现成功:
  失败不持续(下次尝试可能成功)的支持
```

**要点**:在线判断的默认档是 INSUFFICIENT_FOR_DECISION,不是 E。v0.1 把
"单次失败 → failure_class=E(保守方向)"当作保守设计,实则**把证据不足
当成了瞬态证据**——正确的表述是"不足以授权"(决策语义),而非"无信息"
(信息语义):单次失败携带少量方向性信息(后验下修),只是不足以支持
本方法定义的任何决策授权。这与公理 A3 一致:克制是"证据未足时不授权",
不是宣称"证据为零"。

事后标签与在线判断的连接:事后四分类(§5.3,Stage R 冻结口径)是在证据
**积累完成后**的回看类别;在线判断给出的是通往该类别的证据路径上,每一步
的方向与强度。二者使用同一个 PE 对象,但规则不同(§5.3 的规则全部要求
"双臂 8+8 已观测齐全",不适用于中间步)。

### 5.1 重复实验结构与采样条件

对失败事件 e(event = (task, seed, 失败发生上下文)),Stage R 已建立三种采样
条件的 attempt 序列 [D]:

- **SAME**:同动作序列重放(执行随机性的对照)
- **POLICY**:策略重采样(动作选择随机性的对照)
- **NATURAL**:自然重试

结果序列 y_e,c = (y_1..y_n), y_i ∈ {0,1}(per-attempt 的 stable 或 acquired,
契约选择显式记录)。

### 5.2 持续性证据对象

```text
PE(e) = ( n,                        重复次数
          runs(y),                  连败游程序列(时序结构)
          q̂_SAME, q̂_POLICY,        两臂经验率
          contrast = q̂_POLICY − q̂_SAME,   动作特异性对比
          gaps )                    观测缺口记录(§7 R4 输入)
```

**实证锚点 [D]**(既有观测,说明为何 PE 需要这些分量):

- 边际率几乎无臂差(q_same .302 / q_policy .323,配对差 +2.1pp 中位 0)→
  **群体平均层面**未见动作特异性的平均效应。v0.2.1 收缩:这**不能排除
  事件级动作影响**——r129(SAME 0/8 而 POLICY 5/8)是事件级动作关联的
  实例 [D],且 24 事件的有限样本下 contrast 的逐事件不确定性大;
  contrast 的合法读法 = "已测条件下动作分布与失败的平均关联弱",
  不是排除性证据;
- h(k) 低于边际率:连败 3 次后第 4 次成功 1/17、连败 7 次后 0/11,低于
  池化边际 ~.30 → **runs 分量携带失败概率的信息**。v0.2 语义修正:该偏离
  相对的是**同质 iid** 基线;它在"异质 iid"(事件间 q 有分布)下是选择效应的
  必然结果(连败筛出低 q 事件),**不自动构成 attempt 间时序依赖的证据**——
  连败史的信息价值分层解释见 §5.5,这是 v0.1 的过度解读,已改;
- 吸收态存在:P 型事件双臂 16 试零成功(5/5),E 型 14/14 十六试内至少一次
  成功 → PE 分布呈现实证的" ephemeral / absorbing"双峰。

### 5.3 事后四分类的形式判定规则(v0.2.1:回归 Stage R 冻结口径)

**适用对象**:双臂 8+8(SAME/POLICY 各 8 次)已观测齐全的完整 PE(e)。
这是**事后标签**(事件窗口结束后回看);与 §5.0 在线判断是不同对象,
证据未齐时的中间态见本节末段(DETERMINING,过程状态)。

```text
输入:PE(e) 完整双臂:s_SAME, s_POLICY = 各臂成功次数;
                      n_SAME, n_POLICY = 各臂尝试数
阈值槽位(待定标;两个独立量纲,v0.2.1 起不得混用):
  s_E, s_A    每臂最小成功次数(Stage R 实例 = 2)
  n_arm       每臂最小覆盖次数(Stage R 实例 = 8)

判定(互斥;E 先于 A 先于 P,U 为显式补集):
  E (execution-ephemeral):  s_SAME ≥ s_E
                            (Stage R: same ≥ 2/8)
                            [SAME 臂 ≥2 次成功:执行随机性下"失败可翻盘"
                              是已观测事实,不是从缺证推出的默认]
  A (action-specific):      s_SAME = 0 ∧ s_POLICY ≥ s_A
                            (Stage R: same = 0 ∧ policy ≥ 2/8)
                            [失败随动作重采样消失 → 已测分布内动作关联]
  P (policy-persistent):    s_SAME = 0 ∧ s_POLICY = 0 ∧ n_SAME, n_POLICY ≥ n_arm
                            (Stage R: 双臂 0/8 + 0/8)
                            [已测动作分布下的持续失败;"候选"= 仍需
                              repairability 独立审查,且语义限于 §7.5]
  U (unresolved):           其余:s_SAME = 1,或 s_SAME = 0 ∧ s_POLICY = 1
                            [恰 1 次成功的证据量边缘带;Stage R 预注册
                              明文"禁据单次成功赋 latent type"]
```

**互斥性与判定顺序(v0.2.1 修复 B1 重叠)**:v0.2 曾定义
E = `n≥κ_min ∧ ∃y_i=1`(任一臂出现过成功)、A = `SAME 全 0 ∧ POLICY 存在 1`
——**由 A 可推出 E**,类不互斥,且 `classify_persistence`(§7.3)无冲突
优先级。v0.2.1 起上表以**臂内成功数**定义,条件两两互斥,判定顺序
E → A → P → U。验收例(逐例可判):
`SAME 0/8 ∧ POLICY 2/8` → **A** 且不属于 E;`SAME 1/8` → **U**,
不得自动 E;`SAME 2/8` → **E**;`SAME 0/8 ∧ POLICY 1/8` → **U**;
双臂 0/8+0/8 → **P**。(v0.1 的错误——"单次失败 → E"——由 E 需
s_SAME≥s_E≥2 从规则层面排除:n=1 全 0 连分类资格都没有。)

**DETERMINING 是过程状态,不是第五个事后标签(v0.2.1 重定位)**:双臂
8+8(或达到 n_arm 覆盖)尚未观测齐全、或 y 序列可信度被观测缺口破坏时,
输出 DETERMINING(§5.0 在线判断档同此),**不进入本表分类**。v0.2 曾把
DETERMINING 列为五分类成员,混淆了"证据未齐"(过程)与"已齐后的类别"
(事后);v0.2.1 起:事后标签集 = {E, A, P, U}(与 stageR_prereg §8 逐字
一致),DETERMINING 只是 evidence state(过程状态),不是 label。

**κ 槽位的量纲分离(v0.2.1)**:v0.2 的 κ_E 语义摇摆于"尝试数 n≥2"与
"成功数 same≥2"之间——Stage R 的 2 是**成功次数**(s_E),且臂覆盖数 8
是另一个独立量(n_arm)。规范层拆为两个槽位族:**s_E/s_A(成功次数)**与
**n_arm(臂覆盖数)**,定标时分别确定,不得以尝试数替代成功数;
κ_info(§5.0 在线档)另属在线判断槽位,与二者亦不混用。

**与 Stage R 冻结标签的关系**:上表即预注册口径,E14/A1/P5/U4 [D]
原样保留,本规范不改判任何事件、不做重分析。v0.2 曾暗示"按 v0.2 语义
Stage R 的 U4 应落在 E-证据不足带、属未来复核对象"——v0.2.1 **撤销该
暗示**:U 的预注册语义(恰 1 次成功的证据量边缘带)自洽完备,任何
重分类须另立批准的分析,本规范不预设其结论。本文引用 U4 [D] 一律按
预注册口径理解。

**方向性设计(保留自 v0.2,归因克制的落实)**:判 E 需要正面证据
(SAME 臂 ≥2 次成功),不因"不触发演化"而放松——**保守的是决策后果,
不是证据标准**;判 P 需要双臂覆盖且全 0,只输出"已测动作分布下的
持续性"(语义收窄见 §7.5),不输出"技能缺陷";U 不触发演化动作,
记录指向"证据量边缘带"(等待更多 attempt 的自然积累)。

### 5.4 与 repairability 的解耦(公理 A3 的最重应用)

```text
repairability ∈ { UNKNOWN,                             默认
                  EVIDENCE_FOR_CANDIDATE_REVIEW,        存在可修复缺口的正面证据
                  NO_HEADROOM_IN_TESTED_RETRY_ACTIONS } 已测重试动作类内零 headroom
                  (v0.2.1 更名;原 NO_LOCAL_HEADROOM_OBSERVED)
```

**P 与 repairability 是两个独立命题**:"失败会持续"≠"改技能能修好"。
Stage P 已证本栈 verifier 无 headroom(O@8−O@1=10pp < 15pp 门)[D]——
这说明把"持续失败"直接翻译成"需要且值得技能更新"在物理上是站不住的推导,
必须显式分离。repairability 回答的是"进一步审查的资格",不是更新成功概率
(ARCHITECTURE_PROPOSAL 契约 3 的原语义保留)。

**v0.2.1 语义限定(边 3:重试 headroom ≠ Skill 可修复性)**:负面档的
证据来源只能是**已测重试动作类**(SAME 重放 / POLICY 重采样 / NATURAL
自然重试)内的零翻盘。"重试无 headroom"与"技能编辑无 headroom"是
**两个命题**——前者测不出后者:改参数/改提示/再训练一类候选修改的
成功可能性不在重试臂的覆盖范围内。因此:

1. 该档触发 ABSTAIN(§6.3)时,弃权范围**显式限定为重试类候选的提名**;
2. 技能编辑类候选的审查通道**保持开放**(其 repairability 状态记
   UNKNOWN,待独立证据);
3. 禁止用该档把 P 型事件锁死为"不可研究":重试臂零 headroom 而编辑类
   未测时,正确输出是"重试类弃权 + 编辑类 UNKNOWN",不是全局弃权——
   P 型恰是候选审查最应评估的对象(§7.5 X2 的方向一致)。

### 5.5 连败记录的信息价值:三层解释框架(v0.2 新增)

**问题**:h(k) 条件成功率随连败长度下降(连败 3 次后 1/17 [D])。这个下降
**证明**了什么?v0.1 的回答("连败史携带超出独立抽样的信息")混淆了两个不同
的零假设。正确的问题是**分层**的。

**M0(同质 iid,零假设)**:全部 attempt 独立同分布,成功概率为常数 p。
任何历史(包括连败史)对下一次尝试**无信息**:h(k) = p 恒定。
**(v0.2.1 修正)**h(k) 观察值低于池化边际是**观察性迹象,不是检验结论**:
正式检验从未执行;且 h(k) 的分母随连败筛选事件(连败 ≥k 的事件-臂池,
如 k=4 时的 17 个事件-臂 [D]),样本单位是 event-arm,不能把 pooled
Bernoulli trials 当独立 N 做检验。M0/M1/M2 在本文全部是**假设层**;
"拒绝/接受"的任何表述须待获批的离线检验(见本节末"如实登记")。

**M1(异质 iid / 可交换性)**:attempt 独立,但成功概率在**事件之间**异质:
事件 e 有自己的 p_e,p_e ~ F(总体分布),各 attempt 在给定 p_e 时独立。
此时连败史通过**选择效应(selection effect)**携带信息:观察到 k 连败后,
后验 E[p_e | k 连败] 向低 p 移动(de Finetti 意义下,可交换序列的连败是
"当前个体 p 偏低"的证据)。**关键性质:这不需要任何 attempt 之间的时序依赖**
——即使在完全可交换的模型里,h(k) 也会随 k 下降,且下降速度由 F 的形状
决定。异质性越强(方法族内 E 型 q 高 / P 型 q≈0 的双峰结构),选择效应
越陡。

**M2(非可交换 / 真·时序依赖)**:attempt 之间存在超出"独立+异质"的顺序
信息(如技能内部状态漂移、磨损、学习)。只有 M2 才对应"连败本身导致后续
更容易失败"的机制。检验方式是**顺序置换(sham)**:把事件内的 trial 序列
打乱重排,若打乱后连败-后续成功关系消失于与原序列不可区分 → 数据在 M1
层即可解释;若 sham 序列系统性不同于原序列 → M2 证据。(H0 审计方向 1 的
H-OE2 正是该检验的预注册化 [S]。)

**框架给出的三个明确结论**:

1. **连败记录何时提供额外信息**:
   - 相对 M0:**只要 F 非退化(存在事件间异质性),连败史就有信息**——
     RPent 底物满足(E 14/14 十六试内翻盘、P 5/5 双臂零成功的双峰 [D] 是
     异质性的极端形态);
   - 相对 M1:**仅当 M2 成立**(sham 检验可分)。这是比"低于 iid 边际"
     强得多的要求,v0.1 把它当成了已证,错。
2. **止损判定的证据基础在 M1 层就成立**:决定"是否继续重试"只需要
   E[p_e | 连败 k] 的后验下降(M1 给出),**不需要**时序依赖(M2)。
   方法的 Runtime 判断(§5.0)与 κ 门因此全部锚定在 M1 语义上;M2 是否
   成立是独立的科学问题(H-OE2),不影响授权语义。
3. **PE 的 runs 分量的正确解释(v0.2.1 修正充分统计表述)**:固定事件
   q_e、条件 iid(M1)下,后验 p(q_e | y_1..y_n) 的充分统计是
   **(n_success, n_failure)** 计数对,不是游程排列——相同计数的两个
   序列互为重排,后验完全相同,**不产生额外信息**。k 连败对"下一次
   尝试"的预测力全部来自它蕴含的计数与选择效应,顺序本身在 M1 层无
   增量。顺序信息的**增量**只可能在 M2(非可交换)层出现;部分序贯
   决策(如"现在止损"消费当前连败长度)会使用顺序量,但"决策消费
   顺序"与"顺序携带超出计数的后验信息"是两回事。runs 仍被 PE 记录
   (决策接口与 M2/sham 检验需要),但 v0.2 称 runs 为"M1 充分统计
   载体"的表述**错误**,予以更正。

**对方法结构的直接影响**:

- h(k) 的经验曲线 [D] 在 M1 框架下的角色 = **F 的混合结构的事后证据**
  (E/P 双峰混合的显示),而非新机制的信号;
- 在线判断 SUPPORTS_PERSISTENCE(§5.0)的语义 = M1 后验意义下的支持,
  表述为"该事件的失败概率后验偏高",不涉及时序因果;
- κ_info / n_arm 的定标对象因此明确:**M1 下的后验阈值**(连败多长后
  E[p_e|k] 足够低,使继续尝试的期望价值低于门槛)——这是 H-OE3
  (E/P 分流最小试数)的统计学内容 [S]。

**队列选择条件(v0.2.1 显式化)**:Stage R 的 24 事件队列以**已观察到
FALSE_GRASP**(原 episode 失败)为入选条件 [D]。因此 h(k)、q̂ 等统计量的
样本是**条件于"该事件曾失败"的选择样本**:① 原初那次失败是**入选
条件**,不是 PE 序列的成员,不得作为重复证据再计入一次;② 外推域 =
同样以"已失败"为条件的未来事件——对任意新 episode 的**无条件**失败率
或持续性,本框架不直接适用(须经选择修正,且该修正未做)。该条件在
v0.2 及之前未显式声明,现补记。

**如实登记(v0.2.1 强化)**:M0 的正式检验、M1 层的参数拟合(F 的形状)
与 sham 对照(M2 检验)在现有数据上**均未执行**;本节只建立解释框架与
措辞纪律,**不宣称 M0 已被拒绝,不预设任何层的检验或拟合结果**。现象
(h(k) 观察值)、统计假设(M0/M1/M2)、是否完成检验(三者当前均为否)
在本文中严格区分。

### 5.6 证据可得性分层(v0.2.1 新增:在线/离线边界)

Stage R 的 SAME/POLICY 8+8 重复与反事实臂,是**离线、在冻结初始状态上
多次重建**才能获得的特权数据;在线普通 episode 只有本次执行已发生的
观测前缀。双门(尤其 Runtime 门)的输入必须按可得性分层,防止把离线
特权标签读作在线输入:

| 层 | 内容 | 在线可得? | 合法消费者 |
|---|---|---|---|
| **observed_execution_prefix** | 本 episode 已发生的观测流 O(t) 与 claim 账本 | ✅ | Runtime 门(§6.2)的唯一合法输入 |
| **offline_replay_cohort** | 同事件的 SAME/POLICY 重放/重采样臂(Stage R 8+8)、任意时刻 check_success、逐物体位姿 | ❌(离线特权) | 仅 Evolution 层离线统计(§6.3)与离线审计 |
| **cross_episode_history** | 跨 episode 的历史 claim/PE 聚合(不含本事件的离线臂) | ✅(账本投影) | Evolution 门;Runtime 只读 |

规则:

1. **Runtime 门只读 observed_execution_prefix**(加上 cross_episode_
   history 中已入账本的历史 claim 的只读投影);"本次失败是否会持续"
   的在线判断(§5.0 三档)只能用前缀内证据。
2. **offline_replay_cohort 是 Evolution 层的离线特权**:§5.3 事后四分类
   以它为输入——因此**事后标签结构上不可能在线产出**;在线最多到达
   INSUFFICIENT_FOR_DECISION / SUPPORTS_* 档。这从数据可得性层面再次
   落实 §5.0 的两对象分离(在线判断不输出类别)。
3. **与 Simulator Firewall 的衔接(§1/§10.2)**:offline 层内部再分
   "可入 Evolution 统计的重复臂数据"与"仅审计用真值(visibility=
   offline_evaluation_only:位姿、BDDL 真值、state_hash)"——后者连
   Evolution 门也不得消费。防火墙在每一层内部持续有效。

---

## 6. 形式化 IV:Decision Eligibility(双门)

### 6.1 决策类型清单

```text
D_RUNTIME  = { CONTINUE,            继续当前执行
               HOLD_AND_OBSERVE,    暂停并收集证据
               REPORT_COMPLETION,   上报任务完成
               REPORT_FAILURE }     上报失败(止损的信息前提)
D_EVOLUTION = { ARCHIVE,            归档证据(默认,零授权门槛)
                QUARANTINE,         隔离标记(可疑但不审查)
                PROPOSE_REVIEW,     提名进入候选审查
                ABSTAIN }           显式弃权
```

注意清单里**没有** RETRY_NOW / ESCALATE / 自动恢复类决策——它们属于控制器
实现,是 §36 禁区;本方法的 Runtime 门输出的是"证据是否足以支持某判定"的
**资格**,不是动作指令(§10.1 详述)。

### 6.2 Runtime Gate(立即行动的资格)

```python
RUNTIME_GATE(t, d, ledger):
    # 输入:当前时刻、决策类型、活动声明集
    # 规则示例(完整规则以授权矩阵 §8.2 为准):
    if d == REPORT_COMPLETION:
        return ALLOW iff ∃c: c.pred == TaskSatisfied ∧ c.active(t) ∧ c.level ≥ L2
        # L0 工具报告永远不够上报完成(公理 A1)
    if d == REPORT_FAILURE:
        需要 failure claim 处于 CONTRADICTED/UNEXPIRED 且失败种类可判
    if d == HOLD_AND_OBSERVE:
        触发 = 活动声明降级(CONTRADICTED/EXPIRED)或等级跌落(L2→L1)
    if d == CONTINUE:
        默认 ALLOW(无反证即放行;克制公理的方向选择)
    输出: ALLOW | HOLD | DENY | UNRESOLVED (+ reason + 引用 claim ids)
```

**语义要点**:HOLD/UNRESOLVED 是**有效输出**,不是异常。Runtime 层的克制
方向选"多观察一步"而非"臆断失败"——因为 Runtime 错误代价不对称(漏检滑落
→ 任务失败;多观察一步 → 时间成本),且该不对称在此只作为**定性排序**使用,
数值化需要校准(§10.3)。

### 6.3 Evolution Gate(长期更新候选的资格)

```python
EVOLUTION_GATE(e, PE, attribution, ledger):
    # 输入:事件、持续性证据、归因声明、历史声明账本
    if attribution.failure_class ∉ {P, A}:        # 证据未齐(DETERMINING)/E/U 类
        return ARCHIVE(仅归档)                     # 单次/积累中/瞬态/边缘带
                                                   # 失败永不触发演化
    if attribution.evidence_mass < θ_EVO:          # 证据量槽位(待定标)
        return QUARANTINE                          # 证据不足,隔离待积累
    if attribution.repairability == NO_HEADROOM_IN_TESTED_RETRY_ACTIONS:
        return ABSTAIN(仅对重试类候选) + 记录      # 已测重试动作内零 headroom;
                                                   # 不锁死技能编辑类候选(§5.4)
    if attribution.causal_grade == DESCRIPTIVE:    # 重建保真降级到底(§7.2 R3)
        return QUARANTINE                          # 只能描述,不能提名
    return PROPOSE_REVIEW                          # 最高输出:提名候选审查
```

**PROPOSE_REVIEW 是本方法的最高授权**(v0.2.1 注:它只**提名**候选、无
自动晋升,且可撤销——审查可中止、提名可撤回;正式部署 PROMOTE-DEPLOY
属 §6.4 三档中的第二档,不在本方法授权范围内)。技能/配置的实际修改、
验证、晋升、回滚属于 Zetta Loop3 / SkillOpt / RegenHarness 已建立的工程
治理环 [S][P],本方法不重造,只负责给它们提供一个**证据面合格的输入**。

### 6.4 授权门槛的代价对齐(公理 A2 的形式化,v0.2.1 重写)

定义证据强度偏序(不变):

```text
strength(claim) = (level, status) 上的字典序:L3 > L2 > L1 > L0;
                                   CONFIRMED > PROVISIONAL > (EXPIRED, CONTRADICTED, UNKNOWN)
strength(attribution) = (causal_grade, evidence_mass) 上的积序
```

**v0.1 命题及其反例(为何废弃)**。v0.1 断言全局单调性:

```
∀ d_R ∈ D_RUNTIME, d_E ∈ D_EVOLUTION: MinStrength(d_E) ≥ MinStrength(d_R)
```

它被本方法**自己的授权矩阵(§8.2)违反**:Evolution 决策 ARCHIVE 的门槛是零
(归档是默认记录动作),而 Runtime 决策 REPORT_FAILURE 的门槛是高的(连败
结构 + 双臂零成功)。零门槛的 Evolution 决策低于高门槛的 Runtime 决策,
全称命题为假。错误的根源是把"门类"(Runtime/Evolution)当成了门槛的决定
因素,而真正的决定因素是**错误代价**——恰好一个门的**最高**输出
(PROPOSE_REVIEW)代价大,不等于该门的**每个**输出代价都大。

**v0.2.1 替换:一条局部公理 + 决策三档建模**(B4:删除 A2b 全称命题)。

**A2a(局部代价对齐,v0.2.1 收缩)**:仅当两个决策的**错误后果**与
**可消费的证据类型**都能被明确排序时,才对这一决策对给出形式约束:

```text
(错误后果可比 ∧ 证据类型可比)的决策对 (d, d'):
  cost(d) ≤ cost(d')  ⟹  MinStrength(d) ≤ MinStrength(d')
```

即:代价更高的决策,证据门槛不低于代价更低的决策——**该偏序只在上述
可比对上成立,不是全局排序**。可比对举例:

- REPORT_COMPLETION(假阳 → 上报未完成任务,episode 级、可被外验纠正;
  消费 claim 等级)vs PROPOSE_REVIEW(假阳 → 执行噪声进入候选审查流程;
  消费 attribution 四层)——后果与证据类型均可比 ⟹ 前者门槛 ≤ 后者;
- ARCHIVE(假阳 → 多归档一条记录,近零代价)是代价下界 ⟹ 门槛为零
  合法,不违反任何单调性——v0.1 命题的错误在反例中显形。

**决策三档(v0.2.1,取代 A2b)**:v0.2 的 A2b("一切不可逆决策门槛 ≥
一切可逆决策")仍是过宽全称——PROPOSE_REVIEW 只提名候选、无自动晋升,
**可撤销**(审查可中止、提名可撤回);CONTINUE 看似"可逆",其错误却
可能引发**不可逆物理后果**(碰撞、损坏、物体掉落不可恢复位)。不可逆性
不是决策的二元属性,而是随其物理后果分布的性质。改为按三档分别建模:

| 档 | 决策 | 代价性质 | 证据门槛依据 |
|---|---|---|---|
| 候选审查 | PROPOSE_REVIEW / QUARANTINE / ARCHIVE | 审查流程成本,可撤销 | A2a 可对症内的局部偏序(§8.2) |
| 正式部署 | PROMOTE-DEPLOY(技能写入生效) | 跨 episode 难逆、错误先验污染 | **超出本方法授权**:本方法最高输出是提名;部署/晋升/回滚属 Zetta Loop3 等工程治理环 [P][S-ext],其门槛由该环自理 |
| 不可逆物理动作 | CONTINUE 等运行时决策的**物理后果** | 物理损害,不可撤销 | **与候选审查成本不同类,不进同一序**:物理损害风险单独建模(§8.2 代价轴只标方向),数值化属未来校准(§10.3) |

**物理损害风险与候选审查成本分开建模**(B4 要求):前者是物理世界的
不可逆性,后者是信息流程的机会成本——把两者压进单一 L0-L3 序数正是
v0.1 全局单调性与 v0.2 A2b 的共同错误根源。规范层只承诺:① A2a 的
局部偏序;② 三档各自的门槛**依据**显式声明;③ 任何**跨档**比较
(如"部署门槛高于止损门槛")是具体分析结论而非形式不变量,须逐对
论证并登记。

**与授权矩阵的一致性**:§8.2 矩阵逐行补错误代价轴;矩阵内可检验的
只有 A2a 可对症(旁注标出);v0.1 的全称命题与 v0.2 的 A2b 均从规范中
删除。

---

## 7. 核心算法:Persistence-Aware Attribution(PA-Attr)

### 7.1 输入输出规格

```text
输入:
  e            失败事件(含上下文)
  {a_i}        attempt 序列(含每 attempt 的 claim 账本)
  meta         元数据:重建一致性 ρ(restore transition-class 一致率类)、
               观测缺口、契约选择(ACQ/STABLE)、采样条件
输出 AttributionStatement(v0.2 四层显式化):
  ( observed_failure_kind ∈ FAIL_KIND ∪ {UNKNOWN},
    ---- 四层结论,强度语义严格递增,禁止越层推断(§7.5) ----
    L1 association(统计关联,描述性):
        failure_pattern: 模式存在性与强度的描述
          (如"同类失败重复出现 n 次,集中于 chunk_class c")
        failure_class ∈ {E, A, P, U}   §5.3 事后四类(Stage R 冻结口径);
                          DETERMINING 为证据未齐/序列不可信的**过程状态**,
                          非第五个事后标签(§5.3)
        evidence_mass ∈ {INSUFFICIENT, MARGINAL, SUFFICIENT}
    L2 persistence(失败持续性,预测性):
        persistence_call ∈ {PERSISTS_UNDER_TESTED_POLICY_SPACE,
                            DOES_NOT_PERSIST, UNDETERMINED}
        support: M1 后验意义下的支持强度(§5.5;序数,不输出概率数值)
    L3 attribution(因果归因,v0.2.1 改默认档):
        causal_grade ∈ {UNIDENTIFIED, DESCRIPTIVE, MODERATE, STRONG}
            默认 **UNIDENTIFIED**(无有效对照/干预证据时不作任何因果声称);
            提升至 MODERATE/STRONG 只能依赖独立列举的、满足有效性要求的
            干预/对照证据(三轴分离见 §7.3 Layer 4)
        causal_hypothesis ∈ {ENVIRONMENT, POLICY, EXECUTION_NOISE,
                             UNKNOWN}  — 仅作研究假设输出,
        不进入授权(§7.5 X4)
        causal_hypothesis ∈ {ENVIRONMENT, POLICY, EXECUTION_NOISE,
                             UNKNOWN}  — 仅作研究假设输出,
        不进入授权(§7.5 规则 3)
    L4 repairability(可修复性,独立轴,§5.4):
        repairability ∈ {UNKNOWN, EVIDENCE_FOR_CANDIDATE_REVIEW,
                         NO_HEADROOM_IN_TESTED_RETRY_ACTIONS}
    ---- 附加字段 ----
    unknown_clauses: List[缺口描述],     R4 的显式输出
    scope )                                 声明适用范围(任务族/栈/契约)
```

**四层语义(v0.2 的核心澄清)**:

| 层 | 回答的问题 | 证据类型 | 错误用法(禁止) |
|---|---|---|---|
| L1 关联 | "同样的失败重复出现了吗?多少?" | 重复观测的描述统计 | 当作原因 |
| L2 持续性 | "已测条件下,失败会持续吗?" | PE + M1 后验(§5.5) | 外推到未测策略族;当因果 |
| L3 归因 | "为什么失败?" | 反事实/干预/对照证据,受重建保真封顶 | 无反事实证据时的任何非 UNKNOWN 输出 |
| L4 可修复 | "改了会好吗?" | 修复尝试的独立证据 | 由 L2 直接推导 |

v0.1 的单字段 failure_class 把 L1/L2 混在一起(分类既是模式描述又是持续性
预测),causal_grade 又被当作从 L1 直通 L3 的通道。v0.2 起这四层是**独立
输出、独立证据、独立语义**,层间只允许 §7.5 列出的推导。

### 7.2 四种证据情形的处理(用户点名的四情况)

**R1 随机物理失败**(v0.2 拆分为两个子情形,修正 v0.1 的单次失败误标)

- **R1a 序列内出现过成功**(失败后翻盘是已观测事实):
  事实:n ≥ 2 且 ∃ y_i = 1。
  处理:→ failure_class = E(§5.3 新规则:存在量词满足);L2 持续性 =
  DOES_NOT_PERSIST;L3 causal_grade 上限 DESCRIPTIVE;evidence_mass 按 n 定;
  演化层动作 = ARCHIVE。
  依据:E 型 14/14 在 16 试内出现成功 [D]——翻盘可观察、可分类。
- **R1b 单次失败,无序列**(n=1, y_1=0):
  事实:不存在序列,持续性方向的证据尚未积累。
  处理:→ failure_class 槽输出 **DETERMINING**(过程状态:证据未齐,
  §5.3;不是 E——v0.1 错误正在于此:把"无证据"标成"瞬态证据");
  在线判断 = INSUFFICIENT_FOR_DECISION(§5.0:决策资格档,非零信息——
  单次失败使后验下移,只是移动量不足以授权);L2 = UNDETERMINED;
  L3 = causal_grade **UNIDENTIFIED**(默认,无对照/干预证据)+
  causal_hypothesis=UNKNOWN;evidence_mass = INSUFFICIENT;演化层动作 =
  ARCHIVE(与 E 相同的**动作**,但记录的状态不同:DETERMINING 等积累,
  E 已定类)。
  依据:q≈.30 的边际随机性 [D] 使单次失败对持续性两个方向几乎没有
  分辨力(§5.5 M1:一次观测对后验的移动有限);"不足以授权"≠
  "支持瞬态",也≠"零信息"。

**R2 有限重复证据**(2 ≤ n,证据仍不足以分类)

- 事实:双臂覆盖未达 n_arm 或成功数处于边缘带(经验率的置信结构
  覆盖多个假设)。
- 处理:→ failure_class = **DETERMINING**(v0.2:从 U 移入——n 不足不是
  "矛盾"是"未攒够");在线判断按连败长度给 SUPPORTS_PERSISTENCE 或
  INSUFFICIENT_FOR_DECISION(§5.0 三档);双门输出只能 HOLD(运行时)/ QUARANTINE
  (演化),**既不允许 DENY 策略性结论,也不允许提名审查**;输出建议 =
  积累更多 attempt(在未来的自然执行中,不专门采集)。
- 语义:证据量不足时,方法的责任是**拒绝下结论**,不是猜一个。
  (C_pol(4)=.708 已是 C_pol(8) 的 89% [D]——证据的边际价值随 n 衰减,
  n_arm/s 类槽位的定标正是要找这个拐点,属未来校准。)

**R3 状态重建不确定性**(结论依赖 restore/replay 机制)

- 事实:归因推理使用了状态重建(如"同动作重放也失败 → 该事件动作
  关联弱"的对照式推理)。
- 处理:检查重建一致性元数据 ρ;ρ < ρ*(槽位,待定标)时 causal_grade 降一档
  (STRONG→MODERATE→DESCRIPTIVE),全部跨 attempt 聚合声明标注 APPROXIMATE;
  Evolution 门对 APPROXIMATE 声明减权(§6.3 的 QUARANTINE 分支)。
- 依据:restore transition-class 一致率 10/14=.769 < .90 资格门 [D]——
  重放不是精确反事实 oracle;PREFIX 哈希级重建 32/32 [D] 只保证**仪器侧**
  可复现,不保证**执行侧**逐位(≤7.8e-4m 单调漂移)。

**R4 无法归因**(观测缺口 / 终态多义 / 代理失效)

- 事实:FAIL_KIND 判为 UNEXPLAINED,或 y 序列的可信度被 gaps 破坏。
- 处理:→ unknown_clauses 显式列出缺口(类型化:SENSOR_GAP / TEMPORAL_ALIASING /
  PREDICATE_AMBIGUITY / PROXY_FAILURE);failure_class 槽输出
  **DETERMINING**(v0.2.1:序列不可信 = 证据未有效观测的过程状态,
  §5.3 事后四类只对可信且观测齐全的双臂定义——v0.2 在此写 U 与
  预注册 U 语义冲突,已改);causal_grade = UNIDENTIFIED(默认);方法
  **显式 abstain**,不输出最相似假设。
- 语义(v0.2 修订):"允许且尊重分不出来"的**设计立场**不是本方法首创——
  Zetta 已有 unresolved group 与 inconclusive diagnosis 终态 [S-ext]
  (聚类视觉证据不支持共同机制时返回 unresolved 组而非 fallback 合并)。
  本方法的差异在**判据层**:Zetta 的 unresolved 由 LLM 定性判断给出
  (工程出口),本方法为"何时必须 abstain"提供统计学判据(证据量函数、
  §5.5 异质性后验、可证伪的充分性条件)—— abstain 从工程裁量变成
  可定标、可审计的规范对象。(v0.2.1 更正:v0.2 曾以"U 型 4 事件 [D]
  是该情形的实证存在性证明"收尾——按预注册口径 U4 = 恰 1 次成功的
  证据量边缘带,**不是**观测缺口型 abstain 的实例;观测缺口型 abstain
  在 Stage R 队列中无实例(24 事件双臂 8+8 均可信),其存在性来自 H0
  审计的观测面清点 [S],非既有标签。)

### 7.3 算法伪代码

```python
def PA_ATTR(e, attempts, meta):
    # Layer 0 观测事实:从 claim 账本抽取本次失败的种类
    kind = classify_fail_kind(e.contradicted_or_unexpired_claims(), e.gaps)
    #   GRASP_MISS: 无 GraspContact 支持而终态未满足
    #   SLIP_LOST:  曾 CONFIRMED(Held) 后 CONTRADICTED
    #   UNEXPLAINED: 判据不可满足 → R4

    # Layer 1 重复性:构造持续性证据对象(§5.2)
    PE = build_PE(attempts, meta.contract)          # (n, runs, q̂s, contrast, gaps)

    # Layer 2 动作特异性:SAME vs POLICY 对比
    #   contrast 显著 → A 的必要条件;近零 → 仅"群体平均动作关联弱",
    #   不排除事件级动作影响(r129:SAME 0/8 而 POLICY 5/8 [D];§5.2)

    # Layer 3 持续性分类:应用 §5.3 冻结四类规则(槽位 s_E/s_A/n_arm 待定标)
    failure_class = classify_persistence(PE)   # E / A / P / U,互斥,判定
    #   顺序 E→A→P→U;双臂未齐/序列不可信 → DETERMINING(过程状态,非标签)
    #   L1 层输出(统计关联/描述性)

    # Layer 3.5 持续性判断(L2 层,M1 后验语义,§5.0/§5.5)
    persistence_call = judge_persistence(PE)   # PERSISTS_UNDER_TESTED_POLICY_SPACE /
    #   DOES_NOT_PERSIST / UNDETERMINED(序数支持,不输出概率数值)

    # Layer 4 因果层(v0.2.1 重写:三轴分离,默认 UNIDENTIFIED)
    #   轴1 reconstruction_fidelity:ρ ≥ ρ*?(R3 重建一致性)
    #   轴2 execution_stochasticity:执行随机性是否已在 M1 层建模(§5.5)
    #   轴3 causal_identifiability:是否存在满足有效性要求的干预/对照证据
    causal_grade = grade_causation(meta)    # 默认 UNIDENTIFIED;
    #   无轴3 证据(有效对照/干预)时保持 UNIDENTIFIED,与是否用重放无关——
    #   v0.2 的 "not uses_replay → STRONG" 是错误(未用重放 ≠ 因果强:
    #   原生观测再清晰也可能完全不能识别根因),v0.2.1 废弃;
    #   MODERATE/STRONG 只能由独立列举的有效对照/干预证据支撑;
    #   ρ < ρ* 时对已达档位降一档 + APPROXIMATE 标注(R3 封顶机制保留)
    causal_hypothesis = hypothesize(kind, failure_class, PE.contrast, gaps)
    #   ENVIRONMENT/POLICY/EXECUTION_NOISE/UNKNOWN;causal_grade=UNIDENTIFIED
    #   时强制 UNKNOWN;仅研究假设输出,不进授权(§7.5 X4)

    # Layer 5 证据量与缺口(R2 / R4)
    evidence_mass = assess_mass(PE.n, PE.runs)      # INSUFFICIENT/MARGINAL/SUFFICIENT
    unknown_clauses = type_gaps(PE.gaps + e.gaps)   # 类型化缺口列表

    # Layer 6 可修复性(L4 层,独立轴,§5.4)
    repairability = assess_repairability(PE, meta)  # 默认 UNKNOWN

    return AttributionStatement(kind,
                                association=(failure_class, evidence_mass),
                                persistence=persistence_call,
                                attribution=(causal_grade, causal_hypothesis),
                                repairability=repairability,
                                unknown_clauses=unknown_clauses,
                                scope=meta.scope)
```

复杂度与可实现性:全部操作是**声明账本上的符号运算与计数**,无学习组件、
无模型推理、无环境交互——与"纯离线测量学"定位一致,亦不触 §36 的任何
禁令类目(不是 classifier:分类规则是预注册的确定性规则,阈值显式待定标而非
从数据拟合——定标程序另行审批)。

### 7.4 明确不做的事(负面规范)

1. 不从多次失败直接推理"策略错误"或"技能需要修改"(P 只到候选 +
   repairability 审查资格;**Skill Defect 断言在层间推导白名单外,永远
   不可达**,§7.5)。
2. 不把统计类别(failure_class)冒称为未观察到的因果 root cause
   (causal_grade 封顶)。
3. 不输出校准概率(无校准程序前,evidence_quality 只是序数不是基数,§10.3)。
4. 不消费任何 offline_evaluation_only 事件(防火墙)。
5. 不实现重试/止损/恢复控制器(§10.1)。

### 7.5 层间推导白名单(v0.2 新增,PA-Attr 的类型纪律)

四层结论(§7.1)之间的推断**只允许以下规则**;白名单之外的任何层间推导
(尤其是"由重复失败直接推出技能缺陷")是本方法定义下的**类型错误**:

```text
允许的推导:
  (D1) L1 evidence_mass=SUFFICIENT ∧ failure_class=P
         ⟹ L2 PERSISTS_UNDER_TESTED_POLICY_SPACE
       [同为描述/预测层内推进;条件即 §5.3 P 规则]
  (D2) L2 PERSISTS_UNDER_TESTED_POLICY_SPACE ∧ L4 repairability =
         EVIDENCE_FOR_CANDIDATE_REVIEW ∧ L3 causal_grade ≥ MODERATE
         ⟹ Evolution 门 PROPOSE_REVIEW 资格(§6.3)
       [提名审查需要三轴同时支持,任何一轴缺失则止步 QUARANTINE]

禁止的推导(每条都是 v0.1 隐含允许或未显式禁止的):
  (X1) L1/L2 ⟹ "Skill Defect" / "策略缺陷" / "需要重训"
       [统计关联与已测分布下的持续性,均不含"跨策略族缺陷"的语义——
         SAME 臂只重放既有动作,POLICY 臂只覆盖该策略的重采样分布,
         未测策略族的成功可能性永远未被排除。Skill Defect 需要:
         跨策略族持续失败的证据 + 修复成功的反事实,两者都在本方法
         的可观测范围外]
  (X2) L2 ⟹ L4(P 持续 ⟹ "改了会好"或"没救")
       [持续性与可修复性是独立命题(§5.4);Stage P 的 verifier 无
         headroom 结论 [D] 正是"持续失败 ≠ 有修复空间"的实证]
  (X3) L1 ⟹ L3(重复模式 ⟹ 因果)
       [因果声称需要对照/反事实证据,重复本身只给关联;causal_grade
         封顶是结构性约束,不是可积攒突破的阈值。v0.2.1 对齐:伪代码层
         已同步——causal_grade 默认 UNIDENTIFIED、无有效对照/干预时
         causal_hypothesis 强制 UNKNOWN(§7.3 Layer 4),L3 不存在绕过
         白名单的独立出口]
  (X4) L3 causal_hypothesis 进入任何门的授权输入
       [因果假设是研究输出(供人审),不是决策依据;授权只消费
         L1/L2/L4 与 causal_grade(保真度标记)]
```

**P 语义收窄的精确表述(v0.2)**:P 类的全称是 policy-persistent **under
the tested policy space**——SAME(动作重放)与 POLICY(该策略重采样)两臂
覆盖的分布。"持续"是关于该分布的陈述;把 P 读作"该技能在任何策略下都失败"
或"该技能有缺陷"都是超分布外推(归纳跳跃),方法在规范层禁止。
授权矩阵(§8.2)中 P 支持的最高输出 PROPOSE_REVIEW,其语义是"提名进入
**候选审查**"——审查的第一项就是扩大策略族测试以检验 P 的分布外推
有效性,而非接受该外推。

---

## 8. 双门协同的运行语义

### 8.1 同一证据流的两个视角

两个门**共享同一个 append-only claim 账本**,但读取方式不同:

- **Runtime 视角 = 当前窗口投影**:`ledger.active_set(t)`——只看现在有效的声明;
  撤销(CONTRADICTED)立即改变运行时授权。
- **Evolution 视角 = 全历史聚合**:`ledger` 的全部历史 + 跨 attempt 的 PE 与
  attribution——历史 CONFIRMED 的证据价值不因后来撤销而消失(§4.4 撤销不追溯)。

**这是"撤销不追溯"语义存在的理由**:同一次滑落,对 Runtime 是"授权收回"
(不得上报完成),对 Evolution 是"瞬态成功样本入档"(TRANSIENT_SUCCESS 的
实证材料)。两个方向都必须成立,缺一则系统要么过信历史、要么丢掉证据。

### 8.2 证据-决策授权矩阵(方法的核心表)

各决策的错误代价轴(v0.2 新增,供 §6.4 A2a 检验;假阳 = 不该放行时放行):

| 决策 | 假阳代价 | 可逆性 | 影响半径 |
|---|---|---|---|
| CONTINUE | 漏检失败 | 可逆(下一步仍可拦截) | 本 episode |
| REPORT_COMPLETION | 上报未完成任务 | 部分(外验可纠,信用损耗) | 本 episode+调用方 |
| REPORT_FAILURE | 过早放弃可翻盘任务 | 部分 | 本 episode |
| ARCHIVE | 记录噪声 | **完全可逆**(可清理) | 无(纯记录) |
| QUARANTINE | 无实质动作 | 完全可逆 | 无 |
| PROPOSE_REVIEW | 执行噪声进入审查流 | **可撤销**(审查成本;提名可撤回;错误先验污染主要在下游 PROMOTE-DEPLOY 执行时才兑现) | 跨 episode(提名层) |

| 证据状态(行) | CONTINUE | REPORT_COMPLETION | HOLD_OBSERVE | REPORT_FAILURE | ARCHIVE | QUARANTINE | PROPOSE_REVIEW |
|---|---|---|---|---|---|---|---|
| TaskSatisfied L2+ active | ✅ | ✅ | — | ❌ | ✅ | — | — |
| L0-only(仅工具报告) | ✅ | ❌ | 建议 | ❌ | ✅ | — | ❌ |
| 声明降级(CONTRA/EXPIRED) | ❌ | ❌ | ✅(触发) | 视反证 | ✅ | — | — |
| 单次失败(DETERMINING,R1b) | ✅ | ❌ | — | ❌(证据不足) | ✅ | — | ❌ |
| 连败中双臂未齐(DETERMINING/R2) | ✅ | ❌ | 建议 | ❌ | ✅ | ✅ | ❌ |
| 双臂全败(0/8+0/8)+ 修复证据 | ⚠️ | ❌ | — | ✅(资格) | ✅ | — | ✅(最高) |
| 重建保真不足(ρ<ρ*) | ✅ | — | — | ⚠️ | ✅ | ✅(减权) | ❌ |
| 观测缺口(R4) | ✅ | ❌ | ✅(建议) | ❌ | ✅ | ✅ | ❌ |

读法举例:第 6 行——一个证据量足够的 P 型持续失败,**支持**"上报失败"的
判定资格(Runtime 门允许 REPORT_FAILURE),且**支持**提名候选审查
(Evolution 门最高输出),但依然**不允许**任何直接的技能修改(该列不存在)。
第 1 列几乎全 ✅ 不是设计疏忽:CONTINUE 是零授权门槛的默认自由(公理 A3 的
运行时体现——无反证不拦截),方法的约束力全部集中在**高影响授权**上。

**代价对齐检验(v0.2.1,对照 §6.4 A2a——仅可比对,无 A2b)**:矩阵满足
——ARCHIVE/QUARANTINE 零门槛 ↔ 其假阳代价近零;REPORT_COMPLETION 需 L2+
↔ 其假阳是信用损耗;PROPOSE_REVIEW 需双臂+证据量+修复证据+保真度四重
条件 ↔ 其假阳是跨 episode 审查流污染(提名可撤销,但审查成本实质;
下游 PROMOTE-DEPLOY 一旦执行才难逆——该层不在本方法授权内,§6.4 三档)。
**注意该排列不再由"门类"解释**:ARCHIVE(Evolution 门)门槛低于
REPORT_FAILURE(Runtime 门),正是 v0.1 全局单调性命题的反例,也是改为
代价对齐的原因;物理损害类代价与候选审查成本**不进同一序**作形式比较。

### 8.3 门间一致性规则

1. **不矛盾规则**:Evolution DENY 不约束 Runtime(Runtime 可以继续重试一个
   已被判定"演化上无修复空间"的技能——因为运行时重试的代价结构不同);
   反之 Runtime HOLD 不自动产生 Evolution 动作。
2. **升级单向性**:证据状态只能沿"Runtime 可用 → Evolution 可用"单向升级
   (增加证据量/保真度),不允许反向降级 Evolution 判定来"救济"运行时授权
   (防止用统计聚合掩盖当前窗口的反证)。
3. **abstain 传播**:任何层的 UNRESOLVED/UNKNOWN 不被上层静默填充为最相似
   假设;传播路径上每一步保留 abstain 标记。

---

## 9. 三场景机制推演

三个场景分别对应 RPent 实证谱上的 E 型(瞬态)、TRANSIENT_SUCCESS(取得后
失稳)、P 型(吸收态)[D]。推演展示证据流 → claim 状态轨迹 → attribution
输出 → 双门判定的完整链路。**这是机制走查(thought experiment),非实验设计。**

### 9.1 场景 A:偶发抓空(GRASP_MISS,E 型)

**情境**:planner 调用 pick(target);技能返回 success=false;wrist 视觉中
夹爪闭合于空处;物体仍在原位(分割 mask 未移动)。

**Claim 轨迹**:

| 时刻 | 事件 | claim 状态 |
|---|---|---|
| t0 | pick 发起 | — |
| t1 | 工具返回 success=false | `GraspContact` @ L0 PROVISIONAL(弱)|
| t2 | 分割:物体质心未移动 + 夹爪空置视觉 | `GraspContact` → **CONTRADICTED**;`Lifted` 无法进入 PROVISIONAL |

**PA-Attr(v0.2.1 修正)**:kind=GRASP_MISS;n=1(无序列)→ Layer 3 落入
**DETERMINING**(证据积累中,过程状态;v0.1 曾在此处标 E——错误:单次
失败既不支持"瞬态"也不支持"持续",把无证据当瞬态证据违反 §5.0 的
区分);在线判断 = INSUFFICIENT_FOR_DECISION;evidence_mass =
INSUFFICIENT;causal_grade=UNIDENTIFIED(默认,无对照/干预,R1b);
unknown_clauses=[];repairability=UNKNOWN。

**双门判定**:Runtime——CONTINUE=ALLOW(重试自由);REPORT_COMPLETION=DENY;
REPORT_FAILURE=DENY(单次失败不构成失败上报资格)。Evolution——ARCHIVE
(仅归档;与 E 型**动作相同**——都不触发演化,但账本记录 DETERMINING 而非
E,后续若积累出翻盘证据才改判 E、积累出双臂全败才进入 P 路径)。

**实证对照(语义修正)**:E 型事件 14/14 在 16 试内出现成功 [D] 是**事后**
标签的判据——它在事件窗口结束后把"翻盘已发生"归类为 E。它**不能**读作
"单次失败时预测翻盘概率高":单次失败时刻,该事件将落入 E 还是 P 未知
(先验混合:E 型比例 14/24,但单次观测的似然比对两类几乎无分辨)。
归档不提名正是与"单次无分辨力"一致的克制——克制的根据是**无信息**,
不是"信息偏向瞬态"。

### 9.2 场景 B:抓取成功后滑落(SLIP_LOST,TRANSIENT_SUCCESS)

**情境**:pick 返回 success=true;夹爪闭合 + 分割质心随 EEF 上移(L2 一致);
搬运中途 t3 视觉显示物体坠落回桌面;夹爪开度无变化(空握);终态谓词不满足。

**Claim 轨迹**(v0.2 修正:本场景展示闭窗/开窗分离下"撤销不追溯"的正确语义):

| 时刻 | 事件 | claim 状态 |
|---|---|---|
| t1 | 夹爪闭合+质心上移双通道一致 | `GraspContact`(闭窗,[t1])L2 PROVISIONAL;`Lifted` L2 PROVISIONAL |
| t2 | 持有窗口 [t1,t2] 结束,窗口内逐测量点保持 | `Held(o,[t1,t2])`(闭窗)→ **CONFIRMED(L3)**,终态;同时开窗 `Maintained(o, t2→)` PROVISIONAL(持续到放置点的预期) |
| t3 | 分割:物体 z 骤降 + 质心离开爪部;夹爪开度不变 | **开窗** `Maintained(o,t2→)` → **CONTRADICTED**(持续证据链断裂);**闭窗** `Held[o,[t1,t2]]` **保持 CONFIRMED 不变**(v0.1 曾错误地把它改成 CONTRADICTED——t1-t2 期间持有过是历史事实,不因 t3 滑落而假);t3 后的 `GraspContact`(事件型,窗口 [t3])若反证成立则 CONTRADICTED |
| t4 | — | 历史账本:`Held[o,[t1,t2]]` 终态保留;`Maintained` 标 CONTRADICTED 但记录保留;Evolution 层两者都可见 |

**PA-Attr**:kind=SLIP_LOST(由"曾 ACQUIRED(闭窗 CONFIRMED)后开窗持续
断言被否定(`Maintained` CONTRADICTED + 物体 z 骤降反证)"的模式判出——
FAIL_KIND 自动机的用途;v0.2 注:判定链不再引用"闭窗 CONFIRMED 被 CONTRADICTED"
这一被删除的非法转换);若重试后成功 → E + TRANSIENT 特征
标记(acquired 与 stable 的分离模式);causal_grade=DESCRIPTIVE。

**双门判定**:Runtime——REPORT_COMPLETION=DENY(t3 后无 active 的任务级
claim);HOLD_AND_OBSERVE=触发(声明降级);重取(新的 pick attempt)按
CONTINUE 自由放行。Evolution——TRANSIENT_SUCCESS 模式入档:它是"契约选择
问题"的实证来源(用宽契约 ACQ 接受 vs 稳契约 STABLE 接受会给出不同结论),
但**单次滑落不构成技能缺陷候选**;ARCHIVE + 模式标注。

**实证对照**:ACQ−STABLE gap SAME +34.4pp / POLICY +37.5pp、hold ratio≈.70
[D]——即此场景中"用 acquisition 当成功"的机制有约三分之一概率接受一个
保不住的成果;方法用 L3_SUSTAINED 的窗口语义把这个差距显式化为证据等级问题。

### 9.3 场景 C:多次重采样仍失败(P 型,吸收态)

**情境**:同一事件(底物语境:五事件全 t9 [D])第 1..8 次 SAME 重放全败、
第 1..8 次 POLICY 重采样全败;失败模式一致(终态谓词不满足,机制特征集中于
同一 chunk_class);重建一致性元数据 ρ < ρ*。

**Claim 轨迹**(跨 attempt 聚合视角):每次 attempt 的 `TaskSatisfied` 均止步
于"不可满足"或 PROVISIONAL→CONTRADICTED;账本累积 16 次 attempt 的失败记录
与一致的 FAIL_KIND。

**PA-Attr**:

- Layer 1:PE = (n=16, runs 全连败, q̂_SAME=0, q̂_POLICY=0, contrast=0);
- Layer 2:contrast 近零 → **排除**动作特异性(A 的必要条件不满足);
- Layer 3:双臂全 0/8+0/8(§5.3 P 规则)→ failure_class = **P(已测动作分布下的
  持续失败,候选)**,evidence_mass=SUFFICIENT;L2 =
  PERSISTS_UNDER_TESTED_POLICY_SPACE(注意 §7.5 X1:"候选吸收态"的旧称
  有超分布外推的味道,v0.2 起规范表述为 tested-policy-space 持续性;
  "吸收"只是对已测分布内零翻盘的描述,不外推到未测策略族);
- Layer 4:推理链使用了 SAME 重放作为对照 → 依赖重建;ρ<ρ* → causal_grade
  降档至 MODERATE,标注 **APPROXIMATE**(R3:重放是机制证据,不是精确反事实);
- Layer 5:unknown_clauses 含 PREDICATE_AMBIGUITY(为何该任务族零头room的
  机制定位仍不可判——感知死/位置不可观测类的既有发现 [D]);
- Layer 6:repairability —— 若重采样与动作变化均无效的记录成立 →
  **NO_HEADROOM_IN_TESTED_RETRY_ACTIONS**(注意:这与 PROPOSE_REVIEW 并不矛盾,
  §8.2 矩阵外另有 abstain 通道;二者的张力处理见下)。

**双门判定**:Runtime——REPORT_FAILURE=**ALLOW(资格)**:证据状态足以支持
"止损/上报失败"的判定(连败结构 + 双臂零成功);但方法**不实现**自动止损
控制器(§10.1——"支持判定"与"执行控制"的边界即 §36 边界)。
Evolution——若 repairability 无负面证据:PROPOSE_REVIEW(最高授权:提名
候选审查);若 NO_HEADROOM_IN_TESTED_RETRY_ACTIONS:ABSTAIN(仅对重试类
候选)+ 完整记录(克制优先:
有持续失败、有证据量,但无"改了会好"的任何证据时,提名审查的期望价值
无法辩护——Stage P 的 verifier 无 headroom 结论 [D] 正是该 abstain 的实证
依据)。

**实证对照**:P 型 5/5 双臂 16 试零成功 [D];h(k) 连败 3 次后 1/17 ≪
同质 iid .30 [D]——按 §5.5 的分层语义,这是 **M1(异质 iid)下选择效应**
的体现:连败把该事件的后验失败概率筛向高端,足以支持止损判定(在 M1 层
成立,无需时序依赖);是否还存在 M2(真时序)成分,由 H-OE2 的 sham
检验判定 [S],不预设。C_pol(4)=.708≈C_pol(8) 的 89% [D]——第 4 次之后
的重试几乎不增加翻盘概率。n_arm/s 类槽位的未来定标将把这些结构转成正式的
证据量门槛(本文只留槽位)。

---

## 10. 方法论立场与边界

### 10.1 与 Stage R §36 Hard STOP 的边界

§36 禁止的是**机制实现类**工作:recovery method / classifier / escalation
policy / adaptive retry controller / FAR / FLARE / Graph / World Model /
verifier / Planner redesign / SFT / OPD / RL。本方法的位置:

- 本文交付 = **规范层文档**(形式定义 + 算法机制 + 推演),零代码零 rollout;
- PA-Attr 的确定性规则**不是** classifier(§36 语义下的"学习式分类器"):
  规则显式预注册、阈值显式待定标、无拟合;但若未来实现中被用于在线动作
  决策,则整体落入 adaptive controller 禁区——**实现与在线接线须另立阶段、
  另行预注册、用户显式批准**(与提案 §7 一致);
- 双门的输出语义是"资格判定",REPORT_FAILURE=ALLOW 的意思是"证据足以支持
  该判定",不是"系统将自动止损"。

### 10.2 防火墙

层 1 的 `visibility` 硬隔离贯穿全方法:离线真值判据(§3.1 右列)只用于
审计与未来校准,任何层的在线语义都不消费 offline_evaluation_only 事件。
真值判据的唯一合法用途:在离线审计中评估证据判据的假阳/假阴结构——
这正是 H0 方向 1(OUTCOME EVIDENCE CALIBRATION)与本方法的形式对接点:
**方向 1 定标的常数 = 本方法的 κ/τ/θ/ρ* 槽位**。

### 10.3 非概率纪律

在独立校准程序存在之前:

- evidence_quality / evidence_mass 是**序数**(order),不是基数(number);
- 不使用 Bayes / confidence / 概率保证措辞("Outcome Belief" 一词按提案
  约定不使用);
- 错误代价不对称只作定性偏序使用(A2),数值风险预算属未来校准。

### 10.4 已知局限(如实)

1. **底物窄**:P 型证据全部来自 t9 单任务族 [D];四类谱(及在线三档)与 κ/τ 常数的
   适用范围 = FALSE_GRASP@Pi0.5@libero_spatial 族,不外推。
2. **在线代理不完备**:"物体在爪中"在线不可直接观测 [S] → 场景 B 的
   CONTRADICTED 触发依赖视觉反证的及时性;temporal aliasing(低频图像漏掉
   接触/滑落瞬间)会使部分 `Held` claim 长期滞留 PROVISIONAL/UNKNOWN。
   这是特性不是缺陷(不臆断稳定),但削弱了 C3 的运行时表达力——如实声明。
3. **U 型悬置**:4/24 事件的不可归因 [D] 表明 R4 不是罕见路径;unknown_
   clauses 的类型化是否足以指导观测改进,未经验证。
4. **双门与 §36 的依存**:方法的 Runtime 半边距离可用还隔着"实现授权"与
   "常数定标"两道门;Evolution 半边另有 Zetta/RegenHarness 式工程治理环
   可复用 [P][S-ext]——本方法对它们的价值是输入信号的质量学,不是替代。
5. **M1 框架未定标(v0.2 新增)**:§5.5 的三层解释框架只建立了措辞纪律与
   检验设计,异质性分布 F 的拟合、sham(M2)对照、κ_info 的后验定标均
   未执行——这些是 H0 方向 1(H-OE2/H-OE3)获批后的工作,本文不预设结果。
6. **Zetta 对照的核验深度(v0.2 新增)**:v0.2 的 Zetta 更正基于其仓库
   main 分支源码级核验 [S-ext](evolution 模块),**未读其论文全文**;
   若论文含统计判据层面的表述(源码未体现),NOVELTY_REVIEW 的对照需再修订。
7. **既有 U4 标签按预注册口径引用(v0.2.1 更新)**:v0.2.1 已回归 Stage R
   冻结四类(§5.3),"按 v0.2 语义重分类 U4"的议题已随 A2b 式重分类
   暗示一并撤销;本文引用"U4"一律按预注册口径(恰 1 次成功的证据量
   边缘带)理解,任何重分类须另立批准的分析。
8. **L2 通道条件依赖未审计(v0.2.1 新增,边 5)**:"≥2 独立通道"的
   独立性目前是设计假设——同一分割模型派生的特征可能共享误差源,
   未做误差源级核验;定标(H0 方向 1)完成前,L2_CONCORDANT 的可信度
   按风险项对待(§4.2)。

---

## 附录 A:术语表

| 术语 | 定义处 | 一句话 |
|---|---|---|
| Outcome State | §3 | 物理结果的时间索引状态机(可逆,含 FAIL_KIND) |
| Evidence Claim | §4 | 对结果谓词的有时效、分等级、可撤销声明 |
| 闭窗/开窗 claim | §4.1 | 回看性(终态不可被未来否定)/前瞻性(可被未来否定)二分 |
| L0-L3 | §4.2 | 工具报告 → 单代理 → 多通道一致 → 窗口持续 |
| 事后标签 / 在线判断 | §5.0 | 分类(序列终了回看)/ 证据分级(执行中),两个不同对象 |
| Failure Persistence | §5 | 跨 attempt 的失败重复性证据(PE 对象) |
| E/A/P/U(+DETERMINING) | §5.3 | 事后四类(Stage R 冻结):瞬态/动作特异/已测分布持续(候选)/恰 1 次成功边缘带;DETERMINING=证据未齐的过程状态,非标签 |
| M0/M1/M2 | §5.5 | 同质 iid / 异质 iid(选择效应)/ 真·时序依赖——假设层,均未检验 |
| PA-Attr | §7 | 消费 claims+PE 输出四层 AttributionStatement 的确定性算法 |
| 四层结论 | §7.1 | L1 关联 / L2 持续性 / L3 因果 / L4 可修复,层间推导白名单(§7.5) |
| causal_grade | §7.1 | UNIDENTIFIED(默认)/DESCRIPTIVE/MODERATE/STRONG 因果声称封顶 |
| evidence_mass | §7.1 | INSUFFICIENT/MARGINAL/SUFFICIENT 证据量(序数) |
| repairability | §5.4 | 与 P 解耦的"审查资格"三值;负面档仅覆盖已测重试动作类 |
| Runtime/Evolution Gate | §6 | 立即行动 vs 长期候选的双资格门 |
| 代价对齐授权(A2) | §6.4 | 门槛随错误代价非递减,仅限可比决策对的局部偏序;决策三档建模 |
| 撤销不追溯 | §4.4 | CONTRADICTED 收未来授权、不抹历史证据价值 |

## 附录 B:引用数字出典

| 数字 | 出处 |
|---|---|
| q_same .302 [.193,.417] / q_policy .323 / 配对差 +2.1pp 中位 0;h(k) k=4 1/17、k=8 0/11;C_pol(4)=.708=C_pol(8)×89%;E 14/A 1/P 5/U 4(P 全 t9);E 14/14 ≥1 成功、P 5/5 双臂零成功 | analysis/STAGE_R_FINAL_REPORT.md + stageR_event_probabilities.csv [D] |
| ACQ−STABLE gap SAME +34.4pp / POLICY +37.5pp;hold ratio≈.70 | STAGE_Q/R 终报 [D] |
| restore transition-class 10/14=.769<.90 → APPROXIMATE;PREFIX 32/32 哈希级;≤7.8e-4m 单调漂移 | stageR reconstruction 决议 [D] |
| Stage P O@8−O@1=10pp<15pp、sup=100% | stagep 终报 [D] |
| 观测面/防火墙/工具通道;"物体在爪中"在线不可直接观测 | toolkit.py / env_server.py:282-301 / tools.py [S](H0 §3 清单) |
| 感知死/位置不可观测/term 型机制发现 | Stage L 终报 [D] |
