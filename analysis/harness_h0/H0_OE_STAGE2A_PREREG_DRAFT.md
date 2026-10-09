# H0 Direction 1 · Outcome Evidence Calibration
## Stage 2A — Prospective Analysis Specification Draft for EXISTING Retrospective Data

> **状态：DRAFT_NOT_FROZEN · NO_RESULTS_RUN · NOT AN EXECUTION AUTHORIZATION**
> 2026-10-09；本轮用户仅批准“Stage 2A 只读字段审计与预注册草案”，未批准正式冻结、数值门选择、离线结果分析或训练与在线实验。
> 方法与数据依据：Stage 1 的 `H0_OE_STAGE1_RESEARCH_PROTOCOL.md`、
> `H0_OE_STAGE1_IDENTIFIABILITY_MATRIX.md`、
> Stage 2A `H0_OE_STAGE2A_FIELD_PROVENANCE_AUDIT.md`、既有冻结 Stage R prereg/终报。
> 来源与时间语义必须依托 `scripts/stageR1_run.py`、
> `scripts/stageR_rt.py`、`scripts/stageQ_rt.py`、`scripts/stageO_rt.py` 以及当前 24 个 R1 cohort。
> **这是一份对已收集、已发表汇总结果的数据进行的未来分析规格草案**，无新 prospective samples、无“结果未知盲预注册”地位。

## A. 拟注册范围：估计对象、假设、否决条件

**研究单位**：`event_id` 代表一次按 Stage R 预注册纳入的已失败事件；`trial` 表示从独立重建 `S_pre` 开始的该事件-臂下第 j 次历史实验，不是同一状态在自然连续失败后继续演化的序列。

**primary outcome**：Stage R **冻结版本** `STABLE_RECOVERY` 布尔 `Y_eaj`；secondary `ACQUISITION` 布尔 `A_eaj`。不得根据未来效应大小调整判据，尤其不得去掉 `stable` 中 `any(check_success)` 提前放行的源代码分支。

**共性假设**：
- 仅条件于“先前已发生一次稳定 FALSE_GRASP 并满足选入标准”的事件族；
- 仅当前 LIBERO / π0.5 / frozen S_pre PREFIX_REPLAY，方法/模型/经验风险的外推域不超过此实验机制；
- 个体重复试次可能在同一 event-arm 下相关，统计独立单位默认 `event`，不能把 384 个 SAME+POLICY 行当 384 个独立状态；
- 固定 SAME→RESAMPLE→NATURAL 的臂执行次序并未随机化，不能凭臂间均值或试次序号作自然物理时序因果解释；
- 实际 checkpoint 在 GitHub 不可核，原 CSV 无绝对开始时刻，时间漂移的识别仍 HOLD。

### OE1a — 双 outcome 的**同源嵌套操作契约分歧**（当前可起草）

**Estimands**：按臂统计：
- `p_A(a) = P(A=1 | entered_FG,arm=a)`;
- `p_Y(a) = P(Y=1 | entered_FG,arm=a)`;
- `d_a = p_A(a) - p_Y(a) = P(A=1,Y=0 | entered_FG,arm=a)`;
- `q_a = P(Y=0 | A=1, entered_FG,arm=a)`（前提：分母 `P(A=1)>0`）。

**形式恒等式**：由冻结源码 `stable→acquisition`，才允许将两接受率差和上述联合分歧视为同一 estimand；不能把它等价成**来自独立传感器的假阳率**。`q_a` 的分母必须明确，分母为 0 则记 `NOT_ESTIMABLE`。

**预拟报告**：按 event 配对的臂内差异、事件分层描述、不确定性区间；primary claim **只能**是“在既有契约中，较宽接受条件相比严格条件承认了哪些试次”，不评价“已修复”“具身技能真实持有能力”。这个结果和已报告 ACQ−STABLE gap 同源，所以只是新分解，不许用重复现象声称独立创新。

**OE1b（原独立假阳率）**：**暂停/不可识别**。审计确认两个标签同源，而且无独立且合法的决策时代理/未来参考字段；以后除非额外文件经只读审查证明了严格独立新目标，否则**不设 FPR=30% 或 10% 门、不输出修复假阳率**。

### OE2a — 条件连续失败后**下一次独立重建**成功（可起草）

