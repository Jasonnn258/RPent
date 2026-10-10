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

> **P1 视觉审阅板真实生成完成（2026-10-09，用户服务器回传）**：修复后双脚本合成单测 **6/6 OK（0.607s）**；`scripts/p1_dev0_visual_review.py` 报 `PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER`、`n_boards=5`，已在私有 `artifacts/p1_dev0/visual_review/` 生成 5 张 Agentview 前后/差分、Wrist 前后纵向对齐/差分拼图。**真实图像内容尚未被本对话看到或评估，不可报告目标可见、抓持或标签效果**。为减少重复人工命令，已提交 `scripts/p1_dev0_visual_annotation.py` 与离线单测：生成不联网的本地 HTML 审阅表，允许五样本一次性进行可见性/遮挡/空间关系人工审查，并离线汇总。新审阅器**尚未在服务器测试/运行**；人工主观观察不等于物理真值标签。P1-DEV0 CLOSED、新仿真 L2 HOLD。

> **最新视觉审阅工具测试反馈（2026-10-09）**：用户服务器运行 `test_p1_dev0_visual_annotation.py` 得到 **0/4 PASS、4/4 `FileExistsError`**，错误均在 `fixture(root)` 重复创建由 `TemporaryDirectory()` 已创建的目录；由于使用 `&&`，**HTML build 未执行**。已在测试夹具改为 `root.mkdir(parents=True, exist_ok=True)`，commit `ee7efbe`，**修复版尚未在服务器重新测试**（2026-10-10 本机复跑 4/4 OK，服务器复跑仍留作可选）。已有五张 RGB 对照图与 6/6 图像测试 PASS 不受影响。无需新增仿真；只需复跑四项单测，PASS 后 build 私有 HTML。

> **VE-v0.1 视觉证据离线研究完成（2026-10-09/10，夜间自主阶段，全程只读离线）**：对 5 个真实 probe 前后图像完成可辨识性分析（MODEL_VISION 主观判读，非物理真值）+ 确定性 Evidence Claim 原型（`analysis/research_context/p1_ve01_evidence.py`，19/19 单测）+ 六臂对照（B0/B1=B2 冻结规则/B1′ stall 三态/B3 视觉护栏几何/B4 融合）+ 对抗测试 **10/10 PASS**。**核心新事实**：(1) probe 闭合结局三态成立——69mm→2.67mm/10步证明行程能力，t9_s1003(7.31→6.96mm)/t9_s1005(4.53→4.53mm)停住=物理阻挡，D2 的 gap<0.06 把其中 2 个接触案例一律误判 CONTINUE;(2) 薄沿持握(1.8mm flag=T)与空闭合(2.2mm flag=F)在 gap 轴原理不可分，probe 无 lift 时**任何模态都不能断言持握**;(3) 最大 wrist 差分(45.8,63.5% 像素)是纯深度视差(零信息)，护栏=整帧占比+SHA 新鲜度+翻转对齐;(4) 视觉真实增量=图像有效性裁决+接触方位(腕视世界图近场,t9_s1003 最近表面 0.5mm 落在指间投影带中心)，状态区分度 1/1/1→2/4/4。5 例无持握正例、无 probe 时刻真值 → 检出率不可估。详见 `P1_VE01_VISUAL_EVIDENCE_REPORT.md`。**判定：GO(离线证据原语)/ 最小修正 L2(lift-probe+正例+任务分层)HOLD 待用户授权**。

> **2026-10-10 独立复审 VE-v0.1（GitHub 源码层，不等于私有数据复测）**：最新夜间实验 commit `32af61b`，原型 19/19 + 对抗 10/10 为**仓库报告**。审查发现“gap plateau 必然=物理接触”“world_wrist 最近表面=目标接触”“B3 为纯视觉”“ADV7 零继续证明可靠性”“Planner think 的 flag=持握真值”等推断缺少可辨识性或独立对照。保留模型产生有效分箱与近场特征的探索性价值，收窄为 `GAP_PLATEAU_CAUSE_UNKNOWN`、`SURFACE_NEAR_EEF_IDENTITY_UNKNOWN`，不能称已确证的接触。另发现旧 B3/B4 没有输入 `validity` 先行保护。已新增离线、**不改旧冻结实验结果**的 `scripts/p1_ve01_safe_arms.py`（v0.1.1）与合成单测，检查 invalid/stale/字段冲突及物理归因歧义；独立方法审查见 `P1_VE01_INDEPENDENT_REVIEW.md`。**本轮新代码尚未在用户服务器测试/运行**。优先执行只读 v0.1.1 安全复审；不启动新仿真/训练/Runtime，L2 HOLD。

> **2026-10-10 用户服务器 VE01.1 安全门实际回传**：`test_p1_ve01_safe_arms.py` **10/10 OK**、`scripts/p1_ve01_safe_arms.py` 对既有5个 probe 输出 `eligible=5`，RETRY 3/5 + RETRY+ESCALATE 2/5；`NEAR_MIN_GAP_OBJECT_PRESENCE_UNKNOWN=3`、`GAP_PLATEAU_CAUSE_UNKNOWN=2`；几何最近表面 4 常规/1 近 EEF 但**身份未知**。 `claim_holding_positive=0`、`independently_verified_object_contact=0`、`audit_truth_used=false`：这是**没有生成物理正例真值**，不能宣称五次实际接触失败或零误报。下一步针对已有 P1-DEV0 事件设计了**只读时间点与标签来源审计** `scripts/p1_ve01_label_contract_audit.py`，检查 probe 时间与 audit-only 后续任务结果是否可合法配对并区分，不能以 H 后的 `check_success` 充当 probe 结束瞬间的物体接触/持握。新增合成单测 `test_p1_ve01_label_contract_audit.py`；**新脚本尚未在服务器测试**。DEV0 仍 CLOSED，新在线 L2 HOLD。

