# Embodied Harness 机会资格审计(H0)——HARNESS_OPPORTUNITY_REVIEW

生成:2026-10-09 | 性质:**只读审计**(零 rollout、零环境修改、零训练、Stage R 冻结资产未触碰)
依据:Stage Q/R 终报与预注册、`analysis/memory_s0/REFERENCE_CODE_AUDIT.md`(六系统源码级对照)、
PERSISTENT_EVENTS_INDEX、harness 源码(toolkit.py / env_server.py / tools.py / stageR_rt.py)、
Zetta 项目页全文(arXiv 2608.16590)、SHAPER 出版页(arXiv 2608.11350)、EmbodiSkill / SkillOpt
源码级审计(S0 期内完成)。

证据等级沿用 S0 惯例:**[S]** = 本仓源码级;**[D]** = 本仓实验数据级;**[P]** = 外部论文/项目页级
(未读全文)。

---

## 0. 结论摘要(TL;DR)

**总判定:HOLD——机制类新研究 STOP,测量类主案(方向 1,纯离线)条件 GO。**

1. **最有证据支持的瓶颈不是"缺机制",而是"缺测量"**:RPent 数据显示本栈 outcome 信号存在
   三重缺口——单点性(在线唯一成败信号是 episode 终止单点,看不见"取得后保不住")、
   低信噪比(执行随机性 q≈.30,单次成败对能力/缺陷的证据力弱)、时序结构未定标
   (连败史携带强预测信息但从未被转成可用的证据力曲线)。
2. **机制类路线(recovery / critic / 演化环 / verifier)对本项目 STOP**:RPent 自己的负结果链
   (I0/K/L/M/N/P/Q/R,见 §4.3)+ §36 Hard STOP 冻结条款;且 Zetta/SHAPER 已把
   "闭环 harness 自演化有效"这个命题用同家族 harness 证明到 90.8%(LIBERO-Pro)[P],
   RPent 再做机制属于重复验证,无独立贡献。
3. **RPent 的独立空间在演化信号的测量学**:Zetta Loop3 验证门、SHAPER 冻结模型自任 optimizer、
   SkillOpt held-out 晋升、EmbodiSkill defect/lapse 分流——四个系统都要回答"多少 rollout
   outcome 才够下结论",但都没有给出定量答案。RPent 的 Q/R 数据恰好是回答这个问题的
   现成底物(24 事件 × 16+ 试,双契约逐 trial 布尔序列,CSV 在档、列结构本轮已验)。
4. **主案 = OUTCOME EVIDENCE CALIBRATION(方向 1)**:纯离线、零 env boot、不违 §36
   (不建 controller/classifier,只做统计定标)。三个可证伪假设 H-OE1/2/3 见 §6。
   Headroom 论证与诚实风险(重新表述风险、外推窄)在 §6.5-§6.6 如实呈现。

---

## 1. 审计范围与数据资产盘点

### 1.1 本轮实际读取的材料

| 材料 | 状态 |
|---|---|
| `STAGE_Q_FINAL_REPORT.md` / `analysis/STAGE_R_FINAL_REPORT.md` | 全文 |
| `analysis/stageR_prereg.md` §15(=§36 Hard STOP 原文) | 全文 |
| `analysis/memory_s0/REFERENCE_CODE_AUDIT.md`(六系统对照) | 全文 |
| `PERSISTENT_EVENTS_INDEX.md`(五事件 benchmark 底物) | 全文 |
| `analysis/stageR_same_action_rollouts.csv`(193 行=24 事件×8 试)、`stageR_resample_rollouts.csv`(289 行=24×8+2 事件×4 NATURAL 补充)、`stageR_event_probabilities.csv`(24 事件全字段) | 列结构与统计核验(本轮只读复算) |
| Zetta 项目页(air-embodied-brain.github.io/zetta) | 全文 [P] |
| SHAPER 出版页(microsoft.com/research,arXiv 2608.11350) | 全文 [P] |
| EmbodiSkill / SkillOpt | S0 期源码级 [S](本轮引用 S0 结论) |

