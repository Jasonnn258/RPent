# H0 · Stage2K：Stage2J A0 预注册候选独立复审

> 2026-10-09｜**源码复核 / 方法学审查 / 零 outcome 读取**。  
> 受审件：`analysis/harness_h0/H0_OE_STAGE2J_A0_TOOL_FEEDBACK_PREREG_CANDIDATE.md`（commit `762bf1a`，`DRAFT_NOT_FROZEN`）。  
> 源码核对：`robots/libero/tools.py:201-271,1140-1162,1604-1650`，`robots/libero/toolkit.py:60-112`，`rpent/utils/rtrace.py:76-159`，`scripts/stageR_collect.py:112-167`；权限依据：`analysis/harness_next/METHOD_SPEC.md` v0.2.2 §5.6。  
> 数据依据：用户回传的 Stage2I 结构扫描（187 episodes、235/235 pick 结构配对、2,859 chunk）；本轮未独立扫描服务器私有原始轨迹、未读取任何 outcome 值。

## 0. 审查结论

**`STAGE2J_DOCUMENT_DELIVERED / DESIGN_REQUIRES_REVISION / EXPERIMENT_HOLD / P0_DATASET_DOCUMENTATION_GO / H0_A0_NUMERIC_DEFAULT_STOP_PENDING_PURPOSE`**

Stage2J 有三项重要正确推进：①把真实 D2 工具返回与同技能 FGONLY 物理审计配对；②去掉 `check_success` 的主标签 shortcut 并显式申报共享 EEF 通道；③以 episode 聚类、原始全语料样本框和新版本研究性标签限定解释。保留其 **DESCRIPTIVE_ONLY** 与 **NO RUNTIME AUTHORIZATION** 的立场。

但**不能按 Stage2J §8 所称“可直接冻结”为可执行协议**：有三个需要先修复的定义问题，以及一个需重新判断的项目立项条件。

## 1. B1（高优先级）：丢弃不完整测量点导致“any-time 成功”标签不对称

Stage2J §4.2 只要求基点和至少一个未来测量点有效；§4.3 允许 `MEAS_POINT_DROPPED` 后保留 pick。其主参考 `FGONLY = any(FG_match(p))` 是**存在性判据**。

设一个 pick 的有效点均 `FG=False`，但遗漏点恰好在物体取得瞬间。删除遗漏点后计算 `any=False`，会把 **UNKNOWN** 错写为物理 **NEGATIVE**。该问题独立于 Stage2I 外层 `meas` schema 235/235 PASS；Stage2I 未验证所有内部目标位姿/EEF 关键字段。

**必要修订（只能是新候选版本，原文不回写）：**
- 明确三值参考 `POSITIVE / NEGATIVE / UNKNOWN`：任一完整有效时刻的 FG 为真，存在性参考可以判 POSITIVE；所有要求观测的点都有效且 FG 均假，才判 NEGATIVE；存在关键点缺失又没有观察到 FG 真，则判 UNKNOWN。
- 事先定义完整的应观测 checkpoint 集（所有 chunk 前和末端 final），缺失/非有限分开登记；UNKNOWN 不得作为 False 进入 2×2 主表。
- 另行披露 UNKNOWN 的 episode/pick 与时间位置分布。缺失机制可能与抓取动作、仿真状态和仪器错误相关，完整案例率不能不加限定外推全体。
- 如果仅需要可解释的完全案例评价，最稳妥是 **any required measurement missing => 该 pick 排除并披露原因**；不能用删除单点产生的负标签。采用三值保留会保留部分可确定的 POSITIVE，但需说明这是非对称可确定性。

**裁决：当前 `MEAS_POINT_DROPPED` 规则未过标签有效性 Gate（HOLD）。**

## 2. B2（源代码级错误）：`result.episode_truncated` 字段不存在

`robots/libero/tools.py:256-270` 的 `pi0_pick` 返回字典包含 `libero_terminated`，**不包含 `episode_truncated`**。

`episode_truncated` 实际属于 `dump_state` 写入的 **states.json step 顶层字段**（`robots/libero/tools.py:1143-1160`），也是 `view_driver_state` 向 Planner 投影的顶层字段（`tools.py:1604-1650`）。

Stage2J §3.2、§5.2 将其写成 `result.episode_truncated`，若据此实现分层将得到缺失/错误值。须采用 `states_entry.episode_truncated`，并记录它与 pick 返回时点的一致性、字段权限及缺失处置。

另外 Stage2J §3 的断言“剔除 `libero_terminated=True` 就能让结果完全由运动学 latch 决定”**过强**：terminal=False 且 truncated=True 的 `success=False` 仍可由截断路径产生。可以精确定义为“排除官方成功镜像，剩余 negative 包含未触发 latch 的预算耗尽或截断执行”；不能将全 PRIMARY 描述为仅靠运动学触发的完整抓取成败判定。

**裁决：schema 变量与分层语义需修订（HOLD）。**

## 3. B3（指标适配）：原始一致率无法独自评价 tool reliability

Stage2J §5.1 唯一主指标 `raw concordance = P(flag==FGONLY)`，如果工具在样本框里经常返回 False，始终预测 False 的常数基线也可能得到很高一致率，而 **flag=True 是否值得 Planner 信任**仍不清楚。

