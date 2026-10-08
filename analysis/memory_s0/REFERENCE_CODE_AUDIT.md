# S0 任务一:参考实现 Memory 机制对照审计

> 生成:2026-10-08 | 性质:只读审计(无新实验、无模型修改、无大仓库下载)
> 目的:为"Memory 在哪些决策点不可替代"提供外部参照系 —— 六个 2025-2026
> 记忆增强具身/agent 系统的**真实机制**,按统一五维度对照。
> 证据等级:**[S] = 源码已验证**(经 GitHub contents API 逐文件阅读);
> **[P] = 仅论文支持**(README 摘要 + 检索结果,代码未公开或未发布)。

## 一、总对照表(六系统 × 五机制)

| 系统 | 等级 | 记忆写入 | 记忆更新 | 记忆读取 | 决策接口 | 验证机制 |
|---|---|---|---|---|---|---|
| **Zetta** (air-embodied-brain/Zetta-Embodiment) | [S] | 集后 orchestrator 重写任务级参数块(schema v1 固定 7 键;24KB/64 evidence 行上限) | append-only 哈希链版本(versions/rev-NNNN.json + updates.jsonl);`update_boundary="after_episode_only"` episode 内冻结 | episode 开始把**不可变快照**注入 planner 初始 prompt(定位为 "fallible prior… prefer current observations") | 无条件前置注入(非决策点触发) | 三层:反泄漏校验(禁种子坐标/pixel/行列号/绝对路径/BDDL)+ TemporalCritic(chunk 内冻结规则,时间语义 dwell/stagnant/cooldown/consecutive,proposal-only)+ Role1 恢复审批门(剥离绝对几何) |
| **SkillOpt** (microsoft/skillopt) | [S] | ReflACT 六段循环 Rollout→Reflect→Aggregate→Select→Update;记忆=自然语言技能文档(best_skill.md) | Evaluate gate(accept/reject);EXECUTION_LAPSE(执行失误)写入**保护区附录**,与技能缺陷分离 | 技能文档整篇作为 agent 执行指令(文本空间) | 每轮任务执行前载入 | held-out 任务成功率门 + 训练类比机制(LR scheduler 式衰减、CLIP 式排序、slow-update 比较对、meta-skill) |
| **EmbodiSkill** (air-embodied-brain/EmbodiSkill, arXiv:2605.10332) | [S] | Interaction Graph:轨迹凝练 + FINCH 聚类成技能节点 | skill-aware reflection(**执行错误 vs 技能缺陷**分流);手册版本化(current.json + versions/ + reflections epoch) | 三层图检索(ChromaDB 向量):Query Graph k-hop 过往成功 → Skill Graph | 任务受理时检索技能手册 | 反思分流 + 版本化前后对比;域=具身编码 agent(CaP-Gym) |
| **SimpleARM** (simplearm/SimpleARM, arXiv:2609.36595) | [P] | 任务指令**指定监控内容** → 冻结感知工具在线维护紧凑 typed state(四类:relation/reference/progress/route) | 在线增量(interaction-derived,非留存视觉帧) | **条件检索**:仅当提议子目标依赖历史时 structured access;召回实体经 current-view grounding 解析到当前视野 | 子目标提议点(决策时刻)条件触发 | RoboMME 16 任务 67.17% vs 44.51%(最强非 oracle);四类 typed state 消融(relation/reference/progress/route 各自贡献) |
| **Ledger** (arXiv 2026-09-28, object ledger for memory-augmented VLAs) | [P] | 对象中心账本:对象状态变化事件入账 | 账本式追加(对象条目维度) | VLA 决策时查账本(对象当前抽象状态) | 对象交互决策点 | 论文实验(长时程部分可观测操作:记住抽屉里放了什么、移动了谁的杯子) |
| **BATON** (arXiv:2608.16889) | [P] | 已解子任务抽象为记忆(agentic subtask exploration) | transition-aware memory 更新(转换边界) | 子任务间传递记忆 | **verifier agent 管辖转换调用**(转换确认后才写入/读取) | verifier 判定子任务完成;RoboMemArena +11.6% |

## 二、逐系统证据与关键细节

### 2.1 Zetta [S] —— 与 RPent 同 harness 家族的自进化系统

源码路径(经 api.github.com contents API 阅读,未下载):
- `zetta/memory/task_memory.py`(全文)
- `zetta/evolution/critic.py`(TemporalCritic)
- `robots/libero/role1_recovery.py`(前段)

