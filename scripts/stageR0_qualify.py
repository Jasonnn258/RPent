#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage R §4 — R0 重建资格门(DEV pilot 8 事件 × 三臂 × R=4)。

规范:analysis/stageR_prereg.md §4(R0_TRIALS=4;门 |arm−LIVE|≤10pp;
双败 >10pp → STATE-RECONSTRUCTION NOT QUALIFIED → STOP;方法选择规则)。

流程(每事件,事件内臂序固定 LIVE→SNAP→PREFIX):
1. LIVE:第 1 次 fresh boot_to_pre(Pi0.5 前缀重放,observably matched)
   上采样 probe candidate 并冻结(该事件全部 12 个 trial 共用);
   LIVE ×4 = 每次全新 boot_to_pre(不 restore)→ exec probe;
2. SNAP:boot_bare 一次 → 4×(restore 原始 S_pre 字节 → exec probe);
3. PREFIX:boot_bare 一次 → 4×(reset+动作重放 → exec probe)。
统一 hold-through continuation + 双契约标签(Stage Q 冻结路径)。

产物:analysis/stageR_reconstruction_dev.csv + stageR_reconstruction_decision.md
(判定只基于 DEV 8 事件;R1 前冻结方法,禁按 TEST 切换)。

用法:
  nohup python scripts/stageR0_qualify.py --workers 2 \
      >> /workspace/yjx/tmp/stageR0.log 2>&1 &
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
import stageQ_rt as qt
import stageR_rt as srr

R0_TRIALS = 4
DEV_EVENTS = 8
LOG_ROOT = ROOT / "logs/stageR0"
CSV_PATH = ROOT / "analysis/stageR_reconstruction_dev.csv"
PROBE_JL = ROOT / "analysis/stageR0_probes.jsonl"
DECISION_MD = ROOT / "analysis/stageR_reconstruction_decision.md"

CSV_FIELDS = ["event_id", "task", "seed", "t0", "arm", "trial", "stable",
              "acquisition", "terminated_in_chunk", "chunk_class",
              "sha_match", "delta_max", "delta_l2", "readback_max_abs",
              "cand_sha", "wall_s", "note"]

WLOCK = threading.Lock()


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def load_probe_bank() -> dict:
    bank = {}
    if PROBE_JL.exists():
        for line in open(PROBE_JL, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                bank[r["event_id"]] = r
    return bank


def save_probe(ev, actions) -> None:
    import base64
    import numpy as np
    a = np.asarray(actions, dtype=np.float32)
    with WLOCK:
        with open(PROBE_JL, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event_id": ev["event_id"], "prompt": ev["prompt"],
                "cand_sha": srr.prt.chunk_sha(a), "shape": list(a.shape),
                "b64": base64.b64encode(a.tobytes()).decode()}) + "\n")


def decode_probe(rec) -> "np.ndarray":
    import base64
    import numpy as np
    return np.frombuffer(base64.b64decode(rec["b64"]),
                         dtype=np.float32).reshape(rec["shape"])


def done_set() -> set[tuple]:
    done = set()
    if CSV_PATH.exists():
        for r in csv.DictReader(open(CSV_PATH, encoding="utf-8")):
            done.add((r["event_id"], r["arm"], int(r["trial"])))
    return done


def write_row(row: dict) -> None:
    with WLOCK:
        new = not CSV_PATH.exists()
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)


def run_live(ev, gpu, shared, probe, trial_idx) -> dict:
    """LIVE 臂:全新 boot_to_pre(不 restore)→ exec probe。"""
    t0 = time.time()
    outdir = LOG_ROOT / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                         + f"_{ev['event_id']}_live{trial_idx}")
    with srr.BOOT_LOCK:
        ctx = srr.with_infra_retry(
            qt.boot_to_pre, ev, gpu, shared, outdir,
            label=f"{ev['event_id']}-live{trial_idx}-boot")
    try:
        cps = []
        out = srr.exec_trial(ctx, ev, probe, cps, "LIVE", trial_idx)
        return {"stable": out["stable"], "acquisition": out["acquisition"],
                "terminated_in_chunk": out["terminated_in_chunk"],
                "chunk_class": out["chunk_class"], "sha_match": "",
                "delta_max": "", "delta_l2": "",
                "readback_max_abs": "", "cand_sha": out["cand_sha"],
                "wall_s": round(time.time() - t0, 1), "note": "live_boot"}
    finally:
        srr.stop_ctx(ctx)


