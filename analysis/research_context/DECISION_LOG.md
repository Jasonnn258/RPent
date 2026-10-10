# RPent / Harness VLA — DECISION_LOG

> 研究重大决策的**追加式记录**。每项写明：决定、证据、替代项、约束、重新开启条件。日期为做出本次研究上下文归纳的日期，历史事件的确切日期/提交以原始审查文件为准。
> 本文的“研究路线优先级”是**候选建议**，不是解除 Stage R 实验禁令，也不是用户授权新的 rollout。
> 权威原始记录：`analysis/stageR_prereg.md`、`analysis/harness_next/METHOD_SPEC.md`、`NOVELTY_REVIEW.md`、`analysis/harness_h0/H0_OE_STAGE2I_SERVER_RETURN_REVIEW.md`。

## D-001 · 按证据/执行层级拆分物理成功与工具报告

- **状态**：已确立的方法学原则。
- **决定**：分别记录 tool success、同技能 ACQ-like 取得、后续持续保持、任务终局与真实 Planner 接收证据时刻，不将其当作同一标签。
- **理由**：`pi0_pick` 使用下降-提升-夹爪阈值及终局镜像；Stage R 的 hold-through/重建执行语义不同；`final_meas` 于 Planner 接收工具结果前取样。
- **结果**：Stage2E/F/G/H 审查将 D1 执行器内部切点与 D2 Planner 工具返回切点分离；原冻结 ACQ/STABLE 不可静默替换。
- **重新开启**：有新合法采集流程能明确产生返回后的固定未来窗口、且拥有独立审计与时间对齐证据。

## D-002 · 维持 Stage R §36 HARD STOP、S1-DEV0 ON_HOLD

- **状态**：持续生效（原始权威约束）。
- **决定**：不可因结构审查 PASS 或理论规范完成而自动跑控制、恢复、验证器、训练或自进化。
- **理由**：现有结果限于已测协议；缺少证据资格、前瞻独立验证和运行时可消费性。
- **重新开启**：用户明确批准新的阶段、预注册、评价与权限边界；既有冻结文件只读。

## D-003 · Stage R 重建数据是研究性物理审计资产，不能直接作为长期进化授权

- **状态**：已确立的数据权限原则。
- **决定**：Stage R 重建 `S_pre` 的 SAME/RESAMPLE/NATURAL 试验供离线机制审计；`research_audit_truth` 永不因归档进入 Runtime/Evolution。
- **理由**：试验间独立重建，存在重建误差与固定策略条件；E/A/P/U 离线标签无法直接在真实决策时观察。
- **重新开启**：新来源验证了合法的 `evolution_eligible_outcome`、适用窗口与独立持续性证据。

## D-004 · 用 Git 中的三文件体系保持研究上下文连续

- **状态**：2026-10-09 用户明确要求建立；三个文件已完成并提交。
- **决定**：`RESEARCH_MASTER.md` 保存长期问题/知识边界；`CURRENT_STATE.md` 保存真实最新状态；`DECISION_LOG.md` 保留选择与弃选的依据。
- **理由**：ChatGPT 自动记忆和长对话摘要不具备逐项完整性、固定版本或代码/结果可追溯性。
- **维护**：每阶段更新 CURRENT_STATE；重大选择追加本日志；Master 仅在研究问题/边界真正改变时修订。不得把候选主张当作已证实结果。

## D-005 · 候选研究路线：P0 数据可信度 → P1 主动验证与恢复 → P2 长期证据进化

- **状态**：研究建议，**未批准任何新控制实验**。
- **决定**：以现有 187 episode / 235 pick / 24 event / 480 frozen trials 为 P0 的有限基础；P1 优先验证“何时/是否值得追加证据及改变动作”；P2 在有独立任务和回归验证时研究记忆/技能演化。
- **理由**：图1–4 所展示的闭环和进化愿景需要连接“合法证据 → 实际决策收益”；CheckVLA、Zetta、RegenHarness 等已有验证/恢复/状态提交先例，必须通过具体假设、强基线与成本对照区分创新。
- **替代**：可以仅完成 P0 工程基线并停止 H0 数值工作，不强求以描述性定标冒充新算法。
- **重新开启**：预注册定义统一的决策切点、观察预算、终局标签、对照组与错误代价，并得到显式批准。

## D-006 · Stage2I V1 服务器返回仅确认结构完整

- **状态**：用户服务器执行结果已回传并登记（`84fc36b`）。
- **决定**：`235/235` 外层结构配对 PASS；**不自动执行 outcome/class 支持性统计**。
- **理由**：V1 脚本未读取 `result.success` 与 `check_success` 取值，也未检验目标内部物体坐标足以构造 FG 标签；235 是重复 episode 内相关调用。
- **下一决策点**：独立审查 Stage2J 预注册候选，对 A0 的结果构念、shortcut 与实际研究价值作 GO/HOLD/STOP，默认不得越过原始授权。

## D-007 · Stage2J 候选完成，但冻结前必须修订参考缺失和截断字段

- **日期/来源**：2026-10-09；Stage2J `762bf1a`，Stage2K 独立复审 `2b3710e`。
- **状态**：**REVISION_REQUIRED / 实验 HOLD**，Stage2J 保持 `DRAFT_NOT_FROZEN`。
- **决定**：不直接将 A0 预注册候选冻结或运行。需修正 (1) “any(FG)”存在性判据下丢失关键测量点会制造假负例，改成三值结果/完整案例方案；(2) `episode_truncated` 在 states step 顶层而非 `pi0_pick.result`；(3) raw concordance 不足以独自证明工具成功反馈可信，至少申报类别结构和常数预测对照，或在新的决策消费者下预先改主指标。
- **证据**：`analysis/harness_h0/H0_OE_STAGE2K_STAGE2J_INDEPENDENT_REVIEW.md`；`robots/libero/tools.py`、`rpent/utils/rtrace.py`。
- **不能推出什么**：235/235 外层结构配对 PASS ≠ 235 个完整物理标签或两类性能可估；此复审也没有读取 outcome 值。
- **重新开启条件**：用户指定有意义的分析用途，形成修订的独立 v2 候选并批准后续字段资格/结果值分析。

## D-008 · 将 EERD 文档契约与 H0 A0 数值立项分离

- **日期/来源**：2026-10-09；用户此前提出“这些数据能否形成数据集、如何使用”及本轮“建立长期上下文并继续研究”；EERD `70d57ba`。
- **状态**：EERD **研究设计 GO**；数据物化/标签计算、P1 新控制试验 **HOLD**。
- **决定**：另立 `analysis/research_context/EERD_V01_DATA_CONTRACT_DRAFT.md`，将原始执行证据与冻结失败重建试验分成具有独立时间与干预语义的 A/B 子集；C 类主动验证/恢复后果只能由未来独立设计产生。数据集/Benchmark 是合法**研究用途**，不要求先拥有 Runtime 消费权限；但其数据导出、打标签、部署和训练仍需单独审查批准。
- **证据**：Stage2I 的 187/235/2859 结构回传、Stage R 的 24/480 冻结试验、PAEG §5.6 权限防火墙、Stage2K B1–B4。
- **不能推出什么**：文档契约完成 ≠ 数据集已发布；无独立外部验证、无在线 Harness 收益、无新算法创新。
- **重新开启条件**：完成字段可见性与标签来源审查、数据使用授权、按 event/episode 隔离的评测协议，再考虑 v0.1 实际物化；P1 要另立预注册和实验授权。

## D-009 · Stage2J-v2 候选交付:B1/B2/B3 全部解决,设计层重获冻结资格,执行仍 HOLD

