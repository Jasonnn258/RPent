#!/usr/bin/env python3
"""RPent H0 OE Stage2D -- STRICTLY offline analysis of frozen retrospective protocol v1.

No VLA, no simulator, no network, no mutation of repo/data files. STDOUT JSON.
The preflight mode does NOT inspect outcome values or calculate any outcome statistics.
The run mode requires separately approved Stage2D user authorization.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

BASE_COMMIT = "10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a"
FREEZE_ID = "H0-OE-STAGE2C-20261009-V1"
FROZEN_PROTOCOL = "analysis/harness_h0/H0_OE_STAGE2C_FROZEN_PREREG.md"
FROZEN_PROTOCOL_BLOB = "97dc0bc93bae857620554a7c2571c5b0b55b5528"
DATA_BLOBS = {
    "analysis/stageR_manifest.csv": "3972e58f5b356f141fc46c4c9e7da600eb723cfe",
    "analysis/stageR_same_action_rollouts.csv": "966dced03ba26f3357bbc7d7f2f1c31e547e162c",
    "analysis/stageR_resample_rollouts.csv": "919906ce8f6c7db38dbf226f41210793a6b9e351",
    "analysis/stageR_failure_events.jsonl": "74e15deb7c42ce8306d4752c7d4401b7954d824e",
    "analysis/stageR_event_probabilities.csv": "5ec8a3c0a9044410ebc25cc36b60af1b4f4a069e",
    "analysis/stageR_prereg.md": "0eba5d6098bbd61703d59451311525ebe947d6f1",
    "analysis/STAGE_R_FINAL_REPORT.md": "96f58e0c40982780d41c8593bbbab9c865ea1375",
    "scripts/stageR1_run.py": "3afb9c8334c130d4f3866f1dfcd972b0ec0e6c2f",
    "scripts/stageR_rt.py": "526f3aaff8623c737dc8e8675ec583eaadc0c3aa",
    "scripts/stageQ_rt.py": "356901453e0d4715196424709c617927e7088875",
}
TAUS = (0.5, 1, 2, 4, 8, 16, 32, 64, 128)
MUS = tuple(i / 20 for i in range(1, 20))
BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 20261007
MIN_PRIMARY_EVENTS = 12


class ProtocolStop(Exception):
    """A frozen-protocol precondition was violated. No fallback."""


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def checked_blob(path: Path, sha: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ProtocolStop(f"STOP_INPUT_FILE_MISSING_OR_SYMLINK: {path}")
    actual = git_blob_sha(path.read_bytes())
    if actual != sha:
        raise ProtocolStop(f"STOP_INPUT_HASH_MISMATCH: {path} expected={sha} actual={actual}")


def check_base_git_tree(repo: Path) -> None:
    """Read only: assert pinned commit in git DB and every referenced blob at that commit."""
    for name, sha in DATA_BLOBS.items():
        try:
            p = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", f"{BASE_COMMIT}:{name}"],
                text=True, capture_output=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProtocolStop(f"STOP_GIT_OBJECT_VERIFICATION_UNAVAILABLE: {exc}") from exc
        if p.returncode != 0 or p.stdout.strip() != sha:
            raise ProtocolStop(f"STOP_PINNED_COMMIT_OR_BLOB_MISMATCH: {name}: {p.stderr.strip()}")


def preflight_hashes(repo: Path, script_blob: str) -> None:
    checked_blob(Path(__file__).resolve(), script_blob)
    checked_blob(repo / FROZEN_PROTOCOL, FROZEN_PROTOCOL_BLOB)
    check_base_git_tree(repo)
    for name, sha in DATA_BLOBS.items():
        checked_blob(repo / name, sha)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames or len(rdr.fieldnames) != len(set(rdr.fieldnames)):
            raise ProtocolStop(f"STOP_CSV_SCHEMA: {path}")
        rows = list(rdr)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ProtocolStop(f"STOP_CSV_ROW_WIDTH: {path}")
    return rows


def structural_scan(repo: Path):
    """Only structural columns, no outcome value access (even in preflight)."""
    manifest = read_csv(repo / "analysis/stageR_manifest.csv")
    if len(manifest) != 32 or len({r["event_id"] for r in manifest}) != 32:
        raise ProtocolStop("STOP_MANIFEST_SIZE_OR_DUPLICATES")
    cohort = [r for r in manifest if r["role"] == "R1_COHORT"]
    dev = [r for r in manifest if r["role"] == "R0_DEV"]
    if len(cohort) != 24 or len(dev) != 8:
        raise ProtocolStop("STOP_COHORT_SELECTION")
    if len({r["ord"] for r in manifest}) != 32:
        raise ProtocolStop("STOP_MANIFEST_ORD_DUPLICATES")
    cohort = sorted(cohort, key=lambda r: int(r["ord"]))
    m = {r["event_id"]: r for r in cohort}
    by_arm: dict[str, dict[str, dict[int, dict[str, str]]]] = {
        "SAME": {}, "RESAMPLE": {}, "NATURAL": {},
    }
    expected_cols = {
        "event_id", "arm", "trial", "task", "seed", "t0", "stable", "acquisition"
    }
    file_expectation = [
        ("stageR_same_action_rollouts.csv", {"SAME"}),
        ("stageR_resample_rollouts.csv", {"RESAMPLE", "NATURAL"}),
    ]
    counts = Counter()
    for filename, arms in file_expectation:
        rows = read_csv(repo / "analysis" / filename)
        if not rows or not expected_cols.issubset(rows[0]):
            raise ProtocolStop(f"STOP_TRIAL_SCHEMA: {filename}")
        for r in rows:
            arm, event_id = r["arm"], r["event_id"]
            if arm not in arms or event_id not in m:
                raise ProtocolStop(f"STOP_NON_COHORT_OR_WRONG_ARM: {event_id}/{arm}")
            try:
                t = int(r["trial"])
            except ValueError as exc:
                raise ProtocolStop("STOP_NON_INTEGER_TRIAL") from exc
            k = 4 if arm == "NATURAL" else 8
            if not 1 <= t <= k:
                raise ProtocolStop(f"STOP_OUT_OF_RANGE_TRIAL: {event_id}/{arm}/{t}")
            if any(r[field] != m[event_id][field] for field in ("task", "seed", "t0")):
                raise ProtocolStop(f"STOP_MANIFEST_TRIAL_METADATA_MISMATCH: {event_id}")
            if t in by_arm[arm].setdefault(event_id, {}):
                raise ProtocolStop(f"STOP_DUPLICATE_TRIAL: {event_id}/{arm}/{t}")
            by_arm[arm][event_id][t] = r
            counts[arm] += 1
    for arm, groups in by_arm.items():
        required = set(range(1, 5 if arm == "NATURAL" else 9))
        if set(groups) != set(m):
            raise ProtocolStop(f"STOP_ARM_EVENT_COVERAGE: {arm}")
        for event, trials in groups.items():
            if set(trials) != required:
                raise ProtocolStop(f"STOP_TRIAL_COVERAGE: {event}/{arm}")
    if dict(counts) != {"SAME": 192, "RESAMPLE": 192, "NATURAL": 96}:
        raise ProtocolStop(f"STOP_TRIAL_COUNT: {dict(counts)}")
    return cohort, by_arm, dict(counts)


def parse_bit(value: str, context: str) -> int:
    if value in ("True", "true", "1"):
        return 1
    if value in ("False", "false", "0"):
        return 0
    raise ProtocolStop(f"STOP_INVALID_OUTCOME_ENCODING: {context}")


def extract_outcomes(cohort, by_arm):
    outcomes = {arm: {} for arm in ("SAME", "RESAMPLE")}
    for arm in outcomes:
        for ev in cohort:
            event = ev["event_id"]
            result = {}
            for trial, row in by_arm[arm][event].items():
                stable = parse_bit(row["stable"], f"{event}/{arm}/{trial}/stable")
                acq = parse_bit(row["acquisition"], f"{event}/{arm}/{trial}/acquisition")
                if stable and not acq:
                    raise ProtocolStop(f"STOP_CONTRACT_NESTING_VIOLATION: {event}/{arm}/{trial}")
                result[trial] = {"stable": stable, "acquisition": acq}
            outcomes[arm][event] = result
    return outcomes


def logbeta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def fit_m1(training_counts: list[int]):
    if len(training_counts) != 23 or any(not (0 <= x <= 8) for x in training_counts):
        raise ProtocolStop("STOP_M1_TRAINING_GROUPS")
    best = None
    best_score = -math.inf
    for mu in MUS:
        for tau in TAUS:
            a, b = mu * tau, (1 - mu) * tau
            base = logbeta(a, b)
            score = sum(logbeta(a + cnt, b + 8 - cnt) - base for cnt in training_counts)
            if not math.isfinite(score):
                continue
            if (best is None or score > best_score + 1e-10 or
                (abs(score - best_score) <= 1e-10 and
                 (tau > best[1] or (tau == best[1] and mu < best[0])))):
                best, best_score = (mu, tau), score
    if best is None:
        raise ProtocolStop("M1_FIT_FAILED")
    return best[0] * best[1], (1 - best[0]) * best[1], best[0], best[1]


def predictions_for_arm(cohort, events, arm):
    ids = [m["event_id"] for m in cohort]
    counts = {e: sum(events[e][t]["stable"] for t in range(1, 9)) for e in ids}
    preds = {}
    for e in ids:
        training = [counts[j] for j in ids if j != e]
        a, b, mu, tau = fit_m1(training)
        success_train = sum(training)
        preds[e] = {"s": counts[e], "mu": mu, "tau": tau,
                    "pred0_base_success": success_train,
                    "a": a, "b": b}
    return preds


def loss_for_prefix(cohort, events, preds, k: int):
    ids = [m["event_id"] for m in cohort]
    pairs = []
    tasks = Counter()
    for m in cohort:
        e = m["event_id"]
        if any(events[e][t]["stable"] != 0 for t in range(1, k + 1)):
            continue
        fit = preds[e]
        p0 = (1 + fit["pred0_base_success"]) / (2 + 8 * 23 + k)
        p1 = fit["a"] / (fit["a"] + fit["b"] + k)
        target = events[e][k + 1]["stable"]
        if not (0 <= p0 <= 1 and 0 <= p1 <= 1):
            raise ProtocolStop("STOP_INVALID_PREDICTION_RANGE")
        l0, l1 = (target - p0)**2, (target - p1)**2
        tasks[m["task"]] += 1
        pairs.append({"event_id": e, "m0_loss": l0, "m1_loss": l1, "delta": l0 - l1})
    if not pairs:
        return {"eligible_event_n": 0, "task_counts": dict(tasks), "status": "INCONCLUSIVE"}, []
    n = len(pairs)
    summary = {"eligible_event_n": n, "task_counts": dict(sorted(tasks.items())),
               "m0_mean_brier": sum(x["m0_loss"] for x in pairs) / n,
               "m1_mean_brier": sum(x["m1_loss"] for x in pairs) / n,
               "mean_delta_m0_minus_m1": sum(x["delta"] for x in pairs) / n}
    return summary, pairs


def percentile(values: list[float], prob: float) -> float:
    if not 0 <= prob <= 1 or not values:
        raise ProtocolStop("STOP_PERCENTILE_INPUT")
    x = sorted(values)
    pos = (len(x) - 1) * prob
    a, b = math.floor(pos), math.ceil(pos)
    return x[a] + (x[b] - x[a]) * (pos - a)


def descriptive_bootstrap(pairs):
    n = len(pairs)
    vals = [p["delta"] for p in pairs]
    rng = random.Random(BOOTSTRAP_SEED)
    draws = [sum(vals[rng.randrange(n)] for _ in range(n)) / n
             for _ in range(BOOTSTRAP_N)]
    return [percentile(draws, 0.025), percentile(draws, 0.975)]


def outcome_discordance(cohort, arm_events):
    a_sum = y_sum = d_sum = 0
    for m in cohort:
        ev = m["event_id"]
        for t in range(1, 9):
            row = arm_events[ev][t]
            a_sum += row["acquisition"]
            y_sum += row["stable"]
            d_sum += row["acquisition"] - row["stable"]
    n = len(cohort) * 8
    return {"trials": n, "p_acquisition": a_sum / n, "p_stable": y_sum / n,
            "same_source_contract_disagreement": d_sum / n,
            "conditional_disagreement_given_acquisition": d_sum / a_sum if a_sum else None,
            "note": "same-source nested contract disagreement, NOT independent FPR"}


def run_analysis(cohort, by_arm):
    events = extract_outcomes(cohort, by_arm)
    preds = {arm: predictions_for_arm(cohort, events[arm], arm)
             for arm in ("SAME", "RESAMPLE")}
    primary, pairs = loss_for_prefix(cohort, events["SAME"], preds["SAME"], 2)
    if primary["eligible_event_n"] < MIN_PRIMARY_EVENTS:
        primary["status"] = "INCONCLUSIVE_DESCRIPTIVE_ONLY_SMALL_RISK_SET"
        primary["descriptive_bootstrap_percentile_interval"] = None
    else:
        primary["status"] = ("M1_LOWER_OBSERVED_BRIER_IN_RETROSPECTIVE_COHORT"
                             if primary["mean_delta_m0_minus_m1"] > 0
                             else "NO_OBSERVED_BRIER_ADVANTAGE")
        primary["descriptive_bootstrap_percentile_interval"] = descriptive_bootstrap(pairs)
    explorer = {}
    for arm, ks in (("SAME", (0, 1, 3)), ("RESAMPLE", (0, 1, 2, 3))):
        explorer[arm] = {str(k): loss_for_prefix(cohort, events[arm], preds[arm], k)[0]
                         for k in ks}
    boundary_hits = {arm: sum(1 for p in values.values()
                              if p["mu"] in (MUS[0], MUS[-1]) or p["tau"] in (TAUS[0], TAUS[-1]))
                     for arm, values in preds.items()}
    return {
        "primary_oe2a": primary,
        "secondary_oe1a": {arm: outcome_discordance(cohort, events[arm])
                           for arm in ("SAME", "RESAMPLE")},
        "exploratory_oe3a": explorer,
        "m1_boundary_fold_counts": boundary_hits,
        "scientific_scope": "RETROSPECTIVE_INTERNAL_VALIDATION_ONLY",
        "causal_grade": "UNIDENTIFIED",
        "oe1b_independent_reference": "NOT_IDENTIFIABLE_ON_AUDITED_SOURCES",
        "runtime_evolution_eligibility": "NOT_AUTHORIZED",
        "novel_algorithm_established": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="hashes and keys ONLY")
    mode.add_argument("--run", action="store_true", help="compute frozen offline model outcomes")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--expected-script-blob", required=True,
                        help="reviewed script's Git blob SHA-1")
    a = parser.parse_args(argv)
    try:
        repo = a.repo.expanduser().resolve(strict=True)
        preflight_hashes(repo, a.expected_script_blob)
        cohort, by_arm, counts = structural_scan(repo)
        output = {
            "protocol": FREEZE_ID,
            "source_commit": BASE_COMMIT,
            "script_git_blob_sha1": a.expected_script_blob,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "rng": "Python stdlib random.Random / MT19937",
            "input_hashes": "PASS_ALL_PINNED_BLOBS",
            "preflight": "PASS",
            "cohort_events": len(cohort),
            "trial_counts": counts,
            "mode": "PREFLIGHT_ONLY" if a.preflight else "APPROVED_OFFLINE_RUN",
        }
        if a.run:
            output.update(run_analysis(cohort, by_arm))
        print(json.dumps(output, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except ProtocolStop as exc:
        print(f"STAGE2D_STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
