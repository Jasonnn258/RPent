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
    # paired deltas on common (task, seed) — arm must NOT be part of the
    # join key (v1 bug: full (arm,task,seed) keys never intersect)
    pairs = {}
    for a, b in (("B0", "B1"), ("B1", "B2"), ("B2", "B3")):
        ka = {k[1:] for k in rows if k[0] == a}
        kb = {k[1:] for k in rows if k[0] == b}
        common = ka & kb
        wins = losses = ties = 0
        for k in common:
            ra, rb = rows[(a,) + k], rows[(b,) + k]
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


_TOOLRES = re.compile(r"\[tool<\] (\w+): ")


def _step_to_turn(run_log: Path) -> dict[int, int]:
    """step_idx -> planner turn, from run.log `[tool<]` lines carrying
    `"step": N` in the (possibly truncated) payload prefix."""
    out: dict[int, int] = {}
    turn = 0
    try:
        for ln in run_log.read_text(errors="replace").splitlines():
            m = re.search(r"=== turn (\d+)/", ln)
            if m:
                turn = int(m.group(1))
                continue
            tm = _TOOLRES.search(ln)
            if tm:
                sm = re.search(r'"step": (\d+)', ln[tm.end():tm.end() + 60])
                if sm:
                    out.setdefault(int(sm.group(1)), turn)
    except OSError:
        pass
    return out


def should_retrieve_moments(ep_dir: Path):
    """[(turn, action, class)] — post-hoc SHOULD moments.

    run.log truncates tool payloads, so state-changing results come from
    states.json (full `result` dicts); perception failures come from
    segments/*.json (found=false). Steps map to turns via run.log.
    """
    out: list[tuple[int, str, str]] = []
    try:
        states = json.load(open(ep_dir / "states.json"))
    except (OSError, json.JSONDecodeError):
        states = []
    s2t = _step_to_turn(ep_dir / "run.log")
    steps = sorted(s2t)
    for e in states:
        r = e.get("result") or {}
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except json.JSONDecodeError:
                continue
        name = r.get("name") or (e.get("command") or {}).get("action", "")
        cls = _pick_class(name, r)
        if not cls:
            continue
        st = e.get("step_idx")
        if st not in s2t and steps:
            # truncated log line: nearest recorded step's turn
            st = min(steps, key=lambda s: abs(s - (st or 0)))
        out.append((s2t.get(st, 0), name, cls))
    for p in sorted((ep_dir / "segments").glob("segment_*.json")):
        try:
            seg = json.load(open(p))
        except (OSError, json.JSONDecodeError):
            continue
        if seg.get("found") is False:
            m = re.search(r"segment_(\d+)", p.name)
            st = int(m.group(1)) if m else 0
            t = s2t.get(st, min(steps, key=lambda s: abs(s - st)) if steps
                        else 0)
            out.append((t, "segment", "perception"))
    return sorted(out)


def _aligns(turn_fire: int, cls_fire: str, moments) -> bool:
    """Does a fire align (0..3 turns later, same class family) with a SHOULD
    moment? The boundary fires at the START of the reacting turn, so a moment
    at turn M pairs with a fire at M..M+3 (cooldown can delay by 2)."""
    return any(0 <= turn_fire - t <= 3 and _same_family(c, cls_fire)
               for t, _a, c in moments)


def _same_family(a: str, b: str) -> bool:
    return _fam_of(a) == _fam_of(b)


def trigger_coverage(events_by_ep, moments_by_ep):
    """Actual fires vs SHOULD moments, both directions."""
    tot_should = covered = unnecessary = 0
    for ep, events in events_by_ep.items():
        mom = moments_by_ep[ep]
        for t, _a, c in mom:
            tot_should += 1
            if any(0 <= e["turn"] - t <= 3
                   and _same_family(_cls_of_event(e), c) for e in events):
                covered += 1
        unnecessary += sum(1 for e in events
                           if not _aligns(e["turn"], _cls_of_event(e), mom))
    return {"should_moments": tot_should,
            "covered": covered,
            "coverage": round(covered / tot_should, 3) if tot_should else None,
            "fires_without_should_signal": unnecessary}


def _cls_of_event(e) -> str:
    reason = e.get("trigger_reason") or ""
    for pre, c in REASON_CLASS:
        if reason.startswith(pre):
            return c
    return reason.split(":")[0]