- **日期/来源**:2026-10-09;基线 `4d155b9`;Stage2K(`2b3710e`)B1-B3;Stage2J v1 `762bf1a`(原文保留不改写)。
- **状态**:DESIGN_COMPLETE(候选);冻结与执行各自另行批准。
- **决定**:v2 以三项结构性修订解决 Stage2K 判定的阻断——
  1. **B1**:参考改三值状态机 POSITIVE/NEGATIVE/UNKNOWN + 预定义完整应观测点集 Q(= chunks_used+1 个点,逐点 VALID/MISSING/NONFINITE 分记);POSITIVE 由单有效真点即sound(存在性单调),NEGATIVE 需 Q 完备——不对称是构造性 sound 而非调参;UNKNOWN 不进 2×2 主表、率单独报;完全案例敏感性表并列;不假设 MAR。
  2. **B2**:勘误登记 v1 `result.episode_truncated` 字段不存在(pick 返回字典 tools.py:254-272 无此键);截断唯一合法来源=states.json 步级顶层(dump_state tools.py:1147,且经 view_driver_state :1621 在线投影=合法可见协变量);对齐断言 A1(result↔states 终局旗一致)/A2(join)/A3(|Q|=chunks_used+1);PRIMARY 语义修正为"flag=True⇒运动学锁存;flag=False⇒退出前未触发锁存(预算耗尽或截断两路径)",撤回 v1"纯运动学"过强断言;截断 NEGATIVE 申报为删失负例,PRIMARY_UNTRUNCATED 敏感性子集预登记。
  3. **B3**:主交付从单一 raw concordance 改为六件套普查包(M0 类别结构先行/M1 全 2×2+UNKNOWN 列/M2 双条件风险 R_accept 与 R_miss 各两变体/M3 一致率+双常数基线+κ/M4 聚类区间/M5 宣称语言冻结);消费者条件伴报 C1(P1 立项时主指标切向 R_accept)**现在预登记**,杜绝读数后挑指标;可估性门 E1-E4。
- **证据**:`analysis/harness_h0/H0_OE_STAGE2J_V2_A0_PREREG_CANDIDATE.md` + 源码行号级复核。
- **不能推出什么**:设计完成 ≠ 已冻结/已执行;235 结构 PASS ≠ 类别/字段资格;FGONLY 仍是研究代理非接触/保持/任务 oracle。
- **重新开启条件**:用户批准冻结(独立于执行);执行另需检查 B + outcome 读取双重授权。

## D-010 · EERD 字段级契约补全 + P1 最小可证伪问题 + 方向分级与文档轮次封顶

- **日期/来源**:2026-10-09;EERD 契约 `70d57ba` + 本轮配套规范;P1 问题文档;Stage2K B4 三分解。
- **状态**:研究设计 GO(文档);物化/打标签/闭环实验 HOLD。
- **决定**:
  1. **EERD**:新增字段级来源表(A 子集 17 行/B 子集 9 行,逐字段文件→路径→产码行号→语义→可见性→质量规则)、三操作视图权限矩阵(online_eligible/audit_only/reconstruction_metadata,物理分离+黑名单校验)、样本分组(A 按 episode、B 按 parent_failure_event_id、cross_dataset_provenance_group 防同源泄漏——24 R1 事件源 episode 在 187 内)、物化前置验收门 G-QA-1..8(join/对齐/完整性账本先行/视图隔离/假名化/源哈希/schema 阶段零 outcome 读/标签纪律)。
  2. **P1**:冻结最小可证伪假设 H-P1(等预算错误完成率差)+ 机制定位子假设 H-P1m(收益须集中于持续性失败子群=exchangeability 失配处)+ 五对照(C-1 无验证/C-2 固定间隔/C-3 始终/C-4 静态阈值含 conformal/C-5 随机同时机)+ 证伪条件预写死;与 CheckVLA/Zetta/RegenHarness 的机制差异全部转为可检验对照,无差异则如实让渡;C 子集字段需求与"不可从 A/B 构造"理由表(Stage2G D2 合法性 vs 协议固定性不可兼得)。
  3. **方向分级**:理论充分四项(PAEG/Stage2J 设计/EERD/P1 问题)进入**文档轮次封顶**——无新数据或外部实质缺陷不再修订;需实验两项(A0 数值普查、C cohort+P1 闭环);停止五项(A/B 上新回顾性代理、C 前机制变体细化、任何在线接线、S1 重开、以及"用户不授权 C"情形下 P1/P2 收官为可接受终态)。
- **对照/替代**:Stage2K 建议的"完全案例 or 三值"取舍→v2 双轨(三值主+完全案例敏感性);P1 基线强度取 conformal 为最强静态形态而非稻草人。
- **不能推出什么**:文档 ≠ 数据集已发布;P1 问题可证伪 ≠ 机制有效;分级不含任何执行授权。
- **重新开启条件**:用户对 A0/C/收官三选一;§36 局部解除只能随 P1 预注册整体批准。

## D-011 · 修复 P1 主假设的三项方法学阻断及 EERD QA 阶段冲突

- **日期/来源**：2026-10-09；P1 v1 `analysis/research_context/P1_ACTIVE_VERIFICATION_RESEARCH_QUESTION.md`（新增于 `032e188`）；此前已冻结的 `analysis/harness_next/METHOD_SPEC.md` v0.2.2 §5.5；独立方法复审。
- **状态**：**SUBSTANTIVE_CORRECTION_APPLIED / P1 DESIGN STILL ONLY / EXECUTION HOLD**。此项属于“文档轮次封顶”下明确允许的**实质缺陷修正**，不是新一轮无数据的理论扩展。
- **决定**：
  1. **M1 异质性≠M2 时序依赖/可交换性失效**：原 P1 H-P1m 把 Stage R 的 `h(k)` 下降直接解释为 conformal exchangeability 失效，**与仓库 METHOD_SPEC §5.5 已明确的异质 iid/可交换选择效应矛盾**。修订后把机制子群限定为**事先用合法 D2 观测前缀定义**的高不确定性子群；不可用离线 P/E/A/U 真值定义 TEST 分层，不能声称 CheckVLA 保证必然失败。
  2. **错误完成率不能靠永远 ABSTAIN 降低**：保持主指标但新增完成声明覆盖率的非劣性门、弃权/超时上限、物理完成率和总预算共同门；报告选择性风险—覆盖曲线，过不了门就是未支持。
  3. **禁止在 TEST 事后择优 C-1..C-5**：必须先在 DEV/CALIBRATION 锁定最强基线，再一次性独立 TEST；额外比较须预注册统计多重性处理。
  4. **A0→C 不是被证明的信息最优或必要路径**：A0 的技内 FGONLY 与 P1 的 episode 级未来错误完成构念不同，不能直接把 A0 `R_accept` 当作 P1 的功效先验；可选择 A0 支持字段审查，但不能把其设为 C 必须的科学前置。
  5. **EERD G-QA-3 原先同时要求 schema 阶段零 outcome 读取和 UNKNOWN 按 flag 分层，流程冲突**。已改成 schema-only 字段完整性账本先行，获 outcome 授权后才做标签分布/UNKNOWN 分层；防火墙与 G-QA-7 保持。
- **证据**：`METHOD_SPEC.md` §5.5 M0/M1/M2 明确区分；`robots/libero/tools.py:223-272` 的真实 Pick flag；`analysis/research_context/P1_ACTIVE_VERIFICATION_RESEARCH_QUESTION.md` v1.1（commit `92384e5`）；`EERD_V01_FIELD_PROVENANCE_QA_SPEC.md`（commit `a040bfa`）。
- **不能推出什么**：修订 ≠ P1 控制器实现/方法收益，也不证明任何 conformal 假设在新的 C cohort 中成立或失效；未运行实验、未读取 outcome。
- **重新开启条件**：新 cohort 和数据审查获得单独明确授权；尚需独立预注册与规划，不自动解除 Stage R §36 HARD STOP。

