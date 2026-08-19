"""Structured Global Memory v1 — executable phase-scoped rules.

Converts free-text Global Memory into precondition-gated rules the planner
reads via per-turn phase context injection. Pure logic lives here; integration
with the planner is gated behind ``RPENT_STRUCTURED_MEMORY=1`` in
``rpent.planner.api_loop``.
"""
