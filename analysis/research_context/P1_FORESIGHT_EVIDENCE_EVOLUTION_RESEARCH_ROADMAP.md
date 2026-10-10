# RPent 研究方向参考：Foresight-Governed Evidence Acquisition & Evidence Evolution

> **类型**：研究 Insight → 后续实验路线图（REFERENCE_ONLY / NOT A PREREGISTRATION / NOT A RUNTIME AUTHORIZATION）  
> **日期**：2026-10-10。依据两类论文以及 RPent 冻结 L1 / DEV1A 的既有研究合同。  
> **协作约束**：此文档单独提交，不修改正在运行的 Agent 所维护的 `CURRENT_STATE.md`、`DECISION_LOG.md`、`AGENTS.md`、实验代码或 manifest。文中未来的实验均需另行冻结条件与批准预算；**当前仅 D-041 的 DEV1A ≤8 episode / ≤3 GPU·h / ≤4h wall / 单 worker / 受控 lift ≤2cm 在 G1–G4 PASS 后有条件获准**。DEV1B、World Model 训练、OPD 与真实机器人均未获本文件授权。

## 0. 研究定位与证据边界

**总研究问题**：具身 Harness 面对物理执行结果不确定、验证资源有限时，能否**选择性地预测可能的状态变化、主动获取真正有决策价值的时间对齐证据，并从有独立参考的经验中学习更好的验证行为**？

建议的统一叙述：**Time-Aligned Evidence Acquisition → Budgeted Selective Verification → Governed Foresight → Evidence Evolution**。各环节是可被独立证伪的研究问题，**不预设最后必须整合成一个大模型或多 Agent 系统**。

### 已有 RPent 实证（只作为背景，不当作新阶段效果）

- 冻结 A0：206 PRIMARY Pick 中的工具失败与技内 `FGONLY` 代理存在时点不一致；在原 56 个“工具 FALSE / any-time FGONLY 正”中，**26 个在 final_meas 仍正、30 个仅中途正**。因此证据的时间与构念有效性是先决条件。
- 对 103 个工具失败例，合法且零拟合的 **GATE_ONLY** 在 Top20% 复核预算下仅对**末端运动学弱代理**得到期望 13.26/21、Precision≈0.632；旧 `LMG` 17/21 的组成及跨任务效应需要进一步分辨。Task9 D-only 19 例的静态分数无法建立稳健的类内区分力。
- `task_id` 的旧 L1 值来自 `reconstruction_metadata`，并未证明在实时决策点合法可见；事后匹配的 14.48/21 是组成效应对照，**不是独立可执行标签盲分配器**。
- DEV0 的 5 次 Probe 无同刻独立接触/持握参考；在上次源码复核时 DEV1A 的原生双指—目标接触 RPC、真实 G1–G4 仍未验收。应以并行执行 Agent 的新报告更新当前状态，**不能通过此路线图判定 Gate 已通过**。

> **论文来源**仅支持可借鉴的方法；**RPent 实证**支持问题动机；下文 **H1–H4 是待验证假设**，不能写成目前的成果。

## 1. 两类论文分别带来的方法论 Insight

| 研究来源与已提出的问题 | 可借鉴 Insight | 转化为 RPent 的可证伪问题 |
|---|---|---|
| **Current Agents Fail to Leverage World Model as Tool for Foresight**：Agent 可能很少调用模拟，或误解/误用预测；“可以调用”不等于有效利用 | 对**何时调用（Invocation）→ 如何解释（Interpretation）→ 怎样影响决策（Integration）**建立独立治理机制 | **H1**：选择性前瞻相对“永不预测/每次预测”，是否在同等成本下提高实际决策效用与风险表现？ |
| **VAGEN**：区分当前状态估计与未来状态转移，显式训练世界建模 | **State Estimation** 与 **Transition Modeling** 分开评价 | **H2**：同刻观测能否先正确区分接触/支持/脱落，再可靠预测某个候选验证动作的状态变化？ |
| **ViewAgent / Planning with the Views**：从真实视角转移经验累积图，再蒸馏为可用的规划能力 | 优先积累**可审计的经验转移**，而非一开始生成长视频 | 低成本经验式短时转移/前瞻工具能否比静态末端证据提供独立信息？ |
| **OPD-Evolver**：存储经验之外，还须学习选择、使用、写入和维护；Fast memory + Slow OPD | **经验生命周期**与 **privileged hindsight / on-policy distillation** 分开 | **H3**：经过核验的证据经验是否能稳定减少重复/无效验证？**H4**：能否把这种能力从显式 Memory 蒸馏到只读合法观测的 Student？ |
| **ReasoningBank**：成功与失败经验均可能可复用 | 显式记忆检索应先作为低成本强基线 | 冻结模型加经验检索是否已足够？OPD 的参数化收益是否超过新增训练/维护成本？ |

