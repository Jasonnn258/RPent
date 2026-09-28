#!/usr/bin/env python3
"""Stage H1 分析器(prereg stageH1_prereg.md §5 指标 + §7 门,冻结定义)。

数据:outcome_validation_runs.csv 的 stage==h1 行 + 各 episode 的
states.json / memory_events.jsonl。冻结 30 格(ovpm_exp.H1_CELLS)之外
的行(如 DEV 冒烟格 3:19)默认排除,--include-smoke 可附带查看。

对齐方法(§5 "事件日志 + states.json 对齐"):每集用**运行时同一代码**
(DecisionMemory mode=graph + graph_block)重放该集 states.json 得到
fire 步位/节点/合法边 —— replay 校验(analysis/stageH1_replay_validation.md)
已证明该重放与运行时 fire 逐点一致;再与 memory_events.jsonl 事件
逐一交叉核对(数量 + 节点序),不一致的集从 fire 类指标剔除并如实列出。

用法: python scripts/analyze_stageH1.py [--include-smoke]
产物: analysis/stageH1_results.md / analysis/stageH1_results.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from ovpm_exp import H1_CELLS, P0_SUITE, RUNS_CSV  # noqa: E402
from rpent.memory.retrieval import (  # noqa: E402
    DecisionMemory, GENERIC_REFRESH_BLOCK,
)
from rpent.graph.schema import load_graph  # noqa: E402
from rpent.graph.render import render_block  # noqa: E402

ARMS = ("h1P2", "h1C", "h1G")
ARM_LABEL = {"h1P2": "P2", "h1C": "CARD", "h1G": "GRAPH"}
INFRA = ("infra_crash", "infra_timeout")

# ---- prereg §5 冻结映射:action_family -> 原语集(词面) ----------------
_ALL_PRIMS = ("pi0_pick", "pi0_doubled", "move_to", "move_pose", "release",
              "set_gripper", "rotate_wrist", "rotate_pitch")
ACTION_FAMILY_PRIMS = {
    "perceive": {"segment", "detect", "back_project"},
    "perceive_hires": {"segment", "detect", "back_project"},
    "grasp": {"pi0_pick"}, "grasp_retry": {"pi0_pick"},
    "grasp_offset": {"pi0_pick", "move_pose", "rotate_wrist", "rotate_pitch"},
    "verify_hold": {"detect", "segment"},
    "transport": {"move_to", "move_pose"},
    "move_waypoint": {"move_to", "move_pose"},
    "retreat_reapproach": {"move_to", "move_pose"},
    "approach": {"move_to", "move_pose"},
    "grip_adjust_retry": {"set_gripper", "pi0_pick"},
    "contact_settling": {"pi0_doubled", "move_pose"},
    "place": {"release", "move_to", "move_pose"},
    "micro_reposition": {"move_to", "move_pose", "rotate_wrist"},
    "repick_replace": {"pi0_pick", "move_to", "release"},
    "observe": {"detect", "segment", "view_driver_state"},
    "planner_judgment": set(_ALL_PRIMS), "finish": set(_ALL_PRIMS),
}

NODE_FAMILY = {"FALSE_GRASP": "FALSE_GRASP",
               "MOVE_STALL": "MOVE_CONTACT_STALL",
               "CONTACT_STALL": "MOVE_CONTACT_STALL",
               "RELEASE_PREDICATE_STALL": "RELEASE_PREDICATE_STALL"}
FAMILIES = ("FALSE_GRASP", "MOVE_CONTACT_STALL", "RELEASE_PREDICATE_STALL")

VR_WINDOW = 5      # §5 validated_recovery 窗口(primitive steps)
PIP_WINDOW = 3     # §5 post_intervention_progress@3(诊断)
LIFT_OK = 0.005    # §5 真实握持判据
MOVE_OK = 0.03     # §5 到位判据
BANNED = ("fail", "error", "could not", "no object")  # B2 违禁词(冒烟检查)


class FakeTracker:
    def current_phase(self):
        return "analyze"

    def recovery_pending(self):
        return False


def replay_env():
    for k in ("RPENT_MEMORY_TRIGGER", "RPENT_MEMORY_INJECTION_MODE",
              "RPENT_MEMORY_QUERY_MODE", "RPENT_MEMORY_RANK",
              "RPENT_MEMORY_QUERY_REASON", "RPENT_MEMORY_BLOCK_REASON"):
        os.environ.pop(k, None)
    os.environ.update({
        "RPENT_MEMORY_TRIGGER": "graph",
        "RPENT_MEMORY_INJECTION_MODE": "graph_block",
        "RPENT_MEMORY_QUERY_MODE": "common",
        "RPENT_MEMORY_RANK": "Q0_FIXED",
        "RPENT_MEMORY_QUERY_REASON": "0",
    })


def replay_fires(steps):
    """一集 states.json 过运行时 graph 触发路径 →
    [ {step_idx, node, edges(合法边 id), facts} ]。"""
    replay_env()
    dm = DecisionMemory(FakeTracker(), mode="graph")
    fires = []
    for i, step in enumerate(steps):
        name = (step.get("command") or {}).get("action")
        if name is None:
            continue  # init 记录
        res = step.get("result") or {}
        data = {**res, "libero_terminated": step.get("libero_terminated")}
        dm.on_tool_result(name, json.dumps(data), False)
        out = dm.turn_boundary(i + 1)
        if out is not None:
            _blk, ev = out
            fires.append({"step_idx": i, "node": ev["graph_node"],
                          "edges": ev["graph_legal_edges"]})
    return fires


def load_events(d):
    p = Path(d) / "memory_events.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text().splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


def next_act_steps(steps, i, w):
    """fire 步 i 之后的前 w 个 actuation 步 [(action, result, term)]。"""
    out = []
    for s in steps[i + 1:]:
        a = (s.get("command") or {}).get("action")
        if a is None:
            continue
        out.append((a, s.get("result") or {},
                    bool(s.get("libero_terminated"))))
        if len(out) >= w:
            break
    return out


def lift_ok(r):
    """pi0_pick 真实握持:success=True 且 peak_lift_m >= 0.005(§5)。"""
    if r.get("success") is not True:
        return False
    v = r.get("peak_lift_m")
    return isinstance(v, (int, float)) and v >= LIFT_OK


def fire_validated(node, win):
    """§5 家族级物理证据验证(W 窗口)。"""
    for a, r, term in win:
        if term:
            return True
        if node == "FALSE_GRASP":
            if a == "pi0_pick" and lift_ok(r):
                return True
        elif node == "MOVE_STALL":
            d = r.get("final_dist_m")
            if a in ("move_to", "move_pose") \
                    and isinstance(d, (int, float)) and d < MOVE_OK:
                return True
        elif node == "CONTACT_STALL":
            if a == "pi0_doubled" and r.get("success") is True:
                return True
            if a == "pi0_pick" and lift_ok(r):
                return True
        elif node == "RELEASE_PREDICATE_STALL":
            if a == "pi0_pick" and lift_ok(r):
                return True
    return False


def mapped_prims(edge_ids, g, with_af_names=False):
    """active node 合法边 action_family 映射原语集(§5 冻结映射)。

    with_af_names=True 时并上合法边 action_family 名本身(prereg §5
    2026-09-28 修订:wrong_phase 的匹配词表 —— graph v0 渲染词汇是
    action_family,不是原语名;guard_violation 仍用纯原语集)。"""
    prims: set[str] = set()
    for eid in edge_ids:
        e = g.edge(eid)
        if e is None:
            raise ValueError(f"edge {eid} not in frozen graph")
        af = e.action_family
        if af not in ACTION_FAMILY_PRIMS:
            raise ValueError(f"action_family {af!r} 不在 prereg §5 冻结映射")
        prims |= ACTION_FAMILY_PRIMS[af]
        if with_af_names:
            prims.add(af)
    return prims


def reconstruct_block(arm, ev, node, edge_ids, g, dm_card):
    """逐字节重建该 fire 的注入块(三臂内容均确定性可重建)。
    返回 (block | None, wrong_phase_denominator_included)。"""
    if arm == "h1P2":
        return GENERIC_REFRESH_BLOCK, True
    if arm == "h1C":
        ids = ev.get("top3_memories") or []
        if ev.get("retrieval_status") == "EMPTY" or not ids:
            return None, False  # 无注入 → 不进 wrong_phase 分母(保守口径)
        return dm_card._memory_only_block(ids), True
    edges = [g.edge(eid) for eid in edge_ids]
    return render_block(g, node, edges), True


def wilson(k, n, z=1.96):
    """二项 95% Wilson CI。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / denom
    half = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / denom
    return (max(0.0, ctr - half), min(1.0, ctr + half))


