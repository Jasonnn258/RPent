# Stage A 结果 — Memory 检索三层瓶颈离线测评(2026-09-17)

数据:`memory_retrieval_queries.jsonl`(120 YES / 120 NO / 40 UNCERTAIN,
见 `memory_retrieval_queries_audit.md`);脚本:`scripts/memory_stagea_benchmark.py`;
数字:`memory_stageA_results.json`。语义向量:本地 bge-small-en-v1.5
(远程 embedding API 无余额,改本地,可复现)。

## 总判定:**MULTIPLE BOTTLENECKS(三层都坏,权重不同)**

- **A. ACCESS(路径)**:prompt 强制的 memory 路径 100% 断裂(250/251 集必做步骤
  file-not-found);94% 靠事后 list_dir 自救,但只有 29% 读到索引、16% 读到任何
  global 卡、1% task_only。(Q0 审计实测,armA 251 集)
- **B. TRIGGER(决策时刻)**:**decision-time trigger recall = 0/120(0.0%),
  slack±3 turn 仍为 0**。全部 memory 读取发生在开局浏览阶段(turn 0–15,
  102/102 集最后一次读取都早于第一个动作),episode 中途任何决策点都没有回查。
  Unnecessary rate 也是 0 —— 不是"查错时机",是"根本没有决策时检索这个行为"。
- **C. RANK(排序)**:把 ACCESS 和 TRIGGER 都人为修好之后(counterfactual
  条件),最好条件 Q3-structured 的 Recall@3 也只有 **0.592** —— 仍有 40% 的
  "正确经验在场却没排进前三"。

## RANK 层四条件对比(120 YES 点)

| 条件 | R@1 | R@3 | R@5 | MRR | irr@3 | cand_fail | rank_fail | HN违规@3 |
|---|---|---|---|---|---|---|---|---|
| Q0-fixed(索引行词面) | 0.000 | 0.400 | 0.700 | 0.244 | 0.597 | 0.000 | 0.300 | 1.00 |
| Q1-semantic | 0.308 | 0.458 | 0.567 | 0.383 | 0.733 | 0.000 | 0.433 | 0.00 |
| Q2-phase | 0.308 | 0.525 | 0.725 | 0.437 | 0.692 | 0.150 | 0.125 | 0.21 |
| **Q3-structured** | **0.475** | **0.592** | **0.775** | **0.552** | 0.781 | 0.142 | 0.083 | 1.00 |

候选集定义:Q0-fixed/Q1 = 全部 61 卡(名字/语义可见即候选);Q2 = phase 过滤后;
Q3 = 语义 top-20。candidate_fail = gold 没进候选集;rank_fail = 进了候选没进 top-5。
延迟均 <2ms/查询(离线打分,无意义量,记录备查)。

### 分类别 Recall@3(失败模式互补,这是最有信息量的一张表)

| 类 | Q0-fixed | Q1 | Q2 | Q3 |
|---|---|---|---|---|
| predicate_timing(30) | **30/30** | 9/30 | 18/30 | **30/30** |
| pick_verify(36) | 0/36 | **36/36** | 35/36 | 14/36 |
| grasp(7) | 0/7 | 0/7 | 0/7 | **7/7** |
| recovery(30) | 18/30 | 10/30 | 10/30 | 20/30 |
| perception(17) | 0/17 | 0/17 | 0/17 | **0/17** |

- 词面匹配(Q0-fixed)在"关键词显式出现"的类(predicate 卡的索引行就写着
  release/predicate)上满分,在词面完全不同的类上归零。
- 纯语义(Q1)反向:pick 类满分、predicate 类塌掉 —— 嵌入把"release 未验证"
  语义上拉近了"确认是否夹住"的卡。
- **perception 类在全部四个条件下都是 0**:决策点症状("observation produced
  no usable object position",发生在 pi0_pick UNCERTAIN 时刻)与 pick_verify
  表面不可区分,四条件都返回 grasp/verify 卡。**缺失的信号是"哪个通道失败"
  (感知 grounding vs 抓取执行),不是表面症状** —— 这是排序层之外的结构性
  标注问题,也是 Stage B 在线实验里 perception 类的预期短板。
- grasp 7/7 只在 Q3 出现:last_action 项(pi0_pick→卡文中的 pick)起的作用,
  即结构化字段对齐才能把"抓取失败→重抓卡"连起来。

### hard negative(14 个"表面像该查、其实不该查 retreat 卡"的点)

Q1 违规 0.0 是假象(它根本排不到 predicate 卡);Q0-fixed 与 Q3 违规 1.0:
release+未验证 的症状必然把 retreat 卡拉进前三。Q3 实际 top1 是
near-target-repick / near-goal-contact-regrasp(对"物体没放好"是对的建议),
禁排卡多在第 3 —— 严格口径记违规,宽松口径(top1)不违规。要真正区分
"retreat 就能确认" vs "物体没到位需要重抓",靠的是物理状态(物体位置),
不在当前 query schema 的有效信号里 —— 与 perception 类同一个根因。

## 双 funnel(分开报,不合并)

**Access funnel(Q0-observed,armA 251 集)**:prompt 必做读取 250 → file-not-found
250(100%)→ list_dir 自救 94% → 读到索引 29% → 读到 ≥1 global 卡 16% → task_only 1%。

**Retrieval funnel(120 YES 点)**:
- Q0-observed:需要 120 → 决策时触发 **0** → 后续全 0。
- Q3-structured:需要 120 → 触发 120(条件设计即为决策点检索)→ gold 进候选
  103(0.858)→ 进 top3 71(0.592)→ top1 57(0.475)。

## FAILURE BREAKDOWN(规格口径)

| 层 | Q0-observed | Q0-fixed | Q1 | Q2 | Q3 |
|---|---|---|---|---|---|
| ACCESS_FAIL | 1.00(必做路径) | 0(修) | 0 | 0 | 0 |
| TRIGGER_FAIL | 1.00 | 0(允许决策点检索) | 0 | 0 | 0 |
| CANDIDATE_FAIL | — | 0 | 0 | 0.15 | 0.142 |
| RANK_FAIL | — | 0.30 | 0.433 | 0.125 | 0.083 |
| CORRECT(top3) | 0 | 0.40 | 0.458 | 0.525 | 0.592 |

## 对三个研究问题的回答

- **RQ1**(正确经验存在但没被检索):当前系统的主因不在排序,在 **ACCESS(100%
  路径断裂)+ TRIGGER(0% 决策时检索)**。这两层修好前,排序质量根本没被用到。
- **RQ2**(检索到但 Planner 不执行):离线 benchmark 测不到,留给 Stage B
  (B2 已有先导数字:裁决正确但服从率 dev 49% / new tasks 39%)。
- **RQ3**(同时改进检索+执行是否稳定改善):Stage A 给出上界信号 —— 检索侧
  Q3 比 Q0-fixed Recall@3 高 19pp(0.592 vs 0.400)、MRR 翻倍,值得进 Stage B;
  但 perception 类 0/17 与 hard negative 严格违规 1.0 说明纯症状驱动检索有
  结构性盲区,Stage B 设计要带这两个已知短板。

## 纪律自查

- 未修改 Global Memory 内容、未改 B2、未训练 retriever、未用 evidence.cells /
  最终结局 / hidden state 作在线特征(forward outcome 只出现在标注字段)。
- Q0-observed 冻结,只作 audit 描述,未与 Q3 比较"提升"。
- 局限:单 suite(spatial_task 碗→盘子);gold 为策划规则映射 + 规则审计
  (非人工逐点);语义向量 bge-small(CPU 本地)。
