"""Structured Memory + Dual-Route Reasoning — Fast/Slow decider.

Layer added on top of Structured Memory (SM1): keep the phase/rule engine
unchanged and gate every model call behind a decision.

- **Fast**: phase state matches expectation, next step is clear, no recent
  failure -> execute a conservative zero-argument action from the structured
  plan WITHOUT calling the LLM (no Kimi request).
- **Slow**: any of the trigger conditions -> full reasoning as today.

The Fast action set is deliberately minimal and zero-arg (all move/pick/perceive
actions require the model):
    view_driver_state()   -> P_verify termination check
    release()             -> grasp -> target placement when it is unambiguous
    finish(status,summary)-> episode ended (success confirmed or budget spent)

The router is pure and side-effect-free: all state comes in as arguments and is
tracked via ``observe_fast``. It is unit-tested against a PhaseTracker stub.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

P_VERIFY = "P_verify"
P_GRASP = "P_grasp"
P_PLACE = "P_place"


@dataclass(frozen=True)
class FastAction:
    """One zero-arg action the planner can take without an LLM call."""

    name: str
    args: dict[str, Any]
    kind: str
    summary: str


class DualRouter:
    """Pure Fast/Slow decider. No I/O; all inputs injected. Testable."""

    def __init__(self, *, enable_release: bool = True) -> None:
        self.enable_release = enable_release
        # P_verify chain state (set by observe_fast on the vds result)
        self._vds_done = False
        self._vds_terminated = False
        # Slow telemetry
        self.slow_reason = ""
        self.slow_reasons: list[str] = []

    # ------------------------------------------------------------------ decide
    def decide(
        self, *, total_steps: int, max_turns: int, tracker: Any
    ) -> FastAction | None:
        """Return the Fast action to take, or None to fall back to Slow.

        ``tracker`` is any object exposing the read-only dual-route surface:
        ``last_is_error``, ``recovery_pending()``, ``current_phase()``,
        ``last_pick_success``, ``moves_since_pick``, ``finish_called``.
        """
        # 1. budget exhausted and the episode did not finish -> fast failure
        if total_steps >= max_turns and not tracker.finish_called:
            return FastAction(
                "finish",
                {"status": "failure", "summary": "step budget exhausted"},
                "budget_finish",
                "Fast finish(status=failure) — step budget exhausted.",
            )

        # 2. recent tool error -> the model must recover
        if tracker.last_is_error:
            return self._slow("last_error")

        # 3. a current-phase rule is satisfied but not yet fired -> the model
        #    must consume the recovery (P_verify excluded: its vds chain below
        #    has priority and its own finish path)
        pending = tracker.recovery_pending()
        if pending is not None and tracker.current_phase() != P_VERIFY:
            return self._slow("pending_rule")

        # 4. P_verify -> view_driver_state/finish chain (no loops by construction)
        if tracker.current_phase() == P_VERIFY:
            if not self._vds_done:
                return FastAction(
                    "view_driver_state",
                    {},
                    "p_verify_view",
                    "Fast view_driver_state() — confirming final placement / "
                    "episode termination at P_verify.",
                )
            if self._vds_terminated:
                return FastAction(
                    "finish",
                    {"status": "success", "summary": "episode terminated — "
                     "placement confirmed"},
                    "p_verify_finish",
                    "Fast finish(status=success) — episode terminated, "
                    "placement confirmed at P_verify.",
                )
            return self._slow("p_verify_unterminated")

        # 5. release gate: grasp succeeded, travelled to target, phase allows a
        #    placement, nothing else pending -> fast release()
        if (
            self.enable_release
            and tracker.current_phase() in (P_GRASP, P_PLACE)
            and tracker.last_pick_success
            and tracker.moves_since_pick >= 1
            and pending is None
            and not tracker.last_is_error
        ):
            return FastAction(
                "release",
                {},
                "release",
                "Fast release() — object at target, opening gripper.",
            )

        # 6. otherwise the model reasons
        return self._slow("not_fast_eligible")

    # ---------------------------------------------------------------- observe
    def observe_fast(self, action: FastAction, result: dict[str, Any]) -> None:
        """Feed a Fast action's result back so the next decide is consistent."""
        if action.name == "view_driver_state":
            self._vds_done = True
            self._vds_terminated = bool(result.get("libero_terminated"))

    # ------------------------------------------------------------------ slow
    def _slow(self, reason: str) -> None:
        self.slow_reason = reason
        self.slow_reasons.append(reason)
        return None
