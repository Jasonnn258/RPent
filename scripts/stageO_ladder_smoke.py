#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O ladder 集成冒烟(§8 "校准同时充当 runner 集成冒烟"的补充)。

对单个快照跑缩减规模 ladder(O0 K=2 / O1 n=2 / O4 1 rollout;有 reference
则加 O2 n=2 / O3 K=2),**输出全部写 /workspace/yjx/tmp/stageO_ladder_smoke/**
——绝不写 analysis/ 的 confirmatory 产物。

用法:
  MUJOCO_GL=osmesa python scripts/stageO_ladder_smoke.py --gpu 0 \
      [--mani analysis/stageO_split_manifest.csv --snap osnap_00]
  # mani 未冻结时可传 N 池 manifest(--mani analysis/stageN1_split_manifest.csv
  # --snap snap_00),此时无 reference,O2/O3 走 REFERENCE_UNAVAILABLE 路径
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import stageO_ladder as L
import stageO_rt as rt

SMOKE_DIR = Path("/workspace/yjx/tmp/stageO_ladder_smoke")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--mani", default=str(REPO / "analysis/stageO_split_manifest.csv"))
    ap.add_argument("--snap", default="osnap_00")
    ap.add_argument("--skip-o4", action="store_true",
                    help="跳过 O4(不起 planner,纯本地臂冒烟)")
    args = ap.parse_args()

    rt.apply_env_overrides()
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 重定向产物到 tmp + 缩减规模(只改运行参数,不改臂定义)----------
    L.MANI = Path(args.mani)
    L.ROLL_CSV = SMOKE_DIR / "rollouts.csv"
    L.REENT_CSV = SMOKE_DIR / "reentry_results.csv"
    L.TRANS_JL = SMOKE_DIR / "arm_transitions.jsonl"
    L.LOG_ROOT = SMOKE_DIR / "logs"
    L.O12_SAMPLES = 2
    K = 2
    if L.ROLL_CSV.exists():
        L.ROLL_CSV.unlink()      # 冒烟产物可重复覆盖
    if L.REENT_CSV.exists():
        L.REENT_CSV.unlink()
    if L.TRANS_JL.exists():
        L.TRANS_JL.unlink()

    snaps = L.read_manifest()
    snap = next((s for s in snaps if s["snapshot_id"] == args.snap), None)
    assert snap, f"{args.snap} 不在 {args.mani}"
    refs = L.load_references()

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = SMOKE_DIR / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)
    env_spec = get_env_spec("libero")
    import argparse as _ap
    ns = _ap.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    print(f"[{datetime.now():%F %T}] boot shared vla+sam3 ...", flush=True)
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())

    sink = L.Sink()
    try:
        if args.skip_o4:
            # 纯本地:O0 + O1(O4 关闭,单测 N1 移植路径)
            steps = rt.load_steps(snap["episode_dir"])
            L.arm_O0(sink, snap, args.gpu, shared_kwargs, steps, K, set())
            L.arm_sample(sink, snap, args.gpu, shared_kwargs, steps, K,
                         set(), "O1", None)
        else:
            # sanity 传入本快照自身,保证 O1 即便达标也继续跑全部臂(冒烟目的)
            L.process_snapshot(snap, args.gpu, shared_kwargs, sink, K, refs,
                               L.done_rollouts(), sanity={snap["snapshot_id"]})
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass

    import csv, io
    lines = [l for l in open(L.ROLL_CSV, encoding="utf-8")
             if not l.startswith("#")]
    print(f"\n=== 冒烟 rollouts({len(lines) - 1} 行)===")
    for r in csv.DictReader(io.StringIO("".join(lines))):
        print({k: r[k] for k in ("snapshot_id", "arm", "rollout_idx",
                                 "contract_met", "check_success",
                                 "realignment_first", "n_prims", "wall_s",
                                 "end_reason", "note", "infra_abort")})
    print(f"=== reentry ===")
    for l in open(L.REENT_CSV, encoding="utf-8"):
        print(l.rstrip())
    if L.TRANS_JL.exists():
        print("=== transitions(首行前 600 字)===")
        print(open(L.TRANS_JL, encoding="utf-8").readline()[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
