# H0 · Stage 2J-v2 — A0 工具反馈可信度审计 · 预注册候选第二版(DRAFT_NOT_FROZEN)

> 2026-10-09 | **研究设计文档;未读取任何 outcome 值;未运行统计/仿真/rollout;未修改冻结协议、Runtime 或数据。**
>
> 预注册 ID:`H0-A0-STAGE2J-V2-CANDIDATE`(若获批冻结则为 `H0-A0-STAGE2J-FROZEN-V2`)。
> 状态:**DRAFT_NOT_FROZEN**。取代关系:本 v2 解决 Stage2K 独立复审(`2b3710e`)的 B1/B2/B3;**v1 原文(`762bf1a`)保留为历史候选,不改写、不回填**。
> 基线 commit:`4d155b9`。源码行号在本基线复核:`robots/libero/tools.py:228-272`(pick 循环与返回字典)、`:1144-1162`(dump_state step 顶层)、`:1604-1646`(view_driver_state 投影);`robots/libero/toolkit.py:41-110`(_step 顺序);`rpent/utils/rtrace.py`(meas 时机);`scripts/stageR_collect.py:112-124`(_confirms)。

## 0. 相对 v1 的修订总账(逐条对应 Stage2K)

| # | Stage2K 判定 | v1 缺陷 | v2 处置(本节为索引,细节见下文) |
|---|---|---|---|
| B1 | 缺失点在 any-time 判据下制造假负例 | `MEAS_POINT_DROPPED` 允许删点保留 pick,`any(FG)` 存在性判据把 UNKNOWN 错写为 NEGATIVE | §2 三值参考状态机 POSITIVE/NEGATIVE/UNKNOWN + 预定义完整应观测点集 Q + 缺失/非有限分开登记 + 完全案例敏感性表 |
| B2 | `result.episode_truncated` 字段不存在;PRIMARY 纯运动学断言过强 | v1 §3.2/§5.2 写错字段路径;称剔除 libero_terminated 后 flag"只能来自运动学锁存" | §3 截断来源改 states.json step 顶层(源码级)+ 三条对齐断言 + PRIMARY 语义修正(负 flag=退出前未触发锁存,含预算耗尽与截断两条路径)+ 删失负例申报 |
| B3 | raw concordance 被多数类支配,单一数字无决策含义 | v1 唯一主指标为原始一致率 | §5 主交付改为**描述性普查包**(先报 prevalence、全 2×2、双条件风险、常数基线、聚类区间);消费者条件伴报 C1 **现在预登记**(防读数后挑指标);宣称语言冻结 |
| B4 | 无 Runtime 消费者 ≠ 无科学数据集消费者 | v1 将"无消费者"直接用作收官唯一理由 | §7 立项三分解(与 Stage2K §4 对齐):A0 数值默认不执行 / EERD 文档独立 GO / P1 研究设计独立 GO |

继承 v1 不变的部分(仅列,不重复论证):分析对象=原始 `pick.result.success` 原件(禁重算、grip 通道申报)、`IN_SKILL_ACQ_FGONLY_V1` 物理判据(dz≥0.03 ∧ dxy≤0.10,删 check_success 旁路)、A1/B0/B1 排除、terminal shortcut 剥离方向、187 episode 零条件化、episode 聚类、零插补、零确证性检验、配额停止样本框申报、执行仍须双重授权。

## 1. 分析对象(继承 v1,一处措辞修正)

工具侧 = states.json 该原语步 `result.success` 原件。生成机制(源码级,tools.py:230-252):

```
for c in range(max_chunks):           # 预算上限 max_chunks
    ... 每 chunk 更新 min_z/post_min_peak_z/grip ...
    if descent_done ∧ ascended ∧ closed:  success=True; break     # 运动学锁存,:247-249
    if terminated ∨ truncated:            success=terminated;     break     # 终局/截断镜像,:250-252
# 循环自然耗尽 → success 保持 False(预算耗尽路径)
```

返回字典(tools.py:254-272)字段:`name, instruction, success, chunks_used, max_chunks, peak_lift_m, min_gripper_opening, final_gripper_opening, libero_terminated, diagnostics{…}`。**勘误登记[v1→v2]:返回字典不含 `episode_truncated`**;v1 §3.2/§5.2 的 `result.episode_truncated` 写法作废,以本文件 §3 为准。

