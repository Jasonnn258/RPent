"""Synthetic verification of P1 triage incremental information accounting."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_triage_incremental_lab import (
    decompose, group_key, grouped_bootstrap, select_weights, summarize,
)
from p1_return_time_triage_lab import priority, topk_expected

def fake(task="3", gate="011", score=2., positive=False, ep="ep"):
    return {
        "task":task,"episode_id":ep,
        "legal":{"gate_pattern":gate,"peak_lift_m":score*.05,
                 "final_gripper_opening":0.,"min_gripper_opening":0.,
                 "descent_m":.06,"start_eef_z":1.},
        "exit_proxy_positive":bool(positive),
        "ever_proxy_positive":bool(positive),
    }

def frozen_like():
    rows=[]
    for task,n,npos in (("3",21,5),("5",30,9),("9",52,12)):
        for i in range(n):
            gate="011" if task=="9" and i<19 else "001"
            # Task9 011 has 11 exit-positive among 19, plus one
            # exit-positive in a non-011 case (12/52 task-wide).
            positive=(i<11 or i==19) if task=="9" else i<npos
            r=fake(task,gate,score=(.9-i*.01),positive=positive)
            r["episode_id"]=f"e{len(rows)%79:03d}"
            rows.append(r)
    # Thirty mid-skill-only FGONLY positives, preserving 26 exit positives.
    added=0
    for r in rows:
        if not r["exit_proxy_positive"] and added<30:
            r["ever_proxy_positive"]=True
            added+=1
    assert len(rows)==103 and len({r["episode_id"] for r in rows})==79
    assert sum(r["exit_proxy_positive"] for r in rows)==26
    assert sum(r["ever_proxy_positive"] for r in rows)==56
    assert len([r for r in rows if r["task"]=="9" and r["legal"]["gate_pattern"]=="011"])==19
    assert sum(r["exit_proxy_positive"] for r in rows if r["task"]=="9" and r["legal"]["gate_pattern"]=="011")==11
    return rows

class TestIncrementalTriage(unittest.TestCase):
    def test_selection_tie_expectation_exactly_matches_frozen_topk(self):
        rows=[fake(score=2.,positive=i<4,ep=f"e{i}") for i in range(10)]
        w=select_weights(rows,"LIFT_MINUS_GAP",.30)
        self.assertEqual(len(w),10)
        self.assertAlmostEqual(sum(w),3)
        self.assertTrue(all(x==.3 for x in w))
        d=decompose(rows,ratio=.3)
        self.assertEqual(d["expected_selected_positive"],1.2)
        self.assertEqual(d["matched_controls"]["global"]["delta_precision"],0.)
        self.assertEqual(d["matched_controls"]["task_gate"]["delta_precision"],0.)
        self.assertEqual(
            d["expected_selected_positive"],
            topk_expected(rows,"LIFT_MINUS_GAP",.3)["expected_selected_proxy_positive"])

    def test_only_task_prevalence_selection_not_within_task_improvement(self):
        rows=[fake("3","011",score=1.+i*.01,positive=True,ep=f"a{i}") for i in range(4)]
        rows+=[fake("9","011",score=.1+i*.01,positive=False,ep=f"b{i}") for i in range(4)]
        d=decompose(rows,ratio=.5)
        self.assertEqual(d["precision"],1.)
        self.assertEqual(d["matched_controls"]["global"]["expected_precision"],.5)
        self.assertEqual(d["matched_controls"]["task"]["delta_precision"],0.)
        self.assertEqual(d["matched_controls"]["task_gate"]["delta_precision"],0.)
        self.assertEqual(d["matched_controls"]["gate"]["delta_precision"],.5)

    def test_within_same_task_gate_genuine_signal_survives_matching(self):
        rows=[fake(score=1.+i*.1,positive=i==3,ep=f"e{i}") for i in range(4)]
        d=decompose(rows,ratio=.25)
        self.assertEqual(d["expected_selected_positive"],1.)
        self.assertEqual(d["matched_controls"]["task_gate"]["expected_precision"],.25)
        self.assertEqual(d["matched_controls"]["task_gate"]["delta_precision"],.75)

    def test_changing_labels_never_changes_selection_weights(self):
        rows=frozen_like()
        weights=select_weights(rows,"LIFT_MINUS_GAP",.2)
        altered=copy.deepcopy(rows)
        for row in altered:
            row["exit_proxy_positive"]=not row["exit_proxy_positive"]
            row["ever_proxy_positive"]=not row["ever_proxy_positive"]
            row["task"]="9" if row["task"]=="3" else row["task"]
        self.assertEqual(weights,select_weights(altered,"LIFT_MINUS_GAP",.2))
        self.assertTrue(all("episode_id" not in key for key in (
            "task","gate","task_gate","global")))
        with self.assertRaisesRegex(ValueError,"Unapproved"):
            decompose(rows,reference="audit_only_grasp")

    def test_summarize_all_primary_and_task9_conservation(self):
        rows=frozen_like()
        result=summarize(rows,boot_repeats=18)
        self.assertEqual(result["n_failures"],103)
        self.assertEqual(result["n_episodes"],79)
        self.assertEqual(result["n_terminal_proxy_pos"],26)
        self.assertEqual(result["task9_D_only_LMG"]["n"],19)
        self.assertEqual(result["task9_D_only_LMG"]["n_proxy_positive"],11)
        self.assertEqual(result["episode_cluster_bootstrap_LMG_terminal_top20_task_gate_increment"]["n_valid"],18)
        self.assertEqual(set(result["fixed_arm_ablations"]),{
            "LIFT_MINUS_GAP","D_ONLY_PATTERN","PEAK_LIFT"})
        self.assertNotIn("episode_id",str(result))
        self.assertNotIn("start_eef_z",str(result))
        self.assertNotIn("target_pos",str(result))

    def test_grouped_bootstrap_reproducible(self):
        rows=frozen_like()
        a=grouped_bootstrap(rows,n_boot=15,seed=123)
        b=grouped_bootstrap(rows,n_boot=15,seed=123)
        self.assertEqual(a,b)
        self.assertEqual(a["n_source_episodes"],79)

    def test_frozen_denominator_and_missing_reference_fail_closed(self):
        rows=frozen_like()
        with self.assertRaisesRegex(ValueError,"103 rows"):
            summarize(rows[:-1],boot_repeats=2)
        altered=copy.deepcopy(rows)
        altered[0]["ever_proxy_positive"]=False
        with self.assertRaisesRegex(ValueError,"counts mismatch"):
            summarize(altered,boot_repeats=2)
        with self.assertRaisesRegex(ValueError,"Unvalidated"):
            decompose([{"task":"3","legal":{"gate_pattern":"011",
                "peak_lift_m":.08,"final_gripper_opening":.01}}],
                reference="exit_proxy_positive")
        with self.assertRaisesRegex(ValueError,"Unapproved"):
            group_key(rows[0],"UNKNOWN")

if __name__=="__main__":
    unittest.main()
