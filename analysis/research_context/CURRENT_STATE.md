# RPent / Harness VLA — CURRENT_STATE

> 初版：2026-10-09。记录**当前已知的研究状态与下一步**，不是协议授权。
>
> 基线：Stage2I Server Return Review `84fc36b`、Stage2J 候选 `762bf1a`、Stage2K 独立复审 `2b3710e`、PAEG METHOD_SPEC/NOVELTY_REVIEW v0.2.2；EERD v0.1 schema 文档提交 `70d57ba`。Stage2J 原文保留为未冻结历史候选。所有新实验仍须单独批准。

## 1. 总状态

**`P0_STRUCTURE_PASS / STAGE2J_DESIGN_REVISE_BEFORE_FREEZE / EERD_V01_SCHEMA_DRAFT / PAEG_SPEC_ONLY / P1_P2_RESEARCH_ONLY / RUNTIME_HARD_STOP`**

- 研究线：RPent 具身物理证据可信度（H0）→ 有限成本的主动验证与恢复（方法候选 P1）→ 证据治理的长期记忆与进化（P2）。
- 成果级别：已有多阶段离线实证结果、研究审查、可执行结构扫描与 PAEG 规范；**未证明方法上的新算法效果或 Runtime 改善**。
- 硬边界：Stage R §36 HARD STOP、S1-DEV0 ON_HOLD，任何实验/训练/控制接线须独立授权。

## 2. 主要数据和状态

| 项目 | 最新已知事实 | 证据/限制 |
|---|---|---|
| Vanilla collect | 187 episode 目录与两类原始文件存在；186 含 pick | 用户运行 Stage2I V1 结构扫描回传；`analysis/harness_h0/H0_OE_STAGE2I_SERVER_RETURN_REVIEW.md` |
| 真实 pick 调用 | 235/235 完成外层 result/diag + rtrace 结构配对 | **仅结构完整**，没有读取各 `success` 值或物理参考数值 |
| Pick chunk 轨迹 | 2,859 条动作条目，有预动作 meas 和 terminal meas 结构 | 物理目标内部字段、类别支持、标签合法性仍待核 |
| Stage R R1 | 24 个筛选失败事件；480 个正式重建 trial | SAME/RESAMPLE/NATURAL 非真实连续 retry；4 DEV CPS 另存不混入 |
| Stage2D | 回顾性结果已有历史报告 | 小样本/选择偏差/同源真值；不支持因果、泛化或在线接线 |
| Stage2E/F/G/H | D1 早期实验切点与真实 Planner D2 分开；同技能 ACQ 与 D2 后续保持严格分开 | `analysis/harness_h0/` 下各阶段文档 |
| Stage2I | `STRUCTURE_ONLY_PASS_PENDING_CLASS_ELIGIBILITY` | `84fc36b` 的服务器回传已登记 |
| Stage2J | `762bf1a` A0 预注册候选完成（DRAFT_NOT_FROZEN） | Stage2K 指出 B1 缺失 any-time 标签风险、B2 truncation 字段路径错误、B3 主指标决策含义不足；**修订前不冻结** |
| Stage2K | `2b3710e` 独立复审完成 | A0 outcome/数值实验继续 HOLD；建议 EERD 数据集文档方向可 GO |
| EERD v0.1 | `70d57ba` 数据契约草案已交付 | 仅 schema/评测设计，**无任何数据集物化、未重新打标签、没有 P1 控制实验授权** |
| PAEG | `METHOD_SPEC.md` v0.2.2：Outcome State / Evidence Claim / PA-Attr / Runtime & Evolution Gate | **规范层、未实现、未定标** |

## 3. 当前科学问题与优先级

1. **P0 Stage2J A0 候选最终审查**：结构资格已通过，但必须修复 Stage2K B1（ANY 标签缺失）、B2（`episode_truncated` 字段路径）、B3（raw concordance 多数类问题），再决定是否存在足够具体的研究/工程消费用途。无需为了“继续”而默认执行数值审计。
2. **EERD v0.1 内部数据契约**：已建立 `analysis/research_context/EERD_V01_DATA_CONTRACT_DRAFT.md`，分离 Vanilla Skill Evidence 与 Failure Persistence，明确 provenance / visibility / UNKNOWN / grouped split。可以只读完善文档，不允许悄悄物化 outcome 标签。
3. **P1 验证/恢复的研究方案**：优先提出可证伪假设、相同额外预算下的强基线与真实未来测量；在线控制和 rollout 保持 HOLD。
4. **P2 经验与技能演化**：没有独立长期更新证据，保持长期问题定义。

## 4. 当前明确禁止的推断

- 不因 235/235 结构 PASS 声称 235 个有效物理真值标签或两类 flag 平衡；
- 不将同技能 `final_meas` 描述为工具已交付 Planner 后的未来持续持握；
- 不将 Stage R 480 试验当作跨 480 个独立事件或真实顺序恢复；
- 不因图1–图4 研究版图或 PAEG 概念设计而声称已验证长记忆、自动恢复或跨任务进化；
- 不把 sim `check_success`、对象坐标、状态重建元数据送入 Runtime/Evolution 作为合法在线结果。

## 5. 当前待办（Next Action）

1. 将 Stage2K B1–B3 提交给本地研究 Agent：**先只写 Stage2J v2 候选修订方案，原 v1 不改写**；若 A0 缺少明确评价用途，允许直接收官，暂不读取 outcome。
2. 对 EERD v0.1 只做合法字段/时间/任务分组的 schema 对账设计；数据真正导出、标签物化及统计均待新批准。
3. 如决定开展 P1，先设计在固定 VLA + 相同观测/动作预算下的动态验证研究、独立未来 reference 与闭环收益对照，走新实验授权路径。
4. 保留 Stage R §36 Hard STOP、S1 ON_HOLD；后续重要审查结论写入 `DECISION_LOG.md`。

## 6. 标准汇报格式

每轮仅更新：`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用“有望/看起来”替换实际验收结果。
