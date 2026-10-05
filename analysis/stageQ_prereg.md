# Stage Q 预注册 — Why Does Retry Work?

冻结:2026-10-05 | 分支:research/pre-ovpm-20260905
规范:用户 2026-10-05 下发的 32 节 Stage Q spec(唯一权威;本文件为可执行
蒸馏,冲突处以 spec 为准并记 deviation)
纪律:confirmatory(Q1)运行前本文件 commit;TEST 后禁改;deviation 只追加
(dev-Q1 起,附录 C)。

---

## 0. 冻结结论引用(不改写)

- Stage N:information 可改变 downstream control(realization 65.3%)但
  Macro/Option 0 recovery。
- Stage O:FG 上重调 Pi0.5 grasp command 可产生真实 recovery,single-sample
  hit ≈36.7%(终态契约),H_A POLICY SUPPORT=SUPPORTED;oracle conditioning
  0/32 未解释。
- Stage P:candidate 接口 QUALIFIED([5,7] chunk 可冻结重放,transition
  48/48);P1 天花板 FAIL(TEST 9/10 首候选即恢复,O@8−O@1=+10pp<15pp,
  sup=100%),PRE-EXECUTION SELECTION NOT JUSTIFIED;P2/P3 未运行。
  **禁重启**:verifier / Best-of-K / abstention / Graph / Router / World
  Model / Planner redesign / SFT / OPD / RL(§32 全表继续有效)。

## 1. 术语纪律(spec §3)

Stage P 已证:同 frozen candidate 同 snapshot 重放存在亚毫米单向 drift
(≤7.8e-4m,restore 不含 MuJoCo contact/solver history)。因此本阶段禁写
"bit-exact identical physical state";统一使用 **OBSERVABLY MATCHED
RESTORED STATE**(读回校验逐位 + 观测量一致),除非某字段确实逐位一致。

## 2. 双 Outcome Contract(spec §4)

所有正式 rollout 同时计算两标签;**不改 Stage P 历史标签**。

- **ACQUISITION_RECOVERY** = Stage P §4 冻结 RECOVERY 标签逐字复用
  (priority RECOVERY>HARM>NO_EFFECT;任一测量点 check_success 或 FG 契约
  dz≥+0.03 ∧ dxy(obj,EEF)≤0.10,基准 = 该 rollout 自己 restore 后 base)。
- **STABLE_RECOVERY**(新):设 i* = 首个满足 ACQUISITION 条件的测量点。
  STABLE 当且仅当:i* 存在 ∧ 从 i* 到终点的**所有**测量点满足
  (check_success ∨ (dz≥0.03 ∧ dxy≤0.10))∧ 终点满足同条件 ∧
  (任一点 check_success ∨ i* 之后测量点数 ≥ HOLD_MIN_POINTS)。
  - 阈值复用 Stage P verifier 参数(FG_LIFT_DZ=0.03、FG_FOLLOW_DXY=0.10);
  - 新参数仅两个:**HOLD_MIN_POINTS**(初值 4)与 **hold-through
    continuation**(见 §10);只允许在 DEV/calibration(Q0)期修订,
    Q1 TEST 前 commit 冻结,修订记 deviation。

## 3. Q0-A — 同 boot 成对 S_pre/S_post 捕获

失败 pick 技能 = episode transcript 中 step t0 的单条 `pi0_pick` 命令
(一个 transcript step = 一个完整闭环技能,result 含 chunks_used)。

程序(每事件一次 boot,fresh env 重放,连续不 restore):
1. 重放 prefix 1..t0−1 → `save_state` = **S_pre**(失败技能首次物理执行前
   最近可恢复快照);
2. capture_state(S_pre):sim_measurement 全部低维 obs 向量(EEF/夹爪/
   object-state 全键)+ gripper opening + check_success + sim 原始
   flatten state(全长向量,per-index Δ 审计用)+ state sha16 + target 名;
