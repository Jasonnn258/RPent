#!/usr/bin/env python
"""Stage K0 — 分布真值标定 runner(预注册:analysis/stageK0_prereg.md)。

对 analysis/stageK0_snapshot_selection.json 冻结的 6 个 calibration snapshot
× 每快照全部合法边 × K_max=16 次 rollout:restore exact snapshot → 执行边链
(stagek_graph_executor)→ §5 结局分类。产物:analysis/stageK0_rollouts.jsonl。

- 共享一个 vla_server + sam3_server;每快照独立 env_server(同 task/seed,
  horizon=200000 只抬 truncation 天花板,预注册 §1);
- 每次 rollout 前_restore + set_obs + 读回校验(必须逐位 ==0);
- infra 异常(restore 读回非 0 / 原语外异常)按 ≤3 次重试同 k 补采,入档;
- 判定/冻结 K_ROLLOUT 不在本脚本:另由 stagek0_analyze.py 按预注册 §5 计算。

用法:
  MUJOCO_GL=osmesa python scripts/stagek0_calibration.py --gpu 0 \
      [--snapshots 2] [--kmax 2]   # 后两者仅冒烟;全量运行禁止
"""
from __future__ import annotations

# 代理防火墙先于任何 urllib/httpx 使用者(本机 http_proxy 劫持 loopback)
import os as _os

for _k in ("no_proxy", "NO_PROXY"):
    _v = _os.environ.get(_k)
    _loop = "127.0.0.1,localhost"
    _os.environ[_k] = (_v + "," + _loop) if _v else _loop

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stagek_graph_executor import (  # noqa: E402
    EdgeExecutor, ERROR, load_edges)

K_MAX = 16
MAX_RETRY = 3


def _load_source_steps(episode_dir: str) -> list[dict]:
    steps = json.load(open(Path(episode_dir) / "states.json"))
    return sorted(steps, key=lambda s: s.get("step_idx", 0))


def _last_pick_prompt(steps: list[dict], T: int) -> str | None:
    prompt = None
    for s in steps:
        c = s.get("command") or {}
        if s.get("step_idx", 0) <= T and c.get("action") in ("pi0_pick", "pi0_doubled"):
            if isinstance(c.get("prompt"), str):
                prompt = c["prompt"]
    return prompt


def _task_language(steps: list[dict]) -> str | None:
    for s in steps:
        if s.get("task_language"):
            return s["task_language"]
    return None


