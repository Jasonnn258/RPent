# Stage R 预注册 — Failure Persistence & Retryability Characterization

冻结:2026-10-07 | 分支:research/pre-ovpm-20260905
规范:用户 2026-10-07 下发的 36 节 Stage R spec(唯一权威;本文件为可执行
蒸馏,冲突处以 spec 为准并记 deviation)。
定位:**只测失败持续性**(one observed failure 何时才构成 persistent problem
的证据),不提出任何 recovery method;§36 Hard STOP 全表生效。

---

## 0. 冻结结论引用(spec §1)

Stage O:FG 上重发 recovery command 可产生真实 recovery(POLICY SUPPORT
SUPPORTED,single-sample ≈36.7% 终态契约)。
Stage P:candidate interface qualified;selection/verifier 无 headroom
(O@8−O@1=+10pp<15pp,9/10 TEST 首候选即恢复)。
Stage Q:reproducible subset 上 PP stable .391、exec +7.8pp、cand +4.7pp、
interaction −21.9pp(三效应均未过 15pp 门);TRANSIENT_SUCCESS SUPPORTED
(gap +17~30pp);额外发现 14/22 案例 t0 重执行曾成功 → 单次失败未必是
持续问题的证据。

## 1. 措辞纪律(spec §3/§5)

- temporary vs stable deviation 区分;repeated interventions 测量,单次
  rollout 不得当 state property;
- PRIMARY OUTCOME = **STABLE_RECOVERY**(沿用 Stage Q 冻结 stable contract:
  首中后全测量点保持 ∧ (任一点 check_success ∨ i* 后点数 ≥
  HOLD_MIN_POINTS=4);ACQUISITION 仅 secondary);禁改契约;
- 禁 sub-mm 因果解读与 "bit-exact identical state";统一写
  **task-equivalent reconstructed state / observably matched state**
  (Stage Q restore gate:transition-class 一致率 77%<90%)。

## 2. 采集期仪器(spec §6;默认关闭,RPENT_STAGE_R_TRACE=1 启用)

零语义改动,只增观测:
- toolkit `_step` 技能边界:`save_state` 快照 → `stageR_snapshots/
  step_{idx:03d}_{pre,post}.npy`(S_pre = step t0 的 pre 快照,S_post =
  post 快照,均为原始 live episode 字节);
- env 客户端 choke point(step/chunk_step):动作流逐条落
  `stageR_trace.jsonl`(base64 float32 逐位保真;chunk 记录关联
  step_idx/skill);
- pick 类技能(pi0_pick/pi0_doubled)每个 chunk 前附 sim_measurement
  低维测量(供 stable-failure 判定:失败技能期间任一测量点满足
  acquisition(dz≥0.03 ∧ dxy(obj,EEF)≤0.10,基准=技能首个测量点)∨
  check_success → 非稳定失败,排入 excluded)。

## 3. 重建方法(spec §6/§7)

- **DIRECT_SNAPSHOT**:restore 原始 live S_pre 字节;
- **PREFIX_REPLAY**:同 (task,seed) fresh env → `env.reset()`(确定性
  init)→ 逐条重放历史执行的底层动作(base64 解码;禁止重调 Pi0.5)至
  t0 首 chunk 前边界;
- 参考臂 **LIVE_BOOT**(R0 用):Stage Q boot_to_pre(Pi0.5 技能重放,
  observably matched)。

重建一致性报告(spec §7):robot qpos/qvel、EEF、gripper、target
pose/vel(读自快照与 sim_measurement)、state sha、flatten per-index
Δ;contact summary 接口不可读处记 not_available(沿用 Q 纪律)。

## 4. R0 — 重建资格门(spec §8;DEV pilot 8 事件)

每事件:probe candidate = 从 LIVE_BOOT S_pre 采样一次并冻结(prompt =
t0 原命令 prompt);三臂各 R0_TRIALS=4:
- LIVE ×4(每次 fresh boot_to_pre,不 restore);
- SNAP ×4(restore 原始 S_pre 字节);
- PREFIX ×4(reset+动作重放)。
统一 hold-through continuation + 双契约标签。

**门**(pooled over DEV 事件,stable 率):
- |SNAP−LIVE| ≤ 10pp 且 |PREFIX−LIVE| ≤ 10pp:合格;
- 两臂均 >10pp → **STATE-RECONSTRUCTION NOT QUALIFIED → Stage R STOP**;
- 选择:|PREFIX−LIVE| ≤ |SNAP−LIVE| + 5pp → 用 PREFIX_REPLAY,否则
  DIRECT_SNAPSHOT;R1 开始前冻结,禁止按 TEST 切换。

## 5. R1 — 前瞻队列(spec §9;零条件化)

