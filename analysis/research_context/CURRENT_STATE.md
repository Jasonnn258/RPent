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

> **2026-10-10 实验驱动转向：P1 Module Lab v1（代码完成，私有服务器结果待跑）**。根据“先在复现好的 baseline 上做模块增删/位置互换，再从失败与阈值敏感性中提炼 Idea”的方法，已提交 `analysis/research_context/p1_offline_module_lab.py`、`test_p1_offline_module_lab.py`、`P1_MODULE_LAB_EXPERIMENT.md`。对已封版 EERD **206 个 A0 PRIMARY Pick** 的同技能 FGONLY 代理做**13 固定 arms + 48 不选优阈值扰动**；拆分 min/final gap、peak lift、AND/OR、flag rescue 模块；输出原工具失败的 56/103 proxy 不一致切片、补救回来的 proxy 正例数量与新增 proxy false accepts、按 task 分层、1000 次 episode 聚类配对 bootstrap，以及 3 折 leave-one-task-out 家族选择（两个 task 选择，第3 task 评价）。**不训练神经模型；audit 标签仅用于离线评分与训练任务里的模块选择，不作为任何 arm 的输入，不进 Runtime**。按冻结 A0 混淆阵 TP101/FP2/FN56/TN47 自守卫；`peak_lift` 与 FGONLY 都是运动学相关代理，只能报 proxy agreement，不能报真实持握准确率/因果收益。**提交不等于真实实验完成；新代码合成测试、206 私有 Pick 模块评测均尚未在用户服务器运行**。允许 L1 离线实验，P1 新 L2 仍 HOLD。下一步跑一条合成单测+真实离线模块表的命令，基于正/负收益决定保留哪一模块；不再重复 Probe JSONL QA。

