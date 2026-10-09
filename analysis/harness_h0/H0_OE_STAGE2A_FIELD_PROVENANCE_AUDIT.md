# H0 Direction 1 · Stage 2A 字段、来源、顺序与权限审计

> 日期：2026-10-09 | **用户已明确批准 Stage 2A：只读字段审计与未冻结预注册草案**。
> **审计基线** RPent `cd45de662f2b43e645f0c240cf4033aee9b55000`；已有 Stage 1 三文档与 `DIRECTION1_PREAUTH_REVIEW.md`。
> **实际执行的唯一数据操作**：从 GitHub 研究分支只读获取 Stage R 的 CSV/JSONL，解析**列头、结构键、行宽、事件/臂/试次唯一性、必要字段是否为空及键级对齐**；交叉阅读生成脚本与 `.gitignore`。**没有统计 stable/acquisition 的成功数、经验率、模型参数、效果对照、显著性或任何新结果估计**；没有写/执行分析脚本、改动原 CSV/实验程序、启动环境/rollout。
> **审计可见性**：GitHub 上有跟踪的原始 trial CSV 与索引文件；`analysis/stageR_trial_checkpoints.jsonl` 被忽略、未在该 GitHub 目录中，因此本审计**无法声明本地 checkpoint 的时间/独立真值已经通过核对**。服务器本地是否有完整文件需要另行只读确认。

## 0. 最重要的阶段判断

**远端结构审计：PASS；Outcome 来源审计：PASS WITH LIMITATIONS；独立时间/参考与 Runtime/Evolution 合法性：HOLD。**

源头代码已经明确证明：

1. 同一 trial 的 `acquisition`、`stable` **由相同的仿真 checkpoint 序列生成**，都依赖 `rt.measure()→env.sim_measurement()+env.check_success()`（非独立在线物理传感器）。
2. `stable(cps,base,target)=True ⇒ acquisition(cps,base,target)=True` 是源代码逻辑蕴含（`stable` 首先要求 `first_confirm_idx` 非空）。故在这套冻结代码/同序列前提下 `E[A-Y]=P(A=1,Y=0)`，属于**形式恒等关系而非新统计发现**。
3. `stable=True` 存在 `any(check_success)` **提前放行支路**，并不每次都强制 `HOLD_MIN_POINTS=4` 的持续窗口；它仍是**Stage Q/R 冻结的 STABLE_RECOVERY 操作契约**，不得偷偷改写成“外部独立验证持续持有”。旧 Stage R 结果不作重新解释或修改。
4. `trial` 是每个事件/臂内 `1..K` 的执行编号。执行器**固定 SAME → RESAMPLE → NATURAL**，没有绝对 wall-clock 时间戳列或臂顺序随机化。前缀→后缀（OE3）可以定义**历史实验序号上的回顾预测问题**，但不能从 `trial` 序号证明机器人连续失败使物理状态演化，也不应未经审查声称 M2 顺序因果可辨识。

## 1. 只读结构审计表（仅 schema + completeness，非 outcome 统计）

