#!/usr/bin/env python3
"""P1 Visual Evidence Prototype v0.1(VE-v0.1 Phase 2)。

离线、确定性(numpy+PIL,无网络/无 GPU/无训练)的结构化 Evidence Claim 生成器。
针对 P1-DEV0 的 probe 场景(失败 pick 后 set_gripper(+1,10) 定点夹紧),从**仅合法
观测**产出机器可审计的证据主张:

  输入(全部决策时可见,禁入特权真值):
    - pre/post RGB(agentview + wrist;pre wrist 需按源约定纵向翻正)
    - pre/post proprio(gripper_gap / eef_z;来自事件文件 pre_legal/post_legal)
    - trigger step 的 wrist 逐像素世界坐标图(episode 自有 SAM3/深度管线产物)

  输出 EvidenceClaim:
    - source/validity:文件路径+SHA256、尺寸、时间序(pre 先于 post)
    - proprio_closure:闭合结局分类(闭合无阻挡 / 停住=物理阻挡 / 未知)
    - visual_camera_motion:相位相关全局平移估计 + 对齐后残差(视差护栏)
    - visual_change:对齐后的变化统计(变化集中的区域质心)
    - geometric_context:腕视世界图最近表面距离(以"取物瞄准先验"解释)
    - inter_finger_content:一律 ABSTAIN(Phase 1 实测 256px 下 0/5 可辨,不臆造)
    - sufficiency + suggested_action:证据充分性分级与动作建议(仍属离线候选)

方法学纪律:
  1. 本模块不产生任何"物理持握真值"主张;能证明的只有「闭合是否受机械阻挡」
     与「图像变化是否被相机运动解释」两类可复核事实。
  2. MODEL_VISION(大模型看图)结论只能作为外部主观参考传入并标注,不参与
     确定性计算,绝不写成物理真值。
  3. 单帧证据与前后时序严格分离;本模块只做 pre/post 同帧对差分。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

# ---------------- 常量(全部来自 21 集合法观测标定,见报告 §1.2/§1.3) ----------------
# 空闭合机械地板:3 例空闭合 probe 收敛于 2.48/2.67/3.07mm,pick 末端最浅 2.2mm。
FLOOR_MAX_M = 0.0035
# 地板之上的模糊带(考虑控制收敛公差),落在此带判 AMBIGUOUS 而非 STALLED。
AMBIGUOUS_BAND_M = 0.0008
# 相机运动护栏:对齐平移超过该像素数即挂 CAMERA_MOTION(以 256px 图为准)。
CAMERA_MOTION_PX = 1.5
# 残差显著下降比例:对齐后残差 < 原始差分 × 该系数 → 变化主要为视差。
PARALLASS_EXPLAINED_FRAC = 0.5
# 整帧变化占比阈值:diff>20 的像素占比超过该值 → 深度相关视差(单平移对不齐)
# 也构成相机运动证据(t9_s1004 实测:63.5% 像素变化、对齐残差不降)。
WHOLE_FRAME_CHANGE_FRAC = 0.4
# 近场半径:距 EEF 该半径内的腕视表面点视为"爪平面近场"(接触带上下文)。
NEAR_FIELD_M = 0.02

FORBIDDEN_KEYS = ("check_success", "sim_measurement", "object_pos", "audit_only")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_rgb(path: str) -> np.ndarray:
    """读 PNG 为 float64 HxWx3(0-255)。失败抛 IOError(由上层转 INVALID_SOURCE)。"""
    from PIL import Image

    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.float64)


def to_gray(img: np.ndarray) -> np.ndarray:
    return img @ np.array([0.299, 0.587, 0.114])


# ---------------- proprio:闭合结局分类 ----------------
def classify_closure(
    pre_gap: float,
    post_gap: float,
    commanded_close: bool = True,
) -> dict:
    """由 probe 前后 gap 判闭合结局。

    CLOSED_TO_FLOOR:post_gap 落在机械地板带 → 闭合行程无阻挡
                     (不排除 <3.5mm 薄沿夹持——该情形 gap 轴原理上不可分,见 §1.3)
    STALLED_ABOVE_FLOOR:命令闭合但 post_gap 显著高于地板 → 指端受物理阻挡
                     (阻挡物可在指间也可在指外,单凭 proprio 不能定位)
    AMBIGUOUS / UNKNOWN:带内或数据缺失。
    """
    try:
        pre_gap = float(pre_gap)
        post_gap = float(post_gap)
    except (TypeError, ValueError):
        return {"closure_class": "UNKNOWN", "reason": "non-finite gap"}
    if not (np.isfinite(pre_gap) and np.isfinite(post_gap)):
        return {"closure_class": "UNKNOWN", "reason": "non-finite gap"}
    if not commanded_close:
        return {"closure_class": "UNKNOWN", "reason": "no close commanded"}
    out = {
        "pre_gap_m": round(pre_gap, 5),
        "post_gap_m": round(post_gap, 5),
        "closure_travel_m": round(pre_gap - post_gap, 5),
    }
    if post_gap <= FLOOR_MAX_M:
        out["closure_class"] = "CLOSED_TO_FLOOR"
        out["obstruction_free"] = True
        out["caveat"] = "thin-edge pinch (<floor+band) not excludable by gap alone"
    elif post_gap <= FLOOR_MAX_M + AMBIGUOUS_BAND_M:
        out["closure_class"] = "AMBIGUOUS"
        out["obstruction_free"] = None
    else:
        out["closure_class"] = "STALLED_ABOVE_FLOOR"
        out["obstruction_free"] = False
        out["note"] = (
            "close command with proven travel capacity (69mm->2.67mm in 10 steps "
            "observed); stall above floor implies mechanical obstruction"
        )
    return out


# ---------------- 视觉:相机运动护栏 ----------------
def phase_correlation_shift(a: np.ndarray, b: np.ndarray) -> dict:
    """估计 a→b 的全局整数平移(相位相关)。返回 (dx,dy,peak)。"""
    ga = to_gray(a)
    gb = to_gray(b)
    ga = ga - ga.mean()
    gb = gb - gb.mean()
    fa = np.fft.rfft2(ga)
    fb = np.fft.rfft2(gb)
    cp = fa * np.conj(fb)
    cp /= np.maximum(np.abs(cp), 1e-12)
    corr = np.fft.irfft2(cp, s=ga.shape)
    peak_idx = np.unravel_index(np.argmax(corr), corr.shape)
    peak = float(corr[peak_idx])
    dy, dx = int(peak_idx[0]), int(peak_idx[1])
    H, W = ga.shape
    if dy > H // 2:
        dy -= H
    if dx > W // 2:
        dx -= W
    return {"dx": dx, "dy": dy, "peak": round(peak, 4)}


def shifted_diff(a: np.ndarray, b: np.ndarray, dx: int, dy: int) -> float:
    """按平移对齐后取有效重叠区的平均绝对差。"""
    H, W = a.shape[:2]
    ys = slice(max(0, dy), min(H, H + dy))
    xs = slice(max(0, dx), min(W, W + dx))
    ys2 = slice(max(0, -dy), min(H, H - dy))
    xs2 = slice(max(0, -dx), min(W, W - dx))
    if ys.stop <= ys.start or xs.stop <= xs.start:
        return float("nan")
    return float(np.abs(a[ys, xs] - b[ys2, xs2]).mean())


def camera_motion_guard(pre: np.ndarray, post: np.ndarray) -> dict:
    """视差护栏:估计全局平移,比较原始差分与对齐后残差。

    两条独立判据,任一成立即挂旗:
      (a) 可对齐视差:|shift|>阈值 且 对齐后残差显著下降(纯平移);
      (b) 整帧变化:diff>20 像素占比 > 阈值 —— 深度相关视差(各深度位移不同,
          单一平移原理上对不齐,残差不降不代表无相机运动;t9_s1004 实测)。
    """
    d = np.abs(pre - post).mean(axis=2)
    raw = float(d.mean())
    frac_changed = float((d > 20).mean())
    sh = phase_correlation_shift(pre, post)
    res = shifted_diff(pre, post, sh["dx"], sh["dy"])
    alignable = (
        max(abs(sh["dx"]), abs(sh["dy"])) > CAMERA_MOTION_PX
        and (1.0 - res / raw) > PARALLASS_EXPLAINED_FRAC
        if raw > 1e-9
        else False
    )
    whole_frame = frac_changed > WHOLE_FRAME_CHANGE_FRAC
    return {
        "shift_px": [sh["dx"], sh["dy"]],
        "correlation_peak": sh["peak"],
        "raw_mean_absdiff": round(raw, 3),
        "frac_pixels_changed_gt20": round(frac_changed, 3),
        "aligned_residual": round(res, 3),
        "parallax_explained_frac": round(1.0 - res / raw, 3) if raw > 1e-9 else 0.0,
        "camera_motion_flag": bool(alignable or whole_frame),
        "motion_kind": (
            "ALIGNABLE_TRANSLATION"
            if alignable
            else ("WHOLE_FRAME_DEPTH_PARALLAX" if whole_frame else "NONE")
        ),
        "interpretation": (
            "change dominated by camera/arm motion; pixel diff magnitude unusable"
            if alignable or whole_frame
            else "no dominant global translation"
        ),
    }


def change_concentration(img_pre: np.ndarray, img_post: np.ndarray) -> dict:
    """变化集中区域质心(无语义,只报告几何位置,语义判断由人/模型视觉负责)。"""
    d = np.abs(img_pre - img_post).mean(axis=2)
    thr = max(d.mean() + 2 * d.std(), 1.0)
    mask = d > thr
    n = int(mask.sum())
    if n < 20:
        return {"hot_pixels": n, "centroid": None, "note": "no concentrated change"}
    ys, xs = np.nonzero(mask)
    H, W = d.shape
    return {
        "hot_pixels": n,
        "centroid": [round(float(xs.mean()) / W, 3), round(float(ys.mean()) / H, 3)],
        "hot_frac": round(n / mask.size, 4),
    }


# ---------------- 几何:腕视世界图上下文 ----------------
def nearest_surface_metrics(world: np.ndarray, eef_pos) -> dict:
    """腕视逐像素世界坐标 → 最近表面距离 + 近场占据(合法几何观测,无物体语义)。

    解释先验(显式声明,非真值):pi0_pick 失败末刻腕相机大体朝向拾取目标,
    故爪平面近场≈目标面;该先验在 pick 早期失败(未及目标)时不成立。
    near_centroid_rc 落在图像中下部(腕视指间区投影)时,配合 stall 信号支持
    "阻挡物在爪平面附近";仅几何事实,不声称物体被夹。
    """
    try:
        eef = np.asarray(eef_pos, dtype=float)
    except (TypeError, ValueError):
        return {"usable": False, "reason": "bad eef"}
    if eef.shape != (3,) or not np.isfinite(eef).all():
        return {"usable": False, "reason": "bad eef"}
    if world.ndim != 3 or world.shape[2] != 3:
        return {"usable": False, "reason": "bad world map"}
    valid = np.isfinite(world).all(axis=2) & (world[:, :, 2] > 0.05)
    if valid.sum() < 50:
        return {"n_valid": int(valid.sum()), "usable": False}
    dist = np.linalg.norm(world - eef, axis=2)  # 无效像素距离无意义,用 mask 过滤
    dist_masked = np.where(valid, dist, np.inf)
    i_rc = np.unravel_index(np.argmin(dist_masked), dist_masked.shape)
    near = valid & (dist < NEAR_FIELD_M)
    H, W = dist.shape
    out = {
        "n_valid": int(valid.sum()),
        "usable": True,
        "dist_min_m": round(float(dist_masked[i_rc]), 4),
        "nearest_point_rc": [int(i_rc[0]), int(i_rc[1])],
        "nearest_point_xyz": [round(float(v), 4) for v in world[i_rc]],
        "dist_p05_m": round(float(np.percentile(dist[valid], 5)), 4),
        "near_field_frac": round(float(near.mean()), 4),
        "aiming_prior": "nearest surface ~= pick target only if camera still aimed (early-fail violates)",
    }
    if near.sum() >= 20:
        ys, xs = np.nonzero(near)
        out["near_centroid_rc"] = [
            round(float(ys.mean()) / H, 3),
            round(float(xs.mean()) / W, 3),
        ]
    return out


# ---------------- Evidence Claim 组装 ----------------
def build_evidence_claim(
    case: str,
    pre_agentview_path: str,
    pre_wrist_path: str,
    post_agentview_path: str,
    post_wrist_path: str,
    pre_gap: float,
    post_gap: float,
    world_wrist_path: str | None = None,
    eef_pos=None,
    pre_wrist_vertically_flipped: bool = True,
    model_vision: dict | None = None,
    frame_age_s: float | None = None,
) -> dict:
    """组装单个 probe 案例的结构化 EvidenceClaim。

    文件缺失 → INVALID_SOURCE_MISSING;pre/post 同相机字节级相同 → INVALID_STALE_FRAME
    (同一帧不可能同时是前后观测);frame_age_s(可选,post−pre 拍摄墙钟差)过大记
    STALE_SUSPECT(不判 INVALID,只降置信)。
    """
    claim = {
        "case": case,
        "claim_version": "ve01",
        "source": {
            "pre_agentview": pre_agentview_path,
            "pre_wrist": pre_wrist_path,
            "post_agentview": post_agentview_path,
            "post_wrist": post_wrist_path,
        },
        "validity": "VALID",
        "proprio_closure": None,
        "visual_camera_motion": None,
        "visual_change": None,
        "geometric_context": None,
        "inter_finger_content": {
            "claim": "ABSTAIN",
            "reason": "256px wrist cannot resolve inter-finger object material (0/5 in Phase 1 audit)",
        },
        "model_vision_external": model_vision or None,
        "state_class": None,
        "sufficiency": None,
        "suggested_action": None,
    }
    paths = [pre_agentview_path, pre_wrist_path, post_agentview_path, post_wrist_path]
    shas = {}
    for p in paths:
        if not Path(p).exists():
            claim["validity"] = f"INVALID_SOURCE_MISSING:{Path(p).name}"
            claim["sufficiency"] = "INSUFFICIENT"
            claim["suggested_action"] = "RETRY(default;no usable evidence)"
            return claim
        shas[p] = _sha256(p)
        claim["source"][Path(p).name + "_sha256"] = shas[p][:16]
    # 过期/复用帧检测:同相机 pre/post 字节级相同 → 不是新观测
    if shas[pre_agentview_path] == shas[post_agentview_path]:
        claim["validity"] = "INVALID_STALE_FRAME(agentview)"
    if shas[pre_wrist_path] == shas[post_wrist_path]:
        claim["validity"] = "INVALID_STALE_FRAME(wrist)"
    if claim["validity"] != "VALID":
        claim["sufficiency"] = "INSUFFICIENT(stale)"
        claim["suggested_action"] = "RETRY(default;no fresh evidence)"
        return claim
    if frame_age_s is not None and frame_age_s > 120.0:
        claim["freshness"] = f"STALE_SUSPECT(age={frame_age_s:.0f}s>120s)"

    pre_av = load_rgb(pre_agentview_path)
    post_av = load_rgb(post_agentview_path)
    pre_w = load_rgb(pre_wrist_path)
    post_w = load_rgb(post_wrist_path)
    # 源约定:dump_state 存的 pre wrist 是纵向翻转的;post probe 原样 → 翻正再比
    if pre_wrist_vertically_flipped:
        pre_w = pre_w[::-1]

    claim["proprio_closure"] = classify_closure(pre_gap, post_gap)
    claim["visual_camera_motion"] = camera_motion_guard(pre_w, post_w)
    claim["visual_change"] = {
        "agentview": change_concentration(pre_av, post_av),
        "wrist_aligned": change_concentration(
            pre_w, np.roll(post_w, shift=claim["visual_camera_motion"]["shift_px"][0], axis=1)
        ),
    }
    if world_wrist_path and Path(world_wrist_path).exists():
        world = np.load(world_wrist_path)
        claim["geometric_context"] = nearest_surface_metrics(world, eef_pos)
        claim["source"]["world_wrist"] = world_wrist_path

    # ---- 状态分类与充分性(保守;只主张可复核事实) ----
    cc = claim["proprio_closure"]["closure_class"]
    parallax = claim["visual_camera_motion"]["camera_motion_flag"]
    if cc == "CLOSED_TO_FLOOR":
        claim["state_class"] = "CLOSURE_UNOBSTRUCTED"
        claim["sufficiency"] = "SUFFICIENT_FOR_RETRY_NO_FURTHER_PROBE_EVIDENCE"
        claim["suggested_action"] = "RETRY"
    elif cc == "STALLED_ABOVE_FLOOR":
        claim["state_class"] = "CLOSURE_OBSTRUCTED_LOCATION_UNRESOLVED"
        claim["sufficiency"] = (
            "INSUFFICIENT_FOR_CONTINUE(low-res inter-finger unresolved); "
            "TRIAGE: hi-res wrist or lift-test would have information value"
        )
        claim["suggested_action"] = "RETRY(now)/ESCALATE_EVIDENCE(if CONTINUE is considered)"
    else:
        claim["state_class"] = "UNKNOWN"
        claim["sufficiency"] = "INSUFFICIENT"
        claim["suggested_action"] = "RETRY(default)"
    if parallax:
        claim["visual_change"]["wrist_aligned"]["parallax_warning"] = (
            "raw wrist diff dominated by arm/camera motion; ignore magnitude"
        )
    # 泄漏自检:任何禁入键出现在 claim 里(递归搜)即标 INVALID
    def _has_forbidden(obj) -> bool:
        if isinstance(obj, dict):
            return any(k in FORBIDDEN_KEYS or _has_forbidden(v) for k, v in obj.items())
        if isinstance(obj, list):
            return any(_has_forbidden(v) for v in obj)
        return False

    if _has_forbidden(claim):
        claim["validity"] = "INVALID_FORBIDDEN_KEY"
    return claim


def summarize_claims(claims: list[dict]) -> dict:
    """跨案例汇总(Phase 3 用)。"""
    n = len(claims)
    by = lambda f: sum(1 for c in claims if f(c))  # noqa: E731
    return {
        "n_cases": n,
        "n_valid": by(lambda c: c["validity"] == "VALID"),
        "n_closure_unobstructed": by(lambda c: c["state_class"] == "CLOSURE_UNOBSTRUCTED"),
        "n_closure_obstructed": by(lambda c: c["state_class"] == "CLOSURE_OBSTRUCTED_LOCATION_UNRESOLVED"),
        "n_camera_motion_flag": by(lambda c: c["visual_camera_motion"]["camera_motion_flag"]),
        "n_inter_finger_abstain": by(lambda c: c["inter_finger_content"]["claim"] == "ABSTAIN"),
        "n_sufficient_for_retry": by(
            lambda c: c["sufficiency"].startswith("SUFFICIENT_FOR_RETRY")
        ),
    }


if __name__ == "__main__":
    print(json.dumps({"module": "p1_ve01_evidence", "floor_max_m": FLOOR_MAX_M}))
