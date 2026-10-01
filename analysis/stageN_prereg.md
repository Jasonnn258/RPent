# Stage N 预注册 — Causal Control-Dependency Qualification(N0 测量资格 + N1 条件验证)

冻结:2026-10-01 | 执行前 commit | N0 纯离线零新 rollout(复用 Stage L/M 池与基建);
N1 仅 N0 measurement gate PASS 后执行。详细判据见 `analysis/stageN0_analyzer_spec.md`
(与本文件同 commit 冻结,同为预注册组成部分)。

## §0 冻结的既有结论(不可翻案)

- Stage H:soft graph NOT SUPPORTED;graph-menu violation 90%;advice≠policy。
- Stage I0:本地低延迟 LLM router 资格 FAIL。
- Stage J:snapshot/restore 可靠;Pi0.5 技能随机 → 单 rollout 反事实不可判。
- Stage K:WORLD MODEL NOT JUSTIFIED;结构化物理态 > 视觉 latent。
- Stage L:GRAPH EVOLUTION NOT SUPPORTED(两轮 5 候选全 REJECT、终图≡冻结图);
  短 recovery edge 无法承载绝大部分历史成功恢复。
- **Stage M:Recovery abstraction measurement INVALID**(盲审 agreement label/FID 双
  87.9% < 90% 门槛)→ STOP,M1 未运行。机器数字(OPTION≈83%/MACRO≈16%/
  EDGE≈0.6%,187 段)只是无效测量的上下文记录。**禁止将 Stage M 重新解释为
  PASS,禁止把 83% 当作结论使用。**

### Stage M 的机制发现(Stage N 的直接动机)

4 个分歧全部同向(人工 OPTION vs 机械 MACRO),共同模式:
`observe scene → same-family movement → reuse old grasp prompt/recipe`。
旧 analyzer 漏判根因:A 要求观察夹在**不同 action family**之间;E 要求后续
grasp 使用**新 prompt**。但人工判断:若观察显示不同 physical situation,后续
recipe 不会被执行 → 观察**实际 gate 了下游控制**。

**新核心定义(Stage N 全部推理的公理)**:

> OPTION 不由 trajectory shape 定义。OPTION 由
> **NEW INFORMATION → DOWNSTREAM CONTROL DEPENDENCY** 定义。

## §1 研究问题

- **N0**:对具身恢复轨迹中新获得的物理信息的控制依赖(control dependence),
  能否从 recovery trace 可靠测量?
- **N1**(仅 N0 PASS):允许中间物理信息**因果地改变**下游恢复控制
  (closed-loop option),相对 otherwise-matched 的固定宏,是否真正提高
  真实物理恢复?

## §2 核心术语(逐中间 information event 三态)

对窗口 [t0, tR] 内每个中间 information event(OBSERVE / GROUNDING /
VERIFIER / STATE_UPDATE,事件本体见 spec §2)判定:

- **CONTROL_DEPENDENT**:当且仅当存在证据表明 t0 后获得的新 observable
  information 改变了至少一项:continue 与否 / action family / target
  identity / target reference / target pose / action parameters / waypoint /
  retry 决策 / fallback 决策 / termination 决策。
  **不要求 action family 改变;不要求 prompt 字符串改变。**
  observation 仅作为 EXECUTION GATE(observe → condition valid → 执行同一旧
  recipe)同样属于 control dependence,只要"condition 不成立则 recipe 不会
  执行"有证据支持。
- **CONTROL_INDEPENDENT**:仅当有足够证据证明:观察之前后续 action sequence
  与关键参数**已经固定**,且 observation 的取值不会改变
  continue/action/parameter/terminate。
- **UNRESOLVED**:只知道"看过之后继续执行"而无法证明观察是否影响后续
  控制 → 必须判 UNRESOLVED。**禁止猜测。**

## §3 反事实标注问题(人工盲审统一问法)

不再问"这是不是 Option"。逐 information event 问:

