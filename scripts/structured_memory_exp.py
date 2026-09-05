#!/usr/bin/env python3
"""Structured Global Memory v1 paired experiment scheduler.

Runs the SAME suite/tasks/seeds/turns as the progress-gate baseline, with
``RPENT_STRUCTURED_MEMORY=1`` (harness injects CURRENT PHASE + fired-rule
recoveries). Baseline arm = reused cond=baseline repeat-1 rows from
analysis/progress_gate_runs.csv (paired control) + 3 fresh gate-off spot-checks
(t7s2 / t0s5 / t9s9) to confirm no environment drift.

One phase (SM1): structured on libero_spatial_task t0/t7/t9, seeds 1-10,
repeat 1 -> 30 runs. 8 workers (4 GPUs x 2) — unlimited API supply, no
rate-limit throttling. Writes analysis/structured_memory_runs.csv.

Usage: nohup python scripts/structured_memory_exp.py >> .gap_run/sm_super.log 2>&1 &
"""
import os, sys, time, json, csv, queue, threading, subprocess
import datetime, traceback

ROOT = "/vla_test/yjx/workspace/RPent"
LOGS_DIR = os.path.join(ROOT, "logs")
SM_DIR = os.path.join(LOGS_DIR, "sm_exp")
STATE_FILE = os.path.join(ROOT, ".gap_run", "sm_state.json")
RUNS_CSV = os.path.join(ROOT, "analysis", "structured_memory_runs.csv")
STATUS_MD = os.path.join(LOGS_DIR, "sm_status.md")

STAGE = "SM1"
N_EVAL = 10
EVAL_TURNS = 40
PLANNER_TIMEOUT_S = 2400
MAX_INFRA_RETRY = 3
INFRA_PAUSE_S = 600
RUNTIME_S = 4500
WORKERS_PER_GPU = int(os.environ.get("SM_WORKERS_PER_GPU", "2"))
GPU_IDLE_MB = int(os.environ.get("SM_GPU_IDLE_MB", "4000"))
STATUS_INTERVAL = 300

# Same baseline env, plus the structured gate. Baseline cond leaves the gate
# unset so the prompt is byte-identical to the progress-gate baseline.
COND_ENV = {
    "structured": {"RPENT_STRUCTURED_MEMORY": "1"},
    "baseline": {},
}
P0_TASKS = [0, 7, 9]
P0_SUITE = "libero_spatial_task"
# fresh gate-off spot-checks (confirm reused baseline rows are drift-free)
SPOT_CHECKS = [(7, 2), (0, 5), (9, 9)]

# Explicit header — fixed once so reused-baseline rows (which have no metric
# fields) can never silently drop the metric columns from the runs CSV.
RUN_FIELDNAMES = [
    "ts", "stage", "suite", "task", "seed", "cond", "repeat", "dir",
    "rc", "wall_s", "result",
    "rules_ver", "injections", "injection_tokens_approx", "fired_rules",
    "recovery_success_count", "mem_reads", "final_phase",
]

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import progress_gate_exp as pg  # reuse base_env / classify_dir / idle_gpus / ensure_egl


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def now():
    return datetime.datetime.now()


def run_episode(ep, gpu):
    suite, task, seed, cond, repeat = ep["suite"], ep["task"], ep["seed"], ep["cond"], ep["repeat"]
    ts = datetime.datetime.now().strftime("%Y%m%d-%H:%M:%S")
    outdir = os.path.join(SM_DIR, f"{ts}_{cond}_{suite}_t{task}_s{seed}_r{repeat}")
    os.makedirs(outdir, exist_ok=True)
    env = pg.base_env()
    env.update(COND_ENV.get(cond, {}))
    # per-episode task scope for the harness PhaseTracker (RPENT_TASK first)
    env["RPENT_TASK"] = str(task)
    cvd = "0" if gpu == 0 else f"{gpu},0"
    env["CUDA_VISIBLE_DEVICES"] = cvd
    cmd = [
        "rpent", "--env", "libero", "--suite", suite, "--task", str(task),
        "--seed", str(seed), "--output-dir", outdir,
        "--planner", "api", "--model", "anthropic:kimi-k3",
        "--base-url", "https://dwai-data.shizhuang-inc.com/anthropic",
        "--planner-timeout-s", str(PLANNER_TIMEOUT_S),
        "--max-turns", str(EVAL_TURNS),
    ]
    log(f"gpu{gpu} {ep['stage']} {cond} {suite} t{task} s{seed} r{repeat} start")
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
    log(f"gpu{gpu} {ep['stage']} {cond} {suite} t{task} s{seed} r{repeat} done "
        f"rc={rc} result={result} wall={wall}s")
    return dict(ts=ts, dir=outdir, rc=rc, wall_s=wall, result=result)


