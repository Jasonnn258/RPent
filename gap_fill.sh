#!/bin/bash
# gap_fill.sh v4 — fully concurrent GPU-aware gap filler for RPent.
# 4x V100 32GB: one worker per GPU. Bootstrap + eval ALL flow through a shared
# worker pool -> 4 GPUs saturated, Kimi API latency hidden by parallelism.
# P1: fill gaps in libero_spatial / libero_goal_task / libero_goal_swap.
# P2: if time remains, libero_spatial_task + libero_spatial_swap.
# Records: logs/gap_fill.csv, logs/gap_fill.md
# Usage: nohup bash gap_fill.sh >> "$SCRATCH/gap_fill.log" 2>&1 &
set -o pipefail

export PATH=/vla_test/yjx/miniconda3/envs/vla/bin:$PATH

# Runtime scratch (queue/locks/logs) lives in the repo, NOT /tmp: a tmp cleaner
# wiped /tmp once mid-run and silently killed the whole batch (WORK_Q vanished ->
# workers all exit empty). Keep it durable.
SCRATCH="${SCRATCH:-/vla_test/yjx/workspace/RPent/.gap_run}"; mkdir -p "$SCRATCH"
PLANNER=kimi; N_EVAL=10; BOOT_TURNS=60; EVAL_TURNS=40
DEADLINE="2026-08-14 20:00"
FINAL_STOP="${FINAL_STOP:-2026-08-14 20:00}"     # no new episode after this (local time)
STOP_EPOCH=$(date -d "$FINAL_STOP" +%s)
P1_SUITES="libero_spatial libero_goal_task libero_goal_swap"
P2_SUITES="libero_spatial_task libero_spatial_swap"
N_GPU=$(nvidia-smi -L 2>/dev/null | wc -l); N_GPU=${N_GPU:-4}
# GPU subset comes from a side-file so the ablation can hand GPUs back:
#  "0 1" during t9 ablation, then "0 1 2 3" after it finishes.
GPU_CONFIG_FILE="${GPU_CONFIG_FILE:-$SCRATCH/gpu_config}"
GPU_SUBSET=$(cat "$GPU_CONFIG_FILE" 2>/dev/null || echo "")
[ -z "$GPU_SUBSET" ] && GPU_SUBSET=$(seq -s ' ' 0 $((N_GPU-1)))
# WORKERS_PER_GPU: each GPU hosts multiple workers (A800 80GB fits ~2-3; Kimi
# API latency is the real bottleneck, so more workers hide the wait).
WORKERS_PER_GPU="${WORKERS_PER_GPU:-2}"
_expanded=""
for _g in $GPU_SUBSET; do
    for _i in $(seq 1 "$WORKERS_PER_GPU"); do _expanded="$_expanded $_g"; done
