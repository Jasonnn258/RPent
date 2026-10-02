# Stage O 预注册 — Recovery Source Audit(O-B confirmatory 冻结版)

日期冻结:2026-10-02 | 依据:用户 39 节规范(本文件逐节落实 §35 要求冻结的全部条目)
**本文件 commit 后、正式 TEST(O-B ladder)开始前,只允许追加「calibration 附录」;
TEST 开始后禁止修改。任何 deviation 只能追加记录,不得改写已冻结条目。**

---

## 0. 冻结的已有结论(不重开)

H(graph-as-advice NOT SUPPORTED)、I0(router FAIL)、J0(snapshot/restore 可用、
Pi0.5 stochastic、单 rollout 反事实不成立)、K(WM NOT JUSTIFIED)、
L(evolution NOT SUPPORTED)、M(gate FAIL 87.9%)、N(N0 PASS;N1 M 0/72、O 0/72、
realized 65.3%、rescue 0;24 快照 23 个源 episode 可恢复)。
禁止提前得出 "Pi0.5 缺乏 recovery skill"(五种来源未区分)。

## 1. 研究问题与主输出

R(s; policy, conditioning, horizon, replanning):从 failure snapshot s 出发,
给定 policy / conditioning / action budget / planning regime 下达到 recovery 的概率。

主输出 = 逐 snapshot 的 FIRST_RECOVERY_SOURCE(非 leaderboard,禁"O4 比 O1 强"式总结):
`O1_POLICY_SUPPORT / O2_CONDITIONING / O3_FIXED_SEQUENCE / O4_REPLANNING /
OX_EXPERT_ONLY / NO_SOURCE_FOUND / REFERENCE_UNAVAILABLE`,
以及 FIRST_REENTRY_SOURCE、FIRST_TASK_RECOVERY_SOURCE(§27)。

O-A(已完成,commit 63041e5)只作理解与 arm 构造参考,不作 confirmatory 证据。

## 2. 术语与栈冻结

- **Full Planner(本阶段唯一定义)**:`rpent --env libero --planner api
  --model anthropic:glm-5.3-flash --base-url https://open.bigmodel.cn/api/anthropic
  --max-turns 40`,默认 toolkit(全原语集 move_to / pi0_pick / pi0_doubled /
  set_gripper / release / rotate_wrist / rotate_pitch / move_pose + 感知
  segment / back_project / view_driver_state 等),默认 memory 配置(不设任何
  ovpm 实验环境变量)。采集、reference、O4 使用**同一**栈。
- **failure family(沿用 Stage N 冻结契约,逐字)**:
  - `FALSE_GRASP`(P2):t0 步 command.action == `pi0_pick` 且 result.success == False;
  - `RELEASE_PREDICATE_STALL`(P1):t0 步 command.action == `release` 且
    result.libero_terminated == False;
  - 附带:1..t0 每步均有 command(重放完整性)。
- **快照仪器(沿用 J0/N1)**:fresh env 重放 prefix 1..t0(含 t0)→
  `S = env.save_state()`;每次 rollout 前 `restore_state(S)+set_obs`,
  读回 `save_state()` 与 S 逐位比对必须 == 0.0,否则 INFRA。
- **随机性说明(J0 冻结)**:Pi0.5 采样不可经 vla_server 注入 seed,同 obs
  采样本身随机。§8/§24 的 "固定 seed 顺序 / common seed sets" 操作化为:
  **冻结的 attempt 顺序**(ref_1..ref_K_REF;rollout r=0..K-1),各臂同 idx
  attempt 从同一 readback-verified 状态出发。此操作化在 prereg 冻结。
- 环境:MUJOCO_GL=osmesa、PYOPENGL_PLATFORM=osmesa 显式覆盖、unset
  MUJOCO_EGL_DEVICE_ID / LIBGL_ALWAYS_SOFTWARE、OPENPI_DATA_HOME=
  /workspace/yjx/rpent_data/.cache/openpi(N1 教训,缺一不可)。