## D-012 · 用户批准 Research Package A 的阶段级 L1 离线授权

- **日期/来源**：2026-10-09；用户明确同意“阶段级授权，执行 Research Package”——承接上一轮所定义的 Research Package A。
- **状态**：`APPROVED_L1_SCOPE / EXECUTOR_COMMITTED / SERVER_EXECUTION_PENDING`。
- **决定**：在一次授权内完成已有 187 原始 episode / 235 pick 的字段验收、Stage2J v2 FGONLY 三值标签、A0 描述性统计与 Episode 聚类区间，以及 EERD v0.1 A/B 内部数据视图与 QA；只读原始数据和 Stage R 冻结结果；不需要每个字段、统计子步骤再次请求许可。
- **冻结依据**：`analysis/research_context/RESEARCH_AUTHORIZATION.md`；独立 A0 冻结执行映射 `analysis/harness_h0/H0_OE_STAGE2J_FROZEN_V2_PACKAGE_A.md`；源代码 `analysis/research_context/research_package_a.py`；合成测试 `test_research_package_a.py`；一键服务器入口 `run_package_a.sh`。
- **保留边界**：新 rollout / C cohort / P1 干预 / 训练 / Runtime 编辑均未获批；Stage R §36 HARD STOP 和 S1 ON_HOLD 继续有效。允许 L1 内部数据物化不等于对外发布或给模型使用研究审计真值。
- **实际结果**：GitHub 代码与文档已提交；**当前工具环境没有私有服务器原始轨迹，因此尚无 A0 样本资格/结果值统计、没有 EERD 数据集实际物化、合成测试尚未在服务器运行**。把待完成步骤收束为一次服务器执行，收到结果后直接处理异常/验收，阶段内不再就已授权 L1 子任务询问。
- **防跑偏要求**：只认服务器实际回传的 `schema_qa.json`、`a0_result.json`、A0 报告与文件哈希；不把预注册通过、脚本存在或 synthetic tests 编写等同于真实结果。任何 STOP 门失败停本阶段受影响的分析，不后验改指标。

## D-013 · A0 真实服务器统计完成：主要错位位于工具失败反馈侧

- **日期/来源**：2026-10-09；用户在服务器执行 Research Package A，并贴回终端输出；运行分支 `30f2a1e`；协议 `RPENT-PACKAGE-A-STAGE2J-V2-EERD-V01-20261009`。已将脱敏汇总独立存档于 `PACKAGE_A_A0_SERVER_RESULT_20261009.md`。
- **状态**：**SCHEMA_PASS / A0_OUTCOME_PASS / B_BASIC_QA_PASS / EXPORT_FINAL_QA_PENDING**。三个合成回归测试服务器报告 OK；真实输入 187 episodes，235 picks，全部结构及字段资格合格，PRIMARY 206，UNKNOWN=0；B 24 events×480 trials 通过现有基本 QA。
- **关键实测**：在不涉及 terminal 镜像的 PRIMARY 中，`flag=True` 103 与 `flag=False` 103；FGONLY POSITIVE 157 / NEGATIVE 49。**按常规混淆矩阵语义** TP=101、FP=2、FN=56、TN=47。`R_accept=2/103=1.94%` (episode cluster bootstrap 95% [0,4.85%])；`R_miss=56/103=54.37%` (95% [45.26%,64.29%])；一致率 `148/206=71.84%` (95% [65.88%,77.56%])。FGONLY prevalence 高，always-positive 对照一致率 76.21%，不能以 raw concordance 单独选策略。
- **源码级呈现陷阱**：冻结分析程序 `stats()` 的 `table.false_positive` 表示 `(flag=False, FGONLY=POSITIVE)`，是**传统 FN 56**；`table.true_negative` 表示 `(flag=True, FGONLY=NEGATIVE)`，是**传统 FP 2**。修正的是**结果展示语义**，不修改已冻结的原始统计文件、结果/主指标或样本资格。新增独立 `audit_package_a_exports.py` 用于服务器端验证并输出标准混淆矩阵的附属视图。
- **主要解释与限制**：目前最强的描述性信号在工具失败侧（FGONLY 技内代理已有取得但工具报失败），但两者操作契约不同：FGONLY 存在于技内某个点，不保证 D2 时仍持握、更不保证未来真实完成。不能将 56 个“代理错位”直接称真实成功/不必重试，也不能据此证明恢复策略效果。
- **研究路线影响**：P0/A0 已得到一次完整实测，不再重跑同一数据追数字；将 P1 候选问题聚焦为“失败反馈后何时验证物理状态、何时直接重试，是否在相同成本下改善 episode 级真实任务结果”，而不是仅重复失败归因概念；L2 新实验依然 HOLD。
- **下一步**：在已有 L1 授权中做**一次导出产物复核**（A/B 分文件、样本数、跨视图键、泄漏边界、8+8+4 重建分组），只记录脱敏 Gate；真正的新前瞻 C cohort 要单独 L2 批准。
- **不能推出什么**：A0 描述性结果 ≠ 实际接触/长期持握的真值分类；EERD 内部文件已由脚本生成 ≠ 所有八道 QA 均已独立通过或公开数据集已经发布；不存在本次 ChatGPT 环境直接读服务器文件的事实。

## D-014 · Package A 内部数据集与导出 QA 收官

- **日期/来源**：2026-10-09；用户于服务器同步分支至 `741278a` 后执行 `python3 analysis/research_context/audit_package_a_exports.py --output artifacts/research_package_a`，并回传完整 Gate 摘要。
- **状态**：`PACKAGE_A_CLOSED_INTERNAL_V01 / EXPORT_QA_26_OF_26_PASS / P1_L2_HOLD`。
- **确认结果（用户服务器回传）**：`gate=PASS`、`checks_passed=26`、`checks_total=26`、`failures=[]`；A=235 Pick 行、PRIMARY=206、UNKNOWN=0；B=480 trials，24 父事件；标准矩阵 TP=101、FP=2、FN=56、TN=47。已在 `PACKAGE_A_A0_SERVER_RESULT_20261009.md` §6 追加完整脱敏 QA 回执；GitHub 只存报告和源代码，未上传私有 JSONL。
- **决定**：Research Package A 的**离线基线审计、内部 EERD v0.1 物化及当前版本工程验收已完成**；不再重复 A0 数值分析，也不再用无新增科学问题的纯文档轮次延迟 P1。
- **证据局限**：本次 26 项为结构、输出视图权限字段、join、预定条数、B 臂完整性及已报告统计的自洽检查；其中含硬编码预期计数，不能当作完全独立统计复制、特权信息零泄漏的数学证明、物理标签效度检验或跨任务外推。A0 FGONLY 是同技能存在性代理。
- **研究意义**：主分析工具失败后技内 FGONLY 代理曾满足的条件率 56/103；这是 P1 “失败返回后追加验证还是直接重试”的**可验证研究动机**，不是已证实的物理持握成功或动作收益。
- **权限边界**：已有 L1 阶段收官。P1 新 cohort/在线策略对照/恢复接线属于 L2，需新的完整阶段授权；Stage R §36 HARD STOP 与 S1-DEV0 ON_HOLD 仍有效。
- **重开条件**：P1 新数据/新授权、独立的标签有效性证据或出现真正影响当前科学结论的实质缺陷。

