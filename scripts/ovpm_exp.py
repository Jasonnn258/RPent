#!/usr/bin/env python3
"""Outcome-Validated Procedural Memory (OVP-M) experiment scheduler.

Stages (one CSV: analysis/outcome_validation_runs.csv; stage+tier columns keep
arms comparable and strictly paired by (task, seed, repeat)):

  sanity   vanilla x one GLM tier x t0/t7/t9 x s1-10          (30 ep)
           -> run twice: --tier glm-5.3 / --tier glm-5.3-flash
  dev      armA (SM1) + armB (A+RPENT_OVPM) x t0/t7/t9 x s1-10 x r1-3 (180 ep)
  devC     armC (B+RPENT_REASON_MODE) same 90 pairing as dev  (only if B valid)
  heldout  armA+armB+armC x t1/t4/t8 x s1-10 x r1             (90 ep)
  dev2     armB2 (A+RPENT_OVPM2, B2 state-transition verification) x
           t0/t7/t9 x s1-10 x r1-3                             (90 ep)
  stage1   armA+armB+armB2 x t2/t3/t5 x s1-10 x r1             (90 ep)
  memB     memB1/memB2/memB3 x t3/t5/t9 x s1-10 x r1           (90 ep)
           Stage B1 decision-point memory study (tier glm-5.3-flash).
           B0: t3/t5 reuse the 09-15/16 armA stage1 rows; t9 supplement
           runs --conds memB0 --tasks 9 (10 ep).
  smoke    --conds/--tasks/--seeds/--repeats overrides for one-off checks

Everything vanilla/GLM/osmesa differs from the kimi-era scripts:
  - planner = GLM anthropic-compatible endpoint (key from rpent_env.sh
    GLM_API_KEY, never logged);
  - MUJOCO_GL=osmesa + PYOPENGL_PLATFORM=osmesa, MUJOCO_EGL_DEVICE_ID and
    LIBGL_ALWAYS_SOFTWARE unset — this container has 0 EGL devices
    (see memory/rpent-env-gl-fix.md);
  - ROOT points at /workspace/yjx (bind of /vla_test).

Resume-safe: the CSV is the state (completed_keys); infra failures retry up
to MAX_INFRA_RETRY. No rerun-until-success: every finished episode is kept.

Usage:
  nohup python scripts/ovpm_exp.py --stage sanity --tier glm-5.3 \
      >> .gap_run/ovpm_sanity_53.log 2>&1 &
"""
import argparse
import csv
import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import time

ROOT = "/workspace/yjx/workspace/RPent"
LOGS_DIR = os.path.join(ROOT, "logs")
OVPM_DIR = os.path.join(LOGS_DIR, "ovpm_exp")
RUNS_CSV = os.path.join(ROOT, "analysis", "outcome_validation_runs.csv")
STATUS_MD = os.path.join(LOGS_DIR, "ovpm_status.md")
V2_RULES = os.path.join(ROOT, "analysis", "structured_rules_v2.json")

N_EVAL = 10
EVAL_TURNS = 40
# 2026-09-08 mid-heldout incident: GLM morning latency ~87-150s/turn (vs
# ~40-60s when 2400 was calibrated) killed healthy 25-30-turn episodes at
# budget expiry (infra_timeout, auto-retried). Raised to 3600s mid-run —
# wall-clock headroom only; the scientific control (EVAL_TURNS=40) and the
# method are untouched. RUNTIME_S=4500 still > 3600 + ~90s startup.
PLANNER_TIMEOUT_S = 3600
MAX_INFRA_RETRY = 3

# Planner output cap. Thinking(effort='high') maps to budget_tokens=16384
# (pydantic-ai ANTHROPIC_THINKING_BUDGET_MAP); with the old 8192 cap the
# budget exceeded max_tokens and GLM (unlike Anthropic, no validation)
# returned zero-content max_tokens finishes — arm C's per-turn restarts hit
# it at 41% vs arm B's 3%. 24576 = 16384 budget + response headroom.
PLANNER_MAX_TOKENS = 24576

