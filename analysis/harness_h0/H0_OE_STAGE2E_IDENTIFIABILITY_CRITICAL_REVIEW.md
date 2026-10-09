# H0 · Stage 2E 证据独立性与代理复算可行性审查（CRITICAL REVIEW）

> 2026-10-09 · `READ_ONLY_METHOD_REVIEW / NO_STATISTICAL_EXECUTION / NOT_A_PREREGISTRATION`  
> 基线：`ce7d3923ffefbec1d24744bc93001ee143901cf1`，重点审查 `H0_OE_IDENTIFIABILITY_GAP_REVIEW.md`。  
> 本审查复读 GitHub 已跟踪的源码/研究文档；不读取本地 CPS/未公开文件，不重新读取/计算 Stage R outcome 数值，不运行模型、模拟、rollout、训练或 runtime。  
> 原 Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、Stage 2C frozen v1 与 Stage 2D 结果均不变。本文件是**追加审计意见**，不追改旧报告。

## 0. 结论

**裁决：前一份可辨识性审查的“现有数据原则上无法构成任何无泄漏验证”结论过强，且“从 Stage R CPS 精确重算原始 `pi0_pick` success”尚无实现等价性保证。**

已成立的、较窄结论：

1. **Runtime / Evolution 资格仍为 HOLD**。Stage R 的 `stable/acquisition` 是仿真研究真值，且缺少已验证的在线决策时代理映射与独立未来实验队列。现有 Stage 2D 的回顾性 M0/M1 对比不能直接用于在线 Gate。
2. **有限的、同一轨迹内“时间有序代理 → 未来仿真结果”的离线方法研究，在原则上可能成立**。同一仿真环境、同一物理事件不自动造成预测标签泄漏。需要明确冻结切点、代理仅使用切点之前的合法信息、参考标签仅从切点之后的特权测量构造、模型/阈值不在评估事件未来数据上调优。现有 CPS 是否能严格满足这些要求仍须后续有权审计；不声称当前已有这样的结果。
3. **这种分析只会给出 simulator / reconstructed-`S_pre`、specific continuation protocol 下的回顾性代理有效性**。无法代替 prospective 独立队列、真实 `S_post` 连续执行泛化、物理因果或 Runtime 许可。
4. **原先的候选 B（“按 `pi0_pick` 判据重算 pick flag”）需要先做语义等价性 STOP 审查**。Stage R continuation 与在线原始 `pi0_pick` 的执行和早停规则不同，不能将一个新代理命名为已验证的原始 pick flag。

因此，应在选择“C 收官 / B 离线 / A 采集”之前增加一次**零统计的离线可辨识性与语义等价性 Gate**。若 Gate 不通过，保留 `NOT_IDENTIFIABLE_ON_AUDITED_ASSETS`，无需为了产出正面结果新增数据或放宽契约。

---

## 1. 四种独立性，不能混为一个要求

| 维度 | 必须审查的问题 | 对本仓的含义 |
|---|---|---|
| **信息与算法隔离** | 代理是否直接读取标签、其派生值，或未来数据？ | `A(t)` 仅使用在线可见的 RGB/proprio/tool；禁止以 `check_success` 或 sim object pose 构造代理 |
| **时间方向** | 标签是否来自预先固定切点之后的未来测量？ | 可以用相对 chunk index 定义研究窗口；缺绝对时钟意味着不能可靠声明 `T` 秒后 |
| **评估隔离** | 参数/阈值/窗口是否在评价事件的未来结果上选择？ | 已知 Stage R 结果的 retrospective 冻结不等于独立 blind TEST；跨事件拆分与事后选择必须明确 |
| **测量与域外有效性** | 物理标签能否作为明确构念的参考，数据能否代表部署分布？ | 相同 sim 轨迹的非特权观测与特权未来标签可以用于有限的模拟器代理审计；**不能**因此主张独立现实传感验证、真实机器人迁移、自然 `S_post` 或部署保证 |

**关键方法学区分**：标签与特征来自同一个物理过程是有监督评价的常态，且二者本就应对同一事件有物理相关性。“统计独立”“传感器独立”“时间隔离”“无标签泄漏”“独立外部测试集”是不同性质。  
倘若同源的含义是**标签直接重用了被检代理的判定逻辑**，才有典型循环验证风险。例如 `episode_terminated` 与 `check_success` 基于同一任务成功谓词，不能称两份独立物理裁决。  
如果先从允许的 proprio 形成 `A(t)`，再在独立的未来 chunk 中以特权物体保持状态构造 `Y(t+H)`，方法上可进行**已知限域的回顾性预测评价**；即便所有数据来自同一个仿真 episode，也不必自动判为“泄漏”。但该 `Y` 是否可用、标签具体构念是否包含观测期间的早期真值、采样路径是否受 `A` 影响，都必须审查。