- grid {t3,t5,t9} × seeds **121–190**(与历史池零交集),collect 序扫描;
- **进入标准**(逐条满足,全部满足才纳入):1) episode 首个失败事件
  (FG∪RPS 取最早)为 FALSE_GRASP 且发生在 nominal pi0_pick(t0≥2);
  2) 稳定失败契约(§2:失败技能全程无 acquisition 点 ∧ skill end 非
  success);3) S_pre provenance 完整(pre 快照 + t0 前动作流完整);
  4) a_fail 可冻结(t0 首 chunk 完整落盘);5) 重建方法可用(R0 已冻结);
- **禁止任何结果条件化**:重放即成功/8/8 全失败/重采全成功等一律保留
  (spec §27);"无法复现"本身就是 outcome;
- 配额:总 32 个稳定 FG 事件 = R0 DEV pilot 前 8(collect 序)+ R1 cohort
  后 24(容差:网格耗尽时 22–26 可冻结为 N,记 deviation;<22 记
  INSUFFICIENT);不设 DEV/TEST 判定分裂(R1 为刻画研究,统计单位=
  event,全部事件进总体指标)。

## 6. 双臂执行(spec §10-§13)

对 cohort 每个 case i(reconstruct = R0 冻结方法,每次尝试独立重建,
不得从上次终态续):
- **Arm A SAME-ACTION** ×K_same=8:a_fail_i(t0 首 chunk,Stage P P0 粒度,
  不重新定义)→ 冻结 continuation(hold-through,两臂逐字一致;
  continuation 随机性仅来自 Pi0.5 采样,seed 不可注入 → 由 K 吸收并记录);
- **Arm B POLICY RESAMPLE** ×K_resample=8:同 obs 语义/同 task command/
  同 grounding/同 grasp command/同权重,仅重采样 → 每次新冻结 candidate;
- **NATURAL_RETRY**(描述臂,spec §26)×K_nat=4:restore 原始 S_post 快照
  → 同 prompt 重发(fresh candidate + 同 continuation)。仅 descriptive,
  不得作 persistence 因果证据(post-state 重建只能 approximate)。

每次尝试记录:base(重建后)/post-chunk/每 continuation chunk/终态测量点
+ 双契约标签 + chunk 分类 + infra 分类。

## 7. 概率与总体指标(spec §14-§17)

- q_same(i)、q_policy(i)(stable;acquisition 陪报)+ Wilson CI;
- 总体:mean/median、event-level distribution、fraction q>0;
- **Retryability@K**(K=8):SAME/ROBUST_SAME/POLICY/ROBUST_POLICY
  (_RETRYABLE = ≥1 次 stable;ROBUST_ = ≥2 次);
- **Persistent@K**:SAME_PERSISTENT = 0/8 same;POLICY_PERSISTENT = 0/8
  resample;STRONG_PERSISTENT = 二者皆 0;措辞纪律:0/8 只写
  persistent@8,禁写"绝对不可恢复";
- 禁把 24×8 写成 N=192;bootstrap by event。

## 8. 失败持续谱(spec §18/§19;TEST 前冻结的最少成功次数规则)

| TYPE | 规则(K=8)|
|---|---|
| E EXECUTION-EPHEMERAL | same ≥2/8 stable |
| A ACTION-SPECIFIC | same=0/8 ∧ policy ≥2/8 |
| P POLICY-PERSISTENT | same=0/8 ∧ policy=0/8 |
| U UNRESOLVED | 其余(same=1,或 same=0∧policy=1)|

主报告连续 q 值 + retryability@K,TYPE 为派生描述;禁据单次成功赋
latent type。

## 9. R2 — retry 曲线(spec §21-§23;零新 rollout,复用 R1)

- C(k) = P(前 k 次内 ≥1 stable)(event-level:k=1,2,4,8 两臂分别);
- h(k) = P(第 k 次成功 | 前 k−1 次全失败)(分母 = 前 k−1 全败的事件,
  该事件第 k 次尝试);
- 饱和增益 Gain 1→2 / 2→4 / 4→8;NATURAL_RETRY 陪报不入 C(k)。

## 10. 六假设判定门(spec §31;冻结)

| 假设 | SUPPORTED | NOT_SUPPORTED |
|---|---|---|
| EPHEMERAL_FAILURES_EXIST | ≥2/24 事件 TYPE E | TYPE E = 0(否则 INCONCLUSIVE:恰 1 例)|
| ACTION_SPECIFIC_FAILURES_EXIST | ≥2 事件 TYPE A | TYPE A = 0(同上)|
| POLICY_PERSISTENT_FAILURES_EXIST | ≥2 事件 TYPE P | TYPE P = 0(同上)|
| ONE_SHOT_FAILURE_IS_INFORMATIVE | median q_policy ≤ .25 ∧ STRONG_PERSISTENT@8 占比 ≥25% | median q_policy ≥ .50 |
| RETRY_GAIN_SATURATES_EARLY | C_pol(8)−C_pol(4) ≤5pp ∧ [C_pol(4)−C_pol(2)] ≤ [C_pol(2)−C_pol(1)] | C_pol(8)−C_pol(4) >10pp |
| TRANSIENT_SUCCESS_REPLICATES | 任一臂 pooled ACQ−STABLE gap ≥15pp | 两臂 gap <5pp |

