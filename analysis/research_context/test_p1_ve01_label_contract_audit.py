"""No sim/model: exact source-time separation for frozen DEV0 event contract."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"analysis/research_context"))
from p1_dev0_manifest import manifest
from p1_ve01_label_contract_audit import audit

def emit(root, row, contents):
    dst=root/"runs"/row["episode_key"]/"p1_dev0_events.jsonl"
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text("".join(json.dumps(r)+"\n" for r in contents),encoding="utf-8")

def create_frozen_scenario(root):
    rows=manifest()
    byarm=[next(r for r in rows if r["arm"]==arm) for arm in ("D0","D1","D2","D3")]
    extra=next(r for r in rows if r["arm"]=="D1" and r!=byarm[1])
    extra2=next(r for r in rows if r["arm"]=="D3" and r!=byarm[3])
    triggered=byarm+[extra,extra2]
    assert len({r["episode_key"] for r in triggered})==6
    for i,row in enumerate(triggered):
        probed=row["arm"]!="D0"
        ev=[{"ev":"init"},{"ev":"trigger","env_steps":100}]
        if probed:
            ev.append({"ev":"probe","env_steps_start":100,
                       "env_steps_end":110})
        if i <4:
            ev.append({"ev":"audit","kind":"FIXED_HORIZON",
                       "env_steps_at_audit":310,"overshoot_env_steps":10,
                       "audit_only":{"check_success":i%2==0,
                         "sim_measurement_obs":{"object_pos":[0.1,0.2,0.3]}}})
        else:
            ev.append({"ev":"audit","kind":"EPISODE_END",
                       "env_steps_at_audit":175,"overshoot_env_steps":-125,
                       "audit_only":{"check_success":False}})
        ev.append({"ev":"episode_end"})
        emit(root,row,ev)
    for row in rows:
        if row in triggered:continue
        # 15 observed untriggered, three absent
        if sum(1 for x in rows if x not in triggered and x["episode_key"]<
               row["episode_key"])<15:
            emit(root,row,[{"ev":"init"},{"ev":"episode_end"}])
    return rows,triggered

class AuditTests(unittest.TestCase):
    def test_future_truth_never_becomes_probe_time_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rows,_=create_frozen_scenario(root)
            result=audit(rows,root)
            c=result["counts"]
            self.assertEqual(c["allocated"],24)
            self.assertEqual(c["triggered"],6)
            self.assertEqual(c["probed"],5)
            self.assertEqual(c["later_task_success_observed"],6)
            self.assertEqual(c["with_probe_time_contact_reference"],0)
            self.assertEqual(c["with_probe_time_held_reference"],0)
            self.assertEqual(c["followup_audit_strictly_after_probe"],5)
            self.assertEqual(result["audit_window_kinds"]["FIXED_HORIZON"],4)
            self.assertEqual(result["audit_window_kinds"]["EPISODE_END"],2)
            self.assertEqual(result["gate"],
                             "NO_PROBE_TIME_PHYSICAL_LABELS_IN_EVENT_CONTRACT")
            self.assertFalse(result["integrity_violations"])
            self.assertNotIn("object_pos",str(result))
            self.assertTrue(all(
                r["probe_time_held"]=="UNLABELLED"
                for r in result["records"]))

    def test_audit_before_probe_detects_invalid_time_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rows,triggered=create_frozen_scenario(root)
            target=next(r for r in triggered if r["arm"]!="D0")
            fp=root/"runs"/target["episode_key"]/"p1_dev0_events.jsonl"
            es=[json.loads(x) for x in fp.read_text().splitlines()]
            for e in es:
                if e["ev"]=="audit":
                    e["env_steps_at_audit"]=105
            fp.write_text("".join(json.dumps(x)+"\n" for x in es))
            result=audit(rows,root)
            self.assertIn(f"{target['episode_key']}:audit_not_after_probe",
                          result["integrity_violations"])
            self.assertEqual(result["gate"],
                             "HOLD_EVENT_INTEGRITY_OR_PROBE_MISSING")

    def test_manifest_duplicates_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            xs=manifest()
            xs[-1]["episode_key"]=xs[0]["episode_key"]
            with self.assertRaisesRegex(ValueError,"24-cell"):
                audit(xs,Path(tmp))

if __name__=="__main__":
    unittest.main()
