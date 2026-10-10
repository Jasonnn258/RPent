"""P1-DEV1A 实验路径(默认关闭;环境变量 RPENT_P1_DEV1A=1 启用)。

与 p1_dev0 同一挂钩模式:toolkit._step / env_client 计步处各留一行默认
关闭的钩子;未启用时对 vanilla / Stage R / DEV0 **零行为差异**。

预注册协议:D-041(P1_L2_DEV1A_RESEARCH_REVIEW_AND_AUTHORIZATION_20261010)
· 至多 8 个新 episode(t9×4/t3×2/t5×2)、≤3 GPU·h、≤4h 墙钟、单 worker、
每集 ≤1500 env steps、每集最多一次失败触发观测、受控垂直提升 ≤2cm。

与 DEV0 的本质差异(只评价"同步物理标签的可用性与采样成本"):
- 触发后执行**一次**物理 probe = 固定夹爪闭合(≤10 env steps)+
  受控垂直提升(锁定参数,见下);probe 改变 sim 物理状态,但**所有
  Planner 动作保持盲态**:钩子永远返回 None(走 vanilla 失败视图),
  探测观测/接触真值只写 episode output_dir **之外**的 audit 文件。
- **audit-only 同刻接触快照**(t_trigger / t_close_end / 提升采样点 /
  t_lift_end):经 env_server.contact_snapshot(只读、零 env step、
  真 MuJoCo contact pairs;禁止 gap/最近表面/目标距离伪标签)。
- 探测后**立即终止**(manifest 预注册 TERMINATE_AFTER_PROBE):钩子写
  probe_done 事件,runner 监到即安全终止该 episode(Planner 全程盲)。

失败安全:任何异常 → 记 hook_error、停用本 episode 干预、回落 vanilla,
绝不杀死 episode(与 p1_dev0 相同纪律)。
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
# robosuite 约定(见 tools.move_to docstring):gripper +1 = 闭合/保持夹紧。
PROBE_GRIPPER = 1.0
PROBE_CLOSE_STEPS = 10          # 固定夹爪闭合 ≤10 env steps(D-041 上限)
# 受控垂直提升(锁定控制周期/参数;计入每集 1500 步):
LIFT_CMD_M = 0.018              # 指令提升量(安全上限 0.02m 之内)
LIFT_STEP_CLIP = 0.005          # 每步 EEF 指令限幅(m)
LIFT_MAX_STEPS = 24             # 提升最多 24 env steps
LIFT_STOP_DZ = 0.016            # 实测 EEF dz 达到即提前停(≤0.02 硬约束)
LIFT_TOL = 0.003                # servo 容差
LIFT_SAMPLE_DZ = (0.006, 0.012, 0.016)  # 提升窗口采样点(首次越过时取样)
POST_PROBE = "TERMINATE_AFTER_PROBE"    # 预注册二选一的另一项:统一盲继续
PROBE_BUDGET_STEPS = PROBE_CLOSE_STEPS + LIFT_MAX_STEPS  # 触发所需步数余量
EPISODE_STEP_CAP = 1500         # D-041 每集硬上限(env horizon 同值兜底)

# audit 快照在 contact/pose/image 四个通道上必须同刻(同一 env_step)
_SNAPSHOT_STEP_KEYS = ("env_step", "contact_env_step", "pose_env_step",
                       "image_env_step")

# 模块级上下文(每进程一个 episode;rpent CLI 每 episode 一个进程)
_CTX: dict = {
    "inited": False, "broken": False,
    "episode_key": None, "out": None, "fh": None,
    "spec": None, "truth_mod": None, "truth_sha256": None,
    "env_steps": 0,                # 物理 env-step 计数(env_client 钩子累加)
    "triggered": False, "probed": False,
    "snapshots": [],               # 本集 audit 快照(隔离容器,不进 Planner)
    "t_start": None,
}


def enabled() -> bool:
    """RPENT_P1_DEV1A=1 时启用(热路径保持极轻)。"""
    return os.environ.get("RPENT_P1_DEV1A") == "1"


def count_env_steps(n: int) -> None:
    """物理 env-step 计数(env_client.step/chunk_step 钩子调用;绝不抛)。

    probe 完成后(TERMINATE_AFTER_PROBE 窗口内)逐步落 steps 事件:
    runner 可能在任意时刻 kill 进程组,finalize 可能来不及跑,测量必须
    不依赖 episode_end —— 每步一行,kill 前最后一步即真实总数。
    """
    if not enabled():
        return
    try:
        _CTX["env_steps"] += int(n)
        if _CTX.get("probed") and _CTX["fh"] is not None:
            _CTX["fh"].write(json.dumps(
                {"ev": "steps", "env_steps": _CTX["env_steps"],
                 "t": round(time.time(), 3)}) + "\n")
            _CTX["fh"].flush()
    except Exception:
        pass


# ---- 内部 ------------------------------------------------------------------

def _emit(rec: dict) -> None:
    rec["t"] = round(time.time(), 3)
    _CTX["fh"].write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    _CTX["fh"].flush()


def _load_truth_module():
    """按路径加载冻结的 operational_truth(标签判据;不复制实现)。"""
    path = Path(__file__).resolve().parents[2] / "analysis" / \
        "research_context" / "p1_dev1a_operational_truth.py"
    spec = importlib.util.spec_from_file_location("p1_dev1a_truth_frozen", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _CTX["truth_mod"] = mod
    _CTX["truth_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _init() -> bool:
    """读取环境变量、加载冻结 geom spec 与判据模块;失败则自禁用。"""
    if _CTX["inited"]:
        return not _CTX["broken"]
    _CTX["inited"] = True
    _CTX["t_start"] = time.time()
    try:
        _CTX["episode_key"] = os.environ.get(
            "RPENT_P1_DEV1A_EPISODE_KEY", "unknown")
        spec_path = os.environ.get("RPENT_P1_DEV1A_SPEC", "")
        if not spec_path:
            raise ValueError("RPENT_P1_DEV1A_SPEC (frozen geom spec) required")
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)
        for key in ("task", "target", "target_geoms", "left_finger_geoms",
                    "right_finger_geoms", "support_geoms", "robot_self_geoms",
                    "geom_id"):
            if key not in spec:
                raise ValueError(f"geom spec missing key: {key}")
        _CTX["spec"] = spec
        _load_truth_module()
        # audit 输出必须在 episode output_dir 之外(Planner 文件工具不受限)
        out = os.environ.get("RPENT_P1_DEV1A_OUT")
        if not out:
            out = f"/workspace/yjx/tmp/p1_dev1a_fallback/{os.getpid()}"
        _CTX["out"] = Path(out)
        _CTX["out"].mkdir(parents=True, exist_ok=True)
        _CTX["fh"] = open(_CTX["out"] / "p1_dev1a_events.jsonl", "a",
                          encoding="utf-8")
        _emit({"ev": "init", "episode_key": _CTX["episode_key"],
               "out": str(_CTX["out"]), "spec_path": spec_path,
               "spec_task": spec["task"], "spec_target": spec["target"],
               "truth_sha256": _CTX["truth_sha256"],
               "probe": {"gripper": PROBE_GRIPPER,
                         "close_steps": PROBE_CLOSE_STEPS,
                         "lift_cmd_m": LIFT_CMD_M,
                         "lift_step_clip": LIFT_STEP_CLIP,
                         "lift_max_steps": LIFT_MAX_STEPS,
                         "lift_stop_dz": LIFT_STOP_DZ,
                         "lift_sample_dz": list(LIFT_SAMPLE_DZ)},
               "post_probe": POST_PROBE,
               "episode_step_cap": EPISODE_STEP_CAP,
               "pid": os.getpid()})
        return True
    except Exception as exc:
        _CTX["broken"] = True
        try:
            from rpent.utils.logging import get_logger
            get_logger("p1_dev1a").error("P1-DEV1A init failed: %s", exc)
        except Exception:
            pass
        return False


def _eligible(name: str, result_dict: dict, env) -> bool:
    """首个合格 false-pick:pi0_pick ∧ success=False ∧ 非 terminal/truncated。"""
    if name != "pi0_pick":
        return False
    if not isinstance(result_dict, dict):
        return False
    if result_dict.get("success") is not False:
        return False
    if env.episode_terminated or env.episode_truncated:
        return False
    return True


# ---- audit 快照 -----------------------------------------------------------

def _legal_envelope(env, eef_pos=None, eef_quat=None, gripper_qpos=None,
                    rgb_sha=None, wrist_sha=None) -> dict:
    """合法证据信封(严格 prohibit_audit_leak 白名单;不含任何 sim 真值)。"""
    raw = None
    try:
        raw = env.raw_obs()
    except Exception:
        raw = None
    if eef_pos is None and raw is not None:
        eef_pos = raw.get("robot0_eef_pos")
    if eef_quat is None and raw is not None:
        eef_quat = raw.get("robot0_eef_quat")
    if gripper_qpos is None and raw is not None:
        gripper_qpos = raw.get("robot0_gripper_qpos")
    gap = None
    if gripper_qpos is not None:
        try:
            gap = round(abs(float(gripper_qpos[0])) + abs(float(gripper_qpos[1])), 6)
        except Exception:
            gap = None
    return {
        "env_step": int(_CTX["env_steps"]),
        "rgb_sha256": rgb_sha,
        "wrist_sha256": wrist_sha,
        "gripper_gap": gap,
        "eef_pos": [float(x) for x in eef_pos] if eef_pos is not None else None,
        "eef_quat": [float(x) for x in eef_quat] if eef_quat is not None else None,
        "source": "libero_official_obs",
        "fresh": True,
        "validity": "VALID",
    }


def _image_hashes(toolkit) -> tuple[str | None, str | None]:
    """当前合法帧(与 dump_state 同通道的观测缓冲)sha256;(rgb, wrist)。"""
    rgb_sha = wrist_sha = None
    try:
        import numpy as np
        main = getattr(toolkit._primitives, "_last_obs", {}).get("main_images")
        if main is not None:
            rgb_sha = hashlib.sha256(
                np.asarray(main).tobytes()).hexdigest()
        raw = toolkit._primitives.env.raw_obs()
        wrist = raw.get("robot0_eye_in_hand_image")
        if wrist is not None:
            wrist_sha = hashlib.sha256(np.asarray(wrist).tobytes()).hexdigest()
    except Exception:
        pass
    return rgb_sha, wrist_sha


def _name_to_id(name: str):
    table = _CTX["spec"]["geom_id"]
    return table.get(name)


def _take_snapshot(toolkit, phase: str) -> dict:
    """audit-only 同刻接触快照(只读;经 env_server.contact_snapshot RPC)。

    返回冻结判据 validate_snapshot 兼容的 dict(int geom IDs + 真实
    contact pairs)+ 服务器侧同刻/零步进证据;全部只落隔离容器。
    """
    env = toolkit._primitives.env
    spec = _CTX["spec"]
    rpc = env.contact_snapshot({
        "target": spec["target"],
        "target_geoms": spec["target_geoms"],
        "left_finger_geoms": spec["left_finger_geoms"],
        "right_finger_geoms": spec["right_finger_geoms"],
        "support_geoms": spec["support_geoms"],
        "robot_self_geoms": spec["robot_self_geoms"],
    })
    step = int(_CTX["env_steps"])
    # 名字 → 冻结表 int id(未知名字 → None,validate 将判 UNKNOWN)
    def ids(names):
        out = []
        for n in names:
            i = _name_to_id(n)
            if i is None:
                return None
            out.append(int(i))
        return out
    pairs = []
    unresolved = []
    for a, b in rpc.get("pairs") or []:
        ia, ib = _name_to_id(a), _name_to_id(b)
        if ia is None or ib is None:
            unresolved.append([a, b])
        else:
            pairs.append([int(ia), int(ib)])
    obs = rpc.get("obs") or {}
    snap = {
        "env_step": step, "contact_env_step": step,
        "pose_env_step": step, "image_env_step": step,
        "target_instance": spec["target"],
        "target_geom_ids": ids(spec["target_geoms"]),
        "left_finger_geom_ids": ids(spec["left_finger_geoms"]),
        "right_finger_geom_ids": ids(spec["right_finger_geoms"]),
        "support_geom_ids": ids(spec["support_geoms"]),
        "contacts": pairs,
        "target_pos": obs.get(f"{spec['target']}_pos"),
        "eef_pos": obs.get("robot0_eef_pos"),
        # ---- 隔离 audit 附加(不进任何 Planner 可见返回)----
        "audit_phase": phase,
        "flags": rpc.get("flags"),
        "server_step_count": rpc.get("server_step_count"),
        "server_same_tick": rpc.get("same_tick"),
        "state_sha256": rpc.get("state_sha256"),
        "unresolved_names": unresolved,
        "rpc_wall_ms": rpc.get("wall_ms"),
        "rpc_queries": rpc.get("queries"),
        "eef_quat": obs.get("robot0_eef_quat"),
        "gripper_qpos": obs.get("robot0_gripper_qpos"),
    }
    _CTX["snapshots"].append(snap)
    return snap


# ---- 物理 probe -----------------------------------------------------------

def _run_probe(toolkit) -> dict:
    """一次固定闭合 + 一次受控垂直提升;沿途采 audit 快照;全程 Planner 盲。"""
    prim = toolkit._primitives
    env = prim.env
    steps0 = _CTX["env_steps"]

    # t_trigger:同刻合法信封 + 接触快照(先于任何物理扰动)
    rgb_sha, wrist_sha = _image_hashes(toolkit)
    trigger_env = _legal_envelope(env, rgb_sha=rgb_sha, wrist_sha=wrist_sha)
    snap_trigger = _take_snapshot(toolkit, "t_trigger")

    # 1) 固定夹爪闭合(≤10 env steps;直接调 primitives,不占 toolkit 步号)
    t0 = time.monotonic()
    close_result = prim.set_gripper(gripper=PROBE_GRIPPER,
                                    steps=PROBE_CLOSE_STEPS)
    close_wall = round(time.monotonic() - t0, 3)
    snap_close = _take_snapshot(toolkit, "t_close_end")
    rgb_c, wrist_c = _image_hashes(toolkit)
    close_env = _legal_envelope(env, rgb_sha=rgb_c, wrist_sha=wrist_c)

    # 2) 受控垂直提升(锁定参数;实测 dz ≥ LIFT_STOP_DZ 提前停)
    import numpy as np
    z_start = float(np.asarray(
        env.raw_obs()["robot0_eef_pos"])[2])
    lift_samples = []
    pending = list(LIFT_SAMPLE_DZ)
    lift_steps = 0
    t0 = time.monotonic()
    for _ in range(LIFT_MAX_STEPS):
        cur = prim._last_obs_eef_pos
        dz = float(cur[2]) - z_start
        while pending and dz >= pending[0]:
            want = pending.pop(0)
            lift_samples.append({
                "want_dz": want, "measured_dz": round(dz, 6),
                "snap": _take_snapshot(toolkit, f"lift_dz_{want}")})
        if dz >= LIFT_STOP_DZ:
            break
        target_z = z_start + LIFT_CMD_M
        diff = np.array([0.0, 0.0, target_z - float(cur[2])])
        action = np.zeros(7, dtype=np.float32)
        action[:3] = np.clip(np.clip(diff, -LIFT_STEP_CLIP, LIFT_STEP_CLIP)
                             / 0.05, -1, 1)
        action[6] = PROBE_GRIPPER          # 提升全程保持闭合
        prim._step_env(action)
        # 计数说明:生产路径 prim._step_env → LiberoEnvClient.step 已由
        # count_env_steps 钩子 +1,此处不再手动加(曾致 lift 步双重计数)
        lift_steps += 1
        if env.episode_terminated or env.episode_truncated:
            break
    lift_wall = round(time.monotonic() - t0, 3)
    z_end = float(np.asarray(env.raw_obs()["robot0_eef_pos"])[2])
    snap_lift_end = _take_snapshot(toolkit, "t_lift_end")
    rgb_l, wrist_l = _image_hashes(toolkit)
    lift_end_env = _legal_envelope(env, rgb_sha=rgb_l, wrist_sha=wrist_l)

    # 3) 冻结判据打标签(operational_truth;UNKNOWN 亦是合法结果)
    mod = _CTX["truth_mod"]
    close_state = mod.contact_state(snap_close)
    lift_states = [mod.contact_state(s["snap"]) for s in lift_samples]
    retention = (mod.retention_state(snap_close,
                                     [s["snap"] for s in lift_samples])
                 if len(lift_samples) >= mod.MIN_VALID_LIFT_SAMPLES
                 else {"retained": "UNKNOWN",
                       "reason": "INSUFFICIENT_LIFT_SAMPLES"})

    rec = {
        "ev": "probe", "episode_key": _CTX["episode_key"],
        "probe_args": {"gripper": PROBE_GRIPPER,
                       "close_steps": PROBE_CLOSE_STEPS,
                       "lift": {"cmd_m": LIFT_CMD_M,
                                "step_clip": LIFT_STEP_CLIP,
                                "max_steps": LIFT_MAX_STEPS,
                                "stop_dz": LIFT_STOP_DZ}},
        "close_result": close_result,
        "env_steps_start": steps0,
        "env_steps_end": _CTX["env_steps"],
        "env_steps_cost": _CTX["env_steps"] - steps0,
        "wall_s": {"close": close_wall, "lift": lift_wall},
        "eef_dz_m": round(z_end - z_start, 6),
        "lift_steps_used": lift_steps,
        # 合法信封(白名单字段;不含 sim 真值)
        "legal_envelopes": {"t_trigger": trigger_env,
                            "t_close_end": close_env,
                            "t_lift_end": lift_end_env},
        # audit-only 隔离真值(sim 接触/位姿;绝不进 Planner 视图)
        "audit_snapshots": {"t_trigger": snap_trigger,
                            "t_close_end": snap_close,
                            "lift_samples": lift_samples,
                            "t_lift_end": snap_lift_end},
        "labels": {"close_contact": close_state,
                   "lift_contacts": lift_states,
                   "retention": retention},
        "visible_to_planner": False,
    }
    _emit(rec)
    _emit({"ev": "probe_done", "episode_key": _CTX["episode_key"],
           "env_steps": _CTX["env_steps"],
           "post_probe": POST_PROBE})   # runner 监到此事件即安全终止
    return rec


# ---- 公开 API(自守卫:绝不向上抛)----------------------------------------

def maybe_probe(toolkit, name: str, kwargs: dict, result_dict: dict,
                step_idx: int, elapsed: float):
    """_step 的 D2 边界钩子(默认关闭;dump_state 之后、vanilla 视图之前)。

    永远返回 None → 调用方走 vanilla 失败视图(Planner 全程盲,与无钩子
    逐字节同构);probe 的全部观测只写隔离 audit 文件。
    """
    if not enabled():
        return None
    try:
        if not _init():
            return None
        if _CTX["broken"] or _CTX["triggered"]:
            return None
        env = toolkit._primitives.env
        if not _eligible(name, result_dict, env):
            return None
        _CTX["triggered"] = True
        # 触发前记录(ITT 分母;失败即 NOT_TRIGGERED/BUDGET 类)
        headroom = EPISODE_STEP_CAP - _CTX["env_steps"]
        if headroom < PROBE_BUDGET_STEPS:
            _emit({"ev": "trigger_skipped_budget",
                   "episode_key": _CTX["episode_key"],
                   "env_steps": _CTX["env_steps"], "headroom": headroom,
                   "needed": PROBE_BUDGET_STEPS})
            return None
        _emit({"ev": "trigger", "episode_key": _CTX["episode_key"],
               "trigger": "FIRST_NONTERMINAL_NONTRUNCATED_FALSE_PICK",
               "step_idx": step_idx, "pick_kwargs": dict(kwargs),
               "pick_result": result_dict,
               "env_steps": _CTX["env_steps"],
               "wall_s": round(time.time() - _CTX["t_start"], 1)})
        _run_probe(toolkit)
        _CTX["probed"] = True
        return None   # 盲态:vanilla 失败视图原样返回给 Planner
    except Exception as exc:
        _CTX["broken"] = True
        try:
            if _CTX["fh"] is not None:
                _emit({"ev": "hook_error", "episode_key": _CTX["episode_key"],
                       "where": "maybe_probe",
                       "err": f"{type(exc).__name__}: {exc}"[:300],
                       "fallback": "vanilla_pick_view"})
        except Exception:
            pass
        return None


def finalize(toolkit) -> None:
    """episode 结束钩子(LiberoToolkit.close() 调用;默认关闭)。

    落 episode_end 事件(总 env steps、触发/探测状态、标签摘要、墙钟);
    若探测已完成但 runner 尚未终止,这里补一个终止标记。绝不向上抛。
    """
    if not enabled():
        return
    try:
        if not _CTX["inited"]:
            return
        summary = None
        if _CTX["snapshots"]:
            truth = _CTX["truth_mod"]
            summary = {
                "n_snapshots": len(_CTX["snapshots"]),
                "n_valid": sum(1 for s in _CTX["snapshots"]
                               if truth.validate_snapshot(s)),
                "n_same_tick": sum(1 for s in _CTX["snapshots"]
                                   if s.get("server_same_tick")),
            }
        _emit({"ev": "episode_end", "episode_key": _CTX["episode_key"],
               "env_steps_total": _CTX["env_steps"],
               "cap": EPISODE_STEP_CAP,
               "cap_ok": _CTX["env_steps"] <= EPISODE_STEP_CAP,
               "triggered": _CTX["triggered"], "probed": _CTX["probed"],
               "snapshot_summary": summary,
               "wall_s_total": round(time.time() - _CTX["t_start"], 1)})
        try:
            _CTX["fh"].close()
        except Exception:
            pass
    except Exception as exc:
        try:
            from rpent.utils.logging import get_logger
            get_logger("p1_dev1a").warning("finalize failed: %s", exc)
        except Exception:
            pass
