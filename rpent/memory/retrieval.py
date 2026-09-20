"""Decision-point long-term memory recall (Stage B1 arms B2/B3).

Gate: ``RPENT_MEMORY_TRIGGER=1``. Rank method: ``RPENT_MEMORY_RANK`` in
{"Q0_FIXED", "Q3"} — both are FROZEN ports of the Stage A offline benchmark
(``scripts/memory_stagea_benchmark.py``); weights and rules must not be
tuned against online results (experiment discipline).

The component watches primitive/perception tool results, evaluates a frozen
generic trigger at each turn boundary, and on fire retrieves the top-3 cards
which the planner receives as a SOFT context block (no enforcement — the
adoption question is exactly what Stage B measures). Every retrieval event
is logged to ``memory_events.jsonl`` in the episode output dir.

Trigger rules are task-id-free signals only (spec §3): they answer "should
long-term memory be consulted NOW", never "which memory".
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------------ frozen
# Tokenizer + phase map + scoring are verbatim ports of Stage A (frozen).
STOP = set("""a an the and or of to in on at for with by from into onto is are was
were be been being it its this that these those not no does do did over under
near after before while during than then so as if but per via up down out off
you your we they he she i me my their them us has have had can could should
would may might will shall must""".split())

PHASE_KEYWORDS = {
    "P_look": ["segment", "label", "prompt", "ground", "disambiguation",
               "identity", "readable rgb", "brand"],
    "P_grasp": ["grasp", "pick", "grip", "closure", "regrasp", "handle",
                "visual grasp evidence", "carry"],
    "P_transport": ["reach", "wall", "move", "stall", "pitch", "offset",
                    "hang", "workspace"],
    "P_place": ["release", "seat", "insertion", "placement", "place",
                "container", "rim", "drop", "descend", "basket", "cavity",
                "leaned", "wedge"],
    "P_verify": ["predicate", "terminated", "verify", "confirmation",
                 "retreat", "settle", "watching libero_terminated"],
}

PRIMITIVES = ("pi0_pick", "pi0_doubled", "move_to", "move_pose", "release",
              "set_gripper", "rotate_wrist", "rotate_pitch")
PERCEPTION = ("segment", "back_project", "detect")

# Frozen cooldown policy: no trigger within 2 boundaries of the previous one,
# at most 6 retrievals per episode, none before the first primitive action,
# none on memory-file tools.
COOLDOWN_BOUNDARIES = 2
MAX_TRIGGERS_PER_EPISODE = 6

# Q3 structured-rerank weights — FROZEN from Stage A (do not tune online).
W_SEMANTIC = 2.0
W_APPLIES = 0.6
W_SYMPTOM = 0.4
W_ACTION = 0.5
W_PHASE = 0.4


def toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower())
            if w not in STOP and len(w) > 2}


def load_cards() -> dict[str, dict]:
    cards: dict[str, dict] = {}
    gdir = REPO / "resources" / "libero" / "global"
    for f in sorted(gdir.glob("*.md")):
        t = f.read_text()
        m = re.search(r"^---\n(.*?)\n---", t, re.S)
        fm = m.group(1) if m else ""

        def g(k: str) -> str:
            mm = re.search(rf"^{k}:\s*(.+)$", fm, re.M)
            return mm.group(1).strip() if mm else ""

        cards[f.stem] = {
            "id": f.stem,
            "title": g("title"),
            "kind": g("kind"),
            "applies_when": g("applies_when"),
            "symptom": g("symptom"),
            "how_to": (re.search(r"\*\*How to apply:\*\*(.*?)(?:\*\*Falsify:|\Z)",
                                 t, re.S) or ["", ""])[1].strip()[:400],
            "falsify": (re.search(r"\*\*Falsify:\*\*(.*?)(?:\*\*Related:|\Z)",
                                  t, re.S) or ["", ""])[1].strip()[:200],
        }
    return cards


def load_index() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for ln in (REPO / "resources" / "libero" / "MEMORY.md").read_text(
                ).splitlines():
            m = re.match(r"- \[(.+?)\]\(global/(\S+?)\.md\) — (.+)$", ln)
            if m:
                out[m.group(2)] = f"{m.group(1)} {m.group(3)}"
    except OSError:
        pass
    return out


def card_phases(card: dict) -> set[str]:
    text = " ".join([card["title"], card["applies_when"],
                     card["symptom"]]).lower()
    return {p for p, kws in PHASE_KEYWORDS.items()
            if any(k in text for k in kws)}


class _Embedder:
    """Lazy local bge-small-en-v1.5 (CPU) — same encoder as Stage A."""

    def __init__(self) -> None:
        self._net = None
        self._tok = None

    def _load(self):
        if self._net is None:
            os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
            import torch
            from transformers import AutoModel, AutoTokenizer
            name = "BAAI/bge-small-en-v1.5"
            self._torch = torch
            self._tok = AutoTokenizer.from_pretrained(name)
            self._net = AutoModel.from_pretrained(name)
            self._net.eval()
        return self._torch

    def embed(self, texts: list[str]) -> list[list[float]]:
        torch = self._load()
        with torch.no_grad():
            outs = []
            for i in range(0, len(texts), 32):
                batch = texts[i:i + 32]
                enc = self._tok(batch, padding=True, truncation=True,
                                max_length=256, return_tensors="pt")
                h = self._net(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).float()
                v = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
                v = torch.nn.functional.normalize(v, dim=1)
                outs.extend(v.tolist())
            return outs

    @staticmethod
    def cos(a: list[float], b: list[float]) -> float:
        dot = na = nb = 0.0
        for x, y in zip(a, b):
            dot += x * y
            na += x * x
            nb += y * y
        return dot / ((na * nb) ** 0.5 + 1e-9)


class DecisionMemory:
    """Frozen trigger + soft retrieval + event logging for one episode.

    mode="v1" (default, RPENT_MEMORY_TRIGGER=1): the frozen Stage B1
    boundary trigger — DO NOT TOUCH (published behavior).

    mode="progress" (RPENT_MEMORY_TRIGGER=progress, Stage C3 arm O2): the
    Stage C2 frozen progress-aware rules (R1-R5), evaluated per tool result
    (queued and flushed at the next boundary).  Rules mirror
    scripts/memory_stagec2_benchmark.py exactly — including no
    first-primitive gate (the C2 offline replay had none) and the frozen
    thresholds MOVE_EPS=0.005 / MOVE_ARRIVED=0.03 / LIFT_OK=0.05.
    """

    MOVE_EPS = 0.005
    MOVE_ARRIVED = 0.03
    LIFT_OK = 0.05

    def __init__(self, tracker: Any, mode: str = "v1") -> None:
        self.rank = os.environ.get("RPENT_MEMORY_RANK", "Q0_FIXED")
        self.mode = mode
        self.tracker = tracker
        self.cards = load_cards()
        self.index = load_index()
        self.ids = sorted(self.cards)
        # Stage G scale-test banks (stageG_subset_manifest.md §3): append
        # REAL library pages as extra retrieval entries. Additive only —
        # the 61 global cards and MEMORY.md index are never modified.
        extra_bank = os.environ.get("RPENT_MEMORY_EXTRA_BANK", "")
        if extra_bank:
            self._load_extra_bank(extra_bank)
        self.body = {c: " ".join([self.cards[c]["title"],
                                  self.cards[c]["applies_when"],
                                  self.cards[c]["symptom"],
                                  self.cards[c]["how_to"]])
                     for c in self.ids}
        self.phases = {c: card_phases(self.cards[c]) for c in self.ids}
        self._emb_card: dict[str, list[float]] | None = None
        self.events: list[dict] = []
        # per-episode signal state
        self.task_language = ""
        self.boundaries_since_trigger = COOLDOWN_BOUNDARIES
        self.triggers_fired = 0
        self.saw_primitive = False
        self.release_open = False  # release executed, predicate unconfirmed
        self.last_primitive = ""
        self.recent_primitives: list[str] = []
        self.phase_steps = 0
        self.last_phase = ""
        self.picks_failed = 0
        self.turn = 0
        self._last_result: dict | None = None
        self._fresh_result = False  # a result arrived since last boundary
        self._last_scores: list[float] = []
        self._embedder = _Embedder()
        # progress-mode state (Stage C2 frozen rules)
        self._queued_fire: str | None = None   # reason of the pending fire
        self._queued_result: dict | None = None
        self._queued_phase = ""  # tracker phase at queue time (G0-C)
        self._last_eef: list[float] | None = None  # last seen final_eef_pos
        self._consec_pick_fails = 0
        self._prev_prim_failed = False
        # Stage G baseline trigger params (frozen once on the DEV suite in
        # analysis/stageG_trigger_baseline_config.md; never tuned on final
        # suites). Only read when mode is a baseline mode.
        self.periodic_n = int(os.environ.get("RPENT_MEMORY_PERIODIC_N", "6"))
        self.mstuck_k = int(os.environ.get("RPENT_MSTUCK_K", "3"))
        self.mstuck_move_m = float(os.environ.get("RPENT_MSTUCK_MOVE_M",
                                                  "0.01"))
        self.mstuck_prog_m = float(os.environ.get("RPENT_MSTUCK_PROG_M",
                                                  "0.01"))
        self._boundary_count = 0
        # G0-D: window entries are (eef[:3], final_dist_m | None, target_key)
        # — final_dist_m progress is only comparable within ONE commanded
        # target (3-decimal key). Phase the window opened under is tracked
        # separately; a phase transition resets the window.
        self._mstuck_win: list[tuple[list[float], float | None,
                                     tuple]] = []
        self._mstuck_phase = ""
        # G0-A/B: query mode. "native" = historical behavior (query =
        # observation + trigger reason). "common" = WHEN/WHAT decoupled for
        # the causal audit: the query carries ONLY phase / trigger-result
        # action / trigger-result fields / task_language — the trigger
        # reason is logged but never enters retrieval scoring (lexical
        # query text AND the Q3 structured reason term).
        self.query_mode = os.environ.get("RPENT_MEMORY_QUERY_MODE",
                                         "native")
        if self.query_mode not in ("native", "common"):
            raise ValueError(
                f"RPENT_MEMORY_QUERY_MODE={self.query_mode!r} must be "
                "'native' or 'common' — fail fast rather than silently "
                "contaminating an arm")

    # ------------------------------------------------------------- observe
    def on_tool_result(self, name: str, content: str, is_error: bool) -> None:
        try:
            data = json.loads(content) if content.strip().startswith("{") else {}
        except json.JSONDecodeError:
            data = {}
        if data.get("task_language"):
            self.task_language = str(data["task_language"])
        if name in PRIMITIVES:
            self.saw_primitive = True
            self.last_primitive = name
            self.recent_primitives.append(name)
            self.recent_primitives = self.recent_primitives[-6:]
            self.phase_steps += 1
            if name == "pi0_pick" and data.get("success") is False:
                self.picks_failed += 1
            if name == "release":
                # predicate signal lives in the result; if the episode did
                # not terminate on the release, keep watching (T3).
                self.release_open = not data.get("libero_terminated", False)
        self._last_result = {"name": name, "data": data, "is_error": is_error,
                             "text": content[:400]}
        self._fresh_result = True
        if self.mode == "progress":
            self._progress_observe(name, data, is_error)
        elif self.mode == "v1_per_result":
            self._v1pr_observe(name, data, is_error)
        elif self.mode == "motion_stuck":
            self._mstuck_observe(name, data)

    # -------------------------------------- progress mode (Stage C2 frozen)
    def _progress_observe(self, name: str, data: dict, is_error: bool) -> None:
        """Evaluate the frozen C2 rules R1-R5 on THIS result (per-result
        evaluation — the fix for the v1 boundary-overwrite signal loss)."""
        fd = data.get("final_dist_m")
        is_move = name in ("move_to", "move_pose")
        # pre-eef for R2 = last known eef before this result updates it
        pre_eef = self._last_eef
        if isinstance(data.get("final_eef_pos"), list):
            self._last_eef = data["final_eef_pos"]
        reason = None
        if name in PERCEPTION and (data.get("found") is False
                                   or data.get("world_error")):
            reason = (f"perception_progress_failure: {name} produced no "
                      f"usable observation")
        elif is_move and isinstance(fd, (int, float)) and fd > self.MOVE_ARRIVED:
            tgt = data.get("target_xyz")
            dpre = None
            if pre_eef and isinstance(tgt, list) and len(tgt) >= 3:
                dpre = sum((a - b) ** 2
                           for a, b in zip(pre_eef[:3], tgt[:3])) ** 0.5
            if dpre is None or dpre - fd <= self.MOVE_EPS:
                reason = (f"move_stalled_no_progress: residual {fd:.3f} m, "
                          f"no eef progress toward target")
        elif name == "pi0_pick":
            lift = (data.get("diagnostics") or {}).get("post_min_ascent_m")
            # counter semantics mirror the frozen offline replay exactly:
            # increment on success=False, reset on anything else
            if data.get("success") is False:
                self._consec_pick_fails += 1
            else:
                self._consec_pick_fails = 0
            if data.get("success") is True \
                    and isinstance(lift, (int, float)) \
                    and lift < self.LIFT_OK:
                reason = ("pick_reported_success_but_no_lift: expected "
                          "ascent missing physically")
            elif data.get("success") is False \
                    and self._consec_pick_fails >= 2:
                reason = ("repeated_failed_picks: 2nd+ consecutive "
                          "failed pick, no grasp progress")
        elif name == "pi0_doubled" and data.get("success") is False \
                and data.get("libero_terminated") is not True:
            if self._prev_prim_failed:
                reason = ("recovery_no_change: contact skill failed after "
                          "another failed primitive")
        elif name == "release" and data.get("libero_terminated") is not True:
            reason = ("predicate_progress_missing: release executed but "
                      "task predicate not fired")
        if reason and self._queued_fire is None:
            self._queued_fire = reason
            self._queued_result = dict(self._last_result)
        # mirror the offline prev_prim_failed definition
        if name in PRIMITIVES:
            self._prev_prim_failed = data.get("success") is False or (
                is_move and isinstance(fd, (int, float))
                and fd > self.MOVE_ARRIVED)

    def _v1pr_observe(self, name: str, data: dict, is_error: bool) -> None:
        """G0-A experimental mode "v1_per_result": the frozen v1 trigger
        RULES (T1-T7, untouched) evaluated at EACH tool result's arrival,
        queued on hit, flushed at the next boundary.

        Isolates signal preservation: v1_original loses a hit whenever a
        later result arrives before the boundary (last-result-at-boundary
        overwrite); this mode keeps it. Queue/cooldown semantics are the
        PROGRESS flush semantics (drop-on-cooldown, drop at cap) so that
        v1_per_result -> progress differs by rule content only. The v1
        saw_primitive gate is applied at EVAL time (skipped until any
        primitive has run), mirroring where v1 applies it."""
        if not self.saw_primitive:
            return
        reason = self._v1_rules_for(name, data, is_error)
        if reason and self._queued_fire is None:
            self._queued_fire = reason
            self._queued_result = dict(self._last_result)
            self._queued_phase = self.last_phase

    # ------------------------------------------------------------- trigger
    def _trigger_reason(self) -> str | None:
        r = self._last_result
        if not r:
            return None
        return self._v1_rules_for(r["name"], r["data"], r["is_error"])

    def _v1_rules_for(self, name: str, data: dict,
                      is_error: bool) -> str | None:
        """The frozen v1 trigger rules T1-T7, evaluated for ONE result.

        G0-A: body is VERBATIM the historical _trigger_reason logic — same
        rules, same accumulated state reads (recent_primitives,
        release_open, picks_failed, phase_steps, tracker). The only change
        is that the result under judgment is an explicit argument, so
        v1_per_result can evaluate each result at arrival time.
        """
        if name not in PRIMITIVES + PERCEPTION:
            return None
        # T1 primitive failure
        if name == "pi0_pick" and data.get("success") is False:
            return "primitive_failure: pi0_pick reports no grasp"
        if name == "pi0_doubled" and data.get("success") is False:
            return "primitive_failure: contact skill did not terminate task"
        if name in ("move_to", "move_pose") and isinstance(
                data.get("final_dist_m"), (int, float)) \
                and data["final_dist_m"] > 0.03:
            return (f"primitive_failure: move stopped short "
                    f"({data['final_dist_m']:.3f} m residual)")
        if is_error:
            return f"primitive_failure: {name} returned error"
        # T2 pick ambiguous: reported success but near-zero lift
        if name == "pi0_pick" and data.get("success") is True:
            diag = data.get("diagnostics") or {}
            lift = diag.get("post_min_ascent_m")
            if isinstance(lift, (int, float)) and 0.0 <= lift < 0.05:
                return "pick_ambiguous: pick reports success but barely lifted"
        # T3 predicate stalled after release
        if name in PRIMITIVES and self.release_open \
                and not data.get("libero_terminated", False) \
                and name != "release":
            return ("predicate_stalled: actions continue after release but "
                    "the task predicate has not fired")
        # T4 repeated action without progress
        if len(self.recent_primitives) >= 3 \
                and len(set(self.recent_primitives[-3:])) == 1:
            return f"repeated_no_progress: {name} x3 in a row"
        if self.picks_failed >= 2:
            return "repeated_no_progress: repeated failed picks"
        # T5 perception insufficient
        if name in PERCEPTION:
            if data.get("found") is False:
                return "perception_insufficient: segmentation found no mask"
            if data.get("world_error"):
                return f"perception_insufficient: {data['world_error']}"
        # T6 recovery rule pending (SM1 signal)
        try:
            if self.tracker is not None and self.tracker.recovery_pending():
                return "recovery_pending: failure-recovery rule precondition met"
        except Exception:  # noqa: BLE001 - trigger must never break the run
            pass
        # T7 phase stalled: expected transition did not occur
        if self.phase_steps >= 8:
            return "phase_stalled: no phase transition across 8+ actions"
        return None

    # ------------------------------------------------------------ boundary
    def turn_boundary(self, turn: int) -> tuple[str, dict] | None:
        """Evaluate the frozen trigger; return (block, event) on fire."""
        self.turn = turn
        self.boundaries_since_trigger += 1
        self._boundary_count += 1
        if self.tracker is not None:
            ph = ""
            try:
                # PhaseTracker.current_phase is a METHOD (no @property) —
                # call it; a bare attribute fetch grabs the bound method,
                # which then poisons the event JSON and the Q3 query text.
                ph = self.tracker.current_phase()
            except Exception:  # noqa: BLE001
                ph = ""
            if ph and ph != self.last_phase:
                self.last_phase = ph
                self.phase_steps = 0
        if self.mode in ("progress", "v1_per_result"):
            return self._flush_boundary(turn)
        if self.mode == "periodic":
            return self._periodic_boundary(turn)
        if self.mode == "motion_stuck":
            if self._mstuck_win and self.last_phase != self._mstuck_phase:
                self._mstuck_win = []  # G0-D: phase transition resets window
            return self._mstuck_boundary(turn)
        if not self.saw_primitive or self.triggers_fired >= MAX_TRIGGERS_PER_EPISODE:
            return None
        if self.boundaries_since_trigger < COOLDOWN_BOUNDARIES:
            return None
        if not self._fresh_result:
            return None  # nothing new since the last boundary
        reason = self._trigger_reason()
        self._fresh_result = False
        if not reason:
            return None
        self.boundaries_since_trigger = 0
        self.triggers_fired += 1
        # one-shot resets so a signal does not re-fire forever
        self.picks_failed = 0
        self.phase_steps = 0
        self.release_open = False

        t0 = time.time()
        top, cand = self._retrieve(reason)
        latency_ms = (time.time() - t0) * 1000
        event = {
            "episode": "",  # filled at finalize from the output dir
            "task": os.environ.get("RPENT_TASK", ""),
            "turn": turn,
            "phase": self.last_phase,
            "last_action": self.last_primitive,
            "symptom": reason,
            "observation_summary": self._obs_summary(),
            "trigger_reason": reason,
            "trigger_mode": "v1",
            "query_mode": self.query_mode,
            "retrieval_method": self.rank,
            "candidate_memory_ids": cand,
            "retrieval_status": "MATCH" if top else "EMPTY",
            "retrieval_empty": not bool(top),
            "trigger_fired": True,
            "scores": [],
            "ranked_memory_ids": [],
            "top1_memory": "",
            "top3_memories": [],
            "retrieval_latency_ms": round(latency_ms, 2),
            "task_language": self.task_language,
            "planner_next_action": None,   # post-hoc, filled by analysis
            "planner_followed_top1": None,  # post-hoc
            "planner_followed_any_top3": None,  # post-hoc
            "verification_result": None,    # post-hoc
            "episode_result": None,        # post-hoc
        }
        # G0-E applies to the frozen v1 path too: every attempt is logged;
        # EMPTY writes the event but injects nothing. Policy unchanged.
        if not top:
            self.events.append(event)
            logger.info("[memrecall] turn=%s trigger=%s retrieval=EMPTY "
                        "(logged, no injection)", turn, reason)
            return None
        block = self._block(reason, top)
        event["scores"] = [round(s, 4) for s in self._last_scores]
        event["ranked_memory_ids"] = top
        event["top1_memory"] = top[0]
        event["top3_memories"] = top[:3]
        event["retrieval_tokens"] = len(block.split())
        event["planner_context_memory_ids"] = top[:3]
        self.events.append(event)
        logger.info("[memrecall] turn=%s trigger=%s top3=%s", turn, reason,
                    top[:3])
        return block, event

    def _flush_boundary(self, turn: int) -> tuple[str, dict] | None:
        """Flush a queued per-result fire. Shared by mode="progress"
        (Stage C2 frozen rules; no first-primitive gate — the offline
        replay had none) and mode="v1_per_result" (G0-A; the gate applies
        at eval time instead). Cooldown blocks DROP the fire rather than
        deferring it — the frozen progress semantics, adopted by
        v1_per_result so the two differ by rule content only."""
        if self.triggers_fired >= MAX_TRIGGERS_PER_EPISODE:
            self._queued_fire = None
            return None
        if self.boundaries_since_trigger < COOLDOWN_BOUNDARIES:
            self._queued_fire = None
            return None
        if not self._queued_fire:
            return None
        reason, qr = self._queued_fire, self._queued_result or {}
        phase = self._queued_phase or self.last_phase
        self._queued_fire = None
        self._queued_result = None
        self._queued_phase = ""
        self.boundaries_since_trigger = 0
        self.triggers_fired += 1
        t0 = time.time()
        obs = self._obs_summary_for(qr)
        # G0-B: common query = WHEN/WHAT decoupled — the reason never
        # enters the query (lexical text) or the structured reason term.
        reason_toks = toks(reason) if self.query_mode == "native" else set()
        q = " | ".join([obs, reason]) if self.query_mode == "native" \
            else obs
        top, cand = (self._q3(q, reason_toks, obs, qr.get("name", ""),
                              phase) if self.rank == "Q3"
                     else self._q0_fixed(q))
        latency_ms = (time.time() - t0) * 1000
        event = {
            "episode": "",
            "task": os.environ.get("RPENT_TASK", ""),
            "turn": turn,
            "phase": phase,
            "last_action": qr.get("name", ""),
            "symptom": reason,
            "observation_summary": obs,
            "trigger_reason": reason,
            "trigger_mode": self.mode,
            "query_mode": self.query_mode,
            "retrieval_method": self.rank,
            "candidate_memory_ids": cand,
            "retrieval_status": "MATCH" if top else "EMPTY",
            "retrieval_empty": not bool(top),
            "trigger_fired": True,
            "scores": [],
            "ranked_memory_ids": [],
            "top1_memory": "",
            "top3_memories": [],
            "retrieval_latency_ms": round(latency_ms, 2),
            "task_language": self.task_language,
            "planner_next_action": None,
            "planner_followed_top1": None,
            "planner_followed_any_top3": None,
            "verification_result": None,
            "episode_result": None,
        }
        # G0-E: EVERY trigger attempt is logged. An EMPTY retrieval writes
        # the event (retrieval_empty=True) but injects nothing.
        if not top:
            self.events.append(event)
            logger.info("[memrecall] turn=%s trigger=%s retrieval=EMPTY "
                        "(logged, no injection)", turn, reason)
            return None
        block = self._block(reason, top)
        event["scores"] = [round(s, 4) for s in self._last_scores]
        event["ranked_memory_ids"] = top
        event["top1_memory"] = top[0]
        event["top3_memories"] = top[:3]
        event["retrieval_tokens"] = len(block.split())
        event["planner_context_memory_ids"] = top[:3]
        self.events.append(event)
        logger.info("[memrecall] turn=%s trigger=%s top3=%s", turn, reason,
                    top[:3])
        return block, event

    # ------------------------------- Stage G baseline triggers (T2/T3)
    # Baselines ONLY (stageG_trigger_baseline_config.md). The decision rule
    # is the ONLY difference from the frozen modes: retrieval, injection
    # path, cooldown and per-episode cap are identical. The frozen v1/progress
    # code paths above are untouched.
    def _mstuck_observe(self, name: str, data: dict) -> None:
        """T3_MOTION_STUCK: generic spatial-stuck detector (G0-D hardened).
        Uses ONLY EEF displacement between consecutive move results and
        final_dist_m improvement — the latter comparable ONLY between two
        results commanded to the SAME target (target_xyz key, 3 decimals).
        No primitive-specific PICK/PLACE/PERCEPTION logic. Window resets
        on: a non-move primitive interleaved, a commanded-target change, a
        missing target (no progress anchor), or a phase transition (checked
        at the boundary). Evaluated only when a move result arrives."""
        if name in PRIMITIVES and name not in ("move_to", "move_pose"):
            self._mstuck_win = []   # pick/release/... between moves: reset
            return
        if name not in ("move_to", "move_pose"):
            return                  # perception/memory results: no reset
        eef = data.get("final_eef_pos")
        tgt = data.get("target_xyz")
        if not isinstance(eef, list) or len(eef) < 3:
            return
        if not isinstance(tgt, list) or len(tgt) < 3:
            self._mstuck_win = []   # no target -> no progress anchor
            return
        tkey = tuple(round(v, 3) for v in tgt[:3])
        if self._mstuck_win and self._mstuck_win[-1][2] != tkey:
            self._mstuck_win = []   # commanded target changed
        fd = data.get("final_dist_m")
        self._mstuck_win.append(
            (eef[:3], fd if isinstance(fd, (int, float)) else None, tkey))
        self._mstuck_win = self._mstuck_win[-self.mstuck_k:]
        if len(self._mstuck_win) == 1:
            self._mstuck_phase = self.last_phase
        if len(self._mstuck_win) < self.mstuck_k:
            return
        for (p0, d0, _t0), (p1, d1, _t1) in zip(self._mstuck_win,
                                                self._mstuck_win[1:]):
            disp = sum((a - b) ** 2 for a, b in zip(p0, p1)) ** 0.5
            if disp >= self.mstuck_move_m:
                return
            # window entries share tkey by construction; progress is
            # same-target by design. Unknown dist (None) -> cannot verify
            # progress, displacement evidence still stands (kept from the
            # frozen DEV calibration semantics).
            if d0 is not None and d1 is not None \
                    and d0 - d1 >= self.mstuck_prog_m:
                return  # real progress toward the commanded target
        if self._queued_fire is None:
            self._queued_fire = (f"motion_stuck: k={self.mstuck_k} "
                                 f"disp<{self.mstuck_move_m:.3f}m "
                                 f"prog<{self.mstuck_prog_m:.3f}m "
                                 f"same-target")
            self._queued_result = dict(self._last_result)
            self._queued_phase = self.last_phase
            self._mstuck_win = []  # window resets once a fire is queued

    def _periodic_boundary(self, turn: int) -> tuple[str, dict] | None:
        """T2_PERIODIC: fire every N-th turn boundary (a timer, blind to
        state). Ticks before the first primitive result are skipped."""
        if not self.saw_primitive or self._boundary_count % self.periodic_n:
            return None
        reason = (f"periodic_tick: boundary={self._boundary_count} "
                  f"N={self.periodic_n}")
        return self._baseline_fire(turn, reason,
                                   dict(self._last_result)
                                   if self._last_result else {},
                                   "periodic")

    def _mstuck_boundary(self, turn: int) -> tuple[str, dict] | None:
        """Flush a queued T3 fire at the boundary (drop-on-cooldown, like
        the frozen progress semantics)."""
        if not self._queued_fire:
            return None
        reason = self._queued_fire
        qr = self._queued_result or {}
        self._queued_fire = None
        self._queued_result = None
        self._queued_phase = ""
        return self._baseline_fire(turn, reason, qr, "motion_stuck")

    def _baseline_fire(self, turn: int, reason: str, qr: dict,
                       mode_label: str) -> tuple[str, dict] | None:
        """Shared fire path for the Stage G baselines — same cooldown/cap/
        retrieval/logging semantics as the frozen modes (incl. G0-B query
        mode and G0-E attempt logging)."""
        if self.triggers_fired >= MAX_TRIGGERS_PER_EPISODE:
            return None
        if self.boundaries_since_trigger < COOLDOWN_BOUNDARIES:
            return None
        self.boundaries_since_trigger = 0
        self.triggers_fired += 1
        t0 = time.time()
        obs = self._obs_summary_for(qr)
        reason_toks = toks(reason) if self.query_mode == "native" else set()
        q = " | ".join([obs, reason]) if self.query_mode == "native" \
            else obs
        phase = self._queued_phase or self.last_phase
        top, cand = (self._q3(q, reason_toks, obs, qr.get("name", ""),
                              phase) if self.rank == "Q3"
                     else self._q0_fixed(q))
        latency_ms = (time.time() - t0) * 1000
        event = {
            "episode": "",
            "task": os.environ.get("RPENT_TASK", ""),
            "turn": turn,
            "phase": phase,
            "last_action": qr.get("name", ""),
            "symptom": reason,
            "observation_summary": obs,
            "trigger_reason": reason,
            "trigger_mode": mode_label,
            "query_mode": self.query_mode,
            "retrieval_method": self.rank,
            "candidate_memory_ids": cand,
            "retrieval_status": "MATCH" if top else "EMPTY",
            "retrieval_empty": not bool(top),
            "trigger_fired": True,
            "scores": [],
            "ranked_memory_ids": [],
            "top1_memory": "",
            "top3_memories": [],
            "retrieval_latency_ms": round(latency_ms, 2),
            "task_language": self.task_language,
            "planner_next_action": None,
            "planner_followed_top1": None,
            "planner_followed_any_top3": None,
            "verification_result": None,
            "episode_result": None,
        }
        if not top:
            self.events.append(event)
            logger.info("[memrecall] turn=%s trigger=%s retrieval=EMPTY "
                        "(logged, no injection)", turn, reason)
            return None
        block = self._block(reason, top)
        event["scores"] = [round(s, 4) for s in self._last_scores]
        event["ranked_memory_ids"] = top
        event["top1_memory"] = top[0]
        event["top3_memories"] = top[:3]
        event["retrieval_tokens"] = len(block.split())
        event["planner_context_memory_ids"] = top[:3]
        self.events.append(event)
        logger.info("[memrecall] turn=%s trigger=%s top3=%s", turn, reason,
                    top[:3])
        return block, event

    def _load_extra_bank(self, spec: str) -> None:
        """Append real library pages (G4 distractor banks) as retrieval
        entries. G0-F: IDs are NAMESPACED as extra::<dir>::<stem> so pages
        from different bank directories can never collide (the global 61
        card ids are untouched). Page frontmatter supplies task_language
        (used as title); the body supplies the lexical index line and the
        Q3 body text. No card content is edited; global cards keep their
        exact index lines."""
        n = 0
        for d in spec.split(":"):
            base = Path(d)
            if not base.is_dir():
                logger.warning("[memrecall] extra bank dir missing: %s", d)
                continue
            for p in sorted(base.glob("*.md")):
                cid = f"extra::{base.name}::{p.stem}"
                if cid in self.cards:
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except OSError:
                    continue
                fm, _, body = text.partition("\n---")
                card = {"id": cid, "kind": "suite_page", "dir": base.name,
                        "stem": p.stem,
                        "title": p.stem.replace("_", " "),
                        "applies_when": "", "symptom": "",
                        "falsify": ""}
                m = re.search(r"^task_language:\s*(.+)$", fm, re.M)
                if m:
                    card["title"] = m.group(1).strip()[:120]
                # same "how_to" key (and the same 400-char cap) as the
                # global cards, so _block() renders both uniformly.
                card["how_to"] = re.sub(r"\s+", " ", body).strip()[:400]
                self.cards[cid] = card
                self.index[cid] = (card["title"] + " " +
                                   card["how_to"])[:600]
                n += 1
        if n:
            self.ids = sorted(self.cards)
            self.body = {c: " ".join([self.cards[c]["title"],
                                      self.cards[c]["applies_when"],
                                      self.cards[c]["symptom"],
                                      self.cards[c]["how_to"]])
                         for c in self.ids}
            self.phases = {c: card_phases(self.cards[c]) for c in self.ids}
            self._emb_card = None
            logger.info("[memrecall] extra bank: +%d real pages -> %d "
                        "entries (namespaced extra::<dir>::<stem>)", n,
                        len(self.ids))

    # ------------------------------------------------------------ retrieval
    def _obs_summary(self) -> str:
        r = self._last_result
        keys = ("success", "libero_terminated", "final_dist_m", "found",
                "world_error", "min_gripper_opening")
        fields = {k: r["data"][k] for k in keys if k in r["data"]}
        return (f"phase={self.last_phase}; last action={self.last_primitive}; "
                f"result fields={fields}; task: {self.task_language[:110]}")

    def _obs_summary_for(self, r: dict) -> str:
        """Poor-format obs summary for a specific (queued) result — progress
        mode fires on the result that broke, not the last one seen."""
        data = r.get("data") or {}
        keys = ("success", "libero_terminated", "final_dist_m", "found",
                "world_error", "min_gripper_opening")
        fields = {k: data[k] for k in keys if k in data}
        return (f"phase={self.last_phase}; last action={r.get('name', '')}; "
                f"result fields={fields}; task: {self.task_language[:110]}")

    def _retrieve(self, reason: str) -> tuple[list[str], list[str]]:
        """v1 boundary retrieval. The v1 boundary fires on the LAST result,
        so the structured Q3 terms (obs text / action / phase) are that
        result's values — consistent with the G0-C explicit-state fix."""
        obs = self._obs_summary()
        reason_toks = toks(reason) if self.query_mode == "native" else set()
        q = " | ".join([obs, reason]) if self.query_mode == "native" \
            else obs
        if self.rank == "Q3":
            return self._q3(q, reason_toks, obs, self.last_primitive,
                            self.last_phase)
        return self._q0_fixed(q)

    def _q0_fixed(self, q: str) -> tuple[list[str], list[str]]:
        qt = toks(q) | toks(self.task_language)
        # G0-F: namespaced extra ids score by their STEM tokens only (the
        # extra::<dir>:: prefix contributes nothing); global cards, which
        # carry no "::", are scored exactly as before.
        scored = sorted(
            ((len(qt & (toks(self.index.get(c, self.cards[c]["title"]))
                        | toks(c.split("::")[-1].replace("-", " ")))), c)
             for c in self.ids),
            reverse=True)
        self._last_scores = [float(s) for s, _ in scored[:5]]
        top = [c for s, c in scored if s > 0][:3]
        return top, self.ids

    def _q3(self, q: str, reason_toks: set[str], obs_text: str,
            action: str, phase: str) -> tuple[list[str], list[str]]:
        """Q3 structured rerank — FROZEN weights / pool size / encoder /
        phase map (Stage A port, unchanged).

        G0-C: every structured term (observation tokens, action, phase)
        comes in EXPLICITLY from the result the trigger fired on, so a
        queued fire can no longer be rescored against a LATER result's
        state. Weights and the semantic pool are untouched."""
        if self._emb_card is None:
            vecs = self._embedder.embed([self.body[c] for c in self.ids])
            self._emb_card = dict(zip(self.ids, vecs))
        qv = self._embedder.embed([q])[0]
        sem = sorted(((self._embedder.cos(qv, self._emb_card[c]), c)
                      for c in self.ids), reverse=True)
        pool = sem[:20]
        cand = [c for _, c in pool]
        qt_obs = toks(obs_text)
        act = (action or "").lower().replace("pi0_", "")
        rescored = []
        for s, c in pool:
            card = self.cards[c]
            sc = (W_SEMANTIC * s
                  + W_APPLIES * len(qt_obs & toks(card["applies_when"]))
                  + W_SYMPTOM * len(reason_toks & toks(card["symptom"]))
                  + (W_ACTION if act and act in (
                      card["applies_when"] + " " + card["symptom"]).lower()
                     else 0.0)
                  + (W_PHASE if phase in self.phases[c] else 0.0))
            rescored.append((sc, c))
        rescored.sort(reverse=True)
        self._last_scores = [float(s) for s, _ in rescored[:5]]
        return [c for _, c in rescored[:3]], cand

    # ---------------------------------------------------------------- block
    def _block(self, reason: str, top: list[str]) -> str:
        lines = [
            "[DECISION-POINT MEMORY RECALL] "
            f"(turn {self.turn}; trigger: {reason})",
            "Long-term experience retrieved as possibly relevant RIGHT NOW. "
            "This is context, not an instruction — judge each card against "
            "the current scene state; ignore what does not apply.",
        ]
        for i, c in enumerate(top[:3], 1):
            card = self.cards[c]
            lines.append(
                f"{i}. [{card['id']}] {card['title']}\n"
                f"   applies_when: {card['applies_when'][:220]}\n"
                f"   How to apply: {card['how_to'][:280]}\n"
                f"   Falsify (do not use if true): {card['falsify'][:160]}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------- finalize
    def finalize(self, *, success: bool | None) -> None:
        try:
            from rpent.utils.logging import get_output_dir
            out = get_output_dir()
            for e in self.events:
                e["episode"] = out.name
                e["episode_result"] = success
        except Exception:  # noqa: BLE001
            return
        try:
            with open(out / "memory_events.jsonl", "w") as f:
                for e in self.events:
                    # default=str: instrumentation must never lose events to
                    # an unexpected field type again (2026-09-17 smoke incident)
                    f.write(json.dumps(e, ensure_ascii=False,
                                       default=str) + "\n")
            logger.info("[memrecall] wrote %d events", len(self.events))
        except Exception as e:  # noqa: BLE001 - never fail the run
            logger.warning("[memrecall] failed to write events: %s", e)
