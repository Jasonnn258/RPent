#!/usr/bin/env bash
# check_glm53_flash.sh — 本地 GLM-5.3-Flash 服务健康一览(pid/端口/生成/显存/日志尾)
#
# 四级状态:
#   process  — pidfile 的进程组还活着吗
#   port     — 127.0.0.1:8000 有监听吗(no_proxy 必须带上,代理会劫持 loopback)
#   generate — /health 真探活 200(vLLM;首启 JIT 期间 10-40min 不通是正常的)
#   info     — /v1/models 模型名匹配 + GPU 显存/利用率
#
# 用法: bash scripts/check_glm53_flash.sh   (exit 0 = 全部健康)

set -u
PID_FILE="/workspace/yjx/run/glm53_flash.pid"
LOG_FILE="/workspace/yjx/workspace/RPent/logs/glm53_flash_server.log"
PORT=8000
if [ -n "${no_proxy:-}" ]; then
    export no_proxy="127.0.0.1,localhost,$no_proxy"
else
    export no_proxy="127.0.0.1,localhost"
fi
export NO_PROXY="$no_proxy"
CURL="curl -s --max-time 10"

rc=0

# ---- process ----
if [ -f "$PID_FILE" ] && kill -0 "-$(cat "$PID_FILE")" 2>/dev/null; then
    PGID=$(cat "$PID_FILE")
    NRANK=$(pgrep -g "$PGID" | wc -l)
    echo "[process] OK  pgid=$PGID procs=$NRANK"
else
    echo "[process] DEAD (no pidfile or group gone)"
    rc=1
fi

# ---- port ----
if $CURL -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q 200; then
    echo "[port]    OK  /health 200"
else
    echo "[port]    DOWN (JIT warmup 中正常;>40min 见日志尾)"
    rc=1
fi

# ---- generate(真探活:vLLM /health 在模型 ready 后才 200) ----
CODE=$($CURL -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:$PORT/health" 2>/dev/null || echo 000)
if [ "$CODE" = "200" ]; then
    echo "[generate] OK  /health 200"
else
    echo "[generate] FAIL http=$CODE"
    rc=1
fi

# ---- model info ----
MODELS=$($CURL "http://127.0.0.1:$PORT/v1/models" 2>/dev/null)
if echo "$MODELS" | grep -q "GLM-5.3-Flash"; then
    echo "[info]    OK  served-model=GLM-5.3-Flash"
elif [ -n "$MODELS" ] && [ "$MODELS" != "000" ]; then
    echo "[info]    WARN  /v1/models 响应无 GLM-5.3-Flash: $(echo "$MODELS" | head -c 120)"
fi

# ---- GPU ----
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu \
    --format=csv,noheader,nounits 2>/dev/null \
    | awk -F', *' '{printf "[gpu%s]    %s/%s MiB, util=%s%%\n",$1,$2,$3,$4}'

# ---- log tail ----
echo "[log]     $(tail -1 "$LOG_FILE" 2>/dev/null | cut -c1-160)"

exit $rc
