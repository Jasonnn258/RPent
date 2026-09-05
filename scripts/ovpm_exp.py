#!/usr/bin/env python3
"""Outcome-Validated Procedural Memory (OVP-M) experiment scheduler.

Stages (one CSV: analysis/outcome_validation_runs.csv; stage+tier columns keep
arms comparable and strictly paired by (task, seed, repeat)):

  sanity   vanilla x one GLM tier x t0/t7/t9 x s1-10          (30 ep)
           -> run twice: --tier glm-5.3 / --tier glm-5.3-flash
  dev      armA (SM1) + armB (A+RPENT_OVPM) x t0/t7/t9 x s1-10 x r1-3 (180 ep)
  devC     armC (B+RPENT_REASON_MODE) same 90 pairing as dev  (only if B valid)
  heldout  armA+armB+armC x t1/t4/t8 x s1-10 x r1             (90 ep)
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
PLANNER_TIMEOUT_S = 2400
MAX_INFRA_RETRY = 3
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
}

DEV_TASKS = [0, 7, 9]
HELDOUT_TASKS = [1, 4, 8]
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
    # 3) repo path (old scripts hardcode the /vla_test bind)
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
    cvd = "0" if gpu == 0 else f"{gpu},0"
    env["CUDA_VISIBLE_DEVICES"] = cvd
    cmd = [
        "rpent", "--env", "libero", "--suite", suite, "--task", str(task),
        "--seed", str(seed), "--output-dir", outdir,
        "--planner", "api", "--model", model,
        "--base-url", GLM_BASE_URL,
        "--planner-timeout-s", str(PLANNER_TIMEOUT_S),
        "--max-turns", str(EVAL_TURNS),
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
    }


CSV_LOCK = threading.Lock()


def append_run(ep, res):
    row = {
        "ts": res["ts"], "stage": ep["stage"], "tier": ep["tier"],
        "model": TIERS[ep["tier"]], "suite": ep["suite"], "task": ep["task"],
        "seed": ep["seed"], "cond": ep["cond"], "repeat": ep["repeat"],
        "dir": res["dir"], "rc": res["rc"], "wall_s": res["wall_s"],
        "result": res["result"],
    }
    row.update(metric_fields(res["dir"]))
    fresh = not os.path.exists(RUNS_CSV)
    with CSV_LOCK:
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
                    choices=["sanity", "dev", "devC", "heldout", "smoke"])
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
