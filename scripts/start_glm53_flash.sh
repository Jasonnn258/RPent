#!/usr/bin/env bash
# start_glm53_flash.sh — 本地 GLM-5.3-Flash planner 服务(8xH100, vLLM TP8)
#
# 部署详情见 repo 根 DEPLOY_GLM53_FLASH.md。设计要点:
#   - setsid 脱离当前 shell + pidfile 记 pgid,stop 脚本按组杀;
#   - HF_HUB_OFFLINE=1 + 各 JIT/编译缓存指向 /workspace(overlay 重启会丢);
#   - no_proxy 显式含 loopback:容器全局代理会把 127.0.0.1 请求丢出去 → 503;
#   - unset CUDA_VISIBLE_DEVICES:TP8 要看到全部 8 卡;
#   - 首启有 10-40min 安静期(yrfs 流式装载 + flashinfer JIT + CUDA graph 捕获),
#     判活用 check_glm53_flash.sh,别急着杀。
#   - 为什么是 vLLM 而不是 sglang:sglang ≥0.5.18 全线 CUDA 13 依赖栈,本机
#     driver 535(CUDA 12.6)装不了;vLLM nightly cu129 wheel 是 cu12 栈且
#     09-03 就支持 Glm5Next(PR #53906)。见 DEPLOY 文档 §2.1。
#
# 用法: bash scripts/start_glm53_flash.sh [额外 vllm serve 参数透传]
#   已在跑 → 直接退出 0;模型文件不齐 → 拒绝启动。

set -euo pipefail

ROOT="/workspace/yjx/workspace/RPent"
MODEL_DIR="/workspace/yjx/models/GLM-5.3-Flash"
ENV_BIN="/workspace/yjx/envs/sglm/bin"
RUN_DIR="/workspace/yjx/run"
PID_FILE="$RUN_DIR/glm53_flash.pid"
LOG_FILE="$ROOT/logs/glm53_flash_server.log"
PORT=8000

mkdir -p "$RUN_DIR" "$ROOT/logs"

# ---------------- preflight(共享开发机铁律) ----------------
source /workspace/yjx/bin/dev_preflight.sh
preflight_check || {
    echo "REFUSED: dev_preflight 资源检查未过(高载时不要硬启 8 卡服务)" >&2
    exit 1
}

# 防重复:已有存活实例就不再起
if [ -f "$PID_FILE" ] && kill -0 "-$(cat "$PID_FILE")" 2>/dev/null; then
    echo "already running (pgid $(cat "$PID_FILE")) — nothing to do"
    exit 0
fi

# 模型完整性:62 个 shard + 关键小文件
SHARDS=$(ls "$MODEL_DIR"/model-*.safetensors 2>/dev/null | wc -l)
if [ "$SHARDS" -lt 62 ]; then
    echo "REFUSED: $MODEL_DIR 只有 $SHARDS/62 个 shard,下载未完成" >&2
    echo "         续传: bash /workspace/yjx/tmp/dl_glm53.sh" >&2
    exit 1
fi
for f in config.json tokenizer.json tokenizer_config.json chat_template.jinja \
         model.safetensors.index.json; do
    [ -s "$MODEL_DIR/$f" ] || { echo "REFUSED: 缺 $f" >&2; exit 1; }
done

# GPU 空闲检查:最空的卡至少 ~66G(0.75 util ≈60G + 运行时开销;GPU1 有他人
# 常驻 ~4.5G + 历史残留,过不去时单独评估是否放行)
FREE_MB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | sort -n | head -1)
if [ "${FREE_MB:-0}" -lt 66000 ]; then
    echo "REFUSED: 最空的卡只有 ${FREE_MB}MiB free(<66000)" >&2
    exit 1
fi

# ---------------- 环境 ----------------
unset CUDA_VISIBLE_DEVICES          # TP8 需要全部卡
unset MUJOCO_EGL_DEVICE_ID LIBGL_ALWAYS_SOFTWARE
export HF_HUB_OFFLINE=1
# CUDA_HOME 必须指 12.9(conda 前缀):GLM-5.3 的 MHC/tilelang/deep_gemm JIT 会
# 现场用 nvcc 编 sm_90a kernel,代码用 PTX 'q' 128-bit 约束,需要 nvcc>=12.8
# 前端;系统 /usr/local/cuda 是 12.6 → "NVCC compilation failed"(boot4 实测)。
# 不能用 CUDA 13 nvcc 替代:ptxas 13 产的 cubin driver 535 装载报 INVALID_IMAGE
# (已实测)。12.9.86 = conda cuda-nvcc_linux-64 + cuda-cudart-dev + cuda-cccl,
# 编出的 cubin 已验证可装载。JIT 缓存 = DG_JIT_CACHE_DIR(vLLM 自动指到上面
# VLLM_CACHE_ROOT/deep_gemm,本地 tmpfs,跨 worker 共享)。
CUDA_HOME_129="/workspace/yjx/envs/cuda129"
if [ -x "$CUDA_HOME_129/bin/nvcc" ]; then
    export CUDA_HOME="$CUDA_HOME_129"
    export CUDA_PATH="$CUDA_HOME_129"
