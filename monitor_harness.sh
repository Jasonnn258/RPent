#!/bin/bash
# Persistent harness monitor: writes progress to a file every N min.
# Survives Claude sessions (run with nohup). Any session can read the log.
# Usage: nohup bash monitor_harness.sh >/dev/null 2>&1 &
# Progress file: /vla_test/yjx/workspace/RPent/logs/harness_progress.log
set -uo pipefail

LOGS=/vla_test/yjx/workspace/RPent/logs
PROG="$LOGS/harness_progress.log"
PY=/vla_test/yjx/miniconda3/envs/vla/bin/python
INTERVAL=${1:-600}   # seconds between checks (default 10 min)

mkdir -p "$LOGS"
echo "[monitor] started $(date '+%Y-%m-%d %H:%M:%S') interval=${INTERVAL}s" >> "$PROG"

while true; do
    sleep "$INTERVAL"
    TS=$(date '+%Y-%m-%d %H:%M:%S')
    # 1. active runs
    ACTIVE=$(ps aux | grep "rpent --env" | grep -v grep | grep -oE "libero_[a-z_]+.*--task [0-9]+.*--seed [0-9]+" | head -1)
    NACTIVE=$(ps aux | grep "rpent --env" | grep -v grep | wc -l)
    # 2. aggregate done/success across all suites' dirs (spatial + goal + ...)
    SUMMARY=$("$PY" - <<'PY' 2>/dev/null
import os, re, glob, json
from collections import defaultdict
allruns = {}
for d in glob.glob("/vla_test/yjx/workspace/RPent/logs/*_libero_*_t*_s*/"):
    b = os.path.basename(d.rstrip("/"))
    m = re.match(r"^[\d:-]+_libero_([a-z_]+)_t(\d+)_s(\d+)$", b)
    if not m: continue
    suite, task, seed = m.group(1), int(m.group(2)), int(m.group(3))
    term = None
    sf = os.path.join(d, "states.json")
    if os.path.exists(sf):
        try:
            st = json.load(open(sf))
            if isinstance(st, list) and st: term = st[-1].get("libero_terminated")
        except: pass
    if term is None:
        for f in glob.glob(d + "*_t*_s*.json"):
            try:
                a = json.load(open(f))
                if isinstance(a, dict) and "libero_terminated" in a: term = a["libero_terminated"]; break
            except: pass
    key = (suite, task, seed)
    allruns[key] = term   # keep last by dir order
bysuite = defaultdict(lambda: {"done":0,"ok":0})
for (suite,t,s), term in allruns.items():
    bysuite[suite]["done"] += 1
    if term is True: bysuite[suite]["ok"] += 1
out = "; ".join(f"{s}: {v['ok']}/{v['done']} success" for s,v in sorted(bysuite.items()))
print(out or "no runs yet")
PY
)
    echo "$TS | active=$NACTIVE | cur=$ACTIVE | $SUMMARY" >> "$PROG"
done
