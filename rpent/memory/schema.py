"""结构化全局记忆 v1 —— 规则 schema 与校验。

每条规则是一个 Global Memory 条目的可执行形式,携带 v1 规范完整的
九字段契约:``phase``、``trigger``、``precondition``、
``expected_result``、``success_check``、``failure_pattern``、``recovery``、
``next_phase``、``scope``。

校验 fail-fast:规则 JSON 里的笔误(未知字段、坏 phase、坏
谓词键)在加载期暴露,而不是 episode 中途。
"""

from __future__ import annotations

import dataclasses
from typing import Any

#: 确定性 phase 模型 —— 纯由工具调用计数推导。
PHASES = ("P_init", "P_look", "P_transport", "P_grasp", "P_place", "P_verify")
PHASE_ORDER = {p: i for i, p in enumerate(PHASES)}

#: ``precondition`` / ``success_check`` 字典里接受的谓词键。
#: 谓词里的每个键之间取 AND;所有键都对照 tracker 的窗口/累计
#: 计数器求值。
PREDICATE_KEYS = frozenset(
    {
        # 当前 phase 匹配
        "phase",            # 相等(str)  | "ANY" 匹配任意
        "phase_ne",         # 不相等(str)
        "phase_in",         # 属于 phase 列表
        # 计数阈值(全部 AND)
        "consecutive_perception_ge",
        "action_calls_ge",
        "actions_after_fire_ge",
        "move_to_calls_ge",
        "pick_calls_ge",
        "release_calls_ge",
        "doubled_calls_ge",
        "placement_calls_ge",
        "read_text_file_calls_ge",
        "turns_used_ge",
        "max_turns_left_le",
        # 精确的按工具累计计数
        "tool_count",       # {tool_name: int}
        # 杂项
        "result_contains",  # 上一个工具结果包含子串
        "failure_marker",   # str 标记(仅支持 "max_turns")
        "finish_called",    # bool
    }
)

#: 九个规定字段 + ``source``(证据引用)。
REQUIRED_FIELDS = (
    "id",
    "phase",
    "trigger",
    "precondition",
    "expected_result",
    "success_check",
    "failure_pattern",
    "recovery",
    "next_phase",
    "scope",
)


@dataclasses.dataclass(frozen=True)
class Rule:
    """一条结构化记忆规则。"""

    id: str
    phase: str  # P_init..P_verify 或 ANY
    trigger: str
    precondition: dict[str, Any]
    expected_result: str
    success_check: dict[str, Any]
    failure_pattern: str
    recovery: str
    next_phase: str
    scope: str  # GLOBAL | task<N>
    source: str = ""

    def applies_to_phase(self, phase: str) -> bool:
        return self.phase == "ANY" or self.phase == phase

    def applies_to_task(self, task: str) -> bool:
        if self.scope == "GLOBAL":
            return True
        if not task:
            return False
        norm = self.scope.lower().replace("_", "")
        target = task.lower().replace("_", "")
        return target in norm or norm in target


def validate(rule: dict[str, Any], *, index: int | None = None) -> Rule:
    """校验一条原始规则 dict;返回冻结的 :class:`Rule`。"""
    loc = f"rule#{index}" if index is not None else "rule"
    missing = [f for f in REQUIRED_FIELDS if f not in rule]
    if missing:
        raise ValueError(f"{loc}: missing required field(s): {missing}")

    phase = rule["phase"]
    if phase != "ANY" and phase not in PHASES:
        raise ValueError(f"{loc}: bad phase {phase!r} (want one of {PHASES} or ANY)")

    for field in ("precondition", "success_check"):
        value = rule[field]
        if not isinstance(value, dict):
            raise ValueError(f"{loc}: {field} must be a dict")
        for key in value:
            if key not in PREDICATE_KEYS:
                raise ValueError(f"{loc}: unknown predicate key {key!r} in {field}")

    for field in (
        "id",
        "trigger",
        "expected_result",
        "failure_pattern",
        "recovery",
        "next_phase",
        "scope",
    ):
        if not isinstance(rule[field], str) or not rule[field].strip():
            raise ValueError(f"{loc}: {field} must be a non-empty string")

    scope = rule["scope"]
    if scope != "GLOBAL" and not scope.lower().startswith(("task", "t")):
        raise ValueError(f"{loc}: scope must be GLOBAL or task<N> (got {scope!r})")

    return Rule(
        id=rule["id"],
        phase=phase,
        trigger=rule["trigger"],
        precondition=dict(rule["precondition"]),
        expected_result=rule["expected_result"],
        success_check=dict(rule["success_check"]),
        failure_pattern=rule["failure_pattern"],
        recovery=rule["recovery"],
        next_phase=rule["next_phase"],
        scope=scope,
        source=str(rule.get("source", "")),
    )


def parse_phase_file(item: dict[str, Any]) -> list[Rule]:
    """解析一个 phase 文件 dict ``{"phase": ..., "rules": [...]}``。"""
    if not isinstance(item, dict) or "rules" not in item:
        raise ValueError("each phase file must be a dict with a 'rules' list")
    return [
        validate(rule, index=i) for i, rule in enumerate(item["rules"])
    ]


def parse_rules(data: Any) -> list[Rule]:
    """解析完整规则文档(phase 文件列表)。"""
    if isinstance(data, dict) and "phases" in data:
        data = data["phases"]
    if not isinstance(data, list):
        raise ValueError("rules JSON must be a list of phase files")
    rules: list[Rule] = []
    for item in data:
        rules.extend(parse_phase_file(item))
    return rules
