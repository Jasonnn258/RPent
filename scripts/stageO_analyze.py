#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §27-§30 — first-source 分析与五假设独立判定(确定性,零 LLM)。

输入(全部已冻结产物):stageO_split_manifest.csv / stageO_reference_traces.jsonl /
stageO_rollouts.csv / stageO_reentry_results.csv / stageO_arm_transitions.jsonl。
输出:analysis/stageO_first_source.csv + analysis/stageO_hypothesis_results.md。

判定口径(prereg §9-§11):
- RECOVERY_PRESENT := successes ≥ max(2, ceil(0.25×n)) 且 rate ≥ 25%
  (n = K_ROLLOUT 或 16;INFRA_ABORT / 结构性跳过行不计入 n);
- 三版 first-source(spec §27):TASK_RECOVERY 契约版 / POLICY_REENTRY 版 /
  RECOVERY = 两者之并(任一结局达标即算);
- 假设 H_A..H_E 逐个独立判定,禁总 PASS/FAIL、禁多数 vote。

用法:python scripts/stageO_analyze.py(幂等,重跑覆盖两个输出文件)
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt
import stageO_ladder as L            # 复用 load_references / recovery_present / REALIGNMENT

MANI = REPO / "analysis/stageO_split_manifest.csv"
REFJ = REPO / "analysis/stageO_reference_traces.jsonl"
ROLL = REPO / "analysis/stageO_rollouts.csv"
REENT = REPO / "analysis/stageO_reentry_results.csv"
TRANS = REPO / "analysis/stageO_arm_transitions.jsonl"
OUT_CSV = REPO / "analysis/stageO_first_source.csv"
OUT_MD = REPO / "analysis/stageO_hypothesis_results.md"

ARMS = ["O0", "O1", "O2", "O3", "O4"]
SKIP_NOTES = {"no_pi05_cmd_in_prefix", "no_pi05_in_ref_domain",
              "oracle_prompt_missing"}


