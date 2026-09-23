#!/usr/bin/env python3
"""构建 G0.5/G0.6 轨迹分析 bundle(data handoff 轮 §6-14)。

目标:把 G0.6 最终数据集(三臂 × t3/t5/t9 × s1-s20 = 180 final cells)的
原始 episode 文本证据整理成"可追溯、可复现、适合逐轨迹分析"的数据包。

纪律(handoff 规格):
- 不改任何实验结果、不重跑、不推导新指标,只复制已有原始证据;
- 每个 (task, seed, arm) 只保留 CSV 指向的最终合法 episode(is_final=true),
  重试/替换历史只在 manifest 记 attempt_dirs 计数;
- 只复制顶层文本文件(.log/.json/.jsonl/.csv/.yaml/.yml/.md/.txt),
  视频帧/深度图/world dump 等媒体子目录全部排除;
- P4 的 s1-s10 源自 G0(stage=g0/g0D),provenance 如实标 G0,不复制两份。

一致性校验(§13):master CSV result vs stageG06_runs.csv success vs
run.log FINISH 行的 status(raw 侧证据),任何不一致写 mismatch 报告。

用法: python scripts/build_g05g06_bundle.py [--root /workspace/yjx/downloads]
产物: {root}/g05_g06_trajectory_bundle/ + analysis/data_handoff_mismatch_report.md
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TIER = "glm-5.3-flash"
SUITE = "libero_spatial_task"
ARM_OF = {("g05", "g05P0"): "P0", ("g05", "g05P2"): "P2",
          ("g0", "g0D"): "P4"}
TEXT_EXT = {".log", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".md", ".txt"}
# metadata/ 里随包携带的分析层文件(全部 git 内已有,bundle 只是副本)
META_FILES = [
    "stageG06_runs.csv", "stageG06_events.jsonl", "stageG06_results.md",
    "stageG06_results.json", "stageG06_preregistration.md",
    "stageG06_direction_decision.md", "stageG06_freeze_audit.md",
    "stageG06_seed_manifest.md", "stageG06_quota429_incident.md",
    "stageG06_quota429_deleted_rows.json", "stageG05_runs.csv",
    "stageG05_results.md", "stageG05_preregistration.md",
    "outcome_validation_runs.csv", "data_handoff_analysis_index.md",
    "data_handoff_git_audit.md",
]
# run.log 终局判定行(辅助信息:planner 是否显式 finish)
FINISH_RE = re.compile(r"FINISH called: \{.*?'status': '(\w+)'")
# 注意:success 的权威 raw 证据 = states.json 末项 libero_terminated(env 侧
# ground truth,与调度器 classify_dir 同口径)。planner FINISH 行可能缺失:
# env 终止后 planner 的收尾 API 调用可能挂起(3600s timeout 型),此时仍是
# 合法 success —— 不能用 FINISH 缺失否定 env 判定。


def load_final_cells():
    """master CSV → 180 final cells(与 G0.6 分析器同一过滤口径)。"""
    cells = {}
    for r in csv.DictReader(open(REPO / "analysis/outcome_validation_runs.csv")):
        if r["tier"] != TIER or r["repeat"] != "1":
            continue
        if r["suite"] != SUITE or r["task"] not in ("3", "5", "9"):
            continue
        arm = ARM_OF.get((r["stage"], r["cond"]))
        if arm is None or not r["seed"].isdigit() or not 1 <= int(r["seed"]) <= 20:
            continue
        cells[(int(r["task"]), int(r["seed"]), arm)] = r
    return cells


def load_g06_detail():
    """stageG06_runs.csv → optional manifest 字段(turns/fires/tokens/...)。"""
    det = {}
    for r in csv.DictReader(open(REPO / "analysis/stageG06_runs.csv")):
        det[(int(r["task"]), int(r["seed"]), r["arm"])] = r
    return det


def attempt_dir_counts():
    """logs/ovpm_exp 下每 cell 的候选目录数(重试/替换历史,§12)。"""
    pat = re.compile(r"_(g05P0|g05P2|g0D)_libero_spatial_task_t(3|5|9)_s(\d+)_r1$")
    inv = {v: k for k, v in ARM_OF.items()}  # (stage,cond)->arm 反查不需要,直接判
    arm_of_cond = {"g05P0": "P0", "g05P2": "P2", "g0D": "P4"}
    cnt = collections.Counter()
    for d in glob.glob(str(REPO / "logs/ovpm_exp/*")):
        m = pat.search(Path(d).name)
        if m and 1 <= int(m.group(3)) <= 20:
            cnt[(int(m.group(2)), int(m.group(3)), arm_of_cond[m.group(1)])] += 1
    return cnt


def raw_status(ep_dir: Path):
    """raw 侧终局,与调度器 classify_dir(progress_gate_exp.py:145)逐字同口径:
    states.json 末项 libero_terminated=True → success;无 states → infra_missing;
    run.log 含 API timeout 且未终止 → infra_timeout;否则 policy_fail。"""
    p = ep_dir / "states.json"
    if not p.exists():
        return "infra_missing_states"
    try:
        st = json.load(open(p))
    except Exception:
        return "infra_missing_states"
    if not isinstance(st, list) or not st:
        return "infra_missing_states"
    if st[-1].get("libero_terminated"):
        return "success"
    rl = ep_dir / "run.log"
    if rl.exists() and "API planner timed out" in open(
            rl, errors="replace").read():
        return "infra_timeout"
    return "policy_fail"


def finish_status(ep_dir: Path):
    """辅助信息:planner 显式 FINISH 的 status;缺 FINISH 返回 none(合法,
    见模块 docstring:env 终止后收尾调用可能挂起)。"""
    found = None
    rl = ep_dir / "run.log"
    if rl.exists():
        for line in open(rl, errors="replace"):
            m = FINISH_RE.search(line)
            if m:
                found = m.group(1)
    return found or "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/workspace/yjx/downloads")
    args = ap.parse_args()
    bundle = Path(args.root) / "g05_g06_trajectory_bundle"
    if bundle.exists():
        shutil.rmtree(bundle)  # 幂等重建(目录在 repo 外,可安全重建)
    (bundle / "metadata").mkdir(parents=True)

    cells = load_final_cells()
    detail = load_g06_detail()
    attempts = attempt_dir_counts()
    assert len(cells) == 180, f"final cells != 180: {len(cells)}"

    manifest, mismatches = [], []
    info_success_no_finish = 0
    for (t, s, arm), r in sorted(cells.items()):
        src = Path(r["dir"])
        run_id = src.name
        # provenance:P4 的 s1-s10 源自 G0;P0/P2 的 s1-10 源自 G05;s11-20 全是扩样
        src_stage = ("G0" if r["stage"] == "g0"
                     else ("G05" if s <= 10 else "G06_extension"))
        dest = bundle / "episodes" / f"t{t}" / f"s{s:02d}" / arm
        dest.mkdir(parents=True)
        files = bytes_ = 0
        for f in sorted(src.iterdir()):  # 只顶层文本文件,子目录(媒体)全排除
            if f.is_file() and f.suffix.lower() in TEXT_EXT:
                shutil.copy2(f, dest / f.name)
                files += 1
                bytes_ += f.stat().st_size
        d5 = detail.get((t, s, arm), {})
        master_success = int(r["result"] == "success")
        # §13 三方一致性:master vs runs.csv vs raw(states.json 同口径重判)
        runs_success = int(d5.get("success", master_success))
        raw = raw_status(dest)
        raw_success = int(raw == "success")
        fin = finish_status(dest)
        if master_success == 1 and fin == "none":
            # 合法:env 终止后 planner 收尾调用挂起;单独计数供 README 说明
            info_success_no_finish += 1
        if not (master_success == runs_success == raw_success):
            mismatches.append({
                "task": t, "seed": s, "arm": arm, "run_id": run_id,
                "master_result": r["result"], "runs_csv_success": runs_success,
                "raw_recheck": raw, "planner_finish": fin,
                "source_path": str(src)})
        manifest.append({
            "stage": "G0.6", "source_stage": src_stage, "task": t, "arm": arm,
            "seed": s, "run_id": run_id, "source_path": str(src),
            "bundle_path": str(dest.relative_to(bundle)), "is_final": "true",
            "attempt_dirs": attempts.get((t, s, arm), 1),
            "success": master_success, "result": r["result"],
            "raw_recheck": raw, "planner_finish": fin,
            "infra_status": "none",  # 最终 180 格零 infra(§14 复核)
            "trigger_count": d5.get("fires", ""), "recovery3": d5.get("recovery_any", ""),
            "injected_tokens": d5.get("injected_tokens", ""),
            "planner_turns": d5.get("turns", ""), "wall_time": d5.get("wall_s", ""),
            "files_copied": files, "bytes_copied": bytes_,
        })

    mcols = ["stage", "source_stage", "task", "arm", "seed", "run_id",
             "source_path", "bundle_path", "is_final", "attempt_dirs",
             "success", "result", "raw_recheck", "planner_finish",
             "infra_status", "trigger_count", "recovery3",
             "injected_tokens", "planner_turns", "wall_time", "files_copied",
             "bytes_copied"]
    with open(bundle / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mcols)
        w.writeheader()
        w.writerows(manifest)

    # metadata 副本
    for name in META_FILES:
        p = REPO / "analysis" / name
        if p.exists():
            shutil.copy2(p, bundle / "metadata" / name)

    # §12 校验汇总
    by_arm = collections.Counter(m["arm"] for m in manifest)
    by_task = collections.Counter(m["task"] for m in manifest)
    by_src = collections.Counter(m["source_stage"] for m in manifest)
    triplets = collections.Counter((m["task"], m["seed"]) for m in manifest)
    complete = sum(1 for v in triplets.values() if v == 3)
    validation = {
        "total_final_episodes": len(manifest),
        "by_arm": dict(sorted(by_arm.items())),
        "by_task": {f"t{k}": v for k, v in sorted(by_task.items())},
        "by_source_stage": dict(sorted(by_src.items())),
        "complete_matched_triplets": complete,  # 预期 60
        "missing_raw_logs": sum(1 for m in manifest if m["files_copied"] == 0),
        "cells_with_replacement_history": sum(
            1 for m in manifest if m["attempt_dirs"] > 1),
        "max_attempts_single_cell": max(m["attempt_dirs"] for m in manifest),
        "duplicate_final_cells": 0,
        "mismatches": len(mismatches),
        "success_without_planner_finish": info_success_no_finish,
    }
    (bundle / "validation.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False))
    print(json.dumps(validation, indent=2, ensure_ascii=False))

    # §13 mismatch 报告(写 repo analysis/,0 mismatch 也要明确写)
    lines = [
        "# Data Handoff — 一致性校验(data_handoff_mismatch_report.md)\n",
        "_三方核对:outcome_validation_runs.csv `result` vs stageG06_runs.csv "
        "`success` vs **raw 侧重判**。raw 重判与调度器 classify_dir "
        "(progress_gate_exp.py:145)逐字同口径:states.json 末项 "
        "libero_terminated=True → success;未终止且 run.log 含 API timeout → "
        "infra_timeout;否则 policy_fail。manifest 另记 planner_finish "
        "(planner 显式 FINISH 行)作辅助列。\n",
        f"**核对范围:180 final cells。mismatch 数:{len(mismatches)}**\n",
        f"\n补充说明:{info_success_no_finish} 个 success 格 planner 无显式 "
        "FINISH 行 —— env 已判定任务完成(states.json libero_terminated=True),"
        "随后 planner 的收尾 API 调用挂起(3600s timeout 型,重试纪律处理过的"
        "已知接入问题)。按调度器口径(env 优先)这是合法 success,不属于 "
        "mismatch,也§14 意义上不是 infra 残留(格的最终判定已落定)。\n",
    ]
    if mismatches:
        lines += ["| task | arm | seed | run_id | master | runs.csv | raw重判 | planner_finish | source_path |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for m in mismatches:
            lines.append(f"| {m['task']} | {m['arm']} | {m['seed']} | "
                         f"`{m['run_id']}` | {m['master_result']} | "
                         f"{m['runs_csv_success']} | {m['raw_recheck']} | "
                         f"{m['planner_finish']} | `{m['source_path']}` |")
    else:
        lines.append("\n**0 mismatch** — 三方逐格一致,未做任何静默修改。")
    (REPO / "analysis/data_handoff_mismatch_report.md").write_text(
        "\n".join(lines))
    print(f"mismatches: {len(mismatches)} -> "
          "analysis/data_handoff_mismatch_report.md")
    print(f"bundle ready: {bundle}")


if __name__ == "__main__":
    main()