Stage2J 明确每类 flag 至少 10 才过可估性门，这是必要但不足以消除多数类支配。尤其“是否允许任务完成/是否必须追加验证”的错误代价不对称，单一准确率不提供所需误差结构。

**建议 v2 选择（不在已有 outcome 上后验重选）：**
- 如果 A0 是**描述性判据一致性普查**：保留 raw concordance，但强制同时输出所有 2×2 格子、flag prevalence、两条 always-True/always-False 常数对照、按 episode 分组的不确定性；结论仅称“观察到的一致性”，不得简称“工具可靠性已验证”。
- 如果 A0 是为 **P1 验证时机选择** 提供已验证的工程输入：先指定合法消费者、错误代价/决策条件，选择与其匹配的**单个主损失**（例如被接受 flag 中 FGONLY 不成立的条件风险）及支持性样本门，不能保留 `raw concordance` 却对外宣称“危险错误率已降低”。
- FGONLY 的提升 + EEF 跟随是研究性 proxy（共享 EEF），不是接触、保持或任务官方完成的直接物理 oracle。评估对象不能漂移为 `FPR of physical grasp success`。

**裁决：没有新 consumer 时，raw concordance 可作描述性数字，但没有强工程决策意义；新消费者出现须先改预注册而不是在同一结果上挑指标。**

## 4. B4（战略判断）：没有 Runtime 消费者，不等于没有科学数据集消费者

Stage2J §7/§8 将“无已授权 Runtime/Evolution 消费者”用作默认 H0 收官的关键理由。**作为禁止线上门控，这完全正确。** 然而本项目还存在独立、明确的合法交付：**EERD v0.1 证据来源/对齐/构念/泄漏审查数据集及 P1 的离线实验设计**。

应区分三个独立立项判断：

| 工作 | 本轮决策 | 依据 |
|---|---|---|
| H0 A0 一致率数值执行 | **HOLD；默认不执行** | Stage2J 未冻结，B1–B3 待修，用户未批准 outcome 分析 |
| EERD v0.1 数据契约、样本 manifest、证据可见性 schema | **GO：仅文档和只读结构化设计** | Stage2I 235/235 结构配对可作为 foundation，不需要读 outcome |
| P1 主动验证/恢复方法与评价计划 | **GO：仅研究方案**；控制/rollout 仍 HOLD | 要用不同验证策略下的真实未来后果证明因果/净收益；现有离线数据不足 |

数据集存在的意义可以是**benchmark / measurement / 研究可复现性**，无须先成为 Runtime 的合法消费对象；但这同样**不赋予**训练、部署、在线读取特权真值的许可。数据集 v0.1 仅以内部草案/结构能力声明，待物理标签与任务划分核查后再对外发布。

## 5. 方法学下一步：从描述性 A0 转向 P1 的最小可证伪机制

### P1 研究问题

**在固定低层 VLA 与总动作/观测预算下，证据驱动的“何时多观察一步”能否减少被误判为完成的物理任务，同时不造成过高额外成本？**

可比较策略：无额外验证、始终验证、固定间隔验证、简单置信/夹爪阈值、PAEG legality-aware + persistence-aware verification 候选（需未来另外立项和批准）。评价以物理任务达成、错误完成、总额外观察/机器人动作、干预后的恢复收益与置信区间报告；不得拿现有 Stage R 的 480 重建试验直接替代自然 D2 决策。

合理的新贡献必须落在**有限预算、时效证据与物理干预反馈同时作用时的决策改进**，而非声称首次“允许 abstain”“加一个 verifier”或“维护证据库”。对照 CheckVLA、Zetta、RegenHarness、VASO、MemEvolve。

### 现有 EERD 资料的作用

- A 类：确认工具报告与审计真值之间**哪些构念能够辨别、哪些永远只是研究代理**；
- B 类：构造失败持续性分布、恢复决策的异质条件与测试用的事件级分组（不能以子试验充当 480 个独立事件）；
- C 类（缺失，未来采集）：真实 D2 决策边界、验证动作及其成本、已固定评价期的不同策略下结果、独立测试任务。无 C 类不可声称 P1 提高在线成功率。

## 6. 最终 Gate 与边界

| Gate | 裁决 |
|---|---|
| Stage2J 文档交付 | **PASS** |
| B1 缺失点的 any-time 参考语义 | **REVISION_REQUIRED** |
| B2 truncation 字段路径与机制描述 | **REVISION_REQUIRED** |
| B3 单一一致率是否契合工具可信决策 | **REVIEW_REQUIRED** |
| A0 冻结资格 | **HOLD** |
| A0 outcome 读取/统计 | **NOT_AUTHORIZED** |
| 数据集 v0.1 文档设计 | **GO**（不读结果值） |
| P1 闭环实验 | **HOLD**，须全新预注册及用户批准 |
| Stage R §36 / S1-DEV0 | **HARD STOP / ON_HOLD** |
| 本轮新算法创新 | **NOT_ESTABLISHED** |

**最终状态：`STAGE2K_SOURCE_REVIEW_COMPLETE / STAGE2J_REVISION_REQUIRED_BEFORE_FREEZE / EERD_DOCS_ALLOWED / P1_RESEARCH_ONLY / NO_NEW_EXPERIMENT_AUTHORIZATION`。**
