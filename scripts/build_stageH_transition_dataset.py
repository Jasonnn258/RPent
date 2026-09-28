#!/usr/bin/env python3
"""Stage H §7 transition dataset builder(只建数据,不训练 —— spec 明令)。

两个来源,一份 schema:
  src=h0  G0.5/G0.6 历史 148 决策点(analysis/stageH0_failure_states.jsonl,
          与 stageH2_router_items.jsonl 逐点 join 补 node/合法边/冻结标签);
  src=h1  本次 H1 三臂 90 集的全部 fire(重放触发 + 事件交叉核对,
          与 analyze_stageH1.py 同一代码路径),记录注入内容 → 下一条
          实际原语 → W=5 物理验证结果。

每条记录 = 一次干预 transition:(active node, 合法出边菜单, 注入块,
next_prim, guard_ok, validated@5, episode SR)。未来 H3 若做学习式
router,训练对便是 (runtime_view, node, legal_edges) → 标签(h0 的
correct_set / h1 的 validating family);本文档只落盘,不训练。

split 纪律与 H0 协议一致:md5("libero_spatial_task_t{t}_s{s}") % 100
< 40 → validation,否则 discovery;(task,seed) 永远同侧。

用法: python scripts/build_stageH_transition_dataset.py [--include-smoke]
产物: analysis/stageH_transition_dataset.jsonl / .md
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from ovpm_exp import H1_CELLS, P0_SUITE, RUNS_CSV  # noqa: E402
from analyze_stageH1 import (  # noqa: E402
    INFRA, NODE_FAMILY, FakeTracker, load_events, next_act_steps,
    replay_fires, fire_validated, reconstruct_block, mapped_prims,
)
from rpent.memory.retrieval import DecisionMemory  # noqa: E402
from rpent.graph.schema import load_graph  # noqa: E402

H0_STATES = REPO / "analysis/stageH0_failure_states.jsonl"
H2_ITEMS = REPO / "analysis/stageH2_router_items.jsonl"
OUT = REPO / "analysis/stageH_transition_dataset.jsonl"
OUT_MD = REPO / "analysis/stageH_transition_dataset.md"


def build_card_memory():
    """CARD 块重建器(与 analyze_stageH1.main 同 env 构造;h1C 臂用)。"""
    os.environ.update({
        "RPENT_MEMORY_TRIGGER": "graph",
        "RPENT_MEMORY_INJECTION_MODE": "memory_only",
        "RPENT_MEMORY_QUERY_MODE": "common",
        "RPENT_MEMORY_RANK": "Q0_FIXED",
        "RPENT_MEMORY_QUERY_REASON": "0",
        "RPENT_MEMORY_BLOCK_REASON": "0",
    })
    return DecisionMemory(FakeTracker(), mode="graph")


def split_of(task: int, seed: int) -> str:
    h = hashlib.md5(f"libero_spatial_task_t{task}_s{seed}".encode()).hexdigest()
    return "validation" if int(h, 16) % 100 < 40 else "discovery"


# runtime 可观测字段白名单(= interpreter 看得到的原语结果字段;
# 任何 analysis_only / GT / 未来字段不得进入)
_OBS_KEYS = ("success", "peak_lift_m", "final_dist_m",
             "final_gripper_opening", "gripper_opening")


def obs_of_step(step: dict) -> dict:
    """一步的 runtime 可观测摘要(command.action + 白名单结果字段)。"""
    r = step.get("result") or {}
    return {"action": (step.get("command") or {}).get("action"),
            **{k: r[k] for k in _OBS_KEYS if k in r}}


def h0_records():
    """148 历史点 → transition 记录(标签 = H2 冻结 correct_set/DEFER)。"""
    items = {}
    if H2_ITEMS.exists():
        items = {json.loads(l)["evidence_id"]: json.loads(l)
                 for l in open(H2_ITEMS)}
    out = []
    for ln in open(H0_STATES):
        pt = json.loads(ln)
        eid = pt["evidence_id"]
        it = items.get(eid, {})
        rv = pt["runtime_view"]
        out.append({
            "src": "h0", "split": pt.get("split") or split_of(
                pt["task"], pt["seed"]),
            "task": pt["task"], "seed": pt["seed"],
            "evidence_id": eid, "family": pt["failure_family"],
            "node": it.get("node"),
            "legal_edges": it.get("legal_edges"),
            "legal_edge_families": it.get("legal_edge_families"),
            # h0 无干预注入(历史轨迹),注入字段为 null
            "arm": None, "injected_block": None,
            "runtime_view": {
                "observable_pre_state": rv["observable_pre_state"],
                "recent_window": rv["recent_window"],
                "task_goal": rv["task_goal"],
            },
            "label": it.get("label"), "correct_set": it.get("correct_set"),
            "label_sub": it.get("label_sub"),
            "next_prim": None, "guard_ok": None,
            "validated_w5": None, "validating_prim": None,
            "episode_sr": pt["analysis_only"]["episode_final_success"],
        })
    return out


def h1_records(include_smoke: bool):
    """H1 全部 fire → transition 记录(与 analyze_stageH1 同一代码路径)。"""
    g = load_graph()
    dm_card = build_card_memory()
    rows = {}
    with open(RUNS_CSV) as f:
        for r in csv.DictReader(f):
            if r["stage"] != "h1" or r["suite"] != P0_SUITE:
                continue
            rows[(r["cond"], int(r["task"]), int(r["seed"]))] = r
    out, infra_n, mismatch_n = [], 0, 0
    for (arm, t, sd), r in sorted(rows.items()):
        if (t, sd) not in H1_CELLS and not include_smoke:
            continue
        if r["result"] in INFRA:
            infra_n += 1
            continue
        d = r["dir"]
        try:
            steps = json.load(open(os.path.join(d, "states.json")))
        except Exception:  # noqa: BLE001
            infra_n += 1
            continue
        sr = bool(steps[-1].get("libero_terminated"))
        events = load_events(d)
        fires = replay_fires(steps)
        ev_nodes = [e["trigger_reason"].split("=", 1)[1]
                    for e in events if "=" in e.get("trigger_reason", "")]
        ok = (len(ev_nodes) == len(fires)
              and all(a == b["node"] for a, b in zip(ev_nodes, fires)))
        if not ok:
            mismatch_n += 1
            continue  # 与分析器同口径:不一致的集不进 fire 类记录
        for ev, fr in zip(events, fires):
            node, i, eids = fr["node"], fr["step_idx"], fr["edges"]
            win = next_act_steps(steps, i, 5)
            validated = fire_validated(node, win)
            vp = None
            if validated:
                for a, r2, term in win:
                    if term or fire_validated(node, [(a, r2, term)]):
                        vp = a
                        break
            nxt = next_act_steps(steps, i, 1)
            next_prim = nxt[0][0] if nxt else None
            guard_set = mapped_prims(eids, g)
            blk, _ = reconstruct_block(arm, ev, node, eids, g, dm_card)
            out.append({
                "src": "h1", "split": split_of(t, sd), "task": t,
                "seed": sd, "arm": arm, "episode_dir": d,
                "fire_k": len(out), "step_idx": i, "family":
                    NODE_FAMILY[node], "node": node,
                "legal_edges": eids,
                "legal_edge_families": [g.edge(e).action_family for e in eids],
                "injected_block": blk,
                "runtime_view": {
                    "fire_step": obs_of_step(steps[i]),
                    "recent_window": [obs_of_step(s) for s in
                                      steps[max(0, i - 4):i + 1]],
                },
                "label": None, "correct_set": None, "label_sub": None,
                "next_prim": next_prim,
                "guard_ok": (None if next_prim is None
                             else next_prim in guard_set),
                "validated_w5": validated,
                "validating_prim": vp,
                "episode_sr": sr,
            })
    return out, infra_n, mismatch_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-smoke", action="store_true")
    args = ap.parse_args()

    h0 = h0_records()
    h1, infra_n, mismatch_n = h1_records(args.include_smoke)
    recs = h0 + h1
    with open(OUT, "w") as f:
        for rec in recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()

    # ---- 摘要(analysis/stageH_transition_dataset.md)----
    by = collections.Counter((r["src"], r.get("arm")) for r in recs)
    val = collections.Counter(
        (r["src"], r.get("arm"), r["validated_w5"]) for r in recs
        if r["src"] == "h1")
    fam = collections.Counter((r["src"], r["family"]) for r in recs)
    L = ["# Stage H transition dataset(§7,只建不训)\n",
         f"_生成 by scripts/build_stageH_transition_dataset.py;"
         f"记录数 {len(recs)}(h0 {len(h0)} + h1 {len(h1)});"
         f"sha256 = {sha}_\n",
         "- h0 记录:历史 148 点 + H2 冻结标签(join stageH2_router_items;"
         "无干预注入,arm/injected_block/next_prim = null);",
         "- h1 记录:H1 fire 级(重放触发 + 事件交叉核对同分析器;"
         f"infra 缺失 {infra_n} 集、事件不一致剔除 {mismatch_n} 集);",
         "- split:md5(task,seed)%100<40 → validation(与 H0 协议一致);",
         "- **未做任何训练**(§7 冻结;H3 不自动开启)。\n",
         "## 计数\n", "| src | arm | n |", "|---|---|---|"]
    for (src, arm), n in sorted(by.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        L.append(f"| {src} | {arm or '—'} | {n} |")
    L += ["\n## h1 validated@5(fire 级)\n", "| arm | validated | n |",
          "|---|---|---|"]
    for (src, arm, v), n in sorted(val.items()):
        L.append(f"| {arm} | {v} | {n} |")
    L += ["\n## family 分布\n", "| src | family | n |", "|---|---|---|"]
    for (src, f_), n in sorted(fam.items()):
        L.append(f"| {src} | {f_} | {n} |")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nwrote {OUT} (sha256 {sha})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
