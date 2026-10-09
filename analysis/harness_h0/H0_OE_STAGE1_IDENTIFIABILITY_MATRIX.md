# H0 Direction 1 · Stage 1 可辨识性与证据权限矩阵

> 2026-10-09 | **协议设计附件，NOT A DATA AUDIT**。与 [H0_OE_STAGE1_RESEARCH_PROTOCOL.md](H0_OE_STAGE1_RESEARCH_PROTOCOL.md) 配套。
> 用户批准的只是阶段一研究协议设计；本文件只综合既有报告描述，**没有打开原始 CSV、没有检查原始时间戳、没有拟合或检验**。需要现场数据核验的一律标 TO_VERIFY。

## A. H-OE1/2/3 研究对象映射与最小识别条件

| 老草案目标 | 可审查的新 estimand | 已有报告提供的证据 | 原草案致命风险 | 文档级识别判断 | 必须停止/降级的条件 |
|---|---|---|---|---|---|
| H-OE1「ACQ 假阳≥30%，STABLE 假阳 <10%」| **OE1a**：同 trial 的 ACQ/STABLE 接受率差、联合分歧、ACQ 已接受情况下 STABLE 不通过的条件分歧；**OE1b**：有独立未来参考时的误接受 | H0 §1.2 仅报告逐 trial 两个布尔契约与现有 gap；未证明独立未来参考 | STABLE 当信号又当 truth 会循环得到零 FPR，gap ≠ 独立假阳 | OE1a: **DESCRIPTIVE_IDENTIFIABLE (schema TO_VERIFY)**；OE1b: **NOT_IDENTIFIABLE ON DOCUMENTED FIELDS**，除非后来发现独立 reference | 无时间独立的 reference 或无合法决策时代理 → OE1b STOP，只允许 contract-disagreement |
| H-OE2「h(k) 与 pooled iid 不同证明连败历史新信息」| **OE2a**：重建 S_pre 的下一次尝试条件成功 `h_a(k+1)`；**OE2b**：M1 异质性之上的次序额外价值 | Stage R §5.3 原有经验 h(k)，H0 §1.2 报告完整臂数据；R0 PREFIX 一致性验证 | 同质 pooled q 忽略异质性/风险集选择；sham 在 n=8 下可能低功效 | OE2a: **DESCRIPTIVE_IDENTIFIABLE (ordering TO_VERIFY)**；M1 参数/顺序 M2: **CONDITIONAL_IDENTIFIABLE** | 无可信 trial 次序→只做 exchangeable count 风险，M2 不可检；零显著结果只作 INCONCLUSIVE |
| H-OE3「最小 k 次判断事件是 E/P」| **OE3a**：给定 1..k 次失败，对严格未来 k+1..k+m 次中的 STABLE 成功进行回顾性预测；**OE3b**：决定预测资格与弃权所需条件 | Stage R per-event 每臂 K=8；P=5 全 t9；原报告没有独立的新样本 cohort | 完整 8+8 既是 E/P 标签定义又包含前缀，事后 label 泄漏、选择过拟合 | OE3a: **CONDITIONAL_IDENTIFIABLE**，须确认顺序、事件隔离与留未来 suffix；绝对「E/P latent 分类 n*」: **NOT_IDENTIFIABLE** | suffix 不可配对/事件数不足/预测目标包含自己的前缀 → 不可判 `n*`，仅描述 |
| H0 总体「支持 Runtime stop / Evolution promote」| 只输出 **offline research-only evidence** 的适用范围、证据缺口与不确定性 | MCF v0.2.2 §5.6 明确字段可见性与双门权限 | 把离线 `S_pre` 的研究真值当在线 `S_post` 的动作授权/因果技能更新 | **OUT_OF_SCOPE**（本轮及后续离线统计本身都无权限） | 任何希望在线 rollout、生成控制代码、插入系统执行链的请求都须 STOP 并另行授权 |

**标注说明**：
- **文档级可辨识 ≠ 当前 CSV 已经通过字段核验**。即使 OE1a/OE2a 是 `DESCRIPTIVE_IDENTIFIABLE`，字段正确性、独立性、缺失与原始顺序都未确认。
- **同源接受率差**可报告，不能用它代替“未来独立失败预测能力”。
- **统计预测有效**与**决策合法可消费**相互独立，研究中使用的离线 privileged outcome 永远不自动拥有 Runtime/Evolution 授权。

## B. 来源、可见性、统计用途与许可

