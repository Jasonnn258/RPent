# Stage L 预注册 — Verify-to-Evolve Executable Graph(FINAL,先 commit 再运行)

_冻结:2026-09-30 | 依据:用户冻结 spec §0-§18 + stageL_existing_pool_audit.md_
_split manifest:analysis/stageL_split_manifest.csv,split_hash(md5 前 12)=
**77695bed7074** | 池清单:analysis/stageL_pool_inventory.jsonl_
_冻结图基线:resources/libero/executable_graph_v1.yaml(FG-1/2/3、RS-1/2/3、
MS/CS-1/2/3;L 只用 FG/RS 边)_

本文档冻结 Stage L 全部可自由度。运行期只允许按本文执行;任何偏离
写入最终报告"偏离记录"节,不做事后豁免。

## §1 研究问题与假设

核心问题:执行反馈能否把退化恢复图进化为物理验证过的、非退化的、
状态条件化的可执行图?

- **H_L1**:来自真实失败轨迹的 recovery-completing prefix 产生比冻结图
  更好的候选(H 先验:soft graph NOT SUPPORTED、menu violation 90%;
  K:VERIFIED 48/48 集中于 FG-3 单边,瓶颈在候选质量/多样性);
- **H_L2**:执行一致性 + 物理转移双验证能过滤 plausible-but-non-executable
  / executable-but-ineffective / accidentally-effective / harmful 四类;
- **H_L3**:条件特化 —— 不同物理状态下同族内最优边不同;若不成立,
  系统退化为确定性规则/技能库,图分叉无依据。

## §2 Split(机械选定,hash 77695bed7074)

| 角色 | n | 定义 |
|---|---|---|
| L_DISCOVERY_DEV | 34 集/快照(FG 24、RPS 10) | = K 数据集快照(K-TRAIN/VAL/TEST 均已烧毁,合并为 L 开发侧);既是 §4 挖掘源,也是 §9 DEV 验证快照 |
| L_CAL_RESERVED | 6 集 | K0 标定快照;L 不挖掘、不进 DEV/HELDOUT(见 §8) |
| L_HELDOUT_TEST | 24 快照(FG 12、RPS 12;12 个全新对;t9 14 / t5 7 / t3 3) | 池外集,episode 级 anchor(全局最早 fire),族内 md5(episode_dir) 升序取前 12 |

隔离保证:
- HELDOUT 对(task,seed)与 DISCOVERY/DEV/CAL 全部对构造性不相交
  (池外扫描排除);K-TEST 对不入 HELDOUT ✓;
- HELDOUT 选择规则完全机械,无替补:restore 失败 = infra,如实减 n
  并记录,禁止换集;
- 同快照的 K 次重复 rollout 完整属于同一 split;
- HELDOUT 在 candidate generation + evolution 完成前不可见(池扫描只
  记 detection 级:fire 步/族/合法边;无任何恢复/成败字段);
- 已知偏斜(如实记录):HELDOUT 任务分布 t9 偏重(14/24,源自池本身
  分布),Gate B 的"非单任务/seed 驱动"检查据此执行(见 §12)。

## §3 Family inclusion(看 HELDOUT 前已冻结)

纳入 **FALSE_GRASP、RELEASE_PREDICATE_STALL**;**不纳入
MOVE_CONTACT_STALL**(开发侧正例仅 2、DEV 无既控 MCS 快照,凑三类
违反 spec §3;与 K 决策一致)。

## §4 L0 挖掘(→ stageL_recovery_prefixes.jsonl)

对象:L_DISCOVERY_DEV 34 集的全部 fire(离线 replay_fires,同 H/K
代码路径)。对每个 fire@t:

- **正例 prefix**:向后不限窗找首个 validating action(H 冻结契约:
  FG/RPS = pi0_pick 且 peak_lift ≥ 0.005,或集终止 libero_terminated);
  prefix = t+1 … 该动作(含);每条记录:source episode/task/seed/
  failure node+family/fire 时刻 runtime 可观测前状态(EEF xyz、gripper、
  ooi 距离)/ 动作序列(states.json 原始 command dict 含参数)/
  参数 / 终止物理状态 / validated transition / recovery 标签 /
  prefix 长度;
- **负例 prefix**:无 validating action 的 fire,prefix = 后 ≤10 个动作,
  标签 no_recovery(可见 held-drop 则记 harm_hint),作为 §5 反证据;
- 挖掘为离线读取;在线真值一律以 §7 双验证与 §9 执行为准(离线
  first_validating 只用于选源,不作为 promotion 证据)。