# pydantic-ai raises this when a model burns the whole output cap before
# emitting any content; it is an infra defect, never the policy's fault.
_TOKEN_LIMIT_FATAL = "token limit ({}) exceeded before any response was generated"
INFRA_PAUSE_S = 600
RUNTIME_S = 4500
WORKERS_PER_GPU = int(os.environ.get("OVPM_WORKERS_PER_GPU", "2"))
# Dev-machine safety cap (2026-09-05): this box is a SHARED dev machine
# (8xH100, cgroup 200G RAM / 32-core quota), NOT a training node — total
# workers default to <= 8. The historical 16 (2/GPU x 8 cards, ~36-44 ep/h)
# belongs on a dedicated benchmark node: set OVPM_MAX_WORKERS=16 (or
# DEV_MAX_WORKERS=16) there when memory headroom allows.
MAX_WORKERS = int(os.environ.get("OVPM_MAX_WORKERS",
                                 os.environ.get("DEV_MAX_WORKERS", "8")))
# Cold-start stagger: this container has a 200GB cgroup RAM ceiling;
# simultaneous (Pi0.5 + SAM3 + env) loads mass-SIGKILL. Worker i waits
# i*STAGGER before its first episode so at most one model load is in
# flight per interval.
STAGGER_S = int(os.environ.get("OVPM_STAGGER_S", "90"))
GPU_IDLE_MB = int(os.environ.get("OVPM_GPU_IDLE_MB", "4000"))
STATUS_INTERVAL = 300

TIERS = {
    "glm-5.3": "anthropic:glm-5.3",
    "glm-5.3-flash": "anthropic:glm-5.3-flash",
}
GLM_BASE_URL = "https://open.bigmodel.cn/api/anthropic"

COND_ENV = {
    "vanilla": {},
    "armA": {"RPENT_STRUCTURED_MEMORY": "1"},
    "armB": {"RPENT_STRUCTURED_MEMORY": "1",
             "RPENT_OVPM": "1",
             "RPENT_OVPM_CONTRACTS": V2_RULES},
    "armC": {"RPENT_STRUCTURED_MEMORY": "1",
             "RPENT_OVPM": "1",
             "RPENT_OVPM_CONTRACTS": V2_RULES,
             "RPENT_REASON_MODE": "1"},
    # B2 = arm A + state-transition verification (independent of arm B's
    # RPENT_OVPM gate; the SM1 tracker stays on for phase-context logging).
    "armB2": {"RPENT_STRUCTURED_MEMORY": "1",
              "RPENT_OVPM2": "1"},
    # Stage B1 (2026-09-17): decision-point long-term memory retrieval.
    # memB0 = historical armA behavior (t9-only supplement — the t3/t5 B0
    # rows reuse the 2026-09-15/16 armA stage1 batch, same code+config).
    "memB0": {"RPENT_STRUCTURED_MEMORY": "1"},
    # memB1 = access fix only (real layered memory paths in WORKFLOW step 0).
    "memB1": {"RPENT_STRUCTURED_MEMORY": "1",
              "RPENT_MEMORY_ACCESS_FIX": "1"},
    # memB2 = + decision-time trigger + Q0-fixed lexical ranking (frozen).
    "memB2": {"RPENT_STRUCTURED_MEMORY": "1",
              "RPENT_MEMORY_ACCESS_FIX": "1",
              "RPENT_MEMORY_TRIGGER": "1",
              "RPENT_MEMORY_RANK": "Q0_FIXED"},
    # memB3 = same trigger, Q3 structured ranking (frozen Stage A port).
    "memB3": {"RPENT_STRUCTURED_MEMORY": "1",
              "RPENT_MEMORY_ACCESS_FIX": "1",
              "RPENT_MEMORY_TRIGGER": "1",
              "RPENT_MEMORY_RANK": "Q3"},
    # Stage C3 (2026-09-18): O2 = progress-aware trigger (Stage C2 frozen
    # rules R1-R5) + poor query + Q0-fixed lexical + access fix + soft.
    # O0 (OLD_TRIGGER+POOR_QUERY) == memB2 exactly -> reused, not re-run
    # (analysis/stageC_compatibility_audit.md).
    "memO2": {"RPENT_STRUCTURED_MEMORY": "1",
              "RPENT_MEMORY_ACCESS_FIX": "1",
              "RPENT_MEMORY_TRIGGER": "progress",
              "RPENT_MEMORY_RANK": "Q0_FIXED"},
}

