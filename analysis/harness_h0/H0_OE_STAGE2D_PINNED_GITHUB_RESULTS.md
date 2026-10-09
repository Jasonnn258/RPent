# H0 Direction 1 · Stage 2D Frozen-GitHub Offline Reproduction

> 2026-10-09 | **用户明确批准 Stage 2D 纯离线结果分析**。
> **状态：PINNED_GITHUB_RESULT_REPRODUCED / SERVER_LOCAL_PREFLIGHT_PENDING**。
> 本报告基于 Stage 2C 冻结协议 `H0-OE-STAGE2C-20261009-V1`，没有修改冻结文件、Stage R 数据或运行任何 VLA、仿真环境、训练、在线 Gate。
> **特别限定**：此轮真实结果是在隔离 Python 环境中调用**经 Git Blob SHA 校验的 Stage 2D 分析器 Python 函数**计算，输入由 GitHub 的**冻结版本** CSV 经核验后转换为每事件 8 位同臂 outcome 序列；**没有在用户服务器执行 `--preflight` / `--run`，因此不能冒充服务器本地字节复算。**

## 1. 证据链与可复现性

| 资料 / 执行 | 固定身份或证据 | 本轮真实状态 |
|---|---|---|
| 冻结协议 | `H0_OE_STAGE2C_FROZEN_PREREG.md`，创建 `118d98c`，Git blob `97dc0bc93bae857620554a7c2571c5b0b55b5528` | READBACK MATCH；原协议未修改 |
| 输入 Git 仓库基线 | `10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a` | 使用精确 commit，而非移动的 HEAD |
| 冻结 cohort manifest | `3972e58f5b356f141fc46c4c9e7da600eb723cfe` | GitHub fetch_file `sha` 校验通过 |
| SAME 192 行 | `966dced03ba26f3357bbc7d7f2f1c31e547e162c` | SHA 和 24×8 唯一 trial 索引通过 |
| RESAMPLE 192 + NATURAL 96 行 | `919906ce8f6c7db38dbf226f41210793a6b9e351` | SHA 和分臂索引通过，NATURAL 不用于模型 |
| 冻结 v1 离线分析器 | `scripts/h0_oe_stage2d_offline.py`，Git blob `e8916f3f58084f186715a7de00cd450f060592c7` | 远端读回与本地测试字节 SHA 完全一致 |
| 合成回归测试 | `scripts/test_h0_oe_stage2d_offline.py`，Git blob `824c96be60038ee2a06f427646e653b2069c8794` | **6/6 synthetic-only PASS**，包括前缀公平性、事件键 STOP、M1、Brier、bootstrap |
| 冻结试次转换一致性 | 24 event 依冻结 `ord` 排序，仅截取 SAME/RESAMPLE 的 `stable/acquisition` 8 位序列，序列格式 `id ord task SAME SAME_acq RESAMPLE RESAMPLE_acq\n` | 独立重新从 GitHub pinned CSV 计算 64-bit FNV-1a `f10b85a6cbd11380`，与 Python 使用的中间序列完全一致（长度 1099 字节）；这是**搬运校验**，不替代原 CSV Git SHA |
| Python 环境 | CPython 3.13.5，标准库数学/随机数 | 本轮实际使用 |
| 用户服务器本地数据/脚本字节 | 原 Stage 2D `--preflight` 必须检验 Git blob | **NOT_RUN；仍需服务器侧确认** |

**执行路径的透明说明**：GitHub 工具先在固定 commit 读取/验证三份 CSV 的 blob SHA，检查 24 个 R1 event 和两臂 8 次结果对齐；为了避免未经授权进入服务器，将严格限定的 outcome 二值序列以只读中间表示传入隔离 Python，并调用已经发布、测试 SHA 一致的分析器内 `run_analysis`，执行冻结的 LOEO、M0/M1、Brier 与 10,000 次固定预测描述性 bootstrap。**没有调用正式 CLI 入口 `--run`，故服务器 preflight 审计仍 OPEN**。

## 2. 唯一主比较 OE2a（SAME，k=2→Y3）

| 指标 | 离线回顾性复算 |
|---|---:|
| R1 总 event | 24 |
| 前两次 SAME 均 `stable=0` 的主风险集 | **12** |
| 主风险集任务构成 | t3 = 1；t5 = 5；t9 = 6 |
| 主风险集第三次 SAME `stable=1` 的 event | 2 / 12（描述性观察） |
| M0 LOEO 平均 Brier loss | **0.1608288064** |
| M1 LOEO 平均 Brier loss | **0.1479166667** |
| 主要差值 `mean(M0 loss − M1 loss)` | **+0.0129121397** |
| 10,000 次固定 OOF 成对 event bootstrap 描述性 2.5%–97.5% 区间 | **[-0.06156028, +0.06409827]** |
| M1 mu/tau 网格边界 fold 数（SAME） | 0 |
| 冻结符号报告标记 | `M1_LOWER_OBSERVED_BRIER_IN_RETROSPECTIVE_COHORT` |

