#!/usr/bin/env bash
# Approved Research Package A, L1 only. NO new simulation, models or Runtime edits.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
umask 077
mkdir -p artifacts/research_package_a

# Fail closed on synthetic unit regressions before accessing real outcomes.
python3 -m unittest discover -s analysis/research_context \
    -p 'test_research_package_a.py' -v

# Sealed two-phase workflow: schema => source/script hash check => outcomes.
# Writes ONLY under gitignored artifacts/ and never alters frozen sources.
python3 analysis/research_context/research_package_a.py \
    --repo-root "$ROOT" --phase full

echo
echo "Research Package A output (LOCAL ONLY):"
echo "  $ROOT/artifacts/research_package_a/schema_qa.json"
echo "  $ROOT/artifacts/research_package_a/a0_result.json"
echo "  $ROOT/artifacts/research_package_a/A0_REPORT.md"
echo "  $ROOT/artifacts/research_package_a/EERD_DATA_CARD.md"
echo
echo "Return only sanitized gate/counters for review. Do NOT upload audit_only JSONL."
python3 - <<'PY'
import json
from pathlib import Path
p = Path("artifacts/research_package_a/a0_result.json")
j = json.loads(p.read_text(encoding="utf-8"))
print(json.dumps({
    "protocol": j["protocol"],
    "gate": j["gate"],
    "n_eligible_pick": j["n_eligible_pick"],
    "n_primary": j["n_primary"],
    "reference_unknown": j["reference_unknown"],
    "b_dataset": j["b_dataset"],
    "primary_descriptive": j.get("primary_descriptive"),
    "primary_cluster_bootstrap_95": j.get("primary_cluster_bootstrap_95"),
}, ensure_ascii=False, indent=2))
PY
