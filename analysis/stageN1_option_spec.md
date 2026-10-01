# Stage N1 预注册 — CLOSED-LOOP OPTION vs FIXED_MACRO(闭环反馈验证)

冻结日期:2026-10-01 | 前置:N0 PASS(45/45 零分歧,commit 0a2f0bd)
本文档 + resources/libero/options_stageN.yaml + analysis/stageN1_split_manifest.csv
三者先于 runner 代码 commit;runner 只实现此处冻结的内容。

## 0. 研究问题(规范 §14-15)

N1 不研究 "Option 看起来像不像 Option",直接操纵:**新 physical information
是否被允许改变 downstream control**。

- **M = FIXED_MACRO**:t0 冻结 sequence + key parameters;中间观测/验证
  结果被记录(provenance)但**不得**改变任何控制。
- **O = CLOSED_LOOP_OPTION**:同一骨架,维护显式信息状态(§16 七字段),
  中间 information event 可以改变 action / parameter / continue /
  retry / fallback / termination,每次改变记录因果来源。

匹配维度(规范 §15,逐项对齐):primitive set、Pi0.5 skill 与参数模板、
max action count(=5)、retry budget(pick 最多 2 次)、wall-time budget
(每动作沿用原语默认上限,两臂相同)、initial state(同一快照
restore_state,读回校验 0.0)、perception capability(两臂可调同一
SAM3 segment;M 的结果仅落盘不进控制)。

**禁止**:调 GLM planner;改 Pi0.5 semantics;M/O 使用不同 prompt 或不同
chunk 预算模板。

## 1. 备选 procedure(规范 §14:少量、证据充分)

只选 N0 盲审中证据最集中的两族(45 卷中 RPS 23 / FG 20):

### P1 RPS-REICK(RELEASE_PREDICATE_STALL)

- 快照前置条件:step t0 command.action == "release" 且
  result.libero_terminated == False(碗已释放、视觉在盘、谓词未触发)。
- 共享词汇:{move_to, pi0_pick};感知:segment;预算 5 动作 / pick ≤2 次。
- **M(全部冻结于 t0)**:
  1. move_to(eef_t0.xy, eef_t0.z + 0.10, gripper=-1, step_clip=0.015,
     max_steps=60)(retreat)
  2. move_to(eef_t0.xy, 0.99, 同上)(descend,冻结目标)
  3. pi0_pick("pick up the black patterned bowl", max_chunks=12,
     lift_thresh=0.05, gripper_closed_thresh=0.06)
  4. pi0_pick(同 3)(固定重试)
