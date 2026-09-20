#!/usr/bin/env python3
"""Stage E1 — discriminative lexical scoring diagnosis of the Stage D collapse.

Question: was part of the D2 alias collapse caused by RAW overlap scoring not
down-weighting domain-common words (gripper / release / pick / bowl ...)?

Conditions (data frozen: 134 C1 points, frozen gold, original Memory, frozen
468 aliases, hard negatives untouched):

  S0_ORIGINAL_RAW    raw overlap, base docs      — MUST reproduce D0 bit-exact
  S1_ALIAS_RAW       raw overlap, base+aliases   — MUST reproduce D2 bit-exact
  S2_ORIGINAL_BM25   standard BM25, base docs
  S3_ALIAS_BM25      standard BM25, base+aliases
  S4_ALIAS_TFIDF     cosine TF-IDF, base+aliases (auxiliary)

BM25: k1=1.5 b=0.75, idf=ln(1+(N-df+0.5)/(df+0.5)), tokenizer = the frozen
`toks()` (set semantics, each query term counted once), docs = the exact text
the raw scorer sees. Cut & tie-break mirror the deployed behavior: score>0,
top3, ties by card id descending.

Records per token: df / idf; per query: top-3 score, gold score, gold rank,
gold-vs-top-negative margin. Verdict: COMMON-TOKEN COLLISION CONFIRMED iff S3
recovers S0's overall R@3 (>= S0 - 3pp) AND hardneg noise does not worsen
by >5pp; else SCORING FIX NOT SUFFICIENT.

Usage: python scripts/memory_stageE1_scoring.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from rpent.memory.retrieval import load_cards, load_index, toks  # noqa: E402

QUERIES = REPO / "analysis" / "memory_stageC1_queries.jsonl"
SIDECAR = REPO / "analysis" / "retrieval_aliases_v1.json"
OUT = REPO / "analysis" / "stageE_scoring_results.json"

RETREAT_CARDS = ["predicate-fires-after-gripper-retreat",
                 "predicate-gated-by-eef-proximity-retreat-clear",
                 "open-retreat-settles-container", "basket-release-retreat-settle",
                 "basket-insertion-open-retreat"]

ARMS = ["S0_ORIGINAL_RAW", "S1_ALIAS_RAW", "S2_ORIGINAL_BM25",
        "S3_ALIAS_BM25", "S4_ALIAS_TFIDF"]
K1, B = 1.5, 0.75


def load_points():
    return [json.loads(l) for l in QUERIES.read_text().splitlines() if l.strip()]


def build_docs():
    cards, index = load_cards(), load_index()
    ids = sorted(cards)
    side = json.loads(SIDECAR.read_text())
    aliases = {c["memory_id"]: c["retrieval_aliases"] for c in side["cards"]}
    base_txt = {c: f"{index.get(c, cards[c]['title'])} {c.replace('-', ' ')}"
                for c in ids}
    alias_txt = {c: f"{base_txt[c]} {' '.join(aliases.get(c, []))}" for c in ids}
    return ids, base_txt, alias_txt


# ------------------------------------------------------------ scorers
def raw_rank(qt: set, doc_toks: dict, ids):
    scored = sorted(((len(qt & doc_toks[c]), c) for c in ids), reverse=True)
    return [(s, c) for s, c in scored if s > 0]


class BM25:
    def __init__(self, docs: dict, ids):
        self.ids = ids
        self.tf = {c: {} for c in ids}
        self.dl = {}
        for c in ids:
            # term frequency from the RAW text (not the toks() set):
            import re as _re
            words = [w for w in _re.findall(r"[a-z0-9]+", docs[c].lower())]
            self.tf[c] = {w: words.count(w) for w in set(words)}
            self.dl[c] = max(len(words), 1)
        self.N = len(ids)
        self.avgdl = sum(self.dl.values()) / max(self.N, 1)
        self.df = {}
        for c in ids:
            for w in self.tf[c]:
                self.df[w] = self.df.get(w, 0) + 1
        self.idf = {w: math.log(
            1 + (self.N - df + 0.5) / (df + 0.5)) for w, df in self.df.items()}

    def score(self, qt: set, c: str) -> float:
        s = 0.0
        tf, dl = self.tf[c], self.dl[c]
        for w in qt:
            if w not in tf:
                continue
            f = tf[w]
            s += self.idf.get(w, 0.0) * (f * (K1 + 1)) / (
                f + K1 * (1 - B + B * dl / self.avgdl))
        return s

    def rank(self, qt: set):
        scored = sorted(((self.score(qt, c), c) for c in self.ids),
                        reverse=True)
        return [(s, c) for s, c in scored if s > 0]


class TFIDF:
    """Cosine TF-IDF (auxiliary): doc vec = tf * idf, query vec = idf binary."""

    def __init__(self, bm: BM25):
        self.bm = bm

    def vec(self, c: str) -> dict:
        return {w: self.bm.tf[c][w] * self.bm.idf.get(w, 0.0)
                for w in self.bm.tf[c]}

    def rank(self, qt: set):
        out = []
        for c in self.bm.ids:
            v = self.vec(c)
            num = sum(self.bm.idf.get(w, 0.0) for w in qt if w in v)
            dn = math.sqrt(sum(x * x for x in v.values())) or 1.0
            if num / dn > 0:
                out.append((num / dn, c))
        return sorted(out, reverse=True)


def metrics(points, rank_fn) -> dict:
    out = {"ALL": {"n": 0, "R@1": 0, "R@3": 0, "R@5": 0, "MRR": 0.0,
                   "irrelevant@3": 0}}
    margins = []
    ranks = []
    for p in points:
        g = p["gold"]
        if g is None:
            continue
        qt = toks(p["queries"]["Q0_POOR"]) | toks(p["tl"])
        scored = rank_fn(qt)
        pos = [c for _s, c in scored]
        top3 = pos[:3]
        c = out["ALL"]
        c["n"] += 1
        c["R@1"] += bool(top3 and top3[0] in g)
        c["R@3"] += bool(set(top3) & set(g))
        c["R@5"] += bool(set(pos[:5]) & set(g))
        c["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                          if x in g), 0.0)
        c["irrelevant@3"] += not set(top3) & set(g)
        gr = next((i + 1 for i, x in enumerate(pos) if x in g), None)
        ranks.append(gr if gr else len(pos) + 1)
        gs = next((s for s, c2 in scored if c2 in g), 0.0)
        ns = next((s for s, c2 in scored if c2 not in g), 0.0)
        margins.append(ns - gs)
        cls = p["class"]
        out.setdefault(cls, {"n": 0, "R@1": 0, "R@3": 0, "R@5": 0, "MRR": 0.0,
                             "irrelevant@3": 0})
        cc = out[cls]
        cc["n"] += 1
        cc["R@1"] += bool(top3 and top3[0] in g)
        cc["R@3"] += bool(set(top3) & set(g))
        cc["R@5"] += bool(set(pos[:5]) & set(g))
        cc["MRR"] += next((1.0 / (i + 1) for i, x in enumerate(pos)
                           if x in g), 0.0)
        cc["irrelevant@3"] += not set(top3) & set(g)
    for cls, c in out.items():
        n = c["n"]
        for k in ("R@1", "R@3", "R@5", "irrelevant@3"):
            c[k] = round(c[k] / n, 3) if n else 0
        c["MRR"] = round(c["MRR"] / n, 3) if n else 0.0
    stats = {"mean_gold_rank": round(sum(ranks) / len(ranks), 1)
             if ranks else None,
             "mean_margin_topneg_minus_gold": round(
                 sum(margins) / len(margins), 3) if margins else None}
    return out, stats


def hardneg(points, rank_fn) -> dict:
    n = any3 = retreat = 0
    for p in points:
        if p["gold"] is not None:
            continue
        qt = toks(p["queries"]["Q0_POOR"]) | toks(p["tl"])
        pos = [c for _s, c in rank_fn(qt)]
        top3 = pos[:3]
        n += 1
        any3 += bool(top3)
        retreat += bool(set(top3) & set(RETREAT_CARDS))
    return {"n": n, "any_top3": any3, "retreat_in_top3": retreat}


def main() -> None:
    pts = load_points()
    primary = [p for p in pts if p["set"] == "primary"]
    hard = [p for p in pts if p["set"] == "hardneg"]
    ids, base_txt, alias_txt = build_docs()
    base_toks = {c: toks(base_txt[c]) for c in ids}
    alias_toks = {c: toks(alias_txt[c]) for c in ids}

    bm_base = BM25(base_txt, ids)
    bm_alias = BM25(alias_txt, ids)
    tf_alias = TFIDF(bm_alias)

    rankers = {
        "S0_ORIGINAL_RAW": lambda qt: raw_rank(qt, base_toks, ids),
        "S1_ALIAS_RAW": lambda qt: raw_rank(qt, alias_toks, ids),
        "S2_ORIGINAL_BM25": bm_base.rank,
        "S3_ALIAS_BM25": bm_alias.rank,
        "S4_ALIAS_TFIDF": tf_alias.rank,
    }

    res = {"arms": {}, "token_stats": {}, "regression": {}, "verdict": None}

    # regression vs Stage D published numbers
    anchors = {
        "S0_ORIGINAL_RAW": {"R@1": 0.233, "R@3": 0.575, "R@5": 0.592,
                            "MRR": 0.418, "irrelevant@3": 0.425},
        "S1_ALIAS_RAW": {"R@1": 0.083, "R@3": 0.275, "R@5": 0.442,
                         "MRR": 0.268, "irrelevant@3": 0.725},
    }
    ok = True
    for arm, anc in anchors.items():
        m, _ = metrics(primary, rankers[arm])
        m = m["ALL"]
        for k, v in anc.items():
            match = abs(m[k] - v) < 5e-4
            ok &= match
            res["regression"][f"{arm}.{k}"] = {"got": m[k], "anchor": v,
                                               "match": match}
    res["regression"]["ALL_MATCH"] = ok
    print("== regression vs Stage D:", "PASS" if ok else "FAIL")
    if not ok:
        for k, v in res["regression"].items():
            if isinstance(v, dict) and not v.get("match", True):
                print("   MISMATCH:", k, v)
        sys.exit(1)

    for arm, fn in rankers.items():
        m, mst = metrics(primary, fn)
        hn = hardneg(hard, fn)
        perc17 = sum(
            1 for p in primary if p["class"] == "perception"
            and bool(set([c for _s, c in fn(
                toks(p["queries"]["Q0_POOR"]) | toks(p["tl"]))][:3])
                & set(p["gold"])))
        res["arms"][arm] = {"primary": m, "stats": mst, "hardneg": hn,
                            "perception17_hits": perc17}
        print(f"== {arm} ==")
        print("   ALL:", json.dumps(m["ALL"]))
        print("   per-class R@3:", {k: v["R@3"] for k, v in m.items()
                                    if k != "ALL"})
        print(f"   perception17 {perc17}/17  hardneg {hn}  "
              f"gold_rank {mst['mean_gold_rank']}  "
              f"margin {mst['mean_margin_topneg_minus_gold']}")

    # token statistics: the Stage D collision tokens
    watch = ["gripper", "release", "pick", "bowl", "predicate", "move",
             "object", "false", "basket", "plate", "success", "wrist",
             "held", "target", "rim", "opening", "grasp", "pi0"]
    stats = {}
    for w in watch:
        stats[w] = {
            "df_base": bm_base.df.get(w, 0),
            "df_alias": bm_alias.df.get(w, 0),
            "idf_alias": round(bm_alias.idf.get(w, 0.0), 3),
            "raw_weight": 1.0,
            "idf_weight_vs_median_rare": None,
        }
    # relative scale: median idf of tokens with df<=5 (rare, discriminative)
    rare = sorted(v for w, v in bm_alias.idf.items()
                  if bm_alias.df.get(w, 0) <= 5)
    med_rare = rare[len(rare) // 2] if rare else 1.0
    for w in stats:
        stats[w]["median_rare_idf"] = round(med_rare, 3)
        iw = bm_alias.idf.get(w, 0.0)
        stats[w]["idf_weight_vs_median_rare"] = round(
            iw / med_rare, 3) if med_rare else None
    res["token_stats"] = stats
    print("\n== collision-token weights (alias corpus) ==")
    print(f"   median rare-token idf (df<=5): {med_rare:.3f}")
    for w, s in stats.items():
        print(f"   {w:10s} df_base={s['df_base']:2d} df_alias={s['df_alias']:2d}"
              f" idf={s['idf_alias']:.3f} rel_to_rare={s['idf_weight_vs_median_rare']}")

    # verdict
    s0 = res["arms"]["S0_ORIGINAL_RAW"]["primary"]["ALL"]["R@3"]
    s3 = res["arms"]["S3_ALIAS_BM25"]["primary"]["ALL"]["R@3"]
    hn0 = res["arms"]["S0_ORIGINAL_RAW"]["hardneg"]
    hn3 = res["arms"]["S3_ALIAS_BM25"]["hardneg"]
    recovers = s3 >= s0 - 0.03
    safe = (hn3["any_top3"] / max(hn3["n"], 1)) <= \
        (hn0["any_top3"] / max(hn0["n"], 1)) + 0.05
    res["verdict"] = {
        "S3_R@3": s3, "S0_R@3": s0, "recovers_S0_minus3pp": recovers,
        "hardneg_safe": safe,
        "scoring_diagnosis": ("COMMON-TOKEN COLLISION CONFIRMED"
                              if recovers and safe
                              else "SCORING FIX NOT SUFFICIENT")}
    print("\n== E1 verdict ==", json.dumps(res["verdict"]))

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
