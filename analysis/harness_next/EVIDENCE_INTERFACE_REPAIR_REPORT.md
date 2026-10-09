# Evidence Authorization Interface Repair — v0.2.2 收官报告

> 2026-10-09 | RPent `research/pre-ovpm-20260905`；
> 基线 METHOD_SPEC v0.2.1（`17a2991`）、`POST_MCF_INTERFACE_AND_LITERATURE_AUDIT.md`（`21dff30`）。
> 交付：`METHOD_SPEC.md` v0.2.2（本轮改动 `a3c6ec5` + `29ba99d`）、
> `NOVELTY_REVIEW.md` v0.2.2（`adc676d`）及本报告。
> **纯文档修订与 GitHub 原文读回规则自查**：未运行 Stage R/新统计、rollout、环境、模型、训练、预注册或任何执行代码；未修改 E14/A1/P5/U4。Stage R §36 Hard STOP 和 S1-DEV0 暂停持续有效。

## 1. 结论

**GO：本轮四项 evidence-authorization 接口规范矛盾已按保守语义修复。**
这不是 H0 Direction 1 实验/定标 GO，也不代表原创统计算法已证明。N1 继续处于“问题与方法契约成立，定量方法价值待独立验证”的状态。

先前 MCF v0.2.1 修复了分类公理和归因默认值，但跨章节仍允许某些不可用字段绕过门控。
本轮在不增加模型/Agent/Verifier 的情况下，收紧**来源合法性 + 分类正确性 + D2 正向授权**。

## 2. 四项阻断的前后对照与反例

| 编号 | v0.2.1 的反例（原文） | v0.2.2 修订后 | 验收 |
|---|---|---|---|
| **I1** 离线标签入 Runtime | §5.6 禁离线双臂作在线输入，但 §8.2/§9.3 由 P=0/8+0/8 给 REPORT_FAILURE=ALLOW | §5.6 权限类型化；§6.2 只读合法前缀；§8.2 离线双臂行 Runtime=N/A；§9.3 离线 P 案例改为 NOT_APPLICABLE_OFFLINE_ONLY | **通过规范检查**：只用 offline_replay_cohort 不可能授权 Runtime |
| **I2** Gate 绕开 D2 | §6.3 `repairability=UNKNOWN` 且 `causal_grade=UNIDENTIFIED` 可穿过两个排除分支，直接 PROPOSE_REVIEW；违背 §7.5 D2 | §6.3 对 P、充分证据量、持续性、EVIDENCE_FOR_CANDIDATE_REVIEW、MODERATE/STRONG、合法 outcome 逐项正向要求；A 暂 QUARANTINE（尚无独立 D2） | **通过规则推演**：P,SUFFICIENT,UNKNOWN,UNIDENTIFIED → QUARANTINE |
| **I3** 过时成功规则/因果结论 | §7.2 R1a “任意成功→E”；§9.3 “contrast≈0→排除动作影响”以及重建不足仍给 MODERATE | 只有完整双臂且 SAME≥2/8 才能依 Stage R 冻结类判 E；一次翻盘仅描述观测；§9.3 不排除未测动作影响；没有有效干预/对照默认 UNIDENTIFIED | **通过规则推演**：SAME0/8、POLICY1/8 → U；无完整双臂一次成功 → DETERMINING |
| **I4** Evolution 的真值权限混淆 | §5.6 `offline_replay_cohort` 混含 check_success/object pose，却未先区分 audit-only vs evolution-legal 字段 | §5.6 新增 `research_audit_truth`、`reconstruction_metadata` 等类型，禁止特权字段入 Evolution；合法 outcome 缺失 = NOT_AVAILABLE，不能从研究标签借入门控 | **通过接口检查**：sim-only P 仍为 RESEARCH_ONLY_LABEL，不进入 Evolution |

## 3. 规范层逐例走查（非运行时单测）

