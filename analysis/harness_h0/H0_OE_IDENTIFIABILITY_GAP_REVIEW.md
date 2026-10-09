# H0 · 离线 outcome truth 与 Planner 合法在线观测的可辨识性缺口审查

> 2026-10-09 | **只读研究审查**(READ-ONLY REVIEW,零实验/零统计/零代码改动)。
> 基线:RPent `a764f89`(Stage2D 服务器回传评审收官点)。
> 本文件直接执行 `H0_OE_STAGE2D_SERVER_RESULTS_REVIEW.md` §5 提出的下一研究问题
> (证据资格与可辨识性优先于再拟合一个小样本预测器)。
> **本轮实际操作**:只读复读 harness_h0 既有 Stage1/2A/2B/2C/2D 文档、
> `analysis/harness_next/{METHOD_SPEC,NOVELTY_REVIEW}.md` v0.2.2、
> `DIRECTION1_PREAUTH_REVIEW.md`,并对下列源码做行号级核对:
> `robots/libero/tools.py`(dump_state/pi0_pick/view_driver_state)、
> `robots/libero/toolkit.py`(_step/init_primitives_clean)、
> `robots/libero/env_server.py:277-301`(sim 测量防火墙)、
> `scripts/stageQ_rt.py:223-302`(双契约)、`scripts/stageR1_run.py`(trial 结构)。
> **没有**:读取原始 trial CSV 的 outcome 数值、运行任何统计/拟合、启动 VLA/仿真/
> 训练、修改冻结协议或运行时源码、解除 Stage R §36 Hard STOP 或 S1-DEV0 暂停。
>
> 三区分标注(全文适用):
> **[F]** 已验证事实(本仓源码级 [S] 或已冻结实验数据级 [D]);
> **[I]** 理论推断(由事实推出但未经实验检验);
> **[M]** 尚未具备的数据/条件(当前资产中不存在)。

---

## 0. 结论摘要(TL;DR)

**可辨识性裁决:结构性缺口,非实现疏漏。三层证据对象中,当前 RPent 资产只具备两层。**

1. **合法决策时证据(Planner 在线可见)与仿真研究真值(离线仪器专属)在来源、时刻、
   粒度上三重错位**[F];第三层对象——**独立、时间分离的未来 reference——在现有
   全部数据资产中不存在**[F](Stage2A `NO_INDEPENDENT_REFERENCE_IDENTIFIED`;
   checkpoint 12,641 个对象 `time_field_paths=[]`;`wall_s` 仅耗时非时钟)。
2. **非特权 outcome proxy 存在且合法**(`pi0_pick` 的 success flag = 纯 proprio 代理;
   gripper_qpos+EEF z;SAM3 视觉序列)[F],但它们与离线真值来自**同一仿真轨迹的
   不同投影**,不是独立 reference——因此**无泄漏验证在现有数据上不可构成**[I];
   能合法构成的最近形态是"回顾性代理质量审计"(真值只用于审计),它给出的是描述性
   代理质量,不是时间泛化的预测验证(与 G1 循环定义警告一致,DIRECTION1_PREAUTH
   _REVIEW §2)。
3. **研究价值裁决:现有数据上的下一阶段独立实验价值 = 无(NO)**。Stage2D 已把
   回顾性分析推到其科学边界(`OBSERVED_WEAK_RETROSPECTIVE_SIGNAL /
   SCIENTIFIC_GO_NOT_ESTABLISHED`),继续在同一 24 事件上换对象重分析属边际递减。
   唯一结构完备的新对象需要 **prospective 新采集**[M](决策时冻结代理输出 +
   事后独立测量,时间戳分离),属需用户另授权的 rollout 类。
4. **相对 PAEG/Zetta/CheckVLA 的新增贡献:无新增方法创新**(如实结论)。本审查的
   贡献定位 = RPent 栈特定的**逐字段缺口测绘**(工程/审计贡献)+ 把
   `NOT_IDENTIFIABLE` 边界从"结论句"固化为"可查的来源表"(防未来把回顾性代理
   质量误当无泄漏验证)。"来源可见性 ≠ 统计信息量"原则本身是 PAEG v0.2.2 已声明、
   CheckVLA/VASO 已示范先例的思想(NOVELTY_REVIEW §0.3),非本审查首创。

---

## 1. 三对象区分:审查的分类学基础

用户指令要求区分的三类对象,在本栈的对应物与判定:

