#!/usr/bin/env python3
"""VE-v0.1 Phase 3:probe 时刻六臂(B0/B1/B2/B1'/B3/B4)离线决策对照。

只读输入:Phase 2 产出的 evidence_claims.json + 事件文件(合法观测 + audit-only
真值仅作评价列,绝不进任何臂的特征)。

臂定义:
  B0  tool-flag     触发即工具报失败 → RETRY(信任工具,不做任何区分)
  B1  static-gap    冻结 D2 规则:post_gap<0.06 → CONTINUE_CAUTION else RETRY
  B2  gap+dz        冻结 D3 规则:post_gap<0.06 ∧ Δeef_z≥0.03 → CONTINUE else RETRY
  B1' stall-band    本轮新增:闭合结局三态(无阻挡闭合/停住=受阻挡/模糊)
  B3  visual-only   相机运动护栏 + 腕视近场几何;设计上**永不**授权 CONTINUE
                    (256px 下指间内容不可辨 → 只能提供有效性/方位证据)
  B4  fusion        B1' ⊕ B3:联合状态(闭合结局 × 近场几何 × 图像有效性)

诚实地:5 案例均无支持"已持握"的证据 → 无臂可正确输出 CONTINUE;
本对照衡量的是**状态区分度、决策分歧与证据有效性**,不是准确率。
"""
from __future__ import annotations

import argparse
import glob
import json
import os

RUNS = "/workspace/yjx/rpent_data/p1_dev0/runs"
CLAIMS_DEFAULT = "/workspace/yjx/rpent_data/p1_dev0/ve01/evidence_claims.json"
OUT_DEFAULT = "/workspace/yjx/rpent_data/p1_dev0/ve01/arms_comparison.json"

FLOOR_MAX = 0.0035
NEAR_M = 0.005  # 近场带:表面距 EEF < 5mm 视为"爪平面处有材料"
CLOSE_M = 0.015  # 5-15mm 为贴近带


def load_case_events(case: str) -> dict:
    evs = [json.loads(l) for l in open(f"{RUNS}/p1dev0_{case}/p1_dev0_events.jsonl")]
    by = {}
    for e in evs:
        by.setdefault(e["ev"], e)
    return by


def arm_b0(by: dict) -> dict:
    # 触发定义 = 工具报失败;B0 无条件 RETRY
    return {"arm": "B0", "decision": "RETRY", "state": "TOOL_REPORTED_FAILURE", "rationale": "trust flag"}


def arm_b1(by: dict) -> dict:
    gap = by["probe"]["post_legal"]["gripper_gap"]
    cont = gap < 0.06
    return {
        "arm": "B1",
        "decision": "CONTINUE_CAUTION" if cont else "RETRY",
        "state": "gap_below_0.06" if cont else "gap_above_0.06",
        "state_detail": f"post_gap={gap:.4f}",
        "rationale": "frozen D2 static threshold 0.06",
    }


def arm_b2(by: dict) -> dict:
    pl = by["probe"]["post_legal"]["gripper_gap"]
    dz = by["probe"]["post_legal"]["eef_z"] - by["trigger"]["pre_legal"]["eef_z"]
    cont = pl < 0.06 and dz >= 0.03
    if cont:
        st = "gap_below_and_dz_ge_0.03"
    elif pl >= 0.06:
        st = "gap_above_0.06"
    else:
        st = "gap_below_but_dz_lt_0.03"
    return {
        "arm": "B2",
        "decision": "CONTINUE_CAUTION" if cont else "RETRY",
        "state": st,
        "state_detail": f"gap={pl:.4f},dz={dz:+.4f}",
        "rationale": "frozen D3 gap∧ΔEEF_z rule",
    }


def arm_b1p(claim: dict) -> dict:
    cc = claim["proprio_closure"]["closure_class"]
    if cc == "CLOSED_TO_FLOOR":
        return {
            "arm": "B1'",
            "decision": "RETRY",
            "state": "CLOSURE_UNOBSTRUCTED",
            "rationale": "unobstructed close; no further probe evidence has value (thin-edge caveat noted)",
        }
    if cc == "STALLED_ABOVE_FLOOR":
        return {
            "arm": "B1'",
            "decision": "RETRY+ESCALATE",
            "state": "CLOSURE_OBSTRUCTED",
            "rationale": "mechanical obstruction; location unresolved by proprio alone",
        }
    return {"arm": "B1'", "decision": "RETRY", "state": "AMBIGUOUS", "rationale": "in-band"}


def near_band(dist_min) -> str:
    if dist_min is None:
        return "NO_GEOM"
    if dist_min < NEAR_M:
        return "AT_FINGERTIP_PLANE"
    if dist_min < CLOSE_M:
        return "CLOSE"
    return "FAR"


