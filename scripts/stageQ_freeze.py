#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage Q §6 — Q1 快照 manifest 物化 + DEV/TEST 划分 + hash 冻结。

镜像 stageP_freeze.py,差异(prereg §3/§6):
- 每事件物化 = boot_to_pre(重放 1..t0−1 → S_pre)→ run_fail_pick(守卫
  仍 FG)→ S_post,记录双侧 sha16/eef/check_success(同 boot 成对);
- S_post 为重采样产物(每次 boot 的失败 pick 不同 → post sha 逐 boot 变,
  manifest 记录本次物化指纹作 provenance,factorial runner 重跑时另记);
- 命名 qsnap_XX;DEV/TEST = collect 序奇偶。

产物:analysis/stageQ_split_manifest.csv(头注含整文件 sha256)。

用法:
  MUJOCO_GL=osmesa python scripts/stageQ_freeze.py --gpu 0
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
import stageQ_rt as qt

LEDGER = REPO / "analysis/stageQ_collect_ledger.csv"
OUT = REPO / "analysis/stageQ_split_manifest.csv"
LOG_ROOT = REPO / "logs/stageQ_freeze"
SPLIT_SEED = 20261005       # §6 复核记录(规则确定,不实际消费)
FG_QUOTA = 20               # §6 容差上限

FIELDS = ["snapshot_id", "family", "procedure", "task", "seed", "t0",
          "episode_dir", "collect_seq", "split", "event_rule", "collect_ts",
          "pre_state_len", "pre_sha16", "post_sha16", "eef_pre", "eef_post",
          "check_success_at_post", "target_of_interest"]

BOOT_LOCK = None            # 单进程顺序物化,无需锁(占位保持结构一致)


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}]", msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()
    rt.apply_env_overrides()

    rows = [r for r in csv.DictReader(open(LEDGER, encoding="utf-8"))
            if r.get("included") == "True"]
    assert rows, "ledger 无 included 行(采集未完成或全失败)"
    dropped = rows[FG_QUOTA:]                     # 越界在途截断(dev-Q 同 P)
    rows = rows[:FG_QUOTA]
    if dropped:
        log(f"配额截断:{len(rows)+len(dropped)} → 前 {FG_QUOTA}"
            f"(丢:{[(d['task'], d['seed']) for d in dropped]})")
    log(f"ledger included {len(rows)} FG 事件;物化开始(boot→S_pre→fail "
        f"pick→S_post,每事件独立 boot)")

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
        sam3_endpoint=None, libero_type=None)
    log("boot shared vla+sam3 ...")
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())

    out_rows, n_infra = [], 0
    try:
        for i, r in enumerate(rows):
            collect_seq = i + 1
            split = "DEV" if collect_seq % 2 == 1 else "TEST"
            snap = {
                "snapshot_id": f"qsnap_{i:02d}",
                "family": r["assigned_family"],
                "procedure": rt.FAM2PROC[r["assigned_family"]],
                "task": r["task"], "seed": r["seed"], "t0": r["assigned_t0"],
                "episode_dir": r["episode_dir"], "collect_seq": collect_seq,
                "split": split,
            }
            tag = f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}"
            ctx = None
            for attempt in range(1, 4):
                try:
                    outdir = LOG_ROOT / (
                        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
                    ctx = qt.boot_to_pre(snap, args.gpu, shared_kwargs, outdir)
                    cap_pre = qt.capture_state(ctx, ctx["S"], "S_pre")
                    S_post = qt.run_fail_pick(ctx, snap)
                    cap_post = qt.capture_state(ctx, S_post, "S_post")
                    break
                except Exception as exc:
                    if ctx:
                        qt.stop_ctx(ctx)
                        ctx = None
                    log(f"  {tag} INFRA({attempt}/3): "
                        f"{type(exc).__name__}: {str(exc)[:100]}")
            if ctx is None:
                n_infra += 1
                out_rows.append({**snap, "event_rule": r.get("note", ""),
                                 "collect_ts": r.get("episode_dir", "")
                                 .split("/")[-1],
                                 "pre_state_len": "",
                                 "pre_sha16": "INFRA_ABORT_3attempts"})
                continue
            try:
                out_rows.append({**snap,
                                 "event_rule": r.get("note", ""),
                                 "collect_ts": r.get("episode_dir", "")
                                 .split("/")[-1],
                                 "pre_state_len": int(len(ctx["S"])),
                                 "pre_sha16": cap_pre["state_sha16"],
                                 "post_sha16": cap_post["state_sha16"],
                                 "eef_pre": json.dumps(
                                     [round(c, 4) for c in cap_pre["eef"]]),
                                 "eef_post": json.dumps(
                                     [round(c, 4) for c in cap_post["eef"]]),
                                 "check_success_at_post":
                                     cap_post["check_success"],
                                 "target_of_interest": ctx["target"] or ""})
                log(f"  {tag} seq={collect_seq} {split} t0={snap['t0']} "
                    f"pre={cap_pre['state_sha16']} post="
                    f"{cap_post['state_sha16']} succ@post="
                    f"{cap_post['check_success']}")
            finally:
                qt.stop_ctx(ctx)
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(out_rows)
    body = buf.getvalue()
    sha = hashlib.sha256(body.encode()).hexdigest()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(f"# stageQ_split_manifest | frozen "
                f"{datetime.now().isoformat()} | n={len(out_rows)} | "
                f"split_seed={SPLIT_SEED}(未消费,规则=collect序奇偶)\n")
        f.write("# post_sha16 为本次物化指纹(fail pick 每次重采样 → "
                "factorial 重跑另记);pre_sha16 同理\n")
        f.write(f"# sha256(body)={sha}\n")
        f.write(body)
    n_dev = sum(1 for r in out_rows if r["split"] == "DEV")
    n_test = sum(1 for r in out_rows if r["split"] == "TEST")
    log(f"manifest 冻结:n={len(out_rows)} DEV={n_dev} TEST={n_test} "
        f"INFRA_ABORT={n_infra} sha256={sha[:16]}…")
    if len(out_rows) - n_infra < 18:
        log(f"INSUFFICIENT_SNAPSHOTS: 可用 "
            f"{len(out_rows)-n_infra} < 18(§6 容差下限)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