DEV_TASKS = [0, 7, 9]
HELDOUT_TASKS = [1, 4, 8]
# B2 Stage-1 tasks: t2/t3/t5 (t1/t4/t8 already consumed as OVP-M heldout;
# t6 fully reserved; t2/t3/t5 have no A/B1 rows — Stage 1 runs all three
# arms fresh on them).
B2_NEW_TASKS = [2, 3, 5]
# Stage B1 tasks (memory-relevant, from the Stage A decision-point dataset):
# t3 = all five YES classes (predicate/grasp/pick/recovery/perception),
# t5 = predicate timing + pick verification,
# t9 = perception-heavy (diagnostic subset: offline Recall=0 expected to
# reproduce online; no new features added to probe it).
MEMB_TASKS = [3, 5, 9]
P0_SUITE = "libero_spatial_task"

RUN_FIELDNAMES = [
    "ts", "stage", "tier", "model", "suite", "task", "seed", "cond",
    "repeat", "dir", "rc", "wall_s", "result",
    # structured (SM1) metrics
    "rules_ver", "injections", "injection_tokens_approx", "fired_rules",
    "recovery_success_count", "mem_reads", "final_phase",
    "fast_steps", "slow_reasons",
    # ovpm (arm B) metrics
    "ovpm_n_matched", "ovpm_n_mismatched", "ovpm_n_uncertain",
    "ovpm_mismatch_escalations", "ovpm_repeated_same_strategy",
    "ovpm_commit_events", "ovpm_recovery_events",
    "ovpm_commit_latency_mean", "ovpm_recovery_latency_mean",
    # reason mode (arm C) metrics — flat keys in structured_metrics.json
    "commit_mode_steps", "reason_mode_steps",
    "commit_tokens_in", "commit_tokens_out",
    "reason_tokens_in", "reason_tokens_out",
    # B2 (state-transition verification) metrics — nested under "b2"
    "b2_n_success", "b2_n_failure", "b2_n_uncertain",
    "b2_false_positive_caught", "b2_observe_directives", "b2_observe_obeyed",
    "b2_reason_escalations", "b2_redundant_obs",
    "b2_commit_latency_mean", "b2_recovery_latency_mean",
    # Stage B1 (decision-point memory recall) — from memory_events.jsonl
    "mem_triggers", "mem_latency_mean_ms", "mem_top1s",
]

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import progress_gate_exp as pg  # reuse classify_dir / idle_gpus / ensure_egl


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


# ---------------------------------------------------------------- episode env

def base_env():
    """pg.base_env() with the three mandatory container overrides."""
    env = pg.base_env()
    # 1) GLM planner creds (key value never logged)
    env.pop("ANTHROPIC_API_KEY", None)
    try:
        with open("/workspace/yjx/rpent_data/rpent_env.sh") as f:
            for line in f:
                if line.startswith("GLM_API_KEY="):
                    env["ANTHROPIC_API_KEY"] = (
                        line.split("=", 1)[1].strip().strip('"').strip("'"))
    except Exception as ex:
        log(f"WARN reading GLM_API_KEY: {ex}")
    if not env.get("ANTHROPIC_API_KEY"):
        log("FATAL: GLM_API_KEY missing — GLM planner would 401")
        sys.exit(2)
    # 2) this container exposes 0 EGL devices: osmesa is the only working GL
    env["MUJOCO_GL"] = "osmesa"
    env["PYOPENGL_PLATFORM"] = "osmesa"
    env.pop("MUJOCO_EGL_DEVICE_ID", None)
    env.pop("LIBGL_ALWAYS_SOFTWARE", None)
    # 2b) ambient http_proxy must never intercept loopback RPC (the GLM
    # proxy returns 503 for 127.0.0.1 → healthz starves); HttpRpcClient
    # already bypasses via its own opener — this covers any other urllib
    # user on loopback. External calls (open.bigmodel.cn) keep the proxy.
    loopback = "127.0.0.1,localhost"
    env["no_proxy"] = (env.get("no_proxy") and
                       f"{env['no_proxy']},{loopback}") or loopback
    env["NO_PROXY"] = env["no_proxy"]
    # 3) Stage B1 memB3 embeds queries with a local bge-small encoder —
    #    the hub is reachable only via the mirror through this proxy.
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    return env


