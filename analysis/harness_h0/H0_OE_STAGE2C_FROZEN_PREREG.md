# H0 Direction 1 · Stage 2C — FROZEN RETROSPECTIVE ANALYSIS REGISTRATION (v1)

> **Protocol ID:** `H0-OE-STAGE2C-20261009-V1`
>
> **状态：FROZEN_PROTOCOL / RESULTS_NOT_RUN / EXECUTION_NOT_AUTHORIZED**
>
> **用户授权**：2026-10-09 明确批准“Stage 2C：正式预注册审查与冻结，不运行统计或实验”。本文件是**在 Stage R 数据已采集、终报已公开之后、下一轮分析之前**对新分析方案作出的冻结；属于 **retrospective analysis registration / pre-analysis freeze**，绝不可称 outcome-blind / pre-data-collection preregistration，也不能将旧 Stage R 数据宣传为 independent held-out evaluation。
>
> **来源基线（锁定）**：RPent `research/pre-ovpm-20260905`，进入 Stage 2C 前的 commit `10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a`。本文封存后以其 Git Blob SHA + 创建提交 SHA 标识具体版本；见另建 `H0_OE_STAGE2C_FREEZE_MANIFEST.md`。**冻结不授权任何结果统计、功效计算、模型拟合、分析脚本运行、环境 boot/rollout、训练、在线决策/Agent/Verifier 或 S1。**

## 0. 阶段科学裁决与承诺范围

唯一正式比较是：对于 **Stage R 冻结 R1_COHORT 中 SAME-ACTION 前两次独立重建尝试均未 STABLE 成功的事件**，M1（事件异质 Beta-Binomial）在预测第三次结果的**内部回顾性 Brier loss**上，是否比公平使用相同已知前缀的 M0（共享 Bernoulli 概率）更低。

本注册的主结论只能写成：
- `M1_LOWER_OBSERVED_BRIER_IN_RETROSPECTIVE_COHORT`
- `NO_OBSERVED_BRIER_ADVANTAGE`
- `INCONCLUSIVE / DESCRIPTIVE_ONLY`，或 `STOP_DATA_OR_METHOD`

**禁止**由任何正面结果推出“序列失败导致物理状态退化”“真实 S_post 在线恢复更安全”“Skill edit 有修复能力”“PAEG 新算法创新已证明”“已具备 Runtime/Evolution 授权的物理证据”。标准 Beta-Binomial 是已有统计模型，不自动带来新的具身智能算法创新。

## 1. 数据资产和来源锁定（只记录 Git SHA，不读取结果）

**仓库 commit**：`10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a`。以下是从该 commit 下 GitHub file API 只读取**对象 SHA 元数据**记录的 Git **blob SHA-1**，不是 SHA-256，也不是服务器本地当前磁盘内容的散列；计算模型不允许用之后的分支文件静默替换：

| 锁定文件 | Git blob SHA-1 | 用途 |
|---|---|---|
| `analysis/stageR_manifest.csv` | `3972e58f5b356f141fc46c4c9e7da600eb723cfe` | 冻结事件 ID、role、ord、任务分层 |
| `analysis/stageR_same_action_rollouts.csv` | `966dced03ba26f3357bbc7d7f2f1c31e547e162c` | 唯一 primary 试次与 outcome |
| `analysis/stageR_resample_rollouts.csv` | `919906ce8f6c7db38dbf226f41210793a6b9e351` | secondary RESAMPLE 与 NATURAL 结构辨识 |
| `analysis/stageR_failure_events.jsonl` | `74e15deb7c42ce8306d4752c7d4401b7954d824e` | 事件 index/provenance；无 outcome 训练信息 |
| `analysis/stageR_event_probabilities.csv` | `5ec8a3c0a9044410ebc25cc36b60af1b4f4a069e` | **审计排除**：既有结果派生文件，禁止作特征/真值/模型选择依据 |
| `analysis/stageR_prereg.md` | `0eba5d6098bbd61703d59451311525ebe947d6f1` | Stage R 冻结定义/原 Hard STOP |
| `analysis/STAGE_R_FINAL_REPORT.md` | `96f58e0c40982780d41c8593bbbab9c865ea1375` | 已公开结论、deviation 与历史来源 |
| `scripts/stageR1_run.py` | `3afb9c8334c130d4f3866f1dfcd972b0ec0e6c2f` | trial 执行次序及写入来源（只读） |
| `scripts/stageR_rt.py` | `526f3aaff8623c737dc8e8675ec583eaadc0c3aa` | 重建/测量来源（只读） |
| `scripts/stageQ_rt.py` | `356901453e0d4715196424709c617927e7088875` | 冻结 STABLE/ACQUISITION 契约（只读） |
| `analysis/harness_h0/H0_OE_STAGE2B_ANALYSIS_PLAN_CANDIDATE.md` | `8da25eb52d03d3e3d1db6e5417f4323d681e5a56` | 冻结前未执行的候选方案 |
| `analysis/harness_h0/H0_OE_STAGE2B_GATE_REVIEW.md` | `db749ebb629c464aace9367e3534a36dcb2d9f46` | 冻结前独立规范审查 |

