# EERD v0.1 — Embodied Evidence Reliability Dataset · 数据契约草案

> 2026-10-09 | **DRAFT / SCHEMA-ONLY / ZERO DATA EXPORT / NO OUTCOME READ**。
> 基于 Stage2I 服务器回传、Stage2J 候选、Stage2K 独立审查、PAEG `METHOD_SPEC.md` v0.2.2。
> 不是完成或公开发布的数据集；不批准任何 outcome 值读取、特权真值在线消费、仿真/rollout/训练、Stage R §36 改动。

## 0. 目的与不可混淆的任务

**EERD 的研究对象是“证据和物理结果之间的对应关系、可见性与时间有效性”，而非将 187+480 混成泛化机器人学习数据。**

| 子集 | 原始资产 | 可研究对象 | 禁止混用 |
|---|---|---|---|
| **A / Vanilla Skill Evidence** | 187 原始 Planner episode、235 次 `pi0_pick`、2,859 chunk | D2 工具返回与同技能取得类审核构念 `IN_SKILL_ACQ_FGONLY` 的有限对照 | 不叫“D2 后未来持握”，不因 235/235 结构完整就宣布 235 真值齐全 |
| **B / Frozen Failure Persistence** | 24 个失败事件、480 正式 R1 重建 trial（剔除 4 DEV） | SAME/RESAMPLE/NATURAL 已测协议内的重建差异、持续失败及标签敏感性 | 不叫真实 Planner 连续 retry，不把 480 trial 当 480 个独立事件 |
| **C / Future Intervention Cohort** | **尚不存在** | 在真实 D2 决策边界比较固定预算主动验证/恢复策略的后果 | 不从 A/B 伪造反事实、随机对照或动态验证成本收益 |

## 1. 三层数据实体与统一命名

**Episode 级**：
`episode_id`（非原路径的稳定假名）、`suite`、`task_id`、`seed_id`、`collector_protocol`、`source_commit`、`source_hash`、`complete_or_infra`（只在被批准的审计中填合法结果值）、`split_group_id`。

**Skill/attempt 级**：
`episode_id`、`step_idx`、`skill_name`、`attempt_id`、`arm`（B 才有）、`reconstruction_method`、`reconstruction_quality`、`decision_boundary`、`tool_report_fields`、`tool_report_delivery_phase`、`trace_alignment_status`、`eligibility_status`、`missingness_status`。

**Evidence event 级**：
`event_id`、`attempt_id`、`event_time`（绝对时间或相对 chunk index，并记录 units）、`capture_time`、`available_to_actor_time`、`actor`、`modality`、`source_field_path`、`value_or_artifact_ref`、`visibility`、`reference_contract`、`reference_version`、`provenance`、`known_limitations`。

两种**强制防火墙**：
1. `online_eligible` 视图只能包含已确认在该时刻真实交付给 Planner 的合法工具返回和传感字段。仅与这些字段数值相同的内部测量不自动获得资格。校验器不能从 label 表反向拼回决策输入。
2. `audit_only` 视图可含 sim object pose、`check_success` 等研究专属真值；不作为 Runtime/Evolution 的输入，标签任何变体均携带 `outcome_contract`/版本和完成度。

## 2. A 子集标签状态机（不允许静默负例）

`reference_state` 必须支持 `POSITIVE / NEGATIVE / UNKNOWN / NOT_EVALUATED`。

对于“**技内曾满足 FGONLY 取得**”的存在性对象：
- 某有效测量点确认 FG，则 `POSITIVE`；
- 只有规定的全部测量点都具有可构造、有限且正确对齐的目标/EFF 位置，且均未满足 FG，才能 `NEGATIVE`；
- 若关键时点字段缺失且当前未观测到 FG，则 `UNKNOWN`，不能因为点被删除而记负例；
- 目前未批准读取 outcome，全部指标初始为 `NOT_EVALUATED`。

