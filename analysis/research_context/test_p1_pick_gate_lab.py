"""Synthetic-only gate ablation test; no simulator or private data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_pick_gate_lab import gates, predict, score, scan, ARMS

def row(i, task="9", flag=False, reference=True, descent=.12,
        lift=.055, final=.02, minimum=.019):
    return {
        "episode_id": "synthetic_ep_" + str(i), "step_idx": i, "task": task,
        "reference": reference,
        "tool_report": {
            "name":"pick","success":flag,
            "peak_lift_m":lift,
            "min_gripper_opening": minimum,
            "final_gripper_opening": final,
            "diagnostics":{"descent_m":descent}
        }
    }

class GateLabTests(unittest.TestCase):
    def test_original_three_gates_and_missing_descent_ablation(self):
        r=row(1,flag=False,reference=False,descent=.08)
        self.assertFalse(predict("D_AND_L_AND_Gfinal",r["tool_report"]))
        self.assertTrue(predict("L_AND_Gfinal",r["tool_report"]))
        self.assertFalse(predict("D_AND_L",r["tool_report"]))
        self.assertEqual(gates(r["tool_report"]),{
            "D":False,"L":True,"G_final":True,"G_min":True
        })

    def test_min_vs_final_location_is_not_equivalent(self):
        r=row(1,flag=False,descent=.12,lift=.055,minimum=.035,final=.075)
        self.assertTrue(predict("D_AND_L_AND_Gmin",r["tool_report"]))
        self.assertFalse(predict("D_AND_L_AND_Gfinal",r["tool_report"]))

    def test_nonfinite_or_missing_is_explicitly_abstained(self):
        r=row(1,flag=False)
        del r["tool_report"]["diagnostics"]["descent_m"]
        self.assertIsNone(gates(r["tool_report"]))
        self.assertIsNone(predict("D_only",r["tool_report"]))
        r["tool_report"]["diagnostics"]["descent_m"]=float("nan")
        self.assertIsNone(gates(r["tool_report"]))
        m=score([r],"D_only")
        self.assertEqual(m["abstain"],1)
        self.assertEqual(m["fn"],1)

    def test_tool_flag_vs_end_of_skill_heuristic_reported_as_mismatch(self):
        xs=[row(i+1, task=("3","5","9")[i%3],flag=False,reference=True,
                descent=.12,lift=.06,final=.002,minimum=.002)
            for i in range(206)]
        s=scan(xs)
        self.assertEqual(s["n_primary"],206)
        self.assertEqual(s["n_gate_fields_eligible"],206)
        self.assertEqual(s["gate_integrity"]["terminal_gate_and_tool_flag_disagree"],206)
        self.assertEqual(s["overall"]["F0_tool_flag"]["fn"],206)
        self.assertEqual(s["overall"]["D_AND_L_AND_Gfinal"]["tp"],206)
        self.assertEqual(sum(x["n"] for x in s["pattern_distributions"]),206)
        self.assertEqual(
            sum(v["proxy_positive_among_failures"] for v in s["flag_false_by_task"].values()),
            206)

    def test_matching_full_gate_original_baseline(self):
        xs=[row(i+1,task=("3","5","9")[i%3],flag=(i%2==0),
                reference=(i%3==0),descent=(.12 if i%2==0 else .08))
            for i in range(206)]
        s=scan(xs)
        self.assertNotIn("terminal_gate_and_tool_flag_disagree",s["gate_integrity"])
        self.assertEqual(s["overall"]["D_AND_L_AND_Gfinal"],
                         s["overall"]["F0_tool_flag"])
        self.assertEqual(len(s["per_task"]),3)

    def test_sample_count_guard_and_no_privileged_audit_fields(self):
        rows=[row(1)]
        with self.assertRaisesRegex(ValueError,"EXACT"):
            scan(rows)
        self.assertNotIn("reference",gates(rows[0]["tool_report"]))
        self.assertTrue(all(x in ARMS for x in ("D_only","L_only",
                                              "Gfinal_only","D_AND_L_AND_Gfinal")))

if __name__=="__main__":
    unittest.main()
