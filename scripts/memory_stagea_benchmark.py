#!/usr/bin/env python3
"""Stage A-2/A-3 — memory retrieval benchmark over the 240-point dataset.

Layer B (TRIGGER): Q0-observed trigger metrics computed from the actual
run.log of each decision point's episode (expected ~0 decision-time recall).

Layer C (RANK): four conditions over SHOULD_RETRIEVE=YES points
(and hard-negative discipline on NO points):
  Q0-fixed    lexical match on MEMORY.md index lines + filenames only
  Q1-semantic embedding similarity (query fields vs card title+body)
  Q2-phase    phase filter + semantic ranking
  Q3-structured semantic recall (top-20) + rule-based structured rerank

Forbidden features everywhere: evidence.cells, forward outcome, reward,
simulator hidden state (see analysis/memory_stageA_design.md).
Embeddings are benchmark tooling via the remote embedding API and are cached
under analysis/.cache_stagea_embed.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from build_memory_retrieval_queries import MAP, RETREAT_CARDS, load_cards  # noqa: E402

QUERIES = REPO / "analysis" / "memory_retrieval_queries.jsonl"
INDEX = REPO / "resources" / "libero" / "MEMORY.md"
OVPM = REPO / "logs" / "ovpm_exp"
CACHE = REPO / "analysis" / ".cache_stagea_embed.json"

STOP = set("""a an the and or of to in on at for with by from into onto is are was
were be been being it its this that these those not no does do did over under
near after before while during than then so as if but per via up down out off
you your we they he she i me my their them us has have had can could should
would may might will shall must""".split())

PHASE_KEYWORDS = {
    "P_look": ["segment", "label", "prompt", "ground", "disambiguation",
               "identity", "readable rgb", "brand"],
    "P_grasp": ["grasp", "pick", "grip", "closure", "regrasp", "handle",
                "visual grasp evidence", "carry"],
    "P_transport": ["reach", "wall", "move", "stall", "pitch", "offset",
                    "hang", "workspace"],
    "P_place": ["release", "seat", "insertion", "placement", "place",
                "container", "rim", "drop", "descend", "basket", "cavity",
                "leaned", "wedge"],
    "P_verify": ["predicate", "terminated", "verify", "confirmation",
                 "retreat", "settle", "watching libero_terminated"],
}


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP
            and len(w) > 2}


# ---------------------------------------------------------------- layer B
def parse_memory_reads(run_log: Path):
    """Return (reads, first_action_turn). reads = list of (turn, kind)."""
    reads, turn, first_act = [], -1, None
    mem_re = re.compile(r"resources/libero|libero/memory")
    act_re = re.compile(r"\[tool>\] (pi0_pick|pi0_doubled|move_to|move_pose|"
                        r"release|set_gripper|rotate_wrist)\(")
    try:
        lines = run_log.read_text().splitlines()
    except Exception:
        return reads, first_act
    for ln in lines:
        m = re.search(r"=== turn (\d+)/", ln)
        if m:
            turn = int(m.group(1))
            continue
        tm = re.search(r"\[tool>\] (read_text_file|list_dir|grep)\((.*)\)。\s*$", ln) \
            or re.search(r"\[tool>\] (read_text_file|list_dir|grep)\((.*)\)\s*$", ln)
        if tm and mem_re.search(tm.group(2)):
            reads.append((turn, tm.group(1)))
        if first_act is None and act_re.search(ln):
            first_act = turn
    return reads, first_act


def q0_observed_trigger(rows):
    cache = {}

    def reads_for(ep):
        if ep not in cache:
            cache[ep] = parse_memory_reads(OVPM / ep / "run.log")
        return cache[ep]

    stats = {"episodes": 0, "eps_with_reads": 0, "reads_before_first_action": 0,
             "last_read_turn_hist": Counter()}
    trig_yes = trig_no = 0
    slack_yes = 0
    per_class = defaultdict(lambda: [0, 0])  # cls -> [triggered, total]
    # B2 event turns and run.log turns can drift by ~2 (tool batches); the
    # slack variant tolerates +-3 turns to show the result is not an artifact.
    SLACK = 3
    for r in rows:
        reads, first_act = reads_for(r["episode"])
        # decision-time trigger: a memory consultation at/after this turn
        fired = any(t >= r["turn"] for t, _ in reads)
        slack_yes += any(t >= r["turn"] - SLACK for t, _ in reads)
        if r["should_retrieve"] == "YES":
            trig_yes += fired
            per_class[r["class"]][0] += fired
            per_class[r["class"]][1] += 1
        elif r["should_retrieve"] == "NO":
            trig_no += fired
    for ep in {r["episode"] for r in rows}:
        reads, first_act = reads_for(ep)
        stats["episodes"] += 1
        if reads:
            stats["eps_with_reads"] += 1
            stats["last_read_turn_hist"][max(t for t, _ in reads)] += 1
            if first_act is not None and max(t for t, _ in reads) < first_act:
                stats["reads_before_first_action"] += 1
    n_yes = sum(1 for r in rows if r["should_retrieve"] == "YES")
    n_no = sum(1 for r in rows if r["should_retrieve"] == "NO")
    return {
        "trigger_recall_yes": trig_yes / n_yes,
        "trigger_recall_yes_slack3": slack_yes / n_yes,
        "unnecessary_rate_no": trig_no / n_no,
        "triggered_total": trig_yes + trig_no,
        "trigger_precision": (trig_yes / (trig_yes + trig_no))
        if (trig_yes + trig_no) else None,
        "per_class_triggered": {k: f"{a}/{b}" for k, (a, b) in per_class.items()},
        **stats,
    }


# ---------------------------------------------------------------- embeddings
_MODEL = None


def _model():
    """Local bge-small-en-v1.5 via transformers (CPU; hf-mirror download).

    The remote embedding-3 API has no balance on this account — a local
    encoder keeps the benchmark reproducible and API-independent.
    """
    global _MODEL
    if _MODEL is None:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        import torch
        from transformers import AutoModel, AutoTokenizer
        name = "BAAI/bge-small-en-v1.5"
        tok = AutoTokenizer.from_pretrained(name)
        net = AutoModel.from_pretrained(name)
        net.eval()
        _MODEL = (tok, net)
    return _MODEL


def embed(texts, cache):
    """Mean-pooled CLS embeddings with an on-disk cache."""
    todo = []
    keys = {}
    for t in texts:
        k = hashlib.sha1(t.encode()).hexdigest()[:16]
        keys[t] = k
        if k not in cache:
            todo.append(t)
    if todo:
        import torch
        tok, net = _model()
        with torch.no_grad():
            for i in range(0, len(todo), 32):
                batch = todo[i:i + 32]
                enc = tok(batch, padding=True, truncation=True,
                          max_length=256, return_tensors="pt")
                out = net(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).float()
                vec = (out * mask).sum(1) / mask.sum(1).clamp(min=1)
                vec = torch.nn.functional.normalize(vec, dim=1)
                for t, v in zip(batch, vec.tolist()):
                    cache[keys[t]] = v
        json.dump(cache, open(CACHE, "w"))
    return {t: cache[keys[t]] for t in texts}


def cos(a, b):
    na, nb = 0.0, 0.0
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    return dot / ((na * nb) ** 0.5 + 1e-9)


# ---------------------------------------------------------------- conditions
def load_index():
    """(stem -> 'title — blurb') parsed from MEMORY.md global section."""
    out = {}
    for ln in INDEX.read_text().splitlines():
        m = re.match(r"- \[(.+?)\]\(global/(\S+?)\.md\) — (.+)$", ln)
        if m:
            out[m.group(2)] = f"{m.group(1)} {m.group(3)}"
    return out


def card_phases(card):
    text = " ".join([card["title"], card["applies_when"], card["symptom"]]).lower()
    return {p for p, kws in PHASE_KEYWORDS.items()
            if any(k in text for k in kws)}


def run_conditions(rows, cards, index, cache):
    yes = [r for r in rows if r["should_retrieve"] == "YES"]
    hn = [r for r in rows if r["class"] == "hard_negative"]

    card_ids = sorted(cards)
    # online-visible card text per condition
    index_text = {c: index.get(c, cards[c]["title"]) for c in card_ids}
    body_text = {c: " ".join([cards[c]["title"], cards[c]["applies_when"],
                              cards[c]["symptom"], cards[c]["how_to"]])
                 for c in card_ids}
    phases = {c: card_phases(cards[c]) for c in card_ids}

    q_texts = {}
    for r in yes + hn:
        q_texts[id(r)] = " | ".join([r["observation_summary"], r["symptom"]])

    emb_card_index = embed([index_text[c] for c in card_ids], cache)
    emb_card_body = embed([body_text[c] for c in card_ids], cache)
    emb_query = embed([q_texts[id(r)] for r in yes + hn], cache)
    emb_q = {id(r): emb_query[q_texts[id(r)]] for r in yes + hn}

    def q0_fixed(r):
        qt = toks(" ".join([r["observation_summary"], r["symptom"]]))
        scored = []
        for c in card_ids:
            it = toks(index_text[c]) | toks(c.replace("-", " "))
            scored.append((len(qt & it), c))
        scored.sort(reverse=True)
        return [c for s, c in scored if s > 0][:5], card_ids

    def q1_semantic(r):
        q = emb_q[id(r)]
        scored = sorted(((cos(q, emb_card_body[body_text[c]]), c)
                         for c in card_ids), reverse=True)
        return [c for s, c in scored[:5]], card_ids

    def q2_phase(r):
        ph = r["phase"]
        cand = [c for c in card_ids if ph in phases[c]] or card_ids
        q = emb_q[id(r)]
        scored = sorted(((cos(q, emb_card_body[body_text[c]]), c)
                         for c in cand), reverse=True)
        return [c for s, c in scored[:5]], cand

    def q3_structured(r):
        q = emb_q[id(r)]
        pool = sorted(((cos(q, emb_card_body[body_text[c]]), c)
                       for c in card_ids), reverse=True)[:20]
        cand = [c for _, c in pool]
        qt_obs = toks(r["observation_summary"])
        act = r["last_action"].lower()
        rescored = []
        for s, c in pool:
            card = cards[c]
            sc = 2.0 * s
            sc += 0.6 * len(qt_obs & toks(card["applies_when"]))
            sc += 0.4 * len(toks(r["symptom"]) & toks(card["symptom"]))
            if act and act.replace("pi0_", "") in (
                    card["applies_when"] + " " + card["symptom"]).lower():
                sc += 0.5
            if r["phase"] in phases[c]:
                sc += 0.4
            rescored.append((sc, c))
        rescored.sort(reverse=True)
        return [c for _, c in rescored[:5]], cand

    conds = {"Q0-fixed": q0_fixed, "Q1-semantic": q1_semantic,
             "Q2-phase": q2_phase, "Q3-structured": q3_structured}

    applicable = {}
    for r in yes:
        fam = set(MAP[r["class"]]["core"])
        for extra in MAP[r["class"]].get("container", {}).values():
            fam |= set(extra)
        for extra in MAP[r["class"]].get("object", {}).values():
            fam |= set(extra)
        for key in ("transport_stall", "doubled_fail"):
            fam |= set(MAP["recovery"].get(key, []))
        applicable[id(r)] = fam | set(r["gold_memory_ids"])

    results = {}
    for name, fn in conds.items():
        t0 = time.time()
        r1 = r3 = r5 = 0
        mrr = 0.0
        irr3 = 0.0
        app1 = app3 = 0
        cand_fail = rank_fail = 0
        per_class = defaultdict(lambda: [0, 0])
        for r in yes:
            top, cand = fn(r)
            gold = set(r["gold_memory_ids"])
            hits = [i for i, c in enumerate(top) if c in gold]
            r1 += bool(hits and hits[0] == 0)
            r3 += any(top[:3] and c in gold for c in top[:3])
            r5 += any(c in gold for c in top[:5])
            mrr += 1.0 / (hits[0] + 1) if hits else 0.0
            irr3 += sum(1 for c in top[:3] if c not in applicable[id(r)]) / 3.0
            app1 += bool(top and top[0] in applicable[id(r)])
            app3 += any(c in applicable[id(r)] for c in top[:3])
            if not (gold & set(cand)):
                cand_fail += 1
            elif not (gold & set(top)):
                rank_fail += 1
            per_class[r["class"]][0] += any(c in gold for c in top[:3])
            per_class[r["class"]][1] += 1
        lat = (time.time() - t0) / len(yes) * 1000
        hn_v = sum(1 for r in hn if set(fn(r)[0][:3]) & set(RETREAT_CARDS))
        results[name] = {
            "Recall@1": r1 / len(yes), "Recall@3": r3 / len(yes),
            "Recall@5": r5 / len(yes), "MRR": mrr / len(yes),
            "irrelevant@3": irr3 / len(yes),
            "applicable@1": app1 / len(yes), "applicable@3": app3 / len(yes),
            "candidate_fail": cand_fail / len(yes),
            "rank_fail": rank_fail / len(yes),
            "hn_violation@3": hn_v / len(hn) if hn else None,
            "latency_ms": lat,
            "recall@3_by_class": {k: f"{a}/{b}" for k, (a, b)
                                  in per_class.items()},
        }
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-embed", action="store_true",
                    help="skip conditions, run trigger layer only")
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(QUERIES)]
    main_rows = [r for r in rows if r["should_retrieve"] in ("YES", "NO")]

    trig = q0_observed_trigger(main_rows)
    print("== Q0-observed TRIGGER layer ==")
    print(json.dumps(trig, indent=2, default=str))

    if not args.skip_embed:
        cards = load_cards()
        index = load_index()
        cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        res = run_conditions(rows, cards, index, cache)
        print("\n== RANK layer (YES points, n=%d) ==" % sum(
            1 for r in rows if r["should_retrieve"] == "YES"))
        for name, m in res.items():
            print(name, json.dumps({k: (round(v, 3) if isinstance(v, float)
                                        else v) for k, v in m.items()},
                                   default=str))
        out = REPO / "analysis" / "memory_stageA_results.json"
        json.dump({"trigger_q0_observed": trig, "ranking": res},
                  open(out, "w"), indent=2, default=str)
        print("\nwrote", out)


if __name__ == "__main__":
    main()