else
    echo "WARN: $CUDA_HOME_129/bin/nvcc 不存在,deep_gemm JIT 会退回系统 nvcc 12.6 并失败" >&2
fi
# JIT/编译缓存必须放本地盘:/workspace 是网络盘(yrfs),8 个 TP worker 并发
# JIT 时 triton 的文件锁在 yrfs 上不生效 → 缓存竞态 → worker 崩(FileNotFoundError
# + shm_broadcast 卡死,2026-09-14 首启实测)。/dev/shm 是 tmpfs(本机 2T),
# 代价是容器重启后重编 ~5-10min,可接受。切勿改回 /workspace。
JIT_BASE=/dev/shm/jit_glm53
mkdir -p "$JIT_BASE"
export TRITON_CACHE_DIR="$JIT_BASE/triton"
export TORCHINDUCTOR_CACHE_DIR="$JIT_BASE/inductor"
export VLLM_CACHE_ROOT="$JIT_BASE/vllm"
# flashinfer 0.6.18 的正确变量名是 FLASHINFER_WORKSPACE_BASE(不是 _DIR),
# 实际缓存 = $BASE/.cache/flashinfer/<ver>/<arch>/cached_ops。不设会写 /root/.cache
# (overlay,重启即丢 + 违反"重要文件只写 /workspace"的本地盘例外约定)。
export FLASHINFER_WORKSPACE_BASE="$JIT_BASE"
export no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}"
export NO_PROXY="$no_proxy"

# ---------------- 启动(setsid 新进程组) ----------------
# 配方对齐官方 GLM-5.3-Flash recipe(recipes.vllm.ai)+ 本机约束:
#   - H100 必须 BF16 KV(recipe 明说 Hopper 不支持该模型 FP8 KV,不传
#     --kv-cache-dtype 即默认 BF16);
#   - 0.75 显存预算 ≈60G/卡,给 Pi0.5/SAM3 worker 留 13-15G;
#   - 256K 上下文(模型上限 1M;原 64K 在单集 smoke 实测不够 —— RPent 每轮
#     带 1 图,turn 11 时 prompt 已 41K,+max_tokens 24576 恰好超 1 token 被
#     400 拒掉。KV 池 1.39M tokens,256K 不加显存,只是校验口径);
#   - 16 并发(VLA 共存第一版从紧);
#   - 【已知上游 bug,2026-09-14 七崩定位】长 prompt 会确定性触发 CUDA IMA
#     (8 rank 同死;纯文本可复现,与图片/工具/并发无关)。阈值随配置移动:
#     前缀缓存关 = 8-24K 全过、~28K 死;前缀缓存开(全默认)= 共享前缀梯度
#     16K 即死(crash 7)。⇒ 保留 --no-enable-prefix-caching(验证过阈值最高的
#     配置,短 prompt 场景 = 功能测试 7/7 + 基准 300 请求全过)。已证伪的其余
#     缓解:--enforce-eager / 换 FLASH_ATTN_MLA_SPARSE 后端 / 换 09-12 wheel;
#     单块化 boot 不起来(65536 KV 前 OOM,32768 CUBLAS崩)。**episode 级使用
#     (对话会长到 28K+)被阻塞,等上游修复**(issue 草稿
#     analysis/vllm_glm53flash_ima_issue_draft.md,复现器 scripts/repro_glm53_ima.py)。
#   - MTP 投机解码第二版再开(与 sglang 计划同决策:先验证质量基线)。
echo "starting GLM-5.3-Flash (vLLM TP8, port $PORT), first boot 10-40min JIT warmup..." | tee -a "$LOG_FILE"
setsid "$ENV_BIN/vllm" serve "$MODEL_DIR" \
    --tensor-parallel-size 8 \
    --served-model-name zai-org/GLM-5.3-Flash \
    --tool-call-parser glm47 --reasoning-parser glm45 \
    --enable-auto-tool-choice \
    --max-model-len 262144 \
    --max-num-seqs 16 \
    --gpu-memory-utilization 0.75 \
    --no-enable-prefix-caching \
    --host 127.0.0.1 --port "$PORT" \
    "$@" >> "$LOG_FILE" 2>&1 &

PGID=$(ps -o pgid= -p $! | tr -d ' ')
echo "$PGID" > "$PID_FILE"
echo "pgid=$PGID pidfile=$PID_FILE"
echo "log: tail -f $LOG_FILE"
echo "health: bash $ROOT/scripts/check_glm53_flash.sh   (首启 10-40min 内不通是正常的)"
