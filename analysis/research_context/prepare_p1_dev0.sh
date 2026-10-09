#!/usr/bin/env bash
# P1 DEV0 preparation only: ZERO simulator calls, no VLA/Planner/GPU execution.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
umask 077

python3 -m unittest discover \
  -s analysis/research_context -p 'test_p1_dev0_*.py' -v

# Single immutable 24-episode balanced assignment (2 per task x arm).
python3 analysis/research_context/p1_dev0_manifest.py --repo-root "$ROOT"

python3 - <<'PY'
import hashlib, json
from collections import Counter
from pathlib import Path
out=Path("artifacts/p1_dev0")
blob=(out/"manifest.jsonl").read_bytes()
s=json.loads((out/"manifest.sha256.json").read_text())
r=[json.loads(line) for line in blob.decode().splitlines()]
assert hashlib.sha256(blob).hexdigest()==s["sha256"]
assert len(r)==24 and all(x["max_probe_events"]==1 for x in r)
assert all(Counter((x["task"],x["arm"]) for x in r)[(t,a)]==2
           for t in (3,5,9) for a in ("D0","D1","D2","D3"))
print(json.dumps({
  "phase":"P1_DEV0_PREPARATION_ONLY",
  "gate":"ASSIGNMENT_SEALED_INTEGRATION_NOT_YET_QUALIFIED",
  "episode_count":len(r),
  "manifest_sha256":s["sha256"],
  "note":"No simulation has been started; runtime hook & future-horizon audit remain prerequisite."
},indent=2))
PY
