#!/usr/bin/env python3
"""VE-v0.1 Phase 4:对抗性反例测试(全部离线,只读真实帧或其变换)。

每个场景 = 具体输入 + 观察结果 + PASS/FAIL(修复或弃权机制生效与否)。
全局性质(ADV7):新臂(B1'/B3/B4)在任何对抗输入上都不得输出 CONTINUE 类决策、
不得声称"已持握";图像证据被视差/过期/矛盾污染时必须被隔离或降级。
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, "/workspace/yjx/workspace/RPent/analysis/research_context")
sys.path.insert(0, "/workspace/yjx/workspace/RPent/scripts")
from p1_ve01_evidence import build_evidence_claim  # noqa: E402
from p1_ve01_arms import arm_b1p, arm_b3, arm_b4  # noqa: E402
from p1_ve01_run import load_case  # noqa: E402

OUT_DEFAULT = "/workspace/yjx/rpent_data/p1_dev0/ve01/adversarial_results.json"
RUNS = "/workspace/yjx/rpent_data/p1_dev0/runs"

results = []


def record(scenario: str, observed: dict, passed: bool, mechanism: str) -> None:
    results.append(
        {"scenario": scenario, "observed": observed, "pass": passed, "mechanism": mechanism}
    )
    print(f"[{'PASS' if passed else 'FAIL'}] {scenario}: {mechanism}")


def arm_decisions(claim: dict) -> dict:
    return {
        "B1'": arm_b1p(claim),
        "B3": arm_b3(claim),
        "B4": arm_b4(claim),
    }


def no_continue(claim: dict) -> bool:
    return all(
        not a["decision"].startswith("CONTINUE") for a in arm_decisions(claim).values()
    )


def build_real(case: str, **kw) -> dict:
    d = load_case(case)
    label = kw.pop("label", case)
    base = dict(
        case=label,
        pre_agentview_path=d["pre_agentview_path"],
        pre_wrist_path=d["pre_wrist_path"],
        post_agentview_path=d["post_agentview_path"],
        post_wrist_path=d["post_wrist_path"],
        pre_gap=d["pre_gap"],
        post_gap=d["post_gap"],
        world_wrist_path=d["world_wrist_path"],
        eef_pos=d["eef_pos"],
        frame_age_s=d["frame_age_s"],
    )
    base.update(kw)
    return build_evidence_claim(**base)


def main() -> None:
    out_path = OUT_DEFAULT

    # ADV1 空夹爪完全闭合(真实 3 例):新臂不得把"闭合到底"误当持握/CONTINUE
    for case in ["t3_s1002", "t9_s1002", "t9_s1004"]:
        c = build_real(case)
        ok = (
            c["proprio_closure"]["closure_class"] == "CLOSED_TO_FLOOR"
            and no_continue(c)
            and c["inter_finger_content"]["claim"] == "ABSTAIN"
        )
        record(
            f"ADV1_empty_close:{case}",
            {
                "closure": c["proprio_closure"]["closure_class"],
                "B4": arm_b4(c)["decision"],
                "thin_edge_caveat": c["proprio_closure"].get("caveat"),
            },
            ok,
            "unobstructed-closure certification + inter-finger abstention; no CONTINUE claim",
        )

    # ADV2 遮挡/暗对暗(真实 t9_s1002):指间内容不可辨 → 必须弃权而非猜测
    c2 = build_real("t9_s1002")
    ok2 = (
        c2["validity"] == "VALID"
        and c2["inter_finger_content"]["claim"] == "ABSTAIN"
        and "MATERIAL" not in arm_b3(c2)["state"]
    )
    record(
        "ADV2_occlusion_dark_on_dark:t9_s1002",
        {"B3": arm_b3(c2)["state"], "inter_finger": c2["inter_finger_content"]["claim"]},
        ok2,
        "abstention on inter-finger content; only closure/geometric facts asserted",
    )

    # ADV3 wrist 前后纵向未对齐(把翻转校正关掉):整帧镜像差分必须被隔离
    c3 = build_real("t9_s1005", label="ADV3_misaligned_t9_s1005", pre_wrist_vertically_flipped=False)
    cm3 = c3["visual_camera_motion"]
    ok3 = cm3["camera_motion_flag"] and arm_b3(c3)["decision"].startswith("RETRY")
    record(
        "ADV3_wrist_misaligned",
        {
            "frac_changed": cm3["frac_pixels_changed_gt20"],
            "motion_kind": cm3["motion_kind"],
            "B3": arm_b3(c3)["decision"],
        },
        ok3,
        "whole-frame-change guard quarantines unaligned/flip-corrupted pair",
    )

    # ADV4 相机-臂运动像素变化(真实 t9_s1004):差分幅值最大但零信息
    c4 = build_real("t9_s1004")
    cm4 = c4["visual_camera_motion"]
    ok4 = cm4["camera_motion_flag"] and cm4["raw_mean_absdiff"] > 40
    record(
        "ADV4_camera_motion_parallax:t9_s1004",
        {
            "raw": cm4["raw_mean_absdiff"],
            "kind": cm4["motion_kind"],
            "B3": arm_b3(c4)["decision"],
        },
        ok4,
        "depth-parallax criterion (single-shift alignment provably insufficient)",
    )

    # ADV5 过期/复用帧:post 与 pre 同字节 → INVALID_STALE_FRAME;文件缺失 → INVALID
    with tempfile.TemporaryDirectory(dir="/workspace/yjx/tmp") as td:
        d5 = load_case("t9_s1005")
        stale_post = os.path.join(td, "stale_wrist.png")
        shutil.copyfile(d5["pre_wrist_path"], stale_post)
        c5 = build_real(
            "t9_s1005",
            label="ADV5_stale",
            post_wrist_path=stale_post,
            post_agentview_path=d5["pre_agentview_path"],  # agentview 也复用
        )
        ok5 = c5["validity"].startswith("INVALID_STALE") and c5["suggested_action"].startswith("RETRY")
        record(
            "ADV5_stale_frame_reuse",
            {"validity": c5["validity"], "action": c5["suggested_action"]},
            ok5,
            "byte-identical pre/post detection via SHA256",
        )
        c5b = build_real("t9_s1005", label="ADV5_missing", post_wrist_path=os.path.join(td, "ghost.png"))
        ok5b = c5b["validity"].startswith("INVALID_SOURCE_MISSING")
        record(
            "ADV5_missing_frame",
            {"validity": c5b["validity"]},
            ok5b,
            "missing-file guard",
        )

    # ADV6 证据矛盾:闭合无阻挡(指间应无厚物)+ 爪平面近场有材料 → TENSION,不得消解
    c6 = {
        "case": "ADV6_synth",
        "proprio_closure": {"closure_class": "CLOSED_TO_FLOOR", "obstruction_free": True},
        "visual_camera_motion": {"camera_motion_flag": False, "motion_kind": "NONE"},
        "geometric_context": {"usable": True, "dist_min_m": 0.0008},
        "inter_finger_content": {"claim": "ABSTAIN"},
    }
    b4_6 = arm_b4(c6)
    ok6 = b4_6["state"].startswith("TENSION") and not b4_6["decision"].startswith("CONTINUE")
    record(
        "ADV6_evidence_tension",
        {"B4_state": b4_6["state"], "B4_decision": b4_6["decision"]},
        ok6,
        "tension state escalates instead of resolving to a strong claim",
    )

    # ADV7 全局性质:全部真实案例 + 全部对抗构造上新臂零 CONTINUE、零持握主张
    all_claims = [build_real(c) for c in ["t3_s1002", "t9_s1002", "t9_s1003", "t9_s1004", "t9_s1005"]]
    all_claims += [c3, c6]
    ok7 = all(no_continue(c) for c in all_claims) and all(
        c["inter_finger_content"]["claim"] == "ABSTAIN" for c in all_claims if isinstance(c.get("inter_finger_content"), dict)
    )
    n_cont = sum(
        1
        for c in all_claims
        for a in arm_decisions(c).values()
        if a["decision"].startswith("CONTINUE")
    )
    record(
        "ADV7_global_no_false_continue",
        {"n_claim_inputs": len(all_claims), "n_continue_outputs": n_cont},
        ok7 and n_cont == 0,
        "property: B1'/B3/B4 never output CONTINUE without grasp-supporting evidence",
    )

    summary = {
        "n_scenarios": len(results),
        "n_pass": sum(1 for r in results if r["pass"]),
        "n_fail": sum(1 for r in results if not r["pass"]),
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"wrote {out_path}")
    sys.exit(0 if summary["n_fail"] == 0 else 1)


if __name__ == "__main__":
    main()
