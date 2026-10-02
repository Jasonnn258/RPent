#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O dev-O5 取证:每快照 task×seed 的 init 态 check_success(不重放)。

目的:判定 manifest 中 check_success_at_t0=True 的快照是否 init 即成功
(libero 已知怪癖:部分 task×seed 的初始状态已满足目标谓词)——若是,
则该快照在任何重放下都平凡满足 §5.1 契约,无法测量 recovery(确定性退化)。

方法:对 manifest 每行以 t0=0 调 boot_snapshot(重放窗口 1..0 = 空,
即纯 init 态),记录 check_success / terminated / eef。只读,不改任何产物。

用法:MUJOCO_GL=osmesa python scripts/stageO_init_check.py --gpu 0
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt

OUT = Path("/workspace/yjx/tmp/stageO_init_check.json")
LOG_ROOT = REPO / "logs/stageO_init_check"


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()
    rt.apply_env_overrides()

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

    mani = rt_csv_rows()
    results = []
    try:
        for row in mani:
            # t0=0:重放窗口为空 → 纯 init 态
            snap = {**row, "t0": 0}
            tag = f"{row['snapshot_id']}_t{row['task']}s{row['seed']}"
            try:
                outdir = LOG_ROOT / (
                    f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
                ctx = rt.boot_snapshot(snap, args.gpu, shared_kwargs, outdir,
                                       note="init_check")
                base = ctx["base"]
                rec = {"snapshot_id": row["snapshot_id"],
                       "task": row["task"], "seed": row["seed"],
                       "family": row["family"],
                       "init_check_success": base["check_success"],
                       "init_terminated": base["terminated"],
                       "init_eef": base["eef"],
                       "manifest_succ_at_t0": row.get("check_success_at_t0")}
                log(f"  {tag} init_succ={base['check_success']} "
                    f"term={base['terminated']}")
                for d in ctx.get("daemons") or []:
                    try:
                        d.stop()
                    except Exception:
                        pass
            except Exception as exc:
                rec = {"snapshot_id": row["snapshot_id"], "task": row["task"],
                       "seed": row["seed"], "family": row["family"],
                       "error": f"{type(exc).__name__}: {exc}"}
                log(f"  {tag} ERR {rec['error'][:120]}")
            results.append(rec)
            OUT.write_text(json.dumps(results, indent=1, default=str))
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    log(f"done → {OUT}")
    return 0


def rt_csv_rows():
    import csv, io
    mani = REPO / "analysis/stageO_split_manifest.csv"
    lines = [l for l in open(mani, encoding="utf-8") if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


if __name__ == "__main__":
    raise SystemExit(main())
