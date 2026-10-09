# RPent / Harness VLA — CURRENT_STATE

> 初版:2026-10-09。记录**当前已知的研究状态与下一步**,不是协议授权。
>
> 基线:Stage2K 独立复审 `2b3710e`、EERD 契约 `70d57ba`、本轮基线 `4d155b9`;本轮新增 Stage2J-v2 候选 + EERD 字段级 QA 规范 + P1 研究问题文档(见 HEAD)。Stage2J v1 原文保留为未冻结历史候选。所有新实验仍须单独批准。

## 1. 总状态

**`P0_STRUCTURE_PASS / STAGE2J_V2_REVISED_B1B2B3_RESOLVED / EERD_V01_FIELD_QA_SPECIFIED / PAEG_SPEC_ONLY / P1_FALSIFIABLE_QUESTION_DELIVERED / DOCUMENT_ROUNDS_CAPPED / RUNTIME_HARD_STOP`**

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
| **EERD v0.1** | 契约草案 + **字段级来源表(A/B 逐字段:文件→路径→产码行号→可见性→质量规则)、三视图证据权限矩阵、样本分组与跨子集防泄漏、验收门 G-QA-1..8** | 仅文档;物化/导出/打标签 HOLD(D-008) |
| **P1** | **最小可证伪假设 H-P1/H-P1m + 五对照(C-1..C-5,含 conformal 静态阈值)+ 证伪条件预写死;与 CheckVLA/Zetta/RegenHarness 机制差异全部转为可检验对照;C 子集字段需求清单** | 研究设计 GO;闭环实验 HOLD(须全新预注册+授权+§36 局部解除) |
| PAEG | v0.2.2 规范层 | 未实现、未定标、未验证部署效果 |

## 3. 当前科学问题与优先级

1. **P0/A0 数值普查(一次性,待用户决定)**:Stage2J v2 已解决全部设计阻断;执行需双重授权(检查 B 字段扫描 + outcome 读取)。产出=EERD-A G-QA-3 首块 + P1 功效先验。无消费者则默认不执行(§5.2 伴报 C1 已锁定指标切换规则,若 P1 立项不需新预注册)。
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

## 5. 当前待办(Next Action)

1. **[等用户三选一]** ① 批准 A0 数值普查执行(检查 B + outcome 读取,按 Stage2J v2);② 批准 C cohort + P1 预注册起草授权(§36 该协议内局部解除须随预注册一并批准);③ 全线收官(A0 归档不执行、P1/P2 以问题定义收官、EERD 保持文档态)——三选一,均合法,默认无推荐排序,但注意 ①是②的信息前置。
2. 文档轮次封顶生效:除非上述①/②产生新数据,不再新增理论修订轮次;P1 文档 §5.3 停止清单(五项)照此执行。
3. 保留 Stage R §36 Hard STOP、S1 ON_HOLD;后续重要审查结论写入 `DECISION_LOG.md`。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
