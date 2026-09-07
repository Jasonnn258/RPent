"""Outcome-Validated Procedural Memory (OVP-M) — arm B of the 2026-09 study.

The v1 rule schema already carries ``expected_result`` / ``success_check``,
but they were only ever evaluated offline at snapshot time. This module
turns them into a runtime contract: every action-tool result is checked
against the expected outcome for the current phase, producing a
MATCHED / MISMATCHED / UNCERTAIN verdict that is appended to the tool
result the planner already reads (zero extra turns, zero extra requests).

Ground truth comes only from the tool result itself — proprioception
(``min_gripper_opening``, ``final_dist_m``), executed-skill self-report
(``success``) and the official termination flag (``libero_terminated``).
No benchmark GT, no new primitives, no VLA/SAM3 changes.

Injected lines must never contain the substrings "fail" or "error": the
PhaseTracker's pick heuristic greps the result text for those words.

Gate: ``RPENT_OVPM=1`` (requires ``RPENT_STRUCTURED_MEMORY=1``).
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

#: Verify kinds understood by :meth:`OutcomeValidator._evaluate`.
VERIFY_KINDS = frozenset(
    {
        "pick_holding",  # pi0_pick: success=true OR min_gripper_opening < GRIP_TIGHT
        "released",  # release: peak_gripper_opening > GRIP_OPEN
        "moved_to_target",  # move_to: final_dist_m <= MOVE_TOL
        "task_terminated",  # libero_terminated === True (mismatch when False)
        "task_terminated_opt",  # same, but False stays UNCERTAIN (silent)
        "no_exception",  # any tool: executed without raising
    }
)

#: Outcome thresholds — same sources as analysis/pairing_analysis.py.
GRIP_TIGHT = 0.03  # holding := min_gripper_opening below this
GRIP_OPEN = 0.05  # released := peak_gripper_opening above this
MOVE_TOL = 0.03  # arrived := final_dist_m below this (servo tol is 0.012)

#: Tools whose results carry a machine-checkable outcome.
CONTRACT_TOOLS = frozenset(
    {"pi0_pick", "release", "move_to", "pi0_doubled", "set_gripper",
     "view_driver_state"}
)

_MAX_VERDICT_LOG = 200


@dataclasses.dataclass(frozen=True)
class OutcomeContract:
    """One ``action → expected outcome → verify → commit/recover`` contract."""

    id: str
    tool: str
    phases: tuple[str, ...]  # phases the contract applies in ("ANY" = all)
    action: str
    expected_outcome: str
    verify: dict[str, Any]  # {"kind": ...} (+ optional per-kind params)
    on_match: str
    on_mismatch: str
    next_phase: str = ""  # commit target ("P_place"/"finish"/"" = none)
    scope: str = "GLOBAL"  # GLOBAL | task<N> — same semantics as Rule.scope
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
        """Task-scoped contracts win over GLOBAL ones for the same tool."""
        return 0 if self.scope == "GLOBAL" else 1


def parse_contracts(raw: dict[str, Any]) -> list[OutcomeContract]:
    """Validate the ``outcome_contracts`` section of a rules document.

    Fail-fast like :func:`rpent.memory.schema.validate`: a bad contract
    surfaces at load time, not mid-episode.
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
    """Load contracts from a rules document; missing file => [] with warning."""
    p = Path(path)
    if not p.exists():
        logger.warning("[ovpm] contracts file not found: %s — validator is a no-op", p)
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return parse_contracts(raw)


# ---------------------------------------------------------------- outcome IO


