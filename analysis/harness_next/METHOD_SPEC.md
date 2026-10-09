# Persistence-Aware Evidence Governance — 方法规范(METHOD_SPEC)

> 2026-10-09 | 版本 v0.1 方法设计 / 未实现、未测试、未定标。
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
> - 证据等级惯例:**[S]** 本仓源码级 / **[D]** 本仓实验数据级 / **[P]** 外部论文摘要级。
>   外部对照的深核结论在同目录 `NOVELTY_REVIEW.md`。

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
- **A2(授权单调)**:决策的影响时间尺度越长,所需证据强度越高,且该关系是偏序——
  Evolution 门所需证据强度严格不低于 Runtime 门(形式化见 §6.4)。
- **A3(归因克制)**:当证据不足以区分竞争性解释时,输出 UNKNOWN/ABSTAIN 而非
  最相似假设。克制输出是一等公民,不是失败状态。

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
            valid_from, valid_until,     时间窗
            E_sup ⊆ ObservationEvent,   支持事件集(带 provenance)
            level ∈ {L0, L1, L2, L3},   证据等级
            status ∈ {PROVISIONAL, CONFIRMED, CONTRADICTED, EXPIRED, UNKNOWN},
            scope ⊆ DECISION_TYPES      本声明被授权参与的决策类型
          ⟩
```

### 4.2 证据等级(单调,不可越级)

| 等级 | 定义 | 例 |
|---|---|---|
| **L0_TOOL_REPORT** | 工具/技能返回值,无独立物理证据 | pick() 的 success flag |
| **L1_SINGLE_PROXY** | 单通道传感器代理满足判据 | gripper_qpos 闭合 |
| **L2_CONCORDANT** | ≥2 独立通道一致 | 夹爪闭合 + 分割质心随 EEF 上移 |
| **L3_SUSTAINED** | 窗口内逐测量点保持的 L2 | Held(o,W) 全窗一致 |

依据:工具 success ≠ 物理成功(ARCHITECTURE_PROPOSAL 机制 1);视觉富、结构贫、
成败单点的观测不对称 [S][D] 使 L2 需要跨通道合取才可达。

### 4.3 五态生命周期与转换规则

```text
                    ┌──────────── 新证据到达(等级≥L1,判据部分满足)
                    ▼
              PROVISIONAL ──── 窗口内 L3 持续 ────▶ CONFIRMED
                 │   │                                │
                 │   └─ 反证事件 ──▶ CONTRADICTED ◀────┘(窗口内反证)
                 │        (如 GRASP_LOST 观测)
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
| PROVISIONAL/CONFIRMED | 反证事件(≥L1,与谓词否定一致) | CONTRADICTED | **当前授权即刻失效**;历史记录保留并标 superseded |
| PROVISIONAL/CONFIRMED | valid_until 到期且无 L3 续期 | EXPIRED | 不再授权;不构成反证 |
| 任意 | 判据可满足性破坏(缺口/混叠) | UNKNOWN | 一等公民:显式承认"不知道" |

### 4.4 时间语义(本方法对 C3 的落实)

1. **时间局部性**:claim 只授权其窗口内的决策。`CONFIRMED(Held(o,[t1,t2]))`
   对 t3>t2 的决策无授权力。
2. **不可继承**:新窗口需新证据。CONFIRMED 不自动延拓——防"永久持有"谬误
   (物理持有每一秒都可能失效;ACQ−STABLE gap 是其统计表现 [D])。
3. **撤销不追溯**:CONTRADICTED 撤销的是**未来授权**,不抹除**历史证据价值**——
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
  contrast 是**排除**动作特异性的证据,不是改善来源;
- 连败携带超信息:h(k) 连败 3 次后第 4 次成功 1/17、连败 7 次后 0/11,
  远低于 iid 边际 .30 → runs 分量承载时序信息,不能压缩成 n 和 q̂;
- 吸收态存在:P 型事件双臂 16 试零成功(5/5),E 型 14/14 十六试内至少一次
  成功 → PE 分布呈现实证的" ephemeral / absorbing"双峰。

### 5.3 四分类的形式判定规则

```text
输入 PE(e),阈值槽位(待定标):κ_E, κ_P(最小证据次数), δ(对比容忍)

E (execution-ephemeral):  ∃ y_i = 1(任一臂出现过成功)
                          [失败不持久;最保守归类,不触发任何演化动作]
A (action-specific):      SAME 全 0 ∧ POLICY 存在 1 ∧ |contrast| ≥ δ
                          [失败随动作选择消失 → 动作序列是原因]
P (policy-persistent):    双臂全 0 ∧ n ≥ κ_P
                          [候选吸收态;"候选"= 仍需 repairability 独立审查]
U (unresolved):           以上规则的不完备残余:证据矛盾、n < 所需、
                          观测缺口使 y 序列不可信、终态多义
```

