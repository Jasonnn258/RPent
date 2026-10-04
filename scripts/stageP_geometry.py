#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage P §7 — P1 Candidate Support Geometry(唯一 confirmatory runner)。

预注册:analysis/stageP_prereg.md §7(K_MAX=8、candidate 独立、R_CONT=3)。
数据:stageP_split_manifest.csv 可用行(DEV 13 / TEST 11;INFRA_ABORT 行跳过)。

冻结执行序(每快照):
  boot(dev-O5 守卫)→ restore → **连续采 8 个 candidate**(生成序即冻结序,
  全部从同一 failure-state obs、执行前落盘 analysis/stageP_candidates.jsonl,
  断点只复用不补采)→ 逐 candidate:
  restore(S) → chunk → 存 S_j → 3 次独立 restore(S_j)+续跑 → 标签(§4)。
  candidate 间相互独立:每个都从 original S 出发(§7)。

指标(analyze,TEST=confirmatory / DEV=sanity):
  Oracle@1/2/4/8(前 K 个 candidate 含 RECOVERY_CAND 的快照比例)、
  SUPPORTED_SNAPSHOT_RATE(K=8)、MIXED_SUPPORT_RATE;Wilson 95% CI;
  per-snapshot 表。gate(§15,TEST):Oracle@8−Oracle@1 ≥15pp ∧
  SUPPORTED ≥50% ∧ MIXED ≥30%。

产物:stageP_candidates.jsonl、stageP_candidate_outcomes.csv、
stageP_support_geometry.csv、stageP1_results.md、stageP1_decision.md。

用法:
  nohup python scripts/stageP_geometry.py --gpu 0 --workers 2 \
      >> /workspace/yjx/tmp/stageP_geometry.log 2>&1 &
  python scripts/stageP_geometry.py --analyze-only
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt
import stageP_rt as prt
import ovpm_exp as ox

MANI = REPO / "analysis/stageP_split_manifest.csv"
CAND_JL = REPO / "analysis/stageP_candidates.jsonl"
OUT_CSV = REPO / "analysis/stageP_candidate_outcomes.csv"
GEO_CSV = REPO / "analysis/stageP_support_geometry.csv"
RES_MD = REPO / "analysis/stageP1_results.md"
DEC_MD = REPO / "analysis/stageP1_decision.md"
LOG_ROOT = REPO / "logs/stageP_geometry"

K_MAX = 8                     # §7
MAX_INFRA_RETRY = 3
GATE_ORACLE_DELTA = 0.15      # §7 gate(TEST)
GATE_SUPPORTED = 0.50
GATE_MIXED = 0.30

OUT_COLS = [
    "snapshot_id", "split", "family", "task", "seed", "t0", "cand_idx",
    "cand_sha", "n_rec", "n_harm", "n_cont", "cand_label",
    "cont_labels", "terminated_in_chunk", "pick_success", "ee_class",
    "contact_class", "obj_class", "wall_s", "infra_abort", "note",
]