3. 执行 step t0 原命令(同 kwargs;Pi0.5 重采样,J0 冻结:非确定);
4. 守卫(dev-O5 同款):该 pick result.success 必须为 False,否则
   InfraError(事件不可复现,重试至 3 次后该事件记 INFRA_ABORT);
5. `save_state` = **S_post**(FG 契约首次确认后最近快照);capture 同 2。

结构排除(非结果筛选):t0=1(无 pre-state)事件不进 Q0/Q1。
接口不可读字段(contacts per-body、per-joint qpos/qvel 标签名)如实记
not_available;flatten Δ 统计替代(n_changed/max/L2)。

## 4. Q0-B — State Difference Audit(DEV,描述性)

对每 DEV 事件:Δlabeled(EEF xyz/norm、gripper、target pos/quat/vel 如有、
check_success)+ Δflatten(S_pre vs S_post 原始向量 per-index:changed
index 数、max|Δ|、L2、时间槽差)。**只描述,禁止用于筛选 TEST 快照**。
产物 `analysis/stageQ_state_delta_audit.csv`。

## 5. Q0-C — LIVE vs RESTORED 审计(DEV)

每事件(spec §7 逐字操作化):
1. 按 §3 程序 boot(live 重放到 S_post,不 restore);
2. 从该 live S_post obs 生成并冻结 retry candidate a(1 个,pick prompt =
   Stage P pre_prompt_of);
3. **LIVE 臂 ×R_L=2**:每次 = fresh boot 重跑 §3 到 S_post(各次 S_post
   observably matched,非逐位)→ 不 restore 直接执行 a + continuation;
4. **RESTORED 臂 ×R_R=2**:restore(boot1 的 S_post 字节)→ 执行同一
   frozen a + continuation;
5. seed 不可控(vla_server,P0 冻结)→ 随机性由 R 吸收,如实记录。

比较项:transition class(Stage P §5 三类)、ACQUISITION、STABLE、
object displacement、endpoint(check_success/terminated)。

### Restore-Sensitivity Gate(§8 冻结)

pooled(全部 DEV 事件 × replicate):|ACQ_live − ACQ_restored| > 10pp
∨ |STABLE_live − STABLE_restored| > 10pp ∨ transition-class agreement
(配对执行间)< 90% → **RESTORE-SENSITIVE DYNAMICS**:Q1 照常允许运行,
但所有 restored-state 因果拆分结论只能标 APPROXIMATE / INCONCLUSIVE,
禁称精确 physics counterfactual。gate 结果落 `stageQ0_decision.md`。

## 6. Q1 — Confirmatory Dataset(§9)

- 全新 episodes:grid {t3,t5,t9} × seeds **76–120**(与 N/L/O/P 池无交集),
  顺序扫描,程序 = Stage P collect 逐字(FG-only、每 episode 至多 1 事件、
  零 LLM、零结果筛选、RPS logged-excluded);
- 目标 **20 个 FG 事件**(spec 推荐 16–24 取中;容差 18–22,越界记
  deviation);t0=1 结构排除;
- 每 event 具备:S_pre、S_post(§3 同 boot 成对程序)、genuine FG、
  valid restore(读回==0)、完整 candidate provenance(sha16 + 生成序);
- manifest 冻结(collect 序奇→DEV / 偶→TEST,Stage P 同规则)先于执行;
  TEST=confirmatory,DEV=sanity/校准(含 §2 新参修订权)。

## 7. Q1 — Candidate Sampling(§10)

每事件(执行前全部冻结,落 `stageQ_candidates.jsonl`,断点只复用不补采):
- S_pre obs → K=4:**A_pre_1..4**(生成序即冻结序);
- S_post obs → K=4:**A_post_1..4**;
- K 冻结为 4;如 DEV 校准显示 variance 过高,TEST 前可改 6/8(spec §10),
  记 deviation;TEST 后禁改。

## 8. Q1 — Factorial 执行(§11/§12)