## 3. O-B 快照集(§7)

- **配额**:16 个新快照(8 FALSE_GRASP + 8 RELEASE_PREDICATE_STALL),
  容差 12–18;grid 扫尽仍 <12 或任一族 <5 → 停,报 INSUFFICIENT_SNAPSHOTS。
- **采集方式**:对候选 task×seed 逐个跑完整 Full Planner episode(max-turns 40,
  顺序见下);episode 结束后按 §2 契约确定性判定:沿 step 升序**第一个**满足
  family 契约的步为 t0、该 episode 的 family(每 episode 至多 1 快照)。
  无合格事件的 episode 记 logged-excluded(计入采集账,不进 manifest)。
- **隔离**:task×seed 排除集 = Stage N 池 ∪ Stage L split 池的并集(冻结清单
  见附录 A);候选 grid = {t3,t5,t9} × seeds {13,14,15,16,17,18,19,21,22,23,
  24,25} − 排除集(实际可用 30 格,附录 A),**扫描顺序冻结为 task 主序
  (3→5→9)、seed 升序**(FG 集中在 t3,满足 "FALSE_GRASP 优先")。
- 快照不得用于 arm design;不得在查看任何 O-B 结果后筛选(采集判定规则
  本节已冻结,先于任何 rollout)。
- 产物:`analysis/stageO_split_manifest.csv`
  (snapshot_id, family, procedure, task, seed, t0, episode_dir, event_rule,
  collect_ts, state_len, eef0, pos0_json, check_success_at_t0),写完后
  sha256 冻结入头注释 + commit。

## 4. Full Planner reference traces(§8)

- 每个快照:按冻结顺序 ref_1→ref_3 从 restore(s) 起 Full Planner 续跑,
  **K_REF = 3**(上限;第 1 个成功即停,禁止挑拣)。
- reference 成功 := 续跑内任一 checkpoint 满足该 family 的 TASK_RECOVERY 契约
  (§5)**或** env.check_success() == True。
- 全部失败 → `REFERENCE_UNAVAILABLE`:该快照仍跑 O0/O1/O4,不得用于
  O2/O3 归因;单独报告。
- 续跑机制(与 O4 完全同一代码路径):restore(s) 后起 planner 循环,
  user message = 冻结模板(§8.1)。
- 产物:`analysis/stageO_reference_traces.jsonl`
  {snapshot_id, attempt_idx, success, contract_met, ended_by, steps:[…],
  wall_s}。

### 8.1 冻结的续跑 prompt 模板(reference 与 O4 共用,逐字)

```
{episode 原始任务 user prompt 原文}

[RESUME CONTEXT]
You are resuming this same task mid-episode. Below is the verbatim action
log so far (commands and results exactly as recorded):
step 1: ACTION <action> ARGS <kwargs json> -> RESULT <result json,图片剥离>
...
step {t0}: ...
[END OF LOG]
The robot is now exactly in the state right after step {t0}. Continue the
task from here.
```

(信息来源仅为 episode 自身 prefix 记录,无 future 信息、无人为改写。)

## 5. 两种 Recovery 结局契约(§9,全部 sim 级确定性测量)

checkpoint 采样:每个动作原语执行后 + rollout 结束时各测一次 `sim_measurement`
+ `check_success`。

### 5.1 TASK_RECOVERY(failure-specific 物理契约)

- **FALSE_GRASP**:`object lifted AND follows EEF` 操作化为同一 checkpoint 上
  (a) 目标物 z − z(t0) ≥ +0.03 m(抬起)且 (b) 目标物 xy 距 EEF xy ≤ 0.10 m
  (跟随);目标物 = obj_of_interest[0](N1 同源口径)。
  附加通过路径:该 checkpoint check_success() == True。
- **RELEASE_PREDICATE_STALL**:任一 checkpoint `libero_terminated == True`
  或 `check_success() == True`(该族失败即"放置谓词未触发",恢复 = 任务推进)。

