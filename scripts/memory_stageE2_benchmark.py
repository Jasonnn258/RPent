#!/usr/bin/env python3
"""Stage E2c — four-arm retrieval benchmark: failure-origin query vs controls.

Frozen data: the 134 C1 decision points; Memory bank, retriever, candidate
set, lexical scoring ALL frozen (original Memory, no aliases, deployed raw
overlap rank). The ONLY variable is the query tail:

  E0_POOR          frozen online sparse query (regression anchor -> C1)
  E1_CURRENT_STATE frozen C1 rich query (historical negative anchor)
  E2_RAW_TRACE     + verbatim recent key events (no interpretation)
  E3_FAILURE_ORIGIN+ compressed SURFACE/ORIGIN/MISSING/EVIDENCE block

Pre-registered gates:
  (1) E3 perception R@3 >= 8/17
  (2) E3 overall R@3 > E1 by >= 5pp
  (3) E3 > E2_RAW_TRACE (overall R@3 +5pp OR perception hits +3)
  (4) non-perception R@3 drop vs E0 <= 3pp
  (5) hardneg irrelevant@3 worsens vs E0 by <= 5pp
  (6) audit non-UNKNOWN origin accuracy >= 80%   (measured in E2b)

Usage: python scripts/memory_stageE2_benchmark.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter

REPO = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"
DUMP = REPO / "analysis" / "stageE_origin_dump.jsonl"
OUT = REPO / "analysis" / "stageE_retrieval_results.json"
MECH = REPO / "analysis" / "stageE_retrieval_mechanism.jsonl"

ARMS = ["E0_POOR", "E1_CURRENT_STATE", "E2_RAW_TRACE", "E3_FAILURE_ORIGIN"]
C1_ANCHOR = {"R@1": 0.233, "R@3": 0.575, "R@5": 0.592, "MRR": 0.418,
             "irrelevant@3": 0.425}
D1_ANCHOR = {"R@1": 0.275, "R@3": 0.592, "R@5": 0.608, "MRR": 0.458,
             "irrelevant@3": 0.408}


def load_points():
    pts = [json.loads(l) for l in QUERIES.read_text().splitlines() if l.strip()]
    dump = {(r["episode"], r["turn"]): r
            for r in (json.loads(l) for l in DUMP.read_text().splitlines())}
    for p in pts:
        d = dump[(p["episode"], p["turn"])]
        p["queries"]["E0_POOR"] = p["queries"]["Q0_POOR"]
        p["queries"]["E1_CURRENT_STATE"] = p["queries"]["Q2_STATE_GROUNDED"]
        p["queries"]["E2_RAW_TRACE"] = d["q_E2_RAW_TRACE"]
        p["queries"]["E3_FAILURE_ORIGIN"] = d["q_E3_FAILURE_ORIGIN"]
        p["origin"] = d["origin"]
        p["surface"] = d["surface"]
    return pts


class Lexical:
    def __init__(self):
        self.cards = load_cards()
        self.index = load_index()
        self.ids = sorted(self.cards)
        self.doc = {c: toks(self.index.get(c, self.cards[c]["title"]))
                    | toks(c.replace("-", " ")) for c in self.ids}

    def pos_list(self, q: str, tl: str) -> list[str]:
        qt = toks(q) | toks(tl)
        scored = sorted(((len(qt & self.doc[c]), c) for c in self.ids),
                        reverse=True)
        return [c for s, c in scored
                if s > 0 and len(qt & self.doc[c]) > 0]


def metrics(points, lex: Lexical, arm: str):
    """points: gold rows only (all p['gold'] non-None)."""
    per: dict[str, Counter] = {}
    for p in points:
        pos = lex.pos_list(p["queries"][arm], p["tl"])
        top3 = pos[:3]
        c = per.setdefault(p["class"], Counter())
        g = set(p["gold"])
        c["n"] += 1
        c["R@1"] += bool(top3 and top3[0] in g)
        c["R@3"] += bool(set(top3) & g)
        c["R@5"] += bool(set(pos[:5]) & g)
        c["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                          if x in g), 0.0)
        c["irrelevant@3"] += bool(top3) and not set(top3) & g
    rows = {}
    for cls, c in sorted(per.items()):
        n = c["n"]
        rows[cls] = {
            "n": n,
            "R@1": round(c["R@1"] / n, 3),
            "R@3": round(c["R@3"] / n, 3),
            "R@5": round(c["R@5"] / n, 3),
            "MRR": round(c["MRR"] / n, 3),
            "irrelevant@3": round(c["irrelevant@3"] / n, 3),
        }
    # ALL over gold points only
    allc = Counter()
    for p in points:
        if p["gold"] is None:
            continue
        pos = lex.pos_list(p["queries"][arm], p["tl"])
        top3 = pos[:3]
        g = set(p["gold"])
        allc["n"] += 1
        allc["R@1"] += bool(top3 and top3[0] in g)
        allc["R@3"] += bool(set(top3) & g)
        allc["R@5"] += bool(set(pos[:5]) & g)
        allc["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                             if x in g), 0.0)
        allc["irrelevant@3"] += bool(top3) and not set(top3) & g
    n = allc["n"]
    rows["ALL"] = {"n": n,
                   "R@1": round(allc["R@1"] / n, 3),
                   "R@3": round(allc["R@3"] / n, 3),
                   "R@5": round(allc["R@5"] / n, 3),
                   "MRR": round(allc["MRR"] / n, 3),
                   "irrelevant@3": round(allc["irrelevant@3"] / n, 3)}
    return rows


def perception17(points, lex, arm):
    hits = 0
    for p in points:
        if p["class"] != "perception":
            continue
        pos = lex.pos_list(p["queries"][arm], p["tl"])[:3]
        hits += bool(set(pos) & set(p["gold"]))
    return hits


RETREAT_CARDS = ["predicate-fires-after-gripper-retreat",
                 "predicate-gated-by-eef-proximity-retreat-clear",
                 "open-retreat-settles-container", "basket-release-retreat-settle",
                 "basket-insertion-open-retreat"]


def hardneg_row(points, lex, arm):
    n = any3 = retreat = 0
    for p in points:
        if p["gold"] is not None:
            continue
        top3 = lex.pos_list(p["queries"][arm], p["tl"])[:3]
        n += 1
        any3 += bool(top3)
        retreat += bool(set(top3) & set(RETREAT_CARDS))
    return {"n": n, "any_top3": any3, "retreat_in_top3": retreat,
            "irr_rate": round(any3 / n, 3) if n else 0}


def mechanism(points, lex):
    with open(MECH, "w", encoding="utf-8") as fh:
        for p in points:
            if p["gold"] is None:
                continue
            for arm in ARMS:
                pos = lex.pos_list(p["queries"][arm], p["tl"])
                g = p["gold"][0]
                qt = toks(p["queries"][arm]) | toks(p["tl"])
                fh.write(json.dumps({
                    "episode": p["episode"], "turn": p["turn"],
                    "class": p["class"], "origin": p["origin"],
                    "surface": p["surface"], "arm": arm,
                    "top3": pos[:3],
                    "gold_in_top3": bool(set(pos[:3]) & set(p["gold"])),
                    "gold_rank": next((i + 1 for i, x in enumerate(pos)
                                       if x in p["gold"]), None),
                    "matched_terms": sorted(qt & lex.doc[g]),
                    "qlen": len(p["queries"][arm]),
                }, ensure_ascii=False) + "\n")


def main() -> None:
    pts = load_points()
    primary = [p for p in pts if p["set"] == "primary"]
    hard = [p for p in pts if p["set"] == "hardneg"]
    lex = Lexical()
    res = {"arms": {}, "gates": {}, "by_origin": {}, "regression": {}}

    # ---- regression anchors (must reproduce C1/D published numbers)
    ok = True
    for arm, anc in (("E0_POOR", C1_ANCHOR), ("E1_CURRENT_STATE", D1_ANCHOR)):
        m = metrics(primary, lex, arm)["ALL"]
        for k, v in anc.items():
            match = abs(m[k] - v) < 5e-4
            ok &= match
            res["regression"][f"{arm}.{k}"] = {"got": m[k], "anchor": v,
                                               "match": match}
    res["regression"]["ALL_MATCH"] = ok
    print("== regression vs C1(D0)/D1 anchors:", "PASS" if ok else "FAIL")
    if not ok:
        for k, v in res["regression"].items():
            if isinstance(v, dict) and not v.get("match", True):
                print("   MISMATCH:", k, v)
        sys.exit(1)

    for arm in ARMS:
        m = metrics(primary, lex, arm)
        hn = hardneg_row(hard, lex, arm)
        p17 = perception17(primary, lex, arm)
        qlen = sum(len(p["queries"][arm]) for p in primary) / len(primary)
        res["arms"][arm] = {"primary": m, "hardneg": hn,
                            "perception17_hits": p17,
                            "mean_query_len": round(qlen, 1)}
        print(f"== {arm} ==")
        print("   ALL:", json.dumps(m["ALL"]))
        print("   per-class R@3:", {k: v["R@3"] for k, v in m.items()
                                    if k != "ALL"})
        print(f"   perception17 {p17}/17  hardneg {hn}  mean qlen {qlen:.0f}")

    # by-origin breakdown (E3)
    for arm in ARMS:
        by = {}
        for org in ("PERCEPTION", "GRASP", "PLACE", "TRANSPORT", "NONE",
                    "UNKNOWN"):
            sub = [p for p in primary if p["origin"] == org]
            if not sub:
                continue
            pos = lambda p: lex.pos_list(p["queries"][arm], p["tl"])[:3]
            hit = sum(bool(set(pos(p)) & set(p["gold"])) for p in sub)
            by[org] = {"n": len(sub), "R@3": round(hit / len(sub), 3)}
        res["by_origin"][arm] = by
    print("\n== E3 by failure origin R@3 ==",
          json.dumps(res["by_origin"]["E3_FAILURE_ORIGIN"]))

    mechanism(primary, lex)

    # ---- gates
    a = {arm: res["arms"][arm] for arm in ARMS}
    e3, e2, e1, e0 = (a["E3_FAILURE_ORIGIN"], a["E2_RAW_TRACE"],
                      a["E1_CURRENT_STATE"], a["E0_POOR"])
    nonperc = {}
    for arm in ARMS:
        m = a[arm]["primary"]
        np_hit = sum(v["R@3"] * v["n"] for k, v in m.items()
                     if k not in ("ALL", "perception"))
        np_n = sum(v["n"] for k, v in m.items()
                   if k not in ("ALL", "perception"))
        nonperc[arm] = round(np_hit / np_n, 3)
    res["nonperception_R@3"] = nonperc
    gates = {
        "g1_perception": {"value": f"{e3['perception17_hits']}/17",
                          "pass": e3["perception17_hits"] >= 8},
        "g2_E3_gt_E1": {"E3": e3["primary"]["ALL"]["R@3"],
                        "E1": e1["primary"]["ALL"]["R@3"],
                        "pass": e3["primary"]["ALL"]["R@3"]
                        >= e1["primary"]["ALL"]["R@3"] + 0.05},
        "g3_E3_gt_E2": {"E3": e3["primary"]["ALL"]["R@3"],
                        "E2": e2["primary"]["ALL"]["R@3"],
                        "R@3_delta": round(e3["primary"]["ALL"]["R@3"]
                                           - e2["primary"]["ALL"]["R@3"], 3),
                        "perc_delta": e3["perception17_hits"]
                        - e2["perception17_hits"],
                        "pass": (e3["primary"]["ALL"]["R@3"]
                                 >= e2["primary"]["ALL"]["R@3"] + 0.05)
                        or (e3["perception17_hits"]
                            >= e2["perception17_hits"] + 3)},
        "g4_nonperc": {"E0": nonperc["E0_POOR"], "E3": nonperc["E3_FAILURE_ORIGIN"],
                       "drop": round(nonperc["E0_POOR"]
                                     - nonperc["E3_FAILURE_ORIGIN"], 3),
                       "pass": nonperc["E0_POOR"]
                       - nonperc["E3_FAILURE_ORIGIN"] <= 0.03},
        "g5_hardneg": {"E0_irr": e0["hardneg"]["irr_rate"],
                       "E3_irr": e3["hardneg"]["irr_rate"],
                       "pass": e3["hardneg"]["irr_rate"]
                       <= e0["hardneg"]["irr_rate"] + 0.05},
        "g6_audit": {"value": "47/52=.904 (stageE_origin_audit.md)",
                     "pass": True},
    }
    gates["all_pass"] = all(g["pass"] for g in gates.values()
                            if isinstance(g, dict) and "pass" in g)
    res["gates"] = gates
    print("\n== gates ==")
    for k, g in gates.items():
        if k != "all_pass":
            print(f"   {k}: {'PASS' if g['pass'] else 'FAIL'}  {g}")
    print("   ALL:", "PASS" if gates["all_pass"] else "FAIL")

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print("wrote", OUT, "and", MECH)


if __name__ == "__main__":
    main()
