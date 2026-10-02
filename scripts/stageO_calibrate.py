#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §8(prereg)— K_ROLLOUT 校准(N 池,先于 TEST 冻结)。

校准子集(冻结规则):Stage N 24 快照按 snapshot_id 升序前 3 FG + 前 3 RPS。
内容:每快照 O1 式单技能独立采样 16 次(重放 step≤t0 最后一条 Pi0.5 族
命令,逐字重执行,每次先 restore),测 TASK_RECOVERY 契约 → p̂(16)。

冻结选择规则:K∈{4,6,8},p̂(K)=前 K 样本均值,p̂(2K)=前 2K 样本均值,
取 median|p̂(K)−p̂(2K)| ≤ 0.10 的最小 K;无一满足或全退化(六快照 p̂
全 0 或全 1)→ K_ROLLOUT=8。bootstrap 1000 次(seed=20261002)报 CI 附注。

输出:analysis/stageO_calibration.md(prereg 附录 B 的内容源,TEST 前
回填附录 B 并 commit)。

用法:
  MUJOCO_GL=osmesa python scripts/stageO_calibrate.py --gpu 0
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt

MANI = REPO / "analysis/stageN1_split_manifest.csv"
OUT_MD = REPO / "analysis/stageO_calibration.md"
LOG_ROOT = REPO / "logs/stageO_calibrate"
N_SAMPLES = 16
BOOT_SEED = 20261002


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def pick_calibration_subset() -> list[dict]:
    lines = [l for l in open(MANI, encoding="utf-8") if not l.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("".join(lines))))
    fg = sorted((r for r in rows if r["family"] == "FALSE_GRASP"),
                key=lambda r: r["snapshot_id"])[:3]
    rps = sorted((r for r in rows if r["family"] == "RELEASE_PREDICATE_STALL"),
                 key=lambda r: r["snapshot_id"])[:3]
    return fg + rps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()
    rt.apply_env_overrides()

    snaps = pick_calibration_subset()
    log("校准子集(N 池,前3 FG + 前3 RPS): "
        + " ".join(f"{s['snapshot_id']}({s['family'][:4]})" for s in snaps))

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

    results = []   # {snap, family, samples:[bool]*16, note}
    try:
        for snap in snaps:
            tries = 0
            while True:
                try:
                    outdir = LOG_ROOT / (
                        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_"
                        f"{snap['snapshot_id']}")
                    ctx = rt.boot_snapshot(snap, args.gpu, shared_kwargs,
                                           outdir)
                    break
                except rt.InfraError as exc:
                    tries += 1
                    log(f"  {snap['snapshot_id']} INFRA({tries}/3): {exc}")
                    if tries >= 3:
                        ctx = None
                        break
            if ctx is None:
                results.append({"snap": snap["snapshot_id"],
                                "family": snap["family"],
                                "samples": None, "note": "INFRA_ABORT"})
                continue
            steps = rt.load_steps(snap["episode_dir"])
            t0 = int(snap["t0"])
            cmd = rt.last_pi05_cmd(steps, t0)
            if cmd is None:
                results.append({"snap": snap["snapshot_id"],
                                "family": snap["family"], "samples": None,
                                "note": "no_pi05_cmd_in_prefix"})
                for d in ctx.get("daemons") or []:
                    d.stop()
                continue
            action, kwargs = cmd
            samples = []
            for k in range(N_SAMPLES):
                rt.restore_checked(ctx, f"{snap['snapshot_id']} s{k}")
                try:
                    ctx["toolkit"]._step(action, **kwargs)
                except Exception as exc:
                    raise rt.InfraError(
                        f"sample {k} {action}: {type(exc).__name__}: {exc}")
                # 动作 result 从 states.json 尾读(RPS 的 terminated 通道)
                sj = json.load(open(ctx["outdir"] / "states.json"))
                ares = (sj[-1] or {}).get("result") or {}
                cur = rt.measure(ctx["env"])
                ok = rt.task_recovery(snap["family"], cur, ctx["base"],
                                      ctx["target"], action_result=ares)
                samples.append(bool(ok))
            results.append({"snap": snap["snapshot_id"],
                            "family": snap["family"],
                            "samples": samples, "note": "",
                            "action": action,
                            "prompt": str(kwargs.get("prompt", ""))[:60]})
            log(f"  {snap['snapshot_id']} {snap['family'][:4]} "
                f"{action} prompt='{str(kwargs.get('prompt',''))[:40]}' "
                f"→ {sum(samples)}/{N_SAMPLES}")
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

    # ---- 冻结规则计算 ------------------------------------------------------
    import random

    valid = [r for r in results if r["samples"]]
    p16 = {r["snap"]: sum(r["samples"]) / len(r["samples"]) for r in valid}
    cands = {}
    for K in (4, 6, 8):
        devs = []
        for r in valid:
            pk = sum(r["samples"][:K]) / K
            p2k = sum(r["samples"][:2 * K]) / (2 * K)
            devs.append(abs(pk - p2k))
        devs.sort()
        # 中位数(偶数个取中间两数均值)
        n = len(devs)
        med = (devs[n // 2] if n % 2 else (devs[n // 2 - 1]
                                           + devs[n // 2]) / 2) if n else 9.9
        cands[K] = med
    degenerate = (not valid) or all(
        p in (0.0, 1.0) for p in p16.values())
    chosen = 8
    why = "默认(数据退化或无 K 满足)"
    for K in (4, 6, 8):
        if cands[K] <= 0.10 and not degenerate:
            chosen = K
            why = f"最小 K 满足 median|p̂(K)-p̂(2K)|={cands[K]:.3f}≤0.10"
            break

    # bootstrap CI 附注(每快照 p̂16 的 95% 区间)
    rng = random.Random(BOOT_SEED)
    bs = {}
    for r in valid:
        s = r["samples"]
        est = []
        for _ in range(1000):
            est.append(sum(rng.choice(s) for _ in s) / len(s))
        est.sort()
        bs[r["snap"]] = (est[24], est[974])

    w = []
    w.append("# Stage O K_ROLLOUT 校准记录(prereg §8 附录 B 内容源)\n\n")
    w.append(f"- 日期:{datetime.now().isoformat()}\n")
    w.append(f"- 校准子集(N 池,排除出 O-B,合法):"
             f"{[r['snap'] for r in results]}\n")
    w.append(f"- 每快照 O1 式独立采样 {N_SAMPLES} 次"
             f"(重放 step≤t0 最后一条 Pi0.5 族命令,逐字重执行)\n\n")
    w.append("| snapshot | family | action | prompt | k/N | p̂(16) |\n")
    w.append("|---|---|---|---|---|---|\n")
    for r in results:
        if r["samples"]:
            w.append(f"| {r['snap']} | {r['family']} | {r.get('action')} "
                     f"| {r.get('prompt','')} | {sum(r['samples'])}/"
                     f"{len(r['samples'])} | "
                     f"{sum(r['samples'])/len(r['samples']):.3f} |\n")
        else:
            w.append(f"| {r['snap']} | {r['family']} | — | — | — | "
                     f"({r['note']}) |\n")
    w.append("\n稳定性(median|p̂(K)−p̂(2K)|,冻结阈值 ≤0.10):\n")
    for K in (4, 6, 8):
        w.append(f"- K={K}: {cands[K]:.3f}\n")
    w.append(f"\n**K_ROLLOUT = {chosen}**({why};退化={degenerate})\n")
    w.append("\nbootstrap 95% CI(每快照 p̂16,seed=20261002):\n")
    for s_, (lo, hi) in bs.items():
        w.append(f"- {s_}: [{lo:.3f}, {hi:.3f}]\n")
    OUT_MD.write_text("".join(w), encoding="utf-8")
    print("".join(w))
    log(f"已写入 {OUT_MD};K_ROLLOUT={chosen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
