"""Synthetic execution tests for P1 L1 offline module ablation.

No simulator, no private file reads, no neural training.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from p1_offline_module_lab import (
    PRESETS, VIEWS, confusion, delta_vs_flag, evaluate, jl, leave_one_task_out_selection,
    load_data, metrics, predict, score, sensitivity_grid, signal,
    failure_slices, flag_false_rescue_tradeoffs,
)

def make_rows():
    # Repeated picks per episode stress grouped resampling; three task groups.
    data = [
        # task, episode, flag, min_gap, final_gap, lift, reference proxy
        (3,"ep03a",True,.002,.002,.08,True),
        (3,"ep03a",False,.0025,.003,.01,False),
        (3,"ep03b",False,.004,.006,.06,True),
        (3,"ep03c",True,.030,.025,.09,True),
        (5,"ep05a",True,.003,.003,.06,True),
        (5,"ep05a",False,.002,.002,.02,False),
        (5,"ep05b",False,.035,.040,.07,True),
        (5,"ep05c",False,.030,.035,.01,False),
        (9,"ep09a",True,.004,.004,.03,False),
        (9,"ep09a",False,.040,.045,.02,False),
        (9,"ep09b",False,.002,.002,.065,True),
        (9,"ep09c",True,.002,.002,.075,True),
    ]
    rows = []
    for i,(task,ep,flag,gmin,gfinal,lift,ref) in enumerate(data):
        rows.append({"episode_id":ep,"step_idx":i+1,"task":str(task),
                     "tool_report":{
                         "name":"pi0_pick","success":flag,
                         "min_gripper_opening":gmin,
                         "final_gripper_opening":gfinal,
                         "peak_lift_m":lift},
                     "reference":ref})
    return rows

def create_views(root, rows):
    root.mkdir(parents=True,exist_ok=True)
    online = []
    audit = []
    meta = []
    for r in rows:
        ids = {"episode_id":r["episode_id"],"step_idx":r["step_idx"]}
        online.append({**ids,"tool_report":r["tool_report"],
                       "visibility":"observed_execution_prefix"})
        audit.append({**ids,"flag":r["tool_report"]["success"],
                      "reference":"POSITIVE" if r["reference"] else "NEGATIVE",
                      "terminal_involved":False,"outcome_contract":
                          "IN_SKILL_ACQ_FGONLY_V1",
                      "visibility":"research_audit_truth"})
        meta.append({**ids,"task_id":int(r["task"])})
    for name,block in zip(VIEWS,(online,audit,meta)):
        (root/name).write_text("".join(json.dumps(x)+"\n" for x in block),
                               encoding="utf-8")

class ModuleLabTests(unittest.TestCase):
    def test_online_only_predict_is_independent_of_reference_label(self):
        row=make_rows()[0]
        original={k:predict(v,row["tool_report"]) for k,v in PRESETS.items()}
        row["reference"]=not row["reference"]
        new={k:predict(v,row["tool_report"]) for k,v in PRESETS.items()}
        self.assertEqual(new,original)
        self.assertTrue(predict(PRESETS["A0_gap060_AND_lift050"],
                                row["tool_report"]))

    def test_module_location_and_logic_change_predictions(self):
        r={"success":False,"min_gripper_opening":.002,
           "final_gripper_opening":.04,"peak_lift_m":.06}
        self.assertFalse(predict(PRESETS["F0_tool_flag"],r))
        self.assertTrue(predict(PRESETS["G1_min_gap_0035"],r))
        self.assertFalse(predict(PRESETS["G2_final_gap_0035"],r))
        self.assertTrue(predict(PRESETS["A1_gap0035_AND_lift050"],r))
        self.assertTrue(predict(PRESETS["R2_flag_OR_gap0035_AND_lift050"],r))
        r["peak_lift_m"]=.01
        self.assertFalse(predict(PRESETS["A1_gap0035_AND_lift050"],r))
        self.assertTrue(predict(PRESETS["O0_gap0035_OR_lift050"],r))
        self.assertFalse(predict(PRESETS["R2_flag_OR_gap0035_AND_lift050"],r))

    def test_missing_and_nonfinite_are_abstain_not_automatic_success(self):
        r={"success":False,"min_gripper_opening":float("nan"),
           "peak_lift_m":None}
        self.assertIsNone(predict(PRESETS["G1_min_gap_0035"],r))
        self.assertIsNone(predict(PRESETS["A1_gap0035_AND_lift050"],r))
        self.assertIsNone(predict(PRESETS["O0_gap0035_OR_lift050"],r))
        m=metrics(confusion([{"tool_report":r,"reference":True}],
                            PRESETS["O0_gap0035_OR_lift050"]))
        self.assertEqual(m["abstain"],1)
        self.assertEqual(m["fn"],1)
        r["peak_lift_m"]=-.1
        self.assertIsNone(predict(PRESETS["L0_peak_lift_050"],r))

    def test_view_join_and_audit_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            rows=make_rows()
            create_views(path,rows)
            got=load_data(path,strict=False)
            self.assertEqual(len(got),12)
            self.assertEqual(len({r["task"] for r in got}),3)
            self.assertEqual(score(got,PRESETS)["F0_tool_flag"]["n"],12)
            online = jl(path/VIEWS[0])
            self.assertNotIn("reference",str(online))
            audit=jl(path/VIEWS[1])
            audit[0]["flag"]=not audit[0]["flag"]
            (path/VIEWS[1]).write_text("".join(json.dumps(x)+"\n" for x in audit))
            with self.assertRaisesRegex(ValueError,"flag mismatch"):
                load_data(path,strict=False)

    def test_grid_leave_one_task_out_and_episode_bootstrap(self):
        rows=make_rows()
        lab=evaluate(rows)
        self.assertEqual(lab["n_primary"],12)
        self.assertEqual(len(lab["threshold_sensitivity_grid"]),48)
        cross=lab["leave_one_task_out_module_selection"]
        self.assertEqual(len(cross["folds"]),3)
        self.assertEqual(sum(x["n_heldout"] for x in cross["folds"]),12)
        self.assertEqual(cross["pooled_test_selected"]["n"],12)
        self.assertEqual(cross["pooled_test_baseline"]["n"],12)
        interval=delta_vs_flag(rows,PRESETS["A1_gap0035_AND_lift050"],
                               repeats=60,seed=1234)
        self.assertGreater(interval["n_valid"],30)
        self.assertEqual(interval,
                         delta_vs_flag(rows,PRESETS["A1_gap0035_AND_lift050"],
                                       repeats=60,seed=1234))

    def test_error_slice_and_rescue_are_real_counts_not_stubbed(self):
        rows=make_rows()
        cuts=failure_slices(rows)
        overall=[r for r in cuts if r["task"]=="ALL"]
        self.assertEqual(sum(r["n"] for r in overall),12)
        self.assertTrue(all(set(r["features"])=={
            "min_gripper_opening","final_gripper_opening","peak_lift_m"}
                            for r in overall))
        rescue=flag_false_rescue_tradeoffs(rows)
        self.assertEqual(rescue["F0_tool_flag"]["proxy_FN_rescued"],0)
        self.assertEqual(rescue["F0_tool_flag"]["new_proxy_false_accepts"],0)
        self.assertGreater(
            rescue["C1_always_true"]["new_proxy_false_accepts"],0)
        self.assertGreater(
            rescue["R1_flag_OR_lift050"]["proxy_FN_rescued"],0)
        self.assertNotIn("ep03",str(cuts))
        self.assertNotIn("ep03",str(rescue))

    def test_unknown_reference_never_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            create_views(p,make_rows())
            audit=jl(p/VIEWS[1])
            audit[0]["reference"]="UNKNOWN"
            (p/VIEWS[1]).write_text("".join(json.dumps(x)+"\n" for x in audit))
            with self.assertRaisesRegex(ValueError,"UNKNOWN"):
                load_data(p,strict=False)

if __name__=="__main__":
    unittest.main()
