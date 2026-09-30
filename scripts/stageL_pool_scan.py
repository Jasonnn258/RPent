#!/usr/bin/env python
"""Stage L §0 — 快照池全量扫描(离线、只读,产出 split 设计用清单)。

来源与纪律:
- K 已消耗集(K 数据集 34 + K0 标定 6):记录完整信息,含 fire 级
  恢复可采性(首个 validating action)—— 这些集已烧毁,可自由看;
- HELDOUT 候选集(20260928 池外 H1 集 + 老 campaign 池外对集):
  **只记检测信息**(task/seed/fire 步/族/合法边),不计算任何
  恢复/验证状态 —— fire 级 outcome 属于 held-out 内容,evolution
  完成前不可见(spec §3)。

fire 检测 = analyze_stageH1.replay_fires(与 Stage H/K 同一代码路径,
纯离线);老集无 memory 事件可交叉核对,prereg 记录此差异。

用法:python scripts/stageL_pool_scan.py [--tasks 3,5,9]
产物:analysis/stageL_pool_inventory.jsonl
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

OUT = REPO / "analysis/stageL_pool_inventory.jsonl"
EP_PAT = re.compile(r"_task_t(\d+)_s(\d+)_r(\d+)$")


def episode_key(d: str):
    m = EP_PAT.search(d)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tasks", default="3,5,9")
    args = ap.parse_args()
    tasks = {int(x) for x in args.tasks.split(",")}

    from analyze_stageH1 import (NODE_FAMILY, fire_validated,
                                 next_act_steps, replay_fires)

    # ---- K 已消耗集(完整信息)------------------------------------------------
    ksel = json.load(open(REPO / "analysis/stageK_dataset_selection.json"))
    k_eps = {s["episode_dir"]: s for s in ksel["snapshots"]}
    cal = json.load(open(REPO / "analysis/stageK0_snapshot_selection.json"))
    cal_eps = {s["episode_dir"]: s for s in cal["snapshots"]}

    rows = []
    for ep, meta in list(k_eps.items()) + \
            [(e, {**m, "role": "CALIBRATION"}) for e, m in cal_eps.items()]:
        steps = json.loads((Path(ep) / "states.json").read_text())
        fires = replay_fires(steps)
        for f in fires:
            i = f["step_idx"]
            win = next_act_steps(steps, i, 10**9)  # 不限窗,找首个恢复动作
            first_val, n_acts = None, len(win)
            for j, (a, r, term) in enumerate(win):
                if fire_validated(f["node"], [(a, r, term)]):
                    first_val = {"offset": j, "action": a,
                                 "terminated": term}
                    break
            rows.append({
                "episode_dir": ep, "task": meta["task"],
                "seed": meta["seed"], "arm": meta.get("arm"),
                "role": ("K_" + meta["split"]) if "split" in meta
                else meta.get("role", "?"),
                "fire_step": i, "family": NODE_FAMILY[f["node"]],
                "node": f["node"], "legal_edges": f["edges"],
                "n_post_acts": n_acts, "first_validating": first_val,
                "episode_sr": bool(steps[-1].get("libero_terminated")),
            })

    # ---- HELDOUT 候选(只检测,不看结果)------------------------------------
    pool_pairs = set()
    for ln in open(REPO / "analysis/stageH_transition_dataset.jsonl"):
        r = json.loads(ln)
        if str(r.get("arm", "")).startswith("h1"):
            pool_pairs.add((r["task"], r["seed"]))
    k_pairs = {(m["task"], m["seed"]) for m in k_eps.values()} | \
              {(m["task"], m["seed"]) for m in cal_eps.values()}

    heldout_eps = []
    for d in sorted((REPO / "logs/ovpm_exp").glob(
            "*_libero_spatial_task_*")):
        k = episode_key(d.name)
        if k is None or k[0] not in tasks:
            continue
        pair = (k[0], k[1])
        if pair in pool_pairs or pair in k_pairs:
            continue  # 池内对 / K 已用对 → 不是 HELDOUT 候选
        if not (d / "states.json").exists():
            continue
        heldout_eps.append(d)

    for d in heldout_eps:
        t, s, r = episode_key(d.name)
        try:
            steps = json.loads((Path(d) / "states.json").read_text())
            fires = replay_fires(steps)
        except Exception as exc:  # noqa: BLE001
            rows.append({"episode_dir": str(d), "task": t, "seed": s,
                         "role": "HELDOUT_CAND", "scan_error":
                         f"{type(exc).__name__}: {exc}"[:200]})
            continue
        for f in fires:
            rows.append({
                "episode_dir": str(d), "task": t, "seed": s,
                "role": "HELDOUT_CAND", "fire_step": f["step_idx"],
                "family": NODE_FAMILY[f["node"]], "node": f["node"],
                "legal_edges": f["edges"],
                # 故意不记录:n_post_acts / first_validating / episode_sr
            })
        if not fires:
            rows.append({"episode_dir": str(d), "task": t, "seed": s,
                         "role": "HELDOUT_CAND", "fire_step": None,
                         "family": None})

    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    # ---- 摘要 ----------------------------------------------------------------
    cnt = collections.Counter(
        (r.get("role"), r.get("family")) for r in rows if r.get("family"))
    held_pairs = {(r["task"], r["seed"]) for r in rows
                  if r.get("role") == "HELDOUT_CAND"}
    held_fire_rows = [r for r in rows if r.get("role") == "HELDOUT_CAND"
                      and r.get("family")]
    held_ep_fire = {r["episode_dir"] for r in held_fire_rows}
    print(json.dumps({
        "rows": len(rows),
        "k_consuming_fires": dict(collections.Counter(
            (r.get("role"), r.get("family")) for r in rows
            if r.get("role", "").startswith("K_"))),
        "heldout_cand_episodes": len(heldout_eps),
        "heldout_cand_pairs": len(held_pairs),
        "heldout_cand_fires": dict(collections.Counter(
            r.get("family") for r in held_fire_rows)),
        "heldout_cand_episodes_with_fire": len(held_ep_fire),
        "heldout_fire_by_task": {f"t{t}s{fam}": n for (t, fam), n in
                                 collections.Counter(
            (r["task"], r.get("family")) for r in held_fire_rows).items()},
    }, ensure_ascii=False, indent=1))
    print(f"-> {OUT} ({datetime.now().isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
