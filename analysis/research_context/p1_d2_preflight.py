#!/usr/bin/env python3
"""P1 / D2 evidence feasibility gate on EXISTING trajectories, no simulator calls.

Read-only, no model/RPC, no extra outcome audits. Counts post-pick agent-legal
proprioception and stored RGB paths. A missing historical image may have been
pruned AFTER D2 and must not be misreported as unavailable AT D2.

Usage:
  python3 analysis/research_context/p1_d2_preflight.py \
      --repo-root /workspace/yjx/workspace/RPent

Output (gitignored): artifacts/p1_d2_preflight/summary.json
This preflight does NOT authorize L2 simulation or lifting Stage R §36.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

IMG = {
    "agentview_low": "images/image_{step:02d}.png",
    "agentview_calibration_low": "images_cam/image_cam_{step:02d}.png",
    "wrist_low": "images_wrist/image_wrist_{step:02d}.png",
    "agentview_high": "images_cam_hi/image_cam_hi_{step:02d}.png",
    "wrist_high": "images_wrist_hi/image_wrist_hi_{step:02d}.png",
}
STATE_VECS = {"robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}


def vec_valid(v, n):
    return isinstance(v, list) and len(v) >= n and all(
        type(z) in (int, float) and math.isfinite(z) for z in v[:n]
    )


def evaluate(root: Path):
    ledger = root / "analysis" / "stageR_collect_ledger.csv"
    if not ledger.is_file():
        raise FileNotFoundError("Missing source collect ledger")
    with ledger.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    seen = set()
    cnt = Counter()
    by_task = defaultdict(Counter)
    exclusion = Counter()
    cnt["ledger_episodes"] = len(rows)

    for i, row in enumerate(rows):
        relative = (row.get("episode_dir") or "").strip()
        if not relative:
            raise ValueError("missing episode_dir in ledger row %d" % i)
        ep = Path(relative)
        if not ep.is_absolute():
            ep = root / ep
        ep = ep.resolve()
        if ep in seen:
            raise ValueError("duplicate episode_dir in ledger")
        seen.add(ep)
        state_path = ep / "states.json"
        if not state_path.is_file():
            raise FileNotFoundError("missing states.json: ledger index %d" % i)
        states = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(states, list):
            raise ValueError("states not list at ledger index %d" % i)
        pick_steps = [s for s in states if isinstance(s, dict)
                      and isinstance(s.get("command"), dict)
                      and s["command"].get("action") == "pi0_pick"]
        cnt["episodes_with_pick"] += bool(pick_steps)

        for state in pick_steps:
            cnt["all_pick"] += 1
            step = state.get("step_idx")
            result = state.get("result") or {}
            if type(step) is not int or type(result.get("success")) is not bool:
                exclusion["invalid_step_or_flag"] += 1
                continue
            if type(result.get("libero_terminated")) is not bool:
                exclusion["missing_terminated"] += 1
                continue
            if result["libero_terminated"] or state.get("episode_truncated"):
                exclusion["terminated_or_truncated_D2_not_probeable"] += 1
                continue

            # This is a *legal D2* candidate, not a prospective matched trial.
            # No privileged rtrace/target coordinates/check_success are read.
            tag = "tool_failure" if result["success"] is False else "tool_success"
            cnt["nonterminal_notruncated_pick"] += 1
            cnt[tag] += 1
            b = by_task[str(row.get("task"))]
            b[tag] += 1
            legal_state = state.get("state") or {}
            for key, n in STATE_VECS.items():
                ok = vec_valid(legal_state.get(key), n)
                cnt["d2_proprio_" + key + ("_valid" if ok else "_missing")] += 1
                b["proprio_" + key + ("_valid" if ok else "_missing")] += 1
            for key, pattern in IMG.items():
                present = (ep / pattern.format(step=step)).is_file()
                # This is archived *now*, not necessarily at the original D2!
                cnt["archived_" + key + ("_present" if present else "_absent")] += 1
                b["archived_" + key + ("_present" if present else "_absent")] += 1
            # This quantity only establishes the schema has a D2 record;
            # state/img files are historical and may be pruned later.
            next_steps = [s for s in states if isinstance(s, dict) and
                          type(s.get("step_idx")) is int and s["step_idx"] > step and
                          isinstance(s.get("command"), dict)]
            b["natural_followup_step_recorded"] += bool(next_steps)
            cnt["natural_followup_step_recorded"] += bool(next_steps)

    cnt["source_episodes"] = len(seen)
    consistent = (cnt["source_episodes"] == 187 and cnt["all_pick"] == 235 and
                  cnt["episodes_with_pick"] == 186 and
                  not exclusion.get("invalid_step_or_flag") and
                  not exclusion.get("missing_terminated"))
    return {
        "protocol": "P1-D2-LEGAL-OBS-STRUCTURE-PREFLIGHT-V1",
        "gate": "STRUCTURE_PASS_FOR_DESIGN" if consistent else "HOLD_SOURCE_OR_FLAG_MISMATCH",
        "counters": dict(sorted(cnt.items())),
        "by_task": {k: dict(sorted(v.items())) for k, v in sorted(by_task.items())},
        "exclusions": dict(sorted(exclusion.items())),
        "cannot_establish": [
            "whether archived image files were present when D2 occurred (older high-res frames may be pruned)",
            "whether a visual verifier correctly judges object retention",
            "the effects of any active probe, which itself changes physical state",
            "matched counterfactual outcomes or P1 intervention gains",
            "L2 experiment authorization",
        ],
        "permission": "Existing data and legal D2 state only; no simulator or online verifier",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, required=True)
    args = ap.parse_args()
    root = args.repo_root.expanduser().resolve()
    report = evaluate(root)
    out = root / "artifacts" / "p1_d2_preflight"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["gate"] != "STRUCTURE_PASS_FOR_DESIGN":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
