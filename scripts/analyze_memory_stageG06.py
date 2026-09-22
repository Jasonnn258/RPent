#!/usr/bin/env python3
"""Stage G0.6 扩样确认分析器(三臂 60 格,预注册)。

预注册:analysis/stageG06_preregistration.md(commit fb6b51c,先于任何
episode)。臂定义(§2/§5-6):

  P0 g05P0  injection none        (fires 只记日志,零注入)
  P2 g05P2  generic_refresh (F3)  (无检索)
  P4 g0D    full = G0-D           (common query,reason+cards;从不重定义)

网格:libero_spatial_task x {t3,t5,t9} x s1-s20 x r1 = 60 cells/臂;
s1-s10 = G0.5 原行原判,s11-s20 = G0.6 新集。

恰三个主对比(§1):RQ1 P2-P0、RQ2 P4-P0、RQ3 P4-P2。统计实现逐字
复用 G0.5 冻结版(McNemar exact、paired bootstrap 10k seed 20260920、
macro task-cluster CI)。recovery/机制指标 = G0.5 冻结定义原样复用
(c2.label_stream;P0 的 fires 是 null 参照,不参与 recovery 分母)。

判定树 = 预注册 §7 的 CASE A-F,机械套用;边界值(恰好 .08)计入
满足该侧。§8 的 recovery 四问单独输出。成本(§6):若 P2≈P4 on SR
(|diff|<.08)自动计算 token/latency 缩减比。

用法: python scripts/analyze_memory_stageG06.py
产物: analysis/stageG06_runs.csv + stageG06_events.jsonl
      + stageG06_results.json + stageG06_results.md
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import analyze_memory_stageB as sb  # noqa: E402
import memory_stagec2_benchmark as c2  # noqa: E402
import analyze_memory_stageG0 as g0  # noqa: E402
from analyze_memory_stageG import (  # noqa: E402
    ep_events, ep_turns, macro_boot, mcnemar_exact, paired_boot,
)

TIER = "glm-5.3-flash"
SUITE = "libero_spatial_task"
TASKS = (3, 5, 9)
SEEDS = range(1, 21)          # 60 matched cells/arm(§2)
INFRA = ("infra_crash", "infra_timeout", "infra_missing")
TH = 0.08                      # §4 实践阈值 8pp

G06_ARMS = {
    "P0": ("g05", "g05P0"),
    "P2": ("g05", "g05P2"),
    "P4": ("g0", "g0D"),      # Full 从不重定义(§5)
}
CONTRASTS = [("P2", "P0"), ("P4", "P0"), ("P4", "P2")]  # RQ1/2/3

# 冻结 PHASE_BUCKET 语义(与 G0.5 逐字一致)
BUCKET = {"segment": "PERCEPTION", "back_project": "PERCEPTION",
          "detect": "PERCEPTION", "pi0_pick": "PICK",
          "pi0_doubled": "PICK", "move_to": "MOVE", "move_pose": "MOVE",
          "release": "PLACE"}


def log(msg):
    print(msg, flush=True)


def load_rows():
    rows = {}
    for r in sb.csv_dict():
        if r["tier"] != TIER or int(r["repeat"]) != 1:
            continue
        if r["stage"] not in ("g0", "g05"):
            continue
        if r["suite"] != SUITE or int(r["task"]) not in TASKS:
            continue
        if int(r["seed"]) not in SEEDS:
            continue
        k = (r["stage"], r["cond"], r["suite"], int(r["task"]),
             int(r["seed"]))
        rows[k] = r   # 同格多行时后行覆盖(infra 行 -> resume 后的有效行)
    return rows


def arm_rows(rows, arm):
    stage, cond = G06_ARMS[arm]
    out, infra = {}, collections.Counter()
    for (st, c, su, t, s), r in rows.items():
        if st != stage or c != cond:
            continue
        if r["result"] in INFRA:
            infra[(t, s)] = r["result"]
            continue
        out[(t, s)] = r
    return out, infra


# ------------------------------------------------------------------ 冻结机制指标
def recovery_stats(rows, lcache):
    """G0.5 冻结定义原样;新增 prim_to_recovery = 窗口内首个 PROGRESSING
    距干预的 primitive 数(只对已恢复的干预统计;纯派生,不改定义)。"""
    n_int = rec3 = ph3 = 0
    rep_fails, turns_after, p2r = [], [], []
    per_ep_rec = []
    for k, r in sorted(rows.items()):
        ep = Path(r["dir"]).name
        if ep not in lcache:
            try:
                ctx = c2.EpisodeCtx(ep)
                lcache[ep] = [x for x in c2.label_stream(ctx)
                              if x[1] is not None]
            except Exception as exc:  # noqa: BLE001 - 报告绝不崩
                log(f"  label_stream failed for {ep}: {exc}")
                lcache[ep] = []
        ls = lcache[ep]
        t_end = ep_turns(r)
        fires = ep_events(r)
        interventions = [e for e in fires if "retrieval_tokens" in e]
        ep_rec = False
        for e in interventions:
            T = e["turn"]
            n_int += 1
            win = [x for x in ls if T <= x[1] <= T + 3]
            prog_pos = [i for i, x in enumerate(win)
                        if x[4] == "PROGRESSING"]
            ok = bool(prog_pos)
            rec3 += ok
            ep_rec |= ok
            if ok:
                p2r.append(prog_pos[0] + 1)
            buckets = {BUCKET.get(x[2]) for x in win} - {None}
            ph3 += len(buckets) > 1
            rep_fails.append(sum(1 for x in win if x[4] == "STALLED"))
            turns_after.append(max(0, t_end - T))
        per_ep_rec.append((interventions != [], ep_rec))
    n = len(rows)
    return {
        "episodes": n,
        "interventions": n_int,
        "int_per_ep": round(n_int / n, 2) if n else None,
        "recovery@3": round(rec3 / n_int, 3) if n_int else None,
        "ep_with_recovery@3": round(
            sum(1 for has, rec in per_ep_rec if has and rec)
            / max(1, sum(1 for has, _ in per_ep_rec if has)), 3),
        "prim_to_recovery_mean": round(sum(p2r) / len(p2r), 2) if p2r
        else None,
        "phase_change@3": round(ph3 / n_int, 3) if n_int else None,
        "stalled_prims@3_mean": round(sum(rep_fails) / len(rep_fails), 2)
        if rep_fails else None,
        "turns_after_mean": round(sum(turns_after) / len(turns_after), 1)
        if turns_after else None,
    }


def token_stats(rows):
    fires = injected = 0
    toks, walls = [], []
    for k, r in sorted(rows.items()):
        evs = ep_events(r)
        fires += len(evs)
        for e in evs:
            if "retrieval_tokens" in e:
                injected += 1
                toks.append(e["retrieval_tokens"])
        walls.append(float(r["wall_s"] or 0))
    n = len(rows)
    return {
        "fires": fires,
        "fires_per_ep": round(fires / n, 2) if n else None,
        "injections_per_ep": round(injected / n, 2) if n else None,
        "injected_tokens_per_ep": round(sum(toks) / n, 1) if n else None,
        "mean_block_tokens": round(sum(toks) / len(toks), 1) if toks
        else None,
        "wall_mean_s": round(sum(walls) / len(walls), 1) if walls else None,
    }


# ------------------------------------------------------------------ 统计(冻结实现)
def paired_sr(ra, rb):
    common = sorted(set(ra) & set(rb))
    va = {k: ra[k]["result"] == "success" for k in common}
    vb = {k: rb[k]["result"] == "success" for k in common}
    b = sum(1 for k in common if vb[k] and not va[k])
    c = sum(1 for k in common if va[k] and not vb[k])
    diff = (sum(vb.values()) - sum(va.values())) / len(common) if common \
        else None
    by_task = collections.defaultdict(list)
    for k in common:
        by_task[k[0]].append(float(vb[k]) - float(va[k]))
    return {
        "n_pairs": len(common),
        "flips_a_only_success": c, "flips_b_only_success": b,
        "net_wins_b_minus_a": b - c,
        "ties": len(common) - b - c,
        "diff_micro": round(diff, 3) if diff is not None else None,
        "mcnemar_p": round(mcnemar_exact(b, c), 5)
        if mcnemar_exact(b, c) is not None else None,
        "ci95_micro": [round(x, 3) for x in paired_boot(common, va, vb)]
        if common else None,
        "ci95_macro_cluster": [round(x, 3) for x in macro_boot(by_task)]
        if by_task else None,
        "nonneg_tasks": sum(1 for v in by_task.values()
                            if sum(v) >= 0) if by_task else None,
        "by_task_diff": {f"t{t}": round(sum(v) / len(v), 3)
                         for t, v in sorted(by_task.items())},
    }


# ------------------------------------------------------------------ §13 CASE 判定
def case_ruling(arms_sr, contrasts, rec):
    """机械套用预注册 §7;diffs 以小数记(.08 = 8pp)。
    返回 (case, reasons dict)。边界值恰 = .08 计入满足该侧。"""
    d = {k: contrasts[k]["diff_micro"] for k in contrasts}
    nn = {k: contrasts[k]["nonneg_tasks"] for k in contrasts}
    r: dict[str, object] = {"diffs": d, "nonneg_tasks": nn}

    def g(k):
        return d[k] if d[k] is not None else 0.0

    p2p0, p4p0, p4p2 = g("P2->P0"), g("P4->P0"), g("P4->P2")
    # CASE A:P2−P0 ≥8pp ∧ P4−P2 <8pp ∧ P2/P4 各自 ≥2/3 任务非负
    r["A"] = (p2p0 >= TH and p4p2 < TH
              and (nn.get("P2->P0") or 0) >= 2
              and (nn.get("P4->P0") or 0) >= 2)
    # CASE B:P4−P2 ≥8pp ∧ P4−P0 >0 ∧ recovery 不明显反向
    rcp = rec.get("P4", {}).get("recovery@3")
    rcc = rec.get("P2", {}).get("recovery@3")
    rec_ok = (rcp is None or rcc is None or rcp >= rcc - 0.05)
    r["B"] = (p4p2 >= TH and p4p0 > 0 and rec_ok)
    # CASE C:P2≈P4 on SR(|diff|<8pp)但 P4 rec@3 明显更高且延迟更低
    rec_gap = (rcp is not None and rcc is not None and rcp - rcc >= 0.05)
    lat_p4 = rec.get("P4", {}).get("prim_to_recovery_mean")
    lat_p2 = rec.get("P2", {}).get("prim_to_recovery_mean")
    lat_ok = (lat_p4 is not None and lat_p2 is not None and lat_p4 <= lat_p2)
    r["C"] = (abs(p4p2) < TH and rec_gap and lat_ok)
    # CASE D:全部两两 |diff|<8pp 且 paired 无稳定方向
    stable = any(abs(contrasts[k]["net_wins_b_minus_a"]) >= 5
                 for k in contrasts)
    r["D"] = (abs(p2p0) < TH and abs(p4p0) < TH and abs(p4p2) < TH
              and not stable)
    # CASE E:P2−P4 ≥8pp
    r["E"] = (-p4p2 >= TH)
    # CASE F:top 差异在 ±8pp 内但任务方向明显不同
    top = max(abs(p2p0), abs(p4p0), abs(p4p2))
    task_dirs = []
    for k in contrasts:
        bt = contrasts[k]["by_task_diff"]
        signs = {1 if v > 0 else -1 if v < 0 else 0 for v in bt.values()}
        task_dirs.append(len(signs) > 1)
    r["F"] = (top < TH and any(task_dirs))
    for name in ("A", "B", "C", "D", "E", "F"):  # A>B>C>D>E>F
        if r[name]:
            return name, r
    # 无一全条件匹配(树未覆盖的几何,如大幅负向差异)——如实报告
    return "UNMATCHED", r


def recovery_special_check(arm_cells, arms_meta):
    """§14 四问:1) P4 rec@3 是否仍高于 P2;2) 差异来自哪个任务;
    3) rec@3 提升是否转换成 SR;4) 若不转换,是再失败还是近上限。"""
    out = {}
    rc4 = arms_meta.get("P4", {}).get("recovery", {})
    rc2 = arms_meta.get("P2", {}).get("recovery", {})
    out["q1_p4_rec3_higher"] = (
        (rc4.get("recovery@3") or 0) > (rc2.get("recovery@3") or 0))
    # per-task recovery@3(P4 vs P2),由 episodes_detail 聚合
    def task_rec(arm):
        agg = collections.defaultdict(lambda: [0, 0])
        for d in arms_meta[arm]["episodes_detail"]:
            if d["injections"]:
                # detail 里 recovery_any 是 per-episode 粒度
                agg[d["task"]][0] += d["recovery_any"]
                agg[d["task"]][1] += 1
        return {f"t{t}": round(v[0] / v[1], 3) if v[1] else None
                for t, v in sorted(agg.items())}
    out["q2_rec3_by_task"] = {"P4": task_rec("P4"), "P2": task_rec("P2")}
    # Q3:有恢复的 episode 的最终 SR(P4 vs P2)
    def rec_success(arm):
        det = arms_meta[arm]["episodes_detail"]
        rec = [d for d in det if d["injections"] and d["recovery_any"]]
        return (round(sum(d["success"] for d in rec) / len(rec), 3)
                if rec else None)
    out["q3_sr_given_recovery"] = {"P4": rec_success("P4"),
                                   "P2": rec_success("P2")}
    # Q4:恢复了但没成功的 episode 分布(按任务)
    def rec_nosucc(arm):
        det = arms_meta[arm]["episodes_detail"]
        agg = collections.Counter(d["task"] for d in det
                                  if d["injections"] and d["recovery_any"]
                                  and not d["success"])
        return {f"t{t}": n for t, n in sorted(agg.items())}
    out["q4_recovered_but_failed"] = {"P4": rec_nosucc("P4"),
                                      "P2": rec_nosucc("P2")}
    return out


def cost_reduction(arms_meta, contrasts):
    """§6:若 P2≈P4 on SR(|diff|<8pp),报 token/latency 缩减比。"""
    d = contrasts.get("P4->P2", {}).get("diff_micro")
    if d is None or abs(d) >= TH:
        return {"applicable": False,
                "reason": f"|P4-P2| = {d} >= 8pp 或缺失"}
    t2 = arms_meta["P2"]["tokens"]
    t4 = arms_meta["P4"]["tokens"]
    w2 = t2.get("wall_mean_s") or 0
    w4 = t4.get("wall_mean_s") or 0
    k2 = t2.get("injected_tokens_per_ep") or 0
    k4 = t4.get("injected_tokens_per_ep") or 0
    return {
        "applicable": True,
        "token_reduction": round(1 - k2 / k4, 3) if k4 else None,
        "wall_reduction": round(1 - w2 / w4, 3) if w4 else None,
        "P2_tok_per_ep": k2, "P4_tok_per_ep": k4,
        "P2_wall_mean_s": w2, "P4_wall_mean_s": w4,
    }


# ------------------------------------------------------------------ writers
def write_runs_csv(res):
    path = REPO / "analysis" / "stageG06_runs.csv"
    fields = ["arm", "stage", "cond", "task", "seed", "segment",
              "result", "success", "infra", "turns", "wall_s", "fires",
              "injections", "injected_tokens", "recovery_any", "stalled@3"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for arm in G06_ARMS:
            for d in res["arms"][arm]["episodes_detail"]:
                w.writerow(d)
    log(f"wrote {path}")


def write_events_jsonl(res):
    path = REPO / "analysis" / "stageG06_events.jsonl"
    n = 0
    with open(path, "w") as f:
        for arm in G06_ARMS:
            for ev in res["arms"][arm]["events"]:
                ev = dict(ev)
                ev["arm"] = arm
                ev.setdefault("injection_mode", "full")  # P4 历史行
                f.write(json.dumps(ev, ensure_ascii=False, default=str)
                        + "\n")
                n += 1
    log(f"wrote {path} ({n} events)")


# ------------------------------------------------------------------ main
def main():
    rows = load_rows()
    mcache, lcache = {}, {}
    res = {"arms": {}, "contrasts": {}, "infra": {}}
    for arm in G06_ARMS:
        rr, infra = arm_rows(rows, arm)
        stage, cond = G06_ARMS[arm]
        sr = g0.sr_stats(rr)
        tg = g0.trigger_stats(arm, rr, mcache)
        rc = recovery_stats(rr, lcache)
        tk = token_stats(rr)
        detail, evs_out = [], []
        for (t, s), r in sorted(rr.items()):
            evs = ep_events(r)
            interventions = [e for e in evs if "retrieval_tokens" in e]
            ep = Path(r["dir"]).name
            ls = lcache.get(ep, [])
            rec_any = False
            for e in interventions:
                T = e["turn"]
                rec_any |= any(x[4] == "PROGRESSING" for x in ls
                               if T <= x[1] <= T + 3)
            stalled = sum(1 for e in interventions for x in ls
                          if e["turn"] <= x[1] <= e["turn"] + 3
                          and x[4] == "STALLED")
            detail.append({
                "arm": arm, "stage": stage, "cond": cond, "task": t,
                "seed": s, "segment": "s1-10" if s <= 10 else "s11-20",
                "result": r["result"],
                "success": int(r["result"] == "success"),
                "infra": int(r["result"] in INFRA),
                "turns": ep_turns(r), "wall_s": r["wall_s"],
                "fires": len(evs), "injections": len(interventions),
                "injected_tokens": sum(e.get("retrieval_tokens", 0)
                                       for e in interventions),
                "recovery_any": int(rec_any and bool(interventions)),
                "stalled@3": stalled,
            })
            for e in evs:
                evs_out.append(e)
        res["arms"][arm] = {
            "label": G06_ARMS[arm], "n_rows": len(rr),
            "infra": {f"t{t}_s{s}": v for (t, s), v in sorted(
                infra.items())},
            "sr": sr, "trigger": tg, "recovery": rc, "tokens": tk,
            "episodes_detail": detail, "events": evs_out,
        }
        log(f"arm {arm}: n={len(rr)} SR={sr.get('SR_micro')} "
            f"rec@3={rc.get('recovery@3')} "
            f"tok/ep={tk.get('injected_tokens_per_ep')}")

    arm_cells = {a: arm_rows(rows, a)[0] for a in G06_ARMS}
    for a, b in CONTRASTS:  # 报告为 a minus b
        res["contrasts"][f"{a}->{b}"] = paired_sr(arm_cells[b],
                                                  arm_cells[a])
        log(f"contrast {a}->{b}: {res['contrasts'][f'{a}->{b}']}")

    case, reasons = case_ruling(
        {a: res["arms"][a]["sr"] for a in G06_ARMS},
        res["contrasts"],
        {a: res["arms"][a] for a in G06_ARMS})
    res["case"] = case
    res["case_reasons"] = reasons
    log(f"CASE ruling: {case}")

    res["recovery_special_check"] = recovery_special_check(arm_cells,
                                                           res["arms"])
    res["cost_reduction"] = cost_reduction(res["arms"], res["contrasts"])
    # rel@1/@3 仅诊断(§6);P2 无检索故只有 P4
    res["retrieval_quality_P4"] = g0.retrieval_stats(
        "P4", arm_cells["P4"], mcache)

    out = {k: v for k, v in res.items() if k != "arms"}
    out["arms"] = {a: {kk: vv for kk, vv in d.items()
                       if kk not in ("episodes_detail", "events")}
                   for a, d in res["arms"].items()}
    (REPO / "analysis" / "stageG06_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str))

    md = ["# Stage G0.6 — 扩样确认结果(60 cells/arm)\n",
          "_generated by scripts/analyze_memory_stageG06.py;三臂/三对比/"
          "CASE 树 = 预注册 stageG06_preregistration.md(commit fb6b51c,"
          "先于运行)。_\n",
          "## 表 1 — 臂(§18;全部 v1_per_result 触发,common query)",
          "",
          "| 臂 | n | SR | fires/ep | inj/ep | tok/ep | rec@3 | "
          "prim2rec | ph@3 | stalled@3 | turns_after | wall |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm in G06_ARMS:
        d = res["arms"][arm]
        s, tk, rc = d["sr"], d["tokens"], d["recovery"]
        md.append(f"| {arm} {d['label'][1]} | {d['n_rows']} | "
                  f"{s.get('SR_micro')} | {tk.get('fires_per_ep')} | "
                  f"{tk.get('injections_per_ep')} | "
                  f"{tk.get('injected_tokens_per_ep')} | "
                  f"{rc.get('recovery@3')} | "
                  f"{rc.get('prim_to_recovery_mean')} | "
                  f"{rc.get('phase_change@3')} | "
                  f"{rc.get('stalled_prims@3_mean')} | "
                  f"{rc.get('turns_after_mean')} | {tk.get('wall_mean_s')}"
                  f" |")
    md += ["", "SR by task: " + json.dumps(
        {a: res["arms"][a]["sr"].get("SR_by_task") for a in G06_ARMS}),
        "", "SR by segment(诊断:G0.5 原行 vs G0.6 新集): " + json.dumps(
            {a: dict(collections.Counter(
                d["segment"] for d in res["arms"][a]["episodes_detail"]
                if d["success"])) for a in G06_ARMS}),
        "", "## 表 2 — 三个预注册对比(§18)", "",
        "| 对比 | n | ΔSR | wins | losses | ties | McNemar p | "
        "CI95(micro) | CI95(macro) | 非负任务 |",
        "|---|---|---|---|---|---|---|---|---|---|"]
    for a, b in CONTRASTS:
        c = res["contrasts"][f"{a}->{b}"]
        md.append(f"| {a} − {b} | {c['n_pairs']} | {c['diff_micro']} | "
                  f"{c['flips_b_only_success']} | "
                  f"{c['flips_a_only_success']} | {c['ties']} | "
                  f"{c['mcnemar_p']} | {c['ci95_micro']} | "
                  f"{c['ci95_macro_cluster']} | {c['nonneg_tasks']}/3 |")
    md += ["", f"## §7 CASE 判定:**{case}**", "",
           json.dumps(reasons, indent=2, ensure_ascii=False), "",
           "## §14 recovery@3 特别检查", "",
           json.dumps(res["recovery_special_check"], indent=2,
                      ensure_ascii=False), "",
           "## §6 成本对比(P2≈P4 时)", "",
           json.dumps(res["cost_reduction"], indent=2, ensure_ascii=False),
           "", "rel@1/@3(P4,仅诊断): "
           + json.dumps(res["retrieval_quality_P4"]), "",
           "infra(公开计数,已排除): " + json.dumps(
               {a: len(res["arms"][a]["infra"]) for a in G06_ARMS}), ""]
    (REPO / "analysis" / "stageG06_results.md").write_text(
        "\n".join(md), encoding="utf-8")
    write_runs_csv(res)
    write_events_jsonl(res)
    log("wrote analysis/stageG06_results.{json,md}")


if __name__ == "__main__":
    main()
