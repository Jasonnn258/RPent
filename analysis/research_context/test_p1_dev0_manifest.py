"""Pure unit tests for P1-DEV0 24-episode manifest; no simulator."""
import csv
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_dev0_manifest as m


class ManifestTest(unittest.TestCase):
    def test_balanced_stratified_frozen(self):
        a = m.manifest()
        b = m.manifest()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)
        self.assertEqual(
            Counter((x["task"], x["arm"]) for x in a),
            {(task, arm): 2 for task in m.TASKS for arm in m.ARMS},
        )
        self.assertTrue(all(x["max_probe_events"] == 1 for x in a))
        self.assertFalse(any(121 <= x["seed"] <= 190 for x in a))

    def test_reject_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "analysis"
            p.mkdir()
            csv_path = p / "stageR_collect_ledger.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["task", "seed"])
                writer.writeheader()
                writer.writerow({"task": 3, "seed": 1001})
            with self.assertRaisesRegex(ValueError, "Overlap"):
                m.historical_collision_check(Path(tmp), m.manifest())

    def test_idempotent_and_tamper_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rows = m.manifest()
            first = m.write_sealed(out, rows, 187)
            second = m.write_sealed(out, rows, 187)
            self.assertEqual(first["status"], "NEW_SEAL_WRITTEN")
            self.assertEqual(second["status"], "EXISTING_SEAL_IDENTICAL")
            self.assertEqual(
                first["sha256"], m.digest((out / "manifest.jsonl").read_bytes())
            )
            self.assertEqual(
                len([json.loads(x) for x in
                     (out / "manifest.jsonl").read_text().splitlines()]), 24
            )
            with (out / "manifest.jsonl").open("a") as f:
                f.write("{}\n")
            with self.assertRaisesRegex(RuntimeError, "differs"):
                m.write_sealed(out, rows, 187)

    def test_invalid_allocation(self):
        r = m.manifest()
        r[0] = {**r[0], "arm": r[1]["arm"]}
        # If first and second coincidentally same arm, force a wrong one.
        r[0]["arm"] = "D0" if r[0]["arm"] != "D0" else "D1"
        with self.assertRaises(ValueError):
            m.check_manifest(r)


if __name__ == "__main__":
    unittest.main()
