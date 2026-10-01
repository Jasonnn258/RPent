#!/usr/bin/env python
"""Stage N1 — CLOSED-LOOP OPTION vs FIXED_MACRO runner(预注册已冻结)。

预注册:analysis/stageN1_option_spec.md(§1-§7)+ 机读镜像
resources/libero/options_stageN.yaml + 24 快照 manifest(三者已先于本文件
commit,commit affc4fc)。本文件只实现其中冻结的内容,不做任何门判定
(判定在 scripts/stageN1_analyze.py)。

设计要点(全部来自预注册):
- 共享一个 vla_server + sam3_server,每快照新起 env_server(同源 task/seed);
  重放 prefix 1..t0(含 t0)→ S=save_state → 6 rollouts(臂序 M,O 交错,
  R=0..2),每 rollout 前 restore_state(S)+set_obs+读回校验(必须 0.0);
- M = FIXED_MACRO:t0 冻结序列+参数;中间信息只记录(provenance)不进控制;
- O = CLOSED_LOOP_OPTION:同骨架 + R1/R2/R3 规则,决策改变记 realized
  (与同快照 M 冻结决策比对);
- 指标原料:env.check_success()(结尾)、逐物体 pos(z/xy 位移)、
  pi0_pick result(success / *_gripper_opening / libero_terminated);
- infra 错误(读回≠0 / env 崩溃 / 序列化失败)→ InfraError → 快照级重试
  ≤3 次,仍败则写 INFRA_ABORT 行,不混入指标;
- 本脚本不调 planner、不调 GLM、不写任何 planner 可见文本。

产物:
- analysis/stageN1_rollouts.csv(每 rollout 一行,spec §6)
- analysis/stageN1_information_provenance.jsonl(每信息事件一行)
- logs/stageN1/stageN1_rollouts_debug.jsonl(取证用,不 commit)

用法:
  MUJOCO_GL=osmesa python scripts/stageN1_runner.py --gpu 0 \
      [--limit 1] [--skip N] [--only snap_03]
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
import csv
import io
import json
import math
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# ---- 冻结常量(spec §1 / options_stageN.yaml,逐字对应)--------------------
P1_PICK_PROMPT = "pick up the black patterned bowl"
P1_SEG_PROMPT = "the black patterned bowl on the plate"
P2_SEG_BOWL = "the black patterned bowl"
P2_SEG_PLATE = "the plate"
MOVE_KW = dict(gripper=-1, step_clip=0.015, max_steps=60)
PICK_KW_P1 = dict(max_chunks=12, lift_thresh=0.05, gripper_closed_thresh=0.06)
PICK_KW_P2 = dict(max_chunks=20, lift_thresh=0.05, gripper_closed_thresh=0.06)
PICK_KW_P2_RETRY = dict(max_chunks=12, lift_thresh=0.05, gripper_closed_thresh=0.06)
SET_GRIP_KW = dict(gripper=1, steps=10)          # 锁爪(镜像源 episode 原文)
RELEASE_KW = dict(max_steps=30)
SEG_MIN_SCORE = 0.3
POSE_REALIZE_EPS = 0.01     # R2 descend xy 改变 >1cm 才算参数级 realized
OPEN_RETRY = 0.05           # P1 R3:final_gripper_opening > 0.05 → 空/松
HOLD_CLOSED = 0.03          # P2 R2:min_gripper_opening < 0.03 → 持有
Z_DESCEND = 0.99            # P1 descend
Z_PREPOS_HI = 1.155         # P2 预位
Z_PREPOS_LO = 1.135         # P2 retry 预位(更低)
Z_CARRY = 1.05              # P2 搬运
RIM_OFFSET = 0.045          # P2 rim-hook +y 偏置
R_REPEATS = 3               # §3:每臂 3 次重复
MAX_INFRA_RETRY = 3         # §7:快照级 infra 重试上限

RESULT_KEEP = {  # 原语 result 中保留进记录的字段(取证足够,控制流只用少数)
    "success", "libero_terminated", "final_gripper_opening",
    "min_gripper_opening", "peak_lift_m", "final_dist_m", "chunks_used",
    "max_chunks", "steps_used", "name", "target_xyz", "final_eef_pos",
}

CSV_COLS = [
    "procedure", "snapshot_id", "segment_id", "arm", "rollout_idx", "tercile",
    "task", "seed", "t0", "end_reason", "n_actions", "n_picks", "success",
    "target_name", "target_dz_m", "target_dxy_m", "other_max_dxy_m",
    "realized", "n_prov", "n_realized", "restore_readback", "wall_s",
    "infra_abort",
]


class InfraError(Exception):
    """infra 级失败(读回≠0 / env 崩溃):触发快照级重试,不混入指标。"""


# ---- 小工具 ----------------------------------------------------------------
def _read_rows(path: Path) -> list[dict]:
    """读 CSV(dict);跳过 # 注释行(manifest 头部)。"""
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def _load_source_steps(episode_dir: str) -> list[dict]:
    steps = json.load(open(Path(episode_dir) / "states.json"))
    return sorted(steps, key=lambda s: s.get("step_idx", 0))