四 cell(命名 = 候选源|执行态):**PP**=A_pre@S_pre、**PO**=A_pre@S_post、
**OP**=A_post@S_pre、**OO**=A_post@S_post。

每 cell-execution:restore(S_x)→ 读回校验 → base 测量 → 执行 frozen
chunk(零模型调用)→ 每 candidate 独立 **R_Q=2** 次 continuation
(S_j = post-chunk 态,同 Stage P 机制;从 S_j restore 出发)。
continuation 语义四 cell 完全一致(§2 hold-through)。统计单位 =
failure event;continuation replicate 是嵌重复,禁当独立事件。

**A_fail probe(§13,descriptive)**:原始失败技能的 first chunk 未按
chunk 粒度落盘于 transcript(states.json 只记 skill 级 result)→ 记
NOT_RECOVERABLE,不执行;不进任何 gate。

## 9. Continuation Contract(hold-through,冻结)

= Stage P run_continuation 逐字,**唯一差异:success-latch 早停禁用**
(descent∧ascent∧grip 不再 break;仅 env termination/truncation 或
PICK_MAX_CHUNKS=24 预算止步)。目的:STABLE 窗口 = 首中后剩余预算全程,
统一作用于四 cell 与 LIVE/RESTORED 臂。该差异是 §2 新参之一,Q0 期可修
订、Q1 TEST 前 commit 冻结。

## 10. Q1 — 效应与门(§14-§17;TEST,per-snapshot paired)

对 ACQUISITION 与 STABLE 分别计算(单位 = event,cell 值 = 该 event 内
candidate×replicate 的恢复率):

- **EXECUTION-STATE EFFECT** = mean_cand[同 candidate@S_post − @S_pre]
  (PO+OO 与 PP+OP 的配对差);H_QB gate:≥15pp 且非单事件驱动(去任一
  event 后仍 ≥15pp)。
- **CANDIDATE-SOURCE EFFECT** = mean[A_post − A_pre @ 同执行态]
  (OP+OO 与 PP+PO);H_QC gate:≥15pp 且非单事件驱动。
- **INTERACTION** = (OO−OP)−(PO−PP);H_QD gate:≥15pp 且去任一 event
  后仍 >0。
- **H_QA STOCHASTIC RESAMPLING**:PP STABLE 在多事件稳定出现(冻结:
  ≥70% TEST 事件 PP stable>0)∧ |OO_STABLE − PP_STABLE| ≤ 10pp。
- **TRANSIENT_GAP** = ACQUISITION − STABLE,分四 cell 报告;平均 gap
  ≥15pp → H_QE 机制性重要(TEST 前冻结本值,沿用 spec 建议 15pp)。

CI:bootstrap by snapshot(10k 重采样,percentile);所有比例附 Wilson CI。

## 11. Q2(条件触发,§20-§24)

仅当 H_QB SUPPORTED(或 exec-state ≥15pp)才运行,否则 Q2 不运行。
四态 S00/S10/S01/S11(robot|object,pre/post);candidate 只用冻结 bank
(Q1 A_post bank 或 S11 生成后冻结,禁每态重采);每 hybrid 态先过
validity 检查(penetration/joint config/explosive contact/passive drift/
task-valid/predicate 未被构造直接满足),**validity<90% → STOP:
NOT IDENTIFIABLE WITH CURRENT SIM STATE INTERVENTION**。解释分支按
spec §24;禁强行归因。

## 12. Hidden dynamics 措辞(§25)

LIVE>RESTORED 或 Q1 state effect 无法由 Q2 observable state 解释 →
只写 "UNOBSERVED / CONTACT-HISTORY DYNAMICS MAY CONTRIBUTE";禁改
simulator snapshot format 后继续同一 confirmatory TEST(需另立阶段)。

## 13. 预算与模型(§26 冻结)

- 不调用 Planner/Graph/Memory routing/WM/verifier selection;模型仅
  frozen Pi0.5 + 物理 verifier(全 sim 级确定性测量);