| 对象 | 定义 | 本栈对应物 | 存在性 |
|---|---|---|---|
| **A. 合法决策时证据** | 决策时刻物理可得、不依赖特权通道的观测 | states.json 逐技能边界 dump(EEF/quat/gripper_qpos/object_names)、图像工件全集、pick 结果与诊断量、SAM3/back_project、view_driver_state 历史回看、episode_terminated 单点 | **存在** [F] |
| **B. 仿真研究真值** | 事后、特权、只用于离线审计的仪器测量 | sim_measurement 逐物体位姿、任意时刻 check_success、state_hash、STABLE/ACQ 双契约(cps)、chunk_class、recon_sha_match | **存在(仅离线)** [F] |
| **C. 独立未来 reference** | 晚于决策、与被验信号**不同源**、时间戳分离的验证目标 | —— | **不存在** [F](Stage2A 审计 + checkpoint 无时间字段) |

**关键区分 [I]**:B 对 A 的关系是"同一物理过程的不同投影"——可用来**审计** A 的
质量(离线对照),但 A 与 B 的对照不构成"预测验证",因为 B 不是独立抽样的未来,
而是同一轨迹的事后读数。C 的缺失意味着"决策时接受了 X,未来独立地证明 X 错了多
少"这一 OE1b 型问题在现有资产上**不可操作化**。

---

## 2. 字段来源表(核心交付:来源、时间、依赖、可见性)

### 2.1 A 类:Planner 合法决策时证据(在线可见)

| 字段/信号 | 源码来源 | 物理观测时间 | 证据到达时间(决策可用时) | 依赖 | 能证明 / 不能证明 |
|---|---|---|---|---|---|
| `robot0_eef_pos/quat`、`robot0_gripper_qpos` | `tools.py:904-949` dump_state,自 `primitives.env.raw_obs()` 抽取 | 每技能边界(primitive call 返回后) | 同步写 states.json,`view_driver_state(step)` 即时可读 [F] | robosuite 低维状态通道 | EEF 位姿与夹爪开度的**当前值**;不能证明物体在爪中(无物体坐标,源码注释明言 "never privileged object coordinates") [F] |
| `object_names`(无坐标) | 同上 `tools.py:944-948` | 每技能边界 | 同步 | 场景对象表 | 场景里有哪些名字;不含任何空间信息 [F] |
| RGB(agentview 256 policy 帧 / calibration 帧 / wrist / 1024 hi-res)、metric depth、world xyz map(含 wrist 变体) | `tools.py:904` docstring 列举的全部工件 | 每技能边界 | 落盘后经图像路径/segment 工具可用 | 相机标定 + 渲染;wrist 外参逐 step 变化(注释明示) | 视觉富粒度证据;概率性(SAM3)/需自行定位,无结构化真值 [F] |
| **pick 内部 chunk 级 proprio** | `tools.py:152-165`(`_last_obs` 每 chunk 更新)、`:233-234`(pick 循环内读 z/grip) | 每 action chunk 边界(chunk = 5 步伺服原子) | **不直接对 Planner 开放**;聚合成诊断量随 pick 返回值一次性到达 [F] | Pi0.5 帧同步观测 | 聚合后的 `peak_lift_m`/`min_gripper_opening`/`final_gripper_opening`/`chunks_used` 是决策时可见的**技内运动学摘要** [F] |
| **`pi0_pick` success flag** | `tools.py:201-270`:`success :=` 下探≥0.10m ∧ 下探后回升≥`lift_thresh`(0.05m)∧ 夹爪开度<`gripper_closed_thresh`(0.06);`episode_terminated` 时直接镜像 | pick 返回时刻 | pick 返回即达 | 纯 proprio(E_z 序列 + gripper 序列),**不含 sim 真值** | "抓取动作形态上像成功"(L0/L1 混合:工具报告封装单通道代理);**不能证明取得目标物、更不能证明保持**——这正是 ACQ−STABLE ~35pp gap [D] 在线侧的物理来源 [F] |
| `pi0_doubled` success/task_success | `tools.py:264-312` | 技能返回时刻 | 同步 | **只镜像 `libero_terminated`**(spec 明示 "success mirrors official LIBERO task termination only") | 官方终局的镜像,非独立测量 [F] |
| SAM3 `segment`(prompt/point→mask+score)、`back_project`(row,col→xyz) | `rpent/tools/toolkit.py:43-49` 检查类工具注册 | 调用时刻 | 同步 | SAM3 概率模型 + hi-res world map | 概率性视觉定位;score 是模型置信不是物理真值 [F] |
| `view_driver_state(step=NN)` | `tools.py:1604-1650` | 历史任意技能边界 | 调用即达 | states.json 存档 | episode **内**的合法历史回看;跨 episode 不可 [F] |
| `libero_terminated` / `episode_truncated` | `tools.py:1146`(dump 内)、工具返回字段 | episode 终点(单点) | 终点即达 | libero 官方谓词 | **在线唯一的官方成败信号,单点、终局、二元**;窗口内过程(取得后滑落)不可见 [F] |