主风险集恰好是冻结报告纪律的**最低 12**个 event。差值方向略微有利于 M1，但描述性区间**跨越零且很宽**；LOEO 训练折共享 23 个训练事件、bootstrap 未传播重拟合误差，因此**不能给出严格的置信覆盖保证或“模型显著优于基线”结论**。

**科学解读：非常有限的回顾性优势信号；统计证据不足，不能声称 N1 算法 GO。** 该分析在已发表过汇总结果的 Stage R 数据上进行，属于内部回顾验证，不是外部独立测试。

## 3. OE1a 次要：同源 ACQ/STABLE 嵌套契约分歧

| 冻结臂 | ACQ 接受率 | STABLE 接受率 | 同源契约分歧 ACQ−STABLE | 条件分歧 P(STABLE=0 \| ACQ=1) |
|---|---:|---:|---:|---:|
| SAME | 64.58% | 30.21% | **34.375 pp** | 53.23% |
| RESAMPLE | 69.79% | 32.29% | **37.50 pp** | 53.73% |

这些数字符合旧 Stage R 终报中已公布的 ACQ−STABLE gap（四舍五入后的 +34.4pp、+37.5pp）；它们**不是独立未来真值的假阳率，也不是新独立发现**。源码已证明 `stable⇒acquisition`，两者来自同一仿真 cps，不能充当彼此独立的评测器。

## 4. OE3a 探索：不同臂和失败前缀（不可提升为第二主结论）

| Arm | 已失败前缀 k | 合格 event 数 | Brier(M0−M1) |
|---|---:|---:|---:|
| SAME | 0 | 24 | +0.00406 |
| SAME | 1 | 18 | -0.01851 |
| SAME | 2 | 12 | +0.01291（唯一预定主比较） |
| SAME | 3 | 10 | +0.03727 |
| RESAMPLE | 0 | 24 | +0.00129 |
| RESAMPLE | 1 | 20 | -0.01114 |
| RESAMPLE | 2 | 13 | -0.04844 |
| RESAMPLE | 3 | 7 | +0.07065 |

**方向跨 k 和臂并不一致**，且多个较大的差值对应更小的风险集。这些曲线均为同一批事件的探索性比较，不应用于事后挑最好 k 或“证实最小失败试次 n*”。所有结论仅限冻结 `S_pre` 重建尝试，不能外推真实自然 `S_post` 恢复。

## 5. 独立科学裁决

- **方法一致性**：冻结单一主问题、LOEO、同等前缀信息 M0/M1、M1 固定 mu/tau 网格、Brier delta 和无确认性 p 值，均按 v1 运行的**纯函数路径**实现；模型、真实数据和源码的所有 SHA 证据见 §1。
- **观察性差值**：主 `+0.01291`，但描述性区间 `[-0.06156,+0.06410]`，不能主张稳健预测收益或正式“通过”。
- **原创性**：混合 Bernoulli/Beta-Binomial、事件级 LOEO 和条件后验是成熟统计；本结果**未验证**一个新的 VLA/Harness learning/repair 算法。N1 algorithm novelty `NOT_ESTABLISHED`。
- **因果与可见性**：`causal_grade=UNIDENTIFIED`；OE1b 独立物理 false-acceptance `NOT_IDENTIFIABLE_ON_AUDITED_SOURCES`；离线真值不可经 Runtime/Evolution Gate 获得执行授权；Stage R §36 Hard STOP、S1-DEV0 ON_HOLD 完全不变。
- **执行资格**：`PINNED_GITHUB_RESULT_REPRODUCED`；服务器真实字节 preflight `PENDING`。用户可运行 `H0_OE_STAGE2D_RUNBOOK.md` 的 `--preflight` 和 `--run` 做独立服务器确认。若本地 hash 不一致，必须 STOP，而非改 frozen v1 或覆盖文件。
- **后续研究价值**：此类实验可明确“连续失败的后验更新很多是事件异质性的条件选择解释”，但当前只是小样本示例，并不足以证明需要新物理 Harness gate。研究应在未来授权时聚焦可**合法观测**且与 sim truth 分离的信号与新评测集，而非仅增加统计门槛。

## 6. 本次变更边界

本报告为研究文档增量；**没有修改**冻结 Stage 2C 文件、Stage R 实验脚本/数据、checkpoint、DEV 原件或 S1；**没有**启动新 rollout、仿真环境、VLA、训练/控制器。此报告中的数据是**经用户 Stage2D 授权的既有结果离线复算**，不是新的物理实验，也不是服务器实测结果。

**最终标记：`STAGE2D_PINNED_GITHUB_REPRODUCTION_COMPLETE / SERVER_BYTE_PREFLIGHT_PENDING / NO_NEW_ALGORITHM_ESTABLISHED`。**