| Github 文件 | 原始字段/schema | 结构检查 | 状态 |
|---|---|---|---|
| `analysis/stageR_same_action_rollouts.csv` | 16 列：`event_id,task,seed,t0,arm,trial,stable,acquisition,terminated_in_chunk,chunk_class,chunks_used,cand_sha,recon_sha_match,delta_max,wall_s,note` | 192 个记录；24 个事件×SAME 8 次，`trial=1..8`，唯一键 `(event_id,arm,trial)` 无重复，主键及两种 outcome 均非空；臂内序号在文件写入顺序中单调 | **PASS 结构** |
| `analysis/stageR_resample_rollouts.csv` | 与 SAME 同一 16 列，**混装** `RESAMPLE` 和 `NATURAL` | RESAMPLE 24×8=192；NATURAL 24×4=96；总 288 记录；各臂试次完整、主键无重复；NATURAL `recon_sha_match` 96 条均空是实现中明确的**预期行为** | **PASS 结构；使用时必须 arm 过滤** |
| `analysis/stageR_manifest.csv` | `event_id,ord,task,seed,t0,role,n_prefix,a_fail_shape,pre_sha16,post_sha16,a_fail_sha16,prompt,method` | 32 事件，`R0_DEV=8`、`R1_COHORT=24`；`ord=1..32` 唯一；cohort 的 method 为 `PREFIX`；三种 SHA16 字段格式合法，主键/必要元数据非空 | **PASS 结构** |
| `analysis/stageR_failure_events.jsonl` | `event_id,task,seed,t0,role,episode_dir,prompt,target,n_prefix_actions,a_fail_sha16,pre_sha16,post_sha16` | 32 条与 manifest ID 和 task/seed/t0/role 均匹配；source 将 `target` 写为 `null`，运行时才由重建后的 sim `obj_of_interest` 取得 | **PASS 事件索引；target 并非合法在线观测证明** |
| `analysis/stageR_event_probabilities.csv` | event 级 `q_same/q_policy/type` 等 28 列 | 24 条，事件 ID 与 manifest 24 个 R1_COHORT 对齐；本阶段**没有读取这些概率字段的取值作结果分析** | **索引对齐 PASS；派生结果不可当独立标签** |
| `analysis/stageR_collect_ledger.csv` | `task,seed,episode_dir,rc,classify,wall_s,retries,fg_first,rps_first,t0,t0_skill,meas_points,stable_fg,included,note` | 有 187 条扫描 ledger 记录，选择后的 manifest 是独立冻结产物；ledger 无 `event_id` 列，event_id 由源代码按原 ledger 行号生成，**不能用纳入序号替代 ID** | **字段/来源 PASS** |
| `analysis/stageR_trial_checkpoints.jsonl` | 生成代码定义每行 `event_id,arm,trial,cps`；GitHub 被 `.gitignore` 排除 | **用户服务器确认存在**；抽查首条非空 JSONL：顶层 `arm,cps,event_id,trial`，首个 `cps` 对象含 `check_success,eef,grip,meas,obj,obs,pos,terminated`，首个 checkpoint **顶层无含 time/stamp 的键**；本次未查看值和其余记录 | **SAMPLED_SCHEMA_VERIFIED；完整性、其他记录/嵌套时间与独立参考未核实** |

**结构结论**：cohort 24 个事件同 SAME/RESAMPLE/NATURAL 每臂键集均能一一对应 manifest；`task,seed,t0` 在试次行与 manifest 上一致，缺失/重复键均未检出。这里只证**行结构完整**，不能把它当成任何实验效果、统计显著性、随机独立性或在线可信度检验。

## 2. 字段真实来源：生成代码级溯源

