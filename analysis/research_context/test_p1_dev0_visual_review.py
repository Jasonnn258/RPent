"""Synthetic, no-simulator tests for RGB review board alignment and gate."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import imageio.v2 as imageio

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_dev0_manifest import manifest
from p1_dev0_visual_review import aligned_arrays, make_boards


def fake_png(path, img):
    path.parent.mkdir(parents=True, exist_ok=True)
    imageio.imwrite(path, img)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class VisualReviewTest(unittest.TestCase):
    def test_wrist_post_vertical_flip_undoes_storage_mismatch(self):
        pre = np.zeros((4, 5, 3), dtype=np.uint8)
        pre[0, :, :] = 150
        post_raw = pre[::-1, :, :].copy()
        a, b, diff = aligned_arrays(pre, post_raw, "wrist")
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(int(diff.sum()), 0)
        _, _, agent_diff = aligned_arrays(pre, post_raw, "agentview")
        self.assertGreater(int(agent_diff.sum()), 0)

    def test_real_decode_panels_from_synthetic_frozen_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = manifest()
            for i, row in enumerate(rows[:21]):
                ep = root / "runs" / row["episode_key"]
                ep.mkdir(parents=True)
                events = [{"ev": "episode_end"}]
                if i < 6:
                    pre_images, post_frames = [], []
                    if i < 5:
                        for camera, before, after in (
                            ("agent", "policy_image_agentview_low", "probe_agentview"),
                            ("wrist", "image_wrist_low", "probe_wrist"),
                        ):
                            a = np.zeros((8, 8, 3), dtype=np.uint8)
                            a[0:2, :, :] = 120
                            b = np.copy(a)
                            b[4, :, :] = 40
                            pre_images.append({"name": before, **fake_png(
                                root / f"{row['episode_key']}_{camera}_pre.png", a)})
                            post_frames.append({"name": after, **fake_png(
                                root / f"{row['episode_key']}_{camera}_post.png", b)})
                    events.insert(0, {"ev": "trigger", "pre_images": pre_images})
                    if i < 5:
                        events.insert(1, {"ev": "probe", "post_frames": post_frames})
                (ep / "p1_dev0_events.jsonl").write_text(
                    "".join(json.dumps(e)+"\n" for e in events), encoding="utf-8")
            out = root / "private_boards"
            report = make_boards(root, rows, out)
            self.assertEqual(report["n_boards"], 5)
            self.assertEqual(len(list(out.glob("*_paired_rgb.png"))), 5)
            example = imageio.imread(next(out.glob("*_paired_rgb.png")))
            self.assertEqual(example.shape, (16, 24, 3))
            self.assertEqual(report["status"], "PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER")

    def test_bad_camera_does_not_silently_flip(self):
        a = np.zeros((2, 2, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            aligned_arrays(a, a, "camera3")


if __name__ == "__main__":
    unittest.main()