定义 `h_a(k+1)=P(Y_{ea,k+1}=1 | Y_{ea,1..k}=0,entered_FG,arm=a)`，
其中 `k` 限于历史试次序号在 `1..8` 的合法前缀（若研究“0 次失败”，那只是总体基线，不能被解释成新一次失败观测）。实验动作每次都从 `S_pre` 重建。

**必要基线**：
- **M0** pooled constant-q Bernoulli，仅作弱参照，不作为唯一零假设；
- **M1** task/event 难度异质的条件 iid/可交换模型，是预测主对照；不允许将混合选择风险衰减误判为状态因果变化；
- **M2** 顺序剩余效应只能作探索性、受固定执行顺序和时间混杂限制的 sensitivity 项。

**必须先冻结但本稿没有选的参数**：对各臂的 k 集合、异质性分布或正则、是否/如何 task 分层、event 级重复性修正、主检验对象、区间与多重比较处理、负面停止规则。

**预期失败结论**：M0 vs M1 差异不明显、数据贫乏时记 `INCONCLUSIVE`；M2 非显著 ≠ 无时间效应，M2 显著也只说明序列相关/非可交换迹象，不证明“连续失败使物理状态恶化”。

### OE3a — 前缀→严格未来 trial 的**回顾性预测**（有条件可起草）

输入：同一 `event`、同一 `arm` 的 `Y_{1..k}`（仅当在用户指定的目标场景中该布尔值确实可观察；对当前真实 Runtime 则不成立），任务等在预测时合法提供的上下文，和**只由训练事件学习**的基线超参数。

目标：`Y_{k+1}`，或预设 `k+1..k+m` 内是否至少一次满足 frozen STABLE；`k+m≤8`。所有 target 必须严格在输入的时间截点之后。阶段二的科研预测使用**历史实验科研标签**，并不提供合法的在线 `S_post` 覆盖。

**划分原则**：模型选择、先验与决策阈值的任何开发和评估，先按完整 `event_id` 整组隔离，不能从同一事件未来试次提取训练统计量；禁止试次随机切分与“从完整 E/A/P/U 事后标签预测完整标签”的自包含真值目标。

**候选参照**：null baseline（只从训练事件得总体风险），M1 异质性/层次风险模型，以及只用可用前缀失败计数的基线；具体模型与组合方式、评价指标/截点/校准/拒判门槛须**在正式冻结时明确**，不能在看同一数据效果后选最有利版本。

**适用性限制**：
- 只有 24 个事件、P 全 t9，模型泛化误差可能很宽；公开的 Stage R 汇总已泄露总体趋势，未来评估属于 retrospective/内部验证，不能称独立锁定 TEST；
- 因为输入可能包含离线重建结果，即使未来预测准确，也只能主张**研究性条件重试预测**，不能据此自动 REPORT_FAILURE、PROPOSE_REVIEW 或选 `n^*`；
- 仅用历史同一 K=8 的结果，不能证明超过 K 次的长期 persistence 或不可修复性。

**弃权语义**：当分布外、区间/分母不合格、样本信息不足、无法从科研输入构造合法在线观测时，分别输出 `INSUFFICIENT_FOR_RESEARCH_PREDICTION` 或 `EVIDENCE_NOT_TRANSFERABLE_TO_RUNTIME`，不能把 abstention 叫“模型失败”。

### OE2b / OE1b / 在线 Gate — 暂不具备准入资格

- **OE2b 真正时序因果**：固定臂执行顺序、缺绝对时间与物理连续状态，在当前设计里只能探索性描述，不能预注册为“failure causes later failure”的因果实验。
- **OE1b 独立物理误报**：无独立 outcome reference，不可用同源 `stable` 来验证自己的正确性。
- **Runtime/Evolution**：依照 METHOD_SPEC v0.2.2 §5.6 的字段权限，Stage R 的两个 outcome 是科研真值/科研标签；不能把它们消费为 `observed_execution_prefix` 或合法 Evolution outcome。

## B. 数据资产、必要字段与审批结果

