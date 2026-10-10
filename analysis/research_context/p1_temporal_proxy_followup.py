#!/usr/bin/env python3
"""P1 Temporal Proxy Followup v1: exit-time horizon rescoring (L1, offline).

Supplementary experiment for the temporal-proxy round. The ONLY manipulated
variable is the FGONLY reference horizon: any-time (frozen A0) vs skill-exit
(final_meas, from p1_temporal_proxy_lab). Arms, gate thresholds and sample
qualification are reused frozen from p1_pick_gate_lab — nothing is tuned here.

Pre-stated hypotheses (H-a/H-b/H-c are arithmetic consequences of the already
published temporal_proxy_v1.json aggregate; they serve as a cross-validated
join check. H-T2 and the geometry table are the new measurements):

H-a  Under the exit horizon the tool flag keeps TP=101/FP=2, FN 56->26,
     UNKNOWN=0 (no final_meas censoring in PRIMARY).
H-b  >=90% of the 26 exit-persistent FNs are D-only-missing (pattern 011).
H-c  Exit-persistence rate among D-only FNs >=70%, while among FNs missing
     L or G (patterns other than 011/111) <=15%.
H-T2 The gate-lab +0.054 BAcc of dropping D was mostly a reference-horizon
     artifact: re-scored against the exit horizon, |BAcc(L_AND_Gfinal) -
     BAcc(flag)| <= 0.02 (episode-cluster descriptive bootstrap).

Exit-time FGONLY is still the same kinematic weak proxy (object z vs base +
XY near EEF), evaluated at a different time; NOT held-grasp truth. Output is
aggregate-only: no episode ids, paths, or audit pose values.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import ROOT, SRC, load_data
from p1_pick_gate_lab import gates
from p1_temporal_proxy_lab import temporal_trace
from research_package_a import collect, label_reference

PROTOCOL = "RPENT_P1_TEMPORAL_PROXY_FOLLOWUP_V1"
OUT = ROOT / "artifacts" / "p1_temporal_proxy_lab"
SEED = 20261012
BOOT = 1000


def join(src=SRC, root=ROOT):
    """Rebuild the validated 206-row join with per-row terminal proxy state.

    Same qualification chain as p1_temporal_proxy_lab.run(): frozen views,
    sealed source hashes, per-row flag/reference equality, gate diagnostics.
    """
    frozen = load_data(src, strict=True)
    expected = {(r["episode_id"], r["step_idx"]): r for r in frozen}
    qa = json.loads((src / "schema_qa.json").read_text(encoding="utf-8"))
    provenance, _, original, errors = collect(root)
    if errors:
        raise ValueError(f"Frozen trace parser reports {len(errors)} schema problems")
    if provenance != qa.get("source_sha256"):
        raise ValueError("Source hashes do not match sealed A0 schema_qa.json")
    rows = []
    for item in original:
        key = (item["episode_id"], item["step_idx"])
        if key not in expected:
            continue  # terminal-involved rows excluded from frozen PRIMARY
        if item["result"].get("libero_terminated") is not False:
            raise ValueError("Unexpected terminal in frozen PRIMARY")
        row = expected[key]
        if item["result"].get("success") is not row["tool_report"]["success"]:
            raise ValueError("Original tool flag differs from A-online")
        proxy = temporal_trace(item["points"], item["point_status"])
        if proxy["frozen_any_positive"] != row["reference"]:
            raise ValueError("Temporal ANY does not reproduce frozen FGONLY A0 reference")
        if label_reference(item["points"], item["point_status"]) != (
                "POSITIVE" if row["reference"] else "NEGATIVE"):
            raise ValueError("Reference function mismatch")
        gbits = gates(row["tool_report"])
        if gbits is None:
            raise ValueError("Missing tool gate diagnostics")
        diag = row["tool_report"].get("diagnostics") or {}
        rows.append({
            "episode_id": key[0], "task": row["task"],
            "flag": row["tool_report"]["success"],
            "reference_any": row["reference"],
            "reference_terminal": proxy["terminal"] == "POSITIVE",
            "terminal_unknown": proxy["terminal"] == "UNKNOWN",
            "gate_pattern": "".join("1" if gbits[k] else "0"
                                    for k in ("D", "L", "G_final")),
            "start_eef_z": diag.get("start_eef_z"),
            "descent_m": diag.get("descent_m"),
        })
    if len(rows) != 206 or len({r["episode_id"] for r in rows}) != 175:
        raise ValueError("Frozen join is incomplete or duplicates")
    return rows


def arm_predict(row, arm):
    """Frozen arms only; L_AND_Gfinal read from the validated gate pattern."""
    if arm == "flag":
        return row["flag"]
    if arm == "L_AND_Gfinal":
        return row["gate_pattern"][1] == "1" and row["gate_pattern"][2] == "1"
    raise ValueError(f"Unknown frozen arm {arm}")


def confusion(rows, arm, horizon):
    key = "reference_any" if horizon == "any" else "reference_terminal"
    tp = fp = fn = tn = 0
    for r in rows:
        pred, actual = arm_predict(r, arm), r[key]
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
        elif not pred and actual:
            fn += 1
        else:
            tn += 1
    sens = tp / (tp + fn) if tp + fn else None
    spec = tn / (tn + fp) if tn + fp else None
    bacc = (sens + spec) / 2 if sens is not None and spec is not None else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "sensitivity": round(sens, 4) if sens is not None else None,
            "specificity": round(spec, 4) if spec is not None else None,
            "bacc": round(bacc, 4) if bacc is not None else None}


def fn_decomposition(rows):
    """56 proxy FNs split by gate pattern and exit persistence."""
    fn = [r for r in rows if not r["flag"] and r["reference_any"]]
    if len(fn) != 56:
        raise ValueError("Frozen FN denominator changed")
    d_only = [r for r in fn if r["gate_pattern"] == "011"]
    lg_missing = [r for r in fn if r["gate_pattern"] not in ("011", "111")]
    persistent = lambda rs: sum(r["reference_terminal"] for r in rs)
    return {
        "n_fn": len(fn),
        "n_exit_persistent": persistent(fn),
        "n_transient": len(fn) - persistent(fn) - sum(r["terminal_unknown"] for r in fn),
        "n_terminal_unknown": sum(r["terminal_unknown"] for r in fn),
        "exit_persistent_fn_pattern": dict(sorted(Counter(
            r["gate_pattern"] for r in fn if r["reference_terminal"]).items())),
        "d_only_fn": {
            "n": len(d_only),
            "n_exit_persistent": persistent(d_only),
            "exit_persistent_rate": round(persistent(d_only) / len(d_only), 4)
            if d_only else None,
        },
        "lg_missing_fn": {
            "n": len(lg_missing),
            "n_exit_persistent": persistent(lg_missing),
            "exit_persistent_rate": round(persistent(lg_missing) / len(lg_missing), 4)
            if lg_missing else None,
        },
    }


def _bacc(rows, arm, horizon):
    m = confusion(rows, arm, horizon)
    return m["bacc"]


def paired_bootstrap(rows, repeats=BOOT, seed=SEED):
    """Episode-cluster paired bootstrap of BAcc(L_AND_Gfinal - flag) at exit."""
    rng = random.Random(seed)
    episodes = sorted({r["episode_id"] for r in rows})
    by_ep = defaultdict(list)
    for r in rows:
        by_ep[r["episode_id"]].append(r)
    deltas = []
    for _ in range(repeats):
        sample = []
        for _ in episodes:
            sample.extend(by_ep[rng.choice(episodes)])
        a = _bacc(sample, "L_AND_Gfinal", "terminal")
        b = _bacc(sample, "flag", "terminal")
        if a is not None and b is not None:
            deltas.append(a - b)
    deltas.sort()
    n = len(deltas)
    if not n:
        return None
    return {
        "repeats": repeats, "seed": seed, "n_valid": n,
        "median": round(statistics.median(deltas), 4),
        "p2_5": round(deltas[int(0.025 * n)], 4),
        "p97_5": round(deltas[min(n - 1, int(0.975 * n))], 4),
        "frac_ge0": round(sum(d >= 0 for d in deltas) / n, 4),
    }


def donly_geometry(rows):
    """Aggregate medians for D-only proxy FNs by exit persistence (audit-safe)."""
    out = {}
    for task in sorted({r["task"] for r in rows}):
        fn = [r for r in rows if r["task"] == task and not r["flag"]
              and r["reference_any"] and r["gate_pattern"] == "011"]
        entry = {"n_d_only_fn": len(fn)}
        for label, want in (("exit_persistent", True), ("transient", False)):
            sub = [r for r in fn if r["reference_terminal"] is want]
            def med(field):
                vals = [r[field] for r in sub
                        if isinstance(r[field], (int, float))]
                return round(statistics.median(vals), 4) if vals else None
            entry[label] = {
                "n": len(sub),
                "median_start_eef_z": med("start_eef_z"),
                "median_descent_m": med("descent_m"),
            }
        out[task] = entry
    return out


def hypothesis_gate(rows):
    """H-a/H-b/H-c/H-T2, stated in the module docstring before the real run."""
    dec = fn_decomposition(rows)
    flag_any = confusion(rows, "flag", "any")
    flag_term = confusion(rows, "flag", "terminal")
    lg_term = confusion(rows, "L_AND_Gfinal", "terminal")
    persistent_share_011 = (
        dec["exit_persistent_fn_pattern"].get("011", 0)
        / dec["n_exit_persistent"] if dec["n_exit_persistent"] else None)
    delta_term = (lg_term["bacc"] - flag_term["bacc"]
                  if lg_term["bacc"] is not None and flag_term["bacc"] is not None
                  else None)
    return {
        "H_a_flag_confusions_stable": (
            flag_any["tp"] == 101 and flag_any["fp"] == 2
            and dec["n_exit_persistent"] == 26 and dec["n_terminal_unknown"] == 0),
        "H_b_persistent_fn_mostly_d_only": (
            persistent_share_011 is not None and persistent_share_011 >= 0.90),
        "H_c_persistence_split": (
            dec["d_only_fn"]["exit_persistent_rate"] is not None
            and dec["d_only_fn"]["exit_persistent_rate"] >= 0.70
            and dec["lg_missing_fn"]["exit_persistent_rate"] is not None
            and dec["lg_missing_fn"]["exit_persistent_rate"] <= 0.15),
        "H_T2_drop_d_gain_is_horizon_artifact": (
            delta_term is not None and abs(delta_term) <= 0.02),
        "detail": {
            "persistent_fn_share_pattern_011": round(persistent_share_011, 4)
            if persistent_share_011 is not None else None,
            "delta_bacc_terminal_L_AND_Gfinal_vs_flag": delta_term,
            "delta_bacc_any_horizon_reference": 0.8553 - 0.8012,
        },
    }


def run(src=SRC, root=ROOT):
    rows = join(src=src, root=root)
    result = {
        "protocol": PROTOCOL,
        "scope": "RETROSPECTIVE_WITHIN_SKILL_WEAK_PROXY_ONLY",
        "n_rows": len(rows),
        "arms": {
            arm: {"any_horizon": confusion(rows, arm, "any"),
                  "exit_horizon": confusion(rows, arm, "terminal")}
            for arm in ("flag", "L_AND_Gfinal")
        },
        "fn_decomposition": fn_decomposition(rows),
        "hypotheses": hypothesis_gate(rows),
        "paired_bootstrap_exit_horizon": paired_bootstrap(rows),
        "d_only_geometry_by_task": donly_geometry(rows),
        "contract": [
            "Exit-time FGONLY is the same kinematic weak proxy evaluated at final_meas; NOT held-grasp truth.",
            "Arms/thresholds frozen from p1_pick_gate_lab; the horizon is the only manipulated variable.",
            "H-a/H-b/H-c are cross-validation of the published aggregate; H-T2 and geometry are new measurements.",
            "No threshold selection, no posthoc arm choice; descriptive only.",
        ],
    }
    # Cross-check against the already published temporal aggregate, if present.
    published = OUT / "temporal_proxy_v1.json"
    if published.exists():
        pub = json.loads(published.read_text(encoding="utf-8"))
        mine = Counter((r["task"], r["gate_pattern"],
                        "EVER_POS_TERMINAL_POS" if r["reference_terminal"]
                        else "EVER_POS_TERMINAL_NEG" if not r["terminal_unknown"]
                        else "EVER_POS_TERMINAL_UNKNOWN")
                       for r in rows
                       if not r["flag"] and r["reference_any"])
        theirs = Counter()
        for task, block in pub["by_task_gate_failure"].items():
            for cell in block["gate_pattern_class"]:
                theirs[(task, cell["gates_D_L_Gfinal"], cell["temporal_class"])] = cell["n"]
        result["crosscheck_vs_temporal_v1"] = "MATCH" if mine == theirs else "MISMATCH"
        if mine != theirs:
            result["hypotheses"]["H_a_flag_confusions_stable"] = False
    return result


def main():
    pa = argparse.ArgumentParser(description=__doc__)
    pa.add_argument("--input", type=Path, default=SRC)
    pa.add_argument("--output", type=Path, default=OUT)
    args = pa.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / "artifacts").resolve()):
        pa.error("Output must stay within private gitignored artifacts")
    result = run(src=args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / "followup_v1.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "protocol": result["protocol"],
        "crosscheck_vs_temporal_v1": result.get("crosscheck_vs_temporal_v1"),
        "arms": result["arms"],
        "fn_decomposition": result["fn_decomposition"],
        "hypotheses": result["hypotheses"],
        "paired_bootstrap_exit_horizon": result["paired_bootstrap_exit_horizon"],
        "d_only_geometry_by_task": result["d_only_geometry_by_task"],
        "output_path": str(target),
        "warning": "Exit-time FGONLY is a kinematic proxy at final_meas, NOT grasp truth",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
