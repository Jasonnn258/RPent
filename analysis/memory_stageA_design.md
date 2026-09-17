# Stage A 设计(2026-09-17 修订版,依据 Q0 审计)

上游审计见 `memory_q0_audit.md`。核心修订:retrieval failure 不是单一 ranking 问题,拆三层。

## 三层失败模型

- **A. ACCESS**:路径/资源是否可访问(Q0-observed 实测:主路径 100% 断,卡片触达 16%)
- **B. TRIGGER**:决策时刻是否意识到要查 memory(Q0-observed 实测:决策时刻回查 = 0)
- **C. RANK**:发起查询后能否找到正确 memory(benchmark 要量化的部分)

## 五个查询条件(公平比较)

| 条件 | 定义 | 约束 |
|---|---|---|
| Q0-observed | 历史实际行为(错路径+即兴 browse) | **冻结,只作 audit 描述**,不参与算法比较(会把修路径+决策时检索+改排序混在一起) |
| Q0-fixed | 正确新路径 + 允许 decision-point 检索 + 仅原始 browse | 候选信息只许 MEMORY.md index line + list_dir 文件名,词面匹配;禁 embedding/reranker/结构化打分 |
| Q1-semantic | 同 Q0-fixed 访问与触发 | 语义相似度排序(title/body) |
| Q2-phase | phase 过滤 + 语义排序 | |
| Q3-structured | 语义 recall + 结构化 rerank | query:task/phase/last_action/symptom/observation_summary;memory 侧:title/kind/applies_when/symptom/How-to-apply。**禁** evidence.cells / future outcome / reward / hidden state |

## Decision point 双标注(#46)

每点标两问:① SHOULD_RETRIEVE = YES|NO|UNCERTAIN;② YES 时 gold_memory_ids。
schema:episode/task/seed/turn/phase/last_action/symptom/observation_summary/
should_retrieve/gold_memory_ids/why_retrieve/why_applicable/
expected_use(OBSERVE|RETREAT|RETRY|RECOVER|CONTINUE|OTHER)/source_type/is_source_episode
(+ 扩展字段:class/hard_negative_for/forward_outcome/auto_audit/audited)。

规模:**240 高质量点 = 120 YES + 120 NO**;UNCERTAIN 另存不进主评估。
YES 覆盖 grasp / place-contact / predicate-timing / perception / recovery。
**Hard negatives 必须有**:同表面关键词不同适用性(篮内→retreat 适用 vs 篮外→不适用)。

## Gold 标注流程

自动候选允许,最终 gold 不许纯字符串匹配。辅助源:global frontmatter、
task_only evidence、B2 verification events、failure analysis、transcript context。
evidence.cells 只用于 gold 审计,禁作在线特征。
每个 positive 四项确认:(1) memory 在该 step 前已存在(库为静态,成立);
(2) applies_when 与当前状态一致;(3) How to apply 对该决策有实际意义;
(4) Falsify 条件未成立。**同 episode 的后续物理结果允许用于标注审计**
(这是 labeling,不是在线特征),用于区分"对象最终在目标处"(retreat 卡适用)
vs "对象明显脱靶"(retreat 卡不适用 → hard negative)。

## 评估顺序与指标

**先 Trigger**(新核心):Retrieval Trigger Recall(需要 memory 的点中系统发起
检索的比例)/ Trigger Precision / Unnecessary Retrieval Rate(NO 点却触发)。
Q0-observed 的 decision-time trigger recall 由日志脚本正式计算(预期 ≈0)。

**再 Ranking**(仅 SHOULD_RETRIEVE=YES 上,Q0-fixed vs Q1/Q2/Q3):
Recall@1/@3/@5、MRR、irrelevant@3、applicable@1/@3、latency。
**必须区分 candidate recall failure(gold 没进候选集)vs ranking failure
(进了候选但没排前)。**

## 双 funnel(分开报告,不合并)

1. access funnel(已测):旧路径访问 → index → suite → global
2. retrieval funnel(待测):decision point → need memory? → triggered? →
   gold in candidate set? → gold in Top-3? → gold in Top-1?

## 结论格式

A. ACCESS(路径故障率、真实 reach rate)
B. TRIGGER(recall/precision/unnecessary)
C. RANK(四条件指标表)
D. FAILURE BREAKDOWN:ACCESS_FAIL / TRIGGER_FAIL / CANDIDATE_FAIL / RANK_FAIL / CORRECT_RETRIEVAL
最终判定:ACCESS / TRIGGER / RANKING / MULTIPLE BOTTLENECKS。
不把"修了一个错误路径"包装成算法贡献。

## 纪律

Stage A 完成前不做:controller 强执行、executable memory、online R0-R3、
修改 B2、修改 Global Memory、训练 retriever。先回答三个数字:
① 决策时刻是否知道要查?② 决定查后能否找对?③ 找不到主要死在 candidate 还是 rerank?
