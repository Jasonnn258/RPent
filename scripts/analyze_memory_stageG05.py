#!/usr/bin/env python3
"""Stage G0.5 causal-attribution analyzer (DEV five-arm, pre-registered).

Arms (analysis/stageG05_preregistration.md §1-2), all glm-5.3-flash,
libero_spatial_task x {t3,t5,t9} x s1-10 x r1, trigger v1_per_result,
NEUTRAL (common) query for every retrieving arm:

  P0 g05P0  injection none            (fires logged, nothing injected)
  P1 g05P1  reason_only  (F2)         (no retrieval)
  P2 g05P2  generic_refresh (F3)      (no retrieval)
  P3 g05P3  memory_only  (F4+cards)   (common query, Q0_FIXED)
  P4 g0D    full = G0-D REUSED rows   (common query, reason+cards)

Six pre-registered contrasts (§12): P1-P0, P2-P0, P3-P0, P4-P3, P4-P1,
INTERACTION (P4-P3)-(P1-P0). Stats reuse scripts/analyze_memory_stageG
frozen implementations verbatim (McNemar exact, paired bootstrap 10k seed
20260920, macro task-cluster CI).

Recovery metrics (§11) — frozen definitions only:
  recovery@3      >=1 PROGRESSING-labeled primitive within <=3 primitives
                  after the intervention turn (c2.label_stream — the
                  frozen progress_state labeler; no redesign)
  repeated_fail@3 count of STALLED primitives in the same window
  phase_change@3  >1 distinct observable action-family bucket
                  (PERCEPTION/PICK/MOVE/PLACE) among primitives in the
                  window (declared definition; run.log has no full phase
                  timeline — buckets reuse the frozen PHASE_BUCKET map)
  turns_after     planner turns from intervention to episode end
An intervention = a fire that actually injected (event carries
retrieval_tokens). P0's logged fires are the null reference.

Usage: python scripts/analyze_memory_stageG05.py
Writes: analysis/stageG05_runs.csv + stageG05_events.jsonl
        + stageG05_results.json + stageG05_results.md
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import analyze_memory_stageB as sb  # noqa: E402
import memory_stagec2_benchmark as c2  # noqa: E402
import analyze_memory_stageG0 as g0  # noqa: E402
from analyze_memory_stageG import (  # noqa: E402
    ep_events, ep_turns, macro_boot, mcnemar_exact, paired_boot,
)

TIER = "glm-5.3-flash"
SUITE = "libero_spatial_task"
TASKS = (3, 5, 9)
SEEDS = range(1, 11)
INFRA = ("infra_crash", "infra_timeout", "infra_missing")

G05_ARMS = {
    "P0": ("g05", "g05P0"),
    "P1": ("g05", "g05P1"),
    "P2": ("g05", "g05P2"),
    "P3": ("g05", "g05P3"),
    "P4": ("g0", "g0D"),   # REUSE — never re-run (prereg §0-1)
}
CONTRASTS = [("P1", "P0"), ("P2", "P0"), ("P3", "P0"), ("P4", "P3"),
             ("P4", "P1")]
# each pair (a, b) is reported as a-minus-b (P1->P0 = P1-P0 etc.);
# paired_sr(ra, rb) returns rb-ra, so we pass (b_cells, a_cells).

# observable action-family buckets (frozen PHASE_BUCKET semantics)
BUCKET = {"segment": "PERCEPTION", "back_project": "PERCEPTION",
          "detect": "PERCEPTION", "pi0_pick": "PICK",
          "pi0_doubled": "PICK", "move_to": "MOVE", "move_pose": "MOVE",
          "release": "PLACE"}


def log(msg):
    print(msg, flush=True)


def load_rows():
    rows = {}
    for r in sb.csv_dict():
        if r["tier"] != TIER or int(r["repeat"]) != 1:
            continue
        if r["stage"] not in ("g0", "g05"):
            continue
        if r["suite"] != SUITE or int(r["task"]) not in TASKS:
            continue
        if int(r["seed"]) not in SEEDS:
            continue
        k = (r["stage"], r["cond"], r["suite"], int(r["task"]),
             int(r["seed"]))
        rows[k] = r
    return rows


def arm_rows(rows, arm):
    stage, cond = G05_ARMS[arm]
    out, infra = {}, collections.Counter()
    for (st, c, su, t, s), r in rows.items():
        if st != stage or c != cond:
            continue
        if r["result"] in INFRA:
            infra[(t, s)] = r["result"]
            continue
        out[(t, s)] = r
    return out, infra


# ------------------------------------------------------------------ recovery
def recovery_stats(rows, lcache):
    n_int = rec3 = ph3 = 0
    rep_fails, turns_after = [], []
    per_ep_rec = []
    for k, r in sorted(rows.items()):
        ep = Path(r["dir"]).name
        if ep not in lcache:
            try:
                ctx = c2.EpisodeCtx(ep)
                lcache[ep] = [x for x in c2.label_stream(ctx)
                              if x[1] is not None]
            except Exception as exc:  # noqa: BLE001 - never crash the report
                log(f"  label_stream failed for {ep}: {exc}")
                lcache[ep] = []
        ls = lcache[ep]
        t_end = ep_turns(r)
        fires = ep_events(r)
        interventions = [e for e in fires if "retrieval_tokens" in e]
        ep_rec = False
        for e in interventions:
            T = e["turn"]
            n_int += 1
            win = [x for x in ls if T <= x[1] <= T + 3]
            ok = any(x[4] == "PROGRESSING" for x in win)
            rec3 += ok
            ep_rec |= ok
            buckets = {BUCKET.get(x[2]) for x in win} - {None}
            ph3 += len(buckets) > 1
            rep_fails.append(sum(1 for x in win if x[4] == "STALLED"))
            turns_after.append(max(0, t_end - T))
        per_ep_rec.append((interventions != [], ep_rec))
    n = len(rows)
    return {
        "episodes": n,
        "interventions": n_int,
        "int_per_ep": round(n_int / n, 2) if n else None,
        "recovery@3": round(rec3 / n_int, 3) if n_int else None,
        "ep_with_recovery@3": round(
            sum(1 for has, rec in per_ep_rec if has and rec)
            / max(1, sum(1 for has, _ in per_ep_rec if has)), 3),
        "phase_change@3": round(ph3 / n_int, 3) if n_int else None,
        "stalled_prims@3_mean": round(sum(rep_fails) / len(rep_fails), 2)
        if rep_fails else None,
        "turns_after_mean": round(sum(turns_after) / len(turns_after), 1)
        if turns_after else None,
    }


def token_stats(rows):
    fires = injected = 0
    toks = []
    walls = []
    for k, r in sorted(rows.items()):
        evs = ep_events(r)
        fires += len(evs)
        for e in evs:
            if "retrieval_tokens" in e:
                injected += 1
                toks.append(e["retrieval_tokens"])
        walls.append(float(r["wall_s"] or 0))
    n = len(rows)
    return {
        "fires": fires,
        "fires_per_ep": round(fires / n, 2) if n else None,
        "injections_per_ep": round(injected / n, 2) if n else None,
        "injected_tokens_per_ep": round(sum(toks) / n, 1) if n else None,
        "mean_block_tokens": round(sum(toks) / len(toks), 1) if toks
        else None,
        "wall_mean_s": round(sum(walls) / len(walls), 1) if walls else None,
    }


# ------------------------------------------------------------------ stats
def paired_sr(ra, rb):
    common = sorted(set(ra) & set(rb))
    va = {k: ra[k]["result"] == "success" for k in common}
    vb = {k: rb[k]["result"] == "success" for k in common}
    b = sum(1 for k in common if vb[k] and not va[k])
    c = sum(1 for k in common if va[k] and not vb[k])
    diff = (sum(vb.values()) - sum(va.values())) / len(common) if common \
        else None
    by_task = collections.defaultdict(list)
    for k in common:
        by_task[k[0]].append(float(vb[k]) - float(va[k]))
    return {
        "n_pairs": len(common),
        "flips_a_only_success": c, "flips_b_only_success": b,
        "net_wins_b_minus_a": b - c,
        "ties": len(common) - b - c,
        "diff_micro": round(diff, 3) if diff is not None else None,
        "mcnemar_p": round(mcnemar_exact(b, c), 5)
        if mcnemar_exact(b, c) is not None else None,
        "ci95_micro": [round(x, 3) for x in paired_boot(common, va, vb)]
        if common else None,
        "ci95_macro_cluster": [round(x, 3) for x in macro_boot(by_task)]
        if by_task else None,
        "nonneg_tasks": sum(1 for v in by_task.values()
                            if sum(v) >= 0) if by_task else None,
    }


def interaction_contrast(cells, vp0, vp1, vp3, vp4):
    """(P4-P3) - (P1-P0) per paired cell; bootstrap of the mean."""
    diffs = {k: (float(vp4[k]) - float(vp3[k]))
             - (float(vp1[k]) - float(vp0[k])) for k in cells}
    mean = sum(diffs.values()) / len(cells) if cells else None
    lo, hi = paired_boot(sorted(cells), {k: 0.0 for k in cells}, diffs) \
        if cells else (None, None)
    return {
        "n_cells": len(cells),
        "interaction_diff": round(mean, 3) if mean is not None else None,
        "ci95": [round(lo, 3), round(hi, 3)] if cells else None,
    }


# ------------------------------------------------------------------ writers
def write_runs_csv(res):
    path = REPO / "analysis" / "stageG05_runs.csv"
    fields = ["arm", "stage", "cond", "task", "seed", "result", "success",
              "infra", "turns", "wall_s", "fires", "injections",
              "injected_tokens", "recovery_any", "stalled@3"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for arm in G05_ARMS:
            for d in res["arms"][arm]["episodes_detail"]:
                w.writerow(d)
    log(f"wrote {path}")


def write_events_jsonl(res):
    path = REPO / "analysis" / "stageG05_events.jsonl"
    n = 0
    with open(path, "w") as f:
        for arm in G05_ARMS:
            for ev in res["arms"][arm]["events"]:
                ev = dict(ev)
                ev["arm"] = arm
                ev.setdefault("injection_mode", "full")  # P4 historical rows
                f.write(json.dumps(ev, ensure_ascii=False, default=str)
                        + "\n")
                n += 1
    log(f"wrote {path} ({n} events)")


# ------------------------------------------------------------------ main
def main():
    rows = load_rows()
    mcache, lcache = {}, {}
    res = {"arms": {}, "contrasts": {}, "interaction": {}, "infra": {}}
    for arm in G05_ARMS:
        rr, infra = arm_rows(rows, arm)
        stage, cond = G05_ARMS[arm]
        sr = g0.sr_stats(rr)
        tg = g0.trigger_stats(arm, rr, mcache)  # v1 family classes
        rc = recovery_stats(rr, lcache)
        tk = token_stats(rr)
        detail = []
        evs_out = []
        for (t, s), r in sorted(rr.items()):
            evs = ep_events(r)
            interventions = [e for e in evs if "retrieval_tokens" in e]
            # per-episode recovery flag
            ep = Path(r["dir"]).name
            ls = lcache.get(ep, [])
            rec_any = False
            for e in interventions:
                T = e["turn"]
                rec_any |= any(x[4] == "PROGRESSING" for x in ls
                               if T <= x[1] <= T + 3)
            stalled = sum(1 for e in interventions for x in ls
                          if e["turn"] <= x[1] <= e["turn"] + 3
                          and x[4] == "STALLED")
            detail.append({
                "arm": arm, "stage": stage, "cond": cond, "task": t,
                "seed": s, "result": r["result"],
                "success": int(r["result"] == "success"),
                "infra": int(r["result"] in INFRA),
                "turns": ep_turns(r), "wall_s": r["wall_s"],
                "fires": len(evs), "injections": len(interventions),
                "injected_tokens": sum(e.get("retrieval_tokens", 0)
                                       for e in interventions),
                "recovery_any": int(rec_any and bool(interventions)),
                "stalled@3": stalled,
            })
            for e in evs:
                evs_out.append(e)
        res["arms"][arm] = {
            "label": G05_ARMS[arm], "n_rows": len(rr),
            "infra": {f"t{t}_s{s}": v for (t, s), v in sorted(
                infra.items())},
            "sr": sr, "trigger": tg, "recovery": rc, "tokens": tk,
            "episodes_detail": detail, "events": evs_out,
        }
        log(f"arm {arm}: n={len(rr)} SR={sr.get('SR_micro')} "
            f"rec@3={rc.get('recovery@3')} "
            f"tok/ep={tk.get('injected_tokens_per_ep')}")

    arm_cells = {}
    for arm in G05_ARMS:
        arm_cells[arm], _ = arm_rows(rows, arm)
    for a, b in CONTRASTS:  # reported as a minus b
        res["contrasts"][f"{a}->{b}"] = paired_sr(arm_cells[b],
                                                  arm_cells[a])
        log(f"contrast {a}->{b}: {res['contrasts'][f'{a}->{b}']}")

    common = sorted(set(arm_cells["P0"]) & set(arm_cells["P1"])
                    & set(arm_cells["P3"]) & set(arm_cells["P4"]))
    v = {arm: {k: arm_cells[arm][k]["result"] == "success"
               for k in common} for arm in ("P0", "P1", "P3", "P4")}
    res["interaction"]["(P4-P3)-(P1-P0)"] = interaction_contrast(
        common, v["P0"], v["P1"], v["P3"], v["P4"])
    log(f"interaction: {res['interaction']}")

    # §13 factor labeling (diffs are arm-minus-P0 after the swap above).
    # P4->P0 is computed here for labeling only — the six §12 contrasts
    # do not include it.
    labels = {}
    for arm in ("P1", "P2", "P3", "P4"):
        c = res["contrasts"].get(f"{arm}->P0") or paired_sr(
            arm_cells["P0"], arm_cells[arm])
        by_task = collections.defaultdict(list)
        for k in sorted(set(arm_cells[arm]) & set(arm_cells["P0"])):
            by_task[k[0]].append(
                float(arm_cells[arm][k]["result"] == "success")
                - float(arm_cells["P0"][k]["result"] == "success"))
        nnonneg = sum(1 for vals in by_task.values() if sum(vals) >= 0)
        labels[arm] = {
            "diff_vs_P0": c["diff_micro"],
            "net_wins_vs_P0": c["net_wins_b_minus_a"],
            "nonneg_tasks_of3": nnonneg,
            "CLEAR_POSITIVE": bool(c["diff_micro"] is not None
                                   and c["diff_micro"] >= .08
                                   and c["net_wins_b_minus_a"] >= 3
                                   and nnonneg >= 2),
        }
    res["factor_labels"] = labels

    out = {k: v for k, v in res.items() if k != "arms"}
    out["arms"] = {a: {kk: vv for kk, vv in d.items()
                       if kk not in ("episodes_detail", "events")}
                   for a, d in res["arms"].items()}
    (REPO / "analysis" / "stageG05_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str))

    md = ["# Stage G0.5 — attribution results\n",
          "_generated by scripts/analyze_memory_stageG05.py; arms/contrasts",
          "pre-registered in stageG05_preregistration.md BEFORE the run._\n",
          "## TABLE 1 — arms (all v1_per_result trigger; common query)",
          "",
          "| arm | n | SR | fires/ep | inj/ep | tok/ep | rec@3 | ph@3 |"
          "stalled@3 | turns_after | wall |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm in G05_ARMS:
        d = res["arms"][arm]
        s, tk, rc = d["sr"], d["tokens"], d["recovery"]
        md.append(f"| {arm} {d['label'][1]} | {d['n_rows']} | "
                  f"{s.get('SR_micro')} | {tk.get('fires_per_ep')} | "
                  f"{tk.get('injections_per_ep')} | "
                  f"{tk.get('injected_tokens_per_ep')} | "
                  f"{rc.get('recovery@3')} | {rc.get('phase_change@3')} | "
                  f"{rc.get('stalled_prims@3_mean')} | "
                  f"{rc.get('turns_after_mean')} | {tk.get('wall_mean_s')}"
                  f" |")
    md += ["", "SR by task: " + json.dumps(
        {a: res["arms"][a]["sr"].get("SR_by_task") for a in G05_ARMS}),
        "", "## TABLE 2 — six pre-registered contrasts", "",
        "| contrast | n | diff | wins | losses | ties | McNemar p | CI95 |",
        "|---|---|---|---|---|---|---|---|"]
    for a, b in CONTRASTS:
        c = res["contrasts"][f"{a}->{b}"]
        md.append(f"| {a} - {b} | {c['n_pairs']} | {c['diff_micro']} | "
                  f"{c['flips_b_only_success']} | "
                  f"{c['flips_a_only_success']} | {c['ties']} | "
                  f"{c['mcnemar_p']} | {c['ci95_micro']} |")
    md += ["", "## Interaction", "",
           json.dumps(res["interaction"], indent=2), "",
           "## §13 factor labels", "", json.dumps(labels, indent=2), "",
           "retrieval quality (P3/P4 only): "
           + json.dumps({a: g0.retrieval_stats(
               a, arm_cells[a], mcache) for a in ("P3", "P4")}),
        "", "infra (excluded, counted openly): " + json.dumps(
            {a: len(res["arms"][a]["infra"]) for a in G05_ARMS}), ""]
    (REPO / "analysis" / "stageG05_results.md").write_text(
        "\n".join(md), encoding="utf-8")
    write_runs_csv(res)
    write_events_jsonl(res)
    log("wrote analysis/stageG05_results.{json,md}")


def common0(arm_cells, arm):
    return sorted(set(arm_cells[arm]) & set(arm_cells["P0"]))


if __name__ == "__main__":
    main()