def run_snap_or_prefix(ev, gpu, shared, probe, arm: str) -> list[dict]:
    """SNAP/PREFIX 臂:boot_bare 一次 → R0_TRIALS × 独立重建 + exec。"""
    outdir = LOG_ROOT / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                         + f"_{ev['event_id']}_{arm.lower()}")
    with srr.BOOT_LOCK:
        ctx = srr.with_infra_retry(
            srr.boot_bare, ev, gpu, shared, outdir,
            label=f"{ev['event_id']}-{arm}-boot")
    rows = []
    try:
        for k in range(1, R0_TRIALS + 1):
            t0 = time.time()
            try:
                srr.with_infra_retry(
                    srr.reconstruct, ctx, ev, arm,
                    label=f"{ev['event_id']}-{arm}{k}-recon")
                out = srr.exec_trial(ctx, ev, probe, [], arm, k)
                cons = out.get("consistency") or {}
                rows.append({
                    "stable": out["stable"],
                    "acquisition": out["acquisition"],
                    "terminated_in_chunk": out["terminated_in_chunk"],
                    "chunk_class": out["chunk_class"],
                    "sha_match": cons.get("sha_match", ""),
                    "delta_max": (cons.get("flatten_delta") or {}).get(
                        "max_abs", ""),
                    "delta_l2": (cons.get("flatten_delta") or {}).get(
                        "l2", ""),
                    "readback_max_abs": cons.get("readback_max_abs",
                                                 "") if arm == "SNAPSHOT"
                        else "",
                    "cand_sha": out["cand_sha"],
                    "wall_s": round(time.time() - t0, 1), "note": ""})
            except rt.InfraError as exc:
                rows.append({"stable": "", "acquisition": "",
                             "terminated_in_chunk": "", "chunk_class": "",
                             "sha_match": "", "delta_max": "", "delta_l2": "",
                             "readback_max_abs": "", "cand_sha": "",
                             "wall_s": round(time.time() - t0, 1),
                             "note": f"infra: {exc}"[:200]})
    finally:
        srr.stop_ctx(ctx)
    return rows


def process_event(ev, gpu, shared, done) -> None:
    ev = srr.load_event_details(ev)
    tag = f"{ev['event_id']} t{ev['task']}s{ev['seed']} t0={ev['t0']}"
    log(f"== {tag} prefix={ev['n_prefix']} a_fail{ev['a_fail'].shape}")
    # probe 冻结(LIVE 第一次 boot 时采样一次;resume 时从 bank 复用)
    bank = load_probe_bank()
    if ev["event_id"] not in bank:
        outdir = LOG_ROOT / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                             + f"_{ev['event_id']}_probe")
        with srr.BOOT_LOCK:
            ctx = srr.with_infra_retry(
                qt.boot_to_pre, ev, gpu, shared, outdir,
                label=f"{ev['event_id']}-probe-boot")
        try:
            probe = srr.sample_fresh(
                {"prims": ctx["prims"], "prompt": ev["prompt"]}, ev)
        finally:
            srr.stop_ctx(ctx)
        save_probe(ev, probe)
        log(f"   probe 冻结 sha={srr.prt.chunk_sha(probe)}")
    else:
        log(f"   probe 复用 sha={bank[ev['event_id']]['cand_sha']}")
    probe = decode_probe(load_probe_bank()[ev["event_id"]])

    for k in range(1, R0_TRIALS + 1):
        if (ev["event_id"], "LIVE", k) in done:
            continue
        r = run_live(ev, gpu, shared, probe, k)
        write_row({"event_id": ev["event_id"], "task": ev["task"],
                   "seed": ev["seed"], "t0": ev["t0"], "arm": "LIVE",
                   "trial": k, **r})
        log(f"   LIVE {k}: stable={r['stable']} acq={r['acquisition']} "
            f"({r['wall_s']}s)")
    for arm in ("SNAP", "PREFIX"):
        rows = run_snap_or_prefix(ev, gpu, shared, probe, arm)
        for k, r in enumerate(rows, 1):
            if (ev["event_id"], arm, k) in done:
                continue
            write_row({"event_id": ev["event_id"], "task": ev["task"],
                       "seed": ev["seed"], "t0": ev["t0"], "arm": arm,
                       "trial": k, **r})
            log(f"   {arm} {k}: stable={r['stable']} "
                f"acq={r['acquisition']} sha={r['sha_match']} "
                f"dmax={r['delta_max']} ({r['wall_s']}s)")


