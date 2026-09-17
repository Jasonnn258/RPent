# Q0 审计 — 当前系统的 memory 实际使用方式(2026-09-17)

Stage A 前置审计。纪律要求:baseline 按代码与日志实测定义,不凭印象。
以下全部结论有日志证据,样本 = B 系 armA 全部 251 集(logs/ovpm_exp/*armA*/run.log)
+ 8 月探索期老日志抽验。

## 当前系统的三条 memory 通道

### 通道 1:prompt 强制的库浏览(主通道,路径是断的)

- system prompt WORKFLOW 第一步(user BEGIN 同样要求)强制先读
  `resources/libero/memory/MEMORY.md`,并 `list_dir`/`grep` 搜索
  `resources/libero/memory/` 下的叶子。
- **该目录在本地不存在**。HF 数据集 RLinf/RPent-memory 同步下来的是分层结构
  `resources/libero/{MEMORY.md, global/, suite/, task_only/}`,与 prompt 指向的
  旧版 `memory/` 布局代际错位。`results_*_pert/` 同样不存在。

### 通道 2:SM1 PhaseTracker 每轮注入(armA/B1/B2 共有,RPENT_STRUCTURED_MEMORY=1)

- harness 从工具流确定性推导 phase(P_init→P_look→P_transport→P_grasp→P_place→P_verify),
  每轮注入 phase 提示 + 失败循环规则(`analysis/structured_rules_v1.json`,
  3 个 phase 块,规则来自旧失败分析,不是 61 张策略卡)。
- prompt 告诉 planner 需要细节时读 `resources/libero/memory/rules/<PHASE>.json`
  ——同样不存在;但注入由 harness 完成,planner 不必读文件。
- 这是唯一在决策时刻生效的通道,但内容是循环检测/恢复规则,
  **61 张 global 策略卡不经过这条通道**。

### 通道 3:PROVEN_LEVERS 硬编码蒸馏块

- system prompt 里固定的 "PROVEN LEVERS & LESSONS(libero_10_task 9/10)",
  永远在场,无检索过程。

## 通道 1 的真实检索漏斗(251 个 armA 集,日志实测)

| 步骤 | 集数 | 占比 |
|---|---|---|
| 尝试读 `resources/libero/memory/MEMORY.md`(必做步骤) | 250/251 | 99.6% |
| → 得到 `file not found` | 250 | 100%(尝试者全部失败) |
| 事后 `list_dir resources/libero` 自行发现真实布局 | 236 | 94% |
| 读到真实索引 `resources/libero/MEMORY.md` | 74 | 29% |
| 读到 ≥1 张 `suite/` 任务页 | 74 | 29% |
| 读到 ≥1 张 `global/` 策略卡 | **39** | **16%** |
| 读到 `task_only/` | 3 | 1% |
| 读过 guides(strict/pro hybrid) | 161 | 64% |

## 时机:检索只发生在开局,决策时刻为零

抽样 6 个读过 global 卡的集:最后一次 memory 读取的日志行号 55–84,
第一次 pi0_pick 在 105–187 行 —— **所有 memory 读取都在第一个动作之前**,
episode 中途(release 后谓词未触发、pick 报失败等真正需要经验的时刻)
没有任何一次回查。上下文里剩下的只有 planner 开局读过并记住的内容。

## Q0 baseline 的可执行定义(供 benchmark 复现)

Q0 = 通道 1 的忠实复现:给定 decision point 的上下文,模拟 planner 的
即兴浏览行为 —— 从 MEMORY.md 索引行(标题 + 一句话 blurb)+ list_dir 文件名
中按关键词/对象名挑选要读的文件,不做语义排序、不用结构化字段。
实现时以"索引行 + 文件名的词面匹配"为准(这正是 planner 实际能看到的全部信息)。

## 对研究问题的直接影响

- RQ1("正确经验存在但没被检索到")在**路径层已是 100% 故障**(必做步骤必失败);
  在**卡片层**,84% 的集从未读过任何 global 卡,且 0% 在决策时刻检索。
  benchmark 要量化的是:即使把路径修好、在决策时刻发起检索,排序质量还差多少。
- Q0 的 Recall 上限天然受"索引行词面匹配"约束 —— 这正是 Q1/Q2/Q3 要对比的基线。

## Stage A-1 数据源清单(decision points 抽取)

1. `analysis/b2_verification_events.jsonl`(1341 条:turn/tool/verdict/pending)
   —— B 系决策时刻的主源,phase 可由 transcript 重放重建
   (scripts/build_b2_analysis.py 已有重建机制)
2. ovpm_exp 各集 `transcript_*_s*.json` + `run.log` —— 逐轮工具流、
   memory 读取尝试及其失败、8 月老日志(logs/2026081*)同构可用
3. `resources/libero/task_only/*.json`(75 个)—— 上游探索期的
   memory_files_read / strategy_notes / 扰动任务语言
4. `analysis/b2_runs.csv` / `b2_pairs.csv` / `b2_failure_analysis.md` ——
   失败集分类(quiet/verifier-active)
5. global 卡 `evidence.cells` → task_only 素材映射(仅用于 gold 标注审计,
   不作在线特征,符合规格)
