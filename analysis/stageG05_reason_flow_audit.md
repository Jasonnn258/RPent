# Stage G0.5 — Trigger-Reason Flow Audit (§4)

_written 2026-09-21, before any G0.5 implementation. Source:
`rpent/memory/retrieval.py` @ 9f048af (G0-audit batch)._

The trigger reason currently flows through THREE separable channels. G0
varied channel 2 (query composition) but never channel 3 (planner-visible
context) — which is why D's gain cannot yet be attributed.

## Current data flow (per fire)

```
tool result ──► TRIGGER DECISION (channel 1)
                 _v1_rules_for() / _progress_observe() / baseline rules
                 reason string R computed ──► queued fire
                                                │
                ┌───────────────────────────────┤
                ▼                               ▼
   RETRIEVAL QUERY (channel 2)      PLANNER CONTEXT (channel 3)
   query_mode=native:               _block(R, top3) header ALWAYS:
     q = obs + " | " + R              "[DECISION-POINT MEMORY RECALL]
     Q3 reason term = toks(R)          (turn N; trigger: R)"
   query_mode=common (G0-B):         + "Long-term experience retrieved
     q = obs only                      as possibly relevant RIGHT NOW…"
     Q3 reason term = {}             + top-3 cards (id / title /
                                      applies_when / How to apply / Falsify)
```

## Where the reason appears, per arm family (pre-G0.5)

| channel | v1 (native) | v1_per_result B | **G0-D** | progress C/E | T2/T3 |
|---|---|---|---|---|---|
| 1 trigger decision | R | R | R | R | synthetic R |
| 2 retrieval query | **R in text + Q3 term** | **R in text + Q3 term** | not present (common) | native: R / common: not | native: R |
| 3 planner block header | **R** | **R** | **R** | **R** | **R** |

Key facts:

- The reason enters the PLANNER-VISIBLE block header in **every** arm that
  has ever run (all of Stage B/C/G0) — `_block()` at retrieval.py:922-938
  renders `(turn {self.turn}; trigger: {reason})`, followed by a fixed
  framing line ("Long-term experience retrieved as possibly relevant RIGHT
  NOW. This is context, not an instruction — judge each card against the
  current scene state; ignore what does not apply.").
- G0's "common" query removed R from channel 2 only. So G0-D = {R in
  decision, R NOT in query, R in planner block, cards present}.
- No arm has ever separated channels 3's sub-parts (reason vs cards) from
  channel 2. G0.5 does exactly that.
- The card BODY text (applies_when/how_to/falsify) is identical in every
  arm that injects cards; only the header and query differ.

## G0.5 arm → channel configuration

| arm | ch1 decision | ch2 query | ch3 planner block |
|---|---|---|---|
| P0 none | R (fires logged) | not run | nothing injected |
| P1 reason_only | R | not run | "[DECISION-POINT CHECK] trigger reason: R + re-evaluate line" |
| P2 generic_refresh | R | not run | frozen reorientation text (no R, no cards) |
| P3 memory_only | R | NEUTRAL (common) | "[DECISION-POINT MEMORY CONTEXT] …judged against observable state" + top-3 cards, **no R anywhere** |
| P4 full (= G0-D) | R | NEUTRAL (common) | "[DECISION-POINT MEMORY RECALL] (trigger: R)" + top-3 cards |

## Implementation surfaces (for §18)

- channel 2 knob exists: `RPENT_MEMORY_QUERY_MODE` (common/native).
  New explicit alias `RPENT_MEMORY_QUERY_REASON=0/1` validated against it
  (0↔common, 1↔native; mismatch fails fast).
- channel 3 knob is NEW: `RPENT_MEMORY_BLOCK_REASON=0/1` (default 1 =
  historical header). Coarse switch `RPENT_MEMORY_INJECTION_MODE`
  ∈ {full, memory_only, reason_only, generic_refresh, none} (default
  full = byte-identical historical behavior — every old mode ignores it).
- channel 1 is untouched: same `v1_per_result` trigger in all five arms
  (§3: per-result capture is now an engineering constant, not a variable).
