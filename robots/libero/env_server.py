"""RPC server wrapping a single-env LIBERO environment."""
from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, Any

import numpy as np
from omegaconf import OmegaConf

from rpent.utils.config import (
    get_repo_root,
    get_rlinf_repo_path,
)
from rpent.utils.logging import get_logger
from rpent.utils.rpc import RpcFacade

# MuJoCo env vars must be set BEFORE importing anything that touches MuJoCo.
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
assert "mujoco" not in sys.modules, \
    "mujoco must not be imported before MUJOCO_GL/PYOPENGL_PLATFORM are set"

logger = get_logger("env_server")

RPENT_ROOT = get_repo_root()
RLINF_REPO_PATH = get_rlinf_repo_path() or (RPENT_ROOT.parent / "rlinf").resolve()
if str(RLINF_REPO_PATH) not in sys.path:
    sys.path.insert(0, str(RLINF_REPO_PATH))
os.environ.setdefault("ROBOT_PLATFORM", "LIBERO")

# torch and LiberoEnv are only imported at call time (after --cuda-device
# sets CUDA_VISIBLE_DEVICES in main()); LiberoEnv transitively imports torch.
if TYPE_CHECKING:
    import torch  # noqa: F401  (referenced at runtime in _to_numpy_tree)
    from rlinf.envs.libero.libero_env import LiberoEnv


# ---------------------------------------------------------------------------
# Config builders
# ---------------------------------------------------------------------------


def build_env_cfg(
    *,
    task_suite_name: str = "libero_spatial",
    specific_reset_id: int = 0,
    seed: int = 0,
    max_episode_steps: int = 10000,
) -> Any:
    cfg = OmegaConf.create(
        {
            "env_type": "libero",
            "task_suite_name": task_suite_name,
            "auto_reset": False,
            "ignore_terminations": False,
            "max_steps_per_rollout_epoch": max_episode_steps,
            "max_episode_steps": max_episode_steps,
            "use_rel_reward": False,
            "use_step_penalty": False,
            "reward_coef": 1.0,
            "reset_gripper_open": True,
            "is_eval": True,
            "seed": seed,
            "group_size": 1,
            "use_fixed_reset_state_ids": True,
            "use_ordered_reset_state_ids": True,
            "specific_reset_id": specific_reset_id,
            "video_cfg": {
                "save_video": True,
                "info_on_video": True,
                "video_base_dir": "/tmp/primitive_videos",
            },
            "init_params": {
                "camera_heights": 256,
                "camera_widths": 256,
                # Render depth too, so we can back-project pixels to world
                # from depth + camera calibration
                "camera_depths": True,
                "horizon": max_episode_steps,
                **({"robots": [os.environ["LIBERO_ROBOT_BASE"]]}
                   if os.environ.get("LIBERO_ROBOT_BASE") else {}),
            },
        }
    )
    return cfg


def make_env(task_id: int, seed: int, suite_name: str = "libero_spatial",
             max_episode_steps: int = 10000) -> LiberoEnv:
    """Build a single-env LiberoEnv pinned to ``task_id`` / ``seed``."""
    from rlinf.envs.libero.libero_env import LiberoEnv
    from rlinf.envs.libero.utils import benchmark as _bench_mod
    suite = _bench_mod.get_benchmark(suite_name)()
    first_id = sum(len(suite.get_task_init_states(t)) for t in range(task_id))
    trials = len(suite.get_task_init_states(task_id))
    rid = first_id + (seed % trials)
    cfg = build_env_cfg(
        task_suite_name=suite_name,
        specific_reset_id=rid,
        seed=seed,
        max_episode_steps=max_episode_steps,
    )
    return LiberoEnv(cfg=cfg, num_envs=1, seed_offset=0,
                     total_num_processes=1, worker_info=None)


# ---------------------------------------------------------------------------
# Facade implementing the robots.libero.env_client protocol
# ---------------------------------------------------------------------------


