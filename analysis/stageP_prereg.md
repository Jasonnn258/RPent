# Stage P 预注册 — Sample, Identify, Select, Abstain(FALSE_GRASP 专属)

日期冻结:2026-10-03 | 依据:用户 39 节 Stage P 规范 | 接口事实:
`analysis/stageP_candidate_interface.md`(P0 审计,先于本文件完成)
**本文件 commit 后、对应阶段的 confirmatory 运行前只允许追加 calibration
附录;运行开始后禁止修改。deviation 只追加(dev-P1 起编号),不改写冻结条目。**

---

## 0. 冻结的已有结论(不重开)

H(graph-as-advice NOT SUP)/I0(router FAIL)/J0(snapshot-restore 可用、
Pi0.5 执行随机、单次反事实不成立)/K(WM NOT JUSTIFIED)/L(evolution NOT SUP)/
M(gate FAIL)/N(N0 PASS;N1 macro 0/72、option 0/72、realized 65.3%、rescue 0)/
O(FG:同命令重采即恢复、单次命中 ≈36.7%、5/12 快照达标、H_A SUPPORTED、
H_B 0/32 NOT SUP、H_C/H_D INCONCLUSIVE、H_E NOT WRITABLE;O4 69/72 零技能
调用 → 不优先 planner redesign)。
**本阶段只研究 FALSE_GRASP;RPS 禁入主实验**(Stage O RPS n=4 不足且局部
macro 已 84.4%)。

## 1. 研究问题与总结构

Stage O 只证明"重发同一恢复命令有时能恢复";Stage P 检验它能否被表示为
**pre-execution candidate selection** 问题:

- **P0 Candidate Interface Qualification**:candidate 是什么、能否冻结/重放
  (gate:replay agreement ≥95%);
- **P1 Candidate Support Geometry**:同 failure state 多采 candidate 是否扩大
  "至少一个有效"的概率(gate:Oracle@8−Oracle@1 ≥15pp ∧ SUPPORTED ≥50% ∧
  MIXED ≥30%);
- **P2 Pre-execution Verifier Qualification**:好 candidate 执行前可否识别
  (gate:pairwise ≥70% ∧ CAPTURE@8 ≥50% ∧ Selected@8−Single ≥10pp ∧
  selected harm ≤ single+3pp);
- **P3 Select-or-Abstain Online**:选择性执行在线是否成立(gate:C−A ≥10pp ∧
  C harm ≤ A+2pp ∧ coverage ≥50% ∧ no-good abstain ≥60% ∧ C<B forced-bad)。

任一 gate FAIL → Stage P 立即 STOP,不进后续阶段。主输出为四个独立判定
(§38),禁"overall works"式总结。

## 2. 禁研清单(§2,全程)

Graph / Graph evolution / World Model / LLM Router / 新视觉 encoder / 新感知
模型 / recovery SFT / OPD / RL / Pi0.5 finetuning / negative prompting /
prompt search / Full Planner redesign / 新 recovery skill / fallback planner
(P3 abstain 后不得偷偷调用任何 fallback)。**底层 Pi0.5 完全冻结**
(权重、chunk 结构、采样超参一概不动)。

## 3. Candidate 与 continuation(冻结;细则见接口文档 §3)

- candidate := failure state 观测(`_vlm_chunk` 同款 prompt 覆盖 +
  `extra_view_images=None`)经 `predict_action_batch(mode="eval")` 采出的
  **第一个 action chunk `[5,7] float32`**。满足 A(执行前完整产生)/
  B(JSON 序列化)/ C(`env.chunk_step` 精确重放)/ D(执行期零模型调用)。
- continuation contract(全部 candidate 同一语义):candidate chunk 计为
  第 1 个 chunk → 冻结标准 Pi0.5 续跑(同 `pi0_pick` 闭环:同 prompt、总
  chunk 预算 24 含 candidate、早停 descent≥0.10 ∧ post-min ascent≥0.05 ∧
  gripper<0.06、libero 终止同语义)→ physical verifier。
