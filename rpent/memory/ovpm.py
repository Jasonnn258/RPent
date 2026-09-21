"""结果验证式程序记忆(OVP-M)—— 2026-09 研究的 B 臂。

v1 规则 schema 本就携带 ``expected_result`` / ``success_check``,
但它们此前只在 snapshot 时离线求值。本模块把
它们变成运行时契约:每个动作工具的结果都会对照
当前 phase 的预期结果检查,产出一条
MATCHED / MISMATCHED / UNCERTAIN 裁决并追加到 planner
已经在读的工具结果里(零额外 turn、零额外请求)。

真值只来自工具结果本身 —— 本体感知
(``min_gripper_opening``、``final_dist_m``)、已执行技能的自报
(``success``)和官方终止标志(``libero_terminated``)。
没有 benchmark GT、没有新原语、不动 VLA/SAM3。

注入行绝不能包含子串 "fail" 或 "error":
PhaseTracker 的 pick 启发式会在结果文本里 grep 这些词。

门控:``RPENT_OVPM=1``(需要 ``RPENT_STRUCTURED_MEMORY=1``)。
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any

from rpent.memory.schema import PHASE_ORDER
from rpent.memory.structured import ACTION_TOOLS

logger = logging.getLogger(__name__)

#: :meth:`OutcomeValidator._evaluate` 能理解的 verify 种类。
VERIFY_KINDS = frozenset(
    {
        "pick_holding",  # pi0_pick:success=true 或 min_gripper_opening < GRIP_TIGHT
        "released",  # release:peak_gripper_opening > GRIP_OPEN
        "moved_to_target",  # move_to:final_dist_m <= MOVE_TOL
        "task_terminated",  # libero_terminated === True(为 False 时判 mismatch)
        "task_terminated_opt",  # 同上,但 False 保持 UNCERTAIN(静默)
        "no_exception",  # 任意工具:执行且未抛异常
    }
)

#: 结果阈值 —— 来源同 analysis/pairing_analysis.py。
GRIP_TIGHT = 0.03  # 握住 := min_gripper_opening 低于此值
GRIP_OPEN = 0.05  # 已释放 := peak_gripper_opening 高于此值
MOVE_TOL = 0.03  # 已到达 := final_dist_m 低于此值(servo 容差 0.012)

#: 结果带可机器校验 outcome 的工具。
CONTRACT_TOOLS = frozenset(
    {"pi0_pick", "release", "move_to", "pi0_doubled", "set_gripper",
     "view_driver_state"}
)

_MAX_VERDICT_LOG = 200


@dataclasses.dataclass(frozen=True)
class OutcomeContract:
    """一条 ``action → expected outcome → verify → commit/recover`` 契约。"""

    id: str
    tool: str
    phases: tuple[str, ...]  # 契约适用的 phases("ANY" = 全部)
    action: str
    expected_outcome: str
    verify: dict[str, Any]  # {"kind": ...}(+ 可选的按 kind 参数)
    on_match: str
    on_mismatch: str
    next_phase: str = ""  # commit 目标("P_place"/"finish"/"" = 无)
    scope: str = "GLOBAL"  # GLOBAL | task<N> —— 语义同 Rule.scope
    source: str = ""

    def applies_to_phase(self, phase: str) -> bool:
        return "ANY" in self.phases or not self.phases or phase in self.phases

    def applies_to_task(self, task: str) -> bool:
        if self.scope == "GLOBAL":
            return True
        if not task:
            return False
        norm = self.scope.lower().replace("_", "")
        target = task.lower().replace("_", "")
        return target in norm or norm in target

    def scope_priority(self) -> int:
        """同一工具下,task 范围契约优先于 GLOBAL 契约。"""
        return 0 if self.scope == "GLOBAL" else 1


def parse_contracts(raw: dict[str, Any]) -> list[OutcomeContract]:
    """校验规则文档的 ``outcome_contracts`` 段。

    与 :func:`rpent.memory.schema.validate` 一样 fail-fast:坏契约
    在加载期暴露,而不是 episode 中途。
    """
    out: list[OutcomeContract] = []
    for i, c in enumerate(raw.get("outcome_contracts", [])):
        loc = f"contract#{i}"
        missing = [
            k for k in ("id", "tool", "expected_outcome", "verify",
                        "on_match", "on_mismatch") if k not in c
        ]
        if missing:
            raise ValueError(f"{loc} ({c.get('id', '?')}): missing {missing}")
        if c["tool"] not in CONTRACT_TOOLS:
            raise ValueError(f"{loc} ({c['id']}): unknown tool {c['tool']!r}")
        kind = c["verify"].get("kind")
        if kind not in VERIFY_KINDS:
            raise ValueError(f"{loc} ({c['id']}): unknown verify kind {kind!r}")
        for phase in c.get("phases", []):
            if phase not in PHASE_ORDER and phase != "ANY":
                raise ValueError(f"{loc} ({c['id']}): bad phase {phase!r}")
        np_ = c.get("next_phase", "")
        if np_ and np_ not in PHASE_ORDER and np_ != "finish":
            raise ValueError(f"{loc} ({c['id']}): bad next_phase {np_!r}")
        for field in ("on_match", "on_mismatch", "expected_outcome"):
            if "fail" in c[field] or "error" in c[field]:
                raise ValueError(
                    f"{loc} ({c['id']}): {field} contains a forbidden substring"
                    " ('fail'/'error' corrupt the PhaseTracker heuristics)"
                )
        out.append(
            OutcomeContract(
                id=c["id"],
                tool=c["tool"],
                phases=tuple(c.get("phases", ("ANY",))),
                action=c.get("action", ""),
                expected_outcome=c["expected_outcome"],
                verify=dict(c["verify"]),
                on_match=c["on_match"],
                on_mismatch=c["on_mismatch"],
                next_phase=np_,
                scope=c.get("scope", "GLOBAL"),
                source=c.get("source", ""),
            )
        )
    return out


def load_contracts(path: str | os.PathLike) -> list[OutcomeContract]:
    """从规则文档加载契约;文件缺失 => [] 并告警。"""
    p = Path(path)
    if not p.exists():
        logger.warning("[ovpm] contracts file not found: %s — validator is a no-op", p)
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return parse_contracts(raw)


# ---------------------------------------------------------------- 结果 IO


def _fields_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """从工具结果 JSON payload 提取 outcome 字段。

    兼顾实际出现的两种形态:直接工具结果把字段放在
    顶层;``view_driver_state`` 在 ``log.result`` 下回显
    上一条命令的结果。
    """
    out: dict[str, Any] = {}
    log = payload.get("log") or {}
    nested = log.get("result") or {}

    def grab(key: str) -> Any:
        v = payload.get(key)
        if v is None:  # 键缺失或显式为 null -> 尝试嵌套回显
            v = nested.get(key)
        return v

    for key in (
        "success",
        "min_gripper_opening",
        "peak_lift_m",
        "peak_gripper_opening",
        "start_gripper_opening",
        "final_gripper_opening",
        "final_dist_m",
        "libero_terminated",
        "chunks_used",
    ):
        v = grab(key)
        if v is not None:
            out[key] = v
    return out


def _describe_actual(kind: str, f: dict[str, Any]) -> str:
    """裁决行用的紧凑 ``actual=...`` 片段。"""
    bits = []
    if "success" in f:
        bits.append(f"success={str(f['success']).lower()}")
    for k in ("min_gripper_opening", "peak_lift_m", "peak_gripper_opening",
              "final_dist_m"):
        if k in f:
            try:
                bits.append(f"{k}={float(f[k]):.3f}")
            except (TypeError, ValueError):
                bits.append(f"{k}={f[k]}")
    if "libero_terminated" in f:
        bits.append(f"term={str(f['libero_terminated']).lower()}")
    return " ".join(bits) if bits else "no outcome fields"


def _evaluate(kind: str, f: dict[str, Any]) -> bool | None:
    """True/False 裁决;所需字段缺失时为 None。"""
    if kind == "pick_holding":
        if f.get("success") is True:
            return True
        mg = f.get("min_gripper_opening")
        if mg is None:
            return None
        try:
            return float(mg) < GRIP_TIGHT
        except (TypeError, ValueError):
            return None
    if kind == "released":
        pg = f.get("peak_gripper_opening")
        if pg is None:
            return None
        try:
            return float(pg) > GRIP_OPEN
        except (TypeError, ValueError):
            return None
    if kind == "moved_to_target":
        d = f.get("final_dist_m")
        if d is None:
            return None
        try:
            return float(d) <= MOVE_TOL
        except (TypeError, ValueError):
            return None
    if kind in ("task_terminated", "task_terminated_opt"):
        t = f.get("libero_terminated")
        if t is True:
            return True
        if t is False:
            return None if kind == "task_terminated_opt" else False
        return None
    if kind == "no_exception":
        return True  # 仅当工具没有抛异常才会走到这里
    return None


# ------------------------------------------------------------------ 校验器


class OutcomeValidator:
    """喂入工具结果;产出裁决行和延迟指标。

    纯逻辑 —— 无 I/O、无 prompt 副作用。planner 循环用
    模型将看到的原文本调用 :meth:`observe_result`;
    返回的行(若有)被追加到该文本。下面的 ``step`` 是
    校验器自己对已观察工具结果的计数 —— 两个延迟
    指标共用的决策步单位。
    """

    def __init__(
        self,
        contracts: list[OutcomeContract],
        *,
        tracker: Any = None,
        task: str = "",
    ) -> None:
        self._contracts = contracts
        self._tracker = tracker  # 仅用于查询 current_phase()
        self._task = task
        self._step = 0
        self._tool_n: dict[str, int] = {}
        self._consec_mismatch: dict[str, int] = {}
        self._hinted: set[tuple[str, str]] = set()  # (phase, 契约 id)
        self._hinted_phase = ""
        # 打开/关闭中的延迟事件(commit = matched→推进,recovery =
        # mismatch→换策略)
        self._open_commit: list[dict[str, Any]] = []
        self._open_recovery: list[dict[str, Any]] = []
        self.commit_events: list[dict[str, Any]] = []
        self.recovery_events: list[dict[str, Any]] = []
        self.verdicts: list[dict[str, Any]] = []
        self.n_matched = 0
        self.n_mismatched = 0
        self.n_uncertain = 0
        self.mismatch_escalations = 0
        self.repeated_same_strategy_after_mismatch = 0
        self._last_is_error = False

    # ------------------------------------------------------------ 选择

    def _contract_for(self, name: str, phase: str) -> OutcomeContract | None:
        best: OutcomeContract | None = None
        for c in self._contracts:
            if c.tool != name or not c.applies_to_phase(phase):
                continue
            if not c.applies_to_task(self._task):
                continue
            if best is None or c.scope_priority() > best.scope_priority():
                best = c
        return best

    def _phase(self) -> str:
        try:
            return self._tracker.current_phase()
        except Exception:  # noqa: BLE001 - tracker 可选
            return ""

    # ------------------------------------------------------------ 观察

    def observe_result(
        self,
        name: str,
        kwargs: dict[str, Any],
        result_text: str,
        *,
        is_error: bool = False,
        phase: str | None = None,
    ) -> str | None:
        """观察一个工具结果;返回裁决行或 None。

        该行由调用方追加到 ``result_text`` —— 模型在同一个
        工具结果里读到它,零 turn 成本。
        """
        self._step += 1
        self._tool_n[name] = self._tool_n.get(name, 0) + 1
        self._last_is_error = bool(is_error)
        ph = phase if phase is not None else self._phase()

        contract = self._contract_for(name, ph)
        matched: bool | None = None
        actual = ""
        if contract is not None:
            if is_error:
                matched = False
                actual = "tool raised"
            else:
                try:
                    payload = json.loads(result_text)
                except Exception:  # noqa: BLE001 - 无法解析 => uncertain
                    payload = None
                if not isinstance(payload, dict):
                    matched = None
                else:
                    f = _fields_from_payload(payload)
                    matched = _evaluate(contract.verify.get("kind", ""), f)
                    actual = _describe_actual(contract.verify.get("kind", ""), f)

        # 以这条新观察关闭未决的延迟事件。
        self._close_events(name, ph, matched)

        if name == "finish":
            return None  # finish 关闭事件;自身无裁决
        if contract is None:
            return None
        if matched is None:
            self.n_uncertain += 1
            self._log(name, ph, "UNCERTAIN", actual, contract)
            return None

        n = self._tool_n[name]
        if matched:
            self.n_matched += 1
            self._consec_mismatch[name] = 0
            self._log(name, ph, "MATCHED", actual, contract)
            return self._matched_line(name, n, ph, contract, actual)
        self.n_mismatched += 1
        k = self._consec_mismatch.get(name, 0) + 1
        self._consec_mismatch[name] = k
        self._log(name, ph, "MISMATCH", actual, contract)
        return self._mismatched_line(name, n, k, ph, contract, actual)

    # ------------------------------------------------------------- 裁决

    def _matched_line(
        self, name: str, n: int, phase: str, c: OutcomeContract, actual: str
    ) -> str | None:
        if not c.next_phase:
            return None  # 建议性契约:计数但不注入
        if phase != self._hinted_phase:
            self._hinted.clear()
            self._hinted_phase = phase
        key = (phase, c.id)
        already = key in self._hinted
        if c.next_phase != "finish" and already:
            return None  # 每契约每 phase 只提示一次 commit
        self._hinted.add(key)
        self._open_commit.append(
            {
                "tool": name,
                "step": self._step,
                "phase": phase,
                "next_phase": c.next_phase,
                "contract": c.id,
                "hinted_twice": False,
            }
        )
        target = c.next_phase
        where = f"proceed to {target}" if target != "finish" else "call finish now"
        return (
            f"[ovpm] {name}#{n} MATCHED — expected: {c.expected_outcome}; "
            f"actual: {actual}. Commit: {where}; {c.on_match}"
        )

    def _mismatched_line(
        self, name: str, n: int, k: int, phase: str, c: OutcomeContract, actual: str
    ) -> str:
        # 一次 mismatch 使同一工具打开的未决 commit 失效。
        self._open_commit = [e for e in self._open_commit if e["tool"] != name]
        self._open_recovery.append(
            {
                "tool": name,
                "step": self._step,
                "phase": phase,
                "contract": c.id,
                "consecutive": k,
            }
        )
        nth = f"({k}{'st' if k == 1 else 'nd' if k == 2 else 'rd' if k == 3 else 'th'}) "
        suffix = (
            " Repeating the same primitive unchanged is discouraged."
            if k >= 2
            else ""
        )
        return (
            f"[ovpm] {name}#{n} MISMATCH {nth}— expected: {c.expected_outcome}; "
            f"actual: {actual}. {c.on_mismatch}{suffix}"
        )

    # ------------------------------------------------------------- 延迟

    def _close_events(
        self, name: str, phase: str, matched: bool | None
    ) -> None:
        still_open: list[dict[str, Any]] = []
        for e in self._open_recovery:
            if name == "finish":
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "finish"
                self.recovery_events.append(e)
                continue
            # 只有*不同的动作*才算换策略 ——
            # mismatch 后重新观察(感知)是诊断而非
            # 恢复,不得关闭该事件。
            if name in ACTION_TOOLS and name != e["tool"]:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "switch"
                self.mismatch_escalations += 1
                self.recovery_events.append(e)
                continue
            # 再次同一动作工具:已解决或重复
            if matched is True:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "same_tool_resolved"
                self.recovery_events.append(e)
                continue
            if matched is False and name == e["tool"]:
                self.repeated_same_strategy_after_mismatch += 1
                e["consecutive"] = self._consec_mismatch.get(name, 1)
            still_open.append(e)
        self._open_recovery = still_open

        still_open = []
        for e in self._open_commit:
            if name == "finish":
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "finish"
                self.commit_events.append(e)
                continue
            cur = PHASE_ORDER.get(phase, -1)
            tgt = PHASE_ORDER.get(e.get("next_phase", ""), 99)
            if e.get("next_phase") == "finish":
                still_open.append(e)  # 只有 finish 能关闭它
                continue
            if cur > PHASE_ORDER.get(e.get("phase", ""), -1) and cur >= tgt:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "phase_advanced"
                self.commit_events.append(e)
                continue
            still_open.append(e)
        self._open_commit = still_open

    def turn_boundary_hint(self) -> str | None:
        """commit 裁决未被照办时的一行提醒。

        复用 SM1 注入节流:每个打开的 commit 事件至多发
        一次,且仅在 phase 未推进又过了 ≥2 个工具结果之后
        才发。
        """
        for e in self._open_commit:
            if e.get("next_phase") == "finish" or e.get("hinted_twice"):
                continue
            if self._step - e["step"] >= 2:
                e["hinted_twice"] = True
                return (
                    f"[ovpm] {e['tool']}#{self._tool_n.get(e['tool'], '?')} "
                    f"outcome was verified MATCHED at step {e['step']} — "
                    f"commit to {e['next_phase']} now; further confirmation "
                    "is redundant."
                )
        return None

    def commit_mode_ctx(self) -> dict[str, Any] | None:
        """C 臂(RPENT_REASON_MODE):单轮 COMMIT-MODE 资格判定。

        恰好在如下情形才合格:已验证 MATCHED 的 commit 仍打开(下一
        步已知)、无异常未决(无打开的 recovery 事件、上一动作结果
        非报错)、且该打开事件尚未消耗过 commit 轮。若模型仍不
        推进,后续边界会回退到带完整 agent 的 REASON
        MODE —— 构造上自纠。
        """
        if self._open_recovery or self._last_is_error:
            return None
        for e in self._open_commit:
            if e.get("commit_turn_used") or not e.get("next_phase"):
                continue
            e["commit_turn_used"] = True
            return {"target": e["next_phase"], "tool": e["tool"],
                    "step": e["step"]}
        return None

    # --------------------------------------------------------------- 输出

    def _log(
        self, name: str, phase: str, verdict: str, actual: str, c: OutcomeContract
    ) -> None:
        if len(self.verdicts) < _MAX_VERDICT_LOG:
            self.verdicts.append(
                {
                    "step": self._step,
                    "tool": name,
                    "phase": phase,
                    "verdict": verdict,
                    "contract": c.id,
                    "actual": actual,
                    "consecutive": self._consec_mismatch.get(name, 0),
                }
            )

    def snapshot(self, *, success: bool) -> dict[str, Any]:
        """单 episode 的 OVP-M 指标(并入 structured_metrics.json)。"""
        for e in self._open_commit:
            e["closed_by"] = "unclosed"
            e["latency_steps"] = None
            self.commit_events.append(e)
        for e in self._open_recovery:
            e["closed_by"] = "unclosed"
            e["latency_steps"] = None
            self.recovery_events.append(e)
        self._open_commit = []
        self._open_recovery = []

        def _mean(xs: list[int]) -> float | None:
            ys = [x for x in xs if x is not None]
            return round(sum(ys) / len(ys), 2) if ys else None

        return {
            "ovpm": True,
            "task": self._task,
            "contracts": [c.id for c in self._contracts],
            "n_matched": self.n_matched,
            "n_mismatched": self.n_mismatched,
            "n_uncertain": self.n_uncertain,
            "mismatch_escalations": self.mismatch_escalations,
            "repeated_same_strategy_after_mismatch": (
                self.repeated_same_strategy_after_mismatch
            ),
            "commit_events": self.commit_events,
            "recovery_events": self.recovery_events,
            "commit_latency_steps": [
                e["latency_steps"] for e in self.commit_events
            ],
            "commit_latency_mean": _mean(
                [e["latency_steps"] for e in self.commit_events]
            ),
            "recovery_latency_steps": [
                e["latency_steps"] for e in self.recovery_events
            ],
            "recovery_latency_mean": _mean(
                [e["latency_steps"] for e in self.recovery_events]
            ),
            "verdicts": self.verdicts,
            "success": success,
        }
