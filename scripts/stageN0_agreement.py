#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage N0 §10-11:盲审 agreement 计算 + 测量双门判定。

数据三方 join:
- analysis/stageN0_audit_manifest.csv  抽样 manifest(audit_id ↔ segment_id,机器类)
- analysis/stageN0_manual_audit.csv    人工盲审作答(先落盘后比对,已 commit 冻结)
- analysis/stageN0_control_labels.csv  analyzer v2 段级标签(全池)

指标(spec §10):
- overall agreement = #(machine == human) / #(human-resolved)
  (human-resolved = 人工 label ∈ {DEPENDENT, INDEPENDENT},UNRESOLVED 不计入分母)
- false_independent = #(H=D ∧ M=I) / #(H=D)
- false_dependent   = #(H=I ∧ M=D) / #(H=I)(分母为 0 时记 n/a)
- 3×3 混淆矩阵 + 双侧 UNRESOLVED 率

门(spec §11):overall ≥ 90% ∧ false_independent ≤ 5% ∧ human-resolved ≥ 30。

输出:analysis/stageN0_measurement_results.md
"""
import csv
import io
import os
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A_MANIFEST = os.path.join(REPO, "analysis/stageN0_audit_manifest.csv")
A_MANUAL = os.path.join(REPO, "analysis/stageN0_manual_audit.csv")
A_MACHINE = os.path.join(REPO, "analysis/stageN0_control_labels.csv")
A_OUT = os.path.join(REPO, "analysis/stageN0_measurement_results.md")

CLS = ["DEPENDENT", "UNRESOLVED", "INDEPENDENT"]


def read_rows(path):
    """读 CSV(dict),manifest 的注释行(# 开头)跳过。"""
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def main():
    manifest = read_rows(A_MANIFEST)
    manual = {r["audit_id"]: r for r in read_rows(A_MANUAL)}
    machine = {r["segment_id"]: r for r in read_rows(A_MACHINE)}

    # ---- join + 完整性断言 ----
    rows = []
    for m in manifest:
        aid, sid = m["audit_id"], m["segment_id"]
        assert aid in manual, f"人工作答缺失:{aid}"
        assert sid in machine, f"v2 段标签缺失:{sid}"
        rows.append({
            "audit_id": aid,
            "segment_id": sid,
            "family": m["family"],
            "tercile": m["length_tercile"],
            "task": m["task"],
            "human": manual[aid]["label"],
            "machine": machine[sid]["segment_label"],
            "machine_types": machine[sid]["dependency_types"],
            "human_evidence": manual[aid]["evidence_event"],
            "human_type": manual[aid]["dependency_type"],
        })
    assert len(rows) == 45, len(rows)

    # ---- 混淆矩阵 ----
    conf = defaultdict(int)
    for r in rows:
        conf[(r["human"], r["machine"])] += 1

    def cell(h, m):
        return conf.get((h, m), 0)

    n = len(rows)
    human_resolved = [r for r in rows if r["human"] in ("DEPENDENT", "INDEPENDENT")]
    h_res = len(human_resolved)
    h_unres = sum(1 for r in rows if r["human"] == "UNRESOLVED")
    m_unres = sum(1 for r in rows if r["machine"] == "UNRESOLVED")

    agree_resolved = sum(1 for r in human_resolved if r["human"] == r["machine"])
    overall = agree_resolved / h_res if h_res else float("nan")

    n_hd = sum(1 for r in rows if r["human"] == "DEPENDENT")
    n_hi = sum(1 for r in rows if r["human"] == "INDEPENDENT")
    n_hd_mi = cell("DEPENDENT", "INDEPENDENT")   # 假独立:漏报依赖
    n_hi_md = cell("INDEPENDENT", "DEPENDENT")   # 假依赖:误报依赖
    false_indep = n_hd_mi / n_hd if n_hd else float("nan")
    false_dep = (n_hi_md / n_hi) if n_hi else None  # 分母 0 → n/a

    # ---- 门判定 ----
    g_overall = overall >= 0.90
    g_false_indep = (n_hd == 0) or (false_indep <= 0.05)  # 分母 0 时按结构空集处理
    g_resolved = h_res >= 30
    gate_pass = g_overall and g_false_indep and g_resolved

    # ---- 分歧明细(0 则如实写)----
    dis = [r for r in rows if r["human"] != r["machine"]]

    # ---- 描述性:人工 type 分布 + 人机 type 交集(同意段上)----
    h_types = Counter(r["human_type"] for r in rows)
    overlap = Counter()
    for r in rows:
        if r["human"] == r["machine"]:
            mt = r["machine_types"].strip("[]'").replace("'", "").replace(" ", "")
            if r["human_type"] in mt.split(","):
                overlap["both"] += 1
            else:
                overlap["machine_only"] += 1

    # ---- 族 / 分位 / 任务分解 ----
    by_fam = defaultdict(lambda: [0, 0])
    by_ter = defaultdict(lambda: [0, 0])
    for r in human_resolved:
        for key, store in ((r["family"], by_fam), (r["tercile"], by_ter)):
            store[key][1] += 1
            if r["human"] == r["machine"]:
                store[key][0] += 1

    # ---- 报告 ----
    out = io.StringIO()
    w = out.write
    w("# Stage N0 测量资格结果(§10 盲审 agreement + §11 双门)\n\n")
    w("- 机器:analyzer v2(确定性零 LLM,冻结于 DEVELOPMENT 阶段后)\n")
    w("- 人工:45 卷盲审,仅凭卷宗作答,先落盘后比对(commit 61f968f 先于本脚本运行)\n")
    w(f"- 样本:N=45(seed=20261002;eligible=124;q_D=45 q_I=0 q_U=0,deviation #5)\n\n")

    w("## 1. 混淆矩阵(人工 × 机器,N=45)\n\n")
    w("| 人工 \\ 机器 | DEPENDENT | UNRESOLVED | INDEPENDENT | 合计 |\n|---|---|---|---|---|\n")
    for h in CLS:
        cells = [cell(h, m) for m in CLS]
        w(f"| {h} | {cells[0]} | {cells[1]} | {cells[2]} | {sum(cells)} |\n")
    w("| 合计 | " + " | ".join(str(sum(cell(h, m) for h in CLS)) for m in CLS) + f" | {n} |\n\n")

    w("## 2. 主指标\n\n")
    w(f"- **overall agreement**(human-resolved 上)= {agree_resolved}/{h_res} = **{overall:.3f}**\n")
    w(f"- **false_independent** = #(H=D ∧ M=I)/#(H=D) = {n_hd_mi}/{n_hd} = "
      f"**{false_indep:.3f}**\n")
    if false_dep is None:
        w("- **false_dependent** = n/a(#(H=I)=0,人工侧无独立段)\n")
    else:
        w(f"- **false_dependent** = {n_hi_md}/{n_hi} = {false_dep:.3f}\n")
    w(f"- human-resolved = {h_res}/45;人工 UNRESOLVED = {h_unres};机器 UNRESOLVED = {m_unres}\n")
    w(f"- 机器侧结构说明:审计池 45/45 为 machine-DEPENDENT(eligible∩I=0,prereg deviation #5),\n")
    w("  false_independent 门的分子分母均来自 H=D 列,机器-I 方向本轮未被审计检验;\n")
    w("  其方向正确性仅有 dev 阶段全量 5 段 census(4 同意 + 1 存疑 rotate_wrist)作旁证。\n\n")

    w("## 3. 双门判定(§11)\n\n")
    w(f"| 门 | 阈值 | 实测 | 判定 |\n|---|---|---|---|\n")
    w(f"| overall agreement | ≥ 90% | {overall*100:.1f}% | {'PASS' if g_overall else 'FAIL'} |\n")
    w(f"| false_independent | ≤ 5% | {false_indep*100:.1f}% | {'PASS' if g_false_indep else 'FAIL'} |\n")
    w(f"| human-resolved | ≥ 30 | {h_res} | {'PASS' if g_resolved else 'FAIL'} |\n\n")
    w(f"**N0 测量资格门:{'PASS' if gate_pass else 'FAIL'}**"
      f"{' → 允许进入 N1(闭环反馈验证)' if gate_pass else ' → STOP:TRAJECTORY-ONLY CONTROL DEPENDENCY CANNOT YET BE MEASURED RELIABLY'}\n\n")

    w("## 4. 分歧明细(span / 数值链重放)\n\n")
    if not dis:
        w("- **零分歧**:45/45 人工 DEPENDENT 与机器 DEPENDENT 一致,无需重放。\n\n")
    else:
        for r in dis:
            w(f"### {r['audit_id']} / {r['segment_id']}\n")
            w(f"- 人工:{r['human']}(证据:{r['human_evidence']};类型:{r['human_type']})\n")
            w(f"- 机器:{r['machine']}(依赖类型:{r['machine_types']})\n")
            w(f"- 卷宗:analysis/stageN0_audit_dossiers/{r['audit_id']}.md\n\n")

    w("## 5. 描述性补充(非门输入)\n\n")
    w("- 人工 dependency_type 分布:" +
      " / ".join(f"{k}={v}" for k, v in h_types.most_common()) + "\n")
    w(f"- 同意段上人工 type ∈ 机器 dependency_types:{overlap.get('both',0)}/45;"
      f"仅机器侧含:{overlap.get('machine_only',0)}\n")
    w("- 按族 agreement:" +
      " / ".join(f"{k}={v[0]}/{v[1]}" for k, v in sorted(by_fam.items())) + "\n")
    w("- 按长度三分位 agreement:" +
      " / ".join(f"{k}={v[0]}/{v[1]}" for k, v in sorted(by_ter.items())) + "\n")

    with open(A_OUT, "w", encoding="utf-8") as f:
        f.write(out.getvalue())

    # 控制台摘要
    print(out.getvalue())
    print(f"已写入 {A_OUT}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
