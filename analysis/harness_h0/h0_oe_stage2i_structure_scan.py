#!/usr/bin/env python3
"""Stage2I schema-only census of Stage R collect episodes.

Reads only structural keys, timestamps/chunk indices and the ledger's
episode_dir field. Never inspects result.success, check_success,
episode_terminated values, computes labels, or modifies source artifacts.

Usage: python analysis/harness_h0/h0_oe_stage2i_structure_scan.py --repo-root /workspace/yjx/workspace/RPent
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

PICK = "pi0_pick"
RESULT_FIELDS = frozenset({
    "name", "instruction", "success", "chunks_used", "max_chunks",
    "peak_lift_m", "min_gripper_opening", "final_gripper_opening",
    "libero_terminated", "diagnostics",
})
DIAGNOSTIC_FIELDS = frozenset({
    "start_eef_z", "peak_eef_z", "min_eef_z", "post_min_peak_z",
    "descent_m", "post_min_ascent_m", "descent_done", "lift_thresh",
    "gripper_closed_thresh",
})
MEAS_FIELDS = frozenset({"obs", "obj_of_interest", "check_success"})


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def is_meas_schema(meas) -> bool:
    return isinstance(meas, dict) and MEAS_FIELDS <= meas.keys() and isinstance(meas.get("obs"), dict)


def timestamp_ok(begin, acts, end) -> bool:
    stamps = [r.get("t") for r in [begin, *acts, end]]
    return all(type(t) in (int, float) for t in stamps) and all(
        a <= b for a, b in zip(stamps, stamps[1:])
    )


def evaluate(root: Path) -> dict:
    ledger = root / "analysis" / "stageR_collect_ledger.csv"
    with ledger.open("r", encoding="utf-8", newline="") as f:
        records = list(csv.DictReader(f))
    paths = []
    for rec in records:
        directory = (rec.get("episode_dir") or "").strip()
        if directory:
            path = Path(directory)
            paths.append(path if path.is_absolute() else root / path)
    unique_dirs = sorted(set(paths))
    sums = Counter()
    sums["ledger_rows"] = len(records)
    sums["ledger_rows_with_episode_dir"] = len(paths)
    sums["unique_episode_dirs"] = len(unique_dirs)
    sums["duplicate_episode_dir_rows"] = len(paths) - len(unique_dirs)
    examples = []

    def issue(reason: str, i: int, step=None):
        sums[reason] += 1
        if len(examples) < 12:
            examples.append({"episode_index": i, "step_idx": step, "reason": reason})

    for i, ep in enumerate(unique_dirs):
        states_path = ep / "states.json"
        trace_path = ep / "stageR_trace.jsonl"
        if not states_path.is_file() or not trace_path.is_file():
            issue("episode_missing_required_file", i)
            continue
        sums["episodes_with_both_files"] += 1
        try:
            states = json.loads(states_path.read_text(encoding="utf-8"))
            trace = load_jsonl(trace_path)
        except (OSError, UnicodeError, ValueError):
            issue("episode_parse_failure", i)
            continue
        if not isinstance(states, list) or not isinstance(trace, list):
            issue("episode_invalid_top_level_schema", i)
            continue
        steps_seen = Counter(
            s.get("step_idx") for s in states if isinstance(s, dict)
            and type(s.get("step_idx")) is int
        )
        if any(cnt > 1 for cnt in steps_seen.values()):
            issue("duplicate_states_step_idx_episode", i)
        events = defaultdict(list)
        for rec in trace:
            if isinstance(rec, dict) and type(rec.get("step_idx")) is int:
                events[rec["step_idx"]].append(rec)
        pick_steps = [s for s in states if isinstance(s, dict)
                      and isinstance(s.get("command"), dict)
                      and s["command"].get("action") == PICK]
        sums["episodes_with_pick"] += bool(pick_steps)
        sums["pi0_pick_calls"] += len(pick_steps)
        for state in pick_steps:
            step = state.get("step_idx")
            complete = True
            if type(step) is not int or steps_seen[step] != 1:
                issue("pick_missing_or_duplicate_step_idx", i, step)
                complete = False
            result = state.get("result")
            if not isinstance(result, dict) or not RESULT_FIELDS <= result.keys():
                issue("pick_incomplete_return_keys", i, step)
                complete = False
            if not isinstance(result, dict) or not isinstance(result.get("diagnostics"), dict) or not DIAGNOSTIC_FIELDS <= result["diagnostics"].keys():
                issue("pick_incomplete_diagnostics_keys", i, step)
                complete = False
            recs = events.get(step, []) if type(step) is int else []
            begins = [r for r in recs if r.get("ev") == "step_begin" and r.get("skill") == PICK]
            ends = [r for r in recs if r.get("ev") == "step_end" and r.get("skill") == PICK]
            actions = [r for r in recs if r.get("ev") == "action" and r.get("skill") == PICK and r.get("kind") == "chunk"]
            if len(begins) != 1 or len(ends) != 1:
                issue("pick_begin_end_not_unique", i, step)
                complete = False
            if not actions:
                issue("pick_no_chunk_actions", i, step)
                complete = False
            mixed_actions = [r for r in recs if r.get("ev") == "action" and
                             (r.get("skill") != PICK or r.get("kind") != "chunk")]
            if mixed_actions:
                issue("pick_unexpected_action_kind_or_skill", i, step)
                complete = False
            if any(not is_meas_schema(r.get("meas")) for r in actions):
                issue("pick_chunk_measurement_incomplete", i, step)
                complete = False
            if len(ends) == 1 and not is_meas_schema(ends[0].get("final_meas")):
                issue("pick_final_measurement_incomplete", i, step)
                complete = False
            indices = [r.get("chunk_idx") for r in actions]
            if indices != list(range(1, len(indices) + 1)):
                issue("pick_chunk_idx_not_contiguous", i, step)
                complete = False
            if len(begins) == 1 and len(ends) == 1 and not timestamp_ok(begins[0], actions, ends[0]):
                issue("pick_bad_timestamp_order", i, step)
                complete = False
            if len(begins) == 1 and len(ends) == 1 and actions:
                sums["pick_calls_with_trace_boundary_and_action"] += 1
            sums["pick_chunk_actions"] += len(actions)
            if complete:
                sums["complete_paired_pi0_pick_calls"] += 1
            else:
                sums["incomplete_paired_pi0_pick_calls"] += 1
    sums["episodes_without_pick"] = sums["episodes_with_both_files"] - sums["episodes_with_pick"]
    return {
        "protocol": "H0-STAGE2I-STRUCTURE-ONLY-V1",
        "source": "ledger-referenced directories; no outcome stratification",
        "counters": dict(sorted(sums.items())),
        "examples": examples,
        "gate": "STRUCTURE_ONLY_PASS_PENDING_CLASS_ELIGIBILITY" if (
            sums["episodes_with_both_files"] == sums["unique_episode_dirs"]
            and sums["incomplete_paired_pi0_pick_calls"] == 0
            and sums["episode_parse_failure"] == 0
            and sums["pi0_pick_calls"] > 0
        ) else "STRUCTURE_HOLD_OR_STOP_REVIEW_EXAMPLES",
        "cannot_establish": [
            "whether result.success has both classes",
            "concordance/false-positive/false-negative metrics",
            "future retained-grasp reference after Planner return",
            "experimental authorization",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(evaluate(args.repo_root.expanduser().resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