**GitHub 来源锁定并不验证服务器本地当前文件**。以后如另获准执行，**先只读**核验数据从该 Git commit/对应 blob 提取且与实际读取字节一致；不同则 `STOP_INPUT_HASH_MISMATCH`、不得直接替换、下载或“修复”数据。被 gitignore 的 `analysis/stageR_trial_checkpoints.jsonl` 是先前来源审计资产，**不是本协议模型的必需输入**；其额外 DEV 记录亦绝不可加入正式 cohort。当前没有统计分析程序，因此 **analysis-script hash = NOT_CREATED / NOT_FROZEN**；未来另行获准实施时，必须先审查程序是否逐条遵循本文，并在第一次运行前记录脚本 SHA/版本和运行命令，**无须且不允许因此修改本冻结协议**。

## 2. Cohort、结局、独立单位和试次合法性（固定，不得调参）

1. **仅**按 `stageR_manifest.csv` 的 `role == R1_COHORT` 选择 **24 个**事件；key=`(event_id, arm, trial)`；缺 role、重复 key、任务/seed/t0 与 manifest 不一致均触发 `STOP_DATA_INTEGRITY`。
2. 正式臂：`SAME` ×8、`RESAMPLE` ×8；`NATURAL` ×4 只作已公开的 `S_post` 描述，不输入任何主要/次要预测统计；`R0_DEV` 8 个事件**全部排除**。
3. 额外 checkpoint 四键 `r09/SAME/1,2,3` 与 `r12/SAME/1` 属 `R0_DEV`。冻结 `STAGE_R_FINAL_REPORT.md §9 dev-r1-fix` 已记录首次 R1 队列切分错误、额外执行四条 DEV 并保留 CPS；R1 的 480 个 CSV trial 已与 checkpoint 唯一键全对齐。不得清洗、删除或改写源文件。
4. **Primary**：同一 trial 的 `stable`（Stage Q/R 冻结 `STABLE_RECOVERY`，包含 `check_success` 支路），记为 \(Y_{eaj}\in\{0,1\}\)。**Secondary**：`acquisition`，记为 \(A_{eaj}\)；源码的 `stable⇒acquisition` 说明是同源嵌套契约。均来自仿真测量/科研真值，不是已证明合法的 online physical outcome。
5. 完整性：正式 R1 每事件每臂必须有 `trial=1,\ldots,8` 且 `stable/acquisition` 仅是合法二值、无缺失；入组依冻结的稳定 FALSE_GRASP 原始条件，不把初始失败重新算作第 0 trial。模型跨折的独立/不确定性单位为完整 `event`，不是单个 attempt。
6. Infra：遵从 `stageR_prereg.md §11` 原始规则；若以后实际数据验证发现与冻结终报“R1 0 infra”不符，则 `STOP_DATA_OR_INFRA_DISCREPANCY`，不得临时排除“表现差”的事件或启用新 rollout 补齐。模型不会自己重新标注 infra 类型。

## 3. 唯一 primary：SAME 前两次失败之后的第三次 outcome

