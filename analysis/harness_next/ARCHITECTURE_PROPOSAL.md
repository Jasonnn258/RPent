# RPent 下一阶段：Persistence-Aware Evidence Governance 架构设计（Proposal）

> 2026-10-09 | 架构提案，非 RPent 已实现功能；无实验设计、无 rollout、无环境或模型修改。
> 方法论参照：`RELATED_WORK_AND_NOVELTY.md`；内部证据：Stage Q/R、S0、Stage H。Layer 名、接口和状态机是待评审规范。

## 0. North Star

在 frozen π0.5 + planner 的具身执行流程上建立一个**可追溯、时效明确且决策依赖的 Outcome Evidence Plane**：能够区分“物体刚被抓起”“物体保持稳定”“任务已完成”“失败可能持续”“是否足以推动长期修改”等不同强度的声明；可靠性不足时明确 abstain。

不同于 Zetta 的常规 Critic/Recovery 管道，也不同于 RegenHarness 的通用 commit gate，主张将**物理事件在时间上的有效性、失败重复性的有限证据、以及不同动作决策所需的证据强度**耦合表达。这个“不同于”是拟议差异，尚待更多原文核验和未来评价。

## 1. 架构草图

```text
Frozen π0.5 / Existing Planner / Env & Tools
     │ legal RGB / proprioception / tool outcome / action context
     ▼
[1] Evidence Ingestion & Temporal Alignment
    - event stream + provenance / sensor quality / observation firewall
     │ ObservationEvent
     ▼
[2] Temporal Outcome Evidence
    - claim assembler / temporal horizon / contradiction & expiry
    - Acquired ≠ Stable ≠ Task Complete; Unknown is first-class
     │ EvidenceClaim + OutcomeState
     ▼
[3] Persistence & Attribution
    - within-episode stability / cross-attempt repeatability
    - epistemic uncertainty + reconstruction fidelity
    - execution-ephemeral / action-specific / policy-persistent / unresolved
     │ AttributionStatement (not causal root-cause oracle)
     ▼
[4] Decision-Dependent Evidence Governance
    ├─ Runtime Eligibility: observe / continue / hold / request supervisor
    └─ Evolution Eligibility: preserve / quarantine / propose review / abstain
     │ [proposal only; no automatic skill edit in this design]
     ▼
[5] Future Validated Harness Evolution  [future, not authorized]
    - candidate skill / critic / context modifications
    - independent review + heldout / regression / rollback
    - no model-weight update
```

横向约束：`Observation Firewall` + role-based authority + append-only audit trail。高风险真实执行行为必须经原有 Planner/Role1 权限；本提案不能绕过工具权限或 Stage R §36 Hard STOP。

## 2. 四类核心数据契约（概念级）

**ObservationEvent**
- `event_id, episode_id, skill_id, time_index, stream_type`（合法可见 video / proprioception / action log / tool output）。
- `source_ref, content_hash, camera_or_sensor, action_context`，时间戳与延迟元数据；不将 raw simulator object pose 混入正常信息面。
- `visibility=agent_observed|offline_evaluation_only`，数据消费端硬隔离。离线科学仪器可以验证真值，但不能作为在线事件输入。

**EvidenceClaim**
- `claim_id, predicate, args, support_event_ids, issued_at, valid_from, valid_until`。
- `status=PROVISIONAL|CONFIRMED|CONTRADICTED|EXPIRED|UNKNOWN`。
- `evidence_quality, observational_limits, contradiction_ids`：质量或置信不得伪装成已经校准的概率。
- 可支持的 `scope` 被单独授权，并且随新证据撤回；不由对象类型自动赋权。
- 例：`ACQUIRED(object_a)` @t1 有抓取视觉支持，`STABLE_GRASP(object_a,[t1,t2])` 需要整段证据，`TASK_DONE` 必须另有目标状态证据。

**AttributionStatement**
- `event_or_cohort_ref, observed_failure_kind, persistence_evidence, resampling_context, reconstruction_fidelity, scope`。
- `failure_class` 可为 E/A/P/U，但声明必须带样本定义与时间窗口；禁止把统计类别当作未观察到的因果 root cause。
- `repairability=UNKNOWN|EVIDENCE_FOR_CANDIDATE_REVIEW|NO_LOCAL_HEADROOM_OBSERVED` 为“进一步审查资格”，并非更新成功概率。
- 不能由单次执行失败直接推导永久技能故障；不能由连续失败直接推断更新后可恢复。

**EligibilityDecision**
- `decision_id, decision_type=RUNTIME|EVOLUTION, candidate_action, supporting_claim_ids, contraindications, authorization_status, reason`。
- `authorization_status=ALLOW|HOLD|DENY|UNRESOLVED`。
- `cost_of_wrong_positive/negative` 在概念上不同，但只有定义了校准方法之后才能使用数值风险。HOLD/UNRESOLVED 是有效系统输出。
- 默认 Evolution Gate 比 Runtime Gate 需要更强、跨执行的一致证据，且仍只授权候选审查；技能晋升由独立验证与人工/既有发布门处理。

## 3. 关键机制：claim 有效性与授权权责

