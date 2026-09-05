# Memory Utility 分析 — 哪些历史经验真正有用

_2026-09-05。数据同 `reasoning_timing_failure_analysis.md`(303 run + 3025 条记忆相关决策行,见 `memory_utility_cases.csv`)。_

**一句话结论:这个系统当前没有"经验记忆"——episodic 存储恒为空(303 run 零写入),全部"记忆"实为三类静态资产(空索引 MEMORY.md、编写好的 guides、历史 recipe 索引)+ 9 条人工规则注入;真正产生增益的只有规则注入(R1/R5),静态资产被无差别读取且与成败零相关。**

---

## 1. 记忆的现状盘点

### 1.1 episodic memory:空转

- `resources/libero/memory/MEMORY.md` 内容恒为 "No prior manipulation memories are available"(每个 run 开头读一次,352 次 read_text_file 全读到这句话)。
- **142 次 `write_text_file` 全部写进 run 自己的输出目录**(自我笔记),没有一次写回 memory 目录。经验从未沉淀。
- 双臂 mem_reads 均 ~1.2/run:读取是开场仪式,不是决策。

### 1.2 静态资产:无差别读取,零区分度

| 资产 | 读取(read_text_file/list_dir 合计) | 读它的 run SR | 不读的 run SR |
|---|---|---|---|
| guides(strict_hybrid/pro_hybrid/env_calibration) | 1274 次,~97% run | 34-39% | n≤2,无意义 |
| prior_results(results_spatial_pert 的历史 recipe) | 1025 次,~90% run | 34-38% | 56-60%(n=5-9,反向!) |
| memory/MEMORY.md | 352 次,100% run | 35-40% | — |

读取率接近 100% → 读取行为本身不携带任何决策信息;成功与失败的 run 读了一样的东西。**当前不存在"什么 context 下查什么"的选择性,自然也不存在记忆的边际效用。** structured 臂内 prior_results 读取者 SR 62% vs 不读 44%(n=21/9)是唯一正向信号,样本太小仅记录。

### 1.3 规则注入:唯一被证有效的"记忆"

SM1 的 +9pp 全部来自 structured_rules_v1.json 的 9 条规则按 phase 注入。恢复率:

| 规则 | 内容 | 触发数 | 恢复成功 |
|---|---|---|---|
| **R1** | P_look 连续感知≥7 → "commit now,下一个调用必须是动作" | 29 | **29/29** |
| R9 | 剩余≤5 回合 → 最后一搏或诚实 finish | 17 | 9/17 |
| **R5** | t9 进 P_place 未用 pi0_doubled → "用双段放置" | 10 | 5/10 |
| R7 | P_verify → 检查终止谓词后 finish | 10 | 6/10 |
| R4 | pi0_pick≥3 → 查腕姿/间隙,最多再试一次 | 2 | 2/2 |
| R8 | read_text_file≥10 → 停止阅读(计数器还把 guides 误算进去) | 2 | 2/2 |

R5 恢复率只有五成,但 t9 的 3 个同 seed 翻转**全部**由它驱动(其中 t9s6 只触发 R5 一条)——它是"有它不一定赢、没它必输"的关键经验。

---

## 2. 每类经验到底改变了哪个决策(同 seed 翻转逐对)

| 经验 | 改变的决策 | 证据对 |
|---|---|---|
| R1(commit 纪律) | 把 P_look/P_transport 的"再采样一次"改为"用当前估计立即 ACT";move 数 8-9→4-6 | t0s3/s6/s7, t7s1/s3/s6/s9(+t7s10 带 R9) |
| R5(t9 放置原语) | 把"hover+release+微调"改为 pi0_doubled 双段放置 | t9s2/s6/s7 |
| R9(预算尾纪律) | 把尾部 stall 改为最后一搏 release | t7s3/s9/s10 |
| guides / prior_results / MEMORY.md | **可指认的改变:0** | 11 个翻转对中无一由读取触发 |

## 3. Memory Utility Taxonomy

"一条经验值得成为 Global Memory"的判定框架(基于上述证据):

| 维度 | 应记录的内容 | 当前系统的缺口 |
|---|---|---|
| **context(何时适用)** | task 形态(stall 型/precision 型/歧义型)+ phase + 状态签名(如 "release 后 term=false 第 2 次") | 无:规则 trigger 只有计数器,没有结果状态 |
| **trigger(触发什么问题)** | 该 context 下的典型错误模式(place_stall/place_fail) | 有(failure_pattern 字段),但源于人工分析而非自动沉淀 |
| **recommended action** | 具体原语选择(commit-now / pi0_doubled / re-grasp) | 有,且 R1/R5 被证明有效 |
| **expected result** | 动作成功的外观(term=true / grip<0.03 / final_dist<5cm) | **无——这是最大缺口**:动作不带期望结果,无法自动判定"观察与预期一致→提交/不一致→恢复" |
| **actual outcome** | 该经验被应用后的真实结果(recovery_success) | 有(structured_metrics),但无人消费它来更新规则 |
| **是否值得长期化** | 恢复率 + 作用范围(R1 全局 29/29 → 是;R5 任务特异 5/10 但唯一 → 是;R7 6/10 → 存疑) | 无淘汰/降权机制,规则集只会手工增长 |

## 4. 最值得后续 consolidation 的经验(按证据排序)

1. **"hold 后目标已知 → 立即放置"**(t7 stall 13 例 + Case A + R1 的满分恢复率)。通用、跨任务、判据机判(hold=true + 目标 xyz 已解析 + 无失败信号)。
2. **"t9 类精确放置:首 release 失败 → 换 pi0_doubled,禁第三次微调 release"**(t9 place_fail 7 例 + Case B + R5 翻转 3/3)。任务形态特异但判据清晰(term=false 计数)。
3. **"release/动作失败第二次 → 停止微调,重新估计"**(Case B t38 的反面)。当前无规则覆盖(R6 只管 pi0_doubled 循环)。
4. **"动作后例行状态核查可跳过/降频"**(dual-route smoke 里 21 次 not_fast_eligible 的机械 vds)。省 token 型经验,尚无对照数据。
5. **不值得**:历史 recipe 全文(prior_results 读取零区分度)、guides(每次都读,从未被指认改变决策)。

## 5. 当前 global memory 缺什么信息(直接回答)

1. **动作→期望结果对**(expected_result per primitive call):没有它,"观察与预期一致吗"这一步只能靠 LLM 自觉,于是 Q1(一致仍验证)与 Q2(不一致仍执行)都无从自动拦截。
2. **任务形态标签**(stall 型/precision 型/歧义型):hardcap 的教训表明同一策略在不同形态上反号;记忆条目不携带形态标签就无法路由。
3. **outcome 回写**(actual outcome):recovery_success 已经在 structured_metrics 里采集,但从不回流;规则永远不会因为"恢复率跌了"被降权。
4. **首抓/放置的原语级量化档案**(如 t9 的 hang-offset 测量流程、final_dist 分布):成功 run 的放置测量程序(prior recipe 里有文字)从未被结构化成可注入的步骤。

## 6. 证据分级

- 同 seed 对照支持:R1/R5/R9 的决策改变(11 翻转对逐对指认);episodic 零写入(全量 write_text_file 审计)。
- 相关性:静态资产读取与 SR(读取率≈100% 无变异,本质上是常量);R7 恢复率。
- 设计推断(n=1):dual-route 的可省 Slow 调用。

**工具与数据**:`memory_utility_cases.csv`(3025 行:每次 read/list 的 run/turn/类别/目标 + 70 行规则触发行含 recovery_ok)。
