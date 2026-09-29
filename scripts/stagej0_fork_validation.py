#!/usr/bin/env python
"""Stage J0 — simulator 状态分叉验证 runner(预注册:analysis/stageJ0_prereg.md)。

对 stageJ0_fork_selection.json 冻结的 20 个 H1 fork 点逐个执行:
重放 prefix 1..T → snapshot S → A_hist×2 / A_vla×2(支间 restore_state(S))→
逐支记录可观测通道。产物:analysis/stageJ0_fork_results.jsonl(逐 fork 一行)。

设计要点(全部在预注册冻结):
- 共享一个 vla_server + sam3_server,每 fork 新起 env_server(同 task/seed
  与源 episode 一致,init state 确定性);
- 重放用 toolkit._step(全参数原文),自带 states.json 落盘;
- A_hist = 源 step T+1 command 原文;A_vla = pi0_pick(LAST_PICK_PROMPT
  [FG 加 OFFSET_SUFFIX], max_chunks=14, lift_thresh=0.05,
  gripper_closed_thresh=0.06);
- 判定/门不在本脚本:另由分析脚本按预注册 §3-§5 计算;
- 本脚本不调 planner、不调 GLM、不写任何 planner 可见文本。

用法:
  MUJOCO_GL=osmesa python scripts/stagej0_fork_validation.py \
      --gpu 0 [--limit 1] [--selection analysis/stageJ0_fork_selection.json]
"""
from __future__ import annotations

# 代理防火墙必须在任何 urllib/httpx 使用者 import 之前注入(本机
# http_proxy 会劫持 127.0.0.1 的 env/vla/sam3 RPC)。
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

OFFSET_SUFFIX = (
    " — grasp at a slightly offset point, about two centimeters "
    "to the side of the previous attempt"
)
RESULT_FIELDS = {  # 原语 result 中进入 J0 记录的标量/旗标(预注册 §3)
    "success", "peak_lift_m", "final_dist_m", "final_gripper_opening",
    "min_gripper_opening", "chunks_used", "max_chunks", "steps_used",
    "name", "target_xyz", "final_eef_pos",
}


def _channels(meas: dict) -> dict:
    """sim_measurement → 门控通道(EEF/夹爪/object-state;通道缺失记 None)。"""
    o = meas.get("obs") or {}
    obj = None
    for key in ("object-state", "object_state", "object_states"):
        if key in o:
            obj = [float(x) for x in o[key]]
            break
    return {
        "eef_pos": [float(x) for x in o.get("robot0_eef_pos", [])] or None,
        "gripper_qpos": [float(x) for x in o.get("robot0_gripper_qpos", [])] or None,
        "obj_state": obj,
        "meas_keys": sorted(o.keys()),
    }


def _result_subset(result: dict) -> dict:
    if not isinstance(result, dict):
        return {"value": str(result)[:200]}
    return {k: v for k, v in result.items() if k in RESULT_FIELDS}


def _jsonable(o):
    """numpy → python 递归转换(json 序列化兜底,防止单条记录丢整个 run)。"""
    import numpy as np

    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def _load_source_steps(episode_dir: str) -> list[dict]:
    steps = json.load(open(Path(episode_dir) / "states.json"))
    return sorted(steps, key=lambda s: s.get("step_idx", 0))


def _cmd_at(steps: list[dict], idx: int) -> dict | None:
    for s in steps:
        if s.get("step_idx") == idx and s.get("command"):
            return s["command"]
    return None


def _task_language(steps: list[dict]) -> str | None:
    for s in steps:
        if s.get("task_language"):
            return s["task_language"]
    return None


def _last_pick_prompt(steps: list[dict], T: int) -> str | None:
    """prefix 1..T 中最后一条 pi0_pick / pi0_doubled 的 prompt 全文(graph v1
    LAST_PICK_PROMPT 绑定;无则回退 task_language,由调用方处理)。"""
    prompt = None
    for s in steps:
        c = s.get("command") or {}
        if s.get("step_idx", 0) <= T and c.get("action") in ("pi0_pick", "pi0_doubled"):
            if isinstance(c.get("prompt"), str):
                prompt = c["prompt"]
    return prompt


