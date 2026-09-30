#!/usr/bin/env python
"""Stage L §9-10 — Round 1 决策分析(离线,读 rollouts.jsonl)。

职责:
1. 逐 rollout **离线重算 Verifier A**(prereg v1.1 前缀语义;ctx 从
   episode states.json 确定性重建,samples 内含 base eef —— 全链可离线
   复核,不信任运行期内嵌值);
2. stageL_round1_verification.csv:每 rollout 一行(快照 × 边 × k);
3. 晋升判定(prereg §10,一次性):
   - elig(c) = 族匹配 DEV 快照 − source_episodes 快照(episode 级);
     min-N:FG ≥6 / RPS ≥3;
   - exec_consistency = A-PASS / 全部非 infra rollout ≥0.95;
   - harm = elig 上 mean P̂_h ≤0.05;
   - f*(c) = c 的 elig 快照集上 P̂_v 均值最高的冻结合法边(配对);
   - Path A:mean[P̂_v(c,s) − P̂_v(f*,s)] ≥ +0.10 ∧ adv>0 占比 ≥50%;
   - Path B:U = elig 上全部冻结合法边 P̂_v=0 的快照;|U|≥3 ∧
     #{s∈U: P̂_v(c,s)≥0.5}/|U| ≥ 0.60;
   - PROMOTE ⇔ (A ∨ B) ∧ min-N ∧ exec ∧ harm;
4. pair 级排除敏感性 + Wilson 95% CI 并列报告。

用法:python scripts/stageL_round1_decision.py [--round 1]
产物:analysis/stageL_round{N}_verification.csv +
      analysis/stageL_round{N}_decision.md
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stagek_graph_executor import load_edges  # noqa: E402
from stageL_verify import load_candidates, verifier_a  # noqa: E402
from stagek_dataset_collect import (  # noqa: E402
    _last_pick_prompt, _load_source_steps, _task_language)

MIN_N = {"FALSE_GRASP": 6, "RELEASE_PREDICATE_STALL": 3}
TH_V = 0.5            # usefulness 阈值(prereg §12 同值)


def wilson(p, n, z=1.96):
    if n == 0:
        return (None, None)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=1)
    args = ap.parse_args()
    rnd = args.round

    log_root = REPO / f"logs/stageL_round{rnd}"
    recs = []
    for ln in open(log_root / "rollouts.jsonl"):
        r = json.loads(ln)
        if r.get("outcome") and not r.get("infra_error") and r.get("k"):
            recs.append(r)

    # Round 2(--no-frozen):冻结边 P̂ 复用 Round 1 同快照测量 —— 快照由
    # episode 重放确定性重建(readback 逐位校验),边未变,重测同一量只
    # 重复采样 pi0 非确定性;此处把 Round 1 冻结行以本轮 sid 重标并入
    if rnd > 1:
        prev = REPO / f"logs/stageL_round{rnd - 1}/rollouts.jsonl"
        for ln in open(prev):
            r = json.loads(ln)
            if (r.get("outcome") and not r.get("infra_error") and r.get("k")
                    and not r.get("is_candidate")):
                r["snapshot_id"] = (f"L{rnd}r_"
                                    + r["snapshot_id"].split("_", 1)[1])
                r["round"] = rnd      # 仅作显示;测量本身来自 round-1
                recs.append(r)

    # ---- 快照/ctx 重建 ------------------------------------------------------
    snaps = {}
    for r in csv.DictReader(open(REPO / "analysis/stageL_split_manifest.csv")):
        if r["role"] != "L_DISCOVERY_DEV":
            continue
        import hashlib
        sid = (f"L{rnd}r_t{r['task']}s{r['seed']}T{r['anchor_fire_step']}_"
               f"{hashlib.md5(r['episode_dir'].encode()).hexdigest()[:6]}")
        snaps[sid] = {"dir": r["episode_dir"], "task": r["task"],
                      "seed": r["seed"], "family": r["anchor_family"],
                      "pair": (int(r["task"]), int(r["seed"])),
                      "legal": r["legal_edges"].split("|")}
    ctx_cache = {}

    def ctx_of(sid):
        if sid not in ctx_cache:
            first = next(r for r in recs if r["snapshot_id"] == sid)
            steps = _load_source_steps(snaps[sid]["dir"])
            ctx_cache[sid] = (
                {"task_lang": _task_language(steps),
                 "last_pick": _last_pick_prompt(steps, first["T"])},
                first["samples"][0][1])
        return ctx_cache[sid]

    frozen = load_edges()
    cands = {c["id"]: c for c in load_candidates(
        REPO / f"analysis/stageL_candidate_edges_v{'0' if rnd == 1 else '1'}.jsonl")}
    edges = {**frozen, **cands}

    # 逐 rollout 离线重算 Verifier A(一次,缓存复用)
    for r in recs:
        e = edges.get(r["edge_id"])
        r["_va"] = (verifier_a(e, *ctx_of(r["snapshot_id"]), r)
                    if e is not None else {})

    # ---- 展开 CSV ------------------------------------------------------------
    out_csv = REPO / f"analysis/stageL_round{rnd}_verification.csv"
    fields = ["snapshot_id", "task", "seed", "family", "edge_id", "k",
              "is_candidate", "source_excluded", "outcome", "va_pass",
              "va_chain_abort", "va_problems", "perception_found",
              "d_ooi_z", "max_d_ooi_z", "peak_lift_m", "min_grip",
              "final_grip_pick", "check_success_ever", "corr_dz_eefz",
              "readback", "elapsed_s", "ts"]
    va_fail = sum(1 for r in recs if not r["_va"].get("pass"))
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            v = r.get("verify") or {}
            w.writerow({
                "snapshot_id": r["snapshot_id"],
                "task": r["task"], "seed": r["seed"],
                "family": r["family"], "edge_id": r["edge_id"], "k": r["k"],
                "is_candidate": r.get("is_candidate", False),
                "source_excluded": r.get("source_excluded", False),
                "outcome": r["outcome"],
                "va_pass": r["_va"].get("pass"),
                "va_chain_abort": r["_va"].get("chain_abort"),
                "va_problems": "; ".join(r["_va"].get("problems") or [])[:200],
                "perception_found": r.get("perception_found"),
                "d_ooi_z": v.get("d_ooi_z"), "max_d_ooi_z": v.get("max_d_ooi_z"),
                "peak_lift_m": v.get("peak_lift_m"), "min_grip": v.get("min_grip"),
                "final_grip_pick": v.get("final_grip_pick"),
                "check_success_ever": v.get("check_success_ever"),
                "corr_dz_eefz": v.get("corr_dz_eefz"),
                "readback": r.get("readback_max_abs_diff"),
                "elapsed_s": r.get("elapsed_s"), "ts": r.get("ts"),
            })

    # ---- (edge, snapshot) 汇总(A-PASS 且非 ERROR 才计效力)------------------
    eff = defaultdict(lambda: defaultdict(list))   # edge -> snap -> [outcomes]
    for r in recs:
        if r["outcome"] == "ERROR" or not r["_va"].get("pass"):
            continue  # A-FAIL / ERROR 不计入效力(prereg §7)
        eff[r["edge_id"]][r["snapshot_id"]].append(r["outcome"])

    def pv(e, s):
        o = eff.get(e, {}).get(s, [])
        return (sum(x == "VERIFIED_RECOVERY" for x in o) / len(o)) if o else None

    def ph(e, s):
        o = eff.get(e, {}).get(s, [])
        return (sum(x == "HARM" for x in o) / len(o)) if o else None

    # ---- 候选判定 ------------------------------------------------------------
    md = [f"# Stage L Round {rnd} 决策(DEV,prereg §10 一次性判定)", "",
          f"- rollouts: {len(recs)}(A-FAIL {va_fail} 条不计效力,单列)",
          f"- split_hash 77695bed7074 | K_ROLLOUT=4 | λ_harm=1.0", ""]
    decisions = {}
    for cid, c in cands.items():
        fam = c["failure_family"]
        src_eps = set(c["source_evidence"]["episodes"])
        fam_snaps = {s: m for s, m in snaps.items() if m["family"] == fam}
        elig = {s: m for s, m in fam_snaps.items()
                if m["dir"] not in src_eps and pv(cid, s) is not None}
        n_elig = len(elig)
        # exec_consistency:该候选全部非 infra rollout 的 A-PASS 占比
        all_rows = [r for r in recs if r["edge_id"] == cid
                    and r["outcome"] != "ERROR"]
        n_va = sum(1 for r in all_rows if r["_va"].get("pass"))
        exec_c = n_va / len(all_rows) if all_rows else None
        harm_c = (sum(ph(cid, s) for s in elig) / n_elig) if n_elig else None

        # f*:elig 集上 P̂_v 均值最高的冻结合法边(按快照 legal ∩ 全体冻结)
        frozen_pool = sorted({e for m in elig.values() for e in m["legal"]})
        f_star, best_mean = None, -1.0
        for fe in frozen_pool:
            vals = [pv(fe, s) for s in elig if pv(fe, s) is not None]
            mean = sum(vals) / len(vals) if vals else 0.0
            if mean > best_mean:
                f_star, best_mean = fe, mean
        advs = {s: (pv(cid, s) - pv(f_star, s))
                for s in elig if f_star and pv(f_star, s) is not None}
        mean_adv = sum(advs.values()) / len(advs) if advs else None
        pos_share = (sum(a > 0 for a in advs.values()) / len(advs)
                     if advs else None)
        U = {s for s in elig
             if all((pv(fe, s) or 0.0) == 0.0 for fe in frozen_pool)}
        cover = (sum((pv(cid, s) or 0.0) >= TH_V for s in U) / len(U)
                 if U else None)

        min_n_ok = n_elig >= MIN_N[fam]
        exec_ok = exec_c is not None and exec_c >= 0.95
        harm_ok = harm_c is not None and harm_c <= 0.05
        path_a = (mean_adv is not None and mean_adv >= 0.10
                  and pos_share is not None and pos_share >= 0.50)
        path_b = (U and len(U) >= 3 and cover is not None and cover >= 0.60)
        promote = (min_n_ok and exec_ok and harm_ok and (path_a or path_b))
        decisions[cid] = promote

        # pair 级排除敏感性(报告项):排除源 episode 所在 (task,seed) 对
        src_pairs = {m["pair"] for m in fam_snaps.values()
                     if m["dir"] in src_eps}
        n_elig_pair = sum(
            1 for s, m in fam_snaps.items()
            if m["pair"] not in src_pairs and pv(cid, s) is not None)
        md.append(
            f"## {cid}({fam},源 {c['source_evidence']['n_episodes']} 集)\n"
            f"- elig = {n_elig}(min-N {MIN_N[fam]} → "
            f"{'✓' if min_n_ok else '✗'})| exec_consistency "
            f"{exec_c if exec_c is None else round(exec_c, 3)} "
            f"({'✓' if exec_ok else '✗'})| harm "
            f"{harm_c if harm_c is None else round(harm_c, 3)} "
            f"({'✓' if harm_ok else '✗'})\n"
            f"- f* = {f_star}(elig 上 P̂_v 均值 {round(best_mean, 3)})"
            f"| mean_adv "
            f"{mean_adv if mean_adv is None else round(mean_adv, 3)}"
            f"| adv>0 占比 {pos_share if pos_share is None else round(pos_share, 2)}"
            f" → Path A {'✓' if path_a else '✗'}\n"
            f"- 冻结全零快照 |U| = {len(U)} | cover "
            f"{cover if cover is None else round(cover, 2)}"
            f" → Path B {'✓' if path_b else '✗'}\n"
            f"- pair 级排除敏感性:elig(pair) = {n_elig_pair}"
            f"(episode 级 {n_elig})\n"
            f"- **判定:{'PROMOTE' if promote else 'REJECT'}**\n")

    md += ["## 冻结边基线(同批 DEV 重跑,快照级 P̂_v)", ""]
    for fe in sorted({e for m in snaps.values() for e in m["legal"]}):
        per = [(s, pv(fe, s)) for s in snaps if pv(fe, s) is not None]
        if not per:
            continue
        mean_v = sum(v for _, v in per) / len(per)
        mean_h = sum(ph(fe, s) or 0 for s, _ in per) / len(per)
        md.append(f"- {fe}:n_snap={len(per)} mean P̂_v={round(mean_v, 3)} "
                  f"mean P̂_h={round(mean_h, 3)}")

    md += ["", "## 判定汇总", "",
           "| 候选 | 判定 |",
           "|---|---|"]
    for cid, ok in decisions.items():
        md.append(f"| {cid} | {'PROMOTE' if ok else 'REJECT'} |")
    out_md = REPO / f"analysis/stageL_round{rnd}_decision.md"
    out_md.write_text("\n".join(md))
    print("\n".join(md[-8:]))
    print(f"-> {out_csv}\n-> {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
