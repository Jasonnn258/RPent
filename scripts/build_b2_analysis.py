#!/usr/bin/env python3
"""build_b2_analysis.py — assemble the B2 (state-transition verification)
experiment's report artifacts from the master run CSV + episode dirs.

Outputs (analysis/):
  b2_runs.csv                  per-episode B2 metrics (dev2 + stage1 armB2)
  b2_pairs.csv                 paired outcomes vs armA/armB, flip directions
  b2_verification_events.jsonl every b2_events.jsonl event, stage-tagged
  b2_stats.json                the aggregate numbers behind b2_summary.md

Episodes whose structured_metrics.json is missing (e.g. planner-timeout
early return) get their B2 snapshot reconstructed by replaying the episode
transcript through the (frozen) verifier — same code path, offline.

Usage:  python scripts/build_b2_analysis.py   # re-runnable as rows land
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from rpent.memory.stv import TransitionVerifier  # noqa: E402
from replay_b2_offline import PhaseApprox, transcript_stream  # noqa: E402

RUNS_CSV = ROOT / "analysis" / "outcome_validation_runs.csv"
OUT = ROOT / "analysis"

RUN_FIELDS = [
    "stage", "task", "seed", "repeat", "result", "success",
    "n_confirmed_success", "n_confirmed_failure", "n_uncertain",
    "false_positive_caught", "n_observe_directives", "n_observe_obeyed",
    "obey_rate", "n_reason_escalations", "n_redundant_obs",
    "resolved_success", "resolved_failure", "resolved_reason", "overtaken",
    "unresolved", "commit_events", "recovery_events",
    "commit_latency_mean", "recovery_latency_mean",
    "same_tool_repeated", "finish_claim", "false_success_episode",
    "n_picks", "wall_s", "metrics_source", "dir",
]

PAIR_FIELDS = ["stage", "task", "seed", "repeat",
               "res_A", "res_B1", "res_B2",
               "b2_vs_b1", "b2_vs_a"]


def load_b2_snapshot(d: Path) -> tuple[dict, str]:
    """(b2 snapshot dict, source) for one armB2 episode dir."""
    m = d / "structured_metrics.json"
    if m.exists():
        try:
            blob = json.loads(m.read_text())
            if blob.get("b2"):
                return blob["b2"], "structured_metrics"
        except Exception:
            pass
    # offline reconstruction from the transcript (frozen verifier)
    if next(d.glob("transcript_*.json"), None) is not None:
        task = ""
        parts = d.name.split("_t")
        if len(parts) > 1:
            task = parts[1].split("_")[0]
        ph = PhaseApprox()
        v = TransitionVerifier(tracker=ph, task=task)
        for name, kwargs, text in transcript_stream(d):
            if name:
                ph.on_call(name)
                v.observe_result(name, kwargs, text, phase=ph.current_phase())
        snap = v.snapshot(success=False)
        snap["replayed"] = True
        return snap, "transcript_replay"
    return {}, "missing"


def finish_claim(d: Path) -> str:
    """"success"/"failure"/"" — the planner's own last finish() claim."""
    t = next(d.glob("transcript_*.json"), None)
    if t is None:
        return ""
    try:
        msgs = json.loads(t.read_text())["messages"]
    except Exception:
        return ""
    claims = []
    for m in msgs:
        if m.get("role") == "assistant":
            for b in m.get("content", []):
                if (isinstance(b, dict) and b.get("type") == "tool_use"
                        and b.get("name") == "finish"):
                    claims.append(str((b.get("input") or {}).get("status", "")))
    return claims[-1] if claims else ""


def n_picks(d: Path) -> int:
    t = next(d.glob("transcript_*.json"), None)
    if t is None:
        return ""
    try:
        msgs = json.loads(t.read_text())["messages"]
    except Exception:
        return ""
    n = 0
    for m in msgs:
        if m.get("role") == "assistant":
            for b in m.get("content", []):
                if (isinstance(b, dict) and b.get("type") == "tool_use"
                        and b.get("name") in ("pi0_pick", "pi0_doubled")):
                    n += 1
    return n


def arm_rows(stage_conds: list[tuple[str, str]]) -> dict[str, dict]:
    """{(task,seed,repeat): row} per requested (stage, cond)."""
    out: dict[str, dict] = {}
    with open(RUNS_CSV) as f:
        for r in csv.DictReader(f):
            if (r["stage"], r["cond"]) in stage_conds and \
                    r["tier"] == "glm-5.3-flash":
                out.setdefault(
                    (r["stage"], r["cond"], r["task"], r["seed"], r["repeat"]),
                    r)
    return out


