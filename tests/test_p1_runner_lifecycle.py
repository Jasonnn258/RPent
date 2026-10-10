"""P1 runner 生命周期对抗测试(B2/B3,零 GPU/零 episode/零 API)。

覆盖 2026-10-10 性能轮审计出的三条风险路径:
- B2:常驻 vla_server 探活(_persistent_vla_alive)——回归锚:旧实现
  cli.healthz(...) 是 AttributeError,被 except Exception 吞成"恒未就绪",
  --persistent-vla 从未能启动;现在必须真的走 HTTP call("healthz");
- B2:server 死亡(进程死/端口死)→ 探活必须 False;
- B3:_kill_pg 对忽略 SIGTERM 的进程组必须在宽限内升级 SIGKILL;
- B3:子进程 rc≠0 崩溃时 _sweep_if_crashed 必须清扫组内孤儿 daemon;
  rc=0 自然退出必须不动(返回 False,无清扫)。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "p1_dev1a_run", REPO / "scripts" / "p1_dev1a_run.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

PY = sys.executable


class _Handler(BaseHTTPRequestHandler):
    """最小 vla_server 桩:任何 POST /call 都回 ok。"""

    def do_POST(self):  # noqa: N802 - http.server 命名
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        body = json.dumps({"ok": True, "result": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # 静音
        pass


def _start_mock_server() -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _pgid_alive(pgid: int) -> bool:
    try:
        import os

        os.killpg(pgid, 0)
        return True
    except OSError:
        return False


def test_persistent_vla_alive_against_mock_server():
    """活进程 + 活端点 → True;这是 healthz 修正的回归锚。"""
    srv, endpoint = _start_mock_server()
    proc = subprocess.Popen([PY, "-c", "import time; time.sleep(60)"])
    try:
        assert runner._persistent_vla_alive(proc, endpoint) is True
    finally:
        proc.kill()
        proc.wait()
        srv.shutdown()


def test_persistent_vla_dead_endpoint_or_proc():
    """端点死(连接拒绝)或进程死 → False。"""
    proc = subprocess.Popen([PY, "-c", "import time; time.sleep(60)"])
    try:
        # 进程活但端口无人监听:bind 一个再关掉,保证端口死
        import socket

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
        s.close()
        assert runner._persistent_vla_alive(
            proc, f"http://127.0.0.1:{dead_port}") is False
    finally:
        proc.kill()
        proc.wait()
    # 进程死:rc 已收
    dead = subprocess.Popen([PY, "-c", "pass"])
    dead.wait()
    srv, endpoint = _start_mock_server()
    try:
        assert runner._persistent_vla_alive(dead, endpoint) is False
    finally:
        srv.shutdown()


def test_kill_pg_escalates_on_sigterm_ignorer():
    """组内进程忽略 SIGTERM → 宽限内必须 SIGKILL(不能永远等)。"""
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "time.sleep(300)\n"
    )
    proc = subprocess.Popen([PY, "-c", code], start_new_session=True)
    time.sleep(0.5)                       # 让 handler 安装完
    t0 = time.monotonic()
    how = runner._kill_pg(proc.pid, grace_s=1.5)
    proc.wait(timeout=10)
    assert how == "SIGTERM_then_SIGKILL", how
    assert time.monotonic() - t0 < 8
    assert not _pgid_alive(proc.pid)


def _crash_child(with_orphan: bool) -> subprocess.Popen:
    """session-leader 子进程:可选留下忽略 SIGTERM 的孤儿,然后 rc=1 退出。"""
    orphan = (
        "import signal, subprocess, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"subprocess.Popen([sys.executable, '-c', "
        f"'import signal,time\\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\\n"
        f"time.sleep(300)'])\n"
        "time.sleep(0.5)\n"
        "sys.exit(1)\n"
    ) if with_orphan else "import sys; sys.exit(1)\n"
    return subprocess.Popen([PY, "-c", orphan], start_new_session=True)


def test_sweep_if_crashed_kills_orphans():
    """rc=1 崩溃 + 组内孤儿 daemon → 清扫后组必须消亡。"""
    proc = _crash_child(with_orphan=True)
    proc.wait(timeout=10)
    pgid = proc.pid
    assert _pgid_alive(pgid)              # 孤儿还在(这就是旧逻辑的泄漏)
    swept = runner._sweep_if_crashed(proc, pgid, None, "test_key")
    assert swept is True
    deadline = time.monotonic() + 12
    while _pgid_alive(pgid) and time.monotonic() < deadline:
        time.sleep(0.3)
    assert not _pgid_alive(pgid)          # SIGKILL 升级后孤儿也活不成


def test_sweep_skips_clean_exit():
    """rc=0 自然退出 → 不清扫(返回 False)。"""
    proc = subprocess.Popen(
        [PY, "-c", "import sys; sys.exit(0)"], start_new_session=True)
    proc.wait(timeout=10)
    assert runner._sweep_if_crashed(proc, proc.pid, None, "k") is False
