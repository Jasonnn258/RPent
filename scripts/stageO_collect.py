#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §7 — O-B 快照采集(Full Planner 新 episodes + 冻结事件契约)。

规范:analysis/stageO_prereg.md §3(配额/隔离/grid/扫描顺序/族分配规则)。

流程:
1. 按冻结顺序(task 主序 3→5→9、seed 升序)逐格跑 Full Planner episode
   (vanilla,无任何 ovpm 实验环境变量;rpent CLI,max-turns 40);
2. episode 结束后确定性检测 FG_first / RPS_first(§2 契约,零 LLM);
3. 按冻结族配额规则分配 snapshot family 或记 logged-excluded;
4. 全程账目写 analysis/stageO_collect_ledger.csv(断点续跑:已完成的
   task×seed 格跳过;infra(非 success/policy_fail)重试 ≤3)。

快照物化(重放 1..t0 → save_state)不在本脚本:由 stageO_freeze_manifest.py
在采集收尾后统一做并冻结 manifest hash。

用法:
  nohup python scripts/stageO_collect.py --workers 3 \
      >> /workspace/yjx/tmp/stageO_collect.log 2>&1 &
  python scripts/stageO_collect.py --smoke   # 只跑第一格并打印检测结果
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path("/workspace/yjx/workspace/RPent")
sys.path.insert(0, str(ROOT / "scripts"))
import ovpm_exp as ox  # 复用 base_env / log / 常量 / pg(preflight)——均只读复用

LEDGER = ROOT / "analysis/stageO_collect_ledger.csv"
EP_DIR = ROOT / "logs/stageO_collect"

# ---- 冻结常量(prereg §3 + 附录 A)----------------------------------------
GRID_TASKS = (3, 5, 9)  # task 主序
GRID_SEEDS = tuple(list(range(13, 19)) + list(range(21, 29)))  # 13-18, 21-28
EXCLUDE = {  # N 池 ∪ L split 池(prereg 附录 A;与 grid 相交部分)
    (3, 19), (3, 20),
    (5, 13), (5, 18),
    (9, 15), (9, 16), (9, 17), (9, 20),
}
QUOTA = {"FALSE_GRASP": 8, "RELEASE_PREDICATE_STALL": 8}
MAX_INFRA_RETRY = 3

LEDGER_FIELDS = [
    "task", "seed", "episode_dir", "rc", "classify", "wall_s", "retries",
    "fg_first", "rps_first", "assigned_family", "assigned_t0", "included",
    "note",
]


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


def detect_events(episode_dir: str) -> dict:
    """确定性检测 FG_first / RPS_first(stageO_prereg §2 契约,零 LLM)。

    FG_first  = 首个 command.action==pi0_pick 且 result.success is False 的 step
    RPS_first = 首个 command.action==release 且 result.libero_terminated
                is False 的 step
    附带重放完整性:1..t0 每步有 command(缺则记 replay_incomplete)。
    """
    try:
        steps = json.load(open(Path(episode_dir) / "states.json"))
    except Exception as exc:
        return {"error": f"states.json unreadable: {exc}"}
    steps = sorted(steps, key=lambda s: s.get("step_idx") or 0)
    fg = rps = None
    incomplete_from = None
    have = set()
    for s in steps:
        idx = s.get("step_idx")
        cmd = s.get("command") or {}
        res = s.get("result") or {}
        if not cmd:
            if incomplete_from is None and (fg is not None or rps is not None):
                incomplete_from = idx  # 事件之后出现缺 command 步
            continue
        have.add(idx)
        if (fg is None and cmd.get("action") == "pi0_pick"
                and res.get("success") is False):
            fg = idx
        if (rps is None and cmd.get("action") == "release"
                and res.get("libero_terminated") is False):
            rps = idx
    # 重放完整性只对被选中的 t0 有意义;此处一并报告
    miss = [i for i in range(1, (max(have) if have else 0) + 1) if i not in have]
    return {"fg_first": fg, "rps_first": rps,
            "replay_missing_steps": miss[:5] if miss else ""}


def assign_family(ev: dict, quota_open: dict) -> tuple[str, int, str] | None:
    """冻结族配额分配规则(prereg 附录 A):返回 (family, t0, note) 或 None。"""
    if not quota_open["FALSE_GRASP"] and not quota_open[
            "RELEASE_PREDICATE_STALL"]:
        return None
    fg, rps = ev.get("fg_first"), ev.get("rps_first")
    if quota_open["FALSE_GRASP"] and quota_open["RELEASE_PREDICATE_STALL"]:
        if fg is not None and (rps is None or fg <= rps):
            return ("FALSE_GRASP", fg, "both_open_first_event")
        if rps is not None:
            return ("RELEASE_PREDICATE_STALL", rps, "both_open_first_event")
        return None
    if quota_open["FALSE_GRASP"]:
        return ("FALSE_GRASP", fg, "fg_only_open") if fg is not None else None
    return ("RELEASE_PREDICATE_STALL", rps, "rps_only_open") \
        if rps is not None else None


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def quota_state(rows: list[dict]) -> dict:
    return {f: QUOTA[f] - sum(1 for r in rows if r["included"] == "True"
                              and r["assigned_family"] == f)
            for f in QUOTA}