### 5.2 POLICY_REENTRY(observable contract,两族通用)

静态层(rollout 终态测量,全部满足):
- RE1 目标可重定位:probe `segment(prompt=t0 族的 target prompt)` found 且
  score ≥ 0.30(FG 用 t0 pick prompt;RPS 用 prefix 内最后一个 pick/doubled
  prompt;无则 RE1=False);
- RE2 机器人位姿合法:EEF ∈ x(−0.60,0.35) y(−0.45,0.50) z(0.80,1.35) m
  且有限(依据:N 池实测包络 x[−0.395,0.110] y[−0.208,0.249] z[0.918,1.173],
  各向外放 ≥0.15 m);
- RE3 物体构型无害:目标物 dz > −0.03 m 且 dxy ≤ 0.08 m(N1 harm 反向),
  且全部物体 z ≥ 0.80 m(未离桌/未压入)。

动态层(静态层全过才跑,≤3 原语,与臂无关的固定 nominal probe,用 episode
自身 prefix 条件、无 oracle):
- FG probe:`pi0_pick(prompt = t0 prompt 原文)`;verified := 契约 5.1-FG 在
  probe 内成立;
- RPS probe:`pi0_doubled(prompt = prefix 内最后一个 pick/doubled prompt 原文)`;
  verified := 契约 5.1-RPS 在 probe 内成立。

REENTRY := 静态层 ∧ 动态层。probe 在 rollout 全部测量完成后执行
(不污染 TASK_RECOVERY);probe 后状态废弃(下一 rollout 前重新 restore)。
禁止凭"看起来正常"判 reentry。

## 6. Arms(§10–§21)

所有臂共享:同 snapshot(readback==0)、同原语接口、同 checkpoint 测量、
同 REENTRY probe。动作原语计数不含感知(segment/back_project/view_*,与 N1 同)。

- **O0 — CURRENT LOCAL RECOVERY(N1 O-policy 逐字移植)**:按 family 走
  stageN1_runner 的 policy_P1 / policy_P2(R1 termination / R2 carry /
  R3 re-segment+prepos+retry),预算同 N1(5 动作、pick ≤ 2)。不加任何
  skill/prompt/observation/replanning/verifier。
- **O1 — POLICY RESAMPLING**:统一冻结规则——重放确定 **step ≤ t0 的最后一条
  Pi0.5 族命令(pi0_pick / pi0_doubled)**,逐字重执行(action、prompt、全部
  kwargs 原文),从 restore(s) 起 **N_MAX = 16 次独立采样**(每次先 restore,
  禁链式);sampling checkpoints {1,4,8,16} 报 best_of_N;运行时禁止用任何
  verifier 挑 candidate。
- **O2 — ORACLE CONDITIONING(诊断臂)**:与 O1 唯一差异 = conditioning:
  重放对象同 O1(最后一条 Pi0.5 族命令),但其 prompt(若为 move_to 类则
  xyz)替换为该快照冻结 reference trace 中 **ref 成功点之前第一条同族
  (pi0_pick↔pi0_pick / pi0_doubled↔pi0_doubled)调用的参数原文**;
  reference 无同族 → 用 reference 第一条 Pi0.5 族调用(记录)。
  其余 kwargs 不变;采样数同 O1(16);记录 `oracle_conditioning_source_step`
  与该信息在 reference 中的首次出现 turn。禁 future hidden state /
  事后改写 prompt。REFERENCE_UNAVAILABLE 快照不跑 O2。
- **O3 — FROZEN ORACLE SEQUENCE(诊断臂)**:从冻结 reference trace 抽
  高层序列 = 成功点(不含)之前全部动作步的 (action, kwargs) 原文(含
  move_to xyz / prompt;**禁止** replay 低层连续动作——本栈原语本身即技能级,
  每个技能按其正常 closed-loop 语义执行)。episode 开始前整序列冻结;执行中
  禁改序 / 插入 / 删除 / replan / 据中间失败重生成;rollout 终止于序列耗尽 /
  预算耗尽 / TASK_RECOVERY 契约命中(测量性终止)/ env 终止。