- **O(规则集,rule_id 冻结)**:
  1. move_to(retreat,同 M)
  - **R1 [state_flag → termination]** retreat 后读 libero_terminated:
    True → 结束(EARLY_STOP)。
  - **R2 [segment → pose_update]** segment("the black patterned bowl on the
    plate", camera=agentview, min_score=0.3):score ≥ 0.3 → descend 目标
    改为 (world_xyz.xy, 0.99);否则用冻结目标。→ move_to
  3. pi0_pick(同 M)
  - **R3 [verifier_result → retry_fallback]** 读 pick#1 result:libero_terminated
    True → 结束;final_gripper_opening > 0.05(空手/松开)→ segment 重定位
    (R2 同式)→ move_to(新 xy, 0.99)→ pi0_pick #2(max_chunks=12);
    否则(持有)→ 结束(HOLD_END)。

### P2 FG-RETRY(FALSE_GRASP)

- 快照前置条件:step t0 command.action == "pi0_pick" 且
  result.success == False(A1 类:抓后松开/抓空,目标被推移)。
- t0 基线感知(两臂相同,先于任何动作;M 的全部参数在此冻结):
  seg_bowl = segment("the black patterned bowl", agentview);
  seg_plate = segment("the plate", agentview)。
- 共享词汇:{move_to, pi0_pick, set_gripper, release};预算 5 动作 /
  pick ≤2 次。
- **M(固定 5 步)**:
  1. move_to(seg_bowl.xy + (0, +0.045), 1.155, gripper=-1, step_clip=0.015,
     max_steps=60)(rim-hook 预位)
  2. pi0_pick(task_language, max_chunks=20, lift 0.05, closed 0.06)
  3. set_gripper(+1)(锁爪)
  4. move_to(seg_plate.xy + (0, +0.045), 1.05)(搬运)
  5. release
- **O**:
  1. move_to(seg_bowl 同 M)
  2. pi0_pick(task_language, 20)
  - **R1 [state_flag → termination]** result.libero_terminated True → 结束。
  - **R2 [verifier_result → branch]** min_gripper_opening < 0.03(持有)→
    set_gripper(+1) → move_to(seg_plate 同 M) → release(CARRY_END);
    否则(空/松)→ **R3**。
  - **R3 [segment → pose_update + retry]** segment 重定位碗 →
    move_to(新 xy + (0,+0.045), 1.135,更低) → pi0_pick(task_language,
    max_chunks=12)(RETRY_END)。

MCS(45 卷仅 2 卷)证据不足,不设 procedure(如实记录,不追补)。

## 2. 信息状态与 provenance(规范 §16)

O 每步更新显式状态字典:
`target_visible / target_grounded / target_pose_valid / support_relation /
latest_action_result / latest_verifier_result / retry_count`(字段→来源
映射见 yaml)。M 维护同一字典(记录用),但策略不读它。

**stageN1_information_provenance.jsonl** 每行:
`{procedure, snapshot_id, arm, rollout_idx, seq, info_event:{source,field,value},
rule_id, decision:{action, params}, realized}`。
`realized = true` 当且仅当 O 在该点的决策与"同快照 M 冻结决策"不同
(即信息确实改变了控制)。EARLY_STOP / 分支切换 / 参数改变均算。

## 3. 快照与随机性(规范 §17)

- 来源:analysis/stageN0_control_labels.csv 的 eligible 集
  (= RESOLVED 165 − 旧33 − SPOT3 − dev_viewed = 124)再排除
  **45 卷 audit manifest 的全部 episode**(episode 级排除,保守)。
- 前置条件按 §1 逐段核验 states.json(t0 动作与 result 字段);
  另要求 1..t0 每步有 command(可重放)。
- **task × seed 唯一**(全 N1 选择内不重复)。
- 每 procedure 抽 12 个快照(P1 取 RPS 族、P2 取 FG 族),层内
  segment_id 字典序 + np.random.RandomState(20261003).choice;
  长度三分位 S/M/L 均分(不足时按现有层)。
- 汇总:24 快照 × 2 臂 × R=3 重复 = 144 rollouts。
- Pi0.5 非确定性(Stage J:同 obs 动作差 0.23)按预注册重复 rollout
  处理;每次 rollout 前 restore_state(S)+ set_obs,读回校验 0.0。
  臂序交错 M,O,M,O,…(同 R 内),防时间漂移偏置。

## 4. 指标(规范 §18-19)

- **validated_recovery**:rollout 结束时 env.check_success() == True。
- **harm**(冻结 rubric,分析脚本实现):结束时 success == False 且
  (目标物 z 较 t0 下降 > 3cm 或 目标物 |Δxy| 较 t0 > 8cm)。
  附带报告 distractor 位移。
- **dependency_realization**(O):该 rollout ≥1 条 provenance
  realized=true。
- **feedback_rescue**(快照级):M 臂 3 次 rollout 全 fail 且 O 臂 ≥1 次
  recover 且该次 recover 的 rollout realized=true;
  rescue_rate = rescue 快照数 / 24。
- **feedback_harm**(快照级):O 受 harm 而 M 同快照无 harm;
  汇报,不进门。
- **mechanism split**:O rollouts 按 realized 分层;
  delta_realized = rec_rate(realized O) − rec_rate(M 全部),
  delta_not 同理;门要求 delta_realized ≥ delta_not_realized + 10pp。

## 5. 门(规范 §20,逐字冻结)

**CLOSED-LOOP FEEDBACK SUPPORTED** 当且仅当(汇总 144 rollouts,
snapshot-paired):

1. recovery(O) − recovery(M) ≥ 15pp
2. harm(O) − harm(M) ≤ 3pp
3. feedback_rescue_rate ≥ 10%
4. dependency_realization_rate ≥ 20%
5. delta_realized ≥ delta_not_realized + 10pp

若 Δrecovery ≥ 15pp 但 4/5 未过:
**OPTION IMPLEMENTATION OUTPERFORMS MACRO, MECHANISM INCONCLUSIVE.**
若 O ≈ M(< 15pp)或 O < M:
**CLOSED-LOOP FEEDBACK NOT SUPPORTED.**

## 6. 产物(规范 §22)

- analysis/stageN1_split_manifest.csv(选择 + 哈希,先 commit)
- analysis/stageN1_rollouts.csv(每 rollout 一行)
- analysis/stageN1_information_provenance.jsonl
- analysis/stageN1_results.md(指标 + 门判定)
- resources/libero/options_stageN.yaml(procedure 机读定义)

## 7. 运行纪律

- 单进程 runner(1 env + shared vla/sam3),MUJOCO_GL=osmesa,
  nohup 持久日志,断点续跑(--skip);预注册 manifest 先 commit。
- infra 错误(restore 读回 ≠0 / env 崩溃 / 序列化失败)按 infra_abort
  记录并 ≤3 重试,不混入指标。
- Stage N 完成后 STOP(规范 §23):禁止自动 Option Graph / evolution /
  LLM Router / WM / perception replacement / SFT / OPD / RL。