**方向性设计(归因克制的落实)**:

- 从"出现过成功"推 E 是**保守方向**(永不触发演化),故允许单证据;
- 从"全失败"推 P 是**高影响方向**(可能触发演化审查),故要求 n ≥ κ_P 的
  证据量 + 只输出"候选"资格;
- U 不是垃圾类:它的 gaps 分量显式记录"为何无法归因",是未来观测改进的指向
  (Stage R 的 U 型 4 事件即此类 [D])。

### 5.4 与 repairability 的解耦(公理 A3 的最重应用)

```text
repairability ∈ { UNKNOWN,                      默认
                  EVIDENCE_FOR_CANDIDATE_REVIEW, 存在可修复缺口的正面证据
                  NO_LOCAL_HEADROOM_OBSERVED }   重试/重采样/动作变化均无效的负面证据
```

**P 与 repairability 是两个独立命题**:"失败会持续"≠"改技能能修好"。
Stage P 已证本栈 verifier 无 headroom(O@8−O@1=10pp < 15pp 门)[D]——
这说明把"持续失败"直接翻译成"需要且值得技能更新"在物理上是站不住的推导,
必须显式分离。repairability 回答的是"进一步审查的资格",不是更新成功概率
(ARCHITECTURE_PROPOSAL 契约 3 的原语义保留)。

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
    if attribution.failure_class ∉ {P, A}:        # E/U 类
        return ARCHIVE(仅归档)                     # 单次/瞬态失败永不触发演化
    if attribution.evidence_mass < θ_EVO:          # 证据量槽位(待定标)
        return QUARANTINE                          # 证据不足,隔离待积累
    if attribution.repairability == NO_LOCAL_HEADROOM_OBSERVED:
        return ABSTAIN + 记录                      # 有持续失败但无修复空间证据
    if attribution.causal_grade == DESCRIPTIVE:    # 重建保真降级到底(§7.2 R3)
        return QUARANTINE                          # 只能描述,不能提名
    return PROPOSE_REVIEW                          # 最高输出:提名候选审查
```

**PROPOSE_REVIEW 是本方法的最高授权**。技能/配置的实际修改、验证、晋升、回滚
属于 Zetta Loop3 / SkillOpt / RegenHarness 已建立的工程治理环 [S][P],本方法
不重造,只负责给它们提供一个**证据面合格的输入**。

### 6.4 授权单调性(公理 A2 的形式化)

定义证据强度偏序:

```text
strength(claim) = (level, status) 上的字典序:L3 > L2 > L1 > L0;
                                   CONFIRMED > PROVISIONAL > (EXPIRED, CONTRADICTED, UNKNOWN)
strength(attribution) = (causal_grade, evidence_mass) 上的积序
```

**单调性条件(方法的中心不变量)**:

```
∀ d_R ∈ D_RUNTIME, d_E ∈ D_EVOLUTION:
    MinStrength(d_E) ≰ MinStrength(d_R)     # Evolution 门槛不低于任一 Runtime 门槛
    且 PROPOSE_REVIEW 的门槛 > 全部 Runtime 门槛(严格)
```

依据:错误代价的时间尺度不对称——Runtime 误判影响本 episode,Evolution 误判
通过技能库影响**所有未来 episode**(把执行噪声固化为永久知识,即
RESEARCH_PROPOSAL §2 的核心担忧)。

---

## 7. 核心算法:Persistence-Aware Attribution(PA-Attr)

### 7.1 输入输出规格

```text
输入:
  e            失败事件(含上下文)
  {a_i}        attempt 序列(含每 attempt 的 claim 账本)
  meta         元数据:重建一致性 ρ(restore transition-class 一致率类)、
               观测缺口、契约选择(ACQ/STABLE)、采样条件
输出 AttributionStatement:
  ( observed_failure_kind ∈ FAIL_KIND ∪ {UNKNOWN},
    failure_class ∈ {E, A, P, U},
    causal_grade ∈ {STRONG, MODERATE, DESCRIPTIVE},
    evidence_mass ∈ {INSUFFICIENT, MARGINAL, SUFFICIENT},
    repairability ∈ 三值(§5.4),
    unknown_clauses: List[缺口描述],     R4 的显式输出
    scope )                                 声明适用范围(任务族/栈/契约)
