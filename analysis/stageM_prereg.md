# Stage M 预注册 — Recovery Abstraction Study(M0 审计 + M1 条件验证)

冻结:2026-10-01 | 执行前 commit | split/provenance 全程只读复用,
M0 零新 rollout(纯离线日志分析)。

## §0 冻结的既有结论(不可翻案)

Stage H:soft graph NOT SUPPORTED、graph-menu violation 90%、advice≠policy。
Stage I0:4B/9B router 资格 FAIL(fast=menu-position strategy,thinking 延迟
不可接受)。Stage J0:snapshot/restore 可靠、Pi0.5 技能随机、单 rollout
反事实不成立。Stage K:WM NOT JUSTIFIED、结构化物理态>视觉 latent、
候选空间无有效 ranking 结构。Stage L:GRAPH EVOLUTION NOT SUPPORTED
(两轮 5 候选全 REJECT、终图≡冻结图)。

**Stage L 机制发现保留**:(1) FG 失败态 task-language SAM3 grounding
0.009–0.059 < 0.2(恢复阶段目标 observability 不足);(2) RPS 物体当前
位置与冻结语言 reference 脱节;(3) ~95% 历史成功恢复 = planner 多步
闭环策略、收益后置、短边不可承载。**Stage L ≠ "Graph 无效"**;Stage M
的问题:short executable edge 是否是错误的可复用控制抽象。

## §1 研究问题与禁区

Q1 成功恢复的最小可复用单位:short edge / fixed open-loop macro /
closed-loop option?Q2 若需 option,必要的是 longer horizon 还是
intermediate observation/grounding/verification/branching?Q3 edge→option
升级是否真正提高物理 recovery?

禁止:new LLM router、World Model、新视觉编码器、SAM3 训练、Pi0.5
微调、SFT、OPD、RL、Graph 自进化、自动候选生成、新 failure family、
full-episode SR campaign。Stage M 完成后必须 STOP。

## §2 M0 数据池(冻结)

- 池 = `analysis/stageL_pool_inventory.jsonl` 覆盖的全部 episode
  (logs/ovpm_exp,696 行,三个年代 schema 逐字段一致,Stage L §0 审计)
  **逐 episode 重跑 `replay_fires` + 首验证**(与 Stage L §4 挖矿同一
  代码路径;L 时刻意只对 K 侧计算过 first_validating,其余未看)。
- **排除**:`stageL_split_manifest.csv` 中 role=L_HELDOUT_TEST 的 24 集
  (保持原封,为 M1 TEST 候选)。
- 纳入单元 = fire 行:genuine failure(t0)+ 后续出现 failure-specific
  验证(tR,§4)。**不使用** post_intervention_progress@3。
- 前提字段(2026-10-01 审计核验):states.json 每步 command+result
  (success/peak_lift_m/final_gripper_opening/min_gripper_opening/
  chunks_used/final_dist_m)+ state(eef/quat/gripper/object_names,
  **无每步物体位姿**)+ elapsed_s + libero_terminated;transcript_*.json
  含 planner assistant turns + tool_use/tool_result(687/696 集可用,
  缺失者该 fire 行标 UNRESOLVED-transcript,单列不入比率);robot
  tool_use ↔ command steps 顺序对齐(三个年代抽查全对齐)。
- 契约可评估性(离线):采用 **H 冻结 fire_validated**(逐 node:
  FG=pi0_pick success∧peak_lift≥0.005;MOVE_STALL=move_to/move_pose
  final_dist<MOVE_OK;CONTACT_STALL=pi0_doubled success∨pick-lift;
  RPS=pi0_pick lift;全部 ∨ 集终止成功)。K/L 的 d_ooi_z 类分支需
  每步物体位姿,离线不可评 —— 记为已知局限(§17)。

## §3 事件本体(确定性映射,零 LLM)

对每条 fire 的窗口 [t0, tR](§4)从 transcript + steps 映射:

