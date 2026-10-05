#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage Q §7/§8/§10 — Q1 Confirmatory State×Candidate Factorial。

事件源 = analysis/stageQ_split_manifest.csv(freeze 已冻结 DEV/TEST)。
每事件(prereg §7/§8,执行前全部冻结):
  BOOT_LOCK: boot_to_pre(→S_pre)→ 采 A_pre×4 冻结 → run_fail_pick(守卫
             仍 FG)→ S_post → 采 A_post×4 冻结(全部落
             stageQ_candidates.jsonl;断点只复用不补采,半 bank 弃用重采);
  16 cell-exec:PP/PO/OP/OO(候选源|执行态)×K=4,每 cell =
             exec_from_state(restore S_x → frozen chunk → S_j → R_Q=2
             hold-through 续跑,双契约标签)。
resume:已冻结候选 + 16 非 infra cell 行齐 → 跳过事件;否则 fresh boot
重跑全部 16 cell(分析端按 (sid,cell,cand) 去重 last-wins)。

效应(§10,统计单位 = failure event,cell 值 = 4 cand × 2 reps 的率):
  EXECUTION-STATE = mean[(PO−PP)+(OO−OP)]/2;CANDIDATE-SOURCE =
  mean[(OP−PP)+(OO−PO)]/2;INTERACTION = (OO−OP)−(PO−PP)。
门(15pp,TEST,STABLE 主判 ACQUISITION 陪报;bootstrap by snapshot 10k):
  H_QB exec≥15pp 且去任一 event 仍≥15pp;H_QC cand 同式;H_QD int≥15pp
  且去任一 event 仍>0;H_QA PP stable>0 出现率≥70% ∧ |OO−PP|≤10pp;
  TRANSIENT_GAP(ACQ−STABLE)任 cell 均值≥15pp → H_QE 机制性重要。
Q0 gate 已判 RESTORE-SENSITIVE(appendix C)→ 本阶段 restored 拆分结论
一律标 APPROXIMATE/INCONCLUSIVE,decision 中显式携带。

A_fail probe(§8):transcript 无 chunk 级动作 → NOT_RECOVERABLE,不执行,
不进 gate(decision 固定陈述)。

产物:analysis/stageQ_candidates.jsonl、stageQ_factorial_rollouts.csv、
stageQ_acquisition_stable.csv、stageQ_factorial_effects.csv、
stageQ1_results.md、stageQ1_decision.md;S_pre/S_post npy 落 logs/stageQ1/。

用法:
  nohup python scripts/stageQ1_factorial.py --workers 2 \
      >> /workspace/yjx/tmp/stageQ1_factorial.log 2>&1 &
  python scripts/stageQ1_factorial.py --analyze-only   # 效应重算+报告重写
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import threading
import time
import traceback
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO / "scripts"))
import stageO_rt as rt
import stageP_rt as prt
import stageQ_rt as qt
import ovpm_exp as ox

MANI = REPO / "analysis/stageQ_split_manifest.csv"
CAND_JL = REPO / "analysis/stageQ_candidates.jsonl"
ROLL_CSV = REPO / "analysis/stageQ_factorial_rollouts.csv"
AS_CSV = REPO / "analysis/stageQ_acquisition_stable.csv"
EFF_CSV = REPO / "analysis/stageQ_factorial_effects.csv"
RES_MD = REPO / "analysis/stageQ1_results.md"
DEC_MD = REPO / "analysis/stageQ1_decision.md"
LOG_ROOT = REPO / "logs/stageQ1"

K = 4                    # §7:每源候选数(冻结)
MAX_INFRA_RETRY = 3
GATE = 0.15              # §10:15pp
GATE_QA_DIFF = 0.10      # §10:H_QA |OO−PP|≤10pp
GATE_QA_RATE = 0.70      # §10:PP stable>0 出现率≥70%
GATE_TRANSIENT = 0.15    # §10:TRANSIENT_GAP ≥15pp
N_BOOT = 10000           # §10:bootstrap by snapshot

