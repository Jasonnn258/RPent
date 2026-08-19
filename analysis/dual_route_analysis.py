"""Structured Memory + Dual-Route Reasoning (SM2) — paired analysis.

Control  = Structured Memory only (reused SM1 structured repeat-1 rows, stored
           in dual_route_runs.csv as cond=structured repeat=1).
Treatment = Structured Memory + Dual Route (cond=dual_route repeat=1).

Standard metrics come from progress_gate_analysis.analyze_dir:
  model_calls = turns = count of `=== turn N/M ===` markers (fast steps emit no
                marker), tokens, perc, act, maxred.
Dual-route metrics are parsed from each run dir:
  fast_steps   = `[fast]` marker count
  turns_total  = model_calls + fast_steps   (fast steps consume the 40-step budget)
  redundant_streak = longest consecutive same-tool run over the `[tool>]` stream
                     (includes fast tools — release -> act, view_driver_state -> perc)
  slow_reasons = live structured_metrics.json (both arms gate structured memory on)
P_verify→success conversion = among runs whose phase_sequence contains P_verify,
the fraction that succeeded, per arm.

The 2 fixed-code structured spot-checks (cond=structured repeat=2, t7s2 / t0s5)
are excluded from pairing and used only as a Fix-A drift check against the reused
control at the same (task, seed).

Writes:
  analysis/dual_route_paired.csv
  analysis/dual_route_report.md

CLI: python dual_route_analysis.py
"""
import csv, os, re, json, sys, datetime, statistics, collections

ROOT = "/hw-tbo/yjx/workspace/RPent"
RUNS_CSV = os.path.join(ROOT, "analysis", "dual_route_runs.csv")
PAIRED_CSV = os.path.join(ROOT, "analysis", "dual_route_paired.csv")
REPORT_MD = os.path.join(ROOT, "analysis", "dual_route_report.md")

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import progress_gate_analysis as pga  # noqa: E402

_TURN_RE = re.compile(r"=== turn (\d+)/\d+ ===")
_TOOL_RE = re.compile(r"\[tool>\] (\w+)\(")
_FAST_RE = re.compile(r"\[fast\] (\w+)\((\{.*\})\)?", re.DOTALL)
_SLOW_RE = re.compile(r"\[slow\] reason=(\w+)")


# ------------------------------------------------------------ log parsing
def _name_stream(d):
    """Ordered tool names from `[tool>]` markers — model + fast tools."""
    names = []
    rl = os.path.join(d, "run.log")
    if not os.path.exists(rl):
        return names
    for line in open(rl, errors="ignore"):
        m = _TOOL_RE.search(line)
        if m:
            names.append(m.group(1))
    return names


def _fast_calls(d):
    """(name, args) pairs from `[fast]` markers, in order."""
    out = []
    rl = os.path.join(d, "run.log")
    if not os.path.exists(rl):
        return out
    for line in open(rl, errors="ignore"):
        m = _FAST_RE.search(line)
        if m:
            name, args_raw = m.group(1), m.group(2)
            args = {}
            if args_raw:
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}
            out.append((name, args))
    return out


def _slow_reasons_log(d):
    reasons = []
    rl = os.path.join(d, "run.log")
    if not os.path.exists(rl):
        return reasons
    for line in open(rl, errors="ignore"):
        m = _SLOW_RE.search(line)
        if m:
            reasons.append(m.group(1))
    return reasons


def redundant_streak(names):
    """Longest consecutive run of the same tool in the full [tool>] stream."""
    best = cur = 0
    prev = None
    for n in names:
        cur = cur + 1 if n == prev else 1
        prev = n
        best = max(best, cur)
    return best


