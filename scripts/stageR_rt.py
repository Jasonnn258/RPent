#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage R 运行时库 — 事件装载 / bare boot / 两种状态重建 / trial 执行。

R0(重建资格)与 R1(双臂)共用的执行原语。规范:stageR_prereg §3/§4/§6。

关键语义:
- DIRECT_SNAPSHOT:restore 原始 live S_pre 字节(读回校验必须逐位 0);
- PREFIX_REPLAY:同 (task,seed) fresh env → reset(确定性 init)→ 逐条重放
  rtrace 动作流(底层动作原样,禁止重调 Pi0.5)→ 与 S_pre 做 flatten
  per-index 一致性报告(是否逐位一致由 R0 门裁决,这里只测量不断言);
- 每次尝试独立重建(prereg §11):不得从上次终态继续;
- trial 执行复用 Stage Q 冻结路径:prt.execute_chunk + 单次
  hold-through continuation + 双契约标签(qt.exec_from_current, r_cont=1)。
"""
from __future__ import annotations

import base64
import csv
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path("/workspace/yjx/workspace/RPent")
sys.path.insert(0, str(ROOT / "scripts"))
import stageO_rt as rt                      # measure / restore_checked / state_hash
import stageQ_rt as qt                      # exec_from_current / flatten_delta
import stageP_rt as prt                     # sample_candidate / execute_chunk / sha

LEDGER = ROOT / "analysis/stageR_collect_ledger.csv"
BOOT_LOCK = threading.Lock()   # boot/replay 相串行(get_output_dir 全局竞态,dev-Q1)

MAX_INFRA_RETRY = 3


# ---- 事件装载(collect 序;零结果条件化)-----------------------------------

def load_events() -> list[dict]:
    """collect ledger 中 included=True 的行,按采集顺序 = 冻结队列序。

    ord = included 序号(1..N,队列序),不是 ledger 行号 —— R0/R1 的
    8/24 切分(dev-r1-fix)依据此序;event_id 仍按 ledger 行号命名(冻结)。
    """
    with open(LEDGER, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    evs = []
    for i, r in enumerate(rows, 1):
        if r.get("included") != "True":
            continue
        evs.append({"event_id": f"r{i:02d}", "ord": len(evs) + 1,
                    "task": int(r["task"]), "seed": int(r["seed"]),
                    "episode_dir": r["episode_dir"], "t0": int(r["t0"]),
                    "note": r.get("note", "")})
    return evs


def load_event_details(ev: dict) -> dict:
    """episode 产物 → {steps, prompt, prefix 动作流, a_fail, S_pre/S_post}。

    prefix = step_idx < t0 的全部底层动作(文件序);a_fail = t0 技能首个
    chunk(chunk_idx==1;Stage P P0 粒度)。快照按 npy 原始字节读入。
    """
    d = Path(ev["episode_dir"])
    steps = rt.load_steps(str(d))
    t0 = ev["t0"]
    t0_step = next(s for s in steps
                   if s.get("step_idx") == t0 and s.get("command"))
    prompt = t0_step["command"].get("prompt")

    prefix, a_fail = [], None
    with open(d / "stageR_trace.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("ev") != "action":
                continue
            idx = r.get("step_idx")
            if idx is None:
                continue
            a = np.frombuffer(base64.b64decode(r["b64"]),
                              dtype=np.float32).reshape(r["shape"])
            if idx < t0:
                prefix.append({"kind": r["kind"], "actions": a,
                               "step_idx": idx, "skill": r.get("skill")})
            elif idx == t0 and r.get("kind") == "chunk" \
                    and r.get("chunk_idx") == 1 and a_fail is None:
                a_fail = a.copy()          # t0 失败技能首个 chunk(= a_fail)
    if a_fail is None:
        raise ValueError(f"{ev['event_id']}: a_fail 首 chunk 缺失")

    S_pre = np.load(d / "stageR_snapshots" / f"step_{t0:03d}_pre.npy")
    S_post = np.load(d / "stageR_snapshots" / f"step_{t0:03d}_post.npy")
    ev = dict(ev)
    ev.update({"steps": steps, "prompt": prompt, "prefix": prefix,
               "a_fail": a_fail, "S_pre": S_pre, "S_post": S_post,
               "pre_sha16": rt.state_hash(S_pre),
               "post_sha16": rt.state_hash(S_post),
               "a_fail_sha16": prt.chunk_sha(a_fail),
               "n_prefix": len(prefix)})
    return ev


# ---- bare boot(不重放;env_server + toolkit,共享 vla/sam3)----------------

def boot_bare(ev: dict, gpu: int, shared_kwargs: dict, outdir: Path) -> dict:
    """起 env(同源 task/seed)+ toolkit,不做任何重放。

    与 qt.boot_to_pre 的唯一差异:不执行 prefix 技能重放(重建由调用方
    选择 SNAPSHOT / PREFIX 路径)。BOOT_LOCK 由调用方持有(boot 相串行)。
    """
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)
    env_spec = get_env_spec("libero")
    args = qt.argparse_ns(ev, gpu)
    env_daemons, env_kwargs = env_spec.init_task_runtime(
        args, outdir, NullDashboardEventSink())
    primitives_kwargs = dict(env_kwargs)
    primitives_kwargs.update(shared_kwargs)
    toolkit = get_toolkit(
        "libero", primitives_kwargs=primitives_kwargs,
        video_path=str(outdir / "episode.mp4"),
        dashboard_events=NullDashboardEventSink())
    prims = toolkit._primitives
    return {"toolkit": toolkit, "prims": prims, "env": prims.env,
            "daemons": env_daemons, "outdir": outdir, "ev": ev,
            "note": "bare"}


# ---- 两种重建(prereg §3/§11:每次尝试独立重建)---------------------------

def _finish_base(ctx: dict, consistency: dict) -> dict:
    """重建后公共收尾:base 测量 + 守卫(不得 trivially success)。"""
    base = rt.measure(ctx["env"])
    if base["check_success"]:
        raise rt.InfraError("reconstructed base check_success True — trivial")
    if base["eef"] is None:
        raise rt.InfraError("reconstructed base eef missing")
    target = (base["meas"].get("obj_of_interest") or [""])[0] or None
    ctx.update({"base": base, "target": target, "S": None,
                "consistency": consistency})
    return ctx


def reconstruct_snapshot(ctx: dict, ev: dict) -> dict:
    """DIRECT_SNAPSHOT:restore 原始 S_pre 字节(读回校验逐位 0)。"""
    ctx["S"] = ev["S_pre"]
    rt.restore_checked(ctx, f"{ev['event_id']}-snap")
    return _finish_base(ctx, {"method": "SNAPSHOT",
                              "readback_max_abs": 0.0})


def reconstruct_prefix(ctx: dict, ev: dict) -> dict:
    """PREFIX_REPLAY:reset(确定性 init)→ 逐条重放底层动作 → 一致性报告。

    重放期间不产生模型调用;终止闩若在 prefix 内触发 = infra(原 episode
    同动作未触发)。与 S_pre 的 flatten 一致性只测量不断言(R0 门裁决)。
    """
    env, prims = ctx["env"], ctx["prims"]
    obs, _ = env.reset()
    for rec in ev["prefix"]:
        if rec["kind"] == "chunk":
            ret = env.chunk_step(rec["actions"])
            o = ret[0][-1] if env.return_all_frames else ret[0]
        else:
            o = env.step(rec["actions"])[0]
        if env.episode_terminated or env.episode_truncated:
            raise rt.InfraError(
                f"prefix replay 终止闩触发 @step{rec['step_idx']}")
        obs = o
    prims.set_obs(obs)
    S_now = env.save_state()
    fd = qt.flatten_delta(ev["S_pre"], S_now)
    return _finish_base(ctx, {"method": "PREFIX",
                              "sha_match": rt.state_hash(S_now)
                              == ev["pre_sha16"],
                              "flatten_delta": fd})


def reconstruct(ctx: dict, ev: dict, method: str) -> dict:
    if method in ("SNAPSHOT", "SNAP"):        # SNAP = CSV 臂名(R0)
        return reconstruct_snapshot(ctx, ev)
    if method in ("PREFIX", "PREFIX_REPLAY"):
        return reconstruct_prefix(ctx, ev)
    raise ValueError(method)


# ---- trial 执行(复用 Stage Q 冻结路径,r_cont=1)--------------------------

def exec_trial(ctx: dict, ev: dict, actions, cps_out: list,
               arm: str, trial_idx: int) -> dict:
    """一次尝试:candidate 执行 + 单次 hold-through continuation + 双契约。

    target 取自 ctx(重建/boot 后 _finish_base 的运行时测量为准,
    事件文件不含该字段);prompt 取自事件。返回 {arm, trial,
    acquisition, stable, terminated_in_chunk, chunk_class, consistency,
    cand_sha}。
    """
    target = ctx.get("target") or ev.get("target")
    out = qt.exec_from_current(ctx, target, ev["prompt"], actions,
                               cps_out, r_cont=1)
    rep = out["reps"][0]
    return {"arm": arm, "trial": trial_idx,
            "acquisition": rep["acquisition"], "stable": rep["stable"],
            "pick": rep.get("pick"),
            "terminated_in_chunk": out["terminated_in_chunk"],
            "chunk_class": out["chunk_class"],
            "consistency": ctx.get("consistency"),
            "cand_sha": prt.chunk_sha(actions),
            "base": out["base"], "chunk_post": out["chunk_post"]}


def sample_fresh(ctx: dict, ev: dict):
    """Arm B:同 obs 语义下仅重采样(fresh frozen candidate)。"""
    return prt.sample_candidate(ctx["prims"], ev["prompt"])


def stop_ctx(ctx: dict) -> None:
    for d in (ctx.get("daemons") or []):
        try:
            d.stop()
        except Exception:
            pass


def with_infra_retry(fn, *args, label: str = "", retries: int = MAX_INFRA_RETRY):
    """infra 级异常(InfraError)重试 ≤3;其余异常直接上抛。"""
    last = None
    for i in range(1, retries + 1):
        try:
            return fn(*args)
        except rt.InfraError as exc:
            last = exc
            print(f"[infra] {label} 尝试{i}/{retries}: {exc}", flush=True)
            time.sleep(2.0)
    raise rt.InfraError(f"{label}: infra 重试耗尽 — {last}")