### 1.2 磁盘在档的可复用资产

- **双臂逐 trial 序列**:SAME 192/192、RESAMPLE 192/192、NATURAL 96/96(R1 执行账),
  每行含 `stable / acquisition / terminated_in_chunk / chunk_class(EE/contact/obj 三维+
  位移数值)/ cand_sha / recon_sha_match`——即 per-trial 双契约布尔 + 机制特征全在 CSV 里,
  **离线重分析不需要任何新的 env boot**。
- **五事件持久失败底物**:r143/r168/r171/r181/r185(全 t9),16 试(SAME+RESAMPLE)零成功,
  episode_dir / stageR_snapshots / stageR_trace.jsonl 三件全在(2026-10-08 磁盘验证)。
  使用纪律:用作 benchmark 前需新预注册与用户批准(PERSISTENT_EVENTS_INDEX 原条款)。
- **R0 重建资格**:PREFIX 重放 32/32 哈希级一致——任意历史时刻可精确复现(仪器侧)。

### 1.3 本轮补充复算(只读,一行统计)

- 事件类型分布:E_EXECUTION_EPHEMERAL 14/24(58.3%)、P_POLICY_PERSISTENT 5/24(20.8%)、
  U_UNRESOLVED 4/24、A_ACTION_SPECIFIC 1/24。
- **E/P 完美分离**:E 型 14/14 在 16 试内至少一次 stable 成功;P 型 5/5 零成功
  (`strong_persistent` 全真)。P 型 5 个事件 task 全 = 9(t9)。
- SAME 臂 24 事件 × 8 trials 结构完整(无缺行)。

---

## 2. 任务一:执行过程的观测粒度、时序证据、成功稳定性、失败持续性

### 2.1 观测粒度(数据里到底有什么)

**Planner 侧(在线)[S]**:
- 技能边界粒度:每个 primitive call 一次 dump(states.json 一条:EEF pos/quat/gripper_qpos +
  物体名字,无物体坐标);chunk 内部(5 步伺服原子)对 planner 不可见。
- 图像工件:agentview 256 RGB(Pi0 帧与校准帧)、metric depth、world xyz map、wrist 同套、
  1024 hi-res——**视觉粒度是富的**,粒度贫乏的是结构化状态。
- 工具面:SAM3 segment(prompt/point→mask+score)、back_project(row,col→xyz)、
  view_driver_state(回看自己任意步的 states.json 条目)。
- 成败信号:`episode_terminated`(libero 官方 check_success)——**单点、终局、二元**。

**仪器侧(离线)[S]**:rtrace/stageR_rt 的 sim_measurement 逐物体位姿、任意时刻 check_success、
state_hash、chunk_class 机制特征(EE 方向/接触/物体位移数值)。

**判定**:观测粒度呈现"视觉富、结构贫、成败单点"的不对称。E/E 位置与夹爪开度在线可见
(gripper_qpos 是抓握的合法代理),**但"物体是否还在爪中"在线不可直接观测**——这正是
"抓着但已掉/滑"窗口(= 瞬态成功的物理来源)在 planner 视界外的原因。

### 2.2 时序证据(k 曲线与重采样)

- **h(k) 连败坍零 [D]**:同事件连败 3 次后第 4 次尝试成功率 1/17;连败 7 次后第 8 次 0/11。
  对照 iid 基线:若 trials 独立且边际成功率 q≈.30,连败 3 次后第 4 次应仍 ≈.30——实测 ≈.06,
  **显著低于 iid 预测**,即连败史携带超出独立抽样的信息(条件相关:连败事件集中在低 q /
  P 型事件上)。此对比(经验 h(k) vs iid binomial 预测)R 终报**未做过**,是未开发的分析。