- **O4 — RECEDING-HORIZON REPLANNING**:restore(s) + §8.1 模板起 Full
  Planner 循环;相对 O3 唯一新增 = state-dependent sequence-level replanning
  (planner 本性)。预算与 O3 完全一致(§7 预算表)。
  每 planner turn 记录(§22):observation summary / current grounding /
  current subgoal / previous subgoal / subgoal changed / reason / next skill;
  并记录 O4 动作族序列相对该快照 O3 冻结序列的**首次偏离**(turn、双方
  动作族、可观察证据)→ `stageO_arm_transitions.jsonl`。
- **OX — EXPERT CHECK**:仅当 O1≈0 ∧ O2≈0 ∧ O3≈0 ∧ O4≈0 才**手动**决定;
  只用已有 deterministic analytic action / scripted controller
  (如 N1 式 release+重抓宏),禁训新 policy;不自动运行。

## 7. 预算(§20/§33,防 budget confound)

| 项 | O0 | O1 | O2 | O3 | O4 |
|---|---|---|---|---|---|
| 动作原语上限 | 5(N1 冻结) | 单技能(+内部 chunk 语义) | 同 O1 | **12** | **12** |
| Pi0.5 技能调用上限 | 2(N1) | 1/样本 | 1/样本 | **6** | **6** |
| planner turns | — | — | — | — | **16** |
| wall-time / rollout | 600s | 300s/样本 | 300s/样本 | **1200s** | **1200s** |
| 重复次数 | K_ROLLOUT | N_MAX=16 | 16 | K_ROLLOUT | K_ROLLOUT |

预算依据(O-A 实测,23 个恢复 case):prims-to-recovery 中位 3 / p90 7 /
max 9 → 12;turns-to-recovery p90 11 / max 14 → 16;pi0 技能数保守 6。
O3/O4 逐项相同;O1/O2 结构性单技能,如实报告 consumed budget(§20)。
O3/O4 执行器预算耗尽 = 该 rollout 以当前状态进入测量并终止
(计数器在每次 toolkit 动作调用前检查;超限调用不再执行)。
全程记录 primitive calls / Pi0.5 calls / planner calls / wall time。
任何比较若无法干净匹配 → 标 CONFOUNDED,不做强机制结论。

## 8. K_ROLLOUT 校准(§24;在 N 池上,先于 TEST 冻结)

- 校准子集(冻结规则):Stage N 24 快照中按 snapshot_id 升序前 3 个 FG +
  前 3 个 RPS = 6 个(N 池已排除出 O-B,合法)。脚本读
  stageN1_split_manifest.csv 生成,选择规则先于结果冻结。
- 校准内容:每快照跑 O1 式单技能独立采样 16 次(只测 TASK_RECOVERY 契约),
  得 per-snapshot p̂(16);bootstrap(1000 重抽,seed=20261002)比较
  K∈{4,6,8} 的 p̂(K) 与 p̂(2K) 的中位偏差。
- **冻结选择规则**:取满足 median|p̂(K)−p̂(2K)| ≤ 0.10 的最小 K;
  无一满足或数据退化(全部 p̂=0 或 1)→ K_ROLLOUT = 8(spec 建议默认)。
- 校准结果与选定的 K_ROLLOUT 追加写入附录 B 并 commit——**先于任何
  confirmatory rollout**;此后禁改。校准同时充当 runner 集成冒烟。

## 9. RECOVERY_PRESENT(§26,confirmatory 前冻结)

对每 arm × snapshot(该 arm 的全预注册 rollout 集上,n = K_ROLLOUT
(O0/O3/O4)或 16(O1/O2)):