`check_success` 旁路衍生版另列标签版本；`TERMINAL_INVOLVED` 只作为来源/研究子集条件，主子集条件性选择必须申报。truncation 使用 `states.json` **step 顶层**的 `episode_truncated`（不在 `pi0_pick.result` 里）。

不得把 `IN_SKILL_ACQ_FGONLY` 等价为真正夹爪接触、未来稳定保持或总体任务完成。

## 3. B 子集的执行协议元信息（不可省略）

- 每行保留独立 `parent_failure_event_id`，同一失败事件的 8 SAME + 8 RESAMPLE + 4 NATURAL（若按实际冻结 manifest）必须仍归于**同一个 cluster**；数量分配严格以冻结 manifest 为准，不以公式假定每事件无异常。
- `S_pre` 重建与 `S_post` NATURAL 的真实差异必须编码为 `execution_condition`。B 子集真实独立事件数是 24，不可在独立样本量中计 480。
- `acquisition`、`stable` 仅为指定 Stage Q/R continuation 约定下的研究用结果；保留原始标签版本、终局/删失标记、样本资格与 DEV 排除理由。
- 不能因为 `E/A/P/U` 已冻结就将其升级为合法 Runtime/Evolution 经验写回许可。

## 4. 对未来 Benchmark 的分割和度量建议

**按数据家族分别划分，切勿混合做统一 SOTA 排行**：
- A：按 `episode_id` 分组；所有该 episode 的 pick/trace/截图共享同一 split；时间顺序特征必须只取决策边界前合法可得字段。
- B：按 `parent_failure_event_id` 分组，所有该事件的 SAME/RESAMPLE/NATURAL、其源 episode 和导出标签不得跨 split；若 A/B 有共享原始 episode，需构建`cross_dataset_provenance_group` 防交叉泄漏。
- 有 3 个原始任务，可设计少量 task-held-out 压力测试，但这无法证明跨任务族泛化；独立 prospective C 才能有独立验证。
- A 可能的参考表：工具 flag × FGONLY 的二维表、正负类支持、UNKNOWN 覆盖、选择偏差、episode 聚类区间、常数基线；所有 outcome 值统计须新协议和授权。
- B 现有 Stage2D 仅为回顾性已发布描述，不能未经授权改算新评测或重打冻结标签。

## 5. 从 EERD 到 P1 的研究性 Bridge

**科学假设（未验证）**：在等额动作/观察预算下，考虑证据时效、失败持续性和物理风险的主动验证/恢复选择，比固定验证频率和简单阈值基线减少错误完成。

要让此假设可证伪，未来 C 需要新增：
`D2 legal snapshot`、`verification_action`、`verification_cost`、`decision_policy_id`、`physical_future_reference`、`horizon`、`terminated/truncated`、`matched_initial_state`、`heldout_task`。采用已冻结 VLA、清楚的动作预算、策略对照与预设指标；不能把同一 Planner 自然执行的 policy-coupled 未来当固定策略反事实。

## 6. 交付验收与停止准则

EERD v0.1 **仅文档契约**的验收：
1. A/B schema 有字段级来源和可见性映射；
2. 真实 Planner 交付时刻 vs 仪器取样时刻可追溯；
3. 物理判据唯一命名、版本化，缺失与 UNKNOWN 明确；
4. 跨 episode/event 依赖和可复用的 split key 明确；
5. 不导出私有路径/原始数据、不生成未经授权的新 outcome 指标；
6. 所有 scientific claim 都在当前数据能力上有边界。

**任何真正的数据集物化、打标签、计算 benchmark 或 P1 在线实验，都必须另行检查数据合规、冻结协议和用户授权。**

状态：`DRAFT_SCHEMA_READY / EERD_NOT_MATERIALIZED / A0_REFERENCE_UNVALIDATED / P1_CONTROL_EXPERIMENT_NOT_AUTHORIZED`。