| 事件 | 确定性规则 |
|---|---|
| OBSERVE | read_image / view_driver_state 工具调用 |
| GROUND_UPDATE | back_project(或 segment)工具调用且 result 含 world_xyz |
| PHYSICAL_ACTION | 机器人原语命令:move_to/move_pose/rotate_wrist/set_gripper/pi0_pick/pi0_doubled/release |
| VERIFY | 窗口内技能/移动完成时可验证结果到达事件(pi0_pick/pi0_doubled 的 success+lift+grip;move_to 的 final_dist;libero_terminated) |
| BRANCH | 带 §5 强条件证据标记(见 A–D),空证据不发 BRANCH |
| REPLAN | 窗口内发出 ≥1 机器人命令的 assistant turn |
| TERMINATE_SUCCESS / TERMINATE_FAILURE | 集终止(成功/失败) |
| UNKNOWN | 需要的字段缺失/无法对齐的事件(单列,不参与比率) |

禁止由最终成功反推中间事件类型(所有映射只用事件当时可见的
调用+结果字段)。

## §4 恢复前缀与统计量

- t0 = replay_fires 的 fire step;[t0+1 … tR] 为研究区间;
- tR = t0 后首个满足 fire_validated(node, ·) 的命令步(与 Stage L
  挖矿同码同参);
- 统计:primitive_count / planner_turn_count(窗口内 REPLAN 数)/
  wall time(elapsed_s[tR]−elapsed_s[t0];跨集负载差异只作分布参考)/
  OBSERVE / GROUND_UPDATE / VERIFY / BRANCH / REPLAN 计数;
- 每个后续 action 的参数是否依赖 t0 后新信息(§6)。

## §5 抽象标签(确定性判据)

先判强条件证据(A–D;**仅"调用过感知"不算,必须有未来信息依赖**):

- **A(family 切换×新观察)**:存在相邻 PHYSICAL_ACTION 对
  (p_{i−1}, p_i) 使 family(p_i) ≠ family(p_{i−1}),且两者**发射之间**
  (transcript 消息序)存在 ≥1 个 OBSERVE/GROUND_UPDATE 事件;
- **B(grounding→参数)**:存在 t0 后 GROUND_UPDATE 的 world_xyz w 与
  其后(transcript 序)PHYSICAL_ACTION 的 xyz t 满足
  **dist_xy(t,w) ≤ 0.02 ∧ |t.z−w.z| ≤ 0.10**(预冻结标定:back_project
  定位水平位置、z 为接近高度参数,t3s4 实测 xy≈3mm/z 差 3.1cm;
  记录实际距离);
- **C(验证器门控变更)**:存在窗口内技能负验证(pi0_* success=False;
  move_to final_dist≥0.05 视为未达)其后(transcript 序,下一 turn 起)
  PHYSICAL_ACTION 满足(同族重试∧prompt 改变)∨(换族)∨(触发
  TERMINATE),且该变更后窗口继续演进至 tR;
- **D(跨轨迹分叉)**:按 (family, task, 窗口前 2 个 action family
  签名) 分组,组内 ≥2 条轨迹在第 j 位验证结果不同 ∧ 第 j+1 位
  action family 或关键参数(xyz 距离>0.05 或 prompt 不同)不同 →
  组内成员标 D;
- **E(观察后新参数,仅计 FID 不计标签)**:窗口内 OBSERVE/GROUND
  之后发射的技能 prompt 与全部 t0 前 prompt 不同。

标签(互斥,按序判定):

1. **UNRESOLVED**:transcript 缺失/对齐失败/窗口内 >20% 事件 UNKNOWN;
2. **EDGE_REPRESENTABLE**:窗口恰 1 个 PHYSICAL_ACTION ∧ 0 个
   OBSERVE/GROUND_UPDATE ∧ 无 A–D 证据;
3. **OPTION_REQUIRED**:(A∨B∨C∨D)成立(≥2 动作或含观察);
4. **MACRO_REPRESENTABLE**:其余(≥2 动作、无 A–D 证据;参数在 t0
   信息态可定 —— 前置 groundings、eef 相对量、常量、planner 于
   t0 已持有的字面值均算可定)。

## §6 future_information_dependency

FID = true ⇔ (A∨B∨C∨D∨E);false ⇔ 全无;unknown ⇔ UNRESOLVED。
语义:t0 时刻 runtime 可观测状态无法确定后续成功序列的 ≥1 关键要素
(action family / target identity / target pose / 参数 / retry-终止
决策),且该信息在 t0 后经 observation/grounding/verifier 真实获得。

