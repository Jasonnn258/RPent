#!/usr/bin/env python3
"""Prepare LOCAL/PRIVATE, aligned visual review boards from frozen P1 DEV0 RGB.

No model, simulator, training, controller, segmentation, audit-only object
position, or action. A pixel difference is NOT proof of object grasp.
Produces 5 two-row boards of 6 views if the frozen cohort is complete:

 row 1: agentview(pre, post, absdiff)
 row 2: wrist(pre stored-flipped, post vertically-flipped for match, absdiff)

Use only already SHA-verified matching pre/post PNG pairs; output is in
gitignored artifacts/p1_dev0/visual_review/. Never commit image boards.

python3 scripts/p1_dev0_visual_review.py \
  --out-root /workspace/yjx/rpent_data/p1_dev0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def aligned_arrays(pre, post, camera):
    """Return aligned uint8 RGB images and a descriptive absolute difference.

    Camera storage convention is derived from original RPent source code:
    pre wrist = raw_wrist[::-1], post wrist = raw_wrist. Therefore post wrist
    must flip vertically before comparing stored pre/post pixel coordinates.
    Camera motion, changing gripper geometry and occlusion remain confounds.
    """
    import numpy as np

    a = np.asarray(pre)
    b = np.asarray(post)
    if camera not in ("agentview", "wrist"):
        raise ValueError("unsupported camera")
    if (a.dtype != np.uint8 or b.dtype != np.uint8 or
            a.ndim != 3 or b.ndim != 3 or
            a.shape[-1] not in (3, 4) or b.shape[-1] not in (3, 4)):
        raise ValueError("expected uint8 RGB/RGBA arrays; do not coerce silently")
    a, b = a[:, :, :3], b[:, :, :3]
    if a.shape != b.shape:
        raise ValueError("pre/post image shape mismatch")
    if camera == "wrist":
        b = b[::-1, :, :].copy()
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.uint8)
    return a, b, diff


def make_boards(out_root: Path, manifest: list[dict], output: Path):
    import imageio.v2 as imageio
    import numpy as np
    from p1_dev0_visual_pair_preflight import CAMS, evaluate, artifact_status, read_jsonl

    qa = evaluate(out_root, manifest)
    if qa["gate"] != "PAIRED_ASSETS_COMPLETE":
        raise RuntimeError("Visual file provenance/whole-cohort gate not PASS")
    # A supplementary private derived artifact. No original event/PNG editing.
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in manifest:
        key = case["episode_key"]
        evs = read_jsonl(out_root / "runs" / key / "p1_dev0_events.jsonl")
        trigger = next((x for x in evs if x.get("ev") == "trigger"), None)
        probe = next((x for x in evs if x.get("ev") == "probe"), None)
        if not trigger or not probe:
            continue
        pre = {x.get("name"): x for x in trigger.get("pre_images", [])}
        post = {x.get("name"): x for x in probe.get("post_frames", [])}
        panels = []
        measurements = {}
        for camera in ("agentview", "wrist"):
            k1, k2 = CAMS[camera]
            src_a, src_b = pre.get(k1), post.get(k2)
            if not artifact_status(src_a)["ok"] or not artifact_status(src_b)["ok"]:
                raise RuntimeError("Missing/changed source image after verification")
            a = imageio.imread(src_a["path"])
            b = imageio.imread(src_b["path"])
            a, b, diff = aligned_arrays(a, b, camera)
            panels.append(np.concatenate((a, b, diff), axis=1))
            measurements[camera] = {
                "mean_absolute_pixel_difference": round(float(diff.mean()), 4),
                "pixel_fraction_absdiff_gt_20": round(
                    float((diff.max(axis=2) > 20).mean()), 6),
                "shape": list(a.shape),
                "wrist_post_flipped_vertically": camera == "wrist",
            }
        if panels[0].shape[1] != panels[1].shape[1]:
            raise ValueError("agentview and wrist dimensions differ; no rescaling")
        # Different camera image heights are common; pad the shorter ROW to
        # a common width was already enforced; vertical stacking needs no pad.
        board = np.concatenate(panels, axis=0)
        dest = output / f"{key}_paired_rgb.png"
        imageio.imwrite(dest, board)
        rows.append({"episode_key": key, "arm": case["arm"], "task": case["task"],
                     "board_name": dest.name, "descriptive_only": measurements})
    if len(rows) != 5:
        raise RuntimeError("Expected five probed episodes; check source integrity")
    report = {
        "status": "PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER",
        "n_boards": len(rows),
        "layout": "top row agentview pre/post/absdiff; bottom row wrist pre/vertically-aligned-post/absdiff",
        "caution": "These are raw pixel changes, confounded by robot/gripper motion. "
                   "No target detection, valid held-object reference or causal benefit was calculated.",
        "cases": rows,
    }
    (output / "review_index.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-root", type=Path,
                   default=Path("/workspace/yjx/rpent_data/p1_dev0"))
    p.add_argument("--manifest", type=Path,
                   default=REPO / "artifacts" / "p1_dev0" / "manifest.jsonl")
    p.add_argument("--seal", type=Path,
                   default=REPO / "artifacts" / "p1_dev0" / "manifest.sha256.json")
    p.add_argument("--output", type=Path,
                   default=REPO / "artifacts" / "p1_dev0" / "visual_review")
    args = p.parse_args()
    if not args.output.resolve().is_relative_to((REPO / "artifacts").resolve()):
        p.error("Private review output must remain under gitignored artifacts/")
    from p1_dev0_posthoc_audit import verified_manifest
    report = make_boards(args.out_root, verified_manifest(args.manifest, args.seal),
                         args.output)
    print(json.dumps({
        "status": report["status"], "n_boards": report["n_boards"],
        "output_dir": str(args.output), "layout": report["layout"],
        "caution": report["caution"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