def arm_b3(claim: dict) -> dict:
    cm = claim["visual_camera_motion"]
    g = claim.get("geometric_context") or {}
    band = near_band(g.get("dist_min_m") if g.get("usable") else None)
    if cm["camera_motion_flag"]:
        return {
            "arm": "B3",
            "decision": "RETRY(image-invalid)",
            "state": f"CAMERA_MOTION({cm['motion_kind']})",
            "rationale": "pixel evidence quarantined; no positive claim possible",
        }
    if band == "AT_FINGERTIP_PLANE":
        return {
            "arm": "B3",
            "decision": "RETRY+ESCALATE",
            "state": "MATERIAL_AT_FINGERTIP_PLANE",
            "rationale": "geometric near-field at inter-finger projection; not grasp proof",
        }
    return {
        "arm": "B3",
        "decision": "RETRY",
        "state": f"SURFACE_{band}_BELOW",
        "rationale": "no fingertip-plane material evidence; inter-finger content abstained",
    }


def arm_b4(claim: dict) -> dict:
    b1p = arm_b1p(claim)
    b3 = arm_b3(claim)
    cc = claim["proprio_closure"]["closure_class"]
    obstructed = cc == "STALLED_ABOVE_FLOOR"
    at_plane = "AT_FINGERTIP_PLANE" in b3["state"]
    parallax = "CAMERA_MOTION" in b3["state"]
    if obstructed and at_plane:
        state = "CONTACT_AT_FINGERTIP_PLANE(inter-finger projection)"
        dec = "RETRY+ESCALATE"
    elif obstructed:
        state = "CONTACT_BELOW_FINGERTIP_PLANE"
        dec = "RETRY+ESCALATE" if not parallax else "RETRY+ESCALATE(image-invalid)"
    elif at_plane:
        # 证据张力:闭合无阻挡(指间应无 >3.5mm 物体)但爪平面近场有材料
        # → 两者至少其一有误(旁侧表面/几何噪声/薄沿),不允许消解为强主张
        state = "TENSION:unobstructed_closure_with_fingertip_material"
        dec = "RETRY+ESCALATE(tension)"
    elif parallax:
        state = "CLOSURE_UNOBSTRUCTED+IMAGE_INVALID(parallax)"
        dec = "RETRY"
    else:
        state = "CLOSURE_UNOBSTRUCTED+NO_FINGERTIP_MATERIAL"
        dec = "RETRY"
    return {"arm": "B4", "decision": dec, "state": state, "rationale": "B1'⊕B3 joint state"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default=CLAIMS_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()
    claims = {c["case"]: c for c in json.load(open(args.claims))["claims"]}

    rows = []
    for case, claim in claims.items():
        by = load_case_events(case)
        # audit-only 真值(评价列,不进任何臂)
        retry_ok = by["action"].get("retry_result_summary", {}).get("success")
        audit = by["audit"]
        rows.append(
            {
                "case": case,
                "arms": [arm_b0(by), arm_b1(by), arm_b2(by), arm_b1p(claim), arm_b3(claim), arm_b4(claim)],
                "eval_only": {
                    "audit_kind": audit.get("kind"),
                    "retry_pick_success": retry_ok,
                    "pre_gap": by["trigger"]["pre_legal"]["gripper_gap"],
                },
            }
        )

    # 汇总:决策分歧矩阵 + 状态区分度
    arm_names = ["B0", "B1", "B2", "B1'", "B3", "B4"]
    decisions = {
        r["case"]: {a["arm"]: a["decision"] for a in r["arms"]} for r in rows
    }
    states = {r["case"]: {a["arm"]: a["state"] for a in r["arms"]} for r in rows}
    n_continue = {
        a: sum(1 for c in decisions if decisions[c][a].startswith("CONTINUE")) for a in arm_names
    }
    n_escalate = {
        a: sum(1 for c in decisions if "ESCALATE" in decisions[c][a]) for a in arm_names
    }
    distinct_states = {
        a: len({states[c][a] for c in states}) for a in arm_names
    }
    summary = {
        "n_cases": len(rows),
        "n_CONTINUE_per_arm": n_continue,
        "n_RETRY_plus_ESCALATE_per_arm": n_escalate,
        "n_distinct_states_per_arm": distinct_states,
        "notes": [
            "no arm can correctly output CONTINUE on these 5 (no grasp-supporting evidence)",
            "B1(=frozen D2) outputs CONTINUE on ALL 5 including both contact cases",
            "B2(=frozen D3) dz condition is mechanically unsatisfiable under pose-hold probe",
        ],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=1)

    hdr = f"{'case':9s} " + " ".join(f"{a:16s}" for a in arm_names) + " retry_ok audit"
    print(hdr)
    for r in rows:
        cells = " ".join(
            f"{decisions[r['case']][a]:16s}" for a in arm_names
        )
        ev = r["eval_only"]
        print(
            f"{r['case']:9s} {cells} {str(ev['retry_pick_success']):5s} {ev['audit_kind']}"
        )
    print(json.dumps(summary["n_distinct_states_per_arm"], ensure_ascii=False))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