```

### 7.2 四种证据情形的处理(用户点名的四情况)

**R1 随机物理失败**(单次或少数失败,重试可成)

- 事实:y 序列中存在成功(或 n=1 单次失败,无序列)。
- 处理:→ failure_class = E;causal_grade 上限 DESCRIPTIVE(对单次失败,
  **任何高于描述性的因果声称都被禁止**);evidence_mass = INSUFFICIENT;
  演化层动作 = ARCHIVE。
- 依据:E 型 14/14 在 16 试内出现成功 [D]——单次失败对"策略有缺陷"的
  证据力在实证上可忽略;q≈.30 的边际随机性 [D] 使"失败"本身是常态事件。

**R2 有限重复证据**(n 不足以分类)

- 事实:n < κ_P(或区间过宽,经验率的置信结构覆盖多个假设)。
- 处理:→ failure_class = U;双门输出只能 HOLD(运行时)/ QUARANTINE(演化),
  **既不允许 DENY 策略性结论,也不允许提名审查**;输出建议 = 积累更多 attempt
  (在未来的自然执行中,不专门采集)。
- 语义:证据量不足时,方法的责任是**拒绝下结论**,不是猜一个。
  (C_pol(4)=.708 已是 C_pol(8) 的 89% [D]——证据的边际价值随 n 衰减,
  κ_P 的定标正是要找这个拐点,属未来校准。)

**R3 状态重建不确定性**(结论依赖 restore/replay 机制)

- 事实:归因推理使用了状态重建(如"同动作重放也失败 → 排除动作特异性")。
- 处理:检查重建一致性元数据 ρ;ρ < ρ*(槽位,待定标)时 causal_grade 降一档
  (STRONG→MODERATE→DESCRIPTIVE),全部跨 attempt 聚合声明标注 APPROXIMATE;
  Evolution 门对 APPROXIMATE 声明减权(§6.3 的 QUARANTINE 分支)。
- 依据:restore transition-class 一致率 10/14=.769 < .90 资格门 [D]——
  重放不是精确反事实 oracle;PREFIX 哈希级重建 32/32 [D] 只保证**仪器侧**
  可复现,不保证**执行侧**逐位(≤7.8e-4m 单调漂移)。

**R4 无法归因**(观测缺口 / 终态多义 / 代理失效)

- 事实:FAIL_KIND 判为 UNEXPLAINED,或 y 序列的可信度被 gaps 破坏。
- 处理:→ unknown_clauses 显式列出缺口(类型化:SENSOR_GAP / TEMPORAL_ALIASING /
  PREDICATE_AMBIGUITY / PROXY_FAILURE);failure_class = U;causal_grade =
  最低档;方法**显式 abstain**,不输出最相似假设。
- 语义:与 EmbodiSkill 式"必须分流"的关键差异——本方法允许且尊重"分不了"。
  U 型 4 事件 [D] 是该情形的实证存在性证明。

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
    #   contrast 显著 → A 的必要条件;近零 → 排除动作特异性
    #   实证先验:配对差 +2.1pp 中位 0 [D] → 该层在本栈多为排除性证据

    # Layer 3 持续性分类:应用 §5.3 规则(阈值槽位 κ_E/κ_P/δ 待定标)
    failure_class = classify_persistence(PE)        # E / A / P / U

    # Layer 4 保真降级:重建依赖检查(R3)
    causal_grade = STRONG if not uses_replay(e) else downgrade(meta.rho)
    #   ρ ≥ ρ*: 可保持档但标 REPLAY_BASED;ρ < ρ*: 降一档 + APPROXIMATE

    # Layer 5 证据量与缺口(R2 / R4)
    evidence_mass = assess_mass(PE.n, PE.runs)      # INSUFFICIENT/MARGINAL/SUFFICIENT
    unknown_clauses = type_gaps(PE.gaps + e.gaps)   # 类型化缺口列表

    # Layer 6 可修复性(独立轴,§5.4)
    repairability = assess_repairability(PE, meta)  # 默认 UNKNOWN

    return AttributionStatement(kind, failure_class, causal_grade,
                                evidence_mass, repairability,
                                unknown_clauses, scope=meta.scope)
```

复杂度与可实现性:全部操作是**声明账本上的符号运算与计数**,无学习组件、
无模型推理、无环境交互——与"纯离线测量学"定位一致,亦不触 §36 的任何
禁令类目(不是 classifier:分类规则是预注册的确定性规则,阈值显式待定标而非
从数据拟合——定标程序另行审批)。

