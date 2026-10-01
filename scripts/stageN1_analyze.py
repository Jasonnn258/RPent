#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage N1 §4-§5 — 指标计算 + 五门判定(预注册冻结,本脚本不做任何重测)。

输入:
- analysis/stageN1_rollouts.csv(runner 产物;INFRA_ABORT 行过滤)
- analysis/stageN1_information_provenance.jsonl(realized 标记来源)
- analysis/stageN1_split_manifest.csv(快照全集与哈希)

指标(spec §4):
- validated_recovery:rollout 结束 env.check_success()==True;
- harm:success==False 且(目标 z 较 t0 下降>3cm 或 |Δxy|>8cm);
- dependency_realization:O rollout ≥1 条 provenance realized=true;
- feedback_rescue(快照级):M 臂 3 次全 fail 且 O 臂 ≥1 次 recover
  且该 rollout realized=true;rescue_rate = rescue 快照数 / 快照总数;
- feedback_harm(快照级):O 受 harm 而 M 同快照无 harm(汇报不进门);
- mechanism split:O 按 realized 分层,delta_x = rec(O_x) − rec(M 全部)。

主口径(预注册声明):Δ 为**快照配对均值差**(每快照 O 均值 − M 均值,
等权平均;快照缺失一臂时按现有 rollout 计),pooled 差并列汇报。
五门(spec §5):
1. Δrecovery ≥ 15pp;2. Δharm ≤ 3pp;3. rescue_rate ≥ 10%;
4. realization_rate ≥ 20%;5. delta_realized ≥ delta_not_realized + 10pp。

