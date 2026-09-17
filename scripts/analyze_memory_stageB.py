#!/usr/bin/env python3
"""Stage B1 analysis — five metric layers + failure decomposition + verdict.

Inputs:
  analysis/outcome_validation_runs.csv   (stage memB rows + reused B0 rows)
  logs/ovpm_exp/<episode>/memory_events.jsonl   (memB2/memB3 recall events)
  logs/ovpm_exp/<episode>/run.log        (post-hoc adoption evidence)

Post-hoc only: gold_memory_ids / followed_top1 / followed_any_top3 are
annotated AFTER episodes finish (never available at runtime).

Usage: python scripts/analyze_memory_stageB.py [--gold gold.jsonl]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV = REPO / "analysis" / "outcome_validation_runs.csv"
OVPM = REPO / "logs" / "ovpm_exp"

# B0 rows: stage1 armA (t3/t5, 2026-09-15/16 = post max-tokens-fix) +
# memB0 (t9 supplement). Verified by analysis/memory_stageB_design.md.
B0_STAGES = {"stage1": ("armA", (3, 5)), "memB": ("memB0", (9,))}
ARMS = ["B0", "B1", "B2", "B3"]
ARM_OF_COND = {"armA": "B0", "memB0": "B0", "memB1": "B1",
               "memB2": "B2", "memB3": "B3"}

# adoption keyword map: card How-to-apply directive -> planner action verbs
ADOPT_MAP = {
    "RETREAT": ["move_to", "move_pose", "retreat", "lift", "raise"],
    "OBSERVE": ["segment", "back_project", "view_driver_state", "read_image",
                "observe"],
    "RETRY": ["pi0_pick", "pick", "regrasp", "re-pick"],
    "RECOVER": ["pi0_doubled", "move_to", "set_gripper", "rotate"],
}


def load_rows():
    """CSV -> arm rows keyed (arm, task, seed)."""
    out = {}
    for r in csv_dict():
        for stage, (cond, tasks) in B0_STAGES.items():
            if r["stage"] == stage and r["cond"] == cond \
                    and int(r["task"]) in tasks and int(r["repeat"]) == 1:
                out[("B0", int(r["task"]), int(r["seed"]))] = r
        if r["stage"] == "memB" and r["cond"] in ARM_OF_COND \
                and int(r["repeat"]) == 1:
            arm = ARM_OF_COND[r["cond"]]
            if arm == "B0" and int(r["task"]) != 9:
                continue  # B0 on t3/t5 comes from the historical stage1 rows
            out[(arm, int(r["task"]), int(r["seed"]))] = r
    return out


def csv_dict():
    import csv
    with open(CSV) as f:
        for r in csv.DictReader(f):
            yield r


# ---------------------------------------------------------------- task layer
def task_layer(rows):
    per = collections.defaultdict(list)
    for (arm, t, s), r in rows.items():
        per[arm].append(r)
    stats = {}
    for arm, rs in per.items():
        n = len(rs)
        succ = sum(1 for r in rs if r["result"] == "success")
        walls = [float(r["wall_s"]) for r in rs if r["wall_s"]]
        stats[arm] = {
            "n": n, "SR": round(succ / n, 3) if n else None,
            "wall_mean_s": round(sum(walls) / len(walls), 1) if walls else None,
        }
    # paired deltas on common (task, seed)
    pairs = {}
    for a, b in (("B0", "B1"), ("B1", "B2"), ("B2", "B3")):
        common = {k for k in rows if k[0] == a} & {k for k in rows if k[0] == b}
        wins = losses = ties = 0
        for k in common:
            ra, rb = rows[k], rows[(b,) + k[1:]]
            sa = ra["result"] == "success"
            sb = rb["result"] == "success"
            wins += sb and not sa
            losses += sa and not sb
            ties += sa == sb
        pairs[f"{a}_vs_{b}"] = {"n_pairs": len(common), "wins_b": wins,
                                "losses_b": losses, "ties": ties}
    return stats, pairs


# ----------------------------------------------------------- adoption layer
def parse_next_actions(run_log: Path, after_turn: int, k: int = 3):
    """First k primitive tool calls logged after the given turn marker."""
    acts, turn = [], -1
    try:
        lines = run_log.read_text(errors="replace").splitlines()
    except OSError:
        return acts
    for ln in lines:
        m = re.search(r"=== turn (\d+)/", ln)
        if m:
            turn = int(m.group(1))
            continue
        if turn >= after_turn:
            tm = re.search(r"\[tool>\] (pi0_pick|pi0_doubled|move_to|move_pose|"
                           r"release|set_gripper|rotate_wrist|rotate_pitch|"
                           r"segment|back_project|view_driver_state)\(",
                           ln)
            if tm:
                acts.append(tm.group(1))
                if len(acts) >= k:
                    break
    return acts


def adoption_layer(events_by_ep):
    """followed_top1/any_top3 proxy: next planner action matches the card's
    How-to-apply directive family (annotated post-hoc, per spec §6)."""
    n = followed1 = followed3 = 0
    for ep, events in events_by_ep.items():
        run_log = OVPM / ep / "run.log"
        for e in events:
            n += 1
            acts = parse_next_actions(run_log, e["turn"])
            e["planner_next_action"] = acts[:1]
            verbs = set(acts)
            f1 = f3 = False
            for i, card in enumerate(e["top3_memories"]):
                directive = directive_of(card)
                if directive and verbs & set(ADOPT_MAP.get(directive, [])):
                    if i == 0:
                        f1 = True
                    f3 = True
            e["planner_followed_top1"] = f1
            e["planner_followed_any_top3"] = f3
            followed1 += f1
            followed3 += f3
    return {"events": n, "followed_top1": followed1,
            "followed_any_top3": followed3,
            "retrieved_but_ignored": n - followed3}


_CARD_DIRECTIVE = {}


def directive_of(card_id: str):
    """Expected-use directive of a card (RETREAT/OBSERVE/RETRY/RECOVER)."""
    if card_id not in _CARD_DIRECTIVE:
        how = ""
        p = REPO / "resources" / "libero" / "global" / f"{card_id}.md"
        if p.exists():
            t = p.read_text()
            m = re.search(r"\*\*How to apply:\*\*(.{0,400})", t, re.S)
            how = (m.group(1) if m else "").lower()
        d = ("RETREAT" if re.search(r"retreat|raise|lift|back off", how)
             else "OBSERVE" if re.search(r"segment|observe|verify|confirm|"
                                         "watch|check", how)
             else "RETRY" if re.search(r"re-?pick|regrasp|pick again", how)
             else "RECOVER")
        _CARD_DIRECTIVE[card_id] = d
    return _CARD_DIRECTIVE[card_id]


# ------------------------------------------------------------- event loading
def load_events():
    evs = collections.defaultdict(list)
    for d in sorted(OVPM.glob("*_memB[23]_*")):
        p = d / "memory_events.jsonl"
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                evs[d.name].append(json.loads(line))
    return evs


# ------------------------------------------- should-retrieve moments (trigger)
# A SHOULD-retrieve moment is a tool result whose observable fields place it
# in a Stage A class with cards (post-hoc; the same signal family the frozen
# trigger watches). Turn-numbered for joining against actual fires.


def _pick_class(name: str, data: dict) -> str | None:
    if name == "pi0_pick":
        if data.get("success") is False:
            return "grasp"
        lift = (data.get("diagnostics") or {}).get("post_min_ascent_m")
        if data.get("success") is True and isinstance(lift, (int, float)) \
                and lift < 0.05:
            return "pick_verify"
    if name in ("move_to", "move_pose") and isinstance(
            data.get("final_dist_m"), (int, float)) \
            and data["final_dist_m"] > 0.03:
        return "recovery_transport"
    if name == "release" and data.get("libero_terminated") is False:
        return "predicate_open"
    if name == "segment" and data.get("found") is False:
        return "perception"
    return None


_TOOLRES = re.compile(r"\[tool<\] (\w+): (\{.*)")


def should_retrieve_moments(run_log: Path):
    """[(turn, action, class)] — post-hoc SHOULD moments from the tool stream."""
    out, turn = [], -1
    try:
        lines = run_log.read_text(errors="replace").splitlines()
    except OSError:
        return out
    for ln in lines:
        m = re.search(r"=== turn (\d+)/", ln)
        if m:
            turn = int(m.group(1))
            continue
        tm = _TOOLRES.search(ln)
        if not tm:
            continue
        name, payload = tm.group(1), tm.group(2)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            # run.log truncates long results "(+NNN)" — try the saved states
            data = {}
        if not data:
            continue
        cls = _pick_class(name, data)
        if cls:
            out.append((turn, name, cls))
    return out


def trigger_coverage(events_by_ep):
    """Join actual fires against SHOULD moments (slack +/-1 turn)."""
    tot_should = covered = 0
    unnecessary = 0
    for ep, events in events_by_ep.items():
        mom = should_retrieve_moments(OVPM / ep / "run.log")
        fired_turns = [e["turn"] for e in events]
        for t, _a, _c in mom:
            tot_should += 1
            if any(abs(t - ft) <= 1 for ft in fired_turns):
                covered += 1
        for ft in fired_turns:
            if not any(abs(t - ft) <= 1 for t, _a, _c in mom):
                unnecessary += 1
    return {"should_moments": tot_should,
            "covered": covered,
            "coverage": round(covered / tot_should, 3) if tot_should else None,
            "fires_without_should_signal": unnecessary}


# ------------------------------------------------- gold annotation (post-hoc)
# trigger_reason prefix -> Stage A class; gold cards via the SAME MAP/gold_for
# as the Stage A dataset (import from the sibling builder). T7 phase_stalled
# has no direct Stage A class -> manual bucket (gold stays null).
REASON_CLASS = [
    ("primitive_failure: pi0_pick", "grasp"),
    ("primitive_failure: contact skill", "recovery_doubled"),
    ("primitive_failure: move stopped short", "recovery_transport"),
    ("primitive_failure:", "recovery"),
    ("pick_ambiguous", "pick_verify"),
    ("predicate_stalled", "predicate_timing"),
    ("repeated_no_progress", "recovery"),
    ("perception_insufficient", "perception"),
    ("recovery_pending", "recovery"),
]


def annotate_gold(events_by_ep):
    """Fill gold_memory_ids post-hoc; returns events with gold + notes."""
    import build_memory_retrieval_queries as bq
    cards = bq.load_cards()
    n_gold = 0
    for ep, events in events_by_ep.items():
        for e in events:
            reason = e.get("trigger_reason") or ""
            cls = next((c for pre, c in REASON_CLASS
                        if reason.startswith(pre)), None)
            if cls is None:  # phase_stalled -> manual bucket
                e["gold_memory_ids"] = None
                e["gold_note"] = "T7 phase_stalled: needs manual annotation"
                continue
            tags = {}
            if cls == "recovery_doubled":
                cls, tags = "recovery", {"doubled_fail": True}
            if cls == "recovery_transport":
                cls, tags = "recovery", {"transport_stall": True}
            if cls == "predicate_timing" and e.get("episode_result") is False:
                # Stage A rule: failed episode -> retreat cards' Falsify holds
                # (hard negative; gold = none-of-the-retreat-cards)
                e["gold_memory_ids"] = []
                e["gold_note"] = "hard_negative (episode failed)"
                continue
            tl = e.get("task_language") or ""
            if cls == "grasp" and re.search(r"\bbrand\b|\bcan\b", tl.lower()):
                tags["brand"] = True
            gold, _why = bq.gold_for(cls, tags, tl, cards)
            e["gold_memory_ids"] = gold or []
            e["gold_note"] = f"class={cls}"
            n_gold += bool(gold)
    return events_by_ep


def ranking_layer(events_by_ep):
    """Online relevant@1/@3, irrelevant@3 vs post-hoc gold."""
    stats = collections.Counter()
    for ep, events in events_by_ep.items():
        for e in events:
            gold = e.get("gold_memory_ids")
            if gold is None:
                continue  # manual bucket
            if not gold:
                stats["no_relevant_memory_events"] += 1
                stats["irrelevant_top3"] += bool(e["top3_memories"])
                continue
            top = e["top3_memories"]
            stats["gold_events"] += 1
            stats["relevant@1"] += bool(top and top[0] in gold)
            stats["relevant@3"] += bool(set(top) & set(gold))
            stats["irrelevant_top3"] += not set(top) & set(gold)
    out = dict(stats)
    g = stats["gold_events"]
    if g:
        out["relevant@1_rate"] = round(stats["relevant@1"] / g, 3)
        out["relevant@3_rate"] = round(stats["relevant@3"] / g, 3)
    return out


def trigger_layer(events_by_ep, rows):
    per_arm = collections.defaultdict(list)
    for ep, events in events_by_ep.items():
        m = re.search(r"_(memB\d)_libero_spatial_task_t(\d+)_s(\d+)_r1$", ep)
        if not m:
            continue
        arm = ARM_OF_COND[m.group(1)]
        per_arm[arm].append(len(events))
    out = {}
    for arm, counts in per_arm.items():
        eps = len(counts)
        out[arm] = {
            "episodes": eps,
            "episodes_with_trigger": sum(1 for c in counts if c),
            "trigger_count_mean": round(sum(counts) / eps, 2) if eps else 0,
            "triggers_total": sum(counts),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", help="post-hoc gold annotation jsonl "
                    "(episode,turn)->gold_memory_ids; absent = ranking layer "
                    "skipped")
    args = ap.parse_args()
    rows = load_rows()
    stats, pairs = task_layer(rows)
    events = load_events()
    trig = trigger_layer(events, rows)
    cov = trigger_coverage(events)
    adopt = adoption_layer(events)
    events = annotate_gold(events)
    rank = ranking_layer(events)

    print("== Task layer ==")
    print(json.dumps(stats, indent=2))
    print("== Paired comparisons ==")
    print(json.dumps(pairs, indent=2))
    print("== Trigger layer ==")
    print(json.dumps(trig, indent=2))
    print("== Trigger coverage vs post-hoc SHOULD moments ==")
    print(json.dumps(cov, indent=2))
    print("== Adoption layer (keyword proxy) ==")
    print(json.dumps(adopt, indent=2))
    print("== Ranking layer (post-hoc gold) ==")
    print(json.dumps(rank, indent=2))

    if args.gold:
        print("(NOTE: --gold file override not implemented; auto annotation "
              "from trigger_reason used; T7 events need manual review)")

    out = REPO / "analysis" / "memory_stageB_results.json"
    json.dump({"task": stats, "pairs": pairs, "trigger": trig,
               "coverage": cov, "adoption": adopt, "ranking": rank,
               "events": {ep: evs for ep, evs in events.items()}},
              open(out, "w"), indent=2, ensure_ascii=False)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
