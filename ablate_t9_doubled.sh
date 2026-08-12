#!/bin/bash
# ablate_t9_doubled.sh — causal ablation for t9: force placement via pi0_doubled.
# Baseline = existing t9 eval results (no forced doubled). This script runs the
# SAME t9 eval seeds (1..10, 40 turns) with RPENT_FORCE_DOUBLED=1 (release ->
# pi0_doubled via task language). No prompt / perception / budget change.
# Usage: bash ablate_t9_doubled.sh <seed_lo> <seed_hi> [gpu0 gpu1 ...]
set -o pipefail
export PATH=/hw-tbo/yjx/miniconda3/envs/vla/bin:$PATH

SEED_LO=${1:-1}; SEED_HI=${2:-10}; shift 2
GPUS=("$@"); [ ${#GPUS[@]} -eq 0 ] && GPUS=(0 1 2 3)
N_EVAL=10; EVAL_TURNS=40
export PI05_CHECKPOINT_PATH=/hw-tbo/yjx/checkpoints/RLinf-Pi05-LIBERO-130-fullshot-SFT
export SAM3_CHECKPOINT_PATH=/hw-tbo/yjx/checkpoints/sam3/sam3.pt
export ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro
export OPENPI_DATA_HOME=/hw-tbo/yjx/.cache/openpi
export LIBERO_CONFIG_PATH=/hw-tbo/yjx/.libero
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4
export ANTHROPIC_API_KEY=$(grep "^DW_KEY=" /hw-tbo/yjx/workspace/commodity-attribute/configs/config.env | cut -d= -f2-)
P_MODEL="anthropic:kimi-k3"; P_BASE="--base-url https://dwai-data.shizhuang-inc.com/anthropic"; P_IMG=""; PLANNER_TIMEOUT_S=2400
LOGS_DIR="/hw-tbo/yjx/workspace/RPent/logs"
SUITE="libero_goal_swap"
ABL_CSV="/hw-tbo/yjx/workspace/RPent/analysis/t9_pi0_doubled_ablation.csv"
[ -f "$ABL_CSV" ] || echo "ts,suite,task,seed,result,forced_doubled_calls,turns" > "$ABL_CSV"

# self-heal
if [ ! -s /usr/lib/x86_64-linux-gnu/libEGL.so.1 ] || ! command -v xvfb-run >/dev/null 2>&1; then
    apt-get install -y libegl1 libegl-mesa0 libgles2 libosmesa6 xvfb >/dev/null 2>&1
fi

run_t9_eval() {
    local seed=$1 gpu=$2 key="goal_swap" rtmp dir r
    rtmp="/tmp/abl_t9_s${seed}_g${gpu}.log"
    # RPENT_FORCE_DOUBLED=1 -> release routes to pi0_doubled
    timeout 4500 env CUDA_VISIBLE_DEVICES="$gpu,0" MUJOCO_GL=egl MUJOCO_EGL_DEVICE_ID=0 LIBGL_ALWAYS_SOFTWARE=1 \
      RPENT_FORCE_DOUBLED=1 OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4 \
      ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
      PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
      ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
      OPENPI_DATA_HOME="$OPENPI_DATA_HOME" LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" HF_HUB_OFFLINE=1 \
      xvfb-run -a -s "-screen 0 640x480x24" \
      rpent --env libero --suite "$SUITE" --task 9 --seed "$seed" \
        --planner api --model "$P_MODEL" ${P_BASE} \
        --planner-timeout-s "$PLANNER_TIMEOUT_S" --max-turns "$EVAL_TURNS" ${P_IMG} >"$rtmp" 2>&1
    dir=$(ls -td "$LOGS_DIR"/*_${key}_t9_s${seed}/ 2>/dev/null | head -1)
    # classify
    r="missing"
    if [ -n "$dir" ] && [ -f "$dir/states.json" ]; then
        if /hw-tbo/yjx/miniconda3/envs/vla/bin/python -c "
import json,sys; st=json.load(open('$dir/states.json'))
sys.exit(0 if (st and st[-1].get('libero_terminated')) else 1)" 2>/dev/null; then r="success"; else r="fail"; fi
    fi
    # count forced_doubled: number of [tool>] release calls (routed to pi0_doubled)
    fd=$(grep -cE "\[tool>\] release" "$dir"run.log 2>/dev/null || echo 0)
    turns=$(grep -cE "=== turn " "$dir"run.log 2>/dev/null || echo 0)
    echo "$(date '+%T'),$SUITE,9,$seed,$r,$fd,$turns" >> "$ABL_CSV"
    echo "[abl gpu$gpu] t9 s$seed -> $r (forced_doubled=$fd)"
}

echo "=== t9 ablation: forced pi0_doubled, seeds $SEED_LO..$SEED_HI, gpus ${GPUS[*]} ==="
# worker pool: one per GPU, pull seeds from a shared counter
N=$((SEED_HI - SEED_LO + 1))
next_seed() {
    ( flock 9; n=$(cat /tmp/abl_counter 2>/dev/null || echo 0); n=$((n+1)); echo $n > /tmp/abl_counter; echo $n ) 9>/tmp/abl_seed.lock
}
echo 0 > /tmp/abl_counter
worker() {
    local gpu=$1 s
    while true; do
        s=$(next_seed); [ "$s" -gt "$N" ] && break
        run_t9_eval $((SEED_LO + s - 1)) "$gpu"
    done
}
pids=()
for g in "${GPUS[@]}"; do worker "$g" & pids+=($!); done
for p in "${pids[@]}"; do wait "$p"; done
# hand all 4 GPUs back to the benchmark: update GPU config + restart gap_fill
echo "0 1 2 3" > /tmp/gap_gpu_config
for p in $(ps -eo pid,cmd | grep "gap_fill.sh" | grep -v grep | grep -v supervisor | awk '{print $1}'); do kill $p 2>/dev/null; done
echo "=== t9 ablation done $(date '+%T'); GPUs handed back to benchmark ==="