def _task_language(steps: list[dict]) -> str | None:
    for s in steps:
        if s.get("task_language"):
            return s["task_language"]
    return None


def _pos_map(obs: dict) -> dict[str, list[float]]:
    """sim_measurement obs → {物体名: pos[3]}(逐物体键,J0 已验证布局)。"""
    out = {}
    for k, v in obs.items():
        if (k.endswith("_pos") and not k.startswith("robot0")
                and "_to_robot0_eef" not in k):
            try:
                out[k[:-4]] = [float(x) for x in v]
            except (TypeError, ValueError):
                pass
    return out


def _eef(obs: dict) -> list[float] | None:
    v = obs.get("robot0_eef_pos")
    return [float(x) for x in v] if v is not None else None


def _grip(obs: dict) -> float | None:
    q = obs.get("robot0_gripper_qpos")
    return float(abs(q[0]) + abs(q[1])) if q is not None else None


def _rsubset(result) -> dict:
    if not isinstance(result, dict):
        return {"value": str(result)[:120]}
    return {k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in result.items() if k in RESULT_KEEP}


def _seg_usable(seg: dict) -> tuple[bool, list[float] | None]:
    """segment 结果 → (score≥阈值 且 world_xyz 有效, xyz)。"""
    xyz = seg.get("world_xyz")
    ok = (seg.get("score") is not None and seg["score"] >= SEG_MIN_SCORE
          and isinstance(xyz, (list, tuple)) and len(xyz) == 3
          and all(math.isfinite(float(c)) for c in xyz))
    return ok, ([float(c) for c in xyz] if ok else None)