# 四 cell 定义:cell 名 → (候选源, 执行态)
CELLS = {"PP": ("pre", "pre"), "PO": ("pre", "post"),
         "OP": ("post", "pre"), "OO": ("post", "post")}
CELL_ORDER = ("PP", "PO", "OP", "OO")

WLOCK = threading.Lock()
BOOT_LOCK = threading.Lock()   # dev-Q1:boot 相串行(全局 get_output_dir 竞态)

ROLL_COLS = ["snapshot_id", "task", "seed", "t0", "split", "cell",
             "cand_idx", "cand_sha", "n_rep", "acq_reps", "stable_reps",
             "ee_class", "contact_class", "obj_class", "terminated_in_chunk",
             "final_check_success", "pick_chunks_used", "wall_s",
             "infra_abort", "note"]


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def append_csv(path: Path, cols: list[str], row: dict):
    with WLOCK:
        new = not path.exists()
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)


def load_bank(sid: str) -> dict:
    """已冻结候选 bank(断点复用;source → [rows],按冻结序)。"""
    bank: dict[str, list] = {}
    if CAND_JL.exists():
        for line in CAND_JL.read_text().splitlines():
            r = json.loads(line)
            if r["snapshot_id"] == sid:
                bank.setdefault(r["source"], []).append(r)
    return bank


def done_cells(sid: str) -> int:
    """该事件已完成的非 infra cell-exec 数(resume 判据:16 齐)。"""
    if not ROLL_CSV.exists():
        return 0
    return sum(1 for r in csv.DictReader(open(ROLL_CSV))
               if r["snapshot_id"] == sid and not r.get("infra_abort"))