冻结选择：
- arm=`SAME`；
- prefix 长度 `k=2`，只把 \(Y_{e,SAME,1}=0\) 且 \(Y_{e,SAME,2}=0\) 的事件纳入**主风险集** \(\mathcal E_2\)；
- 目标严格是 \(\,T_e=Y_{e,SAME,3}\,\)，**不允许用 Y3 或之后结果定义风险集**；
- 估计/预测解释域为“进入 Stage R 稳定 FG cohort、在冻结 `S_pre` 下两次 SAME 未稳定成功的事件再独立重建的第三次结果”，不外推自然在线 `S_post`；
- 主风险集事件数 \(|\mathcal E_2|\) **本轮不得从 raw outcome 再算**。提议的最少报告纪律 \(|\mathcal E_2|\ge12\) 源自 Stage 2B 候选；**Stage R 已发布 k=2 的总体曲线**，故这个阈值并非“在未知结果前盲选”、没有功效保证，严格只限制报告措辞，不能充当显著性保证或暗示独立发现。

## 4. M0：共享成功率的 Bernoulli baseline（公平消费前缀）

对每个 LOEO 留出事件 \(e\)，其余 23 个正式 R1 事件的 SAME 全 8 次结果构成训练资料。模型假定所有事件共享 \(q\sim\mathrm{Beta}(1,1)\)；在训练结果和留出事件**已知**两次失败之后，预测

\[
S_{-e}=\sum_{j\ne e}\sum_{t=1}^{8} Y_{j,\mathrm{SAME},t},\qquad
\widehat p_{0,e}=\frac{1+S_{-e}}{2+8\cdot23+2}.
\]

分母最后的 `+2` 是留出事件预测时可见的失败前缀；只更新共享 \(q\)，**未看 Y3..Y8**。不更新前缀的 pooled baseline 可以作为额外阅读材料，但不得替换这个 primary M0。

## 5. M1：事件异质 Beta-Binomial 模型与固定训练准则

**候选家族已冻结为分析规范**：

\[
q_e\sim\mathrm{Beta}(\alpha,\beta),\quad
Y_{e,SAME,t}\mid q_e\overset{\mathrm{cond}}{\sim}\mathrm{Bernoulli}(q_e).
\]

\[
\alpha=\mu\tau,\quad\beta=(1-\mu)\tau,\quad
\mu\in\{0.05,0.10,0.15,\ldots,0.95\},\quad
\tau\in\{0.5,1,2,4,8,16,32,64,128\}.
\]

对每个 LOEO fold，仅利用其余 23 个训练事件的 SAME 每个 8 次 `stable` 结果。设其成功计数 \(s_j=\sum_{t=1}^8Y_{j,SAME,t}\)，在以上离散网格最大化

\[
L(\alpha,\beta)=\sum_{j\ne e}
\left[\log B(\alpha+s_j,\beta+8-s_j)-\log B(\alpha,\beta)\right].
\]

Beta-Binomial 组合系数 \(\binom8{s_j}\) 与 \(\alpha,\beta\) 无关，故可以从 grid argmax 略去；不得额外惩罚/按 task 重加权。**在比较允许误差 1e-10 内并列时**，优先**最大 \(\tau\)**，再优先**最小 \(\mu\)**。实现必须使用稳定的 log-beta/lgamma 等数值方法；若无法为某 fold 得到有限最大值，输出 `M1_FIT_FAILED`，**不得**事后改网格/先验/模型救正结果。

对留出事件仅观察前两次失败，在条件 iid 模型下第三次后验预测：

\[
\widehat p_{1,e}=\frac{\widehat\alpha_{-e}}
                      {\widehat\alpha_{-e}+\widehat\beta_{-e}+2}.
\]

此模型已经假设每事件重复重建 trial 条件可交换；**不能**因其预测收益宣称顺序额外信息、真实物理失败状态累积或独立 causality。

## 6. 主损失、折划分及允许的统计说法

