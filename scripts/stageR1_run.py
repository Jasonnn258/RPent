#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage R §6 — R1 双臂执行(24 事件 × SAME-ACTION×8 / RESAMPLE×8 / NATURAL×4)。

规范:analysis/stageR_prereg.md §6/§7/§11(前瞻队列、K=8、独立重建、
infra 分类)。前置:R0 decision 必须 QUALIFIED 且方法已冻结。

臂定义:
- Arm A SAME-ACTION:a_fail(t0 首 chunk)×8,每次独立重建后执行;
- Arm B POLICY RESAMPLE:fresh candidate ×8(同 obs 语义,仅重采样);
- NATURAL(descriptive)×4:restore 原始 S_post → fresh candidate →
  同 continuation;不入 C(k) 与 persistence 因果证据。

产物:stageR_manifest.csv、stageR_failure_events.jsonl、
stageR_same_action_rollouts.csv、stageR_resample_rollouts.csv(NATURAL 行
arm=NATURAL 陪报)、stageR_trial_checkpoints.jsonl(审计)。

用法:
  nohup python scripts/stageR1_run.py --workers 2 \
      >> /workspace/yjx/tmp/stageR1.log 2>&1 &
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
import threading
import time
import traceback
from collections import deque
from pathlib import Path

ROOT = Path("/workspace/yjx/workspace/RPent")
sys.path.insert(0, str(ROOT / "scripts"))
import ovpm_exp as ox
import stageO_rt as rt
import stageR_rt as srr

K_SAME = 8
K_RESAMPLE = 8
K_NATURAL = 4
DEV_EVENTS = 8                    # R0 pilot 占用前 8,R1 cohort 从第 9 起

LOG_ROOT = ROOT / "logs/stageR1"
MANIFEST = ROOT / "analysis/stageR_manifest.csv"
EVENTS_JL = ROOT / "analysis/stageR_failure_events.jsonl"
CSV_SAME = ROOT / "analysis/stageR_same_action_rollouts.csv"
CSV_RES = ROOT / "analysis/stageR_resample_rollouts.csv"
CPS_JL = ROOT / "analysis/stageR_trial_checkpoints.jsonl"
DECISION_MD = ROOT / "analysis/stageR_reconstruction_decision.md"

CSV_FIELDS = ["event_id", "task", "seed", "t0", "arm", "trial", "stable",
              "acquisition", "terminated_in_chunk", "chunk_class",
              "chunks_used", "cand_sha", "recon_sha_match", "delta_max",
              "wall_s", "note"]

WLOCK = threading.Lock()


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def frozen_method() -> str:
    """从 R0 decision md 读冻结方法(QUALIFIED 行;缺失 → 拒跑)。"""
    if not DECISION_MD.exists():
        raise SystemExit("R0 decision 不存在 — 先跑 stageR0_qualify.py")
    txt = DECISION_MD.read_text(encoding="utf-8")
    if "NOT QUALIFIED" in txt:
        raise SystemExit("R0 判定 NOT QUALIFIED — Stage R STOP(prereg §4)")
    for m in ("PREFIX", "SNAPSHOT"):
        if f"R1 重建方法冻结 = {m}" in txt:
            return m
    raise SystemExit("R0 decision 未含冻结方法 — 复核 stageR_reconstruction_"
                     "decision.md")


def append_csv(path: Path, row: dict) -> None:
    with WLOCK:
        new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)


def done_set() -> set[tuple]:
    done = set()
    for p in (CSV_SAME, CSV_RES):
        if p.exists():
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if r.get("event_id"):
                    done.add((r["event_id"], r["arm"], int(r["trial"])))
    return done


def write_manifest(events: list[dict], method: str) -> None:
    """§34 队列冻结产物(manifest csv + events jsonl;只写一次,resume 幂等)。"""
    if MANIFEST.exists() and EVENTS_JL.exists():
        return
    fields = ["event_id", "ord", "task", "seed", "t0", "role", "n_prefix",
              "a_fail_shape", "pre_sha16", "post_sha16", "a_fail_sha16",
              "prompt", "method"]
    rows, jl = [], []
    for ev in events:
        role = "R0_DEV" if ev["ord"] <= DEV_EVENTS else "R1_COHORT"
        rows.append({**{k: ev[k] for k in
                        ("event_id", "ord", "task", "seed", "t0", "role",
                         "n_prefix", "pre_sha16", "post_sha16",
                         "a_fail_sha16", "prompt")},
                     "a_fail_shape": "x".join(map(str, ev["a_fail"].shape)),
                     "method": method if role == "R1_COHORT" else "n/a"})
        jl.append({"event_id": ev["event_id"], "task": ev["task"],
                   "seed": ev["seed"], "t0": ev["t0"], "role": role,
                   "episode_dir": ev["episode_dir"],
                   "prompt": ev["prompt"], "target": None,
                   "n_prefix_actions": ev["n_prefix"],
                   "a_fail_sha16": ev["a_fail_sha16"],
                   "pre_sha16": ev["pre_sha16"],
                   "post_sha16": ev["post_sha16"]})
    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(EVENTS_JL, "w", encoding="utf-8") as f:
        for r in jl:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"manifest 冻结:{len(rows)} 事件 → {MANIFEST.name} / {EVENTS_JL.name}")


