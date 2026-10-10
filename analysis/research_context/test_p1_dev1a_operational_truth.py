"""No sim or private data: G1/G2 contact/retention and leakage adversarial tests."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_dev1a_operational_truth import (
    contact_state,retention_state,prohibit_audit_leak,validate_snapshot
)

def snap(step=100,target_z=.1,eef_z=.25,pairs=None):
    return {
        "env_step":step,"contact_env_step":step,"pose_env_step":step,
        "image_env_step":step,"target_instance":"synthetic_target",
        "target_geom_ids":[100,101],"left_finger_geom_ids":[201],
        "right_finger_geom_ids":[202],"support_geom_ids":[301],
        "contacts":[[201,100],[202,101]] if pairs is None else pairs,
        "target_pos":[0,0,target_z],"eef_pos":[0,0,eef_z],
    }

def lift_states():
    return [
        snap(101,.107,.257),
        snap(102,.113,.263),
        snap(103,.118,.268),
    ]

class ContractTests(unittest.TestCase):
    def test_bilateral_and_support_are_separate_concepts(self):
        c=contact_state(snap())
        self.assertEqual(c["contact"],"BILATERAL")
        self.assertFalse(c["supported"])
        c=contact_state(snap(pairs=[[201,100],[202,101],[100,301]]))
        self.assertEqual(c["contact"],"BILATERAL")
        self.assertTrue(c["supported"])
        self.assertEqual(retention_state(snap(),[
            snap(101,.107,.257,pairs=[[201,100],[202,101],[100,301]]),
            snap(102,.113,.263,pairs=[[201,100],[202,101],[100,301]]),
            snap(103,.118,.268,pairs=[[201,100],[202,101],[100,301]])
        ])["retained"],"NOT_RETAINED")

    def test_empty_gripper_and_robot_self_contact_are_not_target(self):
        p=snap(pairs=[[201,202]])
        self.assertEqual(contact_state(p)["contact"],"NONE")
        self.assertEqual(retention_state(p,[
            snap(101,.100,.257,pairs=[[201,202]]),
            snap(102,.100,.263,pairs=[[201,202]]),
            snap(103,.100,.268,pairs=[[201,202]])
        ])["retained"],"NOT_RETAINED")

    def test_stable_lift_operational_retained_within_2cm(self):
        p=retention_state(snap(),lift_states())
        self.assertEqual(p["retained"],"RETAINED")
        self.assertEqual(p["reason"],"SIM_OPERATIONAL_CONTACT_AND_MOTION")

    def test_lift_drop_and_missing_contact_unknown(self):
        drops=lift_states()
        drops[-1]["contacts"]=[]
        self.assertEqual(retention_state(snap(),drops)["retained"],"UNKNOWN")
        bad=lift_states()
        del bad[1]["contacts"]
        self.assertEqual(retention_state(snap(),bad)["retained"],"UNKNOWN")

    def test_strict_same_tick_and_target_identity(self):
        x=snap()
        x["image_env_step"]=101
        self.assertEqual(contact_state(x)["contact"],"UNKNOWN")
        self.assertFalse(validate_snapshot(x))
        states=lift_states()
        states[-1]["target_instance"]="other"
        self.assertEqual(retention_state(snap(),states)["reason"],"TARGET_ID_SWITCH")

    def test_missing_unresolved_geom_and_invalid_contact_list_unknown(self):
        x=snap()
        x["target_geom_ids"]=[]
        self.assertEqual(contact_state(x)["contact"],"UNKNOWN")
        x=snap()
        x["contacts"]=None
        self.assertEqual(contact_state(x)["contact"],"UNKNOWN")
        x=snap()
        x["target_geom_ids"]=[201]
        self.assertFalse(validate_snapshot(x))

    def test_audit_truth_never_allowed_in_legal_envelope(self):
        sha="b"*64
        valid={"env_step":100,"rgb_sha256":sha,"wrist_sha256":sha,
               "eef_pos":[0.,0.,.2],"source":"same_tick","fresh":True,
               "validity":"VALID"}
        self.assertTrue(prohibit_audit_leak(valid))
        for key in ("contacts","target_instance","target_pos","sim_measurement",
                    "audit_only","held_grasp","target_geom_ids","unknown_field"):
            x=copy.deepcopy(valid)
            x[key]=True
            with self.assertRaisesRegex(ValueError,"UNAPPROVED"):
                prohibit_audit_leak(x)
        x=copy.deepcopy(valid)
        x["fresh"]=False
        with self.assertRaisesRegex(ValueError,"INVALID_OR_STALE"):
            prohibit_audit_leak(x)

if __name__=="__main__":unittest.main()
