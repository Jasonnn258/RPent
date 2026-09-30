#!/usr/bin/env python
"""Stage L §11 — Round 2 最小修复候选(v1)。

Round 1 全 REJECT 后,按取证证据生成 v1:仅当存在**证据支持的**最小修复
(参数化修正 / 插入既有解析步 / 删除无效步 / 重排组合)才升级 v1 候选;
否则 REJECTED 终态。取证数字全部从 logs/stageL_round1/rollouts.jsonl
机械重导(不手抄)。

判定依据(2026-09-30 取证):
- LC-FG-1/2:快照态 SAM3 分数 0.014–0.044(阈值 0.2)——降 min_score 至 0.1
  仍全部 found=False,非"阈值过严"而是 TASK_LANG 分割不出目标;删感知步
  则路点无可导来源,剩余结构退化为 FG-2/FG-3 近重复 → 无修复,终态。
- LC-RS-2:LAST_PICK_PROMPT/TASK_LANG 均指向原抓取位置(炉子),RPS 态物体
  已在盘边 → 抓取飞向错误位置横扫(max_obj_xy 0.051–0.073 判 HARM);
  冻结绑定词表无法表达"当前位置"短 prompt → 无修复,终态。
- LC-RS-1:retreat(+0.114) 后 pi0_doubled 40/40 烧满 20 chunks 且
  d_ooi_z≡0(从未接触物体)——从 11cm 高处出发 chunk 预算耗尽在接近上。
  挖矿唯一 TASK_LANG-doubled 成功(t9s6)在 retreat 与 doubled 之间插了
  下降步(move_pose z=fire−0.011, 开爪)→ 修复 = 插入既有解析步
  move_to(${eef}, gripper=1) 回到 fire 位姿开爪,使 doubled 近距出发。

用法:python scripts/stageL_repair_candidates.py
产物:analysis/stageL_candidate_edges_v1.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stageL_compile_candidates import RAW_BINDINGS, TOOLS  # noqa: E402
from stagek_graph_executor import _eval_expr  # noqa: E402

V0 = REPO / "analysis/stageL_candidate_edges_v0.jsonl"
ROLL1 = REPO / "logs/stageL_round1/rollouts.jsonl"
OUT = REPO / "analysis/stageL_candidate_edges_v1.jsonl"


def forensic(round1: list[dict]) -> dict:
    """从 Round 1 rollout 机械重导取证数字(修复理由的证据锚)。"""
    fg = [r for r in round1 if r.get("edge_id") == "LC-FG-1" and r.get("chain")]
    seg_scores = [c["result"].get("score") for r in fg
                  for c in r["chain"] if c["tool"] == "segment"
                  and c["result"].get("score") is not None]
    rs1 = [r for r in round1 if r.get("edge_id") == "LC-RS-1"
           and r.get("outcome")]
    full_chunks = sum(
        1 for r in rs1
        for c in r["chain"] if c["tool"] == "pi0_doubled"
        and c["result"].get("chunks_used") == 20)
    no_move = sum(1 for r in rs1
                  if abs((r.get("verify") or {}).get("d_ooi_z") or 0) <= 1e-9)
    rs2h = [r for r in round1 if r.get("edge_id") == "LC-RS-2"
            and r.get("outcome") == "HARM"]
    swept = [round((r.get("verify") or {}).get("max_obj_xy") or 0, 3)
             for r in rs2h]
    return {
        "fg_seg_score_min": round(min(seg_scores), 3),
        "fg_seg_score_max": round(max(seg_scores), 3),
        "rs1_doubled_full_chunks": full_chunks,
        "rs1_n_rollouts": len(rs1),
        "rs1_object_never_moved": no_move,
        "rs2_harm_swept_max_obj_xy": swept,
    }


def check_compilable(cand: dict) -> list[str]:
    """静态可编译检查:工具/绑定/表达式全部落在冻结词表内。"""
    problems = []
    for s in cand["executor"]:
        if s["tool"] not in TOOLS:
            problems.append(f"工具 {s['tool']} 不在 executor 词表")
    names = {"eef": [0, 0, 0], "obj": [0, 0, 0]}
    for raw in cand["parameterizer"]["bindings"].values():
        if raw in RAW_BINDINGS:
            continue
        if isinstance(raw, str) and raw.strip().startswith("["):
            try:
                _eval_expr(raw, names)
            except Exception as exc:
                problems.append(f"表达式 {raw!r} 不可解析: {exc}")
        else:
            problems.append(f"绑定 {raw!r} 不在冻结词表")
    return problems


def main() -> int:
    v0 = {r["id"]: r for r in map(json.loads, open(V0))
          if r.get("record_type") != "REJECT"}
    round1 = [json.loads(x) for x in open(ROLL1)]
    ev = forensic(round1)

    # ---- 修复候选:LC-RS-1R(LC-RS-1 + 插入下降步)------------------------
    rs1 = json.loads(json.dumps(v0["LC-RS-1"]))   # 深拷贝,其余字段原样
    rs1["id"] = "LC-RS-1R"
    rs1["source"] = ("B(merge:垂直撤退 × 下降回位 × pi0_doubled 重试)"
                     "| Round2 最小修复:插入既有解析步")
    rs1["repair_of"] = "LC-RS-1"
    rs1["repair_rationale"] = (
        "Round1 取证:doubled {rs1_doubled_full_chunks}/{rs1_n_rollouts} 烧满 20 "
        "chunks 且 {rs1_object_never_moved}/{rs1_n_rollouts} d_ooi_z≡0(从 "
        "retreat 后 11cm 高处出发,预算耗尽在接近、从未接触物体);挖矿唯一 "
        "TASK_LANG-doubled 成功 t9s6 在 doubled 前有下降步(move_pose z≈fire,"
        " 开爪)→ 插入 move_to(${{eef}}, gripper=1) 回 fire 位姿开爪"
    ).format(**ev)
    rs1["executor"] = [
        rs1["executor"][0],                        # retreat(+0.114, 闭爪)原样
        {                                          # 新插入:回 fire 位姿、开爪
            "tool": "move_to",
            "args": {"xyz": "${eef}", "gripper": 1.0, "max_steps": 40},
        },
        rs1["executor"][1],                        # pi0_doubled(TASK_LANG)原样
    ]
    problems = check_compilable(rs1)
    if problems:
        print("[repair] LC-RS-1R 不可编译:", problems)
        return 1

    # ---- 终态 REJECT(无证据支持的修复)------------------------------------
    rejects = [
        {"record_type": "REJECT", "id": "LC-FG-1", "round": 2, "terminal": True,
         "reason": "repair_infeasible_perception_dead",
         "evidence": (
             "快照态 SAM3 分数 {fg_seg_score_min}–{fg_seg_score_max}(阈值 0.2):"
             "降 min_score 至 0.1 仍全 found=False,非阈值问题;删感知步则"
             "路点无可导来源(挖矿成功路点为 planner 字面知识,非 eef/obj 可导),"
             "剩余结构退化为 FG-2/FG-3 近重复").format(**ev),
         "allowed_ops_assessed": ["参数化修正", "删除无效步"]},
        {"record_type": "REJECT", "id": "LC-FG-2", "round": 2, "terminal": True,
         "reason": "repair_infeasible_perception_dead",
         "evidence": "同 LC-FG-1(感知链与其等价,OFFSET_SUFFIX 合并无差别)",
         "allowed_ops_assessed": ["参数化修正", "删除无效步"]},
        {"record_type": "REJECT", "id": "LC-RS-2", "round": 2, "terminal": True,
         "reason": "repair_infeasible_prompt_location",
         "evidence": (
             "HARM 机制 = 抓取飞向错误位置横扫(max_obj_xy {swept});"
             "LAST_PICK_PROMPT/TASK_LANG 均指向原抓取位置,RPS 态物体已在盘边,"
             "冻结绑定词表无『当前位置』短 prompt 变换(挖矿成功用 "
             "'pick up the bowl on the plate' 类短 prompt,不可编译)"
         ).format(swept=ev["rs2_harm_swept_max_obj_xy"]),
         "allowed_ops_assessed": ["参数化修正", "插入既有解析步", "删除无效步"]},
    ]

    with open(OUT, "w") as f:
        f.write(json.dumps(rs1, ensure_ascii=False) + "\n")
        for r in rejects:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[repair] v1 -> {OUT}")
    print(f"  候选:LC-RS-1R(修复 LC-RS-1,插入下降步)")
    print(f"  终态 REJECT:LC-FG-1, LC-FG-2, LC-RS-2")
    print(f"  取证锚:{json.dumps(ev, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
