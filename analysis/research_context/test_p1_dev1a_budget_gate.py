"""No simulator: D-041 8EP / 3 GPUh / 4 wallh reservation gates."""
from __future__ import annotations
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p1_dev1a_budget_gate import BudgetLedger,static_repo_gate

class BudgetGateTests(unittest.TestCase):
    def test_full_worst_case_not_legacy_900s_reservation(self):
        l=BudgetLedger()
        # 5400s could pass an old +900s check but fails if only
        # 5000s total GPU budget left; do not start.
        l.gpu_consumed_s=6000
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_FULL"):
            l.reserve("test_1","9",5400,1)
        self.assertEqual(l.begun,0)

    def test_single_worker_and_task_cap(self):
        l=BudgetLedger()
        r=l.reserve("x","9",1800,1)
        self.assertEqual(r["max_gpu_s"],1800)
        self.assertEqual(r["hard_env_step_cap"],1500)
        with self.assertRaisesRegex(ValueError,"ONE_WORKER"):
            l.reserve("y","3",1800,1)
        l.charge_and_close("x",800,800,1400)
        l.reserve("z","9",1800,1)
        l.charge_and_close("z",800,800,1400)
        l.reserve("w","9",1800,1)
        l.charge_and_close("w",800,800,1400)
        l.reserve("v","9",1800,1)
        l.charge_and_close("v",800,800,1400)
        with self.assertRaisesRegex(ValueError,"EPISODE_OR_TASK_CAP"):
            l.reserve("fifth","9",1800,1)

    def test_exact_both_wall_and_gpu_budget_bounds(self):
        l=BudgetLedger()
        l.gpu_consumed_s=10000
        l.elapsed_wall_s=13500
        r=l.reserve("x","3",500,1)
        self.assertEqual(r["max_wall_s"],500)
        l.charge_and_close("x",500,500,1500)
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_FULL"):
            l.reserve("y","5",400,1)
        self.assertEqual(l.completed,1)

    def test_gpu_count_always_multiplies_reserved_wall(self):
        l=BudgetLedger()
        r=l.reserve("x","9",2000,2)
        self.assertEqual(r["max_gpu_s"],4000)
        l.charge_and_close("x",1900,3800,1200)
        self.assertEqual(l.gpu_consumed_s,3800)
        with self.assertRaisesRegex(ValueError,"MISSING_WORST"):
            l.reserve("invalid","3",100,0)

    def test_overrun_blocks_and_retains_active_episode_for_forensics(self):
        l=BudgetLedger()
        l.reserve("x","3",1000,1)
        with self.assertRaisesRegex(ValueError,"OVERRUN_STOP"):
            l.charge_and_close("x",1001,1001,1400)
        self.assertEqual(l.begun,1)
        self.assertEqual(l.completed,0)
        self.assertEqual(l.inflight_key,"x")
        with self.assertRaisesRegex(ValueError,"ONE_WORKER"):
            l.reserve("y","5",1000,1)

    def test_missing_observed_spending_cannot_silently_release(self):
        l=BudgetLedger()
        l.reserve("x","5",1000,1)
        with self.assertRaisesRegex(ValueError,"INVALID_OBSERVED"):
            l.charge_and_close("x",None,None,100)
        with self.assertRaisesRegex(ValueError,"INVALID_OBSERVED"):
            l.charge_and_close("x",0,0,1501)
        with self.assertRaisesRegex(ValueError,"NOT_RESERVED"):
            l.charge_and_close("wrong",0,0,100)
        self.assertEqual(l.completed,0)

    def test_static_source_without_contact_api_never_reports_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            paths=(root/"robots/libero/env_client.py",
                   root/"robots/libero/env_server.py")
            for p in paths:
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text("def sim_measurement(): pass\n")
            r=static_repo_gate(root)
            self.assertEqual(r["gate"],"HOLD_ZERO_NEW_EPISODES")
            self.assertFalse(r["G1_contact_rpc_code_present"])
            self.assertFalse(r["G4_isolated_dev1a_runner_present"])
            # Even method names added cannot prove working MuJoCo contact IDs.
            for p in paths:
                p.write_text("def contact_snapshot(): pass\n")
            (root/"scripts").mkdir()
            (root/"scripts/p1_dev1a_run.py").write_text("")
            r=static_repo_gate(root)
            self.assertTrue(r["G1_contact_rpc_code_present"])
            self.assertTrue(r["G4_isolated_dev1a_runner_present"])
            self.assertEqual(r["G1_live_geom_ids_and_bilateral_contact"],"UNVERIFIED")
            self.assertEqual(r["gate"],"HOLD_ZERO_NEW_EPISODES")

if __name__=="__main__":unittest.main()
