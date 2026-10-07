#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage R §7-§10 — R2 分析:q 概率 / 持续谱 TYPE / retry 曲线 / 六假设门。

零 rollout:只读 R1 产物(same/resample rollouts CSV;NATURAL 陪报)。
规范:stageR_prereg.md §7-§10(统计单位 = event;禁把 24×8 写成 N=192;
Wilson CI + by-event bootstrap;TYPE 规则;门全部预注册)。

产物:stageR_event_probabilities.csv、stageR_persistence_map.csv、
stageR_retry_curves.csv、stageR_hypothesis_results.md。
"""
from __future__ import annotations

import csv
import datetime
import json
import math
import random
from pathlib import Path

ROOT = Path("/workspace/yjx/workspace/RPent")
CSV_SAME = ROOT / "analysis/stageR_same_action_rollouts.csv"
CSV_RES = ROOT / "analysis/stageR_resample_rollouts.csv"
MANIFEST = ROOT / "analysis/stageR_manifest.csv"
OUT_PROB = ROOT / "analysis/stageR_event_probabilities.csv"
OUT_MAP = ROOT / "analysis/stageR_persistence_map.csv"
OUT_CURVE = ROOT / "analysis/stageR_retry_curves.csv"
OUT_HYP = ROOT / "analysis/stageR_hypothesis_results.md"

BOOT_N = 10000
BOOT_SEED = 20261007          # 冻结:bootstrap 种子(prereg §12)
KS = (1, 2, 4, 8)             # C(k) 评估点


def wilson(s: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 区间(n=0 → (nan, nan))。"""
    if n == 0:
        return (float("nan"), float("nan"))
    p = s / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load_arm(path: Path, arm: str) -> dict[str, list[dict]]:
    """event_id → 该臂 trial 行(按 trial 升序;infra 行 stable='')。"""
    out: dict[str, list[dict]] = {}
    if not path.exists():
        return out
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r.get("arm") != arm or not r.get("event_id"):
            continue
        out.setdefault(r["event_id"], []).append(r)
    for v in out.values():
        v.sort(key=lambda x: int(x["trial"]))
    return out


def valid_trials(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("stable") != ""]


def seq_of(rows: list[dict]) -> list[int]:
    """trial 序 stable 0/1 序列(仅 valid;trial 缺号按已有序取)。"""
    return [1 if r["stable"] == "True" else 0 for r in valid_trials(rows)]


def acq_of(rows: list[dict]) -> list[int]:
    return [1 if r["acquisition"] == "True" else 0
            for r in valid_trials(rows)]


def bootstrap_mean(values: list[float]) -> tuple[float, float]:
    """by-event bootstrap 均值 95% CI(种子冻结)。"""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOT_SEED)
    n = len(values)
    means = sorted(
        sum(rng.choice(values) for _ in range(n)) / n for _ in range(BOOT_N))
    return (means[int(0.025 * BOOT_N)], means[int(0.975 * BOOT_N)])


def classify_type(same: list[int], pol: list[int]) -> str:
    """prereg §8 最少成功次数规则(K=8)。"""
    s, p = sum(same), sum(pol)
    if s >= 2:
        return "E_EXECUTION_EPHEMERAL"
    if s == 0 and p >= 2:
        return "A_ACTION_SPECIFIC"
    if s == 0 and p == 0:
        return "P_POLICY_PERSISTENT"
    return "U_UNRESOLVED"


def c_at(seqs: dict[str, list[int]], k: int) -> float:
    """C(k) = P(前 k 次内 ≥1 stable)(event-level,前 k 次齐全的事件)。"""
    use = [s[:k] for s in seqs.values() if len(s) >= k]
    if not use:
        return float("nan")
    return sum(1 for s in use if any(s)) / len(use)


def h_at(seqs: dict[str, list[int]], k: int) -> tuple[float, int]:
    """h(k) = P(第 k 次 stable | 前 k−1 次全失败);返回 (率, 分母事件数)。"""
    denom = [s for s in seqs.values() if len(s) >= k and not any(s[:k - 1])]
    if not denom:
        return (float("nan"), 0)
    return (sum(1 for s in denom if s[k - 1]) / len(denom), len(denom))


