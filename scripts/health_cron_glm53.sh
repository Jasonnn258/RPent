#!/usr/bin/env bash
# health_cron_glm53.sh — GLM-5.3-Flash 本地服务健康自愈守护(替代 cron)
#
# 为什么是守护进程而不是 cron:本容器 crond 未运行且 /var/spool/cron 缺失,
# 拉起 crond 还要改 overlay;一个 setsid 循环脚本等效(5min 探活 + 自愈 +
# 日志体积守卫),容器重启后重跑本脚本即可(见 DEPLOY_GLM53_FLASH.md §7)。
#
# 行为(每 300s 一轮):
#   1) /health 探活(no_proxy 必带);
#   2) 连续 2 轮失败 → 调 start_glm53_flash.sh 重启(其内置 preflight +
#      pidfile 防重复;boot 中它会自己 dedup 掉);
#   3) "进程在但不健康" 持续 4 轮(≥20min,覆盖正常 boot 10-40min 的场景是
#      先 stop 再 start,防僵尸 APIServer 占 8000 端口;
#   4) 重启频率限制:两次重启动作间隔 ≥30min(崩溃风暴时不放大负载);
#   5) 日志守卫:server log >200MB 时截断保留最后 100MB。
#   自身动作记录 logs/glm53_health.log。只碰自己的进程组,不动别人的。
#
# 用法:
#   bash scripts/health_cron_glm53.sh start    # setsid 后台启动
#   bash scripts/health_cron_glm53.sh stop     # 停 watchdog(不动模型服务)
#   bash scripts/health_cron_glm53.sh once     # 单轮检查(调试用)

set -u

ROOT="/workspace/yjx/workspace/RPent"
RUN_DIR="/workspace/yjx/run"
PID_FILE="$RUN_DIR/glm53_health.pid"
HLOG="$ROOT/logs/glm53_health.log"
SLOG="$ROOT/logs/glm53_flash_server.log"
INTERVAL=300
# set -u 下不能用 ${no_proxy:+,$no_proxy}(老 bash 会报 unbound)
if [ -n "${no_proxy:-}" ]; then
    export no_proxy="127.0.0.1,localhost,$no_proxy"
else
    export no_proxy="127.0.0.1,localhost"
fi
export NO_PROXY="$no_proxy"

log() { echo "$(date '+%F %T') $*" >> "$HLOG"; }

health_code() {
    curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        http://127.0.0.1:8000/health 2>/dev/null || echo 000
}

svc_alive() {
    [ -f "$RUN_DIR/glm53_flash.pid" ] && \
        kill -0 "-$(cat "$RUN_DIR/glm53_flash.pid")" 2>/dev/null
}

guard_log_size() {
    # 200MB 以上截断到尾 100MB(日志是诊断生命线,只截不删)
    local max=$((200 * 1024 * 1024)) keep=$((100 * 1024 * 1024))
    if [ -f "$SLOG" ] && [ "$(stat -c%s "$SLOG")" -gt "$max" ]; then
        tail -c "$keep" "$SLOG" > "$SLOG.tail" && mv "$SLOG.tail" "$SLOG"
        log "log-size-guard: truncated $SLOG to last ${keep} bytes"
    fi
}

restart_service() {
    # 30min 频率限制(stamp 文件)
    local stamp="$RUN_DIR/glm53_health.last_restart"
    local now=$(date +%s) last=$(cat "$stamp" 2>/dev/null || echo 0)
    if [ $((now - last)) -lt 1800 ]; then
        log "restart suppressed (rate-limit, last=$(( (now - last) / 60 ))min ago)"
        return
    fi
    # 启动保护:进程组存活且年龄 <45min(boot 实测 10-40min:权重流式装载
    # ~19min + JIT/图捕获)→ 视为 boot 进行中,绝不能 stop(否则无限重启循环)
    if svc_alive; then
        local leader etimes
        leader=$(pgrep -g "$(cat "$RUN_DIR/glm53_flash.pid")" 2>/dev/null | head -1)
        etimes=$(ps -o etimes= -p "$leader" 2>/dev/null | tr -d ' ')
        if [ -n "$etimes" ] && [ "${etimes:-0}" -lt 2700 ]; then
            log "young instance (${etimes}s < 2700s) — assuming boot, no restart"
            return
        fi
        echo "$now" > "$stamp"
        log "unhealthy-but-alive (${etimes}s): stopping stale instance first"
        bash "$ROOT/scripts/stop_glm53_flash.sh" >> "$HLOG" 2>&1
        sleep 10
    else
        echo "$now" > "$stamp"
    fi
    log "restarting via start_glm53_flash.sh"
    bash "$ROOT/scripts/start_glm53_flash.sh" >> "$HLOG" 2>&1
}

one_cycle() {
    local fails=0 alive_fails=0
    # 状态文件跨轮记忆
    local fstate="$RUN_DIR/glm53_health.fails"
    local astate="$RUN_DIR/glm53_health.alive_fails"
    fails=$(cat "$fstate" 2>/dev/null || echo 0)
    alive_fails=$(cat "$astate" 2>/dev/null || echo 0)

    local code
    code=$(health_code)
    if [ "$code" = "200" ]; then
        [ "$fails" != "0" ] && log "recovered (health=200, was fails=$fails)"
        echo 0 > "$fstate"; echo 0 > "$astate"
    else
        fails=$((fails + 1)); echo "$fails" > "$fstate"
        log "health=$code (consecutive fails=$fails)"
        if svc_alive; then
            alive_fails=$((alive_fails + 1)); echo "$alive_fails" > "$astate"
        else
            echo 0 > "$astate"
        fi
        # 连续 2 轮不健康 → 重启;进程在但 4 轮(≥20min)不健康 → 同样会走到这
        if [ "$fails" -ge 2 ]; then
            restart_service
            echo 0 > "$fstate"; echo 0 > "$astate"
        fi
    fi
    guard_log_size
}

start_daemon() {
    if [ -f "$PID_FILE" ] && kill -0 "-$(cat "$PID_FILE")" 2>/dev/null; then
        echo "watchdog already running (pgid $(cat "$PID_FILE"))"
        exit 0
    fi
    mkdir -p "$RUN_DIR"
    setsid bash "$0" _loop > /dev/null 2>&1 &
    local pgid=$(ps -o pgid= -p $! | tr -d ' ')
    echo "$pgid" > "$PID_FILE"
    echo "watchdog started pgid=$pgid log=$HLOG"
}

stop_daemon() {
    if [ -f "$PID_FILE" ] && kill -0 "-$(cat "$PID_FILE")" 2>/dev/null; then
        kill -TERM "-$(cat "$PID_FILE")" 2>/dev/null
        echo "watchdog stopped (pgid $(cat "$PID_FILE"));模型服务不受影响"
    else
        echo "watchdog not running"
    fi
    rm -f "$PID_FILE"
}

case "${1:-}" in
    start) start_daemon ;;
    stop)  stop_daemon ;;
    once)  one_cycle ;;
    _loop)
        log "watchdog loop started (interval=${INTERVAL}s)"
        while true; do
            one_cycle
            sleep "$INTERVAL"
        done
        ;;
    *) echo "usage: $0 {start|stop|once}"; exit 1 ;;
esac
