# RPent / Harness VLA — CURRENT_STATE

> 初版:2026-10-09。记录**当前已知的研究状态与下一步**,不是协议授权。
>
> 基线:Stage2K 独立复审 `2b3710e`、EERD 契约 `70d57ba`、本轮基线 `4d155b9`;本轮新增 Stage2J-v2 候选 + EERD 字段级 QA + P1 问题定义；2026-10-09 独立方法复审已修正 P1 v1.1（commit `92384e5`）及 EERD QA 两阶段账本（`a040bfa`）。Stage2J v1 原文保留为未冻结历史候选。所有新实验仍须单独批准。

> **Research Package A 收官（2026-10-09，基于用户服务器回传）：**服务器合成测试 **3/3 OK**、Schema **PASS**、A0 outcome **PASS**，235/235 Pick 合格、PRIMARY=206、UNKNOWN=0；冻结 B=24 事件/480 trials。服务器随后执行 `audit_package_a_exports.py`，报告 **26/26 QA PASS、failures=[]**，A/B 关联与字段视图检查通过；常规混淆矩阵 **TP=101、FP=2、FN=56、TN=47**。原始封版统计文件不变，脱敏汇总归档于 `PACKAGE_A_A0_SERVER_RESULT_20261009.md` §6。**EERD v0.1 内部数据集已物化并通过目前约定的工程 QA；尚未经独立物理真值核验、跨任务泛化或外部发布审核。** Package A L1 阶段收官，P1 L2/L3 仍 HOLD。

> **P1 已实际启动（2026-10-09，阶段：离线可行性核查）**：源码确认 `view_driver_state` 重读历史帧不产生新的物理观测；`set_gripper(+1, steps=N)` 会真实执行物理步、可能改变持握状态，必须设置 probe-then-blind 机械效应对照。已提交 `p1_d2_preflight.py`、合成回归测试及 `P1_L2_STAGE_GATE.md`（独立 DEV0 ≤24 新 episode、≤8h 墙钟/6 GPU·hour 的建议边界）。**真实服务器 D2 预检已回传：2/2 合成测试 OK、206 合格 D2、103 次工具失败、low-res + proprio 206/206；结构 Gate PASS**。高分辨图当前归档仅 105/206。新增任务分层约束见 `P1_L2_STAGE_GATE.md` §3.1；新仿真/Runtime L2 仍 HOLD，须明确整阶段许可与 Stage R §36 局部例外。

> **P1-DEV0 L2 阶段收官（2026-10-09）：**用户此前有界 L2 阶段授权后，服务器已运行 21/24 新 episode；22/22 Hook 合成测试和 31/31 全套由执行报告记录，6 个 Pick 失败触发且有审计事件。D2 静态臂没有触发；全部 6 次实际决策均是 RETRY；GPU 6.17h 超过上限 6.0h，已记录偏差。实验状态 `STAGE_CLOSED`，严禁补跑剩余 3 个 skipped；历史 Stage R 和 S1 仍冻结。

> **P1-DEV0 最新独立方法复审（2026-10-09）**：当前 GitHub HEAD 已含运行报告（21/24 episodes，6 triggers，0 D2 arm 触发，6/6 实际决策/动作均为 RETRY）。代码审查进一步确认 Hook 实际为**工具返回交付 Planner 之前的 Harness 拦截**；D3 只判断新图像文件存在+proprio 而未分析像素；所谓 6/6 审计只有 4 次在 H=200 后首技能边界取样，另外 2 次提前结束，固定窗口并未统一；6.17 GPU·hour 越过预算硬上限 0.17h。原 analyzer 的 `no_events_infra` 混合无事件与 3 个预算跳过项。已提交 `P1_DEV0_INDEPENDENT_METHOD_AUDIT.md`、`scripts/p1_dev0_posthoc_audit.py` 与合成测试，**新事后脚本还未在服务器执行，不能提前声称该脚本 PASS**。P1-DEV0 **阶段 CLOSED，禁止补跑剩余 3 格**；只允许继续已有数据只读复核；后续正式 P1 需新独立预注册/有界 L2 授权。