- **重采样增益近零 [D]**:q_same mean .302 [.193,.417] vs q_policy .323,配对差 +2.1pp、中位 0;
  t9 上重采样 −4.5pp。即换动作样本不换命,"再试一次"的价值随连败迅速衰减(C_pol(4)=.708
  已是 C_pol(8)=.792 的 89%)。
- **36 次同命令重执行成功 [D]**(Stage Q):14/22 事件(64%)在重复执行中至少一次翻转。

### 2.3 成功稳定性(ACQ vs STABLE gap)

- **TRANSIENT_SUCCESS_REPLICATES SUPPORTED [D]**:ACQ−STABLE gap SAME +34.4pp /
  POLICY +37.5pp(R);Q 四 cell ACQ−STABLE +17~30pp、hold ratio≈0.70。
- 即:**本栈"取得成功"与"保持成功"是两个相距 ~35pp 的量**。用哪个当"成功"会系统性
  改变任何以此为奖励/门槛机制的结论——这是所有 outcome-grounded 机制(演化门、critic
  触发、retry 控制器)共用的隐含自由度,Q/R 之前无人量化它,现在有了双契约逐 trial 数据。

### 2.4 失败持续性(E-A-P-U 谱)

- E 型(瞬态)58.3%:16 试内必现成功(14/14)——**失败是随机的,成功也是随机的**。
- P 型(策略持久)20.8%:16 试零成功(5/5)——**失败是吸收态**。
- 分离判据现成:`strong_persistent`(双臂零成功)。但注意:
  (a) 底物窄——P 型全部集中在 t9(木质柜碗任务),外推受限;
  (b) U 型 4 个事件悬置,分类不完全;
  (c) ONE_SHOT / ACTION_SPECIFIC 判定 INCONCLUSIVE(R)。

---

## 3. 任务二:Planner 合法观测 vs 离线仿真真值(逐条清单)

| 信息 | Planner 在线合法可得? | 通道 [S] |
|---|---|---|
| EEF pos/quat/gripper_qpos(每技能边界) | **是** | states.json 逐条 dump |
| 自己任意历史步的上述状态 | **是** | view_driver_state(step=NN) |
| 物体名字列表(无坐标) | **是** | states.json object_names |
| RGB / depth / world xyz / wrist 图像 | **是** | dump_state 工件全集 |
| 物体实例分割 + 置信分 | **是**(概率性) | SAM3 segment(prompt/point) |
| 像素→3D 反投影 | **是** | back_project |
| 抓握状态代理(夹爪开度+EEF z) | **是**(代理) | gripper_qpos + eef_pos |
| 自己的连续失败次数 k | **是**(可自数) | 会话历史 |
| episode 成败(单点) | **是** | episode_terminated |
| —— 以下为离线/仪器专属 —— | | |
| 逐物体真实位姿/接触 | **否** | sim_measurement(obj_of_interest 防火墙,env_server.py:282-301) |
| 任意时刻 check_success(连续探测) | **否** | CPS 测量序列(Stage Q/R 双契约通道) |
| ACQ vs STABLE 区分 | **否**(在线无保持性探测) | CPS 仪器 |
| BDDL 实例 ID / 目标谓词真值 | **否** | 离线判分 |
| 状态哈希 / 精确恢复 | **否** | state_hash、save/restore(仪器) |

**判定**:ACQ−STABLE gap(~35pp)的**测量**只能离线做(planner 无探测序列);但其**部分物理
代理在线存在**(夹爪开度保持 + EEF z + SAM3 重分割视觉)。也就是说:Zetta 式 retained-grasp
critic 在本栈的输入端原料是合法可得的——被 §36 拦住的不是可行性,是研究优先级(见 §4)。
这个区分本身是重要的审计结论:**"在线不可观测"的是成功契约的仪器测量,不是稳定性的全部
物理证据。**

---

## 4. 任务三:三大现象能否支撑 Outcome-Grounded Harness 研究

### 4.1 逐现象评估