# ------------------------------------------------------ live structured metrics
def live_metrics(d):
    """Parse the live structured_metrics.json (both arms gate structured on)."""
    p = os.path.join(d, "structured_metrics.json")
    if not os.path.exists(p):
        return {}
    try:
        m = json.load(open(p))
    except Exception:
        return {}
    seq = m.get("phase_sequence") or []
    rs = m.get("recovery_success") or {}
    return {
        "rules_ver": m.get("rules_ver", ""),
        "injections": m.get("injections", 0),
        "injection_tokens_approx": m.get("injection_tokens_approx", 0),
        "fired_rules": json.dumps(m.get("fired_rules", []), ensure_ascii=False),
        "n_fired": len(m.get("fired_rules", [])),
        "recovery_success": sum(1 for v in rs.values() if v),
        "recovery_fail": sum(1 for v in rs.values() if not v),
        "mem_reads": len(m.get("mem_reads", [])),
        "final_phase": m.get("final_phase", ""),
        "phase_sequence": json.dumps(seq, ensure_ascii=False),
        "reached_p_verify": "P_verify" in seq,
        "finish_called": bool(m.get("finish_called")),
        "fast_steps": m.get("fast_steps", 0) or 0,
        "slow_reasons": json.dumps(m.get("slow_reasons") or [], ensure_ascii=False),
    }


def _fast_kinds(fast_calls):
    kinds = collections.Counter()
    for name, args in fast_calls:
        if name == "finish":
            kinds[f"finish:{args.get('status', '?')}"] += 1
        else:
            kinds[name] += 1
    return kinds


def dual_row(d, task, m):
    """Merge standard + dual-route metrics into one flat dict."""
    fast = _fast_calls(d)
    names = _name_stream(d)
    model_calls = m["turns"]
    fast_steps = len(fast)
    kinds = _fast_kinds(fast)
    return {
        "success": m["success"],
        "model_calls": model_calls,
        "fast_steps": fast_steps,
        "turns_total": model_calls + fast_steps,
        "n_slow": len(_slow_reasons_log(d)),
        "tokens": m["tokens"],
        "perc": m["perc"],
        "act": m["act"],
        "maxred": m["maxred"],
        "redundant_streak": redundant_streak(names),
        "env_steps": m["env_steps"],
        "wall_s": m["wall_s"],
        "reason": m["reason"],
        "fast_vds": kinds.get("view_driver_state", 0),
        "fast_release": kinds.get("release", 0),
        "fast_finish_ok": kinds.get("finish:success", 0),
        "fast_finish_fail": kinds.get("finish:failure", 0),
        "fast_kinds": json.dumps(dict(kinds), ensure_ascii=False),
    }


# ------------------------------------------------------------------ load
def load_rows():
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
        base = {k: r.get(k) for k in ("ts", "stage", "suite", "task", "seed",
                                      "cond", "repeat", "dir", "result")}
        base.update(dual_row(d, task, m))
        base["rules_ver"] = r.get("rules_ver", "")
        rows.append(base)
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def _fmt(x, suf=""):
    return "—" if x is None else f"{x:g}{suf}"


def _sr(rs):
    return sum(r["success"] for r in rs) / len(rs) if rs else 0.0


# ------------------------------------------------------------------ write
def write_paired(rows):
    cols = ["task", "seed", "cond", "repeat", "dir", "result", "success",
            "model_calls", "fast_steps", "turns_total", "n_slow", "tokens",
            "perc", "act", "maxred", "redundant_streak", "env_steps",
            "final_phase", "phase_sequence", "injections",
            "injection_tokens_approx", "fired_rules", "n_fired",
            "recovery_success", "recovery_fail", "mem_reads",
            "fast_vds", "fast_release", "fast_finish_ok", "fast_finish_fail",
            "fast_kinds", "slow_reasons", "finish_called", "reached_p_verify"]
    with open(PAIRED_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})
    return PAIRED_CSV


