# RPent / Harness VLA — CURRENT_STATE

> 初版:2026-10-09。记录**当前已知的研究状态与下一步**,不是协议授权。
>
> 基线:Stage2K 独立复审 `2b3710e`、EERD 契约 `70d57ba`、本轮基线 `4d155b9`;本轮新增 Stage2J-v2 候选 + EERD 字段级 QA + P1 问题定义；2026-10-09 独立方法复审已修正 P1 v1.1（commit `92384e5`）及 EERD QA 两阶段账本（`a040bfa`）。Stage2J v1 原文保留为未冻结历史候选。所有新实验仍须单独批准。

> **Research Package A 服务器执行回传（2026-10-09）：**用户已在服务器执行 `bash analysis/research_context/run_package_a.sh`，回传 **3/3 synthetic tests OK / schema PASS / outcome PASS / eligible 235/235 / PRIMARY 206 / UNKNOWN 0 / B 24 events×480 trials PASS**。结果与统计语义已记录于 `PACKAGE_A_A0_SERVER_RESULT_20261009.md`（仅汇总，不提交原始 outcome JSONL）。源代码中原始 `table.false_positive` 表示 `flag=False, reference=POSITIVE`，常规混淆矩阵中应记 FN；标准矩阵 TP=101、FP=2、FN=56、TN=47。已新增独立本地导出审计 `audit_package_a_exports.py`，**尚待服务器运行以完成 A/B 输出行数、权限隔离和溯源关联的复核**。L2/L3 继续 HOLD。

## 1. 总状态

**`PACKAGE_A_SERVER_A0_PASS / EERD_A_B_INTERNAL_OUTPUTS_REPORTED / EXPORT_QA_FINAL_PENDING / P1_L2_HOLD / RUNTIME_HARD_STOP`**

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
| **A0 服务器真实结果** | 结构 PASS，outcome PASS；235/235 合格，206 PRIMARY，UNKNOWN=0；工具 flag True/False 各103。常规 TP=101、FP=2、FN=56、TN=47；`R_accept=1.94%`、`R_miss=54.37%`，一致率 71.84%，always-positive 基线 76.21%。B QA 24/480 PASS | 用户服务器回传；研究代理仅技内 FGONLY。详见 `PACKAGE_A_A0_SERVER_RESULT_20261009.md`；独立 export QA 待跑 |
| PAEG | v0.2.2 规范层 | 未实现、未定标、未验证部署效果 |

## 3. 当前科学问题与优先级

1. **A0 数据及统计已跑完，禁止重复刷结果**：已拿到 235/235 资格、206 PRIMARY 的真实描述结果；原始 `a0_result.json` 和封版源码保持不变。最有研究价值的观察为工具失败侧的 56/103 FGONLY-positive 代理错位，不能把它直接解释成真实持握成功。
2. **EERD v0.1 内部导出最后 QA**（L1 已授权）：在现有服务器仅运行 `python3 analysis/research_context/audit_package_a_exports.py --output artifacts/research_package_a`，检查 A/B 输出行数、跨视图 join、字段权限及 B 每事件 8+8+4；只生成补充 QA / 标准混淆矩阵视图，不改变封版数据和指标。
3. **P1（L2 未批准）**：未来前瞻实验聚焦 pick 失败反馈后的低成本二次核验、何时重试与未来固定 horizon 的实际物理结果；必须记录弃权覆盖/动作成本，强基线在 TEST 前锁定。现有 A0 不是 P1 事件级因果效应估计。
4. **P2**：长期记忆/技能演化仍只有定义，无更新后独立外部证据。

## 4. 当前明确禁止的推断

- 不因 235/235 结构 PASS 声称 235 个有效物理真值标签或两类 flag 平衡;
- 不将同技能 `final_meas` 描述为工具已交付 Planner 后的未来持续持握;
- 不将 Stage R 480 试验当作跨 480 个独立事件或真实顺序恢复;
- 不因研究版图或 PAEG 概念设计声称已验证长记忆、自动恢复或跨任务进化;
- 不把 sim `check_success`、对象坐标、状态重建元数据送入 Runtime/Evolution 作为合法在线结果;
- 不在 UNKNOWN 参考上引用任何"一致率/可靠性"数字;不在多数类未披露时单独引用 raw concordance(Stage2J-v2 M0-M5 纪律)。
- 不由 Stage R 连败 h(k) 下降推导 conformal 可交换性失效（PAEG M1 异质可交换足以解释）；不让 P1 无限弃权套利、不在 TEST 事后选最强对照。

## 5. 当前待办

1. 服务器完成**一次性 L1 export QA**：`python3 analysis/research_context/audit_package_a_exports.py --output artifacts/research_package_a`，核对是否得到 `gate=PASS`；若 FAIL 只修补导出/核验实现，不更改 A0 已冻结分析或原数据。
2. 归档 `PACKAGE_A_EXPORT_QA.json` 的**清洗后汇总**，核验真实 EERD 物化质量并关闭 Research Package A。
3. 若用户希望进入 P1 的新采集/验证/恢复，需另立一次 L2 完整阶段授权；Stage R §36 与 S1 停止状态保持不变。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
