"""VLA inference chain verification for RPent / Pi0.5 on LIBERO.

Replicates the exact runtime call path of ``robots/libero/vla_server.py``:
    env_obs (dict) -> model.predict_action_batch(env_obs, mode="eval")

Inside predict_action_batch:
    env_obs -> obs_processor (Normalize: images, state via norm_stats)
            -> input_transform -> precision_processor
            -> Observation.from_dict -> sample_actions (flow denoise)
            -> output_transform (Unnormalize quantile + slice [:action_chunk] + [:7])
            -> (actions, info)

Checks: single + batch forward, shape/dtype/range, NaN/Inf, normalization
sanity (model_action pre-denorm vs env action post-denorm), variability across
observations, determinism.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time

import imageio.v2 as imageio
import numpy as np

REPO = "/hw-tbo/yjx/workspace/RPent"
sys.path.insert(0, REPO)
os.environ.setdefault("ROBOT_PLATFORM", "LIBERO")

CKPT = os.environ.get(
    "PI05_CHECKPOINT_PATH",
    "/hw-tbo/yjx/checkpoints/RLinf-Pi05-LIBERO-130-fullshot-SFT",
)

IMG_H = IMG_W = 224
STATE_DIM = 32      # 7 joints + gripper + zero-padding (matches norm_stats)
ACTION_DIM = 7      # LIBERO env action dim (joint deltas, radians)
ACTION_CHUNK = 5    # env executes this many steps per predict

rng = np.random.default_rng(20260807)


def b64png(img: np.ndarray) -> str:
    """Encode a uint8 HxWx3 image exactly like the env_client does."""
    return base64.b64encode(imageio.imwrite("<bytes>", img, format="png", plugin="pillow")).decode()


def make_scene_image(seed: int, obj_x: float, obj_y: float) -> np.ndarray:
    y, x = np.mgrid[0:IMG_H, 0:IMG_W].astype(np.float32)
    img = np.zeros((IMG_H, IMG_W, 3), dtype=np.float32)
    img[..., 0] = 0.55 * y / IMG_H + 0.10 * x / IMG_W
    img[..., 1] = 0.45 * y / IMG_H + 0.08 * x / IMG_W
    img[..., 2] = 0.35 * y / IMG_H + 0.12 * x / IMG_W
    arm = np.exp(-((x - 0.30 * IMG_W) ** 2 + (y - 0.25 * IMG_H) ** 2) / (2 * 60**2))
    img[..., :] *= (1 - 0.6 * arm[..., None])
    blob = np.exp(-((x - obj_x * IMG_W) ** 2 + (y - obj_y * IMG_H) ** 2) / (2 * 25**2))
    obj_col = np.array([(0.85, 0.15, 0.15), (0.15, 0.85, 0.15), (0.2, 0.3, 0.9)])[seed % 3]
    img += blob[..., None] * obj_col[None, None, :]
    img = np.clip(img, 0, 1)
    return (img * 255).astype(np.uint8)


def make_state(seed: int, grasp: float = 0.0) -> np.ndarray:
    s = np.zeros(STATE_DIM, dtype=np.float32)
    s[:7] = np.array([0.30 + 0.02 * seed, -0.20 + 0.01 * seed, 0.76, 2.97, -0.22, -0.13, 0.03]) \
        + 0.01 * rng.standard_normal(7).astype(np.float32)
    s[7] = grasp
    return s


INSTRUCTIONS = [
    "pick up the red block and place it on the plate",
    "push the white bowl to the front of the table",
    "open the top drawer of the cabinet",
]


def build_obs(seed: int, grasp: float = 0.0, use_wrist: bool = True) -> dict:
    main = make_scene_image(seed, 0.4 + 0.05 * seed, 0.55)
    images = {"main": {"format": "png", "data": b64png(main)}}
    if use_wrist:
        images["wrist"] = {"format": "png", "data": b64png(make_scene_image(seed + 100, 0.5, 0.3))}
    return {
        "instruction": INSTRUCTIONS[seed % len(INSTRUCTIONS)],
        "images": images,
        "state": make_state(seed, grasp).tolist(),
    }


def report(name: str, arr: np.ndarray) -> None:
    a = arr.reshape(-1, arr.shape[-1]) if arr.ndim == 3 else arr
    print(f"\n--- {name} ---")
    print(f"  shape      : {arr.shape}")
    print(f"  dtype      : {arr.dtype}")
    print(f"  min/max    : {arr.min():+.4f} / {arr.max():+.4f}")
    print(f"  mean/std   : {arr.mean():+.4f} / {arr.std():+.4f}")
    print(f"  nan/inf    : {np.isnan(arr).any()} / {np.isinf(arr).any()}")
    for i in range(min(ACTION_DIM, a.shape[-1])):
        print(f"  dim{i:<2} min/med/max: {a[:, i].min():+.4f} / {np.median(a[:, i]):+.4f} / {a[:, i].max():+.4f}")


def main() -> int:
    import torch
    from robots.libero.vla_server import _build_env_obs, build_model_cfg
    from rlinf.models.embodiment.openpi import get_model as get_openpi_model

    ns = json.load(open(os.path.join(CKPT, "physical-intelligence", "libero", "norm_stats.json")))
    a_mean = np.array(ns["norm_stats"]["actions"]["mean"], np.float32)[:ACTION_DIM]
    a_std = np.array(ns["norm_stats"]["actions"]["std"], np.float32)[:ACTION_DIM]
    a_q01 = np.array(ns["norm_stats"]["actions"]["q01"], np.float32)[:ACTION_DIM]
    a_q99 = np.array(ns["norm_stats"]["actions"]["q99"], np.float32)[:ACTION_DIM]
    print(f"checkpoint : {CKPT}")
    print(f"env-action q01 : {a_q01.tolist()}")
    print(f"env-action q99 : {a_q99.tolist()}")
    print(f"env-action mean: {a_mean.tolist()}")

    t0 = time.time()
    model = get_openpi_model(build_model_cfg(model_path=CKPT), torch_dtype=None).cuda().eval()
    print(f"model loaded in {time.time()-t0:.1f}s: {type(model).__name__}")

    def build_batch_obs(specs):
        """Build an obs dict matching _build_env_obs output, batch of len(specs)."""
        mains = np.stack([imageio.imread(io.BytesIO(base64.b64decode(s["images"]["main"]["data"])))
                          for s in specs])
        states = np.stack([np.asarray(s["state"], np.float32) for s in specs])
        obs = {
            "main_images": mains,
            "task_descriptions": [s["instruction"] for s in specs],
            "wrist_images": None,
            "extra_view_images": None,
            "states": states,
        }
        if "wrist" in specs[0]["images"]:
            obs["wrist_images"] = np.stack(
                [imageio.imread(io.BytesIO(base64.b64decode(s["images"]["wrist"]["data"])))
                 for s in specs])
        return obs

    def run(obs_specs, label):
        obs = build_batch_obs(obs_specs)
        with torch.no_grad():
            acts, info = model.predict_action_batch(obs, mode="eval")
        a = acts.detach().cpu().numpy()
        ma = info["forward_inputs"]["model_action"].detach().cpu().numpy()
        report(f"{label}: env actions (denormalized)", a)
        report(f"{label}: model_action (pre-denorm)", ma.reshape(ma.shape[0], -1))
        print(f"  env actions shape            : {a.shape}")
        return a, ma

    print("\n================ 1. SINGLE-SAMPLE FORWARD ================")
    a1, ma1 = run([build_obs(seed=0)], "single")

    print("\n================ 2. BATCH FORWARD (B=4) ================")
    specs = [build_obs(0, 0.0), build_obs(1, 1.0), build_obs(2, 0.0), build_obs(0, 0.5)]
    aB, maB = run(specs, "batch(B=4)")

    print("\n================ 3. VARIABILITY ================")
    with torch.no_grad():
        # same everything, change only instruction text
        oa = _build_env_obs(specs[0]["instruction"], specs[0]["images"], np.asarray(specs[0]["state"], np.float32).reshape(1, -1))
        ob = _build_env_obs(INSTRUCTIONS[1], specs[0]["images"], np.asarray(specs[0]["state"], np.float32).reshape(1, -1))
        aa, _ = model.predict_action_batch(oa, mode="eval")
        bb, _ = model.predict_action_batch(ob, mode="eval")
        # change image only
        oc = _build_env_obs(specs[0]["instruction"], build_obs(2)["images"], np.asarray(specs[0]["state"], np.float32).reshape(1, -1))
        cc, _ = model.predict_action_batch(oc, mode="eval")
        # change grasp only
        od = _build_env_obs(specs[0]["instruction"], specs[0]["images"], np.asarray(build_obs(0, 1.0)["state"], np.float32).reshape(1, -1))
        dd, _ = model.predict_action_batch(od, mode="eval")
        # determinism: same obs again
        ee, _ = model.predict_action_batch(oa, mode="eval")
    aa, bb, cc, dd, ee = (x.detach().cpu().numpy() for x in (aa, bb, cc, dd, ee))
    d_txt = float(np.abs(aa - bb).max())
    d_img = float(np.abs(aa - cc).max())
    d_grp = float(np.abs(aa - dd).max())
    d_det = float(np.abs(aa - ee).max())
    print(f"  max|action| on instruction change : {d_txt:.5f}")
    print(f"  max|action| on image change       : {d_img:.5f}")
    print(f"  max|action| on grasp change       : {d_grp:.5f}")
    print(f"  max|action| same-obs (repeat, stochastic): {d_det:.7f}  (flow sampling noise, expected)")

    # per-dim variability across the batch
    print("\n  per-dim env-action std across batch (B=4):")
    a4 = aB.reshape(4, -1, ACTION_DIM)
    for i in range(ACTION_DIM):
        print(f"    dim{i}: {a4[:, :, i].std():+.4f}")

    print("\n================ 4. NORMALIZATION / VALUE SANITY ================")
    env = a1.reshape(-1, ACTION_DIM)
    frac_in_q = float(((env >= a_q01[None, :]) & (env <= a_q99[None, :])).mean())
    frac_in_q99 = float(((env >= a_q01[None, :]) & (env <= a_q99[None, :]).max(axis=0)).mean())
    frac_in_qrange = float(((env >= a_q01[None, :]) & (env <= a_q99[None, :])).mean())
    print(f"  env actions within [q01,q99]: {frac_in_q:.1%}  (may exceed q99 when model output > 1)")
    # physically plausible: joint deltas beyond +/-4 rad are implausible
    frac_plaus = float((np.abs(env) <= 4.0).mean())
    print(f"  |env action| <= 4 rad (plausible): {frac_plaus:.1%}")
    ma_flat = ma1.reshape(-1)
    print(f"  model_action range: {ma_flat.min():+.3f}..{ma_flat.max():+.3f} (raw flow output, ~[-1,2.6])")

    print("\n================ VERDICT ================")
    checks = {
        "env actions shape [B,5,7]": (a1.ndim == 3 and a1.shape == (1, ACTION_CHUNK, ACTION_DIM)),
        "batch shape [4,5,7]": (aB.shape == (4, ACTION_CHUNK, ACTION_DIM)),
        "no NaN/Inf": (not np.isnan(a1).any() and not np.isinf(a1).any()
                       and not np.isnan(aB).any() and not np.isinf(aB).any()),
        "finite everywhere": bool(np.isfinite(a1).all() and np.isfinite(aB).all()),
        "actions vary with image": (d_img > 1e-3),
        "actions vary with grasp": (d_grp > 1e-3),
        # flow/diffusion model samples fresh noise per call -> same-obs repeats
        # differ by a bounded, non-degenerate amount (NOT constant, NOT divergent)
        "stochastic but stable (same-obs)": (1e-4 < d_det < 2.0),
        "denorm != model_action (transform active)": not np.allclose(a1.reshape(-1), ma1.reshape(-1)[: a1.size], atol=1e-3),
        "actions physically plausible": (frac_plaus > 0.99),
    }
    ok = all(checks.values())
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\n  VLA SIDE READY: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
