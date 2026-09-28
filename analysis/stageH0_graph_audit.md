# Stage H0 — Graph Audit(stageH0_graph_audit.md)

_2026-09-28 by scripts/audit_stageH0_graph.py。对象:graph v0(11 nodes / 25 edges)× 基准 148 点。_

## 门槛(preregistered)
| 门槛 | 要求 | 实测 | 判定 |
|---|---|---|---|
| hidden/future leakage | 0 | 0 | PASS |
| guard conflicts | 0 | 0 | PASS |
| schema validation | 100% | OK(load_graph fail-fast) | PASS |
| localization(明确 failure states) | >= 90% | 100.0% (148/148) | PASS |
| ambiguous/uncertain rate(报告项) | — | 0/148 (0.0%) | — |
| coverage:零合法出边点数(报告项) | — | 0/148 | — |
| wrong-phase edge exposure(报告项) | — | 0 | — |

## 判定
**ALL GATES PASS — 可以进入 §4 H1。**

## 明细
- node 分布: {'FALSE_GRASP': 113, 'MOVE_STALL': 2, 'RELEASE_PREDICATE_STALL': 18, 'CONTACT_STALL': 15}
- 合法边触达计数(top): {'FG-1': 113, 'FG-3': 113, 'RS-1': 18, 'RS-2': 18, 'RS-3': 18, 'CS-1': 15, 'CS-2': 15, 'CS-3': 15}
- localization per family: {'FALSE_GRASP': '113/113', 'MOVE_STALL': '2/2', 'RELEASE_PREDICATE_STALL': '18/18', 'CONTACT_STALL': '15/15'}

## 修订记录(如实披露,非首跑即过)

首跑 loc=0.723 / leak=177,三类根因全部为**基建侧 bug**,
逐一定位修复后重跑;家族判据本身零改动:

1. **runtime_view 漏计数器**(49 点 mismatch 的主因):抽取器把
   `runtime_view.observable_pre_state` 只填了原语结果字段,漏掉
   SM1 风格计数器(release_open/consec_move_stall/…);真实 runtime
   在 turn boundary 计数器可见(触发器 T1-T7 消费同一词汇)。
   修复 = view 与顶层 pre_state 同源合并。
2. **白名单漏 descent_done/eef_z**(177 点假 leak):两者为
   runtime 可观测(pi0_pick result.diagnostics 与本体感知
   eef_z,planner 在工具结果里可见),补进 OBSERVABLE_FACT_KEYS。
3. **29 个 post-terminal 假失败点**(FALSE_GRASP→DONE 全部来源):
   证据步自身 libero_terminated=True(且 analysis_only 终局多为
   success)—— episode 已结束,不存在恢复决策点;按与
   pi0_doubled/release 分支同一 `not term` 口径从基准剔除。
   基准 177 → 148 点(FALSE_GRASP 142→113)。
4. **interpreter MOVE_STALL 规则收紧**(H1 §3(b) 重放校验钓出):
   原 consec>=2 且无趋势判据,会在残差**在降**(有进展)的 2-move
   远距上早触发。收紧为基准抽取器逐语句同构的 3-move 窗口全
   未到位且残差不降(新增计数器 move_win_first_dist)。收紧后
   本表门槛重跑仍全 PASS(148 点不变、localization 仍 100%)。

修复后全门槛通过;graph v0(节点/边/guard)零改动。