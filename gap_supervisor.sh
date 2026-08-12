#!/bin/bash
# gap_supervisor.sh — keep gap_fill running until deadline; auto-restart on death.
# Usage: nohup bash gap_supervisor.sh > /tmp/gap_supervisor.log 2>&1 &
set -uo pipefail
DEADLINE="2026-08-13 00:00"
FINAL_STOP="${FINAL_STOP:-2026-08-13 10:30}"   # 10:30: no new benchmark episodes; supervisor stops restarting
LOG=/tmp/gap_fill.log
while true; do
    if [ "$(date +%s)" -ge "$(date -d "$FINAL_STOP" +%s)" ]; then
        echo "[supervisor] $(date '+%T') final stop ($FINAL_STOP) reached, stopping" >> /tmp/gap_supervisor.log
        break
    fi
    if [ "$(date +%s)" -ge "$(date -d "$DEADLINE" +%s)" ]; then
        echo "[supervisor] $(date '+%T') deadline reached, stopping" >> /tmp/gap_supervisor.log
        break
    fi
    if ! pgrep -f "gap_fill.sh" >/dev/null 2>&1; then
        echo "[supervisor] $(date '+%T') gap_fill not running, (re)starting" >> /tmp/gap_supervisor.log
        bash /hw-tbo/yjx/workspace/RPent/gap_fill.sh >> "$LOG" 2>&1
        echo "[supervisor] $(date '+%T') gap_fill exited (rc=$?)" >> /tmp/gap_supervisor.log
    fi
    sleep 60
done
