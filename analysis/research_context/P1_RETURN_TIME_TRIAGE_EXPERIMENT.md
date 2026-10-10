# P1 Return-Time Triage · 已实现的 L1 离线实验（2026-10-10）

> **状态**：CODE_READY / SERVER_EXECUTION_PENDING / NEW_L2_HOLD。本实验依赖冻结 A0 EERD + Stage R trace，仅用原 Tool 的合法返回字段为失败案例分配**复核优先级**，不向 Planner、在线 Runtime 或其他动作消费者写入决策。新源码 `p1_return_time_triage_lab.py` 与合成测试 `test_p1_return_time_triage_lab.py` 已提交；**本轮未连接实验服务器执行真实103条结果**。

## 由真实实证导出的下一问题

上一轮 `P1_TEMPORAL_PROXY_RESULT_20261010.md` 实际验证 A0 FGONLY `any` 的 reference-time 偏差：

- frozen 206 Pick：103 Tool TRUE、103 Tool FALSE；在 Tool FALSE 中 56 次 `any` 代理为正，但只有 **26 次 `final_meas` 代理为正，30 次中途 transient**；
- 原 Tool Balanced Accuracy 从任意时刻0.8012变成退出时0.8850；删 D 的收益从 +0.0541 收缩到 +0.0059，且退出时 proxy FP 2→16；
- Task9 中“只缺D”的 **19个旧代理漏报**，11次退出持续、8次 transient；起点高度与下降深度不能明显区分它们。注意这19条是 Task9 flag=F 且历史 any-FGONLY=POSITIVE 的**子集**，不是整个 Task9 只缺 D 的候选总量。

**新问题**：既然任意时刻标签偏差已导致错误实验结论，那么在 Tool 已报失败的103例中，仅凭 decision-visible 工具末端诊断，能否把26个**退出时仍满足弱代理**的样本优先挑出来做人工或未来物理验证，从而减少不必要的验证成本？

这个实验测试的是**证据优先级中是否有增量信息**；即使成功，也**不能证明物体持握**，更不能把排序高分变成在线 `CONTINUE`。

## 固定对照及测量合同

分母只取封版原 Tool `success=False` 的103条；按 Tool 的 `diagnostics` 合法端点特征固定6种排序，不在端点标签上拟合参数：

| Arm | 固定优先级排序 | 研究问题 |
|---|---|---|
| UNTARGETED | 所有失败一视同仁 | 固定复核预算下的基准覆盖 |
| D_ONLY_PATTERN | 仅缺D者优先 | 旧门槛模式的分诊价值 |
| PEAK_LIFT | `peak_lift_m` 越大越先查 | 抬升是否仍有端点信息 |
| FINAL_GAP | `final_gripper_opening` 越小越先查 | 末端夹爪闭合是否有信息 |
| LIFT_MINUS_GAP | `lift/0.05 - final_gap/0.06` | 两信号是否互补 |
| D_ONLY_THEN_LIFT | D-only 优先，内部按有界 lift 排序 | 同门槛类型内能否进一步区分 |

预算固定为每个评分分层中 Top **20%/40%**；每个分层分别 `ceil(ratio * n)`。输出 **precision@budget、proxy positives 捕获数、proxy negatives 误优先数、positive recall、relative enrichment**。布尔 D_ONLY 出现并列时，采用**并列组内平均抽中概率**，不使用 episode ID、task ID、物理标签或随机种子打破并列。

**唯一改变的第二对照**：排序与预算完全相同，仅把离线参考从 `final_meas FGONLY` 改回旧 `any_time FGONLY`，定量检查优先级对评价时间点是否敏感。输出 `global`（end）、`reference_horizon_control.global_any_time`（any）、三任务分层和 Task9 D-only 候选池内的固定排序效果。

**硬约束**：`priority(arm, legal_view)` 的输入只允许 `tool_report` 白名单数值/三道门槛状态；返回时 FGONLY 物体位置仅在原 Stage R 的 audit-only trace 中用于打分。任务/episode ID 只用于分组/内部去重，不作为排序变量。新实验不训练任何模型、无有监督标定、无 Runtime 接线、无新 sim/GPU。输出严格为聚合计数，无原始物体坐标、case ID、图片及 reference 数组。

## 可复现与停止

`analysis/research_context/p1_return_time_triage_lab.py` 通过 `p1_offline_module_lab.load_data` 与 `research_package_a.collect` 重新对齐源数据。必须同时过以下门：

- A-online/audit/metadata 235条三视图 join；PRIMARY=206、原 Tool flag 2×2 完全对照冻结 A0；
- `schema_qa.json` source SHA 和实际187 episode `states.json/stageR_trace.jsonl` **逐项一致**；
- A0 的逐例 FGONLY `any` reference 与重算完全一致；
- Tool FALSE=103、其中退出时 FGONLY POSITIVE=26、任意时刻 FGONLY POSITIVE=56，无法复现即 STOP，不能修改历史资产凑数；
- 合成测试包括纯合法特征、缺失值拒绝、Task9子样本、TopK并列公平性、参考时点替换与脱敏输出。

输出 `artifacts/p1_return_time_triage_lab/triage_v1.json`（gitignored）。新实验完成后保留 source SHA、实测值和必要失败原因，更新 `CURRENT_STATE.md` / `DECISION_LOG.md`，commit/push 脱敏总结。完整跑完前不得宣称6种策略中的任一条有效。

## 数据支持的后续决策分支（不凭直觉“选最优”）

- 如果 **D-only 或连续合法诊断确实能在固定20%预算** 下显著提高端点代理正例的复核命中率，并在三个任务分层方向相近，先研究 **Selective Verification / Budgeted Evidence Acquisition**（检索/物理验证资源优先级），绝不直接改动工具成功判据；
- 如果 t9 的 D-only 混杂样本仍无法区分出口持续/瞬时，且排序效果极依赖某任务或评价时间，就明确报告 **LEGAL_TOOL_RETURN_EVIDENCE_INSUFFICIENT**：需要新的同刻视觉或低成本时序观测，不能靠静态末端阈值硬判持握；
- 如果有收益但只在 Task9 生效，保留任务几何条件的**探索性假设**，不作为全局可部署算法。

最重要的研究裁决条件是**新的信息能否增加选择性**，以及这种选择性对“任意时刻参考”和“退出时刻参考”的变化是否鲁棒。所有正向结论仅为 FGONLY 运动学代理的一致性，后续真实 held/contact 和动作控制效益必须靠独立 L2 实验检验，**仍未获新授权**。
