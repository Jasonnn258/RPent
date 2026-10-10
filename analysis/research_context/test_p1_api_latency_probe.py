"""Pure synthetic tests for the opt-in, no-payload planner latency probe."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rpent.utils.api_latency_probe import ApiLatencyProbe, _private_output


class LatencyProbeTests(unittest.TestCase):
    def test_unset_is_zero_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"RPENT_API_LATENCY_LOG": ""}):
                self.assertIsNone(ApiLatencyProbe.from_env(repo=Path(tmp)))
            with patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(ApiLatencyProbe.from_env(repo=Path(tmp)))

    def test_private_path_only_and_no_absolute_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"artifacts").mkdir()
            good=root/"artifacts"/"p1_perf"/"api_timing.jsonl"
            self.assertEqual(_private_output(str(good),root),good.resolve())
            for bad in (root/"not_private.jsonl",root/"artifacts"/"bad.json",
                        root/"artifacts"/".."/"outside.jsonl"):
                with self.assertRaisesRegex(ValueError,"ARTIFACTS_JSONL"):
                    _private_output(str(bad),root)

    def test_two_requests_write_only_aggregate_usage_no_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            p=root/"artifacts"/"perf"/"timings.jsonl"
            stamps=iter([10.0,11.25,12.0,12.5])
            probe=ApiLatencyProbe(p,clock=lambda:next(stamps))
            probe.begin_request()
            probe.finish_request(
                usage=SimpleNamespace(input_tokens=121,output_tokens=17,requests=1),
                outcome="tool_node")
            probe.begin_request()
            probe.finish_request(
                usage=SimpleNamespace(input_tokens=322,output_tokens=44,requests=2),
                outcome="end_node")
            data=[json.loads(s) for s in p.read_text().splitlines()]
            self.assertEqual(len(data),2)
            self.assertEqual([x["model_node_elapsed_s"] for x in data],[1.25,.5])
            self.assertEqual([x["graph_usage_input_tokens_cumulative"] for x in data],[121,322])
            for row in data:
                self.assertEqual(set(row),{
                    "protocol","request_idx","model_node_elapsed_s",
                    "graph_usage_input_tokens_cumulative",
                    "graph_usage_output_tokens_cumulative",
                    "graph_usage_requests_cumulative","outcome"})
            self.assertNotIn("password",p.read_text())
            self.assertNotIn("prompt",p.read_text())
            self.assertNotIn("tool",json.dumps(data[1]))

    def test_error_and_malformed_time_fail_closed_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stamps=iter([3.,2.])
            probe=ApiLatencyProbe(root/"artifacts"/"metric.jsonl",clock=lambda:next(stamps))
            with self.assertRaisesRegex(ValueError,"START_MISSING"):
                probe.finish_request()
            probe.begin_request()
            with self.assertRaisesRegex(ValueError,"MONOTONIC_DURATION"):
                probe.finish_request()
            self.assertEqual(probe.sequence,0)
            self.assertFalse(probe.destination.exists())

    def test_unknown_usage_is_null_and_double_begin_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stamps=iter([3.,4.])
            probe=ApiLatencyProbe(root/"artifacts"/"metric.jsonl",clock=lambda:next(stamps))
            probe.begin_request()
            with self.assertRaisesRegex(ValueError,"OVERLAPPING"):
                probe.begin_request()
            rec=probe.finish_if_pending(outcome="error")
            self.assertEqual(rec["outcome"],"error")
            self.assertIsNone(rec["graph_usage_output_tokens_cumulative"])
            self.assertIsNone(probe.finish_if_pending())
            self.assertEqual(probe.sequence,1)


if __name__=="__main__":
    unittest.main()