**A 类时序结构 [F]**:测量点 = 技能边界(states.json 粒度)+ pick 技内 chunk 聚合。
chunk 内部(5 步伺服)对 Planner 不可见。`LiberoToolkit.__init__` 会 dump step 0
(交换前初始态,S1 P1 缺陷的根源,`toolkit.py:117-152`)。

### 2.2 B 类:仿真研究真值(离线仪器专属,`offline_evaluation_only`)

| 字段/信号 | 源码来源 | 测量时刻选择者 | 依赖 | 可见性 | 能证明 |
|---|---|---|---|---|---|
| `sim_measurement()`(逐物体位姿 + obj_of_interest) | `env_server.py:282-301`,docstring 明言"科学仪器,只用于离线结局分类,**绝不进入任何 planner/router 可见文本**" | 调用它的仪器脚本 | robosuite object-state | **仅离线** | 任意时刻逐物体真值位姿 [F] |
| `check_success()`(零步进只读探测) | `env_server.py:277-280` | 仪器脚本 | LIBERO 任务谓词 | **仅离线** | 任意时刻任务谓词真值 [F] |
| `state_hash`/`save_state`/`restore_state` | env_server 快照接口 | 仪器脚本 | 仿真状态序列化 | **仅离线** | 仪器级可复现(PREFIX 32/32 哈希级 [D]) |
| **ACQ 契约**(`acquisition`) | `stageQ_rt.py:223-231`:`_confirms` = `check_success` ∨ FG 契约(目标 z 上升≥FG_LIFT_DZ ∧ 目标跟随 EEF 内 FG_FOLLOW_DXY) | cps 测量点序列(base/chunk 后/每 continuation chunk/终态,`stageQ_rt.py:270-295`) | **特权物体位姿** + check_success | **仅离线** | 测量点序列上出现过一次取得证据 [F] |
| **STABLE 契约**(`stable`) | `stageQ_rt.py:233-258`:首中后尾段全 `_confirms` ∧ ≥HOLD_MIN_POINTS(4);任一点 `check_success` 直接放行 | 同上 | 同上 | **仅离线** | 取得后全程保持(或官方谓词过)——**含 check_success 提前放行支路,不是独立"持续持有"验证**(Stage2A §0-3 已冻结此语义) [F] |
| cps checkpoint(`check_success/eef/grip/meas/obj/obs/pos/terminated`) | `stageQ_rt.py` checkpoint;服务器实测 484 记录/12,641 对象,**一级键与递归 `time_field_paths` 均无时间字段** [F,Stage2A §5.1] | 仪器脚本 | 同上 + raw proprio | **仅离线**(gitignore) | 注意其中 `obs` 的 `robot0_*` 子集(eef_pos/gripper_qpos 等)与 A 类 proprio **同源等价**——即离线存档里含"合法等价 proprio 的仪器采样",但物体位姿/`object-state` 子集是特权 [F] |
| `chunk_class`/`recon_sha_match`/`delta_max` | `stageR1_run.py:141-153` 等 | 仪器 | 仿真测量派生 | 仅离线 | 机制特征/重建一致性;`delta_max` 是仪器一致性非 outcome 正确率 [F] |
| `trial`/`wall_s` | `stageR1_run.py:167-226` | 执行器(固定 SAME→RESAMPLE→NATURAL 顺序) | time.time() 差 | CSV | trial 是臂内序号,**非绝对时间非连续物理状态**;wall_s 是耗时 [F] |

### 2.3 C 类:独立未来 reference —— 逐项排除

| 候选 | 为何不是 C |
|---|---|
| `episode_terminated` | 同一仿真契约(check_success)的终点单点采样——它是 A 类合法信号,但作为"验证决策时代理"的 reference 时与 STABLE 的 `any(check_success)` 放行支路**同源**,不独立 [F] |
| 后续 states.json 条目 | 未来到达时才合法可见(届时它自己就是新的决策时证据),不是**预先固定的** reference;且与代理同轨迹 [I] |
| Stage R 双臂重放的未来 trial | 与前缀同属仪器重建序列、同源 sim 契约、无时间戳、回顾性公开 [F] |
| 人工判读 | [M] 不存在任何已采集的人工时序判读存档 |
| 绝对时间戳/事件时钟 | [F] `time_field_paths=[]`;CSV 无时间列——**连"时间分离"都无法登记**,遑论独立 |

