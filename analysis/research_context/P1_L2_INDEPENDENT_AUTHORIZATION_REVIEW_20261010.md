# P1 L2 独立研究审查与分级授权裁决（2026-10-10）

> **后续优先级勘误（D-041，2026-10-10）**：本文件为历史 D-040 较宽的 12 episode 预授权记录。用户委托之下完成进一步文献与预算可行性复审后，当前有效授权改由 `P1_L2_DEV1A_RESEARCH_REVIEW_AND_AUTHORIZATION_20261010.md` 与 D-041 界定，**新阶段硬上限缩为8集（t9×4/t3×2/t5×2），GPU≤3h、wall≤4h，G1–G4失败即0新集**。历史“最多12集”不得作为追加额度或补跑权，DEV1B效果实验仍HOLD。原审查全文留存溯源。



> 审查人：ChatGPT（基于用户“你自己替我审核授权”的本轮委托）。**权限解释**：本次用户已明确委托助手代表其作下一阶段研究授权审查。**裁决为新的独立 P1-L2-FEAS 有界仿真 pilot 预授权**（最多12个新 episode，≤3 GPU·hour，≤4h wall clock），且**仅在服务器 Agent 事先自动核实硬限额、真实环境归属、冻结隔离和接触真值 API 且全部 PASS 后即时生效**，无需再次询问用户同一事项。失败即 STOP=0 episode；不得把此授予 Stage R §36、原 DEV0 CLOSED 或 S1 的解封权。本助手无远端 shell，不宣称已经执行/锁定资源，也不准开始实物机器人动作、训练或多臂性能实验。

## 审查依据

- `P1_TASK9_CONDITIONAL_RESULT_20261010.md`：19 个 Task9 D-only 的 exit-FGONLY 代理正例 11，静态信号 Top4 3/4、置换 p≥0.21，无法建立可靠的类内判别。
- `P1_TEMPORAL_PROXY_RESULT_20261010.md`：56 any-time FGONLY proxy FN = 26 exit-persistent + 30 transient，显示标签时点对结论的实质影响。
- `P1_RETURN_TIME_TRIAGE_RESULT_20261010.md`：103 Tool False、top20 全局连续排序17/21，廉价 Gate-only 期望13.26/21；它们都是弱运动学代理排名，不是真持握或动作收益。
- `P1_TASK9_CONDITIONAL_RESULT_20261010.md` D-038及 D-039 勘误：LMG 选择组成匹配 14.48/21 = 事后随机期望，无法当成独立可执行预算策略的表现。`P1_LABEL_BLIND_QUOTA_EXPERIMENT.md` 提出最后一次独立批量基线，目前服务器真实结果未到。
- `P1_NEXT_L2_LABEL_AND_CONTRAST_GATE.md`：提出同刻参照/机械盲对照/固定未来窗/防泄漏数据合同。
- 过往 DEV0=21/24 executed、6 triggers、5 physical probes、D2 production trigger 0、t5 trigger 0/8；硬GPU预算21600s 曾超615.37s；故触发率和预算预留是重大先验风险。

## Methodological claim and estimands

**主问题**：在 `pi0_pick.success=false` 的 Harness 交付前时刻，是否存在一种可执行、代价有界的 evidence-acquisition policy，使决策者在关键不确定情况下更合理地选择 `CONTINUE/RETRY/ABSTAIN`，并提高独立持握判定或固定物理窗口任务效用？

区分三层研究目标，不许互相替代：

1. **Information acquisition (L2-A)**：在 `t_pick_return`、`t_probe_end`、`t_lift_end` 逐个同环境步数记录合法 RGB/depth/proprio 与 audit-only 目标 ID、双指-目标接触关系、支撑面接触、EEF-目标相对位姿；只报告来源有效性、真值可辨识性、证据区分率、未知率和测量成本。**独立物理 audit 不进入决策特征**。
2. **Decision value (L2-B)**：同一物理 probe/same lift 条件下，blind vs evidence-aware 两条实际可达策略的随机化对照。主要 estimand 是 intent-to-treat 的固定后续 H 窗 outcome（含未触发与提前终局）差异；按各 arm 的新增行动和感知成本报告单位预算物理效用。只得出候选效果，研究资源不足不得输出确认性显著性。
3. **Probe mechanical effect**：No-Probe fixed-retry vs Same-Probe blind-retry；如果没有这对照，不能把 probe 机械改变误算作视觉证据信息价值。Lift probe 类似独立设 same-lift blind 控制。

**冻结 held 标签需双时点**：瞬间的双指接触、物体受支承，以及受控提升后相对位姿稳定/未脱落分别打标签；单一步接触不能当稳定持握。若仿真接触传感/目标身份不可读取，应返回 `UNKNOWN` 并 STOP 确认性 held accuracy，不能以后验阈值/Planner flag 代替。

## 方法上如何体现创新

- **Time-Aligned Evidence**：将 `e_t` 绑定采样动作/物理步号/帧 SHA、机器人 pose、目标 instance 版本和最大允许滞后，杜绝历史 source_step mask 误作新帧证据。
- **Budgeted Selection**：基于工具合法返回和决策关键性 `q_t` 决定是否购入 `observation-only / close-gripper / controlled-lift` 证据，审计硬成本和因探测改变物体状态的干预效应；若无行动差异或结果不可辨识，应该 ABSTAIN/RETRY。
- **Evidence-conditioned decision**：仅把 legal evidence 送给 verifier，包含 `validity/freshness/target-identity/visibility`，必要时输出 UNKNOWN；真实效果只能从同机械行为的实际 arm 之固定 H downstream outcome 取得。

