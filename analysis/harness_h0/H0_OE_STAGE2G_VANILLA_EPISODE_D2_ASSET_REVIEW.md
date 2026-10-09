# H0 · Stage 2G:vanilla Planner 原始 episode 的 D2 决策时评价资产审查

> 2026-10-09 | **只读研究审查(READ-ONLY / STRUCTURE-ONLY,零统计)**。
> 基线:RPent `b4db716`(Stage2F 决策面审查;其对 Stage2E 的三处修正——
> D1 非 Planner 决策面 / N∈[7,23] / 终局删失与结果相关——全部接受并作为
> 本轮前提)。
> **本轮实际操作**:①行号级复读 `scripts/stageR_collect.py`(425 行)、
> `robots/libero/toolkit.py:41-110`(`_step`→`dump_state` 落盘路径)、
> `rpent/utils/rtrace.py`(全部 159 行,三插桩点)、`robots/libero/tools.py`
> (`pi0_pick` 返回字典、`set_obs` 通道);②依用户本轮指令对本地原始
> episode 资产做**纯结构核查**(`stageR_failure_events.jsonl` 的 24 个
> R1 事件 episode 目录 + 已发布 `stageR_collect_ledger.csv` 登记的全部
> episode 目录):只读文件存在性、states.json 条目/键名、step_idx、
> t0 后动作名集合、结果字典键名、trace 的 `t` 键存在性;**没有读取任何
> result 取值**(success/libero_terminated/check_success 等一律未读;
> ledger 的 classify 计数 97/90 引自已冻结发布 CSV 的既有列,非本轮计算)。
> **没有**:运行统计/拟合、启动仿真/VLA/训练、修改冻结协议或 Runtime、
> 解除 Stage R §36 Hard STOP 或 S1-DEV0 暂停。
>
> 三区分标注:**[F]** 已验证事实(源码级或本轮结构扫描);**[I]** 理论推断;
> **[M]** 尚未具备的数据/条件。

---

## 0. 结论摘要(TL;DR)

**总裁决:`VANILLA_EPISODE_D2_ASSETS_COMPLETE / REAL_PICK_VERDICT_ARCHIVED_AT_D2 / COHORT_FLAG_CONSTANT_SELECTION_BIAS_VERIFIED / SKILL_LEVEL_DISCRIMINATION_FEASIBLE_ON_FULL_CORPUS_ONLY / EPISODE_LEVEL_FUTURE_IS_POLICY_COUPLED / REMAINING_INCREMENT_ONE_DESCRIPTIVE_D2_AUDIT / GO_FOR_PREREG_REVIEW_ONLY`。**

1. **真正的 D2(工具返回时刻)决策证据已在原始 episode 中完整存档**[F]。
   collect 阶段每个 vanilla episode 的 `states.json` 逐原语步记录
   `{command, result, elapsed_s, state(robot0_eef_pos/quat/gripper_qpos/
   object_names), task_language, world_map*, libero_terminated,
   episode_truncated}`;其中 `result` 是**原语返回字典原件**——含真实
   `success` flag 与全套技内运动学诊断(`descent_m/post_min_ascent_m/
   descent_done/peak_lift_m/min_gripper_opening/…`,tools.py:250-271)。
   这正是 Stage2F 判为"not evaluable from these CPS"的 D2 面:**在 R1
   重建 CPS 里缺失的东西,在 collect 原始 episode 里本来就有**。
2. **未来观测窗口在全部 24 个事件中存在且为真 Planner 行为**[F]:t0 后
   2-12 个原语步(move_to 76 / set_gripper 30 / **pi0_pick 21(重试)** /
   move_pose 18 / rotate_wrist 7 / release 3,24 事件聚合);17/24 事件
   含 t0 后重试 pick,其 294 个 chunk 全部带特权逐 chunk 测量,21 个
   `final_meas` 齐备;155/155 个 t0 后原语步 post 快照在盘。
3. **绝对时钟存在**[F]:trace 全部 6,979 条记录均带 `t`(wall-clock,
   rtrace `_emit` 统一加戳)——对缺口审查"绝对时间戳在全部资产中不
   存在"的表述构成**限定性勘误**(该结论只对 R1 CPS/CSV 成立;collect
   trace 有钟)。C 类(独立未来 reference)缺失的结论不变:钟解决
   "时间分离可登记",不解决"独立性"。
