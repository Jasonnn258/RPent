#!/usr/bin/env python3
"""P1-DEV0 受控 pilot runner:按冻结 manifest 顺序执行 ≤24 个新 episode。

预注册协议:P1-DEV0-L2-24EP-4ARM-20261009。
授权边界(P1_DEV0_AUTHORIZATION_AND_LOCK.md):
- ≤24 新 episode / ≤8h 墙钟 / ≤6 GPU·hour / ≤2 worker,任一先到即停;
- 不重写/不重跑 Stage R / S1;不启用 Stage R 仪器(RPENT_STAGE_R_TRACE 不设);
- 未触发 D2 的 episode 保留在分母(intention-to-treat);
- 不为补足触发事件加跑;不根据运行结果改 manifest/臂/指标。

恢复规则(运行前冻结):
- episode 已有 episode_end 事件 → COMPLETED,计入预算,不重跑;
- episode 有 trigger 事件但无 episode_end → CENSORED_NO_RERUN(已发生干预,
  重跑等于换样本,禁止);
- episode 已启动但无 trigger 事件(纯 infra 崩溃)→ 允许且仅允许一次重跑
  (同一 manifest cell,未产生任何干预数据,不属于 outcome-conditioned 挑选)。

用法(vla 环境 python):
  python scripts/p1_dev0_run.py --dry-run          # 只打印命令与预算
  nohup python scripts/p1_dev0_run.py >> /workspace/yjx/tmp/p1_dev0_run.log 2>&1 &
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "artifacts" / "p1_dev0" / "manifest.jsonl"
SEAL = REPO / "artifacts" / "p1_dev0" / "manifest.sha256.json"
POLICY = REPO / "analysis" / "research_context" / "p1_dev0_policy.py"

# 预注册预算(与 manifest seal 一致;先到即停)
MAX_EPISODES = 24
MAX_WORKERS = 2
MAX_WALL_S = 8 * 3600
MAX_GPU_S = 6 * 3600

# 固定实验参数(运行前冻结,不得根据结果调整)
TURNS = 100                 # 与 vanilla 入口 run_rpent.sh 文档示例一致
PLANNER_TIMEOUT_S = 2400    # 与 run_rpent.sh 默认一致
EPISODE_HARD_TIMEOUT_S = 5400   # 子进程硬超时(含服务器启动裕量)
AUDIT_HORIZON = 200         # 固定未来审计 horizon(env steps)
EPISODE_STEP_CAP = 1500     # D3 预算门的 episode 级 env-step 上限

# 环境(镜像 run_rpent.sh;GL 按本容器铁律改用 osmesa)
BASE_ENV = {
    "PI05_CHECKPOINT_PATH": "/workspace/yjx/rpent_data/checkpoints/pi05",
    "SAM3_CHECKPOINT_PATH": "/workspace/yjx/rpent_data/checkpoints/sam3/sam3.pt",
    "ROBOT_PLATFORM": "LIBERO",
    "LIBERO_TYPE": "pro",
    "OPENPI_DATA_HOME": "/workspace/yjx/rpent_data/.cache/openpi",
    "LIBERO_CONFIG_PATH": "/workspace/yjx/rpent_data/.libero",
    "HF_HUB_OFFLINE": "1",
    "MUJOCO_GL": "osmesa",          # 本容器 EGL 设备数 0,egl 会 worker 无声死亡
    # env_server.py 会 setdefault PYOPENGL_PLATFORM=egl;必须显式压成 osmesa,
    # 否则 mujoco.osmesa 导入时直接 ImportError(2026-10-09 实测事故)
    "PYOPENGL_PLATFORM": "osmesa",
    "PLANNER_MODEL": "anthropic:glm-5.3-flash",
    "PLANNER_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
}
UNSET_ENV = ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE",
             "RPENT_STAGE_R_TRACE")   # osmesa 铁律 + 不启用 Stage R 仪器

PREFLIGHT = "/workspace/yjx/bin/dev_preflight.sh"
LOCK_DIR = "/workspace/yjx/.runlocks/p1_dev0.lock"


def _log(run_log_fh, run_log_path: Path, rec: dict) -> None:
    rec["t"] = round(time.time(), 3)
    line = json.dumps(rec, ensure_ascii=False, default=str)
    print(line, flush=True)
    if run_log_fh is not None:
        run_log_fh.write(line + "\n")
        run_log_fh.flush()


def _load_manifest() -> list[dict]:
    """读 manifest 并复核 sha256 seal;不一致即拒绝启动。"""
    if not (MANIFEST.is_file() and SEAL.is_file()):
        sys.exit(f"FATAL: manifest/seal missing: {MANIFEST}")
    rows = [json.loads(x) for x in
            MANIFEST.read_text(encoding="utf-8").splitlines() if x.strip()]
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    content = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")) + "\n" for r in rows).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    if digest != seal.get("sha256") or len(rows) != seal.get("episodes"):
        sys.exit("FATAL: manifest sha256 seal mismatch — refuse to start")
    if seal.get("max_workers") != MAX_WORKERS or \
            seal.get("max_wall_seconds") != MAX_WALL_S or \
            seal.get("max_gpu_seconds") != MAX_GPU_S:
        sys.exit("FATAL: runner budgets differ from sealed manifest budgets")
    return rows


def _events_state(out_dir: Path) -> str:
    """读该 episode 的 p1_dev0 事件文件,判恢复状态。"""
    f = out_dir / "p1_dev0_events.jsonl"
    if not f.is_file():
        return "NOT_STARTED"
    evs = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            evs.append(json.loads(line))
        except Exception:
            pass
    kinds = {e.get("ev") for e in evs}
    if "episode_end" in kinds:
        return "COMPLETED"
    if "trigger" in kinds:
        return "CENSORED_NO_RERUN"
    return "INFRA_NO_TRIGGER"


def _episode_cost_s(out_dir: Path) -> float:
    """从事件文件估已耗墙钟(init→episode_end);缺文件按 0。"""
    f = out_dir / "p1_dev0_events.jsonl"
    if not f.is_file():
        return 0.0
    t0 = t1 = None
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("ev") == "init":
            t0 = e.get("t")
        if e.get("ev") == "episode_end":
            t1 = e.get("t")
    if t0 is None:
        return 0.0
    return float(t1 or time.time()) - float(t0)


def _acquire_lock() -> None:
    """防重复启动锁(目录 + pid 文件;陈旧锁自动接管)。"""
    import atexit
    if os.path.isdir(LOCK_DIR):
        pid_file = Path(LOCK_DIR) / "pid"
        try:
            old = int(pid_file.read_text().strip())
            os.kill(old, 0)
            sys.exit(f"FATAL: another p1_dev0 runner alive (pid {old})")
        except (ProcessLookupError, ValueError, OSError):
            shutil.rmtree(LOCK_DIR, ignore_errors=True)   # 陈旧锁:接管
    os.makedirs(LOCK_DIR, exist_ok=True)
    (Path(LOCK_DIR) / "pid").write_text(str(os.getpid()))
    (Path(LOCK_DIR) / "cmd").write_text(" ".join(sys.argv))
    atexit.register(lambda: shutil.rmtree(LOCK_DIR, ignore_errors=True))


def _planner_env() -> dict:
    """GLM planner 密钥:只进子进程 env,绝不打印。"""
    env_file = Path("/workspace/yjx/rpent_data/rpent_env.sh")
    key = ""
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.startswith("GLM_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
                break
    if not key:
        sys.exit("FATAL: GLM_API_KEY not found in rpent_env.sh")
    return {"ANTHROPIC_API_KEY": key}


def _episode_cmd(row: dict, out_root: Path, ts: str):
    """构造单 episode 子进程命令与完整 env(镜像 run_rpent.sh,GL=osmesa)。"""
    key = row["episode_key"]
    ep_out = out_root / "runs" / f"{key}_{ts}"
    env = {k: v for k, v in os.environ.items() if k not in UNSET_ENV}
    env.update(BASE_ENV)
    env.update(_planner_env())
    env.update({
        "RPENT_P1_DEV0": "1",
        "RPENT_P1_DEV0_ARM": row["arm"],
        "RPENT_P1_DEV0_EPISODE_KEY": key,
        "RPENT_P1_DEV0_OUT": str(out_root / "runs" / key),
        "RPENT_P1_DEV0_HORIZON": str(AUDIT_HORIZON),
        "RPENT_P1_DEV0_EPISODE_STEP_CAP": str(EPISODE_STEP_CAP),
        "RPENT_P1_DEV0_POLICY": str(POLICY),
        "PYTHONUNBUFFERED": "1",
    })
    cmd = [
        sys.executable, "-m", "rpent.cli.main",
        "--env", "libero",
        "--suite", row["suite"], "--task", str(row["task"]),
        "--seed", str(row["seed"]),
        "--planner", "api", "--model", BASE_ENV["PLANNER_MODEL"],
        "--base-url", BASE_ENV["PLANNER_BASE_URL"],
        "--planner-timeout-s", str(PLANNER_TIMEOUT_S),
        "--max-turns", str(TURNS),
        "--output-dir", str(ep_out),
    ]
    return cmd, env, ep_out


def _summarize(row: dict, out_root: Path, rc: int, wall_s: float) -> dict:
    """从事件文件提取该 episode 的四臂账目摘要(分析脚本再出统计)。"""
    key = row["episode_key"]
    f = out_root / "runs" / key / "p1_dev0_events.jsonl"
    s = {"episode_key": key, "task": row["task"], "seed": row["seed"],
         "arm": row["arm"], "subprocess_rc": rc, "wall_s": round(wall_s, 1),
         "triggered": False, "decision": None, "action_kind": None,
         "probe_env_steps": None, "action_env_steps": None,
         "audit_kind": None, "audit_check_success": None,
         "env_steps_total": None, "episode_end": False, "hook_errors": 0}
    if not f.is_file():
        s["status"] = "NO_EVENTS_FILE"
        return s
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        ev = e.get("ev")
        if ev == "trigger":
            s["triggered"] = True
            s["trigger_step_idx"] = e.get("step_idx")
            s["trigger_env_steps"] = e.get("env_steps")
        elif ev == "probe":
            s["probe_env_steps"] = e.get("env_steps_cost")
            s["probe_wall_s"] = e.get("wall_s")
        elif ev == "decision":
            s["decision"] = e.get("decision")
            s["rationale_code"] = e.get("rationale_code")
        elif ev == "action":
            s["action_kind"] = e.get("kind")
            s["abstain_fallback"] = e.get("abstain_fallback")
            s["action_env_steps"] = e.get("env_steps_cost")
            s["action_wall_s"] = e.get("wall_s")
        elif ev == "audit":
            s["audit_kind"] = e.get("kind")
            s["audit_overshoot_env_steps"] = e.get("overshoot_env_steps")
            s["audit_check_success"] = (e.get("audit_only") or {}).get(
                "check_success")
        elif ev == "episode_end":
            s["episode_end"] = True
            s["env_steps_total"] = e.get("env_steps_total")
        elif ev == "hook_error":
            s["hook_errors"] += 1
    s["status"] = ("COMPLETED" if s["episode_end"]
                   else ("TRIGGERED_INCOMPLETE" if s["triggered"]
                         else "INFRA_NO_TRIGGER"))
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", type=Path,
                    default=Path("/workspace/yjx/rpent_data/p1_dev0"))
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    ap.add_argument("--episodes", type=int, default=MAX_EPISODES)
    ap.add_argument("--wall-budget-s", type=int, default=MAX_WALL_S)
    ap.add_argument("--gpu-budget-s", type=int, default=MAX_GPU_S)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="仅限资源检查误报时人工确认后使用")
    args = ap.parse_args()

    rows = _load_manifest()
    args.workers = min(args.workers, MAX_WORKERS)
    args.episodes = min(args.episodes, MAX_EPISODES, len(rows))
    out_root: Path = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_log_path = out_root / f"run_{ts}.jsonl"
    fh = None if args.dry_run else run_log_path.open("a", encoding="utf-8")

    # ---- preflight + 锁 ----
    if not args.dry_run:
        if not args.skip_preflight:
            rc = subprocess.run(["bash", PREFLIGHT], capture_output=True)
            if rc.returncode != 0:
                sys.exit(f"FATAL: dev_preflight refuse (rc={rc.returncode}); "
                         "资源紧张,不要硬跑")
        _acquire_lock()

    t0 = time.time()
    lock = threading.Lock()
    budget = {"episodes": 0, "gpu_s": 0.0}
    summaries: list[dict] = []
    infra_storm = {"consecutive_no_events": 0, "abort": threading.Event()}

    # ---- 恢复状态判定(启动前一次性)----
    plan = []
    for row in rows:
        if len(plan) >= args.episodes:
            break
        state = _events_state(out_root / "runs" / row["episode_key"])
        if state == "COMPLETED":
            cost = _episode_cost_s(out_root / "runs" / row["episode_key"])
            budget["episodes"] += 1
            budget["gpu_s"] += cost
            summaries.append({"episode_key": row["episode_key"],
                              "arm": row["arm"], "status": "COMPLETED_RESUMED",
                              "wall_s": round(cost, 1)})
        elif state == "CENSORED_NO_RERUN":
            cost = _episode_cost_s(out_root / "runs" / row["episode_key"])
            budget["episodes"] += 1
            budget["gpu_s"] += cost
            summaries.append({"episode_key": row["episode_key"],
                              "arm": row["arm"],
                              "status": "CENSORED_NO_RERUN",
                              "wall_s": round(cost, 1)})
        else:
            plan.append((row, state))
    _log(fh, run_log_path, {
        "ev": "run_start", "ts": ts, "dry_run": args.dry_run,
        "manifest_sha256": json.loads(SEAL.read_text())["sha256"],
        "budgets": {"episodes": args.episodes, "workers": args.workers,
                    "wall_s": args.wall_budget_s, "gpu_s": args.gpu_budget_s},
        "frozen": {"turns": TURNS, "planner_timeout_s": PLANNER_TIMEOUT_S,
                   "audit_horizon_env_steps": AUDIT_HORIZON,
                   "episode_step_cap": EPISODE_STEP_CAP,
                   "gl": "osmesa"},
        "resume": {"already_counted": len(summaries),
                   "to_run": len(plan),
                   "states": [s for _, s in plan]},
    })

    def _budget_ok() -> tuple[bool, str]:
        if budget["episodes"] >= args.episodes:
            return False, "EPISODE_BUDGET"
        if time.time() - t0 + 900 > args.wall_budget_s:
            return False, "WALL_BUDGET"      # 预留一个 episode 启动裕量
        if budget["gpu_s"] + 900 > args.gpu_budget_s:
            return False, "GPU_BUDGET"
        return True, ""

    def _run_one(row: dict, state: str) -> dict:
        cmd, env, ep_out = _episode_cmd(row, out_root, ts)
        if args.dry_run:
            printable = {k: (v if "KEY" not in k else "***")
                         for k, v in env.items() if k.startswith(("RPENT_", "MUJOCO", "HF_"))}
            _log(fh, run_log_path, {"ev": "dry_run_cmd", "episode_key":
                                    row["episode_key"], "arm": row["arm"],
                                    "cmd": cmd, "p1_env": printable})
            return {"episode_key": row["episode_key"], "arm": row["arm"],
                    "status": "DRY_RUN"}
        with lock:
            ok, why = _budget_ok()
            if not ok:
                return {"episode_key": row["episode_key"], "arm": row["arm"],
                        "status": f"SKIPPED_{why}"}
            if infra_storm["abort"].is_set():
                return {"episode_key": row["episode_key"], "arm": row["arm"],
                        "status": "SKIPPED_INFRA_ABORT"}
            budget["episodes"] += 1
        _log(fh, run_log_path, {"ev": "episode_start",
                                "episode_key": row["episode_key"],
                                "arm": row["arm"], "prior_state": state,
                                "output_dir": str(ep_out)})
        t_ep = time.time()
        ep_out.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                cmd, cwd=str(REPO), env=env,
                stdout=open(ep_out.parent / f"{row['episode_key']}.stdout.log", "ab"),
                stderr=subprocess.STDOUT,
                timeout=EPISODE_HARD_TIMEOUT_S)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = -9
            _log(fh, run_log_path, {"ev": "episode_timeout",
                                    "episode_key": row["episode_key"],
                                    "hard_timeout_s": EPISODE_HARD_TIMEOUT_S})
        wall = time.time() - t_ep
        with lock:
            budget["gpu_s"] += wall
        summary = _summarize(row, out_root, rc, wall)
        (out_root / "summaries").mkdir(parents=True, exist_ok=True)
        (out_root / "summaries" / f"{row['episode_key']}.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2))
        summaries.append(summary)
        # 连续启动级崩溃(env 未就绪/无事件文件)= 环境级 infra 故障:
        # 连续 4 个即中止剩余 episode,防止 infra 风暴烧穿 manifest。
        with lock:
            if summary.get("status") == "NO_EVENTS_FILE":
                infra_storm["consecutive_no_events"] += 1
            else:
                infra_storm["consecutive_no_events"] = 0
            if (infra_storm["consecutive_no_events"] >= 4
                    and not infra_storm["abort"].is_set()):
                infra_storm["abort"].set()
                _log(fh, run_log_path, {
                    "ev": "infra_abort",
                    "reason": "4 consecutive episodes died before env ready"})
        _log(fh, run_log_path, {"ev": "episode_done", **summary,
                                "budget_now": dict(budget)})
        return summary

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_run_one, row, state) for row, state in plan]
        for f in futures:
            f.result()

    # ---- 汇总 ----
    final = {
        "ev": "run_end", "wall_s_total": round(time.time() - t0, 1),
        "budget_final": dict(budget),
        "episodes": len(summaries),
        "counts": _tally(summaries),
    }
    _log(fh, run_log_path, final)
    if not args.dry_run:
        (out_root / f"run_{ts}_summary.json").write_text(
            json.dumps({"final": final, "summaries": summaries},
                       ensure_ascii=False, indent=2))
        if fh is not None:
            fh.close()
        print(f"[p1_dev0_run] done. summary: {out_root / f'run_{ts}_summary.json'}")
    return 0


def _tally(summaries: list[dict]) -> dict:
    """四臂触发/成本粗账(完整分析由 analysis 脚本出)。"""
    out = {}
    for s in summaries:
        arm = s.get("arm", "?")
        d = out.setdefault(arm, {"n": 0, "triggered": 0, "decisions": {},
                                 "actions": {}, "audited": 0, "completed": 0,
                                 "censored": 0})
        d["n"] += 1
        if s.get("triggered"):
            d["triggered"] += 1
            d["decisions"][s.get("decision") or "?"] = \
                d["decisions"].get(s.get("decision") or "?", 0) + 1
            d["actions"][s.get("action_kind") or "?"] = \
                d["actions"].get(s.get("action_kind") or "?", 0) + 1
            if s.get("audit_kind"):
                d["audited"] += 1
        if s.get("status") == "COMPLETED" or s.get("episode_end"):
            d["completed"] += 1
        if s.get("status") in ("CENSORED_NO_RERUN", "TRIGGERED_INCOMPLETE"):
            d["censored"] += 1
    return out


if __name__ == "__main__":
    sys.exit(main())
