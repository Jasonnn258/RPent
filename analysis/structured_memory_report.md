# Structured Global Memory v1 — Baseline vs Structured

_updated 2026-08-18T16:53:23_

paired runs: baseline=33 structured=30 (reused progress-gate baseline repeat-1 + 3 fresh gate-off spot-checks)

rules: `/hw-tbo/yjx/workspace/RPent/analysis/structured_rules_v1.json` (v1, 9 rules) | phase model: P_init→P_look→P_transport→P_grasp→P_place→P_verify


## Task 0

| metric | baseline | structured | delta |
|---|---|---|---|

| n | 11 | 10 | |

| SR | 45% | 60% | +15% |

| turns | 33.36 | 29.6 | -3.76 |

| planner_calls | 33.36 | 29.6 | -3.76 |

| tokens | 2.77199e+06 | 2.14319e+06 | -628797 |

| perc | 20 | 19.2 | -0.8 |

| act | 8 | 8.8 | 0.8 |

| maxred | 7.18 | 7.1 | -0.08 |

| mem_reads | 1 | 1.2 | 0.2 |

| n_fired | 1.73 | 1.8 | 0.07 |

| recovery_success | 1.09 | 1.4 | 0.31 |

| recovery_fail | 0.64 | 0.4 | -0.24 |

| injections | 5.36 | 5.4 | 0.04 |

| off_phase_actions | 6 | 7.2 | 1.2 |


per-seed (paired):

| seed | base SR | str SR | base turns | str turns | base fired | str fired | base memrd | str memrd |
|---|---|---|---|---|---|---|---|---|

| 1 | 0 | 0 | 11 | 12 | 1 | 1 | 1 | 1 |

| 10 | 1 | 1 | 30 | 24 | 1 | 1 | 1 | 1 |

| 2 | 0 | 1 | 40 | 40 | 2 | 4 | 1 | 2 |

| 3 | 0 | 1 | 40 | 22 | 2 | 1 | 1 | 1 |

| 4 | 0 | 0 | 40 | 40 | 2 | 2 | 1 | 1 |

| 5 | 0 | 1 | 40 | 21 | 2 | 1 | 1 | 1 |

| 6 | 1 | 1 | 40 | 22 | 2 | 1 | 1 | 1 |

| 7 | 0 | 1 | 15 | 35 | 1 | 2 | 1 | 1 |

| 8 | 1 | 0 | 40 | 40 | 2 | 3 | 1 | 2 |

| 9 | 1 | 0 | 36 | 40 | 2 | 2 | 1 | 1 |


## Task 7

| metric | baseline | structured | delta |
|---|---|---|---|

| n | 11 | 10 | |

| SR | 55% | 60% | +5% |

| turns | 38.91 | 36.6 | -2.31 |

| planner_calls | 38.91 | 36.6 | -2.31 |

| tokens | 3.32339e+06 | 3.03289e+06 | -290499 |

| perc | 25.27 | 17.6 | -7.67 |

| act | 10.82 | 14.8 | 3.98 |

| maxred | 10.73 | 5.4 | -5.33 |

| mem_reads | 1 | 1.2 | 0.2 |

| n_fired | 2.09 | 2.1 | 0.01 |

| recovery_success | 1.27 | 1.9 | 0.63 |

| recovery_fail | 0.82 | 0.2 | -0.62 |

| injections | 5.73 | 6.2 | 0.47 |

| off_phase_actions | 7.73 | 11.6 | 3.87 |


per-seed (paired):

| seed | base SR | str SR | base turns | str turns | base fired | str fired | base memrd | str memrd |
|---|---|---|---|---|---|---|---|---|

| 1 | 1 | 1 | 40 | 33 | 2 | 2 | 1 | 1 |

| 10 | 1 | 1 | 40 | 40 | 2 | 2 | 1 | 1 |

| 2 | 1 | 1 | 37 | 31 | 2 | 1 | 1 | 1 |

| 3 | 0 | 1 | 40 | 37 | 2 | 2 | 1 | 1 |

| 4 | 0 | 0 | 40 | 40 | 3 | 2 | 1 | 3 |

| 5 | 0 | 0 | 40 | 40 | 2 | 3 | 1 | 1 |

| 6 | 1 | 1 | 38 | 29 | 2 | 1 | 1 | 1 |

| 7 | 1 | 0 | 40 | 40 | 2 | 3 | 1 | 1 |

| 8 | 0 | 0 | 40 | 40 | 3 | 3 | 1 | 1 |