**限定**：世界模型输出是**对未来的假设**，不是已观察的事实；sim 的特权真值只能走审计或离线 oracle upper bound，不能直接进入部署时的模型。OPD Teacher 即使看到 hindsight，也不能强迫 Student 猜测合法观测中本质不可辨的信息：应允许 `UNKNOWN/ABSTAIN`。

## 2. 核心研究假设与停止条件

| 假设 | 关键比较 | 成立时支持什么 | 失败时如何收敛 |
|---|---|---|---|
| **H0 Evidence Validity**：同刻、目标特定的物理参考是可获得的 | 合法观测 vs audit-only 目标/双指接触、支撑与短窗 retained；对照旧 any-time reference | 可以开始评测实际持握识别和主动观测 | 无原生 geom contact、无正负类别或时间戳失配：**STOP 物理准确率主张**，回到数据采集与接口有效性 |
| **H1 Selective Foresight**：有选择的前瞻优于无/强制前瞻 | 从不调用 / 固定频率强制调用 / 按决策关键性调用；相同信息和预算边界 | Agent 学会**何时预测**，而非只会多调用工具 | 如果真实动作决策不变或净效用不改善，停止扩大 World Model |
| **H2 Action-Conditioned Evidence**：追加观测能提高决策信息而非仅改变机械状态 | no probe+blind / same probe+blind / same probe+evidence；lift 单独做 same-lift+blind 对照 | 可归因主动观测与时间对齐证据的增益 | 仅机械扰动有效或真值不可区分：不把它写成感知创新；更换观测方式/减少物理 probe |
| **H3 Evidence Memory**：经物理核验的经验可跨任务复用 | 无记忆 / 原始轨迹检索 / 核验经验检索 / 有管理（更新、冲突、过期） | 学到**哪类证据何时有用**，降低重复验证开销 | 跨任务退化或错误记忆累积：冻结写入与检索，优先解决归因、冲突、遗忘 |
| **H4 OPD Internalization**：OPD 比显式检索/SFT 更能内化证据选择策略 | 同底座同数据预算：Frozen / Retrieval-only / SFT / On-policy Distillation | Student 在未知任务上以更低成本选择、验证和弃权 | 无独立增益或 oracle 信息被模型泄漏学习：停止 OPD，退回轻量 Memory 或规则 |

**优先检验 H0→H2→H1→H3→H4**。H0 不满足，不启动任何声称物理策略有效的研究；H3 的显式 Memory 基线未建立之前，不急于做 H4。

## 3. 后续实验阶梯（仅研究层级，不是实现指令）

### E0 · DEV1A：构造可信的物理证据与状态转移

**与当前 D-041 对齐，已在独立 Agent 流程中执行预检/开发。**

- **问题**：在 `t_pick_return → t_close_end → t_lift_end`，合法 RGB/proprio 和 audit-only 目标接触/支撑/retained 是否真正同步、可辨识且不泄漏？
- **最小产物**：事件—动作—时点—来源对应的数据合同与操作性物理标签；必要的 `UNKNOWN`；动作和信息成本；中止原因。
- **主评价**：有效标签覆盖、正负类别可达性、对齐率、泄漏异常与 GPU/物理步预算。**不是成功率提升、模型准确率或多臂因果实验。**
- **Gate**：完全遵守 D-041；只有真实 G1–G4 PASS 才能使用批准的最多 8 Episode。必要时 0 Episode 收官。D-041 指明下一新 cohort 候选至少需要 2 个 `RETAINED` 与 2 个 `NOT_RETAINED` 的可验证样本及零预算/泄漏/时点异常。达不到即暂停扩展。

