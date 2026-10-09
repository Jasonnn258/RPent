# RPent / Harness VLA — CURRENT_STATE

> 初版:2026-10-09。记录**当前已知的研究状态与下一步**,不是协议授权。
>
> 基线:Stage2K 独立复审 `2b3710e`、EERD 契约 `70d57ba`、本轮基线 `4d155b9`;本轮新增 Stage2J-v2 候选 + EERD 字段级 QA + P1 问题定义；2026-10-09 独立方法复审已修正 P1 v1.1（commit `92384e5`）及 EERD QA 两阶段账本（`a040bfa`）。Stage2J v1 原文保留为未冻结历史候选。所有新实验仍须单独批准。

> **Research Package A 收官（2026-10-09，基于用户服务器回传）：**服务器合成测试 **3/3 OK**、Schema **PASS**、A0 outcome **PASS**，235/235 Pick 合格、PRIMARY=206、UNKNOWN=0；冻结 B=24 事件/480 trials。服务器随后执行 `audit_package_a_exports.py`，报告 **26/26 QA PASS、failures=[]**，A/B 关联与字段视图检查通过；常规混淆矩阵 **TP=101、FP=2、FN=56、TN=47**。原始封版统计文件不变，脱敏汇总归档于 `PACKAGE_A_A0_SERVER_RESULT_20261009.md` §6。**EERD v0.1 内部数据集已物化并通过目前约定的工程 QA；尚未经独立物理真值核验、跨任务泛化或外部发布审核。** Package A L1 阶段收官，P1 L2/L3 仍 HOLD。

> **P1 已实际启动（2026-10-09，阶段：离线可行性核查）**：源码确认 `view_driver_state` 重读历史帧不产生新的物理观测；`set_gripper(+1, steps=N)` 会真实执行物理步、可能改变持握状态，必须设置 probe-then-blind 机械效应对照。已提交 `p1_d2_preflight.py`、合成回归测试及 `P1_L2_STAGE_GATE.md`（独立 DEV0 ≤24 新 episode、≤8h 墙钟/6 GPU·hour 的建议边界）。**真实服务器 D2 预检已回传：2/2 合成测试 OK、206 合格 D2、103 次工具失败、low-res + proprio 206/206；结构 Gate PASS**。高分辨图当前归档仅 105/206。新增任务分层约束见 `P1_L2_STAGE_GATE.md` §3.1；新仿真/Runtime L2 仍 HOLD，须明确整阶段许可与 Stage R §36 局部例外。

> **P1-DEV0 有界 L2 阶段（2026-10-09）：**针对上一轮“是否批准完整 DEV0 阶段”提问，用户回复“go on”，已按该问题中限定的范围记录为 P1-DEV0 阶段级授权（`P1_DEV0_AUTHORIZATION_AND_LOCK.md`，≤24 新 episode/≤8h 墙钟/≤6 GPU·hour/≤2 worker）。**已经提交但服务器尚未执行**：任务分层冻结 manifest 生成器、四臂决策纯逻辑/特权字段禁读、合成单测和 `prepare_p1_dev0.sh`。下一 Gate 必须先完成实际服务器单测与 manifest 封存，然后补齐 D1 probe-blind Runtime 隔离、固定 future-horizon 审计和独立 pilot runner 才能开始新仿真。当前未获得任何 P1 DEV0 新物理实验结果；Stage R 历史冻结不变、S1-DEV0 ON_HOLD。

## 1. 总状态

