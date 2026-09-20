#!/usr/bin/env python3
"""Stage F0 — oracle typed routing vs frozen lexical baseline (four arms).

Frozen everywhere EXCEPT the candidate set (the typed address filter):
query text = deployed sparse E0_POOR for every arm; in-bucket ranking = the
deployed raw-overlap lexical scorer (>0 cut, id-desc tie-break). Arms:

  A0_LEXICAL        full 61-card bank        (regression anchor -> C1)
  A1_ORIGIN         address origin filter
  A2_ORIGIN_PREREQ  + canonical prerequisite (PREREQ_2<->3 merged)
  A3_TYPED_FULL     + phase / action compat  (falls back to A2 bucket)

Address = frozen Stage E extractor output (origin/missing/phase/action),
canonicalised per analysis/stageF_prerequisite_ontology.md section 3.
Rules, metrics and gates are pre-registered in analysis/stageF_router_rules.md.

Usage: python scripts/memory_stageF0_benchmark.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"
DUMP = REPO / "analysis" / "stageE_origin_dump.jsonl"
SIGS = REPO / "analysis" / "memory_activation_signatures_v1.json"
OUT = REPO / "analysis" / "stageF0_results.json"
MECH = REPO / "analysis" / "stageF0_mechanism.jsonl"

ARMS = ["A0_LEXICAL", "A1_ORIGIN", "A2_ORIGIN_PREREQ", "A3_TYPED_FULL"]
C1_ANCHOR = {"R@1": 0.233, "R@3": 0.575, "R@5": 0.592, "MRR": 0.418,
             "irrelevant@3": 0.425}
PREREQ_OF = {"VALID_TARGET_LOCALIZATION": "PREREQ_1",
             "OBJECT_MOVES_WITH_GRIPPER": "PREREQ_2",
             "CONFIRMED_SETTLED_TARGET_RELATION": "PREREQ_4"}   # else None


def load_points():
    pts = [json.loads(l) for l in QUERIES.read_text().splitlines() if l.strip()]
    dump = {(r["episode"], r["turn"]): r
            for r in (json.loads(l) for l in DUMP.read_text().splitlines())}
    for p in pts:
        d = dump[(p["episode"], p["turn"])]
        p["q"] = p["queries"]["Q0_POOR"]
        p["addr"] = {"origin": d["origin"],
                     "prereq": PREREQ_OF.get(d["missing"]),
                     "phase": d["phase"], "action": d["action"]}
    return pts


class TypedLexical:
    """Frozen lexical scorer + typed routing over the signature sidecar."""

    def __init__(self):
        self.cards = load_cards()
        self.index = load_index()
        self.ids = sorted(self.cards)
        self.doc = {c: toks(self.index.get(c, self.cards[c]["title"]))
                    | toks(c.replace("-", " ")) for c in self.ids}
        sig = json.loads(SIGS.read_text())
        self.sig = {c["memory_id"]: c for c in sig["cards"]}

    def origin_ok(self, addr, cid):
        o = self.sig[cid]["failure_origin"]
        return (not o) or (addr["origin"] in o)

    def prereq_ok(self, addr, cid):
        ps = self.sig[cid]["missing_prerequisites"]
        return (not ps) or (addr["prereq"] in ps)   # 2<->3 already one ID

    def phase_action_ok(self, addr, cid):
        s = self.sig[cid]
        ph, af = s["phase"], s["action_family"]
        return ((not ph or addr["phase"] in ph)
                and (not af or addr["action"] in af))

    def bucket(self, arm: str, addr: dict) -> list[str]:
        if arm == "A0_LEXICAL":
            return self.ids
        if addr["origin"] in ("NONE", "UNKNOWN", "", None):
            return self.ids                       # degrade A1 -> A0
        b1 = [c for c in self.ids if self.origin_ok(addr, c)]
        if arm == "A1_ORIGIN":
            return b1
        if addr["prereq"] is None:
            return b1                             # degrade A2 -> A1
        b2 = [c for c in b1 if self.prereq_ok(addr, c)]
        if arm == "A2_ORIGIN_PREREQ":
            return b2
        b3 = [c for c in b2 if self.phase_action_ok(addr, c)]
        return b3 if b3 else b2                   # fall back, never empty-hand

    def pos_list(self, q: str, tl: str, bucket: list[str]) -> list[str]:
        qt = toks(q) | toks(tl)
        scored = sorted(((len(qt & self.doc[c]), c) for c in bucket),
                        reverse=True)
        return [c for s, c in scored if s > 0]


def score(points, lex: TypedLexical, arm: str):
    """Metrics over gold rows + routing metrics; returns dict."""
    per: dict[str, Counter] = {}
    routed_hit = routed_n = 0
    perc_routed_hit = perc_routed_n = 0
    nomiss = 0
    bucket_sizes = []
    for p in points:
        b = lex.bucket(arm, p["addr"])
        bucket_sizes.append(len(b))
        pos = lex.pos_list(p["q"], p["tl"], b)[:3]
        g = set(p["gold"])
        routed_n += 1
        routed_hit += bool(g & set(b))
        if p["class"] == "perception":
            perc_routed_n += 1
            perc_routed_hit += bool(g & set(b))
        nomiss += not pos
        c = per.setdefault(p["class"], Counter())
        c["n"] += 1
        c["R@1"] += bool(pos) and pos[0] in g
        c["R@3"] += bool(set(pos) & g)
        c["R@5"] += bool(set(lex.pos_list(p["q"], p["tl"], b)[:5]) & g)
        c["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(
            lex.pos_list(p["q"], p["tl"], b)) if x in g), 0.0)
        c["irrelevant@3"] += bool(pos) and not set(pos) & g
    rows = {cls: {"n": c["n"], **{k: round(c[k] / c["n"], 3)
                                  for k in ("R@1", "R@3", "R@5", "MRR",
                                            "irrelevant@3")}}
            for cls, c in sorted(per.items())}
    allc = Counter()
    for p in points:
        b = lex.bucket(arm, p["addr"])
        pos = lex.pos_list(p["q"], p["tl"], b)[:3]
        g = set(p["gold"])
        for k, v in (("R@1", bool(pos) and pos[0] in g),
                     ("R@3", bool(set(pos) & g)),
                     ("R@5", bool(set(lex.pos_list(p["q"], p["tl"], b)[:5]) & g)),
                     ("MRR", next((1.0 / (i + 1) for i, x in enumerate(
                         lex.pos_list(p["q"], p["tl"], b)) if x in g), 0.0)),
                     ("irrelevant@3", bool(pos) and not set(pos) & g)):
            allc[k] += v
        allc["n"] += 1
    n = allc["n"]
    rows["ALL"] = {"n": n, **{k: round(allc[k] / n, 3) for k in
                              ("R@1", "R@3", "R@5", "MRR", "irrelevant@3")}}
    np_hit = sum(rows[c]["R@3"] * rows[c]["n"] for c in rows
                 if c not in ("ALL", "perception"))
    np_n = sum(rows[c]["n"] for c in rows if c not in ("ALL", "perception"))
    perc = rows.get("perception", {"n": 0, "R@3": 0.0})
    return {
        "primary": rows,
        "perception_hits": int(round(perc["R@3"] * perc["n"])),
        "perception_n": perc["n"],
        "nonperception_R@3": round(np_hit / np_n, 3) if np_n else 0.0,
        "gold_routing_recall": round(routed_hit / routed_n, 3),
        "perception_routing_recall": (round(perc_routed_hit / perc_routed_n, 3)
                                      if perc_routed_n else None),
        "nomatch_rate": round(nomiss / routed_n, 3),
        "mean_bucket": round(sum(bucket_sizes) / len(bucket_sizes), 1),
    }


def hardneg(points, lex: TypedLexical, arm: str):
    n = any3 = irr = nomiss = 0
    for p in points:
        b = lex.bucket(arm, p["addr"])
        top3 = lex.pos_list(p["q"], p["tl"], b)[:3]
        n += 1
        any3 += bool(top3)
        irr += bool(top3)
        nomiss += not top3
    return {"n": n, "any_top3": any3, "irr_rate": round(irr / n, 3),
            "nomatch_rate": round(nomiss / n, 3)}


def mechanism(points, lex: TypedLexical):
    with open(MECH, "w", encoding="utf-8") as fh:
        for p in points:
            for arm in ARMS:
                b = lex.bucket(arm, p["addr"])
                full = lex.pos_list(p["q"], p["tl"], b)
                qt = toks(p["q"]) | toks(p["tl"])
                fh.write(json.dumps({
                    "episode": p["episode"], "turn": p["turn"],
                    "class": p["class"], "arm": arm,
                    "addr": p["addr"], "bucket": len(b),
                    "gold_in_bucket": bool(set(p["gold"]) & set(b)),
                    "top3": full[:3], "no_match": not full,
                    "gold_rank": next((i + 1 for i, x in enumerate(full)
                                       if x in p["gold"]), None),
                    "gold_matched_terms": sorted(
                        qt & lex.doc[p["gold"][0]]),
                }, ensure_ascii=False) + "\n")


def main() -> None:
    pts = load_points()
    primary = [p for p in pts if p["set"] == "primary"]
    hard = [p for p in pts if p["set"] == "hardneg"]
    lex = TypedLexical()
    res = {"arms": {}, "gates": {}, "regression": {}}

    # G0 — regression anchor
    a0 = score(primary, lex, "A0_LEXICAL")
    ok = True
    for k, v in C1_ANCHOR.items():
        match = abs(a0["primary"]["ALL"][k] - v) < 5e-4
        ok &= match
        res["regression"][k] = {"got": a0["primary"]["ALL"][k], "anchor": v,
                                "match": match}
    res["regression"]["ALL_MATCH"] = ok
    print("== G0 regression vs C1 anchor:", "PASS" if ok else "FAIL")
    if not ok:
        print(json.dumps(res["regression"], indent=2))
        sys.exit(1)
    res["arms"]["A0_LEXICAL"] = {**a0, "hardneg": hardneg(hard, lex, "A0_LEXICAL")}

    for arm in ARMS[1:]:
        r = score(primary, lex, arm)
        res["arms"][arm] = {**r, "hardneg": hardneg(hard, lex, arm)}

    for arm in ARMS:
        a = res["arms"][arm]
        print(f"\n== {arm} ==")
        print("   ALL:", json.dumps(a["primary"]["ALL"]))
        print("   per-class R@3:", {k: v["R@3"] for k, v in a["primary"].items()
                                    if k != "ALL"})
        print(f"   perception {a['perception_hits']}/{a['perception_n']}"
              f"  routing_recall {a['gold_routing_recall']}"
              f"  perc_routing {a['perception_routing_recall']}"
              f"  nomatch {a['nomatch_rate']}  bucket {a['mean_bucket']}")
        print("   hardneg:", json.dumps(a["hardneg"]))

    mechanism(primary, lex)

    # gates (pre-registered)
    a0 = res["arms"]["A0_LEXICAL"]
    best = None
    for arm in ARMS[1:]:
        a = res["arms"][arm]
        g1 = a["perception_hits"] >= 10
        g2 = (a["primary"]["ALL"]["R@3"] >= a0["primary"]["ALL"]["R@3"] - 0.03
              and a0["nonperception_R@3"] - a["nonperception_R@3"] <= 0.03)
        if g1 and (best is None):
            best = arm
        res["gates"][f"{arm}.G1_perception"] = {
            "value": f"{a['perception_hits']}/{a['perception_n']}", "pass": g1}
        res["gates"][f"{arm}.G2_overall"] = {"pass": g2,
            "overall": a["primary"]["ALL"]["R@3"],
            "nonperc": a["nonperception_R@3"]}
    g3 = any((res["arms"][a]["perception_routing_recall"] or 0) >= 15 / 17
             for a in ("A2_ORIGIN_PREREQ", "A3_TYPED_FULL"))
    res["gates"]["G3_perc_routing_recall"] = {
        "A2": res["arms"]["A2_ORIGIN_PREREQ"]["perception_routing_recall"],
        "A3": res["arms"]["A3_TYPED_FULL"]["perception_routing_recall"],
        "pass": g3}
    g4 = (res["arms"]["A3_TYPED_FULL"]["hardneg"]["irr_rate"]
          <= a0["hardneg"]["irr_rate"] + 0.05)
    res["gates"]["G4_hardneg"] = {
        "A0": a0["hardneg"]["irr_rate"],
        "A3": res["arms"]["A3_TYPED_FULL"]["hardneg"]["irr_rate"], "pass": g4}
    res["gates"]["best_G1G2_arm"] = best
    res["gates"]["verdict"] = (
        "CONTINUE_TO_F1" if best else
        ("TYPED_ADDRESS_UPPER_BOUND_INSUFFICIENT_IN_BUCKET_RANK_FAIL"
         if g3 else "SIGNATURES_INSUFFICIENT"))
    print("\n== gates ==")
    for k, g in res["gates"].items():
        if isinstance(g, dict) and "pass" in g:
            print(f"   {k}: {'PASS' if g['pass'] else 'FAIL'}  {g}")
    print("   verdict:", res["gates"]["verdict"])

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print("wrote", OUT, "and", MECH)


if __name__ == "__main__":
    main()