def _to_numpy_tree(x):
    """Recursively convert torch tensors to CPU numpy arrays so the result
    pickles cleanly across the agent/env_server wire."""
    import torch

    if isinstance(x, torch.Tensor):
        return x.detach().cpu().numpy()
    if isinstance(x, dict):
        return {k: _to_numpy_tree(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_to_numpy_tree(v) for v in x]
    if isinstance(x, tuple):
        return tuple(_to_numpy_tree(v) for v in x)
    return x


class LiberoEnvFacade(RpcFacade):
    """Implements :class:`robots.libero.env_client.LiberoEnvClient`
    over :class:`rlinf.envs.libero.libero_env.LiberoEnv`.

    All return values are converted to CPU numpy so the agent process
    (which does not import torch) can consume them after the pickle round
    trip.
    """

    def __init__(self, env: LiberoEnv, *, meta: dict):
        super().__init__()
        self._env = env
        self._env_idx = 0
        self._done = False
        # P1-DEV1A 只读审计:reset 后累计的 env step 数(G2 零步进证明用)
        self._step_count = 0
        # Identifies what task/seed this server was launched with — the
        # client compares against its own expected values at construction
        # and refuses to talk to a stale or mis-configured server.
        self._meta = dict(meta)

    def _dispatch(self, method: str, args: tuple, kwargs: dict) -> Any:
        if method.startswith("env."):
            attr = method[len("env."):]
            try:
                return getattr(self, attr)(*args, **kwargs)
            except Exception as e:
                logger.warning("run method %s failed: %s", method, e)
                raise e
        raise ValueError(f"unknown RPC method: {method!r}")

    # ---- shape helpers ----

    def _strip(self, v):
        """Drop the leading env dim. ``v`` is either a batched numpy array
        (shape ``[B, ...]``), a length-B list (e.g. ``task_descriptions``),
        or ``None`` (optional images). LiberoEnv runs ``num_envs=1`` so
        index ``self._env_idx`` is always present."""
        if v is None:
            return None
        return v[self._env_idx]

    def _strip_obs(self, obs: dict) -> dict:
        """Strip the leading env dim from every value of a LIBERO obs dict."""
        return {k: self._strip(v) for k, v in obs.items()}

    def _expand_action(self, action) -> np.ndarray:
        """Inject the env dim onto a single-env action shaped ``[action_dim]``."""
        return np.asarray(action)[None]

    def _expand_chunk(self, actions) -> np.ndarray:
        """Inject the env dim onto a single-env chunk shaped
        ``[chunk_size, action_dim]``."""
        return np.asarray(actions)[None]

    def _record_done(self, *signals: Any) -> None:
        """OR the truthiness of every termination/truncation signal into
        ``self._done`` so subsequent step() calls short-circuit."""
        for s in signals:
            if np.asarray(s).any():
                self._done = True
                return

    # ---- gym-like surface ----

    def reset(self):
        obs, info = self._env.reset()
        obs = self._strip_obs(_to_numpy_tree(obs))
        self._done = False
        self._step_count = 0
        return obs, _to_numpy_tree(info)

    def step(self, action):
        assert not self._done, "step called after episode done"
        obs, rew, term, trunc, info = self._env.step(self._expand_action(action))
        self._step_count += 1
        obs = self._strip_obs(_to_numpy_tree(obs))
        term = self._strip(_to_numpy_tree(term))
        trunc = self._strip(_to_numpy_tree(trunc))
        self._record_done(term, trunc)
        return (
            obs,
            self._strip(_to_numpy_tree(rew)),
            term,
            trunc,
            _to_numpy_tree(info),
        )

    def chunk_step(self, actions, *, return_all_frames: bool = False):
        """Run a full action chunk in one RPC. ``actions`` shape
        ``[chunk_size, action_dim]`` (single env).

        Returns the 5-positional tuple
        ``(obs_or_list, reward, terminated, truncated, info)``. ``obs`` is
        ``list[Obs]`` when ``return_all_frames=True`` (full per-step
        trajectory), or just the final ``Obs`` dict when False (default).
        ``terminated`` / ``truncated`` carry shape ``[chunk_size]`` after
        the leading env dim is stripped — the agent reduces across the
        chunk itself.
        """
        assert not self._done, "chunk_step called after episode done"
        obs_list, rew, term, trunc, info = self._env.chunk_step(
            self._expand_chunk(actions)
        )
        self._step_count += len(actions)
        obs_list = [self._strip_obs(_to_numpy_tree(o)) for o in obs_list]
        term = self._strip(_to_numpy_tree(term))
        trunc = self._strip(_to_numpy_tree(trunc))
        self._record_done(term, trunc)
        obs_field = obs_list if return_all_frames else obs_list[-1]
        return (
            obs_field,
            self._strip(_to_numpy_tree(rew)),
            term,
            trunc,
            _to_numpy_tree(info),
        )

    def raw_obs(self) -> dict:
        return _to_numpy_tree(self._env.current_raw_obs[self._env_idx])

    # ---- Stage J0/J1:sim 状态快照、恢复与测量通道 ------------------------
    # 全部为纯新增的只读/状态搬运方法,不触碰 task dynamics(不动 reward、
    # termination 逻辑与控制频率)。链条:rlinf LiberoEnv →
    # ReconfigureSubprocEnv → workers[0] 子进程(env_wrapper 层实现
    # get_sim_state / set_init_state / check_success)。

    def _worker(self):
        """单 env worker 的父进程侧句柄(子进程内是 libero ControlEnv)。"""
        return self._env.env.workers[0]

    def save_state(self) -> np.ndarray:
        """MuJoCo flatten 状态快照(qpos/qvel/act/time,含全部物体位姿)。"""
        return np.asarray(self._worker().get_sim_state())

    def restore_state(self, flat) -> dict:
        """恢复 :meth:`save_state` 的快照并重生成观测。

        worker 侧走 env_wrapper ``set_init_state`` = regenerate_obs_from_state
        (set_state_from_flattened + sim.forward + check_success +
        post_process + update_observables),返回单 env 的 raw obs;这里镜像
        :meth:`rlinf...LiberoEnv.reset` 的做法:同步 ``current_raw_obs``
        缓存后过 ``_wrap_obs``,让调用方拿到与 step/reset 同构的观测
        (main_images/wrist_images/states/task_descriptions)。恢复语义是
        "回退到集中态",因此同时解除本 facade 的终止闩(auto_reset=False,
        不会触发重置)。
        """
        obs_raw = self._worker().set_init_state(np.asarray(flat))
        self._env.current_raw_obs[self._env_idx] = obs_raw
        wrapped = self._env._wrap_obs(self._env.current_raw_obs)
        self._done = False
        return self._strip_obs(_to_numpy_tree(wrapped))

    def check_success(self) -> bool:
        """当前 sim 状态下的 LIBERO 任务谓词(零步进只读探测)。"""
        return bool(self._worker().check_success())

    def sim_measurement(self) -> dict:
        """sim 级测量通道(科学仪器,只用于离线结局分类,绝不进入任何
        planner/router 可见文本)。返回 robosuite 低维状态观测(含
        ``object-state`` 物体位姿向量;图像键被丢弃以减小 RPC 载荷)+
        任务关注对象名列表。"""
        w = self._worker()
        obs = w.env_call("_get_observations", target="robosuite")
        keep = {}
        for k, v in _to_numpy_tree(obs).items():
            try:
                ndim = np.asarray(v).ndim
            except Exception:
                continue
            if ndim <= 1:  # 只保留低维状态向量(EEF/夹爪/object-state)
                keep[k] = v
        return {
            "obs": keep,
            "obj_of_interest": w.get_env_attr("obj_of_interest"),
        }

    def get_env_meta(self) -> dict:
        """Return the meta info this server was launched with. """
        return dict(self._meta)

    # ---- P1-DEV1A(D-041):audit-only 只读接触快照 ------------------------

    def contact_snapshot(self, spec: dict) -> dict:
        """DEV1A 同刻接触快照:零 env step,只读真实 MuJoCo contact pairs。

        证据链:worker 单线程串行处理本 RPC 序列,期间不存在 step 命令,
        因此 sim 状态不可变 —— 以 query 前后两次 ``get_sim_state`` 的
        sha256 相等(``same_tick``)与 ``server_step_count`` 不变作证。
        接触真值只来自 ``robosuite check_contact``(内部扫描
        ``sim.data.contact``,geom 名匹配);**绝不**用 gap/最近表面距离/
        目标距离伪造接触标签。分组布尔先粗查,真实对再用单×单细分
        (分治剪枝),返回的 ``pairs`` 每一对都对应 sim.data.contact 中
        至少一条真实接触记录。未知/解析失败一律留给上游判 UNKNOWN。
        """
        import hashlib
        import time as _time

        t0 = _time.monotonic()
        w = self._worker()
        step_mark = self._step_count
        queries = 0

        def cc(g1, g2=None):
            nonlocal queries
            queries += 1
            args = [list(g1)] if g2 is None else [list(g1), list(g2)]
            return bool(w.env_call("check_contact", args=args,
                                   target="robosuite"))

        state_pre = np.asarray(w.get_sim_state())

        # 低维观测(与 sim_measurement 同通道;不含图像,减小载荷)
        obs_full = _to_numpy_tree(
            w.env_call("_get_observations", target="robosuite"))
        target = spec["target"]
        keep_keys = ("robot0_eef_pos", "robot0_eef_quat",
                     "robot0_gripper_qpos", f"{target}_pos")
        obs = {k: [float(x) for x in np.atleast_1d(obs_full[k])]
               for k in keep_keys if k in obs_full}

        tgt = list(spec["target_geoms"])
        lf = list(spec["left_finger_geoms"])
        rf = list(spec["right_finger_geoms"])
        sup = list(spec["support_geoms"])
        rself = list(spec["robot_self_geoms"])

        flags = {
            "left_x_target": cc(lf, tgt),
            "right_x_target": cc(rf, tgt),
            "target_x_support": cc(tgt, sup),
            "left_x_robotself": cc(lf, rself),
            "right_x_robotself": cc(rf, rself),
            "left_x_any": cc(lf),
            "right_x_any": cc(rf),
            "target_x_any": cc(tgt),
        }

        def refine(a: list, b: list) -> list:
            """分治细化真实接触 geom 名对(每次递归先粗查剪枝)。"""
            if not a or not b or not cc(a, b):
                return []
            if len(a) == 1 and len(b) == 1:
                return [(a[0], b[0])]
            if len(a) >= len(b):
                mid = len(a) // 2
                return refine(a[:mid], b) + refine(a[mid:], b)
            mid = len(b) // 2
            return refine(a, b[:mid]) + refine(a, b[mid:])

        pairs: list = []
        if flags["left_x_target"]:
            pairs += refine(lf, tgt)
        if flags["right_x_target"]:
            pairs += refine(rf, tgt)
        if flags["target_x_support"]:
            pairs += refine(tgt, sup)
        if flags["left_x_robotself"]:
            pairs += refine(lf, rself)
        if flags["right_x_robotself"]:
            pairs += refine(rf, rself)
        # 去重(同一 geom 对可能被多组重复发现)
        pairs = sorted(set(tuple(sorted(p)) for p in pairs))
        truncated = len(pairs) > 512
        if truncated:
            pairs = pairs[:512]

        state_post = np.asarray(w.get_sim_state())
        sha = lambda a: hashlib.sha256(np.asarray(a).tobytes()).hexdigest()
        return {
            "target": target,
            "obs": obs,
            "flags": flags,
            "pairs": [list(p) for p in pairs],
            "pairs_truncated": truncated,
            "server_step_count": int(self._step_count),
            "step_mark_unchanged": int(self._step_count) == int(step_mark),
            "state_sha256": sha(state_pre),
            "same_tick": bool(
                np.array_equal(state_pre, state_post)),
            "wall_ms": round((_time.monotonic() - t0) * 1000.0, 2),
            "queries": queries,
        }

    def render_camera(
        self,
        camera_name: str = "agentview",
        height: int = 1024,
        width: int = 1024,
        depth: bool = False,
    ):
        return _to_numpy_tree(
            self._env.render_camera(
                camera_name=camera_name,
                height=height,
                width=width,
                depth=depth,
            )
        )

    def get_camera_meta(
        self,
        camera_name: str = "agentview",
        height: int = 256,
        width: int = 256,
    ) -> dict | None:
        return _to_numpy_tree(
            self._env.get_camera_meta(
                camera_name=camera_name, height=height, width=width
            )
        )

    def get_task_language(self) -> str | None:
        return self._env.task_descriptions[self._env_idx]

    def cached_image(self) -> np.ndarray | None:
        cached = getattr(self._env, "_cached_full_image", None)
        if cached is None:
            return None
        return cached.cpu().numpy() if hasattr(cached, "cpu") else np.asarray(cached)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--transport", choices=["socket", "http"], default="http")
    p.add_argument("--host", type=str, default="127.0.0.1")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--suite", type=str, default="libero_spatial")
    p.add_argument("--task", type=int, default=9)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-episode-steps", type=int, default=10000)
    p.add_argument("--parent-watch", action="store_true",
                   help="watch parent process via stdin pipe and exit when it dies")
    p.add_argument("--cuda-device", type=int, default=None,
                   help="GPU device to pin MuJoCo EGL rendering and the torch "
                        "default device to (physical CUDA ordinal).")
    args = p.parse_args()

    if args.cuda_device is not None:
        # Deliberately do NOT set CUDA_VISIBLE_DEVICES. robosuite (imported
        # transitively via libero) asserts at import time that
        # ``MUJOCO_EGL_DEVICE_ID in CUDA_VISIBLE_DEVICES`` (substring check),
        # which assumes the EGL index equals the CUDA ordinal and crashes on
        # multi-GPU boxes where the EGL order differs. That assertion is gated
        # on ``CUDA_VISIBLE_DEVICES != ""``, so leaving it unset skips it in
        # both this process and the multiprocessing-spawned render workers
        # (which inherit the env). Pin the two backends directly instead:
        #   - MuJoCo render device <- MUJOCO_EGL_DEVICE_ID (configure_egl_device)
        #   - torch default device  <- torch.cuda.set_device(N)
        prev = os.environ.get("CUDA_VISIBLE_DEVICES")
        if prev is not None:
            logger.warning(
                "CUDA_VISIBLE_DEVICES=%s is set; clearing it and pinning via "
                "MUJOCO_EGL_DEVICE_ID + torch.cuda.set_device(--cuda-device=%s) "
                "instead (robosuite's CVD assertion is incompatible with EGL<->CUDA mapping)",
                prev, args.cuda_device,
            )
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        from rpent.utils.egl import configure_egl_device
        configure_egl_device(args.cuda_device)
        import torch
        torch.cuda.set_device(args.cuda_device)

    raw_env = make_env(args.task, args.seed, suite_name=args.suite,
                       max_episode_steps=args.max_episode_steps)
    facade = LiberoEnvFacade(
        raw_env,
        meta={
            "suite": args.suite,
            "task": args.task,
            "seed": args.seed,
            "max_episode_steps": args.max_episode_steps,
        },
    )
    facade.serve(transport=args.transport, host=args.host, port=args.port,
                 parent_watch=args.parent_watch)


if __name__ == "__main__":
    main()
