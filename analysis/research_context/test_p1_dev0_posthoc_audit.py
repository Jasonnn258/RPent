"""Synthetic-only regression test for P1-DEV0 posthoc audit; no env/model."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_dev0_posthoc_audit as qa
from p1_dev0_manifest import manifest, write_sealed


def emit(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r)+"\n" for r in records), encoding="utf-8")


class PosthocAuditTest(unittest.TestCase):
    def test_no_events_not_mislabelled_infra_and_horizon(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = manifest()
            # One triggered D1 and one triggered D3, 22 manifest cells absent.
            d1 = next(r for r in rows if r["arm"] == "D1")
            d3 = next(r for r in rows if r["arm"] == "D3")
            legal = {
                "arm": "D1", "tool_success": False,
                "terminal": False, "truncated": False,
                "pre_eef_z": .20, "post_eef_z": .20,
                "post_gripper_gap": .08, "age_env_steps": 0,
                "probe_performed": True,
                "visual_frame_available": True,
                "budget_remaining_env_steps": 1000,
            }
            for i, row in enumerate((d1, d3)):
                inputs = dict(legal, arm=row["arm"])
                events = [
                    {"ev": "init"},
                    {"ev": "trigger", "env_steps": 100},
                    {"ev": "probe", "env_steps_cost": 10,
                     "post_legal": {"gripper_gap": .08, "eef_z": .20}},
                    {"ev": "decision", "decision": "RETRY",
                     "policy_input": inputs},
                    {"ev": "action", "kind": "RETRY"},
                    {"ev": "audit",
                     "kind": "FIXED_HORIZON" if i == 0 else "EPISODE_END",
                     "overshoot_env_steps": 7 if i == 0 else -55,
                     "audit_only": {"check_success": i == 0}},
                    {"ev": "episode_end"},
                ]
                emit(root/"runs"/row["episode_key"]/"p1_dev0_events.jsonl", events)
            (root/"run_20261009_summary.json").write_text(
                json.dumps({"final": {"budget_final": {"gpu_s": 22215}}}),
                encoding="utf-8")
            report = qa.audit(rows, root)
            den = report["denominators"]
            self.assertEqual(den["allocated"], 24)
            self.assertEqual(den["with_events"], 2)
            self.assertEqual(den["not_started_or_unrecorded"], 22)
            self.assertEqual(den["untriggered_observed"], 0)
            self.assertEqual(den["missing_event_reason"], "UNDETERMINED_FROM_EVENT_FILE_ALONE")
            self.assertTrue(den["do_not_infer_infra_from_missing"])
            self.assertEqual(report["horizon"]["fixed_overshoot_steps"], [7])
            self.assertEqual(report["horizon"]["early_exit_shortfall_steps"], [55])
            self.assertEqual(report["runner_budget"]["over_budget_seconds"], 615)
            self.assertFalse(report["runner_budget"]["hard_budget_pass"])
            self.assertEqual(report["science_gate"], "HOLD_NO_ARM_ACTION_CONTRAST")
            self.assertEqual(report["shadow_not_causal"]["n_probe_snapshots_checked"],
                             2)
            di = report["shadow_not_causal"]["diagnostic_not_physical_truth"]
            self.assertEqual(di["finite_gripper_gap"], 2)
            self.assertEqual(di["post_gap_lt_0p06"], 0)
            self.assertEqual(di["finite_eef_z_delta"], 2)
            self.assertEqual(di["eef_z_delta_ge_0p03"], 0)
            self.assertEqual(di["probe_vs_policy_input_mismatch"], 0)
            self.assertEqual(di["probe_legal_not_recorded"], 0)

    def test_manifest_sha_seal_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            rows = manifest()
            write_sealed(out, rows, 187)
            self.assertEqual(
                qa.verified_manifest(out / "manifest.jsonl",
                                     out / "manifest.sha256.json"), rows
            )
            # A changed assignment after the outcome cannot be substituted.
            rows[0]["arm"] = "D3" if rows[0]["arm"] != "D3" else "D0"
            (out / "manifest.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"))+"\n" for r in rows),
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "FROZEN_MANIFEST_SHA_MISMATCH"):
                qa.verified_manifest(out / "manifest.jsonl",
                                     out / "manifest.sha256.json")

    def test_unknown_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            rows = manifest()
            rows[0]["arm"] = "D4"
            with self.assertRaisesRegex(ValueError, "Unknown arm"):
                qa.audit(rows, Path(td))

    def test_malformed_duplicate_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            rows = manifest()
            rows[-1]["episode_key"] = rows[0]["episode_key"]
            with self.assertRaisesRegex(ValueError, "distinct"):
                qa.audit(rows, Path(td))


if __name__ == "__main__":
    unittest.main()
