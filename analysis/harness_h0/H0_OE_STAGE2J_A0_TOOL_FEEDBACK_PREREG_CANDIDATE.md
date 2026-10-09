# H0 · Stage 2J — A0 工具反馈可信度审计 · 预注册候选(DRAFT_NOT_FROZEN)

> 2026-10-09 | **研究设计文档;未读取任何 outcome 值;未运行统计/仿真/rollout;未修改任何冻结协议、Runtime 或数据。**
>
> 预注册 ID:`H0-A0-STAGE2J-CANDIDATE-V1` | 状态:**DRAFT_NOT_FROZEN(候选,未冻结,未授权执行)**
> 基线 commit:`84fc36b`(Stage2I 服务器回传审查;结构扫描器 `34a7d91`;全语料资格 Gate `86e863d`;D2 分离 Gate `8d48127`;D2 资产审查 `7d988b0`)。
> 执行 Stage2I SERVER_RETURN_REVIEW §3 **选项 A**(一次性 A0 预注册草案,纯文档)。
> 引用源码均在本基线下行号级复核:`robots/libero/tools.py:201-271`、`robots/libero/toolkit.py:41-110`、`rpent/utils/rtrace.py`、`scripts/stageR_collect.py:112-167`。

## 0. 裁决(先给结论)

**`A0_PREREG_CANDIDATE_DELIVERED / DESIGN_COMPLETE_AS_DOCUMENT / EXECUTION_HOLD_PENDING_AUTHORIZATION / SCIENTIFIC_VALUE_DESCRIPTIVE_ONLY / DEFAULT_RECOMMENDATION_STOP_CLOSURE`**

| 层面 | 裁决 | 理由 |
|---|---|---|
| 设计文档 | **GO**(本文交付) | Stage2H 强制资格定义逐条落地;对象/判据/剥离/缺失/聚类/唯一主指标全冻结于读数前 |
| 执行(含类别支持与字段资格检查) | **HOLD** | Stage2I 选项 B(结果值资格检查)未授权;本文只定义、不执行 |
| 科学价值 | **DESCRIPTIVE_ONLY** | 回顾性同技能判据一致率;单栈单策略;无新估计量/新控制器/新授权消费者 |
| 总体建议 | **STOP 收官为默认** | 除非用户在本轮显式命名一个决策消费者;否则一个描述性定标数字不足以支撑继续(见 §7) |

---

## 1. 固定分析对象(要求 1)

### 1.1 工具侧(被审对象)

**原始 `pi0_pick.result.success` flag**,即 collect 原始 episode `states.json` 中该原语步 `result` 字典的 `success` 布尔原件(tools.py:201-271 运行时计算、`toolkit._step` 原样落盘)。其判定逻辑(源码级,冻结引用):

```
start_z      = pick 入口处 _last_obs_eef_z
descent_done = (start_z − min_z) ≥ 0.10        # 硬编码,tools.py:240
kinematic    = descent_done ∧ (post_min_peak_z − min_z ≥ 0.05) ∧ (grip < 0.06)
success:
  if kinematic:            success=True, break          # 运动学置位(锁存+早停)
  if terminated|truncated: success=episode_terminated, break  # 终局镜像覆盖,tools.py:250-252
```

工具侧消费通道注意事项(继承 Stage2E,写入分析纪律):
- `grip` = `|states[6]|+|states[7]|`(prims 策略观测向量展平,tools.py:151-161),**不是** `obs.robot0_gripper_qpos`(两通道仅 93/484 逐位相等)。本审计只读已落盘 `result` 原件,不重算工具 flag,故此通道仅作背景约束:**禁止**任何"重算 pick flag"的衍生分析混入。
- 本审计不重算、不修正、不平移工具 flag;flag 原样进入 2×2 表。

### 1.2 参考侧(同技能物理 ACQ-like 契约)