```
RECOVERY_PRESENT := successes ≥ max(2, ceil(0.25 × n))   且 rate ≥ 25%
```

(即 K=8 时 ≥2 次、n=16 时 ≥4 次;spec 建议形式。)
每个判定附 Wilson 95% CI。非 efficacy benchmark,无 10pp/15pp 门。
分别对 TASK_RECOVERY 与 POLICY_REENTRY 两结局各自判定。

## 10. Sequential ladder(§25,冻结执行序)

每 snapshot 先 O0、O1;O1 达 RECOVERY_PRESENT(TASK_RECOVERY 结局为主判,
reentry 结局平行记录)→ FIRST_RECOVERY_SOURCE = O1_POLICY_SUPPORT
(随机抽 25% 快照(seed=20261002)继续 O2–O4 作 sanity,不改标签);
否则 O2 → 达标即 O2_CONDITIONING;否则 O3 → O3_FIXED_SEQUENCE;否则 O4 →
O4_REPLANNING;全不达标 → NO_SOURCE_FOUND(若 OX 后续手动成功:
OX_EXPERT_ONLY)。REFERENCE_UNAVAILABLE 快照跳过 O2/O3,仍跑 O4;
若其 O4 达标,标签记 `O4_REPLANNING_BELOW_UNTESTED`(H_B/H_C 对该快照
INCONCLUSIVE)。全臂零成功的快照才允许(人工决定)考虑 OX。

## 11. 指标与判定(§28–§30,§38)

- Primary:P(O1 first) / P(O2 first) / P(O3 first) / P(O4 first) /
  P(no source),task-recovery 版与 policy-reentry 版分别统计
  (REFERENCE_UNAVAILABLE 单列)。
- 增量(机制定位,非 leaderboard):Δ01 / Δ12 / Δ23 / Δ34,paired by
  snapshot(R = 各 arm 自身 rollout 集成功率;O1/O2 为 16 样本率)。
- REALIGNMENT_FIRST(§31):每条成功 rollout 记 rollout 内**首个动作族**:
  ∈{realign(rotate_*)} 或首条 move_to 目标距失败技能目标 ≥ 0.05 m 或
  z ≥ eef0_z+0.05 → REALIGNMENT_FIRST;否则 DIRECT_COMPLETION。
  报 O4 成功 rollout 与 reference trace 的 REALIGNMENT_FIRST rate;
  若 reentry 显著早于 task recovery,须讨论 recovery target 是否应为
  policy reentry(§31)。
- 假设判定(独立,禁总 PASS/FAIL,禁多数 vote):
  - H_A POLICY SUPPORT:SUPPORTED 当 ≥3 个独立快照 O1 RECOVERY_PRESENT
    且 O1 明显优于 O0(配对 Δ01 > 0 的快照占多数且无反向主导);
  - H_B CONDITIONING:SUPPORTED 当 O1 不达标但 O2 在 ≥3 个独立快照
    RECOVERY_PRESENT;
  - H_C SEQUENCE:SUPPORTED 当 O2 不足但 O3 在 ≥3 个独立快照达标,
    无需 sequence-level replanning;
  - H_D REPLANNING:SUPPORTED 当 O3 不足但 matched-budget O4 在 ≥3 个
    独立快照达标,且成功 rollout 中存在真实 state-dependent subgoal/sequence
    变化(arm_transitions 证据);
  - H_E SKILL DEFICIT:仅当 O1/O2/O3 全 FAIL(最好 OX 成功)才可写
    "evidence supports";仅凭 N1 0/144 不构成证据。
  - 各附 supporting snapshots / counterexamples / confidence 与样本限制;
    不满足 SUPPORTED 条件且非全 FAIL → NOT SUPPORTED 或 INCONCLUSIVE
    (逐假设说明理由)。
- O2/O3 为 diagnostic oracle:成功只说明该信息/sequence 解释部分 gap,
  禁称 deployable(§32)。

## 12. Infra 与偏差纪律(§34–§35)