- **Evaluation split**：确定性按 manifest `ord` 升序枚举全部 24 个 event，各留出一次，形成 24 个 complete-event LOEO folds。对每个留出事件，训练使用其余完整 23 个事件，不根据留出 Y3..Y8、完整 E/A/P/U 后验类型决定网格或基线。
- 只对 \(\mathcal E_2\) 中的事件评估：
  \[
  \ell_m(e)=(T_e-\widehat p_{m,e})^2,\quad
  \Delta_e=\ell_0(e)-\ell_1(e),\quad
  \bar\Delta=\frac1{|\mathcal E_2|}\sum_{e\in\mathcal E_2}\Delta_e.
  \]
  **正**表示在该回顾性风险集内 M1 平均 Brier loss 较小，**非正**表示本风险集未观测到优势。
- **Report-only bootstrap**：若完整性与最低风险集报告纪律均成立，可对**已形成的**主风险集成对 \(\Delta_e\) 做有放回 event 重采样 **10,000** 次、随机种子 **20261007**，输出 bootstrap 平均差的 2.5% 与 97.5% **描述性百分位区间**。该固定-OOF-bootstrap 无法传播重叠训练集的模型重拟合不确定性，**不得**宣称严格的 95% 频率覆盖、确认性 `p<0.05` 或 nominal power。没有为将来严格再拟合/bootstrap 假设检验冻结任何可执行方案。
- **不设假设显著性检验/α门**。只基于 \(\bar\Delta\) 的符号报告已观察内部回顾性能；区间、有效事件数与 task 构成都需要显式展示，不能用描述性区间的上下界决定“新算法通过”。
- 若 \(|\mathcal E_2|<12\)、出现无法解释的 infra/missing、M1 非有限参数或字段来源不一致，使用 `INCONCLUSIVE / DESCRIPTIVE_ONLY / STOP` 对应状态，**不得**根据 Y3 重新选 k、换成 RESAMPLE 或补录新 rollout。
- 原 Stage R 终报已经披露总体与 h(k)，本次冻结的时间顺序不能创造 blind holdout；**所有正向结果标题必须显式加 `RETROSPECTIVE_INTERNAL_VALIDATION_ONLY`**。

## 7. OE1a：同源嵌套 outcome 分歧（只作为 descriptive）

- 单独按 SAME、RESAMPLE 两臂，以完整 R1 事件统计：
  \[
  d_{e,a}=\frac18\sum_{t=1}^8(A_{eat}-Y_{eat}),\quad
  \bar d_a=\frac1{24}\sum_{e\in\mathrm{R1}}d_{e,a}.
  \]
  在同 trial 的 `stable⇒acquisition` 下，它等于联合分歧率 \(P(A=1,Y=0\mid a,\mathrm{entered FG})\) 的观察版本。
- 条件分歧 \(r_a=P(Y=0\mid A=1,a,\mathrm{entered FG})\) 估计为完整 R1 的“ACQ=1 且 STABLE=0”尝试数除以“ACQ=1”尝试数，若分母为0 → `NOT_ESTIMABLE`；不能称独立 false-positive rate。
- 只作**同源合同差异**描述；已经公开的 `ACQ−STABLE` gap 与这套数据同源，不能作为独立创新证据；不做新的确认性检验或把两种指标当独立代理互相验证。

## 8. OE3a：同一 family 的其余前缀与另一臂（探索、无第二主结果）

- 对 `SAME` 的其余 `k\in\{0,1,3\}`，对 `RESAMPLE` 的 `k\in\{0,1,2,3\}`，每个 `k` 的合法输入为前 k 次全失败的结果，严格未来目标 `Y_{e,a,k+1}`。`k=0` 为无追加失败观测的入组基线。
- 按臂各自单独从另外23个 event 的 8 次对应臂结果训练。M0 预测：\((1+S_{-e,a})/(2+8\cdot23+k)\)；M1 的 \(\mu,\tau\) 网格、LOEO 训练与 §5 相同，但采用对应臂的事件计数，\(k\) 次失败后的预测为 \(\hat\alpha_{-e,a}/(\hat\alpha_{-e,a}+\hat\beta_{-e,a}+k)\)。数据不足输出 `INCONCLUSIVE`。
- 这些折外 Brier/delta 仅为**exploratory descriptive**，不得挑“最好的 k/arm”改写 primary，不统计其“显著性个数”，不得推导准确“最小试数 n*”或 E/P latent oracle。
- 无权使用 NATURAL 的 `S_post` 结果、sim privileged fields 以外推在线物理效果。