**`IN_SKILL_ACQ_AUDIT_V1`**(版本化研究专用名;沿用 Stage2G/2H 命名纪律):
- 计算对象:该次 pick 调用自身的技内测量点序列 = rtrace chunk 前 `meas` 点(按 chunk_idx 顺序)+ `step_end.final_meas`(与 `stageR_collect.stable_fg_check` 同构,stageR_collect.py:145-153);
- 基点 = 序列首点 `pts[0]`;target = `pts[0].obj_of_interest[0]`(stageR_collect.py:158-159);
- 判据 = ∃ 点 p 满足 `_confirms(p, pts[0], target)`(stageR_collect.py:112-124 逐字复用):`dz = pos_z − bpos_z ≥ FG_LIFT_DZ(0.03)` **且** `hypot(pos_x − eef_x, pos_y − eef_y) ≤ FG_FOLLOW_DXY(0.10)`;
- **语义边界(冻结声明)**:这是**技内 concurrent/回顾性**判据,不是"返回后未来保持"标签(Stage2H:final_meas 在原语返回后、无中间动作、Planner 见 flag 前采集);**不等于** Stage Q/R 的 hold-through `STABLE` 契约(Stage2H G-CRITERION FAIL);永不覆盖冻结 ACQ/STABLE 序列。

**`IN_SKILL_ACQ_FGONLY_V1`**(主指标专用变体):同一公式,**删除 `check_success` 旁路**(stageR_collect.py:114-115 那两行),即纯物体位姿物理判据。设立即的必要性见 §3。

### 1.3 明确排除的估计对象(防范围漂移)

| 对象 | 排除理由(Stage2H 表) |
|---|---|
| A1 POST_RETURN_RETENTION | final_meas 与 flag 间无中间动作,不构成"未来保持"检验 |
| B0 OBSERVED_POLICY_FUTURE | vanilla 未来由 Planner 自身重试策略生成 = 策略耦合 |
| B1 FIXED_POLICY_COUNTERFACTUAL | 无固定续作协议,不可识别(Stage2G:D2 合法性与协议固定性不可兼得) |
| pick flag 重算/重建 | `record_trial` 未落盘 flag + chunk 内极值未存档(Stage2E) |

---

## 2. FG 物理参考的字段依赖核查(要求 2a)

`_confirms` 逐字段依赖表(全 [F],行号级):

| 字段 | 出处 | 用途 | 缺失行为 |
|---|---|---|---|
| `pt.check_success` | meas 点 | 旁路:True 直接确认 | 缺省视为 False |
| `pt.obs[f"{target}_pos"]` | meas 点 | 当前物体位姿(x,y,z) | **静默 return False** |
| `base.obs[f"{target}_pos"]` | 基点(pts[0]) | 物体基线位姿(dz 分母) | 同上 |
| `pt.obs["robot0_eef_pos"]` | meas 点 | EEF 位姿(xy 跟随距离) | 同上 |
| `pts[0].obj_of_interest[0]` | 基点 | target 名(构造 `{target}_pos` 键) | 空 → 键不存在 → 静默 False |

**关键缺陷:静默 False 通道**[F](stageR_collect.py:120-121)。collect 的 stable_fg 判定把"字段缺失"与"物理不确认"折叠成同一输出 False。在 Stage R 入组语境这是保守方向;但在 **A0 判别一致率**语境,它是隐性假阴性源:参考侧会因仪器缺字段而"判无取得",与工具 flag 的不一致被误记为工具误报。**处置(冻结):资格检查 B(§4.2)把字段缺失从"静默 False"改判为"排除(REFERENCE_UNCONSTRUCTIBLE / MEAS_POINT_DROPPED)",排除必逐条计数、逐条留 episode/step 索引;禁止把缺字段点当作物理不确认点参与一致率分子分母。**

残余依赖申报 [I]:FG 物理参考与工具 flag 共享 `robot0_eef_pos` 传感器通道(参考用 xy、工具判据用 z 与 grip)。这不是逻辑复用(两构造物理量不同:物体位姿升起+跟随 vs 自体运动学),但作为已知共享输入申报,禁止宣称"完全独立传感器验证"。

---

## 3. Terminal shortcut 循环风险与剥离设计(要求 2b)

**循环的两端**[F]:
- 工具侧:tools.py:250-252 终局支路 `success = episode_terminated` —— flag 直接镜像官方任务谓词;
- 参考侧:`_confirms` 的 `check_success` 旁路(stageR_collect.py:114-115)—— 参考直接消费同一官方任务谓词。

若不剥离,A0 一致率在终局/旁路点退化为"任务谓词 vs 任务谓词"的同义反复,一致性虚高且不携带任何物理校验信息(Stage2I §1.4、Stage2H §2)。

**剥离设计(冻结)**:

1. **逐 pick 层协变量** `TERMINAL_INVOLVED := (result.libero_terminated == True)`(工具返回原件自带该键)。工具侧循环入口 = 终局支路被触发;此协变量在 flag 生成机制层面定义,不依赖参考侧取值,不构成对结果的条件化选择偏倚。
2. **主分析子集(PRIMARY)** := 合格 pick ∧ `TERMINAL_INVOLVED == False`。该子集内工具 flag **只能**来自运动学锁存支路(descent≥0.10 ∧ 回升≥0.05 ∧ grip<0.06),不含任务谓词成分。
   - 已知残余删失申报 [I]:`libero_terminated == False` 的 pick 若因 truncation 提前退出且未达运动学条件,flag=False 仍来自终局支路(镜像值为 False)。此类点保留在 PRIMARY(tool 侧 False 有运动学含义:至退出时刻未达条件),但 `result.episode_truncated` 单独分层伴报,防止把"被截断的未完成"与"完整的抓空"混计。
3. **主指标参考 = `IN_SKILL_ACQ_FGONLY_V1`**(旁路删除版,对**全部**合格 pick 统一计算,不做按点择路)。删除旁路后参考侧不再消费 `check_success`,谓词循环在参考侧关闭。
   - **明确禁止的替代设计**:按 `CONFIRM_SOURCE ∈ {CHECK_SUCCESS, FG_PHYSICS, BOTH}` 逐点分类后只在"纯 FG 点"子集上算主指标 —— 那是以参考侧取值为条件筛选分析集(事后/标签条件化选择),会使一致率估计偏倚。CONFIRM_SOURCE 分解仅作伴报描述(§5.2),永不进主指标分母。
4. 全参考版 `IN_SKILL_ACQ_AUDIT_V1`(含旁路)仍对全部合格 pick 计算并伴报两版差集 = **旁路影响的量化**(这本身是 Stage2I §1.4 悬置问题的一次回答)。

剥离后残余共同依赖:共享物理轨迹(同一执行,这是测量对象本身,非缺陷)+ 共享 EEF 通道(§2 已申报)。**可宣称的上限:主指标是"运动学自体判据 vs 物体位姿判据在同一执行上的判别一致率",不可宣称独立传感器交叉验证或任务级真值符合率。**

---

## 4. 样本资格、episode 聚类、缺失处理(要求 3a)

### 4.1 eligible_episode

- 全部 187 个 ledger 行对应的原始 episode 目录(Stage2I 服务器回传:187/187 双文件、零重复)[F]。
- **不做任何按结局的筛选**:不按 ledger 的 policy_fail/success(97/90)分类过滤 —— 那是 episode 级结局元数据,不是 pick 级资格条件(Stage2H §3 陷阱 2)。
- 1 个无 pick episode:计入样本框描述(`EXCLUDED_NO_PICK`,分母文档化),不进入 pick 级分析,不得记为 infra 失败。

### 4.2 eligible_pick(资格检查 A/B 两级,顺序冻结)

**检查 A(结构,已完成,Stage2I)**:235 次 `pi0_pick` 调用全部具备 result/diagnostics 键、step_begin/step_end 对齐、chunk_idx 连续、逐 chunk meas 键、末端测量键、时间戳非递减 → 235/235 PASS[F]。

**检查 B(字段级,未执行,须授权)** —— 在读任何 `result.success` **取值**之前先跑并先报告:
1. 基点可构造:`pts[0].obj_of_interest[0]` 非空 ∧ `pts[0].obs[f"{target}_pos"]` 存在且三维有限;
2. 曲线可用:该 pick 的技内 meas 点 + final_meas ≥ 2,且**基点之后**至少 1 点具备 `{target}_pos` + `robot0_eef_pos` 有限值(否则参考无法取非平凡值);
3. 检查 B 只读字段存在性与数值有限性,**不读** `result.success`、不读 `check_success`、不算一致率;
4. 检查 B 输出(各级排除计数 + 逐条 episode/step 索引)先于一切 outcome 分析发布并固化;此后任何人不得以检查 B 结果为由调整 §5 指标定义。

### 4.3 缺失处理(零插补,四级分类)