- INFRA(不计 recovery failure):restore 读回 ≠0、vla/sam3 健康失败、
  API timeout / 5xx、重放异常、日志不一致。≤3 次重试;仍败记
  INFRA_ABORT 行(保留在 CSV,分析过滤)。
- confirmatory batch 整体 infra error rate < 2%,否则暂停解释、先修基建,
  禁改 policy semantics;修复仅限不改变 policy behavior/labels 的
  instrumentation bug,逐条记 deviation(编号续 Stage N 之后:dev-O1 起)。
- 原始 episode 日志(transcript/states/videos)不 commit;只 commit
  manifest/CSV/MD/jsonl 汇总产物。

## 13. 执行与资源纪律

- 一切入口先 `/workspace/yjx/bin/dev_preflight.sh`;锁
  `/workspace/yjx/.runlocks/stageO_*.lock`;并发 ≤4(采集/reference/ladder
  各自的快照级 worker);产出只写 /workspace/yjx。
- 预算账(先冻结):采集 ≤30 episodes(≈35 min/集)、reference ≤16×3、
  ladder 每快照 ≈ O0 8 + O1 16 + O2 16 + O3 K + O4 K 次 rollout。
  预计总墙钟 2–3 天(≤4 并发);超限先报告再继续。

## 14. 产物清单(§36)

analysis/ 下:stageO_prereg.md(本文件)、stageO_offline_recovery_audit.csv/.md
(已完成)、stageO_split_manifest.csv、stageO_reference_traces.jsonl、
stageO_rollouts.csv、stageO_arm_transitions.jsonl、stageO_reentry_results.csv、
stageO_first_source.csv、stageO_hypothesis_results.md、STAGE_O_FINAL_REPORT.md
(必答 Q1–Q10)、(如运行 OX)stageO_expert_check.csv。
脚本:scripts/stageO_collect.py、stageO_reference.py、stageO_ladder.py、
stageO_calibrate.py、stageO_analyze.py(均先 commit 再跑 confirmatory)。

## 15. Hard STOP(§39)

Stage O 完成后 STOP:禁自动训练 recovery VLA / SFT / OPD / RL / World Model /
Graph evolution / LLM Router / verifier / 新感知模型 / full sampling system /
reset policy / planner redesign。必须先汇报 "Full Planner 的 recovery
capability 到底来自哪里",再由用户决定下一条研究线。

---

## 附录 A — 排除集与候选 grid(冻结)

排除集(N 池 ∪ L split 池的 task×seed 并集):
- t3:1–12, 19, 20 | t5:2–5, 7–10, 12, 13, 18 | t9:1–10, 12, 15, 16, 17, 20

候选 grid(task 主序 3→5→9,seed 升序;共 30 格):
- t3:13,14,15,16,17,18,21,22,23,24,25
- t5:14,15,16,17,19,21,22,23,24,25
- t9:13,14,18,19,21,22,23,24,25

**预运行修订(2026-10-02,TEST 前零运行)**:为对冲 RPS 事件率不确定导致
配额不满,grid 扩至 seeds 13–28 窗口 = **13–18, 21–28**(19/20 不入窗),
再扣除排除集:t3:13–18,21–28(**14 格**);t5:14–17,21–28(**12 格**,
13/18 被排除);t9:13,14,18,21–28(**11 格**,15/16/17 被排除);
**共 37 格**(= stageO_collect.py 冻结 GRID;此前本文误写 41 格并在
t5/t9 行列入不存在的 seed 19,见附录 C dev-O1)。扫描顺序与配额规则不变。

**族配额分配规则(冻结)**:每 episode 确定性检测 FG_first(首个
pi0_pick success==False 步)与 RPS_first(首个 release terminated==False 步);
配额均开放时,取事件在 episode 内更早者(并列取 FG);仅一族开放时取该族
事件(无则该 episode 记 logged-excluded);两配额满即停。episode 最终
success/fail 不参与筛选(禁结果筛选)。