# ---------------- persistence ----------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {"baseline_recorded": False, "enqueued": False}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    json.dump(state, open(tmp, "w"))
    os.replace(tmp, STATE_FILE)


def completed_keys():
    keys = set()
    if os.path.exists(RUNS_CSV):
        for r in csv.DictReader(open(RUNS_CSV)):
            keys.add((r["stage"], r["suite"], int(r["task"]), int(r["seed"]),
                      r["cond"], int(r["repeat"])))
    return keys


def metric_fields(outdir):
    """Copy the structured_metrics.json columns; empty dict when gate-off."""
    p = os.path.join(outdir, "structured_metrics.json")
    if not os.path.exists(p):
        return {}
    try:
        m = json.load(open(p))
    except Exception:
        return {}
    return {
        "rules_ver": m.get("rules_ver", ""),
        "injections": m.get("injections", ""),
        "injection_tokens_approx": m.get("injection_tokens_approx", ""),
        "fired_rules": json.dumps(m.get("fired_rules", []), ensure_ascii=False),
        "recovery_success_count": sum(
            1 for v in (m.get("recovery_success") or {}).values() if v),
        "mem_reads": len(m.get("mem_reads") or []),
        "final_phase": m.get("final_phase", ""),
    }


def append_run(state, ep, res):
    row = {
        "ts": res["ts"], "stage": ep["stage"], "suite": ep["suite"],
        "task": ep["task"], "seed": ep["seed"], "cond": ep["cond"],
        "repeat": ep["repeat"], "dir": res["dir"], "rc": res["rc"],
        "wall_s": res["wall_s"], "result": res["result"],
    }
    row.update(metric_fields(res["dir"]))
    fresh = not os.path.exists(RUNS_CSV)
    with open(RUNS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_FIELDNAMES)
        if fresh:
            w.writeheader()
        w.writerow(row)


def record_existing_baseline(state):
    """Copy progress-gate baseline repeat-1 rows (same suite/tasks/seeds) as the
    paired control for this experiment, then add fresh gate-off spot-checks."""
    done = completed_keys()
    if not os.path.exists(pg.RUNS_CSV):
        log("progress_gate_runs.csv missing; cannot reuse baseline rows")
        return
    for r in csv.DictReader(open(pg.RUNS_CSV)):
        if (r["cond"] != "baseline" or r["stage"] != "P0"
                or r["suite"] != P0_SUITE
                or int(r["task"]) not in P0_TASKS
                or int(r["repeat"]) != 1):
            continue
        k = (STAGE, P0_SUITE, int(r["task"]), int(r["seed"]), "baseline", 1)
        if k in done:
            continue
        append_run(state, dict(stage=STAGE, suite=P0_SUITE,
                               task=int(r["task"]), seed=int(r["seed"]),
                               cond="baseline", repeat=1),
                   dict(ts=r["ts"], dir=r["dir"], rc=int(r["rc"] or 0),
                        wall_s=r.get("wall_s") or "", result=r["result"]))
        log(f"reused baseline {P0_SUITE} t{r['task']} s{r['seed']} -> {r['result']}")


def build_episodes(done):
    eps = []
    for t in P0_TASKS:
        for sd in range(1, N_EVAL + 1):
            k = (STAGE, P0_SUITE, t, sd, "structured", 1)
            if k not in done:
                eps.append(dict(stage=STAGE, suite=P0_SUITE, task=t, seed=sd,
                                cond="structured", repeat=1))
    for t, sd in SPOT_CHECKS:
        k = (STAGE, P0_SUITE, t, sd, "baseline", 2)  # fresh gate-off sample
        if k not in done:
            eps.append(dict(stage=STAGE, suite=P0_SUITE, task=t, seed=sd,
                            cond="baseline", repeat=2))
    return eps