## D-015 · P1 从失败标签转向真实 D2 的“机械效应 × 信息价值”研究

- **日期/来源**：2026-10-09；用户在 Research Package A 收官后要求“go on”；本轮核对 `robots/libero/toolkit.py:_step`、`robots/libero/tools.py:view_driver_state,set_gripper,dump_state` 与 EERD 字段 QA。
- **状态**：`P1_OFFLINE_PREFLIGHT_READY / P1_L2_DESIGN_SCOPED / NEW_ROLLOUT_HOLD`。
- **决定**：优先在已有 187 个 episode 上执行只读 D2 合法前缀可用性预检（`analysis/research_context/p1_d2_preflight.py`）。在新的 L2 真实验证试验里，必须区分再次读取同一帧、读取已有其他视角和推进物理环境产生新的观测。
- **科学原因**：`view_driver_state` 读取历史数据，重复调用不创造未来物理状态；`set_gripper(gripper=+1,steps=N)` 会执行环境动作，也可能稳定夹持。单看 probe+policy 相比 blind retry 更好，不足以证明 Evidence Gate 的信息价值。
- **必要对照**：no-probe、probe-then-blind（隔离物理干预）、probe-static（简单合法判据）、probe-evidence-policy（PAEG 候选），统一真实 D2 触发和预算；在独立后续固定 horizon 评价，屏蔽 `sim_measurement/check_success` 在线消费。
- **阶段边界**：`P1_L2_STAGE_GATE.md` 建议的 DEV0 最多 24 新 episode / 8 小时墙钟 / 6 GPU·hour 仅是**下一次完整阶段授权的对象**；当前“go on”先推进离线可行性和研究方法准备，不解释为可以越过 §36 执行未知费用的仿真/Runtime 修改。
- **不能推出什么**：原 A0 的 56/103 技内代理错位不等于 D2 真正持握，不提供新试验效应量；D2 档案图像缺失可能由后续清理造成，不能直接称历史时刻缺失。
- **重开条件**：只读 D2 Gate 回传、用户授予明确有界 L2 DEV0 或有方法构念的实质新证据。历史 Stage R/S1 冻结保持。

## D-016 · D2 合法输入资格已由服务器实测验证，P1 DEV0 应按任务分层

- **日期/证据**：2026-10-09 用户服务器在 `3a39cb7` 执行 `test_p1_d2_preflight.py`（2/2 PASS）和只读 `p1_d2_preflight.py`，回传完整脱敏计数与 `STRUCTURE_PASS_FOR_DESIGN`；研究接口见 `P1_L2_STAGE_GATE.md` §3.1。
- **状态**：`P1_D2_PREFLIGHT_STRUCTURE_PASS / PROPOSED_L2_DEV0 / NO_L2_AUTHORIZATION`。
- **结果**：187 原始 episodes、235 Pick；29 terminal/truncation 排除；206 个 D2 合格 Pick，其中 103 tool failure、103 tool success。206/206 已归档 low-res agentview/calibration/wrist 图像，EEF pos/quat 和 gripper qpos 均有限；hi-res 现存 105、缺失 101（可能因后续归档清理）；198/206 有自然后续 Planner 命令记录。
- **新风险**：tool failure 分布 t3=21/71 (29.6%)、t5=30/77 (39.0%)、t9=52/58 (89.7%)；task9 占全部 103 次工具失败中的 52 次。未经分层的新实验会把任务难度/触发率与验证策略效果混淆。现有预检**没有按任务计算 FGONLY mismatch**，不能据此声称 task9 物理漏报最多。
- **决定**：P1-DEV0 新任务/seed/arm 分配应预先按 task 固定；最多 24 新 episode 四臂初期验证仅做可行性与触发分母核验，不能用少量/非均衡触发结果做显著性结论；建议只在每个 episode 首个合法失败 D2 定义干预资格、记录未触发者。新增物理 probe 对结果的直接作用须由 probe-then-blind 对照单列。
- **研究边界**：预检证实在已有轨迹上具备输入字段和文件，不证明运行时新采集图像的新鲜度、视觉判断效果、对照可辨识性或物理因果收益。Stage R §36 原 Hard STOP、S1 ON_HOLD、P1 L2 未批准的事实不变。
- **重开条件**：用户一次性授予有界的 P1-DEV0 L2 阶段权限（≤24 新 episodes / 8h 墙钟 / 6 GPU·hour 并固定 manifest、四臂和审计界线），或获得新的、足以改变数据有效性判断的证据。

## D-017 · P1-DEV0 有界 L2 阶段批准与不可变随机化先行

- **日期/授权**：2026-10-09。用户上一轮收到“是否批准 P1-DEV0 完整 L2 阶段”的明确问题（≤24 episode、2 worker、8h wall 或 6 GPU·hour）；随即回复“go on”。按该限定问题的上下文将其作为**本阶段范围内的继续许可**记录，详细在 `P1_DEV0_AUTHORIZATION_AND_LOCK.md`，不得用于 Stage R 历史改写或未来其他 L2/L3 活动。
- **状态**：`L2_SCOPE_APPROVED / CODE_PREP_COMMITTED / NO_NEW_SIM_STARTED`。已提交 `p1_dev0_manifest.py`（task3/5/9×seed1001..1008=24，新任务/seed grid、任务×臂各2、SHA256 write-once）、`p1_dev0_policy.py`（四臂逻辑、D0/D1 blind parity、privileged payload fail-close），对应合成测试及 `prepare_p1_dev0.sh`。这些测试及真正 manifest seal **尚需服务器实际运行**。
- **原因/方法选择**：历史 D2 有 206 合格调用、103 失败、合法 low-res RGB+proprio 齐备，但任务 9 的工具失败率远高于 3/5；故必须先随机分配并锁定任务分层，**不因没触发失败 D2 而重新挑 seed**。物理 probe 本身有干预效应；D1 必须遮蔽 probe 后证据，D2/D3 消费的只能是真实传递的合法新观察。
- **风险与阻断**：纯 policy 模块只是**候选决策契约**，不等于 Runtime 已接线；D3 中“visual_frame_available”只是可见性元信息，并未完成视觉物体识别。必须实现且测试 Runtime 的 D1 blind 信息遮蔽、后续动作分支、总成本、固定 env-step horizon audit-only truth、运行预算 watchdog 才能实际启动 ≤24 episode。当前不允许把纯决策模块结果解释为 P1 物理收益。
- **局部例外边界**：Stage R §36 HARD STOP 仅针对**本 P1-DEV0 阶段的新仿真**作有界例外；原 Stage R/S1 不解冻。确认性 HELDOUT、训练、自进化和生产部署未批准。
- **下一动作**：服务器执行一次无 GPU 的 `bash analysis/research_context/prepare_p1_dev0.sh`，返回测试/Gate/manifest SHA；随后按已获批阶段实现并运行隔离 Runtime DEV0，出现信息泄漏/无法保证盲态对照/越预算 STOP，而不是重定义指标挽救。

## D-018 · P1-DEV0 执行收官：工程可行性 GO / 确认性 HOLD

