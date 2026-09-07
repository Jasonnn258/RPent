# §1 sanity — tier selection (pre-registered)

_runs: 60 rows over tiers ['glm-5.3', 'glm-5.3-flash']; criteria fixed in plan keen-swinging-dove §1 BEFORE data: ① failure-form fidelity (t7→place_stall, t0/t9→place_fail dominant, grasp_fail<20%) ② SR band 15–85% ③ tie→flagship glm-5.3._

## Mechanism distribution (per tier/task, n=10 seeds)

| tier | task | no_pick | grasp_fail | place_stall | place_fail | success | SR |
|---|---|---|---|---|---|---|---|
| glm-5.3 | t0 | 4 | 0 | 0 | 4 | 2 | 2/10 |
| glm-5.3 | t7 | 0 | 0 | 2 | 5 | 3 | 3/10 |
| glm-5.3 | t9 | 0 | 0 | 0 | 6 | 4 | 4/10 |
| glm-5.3-flash | t0 | 0 | 0 | 0 | 4 | 6 | 6/10 |
| glm-5.3-flash | t7 | 0 | 0 | 0 | 2 | 8 | 8/10 |
| glm-5.3-flash | t9 | 0 | 0 | 0 | 8 | 2 | 2/10 |

## Pre-registered criteria

| tier | ① fidelity (of 3) | grasp_fail<20% | SR | SR in band |
|---|---|---|---|---|
| glm-5.3 | 1 (t0≠ t7≠ t9=) | ✓ | 30% | ✓ |
| glm-5.3-flash | 2 (t0= t7≠ t9=) | ✓ | 53% | ✓ |

**Selected tier: `glm-5.3-flash`** (① fidelity → ② SR band → ③ flagship tie-break, in that order).

---
_Failure-form sanity gate: if NEITHER tier reproduces the diagnostic failure forms (fidelity < 2/3 both), STOP per plan and report — taxonomy drift invalidates the B/C comparison._
