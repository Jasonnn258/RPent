# Stage C2 设计:Progress-Aware Trigger 离线 benchmark(2026-09-18)

上游:C1 已判 QUERY ENRICHMENT NOT SUPPORTED(本轮只动 trigger,query 不动)。
H2:**action repetition ≠ no progress**。该查 Memory 的条件是"实际物理状态没有
产生该动作预期的进展",不是"同一动作连续出现"。

## 诊断出发点(#49 实测)

- T0(#49 冻结 trigger)94 火中 69 次(73%)无对齐 SHOULD 信号,火源 T4"连续
  同 primitive"73/94 —— 正常 waypoint 运输(连续 move_to、每个都到达)被当成
  "卡住重复"。
- **T0 的 move-stopped-short 规则(final_dist>0.03)在线 0 火**:boundary 只评估
  "自上一 boundary 以来的最后一个结果",短 move 常被同 turn 后续工具调用覆盖,
  信号丢失,24 个 recovery_transport 时刻实际全靠 T4 的重复计数碰巧覆盖(6 火)。
- SHOULD 时刻(官方 60 集,states.json result + segments):50 个 =
  predicate_open 25 + recovery_transport 24 + perception 1。(Stage B 报的 45
  = 只含有火集;C2 统一用 60 集全分母,两臂同口径。)

## 标签(两族分开,不混字段)

**progress_state(物理过程标签,事后确定性标注)**,每个工具结果一个:
- MOVE(move_to/move_pose):`final_dist_m≤0.03`(到达)或对 command 目标前进
  >5mm → PROGRESSING;residual>0.03 且前进 ≤5mm → STALLED;字段缺失 → AMBIGUOUS
- PICK(pi0_pick):success=true 且 ascent≥0.05 → PROGRESSING;success=true 但
  ascent<0.05 → STALLED(声称的进展物理上没发生);success=false:若下一个
  primitive 也是失败 pick → STALLED,否则 AMBIGUOUS(**单次失败不自动 STALLED**)
- PLACE(release):libero_terminated → PROGRESSING;gripper 张开(后一 state 的
  span − 前 span >0.02)→ 物理上 PROGRESSING(predicate 期望归 should_retrieve
  族管);没张开 → STALLED;post 缺失 → AMBIGUOUS
- PERCEPTION(segment/back_project):found=true → PROGRESSING;found=false /
  world_error → STALLED(无有效观测 = progress failure);其余 AMBIGUOUS
- RECOVERY(pi0_doubled):success/terminated → PROGRESSING;失败且前一 primitive
  也是失败 → STALLED;失败但前面没失败 → AMBIGUOUS

**should_retrieve(需求标签)**:沿用 Stage B SHOULD 时刻(50 个),不重标。

## T0(复现,不改)

直接用 #49 落盘的 `memory_events.jsonl` 实际火(含 cooldown/cap 真实效果),
不重放。

## T1(progress-aware,冻结规则,task-free)

基础设施与 #49 相同:每集 cap 6、火后 2 turn cooldown、第一个 primitive 前不
火。差别:**逐结果评估**(每个工具结果都判,火挂在该结果所在 turn;修复
T0"只看最后一个结果"的信号丢失)。规则(按序):

| 规则 | 条件(全部 harness 可见) | 火类 |
|---|---|---|
| R1 | perception 工具 found=false / world_error | perception |
| R2 | move:final_dist>0.03 且对目标前进 ≤5mm(dist_pre−final_dist;dist_pre 缺失按 0) | recovery_transport |
| R3 | pick:success=true 但 ascent<0.05;或连续第 2+ 个失败 pick | pick_verify / grasp |
| R4 | pi0_doubled 失败 且 前一 primitive 也失败 | recovery_doubled |
| R5 | release 且 libero_terminated=false(动作预期进展=谓词置真,没发生) | predicate_open |

**删除的 T0 规则**:T4 重复计数(被 R2 的逐 move 物理判据替代)、T6(离线无
tracker 信号,在线 0 火)、T7(≥8 无迁移——crude proxy,8/8 在线仅 2 火)、
is_error(离线 states 无该字段,不可复现)。连续 move 链只要每个 move 在前进或
到达就永不火。

## 指标(官方 60 集,同分母 50 时刻)

- Trigger Precision / Recall(coverage)/ F1、False trigger per episode、
  zero-fire episodes
- **69 个 T0 误报消掉多少**(T0 未对齐火在该 turn±1 内无同集 T1 火 = 消除;
  另报同类口径)
- 正常连续 move false alarm:labeler 判 PROGRESSING 的 move 上发生火的比例
  (T0 vs T1;T1 按构造应为 ~0)
- STALLED detection:labeler 判 STALLED 的事件被 T1 火覆盖(0-3 turn 同族)比例
- PROGRESSING false-positive rate(T1 火落在 PROGRESSING 事件上的比例)、
  AMBIGUOUS rate(全部已标事件中 AMBIGUOUS 占比,单独报不强判)

## 门槛(预注册)

- T1 precision ≥ 0.50(T0 ≈ 0.27)**且** T1 recall 相比 T0 下降 ≤10pp
  (T0 全分母 recall = 24/50 = 0.48 → T1 需 ≥0.38)
- 不过 → PROGRESS TRIGGER NOT SUPPORTED,不进在线
- 过 → 冻结 T1 规则进 C3(与 C1 结论合并:C1 未过 → C3 只跑 O0 vs O2 单变量)

## 已知限制(如实报)

- 离线 T1 无法复现 is_error 与 T6(在线 0/94 火,影响可忽略);cooldown 按
  turn 距离近似(在线按 boundary)。
- labeler 与 T1 用同一信号族(result 字段 + pre/post state),非独立金标准;
  靠 should_retrieve 时刻(独立来源:集结局无关的 result 分类)作主判定锚点。