概念式期望信息价值：
`VOI(e|b) = E[ max_a U(a|b,e) ] - max_a U(a|b) - cost(e)`。
其中 b 为当前合法证据下对 held/contact 的不确定性，e 为具体获取手段。该值**不能**直接用现有 FGONLY proxy 代替真实 posterior utility。

## 本次裁决（资源授权拆分）

| 阶段 | 裁决 | 可做 | 不可做 |
|---|---|---|---|
| G0 研究方向 | **GO** | 相关工作/可证伪假设/指标/对照整理 | 将旧 FGONLY 说成独立持握结果 |
| G1 只读与协议实现 | **APPROVED NOW** | 旧 L1 label-blind quota 收尾；验证 source API、可见性；实现同刻合法/audit隔离采样组件和合成测试（mock env），双通道 SHA；草拟新 manifest | 新物理仿真 episode、实物操作、修改冻结状态或公开私有像素 |
| G2 小型 simulator feasibility | **PRE-AUTHORIZED / CONDITIONAL AUTO-GO** | 服务器 Agent 在单次自主流程里完成硬 GPU/episode/wall 上限、资源归属、物理真值 API、冻结隔离、并发预留、全链路停止 Gate 实测；全部 PASS 才自动启动≤12独立episode的新私有 FEAS pilot | 任一 Gate 不满足仍启动；复用旧 DEV0 额度；实物机器人操作；五臂性能宣称 |
| G3 因果对照扩展 | **HOLD** | 仅在 G2 有正负 held 参考/触发样本、动作确实不同、成本可对齐后再注册和审批 | 无门槛直接扩展大规模随机化、训练模型或声称 control gain |

**用户委托下的 G2 独立预授权硬上限**：最多 **12 新独立 episode，累计实际 GPU ≤3 GPU·hour，wall clock≤4小时，触发≤12**；这些是 *ceiling* 不是必须消耗的目标。优先单进程串行；在飞 Episode 启动前预留其最坏剩余 GPU/wall 成本，任何时刻资源余额不能覆盖则禁止发起；若单 episode 无法可预测上界，可使用更严的进程级时间限制与可恢复的安全终止路径，但不得让安全终止触发封版数据改写。若服务器不受本人控制、无法确认当前GPU计费与预算、无法安全停止或没有独立接触真值 API，则该预授权不生效、零执行 STOP；无需为达12例扩大预算。

G2 阶段试验目标只能是 feasibility，而非臂间显著性：检查各任务失败触发和两种真实持握类别是否可达、真值 API 可读、对齐/泄漏零异常以及三种不同证据获取成本；若前 12 例未获得足够正负有效真值，则报告 UNESTIMABLE/STOP，不后验扩大样本。

## 对照候选（将来 G2 后才可启动）

| Arm | 探测物理作用 | 模型可见证据 | 研究问题 |
|---|---|---|---|
| A0 fixed retry | 无 probe | 冻结 Tool 原字段 | 工具基础结果 |
| A1 same-probe blind retry | 固定夹爪 closure | probe 后证据隐藏 | closure 机械效应 |
| A2 same-probe legal evidence | 与 A1 完全相同 | 同步 RGB+proprio | 证据信息价值 |
| A3 same-lift blind | closure+受控 lift | 额外信息隐藏 | lift 机械效应 |
| A4 same-lift evidence | 与 A3 完全相同 | 同步 RGB+proprio | lift 提供的信息价值 |

**设计注意**：五臂全随机化对12 episode过少，因此 G2 不做五臂性能比较；只做配额、触发、API/标签和动作安全/计费可行性。G3 确认性对照需要另定独立样本规模与 arm allocation、至少不同任务与物体、ITT分析。

## 停止与验收

- 必须先解明 `task_id` 是否在 pre-delivery legal evidence contract 中，和完整 batch queue 是否存在；否则 task-quota baseline只能标 OFFLINE_BATCH_ONLY。
- 必须能运行无 simulator 的 mock 合成测试：audit 真值绝不影响选谁或执行什么；0-step同刻审计不会改变场景；wrist前后坐标/flip统一；缺帧/移动相机/未分割目标退回 UNKNOWN；不同物理探测臂区分行动成本。
- 同刻物理标签无独立目标 identity / 双指接触 / 抬起后保持信息则 L2-A 真值效度 STOP。
- G2 的 hard limits 或 actor attribution 不成立，停止；零新 episode 也可接受。
- G3 若不能做到 action difference 或时间点统一，只给可行性结果不估因果。
- 禁止新模型训练、权重覆盖、未审批环境/实物设备操作。

**研究管理结论**：`METHODOLOGY_GO / G1_CODE_AND_SYNTHETIC_APPROVED / G2_12EP_3GPUH_4WALLH_PREAUTH_AUTO_GO_IF_ALL_RUNTIME_GATES_PASS / G3_CAUSAL_HOLD`。若任一预检条件失败则 `G2_STOP_ZERO_NEW_EPISODES`，不以用户不在场为借口跳过。
