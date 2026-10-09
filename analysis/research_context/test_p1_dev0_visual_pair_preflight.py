"""Synthetic tests: pre/post legal image pair hashes and orientation warning.

Does not read private robot data, run an environment, decode image pixels,
or infer grasp success.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_dev0_manifest import manifest
import p1_dev0_visual_pair_preflight as v


def small_png_header(w=256, h=256):
    # This is deliberately just a PNG header: source function checks header
    # and hash, not full-image decoding.
    return v.PNG_HEADER + b"\x00\x00\x00\x0dIHDR" + w.to_bytes(4, "big") + h.to_bytes(4, "big")


def write_img(path, content=small_png_header()):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}


class PairAuditTests(unittest.TestCase):
    def test_sha_geometry_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "frame.png"
            r = write_img(p)
            self.assertEqual(v.artifact_status(r)["geometry"], (256, 256))
            self.assertTrue(v.artifact_status(r)["ok"])
            r["sha256"] = "bad"
            self.assertEqual(v.artifact_status(r)["why"], "SOURCE_SHA256_MISMATCH")
            self.assertEqual(v.artifact_status(None)["why"], "RECORD_MISSING")

    def test_paired_images_need_full_cohort_before_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = manifest()
            key = rows[0]["episode_key"]
            data = root / "runs" / key
            data.mkdir(parents=True)
            pre_a = write_img(root / "pre_agent.png")
            pre_w = write_img(root / "pre_wrist.png")
            post_a = write_img(root / "probe_agent.png")
            post_w = write_img(root / "probe_wrist.png")
            events = [
                {"ev": "trigger", "pre_images": [
                    {"name": "policy_image_agentview_low", **pre_a},
                    {"name": "image_wrist_low", **pre_w},
                ]},
                {"ev": "probe", "post_frames": [
                    {"name": "probe_agentview", **post_a},
                    {"name": "probe_wrist", **post_w},
                ]},
                {"ev": "episode_end"}
            ]
            (data/"p1_dev0_events.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in events), encoding="utf-8")
            report = v.evaluate(root, rows)
            self.assertEqual(report["counts"]["probe_events"], 1)
            self.assertEqual(report["counts"]["agentview_verified_pair"], 1)
            self.assertEqual(report["counts"]["wrist_verified_pair"], 1)
            self.assertEqual(report["gate"], "HOLD_COHORT_ACCOUNTING_MISMATCH")
            self.assertIn("vertical flip REQUIRED",
                          report["frame_contract"]["wrist"])

            # If a source image is changed, no pair can count as verified.
            (root/"probe_wrist.png").write_bytes(small_png_header(512, 512))
            new_report = v.evaluate(root, rows)
            self.assertEqual(new_report["counts"]["wrist_verified_pair"], 0)
            self.assertEqual(new_report["failure_reasons"]
                             ["wrist_post_SOURCE_SHA256_MISMATCH"], 1)

    def test_only_wrist_missing_does_not_crash_when_agent_is_valid(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            rows=manifest()
            ep=root/"runs"/rows[0]["episode_key"]
            ep.mkdir(parents=True)
            pre=write_img(root/"pre.png")
            post=write_img(root/"post.png")
            events=[
                {"ev":"trigger","pre_images":[
                    {"name":"policy_image_agentview_low", **pre},
                    {"name":"image_wrist_low","path":None,"missing":True}]},
                {"ev":"probe","post_frames":[
                    {"name":"probe_agentview", **post},
                    {"name":"probe_wrist","path":None,"missing":True}]},
            ]
            (ep/"p1_dev0_events.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in events), encoding="utf-8")
            report=v.evaluate(root,rows)
            self.assertEqual(report["counts"]["agentview_verified_pair"],1)
            self.assertEqual(report["failure_reasons"]["wrist_pre_PATH_OR_HASH_MISSING"],1)
            self.assertEqual(report["failure_reasons"]["wrist_post_PATH_OR_HASH_MISSING"],1)


if __name__ == "__main__":
    unittest.main()
