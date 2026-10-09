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
| `analysis/stageR_trial_checkpoints.jsonl` | 生成代码定义每行 `event_id,arm,trial,cps`，`cps` 的测量来自 sim；在 `.gitignore` 被明确排除 | **GitHub 不存在受版本管理的该文件**；无法验证本地行级时间、point-level `check_success` 分量、观测独立性或时间窗口 | **NOT_VERIFIED_LOCAL_ONLY** |

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

## 5. 未完成的服务器本地只读核验（只会进一步限制，不会自动解禁）

1. `analysis/stageR_trial_checkpoints.jsonl` 在服务器本地是否存在、是否完整：检查 schema `event_id/arm/trial/cps` 及每条 cps 的**键名、时间字段是否存在**，不要导出原始数据/结果/路径；
2. `episode_dir` 引用的 `stageR_trace.jsonl` 与 snapshots 是否还在：只确认文件是否存在、命名/哈希来源是否可验证；**不打开或改写世界状态文件**；
3. 是否存在真正**独立于 `stable/acquisition` 判定函数的决策时合法代理和延后真值**：若本地 checkpoint 依旧只有 `rt.measure`，OE1b 继续 NOT_IDENTIFIABLE；不得事后自己定义新 truth；
4. CSV 没有绝对试次开始时间；本地日志若有额外时间源也不能不经明确设计就把实验次序当“连续物理尝试时间”。

以上只读审查可以后续在服务器做，不能以“GitHub 未找到”推断服务器文件不存在。**本轮已完成远端数据结构与生成代码审计；local-only 时间/独立参考 Gate 仍 HOLD**。

## 6. 数据读回可复现性与审计纪律

- 本文所有结构计数只对 `(event_id,arm,trial)` 和 `role` 进行索引检查；没有基于 `stable`/`acquisition` 做成功计数、置信区间、性能对照或统计检验。
- 读取的是**截至基线提交**的 GitHub 已跟踪 CSV/脚本，不等于服务器当前磁盘字节；Github `blob sha`、本审计的结构检查与 Stage R 原报告可以互相交叉参照。
- 没有写入任何执行代码、清理/覆盖原始文件、补齐缺失字段或更改 Stage R 四类 `E14/A1/P5/U4`。
- **审核结论不是统计结果**。下一份预注册只应作为 DRAFT，并保持 Stage R §36 Hard STOP / S1-DEV0 ON_HOLD。
