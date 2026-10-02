# Stage O O-A — 离线恢复来源审计(§4-§6,descriptive)

- 对象:Stage N 24 个 failure snapshots 的源 episode(Full Planner)
- 源 episode 最终恢复:23/24;未恢复 1 例(['snap_00'])
- 全部字段为确定性规则计算(零 LLM);机制标签多标签,descriptive

## 1. 逐 case 表(恢复窗口内 Full Planner 行为)

| case | family | t0→done | prims | turns | obs | ground | subgoalΔ | famΔ | doubled | move_pose | resample | retreat | labels |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| snap_00 | FALSE_GRASP | 4→(未恢复) | 5 | 9 | 4 | 3 | 0 | 3 | · | ✓ | ✓ | ✓ | SAMPLING_LIKE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_01 | FALSE_GRASP | 12→17 | 5 | 5 | 0 | 0 | 1 | 3 | ✓ | ✓ | · | · | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION |
| snap_02 | RELEASE_PRED | 11→13 | 2 | 3 | 1 | 0 | 1 | 1 | ✓ | · | · | ✓ | CONDITIONING_CHANGE|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_03 | RELEASE_PRED | 7→10 | 3 | 4 | 1 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_04 | RELEASE_PRED | 6→8 | 2 | 3 | 1 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_05 | RELEASE_PRED | 7→10 | 3 | 4 | 1 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_06 | FALSE_GRASP | 1→6 | 5 | 11 | 6 | 2 | 1 | 3 | · | · | ✓ | ✓ | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_07 | RELEASE_PRED | 7→9 | 2 | 3 | 1 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_08 | RELEASE_PRED | 8→10 | 2 | 3 | 1 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_09 | RELEASE_PRED | 10→13 | 3 | 6 | 3 | 2 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_10 | RELEASE_PRED | 8→10 | 2 | 3 | 1 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_11 | RELEASE_PRED | 8→11 | 3 | 3 | 0 | 0 | 1 | 1 | · | · | · | ✓ | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|RESET_REALIGNMENT |
| snap_12 | RELEASE_PRED | 10→12 | 2 | 3 | 1 | 0 | 1 | 1 | ✓ | · | · | ✓ | CONDITIONING_CHANGE|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_13 | RELEASE_PRED | 10→12 | 2 | 2 | 0 | 0 | 1 | 1 | ✓ | · | · | ✓ | CONDITIONING_CHANGE|RESET_REALIGNMENT |
| snap_14 | FALSE_GRASP | 4→11 | 7 | 11 | 4 | 1 | 2 | 5 | · | · | ✓ | · | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING |
| snap_15 | FALSE_GRASP | 6→11 | 5 | 9 | 4 | 2 | 0 | 2 | · | · | · | · | SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING |
| snap_16 | FALSE_GRASP | 4→5 | 1 | 1 | 0 | 0 | 0 | 0 | · | · | · | · | UNRESOLVED |
| snap_17 | FALSE_GRASP | 4→11 | 7 | 14 | 7 | 3 | 2 | 5 | · | · | ✓ | · | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING |
| snap_18 | RELEASE_PRED | 10→12 | 2 | 2 | 0 | 0 | 1 | 1 | ✓ | · | · | · | CONDITIONING_CHANGE |
| snap_19 | FALSE_GRASP | 4→12 | 8 | 12 | 4 | 2 | 1 | 5 | · | ✓ | ✓ | ✓ | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING|RESET_REALIGNMENT |
| snap_20 | FALSE_GRASP | 3→5 | 2 | 2 | 0 | 0 | 1 | 1 | · | · | ✓ | · | CONDITIONING_CHANGE |
| snap_21 | FALSE_GRASP | 3→12 | 9 | 10 | 1 | 0 | 1 | 6 | · | · | ✓ | · | SAMPLING_LIKE|CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING |
| snap_22 | FALSE_GRASP | 4→9 | 5 | 9 | 4 | 2 | 1 | 4 | · | · | ✓ | · | CONDITIONING_CHANGE|SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING |
| snap_23 | FALSE_GRASP | 4→9 | 5 | 8 | 3 | 1 | 0 | 2 | · | · | · | · | SEQUENCE_COMPOSITION|DYNAMIC_REPLANNING |

## 2. 机制标签分布(仅 23 个恢复 case,多标签)

- CONDITIONING_CHANGE: 20/23
- DYNAMIC_REPLANNING: 17/23
- SEQUENCE_COMPOSITION: 13/23
- RESET_REALIGNMENT: 13/23
- UNRESOLVED: 1/23
- SAMPLING_LIKE: 1/23

## 3. 确定性亚型分布(arm 构造输入)

- FALSE_GRASP / FG_HELD_AND_PLACE(失败即持有→直接放置/释放):4
- FALSE_GRASP / FG_RESAMPLE_REPICK(重新定位+重抓):8
- RELEASE_PREDICATE_STALL / RPS_PROCEED_DOUBLED(直接换位技能):4
- RELEASE_PREDICATE_STALL / RPS_REPICK(重抓重放):8

- FALSE_GRASP t0 爪闭合(min_o<0.03,raw,闭空/持物不可分):11/12
- FALSE_GRASP 持有推断(物理恒真:放置完成且零重抓):4/12 ⇒ 这部分'失败'是验证器假阴性,非物理抓空

## 4. 关键 repertoire 观察

- 使用 pi0_doubled(Stage N local recovery 词汇表外):5/23
- 使用 move_pose:2/23
- resample 同一 skill 同一 prompt:7/23
- 改变 subgoal/prompt:20/23
- 恢复窗口内含观察调用:17/23
- 恢复前先 retreat/realign:13/23

> O-A 只用于理解与 arm 构造;O-B confirmatory 证据独立采集(§3)。
