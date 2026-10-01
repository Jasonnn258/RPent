#!/usr/bin/env python
"""Stage M §7 — M0 人工盲审 dossier 生成器。

从原始工件(states.json / transcript_*.json)渲染盲审材料,**不含**
analyzer 的事件标注 / 标签 / FID / 任何聚合结论。抽样按族分层、
seed=20261001 机械抽取;n_audit = max(⌈0.2·n_RESOLVED⌉, 30),
并剔除 analyzer 开发期带标签抽查过的 6 条(顺延补足,见
stageM0_audit_protocol 说明)。

产物:analysis/stageM0_audit_dossiers/{id}.md(编号脱敏,不含标签)
      analysis/stageM0_audit_sample.csv(id ↔ segment 映射,审计后用)
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stageM0_analyze import (PRIMS, build_timeline, load_steps)  # noqa: E402

SEED = 20261001
# analyzer 开发期带标签看过(2026-10-01 自检)的 segment,盲审剔除
SPOT_CHECKED = {
    "20260915-18:12:26_glm-5.3-flash_armA_libero_spatial_task_t5_s4_r1#f1",
    "20260907-18:29:08_glm-5.3-flash_armC_libero_spatial_task_t9_s10_r2#f1",
    "20260915-18:12:26_glm-5.3-flash_armA_libero_spatial_task_t5_s4_r1#f0",
}


def stratified_sample(segs, n_audit):
    """按族比例分层机械抽取(余数最大者优先)。"""
    rng = random.Random(SEED)
    by_fam = defaultdict(list)
    for s in segs:
        by_fam[s["family"]].append(s["segment_id"])
    for v in by_fam.values():
        rng.shuffle(v)               # 族内洗牌(可复现)
    tot = len(segs)
    quota = {f: int(n_audit * len(v) / tot) for f, v in by_fam.items()}
    rema = n_audit - sum(quota.values())
    for f in sorted(by_fam, key=lambda f: -(n_audit * len(by_fam[f]) / tot
                                            - quota[f]))[:rema]:
        quota[f] += 1
    picked = []
    for f, ids in by_fam.items():
        picked += [(f, i) for i in ids[:quota[f]]]
    return picked, quota


def render(md_path, seg, steps_by_idx, tl, events):
    """原始材料渲染(无任何 analyzer 结论)。"""
    t0, tR = seg["t0"], seg["tR"]
    seq_of_step = {v: u["seq"] for i, u in enumerate(tl["uses"])
                   if (v := tl["anchor"][i]) is not None}
    lo, hi = seq_of_step[t0], seq_of_step[tR]
    L = []
    L.append(f"# 盲审 dossier:{md_path.stem}")
    L.append(f"- 失败族(fire 检测):{seg['family']}")
    L.append(f"- t0(失败步)= step {t0};tR(首个验证步)= step {tR}")
    L.append(f"- task {seg['task']} / seed {seg['seed']}")
    st0, stR = steps_by_idx[t0]["state"], steps_by_idx[tR]["state"]
    L.append(f"- t0 eef {['%.3f' % x for x in st0['robot0_eef_pos']]} "
             f"grip {st0['robot0_gripper_qpos']}")
    L.append(f"- tR eef {['%.3f' % x for x in stR['robot0_eef_pos']]} "
             f"grip {stR['robot0_gripper_qpos']}")
    L.append("\n## 窗口内命令与结果(states.json 原文)\n")
    for s in sorted(steps_by_idx.values(), key=lambda s: s["step_idx"]):
        if not t0 <= s["step_idx"] <= tR or not (s.get("command") or {}).get("action"):
            continue
        L.append(f"### step {s['step_idx']}")
        L.append("```json\n"
                 + json.dumps(s["command"], ensure_ascii=False, indent=1)
                 + "\n```")
        L.append("```json\n"
                 + json.dumps(s.get("result") or {}, ensure_ascii=False,
                              indent=1)[:1200]
                 + "\n```")
    L.append("\n## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)"
             "\n(思考块截 400 字,其余原文;tool 结果截 800 字)\n")
    for mi, m in enumerate([m for m in events["msgs"]]):
        seqs = events["mi_range"].get(mi)
        if seqs is None or not (lo <= seqs[0] <= hi or lo <= seqs[1] <= hi):
            continue
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                bt = b.get("type")
                if bt == "thinking":
                    L.append(f"- [msg{mi} assistant 思考] "
                             f"{str(b.get('thinking'))[:400]}")
                elif bt == "text":
                    L.append(f"- [msg{mi} assistant 文本] {b.get('text')}")
                elif bt == "tool_use":
                    L.append(f"- [msg{mi} assistant 调用 {b.get('name')}] "
                             f"```json\n"
                             + json.dumps(b.get("input") or {}, ensure_ascii=False)
                             + "\n```")
        elif m["role"] == "tool":
            L.append(f"- [msg{mi} tool 结果] "
                     f"{str(m.get('content'))[:800]}")
        elif m["role"] == "user":
            L.append(f"- [msg{mi} user] {str(c)[:300]}")
    L.append("\n## 请作答(不看任何分析输出,仅凭以上材料)")
    L.append("1. label(四选一):EDGE_REPRESENTABLE / MACRO_REPRESENTABLE / "
             "OPTION_REQUIRED / UNRESOLVED")
    L.append("2. FID(未来信息依赖,true/false):t0 时刻可观测信息是否足以"
             "确定后续成功序列(动作族/目标/参数/重试-终止决策),"
             "还是必须依赖 t0 之后的观察/定位/验证结果?")
    md_path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    segs = [json.loads(l) for l in
            open(REPO / "analysis/stageM0_recovery_segments.jsonl")]
    resolved = [s for s in segs if s["label"] != "UNRESOLVED"]
    pool = [s for s in resolved if s["segment_id"] not in SPOT_CHECKED]
    n_audit = max(-(-len(resolved) * 20 // 100), 30)   # ⌈0.2n⌉
    picked, quota = stratified_sample(pool, n_audit)
    print(f"RESOLVED {len(resolved)} | 可抽池 {len(pool)} "
          f"(剔带标签抽查 {len(resolved) - len(pool)}) | n_audit {n_audit}")
    print("quota:", quota)

    outdir = REPO / "analysis/stageM0_audit_dossiers"
    outdir.mkdir(exist_ok=True)
    rows = []
    for i, (fam, sid) in enumerate(sorted(picked)):
        seg = next(s for s in segs if s["segment_id"] == sid)
        d = Path(seg["episode_dir"])
        steps = load_steps(d)
        steps_by_idx = {s["step_idx"]: s for s in steps}
        tl = build_timeline(d)
        assert tl and tl.get("align_ok")
        msgs = json.load(open(sorted(d.glob("transcript_*.json"))[0]))["messages"]
        mi_range = {}
        from stageM0_analyze import flat_events
        ev = flat_events(msgs)
        for e in ev:
            a, b = mi_range.get(e["mi"], (e["seq"], e["seq"]))
            mi_range[e["mi"]] = (min(a, e["seq"]), max(b, e["seq"]))
        aid = f"dossier_{i:02d}"
        render(outdir / f"{aid}.md", seg, steps_by_idx, tl,
               {"msgs": msgs, "mi_range": mi_range})
        rows.append({"audit_id": aid, "segment_id": sid, "family": fam})
    with open(REPO / "analysis/stageM0_audit_sample.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["audit_id", "segment_id", "family"])
        w.writeheader()
        w.writerows(rows)
    print(f"-> {outdir} ({len(rows)} dossiers) + stageM0_audit_sample.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
