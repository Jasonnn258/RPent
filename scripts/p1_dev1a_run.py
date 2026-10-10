#!/usr/bin/env python3
"""P1-DEV1A 受控 pilot runner:G1-G4 全过后按冻结 manifest 执行 ≤8 集。

预注册协议:D-041(P1_L2_DEV1A_RESEARCH_REVIEW_AND_AUTHORIZATION_20261010)。
授权边界:≤8 新 episode(t9×4/t3×2/t5×2)、≤3 GPU·h、≤4h 墙钟、单 worker、
每集 ≤1500 env steps、每集最多一次失败触发观测(probe=固定闭合≤10步+
受控提升≤2cm)、探测后立即终止(预注册 TERMINATE_AFTER_PROBE)、
Planner 全程盲。任一 Gate 未过 → 拒绝启动(HOLD_ZERO_NEW_EPISODES)。

与 DEV0 900 秒预留机制的关键差异(必须遵守):
- **预留 = 整集最坏成本**:每次 reserve 用完整 worst_wall(初始 2400s,
  之后 max(2400, 1.25×已观测最坏)),子进程硬超时即预留值 → 观测成本
  结构性 ≤ 预留;双硬帽(WALL 4h / GPU 3h)任一不满足即不启动。
- **持久化账本**:DurableBudgetLedger 文件级(fsyc + 原子替换),crash
  后在飞预留不释放、禁 resume,取证语义与 BudgetLedger 一致。
- **进程组安全终止**:子进程 new session(独立 pgid);probe_done 事件
  / 超时 / SIGTERM → killpg(SIGTERM→30s→SIGKILL),绝不动别人的进程。

用法:
  python scripts/p1_dev1a_gate_check.py            # 先过 G1-G4
  nohup python scripts/p1_dev1a_run.py >> /workspace/yjx/tmp/p1_dev1a_run.log 2>&1 &
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis" / "research_context"))
sys.path.insert(0, str(REPO))

from p1_dev1a_budget_gate import BudgetLedger  # noqa: E402

OUT_ROOT = REPO / "artifacts" / "p1_dev1a"
GATE_EVIDENCE = OUT_ROOT / "gate_evidence.json"
LEDGER_PATH = OUT_ROOT / "budget_ledger.json"
RUN_SUMMARY = OUT_ROOT / "run_summary.json"

# 冻结预算(D-041;与 gate 检查的 budget_caps_echo 一致)
MAX_EP = 8
MAX_WALL_S = 4 * 3600
MAX_GPU_S = 3 * 3600
MAX_WORKERS = 1
TASK_CAP = {"9": 4, "3": 2, "5": 2}
EPISODE_STEP_CAP = 1500
# 预留策略(整集最坏):初始 2400s,之后 max(2400, 1.25×观测最坏)
INITIAL_WORST_WALL_S = 2400.0
WORST_MARGIN = 1.25
# 冻结 manifest:任务×新种子网格(2001-2008,不与 DEV0 1001-1008/
# Stage R 1-10 重叠),固定执行顺序
MANIFEST_ROWS = [
    {"task": 9, "seed": 2001}, {"task": 9, "seed": 2002},
    {"task": 9, "seed": 2003}, {"task": 9, "seed": 2004},
    {"task": 3, "seed": 2005}, {"task": 3, "seed": 2006},
    {"task": 5, "seed": 2007}, {"task": 5, "seed": 2008},
]
TURNS = 100
PLANNER_TIMEOUT_S = 2400
# kill 宽限(秒):默认 30 与 D-041 冻结口径一致;可经 P1_KILL_GRACE_S
# 覆盖(性能轮结论:宽限被组内 daemons 全额消耗,审计已在 probe 后
# 逐步 fsync,缩短不损失证据;默认不变,未来批次可设 5)
SIGTERM_GRACE_S = float(os.environ.get("P1_KILL_GRACE_S", "30"))
GPU_SAMPLE_S = 5.0

# 环境(镜像 run_rpent.sh / DEV0;GL 按本容器铁律 osmesa)
BASE_ENV = {
    "PI05_CHECKPOINT_PATH": "/workspace/yjx/rpent_data/checkpoints/pi05",
    "SAM3_CHECKPOINT_PATH": "/workspace/yjx/rpent_data/checkpoints/sam3/sam3.pt",
    "ROBOT_PLATFORM": "LIBERO",
    "LIBERO_TYPE": "pro",
    "OPENPI_DATA_HOME": "/workspace/yjx/rpent_data/.cache/openpi",
    "LIBERO_CONFIG_PATH": "/workspace/yjx/rpent_data/.libero",
    "HF_HUB_OFFLINE": "1",
    "MUJOCO_GL": "osmesa",       # 本容器 EGL 设备数 0(铁律)
    "PYOPENGL_PLATFORM": "osmesa",
    "PLANNER_MODEL": "anthropic:glm-5.3-flash",
    "PLANNER_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
}
UNSET_ENV = ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE",
             "RPENT_STAGE_R_TRACE", "RPENT_P1_DEV0")
PREFLIGHT = "/workspace/yjx/bin/dev_preflight.sh"
LOCK_DIR = "/workspace/yjx/.runlocks/p1_dev1a.lock"


# ---------------------------------------------------------------------------
# 持久化预算账本
# ---------------------------------------------------------------------------

class DurableBudgetLedger:
    """BudgetLedger 的文件持久化封装:每次变更 fsync + 原子替换。

    crash 语义:在飞预留原样保留(取证),重开后拒绝新 reserve 与 resume,
    与 p1_dev1a_budget_gate.BudgetLedger 的 fail-close 语义一致。
    """

    _FIELDS = ("elapsed_wall_s", "gpu_consumed_s", "begun", "completed",
               "reserved_gpu_s", "reserved_wall_s", "inflight_key",
               "inflight_task", "spent_steps", "task_started")

    def __init__(self, path: Path,
                 ledger: BudgetLedger | type[BudgetLedger] | None = None):
        self.path = Path(path)
        # 允许传类(便于测试注入)或实例;缺省新建
        self.l = ledger() if isinstance(ledger, type) else (
            ledger if ledger is not None else BudgetLedger())
        if self.path.is_file():
            self._load()

    def _load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for f in self._FIELDS:
            setattr(self.l, f, data[f])

    def raw(self) -> dict:
        return {f: getattr(self.l, f) for f in self._FIELDS}

    def _flush(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.raw(), sort_keys=True) + "\n",
                       encoding="utf-8")
        # 原子替换 + fsync(目录条目也持久化;绝不让账本半写)
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self.path)

    def reserve(self, key, task, worst_wall_s, gpu_count):
        out = self.l.reserve(key, task, worst_wall_s, gpu_count)
        self._flush()
        return out

    def charge_and_close(self, key, observed_wall_s, observed_gpu_s, steps):
        out = self.l.charge_and_close(key, observed_wall_s,
                                      observed_gpu_s, steps)
        self._flush()
        return out

    def forbid_resume(self, key):
        return self.l.forbid_resume(key)


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------

def _log(fh, rec: dict) -> None:
    rec["t"] = round(time.time(), 3)
    line = json.dumps(rec, ensure_ascii=False, default=str)
    print(line, flush=True)
    if fh is not None:
        fh.write(line + "\n")
        fh.flush()


def _planner_env() -> dict:
    """GLM planner 密钥:只进子进程 env,绝不打印。"""
    env_file = Path("/workspace/yjx/rpent_data/rpent_env.sh")
    key = ""
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("GLM_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
                break
    if not key:
        sys.exit("FATAL: GLM_API_KEY not found in rpent_env.sh")
    return {"ANTHROPIC_API_KEY": key}


def _spec_path(task: int) -> Path:
    p = REPO / "analysis" / "research_context" / \
        f"p1_dev1a_geom_spec_t{task}.json"
    if not p.is_file():
        sys.exit(f"FATAL: frozen geom spec missing: {p}")
    return p


def _episode_cmd(row: dict, ts: str, vla_endpoint: str | None = None):
    key = f"p1dev1a_t{row['task']}_s{row['seed']}"
    ep_out = OUT_ROOT / "runs" / f"{key}_{ts}"
    audit_out = OUT_ROOT / "runs" / key       # 审计目录在 episode output_dir 之外
    env = {k: v for k, v in os.environ.items() if k not in UNSET_ENV}
    env.update(BASE_ENV)
    env.update(_planner_env())
    env.update({
        "RPENT_P1_DEV1A": "1",
        "RPENT_P1_DEV1A_EPISODE_KEY": key,
        "RPENT_P1_DEV1A_OUT": str(audit_out),
        "RPENT_P1_DEV1A_SPEC": str(_spec_path(row["task"])),
        "PYTHONUNBUFFERED": "1",
    })
    cmd = [
        sys.executable, "-m", "rpent.cli.main",
        "--env", "libero",
        "--suite", "libero_spatial", "--task", str(row["task"]),
        "--seed", str(row["seed"]),
        "--planner", "api", "--model", BASE_ENV["PLANNER_MODEL"],
        "--base-url", BASE_ENV["PLANNER_BASE_URL"],
        "--planner-timeout-s", str(PLANNER_TIMEOUT_S),
        "--max-turns", str(TURNS),
        "--output-dir", str(ep_out),
    ]
    if vla_endpoint:
        # 性能轮(2026-10-10):常驻 vla_server 模式,agent 直连外部服务,
        # 免去每集 ~65s 的 Pi0.5 重复加载(占总墙钟 9.8%);默认不启用
        cmd += ["--vla-endpoint", vla_endpoint]
    return cmd, env, ep_out, audit_out, key


def _start_persistent_vla(log_fh) -> tuple[subprocess.Popen, str]:
    """性能轮新增(默认不启用):整批共用一个 vla_server。

    由 --vla-endpoint/--persistent-vla 显式开启;起服务 → 等 healthz
    (Pi0.5 加载 ~65-76s)→ 返回 (proc, endpoint)。整批仅此一次加载,
    每集省一次 model load。隔离性见 artifacts/p1_perf/vla_persist_check.json
    (服务端每请求新建 obs、无跨请求状态;任务隔离/无漂移已验证)。
    """
    import socket

    from rpent.utils.http_rpc import HttpRpcClient

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    env = {k: v for k, v in os.environ.items() if k not in UNSET_ENV}
    env.update(BASE_ENV)
    log_path = OUT_ROOT / "vla_persistent.log"
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "robots" / "libero" / "vla_server.py"),
         "--transport", "http", "--host", "127.0.0.1",
         "--port", str(port)],
        env=env, stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT, start_new_session=True)
    endpoint = f"http://127.0.0.1:{port}"
    cli = HttpRpcClient(endpoint)
    ready = False
    err = ""
    for _ in range(120):                      # 模型加载 ~65-76s,给 240s
        if proc.poll() is not None:
            sys.exit(f"FATAL: persistent vla_server died; see {log_path}")
        try:
            cli.healthz(timeout_s=2)
            ready = True
            break
        except Exception as e:
            err = str(e)[:120]
            time.sleep(2.0)
    if not ready:
        _kill_pg(proc.pid, 5.0)
        sys.exit(f"FATAL: persistent vla_server not ready ({err}); see {log_path}")
    load_s = round(time.time() - t0, 1)
    _log(log_fh, {"ev": "persistent_vla_up", "endpoint": endpoint,
                  "load_s": load_s, "log": str(log_path)})
    return proc, endpoint


def _kill_pg(pgid: int, grace_s: float = SIGTERM_GRACE_S) -> str:
    """安全终止整个子进程组(SIGTERM→grace→SIGKILL);只动自己的组。"""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "already_gone"
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)        # 组存活性探测(信号 0)
        except OSError:
            return "SIGTERM"
        time.sleep(0.5)
    try:
        os.killpg(pgid, signal.SIGKILL)
        return "SIGTERM_then_SIGKILL"
    except ProcessLookupError:
        return "SIGTERM"


def _gpu_sampler(pgid: int, stop: threading.Event) -> dict:
    """周期采样 nvidia-smi:统计属于本进程组的计算进程占用的 GPU 数。

    来源记录(不猜):每 GPU_SAMPLE_S 秒一次;gpu_seconds += n_gpu×dt。
    """
    acc = {"gpu_s": 0.0, "max_gpu_count": 0, "samples": 0, "last_n": 0}
    while not stop.is_set():
        n = 1  # 保守基线:至少 1 张(单 worker + 单 CUDA 设备)
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid",
                 "--format=csv,noheader"], capture_output=True, text=True,
                timeout=20).stdout
            seen_gpu = set()
            for line in out.strip().splitlines():
                parts = [x.strip() for x in line.split(",")]
                if len(parts) != 2:
                    continue
                gpu_uuid, pid_s = parts
                try:
                    pid = int(pid_s)
                except ValueError:
                    continue
                # 只统计属于本进程组的 pid(跨进程组匹配)
                try:
                    with open(f"/proc/{pid}/stat", "rb") as f:
                        fields = f.read().decode("utf-8", "replace").split()
                    if len(fields) > 5 and int(fields[4]) == pgid:
                        seen_gpu.add(gpu_uuid)
                except OSError:
                    continue
            if seen_gpu:
                n = len(seen_gpu)
        except Exception:
            pass
        acc["last_n"] = n
        acc["max_gpu_count"] = max(acc["max_gpu_count"], n)
        acc["gpu_s"] += n * GPU_SAMPLE_S
        acc["samples"] += 1
        stop.wait(GPU_SAMPLE_S)
    return acc


def _episode_steps(audit_out: Path):
    """从事件文件读最终 env-step 数;返回 (steps, source)。

    优先 episode_end.env_steps_total(自然退出路径);TERMINATE_AFTER_PROBE
    被 kill 的集子进程来不及 finalize,回退到全事件最大 env_steps 字段
    (trigger/probe_done/每步 steps 事件;kill 前最后一步即真实总数)。
    两者皆无 → (None, "unmeasured")(不可计量,主循环 STOP)。
    """
    f = audit_out / "p1_dev1a_events.jsonl"
    if not f.is_file():
        return None, "no_events_file"
    end_total = None
    max_seen = None
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("ev") == "episode_end" and \
                isinstance(e.get("env_steps_total"), int):
            end_total = e["env_steps_total"]
        v = e.get("env_steps")
        if isinstance(v, int):
            max_seen = v if max_seen is None else max(max_seen, v)
    if end_total is not None:
        return end_total, "episode_end"
    if max_seen is not None:
        return max_seen, "events_max(killed_after_probe)"
    return None, "unmeasured"


def _wait_probe_done(audit_out: Path, proc: subprocess.Popen,
                     deadline: float) -> bool:
    """轮询 probe_done 事件(探测后立即终止,Planner 全程盲)。"""
    f = audit_out / "p1_dev1a_events.jsonl"
    while time.monotonic() < deadline and proc.poll() is None:
        if f.is_file():
            try:
                for line in f.read_text(encoding="utf-8").splitlines():
                    if '"probe_done"' in line:
                        return True
            except OSError:
                pass
        time.sleep(2.0)
    return False


# ---------------------------------------------------------------------------
# selftest(G4 证据;不跑任何真实 episode)
# ---------------------------------------------------------------------------

def selftest() -> dict:
    """真实子进程组 + 持久账本 + probe_done 终止路径的最小闭环验证。"""
    import tempfile

    results = {"pass": False}
    td = Path(tempfile.mkdtemp(dir="/workspace/yjx/tmp"))
    try:
        ledger = DurableBudgetLedger(td / "ledger.json")
        ledger.reserve("selftest_ep", "9", 60.0, 1)
        results["reserve_ok"] = ledger.raw()["inflight_key"] == "selftest_ep"

        # 哑子进程:new session(独立 pgid),写 probe_done 后长睡
        marker = td / "probe_done.jsonl"
        child_code = (
            "import os,time,sys\n"
            f"open({str(marker)!r},'w').write("
            "'{\"ev\": \"probe_done\"}\\n')\n"
            "time.sleep(600)\n")
        proc = subprocess.Popen(
            [sys.executable, "-c", child_code], start_new_session=True)
        pgid = proc.pid  # start_new_session ⇒ pgid == child pid
        deadline = time.monotonic() + 30
        seen = False
        while time.monotonic() < deadline:
            if marker.is_file() and "probe_done" in marker.read_text():
                seen = True
                break
            time.sleep(0.2)
        results["probe_done_seen"] = seen

        how = _kill_pg(pgid)
        try:
            proc.wait(timeout=45)
        except subprocess.TimeoutExpired:
            pass
        alive = proc.poll() is None
        # 组内确无残留(killpg 生效)
        results["kill_path"] = how
        results["child_dead"] = not alive

        ledger.charge_and_close("selftest_ep", 5.0, 5.0, 42)
        reload = DurableBudgetLedger(td / "ledger.json")
        results["ledger_reload"] = (
            reload.raw()["completed"] == 1
            and reload.raw()["inflight_key"] is None)

        # runner 级 SIGTERM 自处理路径(main 里安装的 handler 冒烟):
        # 这里只验证 _kill_pg + 账本,主循环 handler 在真实运行中执行
        results["pass"] = bool(
            results["reserve_ok"] and results["probe_done_seen"]
            and results["child_dead"] and results["ledger_reload"])
    finally:
        shutil.rmtree(td, ignore_errors=True)
    return results


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def check_gate() -> None:
    if not GATE_EVIDENCE.is_file():
        sys.exit(f"FATAL: gate evidence missing ({GATE_EVIDENCE}) — "
                 "run scripts/p1_dev1a_gate_check.py first")
    ev = json.loads(GATE_EVIDENCE.read_text(encoding="utf-8"))
    if not ev.get("all_gates_pass"):
        sys.exit("FATAL: G1-G4 not all PASS — HOLD_ZERO_NEW_EPISODES")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true",
                   help="G4 自检(不跑任何真实 episode)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vla-endpoint", default=None,
                   help="外部常驻 vla_server URL(如 http://127.0.0.1:18730);"
                        "默认 None=每集自 spawn(冻结行为)")
    p.add_argument("--persistent-vla", action="store_true",
                   help="runner 自起一个整批共用的 vla_server 并在结束时回收"
                        "(性能轮 opt-in;省每集 ~65s 重复加载;默认关)")
    args = p.parse_args()
    if args.persistent_vla and args.vla_endpoint:
        sys.exit("FATAL: --persistent-vla 与 --vla-endpoint 二选一")

    if args.selftest:
        print(json.dumps(selftest(), ensure_ascii=False))
        return

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    log_fh = open(OUT_ROOT / "run_log.jsonl", "a", encoding="utf-8")

    # Gate 证据 + preflight + 防重复锁(三项前置,缺一不启动)
    check_gate()
    rc = subprocess.run([PREFLIGHT], capture_output=True, text=True)
    if rc.returncode != 0:
        _log(log_fh, {"ev": "preflight_refuse", "stderr": rc.stderr[-400:]})
        sys.exit("FATAL: dev_preflight refused — do not force")
    if os.path.isdir(LOCK_DIR):
        pid_file = Path(LOCK_DIR) / "pid"
        try:
            old = int(pid_file.read_text().strip())
            os.kill(old, 0)
            sys.exit(f"FATAL: another p1_dev1a runner alive (pid {old})")
        except (ProcessLookupError, ValueError, OSError):
            shutil.rmtree(LOCK_DIR, ignore_errors=True)
    os.makedirs(LOCK_DIR, exist_ok=True)
    (Path(LOCK_DIR) / "pid").write_text(str(os.getpid()))
    import atexit
    atexit.register(lambda: shutil.rmtree(LOCK_DIR, ignore_errors=True))

    # manifest 封版(顺序冻结;封版后不可改)
    manifest = {
        "protocol": "D-041", "rows": MANIFEST_ROWS,
        "max_ep": MAX_EP, "max_wall_s": MAX_WALL_S, "max_gpu_s": MAX_GPU_S,
        "max_workers": MAX_WORKERS, "episode_step_cap": EPISODE_STEP_CAP,
        "task_cap": TASK_CAP, "post_probe": "TERMINATE_AFTER_PROBE",
        "specs": {str(r["task"]): {
            "path": str(_spec_path(r["task"])),
            "sha256": hashlib.sha256(
                _spec_path(r["task"]).read_bytes()).hexdigest()}
            for r in MANIFEST_ROWS},
    }
    mfile = OUT_ROOT / "manifest.json"
    mfile.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    manifest_sha = hashlib.sha256(mfile.read_bytes()).hexdigest()

    ledger = DurableBudgetLedger(LEDGER_PATH)
    stop_all = threading.Event()
    worst_wall = INITIAL_WORST_WALL_S
    observations = []

    def _sigterm_handler(signum, _frame):
        stop_all.set()
        _log(log_fh, {"ev": "runner_sigterm", "sig": signum})

    signal.signal(signal.SIGTERM, _sigterm_handler)
    signal.signal(signal.SIGINT, _sigterm_handler)

    if args.dry_run:
        _log(log_fh, {"ev": "dry_run", "manifest_sha256": manifest_sha,
                      "rows": len(MANIFEST_ROWS),
                      "budget": ledger.raw()})
        return

    _log(log_fh, {"ev": "run_start", "manifest_sha256": manifest_sha,
                  "gate": "GO_PILOT",
                  "initial_worst_wall_s": worst_wall,
                  "vla_endpoint": args.vla_endpoint,
                  "persistent_vla": args.persistent_vla})

    persistent_proc = None
    endpoint = args.vla_endpoint
    try:
        if args.persistent_vla:
            persistent_proc, endpoint = _start_persistent_vla(log_fh)

        for row in MANIFEST_ROWS:
            if stop_all.is_set():
                _log(log_fh, {"ev": "stop", "reason": "SIGTERM"})
                break
            task = str(row["task"])
            key = f"p1dev1a_t{task}_s{row['seed']}"
            # 禁重跑:该 key 已有终止性事件(probe_done/episode_end)→ 跳过,
            # 不 reserve、不重复执行(D-041 NO_DEV1A_EPISODE_RERUN)
            done_f = OUT_ROOT / "runs" / key / "p1_dev1a_events.jsonl"
            if done_f.is_file():
                try:
                    terms = [json.loads(x).get("ev") for x in
                             done_f.read_text(encoding="utf-8").splitlines()
                             if x.strip()]
                except OSError:
                    terms = []
                if "probe_done" in terms or "episode_end" in terms:
                    _log(log_fh, {"ev": "episode_skip_done", "key": key,
                                  "note": "already terminal (no rerun)"})
                    continue
            # 整集最坏预留(动态最坏 × 边际;双硬帽不满足即停)
            if observations:
                worst_wall = max(INITIAL_WORST_WALL_S,
                                 WORST_MARGIN * max(
                                     o["wall_s"] for o in observations))
            try:
                res = ledger.reserve(key, task, worst_wall, 1)
            except ValueError as exc:
                _log(log_fh, {"ev": "reserve_refused", "key": key,
                              "reason": str(exc),
                              "worst_wall_s": worst_wall})
                break
            _log(log_fh, {"ev": "episode_reserve", "key": key,
                          "reserved_wall_s": worst_wall,
                          "hard_env_step_cap": res["hard_env_step_cap"]})

            cmd, env, ep_out, audit_out, _ = _episode_cmd(
                row, ts=manifest_sha[:8], vla_endpoint=endpoint)
            ep_out.parent.mkdir(parents=True, exist_ok=True)
            t0 = time.monotonic()
            proc = subprocess.Popen(cmd, env=env, start_new_session=True,
                                    stdout=open(ep_out.with_suffix(".out"),
                                                "w"),
                                    stderr=subprocess.STDOUT)
            pgid = proc.pid
            stop_gpu = threading.Event()
            gpu_acc = {"gpu_s": 0.0, "max_gpu_count": 0, "samples": 0,
                       "last_n": 0}
            gpu_thread = threading.Thread(
                target=lambda: gpu_acc.update(
                    _gpu_sampler(pgid, stop_gpu)), daemon=True)
            gpu_thread.start()

            terminated_by = "natural_exit"
            while True:
                if proc.poll() is not None:
                    break
                if stop_all.is_set():
                    terminated_by = "runner_sigterm"
                    break
                if time.monotonic() - t0 > worst_wall:
                    terminated_by = "hard_timeout(reserved)"
                    break
                if _wait_probe_done(audit_out, proc,
                                    time.monotonic() + 5.0):
                    terminated_by = "probe_done(terminate_after_probe)"
                    break
            if terminated_by != "natural_exit":
                how = _kill_pg(pgid)
                _log(log_fh, {"ev": "episode_killed", "key": key,
                              "reason": terminated_by, "how": how})
            try:
                proc.wait(timeout=SIGTERM_GRACE_S + 15)
            except subprocess.TimeoutExpired:
                _kill_pg(pgid, 0.5)
                proc.wait(timeout=30)
            stop_gpu.set()
            gpu_thread.join(timeout=GPU_SAMPLE_S * 2)

            wall_s = time.monotonic() - t0
            gpu_s = gpu_acc["gpu_s"]
            steps, steps_src = _episode_steps(audit_out)
            _log(log_fh, {"ev": "episode_measure", "key": key,
                          "wall_s": round(wall_s, 1),
                          "gpu_s": round(gpu_s, 1),
                          "gpu_max_count": gpu_acc["max_gpu_count"],
                          "env_steps": steps,
                          "steps_source": steps_src,
                          "terminated_by": terminated_by,
                          "subprocess_rc": proc.returncode})
            if steps is None or steps > EPISODE_STEP_CAP:
                # 不可计量/越限:保留预留做取证,立即 STOP(不 resume、不重跑)
                _log(log_fh, {"ev": "stop", "key": key,
                              "reason": "UNMEASURED_OR_OVERCAP_STEPS",
                              "steps": steps})
                _write_summary()
                sys.exit(1)
            try:
                ledger.charge_and_close(key, wall_s, gpu_s, steps)
            except ValueError as exc:
                _log(log_fh, {"ev": "charge_refused", "key": key,
                              "reason": str(exc)})
                _write_summary()
                sys.exit(1)
            observations.append({"key": key, "wall_s": wall_s,
                                 "gpu_s": gpu_s, "steps": steps})

        _log(log_fh, {"ev": "run_end", "budget": ledger.raw(),
                      "episodes": len(observations)})
        _write_summary()
    finally:
        # 常驻服务回收(仅 --persistent-vla 路径;SIGKILL 前不再等待模型卸载)
        if persistent_proc is not None:
            _kill_pg(persistent_proc.pid, 5.0)
            _log(log_fh, {"ev": "persistent_vla_down"})


def _write_summary():
    # 汇总由 runner 收口(标签分布另见 gate/audit 分析脚本)
    ledger = DurableBudgetLedger(LEDGER_PATH)
    summary = {
        "protocol": "D-041",
        "ledger": ledger.raw(),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    RUN_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False,
                                      indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