1. **证据生成**：技能返回 `success=true` 只算一条工具报告，不等于物理成功；视频/本体证据可能冲突。
2. **Temporal claims**：Acquisition、stable、task-complete 分别定义证据窗口；持有物滑落使相应当前声明 `CONTRADICTED/EXPIRED`，历史曾成功事件不被抹去。
3. **Persistence attribution**：仅根据已观察的重复/重建证据提示失败是否可能持续；有 Q0 restoration 限制时写 `APPROXIMATE`，不冒称反事实真值。
4. **Runtime decision**：当前证据不足以确认稳定成功则不允许“已完成”提交；是否继续观察需考虑可用工具与执行窗口。
5. **Evolution decision**：单次失败不能触发长期 Skill 改写；多次重复失败仍需判断是否存在可修复缺口，并限制在“候选更新待审”的级别。
6. **Update isolation**：长期知识是版本化产物，不直接从尚未确认的 `PROVISIONAL` 结果永久写入；未批准前不实现修改算法。
7. **Domain/risk boundary**：仿真隐藏状态与标准评分仅用于离线研究，不提升为运行时可见信息。

## 4. RPent 接入点（当前可复用 vs 拟议）

| 位置 | RPent 已有（源码/报告已审） | 拟议扩展，尚未实现 |
|---|---|---|
| Low-level execution | `robots/libero/tools.py`、`toolkit.py`：Pi0.5 pick / move_to / segment、工具调用记录 | 事件时间对齐 adapter，非动作原语改写 |
| Planner | `rpent/planner/api_loop.py`：tool loop、memory trigger、PhaseTracker | `EligibilityDecision` 作为显式“有无资格提交”接口 |
| Runtime verification | Stage Q stable/acquisition 契约；B2 STV 已有过程裁决 | Temporal Outcome Evidence 的时效语义和 Unknown 分支 |
| Repeated-failure evidence | Stage R 24 失败事件及 resample/same-action 统计 | Persistence-aware attribution；保留 reconstruction fidelity 元数据 |
| Memory | 61 张全局卡片、Episode progress、turn boundary injection | 可信 claim vs 候选经验隔离；不默认增加 Graph Memory |
| Evaluation firewall | `env_server.py` sim_measurement / check_success 为离线仪器 | Evidence claim 上加 `visibility` 并约束跨层消费 |

**重要**：这些扩展目前都是概念接口，仓库本轮不新增任何代码。尤其不要在冻结 Stage R 分支上擅自创建“新 recovery method”或“新 verifier”；未来实现必须由新的授权与隔离分支决定。

## 5. 体系结构论证

- **为何先证据层**：低层动作反馈含有随机性与暂时性；若将工具返回 success 直接当作 Task Completion/Skill Correctness，长期演化会把执行噪声变成可持续错误。
- **为何单列 Persistence**：执行暂时失败、同动作可重现、政策持久失效、技能有机会修复是逻辑上不同的命题。Stage R 的 E14/P5/U4/A1 提供了本项目的具体现象基础。
- **为何双 Gate**：同一证据支持不同损失代价的动作：立即暂停所需证据与“永久改写技能”所需证据强度不同；合并会在动作期漏检或在演化期过拟合。
- **为何不做一般化 World Model**：RPent 当前已经有稳定性与失败持续性数据，尚无证据证明需要学习全环境动力学；复杂度先投入到可解释的 Outcome Claim 和权限语义。
- **为何不先 Memory**：S0 没发现原任务族历史必要决策点；S1 可留作历史身份追踪压力测试，但当前研发资源优先支持已有 headroom 的证据问题。
- **为何此时不做 Skill Evolution**：没有可靠物理反馈与可修复性证据时，新增迭代器可能以短暂失败作为错误标签；Zetta/SkillOpt 已提供候选验证先例，日后可复用而不重造。

## 6. 风险、拒绝场景与设计取舍

- **来源泄漏**：隐藏 sim object pose/任务目标真假通过仪器报告、prompt、缓存进入在线接口；必须设置强制数据边界。
- **Temporal aliasing**：低频图像漏掉接触/滑落瞬间；可能需要 UNKNOWN，不能臆断稳定。
- **Non-identifiability**：同一终态可能由不同动作历史产生；持久性和根因难以辨识，不能假装确定。
- **Calibration gap**：未有独立校准就不要输出伪精确的成功概率或风险阈值。
- **Reconstruction shift**：Q0 类别一致率不足，重建证据不能被当作严格物理干预效应。
- **No intervention window**：即使判准错误，可能太晚干预；此时 Scope 限定为离线归因/未来更新资格。
- **Prior-art collision**：如果 RegenHarness、VASO、CommitFlow 已覆盖一般 Evidence Eligibility，核心创新缩小到 *physical persistence × decision-specific thresholds*，不要包装常见 Gate。

## 7. 拟议阶段产物边界

当前只批准**研究设计与文档**：相关工作差异、问题定义、接口与架构提案、原创性风险表。未定义新的实验预注册，不分配 GPU/LLM，不运行 S1 DEV0，亦不启动 verifier、critic、planner redesign、skill update、RL。

后续是否开展任何新研究实现，要先由用户审核该方向的原创性与研究意义，再独立批准执行路线。