## §5 候选编译(→ stageL_candidate_edges_v0.jsonl)

三个来源,**全部锚定物理证据,禁止自由发明**:

- **A 轨迹挖掘**:正例 prefix → 可编译动作序列(§4 原始 command 的
  工具与参数);
- **B 参数化合并**:同族 ≥2 条支持同模板的 prefix 合并为一条参数化边
  (绑定仅限 runtime observable:LAST_PICK_PROMPT/OOI 位置/EEF);
- **C 离线 LLM 最小泛化**:仅在 A/B 之后、对已有模板做最小参数/步序
  泛化;**LLM 只产 CANDIDATE,永不参与 PROMOTION 判定**;无物理证据
  支撑的发明直接丢弃。

每个候选必备字段:id、failure_family、source_episodes(全部溯源)、
runtime observable 适用谓词、action_sequence(每步 executor 原语 +
parameterizer 绑定)、expected_transition(声明)、physical_verifier
(§7-B 契约引用)、失败出口、rollback 语义、max_attempts、来源证据指针。
**必须编译到既有真实原语/服务/Pi0.5 技能/感知工具,否则
REJECT_UNEXECUTABLE(编译期静态检查,不进入执行)。**
上限:去重后 v0 ≤ 12 条;超出时保留支持 episode 数(独立源数)最高的
12,平手按 md5(id) —— 证据量准则,非表现准则。

## §6 去重

键 = 动作序列(工具链)+ 参数化语义(绑定结构)+ expected_transition。
保留全部 provenance(合并候选的多源并集)。

## §7 双验证(L1)

**Verifier A —— 执行一致性**:实际执行 trace 与声明 action_sequence
逐位比对 —— 工具序列全等 ∧ 解析参数数值差 ≤ 1e-4 ∧ prompt 串全等。
**修订 v1.1(2026-09-30,任何验证运行前)**:感知无果链中止是执行器
冻结语义(K 同栈:链中止记 NO_EFFECT),属候选真实行为而非一致性
违规 —— A 判定改为**前缀语义**:实际 trace 须为声明序列的前缀且参数/
prompt 全等、无任何未声明动作;感知无果早止 = A-PASS(chain_abort=true,
outcome NO_EFFECT,计入效力统计)。A FAIL(未声明动作/参数超差/prompt
不匹配/执行器私换)的 rollout 不计入效力统计(单列账目)。
执行语义与 K 完全同栈:链中感知无果 → 链中止记 NO_EFFECT;原语异常 →
ERROR;序列完成后判定窗口 4 样本 × 5 步保持。

**Verifier B —— 物理转移契约**(逐字沿用 stagek_graph_executor.py 冻结
常数,base = 快照恢复态,ooi = 快照 ooi):

- FG VERIFIED:(d_ooi_z ≥ 0.01 ∧ corr(d_ooi_z, d_eef_z) > 0 ∧
  max_d_ooi_z ≥ 0.01)∨ pick 物证(peak_lift ≥ 0.005 ∧
  final_gripper_opening ≤ 0.06);
- RPS VERIFIED:check_success_ever = True(窗口内任一样本);
- HARM(未 VERIFIED 时):held ∧ dropped(min_grip ≤ 0.06 ∧ 抬升证据
  (max_d_eef_z ≥ 0.01 ∨ peak_lift ≥ 0.005)∧ d_ooi_z ≤ −0.02)
  ∨ swept(max_obj_xy ≥ 0.05);
- 判定优先级 VERIFIED > HARM > NO_EFFECT。

## §8 K_ROLLOUT = 4(沿用 K0 冻结,不重推导)

理由:同一执行器栈、同一 Verifier B 契约、同一 Pi0.5 rollout 协议;
K0 已在 6 个独立标定快照上完成 {4,8,12,16} ladder 并冻结 4(最小达标:
CI_verif 中位 ≤0.30 ∧ rank_agree ≥0.80 ∧ CI_harm 中位 ≤0.25)。
L 不重跑 ladder、不改 K(任何中途改动 = 阈值修改,禁止);
L_CAL_RESERVED 6 集因此保持不挖掘、不使用(保守)。
Pi0.5 sampling seed 不可控(K 已证):k=1..4 重复吸收随机性,
per-(candidate, snapshot) 报 P̂_v/P̂_n/P̂_h + Wilson 95% CI。

## §9 DEV 评测协议(Round 1)

- 快照:L_DISCOVERY_DEV 34(FG 24、RPS 10),restore = K 采集器同款
  (episode prefix 逐命令重放 → save_state),J0 已证逐位精确;