| 字段/证据 | 源头与函数（此仓冻结版本） | 实际语义 | 研究用途及授权边界 |
|---|---|---|---|
| `event_id`,`ord`,`role` | `scripts/stageR_rt.py:48-57`；`scripts/stageR1_run.py:100-133` | `event_id` 来自完整 collect ledger 行号，`ord` 来自纳入序，先 8 DEV 后 24 R1 cohort | 只读按事件连接，不能混入 R0_DEV |
| `S_pre`,`S_post`,`pre_sha16`,`a_fail_sha16` | `scripts/stageR_rt.py:61-105`、`scripts/stageR1_run.py:110-125` | episode 本地快照和 trace 动作重新装载；manifest 记录 provenance 哈希 | 哈希仅说明资产标识/仪器可复现，不能认定可作 perfect causal oracle |
| `trial`,`arm` | `scripts/stageR1_run.py:170-226` | 每个事件从 SAME k1..8，接 RESAMPLE k1..8，最后 NATURAL k1..4；每次**分别重建**，不是从上一 trial 的 terminal state 继续 | `trial` 是 arm 内尝试次序，**非绝对时间，也非连续物理失败计数** |
| `wall_s` | `scripts/stageR1_run.py:174-224` | `time.time()` 差，保存**每 trial 耗时** | 不能当 wall-clock 执行开始/结束时间戳或时间漂移控制变量 |
| `stable`,`acquisition` | `scripts/stageR_rt.py:199-218` 取得 `scripts/stageQ_rt.py:292-294` 的同一 `cps` 上两个函数输出 | 共享 `_confirms`；`stable` 若任一点 `check_success` 则直接为 True，否则要求后续四点以上均确认 | **研究 outcome 标签**；不是互相独立的 verifier；不可直接获得 Runtime/Evolution 授权 |
| `check_success`, `pos`, `eef` | `scripts/stageO_rt.py:245-252` 返回 `env.sim_measurement()` 与 `env.check_success()`；`scripts/stageQ_rt.py:223-258` 用于 _confirms | 仿真特权物理真值/派生位姿与任务判分 | **research_audit_truth**；不得视为线上可见 RGB/proprio 合法代理 |
| `chunk_class`,`terminated_in_chunk` | `scripts/stageP_rt.py:108-... (checkpoint/classify_chunk)`、`stageQ_rt.py:296-301` | chunk 前后仿真测量导出特征；terminal flag 是流程状态，不等于独立成功 | 科学描述可用；不得洗白为合法物理独立标签 |
| `recon_sha_match`,`delta_max` | `scripts/stageR1_run.py:141-153`、`stageR_rt.py:189-195` | PREFIX/SNAPSHOT 重建的仪器一致性/数值差异；NATURAL 无同一 SHA 通道 | 限定重建可比性，不是 outcome 正确率；`ρ` 需重建契约级定义，不能套 Stage Q 10/14 |
| `episode_dir`,原始 `stageR_trace.jsonl` 与 `stageR_snapshots` | `scripts/stageR_rt.py:61-105` | 本地路径及物理快照/动作流；`stageR_failure_events.jsonl` 保存目录引用而非原文件 | GitHub 结构审计不能替代服务器本地文件核验；**本轮没有运行服务器环境，也没有发布原始路径或快照** |
| `cps` | `scripts/stageR1_run.py:137-157`、`stageQ_rt.py:270-295` | 每 trial 内的逐 chunk 测量点；写入被忽略的 checkpoint JSONL | GitHub 无法判断是否有物理事件时间戳或独立 future reference；**目前视为不可核证** |

