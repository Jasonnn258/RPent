#!/bin/bash
# rerun_t37_evals.sh — eval-only re-run for the corrected spatial_task t3/t7.
# The task DEFINITION changed (bowl_2 target, base layout), so EVERY seed 1..10
# must be re-evaluated regardless of the old (swap-variant) run outcomes.
# Usage: bash rerun_t37_evals.sh <task> [<task> ...]   (e.g. "3 7")
set -uo pipefail
export PATH=/vla_test/yjx/miniconda3/envs/vla/bin:$PATH

SCRATCH="/vla_test/yjx/workspace/RPent/.gap_run"
TASKS="${*:-3 7}"
SUITE="libero_spatial_task"
EVAL_TURNS=40
# GPU pool + concurrency (4x V100, 2 workers/GPU is the memory ceiling): all GPUs by default.
GPU_SUBSET="${GPU_SUBSET:-0 1 2 3}"
WORKERS_PER_GPU="${WORKERS_PER_GPU:-2}"
# Optional seed filter (space-separated); empty = all seeds 1..10.
SEEDS="${SEEDS:-}"
export PI05_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/pi05
export SAM3_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/sam3/sam3.pt
export ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro
export OPENPI_DATA_HOME=/vla_test/yjx/rpent_data/.cache/openpi
export LIBERO_CONFIG_PATH=/vla_test/yjx/rpent_data/.libero
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4
export ANTHROPIC_API_KEY=$(grep "^DW_KEY=" /vla_test/yjx/rpent_data/rpent_env.sh | cut -d= -f2-)
P_MODEL="anthropic:kimi-k3"; P_BASE="--base-url https://dwai-data.shizhuang-inc.com/anthropic"; P_IMG=""
PLANNER_TIMEOUT_S=2400
LOGS_DIR="/vla_test/yjx/workspace/RPent/logs"
LOG="$SCRATCH/t37e.log"

run_one() {
    local task=$1 seed=$2 turns=$3 gpu=$4
    local key="${SUITE#libero_}" dir rtmp cvd
    rtmp="$SCRATCH/rt37e_${key}_t${task}_s${seed}_g${gpu}.log"
    # robosuite maps CUDA_VISIBLE_DEVICES -> EGL device; software EGL has only dev 0.
    # Keep 0 visible so MUJOCO_EGL_DEVICE_ID=0 passes the assertion, no "0,0" dup.
    [ "$gpu" = "0" ] && cvd="0" || cvd="$gpu,0"
    echo "[$(date '+%T')] gpu$gpu $SUITE t$task s$seed turns=$turns" >> "$LOG"
    timeout 4500 env CUDA_VISIBLE_DEVICES="$cvd" MUJOCO_GL=egl MUJOCO_EGL_DEVICE_ID=0 LIBGL_ALWAYS_SOFTWARE=1 \
      OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4 \
      ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
      PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
      ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
      OPENPI_DATA_HOME="$OPENPI_DATA_HOME" LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" HF_HUB_OFFLINE=1 \
      rpent --env libero --suite "$SUITE" --task "$task" --seed "$seed" \
        --planner api --model "$P_MODEL" ${P_BASE} \
        --planner-timeout-s "$PLANNER_TIMEOUT_S" --max-turns "$turns" ${P_IMG} >"$rtmp" 2>&1
    echo "[$(date '+%T')] gpu$gpu $SUITE t$task s$seed rc=$?" >> "$LOG"
    dir=$(ls -td "$LOGS_DIR"/*_${key}_t${task}_s${seed}/ 2>/dev/null | head -1)
    echo "$dir"
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

latest_dir() { local t=$1 sd=$2 k="${SUITE#libero_}"; ls -td "$LOGS_DIR"/*_${k}_t${t}_s${sd}/ 2>/dev/null | head -1; }

WORK_Q="$SCRATCH/t37e_queue.txt"; Q_LOCK="$SCRATCH/t37e_q.lock"
take_item() {
    (
        flock 9
        if [ -s "$WORK_Q" ]; then head -1 "$WORK_Q"; sed -i '1d' "$WORK_Q"; fi
    ) 9>"$Q_LOCK"
}
enqueue() { echo "$@" >> "$WORK_Q"; }

worker() {
    local gpu=$1 item s t sd kind d r
    while true; do
        item=$(take_item); [ -z "$item" ] && break
        read -r s t sd kind <<< "$item"
        d=$(run_one "$t" "$sd" "$EVAL_TURNS" "$gpu"); r=$(classify "$d")
        echo "$(date '+%T')|$SUITE|$t|$sd|eval|$r|$d" >> "$SCRATCH/t37e_evals.csv"
        echo "[$(date '+%T')][w:gpu$gpu] $SUITE t$t s$sd done: $r" >> "$LOG"
    done
}

echo "=== rerun_t37_evals start $(date '+%F %T') | tasks=$TASKS gpus=[$GPU_SUBSET] ===" >> "$LOG"
: > "$WORK_Q"
[ -f "$SCRATCH/t37e_evals.csv" ] || echo "ts|suite|task|seed|kind|result|dir" > "$SCRATCH/t37e_evals.csv"
for t in $TASKS; do
    if [ -n "$SEEDS" ]; then
        for s in $SEEDS; do enqueue "$SUITE" "$t" "$s" eval; done
    else
        for s in $(seq 1 10); do enqueue "$SUITE" "$t" "$s" eval; done
    fi
done
pids=()
for g in $GPU_SUBSET; do
    for _i in $(seq 1 "$WORKERS_PER_GPU"); do worker "$g" & pids+=($!); done
done
for p in "${pids[@]}"; do wait "$p"; done
echo "=== rerun_t37_evals DONE $(date '+%F %T') ===" >> "$LOG"
for t in $TASKS; do
    pass=0; total=0
    for s in $(seq 1 10); do
        total=$((total+1)); c=$(classify "$(latest_dir "$t" "$s")")
        [ "$c" = "success" ] && pass=$((pass+1))
    done
    echo "TASK $t eval: $pass/$total"
done
