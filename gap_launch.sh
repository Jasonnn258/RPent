#!/bin/bash
rm -f /tmp/gap_plan_v2.txt
nohup bash /vla_test/yjx/workspace/RPent/gap_fill.sh > /tmp/gap_fill.log 2>&1 &
echo "gap_fill pid=$!"
sleep 8
echo "=== 启动日志 ==="; cat /tmp/gap_fill.log 2>/dev/null | head -20
echo "=== 计划 ==="; head -5 /tmp/gap_plan_v2.txt 2>/dev/null; echo "($(wc -l < /tmp/gap_plan_v2.txt 2>/dev/null) items)"
echo "=== rpent 进程 ==="; ps aux | grep "[r]pent --env" | awk '{print $2}' | wc -l