| 输入假设 | 预期输出 / 不变量 | 理由 |
|---|---|---|
| Runtime 只有当前一条 false-grasp 记录；另有仅研究用 8+8 P 标签 | `REPORT_FAILURE` 不得依据 P 标签 ALLOW | §5.6 + §6.2；在线不足时 UNRESOLVED |
| Evo 输入 P + SUFFICIENT + UNKNOWN repairability + UNIDENTIFIED causal | `QUARANTINE` | §6.3 必须满足 D2 全部正向条件 |
| Evo 输入 P + SUFFICIENT + 正面 repairability + MODERATE，但 success 字段来自 sim 真值 | `QUARANTINE(NO_LEGAL_OUTCOME_EVIDENCE)` | §5.6 权限优先于统计强度 |
| `SAME=0/8`, `POLICY=1/8` | `U`（冻结 Stage R 事后研究标签），不能 E | §5.3 完整 8+8 互斥四分类 |
| `SAME=0/8`, `POLICY=2/8` | `A`，非 E | 同上 |
| `SAME=2/8`（完整双臂） | `E` 事后研究标签 | 同上 |
| 未观测完整双臂，只发生一次成功 | `DETERMINING` + observed-success 描述；不能 E | §7.2 R1a 正文修订 |
| 重建使用 `ρ<ρ*` 且没有有效干预 | `UNIDENTIFIED` 不会因重建降级变成 MODERATE | §7.2 R3 + §9.3 |
| `episode_terminated` 单点成功 flag，无其他独立任务成功代理 | 不可自动形成 `TaskSatisfied L2+` | §6.2；应 UNRESOLVED |

**核验方式**：审阅 GitHub 上的方法规范，并用严格文字/标记检查确认关键守门语句存在，旧的两条越级规则已消失。**没有运行现有控制器、测试框架、任何数据集或环境**，不能将这张表解读为真实软件测试结果。

## 4. 外部先例更新

本轮查阅 [CheckVLA](https://arxiv.org/html/2607.26789) 论文 HTML 的 conformal calibration、实验拆分及限制段，和 [VASO](https://arxiv.org/html/2606.05395) 论文 HTML 的 proposition-aligned labeling 前提及错误映射案例；对应审查写入 `NOVELTY_REVIEW.md §0.3`。

- CheckVLA：在固定管线及 exchangeability 前提下保证**首次不必要干预**的受限风险；不保证 failure recall、修复后安全、分布偏移。
- VASO：模型检查形式保证以命题映射正确为前提；速度范数漏掉一个维度会产生虚假的安全证明。
- 因此“证据需要前提/保证仅在特定决策成立”已经有前例，不能当作本方法独创性。研究焦点仍是**物理状态重建、双结果契约、统计可比性和来源授权**的联合约束。
- Zetta 已由既有 [S-ext] 源码审计，RegenHarness 仍是本轮摘要级事实；这两篇论文全文本轮未完成，创新性结论仍须保留不确定性。

## 5. 保留下来的问题（不是这次已解决的问题）

1. **可辨识性**：Stage R 现存 trial outcome 到底有无满足“非特权 Evolution 合法字段”的真实信号，**未审计原始数据**。v0.2.2 只建立权限约束；可能导致当前 Gate 始终 QUARANTINE。这是诚实结果，不能为获得输出而放松防火墙。
2. **因果可辨识性**：即使存在合法重试 outcome，当前 `causal_grade` 默认 UNIDENTIFIED，且正面 `repairability` 证据未定标，因此尚不能声称 P 类型将导向有效的 proposal。
3. **统计内容**：H0 方向 1 的 H-OE1/2/3 草案仍受 G1–G4 科学风险约束：同源真值循环、事后标签泄漏、异质性选择效应、S_pre/S_post 外推差异。未获批准前不得冻结预注册或运行统计。
4. **观察能力**：`episode_terminated` 和代理视觉信号能否满足任务完成 L2、稳定持有 L3，目前没有独立校准，不承诺在线 Gate 可用。
5. **跨工作原创性**：N1 的方法组合尚无定量效果与完整外部全文排重验证；不得声称已获得新算法。

## 6. 完成条件与边界

- [x] I1–I4 的原文位置、反例与修正规则。
- [x] Stage R 冻结四分类与 E14/A1/P5/U4 不变。
- [x] Runtime/研究-only/Evolution 输入权限分离。
- [x] Evo review 符合正面 D2 而非排除式绕过。
- [x] CheckVLA/VASO 相关先例明确收缩，论文核验范围说明清楚。
- [x] 仅 Markdown 文档更新，未运行实验/统计/代码。
- [ ] H0 方向 1 正式离线定标 **未授权**。
- [ ] Stage R 冻结 Hard STOP 未解禁；S1-DEV0 继续暂停。

**裁决**：**GO（本次接口规范修复收官）/ HOLD（H0 离线定标与任何在线实施）**。
下一项对研究进展真正有帮助的工作是：**在独立批准后先解决 H0 G1–G4 的 reference outcome / future-target / exchangeability 前提，再讨论离线参数定标**。再写更多泛化 Harness 框图不会增加可辨识性。
