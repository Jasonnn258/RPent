"""Milestone-aligned pairing analysis for reasoning-timing diagnostics.

Aligns runs by TASK MILESTONES (pick outcomes, place outcomes, guard events),
not by turn number — turn-aligned "first divergence" is dominated by opening
stochasticity (whether the model bundles list_dir with read_text_file).

For every CSV-registered run, extracts an event timeline from the transcript:
  every tool call with (turn, name, args, ok, guard_blocked) and for actions
  the primitive outcome (pick success / gripper opening / lift / terminated /
  move final_dist) from log.result.

Then:
  1. milestone_summary(run)
  2. pair_divergence(success_run, fail_run)   — first milestone whose OUTCOME
     differs, else first differing response-to-failure, else first differing
     move target
  3. hardcap flips vs baseline (guard causality)
  4. structured flips vs baseline (which decision the memory changed)
Writes pairing_summary.json + milestone_rows.csv.
"""
import csv, glob, json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOGS = os.path.join(ROOT, "logs")
sys.path.insert(0, HERE)

ACTS = {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
        "set_gripper", "rotate_wrist", "rotate_pitch", "rotate_roll"}


def tpath(run_id):
    for base in ("pg_exp", "sm_exp", "dr_exp", "."):
        g = glob.glob(os.path.join(LOGS, base, run_id, "transcript_*.json"))
        if g:
            return g[0]
    return None


def load_reg():
    reg = {}
    for f, src in (("progress_gate_runs.csv", "pg"), ("structured_memory_runs.csv", "sm")):
        for row in csv.DictReader(open(os.path.join(HERE, f))):
            name = row["dir"].rstrip("/").split("/")[-1]
            reg.setdefault(name, dict(row, src=src))
    return reg


def extract_events(run_id):
    """Event timeline from transcript: calls with outcomes."""
    tp = tpath(run_id)
    if not tp:
        return None
    t = json.load(open(tp))
    events = []
    turn = 0
    for m in t["messages"]:
        if m.get("role") != "assistant":
            continue
        turn += 1
        for p in (m.get("content") or []):
            if not (isinstance(p, dict) and p.get("type") == "tool_use"):
                continue
            events.append(dict(turn=turn, name=p.get("name"),
                               args=p.get("input") or {}, cid=p.get("id"),
                               ok=None, outcome={}))
    # join results by cid
    res = {}
    for m in t["messages"]:
        if m.get("role") == "tool":
            res[m.get("tool_call_id")] = m.get("content")
    for e in events:
        c = res.get(e["cid"])
        if c is None:
            e["ok"] = False
            e["outcome"] = {"err": "no-result"}
            continue
        s = c if isinstance(c, str) else json.dumps(c)
        if s.startswith("Perception guard") or '"perception_blocked"' in s[:120]:
            e["ok"] = False
            e["outcome"] = {"guard": True}
            continue
        try:
            d = json.loads(s)
        except Exception:
            e["ok"] = '"error"' not in s[:80]
            e["outcome"] = {}
            continue
        log = (d.get("log") or {})
        r = log.get("result") or {}
        e["ok"] = "error" not in d
        o = {}
        if e["name"] == "pi0_pick":
            o = dict(kind="pick", pick_success=r.get("success"),
                     min_grip=r.get("min_gripper_opening"),
                     peak_lift=r.get("peak_lift_m"),
                     chunks=r.get("chunks_used"))
        elif e["name"] == "pi0_doubled":
            o = dict(kind="doubled", pick_success=r.get("success"),
                     min_grip=r.get("min_gripper_opening"),
                     peak_lift=r.get("peak_lift_m"))
        elif e["name"] == "release":
            o = dict(kind="release", peak_open=r.get("peak_gripper_opening"),
                     term=r.get("libero_terminated", d.get("libero_terminated")))
        elif e["name"] == "move_to":
            o = dict(kind="move", dist=r.get("final_dist_m"),
                     tgt=e["args"].get("xyz"))
        elif e["name"] == "set_gripper":
            o = dict(kind="gripper", term=r.get("libero_terminated"))
        elif e["name"] == "finish":
            o = dict(kind="finish", status=e["args"].get("status"))
        e["outcome"] = o
        if d.get("libero_terminated"):
            e["outcome"]["term"] = True
    fin = t.get("finish") or {}
    return dict(events=events, n_turns=turn,
                finish_status=fin.get("status"),
                finish_summary=(fin.get("summary") or "")[:400],
                success=bool(fin.get("status") == "success"))


def holds(o):
    """Gripper actually holding after pick: heuristic success OR tight grip."""
    if not o:
        return None
    mg = o.get("min_grip")
    if o.get("pick_success") is True:
        return True
    if mg is not None and mg < 0.03:
        return True
    if mg is not None and mg >= 0.03 and o.get("pick_success") is False:
        return False
    return None


def milestones(tl):
    ms = []
    picks = [e for e in tl["events"] if e["name"] in ("pi0_pick", "pi0_doubled")]
    for i, e in enumerate(picks, 1):
        ms.append(dict(m=f"pick{i}", turn=e["turn"], tool=e["name"],
                       out=dict(hold=holds(e["outcome"]),
                                succ=e["outcome"].get("pick_success"),
                                grip=e["outcome"].get("min_grip"))))
    rels = [e for e in tl["events"] if e["name"] == "release"]
    for i, e in enumerate(rels, 1):
        ms.append(dict(m=f"release{i}", turn=e["turn"], tool="release",
                       out=dict(term=e["outcome"].get("term"))))
    return ms