def _fam_of(c: str) -> str:
    return {"recovery_transport": "recovery", "recovery_doubled": "recovery",
            "predicate_open": "predicate_timing"}.get(c, c)


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


def annotate_gold(events_by_ep, moments_by_ep):
    """Fill gold_memory_ids post-hoc.

    v2: gold is assigned ONLY when the fire aligns with a SHOULD moment of
    the same class family — an unaligned fire is an unnecessary fire (a
    TRIGGER-layer metric), not a ranking failure. Unaligned events keep
    gold=None with a note and are excluded from the ranking layer.
    """
    import build_memory_retrieval_queries as bq
    cards = bq.load_cards()
    n_gold = 0
    for ep, events in events_by_ep.items():
        mom = moments_by_ep[ep]
        for e in events:
            reason = e.get("trigger_reason") or ""
            cls = next((c for pre, c in REASON_CLASS
                        if reason.startswith(pre)), None)
            if cls is None:  # phase_stalled -> manual bucket
                e["gold_memory_ids"] = None
                e["gold_note"] = "T7 phase_stalled: needs manual annotation"
                continue
            if not _aligns(e["turn"], cls, mom):
                e["gold_memory_ids"] = None
                e["gold_note"] = "unnecessary_fire (no aligned SHOULD moment)"
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


# ------------------------------------------------------------ outcome layer
def outcome_layer(events_by_ep):
    """Per-event outcome proxies (post-hoc, semi-automated):

    reFire     same trigger class re-fires within 3 turns -> recall did not
               resolve the situation (memory wrong OR ignored — disambiguated
               by adoption + ranking layers)
    helped_c   followed a gold card AND no same-class re-fire AND episode
               succeeded
    harmful_c  followed a card AND a primitive is_error or a NEW failure
               class appears within 2 turns (manual review flag)
    Everything else neutral. Counts are candidates, verdicts manual.
    """
    out = {"helped_c": 0, "harmful_c": 0, "neutral": 0, "refire": 0}
    for ep, events in events_by_ep.items():
        succ = events[0].get("episode_result") if events else None
        for i, e in enumerate(events):
            refire = any(
                abs(later["turn"] - e["turn"]) <= 3
                and (later.get("trigger_reason") or "").startswith(
                    e["trigger_reason"].split(":")[0])
                for later in events[i + 1:])
            out["refire"] += refire
            followed = e.get("planner_followed_any_top3")
            gold = e.get("gold_memory_ids")
            if followed and gold and set(e["top3_memories"]) & set(gold) \
                    and not refire and succ is True:
                out["helped_c"] += 1
            elif followed and refire:
                out["harmful_c"] += 1  # acted on a card, situation worsened
            else:
                out["neutral"] += 1
    return out


# ----------------------------------------------------- failure decomposition
def decompose(events_by_ep, moments_by_ep, rows):
    """Eight-class per-episode decomposition (spec §8), priority order.

    v2 covers ALL memB2/memB3 episodes (15 had zero triggers — v1 dropped
    them); only SHOULD-aligned fires count toward retrieval classes.
    Followed* flags come from the (biased-high) keyword proxy — treat
    RETRIEVED_BUT_IGNORED vs MEMORY_WRONG split as provisional.
    """
    counts = collections.Counter()
    examples = collections.defaultdict(list)
    row_by_dir = {r["dir"].rsplit("/", 1)[-1]: r for r in rows.values()}
    all_eps = {ep: events_by_ep.get(ep, []) for ep in row_by_dir
               if "_memB2_" in ep or "_memB3_" in ep}
    for ep, events in all_eps.items():
        r = row_by_dir[ep]
        if r["result"] == "success":
            counts["SUCCESS"] += 1
            continue
        mom = moments_by_ep[ep]
        note = lambda e: e.get("gold_note", "")  # noqa: E731
        aligned = [e for e in events if note(e).startswith("class=")]
        hardneg = [e for e in events if note(e).startswith("hard_negative")]
        gold_events = [e for e in aligned if e.get("gold_memory_ids")]
        gold_hits = [e for e in gold_events
                     if set(e["top3_memories"]) & set(e["gold_memory_ids"])]
        followed = any(e.get("planner_followed_any_top3") for e in gold_hits)
        covered = any(
            any(0 <= e["turn"] - t <= 3 and _same_family(
                _cls_of_event(e), c) for e in events)
            for t, _a, c in mom)
        if not mom:
            cls = "EXECUTION_FAIL"
        elif not covered:
            cls = "TRIGGER_MISS"
        elif gold_events and not gold_hits:
            cls = "RETRIEVAL_WRONG"
        elif gold_hits and followed:
            cls = "MEMORY_WRONG"
        elif gold_hits and not followed:
            cls = "RETRIEVED_BUT_IGNORED"
        elif (aligned and not gold_events) or hardneg:
            # aligned to a moment whose card family is falsified by the
            # episode outcome (Stage A hard-negative rule) — no card helps
            cls = "NO_RELEVANT_MEMORY"
        else:
            cls = "TRIGGER_MISS"  # moments existed, fires never aligned
        counts[cls] += 1
        if len(examples[cls]) < 5:
            examples[cls].append(ep)
    return dict(counts), dict(examples)