def run_episode(ep, gpu):
    suite, task, seed = ep["suite"], ep["task"], ep["seed"]
    cond, repeat, tier = ep["cond"], ep["repeat"], ep["tier"]
    model = TIERS[tier]
    ts = datetime.datetime.now().strftime("%Y%m%d-%H:%M:%S")
    outdir = os.path.join(
        OVPM_DIR, f"{ts}_{tier}_{cond}_{suite}_t{task}_s{seed}_r{repeat}")
    os.makedirs(outdir, exist_ok=True)
    env = base_env()
    env.update(COND_ENV.get(cond, {}))
    env["RPENT_TASK"] = str(task)
    if cond == "armB2":
        # B2 event logging fields (never read by any other arm's code path)
        env["RPENT_B2_SEED"] = str(seed)
        env["RPENT_B2_REPEAT"] = str(repeat)
    cvd = "0" if gpu == 0 else f"{gpu},0"
    env["CUDA_VISIBLE_DEVICES"] = cvd
    cmd = [
        "rpent", "--env", "libero", "--suite", suite, "--task", str(task),
        "--seed", str(seed), "--output-dir", outdir,
        "--planner", "api", "--model", model,
        "--base-url", GLM_BASE_URL,
        "--planner-timeout-s", str(PLANNER_TIMEOUT_S),
        "--max-turns", str(EVAL_TURNS),
        "--max-tokens", str(PLANNER_MAX_TOKENS),
    ]
    log(f"gpu{gpu} {ep['stage']} {tier} {cond} {suite} t{task} s{seed} "
        f"r{repeat} start")
    t0 = time.time()
    try:
        p = subprocess.run(cmd, env=env, timeout=RUNTIME_S,
                           capture_output=True, text=True)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = -9
    except Exception:
        rc = -1
    wall = round(time.time() - t0, 1)
    result = pg.classify_dir(outdir)
    # Planner-side zero-content truncation (thinking budget burnout) is an
    # infra defect: reclassify so the retry path and the analysis treat it
    # as what it is, never as the policy failing the task.
    if result not in ("success", "infra_crash", "infra_timeout"):
        rl = os.path.join(outdir, "run.log")
        try:
            with open(rl, errors="replace") as f:
                if _TOKEN_LIMIT_FATAL.format(PLANNER_MAX_TOKENS) in f.read() or \
                        _TOKEN_LIMIT_FATAL.format("8192") in f.read():
                    result = "infra_crash"
        except OSError:
            pass
    log(f"gpu{gpu} {ep['stage']} {tier} {cond} {suite} t{task} s{seed} "
        f"r{repeat} done rc={rc} result={result} wall={wall}s")
    return dict(ts=ts, dir=outdir, rc=rc, wall_s=wall, result=result)


# ---------------------------------------------------------------- persistence

def completed_keys():
    keys = set()
    if os.path.exists(RUNS_CSV):
        for r in csv.DictReader(open(RUNS_CSV)):
            keys.add((r["stage"], r["tier"], r["suite"], int(r["task"]),
                      int(r["seed"]), r["cond"], int(r["repeat"])))
    return keys


def metric_fields(outdir):
    """structured_metrics.json columns (SM1 + nested ovpm); {} when gate-off."""
    p = os.path.join(outdir, "structured_metrics.json")
    if not os.path.exists(p):
        return {}
    try:
        m = json.load(open(p))
    except Exception:
        return {}
    o = m.get("ovpm") or {}
    b = m.get("b2") or {}
    return {
        "rules_ver": m.get("rules_ver", ""),
        "injections": m.get("injections", ""),
        "injection_tokens_approx": m.get("injection_tokens_approx", ""),
        "fired_rules": json.dumps(m.get("fired_rules", []), ensure_ascii=False),
        "recovery_success_count": sum(
            1 for v in (m.get("recovery_success") or {}).values() if v),
        "mem_reads": len(m.get("mem_reads") or []),
        "final_phase": m.get("final_phase", ""),
        "fast_steps": m.get("fast_steps", ""),
        "slow_reasons": json.dumps(m.get("slow_reasons") or [],
                                   ensure_ascii=False),
        "ovpm_n_matched": o.get("n_matched", ""),
        "ovpm_n_mismatched": o.get("n_mismatched", ""),
        "ovpm_n_uncertain": o.get("n_uncertain", ""),
        "ovpm_mismatch_escalations": o.get("mismatch_escalations", ""),
        "ovpm_repeated_same_strategy": o.get(
            "repeated_same_strategy_after_mismatch", ""),
        "ovpm_commit_events": len(o.get("commit_events") or []),
        "ovpm_recovery_events": len(o.get("recovery_events") or []),
        "ovpm_commit_latency_mean": o.get("commit_latency_mean", ""),
        "ovpm_recovery_latency_mean": o.get("recovery_latency_mean", ""),
        # arm C (empty for A/B rows — keys absent when the gate is off)
        "commit_mode_steps": m.get("commit_mode_steps", ""),
        "reason_mode_steps": m.get("reason_mode_steps", ""),
        "commit_tokens_in": m.get("commit_tokens_in", ""),
        "commit_tokens_out": m.get("commit_tokens_out", ""),
        "reason_tokens_in": m.get("reason_tokens_in", ""),
        "reason_tokens_out": m.get("reason_tokens_out", ""),
        # arm B2 (empty for other arms — key absent when the gate is off)
        "b2_n_success": b.get("n_confirmed_success", ""),
        "b2_n_failure": b.get("n_confirmed_failure", ""),
        "b2_n_uncertain": b.get("n_uncertain", ""),
        "b2_false_positive_caught": b.get("false_positive_caught", ""),
        "b2_observe_directives": b.get("n_observe_directives", ""),
        "b2_observe_obeyed": b.get("n_observe_obeyed", ""),
        "b2_reason_escalations": b.get("n_reason_escalations", ""),
        "b2_redundant_obs": b.get("n_redundant_observations", ""),
        "b2_commit_latency_mean": b.get("commit_latency_mean", ""),
        "b2_recovery_latency_mean": b.get("recovery_latency_mean", ""),
        # Stage B1 memory recall (empty for non-memB arms — file absent)
        **_mem_recall_fields(outdir),
    }


