#!/usr/bin/env python3
"""P1 渲染/步进/落盘微基准(纯 CPU · osmesa · 非 episode · 零 GPU)。

目的:把 run.log 里 pi0_pick/move_to 的工具时长拆成
MuJoCo step(含 256 obs 渲染)/ 1024 hi-res 渲染 / PNG+NPY 落盘 三部分。
裸 env(seed 0,不在 manifest 网格),≤300 步,不触 planner/probe/GPU。

口径:全部为单 worker 串行均值;渲染走生产 render_camera RPC 通道。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# GL 铁律:osmesa 必须在任何 mujoco 导入前(本容器 /dev/dri 不存在)
os.environ["MUJOCO_GL"] = "osmesa"
os.environ["PYOPENGL_PLATFORM"] = "osmesa"
for k in ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE"):
    os.environ.pop(k, None)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from robots.libero.env_server import LiberoEnvFacade, make_env  # noqa: E402

N_STEPS = 200
N_RENDER = 5
OUT = REPO / "artifacts" / "p1_perf"


def _avg(fn, n, warmup=1):
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1000.0  # ms


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    raw = make_env(9, 0, max_episode_steps=1500)
    f = LiberoEnvFacade(raw, meta={"task": 9, "seed": 0})
    build_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    f.reset()
    reset_s = time.perf_counter() - t0

    import numpy as np

    a = np.zeros(7, dtype=np.float32)
    a[6] = -1.0
    step_ms = _avg(lambda: f.step(a), N_STEPS)

    # 1024 hi-res 渲染(生产 render_camera 通道,RGB+depth)
    render_ms = _avg(
        lambda: f._env.render_camera(camera_name="agentview", height=1024,
                                     width=1024, depth=True), N_RENDER)
    render_wrist_ms = _avg(
        lambda: f._env.render_camera(camera_name="robot0_eye_in_hand",
                                     height=1024, width=1024, depth=True),
        N_RENDER)
    render256_ms = _avg(
        lambda: f._env.render_camera(camera_name="agentview", height=256,
                                     width=256, depth=True), N_RENDER)

    # 落盘:一次 dump_state 的 hi 套件 = 2×PNG(1024²)+ 2×NPY(float16 世界点云)
    import imageio.v2 as imageio
    tmp = OUT / "bench_tmp"
    tmp.mkdir(exist_ok=True)
    rgb = (np.random.rand(1024, 1024, 3) * 255).astype(np.uint8)
    world = np.random.rand(1024, 1024, 3).astype(np.float16)
    png_ms = _avg(lambda: imageio.imwrite(tmp / "b.png", rgb), N_RENDER)
    npy_ms = _avg(lambda: np.save(tmp / "b.npy", world), N_RENDER)

    # 低清 obs 尺寸 PNG(256) 对照
    rgb256 = (np.random.rand(256, 256, 3) * 255).astype(np.uint8)
    png256_ms = _avg(lambda: imageio.imwrite(tmp / "b256.png", rgb256),
                     N_RENDER)

    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    f._env.close()

    result = {
        "env": "t9 seed0 bare facade (osmesa CPU, no episode)",
        "env_build_s": round(build_s, 2),
        "env_reset_s": round(reset_s, 2),
        "env_step_ms_avg_incl_256obs_render": round(step_ms, 2),
        "render_1024_rgbdepth_agentview_ms": round(render_ms, 2),
        "render_1024_rgbdepth_wrist_ms": round(render_wrist_ms, 2),
        "render_256_rgbdepth_ms": round(render256_ms, 2),
        "png_write_1024_ms": round(png_ms, 2),
        "npy_write_float16_1024_ms": round(npy_ms, 2),
        "png_write_256_ms": round(png256_ms, 2),
        "n_steps": N_STEPS, "n_render": N_RENDER,
        "caveats": [
            "单 worker 串行均值;机器共享,绝对值有 ±20% 噪声",
            "env_step 含 256 obs 渲染与 RPC 往返,即生产每步真实成本",
            "dump_state 内部还有 metric_depth/world_from_depth 变换,",
            "未单独计时 → 落盘估计为下界",
        ],
    }
    out = OUT / "microbench.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