- **日期/来源**：2026-10-09。D-017 批准的有界 L2 阶段内完成全部执行：代码冻结 `62701a0` + runner 修复/分析器/报告本次提交；运行 attempt-2（attempt-1 启动级崩溃零数据，已归档）。
- **状态**：`ENGINEERING_GO / CONFIRMATORY_HOLD / STAGE_CLOSED`。
- **执行账目**：21/24 新 episode（3 个 SKIPPED_GPU_BUDGET：t9_s1006/s1007 D2、t9_s1008 D0）；wall 3.15h（<8h）；GPU 6.17h（>6.0h 名义，launch-gate 语义 + 在飞 episode 完成，越限 0.17h 如实记录）；2 worker；0 hook_error / 0 censored / 0 infra。
- **证据（具体）**：6/21 触发（t9 5/5、t3 1/8、t5 0/8）全部完成 probe→decision→action→audit 事件链；6/6 audit（4 FIXED_HORIZON overshoot 3-23 步 + 2 EPISODE_END）；D1 遮蔽生产验证（retry_step_delta=1 6/6、transcript 零 probe 痕迹）；特权键泄漏 0；事件文件 21/21 在 output_dir 外；policy sha256 六次唯一；probe 5/5 未终结 episode；成本：probe 恒 10 env steps（1.6-1.7s），重试 pick 45-80 步。详见 `P1_DEV0_EXECUTION_REPORT.md`。
- **对照/替代**：D0/D1/D2/D3 四臂中 D2 生产路径零执行（0/4 触发）；全部 6 次决策为 RETRY（5 次 probe 后夹爪仍开 = 物理未抓住，D3 判据不满足 → LEGAL_EVIDENCE_NOT_ENOUGH）。CONTINUE_CAUTION/ABSTAIN 分支仅单测覆盖。
- **不能推出什么**：不能宣称 probe/验证策略对恢复或任务成功的任何效应（n≤3/臂、触发任务高度集中、D2 无数据）；不能引用 audit 交叉表作臂间比较；不能据 t5 0/8 触发断言该任务"不需要验证"（仅本批 seed）。
- **重新开启条件**：正式 P1 新预注册 + 新 L2 授权，且设计须先按任务分层解决触发率/功效；修复 runner 两处已知缺陷（SKIPPED 未逐条落日志、预算 launch-gate 语义）。

## D-019 · DEV0 完成后复审：Pre-delivery Hook、零实际策略分歧和不等时审计

- **日期/证据**：2026-10-09；独立读取研究分支 `6d1060a` 的 `P1_DEV0_EXECUTION_REPORT.md`、Runtime Hook `rpent/utils/p1_dev0.py`、`robots/libero/toolkit.py`、`scripts/p1_dev0_run.py` 与 `scripts/p1_dev0_analyze.py`；目标化审查存 `P1_DEV0_INDEPENDENT_METHOD_AUDIT.md`。本轮尚未直接访问服务器私有事件文件，所有 21/24、6/6、6.17 GPU·h 均为 GitHub 已提交的运行报告所载数据。
- **判定**：`PARTIAL_ENGINEERING_GO / P1_METHOD_GAIN_UNIDENTIFIED / P1_DEV0_CLOSED / POSTHOC_AUDIT_ONLY`。对 D-018 的 `ENGINEERING_GO` 作解释性限定，不改写原历史报告。
- **核心发现 1**：`LiberoToolkit._step` 先完成 pick + `dump_state`，再进入 `maybe_intervene`，最后将视图返回 Planner。此方法是**工具结果计算后、Planner tool-return 交付前**的 Harness Adapter 拦截。D0/D1 的原 false flag 被 Harness 消费且往往只把自动 retry 后视图交给 Planner；不能宣称 Planner 已收到 false 再作策略决策。
- **核心发现 2**：D2 从未发生生产触发，6 次真实决策/动作全部 `RETRY`，缺少任何实际“继续 vs 重试”对照；D3 的 `visual_frame_available` 仅检查文件 SHA/存在性，**未分析图像像素**；其 EEF_z 差值取自维持 EEF 位姿的夹爪 probe 过程，不能当作物体抬升。
- **核心发现 3**：审计 4 次在 H 后的下一技能边界（+3/+8/+18/+23 步），另 2 次为 H 前 `EPISODE_END`（−120/−70 步），不同实际窗口不能直接合并作单一 H 时点成功率。
- **预算与分母**：已报告 GPU 6.17h 大于 6.0h 硬上限，launch-gate 在飞任务导致越限；`scripts/p1_dev0_analyze.py` 将全部无事件文件行归为 `no_events_infra`，会误把 3 个 budget-skipped 计作 infra。修正解释应分配 24 / 运行 21 / 触发 6 / 未触发 15 / 无事件 3（具体原因以 Runner 报告为准），不要把缺失等同于 infra。
- **工程行动**：新增**只读** `scripts/p1_dev0_posthoc_audit.py` 与 synthetic tests；按源数据原样补充严格分母、审计时刻/缺口、预算 gate、合法 probe 观测上的 D2/D3 shadow policy 可达性（不构造未执行动作的任务 outcome，且要求冻结 policy SHA 匹配）。未在服务器运行的新脚本不得声称 PASS。
- **授权决定**：原 DEV0 L2 范围耗尽并 CLOSED；本轮不补跑 3 格、不复活 Stage R，不批准新实验。下一步只有在新的独立 L2 研究包里确定真实可辨识证据、预交付工具决策 boundary、hard-budget watchdog、任务分层与独立未来标签，才可执行新 cohort。
- **来源边界**：复审为源码/已提交报告层级，不能替代读取完整私有轨迹的额外复核；如真实事后工具与报告冲突，提交证据后重新审议。

## D-020 · 5 个真实 probe 观测上的策略影子分歧、原执行报告夹爪状态勘误

- **日期/证据**：2026-10-09，用户在服务器执行 `test_p1_dev0_posthoc_audit.py`（4/4 OK）和第一版 `scripts/p1_dev0_posthoc_audit.py`；返回 `policy_sha_match=true`、`science_gate=HOLD_NO_ARM_ACTION_CONTRAST`。该输出为用户实测服务器的脱敏结构结果；本对话没有直接读取原始 event JSONL。
- **完整分母**：24 manifest，21 个实际有事件的 episode，6 trigger、15 观测内未触发，缺事件三格 `p1dev0_t9_s1006/s1007/s1008`。原 runner 报告判其为预算跳过，单靠事件文件缺失不能推断 infra 或 budget；原审计器保持 `UNDETERMINED_FROM_EVENT_FILE_ALONE` 是正确的。
- **真实结果**：6/6 实际 decisions=RETRY、actions=RETRY。H=200 审计4条在首技能边界 H+{3,23,8,18}；2 条早于 H 共{120,70} 步。GPU `22215.374972105026s`，比 `21600s` 上限多 `615.3749721050262s`，`hard_budget_pass=false`。
- **新增决定性观察**：冻结 Policy SHA 一致，`n_probe_snapshots_checked=5`，影子 `D2:CONTINUE_CAUTION=5/5`、`D3:RETRY=5/5`，**同一合法 probe 后输入策略分歧 5/5**。这是候选策略的**行动规则支持/分歧证据**，不是已实际执行的反事实动作/结局；D2 真实试验臂仍未触发，无法比较 physical outcome。
- **勘误与解释撤回**：旧 `P1_DEV0_EXECUTION_REPORT.md` §5.1 的“5 次 probe 后 `post_gap>=0.06`，物理上确实没抓住”与冻结策略 D2 的`gap<0.06→CONTINUE` 严格不相容，且原报告 t3_s1002 样例已记 `post_gap=0.0025`。**撤回“5 次全开”与“物理上确实没抓住”的结论**；不得把闭合指距代理当真实抓持。对旧执行报告和独立方法审计只追加显式更正，不修改原始 run/event/策略。
- **待验证的机制**：D3 的继续条件还要求 `post_eef_z-pre_eef_z≥0.03`，而物理 probe 定义为保持 EEF 位姿；shadow D3 全 RETRY 可能因这一额外门槛（也可能存在非有限值或合法取值不一致）。已增强**只读**事后审计器，聚合计数 `gap<.06`、EEF dz≥.03、有无 NaN/Inf，以及 `probe.post_legal` 与 `decision.policy_input` 的一致性，配套合成测试。**增强版未在服务器运行**，此处不预断数字。
- **科研含义**：后续需要验证可区分“仅夹爪闭合 vs 真持握”的合法新证据，避免 D2 因主动夹紧形成系统性假继续，也避免 D3 用不相干的 EEF dz 条件形成系统性假重试。正式方法实验只能在独立新 L2 方案、硬预算与未来物理 outcome 下开展；当前 DEV0 CLOSED，不补跑 3 格、不调冻结阈值。
- **验收状态**：`POSTHOC_V1_SERVER_PASS / PHYSICAL_EVIDENCE_INCONSISTENCY_IDENTIFIED / AGGREGATE_DIAGNOSTIC_V2_UNRUN / P1_NEW_L2_HOLD`。