- continuation 随机(seed 不可控,J0/vla_server 无注入口)→ **R_CONT = 3**
  次/candidate:restore(S) → 执行 chunk → 存 S_j(post-chunk 态,确定性)
  → 3 次独立 restore(S_j)+续跑。
- candidate 生成保持同 obs / 同 task command / 同 grounding / 同 recovery
  command / 同权重,**只改采样**(§11)。recovery command := 重放确定的
  step ≤ t0 最后一条 Pi0.5 族命令逐字(Stage O O1 同款)。
- Stage P 检验命题(§5 操作化):"selecting the initial sampled chunk 能否
  改变 downstream recovery probability"。禁把整个 closed-loop attempt 事后
  称为 candidate。

## 4. Physical verifier 与标签(§12 操作化;优先级 RECOVERY>HARM>NO_EFFECT)

测量点:candidate chunk 后 + 每 continuation chunk 后 + 终态
(`sim_measurement` + `check_success` 每点全测,Stage O 同源):

- **RECOVERY**:任一测量点 FG 契约成立(目标物 dz ≥ +0.03 m 且 xy 距
  EEF ≤ 0.10 m)或 `check_success()==True`;
- **HARM**(未 RECOVERY 时,任一测量点):目标物 dz < −0.03 m 或 dxy > 0.08 m
  (N1 harm 反向),或任一物体 z < 0.80 m,或 EEF 出包络 x(−0.60,0.35)
  y(−0.45,0.50) z(0.80,1.35);
- **NO_EFFECT**:其余;
- **INFRA_FAILURE**:restore 读回≠0 / vla 崩溃 / chunk_step RPC 异常 / 重放
  异常(§35 分类),≤3 重试仍败记 infra 行,**不进 policy denominator**。

candidate 级聚合(R_CONT=3):**RECOVERY_CAND := ≥1 次续跑 RECOVERY**;
否则 HARM_CAND := ≥1 次 HARM;否则 NO_EFFECT_CAND。逐 candidate 同时报告
recovery 率 / harm 率(3 次中次数),供 P2 目标用。

## 5. P0 — replay qualification(§6/§8)

- 数据:Stage O 8 个 FG 快照(§33 许可:接口理解用途;**不得**充当 P1
  confirmatory)。candidate 选择规则(先于任何执行冻结):每快照前 2 个
  candidate = **16 个**(≥12 达标),逐个执行前生成并冻结。
- 每个 frozen candidate:从同一 original snapshot **restore → 执行 chunk**
  ×3 次(纯 chunk 执行,不含 continuation;chunk 执行即 candidate 本体)。
- chunk 级观测量(全部冻结操作化):
  - transition class(EE 主导位移):DESCEND(dz≤−0.015)/ ASCEND(dz≥+0.015)/
    LATERAL(dxy≥0.03 且 |dz|<0.015)/ STATIONARY(其余);
  - contact class:夹爪开口变化 CLOSING(Δ≤−0.01)/ OPENING(Δ≥+0.01)/ HOLD;
  - object displacement class:TOWARD_LIFT(dz≥+0.01)/ HARM_DISP(dz≤−0.01
    或 dxy≥0.03)/ UNMOVED;
  - success/failure physical flags:FLAG_TARGET_DISPLACED(dxy≥0.02 或
    |dz|≥0.02)/ FLAG_GRIPPER_CLOSED(末态 grip<0.06)/ FLAG_EE_NEAR_TARGET
    (末态 EEF-目标 dxy≤0.10);
  - 数值指纹:endpoint EE pose、目标物位移向量(max|Δ| 跨 replay,预期 0.0)。
- **gate(≥95% 双指标)**:transition-class(三维向量)agreement 与
  success/failure flags agreement,分母 = 全部 (candidate × replay) 比较
  对(replay 间互比);另报 per-candidate 最差值与数值指纹是否逐位相等。
  agreement = 与该 candidate 众数类一致的比较对比例。
- FAIL → `CANDIDATE_OBJECT_NOT_QUALIFIED`,Stage P STOP,不得用 verifier
  预测自身 label 不稳定的对象。P0 PASS 判据另含:identity 明确(接口文档)、
  可执行前冻结、replay PASS、candidate+固定 continuation 有可定义 outcome
  (§4)。P0 FAIL 不推翻 Stage O POLICY SUPPORT。