> "If the newly acquired observation at this point had been **different but
> still physically plausible**, would the downstream recovery control
> (action, parameter, continuation, retry, fallback, or termination) have
> changed?"

答案三选一:`YES_DEPENDENT` / `NO_INDEPENDENT` / `INSUFFICIENT_EVIDENCE`,
分别映射 CONTROL_DEPENDENT / CONTROL_INDEPENDENT / UNRESOLVED。

## §4 段级聚合(冻结)

analyzer v2 的主输出是**事件级**标签;盲审与门使用**段级**聚合:

1. 段内存在 ≥1 个 DEPENDENT 事件 → 段 = DEPENDENT;
2. 否则存在 ≥1 个 UNRESOLVED 事件 → 段 = UNRESOLVED;
3. 否则(全部 INDEPENDENT,或**窗口内零 information event**)→ 段 =
   INDEPENDENT(零事件 = 序列由 t0 信息态完全决定,vacuously independent)。

## §5 Analyzer v2(确定性,零 LLM primary labeling)

- 判据族(操作化细节全部冻结于 `stageN0_analyzer_spec.md`):
  **A′** observation-gated execution;**B′** target/pose dependency;
  **C′** parameter dependency;**D′** verification dependency;
  **E′** grounding-reference dependency;**F′** explicit branch dependency。
- **证据纪律**:禁止因 "OBSERVE followed by ACTION" 自动判 DEPENDENT。
  必须存在数据证据:parameter source link / grounding update / branch
  condition / verifier outcome / planner statement with explicit conditional
  relation / structured state transition followed by conditional action /
  paired trace evidence。证据不足 → UNRESOLVED。
- **开发纪律(§6)**:开发仅限 DEVELOPMENT 材料;最终测量门**禁止**使用
  旧 33 audit samples(它们只允许用于失败模式发现)。

## §6 DEVELOPMENT 子集与污染控制

- 允许人工查看:Stage M 旧 33 audit 样本 + 3 条 SPOT_CHECKED 段(两者
  本就被排除出新抽样框)+ 全池**聚合计数**。
- 开发中任何对其他段的**逐段人工阅读**必须登记进
  `analysis/stageN0_dev_viewed.csv`(segment_id + 查看原因),登记段全部
  排除出最终 qualification 抽样框;目标 ≤10 条,越少越好。
- 禁止"看新样本个案 → 回去改判据 → 重测"循环:v2 代码在抽样**前**冻结
  commit;冻结后任何判据修改都记为偏离并使本轮测量作废。

## §7 Natural Contrast Pairs(仅开发/机制分析)

在 DEVELOPMENT 材料中寻找:相同/近似 recovery recipe 但 information history
不同的案例(如 Case A:no observation → recipe X;Case B:observe →
condition check → recipe X)。分析:相同 action sequence 是否具有不同
control dependency(预期:B 的 A′ 判 DEPENDENT,A 判 INDEPENDENT)。
**被人工查看过的 contrast pair 段不得进入最终 qualification audit。**

## §8 Information Provenance Instrumentation(仅为 N1,不改历史)

为 N1 在 runtime 增加结构化日志字段(实现落在 N1 准备期,历史标签零修改):

```
information_event_id
information_type: observation | grounding | verifier | state_update
information_value_summary
decision_id
decision_depends_on: [information_event_id]
branch_condition / branch_result
action_parameter_sources
termination_reason
```

N1 的 dependency measurement 优先使用显式 provenance,而非事后从自然语言
transcript 猜测。N0 若 FAIL,这也是唯一被允许的 future 路线(§13)。

## §9 新 qualification 抽样(冻结)

- **资格框**:Stage M analyzer 的 187 段中 transcript 可用(RESOLVED 165)段,
  减去 旧 33 audit 样本、3 条 SPOT_CHECKED、§6 登记的 dev-viewed 段;
