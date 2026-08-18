# Progress Gate 实验结果

_updated 2026-08-18T10:49:16_

completed episodes: 270

## P0

| cond | n | SR | turns | planner | tokens | perc | act | maxred |

|---|---|---|---|---|---|---|---|---|

| baseline | 90 | 47% | 37.32 | 37.32 | 3164584.08 | 23.5 | 9.59 | 9.7 |

| ours | 90 | 42% | 38.3 | 38.3 | 3260982.02 | 22.93 | 9.88 | 10.11 |

  baseline reasons: success:47%, grasp_fail:27%, placement_fail:22%, infra_crash:4%

  ours reasons: success:42%, grasp_fail:23%, placement_fail:23%, reach_plan_fail:10%, infra_crash:1%



## P1

| cond | n | SR | turns | planner | tokens | perc | act | maxred |

|---|---|---|---|---|---|---|---|---|

| hardcap | 90 | 47% | 37.12 | 37.12 | 3211541.94 | 21.67 | 10.83 | 7.57 |

  hardcap reasons: success:47%, placement_fail:30%, grasp_fail:21%, infra_crash:1%, reach_plan_fail:1%



## Stage gates

- P1 (proceed to hardcap ablation): **True**  (SR ours 42% vs baseline 47%, rule: ours >= baseline - 10pp)

- P2 (generalize to 4 suites): **False**  (turns 38.3 vs 37.32, red 10.11 vs 9.7)
