"""B2 —— 证据充分的状态转移验证(B2 臂)。

B1(:mod:`rpent.memory.ovpm`)用工具结果自身字段上的二元 outcome 检查
来评判动作 —— 最典型的坑是 ``pi0_pick`` 的紧握信号,空手爪只是
合拢在无物上时它也会触发。B2 把*二元 outcome* 问题("上报的指标
过了吗?")换成*状态转移*问题:给定前置状态、动作和
后置状态,世界是否按这类动作理应造成的方式发生了变化?

模板是动作级且通用的(GRASP / PLACE / TRANSPORT /
CONTACT / ROTATE)。没有 task 范围规则、没有 phase 限定、没有新工具。
证据只来自 planner 已经看到的东西:工具结果字段
(本体感知、官方终止标志)、SAM3 ``segment`` /
``back_project`` 的世界坐标,以及 ``view_driver_state``。没有 benchmark
真值、没有特权物体坐标。

GRASP 确认永远要求物体级状态证据(物体
离开了支撑物/随手爪移动):基于 160 次录制的
arm-B 抓取做标定,真握与假握的手爪开合分布完全
重叠,因此仅凭本体感知可以证伪一次抓取(手爪一直
张开)却永远无法证实它。

裁决是三向的并驱动一个显式的下一步决策:

  CONFIRMED_SUCCESS -> COMMIT    继续;进一步验证是冗余的
  CONFIRMED_FAILURE -> RECOVER   换策略;不要原样重试
  UNCERTAIN         -> OBSERVE   一次定向观察;若仍不能
                                 定论则 REASON(有界,绝不循环)

每条判定都连同前置状态摘要、期望与观测到的变化、证据列表、裁决、
决策以及产生它的规则模板,一起追加到 ``<output_dir>/b2_events.jsonl``。

注入行绝不能包含子串 "fail"/"error"/"could
not"/"no object":PhaseTracker 的 pick 启发式会在结果文本里 grep
这些词。因此 ``CONFIRMED_FAILURE`` 只存在于 JSONL 和
指标里;注入行说 "objective NOT established"。

门控:``RPENT_OVPM2=1``(需要 ``RPENT_STRUCTURED_MEMORY=1`` —— SM1
tracker 为日志和延迟记账提供 phase 上下文,
仅此而已)。
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from rpent.memory.ovpm import (
    GRIP_OPEN,
    GRIP_TIGHT,
    MOVE_TOL,
    _fields_from_payload,
)
from rpent.memory.schema import PHASE_ORDER

logger = logging.getLogger(__name__)

#: 动作工具 -> 规则模板。构造上即通用:按动作
#: 语义作键,绝不按 task 身份。
TEMPLATES: dict[str, str] = {
    "pi0_pick": "GRASP",
    "release": "PLACE",
    "set_gripper": "PLACE",  # 仅在张开时评判(gripper <= 0)
    "move_to": "TRANSPORT",
    "move_pose": "TRANSPORT",
    "pi0_doubled": "CONTACT",
    "rotate_wrist": "ROTATE",
    "rotate_pitch": "ROTATE",
}

EXPECTED_CHANGE: dict[str, str] = {
    "GRASP": (
        "object held: gripper closed on the object (fingers blocked apart, "
        "not pinned shut), object detached from its original support, object "
        "moving with the gripper"
    ),
    "PLACE": (
        "object no longer held: gripper opened, object at rest at the "
        "intended place location, final relation consistent with the task goal"
    ),
    "TRANSPORT": (
        "purpose-relative only: end effector arrived at the commanded target "
        "with the carried object still along"
    ),
    "CONTACT": "contact skill achieved its effect (official termination set)",
    "ROTATE": "wrist reached the commanded orientation",
}

# --------------------------------------------------------------- 阈值
# 与 B1 共享的量复用其常量;其余是 B2 自己的。

NEVER_CLOSED_TOL = 0.06  # min_gripper_opening 高于此 = 从未闭合
FULLY_CLOSED_EPS = 0.004  # 低于此值说明手指空夹合死
LIFT_MIN = 0.05  # pi0_pick 自带的抬升阈值
OBJ_MOVE_TOL = 0.04  # 计为"离开支撑物"的位移量
OBJ_STAY_TOL = 0.03  # 距抓前位置在此值内 = 被留在原地
HOLD_RADIUS = 0.15  # 物体距 eef 在此值内 = 与被握一致
NEAR_EEF = 0.08  # 更紧的 release 后歧义带
PLACE_TOL = 0.10  # 物体距上一个 transport 目标在此值内
PLACE_FAR = 0.20  # 距目标(且距 eef)超过此值 = 放错位置
MAX_OBSERVE_ROUNDS = 2  # 每个未决验证的定向观察次数
STALL_STEPS = 4  # 升级到 REASON 前无动作的工具结果数

_MAX_EVENT_LOG = 400


def _dist(a: tuple[float, ...] | None, b: tuple[float, ...] | None) -> float | None:
    if not a or not b or len(a) < 3 or len(b) < 3:
        return None
    return float(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)) ** 0.5)


def _xyz(v: Any) -> tuple[float, float, float] | None:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        try:
            return (float(v[0]), float(v[1]), float(v[2]))
        except (TypeError, ValueError):
            return None
    return None


# --------------------------------------------------------------- 标签词
# 冒烟运行发现(2026-09-15):planner 会用不同措辞分割同一个
# 对象(抓取前 "the black patterned bowl",抓取后
# "the black patterned bowl held in the gripper"),并通过自然
# 语言抓取("grasp the upper right black bowl by the rim")。精确字符串
# 标签相等因此会漏掉证据;改按共享的实词
# 匹配。回退标签("segment@12")不带语义。

_LABEL_STOP = frozenset({
    "the", "a", "an", "of", "on", "in", "at", "to", "by", "with", "and",
    "or", "not", "up", "held", "gripper", "robot", "its", "it", "this",
    "that", "from", "for",
})


def _label_tokens(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if w not in _LABEL_STOP and len(w) > 2
    }


def _match_label(query: str, records: dict[str, dict[str, Any]]) -> str | None:
    """与 *query* 共享 >=2 个实词的缓存标签(共享最多者、
    其次取最近观察)。无一达标时返回 None。"""
    q = _label_tokens(query)
    if not q:
        return None
    best: str | None = None
    best_key = (1, -1)  # (共享 token 数, 新近度)— 1 = 未达标
    for lbl, rec in records.items():
        if "@" in lbl:
            continue
        key = (len(q & _label_tokens(lbl)), rec.get("step", -1))
        if key[0] >= 2 and key > best_key:
            best, best_key = lbl, key
    return best


def _labels_related(a: str | None, b: str | None) -> bool:
    """两个标签可能指同一对象(或任一是无语义
    回退标签)时为 True,用于门控哪些观察可以消耗
    一个未决验证轮次。"""
    if not a or not b or "@" in a or "@" in b:
        return True
    return a == b or len(_label_tokens(a) & _label_tokens(b)) >= 2


def _is_grip_maintenance(name: str, kwargs: dict[str, Any]) -> bool:
    """闭合驱动(``set_gripper`` gripper>0)是握持维护,不是
    状态转移步骤:它不得超越未决验证(冒烟
    运行显示 planner 会在执行定向观察之前先加固握持 ——
    证据晚一个动作到达)。"""
    if name != "set_gripper":
        return False
    try:
        return float(kwargs.get("gripper", -1.0)) > 0
    except (TypeError, ValueError):
        return False


class TransitionVerifier:
    """喂入工具结果;产出三向裁决行和指标。

    镜像 :class:`rpent.memory.ovpm.OutcomeValidator`,使 planner 循环
    接线对称:``observe_result`` 返回由调用方追加到
    工具结果文本的行(若有)—— 零额外 turn。裁决文本本身避开
    PhaseTracker 的禁用子串。
    """

    def __init__(self, *, tracker: Any = None, task: str = "") -> None:
        self._tracker = tracker  # 仅为日志/延迟提供 phase 上下文
        self._task = task
        self._step = 0
        self._tool_n: dict[str, int] = {}
        # 世界事实缓存 —— 只在 observe_result 内部改动,因此
        # 动作结果到达那一刻拍的快照就是前置状态。
        self._obj: dict[str, dict[str, Any]] = {}  # 标签 -> {xyz, step}
        self._eef: tuple[float, float, float] | None = None
        self._eef_step = -1
        self._grip: float | None = None
        self._grip_step = -1
        self._held: str | None = None  # 假设被握住的标签
        self._target: tuple[float, float, float] | None = None  # 上一个 transport 目标
        self._target_step = -1
        self._pending: dict[str, Any] | None = None
        self._last_action_step = -1
        # 计数器
        self.n_success = 0
        self.n_failure = 0
        self.n_uncertain = 0
        self.n_observe_directives = 0
        self.n_observe_obeyed = 0
        self.n_reason_escalations = 0
        self.n_redundant_obs = 0
        self.false_positive_caught = 0
        self.uncertain_resolutions = {
            "resolved_success": 0,
            "resolved_failure": 0,
            "resolved_reason": 0,
            "overtaken": 0,
            "unresolved": 0,
        }
        # 延迟事件(语义同 B1:commit = 确认成功 ->
        # 推进;recovery = 确认失败 -> 换动作工具)
        self._open_commit: list[dict[str, Any]] = []
        self._open_recovery: list[dict[str, Any]] = []
        self.commit_events: list[dict[str, Any]] = []
        self.recovery_events: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    # ------------------------------------------------------------- 辅助

    def _phase(self) -> str:
        try:
            return self._tracker.current_phase()
        except Exception:  # noqa: BLE001 - tracker 可选
            return ""

    def _pre_state_summary(self) -> dict[str, Any]:
        """当前事件*之前*已知全部信息的紧凑快照。"""
        return {
            "held": self._held,
            "eef": list(self._eef or ()),
            "eef_step": self._eef_step if self._eef else None,
            "gripper_opening": self._grip,
            "objects": {
                lbl: {"xyz": list(v["xyz"]), "step": v["step"]}
                for lbl, v in self._obj.items()
            },
            "last_transport_target": list(self._target or ()),
        }

    def _last_label(self, real_only: bool = False) -> str | None:
        """最近观察到的对象标签(planner 在抓取前一刻定位
        抓取目标 —— 动作级而非 task 级)。
        ``real_only`` 跳过不带可复用语义的点观察
        回退标签("segment@12")。"""
        items = list(self._obj.items())
        if real_only:
            items = [(l, v) for l, v in items if "@" not in l]
        if not items:
            return None
        lbl, v = max(items, key=lambda kv: kv[1]["step"])
        return lbl if v["step"] >= 0 else None

    @staticmethod
    def _segment_directive(label: str | None) -> str:
        """可执行的观察指令;绝不引用回退标签。"""
        if label and "@" not in label:
            return f"segment(prompt='{label}', camera='agentview')"
        return "segment the object in question (text prompt or point)"

    # ------------------------------------------------------------ 事件 IO

    def _emit(self, ev: dict[str, Any]) -> None:
        ev.setdefault("episode", _episode_id())
        ev.setdefault("task", self._task)
        ev.setdefault("seed", os.environ.get("RPENT_B2_SEED", ""))
        ev.setdefault("repeat", os.environ.get("RPENT_B2_REPEAT", ""))
        ev.setdefault("turn", self._step)
        ev.setdefault("phase", self._phase())
        ev.setdefault("confidence", None)
        ev.setdefault("verification_source", "tool_result_fields+state_cache")
        if len(self.events) < _MAX_EVENT_LOG:
            self.events.append(ev)
        try:
            out = _output_dir()
            if out is not None:
                with open(out / "b2_events.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        except Exception as e:  # noqa: BLE001 - 日志绝不能搞挂运行
            logger.warning("[b2] event log write failed: %s", e)

    def _base_event(
        self, tool: str, template: str, pre: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "action": tool,
            "rule_template": template,
            "expected_change": EXPECTED_CHANGE[template],
            "pre_state_summary": pre,
            "observed_change": "",
            "evidence_for_success": [],
            "evidence_for_failure": [],
            "missing_evidence": [],
            "b1_style_would_match": None,
            "pending_of": None,
        }

    # -------------------------------------------------------- 裁决行

    def _commit_line(self, tool: str, why: str, what_next: str) -> str:
        n = self._tool_n.get(tool, 0)
        return (
            f"[b2] {tool}#{n} state change CONFIRMED — {why}. "
            f"Commit: {what_next} Further verification of this step is redundant."
        )

    def _recover_line(self, tool: str, why: str, what_next: str) -> str:
        n = self._tool_n.get(tool, 0)
        return (
            f"[b2] {tool}#{n} objective NOT established — {why}. "
            f"Recover: {what_next}"
        )

    def _observe_line(self, tool: str, missing: str, directive: str) -> str:
        return (
            f"[b2] {tool} evidence incomplete ({missing}). Observe once before "
            f"proceeding: {directive} Act on what you see — repeating {tool} "
            "unchanged before checking is discouraged."
        )

    def _reason_line(self, tool: str, rounds: int) -> str:
        return (
            f"[b2] evidence about {tool} is still incomplete after {rounds} "
            "directed observations. Reason explicitly: state what the last "
            "action achieved and what it did not, then choose ONE deliberate "
            "next step (retry once with a changed approach, or proceed and "
            "verify at the next natural checkpoint). Alternating checks "
            "without acting burns the budget."
        )

    # --------------------------------------------------------- 主入口

    def observe_result(
        self,
        name: str,
        kwargs: dict[str, Any],
        result_text: str,
        *,
        is_error: bool = False,
        phase: str | None = None,
    ) -> str | None:
        """观察一个工具结果;返回裁决行或 None。"""
        self._step += 1
        self._tool_n[name] = self._tool_n.get(name, 0) + 1
        ph = phase if phase is not None else self._phase()
        try:
            payload = json.loads(result_text)
        except Exception:  # noqa: BLE001 - 无法解析
            payload = None
        if not isinstance(payload, dict):
            payload = None

        if name in ("segment", "back_project", "view_driver_state"):
            line = self._observe_perception(name, kwargs, payload, ph)
            self._close_events(name, ph)
            return line

        template = TEMPLATES.get(name)
        if template is None:
            # finish + 中性工具:自身无裁决,但 finish
            # 会关闭打开中的延迟事件(记账口径同 B1)。
            self._close_events(name, ph)
            return None

        # 验证未决期间出现新动作:planner 未产出所求证据就
        # 继续走了 —— 记录并清除。握持
        # 维护(闭合 set_gripper)是透明的:它不回答
        # 任何问题,但也不会把计划推过这一步。
        if self._pending is not None and not _is_grip_maintenance(name, kwargs):
            self._resolve_pending_overtaken(ph, by=name)

        pre = self._pre_state_summary()
        line = self._judge_action(name, kwargs, payload, pre, ph, is_error)
        self._last_action_step = self._step
        self._update_cache_from_action(name, kwargs, payload)
        self._close_events(name, ph)
        return line

    def _update_cache_from_action(
        self,
        name: str,
        kwargs: dict[str, Any],
        payload: dict[str, Any] | None,
    ) -> None:
        """把动作结果的本体感知并入世界缓存。"""
        if not isinstance(payload, dict):
            return
        f = _fields_from_payload(payload)
        if name in ("move_to", "move_pose"):
            eef = _xyz(payload.get("final_eef_pos"))
            if eef is not None:
                self._eef = eef
                self._eef_step = self._step
        grip = f.get("final_gripper_opening")
        if grip is not None:
            try:
                self._grip = float(grip)
                self._grip_step = self._step
            except (TypeError, ValueError):
                pass

    # ---------------------------------------------------------- 感知

    def _observe_perception(
        self,
        name: str,
        kwargs: dict[str, Any],
        payload: dict[str, Any] | None,
        ph: str,
    ) -> str | None:
        if payload is None:
            return None
        if name in ("segment", "back_project"):
            xyz = _xyz(payload.get("world_xyz"))
            found = payload.get("found", True)
            label = None
            if name == "segment":
                p = str(kwargs.get("prompt") or "").strip()
                if p:
                    label = p
            if label is None:
                label = f"{name}@{self._step}"
            if xyz is not None and found is not False:
                prev = self._obj.get(label)
                if (
                    prev
                    and _dist(prev["xyz"], xyz) is not None
                    and _dist(prev["xyz"], xyz) < 0.01
                ):
                    self.n_redundant_obs += 1
                self._obj[label] = {"xyz": xyz, "step": self._step}
            elif self._pending and self._pending.get("wants") == "object_position":
                # 定向观察执行了但没给出位置 —— 仅当它
                # 针对未决项的对象时才算一轮停滞。
                if _labels_related(self._pending.get("label"), label):
                    return self._resolve_pending(
                        ph, obs_xyz=None, obs_label=label
                    )
            return self._maybe_resolve(ph)
        # view_driver_state:为缓存补充新鲜本体感知
        st = payload.get("state") or {}
        eef = _xyz(st.get("robot0_eef_pos"))
        if eef is not None:
            self._eef = eef
            self._eef_step = self._step
        gq = st.get("robot0_gripper_qpos")
        if isinstance(gq, (list, tuple)) and len(gq) >= 2:
            try:
                self._grip = float(abs(gq[0]) + abs(gq[1]))
                self._grip_step = self._step
            except (TypeError, ValueError):
                pass
        return self._maybe_resolve(ph)

    def _maybe_resolve(self, ph: str) -> str | None:
        if not self._pending:
            return None
        if self._pending.get("wants") == "object_position":
            label, rec = self._pending_target_record()
            if rec is not None:
                self._pending["label"] = label  # 首次目击即采纳
                return self._resolve_pending(ph, obs_xyz=rec["xyz"], obs_label=label)
            return None
        # wants == driver_state(set_gripper 执行器检查)
        if self._grip is not None and self._grip_step > self._pending["open_step"]:
            return self._resolve_pending(ph, obs_xyz=None, obs_label=None)
        return None

    def _pending_target_record(
        self,
    ) -> tuple[str | None, dict[str, Any] | None]:
        """未决验证所询问对象的(动作后)新目击;无可用
        信息到达时为 ``(None, None)``。

        带语义标签的未决项在任何措辞下都按自己的标签落定
        (token 匹配);*无关*观察不能回答它。
        无语义标签的未决项接受最新的目击 —— 指令
        已告诉 planner 该看哪个对象。
        """
        p = self._pending
        if p is None:
            return None, None
        fresh = {
            l: r for l, r in self._obj.items() if r["step"] > p["open_step"]
        }
        label = p.get("label")
        if label and "@" not in label:
            if label in fresh:
                return label, fresh[label]
            m = _match_label(label, fresh)
            if m is not None:
                return m, fresh[m]
            return None, None
        if fresh:
            lbl = max(fresh, key=lambda l: fresh[l]["step"])
            return lbl, fresh[lbl]
        return None, None

    # ------------------------------------------------------------ 动作

    def _judge_action(
        self,
        name: str,
        kwargs: dict[str, Any],
        payload: dict[str, Any] | None,
        pre: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        template = TEMPLATES[name]
        ev = self._base_event(name, template, pre)
        f = _fields_from_payload(payload or {})

        # set_gripper 只在张开时才算一次 PLACE 尝试
        if payload is None and not is_error:
            return None  # 结果无法解析 —— 不存在状态转移问题
        if name == "set_gripper":
            try:
                g = float(kwargs.get("gripper", -1.0))
            except (TypeError, ValueError):
                g = -1.0
            if g > 0:
                return None  # 闭合驱动:无状态转移问题

        if template == "GRASP":
            return self._judge_grasp(name, kwargs, ev, f, ph, is_error)
        if template == "PLACE":
            return self._judge_place(name, ev, f, ph, is_error)
        if template == "TRANSPORT":
            return self._judge_transport(name, kwargs, ev, f, ph, is_error)
        if template == "CONTACT":
            return self._judge_contact(name, ev, f, ph, is_error)
        return self._judge_rotate(name, ev, f, ph, is_error, payload)

    def _judge_grasp(
        self,
        name: str,
        kwargs: dict[str, Any],
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        mg = f.get("min_gripper_opening")
        fg = f.get("final_gripper_opening")
        pl = f.get("peak_lift_m")
        succ = f.get("success")
        term = f.get("libero_terminated")
        ev["b1_style_would_match"] = bool(
            succ is True or (mg is not None and mg < GRIP_TIGHT)
        )
        n_checks = checks = 0

        def ratio() -> float | None:
            return round(checks / n_checks, 2) if n_checks else None

        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the attempt did not execute", "retry once with an adjusted "
                "approach, then report honestly via finish"
            )
        if term is True:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change="official termination set during the attempt",
                evidence_for_success=["libero_terminated=true"],
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name, "the task condition is met", "call finish now."
            )
        if mg is None and succ is None:
            return None  # 无可机检内容 —— 不做判定

        if mg is not None:
            n_checks += 1
            if mg > NEVER_CLOSED_TOL:
                checks += 1
                ev["evidence_for_failure"].append(
                    f"gripper never closed (min opening {float(mg):.3f})"
                )
        if pl is not None:
            n_checks += 1
            if pl >= LIFT_MIN:
                checks += 1
                ev["evidence_for_success"].append(
                    f"eef ascended {float(pl):.2f} m after the descent"
                )
        if fg is not None:
            n_checks += 1
            if fg <= NEVER_CLOSED_TOL:
                checks += 1
                ev["evidence_for_success"].append(
                    f"gripper still closed at return ({float(fg):.3f})"
                )

        if ev["evidence_for_failure"]:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="no closure on the target",
                confidence=ratio(),
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                "the gripper did not close on the target",
                "adjust the approach (pose/clearance) and retry once; an "
                "unchanged retry is discouraged",
            )

        # GRASP 确认永远要求物体级状态证据。
        # 标定(2026-09-15,160 次 armB 抓取,dev t0/t7/t9 + heldout
        # t1/t4/t8):真握与假握的 min_gripper_opening 分布完全
        # 重叠(success=true 的假阳性跨度
        # 0.001-0.019;成功 episode 的抓取低至 0.0010)——
        # 没有任何本体感知区间能分开它们。本体感知只能给
        # 假设打分并能证伪(保持张开)。
        # 定向观察的对象身份:pick prompt 的
        # 实词对照缓存感知标签(planner 对同一
        # 对象的措辞各不相同),否则用最近的
        # 真实标签。绝不用点观察回退标签。
        label = (
            _match_label(str(kwargs.get("prompt") or ""), self._obj)
            or self._last_label(real_only=True)
        )
        pre_pos = self._obj.get(label, {}).get("xyz") if label else None
        if mg is not None and mg <= FULLY_CLOSED_EPS:
            ev["evidence_for_failure"].append(
                "gripper pinned fully shut — closure width consistent with "
                "grabbing nothing (thin objects excepted)"
            )
        elif mg is not None:
            ev["evidence_for_success"].append(
                f"closure stopped at {float(mg):.3f} m — consistent with "
                "something between the fingers"
            )
        ev["missing_evidence"].append(
            "object displacement: has the target left its original support "
            "and does it now move with the gripper?"
        )
        directive = self._segment_directive(label)
        directive += (
            " — if its position left the earlier spot and sits near the "
            "gripper, the hold is real; if it stayed put, the grasp did not "
            "take. Closure width and lift cannot distinguish a real hold "
            "from fingers closing on nothing, and firming the grip or moving "
            "on does not answer this."
        )
        ev.update(
            verdict="UNCERTAIN",
            next_decision="OBSERVE",
            observed_change="proprioception alone cannot confirm the object "
            "is held",
            confidence=ratio(),
        )
        self._open_pending(
            name, "GRASP", label=label, pre_pos=pre_pos, wants="object_position", ph=ph
        )
        self.n_uncertain += 1
        self.n_observe_directives += 1
        self._emit(ev)
        return self._observe_line(
            name,
            "object displacement unknown",
            directive,
        )

    def _judge_place(
        self,
        name: str,
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        pg = f.get("peak_gripper_opening")
        term = f.get("libero_terminated")
        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the placement did not execute",
                "retry once, then report honestly via finish",
            )
        if term is True:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change="official termination set",
                evidence_for_success=["libero_terminated=true"],
            )
            self._held = None
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name, "the task condition is met", "call finish now."
            )
        if pg is not None and pg <= GRIP_OPEN:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change=f"gripper stayed shut (peak opening "
                f"{float(pg):.3f})",
                evidence_for_failure=[
                    "gripper did not open — object was not released"
                ],
                confidence=1.0,
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                "the gripper did not open",
                "re-attempt with set_gripper(gripper=-1.0); escalate the "
                "placement method if it repeats",
            )
        # 执行器层面已释放;物体级问题(静止在
        # 目标位置、离开手爪)需要观察。
        label = self._held or self._last_label(real_only=True)
        wants = "object_position"
        if name == "set_gripper" and pg is None:
            wants = "driver_state"  # 先做执行器确认
        directive = self._segment_directive(label)
        directive += (
            " — confirm it now rests at the intended location and is clear "
            "of the gripper."
        )
        ev["missing_evidence"].append(
            "final relation: object at rest at the intended place location"
        )
        if pg is not None:
            ev["evidence_for_success"].append(
                f"gripper opened (peak {float(pg):.3f}) — object no longer "
                "attached at the actuator level"
            )
        ev.update(
            verdict="UNCERTAIN",
            next_decision="OBSERVE",
            observed_change="release actuated; object-level outcome unverified",
            confidence=0.5 if pg is not None else None,
        )
        self._open_pending(
            name, "PLACE", label=label, pre_pos=None, wants=wants, ph=ph
        )
        self.n_uncertain += 1
        self.n_observe_directives += 1
        self._emit(ev)
        return self._observe_line(
            name, "final object position unknown", directive
        )

    def _judge_transport(
        self,
        name: str,
        kwargs: dict[str, Any],
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        d = f.get("final_dist_m")
        target = _xyz(kwargs.get("xyz") or kwargs.get("target"))
        if target is not None:
            self._target = target
            self._target_step = self._step
        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the move did not execute",
                "retry once, then report honestly via finish",
            )
        if d is None:
            return None
        if float(d) <= MOVE_TOL:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change=f"arrived ({float(d):.3f} m residual)",
                evidence_for_success=[f"final_dist_m={float(d):.3f} <= "
                                      f"{MOVE_TOL}"],
                confidence=1.0,
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name,
                f"arrival within {float(d):.3f} m of the commanded target",
                "proceed with the next planned step at this location.",
            )
        ev.update(
            verdict="CONFIRMED_FAILURE",
            next_decision="RECOVER",
            observed_change=f"stopped short ({float(d):.3f} m residual)",
            evidence_for_failure=[
                f"final_dist_m={float(d):.3f} > {MOVE_TOL}"
            ],
            confidence=1.0,
        )
        self._register_failure(ev, ph)
        self._emit(ev)
        return self._recover_line(
            name,
            f"the servo did not converge ({float(d):.3f} m residual)",
            "re-localize the target once (one back_project), then make one "
            "deliberate move straight to it",
        )

    def _judge_contact(
        self,
        name: str,
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
    ) -> str | None:
        succ = f.get("success")
        term = f.get("libero_terminated")
        if is_error:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="tool raised before any state change",
                evidence_for_failure=["tool raised"],
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name, "the skill did not execute",
                "retry once, then report honestly via finish",
            )
        if term is True or succ is True:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change="official termination set",
                evidence_for_success=["success mirrors official termination"],
                confidence=1.0,
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return self._commit_line(
                name, "the task condition is met", "call finish now."
            )
        if succ is False:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change="termination not reached after the skill",
                evidence_for_failure=[
                    "success=false (mirrors official termination)"
                ],
                confidence=1.0,
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                "the contact skill did not reach the task condition",
                "make ONE corrective attempt, then report honestly via "
                "finish",
            )
        return None

    def _judge_rotate(
        self,
        name: str,
        ev: dict[str, Any],
        f: dict[str, Any],
        ph: str,
        is_error: bool,
        payload: dict[str, Any] | None = None,
    ) -> str | None:
        fe = (payload or {}).get("final_err", f.get("final_err"))
        if fe is None:
            return None
        err = abs(float(fe))
        if is_error or err > 0.08:
            ev.update(
                verdict="CONFIRMED_FAILURE",
                next_decision="RECOVER",
                observed_change=f"orientation error {err:.3f} rad remains",
                evidence_for_failure=[f"final_err={float(fe):.3f}"],
                confidence=1.0,
            )
            self._register_failure(ev, ph)
            self._emit(ev)
            return self._recover_line(
                name,
                f"the wrist is {err:.3f} rad off the commanded orientation",
                "re-issue once with a corrected target, then move on",
            )
        if err <= 0.05:
            ev.update(
                verdict="CONFIRMED_SUCCESS",
                next_decision="COMMIT",
                observed_change=f"orientation reached ({err:.3f} rad error)",
                evidence_for_success=[f"final_err={float(fe):.3f}"],
                confidence=1.0,
                quiet=True,
            )
            self._register_success(ev, ph)
            self._emit(ev)
            return None  # 静默:旋转成功无需行为改变
        ev.update(
            verdict="UNCERTAIN",
            next_decision="PROCEED",
            observed_change=f"orientation error {err:.3f} rad — marginal",
            missing_evidence=["whether the residual matters for the next step"],
            confidence=0.5,
        )
        self.n_uncertain += 1
        self._emit(ev)
        return None

    # ------------------------------------------------------------ 未决项

    def _open_pending(
        self,
        tool: str,
        template: str,
        *,
        label: str | None,
        pre_pos: tuple[float, float, float] | None,
        wants: str,
        ph: str,
    ) -> None:
        self._pending = {
            "tool": tool,
            "template": template,
            "label": label,
            "pre_pos": pre_pos,
            "wants": wants,
            "open_step": self._step,
            "open_phase": ph,
            "rounds": 0,
            "stalled_hinted": False,
        }

    def _resolve_pending_overtaken(self, ph: str, by: str) -> None:
        p = self._pending
        if p is None:
            return
        self.uncertain_resolutions["overtaken"] += 1
        ev = self._base_event(by, p["template"], self._pre_state_summary())
        ev.update(
            verdict="UNCERTAIN",
            next_decision="PROCEED",
            observed_change=f"planner ran {by} before the requested evidence "
            "arrived",
            missing_evidence=["the directed observation never ran"],
            pending_of=p["tool"],
            rounds=p["rounds"],
        )
        self.n_uncertain += 0  # 打开时已计数
        self._emit(ev)
        self._pending = None

    def _resolve_pending(
        self,
        ph: str,
        *,
        obs_xyz: tuple[float, float, float] | None,
        obs_label: str | None,
    ) -> str | None:
        p = self._pending
        if p is None:
            return None
        p["rounds"] += 1
        self.n_observe_obeyed += 1  # 定向观察确实到达了
        rounds = p["rounds"]
        ev = self._base_event(p["tool"], p["template"], self._pre_state_summary())
        ev["pending_of"] = p["tool"]
        ev["rounds"] = rounds
        ev["verification_source"] = "directed_observation"

        # --- set_gripper 执行器检查(driver_state 轮)---
        if p["wants"] == "driver_state":
            if self._grip is not None and self._grip > GRIP_OPEN:
                label = p.get("label")
                obj = self._obj.get(label or "", {})
                d_t = _dist(obj.get("xyz"), self._target) if obj else None
                if d_t is not None and d_t <= PLACE_TOL:
                    return self._pending_success(
                        ev, ph,
                        why=f"gripper open ({self._grip:.3f}) and object "
                        f"within {d_t:.2f} m of the intended location",
                    )
                ev["missing_evidence"].append("object position after opening")
                ev.update(
                    verdict="CONFIRMED_SUCCESS",
                    next_decision="COMMIT",
                    observed_change=f"gripper confirmed open "
                    f"({self._grip:.3f})",
                    evidence_for_success=[
                        f"robot0_gripper opening {self._grip:.3f} > "
                        f"{GRIP_OPEN}"
                    ],
                    confidence=0.6,
                )
                self._held = None
                self.uncertain_resolutions["resolved_success"] += 1
                self._register_success(ev, ph)
                self._emit(ev)
                self._pending = None
                return None  # 静默:执行器级确认
            # 执行器也未确认 —— 落入物体轮
            p["wants"] = "object_position"

        # --- object_position 轮(GRASP / PLACE)---
        if obs_xyz is None:
            ev["missing_evidence"].append(
                "observation produced no usable object position"
            )
            return self._pending_stall(ev, ph, rounds)

        label = obs_label or p.get("label")
        eef = self._eef if self._eef_step > p["open_step"] else None
        d_e = _dist(obs_xyz, eef)
        d_pre = _dist(obs_xyz, p.get("pre_pos"))

        if p["template"] == "GRASP":
            if d_pre is not None and d_pre >= OBJ_MOVE_TOL and (
                d_e is None or d_e <= HOLD_RADIUS
            ):
                return self._pending_success(
                    ev, ph,
                    why=f"object moved {d_pre:.2f} m off its original spot"
                    + (f" and rides {d_e:.2f} m from the gripper" if d_e else ""),
                    held=label,
                )
            if d_pre is not None and d_pre <= OBJ_STAY_TOL and (
                d_e is None or d_e > NEAR_EEF
            ):
                ev["b1_style_would_match"] = None  # 由开启者事件设置
                return self._pending_failure(
                    ev, ph,
                    why=f"object stayed at its original support position "
                    f"(moved {d_pre:.2f} m) while the gripper moved away",
                )
            if d_pre is None and d_e is not None and d_e <= NEAR_EEF:
                return self._pending_success(
                    ev, ph,
                    why=f"object now sits {d_e:.2f} m from the end effector "
                    "(no earlier position on record, but it tracks the gripper)",
                    held=label,
                )
            ev["missing_evidence"].append(
                "object displacement does not clearly separate held vs left"
            )
            if d_pre is not None:
                ev["observed_change"] = (
                    f"object moved {d_pre:.2f} m from its pre-pick spot"
                    + (f", {d_e:.2f} m from the eef" if d_e else "")
                )
            return self._pending_stall(ev, ph, rounds)

        # PLACE
        d_t = _dist(obs_xyz, self._target) if self._target else None
        if d_t is not None and d_t <= PLACE_TOL:
            return self._pending_success(
                ev, ph,
                why=f"object rests {d_t:.2f} m from the intended place "
                "location",
                held=None,
            )
        if d_t is not None and d_t > PLACE_FAR and (d_e is None or d_e > NEAR_EEF):
            return self._pending_failure(
                ev, ph,
                why=f"object ended up {d_t:.2f} m from the intended location "
                "and clear of the gripper — it was dropped or displaced",
            )
        ev["missing_evidence"].append(
            "object rest position vs the intended location"
        )
        ev["observed_change"] = (
            f"object at {d_t:.2f} m from the transport target"
            if d_t is not None
            else "object located but no transport target on record"
        ) + (f", {d_e:.2f} m from the eef" if d_e else "")
        return self._pending_stall(ev, ph, rounds)

    def _pending_success(
        self, ev: dict[str, Any], ph: str, *, why: str, held: str | None
    ) -> str:
        p = self._pending or {}
        ev.update(
            verdict="CONFIRMED_SUCCESS",
            next_decision="COMMIT",
            observed_change=why,
            evidence_for_success=[why],
            confidence=0.9,
        )
        self._held = held
        self.uncertain_resolutions["resolved_success"] += 1
        self._register_success(ev, ph)
        self._emit(ev)
        self._pending = None
        tool = p.get("tool", "?")
        if p.get("template") == "GRASP":
            return self._commit_line(
                tool, why, "transport the held object; do not re-grasp."
            )
        return self._commit_line(
            tool, why, "proceed with the plan (finish if this was the goal)."
        )

    def _pending_failure(
        self, ev: dict[str, Any], ph: str, *, why: str
    ) -> str:
        p = self._pending or {}
        ev.update(
            verdict="CONFIRMED_FAILURE",
            next_decision="RECOVER",
            observed_change=why,
            evidence_for_failure=[why],
            confidence=0.9,
        )
        # B1 式检查可能在原动作上匹配过 ——
        # 那种配对正是 B2 为之而生的假阳性类。
        opener = next(
            (e for e in reversed(self.events)
             if e.get("action") == p.get("tool")
             and e.get("pending_of") is None
             and e.get("verdict") == "UNCERTAIN"),
            None,
        )
        if opener is not None and opener.get("b1_style_would_match"):
            self.false_positive_caught += 1
            ev["b1_style_would_match"] = True
        if p.get("template") == "GRASP":
            self._held = None
        self.uncertain_resolutions["resolved_failure"] += 1
        self._register_failure(ev, ph)
        self._emit(ev)
        self._pending = None
        tool = p.get("tool", "?")
        if p.get("template") == "GRASP":
            return self._recover_line(
                tool, why,
                "re-approach with a changed pose and retry once; report "
                "honestly via finish if it repeats",
            )
        return self._recover_line(
            tool, why, "re-localize and re-place once, then report honestly "
            "via finish"
        )

    def _pending_stall(
        self, ev: dict[str, Any], ph: str, rounds: int
    ) -> str | None:
        p = self._pending or {}
        if rounds < MAX_OBSERVE_ROUNDS:
            ev.update(
                verdict="UNCERTAIN",
                next_decision="OBSERVE",
                observed_change=ev.get("observed_change") or "inconclusive",
            )
            self.n_observe_directives += 1
            self._emit(ev)
            label = p.get("label")
            directive = (
                f"one more check: segment or back_project the object"
                + (f" ('{label}')" if label else "")
                + " from the current view — decide from where it sits now"
            )
            return self._observe_line(
                p.get("tool", "?"), "still inconclusive", directive
            )
        ev.update(
            verdict="UNCERTAIN",
            next_decision="REASON",
            observed_change=ev.get("observed_change") or "inconclusive",
        )
        self.uncertain_resolutions["resolved_reason"] += 1
        self.n_reason_escalations += 1
        self._emit(ev)
        tool = p.get("tool", "?")
        self._pending = None
        return self._reason_line(tool, rounds)

    # ------------------------------------------------------------ 延迟

    def _register_success(self, ev: dict[str, Any], ph: str) -> None:
        self.n_success += 1
        self._open_commit.append(
            {
                "tool": ev["action"],
                "step": self._step,
                "phase": ph,
                "template": ev.get("rule_template"),
            }
        )

    def _register_failure(self, ev: dict[str, Any], ph: str) -> None:
        self.n_failure += 1
        self._open_recovery.append(
            {
                "tool": ev["action"],
                "step": self._step,
                "phase": ph,
                "template": ev.get("rule_template"),
            }
        )

    def _close_events(self, name: str, phase: str) -> None:
        from rpent.memory.structured import ACTION_TOOLS

        still: list[dict[str, Any]] = []
        for e in self._open_recovery:
            if name == "finish":
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "finish"
                self.recovery_events.append(e)
                continue
            if name in ACTION_TOOLS and name != e["tool"]:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "switch"
                self.recovery_events.append(e)
                continue
            if name in ACTION_TOOLS and name == e["tool"]:
                e["closed_by"] = "same_tool_repeated"
            still.append(e)
        self._open_recovery = still

        still = []
        for e in self._open_commit:
            if name == "finish":
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "finish"
                self.commit_events.append(e)
                continue
            cur = PHASE_ORDER.get(phase, -1)
            opened = PHASE_ORDER.get(e.get("phase", ""), -1)
            if cur > opened:
                e["latency_steps"] = self._step - e["step"]
                e["closed_by"] = "phase_advanced"
                self.commit_events.append(e)
                continue
            still.append(e)
        self._open_commit = still

    # ------------------------------------------------------------ 边界

    def turn_boundary_hint(self) -> str | None:
        """升级停滞的验证:未决项历经多个工具结果
        却无动作执行、也无定向观察到达。"""
        p = self._pending
        if not p or p.get("stalled_hinted"):
            return None
        # 未决项打开后没有动作执行(开启动作本身满足
        # _last_action_step == open_step)且没有观察
        # 到来 -> 升级一次。
        stalled = (
            self._last_action_step <= p["open_step"]
            and self._step - p["open_step"] >= STALL_STEPS
        )
        if not stalled:
            return None
        p["stalled_hinted"] = True
        self.n_reason_escalations += 1
        self.uncertain_resolutions["resolved_reason"] += 1
        self._pending = None
        return self._reason_line(p["tool"], p["rounds"])

    # ------------------------------------------------------------ 快照

    def snapshot(self, *, success: bool) -> dict[str, Any]:
        """单 episode 的 B2 指标(并入 structured_metrics.json)。"""
        if self._pending is not None:
            self.uncertain_resolutions["unresolved"] += 1
            self._pending = None
        for e in self._open_commit:
            e["closed_by"] = "unclosed"
            e["latency_steps"] = None
            self.commit_events.append(e)
        for e in self._open_recovery:
            e["closed_by"] = "unclosed"
            e["latency_steps"] = None
            self.recovery_events.append(e)
        self._open_commit = []
        self._open_recovery = []

        def _mean(xs: list[int | None]) -> float | None:
            ys = [x for x in xs if x is not None]
            return round(sum(ys) / len(ys), 2) if ys else None

        return {
            "b2": True,
            "task": self._task,
            "n_confirmed_success": self.n_success,
            "n_confirmed_failure": self.n_failure,
            "n_uncertain": self.n_uncertain,
            "n_observe_directives": self.n_observe_directives,
            "n_observe_obeyed": self.n_observe_obeyed,
            "n_reason_escalations": self.n_reason_escalations,
            "n_redundant_observations": self.n_redundant_obs,
            "false_positive_caught": self.false_positive_caught,
            "uncertain_resolutions": dict(self.uncertain_resolutions),
            "commit_events": self.commit_events,
            "recovery_events": self.recovery_events,
            "commit_latency_steps": [
                e["latency_steps"] for e in self.commit_events
            ],
            "commit_latency_mean": _mean(
                [e["latency_steps"] for e in self.commit_events]
            ),
            "recovery_latency_steps": [
                e["latency_steps"] for e in self.recovery_events
            ],
            "recovery_latency_mean": _mean(
                [e["latency_steps"] for e in self.recovery_events]
            ),
            "events": self.events,
            "success": success,
        }


# ------------------------------------------------------------------ 输出

def _output_dir() -> Path | None:
    try:
        from rpent.utils.logging import get_output_dir

        out = get_output_dir()
        return Path(out) if out else None
    except Exception:  # noqa: BLE001 - 可选
        return None


def _episode_id() -> str:
    out = _output_dir()
    return out.name if out is not None else ""