def run_fork(fork: dict, gpu: int, shared_kwargs: dict, log_root: Path,
             keep_full_meas: bool) -> dict:
    """执行单个 fork 点,返回一行 J0 记录(异常 → infra_abort 记录)。"""
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    tag = (f"t{fork['task']}s{fork['seed']}{fork['arm']}T{fork['step_idx']}")
    outdir = log_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}"
    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)

    rec = {
        "fork_id": tag,
        "episode_dir": fork["episode_dir"],
        "task": fork["task"], "seed": fork["seed"], "arm": fork["arm"],
        "T": fork["step_idx"], "family": fork["family"],
        "ts": datetime.now().isoformat(timespec="seconds"),
        "infra_abort": None, "restores": [], "branches": [],
    }

    env_spec = get_env_spec("libero")
    args = argparse.Namespace(
        suite="libero_spatial", task=fork["task"], seed=fork["seed"],
        max_episode_steps=10000, cuda_device=gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None,
    )
    daemons: list = []
    toolkit = None
    try:
        # --- 重放底座:本 fork 专属 env_server + 共享 vla/sam3 -----------
        env_daemons, env_kwargs = env_spec.init_task_runtime(
            args, outdir, NullDashboardEventSink())
        daemons.extend(env_daemons)
        primitives_kwargs = dict(env_kwargs)
        primitives_kwargs.update(shared_kwargs)  # model / sam3_client
        toolkit = get_toolkit(
            "libero", primitives_kwargs=primitives_kwargs,
            video_path=str(outdir / "episode.mp4"),
            dashboard_events=NullDashboardEventSink())
        prims = toolkit._primitives
        env = prims.env

        steps = _load_source_steps(fork["episode_dir"])
        T = fork["step_idx"]
        a_hist = _cmd_at(steps, T + 1)
        assert a_hist is not None, "selection 已保证 T+1 command 存在"
        rec["a_hist"] = a_hist

        # A_vla 参数(graph v1:LAST_PICK_PROMPT,FG 加 OFFSET_SUFFIX)
        base_prompt = _last_pick_prompt(steps, T) or _task_language(steps) or ""
        if fork["family"] == "FALSE_GRASP":
            base_prompt = base_prompt + OFFSET_SUFFIX
        a_vla = {"action": "pi0_pick", "prompt": base_prompt,
                 "max_chunks": 14, "lift_thresh": 0.05,
                 "gripper_closed_thresh": 0.06}
        rec["a_vla"] = {k: v for k, v in a_vla.items() if k != "action"}
        rec["prompt_source"] = ("last_pick" if _last_pick_prompt(steps, T)
                                else "task_language")

        # --- 重放 prefix 1..T ---------------------------------------------
        t0 = time.time()
        for s in steps:
            idx, cmd = s.get("step_idx"), s.get("command")
            if idx is None or not cmd or not (1 <= idx <= T):
                continue
            kwargs = {k: v for k, v in cmd.items() if k != "action"}
            toolkit._step(cmd["action"], **kwargs)
        rec["replay"] = {"n_steps": T, "elapsed_s": round(time.time() - t0, 1)}

        # --- snapshot + baseline 测量 -------------------------------------
        S = env.save_state()
        rec["snapshot_state_len"] = int(len(S))
        base_meas = env.sim_measurement()
        base_ch = _channels(base_meas)
        rec["baseline"] = {
            **base_ch,
            "check_success": bool(env.check_success()),
            "obj_of_interest": base_meas.get("obj_of_interest"),
            "obs_full": base_ch["meas_keys"] if not keep_full_meas else _jsonable(
                base_meas["obs"]),
        }

        def _exec(tag_i: str, action: str, kwargs: dict) -> None:
            t1 = time.time()
            try:
                toolkit._step(action, **kwargs)
                # 原语 result 从本 fork states.json 尾记录读取(全参数已落盘)
                sj = json.load(open(outdir / "states.json"))
                result = _result_subset((sj[-1] or {}).get("result") or {})
                err = None
            except Exception as exc:  # 原语异常 ≠ 分叉判定,记 ERROR 支
                result, err = {}, f"{type(exc).__name__}: {exc}"[:300]
            meas = {}
            try:
                meas = _channels(env.sim_measurement())
                succ = bool(env.check_success())
                state_post_len = int(len(env.save_state()))
            except Exception as exc:
                meas, succ, state_post_len = {}, None, -1
                err = err or f"{type(exc).__name__}: {exc}"[:300]
            rec["branches"].append({
                "tag": tag_i, "action": action,
                "result": result, "error": err,
                "eef_pos": meas.get("eef_pos"), "gripper_qpos": meas.get("gripper_qpos"),
                "obj_state": meas.get("obj_state"),
                "check_success": succ,
                "state_post_len": state_post_len,
                "elapsed_s": round(time.time() - t1, 1),
            })

        # --- 四支:hist×2 → vla×2(支间 restore + 读回校验)---------------
        hist_kwargs = {k: v for k, v in a_hist.items() if k != "action"}
        _exec("hist1", a_hist["action"], hist_kwargs)
        for tag_i, action, kw in (
            ("hist2", a_hist["action"], hist_kwargs),
            ("vla1", "pi0_pick", {k: v for k, v in a_vla.items() if k != "action"}),
            ("vla2", "pi0_pick", {k: v for k, v in a_vla.items() if k != "action"}),
        ):
            obs = env.restore_state(S)
            prims.set_obs(obs)
            readback = env.save_state()
            rec["restores"].append({
                "before": tag_i,
                "readback_max_abs_diff": float(
                    abs(readback - S).max()) if len(readback) == len(S) else -1.0,
            })
            _exec(tag_i, action, kw)
    except Exception as exc:
        rec["infra_abort"] = {
            "reason": f"{type(exc).__name__}: {exc}"[:400],
            "traceback": traceback.format_exc()[-1500:],
        }
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
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection", default="analysis/stageJ0_fork_selection.json")
    ap.add_argument("--out", default="analysis/stageJ0_fork_results.jsonl")
    ap.add_argument("--log-root", default="logs/stageJ0")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None,
                    help="只跑前 N 个 fork(冒烟用;全量运行禁止)")
    ap.add_argument("--skip", type=int, default=0, help="跳过前 N 个(断点续跑)")
    args = ap.parse_args()

    selection = json.load(open(REPO / args.selection))
    forks = selection[args.skip:] if args.skip else selection
    if args.limit:
        forks = forks[: args.limit]
    log_root = REPO / args.log_root
    log_root.mkdir(parents=True, exist_ok=True)
    out_path = REPO / args.out

    # loopback 代理放行后才能 import RPC 层
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = log_root / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)

    # 共享 vla + sam3(J0 全程一份;env 每 fork 新起)
    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    print(f"[stageJ0] boot shared vla+sam3 on gpu{args.gpu} ...", flush=True)
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())
    print(f"[stageJ0] shared runtime ready: {sorted(shared_kwargs)}", flush=True)

    n_ok = n_abort = 0
    try:
        with open(out_path, "a") as f:
            for i, fork in enumerate(forks):
                print(f"[stageJ0] fork {i+1}/{len(forks)} "
                      f"t{fork['task']}s{fork['seed']}{fork['arm']} "
                      f"T={fork['step_idx']} {fork['family']} ...", flush=True)
                t0 = time.time()
                rec = run_fork(fork, args.gpu, shared_kwargs, log_root,
                               keep_full_meas=(n_ok + n_abort) == 0)
                rec["wall_s"] = round(time.time() - t0, 1)
                try:
                    line = json.dumps(rec, ensure_ascii=False, default=str)
                except Exception as exc:  # 序列化失败也不能丢 run
                    line = json.dumps({
                        "fork_id": rec.get("fork_id"),
                        "infra_abort": {"reason": f"serialize: {exc}"},
                        "salvaged_keys": sorted(rec.keys()),
                    }, ensure_ascii=False)
                f.write(line + "\n")
                f.flush()
                if rec["infra_abort"]:
                    n_abort += 1
                    print(f"[stageJ0]   INFRA_ABORT {rec['infra_abort']['reason'][:120]}"
                          f" ({rec['wall_s']}s)", flush=True)
                else:
                    n_ok += 1
                    rb = [r["readback_max_abs_diff"] for r in rec["restores"]]
                    print(f"[stageJ0]   ok ({rec['wall_s']}s) restores={len(rb)} "
                          f"readback_max={max(rb) if rb else None}", flush=True)
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    print(f"[stageJ0] done: ok={n_ok} infra_abort={n_abort} -> {out_path}",
          flush=True)
    return 0


if __name__ == "__main__":
    __import__("os").environ.setdefault("MUJOCO_GL", "osmesa")
    raise SystemExit(main())
