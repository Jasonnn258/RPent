#!/usr/bin/env python3
"""P1-DEV0 结果分析:四臂触发/成本/outcome 可测性 + 消融账目(只读事件文件)。

DEV0 第一终点是工程可行性,不是确证性统计。本脚本产出:
- M1 分母账:总 episode / 触发 / 未触发(ITT 保留)/ infra-censored;
- M2 触发层:arm×task 触发计数、触发时 env steps、pick 结果摘要;
- M3 成本层:probe/action env steps 与墙钟分布(按臂);
- M4 决策层:rationale_code 分布、abstain 回落计数;
- M5 outcome 可测性:audit 覆盖率(FIXED_HORIZON vs EPISODE_END)、
  overshoot 分布、audit check_success 按 arm×action_kind 交叉表
  (描述性,不做显著性检验);
- M6 执行完整性:hook_error 计数、episode_end 缺失清单、step 编号
  连续性抽查(重试步 = 触发步 + 1,探测不占步号);
- M7 隔离审计:事件文件位置在 episode output_dir 之外的断言、
  非 audit 事件中特权键扫描。

用法:
  python scripts/p1_dev0_analyze.py --out-root /workspace/yjx/rpent_data/p1_dev0 \
      [--manifest artifacts/p1_dev0/manifest.jsonl] [--write artifacts/p1_dev0_analysis.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 与 policy/审计事件一致的特权键(p1_dev0_policy.deny_privileged_payload)
FORBIDDEN_KEYS = {
    "check_success", "obj_of_interest", "research_audit_truth",
    "reference", "reference_state", "stable_fg", "acquisition",
    "reconstruction_metadata", "sim_measurement", "target_pos",
    "object_world_pos",
}


def load_manifest(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def load_events(out_root: Path, key: str) -> list[dict]:
    f = out_root / "runs" / key / "p1_dev0_events.jsonl"
    if not f.is_file():
        return []
    evs = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            evs.append(json.loads(line))
        except Exception:
            pass
    # 多次启动(infra 重跑)时取最后一次 init 之后的段落
    last_init = max((i for i, e in enumerate(evs) if e.get("ev") == "init"),
                    default=-1)
    return evs[last_init:] if last_init >= 0 else evs


def episode_output_dirs(out_root: Path, key: str) -> list[Path]:
    return sorted(out_root.glob(f"runs/{key}_2*"))


def analyze(out_root: Path, manifest: list[dict]) -> dict:
    rows = []
    for m in manifest:
        key = m["episode_key"]
        evs = load_events(out_root, key)
        by = defaultdict(list)
        for e in evs:
            by[e.get("ev")].append(e)
        ep_dirs = episode_output_dirs(out_root, key)
        row = {
            "episode_key": key, "task": m["task"], "seed": m["seed"],
            "arm": m["arm"],
            "has_events": bool(evs),
            "n_inits": len(by.get("init", [])),
            "triggered": bool(by.get("trigger")),
            "episode_end": bool(by.get("episode_end")),
            "hook_errors": len(by.get("hook_error", [])),
        }
        if by.get("trigger"):
            tr = by["trigger"][-1]
            row["trigger_env_steps"] = tr.get("env_steps")
            row["trigger_step_idx"] = tr.get("step_idx")
            row["pick_success"] = (tr.get("pick_result") or {}).get("success")
            row["pre_legal_ok"] = tr.get("pre_legal") is not None
            row["pre_images_found"] = sum(
                1 for im in (tr.get("pre_images") or [])
                if not im.get("missing"))
        if by.get("probe"):
            pr = by["probe"][-1]
            row["probe_env_steps"] = pr.get("env_steps_cost")
            row["probe_wall_s"] = pr.get("wall_s")
            row["probe_post_legal_ok"] = pr.get("post_legal") is not None
            row["probe_frames"] = sum(
                1 for f in (pr.get("post_frames") or []) if f.get("sha256"))
        if by.get("decision"):
            de = by["decision"][-1]
            row["decision"] = de.get("decision")
            row["rationale_code"] = de.get("rationale_code")
            row["policy_sha256"] = de.get("policy_sha256")
        if by.get("action"):
            ac = by["action"][-1]
            row["action_kind"] = ac.get("kind")
            row["abstain_fallback"] = ac.get("abstain_fallback")
            row["action_env_steps"] = ac.get("env_steps_cost")
            row["action_wall_s"] = ac.get("wall_s")
            row["retry_success"] = ((ac.get("retry_result_summary") or {})
                                    .get("success"))
            # M6 步号连续性:重试步 = 触发步 + 1(探测不占 toolkit 步号)
            if row.get("trigger_step_idx") is not None and \
                    ac.get("retry_step_idx") is not None:
                row["retry_step_delta"] = (ac["retry_step_idx"]
                                           - row["trigger_step_idx"])
        if by.get("audit"):
            au = by["audit"][-1]
            row["audit_kind"] = au.get("kind")
            row["audit_overshoot"] = au.get("overshoot_env_steps")
            row["audit_check_success"] = (au.get("audit_only") or {}).get(
                "check_success")
            row["audit_has_sim_meas"] = "sim_measurement_obs" in (
                au.get("audit_only") or {})
        if by.get("episode_end"):
            en = by["episode_end"][-1]
            row["env_steps_total"] = en.get("env_steps_total")
        # M7 隔离:事件文件在 episode output_dir 之外
        ev_file = out_root / "runs" / key / "p1_dev0_events.jsonl"
        row["events_outside_output_dir"] = bool(ep_dirs) and all(
            ev_file not in d.parents and d not in ev_file.parents
            for d in ep_dirs)
        rows.append(row)

    # ---- 聚合 ----
    def sel(**kw):
        return [r for r in rows
                if all(r.get(k) == v for k, v in kw.items())]

    total = len(rows)
    triggered = sel(triggered=True)
    m1 = {
        "total_episodes": total,
        "with_events": sum(1 for r in rows if r["has_events"]),
        "triggered": len(triggered),
        "untriggered_itt": sum(1 for r in rows
                               if r["has_events"] and not r["triggered"]),
        "no_events_infra": sum(1 for r in rows if not r["has_events"]),
        "censored_no_end": sum(1 for r in rows
                               if r["triggered"] and not r["episode_end"]),
        "hook_errors_total": sum(r["hook_errors"] for r in rows),
    }
    m2 = {}
    for arm in ("D0", "D1", "D2", "D3"):
        for task in (3, 5, 9):
            s = sel(arm=arm, task=task)
            m2[f"{arm}_t{task}"] = {
                "n": len(s), "triggered": sum(1 for r in s if r["triggered"])}
    m3 = {}
    for arm in ("D0", "D1", "D2", "D3"):
        s = [r for r in sel(arm=arm, triggered=True)]
        m3[arm] = {
            "probe_env_steps": Counter(
                r.get("probe_env_steps") for r in s if
                r.get("probe_env_steps") is not None),
            "action_env_steps": Counter(
                r.get("action_env_steps") for r in s if
                r.get("action_env_steps") is not None),
            "wall_s_mean": _mean([r.get("action_wall_s") for r in s]),
        }
    m4 = {
        "rationale_codes": Counter(r.get("rationale_code")
                                   for r in triggered),
        "decisions": Counter(r.get("decision") for r in triggered),
        "abstain_fallbacks": sum(1 for r in triggered
                                 if r.get("abstain_fallback")),
        "retry_successes": Counter(r.get("retry_success") for r in triggered
                                   if r.get("action_kind") == "RETRY"),
    }
    m5 = {
        "audit_coverage": {
            "triggered": len(triggered),
            "audited": sum(1 for r in triggered if r.get("audit_kind")),
            "fixed_horizon": sum(1 for r in triggered
                                 if r.get("audit_kind") == "FIXED_HORIZON"),
            "episode_end_fallback": sum(1 for r in triggered
                                        if r.get("audit_kind")
                                        == "EPISODE_END"),
            "unaudited": sum(1 for r in triggered
                             if not r.get("audit_kind")),
            "has_sim_measurement": sum(1 for r in triggered
                                       if r.get("audit_has_sim_meas")),
        },
        "overshoot_env_steps": [r.get("audit_overshoot") for r in triggered
                                if r.get("audit_kind") == "FIXED_HORIZON"],
        "audit_cross_arm_action": {
            f"{a}/{k}": {
                "n": len(s := [r for r in triggered
                               if r.get("arm") == a
                               and r.get("action_kind") == k]),
                "check_success_true": sum(
                    1 for r in s if r.get("audit_check_success") is True),
                "check_success_false": sum(
                    1 for r in s if r.get("audit_check_success") is False),
            }
            for a in ("D0", "D1", "D2", "D3")
            for k in ("RETRY", "CONTINUE_CAUTION")
            if [r for r in triggered
                if r.get("arm") == a and r.get("action_kind") == k]
        },
    }
    m6 = {
        "retry_step_delta_counter": Counter(
            r.get("retry_step_delta") for r in rows
            if r.get("retry_step_delta") is not None),
        "episode_end_missing": [r["episode_key"] for r in rows
                                if r["has_events"] and not r["episode_end"]],
        "policy_sha256_unique": sorted({
            r["policy_sha256"] for r in rows if r.get("policy_sha256")}),
        "events_outside_output_dir_all_ok": all(
            r["events_outside_output_dir"] for r in rows if r["has_events"]),
    }
    # M7 特权键扫描:非 audit 事件文本里不得出现 "forbidden_key":
    leaked = []
    for m in manifest:
        evs = load_events(out_root, m["episode_key"])
        for e in evs:
            if e.get("ev") == "audit":
                continue
            text = json.dumps(e, ensure_ascii=False)
            for k in FORBIDDEN_KEYS:
                if f'"{k}"' in text:
                    leaked.append({"episode_key": m["episode_key"],
                                   "ev": e.get("ev"), "key": k})
    m7 = {"privileged_key_leaks_outside_audit": leaked,
          "leak_count": len(leaked)}
    return {"m1_denominator": m1, "m2_trigger_by_arm_task": m2,
            "m3_costs": {k: {kk: (dict(vv) if isinstance(vv, Counter)
                                  else vv)
                             for kk, vv in v.items()}
                         for k, v in m3.items()},
            "m4_decisions": {k: (dict(v) if isinstance(v, Counter) else v)
                             for k, v in m4.items()},
            "m5_outcome_measurability": m5, "m6_integrity": m6,
            "m7_isolation": m7,
            "rows": rows}


def _mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 3) if xs else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", type=Path,
                    default=Path("/workspace/yjx/rpent_data/p1_dev0"))
    ap.add_argument("--manifest", type=Path,
                    default=REPO / "artifacts" / "p1_dev0" / "manifest.jsonl")
    ap.add_argument("--write", type=Path, default=None)
    args = ap.parse_args()
    manifest = load_manifest(args.manifest)
    result = analyze(args.out_root, manifest)
    out = json.dumps(result, ensure_ascii=False, indent=1,
                     default=lambda o: dict(o) if isinstance(o, Counter)
                     else str(o))
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(out + "\n")
        print(f"[p1_dev0_analyze] written: {args.write}")
    # 控制台摘要(白话)
    m1, m5, m7 = result["m1_denominator"], result["m5_outcome_measurability"], result["m7_isolation"]
    print(f"episodes={m1['total_episodes']} with_events={m1['with_events']} "
          f"triggered={m1['triggered']} untriggered(ITT)={m1['untriggered_itt']} "
          f"infra={m1['no_events_infra']} censored={m1['censored_no_end']} "
          f"hook_errors={m1['hook_errors_total']}")
    print(f"audit: {m5['audit_coverage']}")
    print(f"leaks={m7['leak_count']} "
          f"events_outside_output_dir_ok={result['m6_integrity']['events_outside_output_dir_all_ok']}")
    for k, v in result["m4_decisions"]["rationale_codes"].items():
        print(f"  rationale {k}: {v}")
    for k, v in result["m5_outcome_measurability"]["audit_cross_arm_action"].items():
        print(f"  audit {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
