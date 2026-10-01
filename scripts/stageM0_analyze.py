#!/usr/bin/env python
"""Stage M §3-6 — M0 确定性 Recovery Abstraction Analyzer(纯离线)。

输入:Stage L 池全部 episode(logs/ovpm_exp)− L_HELDOUT_TEST 24 集。
对每集重跑 replay_fires(与 H/K/L 同一代码路径),对每个 fire 取
tR = 首个满足 fire_validated 的后续命令步(Stage L 挖矿同码同参),
得 recovery segment;从 transcript_*.json 构造扁平事件序列
(tool_use 发射 / tool 结果到达,位置配对;robot 原语结果带 "step"
字段做 step_idx 精确锚定,与第 k 个 actuation step 位置对齐交叉校验),
映射 §3 事件本体,判 §5 强条件 A-D/E,出 §5 标签 + §6 FID。

产物(analysis/):
- stageM0_recovery_segments.jsonl  每 segment 一行(全字段)
- stageM0_event_annotations.jsonl  每 segment 事件序列
- stageM0_abstraction_labels.csv   标签表(盲审比对用)
- stdout 池级统计(fires / segments / never-validated / 对齐失败)

用法:python scripts/stageM0_analyze.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from analyze_stageH1 import NODE_FAMILY, fire_validated, replay_fires  # noqa: E402

# ---- §3 事件本体的确定性常量(冻结于 prereg) ------------------------------
PICK = {"pi0_pick", "pi0_doubled"}
MOVE = {"move_to", "move_pose", "rotate_wrist"}
GRIP = {"set_gripper", "release"}
PRIMS = PICK | MOVE | GRIP
OBSERVE_TOOLS = {"read_image", "view_driver_state"}
GROUND_TOOLS = {"back_project", "segment"}

# ---- §5 判据阈值(冻结) ---------------------------------------------------
XY_TOL = 0.02      # B:水平距离容差(back_project 定位水平位置)
DZ_TOL = 0.10      # B:z 容差(z 是接近高度参数)
MOVE_NEG = 0.05    # C:move 未达判据(final_dist ≥ 此值)
MOVE_OK = 0.03     # (与 H fire_validated 同值,move 正验证)
UNKNOWN_MAX = 0.2  # UNRESOLVED:窗口内 UNKNOWN 事件占比上限


def af(action: str) -> str:
    """动作粗族(A/D 判据的 family 签名;冻结三族划分)。"""
    if action in PICK:
        return "pick"
    if action in MOVE:
        return "move"
    if action in GRIP:
        return "gripper"
    return "other"


def load_steps(d: Path):
    """states.json → 按 step_idx 排序的步列表。"""
    steps = json.load(open(d / "states.json"))
    return sorted(steps, key=lambda s: s.get("step_idx", 0))


def flat_events(msgs):
    """transcript 消息 → 扁平事件序列(发射/结果,位置配对)。

    assistant 的 tool_use block 依序入队;role=tool 消息按队列消费配对
    (并行调用被拒也会如实回一条错误结果,位置关系保持)。
    每事件 {seq, kind: use|res, name, input/payload, mi}。
    """
    events, pending = [], []
    for mi, m in enumerate(msgs):
        c = m.get("content")
        if m["role"] == "assistant" and isinstance(c, list):
            for b in c:
                if b.get("type") == "tool_use":
                    pending.append({"seq": len(events), "kind": "use",
                                    "name": b.get("name"),
                                    "input": b.get("input") or {},
                                    "mi": mi})
                    events.append(pending[-1])
        elif m["role"] == "tool":
            body = m.get("content")
            try:
                payload = json.loads(body) if isinstance(body, str) else body
            except (json.JSONDecodeError, TypeError):
                payload = None      # 非结构化结果(read_image 路径串等)
            if not pending:
                continue            # 无对应发射(理论上不出现)
            u = pending.pop(0)
            events.append({"seq": len(events), "kind": "res",
                           "name": u["name"], "payload": payload,
                           "mi": mi, "use_seq": u["seq"]})
    return events


def build_timeline(d: Path):
    """一集 → timeline 或失败原因。

    对齐规则(确定性;2026-10-01 二次修正,error 结果 ≠ 未执行 ——
    实证存在 result 为并行锁错误但 states.json 有执行记录的调用):
    1. 有 "step" 字段的 robot 发射 → 直接锚定该 step_idx(单调、
       动作名须一致);
    2. 无 "step" 字段(null 结果)→ 按序占当前指针位,动作名须一致;
    3. 中部出现无发射对应的 actuation step(顺序断链)→ align fail;
       尾部未覆盖(transcript 截断)→ 允许,窗口涉及时的 segment 由
       调用方判 UNRESOLVED(t0/tR 发射须在覆盖内)。
    动作 cmd/result 一律取 states.json(权威);transcript 只提供
    事件顺序与感知结果(world_xyz 等)。
    """
    tfiles = sorted(d.glob("transcript_*.json"))
    if not tfiles:
        return None
    msgs = json.load(open(tfiles[0]))["messages"]
    events = flat_events(msgs)
    act_steps = [s for s in load_steps(d) if (s.get("command") or {}).get("action")]
    res_of_use = {e.get("use_seq"): e for e in events if e["kind"] == "res"}

    def sf_of(u):
        pl = (res_of_use.get(u["seq"]) or {}).get("payload")
        return pl.get("step") if isinstance(pl, dict) else None

    uses = [e for e in events if e["kind"] == "use" and e["name"] in PRIMS]
    anchor, n_field, n_noexec = {}, 0, 0

    # ---- 第一遍:step 字段锚(单调、动作名一致才可信) ----------------------
    # 陈旧 step 字段(并发调用拿到执行前计数器)名字对不上 → 降级为无锚
    # 发射,交第二遍区间匹配;顺序/锚洞约束兜底。
    sf_act = {}          # use seq -> act 下标
    p = 0
    for u in uses:
        sf = sf_of(u)
        if sf is None:
            continue
        n_field += 1
        q = p
        while q < len(act_steps) and act_steps[q]["step_idx"] < int(sf):
            q += 1
        if q < len(act_steps) and act_steps[q]["step_idx"] == int(sf) \
                and act_steps[q]["command"]["action"] == u["name"]:
            anchor[u["seq"]] = int(sf)
            sf_act[u["seq"]] = q
            p = q + 1

    # ---- 第二遍:无 step 发射在前后锚区间内按动作名贪心认领 -----------------
    # (同名 error 结果有时执行有时未执行 —— 唯一可靠区分是槽位占用;
    #  认领不上 = 未执行,保留为序但无锚、不算 PHYSICAL_ACTION)
    claimed = set(sf_act.values())
    seqs = [u["seq"] for u in uses]
    nxt_sf = [None] * len(seqs)      # 各 use 之后(含自身 sf 者=自身)的 sf act 下标
    nxt = None
    for i in range(len(seqs) - 1, -1, -1):
        if seqs[i] in sf_act:
            nxt = sf_act[seqs[i]]
        nxt_sf[i] = nxt
    cursor = 0
    last_sf = -1
    for i, u in enumerate(uses):
        if u["seq"] in sf_act:
            last_sf = sf_act[u["seq"]]
            cursor = last_sf + 1
            continue
        hi = nxt_sf[i] if nxt_sf[i] is not None else len(act_steps)
        got_slot = None
        for q in range(cursor, hi):
            if q in claimed:
                continue
            if act_steps[q]["command"]["action"] == u["name"]:
                got_slot = q
                break
        if got_slot is None:
            n_noexec += 1
            anchor[u["seq"]] = None
        else:
            anchor[u["seq"]] = act_steps[got_slot]["step_idx"]
            claimed.add(got_slot)
            cursor = got_slot + 1

    # ---- 锚洞校验:末位已认领 actuation 之前的每个槽都须被认领 -------------
    claimed_idx = sorted(claimed)
    if claimed_idx and claimed_idx != list(range(len(claimed_idx))):
        return {"align_ok": False, "reason": "anchor holes (mid-gap)"}
    return {"align_ok": True, "events": events, "uses": uses,
            "act_steps": act_steps,
            "anchor": {i: anchor[u["seq"]] for i, u in enumerate(uses)},
            "n_step_field": n_field, "covered_upto": len(claimed_idx),
            "n_noexec": n_noexec}


def outcome_of(action: str, res: dict):
    """§5 C/D 的动作级验证 outcome:pos / neg / None(无验证语义)。"""
    if action in PICK:
        return "pos" if res.get("success") is True else "neg"
    if action in ("move_to", "move_pose"):
        fd = res.get("final_dist_m")
        if not isinstance(fd, (int, float)):
            return None
        return "pos" if fd < MOVE_OK else ("neg" if fd >= MOVE_NEG else None)
    return None


def seg_events_window(tl, t0: int, tR: int):
    """窗口事件 = 扁平序中 (t0 发射位置, tR 发射位置] 内全部 use/res。

    观察/grounding 只要在 t0 发射之后、tR 发射之前即属窗口(它们是
    恢复决策的信息输入);tR 的结果不计(验证本身)。边界发射按锚
    (step_idx → use)定位,不依赖 uses 下标。
    """
    seq_of_step = {v: u["seq"] for i, u in enumerate(tl["uses"])
                   if (v := tl["anchor"][i]) is not None}
    if t0 not in seq_of_step or tR not in seq_of_step:
        return None
    lo, hi = seq_of_step[t0], seq_of_step[tR]
    if lo >= hi:
        return None
    win = [e for e in tl["events"] if lo < e["seq"] <= hi]
    # tR 的结果排除
    win = [e for e in win if not (e["kind"] == "res"
                                  and e.get("use_seq") == hi)]
    return win, lo, hi


def analyze_segment(tl, fire, tR_i, steps_by_idx):
    """§3-6:一个 segment 的事件标注 + A-D/E + 标签。

    t0/tR 的发射必须落在 transcript 覆盖内(uses 序);否则该 segment
    事件序列不完整 → 返回 ("beyond", …) 由调用方标 UNRESOLVED。
    """
    node = fire["node"]
    t0, tR = fire["step_idx"], tl["act_steps"][tR_i]["step_idx"]
    seq_of_step = {v: u["seq"] for i, u in enumerate(tl["uses"])
                   if (v := tl["anchor"][i]) is not None}
    if t0 not in seq_of_step or tR not in seq_of_step:
        return ("beyond", None)
    got = seg_events_window(tl, t0, tR)
    if got is None:
        return ("beyond", None)
    win, t0_seq, tR_seq = got
    events = tl["events"]

    # ---- §3 事件标注 ------------------------------------------------------
    phys, observes, grounds = [], [], []
    unknown = 0
    res_of_use = {e.get("use_seq"): e for e in events
                  if e["kind"] == "res"}
    use_pos = {u["seq"]: i for i, u in enumerate(tl["uses"])}
    for e in win:
        if e["kind"] != "use":
            continue
        if e["name"] in PRIMS:
            step_idx = tl["anchor"][use_pos[e["seq"]]]
            if step_idx is None:      # 未执行发射(指针耗尽后的调用)
                continue
            srow = steps_by_idx[step_idx]     # states.json 为权威
            cmd, res = srow.get("command") or {}, srow.get("result") or {}
            if not isinstance(res, dict):
                unknown += 1
                res = {}
            phys.append({"seq": e["seq"], "mi": e["mi"], "step": step_idx,
                         "action": e["name"], "cmd": cmd, "res": res})
        elif e["name"] in OBSERVE_TOOLS:
            observes.append({"seq": e["seq"], "mi": e["mi"],
                             "name": e["name"]})
        elif e["name"] in GROUND_TOOLS:
            res = (res_of_use.get(e["seq"]) or {}).get("payload")
            if isinstance(res, dict) and "world_xyz" in res:
                grounds.append({"seq": e["seq"], "mi": e["mi"],
                                "name": e["name"],
                                "world_xyz": res["world_xyz"]})
            # 有调用无 world_xyz → 不构成 GROUND_UPDATE 事件(§3)

    # REPLAN:窗口内含 ≥1 机器人发射的 assistant turn
    replan_mis = {p["mi"] for p in phys}
    # VERIFY:窗口内每个动作的 outcome 到达(与 C/D 共用 outcome 定义)
    outs = [outcome_of(p["action"], p["res"]) for p in phys]

    # ---- §5 强条件 A-D / E -------------------------------------------------
    ev = {"A": False, "B": False, "C": False, "D": False, "E": False}
    ev_detail = {}

    # A:相邻动作对换族 ∧ 发射之间有 OBSERVE/GROUND
    obs_ground_seqs = ([o["seq"] for o in observes]
                       + [g["seq"] for g in grounds])
    for a, b in zip(phys, phys[1:]):
        if af(a["action"]) != af(b["action"]) and any(
                a["seq"] < q < b["seq"] for q in obs_ground_seqs):
            ev["A"] = True
            ev_detail.setdefault("A", []).append(
                f"{a['action']}→{b['action']}@s{a['step']}→s{b['step']}")
    # B:grounding world_xyz → 其后动作 xyz(xy≤0.02 ∧ |dz|≤0.10)
    for g in grounds:
        w = g["world_xyz"]
        for p in phys:
            if p["seq"] <= g["seq"]:
                continue
            t = p["cmd"].get("xyz")
            if not (isinstance(t, list) and len(t) == 3):
                continue
            dxy = ((t[0] - w[0]) ** 2 + (t[1] - w[1]) ** 2) ** 0.5
            dz = abs(t[2] - w[2])
            if dxy <= XY_TOL and dz <= DZ_TOL:
                ev["B"] = True
                ev_detail.setdefault("B", []).append(
                    f"w={w}→{p['action']}@s{p['step']} dxy={dxy:.4f} dz={dz:.4f}")
    # C:负验证 → 其后(下一 turn 起)动作变更(同族改 prompt/换族/终止)
    for j, p in enumerate(phys):
        if outs[j] != "neg":
            continue
        after = [q for q in phys if q["mi"] > p["mi"]]
        if not after:
            # 负验证后无动作:tR 若为集终止即“触发 TERMINATE”
            if steps_by_idx[tR].get("libero_terminated"):
                ev["C"] = True
                ev_detail.setdefault("C", []).append(
                    f"neg@{p['action']}s{p['step']}→terminate")
            continue
        q = after[0]
        if af(q["action"]) != af(p["action"]):
            ev["C"] = True
            ev_detail.setdefault("C", []).append(
                f"neg@{p['action']}s{p['step']}→{q['action']}")
        elif p["action"] in PICK and q["action"] in PICK \
                and q["cmd"].get("prompt") != p["cmd"].get("prompt"):
            ev["C"] = True
            ev_detail.setdefault("C", []).append(
                f"neg@{p['action']}s{p['step']}→retry新prompt")
    # E(仅 FID):窗口内观察/grounding 之后发射的 pick prompt ∉ t0 前 prompt 集
    pre_prompts = {json.dumps((u.get("input") or {}).get("prompt"),
                              ensure_ascii=False)
                   for u in tl["uses"] if u["seq"] < t0_seq
                   and u["name"] in PICK}
    first_og = min(obs_ground_seqs) if obs_ground_seqs else None
    if first_og is not None:
        for p in phys:
            if p["seq"] > first_og and p["action"] in PICK:
                pr = json.dumps(p["cmd"].get("prompt"), ensure_ascii=False)
                if pr not in pre_prompts:
                    ev["E"] = True
                    ev_detail.setdefault("E", []).append(
                        f"obs后新prompt@{p['action']}s{p['step']}")

    # ---- 标签(§5 顺序) ---------------------------------------------------
    n_win_events = len(win)
    unknown_rate = unknown / n_win_events if n_win_events else 0.0
    strong = ev["A"] or ev["B"] or ev["C"] or ev["D"]
    if unknown_rate > UNKNOWN_MAX:
        label = "UNRESOLVED"
        sub = "unknown>20%"
    elif len(phys) == 1 and not observes and not grounds and not strong:
        label = "EDGE_REPRESENTABLE"
        sub = ""
    elif strong:
        label = "OPTION_REQUIRED"
        sub = ""
    else:
        label = "MACRO_REPRESENTABLE"
        sub = ""
    fid = (ev["A"] or ev["B"] or ev["C"] or ev["D"] or ev["E"]) \
        if label != "UNRESOLVED" else None

    # tR 依据(§8 首次可局部验证位置)
    tR_step = steps_by_idx[tR]
    tR_res = tR_step.get("result") or {}
    if tR_step.get("libero_terminated"):
        tR_reason = "terminated"
    elif tR_step["command"]["action"] == "pi0_doubled" \
            and tR_res.get("success") is True:
        tR_reason = "doubled_success"
    elif tR_step["command"]["action"] == "pi0_pick":
        tR_reason = "pick_lift"
    else:
        tR_reason = "move_ok"

    seg = {
        "segment_id": None,   # main 填
        "episode_dir": None,
        "task": None, "seed": None, "node": node,
        "family": NODE_FAMILY[node], "t0": t0, "tR": tR, "tR_reason": tR_reason,
        "n_physical": len(phys), "n_observe": len(observes),
        "n_ground": len(grounds),
        "n_verify_pos": sum(o == "pos" for o in outs),
        "n_verify_neg": sum(o == "neg" for o in outs),
        "n_replan_turns": len(replan_mis),
        "primitive_count": len(phys),
        "wall_s": round(steps_by_idx[tR].get("elapsed_s", 0)
                        - steps_by_idx[t0].get("elapsed_s", 0), 2),
        "A": ev["A"], "B": ev["B"], "C": ev["C"], "D": ev["D"], "E": ev["E"],
        "detail": ev_detail,
        "label": label, "label_sub": sub, "fid": fid,
        "unknown_rate": round(unknown_rate, 3),
        "phys": [{"step": p["step"], "action": p["action"],
                  "xyz": p["cmd"].get("xyz"),
                  "prompt": p["cmd"].get("prompt"), "out": outs[i]}
                 for i, p in enumerate(phys)],
    }
    return seg, {"win_events": win, "phys": phys, "observes": observes,
                 "grounds": grounds, "t0_seq": t0_seq, "tR_seq": tR_seq}


def group_key(seg, pre_sig):
    """D 判据分组键:(family, task, 窗口前 2 动作粗族签名)。"""
    return (seg["family"], seg["task"], pre_sig)


def pre_signature(tl, i0):
    """t0(含)之前最后 2 个 actuation 的粗族签名。"""
    sig = [af(s["command"]["action"]) for s in tl["act_steps"][:i0 + 1]]
    return "|".join(sig[-2:]) if sig else "none"


def main() -> int:
    # ---- 池:inventory 全集 − L_HELDOUT_TEST 24 集 -------------------------
    import csv as _csv
    held = {r["episode_dir"] for r in
            _csv.DictReader(open(REPO / "analysis/stageL_split_manifest.csv"))
            if r["role"] == "L_HELDOUT_TEST"}
    pool = {}
    for ln in open(REPO / "analysis/stageL_pool_inventory.jsonl"):
        r = json.loads(ln)
        d = r["episode_dir"]
        if d in held:
            continue
        pool[d] = {"task": r["task"], "seed": r["seed"], "role": r["role"]}
    print(f"pool: {len(pool)} episodes (excluded {len(held)} L_HELDOUT_TEST)")

    segs, annots, align_fail = [], [], []
    n_fires = Counter()
    n_never = Counter()
    k_side_check = {"match": 0, "diff": 0}
    # K 侧交叉核对基准(同码路径 sanity):inventory 记录的 fire 集合
    k_expect = defaultdict(list)
    for ln in open(REPO / "analysis/stageL_pool_inventory.jsonl"):
        r = json.loads(ln)
        if r.get("fire_step") is not None:
            k_expect[r["episode_dir"]].append(r["fire_step"])

    for d, meta in sorted(pool.items()):
        dp = Path(d)
        if not (dp / "states.json").exists():
            continue
        steps = load_steps(dp)
        steps_by_idx = {s["step_idx"]: s for s in steps}
        fires = replay_fires(steps)
        got_steps = sorted(f["step_idx"] for f in fires)
        if sorted(k_expect.get(d, [])) == got_steps:
            k_side_check["match"] += 1
        else:
            k_side_check["diff"] += 1
        tl = build_timeline(dp)
        tl_ok = tl is not None and tl.get("align_ok")
        if tl is not None and not tl.get("align_ok"):
            align_fail.append((d, tl.get("reason")))
        for fi, fire in enumerate(fires):
            fam = NODE_FAMILY[fire["node"]]
            n_fires[fam] += 1
            # tR:首个单步 fire_validated(与 L 挖矿同参)
            acts = [x for x in steps if (x.get("command") or {}).get("action")]
            i0 = next((i for i, s in enumerate(acts)
                       if s["step_idx"] == fire["step_idx"]), None)
            if i0 is None:      # fire 步非 actuation(理论不出现)
                n_never[fam] += 1
                continue
            tR_i = None
            for j in range(i0 + 1, len(acts)):
                s = acts[j]
                if fire_validated(fire["node"], [(s["command"]["action"],
                                                  s.get("result") or {},
                                                  bool(s.get("libero_terminated")))]):
                    tR_i = j
                    break
            if tR_i is None:
                n_never[fam] += 1
                continue
            if not tl_ok:
                seg = {"segment_id": f"{dp.name}#f{fi}",
                       "episode_dir": d, "task": meta["task"],
                       "seed": meta["seed"], "node": fire["node"],
                       "family": fam, "t0": fire["step_idx"],
                       "tR": acts[tR_i]["step_idx"],
                       "label": "UNRESOLVED",
                       "label_sub": "no-transcript" if tl is None
                       else "align-fail",
                       "fid": None}
                segs.append(seg)
                continue
            got = analyze_segment(tl, fire, tR_i, steps_by_idx)
            if got[0] == "beyond":
                segs.append({"segment_id": f"{dp.name}#f{fi}",
                             "episode_dir": d, "task": meta["task"],
                             "seed": meta["seed"], "node": fire["node"],
                             "family": fam, "t0": fire["step_idx"],
                             "tR": acts[tR_i]["step_idx"],
                             "label": "UNRESOLVED",
                             "label_sub": "beyond-transcript",
                             "fid": None})
                continue
            seg, annot = got
            seg["tR_offset"] = tR_i - i0      # 窗口动作跨度(t0→tR)
            seg["segment_id"] = f"{dp.name}#f{fi}"
            seg["episode_dir"] = d
            seg["task"] = meta["task"]
            seg["seed"] = meta["seed"]
            seg["pre_sig"] = pre_signature(
                tl, next(i for i, s in enumerate(tl["act_steps"])
                         if s["step_idx"] == fire["step_idx"]))
            segs.append(seg)
            annot["segment_id"] = seg["segment_id"]
            annot["window"] = [
                {"seq": e["seq"], "kind": e["kind"], "name": e["name"]}
                for e in annot.pop("win_events")]
            annots.append(annot)

    # ---- D 判据(二遍:跨轨迹分组) ----------------------------------------
    groups = defaultdict(list)
    for s in segs:
        if s.get("label") == "UNRESOLVED":
            continue
        groups[group_key(s, s.get("pre_sig", ""))].append(s)
    n_d_groups = 0
    for key, members in groups.items():
        hit = False
        for a in members:
            for b in members:
                if a is b:
                    continue
                n = min(len(a["phys"]), len(b["phys"]))
                for j in range(n - 1):
                    if a["phys"][j]["out"] and b["phys"][j]["out"] \
                            and a["phys"][j]["out"] != b["phys"][j]["out"]:
                        pa, pb = a["phys"][j + 1], b["phys"][j + 1]
                        diff = (af(pa["action"]) != af(pb["action"])
                                or (pa.get("xyz") and pb.get("xyz") and (
                                    sum((x - y) ** 2 for x, y in
                                        zip(pa["xyz"], pb["xyz"])) ** 0.5 > 0.05))
                                or pa.get("prompt") != pb.get("prompt"))
                        if diff:
                            hit = True
                            break
                if hit:
                    break
            if hit:
                break
        if hit:
            n_d_groups += 1
            for m in members:
                m["D"] = True
                m.setdefault("detail", {}).setdefault("D", []).append(
                    f"组{key}第{j+1}位分叉")
            # D 变化可能改变标签:重判一遍
            for m in members:
                strong = m["A"] or m["B"] or m["C"] or m["D"]
                if strong and m["label"] not in ("OPTION_REQUIRED",):
                    m["label"] = "OPTION_REQUIRED"
                    m["label_sub"] = "D-late"
                m["fid"] = bool(m["A"] or m["B"] or m["C"] or m["D"] or m["E"])

    # ---- 产物落盘 ----------------------------------------------------------
    with open(REPO / "analysis/stageM0_recovery_segments.jsonl", "w") as f:
        for s in segs:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(REPO / "analysis/stageM0_event_annotations.jsonl", "w") as f:
        for a in annots:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    fields = ["segment_id", "task", "seed", "family", "node", "t0", "tR",
              "tR_reason", "tR_offset", "pre_sig", "primitive_count",
              "n_observe", "n_ground", "n_verify_pos", "n_verify_neg",
              "n_replan_turns", "wall_s", "A", "B", "C", "D", "E",
              "label", "label_sub", "fid", "unknown_rate"]
    with open(REPO / "analysis/stageM0_abstraction_labels.csv", "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in segs:
            w.writerow(s)

    # ---- 池级统计 ----------------------------------------------------------
    lab = Counter(s["label"] for s in segs)
    print("fires by fam:", dict(n_fires))
    print("never-validated by fam:", dict(n_never))
    print("segments:", len(segs), "| labels:", dict(lab))
    print("align fail / no transcript:", len(align_fail))
    for d, r in align_fail[:10]:
        print("  ", d.split("ovpm_exp/")[-1][:60], r)
    print("D groups hit:", n_d_groups, "/", len(groups))
    byfam = defaultdict(Counter)
    for s in segs:
        byfam[s["family"]][s["label"]] += 1
    for fam, c in sorted(byfam.items()):
        print(fam, dict(c))
    print("K-side fire_step cross-check:", k_side_check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