不设总 SUPPORTED 判定;每项注明 under FALSE_GRASP and current
Pi0.5/runtime。强结论门槛(spec §32):禁写 "most failures are
stochastic"(除非多数事件 same-action 反复 stable success)/ "same-action
retry is sufficient" / "persistent failures need learning"。

## 11. Infra 纪律(spec §29)

分类:prefix replay failure / snapshot failure / candidate generation
failure / continuation failure / simulator crash / physical policy
failure;infra 不进 policy denominator;formal infra >2% → 暂停解释,
只修 instrumentation/reconstruction,禁改 policy semantics。trial 级
infra ≤3 重试;事件级 >50% infra trial → 事件保留并加 flag,总体指标
报告含/不含两口径。

## 12. 统计与作图纪律(spec §30/§15)

按 event bootstrap/Wilson;q_same vs q_policy scatter、C(k) 曲线;
禁训练 embedding/clustering model 画"漂亮 cluster"。

## 13. 预算(先冻结)

| 项 | 规模 | 估时 |
|---|---|---|
| collect(3 workers) | ~130–210 eps(稳定 FG 率估 ~15–20%) | 10–16h |
| R0 资格 | 8 事件 × 3 臂 × 4 trials | ~3–4h(1–2w)|
| R1 双臂+nat | 24 × (8+8+4) trials | ~10–14h(2w)|
| R2 分析 | 零 rollout | <1h |

开发机纪律:preflight + .runlocks/stageR_*.lock + 并发 ≤3 +
nohup 日志 /workspace/yjx/tmp/stageR_*.log。

## 14. 产物(spec §34)

stageR_prereg.md(本件)、stageR_reconstruction_dev.csv、
stageR_reconstruction_decision.md、stageR_manifest.csv、
stageR_failure_events.jsonl、stageR_same_action_rollouts.csv、
stageR_resample_rollouts.csv、stageR_event_probabilities.csv、
stageR_persistence_map.csv、stageR_retry_curves.csv、
stageR_hypothesis_results.md、STAGE_R_FINAL_REPORT.md
(含 Relation to Recovery Literature 节:RoboRecover/Kintsugi-VLA/
FLARE/FAR/ReTVL,只写 "complementary measurement axis",禁称绝对
novelty;必答 Q1-Q10)。

## 15. Hard STOP(spec §36)

完成后 STOP:禁 persistent-failure recovery method / classifier /
escalation policy / adaptive retry controller / FAR-style preference
adaptation / FLARE-style recovery training / Graph / World Model /
verifier / Planner redesign / SFT / OPD / RL。Stage R 只负责
MEASURE FAILURE PERSISTENCE。

---

## 附录 A — 对齐笔记(冻结对齐,非偏离)

1. spec §7 "RGB observation / image similarity":客户端 obs 图像键在
   chunk_step 返回中被 strip(仅低维 states),采集期图像逐帧落盘成本
   高且 Stage Q 已证低维观测足以判定 → 一致性报告以低维 obs + 快照
   per-index Δ 为准,图像列为 not_available(如实记录);
2. spec §11 "如 continuation stochastic 优先 common seed schedule":
   Pi0.5 seed 不可注入(P0/J0 冻结)→ 两臂共用同一 continuation 实现
   (hold-through 逐字),随机性由 K 次重复吸收;
3. spec §26 NATURAL_RETRY:实现为 S_post 快照 restore + 同 prompt fresh
   candidate + 同 hold-through continuation(K=4,descriptive);
4. a_fail_i = t0 失败技能第一个 chunk_step 的动作数组(= 该次
   predict_action_batch(eval)输出,Stage P P0 粒度一致);
5. R1 无 DEV/TEST 分裂(刻画研究),§8/§10 全部门在 R1 首次执行前冻结。

## 附录 B — deviation 日志(只追加)

- **dev-r1-fix(2026-10-08 05:59)**:R1 首次启动(04:58)存在队列切分 bug ——
  `stageR_rt.load_events` 的 `ord` 误用 ledger 行号,而 8/24 切分依据 included
  序号,导致 manifest 32 事件全部标记 R1_COHORT、8 个 R0 DEV 事件(r09/r12)
  进入执行队列。05:01 发现后停止,实际多跑 4 个 trial(r09 SAME 1-3、
  r12 SAME 1,均为 DEV 事件,不在最终 cohort 内)。处置:修 `ord` 为 included
  序号(1..N);删除错误 manifest/events jsonl/rollouts CSV 重新冻结;
  `stageR_trial_checkpoints.jsonl` 保留 4 条越轨 trial 作审计痕迹(R2 不读)。
  对判定无影响:cohort 24 事件(r54..r185)的全部 trial 在修复后从零执行。
