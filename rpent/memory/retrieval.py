"""决策点长期记忆召回(Stage B1 的 B2/B3 臂)。

门控: ``RPENT_MEMORY_TRIGGER=1``。排序方法: ``RPENT_MEMORY_RANK``,取值
{"Q0_FIXED", "Q3"} — 两者都是 Stage A 离线 benchmark
(``scripts/memory_stagea_benchmark.py``)的冻结移植;权重与规则不得针对
线上结果调参(实验纪律)。

该组件监听 primitive/perception 工具结果,在每个 turn boundary 评估冻结的
通用触发器;触发后检索 top-3 卡片,以软性上下文块的形式交给 planner
(不强制执行 —— 是否采纳正是 Stage B 要测量的问题)。每个检索事件都写入
episode 输出目录的 ``memory_events.jsonl``。

触发规则只用无 task-id 的信号(spec §3):它们回答的是"现在该不该查
长期记忆",从不回答"查哪条记忆"。


长期记忆动态召回模块。

它解决两个问题：

1. WHEN：
   当前这个时刻，要不要查长期记忆？

2. WHAT：
   如果要查，从 Memory Bank 里取哪 3 张卡？

注意：
这里的 Memory 只是作为提示信息交给 Planner，
不会强制 Planner 执行 Memory 中的策略。

实验变量：

RPENT_MEMORY_TRIGGER
    决定使用哪种“什么时候查”的策略。

RPENT_MEMORY_RANK
    决定使用哪种“查哪张卡”的检索器。

这两个维度被刻意分开，
方便实验判断：
性能变化到底来自 Trigger，还是来自 Retrieval Ranking。



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

# ------------------------------------------------------------------ 冻结区
# 分词器 + 相位映射 + 打分逻辑都是 Stage A 的逐字移植(冻结)。
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

# 冻结的冷却策略:
# 一次 Memory Retrieval 之后,至少隔 2 个 turn boundary 才能再触发;
# 整个 episode 最多查 6 次 Memory;
# 第一个 primitive 动作之前不触发;memory 文件类工具上不触发。

COOLDOWN_BOUNDARIES = 2
MAX_TRIGGERS_PER_EPISODE = 6

# G0.5 §18 — 仅实验用的注入模式(第 3 通道,planner 可见的上下文)。
# "full" 是历史行为,也是默认值;其余四个模式已在
# analysis/stageG05_preregistration.md 中预注册(下面的文本在那里逐字
# 冻结 — 不得改写措辞)。
INJECTION_MODES = ("full", "memory_only", "reason_only", "generic_refresh",
                   "none")
_NO_RETRIEVAL_MODES = ("reason_only", "generic_refresh", "none")

# F3 — P2 generic_refresh 注入块(与任务无关;不含 reason、不含卡片)。
GENERIC_REFRESH_BLOCK = (
    "[DECISION-POINT REORIENTATION]\n"
    "Re-evaluate the task goal, the latest observable execution result, "
    "and the current scene before choosing the next action.\n"
    "Do not assume the previous action succeeded.\n"
    "Base the next primitive on the latest observable evidence rather "
    "than blindly continuing the previous plan.\n"
    "Do not apply any specific recovery strategy unless supported by "
    "the current state."
)

# F4 头部 — P3 memory_only 用这个中性的两行文本替换 _block() 的头部
# (标题 + 框架说明);卡片渲染与 _block() 完全一致。
MEMORY_CONTEXT_HEADER = (
    "[DECISION-POINT MEMORY CONTEXT]\n"
    "These past experiences may or may not be relevant. Judge them "
    "against the current observable state."
)


def _reason_only_block(reason: str) -> str:
    """F2 — P1 注入块:触发 reason + 一行重新评估的提示。"""
    return ("[DECISION-POINT CHECK]\n"
            f"trigger reason: {reason}\n"
            "Re-evaluate the next action using the latest observable "
            "state.")

# Q3 结构化重排权重 — 从 Stage A 冻结而来(禁止线上调参)。
W_SEMANTIC = 2.0 #语义
W_APPLIES = 0.6 #适用性
W_SYMPTOM = 0.4 #问题匹配度
W_ACTION = 0.5 #行动匹配度
W_PHASE = 0.4 #阶段匹配度


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


def load_index() -> dict[str, str]: #初级索引：title + 简要描述
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


class _Embedder: #语义向量
    """惰性加载本地 bge-small-en-v1.5(CPU)— 与 Stage A 用同一编码器。"""

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
    """单个 episode 的冻结触发器 + 软性检索 + 事件记录。

    mode="v1"(默认,RPENT_MEMORY_TRIGGER=1):冻结的 Stage B1 boundary
    触发器 — 不得改动(已发表的行为)。

    mode="progress"(RPENT_MEMORY_TRIGGER=progress,Stage C3 的 O2 臂):
    Stage C2 冻结的进度感知规则(R1-R5),逐工具结果评估(命中后排队,
    在下一个 boundary 冲刷)。规则与 scripts/memory_stagec2_benchmark.py
    精确镜像 — 包括没有 first-primitive 门(C2 离线重放就没有)以及冻结
    阈值 MOVE_EPS=0.005 / MOVE_ARRIVED=0.03 / LIFT_OK=0.05。
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
        # Stage G 规模压力测试库(stageG_subset_manifest.md §3):把真实
        # 库页面追加为额外检索条目。纯增量 — 61 张全局卡与 MEMORY.md
        # 索引从不被修改。
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
        # 每个 episode 的信号状态
        self.task_language = ""
        self.boundaries_since_trigger = COOLDOWN_BOUNDARIES
        self.triggers_fired = 0
        self.saw_primitive = False
        self.release_open = False  # 已执行 release,谓词尚未确认
        self.last_primitive = ""
        self.recent_primitives: list[str] = []
        self.phase_steps = 0
        self.last_phase = ""
        self.picks_failed = 0
        self.turn = 0
        self._last_result: dict | None = None
        self._fresh_result = False  # 上个 boundary 以来有新结果到达
        self._last_scores: list[float] = []
        self._embedder = _Embedder()
        # progress 模式状态(Stage C2 冻结规则)
        self._queued_fire: str | None = None   # 待冲刷触发的 reason
        self._queued_result: dict | None = None
        self._queued_phase = ""  # 排队时刻的 tracker 相位(G0-C)
        self._last_eef: list[float] | None = None  # 最近一次见到的 final_eef_pos
        self._consec_pick_fails = 0
        self._prev_prim_failed = False
        # Stage G 基线触发器参数(在 DEV suite 上一次性冻结于
        # analysis/stageG_trigger_baseline_config.md;从不在最终 suite 上
        # 调参)。仅在 mode 为基线模式时读取。
        self.periodic_n = int(os.environ.get("RPENT_MEMORY_PERIODIC_N", "6"))
        self.mstuck_k = int(os.environ.get("RPENT_MSTUCK_K", "3"))
        self.mstuck_move_m = float(os.environ.get("RPENT_MSTUCK_MOVE_M",
                                                  "0.01"))
        self.mstuck_prog_m = float(os.environ.get("RPENT_MSTUCK_PROG_M",
                                                  "0.01"))
        self._boundary_count = 0
        # G0-D:窗口条目为 (eef[:3], final_dist_m | None, target_key)
        # — final_dist_m 的进度只在同一个被指令目标内可比(3 位小数键)。
        # 窗口开启时所处的相位单独记录;相位切换会重置窗口。
        self._mstuck_win: list[tuple[list[float], float | None,
                                     tuple]] = []
        self._mstuck_phase = ""
        # G0-A/B:query 模式。"native" = 历史行为(query = 观测 + 触发
        # reason)。"common" = 为因果审计解耦 WHEN/WHAT:query 只携带
        # 相位 / 触发结果的动作 / 触发结果的字段 / task_language —
        # 触发 reason 只写入日志,从不进入检索打分(词面 query 文本和
        # Q3 结构化 reason 项都不含它)。
        self.query_mode = os.environ.get("RPENT_MEMORY_QUERY_MODE",
                                         "native")
        if self.query_mode not in ("native", "common"):
            raise ValueError(
                f"RPENT_MEMORY_QUERY_MODE={self.query_mode!r} must be "
                "'native' or 'common' — fail fast rather than silently "
                "contaminating an arm")
        # G0.5 §18:注入模式(第 3 通道旋钮,仅实验用)。"full" = 历史行为,
        # 对所有既有模式逐字节一致;其余四个是 G0.5 的臂,只在与它们被
        # 预注册时配套的 v1_per_result 触发器下合法。
        self.injection_mode = os.environ.get("RPENT_MEMORY_INJECTION_MODE",
                                             "full")
        if self.injection_mode not in INJECTION_MODES:
            raise ValueError(
                f"RPENT_MEMORY_INJECTION_MODE={self.injection_mode!r} must "
                f"be one of {sorted(INJECTION_MODES)}")
        if (self.injection_mode != "full"
                and self.mode != "v1_per_result"):
            raise ValueError(
                "G0.5 injection modes are pre-registered for "
                "RPENT_MEMORY_TRIGGER=v1_per_result only (got "
                f"{self.mode!r}) — fail fast rather than running an "
                "undeclared arm configuration")
        # G0.5 §18 显式别名旋钮 — 与它们所重复的旋钮交叉校验,确保过期
        # 或互相矛盾的 env 永远无法静默重定义一个臂。
        _qr = os.environ.get("RPENT_MEMORY_QUERY_REASON")
        if _qr is not None:
            _want = "native" if _qr == "1" else "common"
            if _want != self.query_mode:
                raise ValueError(
                    "RPENT_MEMORY_QUERY_REASON="
                    f"{_qr!r} contradicts QUERY_MODE={self.query_mode!r}")
        _br = os.environ.get("RPENT_MEMORY_BLOCK_REASON", "1")
        _br_want = _br == "0"
        if _br_want != (self.injection_mode == "memory_only"):
            raise ValueError(
                "RPENT_MEMORY_BLOCK_REASON=0 marks the P3 memory_only "
                "neutral header; it cannot be combined with "
                f"injection_mode={self.injection_mode!r}")

    # ------------------------------------------------------------- 观测
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
                # 谓词信号就在结果里;若 episode 没有在 release 上终止,
                # 继续保持监视(T3)。
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

    # -------------------------------------- progress 模式(Stage C2 冻结)
    def _progress_observe(self, name: str, data: dict, is_error: bool) -> None:
        """在当前这条结果上评估冻结的 C2 规则 R1-R5(逐结果评估 —
        这是修复 v1 boundary 覆盖导致信号丢失的手段)。"""
        fd = data.get("final_dist_m")
        is_move = name in ("move_to", "move_pose")
        # R2 用的 pre-eef = 本结果更新 _last_eef 之前最后一次已知的 eef
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
            # 计数器语义与冻结的离线重放精确一致:
            # success=False 时递增,其余情况清零
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
        # 镜像离线版的 prev_prim_failed 定义
        if name in PRIMITIVES:
            self._prev_prim_failed = data.get("success") is False or (
                is_move and isinstance(fd, (int, float))
                and fd > self.MOVE_ARRIVED)

    def _v1pr_observe(self, name: str, data: dict, is_error: bool) -> None:
        """G0-A 实验模式 "v1_per_result":冻结的 v1 触发规则(T1-T7,
        未改动)在每条工具结果到达时评估,命中即排队,下一个 boundary
        冲刷。

        用于隔离信号保全问题:v1_original 在 boundary 之前又到达新结果时
        会丢失命中(boundary 只看最后一条结果);本模式逐结果保留
        队列/冷却语义 = 冻结的 PROGRESS 冲刷语义(冷却即丢弃、到上限即
        丢弃),因此 v1_per_result -> progress 只差规则内容本身。v1 的
        saw_primitive 门在评估(EVAL)时施加(任何 primitive 运行过之前
        跳过),与 v1 的施加位置保持一致。"""
        if not self.saw_primitive:
            return
        reason = self._v1_rules_for(name, data, is_error)
        if reason and self._queued_fire is None:
            self._queued_fire = reason
            self._queued_result = dict(self._last_result)
            self._queued_phase = self.last_phase

    # ------------------------------------------------------------- 触发
    def _trigger_reason(self) -> str | None:
        r = self._last_result
        if not r:
            return None
        return self._v1_rules_for(r["name"], r["data"], r["is_error"])

    def _v1_rules_for(self, name: str, data: dict,
                      is_error: bool) -> str | None:
        """冻结的 v1 触发规则 T1-T7,针对单条结果评估。

        G0-A:函数体逐字保留历史 _trigger_reason 逻辑 — 同样的规则、
        同样的累计状态读取(recent_primitives、release_open、
        picks_failed、phase_steps、tracker)。唯一的变化是被评判的
        结果是显式参数,使 v1_per_result 能在每条结果到达时评估。
        """
        if name not in PRIMITIVES + PERCEPTION:
            return None
        # T1 primitive 失败
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
        # T2 pick 模糊:报告成功但抬升近零
        if name == "pi0_pick" and data.get("success") is True:
            diag = data.get("diagnostics") or {}
            lift = diag.get("post_min_ascent_m")
            if isinstance(lift, (int, float)) and 0.0 <= lift < 0.05:
                return "pick_ambiguous: pick reports success but barely lifted"
        # T3 release 之后谓词停滞
        if name in PRIMITIVES and self.release_open \
                and not data.get("libero_terminated", False) \
                and name != "release":
            return ("predicate_stalled: actions continue after release but "
                    "the task predicate has not fired")
        # T4 重复动作且无进展
        if len(self.recent_primitives) >= 3 \
                and len(set(self.recent_primitives[-3:])) == 1:
            return f"repeated_no_progress: {name} x3 in a row"
        if self.picks_failed >= 2:
            return "repeated_no_progress: repeated failed picks"
        # T5 感知不足
        if name in PERCEPTION:
            if data.get("found") is False:
                return "perception_insufficient: segmentation found no mask"
            if data.get("world_error"):
                return f"perception_insufficient: {data['world_error']}"
        # T6 恢复规则待定(SM1 信号)
        try:
            if self.tracker is not None and self.tracker.recovery_pending():
                return "recovery_pending: failure-recovery rule precondition met"
        except Exception:  # noqa: BLE001 - 触发器绝不能弄崩整个 run
            pass
        # T7 相位停滞:预期的切换没有发生
        if self.phase_steps >= 8:
            return "phase_stalled: no phase transition across 8+ actions"
        return None

    # ------------------------------------------------------------ 边界
    def turn_boundary(self, turn: int) -> tuple[str, dict] | None:
        """评估冻结的触发器;触发则返回 (block, event)。"""
        self.turn = turn
        self.boundaries_since_trigger += 1
        self._boundary_count += 1
        if self.tracker is not None:
            ph = ""
            try:
                # PhaseTracker.current_phase 是方法(没有 @property)—
                # 必须调用;裸属性取到的是绑定方法,会污染 event JSON
                # 和 Q3 的 query 文本。
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
                self._mstuck_win = []  # G0-D:相位切换重置窗口
            return self._mstuck_boundary(turn)
        if not self.saw_primitive or self.triggers_fired >= MAX_TRIGGERS_PER_EPISODE:
            return None
        if self.boundaries_since_trigger < COOLDOWN_BOUNDARIES:
            return None
        if not self._fresh_result:
            return None  # 上个 boundary 以来没有新结果
        reason = self._trigger_reason()
        self._fresh_result = False
        if not reason:
            return None
        self.boundaries_since_trigger = 0
        self.triggers_fired += 1
        # 一次性重置,避免同一信号永远重复触发
        self.picks_failed = 0
        self.phase_steps = 0
        self.release_open = False

        t0 = time.time()
        top, cand = self._retrieve(reason)
        latency_ms = (time.time() - t0) * 1000
        event = {
            "episode": "",  # finalize 时从输出目录回填
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
            "planner_next_action": None,   # 事后字段,由分析回填
            "planner_followed_top1": None,  # 事后字段
            "planner_followed_any_top3": None,  # 事后字段
            "verification_result": None,    # 事后字段
            "episode_result": None,        # 事后字段
        }
        # G0-E 同样适用于冻结的 v1 路径:每次尝试都有日志;EMPTY 只写
        # 事件、不注入。策略不变。
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
        """冲刷一条排队的逐结果触发。由 mode="progress"(Stage C2 冻结
        规则;没有 first-primitive 门 — 离线重放就没有)和
        mode="v1_per_result"(G0-A;门改在评估时施加)共享。冷却中的触发
        直接丢弃而不是推迟 — 这是冻结的 progress 语义,v1_per_result
        沿用之,使两者只差规则内容。"""
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
        # G0.5:P0/P1/P2 完全跳过检索(§6 — P3/P4 之外不做记忆检索);
        # 触发本身在上面已完整记录。
        if self.injection_mode in _NO_RETRIEVAL_MODES:
            return self._fire_without_retrieval(turn, reason, qr, phase)
        t0 = time.time()
        obs = self._obs_summary_for(qr)
        # G0-B:common query = WHEN/WHAT 解耦 — reason 永不进入 query
        # (词面文本)也不进入结构化 reason 项。
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
            "injection_mode": self.injection_mode,
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
        # G0-E:每次触发尝试都有日志。检索为 EMPTY 时仍写事件
        # (retrieval_empty=True),但不注入任何内容。
        if not top:
            self.events.append(event)
            logger.info("[memrecall] turn=%s trigger=%s retrieval=EMPTY "
                        "(logged, no injection)", turn, reason)
            return None
        # G0.5:P3 渲染中性 F4 头部;P4/full 走冻结的 _block()(与所有
        # 历史臂逐字节一致)。
        block = (self._memory_only_block(top)
                 if self.injection_mode == "memory_only"
                 else self._block(reason, top))
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

    # ------------------------------- Stage G 基线触发器(T2/T3)
    # 仅作基线(stageG_trigger_baseline_config.md)。与冻结模式的唯一
    # 差别是判定规则本身:检索、注入路径、冷却与每 episode 上限全部
    # 一致。上面冻结的 v1/progress 代码路径未被动过。
    def _mstuck_observe(self, name: str, data: dict) -> None:
        """T3_MOTION_STUCK:通用空间停滞检测器(G0-D 加固版)。只使用
        相邻 move 结果之间的 EEF 位移和 final_dist_m 的改善 — 后者只在
        被指令到同一目标(target_xyz 键,3 位小数)的两次结果之间可比。
        不含任何 primitive 专属的 PICK/PLACE/PERCEPTION 逻辑。窗口在
        以下情况重置:夹入非 move 的 primitive、被指令目标变化、目标
        缺失(失去进度锚点)、或相位切换(boundary 处检查)。仅在 move
        结果到达时评估。"""
        if name in PRIMITIVES and name not in ("move_to", "move_pose"):
            self._mstuck_win = []   # move 之间出现 pick/release 等:重置
            return
        if name not in ("move_to", "move_pose"):
            return                  # perception/memory 结果:不重置
        eef = data.get("final_eef_pos")
        tgt = data.get("target_xyz")
        if not isinstance(eef, list) or len(eef) < 3:
            return
        if not isinstance(tgt, list) or len(tgt) < 3:
            self._mstuck_win = []   # 无目标 -> 无进度锚点
            return
        tkey = tuple(round(v, 3) for v in tgt[:3])
        if self._mstuck_win and self._mstuck_win[-1][2] != tkey:
            self._mstuck_win = []   # 被指令目标变了
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
            # 窗口条目构造上共享 tkey;进度按同目标设计。dist 未知
            # (None) -> 无法验证进度,但位移证据仍然成立(保留冻结
            # DEV 校准时的语义)。
            if d0 is not None and d1 is not None \
                    and d0 - d1 >= self.mstuck_prog_m:
                return  # 朝被指令目标有真实进展
        if self._queued_fire is None:
            self._queued_fire = (f"motion_stuck: k={self.mstuck_k} "
                                 f"disp<{self.mstuck_move_m:.3f}m "
                                 f"prog<{self.mstuck_prog_m:.3f}m "
                                 f"same-target")
            self._queued_result = dict(self._last_result)
            self._queued_phase = self.last_phase
            self._mstuck_win = []  # 一旦排队触发,窗口重置

    def _periodic_boundary(self, turn: int) -> tuple[str, dict] | None:
        """T2_PERIODIC:每第 N 个 turn boundary 触发一次(纯计时器,
        对状态视而不见)。第一个 primitive 结果之前的 tick 跳过。"""
        if not self.saw_primitive or self._boundary_count % self.periodic_n:
            return None
        reason = (f"periodic_tick: boundary={self._boundary_count} "
                  f"N={self.periodic_n}")
        return self._baseline_fire(turn, reason,
                                   dict(self._last_result)
                                   if self._last_result else {},
                                   "periodic")

    def _mstuck_boundary(self, turn: int) -> tuple[str, dict] | None:
        """在 boundary 冲刷排队的 T3 触发(冷却即丢弃,同冻结的
        progress 语义)。"""
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
        """Stage G 基线共用的触发路径 — 冷却/上限/检索/日志语义与
        冻结模式一致(含 G0-B query 模式与 G0-E 尝试日志)。"""
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
        """把真实库页面(G4 干扰库)追加为检索条目。G0-F:id 带命名空间
        extra::<dir>::<stem>,不同库目录的页面永不冲突(全局 61 张卡的
        id 不受影响)。页面 frontmatter 提供 task_language(作 title 用);
        正文提供词面索引行和 Q3 的 body 文本。不编辑任何卡片内容;全局
        卡保留其精确的索引行。"""
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
                # 与全局卡相同的 "how_to" 键(和同样的 400 字符截断),
                # 使 _block() 对两者统一渲染。
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

    # ------------------------------------------------------------ 检索
    def _obs_summary(self) -> str:
        r = self._last_result
        keys = ("success", "libero_terminated", "final_dist_m", "found",
                "world_error", "min_gripper_opening")
        fields = {k: r["data"][k] for k in keys if k in r["data"]}
        return (f"phase={self.last_phase}; last action={self.last_primitive}; "
                f"result fields={fields}; task: {self.task_language[:110]}")

    def _obs_summary_for(self, r: dict) -> str:
        """针对某条(排队的)结果的 poor-format 观测摘要 — progress
        模式在出问题的那条结果上触发,而不是最后看到的那条。"""
        data = r.get("data") or {}
        keys = ("success", "libero_terminated", "final_dist_m", "found",
                "world_error", "min_gripper_opening")
        fields = {k: data[k] for k in keys if k in data}
        return (f"phase={self.last_phase}; last action={r.get('name', '')}; "
                f"result fields={fields}; task: {self.task_language[:110]}")

    def _retrieve(self, reason: str) -> tuple[list[str], list[str]]:
        """v1 boundary 检索。v1 boundary 在最后一条结果上触发,所以
        结构化 Q3 项(obs 文本 / 动作 / 相位)取的就是那条结果的值 —
        与 G0-C 的显式状态修复一致。"""
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
        # G0-F:带命名空间的 extra id 只按其 STEM 词计分(extra::<dir>::
        # 前缀不贡献词);不带 "::" 的全局卡打分方式与从前完全一致。
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
        """Q3 结构化重排 — 冻结的权重 / 池大小 / 编码器 / 相位映射
        (Stage A 移植,未改动)。

        G0-C:每个结构化项(观测词、动作、相位)都显式来自触发所落在
        的那条结果,排队的触发不会再被后续结果的状态重新打分。权重与
        语义池未动。"""
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

    # ---------------------------------------------------------------- 注入块
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

    def _memory_only_block(self, top: list[str]) -> str:
        """F4 — P3 注入块:中性头部,卡片渲染与 _block() 相同。

        刻意作为 _block() 的兄弟函数保留(而不是重构那个冻结函数);
        test_stageG05_injection.py 断言两者对同一 top-3 的卡片行完全
        一致。"""
        lines = [MEMORY_CONTEXT_HEADER]
        for i, c in enumerate(top[:3], 1):
            card = self.cards[c]
            lines.append(
                f"{i}. [{card['id']}] {card['title']}\n"
                f"   applies_when: {card['applies_when'][:220]}\n"
                f"   How to apply: {card['how_to'][:280]}\n"
                f"   Falsify (do not use if true): {card['falsify'][:160]}"
            )
        return "\n".join(lines)

    def _fire_without_retrieval(self, turn: int, reason: str, qr: dict,
                                phase: str) -> tuple[str, dict] | None:
        """G0.5 P0/P1/P2:触发器已触发(完整记录日志,冷却/上限语义
        相同),但不做任何记忆检索。P0 什么都不注入;P1/P2 注入各自
        的冻结文本。事件带 retrieval_status=NOT_RUN — 只作记录,绝不
        计为 EMPTY。"""
        block = {
            "reason_only": _reason_only_block(reason),
            "generic_refresh": GENERIC_REFRESH_BLOCK,
        }.get(self.injection_mode)
        event = {
            "episode": "",  # finalize 时从输出目录回填
            "task": os.environ.get("RPENT_TASK", ""),
            "turn": turn,
            "phase": phase,
            "last_action": qr.get("name", ""),
            "symptom": reason,
            "observation_summary": "",
            "trigger_reason": reason,
            "trigger_mode": self.mode,
            "query_mode": self.query_mode,
            "injection_mode": self.injection_mode,
            "retrieval_method": self.rank,
            "candidate_memory_ids": [],
            "retrieval_status": "NOT_RUN",
            "retrieval_empty": None,
            "trigger_fired": True,
            "scores": [],
            "ranked_memory_ids": [],
            "top1_memory": "",
            "top3_memories": [],
            "retrieval_latency_ms": 0.0,
            "task_language": self.task_language,
            "planner_next_action": None,
            "planner_followed_top1": None,
            "planner_followed_any_top3": None,
            "verification_result": None,
            "episode_result": None,
        }
        if block is not None:
            event["retrieval_tokens"] = len(block.split())
        self.events.append(event)
        logger.info("[memrecall] turn=%s trigger=%s injection=%s "
                    "retrieval=NOT_RUN (logged%s)", turn, reason,
                    self.injection_mode,
                    ", injected" if block is not None else ", no injection")
        return (block, event) if block is not None else None

    # ------------------------------------------------------------- 收尾
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
                    # default=str:插桩绝不能再因意外的字段类型丢事件
                    # (2026-09-17 smoke 事故)
                    f.write(json.dumps(e, ensure_ascii=False,
                                       default=str) + "\n")
            logger.info("[memrecall] wrote %d events", len(self.events))
        except Exception as e:  # noqa: BLE001 - 绝不让 run 失败
            logger.warning("[memrecall] failed to write events: %s", e)
