# P1-DEV0 — 阶段级 L2 授权与首次运行前的锁定条件

> 2026-10-09。上一轮向用户明确提问“是否批准 P1-DEV0 的完整 L2 阶段（≤24 新 episode、≤8h 墙钟或 6 GPU·hour、≤2 worker，先达到即停）？”；用户紧接回复 **“go on”**。本记录将该回答解释为**同意上一条明确限定的 P1-DEV0 阶段**，仅限以下边界。若与用户意图不符，必须以用户的新指令为准。
>
> **执行状态：L2_PHASE_SCOPE_APPROVED / NO_SIM_STARTED / INTEGRATION_VALIDATION_REQUIRED。** 授权可在范围内实现与试验，但不是允许在测量/对照仍有构念缺陷时盲目启动。该授权在本协议范围内对 Stage R §36 的在线 verifier / recovery ban 提供**仅 P1-DEV0 新试验的局部例外**，不回写、不解冻、不重跑 Stage R/R1/S1 历史资产。

## 0. 有界目标

第一研究终点是**工程可行性**：验证真实 D2 后有合法追加观测、动作与代价可记录、四个条件在新前瞻样本上可运行并有独立固定时间窗 audit outcome。24 条新 episode **不得用于**声称 PAEG 优于任何强基线或给出确认性统计显著性。

用户已经完成 L1: A0 / EERD v0.1（206 MAIN picks、103 tool failures）和 P1 D2 preflight（206 legally observable candidate D2、task3/5/9 fail 21/30/52）。该历史结果只指导任务分层，**不得**把技内 FGONLY 当 D2 之后保持的 ground truth。

## 1. Manifest 与分母先验锁定

- 固定 LIBERO Spatial 任务 `(3,5,9)` × 独立 seeds `(1001,…,1008)`，各任务 8 episode，合计 **24**；
- 每任务四臂 D0、D1、D2、D3 **各 2 条**，随机化机制和随机种子在首次新 outcome 产生前物化为 manifest，并按 sha256 写入 seal；不根据执行结果替换 seeds、臂、任务、prompt；
- 一个 episode **只有第一个满足**非 terminal、非 truncated、`pi0_pick.success=False` 的 D2 边界可接受干预；未触发也作为正式 episode（intention-to-treat），不能抽取直到触发 24 次；
- 完整日志要区分总 episode、成功触发、未触发、触发后 infra/censored。历史 Stage R task3/5/9 seed121–190 不重用，旧文件保持只读。

## 2. 实验组与物理探测区分

- **D0**：无新探测；冻结 Planner 的本来决策。
- **D1**：相同物理探测后，**对 Planner 隐藏新 probe 的观测结果**，保持与 D0 同一种后续可见信息（若已有状态被动作改变引发后续反馈，需追踪；只能表述“probe-blind first decision”）。
- **D2**：与 D1 相同物理探测，采用预定合法 post-probe proprio/图像单阈值决定下一步。
- **D3**：与 D1 同探测，采用明确定义、无 privileged truth 的 Evidence Claim / 有效窗口 / abstain 与成本门决定下一步。**没有事前定义可运行的 D3 决策逻辑，就不得靠 Planner 自由解释结果冒充 Evidence Gate**。
- 所有物理 probes 必须保留基线对照与动作影响：`set_gripper` 会改变环境，绝不宣称其是零干预传感。
- 物理未来审计在工具真正**返回 Planner 后**或策略分支执行后的固定实际 env-step horizon；`check_success` 和 sim 物体坐标为 `audit_only`，严禁进入 online policy。

## 3. 成本与运行停止

- 四臂共享冻结 VLA 权重、prompt、Planner、max steps、任务和总观察/动作预算；不可把 D1 的 probe 视作免费动作。
- 上限：24 新 episode、8h wall、6 GPU·hour、最多 2 worker。任一到达即停，infra、未触发者照实记账。不为“补足触发事件”加跑。
- 运行前检查：仅一份正确的 manifest；环境可用、GPU 资源；只在本试验输出目录写新数据；不触碰冻结 Stage R / S1。禁止在原始实验路径复用有清理副作用的 init。
- 必须先通过源码接口对账、纯模拟 dry-run 单测以及一次专门的逻辑验证；检测到在线特权数据、动作和观测同一时间点被混淆、缺少独立 outcome、任一 arm 的信息集无可核验隔离时 **STOP BEFORE SIM**。
- 输出：四臂×任务触发/未触发，probe 成本、固定 horizon outcome 可测率、执行完整性、污染/泄漏审计与是否值得扩至 held-out。强性能声明禁用。

## 4. 授权边界

**本阶段批准的 L2 局部例外**：仅为完成上述 P1-DEV0 的必需代码、短程集成验证、≤24 新 episode 的受控仿真/工具介入及仅本数据的评价。阶段内无需每次子检查重复审批。

**未授权**：SFT/RL/OPD、长期记忆与技能库修改、生产部署、真实机器人、>24 episode / 超预算、公开或外发私有轨迹、Stage R §36 冻结历史结果重写；S1-DEV0 ON_HOLD。

**Gate 当前判定**：`P1_DEV0_PHASE_AUTHORIZED / SIM_RUNTIME_BLOCKED_UNTIL_INTERFACE_AND_COUNTERFACTUAL_CONTROLS_PASS`。