def _mem_recall_fields(outdir):
    """memory_events.jsonl -> CSV columns; {} when the file is absent."""
    p = os.path.join(outdir, "memory_events.jsonl")
    if not os.path.exists(p):
        return {}
    events = []
    try:
        with open(p) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
    except Exception:
        return {}
    if not events:
        return {"mem_triggers": 0, "mem_latency_mean_ms": "",
                "mem_top1s": "[]"}
    lats = [e.get("retrieval_latency_ms") for e in events
            if isinstance(e.get("retrieval_latency_ms"), (int, float))]
    return {
        "mem_triggers": len(events),
        "mem_latency_mean_ms": round(sum(lats) / len(lats), 1) if lats else "",
        "mem_top1s": json.dumps([e.get("top1_memory") for e in events],
                                ensure_ascii=False),
    }


CSV_LOCK = threading.Lock()


def _migrate_csv_header():
    """One-time: extend the header when RUN_FIELDNAMES grew (arm C columns).

    Existing rows keep their column count — short rows are re-serialized
    with "" for the new fields. Rows already in the new width pass through.
    """
    if not os.path.exists(RUNS_CSV):
        return
    with open(RUNS_CSV, newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] == RUN_FIELDNAMES:
        return
    old_header = rows[0]
    out = [RUN_FIELDNAMES]
    for r in rows[1:]:
        if len(r) == len(old_header):
            d = dict(zip(old_header, r))
        elif len(r) == len(RUN_FIELDNAMES):  # written post-extension
            d = dict(zip(RUN_FIELDNAMES, r))
        else:
            log(f"WARN csv row width {len(r)} matches neither header; "
                "keeping raw")
            out.append(r)
            continue
        out.append([d.get(k, "") for k in RUN_FIELDNAMES])
    tmp = RUNS_CSV + ".tmp"
    with open(tmp, "w", newline="") as f:
        csv.writer(f).writerows(out)
    os.replace(tmp, RUNS_CSV)
    log(f"csv header migrated: {len(old_header)} -> {len(RUN_FIELDNAMES)} cols")


def append_run(ep, res):
    row = {
        "ts": res["ts"], "stage": ep["stage"], "tier": ep["tier"],
        "model": TIERS[ep["tier"]], "suite": ep["suite"], "task": ep["task"],
        "seed": ep["seed"], "cond": ep["cond"], "repeat": ep["repeat"],
        "dir": res["dir"], "rc": res["rc"], "wall_s": res["wall_s"],
        "result": res["result"],
    }
    row.update(metric_fields(res["dir"]))
    with CSV_LOCK:
        _migrate_csv_header()
        fresh = not os.path.exists(RUNS_CSV)
        with open(RUNS_CSV, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=RUN_FIELDNAMES)
            if fresh:
                w.writeheader()
            w.writerow(row)


# ---------------------------------------------------------------- episodes