## §7 人工盲审协议

- 抽样:n_audit = min(n, max(⌈0.2n⌉, 30)),按 family 比例分层,
  seed=20261001 机械抽取;
- 盲审材料 = 仅原始工件渲染(fire 信息:family/t0/tR 步号、窗口内
  逐步 command+result、transcript 窗口消息原文、t0/tR eef 状态),
  **不含** analyzer 事件标注、标签、FID、任何聚合结论;
- 人工仅依据材料给 label(四选一)+ FID(true/false),写入
  stageM0_manual_audit.csv(先落盘后比对);
- agreement:label 与 FID 分别 ≥90%(简单一致率,逐条 2×2);
  任一 <90% → M0 measurement invalid → Stage M STOP。

## §8 M0 指标

四比率(分母 = RESOLVED 正例):EDGE/MACRO/OPTION/UNRESOLVED(总池);
FID rate(true/RESOLVED);按 family 分解。分布(中位数+p25/p75):
primitive_count / planner_turns / OBSERVE / GROUND_UPDATE / BRANCH /
VERIFY / time_to_tR。**首次可局部验证位置**:tR 类型分布
(term-only=只在集终止可验 vs 中途 pick-lift/move-ok/doubled-success
可验)+ 中途首个验证证据相对窗口位置(§20 Q5 关键)。

## §9 M0 Gate(冻结数字)

在 RESOLVED 成功恢复上:

- **OPTION ABSTRACTION SUPPORTED** ⇔ OPTION_REQUIRED ≥ 60% ∧
  EDGE_REPRESENTABLE ≤ 25% ∧ FID ≥ 50% ∧ ≥2 个**足够样本**家族方向
  一致(足够样本 = 该族 RESOLVED ≥ 15,冻结);
- 仅 1 个家族达样本下限 → 最多写 **FAMILY-SPECIFIC SUPPORT**;
- MACRO 占主导 ∧ OPTION < 40% → **LONGER PROCEDURE MAY BE NEEDED,
  BUT CLOSED-LOOP OPTION IS NOT JUSTIFIED** → STOP(不跑 M1);
- EDGE 占主导 → **SHORT-EDGE ABSTRACTION NOT FALSIFIED** → STOP。

## §10–17 M1(仅 M0 PASS 时执行;设计冻结于 PASS 后、运行前)

- §10 编译:DISCOVERY/DEV(非 TEST)成功轨迹手工/规则编译,每支持
  族 1–2 个 option,不求全覆盖;不进化、不自动生成;
- §11 schema:option_id/source_failure_state/initiation_guard/
  observability_requirements/internal_state/max_steps/max_retries/
  internal policy(observe-ground-act-verify-branch)/termination_±/
  fallback/physical success contract;一切 branch 只用 runtime
  observable evidence,禁 hidden simulator state;
- §12 信息态:target_grounded / target_pose_valid /
  support_relation_known / latest_physical_result /
  latest_verifier_result / failure_family(+last_reliable_target_pose,
  仅当运行时真可观测);禁读未来态;
- §13 三臂 matched:E=冻结图该族现有最优短边;M=fixed macro(与 O
  同基元/同动作数上限/同执行预算,t0 时冻结整序列与参数,中间
  observation 不得改变后续);O=closed-loop option(同 M 能力预算 +
  observe→grounding/state→branch→retry/terminate)。**O vs M 只差
  中间反馈,不差预算**;
- §14 快照集:未参与编译的 held-out failure snapshots(候选 =
  Stage L HELDOUT_TEST 24 快照,task×seed 隔离,真实 failure
  contract、provenance 完整、restore 已验证;不要求初始 perception
  可用);TEST (task,seed) 不得出现在编译源;
- §15 随机性:J0 已证 Pi0.5 随机 → 每臂每快照 K_ROLLOUT 次重复,
  K 由独立 calibration 集冻结(候选=K0 六集),不得依 TEST 调 K;
  sampling seed 不可控(Stage K/L 同款,以重复取均值);不改 policy
  semantics;