机制要点:
1. **参数块 schema v1**:7 个固定键(strategy_summary / decision_rules /
   tool_parameters / prompt_ladder / failure_modes / success_checks /
   open_questions)。不是自由文本 —— 是**受控词表的紧凑状态**。
2. **episode 内冻结**:`update_boundary="after_episode_only"`。运行中
   记忆只读;写发生在集后 orchestrator。这从结构上杜绝了"记忆被当轮
   决策污染"。
3. **注入即先验,非真理**:注入文本自述 "fallible prior… prefer current
   observations" —— 明确要求当前观测优先,记忆只是先验。
4. **反泄漏三件套**:校验禁种子坐标(xyz/pixel/row/col)、绝对路径、
   BDDL 原文;Role1 恢复审批门前再剥一层绝对几何。
5. **同源发现**:`robots/libero/` 骨架(toolkit / env_client / env_server /
   sam3_server / vla_server / role1_recovery)与 RPent 逐文件同名 ——
   RPent(HarnessVLA 私有镜像)与 Zetta 出自同一 harness 家族。
   Zetta 的 task_memory 反泄漏纪律与 RPent Stage D 的防火墙纪律
   (alias 禁种子/真值词)同构,说明这是该家族反复收敛到的同一设计约束。
6. **TemporalCritic 是冻结规则评估器**,不是学习模型:chunk 内以
   dwell/stagnant/cooldown/consecutive 等**时间语义**判提议,只评
   proposal 不改动作 —— 与 RPent B2 verifier(裁决不驱动行为)同位。

### 2.2 SkillOpt [S] —— 记忆=可验证的自然语言技能文档

源码:`skillopt/engine/trainer.py`(ReflACT 主循环)。
- 六段循环每段职责清晰:Rollout 采轨迹 → Reflect 逐轨迹反思 →
  Aggregate 跨轨迹聚合 → Select 选最优 → Update 写 best_skill.md →
  Evaluate held-out 门(accept/reject)。
- **EXECUTION_LAPSE 分流**是亮点:执行失误(环境随机性)进保护区
  附录,不污染技能正文 —— 与 RPent Stage R 发现"瞬态失败占多数
  (E14/24)"直接对口:瞬态失败不该写进记忆。
- 文本空间训练类比(LR scheduler / CLIP 排序 / slow-update 比较对 /
  meta-skill)提供了不反传梯度的"训练"机制。
- 域:LLM agent(文本任务),非机器人 —— 迁移到具身需验证门重设计。

### 2.3 EmbodiSkill [S] —— 三层图 + 版本化手册

源码:`agentkit/skill/embodiskill_skill/EmbodiSkill.py`。
- 三层:Interaction Graph(轨迹凝练+FINCH 聚类)/ Query Graph
  (k-hop 过往成功)/ Skill Graph(检索)。
- ChromaDB 向量检索 —— 与 RPent retrieval.py 的可选 _Embedder 同类。
- 手册版本化(current.json + versions/ + reflections epoch)与
  Zetta 哈希链版本同旨:记忆演进可回溯。
- skill-aware reflection 区分执行错误 vs 技能缺陷 —— 与 SkillOpt
  EXECUTION_LAPSE 分流同一设计模式(两系统独立收敛)。
- 域:具身编码 agent(CaP-Gym),非操作机器人。

### 2.4 SimpleARM [P] —— 与 RPent 必要性问题最对口的设计

论文 arXiv:2609.36595;官方仓 `simplearm/SimpleARM` 存在但 README
明示 "Code will be released soon"(2026-10-08 核对)—— 故降级为论文级。

核心主张:**"控制的有效记忆不是留存的视觉历史,而是从交互历史导出的
紧凑任务相关状态"**。机制链:
1. 任务指令指定要监控什么(不监控全部);
2. 冻结感知工具在线维护 typed state(不训练);
3. **仅当提议子目标依赖历史时**才 structured access 检索(决策点条件触发);
4. 召回实体经 current-view grounding 解析(防记忆与现实脱节)。

RoboMME 16 任务:67.17% vs 44.51%(最强非记忆基线)。
四类状态消融:relation / reference / progress / route 各有机制特异性贡献。

**对本审计的意义**:SimpleARM 把"Memory 必要性"操作化为**任务侧属性**
(存在依赖历史的子目标)+ **表示侧属性**(typed state 可维护)+
**触发侧属性**(决策点条件检索)。RPent 既往 Memory 线(A-G)恰好缺
第一环 —— 任务族本身没有历史依赖决策点(详见任务三审计)。

### 2.5 Ledger [P]

