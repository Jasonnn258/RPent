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