| 9 | 0 | 1 | 40 | 36 | 2 | 2 | 1 | 1 |


## Task 9

| metric | baseline | structured | delta |
|---|---|---|---|

| n | 11 | 10 | |

| SR | 64% | 70% | +6% |

| turns | 38.64 | 32.4 | -6.24 |

| planner_calls | 38.64 | 32.4 | -6.24 |

| tokens | 3.40163e+06 | 2.44662e+06 | -955017 |

| perc | 22.09 | 16.5 | -5.59 |

| act | 10.18 | 13.5 | 3.32 |

| maxred | 9.73 | 6.2 | -3.53 |

| mem_reads | 1.36 | 1.4 | 0.04 |

| n_fired | 2.82 | 2.9 | 0.08 |

| recovery_success | 1.45 | 2 | 0.55 |

| recovery_fail | 1.36 | 0.9 | -0.46 |

| injections | 5.73 | 5.9 | 0.17 |

| off_phase_actions | 8 | 13.1 | 5.1 |


per-seed (paired):

| seed | base SR | str SR | base turns | str turns | base fired | str fired | base memrd | str memrd |
|---|---|---|---|---|---|---|---|---|

| 1 | 0 | 1 | 40 | 40 | 2 | 3 | 1 | 1 |

| 10 | 1 | 0 | 40 | 40 | 3 | 4 | 1 | 1 |

| 2 | 1 | 1 | 38 | 29 | 3 | 2 | 1 | 1 |

| 3 | 0 | 0 | 40 | 39 | 2 | 4 | 1 | 1 |

| 4 | 1 | 1 | 39 | 18 | 3 | 2 | 1 | 1 |

| 5 | 1 | 1 | 37 | 17 | 3 | 2 | 1 | 1 |

| 6 | 0 | 1 | 40 | 31 | 3 | 1 | 1 | 2 |

| 7 | 1 | 1 | 40 | 38 | 3 | 4 | 1 | 1 |

| 8 | 0 | 0 | 40 | 40 | 3 | 4 | 1 | 1 |

| 9 | 1 | 1 | 32 | 32 | 2 | 3 | 1 | 4 |


## Overall

| metric | baseline | structured | delta |
|---|---|---|---|

| n | 33 | 30 | |

| SR | 55% | 63% | +9% |

| turns | 36.97 | 32.87 | -4.1 |

| planner_calls | 36.97 | 32.87 | -4.1 |

| tokens | 3.16567e+06 | 2.5409e+06 | -624771 |

| perc | 22.45 | 17.77 | -4.68 |

| act | 9.67 | 12.37 | 2.7 |

| maxred | 9.21 | 6.23 | -2.98 |

| mem_reads | 1.12 | 1.27 | 0.15 |

| n_fired | 2.21 | 2.27 | 0.06 |

| recovery_success | 1.27 | 1.77 | 0.5 |

| recovery_fail | 0.94 | 0.5 | -0.44 |

| injections | 5.61 | 5.83 | 0.22 |

| off_phase_actions | 7.24 | 10.63 | 3.39 |


per-seed (paired):

| seed | base SR | str SR | base turns | str turns | base fired | str fired | base memrd | str memrd |
|---|---|---|---|---|---|---|---|---|

| 1 | 0 | 0 | 11 | 12 | 1 | 1 | 1 | 1 |

| 10 | 1 | 1 | 30 | 24 | 1 | 1 | 1 | 1 |

| 2 | 0 | 1 | 40 | 40 | 2 | 4 | 1 | 2 |

| 3 | 0 | 1 | 40 | 22 | 2 | 1 | 1 | 1 |

| 4 | 0 | 0 | 40 | 40 | 2 | 2 | 1 | 1 |

| 5 | 0 | 1 | 40 | 21 | 2 | 1 | 1 | 1 |

| 6 | 1 | 1 | 40 | 22 | 2 | 1 | 1 | 1 |

| 7 | 0 | 1 | 15 | 35 | 1 | 2 | 1 | 1 |

| 8 | 1 | 0 | 40 | 40 | 2 | 3 | 1 | 2 |

| 9 | 1 | 0 | 36 | 40 | 2 | 2 | 1 | 1 |


## Rule engagement (fires per run, avg)

| rule | baseline | structured |
|---|---|---|

| R1 | 1 | 0.93 |

| R4 | 0.06 | 0.07 |

| R5 | 0.27 | 0.33 |

| R7 | 0 | 0.3 |

| R8 | 0.03 | 0.07 |

| R9 | 0.85 | 0.57 |
