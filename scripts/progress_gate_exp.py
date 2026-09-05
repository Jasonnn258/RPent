#!/usr/bin/env python3
"""Progress Gate unattended experiment scheduler (P0 -> P1 -> P2 -> P3).

Runs rpent episodes from an adaptive queue across idle GPUs. Each worker grabs
the next episode, runs it via subprocess, classifies, retries infra failures
(<= MAX_INFRA_RETRY, pausing the worker after 3 consecutive same-type infra
errors), and appends one row to analysis/progress_gate_runs.csv. State survives
restarts via .gap_run/pg_state.json.

Phases (adaptive, gated):
  P0  libero_spatial_task t0/t7/t9, seeds 1-10:
        baseline (repeat 1 = existing run, repeats 2-3 fresh) vs
        ours/progress_gate (repeats 1-3)
  P1  hardcap ablation on t0/t7/t9 (repeats 1-3)  -- gated: P0 no negative effect
  P2  ours on spatial_task/spatial_swap/goal_task/goal_swap x t0-9 x seeds 1-10
        (repeat 1) -- gated: P0 positive; baseline = existing runs (repeat 1)
  P3  extra repeats of P0/P2 while time remains

Window: until FINAL_STOP (2026-08-17 18:45). No new episodes after
STOP_ENQUEUE (1h before); running episodes finish; final summary written.

Usage: nohup python scripts/progress_gate_exp.py >> .gap_run/pg_super.log 2>&1 &
"""
import os, sys, time, json, csv, glob, re, queue, threading, subprocess
import datetime, traceback

ROOT = "/vla_test/yjx/workspace/RPent"
LOGS_DIR = os.path.join(ROOT, "logs")
PG_DIR = os.path.join(LOGS_DIR, "pg_exp")
STATE_FILE = os.path.join(ROOT, ".gap_run", "pg_state.json")
RUNS_CSV = os.path.join(ROOT, "analysis", "progress_gate_runs.csv")
STATUS_MD = os.path.join(ROOT, "logs", "experiment_status.md")
SNAP_DIR = os.path.join(LOGS_DIR, "pg_snapshots")
SUPER_LOG = os.path.join(ROOT, ".gap_run", "pg_super.log")

# Window overridable via env (used for window-outside supplementary backfills,
# e.g. completing the P1 hardcap t9 arm after the official window closed).
FINAL_STOP = os.environ.get("PG_FINAL_STOP", "2026-08-17 18:45")
STOP_ENQUEUE = os.environ.get("PG_STOP_ENQUEUE", "2026-08-17 17:45")
N_EVAL = 10
EVAL_TURNS = 40
PLANNER_TIMEOUT_S = 2400
MAX_INFRA_RETRY = 3
INFRA_PAUSE_S = 600
RUNTIME_S = 4500
WORKERS_PER_GPU = int(os.environ.get("PG_WORKERS_PER_GPU", "2"))
GPU_IDLE_MB = int(os.environ.get("PG_GPU_IDLE_MB", "4000"))
STATUS_INTERVAL = 300

COND_ENV = {
    "baseline": {},
    "ours": {"RPENT_PERCEPTION_MODE": "progress_gate",
             "RPENT_PERCEPTION_STREAK": "3", "RPENT_PERCEPTION_TOL_M": "0.01"},
    "hardcap": {"RPENT_PERCEPTION_MODE": "hardcap", "RPENT_PERCEPTION_STREAK": "6"},
}
P0_TASKS = [0, 7, 9]
P0_SUITE = "libero_spatial_task"
P2_SUITES = ["libero_spatial_task", "libero_spatial_swap",
             "libero_goal_task", "libero_goal_swap"]

BASE_ENV = None


def log(msg):
    # print-only; the launcher redirects stdout/stderr to SUPER_LOG
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def now():
    return datetime.datetime.now()


