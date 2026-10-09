#!/usr/bin/env python3
"""Pure, synthetic P1 D2 preflight regression tests. No simulator/runtime."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_d2_preflight import evaluate, vec_valid


class D2PreflightTest(unittest.TestCase):
    def test_proprio_finiteness(self):
        self.assertTrue(vec_valid([0, 0.02, -0.14], 3))
        self.assertFalse(vec_valid([0, float("nan"), 0], 3))
        self.assertFalse(vec_valid([0, 1], 3))
        self.assertFalse(vec_valid("[0, 1, 2]", 3))

    def test_existing_data_only_and_archive_caveat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ep = root / "logs" / "sample_episode"
            ep.mkdir(parents=True)
            (root / "analysis").mkdir()
            (root / "analysis" / "stageR_collect_ledger.csv").write_text(
                "task,seed,episode_dir\n3,777,logs/sample_episode\n",
                encoding="utf-8")
            state = {
                "step_idx": 1, "command": {"action": "pi0_pick"},
                "result": {"success": False, "libero_terminated": False},
                "episode_truncated": False,
                "state": {"robot0_eef_pos": [0, 0, 0],
                          "robot0_eef_quat": [0, 0, 0, 1],
                          "robot0_gripper_qpos": [0.01, -0.01]},
            }
            (ep / "states.json").write_text(json.dumps([state]), encoding="utf-8")
            (ep / "images").mkdir()
            (ep / "images" / "image_01.png").write_bytes(b"\x89PNG")
            r = evaluate(root)
            self.assertEqual(r["gate"], "HOLD_SOURCE_OR_FLAG_MISMATCH")  # synthetic N
            self.assertEqual(r["counters"]["all_pick"], 1)
            self.assertEqual(r["counters"]["tool_failure"], 1)
            self.assertEqual(r["counters"]["archived_agentview_low_present"], 1)
            self.assertEqual(r["counters"]["archived_wrist_low_absent"], 1)
            self.assertEqual(r["counters"]["d2_proprio_robot0_eef_pos_valid"], 1)
            self.assertIn("older high-res frames may be pruned",
                          r["cannot_establish"][0])


if __name__ == "__main__":
    unittest.main()