4. **入组选择偏差坐实**[F→I]:24 事件入组条件 =(首个 pi0_pick
   `success=False`)∧(特权验证的技能全程稳定失败)∧(t0≥2)→
   **cohort 内 t0 决策时 flag 恒为 False、同技能特权真值恒为"无取得"**
   ——工具成功判别评估在 cohort 内自由度为零,只能在**非条件化全语料**
   (187 集,含 90 个 success 集)上做;cohort 本身只支持失败恢复/持续性
   评估,而后者在 vanilla episode 里的"未来"由 Planner 自身策略生成,
   是**策略耦合**估计对象。
5. **剩余科学增量 = 一个**:在 187 集全语料上,真实返回 flag(及诊断量)
   对同技能特权契约(ACQ/STABLE 型)的判别一致性审计——零 boot、纯离线、
   双类俱全、无需任何重建或代理退化(优于 Stage2E 候选 B 的 2 点 D1 代理
   形态)。若用户判断单个描述性定标数字不值得另立预注册,则 H0 以收官
   结束同样成立(§5.3)。

---

## 1. 源码证据:collect 机制与三份资产的生成语义

### 1.1 collect 流程(`scripts/stageR_collect.py`)

- 冻结网格 task∈{3,5,9} × seed 121-190 跑 **vanilla Full Planner
  episode**(子进程注入 `RPENT_STAGE_R_TRACE=1`,`run_cell`@235-275,
  与 stageO_collect 同构);账本 `analysis/stageR_collect_ledger.csv`
  (断点续跑,infra 重试 ≤3)。
- episode 结束后确定性入组判定(`judge_episode`@201-230,零 LLM、
  零结果条件化):
  - **a)** 首个失败事件(FG∪RPS 取最早)= FALSE_GRASP 且 t0≥2:
    FG = states.json 中**首个 `pi0_pick` 且 `result.success is False`**
    (`detect_first_events`@72-91);RPS = 首个 `release` 且
    `libero_terminated False`;
  - **b)** 稳定失败契约:t0 技能全部测量点无一满足 acquisition
    (`stable_fg_check`@127-167,测量曲线 = 逐 chunk 前 meas + 技能末
    final_meas,基准=技能首点;`_confirms`@112-124 与 stageQ_rt 同式);
  - **c)** provenance:t0 pre/post 快照 + 1..t0-1 动作流 + t0 首 chunk
    (a_fail)逐位可解码(`provenance_check`@170-198)。

### 1.2 states.json = D2 面的完整合法存档(`toolkit.py:60-110`)

`_step`:Planner 调原语 → `result = primitives.<name>(**kwargs)` →
`dump_state(..., log={"command", "result", "elapsed_s"})`(tools.py
:904-949)→ `view_driver_state(step_idx)` 作为返回给 Planner 的状态视图。
因此 states.json 每个原语步条目 = **Planner 当时合法可见的全部决策证据**:

| 层 | 字段(本轮 275 条目键名联合,[F]) | 性质 |
|---|---|---|
| 工具返回 | `command`, `result`(原件 dict), `elapsed_s` | **D2 合法**;pick 的 result 含 `success/chunks_used/peak_lift_m/min_gripper_opening/final_gripper_opening/libero_terminated/diagnostics{start_eef_z,peak_eef_z,min_eef_z,post_min_peak_z,descent_m,post_min_ascent_m,descent_done,lift_thresh,gripper_closed_thresh}`(tools.py:250-271;本轮 24 事件 t0 条目键名核对一致 [F]) |
| 状态 | `state`{`robot0_eef_pos`,`robot0_eef_quat`,`robot0_gripper_qpos`,`object_names`}, `task_language`, `world_map*`, `wrist_world_map*` | A 类合法(无特权物体坐标) |
| 终局 | `libero_terminated`, `episode_truncated` | A 类合法单点 |

检查类工具(view_driver_state/segment/back_project)不经 `_step`、不落
states.json([F],注册表 toolkit.py:47-58)→ **states.json 的步全是推动
环境的原语步**,step 计数即 Planner 的有效动作序列。

