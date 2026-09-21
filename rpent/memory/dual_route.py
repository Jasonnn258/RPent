"""结构化记忆 + 双路由推理 —— Fast/Slow 决策器。

叠加在结构化记忆(SM1)之上的一层:phase/规则引擎保持
不变,把每次模型调用都挡在一个决策后面。

- **Fast**:phase 状态符合预期、下一步明确、近期无
  失败 -> 不调用 LLM(不发 Kimi 请求),直接执行结构化
  计划中的一个保守零参动作。
- **Slow**:命中任一触发条件 -> 与现在一样做完整推理。

Fast 动作集刻意最小且零参(所有 move/pick/perceive
动作都需要模型):
    view_driver_state()   -> P_verify 终止检查
    release()             -> 无歧义时 grasp -> 目标放置
    finish(status,summary)-> episode 结束(确认成功或预算耗尽)

路由器是纯的、无副作用:所有状态经参数传入,经
``observe_fast`` 跟踪。它针对 PhaseTracker 桩做过单元测试。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

P_VERIFY = "P_verify"
P_GRASP = "P_grasp"
P_PLACE = "P_place"


@dataclass(frozen=True)
class FastAction:
    """planner 无需调用 LLM 即可执行的一个零参动作。"""

    name: str
    args: dict[str, Any]
    kind: str
    summary: str


class DualRouter:
    """纯 Fast/Slow 决策器。无 I/O;所有输入注入。可测试。"""

    def __init__(self, *, enable_release: bool = True) -> None:
        self.enable_release = enable_release
        # P_verify 链状态(由 observe_fast 依据 vds 结果设置)
        self._vds_done = False
        self._vds_terminated = False
        # Slow 遥测
        self.slow_reason = ""
        self.slow_reasons: list[str] = []

    # ------------------------------------------------------------------ decide
    def decide(
        self, *, total_steps: int, max_turns: int, tracker: Any
    ) -> FastAction | None:
        """返回要执行的 Fast 动作,或 None 以回退到 Slow。

        ``tracker`` 是任何暴露只读 dual-route 接口的对象:
        ``last_is_error``、``recovery_pending()``、``current_phase()``、
        ``last_pick_success``、``moves_since_pick``、``finish_called``。
        """
        # 1. 预算耗尽且 episode 未结束 -> 快速失败
        if total_steps >= max_turns and not tracker.finish_called:
            return FastAction(
                "finish",
                {"status": "failure", "summary": "step budget exhausted"},
                "budget_finish",
                "Fast finish(status=failure) — step budget exhausted.",
            )

        # 2. 近期工具报错 -> 必须由模型恢复
        if tracker.last_is_error:
            return self._slow("last_error")

        # 3. 当前 phase 有规则已满足但尚未触发 -> 必须
        #    由模型消化该恢复(P_verify 除外:下方它的 vds 链
        #    优先且有自己的 finish 路径)
        pending = tracker.recovery_pending()
        if pending is not None and tracker.current_phase() != P_VERIFY:
            return self._slow("pending_rule")

        # 4. P_verify -> view_driver_state/finish 链(构造上不会循环)
        if tracker.current_phase() == P_VERIFY:
            if not self._vds_done:
                return FastAction(
                    "view_driver_state",
                    {},
                    "p_verify_view",
                    "Fast view_driver_state() — confirming final placement / "
                    "episode termination at P_verify.",
                )
            if self._vds_terminated:
                return FastAction(
                    "finish",
                    {"status": "success", "summary": "episode terminated — "
                     "placement confirmed"},
                    "p_verify_finish",
                    "Fast finish(status=success) — episode terminated, "
                    "placement confirmed at P_verify.",
                )
            return self._slow("p_verify_unterminated")

        # 5. release 门:抓取成功、已走到目标、phase 允许
        #    放置、无其他未决项 -> 快速 release()
        if (
            self.enable_release
            and tracker.current_phase() in (P_GRASP, P_PLACE)
            and tracker.last_pick_success
            and tracker.moves_since_pick >= 1
            and pending is None
            and not tracker.last_is_error
        ):
            return FastAction(
                "release",
                {},
                "release",
                "Fast release() — object at target, opening gripper.",
            )

        # 6. 其余情况由模型推理
        return self._slow("not_fast_eligible")

    # ---------------------------------------------------------------- observe
    def observe_fast(self, action: FastAction, result: dict[str, Any]) -> None:
        """把 Fast 动作的结果回填,使下一次 decide 保持一致。"""
        if action.name == "view_driver_state":
            self._vds_done = True
            self._vds_terminated = bool(result.get("libero_terminated"))

    # ------------------------------------------------------------------ slow
    def _slow(self, reason: str) -> None:
        self.slow_reason = reason
        self.slow_reasons.append(reason)
        return None
