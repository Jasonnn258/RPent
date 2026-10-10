#!/usr/bin/env python3
"""P1 Pi0.5 常驻服务验证(工程测量,非 episode,不触 D-041 账本)。

问题:每集自 spawn vla_server → 每集重复加载 Pi0.5(实测 63.8-69.8s,
占总墙钟 9.8%)。robots/libero 已原生支持 --vla-endpoint 连常驻服务;
本脚本在隔离环境验证常驻模式的三个前提:

1. **可持续服务**:生产入口 vla_server.py 起一次,多次 predict 不崩。
2. **任务隔离**:换 instruction 后输出确实变化(服务不缓存任务)。
   模型推断本非确定(Stage J:同 obs 两次调用差 ~0.23-0.38),单对
   调用分不开"任务效应"与"噪声"——改用统计判据:A/B 指令交错各
   调 6 次,逐维 Welch z,**z>3 的维度数 ≥3** 才算任务效应系统性
   存在(max-dim 包络会被噪声最大的维度支配,不采用)。
3. **无漂移**:前半 A 批与后半 A 批均值差 ≤ 组内包络(无跨调用污染)。

obs 全部取自 DEV1A s2002 真实落盘帧(256 RGB)+ states.json 重建的
生产口径 8 维 state([eef_pos(3), quat→axisangle(3), gripper(2)],
rlinf libero_env._extract_image_and_state 同构),私有数据仅本地读取。

GPU 使用:GPU0 单卡、单 worker、~3 分钟(加载 1 次 + 4 次 predict);
这是独立工程测量,不产生 episode、不写 D-041 账本。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rpent.utils.http_rpc import HttpRpcClient  # noqa: E402
from rpent.utils.vla_client import VLAClient  # noqa: E402

PORT = 18729
OUT = REPO / "artifacts" / "p1_perf"
# DEV1A s2002 真实帧(step 0):私有 artifacts,只本地读、绝不提交
RUN_DIR = REPO / "artifacts" / "p1_dev1a" / "runs" / "p1dev1a_t9_s2002_b57ce6c9"
INSTR_A = ("pick the black bowl on the cabinet and place it on the plate")
INSTR_B = ("put the white mug on the stove into the drawer")  # 异任务指令


def _obs(instr: str) -> dict:
    """真实帧 + 生产口径 8 维 state,内容确定、与 seed 无关。"""
    import imageio.v2 as imageio
    import numpy as np
    from scipy.spatial.transform import Rotation

    st = json.loads((RUN_DIR / "states.json").read_text(encoding="utf-8"))[0]
    s = st["state"]
    # rlinf 口径:eef_pos + quat→axisangle + gripper_qpos(见
    # libero_env._extract_image_and_state)
    axisangle = Rotation.from_quat(s["robot0_eef_quat"]).as_rotvec()
    state = np.concatenate([
        np.asarray(s["robot0_eef_pos"], dtype=np.float32),
        axisangle.astype(np.float32),
        np.asarray(s["robot0_gripper_qpos"], dtype=np.float32),
    ])
    return {
        "main_images": imageio.imread(RUN_DIR / "images_cam" / "image_cam_00.png"),
        "wrist_images": imageio.imread(
            RUN_DIR / "images_wrist" / "image_wrist_00.png"),
        "task_descriptions": instr,
        "states": state,
    }


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), 9)
        proc.wait(timeout=10)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "PI05_CHECKPOINT_PATH": "/workspace/yjx/rpent_data/checkpoints/pi05",
        "OPENPI_DATA_HOME": "/workspace/yjx/rpent_data/.cache/openpi",
        "HF_HUB_OFFLINE": "1",
        "MUJOCO_GL": "osmesa", "PYOPENGL_PLATFORM": "osmesa",
        "CUDA_VISIBLE_DEVICES": "0",
    })
    for k in ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE"):
        env.pop(k, None)

    log = OUT / "vla_persist_server.log"
    t0 = time.time()
    result: dict = {}
    with open(log, "w") as fh:
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "robots" / "libero" / "vla_server.py"),
             "--transport", "http", "--host", "127.0.0.1",
             "--port", str(PORT)], env=env, stdout=fh,
            stderr=subprocess.STDOUT, start_new_session=True)
        try:
            cli = VLAClient(HttpRpcClient(f"http://127.0.0.1:{PORT}"))
            # 等模型就绪(healthz 通即认;首个 predict 另行计时)
            ready = False
            err = ""
            for _ in range(120):
                if proc.poll() is not None:
                    break
                try:
                    cli.healthz(timeout_s=2)
                    ready = True
                    break
                except Exception as e:
                    err = str(e)[:120]
                    time.sleep(2.0)
            if not ready:
                sys.exit(f"FATAL: vla_server not ready ({err}); see {log}")
            load_s = round(time.time() - t0, 1)

            obs_a = _obs(INSTR_A)
            obs_b = _obs(INSTR_B)

            t = time.time()
            a1, _ = cli.predict_action_batch(obs_a)
            first_pred_s = round(time.time() - t, 2)
            # A/B 交错各 6 次(含首调):任务效应与时序漂移去相关
            import numpy as np

            acts_a = [np.asarray(a1)]
            acts_b = []
            for i in range(6):
                b, _ = cli.predict_action_batch(obs_b)
                acts_b.append(np.asarray(b))
                a, _ = cli.predict_action_batch(obs_a)
                acts_a.append(np.asarray(a))
            acts_a = np.stack(acts_a)   # [7, chunk, act]
            acts_b = np.stack(acts_b)   # [6, chunk, act]

            def _pairwise_env(stack: np.ndarray) -> float:
                """组内包络:任意两次调用 max|Δaction|(非确定下界)。"""
                flat = stack.reshape(len(stack), -1)
                return float(max(
                    np.abs(flat[i] - flat[j]).max()
                    for i in range(len(flat)) for j in range(i + 1, len(flat))))

            env_a = _pairwise_env(acts_a)
            env_b = _pairwise_env(acts_b)
            within = max(env_a, env_b)
            mean_a = acts_a.mean(axis=0)
            mean_b = acts_b.mean(axis=0)
            sep = float(np.abs(mean_a - mean_b).max())
            half = len(acts_a) // 2 + 1  # 首 4 次 vs 末 3 次
            drift = float(np.abs(acts_a[:half].mean(axis=0)
                                 - acts_a[half:].mean(axis=0)).max())
            # 逐维 Welch z:任务效应是否系统性跨维存在(而非单个噪声维)。
            # max-dim 包络判据会被噪声最大的维度支配,z 计数才是决定性统计。
            fa = acts_a.reshape(len(acts_a), -1)
            fb = acts_b.reshape(len(acts_b), -1)
            se = np.sqrt(fa.var(axis=0, ddof=1) / len(fa)
                         + fb.var(axis=0, ddof=1) / len(fb) + 1e-9)
            z = np.abs(fa.mean(axis=0) - fb.mean(axis=0)) / se
            n_z3 = int((z > 3.0).sum())
            # 原始动作落盘供离线复检(避免再起服务重测)
            np.savez(OUT / "vla_persist_actions.npz",
                     acts_a=acts_a, acts_b=acts_b)
            result = {
                "persistent_load_s": load_s,
                "first_predict_s": first_pred_s,
                "n_calls": {"A": len(acts_a), "B": len(acts_b)},
                "within_task_envelope_max": round(within, 4),
                "task_mean_separation": round(sep, 4),
                "drift_firsthalf_vs_lasthalf": round(drift, 4),
                "welch_z_max": round(float(z.max()), 2),
                "welch_z_gt3_dims": n_z3,
                "actions_dim": int(fa.shape[1]),
                "actions_shape": list(a1.shape),
                "criteria": {
                    "serving_ok": True,
                    "task_isolation_ok": n_z3 >= 3,
                    "no_cross_call_drift": drift <= max(within, 1e-6),
                },
                "caveats": [
                    "Stage J 已证 pi0.5 推断非确定;隔离判据=逐维 Welch z>3",
                    "的维度数≥3(任务效应系统性存在),非 bit-exact;",
                    "组内包络(单对 max|Δ|~0.40)=该模型非确定幅度,仅作参照",
                    "A/B 交错采样去相关时序;A 首 4 vs 末 3 均值查漂移",
                    "原始动作存 vla_persist_actions.npz(私有,仅本地)",
                    "obs=DEV1A s2002 真实帧+生产口径 8 维 state(私有,仅本地)",
                    "GPU0 单卡 ~4min 工程测量;非 episode、不进 D-041 账本",
                ],
            }
        finally:
            _stop(proc)
    out = OUT / "vla_persist_check.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    ok = all(result["criteria"].values())
    print(f"[vla_persist] {'PASS' if ok else 'FAIL'} -> {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