### 7.4 明确不做的事(负面规范)

1. 不从多次失败直接推理"策略错误"或"技能需要修改"(只到 P 候选 +
   repairability 审查资格)。
2. 不把统计类别(failure_class)冒称为未观察到的因果 root cause
   (causal_grade 封顶)。
3. 不输出校准概率(无校准程序前,evidence_quality 只是序数不是基数,§10.3)。
4. 不消费任何 offline_evaluation_only 事件(防火墙)。
5. 不实现重试/止损/恢复控制器(§10.1)。

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

| 证据状态(行) | CONTINUE | REPORT_COMPLETION | HOLD_OBSERVE | REPORT_FAILURE | ARCHIVE | QUARANTINE | PROPOSE_REVIEW |
|---|---|---|---|---|---|---|---|
| TaskSatisfied L2+ active | ✅ | ✅ | — | ❌ | ✅ | — | — |
| L0-only(仅工具报告) | ✅ | ❌ | 建议 | ❌ | ✅ | — | ❌ |
| 声明降级(CONTRA/EXPIRED) | ❌ | ❌ | ✅(触发) | 视反证 | ✅ | — | — |
| 单次失败(E/未知) | ✅ | ❌ | — | ❌(证据不足) | ✅ | — | ❌ |
| 连败中 n<κ_P | ✅ | ❌ | 建议 | ❌ | ✅ | ✅ | ❌ |
| 双臂全败 n≥κ_P + 修复证据 | ⚠️ | ❌ | — | ✅(资格) | ✅ | — | ✅(最高) |
| 重建保真不足(ρ<ρ*) | ✅ | — | — | ⚠️ | ✅ | ✅(减权) | ❌ |
| 观测缺口(R4) | ✅ | ❌ | ✅(建议) | ❌ | ✅ | ✅ | ❌ |

读法举例:第 6 行——一个证据量足够的 P 型持续失败,**支持**"上报失败"的
判定资格(Runtime 门允许 REPORT_FAILURE),且**支持**提名候选审查
(Evolution 门最高输出),但依然**不允许**任何直接的技能修改(该列不存在)。
第 1 列几乎全 ✅ 不是设计疏忽:CONTINUE 是零授权门槛的默认自由(公理 A3 的
运行时体现——无反证不拦截),方法的约束力全部集中在**高影响授权**上。

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

**PA-Attr**:kind=GRASP_MISS;n=1(无序列)→ Layer 3 不满足任何规则的完备
条件 → failure_class=E(保守方向,证据量 INSUFFICIENT);causal_grade=
DESCRIPTIVE(单次封顶,R1);unknown_clauses=[];repairability=UNKNOWN。

**双门判定**:Runtime——CONTINUE=ALLOW(重试自由);REPORT_COMPLETION=DENY;
REPORT_FAILURE=DENY(单次失败不构成失败上报资格)。Evolution——ARCHIVE(仅归档)。

**实证对照**:E 型事件 14/14 在 16 试内出现成功 [D]——单次抓空对未来的预测力
接近零,归档不提名正是与该实证一致的克制。

### 9.2 场景 B:抓取成功后滑落(SLIP_LOST,TRANSIENT_SUCCESS)

**情境**:pick 返回 success=true;夹爪闭合 + 分割质心随 EEF 上移(L2 一致);
搬运中途 t3 视觉显示物体坠落回桌面;夹爪开度无变化(空握);终态谓词不满足。

**Claim 轨迹**(本场景展示"撤销不追溯"的全部语义):

| 时刻 | 事件 | claim 状态 |
|---|---|---|
| t1 | 夹爪闭合+质心上移双通道一致 | `GraspContact` L2 PROVISIONAL;`Lifted` L2 PROVISIONAL |
| t2 | 持有窗口 [t1,t2] 内逐测量点保持 | `Held(o,[t1,t2])` → **CONFIRMED(L3)** |
| t3 | 分割:物体 z 骤降 + 质心离开爪部;夹爪开度不变 | `Held` → **CONTRADICTED**;`GraspContact` → CONTRADICTED;当前授权全灭 |
| t4 | — | 历史账本:`Held[o,[t1,t2]]` 标 superseded 但**保留**;Evolution 层统计可见 |

