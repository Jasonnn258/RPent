#!/usr/bin/env bash
# stop_glm53_flash.sh — 停本地 GLM-5.3-Flash 服务(按进程组,先 TERM 后 KILL)
#
# 服务是 setsid 起的独立进程组:8 个 TP rank + scheduler + detokenizer 等
# 全在同一 pgid 里。杀组而不是单个 PID,否则留下孤儿 rank 占着显存。
#
# 用法: bash scripts/stop_glm53_flash.sh   (没在跑也返回 0)

set -u

PID_FILE="/workspace/yjx/run/glm53_flash.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "no pidfile — nothing to stop"
    exit 0
fi
PGID=$(cat "$PID_FILE")
if ! kill -0 "-$PGID" 2>/dev/null; then
    echo "pgid $PGID already dead — cleaning pidfile"
    rm -f "$PID_FILE"
    exit 0
fi

echo "SIGTERM process group $PGID ..."
kill -TERM "-$PGID" 2>/dev/null
# TP8 卸载要几十秒(逐 rank 退出 + 显存释放),给 120s
for _ in $(seq 1 24); do
    kill -0 "-$PGID" 2>/dev/null || { echo "clean exit"; rm -f "$PID_FILE"; exit 0; }
    sleep 5
done

echo "still alive after 120s — SIGKILL"
kill -KILL "-$PGID" 2>/dev/null
sleep 5
if kill -0 "-$PGID" 2>/dev/null; then
    echo "WARN: pgid $PGID survived SIGKILL,手动检查: ps -eo pid,pgid,cmd | grep $PGID" >&2
    exit 1
fi
rm -f "$PID_FILE"
echo "stopped"