## D-021 · DEV0 5/5 规则分歧机制确证，转向合法视觉证据资格

- **日期/来源**：2026-10-09，用户服务器执行增强版 `p1_dev0_posthoc_audit.py`（4/4 测试通过，冻结 policy 哈希匹配）；独立再查 `p1_dev0_policy.py`、`rpent/utils/p1_dev0.py` 与 `robots/libero/tools.py:dump_state`。
- **状态**：`P1_DEV0_V2_POSTHOC_CONFIRMED / RULE_CONSTRUCT_MISMATCH / VISUAL_PAIR_FEASIBILITY_PENDING / NEXT_L2_HOLD`。
- **直接事实**：五个真实 probe 对应的合法 `post_gripper_gap<0.06` 为 5/5，EEF Δz 数值有效 5/5 但 `Δz>=0.03` 为 0/5；probe→policy `gripper_gap/eef_z` 传值差异0、缺合法 post 记录0。冻结策略上 D2=CONTINUE 5/5、D3=RETRY 5/5，**没有执行 D2 反事实后续动作**。
- **方法判定**：D2 直接从爪口闭合判断“可能继续”，但物理夹爪闭合可以在空夹爪发生；D3 则在维持 EEF 位姿的夹紧 probe 期间要求 EEF 上升3cm，其额外判据不代表目标物体真实抬升且与操作设计不相容。两种 shadow 决策仅说明存在决策分歧，**不证明哪种策略正确或效果更好**。旧报告“5次夹爪全开/确实没抓住”已正式勘误，历史运行数据/原 frozen policy 不动。
- **新证据有效性问题**：历史触发低分辨图像 `policy_image_agentview_low`/ `image_wrist_low` 与新增 probe 图像 `probe_agentview`/`probe_wrist` 可形成候选视觉前后证据；但源码显示 **pre wrist 以 `raw_wrist[::-1]` 保存、post wrist 以未翻转 raw 保存**。未做纵向对齐的简单像素差分会人为引入大面积变化。已新增只读 `scripts/p1_dev0_visual_pair_preflight.py` 和合成测试，先检查完整5个 probe 的视图文件、记录 SHA 和 PNG 几何是否真的可追溯；**工具刚提交，尚未在服务器运行**。
- **后续研究门槛**：只有图像合法性、时间新鲜性和可比相机约定可验证后，才能设计/测试“视觉目标-爪口相对位置或时序一致性”的**离线候选验证器**；需要独立 audit-only 真值评价，但绝不把该真值输入 Runtime/Evolution。视觉差分变化不等于持握。任何新仿真/在线 action 的 P1 阶段须新的有界 L2 预注册与授权。DEV0 因实际 GPU 超额继续 CLOSED，不补旧3格。
- **原因/选项**：转向观察与标签的构念有效性、对齐和价值检验，暂停无监督阈值追调；不将 EEF dz 门槛偷偷改为更易触发条件去复写 DEV0。

## D-022 · 五组旧 DEV0 Probe 图像配对 QA 真实 PASS，单元测试零值键缺陷修补

- **日期/来源**：2026-10-09，用户在服务器分支 `781339b` 运行 `test_p1_dev0_visual_pair_preflight.py` 与 `scripts/p1_dev0_visual_pair_preflight.py` 并回传终端记录。本轮追查 GitHub `scripts/p1_dev0_visual_pair_preflight.py`、测试及私有数据的**脱敏计数**；未直接访问服务器原图像。
- **实测**：真实 Gate `PAIRED_ASSETS_COMPLETE`，事件文件21、未触发15、已触发6、其中未执行 probe1、真实 probe5；5/5 `policy_image_agentview_low→probe_agentview` 和 5/5 `image_wrist_low→probe_wrist` 配对记录路径、SHA256、PNG头尺寸合格，缺失/哈希错误报告为空。每个摄像头前后 SHA256 不同 5/5、相同0。
- **工程例外**：合成回归为 3 项中 2 项 PASS，失败是测试调用 `new_report["counts"]["wrist_verified_pair"]`；在故意篡改文件而 `verified_pair=0` 时，原 Counter→dict 序列化**省略零值键**，所以抛 `KeyError`。这是结果模式稳定性/测试实现问题，**不改变真实数据 Gate**。已单独修复输出统计模式，强制 `*_verified_pair` 等四类预定字段在为零时仍输出0；修复后回归测试**尚未在服务器运行**。冻结实验、数据和 A0/DEV0 策略均未修改。
- **科学裁决**：`VISUAL_PAIR_ASSET_QA_PASS / VISUAL_SEMANTIC_IDENTIFIABILITY_UNTESTED / SYNTHETIC_TEST_FIX_PENDING_RERUN / P1_NEXT_L2_HOLD`。文件字节不同不能证明对象真实移动，更不能证明物体被夹住。Pre wrist 由原始图像上下翻转保存，post wrist 直接保存原始图像，**比较像素前必须统一坐标方向**；现有 QA 仅查 SHA 和 PNG header，未做完整图像解码或识别物体。
- **下一步**：复跑一次无 GPU 的视觉合成测试验证代码修复，不再重复 5/5 已通过的配对统计；研究上如果要继续，应使用这些已有合法 RGB 做独立的对象-爪口可辨识性分析，既不能用模拟器物体世界坐标当在线特征，也不能借此启动新的 rollout 或修改冻结结果。
- **授权**：历史 DEV0 Stage CLOSED；独立未来在线 P1 新实验需要新阶段 L2，Stage R §36 原 Hard STOP/S1 ON_HOLD 继续。

## D-023 · RGB 对照图生成已实测通过，切换到视觉可辨识性离线审阅

- **日期/来源**：2026-10-09，用户在服务器 `03fa204` 对视觉配对+图板两个模块联合执行 6 项合成测试，6/6 全通过（0.607s）；执行 `scripts/p1_dev0_visual_review.py` 报 `PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER`、`n_boards=5`，产物在私有 `artifacts/p1_dev0/visual_review`。
- **已经证明**：5 张 Agentview/Wrist 前后及差分拼图的本地生成流程实际运行；修复后的 zero-counter 测试已通过；Wrist Post 的纵向翻转处理可在合成测试中正确对齐既有源保存约定。既有 Stage R 与 DEV0 原始数据未被重跑或改写。
- **未证明**：未直接查看私有图像内容，没有物体/夹爪语义分割、目标相对夹爪位置标签、持握真值、视觉分类准确率或证据驱动动作的收益；差分图受夹爪自身运动、遮挡影响。
- **下一阶段决策**：不再开展文件级重复审计。增加单个**离线本地 HTML 可辨识性审阅器** `scripts/p1_dev0_visual_annotation.py`（代码与纯合成测试已提交，尚未执行服务器单测）；通过自包含且离线的审阅页检查目标/夹爪是否可见、遮挡程度和主观视觉关系，可以保留 UNKNOWN。仅生成/汇总本地审阅注记；**任何人类视觉标签都不是独立 sim truth**，不进入 Runtime/Evolution。
- **边界**：旧 DEV0 已 CLOSED，不补跑 3 个预算跳过 episode。图像、内嵌图片的本地 HTML 和标注留在 gitignored `artifacts/`，不自动上传 GitHub/外部服务。新仿真或 Runtime 对照仍需独立有界 L2 授权。
- **当前 Gate**：`VISUAL_RGB_BOARD_SERVER_PASS / OBSERVABILITY_REVIEW_PENDING / PHYSICAL_LABEL_UNVALIDATED / L2_HOLD`。