> **2026-10-10 服务器 label-time 审计实测与方法修正**：用户对旧版 `test_p1_ve01_label_contract_audit.py` 得到 **3/3 PASS**，21/24 有事件、6 trigger、5 probe；5/5 后续 audit 时间晚于 probe，4 fixed boundary、2 early episode end，0 integrity anomaly。回传旧 Gate=`NO_PROBE_TIME_PHYSICAL_LABELS_IN_EVENT_CONTRACT`。进一步源码独立复审发现旧 `with_probe_time_*_reference=0` 是**直接写入的常量**，尚未扫描真实 probe JSONL 的 schema，原 Gate 强度偏高。现已改为逐个检查 5 个实际 Probe 的顶层/嵌套字段是否符合原 `_run_probe` 合法白名单；发现未知字段、潜在 oracle 字段或形状异常则 **HOLD**，不打印敏感字段值；如果通过，只能报告 `NO_EXPLICIT_PROBE_LABEL_IN_RECOGNIZED_EVENT_SCHEMA`，**不能扩张为其他历史资产皆无真值**。配套合成测试新增未知字段/嵌套接触标签反例；**新版本尚未在服务器验证**。旧 DEV0 继续 CLOSED，下一 L2 需要单独授权。

> **2026-10-10 Label-time v2 真实服务器验收完成，离线准确率 Gate 正式 HOLD**：用户回传 `test_p1_ve01_label_contract_audit.py` **5/5 OK**；5 个 Probe JSONL 的顶层及合法子字段均符合既有 Runtime schema，未经审核新字段0；`NO_EXPLICIT_PROBE_LABEL_IN_RECOGNIZED_EVENT_SCHEMA`，24 allocated/21 events/6 triggers/5 probes，后续审计5/5严格晚于 probe；其中固定 H 后4、提前终局2。**限定含义：仅这五个事件包没有明示同步目标接触/持握参考，不证明其他历史资产无可用标签。** 源码追加核对发现 `dump_state` 的 `world_wrist`、hi-res、`segment` 均以 Toolkit `step_idx` 存储，`segment` 仅保存 source_step、box、mask_shape、overlay/世界位置，不保存原始二值 mask；旧 `_run_probe` 直接执行物理步，仅额外存 post RGB 和 proprio。故旧几何/segment 不能自动代表 probe 后目标接触。已提交设计稿 `P1_NEXT_L2_LABEL_AND_CONTRAST_GATE.md`（精确时间同步、独立目标/双指接触 audit、blind 机械效应对照、lift 单独分层、硬预算停止），**DESIGN_ONLY，未授权新 L2、未运行新实验**。在新增标签/批准前，不再对这五例声称持握准确率或方法收益。

## 1. 总状态

**`P1_DEV0_CLOSED / VE011_SERVER_10_OF_10_PASS / LABEL_TIME_V2_SERVER_5_OF_5_PASS / RECOGNIZED_PROBE_SCHEMA_5_OF_5_NO_UNREVIEWED_FIELDS / NO_EXPLICIT_PROBE_HELD_OR_CONTACT_LABELS / NEXT_L2_DESIGN_ONLY_HOLD`**

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
| **DEV0 RGB 本地对照（用户服务器回传）** | 修复后合成回归 6/6 OK；`PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER`，5 张真实 Agentview/Wrist 对照图写入服务器本地 | 图片尚未被视觉审阅或物理真值评价；离线人工标注工具已提交未执行 |
| **VE-v0.1 离线研究（仓库夜间报告）** | 报告称5例图像判读、Evidence Claim 原型 19/19、对抗 10/10；post-gap 3近地板/2高于地板停住，B3/B4 有额外状态分类 | **独立复审降级**：停住不证明物理接触，近 EEF 表面不证明目标接触；B3 含 EEF proprio；ADV7 零 CONTINUE 属代码约束，持握检出/因果收益仍不可估。参见 `P1_VE01_INDEPENDENT_REVIEW.md` |
| **VE01.1 服务器实际验证** | 10/10 tests OK；5/5 合法输入，3 near-min gap / 2 plateau，1 最近表面临近 EEF 但目标身份未知，0 held/contact 独立正例 | 只是保守的离线证据资格和未知状态，不能当作真实物理接触/持握性能；后续目标改为时间同步独立标签可得性 |
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

1. **Label-time v2 已在服务器通过 5/5，且真实 5 个 Probe schema 全部匹配**。无须再重复事件形状/哈希审计。当前冻结 P1 的 probe-time held/contact 准确率和 policy-effect 均**不能合法估计**；下一步仅以 `P1_NEXT_L2_LABEL_AND_CONTRAST_GATE.md` 为设计候选讨论同步 audit-only 目标物体接触/持握参考、探测机械效应对照、可达双分支、分层触发率与精确 H 时点。所有新仿真、Runtime、训练仍需独立明确的 bounded L2 授权。
2. 若继续 P1 主动验证方向，下一步是**修正设计的最小 L2**（用户授权后另立预注册）：probe 改"闭合+受控提升"使 lift 判据可用、采集含真实持握正例的分层样本（t9/t3/t5 配额）、验证触发时刻 hi-res wrist 覆盖、接线两分支可达的 pre-delivery 消费者。旧 D2/D3 冻结规则不得复活。
3. 不补跑 DEV0 3 格；不改在线 Runtime；私有图像/HTML/JSONL 留 `artifacts/` 与 `rpent_data/`，不入 Git。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