## 2. 已查源码中的可操作切点及其限制

### 2.1 `scripts/stageQ_rt.py:274-302`

`exec_from_current` 先保存 `base`，执行冻结 candidate chunk，再保存 `post`，之后 continuation 在 chunk callback 逐点追加 checkpoint，并在尾部再采一次。  
这提供了**严格先后次序**：`base → candidate-post → continuation checkpoints → terminal`。因此可以在**规范层**提出 `candidate-post` 决策切点以及后续 chunk 相对窗口 `H`。缺绝对时间戳限制“固定秒数”的 claim，不自动抹除 chunk 顺序。

限制：
- `terminated_in_chunk` 时的 continuation 与正常持续执行长度不同；短轨迹与缺失未来窗口不能临时当作失败或删除，应在未来分析协议中预先处理。
- `cps` 存的是 instrument 对象，并未原样存档 Planner 的全部图像/模型 segment 输出；**具有某些数值相似的 proprio 字段不等于完整的决策时代理已实际输出**。
- `STABLE` 的现有冻结函数使用从初次 `_confirms` 起的记录及 `any(check_success)` 早放行分支，不能未经重新定义就当作“仅在切点后观察的未来持续保持真值”。新未来标签若要形成，须另立研究目标与版本，**绝不覆盖冻结 STABLE 或 Stage 2C 统计结果**。

### 2.2 `robots/libero/tools.py:151-166, 201-270` vs `scripts/stageQ_rt.py:186-220`

真实 `LiberoPrimitives.pi0_pick` 的成功判据至少包含：
- 从原 pick 开始记录的 `start_z`；
- 向下位移 ≥ 0.10m 的 `descent_done`；
- 最低点之后的上升 `post_min_peak_z-min_z ≥ lift_thresh`；
- `grip < gripper_closed_thresh`；
- 条件满足时**提前 break**，或 terminal/truncated 分支覆盖结果。

但 Stage R 调用 `scripts/stageR_rt.py:200-218` 的 `exec_trial`，后者复用 Stage Q 的 `exec_from_current(...,r_cont=1)`。该路径先执行**单个 candidate chunk**，然后 `run_continuation_hold` 从 candidate-post 状态重新初始化 `min_z`；函数检查 ascent+closed 并将成功 latch 置位，**没有原始 `pi0_pick` 的 `descent_done` 条件，也没有成功即 break 的行为**。

所以 `stageR cps` 不足以自然推出“在线 `pi0_pick` 会在相同时间点返回 success”。即使记录了某些 z/grip 采样，它也是**另一套已执行轨迹与返回语义**。不能用事后 `pi0_pick` 条件重算，声称已验证在线 flag 的实际假阳率。

**现有候选 B 的必要修正**：把待测信号暂称 `CPS_KINEMATIC_PROXY_CANDIDATE`（纯研究性、不可在线消费），先行判断其与原工具 flag 是否等价；如果不等价，可设计“针对当前 Stage R hold-through 协议的候选代理质量审计”，并明确禁止以“原工具 flag”命名。这是新的描述性对象，不应冒充原始在线判定算法的复现。

### 2.3 `scripts/stageR1_run.py:137-157, 164-230`

`record_trial` 先把 `exec_trial` 返回的 cps 写入 `stageR_trial_checkpoints.jsonl`，CSV `stable/acquisition` 与派生字段另记；每次 SAME/RESAMPLE 重试都从 `S_pre` 重建，顺序固定 SAME→RESAMPLE→NATURAL。  
因此即使在一个 trial 内有时间有序的 future reference，也**不能**把 event 中第 j 次重试当成从上一试次终态持续推进的物理后果。  
现有 CPS 未来片段的构念最多是**S_pre 重建 + 指定 hold-through 策略**的后续结果，不代表在真实 runtime 中“观测后是否继续重试”的反事实收益。

## 3. 两个可被独立审查的科学目标

**R-T1：回顾性同轨迹、时间有序代理审计（仅设计候选）**

给定 trial 的候选切点 `t_c`，`X_{≤t_c}^{legal}` 从可重建且不含特权字段的 proprio / 已落盘图像或工具输出构造；`Y_{>t_c}^{audit}` 则来自未来若干 chunk 的仿真审计真值。只评估已发生 trajectory 上此类代理与研究性 future target 的关系，明确 arm、执行方式、时间单位、后验选择和可读字段限制。

必要前置：逐字段确认实际 CPS 的样本位置、代理所需 z/grip 轨迹及真实 pick 返回值能否区分；严格切点对应不依赖未来；未来窗口可得性与 `terminated_in_chunk` censoring 规则；参考标签不能使用切点前值来循环证明未来效果。

