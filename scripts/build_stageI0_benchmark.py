#!/usr/bin/env python3
"""Stage I0 — local router qualification benchmark 构建(spec §1.1,冻结)。

底料 = analysis/stageH_transition_dataset.jsonl(h0 148 + h1 104)。
每条 transition → 一个 router sample:

CLEAR / AMBIGUOUS 分离规则(先于任何模型调用冻结):
  - h0:label == EDGE(correct_set 基数全 1,H2 冻结)→ CLEAR,
        reference_edge = correct_set[0];
        label == DEFER → AMBIGUOUS(sub = not_validated / out_of_menu)。
  - h1:validated_w5 且 validating_prim 经 ACTION_FAMILY_PRIMS 逆映射
        命中**恰好 1** 条合法边 → CLEAR(reference_edge = 该边);
        命中 >1(multi_match)或 0(out_of_menu)→ AMBIGUOUS;
        not validated → AMBIGUOUS(not_validated)。
  禁止:用 episode 终局反推标签;对未来路径之外的选项强行造 label。

runtime_input 与 analysis_only 字段物理分离;prompt 违禁词硬校验。

用法: python scripts/build_stageI0_benchmark.py
产物: analysis/stageI0_router_benchmark.jsonl(+ sha256 打印)
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from analyze_stageH1 import ACTION_FAMILY_PRIMS  # noqa: E402
from rpent.graph.schema import load_graph  # noqa: E402
from rpent.graph.render import NODE_LABELS  # noqa: E402

SRC = REPO / "analysis/stageH_transition_dataset.jsonl"
H0_STATES = REPO / "analysis/stageH0_failure_states.jsonl"
OUT = REPO / "analysis/stageI0_router_benchmark.jsonl"
BANNED = ("fail", "error", "could not", "no object")

# 证据 bullet 的冻结字段序(缺省跳过)
_EVIDENCE_KEYS = ("success", "peak_lift_m", "final_dist_m",
                  "final_gripper_opening", "min_gripper_opening",
                  "consec_move_stall", "release_open",
                  "actions_since_release", "libero_terminated")


def _inv_map():
    inv = collections.defaultdict(set)
    for af, ps in ACTION_FAMILY_PRIMS.items():
        for p in ps:
            inv[p].add(af)
    return inv


def _task_lang(rec):
    """h0 用 runtime_view.task_goal;h1 从 episode states.json init 记录取。"""
    if rec["src"] == "h0":
        return rec["runtime_view"].get("task_goal", "")
    for s in json.load(open(rec["episode_dir"] + "/states.json")):
        if s.get("task_language"):
            return str(s["task_language"])
    return ""


def _evidence_lines(obs: dict) -> list[str]:
    lines = [f"- last primitive: {obs.get('action', 'unknown')}"]
    parts = [f"{k}={obs[k]}" for k in _EVIDENCE_KEYS if k in obs]
    if parts:
        lines.append("  " + ", ".join(parts))
    return lines


def _window_seq(win) -> str:
    """h1 recent_window(obs 列表)→ 'act(k=v) -> act(k=v)'(丢 init 记录)。"""
    seq = []
    for s in win or []:
        a = s.get("action")
        if not a:
            continue
        kv = ", ".join(f"{k}={s[k]}" for k in ("success", "peak_lift_m",
                                               "final_dist_m")
                       if k in s)
        seq.append(f"{a}({kv})" if kv else a)
    return " -> ".join(seq[-4:])


def _prompt(task_lang, family, node, obs, seq, edge_ids, g):
    """冻结模板(I0 资格仪;I1 在线 router prompt 在 stageI_prereg 单独冻结)。"""
    defer = chr(65 + len(edge_ids))
    # 注:词面避免 fail/error 等子串(B2 违禁词红线,router 输出摘要会
    # 回灌 planner 对话);"CURRENT STATE + family" 承载同等信息。
    lines = ["[EDGE-ROUTER] You route a robot to its next strategy.",
             f"Task: {task_lang}",
             f"CURRENT STATE: {node} — {NODE_LABELS.get(node, '')}",
             f"family: {family}",
             "Observable evidence:"]
    lines += _evidence_lines(obs)
    if seq:
        lines.append(f"Recent transitions: {seq}")
    lines.append("Legal recovery options:")
    for lt, eid in zip((chr(65 + i) for i in range(len(edge_ids))), edge_ids):
        e = g.edge(eid)
        lines.append(f"{lt}. [{e.id}] {e.action_family}\n"
                     f"   expected: {e.expected_transition}\n"
                     f"   if expected change absent: {e.falsify}")
    lines.append(f"{defer}. DEFER_TO_PLANNER — return this decision "
                 f"to the main planner.")
    lines.append('Answer with JSON only: {"choice": "<letter>"}')
    return "\n".join(lines), defer


def main():
    g = load_graph()
    inv = _inv_map()
    # h0 primitive_step 回填(turn 字段用)
    h0_step = {}
    for ln in open(H0_STATES):
        p = json.loads(ln)
        h0_step[p["evidence_id"]] = p["primitive_step"]

    samples = []
    stat = collections.Counter()
    for rec in (json.loads(l) for l in open(SRC)):
        edge_ids = rec["legal_edges"]
        node, family = rec["node"], rec["family"]
        if rec["src"] == "h0":
            obs = rec["runtime_view"]["observable_pre_state"]
            seq = ""
            turn = h0_step.get(rec.get("evidence_id"))
            if rec["label"] == "EDGE":
                cls, ref = "CLEAR", rec["correct_set"][0]
                sub = f"h0_edge:{ref}"
            else:
                cls, ref = "AMBIGUOUS", None
                sub = f"h0_defer:{rec.get('label_sub', 'not_validated')}"
        else:
            obs = rec["runtime_view"]["fire_step"]
            seq = _window_seq(rec["runtime_view"]["recent_window"])
            turn = rec["step_idx"]
            if rec["validated_w5"]:
                fams = inv.get(rec["validating_prim"], set())
                hit = [e for e in edge_ids
                       if g.edge(e).action_family in fams]
                if len(hit) == 1:
                    cls, ref, sub = "CLEAR", hit[0], \
                        f"h1_validated:{rec['validating_prim']}"
                elif len(hit) > 1:
                    cls, ref, sub = "AMBIGUOUS", None, "multi_match"
                else:
                    cls, ref, sub = "AMBIGUOUS", None, \
                        f"out_of_menu:{rec['validating_prim']}"
            else:
                cls, ref, sub = "AMBIGUOUS", None, "not_validated"

        task_lang = _task_lang(rec)
        prompt, defer = _prompt(task_lang, family, node, obs, seq,
                                edge_ids, g)
        low = prompt.lower()
        hit_b = [b for b in BANNED if b in low]
        assert not hit_b, f"banned {hit_b} in prompt: {prompt[:200]}"

        sid = f"i0-{len(samples):03d}"
        stat[(cls, family)] += 1
        stat[(cls, sub.split(":")[0])] += 1
        samples.append({
            "sample_id": sid,
            "episode_id": rec.get("evidence_id")
            or Path(rec["episode_dir"]).name,
            "task": rec["task"], "seed": rec["seed"], "turn": turn,
            "failure_family": family, "active_state": node,
            "runtime_input": {
                "task": task_lang, "failure_family": family,
                "active_state": node, "observable_evidence": obs,
                "recent_transition": seq,
                "legal_edges": edge_ids,
                "legal_edge_families": rec["legal_edge_families"],
                "defer_letter": defer, "prompt": prompt,
            },
            "cls": cls,
            "reference_label_type": cls,
            "reference_edge": ref,
            "reference_letter": (chr(65 + edge_ids.index(ref))
                                 if ref in edge_ids else None),
            "ambiguity_sub": sub,
            "analysis_only": {
                "src": rec["src"], "arm": rec.get("arm"),
                "split": rec.get("split"), "episode_sr": rec["episode_sr"],
                "validated_w5": rec.get("validated_w5"),
                "provenance": rec.get("evidence_id")
                or rec.get("episode_dir"),
            },
        })

    with open(OUT, "w") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    n_clear = sum(1 for s in samples if s["cls"] == "CLEAR")
    print(f"wrote {len(samples)} samples -> {OUT}")
    print(f"sha256 = {sha}")
    print(f"CLEAR {n_clear} / AMBIGUOUS {len(samples) - n_clear}")
    print("按 (cls, family):")
    for k, v in sorted(stat.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    sys.exit(main())
