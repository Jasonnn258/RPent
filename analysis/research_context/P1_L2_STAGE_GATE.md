# P1 · D2 Verification/Recovery — L2 阶段入口与实验约束

> 2026-10-09 · 从 `PACKAGE_A_L1_CLOSED` 进入 P1。**当前状态：P1 设计/离线资格预检 GO，L2 新仿真与 Runtime 接线未执行、尚未解除 Stage R §36。**
> 本文件只为避免再逐项审批，同时保留最小明确授权边界；P1 物理试验的真实结果必须来自未来新数据，不能重用 A0 的技内代理作终局标签。

## 1. 依据与最小问题

真实 A0 主集：206 个非 terminal Pick，工具 `success=False` 103 次，其中 56 次 **技内某时刻** `FGONLY=POSITIVE`。该不一致只是历史代理测量，**无法证明工具返回时仍然持握**，也不是验证动作的预期收益。

**最小科学问题：** 当非 terminal `pi0_pick` 在真实 D2 边界返回 False 时，使用**决策时合法可见**的状态/图像选择“继续/观察/重试”，是否比简单重试更有效，且验证消耗和误判完成率不恶化？

## 2. 现有源码约束（已核对，是真实设计阻断）

- `LiberoToolkit._step` : `pi0_pick` → `rtrace.end_step` → `dump_state` → `view_driver_state` → 返回 Planner；真正的 D2 agent 输入是 `view_driver_state` 的投影（含 `state`、图像引用、`log.result`），**不能从 `rtrace.meas` 偷用对象位姿或 `check_success`**。
- `view_driver_state(step)` 是历史状态读取，重复调用通常只返回**同一步原有图像**，没有新动作、没有新物理时刻。
- `set_gripper(gripper=+1, steps=N)` 含**N 个环境物理步**，可使物体位置/夹爪状态变化，因此是 **physical probe + potentially stabilizing intervention**；其效果不能仅解释为“额外观察的信息价值”。
- `dump_state` 产生已合法可见的低分辨率 agentview/wrist 图像及 proprio；历史高分辨率图像可能随之后的 episode 步进被删除，当前磁盘缺失不等于决策时不存在。
- Pi0.5 continuation 随机种子不可直接锁定（Stage R 既有事实），不能声称只按相同 seed 配对就得到严格因果反事实。

## 3. 第一个实际交付：无需 L2 的 D2 数据资格预检

运行 `analysis/research_context/p1_d2_preflight.py`，只读 Stage R collect `states.json`，计算可触发的 `nonterminal & nontruncated & pick.success=False` 边界总量、per-task 分布、合法 proprio 字段和历史低/高分辨图像**当前归档存在性**。不读 audit-only outcome、不调用仿真器、不提取学习目标。

输出 `artifacts/p1_d2_preflight/summary.json`（忽略提交）。此步骤只报告 **输入可用性**；若主要合法输入根本不可获得，则在投入 GPU 前 STOP 或更换独立新采集设计。

## 4. 未来 L2 范围（需阶段级明确批准，不能仅因 P1 文档存在即执行）

**建议边界：独立 P1-DEV0 可行性实验，最多 24 个新前瞻 episode，最多并发 2 个 worker；最多 8 小时墙钟 / 6 GPU·hour，任何先达到的预算即 STOP。** 任务/新种子网格及随机化分配在首次 rollout 前冻结并写入新阶段 manifest；不能沿用 Stage R 121–190 冻结事件做 intervention。不存在“跑到好看为止”。

**阶段对照骨架（只测 DEV 接线正确性，不以 24 次作确证性显著性主张）：**
- **D0 / no-probe**：工具失败后按固定基线继续/重试；
- **D1 / probe-then-blind**：同一固定物理 probe 后忽略额外观察、按与 D0 一致的后续规则执行；隔离 probe 的**直接物理效应**；
- **D2 / probe-static**：与 D1 相同 probe 后按 DEV 预定合法 proprio/图像阈值选择后续行为；
- **D3 / probe-evidence-policy**：与 D1/D2 相同 probe，但由 Evidence Claim（时效/来源/有限历史）+ 有限成本/弃权约束选择后续行为；不得在线使用 `FGONLY`、`check_success`、`reconstruction_metadata` 等 audit-only 字段。

**必要额外记录**：D2 trigger 时间及完整合法快照（图像路径/哈希+proprio）；随机 arm、完整 env-step / chunk / 延迟 / 观察调用成本；probe 前/后合法图像、后续真实动作；独立 audit-only future reference 在固定**物理步 horizon**的实际 outcome；abstain/声明完成率与任务真实成功/错误完成；infra/censored 单列。不能用 probe 后即时 `check_success` 代替固定未来窗口持握参考。

**重要归因纪律**：D2/D3 相对 D0 的差异同时包含机械扰动与决策效果；**只能用 D3 对 D1/D2 的比较讨论“新证据驱动决策是否增益”**。D1 对 D0 估计 probe 本身的物理效应，不能归因于 verifier。

**DEV0 STOP**：D2 合法字段出现审计真值泄漏；不能获得 probe 后新合法图像；probe 导致 task invalid；新动作超预算、infraction/infra 不可控；不同臂已运行代码/提示不同但未记录，或者随机分配、分母不完整。遇上述任一情况停受影响实验；不给未定参数后验选好结果的空间。

**DEV0 结论级别**：接口可执行性、有效触发样本比例、成本分布、outcome 可测性、真实前瞻估计的功效规划；不得宣布 P1 优于 CheckVLA/Zetta。确认性比较需独立 HELDOUT TEST、DEV 锁定静态/Conformal 强基线、覆盖/弃权约束和功效分析后另做预算规划。不能因 A0 56/103 直接估算 P1 效应量。

## 5. 授权划分

| 操作 | 状态 |
|---|---|
| 完成 Package A | **CLOSED** |
| D2 既有资产结构/合法观测预检（本文件 §3） | **GO：只读** |
| 上述 24 新 episode L2 DEV0 仿真与 Runtime 接线 | **HOLD**，需用户就完整 DEV0 阶段批准，并由阶段执行说明限定解除 §36 的范围 |
| 后续大样本新 cohort / SFT、RL、生产部署 | **HOLD / L3 分别批准** |

**下一 Gate：`P1_D2_PREFLIGHT_RESULT`；预检通过后优先执行一次有边界的 DEV0，而不是继续扩张规范文档。**