def response_to_failure(tl, fail_turn, window=3):
    """What the planner did within `window` turns after a failing action."""
    acts = []
    for e in tl["events"]:
        if fail_turn < e["turn"] <= fail_turn + window:
            acts.append(e["name"])
    if not acts:
        return "none"
    a = acts[0]
    if a in ("read_image", "back_project", "segment", "view_driver_state"):
        return "re-perceive"
    if a in ("read_text_file", "list_dir"):
        return "memory"
    if a in ("pi0_pick", "pi0_doubled"):
        return "re-pick"
    if a == "move_to":
        return "re-move"
    if a == "release":
        return "release-anyway"
    return a


def pair_compare(ta, tb):
    """ta=success timeline, tb=fail timeline. Find first qualitative divergence."""
    ma, mb = milestones(ta), milestones(tb)
    for i in range(max(len(ma), len(mb))):
        xa = ma[i] if i < len(ma) else None
        xb = mb[i] if i < len(mb) else None
        if xa is None or xb is None or xa["m"] != xb["m"]:
            return dict(where="milestone-set", idx=i, a=xa, b=xb)
        if xa["out"] != xb["out"]:
            return dict(where="outcome", idx=i, a=xa, b=xb)
    # identical milestone outcomes -> compare response to first failed pick
    for i, (xa, xb) in enumerate(zip(ma, mb)):
        hold = xa["out"].get("hold")
        if hold is False:
            ra = response_to_failure(ta, xa["turn"])
            rb = response_to_failure(tb, xb["turn"])
            if ra != rb:
                return dict(where="failure-response", idx=i, milestone=xa["m"],
                            a_resp=ra, b_resp=rb, a=xa, b=xb)
    # compare move targets
    tga = [e["outcome"].get("tgt") for e in ta["events"] if e["name"] == "move_to"]
    tgb = [e["outcome"].get("tgt") for e in tb["events"] if e["name"] == "move_to"]
    for i in range(min(len(tga), len(tgb))):
        if tga[i] and tgb[i]:
            d = sum((x - y) ** 2 for x, y in zip(tga[i], tgb[i])) ** .5
            if d > 0.15:
                return dict(where="move-target", idx=i, a=tga[i], b=tgb[i], dist=d)
    return dict(where="none-found")


def main():
    reg = load_reg()
    tls = {}
    for name, row in reg.items():
        tl = extract_events(name)
        if tl:
            tls[name] = dict(tl=tl, row=row)
    print("timelines:", len(tls))

    # milestone rows for every canonical run
    with open(os.path.join(HERE, "milestone_rows.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "cond", "task", "seed", "repeat", "result", "run_id",
                    "n_turns", "n_picks", "picks_held", "n_release", "rel_term",
                    "first_hold_pick", "n_moves", "finish_status"])
        for name, d in sorted(tls.items(), key=lambda kv: (kv[1]["row"]["task"], kv[1]["row"]["seed"], kv[1]["row"]["cond"])):
            tl, row = d["tl"], d["row"]
            ms = milestones(tl)
            pms = [m for m in ms if m["m"].startswith("pick")]
            rms = [m for m in ms if m["m"].startswith("release")]
            held = [i for i, m in enumerate(pms, 1) if m["out"].get("hold")]
            w.writerow([d["row"]["src"], row["cond"], row["task"], row["seed"],
                        row["repeat"], row.get("result"), name, tl["n_turns"],
                        len(pms), sum(1 for m in pms if m["out"].get("hold")),
                        len(rms), any(m["out"].get("term") for m in rms),
                        held[0] if held else "",
                        sum(1 for e in tl["events"] if e["name"] == "move_to"),
                        tl["finish_status"]])

    # within-cond pairing
    cells = collections.defaultdict(list)
    for name, d in tls.items():
        cells[(d["row"]["src"], d["row"]["cond"], d["row"]["task"], d["row"]["seed"])].append((name, d))
    pairs_out = []
    for k, items in sorted(cells.items(), key=str):
        succ = [(n, d) for n, d in items if d["tl"]["success"]]
        fail = [(n, d) for n, d in items if not d["tl"]["success"] and d["row"].get("result") != "infra_crash"]
        if succ and fail:
            c = pair_compare(succ[0][1]["tl"], fail[0][1]["tl"])
            pairs_out.append(dict(exp=k[0], cond=k[1], task=k[2], seed=k[3],
                                  succ=succ[0][0], fail=fail[0][0], **c))
    json.dump(pairs_out, open(os.path.join(HERE, "pairing_summary.json"), "w"),
              indent=1, default=str)
    print("within-cond pairs:", len(pairs_out))
    for w_ in ("outcome", "milestone-set", "failure-response", "move-target", "none-found"):
        n = sum(1 for p in pairs_out if p["where"] == w_)
        print(f"  {w_}: {n}")

    # cross-cond outcome flips (same task+seed): baseline vs hardcap / structured
    flips = []
    by_ts = collections.defaultdict(dict)
    for name, d in tls.items():
        by_ts[(d["row"]["task"], d["row"]["seed"])][d["row"]["cond"]] = (name, d)
    for (task, seed), conds in sorted(by_ts.items(), key=str):
        for other in ("hardcap", "ours", "structured"):
            if "baseline" in conds and other in conds:
                b = conds["baseline"][1]["tl"]
                o = conds[other][1]["tl"]
                if b["success"] != o["success"]:
                    flips.append(dict(task=task, seed=seed, cond=other,
                                      base_win=b["success"],
                                      run=conds[other][0],
                                      base_run=conds["baseline"][0]))
    json.dump(flips, open(os.path.join(HERE, "cond_flips.json"), "w"), indent=1)
    print("cross-cond flips:", len(flips))
    fc = collections.Counter((f["cond"], f["task"], f["base_win"]) for f in flips)
    for k, v in sorted(fc.items(), key=str):
        print("  ", k, v)


if __name__ == "__main__":
    main()