def build_episodes(args, done):
    """Pre-registered stage grids; smoke overrides conds/tasks/seeds/repeats."""
    conds = (args.conds.split(",") if args.conds else None)
    tasks = ([int(t) for t in args.tasks.split(",")] if args.tasks else None)
    seeds = (range(1, args.seeds + 1) if args.seeds else range(1, N_EVAL + 1))
    repeats = (range(1, args.repeats + 1) if args.repeats else None)

    if args.stage == "sanity":
        conds = conds or ["vanilla"]
        tasks = tasks or DEV_TASKS
        repeats = repeats or [1]
    elif args.stage == "dev":
        conds = conds or ["armA", "armB"]
        tasks = tasks or DEV_TASKS
        repeats = repeats or [1, 2, 3]
    elif args.stage == "devC":
        conds = conds or ["armC"]
        tasks = tasks or DEV_TASKS
        repeats = repeats or [1, 2, 3]
    elif args.stage == "heldout":
        conds = conds or ["armA", "armB", "armC"]
        tasks = tasks or HELDOUT_TASKS
        repeats = repeats or [1]
    elif args.stage == "dev2":
        # B2 development: t0/t7/t9 x s1-10 x r1-3, strictly paired with the
        # existing dev armA/armB rows (same tier/tasks/seeds/repeats).
        conds = conds or ["armB2"]
        tasks = tasks or DEV_TASKS
        repeats = repeats or [1, 2, 3]
    elif args.stage == "stage1":
        # B2 held-out: t2/t3/t5 x s1-10 x r1 across all three arms (t2/t3/t5
        # have no prior A/B1 rows — Stage 1 runs them fresh for comparability).
        conds = conds or ["armA", "armB", "armB2"]
        tasks = tasks or B2_NEW_TASKS
        repeats = repeats or [1]
    elif args.stage == "memB":
        # Stage B1: access-fix / +trigger+lexical / +trigger+Q3 over the
        # three memory-relevant tasks; B0 = matched historical armA rows
        # (t3/t5 from the 2026-09-15/16 stage1 batch) + a fresh memB0
        # supplement on t9 (the old t9 batch predates --max-tokens 24576).
        conds = conds or ["memB1", "memB2", "memB3"]
        tasks = tasks or MEMB_TASKS
        repeats = repeats or [1]
    elif args.stage == "memC":
        # Stage C3: single-variable online O0 vs O2 (C1 query gate FAILED,
        # C2 progress-trigger gate PASSED -> only the trigger arm runs).
        # O0 == #49 memB2 rows (reused); only memO2 runs fresh.
        conds = conds or ["memO2"]
        tasks = tasks or MEMB_TASKS
        repeats = repeats or [1]
    else:  # smoke
        conds = conds or ["vanilla", "armA", "armB"]
        tasks = tasks or [7]
        repeats = repeats or [1]

    eps = []
    for cond in conds:
        for t in tasks:
            for sd in seeds:
                for r in repeats:
                    k = (args.stage, args.tier, P0_SUITE, t, sd, cond, r)
                    if k not in done:
                        eps.append(dict(stage=args.stage, tier=args.tier,
                                        suite=P0_SUITE, task=t, seed=sd,
                                        cond=cond, repeat=r))
    return eps


# ---------------------------------------------------------------- workers

class Worker(threading.Thread):
    def __init__(self, gpu, q, shared, index=0):
        super().__init__(daemon=True)
        self.gpu = gpu
        self.q = q
        self.shared = shared  # {"retry": {key: n}, "consec_err": int}
        self.index = index

    def run(self):
        if self.index and STAGGER_S:
            log(f"worker{self.index} gpu{self.gpu}: cold-start stagger "
                f"{self.index * STAGGER_S}s")
            time.sleep(self.index * STAGGER_S)
        while True:
            try:
                ep = self.q.get_nowait()
            except queue.Empty:
                break
            res = run_episode(ep, self.gpu)
            key = (ep["stage"], ep["tier"], ep["suite"], ep["task"],
                   ep["seed"], ep["cond"], ep["repeat"])
            if res["result"] in ("infra_crash", "infra_timeout"):
                with CSV_LOCK:
                    n = self.shared["retry"].get(key, 0) + 1
                    self.shared["retry"][key] = n
                    self.shared["consec_err"] += 1
                    consec = self.shared["consec_err"]
                    if consec >= 3:
                        self.shared["consec_err"] = 0
                if n <= MAX_INFRA_RETRY:
                    if consec >= 3:
                        log(f"gpu{self.gpu}: 3 consecutive infra errors, "
                            f"pausing {INFRA_PAUSE_S}s")
                        time.sleep(INFRA_PAUSE_S)
                    self.q.put(ep)
                    continue
            else:
                with CSV_LOCK:
                    self.shared["consec_err"] = 0
            append_run(ep, res)