def _dxy(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _jsonable(o):
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


# ---- 单臂执行上下文 ---------------------------------------------------------
class Arm:
    """一个 rollout 内的执行上下文:动作计数、信息状态、provenance。

    info(spec §16 七字段)两臂都维护;M 只写不读,O 经 rule 读取。
    segment 是感知原语(不推进 env),不计入 5 动作预算。
    """

    def __init__(self, snap: dict, arm: str, rollout_idx: int,
                 toolkit, prims, env, outdir: Path, m_plan: list[dict]):
        self.snap, self.arm, self.ri = snap, arm, rollout_idx
        self.toolkit, self.prims, self.env = toolkit, prims, env
        self.outdir, self.m_plan = outdir, m_plan
        self.n_actions = 0
        self.n_picks = 0
        self.steps: list[dict] = []      # 取证明细(进 debug jsonl)
        self.prov: list[dict] = []       # provenance 事件
        self.info = {
            "target_visible": None, "target_grounded": None,
            "target_pose_valid": None, "support_relation": None,
            "latest_action_result": None, "latest_verifier_result": None,
            "retry_count": 0,
        }

    # -- 感知(不进预算) --
    def segment(self, prompt: str) -> dict:
        seg = self.prims.segment(prompt=prompt, camera="agentview",
                                 min_score=SEG_MIN_SCORE)
        usable, xyz = _seg_usable(seg)
        self.info["target_visible"] = bool(
            seg.get("score") is not None and seg["score"] >= SEG_MIN_SCORE)
        self.info["target_grounded"] = usable
        self.info["target_pose_valid"] = bool(usable and xyz[2] > 0.85)
        self.steps.append({"kind": "segment", "prompt": prompt,
                           "found": seg.get("found"),
                           "score": seg.get("score"),
                           "world_xyz": [round(c, 4) for c in xyz] if xyz
                           else None})
        return {**seg, "world_xyz": xyz}

    # -- 动作(进预算) --
    def exec(self, action: str, kwargs: dict) -> dict:
        if self.n_actions >= 5:  # §1 预算:5 动作(结构上到不了,防呆)
            raise InfraError("action budget exceeded")
        t1 = time.time()
        err = None
        try:
            self.toolkit._step(action, **kwargs)
        except Exception as exc:  # 原语异常按 infra 处理(§7)
            raise InfraError(f"{action} raised {type(exc).__name__}: "
                             f"{exc}") from exc
        try:
            sj = json.load(open(self.outdir / "states.json"))
            result = (sj[-1] or {}).get("result") or {}
        except Exception as exc:
            raise InfraError(f"tail read failed: {exc}") from exc
        self.n_actions += 1
        if action == "pi0_pick":
            self.n_picks += 1
        self.info["latest_action_result"] = {
            k: result.get(k) for k in ("success", "libero_terminated")
            if k in result}
        self.steps.append({
            "kind": "action", "action": action, "kwargs": _jsonable(kwargs),
            "result": _rsubset(result), "error": err,
            "elapsed_s": round(time.time() - t1, 1)})
        return result

    # -- provenance --
    def log(self, source: str, field: str, value, rule_id: str | None,
            decision: dict, realized: bool) -> None:
        self.prov.append({
            "procedure": self.snap["procedure"],
            "snapshot_id": self.snap["snapshot_id"],
            "segment_id": self.snap["segment_id"],
            "arm": self.arm, "rollout_idx": self.ri, "seq": len(self.prov),
            "info_event": {"source": source, "field": field, "value": value},
            "rule_id": rule_id, "decision": decision, "realized": realized,
        })

    def _flag(self) -> bool | None:
        """最近一步 result 的 libero_terminated(源语义:官方谓词旗标)。"""
        return self.info["latest_action_result"].get("libero_terminated")


# ---- 两 procedure 的双臂策略(spec §1 逐字实现)----------------------------
def policy_P1(arm: Arm, eef0: list[float]) -> str:
    """P1_RPS_REPICK:release-谓词未触发 → 重抓。

    M(冻结):retreat → descend(eef_t0.xy, 0.99) → pick → pick。
    O:retreat 后 R1 读旗标;R2 segment 改 descend xy;pick#1 后 R3 按
    final_gripper_opening 分支 retry / HOLD_END。
    返回 end_reason。
    """
    frozen_xy = [eef0[0], eef0[1]]
    retreat = {"action": "move_to",
               "kwargs": dict(xyz=[eef0[0], eef0[1], round(eef0[2] + 0.10, 4)],
                              **MOVE_KW)}

    def descend(xy):
        return {"action": "move_to",
                "kwargs": dict(xyz=[round(xy[0], 4), round(xy[1], 4),
                                    Z_DESCEND], **MOVE_KW)}

    def pick():
        return {"action": "pi0_pick",
                "kwargs": dict(prompt=P1_PICK_PROMPT, **PICK_KW_P1)}

    arm.exec(retreat["action"], retreat["kwargs"])          # 共享骨架 step 1

    if arm.arm == "M":
        # M:信息只记录(RECORD_ONLY),控制走冻结序列
        arm.log("state_flag", "libero_terminated", arm._flag(),
                "RECORD_ONLY", {"action": "none"}, False)
        seg = arm.segment(P1_SEG_PROMPT)
        arm.log("segment", "score/world_xyz",
                {"score": seg.get("score"), "world_xyz": seg.get("world_xyz")},
                "RECORD_ONLY", {"action": "none"}, False)
        arm.exec(*descend(frozen_xy).values())
        arm.exec(*pick().values())
        arm.info["latest_verifier_result"] = {"which": "pick1_recorded"}
        arm.log("pick_result", "final_gripper_opening",
                arm.steps[-1]["result"].get("final_gripper_opening"),
                "RECORD_ONLY", {"action": "pick2_frozen"}, False)
        arm.exec(*pick().values())                          # 固定重试
        arm.info["retry_count"] = 1
        return "MACRO_DONE"

    # O:R1 state_flag → termination
    flag = arm._flag()
    if flag is True:
        arm.log("state_flag", "libero_terminated", True, "R1_termination",
                {"action": "EARLY_STOP"}, True)
        return "EARLY_STOP"
    arm.log("state_flag", "libero_terminated", flag, "R1_termination",
            {"action": "continue"}, False)

    # O:R2 segment → pose_update
    seg = arm.segment(P1_SEG_PROMPT)
    usable, xyz = _seg_usable(seg)
    if usable:
        new_xy = [xyz[0], xyz[1]]
        realized = _dxy(new_xy, frozen_xy) > POSE_REALIZE_EPS
        arm.log("segment", "score/world_xyz",
                {"score": seg.get("score"), "world_xyz": xyz,
                 "frozen_xy": frozen_xy, "dxy_m": round(
                     _dxy(new_xy, frozen_xy), 4)},
                "R2_pose_update",
                {"action": "descend_xy := world_xyz.xy"}, realized)
    else:
        new_xy = frozen_xy
        arm.log("segment", "score/world_xyz",
                {"score": seg.get("score"),
                 "world_error": seg.get("world_error")},
                "R2_pose_update", {"action": "descend_xy := frozen"}, False)
    arm.exec(*descend(new_xy).values())

    # O:pick#1(与 M 同参)
    r1 = arm.exec(*pick().values())

    # O:R3 verifier_result → retry / hold
    term = r1.get("libero_terminated")
    if term is True:
        arm.log("state_flag", "libero_terminated", True, "R3_retry",
                {"action": "EARLY_STOP"}, True)
        return "EARLY_STOP"
    opening = r1.get("final_gripper_opening")
    arm.info["latest_verifier_result"] = {"final_gripper_opening": opening}
    if opening is not None and opening > OPEN_RETRY:
        # 空/松 → 重定位 + 预位 + pick#2(决策 ≠ M 冻结的 pick2 → realized)
        seg2 = arm.segment(P1_SEG_PROMPT)
        u2, xyz2 = _seg_usable(seg2)
        retry_xy = [xyz2[0], xyz2[1]] if u2 else new_xy
        arm.log("segment", "score/world_xyz",
                {"score": seg2.get("score"), "world_xyz": xyz2,
                 "retry_xy": retry_xy}, "R3_retry",
                {"action": "re_segment+move_to+pick2"}, True)
        arm.exec(*descend(retry_xy).values())
        arm.exec(*pick().values())
        arm.info["retry_count"] = 1
        return "RETRY_DONE"
    arm.log("pick_result", "final_gripper_opening", opening, "R3_retry",
            {"action": "HOLD_END(skip pick2)"}, True)
    return "HOLD_END"


def policy_P2(arm: Arm, task_lang: str | None,
              bowl_anchor: list[float], plate_anchor: list[float]) -> str:
    """P2_FG_RETRY:pi0_pick 失败(抓空/松脱)→ 预位重抓或搬运。

    M(冻结):move_to(bowl+(0,0.045),1.155) → pick(20) → set_gripper(+1)
    → move_to(plate+(0,0.045),1.05) → release。
    O:pick#1 后 R1 旗标 / R2 持有判定 / R3 重定位+低预位+重试 pick(12)。
    baseline anchors 由 t0 双臂同感冻结(快照级,不随 rollout 变)。
    """
    prepos = lambda anchor, z: {"action": "move_to", "kwargs": dict(
        xyz=[round(anchor[0], 4), round(anchor[1] + RIM_OFFSET, 4), z],
        **MOVE_KW)}
    pick1 = {"action": "pi0_pick",
             "kwargs": dict(prompt=task_lang or "", **PICK_KW_P2)}
    carry = [
        {"action": "set_gripper", "kwargs": dict(SET_GRIP_KW)},
        prepos(plate_anchor, Z_CARRY),
        {"action": "release", "kwargs": dict(RELEASE_KW)},
    ]

    arm.exec(*prepos(bowl_anchor, Z_PREPOS_HI).values())    # 共享骨架 step 1
    r1 = arm.exec(pick1["action"], pick1["kwargs"])         # 共享骨架 step 2

    if arm.arm == "M":
        arm.info["latest_verifier_result"] = {
            k: r1.get(k) for k in ("success", "min_gripper_opening")}
        arm.log("pick_result", "min_gripper_opening",
                r1.get("min_gripper_opening"), "RECORD_ONLY",
                {"action": "carry_frozen"}, False)
        for st in carry:
            arm.exec(st["action"], st["kwargs"])
        return "MACRO_DONE"

    # O:R1 state_flag → termination
    if r1.get("libero_terminated") is True:
        arm.log("state_flag", "libero_terminated", True, "R1_termination",
                {"action": "EARLY_STOP"}, True)
        return "EARLY_STOP"
    arm.log("state_flag", "libero_terminated",
            r1.get("libero_terminated"), "R1_termination",
            {"action": "continue"}, False)

    # O:R2 verifier_result → branch
    min_open = r1.get("min_gripper_opening")
    arm.info["latest_verifier_result"] = {"min_gripper_opening": min_open}
    if min_open is not None and min_open < HOLD_CLOSED:
        # 持有 → 锁爪+搬运+释放(与 M 冻结序列一致 → 非 realized)
        arm.log("pick_result", "min_gripper_opening", min_open, "R2_carry_end",
                {"action": "set_gripper+move_to_plate+release"}, False)
        for st in carry:
            arm.exec(st["action"], st["kwargs"])
        return "CARRY_END"

    # O:R3 segment → pose_update + retry(决策 ≠ M 冻结 carry → realized)
    seg = arm.segment(P2_SEG_BOWL)
    usable, xyz = _seg_usable(seg)
    new_anchor = [xyz[0], xyz[1]] if usable else bowl_anchor
    arm.log("segment", "score/world_xyz",
            {"score": seg.get("score"), "world_xyz": xyz,
             "frozen_anchor": bowl_anchor, "new_anchor": new_anchor},
            "R3_retry_end", {"action": "re_segment+move_to_low+pick_retry"},
            True)
    arm.exec(*prepos(new_anchor, Z_PREPOS_LO).values())
    retry = {"action": "pi0_pick",
             "kwargs": dict(prompt=task_lang or "", **PICK_KW_P2_RETRY)}
    arm.exec(retry["action"], retry["kwargs"])
    arm.info["retry_count"] = 1
    return "RETRY_DONE"


# ---- 快照执行 ---------------------------------------------------------------
def _attempt_snapshot(snap: dict, gpu: int, shared_kwargs: dict,
                      log_root: Path) -> dict:
    """单次尝试:env 起停 + 重放 + 12 rollout 之外的测量,返回打包结果。

    infra 异常向上抛 InfraError 由调用方重试;正常返回
    {rollouts:[…], prov:[…], baseline:{…}}。
    """
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    tag = f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}T{snap['t0']}"
    outdir = log_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}"
    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)

    env_spec = get_env_spec("libero")
    args = argparse.Namespace(
        suite="libero_spatial", task=int(snap["task"]), seed=int(snap["seed"]),
        max_episode_steps=10000, cuda_device=gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None,
    )
    daemons: list = []
    toolkit = None
    try:
        env_daemons, env_kwargs = env_spec.init_task_runtime(
            args, outdir, NullDashboardEventSink())
        daemons.extend(env_daemons)
        primitives_kwargs = dict(env_kwargs)
        primitives_kwargs.update(shared_kwargs)
        toolkit = get_toolkit(
            "libero", primitives_kwargs=primitives_kwargs,
            video_path=str(outdir / "episode.mp4"),
            dashboard_events=NullDashboardEventSink())
        prims = toolkit._primitives
        env = prims.env

        # --- 重放 prefix 1..t0(含 t0:失败恰发生在 t0)--------------------
        steps = _load_source_steps(snap["episode_dir"])
        t0i = int(snap["t0"])
        t_replay = time.time()
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
        replay_s = round(time.time() - t_replay, 1)

        # --- snapshot + baseline 测量 ------------------------------------
        S = env.save_state()
        base_meas = env.sim_measurement()
        base_obs = base_meas.get("obs") or {}
        pos0 = _pos_map(base_obs)
        eef0 = _eef(base_obs)
        if eef0 is None:
            raise InfraError("baseline robot0_eef_pos missing")
        obj_of_interest = base_meas.get("obj_of_interest") or []
        task_lang = _task_language(steps)
        baseline = {
            "state_len": int(len(S)), "pos0": pos0, "eef0": eef0,
            "check_success": bool(env.check_success()),
            "obj_of_interest": obj_of_interest, "task_language": task_lang,
            "replay_s": replay_s,
        }

        # --- P2:t0 基线双 anchor(双臂同感,M 参数在此冻结)--------------
        bowl_anchor = plate_anchor = None
        if snap["procedure"] == "P2_FG_RETRY":
            seg_bowl = prims.segment(prompt=P2_SEG_BOWL, camera="agentview",
                                     min_score=SEG_MIN_SCORE)
            seg_plate = prims.segment(prompt=P2_SEG_PLATE, camera="agentview",
                                      min_score=SEG_MIN_SCORE)
            ub, xb = _seg_usable(seg_bowl)
            up, xp = _seg_usable(seg_plate)
            bowl_anchor = [xb[0], xb[1]] if ub else [eef0[0], eef0[1]]
            plate_anchor = [xp[0], xp[1]] if up else [eef0[0], eef0[1]]
            baseline["anchors"] = {
                "bowl": {"xy": bowl_anchor, "score": seg_bowl.get("score"),
                         "usable": ub, "xyz": xb},
                "plate": {"xy": plate_anchor, "score": seg_plate.get("score"),
                          "usable": up, "xyz": xp},
                "fallback": not (ub and up),
            }

        # --- 6 rollouts:M,O 交错 × R=0..2(§3)---------------------------
        rollouts = []
        for ri in range(R_REPEATS):
            for arm_name in ("M", "O"):
                obs = env.restore_state(S)
                prims.set_obs(obs)
                readback = env.save_state()
                rb = float(abs(readback - S).max()) if (
                    len(readback) == len(S)) else -1.0
                if rb != 0.0:
                    raise InfraError(f"restore readback {rb} != 0 "
                                     f"({snap['snapshot_id']} {arm_name} r{ri})")
                t_wall = time.time()
                arm = Arm(snap, arm_name, ri, toolkit, prims, env, outdir, [])
                if snap["procedure"] == "P1_RPS_REPICK":
                    end_reason = policy_P1(arm, eef0)
                else:
                    end_reason = policy_P2(arm, task_lang, bowl_anchor,
                                           plate_anchor)
                final_meas = env.sim_measurement()
                posN = _pos_map(final_meas.get("obs") or {})
                succ = bool(env.check_success())
                target = obj_of_interest[0] if obj_of_interest else None
                dz = dxy_t = other_max = None
                if target and target in pos0 and target in posN:
                    dz = round(posN[target][2] - pos0[target][2], 4)
                    dxy_t = round(_dxy(posN[target], pos0[target]), 4)
                    others = [n for n in pos0 if n != target and n in posN]
                    other_max = round(max(
                        (_dxy(posN[n], pos0[n]) for n in others), default=0.0
                    ), 4) if others else 0.0
                n_real = sum(1 for p in arm.prov if p["realized"])
                rollouts.append({
                    "procedure": snap["procedure"],
                    "snapshot_id": snap["snapshot_id"],
                    "segment_id": snap["segment_id"],
                    "arm": arm_name, "rollout_idx": ri,
                    "tercile": snap["tercile"], "task": snap["task"],
                    "seed": snap["seed"], "t0": snap["t0"],
                    "end_reason": end_reason, "n_actions": arm.n_actions,
                    "n_picks": arm.n_picks, "success": succ,
                    "target_name": target, "target_dz_m": dz,
                    "target_dxy_m": dxy_t, "other_max_dxy_m": other_max,
                    "realized": n_real > 0, "n_prov": len(arm.prov),
                    "n_realized": n_real, "restore_readback": rb,
                    "wall_s": round(time.time() - t_wall, 1),
                    "infra_abort": None,
                    "_info": arm.info, "_steps": arm.steps,
                    "_prov": arm.prov,
                })
        return {"rollouts": rollouts, "baseline": baseline, "outdir": outdir}
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


