"""Opt-in, metadata-only P1 planner model-request latency instrumentation.

RPENT_API_LATENCY_LOG must point inside the repository's gitignored artifacts/.
NO prompt, text, model responses, images, tool args, IDs, or API secrets
are inspected or written. Default planner behavior stays unchanged when unset.

Scope: times the model-request node in the pydantic-ai graph, not tool
execution, VLA infer, renderer or environment. TTFT/network/generation
cannot be separated without model-provider-side streaming metrics.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path


def _private_output(path: str, repo: Path) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("MISSING_API_LATENCY_OUTPUT")
    root = (repo / "artifacts").resolve()
    dest = Path(path).expanduser().resolve()
    if not dest.is_relative_to(root) or dest == root or dest.suffix != ".jsonl":
        raise ValueError("LATENCY_OUTPUT_MUST_BE_ARTIFACTS_JSONL")
    return dest


class ApiLatencyProbe:
    """One probe per Planner solve; no mutable global state.

    A graph run may be restarted after each model turn, so usage from
    run.usage is explicitly marked as per-graph cumulative, not falsely
    represented as per-turn token deltas. No per-episode IDs are recorded.
    """

    def __init__(self, destination: Path, clock=time.perf_counter):
        self.destination = Path(destination)
        self.clock = clock
        self.inflight: float | None = None
        self.sequence = 0
        self.reported_errors = 0

    @classmethod
    def from_env(cls, *, repo: Path) -> "ApiLatencyProbe | None":
        raw = os.environ.get("RPENT_API_LATENCY_LOG")
        if raw is None or not raw.strip():
            return None
        return cls(_private_output(raw, repo))

    def begin_request(self) -> None:
        if self.inflight is not None:
            raise ValueError("OVERLAPPING_MODEL_REQUEST_TIMING")
        self.inflight = self.clock()

    def finish_request(self, *, usage=None, outcome: str = "unknown") -> dict:
        if self.inflight is None:
            raise ValueError("MODEL_REQUEST_START_MISSING")
        elapsed = self.clock() - self.inflight
        self.inflight = None
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("INVALID_MONOTONIC_DURATION")
        self.sequence += 1
        def count(attr):
            v = getattr(usage, attr, None) if usage is not None else None
            if type(v) is int and v >= 0:
                return v
            return None
        # pydantic-ai run.usage may be cumulative across requests within
        # one agent.iter; never interpret totals below as per-call values.
        rec = {
            "protocol": "RPENT_API_REQUEST_LATENCY_V1",
            "request_idx": self.sequence,
            "model_node_elapsed_s": round(elapsed, 6),
            "graph_usage_input_tokens_cumulative": count("input_tokens"),
            "graph_usage_output_tokens_cumulative": count("output_tokens"),
            "graph_usage_requests_cumulative": count("requests"),
            "outcome": outcome if outcome in ("tool_node", "end_node", "error") else "unknown",
        }
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        with self.destination.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
        return rec

    def finish_if_pending(self, *, usage=None, outcome: str = "error"):
        if self.inflight is None:
            return None
        return self.finish_request(usage=usage, outcome=outcome)
