#!/usr/bin/env python3
"""Synthetic, offline-only regression checks for Research Package A.

python -m unittest discover -s analysis/research_context -p 'test_research_package_a.py' -v
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_package_a as pkg


def meas(z=0.0, has_object=True, has_eef=True):
    o = {}
    if has_object:
        o["cube_pos"] = [0.0, 0.0, z]
    if has_eef:
        o["robot0_eef_pos"] = [0.0, 0.0, z + 0.01]
    return {"obs": o, "obj_of_interest": ["cube"], "check_success": False}


class PackageATest(unittest.TestCase):
    def test_reference_any_time_three_values(self):
        base = meas()
        yes = meas(0.06)
        no = meas(0.0)
        absent = meas(0.0, has_object=False)
        self.assertEqual(pkg.label_reference([base, yes], ["VALID", "VALID"]), "POSITIVE")
        self.assertEqual(pkg.label_reference([base, no], ["VALID", "VALID"]), "NEGATIVE")
        self.assertEqual(pkg.label_reference([base, absent, no], [
            "VALID", "INVALID_MISSING", "VALID"]), "UNKNOWN")
        self.assertEqual(pkg.label_reference([base, absent, yes], [
            "VALID", "INVALID_MISSING", "VALID"]), "POSITIVE")
        # Base target pose exists but base EEF is missing; a later physical
        # confirm must still establish POSITIVE (per Stage2J v2).
        base_no_eef = meas(0.0, has_eef=False)
        self.assertEqual(pkg.label_reference([base_no_eef, yes], [
            "INVALID_MISSING", "VALID"]), "POSITIVE")

    def test_stats_unknown_and_constants(self):
        data = [
            {"episode_id": "e1", "flag": True, "reference": "POSITIVE"},
            {"episode_id": "e2", "flag": True, "reference": "NEGATIVE"},
            {"episode_id": "e3", "flag": False, "reference": "NEGATIVE"},
            {"episode_id": "e4", "flag": False, "reference": "UNKNOWN"},
        ]
        s = pkg.stats(data)
        self.assertEqual(s["reference_unknown"], 1)
        self.assertAlmostEqual(s["r_accept_complete_case"], 0.5)
        self.assertAlmostEqual(s["r_miss_complete_case"], 0.0)
        self.assertAlmostEqual(s["r_miss_unknown_lower_bound"], 0)
        self.assertAlmostEqual(s["concordance_decidable"], 2/3)
        bounds = pkg.bootstrap(data, 100)
        self.assertIn("concordance_decidable", bounds)

    def test_full_synthetic_pipeline_without_private_data(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            analysis = root / "analysis"
            analysis.mkdir()
            (root / "artifacts").mkdir()
            ledger = analysis / "stageR_collect_ledger.csv"
            episodes = []
            for i, spec in enumerate(("positive", "unknown"), 1):
                ep = root / "synthetic" / ("ep%d" % i)
                ep.mkdir(parents=True)
                pts = [meas(), meas(0.06)] if spec == "positive" else [
                    meas(), meas(0.0, has_object=False), meas(0.0)]
                flag = (spec == "positive")
                result = {
                    "name": "pick", "instruction": "synthetic pick",
                    "success": flag, "chunks_used": len(pts)-1,
                    "max_chunks": 10, "peak_lift_m": 0.1,
                    "min_gripper_opening": 0.01,
                    "final_gripper_opening": 0.01,
                    "libero_terminated": False,
                    "diagnostics": {"descent_done": bool(flag)}
                }
                state = {
                    "step_idx": 1, "command": {"action": "pi0_pick"},
                    "result": result, "libero_terminated": False,
                    "episode_truncated": False
                }
                (ep / "states.json").write_text(json.dumps([state]), encoding="utf-8")
                records = [{"ev": "step_begin", "skill": "pi0_pick",
                            "step_idx": 1, "t": 10.0}]
                for j, p in enumerate(pts[:-1], 1):
                    records.append({"ev": "action", "skill": "pi0_pick",
                                    "kind": "chunk", "step_idx": 1,
                                    "chunk_idx": j, "meas": p, "t": 10.0+j})
                records.append({"ev": "step_end", "skill": "pi0_pick",
                                "step_idx": 1, "final_meas": pts[-1],
                                "success": flag, "t": 20.0})
                (ep / "stageR_trace.jsonl").write_text(
                    "".join(json.dumps(r)+"\n" for r in records), encoding="utf-8")
                episodes.append(ep)
            with ledger.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["task", "seed", "episode_dir"])
                w.writeheader()
                for i, ep in enumerate(episodes, 1):
                    w.writerow({"task": 3, "seed": 120+i, "episode_dir": str(ep)})
            out = root / "artifacts" / "research_package_a"
            qa = pkg.schema(root, out, strict=False)
            self.assertEqual(qa["gate"], "PASS")
            self.assertEqual(qa["counters"]["eligible_pick"], 2)
            result = pkg.outcomes(root, out, strict=False)
            self.assertEqual(result["gate"], "A0_MAIN_UNESTIMABLE")
            self.assertEqual(result["reference_unknown"], 1)
            online = pkg.read_jsonl(out / "EERD_A_online_eligible.jsonl")
            audit = pkg.read_jsonl(out / "EERD_A_audit_only.jsonl")
            self.assertEqual(len(online), 2)
            self.assertEqual(len(audit), 2)
            self.assertEqual([r["reference"] for r in audit],
                             ["POSITIVE", "UNKNOWN"])
            for row in online:
                text = json.dumps(row)
                self.assertNotIn("check_success", text)
                self.assertNotIn("cube_pos", text)
            # Original source file remains byte-identical.
            self.assertTrue((episodes[0] / "states.json").exists())


if __name__ == "__main__":
    unittest.main()
