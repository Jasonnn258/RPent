#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage P §5 — P0 Candidate Replay Qualification(唯一 confirmatory runner)。

预注册:analysis/stageP_prereg.md §5;接口事实:stageP_candidate_interface.md。
数据:Stage O 8 个 FG 快照(§33 许可:接口理解用途,不作 P1 confirmatory)。

冻结执行序(每快照):
  boot(dev-O5 守卫)→ restore → 采 2 个 candidate(生成序即冻结序,
  执行前落盘 analysis/stageP_candidates_p0.jsonl)→ 每 candidate 从同一
  S restore→执行 chunk ×3(纯 chunk,不含 continuation)→ chunk 级分类。

gate(≥95% 双指标):transition-class(三维向量)pairwise agreement 与
success/failure flags pairwise agreement;分母 = 全部 (candidate×replay)
互比对;agreement = 与该 candidate 众数类一致(R=3 时与"对内互相同"等价)。
另报 per-candidate 最差值、数值指纹 max|Δ|(预期逐位 0.0)。

产物:analysis/stageP_replay_qualification.csv + stageP0_decision.md。

用法:
  python scripts/stageP_replay.py --gpu 0
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import stageO_rt as rt           # boot/restore/measure/守卫(零改动复用)
import stageP_rt as prt          # candidate 采样/执行/分类(prereg §5)
import ovpm_exp as ox            # 只用 pg.preflight

MANI = REPO / "analysis/stageO_split_manifest.csv"
CAND_JL = REPO / "analysis/stageP_candidates_p0.jsonl"
QUAL_CSV = REPO / "analysis/stageP_replay_qualification.csv"
DECISION_MD = REPO / "analysis/stageP0_decision.md"
LOG_ROOT = REPO / "logs/stageP_replay"

MAX_INFRA_RETRY = 3
N_CAND = 2                       # §5:每快照前 2 个 candidate
N_REPLAY = 3                     # §5:每 candidate 3 次 replay
GATE = 0.95                      # §5:双指标 ≥95%

QUAL_COLS = [
    "snapshot_id", "family", "task", "seed", "t0", "cand_idx", "cand_sha",
    "replay_idx", "ee_class", "contact_class", "obj_class",
    "flag_target_displaced", "flag_gripper_closed", "flag_ee_near_target",
    "end_eef_x", "end_eef_y", "end_eef_z", "odx", "ody", "odz",
    "ee_dz", "ee_dxy", "odz_raw", "odxy_raw", "terminated_in_chunk",
    "check_success_post", "infra_abort", "note",
]

