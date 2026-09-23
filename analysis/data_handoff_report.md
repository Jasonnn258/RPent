# Data Handoff — 最终报告(data_handoff_report.md)

_2026-09-23。本轮唯一目标:G0.5/G0.6 最终数据 + 原始轨迹 → 可追溯、可复现、
适合逐轨迹分析的数据包。零重跑、零结果改写、零历史修改。_

## 十六问

**1. branch 是否成功 push?**
是。`research/pre-ovpm-20260905` 首次推上 GitHub(此前远端只有 main),
普通 push,无 force。

**2. remote branch URL / name?**
`https://github.com/Jasonnn258/RPent/tree/research/pre-ovpm-20260905`

**3. final HEAD SHA?**
push 时点:`afb7a89be4036bd18ced58192966af4bbd5aff65`(ls-remote 核对一致)。
本 handoff 文档批次 commit 后前移一格,以 `git log -1` 为准。

**4. outcome_validation_runs.csv 是否 commit?**
是,`afb7a89`(仅该文件,+63 行 = 429 手术后重跑补齐的最终格)。
终态 1019 行:G0.6 网格 180 格 = 60/60/60,零全键重复,零 infra 残留。

**5. bundle 中 final episodes 数量?**
**180**(每 (task, seed, arm) 唯一 is_final episode)。

**6. P0/P2/P4 各多少?**
60 / 60 / 60。

**7. t3/t5/t9 各多少?**
60 / 60 / 60(source_stage 亦三等分:G0=60 / G05=60 / G06_extension=60 —— 
P4 的 s1-s10 源自 G0 的 g0D,如实标注,未重复存储)。

**8. complete matched triplets?**
**60/60** —— 每个 (task, seed) 的 P0/P2/P4 三臂齐全,零缺口。

**9. missing raw logs?**
0(180/180 目录存在且复制了文件,files_copied 均 > 0)。

**10. mismatch 数?**
**0**(三方:master CSV × stageG06_runs.csv × states.json 同口径 raw 重判,
180/180 一致)。附:12 个 success 格 planner 无显式 FINISH 行 —— env 已判
完成、收尾 API 调用随后挂起(3600s 型),按调度器口径属合法 success,
已单列说明,未做任何静默修改(data_handoff_mismatch_report.md)。

**11. unresolved infra?**
0。最终 180 格无任何 429/配额/0-turn/网络超时被误记为 policy_fail;
raw 重判也未发现 states.json 缺失或 timeout-未终止型残留。

**12. bundle size?**
解包 43M(1970 个文本文件)/ 压缩包 **3.2M**(zstd -19)。

**13. SHA256?**
`2fe63fa041688d3207668a48d1973062be31d003d36123cdc6b2ab1c4940974a`

**14. 可用的 high-value 轨迹字段(全部已有原始证据,非新算)?**
- `states.json`(逐 primitive 步):robot0_eef_pos/quat、gripper_qpos、
  object_names、command+result(pick success / peak_lift_m /
  min_gripper_opening / descent_done / libero_terminated)—— EEF/物体/
  抓取/持物/容器判定证据全在;
- `memory_events.jsonl`(逐触发):turn/phase/symptom(含
  repeated_no_progress 计数)/trigger_reason/retrieval_method/
  retrieval_latency_ms/ranked_memory_ids/top1/top3/scores/retrieval_tokens/
  planner_followed_top1/verification_result —— 逐 decision-point 与
  recovery event 的主数据源;
- `run.log`:全量时间戳日志(planner think/tool 调用逐 turn、usage
  in/out/tool_calls)—— planner 调用次数与 token 数直接可得,
  per-call latency 可由相邻时间戳差复原;
- `transcript_*.json`:planner 完整输入输出(注入块原文在内);
- `structured_metrics.json`:phase_sequence、fired_rules+触发 turn、
  injections/recovery 汇总;`recipe_*.jsonl`:实际发出的感知 prompts;
- `metadata/stageG06_events.jsonl`(366 事件):跨 episode 统一口径的
  触发/注入事件流,与冻结分析的 recovery@3 定义直接对齐。

**15. 完全不存在的字段?**
- 视频/图像帧本身及其衍生观测(已排除,~16G);
- progress residual 标量(未作为独立字段落盘;progress 信息以
  phase/verification_result/symptom 形式存在);
- embedding/相似度缓存。
按规格未为补齐任何字段新跑模型或模拟器。

**16. 刻意排除的大文件?**
episode.mp4、action_videos/、images*/、depths*/、world*/、segments/
(每集约 90M 媒体);模型权重/checkpoints;conda 环境;Python/嵌入缓存;
G0.5/G0.6 之外的历史阶段 raw logs;完整历史 rpent-logs archive。
原始媒体仍在服务器 `logs/ovpm_exp/` 原目录,按 manifest.source_path 可回取。

## 产物

| 产物 | 位置 |
|---|---|
| 压缩包 | `/workspace/yjx/downloads/g05_g06_trajectory_bundle.tar.zst`(3.2M) |
| 解包目录 | `/workspace/yjx/downloads/g05_g06_trajectory_bundle/`(43M) |
| git 审计 | `analysis/data_handoff_git_audit.md` |
| 分析层索引(35 项) | `analysis/data_handoff_analysis_index.md` |
| 一致性报告 | `analysis/data_handoff_mismatch_report.md` |
| 构建脚本(可幂等重建) | `scripts/build_g05g06_bundle.py` |

## 完整性与安全

- 凭据扫描:全包 0 个 .env/credential 文件;模式命中 7 个唯一串全为
  误报("task-language" 类连字符词片段 × 7 变体 + git SHA × 2),
  **无任何 API key / token / secret**;
- 零删除:服务器原始日志(含 314 个尝试目录)原样保留;
- 零 force push、零历史改写、raw logs 未进 git。

## §20 STOP

handoff 完成,停在此处。不开始新的轨迹分析、不生成 failure taxonomy、
不动 Memory/Graph/Trigger。后续分析入口:bundle `manifest.csv` 任意行 →
`bundle_path` 逐轨迹 → `memory_events.jsonl` 逐 decision-point →
`metadata/stageG06_events.jsonl` 跨集对齐。
