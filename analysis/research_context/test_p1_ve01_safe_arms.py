"""VE01.1 offline conservative eligibility: synthetic, no GPU/no private data."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from p1_ve01_safe_arms import assess, summarize


def case(i=1, closure="STALLED_ABOVE_FLOOR", dist=.0005):
    post_gap = (.0027 if closure == "CLOSED_TO_FLOOR"
                else .0039 if closure == "AMBIGUOUS" else .00696)
    return {
        "case": f"synthetic_case{i}",
        "validity": "VALID",
        "inter_finger_content": {"claim": "ABSTAIN"},
        "proprio_closure": {
            "pre_gap_m": .00731,
            "post_gap_m": post_gap,
            "closure_class": closure,
        },
        "visual_camera_motion": {
            "camera_motion_flag": False,
            "motion_kind": "NONE",
        },
        "geometric_context": {
            "usable": True, "dist_min_m": dist,
            "nearest_point_rc": [213, 128],
        },
    }


class TestVE01SafeReinterpretation(unittest.TestCase):
    def test_eef_nearest_05mm_is_not_verified_object_contact(self):
        c = case()
        a = assess(c)
        self.assertTrue(a["eligible"])
        self.assertEqual(a["geometry"], "SURFACE_NEAR_EEF_IDENTITY_UNKNOWN")
        self.assertEqual(a["state"], "GAP_PLATEAU_CAUSE_UNKNOWN")
        self.assertEqual(a["object_contact"], "UNKNOWN")
        self.assertEqual(a["held_grasp"], "UNKNOWN")
        self.assertIn("not independent physical contact labels", a["inference_limit"])

    def test_fully_closed_can_still_hide_thin_object(self):
        c = case(closure="CLOSED_TO_FLOOR", dist=.020)
        c["proprio_closure"]["pre_gap_m"] = .069
        c["proprio_closure"]["post_gap_m"] = .0027
        a = assess(c)
        self.assertTrue(a["eligible"])
        self.assertEqual(a["state"], "NEAR_MIN_GAP_OBJECT_PRESENCE_UNKNOWN")
        self.assertEqual(a["held_grasp"], "UNKNOWN")
        self.assertEqual(a["decision"], "RETRY")

    def test_invalid_or_stale_downgrades_before_reading_fields(self):
        for invalid in ("INVALID_SOURCE_MISSING", "INVALID_STALE_FRAME",
                        "INVALID_FORBIDDEN_KEY"):
            c = {"case": "bad", "validity": invalid}
            a = assess(c)
            self.assertFalse(a["eligible"])
            self.assertEqual(a["decision"], "RETRY+ABSTAIN")
        c = case()
        c["freshness"] = "STALE_SUSPECT(age=200s>120s)"
        self.assertEqual(assess(c)["decision"], "RETRY+ABSTAIN")
        self.assertEqual(assess({})["decision"], "RETRY+ABSTAIN")

    def test_nested_audit_truth_field_is_denied_even_when_marked_valid(self):
        c = case()
        c["model_vision_external"] = {"metadata": {"target_pos": [0, 0, 1]}}
        r = assess(c)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["reason"], "PRIVILEGED_FIELD_IN_CLAIM")
        self.assertEqual(r["decision"], "RETRY+ABSTAIN")

    def test_flagged_whole_frame_change_is_not_proof_of_parallax(self):
        c = case()
        c["visual_camera_motion"]["camera_motion_flag"] = True
        c["visual_camera_motion"]["motion_kind"] = "WHOLE_FRAME_DEPTH_PARALLAX"
        r = assess(c)
        self.assertEqual(r["image_quality"], "IMAGE_CHANGE_UNATTRIBUTABLE")
        self.assertEqual(r["object_contact"], "UNKNOWN")

    def test_no_target_instance_segmentation_no_grasp_claim(self):
        # Same EEF distance can represent the robot itself, a table, or a
        # target object. This cannot justify a target-specific assertion.
        robot_self_surface = case()
        target_surface = copy.deepcopy(robot_self_surface)
        self.assertEqual(assess(robot_self_surface), assess(target_surface))
        self.assertEqual(assess(robot_self_surface)["held_grasp"], "UNKNOWN")

    def test_claim_class_must_match_gap_not_just_label(self):
        c = case(closure="CLOSED_TO_FLOOR")
        c["proprio_closure"]["post_gap_m"] = .00696
        ans = assess(c)
        self.assertFalse(ans["eligible"])
        self.assertEqual(ans["reason"], "GAP_AND_REPORTED_CLOSURE_DISAGREE")

    def test_unknown_or_incomplete_fields_fail_closed(self):
        c = case()
        c["visual_camera_motion"] = None
        self.assertFalse(assess(c)["eligible"])
        c = case()
        c["inter_finger_content"] = {"claim": "HELD"}
        self.assertFalse(assess(c)["eligible"])
        c = case()
        c["proprio_closure"]["post_gap_m"] = float("nan")
        self.assertFalse(assess(c)["eligible"])

    def test_summary_has_real_five_case_denominator_and_no_truth(self):
        xs = [case(i, closure="CLOSED_TO_FLOOR" if i < 4
                   else "STALLED_ABOVE_FLOOR") for i in range(1, 6)]
        ans = summarize(xs)
        self.assertEqual(ans["n_cases"], 5)
        self.assertEqual(ans["eligible"], 5)
        self.assertEqual(ans["claim_holding_positive"], 0)
        self.assertEqual(ans["independently_verified_object_contact"], 0)
        self.assertFalse(ans["audit_truth_used"])
        self.assertEqual(ans["counts"]["state"]["NEAR_MIN_GAP_OBJECT_PRESENCE_UNKNOWN"], 3)
        self.assertEqual(ans["counts"]["state"]["GAP_PLATEAU_CAUSE_UNKNOWN"], 2)

    def test_duplicate_or_missing_case_denied(self):
        xs = [case(i) for i in range(1, 6)]
        xs[4]["case"] = xs[3]["case"]
        with self.assertRaisesRegex(ValueError, "Missing/duplicate"):
            summarize(xs)
        with self.assertRaisesRegex(ValueError, "exactly 5"):
            summarize(xs[:4])


if __name__ == "__main__":
    unittest.main()