---

## 3. 依赖关系小结(谁从谁派生)

[F] 级依赖链(全部源码可查):

```text
仿真物理状态 σ(t)
 ├─ raw_obs(robosuite 低维+图像)
 │   ├─ states.json dump(eef/quat/gripper/object_names + 图像)──────► A 类
 │   │    └─ pick 循环 chunk 采样(z/grip)──► pick success flag(L0/L1)► A 类
 │   └─ sim_measurement.obs 的 robot0_* 子集 ──────────────────────► B 类存档(与 A 同源)
 ├─ object-state 物体位姿(特权)
 │    └─ _confirms(FG 契约)─┐
 ├─ check_success(特权可随时探测)┴─► acquisition / stable ──────────► B 类
 └─ episode_terminated(终点单点,谓词同 check_success)───────────► A 类(唯一官方成败)
```

**推论 [I]**:A 类最强的抓握代理(pick flag)与 B 类 ACQ/STABLE 的差,不是
"测量误差",而是**判据信息集之差**(proprio 形态 vs 特权物体位姿/谓词)——
ACQ−STABLE gap 是 B 类内部两契约的差 [D],而 pick-flag vs ACQ 的差(在线代理对
离线宽契约的差)**从未测过**[M],这是缺口测绘中唯一尚未量化的格点。

---

## 4. 可辨识性结论

### 4.1 缺口的三重结构 [F→I]

1. **时刻错位**:A 类测量点=技能边界(+pick 内 chunk 聚合);B 类测量点=仪器
   选择的 chunk 边界/终态。两组时刻集合不相等,逐点对照需插值假设 [I]。
2. **粒度错位**:A 类结构性状态贫乏(无物体坐标);B 类物体级真值。在线对
   "物体在爪中"只能代理合取(H0 §3 判定 [S])。
3. **时间方向错位**:A 类永远只有 now 与 episode 内历史;B 类是事后读数;
   **没有任何对象同时满足"晚于决策"+"独立于被验信号"**——C 类缺失。

### 4.2 非特权 outcome proxy 清单与验证可行性

| 代理(全部 A 类合法) | 对应 B 类对象 | 现有数据可回顾性对照? | 构成无泄漏验证? |
|---|---|---|---|
| pick success flag(proprio) | ACQ(宽契约) | **结构上可行但未做过**[M]:cps 含与 A 同源的 `robot0_*` proprio 与 grip/eef,可离线重算"若按 pick 判据会输出什么"并对照同点 ACQ/STABLE——但这属新统计实验,须另授权 | 否:同轨迹事后真值,非独立未来 [I] |
| gripper_qpos 持续闭合 + EEF z 保持 | STABLE(稳契约) | 同上结构可行 [M] | 否,同上 |
| SAM3 分割质心 z 序列 | Lifted/Held | [M] 无逐测量点分割存档(states.json 只有图像,无预计算分割序列) | 否,且概率性 |
| `libero_terminated` | check_success 终点 | 已由 Stage2D OE1a 陪报(同源分歧) [D] | 否:同源 |

**结论**:合法代理存在、回顾性审计通道结构上可开(唯一未量化格点=proxy vs 特权
契约),但"无泄漏验证"要求 prospective 设计(§6),现有数据上**不可构成** [I]。

### 4.3 对 Stage2D 结论的可辨识性重述

Stage2D 的 M0−M1=+0.0129(区间跨 0)是 B 类内部的预测比较;服务器评审已指出
"更好的模拟 Brier 不证明 runtime agent 能合法观测同一前缀、也不证明存在独立未来
reference"。本审查把该论断**落到字段级**:runtime 能合法观测的前缀(states.json
序列)与 Stage2D 消费的前缀(cps 双契约序列)是**两个不同文件、不同测量点、不同
判据**——二者之间没有任何已建立的映射 [M]。因此任何"把 Stage2D 结果往 Runtime
接线"的读法在数据层就没有通道,这不仅缺授权(§5.6/v0.2.2 已禁),也缺**原料** [I]。

---

## 5. 三区分总清单