def parse_dt(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")


def base_env():
    global BASE_ENV
    if BASE_ENV is None:
        e = os.environ.copy()
        e["PATH"] = "/vla_test/yjx/miniconda3/envs/vla/bin:" + e.get("PATH", "")
        e.update({
            "PI05_CHECKPOINT_PATH": "/vla_test/yjx/rpent_data/checkpoints/pi05",
            "SAM3_CHECKPOINT_PATH": "/vla_test/yjx/rpent_data/checkpoints/sam3/sam3.pt",
            "ROBOT_PLATFORM": "LIBERO",
            "LIBERO_TYPE": "pro",
            "OPENPI_DATA_HOME": "/vla_test/yjx/rpent_data/.cache/openpi",
            "LIBERO_CONFIG_PATH": "/vla_test/yjx/rpent_data/.libero",
            "HF_HUB_OFFLINE": "1",
            "OMP_NUM_THREADS": "4",
            "TORCHINDUCTOR_COMPILE_WORKERS": "4",
            "MUJOCO_GL": "egl",
            "MUJOCO_EGL_DEVICE_ID": "0",
            "LIBGL_ALWAYS_SOFTWARE": "1",
        })
        try:
            with open("/vla_test/yjx/rpent_data/rpent_env.sh") as f:
                for line in f:
                    if line.startswith("DW_KEY="):
                        e["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
        except Exception as ex:
            log(f"WARN reading DW_KEY: {ex}")
        BASE_ENV = e
    return dict(BASE_ENV)


def idle_gpus():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        res = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2:
                idx, used = parts
                if int(used) < GPU_IDLE_MB:
                    res.append(int(idx))
        return res
    except Exception:
        return []


def _states(d):
    p = os.path.join(d, "states.json")
    if not os.path.exists(p):
        return None, None
    try:
        st = json.load(open(p))
    except Exception:
        return None, None
    if not isinstance(st, list) or not st:
        return None, None
    return st, st[-1].get("libero_terminated")


def classify_dir(d):
    st, term = _states(d)
    if st is None:
        return "infra_crash"
    if term:
        return "success"
    rl = os.path.join(d, "run.log")
    if os.path.exists(rl) and "API planner timed out" in open(rl, errors="ignore").read():
        return "infra_timeout"
    return "policy_fail"


def run_episode(ep, gpu):
    suite, task, seed, cond, repeat = ep["suite"], ep["task"], ep["seed"], ep["cond"], ep["repeat"]
    ts = datetime.datetime.now().strftime("%Y%m%d-%H:%M:%S")
    outdir = os.path.join(PG_DIR, f"{ts}_{cond}_{suite}_t{task}_s{seed}_r{repeat}")
    os.makedirs(outdir, exist_ok=True)
    env = base_env()
    env.update(COND_ENV.get(cond, {}))
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
    result = classify_dir(outdir)
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
    return {"phase": "P0", "gates": {}, "started": False, "existing_recorded": False}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    json.dump(state, open(tmp, "w"))
    os.replace(tmp, STATE_FILE)


def completed_keys():
    """Set of (stage,suite,task,seed,cond,repeat) already recorded."""
    keys = set()
    if os.path.exists(RUNS_CSV):
        for r in csv.DictReader(open(RUNS_CSV)):
            keys.add((r["stage"], r["suite"], int(r["task"]), int(r["seed"]),
                      r["cond"], int(r["repeat"])))
    return keys


def append_run(state, ep, res):
    row = {
        "ts": res["ts"], "stage": ep["stage"], "suite": ep["suite"],
        "task": ep["task"], "seed": ep["seed"], "cond": ep["cond"],
        "repeat": ep["repeat"], "dir": res["dir"], "rc": res["rc"],
        "wall_s": res["wall_s"], "result": res["result"],
    }
    fresh = not os.path.exists(RUNS_CSV)
    with open(RUNS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if fresh:
            w.writeheader()
        w.writerow(row)


def existing_baseline_dir(suite, task, seed):
    """Latest valid standard-named run dir for (suite,task,seed), excluding pg_exp."""
    key = suite.replace("libero_", "")
    cands = sorted(glob.glob(os.path.join(LOGS_DIR, f"????????-??:??:??_libero_{key}_t{task}_s{seed}/")))
    cands = [d for d in cands if "pg_exp" not in d]
    for d in reversed(cands):
        st, term = _states(d)
        if st is not None:
            return d
    return None


# ---------------- phase queue ----------------
def build_phase_episodes(state, done):
    phase = state["phase"]
    eps = []
    if phase == "P0":
        for t in P0_TASKS:
            for sd in range(1, N_EVAL + 1):
                # baseline repeat 1 = existing if recorded, else fresh; repeats 2-3 fresh
                for rep in (1, 2, 3):
                    k = ("P0", P0_SUITE, t, sd, "baseline", rep)
                    if k not in done:
                        eps.append(dict(stage="P0", suite=P0_SUITE, task=t, seed=sd,
                                        cond="baseline", repeat=rep))
                for rep in (1, 2, 3):
                    k = ("P0", P0_SUITE, t, sd, "ours", rep)
                    if k not in done:
                        eps.append(dict(stage="P0", suite=P0_SUITE, task=t, seed=sd,
                                        cond="ours", repeat=rep))
    elif phase == "P1":
        for t in P0_TASKS:
            for sd in range(1, N_EVAL + 1):
                for rep in (1, 2, 3):
                    k = ("P1", P0_SUITE, t, sd, "hardcap", rep)
                    if k not in done:
                        eps.append(dict(stage="P1", suite=P0_SUITE, task=t, seed=sd,
                                        cond="hardcap", repeat=rep))
    elif phase == "P2":
        for suite in P2_SUITES:
            for t in range(10):
                for sd in range(1, N_EVAL + 1):
                    k = ("P2", suite, t, sd, "ours", 1)
                    if k not in done:
                        eps.append(dict(stage="P2", suite=suite, task=t, seed=sd,
                                        cond="ours", repeat=1))
    elif phase == "P3":
        # extra repeats: second ours repeat for P0 tasks, then P2 tasks
        for t in P0_TASKS:
            for sd in range(1, N_EVAL + 1):
                k = ("P3", P0_SUITE, t, sd, "ours", 4)
                if k not in done:
                    eps.append(dict(stage="P3", suite=P0_SUITE, task=t, seed=sd,
                                    cond="ours", repeat=4))
        for suite in P2_SUITES:
            for t in range(10):
                for sd in range(1, N_EVAL + 1):
                    k = ("P3", suite, t, sd, "ours", 2)
                    if k not in done:
                        eps.append(dict(stage="P3", suite=suite, task=t, seed=sd,
                                        cond="ours", repeat=2))
    return eps


def record_existing_baseline(state):
    """Record P0 baseline repeat-1 (existing runs) at startup; P2 baseline at P2 start."""
    done = completed_keys()
    phase = state["phase"]
    if phase == "P0":
        suite, tasks = P0_SUITE, P0_TASKS
    elif phase == "P2":
        suite, tasks = None, None
    else:
        return
    if phase == "P0":
        for t in tasks:
            for sd in range(1, N_EVAL + 1):
                d = existing_baseline_dir(suite, t, sd)
                k = ("P0", suite, t, sd, "baseline", 1)
                if d and k not in done:
                    res = dict(ts=os.path.basename(d.rstrip("/"))[:16], dir=d, rc=0,
                               wall_s=None, result=classify_dir(d))
                    append_run(state, dict(stage="P0", suite=suite, task=t, seed=sd,
                                           cond="baseline", repeat=1), res)
                    log(f"existing baseline P0 {suite} t{t} s{sd} -> {classify_dir(d)}")
    elif phase == "P2":
        for suite in P2_SUITES:
            for t in range(10):
                for sd in range(1, N_EVAL + 1):
                    d = existing_baseline_dir(suite, t, sd)
                    k = ("P2", suite, t, sd, "baseline", 1)
                    if d and k not in done:
                        append_run(state, dict(stage="P2", suite=suite, task=t, seed=sd,
                                               cond="baseline", repeat=1),
                                   dict(ts=os.path.basename(d.rstrip("/"))[:16], dir=d, rc=0,
                                        wall_s=None, result=classify_dir(d)))


# ---------------- workers ----------------
CSV_LOCK = threading.Lock()


class Worker(threading.Thread):
    """One worker: pops episodes off the shared queue, runs, retries infra."""

    def __init__(self, gpu, q, state, shared):
        super().__init__(daemon=True)
        self.gpu = gpu
        self.q = q
        self.state = state
        self.shared = shared  # {"retry": {key: count}, "consec_err": int}

    def run(self):
        while True:
            if now() >= parse_dt(STOP_ENQUEUE):
                break
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


def ep_key(ep):
    return (ep["stage"], ep["suite"], ep["task"], ep["seed"], ep["cond"], ep["repeat"])


# ---------------- status ----------------
def status_loop(stop_evt):
    while not stop_evt.is_set():
        try:
            write_status()
        except Exception:
            pass
        stop_evt.wait(STATUS_INTERVAL)


def write_status():
    done = completed_keys()
    lines = [
        "# 实验状态\n",
        f"_updated {datetime.datetime.now().isoformat(timespec='seconds')}_\n",
        f"window: {FINAL_STOP} (stop-new: {STOP_ENQUEUE})\n",
        f"completed: {len(done)} episodes\n",
        f"gpus idle: {idle_gpus()}\n",
    ]
    # per-condition SR (from runs.csv analyze-dir counts is heavy; use result column)
    if os.path.exists(RUNS_CSV):
        rows = list(csv.DictReader(open(RUNS_CSV)))
        agg = {}
        for r in rows:
            k = (r["stage"], r["cond"])
            agg.setdefault(k, [0, 0])
            agg[k][1] += 1
            if r["result"] == "success":
                agg[k][0] += 1
        lines.append("\n## SR by stage/cond (from result column)\n")
        for k in sorted(agg):
            ok, tot = agg[k]
            lines.append(f"- {k[0]} / {k[1]}: {ok}/{tot} ({ok / max(tot, 1):.0%})\n")
    with open(STATUS_MD, "w") as f:
        f.write("\n".join(lines))


def snapshot(state, label):
    os.makedirs(SNAP_DIR, exist_ok=True)
    p = os.path.join(SNAP_DIR, f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}_{label}.md")
    write_status()
    shutil_copy(STATUS_MD, p)


def shutil_copy(src, dst):
    with open(src) as f:
        data = f.read()
    with open(dst, "w") as f:
        f.write(data)


# ---------------- gating ----------------
def evaluate_gates(state):
    """Import analysis, compute P0 gates, decide P1/P2."""
    try:
        sys.path.insert(0, os.path.join(ROOT, "analysis"))
        import progress_gate_analysis as an
        rows = an.load_runs()
        g = an.gates(rows)
        if g:
            state["gates"]["P0"] = g
            an.write_summary(rows, g)
            log(f"P0 gate: SR ours={g['sr_og']:.0%} baseline={g['sr_bl']:.0%} | "
                f"p1={g['p1']} p2={g['p2']}")
            return g
    except Exception as ex:
        log(f"gate eval failed: {ex}\n{traceback.format_exc()}")
    return None


def advance_phase(state):
    phase = state["phase"]
    if phase == "P0":
        g = evaluate_gates(state)
        if g is None:
            log("P0 gate indeterminate; stopping to avoid blind expansion")
            state["phase"] = "DONE"
        elif g["p1"]:
            log(f"P0 no obvious negative effect (ours {g['sr_og']:.0%} vs base {g['sr_bl']:.0%}); -> P1 hardcap ablation")
            state["phase"] = "P1"
        else:
            log(f"P0 negative effect (ours {g['sr_og']:.0%} < baseline {g['sr_bl']:.0%} - 10pp); stopping")
            state["phase"] = "DONE"
    elif phase == "P1":
        g = evaluate_gates(state)
        if g and g["p2"]:
            log(f"P2 gate met (ours SR {g['sr_og']:.0%} vs base {g['sr_bl']:.0%}, "
                f"turns {g['turns_og']} vs {g['turns_bl']}); -> P2 generalization")
            state["phase"] = "P2"
        else:
            log("P2 gate not met after ablation; stopping")
            state["phase"] = "DONE"
    elif phase == "P2":
        state["phase"] = "P3"
    elif phase == "P3":
        state["phase"] = "DONE"
    save_state(state)
    log(f"phase advanced: {phase} -> {state['phase']}")


def egl_ready():
    """True if a usable libEGL exists (overlay resets often leave 0-byte stubs)."""
    for cand in ("/usr/lib/x86_64-linux-gnu/libEGL.so.1",
                 "/usr/lib/x86_64-linux-gnu/libEGL_mesa.so.0"):
        try:
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                return True
        except OSError:
            pass
    return False


def ensure_egl():
    """Self-heal the GL/EGL stack at startup (same guard as gap_fill.sh)."""
    if egl_ready():
        return
    log("EGL libs missing/empty (overlay reset); reinstalling mesa")
    subprocess.run(
        ["apt-get", "install", "-y", "libegl1", "libegl-mesa0", "libgles2", "libosmesa6"],
        capture_output=True, timeout=300)
    if not egl_ready():
        log("EGL reinstall FAILED; aborting to avoid poisoning runs.csv with infra rows")
        sys.exit(1)


def main():
    ensure_egl()
    os.makedirs(PG_DIR, exist_ok=True)
    os.makedirs(SNAP_DIR, exist_ok=True)
    state = load_state()
    if not state.get("started"):
        state["started"] = True
        state["phase"] = "P0"
        save_state(state)
    log(f"=== Progress Gate scheduler start | phase={state['phase']} "
        f"workers/gpu={WORKERS_PER_GPU} | final={FINAL_STOP} ===")
    stop_evt = threading.Event()
    threading.Thread(target=status_loop, args=(stop_evt,), daemon=True).start()

    while state["phase"] != "DONE":
        if now() >= parse_dt(STOP_ENQUEUE):
            log("stop-enqueue reached; finishing running episodes")
            break
        # wait for a truly idle GPU (never share a busy card)
        gpus = idle_gpus()
        while not gpus and now() < parse_dt(STOP_ENQUEUE):
            log(f"no idle GPU (idle={gpus}); waiting 120s")
            time.sleep(120)
            gpus = idle_gpus()
        if now() >= parse_dt(STOP_ENQUEUE):
            break
        record_existing_baseline(state)
        done = completed_keys()
        eps = build_phase_episodes(state, done)
        if not eps:
            snapshot(state, f"{state['phase']}_empty")
            advance_phase(state)
            continue
        n_workers = len(gpus) * WORKERS_PER_GPU
        q = queue.Queue()
        for e in eps:
            q.put(e)
        log(f"=== {state['phase']}: {q.qsize()} episodes on gpus={gpus} ({n_workers} workers) ===")
        shared = {"retry": {}, "consec_err": 0}
        workers = []
        for gi in gpus:
            for _ in range(WORKERS_PER_GPU):
                workers.append(Worker(gi, q, state, shared))
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        log(f"=== {state['phase']} worker pool drained ===")
        snapshot(state, f"{state['phase']}_done")
        advance_phase(state)

    # final summary
    write_status()
    snapshot(state, "final")
    try:
        sys.path.insert(0, os.path.join(ROOT, "analysis"))
        import progress_gate_analysis as an
        rows = an.load_runs()
        an.write_summary(rows, an.gates(rows))
        an.write_ablation(rows)
        log("final summary written")
    except Exception as ex:
        log(f"final analysis failed: {ex}")
    log("=== scheduler finished ===")


if __name__ == "__main__":
    main()
