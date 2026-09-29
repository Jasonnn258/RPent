#!/bin/bash
# Stage I — 停止本地 vLLM 服务(只杀自己启动的进程,pid 来自 .runlocks)
# 用法: bash scripts/stop_local_model.sh [port]   # 默认 8100
set -euo pipefail
PORT=${1:-8100}
LOCK=/workspace/yjx/.runlocks/local_model_p${PORT}.lock
if [ ! -f "$LOCK/pid" ]; then
  echo "no pidfile at $LOCK/pid — 服务未在跑?"
  exit 0
fi
PID=$(cat "$LOCK/pid")
if kill -0 "$PID" 2>/dev/null; then
  # vllm 前台进程;SIGTERM 让 engine 优雅退出,10s 后兜底
  kill "$PID" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.5
  done
  kill -9 "$PID" 2>/dev/null || true
  echo "stopped pid $PID"
else
  echo "pid $PID already dead"
fi
rm -rf "$LOCK"
