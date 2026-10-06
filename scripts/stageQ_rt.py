#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage Q 共享运行时:同 boot 成对 S_pre/S_post、状态捕获、双契约标签、
hold-through continuation、cell 执行。

预注册:analysis/stageQ_prereg.md §2(双契约)/§3(Q0-A)/§5(Q0-C)/
§8(factorial)/§9(hold-through)。本模块只实现冻结内容,不做任何判定。

关键事实(沿用 Stage O/P):
- transcript 一个 step = 一个完整闭环技能(pi0_pick 一步 = ≤24 chunk 技能,
  result 含 chunks_used)→ S_pre = 重放 1..t0−1、S_post = 执行 t0 之后;
- 重放含 Pi0.5 技能 → 必然重采样(J0 冻结),跨 boot 逐位不可达;
  措辞纪律:OBSERVABLY MATCHED RESTORED STATE(prereg §1);
- Pi0.5 seed 不可注入 → 随机性由 R 次重复吸收。

被复用:stageQ0.py(Q0-A/B/C)/ stageQ_freeze.py / stageQ1_factorial.py。
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt           # boot/restore/measure/契约/环境三件套
import stageP_rt as prt          # candidate 采样/chunk 执行/checkpoint/标签

# ---- 冻结常量(prereg §2/§8)------------------------------------------------
R_Q = 2                          # continuation 重复数(Q1 cell 与 Q0-C 双臂)
HOLD_MIN_POINTS = 4              # STABLE 窗口下限(DEV 期可修订,TEST 前冻结)
FG_LIFT_DZ = prt.FG_LIFT_DZ      # 0.03(复用 Stage P verifier 参数)
FG_FOLLOW_DXY = prt.FG_FOLLOW_DXY  # 0.10


def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


# ---- Q0-A:同 boot 成对 S_pre / S_post ---------------------------------------
def replay_prefix(toolkit, steps: list[dict], upto: int) -> None:
    """重放 1..upto(Stage O boot 重放逐字;infra 异常向上抛)。"""
    for s in steps:
        idx, cmd = s.get("step_idx"), s.get("command")
        if idx is None or not cmd or not (1 <= idx <= upto):
            continue
        kwargs = {k: v for k, v in cmd.items() if k != "action"}
        try:
            toolkit._step(cmd["action"], **kwargs)
        except Exception as exc:
            raise rt.InfraError(f"replay step {idx} {cmd['action']}: "
                                f"{type(exc).__name__}: {exc}") from exc


def read_step_result(outdir: Path, step_idx: int) -> dict:
    """从 outdir/states.json 读某 step 的 result(dev-O5 守卫同款)。"""
    recs = json.load(open(outdir / "states.json"))
    rec = next((s for s in reversed(recs)
                if s.get("command") and s.get("step_idx") == step_idx), None)
    return (rec or {}).get("result") or {}


def boot_to_pre(snap: dict, gpu: int, shared_kwargs: dict, outdir: Path):
    """起 env + 重放 1..t0−1 → S_pre(失败技能首次物理执行前)。

    返回 ctx(同 Stage O boot_snapshot 结构,S = S_pre)。t0=1 结构排除由
    调用方(采集/冻结层)负责,这里只断言 t0≥2。
    """
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    t0i = int(snap["t0"])
    assert t0i >= 2, f"{snap.get('snapshot_id')}: t0=1 无 pre-state"
    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)
    env_spec = get_env_spec("libero")
    args = argparse_ns(snap, gpu)
    env_daemons, env_kwargs = env_spec.init_task_runtime(
        args, outdir, NullDashboardEventSink())
    primitives_kwargs = dict(env_kwargs)
    primitives_kwargs.update(shared_kwargs)
    toolkit = get_toolkit(
        "libero", primitives_kwargs=primitives_kwargs,
        video_path=str(outdir / "episode.mp4"),
        dashboard_events=NullDashboardEventSink())
    prims = toolkit._primitives
    env = prims.env

    steps = rt.load_steps(snap["episode_dir"])
    replay_prefix(toolkit, steps, t0i - 1)          # 1..t0−1(不含失败 pick)
    S_pre = env.save_state()
    base = rt.measure(env)
    if base["check_success"]:
        raise rt.InfraError("S_pre base check_success True — trivial")
    if base["eef"] is None:
        raise rt.InfraError("S_pre eef missing")
    target = (base["meas"].get("obj_of_interest") or [""])[0]
    return {"toolkit": toolkit, "prims": prims, "env": env, "S": S_pre,
            "daemons": env_daemons, "outdir": outdir, "base": base,
            "target": target or None, "steps": steps,
            "state_hash": rt.state_hash(S_pre), "note": "S_pre"}


