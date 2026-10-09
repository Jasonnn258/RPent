"""P1-DEV0 实验路径(默认关闭;环境变量 RPENT_P1_DEV0=1 启用)。

与 Stage R 仪器(`rpent/utils/rtrace.py`)同一模式:源码里只留极轻的
默认关闭钩子行,全部逻辑集中在本模块;未启用时对 vanilla / Stage R
**零行为差异**。

预注册协议:P1-DEV0-L2-24EP-4ARM-20261009(analysis/research_context/
p1_dev0_manifest.py + p1_dev0_policy.py + P1_DEV0_AUTHORIZATION_AND_LOCK.md)。

设计要点:
- **触发**(每 episode 至多一次,ITT):首个 `pi0_pick` 返回
  `success=False` 且非 terminal、非 truncated 的真实 D2 边界
  (FIRST_NONTERMINAL_NONTRUNCATED_FALSE_PICK_D2_ONLY)。
- **四臂**:D0 无探测+固定盲重试;D1 相同物理探测但**遮蔽探测观测**
  (Planner 可见信息与 D0 同构);D2 探测+合法 proprio 单阈值;D3 探测+
  Evidence Claim(时效/多源/预算/弃权)。决策逻辑**只**来自冻结的
  `p1_dev0_policy.py`(按路径动态加载,不复制实现)。
- **物理探测** = `set_gripper(gripper=+1, steps=N)`:保持 EEF 位姿并夹紧,
  含 N 个真实 env steps,是"physical probe + potentially stabilizing
  intervention",不是零干预传感。探测**直接调 primitives**,不消耗
  toolkit 步号、不写 states.json——保证 D1 的 Planner 可见序列与 D0
  逐字段同构(步号连续、log.command 只有 pi0_pick)。
- **合法观测白名单**:与 dump_state 的 state 构造完全一致
  (robot0_eef_pos / robot0_eef_quat / robot0_gripper_qpos + 图像文件);
  绝不读取/记录物体坐标或 check_success 进决策路径
  (运行时用冻结 policy 的 deny_privileged_payload fail-close 校验)。
- **audit-only 固定 horizon 审计**:触发后第 H 个物理 env step 之后的
  首个技能边界取样 check_success + sim_measurement;只写入实验外部
  事件文件,绝不进入任何 Planner 可见返回。episode 提前结束则在
  close() 兜底取样(EPISODE_END)。
- **信息隔离**:事件/审计文件写在 `RPENT_P1_DEV0_OUT`(episode
  output_dir **之外**;Planner 的 read_text_file/list_dir 不受限,
  output_dir 内文件对 Planner 可见,审计真值绝不能放那里)。

失败安全:任何异常 → 记 hook_error、停用本 episode 干预、回落
vanilla 路径(返回 pick 自身视图),绝不杀死 episode。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

# ---- 预注册常量(运行前冻结;不根据结果调整)---------------------------
# +1 = 保持闭合/夹紧(robosuite 约定,见 move_to docstring);探测是
# 稳定化物理干预,效果归因由 D1 probe-blind 对照承担。
PROBE_GRIPPER = 1.0
PROBE_STEPS = 10          # 固定探测时长 = 10 个真实 env steps
DEFAULT_HORIZON = 200      # 固定未来审计 horizon(env steps)
DEFAULT_EPISODE_STEP_CAP = 1500   # D3 预算门的 episode 级 env-step 上限

# 决策路径合法 proprio 白名单(与 dump_state 的 state 构造一致)
_LEGAL_STATE_KEYS = ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")

# 模块级上下文(每进程一个 episode;rpent CLI 每 episode 一个进程)
_CTX: dict = {
    "inited": False, "broken": False,
    "arm": None, "episode_key": None, "out": None, "fh": None,
    "policy_mod": None, "policy_sha256": None,
    "horizon": None, "episode_step_cap": None,
    "env_steps": 0,                # 物理 env-step 计数(env_client 钩子累加)
    "triggered": False, "trigger_env_steps": None, "target_env_steps": None,
    "audited": False, "audit_kind": None,
    "intervening": False,          # 干预内部重入(retry 走 _step)守卫
    "t_start": None,
}


def enabled() -> bool:
    """RPENT_P1_DEV0=1 时启用(热路径每技能/每 env-step 调用,保持极轻)。"""
    return os.environ.get("RPENT_P1_DEV0") == "1"


def count_env_steps(n: int) -> None:
    """物理 env-step 计数(env_client.step/chunk_step 钩子调用;绝不抛)。"""
    if not enabled():
        return
    try:
        _CTX["env_steps"] += int(n)
    except Exception:
        pass


# ---- 内部 ------------------------------------------------------------------

def _emit(rec: dict) -> None:
    rec["t"] = round(time.time(), 3)
    _CTX["fh"].write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    _CTX["fh"].flush()


def _sha256_file(path: Path) -> dict | None:
    try:
        b = path.read_bytes()
        return {"path": str(path), "bytes": len(b),
                "sha256": hashlib.sha256(b).hexdigest()}
    except Exception:
        return None


def _legal_state(env) -> dict | None:
    """从 raw_obs 提取白名单 proprio(与 dump_state 的 state 同源同值;
    绝不透传 object 坐标键;返回 None 表示提取失败)。"""
    try:
        raw = env.raw_obs()
    except Exception:
        return None
    out = {}
    for k in _LEGAL_STATE_KEYS:
        v = raw.get(k)
        if v is None:
            return None
        out[k] = [float(x) for x in v]
    # robosuite 2f85: |qpos[6]|+|qpos[7]| ≈ 指距代理(开≈0.08,闭≈0)
    gp = out["robot0_gripper_qpos"]
    out["gripper_gap"] = round(abs(gp[0]) + abs(gp[1]), 6)
    out["eef_z"] = out["robot0_eef_pos"][2]
    return out


def _boundary_images(out_dir: Path, step_idx: int) -> list[dict]:
    """触发时刻已 dump 的合法低分图像(存在则哈希;缺失记 None,不影响决策)。"""
    try:
        from robots.libero import tools as lt
    except Exception:
        return []
    names = [
        ("policy_image_agentview_low", "policy_image", "agentview"),
        ("image_agentview_low", "image", "agentview"),
        ("image_wrist_low", "image", "wrist"),
    ]
    recs = []
    for label, kind, camera in names:
        try:
            p = lt.artifact_path(str(out_dir), kind, step=step_idx,
                                 camera=camera, resolution="low")
            rec = _sha256_file(p) if p is not None else None
        except Exception:
            rec = None
        recs.append({"name": label,
                     **(rec or {"path": None, "missing": True})})
    return recs


def _init() -> bool:
    """读取环境变量、加载冻结 policy、打开事件文件;失败则自禁用。"""
    if _CTX["inited"]:
        return not _CTX["broken"]
    _CTX["inited"] = True
    _CTX["t_start"] = time.time()
    try:
        arm = os.environ.get("RPENT_P1_DEV0_ARM", "")
        if arm not in ("D0", "D1", "D2", "D3"):
            raise ValueError(f"RPENT_P1_DEV0_ARM invalid: {arm!r}")
        _CTX["arm"] = arm
        _CTX["episode_key"] = os.environ.get("RPENT_P1_DEV0_EPISODE_KEY", "unknown")
        horizon = int(os.environ.get("RPENT_P1_DEV0_HORIZON", DEFAULT_HORIZON))
        cap = int(os.environ.get("RPENT_P1_DEV0_EPISODE_STEP_CAP",
                                 DEFAULT_EPISODE_STEP_CAP))
        if horizon <= 0 or cap <= 0:
            raise ValueError("horizon/step cap must be positive")
        _CTX["horizon"] = horizon
        _CTX["episode_step_cap"] = cap
        # 事件文件必须在 episode output_dir 之外(Planner 文件工具不受限)
        out = os.environ.get("RPENT_P1_DEV0_OUT")
        if not out:
            out = f"/workspace/yjx/tmp/p1_dev0_fallback/{os.getpid()}"
        _CTX["out"] = Path(out)
        (_CTX["out"] / "probe_frames").mkdir(parents=True, exist_ok=True)
        _CTX["fh"] = open(_CTX["out"] / "p1_dev0_events.jsonl", "a",
                          encoding="utf-8")
        # 动态加载冻结 policy(路径可校验,不复制实现)
        policy_path = os.environ.get(
            "RPENT_P1_DEV0_POLICY",
            str(Path(__file__).resolve().parents[2]
                / "analysis" / "research_context" / "p1_dev0_policy.py"))
        spec = importlib.util.spec_from_file_location("p1_dev0_policy_frozen",
                                                      policy_path)
        mod = importlib.util.module_from_spec(spec)
        # dataclass 的字符串注解解析会查 sys.modules[cls.__module__],
        # 必须先注册再执行,否则 NoneType.__dict__ 崩
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _CTX["policy_mod"] = mod
        _CTX["policy_sha256"] = hashlib.sha256(
            Path(policy_path).read_bytes()).hexdigest()
        _emit({"ev": "init", "episode_key": _CTX["episode_key"], "arm": arm,
               "out": str(_CTX["out"]), "horizon": horizon,
               "episode_step_cap": cap, "policy_path": policy_path,
               "policy_sha256": _CTX["policy_sha256"],
               "probe": {"gripper": PROBE_GRIPPER, "steps": PROBE_STEPS},
               "pid": os.getpid()})
        return True
    except Exception as exc:
        _CTX["broken"] = True
        try:
            from rpent.utils.logging import get_logger
            get_logger("p1_dev0").error("P1-DEV0 init failed: %s", exc)
        except Exception:
            pass
        return False


def _eligible(name: str, result_dict: dict, env) -> bool:
    """首个合格 false-pick D2:pi0_pick ∧ success=False ∧ 非 terminal/truncated。"""
    if name != "pi0_pick":
        return False
    if not isinstance(result_dict, dict):
        return False
    if result_dict.get("success") is not False:
        return False
    if env.episode_terminated or env.episode_truncated:
        return False
    return True


def _maybe_audit(toolkit) -> None:
    """固定 horizon 审计:触发后 env_steps ≥ target 的首个技能边界取样一次。"""
    if not (_CTX["triggered"] and not _CTX["audited"]):
        return
    if _CTX["env_steps"] < _CTX["target_env_steps"]:
        return
    _take_audit(toolkit, "FIXED_HORIZON")


def _take_audit(toolkit, kind: str) -> None:
    """audit-only 取样:check_success + sim_measurement,只写外部事件文件。

    这些是 sim 真值通道,严禁进入任何 Planner 可见返回(本函数不返回值,
    只落盘;调用方也不得把结果并入工具返回)。
    """
    env = toolkit._primitives.env
    audit = {}
    try:
        audit["check_success"] = bool(env.check_success())
    except Exception as exc:
        audit["check_success_error"] = f"{type(exc).__name__}: {exc}"[:200]
    try:
        m = env.sim_measurement() or {}
        obs = m.get("obs") or {}
        audit["sim_measurement_obs_keys"] = sorted(obs.keys())
        audit["sim_measurement_obj_of_interest"] = list(
            m.get("obj_of_interest") or [])
        # 低维数值逐项记录(默认 str 化,jsonl 安全)
        audit["sim_measurement_obs"] = {
            k: [float(x) for x in _flat(v)] for k, v in obs.items()}
    except Exception as exc:
        audit["sim_measurement_error"] = f"{type(exc).__name__}: {exc}"[:200]
    audit["legal_context"] = _legal_state(env)
    _CTX["audited"] = True
    _CTX["audit_kind"] = kind
    _emit({
        "ev": "audit", "kind": kind,
        "episode_key": _CTX["episode_key"], "arm": _CTX["arm"],
        "target_env_steps": _CTX["target_env_steps"],
        "env_steps_at_audit": _CTX["env_steps"],
        "overshoot_env_steps": _CTX["env_steps"] - _CTX["target_env_steps"],
        "audit_only": audit,          # sim 真值:绝不进 Planner 视图
        "never_in_planner_view": True,
    })


def _flat(v):
    """把标量/数组压成可遍历的数字序列(数值观测记录用)。"""
    try:
        import numpy as np
        a = np.atleast_1d(np.asarray(v, dtype=float))
        return list(a)
    except Exception:
        return [v]


def _run_probe(toolkit) -> dict:
    """执行物理探测:直接调 primitives.set_gripper(不占 toolkit 步号)。

    返回事件记录(probe 结果 + 合法 post 观测 + 新鲜图像帧 + 成本)。
    """
    prim = toolkit._primitives
    env = prim.env
    steps_before = _CTX["env_steps"]
    t0 = time.monotonic()
    probe_result = prim.set_gripper(gripper=PROBE_GRIPPER, steps=PROBE_STEPS)
    wall_s = round(time.monotonic() - t0, 3)
    post_legal = _legal_state(env)
    # 探测后新鲜合法帧(与 dump_state 同通道的观测缓冲);写入实验外部目录
    frames = []
    try:
        import imageio
        import numpy as np
        main = getattr(prim, "_last_obs", {}).get("main_images")
        if main is not None:
            p = _CTX["out"] / "probe_frames" / "probe_agentview.png"
            imageio.imwrite(p, np.asarray(main))
            rec = _sha256_file(p)
            if rec:
                frames.append({"name": "probe_agentview", **rec})
        raw_wrist = env.raw_obs().get("robot0_eye_in_hand_image")
        if raw_wrist is not None:
            p = _CTX["out"] / "probe_frames" / "probe_wrist.png"
            imageio.imwrite(p, np.asarray(raw_wrist))
            rec = _sha256_file(p)
            if rec:
                frames.append({"name": "probe_wrist", **rec})
    except Exception as exc:
        frames.append({"name": "probe_frames_error",
                       "err": f"{type(exc).__name__}: {exc}"[:200]})
    rec = {
        "ev": "probe", "arm": _CTX["arm"],
        "probe_args": {"gripper": PROBE_GRIPPER, "steps": PROBE_STEPS},
        "result": probe_result,
        "env_steps_start": steps_before,
        "env_steps_end": _CTX["env_steps"],
        "env_steps_cost": _CTX["env_steps"] - steps_before,
        "wall_s": wall_s,
        "post_legal": post_legal,      # 白名单 proprio;None = 提取失败
        "post_frames": frames,
        "visible_to_planner": False,   # 探测观测只进事件文件(D1 遮蔽的结构保证)
    }
    _emit(rec)
    return rec


# ---- 公开 API(自守卫:绝不向上抛)----------------------------------------

def maybe_intervene(toolkit, name: str, kwargs: dict, result_dict: dict,
                    step_idx: int, elapsed: float):
    """_step 的 D2 边界钩子(默认关闭;LiberoToolkit._step 在 dump_state 后调用)。

    返回 None → 调用方走 vanilla 路径(未触发/未启用/故障回落);
    返回 dict → 该 dict 直接作为本次工具调用返回给 Planner
    (RETRY → 重试 pick 自身的视图;CONTINUE_CAUTION → 原失败 pick 的视图)。
    """
    if not enabled():
        return None
    try:
        if not _init():
            return None
        if _CTX["broken"] or _CTX["intervening"]:
            return None
        env = toolkit._primitives.env
        # 1) 固定 horizon 审计(先于触发判断:旧触发的 horizon 可能在本技能后越过)
        _maybe_audit(toolkit)
        # 2) 触发资格(每 episode 一次)
        if _CTX["triggered"] or not _eligible(name, result_dict, env):
            return None
        return _run_intervention(toolkit, name, kwargs, result_dict,
                                 step_idx, elapsed)
    except Exception as exc:
        _CTX["broken"] = True
        try:
            if _CTX["fh"] is not None:
                _emit({"ev": "hook_error", "episode_key": _CTX["episode_key"],
                       "arm": _CTX["arm"],
                       "where": "maybe_intervene",
                       "err": f"{type(exc).__name__}: {exc}"[:300],
                       "fallback": "vanilla_pick_view"})
        except Exception:
            pass
        return None


def _run_intervention(toolkit, name: str, kwargs: dict, result_dict: dict,
                      step_idx: int, elapsed: float):
    env = toolkit._primitives.env
    mod = _CTX["policy_mod"]
    _CTX["triggered"] = True
    _CTX["trigger_env_steps"] = _CTX["env_steps"]
    _CTX["target_env_steps"] = _CTX["env_steps"] + _CTX["horizon"]

    # 触发事件:完整合法快照(白名单 proprio + 已 dump 图像哈希)
    from rpent.utils.logging import get_output_dir
    out_dir = Path(get_output_dir())
    pre_legal = _legal_state(env)
    _emit({
        "ev": "trigger", "episode_key": _CTX["episode_key"], "arm": _CTX["arm"],
        "trigger": "FIRST_NONTERMINAL_NONTRUNCATED_FALSE_PICK_D2_ONLY",
        "step_idx": step_idx, "pick_kwargs": dict(kwargs),
        "pick_result": result_dict,
        "env_steps": _CTX["env_steps"],
        "target_env_steps": _CTX["target_env_steps"],
        "pre_legal": pre_legal,
        "pre_images": _boundary_images(out_dir, step_idx),
        "wall_s": round(time.time() - _CTX["t_start"], 1),
    })
    pre_eef_z = (pre_legal or {}).get("eef_z")

    # 物理探测:D0 无;D1/D2/D3 相同探测(D1 只记录、不进决策/视图)
    probe_ev = None
    if _CTX["arm"] != "D0":
        probe_ev = _run_probe(toolkit)
    post_legal = (probe_ev or {}).get("post_legal")
    frames = (probe_ev or {}).get("post_frames") or []
    visual_frame_available = any(
        f.get("name", "").startswith("probe_") and f.get("sha256")
        for f in frames)

    # 冻结 policy 决策(证据只含合法字段;payload fail-close 校验)
    evidence = mod.LegalEvidence(
        arm=_CTX["arm"],
        tool_success=False,
        terminal=bool(env.episode_terminated),
        truncated=bool(env.episode_truncated),
        pre_eef_z=(None if pre_eef_z is None else float(pre_eef_z)),
        post_eef_z=(None if (post_legal or {}).get("eef_z") is None
                    else float(post_legal["eef_z"])),
        post_gripper_gap=(None if (post_legal or {}).get("gripper_gap") is None
                          else float(post_legal["gripper_gap"])),
        age_env_steps=(0 if probe_ev is None
                       else _CTX["env_steps"] - probe_ev["env_steps_end"]),
        probe_performed=probe_ev is not None,
        visual_frame_available=bool(visual_frame_available),
        budget_remaining_env_steps=max(
            0, _CTX["episode_step_cap"] - _CTX["env_steps"]),
    )
    policy_input = {
        "arm": evidence.arm, "tool_success": evidence.tool_success,
        "terminal": evidence.terminal, "truncated": evidence.truncated,
        "pre_eef_z": evidence.pre_eef_z, "post_eef_z": evidence.post_eef_z,
        "post_gripper_gap": evidence.post_gripper_gap,
        "age_env_steps": evidence.age_env_steps,
        "probe_performed": evidence.probe_performed,
        "visual_frame_available": evidence.visual_frame_available,
        "budget_remaining_env_steps": evidence.budget_remaining_env_steps,
    }
    mod.deny_privileged_payload(policy_input)   # fail-close:特权键即抛
    decision = mod.choose(evidence)
    _emit({
        "ev": "decision", "episode_key": _CTX["episode_key"], "arm": _CTX["arm"],
        "policy_input": policy_input,
        "decision": decision.decision, "rationale_code": decision.rationale_code,
        "evidence_sources": list(decision.evidence_sources),
        "policy_sha256": _CTX["policy_sha256"],
    })

    # 动作执行:RETRY = 同 kwargs 的真实重试 pick(走完整 _step,占步号);
    # CONTINUE_CAUTION = 不重试,原样返回失败 pick 视图,Planner 自然继续;
    # ABSTAIN(D3)= 固定回落到与 D0 相同的盲重试(预注册回落,不自由发挥)。
    abstain_fallback = decision.decision == "ABSTAIN"
    do_retry = decision.decision in ("RETRY",) or abstain_fallback
    action_ev = {
        "ev": "action", "episode_key": _CTX["episode_key"], "arm": _CTX["arm"],
        "kind": ("RETRY" if do_retry else "CONTINUE_CAUTION"),
        "rationale_code": decision.rationale_code,
        "abstain_fallback": abstain_fallback,
    }
    steps_before_action = _CTX["env_steps"]
    t0 = time.monotonic()
    try:
        if do_retry:
            _CTX["intervening"] = True
            try:
                retry_view = toolkit._step("pi0_pick", **kwargs)
            finally:
                _CTX["intervening"] = False
            action_ev.update({
                "retry_step_idx": toolkit._next_step,
                "retry_result_summary": {
                    k: retry_view.get("log", {}).get("result", {}).get(k)
                    for k in ("success", "chunks_used", "libero_terminated")},
                "env_steps_cost": _CTX["env_steps"] - steps_before_action,
                "wall_s": round(time.monotonic() - t0, 3),
            })
            _emit(action_ev)
            return retry_view
        # CONTINUE_CAUTION:复刻 _step 原返回(失败 pick 自身视图,无新增信息)
        from robots.libero import tools as lt
        out = lt.view_driver_state(step_idx)
        out["agent_elapsed_s"] = elapsed
        action_ev.update({
            "env_steps_cost": _CTX["env_steps"] - steps_before_action,
            "wall_s": round(time.monotonic() - t0, 3),
        })
        _emit(action_ev)
        return out
    except Exception as exc:
        # 重试执行故障:如实记账并回落 vanilla(返回 None → 调用方返回 pick 视图)
        action_ev["error"] = f"{type(exc).__name__}: {exc}"[:300]
        action_ev["fallback"] = "vanilla_pick_view"
        _emit(action_ev)
        raise


def finalize(toolkit) -> None:
    """episode 结束钩子(LiberoToolkit.close() 调用;默认关闭)。

    1) 触发过但未到固定 horizon 的 episode 在此兜底取样 audit-only
       outcome(EPISODE_END);2) 落 episode_end 事件(总 env steps、
       触发/审计状态、全程墙钟)。绝不向上抛。
    """
    if not enabled():
        return
    try:
        if not _CTX["inited"]:
            return
        if _CTX["triggered"] and not _CTX["audited"]:
            _take_audit(toolkit, "EPISODE_END")
        _emit({
            "ev": "episode_end", "episode_key": _CTX["episode_key"],
            "arm": _CTX["arm"],
            "env_steps_total": _CTX["env_steps"],
            "triggered": _CTX["triggered"],
            "audited": _CTX["audited"], "audit_kind": _CTX["audit_kind"],
            "wall_s_total": round(time.time() - _CTX["t_start"], 1),
        })
        try:
            _CTX["fh"].close()
        except Exception:
            pass
    except Exception as exc:
        try:
            from rpent.utils.logging import get_logger
            get_logger("p1_dev0").warning("finalize failed: %s", exc)
        except Exception:
            pass
