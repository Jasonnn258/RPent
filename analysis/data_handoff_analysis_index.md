# Data Handoff — 分析层文件索引(data_handoff_analysis_index.md)

_生成于 2026-09-23(handoff 轮 §5)。定位 G0.5/G0.6 及其溯源链上的全部持久分析产物。
last_commit = 最后触碰该文件的 commit(NEW = 本轮新建未 commit)。分支
`research/pre-ovpm-20260905` 已 push(afb7a89)。清单文件名以实际路径为准,
不要求与外部规格中的名字逐字一致。_

| stage | logical_name | actual_path | exists | git_tracked | last_commit | notes |
|---|---|---|---|---|---|---|
| G0.6 | runs 逐格明细 | `analysis/stageG06_runs.csv` | yes | yes | c439c7a | 180 行 final cells,P0/P2/P4 × t3/t5/t9 × s1-s20;success/turns/wall/fires/injections/tokens/recovery_any/stalled@3 |
| G0.6 | events 事件流 | `analysis/stageG06_events.jsonl` | yes | yes | c439c7a | 366 条 trigger/注入/检索事件,recovery@3 与逐 decision-point 分析的直接输入 |
| G0.6 | results 汇总(md) | `analysis/stageG06_results.md` | yes | yes | c439c7a | 三臂总览表+三对比+CASE 判定+recovery 四问+成本对比 |
| G0.6 | results 汇总(json) | `analysis/stageG06_results.json` | yes | yes | c439c7a | 同上机器可读版,含 by_task 明细与 infra 计数 |
| G0.6 | 方向判定 | `analysis/stageG06_direction_decision.md` | yes | yes | c439c7a | §19 十问 + CASE D 判定 + G1-G4 处置建议 + 运行完整性账 |
| G0.6 | 预注册 | `analysis/stageG06_preregistration.md` | yes | yes | fb6b51c | 三 RQ/8pp 阈值/CASE A-F 树,先于任何 episode commit(fb6b51c) |
| G0.6 | seed manifest | `analysis/stageG06_seed_manifest.md` | yes | yes | 2f8f0d1 | s11-s20 机械选种依据 + tier 勘误记录 |
| G0.6 | 冻结审计 | `analysis/stageG06_freeze_audit.md` | yes | yes | fb6b51c | 臂定义/触发器/指标冻结清单 |
| G0.6 | 429 事故账 | `analysis/stageG06_quota429_incident.md` | yes | yes | 71bd58f | 63 格污染取证 + 分类器补丁 + CSV 手术 + 重跑计划 |
| G0.6 | 429 删除行清单 | `analysis/stageG06_quota429_deleted_rows.json` | yes | yes | 71bd58f | 被手术删除的 63 行逐行记录(可复查) |
| G0.5 | runs 逐格明细 | `analysis/stageG05_runs.csv` | yes | yes | e1cae34 | G0.5 120 episode 逐格表(s1-s10 段后被 G0.6 复用) |
| G0.5 | events 事件流 | `analysis/stageG05_events.jsonl` | yes | yes | e1cae34 | G0.5 事件流 |
| G0.5 | results 汇总(md) | `analysis/stageG05_results.md` | yes | yes | e1cae34 | 六对比 + CASE E/MIXED 判定 |
| G0.5 | results 汇总(json) | `analysis/stageG05_results.json` | yes | yes | e1cae34 | 机器可读版 |
| G0.5 | 方向判定 | `analysis/stageG05_direction_decision.md` | yes | yes | e1cae34 | §23 STOP 判定文档 |
| G0.5 | 预注册 | `analysis/stageG05_preregistration.md` | yes | yes | 57428a5 | G0.5 预注册 |
| G0.5 | reason 流向审计 | `analysis/stageG05_reason_flow_audit.md` | yes | yes | e613a41 | 触发 reason 流向(generic vs specific) |
| G0.5 | campaign 暂停账 | `analysis/stageG05_campaign_pause.md` | yes | yes | 23c62a1 | G1 中止 + orphan 收养记录 |
| G0.5 | 回归审计 | `analysis/stageG05_regression_audit.md` | yes | yes | 57428a5 | s1-s10 复用行逐格回归核对 |
| G0 | 结果(md) | `analysis/stageG0_results.md` | yes | yes | 9d9da3c | G0 五臂因果分解(A/C 复用行 + 新 90 集) |
| G0 | 结果(json) | `analysis/stageG0_results.json` | yes | yes | 9d9da3c | 机器可读版,含 P4=g0D 臂定义源头 |
| G0 | verdict | `analysis/stageG0_verdict.md` | yes | yes | 5d5be54 | 四门槛 go/no-go 判定 |
| G0 | manifest | `analysis/stageG0_manifest.md` | yes | yes | 9f048af | G0 预运行 manifest |
| G0 | 触发语义审计 | `analysis/stageG0_trigger_semantics_audit.md` | yes | yes | 9f048af | R1-R5 触发语义冻结 |
| master | outcome 主表 | `analysis/outcome_validation_runs.csv` | yes | yes | afb7a89 | 全实验主 CSV(1019 行);G0.6 网格 180 行=最终分析输入;afb7a89 提交最终 63 行 |
| C(C3) | C3 结果(md) | `analysis/memory_stageC_results.md` | yes | yes | 332ffa7 | recovery/trigger/SR 的原始出处:PROGRESS 触发 SR .733→.852 |
| C(C3) | C3 结果(json) | `analysis/memory_stageC_results.json` | yes | yes | 332ffa7 | 机器可读版 |
| C(C1) | C1 检索基准结果 | `analysis/memory_stageC1_results.json` | yes | yes | eec5477 | 词面检索 R@k 锚点数字(D0 回归基准) |
| C(C1) | C1 冻结 query 集 | `analysis/memory_stageC1_queries.jsonl` | yes | yes | eec5477 | 134 点(120 gold+14 hardneg)冻结 query |
| C(C2) | C2 结果(json) | `analysis/memory_stageC2_results.json` | yes | yes | 7e5f276 | label 流/recovery@3 指标定义的冻结实现来源 |
| C(C2) | C2 结果(md) | `analysis/memory_stageC2_design.md` | yes | yes | 7e5f276 | 设计文档 |
| C | 兼容性审计 | `analysis/stageC_compatibility_audit.md` | yes | yes | 36dcda7 | 在线臂差异审计先例 |
| infra | C 阶段中断账 | `analysis/stageC_outage_ledger.md` | yes | yes | 332ffa7 | 网络中断+重试纪律的先例记录(infra 判定口径) |
| D | Stage D 结果(md) | `analysis/memory_staged_results.md` | yes | yes | f9e4cb1 | typed-address 卡侧检索负结果(前史,不进本轮 bundle) |
| handoff | git 审计 | `analysis/data_handoff_git_audit.md` | yes | no | NEW | 本轮 §1-4 执行记录(push 成功 afb7a89) |

## 缺失项

无。上表 exists 列全部 yes。

## 说明

- G0.6 的 runs/events/results 即 bundle `metadata/` 的数据源(§10)。
- Stage C 系列列入是因为 G0.5/G0.6 的 recovery@3、trigger 语义、infra 判定口径
  全部沿用 C 阶段冻结定义,做逐轨迹分析时需回查。
- Stage D/A/B 系列结果文件在 analysis/ 下同样存在,但不属于本轮 handoff 范围,
  未列入(见 data_handoff_report.md 排除清单)。