- 冻结边基线**同批重跑**(不直接复用 K 数据集数字,避免跨批次漂移
  混杂):每快照 × 该族合法冻结边 × K=4;
- 候选:每快照 × 适用候选(族匹配 + 适用谓词在快照 observables 上
  通过)× K=4;
- **逐候选源隔离**:候选统计排除其全部 source_episodes 对应的 DEV
  快照(episode 级,预注册);pair 级排除作为敏感性分析并列报告;
- elig(c) = 排除后剩余适用快照数;门槛 min-N:FG ≥ 6、RPS ≥ 3,
  不足者不参评(记录,不补跑);
- 资源纪律:MUJOCO_GL=osmesa、并发 ≤8、.runlocks 锁、断点续采、
  日志写 /workspace/yjx;**预算上限 DEV ≤ 2400 rollouts**,超限即停
  并如实记录(禁止提高上限);
- 产物:stageL_round1_verification.csv(每 rollout 一行:候选 × 快照
  × k,含 Verifier A 结果、outcome、verify stats 原始字段)。

## §10 晋升门(仅 DEV 证据,一次性判定)

对每条候选 c(族 f),在 elig(c) 快照上:

- exec_consistency(c) = A-PASS rollout 数 / 总 rollout 数 **≥ 0.95**;
- harm(c) = mean_s P̂_h(c,s) **≤ 0.05**;
- 冻结族最优 f* = 在同一 elig(c) 快照集上 P̂_v 均值最高的冻结合法边;
- **Path A(替换/增强)**:mean_s[P̂_v(c,s) − P̂_v(f*,s)] ≥ +0.10
  ∧ advantage > 0 的快照占比 ≥ 50%;
- **Path B(覆盖空白)**:U = elig 内全部冻结合法边 P̂_v = 0 的快照;
  |U| ≥ 3 ∧ #{s∈U: P̂_v(c,s) ≥ 0.5} / |U| ≥ 0.60;
- **PROMOTE ⇔ (A ∨ B) ∧ min-N 达标 ∧ exec_consistency ∧ harm 门**,
  多独立快照约束由 min-N + 多数占比条款承载;
- 落选候选全记录(id/失败模式/原因),不得删除;**任何阈值不可修改**。

## §11 Round 2(≤1 轮,最小修复)

仅允许:参数化修正 / 插入既有解析步 / 删除无效步 / 重排组合;
禁止:新模块、新模型、新感知、WM、Router、新证据源。
Round 1 落选且可修复者 → v1 候选,同 §9/§10 协议重验;其余落选者
状态 REJECTED(终态)。Round 2 后立即冻结
resources/libero/executable_graph_stageL_final.yaml(冻结边 + PROMOTED,
含 graph_hash),此后图不可再改;HELDOUT 只在冻结之后触碰。

## §12 HELDOUT 评测 + Gate A/B

在 24 个 HELDOUT 快照上,三池全部执行(冻结边 / PROMOTED / v0 raw
池含 REJECTED,raw 池上限 12 条同 §5 准则),K=4,同 §7 双验证。

- 图 G 在快照 s 的适用边集:G 的族边 ∩ 检测合法边(冻结图)/
  PROMOTED 候选(族 + 适用谓词)(进化图);
- **GRAPH_COVERAGE(G)** = #{s: max_e P̂_v(e,s) ≥ 0.5} / n_s;
- **BEST_EDGE_RECOVERY(G)** = mean_s max_e P̂_v(e,s);
- **HARM_RATE(G)** = 全部 (e,s) 评估的 P̂_h 均值;
- **USEFUL_EDGE_RATE** = mean over PROMOTED 边(适用快照中 P̂_v ≥ 0.5
  占比);**RAW_TO_PROMOTED_PRECISION** = raw 池 vs PROMOTED 的
  useful 率对照(报告项,无门)。

**Gate A(formation)**:
(COV_evo − COV_frozen ≥ +0.15) ∨ (BEST_evo − BEST_frozen ≥ +0.10),
且 HARM_RATE_evo ≤ 0.05。
FAIL → GRAPH EVOLUTION NOT SUPPORTED → STOP(§18:停止图进化线)。

