#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §7 — O-B 快照 manifest 物化与 hash 冻结。

读 stageO_collect_ledger.csv 的 included 行,对每行重放 1..t0 → save_state,
记录 state sha256(前 16 hex)/eef0/pos0/check_success@t0,写
analysis/stageO_split_manifest.csv(头部注释含整文件 sha256,写完即冻结)。

之后所有 runner(reference/ladder/calibrate)boot 后必须断言重放 hash 与
manifest 一致(已内置在 reference;ladder 同样调用)。

用法:
  MUJOCO_GL=osmesa python scripts/stageO_freeze_manifest.py --gpu 0
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt

LEDGER = REPO / "analysis/stageO_collect_ledger.csv"
OUT = REPO / "analysis/stageO_split_manifest.csv"
LOG_ROOT = REPO / "logs/stageO_freeze"

FIELDS = ["snapshot_id", "family", "procedure", "task", "seed", "t0",
          "episode_dir", "event_rule", "collect_ts", "state_len",
          "state_sha16", "eef0", "check_success_at_t0", "target_of_interest"]


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()
    rt.apply_env_overrides()

    lines = [l for l in open(LEDGER, encoding="utf-8") if not l.startswith("#")]
    rows = [r for r in csv.DictReader(io.StringIO("".join(lines)))
            if r.get("included") == "True"]
    assert rows, "ledger 无 included 行(采集未完成或全失败)"
    log(f"ledger included {len(rows)} 快照,开始物化")
    # 排序确定性:family(FALSE_GRASP 先,prereg "FG 优先")→ task → seed
    fam_order = {"FALSE_GRASP": 0, "RELEASE_PREDICATE_STALL": 1}
    rows.sort(key=lambda r: (fam_order.get(r["assigned_family"], 9),
                             int(r["task"]), int(r["seed"])))

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = LOG_ROOT / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)
    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    log("boot shared vla+sam3 ...")
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())

    out_rows = []
    try:
        for i, r in enumerate(rows):
            snap = {
                "snapshot_id": f"osnap_{i:02d}",
                "family": r["assigned_family"],
                "procedure": rt.FAM2PROC[r["assigned_family"]],
                "task": r["task"], "seed": r["seed"],
                "t0": r["assigned_t0"], "episode_dir": r["episode_dir"],
            }
            tag = f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}"
            tries = 0
            while True:
                try:
                    outdir = LOG_ROOT / (
                        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
                    ctx = rt.boot_snapshot(snap, args.gpu, shared_kwargs,
                                           outdir)
                    break
                except rt.InfraError as exc:
                    tries += 1
                    log(f"  {tag} INFRA({tries}/3): {exc}")
                    if tries >= 3:
                        ctx = None
                        break
            if ctx is None:
                log(f"  {tag} 物化失败(INFRA_ABORT),跳过并记录")
                out_rows.append({**{k: snap[k] for k in FIELDS
                                    if k in snap},
                                 "event_rule": r.get("note", ""),
                                 "collect_ts": r.get("episode_dir", ""),
                                 "state_len": "", "state_sha16":
                                 f"INFRA_ABORT_3attempts"})
                continue
            base = ctx["base"]
            out_rows.append({
                "snapshot_id": snap["snapshot_id"],
                "family": snap["family"], "procedure": snap["procedure"],
                "task": snap["task"], "seed": snap["seed"], "t0": snap["t0"],
                "episode_dir": snap["episode_dir"],
                "event_rule": r.get("note", ""),
                "collect_ts": r.get("episode_dir", "").split("/")[-1],
                "state_len": int(len(ctx["S"])),
                "state_sha16": ctx["state_hash"],
                "eef0": json.dumps([round(c, 4) for c in base["eef"]]),
                "check_success_at_t0": base["check_success"],
                "target_of_interest": ctx["target"] or "",
            })
            log(f"  {tag} {snap['family']} t0={snap['t0']} "
                f"sha={ctx['state_hash']} succ@t0={base['check_success']}")
            for d in ctx.get("daemons") or []:
                try:
                    d.stop()
                except Exception:
                    pass
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass

    # 写 manifest + 整文件 sha256 头(冻结)
    import io as _io
    buf = _io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(out_rows)
    body = buf.getvalue()
    sha = hashlib.sha256(body.encode()).hexdigest()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(f"# stageO_split_manifest | frozen {datetime.now().isoformat()}"
                f" | n={len(out_rows)}\n")
        f.write(f"# sha256(body)={sha}\n")
        f.write(body)
    log(f"manifest 冻结:{OUT}(n={len(out_rows)}, sha256={sha[:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
