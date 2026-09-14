#!/usr/bin/env bash
# run_local_planner_smoke.sh — 本地 GLM-5.3-Flash planner 单集冒烟(t0 s1)
#
# 复刻 ovpm_exp.py base_env() 的容器三件套(这个容器 0 EGL 设备,run_rpent.sh
# 的 egl 路径跑不了):
#   1) MUJOCO_GL=osmesa + unset MUJOCO_EGL_DEVICE_ID/LIBGL_ALWAYS_SOFTWARE
#   2) loopback no_proxy(容器全局代理会把 127.0.0.1 请求丢给代理 → 503)
#   3) 不需要 GLM_API_KEY(本地端点无鉴权),ANTHROPIC_API_KEY 清掉防误用远端
# 旋钮:RPENT_REASONING_EFFORT ∈ {low,high,max}(api_loop._build_model_settings,
# 默认不设 = Thinking(high) 映射)。baseline 跑法 = max。
#
# 用法: bash scripts/run_local_planner_smoke.sh [task] [seed]
#   产物: logs/local_planner_smoke/<ts>_t<task>_s<seed>/

set -euo pipefail

ROOT="/workspace/yjx/workspace/RPent"
TASK="${1:-0}"
SEED="${2:-1}"
OUT="$ROOT/logs/local_planner_smoke/$(date +%Y%m%d-%H:%M:%S)_t${TASK}_s${SEED}"
mkdir -p "$OUT"

source /workspace/yjx/bin/dev_preflight.sh
preflight_check || { echo "REFUSED: preflight 未过" >&2; exit 1; }

# 服务必须活着(真生成探测,不是只看端口)
if [ -n "${no_proxy:-}" ]; then
    export no_proxy="127.0.0.1,localhost,$no_proxy"
else
    export no_proxy="127.0.0.1,localhost"
fi
export NO_PROXY="$no_proxy"
code=$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:8000/health || true)
[ "$code" = "200" ] || { echo "REFUSED: 本地服务 /health=$code(先跑 start_glm53_flash.sh)" >&2; exit 1; }

# ---- 容器三件套(与 ovpm_exp.py base_env() 一致) ----
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
unset MUJOCO_EGL_DEVICE_ID LIBGL_ALWAYS_SOFTWARE
unset ANTHROPIC_API_KEY          # 防止误打远端;本地端点不需要 key
# openpi 的 Pi0.5 tokenizer 缓存默认写 ~/.cache(overlay,容器重建即丢,且其
# gs:// 下载器不走代理会卡死):指到持久卷,文件已预放(big_vision/paligemma_tokenizer.model)
export OPENPI_DATA_HOME=/workspace/yjx/rpent_data/openpi_cache

# 单集默认 GPU0(VLA + 渲染);GLM 服务占满 8 卡时留 ~13-15G,单 worker 够用
export CUDA_VISIBLE_DEVICES=0

# --max-tokens 24576 必带:CLI 默认 8192,effort=max 时 thinking 会烧穿上限
# 复现 devC v1 的零内容截断事故(见 analysis/outcome_validation_summary.md)
echo "=== local planner smoke: libero_spatial_task t${TASK} s${SEED} ==="
rpent --env libero --suite libero_spatial_task --task "$TASK" --seed "$SEED" \
    --output-dir "$OUT" \
    --planner api --model "openai-chat:zai-org/GLM-5.3-Flash" \
    --base-url "http://127.0.0.1:8000/v1" \
    --planner-timeout-s 3600 \
    --max-turns 40 \
    --max-tokens 24576 2>&1 | tee "$OUT/run.log"

echo "=== done: $OUT ==="
echo "check: run.log 里应有 ≥3 轮 planner tool call + 图像输入;"
echo "共存显存记录: nvidia-smi --query-gpu=index,memory.used --format=csv"
