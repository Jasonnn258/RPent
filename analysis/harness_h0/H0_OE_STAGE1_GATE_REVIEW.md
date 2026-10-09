# H0 Direction 1 — Stage 1 Protocol Gate Review

> 日期：2026-10-09 | 用户已明确批准**阶段一研究协议与可辨识性设计（不运行统计）**。
> 本次核验基线 RPent `e9f186e` (PAEG v0.2.2)、`DIRECTION1_PREAUTH_REVIEW.md` G1–G4、Stage R 冻结预注册/终报；交付 `H0_OE_STAGE1_RESEARCH_PROTOCOL.md` 和 `H0_OE_STAGE1_IDENTIFIABILITY_MATRIX.md`。
> **核验类型：研究文档的一致性审查（reasoning-only）**。没有打开原始 trial CSV、做任何数据统计、测试分析脚本/运行代码、创造新样本、做新实验或冻结数值阈值。

## 1. 阶段裁决

**GO_FOR_PREREG_REVIEW_ONLY（有条件）**。

**通过的只是**：H0 Direction 1 的研究问题现在有相互区分的 estimand、证据权限、识别边界与降级/停止路径，可以进入下一次**字段资格审核和正式预注册讨论**。

**没有通过、也不属于本轮**：字段级实际存在性；独立 reference availability；OE1 的未来误接受率；M1/M2 检验力；OE3 最优 `n*`；任何阈值冻结；离线真实统计执行；线上 Runtime/Evolution 授权；独立算法创新验证。

当下的方法学价值 = “可证明无法回答时及时停下 + 把可回答的研究对象正确命名”，还不能称“准确度/统计保证已经提高”。

## 2. G1–G4 独立审查对照

| 阻断 | 旧研究对象的问题 | 本阶段文件如何回应 | 门 |
|---|---|---|---|
| G1 自证假阳率 | STABLE 同时当信号与真值；原 ≥30% / <10% 基于同源契约易循环 | PROTOCOL §3 把 OE1a 同源契约分歧与 OE1b 未来独立误接受分离；无独立未来标签就 OE1b NOT_IDENTIFIABLE；MAT A 行 1 记录降级 | **PASS_PROTOCOL; REFERENCE_NOT_VERIFIED** |
| G2 E/P 泄漏 | 预测前缀包含于完整 E/P 标签定义 | PROTOCOL §5 目标为严格未来 `k+1..k+m` 的 STABLE，事件隔离；冻结 E/A/P/U 只保留描述用途；MAT C 的评估纪律 | **PASS_PROTOCOL; FUTURE_SUFFIX_NOT_VERIFIED** |
| G3 异质性选择 | 同质 pooled-q 偏差不能等于真正非可交换顺序效应 | PROTOCOL §4 M0/M1/M2 层次与事件单位，sham 结果仅在有效假设下解释；MAT A/OE2 | **PASS_PROTOCOL; MODEL_TEST_NOT_RUN** |
| G4 分布外推 | 冻结 `S_pre` 结果不能支持自然 `S_post` 重试或 Skill defect/repairability | PROTOCOL §1/§2/§4/§5 和 MAT B/C 将科学结果、观测合法性与门控权限分开 | **PASS_PROTOCOL; ONLINE_NOT_AUTHORIZED** |

## 3. 能识别与不能识别的明确判断

**当前可作为后来获批分析的候选对象**：
- **OE1a**：ACQ/STABLE 同 trial 的接受率差与分歧（依据 H0 已报告在档；不是独立假阳率），必须先确认行级配对与原始契约；
- **OE2a**：`h_a(k+1)` 的已失败 cohort、冻结 S_pre、同臂后续重建 trial 的条件成功描述，必须先确认有效顺序和缺失；
- **OE3a**：以独立于输入前缀的未来 suffix outcome 为目标的回顾性预测，必须先确认逐事件切分与足够数据，任何“训练并验证”都要整 event 隔离。

**现有文档不足以识别**：
- OE1b：真正独立的未来“Skill 已修复/稳定”假阳率；即使 `D_a^{discord}` 可算也不能冒名；
- OE3 原先的 E/P latent 识别和“精确最小试次 `n*`”；同一完整16试的 Stage R 标签无法作为独立 oracle；
- 在 `S_post` 自然连续执行、其他任务族/策略族、真实机器人上的在线控制收益；
- 从 P 型零翻盘直接得出“需要学习”“更换 Skill 就会成功”“绝对不能恢复”。

**身份问题**：Stage R 的 P 全部 t9，研究场景更接近“已失败后的条件风险测量”；任何跨任务/跨策略的泛化判定必须作为剩余问题，不能预先写 GO。

## 4. 按协议检查的七个关口

| 检查项 | 判定 |
|---|---|
| C1 — 研究问题、estimand 与 outcome 契约逐项定义 | **PASS** |
| C2 — 输入前缀与目标后缀明确区分、禁止使用完整 E/P 标签作预测真值 | **PASS（设计）** |
| C3 — M0/M1/M2 与 pooling/event/task 层次明确区分 | **PASS（设计）** |
| C4 — 观测权限、离线真值、恢复保真和 S_pre/S_post 不得越界 | **PASS（规范）** |
| C5 — 有限事件、t9 任务集中、回顾性研究不能伪称盲预注册 | **PASS（诚实性）** |
| C6 — 不可辨识/证据不足有独立降级及停止通道 | **PASS（设计）** |
| C7 — 实际日志字段/独立未来参考/功效/拟合结果 | **NOT TESTED（不在阶段一权限内）** |

上述 PASS 来源为**只读原有报告 + 草案逻辑比对**，不是“真实软件测试通过”；C7 不能以 C1–C6 代替。

## 5. 下一审批节点（本文件不具备冻结/执行效力）

**推荐单独批准的下一小阶段**：
> “批准 H0 Direction 1 Stage 2A：只读字段与 provenance 审计，并形成可审查的正式预注册草案。允许检查现有 Stage R 文件的字段定义、时间戳、样本完整性和权限元数据；不得运行结果统计、模型拟合/检验或选择阈值；不得冻结正式预注册；不得新增 rollout、执行代码、模型训练或在线接线。完成后停止，提交字段可用性和预注册资格报告。”

这能避免当前未核实的数据可得性成为未来统计研究的隐藏前提。**如用户不批准，项目保持 HOLD**。

**在 Stage 2A 完成之后**，还需用户单独批准正式预注册冻结；之后统计运行也须明确放行，不允许依靠本文件的 GO 直接执行。

Stage R §36 Hard STOP、S1-DEV0 ON_HOLD 以及冻结 E14/A1/P5/U4 均不改变。

## 6. 本轮执行核验与文件边界

1. 已新增两个研究协议文件及本审查报告，全部位于 `analysis/harness_h0/`；
2. 没有修改旧 `METHOD_SPEC.md`、`Stage R` 预注册/CSV、原始结果、模型和运行代码；
3. 没有读取/计算原始试次；所有历史数字来自既有报告，并明确是旧证据；
4. `research-sync` 的 NEXT_TASK / DECISIONS 将据此登记“Stage 1 完结、Stage 2A 等用户批准”，不创设下一阶段自动执行权；
5. 当下一阶段获批准时，优先直接复用本协议及矩阵的 `TV-1..TV-5` 字段审核事项，避免又扩写一轮泛化 Harness 架构。

**阶段一最终裁决：GO_FOR_PREREG_REVIEW_ONLY / HOLD_FOR_DATA_AND_EXPERIMENTS**。
