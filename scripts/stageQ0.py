#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage Q Q0 — 资格与审计:状态捕获(Q0-A)/ delta 审计(Q0-B)/
LIVE vs RESTORED 审计与 restore-sensitivity gate(Q0-C)。

预注册:analysis/stageQ_prereg.md §3-§5。事件源 = Stage P split manifest
DEV 行(discovery/calibration 用途,spec §9 允许),manifest 序取前 12 做
Q0-B、前 8 做 Q0-C;t0=1 结构排除。

流程(每事件一次 boot,§3 同 boot 成对):
  replay 1..t0−1 → S_pre 捕获 → 执行 t0 失败 pick(守卫:仍 FG)
  → S_post 捕获 → delta 行
  [C 集] live S_post obs 采 1 个 retry candidate 冻结 → LIVE r1 直接执行
  → RESTORED r1/r2(restore 同一 S_post 字节)→ fresh boot 重跑到
  S_post → LIVE r2 执行(同一 frozen candidate)

gate(§5):|ACQ 或 STABLE 双臂差| >10pp ∨ transition-class 配对一致率
<90% → RESTORE-SENSITIVE DYNAMICS。

产物:analysis/stageQ_state_delta_audit.csv、
analysis/stageQ_live_restore_audit.csv、analysis/stageQ0_decision.md;
原始 S_pre/S_post npy 与 candidate 冻结在 logs/stageQ0/(审计件不进 git)。

用法:
  nohup python scripts/stageQ0.py --workers 2 \
      >> /workspace/yjx/tmp/stageQ0.log 2>&1 &
  python scripts/stageQ0.py --smoke          # 单事件 A/B 流程,不写 CSV
  python scripts/stageQ0.py --analyze-only   # gate 重算 + decision 重写
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import threading
import time
import traceback
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt
import stageP_rt as prt
import stageQ_rt as qt
import ovpm_exp as ox

MANI = REPO / "analysis/stageP_split_manifest.csv"
DELTA_CSV = REPO / "analysis/stageQ_state_delta_audit.csv"
AUDIT_CSV = REPO / "analysis/stageQ_live_restore_audit.csv"
DEC_MD = REPO / "analysis/stageQ0_decision.md"
LOG_ROOT = REPO / "logs/stageQ0"

N_B = 12          # Q0-B 事件数(DEV,manifest 序)
N_C = 8           # Q0-C 事件数(B 集前缀)
MAX_INFRA_RETRY = 3

GATE_DISAG = 0.10     # §5:双臂恢复率差 >10pp
GATE_TRANS = 0.90     # §5:transition-class 配对一致率 <90%

WLOCK = threading.Lock()

DELTA_COLS = ["snapshot_id", "task", "seed", "t0", "wall_s",
              "eef_dx", "eef_dy", "eef_dz", "eef_norm", "gripper_delta",
              "target_dx", "target_dy", "target_dz", "target_dxy",
              "check_success_pre", "check_success_post",
              "obs_key_l2", "n_index", "n_changed", "n_changed_gt_1e-6",
              "max_abs", "l2", "state_sha_pre", "state_sha_post", "note"]

AUDIT_COLS = ["snapshot_id", "task", "seed", "arm", "rep", "cand_sha",
              "ee_class", "contact_class", "obj_class",
              "acq_reps", "stable_reps", "n_rep",
              "terminated_in_chunk", "final_check_success",
              "obj_disp_xy", "obj_disp_z", "pick_chunks_used", "wall_s",
              "infra_abort", "note"]


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def dev_events() -> list[dict]:
    rows = [r for r in qt.read_manifest(MANI) if r["split"] == "DEV"
            and int(r["t0"]) >= 2]
    return rows[:N_B]


def cset_ids() -> set[str]:
    return {r["snapshot_id"] for r in dev_events()[:N_C]}


def append_csv(path: Path, cols: list[str], row: dict):
    with WLOCK:
        new = not path.exists()
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)


