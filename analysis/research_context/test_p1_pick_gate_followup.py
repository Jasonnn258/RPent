"""Gate followup 合成测试;不触私有数据、不做阈值选择。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_pick_gate_followup import (
    descent_sensitivity_descriptive, fn_decomposition, loto_gate_family,
    min_vs_final_detail, paired_bootstrap_vs_flag, _dist,
)
from p1_pick_gate_lab import D_THRESHOLD, L_THRESHOLD, G_THRESHOLD


def row(i, task="9", flag=False, reference=True, descent=.12,
        lift=.055, final=.02, minimum=.019, chunks=24, maxc=24):
    return {
        "episode_id": f"ep_{i}", "step_idx": i, "task": task,
        "reference": reference,
        "tool_report": {
            "name": "pick", "success": flag, "chunks_used": chunks,
            "max_chunks": maxc, "peak_lift_m": lift,
            "min_gripper_opening": minimum, "final_gripper_opening": final,
            "diagnostics": {"descent_m": descent},
        },
    }


class FollowupTests(unittest.TestCase):
    def test_dist_handles_missing_and_nonfinite(self):
        d = _dist([None, float("nan"), -1, 0.5, 1.0])
        self.assertEqual(d["n_valid"], 2)
        self.assertEqual(d["min"], 0.5)
        self.assertEqual(d["max"], 1.0)
        self.assertEqual(_dist([None])["n_valid"], 0)

    def test_fn_decomposition_counts_patterns_and_near_threshold(self):
        rows = [
            # 011(只缺 D),descent=0.08 在 0.10-3cm 内
            row(1, task="9", descent=.08),
            # 011 但 descent 深度未达 0.02
            row(2, task="9", descent=.02),
            # 101(只缺 L)
            row(3, task="9", descent=.12, lift=.03),
            # flag=True 的不是 FN
            row(4, task="9", flag=True),
            # flag=F 但代理为负的不是 FN
            row(5, task="9", reference=False),
        ]
        out = fn_decomposition(rows)["9"]
        self.assertEqual(out["n_fn"], 3)
        self.assertEqual(out["gate_patterns_D_L_Gfinal"], {"011": 2, "101": 1})
        self.assertEqual(out["n_pattern011_descent_within_3cm_of_threshold"], 1)
        self.assertEqual(out["n_chunks_used_eq_max"], 3)

    def test_min_vs_final_breakdown_and_reopen_direction(self):
        rows = [
            # min 闭过、末端张开(重开方向)
            row(1, task="3", minimum=.02, final=.08),
            # 两开度一致(不计数)
            row(2, task="3", minimum=.02, final=.03),
            # 代理负例,保证各类非零
            row(3, task="3", reference=False, minimum=.02, final=.03),
        ]
        out = min_vs_final_detail(rows)
        self.assertEqual(out["n_disagree"], 1)
        self.assertEqual(out["by_task_flag"], {"3|FLAG_F": 1})
        self.assertEqual(out["n_min_closed_but_final_reopened"], 1)
        # final 比 min 更特异:Gfinal 臂 FP 只少不多
        d = out["paired_arm_differences"]["L_AND_Gfinal_minus_L_AND_Gmin"]
        self.assertLessEqual(d["d_fp"], 0)

    def test_paired_bootstrap_deterministic_and_bounded(self):
        rows = [row(i, task=("3", "5", "9")[i % 3],
                    flag=(i % 4 == 0), reference=(i % 2 == 0))
                for i in range(30)]
        a = paired_bootstrap_vs_flag(rows, "L_AND_Gfinal", repeats=50, seed=7)
        b = paired_bootstrap_vs_flag(rows, "L_AND_Gfinal", repeats=50, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(a["n_valid"], 50)
        self.assertLessEqual(a["p95_interval"][0], a["p95_interval"][1])
        self.assertLessEqual(a["p95_interval"][0], a["median"])
        self.assertGreaterEqual(a["p95_interval"][1], a["median"])

    def test_loto_selects_and_pools_without_audit_leakage(self):
        # 任务 3 上 flag 完美,任务 9 上 L∧Gfinal 完美 → 各折应选对赢家
        rows = [row(i, task="3", flag=(i % 2 == 0), reference=(i % 2 == 0),
                    descent=.12 if i % 2 == 0 else .02,
                    lift=.055 if i % 2 == 0 else .01,
                    final=.02 if i % 2 == 0 else .08)
                for i in range(20)]
        rows += [row(100 + i, task="9", flag=False, reference=True,
                     descent=.05, lift=.06, final=.02)
                 for i in range(20)]
        rows += [row(200 + i, task="9", flag=False, reference=False,
                     descent=.05, lift=.01, final=.02)
                 for i in range(20)]
        # 任务 5 少量填充,凑齐三折
        rows += [row(300 + i, task="5", flag=(i % 2 == 0),
                     reference=(i % 2 == 0), descent=.12, lift=.06, final=.02)
                 for i in range(4)]
        out = loto_gate_family(rows)
        self.assertEqual(len(out["folds"]), 3)
        # 留 9 时训练=任务3,flag 完美 → 选 flag;留 3 时训练=任务9 → L_AND_Gfinal
        by_heldout = {f["heldout_task"]: f["selected_arm"] for f in out["folds"]}
        self.assertEqual(by_heldout["9"], "F0_tool_flag")
        self.assertEqual(by_heldout["3"], "L_AND_Gfinal")

    def test_descent_sensitivity_is_monotone_descriptive(self):
        rows = [row(i, task="9", descent=.06, lift=.06, final=.02)
                for i in range(10)]
        out = descent_sensitivity_descriptive(rows)["overall"]
        self.assertIn("descent_gte_0.10", out)
        self.assertIn("descent_gte_0.00", out)
        # 阈值越松 TP 单调不减
        tps = [out[f"descent_gte_{t:.2f}"]["tp"] for t in (0.0, .03, .05, .07, .10)]
        self.assertEqual(tps, sorted(tps, reverse=True))


if __name__ == "__main__":
    unittest.main()
