"""Decision-point level parser for RPent trajectory logs.

Goes one level deeper than progress_gate_analysis / analyze_turns: instead of
per-run counts, it reconstructs the per-turn decision stream of each run —

  phase_at_turn, decision_class (ACT/OBSERVE/MEMORY/FINISH/ERROR),
  tool calls with success/error status, think excerpt,
  redundant streaks entering the turn, turns since last action,
  last action + its env outcome (final_dist_m / eef delta / gripper),
  structured-memory phase injections, fired rules, env steps consumed,

plus run-level meta (cond/task/seed/repeat, success, finish reason).

Sources (per run dir):
  transcript_*.json       — canonical message history (full tool results)
  run.log                 — [phase]/[memread]/[usage]/[fast]/[slow] markers
  states.json             — per-env-step command/result/eef/gripper
  structured_metrics.json — sm/dr arms: phase model, fired rules, mem reads

CLI:
  python decision_points.py parse <run_dir>...   # dump one JSON per run
  python decision_points.py scan                 # parse every run under logs/
"""
import json, os, re, sys, glob

LOGS = "/workspace/yjx/workspace/RPent/logs"

PERCEPTION = {"segment", "read_image", "back_project", "view_driver_state",
              "view_camera_meta", "read_depth", "back_project_action"}
ACTIONS = {"move_to", "move_pose", "pi0_pick", "pi0_doubled", "release",
           "set_gripper", "rotate_wrist", "rotate_pitch", "rotate_roll"}
MEMORY = {"read_text_file", "list_dir"}

_TURN_RE = re.compile(r"=== turn (\d+)/(\d+) ===")
_TOOL_RE = re.compile(r"\[tool>\] (\w+)\((\{.*\})\)")
_TOOLRES_RE = re.compile(r"\[tool<\] (\w+): (\{.*)")
_PHASE_RE = re.compile(r"\[structured_memory\] \[phase\] CURRENT=(\w+) \(prev=(\w+)\)")
_MEMREAD_RE = re.compile(r"\[structured_memory\] \[memread\] (.+)")
_USAGE_RE = re.compile(r"\[usage\] in=(\d+) out=(\d+)")


# ---------------------------------------------------------------- name parsing
_DIR_RE = re.compile(
    r"^(?P<ts>\d{8}-\d\d:\d\d:\d\d)"      # timestamp
    r"(?:_(?P<cond>[a-z_]+?))?"           # optional cond (baseline/ours/hardcap/structured)
    r"_(?P<suite>libero_[a-z_]+?)"
    r"_t(?P<task>\d+)_s(?P<seed>\d+)"
    r"(?:_r(?P<repeat>\d+))?$")
_SMOKE_RE = re.compile(r"^SMOKE_t(?P<task>\d+)s(?P<seed>\d+)$")

KNOWN_CONDS = {"baseline", "ours", "hardcap", "structured", "gateoff", "dual_route"}


def parse_run_dir_name(name):
    m = _SMOKE_RE.match(name)
    if m:
        return dict(cond="smoke", suite="libero_spatial_task",
                    task=m.group("task"), seed=m.group("seed"), repeat="1")
    m = _DIR_RE.match(name)
    if not m:
        return None
    cond = m.group("cond")
    suite = m.group("suite")
    if cond and cond not in KNOWN_CONDS and not cond.startswith("libero"):
        # e.g. 20260817-..._ours_libero_spatial_task_t9_s9_r1 -> cond=ours
        pass
    if cond in ("libero",):  # bare {ts}_libero_spatial_... has no cond slot
        cond = None
    # {ts}_{suite} case: cond group swallowed part of suite? verify suite known
    if cond and not cond.startswith(("base", "our", "hard", "struc", "gate", "dual", "smoke")):
        # cond captured a suite fragment -> actually no cond present
        suite2 = cond + "_" + suite
        if suite2.startswith("libero"):
            suite, cond = suite2, None
    return dict(cond=cond, suite=suite, task=m.group("task"),
                seed=m.group("seed"), repeat=m.group("repeat") or "1")


# ---------------------------------------------------------------- run.log events
def parse_run_log(path):
    ev = dict(turns=[], phase=[], memreads=[], usage=[], fast=[], slow=[])
    if not os.path.exists(path):
        return ev
    for line in open(path, errors="ignore"):
        m = _TURN_RE.search(line)
        if m:
            ev["turns"].append(int(m.group(1)))
            continue
        m = _PHASE_RE.search(line)
        if m:
            ev["phase"].append((len(ev["turns"]), m.group(1), m.group(2)))
            continue
        m = _MEMREAD_RE.search(line)
        if m:
            ev["memreads"].append((len(ev["turns"]), m.group(1)))
            continue
        m = _USAGE_RE.search(line)
        if m:
            ev["usage"].append((int(m.group(1)), int(m.group(2))))
            continue
        if "[fast]" in line:
            fm = re.search(r"\[fast\] (\w+)\(", line)
            ev["fast"].append((len(ev["turns"]), fm.group(1) if fm else "?"))
        if "[slow]" in line:
            sm = re.search(r"\[slow\] reason=(\w+)", line)
            ev["slow"].append((len(ev["turns"]), sm.group(1) if sm else "?"))
    return ev


