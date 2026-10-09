#!/usr/bin/env python3
"""Read-only availability/integrity check of P1-DEV0 pre/post probe RGB pairs.

This checks whether visual evidence exists and can be matched by camera, but
DOES NOT determine whether the gripper actually holds the target object.
It never loads sim object coordinates, writes images, runs a model, or rolls
out a simulator.

CRITICAL frame caveat from source:
- pre policy_image_agentview_low and post probe_agentview are produced from
  primitives._last_obs["main_images"], i.e. aligned stored image convention.
- pre image_wrist_low uses raw_obs["robot0_eye_in_hand_image"][::-1], whereas
  post probe_wrist writes raw_obs["robot0_eye_in_hand_image"] (NO flip).
  Flip one vertical axis before comparing wrist pixels. File existence does
  not demonstrate new semantic evidence, object visibility, or grasp success.

Use after the P1 DEV0 stage is CLOSED:
  python3 scripts/p1_dev0_visual_pair_preflight.py \
    --out-root /workspace/yjx/rpent_data/p1_dev0

Writes an aggregate-only report under gitignored artifacts/p1_dev0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CAMS = {
    "agentview": ("policy_image_agentview_low", "probe_agentview"),
    "wrist": ("image_wrist_low", "probe_wrist"),
}
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def read_jsonl(path: Path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_geometry(path: Path):
    """Header-level geometry only; this is not a full PNG pixel decode."""
    with path.open("rb") as f:
        header = f.read(24)
    if (len(header) != 24 or not header.startswith(PNG_HEADER)
            or header[12:16] != b"IHDR"):
        return None
    return (int.from_bytes(header[16:20], "big"),
            int.from_bytes(header[20:24], "big"))


def artifact_status(record: dict | None):
    if not isinstance(record, dict):
        return {"ok": False, "why": "RECORD_MISSING"}
    name = record.get("path")
    expected_sha = record.get("sha256")
    if not isinstance(name, str) or not name or not isinstance(expected_sha, str):
        return {"ok": False, "why": "PATH_OR_HASH_MISSING"}
    p = Path(name)
    if not p.is_file():
        return {"ok": False, "why": "ARCHIVED_FILE_ABSENT"}
    try:
        actual_sha = sha256(p)
        if actual_sha != expected_sha:
            return {"ok": False, "why": "SOURCE_SHA256_MISMATCH"}
        size = png_geometry(p)
        if not size or size[0] <= 0 or size[1] <= 0:
            return {"ok": False, "why": "PNG_HEADER_NOT_VALID"}
        return {"ok": True, "sha": actual_sha, "geometry": size}
    except (OSError, ValueError):
        return {"ok": False, "why": "IO_OR_FORMAT_ERROR"}


def evaluate(out_root: Path, manifest: list[dict]):
    # The original manifest is checked by the independent sealed-manifest
    # posthoc auditor. Here, use only its episode IDs; do not alter assignments.
    if len(manifest) != 24 or len({r["episode_key"] for r in manifest}) != 24:
        raise ValueError("P1_DEV0_FROZEN_MANIFEST_REQUIRED")
    counts = Counter()
    causes = Counter()
    for row in manifest:
        key = row["episode_key"]
        events = read_jsonl(out_root / "runs" / key / "p1_dev0_events.jsonl")
        if not events:
            counts["without_event_file"] += 1
            continue
        counts["with_event_file"] += 1
        triggers = [r for r in events if r.get("ev") == "trigger"]
        probes = [r for r in events if r.get("ev") == "probe"]
        if not triggers:
            counts["not_triggered"] += 1
            continue
        counts["triggered"] += 1
        if not probes:
            counts["triggered_without_probe"] += 1
            continue
        if len(probes) != 1 or len(triggers) != 1:
            counts["nonunique_trigger_or_probe"] += 1
            continue
        counts["probe_events"] += 1
        pre = {r.get("name"): r for r in triggers[0].get("pre_images", [])}
        post = {r.get("name"): r for r in probes[0].get("post_frames", [])}
        for camera, (before_key, after_key) in CAMS.items():
            a, b = artifact_status(pre.get(before_key)), artifact_status(post.get(after_key))
            counts[camera + "_pair_attempted"] += 1
            if not a["ok"] or not b["ok"]:
                if not a["ok"]:
                    causes[camera + "_pre_" + a["why"]] += 1
                if not b["ok"]:
                    causes[camera + "_post_" + b["why"]] += 1
                continue
            if a["geometry"] != b["geometry"]:
                causes[camera + "_geometry_mismatch"] += 1
                continue
            counts[camera + "_verified_pair"] += 1
            counts[camera + "_identical_file_hash"] += int(a["sha"] == b["sha"])
            counts[camera + "_different_file_hash"] += int(a["sha"] != b["sha"])
    n_probed = counts["probe_events"]
    # This gate is only file provenance/geometry and camera-convention
    # feasibility; it is NOT a visual classification or causal experiment gate.
    if (counts["with_event_file"] != 21 or counts["triggered"] != 6
            or n_probed != 5):
        gate = "HOLD_COHORT_ACCOUNTING_MISMATCH"
    elif all(counts[c + "_verified_pair"] == n_probed for c in CAMS):
        gate = "PAIRED_ASSETS_COMPLETE"
    else:
        gate = "HOLD_MISSING_OR_UNVERIFIED_ASSETS"
    return {
        "protocol": "P1_DEV0_VISUAL_PAIR_PREFLIGHT_V1",
        "gate": gate,
        "counts": dict(sorted(counts.items())),
        "failure_reasons": dict(sorted(causes.items())),
        "frame_contract": {
            "agentview": "pre policy_image_agentview_low and post probe_agentview: same policy-image storage convention; registration still not proven",
            "wrist": "pre image_wrist_low = raw_wrist[::-1]; post probe_wrist = raw_wrist; vertical flip REQUIRED before raw pixel comparison",
        },
        "cannot_conclude": [
            "an object is grasped, lifted or still held",
            "identical or changed image hash implies task outcome",
            "pre/post pixel differences after a physical gripper probe are information-only effects",
            "visual verifier accuracy, causal benefit, or any new L2 experiment authorization",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path,
                        default=Path("/workspace/yjx/rpent_data/p1_dev0"))
    parser.add_argument("--manifest", type=Path,
                        default=REPO / "artifacts" / "p1_dev0" / "manifest.jsonl")
    parser.add_argument("--seal", type=Path,
                        default=REPO / "artifacts" / "p1_dev0" / "manifest.sha256.json")
    parser.add_argument("--output", type=Path,
                        default=REPO / "artifacts" / "p1_dev0" / "visual_pair_preflight.json")
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((REPO / "artifacts").resolve()):
        parser.error("Output must remain in gitignored artifacts/")
    # Reuse existing write-once manifest SHA verifier (does not load outcomes).
    from p1_dev0_posthoc_audit import verified_manifest
    manifest = verified_manifest(args.manifest, args.seal)
    report = evaluate(args.out_root, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