def run_cell(task: int, seed: int, env: dict) -> dict:
    """跑一格 episode(完全镜像 ovpm_exp.run_episode 的 vanilla 路径)。"""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H:%M:%S")
    outdir = EP_DIR / f"{ts}_vanilla_libero_spatial_t{task}_s{seed}"
    outdir.mkdir(parents=True, exist_ok=True)
    e = dict(env)
    e["CUDA_VISIBLE_DEVICES"] = e.pop("_GPU", "0")  # 内部传参,不进子进程 env
    e["RPENT_TASK"] = str(task)
    cmd = [
        "rpent", "--env", "libero", "--suite", "libero_spatial",
        "--task", str(task), "--seed", str(seed),
        "--output-dir", str(outdir),
        "--planner", "api", "--model", "anthropic:glm-5.3-flash",
        "--base-url", ox.GLM_BASE_URL,
        "--planner-timeout-s", str(ox.PLANNER_TIMEOUT_S),
        "--max-turns", str(ox.EVAL_TURNS),
        "--max-tokens", str(ox.PLANNER_MAX_TOKENS),
    ]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, env=e, timeout=ox.RUNTIME_S,
                           capture_output=True, text=True)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = -9
    except Exception:
        rc = -1
    wall = round(time.time() - t0, 1)
    result = ox.pg.classify_dir(str(outdir))
    # token/quota 级 planner 侧截断 = infra(ovpm_exp 同规则)
    if result not in ("success", "infra_crash", "infra_timeout"):
        try:
            rl = Path(outdir) / "run.log"
            txt = rl.read_text(errors="replace") if rl.exists() else ""
            if (ox._TOKEN_LIMIT_FATAL.format(ox.PLANNER_MAX_TOKENS) in txt
                    or ox._TOKEN_LIMIT_FATAL.format("8192") in txt
                    or ox._QUOTA_LIMIT_FATAL in txt):
                result = "infra_crash"
        except OSError:
            pass
    return {"episode_dir": str(outdir), "rc": rc, "classify": result,
            "wall_s": wall}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--smoke", action="store_true",
                    help="只跑第一格(t3 s13)并打印检测结果,不写 ledger")
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()

    # preflight + 防重复锁(CLAUDE.md 铁律;smoke 亦检查)
    ox.pg.preflight(label="stageO_collect",
                    lock_name="stageO_collect.lock")

    cells = [(t, s) for t in GRID_TASKS for s in GRID_SEEDS
             if (t, s) not in EXCLUDE]
    log(f"grid {len(cells)} cells; workers={args.workers} smoke={args.smoke}")

    if args.smoke:
        env = ox.base_env()
        env["_GPU"] = args.gpu
        task, seed = cells[0]
        log(f"SMOKE t{task} s{seed} ...")
        r = run_cell(task, seed, env)
        ev = detect_events(r["episode_dir"])
        log(f"smoke done rc={r['rc']} classify={r['classify']} "
            f"wall={r['wall_s']}s events={ev}")
        return 0

    env = ox.base_env()
    env["_GPU"] = args.gpu

    # 断点续跑:已有终态行(classify∈{success,policy_fail},included 决策已定)
    # 的格子跳过;infra/EXC 行重试
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
            rows = read_ledger()
            q = quota_state(rows)
        if q["FALSE_GRASP"] <= 0 and q["RELEASE_PREDICATE_STALL"] <= 0:
            log("配额已满,停止扫描")
            return False
        retries = 0
        while retries <= MAX_INFRA_RETRY:
            with lock:
                rows = read_ledger()
                q = quota_state(rows)
            if q["FALSE_GRASP"] <= 0 and q["RELEASE_PREDICATE_STALL"] <= 0:
                return False
            r = run_cell(task, seed, env)
            if r["classify"] in ("success", "policy_fail"):
                break
            retries += 1
            log(f"t{task}s{seed} infra({r['classify']}) retry {retries}")
        ev = detect_events(r["episode_dir"]) if r["classify"] in (
            "success", "policy_fail") else {"error": "infra_exhausted"}
        assigned = None
        if "error" not in ev:
            with lock:
                q = quota_state(read_ledger())
            q_open = {f: q[f] > 0 for f in q}
            assigned = assign_family(ev, q_open)
            # 分配出的 t0 必须重放完整(1..t0 每步有 command)
            if assigned:
                fam, t0c, note = assigned
                miss = ev.get("replay_missing_steps")
                if miss:
                    assigned, note = None, f"replay_incomplete@{miss}"
        row = {"task": task, "seed": seed, **r, "retries": retries,
               "fg_first": ev.get("fg_first", ""),
               "rps_first": ev.get("rps_first", ""),
               "assigned_family": assigned[0] if assigned else "",
               "assigned_t0": assigned[1] if assigned else "",
               "included": bool(assigned), "note": assigned[2] if assigned
               else ev.get("error", "no_event" if "error" not in ev else ""),
               }
        with lock:
            lw.writerow(row)
            ledger_f.flush()
        log(f"t{task}s{seed} rc={r['rc']} {r['classify']} "
            f"fg={row['fg_first']} rps={row['rps_first']} -> "
            f"{row['assigned_family']}@{row['assigned_t0']} "
            f"included={row['included']}")
        return True

    # 顺序扫描、窗口并发(冻结顺序即扫描序;窗口内乱序完成不影响分配规则,
    # 因为分配以 ledger 顺序写入时的配额状态为准——窗口大小=workers)
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
        time.sleep(ox.STAGGER_S)  # 冷启动错峰(ovpm 同规则)
    for t in threads:
        t.join()

    rows = read_ledger()
    q = quota_state(rows)
    log(f"采集结束:配额余量 FG={q['FALSE_GRASP']} "
        f"RPS={q['RELEASE_PREDICATE_STALL']};"
        f"included={sum(1 for r in rows if r['included'] == 'True')}")
    if q['FALSE_GRASP'] > 3 or q['RELEASE_PREDICATE_STALL'] > 3:
        log("WARN: 配额未满超过容差(12-18/每族>=5),"
            "需按 prereg §3 报 INSUFFICIENT_SNAPSHOTS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
