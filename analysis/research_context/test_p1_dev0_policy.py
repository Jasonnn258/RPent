"""Pure D2 decision contract tests; no simulator, no tool calls."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_dev0_policy import LegalEvidence, choose, deny_privileged_payload


class P1PolicyTest(unittest.TestCase):
    def setUp(self):
        self.e = LegalEvidence(
            arm="D0", tool_success=False, terminal=False, truncated=False,
            pre_eef_z=0.24, post_eef_z=0.30, post_gripper_gap=0.02,
            age_env_steps=1, probe_performed=False,
            visual_frame_available=True, budget_remaining_env_steps=5,
        )

    def test_blind_retry_same_policy_even_if_probe_changes_physics(self):
        d0 = choose(self.e)
        d1 = choose(replace(self.e, arm="D1", probe_performed=True,
                            post_gripper_gap=0.07, post_eef_z=0.14))
        self.assertEqual(d0.decision, "RETRY")
        self.assertEqual(d0, d1)
        self.assertEqual(d0.evidence_sources, ("tool_result.success",))

    def test_static_probe(self):
        e = replace(self.e, arm="D2", probe_performed=True)
        self.assertEqual(choose(e).decision, "CONTINUE_CAUTION")
        self.assertEqual(choose(replace(e, post_gripper_gap=0.07)).decision,
                         "RETRY")
        with self.assertRaisesRegex(ValueError, "requires"):
            choose(replace(e, probe_performed=False))

    def test_evidence_policy_abstains_on_stale_or_missing(self):
        e = replace(self.e, arm="D3", probe_performed=True)
        self.assertEqual(choose(e).decision, "CONTINUE_CAUTION")
        self.assertEqual(choose(replace(e, age_env_steps=5)).decision,
                         "ABSTAIN")
        self.assertEqual(choose(replace(e, visual_frame_available=False)).decision,
                         "ABSTAIN")
        self.assertEqual(choose(replace(e, budget_remaining_env_steps=0)).decision,
                         "ABSTAIN")

    def test_invalid_trigger(self):
        with self.assertRaises(ValueError):
            choose(replace(self.e, terminal=True))
        with self.assertRaises(ValueError):
            choose(replace(self.e, tool_success=True))
        with self.assertRaises(ValueError):
            choose(replace(self.e, arm="INVALID"))

    def test_privileged_truth_denied(self):
        deny_privileged_payload({"state": {"robot0_eef_pos": [0, 0, 0]},
                                "log": {"result": {"success": False}}})
        for key in ("check_success", "reference", "sim_measurement",
                    "target_pos", "reconstruction_metadata"):
            with self.assertRaisesRegex(ValueError, "PRIVILEGED_POLICY_INPUT"):
                deny_privileged_payload({"nested": [{"nested": {key: 3}}]})


if __name__ == "__main__":
    unittest.main()
