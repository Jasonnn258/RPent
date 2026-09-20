# Stage D 结果报告:Retrieval-Aligned Memory Representation(2026-09-20)

一句话结论:**给 Memory 卡补充"运行时可观测词汇"的检索别名,确实在词面上
把卡和在线查询连起来了(339/350 个 gold 对产生了新共同词),但在冻结的
词面检索下这些新连接几乎不携带区分度——可观测词汇是"整个域的通用语",
不是"这张卡的身份证"。离线门槛四条全挂,按预注册协议判定
CARD-SIDE ALIGNMENT: NOT SUPPORTED,不跑机器人,不回补 alias。**

## 0. 背景与设计(一段话)

A→B1→C 证明检索瓶颈在触发时机而非 query 丰富度,但 perception 类检索
0/17 始终不动,机制是 query 侧状态词与 61 卡索引词表不相交。Stage D 检验
最后一个自由度:卡侧。做法:从每张卡**自有**的证据材料(frontmatter
symptom、evidence.cells 对应的 task_only 原始记录、recipe 命令流)确定性
抽取 ≤8 条可溯源的 runtime-observable 检索别名(sidecar
`analysis/retrieval_aliases_v1.json`,61/61 卡、468 条、audit
`stageD_alias_audit.md` 通过后冻结),只进检索打分、不进 Planner 可见
内容;在 C1 冻结的 134 个决策点上做五臂对照(D0 原样 / D1 富 query /
D2 原卡+别名 / D3 富 query+别名 / D_SHAM 打乱别名对照长度效应)。

## 1. 主表:五臂离线结果(primary 120 gold 点,词面检索 R@k)

| 臂 | query | 卡侧 | R@1 | R@3 | R@5 | MRR | irr@3 | perception17 |
|---|---|---|---|---|---|---|---|---|
| D0_ORIGINAL | 贫 | 原 | .233 | .575 | .592 | .418 | .425 | 0/17 |
| D1_QUERY_RICH | 富 | 原 | .275 | .592 | .608 | .458 | .408 | 0/17 |
| D2_CARD_ALIGNED | 贫 | +alias | .083 | **.275** | .442 | .268 | .725 | **0/17** |
| D3_BOTH | 富 | +alias | .125 | .392 | .483 | .277 | .608 | 0/17 |
| D_SHAM | 贫 | +打乱alias | .050 | .242 | .358 | .202 | .758 | 0/17 |

回归锚:D0/D1 **逐位复现** C1 发布数字(R@1/R@3/R@5/MRR/irr@3、五类
R@3、hardneg retreat 14/14 全对上)——实现与 C1 同构,结果可信。

按类 R@3(D0→D2):pick_verify .944→**0**、predicate_timing .967→1.0、
recovery .2→.1、grasp 0→0、perception 0→0。

## 2. 预注册门槛判定

| # | 门槛 | 实测 | 判 |
|---|---|---|---|
| 1 | D2 perception R@3 ≥ 8/17 | **0/17** | ❌ |
| 2 | 非 perception R@3 降幅 ≤3pp | .67→.32(**−35pp**) | ❌ |
| 3 | hardneg 噪声恶化 ≤5pp | any_top3 14/14→14/14(已饱和;retreat 14→14) | ✅(名义) |
| 4 | D2 明显优于 D_SHAM | perception 0=0;MRR .268 vs .202(R@3 .275 vs .242) | ❌ |

**门控结论:不过 → STOP,不跑 D2 online,不人工补 alias**(协议原文)。

## 3. 机制:为什么"连上了却没用"(机制日志 1050 行,
`memory_staged_mechanism.jsonl`)

perception 17 点的 gold 全是同一张卡 `point-prompt-after-text-misground`
(文本提示选错实例后改用点提示)。逐点看:

- **新词汇连接真实存在**:17/17 点 gold 卡 overlap 0→2,匹配词
  `black/bowl`(来自卡 evidence 里记录的 rejected_segment_prompts
  "text prompt … the patterned black bowl … selected the right
  distractor");全量 350 gold 行中 339 行 overlap 增加。
- **但连接不区分卡**:查询词 `black bowl` 同时命中 ~55 张卡(很多卡的
  evidence 引用了同套任务指令或含同类名词),gold 以 2 分并列第 52 名;
  Top-3 被 `predicate-gated-by-eef-proximity-retreat-clear`(其 alias
  `libero terminated false`、`gripper opening 0.078` 恰好匹配查询的
  result 字段)这类**泛化状态词卡**占据。
- **噪声注入量级**:119/120 个 gold 点的 Top-3 出现新的非 gold 卡,且
  119 个都可归因于 alias token(D_SHAM 同为 120/120——长度/泛化效应,
  不是对齐效应);gold 新进 Top-3 的仅 4 行。pick_verify 的 .944→0 就是
  这样被反超的。
- **一个此前未知的结构性事实**:perception gold 时刻的 last action 多为
  `pi0_pick`(phase=P_grasp,success=True,近闭夹爪),查询里根本没有
  `found/world_error` 等感知字段——"该想起 perception 经验的时刻"发生的
  是 pick 结果叙事。即便卡侧补满感知现象词,这类查询也只能靠任务名词
  与之连接,而任务 nouns 对所有卡近似对称。

## 4. 十问的离线子集回答

1. **61 卡多少能提取 alias?** 61/61(0 空),468 条,min 5/mean 7.67/max 8;
   层构成 R1 symptom 292 / R3a 字段收割 167 / R5 recipe prompt 9。
2. **perception 0/17 → ?** 仍 0/17(D2/D3/D_SHAM 三臂同)。
3. **五臂 R@1/R@3/MRR** 见主表。
4. **query enrichment 为何无效?** D1 复现 C1(+1.7pp);更关键的是
   D3−D2 ≈ +.009 MRR——卡侧加了 alias 后,富 query 的状态词依旧不产生
   区分度(词表不相交的镜像:现在两边都有词,但都是通用词)。
5. **card alignment 是否产生新 token overlap?** 是(339/350 行),
   但 gold rank 中位数不动、仅 4 行新进 Top-3。
6. **rank 改善多少来自 alias?** mean gold rank 165→16(未截断序,含
   未上榜=999 惩罚),但改善几乎全部来自"从 0 分到低分",不足以进 Top-3;
   Top-3 层面净效果为负(119 点被挤入非 gold 卡)。
7. **collision/hard-negative?** alias collision:119/120 gold 点出现
   alias 驱动的新非 gold Top-3 卡;hardneg 噪声 14/14 不变(已饱和)。
8. **online t9?** 未跑(门控 STOP)。
9. **纳入最终方法?** 否——在冻结词面检索下,卡侧可观测别名是净伤害。
10. (在线两问随 STOP 不适用。)

## 5. 最终判定

**CARD-SIDE ALIGNMENT: NOT SUPPORTED**

依据:预注册四门槛中 1/2/4 显著不过(perception 0/17、非 perception
−35pp、不优于 sham)。机制上,"运行时可观测词汇"与"卡的区分性信息"
近乎正交:observable signature 描述的是域通用现象(夹爪、谓词、失败
布尔),把它们写进检索通道,等于给所有卡同时加了同一批词。研究问题的
答案是:**"怎么做"(semantic/procedural)与"什么在线现象应该让我想到
它"(observable signature)确实需要两种表示——但第二种表示无法用
可观测词汇的词袋子集来实现区分;要让 observable signature 可检索,
必须改变打分方式(如带 IDF 权重/归一化/类别先验),而这在冻结清单内。**

## 6. 边界与诚实声明

- 负结果的适用范围:**冻结的未归一化词面重叠打分** + bag-of-words 别名。
  它不证明"卡侧表示对齐"这一思想错误,只证明在本实验冻结的检索器下、
  以卡自有 evidence 可提取的词面形式,对齐不能转化为排序收益。
- extractor 的一切迭代发生在读任何测试数据之前;audit 泄露检查 17 条
  命中逐条裁决为证据内禀重叠(任务指令原文、结果字段短语),无配对定制;
  benchmark 之后 sidecar 未做任何修改(重跑可验证)。
- 未做层消融(R1/R3a/R5 各自贡献):机制日志按条带来源,事后可拆,但
  主结论(可观测词通用、无区分度)对三层同构成立——symptom 层的
  `basket/rim/gripper` 与字段层的 `success flag false` 同样泛化。

产物:`analysis/retrieval_aliases_v1.json`(冻结)、
`analysis/stageD_alias_audit.md`、`scripts/build_retrieval_aliases.py`、
`scripts/audit_stageD_aliases.py`、`scripts/memory_staged_benchmark.py`、
`analysis/memory_staged_results.json`、`analysis/memory_staged_mechanism.jsonl`。