def main() -> int:
    same_rows = load_arm(CSV_SAME, "SAME")
    pol_rows = load_arm(CSV_RES, "RESAMPLE")
    nat_rows = load_arm(CSV_RES, "NATURAL")

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = [r for r in csv.DictReader(f) if r["role"] == "R1_COHORT"]

    # ---- per-event 概率 + TYPE -------------------------------------------
    prob_fields = ["event_id", "task", "seed", "t0", "n_same", "q_same",
                   "q_same_lo", "q_same_hi", "n_policy", "q_policy",
                   "q_policy_lo", "q_policy_hi", "q_same_acq",
                   "q_policy_acq", "same_stable", "policy_stable", "type",
                   "same_retryable", "robust_same", "policy_retryable",
                   "robust_policy", "same_persistent", "policy_persistent",
                   "strong_persistent", "infra_flag", "n_nat", "q_nat",
                   "q_nat_acq"]
    prob_rows, seq_same, seq_pol = [], {}, {}

    def acq_rate(rows: list[dict]) -> float:
        v = acq_of(rows)
        return (sum(v) / len(v)) if v else float("nan")

    for m in manifest:
        eid = m["event_id"]
        s_seq = seq_of(same_rows.get(eid, []))
        p_seq = seq_of(pol_rows.get(eid, []))
        n_seq = seq_of(nat_rows.get(eid, []))
        seq_same[eid], seq_pol[eid] = s_seq, p_seq
        s, p = sum(s_seq), sum(p_seq)
        lo, hi = wilson(s, len(s_seq))
        plo, phi = wilson(p, len(p_seq))
        n_valid_same = len(valid_trials(same_rows.get(eid, [])))
        n_all_same = len(same_rows.get(eid, []))
        infra_flag = (n_all_same - n_valid_same) > 0.5 * max(n_all_same, 1)
        nlo, nhi = wilson(sum(n_seq), len(n_seq))
        prob_rows.append({
            "event_id": eid, "task": m["task"], "seed": m["seed"],
            "t0": m["t0"], "n_same": len(s_seq), "q_same":
            s / len(s_seq) if s_seq else float("nan"),
            "q_same_lo": lo, "q_same_hi": hi, "n_policy": len(p_seq),
            "q_policy": p / len(p_seq) if p_seq else float("nan"),
            "q_policy_lo": plo, "q_policy_hi": phi,
            "q_same_acq": acq_rate(same_rows.get(eid, [])),
            "q_policy_acq": acq_rate(pol_rows.get(eid, [])),
            "same_stable": s, "policy_stable": p,
            "type": classify_type(s_seq, p_seq),
            "same_retryable": s >= 1, "robust_same": s >= 2,
            "policy_retryable": p >= 1, "robust_policy": p >= 2,
            "same_persistent": len(s_seq) > 0 and s == 0,
            "policy_persistent": len(p_seq) > 0 and p == 0,
            "strong_persistent": (len(s_seq) > 0 and len(p_seq) > 0
                                  and s == 0 and p == 0),
            "infra_flag": infra_flag,
            "n_nat": len(n_seq),
            "q_nat": (sum(n_seq) / len(n_seq)) if n_seq else float("nan"),
            "q_nat_acq": acq_rate(nat_rows.get(eid, [])) if n_seq
            else float("nan"),
        })
    with open(OUT_PROB, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=prob_fields)
        w.writeheader()
        w.writerows(prob_rows)

    # ---- persistence map(紧凑视图)---------------------------------------
    with open(OUT_MAP, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "q_same", "q_policy", "q_nat", "type",
                    "strong_persistent@8"])
        for r in prob_rows:
            w.writerow([r["event_id"], f"{r['q_same']:.3f}",
                        f"{r['q_policy']:.3f}",
                        f"{r['q_nat']:.3f}" if r["n_nat"] else "",
                        r["type"], r["strong_persistent"]])

    # ---- retry 曲线 C(k)/h(k) + Gain -------------------------------------
    curve_rows = []
    for arm, seqs in (("SAME", seq_same), ("POLICY", seq_pol)):
        cs = {k: c_at(seqs, k) for k in KS}
        for k in KS:
            h, dn = h_at(seqs, k)
            curve_rows.append({"arm": arm, "k": k, "C(k)": cs[k],
                               "h(k)": h, "h_denom": dn,
                               "n_events": sum(1 for s in seqs.values()
                                               if len(s) >= k)})
        curve_rows.append({"arm": arm, "k": "gain_1to2",
                           "C(k)": cs[2] - cs[1], "h(k)": "",
                           "h_denom": "", "n_events": ""})
        curve_rows.append({"arm": arm, "k": "gain_2to4",
                           "C(k)": cs[4] - cs[2], "h(k)": "",
                           "h_denom": "", "n_events": ""})
        curve_rows.append({"arm": arm, "k": "gain_4to8",
                           "C(k)": cs[8] - cs[4], "h(k)": "",
                           "h_denom": "", "n_events": ""})
    with open(OUT_CURVE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arm", "k", "C(k)", "h(k)",
                                          "h_denom", "n_events"])
        w.writeheader()
        w.writerows(curve_rows)

    # ---- 总体统计 ---------------------------------------------------------
    qs = [r["q_same"] for r in prob_rows if r["n_same"] > 0]
    qp = [r["q_policy"] for r in prob_rows if r["n_policy"] > 0]
    qs_sorted = sorted(qs)
    med_q = qp[len(qp) // 2] if qp else float("nan")
    frac_strong = (sum(1 for r in prob_rows if r["strong_persistent"])
                   / len(prob_rows)) if prob_rows else float("nan")
    lo_s, hi_s = bootstrap_mean(qs)
    lo_p, hi_p = bootstrap_mean(qp)
    types = {t: sum(1 for r in prob_rows if r["type"] == t)
             for t in ("E_EXECUTION_EPHEMERAL", "A_ACTION_SPECIFIC",
                       "P_POLICY_PERSISTENT", "U_UNRESOLVED")}
    # TRANSIENT 复现:臂内 pooled ACQ − STABLE gap
    def pooled_gap(seqs, rows_by_event):
        tot_acq = tot_stable = n = 0
        for eid, s in seqs.items():
            acqs = acq_of(rows_by_event.get(eid, []))
            tot_acq += sum(acqs)
            tot_stable += sum(s)
            n += len(s)
        return (tot_acq - tot_stable) / n if n else float("nan")
    gap_same = pooled_gap(seq_same, same_rows)
    gap_pol = pooled_gap(seq_pol, pol_rows)
    # C_pol 饱和点
    c_pol = {k: c_at(seq_pol, k) for k in KS}

    # ---- 六假设门(prereg §10)-------------------------------------------
    hyp = {}

    def verdict(cnt, name):
        if cnt >= 2:
            return "SUPPORTED"
        if cnt == 0:
            return "NOT_SUPPORTED"
        return "INCONCLUSIVE"

    hyp["EPHEMERAL_FAILURES_EXIST"] = (
        verdict(types["E_EXECUTION_EPHEMERAL"], "E"),
        f"TYPE E 事件数 = {types['E_EXECUTION_EPHEMERAL']}")
    hyp["ACTION_SPECIFIC_FAILURES_EXIST"] = (
        verdict(types["A_ACTION_SPECIFIC"], "A"),
        f"TYPE A 事件数 = {types['A_ACTION_SPECIFIC']}")
    hyp["POLICY_PERSISTENT_FAILURES_EXIST"] = (
        verdict(types["P_POLICY_PERSISTENT"], "P"),
        f"TYPE P 事件数 = {types['P_POLICY_PERSISTENT']}")
    if not qp:
        hyp["ONE_SHOT_FAILURE_IS_INFORMATIVE"] = ("INCONCLUSIVE", "无数据")
    elif med_q <= 0.25 and frac_strong >= 0.25:
        hyp["ONE_SHOT_FAILURE_IS_INFORMATIVE"] = (
            "SUPPORTED", f"median q_policy={med_q:.3f}≤.25 ∧ "
            f"STRONG_PERSISTENT 占比 {frac_strong:.1%}≥25%")
    elif med_q >= 0.50:
        hyp["ONE_SHOT_FAILURE_IS_INFORMATIVE"] = (
            "NOT_SUPPORTED", f"median q_policy={med_q:.3f}≥.50")
    else:
        hyp["ONE_SHOT_FAILURE_IS_INFORMATIVE"] = (
            "INCONCLUSIVE", f"median q_policy={med_q:.3f} 落在中间带")
    g48 = c_pol[8] - c_pol[4]
    g12 = c_pol[2] - c_pol[1]
    g24 = c_pol[4] - c_pol[2]
    if any(math.isnan(v) for v in (g48, g12, g24)):
        hyp["RETRY_GAIN_SATURATES_EARLY"] = ("INCONCLUSIVE", "C(k) 数据不全")
    elif g48 <= 0.05 and g24 <= g12:
        hyp["RETRY_GAIN_SATURATES_EARLY"] = (
            "SUPPORTED", f"C(8)−C(4)={g48:.3f}≤.05 ∧ 增益递减 "
            f"({g12:.3f}/{g24:.3f}/{g48:.3f})")
    elif g48 > 0.10:
        hyp["RETRY_GAIN_SATURATES_EARLY"] = (
            "NOT_SUPPORTED", f"C(8)−C(4)={g48:.3f}>.10")
    else:
        hyp["RETRY_GAIN_SATURATES_EARLY"] = (
            "INCONCLUSIVE", f"C(8)−C(4)={g48:.3f} 落在中间带")
    gaps = [g for g in (gap_same, gap_pol) if not math.isnan(g)]
    if gaps and max(gaps) >= 0.15:
        hyp["TRANSIENT_SUCCESS_REPLICATES"] = (
            "SUPPORTED", f"pooled ACQ−STABLE gap: SAME={gap_same:.3f} "
            f"POLICY={gap_pol:.3f}(任一 ≥.15)")
    elif gaps and max(gaps) < 0.05:
        hyp["TRANSIENT_SUCCESS_REPLICATES"] = (
            "NOT_SUPPORTED", f"双臂 gap <.05: SAME={gap_same:.3f} "
            f"POLICY={gap_pol:.3f}")
    else:
        hyp["TRANSIENT_SUCCESS_REPLICATES"] = (
            "INCONCLUSIVE", f"gap: SAME={gap_same:.3f} POLICY={gap_pol:.3f}")

    # ---- 输出 hypothesis md ----------------------------------------------
    L = [
        "# Stage R 六假设判定(prereg §10 预注册门)",
        "",
        f"生成:{datetime.datetime.now().isoformat(timespec='seconds')}",
        f"cohort 事件数:{len(prob_rows)}(统计单位 = event;全部指标 "
        "under FALSE_GRASP and current Pi0.5/runtime)",
        "",
        "## 总体统计",
        "",
        f"- q_same:mean={sum(qs) / len(qs):.3f} (boot95% "
        f"[{lo_s:.3f},{hi_s:.3f}]) median={qs_sorted[len(qs) // 2]:.3f};"
        f" fraction q>0 = {sum(1 for x in qs if x > 0)}/{len(qs)}",
        f"- q_policy:mean={sum(qp) / len(qp):.3f} (boot95% "
        f"[{lo_p:.3f},{hi_p:.3f}]) median={med_q:.3f};"
        f" fraction q>0 = {sum(1 for x in qp if x > 0)}/{len(qp)}",
        f"- TYPE 分布:E={types['E_EXECUTION_EPHEMERAL']} "
        f"A={types['A_ACTION_SPECIFIC']} P={types['P_POLICY_PERSISTENT']} "
        f"U={types['U_UNRESOLVED']}",
        f"- STRONG_PERSISTENT@8 占比:{frac_strong:.1%}",
        f"- Retryability@8:SAME≥1 {sum(1 for r in prob_rows if r['same_retryable'])}"
        f"/{len(prob_rows)};SAME≥2 {sum(1 for r in prob_rows if r['robust_same'])}"
        f";POLICY≥1 {sum(1 for r in prob_rows if r['policy_retryable'])}"
        f";POLICY≥2 {sum(1 for r in prob_rows if r['robust_policy'])}",
        f"- C(k) POLICY:" + " ".join(f"{k}:{c_pol[k]:.3f}" for k in KS),
        f"- h(k) POLICY:" + " ".join(
            f"{k}:{h_at(seq_pol, k)[0]:.3f}(n={h_at(seq_pol, k)[1]})"
            for k in KS if h_at(seq_pol, k)[1] > 0),
        f"- pooled ACQ−STABLE gap:SAME={gap_same:.3f} "
        f"POLICY={gap_pol:.3f}",
        f"- NATURAL(陪报,不入 C(k)):mean q_nat="
        f"{sum(r['q_nat'] for r in prob_rows if r['n_nat']) / max(1, sum(1 for r in prob_rows if r['n_nat'])):.3f}",
        "",
        "## 六判定",
        "",
        "| 假设 | 判定 | 依据 |",
        "|---|---|---|",
    ]
    for name, (v, why) in hyp.items():
        L.append(f"| {name} | {v} | {why} |")
    L += [
        "",
        "## 措辞纪律(prereg §10)",
        "",
        "0/K 只写 persistent@8,禁写\"绝对不可恢复\";禁写"
        "\"most failures are stochastic\" / \"same-action retry is "
        "sufficient\" / \"persistent failures need learning\""
        "(spec §32 强结论门槛)。",
        "",
    ]
    OUT_HYP.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[R2] 事件 {len(prob_rows)};判定写入 {OUT_HYP.name}")
    for name, (v, why) in hyp.items():
        print(f"  {name}: {v} ({why})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
