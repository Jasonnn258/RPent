#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage R §5 — R1 前瞻采集(稳定 FALSE_GRASP 失败事件队列)。

规范:analysis/stageR_prereg.md §2/§5(仪器 / 进入标准 / 零条件化)。

流程:
1. 冻结顺序(task 主序 3→5→9、seed 升序 121-190)跑 vanilla Full Planner
   episode,子进程注入 RPENT_STAGE_R_TRACE=1(rtrace 仪器:边界快照 +
   动作流 + pick 逐 chunk 测量);
2. episode 结束后确定性判定进入标准(prereg §5,零 LLM、零结果条件化):
   a) 首个失败事件(FG∪RPS 取最早)= FALSE_GRASP 且 t0≥2;
   b) 稳定失败契约:t0 技能全程无任何测量点满足 acquisition
      (dz≥0.03 ∧ dxy(obj,EEF)≤0.10 ∨ check_success;基准=技能首点);
   c) provenance 完整:t0 pre/post 快照 + 1..t0-1 每步动作流 + t0 首
      chunk(a_fail)完整落盘;
3. 配额 STABLE_FG_QUOTA=32(网格耗尽时 22-31 可冻结为 N,<22 报
   INSUFFICIENT;一律不重跑、不挑选);
4. 账目 analysis/stageR_collect_ledger.csv(断点续跑,infra 重试 ≤3)。

用法:
  nohup python scripts/stageR_collect.py --workers 3 \
      >> /workspace/yjx/tmp/stageR_collect.log 2>&1 &
  python scripts/stageR_collect.py --smoke   # 第一格 + 仪器产物检查
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime
import json
import math
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path("/workspace/yjx/workspace/RPent")
sys.path.insert(0, str(ROOT / "scripts"))
import ovpm_exp as ox  # base_env / pg(preflight) / 常量——只读复用

LEDGER = ROOT / "analysis/stageR_collect_ledger.csv"
EP_DIR = ROOT / "logs/stageR_collect"

# ---- 冻结常量(prereg §5)--------------------------------------------------
GRID_TASKS = (3, 5, 9)                 # task 主序
GRID_SEEDS = tuple(range(121, 191))    # 121-190,与历史池零交集
STABLE_FG_QUOTA = 32
MIN_FREEZE_N = 22                      # 低于此 → INSUFFICIENT(不重跑)
MAX_INFRA_RETRY = 3

# 稳定失败契约阈值(= Stage Q 冻结 FG 契约参数,见 stageQ_rt/prereg §2)
FG_LIFT_DZ = 0.03
FG_FOLLOW_DXY = 0.10

LEDGER_FIELDS = [
    "task", "seed", "episode_dir", "rc", "classify", "wall_s", "retries",
    "fg_first", "rps_first", "t0", "t0_skill", "meas_points", "stable_fg",
    "included", "note",
]


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%F %T')}] {msg}", flush=True)


# ---- 事件检测(states.json;与 stageO_collect.detect_events 同契约)-------

def detect_first_events(episode_dir: str) -> dict:
    """首个 FG / 首个 RPS(零 LLM):FG=首个 pi0_pick 且 success False;
    RPS=首个 release 且 libero_terminated False。"""
    try:
        steps = json.load(open(Path(episode_dir) / "states.json"))
    except Exception as exc:
        return {"error": f"states.json unreadable: {exc}"}
    steps = sorted(steps, key=lambda s: s.get("step_idx") or 0)
    fg = rps = None
    for s in steps:
        cmd, res = s.get("command") or {}, s.get("result") or {}
        if not cmd:
            continue
        if fg is None and cmd.get("action") == "pi0_pick" \
                and res.get("success") is False:
            fg = s.get("step_idx")
        if rps is None and cmd.get("action") == "release" \
                and res.get("libero_terminated") is False:
            rps = s.get("step_idx")
    return {"fg_first": fg, "rps_first": rps}


# ---- rtrace 产物解析(prereg §2/§5)--------------------------------------

