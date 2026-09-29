#!/bin/bash
# Stage I — 本地模型 vLLM OpenAI-compatible 服务启动器(spec §2)
#
# 用法:
#   LOCAL_MODEL_DIR=/workspace/yjx/models/Qwen3.5-4B bash scripts/start_local_model.sh
# 可选 env(默认值):
#   LOCAL_MODEL_PORT=8100          监听端口(仅 127.0.0.1)
#   LOCAL_MODEL_GPU=7              单卡 index(TP=1 时)
#   LOCAL_MODEL_TP=1               tensor parallel
#   LOCAL_MODEL_MAX_CONTEXT=32768  服务端截断(原生 262144;Stage I 短上下文纪律)
#   LOCAL_MODEL_DTYPE=bfloat16
#   LOCAL_MODEL_UTIL=0.90          GPU 显存利用率
#
# 特性:
#   - chat template 服务端固化 enable_thinking=False(Qwen3.5 为 thinking
#     模型;不关则 16/32 token 内无答案,Stage H H2 冒烟已证)——客户端零 patch
#   - .runlocks 锁防重复启动;日志落 repo .gap_run/(持久卷)
#   - 健康等待最长 20 分钟(权重加载 19G 需数分钟)
# 停止: bash scripts/stop_local_model.sh [port]
set -euo pipefail

MODEL_DIR=${LOCAL_MODEL_DIR:?need LOCAL_MODEL_DIR (e.g. /workspace/yjx/models/Qwen3.5-4B)}
PORT=${LOCAL_MODEL_PORT:-8100}
GPU=${LOCAL_MODEL_GPU:-7}
TP=${LOCAL_MODEL_TP:-1}
MAXLEN=${LOCAL_MODEL_MAX_CONTEXT:-32768}
DTYPE=${LOCAL_MODEL_DTYPE:-bfloat16}
UTIL=${LOCAL_MODEL_UTIL:-0.90}
NAME=$(basename "$MODEL_DIR")

/workspace/yjx/bin/dev_preflight.sh

LOCK=/workspace/yjx/.runlocks/local_model_p${PORT}.lock
mkdir -p /workspace/yjx/.runlocks
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "REFUSE: lock exists ($LOCK) — 服务可能已在跑;确认后用 stop_local_model.sh"
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

# thinking 服务端固化:把 add_generation_prompt 分支的条件改为恒真
# (原: enable_thinking is defined and enable_thinking is false → 空 think 块)
TPL="$MODEL_DIR/chat_template_nothink.jinja"
if [ ! -f "$TPL" ]; then
  sed 's/enable_thinking is defined and enable_thinking is false/true/' \
    "$MODEL_DIR/chat_template.jinja" > "$TPL"
  echo "wrote nothink template: $TPL"
fi

LOG=/workspace/yjx/workspace/RPent/.gap_run/local_model_p${PORT}.log
echo "starting vLLM: $NAME gpu=$GPU tp=$TP port=$PORT maxlen=$MAXLEN log=$LOG"
CUDA_VISIBLE_DEVICES=$GPU nohup /workspace/yjx/envs/sglm/bin/vllm serve \
  "$MODEL_DIR" \
  --host 127.0.0.1 --port "$PORT" \
  --dtype "$DTYPE" --max-model-len "$MAXLEN" \
  --tensor-parallel-size "$TP" \
  --gpu-memory-utilization "$UTIL" \
  --chat-template "$TPL" \
  --served-model-name "$NAME" \
  >> "$LOG" 2>&1 &
VLLM_PID=$!
echo "$VLLM_PID" > "$LOCK/pid"

echo "waiting for health (pid $VLLM_PID, up to 20min)…"
for i in $(seq 1 120); do
  sleep 10
  if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "FATAL: vllm process died — tail log:"
    tail -20 "$LOG"
    exit 1
  fi
  if curl -sf "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; then
    echo "HEALTH OK after ~$((i * 10))s: http://127.0.0.1:${PORT}/v1 (model=$NAME)"
    echo "smoke: python scripts/smoke_local_model.py --port $PORT"
    trap - EXIT
    exit 0
  fi
done
echo "TIMEOUT: health 未就绪(20min)— 查 $LOG"
exit 1