## D-024 · VE-v0.1 视觉证据离线研究完成：stall 三态信号成立，持握检出不可估，最小 L2 HOLD

- **日期/来源**：2026-10-09/10 夜间自主阶段（用户一次性授权的只读离线研究，6-8h）；全部分析基于既有 5 个真实 probe 前后图像 + 21 集 DEV0 合法观测，未跑任何新仿真、未改冻结数据与 Runtime。产出：`P1_VE01_VISUAL_EVIDENCE_REPORT.md`、`analysis/research_context/p1_ve01_evidence.py`（19/19 单测）、`scripts/p1_ve01_legal_extract.py`、`scripts/p1_ve01_run.py`、`scripts/p1_ve01_arms.py`、`scripts/p1_ve01_adversarial.py`（10/10 PASS）。
- **状态**：已确定（离线证据原语层 GO；最小修正 L2 HOLD 待新授权）。
- **决定**：(1) 采纳 **probe 闭合结局三态**（CLOSED_TO_FLOOR / STALLED_ABOVE_FLOOR / AMBIGUOUS）作为接触存在性原语——以 69mm→2.67mm/10 步实测行程能力为对照，7.31→6.96 与 4.53→4.53 停住判为物理阻挡而非控制节奏；(2) 确认 **gap 静态阈值在重叠区原理不可分**（flag=T 1.8–17.6mm vs flag=F 2.2–79.3mm，薄沿持握 1.8mm T ≈ 空闭合 2.2mm F，planner 自述同歧义），D2 的 gap<0.06 在本 5 例输出 5/5 CONTINUE 且恰含 2 个受阻案例=系统性假继续坐实；(3) 视觉的合法增量定位为**图像有效性裁决**（视差/误对齐/过期/复用/缺失，t9_s1004 最大差分 45.8=纯深度视差零信息）+ **接触方位**（腕视世界图近场，t9_s1003 最近表面 0.5mm 落指间投影带中心），不是"看见夹住"；probe 无 lift → 任何模态不得断言持握；(4) 新臂 B1′/B3/B4 状态区分度 2/4/4 vs 冻结规则 1/1/1，且 ADV7 性质（无持握证据永不 CONTINUE）10/10 对抗通过。
- **证据**：报告 Phase 1–5 全表格；`/workspace/yjx/rpent_data/p1_dev0/ve01/{legal_calibration,evidence_claims,arms_comparison,adversarial_results}.json`（私有 artifacts，不入 Git）。
- **对照/替代**：考虑过裸差分幅值判据（t9_s1004 必假阳，弃）、重调 gap 阈值（重叠区原理不可分，弃）、MODEL_VISION 直出标签（不可复现且非真值，降级为外部主观参考字段）。
- **不能推出什么**：持握检出率/准确率（5 例 0 正例、无 probe 时刻物理真值）；"修正 L2 可改善结局"（Hypothesis）；audit 真值是 retry 结局不构成 probe 状态标签；主观视觉与几何一致(n=5)不等于效度。
- **重新开启条件**：用户授权最小修正 L2 新预注册——probe 改"闭合+受控提升 2-3cm"使 lift 判据可用、分层采样含真实持握正例（t9/t3/t5 配额）、hi-res 触发时刻覆盖验证、两分支可达的 pre-delivery 消费者接线；旧 D2/D3 冻结规则不得复活。

## D-025 · VE-v0.1 独立复审：把闭合停住/近场深度归回候选信号，新增 fail-closed 离线审计

- **日期/来源**：2026-10-10，独立读取夜间提交 `32af61b` 的研究报告与 `p1_ve01_evidence.py`、`p1_ve01_legal_extract.py`、`p1_ve01_run.py`、`p1_ve01_arms.py`、`p1_ve01_adversarial.py`。未登录用户服务器读取私有 5 张图和私有 VE01 JSON；19/19、10/10 是仓库执行报告记载而非本轮独立实测。
- **保留**：有五个 probe 合法观测样本与多模态离线结构化证据；原 D2 5/5 CONTINUE vs D3 5/5 RETRY 的策略差异已另经用户服务器后验核对；新原型将夹爪开度轨迹和几何质量纳入解释性状态分箱，可继续作为 L1 探索。
- **必要降级**：历史三例 post_gap 近最小值、两例较大开度/变化小，仅支持观测到“不同闭合响应模式”，**并未物理证明**两例一定受到目标接触或碰撞（servo/机械限位/控制/传感替代解释未排除）；最近 EEF 0.5mm 的腕视世界坐标可能来自机器人自身、桌面或目标，**无 target-instance/self mask**，不能赋予“目标在指间”或“实际接触”的标签；全画面变化并不能唯一归因为纯深度视差。
- **对照局限**：B3 自称 visual-only，然而使用 EEF proprio 与腕视深度图距离，实际上是几何+proprio；ADV7 测得零 CONTINUE 是 B1′/B3/B4 **代码写死**不输出 CONTINUE 的性质，不是可验证的低误继续率；六臂“独特状态种类”依赖人工状态码，且与门槛配置同源，不能当独立性能结果。Planner think 正则提取的 success/flag 也不能称为独立真实持握标签。
- **工程缺口**：原 `arm_b3/arm_b4` 缺 `claim.validity/freshness` Gate；可能在过期、特权污染、缺图输入上仍读取原有字段，或在 `visual_camera_motion=None` 时崩溃。新增独立 `scripts/p1_ve01_safe_arms.py` (v0.1.1) 和 `test_p1_ve01_safe_arms.py`，不改原历史对照：invalid/stale/缺值/原 gap 类别与值冲突时返回 `RETRY+ABSTAIN`；其他时候仅输出 `GAP_PLATEAU_CAUSE_UNKNOWN` / `SURFACE_NEAR_EEF_IDENTITY_UNKNOWN` 等明确非真值状态。**尚未在服务器跑新测试与私有五例**。
- **决策**：将“已确认两个阻挡”“t9_s1003 已有目标接触”“系统性假继续已坐实”等 VE-v0.1 报告主张降级为探索性风险，原报告保留可追溯且以 `P1_VE01_INDEPENDENT_REVIEW.md` 为解释性勘误。只有有独立 mask/持握真值/时间点对齐且不泄漏的方法，才能恢复相关强主张；新 L2 无授权，所有在线实验保持 HOLD。
- **下一动作**：服务器只读运行 `test_p1_ve01_safe_arms.py`，再对已有 `evidence_claims.json` 执行 `p1_ve01_safe_arms.py`（新输出单独在私有 VE01 数据目录），检查数据兼容与五案例保守输出；若有矛盾 STOP 并定位，绝不修改旧冻结结果。

## D-026 · VE01.1 服务器10/10通过；物理标签改由探测时点独立对齐审查

