# Stage E2 结果报告:Failure-Origin Retrieval(2026-09-20)

一句话结论:**失败溯源本身是可在线可靠识别的(origin accuracy 90.4%,
17/17 perception 案例的 surface=GRASP/origin=PERCEPTION 结构被独立标注确认),
但把它写进检索 query 在冻结词面检索器下不改善任何指标——E3 perception 仍
0/17(gold 卡词面交集为空),non-perception 反跌 6.8pp(origin 证据词把
grasp 卡挤进 predicate 时刻的 Top-3)。判定 FAILURE ORIGIN: NOT
SUPPORTED,按协议 STOP,不跑在线、不 patch perception retrieval。**

## 0. 设计回顾(预注册,零事后自由度)

134 个 C1 冻结决策点、原始 Memory、冻结词面打分、候选集不变;四臂唯一
变量 = query 尾部(E0 贫 / E1 富 / E2 原始轨迹 / E3 溯源块)。E3 块由
确定性提取器生成(`scripts/stageE_origin.py`):SURFACE(决策动作家族)/
ORIGIN(窗口内最上游未满足家族,主证据 = B2 verifier 的固定 5 短语
missing_evidence)/ MISSING(家族前置条件名)/ EVIDENCE(逐字运行时观测)。
模板在观测词汇普查后、任何检索打分之前冻结(纪律声明见模块 docstring)。

回归锚:**E0 逐位复现 C1/D0,E1 逐位复现 C1/D1(R@1/R@3/R@5/MRR/irr@3
全对上)PASS。**

## 1. 主表(primary 120 gold 点)

| 臂 | query 尾部 | R@1 | R@3 | R@5 | MRR | irr@3 | perception17 | 均长 |
|---|---|---|---|---|---|---|---|---|
| E0_POOR | 冻结贫 query | .233 | .575 | .592 | .418 | .425 | 0/17 | 248 |
| E1_CURRENT_STATE | 冻结富 query | .275 | **.592** | .608 | .458 | .408 | 0/17 | 475 |
| E2_RAW_TRACE | 原始关键事件 | .150 | .542 | .600 | .337 | .458 | 0/17 | 492 |
| E3_FAILURE_ORIGIN | 溯源块 | .067 | .517 | .633 | .325 | .483 | **0/17** | 378 |

按类 R@3(E0→E3):pick_verify .944→.972、predicate_timing .967→**.600**、
recovery .200→.300、grasp 0→0、perception 0→0。
按 failure origin(E3):GRASP(n=68) .647、PLACE(n=21) .857、
PERCEPTION(n=22) **.000**、UNKNOWN/NONE .000。

## 2. 六门槛判定

| # | 门槛 | 实测 | 判 |
|---|---|---|---|
| 1 | E3 perception R@3 ≥ 8/17 | **0/17** | ❌ |
| 2 | E3 overall R@3 > E1 +5pp | .517 vs .592(−7.5pp) | ❌ |
| 3 | E3 > E2(+5pp 或 perception +3) | −2.5pp / +0 | ❌ |
| 4 | non-perception 降 ≤3pp(vs E0) | .670→.602(−6.8pp) | ❌ |
| 5 | hardneg irr@3 恶化 ≤5pp | 1.0→1.0(已饱和;retreat 14→11) | ✅(名义) |
| 6 | audit 非 UNKNOWN origin acc ≥80% | 47/52 = **.904** | ✅ |

**门控结论:1-4 FAIL → FAILURE ORIGIN: NOT SUPPORTED → STOP
(协议原文:不跑在线、不 patch perception retrieval、Memory Study 以
Progress Trigger 为主要正结论)。**

## 3. 机制(机制日志 `stageE_retrieval_mechanism.jsonl`,480 gold 行)