def load_trace(episode_dir: str) -> list[dict] | None:
    tj = Path(episode_dir) / "stageR_trace.jsonl"
    if not tj.exists():
        return None
    out = []
    with open(tj, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass     # 仪器半行(进程被杀):截尾容忍,靠完整性检查兜底
    return out


def _confirms(pt: dict, base: dict, target: str) -> bool:
    """单测量点是否满足 acquisition(与 stageQ_rt._confirms 同式)。"""
    if pt.get("check_success"):
        return True
    obs, bobs = pt.get("obs") or {}, base.get("obs") or {}
    pos = obs.get(f"{target}_pos")
    bpos = bobs.get(f"{target}_pos")
    eef = obs.get("robot0_eef_pos")
    if not pos or not bpos or not eef:
        return False
    if pos[2] - bpos[2] < FG_LIFT_DZ:
        return False
    return math.hypot(pos[0] - eef[0], pos[1] - eef[1]) <= FG_FOLLOW_DXY


def stable_fg_check(recs: list[dict], t0: int) -> dict:
    """prereg §5-b/§5-c:t0 技能测量点序列 → 稳定失败 + provenance。

    返回 {t0_skill, meas_points, stable_fg, prov_pre, prov_post, a_fail_ok,
    prefix_complete, target, note}。stable_fg=True 仅当契约 b 成立且
    provenance 全齐(分离字段供 ledger 取证)。
    """
    out = {"t0_skill": None, "meas_points": 0, "stable_fg": False,
           "prov_pre": False, "prov_post": False, "a_fail_ok": False,
           "prefix_complete": False, "target": "", "note": ""}
    # t0 技能边界
    for r in recs:
        if r.get("ev") == "step_begin" and r.get("step_idx") == t0:
            out["t0_skill"] = r.get("skill")
            break
    if out["t0_skill"] != "pi0_pick":
        out["note"] = f"t0_skill={out['t0_skill']}"
        return out
    # 测量点:chunk 前测量(= 上一 chunk 后状态)+ 技能末 final_meas
    pts = [r["meas"] for r in recs
           if r.get("ev") == "action" and r.get("step_idx") == t0
           and r.get("kind") == "chunk" and r.get("meas")]
    for r in reversed(recs):
        if r.get("ev") == "step_end" and r.get("step_idx") == t0:
            if r.get("final_meas"):
                pts.append(r["final_meas"])
            break
    out["meas_points"] = len(pts)
    if len(pts) < 2:
        out["note"] = f"meas_points={len(pts)}<2"
        return out
    base = pts[0]
    out["target"] = (base.get("obj_of_interest") or [""])[0]
    # 契约 b:任一点满足 acquisition → 非稳定失败(transient/success)
    for i, p in enumerate(pts):
        if _confirms(p, base, out["target"]):
            out["note"] = f"acq_point@{i}(dz/lift 或 check_success)"
            return out
    out["stable_fg"] = True
    out["note"] = "stable_fg"
    return out


def provenance_check(recs: list[dict], episode_dir: str, t0: int) -> dict:
    """prereg §5-c 独立检查:快照文件 + 前缀动作完整性 + a_fail 可解码。"""
    snaps = Path(episode_dir) / "stageR_snapshots"
    pre_ok = (snaps / f"step_{t0:03d}_pre.npy").exists()
    post_ok = (snaps / f"step_{t0:03d}_post.npy").exists()
    nact: Counter = Counter()
    a_fail = None
    for r in recs:
        if r.get("ev") != "action":
            continue
        idx = r.get("step_idx")
        nact[idx] += 1
        if idx == t0 and r.get("kind") == "chunk" and a_fail is None:
            a_fail = r
    missing = [i for i in range(1, t0) if nact.get(i, 0) == 0]
    a_fail_ok = False
    if a_fail is not None and a_fail.get("b64") \
            and a_fail.get("chunk_idx") == 1:      # 必须是技能首个 chunk
        try:
            raw = base64.b64decode(a_fail["b64"])
            n = 1
            for d in (a_fail.get("shape") or [len(raw) // 4]):
                n *= d
            a_fail_ok = len(raw) == n * 4          # float32 逐位可解码
        except Exception:
            a_fail_ok = False
    return {"pre": pre_ok, "post": post_ok, "a_fail_ok": a_fail_ok,
            "prefix_complete": not missing and nact.get(t0, 0) >= 1,
            "missing_steps": missing[:5]}


def judge_episode(episode_dir: str) -> dict:
    """进入标准总判定(prereg §5 a/b/c;零结果条件化)。"""
    ev = detect_first_events(episode_dir)
    if "error" in ev:
        return {**ev, "included": False, "t0": "", "stable_fg": False,
                "t0_skill": "", "meas_points": "", "note": ev["error"]}
    fg, rps = ev.get("fg_first"), ev.get("rps_first")
    # a) 首个失败事件 = FG 且 t0≥2
    if fg is None or (rps is not None and rps < fg):
        return {**ev, "included": False, "t0": "", "stable_fg": False,
                "t0_skill": "", "meas_points": "",
                "note": "fg_absent" if fg is None else f"rps_first@{rps}"}
    if fg < 2:
        return {**ev, "included": False, "t0": fg, "stable_fg": False,
                "t0_skill": "", "meas_points": "", "note": "t0<2"}
    recs = load_trace(episode_dir)
    if not recs:
        return {**ev, "included": False, "t0": fg, "stable_fg": False,
                "t0_skill": "", "meas_points": "", "note": "no_trace"}
    sc = stable_fg_check(recs, fg)
    pv = provenance_check(recs, episode_dir, fg)
    ok = (sc["stable_fg"] and pv["pre"] and pv["post"]
          and pv["a_fail_ok"] and pv["prefix_complete"])
    note = sc["note"] if not sc["stable_fg"] else (
        "prov_fail:" + ",".join(k for k in ("pre", "post", "a_fail_ok",
                                            "prefix_complete") if not pv[k])
        if not ok else "stable_fg_event")
    return {**ev, "t0": fg, "t0_skill": sc["t0_skill"],
            "meas_points": sc["meas_points"], "target": sc["target"],
            "stable_fg": sc["stable_fg"], "included": ok, "note": note}


# ---- episode 执行(stageO_collect.run_cell 同构 + RPENT_STAGE_R_TRACE=1)--

def run_cell(task: int, seed: int, env: dict) -> dict:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H:%M:%S")
    outdir = EP_DIR / f"{ts}_vanilla_libero_spatial_t{task}_s{seed}"
    outdir.mkdir(parents=True, exist_ok=True)
    e = dict(env)
    e["CUDA_VISIBLE_DEVICES"] = e.pop("_GPU", "0")
    e["RPENT_TASK"] = str(task)
    e["RPENT_STAGE_R_TRACE"] = "1"          # Stage R 仪器(默认关,此处开)
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


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def quota_left(rows: list[dict]) -> int:
    return STABLE_FG_QUOTA - sum(1 for r in rows
                                 if r.get("included") == "True")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--smoke", action="store_true",
                    help="只跑第一格(t3 s121):打印判定 + 仪器产物体检,"
                         "不写 ledger")
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()

    ox.pg.preflight(label="stageR_collect",
                    lock_name="stageR_collect.lock")

    cells = [(t, s) for t in GRID_TASKS for s in GRID_SEEDS]
    log(f"grid {len(cells)} cells; workers={args.workers} smoke={args.smoke}")

    if args.smoke:
        env = ox.base_env()
        env["_GPU"] = args.gpu
        task, seed = cells[0]
        log(f"SMOKE t{task} s{seed} ...")
        r = run_cell(task, seed, env)
        j = judge_episode(r["episode_dir"])
        # 仪器产物体检:trace 行型分布 + 快照计数 + 体积
        recs = load_trace(r["episode_dir"]) or []
        kinds = Counter(x.get("ev") for x in recs)
        snaps = Path(r["episode_dir"]) / "stageR_snapshots"
        nsnap = len(list(snaps.glob("*.npy"))) if snaps.exists() else 0
        tj = Path(r["episode_dir"]) / "stageR_trace.jsonl"
        sz = tj.stat().st_size // 1024 if tj.exists() else -1
        log(f"smoke rc={r['rc']} classify={r['classify']} wall={r['wall_s']}s")
        log(f"trace: {dict(kinds)} snaps={nsnap} size={sz}KB")
        log(f"judge: {j}")
        log("SMOKE OK" if r["classify"] in ("success", "policy_fail")
            else "SMOKE FAIL(classify)")
        return 0

    env = ox.base_env()
    env["_GPU"] = args.gpu
    terminal = {(int(r["task"]), int(r["seed"])) for r in read_ledger()
                if r.get("classify") in ("success", "policy_fail")}

    lock = threading.Lock()
    ledger_f = open(LEDGER, "a", newline="", encoding="utf-8")
    lw = csv.DictWriter(ledger_f, fieldnames=LEDGER_FIELDS)
    if read_ledger() == []:
        lw.writeheader()
        ledger_f.flush()

    def process_cell(cell):
        task, seed = cell
        with lock:
            left = quota_left(read_ledger())
        if left <= 0:
            log("配额已满(32 稳定 FG),停止扫描")
            return False
        retries, r = 0, None
        while retries <= MAX_INFRA_RETRY:
            with lock:
                if quota_left(read_ledger()) <= 0:
                    return False
            r = run_cell(task, seed, env)
            if r["classify"] in ("success", "policy_fail"):
                break
            retries += 1
            log(f"t{task}s{seed} infra({r['classify']}) retry {retries}")
        j = judge_episode(r["episode_dir"]) if r and r["classify"] in (
            "success", "policy_fail") else {"error": "infra_exhausted"}
        with lock:
            include_now = quota_left(read_ledger()) > 0
        included = bool(j.get("included") and include_now)
        row = {"task": task, "seed": seed, **r, "retries": retries,
               "fg_first": j.get("fg_first", ""),
               "rps_first": j.get("rps_first", ""),
               "t0": j.get("t0", ""), "t0_skill": j.get("t0_skill", ""),
               "meas_points": j.get("meas_points", ""),
               "stable_fg": bool(j.get("stable_fg")),
               "included": included,
               "note": j.get("note", "")}
        with lock:
            lw.writerow(row)
            ledger_f.flush()
        log(f"t{task}s{seed} rc={r['rc']} {r['classify']} "
            f"fg={row['fg_first']} rps={row['rps_first']} "
            f"stable={row['stable_fg']} -> included={included} "
            f"({row['note']})")
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
                    f"{traceback.format_exc()[-400:]}")
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
    n_term = sum(1 for r in rows
                 if r.get("classify") in ("success", "policy_fail"))
    n_incl = sum(1 for r in rows if r["included"] == "True")
    n_stable = sum(1 for r in rows if r["stable_fg"] == "True")
    log(f"采集结束:terminal={n_term} stable_fg={n_stable} "
        f"included={n_incl}/{STABLE_FG_QUOTA}")
    if n_incl < MIN_FREEZE_N:
        log(f"WARN: included={n_incl} < {MIN_FREEZE_N} → 按 prereg §5 记 "
            f"INSUFFICIENT(不重跑、不放宽标准)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