| 来源 | 已有报告能支持的事实 | 可在未来获批准的科研分析中使用？ | 当前 Runtime 可消费？ | 当前 Evolution Gate 可消费？ | 当前状态 |
|---|---|---|---|---|---|
| 已合法观察的本轮 RGB/proprio/tool 输出 | METHOD_SPEC §3 的候选代理；观测代理是否全量留在 Stage R 文件尚未知 | 是，若留档并核实 provenance | 仅当真正在当前时刻可得 | 经账本合法投影，仍需 D2 充分证据 | **字段存在性 TO_VERIFY** |
| SAME/POLICY 重建双臂 8+8 的 STABLE/ACQ | H0 §1.2 宣称在档；Stage R 冻结 outcome 定义 | **可**作为测量科学真值/结果，在批准后离线分析 | **否**，完整双臂属离线实验 | **不能自动**；需独立证明每个 outcome 来源合法 | **研究性可用性 TO_VERIFY** |
| 任意时刻 `sim check_success`/对象真值 | Stage R 研究仪器可记录，线上不能读取 | 可作**科研参考**，不得冒充线上代理 | **否** | **否**（research_audit_truth） | 审计专属 |
| Stage R 的 E/A/P/U 事后标签 | 24 个事件 E14/A1/P5/U4，冻结按 8+8 定义 | 可作**描述性分组**，不能作独立 latent truth | **否** | 若来自 privileged 真值则**否**，本阶段未证其他正当证据链 | 冻结、不可重分类 |
| PREFIX_REPLAY 原始哈希/重建元数据 | Stage R R0 32/32 哈希一致（仪器），不证明执行因果可交换 | 可作**可比性限制或分层** | 不能作为当前自然动作状态 oracle | 只能降低/限制可信度，不能创生结果真值 | 仅重建契约 |
| NATURAL_RETRY 的 S_post | Stage R 描述臂；原报告强调 approximate | 科学描述可用，不允许作为 persistence 对照 | 不等于从当前在线 S_post 继续的独立测量 | 不能推断 skill-edit repairability | 描述-only |

## C. 事件划分与目标独立性的审阅标准

1. **事件入组条件**：第一次 `FALSE_GRASP` 用于筛选，不可再当一条新复验 trial；报告明确写 `P(· | entered stable FG cohort)`。
2. **时间切分**：OE3 的输入至多 `1..k`，结果严格是 `k+1..k+m`；同一事件后缀在预测时不可泄漏给先验训练和超参选择。
3. **训练/评估切分**：即使今后获准可计算，事件所有试次应按 `event_id` 整组隔离，不做 random row split；历史 Stage R 结果已公开，不能伪称全新盲测。
4. **臂与任务**：分别报告 SAME/POLICY，任务 `t3/t5/t9` 为不平衡层级；P 全 t9，不得跨任务族承诺精确误差控制。
5. **模型对照**：M0 pooled iid 只是弱基线；M1 事件难度分布必须是必要对照；M2 顺序依赖不能由 `h(k)` 低于 pooled q 直接推出。
6. **已有执行预算**：0 新 env boot、0 rollout；未来纯离线统计上限若另行批准，参考 H0 原建议 ≤2h CPU/并发≤4，但本阶段没有运行预算，因为 **不允许运行**。
7. **研究 vs 授权**：即使未来后验/置信区间达到冻结标准，也只代表受限于 `S_pre` 数据分布的科研结论，不自动授权 Runtime `REPORT_FAILURE` 或 Evolution `PROPOSE_REVIEW`。

## D. 本阶段的可验证问题和未核验标记

| 标记 | 需要后续经批准才可做的核验 | 没有它的处理 |
|---|---|---|
| TV-1 | ACQ/STABLE 是否在**同一个 trial**有配对字段？定义相同测量时刻还是有可分离未来窗口？ | OE1 只解释旧 gap，不能创设独立 reference |
| TV-2 | 是否保存完全可信的 event_id/arm/trial_index/chronological_order 与缺失/INFRA 标记？ | OE2/3 暂不执行序贯估计 |
| TV-3 | 合法 Agent 代理观察有没有带事件时间的历史存档，与 sim-only truth 如何字段隔离？ | Evolution Gate **NOT_AVAILABLE** |
| TV-4 | 24 事件、P 全 t9 的样本量在预先指定的任务范围与错误损失下是否足够？ | 无精确 n*、只给 INCONCLUSIVE |
| TV-5 | R0 PREFIX_REPLAY 的 state hash 与实际物理 transition 可比性有没有跨臂/任务局限？ | ρ 不可直接用 Stage Q 10/14；仅做保守限定 |

**本阶段没有执行 TV-1..TV-5，以上任何未标记为已证事实的地方都不表示已通过。**