arXiv 2026-09-28("an Object Ledger for Memory-Augmented VLAs")。
对象中心账本:以**对象**为一等公民记录状态变化(抽屉里放了什么、
谁的杯子被移动)。无公开仓库(检索 2026-10-08 未发现)。
对本审计的意义:对象身份 + 历史位置的跨时程账本是 RPent 结构化状态
目前没有的形态(任务二确认)。

### 2.6 BATON [P]

arXiv:2608.16889("Don't Drop the BATON: Long-Horizon Robot Manipulation
via Agentic Subtask Exploration and Transition-aware Memory")。
LLM 编排冻结 VLA;**verifier agent 管辖子任务转换调用**;已解子任务
抽象为记忆。RoboMemArena +11.6%。无公开仓库。
对本审计的意义:验证机制放在**转换边界**(verifier 确认后才传递记忆)
—— 与 RPent Stage Q 的稳定恢复契约(首中后保持)同思路。

## 三、跨系统共性发现(机制层)

1. **写入全部在 episode 边界或轨迹边界**:Zetta `after_episode_only` /
   SkillOpt rollout 后 / EmbodiSkill 轨迹凝练。没有系统在 episode 内
   写持久记忆。→ intra-episode 状态(进度/近因)与持久记忆是两层,
   前者用 tracker,后者集后写。
2. **读取分两派**:无条件前置(Zetta prompt 注入)vs 决策点条件检索
   (EmbodiSkill 任务受理、SimpleARM 子目标提议)。RPent Stage B1/C
   的 turn_boundary 注入属于后者,但触发规则是从进度信号驱动的
   (R1-R5),不是从"该决策是否依赖历史"驱动 —— 与 SimpleARM 的
   条件定义不同源。
3. **验证全靠外部可验证信号**(成功检查 / verifier / held-out 门),
   无一系统用记忆自身一致性当验证。
4. **瞬态/持久分流是共识**:SkillOpt EXECUTION_LAPSE 保护区、
   EmbodiSkill 执行错误 vs 技能缺陷、Zetta episode 冻结 —— 三系统
   独立收敛到"环境随机性失败不进记忆"。RPent Stage R 的 E14/24
   瞬态谱为该纪律提供了本任务族的实证支撑。
5. **反泄漏/防污染纪律**(Zetta 反种子坐标、版本化哈希链)与 RPent
   Stage D 防火墙同构 —— 同 harness 家族同一收敛。

## 四、对 RPent 的机制启示(仅记录,不展开实现)

- RPent 已有:集后离线蒸馏卡片(61 张)、词面+可选语义检索、
  turn_boundary 节流注入、B2 verifier、PhaseTracker episode 内状态
  (任务二详列)。
- RPent 缺(相对六系统):① 决策点**按历史依赖性**定义的触发
  (SimpleARM 型条件检索);② 对象中心跨时程账本(Ledger 型);
  ③ 记忆版本化/演进环(Zetta/EmbodiSkill 型);④ 集后自动重写环
  (目前卡片是人工/离线蒸馏,无 accept/reject 门)。
- 但任务三将论证:**这些缺口在当前任务族上不是瓶颈** —— 瓶颈在
  任务族本身没有历史依赖决策点。机制补齐前必须先过任务资格门。

## 五、证据清单

| 系统 | 证据来源 | 核对日期 |
|---|---|---|
| Zetta | github.com/air-embodied-brain/Zetta-Embodiment:zetta/memory/task_memory.py、zetta/evolution/critic.py、robots/libero/role1_recovery.py(contents API 逐文件读) | 2026-10-08 |
| SkillOpt | github.com/microsoft/skillopt:skillopt/engine/trainer.py(ReflACT 六段) | 2026-10-08 |
| EmbodiSkill | github.com/air-embodied-brain/EmbodiSkill:agentkit/skill/embodiskill_skill/EmbodiSkill.py | 2026-10-08 |
| SimpleARM | github.com/simplearm/SimpleARM README(全文)+ arXiv:2609.36595 摘要(WebSearch);代码未发布 | 2026-10-08 |
| Ledger | arXiv 2026-09-28 标题+摘要(WebSearch);无仓库 | 2026-10-08 |
| BATON | arXiv:2608.16889 标题+摘要(WebSearch);无仓库 | 2026-10-08 |

局限声明:arxiv.org 全文在开发机网络下不可达(WebFetch 域拦截、
export 代理空返回),论文级条目的机制描述以摘要与 README 为准,
细节措辞可能低于全文精度;标注 [P] 即为此意,后续决策不应依赖 [P]
条目的机制细节。
