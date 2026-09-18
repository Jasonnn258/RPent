#!/usr/bin/env python3
"""Stage C3 analysis — online O0 (reused #49 memB2) vs O2 (progress trigger).

Gates that got here: C1 query enrichment FAILED (Q2-Q0 +1.7pp, perception
0/17, hardneg unchanged) -> no query arm online; C2 progress trigger PASSED
(P .986 / R .776 offline) -> single-variable O0 vs O2.

Metrics priority (user spec): 1 trigger precision 2 false triggers/episode
3 harmful/irrelevant injections 4 relevant@1/@3 5 retrieval count 6 SR
7 planner turns 8 wall time.  Failure decomposition: nine classes incl.
QUERY_INSUFFICIENT (aligned gold, gold absent from the whole untruncated
lexical ordering — the query carried no usable vocabulary).

Usage: python scripts/analyze_memory_stageC.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import analyze_memory_stageB as sb  # noqa: E402
import memory_stagec2_benchmark as c2  # noqa: E402
from memory_stagec1_benchmark import RETREAT_CARDS  # noqa: E402
from memory_stagec2_benchmark import corrected_moments, t0_fire_class  # noqa: E402
from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

OVPM = REPO / "logs" / "ovpm_exp"

# O2 fire reason prefix -> class (frozen C2 rules)
O2_REASON_CLASS = [
    ("perception_progress_failure", "perception"),
    ("move_stalled_no_progress", "recovery_transport"),
    ("pick_reported_success_but_no_lift", "pick_verify"),
    ("repeated_failed_picks", "grasp"),
    ("recovery_no_change", "recovery_doubled"),
    ("predicate_progress_missing", "predicate_open"),
]

TASKS = (3, 5, 9)
SEEDS = range(1, 11)


def o2_cls_of_event(e) -> str:
    reason = e.get("trigger_reason") or ""
    for pre, c in O2_REASON_CLASS:
        if reason.startswith(pre):
            return c
    return reason.split(":")[0]


def load_arms():
    """O0 = memB2 rows; O2 = memC memO2 rows; B1 = memB1 rows (baseline).

    `infra_missing` rows (3 keys network-killed 3x, ledger
    analysis/stageC_outage_ledger.md) are excluded everywhere: they carry
    no valid episode, so they enter neither SR denominators nor pairs.
    """
    rows = {}
    for r in sb.csv_dict():
        if int(r["repeat"]) != 1:
            continue
        if r.get("result") == "infra_missing":
            continue
        if r["stage"] == "memB" and r["cond"] == "memB2" \
                and int(r["task"]) in TASKS:
            rows[("O0", int(r["task"]), int(r["seed"]))] = r
        if r["stage"] == "memC" and r["cond"] == "memO2" \
                and int(r["task"]) in TASKS:
            rows[("O2", int(r["task"]), int(r["seed"]))] = r
        if r["stage"] == "memB" and r["cond"] == "memB1" \
                and int(r["task"]) in TASKS:
            rows[("B1", int(r["task"]), int(r["seed"]))] = r
    return rows


def load_arm_events(arm: str):
    """memory_events.jsonl per episode dir for the given arm."""
    pat = "*_memB2_*" if arm == "O0" else "*_memO2_*"
    evs = collections.defaultdict(list)
    for d in sorted(OVPM.glob(pat)):
        p = d / "memory_events.jsonl"
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                evs[d.name].append(json.loads(line))
    return evs


def cls_of(arm, e):
    return o2_cls_of_event(e) if arm == "O2" else t0_fire_class(
        e.get("trigger_reason", ""))


def arm_moments(rows):
    out = {}
    for (arm, t, s), r in rows.items():
        ep = r["dir"].rsplit("/", 1)[-1]
        out[ep] = corrected_moments(OVPM / ep)
    return out


def trigger_layer(events, moments, eps_of_arm, cls_fn):
    tot_mom = covered = 0
    tot_fire = aligned = 0
    per_ep = collections.Counter()
    for ep in eps_of_arm:
        mom = moments.get(ep, [])
        fires = events.get(ep, [])
        per_ep[ep] = len(fires)
        tot_fire += len(fires)
        for t, _a, c in mom:
            tot_mom += 1
            covered += any(0 <= e["turn"] - t <= 3
                           and sb._same_family(cls_fn(e), c) for e in fires)
        for e in fires:
            aligned += sb._aligns(e["turn"], cls_fn(e), mom)
    prec = aligned / tot_fire if tot_fire else None
    rec = covered / tot_mom if tot_mom else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
    return {"moments": tot_mom, "covered": covered,
            "recall": round(rec, 3) if rec is not None else None,
            "fires": tot_fire, "aligned": aligned,
            "unnecessary": tot_fire - aligned,
            "precision": round(prec, 3) if prec is not None else None,
            "F1": round(f1, 3) if f1 is not None else None,
            "fires_per_ep": round(tot_fire / len(eps_of_arm), 2)
            if eps_of_arm else None}


def annotate_gold_arm(events, moments, cls_fn):
    """Same post-hoc gold pipeline as Stage B (aligned-only)."""
    import build_memory_retrieval_queries as bq
    cards = bq.load_cards()
    for ep, evs in events.items():
        mom = moments.get(ep, [])
        for e in evs:
            cls = cls_fn(e)
            # accepts BOTH naming schemes: O0 fires carry Stage-A class
            # names (predicate_timing/recovery/…), O2 fires carry the C2
            # rule names (predicate_open/move_stalled…)
            cls_map = {"recovery_doubled": ("recovery", {"doubled_fail": True}),
                       "recovery_transport": ("recovery",
                                              {"transport_stall": True}),
                       "predicate_open": ("predicate_timing", {}),
                       "predicate_timing": ("predicate_timing", {}),
                       "pick_verify": ("pick_verify", {}),
                       "grasp": ("grasp", {}),
                       "perception": ("perception", {}),
                       "recovery": ("recovery", {})}
            if cls not in cls_map:
                e["gold_memory_ids"] = None
                e["gold_note"] = f"unmapped class {cls}"
                continue
            if not sb._aligns(e["turn"], cls, mom):
                e["gold_memory_ids"] = None
                e["gold_note"] = "unnecessary_fire"
                continue
            if cls in ("predicate_open", "predicate_timing") \
                    and e.get("episode_result") is False:
                e["gold_memory_ids"] = []
                e["gold_note"] = "hard_negative (episode failed)"
                continue
            cls2, tags = cls_map[cls]
            tl = e.get("task_language") or ""
            if cls2 == "grasp" and re.search(r"\bbrand\b|\bcan\b", tl.lower()):
                tags = dict(tags, brand=True)
            gold, _why = bq.gold_for(cls2, tags, tl, cards)
            e["gold_memory_ids"] = gold or []
            e["gold_note"] = f"class={cls2}"
    return events


def ranking_layer(events):
    stats = collections.Counter()
    for ep, evs in events.items():
        for e in evs:
            gold = e.get("gold_memory_ids")
            if gold is None:
                continue
            if not gold:
                stats["hardneg_events"] += 1
                stats["hardneg_retreat_in_top3"] += bool(
                    set(e["top3_memories"]) & set(RETREAT_CARDS))
                continue
            top = e["top3_memories"]
            stats["gold_events"] += 1
            stats["relevant@1"] += bool(top and top[0] in gold)
            stats["relevant@3"] += bool(set(top) & set(gold))
            stats["irrelevant@3"] += not set(top) & set(gold)
    g = stats["gold_events"]
    return {k: (round(v / g, 3) if k in ("relevant@1", "relevant@3",
                                         "irrelevant@3") and g else v)
            for k, v in stats.items()}


def query_insufficient_split(events, lex_cards, lex_index):
    """RETRIEVAL_WRONG refinement: gold missing from the WHOLE untruncated
    lexical ordering -> QUERY_INSUFFICIENT; present in top5 -> RANK_WRONG."""
    q_insuff = rank_wrong = 0
    for ep, evs in events.items():
        for e in evs:
            gold = e.get("gold_memory_ids")
            if not gold:
                continue
            if set(e["top3_memories"]) & set(gold):
                continue
            qt = toks(e["observation_summary"] + " | " + e["trigger_reason"]) \
                | toks(e.get("task_language") or "")
            order = sorted(
                ((len(qt & (toks(lex_index.get(c, lex_cards[c]["title"]))
                            | toks(c.replace("-", " ")))), c)
                 for c in sorted(lex_cards)), reverse=True)
            pos = [c for _s, c in order if _s > 0]
            if set(pos[:5]) & set(gold):
                rank_wrong += 1
            else:
                q_insuff += 1
    return {"QUERY_INSUFFICIENT": q_insuff, "RANK_WRONG": rank_wrong}


def _episode_turns(ep_dir: Path) -> int:
    mx = 0
    try:
        for ln in (ep_dir / "run.log").read_text(errors="replace").splitlines():
            m = re.search(r"=== turn (\d+)/", ln)
            if m:
                mx = max(mx, int(m.group(1)))
    except OSError:
        pass
    return mx


def task_layer(rows):
    per = collections.defaultdict(list)
    for (arm, t, s), r in rows.items():
        per[arm].append(r)
    stats = {}
    for arm, rs in per.items():
        n = len(rs)
        succ = sum(1 for r in rs if r["result"] == "success")
        walls = [float(r["wall_s"]) for r in rs if r["wall_s"]]
        turns = [_episode_turns(OVPM / r["dir"].rsplit("/", 1)[-1])
                 for r in rs]
        stats[arm] = {"n": n, "SR": round(succ / n, 3),
                      "wall_mean_s": round(sum(walls) / len(walls), 1)
                      if walls else None,
                      "turns_mean": round(sum(turns) / n, 1)}
    pairs = {}
    for a, b in (("O0", "O2"), ("B1", "O2")):
        ka = {k[1:] for k in rows if k[0] == a}
        kb = {k[1:] for k in rows if k[0] == b}
        common = ka & kb
        wins = losses = ties = 0
        for k in common:
            ra, rb = rows[(a,) + k], rows[(b,) + k]
            sa = ra["result"] == "success"
            sb_ = rb["result"] == "success"
            wins += sb_ and not sa
            losses += sa and not sb_
            ties += sa == sb_
        pairs[f"{a}_vs_{b}"] = {"n": len(common), "wins_b": wins,
                                "losses_b": losses, "ties": ties}
    # per-task SR
    per_task = {}
    for arm in per:
        for t in TASKS:
            rs = [r for (a, tt, s), r in rows.items() if a == arm and tt == t]
            if rs:
                per_task[f"{arm}_t{t}"] = round(
                    sum(1 for r in rs if r["result"] == "success")
                    / len(rs), 2)
    return stats, pairs, per_task


def main():
    rows = load_arms()
    stats, pairs, per_task = task_layer(rows)
    print("== task layer ==", json.dumps(stats, indent=1))
    print("== pairs ==", json.dumps(pairs))
    print("== per-task SR ==", json.dumps(per_task))

    moments = arm_moments(rows)
    out = {"task": stats, "pairs": pairs, "per_task_SR": per_task}

    for arm in ("O0", "O2"):
        eps = [r["dir"].rsplit("/", 1)[-1] for (a, t, s), r in rows.items()
               if a == arm]
        events = load_arm_events(arm)
        events = {ep: evs for ep, evs in events.items() if ep in eps}
        cls_fn = (lambda e: o2_cls_of_event(e)) if arm == "O2" \
            else (lambda e: t0_fire_class(e.get("trigger_reason", "")))
        tl = trigger_layer(events, moments, eps, cls_fn)
        ev_gold = annotate_gold_arm(events, moments, cls_fn)
        rl = ranking_layer(ev_gold)
        print(f"== {arm} trigger ==", json.dumps(tl))
        print(f"== {arm} ranking ==", json.dumps(rl))
        out[arm] = {"trigger": tl, "ranking": rl,
                    "events": {ep: evs for ep, evs in ev_gold.items()}}
        if arm == "O2":
            split = query_insufficient_split(
                ev_gold, load_cards(), load_index())
            print("== O2 retrieval-wrong split ==", json.dumps(split))
            out["O2"]["retrieval_wrong_split"] = split

    # latency / token overhead
    for arm in ("O0", "O2"):
        lats, toks_ = [], []
        for ep, evs in out[arm]["events"].items():
            for e in evs:
                lats.append(e.get("retrieval_latency_ms") or 0)
                toks_.append(e.get("retrieval_tokens") or 0)
        if lats:
            out[arm]["overhead"] = {
                "latency_mean_ms": round(sum(lats) / len(lats), 2),
                "tokens_mean": round(sum(toks_) / len(toks_), 1)}

    outp = REPO / "analysis" / "memory_stageC_results.json"
    json.dump(out, open(outp, "w"), indent=2, ensure_ascii=False,
              default=str)
    print("wrote", outp)


if __name__ == "__main__":
    main()