## 附录 B — K_ROLLOUT 校准结果(TEST 前追加 + commit)

运行 2026-10-02 06:31 完成(脚本 scripts/stageO_calibrate.py,完整记录
analysis/stageO_calibration.md)。校准子集(N 池前 3 FG + 前 3 RPS):
snap_00/01/06(FG)、snap_02/03/04(RPS)。每快照 O1 式独立采样 16 次。

| snapshot | family | action | prompt | k/16 | p̂(16) |
|---|---|---|---|---|---|
| snap_00 | FALSE_GRASP | pi0_pick | pick up the bowl on the stove | 0/16 | 0.000 |
| snap_01 | FALSE_GRASP | pi0_pick | pick up the black bowl | 0/16 | 0.000 |
| snap_06 | FALSE_GRASP | pi0_pick | pick up the black bowl on the cookie box | 0/16 | 0.000 |
| snap_02 | RELEASE_PREDICATE_STALL | pi0_pick | pick up the bowl on the stove | 0/16 | 0.000 |
| snap_03 | RELEASE_PREDICATE_STALL | pi0_pick | pick up the black patterned bowl | 0/16 | 0.000 |
| snap_04 | RELEASE_PREDICATE_STALL | pi0_pick | pick up the black patterned bowl | 0/16 | 0.000 |

稳定性 median|p̂(K)−p̂(2K)|:K=4/6/8 全 0.000(全零平台)。
数据退化(六快照 p̂ 全 0)→ 冻结规则第三分支:

**K_ROLLOUT = 8**(spec 建议默认;bootstrap 95% CI 全 [0,0],
seed=20261002)。此处冻结,此后禁改。

## 附录 C — 预运行修订与澄清(dev-O1..dev-O4,TEST 前,零 confirmatory 数据)

§35 允许 confirmatory 前修订冻结件(须完整记录)。以下四条均在任何
ladder rollout 之前落盘;当时已运行的部分 = §7 采集(非 confirmatory)
与 §8 校准(在 N 池上,非 O-B 数据)。

- **dev-O1(附录 A grid 枚举勘误)**:修订前文本写"共 41 格"且 t5/t9 行
  含 seed 19——19 不在冻结窗口(13–18, 21–28)内,41 为笔误加总。
  实际冻结 grid(stageO_collect.py 自始未变)= 37 格(14+12+11)。
  已采集格(t3 s13–16)在两种枚举下一致,零数据影响。
- **dev-O2(O3 序列域 = 含达成动作)**:§6 O3"成功点(不含)之前全部
  动作步"操作化为 reference `steps[:contract_at_step]`(**含**契约命中
  的那一步;无中途 latch 而 check_success 收尾的 trace 取全量动作步;
  latch 后的 skipped 步天然不在域内)。理由:若排除达成动作,O3 在
  reference 成功的每一步都定义性缺最后一步、结构性失败,违背 §6 O3
  "冻结序列是否承载恢复能力"的检验目的,§27 Δ23/Δ34 也要求 O3 可达
  成功。"不含"解释为:成功点本身(测量事件)不是序列元素。
- **dev-O3(全臂采集范围)**:除 §10 明文的例外(O1 达标且非 25% sanity
  子集的快照停在 O1),其余快照跑**全部**可用臂(O0/O1 恒跑;reference
  可用加 O2/O3;O4 恒跑),即 §13 预算行的每快照 O0 8 + O1 16 + O2 16
  + O3 K + O4 K。理由:§27-28 的 Δ01/Δ12/Δ23/Δ34 paired-by-snapshot
  要求同一快照上各臂成功率;§10 的 sequential 结构用于**定标签**
  (FIRST_RECOVERY_SOURCE),不截断数据采集。