def main() -> None:
    rows = list(csv.DictReader(open(RUNS_CSV)))

    # ---------------- per-episode B2 table ----------------
    b2_eps = [r for r in rows if r["cond"] == "armB2"
              and r["tier"] == "glm-5.3-flash"
              and r["stage"] in ("dev2", "stage1")]
    run_rows = []
    ev_out = open(OUT / "b2_verification_events.jsonl", "w")
    n_ev = 0
    for r in b2_eps:
        d = Path(r["dir"])
        with redirect_stdout(io.StringIO()):  # replay prints nothing anyway
            snap, src = load_b2_snapshot(d)
        res = snap.get("uncertain_resolutions") or {}
        claim = finish_claim(d)
        false_ep = int(claim == "success" and r["result"] != "success")
        rec_events = snap.get("commit_events", []) + snap.get(
            "recovery_events", [])
        run_rows.append({
            "stage": r["stage"], "task": r["task"], "seed": r["seed"],
            "repeat": r["repeat"], "result": r["result"],
            "success": int(r["result"] == "success"),
            "n_confirmed_success": snap.get("n_confirmed_success", ""),
            "n_confirmed_failure": snap.get("n_confirmed_failure", ""),
            "n_uncertain": snap.get("n_uncertain", ""),
            "false_positive_caught": snap.get("false_positive_caught", ""),
            "n_observe_directives": snap.get("n_observe_directives", ""),
            "n_observe_obeyed": snap.get("n_observe_obeyed", ""),
            "obey_rate": (round(snap["n_observe_obeyed"] /
                                snap["n_observe_directives"], 3)
                          if snap.get("n_observe_directives") else ""),
            "n_reason_escalations": snap.get("n_reason_escalations", ""),
            "n_redundant_obs": snap.get("n_redundant_observations", ""),
            "resolved_success": res.get("resolved_success", ""),
            "resolved_failure": res.get("resolved_failure", ""),
            "resolved_reason": res.get("resolved_reason", ""),
            "overtaken": res.get("overtaken", ""),
            "unresolved": res.get("unresolved", ""),
            "commit_events": len(snap.get("commit_events") or []),
            "recovery_events": len(snap.get("recovery_events") or []),
            "commit_latency_mean": snap.get("commit_latency_mean", ""),
            "recovery_latency_mean": snap.get("recovery_latency_mean", ""),
            "same_tool_repeated": sum(
                1 for e in rec_events
                if e.get("closed_by") == "same_tool_repeated"),
            "finish_claim": claim,
            "false_success_episode": false_ep,
            "n_picks": n_picks(d),
            "wall_s": r["wall_s"], "metrics_source": src, "dir": r["dir"],
        })
        # events (live jsonl preferred; replayed events come from the
        # snapshot's embedded list)
        evf = d / "b2_events.jsonl"
        if evf.exists():
            for line in evf.read_text().splitlines():
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                ev["stage"] = r["stage"]
                ev_out.write(json.dumps(ev, ensure_ascii=False) + "\n")
                n_ev += 1
        elif snap.get("events"):
            for ev in snap["events"]:
                ev = dict(ev)
                ev["stage"] = r["stage"]
                ev["replayed"] = True
                ev_out.write(json.dumps(ev, ensure_ascii=False) + "\n")
                n_ev += 1
    ev_out.close()

    with open(OUT / "b2_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_FIELDS)
        w.writeheader()
        w.writerows(run_rows)

    # ---------------- paired flips ----------------
    pair_rows = []
    grids = [
        ("dev", [("dev", "armA"), ("dev", "armB"), ("dev2", "armB2")]),
        ("stage1", [("stage1", "armA"), ("stage1", "armB"),
                    ("stage1", "armB2")]),
    ]
    by = {}
    with open(RUNS_CSV) as f:
        for r in csv.DictReader(f):
            by[(r["stage"], r["cond"], r["tier"], r["task"], r["seed"],
                r["repeat"])] = r
    for stage, conds in grids:
        keys = set()
        for sc in conds:
            keys |= {k[3:] for k in by if k[:3] == (sc[0], sc[1],
                                                    "glm-5.3-flash")}
        for t, s, rp in sorted(keys, key=lambda x: (int(x[0]), int(x[1]),
                                                    int(x[2]))):
            def res(sc):
                r = by.get((sc[0], sc[1], "glm-5.3-flash", t, s, rp))
                return r["result"] if r else ""
            a, b1, b2 = res(conds[0]), res(conds[1]), res(conds[2])
            if not (a or b1 or b2):
                continue

            def flip(x, y):
                if not x or not y:
                    return ""
                if (x == "success") == (y == "success"):
                    return "tie"
                return "b2_win" if x == "success" else "b2_loss"
            pair_rows.append({
                "stage": stage, "task": t, "seed": s, "repeat": rp,
                "res_A": a, "res_B1": b1, "res_B2": b2,
                "b2_vs_b1": flip(b2, b1), "b2_vs_a": flip(b2, a),
            })
    with open(OUT / "b2_pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PAIR_FIELDS)
        w.writeheader()
        w.writerows(pair_rows)

    # ---------------- aggregates ----------------
    stats: dict = {}
    for stage in ("dev2", "stage1"):
        eps = [x for x in run_rows if x["stage"] == stage]
        if not eps:
            continue
        n = len(eps)
        srv = sum(x["success"] for x in eps)

        def tot(field):
            return sum(int(x[field]) for x in eps
                       if x[field] != "" and x[field] is not None)
        lat_c = [x["commit_latency_mean"] for x in eps
                 if x["commit_latency_mean"] not in ("", None)]
        lat_r = [x["recovery_latency_mean"] for x in eps
                 if x["recovery_latency_mean"] not in ("", None)]
        base = by  # reuse
        stats[stage] = {
            "n_episodes": n,
            "SR_b2": f"{srv}/{n} ({srv/n:.1%})",
            "false_success_episodes_b2": tot("false_success_episode"),
            "fp_caught": tot("false_positive_caught"),
            "confirmed_success": tot("n_confirmed_success"),
            "confirmed_failure": tot("n_confirmed_failure"),
            "uncertain": tot("n_uncertain"),
            "observe_directives": tot("n_observe_directives"),
            "observe_obeyed": tot("n_observe_obeyed"),
            "obey_rate": (f"{tot('n_observe_obeyed')}/"
                          f"{tot('n_observe_directives')} "
                          f"({tot('n_observe_obeyed')/max(tot('n_observe_directives'),1):.0%})"),
            "reason_escalations": tot("n_reason_escalations"),
            "redundant_obs": tot("n_redundant_obs"),
            "uncertain_resolutions": {
                k: tot(k) for k in
                ("resolved_success", "resolved_failure", "resolved_reason",
                 "overtaken", "unresolved")},
            "commit_latency_mean_of_means": (
                round(sum(lat_c)/len(lat_c), 2) if lat_c else None),
            "recovery_latency_mean_of_means": (
                round(sum(lat_r)/len(lat_r), 2) if lat_r else None),
            "same_tool_repeated": tot("same_tool_repeated"),
            "n_picks_total": tot("n_picks"),
            "metrics_sources": dict(Counter(x["metrics_source"] for x in eps)),
        }
        # baseline SR on the same grid
        for cond, stage_src in (("A", "dev" if stage == "dev2" else "stage1"),
                                ("B", "dev" if stage == "dev2" else "stage1")):
            eps_b = [x for x in rows
                     if x["stage"] == stage_src and x["cond"] == f"arm{cond}"
                     and x["tier"] == "glm-5.3-flash"]
            if stage == "stage1":
                eps_b = [x for x in eps_b]
            if eps_b:
                srb = sum(x["result"] == "success" for x in eps_b)
                stats[stage][f"SR_arm{cond}"] = \
                    f"{srb}/{len(eps_b)} ({srb/len(eps_b):.1%})"
        # flips
        prs = [p for p in pair_rows if p["stage"] ==
               ("dev" if stage == "dev2" else "stage1")]
        for col, name in (("b2_vs_b1", "flips_vs_B1"),
                          ("b2_vs_a", "flips_vs_A")):
            c = Counter(p[col] for p in prs if p[col])
            stats[stage][name] = {
                "b2_win": c.get("b2_win", 0),
                "b2_loss": c.get("b2_loss", 0),
                "tie": c.get("tie", 0)}
        # episode-level false success for baselines (finish claim vs truth)
        for cond in ("A", "B"):
            stage_src = "dev" if stage == "dev2" else "stage1"
            fs = 0
            cnt = 0
            for x in rows:
                if x["stage"] != stage_src or x["cond"] != f"arm{cond}" \
                        or x["tier"] != "glm-5.3-flash":
                    continue
                claim = finish_claim(Path(x["dir"]))
                if claim:
                    cnt += 1
                    fs += int(claim == "success" and x["result"] != "success")
            stats[stage][f"false_success_episodes_arm{cond}"] = \
                f"{fs}/{cnt or 'n/a'}"

    stats["_events_total"] = n_ev
    with open(OUT / "b2_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
