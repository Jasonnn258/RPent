#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage P §6 — P1 快照 manifest 物化 + DEV/TEST 划分 + hash 冻结。

读 stageP_collect_ledger.csv 的 included 行(收集顺序 = ledger 写入顺序,
不做任何排序),对每行重放 1..t0(dev-O5 守卫在 rt.boot_snapshot 内)
→ save_state,记录 state sha16/eef0/check_success@t0/target。

DEV/TEST 划分(prereg §6 冻结):collect 顺序编号 1..n,**奇数序 → DEV、
偶数序 → TEST**(纯确定性规则;预注册 seed=20261003 仅作复核记录,规则
本身不随机)。划分先于任何 P1 执行,manifest 冻结即定。

产物:analysis/stageP_split_manifest.csv(头部注释含整文件 sha256)。
物化失败(INFRA_ABORT 3 次重试)行如实记录,计数 <20 时打印
INSUFFICIENT_SNAPSHOTS 警告。

用法:
  MUJOCO_GL=osmesa python scripts/stageP_freeze.py --gpu 0
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

LEDGER = REPO / "analysis/stageP_collect_ledger.csv"
OUT = REPO / "analysis/stageP_split_manifest.csv"
LOG_ROOT = REPO / "logs/stageP_freeze"
SPLIT_SEED = 20261003       # §6 预注册复核 seed(规则确定,不实际消费)
FG_QUOTA = 28               # dev-P2 顺序停止上限(容差上限)

FIELDS = ["snapshot_id", "family", "procedure", "task", "seed", "t0",
          "episode_dir", "collect_seq", "split", "event_rule", "collect_ts",
          "state_len", "state_sha16", "eef0", "check_success_at_t0",
          "target_of_interest"]


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()
    rt.apply_env_overrides()

    rows = [r for r in csv.DictReader(open(LEDGER, encoding="utf-8"))
            if r.get("included") == "True"]
    assert rows, "ledger 无 included 行(采集未完成或全失败)"
    # dev-P2 停止规则上限:并发窗口(3 workers)可能越过配额在途全中,
    # 采集实测 30>28;按冻结的容差上限确定性截断(collect 序前 28,
    # 非结果筛选),被截行留在 ledger 不物化。
    dropped = rows[FG_QUOTA:]
    rows = rows[:FG_QUOTA]
    if dropped:
        log(f"配额截断:ledger included {len(rows)+len(dropped)} → 取前 "
            f"{FG_QUOTA}(丢弃 collect 序 {FG_QUOTA+1}.."
            f"{len(rows)+len(dropped)}:{[(d['task'], d['seed']) for d in dropped]})")
    log(f"ledger included {len(rows)} FG 快照;DEV/TEST = collect 序奇偶"
        f"(seed {SPLIT_SEED} 仅记录);开始物化")

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

    out_rows, n_infra = [], 0
    try:
        for i, r in enumerate(rows):
            collect_seq = i + 1                     # 1 起,collect 顺序
            split = "DEV" if collect_seq % 2 == 1 else "TEST"
            snap = {
                "snapshot_id": f"psnap_{i:02d}",
                "family": r["assigned_family"],
                "procedure": rt.FAM2PROC[r["assigned_family"]],
                "task": r["task"], "seed": r["seed"],
                "t0": r["assigned_t0"], "episode_dir": r["episode_dir"],
                "collect_seq": collect_seq, "split": split,
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
                n_infra += 1
                log(f"  {tag} 物化失败(INFRA_ABORT),跳过并记录")
                out_rows.append({**snap,
                                 "event_rule": r.get("note", ""),
                                 "collect_ts":
                                     r.get("episode_dir", "").split("/")[-1],
                                 "state_len": "",
                                 "state_sha16": "INFRA_ABORT_3attempts"})
                continue
            base = ctx["base"]
            out_rows.append({**snap,
                             "event_rule": r.get("note", ""),
                             "collect_ts":
                                 r.get("episode_dir", "").split("/")[-1],
                             "state_len": int(len(ctx["S"])),
                             "state_sha16": ctx["state_hash"],
                             "eef0": json.dumps(
                                 [round(c, 4) for c in base["eef"]]),
                             "check_success_at_t0": base["check_success"],
                             "target_of_interest": ctx["target"] or ""})
            log(f"  {tag} seq={collect_seq} {split} t0={snap['t0']} "
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
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(out_rows)
    body = buf.getvalue()
    sha = hashlib.sha256(body.encode()).hexdigest()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(f"# stageP_split_manifest | frozen {datetime.now().isoformat()}"
                f" | n={len(out_rows)} | split_seed={SPLIT_SEED}(未消费,"
                f"规则=collect序奇偶)\n")
        f.write(f"# sha256(body)={sha}\n")
        f.write(body)
    n_dev = sum(1 for r in out_rows if r["split"] == "DEV")
    n_test = sum(1 for r in out_rows if r["split"] == "TEST")
    n_ok = len(out_rows) - n_infra
    log(f"manifest 冻结:{OUT}(n={len(out_rows)}, DEV={n_dev}, "
        f"TEST={n_test}, INFRA_ABORT={n_infra}, sha256={sha[:16]}…)")
    if n_ok < 20:
        log(f"INSUFFICIENT_SNAPSHOTS: 可用快照 {n_ok} < 20(§10 容差下限)"
            "→ 按 prereg 停并报告,不进 P1 执行")
    if n_dev < 10 or n_test < 10:
        log(f"WARN: DEV/TEST 侧偏(DEV={n_dev} TEST={n_test})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
