#!/usr/bin/env python
"""Stage K0 离线分析:K 阶梯表 + K_ROLLOUT 冻结判定(预注册 §5)。

输入:analysis/stageK0_rollouts.jsonl(逐 rollout)。
输出:analysis/stageK0_distribution_calibration.csv + 终端判定。

口径:
- 每 (snapshot, edge, k) 取该 k 的最后一条非序列化失败记录(infra 重试
  会产生同 k 多行,attempt 大者覆盖);
- 概率分母 = 非 infra rollout(四类含 ERROR 归一;另报三类条件概率);
- Wilson 95% CI;排序 = p̂_verified 降序,平分 p̂_harm 升序;
- K_ROLLOUT = 满足预注册 §5 三条的最小阶梯;K=16 不满足 → 报告
  "需追加到 20";20 仍不满足 → Stage K STOP。
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LADDER = [2, 4, 8, 12, 16, 20]
CLASSES = ("VERIFIED_RECOVERY", "NO_EFFECT", "HARM", "ERROR")


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.5
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h), h


def load_valid(path: Path):
    """→ {(snap, edge): {k: (outcome 或 None)}};infra 行记 None。"""
    per_k: dict[tuple, dict[int, dict]] = defaultdict(dict)
    for line in open(path):
        r = json.loads(line)
        if r.get("edge_id") is None or r.get("k") is None:
            continue
        key = (r["snapshot_id"], r["edge_id"])
        # 同 k 多 attempt:后写覆盖(runner 成功即 break,非 infra 行必最后)
        per_k[key][r["k"]] = r
    out = {}
    for key, ks in per_k.items():
        out[key] = {k: (None if r.get("infra_error") else r.get("outcome"))
                    for k, r in ks.items()}
    return out


def estimate(outcomes: list[str | None]) -> dict:
    """前 K 条(缺号按已有顺序截断)→ 概率 + CI。"""
    seq = [o for o in outcomes if o is not None]
    n = len(seq)
    n_all = len(outcomes)
    d = {"n": n, "n_infra_excluded": n_all - n}
    for c in CLASSES:
        cnt = seq.count(c)
        p = cnt / n if n else float("nan")
        lo, hi, h = wilson(p, n) if n else (0, 0, 0.5)
        d[f"p_{c.split('_')[0].lower()}"] = round(p, 4)
        d[f"ci_half_{c.split('_')[0].lower()}"] = round(h, 4)
    # 三类条件概率(排除 ERROR)
    n3 = sum(seq.count(c) for c in CLASSES[:3])
    if n3:
        for i, c in enumerate(CLASSES[:3]):
            key = ["verified", "no", "harm"][i]
            d[f"p3_{key}"] = round(seq.count(c) / n3, 4)
    return d


def rank_key(est: dict) -> tuple:
    return (-(est.get("p_verified") or 0), est.get("p_harm") or 0)


def main() -> int:
    path = REPO / (sys.argv[1] if len(sys.argv) > 1
                   else "analysis/stageK0_rollouts.jsonl")
    data = load_valid(path)
    if not data:
        print("无有效 rollout 记录")
        return 1
    kmax_avail = max(max(ks) for ks in data.values())
    ladder = [k for k in LADDER if k <= kmax_avail]
    print(f"组合数 {len(data)} | 可用 kmax {kmax_avail} | 阶梯 {ladder}\n")

    rows, est_by_k = [], {}
    for K in ladder:
        ests = {}
        for key, ks in data.items():
            got = [ks[k] for k in sorted(ks) if k <= K]
            # 只按已有 rollout 顺序取前 K 条(k 连续时即前 K)
            ests[key] = estimate(got)
        est_by_k[K] = ests
        for (snap, edge), e in sorted(ests.items()):
            rows.append({"K": K, "snapshot_id": snap, "edge_id": edge, **e})

    out_csv = REPO / "analysis/stageK0_distribution_calibration.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"CSV -> {out_csv}\n")

    # K_ROLLOUT 三条(预注册 §5)
    print("=== K_ROLLOUT 阶梯判定(门:CI_verif 中位≤0.30 ∧ 排序一致≥0.80 ∧ CI_harm 中位≤0.25)===")
    chosen = None
    for i, K in enumerate(ladder):
        ests = est_by_k[K]
        hv = sorted(e["ci_half_verified"] for e in ests.values())
        hh = sorted(e["ci_half_harm"] for e in ests.values())
        med_v = hv[len(hv) // 2]
        med_h = hh[len(hh) // 2]
        # 排序稳定:同 snapshot 内边对符号 vs 下一阶梯
        agree, n_pairs = None, 0
        if i + 1 < len(ladder):
            K2 = ladder[i + 1]
            agree = 0
            snaps = defaultdict(list)
            for (s, e) in ests:
                snaps[s].append(e)
            for s, eds in snaps.items():
                if len(eds) < 2:
                    continue
                eds = sorted(eds)
                for a in range(len(eds)):
                    for b in range(a + 1, len(eds)):
                        s1 = rank_key(ests[(s, eds[a])]) < rank_key(ests[(s, eds[b])])
                        s2 = rank_key(est_by_k[K2][(s, eds[a])]) < \
                            rank_key(est_by_k[K2][(s, eds[b])])
                        n_pairs += 1
                        agree += int(s1 == s2)
            agree = agree / n_pairs if n_pairs else None
        ok1 = med_v <= 0.30
        ok2 = agree is None or agree >= 0.80
        ok3 = med_h <= 0.25
        print(f"  K={K:2d}: CI_verif_med={med_v:.3f}{'✓' if ok1 else '✗'} "
              f"rank_agree={agree if agree is None else round(agree,3)}"
              f"{'✓' if ok2 else '✗'} CI_harm_med={med_h:.3f}"
              f"{'✓' if ok3 else '✗'}")
        if ok1 and ok2 and ok3 and chosen is None:
            chosen = K
    print(f"\n=== K_ROLLOUT 判定:{chosen if chosen else '未满足(见 STOP/追加规则)'} ===")

    # 组合级终值表(K = 阶梯最大可用)
    Kfin = ladder[-1]
    print(f"\n=== 终值表(K={Kfin})===")
    for (snap, edge), e in sorted(est_by_k[Kfin].items()):
        print(f"  {snap:12s} {edge:5s} n={e['n']:2d} "
              f"V={e['p_verified']:.3f} N={e.get('p_no', float('nan')):.3f} "
              f"H={e['p_harm']:.3f} E={e.get('p_error', float('nan')):.3f} "
              f"ciV={e['ci_half_verified']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
