#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage P 共享运行时:candidate 采样 / chunk 执行 / chunk 级测量 / 续跑 / 标签。

预注册:analysis/stageP_prereg.md §3(candidate 定义与 continuation contract)、
§4(physical verifier 与标签)、§5(chunk 级观测量)。本模块只实现冻结内容。

关键事实(analysis/stageP_candidate_interface.md):
- Pi0.5 每次前向 = 固定 [5,7] action chunk(vla_server num_action_chunks=5);
- `predict_action_batch(obs, mode="eval")` 纯推理、不碰 env → candidate 可
  执行前生成、可序列化;
- `env.chunk_step(actions)` 接受任意 chunk → 已保存 chunk 可精确重放;
- `pi0_pick` = 闭环技能(≤24 chunk,早停 descent≥0.10 ∧ ascent≥0.05 ∧
  grip<0.06),故 candidate 只取第一个 chunk,之后进冻结 continuation。

被复用:stageP_replay.py(P0)/ stageP_geometry.py(P1)/ stageP3_online.py(P3)。
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt          # boot/restore/measure/契约/环境三件套(零改动复用)

# ---- 冻结常量(prereg §3/§4)------------------------------------------------
CHUNK_H, CHUNK_DIM = 5, 7       # vla_server num_action_chunks / action_dim
R_CONT = 3                      # continuation 重复次数(seed 不可控,§7)
PICK_MAX_CHUNKS = 24            # 总 chunk 预算(含 candidate,同 pi0_pick)
PICK_LIFT_THRESH = 0.05         # pi0_pick 默认早停阈值(逐字)
PICK_GRIP_CLOSED = 0.06
PICK_DESCENT_COMMIT = 0.10
# chunk 级分类阈值(prereg §5,冻结)
EE_CLASS_DZ = 0.015
EE_CLASS_DXY = 0.03
GRIP_DELTA = 0.01
OBJ_LIFT_DZ = 0.01
OBJ_HARM_DZ = -0.01
OBJ_HARM_DXY = 0.03
OBJ_DISP_FLAG_DXY = 0.02
OBJ_DISP_FLAG_DZ = 0.02
EE_NEAR_TARGET = 0.10
# 标签契约(prereg §4,与 Stage O §5.1-FG / RE2 / RE3 同源)
FG_LIFT_DZ = 0.03
FG_FOLLOW_DXY = 0.10
HARM_DZ = -0.03
HARM_DXY = 0.08
OBJ_Z_MIN = 0.80
EEF_X = (-0.60, 0.35)
EEF_Y = (-0.45, 0.50)
EEF_Z = (0.80, 1.35)


def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


# ---- candidate 生成与执行 ----------------------------------------------------
def sample_candidate(prims, prompt: str):
    """从当前观测采一个 candidate chunk(镜像 _vlm_chunk 的 obs 处理,tools.py:175-200)。

    纯推理调用:不触碰 env。prompt 覆盖与 extra_view_images 缺省逐字同
    _vlm_chunk,保证 candidate 与标准 pi0_pick 第一 chunk 同条件。
    """
    obs = prims._last_obs
    orig = obs.get("task_descriptions")
    try:
        obs["task_descriptions"] = prompt
        obs.setdefault("extra_view_images", None)
        actions, _ = prims.model.predict_action_batch(obs, mode="eval")
    finally:
        if orig is not None:
            obs["task_descriptions"] = orig
    a = np.asarray(actions, dtype=np.float32)
    assert a.shape == (CHUNK_H, CHUNK_DIM), f"candidate shape {a.shape}"
    return a


def chunk_sha(actions) -> str:
    """chunk 内容指纹(sha256 前 16 hex;provenance 用)。"""
    a = np.asarray(actions, dtype=np.float32)
    return hashlib.sha256(a.tobytes()).hexdigest()[:16]


def execute_chunk(prims, actions):
    """执行一个已保存的 chunk(零模型调用);返回 chunk 内是否触发终止。"""
    chunk_obs, _r, _t, _tr, _i = prims.env.chunk_step(actions)
    obs = chunk_obs[-1] if prims.env.return_all_frames else chunk_obs
    prims.set_obs(obs)
    term = bool(getattr(prims.env, "episode_terminated", False)
                or getattr(prims.env, "episode_truncated", False))
    return term


# ---- chunk 级测量(prereg §5)----------------------------------------------
def gripper_now(prims) -> float:
    return float(prims._last_obs_gripper)


def checkpoint(ctx, target: str | None) -> dict:
    """一个测量点:rt.measure 全字段(标签/审计用)+ chunk 分类所需派生量。

    统一 checkpoint 格式:eef/pos/check_success/terminated 来自 rt.measure,
    obj/grip 为 chunk 级分类与数值指纹追加字段。
    """
    m = rt.measure(ctx["env"])
    m["obj"] = list(m["pos"][target]) if target and target in m["pos"] else None
    m["grip"] = gripper_now(ctx["prims"])
    return m