### 1.3 rtrace = 全程特权审计通道 + 绝对时钟(`rpent/utils/rtrace.py`)

三插桩点(零语义改动,自守卫):
1. 技能边界:pre/post MuJoCo 快照 + `step_begin/step_end` 标记;step_end
   对**所有**技能记 `success` 布尔,pick 类(pi0_pick/pi0_doubled)附
   `final_meas`(sim_measurement obs + obj_of_interest + check_success,
   :118-135);
2. 动作咽喉:全部 step/chunk 动作 b64 逐位落盘(:138-158);
3. pick 逐 chunk meas:chunk k 的 meas 反映 chunk k 执行前状态,与
   final_meas 构成完整测量曲线(:139-143)——**这正是入组契约 b 消费的
   同一条曲线**;
4. **`_emit` 对每条记录统一加 `t = time.time()`**(:72-75)——绝对
   wall-clock 时钟,[F] 本轮 6,979/6,979 条记录带 t。

### 1.4 与 Stage2E/2F 对象的关系

| 资产 | 决策面 | 真实 flag | 未来窗 | 特权标签 | 绝对钟 |
|---|---|---|---|---|---|
| R1 重建 CPS(Stage2E 审计对象) | D1(candidate-post,实验内) | ✗(未落盘) | hold-through 固定协议 | ✓(cps) | ✗ |
| **collect 原始 episode(本轮对象)** | **D2(原语返回)** | **✓(result 原件)** | **Planner 自然行为 2-12 步** | **✓(rtrace meas)** | **✓(t)** |

两份资产**互补而非替代**:R1 给"固定协议下的物理持续性"(但只有 D1);
原始 episode 给"真实 D2 证据 + 自然史未来"(但未来是策略耦合的,§4.2)。

---

## 2. 已有数据资格(本轮结构核查,零 outcome 读取)

### 2.1 24 个 R1 事件的原始 episode(样本资格)

| 检查 | 结果 |
|---|---|
| episode_dir / states.json / stageR_trace.jsonl / stageR_snapshots 存在 | **24/24 全在,零缺失** [F] |
| states.json 条目 | 275 条;251 条含 command(原语步),24 条为 step-0 初始 dump(每集 1 条,S1 P1 已知现象) [F] |
| t0(已发布 manifest) | min=2,max=6 [F] |
| **t0 后原语步数** | **每事件 2-12 步,无零步事件** [F];分布 {2:1, 3:2, 4:2, 5:4, 6:3, 7:4, 8:3, 9:3, 10:1, 12:1} |
| t0 后动作构成(24 事件聚合) | move_to 76, set_gripper 30, **pi0_pick 21**, move_pose 18, rotate_wrist 7, release 3 [F] |
| 含 ≥1 次 t0 后重试 pick 的事件 | **17/24** [F] |
| t0 后 pick 的特权测量 | 294 chunk 全带 meas;21 个 step_end 带 final_meas(=21 次重试 pick 一一对应) [F] |
| t0 后原语步 post 快照在盘 | 155/155 [F] |
| trace `t` 键 | 6,979/6,979 [F] |

### 2.2 非条件化全语料(判别评估的采样框架)

`stageR_collect_ledger.csv`(已冻结发布)登记 **187 个 episode_dir,
187/187 在盘** [F];classify 列既有计数:policy_fail 97 / success 90
(引自已发布 CSV,非本轮 outcome 计算)[F]。→ **两类俱全,success=False
条件化只作用于 24 事件 cohort 的选取,不作用于语料本身**。

---

## 3. `success=False` 入组造成的标签选择偏差(重点 3)

### 3.1 偏差的精确结构 [F→I]

入组三条件在 cohort 内造成的常数化:

| 量 | cohort 内取值 | 原因 |
|---|---|---|
| t0 决策时 pick flag(`result.success`) | **恒 False** | 条件 a 直接定义 |
| t0 技能特权真值(ACQ 型) | **恒 无取得** | 条件 b(稳定失败契约) |
| t0 位置 | ≥2 且为首个失败 | 条件 a |