### E1 · Time-Aligned Selective Verification：验证信息是否真正有用

**另立新 cohort/授权，不能用 DEV1A 的 8 例推导因果收益。**

- **RQ**：新增同刻证据是否比旧 Tool/GATE_ONLY/无额外观测更可靠地指导确认、重试或弃权？
- **关键对照**：原工具 blind；无动作重拍；`same-probe + blind`；`same-probe + legal evidence`；必要时 proprio-only 与 RGB+proprio。**机械效应 vs 信息效应拆开**。
- **结果**：独立接触/retained 下的 risk–coverage、`UNKNOWN`/abstention、成本；当真正允许策略动作分歧时，评估同一固定 H 物理窗的 ITT outcome。不能把 shadow-action 分歧当物理收益。
- **判据**：只有加入的观测在相同机械行为、相同成本（或净效用口径）下提供增量，才能保留 Evidence Acquisition 为方法核心。

### E2 · Governed Foresight：把 World Model 作为有成本的工具

**以 E1 中可靠的证据和独立状态转移积累为前置；暂不训练大型视频世界模型。**

- **前瞻对象**：先预测短时 `contact / supported / retained / slip / evidence change` 等**假设状态分布**及不确定性；可先使用经验式转移模型，再讨论 learned World Model。
- **调用对照**：不调用 / 每次调用 / 选择性调用；有无预测置信度与失效/过时治理；若用 sim oracle，仅可作为**离线分析上界**。
- **必须评价三层**：调用是否在决策关键处发生；预测是否可信且校准；预测实际有没有改变合法后续决策、并提高成本约束下的物理效用。
- **成本约束**：把预测推理耗时、主动观测、夹爪动作、提升风险分开核算。模拟很逼真但不能提高 action value，也视为该方案无增益。

### E3 · Evidence Memory：不训练权重的快速经验演化

**在 E1/E2 有足够独立验证轨迹后开始。**

- **记忆候选**：Trajectory（完整证据链）→ Tip（适用条件与失败教训）→ Skill（可审计验证流程）→ Tool（可重用的验证接口/模板）；分层只是研究假设，不要求一次实现全部。
- **Fast Loop**：Select / Use / Write / Manage 四种能力独立开关消融，记录每条经验的来源、置信度、覆盖范围、适用任务、反例、失效条件。
- **关键对照**：Frozen、Raw trajectory retrieval、Verified memory retrieval、+memory management。用跨任务/新物体连续评估，看验证预算、错误重用、遗忘与维护成本是否变好。
- **经验价值归因**：被检索/使用过不等于产生收益。用一致的独立结果和可比较任务，尽量构造“采用与未采用”的对照；无法消除选择偏差时只能报告相关性。

### E4 · OPD-Evolver：慢循环内化证据选择与维护

**只有 E3 的显式经验基线有效，且独立有标签 On-policy 数据足够时才开始。**

- **Student**：输入仅包含决策时实际可见的 Tool、同步视觉/proprio、合法经验；学习“要不要验证、选哪项验证、何时弃权、何时使用/更新经验”。
- **Teacher**：训练时可获得经过验证的 hindsight（最终接触与 retained、失败分支、成本），但这些 **privileged 参考绝不直接传给部署 Student**。
- **对照**：Frozen、Retrieval-only、普通 SFT、OPD（同训练预算与底座）；先检验验证选择/弃权与泛化，再讨论完整四能力联合演化。
- **重要负例**：模糊场景应被教导返回 UNKNOWN 或请求观测；若 Student 仅因训练学会重现不可由合法观测推断的 oracle 标签，视为泄漏/过拟合，不能判 GO。

## 4. 全路线统一评测与防混淆原则

