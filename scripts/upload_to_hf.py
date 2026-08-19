#!/usr/bin/env python3
"""Upload RPent raw experiment observations (logs/) to a HuggingFace dataset repo.

Two steps, run from any machine with python3 + huggingface_hub:

    # 1. Scan: build index.jsonl + README.md inside the logs dir
    python3 upload_to_hf.py scan --logs /path/to/logs

    # 2. Upload: create repo if needed, then upload_folder (LFS + resume)
    #    token via --token or HF_TOKEN env or `huggingface-cli login`
    python3 upload_to_hf.py upload --logs /path/to/logs \
        --repo Jasonnn258/RPent-logs [--token hf_xxx]

Both at once:
    python3 upload_to_hf.py all --logs /path/to/logs --repo Jasonnn258/RPent-logs

Design notes:
- index.jsonl is plain JSONL (no pandas/pyarrow needed) so the dataset is
  usable immediately via `datasets.load_dataset(..., data_files="index.jsonl")`.
- upload_folder skips already-uploaded files (LFS ETag cache), so re-running
  resumes instead of restarting.
- episode.mp4 files are included; they are part of the episode records.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# ---- dir-name parsing ---------------------------------------------------------
#  top-level: 20260814-12:25:00_libero_spatial_swap_t8_s5
#  pg_exp:    20260814-19:05:48_baseline_libero_spatial_task_t0_s1_r2
#  sm_exp:    20260818-15:51:59_structured_libero_spatial_task_t0_s1_r1
EP_DIR_RE = re.compile(
    r"^(?P<ts>\d{8}-\d{2}:\d{2}:\d{2})_"
    r"(?:(?P<cond>baseline|ours|hardcap|structured)_)?"
    r"(?P<suite>libero_\w+)_(?P<task>t\d+)_(?P<seed>s\d+)"
    r"(?:_(?P<repeat>r\d+))?$"
)

MODALITY_DIRS = (
    "images", "images_cam", "images_wrist", "images_cam_hi", "images_wrist_hi",
    "depths", "depths_wrist", "world", "world_hi", "world_wrist", "world_wrist_hi",
    "segments", "action_videos", "wrist_meta",
)

META_FILES = ("camera_meta.json", "run.log", "env_server.log", "vla_server.log",
              "sam3_server.log", "episode.mp4")


def _dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def scan_episode(ep_dir, rel):
    """Return metadata dict for one episode dir, or None if not an episode."""
    name = os.path.basename(ep_dir)
    m = EP_DIR_RE.match(name)
    meta = {
        "episode_id": rel,
        "episode_dir": rel,
        "suite": None, "task": None, "seed": None, "timestamp": None, "cond": None,
        "repeat": None,
    }
    if m:
        meta.update({"timestamp": m.group("ts"), "suite": m.group("suite"),
                     "task": m.group("task"), "seed": m.group("seed"),
                     "cond": m.group("cond"), "repeat": m.group("repeat")})
    states_path = os.path.join(ep_dir, "states.json")
    if not os.path.exists(states_path):
        meta.update({"valid": False, "reason": "no states.json",
                     "n_steps": 0, "success": None})
    else:
        try:
            with open(states_path, "r", encoding="utf-8") as fh:
                states = json.load(fh)
            n_steps = len(states) if isinstance(states, list) else 0
            last = states[-1] if states else {}
            meta.update({
                "valid": True, "reason": None, "n_steps": n_steps,
                "libero_terminated": last.get("libero_terminated"),
                "episode_truncated": last.get("episode_truncated"),
                "task_language": (states[0].get("task_language") if states else None),
            })
        except Exception as e:  # noqa: BLE001
            meta.update({"valid": False, "reason": f"states.json parse: {e}",
                         "n_steps": 0, "success": None})
    # modality file counts + sizes
    for mod in MODALITY_DIRS:
        p = os.path.join(ep_dir, mod)
        if os.path.isdir(p):
            n = sum(len(fs) for _, _, fs in os.walk(p))
            meta[f"{mod}_files"] = n
            meta[f"{mod}_bytes"] = _dir_size(p)
    # extra top-level files
    extra = []
    for f in sorted(os.listdir(ep_dir)):
        fp = os.path.join(ep_dir, f)
        if os.path.isfile(fp) and not f.startswith(".") and f not in META_FILES:
            extra.append({"file": f, "bytes": os.path.getsize(fp)})
    meta["extra_files"] = extra
    return meta


def scan(logs_dir):
    episodes = []
    skipped = []
    # walk recursively: any dir containing states.json is an episode
    for root, dirs, _files in os.walk(logs_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if "states.json" in _files:
            rel = os.path.relpath(root, logs_dir)
            meta = scan_episode(root, rel)
            (episodes if meta.get("valid") else skipped).append(meta)
            dirs[:] = []  # don't descend into an episode
    episodes.sort(key=lambda m: m["episode_dir"])
    skipped.sort(key=lambda m: m["episode_dir"])
    return episodes, skipped


def write_index(logs_dir, episodes, skipped):
    index_path = os.path.join(logs_dir, "index.jsonl")
    with open(index_path, "w", encoding="utf-8") as fh:
        for meta in episodes:
            fh.write(json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n")
    n_valid = len(episodes)
    tot = sum(m.get("n_steps", 0) for m in episodes)
    suites = {}
    for m in episodes:
        s = m.get("suite") or "unknown"
        suites[s] = suites.get(s, 0) + 1
    with open(os.path.join(logs_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("""---