def classify_chunk(pre: dict, post: dict) -> dict:
    """prereg §5 冻结操作化:transition/contact/object 三类 + 3 flags。"""
    dz = (post["eef"][2] - pre["eef"][2]) if pre["eef"] and post["eef"] else 0.0
    dxy = math.hypot(post["eef"][0] - pre["eef"][0],
                     post["eef"][1] - pre["eef"][1]) if pre["eef"] and post["eef"] else 0.0
    if dz <= -EE_CLASS_DZ:
        ee_cls = "DESCEND"
    elif dz >= EE_CLASS_DZ:
        ee_cls = "ASCEND"
    elif dxy >= EE_CLASS_DXY:
        ee_cls = "LATERAL"
    else:
        ee_cls = "STATIONARY"
    dgrip = post["grip"] - pre["grip"]
    contact = ("CLOSING" if dgrip <= -GRIP_DELTA
               else "OPENING" if dgrip >= GRIP_DELTA else "HOLD")
    odz = odxy = None
    if pre["obj"] and post["obj"]:
        odz = post["obj"][2] - pre["obj"][2]
        odxy = math.hypot(post["obj"][0] - pre["obj"][0],
                          post["obj"][1] - pre["obj"][1])
        if odz >= OBJ_LIFT_DZ:
            obj_cls = "TOWARD_LIFT"
        elif odz <= OBJ_HARM_DZ or odxy >= OBJ_HARM_DXY:
            obj_cls = "HARM_DISP"
        else:
            obj_cls = "UNMOVED"
    else:
        obj_cls = "UNSEEN"
    near = False
    if post["obj"] and post["eef"]:
        near = math.hypot(post["obj"][0] - post["eef"][0],
                          post["obj"][1] - post["eef"][1]) <= EE_NEAR_TARGET
    return {
        "ee_class": ee_cls, "contact_class": contact, "obj_class": obj_cls,
        "flag_target_displaced": bool(
            (odxy is not None and odxy >= OBJ_DISP_FLAG_DXY)
            or (odz is not None and abs(odz) >= OBJ_DISP_FLAG_DZ)),
        "flag_gripper_closed": bool(post["grip"] < PICK_GRIP_CLOSED),
        "flag_ee_near_target": bool(near),
        "end_eef": post["eef"], "obj_disp": ([post["obj"][0] - pre["obj"][0],
                                              post["obj"][1] - pre["obj"][1],
                                              post["obj"][2] - pre["obj"][2]]
                                             if pre["obj"] and post["obj"]
                                             else None),
        "ee_dz": round(dz, 4), "ee_dxy": round(dxy, 4),
        "odz": None if odz is None else round(odz, 4),
        "odxy": None if odxy is None else round(odxy, 4),
        "terminated_in_chunk": bool(post["terminated"]),
    }


# ---- 冻结 continuation(§3;与 pi0_pick 闭环逐字同构)------------------------
def run_continuation(prims, prompt: str, chunks_already: int = 1,
                     max_chunks: int = PICK_MAX_CHUNKS, on_chunk=None) -> dict:
    """candidate chunk 之后的冻结标准 Pi0.5 续跑。

    与 tools.pi0_pick 的差异仅:第 1 个 chunk 已由 candidate 消耗
    (chunks_already=1),预算 = max_chunks - chunks_already;循环体/早停/
    返回字段逐字同构(tools.py:202-275)。seed 不可控 → 随机性由 R_CONT
    次重复吸收(§7)。on_chunk:每个 continuation chunk 后调用一次
    (prereg §4 测量点 = 每 continuation chunk 后)。
    """
    start_z = prims._last_obs_eef_z
    peak_z = min_z = start_z
    post_min_peak_z = start_z
    min_grip = last_grip = prims._last_obs_gripper
    descent_done = success = False
    chunks_used = 0
    for c in range(max_chunks - chunks_already):
        prims._vlm_chunk(prompt)          # 标准闭环路径(含 prompt 覆盖)
        chunks_used = c + 1
        if on_chunk is not None:
            on_chunk(c + 1)
        z, grip = prims._last_obs_eef_z, prims._last_obs_gripper
        peak_z = max(peak_z, z)
        if z < min_z:
            min_z, post_min_peak_z = z, z
        else:
            post_min_peak_z = max(post_min_peak_z, z)
        if (start_z - min_z) >= PICK_DESCENT_COMMIT:
            descent_done = True
        min_grip = min(min_grip, grip)
        last_grip = grip
        ascended = (post_min_peak_z - min_z) >= PICK_LIFT_THRESH
        closed = grip < PICK_GRIP_CLOSED
        if descent_done and ascended and closed:
            success = True
            break
        if prims.env.episode_terminated or prims.env.episode_truncated:
            success = prims.env.episode_terminated
            break
    return {"name": "pick", "instruction": prompt, "success": success,
            "chunks_used": chunks_used + chunks_already, "max_chunks": max_chunks,
            "peak_lift_m": post_min_peak_z - min_z,
            "min_gripper_opening": min_grip,
            "final_gripper_opening": last_grip,
            "libero_terminated": bool(prims.env.episode_terminated)}