> **2026-10-10 实验驱动第一轮真实回传（模块搜索的负结果）**：用户服务器 pull 至 `889cc3e`，`test_p1_offline_module_lab.py` **7/7 PASS**，实际206 A0 PRIMARY /175 episodes，任务3/5/9 =71/77/58。全部13固定arms对 FGONLY **balanced accuracy 均未超过**原 Tool flag 的0.801248（TP101/FP2/FN56/TN47）。其中 `min_gap0.060 AND peak_lift0.050` 虽然 raw agreement=0.830097，高于 Tool 0.718447，**BAcc仅0.769206**、proxy FP=17 vs Tool2；工具失败103例中它“补救”38个代理 FN，同时新增15个代理错误接受。原 flag 在 Task3/5/9 的 BAcc=0.923729/0.796237/**0.583333**，Task9 alone 占30/56代理漏报（53.6%）；LOTO 模块选择 test pooled BAcc=0.722735，低于 Tool0.801248。**实证 STOP 简单 gap/lift OR/AND 作为“持握改进”**。源码新发现：原 `pi0_pick` success 还要求**先下降0.10m**，且成功检查的是当前/final grip，不等于旧实验中的 min grip；先前 A0 gap AND lift 缺少下降 gate、替换了开度位置。已提交下一轮 **三门槛组件消融** `p1_pick_gate_lab.py` / `test_p1_pick_gate_lab.py`，检查工具三门阈值与真实 proxy 错误分解、各任务布尔格模式，不臆断单个 gate 因果，**新脚本尚未在用户服务器跑**。数值来源、限制与后续假设见 `P1_MODULE_LAB_SERVER_RESULT_20261010.md`。原 A0/DEV0 不改，新 L2 HOLD。

> **2026-10-10 三门槛消融真实执行完毕(本轮实验服务器自主运行,全程离线只读)**:`test_p1_pick_gate_lab.py` **6/6 PASS** 后对 206 PRIMARY 实跑,追加 `p1_pick_gate_followup.py`(合成 6/6 PASS 后实跑)。**(1) 末端 D∧L∧G_final 逐例完全重建原 Tool flag(0/206 分歧,103/103 对应,零 terminated 捷径成功)**——"逐 chunk 提前退出 vs 末端摘要"的时间差异在本队列不存在(D/L 单调累积+`closed` 查当前 grip=末帧 grip);**(2) 上一轮"13 模块全面弱于 Tool"的最优挑战臂差距中 0.086 BAcc 是 min↔final 开度错用伪影**(22 行全是"中途闭合末端重开",L∧G 臂 FP 7→17);修正后 **L∧G_final(去 D)=0.8553 vs Tool 0.8012(+0.054,episode 聚类 bootstrap 96.4%≥0,区间 [−0.004,+0.105])**,但 t3 −0.116 有害;**(3) D(绝对下降≥0.10m)是漏报主导源**:56 代理 FN 中 40 缺 D;t9 的 30 FN 中 24 缺 D(19 个"只缺 D",lift 中位 0.092/末端开度 0.0048 齐备),机制=**柜顶高起点几何(start_z 中位 1.20 vs t3 1.01,高 15-20cm)×绝对阈值的交互**,全部 FN 均预算耗尽退出;**(4) LOTO 修正族合并 Δ=−0.006(留 t3 选 L∧G_final 则 t3 测试 −0.116;留 t9 时训练选 flag)**——去 D 收益跨任务学不出,不可全局部署。**下一轮唯一最值得实验:几何相对下降门槛 D_rel 的预注册新采集对照(冻结三门槛为基线,t9 主层,FP 上限预登记),本轮不宣称收益,新 L2 HOLD。**详见 `P1_PICK_GATE_LAB_RESULT_20261010.md`;私有产物在 `artifacts/p1_pick_gate_lab/`。

> **2026-10-10 远端自主三门槛实验已完成；新时间持续性实验待跑**：GitHub `bb7c664` 记录实验服务器 Agent 完成三门槛消融（合成6/6 + 追加分析6/6、真实206），完整报告 `P1_PICK_GATE_LAB_RESULT_20261010.md`、D-031。D∧L∧Gfinal **206/206 逐例重建**原 flag；先前 L∧Gmin 的错用变量造成相对 L∧Gfinal **0.086 BAcc 实现伪影**。纠正后 L∧Gfinal BAcc 0.8553 vs Tool0.8012，但 Task3 下降0.116，3 task LOTO pooled差-0.006；56代理FN中40缺下降D、Task9 30 FN中24缺D（19只缺D），**未证明物理持握或因果恢复效果**。下一步查冻结 `research_package_a.py:label_reference`，发现 FGONLY 采用**整个技能任何一刻为正**，与退出时 Tool flag 的时间构念不同。已新增 `p1_temporal_proxy_lab.py` 与合成测试，做 **56 FN 与 Task9 19 D-only 的末尾/短暂 proxy positivity 对照**，必须复核源 SHA 与原A0逐例reference。**新脚本尚未在服务器跑测试与真数据**；结果分流到几何相对D或时间一致性研究。新 L2 仍 HOLD。

> **2026-10-10 FGONLY 时间持续性实验真实执行完毕（本轮实验服务器自主运行，全程离线只读）**：pull 至 `ce0f78f`，`test_p1_temporal_proxy_lab.py` **7/7 PASS** 后实跑，资格门（source SHA==schema_qa、206 逐例 flag/reference 一致、175 episodes）全过。补充实验 `p1_temporal_proxy_followup.py`（合成 **8/8 PASS** 后实跑，唯一操作变量=参考时点，臂/阈值冻结，零阈值选择）。**(1) 56 个代理漏报 = 26 个退出时仍正 / 30 个仅中途瞬时 / 0 未知**（17/26 末尾 3 个归档测量点连续为正）；101/101 工具成功行退出时仍正（时间上零冲突）。**(2) 持续/瞬时按门槛模式干净分离**：D-only 漏报 72.7%（24/33）退出时仍正，缺 L/G 漏报仅 8.7%（2/23）；26 个持续漏报 92.3% 是 D-only。**(3) 退出时点重打分：flag BAcc 0.8012→0.8850（FN 56→26），L∧G_final 0.8553→0.8909；两臂差从 +0.054 缩到 +0.0059**（episode bootstrap 中位 +0.0057，区间 [−0.046,+0.059] 跨 0）——gate-lab 去 D 收益约 **89% 是 any-time 参考时点伪影**；去 D 在退出时点 FP 2→16。**(4) t9 的 19 个 D-only：11 持续/8 瞬时，start_eef_z/descent 中位（1.2134/0.0664 vs 1.2258/0.0685）几乎无分离**——几何解释"为何缺 D"但不预测退出时状态；t3 5/6、t5 8/8 持续。**(5) 分流判定：下一方向=返回时点证据一致性（Temporal Evidence Consistency）**（同刻观测契约 + 门槛模式风险分层 D-only 72.7% vs 缺L/G 8.7%；P1 失败错位前提 54.4%→25.2% 返回时点）；Geometry-relative Descent 降级为条件性次级（剩 24 例、t9 内不可分、须在退出时点重评）。退出时点 FGONLY 仍是同一运动学弱代理，非持握真值；详见 `P1_TEMPORAL_PROXY_RESULT_20261010.md`；私有产物在 `artifacts/p1_temporal_proxy_lab/`。

> **2026-10-10 第二轮时间持续性结果已归档，第三轮实证实验代码就绪**：服务器 Agent 最新 `bd5048e` 完成 `p1_temporal_proxy_lab` 7/7、followup 8/8 合成测试、206真数据：原56 proxy FN分解为 **26个退出仍正/30个仅中途正**；去 D 的 BAcc 增益从任意时刻 +0.0541 缩到末端 **+0.0059**（末端 proxy FP由2增至16）；Task9 D-only 旧代理FN 19中11退出持续/8瞬时，单靠起点高度/下降深度难区分。核心研究动机转向 **Return-time Evidence Consistency**，Geometry-relative D 已降级。基于该实证，本轮提交 `p1_return_time_triage_lab.py`、`test_p1_return_time_triage_lab.py` 和 `P1_RETURN_TIME_TRIAGE_EXPERIMENT.md`，直接在原103个 Tool False 的合法工具返回字段上对 **6种固定无训练证据排序**测 Top20/40% 复核预算，使用 `any-time` vs `final_meas` 两种 audit-only FGONLY 参考对照，并特别查看 Task9 D-only 候选池内能否区分末端仍正/瞬时。任何排序只代表 **prioritize verification**，不直接 CONTINUE；无独立实际 held 真值。~~新代码已提交、测试和真实服务器实验均尚未运行~~（第三轮已于同日执行完毕，见下一条）。无新仿真、训练或 Runtime 修改，L2 保持 HOLD。

> **2026-10-10 第三轮 Return-Time Triage 实验真实执行完毕（本机只读离线）**：`test_p1_return_time_triage_lab.py` **6/6 PASS 后主代码零改动实跑**，资格门全过（source SHA/逐例 flag/reference 一致；103/26/56 分母复现，79 episodes）。**(1) 全局退出时参考**（26正/77负，基率 0.2524）：Top20% 下 LIFT_MINUS_GAP（`lift/0.05 − final_gap/0.06`，除数均为原工具冻结阈值）precision **0.810**（17正/4误选，lift **3.21**），PEAK_LIFT 0.714、D_ONLY_THEN_LIFT 0.750、D_ONLY 0.632、FINAL_GAP 0.524、基准 0.252；Top40% LIFT_MINUS_GAP recall **25/26**。**(2) 参考时点对照**：any-time 参考下三臂 Top20% 全 21/21=1.000——排序次序对参考时点鲁棒，仅量级变松；LMG 的 4 个 Top20% 误选全部是"中途曾正、退出已放下"的边界例。**(3) 任务分层**：t3/t5/t9 自身 Top20% lift 3.36/3.33/3.15 方向一致；**t9 D-only 子池（n=19，池内基率 0.579）lift 仅 1.30**——预登记分支二触发：合法 Tool Return 字段在该子池**不足以**区分退出持续 vs 瞬时，需要同刻物理/视觉观测（受控 lift probe / 腕视目标在场），静态末端阈值原理性不足。**(4) 鲁棒性**（新增 `p1_return_time_triage_robustness.py`，8/8 测试；顺带修复其 jackknife min/max LOO 组合公式 bug）：episode 聚类 bootstrap 下 LIFT_MINUS_GAP 2.5 分位 **0.619 > 基准臂 97.5 分位 0.354**（区间不重叠）；单 episode jackknife 最大影响 |Δ|=0.048；Top20% 构成 t3:2/t5:8/t9:11 非单任务。**诚实局限**：跨任务分数水平非平稳（t3 抬升天然小 → 全局混排只给 t3 2 席），部署应按任务内排名/配额，本轮零调参。**(5) 机制结论**：分支一成立——LIFT_MINUS_GAP 有预算选择性验证为新 cohort 可证伪机制（预测 Top20% precision ≥2×基率、各任务 lift ≥2）；分支二成立——t9 子池需最小同刻观测。报告 `P1_RETURN_TIME_TRIAGE_RESULT_20261010.md`、D-035；私有产物 `artifacts/p1_return_time_triage_lab/{triage_v1,robustness_v1}.json`。L2 仍 HOLD。

> **2026-10-10 Return-Time Triage 第三轮真实运行 + Task9 条件实验准备**：远端 Agent commit `db9d2b5` 已实跑103失败/79 episodes 的6组固定排序，6/6主单测、8/8鲁棒性测试。全局 LIFT_MINUS_GAP Top20% 命中17/21，precision=0.810 vs 随机0.252，任务内Top20%精度 t3/t5/t9=0.800/1.000/0.727；但全局21个席位仅2给t3，存在任务分布失衡。**Task9 D-only 已知困难子池(n19,退出FGONLY正11/负8) Top4精度0.750，仅相对该池基率1.30×**。因此新增固定 `p1_task9_conditional_lab.py` + 合成测试 + `P1_TASK9_CONDITIONAL_EXPERIMENT.md`，只在这19例内比较旧合法得分 Top4/8、1万次标签置换及留一episode，检验全局分诊杠杆能否在固定失败类别内成立；**新代码服务器尚未测试/实跑**。如果不成立，停止纯静态末端阈值精炼，考虑同刻观测协议（须另外授权新 L2）。本轮无新sim/GPU/Runtime。

> **2026-10-10 追加增量信息消融（L1代码已提交，服务器未跑）**：在第三轮真实103 Tool False结果中，LMG 全局Top20% 17/21 正例相对全局随机5.30/21呈3.21倍富集，但该21席 **全部gate=011，t3/t5/t9占2/8/11**，因此不能将全局富集直接归于 LMG 连续分数；存在门槛组成、任务配额的混合因素。除现有 `p1_task9_conditional_lab.py`（Task9 n19池内固定Top4/8，1万次置换，待跑）外，本轮新增互补实验 `p1_triage_incremental_lab.py` + `test_p1_triage_incremental_lab.py` + `P1_TRIAGE_INCREMENTAL_EXPERIMENT.md`：保持固定分数和预算，计算 **Global/Gate/Task/Task×Gate匹配随机** 的同等席位预期命中，估计连续分数在子群内的净增量，episode聚类bootstrap仅做描述性不确定性。**新增代码尚未在用户服务器运行**；若匹配后 Δ≈0，则停止将复杂排序包装为主创新，只保留风险分层/预算分配候选。所有参考是FGONLY末端运动学弱代理，不是held/contact真值；新L2仍 HOLD。

> **2026-10-10 第四轮两项互补 L1 实验真实执行完毕（本机只读离线，12/12 测试零改动）**：pull 至 `49cd3bd`，资格门全过（103/26/56、t9∧011 子池 19/11、池内 19 个单例 episode）。**(A) Task9 D-only 条件可辨识（D-036）**：Top4 三连续臂完全同分 3/4=0.750（lift 1.30），1万次标签置换 p=0.427/0.434/0.418；Top8 最好 6/8=0.750（p=0.213）；留一集区间 [0.750,1.000] 不低于全量但 n=19 高基率下是弱证据；D_ONLY_THEN_LIFT 池内退化 0.643（lift 截断在池内制造并列，冻结设计缺陷如实登记）→ **停止门触发：淘汰继续精炼静态末端阈值区分 t9 退出持续/瞬中的路线**（与 D-033 几何不可分、D-024/D-025 gap 重叠区三方独立一致）。**(B) 103 例匹配增量分解（D-037）**：LMG Top20 观测 17 正，Global 随机 5.30 → Gate 匹配 13.26（精确等于 D_ONLY 臂观测，内部自洽）→ Task×Gate 匹配 **14.48**；**组成效应解释 3.21× 富集的 78%，连续分数组内增量仅 +0.120**（episode bootstrap 中位 +0.111，95% [−0.022,+0.256]，96.4%>0；any-time +0.080、Top40% +0.062 同向）；三臂增量 PEAK_LIFT +0.091 / FINAL_GAP +0.120 / LMG +0.120——**融合相对单一轴无额外优势**；任务内增量 t3 +0.300 / t5 +0.111 / t9 +0.148 全正。**(C) 统一裁决**：主杠杆 = 廉价"门槛风险分层+分任务预算"（零拟合即 14.5/21=0.69，2.72× 随机）；连续分数降级为需独立 cohort+持握标签确认的次要候选；全局 3.21× 今后必须按"0.69 组成 + 0.12 增量"分解引用，不得再当排序器信息量。唯一下一步 = **同刻观测最小 L2 合同**（分层含真实持握正例、probe 改闭合+受控提升 2-3cm、任务内排名分预算，组成分层作免费基线臂）。报告 `P1_TASK9_CONDITIONAL_RESULT_20261010.md`、D-038；私有产物 `artifacts/p1_return_time_triage_lab/{task9_conditional_v1,incremental_v1}.json`。L2 仍 HOLD。

## 1. 总状态

**`PACKAGE_A_FROZEN / P1_DEV0_CLOSED / TRIAGE_103_SERVER_6_OF_6_PLUS_8_OF_8_PASS / GLOBAL_TOP20_LMG_17_OF_21_PROXY_POS / T9_CONDITIONAL_CODE_UNRUN / TASK_GATE_MATCHED_INCREMENTAL_CODE_UNRUN / NEW_L2_HOLD`**

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
| **Module Lab v1(用户服务器)** | 7/7 tests;13 固定臂 BAcc 全部低于 Tool 0.8012;LOTO 合并 −0.078;t9 占 30/56 代理 FN | 挑战臂缺 D 且误用 min 开度;结论需按 gate-lab 修正重读;详见 `P1_MODULE_LAB_SERVER_RESULT_20261010.md` |
| **三门槛消融 Gate Lab(2026-10-10 实跑)** | 6/6+6/6 tests;末端 D∧L∧G_final **逐例=flag**(0/206 分歧);L∧G_final 0.8553(+0.054,96.4% bootstrap≥0)但 t3 −0.116;min↔final 伪影 0.086 BAcc/22 行;t9 30 FN 中 24 缺 D,机制=柜顶高起点(start_z 1.20 vs 1.01)×绝对 0.10m 阈值;LOTO 合并 −0.006 | FGONLY 弱代理同源;描述性敏感性;去 D 收益 t9 特异不可全局部署;下一轮=几何相对 D_rel 预注册新采集,本轮不宣称收益;详见 `P1_PICK_GATE_LAB_RESULT_20261010.md` |
| **Temporal Proxy Lab(2026-10-10 实跑)** | 7/7+8/8 tests;SHA/逐例资格门全过;56 FN=26 退出持续/30 瞬时/0 未知;D-only 持续率 72.7% vs 缺L/G 8.7%;退出时点重打分 flag 0.8850 / L∧G_final 0.8909(Δ=+0.0059,bootstrap 跨 0)——去 D 收益 89% 是时点伪影;t9 D-only 11 持续/8 瞬时且几何无分离 | 退出时点 FGONLY 仍是同一运动学弱代理非持握真值;P1 失败错位前提修正为 25.2%(返回时点);下一方向=返回时点证据一致性;详见 `P1_TEMPORAL_PROXY_RESULT_20261010.md` |
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

1. **第四轮两项互补 L1 实验已执行完毕（2026-10-10）**：Task9 D-only 子池置换 p 0.21–0.43 判静态阈值路线 **STOP**；103 例匹配分解判组成效应解释 78% 富集、连续增量 +0.120（区间跨 0）。唯一保留主候选 = 廉价门槛+任务组成分层（0.69/Top20% 零拟合）；连续分数为次要候选需独立 cohort。唯一下一步 = 同刻观测最小 L2 合同（等用户授权），不启动新仿真或 L2。
2. 若继续 P1 主动验证方向，下一步是**修正设计的最小 L2**（用户授权后另立预注册）：probe 改"闭合+受控提升"使 lift 判据可用、采集含真实持握正例的分层样本（t9/t3/t5 配额）、验证触发时刻 hi-res wrist 覆盖、接线两分支可达的 pre-delivery 消费者。旧 D2/D3 冻结规则不得复活。
3. 不补跑 DEV0 3 格；不改在线 Runtime；私有图像/HTML/JSONL 留 `artifacts/` 与 `rpent_data/`，不入 Git。

## 6. 标准汇报格式

每轮仅更新:`HEAD`、`VERIFIED`、`REPORTED`、`PROPOSED`、`BLOCKED`、`NEXT`、`GO/HOLD/STOP` 和原始来源。禁止用"有望/看起来"替换实际验收结果。