- **N_audit = 45**(推荐区间 40–50 的中值;冻结);
- 抽样前分层:**failure family × machine(v2) predicted class ×
  primitive_count 三分位**;配额:INDEPENDENT 类 min(12, 池内数)、
  UNRESOLVED 类 min(8, 池内数),余量按族池比例分配给 DEPENDENT 层;
  层内按 length 三分位均衡抽取;**seed = 20261002**(任意但区别于 M);
  目的:避免全抽 Option-like easy case,测量门对机器最难的方向 adversarial;
- 产物 `analysis/stageN0_audit_manifest.csv`(audit_id → segment_id →
  family/machine_class/length_tercile),**manifest SHA256 在人工 audit 前
  冻结并 commit**;分配算法逐字冻结于 spec §9。

## §10 盲审协议(结构盲)

- 可见:recovery trace(states.json 窗口逐步 command+result)、structured
  state/events、action parameters、observation/grounding/verifier records、
  t0/tR eef 状态;images 仅当 provenance 需要(历史日志未存帧 → 实际不可用,
  记为已知局限);
- **禁见**:analyzer v2 标签/事件标注、aggregate dependency rate、
  tR 之后的集结局、Stage N 任何聚合结果;
- 作答(逐 audit_id 一行,先落盘 `analysis/stageN0_manual_audit.csv`
  后比对):`label ∈ {DEPENDENT, INDEPENDENT, UNRESOLVED}` +
  `evidence_event`(窗口内定位:step/turn 引用)+
  `dependency_type ∈ {observation_gate, target_grounding, pose_update,
  parameter_update, verifier_branch, retry_fallback, termination, none}`。

## §11 N0 Primary Gate(冻结数字)

在 **human-resolved**(人工 DEPENDENT ∨ INDEPENDENT)标签上:

1. **overall agreement ≥ 90%**(简单一致率,3×3 对角);
2. **safety gate:false_independent_rate ≤ 5%**,其中
   `false_independent_rate = #(human DEPENDENT ∧ machine INDEPENDENT) /
   #(human DEPENDENT)`;
3. 可评估性前提:human-resolved ≥ 30(否则样本不足,**MEASUREMENT NOT
   QUALIFIED**,不得用未达样本的门数字裁 PASS);

同时报告 `false_dependent_rate`(human INDEPENDENT ∧ machine DEPENDENT /
human INDEPENDENT)与机器/人工 unresolved_rate。

判定:

- overall ≥90% ∧ false_independent ≤5% → **MEASUREMENT QUALIFIED → 开启 N1**;
- overall ≥90% 但 false_independent >5% → **MEASUREMENT NOT QUALIFIED**
  (把真实 control-dependent recovery 错压成 Macro 是当前最大测量风险);
- overall <90% → **MEASUREMENT NOT QUALIFIED**。

任一 NOT QUALIFIED → **Stage N STOP**,报告
**TRAJECTORY-ONLY CONTROL DEPENDENCY CANNOT YET BE MEASURED RELIABLY**;
禁止增加 heuristic 后重测同一 audit;未来只允许 prospective explicit
information provenance logging 重定义测量。不做任何"修判据→重审"循环。

## §12 N0 科学指标(仅 PASS 后才允许计算/引用)

用 analyzer v2 在新样本 + 历史池上重新估计:`control_dependency_rate` /
`future_information_dependency` / dependency type breakdown(observation
gate、target grounding、pose update、parameter update、verifier branch、
retry/fallback、termination)/ failure family breakdown。
**旧 Stage M 的 83% 不得直接替换成新结论**;两套数字不可混引。

## §13-19 N1(仅 N0 PASS;设计冻结于 PASS 后、运行前)

- **§13 操纵对象**:不再研究"Option 像不像 Option",直接操纵**是否允许
  新 physical information 改变下游控制**。选少量有明确 control-dependency
  evidence 的 failure families / recovery procedures,每 family 1–2 个;
