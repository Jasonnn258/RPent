#!/usr/bin/env python3
"""P1-DEV1A hook 集成冒烟:真 facade env + 真 maybe_probe 路径(无 GPU)。

目的:在烧掉任何真实 episode 之前,验证 rpent/utils/p1_dev1a.py 的完整
接线 —— 触发资格 → t_trigger 快照 → set_gripper 闭合 → t_close_end 快照
→ 受控提升采样 → t_lift_end 快照 → 冻结判据标签 → probe_done 事件。
使用 seed 0(不在 pilot 种子网格 2001-2008 内),状态 save/restore 复原,
不触任何 planner/Memory/策略路径。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

# GL 铁律(osmesa)须在任何 mujoco 导入前
os.environ["MUJOCO_GL"] = "osmesa"
os.environ["PYOPENGL_PLATFORM"] = "osmesa"
for k in ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE"):
    os.environ.pop(k, None)
os.environ.setdefault("LIBERO_TYPE", "pro")
os.environ.setdefault("ROBOT_PLATFORM", "LIBERO")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from robots.libero.env_server import LiberoEnvFacade, make_env  # noqa: E402

SPEC = REPO / "analysis" / "research_context" / "p1_dev1a_geom_spec_t9.json"
OUT = Path("/workspace/yjx/tmp/p1_dev1a_hook_smoke")


class _PrimitivesStub:
    """给 hook 的最小 primitives 表面(生产为 LiberoPrimitives,同签名)。"""

    def __init__(self, facade):
        self.env = facade
        self._last_obs = {"main_images": None}

    @property
    def _last_obs_eef_pos(self):
        import numpy as np

        return np.asarray(self.env.raw_obs()["robot0_eef_pos"],
                          dtype=float)

    def set_gripper(self, *, gripper: float, steps: int) -> dict:
        import numpy as np

        for _ in range(steps):
            a = np.zeros(7, dtype=np.float32)
            a[6] = gripper
            self.env.step(a)
            # 镜像生产:LiberoEnvClient.step 内的计步钩子
            from rpent.utils import p1_dev1a
            p1_dev1a.count_env_steps(1)
        return {"name": "set_gripper", "gripper": gripper, "steps": steps}

    def _step_env(self, action) -> None:
        self.env.step(action)
        from rpent.utils import p1_dev1a
        p1_dev1a.count_env_steps(1)


class _ToolkitStub:
    def __init__(self, facade):
        self._primitives = _PrimitivesStub(facade)


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "RPENT_P1_DEV1A": "1",
        "RPENT_P1_DEV1A_EPISODE_KEY": "hook_smoke_t9_s0",
        "RPENT_P1_DEV1A_OUT": str(OUT),
        "RPENT_P1_DEV1A_SPEC": str(SPEC),
    })
    from rpent.utils import p1_dev1a

    f = make_env(9, 0, max_episode_steps=1500)
    facade = LiberoEnvFacade(f, meta={"task": 9, "seed": 0})
    facade.reset()
    facade.episode_terminated = False   # 生产侧由 LiberoEnvClient 维护
    facade.episode_truncated = False
    tk = _ToolkitStub(facade)

    st0 = __import__("numpy").asarray(facade.save_state())
    steps_before = facade._step_count

    t0 = time.monotonic()
    ret = p1_dev1a.maybe_probe(
        tk, "pi0_pick", {"target": "akita_black_bowl_1"},
        {"success": False, "reason": "smoke"}, step_idx=1, elapsed=0.1)
    wall = round(time.monotonic() - t0, 1)

    facade.restore_state(st0)
    f.close()

    # ---- 断言:事件链完整 + 快照合法 + 同刻 + 步数单调 ----
    events = [json.loads(x) for x in
              (OUT / "p1_dev1a_events.jsonl").read_text("utf-8").splitlines()
              if x.strip()]
    kinds = [e.get("ev") for e in events]
    probe = next((e for e in events if e.get("ev") == "probe"), None)
    checks = {
        "maybe_probe_returns_none_blind": ret is None,
        "events_order_ok": (
            kinds[:2] == ["init", "trigger"] and "probe" in kinds
            and "probe_done" in kinds),
        "probe_present": probe is not None,
        "restored_state_ok": bool(
            (__import__("numpy").asarray(facade.save_state())
             == st0).all()),
        "step_accounting": probe and {
            "env_steps_cost": probe["env_steps_cost"],
            "server_steps_used": facade._step_count - steps_before - (
                1),  # restore_state 不计步;最后一次 save_state 无步进
        },
        "wall_s": wall,
    }
    if probe:
        snaps = probe["audit_snapshots"]
        seq = [("t_trigger", snaps["t_trigger"]),
               ("t_close_end", snaps["t_close_end"])] + \
              [(f"lift_{s['want_dz']}", s["snap"])
               for s in snaps["lift_samples"]] + \
              [("t_lift_end", snaps["t_lift_end"])]
        server_counts = [s["server_step_count"] for _, s in seq]
        checks["snapshots"] = [
            {"phase": p, "server_step": s["server_step_count"],
             "same_tick": s["server_same_tick"]} for p, s in seq]
        # 用冻结判据复验快照结构
        sys.path.insert(0, str(REPO / "analysis" / "research_context"))
        from p1_dev1a_operational_truth import validate_snapshot
        checks["snapshot_validity"] = [
            {"phase": p, "valid": validate_snapshot(s)} for p, s in seq]
        # 步数语义:阶段边界严格递增(trigger < close_end < lift_end),
        # 相邻快照间非递减(dz 阈值停止时末采样与 t_lift_end 同刻,合法)
        checks["server_counts_nondecreasing"] = all(
            b >= a for a, b in zip(server_counts, server_counts[1:]))
        checks["phase_boundaries_strict"] = (
            server_counts[0] < server_counts[1] < server_counts[-1])
        checks["all_same_tick"] = all(s["server_same_tick"]
                                      for _, s in seq)
        checks["labels"] = probe["labels"]
        checks["lift_env_steps"] = probe["lift_steps_used"]
        checks["eef_dz"] = probe["eef_dz_m"]
        checks["env_steps_cost"] = probe["env_steps_cost"]
        checks["legal_envelope_keys_ok"] = all(
            set(e) == {"env_step", "rgb_sha256", "wrist_sha256",
                       "gripper_gap", "eef_pos", "eef_quat", "source",
                       "fresh", "validity"}
            for e in probe["legal_envelopes"].values())

    out_json = OUT / "hook_smoke_result.json"
    out_json.write_text(json.dumps(checks, ensure_ascii=False, indent=2,
                                   default=str), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=1, default=str))
    ok = (checks["maybe_probe_returns_none_blind"]
          and checks["events_order_ok"] and checks["probe_present"]
          and checks["server_counts_nondecreasing"]
          and checks["phase_boundaries_strict"]
          and checks["all_same_tick"]
          and checks["legal_envelope_keys_ok"]
          and all(x["valid"] for x in checks["snapshot_validity"]))
    print(f"[hook_smoke] {'PASS' if ok else 'FAIL'} -> {out_json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
