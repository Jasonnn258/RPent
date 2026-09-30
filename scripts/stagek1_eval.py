#!/usr/bin/env python
"""Stage K1 评测 —— §7 指标 + §9 资格门(TEST 只在此触一次)。

指标(Arm × 3-seed 集成,TEST):
- P(VERIFIED) 校准/辨别:AUROC、AUPRC、Brier、NLL、ECE(10 bin)
- HARM:AUROC、AUPRC
- 边排序(快照内合法边):Top-1 best-edge recall、成对排序准确率、
  regret vs 经验最优(p̂_verified 主序 / p̂_harm 平分,同 K0 规)
- 族分解 FG / RPS(MCS 结构缺位,决策文档在案)
- 集成不确定度 std(诊断;K2 复用)

§9 门(B2 vs B1):Brier 相对降 ≥10% ∧ (排序 +8pp ∨ regret −20%);
HARM AUROC ≥0.75;全部可用族非负;B3 必须明显优于 B1
(操作化:Brier ≤0.9×B1 或 pairwise +8pp)。任一不满足 →
WORLD MODEL NOT JUSTIFIED → STOP,禁入 K2。

产物:analysis/stageK1_metrics.csv + analysis/stageK1_results.md
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from stagek1_train import Arm, TASKS, FAMS, REPO, batchify, load_samples

OUT_CSV = REPO / "analysis/stageK1_metrics.csv"
OUT_MD = REPO / "analysis/stageK1_results.md"


def ece(probs_pos, y_bin, bins=10):
    e, n = 0.0, len(probs_pos)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        m = (probs_pos >= lo) & (probs_pos < hi if b < bins - 1 else probs_pos <= hi)
        if m.sum() == 0:
            continue
        e += m.sum() / n * abs(probs_pos[m].mean() - y_bin[m].mean())
    return e


def load_arm(arm: str, samples, edges, device):
    """3-seed 集成 → 每样本 mean P(VERIFIED)/P(HARM)(+std 不确定度)。"""
    edge_ix = {e: i for i, e in enumerate(edges)}
    te = [x for x in samples if x["split"] == "TEST"]
    b = batchify(te, device)
    if arm == "B3":
        b["z"] = torch.cat([b["z"], b["z_post"]], -1)
    et = torch.tensor([edge_ix[x["edge"]] for x in te], device=device)
    pv, ph = [], []
    for seed in (0, 1, 2):
        ck = torch.load(REPO / f"logs/stageK1/ckpt_{arm}_s{seed}.pt",
                        map_location=device)
        m = Arm(arm, s_dim=len(te[0]["s"]), n_edges=len(edges)).to(device)
        m.load_state_dict(ck["state_dict"]); m.eval()
        with torch.no_grad():
            out = m(b, et)
            p = torch.softmax(out["logits"], -1)
        pv.append(p[:, 0].cpu().numpy()); ph.append(p[:, 2].cpu().numpy())
    pv, ph = np.stack(pv), np.stack(ph)
    return te, pv.mean(0), ph.mean(0), pv.std(0)


def rank_key(p_v, p_h):
    return (-p_v, p_h)


def ranking_metrics(te, pred_v, pred_h):
    """快照内合法边排序 vs 经验分布(K=4 rollouts 的 p̂)。"""
    by_snap = defaultdict(list)
    for i, x in enumerate(te):
        by_snap[x["snapshot"]].append(i)
    top1, pairs, regret_v, regret_h, n_snap = 0, [], [], [], 0
    for snap, idxs in by_snap.items():
        edges = sorted({te[i]["edge"] for i in idxs})
        if len(edges) < 2:
            continue
        n_snap += 1
        emp, prd = {}, {}
        for e in edges:
            ii = [i for i in idxs if te[i]["edge"] == e]
            y = np.array([te[i]["y"] for i in ii])
            emp[e] = (np.mean(y == 0), np.mean(y == 2))
            prd[e] = (float(np.mean([pred_v[i] for i in ii])),
                      float(np.mean([pred_h[i] for i in ii])))
        best = sorted(edges, key=lambda e: rank_key(*emp[e]))[0]
        top = sorted(edges, key=lambda e: rank_key(*prd[e]))[0]
        top1 += int(best == top)
        regret_v.append(emp[best][0] - emp[top][0])
        regret_h.append(emp[top][1] - emp[best][1])
        for a in range(len(edges)):
            for c in range(a + 1, len(edges)):
                e1, e2 = edges[a], edges[c]
                s_emp = rank_key(*emp[e1]) < rank_key(*emp[e2])
                s_prd = rank_key(*prd[e1]) < rank_key(*prd[e2])
                pairs.append(int(s_emp == s_prd))
    return {"top1_best_recall": top1 / n_snap if n_snap else float("nan"),
            "pairwise_acc": float(np.mean(pairs)) if pairs else float("nan"),
            "regret_verified": float(np.mean(regret_v)) if regret_v else float("nan"),
            "regret_harm": float(np.mean(regret_h)) if regret_h else float("nan"),
            "n_snapshots_ranked": n_snap}


def roc_auc(y_true, scores):
    """Mann-Whitney 秩法 AUROC(平均秩处理并列,无 sklearn 依赖)。"""
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    i = 0
    while i < len(scores):  # 并列取平均秩
        j = i
        while j + 1 < len(scores) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # 1-based 平均秩
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y_true == 1].sum() - n_pos * (n_pos + 1) / 2)
                 / (n_pos * n_neg))


def average_precision(y_true, scores):
    """阈值步进 AP(与 sklearn average_precision_score 同义,含并列处理)。"""
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    n_pos = int(y_true.sum())
    if n_pos == 0:
        return float("nan")
    order = np.argsort(-scores, kind="mergesort")
    ap, tp = 0.0, 0
    i = 0
    while i < len(scores):  # 同分组内合并为一个阈值
        j = i
        while j + 1 < len(scores) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        tp += int(y_true[order[i:j + 1]].sum())
        prec = tp / (j + 1)
        recall_prev = (tp - int(y_true[order[i:j + 1]].sum())) / n_pos
        recall = tp / n_pos
        ap += (recall - recall_prev) * prec
        i = j + 1
    return float(ap)


def arm_metrics(arm, samples, edges, device):
    te, pv, ph, ustd = load_arm(arm, samples, edges, device)
    yv = np.array([x["y"] == 0 for x in te], dtype=int)
    yh = np.array([x["y"] == 2 for x in te], dtype=int)
    nll = -np.mean([np.log(max(p, 1e-9)) if yi else np.log(max(1 - p, 1e-9))
                    for p, yi in zip(pv, yv)])
    m = {
        "arm": arm, "n_test": len(te),
        "verified_auroc": roc_auc(yv, pv),
        "verified_auprc": average_precision(yv, pv),
        "verified_brier": float(np.mean((pv - yv) ** 2)),
        "verified_nll": float(nll),
        "verified_ece": float(ece(pv, yv)),
        "harm_auroc": roc_auc(yh, ph) if yh.any() else float("nan"),
        "harm_auprc": average_precision(yh, ph) if yh.any() else float("nan"),
        "ens_std_mean": float(ustd.mean()),
    }
    m.update(ranking_metrics(te, pv, ph))
    # 族分解
    for fam in FAMS:
        idx = [i for i, x in enumerate(te) if x["family"] == fam]
        if len(idx) < 2:
            continue
        m[f"{fam[:2].lower()}_brier"] = float(np.mean((pv[idx] - yv[idx]) ** 2))
    return m, te, pv, ph


def main() -> int:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    samples, edges = load_samples()
    rows, per_arm = [], {}
    for arm in ("B0", "B1", "B2", "B3"):
        m, *_ = arm_metrics(arm, samples, edges, device)
        rows.append(m); per_arm[arm] = m
        print(json.dumps(m, ensure_ascii=False))

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # §9 门
    b1, b2, b3 = per_arm["B1"], per_arm["B2"], per_arm["B3"]
    brier_rel = (b1["verified_brier"] - b2["verified_brier"]) / b1["verified_brier"]
    rank_gain = b2["pairwise_acc"] - b1["pairwise_acc"]
    regret_rel = (b2["regret_verified"] - b1["regret_verified"]) / max(abs(b1["regret_verified"]), 1e-9)
    g1 = brier_rel >= 0.10 and (rank_gain >= 0.08 or regret_rel <= -0.20)
    g2 = b2["harm_auroc"] >= 0.75
    fam_ok = all(b2.get(f"{f}_brier", 0) <= b1.get(f"{f}_brier", 1) + 0.05
                 for f in ("fa", "re"))
    g3 = b3["verified_brier"] <= 0.9 * b1["verified_brier"] or \
        b3["pairwise_acc"] - b1["pairwise_acc"] >= 0.08
    gate = {"brier_rel_improve": round(brier_rel, 4),
            "pairwise_gain": round(rank_gain, 4),
            "regret_rel": round(regret_rel, 4),
            "g1_wm_vs_static": bool(g1), "g2_harm_auroc": bool(g2),
            "g3_oracle_beats_static": bool(g3),
            "families_nonneg": bool(fam_ok),
            "PASS": bool(g1 and g2 and g3 and fam_ok)}

    md = ["# Stage K1 结果(TEST 单触,3-seed 集成)", "",
          "| 指标 | " + " | ".join(per_arm) + " |",
          "|---|" + "---|" * len(per_arm)]
    keys = ["verified_auroc", "verified_auprc", "verified_brier", "verified_nll",
            "verified_ece", "harm_auroc", "harm_auprc", "top1_best_recall",
            "pairwise_acc", "regret_verified", "regret_harm", "ens_std_mean"]
    for k in keys:
        md.append(f"| {k} | " + " | ".join(
            f"{per_arm[a].get(k, float('nan')):.3f}" for a in per_arm) + " |")
    md += ["", "## §9 资格门", "", "```json",
           json.dumps(gate, ensure_ascii=False, indent=1), "```", "",
           "**判定:" + ("PASS → 可进 K2" if gate["PASS"]
                        else "FAIL → WORLD MODEL NOT JUSTIFIED → STOP(禁入 K2)")
           + "**", "",
           f"注:MCS 族结构缺位(K0 决策文档三证据),族条款按 FG/RPS 解读。"]
    OUT_MD.write_text("\n".join(md))
    print(f"-> {OUT_CSV}\n-> {OUT_MD}")
    print(json.dumps(gate, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
