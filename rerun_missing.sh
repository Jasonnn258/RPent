#!/bin/bash
# rerun_missing.sh — after the current harness batch finishes, re-run the
# tasks whose seed0 bootstrap failed (skipped by the auto-harness) using the
# FIXED prompt (Rule 2e perception budget) + 2400s planner timeout.
#
# Targets: libero_goal_task t0,t3,t6 ; libero_goal_swap t0
# Run (background): nohup bash rerun_missing.sh >/dev/null 2>&1 &
set -uo pipefail

export PATH=/vla_test/yjx/miniconda3/envs/vla/bin:$PATH

# ---- dev-machine preflight + singleton lock ----
source /workspace/yjx/bin/dev_preflight.sh
preflight_lock rerun_missing || exit 1

# ---- env (same as harness_auto.sh) ----
PLANNER=kimi
N_EVAL=10
BOOT_TURNS=60
EVAL_TURNS=40
export PI05_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/pi05
export SAM3_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/sam3/sam3.pt
export ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro
export OPENPI_DATA_HOME=/vla_test/yjx/rpent_data/.cache/openpi
export LIBERO_CONFIG_PATH=/vla_test/yjx/rpent_data/.libero
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=8 TORCHINDUCTOR_COMPILE_WORKERS=8
LOGS_DIR="/vla_test/yjx/workspace/RPent/logs"
REPORT="/vla_test/yjx/workspace/RPent/logs/rerun_report.jsonl"
RES_BASE="/vla_test/yjx/workspace/RPent/resources/libero"
export ANTHROPIC_API_KEY=$(grep "^DW_KEY=" /vla_test/yjx/rpent_data/rpent_env.sh | cut -d= -f2-)
P_MODEL="anthropic:kimi-k3"; P_BASE="--base-url https://dwai-data.shizhuang-inc.com/anthropic"; P_IMG=""
PLANNER_TIMEOUT_S=2400

# ---- helpers (copied from harness_auto.sh) ----
run_one() {
    local suite=$1 task=$2 seed=$3 turns=$4
    cd /vla_test/yjx/workspace/RPent
    xvfb-run -a -s "-screen 0 640x480x24" \
      env MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 OMP_NUM_THREADS=8 TORCHINDUCTOR_COMPILE_WORKERS=8 \
      ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
      PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
      ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
      OPENPI_DATA_HOME="$OPENPI_DATA_HOME" LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" HF_HUB_OFFLINE=1 \
      rpent --env libero --suite "$suite" --task "$task" --seed "$seed" \
        --planner api --model "$P_MODEL" ${P_BASE} \
        --planner-timeout-s "$PLANNER_TIMEOUT_S" \
        --max-turns "$turns" ${P_IMG} >/dev/null 2>&1
    local key="${suite#libero_}"
    ls -td "$LOGS_DIR"/*_${key}_t${task}_s${seed}/ 2>/dev/null | head -1
}

check_ok() {
    local dir=$1
    [ -f "$dir/states.json" ] || return 1
    /vla_test/yjx/miniconda3/envs/vla/bin/python -c "
import json,sys
st=json.load(open('$dir/states.json'))
sys.exit(0 if (st and st[-1].get('libero_terminated')) else 1)"
}

store_memory() {
    local suite=$1 task=$2 dir=$3
    local key="${suite#libero_}" res="$RES_BASE/results_${key}_pert"
    mkdir -p "$res"
    for f in "$dir"/*.json; do
        [ -f "$f" ] || continue
        case "$(basename "$f")" in ${key}_t${task}_s0.json|*_t${task}_s0.json) cp "$f" "$res/$(basename "$f")";; esac
    done
    for r in "$dir"/recipe_*.jsonl; do [ -f "$r" ] && cp "$r" "$res/$(basename "$r")"; done
}

process_task() {
    local suite=$1 task=$2 key="${1#libero_}" d turns
    echo ""
    echo "########## RERUN SUITE=$suite TASK=$task ##########"
    d=$(run_one "$suite" "$task" 0 "$BOOT_TURNS")
    if [ -z "$d" ] || ! check_ok "$d"; then
        echo "  bootstrap failed at $BOOT_TURNS; retrying at 100 turns"
        d=$(run_one "$suite" "$task" 0 100)
    fi
    if [ -z "$d" ] || ! check_ok "$d"; then
        echo "  BOOTSTRAP FAILED task=$task"
        echo "{\"suite\":\"$suite\",\"task\":$task,\"bootstrap\":\"FAIL\",\"pass\":0,\"total\":0}" >> "$REPORT"
        return
    fi
    echo "  bootstrap SUCCESS task=$task"
    store_memory "$suite" "$task" "$d"
    local pass=0 total=0 pids=() running=0
    for s in $(seq 1 "$N_EVAL"); do
        ( d2=$(run_one "$suite" "$task" "$s" "$EVAL_TURNS") ) &
        pids+=($!); running=$((running+1))
        if [ "$running" -ge 2 ]; then wait "${pids[0]}"; running=$((running-1)); pids=("${pids[@]:1}"); fi
    done
    for p in "${pids[@]}"; do wait "$p"; done
    for s in $(seq 1 "$N_EVAL"); do
        d2=$(ls -td "$LOGS_DIR"/*_${key}_t${task}_s${s}/ 2>/dev/null | head -1)
        total=$((total+1))
        if [ -n "$d2" ] && check_ok "$d2"; then pass=$((pass+1)); fi
    done
    echo "  TASK $task RESULT: $pass/$total (seed1..$N_EVAL)"
    echo "{\"suite\":\"$suite\",\"task\":$task,\"bootstrap\":\"OK\",\"pass\":$pass,\"total\":$total}" >> "$REPORT"
}

# ---- wait for the current harness batch to finish (no active rpent) ----
echo "=== waiting for current batch to finish ... $(date '+%H:%M') ==="
WAITED=0
while ps aux | grep -q "[r]pent --env"; do
    sleep 60; WAITED=$((WAITED+60))
    if [ $((WAITED % 600)) -eq 0 ]; then echo "  ...still waiting ($((WAITED/60)) min)"; fi
done
echo "=== batch finished at $(date '+%H:%M'); starting reruns ==="

# ---- rerun the bootstrap-failed tasks ----
process_task libero_goal_task 0
process_task libero_goal_task 3
process_task libero_goal_task 6
process_task libero_goal_swap 0

echo ""
echo "=========== RERUNS DONE. Report: $REPORT ==========="
cat "$REPORT"