def run_snapshot(snap: dict, gpu: int, shared_kwargs: dict, log_root: Path,
                 csv_w, prov_f, debug_f) -> bool:
    """带 ≤3 次 infra 重试的快照执行;返回是否全部 6 rollout 成功落盘。"""
    for attempt in range(1, MAX_INFRA_RETRY + 1):
        reason = None
        try:
            packed = _attempt_snapshot(snap, gpu, shared_kwargs, log_root)
        except InfraError as exc:
            reason = f"{type(exc).__name__}: {exc}"
            print(f"[stageN1]   INFRA attempt {attempt}/{MAX_INFRA_RETRY} "
                  f"{reason[:160]}", flush=True)
            continue
        except Exception as exc:  # 非 InfraError 的意外异常同样按 infra 重试
            reason = f"{type(exc).__name__}: {exc}"
            print(f"[stageN1]   UNEXPECTED attempt {attempt} "
                  f"{reason[:160]}\n{traceback.format_exc()[-800:]}", flush=True)
            continue
        for row in packed["rollouts"]:
            prov_lines = row.pop("_prov")
            info_final = row.pop("_info")
            steps_dbg = row.pop("_steps")
            csv_w.writerow({c: row.get(c) for c in CSV_COLS})
            for p in prov_lines:
                prov_f.write(json.dumps(p, ensure_ascii=False, default=str)
                             + "\n")
            prov_f.flush()
            debug_f.write(json.dumps({
                "row": {c: row.get(c) for c in CSV_COLS},
                "info_state_final": info_final, "steps": steps_dbg,
                "baseline": packed["baseline"],
            }, ensure_ascii=False, default=str) + "\n")
            debug_f.flush()
        return True
    # 3 次全败:写 INFRA_ABORT 标记行(分析层过滤,不进指标)
    csv_w.writerow({
        "procedure": snap["procedure"], "snapshot_id": snap["snapshot_id"],
        "segment_id": snap["segment_id"], "arm": "INFRA_ABORT",
        "rollout_idx": "", "tercile": snap["tercile"], "task": snap["task"],
        "seed": snap["seed"], "t0": snap["t0"], "end_reason": "",
        "n_actions": "", "n_picks": "", "success": "", "target_name": "",
        "target_dz_m": "", "target_dxy_m": "", "other_max_dxy_m": "",
        "realized": "", "n_prov": "", "n_realized": "",
        "restore_readback": "", "wall_s": "", "infra_abort": "3_attempts",
    })
    return False


