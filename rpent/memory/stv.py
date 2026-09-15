"""B2 — Evidence-Sufficient State-Transition Verification (arm B2).

B1 (:mod:`rpent.memory.ovpm`) judges an action by binary outcome checks on
the tool result's own fields — most notoriously ``pi0_pick``'s tight-grip
signal, which fires on an empty gripper that simply closed on nothing.
B2 replaces the *binary outcome* question ("did the reported metric pass?")
with a *state-transition* question: given the pre-state, the action, and
the post-state, did the world change the way this action type is supposed
to change it?

Templates are action-level and general (GRASP / PLACE / TRANSPORT /
CONTACT / ROTATE). No task-scoped rules, no phase scoping, no new tools.
Evidence comes only from what the planner already sees: tool-result fields
(proprioception, the official termination flag), SAM3 ``segment`` /
``back_project`` world positions, and ``view_driver_state``. No benchmark
ground truth, no privileged object coordinates.

GRASP confirmation always requires object-level state evidence (the object
left its support / rides with the gripper): calibrated on 160 recorded
arm-B picks, gripper-opening distributions of true and false holds fully
overlap, so proprioception alone can disprove a grasp (gripper stayed
open) but never confirm one.

Verdicts are three-way and drive an explicit next decision:

  CONFIRMED_SUCCESS -> COMMIT    proceed; further verification is redundant
  CONFIRMED_FAILURE -> RECOVER   switch strategy; do not repeat unchanged
  UNCERTAIN         -> OBSERVE   one targeted observation; if that does not
                                 resolve it, REASON (bounded, never loops)

Every judgment is appended to ``<output_dir>/b2_events.jsonl`` with the
pre-state summary, expected vs observed change, evidence lists, verdict,
decision, and the rule template that produced it.

Injected lines must never contain the substrings "fail"/"error"/"could
not"/"no object": the PhaseTracker pick heuristic greps result text for
those words. ``CONFIRMED_FAILURE`` therefore lives only in the JSONL and
metrics; injected lines say "objective NOT established".

Gate: ``RPENT_OVPM2=1`` (requires ``RPENT_STRUCTURED_MEMORY=1`` — the SM1
tracker supplies phase context for the logs and latency accounting,
nothing more).
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from rpent.memory.ovpm import (
    GRIP_OPEN,
    GRIP_TIGHT,
    MOVE_TOL,
    _fields_from_payload,
)
from rpent.memory.schema import PHASE_ORDER

logger = logging.getLogger(__name__)

#: Action tool -> rule template. General by construction: keyed on action
#: semantics, never on task identity.
TEMPLATES: dict[str, str] = {
    "pi0_pick": "GRASP",
    "release": "PLACE",
    "set_gripper": "PLACE",  # only judged when opening (gripper <= 0)
    "move_to": "TRANSPORT",
    "move_pose": "TRANSPORT",
    "pi0_doubled": "CONTACT",
    "rotate_wrist": "ROTATE",
    "rotate_pitch": "ROTATE",
}

EXPECTED_CHANGE: dict[str, str] = {
    "GRASP": (
        "object held: gripper closed on the object (fingers blocked apart, "
        "not pinned shut), object detached from its original support, object "
        "moving with the gripper"
    ),
    "PLACE": (
        "object no longer held: gripper opened, object at rest at the "
        "intended place location, final relation consistent with the task goal"
    ),
    "TRANSPORT": (
        "purpose-relative only: end effector arrived at the commanded target "
        "with the carried object still along"
    ),
    "CONTACT": "contact skill achieved its effect (official termination set)",
    "ROTATE": "wrist reached the commanded orientation",
}

# --------------------------------------------------------------- thresholds
# Quantities shared with B1 reuse its constants; the rest are B2's own.

NEVER_CLOSED_TOL = 0.06  # min_gripper_opening above this = never closed
FULLY_CLOSED_EPS = 0.004  # below this the fingers pinned shut on nothing
LIFT_MIN = 0.05  # pi0_pick's own lift threshold
OBJ_MOVE_TOL = 0.04  # displacement that counts as "left its support"
OBJ_STAY_TOL = 0.03  # within this of the pre-pick spot = left behind
HOLD_RADIUS = 0.15  # object within this of the eef = consistent with held
NEAR_EEF = 0.08  # tighter post-release ambiguity band
PLACE_TOL = 0.10  # object within this of the last transport target
PLACE_FAR = 0.20  # beyond this from target (and from eef) = misplaced
MAX_OBSERVE_ROUNDS = 2  # directed observations per pending verification
STALL_STEPS = 4  # tool results without action before REASON escalation

_MAX_EVENT_LOG = 400


def _dist(a: tuple[float, ...] | None, b: tuple[float, ...] | None) -> float | None:
    if not a or not b or len(a) < 3 or len(b) < 3:
        return None
    return float(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)) ** 0.5)


def _xyz(v: Any) -> tuple[float, float, float] | None:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        try:
            return (float(v[0]), float(v[1]), float(v[2]))
        except (TypeError, ValueError):
            return None
    return None


# --------------------------------------------------------------- label words
# Smoke-run finding (2026-09-15): the planner segments the SAME object under
# different wordings ("the black patterned bowl" pre-pick, "the black
# patterned bowl held in the gripper" post-pick) and picks via natural
# language ("grasp the upper right black bowl by the rim"). Exact-string
# label equality therefore misses the evidence; match on shared content
# words instead. Fallback labels ("segment@12") carry no semantics.

_LABEL_STOP = frozenset({
    "the", "a", "an", "of", "on", "in", "at", "to", "by", "with", "and",
    "or", "not", "up", "held", "gripper", "robot", "its", "it", "this",
    "that", "from", "for",
})


def _label_tokens(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if w not in _LABEL_STOP and len(w) > 2
    }


def _match_label(query: str, records: dict[str, dict[str, Any]]) -> str | None:
    """Cached label sharing >=2 content tokens with *query* (max shared,
    then most recently observed). None when nothing clears the bar."""
    q = _label_tokens(query)
    if not q:
        return None
    best: str | None = None
    best_key = (1, -1)  # (shared tokens, recency) — 1 = below the bar
    for lbl, rec in records.items():
        if "@" in lbl:
            continue
        key = (len(q & _label_tokens(lbl)), rec.get("step", -1))
        if key[0] >= 2 and key > best_key:
            best, best_key = lbl, key
    return best


def _labels_related(a: str | None, b: str | None) -> bool:
    """True when two labels plausibly name the same object (or either is a
    semantic-free fallback), for gating which observations may consume a
    pending verification round."""
    if not a or not b or "@" in a or "@" in b:
        return True
    return a == b or len(_label_tokens(a) & _label_tokens(b)) >= 2


def _is_grip_maintenance(name: str, kwargs: dict[str, Any]) -> bool:
    """Closing actuation (``set_gripper`` gripper>0) is grip maintenance, not
    a state-transition step: it must not overtake an open verification (the
    smoke run showed the planner firming the grip BEFORE running the
    directed observation — the evidence arrives one action later)."""
    if name != "set_gripper":
        return False
    try:
        return float(kwargs.get("gripper", -1.0)) > 0
    except (TypeError, ValueError):
        return False


class TransitionVerifier:
    """Feed tool results in; get three-way verdict lines and metrics out.

    Mirrors :class:`rpent.memory.ovpm.OutcomeValidator` so the planner-loop
    wiring is symmetric: ``observe_result`` returns the line (if any) that
    the caller appends to the tool result text — zero extra turns. The
    verdict text itself avoids the PhaseTracker's forbidden substrings.
    """

    def __init__(self, *, tracker: Any = None, task: str = "") -> None:
        self._tracker = tracker  # phase context for logs/latency only
        self._task = task
        self._step = 0
        self._tool_n: dict[str, int] = {}
        # world-fact cache — mutated only inside observe_result, so a
        # snapshot taken when an action's result arrives IS the pre-state.
        self._obj: dict[str, dict[str, Any]] = {}  # label -> {xyz, step}
        self._eef: tuple[float, float, float] | None = None
        self._eef_step = -1
        self._grip: float | None = None
        self._grip_step = -1
        self._held: str | None = None  # label hypothesized held
        self._target: tuple[float, float, float] | None = None  # last transport
        self._target_step = -1
        self._pending: dict[str, Any] | None = None
        self._last_action_step = -1
        # counters
        self.n_success = 0
        self.n_failure = 0
        self.n_uncertain = 0
        self.n_observe_directives = 0
        self.n_observe_obeyed = 0
        self.n_reason_escalations = 0
        self.n_redundant_obs = 0
        self.false_positive_caught = 0
        self.uncertain_resolutions = {
            "resolved_success": 0,
            "resolved_failure": 0,
            "resolved_reason": 0,
            "overtaken": 0,
            "unresolved": 0,
        }
        # latency events (same semantics as B1: commit = confirmed success ->
        # advance; recovery = confirmed failure -> different action tool)
        self._open_commit: list[dict[str, Any]] = []
        self._open_recovery: list[dict[str, Any]] = []
        self.commit_events: list[dict[str, Any]] = []
        self.recovery_events: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    # ------------------------------------------------------------- helpers

    def _phase(self) -> str:
        try:
            return self._tracker.current_phase()
        except Exception:  # noqa: BLE001 - tracker is optional
            return ""

    def _pre_state_summary(self) -> dict[str, Any]:
        """Compact snapshot of everything known *before* the current event."""
        return {
            "held": self._held,
            "eef": list(self._eef or ()),
            "eef_step": self._eef_step if self._eef else None,
            "gripper_opening": self._grip,
            "objects": {
                lbl: {"xyz": list(v["xyz"]), "step": v["step"]}
                for lbl, v in self._obj.items()
            },
            "last_transport_target": list(self._target or ()),
        }

    def _last_label(self, real_only: bool = False) -> str | None:
        """Most recently observed object label (planners localize the grasp
        target immediately before picking it — action-level, not task-level).
        ``real_only`` skips point-observation fallback labels ("segment@12")
        that carry no reusable semantics."""
        items = list(self._obj.items())
        if real_only:
            items = [(l, v) for l, v in items if "@" not in l]
        if not items:
            return None
        lbl, v = max(items, key=lambda kv: kv[1]["step"])
        return lbl if v["step"] >= 0 else None

    @staticmethod
    def _segment_directive(label: str | None) -> str:
        """Actionable observation directive; never quotes a fallback label."""
        if label and "@" not in label:
            return f"segment(prompt='{label}', camera='agentview')"
        return "segment the object in question (text prompt or point)"

    # ------------------------------------------------------------ events IO

    def _emit(self, ev: dict[str, Any]) -> None:
        ev.setdefault("episode", _episode_id())
        ev.setdefault("task", self._task)
        ev.setdefault("seed", os.environ.get("RPENT_B2_SEED", ""))
        ev.setdefault("repeat", os.environ.get("RPENT_B2_REPEAT", ""))
        ev.setdefault("turn", self._step)
        ev.setdefault("phase", self._phase())
        ev.setdefault("confidence", None)
        ev.setdefault("verification_source", "tool_result_fields+state_cache")
        if len(self.events) < _MAX_EVENT_LOG:
            self.events.append(ev)
        try:
            out = _output_dir()
            if out is not None:
                with open(out / "b2_events.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        except Exception as e:  # noqa: BLE001 - logging must never break a run
            logger.warning("[b2] event log write failed: %s", e)

    def _base_event(
        self, tool: str, template: str, pre: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "action": tool,
            "rule_template": template,
            "expected_change": EXPECTED_CHANGE[template],
            "pre_state_summary": pre,
            "observed_change": "",
            "evidence_for_success": [],
            "evidence_for_failure": [],
            "missing_evidence": [],
            "b1_style_would_match": None,
            "pending_of": None,
        }

    # -------------------------------------------------------- verdict lines

    def _commit_line(self, tool: str, why: str, what_next: str) -> str:
        n = self._tool_n.get(tool, 0)
        return (
            f"[b2] {tool}#{n} state change CONFIRMED — {why}. "
            f"Commit: {what_next} Further verification of this step is redundant."
        )

    def _recover_line(self, tool: str, why: str, what_next: str) -> str:
        n = self._tool_n.get(tool, 0)
        return (
            f"[b2] {tool}#{n} objective NOT established — {why}. "
            f"Recover: {what_next}"
        )

    def _observe_line(self, tool: str, missing: str, directive: str) -> str:
        return (
            f"[b2] {tool} evidence incomplete ({missing}). Observe once before "
            f"proceeding: {directive} Act on what you see — repeating {tool} "
            "unchanged before checking is discouraged."
        )

    def _reason_line(self, tool: str, rounds: int) -> str:
        return (
            f"[b2] evidence about {tool} is still incomplete after {rounds} "
            "directed observations. Reason explicitly: state what the last "
            "action achieved and what it did not, then choose ONE deliberate "
            "next step (retry once with a changed approach, or proceed and "
            "verify at the next natural checkpoint). Alternating checks "
            "without acting burns the budget."
        )

    # --------------------------------------------------------- main entry

    def observe_result(
        self,
        name: str,
        kwargs: dict[str, Any],
        result_text: str,
        *,
        is_error: bool = False,
        phase: str | None = None,
    ) -> str | None:
        """Observe one tool result; return the verdict line or None."""
        self._step += 1
        self._tool_n[name] = self._tool_n.get(name, 0) + 1
        ph = phase if phase is not None else self._phase()
        try:
            payload = json.loads(result_text)
        except Exception:  # noqa: BLE001 - unparseable
            payload = None
        if not isinstance(payload, dict):
            payload = None

        if name in ("segment", "back_project", "view_driver_state"):
            line = self._observe_perception(name, kwargs, payload, ph)
            self._close_events(name, ph)
            return line

        template = TEMPLATES.get(name)
        if template is None:
            # finish + neutral tools: no verdict of their own, but finish
            # closes open latency events (same accounting as B1).
            self._close_events(name, ph)
            return None

        # A new action while a verification is pending: the planner moved on
        # without producing the requested evidence — record and clear. Grip
        # maintenance (closing set_gripper) is transparent: it answers no
        # question but also does not advance the plan past one.
        if self._pending is not None and not _is_grip_maintenance(name, kwargs):
            self._resolve_pending_overtaken(ph, by=name)

        pre = self._pre_state_summary()
        line = self._judge_action(name, kwargs, payload, pre, ph, is_error)
        self._last_action_step = self._step
        self._update_cache_from_action(name, kwargs, payload)
        self._close_events(name, ph)
        return line

    def _update_cache_from_action(
        self,
        name: str,
        kwargs: dict[str, Any],
        payload: dict[str, Any] | None,
    ) -> None:
        """Fold an action result's proprioception into the world cache."""
        if not isinstance(payload, dict):
            return
        f = _fields_from_payload(payload)
        if name in ("move_to", "move_pose"):
            eef = _xyz(payload.get("final_eef_pos"))
            if eef is not None:
                self._eef = eef
                self._eef_step = self._step
        grip = f.get("final_gripper_opening")
        if grip is not None:
            try:
                self._grip = float(grip)
                self._grip_step = self._step
            except (TypeError, ValueError):
                pass

    # ---------------------------------------------------------- perception

    def _observe_perception(
        self,
        name: str,
        kwargs: dict[str, Any],
        payload: dict[str, Any] | None,
        ph: str,
    ) -> str | None:
        if payload is None:
            return None
        if name in ("segment", "back_project"):
            xyz = _xyz(payload.get("world_xyz"))
            found = payload.get("found", True)
            label = None
            if name == "segment":
                p = str(kwargs.get("prompt") or "").strip()
                if p:
                    label = p
            if label is None:
                label = f"{name}@{self._step}"
            if xyz is not None and found is not False:
                prev = self._obj.get(label)
                if (
                    prev
                    and _dist(prev["xyz"], xyz) is not None
                    and _dist(prev["xyz"], xyz) < 0.01
                ):
                    self.n_redundant_obs += 1
                self._obj[label] = {"xyz": xyz, "step": self._step}
            elif self._pending and self._pending.get("wants") == "object_position":
                # The directed observation ran but produced no position —
                # a stall round only when it targeted the pending's object.
                if _labels_related(self._pending.get("label"), label):
                    return self._resolve_pending(
                        ph, obs_xyz=None, obs_label=label
                    )
            return self._maybe_resolve(ph)
        # view_driver_state: fresh proprioception for the cache
        st = payload.get("state") or {}
        eef = _xyz(st.get("robot0_eef_pos"))
        if eef is not None:
            self._eef = eef
            self._eef_step = self._step
        gq = st.get("robot0_gripper_qpos")
        if isinstance(gq, (list, tuple)) and len(gq) >= 2:
            try:
                self._grip = float(abs(gq[0]) + abs(gq[1]))
                self._grip_step = self._step
            except (TypeError, ValueError):
                pass
        return self._maybe_resolve(ph)

    def _maybe_resolve(self, ph: str) -> str | None:
        if not self._pending:
            return None
        if self._pending.get("wants") == "object_position":
            label, rec = self._pending_target_record()
            if rec is not None:
                self._pending["label"] = label  # adopt on first sighting
                return self._resolve_pending(ph, obs_xyz=rec["xyz"], obs_label=label)
            return None
        # wants == driver_state (set_gripper actuator check)
        if self._grip is not None and self._grip_step > self._pending["open_step"]:
            return self._resolve_pending(ph, obs_xyz=None, obs_label=None)
        return None

    def _pending_target_record(
        self,
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Fresh (post-action) sighting of the object an open verification
        asks about; ``(None, None)`` when nothing usable has arrived.

        A semantically labeled pending resolves on its own label under any
        wording (token match); an *unrelated* observation does not answer it.
        A pending with no semantic label accepts the freshest sighting — the
        directive told the planner which object to look at.
        """
        p = self._pending
        if p is None:
            return None, None
        fresh = {
            l: r for l, r in self._obj.items() if r["step"] > p["open_step"]
        }
        label = p.get("label")
        if label and "@" not in label:
            if label in fresh:
                return label, fresh[label]
            m = _match_label(label, fresh)
            if m is not None:
                return m, fresh[m]
            return None, None
        if fresh:
            lbl = max(fresh, key=lambda l: fresh[l]["step"])
            return lbl, fresh[lbl]
        return None, None

    # ------------------------------------------------------------ actions

    def _judge_action(
        self,
        name: str,
        kwargs: dict[str, Any],
        payload: dict[str, Any] | None,
        pre: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        template = TEMPLATES[name]
        ev = self._base_event(name, template, pre)
        f = _fields_from_payload(payload or {})

        # set_gripper only counts as a PLACE attempt when opening
        if payload is None and not is_error:
            return None  # unparseable result — no state-transition question
        if name == "set_gripper":
            try:
                g = float(kwargs.get("gripper", -1.0))
            except (TypeError, ValueError):
                g = -1.0
            if g > 0:
                return None  # closing actuation: no state-transition question

        if template == "GRASP":
            return self._judge_grasp(name, kwargs, ev, f, ph, is_error)
        if template == "PLACE":
            return self._judge_place(name, ev, f, ph, is_error)
        if template == "TRANSPORT":
            return self._judge_transport(name, kwargs, ev, f, ph, is_error)
        if template == "CONTACT":
            return self._judge_contact(name, ev, f, ph, is_error)
        return self._judge_rotate(name, ev, f, ph, is_error, payload)

    def _judge_grasp(
        self,
        name: str,
        kwargs: dict[str, Any],
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        mg = f.get("min_gripper_opening")
        fg = f.get("final_gripper_opening")
        pl = f.get("peak_lift_m")
        succ = f.get("success")
        term = f.get("libero_terminated")
        ev["b1_style_would_match"] = bool(
            succ is True or (mg is not None and mg < GRIP_TIGHT)
        )
        n_checks = checks = 0

        def ratio() -> float | None:
            return round(checks / n_checks, 2) if n_checks else None

        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the attempt did not execute", "retry once with an adjusted "
                "approach, then report honestly via finish"
            )
        if term is True:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change="official termination set during the attempt",
                evidence_for_success=["libero_terminated=true"],
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name, "the task condition is met", "call finish now."
            )
        if mg is None and succ is None:
            return None  # nothing machine-checkable — no judgment

        if mg is not None:
            n_checks += 1
            if mg > NEVER_CLOSED_TOL:
                checks += 1
                ev["evidence_for_failure"].append(
                    f"gripper never closed (min opening {float(mg):.3f})"
                )
        if pl is not None:
            n_checks += 1
            if pl >= LIFT_MIN:
                checks += 1
                ev["evidence_for_success"].append(
                    f"eef ascended {float(pl):.2f} m after the descent"
                )
        if fg is not None:
            n_checks += 1
            if fg <= NEVER_CLOSED_TOL:
                checks += 1
                ev["evidence_for_success"].append(
                    f"gripper still closed at return ({float(fg):.3f})"
                )

        if ev["evidence_for_failure"]:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="no closure on the target",
                confidence=ratio(),
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                "the gripper did not close on the target",
                "adjust the approach (pose/clearance) and retry once; an "
                "unchanged retry is discouraged",
            )

        # GRASP confirmation ALWAYS requires object-level state evidence.
        # Calibration (2026-09-15, 160 armB picks, dev t0/t7/t9 + heldout
        # t1/t4/t8): min_gripper_opening distributions of true and false
        # holds fully overlap (false positives with success=true span
        # 0.001-0.019; successful episodes' picks reach 0.0010) — no
        # proprioceptive band separates them. Proprioception only grades
        # the hypothesis and can disprove (stayed open).
        # Object identity for the directed observation: the pick prompt's
        # content words against cached perception labels (planners describe
        # the same object differently across wordings), else the most recent
        # real label. Never a point-observation fallback label.
        label = (
            _match_label(str(kwargs.get("prompt") or ""), self._obj)
            or self._last_label(real_only=True)
        )
        pre_pos = self._obj.get(label, {}).get("xyz") if label else None
        if mg is not None and mg <= FULLY_CLOSED_EPS:
            ev["evidence_for_failure"].append(
                "gripper pinned fully shut — closure width consistent with "
                "grabbing nothing (thin objects excepted)"
            )
        elif mg is not None:
            ev["evidence_for_success"].append(
                f"closure stopped at {float(mg):.3f} m — consistent with "
                "something between the fingers"
            )
        ev["missing_evidence"].append(
            "object displacement: has the target left its original support "
            "and does it now move with the gripper?"
        )
        directive = self._segment_directive(label)
        directive += (
            " — if its position left the earlier spot and sits near the "
            "gripper, the hold is real; if it stayed put, the grasp did not "
            "take. Closure width and lift cannot distinguish a real hold "
            "from fingers closing on nothing, and firming the grip or moving "
            "on does not answer this."
        )
        ev.update(
            verdict="UNCERTAIN",
            next_decision="OBSERVE",
            observed_change="proprioception alone cannot confirm the object "
            "is held",
            confidence=ratio(),
        )
        self._open_pending(
            name, "GRASP", label=label, pre_pos=pre_pos, wants="object_position", ph=ph
        )
        self.n_uncertain += 1
        self.n_observe_directives += 1
        self._emit(ev)
        return self._observe_line(
            name,
            "object displacement unknown",
            directive,
        )

    def _judge_place(
        self,
        name: str,
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        pg = f.get("peak_gripper_opening")
        term = f.get("libero_terminated")
        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the placement did not execute",
                "retry once, then report honestly via finish",
            )
        if term is True:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change="official termination set",
                evidence_for_success=["libero_terminated=true"],
            )
            self._held = None
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name, "the task condition is met", "call finish now."
            )
        if pg is not None and pg <= GRIP_OPEN:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change=f"gripper stayed shut (peak opening "
                f"{float(pg):.3f})",
                evidence_for_failure=[
                    "gripper did not open — object was not released"
                ],
                confidence=1.0,
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                "the gripper did not open",
                "re-attempt with set_gripper(gripper=-1.0); escalate the "
                "placement method if it repeats",
            )
        # Released at the actuator level; the object-level question (at rest
        # at the intended location, clear of the gripper) needs observation.
        label = self._held or self._last_label(real_only=True)
        wants = "object_position"
        if name == "set_gripper" and pg is None:
            wants = "driver_state"  # actuator confirmation first
        directive = self._segment_directive(label)
        directive += (
            " — confirm it now rests at the intended location and is clear "
            "of the gripper."
        )
        ev["missing_evidence"].append(
            "final relation: object at rest at the intended place location"
        )
        if pg is not None:
            ev["evidence_for_success"].append(
                f"gripper opened (peak {float(pg):.3f}) — object no longer "
                "attached at the actuator level"
            )
        ev.update(
            verdict="UNCERTAIN",
            next_decision="OBSERVE",
            observed_change="release actuated; object-level outcome unverified",
            confidence=0.5 if pg is not None else None,
        )
        self._open_pending(
            name, "PLACE", label=label, pre_pos=None, wants=wants, ph=ph
        )
        self.n_uncertain += 1
        self.n_observe_directives += 1
        self._emit(ev)
        return self._observe_line(
            name, "final object position unknown", directive
        )

    def _judge_transport(
        self,
        name: str,
        kwargs: dict[str, Any],
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        d = f.get("final_dist_m")
        target = _xyz(kwargs.get("xyz") or kwargs.get("target"))
        if target is not None:
            self._target = target
            self._target_step = self._step
        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the move did not execute",
                "retry once, then report honestly via finish",
            )
        if d is None:
            return None
        if float(d) <= MOVE_TOL:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change=f"arrived ({float(d):.3f} m residual)",
                evidence_for_success=[f"final_dist_m={float(d):.3f} <= "
                                      f"{MOVE_TOL}"],
                confidence=1.0,
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name,
                f"arrival within {float(d):.3f} m of the commanded target",
                "proceed with the next planned step at this location.",
            )
        ev.update(
            verdict="CONFIRMED_FAILURE",
            next_decision="RECOVER",
            observed_change=f"stopped short ({float(d):.3f} m residual)",
            evidence_for_failure=[
                f"final_dist_m={float(d):.3f} > {MOVE_TOL}"
            ],
            confidence=1.0,
        )
        self._register_failure(ev, ph)
        self._emit(ev)
        return self._recover_line(
            name,
            f"the servo did not converge ({float(d):.3f} m residual)",
            "re-localize the target once (one back_project), then make one "
            "deliberate move straight to it",
        )

    def _judge_contact(
        self,
        name: str,
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        succ = f.get("success")
        term = f.get("libero_terminated")
        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the skill did not execute",
                "retry once, then report honestly via finish",
            )
        if term is True or succ is True:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change="official termination set",
                evidence_for_success=["success mirrors official termination"],
                confidence=1.0,
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name, "the task condition is met", "call finish now."
            )
        if succ is False:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="termination not reached after the skill",
                evidence_for_failure=[
                    "success=false (mirrors official termination)"
                ],
                confidence=1.0,
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                "the contact skill did not reach the task condition",
                "make ONE corrective attempt, then report honestly via "
                "finish",
            )
        return None

    def _judge_rotate(
        self,
        name: str,
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
        payload: dict[str, Any] | None = None,
    ) -> str | None:
        fe = (payload or {}).get("final_err", f.get("final_err"))
        if fe is None:
            return None
        err = abs(float(fe))
        if is_error or err > 0.08:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change=f"orientation error {err:.3f} rad remains",
                evidence_for_failure=[f"final_err={float(fe):.3f}"],
                confidence=1.0,
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                f"the wrist is {err:.3f} rad off the commanded orientation",
                "re-issue once with a corrected target, then move on",
            )
        if err <= 0.05:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change=f"orientation reached ({err:.3f} rad error)",
                evidence_for_success=[f"final_err={float(fe):.3f}"],
                confidence=1.0,
                quiet=True,
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return None  # quiet: rotation success needs no behavior change
        ev.update(
            verdict="UNCERTAIN",
            next_decision="PROCEED",
            observed_change=f"orientation error {err:.3f} rad — marginal",
            missing_evidence=["whether the residual matters for the next step"],
            confidence=0.5,
        )
        self.n_uncertain += 1
        self._emit(ev)
        return None

    # ------------------------------------------------------------ pending

    def _open_pending(
        self,
        tool: str,
        template: str,
        *,
        label: str | None,
        pre_pos: tuple[float, float, float] | None,
        wants: str,
        ph: str,
    ) -> None:
        self._pending = {
            "tool": tool,
            "template": template,
            "label": label,
            "pre_pos": pre_pos,
            "wants": wants,
            "open_step": self._step,
            "open_phase": ph,
            "rounds": 0,
            "stalled_hinted": False,
        }

    def _resolve_pending_overtaken(self, ph: str, by: str) -> None:
        p = self._pending
        if p is None:
            return
        self.uncertain_resolutions["overtaken"] += 1
        ev = self._base_event(by, p["template"], self._pre_state_summary())
        ev.update(
            verdict="UNCERTAIN",
            next_decision="PROCEED",
            observed_change=f"planner ran {by} before the requested evidence "
            "arrived",
            missing_evidence=["the directed observation never ran"],
            pending_of=p["tool"],
            rounds=p["rounds"],
        )
        self.n_uncertain += 0  # already counted when opened
        self._emit(ev)
        self._pending = None

    def _resolve_pending(
        self,
        ph: str,
        *,
        obs_xyz: tuple[float, float, float] | None,
        obs_label: str | None,
    ) -> str | None:
        p = self._pending
        if p is None:
            return None
        p["rounds"] += 1
        self.n_observe_obeyed += 1  # a directed observation actually arrived
        rounds = p["rounds"]
        ev = self._base_event(p["tool"], p["template"], self._pre_state_summary())
        ev["pending_of"] = p["tool"]
        ev["rounds"] = rounds
        ev["verification_source"] = "directed_observation"

        # --- set_gripper actuator check (driver_state round) ---
        if p["wants"] == "driver_state":
            if self._grip is not None and self._grip > GRIP_OPEN:
                label = p.get("label")
                obj = self._obj.get(label or "", {})
                d_t = _dist(obj.get("xyz"), self._target) if obj else None
                if d_t is not None and d_t <= PLACE_TOL:
                    return self._pending_success(
                        ev, ph,
                        why=f"gripper open ({self._grip:.3f}) and object "
                        f"within {d_t:.2f} m of the intended location",
                    )
                ev["missing_evidence"].append("object position after opening")
                ev.update(
                    verdict="CONFIRMED_SUCCESS",
                    next_decision="COMMIT",
                    observed_change=f"gripper confirmed open "
                    f"({self._grip:.3f})",
                    evidence_for_success=[
                        f"robot0_gripper opening {self._grip:.3f} > "
                        f"{GRIP_OPEN}"
                    ],
                    confidence=0.6,
                )
                self._held = None
                self.uncertain_resolutions["resolved_success"] += 1
                self._register_success(ev, ph)
                self._emit(ev)
                self._pending = None
                return None  # quiet: actuator-level confirmation
            # actuator not confirmed either — fall through to object rounds
            p["wants"] = "object_position"

        # --- object_position rounds (GRASP / PLACE) ---
        if obs_xyz is None:
            ev["missing_evidence"].append(
                "observation produced no usable object position"
            )
            return self._pending_stall(ev, ph, rounds)

        label = obs_label or p.get("label")
        eef = self._eef if self._eef_step > p["open_step"] else None
        d_e = _dist(obs_xyz, eef)
        d_pre = _dist(obs_xyz, p.get("pre_pos"))

        if p["template"] == "GRASP":
            if d_pre is not None and d_pre >= OBJ_MOVE_TOL and (
                d_e is None or d_e <= HOLD_RADIUS
            ):
                return self._pending_success(
                    ev, ph,
                    why=f"object moved {d_pre:.2f} m off its original spot"
                    + (f" and rides {d_e:.2f} m from the gripper" if d_e else ""),
                    held=label,
                )
            if d_pre is not None and d_pre <= OBJ_STAY_TOL and (
                d_e is None or d_e > NEAR_EEF
            ):
                ev["b1_style_would_match"] = None  # set by the opener event
                return self._pending_failure(
                    ev, ph,
                    why=f"object stayed at its original support position "
                    f"(moved {d_pre:.2f} m) while the gripper moved away",
                )
            if d_pre is None and d_e is not None and d_e <= NEAR_EEF:
                return self._pending_success(
                    ev, ph,
                    why=f"object now sits {d_e:.2f} m from the end effector "
                    "(no earlier position on record, but it tracks the gripper)",
                    held=label,
                )
            ev["missing_evidence"].append(
                "object displacement does not clearly separate held vs left"
            )
            if d_pre is not None:
                ev["observed_change"] = (
                    f"object moved {d_pre:.2f} m from its pre-pick spot"
                    + (f", {d_e:.2f} m from the eef" if d_e else "")
                )
            return self._pending_stall(ev, ph, rounds)

        # PLACE
        d_t = _dist(obs_xyz, self._target) if self._target else None
        if d_t is not None and d_t <= PLACE_TOL:
            return self._pending_success(
                ev, ph,
                why=f"object rests {d_t:.2f} m from the intended place "
                "location",
                held=None,
            )
        if d_t is not None and d_t > PLACE_FAR and (d_e is None or d_e > NEAR_EEF):
            return self._pending_failure(
                ev, ph,
                why=f"object ended up {d_t:.2f} m from the intended location "
                "and clear of the gripper — it was dropped or displaced",
            )
        ev["missing_evidence"].append(
            "object rest position vs the intended location"
        )
        ev["observed_change"] = (
            f"object at {d_t:.2f} m from the transport target"
            if d_t is not None
            else "object located but no transport target on record"
        ) + (f", {d_e:.2f} m from the eef" if d_e else "")
        return self._pending_stall(ev, ph, rounds)

    def _pending_success(
        self, ev: dict[str, Any], ph: str, *, why: str, held: str | None
    ) -> str:
        p = self._pending or {}
        ev.update(
            verdict="CONFIRMED_SUCCESS",
            next_decision="COMMIT",
            observed_change=why,
            evidence_for_success=[why],
            confidence=0.9,
        )
        self._held = held
        self.uncertain_resolutions["resolved_success"] += 1
        self._register_success(ev, ph)
        self._emit(ev)
        self._pending = None
        tool = p.get("tool", "?")
        if p.get("template") == "GRASP":
            return self._commit_line(
                tool, why, "transport the held object; do not re-grasp."
            )
        return self._commit_line(
            tool, why, "proceed with the plan (finish if this was the goal)."
        )

    def _pending_failure(
        self, ev: dict[str, Any], ph: str, *, why: str
    ) -> str:
        p = self._pending or {}
        ev.update(
            verdict="CONFIRMED_FAILURE",
            next_decision="RECOVER",
            observed_change=why,
            evidence_for_failure=[why],
            confidence=0.9,
        )
        # The B1-style check may have matched on the original action —
        # that pairing is exactly the false-positive class B2 exists to catch.
        opener = next(
            (e for e in reversed(self.events)
             if e.get("action") == p.get("tool")
             and e.get("pending_of") is None
             and e.get("verdict") == "UNCERTAIN"),
            None,
        )
        if opener is not None and opener.get("b1_style_would_match"):
            self.false_positive_caught += 1
            ev["b1_style_would_match"] = True
        if p.get("template") == "GRASP":
            self._held = None
        self.uncertain_resolutions["resolved_failure"] += 1
        self._register_failure(ev, ph)
        self._emit(ev)
        self._pending = None
        tool = p.get("tool", "?")
        if p.get("template") == "GRASP":
            return self._recover_line(
                tool, why,
                "re-approach with a changed pose and retry once; report "
                "honestly via finish if it repeats",
            )
        return self._recover_line(
            tool, why, "re-localize and re-place once, then report honestly "
            "via finish"
        )

    def _pending_stall(
        self, ev: dict[str, Any], ph: str, rounds: int
    ) -> str | None:
        p = self._pending or {}
        if rounds < MAX_OBSERVE_ROUNDS:
            ev.update(
                verdict="UNCERTAIN",
                next_decision="OBSERVE",
                observed_change=ev.get("observed_change") or "inconclusive",
            )
            self.n_observe_directives += 1
            self._emit(ev)
            label = p.get("label")
            directive = (
                f"one more check: segment or back_project the object"
                + (f" ('{label}')" if label else "")
                + " from the current view — decide from where it sits now"
            )
            return self._observe_line(
                p.get("tool", "?"), "still inconclusive", directive
            )
        ev.update(
            verdict="UNCERTAIN",
            next_decision="REASON",
            observed_change=ev.get("observed_change") or "inconclusive",
        )
        self.uncertain_resolutions["resolved_reason"] += 1
        self.n_reason_escalations += 1
        self._emit(ev)
        tool = p.get("tool", "?")
        self._pending = None
        return self._reason_line(tool, rounds)

    # ------------------------------------------------------------ latency

    def _register_success(self, ev: dict[str, Any], ph: str) -> None:
        self.n_success += 1
        self._open_commit.append(
            {
                "tool": ev["action"],
                "step": self._step,
                "phase": ph,
                "template": ev.get("rule_template"),
            }
        )

    def _register_failure(self, ev: dict[str, Any], ph: str) -> None:
        self.n_failure += 1
        self._open_recovery.append(
            {
                "tool": ev["action"],
                "step": self._step,
                "phase": ph,
                "template": ev.get("rule_template"),
            }
        )

    def _close_events(self, name: str, phase: str) -> None:
        from rpent.memory.structured import ACTION_TOOLS

        still: list[dict[str, Any]] = []
        for e in self._open_recovery:
            if name == "finish":
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "finish"
                self.recovery_events.append(e)
                continue
            if name in ACTION_TOOLS and name != e["tool"]:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "switch"
                self.recovery_events.append(e)
                continue
            if name in ACTION_TOOLS and name == e["tool"]:
                e["closed_by"] = "same_tool_repeated"
            still.append(e)
        self._open_recovery = still

        still = []
        for e in self._open_commit:
            if name == "finish":
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "finish"
                self.commit_events.append(e)
                continue
            cur = PHASE_ORDER.get(phase, -1)
            opened = PHASE_ORDER.get(e.get("phase", ""), -1)
            if cur > opened:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "phase_advanced"
                self.commit_events.append(e)
                continue
            still.append(e)
        self._open_commit = still

    # ------------------------------------------------------------ boundary

    def turn_boundary_hint(self) -> str | None:
        """Escalate a stalled verification: pending for many tool results
        with no action executed and no directed observation arriving."""
        p = self._pending
        if not p or p.get("stalled_hinted"):
            return None
        # no action executed since the pending opened (the opening action
        # itself has _last_action_step == open_step) and no observation is
        # arriving -> escalate once.
        stalled = (
            self._last_action_step <= p["open_step"]
            and self._step - p["open_step"] >= STALL_STEPS
        )
        if not stalled:
            return None
        p["stalled_hinted"] = True
        self.n_reason_escalations += 1
        self.uncertain_resolutions["resolved_reason"] += 1
        self._pending = None
        return self._reason_line(p["tool"], p["rounds"])

    # ------------------------------------------------------------ snapshot

    def snapshot(self, *, success: bool) -> dict[str, Any]:
        """Per-episode B2 metrics (merged into structured_metrics.json)."""
        if self._pending is not None:
            self.uncertain_resolutions["unresolved"] += 1
            self._pending = None
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

        def _mean(xs: list[int | None]) -> float | None:
            ys = [x for x in xs if x is not None]
            return round(sum(ys) / len(ys), 2) if ys else None

        return {
            "b2": True,
            "task": self._task,
            "n_confirmed_success": self.n_success,
            "n_confirmed_failure": self.n_failure,
            "n_uncertain": self.n_uncertain,
            "n_observe_directives": self.n_observe_directives,
            "n_observe_obeyed": self.n_observe_obeyed,
            "n_reason_escalations": self.n_reason_escalations,
            "n_redundant_observations": self.n_redundant_obs,
            "false_positive_caught": self.false_positive_caught,
            "uncertain_resolutions": dict(self.uncertain_resolutions),
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
            "events": self.events,
            "success": success,
        }


# ------------------------------------------------------------------ output

def _output_dir() -> Path | None:
    try:
        from rpent.utils.logging import get_output_dir

        out = get_output_dir()
        return Path(out) if out else None
    except Exception:  # noqa: BLE001 - optional
        return None


def _episode_id() -> str:
    out = _output_dir()
    return out.name if out is not None else ""
