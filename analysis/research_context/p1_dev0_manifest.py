#!/usr/bin/env python3
"""P1-DEV0: preregistered 24-episode task-stratified experimental manifest.

No environment calls, no outcomes, no privileged measurements. Runs before
the first P1 rollout; refuse overwrite. A manifest is only an assignment,
not proof that any intervention tool is ready to run.

  python3 analysis/research_context/p1_dev0_manifest.py --repo-root "$PWD"
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROTOCOL = "P1-DEV0-L2-24EP-4ARM-20261009"
TASKS = (3, 5, 9)
SEEDS = tuple(range(1001, 1009))
ARMS = ("D0", "D1", "D2", "D3")
RANDOM_SEED = 20261009
MAX_EPISODES = 24
MAX_WORKERS = 2
MAX_WALL_SECONDS = 8 * 3600
MAX_GPU_SECONDS = 6 * 3600


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(body: bytes):
    return hashlib.sha256(body).hexdigest()


def manifest():
    rng = random.Random(RANDOM_SEED)
    rows = []
    for task in TASKS:
        assignment = list(ARMS) * 2
        rng.shuffle(assignment)
        for seed, arm in zip(SEEDS, assignment):
            rows.append({
                "episode_key": f"p1dev0_t{task}_s{seed}",
                "task": task,
                "seed": seed,
                "suite": "libero_spatial",
                "arm": arm,
                "trigger": "FIRST_NONTERMINAL_NONTRUNCATED_FALSE_PICK_D2_ONLY",
                "split": "DEV0_ONLY",
                "max_probe_events": 1,
                "source": "NEW_PROSPECTIVE",
            })
    check_manifest(rows)
    return rows


def check_manifest(rows):
    if len(rows) != MAX_EPISODES:
        raise ValueError("24 episode manifest required")
    if len({r["episode_key"] for r in rows}) != MAX_EPISODES:
        raise ValueError("duplicate episode key")
    if len({(r["task"], r["seed"]) for r in rows}) != MAX_EPISODES:
        raise ValueError("duplicate task seed")
    if sorted(set(r["task"] for r in rows)) != list(TASKS):
        raise ValueError("wrong task set")
    if any(r["seed"] not in SEEDS for r in rows):
        raise ValueError("seed outside preregistered new grid")
    if any(r["arm"] not in ARMS or r["trigger"] !=
           "FIRST_NONTERMINAL_NONTRUNCATED_FALSE_PICK_D2_ONLY"
           for r in rows):
        raise ValueError("invalid arm/trigger")
    per_task_arm = Counter((r["task"], r["arm"]) for r in rows)
    if any(per_task_arm[(task, arm)] != 2
           for task in TASKS for arm in ARMS):
        raise ValueError("task-arm allocation is not 2 x each")
    if any(r["max_probe_events"] != 1 or r["split"] != "DEV0_ONLY"
           for r in rows):
        raise ValueError("prospective attribution requires one event per episode")


def historical_collision_check(root, rows):
    historical = root / "analysis" / "stageR_collect_ledger.csv"
    if not historical.is_file():
        raise FileNotFoundError("Cannot check Stage R seed collision without original ledger")
    with historical.open(newline="", encoding="utf-8") as f:
        sources = {(int(r["task"]), int(r["seed"])) for r in csv.DictReader(f)
                   if r.get("task") and r.get("seed")}
    overlap = sources & {(r["task"], r["seed"]) for r in rows}
    if overlap:
        raise ValueError("Overlap with historical Stage R collected cells: %r" % sorted(overlap))
    # This check is limited to the Stage R ledger; it does NOT prove these
    # seeds have never appeared in OTHER prior project experiments.
    return len(sources)


def write_sealed(out, rows, historical_cells):
    out.mkdir(parents=True, exist_ok=True)
    path, seal = out / "manifest.jsonl", out / "manifest.sha256.json"
    content = "".join(canonical(r) + "\n" for r in rows).encode("utf-8")
    hash_value = digest(content)
    metadata = {
        "protocol": PROTOCOL, "sha256": hash_value,
        "assignment_seed": RANDOM_SEED, "episodes": len(rows),
        "tasks": list(TASKS), "seeds": list(SEEDS),
        "arms": list(ARMS), "events_per_episode": 1,
        "max_wall_seconds": MAX_WALL_SECONDS,
        "max_gpu_seconds": MAX_GPU_SECONDS,
        "max_workers": MAX_WORKERS,
        "historical_stageR_cells_checked": historical_cells,
        "note": "Assignment frozen before any P1 outcome; not permission to bypass integration gates.",
    }
    seal_content = (json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode("utf-8")
    if path.exists() or seal.exists():
        if not (path.is_file() and seal.is_file()
                and path.read_bytes() == content
                and seal.read_bytes() == seal_content):
            raise RuntimeError("P1 DEV0 manifest seal already exists but differs; STOP, do not overwrite")
        return {"status": "EXISTING_SEAL_IDENTICAL", **metadata}
    # Write-once, no clobber; should not be called concurrently.
    with path.open("xb") as f:
        f.write(content)
    with seal.open("xb") as f:
        f.write(seal_content)
    return {"status": "NEW_SEAL_WRITTEN", **metadata}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    root = args.repo_root.resolve()
    out = (args.output or (root / "artifacts" / "p1_dev0")).resolve()
    if not out.is_relative_to(root / "artifacts"):
        ap.error("output must remain under gitignored RPent/artifacts")
    rows = manifest()
    previous_count = historical_collision_check(root, rows)
    receipt = write_sealed(out, rows, previous_count)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
