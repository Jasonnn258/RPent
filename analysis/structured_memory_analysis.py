"""Structured Global Memory v1 — paired analysis (Baseline vs Structured).

For every run in analysis/structured_memory_runs.csv, standard metrics come from
progress_gate_analysis.analyze_dir (turns / tokens / perc / act / maxred /
success). Structured-arm metrics (fired rules, injections, recovery, phase
sequence, mem reads) are replayed deterministically from each run's tool stream
through the same PhaseTracker engine — so the baseline reused rows get an
apples-to-apples "would-have-fired" rule engagement, identical to what the live
harness computes for the structured arm.

The paired comparison is by (task, seed): baseline repeat-1 (reused progress-gate
rows) vs structured repeat-1.

Writes:
  analysis/structured_memory_paired.csv    — one row per (task, seed, arm)
  analysis/structured_memory_report.md     — aggregates + highlights

CLI: python structured_memory_analysis.py
"""
import csv, os, re, json, sys, datetime, statistics, collections

ROOT = "/hw-tbo/yjx/workspace/RPent"
RUNS_CSV = os.path.join(ROOT, "analysis", "structured_memory_runs.csv")
PAIRED_CSV = os.path.join(ROOT, "analysis", "structured_memory_paired.csv")
REPORT_MD = os.path.join(ROOT, "analysis", "structured_memory_report.md")
RULES_PATH = os.path.join(ROOT, "analysis", "structured_rules_v1.json")
MEMORY_DIR = os.path.join(ROOT, "resources", "libero", "memory")

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import progress_gate_analysis as pga  # noqa: E402
from rpent.memory.structured import PhaseTracker, load_rules  # noqa: E402
from rpent.memory.schema import PHASE_ORDER  # noqa: E402

_TURN_RE = re.compile(r"=== turn (\d+)/\d+ ===")
_TOOL_RE = re.compile(r"\[tool>\] (\w+)(?:\((\{.*\})\))?", re.DOTALL)

#: Tool calls that are semantically out of place for the current phase — a
#: conservative proxy for "wrong phase jumps" (e.g. re-opening perception in
#: P_verify, or re-grasping after placing).
FORBIDDEN = {
    "P_init": {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
               "set_gripper", "rotate_wrist", "rotate_pitch"},
    "P_look": {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
               "set_gripper", "rotate_wrist", "rotate_pitch"},
    "P_transport": {"pi0_pick", "pi0_doubled", "release"},
    "P_grasp": {"move_to", "move_pose", "pi0_doubled", "release"},
    "P_place": {"move_to", "move_pose", "pi0_pick"},
    "P_verify": {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
                 "segment", "back_project", "read_image", "view_driver_state",
                 "view_camera_meta", "set_gripper", "rotate_wrist",
                 "rotate_pitch", "read_text_file", "write_text_file", "list_dir"},
}


def _tool_stream(d):
    """Return list of (turn, name, args) from run.log, preserving order."""
    stream = []
    turn = 0
    if not os.path.exists(os.path.join(d, "run.log")):
        return stream
    for line in open(os.path.join(d, "run.log"), errors="ignore"):
        m = _TURN_RE.search(line)
        if m:
            turn = int(m.group(1))
            continue
        m2 = _TOOL_RE.search(line)
        if m2:
            name, args_raw = m2.group(1), m2.group(2)
            try:
                args = json.loads(args_raw) if args_raw else {}
            except Exception:
                args = {}
            stream.append((turn, name, args))
    return stream