**source links（固定审计版本）**：
- [Stage R1 Runner](https://github.com/Jasonnn258/RPent/blob/cd45de662f2b43e645f0c240cf4033aee9b55000/scripts/stageR1_run.py#L53-L157)
- [同一事件三臂固定顺序](https://github.com/Jasonnn258/RPent/blob/cd45de662f2b43e645f0c240cf4033aee9b55000/scripts/stageR1_run.py#L167-L226)
- [Stage Q 双契约实现](https://github.com/Jasonnn258/RPent/blob/cd45de662f2b43e645f0c240cf4033aee9b55000/scripts/stageQ_rt.py#L223-L295)
- [仿真测量来源](https://github.com/Jasonnn258/RPent/blob/cd45de662f2b43e645f0c240cf4033aee9b55000/scripts/stageO_rt.py#L245-L252)
- [Gitignore 忽略 checkpoint](https://github.com/Jasonnn258/RPent/blob/cd45de662f2b43e645f0c240cf4033aee9b55000/.gitignore#L43)

## 3. TV-1..TV-5 正式处理

| Gate | 已核实的部分 | 剩余不足 | 本轮资格 |
|---|---|---|---|
| **TV-1：双 outcome 是否成对、真值是否独立** | SAME/RESAMPLE 每记录各有 `acquisition` 与 `stable`；源码明确共享 cps、_confirms、sim check_success；按源码蕴含 `stable→acquisition` | 缺独立的合法 decision-time proxy 与未来新时间窗的 reference；checkpoint GitHub 不可读 | **OE1a GO 描述；OE1b NOT_IDENTIFIABLE on audited sources** |
| **TV-2：事件+臂+顺序+完整性** | 24 R1 cohort；SAME 24×8、RESAMPLE 24×8、NATURAL 24×4；键无重复，单臂序号 1..K 且按文件序列单调 | 无绝对 time/顺序随机化；固定臂先后与时间混杂；事件级 sample 很少 | **OE2a / OE3 回顾性索引 GO；M2 因果识别 HOLD** |
| **TV-3：合法输入和 sim 真值隔离** | `env.sim_measurement` / `check_success` 是标签生成主依赖；CSV 无 `visibility`、合法在线 proxy 时间或 provenance 类型字段；事件 target 初始为 null，重建后从 sim 取得 | 不能证明进化授权所需合法 outcome/观测 | **Evolution eligibility = NOT_AVAILABLE**（不得自动晋升） |
| **TV-4：样本/统计功效** | 结构级 24 event、每事件各臂覆盖齐；Stage R 既有终报指出 P 仅 t9 | 本阶段未运行功效计算；数据已公开不能伪称盲测、P 的跨 task 预测不能保证 | **结构 PASS、统计功效 NOT_TESTED；数值 `n^*` 不可冻结** |
| **TV-5：重建保真/时间可比性** | manifest cohort `method=PREFIX`，三 SHA16 非空，replay `recon_sha_match` 非空；NATURAL 来自 S_post,对应 recon SHA 空符合源码 | checkpoint 与原 episode 目录不在 GitHub；未直接审计全状态、接触、试次漂移、真实时间 | **仪器 provenance PASS、物理/因果等价性 NOT_ESTABLISHED** |

## 4. 直接产生的预注册约束（不等于冻结）

- **OE1a**：后续只能声称“同源的嵌套操作契约”间的分歧；因为 `stable→acquisition` 已由源码证明，对同一批合法完整试次才有 `E[A]-E[Y]=P(A=1,Y=0)`，其数学等价是**代数事实**，不是本阶段新观察结果。
- **OE1b**：若要真正“提前宣告持有/已修复却未来失败”的错误，必须有一个**不复用既有标签或其未来片段**的 reference 与合法的决策时代理；当前远端不具备，标 NOT_IDENTIFIABLE。不得将 `STABLE` 本身冒充独立物理验证。
- **OE2a**：可在获批后研究条件预测 `h_a(k+1)`，M1 事件异质性必须是正式对照；`wall_s` 不能校正真实时间漂移。
- **OE2b/M2**：trial 序号与执行先后确实存在，但同一事件内顺序未随机化，三臂固定顺序且无绝对时钟；在此条件下即使顺序置换出现差异，也**只能**报告非可交换关联/可能时间混杂，不能识别“连败导致物理持续失败”。
- **OE3a**：用同一个 `event_id` 内的 `1..k` 作为输入、`k+1..k+m` 为未来评价，**整 event 按组隔离**做模型选择与评价；外部研究者已经见到 Stage R 的汇总报告，属于回顾性/公开数据研究，不得伪装新的 prospective test。
- **Gate firewall**：此 R1 trial CSV 的 outcome 无独立合法来源证明；即使科学预测良好，也属于 `RESEARCH_ONLY_LABEL`，不能成为在线 Runtime 或 Evolution PROPOSE_REVIEW 的可消费真值。
- **不得新造观察通道**：若 checkpoint 本地存在且只有 sim cps，也不等于独立合法 RGB/proprio 或分离的未来真值；字段存在性与证据独立性是不同 Gate。

## 5. 服务器本地只读 schema 反馈（用户已完成单条抽样）

**用户终端原始输出（只展示字段名，不展示观测值）**：

```text
file_exists: True
record_keys: ['arm', 'cps', 'event_id', 'trial']
checkpoint_keys: ['check_success', 'eef', 'grip', 'meas', 'obj', 'obs', 'pos', 'terminated']
time_like_keys: []
```

**证据强度与边界**：

1. `file_exists: True` 证明报告时该路径在用户服务器上存在；GitHub 看不到不意味着文件不存在。
2. `record_keys` 和 `checkpoint_keys` 来自**第一个非空 JSONL 记录的 `cps[0]`**；`time_like_keys: []` 只说明这**一个** checkpoint 对象的**一级键名**中没有包含 `time` 或 `stamp` 的键，不能据此宣称整份文件或 `meas/obs` 嵌套对象均没有时间字段。
3. `check_success` 与 `pos/eef` 证实 checkpoint 第一例暴露仿真测量接口；联合已审计 `stageQ_rt.py` 与 `stageO_rt.py`，不支持把它当成独立的合法在线 success reference。即使未来找到时间字段，也**不自动**成为独立参考或 M2 因果证据。
4. 此次**没有**进行全文件行数、唯一键/试次数、`cps` 长度、嵌套 `meas/obs` 的结构检查；未查看物理值、成功率或状态。此项报告的 local-only Gate 由 `NOT_VERIFIED` **提升为 `SAMPLED_SCHEMA_VERIFIED`，不能写成 `FULL_SCHEMA_PASS`**。
5. 后续如仍在 Stage 2A 范围做补齐核验，可只读扫描全部行的**键名集合和缺失/异常记录数量**，不输出原始状态或任何 outcome 频次；不得运行统计/拟合。

**尚未完成的本地审计**：

- `analysis/stageR_trial_checkpoints.jsonl` 是否所有行结构一致、是否有嵌套时间/其他参考来源，仍未验证；
- `episode_dir` 下的 `stageR_trace.jsonl` 与 snapshot 文件在本地是否存在、是否有可追溯的独立参考，仍未验证；
- CSV 没有绝对试次开始时刻。若本地日志存有更多时间来源，也不意味着实验顺序已经随机化或 `S_post` 的时序因果可识别。

**阶段许可不变**：本地只读 schema 补查属于已获批 Stage 2A；正式预注册冻结、数值估计/检验和 Stage 2B 新内容仍需单独授权。

## 5.1 用户服务器全文件 key-only schema 核验（追加）

> **用户终端回传**：脚本只逐行解析 JSON、统计结构完整性和键名，不分析成功率、任何物理测量数值或新效果指标。本记录只描述用户返回的检查结果，不声称模型直接访问了服务器字节。

```text
records: 484
checkpoints: 12641
malformed: 0
empty_cps: 0
record_schemas: {('arm', 'cps', 'event_id', 'trial'): 484}
checkpoint_schemas: {('check_success', 'eef', 'grip', 'meas', 'obj', 'obs', 'pos', 'terminated'): 12641}
meas_keys: ['obj_of_interest', 'obs']
obs_keys: ['akita_black_bowl_1_pos', 'akita_black_bowl_1_quat',
           'akita_black_bowl_1_to_robot0_eef_pos', 'akita_black_bowl_1_to_robot0_eef_quat',
           'akita_black_bowl_2_pos', 'akita_black_bowl_2_quat',
           'akita_black_bowl_2_to_robot0_eef_pos', 'akita_black_bowl_2_to_robot0_eef_quat',
           'cookies_1_pos', 'cookies_1_quat',
           'cookies_1_to_robot0_eef_pos', 'cookies_1_to_robot0_eef_quat',
           'glazed_rim_porcelain_ramekin_1_pos', 'glazed_rim_porcelain_ramekin_1_quat',
           'glazed_rim_porcelain_ramekin_1_to_robot0_eef_pos',
           'glazed_rim_porcelain_ramekin_1_to_robot0_eef_quat',
           'object-state', 'plate_1_pos', 'plate_1_quat',
           'plate_1_to_robot0_eef_pos', 'plate_1_to_robot0_eef_quat',
           'robot0_eef_pos', 'robot0_eef_quat',
           'robot0_gripper_qpos', 'robot0_gripper_qvel',
           'robot0_joint_pos', 'robot0_joint_pos_cos', 'robot0_joint_pos_sin',
           'robot0_joint_vel', 'robot0_proprio-state']
time_field_paths: []
```

**Gate 更新（严格分维度）**

- `FULL_SCHEMA_PASS`：在扫描到的 484 个非空记录上，顶层字段集合完全一致；全部 12,641 个 `cps` 字典具有同一组一级键；没有 JSON 解析异常/空列表。脚本还检查了 `meas/obs` 的字典键集合。
- `TIME_NAMED_FIELD_NOT_OBSERVED`：此前脚本仅识别键名中含 `time` 或 `stamp` 的路径，且递归深度受限（原脚本在 `depth>3` 时终止）。本次结果没有此类路径，但**不能排除隐藏在不含 time/stamp 名称的编码值、外部日志或更深结构中的时间信息**。CSV `wall_s` 仍然只是每 trial 耗时。
- `NO_INDEPENDENT_REFERENCE_IDENTIFIED`：键名显示 sim `check_success`、EEF、物体位姿及 robot proprio，未见显式独立未来 label/合法决策时代理；只能说“**本审计没有找到**”，而非证明不存在任何别处的参考信号。
- **`KEY_RECONCILIATION_PENDING`（新阻断）**：现有 GitHub 冻结 trial CSV 的 SAME=192、RESAMPLE=192、NATURAL=96，总计 **480** 个事件-臂-试次键；本地 checkpoint JSONL 有 **484** 个记录。相差 4 条，尚未比较本地 JSONL 与 CSV 的 `(event_id,arm,trial)` Counter，**不得猜测**是重复、旧尝试、DEV、INFRA 等何种原因。记录数差异也意味着当前不能宣称“全部记录逐试次配对”。
- 仍未确认：逐个 checkpoint 的完整时间序列语义、外部 `episode_dir` 中的其他 reference、独立观测合法性、真正的 M2 顺序因果可辨识性。

**立即可做的后续（仍是已获批 Stage 2A 只读结构审计）**：对本地 checkpoint JSONL 与两个 CSV 计算 `(event_id,arm,trial)` 键的 Counter 差，并只打印重复/缺失/额外的键以及计数；不读取或聚合 `stable/acquisition/check_success` 值，不写文件、不运行模型。将结果回填本文后再考虑把 key Gate 置 PASS。

## 5.2 CSV ↔ checkpoint 双向键对账与 DEV 来源归类（最终补审）

> 2026-10-09 用户再次在服务器执行**只读** Counter 双向差集检查；输出仅为事件/臂/试次标识、计数、重复键数量、臂内记录数，**未读取/计算稳定成功标签、物理状态、试次性能**。

```text
CSV records: 480
Checkpoint records: 484
Unique CSV keys: 480
Unique checkpoint keys: 484
Checkpoint arm counts: {'NATURAL': 96, 'RESAMPLE': 192, 'SAME': 196}
Extra checkpoint keys:
('r09', 'SAME', 1) count: 1
('r09', 'SAME', 2) count: 1
('r09', 'SAME', 3) count: 1
('r12', 'SAME', 1) count: 1
Missing checkpoint keys: (none)
Duplicate checkpoint keys: (none)
extra_records: 4
missing_records: 0
duplicate_key_count: 0
```

**冻结 manifest 独立交叉核对（GitHub `analysis/stageR_manifest.csv`）**：

| event_id | ord | role | 额外 SAME trial |
|---|---:|---|---|
| `r09` | 1 | `R0_DEV` | 1, 2, 3 |
| `r12` | 2 | `R0_DEV` | 1 |

- **`R1_COHORT_KEY_JOIN_PASS`**：CSV 的全部 480 个唯一键都在 checkpoint 中各存在恰好一次；checkpoint 多出的四键**全部属于冻结 manifest 的 DEV 事件**，均不属于 R1 cohort。按冻结 manifest `role=R1_COHORT` 过滤的 checkpoint 键集与正式 R1 CSV 键集一致，可作为**未来获批离线研究的结构资格**。必须坚持冻结事件 role/ord 分离，而不是根据 event_id 数字大小或事后成功率选样本。
- **`EXTRA_DEV_ROWS_IDENTIFIED_4`**：混合 JSONL 的四条额外记录在**事件角色层面**已被识别为 DEV 事件数据。它们仍留在原始 JSONL，不能删除、重写、自动聚合进 R1 的 24-event 数据。
- **`DEV_WRITE_ORIGIN_NOT_VERIFIED`**：为何 DEV 事件的这四次 SAME 记录进入 R1 checkpoint 文件仍未确定。现有冻结源码 `scripts/stageR1_run.py:153-157` 在单个 trial 内**先追加 checkpoint JSONL**，而 `:183-184` 随后写 CSV，这说明二者并非原子落盘、存在脱配风险；但**不能仅凭该写入顺序证明**这四行由中断、某次 DEV pilot 或历史脚本生成。冻结 `stageR0_qualify.py` 主要维护其独立 R0 CSV，不足以归因这些行的生成者。
- 原先 §5.1 的 `KEY_RECONCILIATION_PENDING` 属于**检查前的历史状态，已被本节的新审计结论取代**；不会因此修改旧报告或篡改原始记录。

**本轮最终状态（分维度）**：
`FULL_SCHEMA_PASS / R1_COHORT_KEY_JOIN_PASS / EXTRA_DEV_ROWS_IDENTIFIED_4 / DEV_WRITE_ORIGIN_NOT_VERIFIED / NO_INDEPENDENT_REFERENCE_IDENTIFIED`。

这项结论只关闭 Stage 2A 的**样本结构对账阻断**；并不证明原始 checkpoint 的物理因果真实性、独立物理 reference、时间序列因果、预测模型效果或 Runtime/Evolution 权限。OE1b、M2 实际时序因果与在线授权继续 HOLD；Stage 2B、正式预注册冻结、离线统计仍需用户单独批准。

## 6. 数据读回可复现性与审计纪律

- 本文所有结构计数只对 `(event_id,arm,trial)` 和 `role` 进行索引检查；没有基于 `stable`/`acquisition` 做成功计数、置信区间、性能对照或统计检验。
- 读取的是**截至基线提交**的 GitHub 已跟踪 CSV/脚本，不等于服务器当前磁盘字节；Github `blob sha`、本审计的结构检查与 Stage R 原报告可以互相交叉参照。
- 没有写入任何执行代码、清理/覆盖原始文件、补齐缺失字段或更改 Stage R 四类 `E14/A1/P5/U4`。
- **审核结论不是统计结果**。下一份预注册只应作为 DRAFT，并保持 Stage R §36 Hard STOP / S1-DEV0 ON_HOLD。


> **Stage 2B 源文档复读后的追溯修正（2026-10-09）**：此前的 `DEV_WRITE_ORIGIN_NOT_VERIFIED` 是 Stage 2A 检查时的历史结论。冻结 `analysis/STAGE_R_FINAL_REPORT.md §9`（deviation `dev-r1-fix`, 2026-10-08 05:59）明确记录 R1 首启队列切分错误使 8 个 DEV 事件误入 R1，05:01 停止时**已多跑 4 个 DEV trial**，修复队列后 R1 的 24 个 cohort 全部重新执行，**CPS 日志保留越轨 trial 作为审计**。这一已冻结记载与本地 checkpoint 额外的 `r09/SAME/1-3`、`r12/SAME/1` 四键及 manifest DEV 角色数量/身份吻合。**现在可将来源判为 `DEV_R1_STARTUP_DEVIATION_DOCUMENTED`（原始日志明确说明，非额外自行推断中断）**；但不声称已逐字节比对 04:58 启动日志或每条 CPS 生成时刻。原 Stage 2A 的“未验证”表述保留为复读前历史审计状态，由本附注覆盖。正式 R1 集合仍为 `role=R1_COHORT`，480/480 通过、零重复零缺失，禁止修改原始 CSV/JSONL。
