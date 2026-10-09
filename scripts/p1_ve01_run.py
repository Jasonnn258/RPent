#!/usr/bin/env python3
"""VE-v0.1 Phase 2 运行器:对 5 个真实 probe 案例生成结构化 Evidence Claim。

只读输入:
  - runs/p1dev0_{case}/p1_dev0_events.jsonl(trigger pre_images / pre_legal / probe post_legal)
  - runs/p1dev0_{case}_{ts}/(episode 输出:pre 图像、world_wrist 3D 图)
  - runs/p1dev0_{case}/probe_frames/(post 图像)

MODEL_VISION:Phase 1 由大模型看板产生的**主观**判读,仅作为外部参考字段写入
(标注 external_subjective=true),不参与确定性计算。

输出:artifacts/p1_dev0/ve01/evidence_claims.json(私有,不入 Git)。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, "/workspace/yjx/workspace/RPent/analysis/research_context")
from p1_ve01_evidence import build_evidence_claim, summarize_claims  # noqa: E402

RUNS = "/workspace/yjx/rpent_data/p1_dev0/runs"
OUT_DEFAULT = "/workspace/yjx/rpent_data/p1_dev0/ve01/evidence_claims.json"

# Phase 1 MODEL_VISION 判读(主观,外部参考;board = 3x2 对照拼图)
MODEL_VISION = {
    "t3_s1002": {
        "external_subjective": True,
        "verdict": "UNCERTAIN(倾向未夹持)",
        "detail": "碗在爪下方偏右静止;wrist 碗内壁充满,爪尖底缘;无新夹持内容;接触点被碗沿遮挡",
    },
    "t9_s1002": {
        "external_subjective": True,
        "verdict": "UNKNOWN(指间内容)",
        "detail": "爪悬深色抽屉上方,暗对暗;碗在左侧台面;前后近同",
    },
    "t9_s1003": {
        "external_subjective": True,
        "verdict": "CONFIDENT 空闭合(邻接非夹持)",
        "detail": "碗在爪尖下方/旁侧未动;wrist 碗在爪前下方不在指间;diff 集中于臂",
    },
    "t9_s1004": {
        "external_subjective": True,
        "verdict": "高置信纯相机/臂运动、无物体接触",
        "detail": "碗像素级不动,diff 仅臂缘;wrist 整帧视差滑动(mean 45.8),无夹持内容",
    },
    "t9_s1005": {
        "external_subjective": True,
        "verdict": "CONFIDENT 空闭合",
        "detail": "碗在闭合爪尖下方偏侧未动;wrist 碗在爪前方下方,无变化",
    },
}

CASES = ["t3_s1002", "t9_s1002", "t9_s1003", "t9_s1004", "t9_s1005"]


def load_case(case: str) -> dict:
    ev_path = f"{RUNS}/p1dev0_{case}/p1_dev0_events.jsonl"
    events = [json.loads(l) for l in open(ev_path)]
    by_ev = {}
    for e in events:
        by_ev.setdefault(e["ev"], e)
    trig, probe = by_ev["trigger"], by_ev["probe"]
    pre_imgs = {im["name"]: im["path"] for im in trig["pre_images"]}
    step_idx = trig["step_idx"]
    ep_dir = sorted(glob.glob(f"{RUNS}/p1dev0_{case}_*"))[0]
    return {
        "pre_agentview_path": pre_imgs["policy_image_agentview_low"],
        "pre_wrist_path": pre_imgs["image_wrist_low"],
        "post_agentview_path": f"{RUNS}/p1dev0_{case}/probe_frames/probe_agentview.png",
        "post_wrist_path": f"{RUNS}/p1dev0_{case}/probe_frames/probe_wrist.png",
        "pre_gap": trig["pre_legal"]["gripper_gap"],
        "post_gap": probe["post_legal"]["gripper_gap"],
        "eef_pos": trig["pre_legal"]["robot0_eef_pos"],
        "world_wrist_path": f"{ep_dir}/world_wrist/world_wrist_{step_idx:02d}.npy",
        "step_idx": step_idx,
        "frame_age_s": probe.get("t", 0) - trig.get("t", 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()
    claims = []
    for case in CASES:
        d = load_case(case)
        claim = build_evidence_claim(
            case=case,
            pre_agentview_path=d["pre_agentview_path"],
            pre_wrist_path=d["pre_wrist_path"],
            post_agentview_path=d["post_agentview_path"],
            post_wrist_path=d["post_wrist_path"],
            pre_gap=d["pre_gap"],
            post_gap=d["post_gap"],
            world_wrist_path=d["world_wrist_path"],
            eef_pos=d["eef_pos"],
            pre_wrist_vertically_flipped=True,  # dump_state 存 pre 翻转,post 原样
            model_vision=MODEL_VISION.get(case),
            frame_age_s=d["frame_age_s"],
        )
        claims.append(claim)
        cm = claim["visual_camera_motion"]
        print(
            f"{case}: closure={claim['proprio_closure']['closure_class']:20s} "
            f"state={claim['state_class']:38s} "
            f"shift={cm['shift_px']} parallax_flag={cm['camera_motion_flag']} "
            f"raw={cm['raw_mean_absdiff']:6.2f} aligned_res={cm['aligned_residual']:6.2f} "
            f"explained={cm['parallax_explained_frac']}"
        )
        if claim.get("geometric_context", {}) and claim["geometric_context"].get("usable"):
            g = claim["geometric_context"]
            print(
                f"    nearest_surface: dist_min={g['dist_min_m']}m "
                f"p05={g['dist_p05_m']}m nearest_xyz={g['nearest_point_xyz']}"
            )
    summary = summarize_claims(claims)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "claims": claims}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