def run_snapshot(snap: dict, edges: dict, gpu: int, shared_kwargs: dict,
                 log_root: Path, kmax: int) -> list[dict]:
    """单个 snapshot × 全部合法边 × k=1..kmax;返回 rollout 记录列表。"""
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    outdir = log_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{snap['snapshot_id']}"
    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)

    env_spec = get_env_spec("libero")
    args = argparse.Namespace(
        suite="libero_spatial", task=snap["task"], seed=snap["seed"],
        max_episode_steps=200000, cuda_device=gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None,
    )
    daemons, recs = [], []
    toolkit = None
    try:
        env_daemons, env_kwargs = env_spec.init_task_runtime(
            args, outdir, NullDashboardEventSink())
        daemons.extend(env_daemons)
        primitives_kwargs = dict(env_kwargs)
        primitives_kwargs.update(shared_kwargs)
        toolkit = get_toolkit(
            "libero", primitives_kwargs=primitives_kwargs,
            video_path=str(outdir / "episode.mp4"),
            dashboard_events=NullDashboardEventSink())
        prims = toolkit._primitives
        env = prims.env

        # --- 重放 prefix 1..T → snapshot(J0 同款)-----------------------
        steps = _load_source_steps(snap["episode_dir"])
        T = snap["T"]
        t0 = time.time()
        for s in steps:
            idx, cmd = s.get("step_idx"), s.get("command")
            if idx is None or not cmd or not (1 <= idx <= T):
                continue
            toolkit._step(cmd["action"], **{k: v for k, v in cmd.items()
                                            if k != "action"})
        replay_s = round(time.time() - t0, 1)
        S = env.save_state()
        base_obs = env.restore_state(S)
        prims.set_obs(base_obs)
        ex = EdgeExecutor(toolkit, env, prims, outdir)
        baseline = ex.measure()
        ctx = {"task_lang": _task_language(steps),
               "last_pick": _last_pick_prompt(steps, T)}
        print(f"[K0] {snap['snapshot_id']} replay={replay_s}s "
              f"ooi={baseline['ooi']} edges={snap['legal_edges']}", flush=True)

        for edge_id in snap["legal_edges"]:
            edge = edges[edge_id]
            for k in range(1, kmax + 1):
                for attempt in range(1, MAX_RETRY + 1):
                    rec = {
                        "snapshot_id": snap["snapshot_id"], "edge_id": edge_id,
                        "family": edge["failure_family"], "k": k,
                        "attempt": attempt,
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                    ok = False
                    try:
                        obs = env.restore_state(S)
                        prims.set_obs(obs)
                        readback = env.save_state()
                        diff = float(abs(readback - S).max()) \
                            if len(readback) == len(S) else -1.0
                        rec["readback_max_abs_diff"] = diff
                        if diff != 0.0:
                            rec["infra_error"] = f"restore readback {diff}"
                        else:
                            r = ex.exec_edge(edge, ctx)
                            rec.update(r)
                            ok = True
                    except Exception as exc:
                        rec["infra_error"] = (
                            f"{type(exc).__name__}: {exc}"[:300])
                    recs.append(rec)
                    if ok:
                        break
                last = recs[-1]
                print(f"[K0]   {edge_id} k={k:2d} -> {last.get('outcome') or last.get('infra_error','?')[:60]}"
                      f" ({last.get('elapsed_s','?')}s)", flush=True)
    finally:
        try:
            if toolkit is not None:
                toolkit.close()
        except Exception:
            pass
        for d in daemons:
            try:
                d.stop()
            except Exception:
                pass
    return recs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection",
                    default="analysis/stageK0_snapshot_selection.json")
    ap.add_argument("--out", default="analysis/stageK0_rollouts.jsonl")
    ap.add_argument("--log-root", default="logs/stageK0")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--snapshots", type=int, default=None,
                    help="只跑前 N 个快照(冒烟;全量运行禁止)")
    ap.add_argument("--kmax", type=int, default=K_MAX,
                    help="每边 rollout 数上限(冒烟可降;全量=16)")
    ap.add_argument("--only", default=None,
                    help="仅重跑指定组合 snap_id:edge_id[,…](infra 补采;"
                         "记录后写覆盖,前后均保留)")
    args = ap.parse_args()

    # 防重锁(CLAUDE.md 纪律;存在即拒绝)
    lock = Path("/workspace/yjx/.runlocks/stagek0.lock")
    try:
        lock.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"[K0] 拒绝启动:锁已存在 {lock}", flush=True)
        return 1
    import atexit
    atexit.register(lambda: lock.rmdir() if lock.exists() else None)

    selection = json.load(open(REPO / args.selection))
    snaps = selection["snapshots"]
    if args.snapshots:
        snaps = snaps[: args.snapshots]
    if args.only:
        want: dict[str, list] = {}
        for tok in args.only.split(","):
            s, _, e = tok.partition(":")
            want.setdefault(s.strip(), []).append(e.strip())
        snaps = [dict(s, legal_edges=[e for e in s["legal_edges"]
                                      if e in want.get(s["snapshot_id"], [])])
                 for s in snaps if s["snapshot_id"] in want]
        snaps = [s for s in snaps if s["legal_edges"]]
        print(f"[K0] 补采模式:{[s['snapshot_id'] for s in snaps]}", flush=True)
    edges = load_edges()
    log_root = REPO / args.log_root
    log_root.mkdir(parents=True, exist_ok=True)

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = log_root / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)

    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=200000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    print(f"[K0] boot shared vla+sam3 on gpu{args.gpu} ...", flush=True)
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())
    print(f"[K0] shared runtime ready: {sorted(shared_kwargs)}", flush=True)

    n_out = n_infra = 0
    try:
        with open(REPO / args.out, "a") as f:
            for snap in snaps:
                t0 = time.time()
                try:
                    recs = run_snapshot(snap, edges, args.gpu,
                                        shared_kwargs, log_root, args.kmax)
                except Exception as exc:  # 快照级 infra(boot/重放失败)
                    recs = [{"snapshot_id": snap["snapshot_id"],
                             "edge_id": None, "family": snap["family"],
                             "k": None, "attempt": 1,
                             "ts": datetime.now().isoformat(timespec="seconds"),
                             "infra_error": f"{type(exc).__name__}: {exc}"[:300],
                             "traceback": traceback.format_exc()[-1200:]}]
                for r in recs:
                    try:
                        line = json.dumps(r, ensure_ascii=False, default=str)
                    except Exception as exc:
                        line = json.dumps({
                            "snapshot_id": r.get("snapshot_id"),
                            "edge_id": r.get("edge_id"), "k": r.get("k"),
                            "infra_error": f"serialize: {exc}"},
                            ensure_ascii=False)
                    f.write(line + "\n")
                    f.flush()
                    if r.get("infra_error"):
                        n_infra += 1
                    else:
                        n_out += 1
                wall = round(time.time() - t0, 1)
                print(f"[K0] {snap['snapshot_id']} done: {len(recs)} rollouts"
                      f" ({wall}s) cumulative ok={n_out} infra={n_infra}",
                      flush=True)
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    print(f"[K0] done: ok={n_out} infra={n_infra} -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    __import__("os").environ.setdefault("MUJOCO_GL", "osmesa")
    raise SystemExit(main())
