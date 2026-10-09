# RPent / Harness VLA — CURRENT_STATE

> 初版:2026-10-09。记录**当前已知的研究状态与下一步**,不是协议授权。
>
> 基线:Stage2K 独立复审 `2b3710e`、EERD 契约 `70d57ba`、本轮基线 `4d155b9`;本轮新增 Stage2J-v2 候选 + EERD 字段级 QA + P1 问题定义；2026-10-09 独立方法复审已修正 P1 v1.1（commit `92384e5`）及 EERD QA 两阶段账本（`a040bfa`）。Stage2J v1 原文保留为未冻结历史候选。所有新实验仍须单独批准。

> **Research Package A 执行状态（2026-10-09）：L1 已获用户阶段级授权；A0 v2 已独立冻结为 `analysis/harness_h0/H0_OE_STAGE2J_FROZEN_V2_PACKAGE_A.md`；只读两阶段执行代码、合成测试、服务器一键入口已提交。当前 GitHub 工具环境无服务器私有原始轨迹访问，故**尚未运行真实 A0 / EERD 物化**；需在已有服务器执行 `bash analysis/research_context/run_package_a.sh`，回传 gates 与摘要。无需再次申请 L1 字段/outcome 权限。L2/L3 继续 HOLD。执行资产位于 `analysis/research_context/{RESEARCH_AUTHORIZATION.md,research_package_a.py,test_research_package_a.py,run_package_a.sh}`。合成测试代码已提交，但在本环境未执行。

## 1. 总状态

**`PACKAGE_A_L1_APPROVED / A0_V2_LOCKED / OFFLINE_EXECUTOR_COMMITTED / SERVER_OUTCOME_AWAITING_EXECUTION / P1_L2_HOLD / RUNTIME_HARD_STOP`**

- 研究线:RPent 具身物理证据可信度(H0)→ 有限成本的主动验证与恢复(方法候选 P1)→ 证据治理的长期记忆与进化(P2)。
- 成果级别:多阶段离线实证结果、研究审查、结构扫描、PAEG 规范、A0 v2 预注册候选、EERD 字段级契约、P1 可证伪问题定义;**未证明方法上的新算法效果或 Runtime 改善**。
- 硬边界:Stage R §36 HARD STOP、S1-DEV0 ON_HOLD,任何实验/训练/控制接线须独立授权。
- **文档轮次封顶(本轮生效)**:PAEG 规范、Stage2J 设计、EERD 契约、P1 问题定义四项,在无新数据( A0 读数 / C 采集)、无外部审查实质缺陷时不再产生新修订轮次(见 P1 文档 §5.1)。

## 2. 主要数据和状态

| 项目 | 最新已知事实 | 证据/限制 |
|---|---|---|
| Vanilla collect | 187 episode 目录与两类原始文件存在;186 含 pick | Stage2I V1 结构扫描回传(用户服务器) |
| 真实 pick 调用 | 235/235 完成外层 result/diag + rtrace 结构配对 | **仅结构完整**;类别支持、内部物理字段、标签合法性待核 |
| Pick chunk 轨迹 | 2,859 条动作条目,预动作 meas + terminal meas 结构在 | 同上 |
| Stage R R1 | 24 个筛选失败事件;480 正式重建 trial(+4 DEV 排除) | 非真实连续 retry;restore-SENSITIVE(APPROXIMATE) |
| Stage2D | 回顾性弱信号(差 +0.0129,区间跨 0) | 小样本/同源真值;不支持因果与外推 |
| Stage2E/F/G/H/I | D1/D2 分离;同技能 ACQ 与 D2 后保持分离;235/235 结构 PASS | `analysis/harness_h0/` 各阶段文档 |
| **Stage2J v2** | **B1(三值参考状态机+应观测点集 Q)/B2(truncation 改 states 步级顶层+对齐断言 A1-A3+PRIMARY 语义修正)/B3(描述性普查包六件套+消费者条件伴报 C1 预登记)全部落地;设计层 freeze-eligible** | 本轮交付;v1 `762bf1a` 保留;执行仍 HOLD |
| **EERD v0.1** | 契约草案 + A/B 字段来源/证据权限/样本分组/QA 八门；**G-QA-3 分 schema-only 完整性账本与 outcome 授权后的 UNKNOWN/flag 分层** | 仅文档；物化/导出/打标签 HOLD(D-008) |
| **P1 v1.1** | **已修正 H-P1m 对“异质性 ⇒ 不可交换/Conformal 失效”的错误推断**；要求合法在线前缀定义风险组、完成声明覆盖/弃权约束、DEV 锁定最强基线。A0 与 C 的结果构念不同 | 研究设计仅为候选；真实闭环实验仍 HOLD(新预注册+授权+§36 局部解除) |
| PAEG | v0.2.2 规范层 | 未实现、未定标、未验证部署效果 |

## 3. 当前科学问题与优先级

1. **P0/A0 数值普查(一次性,待用户决定)**:Stage2J v2 已解决全部设计阻断;执行需双重授权(检查 B 字段扫描 + outcome 读取)。产出可包含 EERD-A 结果阶段质量账本及工具 flag/FGONLY 参考的描述；**不是** P1（episode 级错误完成率）的功效先验。无具体消费者则默认不执行。
2. **C cohort 采集 + P1 闭环对照(唯一能检验 PAEG 机制主张的路径)**:问题、对照、数据需求、治理骨架已齐;下一步只能是全新预注册 + 用户授权,不存在更多文档前置。
3. **P2**:保持长期问题定义;无独立长期更新证据,不启动。
4. **文档轮次封顶执行中**:四项理论文档不再空转;重开条件=新数据/外部实质缺陷/用户明示。

## 4. 当前明确禁止的推断

- 不因 235/235 结构 PASS 声称 235 个有效物理真值标签或两类 flag 平衡;
- 不将同技能 `final_meas` 描述为工具已交付 Planner 后的未来持续持握;
- 不将 Stage R 480 试验当作跨 480 个独立事件或真实顺序恢复;
- 不因研究版图或 PAEG 概念设计声称已验证长记忆、自动恢复或跨任务进化;
- 不把 sim `check_success`、对象坐标、状态重建元数据送入 Runtime/Evolution 作为合法在线结果;
- 不在 UNKNOWN 参考上引用任何"一致率/可靠性"数字;不在多数类未披露时单独引用 raw concordance(Stage2J-v2 M0-M5 纪律)。
- 不由 Stage R 连败 h(k) 下降推导 conformal 可交换性失效（PAEG M1 异质可交换足以解释）；不让 P1 无限弃权套利、不在 TEST 事后选最强对照。

## 5. 当前待办(Next Action)

1. **[Package A 已获授权，等待服务器一次运行]** 在服务器仓库执行 `bash analysis/research_context/run_package_a.sh`，它先尝试纯合成回归测试，再完成 schema seal→A0 outcome→EERD A/B 私有输出和总结。读取已有 outcome 无需额外逐项批准，但本会话不能代替服务器执行。
2. 文档轮次封顶生效:除非上述①/②产生新数据,不再新增理论修订轮次;P1 文档 §5.3 停止清单(五项)照此执行。
3. 保留 Stage R §36 Hard STOP、S1 ON_HOLD;后续重要审查结论写入 `DECISION_LOG.md`。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
