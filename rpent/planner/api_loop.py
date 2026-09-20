"""Provider-independent tool-use agent loop built on pydantic-ai.

The loop wraps the agent's :class:`~rpent.tools.toolkit.Toolkit` as
pydantic-ai function tools and drives :class:`pydantic_ai.Agent` runs,
streaming each turn so progress is logged in real time. Task completion is
signalled by the env-provided ``finish`` tool, whose result carries ``_finish``.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import dataclasses
import hashlib
import json
import os
import queue
import re
import traceback
from collections import deque
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, BinaryContent, ModelSettings, Tool, ToolReturn
from pydantic_ai.capabilities import ProcessHistory, Thinking
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage, UsageLimits

from rpent.cli.tui import QUIT_TOKENS
from rpent.dashboard.events import (
    DashboardEventSink,
    TranscriptEvent,
    UsageEvent,
)
from rpent.dashboard.interaction import DashboardInteractionPort, DashboardMessage
from rpent.dashboard.planner_control import DashboardPlannerControl
from rpent.planner.base import PlannerResult
from rpent.tools.toolkit import Toolkit
from rpent.utils.config import get_repo_root
from rpent.utils.logging import get_logger, get_output_dir

logger = get_logger("api_loop")

#: Console-log truncation limits (characters).
_TEXT_LOG_LIMIT = 500
_ARGS_LOG_LIMIT = 250
_TOOL_LOG_LIMIT = 350
#: Cap on cumulative decoded image bytes kept in the resent request history.
_MAX_HISTORY_IMAGE_BYTES = 4 * 1024 * 1024

#: Always retain at least this many of the most recent images, even if a single
#: frame exceeds the byte budget, so the model never loses its current view.
_MIN_RECENT_IMAGES = 2


def _merge_into_tail(history: list[ModelMessage], text: str) -> list[ModelMessage]:
    """Append *text* to the trailing model request so it survives the restart.

    pydantic-ai 2.25.0 restarts a run with ``user_prompt=None`` by popping the
    trailing ``ModelRequest`` and reusing its parts as the next message
    (``_agent_graph.py`` ``is_resuming_without_prompt``). ``run.enqueue`` is
    lost the moment the run closes, so a pending structured block / fast summary
    must ride inside the tail request instead. Pure + unit-tested.
    """
    if not history:
        return [ModelRequest(parts=[UserPromptPart(content=text)])]
    tail = history[-1]
    if isinstance(tail, ModelRequest):
        # ModelRequest is a @dataclass (no pydantic model_copy); replace() copies
        # the dataclass with the summary appended to the tail request's parts.
        merged = dataclasses.replace(
            tail, parts=list(tail.parts) + [UserPromptPart(content=text)]
        )
        return history[:-1] + [merged]
    # Defensive: no trailing request (e.g. a bare end response). Start a fresh
    # request so the injected text is still delivered on restart.
    return history + [ModelRequest(parts=[UserPromptPart(content=text)])]

#: Perception tools the Progress Gate watches. The gate is an opt-in experiment
#: selected by RPENT_PERCEPTION_MODE:
#:   none          (default) — baseline Rule 2e, no blocking
#:   hardcap       — block after RPENT_PERCEPTION_STREAK consecutive perception
#:                   calls regardless of information change (a pure count cap)
#:   progress_gate — block when consecutive perception calls return essentially
#:                   unchanged information (world_xyz within RPENT_PERCEPTION_TOL_M,
#:                   same camera/step), nudging the agent to act or re-observe.
#: (Legacy RPENT_BLOCK_REPEATED_PERCEPTION=1 maps to progress_gate.)
_PERCEPTION_GUARD_TOOLS = {"segment", "back_project", "view_driver_state", "read_image"}

_PERCEPTION_BLOCK_MESSAGE = (
    "Perception guard ({mode}): the last {n} consecutive perception calls returned "
    "essentially unchanged information. Continuing to perceive cannot add information. "
    "Choose ONE of the following now:\n"
    "1) Execute a primitive action (move_to / move_pose / pi0_pick / pi0_doubled "
    "/ release / set_gripper / rotate_wrist / rotate_pitch) to advance the task;\n"
    "2) Get genuinely NEW information by acting first (the scene changes), or by "
    "querying a different step / camera / pixel / prompt;\n"
    "3) Call finish() if the task is done or hopeless."
)

_XYZ_RE = re.compile(
    r'"(?:world_xyz|center_xyz|median_xyz)":\s*\[\s*'
    r"(-?[0-9.]+)[,\s]*(-?[0-9.]+)[,\s]*(-?[0-9.]+)"
)


def _perception_query_sig(name: str, kwargs: dict[str, Any]) -> tuple | None:
    """Stable fingerprint of *what the perception call is asking for*.

    Same fingerprint => same information returned (these tools are
    deterministic in their args), so a run of identical fingerprints is
    repeated perception. ``None`` for non-perception tools.
    """
    k = kwargs or {}
    if name == "read_image":
        return ("read_image", str(k.get("path")))
    if name == "view_driver_state":
        return ("view_driver_state", k.get("step"))
    if name == "back_project":
        return (
            "back_project",
            k.get("camera"),
            k.get("resolution"),
            k.get("step"),
            k.get("row"),
            k.get("col"),
            tuple(k.get("row_range")) if k.get("row_range") is not None else None,
            tuple(k.get("col_range")) if k.get("col_range") is not None else None,
        )
    if name == "segment":
        return (
            "segment",
            k.get("camera"),
            k.get("step"),
            ("p", tuple(k.get("point"))) if k.get("point") is not None else ("t", k.get("prompt")),
        )
    return None


def _perception_info(name: str, kwargs: dict[str, Any], text: str) -> tuple | None:
    """Semantic info a perception call returned, for change detection."""
    k = kwargs or {}
    if name in ("back_project", "segment"):
        m = _XYZ_RE.search(text or "")
        xyz = tuple(round(float(v), 4) for v in m.groups()) if m else None
        return ("xyz", k.get("camera"), k.get("step"), xyz)
    if name == "view_driver_state":
        return ("view", k.get("step"))
    if name == "read_image":
        return ("img", str(k.get("path")))
    return None


def _info_unchanged(a: tuple, b: tuple, tol: float) -> bool:
    """True when perception info b carries no new information vs a."""
    if a[0] != b[0]:
        return False
    if a[0] == "xyz":
        if a[1] != b[1] or a[2] != b[2]:  # camera or step differ -> new info
            return False
        if a[3] is None or b[3] is None:
            return False
        return all(abs(x - y) <= tol for x, y in zip(a[3], b[3]))
    return a[1] == b[1]


class _PerceptionGuard:
    """Blocks perception that stops adding information (or a hard count cap).

    ``hardcap`` counts every consecutive perception call and blocks past the
    threshold. ``progress_gate`` counts only consecutive calls whose returned
    info is essentially unchanged (same camera/step, world_xyz within tol) and
    blocks when that no-progress streak passes the threshold. Any non-perception
    call (an action, finish, ...) resets the streak.
    """

    def __init__(self, mode: str, streak_limit: int, tol_m: float = 0.01) -> None:
        self._mode = mode
        self._streak_limit = max(1, int(streak_limit))
        self._tol = float(tol_m)
        self._last_sig: tuple | None = None
        self._last_info: tuple | None = None
        self._streak = 0

    def check_before(self, name: str, kwargs: dict[str, Any]) -> str | None:
        """Return a block message if the call is known-blocked (skip execution)."""
        sig = _perception_query_sig(name, kwargs)
        if sig is None:
            return None  # action -> reset happens in observe_after
        if self._mode == "hardcap":
            if self._streak >= self._streak_limit:
                return self._block(name)
            return None
        # progress_gate: identical query already past threshold -> deterministic repeat
        if sig == self._last_sig and self._streak >= self._streak_limit:
            return self._block(name)
        return None

    def observe_after(self, name: str, kwargs: dict[str, Any], text: str) -> str | None:
        """Return a block message after a tool executed, or None. Resets on action."""
        sig = _perception_query_sig(name, kwargs)
        if sig is None:
            self._last_sig = None
            self._last_info = None
            self._streak = 0
            return None
        if self._mode == "hardcap":
            self._streak += 1
        else:  # progress_gate
            self._last_sig = sig
            info = _perception_info(name, kwargs, text)
            if info is None:
                self._last_info = None
                self._streak = 0
                return None
            unchanged = self._last_info is not None and _info_unchanged(
                self._last_info, info, self._tol
            )
            self._last_info = info
            self._streak = self._streak + 1 if unchanged else 1
        if self._streak > self._streak_limit:
            return self._block(name)
        return None

    def _block(self, name: str) -> str:
        return _PERCEPTION_BLOCK_MESSAGE.format(
            mode=self._mode, name=name, n=self._streak
        )

    @classmethod
    def make(cls) -> "_PerceptionGuard | None":
        """Instantiate from env; None for the baseline (no gate)."""
        mode = os.environ.get("RPENT_PERCEPTION_MODE", "none")
        if mode == "none" and os.environ.get("RPENT_BLOCK_REPEATED_PERCEPTION") == "1":
            mode = "progress_gate"  # legacy flag
        if mode == "none":
            return None
        if mode not in ("hardcap", "progress_gate"):
            logger.warning("unknown RPENT_PERCEPTION_MODE=%r; disabling guard", mode)
            return None
        limit = int(os.environ.get("RPENT_PERCEPTION_STREAK", "3") or "3")
        tol = float(os.environ.get("RPENT_PERCEPTION_TOL_M", "0.01") or "0.01")
        logger.info(
            "perception guard enabled: mode=%s streak_limit=%s tol_m=%s",
            mode, limit, tol,
        )
        return cls(mode, limit, tol)


class ApiAgentLoop:
    """Planner that runs the tool-calling loop via a pydantic-ai ``Agent``."""

    def __init__(
        self,
        model: Model,
        max_tokens: int = 8192,
        no_images: bool = False,
        *,
        dashboard_events: DashboardEventSink,
        timeout_s: int | None = None,
    ):
        """Store the pydantic-ai model and the output-token cap."""
        self._model = model
        self._max_tokens = max_tokens
        self._dashboard_events = dashboard_events
        self._no_images = no_images
        self._timeout_s = timeout_s

    def solve(
        self,
        *,
        system_prompt: str,
        user_message: str,
        toolkit: Toolkit,
        max_turns: int,
        input_queue: queue.Queue[str | None] | None = None,
        dashboard_interaction: DashboardInteractionPort | None = None,
    ) -> PlannerResult:
        """Run the tool-calling loop until finish, normal stop, or budget."""
        if input_queue is not None and dashboard_interaction is not None:
            raise ValueError(
                "input_queue and dashboard_interaction cannot be used together"
            )
        if dashboard_interaction is not None:
            return asyncio.run(
                self._solve_dashboard(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    toolkit=toolkit,
                    max_turns=max_turns,
                    interaction=dashboard_interaction,
                )
            )
        solve = self._solve(
            system_prompt=system_prompt,
            user_message=user_message,
            toolkit=toolkit,
            max_turns=max_turns,
            input_queue=input_queue,
        )
        if input_queue is not None:
            return asyncio.run(solve)
        try:
            return asyncio.run(asyncio.wait_for(solve, timeout=self._timeout_s))
        except asyncio.TimeoutError:
            toolkit.cancel_active_and_wait()
            return PlannerResult(
                finish_result=None,
                messages=[{"role": "user", "content": user_message}],
                stats={},
                error=f"API planner timed out after {self._timeout_s}s",
            )

    async def _solve(
        self,
        *,
        system_prompt: str,
        user_message: str,
        toolkit: Toolkit,
        max_turns: int,
        input_queue: queue.Queue[str | None] | None = None,
    ) -> PlannerResult:
        tracker = _new_phase_tracker(max_turns=max_turns)
        # OVP-M (arm B) — requires the SM1 tracker for phase context.
        outcome_validator = _new_outcome_validator(tracker)
        # B2 (arm B2) — evidence-sufficient state-transition verification.
        # Runs alongside the tracker only; arms A/B never set its gate.
        b2_verifier = _new_b2_verifier(tracker)
        # Stage B1 (arms memB2/memB3) — decision-point long-term memory
        # recall. Soft context injection only; gated by RPENT_MEMORY_TRIGGER.
        memory_recall = _new_memory_recall(tracker)
        # Arm C — event-triggered reasoning: COMMIT turns run on a constrained
        # agent (trimmed instructions, action tools only, pruned history);
        # every other turn runs the full REASON agent. Requires arm B.
        reason_mode = (
            outcome_validator is not None
            and os.environ.get("RPENT_REASON_MODE") == "1"
        )
        commit_agent = (
            self._build_commit_agent(toolkit, outcome_validator=outcome_validator)
            if reason_mode
            else None
        )
        commit_mode_steps = 0
        reason_mode_steps = 0
        mode_tokens = {"commit": [0, 0], "reason": [0, 0]}  # [in, out]
        logger.info(
            "[prompt] len=%d sha1=%s sm=%s ovpm=%s reason=%s",
            len(system_prompt or ""),
            hashlib.sha1((system_prompt or "").encode()).hexdigest()[:12],
            os.environ.get("RPENT_STRUCTURED_MEMORY") == "1",
            outcome_validator is not None,
            reason_mode,
        )
        agent = self._build_agent(
            system_prompt, toolkit, outcome_validator=outcome_validator,
            b2_verifier=b2_verifier,
        )

        interactive = input_queue is not None
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        observer = _ApiRunObserver(
            dashboard_events=self._dashboard_events,
            messages=messages,
            max_turns=max_turns,
            phase_tracker=tracker,
            memory_recall=memory_recall,
        )
        last_error: str | None = None
        quit_requested = False

        # Dual-Route Reasoning — Fast/Slow decider layered on Structured Memory
        # (SM1 unchanged). Fast steps run conservative zero-arg actions without
        # an LLM call; everything else falls through to the model below.
        dual_route = tracker is not None and os.environ.get("RPENT_DUAL_ROUTE") == "1"
        router: Any = None
        if dual_route:
            from rpent.memory.dual_route import DualRouter

            router = DualRouter(
                enable_release=os.environ.get("RPENT_DUAL_ROUTE_RELEASE", "1") == "1"
            )
        total_steps = 0
        fast_steps = 0
        pending_block: str | None = None
        session_over = False

        def _inject_pending(run: Any) -> bool:
            """Drain queued user lines into the live run; True => end session.

            Each line is enqueued ``asap`` so it lands in the next model request
            (the next turn boundary). This runs on the event-loop thread, so
            mutating the run's pending-message queue here is race-free.
            """
            while True:
                try:
                    line = input_queue.get_nowait()  # type: ignore[union-attr]
                except queue.Empty:
                    return False
                if line is None:
                    return True
                line = line.strip()
                if line.lower() in QUIT_TOKENS:
                    return True
                if not line:
                    continue
                run.enqueue(line, priority="asap")
                messages.append({"role": "user", "content": line})
                logger.info("[user] %s", _clip(line, _ARGS_LOG_LIMIT))

        async def _await_next() -> str | None:
            """Block off-loop for the next user line between runs (None => end)."""
            logger.info("awaiting input — type a message to continue, /quit to end")
            while True:
                line = await asyncio.to_thread(input_queue.get)  # type: ignore[union-attr]
                if line is None:
                    return None
                line = line.strip()
                if line.lower() in QUIT_TOKENS:
                    return None
                if line:
                    logger.info("[user] %s", _clip(line, _ARGS_LOG_LIMIT))
                    return line

        seed = user_message
        history: list[ModelMessage] | None = None
        try:
            while True:
                # Dual-route Fast branch: no LLM call. Runs before each model
                # run; the first iteration (history is None) always goes Slow.
                if router is not None and history is not None:
                    action = router.decide(
                        total_steps=total_steps, max_turns=max_turns, tracker=tracker
                    )
                    if action is None:
                        logger.info("[slow] reason=%s", router.slow_reason)
                    else:
                        total_steps += 1
                        fast_steps += 1
                        result = toolkit.execute_tool(action.name, action.args)
                        tracker.on_tool_call(action.name, action.args)
                        result_text = json.dumps(result.result, default=str)
                        tracker.on_tool_result(
                            action.name, result_text, "error" in result.result
                        )
                        # OVP-M: fast steps get the same verdict treatment.
                        action_summary = action.summary
                        if outcome_validator is not None:
                            vline = outcome_validator.observe_result(
                                action.name,
                                action.args,
                                result_text,
                                is_error="error" in result.result,
                            )
                            if vline:
                                action_summary = f"{action.summary}\n\n{vline}"
                        router.observe_fast(action, result.result)
                        logger.info(
                            "[fast] %s(%s)",
                            action.name,
                            _clip(json.dumps(action.args), _ARGS_LOG_LIMIT),
                        )
                        logger.info(
                            "[tool>] %s(%s)",
                            action.name,
                            _clip(json.dumps(action.args), _ARGS_LOG_LIMIT),
                        )
                        logger.info(
                            "[tool<] %s: %s",
                            action.name,
                            _clip(result_text, _TOOL_LOG_LIMIT),
                        )
                        messages.append({"role": "user", "content": action_summary})
                        history = _merge_into_tail(history, action_summary)
                        if result.is_finish:
                            observer.finish_result = result.result
                            logger.info(
                                "FINISH called (fast): %s", observer.finish_result
                            )
                            break
                        continue

                # Dual-route / reason-mode resume with no new prompt: the merged
                # tail (tool results + pending block / fast summary) is popped
                # and reused by pydantic-ai's resume-without-prompt path. The
                # first run (history is None) still starts from the seed.
                _resume = (dual_route or reason_mode) and history is not None
                # Arm C mode selection at this turn boundary: an open
                # verified-MATCHED commit (and nothing anomalous pending)
                # routes this one turn to the constrained COMMIT agent; every
                # other boundary runs the full REASON agent.
                commit_ctx = None
                if reason_mode and history is not None:
                    commit_ctx = outcome_validator.commit_mode_ctx()
                mode = "commit" if commit_ctx is not None else "reason"
                if mode == "commit":
                    commit_mode_steps += 1
                    logger.info(
                        "[reason-mode] COMMIT turn — target=%s (from %s#%s)",
                        commit_ctx["target"],
                        commit_ctx["tool"],
                        commit_ctx["step"],
                    )
                else:
                    reason_mode_steps += 1
                active_agent = commit_agent if mode == "commit" else agent
                # request_limit overrides pydantic-ai's default (50) so the
                # manual max_turns break below is what bounds each run.
                async with active_agent.iter(
                    None if _resume else seed,
                    message_history=history,
                    usage_limits=UsageLimits(request_limit=max_turns + 1),
                ) as run:
                    async for node in run:
                        if interactive and _inject_pending(run):
                            quit_requested = True
                            break
                        if Agent.is_call_tools_node(node):
                            total_steps += 1
                            observer.observe_response(
                                node.model_response,
                                run.usage,
                                log_turn=observer.turns,
                            )

                            async with node.stream(run.ctx) as stream:
                                async for event in stream:
                                    observer.observe_tool(event, run.usage)

                            # Structured Memory v1 — inject a compact context
                            # block, but ONLY on phase transitions / rule fires
                            # (throttled, so it does not inflate the turn count
                            # with every perception).
                            if tracker is not None and observer.finish_result is None:
                                block = tracker.current_block(total_steps)
                                # OVP-M: a MATCHED verdict that has not been
                                # acted on gets one throttled commit reminder,
                                # riding the same injection machinery.
                                if outcome_validator is not None:
                                    hint = outcome_validator.turn_boundary_hint()
                                    if hint:
                                        block = (
                                            f"{block}\n{hint}"
                                            if block
                                            else hint
                                        )
                                if b2_verifier is not None:
                                    hint2 = b2_verifier.turn_boundary_hint()
                                    if hint2:
                                        block = (
                                            f"{block}\n{hint2}"
                                            if block
                                            else hint2
                                        )
                                # Stage B1: decision-point memory recall.
                                # Rides the same throttled injection path.
                                if memory_recall is not None:
                                    try:
                                        fired = memory_recall.turn_boundary(
                                            total_steps
                                        )
                                    except Exception as e:  # noqa: BLE001
                                        fired = None
                                        logger.warning(
                                            "[memrecall] boundary failed: %s", e
                                        )
                                    if fired is not None:
                                        mblock, _event = fired
                                        block = (
                                            f"{block}\n\n{mblock}"
                                            if block
                                            else mblock
                                        )
                                if block is not None:
                                    if dual_route or reason_mode:
                                        # run.enqueue dies with the run on
                                        # restart — stash it and merge it into
                                        # the tail request instead.
                                        pending_block = block
                                    else:
                                        run.enqueue(block, priority="asap")
                                    messages.append(
                                        {"role": "user", "content": block}
                                    )
                                    tracker.mark_injected()
                                    logger.info(
                                        "[phase] injected block (phase=%s)",
                                        tracker.current_phase(),
                                    )

                            if observer.finish_result is not None:
                                logger.info("FINISH called: %s", observer.finish_result)
                                break
                            if total_steps >= max_turns:
                                logger.info(
                                    "reached max_turns=%d. Stopping.", max_turns
                                )
                                break
                            # Dual-route / reason-mode (non-interactive): end
                            # this agent.iter after exactly one model turn so
                            # the outer loop can run the Fast/Slow or
                            # COMMIT/REASON decision. pydantic-ai only commits
                            # this turn's tool results to message_history when
                            # the *next* ModelRequestNode runs; breaking out
                            # now would leave a ModelResponse-with-tool_calls
                            # tail, and the resume path would then re-execute
                            # the tools (double robot actions). CallToolsNode
                            # has already built the tool-result request as
                            # node._next_node.request — commit it so the next
                            # model run resumes on a clean ModelRequest tail.
                            if (dual_route or reason_mode) and not interactive:
                                next_node = getattr(node, "_next_node", None)
                                if getattr(next_node, "request", None) is not None:
                                    run.ctx.state.message_history.append(
                                        next_node.request
                                    )
                                    break
                        elif Agent.is_end_node(node):
                            if interactive:
                                logger.info(
                                    "model ended turn without a tool call "
                                    "— awaiting your input."
                                )
                            else:
                                logger.info(
                                    "model ended turn without a tool call. Stopping."
                                )
                                if dual_route or reason_mode:
                                    # Restarting on a bare ModelResponse tail
                                    # re-emits it forever (_agent_graph.py) —
                                    # end the session instead.
                                    session_over = True
                            break

                    history = run.all_messages()
                    if reason_mode:
                        # Honest per-mode accounting: one model request per
                        # restarted run, so run.usage is that turn's usage.
                        mode_tokens[mode][0] += int(run.usage.input_tokens or 0)
                        mode_tokens[mode][1] += int(run.usage.output_tokens or 0)
                    if (dual_route or reason_mode) and pending_block is not None:
                        history = _merge_into_tail(history, pending_block)
                        pending_block = None

                # finish, quit, end-node (dual-route/reason-mode),
                # non-interactive, or the cumulative step budget is spent =>
                # end the whole session so max_turns is enforced across every
                # run, not per run.
                if (
                    observer.finish_result is not None
                    or quit_requested
                    or session_over
                    or (not interactive and not (dual_route or reason_mode))
                    or total_steps >= max_turns
                ):
                    break
                if interactive:
                    nxt = await _await_next()
                    if nxt is None:
                        break
                    seed = nxt
                    messages.append({"role": "user", "content": seed})
        except UsageLimitExceeded as e:
            logger.info("usage limit reached: %s", e)
        except Exception as e:  # noqa: BLE001 - surfaced via PlannerResult.error
            last_error = _api_error_text(e, no_images=self._no_images)
            logger.error("agent run failed: %s", last_error)
            logger.error("traceback:\n%s", traceback.format_exc())

        if tracker is not None:
            _write_structured_metrics(
                tracker,
                success=(observer.finish_result or {}).get("status") == "success",
                fast_steps=fast_steps,
                slow_reasons=router.slow_reasons if router is not None else None,
                outcome_validator=outcome_validator,
                reason_mode=reason_mode,
                commit_mode_steps=commit_mode_steps,
                reason_mode_steps=reason_mode_steps,
                mode_tokens=mode_tokens if reason_mode else None,
                b2_verifier=b2_verifier,
            )
        if memory_recall is not None:
            try:
                memory_recall.finalize(
                    success=(observer.finish_result or {}).get("status")
                    == "success"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("[memrecall] finalize failed: %s", e)

        return PlannerResult(
            finish_result=observer.finish_result,
            messages=messages,
            stats=_build_stats(
                observer._usage_accum, total_steps, observer.tool_calls
            ),
            error=last_error,
        )

    async def _solve_dashboard(
        self,
        *,
        system_prompt: str,
        user_message: str,
        toolkit: Toolkit,
        max_turns: int,
        interaction: DashboardInteractionPort,
    ) -> PlannerResult:
        """Drive cancellable PydanticAI runs from complete history checkpoints."""
        agent = self._build_agent(system_prompt, toolkit)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        def emit_user(text: str, *, initial: bool = False) -> None:
            if not initial:
                messages.append({"role": "user", "content": text})
            self._dashboard_events.emit(
                TranscriptEvent(
                    {"type": "initial_prompt"}
                    if initial
                    else {"type": "user", "text": text}
                )
            )

        control = DashboardPlannerControl(
            interaction=interaction,
            cancel_active_and_wait=toolkit.cancel_active_and_wait,
            emit_user=emit_user,
            emit_initial_user=lambda: emit_user(user_message, initial=True),
            defer_message_ack=True,
        )
        observer = _ApiRunObserver(
            dashboard_events=self._dashboard_events,
            messages=messages,
            max_turns=max_turns,
        )
        session = _ApiDashboardSession(
            agent=agent,
            control=control,
            observer=observer,
            max_turns=max_turns,
            no_images=self._no_images,
        )
        error: str | None = None
        try:
            await asyncio.wait_for(
                session.run(user_message),
                timeout=self._timeout_s,
            )
        except asyncio.TimeoutError:
            error = f"API planner timed out after {self._timeout_s}s"
            control.end()
        except Exception as exc:
            error = _api_error_text(exc, no_images=self._no_images)
            control.end()
        finally:
            try:
                await control.cancel_active_toolkit()
            except Exception as exc:
                cleanup_error = (
                    f"API toolkit cancellation failed: {type(exc).__name__}: {exc}"
                )
                logger.warning(cleanup_error)
                error = error or cleanup_error
            await session.close()

        return PlannerResult(
            finish_result=observer.finish_result,
            messages=messages,
            stats={
                "backend": "api",
                **_build_stats(session.usage, observer.turns, observer.tool_calls),
            },
            error=error or session.error,
        )

    def _build_agent(
        self,
        system_prompt: str,
        toolkit: Toolkit,
        *,
        outcome_validator: Any = None,
        b2_verifier: Any = None,
    ) -> Agent:
        """Build an Agent for terminal or Dashboard execution."""
        return Agent(
            self._model,
            instructions=system_prompt or None,
            tools=_build_tools(
                toolkit,
                no_images=self._no_images,
                outcome_validator=outcome_validator,
                b2_verifier=b2_verifier,
            ),
            model_settings=_build_model_settings(self._model, self._max_tokens),
            capabilities=[
                Thinking(effort="high"),
                ProcessHistory(processor=_prune_history_images),
            ],
        )

    def _build_commit_agent(
        self,
        toolkit: Toolkit,
        *,
        outcome_validator: Any = None,
    ) -> Agent:
        """Arm C COMMIT-MODE agent: shared model, trimmed instructions,
        action-tools-only. Verdict target rides the tool-result tail."""
        from robots.libero.prompts.reason_mode import COMMIT_AGENT

        return Agent(
            self._model,
            instructions=COMMIT_AGENT,
            tools=_build_tools(
                toolkit,
                no_images=True,  # commit mode forbids perception anyway
                outcome_validator=outcome_validator,
                action_tools_only=True,
            ),
            model_settings=_build_model_settings(self._model, self._max_tokens),
            capabilities=[
                ProcessHistory(processor=_prune_commit_history),
            ],
        )


@dataclasses.dataclass
class _ApiRunObserver:
    """Record model/tool events shared by terminal and Dashboard runs."""

    dashboard_events: DashboardEventSink
    messages: list[dict[str, Any]]
    max_turns: int
    turns: int = 0
    tool_calls: int = 0
    finish_result: dict[str, Any] | None = None
    # Structured Global Memory v1 — set by _solve when the gate is on. The
    # tracker is fed the exact same tool stream the observer already sees.
    phase_tracker: Any = None
    # Stage B1 decision-point memory recall — same stream, same pattern.
    memory_recall: Any = None
    # Usage accumulation across graph runs. Each ``agent.iter`` starts a fresh
    # per-run ``RunUsage`` (new run_id, no inheritance from message_history);
    # in dual-route the planner restarts the graph after every model turn, so
    # the per-run totals must be summed here to keep the ``[usage]`` log lines
    # (and therefore the report's token/request totals) cumulative.
    _usage_accum: RunUsage | None = None
    _usage_run_id: str | None = None
    _usage_in_run: RunUsage | None = None

    def observe_response(
        self,
        response: ModelResponse,
        usage: RunUsage,
        *,
        log_turn: int | None = None,
    ) -> None:
        self.turns += 1
        run_id = getattr(response, "run_id", None)
        if run_id != self._usage_run_id:
            # First model turn of a graph run: `usage` is that run's own
            # cumulative total (== this turn's usage in the one-turn-per-run
            # dual-route flow).
            self._usage_run_id = run_id
            self._usage_in_run = usage
            incr = usage
        else:
            # Later turn within the same run: the run's usage is cumulative,
            # so only the delta since the previous observation is new.
            incr = _usage_delta(usage, self._usage_in_run)
            self._usage_in_run = usage
        self._usage_accum = (
            incr if self._usage_accum is None else self._usage_accum + incr
        )
        message = _serialize_response(response)
        self.messages.append(message)
        _log_response(
            response,
            self._usage_accum,
            self.turns if log_turn is None else log_turn,
            self.max_turns,
        )
        for block in message["content"]:
            if block["type"] == "text":
                payload = {"type": "text", "text": block["text"]}
            elif block["type"] == "thinking":
                payload = {"type": "thinking", "text": block["thinking"]}
            else:
                continue
            self.dashboard_events.emit(TranscriptEvent(payload))
        self.emit_usage(usage)

    def observe_tool(self, event: Any, usage: RunUsage) -> bool:
        completed = False
        if isinstance(event, FunctionToolCallEvent):
            self.tool_calls += 1
            part = event.part
            args = part.args_as_dict()
            if self.phase_tracker is not None:
                self.phase_tracker.on_tool_call(part.tool_name, args)
            self.dashboard_events.emit(
                TranscriptEvent(
                    {"type": "tool_call", "tool": part.tool_name, "args": args}
                )
            )
            if part.tool_name == "finish":
                self.finish_result = {"_finish": True, **args}
        elif isinstance(event, FunctionToolResultEvent):
            completed = True
            message = _serialize_tool_result(event)
            self.messages.append(message)
            _log_tool_result(message)
            part = event.part
            is_error = bool(getattr(part, "is_error", False))
            if self.phase_tracker is not None:
                self.phase_tracker.on_tool_result(
                    part.tool_name, str(message.get("content", "")), is_error
                )
            if self.memory_recall is not None:
                try:
                    self.memory_recall.on_tool_result(
                        part.tool_name, str(message.get("content", "")),
                        is_error,
                    )
                except Exception as e:  # noqa: BLE001 - never break the run
                    logger.warning("[memrecall] observe failed: %s", e)
            self.dashboard_events.emit(
                TranscriptEvent(
                    {
                        "type": "tool_result",
                        "tool": message.get("name") or "tool_result",
                        "result": {
                            "is_error": is_error,
                            "size": len(message["content"]),
                        },
                    }
                )
            )
        self.emit_usage(usage)
        return completed

    def emit_usage(self, usage: RunUsage) -> None:
        self.dashboard_events.emit(
            UsageEvent(
                inp=int(usage.input_tokens or 0),
                out=int(usage.output_tokens or 0),
                tool_calls=self.tool_calls,
            )
        )


def _new_phase_tracker(*, max_turns: int) -> Any:
    """Build the Structured Memory PhaseTracker when the gate is on, else None.

    Gate: ``RPENT_STRUCTURED_MEMORY=1`` (off => baseline behavior, no tracker).
    Rules come from ``RPENT_STRUCTURED_RULES`` (absolute path) or the frozen
    authoritative copy at ``analysis/structured_rules_v1.json``. Task scope
    comes from ``RPENT_TASK`` (set per-episode by the scheduler), falling back
    to parsing the run output dir basename (``_t<N>_s<M>``).
    """
    if os.environ.get("RPENT_STRUCTURED_MEMORY") != "1":
        return None
    from rpent.memory.structured import (
        PhaseTracker,
        detect_task,
        load_rules,
    )

    rules_path = os.environ.get("RPENT_STRUCTURED_RULES") or str(
        Path(get_repo_root()) / "analysis" / "structured_rules_v1.json"
    )
    rules = load_rules(rules_path)
    task = detect_task()
    memory_dir = str(Path(get_repo_root()) / "resources" / "libero" / "memory")
    logger.info("[phase] structured memory ON — rules=%s task=%s", rules_path, task)
    return PhaseTracker(
        rules,
        task=task,
        max_turns=max_turns,
        memory_dir=memory_dir,
    )


def _new_outcome_validator(tracker: Any) -> Any:
    """Build the OVP-M OutcomeValidator when the gate is on, else None.

    Gate: ``RPENT_OVPM=1`` (requires the Structured Memory tracker — phase
    context comes from it; ``RPENT_STRUCTURED_MEMORY=1`` must also be set).
    Contracts come from ``RPENT_OVPM_CONTRACTS`` (absolute path) or the v2
    rules document at ``analysis/structured_rules_v2.json``; a missing file
    degrades to a no-op validator with a warning, never a mid-episode crash.
    """
    if os.environ.get("RPENT_OVPM") != "1" or tracker is None:
        return None
    from rpent.memory.ovpm import OutcomeValidator, load_contracts
    from rpent.memory.structured import detect_task

    contracts_path = os.environ.get("RPENT_OVPM_CONTRACTS") or str(
        Path(get_repo_root()) / "analysis" / "structured_rules_v2.json"
    )
    contracts = load_contracts(contracts_path)
    task = detect_task()
    logger.info(
        "[ovpm] outcome validation ON — contracts=%s n=%d task=%s",
        contracts_path,
        len(contracts),
        task,
    )
    return OutcomeValidator(contracts, tracker=tracker, task=task)


def _new_b2_verifier(tracker: Any) -> Any:
    """Build the B2 TransitionVerifier when the gate is on, else None.

    Gate: ``RPENT_OVPM2=1`` (arm B2 = arm A + state-transition verification;
    independent of arm B's ``RPENT_OVPM``). Requires the Structured Memory
    tracker for phase context in logs and latency accounting — the rules
    themselves are action-level and phase-free.
    """
    if os.environ.get("RPENT_OVPM2") != "1" or tracker is None:
        return None
    from rpent.memory.structured import detect_task
    from rpent.memory.stv import TransitionVerifier

    task = detect_task()
    logger.info("[b2] state-transition verification ON — task=%s", task)
    return TransitionVerifier(tracker=tracker, task=task)


def _new_memory_recall(tracker: Any) -> Any:
    """Build the DecisionMemory recall component when the gate is on.

    Gate: ``RPENT_MEMORY_TRIGGER`` in {"1", "progress"} (Stage B1 arms
    memB2/memB3 used "1" — the frozen v1 trigger; Stage C3 arm O2 uses
    "progress" — the Stage C2 frozen progress-aware rules). Requires the
    Structured Memory tracker for the phase signal. Rank method comes from
    ``RPENT_MEMORY_RANK`` (Q0_FIXED | Q3) — both frozen Stage A ports.
    Stage G baseline arms add "periodic"/"motion_stuck" (frozen in
    analysis/stageG_trigger_baseline_config.md) — baseline decision rules
    only; retrieval/injection/cooldown identical to the frozen modes.
    """
    mode = os.environ.get("RPENT_MEMORY_TRIGGER", "")
    if mode not in ("1", "progress", "periodic", "motion_stuck") \
            or tracker is None:
        return None
    from rpent.memory.retrieval import DecisionMemory

    rank = os.environ.get("RPENT_MEMORY_RANK", "Q0_FIXED")
    logger.info("[memrecall] decision-point memory recall ON — rank=%s "
                "mode=%s", rank, mode)
    return DecisionMemory(tracker, mode=("v1" if mode == "1" else mode))


def _write_structured_metrics(
    tracker: Any,
    *,
    success: bool,
    fast_steps: int = 0,
    slow_reasons: list[str] | None = None,
    outcome_validator: Any = None,
    reason_mode: bool = False,
    commit_mode_steps: int = 0,
    reason_mode_steps: int = 0,
    mode_tokens: dict[str, list[int]] | None = None,
    b2_verifier: Any = None,
) -> None:
    """Write per-episode Structured Memory metrics into the run output dir.

    Best-effort: a metrics write failure must never fail the run.
    """
    try:
        out = get_output_dir()
        snap = tracker.snapshot(success=success)
        snap["fast_steps"] = fast_steps
        snap["slow_reasons"] = slow_reasons
        if outcome_validator is not None:
            snap["ovpm"] = outcome_validator.snapshot(success=success)
        if b2_verifier is not None:
            snap["b2"] = b2_verifier.snapshot(success=success)
        if reason_mode:
            # Arm C per-mode accounting (flat keys for the scheduler's
            # metric_fields extraction). Tokens are per mode, not per
            # request — both modes still cost one model call per turn.
            mt = mode_tokens or {}
            snap["reason_mode_enabled"] = True
            snap["commit_mode_steps"] = commit_mode_steps
            snap["reason_mode_steps"] = reason_mode_steps
            snap["commit_tokens_in"] = int(mt.get("commit", [0, 0])[0])
            snap["commit_tokens_out"] = int(mt.get("commit", [0, 0])[1])
            snap["reason_tokens_in"] = int(mt.get("reason", [0, 0])[0])
            snap["reason_tokens_out"] = int(mt.get("reason", [0, 0])[1])
        (out / "structured_metrics.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "[phase] metrics written — fired=%s injections=%s success=%s "
            "fast_steps=%s commit_steps=%s reason_steps=%s",
            snap["fired_rules"],
            snap["injections"],
            success,
            fast_steps,
            commit_mode_steps if reason_mode else "-",
            reason_mode_steps if reason_mode else "-",
        )
    except Exception as e:  # noqa: BLE001 - metrics must never break the run
        logger.warning("[phase] failed to write structured metrics: %s", e)


class _ApiDashboardSession:
    """Own serial, independent PydanticAI runs for one Dashboard TaskRun."""

    def __init__(
        self,
        *,
        agent: Agent,
        control: DashboardPlannerControl,
        observer: _ApiRunObserver,
        max_turns: int,
        no_images: bool,
    ) -> None:
        self._agent = agent
        self._control = control
        self._max_turns = max_turns
        self._no_images = no_images
        self._observer = observer
        self._history: list[ModelMessage] = []
        self.usage = RunUsage()
        self._pending_prompts: deque[tuple[str | None, str]] = deque()
        self._run_task: asyncio.Task[Any] | None = None
        self._active_prompt = False
        self._closing = False
        self.error: str | None = None

    async def run(self, prompt: str) -> None:
        await self.submit(prompt)
        await self._control.start()
        await self._control.run(self)

    async def submit(self, text: str) -> int:
        """Queue Dashboard input as a new independent API run."""
        return self._queue_prompt(text)

    async def submit_dashboard_message(self, message: DashboardMessage) -> int:
        """Queue Dashboard input and defer acknowledgement until it starts."""
        return self._queue_prompt(message.text, message_id=message.message_id)

    def _queue_prompt(self, text: str, *, message_id: str | None = None) -> int:
        if self._closing:
            raise RuntimeError("API conversation is closed")
        if self.error is not None:
            raise RuntimeError(self.error)
        self._pending_prompts.append((message_id, text))
        if self._run_task is None:
            self._run_task = asyncio.create_task(self._run_pending_prompts())
        return 1

    async def interrupt(self) -> int:
        run_task = self._run_task
        interrupted = int(self._active_prompt) + len(self._pending_prompts)
        discarded_message_ids = tuple(
            message_id
            for message_id, _ in self._pending_prompts
            if message_id is not None
        )
        self._pending_prompts.clear()
        for message_id in discarded_message_ids:
            self._control.message_discarded(message_id)
        if run_task is None or run_task.done():
            return interrupted
        run_task.cancel()
        try:
            with contextlib.suppress(asyncio.CancelledError):
                await run_task
        finally:
            if self._run_task is run_task:
                self._run_task = None
        return interrupted

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        await self.interrupt()

    async def _run_pending_prompts(self) -> None:
        task = asyncio.current_task()
        try:
            while self._pending_prompts and not self._closing:
                message_id, seed = self._pending_prompts.popleft()
                self._active_prompt = True
                try:
                    if message_id is not None:
                        self._control.message_started(message_id, seed)
                    if not await self._run_agent(seed):
                        self._pending_prompts.clear()
                        return
                    await self._control.complete(self)
                finally:
                    self._active_prompt = False
        finally:
            if self._run_task is task:
                self._run_task = None

    async def _run_agent(self, seed: str) -> bool:
        run_completed = False
        run: Any | None = None
        node: Any | None = None
        try:
            async with self._agent.iter(
                seed,
                message_history=list(self._history),
                usage=self.usage,
                usage_limits=UsageLimits(request_limit=self._max_turns + 1),
            ) as run:
                node = run.next_node
                while not Agent.is_end_node(node):
                    if Agent.is_call_tools_node(node):
                        await self._process_tool_node(run, node)
                    if (
                        self._observer.finish_result is not None
                        or self._observer.turns >= self._max_turns
                    ):
                        self._control.end()
                        return False
                    if self._pending_prompts:
                        # Dashboard input accepted at this tool boundary starts
                        # a fresh run from the checkpoint captured below.
                        node = await run.next(node)
                        break
                    node = await run.next(node)

                run_completed = True
        except Exception as exc:
            self.error = _api_error_text(exc, no_images=self._no_images)
            if not self._closing:
                self._control.end()
        finally:
            # Preserve interrupted tool results for PydanticAI to repair on the
            # next run. Older supported releases can leave a bare tool-call
            # response when cancellation wins before any tool returns; remove
            # only that unusable frontier.
            if run is not None:
                history = list(run.all_messages())
                if (
                    history
                    and isinstance(history[-1], ModelResponse)
                    and history[-1].tool_calls
                ):
                    if request := getattr(node, "request", None):
                        history.append(request)
                    else:
                        history.pop()
                self._history = history
        return run_completed and not self._closing

    async def _process_tool_node(self, run: Any, node: Any) -> None:
        self._observer.observe_response(node.model_response, run.usage)

        async with node.stream(run.ctx) as stream:
            async for event in stream:
                tool_completed = self._observer.observe_tool(event, run.usage)
                if (
                    tool_completed
                    and self._observer.finish_result is None
                    and self._observer.turns < self._max_turns
                ):
                    await self._control.tool_completed(self)


def _build_model_settings(model: Model, max_tokens: int) -> ModelSettings:
    """Build model settings, enabling prompt caching for Anthropic models."""
    from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings

    # RPENT_REASONING_EFFORT: OpenAI-compatible planner 的推理档位旋钮。
    # GLM-5.3-Flash chat template 只认 low/high 两档,其余值(含未设)一律渲染
    # Max — 本地部署默认想要 max,但 pydantic-ai Thinking 枚举没有 'max',
    # 所以走显式 OpenAIChatModelSettings 字段直传。只收 {low,high,max},非法
    # 值/误用于非 openai 模型(如远端 anthropic 端点)一律 fail-fast:模板会把
    # 垃圾值静默当 Max,掩盖配置错误。不设此 env 时行为与以前完全一致。
    effort = os.environ.get("RPENT_REASONING_EFFORT")
    if effort is not None:
        from pydantic_ai.models.openai import (
            OpenAIChatModel,
            OpenAIChatModelSettings,
        )

        if not isinstance(model, OpenAIChatModel):
            raise ValueError(
                f"RPENT_REASONING_EFFORT={effort!r} only applies to "
                f"openai-chat: models (got {type(model).__name__})"
            )
        if effort not in ("low", "high", "max"):
            raise ValueError(
                f"RPENT_REASONING_EFFORT must be one of low/high/max, "
                f"got {effort!r} (GLM template silently maps anything "
                "else to max)"
            )
        return OpenAIChatModelSettings(
            max_tokens=max_tokens,
            openai_reasoning_effort=effort,
        )

    if isinstance(model, AnthropicModel):
        return AnthropicModelSettings(
            max_tokens=max_tokens,
            anthropic_cache_instructions=True,
            anthropic_cache_tool_definitions=True,
            anthropic_cache_messages=True,
        )
    return ModelSettings(max_tokens=max_tokens)


def _prune_history_images(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Drop old camera images so the resent request body stays bounded."""
    # Every image in history, oldest -> newest: (msg_idx, part_idx, item_idx, nbytes).
    located: list[tuple[int, int, int, int]] = []
    for mi, message in enumerate(messages):
        for pi, part in enumerate(getattr(message, "parts", ()) or ()):
            if not isinstance(part, UserPromptPart) or not isinstance(
                part.content, list
            ):
                continue
            for ii, item in enumerate(part.content):
                if isinstance(item, BinaryContent) and item.media_type.startswith(
                    "image/"
                ):
                    located.append((mi, pi, ii, len(item.data)))

    if not located:
        return messages

    # Walk newest -> oldest, keeping images while under the byte budget.
    keep: set[tuple[int, int, int]] = set()
    total = 0
    for rank, (mi, pi, ii, nbytes) in enumerate(reversed(located)):
        if rank < _MIN_RECENT_IMAGES or total + nbytes <= _MAX_HISTORY_IMAGE_BYTES:
            keep.add((mi, pi, ii))
            total += nbytes

    if len(keep) == len(located):
        return messages

    drop_items_by_part: dict[tuple[int, int], set[int]] = {}
    for mi, pi, ii, _ in located:
        if (mi, pi, ii) not in keep:
            drop_items_by_part.setdefault((mi, pi), set()).add(ii)

    new_messages = list(messages)
    for (mi, pi), drop_items in drop_items_by_part.items():
        message = new_messages[mi]
        part = message.parts[pi]
        new_content = [
            "[earlier camera image omitted to bound request size]"
            if ci in drop_items
            else item
            for ci, item in enumerate(part.content)
        ]
        new_parts = list(message.parts)
        new_parts[pi] = dataclasses.replace(part, content=new_content)
        new_messages[mi] = dataclasses.replace(message, parts=new_parts)

    return new_messages


def _is_image_rejection(e: Exception) -> bool:
    """True when the provider returned a 4xx complaining about image input.

    Matches errors like ``400 {'code': 10007, 'msg': "Bad Request: [message
    type 'image_url' is not supported]"}`` from OpenAI-compatible endpoints
    serving text-only models.
    """
    if not isinstance(e, ModelHTTPError):
        return False
    if not 400 <= e.status_code < 500:
        return False
    return "image" in str(e).lower()


def _api_error_text(error: Exception, *, no_images: bool) -> str:
    text = f"{type(error).__name__}: {error}"
    if not no_images and _is_image_rejection(error):
        text += (
            "\n\nThe model rejected image input — it is likely a text-only "
            "model (no vision support). Re-run with --no-images: RPent will "
            "then keep every visual observation as a file-path text notice "
            "instead of sending image bytes."
        )
    return text


def _build_tools(
    toolkit: Toolkit,
    *,
    no_images: bool = False,
    outcome_validator: Any = None,
    action_tools_only: bool = False,
    b2_verifier: Any = None,
) -> list[Tool]:
    """Build the API-only image reader plus pydantic-ai toolkit wrappers.

    ``action_tools_only`` (arm C COMMIT MODE) drops the image reader and all
    perception/memory tools, keeping ACTION_TOOLS + finish only.
    """
    from rpent.memory.structured import ACTION_TOOLS

    guard = None if action_tools_only else _PerceptionGuard.make()
    tools: list[Tool] = []
    if not action_tools_only:
        image_reader = read_image_text_only if no_images else read_image
        if guard is not None:
            base_reader = image_reader  # capture pre-rebind reference

            def _guarded_read_image(path: str):
                pre = guard.check_before("read_image", {"path": path})
                if pre is not None:
                    return {
                        "perception_blocked": True,
                        "repeated_perception": True,
                        "note": pre,
                    }
                res = base_reader(path)
                post = guard.observe_after("read_image", {"path": path}, str(path))
                if post is not None:
                    return {
                        "perception_blocked": True,
                        "repeated_perception": True,
                        "note": post,
                    }
                return res

            image_reader = _guarded_read_image
        tools.append(Tool(image_reader, name="read_image"))
    for spec in toolkit.get_tools_spec():
        name = spec["name"]
        if action_tools_only and name not in ACTION_TOOLS and name != "finish":
            continue
        tools.append(
            Tool.from_schema(
                function=_make_tool_function(
                    toolkit,
                    name,
                    no_images=no_images,
                    perception_guard=guard,
                    outcome_validator=outcome_validator,
                    b2_verifier=b2_verifier,
                ),
                name=name,
                description=spec.get("description", ""),
                json_schema=spec.get("input_schema")
                or {"type": "object", "properties": {}},
                takes_ctx=False,
            )
        )
    return tools


def read_image(path: str) -> ToolReturn | dict[str, str]:
    """Read a local image path returned by an RPent tool as visual input.

    File-system failures are returned to the model as structured tool errors,
    matching :func:`rpent.tools.common.read_text_file`, so a bad model-supplied
    path does not abort the entire agent run.
    """
    image_path = Path(path)
    if not image_path.is_absolute():
        image_path = get_repo_root() / image_path
    if not image_path.exists():
        return {"error": f"file not found: {image_path}"}
    if image_path.is_dir():
        return {"error": f"is a directory: {image_path}"}
    try:
        content = BinaryContent.from_path(image_path)
    except Exception as e:
        return {"error": str(e)}
    return ToolReturn(
        return_value=str(image_path),
        content=[content],
    )


def read_image_text_only(path: str) -> str:
    """``read_image`` stub for ``--no-images``: acknowledge, send no bytes."""
    return (
        f"{path} exists, but image input is disabled (--no-images, text-only "
        "model). Reason from textual state instead: view_driver_state, "
        "back_project, and the numeric fields in tool results."
    )


def _make_tool_function(
    toolkit: Toolkit,
    name: str,
    *,
    no_images: bool = False,
    perception_guard: _PerceptionGuard | None = None,
    outcome_validator: Any = None,
    b2_verifier: Any = None,
):
    """Return a callable that dispatches one tool call to the toolkit."""

    def _call(**kwargs: Any) -> Any:
        if perception_guard is not None:
            pre = perception_guard.check_before(name, kwargs)
            if pre is not None:
                return {
                    "perception_blocked": True,
                    "repeated_perception": True,
                    "note": pre,
                }
        result = toolkit.execute_tool(name, kwargs)
        text, images = _content_blocks_to_pydantic(result.content_blocks)
        # OVP-M: append the outcome verdict to the tool result the model
        # already reads — zero extra turns, zero extra requests.
        if outcome_validator is not None:
            line = outcome_validator.observe_result(
                name,
                kwargs,
                text,
                is_error=isinstance(result.result, dict)
                and "error" in result.result,
            )
            if line:
                text = f"{text}\n\n{line}"
        # B2: state-transition verdict, same zero-turn injection channel.
        if b2_verifier is not None:
            line2 = b2_verifier.observe_result(
                name,
                kwargs,
                text,
                is_error=isinstance(result.result, dict)
                and "error" in result.result,
            )
            if line2:
                text = f"{text}\n\n{line2}"
        if perception_guard is not None:
            post = perception_guard.observe_after(name, kwargs, text)
            if post is not None:
                return {
                    "perception_blocked": True,
                    "repeated_perception": True,
                    "note": post,
                }
        if images and not no_images:
            return ToolReturn(return_value=text, content=images)
        return text

    _call.__name__ = name
    return _call


def _content_blocks_to_pydantic(
    blocks: list[dict[str, Any]],
) -> tuple[str, list[BinaryContent]]:
    """Split Anthropic-shaped content blocks into text and image content."""
    text_parts: list[str] = []
    images: list[BinaryContent] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "image":
            source = block.get("source") or {}
            data = source.get("data")
            if source.get("type") == "base64" and data:
                images.append(
                    BinaryContent(
                        data=base64.b64decode(data),
                        media_type=source.get("media_type", "image/png"),
                    )
                )
    text = "\n\n".join(part for part in text_parts if part) or "{}"
    return text, images


def _serialize_response(response: ModelResponse) -> dict[str, Any]:
    """Render one assistant turn as a serialisable transcript message."""
    content: list[dict[str, Any]] = []
    for part in response.parts:
        if isinstance(part, TextPart):
            if part.content:
                content.append({"type": "text", "text": part.content})
        elif isinstance(part, ThinkingPart):
            if part.content:
                content.append({"type": "thinking", "thinking": part.content})
        elif isinstance(part, ToolCallPart):
            content.append(
                {
                    "type": "tool_use",
                    "id": part.tool_call_id,
                    "name": part.tool_name,
                    "input": part.args_as_dict(),
                }
            )
    return {"role": "assistant", "content": content}


def _serialize_tool_result(event: FunctionToolResultEvent) -> dict[str, Any]:
    """Render one tool result as a serialisable transcript message (no images)."""
    part = event.part
    content = getattr(part, "content", None)
    if not isinstance(content, str):
        content = json.dumps(content, default=str)
    return {
        "role": "tool",
        "name": getattr(part, "tool_name", None),
        "tool_call_id": getattr(part, "tool_call_id", None),
        "content": content,
    }


def _usage_delta(later: RunUsage, earlier: RunUsage) -> RunUsage:
    """Return ``later - earlier`` as a fresh RunUsage (clamped at 0).

    ``RunUsage`` is cumulative within one graph run and has no subtraction
    operator; ``_ApiRunObserver`` needs the per-turn increment to accumulate
    totals across the restarted runs of the dual-route flow.
    """
    _d = lambda a, b: max(a - b, 0)  # noqa: E731 - tiny local clamp
    d = RunUsage()
    d.requests = _d(later.requests, earlier.requests)
    d.tool_calls = _d(later.tool_calls, earlier.tool_calls)
    d.input_tokens = _d(later.input_tokens, earlier.input_tokens)
    d.output_tokens = _d(later.output_tokens, earlier.output_tokens)
    d.cache_read_tokens = _d(later.cache_read_tokens, earlier.cache_read_tokens)
    d.cache_write_tokens = _d(later.cache_write_tokens, earlier.cache_write_tokens)
    d.input_audio_tokens = _d(later.input_audio_tokens, earlier.input_audio_tokens)
    d.cache_audio_read_tokens = _d(
        later.cache_audio_read_tokens, earlier.cache_audio_read_tokens
    )
    return d


def _build_stats(
    usage: RunUsage | None, turns: int, n_tool_calls: int
) -> dict[str, Any]:
    """Assemble the run stats dict from accumulated usage and counters."""
    stats: dict[str, Any] = {"turns_used": turns, "tool_calls": n_tool_calls}
    if usage is not None:
        stats.update(
            {
                "total_input_tokens": int(usage.input_tokens or 0),
                "total_output_tokens": int(usage.output_tokens or 0),
                "cache_read_tokens": int(usage.cache_read_tokens or 0),
                "cache_write_tokens": int(usage.cache_write_tokens or 0),
                "requests": int(usage.requests or 0),
            }
        )
    return stats


def _log_response(
    response: ModelResponse, usage: RunUsage, turn: int, max_turns: int
) -> None:
    """Log model text, thinking, tool calls, and cumulative usage for a turn."""
    logger.info("=== turn %d/%d ===", turn, max_turns)
    for part in response.parts:
        if isinstance(part, TextPart):
            text = (part.content or "").strip()
            if text:
                logger.info("[model] %s", text)
        elif isinstance(part, ThinkingPart):
            text = (part.content or "").strip()
            if text:
                logger.info("[think] %s", _clip(text, _TEXT_LOG_LIMIT))
        elif isinstance(part, ToolCallPart):
            args = json.dumps(part.args_as_dict(), default=str)
            logger.info("[tool>] %s(%s)", part.tool_name, _clip(args, _ARGS_LOG_LIMIT))
    logger.info(
        "[usage] in=%s out=%s cache_read=%s cache_write=%s requests=%s",
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_tokens,
        usage.cache_write_tokens,
        usage.requests,
    )


def _log_tool_result(message: dict[str, Any]) -> None:
    """Log a one-line summary of a tool result."""
    content = " ".join((message.get("content") or "").split())
    logger.info("[tool<] %s: %s", message.get("name"), _clip(content, _TOOL_LOG_LIMIT))


def _clip(text: str, limit: int) -> str:
    """Truncate ``text`` to ``limit`` characters with an overflow marker."""
    if len(text) <= limit:
        return text
    return text[:limit] + "...(+%d)" % (len(text) - limit)


def _prune_commit_history(messages: list[ModelMessage]) -> list[ModelMessage]:
    """COMMIT-MODE history: last few messages only, images stripped.

    The verdict-bearing tool result the commit turn must act on is at the
    tail; everything older is context the full REASON agent already weighed.
    """
    return _prune_history_images(messages[-8:])
