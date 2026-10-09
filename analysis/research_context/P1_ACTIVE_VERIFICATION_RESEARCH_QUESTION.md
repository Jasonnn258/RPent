# P1 — Evidence-Aware Active Verification · 最小可证伪研究问题与方向分级

> 2026-10-09 | **研究设计文档;零 outcome 读取;零统计/仿真/训练/Runtime 改动。**
> 依据:`RESEARCH_MASTER.md`(P1 定义)、`analysis/harness_next/METHOD_SPEC.md` v0.2.2 与 `NOVELTY_REVIEW.md` v0.2.2、Stage Q/R 终报、Stage2G/2K 审查、`EERD_V01_DATA_CONTRACT_DRAFT.md` + `EERD_V01_FIELD_PROVENANCE_QA_SPEC.md`。
> 约束:闭环实验 HOLD(§36 Hard STOP);本文只交付问题定义、机制区别、数据需求与对照设计,以及 §5 方向分级裁决。

## 0. 一句话问题

**在冻结 VLA 与固定总预算(动作+观测)下,只消费决策时刻合法可得的证据来选择"何时多验证一步/是否接受/是否恢复"的策略,能否降低被误判为完成的物理任务,且不牺牲真实完成率、不超预算?**

这是 PAEG(Evidence Claim 合法性 × 失败持续性 × 双门授权)唯一能被**实验证伪**的最小机制主张;其余组件(规范、数据集)只支持"问题成立",不支持"机制有效"。

## 1. 可证伪假设(预注册形态,冻结于任何数据采集之前)

### H-P1(主假设)

固定低层 VLA、固定每 episode 总预算 B(动作 chunk + 验证动作 + 观测步统一计账),在真实 D2 决策边界上:

> 以 online_eligible 证据为唯一输入、按 PAEG 证据资格规则(合法性分级 + 时效 + 持续性感知)选择验证时机的策略 **π_ev**,其**错误完成率**(策略接受"完成"而独立物理审计判定未达成的 episode 比例)显著低于等预算最强静态基线。

对照基线(全部等预算计账):
- C-1 无验证(直接接受工具返回);
- C-2 固定间隔验证(每 k 步验证一次,k 扫一个小网格,取其最优=强基线);
- C-3 始终验证(预算允许处全验证;预算上限内自然收缩);
- C-4 静态阈值(grip/EEF 上升量单阈值;以及 **conformal 校准阈值**——CheckVLA 型,用标定集校准干预时机,为最强静态形态);
- C-5 随机同时机验证(同验证预算、时机随机;剥离"时机信息"本身)。

**主指标**:错误完成率差 π_ev − best(C-1..C-5),episode 聚类推断,预注册 margin。
**非劣性门(必须同时过)**:真实完成率不降超过预设 ε;总成本不超 B;abstain 率单报告(不作门槛,PAEG 允许弃权是一等公民)。

### H-P1m(机制定位子假设——判"机制成立"还是"数字好看")

PAEG 的可检验增量主张是:**收益集中在静态校准失配的子群**,即失败持续性异质处(Stage R 实测:连败 3 次后第 4 次成功率 1/17,远低于 iid 基线 ~.30 —— 恰是任何 exchangeability 假设失效的区域)。预注册分层:

- 若 π_ev 仅在**随机失败子群**与基线打平、且在**持续性失败子群**也打平 → 即使总错误率偶有改善,判 **MECHANISM_NOT_SUPPORTED**(收益不来自声称的机制);
- 若 π_ev 在持续子群显著优于 C-4(conformal 静态阈值)而随机子群打平 → 机制主张的最强支持形态;
- 若 π_ev ≈ C-4 全线 → 贡献塌缩为"CheckVLA 思想应用于抓取验证",**不具新颖性,如实降级**。

### 证伪条件(预先写死)

π_ev 在主指标上不优于 best(C-1..C-5)(预注册 margin 内)→ **P1 NOT SUPPORTED**,PAEG 决策资格层无实测收益,规范层降级为"负结果+工程护栏";不做事后子集挑选、不改 margin。

