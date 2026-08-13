#!/bin/bash
# data_guardian.sh — unattended data preservation for the RPent overnight run.
# Every INTERVAL: aggregate suites -> benchmark_summary.csv, copy critical data to
# artifacts/final_export/, write benchmark_status.md, git-commit small files (local;
# push needs user auth, attempted with timeout).
# Usage: nohup bash data_guardian.sh > /tmp/data_guardian.log 2>&1 &
set -o pipefail
export PATH=/hw-tbo/yjx/miniconda3/envs/vla/bin:$PATH
REPO=/hw-tbo/yjx/workspace/RPent
INTERVAL=${1:-3600}
EXPORT="$REPO/artifacts/final_export"
mkdir -p "$EXPORT" "$REPO/analysis"
GITSHA=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)

echo "[guardian] start $(date '+%F %T') git=$GITSHA interval=${INTERVAL}s" >> /tmp/data_guardian.log

while true; do
  sleep "$INTERVAL"
  TS=$(date '+%Y-%m-%d %H:%M')
  # ---- 1. aggregate suites -> benchmark_summary.csv ----
  "$PY" 2>/dev/null || PY="/hw-tbo/yjx/miniconda3/envs/vla/bin/python"
  $PY - "$REPO" <<'PY' > "$REPO/analysis/benchmark_summary.csv" 2>/dev/null
import os, re, glob, json, sys
from collections import defaultdict
repo = sys.argv[1]; logs = os.path.join(repo, "logs")
print("suite,task,ok,total,sr")
for suite in ["spatial","goal_task","goal_swap","spatial_task","spatial_swap"]:
    latest = {}
    for d in glob.glob(f"{logs}/*_libero_{suite}_t*_s*/"):
        b = os.path.basename(d.rstrip("/"))
        m = re.match(r"^[\d:-]+_libero_"+suite+r"_t(\d+)_s(\d+)$", b)
        if not m: continue
        t, sd = int(m.group(1)), int(m.group(2))
        term = None
        sf = os.path.join(d, "states.json")
        if os.path.exists(sf):
            try:
                st = json.load(open(sf))
                if isinstance(st, list) and st: term = st[-1].get("libero_terminated")
            except: pass
        latest[(t, sd)] = term
    stat = defaultdict(lambda: [0, 0])
    for (t, sd), term in latest.items():
        stat[t][1] += 1
        if term is True: stat[t][0] += 1
    for t in sorted(stat):
        ok, tot = stat[t]
        print(f"{suite},t{t},{ok},{tot},{ok/max(tot,1)*100:.1f}")
PY
  # ---- 2. copy critical data to final_export ----
  cp -f "$REPO/logs/gap_fill.csv" "$EXPORT/" 2>/dev/null
  cp -f "$REPO/analysis/"*.csv "$REPO/analysis/"*.md "$EXPORT/" 2>/dev/null
  cp -f "$REPO/gap_fill.sh" "$REPO/gap_supervisor.sh" "$REPO/ablate_t9_doubled.sh" "$REPO/run_rpent.sh" "$EXPORT/" 2>/dev/null
  cp -f "$REPO/logs/harness_report.jsonl" "$EXPORT/" 2>/dev/null
  # t9 ablation raw results
  mkdir -p "$EXPORT/ablation_t9"
  for d in $(ls -dt "$REPO"/logs/*_goal_swap_t9_s*/ 2>/dev/null | head -12); do
    cp -rf "$d" "$EXPORT/ablation_t9/" 2>/dev/null
  done
  # ---- 3. benchmark_status.md ----
  {
    echo "# Benchmark Status ($TS, git=$GITSHA)"
    echo ""
    echo "## GPU workers"
    nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader 2>/dev/null
    echo ""
    echo "## Active runs"
    ps -eo cmd | grep "[r]pent --env" | grep -oE "libero_[a-z_]+ --task [0-9]+ --seed [0-9]+" | sort -u
    echo ""
    echo "## Suite SR (latest per seed)"
    cat "$REPO/analysis/benchmark_summary.csv" 2>/dev/null | head -60
    echo ""
    echo "## gap_fill CSV tail"
    tail -8 "$REPO/logs/gap_fill.csv" 2>/dev/null
    echo ""
    echo "## t9 ablation"
    cat "$REPO/analysis/t9_pi0_doubled_ablation.csv" 2>/dev/null
  } > "$REPO/logs/benchmark_status.md"
  # ---- 4. git commit small files (local; push if auth works) ----
  cd "$REPO"
  git add -u -- analysis/ robots/libero/ scripts/ *.sh SETUP_NOTES.md 2>/dev/null
  git add analysis/ 2>/dev/null
  git commit -q -m "bench: status snapshot $TS (git=$GITSHA)" 2>/dev/null && echo "[guardian] committed $TS" >> /tmp/data_guardian.log
  # push attempt with short timeout (skips if no auth)
  timeout 12 git push origin main >/dev/null 2>&1 && echo "[guardian] pushed $TS" >> /tmp/data_guardian.log
  echo "[guardian] snapshot $TS done" >> /tmp/data_guardian.log
done