- **日期/来源**：2026-10-10；用户服务器在研究分支执行 `python -m unittest discover -p test_p1_ve01_safe_arms.py` 与 `python scripts/p1_ve01_safe_arms.py`。测试真实回传 10/10 OK，既有五个 probe 的离线结果 `eligible=5`，`RETRY=3`、`RETRY+ESCALATE=2`。
- **三类证据边界**：`NEAR_MIN_GAP_OBJECT_PRESENCE_UNKNOWN=3`、`GAP_PLATEAU_CAUSE_UNKNOWN=2`；4 个最近表面距离属于通常范围、1 个接近 EEF 但表面身份未知。 `claim_holding_positive=0`、`independently_verified_object_contact=0`、`audit_truth_used=false` **不是五个已证物理失败，亦非零假阳率**；只是持握/接触没有得到独立证据。
- **关键源码检查**：`rpent/utils/p1_dev0.py:_run_probe` 在夹爪10步结束后只读白名单 proprio + RGB，**没有在 probe 时间点记录目标归属/接触物理真值**；`_take_audit` 在触发后的 H=200 首个技能边界或提前终局记录 `check_success` 与 `sim_measurement`，其时点**晚于 probe**且后续可能已重试。旧 DEV0 的四个 H 后边界+两个提前结束之间也不同时间窗，不能合并成 probe-time held labels。
- **动作**：新增 `scripts/p1_ve01_label_contract_audit.py` 与独立合成测试，只读检查已封版 manifest 24 个分配项、21 个事件文件、6 个触发、5 个 probe 中合法事件时间、后续 H 任务结果的原始可得性。其输出中只允许 **probe_time_held/contact=UNLABELLED**，显示未来任务成功字段是否存在，但不回显其数值、物体坐标或私有轨迹；不会替现有实验生成伪真值。**新脚本本轮已提交，服务器未实测**。
- **方法下一步**：真实目标持握评估的合同必须包含“probe 结束同物理时刻、目标实例标识、机器人自身隔离、物体与爪指接触/相对刚性运动、后续固定窗”，且在线证据路径与独立 audit 不能相互混用。只有来源核实和新受限预注册实验经授权后才可构建 confirmatory outcome；不补跑旧 DEV0、无新仿真授权。
- **裁决**：`VE011_SERVER_PASS / OFFLINE_EVIDENCE_VALIDATED_NOT_PHYSICAL_CONTACT / LABEL_TIME_AUDIT_UNRUN / NEXT_L2_HOLD`。

## D-027 · Label-time 服务器 3/3 PASS；收缩零标签结论并修复固定零计数漏洞

- **来源**：2026-10-10 用户服务器对 `p1_ve01_label_contract_audit.py` 首版执行 3/3 单测 OK，24 manifest/21 事件/6 trigger/5 probe；5/5 audit 严格晚于 probe、未来任务成功审核6/6（H 后边界4，提前终局2）；数据内时序完整性问题0。
- **复审发现**：首版 `with_probe_time_contact_reference=0` / `with_probe_time_held_reference=0` 由**常量赋值**产生，并未主动排查真实 Probe JSONL 的新增字段或其他历史来源；该 Gate 最多从源代码预测可能缺标签，**不能用其作为所有潜在物理标签不存在的实证证明**。
- **修正代码**：`scripts/p1_ve01_label_contract_audit.py` 加入 `probe_schema_unexpected_paths`：从真实 5 个 Probe 事件仅读取字段名，对照已有 Runtime `_run_probe` 的顶层 + `probe_args/result/post_legal/post_frames` 嵌套白名单；遇陌生 contact/held 类字段、结构变化或不能识别的新字段，记录异常数量并转 `HOLD_EVENT_INTEGRITY_OR_PROBE_MISSING`，不输出字段值或图像内容。通过时新版 Gate 改为 `NO_EXPLICIT_PROBE_LABEL_IN_RECOGNIZED_EVENT_SCHEMA`，保留 scope：**只覆盖这组事件 JSONL，不覆盖其他私有仓储数据或 simulator runtime**。
- **新增对抗性测试**：向 Probe 顶层注入 `contact_at_probe`、向 `post_legal` 注入 `object_contact`，新审计应拒绝无标签 Gate；使用 Runtime 接近的完整 Probe fixture 防止合成空壳通过。代码已提交，**新版本服务器单测及真实字段扫描尚未运行**。
- **科研边界**：五个已有 Probe 只有 RGB+合法 proprio 的事实仍与 Runtime 源码一致；此事件合同中后续 `check_success` 无法变成 probe-time target-contact/held 标签。下一正式 L2 如需正例必须获得新独立授权与可验证的物理标签采集合同，不补跑旧 DEV0。
- **判定**：`LABEL_TIME_V1_REPORTED_PASS / NO_LABEL_SCOPE_DOWNGRADED / V2_PROBE_SCHEMA_SCAN_UNRUN / NO_NEW_L2`。

## D-028 · v2 Label-time 真实5/5 PASS，L1 停止点与下一 L2 合同

- **日期/来源**：2026-10-10，用户服务器运行新版 `test_p1_ve01_label_contract_audit.py` 与既有 DEV0 JSONL 实测：5/5 单元测试 OK；`NO_EXPLICIT_PROBE_LABEL_IN_RECOGNIZED_EVENT_SCHEMA`；5 个 Probe 字段结构全部匹配 Runtime，unreviewed=0，integrity violations=0；四个 H 后审计+两个提前终局，五次 Probe 均在各自未来审计之前。
- **正确的研究解释**：**只在五个已检查的 Probe 事件 JSONL 结构中**没有明示同刻 `target_contact/target_held` 真值。不能推断私有目录其他历史文件/模拟器可重建数据没有相关信号，不能把后续 `check_success`/Planner flag 当 probe-time 标签；`0 reference` 不是 `0 contact` 或模型 `0 error`。
- **增量源码事实**：`robots/libero/tools.py:dump_state` 的 Wrist low/hi world map 与 images 基于 Toolkit step `NN`，`segment` 的 mask 仅临时用于落 `mask_shape/box/world_xyz/overlay/source_step` 等，不保留可直接分离目标/机器人自身的 raw binary mask。旧 `rpent/utils/p1_dev0.py:_run_probe` 绕 Toolkit step 直接调 `set_gripper`，其新增输出只有后置 RGB 和白名单 proprio；旧 pre-trigger world 和 segment 无法视为 probe-end 同步物理参考。文件源码能限定数据合同，但本轮未实际扫描其他私有 sidecar 文件存在性。
- **交付**：`P1_NEXT_L2_LABEL_AND_CONTRAST_GATE.md`，对下一阶段提出明确 probe-end 同物理步号独立双指/目标身份与支撑物审计，区分接触 vs lift 后持续持握，保留 UNKNOWN；采用相同物理 Probe 的 blind/proprio/visual 信息对照、单独评估 lift 机械效果、精确 H 评价及在飞工作预算预留。**设计草案不是资源或 Runtime 授权，不是对未来收益的已验证论断。**
- **STOP/GO**：合法 RGB/proprio 证据原型与 schema/时序分析层 GO；继续用这五例给出 held/contact precision、已证物理接触位置、证据收益等结论 **STOP**（缺独立标签与执行分支效果）；新 L2 物理实验 **HOLD**，需要新有界授权与预注册封版。停止继续重复同类 QA。

## 新决策追加模板

```markdown
## D-XXX · 标题
- 日期/来源：
- 状态：已确定 | 研究候选 | HOLD | STOP
- 决定：
- 证据（具体报告/代码/实验结果）：
- 对照/替代：
- 不能推出什么：
- 重新开启条件：
```
