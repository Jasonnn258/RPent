#!/usr/bin/env python3
"""P1 Pick-Gate Lab 追加分析(L1 离线,只读冻结 206 PRIMARY)。

在 gate_lab_v1 的 11 个预登记臂结果之上回答三个遗留问题:
  1) FN(工具 flag=False 且 FGONLY 代理为正)按门槛模式逐任务分解,并给出
     descent/lift/gap 的真实数值分布(区分"贴阈值"与"深度未达");
  2) min↔final 夹爪开度分歧的逐任务/旗标分布与其对臂指标的因果影响;
  3) 修正后门槛族的 LOTO 跨任务选择 + 逐 episode 配对 bootstrap 区间
     (样本不确定性描述,不是置信的概率陈述);
  4) descent 阈值敏感性网格(**仅描述,不选模**;不在此数据上产生"新优胜臂")。

纪律:预测只用 online 视图 tool_report;FGONLY 参考标签只在 scoring 出现;
不做任何阈值优化或胜者宣称;输出私有 JSON 留在 gitignored artifacts。
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from p1_offline_module_lab import load_data, metrics, ROOT, SRC
from p1_pick_gate_lab import (
    ARMS, D_THRESHOLD, L_THRESHOLD, G_THRESHOLD, gates, predict, score,
)

OUT = ROOT / "artifacts" / "p1_pick_gate_lab"

# 敏感性网格(描述用;含 0.10 冻结原值;不含任何"调出来的"新值)
DESCENT_GRID = (0.0, 0.03, 0.05, 0.07, 0.10)
BOOTSTRAP_REPEATS = 1000
BOOTSTRAP_SEED = 20261011


def _num(x):
    return type(x) in (int, float) and x == x and x not in (float("inf"), float("-inf"))


def _dist(values):
    """有限非负值的保守分布摘要(与 module lab failure_slices 同风格)。"""
    finite = sorted(v for v in values if _num(v) and v >= 0)
    if not finite:
        return {"n_valid": 0}
    def q(f):
        return round(finite[min(len(finite) - 1, int(f * (len(finite) - 1)))], 4)
    return {"n_valid": len(finite), "min": q(0.0), "p25": q(.25),
            "median": q(.5), "p75": q(.75), "max": q(1.0)}


def _diag(rep, key):
    d = rep.get("diagnostics", {})
    return d.get(key)


def fn_decomposition(rows):
    """56 个 proxy-FN 的门槛模式分解 + descent/lift/gap 数值分布。"""
    out = {}
    for task in sorted({r["task"] for r in rows}):
        fn_rows = [r for r in rows if r["task"] == task
                   and not r["tool_report"]["success"] and r["reference"]]
        pats = Counter()
        descents, lifts, finals, chunks_exhausted, near_threshold = [], [], [], 0, 0
        for r in fn_rows:
            b = gates(r["tool_report"])
            if b is None:
                pats["invalid"] += 1
                continue
            pat = "".join("1" if b[k] else "0" for k in ("D", "L", "G_final"))
            pats[pat] += 1
            descents.append(_diag(r["tool_report"], "descent_m"))
            lifts.append(r["tool_report"].get("peak_lift_m"))
            finals.append(r["tool_report"].get("final_gripper_opening"))
            rep = r["tool_report"]
            if rep.get("chunks_used") == rep.get("max_chunks"):
                chunks_exhausted += 1
            # "只缺 D"(011)案例里 descent 离 0.10 有多远
            if pat == "011":
                d = _diag(r["tool_report"], "descent_m")
                if _num(d) and d >= D_THRESHOLD - 0.03:
                    near_threshold += 1
        out[task] = {
            "n_fn": len(fn_rows),
            "gate_patterns_D_L_Gfinal": dict(sorted(pats.items())),
            "descent_m": _dist(descents),
            "peak_lift_m": _dist(lifts),
            "final_gripper_opening_m": _dist(finals),
            "n_chunks_used_eq_max": chunks_exhausted,
            "n_pattern011_descent_within_3cm_of_threshold": near_threshold,
        }
    return out


def task_geometry(rows):
    """逐任务的 eef 起点/下降/提升/开度分布——检验"任务几何决定 D 门槛可达性"。"""
    out = {}
    for task in sorted({r["task"] for r in rows}):
        rs = [r for r in rows if r["task"] == task]
        by_flag = {}
        for flag in (True, False):
            sub = [r["tool_report"] for r in rs
                   if r["tool_report"]["success"] is flag]
            by_flag["FLAG_T" if flag else "FLAG_F"] = {
                "n": len(sub),
                "start_eef_z": _dist([_diag(rep, "start_eef_z") for rep in sub]),
                "min_eef_z": _dist([_diag(rep, "min_eef_z") for rep in sub]),
                "descent_m": _dist([_diag(rep, "descent_m") for rep in sub]),
                "peak_lift_m": _dist([rep.get("peak_lift_m") for rep in sub]),
                "final_gripper_opening": _dist(
                    [rep.get("final_gripper_opening") for rep in sub]),
                "min_gripper_opening": _dist(
                    [rep.get("min_gripper_opening") for rep in sub]),
                "n_chunks_used_eq_max": sum(
                    1 for rep in sub if rep.get("chunks_used") == rep.get("max_chunks")),
                "n_libero_terminated": sum(
                    1 for rep in sub if rep.get("libero_terminated") is True),
            }
        out[task] = by_flag
    return out


def min_vs_final_detail(rows):
    """22 个 min↔final 分歧行:分布 + 对臂的差分(同一样本配对)。"""
    disagree = [r for r in rows
                if (b := gates(r["tool_report"]))
                and b["G_min"] != b["G_final"]]
    breakdown = Counter((r["task"], "FLAG_T" if r["tool_report"]["success"] else "FLAG_F")
                        for r in disagree)
    # 分歧方向:min<0.06(闭过)但 final>=0.06(末端又张开)
    reopened = sum(1 for r in disagree
                   if gates(r["tool_report"])["G_min"]
                   and not gates(r["tool_report"])["G_final"])
    arms = {}
    for pair in (("L_AND_Gfinal", "L_AND_Gmin"),
                 ("D_AND_L_AND_Gfinal", "D_AND_L_AND_Gmin")):
        a, b = score(rows, pair[0]), score(rows, pair[1])
        both = a["balanced_accuracy"] is not None and b["balanced_accuracy"] is not None
        arms[f"{pair[0]}_minus_{pair[1]}"] = {
            "d_tp": a["tp"] - b["tp"], "d_fp": a["fp"] - b["fp"],
            "d_fn": a["fn"] - b["fn"], "d_tn": a["tn"] - b["tn"],
            "d_bacc": round(a["balanced_accuracy"] - b["balanced_accuracy"], 6)
            if both else None,
        }
    return {"n_disagree": len(disagree),
            "by_task_flag": {f"{t}|{f}": n for (t, f), n in sorted(breakdown.items())},
            "n_min_closed_but_final_reopened": reopened,
            "paired_arm_differences": arms}


def paired_bootstrap_vs_flag(rows, arm, repeats=BOOTSTRAP_REPEATS,
                             seed=BOOTSTRAP_SEED):
    """episode 级聚类的配对重采样:arm−flag 的 BAcc 差区间(描述样本不确定性)。"""
    eps = defaultdict(list)
    for r in rows:
        eps[r["episode_id"]].append(r)
    keys = sorted(eps)
    rng = random.Random(seed)
    diffs = []
    for _ in range(repeats):
        sample = [row for _ in range(len(keys)) for row in eps[rng.choice(keys)]]
        a = score(sample, arm)["balanced_accuracy"]
        b = score(sample, "F0_tool_flag")["balanced_accuracy"]
        if a is not None and b is not None:
            diffs.append(a - b)
    diffs.sort()
    if not diffs:
        return {"n_valid": 0}
    return {"n_valid": len(diffs),
            "median": round(diffs[len(diffs) // 2], 6),
            "p95_interval": [round(diffs[int(.025 * (len(diffs) - 1))], 6),
                             round(diffs[int(.975 * (len(diffs) - 1))], 6)],
            "frac_ge_0": round(sum(1 for d in diffs if d >= 0) / len(diffs), 4)}


def loto_gate_family(rows):
    """11 臂门槛族的留一任务选择(与 module lab LOTO 同判据:BAcc 主、FAR 次)。"""
    tasks = sorted({r["task"] for r in rows})
    folds, pooled = [], Counter()
    for heldout in tasks:
        train = [r for r in rows if r["task"] != heldout]
        test = [r for r in rows if r["task"] == heldout]
        trained = {arm: score(train, arm) for arm in ARMS}

        def key(name):
            m = trained[name]
            return (-m["balanced_accuracy"], m["proxy_false_accept_rate"],
                    m["abstain"], name)

        chosen = min(ARMS, key=key)
        test_m = score(test, chosen)
        base = score(test, "F0_tool_flag")
        for k in ("tp", "fp", "fn", "tn", "abstain", "n"):
            pooled[k] += test_m[k]
        folds.append({"heldout_task": heldout, "selected_arm": chosen,
                      "train_bacc": trained[chosen]["balanced_accuracy"],
                      "train_flag_bacc": trained["F0_tool_flag"]["balanced_accuracy"],
                      "test_selected": test_m, "test_flag": base,
                      "delta_test_bacc": round(
                          test_m["balanced_accuracy"] - base["balanced_accuracy"], 6)})
    pooled_m = metrics(dict(pooled))
    pooled_flag = score(rows, "F0_tool_flag")
    return {"folds": folds, "pooled_test_selected": pooled_m,
            "pooled_test_flag": pooled_flag,
            "delta_pooled_bacc": round(
                pooled_m["balanced_accuracy"] - pooled_flag["balanced_accuracy"], 6),
            "caution": "三个非独立任务折;选择只用训练折代理标签;描述性迁移估计"}


def descent_sensitivity_descriptive(rows):
    """L∧Gfinal 前提下 descent 阈值扫描——只描述 rescued 质量随阈值的变化。"""
    out = {}
    for t in DESCENT_GRID:
        def pred(rep, _t=t):
            b = gates(rep)
            if b is None:
                return None
            descent = rep.get("diagnostics", {}).get("descent_m")
            if type(descent) not in (int, float) or descent != descent or descent < 0:
                return None
            return descent >= _t and b["L"] and b["G_final"]
        tp = fp = fn = tn = abst = 0
        for r in rows:
            p = pred(r["tool_report"])
            if p is None:
                abst += 1
                p = False
            y = r["reference"]
            if p and y: tp += 1
            elif p and not y: fp += 1
            elif not p and y: fn += 1
            else: tn += 1
        out[f"descent_gte_{t:.2f}"] = metrics(
            {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "abstain": abst})
    return {"note": "SENSITIVITY_DESCRIPTION_ONLY_NOT_MODULE_SELECTION",
            "grid": DESCENT_GRID, "overall": out}


def evaluate(rows):
    return {
        "protocol": "RPENT_P1_PICK_GATE_FOLLOWUP_V1",
        "n_primary": len(rows),
        "fn_gate_decomposition_by_task": fn_decomposition(rows),
        "task_geometry": task_geometry(rows),
        "min_vs_final_detail": min_vs_final_detail(rows),
        "paired_bootstrap_vs_flag": {
            arm: paired_bootstrap_vs_flag(rows, arm) for arm in
            ("L_AND_Gfinal", "D_AND_Gfinal", "D_AND_L_AND_Gfinal")},
        "loto_gate_family": loto_gate_family(rows),
        "descent_sensitivity": descent_sensitivity_descriptive(rows),
        "limitations": [
            "FGONLY 同技能弱代理;不构成持握真值或控制收益",
            "bootstrap 区间只描述 episode 聚类下的样本不确定性",
            "LOTO 三任务折非独立;不是确认性泛化证据",
            "descent 网格是描述性敏感性,禁止据此选臂宣称提升",
            "descent_m 为 4 位小数舍入的诊断值,阈值边缘比较受舍入影响",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=SRC)
    ap.add_argument("--output", type=Path, default=OUT)
    a = ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT / "artifacts").resolve()):
        ap.error("Output must be in gitignored artifacts")
    rows = load_data(a.input, strict=True)
    result = evaluate(rows)
    a.output.mkdir(parents=True, exist_ok=True)
    path = a.output / "followup_v1.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
