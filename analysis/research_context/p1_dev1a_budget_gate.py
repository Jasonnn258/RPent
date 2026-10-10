#!/usr/bin/env python3
"""DEV1A G4 fail-closed single-worker prelaunch budget reservation.

This is offline mock-testable infrastructure, not a runnable simulator runner.
It enforces the strict D-041 ceiling of 8 new EP, 3 GPU-h, 4 wall-h,
1500 env steps/EP, 1 worker. Episode reservations use WHOLE worst-case
duration (not the legacy DEV0 900s placeholder against a 5400s timeout).
A simulator adapter still must implement process-group kill, timeouts,
accounting, persisted atomic ledger, safety stops and resource provenance.

No commit of this file certifies live G4 PASS.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from math import isfinite

MAX_EP=8
MAX_GPU_S=3*3600
MAX_WALL_S=4*3600
MAX_ENV_STEPS=1500
MAX_WORKERS=1
TASK_CAP={"9":4,"3":2,"5":2}

def positive(value):
    return type(value) in (int,float) and isfinite(value) and value>0

@dataclass
class BudgetLedger:
    """In-memory one-process component; not durable enough for real sim yet."""
    elapsed_wall_s:float=0.
    gpu_consumed_s:float=0.
    begun:int=0
    completed:int=0
    reserved_gpu_s:float=0.
    reserved_wall_s:float=0.
    inflight_key:str|None=None
    inflight_task:str|None=None
    spent_steps:int=0
    task_started:dict=field(default_factory=dict)

    def _validate_common(self):
        if (not 0<=self.completed<=self.begun<=MAX_EP or
                not 0<=self.gpu_consumed_s<=MAX_GPU_S or
                not 0<=self.elapsed_wall_s<=MAX_WALL_S):
            raise ValueError("INVALID_BUDGET_LEDGER")
        if (self.inflight_key is None)!=(self.inflight_task is None):
            raise ValueError("INCONSISTENT_INFLIGHT")
        if self.inflight_key is None and (self.reserved_gpu_s!=0 or
                                          self.reserved_wall_s!=0):
            raise ValueError("STALE_RESERVATION")
        if sum(self.task_started.values()) != self.begun:
            raise ValueError("TASK_EPISODE_COUNT_MISMATCH")
        for task,count in self.task_started.items():
            if task not in TASK_CAP or type(count) is not int or count<0 or count>TASK_CAP[task]:
                raise ValueError("TASK_ALLOCATION_EXCEEDED")

    def reserve(self,key,task,worst_wall_s,gpu_count):
        """Call immediately BEFORE episode; no actual process can start first.

        Worst-case wall includes launch/shutdown/timeout grace. gpu_count
        must be proven by runtime resource inventory (NOT guessed here).
        """
        self._validate_common()
        if self.inflight_key is not None:
            raise ValueError("ONE_WORKER_ONLY")
        if not isinstance(key,str) or not key or task not in TASK_CAP:
            raise ValueError("INVALID_EPISODE_IDENTIFICATION")
        if not positive(worst_wall_s) or type(gpu_count) is not int or gpu_count<1:
            raise ValueError("MISSING_WORST_CASE_OR_GPU_COUNT")
        if (self.begun>=MAX_EP or
                self.task_started.get(task,0)>=TASK_CAP[task]):
            raise ValueError("EPISODE_OR_TASK_CAP")
        worst_gpu_s=worst_wall_s*gpu_count
        # Both clocks must reserve a full maximum remaining episode cost.
        if (self.elapsed_wall_s+worst_wall_s>MAX_WALL_S or
                self.gpu_consumed_s+worst_gpu_s>MAX_GPU_S):
            raise ValueError("INSUFFICIENT_FULL_EPISODE_RESERVATION")
        self.inflight_key=key
        self.inflight_task=task
        self.reserved_gpu_s=worst_gpu_s
        self.reserved_wall_s=worst_wall_s
        self.begun+=1
        self.task_started[task]=self.task_started.get(task,0)+1
        return {"episode_key":key,"task":task,"max_gpu_s":worst_gpu_s,
                "max_wall_s":worst_wall_s,
                "hard_env_step_cap":MAX_ENV_STEPS}

    def charge_and_close(self,key,observed_wall_s,observed_gpu_s,steps):
        """Counts partial/interrupted runs toward irreversible EP cap.

        Caller MUST obtain observed costs from a trusted resource monitor;
        an interrupted unmeasurable run is a STOP condition, not a retry.
        """
        self._validate_common()
        if self.inflight_key!=key:
            raise ValueError("NOT_RESERVED_OR_WRONG_EPISODE")
        if (type(steps) is not int or not 0<=steps<=MAX_ENV_STEPS or
            type(observed_wall_s) not in (int,float) or not isfinite(observed_wall_s) or
            type(observed_gpu_s) not in (int,float) or not isfinite(observed_gpu_s) or
            observed_wall_s<0 or observed_gpu_s<0):
            raise ValueError("INVALID_OBSERVED_COST")
        if (observed_wall_s>self.reserved_wall_s or
                observed_gpu_s>self.reserved_gpu_s):
            raise ValueError("OVERRUN_STOP_KEEP_RESERVATION_FOR_FORENSICS")
        self.elapsed_wall_s+=observed_wall_s
        self.gpu_consumed_s+=observed_gpu_s
        self.spent_steps+=steps
        self.completed+=1
        self.inflight_key=None
        self.inflight_task=None
        self.reserved_gpu_s=0.
        self.reserved_wall_s=0.
        self._validate_common()
        return {"gpu_s":self.gpu_consumed_s, "wall_s":self.elapsed_wall_s,
                "completed":self.completed, "begun":self.begun}

    def forbid_resume(self,key):
        """No resumed historical episode unless a new independent manifest."""
        raise ValueError("NO_DEV1A_EPISODE_RERUN_OR_RESTART_AUTHORIZED")


def static_repo_gate(root):
    """Analyze only code surfaces; always demand separate live G1-G4 proof.

    IMPORTANT: a code symbol cannot certify MuJoCo source geom identity,
    contact non-stepping behavior or hardware spending.
    """
    from pathlib import Path
    import ast
    root=Path(root)
    def has_method(filename,name):
        if not filename.is_file():
            return False
        tree=ast.parse(filename.read_text(encoding="utf-8"))
        return any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and
                   n.name==name for n in ast.walk(tree))
    client=root/"robots/libero/env_client.py"
    server=root/"robots/libero/env_server.py"
    has_client=has_method(client,"contact_snapshot")
    has_server=has_method(server,"contact_snapshot")
    has_runner=(root/"scripts/p1_dev1a_run.py").is_file()
    return {
        "protocol":"DEV1A_G1_G4_STATIC_OBSERVABILITY",
        "G1_contact_rpc_code_present":has_client and has_server,
        "G4_isolated_dev1a_runner_present":has_runner,
        "G1_live_geom_ids_and_bilateral_contact":"UNVERIFIED",
        "G2_live_same_env_tick":"UNVERIFIED",
        "G3_live_audit_firewall":"UNVERIFIED",
        "G4_live_gpu_wall_reservation_and_process_kill":"UNVERIFIED",
        "gate":"HOLD_ZERO_NEW_EPISODES",
        "rationale":"Static source and synthetic tests never authorize real simulator episodes; D-041 runtime G1-G4 evidence missing.",
    }

def main():
    import argparse
    import json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--out",type=Path,default=None)
    args=p.parse_args()
    result=static_repo_gate(args.repo)
    if args.out:
        if not args.out.resolve().is_relative_to((args.repo/"artifacts").resolve()):
            p.error("Output must stay under gitignored artifacts/")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
