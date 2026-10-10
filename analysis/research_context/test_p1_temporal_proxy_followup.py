"""Pure synthetic tests for the exit-horizon rescoring followup. No real data."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_temporal_proxy_followup as f


def row(ep, task, flag, ref_any, ref_term, pattern, start=1.1, descent=0.05):
    return {"episode_id": ep, "task": task, "flag": flag,
            "reference_any": ref_any, "reference_terminal": ref_term,
            "terminal_unknown": False, "gate_pattern": pattern,
            "start_eef_z": start, "descent_m": descent}


def fixture():
    """101 TP + 2 FP + 33 D-only FN (24 persistent) + 23 L/G-missing FN
    (2 persistent) + 47 TN (5 of them gate pattern 011, mirroring the real
    frozen composition that gives L_AND_Gfinal FP=7=2+5 on the any horizon),
    spread over episodes/tasks like the real data."""
    rows = []
    for i in range(101):
        rows.append(row(f"e{i % 90:03d}", "3", True, True, True, "111"))
    for i in range(2):
        rows.append(row(f"p{i}", "5", True, False, False, "111"))
    for i in range(33):
        rows.append(row(f"d{i % 20:03d}", "9" if i % 3 else "5",
                        False, True, i < 24, "011"))
    for i in range(23):
        rows.append(row(f"m{i % 15:03d}", "5" if i % 2 else "3",
                        False, True, i < 2, "101"))
    for i in range(42):
        rows.append(row(f"t{i % 40:03d}", "9", False, False, False, "000"))
    for i in range(5):
        rows.append(row(f"z{i}", "9", False, False, False, "011"))
    return rows


class FollowupTests(unittest.TestCase):
    def test_arm_predict_frozen_and_rejects_unknown(self):
        r = row("e", "9", False, True, True, "011")
        self.assertTrue(f.arm_predict(r, "L_AND_Gfinal"))
        self.assertFalse(f.arm_predict(r, "flag"))
        r2 = row("e", "9", False, True, True, "001")
        self.assertFalse(f.arm_predict(r2, "L_AND_Gfinal"))
        with self.assertRaisesRegex(ValueError, "Unknown frozen arm"):
            f.arm_predict(r, "Gmin_only")

    def test_confusion_math_both_horizons(self):
        rows = fixture()
        any_h = f.confusion(rows, "flag", "any")
        self.assertEqual((any_h["tp"], any_h["fp"], any_h["fn"], any_h["tn"]),
                         (101, 2, 56, 47))
        term = f.confusion(rows, "flag", "terminal")
        self.assertEqual((term["tp"], term["fp"], term["fn"], term["tn"]),
                         (101, 2, 26, 77))
        # L_AND_Gfinal predicts success on every 011/111 row.
        lg = f.confusion(rows, "L_AND_Gfinal", "terminal")
        self.assertEqual(lg["tp"], 125)
        self.assertEqual(lg["fp"], 16)
        self.assertEqual(lg["fn"], 2)
        self.assertEqual(lg["tn"], 63)

    def test_fn_decomposition_frozen_denominators(self):
        dec = f.fn_decomposition(fixture())
        self.assertEqual(dec["n_fn"], 56)
        self.assertEqual(dec["n_exit_persistent"], 26)
        self.assertEqual(dec["n_transient"], 30)
        self.assertEqual(dec["n_terminal_unknown"], 0)
        self.assertEqual(dec["exit_persistent_fn_pattern"], {"011": 24, "101": 2})
        self.assertEqual(dec["d_only_fn"]["n"], 33)
        self.assertAlmostEqual(dec["d_only_fn"]["exit_persistent_rate"],
                               24 / 33, places=3)
        self.assertAlmostEqual(dec["lg_missing_fn"]["exit_persistent_rate"],
                               2 / 23, places=3)
        with self.assertRaisesRegex(ValueError, "denominator"):
            f.fn_decomposition(fixture()[:50])

    def test_hypothesis_gate_passes_on_fixture(self):
        h = f.hypothesis_gate(fixture())
        self.assertTrue(h["H_a_flag_confusions_stable"])
        self.assertTrue(h["H_b_persistent_fn_mostly_d_only"])
        self.assertTrue(h["H_c_persistence_split"])
        self.assertTrue(h["H_T2_drop_d_gain_is_horizon_artifact"])

    def test_hypothesis_gate_fails_when_split_changes(self):
        rows = fixture()
        # Flip persistence: make most D-only FNs transient.
        for i, r in enumerate(rows):
            if r["gate_pattern"] == "011" and not r["flag"]:
                r["reference_terminal"] = i % 3 == 0
        h = f.hypothesis_gate(rows)
        self.assertFalse(h["H_b_persistent_fn_mostly_d_only"])
        self.assertFalse(h["H_c_persistence_split"])

    def test_bootstrap_deterministic_and_sign(self):
        rows = fixture()
        a = f.paired_bootstrap(rows, repeats=60, seed=7)
        b = f.paired_bootstrap(rows, repeats=60, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(a["n_valid"], 60)
        self.assertGreaterEqual(a["frac_ge0"], 0.0)
        self.assertLessEqual(a["p2_5"], a["median"] + 1e-9)

    def test_donly_geometry_none_safe_and_private(self):
        rows = fixture()
        rows[0]["start_eef_z"] = None      # only on a pattern-111 row: ignored
        for r in rows:
            if r["gate_pattern"] == "011" and r["task"] == "9":
                r["start_eef_z"] = None if r["reference_terminal"] else 1.2
        geo = f.donly_geometry(rows)
        self.assertIn("9", geo)
        self.assertEqual(geo["9"]["exit_persistent"]["median_start_eef_z"], None)
        self.assertEqual(geo["9"]["transient"]["median_start_eef_z"], 1.2)
        self.assertNotIn("e0", str(geo))
        self.assertNotIn("episode_id", str(geo))

    def test_privacy_no_ids_in_result_shapes(self):
        dec = f.fn_decomposition(fixture())
        h = f.hypothesis_gate(fixture())
        geo = f.donly_geometry(fixture())
        blob = str([dec, h, geo])
        for banned in ("episode_id", "e00", "target_pos"):
            self.assertNotIn(banned, blob)


if __name__ == "__main__":
    unittest.main()