def fmt_ci(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n:.1%}) CI[{lo:.1%},{hi:.1%}]" if n else "0/0"


def pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-smoke", action="store_true",
                    help="附带分析 30 格之外的行(如冒烟格 3:19),"
                         "不计入正式判定")
    args = ap.parse_args()

    g = load_graph()
    # CARD 块重建器(冻结卡库;env = h1C 臂)
    os.environ.update({
        "RPENT_MEMORY_TRIGGER": "graph",
        "RPENT_MEMORY_INJECTION_MODE": "memory_only",
        "RPENT_MEMORY_QUERY_MODE": "common",
        "RPENT_MEMORY_RANK": "Q0_FIXED",
        "RPENT_MEMORY_QUERY_REASON": "0",
        "RPENT_MEMORY_BLOCK_REASON": "0",
    })
    dm_card = DecisionMemory(FakeTracker(), mode="graph")

    frozen_cells = set(H1_CELLS)
    rows_by_key = {}
    with open(RUNS_CSV) as f:
        for r in csv.DictReader(f):
            if r["stage"] != "h1" or r["suite"] != P0_SUITE:
                continue
            key = (r["cond"], int(r["task"]), int(r["seed"]))
            rows_by_key[key] = r  # 同 key 多行时保留最后一行
    smoke_rows = {k: v for k, v in rows_by_key.items()
                  if (k[1], k[2]) not in frozen_cells}
    main_rows = {k: v for k, v in rows_by_key.items()
                 if (k[1], k[2]) in frozen_cells}

    # 每集分析结果:{(arm,cell): {...}}
    eps = {}
    mismatches, infra_missing, banned_hits, empty_legal = [], [], [], []
    pool = dict(main_rows)
    if args.include_smoke:
        pool.update(smoke_rows)
    for (arm, t, sd), r in sorted(pool.items()):
        d = r["dir"]
        if r["result"] in INFRA:
            infra_missing.append((arm, t, sd, r["result"]))
            continue
        try:
            steps = json.load(open(os.path.join(d, "states.json")))
        except Exception as ex:  # noqa: BLE001
            infra_missing.append((arm, t, sd, f"states.json unreadable: {ex}"))
            continue
        sr = bool(steps[-1].get("libero_terminated"))  # 冻结口径
        events = load_events(d)
        fires = replay_fires(steps)
        # 交叉核对:事件 ↔ 重放(数量 + 节点序)
        ev_nodes = [e["trigger_reason"].split("=", 1)[1]
                    for e in events if "=" in e.get("trigger_reason", "")]
        ok = (len(ev_nodes) == len(fires)
              and all(a == b["node"] for a, b in zip(ev_nodes, fires)))
        if not ok:
            mismatches.append((arm, t, sd, len(events), len(fires)))
        rec = {"arm": arm, "task": t, "seed": sd, "sr": sr,
               "fires": [], "ok": ok}
        if ok:
            for ev, fr in zip(events, fires):
                node, i, eids = fr["node"], fr["step_idx"], fr["edges"]
                win = next_act_steps(steps, i, VR_WINDOW)
                rec["fires"].append({
                    "step_idx": i, "node": node, "edges": eids,
                    "validated": fire_validated(node, win),
                    "pip3": fire_validated(node, next_act_steps(
                        steps, i, PIP_WINDOW)),
                })
                blk, in_wp = reconstruct_block(arm, ev, node, eids, g, dm_card)
                prims = mapped_prims(eids, g)
                wp_vocab = mapped_prims(eids, g, with_af_names=True)
                if not eids:
                    empty_legal.append((arm, t, sd, i, node))
                rec["fires"][-1]["block"] = blk
                rec["fires"][-1]["wp_denom"] = in_wp
                rec["fires"][-1]["wrong_phase"] = (
                    in_wp and (blk is None or not any(
                        p in (blk or "").lower() for p in wp_vocab)))
                if blk is not None:
                    low = blk.lower()
                    hit = [b for b in BANNED if b in low]
                    if hit:
                        banned_hits.append((arm, t, sd, i, hit))
                # guard_violation(仅 GRAPH 面使用):fire 后下一条动作原语
                nxt = next_act_steps(steps, i, 1)
                rec["fires"][-1]["next_prim"] = nxt[0][0] if nxt else None
                rec["fires"][-1]["guard_set"] = prims
        eps[(arm, t, sd)] = rec

    # ------------------------------------------------------------ 聚合
    def arm_eps(arm):
        return [eps[k] for k in eps if k[0] == arm and (k[1], k[2]) in frozen_cells]

    stats = {}
    for arm in ARMS:
        es = arm_eps(arm)
        n = len(es)
        sr_k = sum(e["sr"] for e in es)
        ok_es = [e for e in es if e["ok"]]
        fires = [f for e in ok_es for f in e["fires"]]
        fired_eps = [e for e in ok_es if e["fires"]]
        vred = [e for e in fired_eps
                if any(f["validated"] for f in e["fires"])]
        st = {"n": n, "sr": (sr_k, n), "n_fires": len(fires),
              "fired_eps": len(fired_eps),
              "vr": (len(vred), len(fired_eps)),
              "wp": (sum(f["wrong_phase"] for f in fires
                         if f["wp_denom"]),
                     sum(1 for f in fires if f["wp_denom"])),
              "pip3": (sum(f["pip3"] for f in fires), len(fires)),
              "fam": {}}
        for fam in FAMILIES:
            fe = [e for e in fired_eps
                  if any(NODE_FAMILY[f["node"]] == fam for f in e["fires"])]
            vk = [e for e in fe if any(
                f["validated"] and NODE_FAMILY[f["node"]] == fam
                for f in e["fires"])]
            st["fam"][fam] = (len(vk), len(fe))
        if arm == "h1G":
            gv_d = [f for f in fires if f["next_prim"] is not None]
            st["gv"] = (sum(1 for f in gv_d
                            if f["next_prim"] not in f["guard_set"]), len(gv_d))
        stats[arm] = st

    # 家族门:cell 级配对指示(全 30 格口径;matched 子集附报)
    fam_gate, fam_detail = {}, {}
    for fam in FAMILIES:
        ctrl = max(("h1C", "h1P2"), key=lambda a: (
            stats[a]["fam"][fam][0] / max(stats[a]["fam"][fam][1], 1)))
        diffs, matched = [], []
        for (t, sd) in H1_CELLS:
            def v(arm):
                e = eps.get((arm, t, sd))
                if not e or not e["ok"] or not e["fires"]:
                    return 0
                return int(any(f["validated"] and NODE_FAMILY[f["node"]] == fam
                               for f in e["fires"]))
            diffs.append(v("h1G") - v(ctrl))
            eg, ec = eps.get(("h1G", t, sd)), eps.get((ctrl, t, sd))
            if eg and ec and eg["ok"] and ec["ok"] \
                    and eg["fires"] and ec["fires"]:
                matched.append(diffs[-1])
        fam_gate[fam] = (sum(diffs) >= 0, ctrl, sum(diffs), len(diffs),
                         sum(matched) >= 0 if matched else None,
                         len(matched))
        fam_detail[fam] = diffs

    # ------------------------------------------------------------ 门槛
    vr = {a: (stats[a]["vr"][0] / stats[a]["vr"][1]
              if stats[a]["vr"][1] else None) for a in ARMS}
    sr = {a: (stats[a]["sr"][0] / stats[a]["sr"][1]
              if stats[a]["sr"][1] else None) for a in ARMS}
    wp = {a: (stats[a]["wp"][0] / stats[a]["wp"][1]
              if stats[a]["wp"][1] else None) for a in ARMS}
    inconclusive_vr = any(stats[a]["vr"][1] < 20 for a in ARMS)
    m1 = None if (wp["h1G"] is None or wp["h1C"] is None) \
        else wp["h1G"] <= 0.5 * wp["h1C"]
    gv = stats["h1G"].get("gv")
    m2 = None if gv is None or gv[1] == 0 else gv[0] / gv[1] <= 0.02
    max_vr = max((v for v in (vr["h1C"], vr["h1P2"]) if v is not None),
                 default=None)
    max_sr = max((v for v in (sr["h1C"], sr["h1P2"]) if v is not None),
                 default=None)
    gate_a = (vr["h1G"] is not None and max_vr is not None
              and vr["h1G"] >= max_vr + 0.10
              and sr["h1G"] is not None and sr["h1G"] >= max_sr - 0.03)
    gate_b = (sr["h1G"] is not None and max_sr is not None
              and sr["h1G"] >= max_sr + 0.08
              and vr["h1G"] is not None and vr["h1G"] >= (max_vr or 0))
    # 行为门 3pp 边界带(prereg §7 "行为门差 ≤3pp" 的操作化:门公式各
    # 阈值放宽 0.03;如实记录,判 PARTIALLY 而非 SUPPORTED)
    gate_a_band = (vr["h1G"] is not None and max_vr is not None
                   and vr["h1G"] >= max_vr + 0.07
                   and sr["h1G"] is not None and sr["h1G"] >= max_sr - 0.06)
    gate_b_band = (sr["h1G"] is not None and max_sr is not None
                   and sr["h1G"] >= max_sr + 0.05
                   and vr["h1G"] is not None
                   and vr["h1G"] >= (max_vr or 0) - 0.03)
    fam_n = sum(1 for fam in FAMILIES if fam_gate[fam][0])
    mech = (m1 is True and m2 is True)
    if mech and (gate_a or gate_b) and fam_n >= 2:
        verdict = "REPRESENTATION SUPPORTED"
    elif mech and (gate_a_band or gate_b_band):
        verdict = "REPRESENTATION PARTIALLY SUPPORTED(行为门差 ≤3pp)"
    else:
        verdict = "REPRESENTATION NOT SUPPORTED"

    # ------------------------------------------------------------ 报告
    L = []
    A = L.append
    A("# Stage H1 结果 — Frozen Graph vs Flat Cards vs Generic Refresh\n")
    A("_2026-09-28 by scripts/analyze_stageH1.py(指标/门 = "
      "analysis/stageH1_prereg.md §5/§7 冻结定义)。_")
    A("")
    A(f"- 冻结 30 格 × 3 臂 = 90;有效集 {len(eps)}"
      f"(infra 缺失 {len(infra_missing)});"
      f"冒烟/格 外行 {len(smoke_rows)}"
      f"{'(已排除)' if not args.include_smoke else '(--include-smoke 附带)'}")
    if inconclusive_vr:
        A(f"- **INCONCLUSIVE-VR 降级**:某臂有 fire 的 episode < 20"
          f"(prereg §6)— VR 面如实降级,SR 面照判")
    if mismatches:
        A(f"- **触发重放交叉核对不一致 {len(mismatches)} 集**(已从 fire "
          f"类指标剔除,SR 保留):{mismatches[:10]}")
    else:
        A("- 触发重放交叉核对:全部一致(事件 ↔ 重放 fire 逐点)")
    A("")
    A("## 主表(per arm)\n")
    A("| 指标 | P2(泛型) | CARD(扁平卡) | GRAPH(冻结图) |")
    A("|---|---|---|---|")
    A(f"| n(有效集) | {stats['h1P2']['n']} | {stats['h1C']['n']} "
      f"| {stats['h1G']['n']} |")
    A(f"| SR | {fmt_ci(*stats['h1P2']['sr'])} | "
      f"{fmt_ci(*stats['h1C']['sr'])} | {fmt_ci(*stats['h1G']['sr'])} |")
    A(f"| fires 总数(均/集) | {stats['h1P2']['n_fires']} "
      f"({stats['h1P2']['n_fires'] / max(stats['h1P2']['n'], 1):.1f}) | "
      f"{stats['h1C']['n_fires']} "
      f"({stats['h1C']['n_fires'] / max(stats['h1C']['n'], 1):.1f}) | "
      f"{stats['h1G']['n_fires']} "
      f"({stats['h1G']['n_fires'] / max(stats['h1G']['n'], 1):.1f}) |")
    A(f"| 有 fire 的 episode | {stats['h1P2']['fired_eps']} | "
      f"{stats['h1C']['fired_eps']} | {stats['h1G']['fired_eps']} |")
    A(f"| validated_recovery(episode 级) | {fmt_ci(*stats['h1P2']['vr'])} | "
      f"{fmt_ci(*stats['h1C']['vr'])} | {fmt_ci(*stats['h1G']['vr'])} |")
    A(f"| wrong_phase_advice_rate(fire 级) | "
      f"{fmt_ci(*stats['h1P2']['wp'])} | {fmt_ci(*stats['h1C']['wp'])} | "
      f"{fmt_ci(*stats['h1G']['wp'])} |")
    A(f"| post_intervention_progress@3(诊断) | "
      f"{fmt_ci(*stats['h1P2']['pip3'])} | "
      f"{fmt_ci(*stats['h1C']['pip3'])} | "
      f"{fmt_ci(*stats['h1G']['pip3'])} |")
    if gv:
        A(f"| guard_violation_rate(GRAPH 专属) | — | — | "
          f"{fmt_ci(*gv)} |")
    A("")
    A("### VR per family(episode 级;分母 = 该家族有 fire 的集数)\n")
    A("| 家族 | P2 | CARD | GRAPH |")
    A("|---|---|---|---|")
    for fam in FAMILIES:
        A(f"| {fam} | {fmt_ci(*stats['h1P2']['fam'][fam])} | "
          f"{fmt_ci(*stats['h1C']['fam'][fam])} | "
          f"{fmt_ci(*stats['h1G']['fam'][fam])} |")
    A("")
    A("## 门槛(prereg §7)\n")
    A("| 门 | 定义 | 实测 | 判定 |")
    A("|---|---|---|---|")
    A(f"| M1 wrong_phase | GRAPH ≤ 0.5×CARD | "
      f"{pct(wp['h1G'])} vs ≤"
      f"{pct(0.5 * wp['h1C']) if wp['h1C'] is not None else 'n/a(CARD 分母 0)'} | "
      f"{'PASS' if m1 else ('FAIL' if m1 is False else 'N/A')} |")
    if gv:
        gv_txt = (f"{gv[0] / gv[1]:.1%} ({gv[0]}/{gv[1]})"
                  if gv[1] else "0/0")
        A(f"| M2 guard_violation | GRAPH ≤ 2% | {gv_txt} | "
          f"{'PASS' if m2 else ('FAIL' if m2 is False else 'N/A')} |")
    A(f"| 行为门 A | VR_G ≥ max(VR_ctrl)+10pp 且 SR_G ≥ max(SR_ctrl)−3pp | "
      f"VR {pct(vr['h1G'])} vs {pct(max_vr)}+10pp;SR "
      f"{pct(sr['h1G'])} vs {pct(max_sr)}−3pp | "
      f"{'PASS' if gate_a else 'FAIL'} |")
    A(f"| 行为门 B | SR_G ≥ max(SR_ctrl)+8pp 且 VR_G ≥ max(VR_ctrl) | "
      f"SR {pct(sr['h1G'])} vs {pct(max_sr)}+8pp;VR {pct(vr['h1G'])} vs "
      f"{pct(max_vr)} | {'PASS' if gate_b else 'FAIL'} |")
    for fam in FAMILIES:
        ok30, ctrl, d30, n30, okm, nm = fam_gate[fam]
        A(f"| 家族门 {fam} | GRAPH−{ARM_LABEL[ctrl]} 配对差 ≥ 0 "
          f"(全 {n30} 格) | Σdiff={d30:+d}"
          f"{f'(matched {nm} 格 Σ={okm})' if nm else ''} | "
          f"{'PASS' if ok30 else 'FAIL'} |")
    A(f"| 家族门合计 | ≥2/3 | {fam_n}/3 | "
      f"{'PASS' if fam_n >= 2 else 'FAIL'} |")
    A("")
    A(f"## 判定\n**{verdict}**\n")
    A("## 口径备注(操作化声明)")
    A("- fire 步位 = 运行时同一触发代码对该集 states.json 的重放"
      "(replay 校验已证一致),并与 memory_events.jsonl 逐点交叉核对;")
    A("- wrong_phase:CARD 检索为 EMPTY(无注入)的 fire 不进分母"
      "(保守口径,利于对照);P2 恒为泛型文本(预期全 wrong);匹配词表 = "
      "映射原语集 ∪ 合法边 action_family 名(prereg §5 2026-09-28 修订,"
      "数据前冻结);")
    A("- guard_violation 分母 = fire 后存在下一条动作原语的 fire"
      "(感知步天然不进 states.json;无后续动作原语 = 豁免);")
    A("- PIP@3 为诊断项:相位推进以家族物理证据(§5 验证规则)在 3 步"
      "窗内成立为代理(SM1 逐步相位不在 states.json);")
    A("- 家族门主口径 = 全 30 格 cell 级指示差(含 fire 覆盖);"
      "matched(两臂均有该家族 fire)子集附报。")
    if empty_legal:
        A(f"\n**零合法出边 fire {len(empty_legal)} 次(审计 coverage 应为 0,"
          f"须核查)**:{empty_legal[:10]}")
    if banned_hits:
        A(f"\n**注入块违禁词命中 {len(banned_hits)}**:口径(prereg §3(c)"
          f" 2026-09-28 澄清)——新内容臂(P2/GRAPH)应为 0;CARD 命中为"
          f"冻结 61 卡正文继承(2 张卡 falsify/how_to 含 'fail',G0.5 同款"
          f"注入),如实报告、不改卡:{banned_hits[:10]}")
    if infra_missing:
        A(f"\n### infra 缺失格(未计入,调度器重试后应清零)\n")
        for a, t, sd, r_ in infra_missing:
            A(f"- {a} t{t} s{sd}: {r_}")

    out_md = REPO / "analysis/stageH1_results.md"
    out_md.write_text("\n".join(L))
    payload = {
        "stats": {a: {k: v for k, v in stats[a].items() if k != "fam"}
                  | {"fam": {f: list(stats[a]["fam"][f]) for f in FAMILIES}}
                  for a in ARMS},
        "gates": {"M1": m1, "M2": m2, "A": gate_a, "B": gate_b,
                  "family_n": fam_n,
                  "family": {f: {"pass": fam_gate[f][0], "ctrl": fam_gate[f][1],
                                 "sum_diff": fam_gate[f][2],
                                 "n_cells": fam_gate[f][3]} for f in FAMILIES}},
        "verdict": verdict, "inconclusive_vr": inconclusive_vr,
        "n_eps": len(eps), "n_infra_missing": len(infra_missing),
        "n_mismatch": len(mismatches), "n_banned": len(banned_hits),
    }
    (REPO / "analysis/stageH1_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1))
    print("\n".join(L[:40]))
    print(f"\nwrote {out_md}")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
