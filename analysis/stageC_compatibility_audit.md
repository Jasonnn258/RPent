# Stage C3 Compatibility Audit:O0 ≡ #49 memB2(2026-09-18)

结论:**通过,直接复用 memB2 的 30 行,不重跑。**

| 项 | O0 规格 | #49 memB2 实测 | 一致 |
|---|---|---|---|
| env | ACCESS_FIX=1 + TRIGGER=1(OLD)+ RANK=Q0_FIXED + SM1=1 | `memB2` COND_ENV 完全相同(ovpm_exp.py) | ✓ |
| 模型/端点 | anthropic:glm-5.3-flash @ bigmodel | 同(tier 列 glm-5.3-flash) | ✓ |
| turns/tokens/timeout | 40 / 24576 / 3600s | 同(EVAL_TURNS/PLANNER_MAX_TOKENS/PLANNER_TIMEOUT_S 未改) | ✓ |
| 任务/种子 | t3/t5/t9 × s1-10 × r1 | CSV memB2 30 行全在、无 infra 残留 | ✓ |
| Memory bank / retriever | 冻结 Q0-fixed 词面 + 全局卡库 | resources/libero/global 与 MEMORY.md 自 Stage A 后零改动(git log) | ✓ |
| 注入方式 | soft(Planner 自决) | 同 | ✓ |

代码漂移核验:
- cfda224(Stage B 结果 commit)→ 工作树之前,`rpent/`、`robots/` **零改动**
  (`git diff cfda224 HEAD -- rpent/ robots/` 为空;C1/C2 只加了 analysis/scripts)。
- 本轮为 C3 新增 progress 模式(`RPENT_MEMORY_TRIGGER=progress`):
  retrieval.py 新增 `_progress_observe/_progress_boundary`(独立分支),
  **v1 路径行为不变**(mode 参数默认 "v1";turn_boundary 的 progress 分支在
  phase 追踪之后、v1 逻辑之前 return;on_tool_result 的 progress 调用有
  mode 门控);api_loop 的门从 `== "1"` 放宽为 `∈ {"1","progress"}`,
  "1" 分支构造与原代码逐字相同。单测覆盖 v1 回归(见 scripts/ 下测试运行
  记录,本文件下方)。

## 与 #49 O0 定义的唯一已知差异(如实列出)

- 无。O0 定义 = memB2;不引入新 run。
- memO2 与 memB2 的唯一 env 差:RPENT_MEMORY_TRIGGER=progress(其余逐项相同)。
- memO2 与冻结 C2 离线重放的唯一语义差异:cooldown 在线按 boundary 计数
  (离线按 turn 距离),is_error 规则在线可用(离线不可复现,未计入离线指标;
  在线它属于 progress 失败的子集,预期少量增火,分析时单列)。

## 单测记录(2026-09-18,python -m pytest 风格脚本内联运行)

- progress 模式:R3(2nd 连续失败 pick)、R2(短 move 无进展)、
  R5(release 未置谓词)、R1(segment found=false)各触发一次,reason 字符串
  与冻结规格一致;cooldown 2 boundary 内的排队火被丢弃;cap 6 生效;
  PROGRESSING move(final_dist 0.012)不火。
- v1 回归:同流下 3 连 move 触发 T4 "repeated_no_progress"(reason 命名含
  已知 bug,保持),pick success=false 触发 T1——v1 行为与 #49 一致。
