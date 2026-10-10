"""Synthetic-only robustness-lab tests; never open private data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_return_time_triage_lab import legal_view
from p1_return_time_triage_robustness import (
    bootstrap_precision, frac_selected_mix, jackknife_episodes, score_levels)


def report(descent=.06, lift=.09, final=.004, min_gap=.003, flag=False):
    return {
        "name": "pick", "success": flag,
        "peak_lift_m": lift,
        "min_gripper_opening": min_gap,
        "final_gripper_opening": final,
        "diagnostics": {"descent_m": descent, "start_eef_z": 1.2,
                        "post_min_ascent_m": lift},
    }


def row(positive, task="9", lift=.09, ep="e1", pattern="011"):
    descent = .06 if pattern == "011" else .12
    final = .004 if pattern != "001" else .08
    r = report(descent=descent, lift=lift, final=final)
    return {
        "episode_id": ep, "task": task,
        "legal": legal_view(r),
        "exit_proxy_positive": positive,
        "ever_proxy_positive": positive,
    }


def population():
    """两 episode 聚类、跨两任务的 12 行小总体。

    task9(ep1) lift=.05..0.10, i>=2 为正 → 高分多正;
    task3(ep2) 同 lift 网格, i>=4 为正 → 仅两个高分正例。
    Top50%=6 行 = lift .10/.09/.08 三档(每档 t9+t3 各一)。
    """
    rows = []
    for i in range(6):
        rows.append(row(i >= 2, "9", lift=.05 + .01 * i, ep="ep1"))
    for i in range(6):
        rows.append(row(i >= 4, "3", lift=.05 + .01 * i, ep="ep2"))
    return rows


class RobustnessLabTests(unittest.TestCase):
    def test_frac_selected_mix_task_and_pattern(self):
        rows = population()
        mix = frac_selected_mix(rows, "PEAK_LIFT", .5, "task")
        # Top50% = 6 行:lift .10×2/.09×2/.08×2 全入选,无跨界并列残留
        self.assertEqual(sum(mix["selected"].values()), 6.)
        self.assertEqual(mix["selected"]["9"], 3.)
        self.assertEqual(mix["selected"]["3"], 3.)
        # t9 三行(.10正/.09正/.08正)=3;t3 三行(.10正/.09正/.08负)=2
        self.assertEqual(mix["selected_proxy_positive"]["9"], 3.)
        self.assertEqual(mix["selected_proxy_positive"]["3"], 2.)
        pat = frac_selected_mix(rows, "PEAK_LIFT", .5, "gate_pattern")
        self.assertEqual(sum(pat["selected"].values()), 6.)
        with self.assertRaisesRegex(ValueError, "dimension"):
            frac_selected_mix(rows, "PEAK_LIFT", .5, "episode_id")

    def test_frac_selected_mix_fractional_tie(self):
        # D_ONLY_PATTERN 全部同分 → k=3 均匀分配
        rows = [row(i < 2, ep=f"e{i}") for i in range(10)]
        mix = frac_selected_mix(rows, "D_ONLY_PATTERN", .3, "task")
        self.assertAlmostEqual(mix["selected"]["9"], 3., places=6)
        self.assertAlmostEqual(mix["selected_proxy_positive"]["9"], .6, places=6)

    def test_bootstrap_deterministic_and_bounded(self):
        rows = population()
        a = bootstrap_precision(rows, "PEAK_LIFT", .5, repeats=40, seed=7)
        b = bootstrap_precision(rows, "PEAK_LIFT", .5, repeats=40, seed=7)
        self.assertEqual(a, b)  # 固定种子完全可复现
        # 语义敏感性:换随机排序臂(UNTARGETED 并列均分)应给出不同分布
        u = bootstrap_precision(rows, "UNTARGETED", .5, repeats=40, seed=7)
        self.assertNotEqual((a["median"], a["p2_5"], a["p97_5"]),
                            (u["median"], u["p2_5"], u["p97_5"]))
        self.assertLessEqual(a["min"], a["p2_5"])
        self.assertLessEqual(a["p2_5"], a["median"])
        self.assertLessEqual(a["median"], a["p97_5"])
        self.assertLessEqual(0., a["min"])
        self.assertGreaterEqual(1., a["p97_5"])
        self.assertNotIn("episode_id", str(a))

    def test_bootstrap_single_cluster_is_constant(self):
        # 单一 episode:重采样恒为原样本的整簇复制 → precision 无方差
        rows = [row(i >= 1, ep="only", lift=.05 + .01 * i) for i in range(3)]
        a = bootstrap_precision(rows, "PEAK_LIFT", .5, repeats=20, seed=1)
        self.assertEqual(a["min"], a["p97_5"])
        self.assertEqual(a["median"], 1.0)

    def test_bootstrap_uses_episode_clusters(self):
        # 两 episode 标签相反:聚类重采样会整簇复制 → 0 与 1 都出现
        rows = [row(True, ep="pos1", lift=.10), row(True, ep="pos1", lift=.09),
                row(False, ep="neg1", lift=.08), row(False, ep="neg1", lift=.07)]
        a = bootstrap_precision(rows, "PEAK_LIFT", .5, repeats=40, seed=1)
        self.assertEqual(a["min"], 0.0)
        self.assertEqual(a["p97_5"], 1.0)

    def test_jackknife_reports_worst_single_episode(self):
        rows = population()
        j = jackknife_episodes(rows, "PEAK_LIFT", .5)
        self.assertEqual(j["n_episodes"], 2)
        # 全量 Top6 = 5 正/6 → 0.8333
        self.assertAlmostEqual(j["full_precision"], .8333, places=4)
        # 拿掉 ep1(task9):剩 task3 六行,Top3 = .10正/.09正/.08负 → 2/3
        self.assertAlmostEqual(j["min_leave_one_out_precision"],
                               round(2 / 3, 4), places=4)
        # 拿掉 ep2(task3):剩 task9 六行,Top3 = .10/.09/.08 全正 → 1.0
        self.assertAlmostEqual(j["max_leave_one_out_precision"], 1., places=4)
        self.assertAlmostEqual(j["max_abs_delta"], round(1 / 6, 4), places=4)
        self.assertGreaterEqual(j["max_abs_delta"], 0.)

    def test_jackknife_identical_rows_not_double_dropped(self):
        # 同 episode 内两行内容完全一致:索引剔除保证只删本 episode 的两行
        twin = row(True, ep="dup", lift=.09)
        rows = [dict(twin), dict(twin)]
        rows += [row(False, ep="o1", lift=.05), row(False, ep="o2", lift=.04),
                 row(False, ep="o3", lift=.03)]
        j = jackknife_episodes(rows, "PEAK_LIFT", .5)
        self.assertEqual(j["n_episodes"], 4)
        # 拿掉 dup 后剩 3 行全负 → precision 0;全量 Top3 含 2 正 → ≥0
        self.assertEqual(j["min_leave_one_out_precision"], 0.)

    def test_score_levels_shape_and_no_ids(self):
        levels = score_levels(population())
        self.assertEqual(set(levels), {"3", "9"})
        for task, entry in levels.items():
            self.assertIn("n", entry)
            self.assertIn("LIFT_MINUS_GAP_pos", entry)
            self.assertIn("PEAK_LIFT_neg", entry)
        # 两任务内高分=正例:中位正例分数 > 中位负例分数
        self.assertGreater(levels["9"]["PEAK_LIFT_pos"],
                           levels["9"]["PEAK_LIFT_neg"])
        self.assertGreater(levels["3"]["PEAK_LIFT_pos"],
                           levels["3"]["PEAK_LIFT_neg"])
        self.assertNotIn("episode_id", str(levels))
        self.assertNotIn("ep1", str(levels))


if __name__ == "__main__":
    unittest.main()