def boot_with_retries(snap, gpu, shared, tag):
    """boot → S_pre 捕获 → 执行失败 pick → S_post 捕获(同 boot 成对)。

    返回 (ctx, S_post, cap_pre, cap_post);infra 重试整个 boot。
    """
    for attempt in range(1, MAX_INFRA_RETRY + 1):
        ctx = None
        try:
            outdir = LOG_ROOT / (
                f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
            ctx = qt.boot_to_pre(snap, gpu, shared, outdir)
            cap_pre = qt.capture_state(ctx, ctx["S"], "S_pre")
            S_post = qt.run_fail_pick(ctx, snap)     # 守卫在同 boot 内
            cap_post = qt.capture_state(ctx, S_post, "S_post")
            return ctx, S_post, cap_pre, cap_post
        except Exception as exc:
            if ctx:
                qt.stop_ctx(ctx)
            log(f"    boot INFRA({attempt}/{MAX_INFRA_RETRY}) {tag}: "
                f"{type(exc).__name__}: {str(exc)[:120]}")
    return None, None, None, None


def capture_phase(snap, ctx, S_pre, S_post, cap_pre, cap_post) -> dict:
    """Q0-A/B:捕获已在 boot 阶段完成,这里只落 npy + delta 行(纯描述)。"""
    states_dir = LOG_ROOT / "states"
    states_dir.mkdir(parents=True, exist_ok=True)
    np.save(states_dir / f"{snap['snapshot_id']}_pre.npy",
            np.asarray(S_pre))
    np.save(states_dir / f"{snap['snapshot_id']}_post.npy",
            np.asarray(S_post))
    tgt = ctx["target"]
    eef_d = [cap_post["eef"][i] - cap_pre["eef"][i] for i in range(3)]
    tgt_d = ([cap_post["pos"][tgt][i] - cap_pre["pos"][tgt][i]
              for i in range(3)] if tgt and tgt in cap_pre["pos"]
             and tgt in cap_post["pos"] else [float("nan")] * 3)
    common = set(cap_pre["obs"]) & set(cap_post["obs"])
    key_l2 = {k: float(np.linalg.norm(
        np.asarray(cap_post["obs"][k]) - np.asarray(cap_pre["obs"][k])))
        for k in sorted(common)}
    fd = qt.flatten_delta(S_pre, S_post)
    row = {"snapshot_id": snap["snapshot_id"], "task": snap["task"],
           "seed": snap["seed"], "t0": snap["t0"],
           "eef_dx": round(eef_d[0], 6), "eef_dy": round(eef_d[1], 6),
           "eef_dz": round(eef_d[2], 6),
           "eef_norm": round(float(np.linalg.norm(eef_d)), 6),
           "gripper_delta": round(cap_post["gripper"]
                                  - cap_pre["gripper"], 6),
           "target_dx": round(tgt_d[0], 6), "target_dy": round(tgt_d[1], 6),
           "target_dz": round(tgt_d[2], 6),
           "target_dxy": round(float(np.hypot(tgt_d[0], tgt_d[1])), 6),
           "check_success_pre": cap_pre["check_success"],
           "check_success_post": cap_post["check_success"],
           "obs_key_l2": json.dumps(key_l2),
           **{k: fd.get(k, "") for k in ("n_index", "n_changed",
                                         "n_changed_gt_1e-6", "max_abs",
                                         "l2")},
           "state_sha_pre": cap_pre["state_sha16"],
           "state_sha_post": cap_post["state_sha16"], "note": ""}
    return row


def exec_row(snap, arm, rep, cand_sha, res, wall) -> dict:
    tgt_disp = res["chunk_class"]["obj_disp"]
    picks = [r.get("pick", {}).get("chunks_used", "")
             for r in res["reps"]]
    final_succ = any(r.get("pick", {}).get("libero_terminated")
                     for r in res["reps"])
    return {"snapshot_id": snap["snapshot_id"], "task": snap["task"],
            "seed": snap["seed"], "arm": arm, "rep": rep,
            "cand_sha": cand_sha,
            "ee_class": res["chunk_class"]["ee_class"],
            "contact_class": res["chunk_class"]["contact_class"],
            "obj_class": res["chunk_class"]["obj_class"],
            "acq_reps": ";".join(str(int(r["acquisition"]))
                                 for r in res["reps"]),
            "stable_reps": ";".join(str(int(r["stable"]))
                                    for r in res["reps"]),
            "n_rep": len(res["reps"]),
            "terminated_in_chunk": int(res["terminated_in_chunk"]),
            "final_check_success": int(final_succ),
            "obj_disp_xy": round(float(np.hypot(tgt_disp[0], tgt_disp[1])),
                                 6) if tgt_disp else "",
            "obj_disp_z": round(tgt_disp[2], 6) if tgt_disp else "",
            "pick_chunks_used": ";".join(str(p) for p in picks),
            "wall_s": round(wall, 1), "infra_abort": "", "note": ""}


def process_event(snap, gpu, shared_kwargs, in_c: bool):
    sid = snap["snapshot_id"]
    tag = f"{sid}_t{snap['task']}s{snap['seed']}"
    t_start = time.time()
    ctx, S_post, cap_pre, cap_post = boot_with_retries(
        snap, gpu, shared_kwargs, tag)
    if ctx is None:
        append_csv(DELTA_CSV, DELTA_COLS,
                   {"snapshot_id": sid, "task": snap["task"],
                    "seed": snap["seed"], "t0": snap["t0"],
                    "note": "INFRA_ABORT_3attempts"})
        if in_c:
            for rep in (1, 2):
                append_csv(AUDIT_CSV, AUDIT_COLS,
                           {"snapshot_id": sid, "arm": "LIVE", "rep": rep,
                            "infra_abort": "boot_3attempts"})
                append_csv(AUDIT_CSV, AUDIT_COLS,
                           {"snapshot_id": sid, "arm": "RESTORED",
                            "rep": rep, "infra_abort": "boot_3attempts"})
        return
    try:
        S_pre = ctx["S"]
        drow = capture_phase(snap, ctx, S_pre, S_post, cap_pre, cap_post)
        drow["wall_s"] = round(time.time() - t_start, 1)
        append_csv(DELTA_CSV, DELTA_COLS, drow)
        log(f"  {sid} delta: eef‖Δ‖={drow['eef_norm']} "
            f"tgt_dxy={drow['target_dxy']} obj_dz={drow['target_dz']} "
            f"l2={drow['l2']:.3f}")
        if not in_c:
            return
        # ---- Q0-C ----
        prompt = prt.pre_prompt_of(snap)
        cand = prt.sample_candidate(ctx["prims"], prompt)   # live S_post obs
        csha = prt.chunk_sha(cand)
        (LOG_ROOT / "retry_candidates.jsonl").open("a").write(
            json.dumps({"snapshot_id": sid, "cand_sha": csha,
                        "prompt": prompt,
                        "actions": [[float(v) for v in r] for r in cand]})
            + "\n")
        target = ctx["target"]
        # LIVE r1:live 态直接执行(不 restore)
        t1 = time.time()
        cps: list[dict] = []
        res = qt.exec_from_current(ctx, target, prompt, cand, cps)
        append_csv(AUDIT_CSV, AUDIT_COLS,
                   exec_row(snap, "LIVE", 1, csha, res, time.time() - t1))
        log(f"  {sid} LIVE r1 acq={res['n_acq']}/{len(res['reps'])} "
            f"stable={res['n_stable']}/{len(res['reps'])}")
        # RESTORED r1/r2:同一 S_post 字节
        for rep in (1, 2):
            t1 = time.time()
            res = qt.exec_from_state(ctx, S_post, target, prompt, cand,
                                     cps, f"{sid} restored r{rep}")
            append_csv(AUDIT_CSV, AUDIT_COLS,
                       exec_row(snap, "RESTORED", rep, csha, res,
                                time.time() - t1))
            log(f"  {sid} RESTORED r{rep} acq={res['n_acq']}/"
                f"{len(res['reps'])} stable={res['n_stable']}/"
                f"{len(res['reps'])}")
    finally:
        qt.stop_ctx(ctx)

    # LIVE r2:fresh boot 重跑到 S_post(observably matched,非逐位)
    ctx2, _S_post2, _cp2, _cp2b = boot_with_retries(
        snap, gpu, shared_kwargs, tag + "_b2")
    if ctx2 is None:
        append_csv(AUDIT_CSV, AUDIT_COLS,
                   {"snapshot_id": sid, "arm": "LIVE", "rep": 2,
                    "infra_abort": "boot2_3attempts"})
        return
    try:
        prompt = prt.pre_prompt_of(snap)
        target = ctx2["target"]
        t1 = time.time()
        res = qt.exec_from_current(ctx2, target, prompt, cand, [])
        append_csv(AUDIT_CSV, AUDIT_COLS,
                   exec_row(snap, "LIVE", 2, csha, res, time.time() - t1))
        log(f"  {sid} LIVE r2 acq={res['n_acq']}/{len(res['reps'])} "
            f"stable={res['n_stable']}/{len(res['reps'])}")
    finally:
        qt.stop_ctx(ctx2)


# ---- 分析与 gate -------------------------------------------------------------
def dedup_delta() -> int:
    """断点重跑可能产生重复 delta 行:每 snapshot_id 取最后一行重写。"""
    if not DELTA_CSV.exists():
        return 0
    by_sid: dict[str, dict] = {}
    for r in csv.DictReader(open(DELTA_CSV)):
        by_sid[r["snapshot_id"]] = r
    rows = list(by_sid.values())
    with open(DELTA_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DELTA_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def analyze() -> dict:
    # 去重:断点重跑的事件取每 (snapshot, arm, rep) 最后一行
    by_key: dict[tuple, dict] = {}
    for r in csv.DictReader(open(AUDIT_CSV)):
        if not r.get("infra_abort"):
            by_key[(r["snapshot_id"], r["arm"], r["rep"])] = r
    rows = list(by_key.values())

    def rep_rate(arm, col):
        vals = []
        for r in rows:
            if r["arm"] != arm:
                continue
            reps = r.get(col, "").split(";")
            vals.extend(1 if v == "1" else 0 for v in reps if v != "")
        return (sum(vals) / len(vals) if vals else float("nan")), len(vals)

    acq_l, n_l = rep_rate("LIVE", "acq_reps")
    acq_r, n_r = rep_rate("RESTORED", "acq_reps")
    st_l, _ = rep_rate("LIVE", "stable_reps")
    st_r, _ = rep_rate("RESTORED", "stable_reps")

    # transition-class 配对一致率:同事件 (LIVE rep, RESTORED rep) 同 rep 号
    def cls(r):
        return (r["ee_class"], r["contact_class"], r["obj_class"])
    live = {(r["snapshot_id"], r["rep"]): r for r in rows
            if r["arm"] == "LIVE"}
    rest = {(r["snapshot_id"], r["rep"]): r for r in rows
            if r["arm"] == "RESTORED"}
    pairs = [(k, live[k], rest[k]) for k in live.keys() & rest.keys()]
    agree = sum(1 for _, a, b in pairs if cls(a) == cls(b))

    return {"acq_live": acq_l, "acq_restored": acq_r,
            "st_live": st_l, "st_restored": st_r,
            "n_live": n_l, "n_restored": n_r,
            "pairs": len(pairs), "agree": agree,
            "agree_rate": (agree / len(pairs)) if pairs else float("nan"),
            "acq_disag": abs(acq_l - acq_r),
            "st_disag": abs(st_l - st_r)}


def write_decision(a: dict):
    sensitive = (a["acq_disag"] > GATE_DISAG or a["st_disag"] > GATE_DISAG
                 or a["agree_rate"] < GATE_TRANS)
    lines = [
        "# Stage Q0 Decision — Restore-Sensitivity Gate",
        "",
        f"生成:{datetime.datetime.now().isoformat()} | prereg §5 | "
        "事件源:Stage P DEV(manifest 序前 8,Q0-C)",
        "",
        "## LIVE vs RESTORED(pooled replicate)",
        "",
        "| 指标 | LIVE | RESTORED | 双臂差 | 门 |",
        "|---|---|---|---|---|",
        (f"| ACQUISITION | {a['acq_live']:.3f} | {a['acq_restored']:.3f} "
         f"| {a['acq_disag']:.3f} | ≤{GATE_DISAG:.2f} |"),
        (f"| STABLE | {a['st_live']:.3f} | {a['st_restored']:.3f} "
         f"| {a['st_disag']:.3f} | ≤{GATE_DISAG:.2f} |"),
        "",
        (f"transition-class 配对一致率 = **{a['agree_rate']:.3f}**"
         f"({a['agree']}/{a['pairs']} 对;门 ≥{GATE_TRANS:.2f})"),
        "",
        ("**RESTORE-SENSITIVE DYNAMICS** — Q1 所有 restored-state 因果拆分"
         "只能标 APPROXIMATE / INCONCLUSIVE,禁称精确 physics counterfactual。"
         if sensitive else
         "**GATE PASS(差异较小)** — 允许进入 Q1;Q1 仍只能解释 "
         "observable state intervention,不能排除全部 hidden dynamics。"),
        "",
    ]
    DEC_MD.write_text("\n".join(lines), encoding="utf-8")
    return sensitive


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--smoke", action="store_true",
                    help="单事件 A/B 流程(打印 delta,不写 CSV)")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    rt.apply_env_overrides()
    if args.analyze_only:
        a = analyze()
        log(f"GATE: acq {a['acq_live']:.3f}/{a['acq_restored']:.3f} "
            f"(Δ{a['acq_disag']:.3f}) stable {a['st_live']:.3f}/"
            f"{a['st_restored']:.3f} (Δ{a['st_disag']:.3f}) "
            f"trans-agree {a['agree']}/{a['pairs']}")
        write_decision(a)
        return 0

    ox.pg.preflight(label="stageQ0", lock_name="stageQ0.lock")
    events = dev_events()
    cids = cset_ids()
    log(f"Q0:B 集 {len(events)} DEV 事件(其中 C 集 {len(cids)});"
        f"workers={args.workers} smoke={args.smoke}")
    if args.smoke:
        events, cids = events[:1], set()

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

    from collections import deque
    pending = deque(events)
    plock = threading.Lock()
    done: set[str] = set()
    if not args.smoke:
        for r in (csv.DictReader(open(DELTA_CSV))
                  if DELTA_CSV.exists() else []):
            if r.get("note") != "INFRA_ABORT_3attempts":
                done.add(r["snapshot_id"])
        # C 集事件还须已有 LIVE/RESTORED audit 行才算完成(防冒烟/中断
        # 只写了 delta 就被 resume 跳过)
        audited = set()
        if AUDIT_CSV.exists():
            for r in csv.DictReader(open(AUDIT_CSV)):
                if not r.get("infra_abort"):
                    audited.add(r["snapshot_id"])
        done = {s for s in done if s not in cids or s in audited}
        pending = deque(e for e in events
                        if e["snapshot_id"] not in done)
        log(f"resume:{len(done)} 已完成,{len(pending)} 待跑")

    def worker():
        while True:
            with plock:
                if not pending:
                    return
                s = pending.popleft()
            sid = s["snapshot_id"]
            try:
                log(f"== {sid} t{s['task']}s{s['seed']} t0={s['t0']}")
                process_event(s, args.gpu, shared_kwargs,
                              sid in cids and not args.smoke)
            except Exception as exc:
                log(f"{sid} EXC {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()[-600:]}")

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

    if not args.smoke:
        dedup_delta()
        a = analyze()
        log(f"GATE: acq {a['acq_live']:.3f}/{a['acq_restored']:.3f} "
            f"(Δ{a['acq_disag']:.3f}) stable {a['st_live']:.3f}/"
            f"{a['st_restored']:.3f} (Δ{a['st_disag']:.3f}) "
            f"trans-agree {a['agree']}/{a['pairs']} → "
            f"{'SENSITIVE' if (a['acq_disag'] > GATE_DISAG or a['st_disag'] > GATE_DISAG or a['agree_rate'] < GATE_TRANS) else 'PASS'}")
        write_decision(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