def replay_run(d, task, max_turns=40):
    """Replay a run's tool stream through the PhaseTracker; return metrics.

    Faithful to the live harness: ``current_block`` is called once per TURN
    (after all tools in that turn), exactly like ``_solve``. Deterministic — for
    structured rows this equals structured_metrics.json (cross-checked in tests).
    """
    rules = [r for r in load_rules(RULES_PATH) if r.applies_to_task(task)]
    tr = PhaseTracker(rules, task=task, max_turns=max_turns, memory_dir=MEMORY_DIR)
    stream = _tool_stream(d)
    # group tools by turn (tools before any turn marker get synthetic turn 1)
    by_turn: dict[int, list[tuple[str, dict]]] = collections.defaultdict(list)
    for turn, name, args in stream:
        by_turn[turn or 1].append((name, args))
    off_phase = 0
    for turn in sorted(by_turn):
        for name, args in by_turn[turn]:
            phase_before = tr.current_phase()
            if name in FORBIDDEN.get(phase_before, set()):
                off_phase += 1
            tr.on_tool_call(name, args)
        block = tr.current_block(turn)
        if block is not None:
            tr.mark_injected()
    snap = tr.snapshot()
    snap["off_phase_actions"] = off_phase
    snap["tool_calls_total"] = len(stream)
    return snap


def phase_regressions(snap):
    """Backward phase transitions in the (monotonic-by-construction) sequence.

    Always 0 for the forward-only phase model; kept as an explicit, cheap check.
    """
    seq = snap["phase_sequence"]
    return sum(1 for a, b in zip(seq, seq[1:]) if PHASE_ORDER[a] > PHASE_ORDER[b])


def structured_row(d, task, m):
    """Merge standard + replayed structured metrics into one flat dict."""
    snap = replay_run(d, task)
    return {
        "success": m["success"],
        "turns": m["turns"],
        "planner_calls": m["planner_calls"],
        "tokens": m["tokens"],
        "perc": m["perc"],
        "act": m["act"],
        "maxred": m["maxred"],
        "env_steps": m["env_steps"],
        "wall_s": m["wall_s"],
        "final_phase": snap["final_phase"],
        "injections": snap["injections"],
        "injection_tokens_approx": snap["injection_tokens_approx"],
        "fired_rules": json.dumps(snap["fired_rules"], ensure_ascii=False),
        "n_fired": len(snap["fired_rules"]),
        "recovery_success": sum(1 for v in snap["recovery_success"].values() if v),
        "recovery_fail": sum(1 for v in snap["recovery_success"].values() if not v),
        "mem_reads": len(snap["mem_reads"]),
        "off_phase_actions": snap["off_phase_actions"],
        "phase_regressions": phase_regressions(snap),
        "finish_called": snap["finish_called"],
    }


def load_paired():
    if not os.path.exists(RUNS_CSV):
        print(f"missing {RUNS_CSV}")
        return []
    rows = []
    for r in csv.DictReader(open(RUNS_CSV)):
        d = r["dir"]
        task = str(r["task"])
        m = pga.analyze_dir(d) if os.path.isdir(d) else None
        if m is None:
            continue
        base = {k: r.get(k) for k in ("ts", "stage", "suite", "task", "seed", "cond", "repeat", "dir")}
        base.update(structured_row(d, task, m))
        base["rules_ver"] = r.get("rules_ver", "")
        rows.append(base)
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def _fmt(x, suf=""):
    return "—" if x is None else f"{x:g}{suf}"


def write_paired(rows):
    cols = ["task", "seed", "cond", "repeat", "dir", "success", "turns",
            "planner_calls", "tokens", "perc", "act", "maxred", "env_steps",
            "wall_s", "final_phase", "injections", "injection_tokens_approx",
            "fired_rules", "n_fired", "recovery_success", "recovery_fail",
            "mem_reads", "off_phase_actions", "phase_regressions", "finish_called"]
    with open(PAIRED_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})
    return PAIRED_CSV