**Gate B(条件特化,仅 A 过后)**:
u(e,s) = P̂_v(e,s) − λ_harm·P̂_h(e,s),**λ_harm = 1.0**(冻结);
族内全局最优 g_f = argmax_e mean_s u(e,s);
GAIN = mean_s[u_oracle(s) − u(g_{fam(s)}, s)]。
PASS ⇔ GAIN ≥ 0.10 ∧ ≥2 条不同边各自在其适用快照的 ≥20% 上为
u-argmax ∧ 每条该份额跨越 ≥2 个 (task,seed) 对(对冲 t9 偏斜的
单任务驱动)。
FAIL → "EXECUTABLE RECOVERY LIBRARY MAY BE USEFUL, BUT GRAPH
BRANCHING IS NOT JUSTIFIED"(未来 = 确定性族级技能/规则库)。

## §13 选择器禁令 + 晋升状态

- 禁止在任何 HELDOUT 数据上训练选择器(router/分类器/WM/RL);
  选择器研究只在双门 PASS 后另立 Stage;
- 候选状态机 CANDIDATE → VERIFIED → PROMOTED / REJECTED;
  运行时图只含 PROMOTED;评测批次内图冻结。

## §14 工件(全部带 git commit / split_hash / graph_hash / provenance)

stageL_split_manifest.csv(已冻结)、本 prereg、
stageL_recovery_prefixes.jsonl、stageL_candidate_edges_v0.jsonl、
stageL_round1_verification.csv、stageL_round1_decision.md、
stageL_candidate_edges_v1.jsonl、stageL_round2_verification.csv、
stageL_round2_decision.md、resources/libero/executable_graph_stageL_final.yaml、
stageL_heldout_edge_utility.csv、stageL_specialization.csv、
STAGE_L_FINAL_REPORT.md。logs/ 下原始 rollout jsonl 为工作产物,
汇总表拷入 analysis/ 保真。

## §15 十问(final report 直答,SUPPORTED/NOT SUPPORTED/INCONCLUSIVE)

Q1 prefix→有价值候选? Q2 generate-verify-promote 精度? Q3 执行一致性
过滤量? Q4 物理验证过滤量? Q5 进化图 coverage > 冻结图? Q6 promoted
跨任务/seed/快照复现? Q7 同族多条有效边? Q8 不同状态最优边不同?
Q9 特化增益够大? Q10 是否有资格重启 Rule/学习打分器/WM/Router?

## §16 STOP 与预算护栏

- 挖掘正例 < 3(FG)或 < 2(RPS)→ 该族放弃;两族皆不足 → STOP
  (formation 阶段中止,如实报告);
- Gate A FAIL → STOP;预算超限(DEV 2400 / HELDOUT 2400 rollouts)
  → 停并记录,不提额;
- Stage L 结束后硬 STOP(spec §18):禁止 full-episode Graph campaign、
  Router 训练、WM 重启、换编码器、SFT/OPD/RL、加进化轮、改 TEST 后图。

## §17 偏离与已知差异记录(冻结时点)

1. 老 campaign(20260905/20260915)HELDOUT 集无 memory 事件可交叉
   核对(H1 特有过滤路径),fire 检测为纯 replay_fires;schema 三个
   年代逐字段一致,restore 前另有机械 dry-run(非结果性);
2. HELDOUT 任务分布偏 t9(14/24)—— 池分布所致,机械选择不做
   再平衡(再平衡=非机械);
3. K0 标定 6 集不重用不重挖(§8);
4. term 型恢复占挖掘正例 ~95%(recovery-completing 定义含集终止);
   GRASP_CONFIRMED 型(pi0_pick + lift)单独计数报告;
5. K 数据集侧冻结边基线同批重跑(不复用 K 数字),K 数字仅作参考并
   列报告。
6. (2026-09-30,Round 2 启动前)Round 2 冻结边基线**复用 Round 1 同快照
   测量**(--no-frozen,不重跑):快照由 episode 重放确定性重建且每 rollout
   restore readback 逐位校验,冻结边未变,重跑同一 (snapshot, edge, 协议)
   仅重复采样 pi0 非确定性、无信息增量;候选行全部为 Round 2 新跑。
   §10 比较量 = 候选(R2)vs 冻结(R1)同快照配对差,协议同 §8;
7. (2026-09-30,Round 2 启动前)Round 1 全 REJECT 后的修复取舍依据
   Round 1 DEV rollout 取证(§17-6 复用同一数据源,无 HELDOUT 信息):
   LC-FG-1/2 感知死(SAM3 0.009–0.059 ≪ 阈值 0.2,降阈值至 0.1 仍全
   found=False)、LC-RS-2 prompt 指向原位置(词表内无修复)、仅 LC-RS-1
   有证据支持的最小修复(t9s6 下降步)→ v1 仅 1 候选 LC-RS-1R,其余
   REJECTED 终态(analysis/stageL_candidate_edges_v1.jsonl)。
