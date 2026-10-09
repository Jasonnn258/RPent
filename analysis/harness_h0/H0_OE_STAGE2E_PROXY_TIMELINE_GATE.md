# H0 · Stage 2E 代理-时间线 Gate:决策时代理 → 未来物理结果的离线可辨识性

> 2026-10-09 | **零统计 Gate(READ-ONLY / STRUCTURE-ONLY)**。
> 基线:RPent `d080e89`(含 `H0_OE_STAGE2E_IDENTIFIABILITY_CRITICAL_REVIEW.md`,
> 本文件直接执行其 §4 提出的五项 Gate)。
> **本轮实际操作**:①对 `robots/libero/tools.py`、`scripts/stageP_rt.py`、
> `scripts/stageQ_rt.py`、`scripts/stageR_rt.py`、`scripts/stageR1_run.py`、
> `scripts/stageO_rt.py` 做行号级复读;②依用户本轮指令("仅做源码与数据结构
> 审查,不读取 outcome 数值")对本地 `analysis/stageR_trial_checkpoints.jsonl`
> (484 记录,gitignore,不在 GitHub)做**纯结构扫描**:只读键名集合、
> `cps` 长度分布、指定条目间的相等性布尔,以及字段存在性;**没有**读取/
> 聚合 `stable/acquisition/check_success` 的任何取值或频次到人读层(唯一
> 涉及 `check_success` 的操作是"同一 trial 内末两个 checkpoint 的该键是否
> 相等"的布尔核对,用于验证 tail 复测冗余,484/484 相等,不构成 outcome
> 统计)。
> **没有**:运行统计/拟合、启动 VLA/仿真/训练、修改冻结协议或 Runtime、
> 解除 Stage R §36 Hard STOP 或 S1-DEV0 暂停。
>
> 三区分标注(全文适用):**[F]** 已验证事实(源码级,或本轮数据级结构扫描);
> **[I]** 理论推断(未经实验检验);**[M]** 尚未具备的数据/条件。

---

## 0. 结论摘要(TL;DR)

**总裁决:`GATE_ITEM1_FAIL_EQUIVALENCE / GATE_ITEM2_PASS_WITH_BOUNDS / GATE_ITEM3_HOLD_CONDITIONAL / GATE_ITEM4_RETROSPECTIVE_FEASIBLE__PROSPECTIVE_NOT_IDENTIFIABLE`。**

1. **执行语义等价性:不成立(且比批判性审查所指更弱)**[F]。`pi0_pick`、
   Stage P `run_continuation`、Stage Q/R 实际调用的 `run_continuation_hold`
   三者在启动位置、下降记忆基准面、descent 门、早停、terminated 镜像五个轴
   上有实质差异(§1 逐轴表)。连 Stage P 自称"与 pi0_pick 逐字同构"的版本
   也存在一个未被其 docstring 承认的差异:candidate chunk 内的下降不进入
   descent 累计(min_z 基准面从 pick 入口换到 candidate-post)。**"从 Stage R
   CPS 重算原始 pi0_pick success flag"不具备判据等价性;且该 flag 在 Stage R
   运行时虽被计算(`rep["pick"]["success"]`)但从未落盘**[F]——重算对象与
   真值双重缺失。唯一合法研究对象必须命名为 `CPS_KINEMATIC_PROXY_CANDIDATE`
   (研究性 2 点退化形态,§3)。
2. **CPS 相对时间线与切点:数据级坐实**[F]。484/484 记录布局 =
   `[base, post, post(重复), cont_1..cont_N, tail(=cont_N 复测)]`;切点 =
   索引 2(candidate-post);严格未来窗 = 索引 3..end,其中有效新时间点为
   cont_1..cont_N(N∈[8,23],每点间隔一个 5 步伺服 chunk),tail 零信息增量
   (484/484 obj/pos/check_success 与 cont_N 全等)。**全部 484 条 trial 的
   未来窗非空**(无任何记录走 terminated_in_chunk 空窗支路,len(cps)≥11)。
   无绝对时钟,时间单位只能是 chunk 序号(相对 H),不能声明"T 秒后"[F]。
3. **合法前缀代理 + 未来-only 标签:结构上可构造,但带三处硬边界**[F/I]。
   切点处合法原料只有 2 个测量点(base、post)的 eef/grip——chunk 内部极值
   未存档,无法复现 pick 判据的 min/peak 聚合,代理只能是 2 点退化形态;
   存档 `grip` 通道与 `obs.robot0_gripper_qpos` 在切点 391/484 不相等
   (两者是不同扁平化来源),重算若用错通道则 0.06 阈值语义即断;冻结
   ACQ/STABLE 的标签序列**包含切点本身**(`cps=[post]+…`),不是未来-only,
   不得复用,须另立新版本研究标签。冻结 STABLE 永不覆盖。
4. **无时间泄漏的离线评价:回顾性=条件可行(本轮零统计,执行须另授权);
   独立泛化=不可辨识(维持)**。同轨迹 ≠ 自动泄漏(接受批判性审查勘误):
   trial 内切点前/后的信息隔离在字段级可强制执行,时间方向在 chunk 序上
   真实成立。但评估隔离(数据已公开、阈值事后选择风险)与域外有效性
   (S_pre 重建 + hold-through 协议特定)两维度不满足;C 类独立未来队列
   仍不存在[ M]。最小可行实验设计见 §5,缺失条件清单见 §5.4。

---

## 1. Gate 第 1 项:执行与返回语义等价性(逐轴判定)

对照对象:在线原语 `pi0_pick`(`robots/libero/tools.py:202-270`)、
Stage P 冻结续跑 `run_continuation`(`scripts/stageP_rt.py:172-210`)、
Stage Q/R 实际调用链 `exec_trial`(`scripts/stageR_rt.py:199`)→
`exec_from_current`(`scripts/stageQ_rt.py:262-302`)→
`run_continuation_hold`(`scripts/stageQ_rt.py:186-221`)。

| 轴 | `pi0_pick`(在线) | Stage P `run_continuation` | Stage Q `run_continuation_hold`(Stage R 实际) | 等价? |
|---|---|---|---|---|
| 启动位置 | pick 入口当前 obs | candidate-post(第 1 chunk 已由 candidate 消耗,docstring 自认) | candidate-post | P/Q 一致;与 pi0_pick 的关系是"拆掉第一块" |
| `start_z`/`min_z` 基准面 | pick 入口 z;min_z 从入口开始累计(含第 1 chunk 的下降) | **candidate-post z;min_z 重初始化**(candidate chunk 内已发生的下降不进入累计) | 同左 | **三个版本两两不同**:candidate 内下降的记忆被丢弃 [F] |
| descent 门(≥0.10m) | 有:`descent_done` 是 success 必要条件 | 有(但基准面已换,见上) | **无**:函数内不存在 descent_done 变量,success 只要 `ascended ∧ closed` [F] | Q vs pi0_pick:FAIL |
| ascent/closed 阈值 | lift 0.05 / closed 0.06 | 同(逐字,常量 `stageP_rt.py:35-37` 注释自证"pi0_pick 默认早停阈值(逐字)") | 同(引用同一组常量) | 阈值等价 [F] |
| 成功早停 | `break` on success | `break` on success | **不 break(hold-through),仅 latch 记录** [F] | FAIL |
| terminated 镜像 | 镜像 episode_terminated | `success = terminated`(覆盖式:截断可把已 latch 的 success 覆写为 False) | `success = success or terminated`(保守式:保留 latch) | P 与 Q 亦互不相同 [F] |
| chunks 记账 | 计自身循环 | `chunks_used = c+1+chunks_already` | 同左 | 等价 [F] |
| 判据消费的观测通道 | `prims._last_obs_eef_z` / `_last_obs_gripper`(policy obs `states` 向量:`states[:3]`=EEF、`|states[6]|+|states[7]|`=指距代理,`tools.py:151-161`) | 同左 | 同左 | 通道等价 [F];但见 §3.1 存档缺口 |
| 返回/落盘 | pick result 返回 Planner(含 success 与技内聚合诊断量) | rep 字典返回 | rep["pick"] 返回**但 `record_trial`(`stageR1_run.py:137-157`)只落盘 `chunks_used` 一个字段;`pick["success"]`、`min/final_gripper_opening` 均未持久化** [F] | 在线可见 ↔ 存档可见:FAIL |

**逐项判定(按批判性审查 §4-1 的轴)**:启动位置 PASS(仅"拆第一块"差异,
属协议设计);min_z 基准面 FAIL;descent 门 FAIL;早停 FAIL;terminated
镜像 FAIL(三版本互异);返回/记录时点 FAIL(flag 未存档)。

**裁定:不存在 source-equivalent 的原工具代理。** 任何离线重算对象都不是
"原始 pi0_pick flag 的复现",而是新定义的运动学代理。这一裁定把批判性审查
的 `PICK_FLAG_EQUIVALENCE_NOT_ESTABLISHED` 从"审查性论断"升级为
"逐轴源码级证据 + 落盘缺失证据"。附带发现:Stage P docstring"与 pi0_pick
的差异仅:第 1 个 chunk 已由 candidate 消耗"**不精确**——min_z 基准面重置
是第二个未被承认的差异 [F];此发现同时影响对未来任何"Stage P 语义=在线
语义"引用的信任度。

---

## 2. Gate 第 2 项:CPS 字段、相对时间线、切点与未来窗(数据级验证)

### 2.1 构造代码(存档布局的来源)

`exec_from_current`(`stageQ_rt.py:262-302`,Stage R 经 `exec_trial` 以
`r_cont=1` 调用):

```text
base = checkpoint()                 → checkpoints_out[0]        (t0,执行 candidate 前)
execute_chunk(actions)              ← candidate chunk(5 步伺服,不产 checkpoint)
post = checkpoint()                 → checkpoints_out[1]        (t1 = 切点)
S_j = save_state()                  (非测量点,供 replicate 重放)
rep 0(唯一 rep):
  restore_state(S_j); cps = [post]                              ← 标签序列起点
  若 terminated_in_chunk:cps.append(checkpoint())               ← 空窗支路(终态复测)
  否则:run_continuation_hold(每 chunk 后 on_chunk→checkpoint)   ← cont_1..cont_N
        循环结束后再 append(checkpoint())                       ← tail
  checkpoints_out.extend(cps)       → 索引 2..N+3
```

**存档布局 [F]**:`[base(0), post(1), post(2)(同一 dict 引用重复 extend),
cont_1(3)..cont_N(2+N), tail(3+N)]`;`len = N+4`(非空窗支路)。

### 2.2 本轮数据级结构扫描结果(484 记录,含 4 条 R0_DEV)

| 检查 | 结果 | 判定 |
|---|---|---|
| 顶层键恒为 `{arm,cps,event_id,trial}` | 484/484 | schema PASS [F] |
| 每个 checkpoint 键恒为 `{check_success,eef,grip,meas,obj,obs,pos,terminated}` | 12,641/12,641(键名级,与 Stage2A §5.1 一致) | PASS [F] |
| `cps[1]` 与 `cps[2]` proprio(eef+grip)逐位相等 | **484/484** | **布局=§2.1 推导,切点=索引 2,数据级坐实** [F] |
| `len(cps)<3`(无法定位切点) | 0 | PASS [F] |
| `len(cps)==4`(terminated_in_chunk 空窗支路) | **0(SAME/RESAMPLE/NATURAL 均为 0)** | **全部存档 trial 的未来窗非空** [F] |
| `cps` 长度 | min 11(NATURAL)/ 17(SAME)/ 18(RESAMPLE),max 27,均值 26.12 | N∈[8,23];max=预算上限(24−1 continuation) [F] |
| 末两个 checkpoint(cont_N 与 tail)obj/pos/check_success 全等 | 484/484 | **tail 是 cont_N 的零步进复测,零信息增量** [F] |
| 切点前(索引 0/1/2)eef/grip/obs.robot0_eef_pos/robot0_gripper_qpos 存在 | 484/484 无缺失 | 代理原料齐 [F] |
| 切点后(索引 3..)obj/pos 存在 | 无缺失 | 未来标签原料齐 [F] |

### 2.3 相对时间线(每 trial)

```text
PREFIX 重放(原始 episode 合法历史,S_pre 重建)
  └─ t0  base(索引 0)          ─┐
       candidate chunk(5 步)     │ 切点前:2 个不同状态(3 个存档条目)
  └─ t1  post(索引 1=2 = 切点)  ─┘ ← 决策时代理的信息上界
       cont_1(索引 3)            ─┐
       cont_2 …                   │ 严格未来窗:N 个新时间点,
       …cont_N(索引 2+N)         │ 每点间隔 = 1 chunk = 5 步伺服
       tail(索引 3+N,冗余)      ─┘ (= cont_N 复测)
删失:仅 (a) continuation 中途 terminated/truncated 触发 break(N<23),
     (b) 预算耗尽(N=23);hold-through 不因成功提前截断
     → 未来窗长度不受"是否已成功"选择 [F]
```

**时间单位裁定 [F]**:chunk 序号是唯一可用时间轴(无绝对时钟,`time_field_
paths=[]` 既有审计 + 本轮验证 cont_N 与 tail 之间零步进)。可声明"H 个
chunk 后";不可声明"T 秒后"。

**跨 trial 边界 [F]**:每 trial 从 S_pre 独立重建(`stageR1_run.py:164-230`,
SAME→RESAMPLE→NATURAL 固定序),trial j 不是 trial j−1 终态的物理延续
→ "未来"只存在于 trial 内,不存在跨 trial 的前缀→后缀时间方向。

---

## 3. Gate 第 3 项:合法前缀代理 / 未来-only 标签的可构造性

### 3.1 代理侧(只用切点前合法非特权信息)

**切点处可得原料 [F]**:索引 0 与 2(base、post)两点的
`eef`(= sim `robot0_eef_pos` 通道,484/484 与 obs 字段逐位同源)、
`grip`(= `prims._last_obs_gripper` 通道,`tools.py:160` 的 `|q6|+|q7|`
指距代理——**正是 pick 判据消费的同一通道**)、以及 obs 内 robot0_*
proprio 子集(与 states.json 合法 dump 同族);obj/pos/check_success 属
特权,禁入代理。

**硬边界 1(2 点信息上界)[F→I]**:chunk 内部(5 步伺服)的 z/grip 极值
未存档;pi0_pick 判据的 min/peak 聚合原则上不可复现。代理只能是 2 点
退化形态,建议形式(预注册时冻结,此处仅示例):
`CPS_KINEMATIC_PROXY_CANDIDATE := (dz = post.eef_z − base.eef_z;
grip_post;可选 terminated@cut)`。在线 Planner 在真实 episode 里本可获得
更富的 pick 返回诊断量(success/min_gripper_opening/…),而 Stage R CSV
只持久化了 `chunks_used`(`stageR1_run.py:149`)[F] → 离线代理是在线
决策时信息的**下界**,任何离线测得的代理质量都不可外推为在线代理质量 [I]。

**硬边界 2(grip 通道陷阱)[F]**:切点处 `grip` 与同 checkpoint 内
`obs["robot0_gripper_qpos"]` 的 `|q0|+|q1|` 逐位相等仅 93/484(391/484
不等)——两者来自不同扁平化来源(prims policy obs `states` vs sim 测量
obs)。**重算必须用 checkpoint 顶层 `grip` 字段**;若误用 obs qpos,0.06
闭合阈值语义即断。

**硬边界 3(z 通道残余风险 R-z)[I]**:冻结判据消费的 z 是 prims
`states[:3][2]`,存档 `eef` 是 sim `robot0_eef_pos`;两者在 robosuite 中
应为同一 EEF site,但 prims `states` 向量未存档,**离线不可验证**逐位
相等。未来协议若做数值重算,须在预注册中登记此残余(影响:潜在常数级
z 偏移,对 0.05/0.10 阈值判据的边界样本有翻转风险)。

**命名纪律 [F,沿用批判性审查 §2.2]**:研究对象只能命名
`CPS_KINEMATIC_PROXY_CANDIDATE`(research-only);禁止"recomputed
pi0_pick flag"/"pick-flag FPR"等命名。

### 3.2 标签侧(只用切点后特权测量)

**冻结 ACQ/STABLE 不是未来-only [F]**:其标签序列
`cps = [post] + own_checkpoints`(`stageQ_rt.py:277-291`)——**包含切点
本身**(索引 2)。ACQ 可因切点处的 FG 契约/`check_success` 直接为真;
STABLE 的 `first_confirm_idx` 可落在切点、且 `any(check_success)` 早放行
支路进一步污染时间语义。→ 复用冻结标签即引入"标签含切点信息"通道,
违反时间方向要求。

**必须另立新标签 [F 纪律 / M 数据操作]**:如
`Y_FUTURE_FG_CONFIRM`(索引 3..N 上任一点满足 FG 契约,以 base 为对照)、
`Y_FUTURE_HOLD`(索引 3..N 上的持续保持窗)。属 B 类特权研究标签,
新版本命名、永不覆盖冻结 STABLE/ACQ 或 Stage2C 统计;其计算=新统计,
本轮零统计未执行。

### 3.3 泄漏防火墙(字段级白名单)

| 面 | 允许 | 禁止 |
|---|---|---|
| 代理输入 | 索引 0/2 的 `eef`,`grip`,`obs.robot0_*` proprio 子集,`terminated@cut` | 一切 `obj`/`pos`/`check_success`;索引 ≥3 的任何字段;跨 trial 字段 |
| 标签输入 | 索引 3..N 的 `obj`/`pos`/`check_success`(特权,研究用) | 切点前(索引 0-2)任何值;冻结 ACQ/STABLE(含切点) |
| 模型/阈值 | 事件级隔离下预注册冻结;不得在评价事件未来数据上调优 | 事后看结果挑阈值/窗口(数据已公开,无法盲测,只能靠预注册+如实标注回顾性) |
| 对象边界 | trial 内相对 chunk 序 | 绝对秒数;跨 trial 前缀→后缀;真实 S_post 连续执行泛化 |

---

## 4. Gate 第 4 项:无时间泄漏离线评价的可辨识性裁决

按批判性审查 §1 的四独立性维度:

| 维度 | 判定 | 证据 |
|---|---|---|
| 信息与算法隔离 | **可满足(条件)** | §3.3 白名单在字段级可程序化强制;代理字段与标签字段在存档中物理分离 [F] |
| 时间方向 | **可满足(限定相对 H)** | 切点=索引 2 数据级坐实;未来窗全非空;hold-through 保证窗长不受成功选择 [F];无绝对时钟 [F] |
| 评估隔离 | **不满足,只能缓解** | 数据/汇总已公开(Stage R 终报、Stage2D),任何阈值选择均事后;事件级聚类+预注册+如实标注"回顾性"是上限,不能伪称 blind TEST [F→纪律] |
| 测量与域外有效性 | **不满足(维持)** | 标签=同轨迹 sim 特权读数;S_pre 重建+PREFIX 重放+hold-through 协议特定;真实 S_post 连续执行、真实机器人、部署分布均在数据外 [F/M] |

**裁决**:

1. **回顾性、同轨迹、时间有序的代理审计(R-T1)= 结构条件已验证
   `RETROSPECTIVE_TIME_ORDERED_PROXY_AUDIT_FEASIBLE`**[F 结构级]。
   本轮把批判性审查的"原则上可能成立"推进到"字段与切点已在数据级核实"。
   执行(任何数值计算)须新预注册+用户授权,本轮零统计维持。
2. **独立泛化验证 = `NOT_IDENTIFIABLE_ON_AUDITED_ASSETS`(维持)**。
   缺失条件见 §5.4;C 类(独立未来队列/绝对时间戳/决策时冻结的代理输出
   落盘)在现有资产中不存在 [M]。
3. **对前份缺口审查勘误的确认**(不改写原文,仅登记):勘误 1(同轨迹
   ≠自动泄漏)与勘误 2(相对 chunk 序可用)被本轮数据级证据支持;
   勘误 3(重算 pick flag 有语义阻断)被 §1 升级为逐轴证据+落盘缺失;
   勘误 4(ACQ/STABLE 非代理精度上下界)接受——它们是嵌套操作契约,
   对在线代理只提供"契约差"描述,不提供精度界;勘误 5(研究价值=NO
   过强)修正为:回顾性结构可行性成立,但**科学增量仍限于一个描述性
   契约差数字**,是否值得执行属用户立项决策(候选 B 修订版,§5)。

---

## 5. 最小可行实验设计(仅设计,不构成预注册,不构成执行授权)

### 5.1 对象与数据

- 数据:本地 `stageR_trial_checkpoints.jsonl` 按 manifest `role=R1_COHORT`
  过滤 → 480 trial(排除 4 条 R0_DEV,沿用 Stage2A §5.2 对账结论);
  事件级单位 24。
- 代理:`CPS_KINEMATIC_PROXY_CANDIDATE`(2 点形态,公式在预注册中冻结,
  建议主形态 `accept := (base_z − post_z ≥ d*) ∧ (grip_post < 0.06)`,
  d* 须在见任何结果前从 {0.10(pi0_pick descent), 0.05(lift)} 中预登记
  选择并冻结;敏感性臂报告另一值)。
- 标签:`Y_FUTURE_FG_CONFIRM` / `Y_FUTURE_HOLD`(§3.2,新版本研究标签)。

### 5.2 分析形态(预注册要素)

- 主问题:切点代理接受 vs 未来-only 标签的条件一致率与差值(描述性,
  事件级聚类 bootstrap 区间如实报宽,沿用 Stage2D 纪律:区间不作确认性
  显著性)。
- 对照臂:①冻结 ACQ(含切点,作为"时间污染对照"显式报告其与
  Y_FUTURE 的差=切点贡献);②STABLE(同上);③事件层 E/P/U 分层;
  ④任务层 t3/t5/t9。
- 删失规则:N(未来窗长)逐 trial 报告;continuation 中途 terminated
  break 的 trial 单列,不删除不填补;零 len==4 记录意味着无需处理
  空窗支路 [F]。
- STOP:字段缺失(本轮已验无缺);R-z 残余导致阈值边界样本翻转且无法
  裁定;任何分支需要新 rollout/env boot;结果只能以
  "S_pre 重建 + hold-through 协议特定的回顾性描述"表述。

### 5.3 可声明 / 不可声明

可:该协议下 2 点运动学代理对未来 sim 特权契约的回顾性条件率。
不可:在线 pick flag 的假阳率(判据不等价+真值未存档,§1);真实
S_post 连续执行泛化;任何 Runtime/Evolution 授权;因果解释。

### 5.4 独立泛化验证的缺失条件(不满足则不通过,不新增假设强行放行)

1. prospective 队列(决策与评价样本分离)[M];
2. 决策时代理输出的当时落盘+绝对时间戳 [M:CSV 无此列,checkpoint 无
   时间字段];
3. 与被验信号不同源的独立 reference(C 类本体)[M];
4. 臂顺序随机化/真实 S_post 连续执行通道 [M:三臂固定序,每 trial 独立
   重建];
5. 盲测条件(数据已公开,只能以"预注册+回顾性标注"缓解,不能消除)[F]。

---

## 6. 五项 Gate 总表(对应批判性审查 §4)

| # | 审查项 | 裁定 | 关键证据 |
|---|---|---|---|
| 1 | `pi0_pick` vs `run_continuation_hold` 逐轴等价 | **FAIL(不等价)** | §1 五轴表;`pick["success"]` 未落盘(`stageR1_run.py:137-157`) |
| 2 | CPS 相对时序/切点/未来窗结构 | **PASS(带边界:相对 chunk 序,无绝对时钟;tail 冗余;无空窗记录)** | §2.2 扫描 484/484 |
| 3 | 泄漏防火墙字段级划定 | **HOLD→可执行(白名单成立;代理=2 点退化;标签须新立)** | §3 |
| 4 | 候选 B 命名与对象修订 | **已修订:对象=`CPS_KINEMATIC_PROXY_CANDIDATE` vs 新未来-only 标签;禁"pick-flag"命名** | §1/§3 |
| 5 | 独立未来队列缺失的明确保留 | **维持 NOT_IDENTIFIABLE(泛化);回顾性=FEASIBLE** | §4/§5.4 |

**STOP 条款(本轮触发与否)**:字段缺失——未触发;阶段对齐不可恢复——
未触发;需凭未来真值构造当前代理——设计上已禁止;无可复核物理 target
窗口——未触发(未来窗全非空);需要新 rollout/训练/runtime 改写——
未触发(§5 设计零 boot)。→ Gate 本体完结,后续任何数值执行=新授权。

---

## 7. 边界与合规声明

1. 本文件为零统计结构审查:未运行统计/拟合/rollout/训练,未改冻结协议、
   原始数据与 Runtime 源码;Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、
   E14/A1/P5/U4、Stage2C frozen v1、Stage2D 结果全部原样。
2. 本地 CPS 结构扫描的授权依据=用户本轮指令("仅做源码与数据结构审查,
   不读取 outcome 数值");扫描脚本与输出留存于 `/workspace/yjx/tmp/
   stage2e_struct_scan*.py`(开发机临时区,不入库);扫描只产生键名/
   长度/相等性布尔,无 outcome 数值进入本文件。
3. 本文件不授权任何后续执行;§5 仅为设计草案。候选 B 修订版的任何启动
   须用户显式批准并另立预注册(次序锁定纪律与 Stage2C/S1 v2.1 同款)。
4. 涉及前份报告的勘误按批判性审查 §5 处理:原文不改写,本文件 §4-3
   登记确认;`H0_OE_IDENTIFIABILITY_GAP_REVIEW.md` 保持为历史审计快照。
