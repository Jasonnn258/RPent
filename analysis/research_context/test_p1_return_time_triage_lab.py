"""Synthetic-only P1 legal-return priority tests; never open private data."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_return_time_triage_lab import (
    ARMS, RATIOS, legal_view, priority, summarize, topk_expected,
)

def report(descent=.06,lift=.09,final=.004,min_gap=.003,flag=False):
    return {
        "name":"pick","success":flag,
        "peak_lift_m":lift,
        "min_gripper_opening":min_gap,
        "final_gripper_opening":final,
        "diagnostics":{"descent_m":descent,"start_eef_z":1.2,
                       "post_min_ascent_m":lift},
    }

def row(label,task="9",D_only=True,i=0):
    r=report(
        descent=.06 if D_only else .025,
        lift=.09 if D_only else .02,
        final=.004,
    )
    return {
        "episode_id":f"synthetic_{task}_{i}",
        "task":task,
        "legal":legal_view(r),
        "exit_proxy_positive":label,
    }

def frozen_like():
    # 103 originally failed picks, 26 endpoint proxy+, 77 endpoint proxy-.
    # Task9 includes 19 D-only cases, 11 endpoint+ and 8 endpoint-.
    counts={
        "3":(21,5,0,0),
        "5":(30,10,0,0),
        "9":(52,11,19,11),
    }
    data=[]
    for task,(n,npos,n_d,n_d_pos) in counts.items():
        for i in range(n):
            positive=(i<npos)
            d_only=(i<n_d) if n_d else (i%4==0)
            data.append(row(positive,task,d_only,i))
    return data

class ReturnTimeTriageTests(unittest.TestCase):
    def test_exact_threshold_semantics_and_no_reference_as_feature(self):
        legal=legal_view(report())
        self.assertEqual(legal["gate_pattern"],"011")
        self.assertTrue("exit_proxy_positive" not in legal)
        self.assertEqual(set(legal),{
            "descent_m","peak_lift_m","final_gripper_opening",
            "min_gripper_opening","start_eef_z","gate_pattern"})
        self.assertEqual(priority("D_ONLY_PATTERN",legal),1.)
        self.assertGreater(priority("D_ONLY_THEN_LIFT",legal),1.)
        legal2=legal_view(report(descent=.12,lift=.02,final=.08))
        self.assertEqual(priority("D_ONLY_PATTERN",legal2),0.)

    def test_missing_nonfinite_and_malformed_legal_diagnostics_block(self):
        for invalid in (float("nan"),float("inf"),-1.,None):
            r=report()
            r["peak_lift_m"]=invalid
            with self.assertRaises(ValueError):
                legal_view(r)
        r=report()
        del r["diagnostics"]["start_eef_z"]
        with self.assertRaises(ValueError):
            legal_view(r)

    def test_fractional_ties_use_no_episode_ids(self):
        legal=legal_view(report())
        ten=[{"legal":legal,"exit_proxy_positive":i<4} for i in range(10)]
        ans=topk_expected(ten,"UNTARGETED",.30)
        self.assertEqual(ans["k"],3)
        self.assertEqual(ans["n_proxy_positive"],4)
        self.assertEqual(ans["expected_selected_proxy_positive"],1.2)
        self.assertEqual(ans["expected_selected_proxy_negative"],1.8)
        self.assertEqual(ans["precision_at_budget"],.4)
        self.assertEqual(ans["precision_lift_over_prevalence"],1.)
        self.assertEqual(ans["tie_policy"],"FRACTIONAL_EXPECTATION")

    def test_all_scores_independent_of_audit_labels_and_task(self):
        legal=legal_view(report())
        s={arm:priority(arm,legal) for arm in ARMS}
        one={"legal":legal,"exit_proxy_positive":True,
             "task":"9","episode_id":"danger"}
        other={**one,"exit_proxy_positive":False,"task":"3",
               "episode_id":"other"}
        self.assertEqual({arm:priority(arm,one["legal"]) for arm in ARMS},s)
        self.assertEqual({arm:priority(arm,other["legal"]) for arm in ARMS},s)
        self.assertEqual(len(RATIOS),2)

    def test_frozen_like_population_and_task9_donly_group(self):
        data=frozen_like()
        self.assertEqual(len(data),103)
        self.assertEqual(sum(r["exit_proxy_positive"] for r in data),26)
        result=summarize(data)
        self.assertEqual(result["n_failures"],103)
        self.assertEqual(result["task_n"],{"3":21,"5":30,"9":52})
        self.assertEqual(result["task9_D_only_subgroup"]["n"],19)
        self.assertEqual(result["task9_D_only_subgroup"]["terminal_pos"],11)
        for arm in ARMS:
            rec=result["global"][arm]["budget_20pct"]
            self.assertEqual(rec["k"],21)
            self.assertAlmostEqual(
                rec["expected_selected_proxy_positive"]+
                rec["expected_selected_proxy_negative"],21,places=5)
        self.assertNotIn("episode_id",str(result))
        self.assertNotIn("synthetic_9",str(result))

    def test_broken_denominator_and_invalid_scores_fail(self):
        data=frozen_like()
        with self.assertRaisesRegex(ValueError,"Frozen tool-failure"):
            summarize(data[:20])
        for ratio in (0.,1.1):
            with self.assertRaises(ValueError):
                topk_expected(data,"D_ONLY_PATTERN",ratio)
        with self.assertRaisesRegex(ValueError,"Unknown triage"):
            priority("fake",data[0]["legal"])

if __name__=="__main__":
    unittest.main()