## 6. P1 — confirmatory 数据集(§10)

- **24 个新 FG 快照:12 DEV + 12 HELDOUT_TEST**(容差 20-28;<20 或不可行
  → 停并报 INSUFFICIENT_SNAPSHOTS)。Stage O 快照只作 discovery(§33)。
- 采集:Stage O §3 程序逐字(完整 Full Planner episode,max-turns 40,首个
  FG 事件为 t0,每 episode 至多 1 快照,判定规则先于运行冻结,零结果筛选);
  RPS 事件一律 logged-excluded。
- 隔离:task×seed 排除集 = N 池 ∪ L split 池 ∪ Stage O 已用 12 格;候选
  grid = {t3,t5,t9} × seeds **29-46**(全新窗口),扫描顺序 task 主序
  3→5→9、seed 升序(FG 集中在 t3)。DEV/TEST 划分:manifest 冻结时按
  collect 顺序交替分配(奇数序 DEV、偶数序 TEST,seed=20261003 复核),
  划分先于任何 P1 执行。
- 产物:`analysis/stageP_split_manifest.csv`(全 provenance 列 + state_len +
  eef0 + check_success_at_t0,boot 守卫沿用 dev-O5:重放必须复现 FG 事件且
  base check_success=False;退化者剔除规则同 dev-O5 init 取证)。
- **manifest 冻结 commit 先于任何 P1 执行**;正式 TEST 后 K_MAX/R_CONT 禁改。

## 7. P1 — 采样、执行与指标(§11-§14)

- 每快照:boot(重放 1..t0 + 守卫)→ restore → **K_MAX = 8** 个 candidate
  逐个生成(生成序即冻结 candidate order 1..8)→ 每个 candidate 按 §3
  执行(chunk + 3 continuation)→ 标签。
- **candidate 间相互独立**:每个 candidate(及其 3 续跑)都从同一
  original snapshot S 出发(§12);S_j 只在同 candidate 内部复用。
- 指标(TEST 12 上 confirmatory):
  - Oracle@1/2/4/8 = 前 K 个 candidate 中存在 RECOVERY_CAND 的快照比例;
  - SUPPORTED_SNAPSHOT_RATE = K_MAX=8 中 ≥1 RECOVERY_CAND 的快照比例;
  - MIXED_SUPPORT_RATE = ≥1 RECOVERY_CAND 且 ≥1 NON_RECOVERY_CAND 的快照
    比例;
  - per-snapshot 表 + Wilson 95% CI(快照为统计单位,§34);
  - DEV 12 同表(仅作 sanity/特征理解,不进判定)。
- **P1 gate(§15,全部冻结)**:Oracle@8 − Oracle@1 ≥ 15pp ∧
  SUPPORTED_SNAPSHOT_RATE ≥ 50% ∧ MIXED_SUPPORT_RATE ≥ 30%。
  FAIL → STOP,结论 = "REPEATED ROLLOUT SUPPORT EXISTS, BUT WITHIN-STATE
  CANDIDATE DIVERSITY IS INSUFFICIENT FOR SELECTION STUDY",禁训 verifier。

## 8. P2 — verifier 资格(§16-§23;仅 P1 PASS 后)

- 特征集(全部执行前可得,§16-§18;禁 §17 泄漏清单):
  - **V0 CANDIDATE_ONLY**:chunk 原始 5×7、Δxyz 逐步、Δrotation、gripper
    序列、动作幅度(范数)、末端估计(chunk 末 EE 预测位移)、smoothness/
    jerk(二阶差分);
  - **V1 +STATE**:并入 Stage K 结构化 14D 物理 state(实现定位:Stage K
    state builder;字段清单在 features builder 内冻结枚举);
  - **V2 +HISTORY**:failure family、previous skill/action summary、最近
    观测物理 transition、最近 failure evidence(全部来自 prefix 记录)。