- **§14 matched 三要素**:每 procedure 构造 M(FIXED_MACRO)与
  O(CLOSED_LOOP_OPTION),保持相同:primitive set / Pi0.5 skill / max action
  count / wall-time budget / retry budget / 初始快照 / perception capability。
  唯一核心差异:M 在 t0 冻结 sequence+关键参数,中间 observation/verification
  **不得**改变下游控制;O 的中间 observation/grounding/verifier 可更新
  information state 并改变 action/parameter/continue/retry/fallback/
  termination。**O vs M 只差中间反馈的因果效力,不差预算**;
- **§15 O 的显式 information state**:target_visible / target_grounded /
  target_pose_valid / support_relation / latest_action_result /
  latest_verifier_result / retry_count;每次下游控制改变必须记录
  which information event caused which decision change(§8 provenance);
- **§16 快照与随机性**:全新 held-out failure snapshots(不得用 Option
  编译/设计期间看过的),task × seed 隔离;Pi0.5 随机性按 Stage J 经验用
  预注册 repeated rollouts(K 由独立 calibration 集冻结,候选 K0 六集,
  不得依 TEST 调 K);sampling seed 可控则 M/O 用 common seed set;
  禁止修改 Pi0.5 semantics;
- **§17 指标**:Primary = validated_recovery_rate / harm_rate;
  Secondary = no_effect / unresolved / wall time / primitive count;
  Mechanism = dependency_realization_rate(O rollout 中 ≥1 次 information
  event 实际改变下游控制的比例)/ feedback_rescue_rate(matched M 未恢复
  而 O 因 information-dependent control change 恢复)/ feedback_harm_rate
  (O 因错误 information-dependent branching 比 M 更差);
- **§18 mechanism split(冻结)**:O rollout 分 DEPENDENCY_REALIZED /
  NOT_REALIZED 分别计算 O−M delta;**该分析在 prereg 冻结**;
- **§19 N1 Gate(冻结数字)**:
  `CLOSED-LOOP FEEDBACK SUPPORTED` ⇔ validated_recovery(O)−(M) ≥ 15pp
  ∧ harm(O)−harm(M) ≤ 3pp ∧ feedback_rescue_rate ≥ 10% ∧
  dependency_realization_rate ≥ 20% ∧
  **delta_realized ≥ delta_not_realized + 10pp**(操作化"方向明显高于")。
  若 O>M 但 realization 很低 → 只能写
  `OPTION IMPLEMENTATION OUTPERFORMS MACRO, MECHANISM INCONCLUSIVE`;
  若 O≈M → `CLOSED-LOOP FEEDBACK NOT SUPPORTED`;
- **§20 Graph implication**:仅 N1 PASS 才允许报告
  `OPTION-LEVEL GRAPH ABSTRACTION IS EMPIRICALLY JUSTIFIED`
  (Graph edge 应表示 initiation condition + internal information state +
  closed-loop policy + termination condition,而非固定动作序列)。
  **即使如此 Stage N 仍 STOP。**

## §21 Hard STOP

Stage N 完成后 STOP。禁止自动:full-episode Option Graph、Graph evolution、
LLM Router、World Model、perception replacement、SFT、OPD、RL。
若 N0 再次 FAIL:停止用 retrospective trajectory heuristics 判断
Option/Macro;下一步只能通过 prospective explicit dependency
instrumentation 重新定义研究测量。

## §22 工件

- N0:`stageN0_analyzer_spec.md` / `stageN0_audit_manifest.csv` /
  `stageN0_manual_audit.csv` / `stageN0_measurement_results.md` /
  `stageN0_decision.md`(/ `stageN0_dev_viewed.csv` / `stageN0_information_
events.jsonl` / `stageN0_control_labels.csv` / `stageN0_audit_dossiers/`);
- N1(条件):`resources/libero/options_stageN.yaml` / `stageN1_option_spec.md` /
  `stageN1_split_manifest.csv` / `stageN1_rollouts.csv` /
  `stageN1_information_provenance.jsonl` / `stageN1_results.md`;
