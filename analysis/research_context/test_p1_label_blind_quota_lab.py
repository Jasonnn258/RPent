"""P1 L1 synthetic label-blind budget tests, no private data/simulator."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_label_blind_quota_lab import (
    METHODS, hamilton_quota, weights_for, report, evaluate,
)

def rows103():
    rows=[]
    # Exactly 103 failures / 79 episode IDs / 26 terminal positives
    # / 56 any-time positives, with original task partition 21/30/52.
    for task,n in (("3",21),("5",30),("9",52)):
        for j in range(n):
            i=len(rows)
            gate="011" if j % 3 < 2 else "001"
            label=i<26
            r={"episode_id":f"syn_ep_{i%79:03d}", "task":task,
               "legal":{"gate_pattern":gate,
                        "peak_lift_m":.07+(i%7)*.001,
                        "final_gripper_opening":.005+(i%5)*.001},
               "exit_proxy_positive":label,
               "ever_proxy_positive":label or 26<=i<56}
            rows.append(r)
    return rows

class LabelBlindQuotaTests(unittest.TestCase):
    def test_ceil_and_fixed_quota_without_audit_labels(self):
        cap={"3":21,"5":30,"9":52}
        self.assertEqual(hamilton_quota(cap,21,"equal"),
                         {"3":7,"5":7,"9":7})
        self.assertEqual(hamilton_quota(cap,21,"proportional"),
                         {"3":4,"5":6,"9":11})
        self.assertEqual(hamilton_quota(cap,42,"proportional"),
                         {"3":9,"5":12,"9":21})
        self.assertEqual(hamilton_quota({"3":2,"5":30,"9":52},21,"equal"),
                         {"3":2,"5":10,"9":9})

    def test_fixed_total_mass_and_expected_gate_only_behavior(self):
        xs=rows103()
        for method in METHODS:
            w=weights_for(xs,method,.2)
            self.assertEqual(len(w),103)
            self.assertAlmostEqual(sum(w),21)
            self.assertTrue(all(0<=p<=1 for p in w))
            self.assertEqual(weights_for(xs,method,.2),w)
        gate=weights_for(xs,"GATE_ONLY",.2)
        self.assertTrue(all(
            gate[i] == 0. for i,r in enumerate(xs)
            if r["legal"]["gate_pattern"]!="011"))
        self.assertAlmostEqual(sum(gate),21)

    def test_weights_independent_of_proxy_labels(self):
        xs=rows103()
        original={m:weights_for(xs,m,.2) for m in METHODS}
        flipped=copy.deepcopy(xs)
        for r in flipped:
            r["exit_proxy_positive"]=not r["exit_proxy_positive"]
            r["ever_proxy_positive"]=not r["ever_proxy_positive"]
        for m in METHODS:
            self.assertEqual(original[m],weights_for(flipped,m,.2))

    def test_batch_task_metadata_affects_quota_not_score_label(self):
        xs=rows103()
        eq=weights_for(xs,"TASK_EQUAL_GATE",.2)
        pp=weights_for(xs,"TASK_PROP_GATE",.2)
        for w,expected in ((eq,{"3":7,"5":7,"9":7}),
                           (pp,{"3":4,"5":6,"9":11})):
            mix={t:sum(w[i] for i,r in enumerate(xs) if r["task"]==t)
                 for t in ("3","5","9")}
            for task,n in expected.items():
                self.assertAlmostEqual(mix[task],n)
        self.assertEqual(sum(weights_for(xs,"RANDOM",.2)),21)

    def test_synthetic_report_frozen_denominators_and_aggregate_only(self):
        x=evaluate(rows103())
        self.assertEqual(x["n_tool_failures"],103)
        self.assertEqual(x["n_episodes"],79)
        self.assertEqual(set(x["budget_results"]),{"top_20pct","top_40pct"})
        random_result=x["budget_results"]["top_20pct"]["RANDOM"]["terminal"]
        self.assertEqual(random_result["n_reference_positive"],26)
        self.assertAlmostEqual(random_result["precision_at_budget"],26/103,places=5)
        self.assertNotIn("syn_ep",str(x))
        self.assertNotIn("episode_id",str(x))

    def test_invalid_inputs_refuse_and_no_implicit_online_claim(self):
        xs=rows103()
        bad=copy.deepcopy(xs)
        bad[0]["exit_proxy_positive"]=None
        with self.assertRaisesRegex(ValueError,"Invalid audit"):
            report(bad,"GATE_ONLY",.2)
        with self.assertRaisesRegex(ValueError,"Unapproved"):
            report(xs,"GATE_ONLY",.2,"physical_contact")
        with self.assertRaisesRegex(ValueError,"Unrecognized task"):
            weights_for([{"task":"other","legal":{"gate_pattern":"011"}}],
                        "TASK_PROP_GATE",1)
        with self.assertRaisesRegex(ValueError,"denominators"):
            evaluate(xs[:-1])
        with self.assertRaisesRegex(ValueError,"Invalid quota"):
            hamilton_quota({"3":1},2,"equal")

if __name__=="__main__":
    unittest.main()