| 数据文件 | 结构已只读核验 | 运行时/科学权限 |
|---|---|---|
| `stageR_manifest.csv` + `stageR_failure_events.jsonl` | 32 全事件（8 DEV+24 cohort）、联合 ID 与 SHA16 一致；cohort PREFIX | 仅复现 cohort/来源，不能用原始失败作为新增 trial |
| `stageR_same_action_rollouts.csv` | 24×8，序号齐、无重复、两 outcome 字段非空 | 科研分析 ONLY |
| `stageR_resample_rollouts.csv` | RESAMPLE 24×8，另含 NATURAL 24×4，必须过滤 | 科研分析 ONLY；NATURAL 不入 persistence |
| `stageR_event_probabilities.csv` | 24 条 event 级索引匹配 | 已衍生的**事后结果**，不得用于预测输入/评估金标准 |
| `stageR_trial_checkpoints.jsonl` | GitHub `.gitignore` 忽略，远端不可访问 | **LOCAL_SCHEMA_NOT_VERIFIED**，不得假设含独立 reference/绝对时间 |
| `episode_dir/stageR_trace.jsonl`、`stageR_snapshots` | 只有路径索引和 provenance 代码在远端 | **LOCAL_ASSET_NOT_VERIFIED**，不得重新执行或新生成 |

明确拒绝：将 `chunk_class` 中 sim object pose/EEF 底层测量伪装成在线代理；根据 `cand_sha` 生成额外因果动作偏差结论；将 NATURAL `S_post` 的结果用于 SAME/POLICY `S_pre` 预测模型的无条件验证。

## C. 冻结前还缺什么（全部保持 OPEN）

1. **样本切分与任务域**：具体 event-level split 方案、是否仅按当前 24 cohort 进行复用、如何避免旧汇总信息产生的分析者偏差；
2. **明确 primary/secondary 问题数量**：不设多个事后任选 endpoint，OE1a/OE2a/OE3a 哪些可成为 formal primary、对应多个不确定性检验的控制方式；
3. **统计估计规格**：M1 distribution/弱信息先验、重试前缀 k 集合、未来 m、损失函数、coverage/校准、missing/INFRA 处理、事件依赖和小样本偏差；
4. **门槛/停规和功效预审**：不直接沿用旧草案 30%/10%/2× 门；在完整规格审查并独立获批前不选数值；
5. **local-only checkpoint 来源**：仅做可能的只读字段确认，不为追求通过而补造新 reference；
6. **冻结签名**：正式 prereg ID、commit SHA、脚本审查/hash、版本化禁止改动、执行日志与复算计划——本阶段一律**没有冻结**。

本稿包含了潜在比较方法与拒判原则，但还**没有确定实际方法、参数、数值检验标准与执行代码**；不能作为直接运行任务单。

## D. 前置 STOP 与回报格式（待冻结协议审查）

| 条件 | 结果 |
|---|---|
| 独立参考不存在 | **STOP OE1b**，保留 OE1a 契约分歧 |
| 事件-臂-试次键不唯一或顺序不可信 | **STOP OE2a/OE3a 序贯预测**，最多限计数描述 |
| 没有 event 级隔离，模型选择/评估交叉泄漏 | **STOP OE3a**，不得声称独立预测 |
| M1 层次结构无法合理约束，结果对先验敏感且区间极宽 | **INCONCLUSIVE**，不得强推 n* |
| 只看到相同 sim 数据重复驱动的 ACQ/STABLE | **NO INDEPENDENT PHYSICAL FPR** |
| 任何需要新的 rollout、训练、在线控制或 S1 资产 | **STOP WHOLE REQUEST**，另行用户授权 |

如未来确实获批运行统计，报告必须显式区分“结构审计”“冻结契约”“后验预测”“控制器资格”，禁止用科研成功率去替代 Runtime/Evolution 的原始证据权限。

## E. Approval & Execution Ledger

- `Stage 1`：已获授权、已完结（定义 estimands；零数据）；
- `Stage 2A`：本文件仅草拟协议与字段来源核对，**本次已被授权**；
- `Stage 2B`：**正式预注册冻结，尚未授权**；
- `Stage 3`：**现有 Stage R 数据的离线结果定标/检验，尚未授权**；
- `Runtime/Recovery/S1`：均未授权，Stage R §36 Hard STOP 和 S1-DEV0 ON_HOLD 继续。

**本文件状态永远保持 `DRAFT_NOT_FROZEN`，直到另建经过用户批准的正式冻结文件；修改本文件不能冒充冻结。**
