#!/usr/bin/env python
"""replay_b2_offline.py — replay real episode tool streams through B2.

Feeds the recorded (command, result) sequence from an episode's
``states.json`` plus its ``segments/*.json`` artifacts into
``TransitionVerifier`` and prints every verdict. Purely offline: no env,
no model, no oracle — the same payloads the planner saw live.

Usage:
  python scripts/replay_b2_offline.py <episode_dir> [<episode_dir> ...]

An episode dir with a transcript_*.json (tool_use inputs + tool results)
replays from the transcript; older dirs fall back to states.json
command/result records.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpent.memory.stv import TransitionVerifier  # noqa: E402


class PhaseApprox:
    """Cheap phase stand-in: recompute the SM1 phase from tool counts."""

    def __init__(self):
        from rpent.memory.structured import ACTION_TOOLS, PERCEPTION_TOOLS

        self.action = ACTION_TOOLS
        self.perception = PERCEPTION_TOOLS
        self.counts = {}

    def current_phase(self):
        c = self.counts
        if c.get("release", 0) + c.get("pi0_doubled", 0) >= 2:
            return "P_verify"
        if c.get("release", 0) + c.get("pi0_doubled", 0) >= 1:
            return "P_place"
        if c.get("pi0_pick", 0) >= 1:
            return "P_grasp"
        if c.get("move_to", 0) + c.get("move_pose", 0) >= 1:
            return "P_transport"
        if sum(c.get(t, 0) for t in self.perception) >= 1:
            return "P_init"
        return "P_init"

    def on_call(self, name):
        if name in self.action or name in self.perception:
            self.counts[name] = self.counts.get(name, 0) + 1


def _first_json(text: str) -> str:
    """Strip live-appended verdict lines ([b2]/[ovpm] injected AFTER the
    result JSON) — the first JSON object is the raw tool result."""
    try:
        obj, _ = json.JSONDecoder().raw_decode(text.lstrip())
        return json.dumps(obj)
    except ValueError:
        return text


def transcript_stream(d: Path):
    """(name, kwargs, result_text) stream from a transcript_*.json: assistant
    tool_use inputs paired with the following role=tool results by call id."""
    tpath = next(d.glob("transcript_*.json"))
    t = json.loads(tpath.read_text())
    pending: dict[str, tuple[str, dict]] = {}
    for m in t.get("messages", []):
        if m.get("role") == "assistant":
            for b in m.get("content", []):
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    pending[b.get("id")] = (
                        b.get("name", ""), dict(b.get("input") or {}))
        elif m.get("role") == "tool":
            name = m.get("name") or ""
            call = pending.pop(m.get("tool_call_id"), None)
            kwargs = call[1] if call else {}
            yield (call[0] if call else name), kwargs, _first_json(
                str(m.get("content", "")))


def replay_transcript(ep_dir: str) -> dict:
    d = Path(ep_dir)
    task = ""
    m = d.name.split("_t")
    task = m[1].split("_")[0] if len(m) > 1 else ""
    ph = PhaseApprox()
    v = TransitionVerifier(tracker=ph, task=task)
    n_lines = 0
    for name, kwargs, text in transcript_stream(d):
        if not name:
            continue
        ph.on_call(name)
        line = v.observe_result(name, kwargs, text, phase=ph.current_phase())
        if line:
            n_lines += 1
            print(f"  [{name}] {line}")
    snap = v.snapshot(success=False)
    print(f"  metrics: S={snap['n_confirmed_success']} "
          f"F={snap['n_confirmed_failure']} U={snap['n_uncertain']} "
          f"fp_caught={snap['false_positive_caught']} "
          f"observe={snap['n_observe_directives']} "
          f"obeyed={snap['n_observe_obeyed']} "
          f"reason={snap['n_reason_escalations']} lines={n_lines}")
    print(f"  resolutions: {snap['uncertain_resolutions']}")
    return snap


def replay(ep_dir: str) -> dict:
    d = Path(ep_dir)
    if next(d.glob("transcript_*.json"), None) is not None:
        return replay_transcript(ep_dir)
    steps = json.loads((d / "states.json").read_text())
    segs = []
    segdir = d / "segments"
    if segdir.is_dir():
        for f in sorted(segdir.glob("segment_*.json")):
            blob = json.loads(f.read_text())
            blob["_file"] = f.name
            segs.append(blob)

    task = ""
    m = d.name.split("_t")
    task = m[1].split("_")[0] if len(m) > 1 else ""
    ph = PhaseApprox()
    v = TransitionVerifier(tracker=ph, task=task)

    pending_segs = list(segs)
    n_lines = 0
    for s in steps:
        cmd = s.get("command") or {}
        name = cmd.get("action") or cmd.get("name")
        if not name:
            continue
        ph.on_call(name)
        kwargs = {k: w for k, w in cmd.items() if k not in ("action", "name")}
        res = s.get("result")
        text = json.dumps(res) if res is not None else "{}"
        line = v.observe_result(name, kwargs, text, phase=ph.current_phase())
        if line:
            n_lines += 1
            print(f"  [{name}] {line}")
        # segments recorded against this step replay right after it
        for blob in list(pending_segs):
            if blob.get("source_step") == s.get("step_idx"):
                prompt = blob.get("prompt") or ""
                payload = json.dumps(
                    {"found": blob.get("found"),
                     "world_xyz": blob.get("world_xyz"),
                     "score": blob.get("score")}
                )
                line = v.observe_result(
                    "segment", {"prompt": prompt} if prompt else {},
                    payload, phase=ph.current_phase())
                pending_segs.remove(blob)
                if line:
                    n_lines += 1
                    print(f"  [segment:{prompt[:24]}] {line}")
    for blob in pending_segs:  # trailing segments
        prompt = blob.get("prompt") or ""
        line = v.observe_result(
            "segment", {"prompt": prompt} if prompt else {},
            json.dumps({"found": blob.get("found"),
                        "world_xyz": blob.get("world_xyz")}),
            phase=ph.current_phase())
        if line:
            n_lines += 1
            print(f"  [segment:{prompt[:24]}] {line}")

    snap = v.snapshot(success=False)
    print(f"  metrics: S={snap['n_confirmed_success']} "
          f"F={snap['n_confirmed_failure']} U={snap['n_uncertain']} "
          f"fp_caught={snap['false_positive_caught']} "
          f"observe={snap['n_observe_directives']} "
          f"reason={snap['n_reason_escalations']} lines={n_lines}")
    return snap


def main():
    for ep in sys.argv[1:]:
        print(f"== {Path(ep).name}")
        replay(ep)


if __name__ == "__main__":
    main()
