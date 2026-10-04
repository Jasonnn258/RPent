#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage P §6(dev-P2)— P1 快照采集(Full Planner 新 episodes,FG-only)。

规范:analysis/stageP_prereg.md §6 + 附录 C dev-P2(扩格 seeds 29-75,
用户 2026-10-04 批准);程序 = Stage O §3 逐字(完整 episode、max-turns 40、
首个 FG 事件为 t0、每 episode 至多 1 快照、判定规则零 LLM、零结果筛选)。

与 stageO_collect.py 的差异(全部来自 prereg §6/dev-P2,其余逐字镜像):
- grid:{t3,t5,t9} × seeds 29-75(141 格);排除集交集为空,保留可读性;
- 配额:FALSE_GRASP 28 上限,**RPS 一律 logged-excluded**;
- ledger/episode 目录换 stageP_*;断点续跑/infra≤3 重试同 Stage O。

产物:analysis/stageP_collect_ledger.csv(快照物化由 stageP_freeze.py 收尾)。

用法:
  nohup python scripts/stageP_collect.py --workers 3 \
      >> /workspace/yjx/tmp/stageP_collect.log 2>&1 &
  python scripts/stageP_collect.py --smoke   # 只跑第一格,不写 ledger
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path("/workspace/yjx/workspace/RPent")
sys.path.insert(0, str(ROOT / "scripts"))
import ovpm_exp as ox  # 复用 base_env / log / 常量 / pg(preflight)——均只读复用
import stageO_collect as oc  # detect_events / run_cell 逐字复用(零改动)

LEDGER = ROOT / "analysis/stageP_collect_ledger.csv"
EP_DIR = ROOT / "logs/stageP_collect"

# ---- 冻结常量(prereg §6 + dev-P2)----------------------------------------
GRID_TASKS = (3, 5, 9)          # task 主序
GRID_SEEDS = tuple(range(29, 76))  # dev-P2:29-75(141 格)
EXCLUDE: set[tuple[int, int]] = set()   # N∪L∪O 池与 29-75 交集为空(dev-P2)
FG_QUOTA = 28                   # 容差上限(dev-P2 顺序停止规则)
MAX_INFRA_RETRY = 3

LEDGER_FIELDS = [
    "task", "seed", "episode_dir", "rc", "classify", "wall_s", "retries",
    "fg_first", "rps_first", "assigned_family", "assigned_t0", "included",
    "note",
]


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fg_count(rows: list[dict]) -> int:
    return sum(1 for r in rows if r["included"] == "True"
               and r["assigned_family"] == "FALSE_GRASP")