1. **物理状态**：目标特定双指 contact、支撑、提升后短窗 retained 分开评估；任何旧 FGONLY、Tool flag、Planner think、最近深度表面都不是替代物理真值。
2. **时间与来源**：观察时点、世界模型预测的目标时点、物理动作时点和后续 outcome 评价 H 必须分离；记录滞后、失配、缺失与 UNKNOWN。
3. **验证效益**：报告触发率、选择率、实际执行分支、误接受、漏检、拒绝/弃权、覆盖率；不允许永不 CONTINUE 或全部 ABSTAIN 赢得“零误判”。
4. **预算**：同等 Episode/环境步/动作危险性/推理成本/墙钟/GPU 口径；比较全成本下 risk–coverage、utility–cost Pareto。预测与物理探测的成本不可混为一谈。
5. **可归因性**：同机械 probe 的 blind vs evidence 才能回答信息效应；no-probe vs same-probe blind 回答机械效应；World Model 调用与 Student 参数改变必须作为单独因素。
6. **泛化与选择偏差**：冻结训练/验证/test 的 task、object、episode 切分与模型/记忆版本；此前206/103/19反复做过方向选择，不能继续当新的 held-out 确认集。
7. **安全与权限**：在线决策只能见 legal evidence，audit-only/hindsight/仿真隐藏状态仅服务离线标签与 Teacher；未来任何新仿真/训练/实物实验仍须相应阶段独立预注册与授权。

## 5. 实验结果驱动的分流（避免重复“写方案”）

| 新数据出现什么结果 | 下一步唯一优先选择 | 暂停什么 |
|---|---|---|
| E0 无同步独立物理标签、接触 RPC 缺失、预算不受控 | 只修数据/标签/执行基础，报告 0 新 episode 也可接受 | E1–E4，所有 held 性能主张 |
| E0 合格但 E1 的主动观测相对 blind 无增量 | 聚焦观测可辨识性或低成本 passive evidence | 训练 World Model/OPD |
| E1 有可靠信息价值，E2 选择性模拟无法改进决策 | 保留 budgeted verification，研究模拟可靠性/拒绝条件 | 强制模拟与大型 World Model |
| E1/E2 效益成立，E3 显式 Memory 失败 | 单独研究经验有效期、冲突、归因 | E4 OPD |
| E3 Memory 有益，但 E4 相对检索/SFT 无增益 | 保留显式 Memory 与选择性工具治理 | 进一步扩大 OPD 训练 |
| E4 在独立任务下稳定改善效用/成本 | 才考虑完整 Fast–Slow 共演化 | 用同一训练集自证泛化 |

## 6. 候选论文叙事（不是已经证实的贡献）

- **主线**：*Decision-Critical, Time-Aligned, Cost-Aware Physical Verification for Embodied Agent Harnesses*。最小可独立成立的贡献是**来源可信的证据获取+机械效应剥离+风险/成本评价**。
- **后续机制**：*Governed Foresight for Embodied Tool Use*。贡献必须来自 **Invocation / Interpretation / Integration** 的真实决策改进，不能仅增加预测工具。
- **长期延伸**：*Evidence-Grounded Agent Evolution through On-Policy Distillation*。贡献是物理核验经验的选择/复用/维护/内化，必须有比显式检索和 SFT 更强的跨任务结果。

### 文献索引（论文结论与本项目推导分离）

- Qian et al., **Current Agents Fail to Leverage World Model as Tool for Foresight**, ACL 2026. https://aclanthology.org/2026.acl-long.623/
- Zhang et al., **OPD-Evolver: Cultivating Holistic Agent Evolver via On-Policy Distillation**, arXiv:2606.17628 (2026). https://arxiv.org/abs/2606.17628
- Wang et al., **VAGEN: Reinforcing World Model Reasoning for Multi-Turn VLM Agents**, NeurIPS 2025. https://github.com/mll-lab-nu/VAGEN
- Wang et al., **Planning with the Views** (ViewAgent / ViewSuite), 2026. https://viewagent.github.io/
- Ouyang et al., **ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory**, arXiv:2509.25140. https://arxiv.org/abs/2509.25140

### 后续使用方式

当 DEV1A 的真实报告完成时，**先从 E0 的证据可达性与数据边界更新本路线图适用条件**，再决定是否独立预注册 E1。此文档只作为研究判断参考；不可被 Coding Agent 当作已经批准新增 Episode/训练/Runtime 接线的执行任务。
