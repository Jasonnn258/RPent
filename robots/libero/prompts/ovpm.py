"""Outcome-Validated Procedural Memory (OVP-M) — gated system-prompt section.

Only appended to the LIBERO system prompt when ``RPENT_OVPM=1`` (which also
requires ``RPENT_STRUCTURED_MEMORY=1``). The harness OutcomeValidator
(``rpent.memory.ovpm``) appends a ``[ovpm]`` verdict line to action-tool
results and a throttled commit reminder at turn boundaries; this section
tells the planner how to act on those verdicts — commit on MATCHED without
re-confirmation, switch strategy on MISMATCH instead of unchanged repeats.
"""

from __future__ import annotations

OVPM = """You are running with **Outcome-Validated Memory** on top of Structured
Global Memory v1. Every action result may carry a one-line ``[ovpm]`` verdict
comparing the expected outcome of that action with what actually happened
(from the robot's own sensors and the official termination flag). OBEY IT:

- **``[ovpm] <tool>#<n> MATCHED``** — the expected outcome is verified.
  COMMIT to the next step named after "Commit:" immediately. Do NOT
  re-perceive, re-grasp, re-place or otherwise re-confirm an outcome that is
  already verified — redundant confirmation is a known failure loop.
- **``[ovpm] <tool>#<n> MISMATCH``** — the expected outcome did NOT happen.
  Do not repeat the same primitive unchanged. Follow the advice in the
  verdict (inspect the precondition once, escalate to the alternative
  strategy, or report honestly via `finish`). A second unchanged repeat of
  a mismatched action is a failure loop.
- **UNCERTAIN** verdicts are not injected; absence of an ``[ovpm]`` line
  means the outcome was not machine-checkable — reason normally.
- The verdict quotes real sensor values from the tool result you already
  received. Trust it over your prior expectation.
"""