## 2. 与已有工作的机制区别(逐条可证伪,非形容词)

| 系统 | 其机制(核验来源) | 与 P1 的机制差异(=我们的可证伪主张所在) |
|---|---|---|
| **CheckVLA**(NOVELTY_REVIEW [P-abs]) | conformal 校准干预阈值:first-intervention 触发,**exchangeability 假设下的分布无关保证**;阈值静态、作用于一个监测分数 | P1 的时机决策受**证据合法边界**(什么能看/什么只是研究真值)、**物理验证动作成本**与**失败持续性异质**(h(k) 衰减区)同时约束,并决定验证后的接受/恢复分支。可检验差异:exchangeability 失效的持续子群上 C-4 应退化而 π_ev 不(§1 H-P1m)。若实测无差异,新颖性让渡 |
| **Zetta**(源码级) | 闭环 critic-恢复 + 版本化技能;统计门(exact McNemar 两段式 heldout)作用于**技能候选改善验证**;critic 分数在线消费 | P1 不改技能、不进化;对象是**运行时证据资格与验证成本**的决策,审计真值按 PAEG I1/I4 禁止进入策略输入(Zetta 的 critic 可自由消费自有评分)。可检验差异:P1 在"critic 类证据不合法/不可得"的约束下仍要求改善——即只用工具返回+本体感知达成同时机决策 |
| **RegenHarness**([P-abs]) | 版本化记忆 + commit gate + proposal/termination/completion 三分生命周期,作用于 **harness 自我修改** | P1 冻结 VLA 与 harness,零自我修改;经验/技能更新属 P2,且 P2 需 Evolution Gate 的合法 outcome 来源(现无)。可检验差异:P1 的收益不依赖任何记忆/版本机制(对照 C-5 与"π_ev 去记忆化"消融) |
| (VASO/EmbodiSkill) | trace 证据不足信论证 / 缺陷-失效分流先例 | 已在 NOVELTY_REVIEW 让渡;不重复主张"允许弃权""缺陷分流"为创新 |

**共同不主张**:首次闭环验证、首个 verifier、首个弃权机制、首个版本化记忆(全部被占席)。

## 3. 所需新数据(C 子集;不可从 A/B 构造的理由)

| 需要的字段 | 为什么 A/B 给不出 |
|---|---|
| 真实 D2 边界的合法快照 + 当时在线可见证据集 | A 有 D2 但未来是 Planner 自选动作(policy-coupled);B 有固定协议但是 D1 重建、restore-SENSITIVE(APPROXIMATE)——**D2 合法性与协议固定性在现有资产不可兼得**(Stage2G 定案) |
| 验证动作 `verification_action` + 逐项成本计账 | 现有轨迹中没有受控验证动作 |
| 策略标识 `decision_policy_id` 与随机/配对分组 | 现有数据无策略对照 |
| 独立 `physical_future_reference` + 固定 horizon | A 的同技能 final_meas 非"返回后未来";任何事后构造都会重蹈 Stage2H A1 覆辙 |
| `matched_initial_state`(配对)或组内随机化 | 现有采集无配对设计 |
| heldout 任务 | 仅 3 任务且全部已用于历史分析 |

采集形态(设计,未授权):前瞻 instrumented cohort——在真实 D2 边界注入策略对照,冻结 VLA/预算/评价 horizon,一次预注册。规模由功效分析定(依赖 P0/A0 普查给出的 R_accept 量级;S1 教训:15pp 差异需 25-56 cells,勿低估);**先 A0 后 C 的顺序是信息价值最优**(A0 一次授权同时供 EERD G-QA-3 首块与功效先验)。

## 4. 评价与治理骨架(预注册要素清单)