| 现象 | 证据强度 | 对新研究的支撑 |
|---|---|---|
| 临时成功(transient) | 强(SUPPORTED,Q/R 双复现,gap 17~37pp,hold .70) | **支撑"信号质量"研究**:任何以"一次成功"为接受信号的机制在本栈有 ≥1/3 概率接受一个 30 分钟内会掉的成果 |
| 持续失败(persistent) | 中强(SUPPORTED,但 P 型仅 5 事件且全 t9) | 支撑 benchmark 底物(五事件索引在档);不足以支撑跨任务泛化性结论 |
| 执行随机性(stochasticity) | 强(q_same .302、cand-var 0.38-0.88、J0 同 obs 动作差 0.23、36 次重执行成功) | **支撑"证据力定标"研究**:单 rollout 信噪比低到必须回答"几试才够" |

### 4.2 合成判断

三个现象共同指向的研究对象**不是某个新机制**,而是:**"outcome 观测作为演化/决策信号的质量
与证据力"**——即:给定这个栈的随机结构,一次/ k 次 / 连败史 / 宽契约 / 稳契约各自携带多少
证据,何时足以支撑 accept / reject / defect 分流决策。这是 Q/R 数据已被证明能回答、而
机制类研究反而无法回答的问题。

### 4.3 为什么机制类对本项目 STOP(负结果链)

| RPent 阶段 | 结果 | 对应外部机制 |
|---|---|---|
| Stage L | GRAPH EVOLUTION 两轮候选全 REJECT、Gate A 恒等 FAIL | ≈ SkillOpt 候选编辑+晋升 |
| Stage P | P2 verifier 无 headroom(O@8−O@1=10pp<15pp)、sup=100% | ≈ Zetta Loop3 验证门 |
| Stage N | 65% realized、0/144 recovery | ≈ recovery skill |
| Stage M | 盲审双 FAIL(测量无效) | ≈ 人工 critic |
| Stage I0 / K | 资格门 FAIL / 表示层负贡献 | — |
| Stage Q / R | 三效应不过门 / §36 Hard STOP 全表 | — |

加上 §36 冻结条款原文(禁 recovery method / classifier / escalation policy / adaptive retry
controller / FAR / FLARE / Graph / World Model / verifier / Planner redesign / SFT / OPD / RL),
机制类路线在本项目内的合规路径也已关闭(解禁需用户显式批准 + 另立阶段另行预注册)。

---

## 5. 任务四:对照 Zetta / EmbodiSkill / SHAPER / SkillOpt

### 5.1 四系统机制摘要(证据级标注)