| 类别 | 层级 | 处置 |
|---|---|---|
| `EXCLUDED_NO_PICK` | episode | 样本框文档化(1 例预期)[F] |
| `EXCLUDED_REFERENCE_UNCONSTRUCTIBLE` | pick | 基点不可构造 / 基点后无有效点 → 出局,逐条索引 |
| `MEAS_POINT_DROPPED` | 点 | 单点缺 `{target}_pos` 或 `eef_pos` 或非有限 → 该点从曲线剔除,**不**当"物理不确认"计数(§2 静默 False 处置);pick 保留 |
| `RESULT_FIELDS_MISSING` | pick | 理论可能(结构检查 A 已证 0 例),若出现 → 出局并索引 |

### 4.4 episode 聚类

- 分析单位 = **pick 调用**;186 个含 pick episode、235 次调用(约 1.26/episode)[F]。
- 推断纪律:任何区间/汇总一律以 **episode 为聚类单元的 cluster bootstrap**(重采样 episode、保集内全部 pick;10,000 次;seed=20261009 固定)伴报;禁止把 235 当 235 个独立样本做名义二项区间。
- 伴报表:picks-per-episode 分布、episode 级聚合一致率(每 episode 先聚合再平均,与 pick 级并列对照,报告聚类效应量级)。

### 4.5 样本框申报(外推边界,[F] 采集事实)

3 任务(t3/t5/t9)× seeds 121-190 网格、STABLE_FG_QUOTA=32 配额停止的有界采集过程;非 LIBERO 随机样本。所有数字仅在此样本框内解释;禁止总体 LIBERO 外推。cohort flag 选择偏差(Stage2G:R1 24 事件 = 首 pick 失败 ∧ 全程稳定失败条件化)不影响本设计 —— 本设计用全语料、不条件化 —— 但申报:多 pick episode 的重试 pick 与首 pick 在时序上非独立。

---

## 5. 唯一主要指标与伴报(要求 3b)

### 5.1 唯一主要指标(PRIMARY,一条)

**主子集(PRIMARY = 合格 pick ∧ TERMINAL_INVOLVED==False)上,工具 flag 与 `IN_SKILL_ACQ_FGONLY_V1` 的原始判别一致率:**

```
CONCORDANCE_PRIMARY = n(flag == FGONLY) / n_PRIMARY
```

- 单一、无参数、无阈值选择空间;两版参考中主指标只用 FGONLY(§3.3 冻结);
- 点估计 + Wilson 95% 区间(标称) + episode cluster bootstrap 95% 区间(推荐引用,标 descriptive);
- **无确证性假设检验**:不设 H0、不算 p 值、不做显著性宣称(回顾性单栈定标,Stage2H 纪律)。

**可估性 STOP 门(读数前冻结)**:若 `n_PRIMARY < 30`,或 PRIMARY 内 flag True/False 任一类 `< 10`,或检查 B 后合格 pick `< 100` → 判 `A0_MAIN_UNESTIMABLE`:只发布资格计数与 2×2 伴表,主指标留空,不得以任何子集替代重定义。

### 5.2 伴报(全部 DESCRIPTIVE,永不升级为主)

1. PRIMARY 2×2 表:flag × FGONLY(真阳/假阳/真阴/假阴逐格计数与示例索引);
2. 全合格集(含 TERMINAL_INVOLVED=True)同表,及 `IN_SKILL_ACQ_AUDIT_V1`(含旁路)vs `FGONLY` 的差集 = check_success 旁路影响量化;
3. 分层:task(t3/t5/t9)× pick 次序(首 pick vs 重试 pick)× `episode_truncated` × episode 级 ledger 分类(已发布元数据);
4. 错误解剖索引:每个不一致 pick 给 episode/step/诊断字段(`descent_m/post_min_ascent_m/descent_done/peak_lift_m/min_gripper_opening` 等,result 原件自带),仅索引不解释;
5. CONFIRM_SOURCE 分解(描述性,§3.3 禁入主指标)。

---

## 6. 执行前置与 STOP 规则

**执行顺序(一次性,全部完成后才算 A0 执行完毕)**:
检查 B(字段资格)→ 发布资格计数 → 可估性 STOP 门判定 → (过门)主指标 + 伴报 → 一次性报告。任何一步 FAIL 即停,不留部分重跑空间。

**STOP 规则(预冻结)**:
- S1:检查 B 排除后合格 pick < 100 → `A0_ELIGIBILITY_FAIL_STOP`;
- S2:可估性门不过 → `A0_MAIN_UNESTIMABLE`(§5.1);
- S3:执行中发现需改判据/阈值/子集定义 → 停,发 v2 候选重新审,**不得原地改 V1**;
- S4:任何 runtime/evolution 消费意图出现 → 立即停止并回引 PAEG v0.2.2 I1(离线标签禁入 Runtime)与 Stage R §36。