# ---- 主入口 -----------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default="analysis/stageN1_split_manifest.csv")
    ap.add_argument("--out", default="analysis/stageN1_rollouts.csv")
    ap.add_argument("--prov", default="analysis/stageN1_information_provenance.jsonl")
    ap.add_argument("--log-root", default="logs/stageN1")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None,
                    help="只跑前 N 个快照(冒烟用;全量运行禁止)")
    ap.add_argument("--skip", type=int, default=0, help="跳过前 N 个(断点续跑)")
    ap.add_argument("--only", default=None, help="只跑指定 snapshot_id(冒烟用)")
    args = ap.parse_args()

    snaps = _read_rows(REPO / args.manifest)
    if args.only:
        snaps = [s for s in snaps if s["snapshot_id"] == args.only]
    else:
        snaps = snaps[args.skip:] if args.skip else snaps
        if args.limit:
            snaps = snaps[: args.limit]
    assert snaps, "空快照集(检查 --only/--skip/--limit)"

    log_root = REPO / args.log_root
    log_root.mkdir(parents=True, exist_ok=True)
    out_path, prov_path = REPO / args.out, REPO / args.prov
    debug_path = log_root / "stageN1_rollouts_debug.jsonl"

    # 断点续跑:已有完整 6 行的快照跳过(冒烟/中断后 --skip 之外的兜底)
    done: set[str] = set()
    if out_path.exists():
        counts: dict[str, int] = {}
        for r in _read_rows(out_path):
            counts[r["snapshot_id"]] = counts.get(r["snapshot_id"], 0) + 1
        done = {k for k, v in counts.items() if v >= 6}
        if done:
            print(f"[stageN1] resume:{len(done)} 快照已有 ≥6 行,跳过 "
                  f"{sorted(done)}", flush=True)
    todo = [s for s in snaps if s["snapshot_id"] not in done]
    if not todo:
        print("[stageN1] nothing to do(全部已完成)", flush=True)
        return 0

    # loopback 代理放行后才能 import RPC 层
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = log_root / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)

    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    print(f"[stageN1] boot shared vla+sam3 on gpu{args.gpu} ...", flush=True)
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())
    print(f"[stageN1] shared runtime ready: {sorted(shared_kwargs)}", flush=True)

    n_ok = n_abort = 0
    new_out = not out_path.exists()
    try:
        with open(out_path, "a", newline="", encoding="utf-8") as cf, \
                open(prov_path, "a", encoding="utf-8") as pf, \
                open(debug_path, "a", encoding="utf-8") as df:
            writer = csv.DictWriter(cf, fieldnames=CSV_COLS)
            if new_out:
                writer.writeheader()
                cf.flush()
            for i, snap in enumerate(todo):
                print(f"[stageN1] {i+1}/{len(todo)} {snap['snapshot_id']} "
                      f"{snap['procedure']} t{snap['task']}s{snap['seed']} "
                      f"T={snap['t0']} {snap['tercile']} ...", flush=True)
                t0 = time.time()
                ok = run_snapshot(snap, args.gpu, shared_kwargs, log_root,
                                  writer, pf, df)
                cf.flush()
                if ok:
                    n_ok += 1
                    print(f"[stageN1]   ok ({round(time.time()-t0,1)}s)",
                          flush=True)
                else:
                    n_abort += 1
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    print(f"[stageN1] done: snapshots ok={n_ok} infra_aborted={n_abort} "
          f"-> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    # GL 环境纪律(CLAUDE.md,同 stageL_verify.py 先例):本容器必须 osmesa;
    # env_server.py 对 PYOPENGL_PLATFORM 做 setdefault("egl"),父进程只 unset
    # 会被填回 → 必须显式 =osmesa 覆盖;tokenizer 走持久卷 openpi 缓存,
    # 否则 vla_server 会卡在 gs:// 下载(本机网络不通 → healthz 300s 超时)。
    _e = __import__("os").environ
    _e["MUJOCO_GL"] = "osmesa"
    _e["PYOPENGL_PLATFORM"] = "osmesa"
    for _bad in ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE"):
        _e.pop(_bad, None)
    _e.setdefault("OPENPI_DATA_HOME",
                  "/workspace/yjx/rpent_data/.cache/openpi")
    raise SystemExit(main())