def process_event(snap: dict, gpu: int, shared_kwargs: dict,
                  smoke: bool = False):
    sid = snap["snapshot_id"]
    tag = f"{sid}_t{snap['task']}s{snap['seed']}"
    bank = load_bank(sid)
    have_all = (len(bank.get("pre", [])) == K
                and len(bank.get("post", [])) == K)
    t_start = time.time()
    ctx = None
    for attempt in range(1, MAX_INFRA_RETRY + 1):
        try:
            with BOOT_LOCK:
                outdir = LOG_ROOT / (
                    f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
                ctx = qt.boot_to_pre(snap, gpu, shared_kwargs, outdir)
                prompt = prt.pre_prompt_of(snap)
                target = ctx["target"]
                # §7:执行前全部冻结。半 bank 无法配对 → 弃用重采。
                if bank and not have_all:
                    raise rt.InfraError(
                        f"{sid}: 半冻结 bank(pre={len(bank.get('pre', []))} "
                        f"post={len(bank.get('post', []))})—弃用重采")
                if not have_all:
                    for k in range(K):            # live S_pre obs
                        cand = prt.sample_candidate(ctx["prims"], prompt)
                        with WLOCK:
                            CAND_JL.open("a").write(json.dumps({
                                "snapshot_id": sid, "source": "pre",
                                "cand_idx": k + 1,
                                "cand_sha": prt.chunk_sha(cand),
                                "prompt": prompt,
                                "actions": [[float(v) for v in row]
                                            for row in cand]}) + "\n")
                    S_post = qt.run_fail_pick(ctx, snap)   # 守卫仍 FG
                    for k in range(K):                     # live S_post obs
                        cand = prt.sample_candidate(ctx["prims"], prompt)
                        with WLOCK:
                            CAND_JL.open("a").write(json.dumps({
                                "snapshot_id": sid, "source": "post",
                                "cand_idx": k + 1,
                                "cand_sha": prt.chunk_sha(cand),
                                "prompt": prompt,
                                "actions": [[float(v) for v in row]
                                            for row in cand]}) + "\n")
                    bank = load_bank(sid)
                    have_all = True
                else:
                    # 复用冻结 bank:fresh boot 重跑到 S_post(执行态两块)
                    S_post = qt.run_fail_pick(ctx, snap)
                states_dir = LOG_ROOT / "states"
                states_dir.mkdir(parents=True, exist_ok=True)
                np.save(states_dir / f"{sid}_pre.npy",
                        np.asarray(ctx["S"]))
                np.save(states_dir / f"{sid}_post.npy", np.asarray(S_post))
            break
        except Exception as exc:
            if ctx:
                qt.stop_ctx(ctx)
                ctx = None
            log(f"  {tag} boot INFRA({attempt}/{MAX_INFRA_RETRY}): "
                f"{type(exc).__name__}: {str(exc)[:120]}")
    if ctx is None:
        if not smoke:
            append_csv(ROLL_CSV, ROLL_COLS,
                       {"snapshot_id": sid, "task": snap["task"],
                        "seed": snap["seed"], "t0": snap["t0"],
                        "infra_abort": "boot_3attempts"})
        return

    # ---- 16 cell-exec(BOOT_LOCK 外;exec 相不落 states.json 可并行)----
    try:
        k_max = 1 if smoke else K      # smoke:每 cell 只第 1 个候选
        actions = {src: [np.asarray(c["actions"], dtype=np.float32)
                         for c in bank[src][:k_max]]
                   for src in ("pre", "post")}
        shas = {src: [c["cand_sha"] for c in bank[src][:k_max]]
                for src in ("pre", "post")}
        states = {"pre": ctx["S"], "post": S_post}
        for cell, (src, estate) in CELLS.items():
            for k in range(k_max):
                t1 = time.time()
                try:
                    cps: list[dict] = []
                    res = qt.exec_from_state(
                        ctx, states[estate], target, prompt,
                        actions[src][k], cps, f"{sid} {cell} cand{k+1}")
                    row = {"snapshot_id": sid, "task": snap["task"],
                           "seed": snap["seed"], "t0": snap["t0"],
                           "split": snap["split"], "cell": cell,
                           "cand_idx": k + 1, "cand_sha": shas[src][k],
                           "n_rep": len(res["reps"]),
                           "acq_reps": ";".join(str(int(r["acquisition"]))
                                                for r in res["reps"]),
                           "stable_reps": ";".join(str(int(r["stable"]))
                                                   for r in res["reps"]),
                           "ee_class": res["chunk_class"]["ee_class"],
                           "contact_class":
                               res["chunk_class"]["contact_class"],
                           "obj_class": res["chunk_class"]["obj_class"],
                           "terminated_in_chunk":
                               int(res["terminated_in_chunk"]),
                           "final_check_success": int(any(
                               r.get("pick", {}).get("libero_terminated")
                               for r in res["reps"])),
                           "pick_chunks_used": ";".join(
                               str(r.get("pick", {}).get("chunks_used", ""))
                               for r in res["reps"]),
                           "wall_s": round(time.time() - t1, 1), "note": ""}
                except Exception as exc:
                    log(f"  {tag} {cell}#{k+1} CELL INFRA: "
                        f"{type(exc).__name__}: {str(exc)[:120]}")
                    row = {"snapshot_id": sid, "task": snap["task"],
                           "seed": snap["seed"], "t0": snap["t0"],
                           "split": snap["split"], "cell": cell,
                           "cand_idx": k + 1,
                           "infra_abort": f"cell_{type(exc).__name__}",
                           "note": str(exc)[:200]}
                if not smoke:
                    append_csv(ROLL_CSV, ROLL_COLS, row)
                else:
                    log(f"  SMOKE {cell}#{k+1} "
                        f"acq={row.get('acq_reps')} "
                        f"stable={row.get('stable_reps')}")
        if not smoke:
            log(f"== {tag} {snap['split']} 完成:{done_cells(sid)}/16 cell "
                f"wall={round(time.time()-t_start)}s")
    finally:
        qt.stop_ctx(ctx)


# ---- 分析(§10)---------------------------------------------------------------
def read_rollouts() -> list[dict]:
    """非 infra 行按 (sid, cell, cand_idx) 去重取最后一行。"""
    by_key: dict[tuple, dict] = {}
    if not ROLL_CSV.exists():
        return []
    for r in csv.DictReader(open(ROLL_CSV)):
        if not r.get("infra_abort"):
            by_key[(r["snapshot_id"], r["cell"], int(r["cand_idx"]))] = r
    return list(by_key.values())


def event_cell_table(split: str | None = None):
    """→ ({sid: {cell: {acq,stable,n}}}, {sid: meta})。"""
    acc: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    for r in read_rollouts():
        if split and r["split"] != split:
            continue
        sid = r["snapshot_id"]
        meta.setdefault(sid, {"task": r["task"], "seed": r["seed"],
                              "t0": r["t0"], "split": r["split"]})
        vals = acc.setdefault(sid, {}).setdefault(
            r["cell"], {"acq": [], "stable": []})
        vals["acq"].extend(1 if v == "1" else 0
                           for v in r["acq_reps"].split(";") if v != "")
        vals["stable"].extend(1 if v == "1" else 0
                              for v in r["stable_reps"].split(";")
                              if v != "")
    out = {sid: {c: {"acq": float(np.mean(v["acq"])),
                     "stable": float(np.mean(v["stable"])),
                     "n": len(v["acq"])}
                 for c, v in cell.items()}
           for sid, cell in acc.items()}
    return out, meta


def event_effects(t: dict) -> dict:
    """单事件 cell 率与三效应(PO−PP 与 OO−OP 各半 / OP−PP 与 OO−PO 各半)。"""
    g = lambda c, k: t[c][k] if c in t else float("nan")
    return {
        **{f"{c.lower()}_{k}": g(c, k) for c in CELL_ORDER
           for k in ("acq", "stable")},
        "exec_acq": (g("PO", "acq") - g("PP", "acq")
                     + g("OO", "acq") - g("OP", "acq")) / 2,
        "exec_stable": (g("PO", "stable") - g("PP", "stable")
                        + g("OO", "stable") - g("OP", "stable")) / 2,
        "cand_acq": (g("OP", "acq") - g("PP", "acq")
                     + g("OO", "acq") - g("PO", "acq")) / 2,
        "cand_stable": (g("OP", "stable") - g("PP", "stable")
                        + g("OO", "stable") - g("PO", "stable")) / 2,
        "int_acq": (g("OO", "acq") - g("OP", "acq"))
                   - (g("PO", "acq") - g("PP", "acq")),
        "int_stable": (g("OO", "stable") - g("OP", "stable"))
                      - (g("PO", "stable") - g("PP", "stable")),
    }


def pooled(vals) -> float:
    v = [x for x in vals if not np.isnan(x)]
    return float(np.mean(v)) if v else float("nan")


def boot_ci(vals, seed: int = 20261005) -> tuple[float, float]:
    v = np.asarray([x for x in vals if not np.isnan(x)], dtype=float)
    if len(v) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(N_BOOT, len(v)))
    means = v[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def loo_min(vals) -> float:
    """去任一 event 后的最小均值(非单事件驱动判据)。"""
    v = [x for x in vals if not np.isnan(x)]
    if len(v) < 2:
        return float("nan")
    return float(min(np.mean(v[:i] + v[i+1:]) for i in range(len(v))))


def analyze() -> dict:
    tables, meta = {}, {}
    for split in ("ALL", "DEV", "TEST"):
        tables[split], meta = event_cell_table(
            None if split == "ALL" else split)
    eff = {s: {sid: event_effects(t)
               for sid, t in tables[s].items() if len(t) == 4}
           for s in ("DEV", "TEST")}
    agg = {}
    for split in ("DEV", "TEST"):
        a = {}
        for k in ("exec_acq", "exec_stable", "cand_acq", "cand_stable",
                  "int_acq", "int_stable",
                  *[f"{c.lower()}_{m}" for c in CELL_ORDER
                    for m in ("acq", "stable")]):
            vals = [v[k] for v in eff[split].values()]
            a[k] = pooled(vals)
            if k.split("_")[0] in ("exec", "cand", "int"):
                a[k + "_ci"] = boot_ci(vals)
                a[k + "_loo"] = loo_min(vals)
        a["pp_stable_pos_rate"] = (
            sum(1 for v in eff[split].values() if v["pp_stable"] > 0)
            / len(eff[split]) if eff[split] else float("nan"))
        a["qa_absdiff_stable"] = abs(a["oo_stable"] - a["pp_stable"])
        agg[split] = a
    transient = {s: {c: pooled([t[c]["acq"] - t[c]["stable"]
                                for t in tables[s].values() if len(t) == 4])
                     for c in CELL_ORDER} for s in ("DEV", "TEST")}
    # gates(§10;STABLE 主判,ACQUISITION 陪报)
    gates = {}
    for metric in ("stable", "acq"):
        for name, key in (("H_QB_exec", "exec"), ("H_QC_cand", "cand"),
                          ("H_QD_int", "int")):
            v, loo = agg["TEST"][f"{key}_{metric}"], \
                agg["TEST"][f"{key}_{metric}_loo"]
            gates[f"{name}_{metric}"] = {
                "value": v, "loo": loo,
                "pass": (v >= GATE and loo >= GATE if name != "H_QD_int"
                         else v >= GATE and loo > 0)}
    gates["H_QA"] = {"pp_pos_rate": agg["TEST"]["pp_stable_pos_rate"],
                     "absdiff_oo_pp": agg["TEST"]["qa_absdiff_stable"],
                     "pass": (agg["TEST"]["pp_stable_pos_rate"]
                              >= GATE_QA_RATE
                              and agg["TEST"]["qa_absdiff_stable"]
                              <= GATE_QA_DIFF)}
    gates["TRANSIENT"] = {**transient["TEST"],
                          "any_ge_gate": any(
                              (not np.isnan(v)) and v >= GATE_TRANSIENT
                              for v in transient["TEST"].values())}
    return {"tables": tables, "meta": meta, "eff": eff, "agg": agg,
            "transient": transient, "gates": gates}


def fmt_ci(ci) -> str:
    if ci is None or np.isnan(ci[0]):
        return "—"
    return f"[{ci[0]:+.3f},{ci[1]:+.3f}]"


def write_reports(a: dict):
    meta = a["meta"]
    # ---- stageQ_acquisition_stable.csv ----
    with open(AS_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["snapshot_id", "task", "seed", "t0", "split"]
                   + [f"{c}_{k}" for c in CELL_ORDER
                      for k in ("acq", "stable", "gap")])
        for split in ("DEV", "TEST"):
            for sid in sorted(a["tables"][split]):
                t = a["tables"][split][sid]
                m = meta.get(sid, {})
                row = [sid, m.get("task"), m.get("seed"), m.get("t0"), split]
                for c in CELL_ORDER:
                    v = t.get(c, {"acq": float("nan"),
                                  "stable": float("nan")})
                    row += [round(v["acq"], 3), round(v["stable"], 3),
                            round(v["acq"] - v["stable"], 3)]
                w.writerow(row)
    # ---- stageQ_factorial_effects.csv ----
    eff_keys = tuple(event_effects({}).keys())
    with open(EFF_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["snapshot_id", "split"] + list(eff_keys))
        for split in ("DEV", "TEST"):
            for sid in sorted(a["eff"][split]):
                e = a["eff"][split][sid]
                w.writerow([sid, split] +
                           [round(e[k], 3) if not np.isnan(e[k]) else ""
                            for k in eff_keys])
            g = a["agg"][split]
            w.writerow([f"POOLED({split})", ""] +
                       [round(g.get(k, float("nan")), 3)
                        if not np.isnan(g.get(k, float("nan"))) else ""
                        for k in eff_keys])
    # ---- stageQ1_results.md ----
    g = a["agg"]["TEST"]
    L = [
        "# Stage Q1 — State×Candidate Factorial 结果",
        "",
        f"生成:{datetime.datetime.now().isoformat()} | prereg §7/§8/§10 | "
        f"K={K} R_Q={qt.R_Q} HOLD_MIN_POINTS={qt.HOLD_MIN_POINTS}",
        "",
        f"事件(完整四 cell):DEV {len(a['eff']['DEV'])}/"
        f"TEST {len(a['eff']['TEST'])};A_fail probe = NOT_RECOVERABLE"
        "(transcript 无 chunk 级动作,不执行不进 gate)。",
        "",
        "## 四 cell 恢复率(TEST pooled,事件等权)", "",
        "| cell | ACQUISITION | STABLE | ACQ−STABLE |",
        "|---|---|---|---|",
    ]
    for c in CELL_ORDER:
        L.append(f"| {c} | {g[c.lower()+'_acq']:.3f} | "
                 f"{g[c.lower()+'_stable']:.3f} | "
                 f"{g[c.lower()+'_acq']-g[c.lower()+'_stable']:+.3f} |")
    L += ["", "## 效应(TEST pooled;bootstrap by snapshot 10k)", "",
          "| 效应 | ACQUISITION (LOO) CI | STABLE (LOO) CI | 门 |",
          "|---|---|---|---|"]
    for name, key in (("EXECUTION-STATE(H_QB)", "exec"),
                      ("CANDIDATE-SOURCE(H_QC)", "cand"),
                      ("INTERACTION(H_QD)", "int")):
        L.append(
            f"| {name} | {g[key+'_acq']:+.3f} "
            f"({g[key+'_acq_loo']:+.3f}) {fmt_ci(g[key+'_acq_ci'])} "
            f"| {g[key+'_stable']:+.3f} ({g[key+'_stable_loo']:+.3f}) "
            f"{fmt_ci(g[key+'_stable_ci'])} | ≥{GATE:.2f},LOO 同"
            f"(H_QD LOO>0) |")
    L += ["", "## H_QA / TRANSIENT(TEST)", "",
          f"- PP stable>0 事件率 = {g['pp_stable_pos_rate']:.3f}"
          f"(门 ≥{GATE_QA_RATE:.2f});",
          f"- |OO_STABLE − PP_STABLE| = {g['qa_absdiff_stable']:.3f}"
          f"(门 ≤{GATE_QA_DIFF:.2f});",
          "- TRANSIENT_GAP(ACQ−STABLE):" + ", ".join(
              f"{c}={v:+.3f}" for c, v in a["transient"]["TEST"].items())
          + f"(任一 ≥{GATE_TRANSIENT:.2f} → H_QE 机制性重要)。",
          "", "## DEV sanity(陪报)", ""]
    gd = a["agg"]["DEV"]
    L.append(f"- exec_stable {gd['exec_stable']:+.3f}, "
             f"cand_stable {gd['cand_stable']:+.3f}, "
             f"int_stable {gd['int_stable']:+.3f};PP stable 率 "
             f"{gd['pp_stable']:.3f}。")
    RES_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- stageQ1_decision.md ----
    gt = a["gates"]
    qb, qc = gt["H_QB_exec_stable"], gt["H_QC_cand_stable"]
    qd, qa = gt["H_QD_int_stable"], gt["H_QA"]
    D = [
        "# Stage Q1 Decision — State×Candidate Factorial",
        "",
        f"生成:{datetime.datetime.now().isoformat()} | 门 = {GATE:.2f}"
        "(15pp) | 判据:STABLE 主、ACQUISITION 陪报;统计单位 = event",
        "",
        "| 假设 | 检验 | 值 | LOO | 判定 |",
        "|---|---|---|---|---|",
        (f"| H_QB 物理预置 | exec-state effect(STABLE) | {qb['value']:+.3f}"
         f" | {qb['loo']:+.3f} | "
         f"{'SUPPORTED' if qb['pass'] else 'NOT SUPPORTED'} |"),
        (f"| H_QC 动作后置 | cand-source effect(STABLE) | {qc['value']:+.3f}"
         f" | {qc['loo']:+.3f} | "
         f"{'SUPPORTED' if qc['pass'] else 'NOT SUPPORTED'} |"),
        (f"| H_QD 交互 | interaction(STABLE) | {qd['value']:+.3f} | "
         f"{qd['loo']:+.3f} | "
         f"{'SUPPORTED' if qd['pass'] else 'NOT SUPPORTED'} |"),
        (f"| H_QA 随机重采样 | PP stable 出现率 {qa['pp_pos_rate']:.3f}"
         f"(≥{GATE_QA_RATE:.2f}) ∧ |OO−PP|={qa['absdiff_oo_pp']:.3f}"
         f"(≤{GATE_QA_DIFF:.2f}) | | | "
         f"{'SUPPORTED' if qa['pass'] else 'NOT SUPPORTED'} |"),
        "",
        "TRANSIENT_GAP(TEST):" + ", ".join(
            f"{c}={v:+.3f}" for c, v in a["transient"]["TEST"].items())
        + f";任一 ≥{GATE_TRANSIENT:.2f} → H_QE 机制性重要(本次 "
        f"{'是' if gt['TRANSIENT']['any_ge_gate'] else '否'})。",
        "",
        "**措辞约束(Q0 gate,prereg §5)**:restore-sensitivity 已判 "
        "RESTORE-SENSITIVE DYNAMICS(transition-class 一致率 0.769<0.90)"
        " → 本文件所有 restored-state 因果拆分结论标 **APPROXIMATE**,禁称"
        "精确 physics counterfactual;不可解释部分按 §12 记 UNOBSERVED/"
        "CONTACT-HISTORY DYNAMICS MAY CONTRIBUTE。",
        "",
        (f"Q2 触发条件:exec-state(STABLE)≥{GATE:.2f} 或 H_QB SUPPORTED → "
         f"本次值 {qb['value']:+.3f}、gate "
         f"{'过' if qb['pass'] else '未过'} → **"
         f"{'触发' if (qb['value'] >= GATE or qb['pass']) else '不触发'}**"
         "(prereg §11)。"),
        "",
    ]
    DEC_MD.write_text("\n".join(D) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--smoke", action="store_true",
                    help="单事件 1 cand/cell 全流程(只打印,不写 CSV)")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    rt.apply_env_overrides()
    if args.analyze_only:
        write_reports(analyze())
        log("analyze-only 完成")
        return 0

    ox.pg.preflight(label="stageQ1_factorial",
                    lock_name="stageQ1_factorial.lock")
    events = qt.read_manifest(MANI)
    log(f"manifest {len(events)} 事件;workers={args.workers} "
        f"smoke={args.smoke}")

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources
    ensure_resources("libero")
    shared_root = LOG_ROOT / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)
    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None)
    log("boot shared vla+sam3 ...")
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())

    from collections import deque
    if args.smoke:
        pending = deque([events[0]])
    else:
        pending = deque(e for e in events
                        if done_cells(e["snapshot_id"]) < 16)
        log(f"resume:{len(events)-len(pending)} 已完成,"
            f"{len(pending)} 待跑")
    plock = threading.Lock()

    def worker():
        while True:
            with plock:
                if not pending:
                    return
                s = pending.popleft()
            sid = s["snapshot_id"]
            try:
                log(f"== {sid} t{s['task']}s{s['seed']} t0={s['t0']} "
                    f"{s['split']}")
                process_event(s, args.gpu, shared_kwargs, args.smoke)
            except Exception as exc:
                log(f"{sid} EXC {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()[-600:]}")

    try:
        threads = [threading.Thread(target=worker, daemon=True)
                   for _ in range(max(1, args.workers))]
        for t in threads:
            t.start()
            time.sleep(ox.STAGGER_S)
        for t in threads:
            t.join()
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass

    write_reports(analyze())
    log("Q1 factorial 完成,报告已写")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
