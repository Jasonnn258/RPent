#!/usr/bin/env python
"""Stage N §9 — N0 人工盲审卷宗生成器(结构盲)。

从 manifest 读抽样(选择与渲染解耦:seed 只用于 sampler,本脚本不抽样),
从原始工件(states.json / transcript_*.json)渲染,**不含** v2 任何输出
(事件/标签/正则命中)、M 标签、聚合率、tR 之后集结局、memory 卡内容。

与 M 卷宗的差异(prereg §9/spec §9):
- tR 写作中性"窗口结束步",不写 tR_reason(不泄漏验证语义);
- 头部含事件边界契约(附录 A.5):qualifying information event 定义,
  使审计人与测量共享同一事件边界;
- 作答为三态反事实(label / evidence_event / dependency_type)。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from analyze_stageH1 import fire_validated, replay_fires  # noqa: E402
from stageM0_analyze import build_timeline, flat_events, load_steps  # noqa: E402

CONTRACT = """## 事件边界契约(审计与测量共享的定义;只对 qualifying 事件作答)

窗口 = (t0, tR],即 t0 结果到达之后、tR 发射为止。**qualifying information
event** 限以下四类:

1. **OBSERVE**:read_image / view_driver_state 的结果到达;
2. **GROUNDING**:back_project / segment 的结果到达;
3. **VERIFIER**:pi0_pick / pi0_doubled / move_to / move_pose / set_gripper
   的 result 到达(t0 与 tR 自身的 result 是窗口边界,不计入);
4. **STATE_UPDATE**:libero_terminated 实际翻转(True↔False)。

排除(不构成新信息):
- 每个动作 result 都携带的 libero_terminated **取值与 t0 相同的复读**
  (否则任何动作结果都是事件,问题退化为平凡);
- VERIFIER **正结果**(动作如预期成功)若 planner 仅叙述数值、全文无任何
  条件反应,视为预期内复读;**负结果**(失败/未达)恒为新信息;
- t0 自身 result 属 initiation(恢复被触发的依据),不是窗口内新信息。

反事实问题(对每个 qualifying event e):
> If the newly acquired observation at e had been **different but still
> physically plausible**, would the downstream recovery control (action,
> parameter, continuation, retry, fallback, or termination) have changed?
"""

ANSWER = """## 请作答(仅凭以上材料;不看任何分析输出)

段级三选一(聚合规则:任一事件 YES → DEPENDENT;全部事件 NO 且观察前
序列+关键参数已固定 → INDEPENDENT;无法证明任一方 → UNRESOLVED,禁止猜测):

1. **label**:DEPENDENT / INDEPENDENT / UNRESOLVED
2. **evidence_event**:支撑判定的关键事件定位(引用 step 编号或
   [msgN] 编号,如 "step 8 move_to 结果" / "[msg54] 看图后";无事件写 none)
3. **dependency_type**(八选一):observation_gate / target_grounding /
   pose_update / parameter_update / verifier_branch / retry_fallback /
   termination / none
"""


def render(md_path, row, steps_by_idx, tl, msgs, mi_range):
    """原始材料渲染(无任何 v2/M 结论)。"""
    t0, tR = int(row["t0"]), int(row["tR"])
    seq_of_step = {v: u["seq"] for i, u in enumerate(tl["uses"])
                   if (v := tl["anchor"][i]) is not None}
    lo, hi = seq_of_step[t0], seq_of_step[tR]
    L = []
    L.append(f"# N0 盲审卷宗:{md_path.stem}(control-dependency audit)")
    L.append(f"- 失败族:{row['family']}(node {row['node']})")
    L.append(f"- t0(窗口起始步)= step {t0};tR(窗口结束步)= step {tR}")
    L.append(f"- task {row['task']} / seed {row['seed']} / "
             f"长度层 {row['length_tercile']}")
    st0, stR = steps_by_idx[t0]["state"], steps_by_idx[tR]["state"]
    L.append(f"- t0 eef {['%.3f' % x for x in st0['robot0_eef_pos']]} "
             f"grip {st0['robot0_gripper_qpos']}")
    L.append(f"- tR eef {['%.3f' % x for x in stR['robot0_eef_pos']]} "
             f"grip {stR['robot0_gripper_qpos']}")
    if st0.get("object_names"):
        L.append(f"- t0 物体 {st0['object_names']}")
    L.append("\n" + CONTRACT)
    L.append("## 窗口内命令与结果(states.json 原文,step t0 至 tR)\n")
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
             "\n(思考块截 400 字,其余原文;tool 结果截 800 字;"
             "tR 自身 result 不在窗口内)\n")
    for mi, m in enumerate(msgs):
        seqs = mi_range.get(mi)
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
                             + json.dumps(b.get("input") or {},
                                          ensure_ascii=False)
                             + "\n```")
        elif m["role"] == "tool":
            L.append(f"- [msg{mi} tool 结果] "
                     f"{str(m.get('content'))[:800]}")
        elif m["role"] == "user":
            L.append(f"- [msg{mi} user] {str(c)[:300]}")
    L.append("\n" + ANSWER)
    md_path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    # manifest:跳过注释行
    lines = [l for l in
             open(REPO / "analysis/stageN0_audit_manifest.csv").readlines()
             if not l.startswith("#")]
    manifest = list(csv.DictReader(lines))
    outdir = REPO / "analysis/stageN0_audit_dossiers"
    outdir.mkdir(exist_ok=True)
    # 清旧卷宗(重生成前;只清本目录内 .md)
    for old in outdir.glob("dossier_*.md"):
        old.unlink()

    cache = {}      # episode_dir → (steps_by_idx, tl, msgs, mi_range)
    # 池 inventory:name → 完整目录(与分析脚本同源)
    dir_of = {}
    for ln in open(REPO / "analysis/stageL_pool_inventory.jsonl"):
        r = json.loads(ln)
        dir_of[Path(r["episode_dir"]).name] = r["episode_dir"]
    for row in manifest:
        ep = row["segment_id"].split("#")[0]
        d = Path(dir_of[ep])
        assert (d / "states.json").exists(), f"缺 states.json {d}"
        if str(d) not in cache:
            steps = load_steps(d)
            tl = build_timeline(d)
            assert tl and tl.get("align_ok"), f"align fail {d}"
            msgs = json.load(
                open(sorted(d.glob("transcript_*.json"))[0]))["messages"]
            mi_range = {}
            for e in flat_events(msgs):
                a, b = mi_range.get(e["mi"], (e["seq"], e["seq"]))
                mi_range[e["mi"]] = (min(a, e["seq"]), max(b, e["seq"]))
            cache[str(d)] = ({s["step_idx"]: s for s in steps}, tl, msgs,
                             mi_range)
        steps_by_idx, tl, msgs, mi_range = cache[str(d)]
        render(outdir / f"{row['audit_id']}.md", row, steps_by_idx, tl,
               msgs, mi_range)
    print(f"-> {outdir} ({len(manifest)} dossiers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
