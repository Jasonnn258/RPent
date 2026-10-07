"""Stage R 采集期仪器(默认关闭;环境变量 RPENT_STAGE_R_TRACE=1 启用)。

设计约束(prereg §2):
- **零语义改动**——只增加观测:不改任何动作派发/终止/超时逻辑;
- 插桩点 1:`LiberoToolkit._step` 技能边界 → 每技能 pre/post `save_state`
  快照(S_pre/S_post 原始 live 字节)+ step 起止标记;
- 插桩点 2:`LiberoEnvClient.step/chunk_step`(全部底层动作的唯一咽喉)
  → 动作流逐条落盘(base64 float32 逐位保真,支撑 PREFIX_REPLAY 与
  a_fail 冻结);
- 插桩点 3:pick 类技能(pi0_pick/pi0_doubled)每个 chunk 前附
  sim_measurement 低维测量 + check_success(支撑稳定失败进入标准:
  失败技能期间任一测量点满足 acquisition → 非稳定失败)。

产物(episode outdir 内):
- ``stageR_trace.jsonl``:动作流 + step 边界标记(append,逐行 flush);
- ``stageR_snapshots/step_{idx:03d}_{pre,post}.npy``:MuJoCo flatten 快照。

失败安全:本模块任何异常都不得杀死 episode——所有公开函数整体
try/except,仪器自身故障只落一条 error 记录(或完全吞掉)。
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import numpy as np

# 需要逐 chunk 附测量的技能(策略闭环抓取;scripted 原语不附,省 RPC)
PICK_SKILLS = frozenset({"pi0_pick", "pi0_doubled"})

# 模块级上下文(agent 子进程内 toolkit 与 env_client 共享同一进程)
_CTX: dict = {"fh": None, "env": None, "step_idx": None, "skill": None,
              "chunk": 0, "broken": False}


def enabled() -> bool:
    """RPENT_STAGE_R_TRACE=1 时启用(热路径每步调用,保持极轻)。"""
    return os.environ.get("RPENT_STAGE_R_TRACE") == "1"


# ---- 内部 ------------------------------------------------------------------

def _f2b(arr) -> str:
    """动作数组 → base64(float32 逐位保真;PREFIX_REPLAY 解码还原)。"""
    return base64.b64encode(
        np.asarray(arr, dtype=np.float32).tobytes()).decode("ascii")


def _outdir() -> Path:
    from rpent.utils.logging import get_output_dir
    d = Path(get_output_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapdir() -> Path:
    p = _outdir() / "stageR_snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fh():
    if _CTX["fh"] is None:
        _CTX["fh"] = open(_outdir() / "stageR_trace.jsonl", "a",
                          encoding="utf-8")
    return _CTX["fh"]


def _emit(rec: dict) -> None:
    rec["t"] = round(time.time(), 3)
    _fh().write(json.dumps(rec, ensure_ascii=False) + "\n")
    _fh().flush()


def _meas_now(env) -> dict | None:
    """一次低维测量(sim_measurement + check_success),失败返回 None。"""
    try:
        m = env.sim_measurement()
        obs = m.get("obs") or {}
        return {
            "obs": {k: [float(x) for x in np.atleast_1d(v)]
                    for k, v in obs.items()},
            "obj_of_interest": list(m.get("obj_of_interest") or []),
            "check_success": bool(env.check_success()),
        }
    except Exception:
        return None


def _save_snap(env, step_idx: int, phase: str) -> None:
    snap = env.save_state()
    np.save(_snapdir() / f"step_{step_idx:03d}_{phase}.npy",
            np.asarray(snap))


# ---- 公开 API(全部自守卫:仪器故障绝不向上抛)---------------------------

def begin_step(step_idx: int, name: str, kwargs: dict, env) -> None:
    """技能开始:登记上下文 + pre 快照。"""
    if _CTX["broken"]:
        return
    try:
        _CTX.update(env=env, step_idx=step_idx, skill=name, chunk=0)
        _emit({"ev": "step_begin", "step_idx": step_idx, "skill": name,
               "kwargs": {k: str(v)[:100] for k, v in (kwargs or {}).items()}})
        try:
            _save_snap(env, step_idx, "pre")
        except Exception as exc:
            _emit({"ev": "snap_fail", "phase": "pre", "step_idx": step_idx,
                   "err": f"{type(exc).__name__}: {exc}"[:200]})
    except Exception:
        _CTX["broken"] = True   # 文件系统级故障:静默停用,不杀 episode


def end_step(step_idx: int, result: dict) -> None:
    """技能结束:post 快照 + 结果标记(pick 类附终态测量)。"""
    if _CTX["broken"]:
        return
    try:
        rec = {"ev": "step_end", "step_idx": step_idx,
               "skill": _CTX.get("skill"),
               "success": (bool(result.get("success"))
                           if isinstance(result, dict) else None)}
        if _CTX.get("skill") in PICK_SKILLS and _CTX.get("env") is not None:
            rec["final_meas"] = _meas_now(_CTX["env"])
        try:
            _save_snap(_CTX["env"], step_idx, "post")
        except Exception as exc:
            rec["snap_fail_post"] = f"{type(exc).__name__}: {exc}"[:200]
        _emit(rec)
    except Exception:
        _CTX["broken"] = True


def log_env_call(kind: str, actions) -> None:
    """动作咽喉日志:kind ∈ {"step", "chunk"};pick 技能 chunk 附测量。

    注意在 RPC **调用前**记录:记录的是发出的动作本身;chunk k 的测量
    反映 chunk k 执行前(= chunk k−1 执行后)的状态,与技能末 final_meas
    一起构成完整测量曲线。
    """
    if _CTX["broken"] or _CTX.get("env") is None:
        return
    try:
        a = np.asarray(actions, dtype=np.float32)
        rec = {"ev": "action", "kind": kind,
               "step_idx": _CTX.get("step_idx"), "skill": _CTX.get("skill"),
               "shape": list(a.shape), "b64": _f2b(a)}
        if kind == "chunk" and _CTX.get("skill") in PICK_SKILLS:
            _CTX["chunk"] += 1
            rec["chunk_idx"] = _CTX["chunk"]
            rec["meas"] = _meas_now(_CTX["env"])
        _emit(rec)
    except Exception:
        _CTX["broken"] = True