def argparse_ns(snap, gpu):
    import argparse
    return argparse.Namespace(
        suite="libero_spatial", task=int(snap["task"]), seed=int(snap["seed"]),
        max_episode_steps=10000, cuda_device=gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None)


def run_fail_pick(ctx: dict, snap: dict) -> str:
    """执行 step t0 原命令(重采样的失败 pick)→ 守卫必须仍为 FG。

    返回 S_post(save_state 字节);守卫违反 → InfraError(调用方重试)。
    t0 记录以轮询方式读回(dump_state 同步追加;多 worker 下
    get_output_dir 为全局量,由调用方 BOOT_LOCK 串行化 boot 相)。
    """
    t0i = int(snap["t0"])
    t0_step = next(s for s in ctx["steps"]
                   if s.get("step_idx") == t0i and s.get("command"))
    cmd = t0_step["command"]
    kwargs = {k: v for k, v in cmd.items() if k != "action"}
    try:
        ctx["toolkit"]._step(cmd["action"], **kwargs)
    except Exception as exc:
        raise rt.InfraError(f"fail-pick step {t0i}: "
                            f"{type(exc).__name__}: {exc}") from exc
    res = None
    for _ in range(20):                     # 轮询 ≤5s 等 t0 记录落盘
        try:
            res = read_step_result(ctx["outdir"], t0i)
        except (OSError, ValueError):
            res = {}
        if res:
            break
        time.sleep(0.25)
    if not res:
        raise rt.InfraError(f"fail-pick t0 record not found (poll 5s)")
    if snap.get("family") == "FALSE_GRASP" and res.get("success") is True:
        raise rt.InfraError("replayed t0 pick succeeded — FG event not "
                            "reproduced")
    S_post = ctx["env"].save_state()
    return S_post


# ---- 状态捕获(Q0-A;全字段,接口不可读处记 not_available)------------------
def capture_state(ctx: dict, S, tag: str) -> dict:
    """§3 冻结字段:sim_measurement 全部低维 obs 向量 + gripper +
    check_success + target + state sha16/len + 捕获时刻。"""
    m = rt.measure(ctx["env"])
    return {
        "tag": tag, "obs": {k: [float(x) for x in np.atleast_1d(v)]
                            for k, v in (m["obs"] or {}).items()},
        "eef": m["eef"], "pos": m["pos"],
        "gripper": prt.gripper_now(ctx["prims"]),
        "check_success": m["check_success"], "terminated": m["terminated"],
        "target": ctx.get("target"),
        "state_len": int(len(S)), "state_sha16": rt.state_hash(S),
    }


def flatten_delta(S_pre, S_post) -> dict:
    """S_pre vs S_post 原始 flatten 向量 per-index 统计(描述性)。"""
    a, b = np.asarray(S_pre, dtype=np.float64), np.asarray(S_post,
                                                           dtype=np.float64)
    if a.shape != b.shape:
        return {"shape_mismatch": f"{a.shape}!={b.shape}"}
    d = b - a
    return {"n_index": int(d.size),
            "n_changed": int(np.count_nonzero(np.abs(d) > 0)),
            "n_changed_gt_1e-6": int(np.count_nonzero(np.abs(d) > 1e-6)),
            "max_abs": float(np.abs(d).max()),
            "l2": float(np.linalg.norm(d))}


# ---- hold-through continuation(prereg §9;Stage P 唯一差异=禁早停锁)-------
def run_continuation_hold(prims, prompt: str, chunks_already: int = 1,
                          max_chunks: int = prt.PICK_MAX_CHUNKS,
                          on_chunk=None) -> dict:
    start_z = prims._last_obs_eef_z
    min_z = start_z
    post_min_peak_z = start_z
    min_grip = last_grip = prims._last_obs_gripper
    chunks_used = 0
    success = False
    for c in range(max_chunks - chunks_already):
        prims._vlm_chunk(prompt)
        chunks_used = c + 1
        if on_chunk is not None:
            on_chunk(c + 1)
        z, grip = prims._last_obs_eef_z, prims._last_obs_gripper
        if z < min_z:
            min_z, post_min_peak_z = z, z
        else:
            post_min_peak_z = max(post_min_peak_z, z)
        min_grip = min(min_grip, grip)
        last_grip = grip
        closed = grip < prt.PICK_GRIP_CLOSED
        ascended = (post_min_peak_z - min_z) >= prt.PICK_LIFT_THRESH
        if ascended and closed:      # latch 仅记录,不 break(hold-through)
            success = True
        if prims.env.episode_terminated or prims.env.episode_truncated:
            success = success or prims.env.episode_terminated
            break
    return {"name": "pick", "instruction": prompt, "success": bool(success),
            "chunks_used": chunks_used + chunks_already,
            "max_chunks": max_chunks,
            "min_gripper_opening": min_grip,
            "final_gripper_opening": last_grip,
            "libero_terminated": bool(prims.env.episode_terminated)}


