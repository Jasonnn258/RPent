"""结构化全局记忆 v1 —— 可执行规则引擎。

本引擎把自由文本 Global Memory 转换成按 phase 限定、
前置条件门控的规则,planner 通过逐轮 phase 上下文
注入来消费它们。除日志外它是纯的、无副作用的:

- 计数器随工具流推进(``on_tool_call`` / ``on_tool_result``);
- ``current_block()`` 返回要入队的紧凑文本(或 ``None`` 保持
  静默 —— 唯一消耗 turn 的是真实注入);
- ``snapshot()`` 产出配对分析消费的离线指标。

phase 模型是确定性的,纯由累计工具计数推导
(没有 ``set_phase`` 工具,因此工具列表与 baseline 完全一致):

    P_init -> P_look(首次感知)-> P_transport(首次 move_to/move_pose)
    -> P_grasp(首次 pi0_pick)-> P_place(首次 release/pi0_doubled)
    -> P_verify(第二次 release/pi0_doubled)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from rpent.memory.schema import PHASE_ORDER, Rule, parse_rules
from rpent.utils.logging import get_logger

logger = get_logger("structured_memory")

#: 推进感知连击的工具。连击只在 ACTION 上重置。
PERCEPTION_TOOLS = frozenset(
    {
        "view_driver_state",
        "view_camera_meta",
        "segment",
        "back_project",
        "read_image",
    }
)

#: 计为"动作"的工具(打断感知连击、计入 ``action_calls``
#: 和 F2/F3 重新定位循环)。
ACTION_TOOLS = frozenset(
    {
        "move_to",
        "move_pose",
        "pi0_pick",
        "pi0_doubled",
        "release",
        "set_gripper",
        "rotate_wrist",
        "rotate_pitch",
    }
)

#: 既不感知也不动作的工具。
NEUTRAL_TOOLS = frozenset({"read_text_file", "write_text_file", "list_dir", "finish"})

#: 每个 phase 的一行语义提示 —— 注入上下文的一部分。
PHASE_HINT = {
    "P_init": "task not started — first act: perceive the scene once.",
    "P_look": "perceiving / localizing — resolve a target xyz, then act. Never loop perception.",
    "P_transport": "travelling to the target — one deliberate approach, then pick.",
    "P_grasp": "grasping — fix pre-grasp (wrist pitch / clearance), retry at most twice.",
    "P_place": "placing — t9: prefer pi0_doubled double-stage placement; cap placement retries.",
    "P_verify": "confirm final placement, then call finish — do not re-open perception.",
}

#: 谓词键 -> 用于 ``*_ge`` 和 ``max_turns_left_le`` 的当前计数值。
def _counter_for(tracker: "PhaseTracker", key: str) -> int | None:
    if key == "consecutive_perception_ge":
        return tracker._consecutive_perception
    if key == "action_calls_ge":
        return tracker._action_calls
    if key == "move_to_calls_ge":
        return tracker._counts["move_to"]
    if key == "pick_calls_ge":
        return tracker._counts["pi0_pick"]
    if key == "release_calls_ge":
        return tracker._counts["release"]
    if key == "doubled_calls_ge":
        return tracker._counts["pi0_doubled"]
    if key == "placement_calls_ge":
        return tracker._counts["release"] + tracker._counts["pi0_doubled"]
    if key == "read_text_file_calls_ge":
        return tracker._counts["read_text_file"]
    if key == "turns_used_ge":
        return tracker._turns_used
    if key == "max_turns_left_le":
        return tracker._max_turns - tracker._turns_used
    return None


class PhaseTracker:
    """由工具流驱动的确定性单 episode phase + 规则引擎。"""

    def __init__(
        self,
        rules: list[Rule],
        *,
        task: str = "",
        max_turns: int = 40,
        memory_dir: str = "",
    ) -> None:
        self._task = task
        self._max_turns = max_turns
        self._memory_dir = memory_dir
        # 规则在构造时按当前 task 范围一次性过滤。
        self._rules = [r for r in rules if r.applies_to_task(task)]
        self._rules_by_id = {r.id: r for r in self._rules}

        # 按工具的累计计数器(每个工具名都零初始化)
        self._counts: dict[str, int] = {name: 0 for name in PERCEPTION_TOOLS}
        self._counts.update({name: 0 for name in ACTION_TOOLS})
        self._counts.update({name: 0 for name in NEUTRAL_TOOLS})

        self._consecutive_perception = 0
        self._action_calls = 0
        self._turns_used = 0
        self._last_result = ""
        self._last_pick_success: bool | None = None
        self._last_is_error = False
        self._moves_since_pick = 0
        self._finish_called = False

        # phase 状态
        self._phase = "P_init"
        self._prev_phase = "P_init"
        self._phase_sequence: list[str] = ["P_init"]
        self._phase_entries: dict[str, int] = {"P_init": 1}

        # 规则/注入记账
        self._fired: list[str] = []  # 已触发的规则 id,去重,按触发顺序
        self._fired_detail: dict[str, dict[str, Any]] = {}
        self._actions_since_fire: dict[str, int] = {}
        self._injections = 0
        self._injection_tokens_approx = 0
        self._last_injected_phase: str | None = None
        self._mem_reads: list[str] = []

    # ------------------------------------------------------------------ 喂入
    def on_tool_call(self, name: str, args: dict[str, Any] | None = None) -> None:
        args = args or {}
        # read_text_file 单独计数(仅 memory 范围,见下),这样
        # R8 过度读取守卫只在真实记忆读取时触发。
        if name in self._counts and name != "read_text_file":
            self._counts[name] += 1
        if name in PERCEPTION_TOOLS:
            self._consecutive_perception += 1
        elif name in ACTION_TOOLS:
            self._consecutive_perception = 0
            self._action_calls += 1
            for rule_id in self._fired:
                self._actions_since_fire[rule_id] = (
                    self._actions_since_fire.get(rule_id, 0) + 1
                )
        if name == "finish":
            self._finish_called = True
        if name in ("move_to", "move_pose"):
            self._moves_since_pick += 1
        if name == "read_text_file":
            path = str(args.get("path", ""))
            if self._is_memory_read(path):
                self._counts["read_text_file"] += 1
                self._mem_reads.append(path)
                logger.info("[memread] %s", path)
        self._recompute_phase()

    def on_tool_result(
        self, name: str, content: str, is_error: bool = False
    ) -> None:
        self._last_result = content or ""
        self._last_is_error = is_error
        if name == "pi0_pick":
            low = self._last_result.lower()
            self._last_pick_success = not any(
                tok in low for tok in ("fail", "error", "could not", "no object")
            )
            # 新的一次抓取会重置移动距离计数器
            self._moves_since_pick = 0
        elif name == "release":
            # 这次 release 消耗掉了抓取 —— 清掉它,第二次快速
            # release() 便不能触发(那会跳过双段放置)。
            self._last_pick_success = None

    # ----------------------------------------------------------------- phase
    def _recompute_phase(self) -> None:
        c = self._counts
        if c["release"] + c["pi0_doubled"] >= 2:
            new = "P_verify"
        elif c["release"] + c["pi0_doubled"] >= 1:
            new = "P_place"
        elif c["pi0_pick"] >= 1:
            new = "P_grasp"
        elif c["move_to"] + c["move_pose"] >= 1:
            new = "P_transport"
        elif sum(c[t] for t in PERCEPTION_TOOLS) >= 1:
            new = "P_look"
        else:
            new = "P_init"
        if new != self._phase:
            self._prev_phase = self._phase
            self._phase = new
            self._phase_sequence.append(new)
            self._phase_entries[new] = self._phase_entries.get(new, 0) + 1
            logger.info(
                "[phase] CURRENT=%s (prev=%s) task=%s",
                new, self._prev_phase, self._task or "?",
            )

    def current_phase(self) -> str:
        return self._phase

    # ------------------------------------------------------------ fast/slow API
    def recovery_pending(self) -> str | None:
        """第一条前置条件已满足但尚未触发的当前 phase 规则。

        纯查询:无副作用(不触发规则、不碰
        ``_turns_used``、不记日志)。dual-route 决策器做 pending 检查时
        绝不能调用 ``current_block`` —— 那会触发规则并记录
        ``_turns_used``。
        """
        for rule in self._rules:
            if rule.id in self._fired:
                continue
            if not rule.applies_to_phase(self._phase):
                continue
            if self._eval_predicate(rule.precondition, rule.id):
                return rule.id
        return None

    @property
    def last_is_error(self) -> bool:
        return self._last_is_error

    @property
    def moves_since_pick(self) -> int:
        return self._moves_since_pick

    @property
    def last_pick_success(self) -> bool | None:
        return self._last_pick_success

    @property
    def finish_called(self) -> bool:
        return self._finish_called

    # ------------------------------------------------------------- 谓词
    def _value_for(self, key: str) -> Any:
        if key == "phase":
            return self._phase
        return _counter_for(self, key)

    def _eval_predicate(self, pred: dict[str, Any], rule_id: str) -> bool:
        for key, value in pred.items():
            if key == "phase":
                if value != "ANY" and value != self._phase:
                    return False
            elif key == "phase_ne":
                if self._phase == value:
                    return False
            elif key == "phase_in":
                if self._phase not in value:
                    return False
            elif key == "actions_after_fire_ge":
                if self._actions_since_fire.get(rule_id, 0) < value:
                    return False
            elif key == "tool_count":
                for tname, tcount in value.items():
                    if self._counts.get(tname, 0) != tcount:
                        return False
            elif key == "result_contains":
                if value not in self._last_result:
                    return False
            elif key == "failure_marker":
                if value != "max_turns" or self._turns_used < self._max_turns:
                    return False
            elif key == "finish_called":
                if bool(value) and not self._finish_called:
                    return False
                if not value and self._finish_called:
                    return False
            elif key == "max_turns_left_le":
                cur = self._value_for(key)
                if cur is None or not (cur <= value):
                    return False
            elif key.endswith("_ge"):
                cur = self._value_for(key)
                if cur is None or not (cur >= value):
                    return False
            else:
                return False  # 未知键 -> 保险起见判负,永不触发
        return True

    def _imminent_rule(self) -> Rule | None:
        """第一条距自身 ``*_ge`` 阈值只差 1 的当前 phase 规则(建议性)。

        只有数值型 ``*_ge`` / ``max_turns_left_le`` 键可能"临近";
        字符串/布尔键被排除。
        """
        for rule in self._rules:
            if rule.id in self._fired or not rule.applies_to_phase(self._phase):
                continue
            for key, threshold in rule.precondition.items():
                if key.endswith("_ge"):
                    cur = self._value_for(key)
                    if cur is not None and threshold - 1 <= cur < threshold:
                        return rule
                elif key == "max_turns_left_le":
                    cur = self._value_for(key)
                    if cur is not None and threshold < cur <= threshold + 1:
                        return rule
        return None

    # ----------------------------------------------------------------- 注入块
    def current_block(self, turns: int) -> str | None:
        """返回紧凑的注入块,或 None 保持静默。

        仅当自上次注入以来 phase 变化或有新规则触发时才注入 ——
        这正是控制 turn 膨胀的手段(每次注入
        消耗一次模型请求)。
        """
        self._turns_used = turns

        newly_fired: list[Rule] = []
        for rule in self._rules:
            if rule.id in self._fired:
                continue
            if not rule.applies_to_phase(self._phase):
                continue
            if self._eval_predicate(rule.precondition, rule.id):
                self._fired.append(rule.id)
                self._fired_detail[rule.id] = {
                    "fired_turn": turns,
                    "phase": self._phase,
                    "fired_order": len(self._fired),
                }
                newly_fired.append(rule)
                logger.info("[recovery] rule=%s phase=%s turn=%s", rule.id, self._phase, turns)

        phase_changed = self._phase != self._last_injected_phase
        if not newly_fired and not phase_changed:
            return None
        return self._build_block(newly_fired, phase_changed)

    def _build_block(self, newly_fired: list[Rule], phase_changed: bool) -> str:
        lines: list[str] = []
        header = f"[CURRENT PHASE: {self._phase}]"
        if phase_changed:
            header += f" (from {self._prev_phase})"
        if self._task:
            header += f" — task {self._task}"
        lines.append(header)
        hint = PHASE_HINT.get(self._phase, "")
        if hint:
            lines.append(hint)

        if newly_fired:
            for rule in newly_fired[:2]:
                lines.append(f"RULE {rule.id} fired — {rule.trigger}")
                lines.append(f"  recovery: {rule.recovery}")
            lines.append(
                "If the recovery does not work within 2 calls, stop and finish "
                "honestly — do not loop until max_turns."
            )
        elif phase_changed:
            adv = self._imminent_rule()
            if adv is not None:
                lines.append(f"ADVISORY ({adv.id}): {adv.recovery}")

        block = "\n".join(lines)
        self._injection_tokens_approx += max(1, len(block.split()))
        return block

    def mark_injected(self) -> None:
        self._injections += 1
        self._last_injected_phase = self._phase

    # ---------------------------------------------------------------- 指标
    def snapshot(self, *, success: bool | None = None) -> dict[str, Any]:
        c = self._counts
        # 用最终计数器对每条已触发规则的 success_check 求值
        #(恢复是否真的让 planner 走出了循环?)。
        recovery_success: dict[str, bool] = {}
        for rule_id in self._fired:
            rule = self._rules_by_id.get(rule_id)
            if rule is None:
                continue
            recovery_success[rule_id] = bool(
                self._eval_predicate(rule.success_check, rule_id)
            )
        return {
            "rules_ver": "v1",
            "task": self._task,
            "phase_entries": dict(self._phase_entries),
            "phase_sequence": list(self._phase_sequence),
            "injections": self._injections,
            "injection_tokens_approx": self._injection_tokens_approx,
            "fired_rules": list(self._fired),
            "fired_detail": {
                k: dict(v) for k, v in self._fired_detail.items()
            },
            "recovery_success": recovery_success,
            "counters": {
                "perception_calls": sum(c[t] for t in PERCEPTION_TOOLS),
                "consecutive_perception": self._consecutive_perception,
                "action_calls": self._action_calls,
                "move_to_calls": c["move_to"],
                "pick_calls": c["pi0_pick"],
                "doubled_calls": c["pi0_doubled"],
                "release_calls": c["release"],
                "placement_calls": c["release"] + c["pi0_doubled"],
                "read_text_file_calls": c["read_text_file"],
                "turns_used": self._turns_used,
            },
            "mem_reads": list(self._mem_reads),
            "final_phase": self._phase,
            "finish_called": self._finish_called,
            "success": success,
        }

    # ------------------------------------------------------------------ 杂项
    def _is_memory_read(self, path: str) -> bool:
        low = path.lower()
        if "memory" in low or "rules" in low:
            return True
        if self._memory_dir and str(self._memory_dir).lower() in low:
            return True
        return False


# ---------------------------------------------------------------- 加载器
def load_rules(path: str | os.PathLike) -> list[Rule]:
    """加载并校验位于 *path* 的规则文档。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_rules(raw)


def detect_task(output_dir: str | os.PathLike | None = None) -> str:
    """task id 取自 RPENT_TASK 环境变量,否则取自运行目录名 ``_t<N>_s<M>``。"""
    env = os.environ.get("RPENT_TASK", "").strip()
    if env:
        return env
    if output_dir:
        m = re.search(r"_t(\d+)_s\d+", str(output_dir))
        if m:
            return m.group(1)
    return ""


def detect_seed(output_dir: str | os.PathLike | None = None) -> str:
    """seed 取自 RPENT_SEED 环境变量,否则取自运行目录名 ``_s<M>``。"""
    env = os.environ.get("RPENT_SEED", "").strip()
    if env:
        return env
    if output_dir:
        m = re.search(r"_s(\d+)(?:_r\d+)?/?", str(output_dir))
        if m:
            return m.group(1)
    return ""
