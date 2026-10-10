#!/usr/bin/env python3
"""P1-DEV1A pilot 汇总:只产聚合指标,不落任何私有明细。

数据源(全部只读):
- artifacts/p1_dev1a/run_log.jsonl        runner 侧每集墙钟/GPU/步数/终止方式
- artifacts/p1_dev1a/budget_ledger.json   最终预算账本
- artifacts/p1_dev1a/runs/<key>/p1_dev1a_events.jsonl   每集审计事件

输出(聚合,可入报告):
- 每集:触发与否、probe 步数成本、CONTACT 分布(BILATERAL/SINGLE/NONE/UNKNOWN,
  取 t_close_end 时刻)、RETAINED 分布、快照 same_tick 合格率、快照成本
- 总量:真实新 episode 数、墙钟/GPU 合计、触发率、各分布计数
详细快照(geom 对、位姿)留在 artifacts/ 下不入库。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "artifacts" / "p1_dev1a"


def _events(key: str) -> list[dict]:
    f = ROOT / "runs" / key / "p1_dev1a_events.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def main() -> int:
    run_log = ROOT / "run_log.jsonl"
    rows = []
    if run_log.is_file():
        for line in run_log.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("ev") == "episode_measure":
                rows.append(e)

    per_episode = []
    contact_dist = Counter()
    retention_dist = Counter()
    trig = Counter()
    same_tick_total = same_tick_ok = 0
    snap_cost_ms = []

    for r in rows:
        key = r["key"]
        evs = _events(key)
        probe = next((e for e in evs if e.get("ev") == "probe"), None)
        end = next((e for e in reversed(evs)
                    if e.get("ev") == "episode_end"), None)
        item = {
            "key": key,
            "wall_s": r.get("wall_s"),
            "gpu_s": r.get("gpu_s"),
            "env_steps_runner": r.get("env_steps"),
            "steps_source": r.get("steps_source"),
            "terminated_by": r.get("terminated_by"),
            "subprocess_rc": r.get("subprocess_rc"),
            "triggered": probe is not None,
        }
        if probe:
            labels = probe.get("labels", {})
            cc = labels.get("close_contact", {})
            contact_dist[cc.get("contact", "MISSING")] += 1
            retention_dist[labels.get("retention", {}).get(
                "retained", "MISSING")] += 1
            item.update({
                "trigger_step": probe.get("trigger_env_step"),
                "probe_env_steps_cost": probe.get("env_steps_cost"),
                "close_contact": cc.get("contact"),
                "close_supported": cc.get("supported"),
                "retention": labels.get("retention", {}).get("retained"),
                "retention_reason": labels.get("retention", {}).get("reason"),
                "eef_dz_m": probe.get("eef_dz_m"),
                "obj_dz_m": probe.get("obj_dz_m"),
            })
            snaps = probe.get("audit_snapshots", {})
            seq = [snaps.get("t_trigger"), snaps.get("t_close_end")]
            seq += [s.get("snap") for s in snaps.get("lift_samples", [])]
            seq.append(snaps.get("t_lift_end"))
            for s in filter(None, seq):
                same_tick_total += 1
                same_tick_ok += bool(s.get("server_same_tick"))
                for k in ("rpc_wall_ms", "wall_ms"):
                    if isinstance(s.get(k), (int, float)):
                        snap_cost_ms.append(float(s[k]))
                        break
        if end:
            item["episode_end_cap_ok"] = end.get("cap_ok")
            item["env_steps_hook"] = end.get("env_steps_total")
        per_episode.append(item)
        trig["triggered" if probe else "no_trigger"] += 1

    ledger_f = ROOT / "budget_ledger.json"
    ledger = json.loads(ledger_f.read_text(encoding="utf-8")) \
        if ledger_f.is_file() else None

    summary = {
        "protocol": "D-041",
        "episodes_total": len(rows),
        "trigger_counter": dict(trig),
        "contact_dist": dict(contact_dist),
        "retention_dist": dict(retention_dist),
        "snapshot_same_tick": {"ok": same_tick_ok, "total": same_tick_total},
        "snapshot_cost_ms_avg": (round(sum(snap_cost_ms) / len(snap_cost_ms), 2)
                                 if snap_cost_ms else None),
        "wall_s_total": round(sum(r.get("wall_s") or 0 for r in rows), 1),
        "gpu_s_total": round(sum(r.get("gpu_s") or 0 for r in rows), 1),
        "env_steps_max": max((r.get("env_steps") or 0 for r in rows),
                             default=None),
        "ledger_final": ledger,
        "per_episode": per_episode,
    }
    out = ROOT / "pilot_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    # 控制台只打聚合(不含每集标签细目,防泄漏到日志)
    safe = {k: v for k, v in summary.items() if k != "per_episode"}
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    print(f"[summarize] -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
