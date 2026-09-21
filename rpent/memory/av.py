"""B3 —— 主动验证 + 裁决合规。

B2(``rpent.memory.stv``)回答了*验证器能否正确裁决?* —— 能:
裁决与物理现实相符、无循环、commit 延迟减半。B3 不动冻结的
验证器,专攻 B2 暴露的两个瓶颈:

1. **裁决合规**(服从率约 39-49%)。planner 读了裁决却仍按原计划
   继续。B3-A 加入显式裁决协议:
   SUCCESS -> commit;NOT-established -> 恢复(换做法);
   UNCERTAIN -> 在任何任务动作之前先取得所求证据;
   REASON -> 一步审慎动作。每条裁决之后*实际*的下一个动作
   被分类为服从/违规(看行为而非口头同意)并记录到
   ``b3_compliance_events.jsonl``;违规会得到一行注入的提醒。

2. **证据时机**。多数 UNCERTAIN 落在失败不可判定的位置
   (物体还在原位、手爪还在旁边 —— 失败签名需要手爪已经
   离开)。B3-B 加入*后撤-再观察*:对 UNCERTAIN 证据指令,验证器
   追加一条确定性探针指令 —— ``move_to`` 到一个固定的
   远离物体的后撤向量,然后重新 segment —— 并对后撤后的
   状态运行同一套冻结判定逻辑。探针移动对未决项
   机制透明(它是验证、不是任务动作)并单独计数
   (``b3_probe_events.jsonl``)。

B3-C = 两者兼用。门控:``RPENT_B3_COMPLY=1`` / ``RPENT_B3_PROBE=1``
(两者都需要 ``RPENT_OVPM2=1``)。子类的合规*记录*永远开启
(2x2 需要每个臂的服从率);两个门都关掉时注入文本
不变,因此 planner 可见行为与冻结 B2 逐字节一致 ——
由测试保证。

注入行的卫生要求继承自 B2:绝不出现子串
"fail"/"error"/"could not"/"no object"(PhaseTracker 会 grep 这些词)。
因此失败裁决类在注入文本中只写作
"NOT_ESTABLISHED" / "objective NOT established"。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from rpent.memory.stv import (
    TransitionVerifier,
    _dist,
    _is_grip_maintenance,
    _xyz,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------- B3 常量
PROBE_RETREAT_DY = 0.12  # 后撤向量:从桌面中心退开 ...
PROBE_RETREAT_DZ = 0.10  # ...并抬高。|v| ~ 0.156 m > HOLD_RADIUS(0.15):
PROBE_Z_MAX = 1.15       # 被握住的对象会跟随,被留在原地的对象不动。
PROBE_TARGET_TOL = 0.02  # move_to 距下发目标在该值内 = 探针
MAX_PROBES_PER_PENDING = 1  # 每个未决验证一次探针,之后走冻结的
MAX_PROBES_PER_EPISODE = 4  # OBSERVE->REASON 路径 —— 探针永不循环
PERCEPTION_TOOLS = frozenset(
    {"segment", "back_project", "view_driver_state", "view_camera_meta"})

# 裁决类别,从冻结的行格式归类(字符串稳定)。
_CLS_SUCCESS = "state change CONFIRMED"
_CLS_FAILURE = "NOT established"
_CLS_UNCERTAIN = "Observe once"
_CLS_REASON = "Reason explicitly"

# 可安全用于注入文本的类别 token(卫生:不含 "fail" 子串)。
_CLS_DISPLAY = {"SUCCESS": "CONFIRMED", "FAILURE": "NOT_ESTABLISHED",
                "UNCERTAIN": "UNCERTAIN", "REASON": "REASON"}

_PROTOCOL_PREAMBLE = (
    "[b3] VERDICT PROTOCOL — applies to every [b2] verdict from now on:\n"
    "- state change CONFIRMED -> commit: proceed to the next planned stage; "
    "re-verifying this step is redundant.\n"
    "- objective NOT established -> recover: switch to a changed approach "
    "(different tool, pose, or target); repeating the same call unchanged is "
    "a recorded protocol violation.\n"
    "- evidence incomplete (Observe) -> acquire the requested evidence "
    "BEFORE any task action; acting first is a recorded protocol violation.\n"
    "- after explicit reasoning -> take ONE deliberate next step, then let "
    "the verdicts guide you again."
)

_PROTOCOL_FOR = {
    "SUCCESS": "proceed with the committed plan.",
    "FAILURE": "switch to a changed approach (different tool, pose, or "
               "target); do not repeat the same call unchanged.",
    "UNCERTAIN": "acquire the requested evidence first (perception or the "
                 "verification probe); no task action before it.",
    "REASON": "take one deliberate next step.",
}

_VIOLATION_TEMPLATE = (
    "[b3] COMPLIANCE: the verdict for {tool} was {cls} and the protocol "
    "required: {protocol} Your next action ({next_tool}) did not comply — "
    "this is recorded. Do it now: {protocol}"
)


def _classify_line(line: str | None) -> str | None:
    """冻结 B2 裁决行的裁决类别(其格式稳定)。"""
    if not line:
        return None
    if _CLS_REASON in line:
        return "REASON"
    if _CLS_FAILURE in line:
        return "FAILURE"
    if _CLS_UNCERTAIN in line:
        return "UNCERTAIN"
    if _CLS_SUCCESS in line:
        return "SUCCESS"
    return None


def _args_relevantly_different(
    name: str, a: dict[str, Any], b: dict[str, Any]
) -> bool:
    """同工具重试是否改变了做法(target/prompt/pose)?"""
    keys = {
        "pi0_pick": ("prompt", "xyz"),
        "move_to": ("xyz", "target"),
        "move_pose": ("xyz", "target", "quat"),
        "pi0_doubled": ("prompt", "xyz"),
        "set_gripper": ("gripper",),
        "rotate_wrist": ("target_yaw",),
        "rotate_pitch": ("target_pitch",),
    }.get(name, None)
    if keys is None:
        return True  # 未知工具:任何重试都算有变化
    if not keys:
        return False  # release():无可改变 —— 同样调用 = 未变化
    for k in keys:
        if a.get(k) != b.get(k):
            return True
    return False


class ActiveVerifier(TransitionVerifier):
    """冻结 B2 +(可选的)裁决合规强制和/或
    后撤-再观察探针。判定规则零改动:每条
    裁决仍逐字出自冻结代码。"""

    def __init__(
        self,
        *,
        tracker: Any = None,
        task: str = "",
        comply: bool = False,
        probe: bool = False,
    ) -> None:
        super().__init__(tracker=tracker, task=task)
        self.comply = comply
        self.probe = probe
        # 合规状态
        self._awaiting: dict[str, Any] | None = None
        self._protocol_sent = False
        self._violation_line: str | None = None
        self.verdicts: dict[str, int] = {"SUCCESS": 0, "FAILURE": 0,
                                         "UNCERTAIN": 0, "REASON": 0}
        self.obeyed: dict[str, int] = dict(self.verdicts)
        self.violated: dict[str, int] = dict(self.verdicts)
        # 探针状态
        self._probe_issued: dict[str, Any] | None = None
        self._probe_armed: dict[str, Any] | None = None  # 移动已执行,
        # 等待再观察来解决未决项
        self.probe_directives = 0
        self.probe_executed = 0
        self.probe_ignored = 0
        self.probe_abandoned = 0
        self.probe_results = {"to_success": 0, "to_failure": 0,
                              "still_uncertain": 0}
        self._probe_latencies: list[int] = []
        self._armed_s0 = 0
        self._armed_f0 = 0

    # ------------------------------------------------------------ 管道

    def _emit3(self, kind: str, ev: dict[str, Any]) -> None:
        """把 B3 事件追加到它自己的 JSONL(尽力而为,绝不致命)。"""
        ev.setdefault("kind", kind)
        ev.setdefault("task", self._task)
        ev.setdefault("turn", self._step)
        try:
            from rpent.utils.logging import get_output_dir

            out = get_output_dir()
        except Exception:  # noqa: BLE001
            return
        if not out:
            return
        fname = ("b3_compliance_events.jsonl" if kind == "compliance"
                 else "b3_probe_events.jsonl")
        try:
            with open(Path(out) / fname, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False, default=str)
                        + "\n")
        except Exception as e:  # noqa: BLE001
            logger.warning("[b3] event write failed: %s", e)

    # ---------------------------------------------------------- 合规

    def _await_on(self, cls: str, tool: str, kwargs: dict[str, Any]) -> None:
        self.verdicts[cls] = self.verdicts.get(cls, 0) + 1
        self._awaiting = {
            "cls": cls,
            "tool": tool,
            "kwargs": dict(kwargs or {}),
            "step": self._step,
        }

    def _classify_incoming(
        self, name: str, kwargs: dict[str, Any], ph: str
    ) -> None:
        """行为合规:本次工具调用是否遵守了仍在等待
        响应的裁决?发出一条合规事件。"""
        a = self._awaiting
        self._awaiting = None
        if a is None:
            return
        cls, tool = a["cls"], a["tool"]
        if name == "finish":
            obeyed = cls in ("SUCCESS", "FAILURE", "REASON")
        elif cls == "SUCCESS":
            obeyed = True  # commit:接下来做什么都算服从
        elif cls == "FAILURE":
            if name != tool:
                obeyed = True  # 换了动作 = 恢复
            else:
                obeyed = _args_relevantly_different(name, kwargs,
                                                    a.get("kwargs") or {})
        elif cls == "UNCERTAIN":
            if name in PERCEPTION_TOOLS or self._probe_hit(name, kwargs):
                obeyed = True  # 证据获取(含探针)
            else:
                obeyed = False
        else:  # REASON
            obeyed = True  # 接下来的任何动作都算一步审慎动作
        ev = {
            "verdict": cls,
            "verdict_tool": tool,
            "verdict_step": a["step"],
            "planner_next_action": name,
            "next_args": {k: v for k, v in (kwargs or {}).items()
                          if isinstance(v, (int, float, str, bool))},
            "obeyed": obeyed,
            "phase": ph,
        }
        self._emit3("compliance", ev)
        if obeyed:
            self.obeyed[cls] = self.obeyed.get(cls, 0) + 1
        else:
            self.violated[cls] = self.violated.get(cls, 0) + 1
            if self.comply:
                self._violation_line = _VIOLATION_TEMPLATE.format(
                    tool=tool, cls=_CLS_DISPLAY[cls],
                    protocol=_PROTOCOL_FOR[cls], next_tool=name)

    # -------------------------------------------------------------- 探针

    def _probe_hit(self, name: str, kwargs: dict[str, Any]) -> bool:
        """这个动作是不是下发的验证探针(精确后撤)?"""
        if not self._probe_issued or name not in ("move_to", "move_pose"):
            return False
        t = _xyz(kwargs.get("xyz") or kwargs.get("target"))
        if t is None:
            return False
        d = _dist(t, tuple(self._probe_issued["target"]))
        return d is not None and d <= PROBE_TARGET_TOL

    def _maybe_issue_probe(self, line: str | None) -> str | None:
        """在 UNCERTAIN 证据指令后追加后撤-再观察说明
        (B3-B)。每个未决项一次探针,每 episode 封顶;
        目标由最新的 eef 确定性算出。"""
        if not line or not self.probe:
            return line
        if _classify_line(line) != "UNCERTAIN" or self._pending is None:
            return line
        if self._pending.get("wants") != "object_position":
            return line
        if self._pending.get("probes_used", 0) >= MAX_PROBES_PER_PENDING:
            return line
        if self._probe_issued is not None:
            return line  # 同一时刻只有一条活跃指令
        if self.probe_executed >= MAX_PROBES_PER_EPISODE:
            return line
        eef = self._eef
        if eef is None:
            return line
        target = (round(eef[0], 3), round(eef[1] - PROBE_RETREAT_DY, 3),
                  round(min(eef[2] + PROBE_RETREAT_DZ, PROBE_Z_MAX), 3))
        self._pending["probes_used"] = self._pending.get("probes_used", 0) + 1
        self._probe_issued = {
            "target": target,
            "label": self._pending.get("label"),
            "step": self._step,
            "pending_tool": self._pending.get("tool"),
        }
        self.probe_directives += 1
        label = self._pending.get("label")
        seg = (f"segment(prompt='{label}', camera='agentview')"
               if label and "@" not in label
               else "segment the object in question (text prompt or point)")
        probe_block = (
            "\n\n[b3] VERIFICATION PROBE (not a task step): first run "
            f"move_to(x={target[0]}, y={target[1]}, z={target[2]}) exactly — "
            "retract clear of the object and wait for the move to finish — "
            f"then {seg}. Retreating separates a held object (it follows the "
            "gripper) from a left one (it stays put); checking from the "
            "current pose cannot. No other task action in between."
        )
        self._emit3("probe", {"event": "directive", "target": list(target),
                              "label": label, "pending_tool":
                              self._pending.get("tool")})
        return line + probe_block

    def _close_probe(self, result: str | None) -> None:
        """当已执行探针对应的未决验证落定(或未决项未落定
        即关闭)时,记录其结果转移。"""
        if self._probe_armed is None:
            return
        p = self._probe_armed
        self._probe_armed = None
        lat = max(self._step - p["step"], 0)
        self._probe_latencies.append(lat)
        if result == "to_success":
            self.probe_results["to_success"] += 1
        elif result == "to_failure":
            self.probe_results["to_failure"] += 1
        elif result:
            self.probe_results["still_uncertain"] += 1
        self._emit3("probe", {"event": "result", "result": result,
                              "target": p.get("target"),
                              "latency_steps": lat})

    # ------------------------------------------------------- 主入口

    def observe_result(
        self,
        name: str,
        kwargs: dict[str, Any],
        result_text: str,
        *,
        is_error: bool = False,
        phase: str | None = None,
    ) -> str | None:
        ph = phase if phase is not None else self._phase()
        from rpent.memory.structured import ACTION_TOOLS

        kwargs = kwargs or {}
        is_action = name in ACTION_TOOLS
        pending_tool_at_entry = (self._pending or {}).get("tool")

        # 1) 到来的工具相对等待中裁决的行为合规。
        #    握持维护(闭合 set_gripper)在 B2 中透明且不回答
        #    任何协议问题 —— 跳过。
        if self._awaiting is not None and \
                not _is_grip_maintenance(name, kwargs) and \
                (is_action or name in PERCEPTION_TOOLS or name == "finish"):
            self._classify_incoming(name, kwargs, ph)
        violation = self._violation_line
        self._violation_line = None

        # 2) 已下发的探针移动对冻结机制透明
        if self._probe_hit(name, kwargs):
            self._step += 1
            self._tool_n[name] = self._tool_n.get(name, 0) + 1
            try:
                payload = json.loads(result_text)
            except Exception:  # noqa: BLE001
                payload = None
            self._update_cache_from_action(name, kwargs, payload)
            self.probe_executed += 1
            self._probe_armed = dict(self._probe_issued or {})
            self._probe_armed["step"] = self._step
            self._emit3("probe", {"event": "executed",
                                  "target": list(self._probe_armed["target"]),
                                  "issued_step": self._probe_issued["step"]})
            self._probe_issued = None
            return None  # 无裁决、不超越、无 TRANSPORT 判定

        # 3) 探针指令仍活跃期间的任何其他动作:记为忽略
        if self._probe_issued is not None and is_action:
            self.probe_ignored += 1
            self._emit3("probe", {"event": "ignored", "by": name})
            self._probe_issued = None

        # 4) 冻结 B2 路径(判定不变;自发自己的事件)
        line = super().observe_result(
            name, kwargs, result_text, is_error=is_error, phase=phase)

        # 5) 探针结果记录:若探针所对应的未决项
        #    现在落定,归类该转移
        if self._probe_armed is not None:
            res = self.uncertain_resolutions
            if res.get("resolved_success", 0) > self._armed_s0:
                self._close_probe("to_success")
            elif res.get("resolved_failure", 0) > self._armed_f0:
                self._close_probe("to_failure")
            elif self._pending is None:  # 被超越 / REASON / 已关闭
                self._close_probe("still_uncertain")
        self._armed_s0 = self.uncertain_resolutions.get("resolved_success", 0)
        self._armed_f0 = self.uncertain_resolutions.get("resolved_failure", 0)

        # 6) 指令被放弃(未决项关闭而探针未执行)
        if self._probe_issued is not None and self._pending is None:
            self.probe_abandoned += 1
            self._emit3("probe", {"event": "abandoned"})
            self._probe_issued = None

        # 7) 后处理:探针指令 / 等待中 / 违规提醒 /
        #    一次性协议前言
        line = self._maybe_issue_probe(line)
        cls = _classify_line(line)
        if cls:
            subject = name if is_action else (pending_tool_at_entry or name)
            self._await_on(cls, subject, kwargs)
        if violation:
            line = f"{violation}\n\n{line}" if line else violation
        if self.comply and not self._protocol_sent and line:
            self._protocol_sent = True
            line = f"{_PROTOCOL_PREAMBLE}\n\n{line}"
        return line

    # ------------------------------------------------------------ 快照

    def snapshot(self, *, success: bool) -> dict[str, Any]:
        if self._probe_armed is not None:
            self._close_probe("still_uncertain")
        if self._probe_issued is not None:
            self.probe_abandoned += 1
            self._emit3("probe", {"event": "abandoned"})
            self._probe_issued = None
        self._awaiting = None
        snap = super().snapshot(success=success)
        total_ob = sum(self.obeyed.values())
        total_vio = sum(self.violated.values())
        lat = [x for x in self._probe_latencies if x is not None]
        snap["b3"] = {
            "comply": self.comply,
            "probe": self.probe,
            "verdict_counts": dict(self.verdicts),
            "obeyed": dict(self.obeyed),
            "violated": dict(self.violated),
            "verdict_obedience_rate": (
                round(total_ob / (total_ob + total_vio), 3)
                if total_ob + total_vio else None),
            "probe_directives": self.probe_directives,
            "probe_executed": self.probe_executed,
            "probe_ignored": self.probe_ignored,
            "probe_abandoned": self.probe_abandoned,
            "verification_probe_count": self.probe_executed,
            "probe_results": dict(self.probe_results),
            "probe_latency_steps": list(self._probe_latencies),
            "probe_latency_mean": (round(sum(lat) / len(lat), 2)
                                   if lat else None),
        }
        return snap
