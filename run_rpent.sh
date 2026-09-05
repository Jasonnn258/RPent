#!/bin/bash
# RPent end-to-end: LIBERO + Pi0.5 (self-healing setup + run)
# PLANNER=glm|kimi|deepseek   (default glm)
#   glm     : anthropic:glm-5.3-flash via BigModel Anthropic-compatible endpoint, vision-capable
#   kimi    : anthropic:kimi-k3 via DWAI gateway, vision-capable -> sends images
#   deepseek: deepseek:deepseek-v4-flash, text-only -> --no-images
#
# Run: ! bash run_rpent.sh [suite task seed turns]   (PLANNER=glm default; PLANNER=kimi/deepseek to switch)
set -euo pipefail

export PATH=/vla_test/yjx/miniconda3/envs/vla/bin:$PATH

# --------------------------- config ---------------------------
PLANNER=${PLANNER:-glm}
export PI05_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/pi05
export SAM3_CHECKPOINT_PATH=/vla_test/yjx/rpent_data/checkpoints/sam3/sam3.pt
export ROBOT_PLATFORM=LIBERO
export LIBERO_TYPE=pro
# persistent caches on the mounted volume (survives container resets)
export OPENPI_DATA_HOME=/vla_test/yjx/rpent_data/.cache/openpi
export LIBERO_CONFIG_PATH=/vla_test/yjx/rpent_data/.libero
# skip slow HF memory-sync (unreachable); use local placeholder memory
export HF_HUB_OFFLINE=1

SUITE=${1:-libero_spatial}
TASK=${2:-0}
SEED=${3:-0}
TURNS=${4:-100}

# --- planner-specific config ---
PLANNER_MODEL="" PLANNER_BASE_URL="" PLANNER_EXTRA_ENV="" PLANNER_IMAGES=""
if [ "$PLANNER" = "glm" ]; then
    # GLM via BigModel Anthropic-compatible endpoint (vision-capable)
    export ANTHROPIC_API_KEY=$(grep "^GLM_API_KEY=" /vla_test/yjx/rpent_data/rpent_env.sh | cut -d= -f2- | tr -d '"')
    PLANNER_MODEL="anthropic:glm-5.3-flash"
    PLANNER_BASE_URL="https://open.bigmodel.cn/api/anthropic"
    PLANNER_IMAGES=""                          # glm-5.3-flash supports vision
elif [ "$PLANNER" = "kimi" ]; then
    export ANTHROPIC_API_KEY=$(grep "^DW_KEY=" /vla_test/yjx/rpent_data/rpent_env.sh | cut -d= -f2-)
    PLANNER_MODEL="anthropic:kimi-k3"
    PLANNER_BASE_URL="https://dwai-data.shizhuang-inc.com/anthropic"
    PLANNER_IMAGES=""                          # kimi-k3 supports vision
elif [ "$PLANNER" = "deepseek" ]; then
    export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"   # set via env (never hardcode)
    PLANNER_MODEL="deepseek:deepseek-v4-flash"
    PLANNER_BASE_URL=""
    PLANNER_IMAGES="--no-images"               # deepseek is text-only
else
    echo "unknown PLANNER: $PLANNER"; exit 1
fi

# ----------------------- 1. mesa EGL (overlay-reset guard) -----------------------
if [ ! -s /usr/lib/x86_64-linux-gnu/libEGL.so.1 ] || \
   [ "$(stat -c%s /usr/lib/x86_64-linux-gnu/libEGL.so.1 2>/dev/null || echo 0)" = "0" ]; then
    echo "[setup] reinstalling mesa EGL ..."
    apt-get install -y libegl1 libegl-mesa0 libgles2 libosmesa6 >/dev/null 2>&1
fi

# ----------------------- 2. paligemma tokenizer -----------------------
TOK=/vla_test/yjx/rpent_data/.cache/openpi/big_vision/paligemma_tokenizer.model
if [ ! -s "$TOK" ]; then
    echo "[setup] downloading paligemma tokenizer ..."
    mkdir -p "$(dirname "$TOK")"
    curl -s -m 120 -o "$TOK" -L \
      "https://modelscope.cn/models/google/paligemma-3b-pt-224/resolve/master/tokenizer.model"
fi

# ----------------------- 3. libero config -----------------------
LIBERO_CFG=/vla_test/yjx/rpent_data/.libero/config.yaml
if [ ! -f "$LIBERO_CFG" ]; then
    echo "[setup] writing libero config ..."
    mkdir -p /vla_test/yjx/rpent_data/.libero
    LP=/vla_test/yjx/miniconda3/envs/vla/lib/python3.11/site-packages/liberopro/liberopro
    cat > "$LIBERO_CFG" <<EOF
benchmark_root: $LP
bddl_files: $LP/bddl_files
datasets: $LP/../datasets
init_states: $LP/init_files
EOF
fi

# ----------------------- 4. libero assets symlink -----------------------
LP=/vla_test/yjx/miniconda3/envs/vla/lib/python3.11/site-packages
if [ ! -e "$LP/libero/libero/assets" ]; then
    echo "[setup] linking libero assets ..."
    ln -sfn "$LP/liberopro/liberopro/assets" "$LP/libero/libero/assets"
fi

# ----------------------- run -----------------------
cd /vla_test/yjx/workspace/RPent
echo "=== RPent: $PLANNER planner + LIBERO ==="
echo " suite=$SUITE task=$TASK seed=$SEED turns=$TURNS model=$PLANNER_MODEL ${PLANNER_IMAGES:-vision}"

xvfb-run -a -s "-screen 0 640x480x24" \
  env MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 \
  DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  PI05_CHECKPOINT_PATH="$PI05_CHECKPOINT_PATH" \
  SAM3_CHECKPOINT_PATH="$SAM3_CHECKPOINT_PATH" \
  ROBOT_PLATFORM=LIBERO LIBERO_TYPE=pro \
  OPENPI_DATA_HOME="$OPENPI_DATA_HOME" \
  LIBERO_CONFIG_PATH="$LIBERO_CONFIG_PATH" \
  HF_HUB_OFFLINE=1 \
  rpent --env libero \
    --suite "$SUITE" --task "$TASK" --seed "$SEED" \
    --planner api --model "$PLANNER_MODEL" \
    ${PLANNER_BASE_URL:+--base-url "$PLANNER_BASE_URL"} \
    --planner-timeout-s "${PLANNER_TIMEOUT_S:-2400}" \
    --max-turns "$TURNS" ${PLANNER_IMAGES} \
    2>&1 | tee "$(ls -td /vla_test/yjx/workspace/RPent/logs/*/ 2>/dev/null | head -1)/agent_terminal.log"
