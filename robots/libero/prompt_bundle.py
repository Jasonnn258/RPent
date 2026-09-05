"""LIBERO prompt bundle assembly."""

from __future__ import annotations

import os

from robots.libero.prompts import system as system_parts
from robots.libero.prompts import user as user_parts
from rpent.context.prompt_utils import Numbered, PromptNode


def system_prompt() -> PromptNode:
    """Assemble the LIBERO system prompt tree."""
    node = {
        "ROLE AND EVALUATION": system_parts.ROLE_AND_EVALUATION,
        "PROVEN LEVERS & LESSONS — libero_10_task seed-0 sweep solved 9/10 (READ THIS)": (
            system_parts.PROVEN_LEVERS
        ),
        "RUNTIME": system_parts.RUNTIME,
        "YOUR GOAL": system_parts.GOAL,
        "RULES (NON-NEGOTIABLE)": system_parts.RULES,
        "LOCALIZATION — how to get an object's world xyz WITHOUT GT coords": (
            system_parts.LOCALIZATION
        ),
        "FIRST-STEP ALGORITHM — agentview = IDENTITY, wrist = GEOMETRY": (
            system_parts.PERCEPTION_ALGORITHM
        ),
        "WORKFLOW": Numbered(system_parts.WORKFLOW_STEPS),
        "KEY HYPERPARAMETERS": system_parts.KEY_HYPERPARAMETERS,
        "OUTPUT DISCIPLINE": system_parts.OUTPUT_DISCIPLINE,
    }
    # Structured Global Memory v1 — gated, so the baseline prompt stays
    # byte-identical when the gate is off.
    if os.environ.get("RPENT_STRUCTURED_MEMORY") == "1":
        from robots.libero.prompts import structured_memory as sm

        node["STRUCTURED MEMORY (v1) — obey CURRENT PHASE + phase rules"] = (
            sm.STRUCTURED_MEMORY
        )
    # OVP-M (arm B) — gated, so the SM1 baseline prompt stays byte-identical
    # when the gate is off. Mirrors the validator gate: needs the tracker.
    if os.environ.get("RPENT_OVPM") == "1" and (
        os.environ.get("RPENT_STRUCTURED_MEMORY") == "1"
    ):
        from robots.libero.prompts import ovpm as _ovpm

        node["OUTCOME-VALIDATED MEMORY — obey [ovpm] verdicts (commit/recover)"] = (
            _ovpm.OVPM
        )
    return node


def user_prompt() -> PromptNode:
    """Assemble the LIBERO user prompt tree."""
    return {
        "CELL": user_parts.CELL,
        "MODE": user_parts.MODE,
        "BEGIN": user_parts.BEGIN,
    }


__all__ = ["system_prompt", "user_prompt"]
