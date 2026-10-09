#!/usr/bin/env python3
"""Research Package A: bounded, read-only A0 census + internal EERD v0.1.

Requires existing Stage R data on the user's server. Python stdlib only.
Two sealed phases: schema (NO success/check_success value analysis),
then outcomes (user approved L1 in RESEARCH_AUTHORIZATION.md).
No sim, model calls, runtime writes, or modification of source assets.

python analysis/research_context/research_package_a.py --repo-root "$PWD" --phase full

Output is under artifacts/research_package_a/ (gitignored); audit data
must never be committed or passed to online agents.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROTOCOL = "RPENT-PACKAGE-A-STAGE2J-V2-EERD-V01-20261009"
FG_DZ = 0.03
FG_DXY = 0.10
SEED = 20261009
N_BOOT = 10000


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def source_paths(root):
    p = root / "analysis" / "stageR_collect_ledger.csv"
    with p.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    episodes = []
    seen = set()
    for i, row in enumerate(rows):
        name = (row.get("episode_dir") or "").strip()
        if not name:
            raise ValueError("ledger row without episode_dir: %s" % i)
        ep = Path(name)
        if not ep.is_absolute():
            ep = root / ep
        ep = ep.resolve()
        if ep in seen:
            raise ValueError("duplicate episode directory (ledger row %s)" % i)
        seen.add(ep)
        if not (ep / "states.json").is_file() or not (ep / "stageR_trace.jsonl").is_file():
            raise FileNotFoundError("source files absent, episode ledger index %d" % i)
        episodes.append((row, ep, "ep_%04d" % (i + 1)))
    return p, episodes


def valid_vec(obs, key):
    if not isinstance(obs, dict) or key not in obs:
        return None, "INVALID_MISSING"
    v = obs[key]
    if not isinstance(v, (tuple, list)) or len(v) < 3:
        return None, "INVALID_NONFINITE"
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in v[:3]):
        return None, "INVALID_NONFINITE"
    return v, "VALID"


def reference_field_check(points):
    """Presence and numeric finiteness ONLY. No outcome field is consumed."""
    if not points:
        return {"valid_base": False, "status": ["INVALID_MISSING"], "reason": "NO_MEAS"}
    base = points[0]
    target_list = base.get("obj_of_interest") if isinstance(base, dict) else None
    if not isinstance(target_list, list) or not target_list or not isinstance(target_list[0], str) or not target_list[0]:
        return {"valid_base": False, "status": ["INVALID_MISSING"] * len(points), "reason": "NO_TARGET"}
    target = target_list[0]
    bpos, bstatus = valid_vec(base.get("obs"), target + "_pos")
    if bstatus != "VALID":
        return {"valid_base": False, "status": [bstatus] * len(points), "reason": "BASE_" + bstatus}
    statuses = []
    for p in points:
        obs = p.get("obs") if isinstance(p, dict) else None
        _, s1 = valid_vec(obs, target + "_pos")
        _, s2 = valid_vec(obs, "robot0_eef_pos")
        statuses.append("INVALID_MISSING" if "INVALID_MISSING" in (s1, s2) else
                        "INVALID_NONFINITE" if "INVALID_NONFINITE" in (s1, s2) else "VALID")
    return {"valid_base": True, "status": statuses, "reason": None}


def collect(root):
    ledger_path, episodes = source_paths(root)
    records = []
    provenance = {"ledger": sha256(ledger_path), "episodes": {}}
    episode_info = {}
    errors = []
    for ledger, ep, ep_id in episodes:
        sp, tp = ep / "states.json", ep / "stageR_trace.jsonl"
        provenance["episodes"][ep_id] = {"states_sha256": sha256(sp), "trace_sha256": sha256(tp)}
        states = json.loads(sp.read_text(encoding="utf-8"))
        trace = read_jsonl(tp)
        if not isinstance(states, list):
            raise ValueError("invalid states top-level: %s" % ep_id)
        state_steps = defaultdict(list)
        for state in states:
            if isinstance(state, dict):
                state_steps[state.get("step_idx")].append(state)
        trace_steps = defaultdict(list)
        for ev in trace:
            if isinstance(ev, dict):
                trace_steps[ev.get("step_idx")].append(ev)
        episode_info[ep_id] = {
            "episode_id": ep_id, "task": ledger.get("task"), "seed": ledger.get("seed"),
            "n_pick": 0,
        }
        for step_key, items in state_steps.items():
            for state in items:
                if (state.get("command") or {}).get("action") != "pi0_pick":
                    continue
                episode_info[ep_id]["n_pick"] += 1
                res = state.get("result") or {}
                events = trace_steps.get(step_key, [])
                begins = [e for e in events if e.get("ev") == "step_begin" and e.get("skill") == "pi0_pick"]
                ends = [e for e in events if e.get("ev") == "step_end" and e.get("skill") == "pi0_pick"]
                acts = [e for e in events if e.get("ev") == "action" and e.get("kind") == "chunk" and e.get("skill") == "pi0_pick"]
                problems = []
                if not isinstance(step_key, int) or len(items) != 1 or len(begins) != 1 or len(ends) != 1 or not acts:
                    problems.append("MISSING_OR_DUPLICATE_JOIN")
                if [a.get("chunk_idx") for a in acts] != list(range(1, len(acts) + 1)):
                    problems.append("NONCONTIGUOUS_CHUNKS")
                if type(res.get("chunks_used")) is not int or res["chunks_used"] != len(acts):
                    problems.append("A3_CHUNKS_USED_MISMATCH")
                if type(res.get("libero_terminated")) is not bool or type(state.get("libero_terminated")) is not bool or res.get("libero_terminated") != state.get("libero_terminated"):
                    problems.append("A1_TERMINATION_MISMATCH")
                if type(state.get("episode_truncated")) is not bool:
                    problems.append("MISSING_TRUNCATION_FLAG")
                if (state.get("command") or {}).get("action") != "pi0_pick":
                    problems.append("A2_COMMAND_MISMATCH")
                if len(ends) == 1 and ends[0].get("step_idx") != step_key:
                    problems.append("A2_STEP_MISMATCH")
                points = [e.get("meas") for e in acts] + ([ends[0].get("final_meas")] if len(ends) == 1 else [])
                if len(points) != len(acts) + 1:
                    problems.append("A3_Q_LENGTH_MISMATCH")
                check = reference_field_check(points)
                if not check["valid_base"]:
                    problems.append("REFERENCE_UNCONSTRUCTIBLE")
                # A non-base VALID point is not essential for all statuses, but a
                # completely unevaluable suffix cannot support meaningful labels.
                if not any(x == "VALID" for x in check["status"][1:]):
                    problems.append("REFERENCE_UNCONSTRUCTIBLE_NO_SUFFIX")
                item = {
                    "episode_id": ep_id, "step_idx": step_key,
                    "task": ledger.get("task"), "seed": ledger.get("seed"),
                    "result": res, "state": state, "end": ends[0] if ends else {},
                    "points": points, "point_status": check["status"],
                    "problems": sorted(set(problems)),
                }
                records.append(item)
                if problems:
                    errors.append({"episode_id": ep_id, "step_idx": step_key, "reasons": sorted(set(problems))})
    return provenance, episode_info, records, errors


def schema(root, output, strict=True):
    provenance, episodes, records, errors = collect(root)
    counters = Counter({"episodes": len(episodes), "pick_calls": len(records)})
    counters["episodes_with_pick"] = sum(bool(ep["n_pick"]) for ep in episodes.values())
    counters["pick_chunk_actions"] = sum(len(x["points"]) - 1 for x in records)
    counters["eligible_pick"] = sum(not x["problems"] for x in records)
    for x in records:
        for status in x["point_status"]:
            counters["point_" + status] += 1
        for p in x["problems"]:
            counters["excluded_" + p] += 1
    consistency = (counters["pick_calls"] == 235 and counters["episodes"] == 187
                   and counters["pick_chunk_actions"] == 2859)
    gate = "PASS" if not errors and (consistency or not strict) else "HOLD"
    if counters["eligible_pick"] < 100:
        gate = "STOP_ELIGIBLE_PICK_LT_100"
    data = {
        "protocol": PROTOCOL, "phase": "SCHEMA_ONLY", "gate": gate,
        "source_sha256": provenance,
        "counters": dict(counters), "known_stage2i_counts_matched": consistency,
        "reference_field_errors": errors,
        "note": "No result.success/check_success value used in schema calculations. "
                "Physical labels NOT_EVALUATED. Outcome analysis is a separate phase.",
    }
    write_json(output / "schema_qa.json", data)
    return data


def fg_only(p, b, target):
    pos, _ = valid_vec(p.get("obs") if isinstance(p, dict) else None, target + "_pos")
    eef, _ = valid_vec(p.get("obs") if isinstance(p, dict) else None, "robot0_eef_pos")
    bpos, _ = valid_vec(b.get("obs") if isinstance(b, dict) else None, target + "_pos")
    if pos is None or eef is None or bpos is None:
        return None
    return (pos[2] - bpos[2] >= FG_DZ and math.hypot(pos[0] - eef[0], pos[1] - eef[1]) <= FG_DXY)


def label_reference(points, statuses):
    if not points or statuses[0] != "VALID":
        return "UNKNOWN"
    b = points[0]
    target = b["obj_of_interest"][0]
    any_true = any(fg_only(p, b, target) is True for p, s in zip(points, statuses) if s == "VALID")
    if any_true:
        return "POSITIVE"
    return "NEGATIVE" if all(s == "VALID" for s in statuses) else "UNKNOWN"


def beta_wilson(count, total):
    if not total:
        return None
    p = count / total
    z = 1.95996398454
    d = 1 + z * z / total
    c = (p + z * z / (2 * total)) / d
    h = z * math.sqrt((p * (1-p) + z * z/(4*total)) / total) / d
    return [c-h, c+h]


def stats(rows):
    """Pick-level descriptive estimands. Cluster resample belongs to parent episode."""
    counts = Counter((r["flag"], r["reference"]) for r in rows)
    npos = sum(v for (fl, ref), v in counts.items() if fl)
    nneg = sum(v for (fl, ref), v in counts.items() if not fl)
    decpos = counts[(True, "POSITIVE")] + counts[(True, "NEGATIVE")]
    decneg = counts[(False, "POSITIVE")] + counts[(False, "NEGATIVE")]
    ndec = decpos + decneg
    agreements = counts[(True, "POSITIVE")] + counts[(False, "NEGATIVE")]
    refpos = counts[(True, "POSITIVE")] + counts[(False, "POSITIVE")]
    refneg = counts[(True, "NEGATIVE")] + counts[(False, "NEGATIVE")]
    risk = lambda num, den: (num / den if den else None)
    # UNKNOWN-lower bound uses all accepted flags in denominator (unknowns
    # contribute neither error nor a confirmed correct result).
    r_accept = risk(counts[(True, "NEGATIVE")], decpos)
    r_miss = risk(counts[(False, "POSITIVE")], decneg)
    obs = {
        "n_pick": len(rows), "n_flag_true": npos, "n_flag_false": nneg,
        "reference_positive": sum(v for (fl, ref), v in counts.items() if ref == "POSITIVE"),
        "reference_negative": sum(v for (fl, ref), v in counts.items() if ref == "NEGATIVE"),
        "reference_unknown": sum(v for (fl, ref), v in counts.items() if ref == "UNKNOWN"),
        "table": {("true" if fl else "false") + "_" + ref.lower(): v
                  for (fl, ref), v in sorted(counts.items(), key=lambda x: (x[0][0], x[0][1]))},
        "r_accept_complete_case": r_accept,
        "r_accept_unknown_lower_bound": risk(counts[(True, "NEGATIVE")], npos),
        "r_miss_complete_case": r_miss,
        "r_miss_unknown_lower_bound": risk(counts[(False, "POSITIVE")], nneg),
        "concordance_decidable": risk(agreements, ndec),
        "constant_true_concordance": risk(refpos, ndec),
        "constant_false_concordance": risk(refneg, ndec),
        "n_decidable": ndec,
        "n_accepted_decidable": decpos,
        "n_rejected_decidable": decneg,
    }
    if ndec:
        p_flag = decpos / ndec
        p_phys = refpos / ndec
        chance = p_flag * p_phys + (1-p_flag)*(1-p_phys)
        obs["cohen_kappa"] = ((agreements / ndec - chance) / (1-chance)
                               if chance < 1 else None)
        obs["wilson_concordance_descriptive"] = beta_wilson(agreements, ndec)
    else:
        obs["cohen_kappa"] = None
    return obs


def bootstrap(rows, n=N_BOOT):
    groups = defaultdict(list)
    for row in rows:
        groups[row["episode_id"]].append(row)
    keys = sorted(groups)
    if not keys:
        return {}
    rng = random.Random(SEED)
    targets = ("r_accept_complete_case", "r_miss_complete_case", "concordance_decidable")
    samples = {x: [] for x in targets}
    for _ in range(n):
        resampled = [r for k in rng.choices(keys, k=len(keys)) for r in groups[k]]
        s = stats(resampled)
        for key in targets:
            if s[key] is not None:
                samples[key].append(s[key])
    out = {}
    for key in targets:
        v = sorted(samples[key])
        out[key] = ([v[int(0.025 * (len(v)-1))], v[int(0.975 * (len(v)-1))]]
                    if len(v) >= max(10, int(n * 0.8)) else None)
    return out


def as_bool(x):
    if type(x) is bool:
        return x
    if isinstance(x, str) and x.strip().lower() in ("true", "false"):
        return x.strip().lower() == "true"
    return None


def b_dataset(root, ep_info):
    """Only frozen R1 rows; no model/rollout and no new label computation."""
    manifest = root / "analysis" / "stageR_manifest.csv"
    same = root / "analysis" / "stageR_same_action_rollouts.csv"
    resample = root / "analysis" / "stageR_resample_rollouts.csv"
    if not all(p.is_file() for p in (manifest, same, resample)):
        return [], {"status": "B_SOURCE_ABSENT", "reason": "manifest or frozen CSV missing"}
    with manifest.open(encoding="utf-8", newline="") as f:
        manifest_rows = {r["event_id"]: r for r in csv.DictReader(f) if r.get("role") == "R1_COHORT"}
    by_task_seed = defaultdict(list)
    for eid, ep in ep_info.items():
        by_task_seed[(str(ep["task"]), str(ep["seed"]))].append(eid)
    result = []
    seen = set()
    problems = []
    for csv_file in (same, resample):
        with csv_file.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                event = manifest_rows.get(r.get("event_id"))
                if not event:
                    continue
                key = (r["event_id"], r.get("arm"), r.get("trial"))
                if key in seen:
                    problems.append("DUPLICATE_B_TRIAL")
                    continue
                seen.add(key)
                try:
                    index = int(r["trial"])
                except (ValueError, KeyError, TypeError):
                    problems.append("INVALID_TRIAL")
                    continue
                sources = by_task_seed.get((event.get("task"), event.get("seed")), [])
                if len(sources) != 1:
                    problems.append("UNRESOLVED_SOURCE_EPISODE")
                stable, acquired = as_bool(r.get("stable")), as_bool(r.get("acquisition"))
                if stable is None or acquired is None:
                    problems.append("INVALID_FROZEN_OUTCOME")
                result.append({
                    "event_id": r["event_id"], "arm": r.get("arm"), "trial": index,
                    "source_episode_id": sources[0] if len(sources) == 1 else None,
                    "cross_dataset_provenance_group": sources[0] if len(sources) == 1 else None,
                    "reconstruction_condition": "S_POST" if r.get("arm") == "NATURAL" else "S_PRE",
                    "restore_quality": "APPROXIMATE_NOT_COUNTERFACTUAL",
                    "research_audit_only": {"stable": stable, "acquisition": acquired},
                })
    complete = len(result) == 480 and not problems and len(manifest_rows) == 24
    return result, {"status": "PASS" if complete else "HOLD", "n_trials": len(result),
                    "n_events": len(manifest_rows), "problems": dict(Counter(problems))}


def outcomes(root, output, strict=True):
    schema_path = output / "schema_qa.json"
    if not schema_path.is_file():
        raise RuntimeError("Run --phase schema before outcomes")
    report = json.loads(schema_path.read_text(encoding="utf-8"))
    if report.get("gate") != "PASS" or report.get("protocol") != PROTOCOL:
        raise RuntimeError("Schema gate not PASS, stop before outcome values")
    provenance, eps, records, errors = collect(root)
    if provenance != report["source_sha256"] or errors:
        raise RuntimeError("Source changed since schema seal or eligibility error")
    eligible = [x for x in records if not x["problems"]]
    if len(eligible) < 100 and strict:
        raise RuntimeError("E1 eligible pick count < 100; stop")

    audit, online, metadata, primary = [], [], [], []
    invalid_success = 0
    trace_mismatch = 0
    for x in eligible:
        res, st = x["result"], x["state"]
        flag = res.get("success")
        if type(flag) is not bool:
            invalid_success += 1
            continue
        if x["end"].get("success") is not flag:
            trace_mismatch += 1
            continue
        label = label_reference(x["points"], x["point_status"])
        rec = {
            "episode_id": x["episode_id"], "step_idx": x["step_idx"],
            "flag": flag, "reference": label,
            "terminal_involved": bool(res["libero_terminated"]),
            "truncated": bool(st["episode_truncated"]),
            "complete_case": all(s == "VALID" for s in x["point_status"]),
        }
        audit.append({**rec, "outcome_contract": "IN_SKILL_ACQ_FGONLY_V1",
                      "visibility": "research_audit_truth",
                      "meas_validity": x["point_status"]})
        # Explicit allowlist mirrors the actual D2 view. No sim_measurement
        # or check_success from rtrace is ever copied into this view.
        online.append({
            "episode_id": x["episode_id"], "step_idx": x["step_idx"],
            "tool_report": {k: res.get(k) for k in (
                "name", "instruction", "success", "chunks_used", "max_chunks",
                "peak_lift_m", "min_gripper_opening", "final_gripper_opening",
                "libero_terminated", "diagnostics")},
            "episode_truncated": st["episode_truncated"],
            "libero_terminated": st["libero_terminated"],
            "visibility": "observed_execution_prefix",
        })
        metadata.append({
            "episode_id": x["episode_id"], "step_idx": x["step_idx"],
            "task_id": x["task"], "seed": x["seed"], "n_expected_points": len(x["points"]),
            "invalid_missing": x["point_status"].count("INVALID_MISSING"),
            "invalid_nonfinite": x["point_status"].count("INVALID_NONFINITE"),
        })
        if not rec["terminal_involved"]:
            primary.append(rec)
    if invalid_success or trace_mismatch:
        gate = "STOP_FLAG_SCHEMA_OR_TRACE_MISMATCH"
    elif len(primary) < 30 or min(
            sum(x["flag"] for x in primary), sum(not x["flag"] for x in primary), default=0) < 10:
        gate = "A0_MAIN_UNESTIMABLE"
    else:
        gate = "PASS"
    # Ensure online view has only actually D2-available fields.
    forbidden = ("check_success", "obj_of_interest", "acquisition", "stable_fg", "reference")
    assert all(not any(word in json.dumps(x, ensure_ascii=False) for word in forbidden)
               for x in online), "online/audit firewall violation"
    b, b_info = b_dataset(root, eps)
    full = {
        "protocol": PROTOCOL, "gate": gate, "n_eligible_pick": len(eligible),
        "n_primary": len(primary), "invalid_success": invalid_success,
        "trace_success_mismatch": trace_mismatch,
        "reference_unknown": sum(x["reference"] == "UNKNOWN" for x in audit),
        "b_dataset": b_info,
        "warnings": [
            "FGONLY is same-skill pose-following proxy, NOT actual grip contact or future retention.",
            "Outcome audit data not authorized for online Runtime/Evolution use.",
            "This is a quota-stopped, three-task observational sample; pick calls cluster within episode.",
            "All results descriptive, no confirmatory p-values or causal claims.",
        ],
    }
    if gate == "PASS":
        s = stats(primary)
        full["primary_descriptive"] = s
        full["primary_cluster_bootstrap_95"] = bootstrap(primary)
        full["primary_untruncated_sensitivity"] = stats([r for r in primary if not r["truncated"]])
        full["complete_case_sensitivity"] = stats([r for r in primary if r["complete_case"]])
        full["all_eligible_descriptive"] = stats([{"episode_id": r["episode_id"],
              "flag": r["flag"], "reference": r["reference"]} for r in audit])
        if min(s["n_accepted_decidable"], s["n_rejected_decidable"]) < 10:
            full["gate"] = "CENSUS_DEGRADED_M2_LIMITED"
            # E3: no decision-related complete-case point estimates.
            for k in ("r_accept_complete_case", "r_miss_complete_case"):
                full["primary_descriptive"][k] = None
            full["primary_cluster_bootstrap_95"] = {}
    else:
        full["primary_descriptive"] = None
    write_json(output / "a0_result.json", full)
    if not (invalid_success or trace_mismatch):
        write_jsonl(output / "EERD_A_online_eligible.jsonl", online)
        write_jsonl(output / "EERD_A_audit_only.jsonl", audit)
        write_jsonl(output / "EERD_A_reconstruction_metadata.jsonl", metadata)
        if b_info["status"] == "PASS":
            write_jsonl(output / "EERD_B_audit_only.jsonl", b)
    return full


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--phase", choices=("schema", "outcomes", "full"), default="full")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fixture", action="store_true",
                        help="Only for synthetic tests: relax official 187/235/2859 corpus gates")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = (args.output or root / "artifacts" / "research_package_a").resolve()
    if root == output or root in output.parents and "artifacts" not in output.parts and not args.fixture:
        raise SystemExit("Output must live in repo artifacts/ for real data; source files read-only")
    output.mkdir(parents=True, exist_ok=True)
    if args.phase in ("schema", "full"):
        qa = schema(root, output, strict=not args.fixture)
        print(json.dumps({"stage": "schema", "gate": qa["gate"], "counters": qa["counters"],
                          "output": str(output / "schema_qa.json")}, ensure_ascii=False))
        if qa["gate"] != "PASS":
            raise SystemExit(2)
    if args.phase in ("outcomes", "full"):
        done = outcomes(root, output, strict=not args.fixture)
        print(json.dumps({"stage": "outcomes", "gate": done["gate"],
                          "n_primary": done["n_primary"], "n_eligible": done["n_eligible_pick"],
                          "output": str(output / "a0_result.json")}, ensure_ascii=False))
        if done["gate"].startswith("STOP_"):
            raise SystemExit(3)


if __name__ == "__main__":
    main()
