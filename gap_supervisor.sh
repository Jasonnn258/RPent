#!/bin/bash
# gap_supervisor.sh — keep gap_fill running until deadline; auto-restart on death.
# Usage: nohup bash gap_supervisor.sh > /tmp/gap_supervisor.log 2>&1 &
set -uo pipefail
# Durable scratch (queue/locks/logs) — NOT /tmp: a tmp cleaner already wiped /tmp
# once and killed the whole batch. Keep it in the repo.
SCRATCH="${SCRATCH:-/vla_test/yjx/workspace/RPent/.gap_run}"; mkdir -p "$SCRATCH"
DEADLINE="2026-08-14 20:00"
FINAL_STOP="${FINAL_STOP:-2026-08-14 20:00}"   # no new benchmark episodes after this; supervisor stops restarting
LOG="$SCRATCH/gap_fill.log"
while true; do
    if [ "$(date +%s)" -ge "$(date -d "$FINAL_STOP" +%s)" ]; then
        echo "[supervisor] $(date '+%T') final stop ($FINAL_STOP) reached, stopping" >> "$SCRATCH/gap_supervisor.log"
        break
    fi
    if [ "$(date +%s)" -ge "$(date -d "$DEADLINE" +%s)" ]; then
        echo "[supervisor] $(date '+%T') deadline reached, stopping" >> "$SCRATCH/gap_supervisor.log"
        break
    fi
    if ! pgrep -f "gap_fill.sh" >/dev/null 2>&1; then
        echo "[supervisor] $(date '+%T') gap_fill not running, (re)starting" >> "$SCRATCH/gap_supervisor.log"
        bash /vla_test/yjx/workspace/RPent/gap_fill.sh >> "$LOG" 2>&1
        echo "[supervisor] $(date '+%T') gap_fill exited (rc=$?)" >> "$SCRATCH/gap_supervisor.log"
    fi
    sleep 60
done