def analyze_and_decide() -> dict:
    """汇总 + 门判定(prereg §4;只基于本 CSV,零额外 rollout)。"""
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    dev_ids = [e["event_id"] for e in srr.load_events()][:DEV_EVENTS]
    dev = [r for r in rows if r["event_id"] in dev_ids]

    def rate(arm):
        rs = [r for r in dev if r["arm"] == arm and r["stable"] != ""]
        n = len(rs)
        s = sum(1 for r in rs if r["stable"] == "True")
        return {"n": n, "stable": s, "rate": s / n if n else float("nan")}

    live, snap, pref = rate("LIVE"), rate("SNAP"), rate("PREFIX")
    d_snap = abs(snap["rate"] - live["rate"])
    d_pref = abs(pref["rate"] - live["rate"])
    qualified = d_snap <= 0.10 and d_pref <= 0.10
    both_fail = d_snap > 0.10 and d_pref > 0.10
    method = ("PREFIX" if d_pref <= d_snap + 0.05 else "SNAPSHOT") \
        if qualified else ""
    # PREFIX 一致性(资格旁证)
    prs = [r for r in dev if r["arm"] == "PREFIX" and r["sha_match"] != ""]
    sha_match = (sum(1 for r in prs if r["sha_match"] == "True")
                 / len(prs)) if prs else float("nan")
    dmax = [float(r["delta_max"]) for r in prs if r["delta_max"] != ""]
    dec = {"live": live, "snap": snap, "prefix": pref,
           "d_snap": d_snap, "d_pref": d_pref, "qualified": qualified,
           "both_fail": both_fail, "method": method,
           "prefix_sha_match_rate": sha_match,
           "prefix_delta_max_med": sorted(dmax)[len(dmax) // 2]
           if dmax else None}
    return dec


def write_decision(dec: dict) -> None:
    lines = [
        "# Stage R R0 — 重建资格判定(DEV pilot 8 事件)",
        "",
        f"生成:{datetime.datetime.now().isoformat(timespec='seconds')}",
        "",
        "| 臂 | n | stable | rate |",
        "|---|---|---|---|",
        f"| LIVE | {dec['live']['n']} | {dec['live']['stable']} "
        f"| {dec['live']['rate']:.3f} |",
        f"| SNAP | {dec['snap']['n']} | {dec['snap']['stable']} "
        f"| {dec['snap']['rate']:.3f} |",
        f"| PREFIX | {dec['prefix']['n']} | {dec['prefix']['stable']} "
        f"| {dec['prefix']['rate']:.3f} |",
        "",
        f"|SNAP−LIVE| = {dec['d_snap']:.3f};|PREFIX−LIVE| = "
        f"{dec['d_pref']:.3f}(门 ≤0.10)",
        "",
        f"PREFIX sha 逐位一致率:{dec['prefix_sha_match_rate']:.3f};"
        f"flatten Δmax 中位:{dec['prefix_delta_max_med']}",
        "",
    ]
    if dec["both_fail"]:
        lines += ["## 判定:STATE-RECONSTRUCTION NOT QUALIFIED → Stage R STOP",
                  "", "双臂均 >10pp(prereg §4);不进入 R1。"]
    elif dec["qualified"]:
        lines += [f"## 判定:QUALIFIED;R1 重建方法冻结 = {dec['method']}",
                  "",
                  ("选择规则:|PREFIX−LIVE| ≤ |SNAP−LIVE|+5pp → PREFIX_REPLAY,"
                   " 否则 DIRECT_SNAPSHOT。R1 全程使用该方法,禁切换。")]
    else:
        lines += ["## 判定:单臂未过门(非双败)→ 按 §4 仍需 STOP 复核",
                  "",
                  "双臂均须 ≤10pp;单臂 >10pp 时以 NOT QUALIFIED 记录,"
                  "细节见 prereg §4 与 deviation。"]
    DECISION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    if args.analyze_only:
        write_decision(analyze_and_decide())
        log(f"decision 写入 {DECISION_MD}")
        return 0

    ox.pg.preflight(label="stageR0", lock_name="stageR0.lock")

    events = srr.load_events()
    if len(events) < DEV_EVENTS:
        log(f"WARN: included 事件 {len(events)} < {DEV_EVENTS}"
            "(采集配额未满,prereg §5 容差内继续)")
    dev_events = events[:DEV_EVENTS]
    done = done_set()
    log(f"R0: {len(dev_events)} DEV 事件 × 3 臂 × {R0_TRIALS};"
        f"resume done={len(done)}")

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources
    ensure_resources("libero")
    shared_root = LOG_ROOT / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)
    env_spec = get_env_spec("libero")
    import argparse as _ap
    ns = _ap.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None)
    log("boot shared vla+sam3 ...")
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())

    pending = deque(dev_events)
    plock = threading.Lock()

    def worker():
        while True:
            with plock:
                if not pending:
                    return
                ev = pending.popleft()
            try:
                process_event(ev, args.gpu, shared_kwargs, done)
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

    write_decision(analyze_and_decide())
    log(f"R0 完成;decision → {DECISION_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
