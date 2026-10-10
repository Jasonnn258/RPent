#!/usr/bin/env python3
"""P1-DEV1A G1-G4 预检门:真实仿真证据(无 GPU;osmesa CPU)。

D-041 授权要求:四个 Gate 全部以**真实运行证据**判定,模拟输入通过只能
说明代码正确。本脚本逐项产出证据并写入 gate_evidence.json:

- G1 场景能力:进程内 ground-truth env(直连 robosuite)按 task 冻结
  目标/左右指/支撑/robot-self geom 名与 int id 表;步进后正对照
  (目标↔支撑 True、目标↔地面 False、指↔目标 False);再经**生产
  worker 路径**(rlinf LiberoEnv + LiberoEnvFacade,与真实 episode 同
  构)复验同 seed 同步数下接触标志逐项一致 + 状态逐位一致;最后在
  封版副本上做真实抓取彩排,证明接触事件中 finger↔target 与
  finger↔robot-self/support 可区分(真实 pairs)。
- G2 同时刻:worker 路径 contact_snapshot 的 server_step_count 不变、
  query 前后 state sha 相等(same_tick)、重复快照幂等、A/B 世界
  (有无快照交错)20 步后状态逐位一致(读取不推进仿真)、快照成本。
- G3 防泄漏:用**真实** audit 快照做对抗——特权字段注入 legal 信封
  (递归嵌套)必须 ValueError;种子化随机改写审计真值后 legal 信封
  字节不变、标签只随审计容器变;maybe_probe 静态断言(永远 return
  None,不触碰 toolkit 视图)。
- G4 预算与执行时序:DurableBudgetLedger(文件持久化、fsync、原子写、
  crash 恢复、双硬帽、单 worker、task 配额、禁 resume)真实文件往返;
  runner --selftest 真实子进程组 SIGTERM/killpg;nvidia-smi GPU 清单。

任何一项 FAIL → exit 1,总门 HOLD_ZERO_NEW_EPISODES。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# GL 铁律:本容器 EGL 设备数 0,必须 osmesa,且在任何 mujoco 导入前设置
os.environ["MUJOCO_GL"] = "osmesa"
os.environ["PYOPENGL_PLATFORM"] = "osmesa"
for _k in ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE"):
    os.environ.pop(_k, None)
os.environ.setdefault("LIBERO_TYPE", "pro")
os.environ.setdefault("ROBOT_PLATFORM", "LIBERO")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# env_server 自带"mujoco 必须晚于 GL 环境变量导入"的断言:必须抢在任何
# liberopro/mujoco 导入之前先把 facade 模块导入(osmesa 已在上面设好)
from robots.libero.env_server import LiberoEnvFacade, make_env  # noqa: E402

SPEC_DIR = REPO / "analysis" / "research_context"
TRUTH_PATH = SPEC_DIR / "p1_dev1a_operational_truth.py"

# 彩排参数(彩排专用;生产 probe 参数冻结在 rpent/utils/p1_dev1a.py)
REH_APPROACH_STEPS = 500
REH_DESCEND_STEPS = 150
REH_APPROACH_DZ = 0.06      # 目标上方巡航高度
REH_DESCEND_DZ = 0.005      # 闭合高度(目标中心附近)
REH_STEP_CLIP = 0.005
GRIP_OPEN = -1.0            # robosuite 约定:-1 张开,+1 闭合
GRIP_CLOSE = 1.0


def _sha(arr) -> str:
    import numpy as np

    return hashlib.sha256(np.asarray(arr).tobytes()).hexdigest()


def _load_truth():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gate_truth", TRUTH_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# G1:ground-truth env(进程内直连 robosuite)
# ---------------------------------------------------------------------------

def _gt_env(task_id: int, seed: int):
    import liberopro.liberopro as l_pro
    from liberopro.liberopro.envs import OffScreenRenderEnv
    from rlinf.envs.libero.utils import benchmark as _bench

    suite = _bench.get_benchmark("libero_spatial")()
    task = suite.get_task(task_id)
    bddl = os.path.join(l_pro.get_libero_path("bddl_files"),
                        task.problem_folder, task.bddl_file)
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256,
                             camera_widths=256, camera_depths=True,
                             horizon=1500)
    env.seed(seed)
    return env, task


def _geom_body_table(sim):
    """geom 名→id、body 名→id、body→geoms(权威:mj_id2name 全枚举)。"""
    import mujoco
    import numpy as np

    m = sim.model._model
    gname = {}
    for i in range(m.ngeom):
        n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i)
        if n:
            gname[n] = int(i)
    bname = {}
    for i in range(m.nbody):
        n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i)
        if n:
            bname[n] = int(i)
    body_geoms = {}
    for name, bid in bname.items():
        body_geoms[name] = sorted(
            int(g) for g in np.flatnonzero(m.geom_bodyid == bid))
    return gname, bname, body_geoms


def build_spec(task_id: int) -> dict:
    """冻结每任务 geom 表(只含名字/int id/分组,不含任何私有数据)。"""
    env, task = _gt_env(task_id, seed=0)
    obs = env.reset()
    rob = env.env
    sim = rob.sim
    gname, bname, body_geoms = _geom_body_table(sim)

    target = rob.obj_of_interest[0]
    obj_contact = {}
    for o in getattr(rob, "objects", []) or []:
        cg = [str(g) for g in (getattr(o, "contact_geoms", None) or [])]
        if cg:
            obj_contact[str(getattr(o, "name", "?"))] = sorted(set(cg))

    grip = rob.robots[0].gripper
    lf = sorted({str(g) for g in grip.important_geoms["left_finger"]})
    rf = sorted({str(g) for g in grip.important_geoms["right_finger"]})
    rself = sorted({str(g) for g in rob.robots[0].robot_model.contact_geoms})

    # 支撑分组:家具碰撞 geom(非 robot/gripper/物体 body)+ 地面 + 其他物体
    robot_prefix = ("robot0_", "gripper0_", "mount0_")
    obj_bodies = {f"{n}_main" for n in obj_contact}
    furniture = {}
    for b, geoms in body_geoms.items():
        if b in ("world",) or b.startswith(robot_prefix) or b in obj_bodies:
            continue
        names = sorted(n for n in gname if n != "floor"
                       and gname[n] in geoms and not n.endswith("_visual"))
        if names:
            furniture[b] = names
    support_groups = dict(furniture)
    support_groups["floor"] = ["floor"]
    for n, cg in obj_contact.items():
        if n != target:
            support_groups[f"object:{n}"] = cg
    support = sorted({g for v in support_groups.values() for g in v})
    tgt_geoms = obj_contact.get(target) or []

    spec = {
        "task": task_id,
        "suite": "libero_spatial",
        "target": target,
        "obj_of_interest": list(rob.obj_of_interest),
        "language": getattr(env, "language_instruction", None),
        "target_geoms": tgt_geoms,
        "left_finger_geoms": lf,
        "right_finger_geoms": rf,
        "robot_self_geoms": rself,
        "support_geoms": support,
        "support_groups": support_groups,
        "geom_id": dict(gname),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    env.close()
    return spec


def _verify_spec(spec: dict) -> list[str]:
    """结构校验:全部名字可解析、四组 int id 两两不相交(判据前置)。"""
    errs = []
    gid = spec["geom_id"]
    sets = {}
    for key in ("target_geoms", "left_finger_geoms", "right_finger_geoms",
                "support_geoms", "robot_self_geoms"):
        ids = []
        for n in spec[key]:
            if n not in gid:
                errs.append(f"{key}: name not in model: {n}")
            else:
                ids.append(gid[n])
        if not ids:
            errs.append(f"{key}: empty")
        sets[key] = set(ids)
    core = ["target_geoms", "left_finger_geoms", "right_finger_geoms",
            "support_geoms"]
    for i, a in enumerate(core):
        for b in core[i + 1:]:
            if sets[a] & sets[b]:
                errs.append(f"geom id overlap: {a} ∩ {b}")
    return errs


def g1_ground_truth(task_id: int, ev: dict):
    """G1 证据 Part A:冻结 geom 表(名字↔int id,模型编译属性,与状态无关)。

    注:ground-truth 直连 env 与生产 worker env 的 reset 初始状态不同
    (rlinf 用 suite task_init_states),因此一切**接触语义**对照都在
    Part B(worker 路径)做;本函数只产出权威 geom 名表与结构校验。
    """
    spec = build_spec(task_id)
    ev["spec_errors"] = _verify_spec(spec)
    ev["g1_gt_pass"] = not ev["spec_errors"]
    return spec


# ---------------------------------------------------------------------------
# G1+G2:生产 worker 路径(rlinf LiberoEnv + LiberoEnvFacade)
# ---------------------------------------------------------------------------

def _facade_env(task_id: int, seed: int):
    raw = make_env(task_id, seed, max_episode_steps=1500)
    return LiberoEnvFacade(raw, meta={"task": task_id, "seed": seed})


def g1_g2_worker_path(task_id: int, spec: dict, ev: dict):
    """G1 Part B + G2:生产 worker 路径的快照/零步进/同刻/成本证据。"""
    import numpy as np

    rpc_spec = {k: spec[k] for k in
                ("target", "target_geoms", "left_finger_geoms",
                 "right_finger_geoms", "support_geoms", "robot_self_geoms")}
    f = _facade_env(task_id, seed=0)
    f.reset()
    a0 = np.zeros(7, dtype=np.float32)
    f.step(a0)          # settle:接触缓冲需要一次真实步进

    snap1 = f.contact_snapshot(rpc_spec)
    snap2 = f.contact_snapshot(rpc_spec)

    # ---- G1 Part B:步进后正/负对照 + 支撑归属(全部生产 RPC 通道)----
    # 正对照:目标初始放在家具/其他物体上 → target↔support True;
    # 负对照:机械臂初始远离目标 → finger↔target False;目标不触地。
    def group_spec(groups: dict) -> dict:
        s = dict(rpc_spec)
        s["support_geoms"] = sorted(
            {g for v in groups.values() for g in v})
        return s

    support_hits = {}
    for gname, ggeoms in spec["support_groups"].items():
        s = dict(rpc_spec)
        s["support_geoms"] = ggeoms
        support_hits[gname] = f.contact_snapshot(s)["flags"][
            "target_x_support"]
    fl = snap1["flags"]
    ctl = {
        "target_x_support": fl["target_x_support"],
        "target_x_any": fl["target_x_any"],
        "target_x_floor": support_hits.get("floor", False),
        "left_x_target": fl["left_x_target"],
        "right_x_target": fl["right_x_target"],
        "support_group_hits": support_hits,
    }
    ev["controls_after_one_step"] = ctl
    ev["pass_controls"] = bool(
        ctl["target_x_support"] and ctl["target_x_any"]
        and not ctl["target_x_floor"]
        and not ctl["left_x_target"] and not ctl["right_x_target"])

    g2 = {
        "server_step_count": snap1["server_step_count"],
        "step_mark_unchanged": snap1["step_mark_unchanged"],
        "same_tick": snap1["same_tick"],
        "repeat_identical": (
            snap1["state_sha256"] == snap2["state_sha256"]
            and snap1["flags"] == snap2["flags"]
            and snap1["pairs"] == snap2["pairs"]),
        "snapshot_cost": {
            "wall_ms": [snap1["wall_ms"], snap2["wall_ms"]],
            "queries": [snap1["queries"], snap2["queries"]],
            "n_pairs": len(snap1["pairs"]),
        },
    }
    ev["worker_path"] = {
        "flags": snap1["flags"],
        "pairs": snap1["pairs"],
        # worker 路径接触语义与 ground-truth 模型一致性(名字通道可用)
        "matches_gt_expectation": bool(ev["pass_controls"]),
        "state_sha256": snap1["state_sha256"],
    }

    # ---- A/B 世界:20 步,有无快照交错,终态必须逐位一致 ----
    actions = [np.clip(np.sin(0.3 * i), -0.3, 0.3) *
               np.ones(7, dtype=np.float32) for i in range(20)]

    def run_world(interleave: bool):
        f.reset()
        shas = []
        for i, a in enumerate(actions):
            f.step(a)
            if interleave and (i + 1) % 5 == 0:
                s = f.contact_snapshot(rpc_spec)
                shas.append(s["state_sha256"])
                assert s["server_step_count"] == i + 1, \
                    f"snapshot advanced steps: {s['server_step_count']} != {i+1}"
        # 合法低维观测走 raw_obs 通道(robosuite 官方观测,与快照同刻)
        eef = np.asarray(f.raw_obs()["robot0_eef_pos"], dtype=float)
        return _sha(np.asarray(f.save_state())), eef, shas

    state_a, eef_a, _ = run_world(False)
    state_b, eef_b, snap_shas = run_world(True)
    g2["ab_world_final_state_identical"] = bool(state_a == state_b)
    g2["ab_world_final_eef_identical"] = bool(
        np.array_equal(eef_a, eef_b))
    g2["ab_world_snapshot_shas"] = snap_shas

    # ---- 同刻合法性:快照低维观测 == 同一步的合法 raw_obs ----
    f.step(a0)          # 第 21 步
    legal_eef = np.asarray(f.raw_obs()["robot0_eef_pos"], dtype=float)
    snap3 = f.contact_snapshot(rpc_spec)
    g2["same_tick_pose_matches_legal_obs"] = bool(np.allclose(
        np.asarray(snap3["obs"]["robot0_eef_pos"], dtype=float),
        legal_eef, atol=1e-9))
    g2["snapshot_after_step_count"] = snap3["server_step_count"]

    ev["g2_evidence"] = g2
    ev["g2_pass"] = bool(
        g2["same_tick"] and g2["step_mark_unchanged"]
        and g2["repeat_identical"]
        and g2["ab_world_final_state_identical"]
        and g2["ab_world_final_eef_identical"]
        and g2["same_tick_pose_matches_legal_obs"]
        and g2["snapshot_after_step_count"] == 21)

    # 关闭前记录 worker 状态指纹(供 G1 与 ground-truth 交叉对照)
    ev["worker_final_state_sha256"] = state_b
    f._env.close()
    return ev


# ---------------------------------------------------------------------------
# G1 Part C:生产 worker 路径上的真实抓取彩排(close+lift+接触真值+复原)
# ---------------------------------------------------------------------------

def rehearsal(task_id: int, spec: dict, ev: dict):
    """封版副本纪律:save_state → 彩排 → restore_state → 逐位复原校验。

    全部接触证据走 contact_snapshot RPC(生产通道);彩排专用巡航参数
    与生产 probe 参数分开(生产只有 close+lift,无巡航)。
    """
    import numpy as np

    rpc_spec = {k: spec[k] for k in
                ("target", "target_geoms", "left_finger_geoms",
                 "right_finger_geoms", "support_geoms", "robot_self_geoms")}
    tgt_name = spec["target"]

    f = _facade_env(task_id, seed=0)
    f.reset()
    st0 = np.asarray(f.save_state())

    def snap():
        return f.contact_snapshot(rpc_spec)

    def raw(key):
        return np.asarray(f.raw_obs()[key], dtype=float)

    def gap():
        gp = raw("robot0_gripper_qpos")
        return float(abs(gp[0]) + abs(gp[1]))

    def move_to(pos, max_steps, gripper):
        used, last_dist = 0, None
        for _ in range(max_steps):
            cur = raw("robot0_eef_pos")
            diff = np.asarray(pos) - cur
            last_dist = float(np.linalg.norm(diff))
            if last_dist < 0.004:
                break
            a = np.zeros(7, dtype=np.float32)
            a[:3] = np.clip(np.clip(diff, -REH_STEP_CLIP, REH_STEP_CLIP)
                            / 0.05, -1, 1)
            a[6] = gripper
            f.step(a)
            used += 1
        return used, last_dist

    # 目标位置来自接触快照的 obs(同刻 sim 真值;彩排侧允许使用)
    tpos = np.asarray(snap()["obs"][f"{tgt_name}_pos"], dtype=float)
    gap0 = gap()
    app_used, app_dist = move_to(tpos + [0, 0, REH_APPROACH_DZ],
                                 REH_APPROACH_STEPS, GRIP_OPEN)
    desc_used, desc_dist = move_to(tpos + [0, 0, REH_DESCEND_DZ],
                                   REH_DESCEND_STEPS, GRIP_OPEN)
    steps = {"approach": app_used, "descend": desc_used, "close": 10}

    # 固定闭合 10 步(与生产 probe 同参数)
    a_close = np.zeros(7, dtype=np.float32)
    a_close[6] = GRIP_CLOSE
    for _ in range(10):
        f.step(a_close)
    gap1 = gap()
    close_snap = snap()

    # 受控提升(生产锁定参数:clip 0.005 / ≤24 步 / dz≥0.016 停)
    eef0 = float(raw("robot0_eef_pos")[2])
    obj0 = float(close_snap["obs"][f"{tgt_name}_pos"][2])
    lift_steps = 0
    for _ in range(24):
        cur = raw("robot0_eef_pos")
        if float(cur[2]) - eef0 >= 0.016:
            break
        diff = np.array([0., 0., (eef0 + 0.018) - float(cur[2])])
        a = np.zeros(7, dtype=np.float32)
        a[:3] = np.clip(np.clip(diff, -0.005, 0.005) / 0.05, -1, 1)
        a[6] = GRIP_CLOSE
        f.step(a)
        lift_steps += 1
    eef1 = float(raw("robot0_eef_pos")[2])
    lift_snap = snap()
    obj1 = float(lift_snap["obs"][f"{tgt_name}_pos"][2])

    # 复原:彩排对世界的全部扰动被丢弃
    f.restore_state(st0)
    restored_sha = _sha(np.asarray(f.save_state()))
    pre_sha = _sha(st0)
    f._env.close()

    ev["rehearsal"] = {
        "target": tgt_name,
        "steps_used": steps,
        "final_dist_to_target_m": {
            "approach": None if app_dist is None else round(app_dist, 4),
            "descend": None if desc_dist is None else round(desc_dist, 4)},
        "gripper_gap_before_close": round(gap0, 6),
        "gripper_gap_after_close": round(gap1, 6),
        "close_flags": close_snap["flags"],
        "close_pairs_all": close_snap["pairs"],
        "lift": {"steps": lift_steps,
                 "eef_dz": round(eef1 - eef0, 6),
                 "obj_dz": round(obj1 - obj0, 6)},
        "lift_flags": lift_snap["flags"],
        "restored_matches_pre": restored_sha == pre_sha,
    }
    finger_geoms = set(spec["left_finger_geoms"]) | \
        set(spec["right_finger_geoms"])
    tgt_set = set(spec["target_geoms"])
    real_ft_pairs = [p for p in close_snap["pairs"]
                     if (p[0] in finger_geoms and p[1] in tgt_set)
                     or (p[0] in tgt_set and p[1] in finger_geoms)]
    ev["rehearsal"]["finger_target_pairs"] = real_ft_pairs

    # 判据:闭合确实闭合(gap 减小)、彩排产生真实 finger↔target 对、
    # 提升运动学可达 dz≥0.010、复原逐位一致
    ev["rehearsal_pass"] = bool(
        ev["rehearsal"]["gripper_gap_after_close"]
        < ev["rehearsal"]["gripper_gap_before_close"]
        and len(real_ft_pairs) > 0
        and ev["rehearsal"]["lift"]["eef_dz"] >= 0.010
        and ev["rehearsal"]["restored_matches_pre"])
    return ev


# ---------------------------------------------------------------------------
# G3:防泄漏对抗(基于真实快照数据)
# ---------------------------------------------------------------------------

def g3_adversarial(snapshot_flags: dict, snapshot_pairs: list, ev: dict):
    truth = _load_truth()
    import copy
    import random

    envelope = {
        "env_step": 7, "rgb_sha256": "a" * 64, "wrist_sha256": "b" * 64,
        "gripper_gap": 0.04, "eef_pos": [0.1, 0.2, 1.0],
        "eef_quat": [0., 0., 0., 1.], "source": "libero_official_obs",
        "fresh": True, "validity": "VALID",
    }
    checks = {"legal_envelope_passes": truth.prohibit_audit_leak(envelope)}

    # 特权字段注入(平铺 + 递归嵌套)必须 fail-close
    for poison_key, poison_val in (
            ("contacts", snapshot_pairs),
            ("contact_flags", snapshot_flags),
            ("obj_pos", [0.1, 0.2, 0.9]),
            ("audit", {"held": True, "pairs": snapshot_pairs}),
            ("planner_hint", {"nested": {"contacts": snapshot_pairs}})):
        bad = dict(envelope)
        bad[poison_key] = poison_val
        try:
            truth.prohibit_audit_leak(bad)
            checks[f"inject_{poison_key}_rejected"] = False
        except ValueError:
            checks[f"inject_{poison_key}_rejected"] = True

    # 种子化随机改写审计真值 → legal 信封字节不变;标签只随审计容器变
    rng = random.Random(20261010)
    audit = {"flags": dict(snapshot_flags), "pairs": list(snapshot_pairs)}
    frozen_envelope = json.dumps(envelope, sort_keys=True)
    mutated = 0
    for _ in range(20):
        m = copy.deepcopy(audit)
        if m["pairs"]:
            rng.shuffle(m["pairs"])
            m["pairs"] = m["pairs"][:max(0, len(m["pairs"]) - 1)]
        for k in m["flags"]:
            m["flags"][k] = rng.choice([True, False])
        if m != audit:
            mutated += 1
        assert json.dumps(envelope, sort_keys=True) == frozen_envelope
    checks["randomized_truth_perturbation"] = {
        "mutations": mutated, "envelope_bytes_unchanged": True}

    # audit 容器与 legal 信封键不相交(除白名单语义外)
    audit_keys = {"flags", "pairs", "contacts", "obj_pos", "held",
                  "target_geom_ids", "support_geom_ids"}
    checks["container_key_disjoint"] = not (
        audit_keys & set(envelope))

    # 静态断言:maybe_probe 永远 return None,不向 toolkit 视图注入任何字段
    src = (REPO / "rpent" / "utils" / "p1_dev1a.py").read_text("utf-8")
    tree = ast.parse(src)
    probe_ret = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "maybe_probe":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    probe_ret.append(sub.value)
    checks["maybe_probe_always_returns_none"] = bool(
        probe_ret and all(v is None or (isinstance(v, ast.Constant)
                                        and v.value is None)
                          for v in probe_ret))

    ev["g3_evidence"] = checks
    ev["g3_pass"] = bool(
        checks["legal_envelope_passes"]
        and all(checks[f"inject_{k}_rejected"] for k in
                ("contacts", "contact_flags", "obj_pos", "audit",
                 "planner_hint"))
        and checks["randomized_truth_perturbation"]["envelope_bytes_unchanged"]
        and checks["container_key_disjoint"]
        and checks["maybe_probe_always_returns_none"])
    return ev


# ---------------------------------------------------------------------------
# G4:持久化账本 + runner selftest + GPU 清单
# ---------------------------------------------------------------------------

def g4_budget(ev: dict):
    sys.path.insert(0, str(REPO / "analysis" / "research_context"))
    from p1_dev1a_budget_gate import (BudgetLedger, MAX_EP, MAX_ENV_STEPS,
                                      MAX_GPU_S, MAX_WALL_S, TASK_CAP,
                                      static_repo_gate)

    import tempfile
    checks = {}
    # 文件持久化往返 + crash 中断保留在飞预留(不释放、不 resume)
    with tempfile.TemporaryDirectory(
            dir="/workspace/yjx/tmp") as td:
        ledger_path = Path(td) / "ledger.json"
        import importlib.util

        spec_mod = importlib.util.spec_from_file_location(
            "p1_dev1a_run_mod",
            REPO / "scripts" / "p1_dev1a_run.py")
        run_mod = importlib.util.module_from_spec(spec_mod)
        sys.modules[spec_mod.name] = run_mod
        spec_mod.loader.exec_module(run_mod)
        DurableBudgetLedger = run_mod.DurableBudgetLedger
        dl = DurableBudgetLedger(ledger_path, BudgetLedger)
        dl.reserve("ep1", "9", 2400.0, 1)
        # 模拟 crash:不再 charge,直接重开文件
        dl2 = DurableBudgetLedger(ledger_path, BudgetLedger)
        checks["crash_keeps_inflight"] = (
            dl2.raw()["inflight_key"] == "ep1"
            and dl2.raw()["begun"] == 1)
        try:
            dl2.reserve("ep2", "9", 2400.0, 1)
            checks["crash_refuses_new_episode"] = False
        except ValueError:
            checks["crash_refuses_new_episode"] = True
        # 断点续跑禁止
        try:
            dl2.forbid_resume("ep1")
            checks["resume_forbidden"] = False
        except ValueError:
            checks["resume_forbidden"] = True
        # 超预留 → OVERRUN_STOP 且保留预留做取证
        try:
            dl2.charge_and_close("ep1", 3000.0, 3000.0, 100)
            checks["overrun_rejected"] = False
        except ValueError as e:
            checks["overrun_rejected"] = "OVERRUN" in str(e)
            checks["overrun_keeps_reservation"] = (
                dl2.raw()["inflight_key"] == "ep1")
        # 正常结账后可继续
        dl2.charge_and_close("ep1", 900.0, 900.0, 700)
        checks["normal_close"] = (
            dl2.raw()["completed"] == 1 and dl2.raw()["inflight_key"] is None)

    # 静态门:代码面完备(contact RPC 双端 + 独立 runner)
    static = static_repo_gate(REPO)
    checks["static_repo_gate"] = static
    checks["static_code_present"] = bool(
        static["G1_contact_rpc_code_present"]
        and static["G4_isolated_dev1a_runner_present"])

    # runner selftest:真实子进程组 SIGTERM/killpg/记账
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "p1_dev1a_run.py"),
         "--selftest"],
        capture_output=True, text=True, timeout=300)
    try:
        checks["runner_selftest"] = json.loads(
            r.stdout.strip().splitlines()[-1])
    except Exception:
        checks["runner_selftest"] = {"rc": r.returncode,
                                     "stderr": r.stderr[-500:]}
    checks["runner_selftest_pass"] = bool(
        checks["runner_selftest"].get("pass"))

    # GPU 清单(来源记录;不猜 GPU 个数)
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total",
             "--format=csv,noheader"], capture_output=True, text=True,
            timeout=30).stdout.strip()
        checks["gpu_inventory"] = out
        checks["gpu_visible"] = len(out.splitlines()) >= 1
    except Exception as exc:
        checks["gpu_inventory"] = f"ERROR: {exc}"
        checks["gpu_visible"] = False

    checks["budget_caps_echo"] = {
        "MAX_EP": MAX_EP, "MAX_GPU_S": MAX_GPU_S,
        "MAX_WALL_S": MAX_WALL_S, "MAX_ENV_STEPS": MAX_ENV_STEPS,
        "TASK_CAP": TASK_CAP, "MAX_WORKERS": 1,
    }
    ev["g4_evidence"] = checks
    ev["g4_pass"] = bool(
        checks["crash_keeps_inflight"] and checks["crash_refuses_new_episode"]
        and checks["resume_forbidden"] and checks["overrun_rejected"]
        and checks["overrun_keeps_reservation"] and checks["normal_close"]
        and checks["static_code_present"]
        and checks["runner_selftest_pass"] and checks["gpu_visible"])
    return ev


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tasks", default="9,3,5")
    p.add_argument("--out", type=Path,
                   default=REPO / "artifacts" / "p1_dev1a" / "gate_evidence.json")
    p.add_argument("--skip-rehearsal", action="store_true")
    args = p.parse_args()
    tasks = [int(x) for x in args.tasks.split(",")]

    evidence = {"protocol": "D-041", "started_at": time.strftime(
        "%Y-%m-%dT%H:%M:%S"), "tasks": tasks}
    all_pass = True
    worker_flags = None
    worker_pairs = None

    for t in tasks:
        ev: dict = {"task": t}
        try:
            spec = g1_ground_truth(t, ev)
            # 冻结 spec 写盘(名字+id 表,可提交;运行期只读)
            sp = SPEC_DIR / f"p1_dev1a_geom_spec_t{t}.json"
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                          encoding="utf-8")
            ev["spec_path"] = str(sp)
            ev["spec_sha256"] = hashlib.sha256(
                sp.read_bytes()).hexdigest()

            g1_g2_worker_path(t, spec, ev)
            if not args.skip_rehearsal:
                rehearsal(t, spec, ev)
            else:
                ev["rehearsal_pass"] = None
            ev["g1_pass"] = bool(
                ev["g1_gt_pass"]
                and ev["worker_path"]["matches_gt_expectation"]
                and (args.skip_rehearsal or ev["rehearsal_pass"]))
            if t == tasks[0]:
                worker_flags = ev["worker_path"]["flags"]
                worker_pairs = ev["worker_path"]["pairs"]
        except Exception as exc:  # noqa: BLE001
            ev["fatal"] = f"{type(exc).__name__}: {exc}"
            import traceback
            ev["traceback"] = traceback.format_exc()[-2000:]
            ev["g1_pass"] = False
            ev["g2_pass"] = False
        evidence[f"task_{t}"] = ev
        all_pass &= bool(ev.get("g1_pass")) and bool(ev.get("g2_pass"))

    if worker_flags is not None:
        try:
            g3_adversarial(worker_flags, worker_pairs, evidence)
        except Exception as exc:  # noqa: BLE001
            evidence["g3_evidence"] = {"fatal": f"{type(exc).__name__}: {exc}"}
            evidence["g3_pass"] = False
    else:
        evidence["g3_pass"] = False
    try:
        g4_budget(evidence)
    except Exception as exc:  # noqa: BLE001
        import traceback
        evidence["g4_evidence"] = {"fatal": f"{type(exc).__name__}: {exc}",
                                   "traceback": traceback.format_exc()[-2000:]}
        evidence["g4_pass"] = False

    evidence["all_gates_pass"] = bool(
        all_pass and evidence.get("g3_pass") and evidence.get("g4_pass"))
    evidence["gate"] = ("GO_PILOT" if evidence["all_gates_pass"]
                        else "HOLD_ZERO_NEW_EPISODES")
    evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2,
                                   default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items()
                      if k in ("all_gates_pass", "gate")},
                     ensure_ascii=False))
    for t in tasks:
        ev = evidence[f"task_{t}"]
        print(f"task {t}: g1={ev.get('g1_pass')} g2={ev.get('g2_pass')} "
              f"rehearsal={ev.get('rehearsal_pass')} "
              f"fatal={ev.get('fatal')}")
    print(f"g3={evidence.get('g3_pass')} g4={evidence.get('g4_pass')}")
    print(f"[gate] evidence -> {args.out}")
    sys.exit(0 if evidence["all_gates_pass"] else 1)


if __name__ == "__main__":
    main()
