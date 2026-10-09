#!/usr/bin/env python3
"""VE-v0.1 Phase 2 原型模块合成回归测试(无 GPU/无网络/不读私有数据)。"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from p1_ve01_evidence import (  # noqa: E402
    build_evidence_claim,
    camera_motion_guard,
    change_concentration,
    classify_closure,
    nearest_surface_metrics,
    phase_correlation_shift,
    summarize_claims,
)


def _pattern(h=256, w=256, seed=0):
    rng = np.random.default_rng(seed)
    img = rng.uniform(20, 220, size=(h, w, 3))
    # 加结构(否则相位相关无峰)
    yy, xx = np.mgrid[0:h, 0:w]
    img[:, :, 0] += 30 * np.sin(yy / 9.0) + 25 * np.cos(xx / 7.0)
    img[:, :, 1] += 28 * np.cos(yy / 11.0)
    img[:, :, 2] += 26 * np.sin(xx / 13.0)
    return np.clip(img, 0, 255)


class TestClassifyClosure(unittest.TestCase):
    def test_floor(self):
        r = classify_closure(0.069, 0.0027)
        self.assertEqual(r["closure_class"], "CLOSED_TO_FLOOR")
        self.assertTrue(r["obstruction_free"])
        self.assertIn("thin-edge", r["caveat"])

    def test_stall(self):
        r = classify_closure(0.0073, 0.0069)
        self.assertEqual(r["closure_class"], "STALLED_ABOVE_FLOOR")
        self.assertFalse(r["obstruction_free"])

    def test_no_move_stall(self):
        r = classify_closure(0.0045, 0.0045)
        self.assertEqual(r["closure_class"], "STALLED_ABOVE_FLOOR")

    def test_ambiguous_band(self):
        r = classify_closure(0.05, FLOOR := 0.0035 + 0.0004)
        self.assertEqual(r["closure_class"], "AMBIGUOUS")
        self.assertIsNone(r["obstruction_free"])

    def test_nonfinite(self):
        r = classify_closure(float("nan"), 0.002)
        self.assertEqual(r["closure_class"], "UNKNOWN")

    def test_no_command(self):
        r = classify_closure(0.02, 0.02, commanded_close=False)
        self.assertEqual(r["closure_class"], "UNKNOWN")


class TestPhaseCorrelation(unittest.TestCase):
    def test_detect_shift(self):
        # 约定:返回 (dx,dy) 为"对齐平移"(b 需平移多少回到 a);
        # 内容右移 5px(np.roll +5)→ 对齐移 −5px。
        a = _pattern(seed=1)
        b = np.roll(np.roll(a, 5, axis=1), 3, axis=0)
        sh = phase_correlation_shift(a, b)
        self.assertEqual(sh["dx"], -5)
        self.assertEqual(sh["dy"], -3)

    def test_camera_motion_flag_on_parallax(self):
        a = _pattern(seed=2)
        b = np.roll(a, 7, axis=1)
        g = camera_motion_guard(a, b)
        self.assertTrue(g["camera_motion_flag"])
        self.assertGreater(g["parallax_explained_frac"], 0.5)

    def test_no_flag_on_local_change(self):
        a = _pattern(seed=3)
        b = a.copy()
        b[100:130, 100:130] += 60  # 局部变化,无全局平移
        g = camera_motion_guard(a, b)
        self.assertFalse(g["camera_motion_flag"])

    def test_whole_frame_depth_parallax_flag(self):
        # 深度相关视差:不同行带位移不同 → 单平移对不齐,但整帧变化占比高
        a = _pattern(seed=6)
        b = a.copy()
        for band, sh in [((0, 85), 4), ((85, 170), 8), ((170, 256), 13)]:
            b[band[0] : band[1]] = np.roll(a[band[0] : band[1]], sh, axis=1)
        g = camera_motion_guard(a, b)
        self.assertTrue(g["camera_motion_flag"])
        self.assertEqual(g["motion_kind"], "WHOLE_FRAME_DEPTH_PARALLAX")
        self.assertGreater(g["frac_pixels_changed_gt20"], 0.4)


class TestChangeConcentration(unittest.TestCase):
    def test_centroid(self):
        a = _pattern(seed=4)
        b = a.copy()
        b[190:220, 30:60] += 80  # 左下角
        r = change_concentration(a, b)
        self.assertIsNotNone(r["centroid"])
        cx, cy = r["centroid"]
        self.assertLess(cx, 0.35)
        self.assertGreater(cy, 0.6)

    def test_no_change(self):
        a = _pattern(seed=5)
        r = change_concentration(a, a.copy())
        self.assertLess(r["hot_pixels"], 20)


class TestNearestSurface(unittest.TestCase):
    def test_plane_below_eef(self):
        # 256x256 每像素世界坐标:z=0.95 平面,x/y 网格
        yy, xx = np.mgrid[0:256, 0:256]
        world = np.stack(
            [xx * 0.002 - 0.25, yy * 0.002 - 0.25, np.full((256, 256), 0.95)],
            axis=-1,
        ).astype(np.float32)
        r = nearest_surface_metrics(world, [0.0, 0.0, 1.0])
        self.assertTrue(r["usable"])
        self.assertAlmostEqual(r["dist_min_m"], 0.05, places=2)
        self.assertIn("nearest_point_rc", r)
        # 近场测试:平面抬到 z=0.99 → 最近 0.01m;近场=中心小圆盘(非全图),
        # 质心应落在图像中心(x≈0,y≈0 映射到 (0.5,0.5) 归一化坐标)。
        world2 = world.copy()
        world2[:, :, 2] = 0.99
        r2 = nearest_surface_metrics(world2, [0.0, 0.0, 1.0])
        self.assertAlmostEqual(r2["dist_min_m"], 0.01, places=2)
        self.assertGreater(r2["near_field_frac"], 0.001)
        self.assertLess(r2["near_field_frac"], 0.05)
        self.assertIn("near_centroid_rc", r2)
        ry, rx = r2["near_centroid_rc"]
        self.assertLess(abs(ry - 0.5), 0.1)
        self.assertLess(abs(rx - 0.5), 0.1)

    def test_invalid_points_filtered(self):
        world = np.zeros((256, 256, 3), dtype=np.float32)  # z=0 → 全部无效
        r = nearest_surface_metrics(world, [0, 0, 1])
        self.assertFalse(r["usable"])


class TestBuildClaim(unittest.TestCase):
    def _make_pngs(self, root):
        from PIL import Image

        pre_av = _pattern(seed=10)
        post_av = pre_av.copy()
        post_av[30:60, 30:60] += 70  # agentview 局部变化(夹爪区)
        pre_w = _pattern(seed=11)  # 将被 runner 翻转;测试里直接给未翻转语义的图
        post_w = pre_w.copy()
        post_w[200:230, 120:150] += 70  # wrist 局部变化
        paths = {}
        for name, arr in [
            ("pre_av.png", pre_av),
            ("post_av.png", post_av),
            ("pre_w.png", pre_w),
            ("post_w.png", post_w),
        ]:
            p = os.path.join(root, name)
            Image.fromarray(arr.astype(np.uint8)).save(p)
            paths[name] = p
        return paths

    def test_end_to_end_floor_case(self):
        with tempfile.TemporaryDirectory() as root:
            paths = self._make_pngs(root)
            c = build_evidence_claim(
                case="synthetic_floor",
                pre_agentview_path=paths["pre_av.png"],
                pre_wrist_path=paths["pre_w.png"],
                post_agentview_path=paths["post_av.png"],
                post_wrist_path=paths["post_w.png"],
                pre_gap=0.069,
                post_gap=0.0027,
                pre_wrist_vertically_flipped=False,
            )
            self.assertEqual(c["validity"], "VALID")
            self.assertEqual(c["state_class"], "CLOSURE_UNOBSTRUCTED")
            self.assertEqual(c["suggested_action"], "RETRY")
            self.assertEqual(c["inter_finger_content"]["claim"], "ABSTAIN")

    def test_end_to_end_stall_case(self):
        with tempfile.TemporaryDirectory() as root:
            paths = self._make_pngs(root)
            c = build_evidence_claim(
                case="synthetic_stall",
                pre_agentview_path=paths["pre_av.png"],
                pre_wrist_path=paths["pre_w.png"],
                post_agentview_path=paths["post_av.png"],
                post_wrist_path=paths["post_w.png"],
                pre_gap=0.0073,
                post_gap=0.0069,
                pre_wrist_vertically_flipped=False,
            )
            self.assertEqual(c["state_class"], "CLOSURE_OBSTRUCTED_LOCATION_UNRESOLVED")
            self.assertIn("TRIAGE", c["sufficiency"])

    def test_missing_source_invalid(self):
        with tempfile.TemporaryDirectory() as root:
            paths = self._make_pngs(root)
            c = build_evidence_claim(
                case="synthetic_missing",
                pre_agentview_path=paths["pre_av.png"],
                pre_wrist_path=os.path.join(root, "nope.png"),
                post_agentview_path=paths["post_av.png"],
                post_wrist_path=paths["post_w.png"],
                pre_gap=0.02,
                post_gap=0.002,
            )
            self.assertTrue(c["validity"].startswith("INVALID"))
            self.assertEqual(c["sufficiency"], "INSUFFICIENT")

    def test_forbidden_key_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            paths = self._make_pngs(root)
            c = build_evidence_claim(
                case="synthetic_leak",
                pre_agentview_path=paths["pre_av.png"],
                pre_wrist_path=paths["pre_w.png"],
                post_agentview_path=paths["post_av.png"],
                post_wrist_path=paths["post_w.png"],
                pre_gap=0.02,
                post_gap=0.002,
                model_vision={"check_success": True},  # 故意泄漏特权键
                pre_wrist_vertically_flipped=False,
            )
            self.assertEqual(c["validity"], "INVALID_FORBIDDEN_KEY")

    def test_summarize(self):
        with tempfile.TemporaryDirectory() as root:
            paths = self._make_pngs(root)
            cs = [
                build_evidence_claim(
                    case=f"syn{i}",
                    pre_agentview_path=paths["pre_av.png"],
                    pre_wrist_path=paths["pre_w.png"],
                    post_agentview_path=paths["post_av.png"],
                    post_wrist_path=paths["post_w.png"],
                    pre_gap=0.06,
                    post_gap=0.0027 if i == 0 else 0.0069,
                    pre_wrist_vertically_flipped=False,
                )
                for i in range(2)
            ]
            s = summarize_claims(cs)
            self.assertEqual(s["n_cases"], 2)
            self.assertEqual(s["n_valid"], 2)
            self.assertEqual(s["n_closure_unobstructed"], 1)
            self.assertEqual(s["n_closure_obstructed"], 1)
            # 汇总 JSON 可序列化
            json.dumps(s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