# ---------------------------------------------------------------- transcript
def _assistant_calls(msg):
    out = []
    for p in (msg.get("content") or []):
        if isinstance(p, dict) and p.get("type") == "tool_use":
            out.append((p.get("name"), p.get("input") or {}))
    return out


def _assistant_text(msg):
    txt = []
    for p in (msg.get("content") or []):
        if isinstance(p, dict) and p.get("type") in ("thinking", "text"):
            if p.get(p.get("type")):
                txt.append(str(p.get(p.get("type"))))
    return " ".join(txt).strip()


def parse_transcript(path):
    """Return (meta, turns) where each turn = dict of what the planner did."""
    t = json.load(open(path))
    msgs = t["messages"]
    turns = []          # one per assistant message
    results = {}        # tool_call_id -> (name, ok, result_head)
    guard_blocks = []   # perception-guard interceptions
    phase_at = {}       # message index -> phase entering it
    injected_at = set() # message idx carrying a phase injection
    # tool results: map call ids in order
    for i, m in enumerate(msgs):
        if m.get("role") == "tool":
            c = m.get("content") or ""
            head = str(c)
            blocked = "Perception guard" in head[:120]
            ok = (not blocked) and ('"error"' not in head[:80])
            results[m.get("tool_call_id")] = (m.get("name"), ok, head)
            if blocked:
                guard_blocks.append((m.get("name"), head[:200]))
        if m.get("role") == "user":
            c = str(m.get("content") or "")
            pm = re.search(r"\[CURRENT PHASE: (\w+)\]", c)
            if pm:
                phase_at[i] = pm.group(1)
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        calls = _assistant_calls(m)
        rec = dict(idx=i, think=_assistant_text(m)[:400], calls=[])
        for name, args in calls:
            cid = None
            for p in (m.get("content") or []):
                if isinstance(p, dict) and p.get("type") == "tool_use" and p.get("name") == name:
                    cid = p.get("id"); break
            n_, ok, head = results.get(cid, (name, True, ""))
            rec["calls"].append(dict(name=name, args=args, ok=ok,
                                     res=head[:240]))
        rec["injected"] = any(j in injected_at for j in range(max(0, i - 2), i + 1))
        turns.append(rec)
    # mark injections after the pass (user msg just before an assistant msg)
    for rec in turns:
        i = rec["idx"]
        rec["injected"] = any(
            msgs[j].get("role") == "user" and "[CURRENT PHASE" in str(msgs[j].get("content"))
            for j in range(max(0, i - 3), i) if j >= 0)
        rec["phase_injected"] = None
        for j in range(max(0, i - 3), i):
            if j >= 0 and msgs[j].get("role") == "user":
                pm = re.search(r"\[CURRENT PHASE: (\w+)\]", str(msgs[j].get("content")))
                if pm:
                    rec["phase_injected"] = pm.group(1)
    meta = dict(suite=t.get("suite"), task=str(t.get("task")), seed=str(t.get("seed")),
                model=t.get("model"), finish=t.get("finish"), stats=t.get("stats"),
                guard_blocks=guard_blocks)
    return meta, turns


# ---------------------------------------------------------------- states.json
def parse_states(path):
    if not os.path.exists(path):
        return []
    try:
        st = json.load(open(path))
    except Exception:
        return []
    steps = []
    for s in st:
        eef = s.get("state", {}).get("robot0_eef_pos")
        grip = s.get("state", {}).get("robot0_gripper_qpos")
        cmd = s.get("command") or {}
        res = s.get("result") or {}
        steps.append(dict(
            step_idx=s.get("step_idx"), term=s.get("libero_terminated"),
            cmd_action=cmd.get("action"),
            cmd_xyz=cmd.get("xyz"), cmd_gripper=cmd.get("gripper"),
            res_name=res.get("name"),
            final_dist_m=res.get("final_dist_m"),
            final_eef=res.get("final_eef_pos"),
            eef=eef, grip=grip))
    # eef delta per step (vs previous)
    for i in range(1, len(steps)):
        a, b = steps[i - 1]["eef"], steps[i]["eef"]
        steps[i]["eef_delta"] = (round(sum((x - y) ** 2 for x, y in zip(a, b)) ** .5, 4)
                                 if a and b else None)
    return steps


# ---------------------------------------------------------------- classify
def classify(calls):
    names = [c["name"] for c in calls]
    if not calls:
        return "ERROR" if True else "NONE"
    cats = set()
    for n in names:
        if n in ACTIONS: cats.add("ACT")
        elif n in PERCEPTION: cats.add("OBSERVE")
        elif n in MEMORY: cats.add("MEMORY")
        elif n == "finish": cats.add("FINISH")
    if "ACT" in cats: return "ACT"
    if cats == {"MEMORY"}: return "MEMORY"
    if "OBSERVE" in cats: return "OBSERVE"
    if "FINISH" in cats: return "FINISH"
    return "MIXED"