推论:任何"决策时信号判别同一技能物理成败"的评估在 cohort 内
**自由度为零**(2×2 表两列全空);可估计的只剩"t0 证据 → 未来"型的
条件量。这不是缺陷而是设计——Stage R 要的就是干净失败队列——但它把
cohort 的用途**限制**在失败恢复/持续性评估,且要求未来标签只能来自
t0 之后(§4.2 的策略耦合限制随之而来)。

### 3.2 两类评估的区分(必须分开命名)

| 评估类型 | 问题 | 所需数据 | 现有资产支持? |
|---|---|---|---|
| **A. 工具成功判别评估**(tool-verdict discrimination) | 决策时返回的 flag/诊断量与同技能特权契约(ACQ/STABLE 型)的一致率、错误解剖 | **双类**(flag 真/假都要有)、单位=pick 调用、episode 聚类 | **仅全语料 187 集支持**(2.2);cohort 不支持(§3.1)。零 boot、纯离线、无需重建——**这是缺口审查"唯一未量化格点"在真实 D2 面上的形态** |
| **B. 失败恢复评估**(failure-recovery / persistence) | 给定 t0 已验证失败,决策时证据能否预测未来恢复/持续失败 | cohort(24 事件)+ t0 后未来标签 | 结构上支持(2.1 未来窗全存在),但见 §4.2:**vanilla 未来是策略耦合的**;固定协议下的物理持续性已由 R1 覆盖(其代价是 D1) |

混用两者的典型错误:在 cohort 上报"flag 无预测力"(它方差为零)或在
全语料上报"持续失败率"(被 success 集稀释)。任何未来预注册必须先声明
评估类型与采样框架。

---

## 4. 可辨识性结论(重点 4)

### 4.1 技能级判别(类型 A):结构条件完备,`FEASIBLE_OFFLINE`

- 决策时侧(合法):`result` 原件(flag + 诊断量)+ `state` proprio,
  187 集逐 pick 调用可得 [F];
- 标签侧(特权,研究用):同一技能的 rtrace 测量曲线(逐 chunk meas +
  final_meas)→ 按 `_confirms` 同式重算 ACQ/STABLE 型确认 [F,collect
  已在入组判定中消费同一曲线,证明曲线可用];
- 时间语义:同技能内,标签曲线终点的 `t` 晚于 pick 返回时刻
  (`elapsed_s`/step_end 的 t)[F];非"决策时已可读"——flag 产生于
  pick 返回,曲线确认含技能内更晚时点,方向合法 [I];
- 缺失:无(数据齐)。阻断仅在授权层:**本轮零统计,任何数值执行须新
  预注册 + 用户批准** [纪律]。
- 边界:测量点粒度 = chunk 边界(与 CPS 同),chunk 内极值仍不可见
  ——但**诊断量本身(descent_m/peak_lift_m 等)是 pick 内部逐 chunk
  采样的合法聚合**,已在 result 里 [F] → 无 Stage2E 的"2 点退化"问题。

### 4.2 事件级未来评价(类型 B):`POLICY_COUPLED`,只支持自然史解释

vanilla episode 的 t0 后窗口内容由 Planner 自身策略生成:它看到 t0 的
失败证据(与代理同源)、调记忆、决定重试(move_to/set_gripper/
pi0_pick 21 次)——**未来结局 = 物理持续性 × Planner 恢复策略的复合**
[I]。因此:
- 可辨识的对象:"在部署策略下的 episode 自然史结局"(对 PAEG Runtime
  可用性叙事有价值);
- 不可辨识的对象:"t0 证据 → 物理持续性"的解耦估计——这恰是 R1 固定
  协议(SAME/RESAMPLE/NATURAL + hold-through)的设计目的,R1 已做且
  §36 已冻结;
- **D2 合法性与协议固定性在现有两份资产中不可兼得**[F 结构性]:
  要两者兼得需前瞻采集(在 D2 时刻冻结决策证据落盘 + 从该点执行冻结
  续跑协议)= Stage2F Priority 3 的 D2 instrumented cohort,须 rollout
  授权 [M]。

### 4.3 对既有结论的修订登记(不改写原文)

