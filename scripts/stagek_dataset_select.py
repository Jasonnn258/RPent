#!/usr/bin/env python
"""Stage K §3 — 数据集快照机械选择 + TRAIN/VAL/TEST 切分(先于任何采集/训练)。

规则(全部机械,零人工挑选;生成后随 manifest 冻结):
- 池:stageH_transition_dataset.jsonl 的 h1 行(h1C/h1G/h1P2);
- 每集(episode_dir)取 step_idx 最小 fire 为该集候选快照(K0 同规);
- 排除校准 episodes 整集(prereg 只承诺排除 6 快照;整集排除是保守
  超集 —— 池普查:校准集内无额外 MCS fire,该排除不改变 MCS=0 事实);
- 切分按 (task,seed) 对(同对同 split,杜绝同初态跨 split),**族内分层
  定比**(结果盲):对按 primary family(FG 优先,无 FG 才 RPS)分两层,
  层内按 md5("stageK-split-v2:{family}:{task},{seed}") 排序,前 15% VAL、
  次 25% TEST、余 TRAIN —— 修正全局 hash 导致的 RPS VAL=0(λ 需在
  VALIDATION 冻结);
- FG 预算闸:--fg-cap N,按 (task,seed,arm,dir) 排序取前 N 集;
- MCS 普查结论(h1 池排除校准后 0 快照;h0 行无 episode_dir 不可重放)
  写入 selection 的 census 字段 —— 三族 spec 在本语料上结构不可达,
  K1 gate 族条款按可用族(FG/RPS)解读,偏离记录在案。

用法:python scripts/stagek_dataset_select.py --k-rollout 8 --fg-cap 24
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "analysis/stageH_transition_dataset.jsonl"
CALIB = REPO / "analysis/stageK0_snapshot_selection.json"
OUT = REPO / "analysis/stageK_dataset_selection.json"
SPLIT_DOMAIN = "stageK-split-v2"


def pair_split(pairs: list[tuple[int, int, str]]) -> dict[tuple[int, int], str]:
    """族内分层:层内按 md5 排序,前 15% VAL、次 25% TEST、余 TRAIN。

    pairs = [(task, seed, family)];返回 {(task,seed): split}。
    """
    order = sorted(pairs, key=lambda p: hashlib.md5(
        f"{SPLIT_DOMAIN}:{p[2]}:{p[0]},{p[1]}".encode()).hexdigest())
    n = len(order)
    n_val = max(1, round(n * 0.15)) if n >= 2 else 0
    n_test = max(1, round(n * 0.25)) if n >= 2 else 1
    out: dict[tuple[int, int], str] = {}
    for i, (t, s, _) in enumerate(order):
        out[(t, s)] = "VAL" if i < n_val else \
            "TEST" if i < n_val + n_test else "TRAIN"
    return out


def episode_sort_key(ep_dir: str) -> tuple:
    m = re.search(r"_task_t(\d+)_s(\d+)_r(\d+)$", ep_dir)
    arm = re.search(r"_(h1[C|G|P2]+)_libero", ep_dir)
    t, s, r = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (99, 99, 99)
    a = arm.group(1) if arm else "zz"
    return (t, s, a, r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k-rollout", type=int, required=True,
                    help="K_ROLLOUT 冻结值(必须与 stageK0_decision.md 一致)")
    ap.add_argument("--fg-cap", type=int, default=None,
                    help="FG 每集预算闸(episode 数;None=全取)")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(POOL)]
    h1 = [r for r in rows if str(r.get("arm", "")).startswith("h1")]
    cal_eps = {s["episode_dir"] for s in json.load(open(CALIB))["snapshots"]}

    # 每集最早 fire
    by_ep: dict[str, dict] = {}
    for r in h1:
        ep = r["episode_dir"]
        if ep not in by_ep or r["step_idx"] < by_ep[ep]["step_idx"]:
            by_ep[ep] = r

    cal_rejected = [r for r in by_ep.values() if r["episode_dir"] in cal_eps]
    cand = [r for r in by_ep.values() if r["episode_dir"] not in cal_eps]

    # FG 预算闸(机械排序取前 N)
    fg = sorted((r for r in cand if r["family"] == "FALSE_GRASP"),
                key=lambda r: episode_sort_key(r["episode_dir"]))
    if args.fg_cap is not None:
        fg = fg[: args.fg_cap]
    rest = [r for r in cand if r["family"] != "FALSE_GRASP"]
    kept = fg + rest

    # 切分:按 (task,seed) 对 + primary family 分层(FG 优先,无 FG 才 RPS)
    pair_fam: dict[tuple[int, int], set] = collections.defaultdict(set)
    for r in kept:
        pair_fam[(r["task"], r["seed"])].add(r["family"])
    pairs_by_fam: dict[str, list] = collections.defaultdict(list)
    for (t, s), fams in pair_fam.items():
        primary = "FALSE_GRASP" if "FALSE_GRASP" in fams \
            else next(iter(fams))
        pairs_by_fam[primary].append((t, s, primary))
    split_map: dict[tuple[int, int], str] = {}
    for fam, ps in pairs_by_fam.items():
        split_map.update(pair_split(ps))

    # snapshot_id:K0 风格 t{task}s{seed}{arm}T{step};同 (task,seed,arm)
    # 多集时加 r 尾缀消歧
    seen: collections.Counter = collections.Counter()
    snapshots, missing = [], []
    for r in sorted(kept, key=lambda r: episode_sort_key(r["episode_dir"])):
        ep = r["episode_dir"]
        m = re.search(r"_(h1[C|G|P2]+)_libero", ep)
        arm = m.group(1) if m else "h1"
        sid = f"t{r['task']}s{r['seed']}{arm}T{r['step_idx']}"
        seen[(r["task"], r["seed"], arm)] += 1
        if seen[(r["task"], r["seed"], arm)] > 1:
            rr = re.search(r"_r(\d+)$", ep)
            sid += f"r{rr.group(1) if rr else seen[(r['task'], r['seed'], arm)]}"
        if not (Path(ep) / "states.json").exists():
            missing.append({"snapshot_id": sid, "episode_dir": ep})
            continue
        snapshots.append({
            "snapshot_id": sid, "episode_dir": ep, "task": r["task"],
            "seed": r["seed"], "arm": arm, "T": r["step_idx"],
            "family": r["family"], "node": r.get("node"),
            "legal_edges": r["legal_edges"],
            "split": split_map[(r["task"], r["seed"])],
        })

    # 普查 + 预算
    census = {
        "h1_rows": len(h1), "episodes": len(by_ep),
        "calibration_episodes_excluded": len(cal_rejected),
        "candidates_after_exclusion": len(cand),
        "kept": len(snapshots), "missing_states_json": missing,
        "family_kept": dict(collections.Counter(s["family"] for s in snapshots)),
        "family_split": {f: dict(collections.Counter(
            s["split"] for s in snapshots if s["family"] == f))
            for f in {s["family"] for s in snapshots}},
        "mcs_note": ("h1 池排除校准集后 MCS 候选=0(仅有的 2 个 MCS fire 即"
                     "校准快照);h0 行无 episode_dir 不可重放 —— MCS 边执行"
                     "数据本语料结构不可达,K1 族条款按 FG/RPS 解读"),
    }
    n_combos = sum(len(s["legal_edges"]) for s in snapshots)
    budget = {
        "k_rollout": args.k_rollout, "combos": n_combos,
        "total_rollouts": n_combos * args.k_rollout,
        "est_wall_h": round(n_combos * args.k_rollout * 10.5 / 3600, 2),
        "per_rollout_s_basis": "K0 实测 10.5s(2026-09-30)",
    }

    doc = {
        "version": "stageK-dataset-selection-v1",
        "frozen_date": datetime.now().strftime("%Y-%m-%d"),
        "rule": {
            "pool": "h1C/h1G/h1P2 rows, earliest fire per episode",
            "exclusion": "calibration episodes 整集(保守超集)",
            "split": f"(task,seed) 对 + primary-family 分层,层内 md5('{SPLIT_DOMAIN}:{{family}}:{{task}},{{seed}}') 排序,前 15% VAL / 次 25% TEST / 余 TRAIN",
            "fg_cap": args.fg_cap,
        },
        "census": census, "budget": budget, "snapshots": snapshots,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(json.dumps({"census": census, "budget": budget},
                     ensure_ascii=False, indent=1))
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
