# H0 · Stage2I 全语料 D2-A0 逐次 pick 结构资格 Gate

> 2026-10-09 · **源码级审查 + 只读结构检查器交付；服务器真实数据扫描未执行。**
>
> 接续 `8d48127` 的 Stage2H，结构检查器在 `analysis/harness_h0/h0_oe_stage2i_structure_scan.py`。  
> 仅查阅 GitHub 跟踪源码。无法读取服务器 `logs/stageR_collect` 目录及私有 `states.json` / `stageR_trace.jsonl`，所以本报告**不能报告真实全语料 pick 配对数量、类别分布或 A0 性能**。
>
> 研究边界不变：Stage R §36 HARD STOP、S1-DEV0 ON_HOLD、Stage2C 冻结协议、Stage2D 历史结果、Runtime/Evolution 不授权。

## 0. 独立裁决

**`STAGE2I_SOURCE_GATE_PREPARED / SERVER_SCHEMA_CENSUS_PENDING / A0_STILL_NOT_AUTHORIZED / SCIENTIFIC_NOVELTY_NOT_ESTABLISHED`**。

1. Stage2G 的“187 个 episode 目录在盘”是 episode 级**资产存在性**；并未证成 187 个可用 `pi0_pick`，或任一数目的 **逐次工具返回 ↔ 同技能特权测量** 成对样本。
2. 当前唯一有界评价对象仍为 **A0: `pi0_pick.result.success` vs `IN_SKILL_ACQ_AUDIT` 的回顾性同技能判据一致性**。这里的特权物理参考来自对应技能执行期间，严格**不是**工具返回后的未来抓握保持。
3. 已交付**只读、无标签统计**检查器，用于核验 (episode_dir, step_idx, skill) 联结、工具结果字段、每个 chunk 的 meas、末端 final_meas、相对顺序、重复键、缺失等；当前没有执行服务器扫描。
4. 即使结构完备，也不能自动 GO：**`pick.result.success` 正负两类是否都在最终 eligible-pick 集合存在**，目前没有被合法读取，必须继续记 `CLASS_SUPPORT_NOT_VERIFIED`。只有另获授权才可做结果值资格审查或 A0 数值评价。
5. H0 的可验证方法增量仍主要是栈内数据测量学（A0），没有已成立的 Embodied Harness 方法创新。若不重视该定标需求，**停止 H0 数值阶段也是合理裁决**。

## 1. 源码审查：结构对账必须比“文件在盘”严格

| 联结链 | 源码依据 | 对 A0 的约束 |
|---|---|---|
| 采集样本框 | `scripts/stageR_collect.py:47-68,304-426` | task=3/5/9、seed 121-190；停止配额、infra retry 和并发会影响最终 episode 清单。检查器只处理 ledger 的 episode_dir，并**不按 outcome classify 筛样本** |
| 真实决策时返回 | `robots/libero/toolkit.py:59-111`；`robots/libero/tools.py:201-270,1140-1157` | `states.json` 的 `command.action=pi0_pick`、`result` 原件是 D2 对象；`result.success` **仅检查字段是否存在，绝不读值** |
| rtrace 技能边界 | `rpent/utils/rtrace.py:100-135` | `step_begin` / `step_end` 按 step_idx+skill 精确配对；`step_end.success` 是通用 `bool(result.get('success'))`，**普通原语缺该字段也会被写为 False**，禁止把所有 step_end.success 当作 pick 标签 |
| chunk 特权测量 | `rpent/utils/rtrace.py:138-159` | 逐 pick chunk 的 `meas` **在对应动作执行前取样**；尾部 `final_meas` 对应技能执行末状态，绝不能把预动作测量误算为执行后 |
| 仪器失败与日志完整性 | `rpent/utils/rtrace.py:37-41,76-97,100-159` | `_meas_now` 异常可返回 None；`_CTX['broken']` 的 fail-safe 会静默停用后续仪器。存在 states.json 与 trace.jsonl **不足以证明**全部 chunk meas 有效 |
| 工具判据/终局共享依赖 | `robots/libero/tools.py:230-249`; `scripts/stageQ_rt.py:223-260` | pick 可在 `episode_terminated` 路径镜像官方成功，ACQ-like 参考也允许 `check_success` 直接成立；可能共享同一任务谓词，不能将其一致性包装成“独立物理证实” |

**来源等级说明**：上述代码路径和条件是已读 GitHub 源码可直接验证的事实；“187 目录在盘”及“24 R1 asset 完整”来自 Stage2G 的**服务器回传审查**，本轮未重测。

