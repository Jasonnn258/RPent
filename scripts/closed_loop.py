"""Minimal LIBERO x Pi0.5 closed-loop verification.

Loop (reuses RPent runtime):
    env.reset -> obs -> predict_action_batch(obs) -> [1,5,7] action chunk
                 -> env.chunk_step(chunk) -> next obs  (x10 chunks = 50 env steps)

Records per env step: main image stats, state (7-dim), executed action,
raw model_action (pre-denorm), denormalized action. Audits rendering, eef
motion, NaN/Inf, action ranges.
"""
import os, sys, time, json
import numpy as np

REPO = "/hw-tbo/yjx/workspace/RPent"
sys.path.insert(0, REPO)
os.environ.setdefault("ROBOT_PLATFORM", "LIBERO")
CKPT = os.environ.get("PI05_CHECKPOINT_PATH",
                      "/hw-tbo/yjx/checkpoints/RLinf-Pi05-LIBERO-130-fullshot-SFT")
OUT = "/tmp/closed_loop_records.json"


def main():
    import torch
    from robots.libero.env_server import make_env
    from robots.libero.vla_server import build_model_cfg
    from rlinf.models.embodiment.openpi import get_model as get_openpi_model

    print(f"[loop] loading Pi0.5 ...", flush=True)
    t0 = time.time()
    model = get_openpi_model(build_model_cfg(model_path=CKPT), torch_dtype=None).cuda().eval()
    print(f"[loop] model ready in {time.time()-t0:.1f}s", flush=True)

    print(f"[loop] creating LiberoEnv ...", flush=True)
    env = make_env(task_id=2, seed=0, suite_name="libero_spatial", max_episode_steps=500)
    obs, info = env.reset()
    print(f"[loop] env ready; task: {list(obs['task_descriptions'])}", flush=True)

    def to_np(t):
        return t.detach().cpu().numpy() if torch.is_tensor(t) else np.asarray(t)

    records = []
    n_chunks, chunk_len = 10, 5  # 50 env steps
    final_term = final_trunc = False
    for ci in range(n_chunks):
        vla_obs = {
            "main_images": obs["main_images"],       # [1,256,256,3] uint8
            "task_descriptions": list(obs["task_descriptions"]),
            "wrist_images": obs["wrist_images"],
            "extra_view_images": None,
            "states": obs["states"],                 # [1,7] torch
        }
        with torch.no_grad():
            acts, info_model = model.predict_action_batch(vla_obs, mode="eval")
        acts_np = to_np(acts).astype(np.float64)                      # [1,5,7] denormalized
        ma_np = to_np(info_model["forward_inputs"]["model_action"])   # [1,320] raw
        chunk = acts_np  # [1,5,7]

        step_obs_list, rew, term, trunc, infos = env.chunk_step(chunk)
        # term/trunc are [1, chunk_len] torch tensors (per-step); final_obs = last step
        final_obs = step_obs_list[-1]
        term = bool(np.asarray(term.cpu() if hasattr(term, "cpu") else term).any())
        trunc = bool(np.asarray(trunc.cpu() if hasattr(trunc, "cpu") else trunc).any())
        for k, s_obs in enumerate(step_obs_list):
            step = ci * chunk_len + k
            img = to_np(s_obs["main_images"][0]) if hasattr(s_obs["main_images"], "__len__") else to_np(s_obs["main_images"])
            st = to_np(s_obs["states"][0]) if hasattr(s_obs["states"], "__len__") else to_np(s_obs["states"])
            rec = {
                "step": step,
                "chunk": ci,
                "img_mean": float(img.mean()), "img_nonblack": float((img.sum(axis=-1) > 10).mean()),
                "state": st[:7].tolist(),
                "exec_action": chunk[0, k].tolist(),          # what we asked env to run
                "denorm_action": chunk[0, k].tolist(),        # same (no extra transform in env)
                "model_action_first7": ma_np.reshape(-1)[k*7:(k+1)*7].tolist(),
            }
            records.append(rec)
        print(f"[loop] chunk {ci}: step {ci*chunk_len}-{ci*chunk_len+len(step_obs_list)-1} "
              f"term={term} trunc={trunc} img_mean={rec['img_mean']:.1f}", flush=True)
        final_term, final_trunc = term, trunc
        if term or trunc:
            print(f"[loop] episode done at step {ci*chunk_len + len(step_obs_list)-1}", flush=True)
            break

    env.close()

    # ---------------- audit ----------------
    acts_arr = np.array([r["exec_action"] for r in records])
    states = np.array([r["state"] for r in records])
    img_nonblack = np.array([r["img_nonblack"] for r in records])
    ma_arr = np.array([r["model_action_first7"] for r in records])

    eef_motion = float(np.abs(np.diff(states[:, :3], axis=0)).max()) if len(states) > 1 else 0.0
    audit = {
        "n_env_steps": len(records),
        "terminated": bool(final_term),
        "truncated": bool(final_trunc),
        "img_nonblack_mean": float(img_nonblack.mean()),
        "img_nonblack_min": float(img_nonblack.min()),
        "action_shape": list(acts_arr.shape),
        "action_nan": bool(np.isnan(acts_arr).any()),
        "action_inf": bool(np.isinf(acts_arr).any()),
        "action_minmax": [float(acts_arr.min()), float(acts_arr.max())],
        "action_abs_le1_frac": float((np.abs(acts_arr) <= 1.0).mean()),
        "model_action_nan": bool(np.isnan(ma_arr).any()),
        "model_action_inf": bool(np.isinf(ma_arr).any()),
        "model_action_minmax": [float(ma_arr.min()), float(ma_arr.max())],
        "eef_pos_motion_max": eef_motion,
        "state_nan": bool(np.isnan(states).any()),
        "state_minmax_per_dim": [float(states[:, i].min()) for i in range(7)],
    }
    print("\n================ AUDIT ================")
    for k, v in audit.items():
        print(f"  {k}: {v}")
    with open(OUT, "w") as f:
        json.dump({"audit": audit, "records": records}, f, indent=1)
    print(f"\n[loop] records -> {OUT}")

    ok = (len(records) >= 50 and img_nonblack.min() > 0.9
          and not audit["action_nan"] and not audit["action_inf"]
          and eef_motion > 1e-4)
    print(f"\n  LOOP OK: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
