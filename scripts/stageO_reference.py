#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §8 — Full Planner reference traces(K_REF 冻结,取第一个成功)。

规范:analysis/stageO_prereg.md §4(K_REF=3,attempt 顺序冻结,首个满足
TASK_RECOVERY ∨ check_success 的 trace 即 oracle;全败 REFERENCE_UNAVAILABLE)。

对 manifest 每个 O-B 快照:boot(重放 1..t0)→ 逐 attempt:
restore → planner 续跑(§8.1 模板,预算 §7)→ 判成功 → 成功即停。
reference trace 落 stageO_reference_traces.jsonl(成功与否都记录 attempt,
成功 attempt 附 oracle 序列供 O2/O3 抽取)。

infra:boot/restore 异常 → 快照级重试 ≤3(整个快照重跑);
单 attempt 的 agent_error(API 级)不重跑整个 attempt(它是策略性失败还是
infra 由 §34 规则判:HTTP/timeout 字样才计 infra,记 INFRA_ABORT 行)。

用法:
  MUJOCO_GL=osmesa python scripts/stageO_reference.py --gpu 0 \
      [--only osnap_00] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import stageO_rt as rt

MANI = REPO / "analysis/stageO_split_manifest.csv"
OUT = REPO / "analysis/stageO_reference_traces.jsonl"
LOG_ROOT = REPO / "logs/stageO_reference"
K_REF = 3            # prereg §4
MAX_INFRA_RETRY = 3


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


def read_manifest() -> list[dict]:
    lines = [l for l in open(MANI, encoding="utf-8") if not l.startswith("#")]
    import csv, io
    return list(csv.DictReader(io.StringIO("".join(lines))))


def is_api_infra(agent_error: str | None) -> bool:
    """§34:API timeout / HTTP 5xx / 连接级错误才算 infra。"""
    if not agent_error:
        return False
    low = agent_error.lower()
    return any(k in low for k in (
        "timeout", "timed out", "502", "503", "504", "connection",
        "remoteprotocolerror", "httpstatuserror"))


def reference_success(rec: dict) -> bool:
    return bool(rec["contract_met"] or rec["check_success"])


def attempt_records(snap, gpu, shared_kwargs) -> list[dict]:
    """>=K_REF attempts;每次 attempt 独立 boot(独立 outdir)。

    独立 boot 的原因(instrumentation,prereg §12 纪律):planner 可读
    outdir/states.json,共用 outdir 会让 attempt k 看到 attempt<k 的步
    (额外信息,违反 §32-33 干净比较;且 O4 必须与 reference 同构)。
    infra 抛 rt.InfraError。
    """
    tag = f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}T{snap['t0']}"
    attempts = []
    for k in range(1, K_REF + 1):
        outdir = LOG_ROOT / (
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_ref{k}_{tag}")
        # dev-O5:不再断言跨 boot hash 相等(prefix 含 Pi0.5 重采样,结构性
        # 不可达);boot 内事件复现/契约守卫由 boot_snapshot(validate_event)承担
        ctx = rt.boot_snapshot(snap, gpu, shared_kwargs, outdir,
                               note=f"ref{k} {tag}")
        try:
            rec = rt.run_planner_continuation(ctx, snap, snap["family"])
            rec.update({"snapshot_id": snap["snapshot_id"],
                        "family": snap["family"], "attempt_idx": k,
                        "task": snap["task"], "seed": snap["seed"],
                        "t0": snap["t0"], "episode_dir": snap["episode_dir"]})
            attempts.append(rec)
            log(f"  ref_{k}: met={rec['contract_met']} "
                f"succ={rec['check_success']} prims={rec['n_prims']} "
                f"pi05={rec['n_pi05']} wall={rec['wall_s']}s "
                f"err={str(rec['agent_error'])[:80]}")
        finally:
            # 收尾:停本次 attempt 的 env daemon(共享 vla/sam3 不动)
            for d in ctx.get("daemons") or []:
                try:
                    d.stop()
                except Exception:
                    pass
        if reference_success(rec):
            break
    return attempts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    rt.apply_env_overrides()

    snaps = read_manifest()
    if args.only:
        snaps = [s for s in snaps if s["snapshot_id"] == args.only]
    if args.limit:
        snaps = snaps[: args.limit]
    assert snaps, "空快照集"

    # 断点续跑:已有成功 attempt 或已写满 K_REF 失败 attempt 的快照跳过
    done: set[str] = set()
    counts: dict[str, int] = {}
    if OUT.exists():
        for line in open(OUT, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            counts[d["snapshot_id"]] = counts.get(d["snapshot_id"], 0) + 1
            if reference_success(d) or counts[d["snapshot_id"]] >= K_REF:
                done.add(d["snapshot_id"])
    todo = [s for s in snaps if s["snapshot_id"] not in done]
    # dev-O5:init 即成功的确定性退化快照跳过(分析层单列,不产 reference)
    degenerate = rt.init_degenerate_ids() & {s["snapshot_id"] for s in snaps}
    if degenerate:
        log(f"ALREADY_RECOVERED_AT_INIT 跳过:{sorted(degenerate)}")
        todo = [s for s in todo if s["snapshot_id"] not in degenerate]
    log(f"manifest {len(snaps)} | todo {len(todo)}"
        + (f"(resume skip {sorted(done)})" if done else ""))

    # 共享 vla + sam3(N1 模式)
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
    log(f"boot shared vla+sam3 on gpu{args.gpu} ...")
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())
    log(f"shared runtime ready: {sorted(shared_kwargs)}")

    out_f = open(OUT, "a", encoding="utf-8")
    n_ok = n_unavail = 0
    try:
        for snap in todo:
            log(f"{snap['snapshot_id']} {snap['family']} "
                f"t{snap['task']}s{snap['seed']} T{snap['t0']}")
            tries = 0
            while True:
                try:
                    attempts = attempt_records(snap, args.gpu, shared_kwargs)
                    break
                except rt.InfraError as exc:
                    tries += 1
                    log(f"  INFRA({tries}/{MAX_INFRA_RETRY}): {exc}")
                    if tries >= MAX_INFRA_RETRY:
                        attempts = None
                        break
            if attempts is None:
                out_f.write(json.dumps({
                    "snapshot_id": snap["snapshot_id"],
                    "family": snap["family"], "attempt_idx": -1,
                    "infra_abort": f"{MAX_INFRA_RETRY}_attempts",
                    "task": snap["task"], "seed": snap["seed"],
                    "t0": snap["t0"]}, default=str) + "\n")
                out_f.flush()
                continue
            for rec in attempts:
                if is_api_infra(rec.get("agent_error")) and not reference_success(rec):
                    rec["infra_attempt"] = True
                out_f.write(json.dumps(rec, default=str) + "\n")
            out_f.flush()
            best = attempts[-1]
            if reference_success(best):
                n_ok += 1
                log(f"  => REFERENCE OK(attempt {best['attempt_idx']})")
            else:
                n_unavail += 1
                log("  => REFERENCE_UNAVAILABLE")
    finally:
        out_f.close()
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    log(f"reference 完成:OK={n_ok} UNAVAILABLE={n_unavail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