# ---- 双契约标签(prereg §2)--------------------------------------------------
def _confirms(cur: dict, base: dict, target: str | None) -> bool:
    """单测量点是否满足 ACQUISITION 条景(check_success ∨ FG 契约)。"""
    if cur["check_success"]:
        return True
    if not target or target not in cur["pos"] or target not in base["pos"]:
        return False
    dz = cur["pos"][target][2] - base["pos"][target][2]
    if dz < FG_LIFT_DZ or cur["eef"] is None:
        return False
    return math.hypot(cur["pos"][target][0] - cur["eef"][0],
                      cur["pos"][target][1] - cur["eef"][1]) <= FG_FOLLOW_DXY


def acquisition(cps: list[dict], base: dict, target: str | None) -> bool:
    return any(_confirms(c, base, target) for c in cps)


def first_confirm_idx(cps: list[dict], base: dict, target: str | None):
    for i, c in enumerate(cps):
        if _confirms(c, base, target):
            return i
    return None


def stable(cps: list[dict], base: dict, target: str | None,
           hold_min_points: int = HOLD_MIN_POINTS) -> bool:
    """§2:首中后全程保持 + 窗口下限;check_success 任一点 = 稳定证据。"""
    i = first_confirm_idx(cps, base, target)
    if i is None:
        return False
    if any(c["check_success"] for c in cps):
        return True
    tail = cps[i:]
    if len(tail) - 1 < hold_min_points:
        return False
    return all(_confirms(c, base, target) for c in tail)


# ---- cell 执行(prereg §8:restore → chunk → S_j → R_Q 次 hold 续跑)--------
def exec_from_current(ctx: dict, target: str | None, prompt: str, actions,
                      checkpoints_out: list[dict],
                      r_cont: int = R_Q) -> dict:
    """从 env 当前态(已 restore 或 live)执行 candidate + R 次续跑。

    测量点:base(执行前)+ chunk 后 + 每 continuation chunk 后 + 终态,
    全部 prt.checkpoint 格式;返回逐 replicate 双契约标签 + chunk 分类。
    """
    base = pre = prt.checkpoint(ctx, target)    # 本 cell 自己的基准
    checkpoints_out.append(base)
    term = prt.execute_chunk(ctx["prims"], actions)
    post = prt.checkpoint(ctx, target)
    checkpoints_out.append(post)
    S_j = ctx["env"].save_state()
    reps = []
    for r in range(r_cont):
        obs = ctx["env"].restore_state(S_j)
        ctx["prims"].set_obs(obs)
        cps = [post]
        rep = {"cont_idx": r + 1, "terminated_in_chunk": term}
        if term:
            cps.append(prt.checkpoint(ctx, target))
        else:
            def on_chunk(_i, _t=target, _c=cps):
                _c.append(prt.checkpoint(ctx, _t))
            pick = run_continuation_hold(ctx["prims"], prompt,
                                         on_chunk=on_chunk)
            rep["pick"] = pick
            cps.append(prt.checkpoint(ctx, target))
        checkpoints_out.extend(cps)
        rep["acquisition"] = acquisition(cps, base, target)
        rep["stable"] = stable(cps, base, target)
        rep["label_p"] = prt.outcome_label("FALSE_GRASP", cps, base, target)
        reps.append(rep)
    cls = prt.classify_chunk(pre, post)
    return {"reps": reps,
            "n_acq": sum(1 for x in reps if x["acquisition"]),
            "n_stable": sum(1 for x in reps if x["stable"]),
            "base": base, "chunk_post": post,
            "terminated_in_chunk": term, "chunk_class": cls}


def exec_from_state(ctx: dict, S, target: str | None, prompt: str, actions,
                    checkpoints_out: list[dict], tag: str,
                    r_cont: int = R_Q) -> dict:
    """restore(S)(读回校验)→ exec_from_current。"""
    ctx["S"] = S
    rt.restore_checked(ctx, tag)
    return exec_from_current(ctx, target, prompt, actions,
                             checkpoints_out, r_cont)


def stop_ctx(ctx):
    for d in (ctx.get("daemons") or []):
        try:
            d.stop()
        except Exception:
            pass


# ---- manifest 读取(Q0 复用 Stage P DEV/TEST 行;Q1 用自己的 manifest)------
def read_manifest(path: Path) -> list[dict]:
    lines = [l for l in Path(path).read_text().splitlines()
             if not l.startswith("#")]
    import csv, io
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    # P manifest 用 state_sha16,Q manifest 用 pre_sha16(同 boot 成对,双 sha)
    def sha(r):
        return r.get("pre_sha16") or r.get("state_sha16")
    return [r for r in rows if sha(r)
            and sha(r) != "INFRA_ABORT_3attempts"]
