# Stage E1 结果报告:Discriminative Lexical Scoring(2026-09-20)

一句话结论:**换 BM25/IDF 救不回 Stage D 的 alias 崩塌(S3 R@3 .292 vs 原
.575,只捞回 +1.7pp),perception 在全部五个打分器下都是 0/17——D 的失败
主要不是"词权重没归一化",是 alias 表示本身不携带区分度。
SCORING DIAGNOSIS: COMMON-TOKEN COLLISION NOT CONFIRMED
(准确说:collision 存在且被 IDF 证实,但不是主要死因)。**

## 0. 设计回顾

数据完全冻结复用 Stage D(134 决策点、冻结 gold、原始 Memory、冻结 468
aliases、14 硬负例)。五臂:S0/S1 = 原词面重叠打分(必须逐位复现 D0/D2,
**回归锚 PASS**);S2/S3 = 标准 BM25(k1=1.5, b=0.75,idf=ln(1+(N-df+.5)/
(df+.5)),tokenizer 沿用冻结 `toks()`,文档=原词面打分所见的同一文本);
S4 = cosine TF-IDF(辅助)。

## 1. 主表(primary 120 gold 点)

| 臂 | 文档 | 打分 | R@1 | R@3 | R@5 | MRR | irr@3 | perc17 | hardneg any |
|---|---|---|---|---|---|---|---|---|---|
| S0_ORIGINAL_RAW | 原 | raw | .233 | .575 | .592 | .418 | .425 | 0/17 | 14/14 |
| S1_ALIAS_RAW | +alias | raw | .083 | .275 | .442 | .268 | .725 | 0/17 | 14/14 |
| S2_ORIGINAL_BM25 | 原 | BM25 | .233 | .583 | .633 | .435 | .417 | 0/17 | 14/14 |
| S3_ALIAS_BM25 | +alias | BM25 | .125 | **.292** | .408 | .284 | .708 | 0/17 | 14/14 |
| S4_ALIAS_TFIDF | +alias | TF-IDF | .042 | .333 | .492 | .235 | .667 | 0/17 | 14/14 |

按类 R@3(S3):pick_verify 仍 **0**(S0 .944)、predicate 1.0、recovery
.167、grasp 0、perception 0。gold-mean-rank:S3 10.2(与 S2 持平)但
top-negative−gold margin 从 S2 的 3.6 涨到 **6.2**——BM25 把分数差距拉开
了,赢的仍是非 gold 卡。

## 2. Collision 词的量化(十问 Q1/Q2 的直接答案)

alias 语料中,Stage D 制造碰撞的词在 BM25/IDF 下被压到**稀有词
(df≤5)中位权重 idf=3.72 的 8%~53%**:

| token | df 原→alias | idf | 相对稀有词权重 |
|---|---|---|---|
| object | 41→46 | .288 | .077 |
| gripper | 13→39 | .451 | .121 |
| pick | 10→33 | .616 | .165 |
| pi0 | 15→28 | .777 | .209 |
| wrist/target | 9/16→28 | .777 | .209 |
| release/held/false/rim | 7-13→25 | .888 | .239 |
| grasp | 13→23 | .970 | .261 |
| predicate/opening | 15/3→20 | 1.107 | .297 |
| basket | 10→19 | 1.157 | .311 |
| bowl/plate | 5/1→16 | 1.324 | .356 |
| success | 2→13 | 1.524 | .410 |
| move | 3→8 | 1.987 | .534 |

即:IDF 机制本身工作正常(通用词被压 3-12 倍),S3−S1 = +1.7pp R@3 就是
"权重修正"能贡献的全部。

## 3. 判定与解读

- **S3(=S0−3pp 以内)不成立**:.292 vs .575,差 28pp → 判定
  **SCORING FIX NOT SUFFICIENT**(硬负例倒是安全:14/14 不变)。
- 机制解读:BM25 同时做了两件事——压通用词权重、也按文档长度/词频给
  alias 大文档重新计分。前者有利于 gold,后者无助于"gold 没有区分性词"
  这一根本问题。perception 0/17 在 S2/S3/S4 全部复现:**无论怎么加权,
  查询与 gold perception 卡之间就不存在可区分的共同词**——与 Stage D
  机制结论(可观测词汇是域通用语)互相印证,且现在有了独立打分族证据。
- 附带:S2_ORIGINAL_BM25 vs S0:R@3 +0.8pp、MRR +1.7pp、R@5 +4.1pp、
  硬负例 retreat 14→12——BM25 对**原始** Memory 是温和无害的小改良,
  但 perception/grasp/recovery 不动。冻结词面检索的瓶颈不在打分公式。

## 4. 对后续的指引

E1 是机制诊断,不触发任何在线动作(协议规定)。它把 Stage D 的死因
从"可能是打分问题"收紧为"表示问题":查询侧无论贫富(E0/E1)、卡侧无论
原样还是加别名(D)、打分无论 raw 还是 BM25/TF-IDF(E1),perception
0/17 纹丝不动。剩下唯一未检验的查询侧自由度 = **查询的结构化历史信息**
(失败溯源),即 Stage E2 的对象。

产物:`scripts/memory_stageE1_scoring.py`、
`analysis/stageE_scoring_results.json`(逐臂指标+逐 token df/idf)。