WRITE_LOCK = threading.Lock()


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def read_manifest() -> list[dict]:
    lines = [l for l in MANI.read_text().splitlines() if not l.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    ok = [r for r in rows if r["state_sha16"] != "INFRA_ABORT_3attempts"]
    return ok


def load_frozen() -> dict[str, list[dict]]:
    frozen: dict[str, list[dict]] = {}
    if CAND_JL.exists():
        for line in CAND_JL.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                frozen.setdefault(rec["snapshot_id"], []).append(rec)
    return frozen


def done_outcomes() -> dict[str, set[int]]:
    """已完成的 (snapshot → cand_idx 集合):有有效 outcome 行者。"""
    done: dict[str, set[int]] = {}
    if OUT_CSV.exists():
        for r in csv.DictReader(open(OUT_CSV)):
            if not r.get("infra_abort"):
                done.setdefault(r["snapshot_id"], set()).add(
                    int(r["cand_idx"]))
    return done


def append_jsonl(path: Path, rec: dict):
    with WRITE_LOCK:
        with open(path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()


class Sink:
    def __init__(self):
        if not OUT_CSV.exists():
            with open(OUT_CSV, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=OUT_COLS).writeheader()

    def row(self, r: dict):
        with WRITE_LOCK:
            with open(OUT_CSV, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=OUT_COLS,
                               extrasaction="ignore").writerow(r)


def stop_ctx(ctx):
    for d in (ctx.get("daemons") or []):
        try:
            d.stop()
        except Exception:
            pass


def boot(snap: dict, gpu: int, shared_kwargs: dict, tag: str):
    for attempt in range(1, MAX_INFRA_RETRY + 1):
        try:
            outdir = LOG_ROOT / (
                f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
            return rt.boot_snapshot(snap, gpu, shared_kwargs, outdir, note=tag)
        except Exception as exc:
            log(f"    boot INFRA({attempt}/{MAX_INFRA_RETRY}) {tag}: "
                f"{type(exc).__name__}: {str(exc)[:120]}")
    return None


def process_snapshot(snap: dict, gpu: int, shared_kwargs: dict, sink: Sink):
    sid = snap["snapshot_id"]
    split = snap["split"]
    steps = rt.load_steps(snap["episode_dir"])
    prompt = prt.pre_prompt_of(snap)

    frozen = load_frozen().get(sid, [])
    done = done_outcomes().get(sid, set())

    ctx = boot(snap, gpu, shared_kwargs, f"{sid}_t{snap['task']}s{snap['seed']}")
    if ctx is None:
        sink.row({"snapshot_id": sid, "split": split, "family": "FALSE_GRASP",
                  "task": snap["task"], "seed": snap["seed"], "t0": snap["t0"],
                  "infra_abort": "boot_3attempts"})
        return
    try:
        # ① 执行前连续采样 + 冻结(同一 failure-state obs,零 env 步进)
        if len(frozen) >= K_MAX:
            log(f"    reuse {len(frozen)} frozen candidates(不重采)")
        elif frozen:
            log(f"    partial freeze {len(frozen)}/{K_MAX} — 不补采(冻结纪律)")
        else:
            for i in range(K_MAX):
                try:
                    actions = prt.sample_candidate(ctx["prims"], prompt)
                except Exception as exc:
                    log(f"    gen INFRA cand{i+1}: {type(exc).__name__}: "
                        f"{str(exc)[:100]}")
                    break
                append_jsonl(CAND_JL, {
                    "snapshot_id": sid, "split": split, "cand_idx": i + 1,
                    "frozen_ts": datetime.now().isoformat(), "prompt": prompt,
                    "cand_sha": prt.chunk_sha(actions),
                    "actions": [[float(v) for v in row] for row in actions]})
                log(f"    frozen cand{i+1}/{K_MAX}")
            frozen = load_frozen().get(sid, [])

        # ② 逐 candidate 执行(每个都从 original S 出发)
        for rec in frozen:
            ci = int(rec["cand_idx"])
            if ci in done:
                continue
            actions = np.asarray(rec["actions"], dtype=np.float32)
            for attempt in range(1, MAX_INFRA_RETRY + 1):
                t0 = time.time()
                checkpoints: list[dict] = []
                try:
                    res = prt.execute_candidate_with_continuation(
                        ctx, snap, prompt, actions, checkpoints)
                    break
                except Exception as exc:
                    log(f"    exec INFRA({attempt}/{MAX_INFRA_RETRY}) "
                        f"cand{ci}: {type(exc).__name__}: {str(exc)[:120]}")
                    res = None
            if res is None:
                sink.row({"snapshot_id": sid, "split": split,
                          "family": "FALSE_GRASP", "task": snap["task"],
                          "seed": snap["seed"], "t0": snap["t0"],
                          "cand_idx": ci, "cand_sha": rec["cand_sha"],
                          "infra_abort": f"{MAX_INFRA_RETRY}_attempts"})
                continue
            cls = prt.classify_chunk(res["chunk_pre"], res["chunk_post"])
            picks = [c.get("pick", {}).get("success", "")
                     for c in res["conts"]]
            sink.row({
                "snapshot_id": sid, "split": split, "family": "FALSE_GRASP",
                "task": snap["task"], "seed": snap["seed"], "t0": snap["t0"],
                "cand_idx": ci, "cand_sha": rec["cand_sha"],
                "n_rec": res["n_rec"], "n_harm": res["n_harm"],
                "n_cont": len(res["labels"]),
                "cand_label": res["cand_label"],
                "cont_labels": ";".join(res["labels"]),
                "terminated_in_chunk": int(res["terminated_in_chunk"]),
                "pick_success": ";".join(str(p) for p in picks),
                "ee_class": cls["ee_class"], "contact_class":
                    cls["contact_class"], "obj_class": cls["obj_class"],
                "wall_s": round(time.time() - t0, 1)})
            # 审计明细:测量点落 logs(不进 analysis/)
            append_jsonl(LOG_ROOT / "checkpoints.jsonl", {
                "snapshot_id": sid, "split": split, "cand_idx": ci,
                "cand_sha": rec["cand_sha"], "ts": datetime.now().isoformat(),
                "points": [{k: v for k, v in cp.items()
                            if k in ("eef", "pos", "check_success",
                                     "terminated", "grip")}
                           for cp in checkpoints]})
            log(f"    cand{ci} {res['cand_label']} "
                f"rec={res['n_rec']}/3 harm={res['n_harm']}/3")
    finally:
        stop_ctx(ctx)


# ---- 分析:支撑几何 + gate ---------------------------------------------------
def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def analyze():
    rows = [r for r in csv.DictReader(open(OUT_CSV))
            if not r.get("infra_abort")]
    geo_rows, tables = [], {}
    for split in ("TEST", "DEV"):
        sn = {}
        for r in rows:
            if r["split"] != split:
                continue
            sn.setdefault(r["snapshot_id"], {})[int(r["cand_idx"])] = r
        snaps = sorted(sn)
        for sid in snaps:
            cand = sn[sid]
            ks = sorted(cand)
            labels = [cand[k]["cand_label"] for k in ks]
            recs = [l == "RECOVERY" for l in labels]
            geo_rows.append({
                "snapshot_id": sid, "split": split,
                "n_cand": len(ks),
                "oracle1": int(any(recs[:1])), "oracle2": int(any(recs[:2])),
                "oracle4": int(any(recs[:4])),
                "oracle8": int(any(recs)),
                "supported": int(any(recs)),
                "mixed": int(any(recs) and not all(recs)),
                "n_rec_cand": sum(recs),
                "first_rec_idx": (recs.index(True) + 1) if any(recs) else "",
            })
        g = [r for r in geo_rows if r["split"] == split]
        n = len(g)
        def rate(k):
            return (sum(r[k] for r in g) / n) if n else float("nan")
        tables[split] = {
            "n_snapshot": n,
            "oracle1": rate("oracle1"), "oracle2": rate("oracle2"),
            "oracle4": rate("oracle4"), "oracle8": rate("oracle8"),
            "supported": rate("supported"), "mixed": rate("mixed"),
        }
    with open(GEO_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["snapshot_id", "split", "n_cand",
                                          "oracle1", "oracle2", "oracle4",
                                          "oracle8", "supported", "mixed",
                                          "n_rec_cand", "first_rec_idx"])
        w.writeheader()
        w.writerows(geo_rows)
    t = tables.get("TEST", {})
    d1, d8 = t.get("oracle1", float("nan")), t.get("oracle8", float("nan"))
    passed = (t and d8 - d1 >= GATE_ORACLE_DELTA
              and t["supported"] >= GATE_SUPPORTED
              and t["mixed"] >= GATE_MIXED)
    return {"tables": tables, "geo_rows": geo_rows,
            "n_rows": len(rows), "pass": passed,
            "oracle_delta": (d8 - d1) if t else float("nan")}


def write_reports(res: dict):
    T, D = res["tables"].get("TEST", {}), res["tables"].get("DEV", {})
    lines = [
        "# Stage P1 Results — Candidate Support Geometry",
        "",
        f"生成:{datetime.now().isoformat()} | runner:scripts/stageP_geometry.py",
        "| prereg §7 | manifest:stageP_split_manifest.csv(24 可用:DEV 13/TEST 11)",
        "",
        "## TEST(12 预定,实测 11,confirmatory)",
        "",
        "| 指标 | 值 | Wilson 95% CI |",
        "|---|---|---|",
    ]
    for k, lab in (("oracle1", "Oracle@1"), ("oracle2", "Oracle@2"),
                   ("oracle4", "Oracle@4"), ("oracle8", "Oracle@8"),
                   ("supported", "SUPPORTED_RATE"), ("mixed", "MIXED_RATE")):
        a, b = wilson(T[k], T["n_snapshot"])
        lines.append(f"| {lab} | {T[k]:.3f} | [{a:.3f}, {b:.3f}] |")
    lines += [
        "",
        f"**Oracle@8 − Oracle@1 = {res['oracle_delta']:.3f}**"
        f"(gate ≥{GATE_ORACLE_DELTA:.0%})",
        "",
        "## DEV(13,sanity/特征理解,不进判定)",
        "",
        "| Oracle@1 | Oracle@2 | Oracle@4 | Oracle@8 | SUPPORTED | MIXED |",
        "|---|---|---|---|---|---|",
        (f"| {D['oracle1']:.3f} | {D['oracle2']:.3f} | {D['oracle4']:.3f} "
         f"| {D['oracle8']:.3f} | {D['supported']:.3f} | {D['mixed']:.3f} |"),
        "",
        "## Per-snapshot 明细",
        "",
        "| snapshot | split | n_cand | O@1 | O@2 | O@4 | O@8 | mixed | "
        "n_rec_cand | first_rec_idx |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res["geo_rows"]:
        lines.append(
            f"| {r['snapshot_id']} | {r['split']} | {r['n_cand']} "
            f"| {r['oracle1']} | {r['oracle2']} | {r['oracle4']} "
            f"| {r['oracle8']} | {r['mixed']} | {r['n_rec_cand']} "
            f"| {r['first_rec_idx']} |")
    RES_MD.write_text("\n".join(lines))

    dec = [
        "# Stage P1 Decision — Support Geometry Gate",
        "",
        f"生成:{datetime.now().isoformat()} | gate(prereg §7/§15,TEST):"
        "Oracle@8−Oracle@1 ≥15pp ∧ SUPPORTED ≥50% ∧ MIXED ≥30%",
        "",
        f"- Oracle@8−Oracle@1 = **{res['oracle_delta']:.3f}** "
        f"(需 ≥0.15)→ {'PASS' if res['oracle_delta'] >= GATE_ORACLE_DELTA else 'FAIL'}",
        f"- SUPPORTED_SNAPSHOT_RATE = **{T['supported']:.3f}** "
        f"(需 ≥0.50)→ {'PASS' if T['supported'] >= GATE_SUPPORTED else 'FAIL'}",
        f"- MIXED_SUPPORT_RATE = **{T['mixed']:.3f}** "
        f"(需 ≥0.30)→ {'PASS' if T['mixed'] >= GATE_MIXED else 'FAIL'}",
        "",
        ("**P1 PASS** — SUPPORT_DIVERSITY 成立:同 failure state 的多采 "
         "candidate 显著扩大可恢复覆盖,可进 P2 verifier 资格。"
         if res["pass"] else
         "**P1 FAIL** — REPEATED ROLLOUT SUPPORT EXISTS, BUT WITHIN-STATE "
         "CANDIDATE DIVERSITY IS INSUFFICIENT FOR SELECTION STUDY。按 §39:"
         "Stage P STOP,禁训 verifier。"),
        "",
    ]
    DEC_MD.write_text("\n".join(dec))
    log(f"reports written: {RES_MD} / {DEC_MD}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default=None)
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    rt.apply_env_overrides()
    if not args.analyze_only:
        ox.pg.preflight(label="stageP_geometry", lock_name="stageP_geometry.lock")
        snaps = read_manifest()
        if args.only:
            snaps = [s for s in snaps if s["snapshot_id"] == args.only]
        log(f"P1 geometry: {len(snaps)} usable snapshots × {K_MAX} cand × "
            f"{prt.R_CONT} cont(workers={args.workers})")

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
        log(f"boot shared vla+sam3 on gpu{args.gpu} ...")
        shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
            ns, shared_root, NullDashboardEventSink())
        sink = Sink()
        from collections import deque
        pending = deque(snaps)
        plock = threading.Lock()

        def worker():
            while True:
                with plock:
                    if not pending:
                        return
                    s = pending.popleft()
                try:
                    log(f"== {s['snapshot_id']} {s['split']} "
                        f"t{s['task']}s{s['seed']} t0={s['t0']}")
                    process_snapshot(s, args.gpu, shared_kwargs, sink)
                except Exception as exc:
                    log(f"{s['snapshot_id']} SNAPSHOT EXC "
                        f"{type(exc).__name__}: {exc}\n"
                        f"{traceback.format_exc()[-600:]}")

        try:
            n_w = max(1, args.workers)
            threads = [threading.Thread(target=worker, daemon=True)
                       for _ in range(n_w)]
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

    res = analyze()
    T = res["tables"].get("TEST", {})
    log(f"RESULT: rows={res['n_rows']} | TEST n={T.get('n_snapshot')} "
        f"O@1={T.get('oracle1', float('nan')):.3f} "
        f"O@8={T.get('oracle8', float('nan')):.3f} "
        f"Δ={res['oracle_delta']:.3f} sup={T.get('supported', float('nan')):.3f} "
        f"mixed={T.get('mixed', float('nan')):.3f} → "
        f"{'PASS' if res['pass'] else 'FAIL'}")
    write_reports(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