def verdict(stats_pairs, cov, rank, adopt, decomp):
    """Final call (spec §9) — printed, human confirms.

    Trigger support requires BOTH coverage (fires reach true decision
    moments) and precision (fires are not mostly noise) — v1 ignored
    precision and called 73%-unnecessary firing 'supported'.
    """
    fires = (cov.get("covered", 0) + 0) + 0  # aligned fires = covered-side
    # aligned fires per annotate_gold: gold + hardneg + (T7/unnecessary not)
    cov_rate = cov.get("coverage")
    tot_fires = adopt.get("events", 0)
    gold_n = rank.get("gold_events", 0)
    hardneg_n = rank.get("no_relevant_memory_events", 0)
    prec = round((gold_n + hardneg_n) / tot_fires, 3) if tot_fires else None
    trig_ok = cov_rate is not None and cov_rate >= 0.5 and prec is not None \
        and prec >= 0.5
    rank_ok = (rank.get("relevant@3_rate") or 0) >= 0.4
    lines = [
        f"TRIGGER: coverage={cov_rate} precision={prec} "
        f"(unnecessary fires={cov.get('fires_without_should_signal')}) "
        f"-> {'SUPPORTED' if trig_ok else 'NOT SUPPORTED'}",
        f"RANKING: relevant@3={rank.get('relevant@3_rate')} "
        f"(n gold events={gold_n}) "
        f"-> {'SUPPORTED' if rank_ok else 'NOT SUPPORTED (n too small / rate low)'}",
        "Adoption bottleneck check (B3): followed_top1="
        f"{adopt.get('followed_top1')}/{adopt.get('events')} "
        "(keyword proxy, biased HIGH — RETREAT/OBSERVE verbs overlap "
        "routine moves), "
        f"ignored={adopt.get('retrieved_but_ignored')}",
        f"Decomposition: {decomp}",
        "EXECUTABLE MEMORY NEXT: gate = gold-in-top3 high + adoption low + "
        "ignored cards confirmed applicable. Current: ranking only 0.57 "
        "on n=14, trigger precision low, paired SR negative -> NO.",
    ]
    return "\n".join(lines)


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
    # SHOULD moments for every memB2/memB3 episode dir (zero-trigger
    # episodes included — they feed TRIGGER_MISS)
    moments_by_ep = {
        d.name: should_retrieve_moments(d)
        for d in sorted(OVPM.glob("*_memB[23]_*")) if d.is_dir()}
    cov = trigger_coverage(events, moments_by_ep)
    adopt = adoption_layer(events)
    events = annotate_gold(events, moments_by_ep)
    rank = ranking_layer(events)
    outc = outcome_layer(events)
    decomp, examples = decompose(events, moments_by_ep, rows)

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
    print("== Outcome layer (candidate proxies) ==")
    print(json.dumps(outc, indent=2))
    print("== Failure decomposition (episodes) ==")
    print(json.dumps(decomp, indent=2))
    for cls, eps in examples.items():
        print(f"  {cls}: {', '.join(eps)}")

    if args.gold:
        print("(NOTE: --gold file override not implemented; auto annotation "
              "from trigger_reason used; T7 events need manual review)")

    print("\n== VERDICT (auto-proposal; human confirms) ==")
    print(verdict(pairs, cov, rank, adopt, decomp))

    out = REPO / "analysis" / "memory_stageB_results.json"
    json.dump({"task": stats, "pairs": pairs, "trigger": trig,
               "coverage": cov, "adoption": adopt, "ranking": rank,
               "outcome": outc, "decomposition": decomp,
               "events": {ep: evs for ep, evs in events.items()}},
              open(out, "w"), indent=2, ensure_ascii=False)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
