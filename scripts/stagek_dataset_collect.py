#!/usr/bin/env python
"""Stage K §3 — 转移数据集采集 runner((snapshot, edge, rollout) 单元)。

与 K0 标定的差异(其余协议逐条复用 stagek0_calibration.py):
- 输入:冻结选择清单 analysis/stageK_dataset_selection.json(K_ROLLOUT 冻结后
  由 stagek_dataset_select.py 生成;含 TRAIN/VAL/TEST 机械切分);
- 逐 rollout 增量落盘(K0 按快照缓冲;本跑数小时,断点续采必须);
- 每快照重放后立即捕获 RGB:dump 快照帧并**立即拷出** hi-res artifact
  (dump_state 只保留最近 5 步 hi-res,链推进 >4 步即被 GC —— 见
  stageK0_prereg.md §3),低清帧一并登记;
- 字段分 runtime_input / analysis_only 于训练装配时标记,本文件只采集。

用法(全量运行前先跑 stagek_dataset_select.py 冻结清单):
  MUJOCO_GL=osmesa python scripts/stagek_dataset_collect.py --gpu 0 \
      [--max-rollouts N] [--snapshots id1,id2]
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
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stagek_graph_executor import (  # noqa: E402
    EdgeExecutor, load_edges)

MAX_RETRY = 3

# 快照帧捕获清单:hi-res(GC 风险 → 拷出)+ 低清(全保留 → 登记路径)。
# 模板必须是带子目录的完整相对路径(ARTIFACT_LAYOUT 的 value 形式;
# 冒烟2发现纯文件名模板让拷出在 run 目录根部找文件、静默全 missing)。
_CAPTURE = [
    ("image", "agentview", "high", "images_cam_hi/image_cam_hi_{step:02d}.png", True),
    ("world", "agentview", "high", "world_hi/world_hi_{step:02d}.npy", True),
    ("image", "wrist", "high", "images_wrist_hi/image_wrist_hi_{step:02d}.png", True),
    ("world", "wrist", "high", "world_wrist_hi/world_wrist_hi_{step:02d}.npy", True),
    ("policy_image", "agentview", "low", "images/image_{step:02d}.png", False),
    ("image", "agentview", "low", "images_cam/image_cam_{step:02d}.png", False),
    ("image", "wrist", "low", "images_wrist/image_wrist_{step:02d}.png", False),
    ("depth", "agentview", "low", "depths/depth_{step:02d}.npy", False),
]


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


def capture_snapshot_rgb(toolkit, prims, outdir: Path, snapshot_id: str) -> dict:
    """dump 快照帧并立即拷出 hi-res(GC 窗口只有最近 5 步)。

    拷出目录 snapshot_rgb/<snapshot_id>/;低清只登记原路径(全保留)。
    返回 {rel_path, copy_path} 清单 + 所用 step 号,入 manifest。
    """
    from robots.libero import tools as lt
    step = toolkit._next_step + 1
    lt.dump_state(prims, str(outdir), step_idx=step, log={"snapshot": True})
    cap_dir = outdir / "snapshot_rgb" / snapshot_id
    cap_dir.mkdir(parents=True, exist_ok=True)
    captured = {"step": step, "copied": [], "referenced": []}
    for kind, cam, res, tmpl, copy in _CAPTURE:
        rel = tmpl.format(step=step)
        src = outdir / rel
        if not src.exists():
            if copy:
                # hi-res 是 §4 特征源,缺失即失败(渲染/GC 语义破坏)
                raise RuntimeError(f"快照 hi-res artifact 缺失: {rel}")
            captured["referenced"].append({"path": rel, "missing": True})
            continue
        if copy:  # hi-res 立即拷出(否则链推进 >4 步被 GC)
            dst = cap_dir / Path(rel).name
            shutil.copy2(src, dst)
            captured["copied"].append(str(dst.relative_to(outdir)))
        else:
            captured["referenced"].append({"path": rel, "missing": False})
    return captured


def run_snapshot(snap: dict, edges: dict, gpu: int, shared_kwargs: dict,
                 log_root: Path, kmax: int, emit, done: set) -> int:
    """单个 snapshot × 全部合法边 × k=1..kmax;emit(rec) 逐条落盘。

    done = 已有有效 (edge_id, k) 集合(断点续采跳过)。返回本快照新增数。
    """
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
    daemons, n_new = [], 0
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

        # --- 重放 prefix 1..T → snapshot(与 K0/J0 同款) ----------------
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
        # 快照 RGB 捕获(dump 后立即拷出 hi-res;§3)
        rgb = capture_snapshot_rgb(toolkit, prims, outdir, snap["snapshot_id"])
        ctx = {"task_lang": _task_language(steps),
               "last_pick": _last_pick_prompt(steps, T)}
        print(f"[KD] {snap['snapshot_id']} replay={replay_s}s ooi={baseline['ooi']} "
              f"rgb_step={rgb['step']} edges={snap['legal_edges']}", flush=True)

        for edge_id in snap["legal_edges"]:
            edge = edges[edge_id]
            for k in range(1, kmax + 1):
                if (snap["snapshot_id"], edge_id, k) in done:
                    continue
                for attempt in range(1, MAX_RETRY + 1):
                    rec = {
                        "snapshot_id": snap["snapshot_id"], "edge_id": edge_id,
                        "family": edge["failure_family"], "k": k,
                        "attempt": attempt, "split": snap.get("split"),
                        "task": snap["task"], "seed": snap["seed"],
                        "arm": snap.get("arm"), "T": T,
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
                            rec["snapshot_rgb"] = {
                                "outdir": str(outdir.name), **rgb}
                            ok = True
                    except Exception as exc:
                        rec["infra_error"] = (
                            f"{type(exc).__name__}: {exc}"[:300])
                    emit(rec)
                    if ok:
                        n_new += 1
                        break
                last = rec
                print(f"[KD]   {edge_id} k={k:2d} -> "
                      f"{last.get('outcome') or str(last.get('infra_error','?'))[:60]}"
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
    return n_new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection",
                    default="analysis/stageK_dataset_selection.json")
    ap.add_argument("--out", default="analysis/stageK_transition_rollouts.jsonl")
    ap.add_argument("--manifest",
                    default="analysis/stageK_transition_dataset_manifest.csv")
    ap.add_argument("--log-root", default="logs/stageK_dataset")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--max-rollouts", type=int, default=None,
                    help="全局新增 rollout 上限(预算闸;到量即停)")
    ap.add_argument("--snapshots", default=None,
                    help="逗号分隔 snapshot_id 白名单(补采用)")
    args = ap.parse_args()

    # 防重锁(CLAUDE.md 纪律)
    lock = Path("/workspace/yjx/.runlocks/stagek_dataset.lock")
    try:
        lock.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"[KD] 拒绝启动:锁已存在 {lock}", flush=True)
        return 1
    import atexit
    atexit.register(lambda: lock.rmdir() if lock.exists() else None)

    selection = json.load(open(REPO / args.selection))
    kmax = selection["budget"]["k_rollout"]
    snaps = selection["snapshots"]
    if args.snapshots:
        keep = set(args.snapshots.split(","))
        snaps = [s for s in snaps if s["snapshot_id"] in keep]

    # 断点续采:已有有效记录的 (snap, edge, k) 跳过
    out_path = REPO / args.out
    done: set = set()
    if out_path.exists():
        for line in open(out_path):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("outcome") and not r.get("infra_error"):
                done.add((r.get("snapshot_id"), r.get("edge_id"), r.get("k")))
        print(f"[KD] resume:{len(done)} 条已有有效记录,跳过", flush=True)

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
    print(f"[KD] boot shared vla+sam3 on gpu{args.gpu} ...", flush=True)
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())
    print(f"[KD] shared runtime ready | kmax(=K_ROLLOUT)={kmax} | "
          f"snapshots={len(snaps)}", flush=True)

    n_out = n_infra = 0
    fout = open(out_path, "a")

    def emit(r: dict) -> None:
        nonlocal n_out, n_infra
        try:
            line = json.dumps(r, ensure_ascii=False, default=str)
        except Exception as exc:
            line = json.dumps({
                "snapshot_id": r.get("snapshot_id"),
                "edge_id": r.get("edge_id"), "k": r.get("k"),
                "infra_error": f"serialize: {exc}"}, ensure_ascii=False)
        fout.write(line + "\n")
        fout.flush()
        if json.loads(line).get("infra_error"):
            n_infra += 1
        else:
            n_out += 1

    try:
        for snap in snaps:
            if args.max_rollouts and n_out >= args.max_rollouts:
                print(f"[KD] 预算闸到量(n_out={n_out}),停止排新快照", flush=True)
                break
            t0 = time.time()
            try:
                new = run_snapshot(snap, edges, args.gpu, shared_kwargs,
                                   log_root, kmax, emit, done)
            except Exception as exc:  # 快照级 infra(boot/重放失败)
                emit({"snapshot_id": snap["snapshot_id"], "edge_id": None,
                      "family": snap.get("family"), "k": None, "attempt": 1,
                      "split": snap.get("split"), "task": snap.get("task"),
                      "seed": snap.get("seed"), "arm": snap.get("arm"),
                      "ts": datetime.now().isoformat(timespec="seconds"),
                      "infra_error": f"{type(exc).__name__}: {exc}"[:300],
                      "traceback": traceback.format_exc()[-1200:]})
                new = 0
            wall = round(time.time() - t0, 1)
            print(f"[KD] {snap['snapshot_id']} done: +{new} "
                  f"({wall}s) cumulative ok={n_out} infra={n_infra}", flush=True)
    finally:
        fout.close()
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    print(f"[KD] done: ok={n_out} infra={n_infra} -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    __import__("os").environ.setdefault("MUJOCO_GL", "osmesa")
    raise SystemExit(main())
