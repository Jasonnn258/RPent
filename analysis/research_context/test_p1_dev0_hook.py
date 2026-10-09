"""P1-DEV0 D2 钩子无 GPU mock 测试 + 源码接线验证(不启动仿真)。

覆盖:
- 默认关闭零副作用(源码接线断言 + 行为断言);
- 四臂触发/遮蔽/决策/动作(D0 盲重试、D1 probe-blind、D2 静态阈值、
  D3 弃权回落与多源判据);
- 触发资格严格性(仅首个 pi0_pick success=False 且非终局/截断);
- 固定 horizon audit-only 审计与 episode 结束兜底;
- 信息隔离(特权键不进决策路径/事件策略输入;审计值不进 Planner 视图);
- 成本记账(env steps / 墙钟)。

运行:python -m unittest analysis.research_context.test_p1_dev0_hook -v
(或 discovery:python -m unittest discover -s analysis/research_context -p "test_p1_dev0_*.py")
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from rpent.utils import p1_dev0                     # noqa: E402
from robots.libero import tools as libero_tools     # noqa: E402
from robots.libero import toolkit as libero_toolkit # noqa: E402
from robots.libero import env_client as libero_env_client  # noqa: E402
from rpent.utils.logging import init_output_dir     # noqa: E402

POLICY_PATH = REPO / "analysis" / "research_context" / "p1_dev0_policy.py"


# ---- fakes(镜像真实接口;env-step 计数按 env_client 生产接线模拟)--------

class FakeEnv:
    def __init__(self, gripper_open=0.08, probe_dz=0.0):
        self.episode_terminated = False
        self.episode_truncated = False
        self.gripper_qpos = [gripper_open / 2, -gripper_open / 2]
        self.eef_pos = [0.30, 0.10, 0.20]
        self.probe_dz = probe_dz     # 探测引起的 eef_z 变化(测试可控)
        self.check_success_calls = 0
        self.sim_measurement_calls = 0
        self.raw_obs_calls = 0

    def raw_obs(self):
        self.raw_obs_calls += 1
        return {
            "robot0_eef_pos": list(self.eef_pos),
            "robot0_eef_quat": [1.0, 0.0, 0.0, 0.0],
            "robot0_gripper_qpos": list(self.gripper_qpos),
            "robot0_eye_in_hand_image": np.zeros((8, 8, 3), dtype=np.uint8),
        }

    def check_success(self):
        self.check_success_calls += 1
        return "AUDIT_TRUTH_SENTINEL"

    def sim_measurement(self):
        self.sim_measurement_calls += 1
        return {"obs": {"obj_z": [0.05]}, "obj_of_interest": ["milk"]}


class FakePrimitives:
    """set_gripper 镜像:推进 env-step 计数(生产中由 env_client 计)。"""

    CHUNK_ENV_STEPS = 30

    def __init__(self, env):
        self.env = env
        self._last_obs = {"main_images": np.zeros((8, 8, 3), dtype=np.uint8)}
        self.set_gripper_calls = []

    def set_gripper(self, *, gripper, steps):
        self.set_gripper_calls.append({"gripper": gripper, "steps": steps})
        # 物理:夹紧(+1 → 指距趋零)+ 测试可控的 eef_z 漂移
        gap = 0.004 if gripper > 0 else 0.08
        self.env.gripper_qpos = [gap / 2, -gap / 2]
        self.env.eef_pos[2] += self.env.probe_dz
        for _ in range(int(steps)):
            p1_dev0.count_env_steps(1)

    def fake_skill_advance(self, n=1):
        p1_dev0.count_env_steps(self.CHUNK_ENV_STEPS * n)


class FakeToolkit:
    """镜像 LiberoToolkit._step 的钩子插入契约(dump 后、view 前调用)。"""

    def __init__(self, env, view_overrides=None):
        self._primitives = FakePrimitives(env)
        self._next_step = 0
        self.env = env
        self.views = view_overrides or {}

    def _step(self, name, **kwargs):
        # (真实 _step 此处已有 dump_state;fake 只推进物理计数)
        self._primitives.fake_skill_advance()
        self._next_step += 1
        step_idx = self._next_step
        result = self.skill_result(name, kwargs)
        # 与 LiberoToolkit._step 相同的插入点
        if p1_dev0.enabled():
            hooked = p1_dev0.maybe_intervene(
                self, name, kwargs, result, step_idx, 1.0)
            if hooked is not None:
                return hooked
        return self._view(step_idx, result)

    def skill_result(self, name, kwargs):
        if name == "pi0_pick":
            return {"name": "pick", "success": False, "chunks_used": 3,
                    "max_chunks": 20, "libero_terminated": False}
        return {"name": name, "success": True}

    def _view(self, step_idx, result):
        v = {"step": step_idx,
             "log": {"command": {"action": "pi0_pick"},
                     "result": result, "elapsed_s": 1.0},
             "state": {"robot0_eef_pos": list(self.env.eef_pos),
                       "robot0_gripper_qpos": list(self.env.gripper_qpos)}}
        self.views[step_idx] = v
        return v


# ---- 测试基础设施 ---------------------------------------------------------

class HookTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "p1_out"
        self.policy = str(POLICY_PATH)
        init_output_dir(Path(self.tmp.name) / "episode_out")
        self._saved_ctx = dict(p1_dev0._CTX)
        p1_dev0._CTX.clear()
        p1_dev0._CTX.update({
            "inited": False, "broken": False, "arm": None, "episode_key": None,
            "out": None, "fh": None, "policy_mod": None, "policy_sha256": None,
            "horizon": None, "episode_step_cap": None, "env_steps": 0,
            "triggered": False, "trigger_env_steps": None,
            "target_env_steps": None, "audited": False, "audit_kind": None,
            "intervening": False, "t_start": None,
        })
        # view_driver_state / artifact_path 打桩(fake 视图,不写盘)
        self._real_vds = libero_tools.view_driver_state
        self.tk_views: dict[int, dict] = {}
        libero_tools.view_driver_state = self._fake_vds

    def _fake_vds(self, step):
        v = self.tk_views.get(step)
        if v is not None:
            return json.loads(json.dumps(v))
        return {"step": step, "log": {"command": {"action": "pi0_pick"},
                                      "result": {}, "elapsed_s": 1.0}}

    def tearDown(self):
        libero_tools.view_driver_state = self._real_vds
        if p1_dev0._CTX.get("fh") is not None:
            try:
                p1_dev0._CTX["fh"].close()
            except Exception:
                pass
        p1_dev0._CTX.clear()
        p1_dev0._CTX.update(self._saved_ctx)
        for k in ("RPENT_P1_DEV0", "RPENT_P1_DEV0_ARM",
                  "RPENT_P1_DEV0_EPISODE_KEY", "RPENT_P1_DEV0_OUT",
                  "RPENT_P1_DEV0_POLICY", "RPENT_P1_DEV0_HORIZON",
                  "RPENT_P1_DEV0_EPISODE_STEP_CAP"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def enable(self, arm, horizon=200):
        os.environ["RPENT_P1_DEV0"] = "1"
        os.environ["RPENT_P1_DEV0_ARM"] = arm
        os.environ["RPENT_P1_DEV0_EPISODE_KEY"] = "p1dev0_test"
        os.environ["RPENT_P1_DEV0_OUT"] = str(self.out)
        os.environ["RPENT_P1_DEV0_POLICY"] = self.policy
        os.environ["RPENT_P1_DEV0_HORIZON"] = str(horizon)

    def reset_hook(self):
        """同一测试内模拟第二个 episode:重置模块级触发/审计状态。"""
        p1_dev0._CTX.update({
            "triggered": False, "trigger_env_steps": None,
            "target_env_steps": None, "audited": False, "audit_kind": None,
            "intervening": False, "broken": False,
        })

    def events(self):
        f = self.out / "p1_dev0_events.jsonl"
        if not f.is_file():
            return []
        return [json.loads(x) for x in
                f.read_text(encoding="utf-8").splitlines() if x.strip()]

    def kinds(self):
        return [e.get("ev") for e in self.events()]


# ---- 1. 默认关闭:源码接线 + 行为零副作用 ---------------------------------

class TestDefaultOff(HookTestBase):
    def test_env_unset_means_disabled(self):
        os.environ.pop("RPENT_P1_DEV0", None)
        self.assertFalse(p1_dev0.enabled())
        env = FakeEnv()
        tk = FakeToolkit(env)
        out = tk._step("pi0_pick", target="milk")
        self.assertEqual(out["step"], 1)
        self.assertFalse(out["log"]["result"]["success"])  # 原样透传
        self.assertFalse(self.out.exists())                 # 无事件文件

    def test_wiring_toolkit_step_hook_after_dump(self):
        src = inspect.getsource(libero_toolkit.LiberoToolkit._step)
        self.assertIn("p1_dev0.enabled()", src)
        self.assertIn("p1_dev0.maybe_intervene", src)
        # 插入点顺序:dump_state 之后、view_driver_state 之前
        i_dump = src.index("libero_tools.dump_state")
        i_hook = src.index("p1_dev0.maybe_intervene")
        i_view = src.index("out = libero_tools.view_driver_state")
        self.assertLess(i_dump, i_hook)
        self.assertLess(i_hook, i_view)

    def test_wiring_toolkit_close_finalize(self):
        src = inspect.getsource(libero_toolkit.LiberoToolkit.close)
        self.assertIn("p1_dev0.finalize", src)

    def test_wiring_env_client_counters(self):
        for fn in ("step", "chunk_step"):
            src = inspect.getsource(
                getattr(libero_env_client.LiberoEnvClient, fn))
            self.assertIn("p1_dev0.count_env_steps", src)
            self.assertIn("p1_dev0.enabled()", src)

    def test_count_env_steps_noop_when_disabled(self):
        os.environ.pop("RPENT_P1_DEV0", None)
        p1_dev0.count_env_steps(5)
        self.assertEqual(p1_dev0._CTX["env_steps"], 0)


# ---- 2. 四臂行为 -----------------------------------------------------------

class TestArms(HookTestBase):
    def _first_pick(self, tk):
        return tk._step("pi0_pick", target="milk")

    def test_D0_blind_retry_no_probe(self):
        self.enable("D0")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        out = self._first_pick(tk)
        # D0:无探测;固定盲重试 → 返回的是重试 pick 的视图(step 2)
        self.assertEqual(env.check_success_calls, 0)
        self.assertEqual(tk._primitives.set_gripper_calls, [])
        self.assertEqual(out["step"], 2)
        self.assertEqual(out["log"]["command"]["action"], "pi0_pick")
        evs = {e["ev"]: e for e in self.events()}
        self.assertIn("trigger", evs)
        self.assertNotIn("probe", evs)
        self.assertEqual(evs["decision"]["decision"], "RETRY")
        self.assertEqual(evs["decision"]["rationale_code"], "BLIND_RETRY_FIXED")
        self.assertEqual(evs["action"]["kind"], "RETRY")
        self.assertFalse(evs["action"]["abstain_fallback"])

    def test_D1_probe_blind_masking(self):
        """D1 核心:探测执行且记账,但 Planner 可见序列与 D0 同构。"""
        self.enable("D1")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        out = self._first_pick(tk)
        # 探测确实发生(物理效应存在)
        self.assertEqual(len(tk._primitives.set_gripper_calls), 1)
        self.assertEqual(tk._primitives.set_gripper_calls[0]["gripper"],
                         p1_dev0.PROBE_GRIPPER)
        self.assertEqual(tk._primitives.set_gripper_calls[0]["steps"],
                         p1_dev0.PROBE_STEPS)
        # Planner 可见:返回重试 pick 视图,步号连续(+1),无探测痕迹
        self.assertEqual(out["step"], 2)
        self.assertEqual(out["log"]["command"]["action"], "pi0_pick")
        dumped = json.dumps(out)
        self.assertNotIn("set_gripper", dumped)
        self.assertNotIn("probe", dumped.lower())
        # 决策仍是盲重试(探测观测被遮蔽,不进决策)
        evs = {e["ev"]: e for e in self.events()}
        self.assertEqual(evs["decision"]["decision"], "RETRY")
        self.assertEqual(evs["decision"]["rationale_code"], "BLIND_RETRY_FIXED")
        self.assertFalse(evs["decision"]["policy_input"]["probe_performed"]
                         is True and evs["decision"]["policy_input"]
                         ["post_gripper_gap"] is not None
                         and evs["decision"]["decision"] != "RETRY")
        # 探测观测只进事件文件(visible_to_planner=False)
        self.assertFalse(evs["probe"]["visible_to_planner"])
        self.assertEqual(evs["probe"]["env_steps_cost"], p1_dev0.PROBE_STEPS)
        # 与 D0 的步号推进一致(信息集结构同构)
        self.assertEqual(tk._next_step, 2)

    def test_D2_static_closed_grip_continues(self):
        """gap < 0.06 → CONTINUE_CAUTION:不重试,返回原失败 pick 视图。"""
        self.enable("D2")
        env = FakeEnv(gripper_open=0.08)   # 探测夹紧 → gap≈0.004
        tk = FakeToolkit(env)
        out = self._first_pick(tk)
        self.assertEqual(out["step"], 1)   # 无重试 → 返回触发步自身视图
        evs = {e["ev"]: e for e in self.events()}
        self.assertEqual(evs["decision"]["decision"], "CONTINUE_CAUTION")
        self.assertEqual(evs["decision"]["rationale_code"], "STATIC_GRIP_CLOSED")
        self.assertEqual(evs["action"]["kind"], "CONTINUE_CAUTION")
        # CONTINUE 不新增 Planner 可见信息:视图即 view_driver_state(step_idx)
        self.assertEqual(out["log"]["command"]["action"], "pi0_pick")

    def test_D2_static_open_grip_retries(self):
        self.enable("D2")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        # 让探测后 gap 仍开(模拟空手):探测不闭合
        tk._primitives.set_gripper = lambda **kw: p1_dev0.count_env_steps(
            kw.get("steps", 0))
        out = self._first_pick(tk)
        self.assertEqual(out["step"], 2)
        evs = {e["ev"]: e for e in self.events()}
        self.assertEqual(evs["decision"]["decision"], "RETRY")
        self.assertEqual(evs["decision"]["rationale_code"], "STATIC_GRIP_OPEN")

    def test_D3_continue_when_closed_and_lifted(self):
        """gap<0.06 ∧ lift≥0.03 ∧ 新鲜帧 → CONTINUE_CAUTION。"""
        self.enable("D3")
        env = FakeEnv(gripper_open=0.08, probe_dz=0.05)
        tk = FakeToolkit(env)
        out = self._first_pick(tk)
        evs = {e["ev"]: e for e in self.events()}
        self.assertEqual(evs["decision"]["decision"], "CONTINUE_CAUTION")
        self.assertEqual(evs["decision"]["rationale_code"],
                         "LEGAL_PROPRIO_PLUS_VISIBILITY_HEURISTIC")
        self.assertEqual(out["step"], 1)
        # 新鲜帧文件已写并哈希(visual_frame_available=True)
        self.assertTrue(evs["decision"]["policy_input"]["visual_frame_available"])
        frames = [f["name"] for f in evs["probe"]["post_frames"]]
        self.assertIn("probe_agentview", frames)

    def test_D3_proprio_missing_abstain_falls_back_to_blind_retry(self):
        self.enable("D3")
        env = FakeEnv(gripper_open=0.08)
        env.raw_obs = lambda: {"robot0_eef_pos": [0, 0, 0]}  # 缺 gripper 键
        tk = FakeToolkit(env)
        out = self._first_pick(tk)
        evs = {e["ev"]: e for e in self.events()}
        self.assertEqual(evs["decision"]["decision"], "ABSTAIN")
        self.assertEqual(evs["decision"]["rationale_code"], "PROPRIO_MISSING")
        # 预注册回落:ABSTAIN → 与 D0 相同的盲重试
        self.assertEqual(evs["action"]["kind"], "RETRY")
        self.assertTrue(evs["action"]["abstain_fallback"])
        self.assertEqual(out["step"], 2)

    def test_no_trigger_when_success_or_terminal_or_other_skill(self):
        self.enable("D2")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        # 成功 pick:不触发
        orig = tk.skill_result
        tk.skill_result = lambda n, kw: {"name": "pick", "success": True,
                                         "chunks_used": 2}
        out = tk._step("pi0_pick", target="milk")
        self.assertEqual(out["step"], 1)
        self.assertEqual(self.kinds(), ["init"])
        # 非 pick 技能:不触发
        tk.skill_result = orig
        tk._step("move_to", xyz=[0.1, 0.2, 0.3])
        self.assertEqual(self.kinds(), ["init"])
        # truncated:不触发
        env.episode_truncated = True
        tk._step("pi0_pick", target="milk")
        env.episode_truncated = False
        self.assertEqual(self.kinds(), ["init"])
        # terminal:不触发
        env.episode_terminated = True
        tk._step("pi0_pick", target="milk")
        env.episode_terminated = False
        self.assertEqual(self.kinds(), ["init"])

    def test_only_first_false_pick_triggers(self):
        self.enable("D0")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")
        n_events = len(self.events())
        tk._step("pi0_pick", target="milk")   # 第二次失败 pick:不再干预
        self.assertEqual(len(self.events()), n_events)
        self.assertEqual(tk._primitives.set_gripper_calls, [])


# ---- 3. 固定 horizon 审计 --------------------------------------------------

class TestAudit(HookTestBase):
    def test_audit_at_fixed_horizon_not_earlier(self):
        self.enable("D0", horizon=100)
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")           # 触发(env_steps=30)
        evs = self.events()
        trig = [e for e in evs if e["ev"] == "trigger"][0]
        target = trig["target_env_steps"]
        self.assertEqual(target, 30 + 100)
        # 未到 horizon:后续技能边界不审计
        for _ in range(2):
            tk._step("move_to", xyz=[0, 0, 0])        # 每次 +30
        self.assertNotIn("audit", self.kinds())
        # 越过 horizon 的首个边界:审计一次
        while p1_dev0._CTX["env_steps"] < target:
            tk._step("move_to", xyz=[0, 0, 0])
        tk._step("move_to", xyz=[0, 0, 0])
        audits = [e for e in self.events() if e["ev"] == "audit"]
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["kind"], "FIXED_HORIZON")
        self.assertGreaterEqual(audits[0]["env_steps_at_audit"], target)
        self.assertEqual(audits[0]["overshoot_env_steps"],
                         audits[0]["env_steps_at_audit"] - target)
        # 审计值来自真值通道;再前进也不重复审计
        tk._step("move_to", xyz=[0, 0, 0])
        self.assertEqual(len([e for e in self.events()
                              if e["ev"] == "audit"]), 1)

    def test_audit_value_never_in_planner_view(self):
        self.enable("D0", horizon=10)
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        views = [tk._step("pi0_pick", target="milk")]
        for _ in range(8):
            views.append(tk._step("move_to", xyz=[0, 0, 0]))
        self.assertTrue(any(e["ev"] == "audit" for e in self.events()))
        for v in views:
            self.assertNotIn("AUDIT_TRUTH_SENTINEL", json.dumps(v))
        self.assertNotIn("AUDIT_TRUTH_SENTINEL",
                         json.dumps([e for e in self.events()
                                     if e["ev"] != "audit"]))

    def test_finalize_episode_end_fallback_audit(self):
        self.enable("D3")
        env = FakeEnv(gripper_open=0.08, probe_dz=0.05)
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")           # CONTINUE_CAUTION
        self.assertNotIn("audit", self.kinds())       # 远未到 horizon
        p1_dev0.finalize(tk)
        audits = [e for e in self.events() if e["ev"] == "audit"]
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["kind"], "EPISODE_END")
        end = [e for e in self.events() if e["ev"] == "episode_end"][0]
        self.assertTrue(end["triggered"])
        self.assertTrue(end["audited"])
        self.assertGreater(end["env_steps_total"], 0)

    def test_finalize_untriggered_episode_no_audit(self):
        self.enable("D0")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        tk._step("move_to", xyz=[0, 0, 0])
        p1_dev0.finalize(tk)
        self.assertNotIn("audit", self.kinds())
        end = [e for e in self.events() if e["ev"] == "episode_end"][0]
        self.assertFalse(end["triggered"])


# ---- 4. 信息隔离 -----------------------------------------------------------

class TestIsolation(HookTestBase):
    def test_privileged_keys_never_in_policy_path(self):
        """raw_obs 含物体坐标/check_success 键时,决策与合法快照零透传。"""
        self.enable("D3")
        env = FakeEnv(gripper_open=0.08, probe_dz=0.05)
        real_raw = env.raw_obs

        def poisoned_raw():
            d = real_raw()
            d.update({"milk_pos": [1, 2, 3], "check_success": True,
                      "target_pos": [0, 0, 0], "object_world_pos": [0, 0, 0]})
            return d
        env.raw_obs = poisoned_raw
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")
        evs = self.events()
        forbidden = {"milk_pos", "check_success", "target_pos",
                     "object_world_pos", "obj_of_interest",
                     "research_audit_truth", "sim_measurement"}
        non_audit = json.dumps([e for e in evs if e["ev"] != "audit"])
        for k in forbidden:
            self.assertNotIn(f'"{k}"', non_audit,
                             f"privileged key {k} leaked outside audit event")
        # 冻结 policy 的 fail-close 校验在真实污染 payload 上必须抛
        mod = p1_dev0._CTX["policy_mod"]
        with self.assertRaises(ValueError):
            mod.deny_privileged_payload({"nested": {"check_success": 1}})

    def test_events_outside_episode_output_dir(self):
        """事件文件必须写在 episode output_dir 之外(Planner 文件工具可列
        output_dir 并读其中文件,审计真值绝不能放那里)。"""
        self.enable("D1")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")
        from rpent.utils.logging import get_output_dir
        ev_file = self.out / "p1_dev0_events.jsonl"
        self.assertTrue(ev_file.is_file())
        self.assertNotIn(str(get_output_dir()), str(ev_file))
        self.assertFalse(get_output_dir() in ev_file.parents)

    def test_d1_and_d0_planner_visible_identical_structure(self):
        """D0 与 D1 的 Planner 可见序列逐字段同构(信息集隔离的构成性检验)。"""
        outs = {}
        for arm in ("D0", "D1"):
            self.enable(arm)
            self.reset_hook()   # 模拟两个独立 episode
            env = FakeEnv(gripper_open=0.08)
            tk = FakeToolkit(env)
            outs[arm] = tk._step("pi0_pick", target="milk")
            # 规范化:去掉数值,只比结构(键集合 + command/result 键)
        def shape(v):
            return {"keys": sorted(v.keys()),
                    "command": v["log"]["command"],
                    "result_keys": sorted(v["log"]["result"].keys()),
                    "step": v["step"]}
        self.assertEqual(shape(outs["D0"]), shape(outs["D1"]))


# ---- 5. 成本记账 -----------------------------------------------------------

class TestCosts(HookTestBase):
    def test_probe_and_action_costs_recorded(self):
        self.enable("D1")
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")
        evs = {e["ev"]: e for e in self.events()}
        self.assertEqual(evs["probe"]["env_steps_cost"], p1_dev0.PROBE_STEPS)
        self.assertEqual(evs["probe"]["probe_args"]["gripper"],
                         p1_dev0.PROBE_GRIPPER)
        self.assertIn("wall_s", evs["probe"])
        # 重试成本 = 一次 fake 技能推进(30 env steps)
        self.assertEqual(evs["action"]["env_steps_cost"],
                         FakeToolkit.CHUNK_ENV_STEPS
                         if hasattr(FakeToolkit, "CHUNK_ENV_STEPS")
                         else FakePrimitives.CHUNK_ENV_STEPS)
        self.assertIn("retry_result_summary", evs["action"])
        self.assertIn("success", evs["action"]["retry_result_summary"])

    def test_budget_gate_reflected_in_evidence(self):
        self.enable("D2")
        os.environ["RPENT_P1_DEV0_EPISODE_STEP_CAP"] = "35"   # 极小预算
        env = FakeEnv(gripper_open=0.08)
        tk = FakeToolkit(env)
        tk._step("pi0_pick", target="milk")   # 触发时已 30 步
        evs = {e["ev"]: e for e in self.events()}
        pi = evs["decision"]["policy_input"]
        self.assertEqual(pi["budget_remaining_env_steps"],
                         max(0, 35 - p1_dev0._CTX["env_steps"]))


if __name__ == "__main__":
    unittest.main()
