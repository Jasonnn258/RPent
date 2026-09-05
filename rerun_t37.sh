#!/bin/bash
# rerun_t37.sh — re-run spatial_task t3/t7 with the CORRECTED task definitions.
# The earlier swap-file fix changed the task (bowl_1 target + swapped layout).
# The reconstructed files restore the intended P1-task variant (bowl_2 target,
# base-like layout) validated against the pre-corruption broken bddl backups.
# Bootstrap (s0) + 10 evals per task, concurrency 2 on the shared GPU.
# Run (background): nohup bash rerun_t37.sh >> .gap_run/t37_super.log 2>&1 &
set -uo pipefail
export PATH=/vla_test/yjx/miniconda3/envs/vla/bin:$PATH

# ---- dev-machine preflight + singleton lock ----
source /workspace/yjx/bin/dev_preflight.sh
preflight_lock rerun_t37 || exit 1

SCRATCH="/vla_test/yjx/workspace/RPent/.gap_run"; mkdir -p "$SCRATCH"
PLANNER=kimi; N_EVAL=10; BOOT_TURNS=60; EVAL_TURNS=40
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
P_MODEL="anthropic:kimi-k3"; P_BASE="--base-url https://dwai-data.shizhuang-inc.com/anthropic"; P_IMG=""
PLANNER_TIMEOUT_S=2400
SUITE="libero_spatial_task"
TASKS="3 7"
GPU="0"
CSV="$LOGS_DIR/t37_rerun.csv"
REPORT="$SCRATCH/t37_rerun_report.jsonl"
LOG="$SCRATCH/t37.log"

run_one() {
    local task=$1 seed=$2 turns=$3
    local key="${SUITE#libero_}" dir rtmp cvd
    rtmp="$SCRATCH/rt37_${key}_t${task}_s${seed}.log"
    [ "$GPU" = "0" ] && cvd="0" || cvd="$GPU,0"
    echo "[$(date '+%T')] gpu$GPU $SUITE t$task s$seed turns=$turns" >> "$LOG"
    timeout 4500 env CUDA_VISIBLE_DEVICES="$cvd" MUJOCO_GL=egl MUJOCO_EGL_DEVICE_ID=0 LIBGL_ALWAYS_SOFTWARE=1 \
      OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4 \
      ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
      PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
      ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
      OPENPI_DATA_HOME="$OPENPI_DATA_HOME" LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" HF_HUB_OFFLINE=1 \
      xvfb-run -a -s "-screen 0 640x480x24" \
      rpent --env libero --suite "$SUITE" --task "$task" --seed "$seed" \
        --planner api --model "$P_MODEL" ${P_BASE} \
        --planner-timeout-s "$PLANNER_TIMEOUT_S" --max-turns "$turns" ${P_IMG} >"$rtmp" 2>&1
    echo "[$(date '+%T')] gpu$GPU $SUITE t$task s$seed rc=$? rtmp=$rtmp" >> "$LOG"
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

store_memory() {
    local task=$1 dir=$2 key res
    key="${SUITE#libero_}"; res="$RES_BASE/results_${key}_pert"
    mkdir -p "$res"
    for f in "$dir"/*.json; do [ -f "$f" ] || continue; case "$(basename "$f")" in ${key}_t${task}_s0.json|*_t${task}_s0.json) cp "$f" "$res/$(basename "$f")";; esac; done
    for r in "$dir"/recipe_*.jsonl; do [ -f "$r" ] && cp "$r" "$res/$(basename "$r")"; done
}

worker() {
    local item s t sd kind d r
    while true; do
        item=$(take_item); [ -z "$item" ] && break
        read -r s t sd kind <<< "$item"
        echo "[$(date '+%T')][w] $kind $s t$t s$sd" >> "$LOG"
        if [ "$kind" = "bootstrap" ]; then
            d=$(run_one "$t" 0 "$BOOT_TURNS"); r=$(classify "$d")
            if [ "$r" != "success" ]; then d=$(run_one "$t" 0 100); r=$(classify "$d"); fi
            echo "$(date '+%T'),$s,$t,0,bootstrap,$r" >> "$CSV"
            if [ "$r" = "success" ]; then
                store_memory "$t" "$d"
                for ss in $(seq 1 "$N_EVAL"); do
                    c=$(classify "$(latest_dir "$t" "$ss")")
                    [ "$c" != "success" ] && [ "$c" != "policy_fail" ] && enqueue "$s" "$t" "$ss" eval
                done
            fi
        else
            d=$(run_one "$t" "$sd" "$EVAL_TURNS"); r=$(classify "$d")
            echo "$(date '+%T'),$s,$t,$sd,eval,$r" >> "$CSV"
        fi
        echo "[$(date '+%T')][w] $s t$t s$sd done: $r" >> "$LOG"
    done
}

WORK_Q="$SCRATCH/t37_queue.txt"; Q_LOCK="$SCRATCH/t37_q.lock"
take_item() {
    (
        flock 9
        if [ -s "$WORK_Q" ]; then head -1 "$WORK_Q"; sed -i '1d' "$WORK_Q"; fi
    ) 9>"$Q_LOCK"
}
enqueue() { echo "$@" >> "$WORK_Q"; }

echo "=== rerun_t37 start $(date '+%F %T') | $SUITE $TASKS | concurrency 2 ===" >> "$LOG"
: > "$WORK_Q"; [ -f "$CSV" ] || echo "ts,suite,task,seed,kind,result" > "$CSV"
for t in $TASKS; do enqueue "$SUITE" "$t" 0 bootstrap; done
# 2 concurrent workers
worker & p1=$!
worker & p2=$!
wait $p1 $p2
echo "=== rerun_t37 DONE $(date '+%F %T') ===" >> "$LOG"
for t in $TASKS; do
    c0=$(classify "$(latest_dir "$t" 0)")
    pass=0; total=0
    for s in $(seq 1 "$N_EVAL"); do
        total=$((total+1)); c=$(classify "$(latest_dir "$t" "$s")")
        [ "$c" = "success" ] && pass=$((pass+1))
    done
    echo "TASK $t: bootstrap=$c0 eval=$pass/$total"
    echo "{\"suite\":\"$SUITE\",\"task\":$t,\"bootstrap\":\"$c0\",\"pass\":$pass,\"total\":$total}" >> "$REPORT"
done