def read_csv_skip_comments(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [l for l in open(path, encoding="utf-8")
             if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def valid_row(r: dict) -> bool:
    """有效 rollout 行:非 infra_abort、非结构性跳过(contract_met 已填)。"""
    return (not r.get("infra_abort") and r.get("contract_met") != ""
            and r.get("contract_met") is not None
            and r.get("note") not in SKIP_NOTES)


def wilson(s: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = s / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def load_reentry() -> dict[tuple[str, str, int], dict]:
    out = {}
    for r in read_csv_skip_comments(REENT):
        try:
            key = (r["snapshot_id"], r["arm"], int(r["rollout_idx"]))
        except (KeyError, TypeError, ValueError):
            continue
        out[key] = r
    return out


def load_transitions() -> dict[tuple[str, int], dict]:
    out = {}
    if TRANS.exists():
        for line in open(TRANS, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            out[(d.get("snapshot_id"), int(d.get("rollout_idx", -1)))] = d
    return out


def arm_flags(rows: list[dict], reent: dict, sid: str, arm: str,
              outcome: str) -> list[bool]:
    """(snapshot, arm) 的结局 flags;outcome ∈ task|reentry|union。"""
    task, re_ = [], []
    for r in rows:
        if r["snapshot_id"] != sid or r["arm"] != arm or not valid_row(r):
            continue
        task.append(r["contract_met"] == "True")
        er = reent.get((sid, arm, int(r["rollout_idx"])))
        re_.append((er or {}).get("reentry") == "True")
    if outcome == "task":
        return task
    if outcome == "reentry":
        return re_
    return [t or e for t, e in zip(task, re_)]


def ladder_label(present: dict[str, bool], ref_ok: bool,
                 ox_ok: bool = False) -> str:
    """§10 sequential 规则 → 首现层标签。"""
    if present.get("O1"):
        return "O1_POLICY_SUPPORT"
    if present.get("O2"):
        return "O2_CONDITIONING"
    if present.get("O3"):
        return "O3_FIXED_SEQUENCE"
    if present.get("O4"):
        # ref 不可用 ⇒ O2/O3 未测(§10 特例标签)
        return "O4_REPLANNING_BELOW_UNTESTED" if not ref_ok else "O4_REPLANNING"
    if ox_ok:
        return "OX_EXPERT_ONLY"
    return "NO_SOURCE_FOUND" if ref_ok else "REFERENCE_UNAVAILABLE"


def read_manifest() -> list[dict]:
    lines = [l for l in open(MANI, encoding="utf-8") if not l.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("".join(lines))))
    assert rows, "stageO_split_manifest.csv 无数据行"
    return rows


def read_k_rollout() -> int:
    m = __import__("re").search(r"K_ROLLOUT\s*=\s*(\d+)",
                                CALIB.read_text(encoding="utf-8"))
    assert m, f"{CALIB} 缺 K_ROLLOUT 冻结行"
    return int(m.group(1))


def load_references() -> dict[str, dict | None]:
    """与 stageO_ladder.load_references 同规则(此处独立 IO)。"""
    refs: dict[str, dict | None] = {}
    if not REFJ.exists():
        return refs
    for line in open(REFJ, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        sid = d.get("snapshot_id")
        if sid is None:
            continue
        if d.get("attempt_idx") == 1:
            refs[sid] = None
        if (d.get("contract_met") or d.get("check_success")) \
                and not d.get("infra_attempt"):
            if refs.get(sid) is None:
                refs[sid] = d
    return refs


def main() -> int:
    mani = read_manifest()
    refs = load_references()
    rows = read_csv_skip_comments(ROLL)
    reent = load_reentry()
    trans = load_transitions()
    sids = [s["snapshot_id"] for s in mani]
    K = read_k_rollout()
    ts = datetime.now().isoformat()

    # ---- per snapshot × arm × outcome ------------------------------------
    flags = {(sid, arm, oc): arm_flags(rows, reent, sid, arm, oc)
             for sid in sids for arm in ARMS for oc in ("task", "reentry",
                                                        "union")}
    present = {(sid, arm, oc): L.recovery_present(flags[(sid, arm, oc)])
               for sid in sids for arm in ARMS for oc in
               ("task", "reentry", "union")}
    rate = {(sid, arm): (sum(flags[(sid, arm, "task")])
                         / len(flags[(sid, arm, "task")])
                         if flags[(sid, arm, "task")] else None)
            for sid in sids for arm in ARMS}
    n_valid = {(sid, arm): len(flags[(sid, arm, "task")])
               for sid in sids for arm in ARMS}

    # ---- first-source 三版 -------------------------------------------------
    labels = {}
    for oc, col in (("union", "first_recovery_source"),
                    ("reentry", "first_reentry_source"),
                    ("task", "first_task_recovery_source")):
        for sid in sids:
            labels[(sid, col)] = ladder_label(
                {a: present[(sid, a, oc)] for a in ARMS},
                ref_ok=refs.get(sid) is not None)

    # ---- P(Ox first) 分布 ---------------------------------------------------
    dist = {oc: defaultdict(int) for oc in
            ("union", "reentry", "task")}
    for sid in sids:
        for oc, col in (("union", "first_recovery_source"),
                        ("reentry", "first_reentry_source"),
                        ("task", "first_task_recovery_source")):
            dist[oc][labels[(sid, col)]] += 1

    # ---- Δ 配对(机制定位)---------------------------------------------------
    def paired(a: str, b: str) -> dict:
        """Δab = rate(a) − rate(b),task 结局,paired by snapshot。"""
        ds, pairs = [], []
        for sid in sids:
            ra, rb = rate[(sid, a)], rate[(sid, b)]
            if ra is None or rb is None:
                continue
            ds.append(ra - rb)
            pairs.append((sid, round(ra - rb, 3)))
        pos = sum(1 for d in ds if d > 0)
        neg = sum(1 for d in ds if d < 0)
        return {"n": len(ds), "mean": (sum(ds) / len(ds)) if ds else None,
                "pos": pos, "neg": neg, "pairs": pairs}

    # Δ 语义 = 后臂 − 前臂(Δ01 = O1 − O0,prereg §11 "O1 优于 O0")
    deltas = {
        "Δ01": paired("O1", "O0"),
        "Δ12": paired("O2", "O1"),
        "Δ23": paired("O3", "O2"),
        "Δ34": paired("O4", "O3"),
    }

    # ---- 假设判定(§30,独立)----------------------------------------------
    o1_present_task = [s for s in sids if present[(s, "O1", "task")]]
    o2_where_o1_not = [s for s in sids
                       if present[(s, "O2", "task")]
                       and not present[(s, "O1", "task")]]
    o3_where_o2_not = [s for s in sids
                       if present[(s, "O3", "task")]
                       and not present[(s, "O2", "task")]]
    o4_where_o3_not = [s for s in sids
                       if present[(s, "O4", "task")]
                       and not present[(s, "O3", "task")]]
    d01 = deltas["Δ01"]

    # H_D 附加证据:成功 O4 rollout 的 state-dependent 变化(§22)
    o4_replan_evidence = []
    for (sid, ri), t in trans.items():
        if not t.get("contract_met"):
            continue
        changed = any(t2.get("subgoal_changed") for t2 in t.get("turns") or [])
        diverged = t.get("first_divergence") is not None
        o4_replan_evidence.append({"snapshot": sid, "rollout": ri,
                                   "subgoal_changed": changed,
                                   "diverged_from_O3": diverged})

    hyp = {}
    hyp["H_A POLICY SUPPORT"] = (
        "SUPPORTED" if (len(o1_present_task) >= 3 and d01["pos"] >= d01["neg"]
                        and d01["pos"] > 0) else
        ("INCONCLUSIVE" if len(o1_present_task) > 0 else "NOT SUPPORTED"))
    hyp["H_B CONDITIONING"] = (
        "SUPPORTED" if len(o2_where_o1_not) >= 3 else
        ("INCONCLUSIVE" if len(o2_where_o1_not) > 0 else "NOT SUPPORTED"))
    hyp["H_C FIXED SEQUENCE"] = (
        "SUPPORTED" if len(o3_where_o2_not) >= 3 else
        ("INCONCLUSIVE" if len(o3_where_o2_not) > 0 else "NOT SUPPORTED"))
    hyp["H_D REPLANNING"] = (
        "SUPPORTED" if (len(o4_where_o3_not) >= 3 and any(
            e["subgoal_changed"] or e["diverged_from_O3"]
            for e in o4_replan_evidence)) else
        ("INCONCLUSIVE" if len(o4_where_o3_not) > 0 else "NOT SUPPORTED"))
    all_below = all(not present[(s, a, "task")] for s in sids
                    for a in ("O1", "O2", "O3"))
    ox_path = REPO / "analysis/stageO_expert_check.csv"
    ox_ok = False
    if ox_path.exists():      # OX 仅人工决定后运行(§6);默认不存在
        ox_rows = read_csv_skip_comments(ox_path)
        ox_ok = any(r.get("success") == "True" for r in ox_rows)
    if all_below and ox_ok:
        hyp["H_E SKILL DEFICIT"] = "SUPPORTED(仅 OX 成功;§30 限定)"
    elif all_below:
        hyp["H_E SKILL DEFICIT"] = ("INCONCLUSIVE(O1/O2/O3 全 FAIL 但 "
                                    "OX 未运行;§30 需人工决定)")
    else:
        hyp["H_E SKILL DEFICIT"] = ("NOT WRITABLE(O1/O2/O3 存在达标快照;"
                                    "§30 限定条件不满足)")

    # ---- REALIGNMENT_FIRST(§31)-------------------------------------------
    rf_counts = defaultdict(lambda: [0, 0])     # arm → [realign, total_success]
    for r in rows:
        if not valid_row(r) or r["contract_met"] != "True":
            continue
        rf_counts[r["arm"]][1] += 1
        if r["realignment_first"] == "REALIGNMENT_FIRST":
            rf_counts[r["arm"]][0] += 1
    # reference trace 的 REALIGNMENT_FIRST(ref steps 首动作,同 §11 规则)
    ref_rf = [0, 0]
    for sid, rec in refs.items():
        if rec is None:
            continue
        snap = next(s for s in mani if s["snapshot_id"] == sid)
        steps = rt.load_steps(snap["episode_dir"])
        base_eef = [float(c) for c in json.loads(snap["eef0"])]
        dom = L.ref_domain(rec)
        first = dom[0] if dom else None
        if first is None:
            continue
        ftarget = L.fail_target_of(steps, int(snap["t0"]), base_eef)
        ref_rf[1] += 1
        if L.realignment_first(first["action"], first["kwargs"], ftarget,
                               base_eef) == "REALIGNMENT_FIRST":
            ref_rf[0] += 1

    # ---- reentry 早于 task recovery(§31 讨论 input)-----------------------
    early_re = [(s, a) for s in sids for a in ARMS
                if present[(s, a, "reentry")]
                and not present[(s, a, "task")]]

    # ---- 预算账 + infra 率 --------------------------------------------------
    bud = defaultdict(list)
    for r in rows:
        if valid_row(r):
            bud[r["arm"]].append(r)
    n_infra = sum(1 for r in rows if r.get("infra_abort"))

    # ---- O1/O2 best_of_N(§6 checkpoints {1,4,8,16})------------------------
    def best_of(arm: str) -> list[float]:
        accs = []
        for sid in sids:
            fl = flags[(sid, arm, "task")]
            if not fl:
                continue
            accs.append([sum(fl[:n]) / n for n in (1, 4, 8, 16)
                         if n <= len(fl)])
        if not accs:
            return []
        m = max(len(a) for a in accs)
        return [round(sum(a[i] for a in accs if len(a) > i) /
                      sum(1 for a in accs if len(a) > i), 3)
                for i in range(m)]

    # ---- 落盘 ----------------------------------------------------------------
    csv_cols = ["snapshot_id", "ref_available", "first_recovery_source",
                "first_reentry_source", "first_task_recovery_source"]
    for a in ARMS:
        csv_cols += [f"{a}_rate", f"{a}_n", f"{a}_present_task",
                     f"{a}_present_reentry"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols)
        w.writeheader()
        for sid in sids:
            row = {"snapshot_id": sid,
                   "ref_available": refs.get(sid) is not None
                   if sid in refs else "",
                   "first_recovery_source": labels[(sid, "first_recovery_source")],
                   "first_reentry_source": labels[(sid, "first_reentry_source")],
                   "first_task_recovery_source": labels[(sid, "first_task_recovery_source")]}
            for a in ARMS:
                row[f"{a}_rate"] = ("—" if rate[(sid, a)] is None
                                    else round(rate[(sid, a)], 3))
                row[f"{a}_n"] = n_valid[(sid, a)]
                row[f"{a}_present_task"] = present[(sid, a, "task")]
                row[f"{a}_present_reentry"] = present[(sid, a, "reentry")]
            w.writerow(row)

    md = []
    md.append("# Stage O 假设判定与 first-source 分析(§27-§30)\n\n")
    md.append(f"- 生成:{ts}(确定性 analyzer,零 LLM)\n")
    md.append(f"- 快照 {len(sids)} 个 | K_ROLLOUT={K} | "
              f"reference OK={sum(1 for v in refs.values() if v)}\n")
    md.append(f"- rollout 行 {len(rows)}(infra_abort {n_infra} = "
              f"{(n_infra / len(rows) * 100 if rows else 0):.1f}%;"
              f"§12 门 <2%)\n\n")

    md.append("## First-source 分布(spec §28 P(Ox first))\n\n")
    for oc, name in (("task", "TASK_RECOVERY 契约版"),
                     ("reentry", "POLICY_REENTRY 版"),
                     ("union", "RECOVERY 并集版")):
        md.append(f"- **{name}**:" + ", ".join(
            f"{k}={v}" for k, v in sorted(dist[oc].items(),
                                          key=lambda kv: -kv[1])) + "\n")

    md.append("\n## Δ 配对(task 结局,paired by snapshot)\n\n")
    for name, d in deltas.items():
        if d["n"]:
            md.append(f"- {name}: n={d['n']} mean={d['mean']:+.3f} "
                      f"(正 {d['pos']} / 负 {d['neg']})\n")
        else:
            md.append(f"- {name}: 无可配对快照\n")

    md.append("\n## 假设判定(独立,§30)\n\n")
    md.append(f"- H_A POLICY SUPPORT:**{hyp['H_A POLICY SUPPORT']}**"
              f"(O1 达标快照 {len(o1_present_task)} 个:"
              f"{o1_present_task or '无'};Δ01 正/负 = "
              f"{d01['pos']}/{d01['neg']})\n")
    md.append(f"- H_B CONDITIONING:**{hyp['H_B CONDITIONING']}**"
              f"(O1 未达标而 O2 达标:{len(o2_where_o1_not)} 个:"
              f"{o2_where_o1_not or '无'})\n")
    md.append(f"- H_C FIXED SEQUENCE:**{hyp['H_C FIXED SEQUENCE']}**"
              f"(O2 未达标而 O3 达标:{len(o3_where_o2_not)} 个:"
              f"{o3_where_o2_not or '无'})\n")
    md.append(f"- H_D REPLANNING:**{hyp['H_D REPLANNING']}**"
              f"(O3 未达标而 O4 达标:{len(o4_where_o3_not)} 个:"
              f"{o4_where_o3_not or '无'};state-dependent 证据 "
              f"{sum(1 for e in o4_replan_evidence if e['subgoal_changed'] or e['diverged_from_O3'])}"
              f" 条)\n")
    md.append(f"- H_E SKILL DEFICIT:**{hyp['H_E SKILL DEFICIT']}**\n")

    md.append("\n## REALIGNMENT_FIRST(§31;成功 rollout 内)\n\n")
    for a in ARMS:
        r_, t_ = rf_counts[a]
        md.append(f"- {a}: {r_}/{t_}"
                  + (f"({r_ / t_ * 100:.0f}%)" if t_ else "") + "\n")
    md.append(f"- reference traces: {ref_rf[0]}/{ref_rf[1]}\n")

    md.append("\n## Reentry 早于 task recovery(§31 讨论输入)\n\n")
    md.append(f"- reentry 达标而 task 未达标的 (snapshot, arm) 对:"
              f"{len(early_re)} 个:{early_re or '无'}\n")

    md.append("\n## O1/O2 best_of_N(checkpoints 1/4/8/16 均值)\n\n")
    for a in ("O1", "O2"):
        b = best_of(a)
        md.append(f"- {a}: {b or '无样本'}\n")

    md.append("\n## 预算账(§20/§33;均值 [p90])\n\n")
    md.append("| arm | n | prims | pi05 | turns | wall_s |\n|---|---|---|---|---|---|\n")
    for a in ARMS:
        rs = bud[a]
        if not rs:
            md.append(f"| {a} | 0 | — | — | — | — |\n")
            continue

        def col(key, cast=float):
            vs = sorted(cast(r[key]) for r in rs if r[key] not in ("", None))
            if not vs:
                return "—"
            p90 = vs[max(0, int(0.9 * len(vs)) - 1)]
            return f"{sum(vs) / len(vs):.1f} [{p90:.1f}]"

        md.append(f"| {a} | {len(rs)} | {col('n_prims', int)} | "
                  f"{col('n_pi05', int)} | {col('n_turns', int)} | "
                  f"{col('wall_s')} |\n")

    md.append("\n## Wilson 95% CI(每 arm×snapshot task 结局)\n\n")
    for a in ARMS:
        cis = []
        for sid in sids:
            fl = flags[(sid, a, "task")]
            if not fl:
                continue
            lo, hi = wilson(sum(fl), len(fl))
            cis.append(f"{sid}[{lo:.2f},{hi:.2f}]")
        md.append(f"- {a}: " + (" ".join(cis) if cis else "无样本") + "\n")

    OUT_MD.write_text("".join(md), encoding="utf-8")
    print("".join(md))
    print(f"\n已写入 {OUT_CSV} 与 {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
