"""Structured Global Memory v1 — rule schema and validation.

Each rule is the executable form of one Global Memory entry, carrying the full
nine-field contract from the v1 spec: ``phase``, ``trigger``, ``precondition``,
``expected_result``, ``success_check``, ``failure_pattern``, ``recovery``,
``next_phase``, ``scope``.

Validation fails fast: a typo in a rules JSON (unknown field, bad phase, bad
predicate key) surfaces at load time, not mid-episode.
"""

from __future__ import annotations

import dataclasses
from typing import Any

#: Deterministic phase model — derived purely from tool-call counts.
PHASES = ("P_init", "P_look", "P_transport", "P_grasp", "P_place", "P_verify")
PHASE_ORDER = {p: i for i, p in enumerate(PHASES)}

#: Predicate keys accepted inside ``precondition`` / ``success_check`` dicts.
#: Every key in a predicate is AND'd; all keys are evaluated against the
#: tracker's windowed/cumulative counters.
PREDICATE_KEYS = frozenset(
    {
        # current phase matching
        "phase",            # equals (str)  | "ANY" matches anything
        "phase_ne",         # not equals (str)
        "phase_in",         # in a list of phases
        # counter thresholds (all AND'd)
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
        # exact cumulative per-tool count
        "tool_count",       # {tool_name: int}
        # misc
        "result_contains",  # last tool result contains substring
        "failure_marker",   # str marker (only "max_turns" supported)
        "finish_called",    # bool
    }
)

#: The nine mandated fields + ``source`` (evidence citation).
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
    """One structured memory rule."""

    id: str
    phase: str  # P_init..P_verify, or ANY
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
    """Validate one raw rule dict; return a frozen :class:`Rule`."""
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
    """Parse one phase-file dict ``{"phase": ..., "rules": [...]}``."""
    if not isinstance(item, dict) or "rules" not in item:
        raise ValueError("each phase file must be a dict with a 'rules' list")
    return [
        validate(rule, index=i) for i, rule in enumerate(item["rules"])
    ]


def parse_rules(data: Any) -> list[Rule]:
    """Parse the full rules document (list of phase files)."""
    if isinstance(data, dict) and "phases" in data:
        data = data["phases"]
    if not isinstance(data, list):
        raise ValueError("rules JSON must be a list of phase files")
    rules: list[Rule] = []
    for item in data:
        rules.extend(parse_phase_file(item))
    return rules