**`PACKAGE_A_L1_CLOSED / EERD_V01_QA_26_26_PASS / P1_D2_PREFLIGHT_PASS / P1_DEV0_L2_SCOPED_APPROVAL / MANIFEST_POLICY_CODE_COMMITTED_TESTS_PENDING / NEW_SIM_NOT_STARTED`**

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
| **Stage2J v2** | B1 三值参考、B2 截断字段/对齐、B3 六件套与常数基线，均按 Package A 封版协议执行 | **A0 已在服务器执行并 PASS**，仅限单栈回顾性同技能代理一致性；历史 v1/v2 候选与冻结映射保留 |
| **EERD v0.1** | A 已物化 235 行，B 已物化 480 行/24 个父事件；服务器 export QA 26/26 PASS，字段权限与分组关联已按检查脚本验收 | **内部研究数据集已构建**（用户服务器回传）；不得外发、用于 online/evolution 或声称物理真值独立核验 |
| **P1 D2 preflight（真实服务器回传）** | `STRUCTURE_PASS_FOR_DESIGN`; 2/2 tests；206 非 terminal 非 truncation 合格 Pick，成功/失败各103；206/206 low-res RGB + proprio 结构有效；现存 hi-res 105/206；198/206 有自然后续命令；t3 fail=21/71、t5=30/77、t9=52/58 | 仅证明合法输入/现有目录结构，不能证明在线视觉验证准确率、因果恢复收益或物理标签有效性；详见 `P1_L2_STAGE_GATE.md` §3.1 |
| **P1 v1.1** | **已修正 H-P1m 对“异质性 ⇒ 不可交换/Conformal 失效”的错误推断**；要求合法在线前缀定义风险组、完成声明覆盖/弃权约束、DEV 锁定最强基线。A0 与 C 的结果构念不同 | 研究设计仅为候选；真实闭环实验仍 HOLD(新预注册+授权+§36 局部解除) |
| **A0 服务器真实结果** | 结构 PASS，outcome PASS；235/235 合格，206 PRIMARY，UNKNOWN=0；常规 TP=101、FP=2、FN=56、TN=47；`R_accept=1.94%`、`R_miss=54.37%`，一致率 71.84%；export QA 26/26 PASS | 用户服务器回传，独立的字段/数据行工程核验已跑；详见 `PACKAGE_A_A0_SERVER_RESULT_20261009.md` §6 |
| PAEG | v0.2.2 规范层 | 未实现、未定标、未验证部署效果 |

## 3. 当前科学问题与优先级

1. **P0 / Research Package A 正式收官（内部数据层）**：3/3 synthetic tests OK、A0 结果 PASS、Export QA 26/26 PASS；不再重复 A0 统计、改动冻结结果或增加无新证据的审查轮次。
2. **已取得的主要科学现象**：在主分析 206 picks 中，`flag=False` 的 103 次里有 56 次 **技内某时刻 FGONLY 代理满足**；工具成功侧仅 2/103 次代理不成立。这支持“工具失败后先验证/还是直接重试”的**研究动机**，不能等同返回时已经抓稳或未来真实持握。
3. **P1-DEV0 阶段授权已记录，执行尚未启动**：按 task3/5/9 每任务 8 新 episode、D0/D1/D2/D3 每 task×arm=2 条、seeds 1001–1008、单事件资格、无触发纳入分母。已提交封存脚本和纯合法证据决策合同；需在服务器先完成单测及 manifest seal；D1 物理 probe 掩蔽、真实未来物理 horizon 与成本记账的 Runtime 接线仍需实施和验证。24 episode 仅可行性，不可宣称显著效应。
4. **P2**：证据治理的跨任务记忆/技能演化仍属长远研究问题，现无经验证的更新收益。

## 4. 当前明确禁止的推断

- 不因 235/235 结构 PASS 声称 235 个有效物理真值标签或两类 flag 平衡;
- 不将同技能 `final_meas` 描述为工具已交付 Planner 后的未来持续持握;
- 不将 Stage R 480 试验当作跨 480 个独立事件或真实顺序恢复;
- 不因研究版图或 PAEG 概念设计声称已验证长记忆、自动恢复或跨任务进化;
- 不把 sim `check_success`、对象坐标、状态重建元数据送入 Runtime/Evolution 作为合法在线结果;
- 不在 UNKNOWN 参考上引用任何"一致率/可靠性"数字;不在多数类未披露时单独引用 raw concordance(Stage2J-v2 M0-M5 纪律)。
- 不由 Stage R 连败 h(k) 下降推导 conformal 可交换性失效（PAEG M1 异质可交换足以解释）；不让 P1 无限弃权套利、不在 TEST 事后选最强对照。

## 5. 当前待办

1. 服务器先执行 `bash analysis/research_context/prepare_p1_dev0.sh`：仅纯合成单测+写入不可覆盖的 `artifacts/p1_dev0/manifest.jsonl` 和 `manifest.sha256.json`。**不启动仿真**，回传 status/哈希/测试结果。
2. **同一已批准 L2 阶段内继续实现隔离的 P1 Runtime hook + pilot runner**：D0 与 D1 首次决策共用 blind policy；D1 的 probe 新数据不能进入首次决策，D2/D3 才允许消费；probe/重试费用单独记；用相同实际物理步 horizon 做未来 audit-only reference。必须通过无 GPU mock 测试和服务器逻辑烟测再允许新 rollout。
3. 24 新 episode、最多 2 worker、8h wall/6GPU·hour 任一达到即 STOP；记录未触发 episode，审计真值在线隔离；Stage R §36 仅此 P1DEV0 局部例外，原 Stage R/S1 仍冻结。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
