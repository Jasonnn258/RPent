#!/usr/bin/env python
"""Stage N §5 — N0 Analyzer v2:事件级 control-dependency 确定性测量(纯离线)。

与 Stage M analyzer 的关系:复用其数据通路(池加载/transcript 对齐/窗口构造/
states.json 结果权威),**完全替换标注逻辑** —— M 的 A-E 判据废弃,v2 按
analysis/stageN0_analyzer_spec.md 对窗口内每个中间 information event 判
CONTROL_DEPENDENT / CONTROL_INDEPENDENT / UNRESOLVED,段级聚合
DEPENDENT ≻ UNRESOLVED ≻ INDEPENDENT(零信息事件 → INDEPENDENT)。

信息事件本体:OBSERVE(read_image/view_driver_state)/ GROUNDING
(back_project/segment)/ VERIFIER(动作级验证结果到达,排除 t0 自身——
t0 结果是 fire 定义,属 initiation 不属中间反馈)/ STATE_UPDATE
(窗口内 libero_terminated 翻转)。

产物(analysis/):
- stageN0_information_events.jsonl  逐段信息事件 + 事件级标签 + 证据 span
- stageN0_control_labels.csv        段级标签表(抽样分层/盲审比对用)

用法:
  python scripts/stageN0_analyze.py            # 全池
  python scripts/stageN0_analyze.py --dev      # 仅旧 33 audit 样本(开发校准,
                                               # 与 M 人工答案打混淆矩阵)
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from analyze_stageH1 import NODE_FAMILY, fire_validated, replay_fires  # noqa: E402
from stageM0_analyze import (  # noqa: E402
    GROUND_TOOLS, OBSERVE_TOOLS, PRIMS, af, build_timeline, flat_events,
    load_steps, outcome_of, seg_events_window)

# ===========================================================================
# 冻结常量区(spec §4;判据改动 = 偏离 = 测量作废)
# ===========================================================================
# ---- B′:grounding 数值 → 动作参数链接容差 --------------------------------
XY_TOL = 0.025       # 水平距离(米)
DZ_TOL = 0.20        # z 差(接近高度参数,悬停逼近合法偏高)
# ---- C′:参数依赖 ---------------------------------------------------------
PARAM_DELTA = 0.01   # 同族动作参数改变阈值(euclid)
TXT_TRIPLE_TOL = 0.01  # 文本十进制三元组 ↔ 动作 xyz 逐分量容差
# ---- D′:负验证 → 控制变更 ------------------------------------------------
MOVE_CHANGE = 0.05   # move 参数变更判阈值(euclid;与 M 的 D 同值)
# ---- A′/D′/F′ 文本正则族(planner 语言为英文;中文保底) -------------------
RE_ASSERT = re.compile(
    r"(?i)\b(confirm(?:ed|s)?|verif(?:y|ies|ied)|see(?:n|s)?|visible|"
    r"appear(?:s|ed)?|show(?:n|s)?|observ(?:e|ed)|indeed|sits?|sitting|"
    r"lying|seated|empty|missing|gone|tilted|leaning|occluded|upright|"
    r"inverted|knocked|perched|still (?:on|in|at|false|true|not)|"
    r"is now|are now|was still|were still)\b")
RE_COND = re.compile(
    r"(?i)\b(if|whether|unless|otherwise|match(?:es|ing)?|exactly|"
    r"consistent with|failure mode|known (?:case|mode)|recipe|still false|"
    r"still not|still true|not settled|wrong|instead)\b")
RE_DECIDE = re.compile(
    r"(?i)\b(follow|apply|proceed|execute|so:|therefore|thus|next step|"
    r"will now|let me|going to|repick|re-?grasp|retry|plan:|the plan is|"
    r"switch to|fall back)\b")
RE_PURPOSE = re.compile(
    r"(?i)\bto (?:confirm|verify|see (?:if|whether)|check (?:if|whether))\b|"
    r"need to see|i need to see\b")
# 观察断言须在结果到达之后(post 段);条件/目的/决定可在整 span
# ---- D′ 正验证门控:验证量断言 --------------------------------------------
RE_VERIFY_ASSERT = re.compile(
    r"(?i)\b(lift(?:ed)?|success(?:ful)?|grasp(?:ed)?|gripper (?:is |has )?"
    r"(?:closed|open)|final_?dist|in position|reached|arrived|holding)\b")
# ---- F′:不可达/掉落 → 改道;已完成 → 终止 --------------------------------
RE_F_SWITCH = re.compile(
    r"(?i)\b(unreachable|cannot reach|can't reach|cannot be reached|"
    r"too (?:far|high|low)|out of reach|knocked (?:off|over)|fell off|"
    r"dropped|displaced|not present|no longer (?:there|visible))\b")
RE_F_TERM = re.compile(
    r"(?i)\b(already (?:done|solved|placed|seated|succeeded)|nothing "
    r"(?:more|else) to do|goal (?:is |has been )?(?:met|achieved|done)|"
    r"terminat(?:e|ing|ion)|end(?:ing)? (?:the )?episode|finish(?:ing)? "
    r"(?:the )?(?:episode|task))\b")
# ---- D′ 正验证资格:t0-uncertainty 测试 -----------------------------------
# 配对 1:条件标记 … 动作级验证量;配对 2:验证量 … 顺序词。
# 刻意排除 terminated/predicate/still false —— 与 t0 值相同的集级 predicate
# 复读是冗余信道,不构成新信息(见 spec 附录 A)。
RE_VC_A = re.compile(
    r"(?i)\b(if|whether|unless|since|because|now that|in case)\b"
    r"[^.!;]{0,80}\b(lift(?:ed|ing)?|success(?:ful)?|fail(?:ed|ing)?|"
    r"grasp(?:ed|ing)?|gripp?er|final_?dist|reached|in position|seated|"
    r"holds?|holding|closed|open(?:ed)?)\b")
RE_VC_B = re.compile(
    r"(?i)\b(lift(?:ed|ing)?|success(?:ful)?|fail(?:ed|ing)?|"
    r"grasp(?:ed|ing)?|gripp?er|final_?dist|reached|in position|seated|"
    r"holds?|holding|closed|open(?:ed)?)\b[^.!;]{0,60}"
    r"\b(then|next|so\b|proceed|continue|→)\b")
# ---- EC5(c) 无条件顺序计划承诺 + 条件标记否决 ----------------------------
RE_SEQ_PLAN = re.compile(
    r"(?i)\b(retreat|descend|move(?:_to)?|approach|rotate|re-?pick|"
    r"pi0_pick|pick|release|set_?gripp?er|gripper)\b"
    r"[^.!;]{0,100}?\b(?:then|next|after that|followed by|before)\b"
    r"[^.!;]{0,100}?\b(retreat|descend|move(?:_to)?|approach|rotate|"
    r"re-?pick|pi0_pick|pick|release|set_?gripp?er|gripper)\b")
RE_COND_ANY = re.compile(
    r"(?i)\b(if|whether|unless|still false|still not|in case)\b")
FAM_WORDS = {"retreat": "move", "descend": "move", "move": "move",
             "move_to": "move", "approach": "move", "rotate": "move",
             "repick": "pick", "re-pick": "pick", "pi0_pick": "pick",
             "pick": "pick", "release": "gripper", "set_gripper": "gripper",
             "gripper": "gripper"}
# ---- C′:偏移量表达(带符号十进制) ---------------------------------------
RE_SIGNED_DEC = re.compile(r"[+−\-]\s?\d+\.\d+")
RE_OFFSET_WORD = re.compile(
    r"(?i)\b(offset|shift|correct(?:ed|ion)?|true held|drift|bias|"
    r"measur(?:e|ed|ement)|偏|差|修正)\b")
# ---- E′:目标实体名词差异(stopword 裁剪) -------------------------------
STOP_NOUNS = {
    "pick", "picks", "up", "the", "and", "put", "place", "onto", "into",
    "in", "on", "table", "then", "from", "with", "this", "that", "over",
    "near", "short", "local", "bowl", "object", "item", "target", "one",
}
# ---- 数据质量 -------------------------------------------------------------

def load_msgs(d: Path):
    """transcript → (msgs, {mi: assistant 文本(thinking+text 拼接)})."""
    tf = sorted(d.glob("transcript_*.json"))
    if not tf:
        return None, None
    msgs = json.load(open(tf[0]))["messages"]
    texts = {}
    for mi, m in enumerate(msgs):
        if m["role"] != "assistant":
            continue
        parts = []
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if b.get("type") == "thinking":
                    parts.append(b.get("thinking") or "")
                elif b.get("type") == "text":
                    parts.append(b.get("text") or "")
        texts[mi] = "\n".join(parts)
    return msgs, texts


def span_texts(texts, lo_mi: int, hi_mi: int):
    """(lo_mi, hi_mi] 内的 assistant 文本拼接与逐 mi 列表。"""
    per = [(mi, t) for mi, t in texts.items() if lo_mi < mi <= hi_mi]
    return per, "\n".join(t for _, t in per)


def rounded_variants(v: float):
    """数值的打印形态集合(planner 常按 2-4 位舍入)。"""
    out = set()
    for nd in (2, 3, 4):
        s = f"{v:.{nd}f}"
        out.add(s)
        if s.startswith("0."):
            out.add(s[1:])           # ".123" 形态
        if s.startswith("-0."):
            out.add("-" + s[2:])
    return out


def xyz_in_text(text: str, xyz) -> int:
    """文本中出现 xyz 几个分量(舍入形态匹配)。"""
    n = 0
    for v in xyz:
        if any(s in text for s in rounded_variants(v)):
            n += 1
    return n


def find_match(rex, text: str):
    """首个命中 + 上下文截断(证据 span 落盘用)。"""
    m = rex.search(text)
    if not m:
        return None
    a, b = m.span()
    return text[max(0, a - 60):min(len(text), b + 60)].replace("\n", " ")[:180]


class SegmentV2:
    """一个 recovery segment 的 v2 标注。"""

    def __init__(self, tl, texts, fire, t0, tR, steps_by_idx, n_msgs):
        self.tl, self.texts = tl, texts
        self.fire, self.t0, self.tR = fire, t0, tR
        self.steps = steps_by_idx
        self.n_msgs = n_msgs
        self.events = []      # 信息事件(带标签)
        self.phys = []        # 执行过的动作

    # ---- 基础构造 ----------------------------------------------------------
    def build(self, win, t0_seq, tR_seq):
        tl = self.tl
        res_of_use = {e.get("use_seq"): e for e in tl["events"]
                      if e["kind"] == "res"}
        use_pos = {u["seq"]: i for i, u in enumerate(tl["uses"])}
        events = tl["events"]
        # t0 结果到达位置(initiation 边界;其后才是中间信息)
        t0_res = res_of_use.get(t0_seq)
        self.t0_res_seq = t0_res["seq"] if t0_res else t0_seq

        for e in win:
            if e["kind"] != "use":
                continue
            if e["name"] in PRIMS:
                pos = use_pos[e["seq"]]
                step_idx = tl["anchor"][pos]
                if step_idx is None:        # 未执行发射
                    continue
                srow = self.steps[step_idx]
                cmd, res = srow.get("command") or {}, srow.get("result") or {}
                res_e = res_of_use.get(e["seq"]) or {}
                self.phys.append({
                    "seq": e["seq"], "mi_use": e["mi"],
                    "mi_res": res_e.get("mi", e["mi"]),
                    "step": step_idx, "action": e["name"],
                    "cmd": cmd, "res": res if isinstance(res, dict) else {},
                    "out": outcome_of(e["name"],
                                      res if isinstance(res, dict) else {}),
                })
            elif e["name"] in OBSERVE_TOOLS:
                res_e = res_of_use.get(e["seq"]) or {}
                pl = res_e.get("payload")
                ev = {"event_id": None, "kind": "OBSERVE", "tool": e["name"],
                      "seq": e["seq"], "mi_use": e["mi"],
                      "mi_res": res_e.get("mi", e["mi"]),
                      "usable_fields": sorted(pl.keys())
                      if isinstance(pl, dict) else []}
                if isinstance(pl, dict) and "libero_terminated" in pl:
                    ev["libero_terminated"] = pl["libero_terminated"]
                self.events.append(ev)
            elif e["name"] in GROUND_TOOLS:
                res_e = res_of_use.get(e["seq"]) or {}
                pl = res_e.get("payload") if res_e else None
                ev = {"event_id": None, "kind": "GROUNDING", "tool": e["name"],
                      "seq": e["seq"], "mi_use": e["mi"],
                      "mi_res": res_e.get("mi", e["mi"]),
                      "input": e.get("input") or {},
                      "usable_fields": sorted(pl.keys())
                      if isinstance(pl, dict) else []}
                if isinstance(pl, dict):
                    for k in ("world_xyz", "center_xyz", "median_xyz"):
                        if isinstance(pl.get(k), list) and len(pl[k]) == 3:
                            ev[k] = [round(x, 4) for x in pl[k]]
                self.events.append(ev)
        # VERIFIER:动作级验证结果到达(排除 t0 自身;tR 自身结果是
        # validation 边界,不算窗口内中间信息)
        for p in self.phys:
            if p["out"] is None or p["seq"] <= self.t0_res_seq:
                continue
            res_e = res_of_use.get(p["seq"])
            if res_e is None or res_e["seq"] > tR_seq:
                continue
            self.events.append({
                "event_id": None, "kind": "VERIFIER", "tool": p["action"],
                "seq": res_e["seq"], "mi_use": p["mi_use"],
                "mi_res": res_e["mi"], "step": p["step"],
                "outcome": p["out"], "phys_seq": p["seq"]})
        # STATE_UPDATE:窗口内(t0 结果之后、tR 结果之前)libero_terminated 翻转
        prev_flag = bool(self.steps[self.t0].get("libero_terminated"))
        for si in sorted(self.steps):
            if not (self.t0 < si < self.tR):
                continue
            flag = bool(self.steps[si].get("libero_terminated"))
            if flag != prev_flag:
                self.events.append({
                    "event_id": None, "kind": "STATE_UPDATE",
                    "tool": "libero_terminated", "seq": None,
                    "mi_use": None, "mi_res": None, "step": si,
                    "value": flag})
                prev_flag = flag
        # 排序:seq 为主序(None 排最后);同 seq 按 mi
        self.events.sort(key=lambda e: (e["seq"] is None, e["seq"] or 0,
                                        e["mi_res"] or 0))
        for k, ev in enumerate(self.events):
            ev["event_id"] = f"ev{k:02d}"

    # ---- 查询助手 ----------------------------------------------------------
    def next_phys(self, seq):
        for p in self.phys:
            if p["seq"] > seq:
                return p
        return None

    def prev_phys(self, seq):
        last = None
        for p in self.phys:
            if p["seq"] < seq:
                last = p
            else:
                break
        return last

    def span(self, ev):
        """决策 span:上一动作结果之后 → 下一动作发射(含)。"""
        prev = self.prev_phys(ev["seq"])
        lo = prev["mi_res"] if prev else self.t0_res_mi
        nxt = self.next_phys(ev["seq"])
        hi = nxt["mi_use"] if nxt else self.n_msgs - 1
        return lo, hi

    def pre_post_text(self, ev):
        lo, hi = self.span(ev)
        per, whole = span_texts(self.texts, lo, hi)
        pre, post = [], []
        for mi, t in per:
            (post if mi > ev.get("mi_res", -1) else pre).append((mi, t))
        return (("\n".join(t for _, t in pre)),
                ("\n".join(t for _, t in post)), post)

    def text_before(self, mi):
        return "\n".join(t for m, t in sorted(self.texts.items())
                         if m <= mi)

    # ---- 判据族(spec §4)---------------------------------------------------
    def detect(self, pre_t0_prompts):
        """逐事件评估 A′/B′/C′/D′/E′/F′ + EC5,填 label。

        VERIFIER 的 t0-uncertainty 测试(spec 附录 A):正结果只有在
        决策 span 存在动作级验证量配对(RE_VC_A/B)时才具备信息资格;
        否则标 NONINFORMATIVE(纯叙述/冗余复读,不参与段级聚合)。
        """
        for ev in self.events:
            types, evid = [], []
            kind = ev["kind"]
            if kind == "OBSERVE":
                types, evid = self._a_prime(ev)
                t2, e2 = self._c_prime(ev)
                types += t2
                evid += e2
                t3, e3 = self._f_prime(ev)
                types += t3
                evid += e3
            elif kind == "GROUNDING":
                types, evid = self._b_prime(ev)
                t2, e2 = self._e_prime(ev, pre_t0_prompts)
                types += t2
                evid += e2
            elif kind == "VERIFIER":
                if ev["outcome"] == "pos":
                    # t0-uncertainty 测试:同句内 验证量断言 ∧ 配对条件
                    # (立即反应区)才算门控;否则纯叙述/冗余 → NONINFORMATIVE
                    got = self._verify_gate(ev)
                    if got:
                        ev["label"] = "DEPENDENT"
                        ev["dependency_types"] = ["verifier_branch"]
                        ev["evidence"] = [got]
                    else:
                        ev["label"] = "NONINFORMATIVE"
                        ev["dependency_types"] = []
                        ev["evidence"] = [{"detector": "qualify",
                                           "note": "narration-only"}]
                    continue
                types, evid = self._d_prime(ev)
            elif kind == "STATE_UPDATE":
                # 窗口内翻转即新信息;翻 True 且其后无动作 → 终止决策依赖
                after = [p for p in self.phys if p["step"] > ev["step"]]
                if ev.get("value") is True and not after:
                    types, evid = ["termination"], [{
                        "detector": "STATE_UPDATE",
                        "channel": "EC4", "note": "flag→True 停止"}]
            if types:
                ev["label"] = "DEPENDENT"
                ev["dependency_types"] = sorted(set(types))
                ev["evidence"] = evid
            elif ev.get("label") == "NONINFORMATIVE":
                pass
            elif self._ec5_committed(ev):
                ev["label"] = "INDEPENDENT"
                ev["dependency_types"] = []
                ev["evidence"] = [{"detector": "EC5",
                                   "note": "pre-commitment"}]
            else:
                ev["label"] = "UNRESOLVED"
                ev["dependency_types"] = []
                ev["evidence"] = []

    def _a_prime(self, ev):
        """A′ observation-gated execution:断言(post)∧(条件|目的)∧决定。"""
        pre, post, post_per = self.pre_post_text(ev)
        _, whole = span_texts(self.texts, *self.span(ev))
        m_assert = find_match(RE_ASSERT, post)
        if not m_assert:
            return [], []
        cond = find_match(RE_COND, whole) or find_match(RE_PURPOSE, pre)
        if not cond:
            return [], []
        nxt = self.next_phys(ev["seq"])
        decide = find_match(RE_DECIDE, whole)
        same_msg = nxt is not None and any(
            mi == nxt["mi_use"] for mi, _ in post_per)
        if not (decide or same_msg):
            return [], []
        note = "same-msg" if not decide else None
        ev_detail = [{"detector": "A′", "channel": "EC3/EC7",
                      "assert": m_assert, "cond": cond,
                      "decide": decide or note}]
        return ["observation_gate"], ev_detail

    def _b_prime(self, ev):
        """B′ target/pose:grounding 数值 → 后续动作参数(数值或文本引用)。"""
        xyz = ev.get("world_xyz") or ev.get("center_xyz") \
            or ev.get("median_xyz")
        if not xyz:
            return [], []
        weak = "world_xyz" not in ev
        hits = []
        for p in self.phys:
            if p["seq"] <= ev["seq"]:
                continue
            t = p["cmd"].get("xyz")
            if not (isinstance(t, list) and len(t) == 3):
                continue
            dxy = ((t[0] - xyz[0]) ** 2 + (t[1] - xyz[1]) ** 2) ** 0.5
            dz = abs(t[2] - xyz[2])
            if dxy <= XY_TOL and dz <= DZ_TOL:
                hits.append({"detector": "B′", "channel": "EC1",
                             "link": f"{ev['tool']}→{p['action']}"
                                     f"@s{p['step']} dxy={dxy:.4f} "
                                     f"dz={dz:.4f} weak={weak}"})
                break
            # 文本数值引用:span 中出现 ≥2 个 grounding 分量
            nxt = self.next_phys(ev["seq"])
            hi = nxt["mi_use"] if nxt else self.n_msgs - 1
            prev = self.prev_phys(ev["seq"])
            lo = prev["mi_res"] if prev else self.t0_res_mi
            _, whole = span_texts(self.texts, lo, hi)
            if xyz_in_text(whole, xyz) >= 2:
                hits.append({"detector": "B′", "channel": "EC1-text",
                             "link": f"文本引用≥2分量→{p['action']}"
                                     f"@s{p['step']}"})
                break
        if not hits:
            return [], []
        return ["pose_update"], hits

    def _c_prime(self, ev):
        """C′ parameter dependency:观察后偏移量表达 ∧ 同族参数改变。"""
        nxt = self.next_phys(ev["seq"])
        prev = self.prev_phys(ev["seq"])
        if not (nxt and prev):
            return [], []
        pre, post, _ = self.pre_post_text(ev)
        whole = pre + "\n" + post
        if not (RE_OFFSET_WORD.search(whole) and RE_SIGNED_DEC.search(post)):
            return [], []
        # (a) 同族参数改变
        fam_n, fam_p = af(nxt["action"]), af(prev["action"])
        t_n, t_p = nxt["cmd"].get("xyz"), prev["cmd"].get("xyz")
        changed = (fam_n == fam_p and isinstance(t_n, list)
                   and isinstance(t_p, list)
                   and sum((a - b) ** 2 for a, b in zip(t_n, t_p)) ** 0.5
                   > PARAM_DELTA)
        # (b) 文本十进制三元组 ↔ 动作 xyz
        cited = False
        if isinstance(t_n, list):
            for m in re.finditer(
                    r"[\(\[]\s*(-?\d+\.\d+)\s*[,，]\s*(-?\d+\.\d+)"
                    r"\s*[,，]\s*(-?\d+\.\d+)\s*[\)\]]", post):
                trip = [float(m.group(i)) for i in (1, 2, 3)]
                if all(abs(a - b) <= TXT_TRIPLE_TOL
                       for a, b in zip(trip, t_n)):
                    cited = True
                    break
        if not (changed or cited):
            return [], []
        return ["parameter_update"], [{
            "detector": "C′", "channel": "EC1/EC7",
            "changed": bool(changed), "cited": bool(cited)}]

    def _verify_gate(self, ev):
        """正验证门控(t0-uncertainty 测试):post 段存在一个句子,同时
        含动作级验证量断言(RE_VERIFY_ASSERT)与配对条件(RE_VC_A/B),
        且执行决定成立(RE_DECIDE 或同消息发射下一动作)。"""
        pre, post, post_per = self.pre_post_text(ev)
        nxt = self.next_phys(ev["seq"])
        for s in re.split(r"(?<=[.!?;])\s+", post):
            if not (RE_VERIFY_ASSERT.search(s)
                    and (RE_VC_A.search(s) or RE_VC_B.search(s))):
                continue
            decide = RE_DECIDE.search(s) or RE_DECIDE.search(post) or (
                nxt is not None and any(mi == nxt["mi_use"]
                                        for mi, _ in post_per))
            if decide:
                return {"detector": "D′+", "channel": "EC4/EC3",
                        "sentence": s.strip()[:180]}
        return None

    def _d_prime(self, ev):
        """D′ verification dependency(负验证 → 控制变更)。"""
        p = next((q for q in self.phys if q["seq"] == ev["phys_seq"]), None)
        if p is None:
            return [], []
        after = [q for q in self.phys if q["mi_use"] > ev["mi_res"]]
        pre_text = self.text_before(ev["mi_use"])
        if not after:
            if self.steps[self.tR].get("libero_terminated"):
                return ["termination"], [{"detector": "D′",
                                          "channel": "EC4",
                                          "note": "neg→terminate"}]
            return [], []
        q = after[0]
        changed = (af(q["action"]) != af(p["action"])
                   or (p["action"] in ("pi0_pick", "pi0_doubled")
                       and q["action"] in ("pi0_pick", "pi0_doubled")
                       and q["cmd"].get("prompt") != p["cmd"].get("prompt")))
        tq, tp = q["cmd"].get("xyz"), p["cmd"].get("xyz")
        if (not changed and isinstance(tq, list) and isinstance(tp, list)):
            changed = sum((a - b) ** 2 for a, b in zip(tq, tp)) ** 0.5 \
                > MOVE_CHANGE
        if not changed:
            return [], []
        # pre-commitment 否决:变更动作早已在验证前文本中列明
        q_prompt = q["cmd"].get("prompt")
        committed = False
        if q_prompt and q_prompt in pre_text:
            committed = True
        elif isinstance(tq, list) and xyz_in_text(pre_text, tq) >= 2:
            committed = True
        if committed:
            return [], []
        return ["retry_fallback"], [{
            "detector": "D′", "channel": "EC4",
            "note": f"neg@{p['action']}s{p['step']}→"
                    f"{q['action']}s{q['step']}"}]

    def _e_prime(self, ev, pre_t0_prompts):
        """E′ grounding-reference:t0 后新目标实体被后续动作采用。"""
        nxt = self.next_phys(ev["seq"])
        if nxt is None or nxt["action"] not in ("pi0_pick", "pi0_doubled"):
            return [], []
        pr = nxt["cmd"].get("prompt")
        if not pr or pr in pre_t0_prompts:
            return [], []
        toks = {w.lower().strip(".,") for w in pr.split()}
        diff = {w for w in toks
                if w not in STOP_NOUNS and len(w) >= 4
                and not any(w in pp.lower().split()
                            for pp in pre_t0_prompts)}
        if not diff:
            return [], []
        # 溯源:新词须出现在 t0 后 grounding 输入/结果或其决策 span 文本
        src = json.dumps(ev.get("input") or {}, ensure_ascii=False) + \
            " " + json.dumps({k: v for k, v in ev.items()
                              if k in ("usable_fields",)}, ensure_ascii=False)
        lo, hi = self.span(ev)
        _, whole = span_texts(self.texts, lo, hi)
        for w in diff:
            if w in src.lower() or w in whole.lower():
                return ["target_grounding"], [{
                    "detector": "E′", "channel": "EC2",
                    "new_term": w, "prompt": pr}]
        return [], []

    def _f_prime(self, ev):
        """F′ explicit branch:不可达/掉落→改道;已完成→终止。"""
        nxt = self.next_phys(ev["seq"])
        pre, post, _ = self.pre_post_text(ev)
        whole = pre + "\n" + post
        m_sw = RE_F_SWITCH.search(post)
        if m_sw and nxt is not None:
            return ["retry_fallback"], [{
                "detector": "F′", "channel": "EC3",
                "span": post[max(0, m_sw.start() - 40):
                             m_sw.end() + 40][:160]}]
        m_tm = RE_F_TERM.search(whole)
        if m_tm and nxt is None:
            return ["termination"], [{
                "detector": "F′", "channel": "EC3",
                "span": whole[max(0, m_tm.start() - 40):
                              m_tm.end() + 40][:160]}]
        return [], []

    def _ec5_committed(self, ev):
        """INDEPENDENT 证据(严格):信息到达前,后续序列+关键参数已承诺。

        三个充分条件之一(文本须发布于事件到达前):
        (a) 下一动作 prompt 全等出现;(b) 下一动作 xyz ≥2 分量出现;
        (c) 无条件顺序计划:两个动作族词被顺序词连接,族覆盖后续两动作,
            且计划 span 无任何条件标记(有条件计划不算承诺)。
        必要否决:pre 段有观察目的表达、或 post 段有观察内容断言
        (信息被实际使用过 → 不判 INDEPENDENT)。
        """
        if ev["kind"] not in ("OBSERVE", "GROUNDING"):
            return False
        nxt = self.next_phys(ev["seq"])
        nxt2 = self.next_phys(nxt["seq"]) if nxt else None
        pre, post, _ = self.pre_post_text(ev)
        if RE_PURPOSE.search(pre) or RE_ASSERT.search(post):
            return False
        committed = False
        for q in (nxt, nxt2):
            if not q:
                continue
            pr = q["cmd"].get("prompt")
            if pr and pr in pre:
                committed = True
                break
            t = q["cmd"].get("xyz")
            if isinstance(t, list) and xyz_in_text(pre, t) >= 2:
                committed = True
                break
        if not committed and nxt and nxt2:
            m = RE_SEQ_PLAN.search(pre)
            if m and not RE_COND_ANY.search(m.group(0)):
                fams = sorted({FAM_WORDS.get(w.lower().strip())
                               for w in re.findall(
                                   r"(?i)\b(retreat|descend|move_to|move|"
                                   r"approach|rotate|repick|re-pick|"
                                   r"pi0_pick|pick|release|set_gripper|"
                                   r"gripper)\b", m.group(0))}
                              - {None})
                need = sorted({af(nxt["action"]), af(nxt2["action"])})
                if fams == need:
                    committed = True
        return committed


def analyze_segment_v2(tl, msgs, texts, fire, tR_i, steps_by_idx):
    """一个 segment 的 v2 标注;返回 (segment dict) 或 ("beyond", None)。"""
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

    seg = SegmentV2(tl, texts, fire, t0, tR, steps_by_idx, len(msgs))
    t0_res = next((e for e in tl["events"] if e["kind"] == "res"
                   and e.get("use_seq") == t0_seq), None)
    seg.t0_res_mi = t0_res["mi"] if t0_res else 0
    seg.build(win, t0_seq, tR_seq)

    # t0 前 pick prompt 集(E′ 基准)
    pre_t0_prompts = {(u.get("input") or {}).get("prompt") or ""
                      for u in tl["uses"] if u["seq"] < t0_seq
                      and u["name"] in ("pi0_pick", "pi0_doubled")}
    seg.detect(pre_t0_prompts)

    n_dep = sum(e["label"] == "DEPENDENT" for e in seg.events)
    n_unres = sum(e["label"] == "UNRESOLVED" for e in seg.events)
    n_ind = sum(e["label"] == "INDEPENDENT" for e in seg.events)
    n_noninf = sum(e["label"] == "NONINFORMATIVE" for e in seg.events)
    if n_dep:
        seg_label = "DEPENDENT"
    elif n_unres:
        seg_label = "UNRESOLVED"
    else:
        seg_label = "INDEPENDENT"

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

    acts = [af(s["command"]["action"]) for s in tl["act_steps"]]
    i0 = next(i for i, s in enumerate(tl["act_steps"])
              if s["step_idx"] == t0)
    pre_sig = "|".join(acts[:i0 + 1][-2:]) if acts else "none"

    return {
        "segment_id": None, "episode_dir": None,
        "task": None, "seed": None, "node": node,
        "family": NODE_FAMILY[node], "t0": t0, "tR": tR,
        "tR_reason": tR_reason, "tR_offset": tR_i - i0, "pre_sig": pre_sig,
        "primitive_count": len(seg.phys),
        "n_information_events": len(seg.events),
        "n_observe": sum(e["kind"] == "OBSERVE" for e in seg.events),
        "n_grounding": sum(e["kind"] == "GROUNDING" for e in seg.events),
        "n_verifier": sum(e["kind"] == "VERIFIER" for e in seg.events),
        "n_state_update": sum(e["kind"] == "STATE_UPDATE" for e in seg.events),
        "n_dependent": n_dep, "n_unresolved": n_unres,
        "n_independent": n_ind, "n_noninformative": n_noninf,
        "segment_label": seg_label,
        "dependency_types": sorted({t for e in seg.events
                                    for t in e.get("dependency_types", [])}),
        "fired_detectors": sorted({e["evidence"][0]["detector"]
                                   for e in seg.events
                                   if e["label"] == "DEPENDENT"
                                   and e.get("evidence")}),
        "events": seg.events, "phys": [
            {"step": p["step"], "action": p["action"],
             "xyz": p["cmd"].get("xyz"), "prompt": p["cmd"].get("prompt"),
             "out": p["out"]} for p in seg.phys],
        "wall_s": round(steps_by_idx[tR].get("elapsed_s", 0)
                        - steps_by_idx[t0].get("elapsed_s", 0), 2),
    }


def main() -> int:
    dev = "--dev" in sys.argv
    held = {r["episode_dir"] for r in
            csv.DictReader(open(REPO / "analysis/stageL_split_manifest.csv"))
            if r["role"] == "L_HELDOUT_TEST"}
    pool = {}
    for ln in open(REPO / "analysis/stageL_pool_inventory.jsonl"):
        r = json.loads(ln)
        if r["episode_dir"] in held:
            continue
        pool[r["episode_dir"]] = {"task": r["task"], "seed": r["seed"]}
    print(f"pool: {len(pool)} episodes")

    old33 = {}
    if dev:
        for r in csv.DictReader(
                open(REPO / "analysis/stageM0_audit_sample.csv")):
            old33[r["segment_id"]] = r["audit_id"]
        old_eps = {sid.split("#")[0] for sid in old33}
        print(f"dev mode: 仅旧 33 audit 样本({len(old33)} 段,"
              f"{len(old_eps)} 集)")

    segs = []
    n_never = Counter()
    for d, meta in sorted(pool.items()):
        if dev and Path(d).name not in old_eps:
            continue
        dp = Path(d)
        if not (dp / "states.json").exists():
            continue
        steps = load_steps(dp)
        steps_by_idx = {s["step_idx"]: s for s in steps}
        fires = replay_fires(steps)
        acts = [x for x in steps if (x.get("command") or {}).get("action")]
        tl = build_timeline(dp)
        tl_ok = tl is not None and tl.get("align_ok")
        msgs = texts = None
        if tl_ok:
            msgs, texts = load_msgs(dp)
        for fi, fire in enumerate(fires):
            fam = NODE_FAMILY[fire["node"]]
            sid = f"{dp.name}#f{fi}"
            i0 = next((i for i, s in enumerate(acts)
                       if s["step_idx"] == fire["step_idx"]), None)
            if i0 is None:
                n_never[fam] += 1
                continue
            tR_i = None
            for j in range(i0 + 1, len(acts)):
                s = acts[j]
                if fire_validated(fire["node"], [
                        (s["command"]["action"], s.get("result") or {},
                         bool(s.get("libero_terminated")))]):
                    tR_i = j
                    break
            if tR_i is None:
                n_never[fam] += 1
                continue
            base = {"segment_id": sid, "episode_dir": d,
                    "task": meta["task"], "seed": meta["seed"],
                    "node": fire["node"], "family": fam,
                    "t0": fire["step_idx"], "tR": acts[tR_i]["step_idx"]}
            if not tl_ok or msgs is None:
                segs.append({**base, "segment_label": "UNRESOLVED",
                             "label_sub": "no-transcript" if tl is None
                             else "align-fail", "events": [],
                             "n_information_events": 0})
                continue
            got = analyze_segment_v2(tl, msgs, texts, fire, tR_i,
                                     steps_by_idx)
            if not isinstance(got, dict):     # ("beyond", None)
                segs.append({**base, "segment_label": "UNRESOLVED",
                             "label_sub": "beyond-transcript", "events": [],
                             "n_information_events": 0})
                continue
            seg = got
            seg.update(base)
            segs.append(seg)

    # ---- 落盘 --------------------------------------------------------------
    suffix = "_dev" if dev else ""
    with open(REPO / f"analysis/stageN0_information_events{suffix}.jsonl",
              "w") as f:
        for s in segs:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    fields = ["segment_id", "task", "seed", "family", "node", "t0", "tR",
              "tR_reason", "tR_offset", "pre_sig", "primitive_count",
              "n_information_events", "n_observe", "n_grounding",
              "n_verifier", "n_state_update", "n_dependent", "n_unresolved", "n_noninformative",
              "n_independent", "segment_label", "dependency_types",
              "fired_detectors", "machine_class", "unknown_rate"]
    with open(REPO / f"analysis/stageN0_control_labels{suffix}.csv",
              "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in segs:
            # spec §6 两列:machine_class=段级标签别名;unknown_rate=事件级
            # UNRESOLVED 占比(NONINFORMATIVE 不计入分母,零事件记 0)
            row = dict(s)
            row["machine_class"] = s["segment_label"]
            row["unknown_rate"] = round(
                s.get("n_unresolved", 0) / s["n_information_events"], 3) \
                if s.get("n_information_events") else 0.0
            w.writerow(row)

    # ---- 统计 --------------------------------------------------------------
    lab = Counter(s["segment_label"] for s in segs)
    print("segments:", len(segs), "| labels:", dict(lab))
    byfam = defaultdict(Counter)
    for s in segs:
        byfam[s["family"]][s["segment_label"]] += 1
    for fam, c in sorted(byfam.items()):
        print(" ", fam, dict(c))
    print("detectors:", dict(Counter(
        d for s in segs for d in s.get("fired_detectors", []))))
    print("dep types:", dict(Counter(
        t for s in segs for t in s.get("dependency_types", []))))

    # ---- dev:与 M 人工答案混淆矩阵(失败模式发现用) ------------------------
    if dev:
        human = {r["audit_id"]: r for r in csv.DictReader(
            open(REPO / "analysis/stageM0_manual_audit.csv"))}
        expect = {"OPTION_REQUIRED": "DEPENDENT",
                  "MACRO_REPRESENTABLE": "INDEPENDENT",
                  "EDGE_REPRESENTABLE": "INDEPENDENT"}
        conf = defaultdict(int)
        print("\n== dev 混淆(M 人工语义映射 → v2 段级)==")
        for s in segs:
            aid = old33.get(s["segment_id"])
            if not aid or aid not in human:
                continue
            h = expect.get(human[aid]["label"], "UNRESOLVED")
            conf[(h, s["segment_label"])] += 1
            if h != s["segment_label"]:
                print(f"  mismatch {aid} {s['segment_id'][:50]}: "
                      f"M-human={h} v2={s['segment_label']} "
                      f"det={s.get('fired_detectors')}")
        for (h, m), n in sorted(conf.items()):
            print(f"  human={h:<12} v2={m:<12} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