def assign_fg(ev: dict) -> tuple[str, int, str] | None:
    """§6:FG-only 分配——首个 FG 事件即 t0;RPS 不分配(logged-excluded)。"""
    fg = ev.get("fg_first")
    if fg is None:
        return None
    return ("FALSE_GRASP", fg, "fg_first_event")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--smoke", action="store_true",
                    help="只跑第一格(t3 s29)并打印检测结果,不写 ledger")
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()

    # preflight + 防重复锁(CLAUDE.md 铁律;smoke 亦检查)
    ox.pg.preflight(label="stageP_collect", lock_name="stageP_collect.lock")

    cells = [(t, s) for t in GRID_TASKS for s in GRID_SEEDS
             if (t, s) not in EXCLUDE]
    log(f"grid {len(cells)} cells (dev-P2 seeds 29-75); "
        f"workers={args.workers} smoke={args.smoke}")

    # run_cell/detect_events 与 Stage O 共享 episode 目录由参数传入 → 覆写
    oc.EP_DIR = EP_DIR

    if args.smoke:
        env = ox.base_env()
        env["_GPU"] = args.gpu
        task, seed = cells[0]
        log(f"SMOKE t{task} s{seed} ...")
        r = oc.run_cell(task, seed, env)
        ev = oc.detect_events(r["episode_dir"])
        log(f"smoke done rc={r['rc']} classify={r['classify']} "
            f"wall={r['wall_s']}s events={ev}")
        return 0

    env = ox.base_env()
    env["_GPU"] = args.gpu

    # 断点续跑:终态行(classify∈{success,policy_fail})的格子跳过
    terminal = {(int(r["task"]), int(r["seed"])) for r in read_ledger()
                if r.get("classify") in ("success", "policy_fail")}

    lock = threading.Lock()
    ledger_f = open(LEDGER, "a", newline="", encoding="utf-8")
    lw = csv.DictWriter(ledger_f, fieldnames=LEDGER_FIELDS)
    if not LEDGER.exists() or read_ledger() == []:
        lw.writeheader()
        ledger_f.flush()

    def process_cell(cell):
        task, seed = cell
        with lock:
            if fg_count(read_ledger()) >= FG_QUOTA:
                return False
        retries = 0
        while retries <= MAX_INFRA_RETRY:
            with lock:
                if fg_count(read_ledger()) >= FG_QUOTA:
                    return False
            r = oc.run_cell(task, seed, env)
            if r["classify"] in ("success", "policy_fail"):
                break
            retries += 1
            log(f"t{task}s{seed} infra({r['classify']}) retry {retries}")
        ev = oc.detect_events(r["episode_dir"]) if r["classify"] in (
            "success", "policy_fail") else {"error": "infra_exhausted"}
        assigned = None
        if "error" not in ev:
            assigned = assign_fg(ev)
            # 分配出的 t0 必须重放完整(1..t0 每步有 command)
            if assigned and ev.get("replay_missing_steps"):
                assigned = None
        row = {"task": task, "seed": seed, **r, "retries": retries,
               "fg_first": ev.get("fg_first", ""),
               "rps_first": ev.get("rps_first", ""),
               "assigned_family": assigned[0] if assigned else "",
               "assigned_t0": assigned[1] if assigned else "",
               "included": bool(assigned),
               "note": assigned[2] if assigned
               else ("rps_logged_excluded"
                     if "error" not in ev and ev.get("rps_first") is not None
                     and ev.get("fg_first") is None
                     else ev.get("error", "no_event" if "error" not in ev
                                 else "")),
               }
        with lock:
            lw.writerow(row)
            ledger_f.flush()
        log(f"t{task}s{seed} rc={r['rc']} {r['classify']} "
            f"fg={row['fg_first']} rps={row['rps_first']} -> "
            f"{row['assigned_family']}@{row['assigned_t0']} "
            f"included={row['included']} "
            f"(FG {fg_count(read_ledger())}/{FG_QUOTA})")
        return True

    # 顺序扫描、窗口并发(同 Stage O:冻结顺序即扫描序,窗口=workers)
    from collections import deque
    pending = deque([c for c in cells if c not in terminal])
    log(f"resume: {len(terminal)} cells already terminal, "
        f"{len(pending)} to go")
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            with lock:
                if not pending:
                    return
                cell = pending.popleft()
            try:
                alive = process_cell(cell)
                if alive is False:
                    stop.set()
                    with lock:
                        pending.clear()
            except Exception as exc:   # 单格异常不拖垮整个采集(留 ledger 行)
                import traceback
                log(f"cell {cell} EXC {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()[-500:]}")
                with lock:
                    lw.writerow({"task": cell[0], "seed": cell[1],
                                 "note": f"EXC {type(exc).__name__}"})
                    ledger_f.flush()

    threads = [threading.Thread(target=worker, daemon=True)
               for _ in range(max(1, args.workers))]
    for t in threads:
        t.start()
        time.sleep(ox.STAGGER_S)      # 冷启动错峰(ovpm 同规则)
    for t in threads:
        t.join()

    rows = read_ledger()
    n_fg = fg_count(rows)
    log(f"采集结束:FG {n_fg}/{FG_QUOTA} | episodes {len(rows)} | "
        f"included={sum(1 for r in rows if r['included'] == 'True')}")
    if n_fg < 20:
        log("WARN: FG < 20(§10 容差下限)→ 需报 INSUFFICIENT_SNAPSHOTS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