1. 单位与分组:episode 聚类;配对(孪生初始态,S1 可行性已证 spatial 孪生可得)或组内随机;split 按 `cross_dataset_provenance_group`(EERD QA 规范 §4)防 A/B 同源泄漏。
2. 输入防火墙:策略只准吃 `online_eligible` 视图;审计真值只进评价(PAEG I1/I4,运行时抽查禁读)。
3. 指标:主=错误完成率差;非劣性=真实完成率/预算;次=恢复收益、abstain 率、成本-收益前沿;一切区间 episode 聚类。
4. STOP 规则:预注册 margin 不过即 NOT SUPPORTED;infra 错误指纹清单纪律(Stage C 事故账);中途禁改策略/指标。
5. 授权路径:全新预注册 → 用户批准 → §36 在该协议范围内显式局部解除(仅此 cohort,不泛化)。

## 5. 方向分级裁决(任务四)

### 5.1 理论基础已充分(文档层收敛,不需要更多理论轮次)

| 方向 | 状态 |
|---|---|
| PAEG 规范层 v0.2.2 | 两轮独立复审收敛;再改只能因新数据或外部实质缺陷 |
| Stage2J v2 设计(B1-B3 已解决) | 本轮交付;设计层 freeze-eligible |
| EERD 契约 + 字段级 QA 规范 | 本轮交付;八门齐 |
| P1 问题/对照/数据需求 | 本轮交付;已到"不采数据就无法再推进"的终点 |

**文档轮次封顶纪律(反"以阶段数量代替解决问题")**:以上四项在**无新数据(A0 读数/C 采集)、无新外部审查实质缺陷**的情况下,不再产生新的修订轮次。重开仅限:新数据、外部审查、用户明示。

### 5.2 需要实验(且需新授权/新数据)

| 优先级 | 实验 | 前置 |
|---|---|---|
| 1 | **A0 数值普查**(检查 B+outcome 读取,一次性) | 用户批准;产出 EERD-A G-QA-3 首块 + P1 功效先验;无消费者则默认不执行 |
| 2 | **C cohort 采集 + P1 闭环对照** | 全新预注册 + 用户批准 + §36 该协议内局部解除;唯一能检验 PAEG 机制主张的路径 |
| 3(远期) | P2 经验/技能演化 | 多任务经验消费痕迹 + 更新后独立回归验证;现无数据 |

### 5.3 应停止(明确 STOP)

1. **A/B 现有资产上的新回顾性代理/重标签/再加权分析**:Stage2D 弱信号已定,Stage2I 已警示不宜围绕 235 样本反复重定义代理;边际信息趋零 → STOP;
2. **C 存在前的机制变体设计细化**(verifier 架构、gate 变体、evolution 策略的进一步文档迭代):零边际信息 → STOP;
3. **任何 Runtime/Evolution 在线接线**:§36 + PAEG I1-I4,持续硬停 → STOP;
4. **S1 memory 线**:维持 ON_HOLD;重开须用户明示(与 P1 无资源竞争关系时不自动重开)→ STOP(本轮);
5. **若用户最终不授权 C 采集**:P1/P2 以"规范+问题定义+负结果边界"收官,EERD 保持文档态,H0 全线收官——这是可接受的终态,不是失败。

## 6. Gate 表

| Gate | 裁决 |
|---|---|
| P1 研究问题可证伪性 | PASS(H-P1/H-P1m/证伪条件预写死) |
| 与 CheckVLA/Zetta/RegenHarness 机制区别 | 条件成立(差异点全部转为可检验对照;无差异则让渡) |
| 现有数据支持 P1 闭环结论 | FAIL(必须 C cohort) |
| P1 闭环实验执行 | **HOLD**(须全新预注册+授权+§36 局部解除) |
| A0→C 顺序建议 | GO(信息价值最优路径,均待授权) |
| Stage R §36 / S1-DEV0 | HARD STOP / ON_HOLD 不变 |

**最终:`P1_MINIMAL_FALSIFIABLE_QUESTION_DELIVERED / MECHANISM_DISTINCTIONS_TESTABLE / REQUIRES_NEW_C_COHORT / EXECUTION_HOLD / DOCUMENT_ROUNDS_CAPPED / STOP_LIST_ISSUED`**
