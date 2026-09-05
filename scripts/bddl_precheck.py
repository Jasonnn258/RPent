"""Held-out task bddl/init integrity precheck (one reset per task, no VLA/SAM3).

Usage (vla python):
  python scripts/bddl_precheck.py --suite libero_spatial_task --tasks 0 1 4 7 8 9

Exits non-zero if any task fails to build/reset. t3 historically corrupted in
libero_spatial_task — run before scheduling held-out episodes.
"""
import argparse
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="libero_spatial_task")
    ap.add_argument("--tasks", type=int, nargs="+", default=[0, 1, 4, 7, 8, 9])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cuda-device", type=int, default=0)
    args = ap.parse_args()

    os.environ.setdefault("MUJOCO_GL", "egl")
    os.environ.pop("CUDA_VISIBLE_DEVICES", None)
    if os.environ["MUJOCO_GL"] == "egl":
        from rpent.utils.egl import configure_egl_device
        configure_egl_device(args.cuda_device)
    else:
        # osmesa / glfw platforms must not touch the egl device mapper (and
        # must not import mujoco before robots.libero.env_server does).
        os.environ.pop("MUJOCO_EGL_DEVICE_ID", None)

    from robots.libero.env_server import make_env

    failures = []
    for t in args.tasks:
        env = None
        try:
            env = make_env(t, args.seed, suite_name=args.suite,
                           max_episode_steps=10000)
            obs, info = env.reset()
            assert obs is not None
            print(f"t{t}: OK", flush=True)
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"t{t}: FAIL {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            failures.append(t)
        finally:
            if env is not None:
                try:
                    env.close()
                except Exception:  # noqa: BLE001
                    pass
    print(f"summary: {len(args.tasks) - len(failures)}/{len(args.tasks)} OK"
          + (f", failed={failures}" if failures else ""), flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