done
GPU_SUBSET="$(echo $_expanded | xargs)"
MAX_CONC=$(echo "$GPU_SUBSET" | wc -w)
export PI05_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/pi05
export SAM3_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/sam3/sam3.pt
export ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro
export OPENPI_DATA_HOME=/vla_test/yjx/rpent_data/.cache/openpi
export LIBERO_CONFIG_PATH=/vla_test/yjx/rpent_data/.libero
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4
LOGS_DIR="/vla_test/yjx/workspace/RPent/logs"
RES_BASE="/vla_test/yjx/workspace/RPent/resources/libero"
export ANTHROPIC_API_KEY=$(grep "^DW_KEY=" /vla_test/yjx/rpent_data/rpent_env.sh | cut -d= -f2-)
P_MODEL="anthropic:kimi-k3"; P_BASE="--base-url https://dwai-data.shizhuang-inc.com/anthropic"; P_IMG=""; PLANNER_TIMEOUT_S=2400
LOCKROOT="$SCRATCH/locks"; mkdir -p "$LOCKROOT"; rm -f "$LOCKROOT"/*.lock  # clear stale locks (orphan flock from a killed run)
WORK_Q="$SCRATCH/work_queue.txt"; Q_LOCK="$SCRATCH/q.lock"
CSV="$LOGS_DIR/gap_fill.csv"

# self-healing (overlay reset guard)
if [ ! -s /usr/lib/x86_64-linux-gnu/libEGL.so.1 ] || [ "$(stat -c%s /usr/lib/x86_64-linux-gnu/libEGL.so.1 2>/dev/null || echo 0)" = "0" ] || ! command -v xvfb-run >/dev/null 2>&1; then
    echo "[setup] reinstalling mesa + xvfb ..."
    apt-get install -y libegl1 libegl-mesa0 libgles2 libosmesa6 xvfb >/dev/null 2>&1
fi
LP="/vla_test/yjx/miniconda3/envs/vla/lib/python3.11/site-packages"
[ -e "$LP/libero/libero/assets" ] || ln -sfn "$LP/liberopro/liberopro/assets" "$LP/libero/libero/assets"

echo "=== gap_fill v4 start $(date '+%F %T') | GPU=$N_GPU conc=$MAX_CONC | deadline=$DEADLINE ==="
mkdir -p "$LOGS_DIR"; [ -f "$CSV" ] || echo "ts,suite,task,seed,kind,result" > "$CSV"

# ---------------- helpers ----------------
run_one() {
    local suite=$1 task=$2 seed=$3 turns=$4 gpu=$5
    local key="${suite#libero_}" dir rtmp cvd
    rtmp="$SCRATCH/runtmp_${key}_t${task}_s${seed}_g${gpu}.log"
    # robosuite maps CUDA_VISIBLE_DEVICES -> EGL device; software EGL has only dev 0.
    # Keep 0 visible so MUJOCO_EGL_DEVICE_ID=0 passes robosuite's assertion, but do NOT
    # duplicate it (torch "0,0" => invalid device ordinal). torch cuda:0 = physical $gpu.
    [ "$gpu" = "0" ] && cvd="0" || cvd="$gpu,0"
    # No flock: workers are fixed-allocated to GPUs by the pool; same-GPU workers
    # must run concurrently (A800 80GB hosts multiple) — a lock would serialize them.
    echo "[$(date '+%T')] gpu$gpu $suite t$task s$seed turns=$turns" >> "$SCRATCH/gap_fill.log"
    timeout 4500 env CUDA_VISIBLE_DEVICES="$cvd" MUJOCO_GL=egl MUJOCO_EGL_DEVICE_ID=0 LIBGL_ALWAYS_SOFTWARE=1 \
      OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4 \
      ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
      PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
      ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
      OPENPI_DATA_HOME="$OPENPI_DATA_HOME" LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" HF_HUB_OFFLINE=1 \
      xvfb-run -a -s "-screen 0 640x480x24" \
      rpent --env libero --suite "$suite" --task "$task" --seed "$seed" \
        --planner api --model "$P_MODEL" ${P_BASE} \
        --planner-timeout-s "$PLANNER_TIMEOUT_S" --max-turns "$turns" ${P_IMG} >"$rtmp" 2>&1
    echo "[$(date '+%T')] gpu$gpu $suite t$task s$seed rc=$? rtmp=$rtmp" >> "$SCRATCH/gap_fill.log"
    dir=$(ls -td "$LOGS_DIR"/*_${key}_t${task}_s${seed}/ 2>/dev/null | head -1)
    echo "$dir"
}

check_ok() { local d=$1; [ -f "$d/states.json" ] || return 1; /vla_test/yjx/miniconda3/envs/vla/bin/python -c "
import json,sys; st=json.load(open('$d/states.json'))
sys.exit(0 if (st and st[-1].get('libero_terminated')) else 1)"; }

store_memory() {
    local suite=$1 task=$2 dir=$3 key="${suite#libero_}" res="$RES_BASE/results_${key}_pert"
    mkdir -p "$res"
    for f in "$dir"/*.json; do [ -f "$f" ] || continue; case "$(basename "$f")" in ${key}_t${task}_s0.json|*_t${task}_s0.json) cp "$f" "$res/$(basename "$f")";; esac; done
    for r in "$dir"/recipe_*.jsonl; do [ -f "$r" ] && cp "$r" "$res/$(basename "$r")"; done
}

classify() {
    local d=$1
    [ -n "$d" ] || { echo missing; return; }
    [ -f "$d/states.json" ] || { echo infra_crash; return; }
    if /vla_test/yjx/miniconda3/envs/vla/bin/python -c "
import json,sys; st=json.load(open('$d/states.json'))
sys.exit(0 if (st and st[-1].get('libero_terminated')) else 1)" 2>/dev/null; then echo success; return; fi
    if [ -f "$d/run.log" ] && grep -q "API planner timed out" "$d/run.log" 2>/dev/null; then echo infra_timeout; return; fi
    echo policy_fail
}

latest_dir() { local s=$1 t=$2 sd=$3 k; k="${s#libero_}"; ls -td "$LOGS_DIR"/*_${k}_t${t}_s${sd}/ 2>/dev/null | head -1; }

gpu_used() { nvidia-smi -i "$1" --query-gpu=memory.used --format=csv,noheader 2>/dev/null | grep -oE '[0-9]+' | head -1; }
gpu_free() { local u; u=$(gpu_used "$1"); [ -n "$u" ] && [ "$u" -lt 2000 ]; }
pick_gpu() { for g in $(seq 0 $((N_GPU-1))); do gpu_free "$g" && { echo "$g"; return 0; }; done; echo 0; }

past_deadline() { [ "$(date +%s)" -ge "$(date -d "$DEADLINE" +%s)" ]; }

# thread-safe queue pop: prints the item (or empty), removes it atomically
take_item() {
    (
        flock 9
        if [ -s "$WORK_Q" ]; then
            head -1 "$WORK_Q"
            sed -i '1d' "$WORK_Q"
        fi
    ) 9>"$Q_LOCK"
}
enqueue() { echo "$@" >> "$WORK_Q"; }

# ---------------- worker ----------------
worker() {
    local gpu=$1 item s t sd kind d r
    while true; do
        past_deadline && break
        # final-window: no new episodes after FINAL_STOP; bootstrap needs 30min,
        # eval 15min before the stop so episodes can finish in time.
        if [ "$(date +%s)" -ge "$STOP_EPOCH" ]; then echo "[$(date '+%T')] final window passed ($FINAL_STOP)" >> "$SCRATCH/gap_fill.log"; break; fi
        item=$(take_item); [ -z "$item" ] && break
        read -r s t sd kind <<< "$item"
        now=$(date +%s)
        if [ "$kind" = "bootstrap" ] && [ "$now" -ge "$((STOP_EPOCH - 1800))" ]; then
            echo "[$(date '+%T')] skip bootstrap (won't finish before $FINAL_STOP)" >> "$SCRATCH/gap_fill.log"; continue
        fi
        if [ "$kind" = "eval" ] && [ "$now" -ge "$((STOP_EPOCH - 900))" ]; then
            echo "[$(date '+%T')] skip eval (won't finish before $FINAL_STOP)" >> "$SCRATCH/gap_fill.log"; continue
        fi
        echo "[$(date '+%T')][gpu$gpu] $kind $s t$t s$sd" >> "$SCRATCH/gap_fill.log"
        if [ "$kind" = "bootstrap" ]; then
            d=$(run_one "$s" "$t" 0 "$BOOT_TURNS" "$gpu"); r=$(classify "$d")
            if [ "$r" != "success" ]; then
                d=$(run_one "$s" "$t" 0 100 "$gpu"); r=$(classify "$d")
            fi
            echo "$(date '+%T'),$s,$t,0,bootstrap,$r" >> "$CSV"
            if [ "$r" = "success" ]; then
                store_memory "$s" "$t" "$d"
                local ss c
                for ss in $(seq 1 "$N_EVAL"); do
                    c=$(classify "$(latest_dir "$s" "$t" "$ss")")
                    [ "$c" != "success" ] && [ "$c" != "policy_fail" ] && enqueue "$s" "$t" "$ss" eval
                done
            fi
        else
            d=$(run_one "$s" "$t" "$sd" "$EVAL_TURNS" "$gpu"); r=$(classify "$d")
            echo "$(date '+%T'),$s,$t,$sd,eval,$r" >> "$CSV"
        fi
        echo "[$(date '+%T')][gpu$gpu] $s t$t s$sd done: $r" >> "$SCRATCH/gap_fill.log"
    done
}

spawn_pool() {
    local g pids=()
    # fixed allocation: one worker per GPU_SUBSET entry (already expanded by
    # WORKERS_PER_GPU). No gpu_free check — A800 80GB hosts multiple workers.
    for g in $GPU_SUBSET; do
        worker "$g" & pids+=($!)
    done
    for p in "${pids[@]}"; do wait "$p"; done
}

# ---------------- detect gaps (P1) ----------------
echo "=== detecting gaps ==="
: > "$WORK_Q"
for suite in $P1_SUITES; do
  /vla_test/yjx/miniconda3/envs/vla/bin/python - "$suite" "$LOGS_DIR" >> "$WORK_Q" <<'PY'
import os, re, glob, sys, json
suite, logs = sys.argv[1], sys.argv[2]
def latest(s, t, sd):
    k = s.replace("libero_","")
    d = glob.glob(f"{logs}/*_{k}_t{t}_s{sd}/")
    return sorted(d)[-1] if d else ""
def classify(d):
    if not d: return "missing"
    sf = os.path.join(d, "states.json")
    if not os.path.exists(sf): return "infra_crash"
    try:
        st = json.load(open(sf))
        if st and st[-1].get("libero_terminated"): return "success"
    except: return "infra_crash"
    rl = os.path.join(d, "run.log")
    if os.path.exists(rl):
        txt = open(rl, errors="ignore").read()
        if "API planner timed out" in txt: return "infra_timeout"
        if "reached max_turns" in txt: return "policy_fail"
    return "policy_fail"
for task in range(10):
    s0 = classify(latest(suite, task, 0))
    if s0 == "success":
        for s in range(1, 11):
            c = classify(latest(suite, task, s))
            if c in ("missing","infra_crash","infra_timeout"):
                print(f"{suite} {task} {s} eval")
    elif s0 in ("infra_crash","infra_timeout","missing"):
        print(f"{suite} {task} 0 bootstrap")
PY
done
echo "=== P1 work queue: $(wc -l < "$WORK_Q") items ==="
spawn_pool
echo "=== P1 done $(date '+%T') ==="

# ---------------- P2: extend if time ----------------
if ! past_deadline; then
    echo "=== P2: $P2_SUITES ==="
    for suite in $P2_SUITES; do
        for t in 0 1 2 3 4 5 6 7 8 9; do
            past_deadline && { echo "[deadline] stop"; break 2; }
            c0=$(classify "$(latest_dir "$suite" "$t" 0)")
            if [ "$c0" = "success" ]; then
                # bootstrap already OK: enqueue only missing/infra evals
                for ss in $(seq 1 "$N_EVAL"); do
                    c=$(classify "$(latest_dir "$suite" "$t" "$ss")")
                    [ "$c" != "success" ] && [ "$c" != "policy_fail" ] && enqueue "$suite" "$t" "$ss" eval
                done
            elif [ "$c0" = "policy_fail" ]; then
                echo "  skip $suite t$t (bootstrap policy_fail, not re-run)"
            else
                enqueue "$suite" "$t" 0 bootstrap
            fi
        done
    done
    echo "=== P2 work queue: $(wc -l < "$WORK_Q") items ==="
    spawn_pool
else echo "=== no time for P2 ==="; fi

echo "=== gap_fill DONE $(date '+%F %T') ==="