# ---------------------------------------------------------------- main parse
def parse_run(d):
    name = os.path.basename(d.rstrip("/"))
    nm = parse_run_dir_name(name) or {}
    tl = glob.glob(os.path.join(d, "transcript_*.json"))
    if not tl:
        return None
    tmeta, turns = parse_transcript(tl[0])
    lev = parse_run_log(os.path.join(d, "run.log"))
    steps = parse_states(os.path.join(d, "states.json"))
    sm = {}
    smp = os.path.join(d, "structured_metrics.json")
    if os.path.exists(smp):
        try:
            sm = json.load(open(smp))
        except Exception:
            sm = {}

    # phase timeline: run.log [phase] events indexed by completed-turn count
    phase_events = lev["phase"]

    points = []
    last_action = None           # (tool, step_idx, dist, eef_delta, grip_delta)
    perc_streak = 0              # consecutive OBSERVE-class turns
    same_tool_streak = 0
    last_tool = None
    since_act = 0
    step_cursor = 0              # env steps consumed so far (approx via cmd count)
    for k, rec in enumerate(turns, start=1):
        cls = classify(rec["calls"])
        names = [c["name"] for c in rec["calls"]]
        # phase active entering turn k = last phase event with turn_idx < k
        ph = None
        for ti, cur, prev in phase_events:
            if ti < k:
                ph = cur
        # env steps advanced by ACT calls in this turn (crude: count action cmds
        # actually recorded in states; align by order)
        rec2 = dict(
            turn=k, phase=ph or rec.get("phase_injected"), cls=cls,
            tools=names, n_err=sum(1 for c in rec["calls"] if not c["ok"]),
            think=rec["think"][:160],
            perc_streak_before=perc_streak,
            same_tool_streak_before=same_tool_streak,
            since_last_act=since_act,
            last_action=last_action,
            injected=rec.get("phase_injected"))
        if lev["usage"] and k <= len(lev["usage"]):
            rec2["tok_in"], rec2["tok_out"] = lev["usage"][k - 1]
        points.append(rec2)
        # update streaks
        if cls == "OBSERVE":
            perc_streak += 1
        else:
            perc_streak = 0
        if names and names[0] == last_tool and len(set(names)) == 1:
            same_tool_streak += 1
        elif names:
            same_tool_streak = 1
        last_tool = names[0] if names else last_tool
        if cls == "ACT":
            since_act = 0
            # find outcome from steps (next cmd with matching action after cursor)
            act_name = names[0]
            matched = None
            for s in steps[step_cursor + 1:]:
                if s["cmd_action"] in (act_name, "pi0_doubled" if act_name == "pi0_doubled" else act_name):
                    matched = s
                    step_cursor = s["step_idx"]
                    break
            if matched:
                last_action = dict(tool=act_name, step=matched["step_idx"],
                                   dist=matched["final_dist_m"],
                                   eef_delta=matched.get("eef_delta"))
            else:
                last_action = dict(tool=act_name, step=None, dist=None, eef_delta=None)
        else:
            since_act += 1

    success = None
    if steps:
        success = bool(steps[-1].get("term"))
    fin = tmeta.get("finish")
    reason = None
    if fin:
        reason = str(fin.get("reason") or fin.get("status") or "finish")[:40] if isinstance(fin, dict) else str(fin)[:40]
    out = dict(
        run_id=name, cond=nm.get("cond"), suite=tmeta.get("suite") or nm.get("suite"),
        task=tmeta.get("task") or nm.get("task"), seed=tmeta.get("seed") or nm.get("seed"),
        repeat=nm.get("repeat"), model=tmeta.get("model"),
        success=success, finish_reason=reason, n_turns=len(turns),
        n_steps=len(steps), points=points, steps=steps,
        phase_events=phase_events, memreads=lev["memreads"],
        fast=lev["fast"], slow=lev["slow"],
        structured=({k: sm[k] for k in
                     ("phase_sequence", "final_phase", "fired_rules", "fired_detail",
                      "recovery_success", "counters", "mem_reads", "injections")}
                    if sm else None))
    return out


def scan(root=LOGS, out_path="/workspace/yjx/workspace/RPent/analysis/decision_points.jsonl"):
    n = 0
    with open(out_path, "w") as f:
        for d in sorted(glob.glob(os.path.join(root, "*"))):
            if not os.path.isdir(d):
                continue
            for sub in ([d] if os.path.exists(os.path.join(d, "run.log")) or
                        glob.glob(os.path.join(d, "transcript_*.json")) else
                        sorted(glob.glob(os.path.join(d, "*")))):
                if not os.path.isdir(sub):
                    continue
                r = parse_run(sub)
                if not r:
                    continue
                f.write(json.dumps(r) + "\n")
                n += 1
    print(f"wrote {n} runs -> {out_path}")


if __name__ == "__main__":
    if sys.argv[1] == "scan":
        scan()
    else:
        for d in sys.argv[2:]:
            print(json.dumps(parse_run(d), indent=1)[:4000])
