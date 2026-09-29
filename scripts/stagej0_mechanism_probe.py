#!/usr/bin/env python
"""Stage J0 机制探针(判定后归因用,不改四门结论)。

问题:J0 的 A_vla 支对 0/20 一致 —— 噪声从哪一层进来?
  T1 VLA 推断确定性:同一 obs 连续 predict 两次,动作是否逐位一致;
  T2 restore 观测等价性:同快照两次 restore 生成的 obs(states / 图像)
     是否逐位一致,以及各自喂 VLA 后动作是否一致;
  T3 渲染确定性:同状态连续 render_camera 两次是否逐位一致。

用法:MUJOCO_GL=osmesa python scripts/stagej0_mechanism_probe.py --gpu 0
产物:analysis/stageJ0_mechanism_probe.json
"""
from __future__ import annotations

# 代理放行必须先于任何 urllib/httpx 使用者(本机 http_proxy 劫持 loopback)
import os as _os

for _k in ("no_proxy", "NO_PROXY"):
    _v = _os.environ.get(_k)
    _loop = "127.0.0.1,localhost"
    _os.environ[_k] = (_v + "," + _loop) if _v else _loop

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _maxdiff(a, b) -> float:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return -1.0
    return float(np.abs(a - b).max()) if a.size else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--task", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--prompt", default="pick up the black bowl on the stove")
    ap.add_argument("--n-predict", type=int, default=3)
    args = ap.parse_args()

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir

    out = {"ts": datetime.now().isoformat(timespec="seconds"),
           "task": args.task, "seed": args.seed, "gpu": args.gpu,
           "prompt": args.prompt}
    outdir = REPO / "logs" / "stageJ0" / f"probe_{datetime.now().strftime('%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)

    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=args.task, seed=args.seed,
        max_episode_steps=10000, cuda_device=args.gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None,
    )
    env_daemons, env_kwargs = env_spec.init_task_runtime(
        ns, outdir, NullDashboardEventSink())
    shared_daemons, shared = env_spec.init_shared_runtime(
        ns, outdir, NullDashboardEventSink())
    env, model = env_kwargs["env"], shared["model"]

    try:
        # 前进一步让 scene 离开 init 瞬态(与生产路径一致的 reset 流程)
        obs0, _ = env.reset()
        S = env.save_state()

        # T2:同快照两次 restore 的 obs 等价性
        obsA = env.restore_state(S)
        obsB = env.restore_state(S)
        out["T2_obs"] = {
            "states_maxdiff": _maxdiff(obsA["states"], obsB["states"]),
            "main_images_maxdiff": _maxdiff(obsA["main_images"], obsB["main_images"]),
            "wrist_images_maxdiff": _maxdiff(obsA["wrist_images"], obsB["wrist_images"]),
        }

        # T3:同状态连续渲染两次
        r1 = env.render_camera("agentview", 256, 256)
        r2 = env.render_camera("agentview", 256, 256)
        out["T3_render"] = {"agentview_maxdiff": _maxdiff(r1, r2)}

        # T1:同一 obs 重复 predict 的动作确定性
        def predict(obs):
            o = copy.deepcopy(obs)
            o["task_descriptions"] = args.prompt
            o.setdefault("extra_view_images", None)
            a, _ = model.predict_action_batch(o, mode="eval")
            return np.asarray(a, dtype=np.float64)

        acts = [predict(obsA) for _ in range(args.n_predict)]
        act_b = predict(obsB)
        out["T1_predict_same_obs"] = {
            f"act{i}_vs_act0_maxdiff": _maxdiff(acts[i], acts[0])
            for i in range(1, args.n_predict)}
        out["T1_shape"] = list(acts[0].shape)
        out["T2_predict_obsA_vs_obsB"] = {
            "actA0_vs_actB_maxdiff": _maxdiff(acts[0], act_b)}
    finally:
        for d in env_daemons + shared_daemons:
            try:
                d.stop()
            except Exception:
                pass

    json.dump(out, open(REPO / "analysis/stageJ0_mechanism_probe.json", "w"),
              indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    __import__("os").environ.setdefault("MUJOCO_GL", "osmesa")
    raise SystemExit(main())
