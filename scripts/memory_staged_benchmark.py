#!/usr/bin/env python3
"""Stage D1 offline benchmark — card-side retrieval alignment, 5 arms.

Reads the FROZEN C1 query dump (134 points, query texts already computed by
memory_stagec1_benchmark.py) and the FROZEN alias sidecar; replays the exact
Q0_FIXED lexical scoring with a parametrised card-side token set:

  D0_ORIGINAL    Q0_POOR query, base tokens           (must reproduce C1)
  D1_QUERY_RICH  Q2_STATE_GROUNDED query, base tokens (must reproduce C1)
  D2_CARD_ALIGNED Q0_POOR + aliases
  D3_BOTH         Q2_STATE_GROUNDED + aliases
  D_SHAM          Q0_POOR + permuted aliases (length/genericity control)

Base token set is verbatim `_q0_fixed` / C1 Lexical:
  toks(index.get(c, cards[c]["title"])) | toks(c.replace("-", " "))
Scoring & tie-break verbatim: sorted(((score, c) for c in sorted(ids)),
reverse=True); deployed cut = score > 0, top3 = pos[:3].

Mechanism log (per primary gold point x arm in {D2, D3, D_SHAM}):
token_overlap / gold_rank / matched terms before vs after — answers whether
rank gains come from new query<->alias vocabulary connections.

Pre-registered gates:
  (1) D2 perception R@3 >= 8/17
  (2) non-perception primary R@3 drop vs D0 <= 3pp
  (3) hardneg noise (any_top3 / retreat_in_top3) worsens <= 5pp
  (4) D2 clearly beats D_SHAM (perception R@3 AND primary MRR)

Usage: python scripts/memory_staged_benchmark.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"
SIDECAR = REPO / "analysis" / "retrieval_aliases_v1.json"
MECH = REPO / "analysis" / "memory_staged_mechanism.jsonl"
OUT = REPO / "analysis" / "memory_staged_results.json"

RETREAT_CARDS = ["predicate-fires-after-gripper-retreat",
                 "predicate-gated-by-eef-proximity-retreat-clear",
                 "open-retreat-settles-container", "basket-release-retreat-settle",
                 "basket-insertion-open-retreat"]
SHAM_SEED = 20260920

ARMS = ["D0_ORIGINAL", "D1_QUERY_RICH", "D2_CARD_ALIGNED", "D3_BOTH", "D_SHAM"]
QUERY_OF = {"D0_ORIGINAL": "Q0_POOR", "D1_QUERY_RICH": "Q2_STATE_GROUNDED",
            "D2_CARD_ALIGNED": "Q0_POOR", "D3_BOTH": "Q2_STATE_GROUNDED",
            "D_SHAM": "Q0_POOR"}

# C1 published anchors (analysis/memory_stageC1_results.json) — regression
C1_ANCHOR = {
    ("primary", "Q0_POOR"): {"R@1": 0.233, "R@3": 0.575, "R@5": 0.592,
                             "MRR": 0.418, "irrelevant@3": 0.425},
    ("primary", "Q2_STATE_GROUNDED"): {"R@1": 0.275, "R@3": 0.592,
                                       "R@5": 0.608, "MRR": 0.458,
                                       "irrelevant@3": 0.408},
    ("hardneg", "Q0_POOR"): {"retreat_in_top3": 14},
    ("perception17", "Q0_POOR"): {"R@3": 0},
    ("perception17", "Q2_STATE_GROUNDED"): {"R@3": 0},
}


def load_points() -> list[dict]:
    pts = []
    for line in QUERIES.read_text().splitlines():
        if line.strip():
            pts.append(json.loads(line))
    return pts


def build_token_sets():
    cards = load_cards()
    index = load_index()
    ids = sorted(cards)
    side = json.loads(SIDECAR.read_text())
    aliases = {c["memory_id"]: list(c["retrieval_aliases"]) for c in side["cards"]}
    alias_tok = {c: toks(" ".join(aliases.get(c, []))) for c in ids}

    # D_SHAM: permute the pooled alias strings across cards (derangement at
    # the alias level, per-card counts preserved, deterministic seed).
    rng = random.Random(SHAM_SEED)
    pool = [(c, a) for c in ids for a in aliases.get(c, [])]
    order = list(range(len(pool)))
    rng.shuffle(order)
    # deal sequentially but never onto the source card (bounded fix-up pass)
    sham_of: dict[str, list[str]] = {c: [] for c in ids}
    slots = {c: len(aliases.get(c, [])) for c in ids}
    for i in order:
        src_c, alias = pool[i]
        placed = False
        for j in range(len(order)):  # deterministic scan
            dst = pool[order[j]][0]
            if dst != src_c and len(sham_of[dst]) < slots[dst]:
                sham_of[dst].append(alias)
                placed = True
                break
            if dst != src_c:
                continue
        if not placed:  # extremely unlikely; append to any non-source card
            for c in ids:
                if c != src_c and len(sham_of[c]) < slots[c] + 1:
                    sham_of[c].append(alias)
                    break
    sham_tok = {c: toks(" ".join(sham_of.get(c, []))) for c in ids}

    def base(c):
        return toks(index.get(c, cards[c]["title"])) | toks(c.replace("-", " "))

    extra_of = {}
    for arm in ARMS:
        if arm in ("D2_CARD_ALIGNED", "D3_BOTH"):
            extra_of[arm] = alias_tok
        elif arm == "D_SHAM":
            extra_of[arm] = sham_tok
        else:
            extra_of[arm] = {c: set() for c in ids}
    toks_of = {arm: {c: base(c) | extra_of[arm][c] for c in ids}
               for arm in ARMS}
    return ids, toks_of, alias_tok, sham_tok


def rank(q: str, tl: str, arm: str, ids, toks_of):
    """Verbatim C1 Lexical.rank + deployed >0 cut. Returns (pos, scored)."""
    qt = toks(q) | toks(tl)
    scored = sorted(
        ((len(qt & toks_of[arm][c]), c) for c in ids), reverse=True)
    pos = [c for s, c in scored if s > 0]
    return pos, scored


def metrics(points, arm, ids, toks_of) -> dict:
    out: dict = {"ALL": {"n": 0, "R@1": 0, "R@3": 0, "R@5": 0, "MRR": 0.0,
                         "empty_top3": 0, "irrelevant@3": 0,
                         "retreat_in_top3": 0}}
    for p in points:
        g = p["gold"]
        if g is None:  # hard negative handled by caller
            continue
        pos, _ = rank(p["queries"][QUERY_OF[arm]], p["tl"], arm, ids, toks_of)
        top3 = pos[:3]
        c = out["ALL"]
        c["n"] += 1
        c["R@1"] += bool(top3 and top3[0] in g)
        c["R@3"] += bool(set(top3) & set(g))
        c["R@5"] += bool(set(pos[:5]) & set(g))
        c["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                          if x in g), 0.0)
        c["empty_top3"] += not top3
        c["irrelevant@3"] += not set(top3) & set(g)
        c["retreat_in_top3"] += bool(set(top3) & set(RETREAT_CARDS))
        cls = p["class"]
        if cls not in out:
            out[cls] = {"n": 0, "R@1": 0, "R@3": 0, "R@5": 0, "MRR": 0.0,
                        "empty_top3": 0, "irrelevant@3": 0,
                        "retreat_in_top3": 0}
        cc = out[cls]
        for k in ("n", "R@1", "R@3", "R@5", "empty_top3", "irrelevant@3",
                  "retreat_in_top3"):
            cc[k] += 0
        cc["n"] += 1
        cc["R@1"] += bool(top3 and top3[0] in g)
        cc["R@3"] += bool(set(top3) & set(g))
        cc["R@5"] += bool(set(pos[:5]) & set(g))
        cc["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                           if x in g), 0.0)
        cc["empty_top3"] += not top3
        cc["irrelevant@3"] += not set(top3) & set(g)
        cc["retreat_in_top3"] += bool(set(top3) & set(RETREAT_CARDS))
    # rates
    for cls, c in out.items():
        n = c["n"]
        for k in ("R@1", "R@3", "R@5", "irrelevant@3", "retreat_in_top3"):
            if k in ("retreat_in_top3",):
                c[k] = c[k]  # keep count
            else:
                c[k] = round(c[k] / n, 3) if n else 0
        c["MRR"] = round(c["MRR"] / n, 3) if n else 0.0
    return out


def hardneg_metrics(points, arm, ids, toks_of) -> dict:
    """Hard negatives: gold=[] — noise = any non-empty top3; retreat cards
    in top3 tracked separately (retreat_in_top3 was already 14/14 in C1)."""
    n = any3 = retreat = 0
    for p in points:
        if p["gold"] is not None:
            continue
        pos, _ = rank(p["queries"][QUERY_OF[arm]], p["tl"], arm, ids, toks_of)
        top3 = pos[:3]
        n += 1
        any3 += bool(top3)
        retreat += bool(set(top3) & set(RETREAT_CARDS))
    return {"n": n, "any_top3": any3, "retreat_in_top3": retreat}


def collision(points, arm, ids, toks_of, alias_tok) -> dict:
    """Alias collision: gold points where a non-gold card newly enters top3
    under `arm` (vs D0) while that card's entry is attributable to alias
    tokens (query shares tokens with that card's alias set)."""
    n_pts = new_entry = alias_driven = 0
    for p in points:
        if not p["gold"]:
            continue
        q = p["queries"][QUERY_OF[arm]]
        qt = toks(q) | toks(p["tl"])
        pos0, _ = rank(p["queries"]["Q0_POOR"], p["tl"], "D0_ORIGINAL",
                       ids, toks_of)
        pos1, _ = rank(q, p["tl"], arm, ids, toks_of)
        newcomers = [c for c in pos1[:3] if c not in pos0[:3]
                     and c not in p["gold"]]
        n_pts += 1
        if newcomers:
            new_entry += 1
            if any(qt & alias_tok.get(c, set()) for c in newcomers):
                alias_driven += 1
    return {"gold_points": n_pts, "points_with_new_nongold_top3": new_entry,
            "alias_driven": alias_driven}


def mechanism(points, ids, toks_of, alias_tok, sham_tok):
    rows = []
    for p in points:
        if not p["gold"]:
            continue
        for arm, qkey in (("D2_CARD_ALIGNED", "Q0_POOR"),
                          ("D3_BOTH", "Q2_STATE_GROUNDED"),
                          ("D_SHAM", "Q0_POOR")):
            q0 = p["queries"]["Q0_POOR"]
            qa = p["queries"][qkey]
            qt0 = toks(q0) | toks(p["tl"])
            qta = toks(qa) | toks(p["tl"])
            pos0, _ = rank(q0, p["tl"], "D0_ORIGINAL", ids, toks_of)
            pos1, _ = rank(qa, p["tl"], arm, ids, toks_of)
            extra = alias_tok if arm != "D_SHAM" else sham_tok
            for g in p["gold"]:
                base_set = toks_of["D0_ORIGINAL"][g]
                r0 = pos0.index(g) + 1 if g in pos0 else None
                r1 = pos1.index(g) + 1 if g in pos1 else None
                rows.append({
                    "episode": p["episode"], "turn": p["turn"],
                    "class": p["class"], "gold": g, "arm": arm,
                    "overlap_before": len(qt0 & base_set),
                    "overlap_after": len(qta & toks_of[arm][g]),
                    "matched_original_terms": sorted(qta & base_set)[:24],
                    "matched_alias_terms": sorted(qta & extra.get(g, set()))[:24],
                    "gold_rank_before": r0, "gold_rank_after": r1,
                })
    return rows


def main() -> None:
    pts = load_points()
    primary = [p for p in pts if p["set"] == "primary"]
    hardneg = [p for p in pts if p["set"] == "hardneg"]
    assert len(primary) == 120 and len(hardneg) == 14, \
        f"unexpected frozen set sizes {len(primary)}/{len(hardneg)}"
    ids, toks_of, alias_tok, sham_tok = build_token_sets()

    res = {"arms": {}, "gates": {}, "regression": {}}

    # ---- regression vs C1 anchors
    ok = True
    for arm, cond in (("D0_ORIGINAL", "Q0_POOR"),
                      ("D1_QUERY_RICH", "Q2_STATE_GROUNDED")):
        m = metrics(primary, arm, ids, toks_of)["ALL"]
        for k, v in C1_ANCHOR[("primary", cond)].items():
            match = abs(m[k] - v) < 5e-4
            ok &= match
            res["regression"][f"{arm}.{k}"] = {"got": m[k], "anchor": v,
                                               "match": match}
    perc17 = {arm: sum(1 for p in primary if p["class"] == "perception"
                       and (lambda pos: bool(set(pos[:3]) & set(p["gold"])))(
                           rank(p["queries"][QUERY_OF[arm]], p["tl"], arm,
                                ids, toks_of)[0]))
              for arm in ARMS}
    for arm, cond in (("D0_ORIGINAL", "Q0_POOR"),
                      ("D1_QUERY_RICH", "Q2_STATE_GROUNDED")):
        v = C1_ANCHOR[("perception17", cond)]["R@3"]
        match = perc17[arm] == v
        ok &= match
        res["regression"][f"{arm}.perception17_R@3"] = {
            "got": perc17[arm], "anchor": v, "match": match}
    hn0 = hardneg_metrics(hardneg, "D0_ORIGINAL", ids, toks_of)
    match = hn0["retreat_in_top3"] == C1_ANCHOR[("hardneg", "Q0_POOR")]["retreat_in_top3"]
    ok &= match
    res["regression"]["D0.hardneg_retreat"] = {
        "got": hn0["retreat_in_top3"],
        "anchor": C1_ANCHOR[("hardneg", "Q0_POOR")]["retreat_in_top3"],
        "match": match}
    res["regression"]["ALL_MATCH"] = ok
    print(f"== regression vs C1 anchors: {'PASS' if ok else 'FAIL'} ==")
    if not ok:
        for k, v in res["regression"].items():
            if isinstance(v, dict) and not v.get("match", True):
                print("   MISMATCH:", k, v)
        sys.exit(1)  # do not read anything else until anchors reproduce

    # ---- five arms
    for arm in ARMS:
        m = metrics(primary, arm, ids, toks_of)
        hn = hardneg_metrics(hardneg, arm, ids, toks_of)
        col = collision(primary, arm, ids, toks_of, alias_tok)
        res["arms"][arm] = {"primary": m, "hardneg": hn, "collision": col,
                            "perception17_hits": perc17[arm]}
        print(f"== {arm} ==")
        print("   ALL:", json.dumps(m["ALL"]))
        print("   per-class R@3:", {k: v["R@3"] for k, v in m.items()
                                    if k != "ALL"})
        print(f"   perception17 hits: {perc17[arm]}/17  hardneg: {hn}")

    # ---- mechanism log
    rows = mechanism(primary, ids, toks_of, alias_tok, sham_tok)
    with open(MECH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} mechanism rows -> {MECH.name}")

    # ---- pre-registered gates
    d0 = res["arms"]["D0_ORIGINAL"]["primary"]["ALL"]
    d2 = res["arms"]["D2_CARD_ALIGNED"]["primary"]["ALL"]
    sham = res["arms"]["D_SHAM"]["primary"]["ALL"]
    g1 = perc17["D2_CARD_ALIGNED"] >= 8
    nonp0 = [p for p in primary if p["class"] != "perception"]
    r3 = lambda arm, ps: sum(
        bool(set(rank(p["queries"][QUERY_OF[arm]], p["tl"], arm, ids,
                    toks_of)[0][:3]) & set(p["gold"])) for p in ps) / len(ps)
    g2 = r3("D2_CARD_ALIGNED", nonp0) >= r3("D0_ORIGINAL", nonp0) - 0.03
    hn2 = res["arms"]["D2_CARD_ALIGNED"]["hardneg"]
    g3 = (hn2["any_top3"] / hn2["n"]) <= (hn0["any_top3"] / hn0["n"]) + 0.05
    g4 = (perc17["D2_CARD_ALIGNED"] > perc17["D_SHAM"]) and \
         (d2["MRR"] > sham["MRR"])
    res["gates"] = {
        "1_D2_perception_R@3_ge_8of17": {"value": perc17["D2_CARD_ALIGNED"],
                                         "pass": g1},
        "2_nonperception_R@3_drop_le_3pp": {
            "D0": round(r3("D0_ORIGINAL", nonp0), 3),
            "D2": round(r3("D2_CARD_ALIGNED", nonp0), 3), "pass": g2},
        "3_hardneg_noise_le_+5pp": {"D0_any": hn0["any_top3"],
                                    "D2_any": hn2["any_top3"], "pass": g3},
        "4_D2_beats_D_SHAM": {"perception17": [perc17["D2_CARD_ALIGNED"],
                                               perc17["D_SHAM"]],
                              "MRR": [d2["MRR"], sham["MRR"]], "pass": g4},
    }
    print("== pre-registered gates ==")
    for k, v in res["gates"].items():
        print(f"   {'PASS' if v['pass'] else 'FAIL'}  {k}: {v}")
    res["offline_verdict"] = "GATE_PASSED" if all(
        v["pass"] for v in res["gates"].values()) else "GATE_FAILED"

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print("wrote", OUT, "| verdict:", res["offline_verdict"])


if __name__ == "__main__":
    main()
