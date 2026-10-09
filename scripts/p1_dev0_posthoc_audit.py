#!/usr/bin/env python3
"""Independent P1-DEV0 POST-RUN audit (read-only, no GPU, no environment calls).

Separates:
  * 24 assigned / started / triggered / not started (not infra by default)
  * physical horizon reached versus early EPISODE_END fallback
  * actually observed arm decisions from offline shadow decisions
  * execution engineering from identifiable evidence-decision contrasts
  * hard GPU budget vs launch-time soft guard

DO NOT restart the 3 missed cells, retrain a policy, update frozen A0/DEV0
outcomes, or call rpent CLI. The original policy's SHA256 must match the
reported running version before any shadow prediction.

  python scripts/p1_dev0_posthoc_audit.py \
    --out-root /workspace/yjx/rpent_data/p1_dev0 \
    --manifest artifacts/p1_dev0/manifest.jsonl

Writes sanitized summary to gitignored artifacts/p1_dev0/posthoc_audit.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import fields
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POLICY = REPO / "analysis" / "research_context" / "p1_dev0_policy.py"
EXPECTED_POLICY_SHA = "15d58071cea670039b00a264f1486ed7f8571b7d448b99af60035ce801a50630"
EXPECTED_MANIFEST_SHA = "839bc0d1b392806553fd2e6a5338a4f8a6f9c47e6a77957ec95dbc29a21b9132"
GPU_BUDGET_S = 6 * 3600
ALLOWED_ARMS = ("D0", "D1", "D2", "D3")


def load_jsonl(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def verified_manifest(path, seal_path):
    """Refuse all post-hoc tallies if the allocation is not the frozen 24-grid."""
    if not path.is_file() or not seal_path.is_file():
        raise FileNotFoundError("FROZEN_MANIFEST_OR_SEAL_MISSING")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    rows = load_jsonl(path)
    canonical = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")) + "\n" for r in rows).encode("utf-8")
    value = hashlib.sha256(canonical).hexdigest()
    if value != seal.get("sha256") or value != EXPECTED_MANIFEST_SHA:
        raise ValueError("FROZEN_MANIFEST_SHA_MISMATCH")
    if len(rows) != 24 or seal.get("episodes") != 24:
        raise ValueError("FROZEN_MANIFEST_N_MISMATCH")
    return rows


def load_summary(out_root):
    """Last *completed* runner summary, metadata only, no audit measurements."""
    paths = sorted(out_root.glob("run_*_summary.json"))
    for path in reversed(paths):
        try:
            val = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(val.get("final"), dict):
                return val["final"]
        except (OSError, ValueError):
            continue
    return None


def audit(manifest, out_root, policy_path=POLICY):
    keys = [r["episode_key"] for r in manifest]
    if len(keys) != 24 or len(set(keys)) != 24:
        raise ValueError("Expected 24 distinct, preregistered episode keys")
    if any(r.get("arm") not in ALLOWED_ARMS or r.get("task") not in (3, 5, 9)
           for r in manifest):
        raise ValueError("Unknown arm/task in immutable manifest")

    allocated, observed, triggered = Counter(), Counter(), Counter()
    missing, interrupted = [], []
    event_quality = Counter()
    action_kinds, decision_kinds = Counter(), Counter()
    horizon = {"fixed_at_skill_boundary": 0, "ended_before_target": 0,
               "unaudited": 0, "fixed_overshoot_steps": [],
               "early_exit_shortfall_steps": []}
    shadow_rows = []
    policy_sha = hashlib.sha256(policy_path.read_bytes()).hexdigest() \
        if policy_path.is_file() else None
    shadow_permitted = policy_sha == EXPECTED_POLICY_SHA
    # Keep a pure, stdlib policy import and never pass raw simulator fields.
    if shadow_permitted:
        sys.path.insert(0, str(policy_path.parent))
        from p1_dev0_policy import LegalEvidence, choose, deny_privileged_payload
        allowed = {f.name for f in fields(LegalEvidence)}

    for row in manifest:
        key, arm, task = row["episode_key"], row["arm"], row["task"]
        allocated[(task, arm)] += 1
        evs = load_jsonl(out_root / "runs" / key / "p1_dev0_events.jsonl")
        if not evs:
            # Missing event file is NOT an infra failure. In this completed
            # run, budget-skipped cells never got an event or ledger entry.
            missing.append(key)
            continue
        observed[(task, arm)] += 1
        event_quality["has_any_events"] += 1
        by = defaultdict(list)
        for e in evs:
            by[e.get("ev")].append(e)
        if len(by["trigger"]) > 1:
            event_quality["multiple_triggers"] += 1
        if not by["episode_end"]:
            interrupted.append(key)
        if not by["trigger"]:
            event_quality["started_no_trigger"] += 1
            continue

        triggered[(task, arm)] += 1
        event_quality["triggered"] += 1
        for name in ("decision", "action", "audit", "episode_end"):
            if not by[name]:
                event_quality["trigger_without_" + name] += 1
        if bool(by["probe"]) != (arm != "D0"):
            event_quality["probe_arm_mismatch"] += 1

        for d in by["decision"][:1]:
            decision_kinds[d.get("decision", "UNKNOWN")] += 1
        for a in by["action"][:1]:
            action_kinds[a.get("kind", "UNKNOWN")] += 1
        audits = by["audit"]
        if not audits:
            horizon["unaudited"] += 1
        else:
            e = audits[0]
            over = e.get("overshoot_env_steps")
            if e.get("kind") == "FIXED_HORIZON" and isinstance(over, (int, float)):
                horizon["fixed_at_skill_boundary"] += 1
                horizon["fixed_overshoot_steps"].append(int(over))
            elif e.get("kind") == "EPISODE_END" and isinstance(over, (int, float)):
                horizon["ended_before_target"] += 1
                horizon["early_exit_shortfall_steps"].append(int(-over))
            else:
                horizon["unaudited"] += 1

        # Offline-only policy behavior test on *observed* physical probe data.
        # Shadow actions were never executed and have NO potential outcome.
        if by["probe"] and by["decision"] and shadow_permitted:
            payload = by["decision"][0].get("policy_input", {})
            try:
                clean = {k: v for k, v in payload.items() if k in allowed}
                deny_privileged_payload(payload)
                d2 = choose(LegalEvidence(**{**clean, "arm": "D2"}))
                d3 = choose(LegalEvidence(**{**clean, "arm": "D3"}))
                shadow_rows.append({
                    "task": task, "observed_arm": arm,
                    "actual_decision": by["decision"][0].get("decision"),
                    "d2_shadow": d2.decision, "d3_shadow": d3.decision,
                    "d2_rationale": d2.rationale_code,
                    "d3_rationale": d3.rationale_code,
                })
            except (TypeError, ValueError, KeyError) as exc:
                event_quality["shadow_unavailable_or_invalid"] += 1

    runner = load_summary(out_root)
    gpu_used = ((runner or {}).get("budget_final") or {}).get("gpu_s")
    gpu_over = max(0.0, gpu_used - GPU_BUDGET_S) \
        if isinstance(gpu_used, (float, int)) else None

    def group(c):
        return {f"t{t}/{a}": c.get((t, a), 0)
                for t in (3, 5, 9) for a in ALLOWED_ARMS}

    shadow_d2 = Counter(r["d2_shadow"] for r in shadow_rows)
    shadow_d3 = Counter(r["d3_shadow"] for r in shadow_rows)
    return {
        "protocol": "P1-DEV0-POSTHOC-AUDIT-V1",
        "provenance": {
            "source": "immutable P1-DEV0 event files plus frozen manifest",
            "policy_sha256": policy_sha,
            "expected_frozen_policy_sha256": EXPECTED_POLICY_SHA,
            "shadow_policy_version_match": shadow_permitted,
        },
        "denominators": {
            "allocated": len(manifest),
            "with_events": sum(observed.values()),
            "triggered": sum(triggered.values()),
            "untriggered_observed": sum(observed.values()) - sum(triggered.values()),
            "not_started_or_unrecorded": len(missing),
            "not_started_keys": missing,
            "events_without_episode_end": interrupted,
            "missing_event_reason": "UNDETERMINED_FROM_EVENT_FILE_ALONE",
            "do_not_infer_infra_from_missing": True,
        },
        "by_task_arm": {
            "allocated": group(allocated), "with_events": group(observed),
            "triggered": group(triggered),
        },
        "event_integrity": dict(event_quality),
        "actual_decisions": dict(decision_kinds),
        "actual_actions": dict(action_kinds),
        "horizon": horizon,
        "runner_budget": {
            "budget_gpu_seconds": GPU_BUDGET_S,
            "observed_gpu_seconds": gpu_used,
            "over_budget_seconds": gpu_over,
            "hard_budget_pass": gpu_over == 0.0 if gpu_over is not None else None,
            "warning": "Launch gate can overrun when two episodes are in flight.",
        },
        "shadow_not_causal": {
            "n_probe_snapshots_checked": len(shadow_rows),
            "d2_static_decision_counts": dict(shadow_d2),
            "d3_legal_heuristic_decision_counts": dict(shadow_d3),
            "different_D2_vs_D3": sum(
                r["d2_shadow"] != r["d3_shadow"] for r in shadow_rows),
            "note": "Shadow decisions use existing legal observations only; "
                    "actions and future outcomes are NOT counterfactuals.",
        },
        "science_gate": (
            "HOLD_NO_ARM_ACTION_CONTRAST"
            if len(action_kinds) <= 1
            else "EXPLORATORY_ONLY_NOT_CAUSAL"
        ),
        "limits": [
            "This is a post-hoc secondary audit and cannot retroactively change preregistration.",
            "Pre-delivery tool interception is not proof the original failure reached Planner.",
            "D3 uses proprio plus fresh-image existence, not the image pixels.",
            "EPISODE_END outcome is early exit, not the fixed-horizon result.",
            "No new L2 cohort is authorized by this script.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-root", type=Path,
                   default=Path("/workspace/yjx/rpent_data/p1_dev0"))
    p.add_argument("--manifest", type=Path,
                   default=REPO / "artifacts" / "p1_dev0" / "manifest.jsonl")
    p.add_argument("--seal", type=Path,
                   default=REPO / "artifacts" / "p1_dev0" / "manifest.sha256.json")
    p.add_argument("--write", type=Path,
                   default=REPO / "artifacts" / "p1_dev0" / "posthoc_audit.json")
    args = p.parse_args()
    if not args.write.resolve().is_relative_to((REPO / "artifacts").resolve()):
        p.error("Only write to gitignored artifacts/; never output raw audit data")
    data = audit(verified_manifest(args.manifest, args.seal), args.out_root, POLICY)
    args.write.parent.mkdir(parents=True, exist_ok=True)
    args.write.write_text(json.dumps(data, ensure_ascii=False, indent=2)
                          + "\n", encoding="utf-8")
    safe = {
        "science_gate": data["science_gate"],
        "denominators": data["denominators"],
        "actual_decisions": data["actual_decisions"],
        "actual_actions": data["actual_actions"],
        "horizon": data["horizon"],
        "runner_budget": data["runner_budget"],
        "shadow_not_causal": data["shadow_not_causal"],
        "policy_sha_match": data["provenance"]["shadow_policy_version_match"],
    }
    print(json.dumps(safe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