# ---- 标签(prereg §4;优先级 RECOVERY > HARM > NO_EFFECT)--------------------
def _harm(cur: dict, base: dict, target: str | None) -> bool:
    if target and target in cur["pos"] and target in base["pos"]:
        dzc = cur["pos"][target][2] - base["pos"][target][2]
        dxyc = math.hypot(cur["pos"][target][0] - base["pos"][target][0],
                          cur["pos"][target][1] - base["pos"][target][1])
        if dzc < HARM_DZ or dxyc > HARM_DXY:
            return True
    for p in cur["pos"].values():
        if p[2] < OBJ_Z_MIN:
            return True
    e = cur["eef"]
    if e and all(math.isfinite(c) for c in e) and not (
            EEF_X[0] < e[0] < EEF_X[1] and EEF_Y[0] < e[1] < EEF_Y[1]
            and EEF_Z[0] < e[2] < EEF_Z[1]):
        return True
    return False


def outcome_label(family: str, checkpoints: list[dict], base: dict,
                  target: str | None, pick_result: dict | None = None) -> str:
    """对一次 candidate(+continuation)的测量点序列打标签。

    checkpoints:候选 chunk 后 + 每 continuation chunk 后 + 终态的 rt.measure
    结果(调用方收集)。RECOVERY = 任一点 FG 契约/check_success;HARM = 未
    RECOVERY 时任一点 harm 条件(§4 冻结优先级)。
    """
    for cur in checkpoints:
        if cur["check_success"]:
            return "RECOVERY"
        if family == "FALSE_GRASP" and target \
                and target in cur["pos"] and target in base["pos"]:
            dz = cur["pos"][target][2] - base["pos"][target][2]
            if dz >= FG_LIFT_DZ and cur["eef"] is not None \
                    and math.hypot(cur["pos"][target][0] - cur["eef"][0],
                                   cur["pos"][target][1] - cur["eef"][1]) \
                    <= FG_FOLLOW_DXY:
                return "RECOVERY"
    for cur in checkpoints:
        if _harm(cur, base, target):
            return "HARM"
    return "NO_EFFECT"


# ---- P1/P3 复用:candidate 全流程(chunk → S_j → R_CONT 续跑 → 标签)---------
def execute_candidate_with_continuation(ctx, snap: dict, prompt: str, actions,
                                        checkpoints_out: list[dict]) -> dict:
    """§3/§7 冻结流程:restore(S) → chunk → 存 S_j → 3 次独立续跑 → 标签。

    测量点(prereg §4):candidate chunk 后 + 每 continuation chunk 后 +
    终态;全部以 checkpoint() 统一格式追加进 checkpoints_out(审计用)。
    S_j = post-chunk 态:物理在 (S, chunk) 下确定 → 同 candidate 的 3 次
    续跑都从 S_j 独立 restore(等价于从 S 重放同一 chunk)。
    """
    family = snap["family"]
    target = ctx["target"]
    rt.restore_checked(ctx, f"{snap['snapshot_id']} cand-exec")
    pre = checkpoint(ctx, target)
    term = execute_chunk(ctx["prims"], actions)
    post = checkpoint(ctx, target)
    S_j = ctx["env"].save_state()          # post-chunk 态(确定性)
    labels, conts = [], []
    for r in range(R_CONT):
        obs = ctx["env"].restore_state(S_j)
        ctx["prims"].set_obs(obs)
        cps = [post]
        res = {"cont_idx": r + 1, "terminated_in_chunk": term}
        if term:
            # chunk 内已终止:续跑无意义(chunk_step 有终止闩断言),
            # 直接以 post 态判(契约点仍测)
            cps.append(checkpoint(ctx, target))
        else:
            def on_chunk(_i, _target=target, _cps=cps):
                _cps.append(checkpoint(ctx, _target))
            pick = run_continuation(ctx["prims"], prompt, on_chunk=on_chunk)
            res["pick"] = pick
            cps.append(checkpoint(ctx, target))       # 终态
        checkpoints_out.extend(cps)
        labels.append(outcome_label(family, cps, ctx["base"], target))
        conts.append(res)
    n_rec = sum(1 for l in labels if l == "RECOVERY")
    n_harm = sum(1 for l in labels if l == "HARM")
    cand = "RECOVERY" if n_rec else ("HARM" if n_harm else "NO_EFFECT")
    return {"cand_label": cand, "labels": labels, "n_rec": n_rec,
            "n_harm": n_harm, "conts": conts, "chunk_pre": pre,
            "chunk_post": post, "terminated_in_chunk": term}


def pre_prompt_of(snap: dict) -> str:
    """recovery command:重放确定的 step≤t0 最后一条 Pi0.5 族命令 prompt。"""
    steps = rt.load_steps(snap["episode_dir"])
    cmd = rt.last_pi05_cmd(steps, int(snap["t0"]))
    assert cmd is not None, f"{snap['snapshot_id']} prefix 无 pi05 命令"
    return cmd[1].get("prompt")
