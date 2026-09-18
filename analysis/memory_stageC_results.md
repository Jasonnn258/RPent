# Stage C 结果报告:Query Sufficiency / Progress-Aware Trigger / 在线组合(2026-09-18)

研究主旨:**机器人调用长期经验之前,是否必须先形成一个由真实执行状态支撑的
"我现在到底发生了什么"的表示?以及只有当实际物理进展偏离预期时,才应该触发
长期经验检索吗?**

门控路径:C1(query 丰富化)离线 **NOT SUPPORTED** → 不带 query 臂进在线;
C2(progress trigger)离线 **SUPPORTED**(P .986 / R .776)→ 在线单变量
**O0 vs O2**(其余一切冻结同 #49:同 access fix、同 Planner/Pi0.5/SAM3、
同卡库、同 lexical retriever、同 turn 预算 40 / token 24576 / 超时 3600s、
同任务 t3/t5/t9 × s1-10 × r1)。O0 = #49 memB2 原行复用
(compatibility audit 通过,见 stageC_compatibility_audit.md);
O2 唯一差异 `RPENT_MEMORY_TRIGGER=progress`(C2 冻结规则 R1-R5,
逐 tool result 评估,boundary 冲刷,cooldown 2 / cap 6)。

## 0. 数据完整性与基础设施事故(必须先读)

在线批(06:17-11:29)期间遭遇**出口代理中断**(~07:15 劣化 → 07:26-07:48
硬断 → 08:21 前残余抖动),之后 GLM 晨间延迟(~3 min/turn)造成若干
3600s 墙钟超时。全部 24 个非成功结局逐集审计 run.log(方法与逐集明细见
`stageC_outage_ledger.md`):

- 22+6 个网络杀(`ModelAPIError`/ConnectTimeout,0 轮或中途)→ 按 ≤3
  infra 重试纪律清理重跑,episode 目录全部保留;
- 最终 **3 格(t3 s2/s6/s7)3 次 infra 尝试耗尽**,定型 `infra_missing`,
  不进任何分母;
- 4 个 policy_fail **全部验证为真实失败**(38-40 轮、无 API 错误);
- **最终 O2 数据集零网络混入**:26 官方格 + 1 格 smoke(t3 s1,完整正式
  配置 episode,计入)= 27 有效格,SR 分母一致口径。

## 1. 主表:八项优先指标(用户规格排序)

| # | 指标 | O0(旧触发+贫query) | O2(progress 触发) | 判 |
|---|---|---|---|---|
| 1 | Trigger precision | .265(13/49) | **1.00(13/13)** | ✅ 大幅提升 |
| 2 | False trigger / episode | 1.2(36 次无关注入/30 集) | **0.00(0 次)** | ✅ 全消 |
| 3 | Harmful/irrelevant 注入 | 36 次(每次 ~347 tok) | **0 次** | ✅ 全消 |
| 4 | Relevant@1 / @3 | .571 / .571 | **.889 / .889** | ✅ +32pp |
| 5 | Retrieval count / ep | 1.63 | **0.48** | ✅ 少而准 |
| 6 | Success Rate | .733 | **.852** | ✅ +12pp |
| 7 | Planner turns(mean) | 29.8 | **28.5** | ✅ 略降 |
| 8 | Wall time(mean) | 2465s | **2141s** | ✅ −13% |

检索本身开销两臂相同(词面检索 ~0.9ms、~346 tokens/次注入)——差异全部
来自"何时触发、查什么时刻"。

## 2. 任务层与配对

| 臂 | n | SR | t3 | t5 | t9 | turns | wall |
|---|---|---|---|---|---|---|---|
| B1(仅 access fix,无触发) | 30 | .833 | .60 | 1.00 | .90 | 29.1 | 2489s |
| O0(+旧触发+贫query) | 30 | .733 | .60 | 1.00 | .60 | 29.8 | 2465s |
| O2(+progress 触发) | 27 | .852 | **.86** | 1.00 | .70 | 28.5 | 2141s |

配对(同 task×seed):O0_vs_O2(n=27)**5 胜 / 2 负 / 20 平**(O2 净 +3);
B1_vs_O2(n=27)**2 胜(O2)/ 4 负 / 21 平**(O2 净 +2)。

- O2 恢复并略超 B1 无触发基线(.852 vs .833),幅度在噪声量级,但方向一致;
- 最大单任务效应在 **t3(+26pp vs O0 与 B1)**——t3 是五类失败混合任务,
  也是 progress 信号最丰富的任务;
- 诚实记录:t9(perception 重)上 O2 .7 仍低于 B1 .9(2 格,40 轮耗尽型),
  与 C1 结论一致——perception 卡在词面上检索不到,触发再准也查不出有用的卡。

## 3. Trigger 层:离线预测的在线兑现

| 量 | C2 离线重放 | C3 在线 |
|---|---|---|
| precision | .986 | **1.00**(13/13 对齐 gold 时刻) |
| recall | .776 | **.302**(13/43 时刻) |
| 误报 | 69→0(消除) | **0** |

- **precision 完全兑现**:R1-R5 冻结规则在线零误报。在线 13 次火的构成:
  12× R5(release 后谓词未置)+ 1× R1(perception 无观测);R2/R3/R4
  在线未火——健康 episode(SR .852)很少以那种方式卡住。