## 2. B1 修复:三值参考状态机(核心修订)

### 2.1 应观测点集 Q(读数前可定义,不依赖任何 outcome 值)

对每次合格 pick:其技内测量点序列 = rtrace 逐 chunk 前 `meas`(第 k 个 chunk 执行前采集,含 meas_0=进技能前基点)+ `step_end.final_meas`。以 `chunks_used`(返回字典自带)计:

```
Q = {meas_0, meas_1, …, meas_{C−1}, final_meas},  C = chunks_used,  |Q| = C + 1
基点 = meas_0;target = meas_0.obj_of_interest[0]
```

**结构性自检(执行时作为对齐断言 A3,§3.3)**:trace 内该 step 的 chunk meas 记录数 + final_meas 数必须恰为 C+1;不符 → ALIGNMENT_ANOMALY,该 pick 出局并索引(Stage2I 已证 chunk_idx 连续,故该断言不是空转)。

### 2.2 逐点有效性(三分类,分开登记)

对每个点 p ∈ Q,按其角色所需字段判定:
- 基点所需:`obj_of_interest[0]` 非空 ∧ `obs[f"{target}_pos"]` 存在且三维有限;
- 非基点所需:`obs[f"{target}_pos"]` ∧ `obs["robot0_eef_pos"]` 存在且有限(FGONLY 不读 `check_success`);
- 三态:`VALID` / `INVALID_MISSING`(字段缺失)/ `INVALID_NONFINITE`(存在但非有限/畸形)。两类无效分别计数、分别索引。

### 2.3 参考状态机(冻结)

```
reference_state(pick) ∈ {POSITIVE, NEGATIVE, UNKNOWN}

POSITIVE ⇔ 基点 VALID ∧ ∃ p ∈ Q: p VALID ∧ FG(p) 为真
NEGATIVE ⇔ Q 完备(∀ p ∈ Q: p VALID)∧ ¬∃ FG 真
UNKNOWN  ⇔ ¬POSITIVE ∧ ¬NEGATIVE(即:存在无效点且未观察到 FG 真)
```

**不对称性是构造性sound,不是调参选择**:对象是"技内**曾**满足取得"的存在性事件——它在观测时间上是单调的(一旦某有效点确认,后续点缺失不能撤销),故 **POSITIVE 由单个有效真点即可sound判定**;而 NEGATIVE 是全称命题,**任何关键点缺失都使其不可判定**。v1 把删点后的 `any=False` 当 NEGATIVE,正是把不可判定误写为假——本节从语义层修复,而非加补丁。

### 2.4 缺失机制申报与外推禁令

- UNKNOWN 的 episode/pick/时间位置分布必须作为**一等公民数字**单独报告(含 UNKNOWN 率、按 flag 分层的 UNKNOWN 率);
- 缺失机制可能与抓取动力学、仿真状态、仪器错误相关(**不假设 MAR**);完全案例率不得无条件外推到全体;
- 完全案例敏感性表(companion):`any required measurement invalid ⇒ 整 pick 排除` 的严格完全案例口径与三值口径并列报告,差异本身即缺失敏感性的证据。

## 3. B2 修复:截断字段来源、对齐与 PRIMARY 语义

### 3.1 字段来源(源码级)

| 量 | 唯一合法来源 | 产码位置 | 备注 |
|---|---|---|---|
| `libero_terminated`(pick 时刻) | `result.libero_terminated` | tools.py:263 | 随工具返回交付 |
| `episode_truncated`(pick 时刻) | **states.json 该 step 条目顶层** `episode_truncated` | tools.py:1147(dump_state) | result 里没有;join 键 =(episode_id, step_idx) |
| `episode_truncated`(对 Planner 可见性) | view_driver_state 投影 | tools.py:1621 | **截断是在线合法可见协变量**,EERD 归入 online_eligible |

### 3.2 对齐论证与断言[F]

`toolkit._step` 顺序:pick 返回 → `rtrace.end_step`(final_meas,**无环境步**)→ `dump_state`(读 `env.episode_terminated/episode_truncated`)。pick 返回与 dump 之间无任何环境动作,故 states 条目的两旗 = pick 退出时刻的环境两旗。据此三条**执行时强制断言**:
- A1:`result.libero_terminated == states_entry.libero_terminated`(同 step);不符 → ALIGNMENT_ANOMALY;
- A2:states 条目存在且 `command` 与该 pick 匹配(join 完整性);
- A3:|Q| == chunks_used+1(§2.1)。