## 2. 已交付扫描器：只输出结构计数

路径：`analysis/harness_h0/h0_oe_stage2i_structure_scan.py`

它将：

- 只读取 ledger 的 `episode_dir` 字段，去重并核对各目录的 `states.json` 与 `stageR_trace.jsonl`；
- 从 `states.json` 按 `command.action == pi0_pick` 提取每次工具调用的 **key existence**，包括 result/diagnostics 所需键；
- 在同 episode 同 step_idx 上配对 rtrace `step_begin`、`action(kind=chunk)` 和 `step_end`，核查 chunk_idx 连续、每个 chunk 的 `meas` 键存在、final_meas 键存在、时间戳非递减；
- 只在终端输出聚合的结构计数、最多 12 条匿名索引级缺陷样例与结构 Gate；**不展示 episode 路径、不打印标签或物理数值、不写入原始目录或新结果文件**；
- 不读取 `result.success`、`check_success` 或 `episode_terminated` 的**取值**。解析完整 JSON 文档不可避免地将源值加载进内存，但算法不访问这些判定字段的值、不基于它们筛选、分组或统计。

**检查器不具备**：证明 `check_success` 为独立判据；证明物体位姿目标字段完整可构造；验证 true/false 两类都有；生成 A0 一致率、FPR 或性能估计；执行 rollout。

可在服务器执行一次结构检查：

```bash
cd /workspace/yjx/workspace/RPent
git pull --ff-only origin research/pre-ovpm-20260905
python analysis/harness_h0/h0_oe_stage2i_structure_scan.py --repo-root /workspace/yjx/workspace/RPent
```

回传只需扫描器输出的 `gate`、`counters`、`examples`，无需复制任何原始 outcome、个人信息或 sim 物理状态。

## 3. Gate 的精确含义

| Gate | 当前状态 | 后续判定 |
|---|---|---|
| **S0** GitHub 源码来源与真实 D2 面 | **PASS** | `_step` 先取 result，后 dump 并返回 Planner |
| **S1** 已有服务器全语料路径资格 | **Stage2G 报告称存在** | 不能替代逐 pick 配对扫描 |
| **S2** 全 corpus 逐 pick schema + 时间顺序 | **SERVER_PENDING** | 完整方可继续；缺失、重复、混臂或仪器中断须 HOLD/STOP |
| **S3** 可计算明确 ACQ-like 参考 | **CONDITIONAL** | 另须有目标物体位置/EEF字段对齐，且确认为合法研究真值，不被 planner 使用 |
| **S4** 正负两类与被审计样本框 | **NOT_VERIFIED** | 结果值不可在本轮读取；结构 PASS 也不能自动宣称二分类可评估 |
| **S5** 独立时间后验 STABLE / 自然恢复因果 | **NOT_SUPPORTED** | Stage2H 已说明不能由 same-skill `final_meas` 替代 |
| **S6** 方法创新/Runtime 资格 | **NOT_ESTABLISHED / NOT_AUTHORIZED** | A0 最多是单栈回顾性判据一致性，不能升级系统权限 |

### 是否值得实际计算 A0？

此阶段不应提前许诺肯定收益。最强的可能结果是：“在有限的 vanilla collect 策略、任务和样本框内，原工具形态学成功判据与同技能取得契约存在多少一致或分歧”。这值得做的前提是**有明确的物理证据质量工程决策要由该数字支持**。若目标是具身 Harness 方法创新、跨策略泛化或纠正决策后持握失效，A0 单个描述性实验不能回答，应优先 **STOP 本分支而转向有独立可证伪机制的研究问题**。

## 4. 本轮执行与冻结边界

- 已执行：GitHub 源码及先前研究审查复读、结构扫描器编写；服务器真实数据**未扫描**，A0 数值统计**未执行**。
- 允许下一动作：在拥有原始 episode 的服务器上运行只读结构扫描器；它仍**不授权**后续 outcome/类别统计。
- 明确禁止：直接运行 A0 绩效比较、重新定义 Stage R 冻结标签、通过 `check_success` 通道接线 Runtime、启动 VLA/训练/rollout、重新评估冻结 Stage2D 结论。
- 历史审查报告保持原样，不静默修改；本报告补充实际可操作的 schema Gate，并不等于已收到服务器结果。

**最终：`STAGE2I_SOURCE_AND_SCANNER_DELIVERED / SERVER_SCAN_NOT_RUN / A0_PAIRED_ELIGIBILITY_UNKNOWN / H0_STOP_IS_DEFENSIBLE`。**
