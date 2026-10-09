# RPent / Harness VLA — CURRENT_STATE

> 初版：2026-10-09。记录**当前已知的研究状态与下一步**，不是协议授权。
>
> 基线：Stage2I Server Return Review `84fc36b`、`METHOD_SPEC.md` v0.2.2、`NOVELTY_REVIEW.md` v0.2.2。2026-10-09 GitHub 研究分支上已发现“Stage2J A0 预注册候选已交付”提交，**但建立本文件时尚未审查其实际正文**；Stage2J 的资格结论不得从提交标题推断。本文件后续应在完成其审查后追加更新。

## 1. 总状态

**`P0_DATA_STRUCTURE_PASS / P0_OUTCOME_ELIGIBILITY_PENDING / PAEG_SPEC_ONLY / P1_P2_PROPOSED_ONLY / RUNTIME_HARD_STOP`**

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
| Stage2J | GitHub 分支提交标题显示“预注册候选已交付” | **待完整审查**，本文件先保持 `NOT_REVIEWED` |
| PAEG | `METHOD_SPEC.md` v0.2.2：Outcome State / Evidence Claim / PA-Attr / Runtime & Evolution Gate | **规范层、未实现、未定标** |

## 3. 当前科学问题与优先级

1. **P0 数据与 reference 的最后资格审查（优先，read-only）**：Stage2J 的对象、主指标、terminal shortcut、样本资格及“是否值得做”需要独立复核；确认是否只是同技能回顾性一致率。
2. **P1 最小可证伪研究设计（仅在后续授权时执行）**：围绕合法证据能否提升有成本限制的验证/恢复选择，设计固定 VLA、预算匹配、强基线和物理结果对照。
3. **P2 仅作长期问题定义**：无独立长期复用/迁移/更新收益数据，避免提前主张自进化能力。

## 4. 当前明确禁止的推断

- 不因 235/235 结构 PASS 声称 235 个有效物理真值标签或两类 flag 平衡；
- 不将同技能 `final_meas` 描述为工具已交付 Planner 后的未来持续持握；
- 不将 Stage R 480 试验当作跨 480 个独立事件或真实顺序恢复；
- 不因图1–图4 研究版图或 PAEG 概念设计而声称已验证长记忆、自动恢复或跨任务进化；
- 不把 sim `check_success`、对象坐标、状态重建元数据送入 Runtime/Evolution 作为合法在线结果。

## 5. 当前待办（Next Action）

1. **审查 Stage2J 正文和提交 diff**，检查预注册候选是否正确区分实验指标、信息集、物理参考和统计独立单元。
2. 核查 `A0` 是否真有明确的合法决策消费用途；若没有，在审查结论中建议 H0 描述性分析线收官。
3. 将 Stage2J 及后续审查结论更新到本文件；发生研究方向变化再补充 `DECISION_LOG.md`。
4. 任何服务器 outcome 分布核查、数值 A0 或新实验均须新冻结协议和用户明确批准，不能自动执行。

## 6. 标准汇报格式

每轮仅更新：`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用“有望/看起来”替换实际验收结果。