- **perception 的墙与 Stage D 完全相同,只是换了位置**:E3 尾部携带的
  全部词汇(SURFACE=GRASP; ORIGIN=PERCEPTION; MISSING=
  VALID_TARGET_LOCALIZATION; EVIDENCE="observation produced no usable
  object position" 等)与 gold 卡 `point-prompt-after-text-misground`
  索引行(point/prompt/text/masks/instance/wrong/duplicate…)的**词面
  交集为空——17/17 行 matched_terms = ∅**。运行时观测通道(b2 短语、
  回执字段)根本不产生卡索引行的区分性词汇;溯源信息"说对了事,说的
  不是检索器听得懂的话"。
- **origin 词汇在错误方向上有区分度**:predicate_timing 12 个 E0 命中
  行被**同一批三张卡**(visual-over-pick-heuristic、
  pi0-pick-carries-past-lift-judge-by-grip、near-goal-contact-regrasp)
  全部挤出 Top-3——E3 证据词(gripper/object/target)给这些 grasp 味
  卡 4+ 词重叠,反超 gold 原有的 {false, libero, terminated} 3 词。
  即:溯源块把"错在哪一族"的信息给了打分器,而打分器用它把**同族**
  的错误卡推得更靠前。
- **E2_RAW_TRACE 也不救命**(.542 < E0 .575):多给原始历史本身是
  轻微负贡献;E3≈E2(−2.5pp)说明"压缩解释"相对"原始罗列"无增益。
  与 C1(query 富化 +1.7pp)、D(卡侧别名 −30pp)、E1(BM25 +1.7pp)
  拼成完整证据链:**瓶颈从来不是信息量,是冻结词面通道的表达力**。

## 4. 审计集结果(详见 `stageE_origin_audit.md`)

64 行(17 perception 全收 + 分层 37 + hardneg 10),防循环流程
(工作表只含可观测量,gold 先标完再 join)。origin accuracy
47/52 = .904,surface 52/52,missing 44/52,UNKNOWN 2/54。
hardneg 10/10 被赋予非 NONE origin(b2 验证短语在健康时刻同样未决),
其检索后果由门槛 5 裁定(名义 PASS,any_top3 全臂饱和 14/14)。

## 5. 十问作答(离线部分)

1. **D 崩塌多少是 common-token weighting?** 不是主因(E1:S3 仅 +1.7pp,
   perception 全臂 0/17);主要死因是表示。
2. **BM25 能救 aliases 吗?** 不能(S3 .292 vs S0 .575);对原始 Memory
   温和无害(S2 +0.8pp)。
3. **surface 与 origin 多经常不同?** 134 点中 105(78%):GRASP 表面下
   藏着 24 个 PERCEPTION origin、44 个 PREDICATE 表面下 25 GRASP/17 PLACE。
4. **17 perception 中 surface≠PERCEPTION 但 origin=PERCEPTION?** 
   **17/17**(全部 surface=GRASP)。
5. **Failure Origin 能被在线信息可靠识别吗?** **能**(audit .904;
   b2 的 5 短语词汇表 + 原语返回足够,无需特权信息)。
6. **四条件 R@3?** .575 / .592 / .542 / .517(见主表)。
7. **failure-origin 优于直接塞历史吗?** **否**(E3≤E2,均≤E0)。
8. **perception 0/17 最终?** 仍是 **0/17**——query 侧(贫/富/历史/溯源)、
   卡侧(原样/别名)、打分(raw/BM25/TF-IDF)三个轴上的全部处理都已
   试尽,词面交集为空是结构性死因。
9. **hard negative 被破坏了吗?** 没有(any_top3 饱和 14/14;
   retreat 14→11)。
10. **值得上线吗?** 否——离线全败,按协议不跑在线。

## 6. 最终判定

**FAILURE ORIGIN: NOT SUPPORTED**
**ONLINE: NOT RUN(协议 STOP)**

研究问题的答案:长程执行中的 Memory retrieval key 应该是 failure
surface 还是 failure provenance?——**provenance 是可观测的(90%
可判),但在这套冻结词面检索器里,它既不可寻址(perception gold 词面
交集为空)又有副作用(同族错误卡被推高 −6.8pp)。要使用 provenance,
必须换掉检索通道本身(语义向量/结构化字段匹配),而这在本研究的冻结
清单内。** Memory Study 的主要正结论维持 Stage C:检索瓶颈在触发时机
(Progress-Gated Retrieval),不在 query 构造。

## 7. 诚实声明

- 模板冻结纪律:提取器与两个模板的全部迭代发生在任何检索打分之前;
  唯一一次模板前的诊断窥视(8 行 perception query 与 gold 卡的词面交集
  检查)促成了"证据必须逐字"的原则落地,已在此披露。
- E3 在线对照(30 集)未运行:协议规定门槛不过即停,非资源原因。
- origin=UNKNOWN 的 5 行(recovery 首事件、窗口空)在 E3 中 query
  仅含 SURFACE/UNKNOWN,未参与任何"猜"。

产物:`scripts/stageE_origin.py`、`scripts/stageE_origin_dump.py`、
`scripts/memory_stageE2_benchmark.py`、
`analysis/stageE_origin_dump.jsonl`(134 点提取器输出)、
`analysis/stageE_audit_worksheet.jsonl`、`analysis/stageE_origin_gold.jsonl`、
`analysis/stageE_origin_audit.md`、`analysis/stageE_retrieval_results.json`、
`analysis/stageE_retrieval_mechanism.jsonl`。