**PA-Attr**:kind=SLIP_LOST(由"曾 CONFIRMED 后 CONTRADICTED"的模式直接
判出——这正是 FAIL_KIND 自动机的用途);若重试后成功 → E + TRANSIENT 特征
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
- Layer 3:双臂全 0 且 n≥κ_P → failure_class = **P(候选吸收态)**,
  evidence_mass=SUFFICIENT;
- Layer 4:推理链使用了 SAME 重放作为对照 → 依赖重建;ρ<ρ* → causal_grade
  降档至 MODERATE,标注 **APPROXIMATE**(R3:重放是机制证据,不是精确反事实);
- Layer 5:unknown_clauses 含 PREDICATE_AMBIGUITY(为何该任务族零头room的
  机制定位仍不可判——感知死/位置不可观测类的既有发现 [D]);
- Layer 6:repairability —— 若重采样与动作变化均无效的记录成立 →
  **NO_LOCAL_HEADROOM_OBSERVED**(注意:这与 PROPOSE_REVIEW 并不矛盾,
  §8.2 矩阵外另有 abstain 通道;二者的张力处理见下)。

**双门判定**:Runtime——REPORT_FAILURE=**ALLOW(资格)**:证据状态足以支持
"止损/上报失败"的判定(连败结构 + 双臂零成功);但方法**不实现**自动止损
控制器(§10.1——"支持判定"与"执行控制"的边界即 §36 边界)。
Evolution——若 repairability 无负面证据:PROPOSE_REVIEW(最高授权:提名
候选审查);若 NO_LOCAL_HEADROOM_OBSERVED:ABSTAIN + 完整记录(克制优先:
有持续失败、有证据量,但无"改了会好"的任何证据时,提名审查的期望价值
无法辩护——Stage P 的 verifier 无 headroom 结论 [D] 正是该 abstain 的实证
依据)。

**实证对照**:P 型 5/5 双臂 16 试零成功 [D];h(k) 连败 3 次后 1/17 ≪ iid
.30 [D]——连败史本身携带"再试无用"的预测信息;C_pol(4)=.708≈C_pol(8)
的 89% [D]——第 4 次之后的重试几乎不增加翻盘概率。κ_P 的未来定标将把
这些结构转成正式的证据量门槛(本文只留槽位)。

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

1. **底物窄**:P 型证据全部来自 t9 单任务族 [D];E/A/P/U 谱与 κ/τ 常数的
   适用范围 = FALSE_GRASP@Pi0.5@libero_spatial 族,不外推。
2. **在线代理不完备**:"物体在爪中"在线不可直接观测 [S] → 场景 B 的
   CONTRADICTED 触发依赖视觉反证的及时性;temporal aliasing(低频图像漏掉
   接触/滑落瞬间)会使部分 `Held` claim 长期滞留 PROVISIONAL/UNKNOWN。
   这是特性不是缺陷(不臆断稳定),但削弱了 C3 的运行时表达力——如实声明。
3. **U 型悬置**:4/24 事件的不可归因 [D] 表明 R4 不是罕见路径;unknown_
   clauses 的类型化是否足以指导观测改进,未经验证。
4. **双门与 §36 的依存**:方法的 Runtime 半边距离可用还隔着"实现授权"与
   "常数定标"两道门;Evolution 半边另有 Zetta/RegenHarness 式工程治理环
   可复用 [P]——本方法对它们的价值是输入信号的质量学,不是替代。

---

## 附录 A:术语表

| 术语 | 定义处 | 一句话 |
|---|---|---|
| Outcome State | §3 | 物理结果的时间索引状态机(可逆,含 FAIL_KIND) |
| Evidence Claim | §4 | 对结果谓词的有时效、分等级、可撤销声明 |
| L0-L3 | §4.2 | 工具报告 → 单代理 → 多通道一致 → 窗口持续 |
| Failure Persistence | §5 | 跨 attempt 的失败重复性证据(PE 对象) |
| E/A/P/U | §5.3 | 瞬态/动作特异/策略持久(候选)/不可归因 |
| PA-Attr | §7 | 消费 claims+PE 输出 AttributionStatement 的确定性算法 |
| causal_grade | §7.1 | STRONG/MODERATE/DESCRIPTIVE 因果声称封顶 |
| evidence_mass | §7.1 | INSUFFICIENT/MARGINAL/SUFFICIENT 证据量(序数) |
| repairability | §5.4 | 与 P 解耦的"进一步审查资格"三值 |
| Runtime/Evolution Gate | §6 | 立即行动 vs 长期候选的双资格门 |
| 授权单调性 | §6.4 | Evolution 证据门槛 ≥ 一切 Runtime 门槛(偏序) |
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
