"""B3 — Active Verification + Verdict Compliance.

B2 (``rpent.memory.stv``) answered *can the verifier judge correctly?* — yes:
verdicts matched physical reality, no loops, commit latency halved. B3 leaves
the frozen verifier untouched and attacks the two bottlenecks B2 exposed:

1. **Verdict compliance** (~39-49% obey rate). The planner reads a verdict and
   proceeds with the plan anyway. B3-A adds an explicit verdict protocol:
   SUCCESS -> commit; NOT-established -> recover (changed approach);
   UNCERTAIN -> acquire the requested evidence before any task action;
   REASON -> one deliberate step. Every verdict's *actual* next action is
   classified obeyed/violated (behavioral, not textual assent) and logged to
   ``b3_compliance_events.jsonl``; violations get an injected reminder line.

2. **Evidence timing**. Most UNCERTAINs land where failure is undecidable
   (object still at its spot, gripper still next to it — the failure
   signature needs the gripper to have left). B3-B adds
   *retreat-and-reobserve*: on an UNCERTAIN evidence directive the verifier
   appends a deterministic probe instruction — ``move_to`` one fixed
   retreat vector clear of the object, then re-segment — and runs the SAME
   frozen resolution logic on the post-retreat state. The probe move is
   transparent to the pending machinery (it is verification, not a task
   action) and is counted separately (``b3_probe_events.jsonl``).

B3-C = both. Gates: ``RPENT_B3_COMPLY=1`` / ``RPENT_B3_PROBE=1``
(both require ``RPENT_OVPM2=1``). Compliance *logging* is always on for the
subclass (the 2x2 needs obedience rates on every arm); with both gates off
no injected text changes, so planner-visible behavior is byte-identical to
frozen B2 — enforced by tests.

Injected-line hygiene is inherited from B2: never the substrings
"fail"/"error"/"could not"/"no object" (the PhaseTracker greps for those).
The failure verdict class is therefore referred to in injected text only as
"NOT_ESTABLISHED" / "objective NOT established".
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

# ------------------------------------------------------------- B3 constants
PROBE_RETREAT_DY = 0.12  # retreat vector: back off the table center ...
PROBE_RETREAT_DZ = 0.10  # ... and up. |v| ~ 0.156 m > HOLD_RADIUS (0.15):
PROBE_Z_MAX = 1.15       # a held object follows, a left one stays put.
PROBE_TARGET_TOL = 0.02  # a move_to within this of the issued target = probe
MAX_PROBES_PER_PENDING = 1  # one probe per open verification, then the frozen
MAX_PROBES_PER_EPISODE = 4  # OBSERVE->REASON path — probes can never loop
PERCEPTION_TOOLS = frozenset(
    {"segment", "back_project", "view_driver_state", "view_camera_meta"})

# Verdict classes, classified from the frozen line formats (stable strings).
_CLS_SUCCESS = "state change CONFIRMED"
_CLS_FAILURE = "NOT established"
_CLS_UNCERTAIN = "Observe once"
_CLS_REASON = "Reason explicitly"

# Class tokens safe for injected text (hygiene: no "fail" substring).
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
    """Verdict class of a frozen B2 verdict line (its formats are stable)."""
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
    """Did a same-tool retry change the approach (target/prompt/pose)?"""
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
        return True  # unknown tool: any retry counts as changed
    if not keys:
        return False  # release(): nothing to change — same call = unchanged
    for k in keys:
        if a.get(k) != b.get(k):
            return True
    return False


class ActiveVerifier(TransitionVerifier):
    """Frozen B2 + (optional) verdict-compliance enforcement and/or
    retreat-and-reobserve probing. Zero edits to judgment rules: every
    verdict still comes from the frozen code, verbatim."""

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
        # compliance state
        self._awaiting: dict[str, Any] | None = None
        self._protocol_sent = False
        self._violation_line: str | None = None
        self.verdicts: dict[str, int] = {"SUCCESS": 0, "FAILURE": 0,
                                         "UNCERTAIN": 0, "REASON": 0}
        self.obeyed: dict[str, int] = dict(self.verdicts)
        self.violated: dict[str, int] = dict(self.verdicts)
        # probe state
        self._probe_issued: dict[str, Any] | None = None
        self._probe_armed: dict[str, Any] | None = None  # move executed,
        # waiting for the re-observation to resolve the pending
        self.probe_directives = 0
        self.probe_executed = 0
        self.probe_ignored = 0
        self.probe_abandoned = 0
        self.probe_results = {"to_success": 0, "to_failure": 0,
                              "still_uncertain": 0}
        self._probe_latencies: list[int] = []
        self._armed_s0 = 0
        self._armed_f0 = 0

    # ------------------------------------------------------------ plumbing

    def _emit3(self, kind: str, ev: dict[str, Any]) -> None:
        """Append a B3 event to its own JSONL (best-effort, never fatal)."""
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

    # ---------------------------------------------------------- compliance

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
        """Behavioral compliance: does THIS tool call honor the verdict that
        is still awaiting a response? Emits one compliance event."""
        a = self._awaiting
        self._awaiting = None
        if a is None:
            return
        cls, tool = a["cls"], a["tool"]
        if name == "finish":
            obeyed = cls in ("SUCCESS", "FAILURE", "REASON")
        elif cls == "SUCCESS":
            obeyed = True  # commit: anything proceeds
        elif cls == "FAILURE":
            if name != tool:
                obeyed = True  # switched action = recovery
            else:
                obeyed = _args_relevantly_different(name, kwargs,
                                                    a.get("kwargs") or {})
        elif cls == "UNCERTAIN":
            if name in PERCEPTION_TOOLS or self._probe_hit(name, kwargs):
                obeyed = True  # evidence acquisition (incl. the probe)
            else:
                obeyed = False
        else:  # REASON
            obeyed = True  # one deliberate step is whatever comes next
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

    # -------------------------------------------------------------- probe

    def _probe_hit(self, name: str, kwargs: dict[str, Any]) -> bool:
        """Is this action the issued verification probe (exact retreat)?"""
        if not self._probe_issued or name not in ("move_to", "move_pose"):
            return False
        t = _xyz(kwargs.get("xyz") or kwargs.get("target"))
        if t is None:
            return False
        d = _dist(t, tuple(self._probe_issued["target"]))
        return d is not None and d <= PROBE_TARGET_TOL

    def _maybe_issue_probe(self, line: str | None) -> str | None:
        """Append the retreat-and-reobserve instruction to an UNCERTAIN
        evidence directive (B3-B). One probe per pending, capped per
        episode; deterministic target from the freshest eef."""
        if not line or not self.probe:
            return line
        if _classify_line(line) != "UNCERTAIN" or self._pending is None:
            return line
        if self._pending.get("wants") != "object_position":
            return line
        if self._pending.get("probes_used", 0) >= MAX_PROBES_PER_PENDING:
            return line
        if self._probe_issued is not None:
            return line  # one live directive at a time
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
        """Record the outcome transition of an executed probe once its
        pending verification resolves (or the pending closes without
        resolving)."""
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

    # ------------------------------------------------------- main entry

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

        # 1) behavioral compliance for the incoming tool vs the awaiting
        #    verdict. Grip maintenance (closing set_gripper) is transparent
        #    in B2 and answers no protocol question — skip it.
        if self._awaiting is not None and \
                not _is_grip_maintenance(name, kwargs) and \
                (is_action or name in PERCEPTION_TOOLS or name == "finish"):
            self._classify_incoming(name, kwargs, ph)
        violation = self._violation_line
        self._violation_line = None

        # 2) the issued probe move is transparent to the frozen machinery
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
            return None  # no verdict, no overtake, no TRANSPORT judgment

        # 3) any other action while a probe directive is live: ignored
        if self._probe_issued is not None and is_action:
            self.probe_ignored += 1
            self._emit3("probe", {"event": "ignored", "by": name})
            self._probe_issued = None

        # 4) frozen B2 path (unchanged judgment; emits its own events)
        line = super().observe_result(
            name, kwargs, result_text, is_error=is_error, phase=phase)

        # 5) probe result instrumentation: if the pending that a probe was
        #    armed for resolves now, classify the transition
        if self._probe_armed is not None:
            res = self.uncertain_resolutions
            if res.get("resolved_success", 0) > self._armed_s0:
                self._close_probe("to_success")
            elif res.get("resolved_failure", 0) > self._armed_f0:
                self._close_probe("to_failure")
            elif self._pending is None:  # overtaken / REASON / closed
                self._close_probe("still_uncertain")
        self._armed_s0 = self.uncertain_resolutions.get("resolved_success", 0)
        self._armed_f0 = self.uncertain_resolutions.get("resolved_failure", 0)

        # 6) directive abandoned (pending closed without the probe running)
        if self._probe_issued is not None and self._pending is None:
            self.probe_abandoned += 1
            self._emit3("probe", {"event": "abandoned"})
            self._probe_issued = None

        # 7) post-processing: probe directive / awaiting / violation /
        #    one-time protocol preamble
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

    # ------------------------------------------------------------ snapshot

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