def write_report(rows):
    lines = ["# Structured Global Memory v1 — Baseline vs Structured\n"]
    lines.append(f"_updated {datetime.datetime.now().isoformat(timespec='seconds')}_\n")
    lines.append(f"paired runs: baseline={sum(1 for r in rows if r['cond']=='baseline')} "
                 f"structured={sum(1 for r in rows if r['cond']=='structured')} "
                 f"(reused progress-gate baseline repeat-1 + 3 fresh gate-off spot-checks)\n")
    lines.append(f"rules: `{RULES_PATH}` (v1, 9 rules) | phase model: "
                 f"P_init→P_look→P_transport→P_grasp→P_place→P_verify\n")

    def agg(rows, keys):
        out = {}
        for k in keys:
            out[k] = mean([r[k] for r in rows])
        return out

    metric_keys = ["turns", "planner_calls", "tokens", "perc", "act", "maxred",
                   "mem_reads", "n_fired", "recovery_success", "recovery_fail",
                   "injections", "off_phase_actions"]

    # --- paired-by-seed comparison per task + overall -----------------------
    for task in ("0", "7", "9", "all"):
        if task == "all":
            bl = [r for r in rows if r["cond"] == "baseline"]
            st = [r for r in rows if r["cond"] == "structured"]
        else:
            bl = [r for r in rows if r["cond"] == "baseline" and r["task"] == task]
            st = [r for r in rows if r["cond"] == "structured" and r["task"] == task]
        if not bl or not st:
            continue
        # paired by seed
        seeds = sorted({r["seed"] for r in bl} & {r["seed"] for r in st})
        paired = []
        for s in seeds:
            b = next((r for r in bl if r["seed"] == s), None)
            g = next((r for r in st if r["seed"] == s), None)
            if b is not None and g is not None:
                paired.append((b, g))
        sr_bl = sum(r["success"] for r in bl) / len(bl)
        sr_st = sum(r["success"] for r in st) / len(st)
        lines.append(f"\n## {'Overall' if task == 'all' else 'Task ' + task}\n")
        lines.append(f"| metric | baseline | structured | delta |\n|---|---|---|---|\n")
        lines.append(f"| n | {len(bl)} | {len(st)} | |\n")
        lines.append(f"| SR | {sr_bl:.0%} | {sr_st:.0%} | "
                     f"{sr_st - sr_bl:+.0%} |\n")
        ab = agg(bl, metric_keys)
        as_ = agg(st, metric_keys)
        for k in metric_keys:
            d = (as_[k] - ab[k]) if (ab[k] is not None and as_[k] is not None) else None
            lines.append(f"| {k} | {_fmt(ab[k])} | {_fmt(as_[k])} | {_fmt(d, '') if d is not None else '—'} |\n")

        # paired per-seed detail (key columns only)
        lines.append(f"\nper-seed (paired):\n")
        lines.append(f"| seed | base SR | str SR | base turns | str turns | base fired | str fired | base memrd | str memrd |\n|---|---|---|---|---|---|---|---|---|\n")
        for b, g in paired:
            lines.append(
                f"| {b['seed']} | {int(b['success'])} | {int(g['success'])} | "
                f"{_fmt(b['turns'])} | {_fmt(g['turns'])} | {_fmt(b['n_fired'])} | "
                f"{_fmt(g['n_fired'])} | {_fmt(b['mem_reads'])} | {_fmt(g['mem_reads'])} |\n")

    # --- fired-rule engagement -----------------------------------------------
    lines.append(f"\n## Rule engagement (fires per run, avg)\n")
    lines.append(f"| rule | baseline | structured |\n|---|---|---|\n")
    bl = [r for r in rows if r["cond"] == "baseline"]
    st = [r for r in rows if r["cond"] == "structured"]
    all_ids = sorted({rid for r in bl + st for rid in json.loads(r["fired_rules"])})
    for rid in all_ids:
        cb = mean([sum(1 for x in json.loads(r["fired_rules"]) if x == rid) for r in bl])
        cs = mean([sum(1 for x in json.loads(r["fired_rules"]) if x == rid) for r in st])
        lines.append(f"| {rid} | {_fmt(cb)} | {_fmt(cs)} |\n")

    with open(REPORT_MD, "w") as f:
        f.write("\n".join(lines))
    return REPORT_MD


def main():
    rows = load_paired()
    if not rows:
        print("no run rows to analyze")
        return
    write_paired(rows)
    rep = write_report(rows)
    print(f"rows={len(rows)} -> {PAIRED_CSV}, {REPORT_MD}")


if __name__ == "__main__":
    main()
