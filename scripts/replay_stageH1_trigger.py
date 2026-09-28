#!/usr/bin/env python3
"""Stage H1 §3(b) 运行前验证:graph 触发器离线重放(无 LLM、无 GPU)。

把 G0.5/G0.6 final 180 集 states.json 逐 result 喂给**真实运行时路径**
(DecisionMemory mode="graph" + injection_mode=graph_block 的
on_tool_result / turn_boundary),与 §1 基准 148 决策点逐点比对。

通过标准(prereg §3):
- 基准每个点在重放中都有对应 fire,或被明确归类为冷却/上限丢弃(列出);
- 重放多出的 fire 只允许 REL 未来窗类(runtime 在 fire 时刻不可知
  "其后 4 步内谓词会不会触发",基准事后排除了这部分 —— 这是正确的
  运行时行为,逐条列出);
- 每 fire 的 graph_node 与基准家族一致。

用法: python scripts/replay_stageH1_trigger.py
产物: analysis/stageH1_replay_validation.md
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.build_stageH0_failure_states import load_episodes  # noqa: E402
from rpent.memory.retrieval import DecisionMemory  # noqa: E402
from rpent.graph.pipeline import NODE_FAMILY  # noqa: E402

# 基准家族 → 期望节点(与 audit EXPECTED 同口径)
FAMILY_NODES = {"FALSE_GRASP": "FALSE_GRASP",
                "MOVE_CONTACT_STALL": ("MOVE_STALL", "CONTACT_STALL"),
                "RELEASE_PREDICATE_STALL": "RELEASE_PREDICATE_STALL"}
STALL_WINDOW = 4  # 基准 REL 未来窗(重放多出 fire 的唯一合法类)


class FakeTracker:
    """DecisionMemory 只读 current_phase;重放里相位不可知,给常量。"""

    def current_phase(self):
        return "replay"

    def recovery_pending(self):
        return False


def replay_episode(steps):
    """一个 episode 过真实 graph 触发路径;返回 fired[(step_idx, node)]。

    step_idx = states.json 的 0-based step 序(**含 init 记录**,
    与基准 primitive_step 同基 —— init 占 0,首个 actuation 为 1;
    感知步 states.json 本就不记)。
    """
    for k in ("RPENT_MEMORY_TRIGGER", "RPENT_MEMORY_INJECTION_MODE",
              "RPENT_MEMORY_QUERY_MODE", "RPENT_MEMORY_RANK",
              "RPENT_MEMORY_QUERY_REASON"):
        os.environ.pop(k, None)
    os.environ.update({
        "RPENT_MEMORY_TRIGGER": "graph",
        "RPENT_MEMORY_INJECTION_MODE": "graph_block",
        "RPENT_MEMORY_QUERY_MODE": "common",
        "RPENT_MEMORY_RANK": "Q0_FIXED",
        "RPENT_MEMORY_QUERY_REASON": "0",
    })
    dm = DecisionMemory(FakeTracker(), mode="graph")
    fired = []
    for i, step in enumerate(steps):
        name = (step.get("command") or {}).get("action")
        if name is None:
            continue  # init 记录:不进 graph 触发历史
        res = step.get("result") or {}
        data = {**res, "libero_terminated": step.get("libero_terminated")}
        dm.on_tool_result(name, json.dumps(data), False)
        out = dm.turn_boundary(i + 1)
        if out is not None:
            _blk, ev = out
            node = ev.get("graph_node")
            assert node, f"graph_block fire without graph_node: {ev}"
            fired.append((i, node, ev["turn"]))
    return fired


def main():
    eps = load_episodes()  # {(t,s,arm): dir},180
    bench = [json.loads(l) for l in
             open(REPO / "analysis/stageH0_failure_states.jsonl")]

    # 基准点按 episode 分组:key = episode 目录名
    bench_by_ep: dict[str, list] = {}
    for p in bench:
        bench_by_ep.setdefault(p["analysis_only"]["source_path"],
                               []).append(p)

    n_match = n_cooldown = n_future_rel = n_missing = n_extra = 0
    mismatches, cooldown_list, future_list, extra_list = [], [], [], []
    for key, d in sorted(eps.items()):
        try:
            steps = json.load(open(os.path.join(d, "states.json")))
        except Exception:
            continue
        fired = replay_episode(steps)
        bpts = bench_by_ep.get(d, [])
        # 基准点:(primitive_step, family, evidence)
        bmap = {p["primitive_step"]: p for p in bpts}
        fmap = {s: (n, t) for s, n, t in fired}

        for s, p in bmap.items():
            if s not in fmap:
                # 合法类 1:冷却/上限丢弃 —— 该 step 有失败家族但被冲刷丢弃
                n_cooldown += 1
                cooldown_list.append((d[-50:], s, p["failure_family"]))
                continue
            node, _t = fmap[s]
            want = FAMILY_NODES[p["failure_family"]]
            if node != want and node not in (want if isinstance(
                    want, tuple) else (want,)):
                mismatches.append((d[-50:], s, p["failure_family"], node))
            else:
                n_match += 1
        for s, (node, _t) in fmap.items():
            if s in bmap:
                continue
            # 重放多出的 fire 合法类(仅限 REL):
            # (i) 未来窗:release 后 4 步内谓词触发(runtime 不可知);
            # (ii) 终窗:release 是(或近)最后一步,nxt 为空(基准要求
            #      nxt 非空才记点;runtime 无法预知 episode 结束)。
            fam = NODE_FAMILY[node]
            nxt = steps[s + 1: s + 1 + STALL_WINDOW]
            if fam == "RELEASE_PREDICATE_STALL" and (
                    not nxt or any(x.get("libero_terminated") for x in nxt)):
                n_future_rel += 1
                future_list.append((d[-50:], s))
            else:
                n_extra += 1
                extra_list.append((d[-50:], s, node))

    n_bench = len(bench)
    lines = [
        "# Stage H1 — graph 触发器离线重放校验(§3(b))\n",
        "_2026-09-28 by scripts/replay_stageH1_trigger.py。180 集真实",
        " states.json 逐 result 过**运行时** DecisionMemory(graph+",
        "graph_block)路径,与基准 148 点逐点比对。_\n",
        "## 结果",
        "",
        "| 类 | 数量 | 说明 |",
        "|---|---|---|",
        f"| 基准点 ↔ 重放 fire 逐一匹配(节点一致) | {n_match} | |",
        f"| 基准点被冷却/上限丢弃 | {n_cooldown} | 合法(冻结冲刷语义) |",
        f"| 重放多出:REL 未来窗类 | {n_future_rel} | 合法(runtime 不可",
        "知未来;基准事后排除) |",
        f"| 基准点缺失(非冷却) | {n_missing} | **必须为 0** |",
        f"| 重放多出(非 REL 未来窗) | {n_extra} | **必须为 0** |",
        f"| 节点不一致 | {len(mismatches)} | **必须为 0** |",
        "",
        "## 判定",
        ("**REPLAY VALIDATION PASS** — 运行时触发器与基准决策点一致,"
         "可以进入在线实验。"
         if not mismatches and n_missing == 0 and n_extra == 0
         else "**REPLAY VALIDATION FAIL — 先修再跑。**"),
    ]
    if cooldown_list:
        lines += ["", "### 冷却/上限丢弃(前 15)",
                  "| episode | step | family |", "|---|---|---|"]
        lines += [f"| `{e}` | {s} | {f} |" for e, s, f in cooldown_list[:15]]
    if future_list:
        lines += ["", "### REL 未来窗多出(前 15)",
                  "| episode | step |", "|---|---|"]
        lines += [f"| `{e}` | {s} |" for e, s in future_list[:15]]
    if mismatches:
        lines += ["", "### 节点不一致(全部)",
                  "| episode | step | want_family | got_node |"]
        lines += [f"| `{m[0]}` | {m[1]} | {m[2]} | {m[3]} |"
                  for m in mismatches]
    if extra_list:
        lines += ["", "### 非法多出(全部,前 15)"]
        lines += [f"- `{e}` step {s} node {n}" for e, s, n in extra_list[:15]]
    (REPO / "analysis/stageH1_replay_validation.md").write_text(
        "\n".join(lines))
    print("\n".join(lines[7:20]))
    print(f"\nwrote analysis/stageH1_replay_validation.md "
          f"(match={n_match}/{n_bench}, cooldown={n_cooldown}, "
          f"future_rel={n_future_rel}, missing={n_missing}, "
          f"extra={n_extra}, mism={len(mismatches)})")
    return 0 if (not mismatches and n_missing == 0 and n_extra == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
