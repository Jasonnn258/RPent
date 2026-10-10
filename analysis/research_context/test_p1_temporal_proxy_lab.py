"""Pure synthetic L1 temporal proxy tests. No GPU/episode files/simulator."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_temporal_proxy_lab import temporal_trace, aggregate

def point(objz,eefx=0.0,objx=0.0,valid=True):
    if not valid:
        return {"obs":{}}
    return {"obs":{
        "target_pos":[objx,0.0,objz],
        "robot0_eef_pos":[eefx,0.0,0.0],
    },"obj_of_interest":["target"]}

def trace(zs, status=None):
    ps=[point(z) for z in zs]
    sts=status or ["VALID"]*len(ps)
    return temporal_trace(ps,sts)

class TemporalProxyTests(unittest.TestCase):
    def test_transient_any_positive_but_terminal_negative(self):
        result=trace([0.0,.04,.05,.01,0.0])
        self.assertTrue(result["frozen_any_positive"])
        self.assertEqual(result["class"],"EVER_POS_TERMINAL_NEG")
        self.assertEqual(result["terminal"],"NEGATIVE")
        self.assertEqual(result["trailing_positive_nonbase"],0)
        self.assertFalse(result["last_3_all_positive"])
        self.assertEqual(result["first_positive_frac"],.25)
        self.assertEqual(result["last_positive_frac"],.5)

    def test_sustained_last_three_samples(self):
        result=trace([0.0,0.0,.04,.05,.06])
        self.assertEqual(result["class"],"EVER_POS_TERMINAL_POS")
        self.assertEqual(result["trailing_positive_nonbase"],3)
        self.assertTrue(result["last_3_all_positive"])
        self.assertEqual(result["n_positive"],3)

    def test_ever_negative_complete_vs_incomplete(self):
        self.assertEqual(trace([0,0.0,.02])["class"],"EVER_NEGATIVE_COMPLETE")
        r=temporal_trace(
            [point(0),point(.0),point(.04,valid=False)],
            ["VALID","VALID","INVALID_MISSING"])
        self.assertEqual(r["class"],"EVER_NEGATIVE_INCOMPLETE")
        self.assertEqual(r["terminal"],"UNKNOWN")

    def test_terminal_unknown_is_not_last_available_valid(self):
        r=temporal_trace(
            [point(0),point(.04),point(.05,valid=False)],
            ["VALID","VALID","INVALID_MISSING"])
        self.assertEqual(r["class"],"EVER_POS_TERMINAL_UNKNOWN")
        self.assertTrue(r["frozen_any_positive"])
        self.assertEqual(r["terminal"],"UNKNOWN")
        self.assertEqual(r["trailing_positive_nonbase"],0)
        self.assertFalse(r["last_3_all_positive"])

    def test_invalid_target_and_misaligned_sequence_rejected(self):
        with self.assertRaisesRegex(ValueError,"No valid target"):
            temporal_trace([{"obs":{}}],["VALID"])
        with self.assertRaisesRegex(ValueError,"Missing or misaligned"):
            temporal_trace([point(0),point(.04)],["VALID"])

    def test_aggregate_frozen_denominators_and_gate_intersection(self):
        # 101 TP + 2 FP + 56 FN + 47 TN. Return/held labels NOT generated.
        groups=((True,True,101),(True,False,2),
                (False,True,56),(False,False,47))
        rows=[]
        for flag,any_proxy,n in groups:
            for i in range(n):
                j=len(rows)
                # First FN 19 are D-missing, of which first ten are transient.
                pattern="011" if not flag and any_proxy and i<19 else "111" if flag else "001"
                if any_proxy:
                    z=[0,.04,.01] if not flag and i<10 else [0,.04,.05]
                else:
                    z=[0,.01,.02]
                rows.append({
                    "episode_id":f"e{j%175:03d}",
                    "task":"9" if j%3==0 else "3" if j%3==1 else "5",
                    "flag":flag,
                    "gate_pattern":pattern,
                    "proxy":trace(z),
                })
        a=aggregate(rows)
        self.assertEqual(a["n_primary"],206)
        self.assertEqual(a["n_episodes"],175)
        self.assertEqual(a["frozen_any_reference"],{"NEGATIVE":49,"POSITIVE":157})
        self.assertEqual(a["proxy_false_negative_temporal"]["n"],56)
        self.assertEqual(a["proxy_false_negative_temporal"][
            "n_any_proxy_positive_but_terminal_negative"],10)
        self.assertEqual(sum(z["n"] for z in a["by_tool_proxy_group"]),206)
        self.assertFalse(any("e001" in str(x) for x in a["by_tool_proxy_group"]))
        self.assertEqual(sum(a["by_task"][t]["n"] for t in a["by_task"]),206)
        # Prevent per-record audit-only poses, file paths and sample IDs.
        self.assertNotIn("target_pos",str(a))
        self.assertNotIn("episode_id",str(a))

    def test_aggregate_frozen_label_change_stops(self):
        rs=[{
            "episode_id":f"e{i%175:03d}","task":"9",
            "flag":False,"gate_pattern":"011","proxy":trace([0,.04,.05])
        } for i in range(206)]
        with self.assertRaisesRegex(ValueError,"reference counts changed"):
            aggregate(rs)

if __name__=="__main__":
    unittest.main()