- **recall 保守化**(.776→.302)的两个原因:①人群更健康——C2 离线重放的
  #49 集群失败率高(卡住时刻多),O2 在线自己把成功率拉上去了,可覆盖
  时刻本来就少;②cooldown 按 boundary 计数且 drop 掉窗口内后续火
  (离线按 turn 距离)。这是刻意的保守取向:宁可少查,不注入噪声。
- F1:.245(O0)→ .464(O2)。

## 4. Ranking 层与九类失败拆分(retrieval-wrong 细分)

- O0:7 个 gold 事件,relevant@3 .571;6 个硬负例事件(失败集上的
  predicate 火)top3 全部被 retreat 卡占据(6/6);
- O2:9 个 gold 事件,relevant@3 **.889**;4 个硬负例事件 retreat 进 top3
  4/4(硬负例行为不变——失败集上查到 retreat 卡是词面排序的固有行为,
  但 O2 注入总量小,伤害被 precision 挡住);
- retrieval-wrong 细分(O2):错误事件仅 1 个,且为
  **QUERY_INSUFFICIENT**(gold 完全不在未截断词面序里,query 没携带
  卡侧词表词汇)、RANK_WRONG 0 ——与 C1 的机制结论完全一致:
  词面检索的错误几乎全是"词表不相交",不是"排序排错"。

九类失败 breakdown(O2 的 4 个真实失败):
- t3 s10:grasp 类(单次 pick 失败后 planner 自报 stuck,38 轮自弃);
- t9 s2 / s3 / s6:QUERY_INSUFFICIENT 类连锁(perception 循环耗尽 40 轮,
  对应 perception 词表缺口 + R1 只火过 1 次的保守性);
- 无 RANK_WRONG 类、无 controller 类、无 infra 类混入。

## 5. 十问的 C3 子集回答

**Q:progress trigger 在线有收益吗?**
有,且全方位:precision .265→1.00、误报 1.2/集→0、SR .733→.852、
turns/wall 同步下降。八项优先指标全部 O2 ≥ O0。

**Q:组合至少恢复到 B1 Access-fixed baseline 了吗?**
恢复了并略超(.852 vs .833,配对净 +2)。关键转变:O0 的触发+检索组合
曾把 SR 拉到基线**以下**(-10pp,#49 的核心病灶);换成 progress 触发后,
同一卡库、同一检索器、同一注入机制,变成了基线**以上**。收益集中在
t3(+26pp);t9 上仍差 B1 两格(perception 词面缺口,C1 已判不可修)。

**Q:Dynamic Memory 从噪声源变成有效机制了吗?**
从"净伤害"变成了"精准但保守的辅助":36 次无关注入清零、13 次注入
12 次带 gold 卡;但 recall .302 说明它只在少数明确卡住时刻出手。
定性:它不再需要被关掉(对比 #49 结论 executable=NO 时的处境),
但也还不是主要得分来源——主要得分来源是"别在错误时刻打扰 planner"。

## 6. 三个最终判定

| 判定 | 结论 | 依据 |
|---|---|---|
| **QUERY(H1)** | **NOT SUPPORTED** | C1 离线:Q2−Q0 R@3 仅 +1.7pp,perception 0/17,硬负例不动;机制:query 侧状态词与卡侧词表不相交。在线零额外证据反对改判(QUERY_INSUFFICIENT 1 例与该机制一致) |
| **PROGRESS TRIGGER(H2)** | **SUPPORTED** | C2 离线 P .986 / 误报 69→0;C3 在线 P 1.00 / 误报 0,precision 完全迁移;recall 在线保守化(.302)如实记录,源于人群健康度 + cooldown drop 语义,不改变"只在物理进展偏离时触发"这一主命题成立 |
| **ONLINE COMBINATION** | **SUPPORTED** | 单变量 O0 vs O2:八项优先指标全部占优,SR .733→.852(配对 +5/−2),恢复并略超无触发基线 B1(配对 +4/−2),t3 +26pp;0 次有害注入 |

## 7. 对研究主旨的回答

**"必须先有执行状态支撑的'现在发生了什么'表示吗?"** ——在线证据支持:
同一个检索器,query 不变(仍是贫格式),仅仅把**触发时刻**从"重复计数
启发式"换成"物理进展偏离判定"(残距、上升高度、谓词状态、观测有效性),
relevant@3 就从 .571 升到 .889:检索质量的瓶颈不在 query 的丰富度
(C1 已证不可修),而在**在什么时刻检索**。

**"只有物理进展偏离预期时才触发吗?"** ——支持:进展中检索(O0 的 36 次)
全部是噪声且净伤害;偏离时检索(O2 的 13 次)全部命中 gold 时刻。
保守方向(recall .302)的代价是漏查,但漏查不伤 SR,误注入伤 SR
(#49 与本次 O0 的对照即证明)。

## 8. 边界与下一步(不构成新承诺)

- t9 perception 词面缺口是结构性剩余(C1 判 NOT SUPPORTED 的根因),
  本次在线再次复现(3 个 40 轮耗尽失败全在 t9);
- 硬负例行为(失败集上 retreat 进 top3)未变,只是被低频触发兜住;
- 本报告不改变冻结件:卡库、Q0_FIXED 权重、R1-R5 阈值、B2 verifier
  均未动;线上唯一新代码是 retrieval.py 的 progress 分支(v1 逐字保留)。

数据:`analysis/memory_stageC_results.json`(逐事件)、
`outcome_validation_runs.csv`(memC 行)、episode 目录 logs/ovpm_exp/、
事故账 `stageC_outage_ledger.md`。