**Zetta ζ**(arXiv 2608.16590,清华 AIR)[P-项目页全文;S0 期源码级部分]:
- 三时间尺度闭环:Loop1 Critic-Governed Action Loop(action 频率,代码化 runtime critic 监控
  物理状态,偏离即触发 recovery);Loop2 Candidate Optimization(失败 rollout 按"最早可观测
  分歧"聚类、因果诊断、转成代码空间候选 critic/recovery);Loop3 Validation-Gated Skill
  Update(历史回归 + 严格 held-out 泛化门才入版本化 skill memory)。
- 数字:LIBERO-Pro Goal 90.8%(较冻结 VLA +56.3pt)、RoboCasa 93.6%(+20pt)、11.1× 推理
  加速、20.6× valid rollout 吞吐。
- **直接对口案例**:LIBERO-Pro "Push the plate":Round0 0%(抓起后失稳丢失)→ Critic1
  "retained-grasp" + Recovery1 → 45% → Critic2 "carry-retention" + Recovery2 → 95%。
  **这正是 RPent TRANSIENT_SUCCESS(ACQ−STABLE ~35pp)现象的机制化解法**——Zetta 用
  critic 在线检测 grasp 稳定性,RPent 用 CPS 双契约离线量化了同一现象。
- "Shadow Replay":项目页与 S0 源码审计均未见此术语,疑为论文内部机制,**不作依赖**
  (如后续拿到论文全文再核)。

**SHAPER**(arXiv 2608.11350,MSRA)[P-出版页]:
- train-free,模型冻结,同一冻结模型自任 planner 与 optimizer,通过目标环境 rollout 演化
  reusable skills + context-code harness;评测 VLABench + ESI-Bench;对照 pure execution /
  SFT / test-time-scaling(verifier-free selection、voting)。

**EmbodiSkill**(S0 源码级)[S]:三层图;Skill Defect(技能本身错)与 Execution Lapse
(执行偶发失手)区分分流;版本化手册。

**SkillOpt**(S0 源码级)[S]:ReflACT 六段;EXECUTION_LAPSE 保护区(执行偶发不触发技能
修改);held-out 晋升门。

### 5.2 已有通用机制 vs RPent 可提出的独立贡献

**已被占据的机制席位**(RPent 不必也不应重复):
- 闭环 critic-recovery 演化有效性(Zetta,同 harness 家族,90.8%)
- 冻结模型自优化 skills+harness(SHAPER)
- defect vs lapse 分流规则(EmbodiSkill / SkillOpt)
- 验证门 / held-out 晋升(Zetta Loop3 / SkillOpt;RPent Stage P 已测:本栈 verifier 无 headroom)

**RPent 的独立空间——演化信号的测量学**:
四个系统做机制时都隐含回答"多少 rollout 证据才够下结论"(Zetta 的门、SHAPER 的 optimizer
接受、SkillOpt 的晋升、EmbodiSkill 的分流),但**没有一个给出定量的证据力曲线**:
- 用宽契约(首次取得)还是稳契约(保持)接受,假阳率差多少?——RPent 是唯一有
  ACQ/STABLE 双契约逐 trial 数据的(E 型事件"一次成功"后 stable 率仅 ~.30);
- 连败 k 次携带多少超出现计数的缺陷证据?——h(k) vs iid 基线的偏离从未被定标;
- E/P 分流(= defect/lapse 分流的 RPent 对应物)最小需要几试?——P 型 16 试零成功 vs
  E 型 14/14 有成功,分离所需 n* 可直接从数据估计。
即:**别人回答"机制有效吗",RPent 数据能回答"信号什么时候才可信"**——这是机制工作的
地基,互补而非竞争,且与 §36 零冲突(纯离线统计,不建任何 controller)。

---

## 6. 任务五:最小研究方案、资格门、对照、成本、STOP、Headroom

### 6.1 主案:方向 1 = OUTCOME EVIDENCE CALIBRATION(纯离线)

**最小研究问题(MRQ-OE)**:在执行随机性 q≈.30、ACQ−STABLE gap ~35pp 的栈上,
"k 次 rollout outcome 观测 + 契约选择(ACQ vs STABLE)+ 失败史"对 harness 演化决策
(accept / reject / defect 分流)提供的证据力是多少?

**预注册假设(草案,数值门待 DEV 式校准后冻结)**:
- **H-OE1(契约假阳率)**:以 ACQ 契约单 episode 接受"技能已修复/已掌握"时,对 E 型底物
  的瞬态假阳率 ≥ 30%(由 stable|acq 条件率直接可算);STABLE 契约(首中后全测量点保持)
  将假阳率压到 < 10%,代价是假阴率上升——两曲线交叉点给出契约选择定标。
- **H-OE2(连败证据曲线)**:经验 h(k) 显著低于 iid binomial(q̂) 预测(k≥4 处偏离最大,
  cluster-bootstrap by event),即连败史携带独立信息;"连败 k* 次即判 defect"的最小 k*
  可由后验错误率曲线定标。
- **H-OE3(分流最小证据量)**:E/P 分流所需最小 trial 数 n*,在宽 vs 稳契约下相差 ≥ 2×
  (预期稳契约需要更多试数才能把 E 型的瞬态成分洗出去)。

**必要对照**:
1. 契约对照:ACQ vs STABLE(双契约序列都在 CSV)。
2. 随机源对照:SAME(动作重放)vs POLICY(重采样)——区分执行随机与策略随机下的
   证据力差异。
3. 事件层分层:E(14)/ P(5)/ U(4);P 型单独标注 t9 集中局限。
4. **iid / sham 基线**(方法学关键,从未做过):①iid binomial(q̂ 经验边际)预测曲线;
  ②trial 序列事件内随机打乱(保边际、破时序)——检验 k 的信息是否超出可交换性。
   若经验曲线与 sham 不可分 → k 无时序信息,如实报告(负结果同样入档)。
5. 推断单位:event 级 cluster bootstrap(24 簇,区间会宽,如实报告宽度)。

**资格门(进 DEV 式定标前的 G 门)**:
- G0 数据在档 ✓(本轮盘点 + 列结构核验完成);
- G1 离线复算可行 ✓(CSV 列含 per-trial stable/acquisition/chunk_class,本轮验证);
- G2 底物可复现 ✓(R0 32/32 哈希级,免测);
- G3 外推边界声明:结论限定 FALSE_GRASP@Pi0.5@libero_spatial 族(任务/模型/栈单点),
  论述时不得外推为通用规律——写进报告限制节。

**成本**:纯离线统计。env boot = 0、planner ep = 0、墙钟预计 ≤ 2h CPU、并发 ≤ 4。
新增产物:一个分析脚本 + 一份结果报告 + 预注册文档(含假设/门/STOP 冻结后再跑)。

**STOP 条件**:
- S1:预注册后发现任何需要的字段在 CSV 中缺失且无法从既有 trace 重建 → 停,报告缺口;
- S2:H-OE2 的经验 h(k) 与 iid/sham 基线不可分 **且** H-OE1 两契约证据力曲线不可分
  → 测量学亦无 headroom,STOP(结论:"本栈 outcome 信号在可用粒度下无可定标结构"——
  这本身是对四个外部系统隐含假设的有信息量否定);
- S3:发现任何需要新 rollout 才能回答的分支 → 停在该分支,另行审批。

### 6.2 替代路径

- **方向 2:PERSISTENT_EVENTS benchmark 正式化**(五事件底物 → 公开 benchmark):
  价值明确(唯一已证吸收态失败底物)、成本中等(需新预注册 + 判分文档 + 用户批准;
  底物使用纪律已由 INDEX 预置)。定位:方向 1 的姊妹产物而非竞争——定标曲线上的
  "吸收态端点"就是这五个事件。建议仅在方向 1 出阳性结果后启动。
- **方向 3:在线稳定探测 / verifier 复活**:§36 明确禁止(verifier / adaptive retry /
  classifier 全在禁令表),且 Stage P 已证本栈 verifier 无 headroom。**不推荐**;
  除非用户显式解禁并另立阶段预注册。

### 6.3 与 S1(历史记忆线)的关系

S1(孪生碗历史反事实)与 H0 主案互不冲突、数据面不重叠(S1 用 s1dev 套件,H0 用
stageR CSV);S1-DEV0 处于暂停态、文档全部保留。若两者都获批,建议串行
(S1 已有锁定协议在先)。

### 6.4 Headroom 论证(正反如实)

**支持有 headroom**:
- 数据 100% 在档,零增量采集成本;三个假设全部可证伪、且 H-OE2 的 iid 对照是真空白
  (R 终报报了 h(k) 但未对比 iid 基线);
- 外部对照有明确空白席位(四系统均无证据力定标);
- 负结果也有信息量(S2 的两种停法各自关闭一类后续研究的隐含假设)。

**反对/风险(如实)**:
- **重新表述风险**:hold ratio .70 与 ACQ−STABLE gap 已在 Q/R 报告中,方向 1 的增量
  必须落在"决策错误率框架 + iid/sham 基线 + h(k) 定标"三件新分析上,否则是旧数新说;
- **外推窄**:P 型全 t9、单模型单栈,定标常数是"本栈常数"而非通用常数;
- **n 小**:24 事件 cluster bootstrap 区间宽,H-OE3 的 ≥2× 门可能功效不足——
  预注册时须先做功效自查(与 S1 v2.1 的功效表纪律同款)。

### 6.5 执行前置

方向 1 若获批:先冻结预注册文档(假设/数值门/STOP/分析脚本哈希),再跑分析——
与 S1 v2.1 的"次序锁定防回看"纪律同款。本轮审计不产生任何判定。

---

## 7. 总判定:GO / HOLD / STOP

| 路线 | 判定 | 条件 |
|---|---|---|
| 机制类新研究(recovery/critic/演化环/verifier/在线探测) | **STOP** | §36 冻结 + 负结果链 I0/K/L/M/N/P/Q/R + Zetta/SHAPER 已占机制席位;解禁 = 用户显式批准 + 另立阶段预注册 |
| **方向 1:Outcome Evidence Calibration(离线定标)** | **条件 GO**(总评 HOLD 的构成部分) | 用户批准;预注册冻结(含 S1/S2/S3 停规 + 功效自查)后执行;0 boot |
| 方向 2:五事件 benchmark 正式化 | HOLD(备选) | 方向 1 阳性后另议;需新预注册 |
| 方向 3:在线稳定探测 | 不推荐 | §36 禁 |

**一句话**:RPent 最有证据支持的瓶颈是"outcome 信号的单点性、低信噪比、时序结构未定标";
最有价值的下一步不是再造机制(Zetta/SHAPER 已证明机制有效,RPent 负结果链也已证明本栈
机制无 headroom),而是把 Q/R 数据转成**演化环所需的信号质量定标**——契约选择、连败阈值、
分流最小试数——这是四个外部系统都隐含依赖但没人给出的地基,且零 rollout 成本、与 §36
零冲突。

---

## 附录:数字出典表

| 数字 | 出处 |
|---|---|
| ACQ−STABLE gap SAME +34.4pp / POLICY +37.5pp;hold ratio≈0.70;Q 四 cell gap +17~30pp;36 次重执行成功、14/22 事件≥1 翻转;三效应 +7.8/+4.7/−21.9pp 全 <15pp 门 | STAGE_Q_FINAL_REPORT.md(TEST n=8) |
| q_same .302 [.193,.417] / q_policy .323;配对差 +2.1pp 中位 0;C_pol(k)=.167/.458/.708/.792;h(k) k=4 1/17、k=8 0/11;t9 重采样 −4.5pp;E 14/A 1/P 5/U 4;E 14/14 ≥1 成功、P 5/5 零成功(P 全 t9) | analysis/STAGE_R_FINAL_REPORT.md + stageR_event_probabilities.csv(比例为本轮复算) |
| R0 PREFIX 32/32 哈希级;SAME 192/192、RESAMPLE 192/192、NATURAL 96/96 | stageR_reconstruction_decision.md / R1 执行账 |
| J0 同 obs 动作差 0.23 | Stage J 终报(commit b282445) |
| Stage P O@8−O@1=10pp<15pp、sup=100% | stagep 终报 / stageR_prereg §0 |
| 观测面/防火墙/工具通道 | toolkit.py / env_server.py:282-301 / tools.py [S] |
| Zetta 90.8% / +56.3pt / 三环 / Push-plate 0→45→95% 案例 | Zetta 项目页全文 [P](arXiv 2608.16590) |
| SHAPER 冻结模型自任 planner+optimizer、VLABench/ESI-Bench | Microsoft Research 出版页 [P](arXiv 2608.11350) |
| EmbodiSkill defect/lapse 分流、SkillOpt held-out 门 | analysis/memory_s0/REFERENCE_CODE_AUDIT.md [S] |
