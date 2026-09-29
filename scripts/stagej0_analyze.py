#!/usr/bin/env python
"""Stage J0 离线判定:按预注册 stageJ0_prereg.md §3-§5 计算四门。

输入:analysis/stageJ0_fork_results.jsonl(runner 产物,逐 fork 一行)。
输出:逐对明细 + 四门判定 + 机制统计(供 stageJ0_state_restore_results.md)。

物体位姿通道:分支记录里的 obj_state = LIBERO `object-state`(每物体
14 维:pos3+quat4+to_eef_pos3+to_eef_quat4,按物体名字典序拼接)。首个
fork 的 obs_full 会与逐物体键做一次布局断言。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 预注册 §3 容差
TOL = {
    "hist": {"pos": 0.002, "scalar": 0.002, "grip": 0.004},
    "vla": {"pos": 0.005, "scalar": 0.005, "grip": 0.004},
}


def _l2(a, b):
    if a is None or b is None:
        return None
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _obj_blocks(obj_state, n_obj):
    """object-state → 每物体 pos(3);布局 = n_obj × 14,断言整除。"""
    if obj_state is None:
        return None
    assert len(obj_state) == 14 * n_obj, (
        f"object-state 布局异常: len={len(obj_state)} n_obj={n_obj}")
    return [obj_state[i * 14: i * 14 + 3] for i in range(n_obj)]


def _grip_opening(q):
    if q is None:
        return None
    return abs(q[0]) + abs(q[1])


def _stv_class(base, branch, n_obj):
    """预注册 §4 STV 代理:TERMINAL > LIFT > DROP > MOVE > STALL。"""
    if branch["check_success"]:
        return "TERMINAL"
    dz = mx = None
    if base["obj_state"] is not None and branch["obj_state"] is not None:
        bb = _obj_blocks(base["obj_state"], n_obj)
        ob = _obj_blocks(branch["obj_state"], n_obj)
        dz = max(b[2] - a[2] for a, b in zip(bb, ob))
        mx = math.sqrt(max(
            (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 for a, b in zip(bb, ob)))
    deef = _l2(base["eef_pos"], branch["eef_pos"])
    if dz is not None and dz >= 0.01:
        return "LIFT"
    if dz is not None and dz <= -0.01:
        return "DROP"
    if deef is not None and deef >= 0.03:
        return "MOVE"
    return "STALL"


def analyze(path: str):
    recs = [json.loads(l) for l in open(REPO / path)]
    ok = [r for r in recs if not r.get("infra_abort")]
    abort = [r for r in recs if r.get("infra_abort")]

    # 首个含 obs_full 的 fork:object-state 布局断言(实现自证,不改判定)
    for r in ok:
        full = r["baseline"].get("obs_full")
        if isinstance(full, dict) and "akita_black_bowl_1_pos" in full:
            names = [k[:-4] for k in full if k.endswith("_pos")
                     and not k.startswith("robot0")
                     and "_to_robot0_eef" not in k]
            names = [n for n in names if f"{n}_quat" in full]
            n_obj = len(names)
            blocks = _obj_blocks(r["baseline"]["obj_state"], n_obj)
            assert all(
                abs(a - b) < 1e-9 for a, b in zip(blocks[0], full[f"{names[0]}_pos"])
            ), "object-state 首物体 pos 与逐物体键不一致,布局假设不成立"
            print(f"[layout] object-state = {n_obj} 物体 × 14 维,"
                  f"首物体 {names[0]} 对齐验证通过")
            break

    # G1:restore 读回精确性
    restores = [x for r in ok for x in r["restores"]]
    g1_exact = sum(1 for x in restores if x["readback_max_abs_diff"] == 0.0)
    g1_rate = g1_exact / len(restores) if restores else 0.0

    pair_rows = []
    for r in ok:
        n_obj = len(r["baseline"]["obj_of_interest"] or []) or 5
        # 实际物体数以 object-state 长度为准(关注对象是任务相关子集)
        n_obj = len(r["baseline"]["obj_state"]) // 14 if r["baseline"]["obj_state"] else 0
        base = {"eef_pos": r["baseline"]["eef_pos"],
                "obj_state": r["baseline"]["obj_state"]}
        br = {b["tag"]: b for b in r["branches"]}
        for kind, t1, t2 in (("hist", "hist1", "hist2"), ("vla", "vla1", "vla2")):
            if t1 not in br or t2 not in br:
                continue
            b1, b2 = br[t1], br[t2]
            row = {"fork": r["fork_id"], "kind": kind}
            row["eef_l2"] = _l2(b1["eef_pos"], b2["eef_pos"])
            if b1["obj_state"] and b2["obj_state"]:
                o1 = _obj_blocks(b1["obj_state"], n_obj)
                o2 = _obj_blocks(b2["obj_state"], n_obj)
                row["obj_l2_max"] = max(_l2(a, b) for a, b in zip(o1, o2))
            else:
                row["obj_l2_max"] = None
            g1 = _grip_opening(b1["gripper_qpos"])
            g2 = _grip_opening(b2["gripper_qpos"])
            row["grip_diff"] = abs(g1 - g2) if (g1 is not None and g2 is not None) else None
            r1, r2 = b1["result"], b2["result"]
            row["flag_success"] = (r1.get("success"), r2.get("success"))
            row["flags_eq"] = r1.get("success") == r2.get("success")
            row["cs_eq"] = b1["check_success"] == b2["check_success"]
            if kind == "hist":
                row["scalar"] = (abs((r1.get("final_dist_m") or 0) -
                                     (r2.get("final_dist_m") or 0))
                                 if r1.get("final_dist_m") is not None
                                 and r2.get("final_dist_m") is not None else None)
            else:
                row["scalar"] = (abs(r1["peak_lift_m"] - r2["peak_lift_m"])
                                 if r1.get("peak_lift_m") is not None
                                 and r2.get("peak_lift_m") is not None else None)
            # G2:全部门控通道在容差内
            tol = TOL[kind]
            checks = [
                row["eef_l2"] is not None and row["eef_l2"] <= tol["pos"],
                row["obj_l2_max"] is None or row["obj_l2_max"] <= tol["pos"],
                row["grip_diff"] is None or row["grip_diff"] <= tol["grip"],
                row["scalar"] is None or row["scalar"] <= tol["scalar"],
                row["flags_eq"], row["cs_eq"],
            ]
            row["g2_pass"] = all(checks)
            row["err"] = bool(b1.get("error") or b2.get("error"))
            # G3:STV 代理类一致
            row["stv1"] = _stv_class(base, b1, n_obj)
            row["stv2"] = _stv_class(base, b2, n_obj)
            row["stv_eq"] = row["stv1"] == row["stv2"]
            # G4:成败旗标(move_to 无 success 旗标 → 只比 check_success)
            row["g4_pass"] = row["cs_eq"] and row["flags_eq"]
            pair_rows.append(row)

    valid_hist = [p for p in pair_rows if p["kind"] == "hist" and not p["err"]]
    valid_vla = [p for p in pair_rows if p["kind"] == "vla" and not p["err"]]

    def _rate(rows, key):
        return sum(1 for x in rows if x[key]) / len(rows) if rows else float("nan")

    print(f"\n=== 样本 ===\nforks ok={len(ok)} infra_abort={len(abort)} "
          f"(有效要求 ≥16)")
    for r in abort:
        print(f"  ABORT {r['fork_id']}: {r['infra_abort']['reason'][:80]}")

    print(f"\n=== G1 restore 精确性 ===\nrestore 事件 {len(restores)},"
          f"bitwise 精确 {g1_exact},rate={g1_rate:.4f}(门=100%)")

    print(f"\n=== G2 可观测一致(容差内比例,门=95%)===")
    for name, rows in (("hist", valid_hist), ("vla", valid_vla)):
        print(f"  {name}: n={len(rows)} pass={_rate(rows,'g2_pass'):.4f}")
        for ch in ("eef_l2", "obj_l2_max", "grip_diff", "scalar"):
            vals = [x[ch] for x in rows if x[ch] is not None]
            if vals:
                sv = sorted(vals)
                print(f"    {ch}: median={sv[len(sv)//2]:.5f} "
                      f"p90={sv[int(len(sv)*0.9)]:.5f} max={sv[-1]:.5f}")

    print(f"\n=== G3 STV 代理一致(门=95%)===")
    allp = valid_hist + valid_vla
    print(f"  n={len(allp)} eq_rate={_rate(allp,'stv_eq'):.4f}")
    for x in allp:
        if not x["stv_eq"]:
            print(f"    DISAGREE {x['fork']} {x['kind']}: {x['stv1']} vs {x['stv2']}")

    print(f"\n=== G4 成败一致(门=95%)===")
    print(f"  n={len(allp)} eq_rate={_rate(allp,'g4_pass'):.4f}")
    for x in allp:
        if not x["g4_pass"]:
            print(f"    DISAGREE {x['fork']} {x['kind']}: flags={x['flag_success']}")

    print(f"\n=== 明细(n吃满容差的支对)===")
    for x in allp:
        if not x["g2_pass"]:
            print(f"  {x['fork']} {x['kind']}: eef={x['eef_l2']:.4f} "
                  f"obj={x['obj_l2_max'] if x['obj_l2_max'] is None else round(x['obj_l2_max'],4)} "
                  f"grip={x['grip_diff'] if x['grip_diff'] is None else round(x['grip_diff'],4)} "
                  f"scalar={x['scalar']} flags_eq={x['flags_eq']} cs_eq={x['cs_eq']}")

    g2h, g2v = _rate(valid_hist, "g2_pass"), _rate(valid_vla, "g2_pass")
    g3, g4 = _rate(allp, "stv_eq"), _rate(allp, "g4_pass")
    verdict = (
        g1_rate == 1.0 and g2h >= 0.95 and g2v >= 0.95
        and g3 >= 0.95 and g4 >= 0.95 and len(ok) >= 16)
    print(f"\n=== J0 判定:{'PASS' if verdict else 'FAIL'} ===")
    print(f"  G1={g1_rate:.4f} G2_hist={g2h:.4f} G2_vla={g2v:.4f} "
          f"G3={g3:.4f} G4={g4:.4f} valid_forks={len(ok)}/20")
    return verdict


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1
            else "analysis/stageJ0_fork_results.jsonl")
