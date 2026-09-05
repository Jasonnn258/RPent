"""Regenerate empty .pruned_init files for damaged LIBERO-PRO tasks.

libero_spatial_task t3 (on_the_cookie_box) and t7 (on_the_stove) shipped as
empty torch archives (valid ndarray, len 0) in the LIBERO-PRO download and the
pip-installed liberopro package -> benchmark reports init_states=0 -> make_env
raises ZeroDivisionError (seed % trials). The other 8 tasks have 50 states.

This follows the official generator (downloads/LIBERO-PRO/notebooks/
generate_init_states.py: build OffScreenRenderEnv once per state, snapshot
get_sim_state) but saves with torch.save to match the format the benchmark
loads (benchmark/__init__.py:get_task_init_states -> torch.load).

States are NEW random draws (the old host's exact states are unrecoverable:
archived states.json holds named obs dicts, not flat sim states). The saved
file is the artifact — generate once, never regenerate.

Usage (vla python, MUJOCO_GL=osmesa):
  python scripts/regen_init_states.py --suite libero_spatial_task \
      --tasks 3 7 --num-inits 50 --apply
"""
import argparse
import os
import shutil
import sys

import numpy as np

DOWNLOADS_SRC = "/vla_test/yjx/downloads/LIBERO-PRO/liberopro/liberopro"
SITE_PKG = os.path.join(os.path.dirname(
    __import__("importlib.util", fromlist=["util"]).find_spec("liberopro").origin
), "liberopro")
BACKUP_DIR = "/vla_test/yjx/rpent_data/init_state_backups"
SEED = 20260905


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="libero_spatial_task")
    ap.add_argument("--tasks", type=int, nargs="+", required=True)
    ap.add_argument("--num-inits", type=int, default=50)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--apply", action="store_true",
                    help="write into site-packages + source tree + backup dir")
    args = ap.parse_args()

    from liberopro.liberopro.envs import OffScreenRenderEnv
    from liberopro.liberopro.benchmark import get_benchmark

    bench = get_benchmark(args.suite)()
    site_pkg_dir = os.path.join(SITE_PKG, "init_files", args.suite)
    src_dir = os.path.join(DOWNLOADS_SRC, "init_files", args.suite)

    for t in args.tasks:
        task = bench.get_task(t)
        bddl = os.path.join(SITE_PKG, "bddl_files", args.suite, task.bddl_file)
        print(f"task {t}: {task.name}", flush=True)
        states = []
        for i in range(args.num_inits):
            np.random.seed(args.seed + t * 1000 + i)
            env = OffScreenRenderEnv(
                bddl_file_name=bddl, camera_heights=128, camera_widths=128)
            try:
                states.append(np.asarray(env.get_sim_state(), dtype=np.float64))
            finally:
                env.close()
        uniq = len({s.tobytes() for s in states})
        print(f"  sampled {len(states)} states, unique={uniq}", flush=True)
        if uniq < args.num_inits * 0.8:
            print("  ERROR: states not diverse — placement RNG not varying; abort")
            sys.exit(2)
        arr = np.array(states)
        out = f"/tmp/{task.name}.pruned_init"
        import torch
        torch.save(arr, out)
        # verify round-trip
        back = torch.load(out, weights_only=False)
        assert len(back) == args.num_inits and float(
            np.isclose(back[0], states[0]).all()) == 1.0
        print(f"  wrote {out} ({os.path.getsize(out)} bytes)", flush=True)

        if args.apply:
            for d in (site_pkg_dir, src_dir):
                dst = os.path.join(d, f"{task.name}.pruned_init")
                if os.path.exists(dst):
                    shutil.copy2(dst, dst + ".empty.bak")
                shutil.copy2(out, dst)
                print(f"  applied -> {dst}", flush=True)
            os.makedirs(BACKUP_DIR, exist_ok=True)
            shutil.copy2(out, os.path.join(BACKUP_DIR, f"{task.name}.pruned_init"))
            print(f"  backup -> {BACKUP_DIR}", flush=True)


if __name__ == "__main__":
    main()
