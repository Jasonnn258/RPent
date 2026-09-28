# Stage H0 — Failure-State Benchmark 协议(stageH0_protocol.md)

_2026-09-28 生成 by scripts/build_stageH0_failure_states.py(确定性抽取,
零重跑、零仿真)。判据全部为 runtime-observable 字段;未来信息只进
`analysis_only` 块。_

## 数据源与排除

- 源:G0.5/G0.6 final 180 matched trajectories(outcome_validation_runs.csv
  指向的最终合法 episode;provenance G0/G05/G06_extension 各 60)。
- infra 排除:180 格终态零 infra(§14 已核);states.json 缺失/损坏的
  目标本 集排除并计数(本轮:0)。
- 正常 waypoint repetition 处理:MOVE_STALL 判据要求 residual >=
  MOVE_TOL(0.03,冻结值)且窗口内不下降 —— 到位后的重复 move 不算。

## 三类失败判据(冻结)

| 家族 | 判据(全 runtime 可观测) |
|---|---|
| FALSE_GRASP | pi0_pick success=True 且 peak_lift_m < 0.005(B2 紧握误报同阈值);或 success=False |
| MOVE_CONTACT_STALL | 两种证据型:(a) move_group_stall = >= 3 个 move(穿插 <= 3 步非 move)residual 全部 >= 0.03 且不下降 —— 本语料实测仅 2 集(move 是伺服原语,持续物理停滞罕见,如实报告);(b) contact_skill_no_terminate = pi0_doubled success=False(冻结触发器 T1 原话定义)。residual < TOL 的 move 重复一律不算(正常 waypoint 驻留) |
| RELEASE_PREDICATE_STALL | release 开爪成功(final_gripper_opening > 0.05)但其后 4 step 内 libero_terminated 仍 False |

同家族紧邻步(间隔 <= 1 step)视为同一停滞的延续,只保留首个 point。

## split 纪律

- 单位 = (task, seed):同 (task,seed) 的三臂 episode 永远同侧;
- hash = md5("libero_spatial_task_t{t}_s{s}") % 100,validation 取
  前 40%,discovery 其余;同一 episode 不跨 split(结构性保证)。

## 字段与防火墙

- `runtime_view` = router/graph 的**唯一**合法输入(task goal、
  observable pre-state、窗口证据);无 reason 文本、无 GT、无未来字段。
- `analysis_only.*`(终局 success、source_path)只供离线评测;
  **任何 runtime/router prompt 不得读取** —— loader 按字段名硬过滤。
- 旧 recovery@3 保留为 diagnostic(post_intervention_progress@3);
  H1 主指标 validated_recovery 按 stageH1_prereg 定义,不混用。

## 本轮数量与证据质量

```json
{
  "episodes_scanned": 180,
  "episodes_infra_excluded": 0,
  "episodes_with_failure_points": 90,
  "episodes_contributing_points": 90,
  "decision_points_total": 177,
  "points_by_family": {
    "FALSE_GRASP": 142,
    "MOVE_CONTACT_STALL": 17,
    "RELEASE_PREDICATE_STALL": 18
  },
  "episodes_by_family": {
    "FALSE_GRASP": 78,
    "MOVE_CONTACT_STALL": 16,
    "RELEASE_PREDICATE_STALL": 17
  },
  "points_by_family_split": {
    "FALSE_GRASP/discovery": 51,
    "FALSE_GRASP/validation": 91,
    "MOVE_CONTACT_STALL/discovery": 9,
    "MOVE_CONTACT_STALL/validation": 8,
    "RELEASE_PREDICATE_STALL/discovery": 9,
    "RELEASE_PREDICATE_STALL/validation": 9
  }
}
```

- RELEASE_PREDICATE_STALL 偏少:不补造、不放宽定义(§1 纪律)。
  180 格内该家族共 17 集;若 H1 需要更多,只允许从未用 seeds 的
  **新真实 episode** 补,并同样过本判据。
- 判据的假阳性面:FALSE_GRASP 的 success=False 分支可能含"目标本身
  不可抓"的 episode 级困难 —— H1 分析按 evidence_id 分层复核。