> **P1-DEV0 服务器后验审计结果（2026-10-09，用户回传）**：4/4 synthetic tests OK，原版 `p1_dev0_posthoc_audit.py` 的 `science_gate=HOLD_NO_ARM_ACTION_CONTRAST`、冻结 policy 哈希匹配。24 分配/21 真实事件/6 触发/15 未触发/3 无事件（原 runner 归因为预算跳过），6/6 真实决定=RETRY。**影子决策重大新发现：5 个 probe 后合法观测，D2 静态规则 5/5 CONTINUE、D3 合法启发式 5/5 RETRY，二者分歧 5/5；没有影子动作的真实后续 outcome，不能推出方法收益。**该事实与原执行报告所写 5 次 `post_gap>=0.06` 相矛盾；已于 `P1_DEV0_EXECUTION_REPORT.md` 和 `P1_DEV0_INDEPENDENT_METHOD_AUDIT.md` 追加更正，不改冻结数据。H=200 后边界审计4次(+3/+23/+8/+18)，提前结束2次(早120/70步)。GPU=22215.37s、超过21600s上限615.37s，hard budget FAIL。**后续聚合诊断增强版代码已提交但未实测**：`scripts/p1_dev0_posthoc_audit.py` 加 probe→policy 传值、gap 与 EEF dz 阈值核验，须只读执行验证。P1-DEV0 CLOSED，不补跑，正式 P1 新 L2 HOLD。

> **最新 P1 诊断归档（2026-10-09；用户服务器增强版实测）**：4/4 tests OK，`policy_sha_match=true`，5/5 probe 的合法 `post_gap<0.06`、5/5 `ΔEEF_z` 有效但 **0/5 达到 0.03 m**，probe→policy `gripper_gap/eef_z` 不一致 0，缺 post_legal 0。影子 **D2=CONTINUE 5/5 vs D3=RETRY 5/5** 的原因是 D3 冻结规则的 EEF 高度门槛与定点夹紧 probe 不匹配；两者都未得到正确持握真值的验证。已在执行报告/独立审计中追加勘误，历史数据/策略保持冻结。进一步源码发现**pre wrist PNG 做纵向翻转、post probe wrist PNG 不翻转**。已提交独立只读的 pre/post 图像配对+SHA/尺寸核验及合成测试（尚未在服务器执行），下一 Gate 是图像证据是否实际可对齐/可用，不是再跑仿真。P1-DEV0 CLOSED；下一新 L2 未授权。

> **视觉图像配对真实验收（2026-10-09，用户服务器回传）**：只读 `p1_dev0_visual_pair_preflight.py` 得到 `PAIRED_ASSETS_COMPLETE`；21 有事件/15 无触发/6 触发/其中5个物理 Probe，原始 agentview 与 wrist 前后 PNG 文件分别 **5/5 SHA256+头部尺寸合格**，均前后哈希不同；`failure_reasons={}`。这是**图像文件存在与溯源证据**，尚未完成像素语义、物体是否可见、真实持握或独立标签效度的验证。首次服务器运行的合成单测为 **2/3 PASS + 1 个 `KeyError: wrist_verified_pair`**：失败场景有效配对数=0 时 Counter 转字典省略零键，测试用下标读取。已在 `scripts/p1_dev0_visual_pair_preflight.py` 给固定统计键补零，**修正版尚未在服务器回归测试**；真实数据 PASS 可保留，不能声称整个质量门“测试全绿”。Pre wrist PNG 与 Post wrist PNG 的纵向翻转差异仍需在真正比较像素前显式校正。旧 DEV0 继续 CLOSED，不准补跑；下一阶段以离线合法视觉证据的语义可辨识性为问题，新 L2 仍 HOLD。

## 1. 总状态

**`P1_DEV0_CLOSED / VISUAL_PAIR_DATA_GATE_PASS_5_5_BOTH_CAMERAS / VISUAL_UNIT_TEST_2_OF_3_ONE_ZERO_COUNTER_ERROR / FIX_COMMITTED_RERUN_PENDING / GRASP_SEMANTICS_UNVERIFIED / NEXT_L2_HOLD`**

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
| **P1-DEV0 已执行** | 21/24 新 episode(3 个 SKIPPED_GPU_BUDGET)、6 触发全审计、0 hook_error/0 censor/0 infra;D1 遮蔽、特权键隔离、事件外置全部核验通过;判定 GO(工程)/HOLD(确认性) | 触发率 6/21 且 t9 集中(t5 0/8)、D2 臂 0 触发未生产暴露;详见 `P1_DEV0_EXECUTION_REPORT.md` |
| **DEV0 增强版后验诊断（用户服务器回传）** | 4/4 tests OK，5/5 gap<0.06，0/5 EEF dz≥0.03，probe→policy 不一致0，D2/D3 影子分歧 5/5；未实际执行的 D2 结果仍未知 | 规则失配已确认，夹爪闭合≠真实持握；Pre wrist PNG 被纵向翻转而 Post wrist 原样写出；只读视觉文件配对 Gate 待跑 |
| **DEV0 视觉证据配对（用户服务器回传）** | `PAIRED_ASSETS_COMPLETE`;5/5 probe 对 agentview 与 wrist 图像哈希/PNG 头尺寸合格，5/5 两相机前后哈希均不同；`failure_reasons={}` | 只验证静态文件与视图配对；合成测试 2/3（零字段 KeyError），归零输出已修待复跑；wrist 纵向方向不一致，尚无任何视觉持握识别结果 |
| PAEG | v0.2.2 规范层 | 未实现、未定标、未验证部署效果 |