- §16 指标:Primary=validated_recovery_rate/harm_rate/
  no_effect_rate/unresolved_rate;Mechanism=information_recovery_success/
  grounding_reacquired_rate/branch_activation_rate/bounded_retry_success/
  option_termination_correctness/future_information_used_rate;
  **FEEDBACK_RESCUE_RATE**(同快照/seed:M 未达 VERIFIED 而 O 因中间
  observation/grounding/verifier 改变路径后达到)与
  **FEEDBACK_HARM_RATE**(M 成功或无害而 O 因错误 feedback 致 HARM);
- §17 Gate(O vs M 主假设):O−M ≥ 15pp ∧ harm(O)−harm(M) ≤ 3pp ∧
  FEEDBACK_RESCUE ≥ 10% ∧ ≥2 个足够数据家族方向非负;且 O−E ≥ 10pp。
  O>E 但 O≈M → LONG-HORIZON MACRO SUPPORTED, CLOSED-LOOP OPTION NOT
  JUSTIFIED(未来研究 Macro Skill Graph 而非 Option Graph);O>M 且
  全过 → OPTION-LEVEL EXECUTABLE GRAPH SUPPORTED,但 Stage M 仍 STOP;
- §18 禁 full-episode campaign(Option Graph 进线须另立预注册)。

## 工件

M0:stageM0_recovery_segments.jsonl / stageM0_event_annotations.jsonl /
stageM0_abstraction_labels.csv / stageM0_manual_audit.csv /
stageM0_metrics.md / stageM0_decision.md。M1(条件):
options_stageM.yaml / stageM1_option_spec.md / stageM1_split_manifest.csv /
stageM1_rollouts.csv / stageM1_feedback_events.jsonl / stageM1_results.md。
终:STAGE_M_FINAL_REPORT.md(§20 十问,三档判定)。

## §17' 已知局限(冻结时点,计为偏离记录起点)

1. states.json 无每步物体位姿 → FG/MCS 的物体位移类契约分支离线
   不可评,验证采用 H fire_validated(动作级 pick-lift/move-ok/
   doubled-success/集终止);RPS 的 check_success 只在集终止可评;
2. 老集无 memory_events 交叉核对(H1 特有过滤路径;Stage L §17-1
   同款差异);
3. transcript 缺失 9 集 → 其 fire 行 UNRESOLVED-transcript 单列;
4. wall time 含平台负载噪声,只作分布参考;
5. B 判据阈值(xy 0.02/z 0.10)为冻结前对 t3s4 单例的力学标定,
   未接触任何恢复结果标签。

## 偏离记录(运行后追加)

1. **transcript 可用性**:§2 估计缺失 9 集;实际因 transcript 覆盖不足/
   对齐失败而 beyond→UNRESOLVED 的规模约 100 集(池 502 集的 ~20%)。
   最终 UNRESOLVED 22/187 段,未入比率,方向与预注册一致。
2. **对齐算法迭代 3 轮**:98 align-fail → sf-anchor+名称校验 → 错误结果
   丢弃修正 → 两段式区间匹配(498/502=99.2% 对齐)。每轮变更均为机械性
   修正,但开发过程可见聚合计数(非盲);最终版先于盲审冻结。
3. **n_audit 的 n 取值**:公式中 n 未显式定义分母;执行时取 RESOLVED=165
   → n_audit=33(⌈0.2×165⌉)。若取总段 187 则为 38;取样先于 seeing
   analyzer 标签分布的 audit 侧输出。
4. **排除 3 条开发期抽查段**(SPOT_CHECKED 集合,曾人工翻看原始轨迹),
   不入抽样框,防止非首盲污染。
5. **盲审执行者为 assistant(Claude)**:结构盲(dossier 不含 analyzer
   任何输出)但非失忆盲(判据代码在 #135 已读)。预期分歧标记与实际
   分歧集高度重合(标记的 7 条中 4 条为真分歧,其余 3 条经 D-late 一致),
   支持人工标签追踪语义而非机械模仿;该局限仍需披露。
6. **结果**:agreement label/FID 双 87.9% <90% → M0 measurement invalid →
   Stage M STOP(详见 `stageM0_decision.md`);未做任何"修判据→重审"循环。

