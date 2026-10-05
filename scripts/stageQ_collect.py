#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage Q §6 — Q1 快照采集(Full Planner 新 episodes,FG-only)。

程序 = stageP_collect.py 逐字镜像,仅改冻结常量(prereg §6):
- grid:{t3,t5,t9} × seeds 76-120(与 N/L/O/P 池零交集);
- 配额:FALSE_GRASP 20 上限(容差 18-22),RPS 一律 logged-excluded;
- 结构排除:t0=1 无 S_pre(prereg §3,t0_lt_2_excluded;非结果筛选);
- ledger/episode 目录换 stageQ_*。

产物:analysis/stageQ_collect_ledger.csv(物化由 stageQ_freeze.py 收尾)。

用法:
  nohup python scripts/stageQ_collect.py --workers 3 \
      >> /workspace/yjx/tmp/stageQ_collect.log 2>&1 &
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path("/workspace/yjx/workspace/RPent")
sys.path.insert(0, str(ROOT / "scripts"))
import ovpm_exp as ox  # base_env / log / 常量 / pg(preflight)——只读复用
import stageO_collect as oc  # detect_events / run_cell 逐字复用(零改动)

LEDGER = ROOT / "analysis/stageQ_collect_ledger.csv"
EP_DIR = ROOT / "logs/stageQ_collect"

# ---- 冻结常量(prereg §6)--------------------------------------------------
GRID_TASKS = (3, 5, 9)
GRID_SEEDS = tuple(range(76, 121))   # 76-120,与历史池零交集
EXCLUDE: set[tuple[int, int]] = set()
FG_QUOTA = 20                        # 容差上限(顺序停止规则)
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
    """§6:FG-only 分配;RPS 不分配;t0=1 结构排除(无 S_pre)。"""
    fg = ev.get("fg_first")
    if fg is None:
        return None
    if int(fg) < 2:
        return ("EXCLUDED", fg, "t0_lt_2_no_pre_state")
    return ("FALSE_GRASP", fg, "fg_first_event")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()

    ox.pg.preflight(label="stageQ_collect", lock_name="stageQ_collect.lock")

    cells = [(t, s) for t in GRID_TASKS for s in GRID_SEEDS
             if (t, s) not in EXCLUDE]
    log(f"grid {len(cells)} cells (seeds 76-120); "
        f"workers={args.workers} smoke={args.smoke}")

    oc.EP_DIR = EP_DIR

    if args.smoke:
        env = ox.base_env()
        env["_GPU"] = args.gpu
        task, seed = cells[0]
        log(f"SMOKE t{task} s{seed} ...")
        r = oc.run_cell(task, seed, env)
        ev = oc.detect_events(r["episode_dir"])
        log(f"smoke done rc={r['rc']} classify={r['classify']} "
            f"events={ev}")
        return 0

    env = ox.base_env()
    env["_GPU"] = args.gpu

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
               "assigned_family": (assigned[0] if assigned
                                   and assigned[0] == "FALSE_GRASP" else ""),
               "assigned_t0": assigned[1] if assigned else "",
               "included": bool(assigned
                                and assigned[0] == "FALSE_GRASP"),
               "note": (assigned[2] if assigned
                        else ("rps_logged_excluded"
                              if "error" not in ev
                              and ev.get("rps_first") is not None
                              and ev.get("fg_first") is None
                              else ev.get("error", "no_event"
                                          if "error" not in ev else "")))
               }
        with lock:
            lw.writerow(row)
            ledger_f.flush()
        log(f"t{task}s{seed} rc={r['rc']} {r['classify']} "
            f"fg={row['fg_first']} -> {row['assigned_family']}"
            f"@{row['assigned_t0']} included={row['included']} "
            f"(FG {fg_count(read_ledger())}/{FG_QUOTA})")
        return True

    from collections import deque
    pending = deque([c for c in cells if c not in terminal])
    log(f"resume: {len(terminal)} cells terminal, {len(pending)} to go")
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
            except Exception as exc:
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
        time.sleep(ox.STAGGER_S)
    for t in threads:
        t.join()

    rows = read_ledger()
    n_fg = fg_count(rows)
    log(f"采集结束:FG {n_fg}/{FG_QUOTA} | episodes {len(rows)} | "
        f"included={sum(1 for r in rows if r['included'] == 'True')}")
    if n_fg < 18:
        log("WARN: FG < 18(§6 容差下限)→ 记 INSUFFICIENT_SNAPSHOTS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