- 模型纪律(§19):**两候选**——A. L2 正则 logistic(scaler + class_weight
  balanced,C∈{0.01,0.1,1,10} DEV 网格);B. 浅层梯度提升树(max_depth≤3,
  n_estimators≤200,lr 0.1)。DEV(12)上以 within-snapshot pairwise accuracy
  选一个 final verifier 并**冻结**(模型类型+超参+特征集);TEST(12)上只跑
  一次,禁切换。禁 deep VLM / large transformer / 新 embedding 训练。
- 目标(§20):主 = RECOVERY_CAND vs NON_RECOVERY_CAND;**harm 风险单独
  学习/报告**(HARM_CAND 概率或秩),禁把 HARM 与 NO_EFFECT 混为一谈。
- 指标(§21-§22):within-snapshot pairwise ranking accuracy、Success@1、
  Selected@K、Oracle@K、CAPTURE_RATIO@K = (Selected@K−Single)/(Oracle@K−
  Single)(|分母|<5pp → NOT_IDENTIFIABLE);harm rate of random / first /
  selected-top1 / oracle candidate + harm AUROC(标签量足够时)。
- **P2 gate(§23)**:pairwise ≥70% ∧ CAPTURE_RATIO@8 ≥50% ∧
  Selected@8−Single ≥10pp ∧ selected harm ≤ single baseline +3pp。
  FAIL → STOP,结论 = "GOOD CANDIDATES EXIST, BUT TESTED PRE-EXECUTION
  SIGNALS DO NOT RELIABLY IDENTIFY THEM",禁自动升级 VLM/WM/larger model。

## 9. Abstention 校准(§24;仅 P2 PASS 后)

DEV 上校准 final verifier 分数:选 τ_accept 使 candidate recovery
**precision ≥70% 且 harm rate ≤5%**,在满足者中取 **coverage 最大**;
同时冻结 τ_harm(selected candidate 的 harm 分数阈值,P3 臂 C 双条件)。
DEV 上无同时满足的 τ → Stage P STOP,不进 P3。校准曲线全量落盘。

## 10. P3 — 在线 select-or-abstain(§25-§31;仅校准通过后)

- **全新 12-18 个 P3 HELDOUT FG 快照**(同 §6 程序采集,排除集再并
  P1 24 格;manifest `stageP3_split_manifest.csv` 冻结)。禁复用 P1/P2
  TEST。abstain 语义(§27):不执行任何 recovery 物理动作,标
  UNRESOLVED_ABSTAIN,禁 fallback(§2/§32)。
- 三臂(§26/§28,同快照独立 restore,同 verifier/同 horizon/同 verifier
  契约):
  - **A SINGLE**:采 1 candidate,执行(chunk+continuation);
  - **B FIXED BEST-OF-K**:采 K_MAX=8 个全部打分,执行分数最高者
    (无论分数多低都必须执行);
  - **C SELECT-OR-ABSTAIN**:逐个采样+打分;score≥τ_accept 且 harm<τ_harm
    → 立即执行;否则继续采样至 K_MAX;全不达标 → ABSTAIN。
- 指标(§29):VERIFIED_RECOVERY_RATE / HARM_RATE / NO_EFFECT_RATE /
  ABSTAIN_RATE / EXECUTION_COVERAGE / AVERAGE_CANDIDATES_SAMPLED /
  WALL_TIME / RECOVERY_PER_EXECUTED_ACTION。support-aware 事后评估(§30,
  只评不改在线决策):ABSTAIN_WHEN_NO_GOOD / EXECUTE_WHEN_GOOD_EXISTS /
  FALSE_ABSTAIN / FORCED_BAD_SELECTION(B 臂强制执行低分 candidate)。
- **P3 gate(§31)**:C recovery − A recovery ≥10pp ∧ C harm ≤ A harm+2pp ∧
  coverage ≥50% ∧ (sampled set 无 recovery candidate 时 C abstain ≥60%)
  ∧ C 的 FORCED_BAD_SELECTION < B。分支结论:B 升 C 不升 → "BEST-OF-K
  SUPPORTED, ABSTENTION NOT JUSTIFIED";Oracle 高但 B/C 都不升 →
  "SELECTION MECHANISM NOT SUPPORTED"。

