#!/usr/bin/env python
"""Stage L §10 终图冻结 — executable_graph_stageL_final.yaml。

构成 = executable_graph_v1.yaml 冻结边(逐字段原样)+ Round 1/2 晋升候选
(若有)。零晋升时终图 = 冻结图原样,并在 meta 记录 Stage L 演化结果与
provenance(判定 JSON / split_hash / 提交)。产出 graph_hash(规范化序列化
的 sha256 前 16 位)供后续 HELDOUT/报告引用。

用法:python scripts/stageL_freeze_final.py
产物:resources/libero/executable_graph_stageL_final.yaml
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "resources/libero/executable_graph_v1.yaml"
OUT = REPO / "resources/libero/executable_graph_stageL_final.yaml"
SPLIT_HASH = "77695bed7074"   # prereg 冻结值(stageL_split_freeze.py 输出)

# 候选 jsonl → yaml 边 schema 的字段映射(候选无 guard/priority 历史,
# priority 排在族内冻结边之后 = 最大值 +1;fallback/状态字段按家族默认)
_PRIORITY_BASE = {"FALSE_GRASP": 10, "MOVE_CONTACT_STALL": 10,
                  "RELEASE_PREDICATE_STALL": 10}


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
            text=True).strip()
    except Exception:
        return "unknown"


def promoted_edges() -> list[dict]:
    """收集 Round 1/2 判定 PROMOTE 的候选(通常为空)。"""
    out = []
    for rnd in (1, 2):
        p = REPO / f"analysis/stageL_round{rnd}_decisions.json"
        if not p.exists():
            continue
        dec = json.loads(p.read_text())
        cands = {}
        cf = REPO / f"analysis/stageL_candidate_edges_v{'0' if rnd == 1 else '1'}.jsonl"
        for line in open(cf):
            r = json.loads(line)
            if r.get("record_type") != "REJECT":
                cands[r["id"]] = r
        for cid in dec["promoted"]:
            c = cands[cid]
            out.append({
                "id": c["id"],
                "source_state": c["failure_family"],
                "failure_family": c["failure_family"],
                "guard": {},
                "option_id": c.get("option_id", c["id"]),
                "parameterizer": c["parameterizer"],
                "executor": c["executor"],
                "expected_transition": c.get("expected_transition", ""),
                "verifier": {"family": c["failure_family"]},
                "success_state": "DONE",
                "failure_state": c["failure_family"],
                "fallback": None,
                "priority": _PRIORITY_BASE[c["failure_family"]],
                "max_attempts": c.get("max_attempts", 1),
                "stage_l_provenance": {
                    "round": rnd, "source": c.get("source", ""),
                    "source_evidence": c["source_evidence"],
                },
                "status": "active",
            })
    return out


def main() -> int:
    base = yaml.safe_load(open(BASE))
    promoted = promoted_edges()
    final = json.loads(json.dumps(base))     # 深拷贝
    final["edges"].extend(promoted)

    final["meta"] = {
        "version": "stageL_final",
        "frozen_date": "2026-09-30",
        "base_graph": "resources/libero/executable_graph_v1.yaml",
        "families": base["meta"]["families"],
        "selection": base["meta"]["selection"],
        "llm_edge_selection": False,
        "stage_l": {
            "split_hash": SPLIT_HASH,
            "rounds": {"round1": "4/4 REJECT(DEV 584 rollouts)",
                       "round2": None},   # 由下方 decisions 填
            "promoted": [e["id"] for e in promoted] or [],
            "note": ("Stage L verify-to-evolve:零晋升时终图 ≡ 冻结图"
                     "(逐字段),演化判定见 STAGE_L_FINAL_REPORT.md"),
            "git_head_at_freeze": git_head(),
        },
    }
    # round2 判定(若有)写进 meta
    r2 = REPO / "analysis/stageL_round2_decisions.json"
    if r2.exists():
        d = json.loads(r2.read_text())
        final["meta"]["stage_l"]["rounds"]["round2"] = (
            f"{len(d['decisions'])} 候选:"
            + ",".join(f"{k}={v['decision']}"
                       for k, v in d["decisions"].items()))

    graph_hash = hashlib.sha256(
        json.dumps(final, sort_keys=True, ensure_ascii=False)
        .encode()).hexdigest()[:16]
    final["meta"]["graph_hash"] = graph_hash

    header = (
        "# Stage L — Executable Graph FINAL(2026-09-30 冻结)\n"
        "#\n"
        "# 构成 = executable_graph_v1.yaml 冻结边(逐字段原样)+ Stage L\n"
        "# Round 1/2 双验证晋升候选(meta.stage_l.promoted;零晋升时 ≡ 冻结图)。\n"
        "# 冻结纪律与 v1 相同:guard 只用 runtime observable;executor 只用\n"
        "# 已注册原语;确定性 priority 选择;零 LLM 边选择。\n\n")
    OUT.write_text(header + yaml.safe_dump(
        final, allow_unicode=True, sort_keys=False, width=100))
    print(f"[freeze] promoted={len(promoted)} {[' + '.join(e['id'] for e in promoted)] or '(终图=冻结图)'}")
    print(f"[freeze] graph_hash={graph_hash}")
    print(f"[freeze] -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
