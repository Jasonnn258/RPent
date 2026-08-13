#!/usr/bin/env bash
# RPent 复现运行脚本（部署后使用）
# 用法:
#   source ~/rpent_data/rpent_env.sh && bash run_repro.sh [--cuda-device N]
set -euo pipefail

ENV_NAME="libero"
SUITE="libero_object_swap"
TASK=2
SEED=0
CUDA_DEVICE="${CUDA_DEVICE:-0}"
PLANNER="api"
MODEL="anthropic:deepseek-v4-flash"
MAX_TURNS=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2;;
    --suite) SUITE="$2"; shift 2;;
    --task) TASK="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    --cuda-device) CUDA_DEVICE="$2"; shift 2;;
    --planner) PLANNER="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --max-turns) MAX_TURNS="$2"; shift 2;;
    *) echo "未知参数: $1"; exit 2;;
  esac
done

echo ">>> 运行 RPent 复现: suite=$SUITE task=$TASK seed=$SEED cuda=$CUDA_DEVICE"
echo ">>> 先看空闲 GPU: nvidia-smi"
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader

exec rpent --env "$ENV_NAME" \
  --suite "$SUITE" --task "$TASK" --seed "$SEED" \
  --cuda-device "$CUDA_DEVICE" \
  --planner "$PLANNER" --model "$MODEL" \
  --max-turns "$MAX_TURNS"