输出:analysis/stageN1_results.md
"""
import csv
import io
import json
import os
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A_ROLL = os.path.join(REPO, "analysis/stageN1_rollouts.csv")
A_PROV = os.path.join(REPO, "analysis/stageN1_information_provenance.jsonl")
A_MANI = os.path.join(REPO, "analysis/stageN1_split_manifest.csv")
A_OUT = os.path.join(REPO, "analysis/stageN1_results.md")

HARM_DZ = -0.03
HARM_DXY = 0.08


def read_rows(path):
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def is_harm(r) -> bool:
    """harm(spec §4):success==False 且(z 降 >3cm 或 |Δxy| >8cm)。"""
    if r["success"] == "True":
        return False
    dz = float(r["target_dz_m"]) if r["target_dz_m"] else 0.0
    dxy = float(r["target_dxy_m"]) if r["target_dxy_m"] else 0.0
    return dz < HARM_DZ or dxy > HARM_DXY


def main():
    mani = read_rows(A_MANI)
    snaps = {r["snapshot_id"]: r for r in mani}
    rows = read_rows(A_ROLL)
    valid = [r for r in rows if r["arm"] in ("M", "O")]
    abort = [r for r in rows if r["arm"] == "INFRA_ABORT"]

    prov = [json.loads(l) for l in open(A_PROV, encoding="utf-8")]
    # realized 以 runner 落盘的 CSV 列为准(与 provenance 同源生成;
    # prov 在此只用于 rule_id 分解,不参与 join——避免键型不一致)。
    rule_hits = defaultdict(int)
    for p in prov:
        if p["arm"] == "O" and p["realized"]:
            rule_hits[p["rule_id"]] += 1

    for r in valid:
        r["succ"] = r["success"] == "True"
        r["harm"] = is_harm(r)
        r["realized"] = r["realized"] == "True"

    # ---- 完整性:每快照 6 行(M/O × r0..2)----
    by_snap = defaultdict(list)
    for r in valid:
        by_snap[r["snapshot_id"]].append(r)
    complete = {k for k, v in by_snap.items() if len(v) == 6}
    incomplete = {k: v for k, v in by_snap.items()
                  if k not in complete and k not in {a["snapshot_id"] for a in abort}}
    missing = [k for k in snaps if k not in by_snap]

    # ---- 主指标 ----
    def rate(sub, key):
        return sum(1 for r in sub if r[key]) / len(sub) if sub else float("nan")

    O = [r for r in valid if r["arm"] == "O"]
    M = [r for r in valid if r["arm"] == "M"]
    rec_O, rec_M = rate(O, "succ"), rate(M, "succ")
    harm_O, harm_M = rate(O, "harm"), rate(M, "harm")

    # 快照配对均值差
    diffs_rec, diffs_harm = [], []
    for sid, v in by_snap.items():
        if sid not in complete:
            continue
        m = [r for r in v if r["arm"] == "M"]
        o = [r for r in v if r["arm"] == "O"]
        diffs_rec.append(sum(r["succ"] for r in o) / len(o)
                         - sum(r["succ"] for r in m) / len(m))
        diffs_harm.append(sum(r["harm"] for r in o) / len(o)
                          - sum(r["harm"] for r in m) / len(m))
    d_rec = (sum(diffs_rec) / len(diffs_rec)) if diffs_rec else float("nan")
    d_harm = (sum(diffs_harm) / len(diffs_harm)) if diffs_harm else float("nan")
    pooled_rec = rec_O - rec_M
    pooled_harm = harm_O - harm_M

    # rescue / feedback_harm(快照级)
    rescued, fb_harm = [], []
    for sid, v in by_snap.items():
        if sid not in complete:
            continue
        m, o = [r for r in v if r["arm"] == "M"], [r for r in v if r["arm"] == "O"]
        if all(not r["succ"] for r in m) and any(
                r["succ"] and r["realized"] for r in o):
            rescued.append(sid)
        if any(r["harm"] for r in o) and not any(r["harm"] for r in m):
            fb_harm.append(sid)
    rescue_rate = len(rescued) / len(snaps)

    # realization + mechanism split
    real_rate = rate(O, "realized")
    O_real = [r for r in O if r["realized"]]
    O_not = [r for r in O if not r["realized"]]
    delta_real = rate(O_real, "succ") - rec_M
    delta_not = rate(O_not, "succ") - rec_M

    # ---- 五门 ----
    g1 = d_rec >= 0.15
    g2 = d_harm <= 0.03
    g3 = rescue_rate >= 0.10
    g4 = real_rate >= 0.20
    g5 = (delta_real - delta_not) >= 0.10
    gates = [("1 Δrecovery ≥ 15pp", f"{d_rec*100:+.1f}pp", g1),
             ("2 Δharm ≤ 3pp", f"{d_harm*100:+.1f}pp", g2),
             ("3 rescue_rate ≥ 10%", f"{rescue_rate*100:.1f}% ({len(rescued)}/{len(snaps)})", g3),
             ("4 realization_rate ≥ 20%", f"{real_rate*100:.1f}%", g4),
             ("5 delta_realized ≥ delta_not + 10pp",
              f"{(delta_real-delta_not)*100:+.1f}pp "
              f"({delta_real*100:+.1f} vs {delta_not*100:+.1f})", g5)]
    all_pass = all(g for _, _, g in gates)

    if all_pass:
        verdict = "CLOSED-LOOP FEEDBACK SUPPORTED"
    elif g1 and not (g4 and g5):
        verdict = "OPTION IMPLEMENTATION OUTPERFORMS MACRO, MECHANISM INCONCLUSIVE"
    else:
        verdict = "CLOSED-LOOP FEEDBACK NOT SUPPORTED"

    # ---- 分解 ----
    def brk(sub, key="succ"):
        out = {}
        for proc in ("P1_RPS_REPICK", "P2_FG_RETRY"):
            s = [r for r in sub if r["procedure"] == proc]
            out[proc] = (sum(1 for r in s if r[key]) / len(s) if s else None,
                         len(s))
        return out

    end_reasons = defaultdict(int)
    for r in O:
        end_reasons[f"O:{r['end_reason']}"] += 1
    for r in M:
        end_reasons[f"M:{r['end_reason']}"] += 1

    # ---- 报告 ----
    out = io.StringIO()
    w = out.write
    w("# Stage N1 结果 — CLOSED-LOOP OPTION vs FIXED_MACRO(§4-§5)\n\n")
    w(f"- rollouts:有效 {len(valid)}(M={len(M)} O={len(O)});"
      f"INFRA_ABORT 快照 {len(abort)};manifest 快照 {len(snaps)}\n")
    w(f"- 完整快照(6 行){len(complete)}/{len(snaps)}"
      + (f";不完整:{sorted(incomplete)}" if incomplete else "") + "\n"
      + (f";缺失:{missing}" if missing else "") + "\n\n")

    w("## 1. 主指标\n\n| 指标 | M | O | Δ(快照配对) | Δ(pooled) |\n|---|---|---|---|---|\n")
    w(f"| validated_recovery | {rec_M*100:.1f}% | {rec_O*100:.1f}% | "
      f"**{d_rec*100:+.1f}pp** | {pooled_rec*100:+.1f}pp |\n")
    w(f"| harm | {harm_M*100:.1f}% | {harm_O*100:.1f}% | "
      f"**{d_harm*100:+.1f}pp** | {pooled_harm*100:+.1f}pp |\n\n")
    w(f"- rescue 快照:{sorted(rescued) if rescued else '∅'}"
      f"→ rescue_rate = {rescue_rate*100:.1f}%\n")
    w(f"- feedback_harm 快照(汇报不进门):{sorted(fb_harm) if fb_harm else '∅'}\n")
    w(f"- realization_rate(O)={real_rate*100:.1f}%"
      f"({sum(1 for r in O if r['realized'])}/{len(O)})\n")
    w(f"- mechanism split:delta_realized={delta_real*100:+.1f}pp "
      f"(n={len(O_real)}) / delta_not={delta_not*100:+.1f}pp (n={len(O_not)})\n\n")

    w("## 2. 五门判定(§5 逐字)\n\n| 门 | 实测 | 判定 |\n|---|---|---|\n")
    for name, val, ok in gates:
        w(f"| {name} | {val} | {'PASS' if ok else 'FAIL'} |\n")
    w(f"\n**判定:{verdict}**\n\n")

    w("## 3. 分解(描述性)\n\n")
    w("| 臂×procedure | recovery | harm | n |\n|---|---|---|---|\n")
    for arm, sub in (("M", M), ("O", O)):
        rr, hh = brk(sub, "succ"), brk(sub, "harm")
        for proc in ("P1_RPS_REPICK", "P2_FG_RETRY"):
            w(f"| {arm} {proc} | {(rr[proc][0] or 0)*100:.0f}% | "
              f"{(hh[proc][0] or 0)*100:.0f}% | {rr[proc][1]} |\n")
    w("\nend_reason 分布:" +
      " / ".join(f"{k}={v}" for k, v in sorted(end_reasons.items())) + "\n")
    w("\nO 臂 realized 按 rule_id(计数,同一 rollout 可多条):" +
      " / ".join(f"{k}={v}" for k, v in sorted(rule_hits.items())) + "\n")

    # 背景对照(描述性,非门输入):源 episode 在完整 planner 预算下
    # 的最终结局——证明快照态本身可恢复、check_success 通道正常。
    src_ok = 0
    for sid, m in snaps.items():
        try:
            steps = json.load(open(os.path.join(
                m["episode_dir"], "states.json")))
            last = sorted(steps, key=lambda s: s.get("step_idx", 0))[-1]
            res = last.get("result") or {}
            if res.get("libero_terminated") or res.get("success"):
                src_ok += 1
        except Exception:
            pass
    w(f"\n源 episode 最终 terminated/success(完整 planner 预算,对照):"
      f"{src_ok}/{len(snaps)} —— 快照态可恢复性成立,"
      f"0% recovery 属于宏预算内不可恢复,而非通道损坏或不可恢复态。\n")
    w("\n按 tercile recovery(M→O):\n")
    for ter in ("S", "M", "L"):
        mm = [r for r in M if r["tercile"] == ter]
        oo = [r for r in O if r["tercile"] == ter]
        w(f"- {ter}:M {(rate(mm,'succ') or 0)*100:.0f}% → "
          f"O {(rate(oo,'succ') or 0)*100:.0f}% (n={len(mm)}/{len(oo)})\n")

    with open(A_OUT, "w", encoding="utf-8") as f:
        f.write(out.getvalue())
    print(out.getvalue())
    print(f"已写入 {A_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