- **dev-O4(reference attempt 与 O4 rollout 独立 boot/instrumentation)**:
  每次 reference attempt 与每次 O4 rollout 都单独 boot(独立 output
  directory,states.json 只含本 run 的 1..t0 重放步)。理由:planner
  可读 `states.json`(system prompt 明示);共用目录会让第 k 次 run
  看到前序 run 的步(额外信息,违反 §32-33 干净比较)。不改任何 policy
  语义,只改运行目录布局;O4 与 reference 同构(同一续跑代码路径)。

## 附录 C-2 — dev-O5(重放有效性与 hash 断言修正;2026-10-02,
## reference 首次启动后 4 快照全 INFRA 时发现;当时零有效 confirmatory 数据)

**现象**:reference 首启 12 快照中前 4 个连续 3×INFRA:"state hash
mismatch: replay X != manifest Y",且同快照三次重试 hash 互不相同。

**根因(两条,均为 instrumentation 层,prereg 冻结件本身无错)**:

1. *跨 boot hash 相等结构性不可达*:prefix 1..t0 含 Pi0.5 技能(FG 的
   t0 即 pi0_pick;RPS 的 prefix 含 pick),重放 = 重新采样,而 J0 已冻结
   "Pi0.5 同 obs 推断非确定"→ 每次重放产生不同轨迹与 save_state 字节。
   实现里 stageO_reference/stageO_ladder 自加的"重放 hash 必须等于
   manifest state_sha16"断言超出 prereg §2 的冻结仪器(§2 只要求
   **boot 内** restore 读回 == 0.0,该检查保留且始终通过)。修正 =
   删除该断言;state_len 结构校验(=92)保留;manifest state_sha16 降级
   为 freeze 时指纹(provenance)。
2. *家族事件在重放中不复现 → boot 无效*:freeze 取证(logs/stageO_freeze
   各 states.json 的 t0 步结果)显示 12 快照中 5 个的 freeze 重放未复现
   定义性事件——osnap_01/02 重放 t0 pick **成功**(success=True,osnap_02
   还 terminated=True);osnap_08/09/11 重放 t0 release **触发了谓词**
   (libero_terminated=True)。这些 freeze 状态不是失败态;若不设防,
   后续 boot 也会以一定概率抽到"事件不复现"的重放,此时 base 已(可能)
   满足 §5.1 契约 → 所有臂平凡通过,污染 recovery 测量。
   init 取证(scripts/stageO_init_check.py,t0=0 不重放;证据 =
   analysis/stageO_init_check.json):**12/12 init check_success=False**
   → manifest 中 4 个 check_success_at_t0=True(02/08/09/11)均为单次
   重放抽样的运气,非确定性退化 → 无快照需要剔除,全部 12 个保留,
   有效性由逐 boot 守卫保证。

**修正(instrumentation,不改任何臂语义/预算/契约)**:

- `rt.boot_snapshot(validate_event=True)` 新增 boot 有效性守卫,违反者
  抛 InfraError(§12 infra,调用方 ≤3 重试):①重放的 t0 步结果必须复现
  家族事件(FG:success 非 True;RPS:libero_terminated 非 True);
  ②base check_success 必须为 False(否则 §5.1 附加通过路径平凡成立)。
  各臂(含 reference/O4)从"事件复现"的同一条件下测量,conditioning
  一致、无偏。
- 若某快照始终抽不到有效 boot(3×INFRA)→ 各臂记 INFRA_ABORT 行,
  分析层标 NO_VALID_BOOT 单列(不入分布/门);init 退化(本次为空集,
  机制保留)标 ALREADY_RECOVERED_AT_INIT 单列。
- 已污染的 stageO_reference_traces.jsonl 头 4 行(纯 hash 断言失败的
  infra_abort 行,零有效 attempt)截断后重启 reference;该文件不含任何
  有效数据,截断不损失信息。

**时间戳**:发现于 2026-10-02 09:27(reference 首启后 2 分钟),修复
commit 先于 reference 重启;期间零有效 confirmatory rollout、零有效
reference attempt 落盘。