- 终:`STAGE_N_FINAL_REPORT.md`。

## §23 已知局限(冻结时点,计为偏离记录起点)

1. 历史日志未存图像帧 → 盲审与 analyzer 均只有文本记录(read_image 的
   tool_result 文本 + planner 表述);§3 反事实问题在"图像内容"维度依赖
   planner 事后表述,记为局限;
2. states.json 无每步物体位姿(Stage M §17 同款)→ B′ 位姿数值链接只能
   用 grounding 输出 ↔ action 参数,不能用真值物体位姿核验;
3. planner conditional statement 检测是文本模式匹配,存在漏检(→
   UNRESOLVED,方向保守)与误检(由开发期负例控制)两类风险;
4. dev-viewed 排除会使资格框略缩(目标 ≤10 段);
5. N=45 为推荐区间中值,统计功效以 §11 的 30 resolved 前提为界;
6. **未覆盖信道(开发期发现)**:PHYSICAL_ACTION result 中的 eef 位置状态
   (尤其 rotate_wrist,无 VERIFIER 事件)被 planner 用于重算 waypoint 的
   信道不在 §2 事件本体内;观察到 1 例(dev-viewed 排除)人工判 D、机器判 I。
   详见 spec 附录 A.6。

## 偏离记录(运行后追加)

1. **判据文本族语言**:spec §4 A′/F′ 示例正则为中文(G1–G4 等);实现发现
   planner 推理语言为英文,故冻结常量区采用英文正则族(RE_ASSERT/RE_COND/
   RE_DECIDE/RE_PURPOSE/RE_VC_A/B 等,中文词保底)。判据语义不变,
   词面按数据实际语言重写。开发校准:旧 33 混淆 33/33。
2. **VERIFIER 资格测试(spec §2/§5 细化)**:正结果须同句"验证量断言 ∧
   配对条件"才具信息资格,否则标 NONINFORMATIVE(不参与聚合);
   libero_terminated 不变复读不构成事件;EC5 收紧到 OBSERVE/GROUNDING。
   全部成文于 spec 附录 A,与 v2 代码同 commit 冻结(先于抽样)。
3. **dev_viewed 登记 n=7**(4 machine-I 方向校验 + 3 machine-D 火灾语义
   校验;≤10 上限内;`stageN0_dev_viewed.csv`)。后果:machine-INDEPENDENT
   资格池 5 → 约 1 条,抽样 q_I≈1,false_independent 门功效受限(门本身
   已受 97%-D 输出分布限制)。
4. **输出 schema**:jsonl 事件字段以实现为准(比 §6 更完整:input/
   usable_fields/outcome/evidence 等;args_summary/result_summary 由其承担);
   CSV 含 spec §6 全部列(machine_class=segment_label 别名,unknown_rate=
   n_unresolved/n_information_events)。
5. **eligible∩INDEPENDENT = 0 → q_I=0,audit 45/45 machine-DEPENDENT**
   (2026-10-01 抽样时发现):机器 I 池共 5 条 = 2 条 M 期 SPOT_CHECKED +
   1 条旧 33 + 2 条本次开发抽查(§6 登记排除)——全部被排除,非抽样选择。
   后果:盲审样本中机器 I 为 0,**false_independent 分子结构性为 0,该安全
   门轴在正式 audit 中空转**;测量资格判定实际由 overall agreement 与
   false_dependent 方向承载。I 方向的全部既有证据(仅上下文,非门输入):
   5 条机器 I 已全部在开发期被人工检视——4 条判 I 一致(其中旧 33 的 1 条
   对齐 M 盲审人工标签)、1 条存疑(rotate_wrist 位置信道,局限 #6)。
   manifest 首行 sha256 只覆盖注释行以下字节(自引用无解,采用此约定)。