def _fields_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract outcome fields from a tool-result JSON payload.

    Handles both shapes in the wild: direct tool results carry the fields at
    the top level; ``view_driver_state`` echoes the last command's result
    under ``log.result``.
    """
    out: dict[str, Any] = {}
    log = payload.get("log") or {}
    nested = log.get("result") or {}

    def grab(key: str) -> Any:
        v = payload.get(key)
        if v is None:  # key absent OR explicitly null -> try the nested echo
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
    """Compact ``actual=...`` fragment for the verdict line."""
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
    """True/False verdict, or None when the fields needed are absent."""
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
        return True  # reached only when the tool did not raise
    return None


# ------------------------------------------------------------------ validator


class OutcomeValidator:
    """Feed tool results in; get verdict lines and latency metrics out.

    Pure logic — no I/O, no prompt side effects. The planner loop calls
    :meth:`observe_result` with exactly the text the model will see; the
    returned line (if any) is appended to that text. ``step`` below is the
    validator's own count of observed tool results — the decision-step unit
    for both latency metrics.
    """

    def __init__(
        self,
        contracts: list[OutcomeContract],
        *,
        tracker: Any = None,
        task: str = "",
    ) -> None:
        self._contracts = contracts
        self._tracker = tracker  # queried for current_phase() only
        self._task = task
        self._step = 0
        self._tool_n: dict[str, int] = {}
        self._consec_mismatch: dict[str, int] = {}
        self._hinted: set[tuple[str, str]] = set()  # (phase, contract id)
        self._hinted_phase = ""
        # open / closed latency events (commit = matched→advance, recovery =
        # mismatch→strategy switch)
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

    # ------------------------------------------------------------ selection

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
        except Exception:  # noqa: BLE001 - tracker is optional
            return ""

    # ------------------------------------------------------------ observing

    def observe_result(
        self,
        name: str,
        kwargs: dict[str, Any],
        result_text: str,
        *,
        is_error: bool = False,
        phase: str | None = None,
    ) -> str | None:
        """Observe one tool result; return the verdict line or None.

        The line is appended to ``result_text`` by the caller — the model
        reads it inside the same tool result, at zero turn cost.
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
                except Exception:  # noqa: BLE001 - unparseable => uncertain
                    payload = None
                if not isinstance(payload, dict):
                    matched = None
                else:
                    f = _fields_from_payload(payload)
                    matched = _evaluate(contract.verify.get("kind", ""), f)
                    actual = _describe_actual(contract.verify.get("kind", ""), f)

        # Close pending latency events against this new observation.
        self._close_events(name, ph, matched)

        if name == "finish":
            return None  # finish closes events; no verdict of its own
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

    # ------------------------------------------------------------- verdicts

    def _matched_line(
        self, name: str, n: int, phase: str, c: OutcomeContract, actual: str
    ) -> str | None:
        if not c.next_phase:
            return None  # advisory contract: counted, not injected
        if phase != self._hinted_phase:
            self._hinted.clear()
            self._hinted_phase = phase
        key = (phase, c.id)
        already = key in self._hinted
        if c.next_phase != "finish" and already:
            return None  # one commit hint per contract per phase
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
        # A mismatch invalidates the pending commit opened by the same tool.
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

    # ------------------------------------------------------------- latency

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
            # Only a *different action* counts as a strategy switch —
            # re-observing (perception) after a mismatch is diagnosis, not
            # recovery, and must not close the event.
            if name in ACTION_TOOLS and name != e["tool"]:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "switch"
                self.mismatch_escalations += 1
                self.recovery_events.append(e)
                continue
            # same action tool again: resolved or repeated
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
                still_open.append(e)  # only finish closes it
                continue
            if cur > PHASE_ORDER.get(e.get("phase", ""), -1) and cur >= tgt:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "phase_advanced"
                self.commit_events.append(e)
                continue
            still_open.append(e)
        self._open_commit = still_open

    def turn_boundary_hint(self) -> str | None:
        """One-line reminder when a commit verdict has not been acted on.

        Reuses the SM1 injection throttle: emitted at most once per open
        commit event, only after ≥2 further tool results without the phase
        advancing.
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
        """Arm C (RPENT_REASON_MODE): COMMIT-MODE eligibility for one turn.

        Eligible exactly when a verified-MATCHED commit is still open (the
        next step is known), nothing anomalous is pending (no open recovery
        events, last action result not an error), and this open event has
        not already consumed a commit turn. If the model still does not
        advance, later boundaries fall back to REASON MODE with the full
        agent — self-correcting by construction.
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

    # --------------------------------------------------------------- output

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
        """Per-episode OVP-M metrics (merged into structured_metrics.json)."""
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
