"""Synthetic-only local RGB observability review tests; no simulator/GPU."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import p1_dev0_visual_annotation as a


def fixture(root):
    # TemporaryDirectory() already creates this directory. Fixture must be idempotent.
    root.mkdir(parents=True, exist_ok=True)
    cases = []
    for i in range(5):
        key = f"p1dev0_t3_s{1001+i}"
        file = root / f"{key}_paired_rgb.png"
        file.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([i]) * 30)
        cases.append({"episode_key": key, "task": 3, "arm": "D1",
                      "board_name": file.name})
    (root / "review_index.json").write_text(json.dumps({
        "status": "PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER",
        "n_boards": 5, "cases": cases
    }), encoding="utf-8")
    return cases


def all_unknown(rows):
    return {
        "protocol": a.PROTOCOL,
        "items": [
            {"episode_key": r["episode_key"],
             **{k: "unknown" for k in a.CHOICES},
             "notes": ""}
            for r in rows
        ],
    }


class AnnotatorTests(unittest.TestCase):
    def test_build_is_self_contained_and_no_remote_url(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            fixture(out)
            html = a.build(out)
            data = html.read_text(encoding="utf-8")
            self.assertEqual(data.count("data:image/png;base64,"), 5)
            self.assertEqual(data.count('class="case"'), 5)
            self.assertNotIn("<script src=", data)
            self.assertNotIn("<iframe", data)
            self.assertIn("导出本地视觉标注 JSON", data)
            self.assertIn("object_gripper_relation_post", data)
            self.assertNotIn("https://", data)

    def test_summary_all_unknown_is_not_grasp_truth(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            rows = fixture(out)
            labels = out / "visual_labels.json"
            labels.write_text(json.dumps(all_unknown(rows)), encoding="utf-8")
            summary = a.summarize(out, labels)
            self.assertEqual(summary["n_episodes"], 5)
            self.assertEqual(summary["unresolved_target_visibility_post"], 5)
            self.assertEqual(summary["counts"]["confidence"]["unknown"], 5)
            self.assertIn("NOT_GROUND_TRUTH", summary["status"])
            self.assertEqual(summary["annotation_file_sha256"],
                             hashlib.sha256(labels.read_bytes()).hexdigest())
            self.assertTrue((out / "visual_observability_summary.json").exists())

    def test_rejects_unknown_key_and_unapproved_category(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            rows = fixture(out)
            labels = out / "visual_labels.json"
            payload = all_unknown(rows)
            payload["items"][0]["episode_key"] = "t99_external"
            labels.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown/duplicate"):
                a.summarize(out, labels)
            payload = all_unknown(rows)
            payload["items"][0]["object_gripper_relation_post"] = "actually_grasped"
            labels.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid visual label"):
                a.summarize(out, labels)

    def test_rejects_path_traversal_in_index(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            rows = fixture(out)
            rows[0]["board_name"] = "../secrets.png"
            (out / "review_index.json").write_text(json.dumps({
                "status": "PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER",
                "cases": rows
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                a.build(out)


if __name__ == "__main__":
    unittest.main()
