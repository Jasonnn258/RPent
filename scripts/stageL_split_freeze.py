#!/usr/bin/env python
"""Stage L §3 — split 冻结:DISCOVERY/DEV/CAL_RESERVED/HELDOUT_TEST 机械选定。

纪律(spec §3):
- HELDOUT 选择完全机械:每族(按集内全局最早 fire 的族分层,episode 级
  唯一 anchor),md5(episode_dir) 升序取前 12;不做任何人工/结果性挑选,
  不设替补(restore 失败 = infra,如实减 n,禁止事后换人);
- family inclusion(FG+RPS)在看 HELDOUT 前冻结(MCS anchor 集不入选);
- DISCOVERY = K 数据集 34 集(挖掘源;其快照即 L 的 DEV 侧);
- CAL_RESERVED = K0 标定 6 集:不挖掘、不进 DEV/HELDOUT(K_ROLLOUT=4
  沿用 K0 冻结值,不重推导,见 prereg §6);
- 产物 manifest 连同 split_hash 记入 prereg,先于任何挖掘/执行 commit。

用法:python scripts/stageL_split_freeze.py
产物:analysis/stageL_split_manifest.csv + stdout 摘要
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

INV = REPO / "analysis/stageL_pool_inventory.jsonl"
KSEL = REPO / "analysis/stageK_dataset_selection.json"
CAL = REPO / "analysis/stageK0_snapshot_selection.json"
OUT = REPO / "analysis/stageL_split_manifest.csv"

N_HELDOUT_PER_FAMILY = 12          # 每族 HELDOUT 快照数(冻结)
FAMILIES = ("FALSE_GRASP", "RELEASE_PREDICATE_STALL")  # MCS 不纳入(§0 审计)


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def main() -> int:
    # ---- K 侧:DISCOVERY(=DEV 快照所在集)+ CAL_RESERVED --------------------
    ksel = json.load(open(KSEL))
    cal = json.load(open(CAL))
    rows = []
    for s in ksel["snapshots"]:
        rows.append({
            "episode_dir": s["episode_dir"], "task": s["task"],
            "seed": s["seed"], "role": "L_DISCOVERY_DEV",
            "anchor_fire_step": s["T"], "anchor_family": s["family"],
            "legal_edges": "|".join(s.get("legal_edges", [])),
            "k_split": s.get("split", ""), "md5_rank": "",
        })
    for s in cal["snapshots"]:
        rows.append({
            "episode_dir": s["episode_dir"], "task": s["task"],
            "seed": s["seed"], "role": "L_CAL_RESERVED",
            "anchor_fire_step": s["T"], "anchor_family": s["family"],
            "legal_edges": "|".join(s.get("legal_edges", [])),
            "k_split": "cal", "md5_rank": "",
        })
    dev_pairs = {(r["task"], r["seed"]) for r in rows}

    # ---- HELDOUT 候选:episode 级 anchor(全局最早 fire)--------------------
    # 合法边 = anchor fire 自身的检测边(与 K 的快照口径一致,不跨 fire 并集)
    inv = [json.loads(x) for x in open(INV)]
    cand = {}
    for r in inv:
        if r.get("role") != "HELDOUT_CAND" or r.get("family") is None:
            continue
        ep = r["episode_dir"]
        cur = cand.get(ep)
        if cur is None or r["fire_step"] < cur["fire_step"]:
            cand[ep] = r

    held_rows = []
    for fam in FAMILIES:
        pool = sorted((r for r in cand.values()
                       if r["family"] == fam and
                       (r["task"], r["seed"]) not in dev_pairs),
                      key=lambda r: md5(r["episode_dir"]))
        for i, r in enumerate(pool):
            if i >= N_HELDOUT_PER_FAMILY:
                break
            held_rows.append({
                "episode_dir": r["episode_dir"], "task": r["task"],
                "seed": r["seed"], "role": "L_HELDOUT_TEST",
                "anchor_fire_step": r["fire_step"],
                "anchor_family": fam,
                "legal_edges": "|".join(r["legal_edges"]),
                "k_split": "", "md5_rank": i + 1,
            })
    rows += held_rows

    # ---- 写 manifest + split_hash -------------------------------------------
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["role"], x["episode_dir"])):
            w.writerow(r)
    split_hash = hashlib.md5(Path(OUT).read_bytes()).hexdigest()[:12]

    summary = {
        "split_hash_md5_12": split_hash,
        "discovery_dev": sum(r["role"] == "L_DISCOVERY_DEV" for r in rows),
        "discovery_dev_by_family": {
            f: sum(r["role"] == "L_DISCOVERY_DEV" and
                   r["anchor_family"] == f for r in rows) for f in FAMILIES},
        "cal_reserved": sum(r["role"] == "L_CAL_RESERVED" for r in rows),
        "heldout_test": len(held_rows),
        "heldout_by_family": {
            f: sum(r["anchor_family"] == f for r in held_rows) for f in FAMILIES},
        "heldout_by_task": {
            f"t{r['task']}": sum(x["task"] == r["task"] for x in held_rows)
            for r in held_rows},
        "heldout_pairs": len({(r["task"], r["seed"]) for r in held_rows}),
        "heldout_pool_size_per_family": {
            f: sum(1 for r in cand.values()
                   if r["family"] == f and
                   (r["task"], r["seed"]) not in dev_pairs) for f in FAMILIES},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