- Q0-B:12 DEV 事件 ×1 boot ≈ 3h;Q0-C:8 DEV 事件 ×(2 live boot +
  4 exec×~7min)≈ 6-8h;Q1 collect:~70-100 eps ≈ 6-9h(3 workers);
  Q1 factorial:20 事件 ×16 cell-exec ×R=2 ≈ 20-30h(2 workers);
- 开发机纪律:preflight + .runlocks/stageQ_*.lock + 并发≤3 + nohup 日志
  /workspace/yjx/tmp/stageQ_*.log;超 1h 高负载任务仅此调试规模。

## 14. Infra 纪律(§27)

分类记录:snapshot failure / candidate generation failure / candidate
replay failure / continuation failure / simulator failure / physical
failure;正式 batch infra >2% → 暂停解释,只修 instrumentation,禁改
candidate 定义 / outcome contract / state construction semantics。

## 15. 产物清单(§29)

stageQ_prereg.md(本件)、stageQ_state_delta_audit.csv、
stageQ_live_restore_audit.csv、stageQ0_decision.md、
stageQ_split_manifest.csv、stageQ_candidates.jsonl、
stageQ_factorial_rollouts.csv、stageQ_acquisition_stable.csv、
stageQ_factorial_effects.csv、stageQ1_results.md、stageQ1_decision.md、
(如 Q2)stageQ_hybrid_state_validation.csv / stageQ_hybrid_rollouts.csv /
stageQ_state_component_effects.csv / stageQ2_results.md、
STAGE_Q_FINAL_REPORT.md。

## 16. 终报与 Hard STOP(§30-§32)

终报必答 Q1-Q10(spec §30 原文);六判定独立输出:STOCHASTIC_RESAMPLING /
PHYSICAL_PRECONDITIONING / POST_STATE_CONDITIONING /
STATE_ACTION_INTERACTION / TRANSIENT_SUCCESS / HIDDEN_DYNAMICS_EFFECT,
禁总体 "Stage Q works"。完成后 STOP,禁自动:retry controller redesign /
adaptive retry count / verifier / Best-of-K / Planner fallback / Graph /
World Model / new perception / SFT / OPD / RL / simulator snapshot redesign。
分支语义按 spec §32 逐字。

---

## 附录 A — spec 与实现的对齐笔记(冻结对齐,非偏离)

1. spec §5 S_pre 定义"原失败 grasp skill 第一次物理执行之前" → 实现 =
   重放 1..t0−1(transcript 一个 step = 一个完整闭环技能,故 t0 步前即
   技能首 chunk 前);
2. spec §7 LIVE 臂"不 restore 直接执行 a" → 每次 LIVE replicate 用 fresh
   replay boot(重放含 Pi0.5 重采样,各次 S_post observably matched 但非
   逐位;符合 §1 措辞纪律),第 1 次即 boot1 的连续执行;
3. spec §4 STABLE "hold/lift/continuation window" → 实现为 hold-through
   continuation 的剩余预算全程 + HOLD_MIN_POINTS 下限(§2/§9);
4. spec §13 A_fail → transcript 无 chunk 级动作,NOT_RECOVERABLE(§8)。

## 附录 B — 预算账(先冻结)

| 项 | 规模 | 估时(含 boot) |
|---|---|---|
| Q0-B | 12 DEV × 1 boot + capture | ~3h |
| Q0-C | 8 DEV ×(2 live boot + 4 exec×R=2) | ~6-8h |
| Q1 collect | ~70-100 eps(FG 率~29% 取 20) | ~6-9h(3w) |
| Q1 freeze | 20 事件物化+划分 | ~2h |
| Q1 factorial | 20 × 16 exec × R=2 | ~20-30h(2w) |
| Q2(如触发) | 16-20 事件 × 4 态 × bank 执行 | 另账 |

## 附录 C — deviation 记录(只追加)

(dev-Q 起编号;空 = 无)
