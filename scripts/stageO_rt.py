#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O O-B 共享运行时:快照重放/restore、契约测量、预算守卫、planner 续跑。

预注册:analysis/stageO_prereg.md(§2 仪器、§5 双结局契约、§6 arms、
§7 预算、§8.1 续跑模板)。本模块只实现冻结内容,不做任何判定。

被以下脚本复用:stageO_reference.py(K_REF)/ stageO_ladder.py(O0-O4)/
stageO_calibrate.py(K_ROLLOUT 校准)/ stageO_freeze_manifest.py(manifest)。

核心组件:
- boot_snapshot():init_task_runtime + get_toolkit + 重放 1..t0 + save_state
  (N1 已验证模式;J0 已证重放位精确);
- restore_checked():restore + set_obs + 读回校验(必须 0.0,否则 InfraError);
- measure()/task_recovery()/reentry_static()/reentry_probe():§5 契约
  (全部 sim 级确定性测量);
- BudgetGuard:包 toolkit.execute_tool(实例属性遮蔽,planner 唯一动作通道),
  动作原语/pi05/墙钟三计数,超限返回 error 不执行;每动作后在线测契约;
- continuation_prompt():§8.1 冻结模板(仅 episode 自身 prefix 信息);
- run_planner_continuation():build_planner + solve(max_turns=16)。
"""
from __future__ import annotations

# 代理防火墙必须在任何 urllib/httpx 使用者 import 之前注入(同 stageN1_runner)
import os as _os

for _k in ("no_proxy", "NO_PROXY"):
    _v = _os.environ.get(_k)
    _loop = "127.0.0.1,localhost"
    _os.environ[_k] = (_v + "," + _loop) if _v else _loop

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# ---- 冻结常量(prereg §2/§5/§6/§7)----------------------------------------
ACTION_TOOLS = {"move_to", "pi0_pick", "pi0_doubled", "set_gripper",
                "release", "rotate_wrist", "rotate_pitch", "move_pose"}
PI05_TOOLS = {"pi0_pick", "pi0_doubled"}

FAM2PROC = {"RELEASE_PREDICATE_STALL": "P1_RPS_REPICK",
            "FALSE_GRASP": "P2_FG_RETRY"}

# 预算表(prereg §7;O3 = O4)
BUDGET_LADDER = dict(max_primitives=12, max_pi05=6, max_turns=16,
                     wall_s=1200.0)
BUDGET_SAMPLE = dict(wall_s=300.0)          # O1/O2 单样本
# O0 预算 = N1 冻结(5 动作 / pick≤2),由 ladder 内 N1 移植策略自带

# TASK_RECOVERY 契约(prereg §5.1)
FG_LIFT_DZ = 0.03          # 目标物 z 抬升阈值
FG_FOLLOW_DXY = 0.10       # 目标物 xy 距 EEF 阈值
# RE 静态层(prereg §5.2)
RE_SEG_MIN_SCORE = 0.30
RE_EEF_X = (-0.60, 0.35)
RE_EEF_Y = (-0.45, 0.50)
RE_EEF_Z = (0.80, 1.35)
RE_HARM_DZ = -0.03
RE_HARM_DXY = 0.08
RE_OBJ_Z_MIN = 0.80
RE_PROBE_MAX_PRIMS = 3

MAX_INFRA_RETRY = 3


def init_degenerate_ids() -> set[str]:
    """dev-O5:init 即 check_success=True 的确定性退化快照(统一口径)。

    这些快照在任何重放下 base 都平凡满足 §5.1 契约(check_success 附加
    通过路径),无法测量 recovery:runner 跳过(省无效 boot),分析层
    单列(ALREADY_RECOVERED_AT_INIT)。证据文件 stageO_init_check.json
    (t0=0 不重放、纯 init 态测量)随 dev-O5 commit 冻结。
    """
    p = REPO / "analysis/stageO_init_check.json"
    if not p.exists():
        return set()
    try:
        recs = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {r.get("snapshot_id") for r in recs
            if r.get("init_check_success") is True}


class InfraError(Exception):
    """infra 级失败(读回≠0 / env 崩溃 / RPC 异常):重试,不混入指标。"""


# ---- 通用小工具(沿用 N1 语义)---------------------------------------------
def load_steps(episode_dir: str) -> list[dict]:
    steps = json.load(open(Path(episode_dir) / "states.json"))
    return sorted(steps, key=lambda s: s.get("step_idx") or 0)


def pos_map(obs: dict) -> dict[str, list[float]]:
    """sim_measurement obs → {物体名: pos[3]}(逐物体键,J0 布局)。"""
    out = {}
    for k, v in obs.items():
        if (k.endswith("_pos") and not k.startswith("robot0")
                and "_to_robot0_eef" not in k):
            try:
                out[k[:-4]] = [float(x) for x in v]
            except (TypeError, ValueError):
                pass
    return out


def eef_of(obs: dict) -> list[float] | None:
    v = obs.get("robot0_eef_pos")
    return [float(x) for x in v] if v is not None else None


def dxy(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def state_hash(S) -> str:
    """save_state 字节串的 sha256 前 16 hex(manifest 冻结/runner 断言用)。"""
    if isinstance(S, (bytes, bytearray)):
        return hashlib.sha256(bytes(S)).hexdigest()[:16]
    import numpy as np
    if isinstance(S, np.ndarray):
        return hashlib.sha256(S.tobytes()).hexdigest()[:16]
    return hashlib.sha256(str(type(S)).encode() + b":"
                          + str(len(S)).encode()).hexdigest()[:16]


def jsonable(o):
    import numpy as np
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o


# ---- 快照启动 / restore -----------------------------------------------------
def boot_snapshot(snap: dict, gpu: int, shared_kwargs: dict,
                  outdir: Path, note="", validate_event: bool = True):
    """起 env(同源 task/seed)+ toolkit + 重放 prefix 1..t0 + save_state。

    返回 dict(toolkit/prims/env/S/baseline)。infra 异常向上抛。

    validate_event(dev-O5):重放有效性守卫——重放实例必须复现该快照的
    定义性家族事件(t0 结果),且 base 不得已满足恢复契约;违反 → InfraError
    (调用方按 infra 重试)。prefix 含 Pi0.5 技能,重放必然重采样(J0 冻结:
    同 obs 动作非确定),因此跨 boot 逐位 hash 相等不可达,prereg §2 只冻结
    boot 内 readback==0(restore_checked);state_sha16 仅作 freeze 时指纹。
    validate_event=False 供 init 取证(t0=0 无重放)使用。
    """
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)
    env_spec = get_env_spec("libero")
    args = argparse.Namespace(
        suite="libero_spatial", task=int(snap["task"]), seed=int(snap["seed"]),
        max_episode_steps=10000, cuda_device=gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None,
    )
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

    # 重放 prefix 1..t0(含 t0:失败恰发生在 t0,N1 同款)
    steps = load_steps(snap["episode_dir"])
    t0i = int(snap["t0"])
    for s in steps:
        idx, cmd = s.get("step_idx"), s.get("command")
        if idx is None or not cmd or not (1 <= idx <= t0i):
            continue
        kwargs = {k: v for k, v in cmd.items() if k != "action"}
        try:
            toolkit._step(cmd["action"], **kwargs)
        except Exception as exc:
            raise InfraError(f"replay step {idx} {cmd['action']}: "
                             f"{type(exc).__name__}: {exc}") from exc

    S = env.save_state()
    # 结构性校验:save_state 长度必须与 manifest 冻结值一致(固定长度状态向量)
    if snap.get("state_len") and len(S) != int(snap["state_len"]):
        raise InfraError(f"state len {len(S)} != manifest "
                         f"{snap['state_len']}")
    base = measure(env)
    if validate_event and t0i > 0:
        # dev-O5 家族事件复现守卫:重放出的 t0 步结果必须仍是该家族事件
        replayed = json.load(open(outdir / "states.json"))
        t0_rec = next((s for s in reversed(replayed)
                       if s.get("command")
                       and s.get("step_idx") == t0i), None)
        t0_res = (t0_rec or {}).get("result") or {}
        if snap.get("family") == "FALSE_GRASP" \
                and t0_res.get("success") is True:
            raise InfraError("replay t0 pick succeeded — family event "
                             "not reproduced")
        if snap.get("family") == "RELEASE_PREDICATE_STALL" \
                and t0_res.get("libero_terminated") is True:
            raise InfraError("replay t0 release terminated — family event "
                             "not reproduced")
        if base["check_success"]:
            raise InfraError("base check_success True — recovery contract "
                             "trivially met at t0")
    if base["eef"] is None:
        raise InfraError("baseline robot0_eef_pos missing")
    target = (base["meas"].get("obj_of_interest") or [""])[0]
    return {
        "toolkit": toolkit, "prims": prims, "env": env, "S": S,
        "daemons": env_daemons, "outdir": outdir,
        "base": base, "target": target or None,
        "state_hash": state_hash(S), "note": note,
    }


def restore_checked(ctx: dict, tag: str) -> None:
    """restore + set_obs + 读回校验(必须逐位 0.0)。"""
    obs = ctx["env"].restore_state(ctx["S"])
    ctx["prims"].set_obs(obs)
    readback = ctx["env"].save_state()
    same_len = len(readback) == len(ctx["S"])
    rb = float(abs(readback - ctx["S"]).max()) if same_len else -1.0
    if rb != 0.0:
        raise InfraError(f"restore readback {rb} != 0 ({tag})")


# ---- 测量与契约(§5)--------------------------------------------------------
def measure(env) -> dict:
    """一次 sim 级测量:check_success + obs 派生量。"""
    meas = env.sim_measurement()
    obs = meas.get("obs") or {}
    return {"meas": meas, "obs": obs, "pos": pos_map(obs),
            "eef": eef_of(obs), "check_success": bool(env.check_success()),
            "terminated": bool(meas.get("libero_terminated")
                               or obs.get("libero_terminated"))}


def task_recovery(family: str, cur: dict, base: dict, target: str | None,
                  action_result: dict | None = None) -> bool:
    """§5.1 TASK_RECOVERY(确定性;FG 需 base 对照,RPS 只看当前/结果)。

    action_result:刚执行动作的 result(在线检测通道;RPS 的
    libero_terminated 只在动作 result 里)。
    """
    if cur["check_success"]:
        return True
    if family == "RELEASE_PREDICATE_STALL":
        if cur["terminated"]:
            return True
        if action_result and action_result.get("libero_terminated") is True:
            return True
        return False
    # FALSE_GRASP:object lifted AND follows EEF(同一测量点)
    if not target or target not in cur["pos"] or target not in base["pos"]:
        return False
    dz = cur["pos"][target][2] - base["pos"][target][2]
    if dz < FG_LIFT_DZ or cur["eef"] is None:
        return False
    return dxy(cur["pos"][target], cur["eef"]) <= FG_FOLLOW_DXY


def reentry_static(cur: dict, base: dict, target: str | None) -> dict:
    """§5.2 静态层 RE1/RE2/RE3(不依赖 probe;RE1 由调用方填 segment 结果)。
    返回逐项 dict;RE1 单独补。"""
    eef = cur["eef"]
    re2 = bool(eef and all(math.isfinite(c) for c in eef)
               and RE_EEF_X[0] < eef[0] < RE_EEF_X[1]
               and RE_EEF_Y[0] < eef[1] < RE_EEF_Y[1]
               and RE_EEF_Z[0] < eef[2] < RE_EEF_Z[1])
    re3 = True
    if target and target in cur["pos"] and target in base["pos"]:
        dzc = cur["pos"][target][2] - base["pos"][target][2]
        dxyc = dxy(cur["pos"][target], base["pos"][target])
        if dzc < RE_HARM_DZ or dxyc > RE_HARM_DXY:
            re3 = False
    for p in cur["pos"].values():
        if p[2] < RE_OBJ_Z_MIN:
            re3 = False
            break
    return {"RE2_pose_legal": re2, "RE3_config_valid": re3}


def _skip_result(name: str, reason: str):
    """超限/已命中时的 ToolResult(planner 工具包装层需要 content_blocks)。"""
    from rpent.tools.toolkit import ToolResult
    return ToolResult(name=name, result={"error": f"stageO_{reason}"})


def seg_probe(prims, prompt: str) -> dict:
    """RE1 探测 segment(感知不进预算)。"""
    try:
        seg = prims.segment(prompt=prompt, camera="agentview",
                            min_score=RE_SEG_MIN_SCORE)
    except Exception as exc:
        raise InfraError(f"reentry segment: {type(exc).__name__}: {exc}")
    xyz = seg.get("world_xyz")
    ok = bool(seg.get("found") and seg.get("score") is not None
              and seg["score"] >= RE_SEG_MIN_SCORE
              and isinstance(xyz, (list, tuple)) and len(xyz) == 3
              and all(math.isfinite(float(c)) for c in xyz))
    return {"found": seg.get("found"), "score": seg.get("score"),
            "usable": ok}


def last_pi05_cmd(steps: list[dict], t0: int) -> tuple[str, dict] | None:
    """O1/O2 重放对象:step ≤ t0 的最后一条 Pi0.5 族命令(prereg §6)。"""
    for s in reversed(steps):
        idx = s.get("step_idx")
        cmd = s.get("command") or {}
        if idx is None or idx > t0:
            continue
        if cmd.get("action") in PI05_TOOLS:
            return cmd["action"], {k: v for k, v in cmd.items()
                                   if k != "action"}
    return None


def t0_prompt(family: str, steps: list[dict], t0: int) -> str | None:
    """RE1/RE probe 的 target prompt:FG 用 t0 pick prompt;
    RPS 用 prefix 内最后一个 pick/doubled prompt(prereg §5.2)。"""
    by = {s.get("step_idx"): s for s in steps}
    if family == "FALSE_GRASP":
        return (by.get(t0) or {}).get("command", {}).get("prompt")
    cmd = last_pi05_cmd(steps, t0)
    return (cmd[1] or {}).get("prompt") if cmd else None


# ---- 预算守卫(planner 唯一动作通道)---------------------------------------
class BudgetGuard:  # noqa: D101 — 见类 docstring
    """遮蔽 toolkit.execute_tool:三计数 + 超限 no-op + 在线契约检测。

    - 动作原语(pi05 与否)计 prims;pi05 另计;
    - 感知工具不计数(与 N1 同);
    - 超限:返回 {"error": "stageO_budget_exhausted"} 不执行;
    - 契约命中后(contract_latched):后续动作调用返回
      {"error": "stageO_task_recovery_already_met"}(planner 快速收尾,
      浪费有界;步记录保留首中点)。
    """

    def __init__(self, toolkit, env, family: str, base: dict,
                 target: str | None, budget: dict):
        self._toolkit = toolkit
        self._orig = toolkit.execute_tool
        self.env, self.family, self.base, self.target = env, family, base, target
        self.budget = dict(budget)
        self.n_prims = 0
        self.n_pi05 = 0
        self.n_planner_tools = 0
        self.t_start = time.time()
        self.steps: list[dict] = []       # (action, kwargs, result_subset)
        self.contract_latched = False
        self.contract_at_step: int | None = None
        self.exhausted = False
        toolkit.execute_tool = self  # 实例属性遮蔽(__call__ 分发)

    def close(self):
        try:
            delattr(self._toolkit, "execute_tool")  # 恢复绑定方法
        except AttributeError:
            pass

    def _remaining(self) -> tuple[bool, str]:
        if time.time() - self.t_start > self.budget["wall_s"]:
            return False, "wall"
        if self.n_prims >= self.budget["max_primitives"]:
            return False, "prims"
        if self.n_pi05 >= self.budget["max_pi05"]:
            return False, "pi05"
        return True, ""

    def __call__(self, name: str, input_dict: dict):
        self.n_planner_tools += 1
        if name not in ACTION_TOOLS:      # 感知/finish 等照常
            return self._orig(name, input_dict)
        if self.contract_latched:
            self.steps.append({"action": name,
                               "kwargs": jsonable(input_dict),
                               "result": {"skipped": "already_met"}})
            return _skip_result(name, "task_recovery_already_met")
        ok, why = self._remaining()
        if not ok:
            self.exhausted = True
            self.steps.append({"action": name,
                               "kwargs": jsonable(input_dict),
                               "result": {"skipped": f"budget_{why}"}})
            return _skip_result(name, f"budget_exhausted_{why}")
        t1 = time.time()
        res = self._orig(name, input_dict)
        result = res.result if hasattr(res, "result") else res
        if not (isinstance(result, dict) and result.get("error")):
            self.n_prims += 1
            if name in PI05_TOOLS:
                self.n_pi05 += 1
        self.steps.append({
            "action": name, "kwargs": jsonable(input_dict),
            "result": _result_subset(result),
            "elapsed_s": round(time.time() - t1, 1)})
        # 在线契约检测(首中即锁)
        try:
            cur = measure(self.env)
            if task_recovery(self.family, cur, self.base, self.target,
                             action_result=_as_dict(result)):
                self.contract_latched = True
                self.contract_at_step = len(self.steps)
        except Exception:
            pass  # 测量异常不中断 rollout(结束再测一次)
        return res


RESULT_KEEP = {"success", "libero_terminated", "final_gripper_opening",
               "min_gripper_opening", "peak_lift_m", "final_dist_m",
               "chunks_used", "max_chunks", "steps_used", "name",
               "target_xyz", "final_eef_pos", "error"}


def _as_dict(x) -> dict | None:
    return x if isinstance(x, dict) else None


def _result_subset(result) -> dict:
    if not isinstance(result, dict):
        return {"value": str(result)[:120]}
    return {k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in result.items() if k in RESULT_KEEP}


# ---- §8.1 续跑模板 ----------------------------------------------------------
RESUME_HEADER = "\n\n[RESUME CONTEXT]\n" \
    "You are resuming this same task mid-episode. Below is the verbatim " \
    "action log so far (commands and results exactly as recorded):\n"
RESUME_FOOTER = "\n[END OF LOG]\nThe robot is now exactly in the state " \
    "right after step {t0}. Continue the task from here."


def continuation_prompt(user_msg: str, steps: list[dict], t0: int) -> str:
    """§8.1 冻结模板:原文任务 prompt + 逐字 prefix 步日志。"""
    lines = []
    for s in steps:
        idx, cmd = s.get("step_idx"), s.get("command")
        if idx is None or not cmd or not (1 <= idx <= t0):
            continue
        kwargs = {k: v for k, v in cmd.items() if k != "action"}
        res = _result_subset(s.get("result") or {})
        lines.append(f"step {idx}: ACTION {cmd['action']} "
                     f"ARGS {json.dumps(jsonable(kwargs), default=str)} "
                     f"-> RESULT {json.dumps(res, default=str)}")
    return (user_msg + RESUME_HEADER + "\n".join(lines)
            + RESUME_FOOTER.format(t0=t0))


def render_task_prompts(snap: dict, outdir: Path) -> tuple[str, str]:
    """按 CLI 同一路径渲染 system/user prompt(prompt_vars 同源)。"""
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec

    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(suite="libero_spatial", task=int(snap["task"]),
                            seed=int(snap["seed"]), output_dir=str(outdir))
    run_config = env_spec.parse_config(ns)
    prompt_vars = {**run_config.prompt_vars, "output_dir": str(outdir)}
    system_prompt = env_spec.prompts.render("system", variables=prompt_vars)
    user_msg = env_spec.prompts.render("user", variables=prompt_vars)
    return system_prompt, user_msg


# ---- §22 turn 记录(从 planner transcript 消息抽取紧凑摘要)-----------------
def extract_turns(messages) -> list[dict]:
    """planner messages → 每 assistant turn 一条紧凑记录(§22)。

    next_skill = 该 turn 首个 tool_use;reason = thinking/tail 文本末 300 字;
    obs_excerpt = 该 turn 之前最近一条 tool 结果前 200 字(observation summary)。
    原始 transcript 由 api_loop 落 outdir,此处只留分析所需摘要。
    """
    turns = []
    last_tool_res = ""
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "tool":
            last_tool_res = str(m.get("content", ""))[:200]
            continue
        if role != "assistant":
            continue
        blocks = m.get("content") or []
        text = [b.get("text", "") for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"]
        think = [b.get("thinking", "") for b in blocks
                 if isinstance(b, dict) and b.get("type") == "thinking"]
        tools = [b for b in blocks
                 if isinstance(b, dict) and b.get("type") == "tool_use"]
        reason = (think[-1] if think else (text[-1] if text else "")) or ""
        tu = tools[0] if tools else None
        args = (tu.get("input") or {}) if tu else {}
        turns.append({
            "turn_idx": len(turns) + 1,
            "next_skill": tu.get("name") if tu else None,
            "skill_args_excerpt": {k: str(v)[:80] for k, v in args.items()},
            "reason_excerpt": reason.strip()[-300:],
            "obs_excerpt": last_tool_res,
        })
    return turns


# ---- planner 续跑(reference 与 O4 共用)-----------------------------------
def run_planner_continuation(ctx: dict, snap: dict, family: str,
                             max_turns: int | None = None,
                             base_url: str = "https://open.bigmodel.cn/api/anthropic",
                             model: str = "anthropic:glm-5.3-flash",
                             max_tokens: int = 24576):
    """restore 后起 planner 循环;返回 rollout 记录 dict。

    预算 = BUDGET_LADDER(prereg §7;O3/O4 同表)。契约首中即锁
    (后续动作 no-op,planner 有界收尾)。
    """
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.planner.base import build_planner

    steps = load_steps(snap["episode_dir"])
    t0 = int(snap["t0"])
    restore_checked(ctx, f"{snap['snapshot_id']} planner")
    system_prompt, user_msg = render_task_prompts(snap, ctx["outdir"])
    cont_user = continuation_prompt(user_msg, steps, t0)

    guard = BudgetGuard(ctx["toolkit"], ctx["env"], family, ctx["base"],
                        ctx["target"], BUDGET_LADDER)
    planner = build_planner(
        "api", output_dir=ctx["outdir"],
        recipe_tag=f"stageO_{snap['snapshot_id']}",
        env_name="libero", base_url=base_url, model=model,
        max_tokens=max_tokens, planner_timeout_s=None,
        dashboard_events=NullDashboardEventSink(), no_images=False)
    t1 = time.time()
    agent_error = None
    result = None
    try:
        result = planner.solve(
            system_prompt=system_prompt, user_message=cont_user,
            toolkit=ctx["toolkit"],
            max_turns=max_turns or BUDGET_LADDER["max_turns"])
        agent_error = result.error
        finish = result.finish_result
    except Exception as exc:
        finish, agent_error = None, f"{type(exc).__name__}: {exc}"
    finally:
        guard.close()
    wall = round(time.time() - t1, 1)

    final = measure(ctx["env"])
    met = guard.contract_latched or task_recovery(
        family, final, ctx["base"], ctx["target"])
    # §22 turn 摘录:messages 在 solve 正常返回时才有
    turns = extract_turns(getattr(result, "messages", None)) \
        if result is not None else []
    return {
        "contract_met": bool(met),
        "contract_at_step": guard.contract_at_step,
        "check_success": final["check_success"],
        "n_prims": guard.n_prims, "n_pi05": guard.n_pi05,
        "n_planner_tools": guard.n_planner_tools,
        "budget_exhausted": guard.exhausted,
        "wall_s": wall, "agent_error": agent_error,
        "finish": jsonable(finish) if finish else None,
        "steps": guard.steps, "final": final,
        "turns": turns,
    }


# ---- 环境块(N1 教训:缺一个就 vla_server 卡 gs:// 300s)--------------------
ENV_FILE = "/workspace/yjx/rpent_data/rpent_env.sh"


def apply_env_overrides() -> None:
    e = _os.environ
    e["MUJOCO_GL"] = "osmesa"
    e["PYOPENGL_PLATFORM"] = "osmesa"
    e.pop("MUJOCO_EGL_DEVICE_ID", None)
    e.pop("LIBGL_ALWAYS_SOFTWARE", None)
    e.setdefault("OPENPI_DATA_HOME",
                 "/workspace/yjx/rpent_data/.cache/openpi")
    # GLM planner 凭据(进程内 build_planner 需要;key 值绝不打印/落日志)
    if not e.get("ANTHROPIC_API_KEY"):
        try:
            with open(ENV_FILE) as f:
                for line in f:
                    if line.startswith("GLM_API_KEY="):
                        e["ANTHROPIC_API_KEY"] = (
                            line.split("=", 1)[1].strip().strip('"')
                            .strip("'"))
        except OSError:
            pass
        assert e.get("ANTHROPIC_API_KEY"), (
            f"GLM_API_KEY missing in {ENV_FILE} — GLM planner would 401")