## 3. 当前科学问题与优先级

1. **P0 / Research Package A 正式收官（内部数据层）**：3/3 synthetic tests OK、A0 结果 PASS、Export QA 26/26 PASS；不再重复 A0 统计、改动冻结结果或增加无新证据的审查轮次。
2. **已取得的主要科学现象**：在主分析 206 picks 中，`flag=False` 的 103 次里有 56 次 **技内某时刻 FGONLY 代理满足**；工具成功侧仅 2/103 次代理不成立。这支持“工具失败后先验证/还是直接重试”的**研究动机**，不能等同返回时已经抓稳或未来真实持握。
3. **P1-DEV0 已执行完毕（2026-10-09，GO-工程/HOLD-确认性）**：manifest seal 复核通过、22/22 单测 + 集成 Gate 后执行 21/24 新 episode（wall 3.15h / GPU 6.17h，后者为在飞 episode 完成导致的 0.17h 越限，已如实记录）。四臂接线、D1 probe 遮蔽（结构同构 + 生产步号 delta=1 全 6/6）、固定 horizon audit-only（6/6 覆盖）、成本记账、事件外置隔离（0 泄漏）全部验证。触发率 6/21（t9 5/5、t3 1/8、t5 0/8），D2 臂 0/4 触发（t9 两格被预算跳过），全部决策 RETRY。**不得据此宣称任何臂间效应**。
4. **P2**：证据治理的跨任务记忆/技能演化仍属长远研究问题，现无经验证的更新收益。

## 4. 当前明确禁止的推断

- 不因 235/235 结构 PASS 声称 235 个有效物理真值标签或两类 flag 平衡;
- 不将同技能 `final_meas` 描述为工具已交付 Planner 后的未来持续持握;
- 不将 Stage R 480 试验当作跨 480 个独立事件或真实顺序恢复;
- 不因研究版图或 PAEG 概念设计声称已验证长记忆、自动恢复或跨任务进化;
- 不把 sim `check_success`、对象坐标、状态重建元数据送入 Runtime/Evolution 作为合法在线结果;
- 不在 UNKNOWN 参考上引用任何"一致率/可靠性"数字;不在多数类未披露时单独引用 raw concordance(Stage2J-v2 M0-M5 纪律)。
- 不由 Stage R 连败 h(k) 下降推导 conformal 可交换性失效（PAEG M1 异质可交换足以解释）；不让 P1 无限弃权套利、不在 TEST 事后选最强对照。

## 5. 当前待办（禁止再次启动旧 DEV0）

1. **视觉文件数据验收已 PASS（5/5 两相机配对）**；原测试 2/3，零值统计键导致一例 KeyError，代码已修复。服务器仅需重新运行 `python3 -m unittest discover -s analysis/research_context -p 'test_p1_dev0_visual_pair_preflight.py' -v` 证明修复版测试通过；无需再次执行 GPU/仿真，也不必重复真数据配对扫描。
2. 若后验检查与既有数据一致，DEV0 正式结束；不补跑 3 格、不因各臂样本不足更改本批预注册任务/seed/阈值。
3. 下一研究若继续主动验证方法，首先明确 pre-delivery Harness 作为决策 consumer，找到能区分夹持状态的**真实合法新证据**（现有 D3 没有用图像像素且 EEF_z 变化判据不代表物体抬升），给出真正能让 RETRY/CONTINUE 两种决策均可达的新方案。必须另立有界 L2 预注册和严格硬预算才允许新仿真；P2 不启动。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