## 11. 统计纪律(§34)

统计单位 = failure snapshot;candidate 是 snapshot 内 repeated samples。
全部主指标按 snapshot 配对报告,CI 用 Wilson(比例)或 bootstrap(差值,
1000 重抽、按 snapshot 重抽、seed=20261003)。禁把 8×24 写成 N=192 独立态。

## 12. Infra 纪律(§35)

分类记录:candidate generation failure / replay failure / Pi0.5 failure /
simulator failure / verifier-instrumentation failure / physical policy
failure。infra 不进 denominator;正式阶段 infra >2% → 暂停解释、只修
instrumentation/infrastructure、禁改 candidate semantics,deviation 编号
追加。环境三件套 + OPENPI_DATA_HOME + no_proxy 沿用 Stage O(dev_preflight
+ .runlocks/stageP_*.lock,并发 ≤4,重要产物只写 /workspace/yjx)。

## 13. 产物清单(§36)

analysis/:stageP_prereg.md(本文件)、stageP_candidate_interface.md、
stageP_replay_qualification.csv、stageP0_decision.md、
stageP_split_manifest.csv、stageP_candidates.jsonl、
stageP_candidate_outcomes.csv、stageP_support_geometry.csv、
stageP1_results.md、stageP1_decision.md;(P1 PASS)stageP_verifier_features
.parquet、stageP_verifier_dev_results.csv、stageP_verifier_test_results.csv、
stageP2_results.md、stageP2_decision.md;(P2 PASS)stageP3_split_manifest.csv、
stageP3_rollouts.csv、stageP3_selection_events.jsonl、stageP3_results.md;
STAGE_P_FINAL_REPORT.md。脚本:stageP_rt.py、stageP_replay.py、
stageP_collect.py、stageP_geometry.py、stageP_features.py、stageP_verifier.py、
stageP3_online.py、stageP_analyze.py(各自 confirmatory 运行前 commit)。

## 14. Hard STOP(§39)

Stage P 完成后 STOP,禁自动:verifier scaling / VLM verifier / temporal
transformer / World Model / negative prompting / Pi0.5 训练 / SFT / OPD /
RL / fallback Planner / Graph / recovery skill learning。P0 FAIL =
Stage O 随机恢复不能直接转化为 candidate-selection 问题;P1 FAIL =
diversity 不足;P2 FAIL = 执行前信息不足;P3 FAIL = 离线可分性未转化为
安全在线恢复。对应 gate PASS 后未来才能另立阶段研究更复杂 verifier /
adaptive fallback。

---

## 附录 A — Stage O O1 discovery 用途声明(§33)

Stage O O1 数据(FG 8 快照 × 16 重采)仅用于:candidate-interface
理解(本文 §3)、粗功效预期(单次命中 36.7%、3/8 快照 16 采全中 →
K_MAX=8 下 Oracle 预期偏高、MIXED 预期中等)、假设形成。**不得作为
Stage P 任何 confirmatory 证据**;P1/P2 TEST 与 P3 TEST 相互独立。

## 附录 B — 预算账(先冻结)

- P0:16 candidate × 3 replay = 48 次 chunk 执行(纯 chunk,秒级)+ 8 快照
  boot(重放 prefix);预计 <1h。
- P1 采集:FG 命中率按 Stage O 经验 ~35%(13/37)→ 24 快照 ≈ 60-70 集 ×
  ~35 min ≈ 1.5-2 天(≤2 并发,Training Task 候选;启动前向用户报预算)。
- P1 执行:24 快照 × 8 candidate × (1 chunk + 3 continuation) ≈ 576 次
  pick ≈ 20s/次 ≈ 3.5h(1 worker)/ ~2h(2 workers)+ boot 开销 ~1.5h。
- P2:特征构建(纯离线)+ 2 模型 × 3 特征集 DEV 网格(分钟级)+ TEST 一次。
- P3:12-18 快照 × (A:1 + B:8 + C:1-8) candidate 执行 + 采集 ~25-40 集。
超限先报告再继续(§13 纪律同 Stage O)。
