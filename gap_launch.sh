#!/bin/bash
# nohup 日志走持久卷(/tmp 曾被清理器清空,且占 50G 临时盘预算)
mkdir -p /workspace/yjx/tmp
rm -f /tmp/gap_plan_v2.txt
nohup bash /vla_test/yjx/workspace/RPent/gap_fill.sh > /workspace/yjx/tmp/gap_fill.log 2>&1 &
echo "gap_fill pid=$!"
sleep 8
echo "=== 启动日志 ==="; cat /workspace/yjx/tmp/gap_fill.log 2>/dev/null | head -20
echo "=== 计划 ==="; head -5 /tmp/gap_plan_v2.txt 2>/dev/null; echo "($(wc -l < /tmp/gap_plan_v2.txt 2>/dev/null) items)"
echo "=== rpent 进程 ==="; ps aux | grep "[r]pent --env" | awk '{print $2}' | wc -l