def record_trial(ev, ctx, arm, k, actions, note="") -> dict:
    """一次尝试(reconstruct 已由调用方完成)→ 执行 + 落盘。"""
    cps = []
    out = srr.exec_trial(ctx, ev, actions, cps, arm, k)
    cons = out.get("consistency") or {}
    fd = cons.get("flatten_delta") or {}
    row = {"event_id": ev["event_id"], "task": ev["task"], "seed": ev["seed"],
           "t0": ev["t0"], "arm": arm, "trial": k,
           "stable": out["stable"], "acquisition": out["acquisition"],
           "terminated_in_chunk": out["terminated_in_chunk"],
           "chunk_class": out["chunk_class"],
           "chunks_used": (out.get("pick") or {}).get("chunks_used", ""),
           "cand_sha": out["cand_sha"],
           "recon_sha_match": cons.get("sha_match", ""),
           "delta_max": fd.get("max_abs", ""), "wall_s": 0.0, "note": note}
    # NATURAL 臂从 S_post restore:consistency 无 sha 字段 → 留空
    with WLOCK, open(CPS_JL, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "event_id": ev["event_id"], "arm": arm, "trial": k,
            "cps": rt.jsonable(cps)}, ensure_ascii=False) + "\n")
    return row


def process_event(ev, gpu, shared, method, done) -> None:
    ev = srr.load_event_details(ev)
    tag = f"{ev['event_id']} t{ev['task']}s{ev['seed']} t0={ev['t0']}"
    log(f"== {tag} method={method} prefix={ev['n_prefix']}")
    outdir = LOG_ROOT / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                         + f"_{ev['event_id']}")
    with srr.BOOT_LOCK:
        ctx = srr.with_infra_retry(srr.boot_bare, ev, gpu, shared, outdir,
                                   label=f"{ev['event_id']}-boot")
    try:
        # ---- Arm A:SAME-ACTION(a_fail × K_same,每次独立重建)----
        for k in range(1, K_SAME + 1):
            if (ev["event_id"], "SAME", k) in done:
                continue
            t0 = time.time()
            try:
                srr.with_infra_retry(srr.reconstruct, ctx, ev, method,
                                     label=f"{ev['event_id']}-A{k}")
                row = record_trial(ev, ctx, "SAME", k, ev["a_fail"])
            except rt.InfraError as exc:
                row = {"event_id": ev["event_id"], "task": ev["task"],
                       "seed": ev["seed"], "t0": ev["t0"], "arm": "SAME",
                       "trial": k, "note": f"infra: {exc}"[:200]}
            row["wall_s"] = round(time.time() - t0, 1)
            append_csv(CSV_SAME, row)
            log(f"   A/SAME {k}: stable={row.get('stable')} "
                f"acq={row.get('acquisition')} ({row['wall_s']}s)")
        # ---- Arm B:POLICY RESAMPLE(fresh candidate × K_resample)----
        for k in range(1, K_RESAMPLE + 1):
            if (ev["event_id"], "RESAMPLE", k) in done:
                continue
            t0 = time.time()
            try:
                srr.with_infra_retry(srr.reconstruct, ctx, ev, method,
                                     label=f"{ev['event_id']}-B{k}")
                cand = srr.sample_fresh(ctx, ev)
                row = record_trial(ev, ctx, "RESAMPLE", k, cand)
            except rt.InfraError as exc:
                row = {"event_id": ev["event_id"], "task": ev["task"],
                       "seed": ev["seed"], "t0": ev["t0"], "arm": "RESAMPLE",
                       "trial": k, "note": f"infra: {exc}"[:200]}
            row["wall_s"] = round(time.time() - t0, 1)
            append_csv(CSV_RES, row)
            log(f"   B/RESAMPLE {k}: stable={row.get('stable')} "
                f"acq={row.get('acquisition')} ({row['wall_s']}s)")
        # ---- NATURAL(descriptive):restore 原始 S_post → fresh → exec ----
        for k in range(1, K_NATURAL + 1):
            if (ev["event_id"], "NATURAL", k) in done:
                continue
            t0 = time.time()
            try:
                ctx["S"] = ev["S_post"]
                srr.with_infra_retry(
                    lambda: (rt.restore_checked(ctx, f"{ev['event_id']}-nat{k}"),
                             srr._finish_base(ctx, {"method": "S_POST"}))[1],
                    label=f"{ev['event_id']}-N{k}")
                cand = srr.sample_fresh(ctx, ev)
                row = record_trial(ev, ctx, "NATURAL", k, cand,
                                   note="from_S_post_descriptive")
            except rt.InfraError as exc:
                row = {"event_id": ev["event_id"], "task": ev["task"],
                       "seed": ev["seed"], "t0": ev["t0"], "arm": "NATURAL",
                       "trial": k, "note": f"infra: {exc}"[:200]}
            row["wall_s"] = round(time.time() - t0, 1)
            append_csv(CSV_RES, row)
            log(f"   N/NATURAL {k}: stable={row.get('stable')} "
                f"acq={row.get('acquisition')} ({row['wall_s']}s)")
    finally:
        srr.stop_ctx(ctx)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()

    method = frozen_method()
    ox.pg.preflight(label="stageR1", lock_name="stageR1.lock")

    events = [srr.load_event_details(e) for e in srr.load_events()]
    cohort = [e for e in events if e["ord"] > DEV_EVENTS]
    log(f"R1:cohort {len(cohort)} 事件(cohort 序);method={method};"
        f"K_same={K_SAME} K_resample={K_RESAMPLE} K_nat={K_NATURAL}")
    write_manifest(events, method)
    done = done_set()

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

    pending = deque(cohort)
    plock = threading.Lock()

    def worker():
        while True:
            with plock:
                if not pending:
                    return
                ev = pending.popleft()
            try:
                process_event(ev, args.gpu, shared_kwargs, method, done)
            except Exception as exc:
                log(f"{ev['event_id']} EXC {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()[-500:]}")

    try:
        threads = [threading.Thread(target=worker, daemon=True)
                   for _ in range(max(1, args.workers))]
        for t in threads:
            t.start()
            time.sleep(ox.STAGGER_S)
        for t in threads:
            t.join()
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    log("R1 完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