license: cc-by-4.0
task_categories:
- robotics
tags:
- rpent
- vla
- pi0.5
- libero
---

# RPent — Raw VLA Benchmark Observations

Pi0.5 + SAM3 + Kimi K3 planner benchmark (Libero suites). See
`analysis/` in the companion GitHub repo (Jasonnn258/RPent) for the
progress-gate vs baseline vs hardcap ablation.

## Stats

- Episodes: {n_valid}
- Total steps: {tot}
- By suite: {suites}
- Skipped (invalid/empty): {n_skip}

## Layout

Each episode directory is a full run: `states.json` (per-step robot state +
`libero_terminated`), `images*/`/`world*/`/`depths*/` observations,
`transcript_*.json` (planner turns), `recipe_*.jsonl`, `episode.mp4`,
server logs. `index.jsonl` has one metadata line per episode.
""".format(n_valid=n_valid, tot=tot, suites=json.dumps(suites, ensure_ascii=False),
           n_skip=len(skipped)))
    return index_path


def upload(logs_dir, repo, token):
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("huggingface_hub not installed: pip install -U huggingface_hub")
    api = HfApi(token=token)
    api.create_repo(repo_id=repo, repo_type="dataset", exist_ok=True)
    print(f"[upload] {logs_dir} -> {repo}")
    # upload_large_folder: robust for big dirs (batched git commits, resumable).
    api.upload_large_folder(
        repo_id=repo, folder_path=logs_dir, repo_type="dataset",
        allow_patterns=None,
        ignore_patterns=[".DS_Store", "__pycache__/*"],
    )
    print("[upload] done (resume-safe; re-run to continue any incomplete files)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["scan", "upload", "all"])
    ap.add_argument("--logs", required=True, help="path to logs/ dir")
    ap.add_argument("--repo", default="Jasonnn258/RPent-logs")
    ap.add_argument("--token", default=None, help="HF token (or HF_TOKEN env)")
    ap.add_argument("--json-out", default=None,
                    help="write index.jsonl here instead of inside logs/ (scan only)")
    args = ap.parse_args()
    token = args.token or os.environ.get("HF_TOKEN")

    if args.mode in ("scan", "all"):
        episodes, skipped = scan(args.logs)
        index_path = write_index(args.logs, episodes, skipped)
        if args.json_out and args.json_out != index_path:
            import shutil
            shutil.copy2(index_path, args.json_out)
            print(f"[scan] index also copied to {args.json_out}")
        print(f"[scan] {len(episodes)} valid episodes, {len(skipped)} skipped "
              f"-> {index_path}")
    if args.mode in ("upload", "all"):
        if not token:
            sys.exit("need HF token (--token or HF_TOKEN env)")
        upload(args.logs, args.repo, token)


if __name__ == "__main__":
    main()
