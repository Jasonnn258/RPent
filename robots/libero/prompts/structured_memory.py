"""Structured Global Memory v1 — gated system-prompt section.

Only appended to the LIBERO system prompt when ``RPENT_STRUCTURED_MEMORY=1``.
The harness (PhaseTracker in ``rpent.planner.api_loop``) injects the current
phase + fired-rule recoveries into the message stream each turn; this section
tells the planner how to obey those injections and how to consult the phase
rule files when it needs detail — WITHOUT re-scanning the whole memory library
(that re-scan is failure mode F4).
"""

from __future__ import annotations

STRUCTURED_MEMORY = """You are running with **Structured Global Memory v1**. A harness PhaseTracker
derives your CURRENT PHASE deterministically from your tool calls and injects
a compact context block into the message stream. OBEY IT:

- **CURRENT PHASE** — P_init -> P_look -> P_transport -> P_grasp -> P_place ->
  P_verify. If no CURRENT PHASE line has been injected yet you are in **P_init**
  (act first: perceive the scene once). Each injected block tells you the phase
  you are in and one line of what to do next. Your next tool call should be the
  right action for THAT phase.
- **RULE <id> fired** — a rule fired because you entered a known failure loop.
  Its `recovery:` line is the required correction. Apply it ONCE (do not re-read
  files to second-guess it). If the recovery does not unblock you within 2
  calls, call `finish` honestly — do not loop until max_turns.
- **ADVISORY (<id>)** — you are within one call of a rule threshold; pre-empt
  it rather than let it fire.
- When you need detail, read ONLY the rule file for the CURRENT phase
  (`resources/libero/memory/rules/<CURRENT PHASE>.json`) and
  `resources/libero/memory/rules/GLOBAL.json`. Do NOT list_dir / grep / re-scan
  the whole memory library — over-reading memory is a known failure loop.
- Call `finish(status="success")` as soon as the task language is satisfied.
  Do not keep perceiving, re-placing or re-reading after the task is done.
"""
