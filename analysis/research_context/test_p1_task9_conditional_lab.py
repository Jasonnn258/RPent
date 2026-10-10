"""Synthetic Task9 D-only conditional ranking tests; no private traces."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_return_time_triage_lab import legal_view
from p1_task9_conditional_lab import (
    task9_donly,score_k,permutation_test,leave_episode_out,evaluate
)

def fixture():
    rows=[]
    for i in range(19):
        r={
          "name":"pick","success":False,"peak_lift_m":.05+i*.001,
          "min_gripper_opening":.003,"final_gripper_opening":.006,
          "diagnostics":{"descent_m":.07,"start_eef_z":1.2}
        }
        rows.append({"task":"9","episode_id":f"syn_ep_{i//2}",
                    "legal":legal_view(r),"exit_proxy_positive":i>=8})
    return rows

class Tests(unittest.TestCase):
    def test_denominator_and_exact_subgroup(self):
        rows=fixture()
        sub=task9_donly(rows)
        self.assertEqual(len(sub),19)
        self.assertEqual(sum(r["exit_proxy_positive"] for r in sub),11)
        rows[0]["task"]="3"
        with self.assertRaisesRegex(ValueError,"19/11"):
            task9_donly(rows)

    def test_ranking_vs_untargeted(self):
        rows=fixture()
        self.assertEqual(score_k(rows,"UNTARGETED",4),round(4*11/19,6))
        self.assertEqual(score_k(rows,"PEAK_LIFT",4),4.)
        self.assertEqual(score_k(rows,"LIFT_MINUS_GAP",4),4.)

    def test_permutation_reproducible_and_truth_not_in_score(self):
        rows=fixture()
        a=permutation_test(rows,"PEAK_LIFT",4,repeats=1000,seed=123)
        b=permutation_test(rows,"PEAK_LIFT",4,repeats=1000,seed=123)
        self.assertEqual(a,b)
        self.assertEqual(a["observed_proxy_positives"],4.)
        self.assertLess(a["one_sided_permutation_p_exploratory"],.15)
        self.assertEqual(a["n_permutations"],1000)

    def test_leave_episode_out_counts_and_boundaries(self):
        z=leave_episode_out(fixture(),"PEAK_LIFT",4)
        self.assertEqual(z["n_episodes"],10)
        self.assertEqual(z["n_leave_one_out"],10)
        self.assertLessEqual(z["precision_min"],z["precision_full"])
        self.assertGreaterEqual(z["precision_max"],z["precision_full"])

    def test_full_aggregate_no_case_leak(self):
        res=evaluate(fixture())
        self.assertEqual(res["n"],19)
        self.assertEqual(res["positive"],11)
        self.assertEqual(res["negative"],8)
        self.assertEqual(set(res["budgets"]),{"4","8"})
        self.assertNotIn("syn_ep",str(res))
        self.assertNotIn("episode_id",str(res))
        self.assertEqual(res["budgets"]["4"]["UNTARGETED"]["topk"]["k"],4)

if __name__=="__main__":unittest.main()