# ---------------- workers (infra-retry logic mirrors progress_gate_exp) ----------------
CSV_LOCK = threading.Lock()


def ep_key(ep):
    return (ep["stage"], ep["suite"], ep["task"], ep["seed"], ep["cond"], ep["repeat"])


class Worker(threading.Thread):
    def __init__(self, gpu, q, state, shared):
        super().__init__(daemon=True)
        self.gpu = gpu
        self.q = q
        self.state = state
        self.shared = shared  # {"retry": {key: count}, "consec_err": int}

    def run(self):
        while True:
            try:
                ep = self.q.get_nowait()
            except queue.Empty:
                break
            res = run_episode(ep, self.gpu)
            key = ep_key(ep)
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
                        log(f"gpu{self.gpu}: 3 consecutive infra errors, pausing {INFRA_PAUSE_S}s")
                        time.sleep(INFRA_PAUSE_S)
                    self.q.put(ep)
                    continue
            else:
                with CSV_LOCK:
                    self.shared["consec_err"] = 0
            with CSV_LOCK:
                append_run(self.state, ep, res)


# ---------------- status ----------------
def write_status():
    done = completed_keys()
    lines = [
        "# Structured Memory v1 实验状态\n",
        f"_updated {datetime.datetime.now().isoformat(timespec='seconds')}_\n",
        f"completed: {len(done)} episodes\n",
        f"gpus idle: {pg.idle_gpus()}\n",
    ]
    if os.path.exists(RUNS_CSV):
        rows = list(csv.DictReader(open(RUNS_CSV)))
        agg = {}
        for r in rows:
            k = r["cond"]
            agg.setdefault(k, [0, 0, 0])
            agg[k][1] += 1
            if r["result"] == "success":
                agg[k][0] += 1
            if r.get("injections"):
                agg[k][2] += int(r["injections"])
        lines.append("\n## SR by cond (from result column)\n")
        for k in sorted(agg):
            ok, tot, inj = agg[k]
            lines.append(f"- {k}: {ok}/{tot} ({ok / max(tot, 1):.0%}) avg_inj={inj / max(tot, 1):.1f}\n")
    with open(STATUS_MD, "w") as f:
        f.write("\n".join(lines))


def status_loop(stop_evt):
    while not stop_evt.is_set():
        try:
            write_status()
        except Exception:
            pass
        stop_evt.wait(STATUS_INTERVAL)


def main():
    pg.ensure_egl()
    os.makedirs(SM_DIR, exist_ok=True)
    state = load_state()
    log(f"=== Structured Memory scheduler start | workers/gpu={WORKERS_PER_GPU} "
        f"tasks={P0_TASKS} suite={P0_SUITE} ===")
    stop_evt = threading.Event()
    threading.Thread(target=status_loop, args=(stop_evt,), daemon=True).start()

    # wait for idle GPU(s) — never share a busy card
    gpus = pg.idle_gpus()
    while not gpus:
        log(f"no idle GPU (idle={gpus}); waiting 120s")
        time.sleep(120)
        gpus = pg.idle_gpus()

    record_existing_baseline(state)
    save_state(state)
    done = completed_keys()
    eps = build_episodes(done)
    if not eps:
        log("all episodes already recorded; nothing to run")
        write_status()
        return
    n_workers = len(gpus) * WORKERS_PER_GPU
    q = queue.Queue()
    for e in eps:
        q.put(e)
    log(f"=== {STAGE}: {q.qsize()} episodes on gpus={gpus} ({n_workers} workers) ===")
    shared = {"retry": {}, "consec_err": 0}
    workers = []
    for gi in gpus:
        for _ in range(WORKERS_PER_GPU):
            workers.append(Worker(gi, q, state, shared))
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    log(f"=== {STAGE} worker pool drained ===")
    write_status()
    log("=== scheduler finished ===")


if __name__ == "__main__":
    main()