def write_report(rows):
    ctrl = [r for r in rows if r["cond"] == "structured" and r["repeat"] == "1"]
    treat = [r for r in rows if r["cond"] == "dual_route"]
    spots = [r for r in rows if r["cond"] == "structured" and r["repeat"] == "2"]
    lines = ["# Structured Memory + Dual-Route Reasoning (SM2)\n"]
    lines.append(f"_updated {datetime.datetime.now().isoformat(timespec='seconds')}_\n")
    lines.append(f"paired runs: structured={len(ctrl)} dual_route={len(treat)} "
                 f"(+ {len(spots)} Fix-A spot-checks, drift check only)\n")
    lines.append(f"control = SM1 structured repeat-1 reused rows; treatment = "
                 f"RPENT_DUAL_ROUTE=1, same suite/tasks/seeds.\n")
    lines.append(f"Fast/Slow: fast steps never call the LLM; model_calls = `=== turn N/M ===` "
                 f"markers; turns_total = model_calls + fast_steps (fast steps consume the "
                 f"40-step budget).\n")

    def metric_table(title, c, t, keys):
        lines.append(f"\n## {title}\n")
        lines.append(f"| metric | structured | dual_route | delta |\n|---|---|---|---|\n")
        lines.append(f"| n | {len(c)} | {len(t)} | |\n")
        lines.append(f"| SR | {_sr(c):.0%} | {_sr(t):.0%} | {_sr(t) - _sr(c):+.0%} |\n")
        ac = {k: mean([r[k] for r in c]) for k in keys}
        at = {k: mean([r[k] for r in t]) for k in keys}
        for k in keys:
            d = (at[k] - ac[k]) if (ac[k] is not None and at[k] is not None) else None
            lines.append(f"| {k} | {_fmt(ac[k])} | {_fmt(at[k])} | "
                         f"{_fmt(d, '') if d is not None else '—'} |\n")

    keys = ["model_calls", "fast_steps", "turns_total", "perc", "act", "maxred",
            "redundant_streak", "tokens", "mem_reads", "n_fired",
            "recovery_success", "recovery_fail", "injections"]

    # --- overall -------------------------------------------------------
    metric_table("Overall", ctrl, treat, keys)

    # --- per task ------------------------------------------------------
    for task in ("0", "7", "9"):
        c = [r for r in ctrl if r["task"] == task]
        t = [r for r in treat if r["task"] == task]
        if not c or not t:
            continue
        metric_table(f"Task {task}", c, t, keys)

    # --- paired per-seed ------------------------------------------------
    lines.append(f"\n## Paired per-seed (structured vs dual_route)\n")
    lines.append(f"| task | seed | c SR | d SR | c mc | d mc | d fast | d tt | "
                 f"c toks | d toks | d redstr |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|\n")
    for task in ("0", "7", "9", "all"):
        cs = [r for r in ctrl if task == "all" or r["task"] == task]
        ts = [r for r in treat if task == "all" or r["task"] == task]
        for s in sorted({r["seed"] for r in cs} & {r["seed"] for r in ts}):
            c = next((r for r in cs if r["seed"] == s), None)
            t = next((r for r in ts if r["seed"] == s), None)
            if c is None or t is None:
                continue
            label = "all" if task == "all" else task
            lines.append(
                f"| {label} | {s} | {int(c['success'])} | {int(t['success'])} | "
                f"{_fmt(c['model_calls'])} | {_fmt(t['model_calls'])} | "
                f"{_fmt(t['fast_steps'])} | {_fmt(t['turns_total'])} | "
                f"{_fmt(c['tokens'])} | {_fmt(t['tokens'])} | "
                f"{_fmt(t['redundant_streak'])} |\n")

    # --- P_verify conversion ---------------------------------------------
    lines.append(f"\n## P_verify → success conversion\n")
    lines.append(f"| arm | reached P_verify | success | conversion |\n|---|---|---|---|\n")
    for label, arm in (("structured", ctrl), ("dual_route", treat)):
        reached = [r for r in arm if r["reached_p_verify"]]
        ok = sum(r["success"] for r in reached)
        lines.append(f"| {label} | {len(reached)}/{len(arm)} | {ok} | "
                     f"{ok / max(len(reached), 1):.0%} |\n")
    lines.append(f"*P_verify is not sufficient for success (placement/gripper still wrong); "
                 f"conversion shows whether the fast vds→finish chain lands.*\n")

    # --- slow reasons + fast breakdown -----------------------------------
    lines.append(f"\n## Slow-reason distribution (dual_route, per-run avg)\n")
    lines.append(f"| reason | count | share of slow |\n|---|---|---|\n")
    all_slow = collections.Counter()
    for r in treat:
        all_slow.update(json.loads(r["slow_reasons"]))
    tot = sum(all_slow.values()) or 1
    for reason, n in all_slow.most_common():
        lines.append(f"| {reason} | {n} | {n / max(tot, 1):.0%} |\n")
    lines.append(f"\n## Fast actions (dual_route, per-run avg)\n")
    lines.append(f"| action | structured | dual_route |\n|---|---|---|\n")
    lines.append(f"| fast_steps | — | {mean([r['fast_steps'] for r in treat])} |\n")
    lines.append(f"| ├ view_driver_state | — | {mean([r['fast_vds'] for r in treat])} |\n")
    lines.append(f"| ├ release | — | {mean([r['fast_release'] for r in treat])} |\n")
    lines.append(f"| ├ finish:success | — | {mean([r['fast_finish_ok'] for r in treat])} |\n")
    lines.append(f"| └ finish:failure | — | {mean([r['fast_finish_fail'] for r in treat])} |\n")

    # --- sanity / turn-drift check --------------------------------------
    n_slow_mean = mean([r["n_slow"] for r in treat])
    mc_mean = mean([r["model_calls"] for r in treat])
    lines.append(f"\n## Sanity checks\n")
    lines.append(f"- dual_route turns_total max = "
                 f"{max((r['turns_total'] for r in treat), default='—')} (≤40 enforced)\n")
    lines.append(f"- `[slow]` marker mean = {_fmt(n_slow_mean)} vs model_calls mean = "
                 f"{_fmt(mc_mean)} (≈ model_calls − 1; first model turn has no slow log)\n")
    drift = []
    for (task, s) in [("7", 2), ("0", 5)]:
        c = next((r for r in ctrl if r["task"] == task and r["seed"] == str(s)), None)
        sp = next((r for r in spots if r["task"] == task and r["seed"] == str(s)), None)
        if c is None or sp is None:
            continue
        ratio = sp["model_calls"] / max(c["model_calls"], 1)
        drift.append((task, s, c, sp, ratio))
    if drift:
        lines.append(f"\n## Fix-A drift check (fixed-code structured spot-checks vs reused control)\n")
        lines.append(f"| task | seed | ctrl SR | spot SR | ctrl mc | spot mc | ctrl toks | spot toks | ctrl nfired | spot nfired |\n")
        lines.append("|---|---|---|---|---|---|---|---|---|---|\n")
        for task, s, c, sp, ratio in drift:
            lines.append(f"| {task} | {s} | {int(c['success'])} | {int(sp['success'])} | "
                         f"{_fmt(c['model_calls'])} | {_fmt(sp['model_calls'])} | "
                         f"{_fmt(c['tokens'])} | {_fmt(sp['tokens'])} | "
                         f"{_fmt(c['n_fired'])} | {_fmt(sp['n_fired'])} |\n")
        lines.append(f"*Spot-checks re-run the same (task,seed) under the fixed R8 counter; "
                     f"moderate per-seed variance is expected, large drift would flag a Fix-A regression.*\n")

    lines.append(f"\n## Caveats\n")
    lines.append(f"- Control live `structured_metrics.json` was written by the pre-Fix-A code: "
                 f"its R8 counter counted non-memory reads, so control `n_fired` may include a "
                 f"false R8 fire. Fix A narrows R8 to memory reads; the false fires were "
                 f"harmless one-line injections (SM1 report Anomaly 2).\n")

    with open(REPORT_MD, "w") as f:
        f.write("\n".join(lines))
    return REPORT_MD


def main():
    rows = load_rows()
    if not rows:
        print("no run rows to analyze")
        return
    write_paired(rows)
    rep = write_report(rows)
    ctrl = sum(1 for r in rows if r["cond"] == "structured" and r["repeat"] == "1")
    treat = sum(1 for r in rows if r["cond"] == "dual_route")
    print(f"rows={len(rows)} (ctrl={ctrl} treat={treat}) -> {PAIRED_CSV}, {REPORT_MD}")


if __name__ == "__main__":
    main()