可能输出：
- `RETROSPECTIVE_TIME_ORDERED_PROXY_AUDIT_FEASIBLE`（仅可提出预注册，仍未统计）；
- `PARTIAL_ONLY_WITH_UNMATCHED_SEMANTICS`；
- `NOT_IDENTIFIABLE_ON_AUDITED_ASSETS`。

**R-T2：Prospective 跨队列与在线可消费性（另立研究，尚无数据与权限）**

预先冻结合法观测代理、其输出时刻和决策/观察预算，在新队列上独立测量未来目标并按 event 分组评估。这样才有资格探讨跨分布可信度、未来窗口校准/误报与 Runtime/Evolution 的证据适用边界；即使成功，也**不自动**获得 Runtime 权限、更不证明因果修复或策略获益。

## 4. 零统计的下一步 Gate（建议优先于候选 A/B 运行）

1. **逐源码判定** `pi0_pick` 与 Stage R `run_continuation_hold` 在启动位置、最小点维护、descent gate、早停、episode terminated、返回/记录时点上的差异，逐项 PASS/FAIL。禁止把二者直接设为等价。
2. **列出 CPS 相对时序**：candidate-post 之前/之后具体有哪些已保存字段，未来窗口是否能只用后续 cps 构建；在文档里仅检查结构，不统计 outcome。
3. **画出严格 leakage firewall**：代理可用字段、`check_success` 与 `obj/pos` 特权字段隔离、目标窗口、`S_pre/S_post` 边界、训练/评估事件隔离。
4. **裁决候选 B 的命名和对象是否需修订**；没有 source-equivalent 原工具代理，就拒绝“pick-flag FPR”命名；即使有可研究 proxy，也不称独立外部验证。
5. **保留独立未来队列缺失**的明确判断：目前尚无 prospective independent held-out performance evidence。任何想确认泛化/真实在线效果的结论继续 `HOLD`。

**STOP**：字段缺失、阶段对齐不可恢复、需要凭未来真值构造当前代理、无可复核的物理 target 窗口或继续工作要求新 rollout/训练/runtime 改写 → 仅报告缺口，不执行数值实验。

## 5. 对前一份报告的精确勘误（不原位覆盖）

| 前稿表述 | 当前审查 |
|---|---|
| “A 与 B 同轨迹，所以任何无泄漏验证不可构成” | **需要收缩**：同轨迹不自动意味着泄漏。可研究是否存在严格分离的切点与未来 suffix，仅限回顾性模拟器测量 |
| “C 层完全不存在，因没有绝对时间戳” | **需要区分**：无固定秒数参考是事实；同 trial chunk 顺序作为相对未来候选已有源码依据，但尚未构成已验证独立 benchmark |
| “现有 CPS 可重算 pi0_pick success” | **存在语义阻断**：Stage R hold-through 与 pi0_pick 有重要差异，最多先设计研究性运动学代理，禁止冒充原工具输出 |
| “ACQ 同信息集上界、STABLE 下界” | **需限定**：两者是特权嵌套操作契约，接受率存在数学大小关系；对在线代理的测量精度/可信度不构成自然上下界 |
| “研究价值=NO、默认 C 收官” | **策略判断可保留为谨慎选择**，但“无法做有限时间有序回顾研究”目前未由数据逻辑必然推出；应先通过零统计 Gate 决定 B 能否正确命名与研究 |

## 6. 独立性/创新性/授权结论

- 当前新发现是**先前审查的科学方法与工具语义修正**，不是新的 VLA algorithm，也没有正向性能结果。
- 没有获得可用独立跨队列未来参考、在线具身行为因果效应，`novel_algorithm_established=false`、`runtime_evolution_eligibility=NOT_AUTHORIZED`、`causal_grade=UNIDENTIFIED` 保持。
- 本文没有读取私有 `stageR_trial_checkpoints.jsonl`、没有据其计算任何新统计，也未重新运行已有结果分析；下一步如要用 CPS 的实际内容必须先独立明确授权、冻结专门分析协议与来源 hash。
- 原 `H0_OE_IDENTIFIABILITY_GAP_REVIEW.md` 是历史审计快照，不应被静默改写；本文件为追加批判性审查，处理逻辑争议并继续开放相应研究问题。

**最终：`CRITICAL_REVIEW_COMPLETE / RETROSPECTIVE_FUTURE_PROXY_IDENTIFIABILITY_CONDITIONAL / PICK_FLAG_EQUIVALENCE_NOT_ESTABLISHED / NO_NEW_EXECUTION_AUTHORIZED`。**