WRITE_LOCK = threading.Lock()


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def read_fg_manifest() -> list[dict]:
    """Stage O manifest → 8 个 FG 快照(注释头跳过;零结果筛选)。"""
    lines = [l for l in MANI.read_text().splitlines()
             if not l.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    return [r for r in rows if r["family"] == "FALSE_GRASP"]


def load_frozen_candidates() -> dict[str, list[dict]]:
    """已冻结 candidate(断点续跑只复用,绝不重采——冻结纪律)。"""
    frozen: dict[str, list[dict]] = {}
    if CAND_JL.exists():
        for line in CAND_JL.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            frozen.setdefault(rec["snapshot_id"], []).append(rec)
    return frozen


def append_jsonl(path: Path, rec: dict):
    with WRITE_LOCK:
        with open(path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()


class Sink:
    """CSV 追加落盘(幂等重跑时人工清空;正常一次跑齐)。"""

    def __init__(self):
        if not QUAL_CSV.exists():
            with open(QUAL_CSV, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=QUAL_COLS).writeheader()

    def row(self, r: dict):
        with WRITE_LOCK:
            with open(QUAL_CSV, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=QUAL_COLS,
                               extrasaction="ignore").writerow(r)


def stop_ctx(ctx):
    for d in (ctx.get("daemons") or []):
        try:
            d.stop()
        except Exception:
            pass


def boot(snap: dict, gpu: int, shared_kwargs: dict, tag: str):
    """boot(dev-O5 守卫在 rt.boot_snapshot 内);≤3 次重试,败则 None。"""
    for attempt in range(1, MAX_INFRA_RETRY + 1):
        try:
            outdir = LOG_ROOT / (
                f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
            return rt.boot_snapshot(snap, gpu, shared_kwargs, outdir, note=tag)
        except Exception as exc:
            log(f"    boot INFRA({attempt}/{MAX_INFRA_RETRY}) {tag}: "
                f"{type(exc).__name__}: {str(exc)[:120]}")
    return None


def freeze_candidates(ctx, snap, prompt, frozen_n: int) -> list[dict]:
    """采样并立即冻结(执行前落盘)。frozen_n>0(断点部分冻结)→ 不补采:
    补采会改变 candidate 生成序,违反冻结纪律;如实以现有数继续。"""
    if frozen_n:
        log(f"    reuse {frozen_n} frozen candidates(不重采/不补采)")
        return []
    made = []
    for i in range(N_CAND):
        try:
            actions = prt.sample_candidate(ctx["prims"], prompt)
        except Exception as exc:
            log(f"    candidate generation INFRA cand{i+1}: "
                f"{type(exc).__name__}: {str(exc)[:120]}")
            break
        rec = {"snapshot_id": snap["snapshot_id"], "cand_idx": i + 1,
               "frozen_ts": datetime.now().isoformat(),
               "prompt": prompt, "shape": [5, 7],
               "cand_sha": prt.chunk_sha(actions),
               "actions": [[float(v) for v in row] for row in actions]}
        append_jsonl(CAND_JL, rec)
        made.append(rec)
        log(f"    frozen cand{i+1}/{N_CAND} sha={rec['cand_sha']}")
    return made


def replay_one(ctx, snap, target, actions, replay_idx: int) -> tuple[dict, str]:
    """一次 replay:restore → pre 测点 → chunk 执行 → post 测点 → 分类行。"""
    rt.restore_checked(ctx, f"{snap['snapshot_id']} replay{replay_idx}")
    pre = prt.checkpoint(ctx, target)
    term = prt.execute_chunk(ctx["prims"], actions)
    post = prt.checkpoint(ctx, target)
    cls = prt.classify_chunk(pre, post)
    row = dict.fromkeys(QUAL_COLS, "")
    row.update({
        "snapshot_id": snap["snapshot_id"], "family": snap["family"],
        "task": snap["task"], "seed": snap["seed"], "t0": snap["t0"],
        "replay_idx": replay_idx, "ee_class": cls["ee_class"],
        "contact_class": cls["contact_class"], "obj_class": cls["obj_class"],
        "flag_target_displaced": int(cls["flag_target_displaced"]),
        "flag_gripper_closed": int(cls["flag_gripper_closed"]),
        "flag_ee_near_target": int(cls["flag_ee_near_target"]),
        "terminated_in_chunk": int(term),
        "check_success_post": int(post["check_success"]),
        "ee_dz": cls["ee_dz"], "ee_dxy": cls["ee_dxy"],
        "odz_raw": cls["odz"], "odxy_raw": cls["odxy"],
    })
    if post["eef"]:
        row["end_eef_x"], row["end_eef_y"], row["end_eef_z"] = \
            (float(c) for c in post["eef"])   # 指纹列:全精度不 round
    if cls["obj_disp"]:
        row["odx"], row["ody"], row["odz"] = \
            (float(c) for c in cls["obj_disp"])
    return row, cls["ee_class"]


def process_snapshot(snap: dict, gpu: int, shared_kwargs: dict,
                     frozen: dict[str, list[dict]], sink: Sink):
    sid = snap["snapshot_id"]
    steps = rt.load_steps(snap["episode_dir"])
    cmd = rt.last_pi05_cmd(steps, int(snap["t0"]))
    if cmd is None:
        log(f"  {sid}: prefix 无 pi05 命令 → INFRA 行")
        sink.row({"snapshot_id": sid, "family": snap["family"],
                  "infra_abort": "no_pi05_cmd_in_prefix"})
        return
    prompt = (cmd[1] or {}).get("prompt")

    ctx = boot(snap, gpu, shared_kwargs,
               f"{sid}_t{snap['task']}s{snap['seed']}_p0")
    if ctx is None:
        sink.row({"snapshot_id": sid, "family": snap["family"],
                  "infra_abort": "boot_3attempts"})
        return
    try:
        # ① 执行前采样 + 冻结(断点续跑只复用,不补采不重采)
        pre_frozen = frozen.get(sid, [])
        made = freeze_candidates(ctx, snap, prompt, len(pre_frozen))
        cands = pre_frozen + made
        for rec in cands:
            actions = np.asarray(rec["actions"], dtype=np.float32)
            got = []
            for replay_idx in range(1, N_REPLAY + 1):
                for attempt in range(1, MAX_INFRA_RETRY + 1):
                    try:
                        row, _ = replay_one(ctx, snap, ctx["target"],
                                            actions, replay_idx)
                        row["cand_idx"], row["cand_sha"] = \
                            rec["cand_idx"], rec["cand_sha"]
                        sink.row(row)
                        got.append(row)
                        break
                    except Exception as exc:
                        log(f"    replay INFRA({attempt}/{MAX_INFRA_RETRY}) "
                            f"cand{rec['cand_idx']} r{replay_idx}: "
                            f"{type(exc).__name__}: {str(exc)[:120]}")
                else:
                    sink.row({"snapshot_id": sid, "family": snap["family"],
                              "cand_idx": rec["cand_idx"],
                              "cand_sha": rec["cand_sha"],
                              "replay_idx": replay_idx,
                              "infra_abort": f"{MAX_INFRA_RETRY}_attempts"})
            log(f"    cand{rec['cand_idx']} sha={rec['cand_sha']}: "
                f"{len(got)}/{N_REPLAY} valid replays")
    finally:
        stop_ctx(ctx)


# ---- 分析:agreement + 数值指纹 + gate ---------------------------------------
def analyze():
    rows = list(csv.DictReader(open(QUAL_CSV)))
    valid = [r for r in rows if not r.get("infra_abort")]
    infra = [r for r in rows if r.get("infra_abort")]
    by_cand: dict[tuple, list[dict]] = {}
    for r in valid:
        by_cand.setdefault((r["snapshot_id"], r["cand_idx"]), []).append(r)

    def tvec(r):
        return (r["ee_class"], r["contact_class"], r["obj_class"])

    def fvec(r):
        return (r["flag_target_displaced"], r["flag_gripper_closed"],
                r["flag_ee_near_target"])

    def pairs_of(rs, key):
        """返回 (一致对数, 总对数)。R=3 下与"与众数一致"等价:一致的对待
        必然等于多数类;全不同则 0 对一致、众数任取也无法产生一致对。"""
        n, tot, agree = len(rs), 0, 0
        for i in range(n):
            for j in range(i + 1, n):
                tot += 1
                agree += int(key(rs[i]) == key(rs[j]))
        return agree, tot

    t_agree = t_tot = f_agree = f_tot = 0
    per_cand, fingerprint_bad, fingerprint_incomplete = [], [], []
    for (sid, ci), rs in sorted(by_cand.items()):
        a3, n3 = pairs_of(rs, tvec)
        a5, n5 = pairs_of(rs, fvec)
        t_agree, t_tot = t_agree + a3, t_tot + n3
        f_agree, f_tot = f_agree + a5, f_tot + n5
        # 数值指纹:end EE pose + 目标位移向量 跨 replay max|Δ|
        vecs = []
        for r in rs:
            v = [r["end_eef_x"], r["end_eef_y"], r["end_eef_z"],
                 r["odx"], r["ody"], r["odz"]]
            if any(x == "" or x is None for x in v):
                continue        # target 不可见等 → 指纹缺格,跳过并记录
            vecs.append([float(x) for x in v])
        if len(vecs) == len(rs) and vecs:
            arr = np.asarray(vecs)
            maxdiff = float(np.abs(arr - arr[0]).max())
            if maxdiff != 0.0:
                fingerprint_bad.append((sid, ci, maxdiff))
        else:
            fingerprint_incomplete.append((sid, ci))
            maxdiff = -1.0      # 缺格:另报,不进 gate(非不稳定证据)
        per_cand.append({
            "snapshot_id": sid, "cand_idx": ci, "n_valid": len(rs),
            "transition_agree": f"{a3}/{n3}" if n3 else "-",
            "flags_agree": f"{a5}/{n5}" if n5 else "-",
            "worst_transition": (a3 / n3) if n3 else None,
            "worst_flags": (a5 / n5) if n5 else None,
            "fingerprint_max_abs_diff": maxdiff,
        })
    t_rate = t_agree / t_tot if t_tot else 0.0
    f_rate = f_agree / f_tot if f_tot else 0.0
    return {
        "n_snapshot": len({r["snapshot_id"] for r in valid}),
        "n_cand": len(by_cand), "n_replay_rows": len(valid),
        "n_infra": len(infra),
        "transition_agreement": t_rate, "flags_agreement": f_rate,
        "t_pairs": f"{t_agree}/{t_tot}", "f_pairs": f"{f_agree}/{f_tot}",
        "per_cand": per_cand, "fingerprint_bad": fingerprint_bad,
        "fingerprint_incomplete": fingerprint_incomplete,
        "pass": (t_rate >= GATE and f_rate >= GATE
                 and len(by_cand) >= 12 and not fingerprint_bad),
    }


def write_decision(res: dict):
    lines = [
        "# Stage P0 Decision — Candidate Replay Qualification",
        "",
        f"生成:{datetime.now().isoformat()} | runner:scripts/stageP_replay.py",
        "| prereg:analysis/stageP_prereg.md §5 | 数据:Stage O 8 FG 快照"
        "(§33 discovery 许可)",
        "",
        "## P0 四条件(§5)",
        "",
        "1. **identity 明确**:candidate := 首个 [5,7] action chunk("
        "stageP_candidate_interface.md §3,实现事实 file:line 全引)",
        "2. **可执行前冻结**:16 candidate 全部执行前生成并落盘"
        "`analysis/stageP_candidates_p0.jsonl`(frozen_ts 先于任何 chunk 执行)",
        "3. **replay PASS**:(下表)",
        "4. **candidate+固定 continuation 有可定义 outcome**:§4 契约已冻结"
        "(测量点/标签优先级);Stage O O1 同快照全 attempt 结果(discovery)"
        "佐证 outcome 分布非退化",
        "",
        "## Replay 结果",
        "",
        f"- candidate 数:{res['n_cand']}(要求 ≥12)",
        f"- 有效 replay 行:{res['n_replay_rows']} | infra 行:{res['n_infra']}",
        f"- transition-class agreement:**{res['transition_agreement']:.4f}**"
        f"({res['t_pairs']})(gate ≥{GATE:.0%})",
        f"- success/failure flags agreement:**{res['flags_agreement']:.4f}**"
        f"({res['f_pairs']})(gate ≥{GATE:.0%})",
        f"- 数值指纹(end EE pose + 目标位移 max|Δ| 跨 replay):"
        + ("全部逐位 0.0 ✓" if not res["fingerprint_bad"]
           else f"**超标:{res['fingerprint_bad']}**")
        + (f"(另:缺格 {len(res['fingerprint_incomplete'])} 见上表 -1)"
           if res.get("fingerprint_incomplete") else ""),
        f"- per-candidate 最差 transition agreement:"
        f"{min((c['worst_transition'] for c in res['per_cand'] if c['worst_transition'] is not None), default=float('nan')):.3f}"
        f" | 最差 flags agreement:"
        f"{min((c['worst_flags'] for c in res['per_cand'] if c['worst_flags'] is not None), default=float('nan')):.3f}",
        "",
        "## Per-candidate(最差 agreement 与指纹)",
        "",
        "| snapshot | cand | n_valid | transition | flags | fingerprint |",
        "|---|---|---|---|---|---|",
    ]
    for c in res["per_cand"]:
        wt = "-" if c["worst_transition"] is None else f"{c['worst_transition']:.3f}"
        wf = "-" if c["worst_flags"] is None else f"{c['worst_flags']:.3f}"
        lines.append(
            f"| {c['snapshot_id']} | {c['cand_idx']} | {c['n_valid']} "
            f"| {c['transition_agree']}({wt}) | {c['flags_agree']}({wf}) "
            f"| {c['fingerprint_max_abs_diff']:.2e} |")
    lines += [
        "",
        "## 判定",
        "",
        ("**P0 PASS** —— transition 与 flags 双指标 ≥95%,指纹逐位相等,"
         "candidate ≥12。CANDIDATE_INTERFACE:QUALIFIED,可进 P1。"
         if res["pass"] else
         "**P0 FAIL** —— `CANDIDATE_OBJECT_NOT_QUALIFIED`。按 §39:Stage P "
         "STOP,不得用 verifier 预测自身 label 不稳定的对象;Stage O "
         "POLICY SUPPORT 结论不受影响。"),
        "",
    ]
    DECISION_MD.write_text("\n".join(lines))
    log(f"decision written: {DECISION_MD}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--only", default=None, help="只跑指定 snapshot_id(调试)")
    ap.add_argument("--analyze-only", action="store_true",
                    help="只重算 gate(不跑机器人)")
    args = ap.parse_args()

    rt.apply_env_overrides()
    if not args.analyze_only:
        ox.pg.preflight(label="stageP_replay", lock_name="stageP_replay.lock")

    frozen = load_frozen_candidates()
    if not args.analyze_only:
        snaps = read_fg_manifest()
        if args.only:
            snaps = [s for s in snaps if s["snapshot_id"] == args.only]
        log(f"P0 replay: {len(snaps)} FG snapshots × {N_CAND} cand × "
            f"{N_REPLAY} replays(frozen reuse: "
            f"{sum(len(v) for v in frozen.values())})")

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
        try:
            for snap in snaps:
                try:
                    log(f"== {snap['snapshot_id']} "
                        f"t{snap['task']}s{snap['seed']} t0={snap['t0']}")
                    process_snapshot(snap, args.gpu, shared_kwargs,
                                     frozen, sink)
                except Exception as exc:
                    log(f"{snap['snapshot_id']} SNAPSHOT EXC "
                        f"{type(exc).__name__}: {exc}\n"
                        f"{traceback.format_exc()[-600:]}")
        finally:
            for d in shared_daemons:
                try:
                    d.stop()
                except Exception:
                    pass

    res = analyze()
    log(f"RESULT: cands={res['n_cand']} rows={res['n_replay_rows']} "
        f"infra={res['n_infra']} transition={res['transition_agreement']:.4f} "
        f"flags={res['flags_agreement']:.4f} fingerprint_bad="
        f"{len(res['fingerprint_bad'])} → "
        f"{'PASS' if res['pass'] else 'FAIL'}")
    write_decision(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