| 既有表述 | 本轮修订 | 性质 |
|---|---|---|
| 缺口审查 §2.3:"绝对时间戳/事件时钟 [F] 不存在(C 类排除行)" | **限定**:R1 CPS/CSV 无钟成立;collect trace 6,979 条全带 `t`。"时间分离无法登记"只对 R1 资产成立;C 类缺失的真正理由是**独立性**(同轨迹仪器记录),不是无钟 | 限定性勘误 |
| Stage2F §1 D2 行:"currently no matched successor labels / exact return flags in the audited Stage R assets" | **成立但范围扩展**:其审计对象是 R1 CPS;collect 原始 episode(在盘、24/24+187/187)有 return 原件 + 后继窗 | 范围补充 |
| Stage2E 候选 B(2 点 D1 代理 vs 新未来标签) | **被本轮替代**:全语料上的真实 flag 判别审计(§4.1)在合法性、双类性、零退化上全面优于 2 点代理形态;D1 对象按 Stage2F 建议归档 | 对象升级 |

---

## 5. 下一阶段裁决(重点 4/5)

### 5.1 最少补充数据

- **类型 A(判别审计)**:**零补充**——187 集全在盘、双类俱全、字段齐
  [F]。唯一前置 = 新预注册 + 授权(零统计纪律)。
- **类型 B(解耦的 D2 物理评价)**:需前瞻 D2 instrumented cohort(决策
  时冻结证据 + 冻结续跑协议 + 独立队列)[M],rollout 级授权,§36 之下
  不启动。
- **prospective 独立验证(C 类)**:维持缺失清单(缺口审查 §5.4 五条)
  不变。

### 5.2 剩余科学增量的如实评估

唯一具名增量 = **类型 A 的一个描述性定标数字族**:真实返回 flag(及
诊断量)对特权契约的一致率与错误解剖,全语料、回顾性、单栈单策略。
- 它回答 PAEG §5.6 一直悬置的实证问题:"Planner 唯一在线成败信号在
  物理上到底意味着什么"(预期与 ACQ−STABLE ~35pp 缺口同阶或更大 [I],
  方向未知);
- 它**不是**方法创新(校准/一致性思想为 CheckVLA 等先例占据),不是
  因果证据,不支持任何 Runtime 接线;
- 先验风险:187 集/3 任务/1 策略,结论窄;且数据已公开,只能回顾性。

### 5.3 GO/HOLD/STOP

| 选项 | 内容 | 裁决 |
|---|---|---|
| **GO_FOR_PREREG_REVIEW_ONLY(唯一实验候选 D2-AUDIT)** | 全语料真实 flag vs 特权契约判别审计;零 boot;单位=pick 调用、episode 聚类;双类;预注册先行 | **结构资格 PASS**;是否立项=用户判断"单个定标数字是否值得" |
| **HOLD** | 前瞻 D2 instrumented cohort(类型 B 解耦)/prospective C 类 | 维持:须 rollout 授权,§36 之下不启动 |
| **STOP(收官)** | H0 线以 Stage2D+缺口审查+2E/2F/2G 文档链收官 | **合理选项**:若用户判 D2-AUDIT 增量不足,收官有完整证据链支撑 |

**本轮 STOP 条款触发检查**:字段缺失——未触发;结构不完整——未触发
(24/24+187/187);需要 rollout——未触发(设计零 boot);需要读
outcome——已避免。→ 审查完结,无强制阻断。

---

## 6. 边界与合规声明

1. 本文件为只读结构审查:零统计、零 rollout、零 Runtime/冻结协议改动;
   Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、E14/A1/P5/U4、Stage2C v1、
   Stage2D 结果原样。
2. 本轮扫描授权依据 = 用户指令("只读核查……不读取 outcome 数值");
   扫描只产生存在性/键名/计数/动作名聚合,无任何 result 取值进入本文件;
   ledger classify 计数引自已发布冻结 CSV。
3. 本文件不授权任何后续执行;D2-AUDIT 的任何启动须用户显式批准并另立
   预注册(次序锁定纪律与 Stage2C/S1 v2.1 同款)。
4. 对既有文档的修订按 §4.3 登记,原文均不改写(Stage2E/2F/缺口审查
   保持历史快照)。
