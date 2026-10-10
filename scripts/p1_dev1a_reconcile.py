#!/usr/bin/env python3
"""P1-DEV1A 账目回补:把已实际跑完、但因 kill-先于-finalize 而未结账的
episode 用**真实观测值**结账(wall/gpu 来自 run_log episode_measure,
steps 来自事件文件)。不重跑、不释放、不扩容;仅一次性记账修正。

背景(2026-10-10 事故):ep t9_s2001 的 runner 在 probe_done 后立即
killpg,子进程来不及 finalize → episode_end 缺失 → 旧版 _episode_steps
返回 None → runner 按预注册 fail-close STOP。该集本身有效(触发合法、
probe 成本入帽、标签已落),只是账本停在在飞态。本脚本把它按观测值
结账,使剩余 7 集可在同一 manifest/账本下继续(NO_DEV1A_EPISODE_RERUN
由 runs/ 下终止性事件 + runner skip-done 保证)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis" / "research_context"))
sys.path.insert(0, str(REPO))

from p1_dev1a_run import (DurableBudgetLedger, LEDGER_PATH,  # noqa: E402
                          OUT_ROOT, _episode_steps)


def main() -> int:
    run_log = OUT_ROOT / "run_log.jsonl"
    measures = {}
    for line in run_log.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("ev") == "episode_measure":
            measures[e["key"]] = e

    ledger = DurableBudgetLedger(LEDGER_PATH)
    raw = ledger.raw()
    key = raw.get("inflight_key")
    if key is None:
        print("no inflight episode; nothing to reconcile")
        return 0
    if key not in measures:
        sys.exit(f"FATAL: inflight {key} has no episode_measure record")

    m = measures[key]
    audit = OUT_ROOT / "runs" / key
    steps, src = _episode_steps(audit)
    if steps is None:
        sys.exit(f"FATAL: {key} steps unmeasurable ({src}) — refuse to charge")
    if m.get("env_steps") is not None:
        # 旧记录里已有数(此处通常 None,因当时测量失败)
        steps = max(steps, m["env_steps"])
    print(f"reconcile {key}: wall={m['wall_s']} gpu={m['gpu_s']} "
          f"steps={steps} (source={src})")
    ledger.charge_and_close(key, float(m["wall_s"]), float(m["gpu_s"]),
                            int(steps))
    print(json.dumps(DurableBudgetLedger(LEDGER_PATH).raw(),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