**已验证事实 [F]**(源码级或冻结数据级,出典见 §2 表):
- A 类信号全集与测量粒度(states.json/dump_state/pick flag 内部判据/内 chunk 聚合);
- B 类真值全集与防火墙(env_server.py:277-301 双通道 docstring 明言离线专属);
- ACQ/STABLE 判据含特权依赖与 check_success 放行支路;
- checkpoint 12,641 对象无时间字段;trial 无绝对时间;三臂固定顺序;
- C 类不存在(Stage2A `NO_INDEPENDENT_REFERENCE_IDENTIFIED`);
- ACQ−STABLE gap SAME +34.4pp/POLICY +37.5pp [D](B 类内部差);
- Stage2D 主结果弱观察信号、科学 GO 未建立 [D]。

**理论推断 [I]**(本审查提出、未经实验):
- pick-flag vs ACQ 差是判据信息集之差,量级可能与 ACQ−STABLE 同阶(证据:二者
  分别失去"特权物体跟随"与"持续性窗口"两个不同信息源,但无数据支持具体数值);
- A/B 测量点错位使逐点对照需要插值假设,回顾性审计的误差下界受此限制;
- prospective 校准误差低于自证校准(§6 H-G2 方向)仅是假设。

**尚未具备的数据 [M]**:
- 决策时代理输出的逐事件落盘(Stage R CSV 无 pick-flag 列;重算需授权);
- 预计算分割序列;人工时序判读;绝对时间戳;跨 episode 合法历史;
- 任何时间分离的独立 reference(=C 类本体);prospective 队列。

---

## 6. 下一阶段若获批:可证伪假设、最小评测、对照、STOP

> 本节仅为设计草案,不构成预注册,不构成执行授权(与 DIRECTION1_PREAUTH
> _REVIEW §4 同纪律)。

### 6.1 候选 B(纯离线,0 boot,结构已备)

