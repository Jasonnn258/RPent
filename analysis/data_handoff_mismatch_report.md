# Data Handoff — 一致性校验(data_handoff_mismatch_report.md)

_三方核对:outcome_validation_runs.csv `result` vs stageG06_runs.csv `success` vs **raw 侧重判**。raw 重判与调度器 classify_dir (progress_gate_exp.py:145)逐字同口径:states.json 末项 libero_terminated=True → success;未终止且 run.log 含 API timeout → infra_timeout;否则 policy_fail。manifest 另记 planner_finish (planner 显式 FINISH 行)作辅助列。

**核对范围:180 final cells。mismatch 数:0**


补充说明:12 个 success 格 planner 无显式 FINISH 行 —— env 已判定任务完成(states.json libero_terminated=True),随后 planner 的收尾 API 调用挂起(3600s timeout 型,重试纪律处理过的已知接入问题)。按调度器口径(env 优先)这是合法 success,不属于 mismatch,也§14 意义上不是 infra 残留(格的最终判定已落定)。


**0 mismatch** — 三方逐格一致,未做任何静默修改。