# ---------------------------------------------------------------- status

def write_status():
    done = completed_keys()
    lines = [
        "# OVP-M 实验状态\n",
        f"_updated {datetime.datetime.now().isoformat(timespec='seconds')}_\n",
        f"completed episodes (all stages): {len(done)}\n",
        f"gpus idle: {pg.idle_gpus()}\n",
    ]
    if os.path.exists(RUNS_CSV):
        rows = list(csv.DictReader(open(RUNS_CSV)))
        agg = {}
        for r in rows:
            k = (r["stage"], r["tier"], r["cond"])
            agg.setdefault(k, [0, 0])
            agg[k][1] += 1
            if r["result"] == "success":
                agg[k][0] += 1
        lines.append("\n## SR by stage/tier/cond\n")
        for k in sorted(agg):
            ok, tot = agg[k]
            lines.append(
                f"- {'/'.join(k)}: {ok}/{tot} ({ok / max(tot, 1):.0%})\n")
    with open(STATUS_MD, "w") as f:
        f.write("\n".join(lines))


def status_loop(stop_evt):
    while not stop_evt.is_set():
        try:
            write_status()
        except Exception:
            pass
        stop_evt.wait(STATUS_INTERVAL)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["sanity", "dev", "devC", "heldout", "dev2",
                             "stage1", "memB", "memC", "smoke"])
    ap.add_argument("--tier", default="glm-5.3", choices=sorted(TIERS))
    ap.add_argument("--conds", help="comma list overriding stage defaults")
    ap.add_argument("--tasks", help="comma list, e.g. 0,7,9")
    ap.add_argument("--seeds", type=int, help="number of seeds (1..N)")
    ap.add_argument("--repeats", type=int, help="number of repeats (1..N)")
    args = ap.parse_args()

    pg.preflight(label="ovpm", lock_name="ovpm")

    # egl_ready() is false forever on this container (0 EGL devices) and
    # ensure_egl() sys.exits when its apt reinstall fails — we render with
    # osmesa, so probe that directly with a tiny render instead.
    probe = subprocess.run(
        [sys.executable, "-c",
         "import os; os.environ['MUJOCO_GL']='osmesa';"
         "os.environ['PYOPENGL_PLATFORM']='osmesa';"
         "import mujoco; m = mujoco.MjModel.from_xml_string('<mujoco/>');"
         "r = mujoco.Renderer(m, 32, 32); r._scene  # force context"],
        capture_output=True, text=True, timeout=120)
    if probe.returncode == 0:
        log("GL check: osmesa render probe OK (EGL not needed)")
    else:
        log(f"FATAL: osmesa render probe failed: {probe.stderr[-400:]}")
        sys.exit(1)
    os.makedirs(OVPM_DIR, exist_ok=True)
    stop_evt = threading.Event()
    threading.Thread(target=status_loop, args=(stop_evt,),
                     daemon=True).start()

    gpus = pg.idle_gpus()
    while not gpus:
        log("no idle GPU; waiting 120s")
        time.sleep(120)
        gpus = pg.idle_gpus()

    done = completed_keys()
    eps = build_episodes(args, done)
    if not eps:
        log("all episodes already recorded; nothing to run")
        write_status()
        return

    n_workers = min(len(gpus) * WORKERS_PER_GPU, MAX_WORKERS)
    q = queue.Queue()
    for e in eps:
        q.put(e)
    log(f"=== {args.stage}/{args.tier}: {q.qsize()} episodes on gpus={gpus} "
        f"({n_workers} workers, cap {MAX_WORKERS}) ===")
    shared = {"retry": {}, "consec_err": 0}
    workers = []
    # round-robin GPUs over the capped worker count
    for i in range(n_workers):
        workers.append(Worker(gpus[i % len(gpus)], q, shared, index=i))
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    log(f"=== {args.stage}/{args.tier} worker pool drained ===")
    write_status()
    stop_evt.set()
    log("=== scheduler finished ===")


if __name__ == "__main__":
    main()
