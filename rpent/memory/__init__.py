"""结构化全局记忆 v1 —— 可执行的按 phase 限定范围的规则。

把自由文本 Global Memory 转换成前置条件门控的规则,planner
通过逐轮 phase 上下文注入来读取。纯逻辑都在这里;与 planner 的
集成由 ``rpent.planner.api_loop`` 里的 ``RPENT_STRUCTURED_MEMORY=1`` 门控。
"""