---

## 7. 科学价值评估(要求 4)

**能回答的问题(上限)**:"在 RPent 这个栈、这 3 个任务、这个策略与样本框内,Planner 收到的 `pick.success` 与同技能物体位姿取得判据的一致率是多少、错在哪个方向。"这量化一个已被源码审计坐实的证据接口错位(Stage2G D2 面发现),属于**工程可靠性定标**。

**不能回答/不提供的(诚实清单)**:
1. 无新统计估计量、无新控制器、无新机制(Zetta/SHAPER 席位论证不变,Stage H0 机会审计结论维持);
2. 无 Runtime/Evolution 决策消费者:**PAEG v0.2.2 I1** 明确离线研究标签不得作为 Runtime `REPORT_FAILURE` 依据;**Stage R §36** 禁止一切恢复/门控/重试类控制器;Evolution Gate 在现规范下对合法 outcome 来源本身处于 QUARANTINE —— 即便 A0 一致率很差,当前规范层也没有任何一个被授权的消费者能据此数字改变任何运行时行为;
3. 无跨栈/跨任务族外推(§4.5);无未来保持语义(§1.3 排除 A1);
4. 类别支持未验证(235 个 flag 的正负分布未知,Stage2I V1 未读)—— 若现实中 flag 几乎全 False(采集语境:quota 按"首 pick 失败"事件驱动,语料整体偏失败侧),主指标可能直接撞 S2 门。

**结论:SCIENTIFIC_VALUE_DESCRIPTIVE_ONLY。** 该数字的用途严格限于:①对已发表的接口错位审计补一个量化注脚;②若未来某天用户要立一个新的证据接口修订提案,可作为其动机节数据。二者都不需要现在执行 —— 文档已把定义冻结,数字随时可按此补算。

## 8. 总裁决(要求 5)

**GO/HOLD/STOP 三层裁决**:

- **设计文档层:GO** —— 本候选满足 Stage2H"强制资格定义"全部七条(eligible_episode/eligible_pick/缺失行为/聚类/provenance join/单一物理构造含精确旁路声明/采集过程与回顾性申报),可在用户批准后直接冻结为 `H0-A0-STAGE2J-FROZEN-V1`(冻结须单独批准,本文不是冻结)。
- **执行层:HOLD** —— 执行需要两个独立授权:①检查 B 的字段级扫描(Stage2I 选项 B 范畴);②outcome 值读取与一次性分析。二者均未授权,本文零执行。
- **战略层:STOP(默认建议)** —— 依用户要求第 5 条明判:本实验**只能**产出一个缺乏决策用途的描述性数字(§7 诚实清单第 2 条:无授权消费者)。**默认建议 = H0 线就此收官**:以 Stage2D 弱信号 + 可辨识性缺口审查 + 2E/2F/2G/2I/2J 文档链作为完整收官证据;本候选文档作为"若未来需要可一键补算的冻结定义"归档。**唯一反转条件**:用户在本轮显式命名一个合法决策消费者(例如:一个未来要单独立项的证据接口修订提案,且该提案明确引用本审计为动机数据)——此时先批准检查 B,再批准执行。

## 9. 合规与不变量

- 本文为纯研究设计文档:零 outcome 值读取(`result.success`/`check_success` 取值一概未读)、零统计、零仿真、零 rollout、零代码改动、零数据触碰;
- 未修改:Stage R 冻结资产与 §36 Hard STOP、Stage2C frozen v1、S1-DEV0 ON_HOLD、E14/A1/P5/U4、PAEG v0.2.2、Runtime/工具接口;
- 既有文档(Stage2I 两份 SERVER_SCAN_NOT_RUN 历史语句等)原样保留,未回写;
- 本文若获冻结,冻结版为独立新文件,V1 候选原文不改。

**最终:`H0_STAGE2J_A0_PREREG_CANDIDATE_DELIVERED / DESIGN_GO_AS_DOCUMENT / EXECUTION_HOLD / SCIENTIFIC_VALUE_DESCRIPTIVE_ONLY / DEFAULT_RECOMMENDATION_H0_CLOSURE`**