### 3.3 PRIMARY 重定义(修正 v1 过强断言)

```
OUTCOME_MIRROR := (result.libero_terminated == True)        # 官方成功镜像被触发的 pick
TRUNC_EXIT     := (states_entry.episode_truncated == True)  # 截断退出
PRIMARY := 合格 pick ∧ ¬OUTCOME_MIRROR
```

PRIMARY 内语义(精确,不再宣称"纯运动学"):
- `flag=True` ⇒ 运动学锁存触发(镜像支路只能写 False,不能写真——源码 `success = episode_terminated` 在 ¬OUTCOME_MIRROR 下只能取 False)[F];
- `flag=False` ⇒ **退出时刻前锁存未触发**;退出路径 ∈ {max_chunks 预算耗尽(循环自然结束), 截断镜像(truncated=True 时 success=False)}。
- **删失申报**:TRUNC_EXIT 的 pick 其观测窗被截断缩短 → 其 NEGATIVE 是**删失负例**(=截断前无取得,非全程无取得);TRUNC_EXIT 为强制分层协量;`PRIMARY_UNTRUNCATED`(¬OUTCOME_MIRROR ∧ ¬TRUNC_EXIT)作敏感性子集预登记。
- **主子集选择依据重申**:OUTCOME_MIRROR 是 flag 生成机制侧协变量(终局支路是否可写 True),以其筛选不构成对参考取值的条件化;这与按 CONFIRM_SOURCE(参考侧取值)筛选有本质区别——后者仍然禁止(继承 v1 §3.3)。

## 4. 样本资格、聚类、缺失(v1 继承 + 增补)

继承:187 episode 零条件化(不按 97/90 ledger 分类过滤);1 个无 pick episode 记 `EXCLUDED_NO_PICK`;检查 A(结构 235/235 PASS[F])+ 检查 B(字段级,须授权,先于一切 outcome 读取发布)两级;episode cluster bootstrap(10,000 次,seed=20261009);配额停止样本框(3 任务 × seeds 121-190,STABLE_FG_QUOTA=32)申报;零插补。

增补:
- 缺失分类从 v1 四类改为五类:`EXCLUDED_NO_PICK` / `EXCLUDED_REFERENCE_UNCONSTRUCTIBLE`(基点 INVALID,或 Q 中无任何可评估点)/ `EXCLUDED_ALIGNMENT_ANOMALY`(A1-A3 任一不符)/ `UNKNOWN_CASE`(基点 VALID、部分点 INVALID、未观察到 FG——**保留在册但不进 2×2 主表**,率单独报)/ 点级 INVALID 登记表;
- 检查 B 扩展:除 v1 的字段存在性/有限性外,执行 A1-A3 断言;A1 断言需读 `libero_terminated` 布尔——该读数属**机制协变量**,不属 outcome(flag=success 与参考取值仍不读);此边界写入检查 B 脚本的只读白名单。

## 5. B3 修复:主交付从单一数字改为描述性普查包 + 预登记消费者条件伴报

### 5.1 主交付 = DESCRIPTIVE CENSUS PACKAGE(六件套,缺一不可)

在 PRIMARY 上,按以下**固定报告顺序**:

1. **M0 类别结构先行**:flag=True/False 计数与占比;reference_state ∈ {POSITIVE, NEGATIVE, UNKNOWN} 计数;UNKNOWN 率及其按 flag 分层。**任何一致率数字必须与 M0 同页出现,禁止单独引用**;
2. **M1 全 2×2(+UNKNOWN 列)**:flag × reference_state,逐格计数;UNKNOWN 不折叠进任何格;
3. **M2 双条件风险**(错误结构,比一致率更重要):
   - `R_accept = P(reference ≠ POSITIVE | flag=True, 可判定)`——"接受风险":Planner 收到成功报告时物体并未取得的比例;
   - `R_miss = P(reference = POSITIVE | flag=False, 可判定)`——"漏报风险";
   - 各报两个变体并标注:完全案例版(排 UNKNOWN,假设层:层内缺失不携带信息,申报为 A-MN 假设)+ 下界版(UNKNOWN 计入分母、不记正,=真实风险的下界);