## 9. Reporting gate、完整性与禁止的研究升级

| 触发条件 | 预定动作 |
|---|---|
| 输入 blob / 基线 commit 不匹配，或 cohort 非冻结 R1_ROLE | `STOP_INPUT_HASH_MISMATCH` / `STOP_DATA_INTEGRITY` |
| 未按完整 event LOEO，或模型参数使用留出事件未来 Y3..Y8 / ex-post E/P | `STOP_EVALUATION_LEAKAGE` |
| `stable/acquisition` 非法值、原 trial 1..8 不完整、结果与 Stage R 冻结记录不一致 | `STOP_DATA_OR_INFRA_DISCREPANCY` |
| 风险集少于12或训练/置信区间过于贫乏 | `INCONCLUSIVE/DESCRIPTIVE_ONLY`，允许保留明示不足的指标描述，不报告预设“优势” |
| M1 网格完全非有限或数值拟合失败 | `M1_FIT_FAILED`，停止正式 primary 比较并如实汇报 |
| \(\bar\Delta>0\) 且完整性条件满足 | 只报 `M1_LOWER_OBSERVED_BRIER_IN_RETROSPECTIVE_COHORT` + 风险集规模、任务构成、不确定性和局限 |
| \(\bar\Delta\le0\) 且完整性条件满足 | 报 `NO_OBSERVED_BRIER_ADVANTAGE`，不能声称同质模型在所有物理条件都充分 |
| 想把研究标签变成 Runtime STOP 或 Evolution `PROPOSE_REVIEW` | `STOP_OUT_OF_SCOPE`，需要独立合法可消费的物理观测、另行 Stage R §36 解禁及用户授权 |
| 想补做 rollout/统计功效模拟/参数敏感性挖掘/自适应更改主臂 | `STOP_NEW_WORK_NOT_AUTHORIZED` |

**固定报告内容（将来单独获准执行后）**：输入数据 commit/blob 哈希核验、cohort key check、主风险集数量和 task 分布、主臂 LOEO 的 M0/M1 预测损失与 \(\bar\Delta\)、弱描述性区间或无法形成区间的原因、M1 网格边界/失败信息、OE1a 契约分歧、OE3a 探索性曲线、已发布结果关系说明、反证/停止状态、科学创新性限定。**无输出也应提交 STOP 报告，不可静默把负例变成新方案**。

## 10. 冻结后的版本、偏离审计与授权状态

1. **本文件封存时**通过 GitHub 创建独立文件、获取其 blob SHA 与创建提交 SHA，并在独立 `H0_OE_STAGE2C_FREEZE_MANIFEST.md` 记录。之后发现文本笔误、统计方法缺陷或新资料，应**追加另一个审计/deviation 说明**并要求用户再次决定是否发布 `v2`，不得原地修改这份 v1 冻结承诺。
2. 本冻结**不创建分析脚本**。将来 Stage 2D 若另行批准，必须先独立实现符合本协议的分析器，出示源码 SHA 与输入 Git blob 比对，记录运行命令/环境且完成权限 Gate，再允许触及 `stable/acquisition` 数据和计算模型结果；**现阶段没有这种批准**。
3. Stage R 既有 `E14/A1/P5/U4`、`stageR_prereg.md §36 Hard STOP`、S1-DEV0 `ON_HOLD` 均继续。完全禁止新 VLA/env boot/rollout、Recovery/Verifier/Controller/Graph/WorldModel/Skill evolution 机制实现。
4. Freeze verdict = `PROTOCOL_FROZEN_FOR_RETROSPECTIVE_INTERNAL_ANALYSIS`; Execution verdict = `STOP_PENDING_SEPARATE_STAGE_2D_APPROVAL`; algorithm novelty = `NOT_ESTABLISHED`; independent physical reference = `NOT_IDENTIFIED`。

**Signed scope record**：用户在本对话中授权 Stage 2C 的正式协议冻结；该批准仅约束文档内容和后续执行必须遵守的范围，**不是加密电子签名，也不包含统计执行许可**。
