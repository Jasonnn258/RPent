#!/bin/bash
# run_guard_exp.sh — minimal A/B: repeated-perception guard vs original rule.
# Runs EVAL seeds for libero_spatial_task t0/t7/t9 with
# RPENT_BLOCK_REPEATED_PERCEPTION=1 (streak=3), writing each run to an
# isolated dir .gap_run/guard_exp/<suite>_t<task>_s<seed> so the original
# logs/ runs stay untouched for the baseline comparison.
# Bootstrap memory for t0/t7/t9 already exists (results_*_pert).
# Usage: nohup bash run_guard_exp.sh >> .gap_run/guard_exp/super.log 2>&1 &
set -uo pipefail
export PATH=/hw-tbo/yjx/miniconda3/envs/vla/bin:$PATH

SCRATCH="/hw-tbo/yjx/workspace/RPent/.gap_run"
EXPDIR="$SCRATCH/guard_exp"; mkdir -p "$EXPDIR"
SUITE="libero_spatial_task"
TASKS="0 7 9"
SEEDS="1 2 3 4 5 6 7 8 9 10"
EVAL_TURNS=40
GPU="0"
export PI05_CHECKPOINT_PATH=/hw-tbo/yjx/checkpoints/RLinf-Pi05-LIBERO-130-fullshot-SFT
export SAM3_CHECKPOINT_PATH=/hw-tbo/yjx/checkpoints/sam3/sam3.pt
export ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro
export OPENPI_DATA_HOME=/hw-tbo/yjx/.cache/openpi
export LIBERO_CONFIG_PATH=/hw-tbo/yjx/.libero
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4
# ---- the intervention ----
export RPENT_BLOCK_REPEATED_PERCEPTION=1
export RPENT_PERCEPTION_STREAK=3
export ANTHROPIC_API_KEY=$(grep "^DW_KEY=" /hw-tbo/yjx/workspace/commodity-attribute/configs/config.env | cut -d= -f2-)
P_MODEL="anthropic:kimi-k3"; P_BASE="--base-url https://dwai-data.shizhuang-inc.com/anthropic"; P_IMG=""
PLANNER_TIMEOUT_S=2400
LOG="$EXPDIR/exp.log"
MANIFEST="$EXPDIR/manifest.tsv"

run_one() {
    local task=$1 seed=$2
    local outdir="$EXPDIR/${SUITE#libero_}_t${task}_s${seed}"
    local rtmp="$EXPDIR/rt_${SUITE#libero_}_t${task}_s${seed}.log"
    local cvd; [ "$GPU" = "0" ] && cvd="0" || cvd="$GPU,0"
    echo "[$(date '+%T')] guard gpu$GPU $SUITE t$task s$seed -> $outdir" >> "$LOG"
    timeout 4500 env CUDA_VISIBLE_DEVICES="$cvd" MUJOCO_GL=egl MUJOCO_EGL_DEVICE_ID=0 LIBGL_ALWAYS_SOFTWARE=1 \
      OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_WORKERS=4 \
      ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
      PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
      ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
      OPENPI_DATA_HOME="$OPENPI_DATA_HOME" LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" HF_HUB_OFFLINE=1 \
      RPENT_BLOCK_REPEATED_PERCEPTION=1 RPENT_PERCEPTION_STREAK=3 \
      xvfb-run -a -s "-screen 0 640x480x24" \
      rpent --env libero --suite "$SUITE" --task "$task" --seed "$seed" \
        --output-dir "$outdir" \
        --planner api --model "$P_MODEL" ${P_BASE} \
        --planner-timeout-s "$PLANNER_TIMEOUT_S" --max-turns "$EVAL_TURNS" ${P_IMG} >"$rtmp" 2>&1
    local rc=$?
    echo "$(date '+%T')|$SUITE|$task|$seed|$outdir|rc=$rc" >> "$MANIFEST"
    echo "[$(date '+%T')] guard gpu$GPU $SUITE t$task s$seed rc=$rc" >> "$LOG"
}

echo "=== run_guard_exp start $(date '+%F %T') | $SUITE $TASKS seeds=$SEEDS | guard streak=3 ===" >> "$LOG"
# concurrency 2
pids=()
for t in $TASKS; do
    for s in $SEEDS; do
        run_one "$t" "$s" &
        pids+=($!)
        if [ "${#pids[@]}" -ge 2 ]; then wait "${pids[0]}"; pids=("${pids[@]:1}"); fi
    done
done
for p in "${pids[@]}"; do wait "$p"; done
echo "=== run_guard_exp DONE $(date '+%F %T') ===" >> "$LOG"
