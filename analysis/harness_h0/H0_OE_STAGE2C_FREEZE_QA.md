# Stage 2C — Freeze Conformance & Scientific Limitations Review

> 2026-10-09 | **协议逻辑检查，不是统计/代码验证**。
> 对象：`H0_OE_STAGE2C_FROZEN_PREREG.md` v1；
> GitHub 创建提交 `118d98ccc774ba63f6ad06ab6cd69df8697195b3`，
> 协议 blob SHA-1 `97dc0bc93bae857620554a7c2571c5b0b55b5528`。
> 本文仅为冻结后可追溯的 QA 补充，**不修改已冻结 v1**。

## 1. 明确的审阅结果

**结论：`FREEZE_CONSISTENT / EXECUTION_NOT_AUTHORIZED`。**
Stage 2C 的目的“将既有数据上的新回顾性分析方案固定到不可混淆的内容版本”已经达成；算法有效性、数值功效、独立结果参考和可执行实现均**尚未验证**，不可据此执行统计。

| 项 | 本轮检查依据 | 结论 |
|---|---|---|
| 冻结范围 | 用户只批准 Stage 2C 冻结，无 Stage 2D 结果运行授权 | **PASS** |
| 冻结物身份 | 独立 v1 文件、固定 commit/blob SHA、原内容读回逐字符 MATCH | **PASS** |
| 输入版本 | 数据仓基线 commit `10f158b` + manifest、双 CSV、终报、生成代码 blob SHA | **PASS (remote metadata)** |
| 样本资格 | 冻结 `role=R1_COHORT` 24 event，SAME/RESAMPLE 共 384 科研 trial；checkpoint 的 4 个 DEV 只作来源审计，NATURAL 不进预测 | **PASS (design and prior structural audit)** |
| 真值权限 | stable/acquisition 都来自 sim cps，同源 nested contract，不进合法 Runtime/Evolution | **PASS (scope)** |
| 主要预测 | SAME 两次失败→第三次结果，目标未包含于用于同折拟合/选参的留出 Y3..Y8 | **PASS (protocol rules)** |
| 基线公平 | M0 / M1 均使用留出事件已知两次失败；M0 `+2` 与 M1 `+2` 统一 | **PASS (algebra)** |
| M1 优化 | 固定 mu/tau 网格、训练 event 边际对数似然、平手规则与失稳行为 | **PASS (spec only)** |
| 主评价 | event LOEO、正向 Brier improvement，其他 k/arm 仅探索 | **PASS (spec only)** |
| 小样本统计 | 固定 OOF bootstrap 只描述，未承诺严格 nominal CI/p 值/确认性假设检验 | **PASS (scientific honesty)** |
| 不可辨识项 | OE1b 独立物理假阳率、M2 连败的时序因果、Skill edit repairability | **STOP / NOT_IDENTIFIED** |
| 运行资产 | 分析器代码/运行命令/sha 未存在，服务器本地文件未以本冻结版本逐字节核对 | **NOT EXECUTION-READY** |

## 2. 剩余审查风险，不得沉默

1. **研究已非盲预注册**：原 Stage R 含已公开的 `C(2)`、整体 hazard 与 24 个 event 的统计结论，Stage 2B 才选 SAME/k=2 和风险集最低 12 的报告纪律。因此所有“提前冻结”只相对**尚未批准的新分析**成立，不能声称结果未知的研究设计或独立评估。
2. **参数族是标准方法**：Beta-Binomial 本身非本项目算法创新，模型有效并不证明 PAEG 的 evidence authority 新颖。N1 算法主张始终 `NOT_ESTABLISHED`。
3. **统计误差与过拟合**：LOEO 训练折高度重合，简单固定预测的 bootstrap 不传播完整估计不确定性；24 个事件、任务分布不均（P 全 t9），结论可能不稳定。即使未来平均 Brier 正向也只可输出内部回顾性观察。
4. **预定义功效未得到保证**：主风险集最低 12 来自未作功效证明的设计性报告纪律。任何显著性门/准确最小试数/物理安全概率都没有被验证或冻结。
5. **随机数实现未指定**：仅固定 bootstrap 次数与 seed，未提供 RNG 引擎和分析器源码，跨运行环境完全相同的重采样索引不能据此保证。后续如获准实施，执行前必须记录脚本 SHA、RNG 引擎、库版本及冻结协议一致性；如果该选择改变统计推断行为，需走单独 deviation 审批，不能直接改 v1。
6. **报告措辞存在定性界限**：协议中“区间过宽/训练不确定性太大”仅允许更保守地标记 `INCONCLUSIVE`，**绝不可依据临时选择的数值阈值宣称 `SUPPORTED`**。如果使用者认为这些条件足以改变正式判决，则必须在执行前申请 v2 协议审查；执行者无自行补门槛的权限。
7. **身份锁定并非 GitHub 分支保护**：Git commit/blob 提供内容地址身份，不能证明仓库禁止 force-push；后续只认本报告所列 immutable SHA 地址。如果分支历史发生改写，冻结协议数据不可查/不一致，则立即 STOP，不得自动重绑最新 HEAD。

## 3. Stage 2D 之前必须做的动作（尚无授权）

- 检查服务器上实际读取的文件与冻结 Git blob SHA/基线 commit 的一致性（输入不同立刻 STOP）；
- 单独审阅并创建**符合 v1 的研究离线分析器**，明确 Beta-Binomial log marginal、LOEO fold、风险集与 Brier，审计脚本哈希/执行环境/RNG；本轮**没有写分析器**；
- 按规范明确 result audit、failure/deviation 日志及负面结论模板；
- 用户必须**另外明确批准 Stage 2D 的纯离线统计运行**，才能读取 outcome 值、拟合、估计或画新图；
- 任何 VLA/rollout/在线接线、Stage R §36 解禁、S1-DEV0 仍在 STOP。

## 4. Final gate

- `PROTOCOL_FROZEN_FOR_RETROSPECTIVE_INTERNAL_ANALYSIS` — **YES**
- `INPUT_VERSION_PINS_RECORDED` — **YES (Git SHA-1 metadata; local bytes unverified)**
- `METHOD_NEW_ALGORITHM_ESTABLISHED` — **NO**
- `STATISTICAL_RESULTS_AVAILABLE` — **NO**
- `READY_TO_RUN` — **NO**
- `STAGE_2D_AUTHORIZED` — **NO**

**Stage 2C 自检收官后不需修改已冻结主文件；若将来发现规则实质歧义，需要新批准的 v2 与可追溯偏离记录，不能在 v1 上覆盖改写。**