4. **M3 原始一致率 + 常数基线**:raw concordance 与 always-True、always-False 两常数基线一致率并列;附 prevalence-adjusted 描述量(Cohen's κ,标 descriptive);
5. **M4 聚类区间**:episode cluster bootstrap 95%(10k/seed 20261009)用于 M2/M3;
6. **M5 宣称语言冻结**:结论只允许"本样本框内观察到的判据一致性/错误结构",禁止"工具可靠性已验证/已定标"及任何外推。

**多数类问题由此解决**:M0 先行强制暴露 prevalence;M3 一致率永不脱离基线单独出现;M2 给出决策相关的非对称错误结构;任何后续读者想问"flag 该不该信"时,答案在 M2 而非 M3。

### 5.2 消费者条件伴报 C1(现在预登记,防读数后挑指标)

**若**未来 P1 验证时机研究获批(其合法工程输入需求已由 Stage2K §3 指出),则 A0 的决策相关主量 = **PRIMARY 且 flag=True 子集上的 R_accept**(接受风险)。本条作为**预登记的指标切换规则**冻结于读数之前:届时主指标从普查包切换为 R_accept **不需要新预注册**(消费关系与指标已在此锁定),但**禁止**任何其他未在本文件点名的指标事后升级。无消费者出现则普查包即终点,数字归档 EERD-A。

### 5.3 可估性 STOP 门(读数前冻结)

- E1:检查 B 后合格 pick < 100 → `A0_ELIGIBILITY_FAIL_STOP`;
- E2:PRIMARY n < 30,或 flag 任一类 < 10 → `A0_MAIN_UNESTIMABLE`;
- E3:flag=True∩可判定 或 flag=False∩可判定 任一 < 10 → M2 降级为仅报下界版并标 `CENSUS_DEGRADED`;
- E4:执行中需改判据/阈值/子集定义 → 停,发 v3,不得原地改。

### 5.4 构念边界(继承 + 重申)

FGONLY(物体位姿升起+EEF 跟随,共享 EEF 通道)是**研究性代理**,不是夹爪接触、持续保持或任务官方完成的物理 oracle;本审计评估对象固定为"运动学自体判据 vs 物体位姿判据在同一执行上的判别结构",不得漂移为"物理抓取成功误报率"。

## 6. 执行前置与 STOP(继承 v1 §6)

执行顺序:检查 B(含 A1-A3 断言)→ 发布资格计数与 UNKNOWN/无效点登记 → E1-E3 判定 → (过门)普查包 → 一次性报告。S4 不变:任何 runtime/evolution 消费意图出现即停,回引 PAEG v0.2.2 I1 与 §36。

## 7. 价值与立项裁决(对齐 Stage2K B4 三分解)

| 工作 | 裁决 |
|---|---|
| A0 数值执行(检查 B + outcome 读取) | **HOLD,默认不执行**;除非用户为 R_accept 或普查包点名合法消费者(P1 立项是唯一已预见情形,已由 §5.2 锁定切换规则) |
| 本 v2 设计文档 | **DESIGN_COMPLETE**:B1/B2/B3 全部落地;设计层重获"可冻结"资格(冻结与执行各自另行批准) |
| EERD 文档(契约/QA 规范) | 独立 GO(另行交付) |
| P1 研究方案 | 独立 GO(另行交付);闭环实验 HOLD 待全新预注册+授权 |

H0 A0 支线的收官判断不再以"无 Runtime 消费者"为唯一依据(v1 的过窄理由,已修正):数据集/研究设计消费者合法存在;但**是否值得花一次授权去读出这组数字**,仍取决于用户是否要 P1 或 EERD 物化——若都不做,A0 保持未执行归档,证据链完整。

## 8. 合规与不变量

零 outcome 值读取(`success`/`check_success`/参考取值;`libero_terminated` 仅作为机制协变量在**未来授权执行时**进入检查 B 白名单,本轮未读任何私有数据)、零统计、零仿真、零代码改动;Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、Stage2C frozen v1、E14/A1/P5/U4、PAEG v0.2.2 原样;v1 原文不改写;本文件若冻结则另立 FROZEN-V2 新文件。

**最终:`STAGE2J_V2_CANDIDATE_DELIVERED / B1_B2_B3_RESOLVED / DESIGN_FREEZE_ELIGIBLE / EXECUTION_HOLD / CLAIM_LANGUAGE_FROZEN`**