- **H-B1(代理-契约差)**:在同批 R1 trial 的 cps 测量点上,按 `pi0_pick` 判据
  重算的代理接受率与 ACQ 接受率之差 ≥ 10pp(可证伪:差 <10pp 则"在线 proprio
  代理已足够接近宽契约",缺口小于预期)。
- **H-B2(代理假阳结构)**:代理接受 ∧ STABLE=0 的条件率 ≥ 20%(即在线代理对
  稳契约的假阳率与 ACQ−STABLE gap 同阶)。
- 最小评测:24 事件 × SAME/RESAMPLE 各 8 trial 的 cps(480 键已在档、结构
  PASS [F]);单位=事件级聚类;无新采集。
- 对照:①ACQ(同信息集上界);②STABLE(稳契约下界);③事件层分层(E/P/U);
  ④任务层(t3/t5/t9)。
- STOP:重算发现 cps 缺 grip/eef 关键字段;判据无法在测量点对齐;任何需要
  新 rollout 的分支;结果只作描述(24 事件、回顾性、区间如实报宽)。

### 6.2 候选 A(prospective,需 rollout 授权,与 §36 的关系=纯测量)

- **H-G1(时间泛化失效)**:决策时代理在 prospective 队列上对 T 秒后独立测量
  (sim 真值,事后审计读取)的校准误差,显著大于对同时刻自证契约的校准误差
  (可证伪:不可分则代理具时间泛化性,缺口被证伪收窄)。
- **H-G2(契约选择的时间代价)**:ACQ 型接受对 T 后 STABLE 型 reference 的
  假阳率 ≥ STABE 型接受的 2×。
- 最小评测:N 个新 episode(功效自查后定,参考 S1 v2.1 纪律);决策时自动落盘
  代理输出+时间戳;决策后固定延迟的仪器测量;事件级聚类;预注册冻结后执行。
- 对照:①自证对照(同契约循环,作为"循环定义基线"显式报告);②多延迟窗口
  (T1<T2);③任务分层;④同时刻特权真值(上界锚)。
- STOP:代理与 reference 无法时间分离(实现层混入);预注册后字段缺失;
  任何在线接线需求(§36);队列选择条件不可声明。

### 6.3 候选 C(不启动)

接受 NOT_IDENTIFIABLE 边界,H0 线以文档收官(本审查 + Stage2D 即终点)。

---

## 7. 相对现有工作的潜在新增贡献(允许无创新,如实)

| 对照工作 | 已占据 | 本审查对象与其关系 | 新增? |
|---|---|---|---|
| **PAEG v0.2.2**(本仓自身) | "来源可见性 ≠ 统计信息量"原则(NOVELTY_REVIEW §0.3-1);§5.6 字段权限分层;I1-I4 接口修复 | 本审查 = 该原则在 RPent 栈的**逐字段实证测绘**(从原则到字段表) | 原则无新;测绘属审计增量 |
| **Zetta** [S-ext] | Loop1 代码化 critic 在线监控物理状态;Loop3 exact McNemar 验证门;unresolved/inconclusive 克制出口 | Zetta 不处理"决策时代理 vs 独立未来真值的校准/可辨识性"——其 critic 合法性来自自定义监控谓词,验证门对象是候选改善 | 本审查的缺口问题在其体系外,但解决它需要的新统计方法=无(Beta-Binomial/校准/交换性思想全为经典) |
| **CheckVLA** [F:HTML] | conformal 校准"第一次不必要干预"概率;**校准/部署 exchangeability 前提的显式声明**;"限定保证对象+有效前提"方法论 | prospective 代理校准(H-G1/G2)在方法学上=CheckVLA exchangeability 思想应用于"持续性证据资格";其 keyframe bank 亦是"跨修复保留进度证据"先例 | 方法无新;对象(持续性 vs 干预)不同但属应用差异 |
| **VASO** [F:HTML] | 物理信号→命题映射保真性问题(作者反例:忽略速度第三维→虚假安全验证) | 本审查 §2 表即"映射保真性"的字段级版本;VASO 已示范该问题意识 | 无新 |
| 经典统计(Beta-Binomial/序贯/稳健先验) | 全部工具 | 见 NOVELTY_REVIEW §7 v0.2.1 让渡清单 | 无新 |

**裁决:无新增方法创新。** 本审查的独立价值限于:(a)RPent 栈的缺口测绘
(内部工程资产);(b)把 NOT_IDENTIFIABLE 从论断固化为可查证的字段级证据
(防未来误用);(c)为候选 A/B 的立项书提供对象定义。三项均不构成可对外
声称的方法学贡献——若候选 A/B 未来获批且出阳性结果,其表述也须按
CheckVLA/VASO 先例收窄为"限定对象+条件保证的应用"。

---

## 8. 研究价值裁决与下一阶段实验候选

**总裁决:现有数据上的独立实验价值 = NO;研究线的文档价值已交付;后续任何实验
均需用户对候选 A/B 单独授权,且预期贡献为栈特定测量学结论(非方法创新)。**

| 候选 | 内容 | 成本 | 前置 | 裁决 |
|---|---|---|---|---|
| **A. prospective 代理验证采集** | H-G1/G2;决策时冻结代理+事后独立测量 | 高(需 env boot/rollout 授权、新预注册) | §36 不涉 controller 实现,但 rollout 本身须批准;功效自查 | **有条件值得**(唯一能填补 C 类缺口、回答"在线代理的时间可信度"的路径);但通用性受限(P 全 t9、单栈) |
| **B. 离线代理-契约差重算** | H-B1/B2;cps 上重算 pick 判据对照 ACQ/STABLE | 低(纯离线 0 boot,480 键结构已 PASS) | 新预注册+批准(本轮 0 统计) | **边际值得**:量化 §3 指出的唯一未测格点;属 Stage2D 延长线,增量=一个 gap 数字 |
| **C. 不启动(收官)** | 接受边界 | 零 | — | **保守合理选项**:缺口已测绘清楚,NOT_IDENTIFIABLE 已固化 |

推荐顺序:C(默认)> B(若用户想要最后一块拼图)> A(仅当用户判断
"在线证据可信度"值得为新采集付费)。三选一由用户决定;本审查不预设。

---

## 9. 边界与合规声明

1. 本文件为只读研究审查:零统计、零 rollout、零运行代码改动、零冻结协议触碰;
   Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、E14/A1/P5/U4 冻结口径全部原样。
2. 引用的 Stage2A/2B/2C/2D 结论不因本审查改写;Stage2D 的弱观察信号与
   `SCIENTIFIC_GO_NOT_ESTABLISHED` 裁决不变。
3. 本文件不授权任何后续执行;候选 A/B 的任何启动须用户显式批准并另立预注册
   (次序锁定防回看纪律与 S1 v2.1/Stage2C 同款)。
4. 涉及外部工作的对照结论核验深度沿袭 NOVELTY_REVIEW v0.2.2 的等级标注
   ([S-ext]/[F:HTML]);未读全文的残余风险登记(R1/R5)继续有效。
