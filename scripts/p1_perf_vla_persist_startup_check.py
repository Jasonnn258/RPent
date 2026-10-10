#!/usr/bin/env python3
"""persistent-VLA 修复的真实端到端验证(Phase D;GPU0,~3min,零 episode)。

背景(2026-10-10 性能轮 B2 修复):_start_persistent_vla 原实现调用不存在的
cli.healthz(...),AttributeError 被 except Exception 吞成"恒未就绪",
--persistent-vla 从未能启动;修正为 call("healthz")。本脚本用**真实**
vla_server(Pi0.5 加载 ~78s)验证修复闭环:

1. _start_persistent_vla 能在 healthz 就绪后正常返回(不再 240s 超时 FATAL);
2. 就绪后 _persistent_vla_alive(集间探活)为 True;
3. 故障注入:SIGKILL 服务进程 → 探活必须立刻 False(集间守卫的触发条件);
4. finally 清扫无残留组。

输出 artifacts/p1_perf/vla_persist_startup_check.json(私有)。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "artifacts" / "p1_perf"

spec = importlib.util.spec_from_file_location(
    "p1_dev1a_run", REPO / "scripts" / "p1_dev1a_run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _pgid_alive(pgid: int) -> bool:
    import os

    try:
        os.killpg(pgid, 0)
        return True
    except OSError:
        return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    import os

    assert "CUDA_VISIBLE_DEVICES" not in os.environ or \
        os.environ["CUDA_VISIBLE_DEVICES"] in ("", "0"), "只在 GPU0 跑"

    class _NullFH:
        def write(self, s):
            pass

        def flush(self):
            pass

    res: dict = {"protocol": "RPENT_P1_VLA_PERSIST_STARTUP_V1"}
    t0 = time.time()
    proc, endpoint = runner._start_persistent_vla(_NullFH())
    res["startup_ok"] = True
    res["startup_load_s"] = round(time.time() - t0, 1)
    res["endpoint"] = endpoint
    try:
        res["alive_after_startup"] = runner._persistent_vla_alive(proc, endpoint)

        # 故障注入:模拟 server 中途崩溃(集间守卫要捕捉的情景)
        proc.kill()
        proc.wait(timeout=10)
        time.sleep(0.2)
        res["alive_after_crash"] = runner._persistent_vla_alive(proc, endpoint)
        res["crash_detected_immediately"] = res["alive_after_crash"] is False
    finally:
        how = runner._kill_pg(proc.pid, 5.0)
        time.sleep(0.5)
        res["cleanup_how"] = how
        res["group_gone"] = not _pgid_alive(proc.pid)

    res["pass"] = bool(
        res["startup_ok"] and res["alive_after_startup"]
        and res["crash_detected_immediately"] and res["group_gone"])
    out = OUT / "vla_persist_startup_check.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"[vla-persist-startup] -> {out}")
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
