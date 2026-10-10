# RPent · P1 Module Lab：用已有 206 次 Pick 做实验驱动的方法搜索

> **类型**：L1 既有数据离线实验，`CODE_READY / SERVER_RESULTS_PENDING`（2026-10-10）。
> **执行**：`python3 -m unittest discover -s analysis/research_context -p 'test_p1_offline_module_lab.py' -v && python3 analysis/research_context/p1_offline_module_lab.py`
> **源码**：`analysis/research_context/p1_offline_module_lab.py`。只读取既有 `artifacts/research_package_a/EERD_A_{online_eligible,audit_only,reconstruction_metadata}.jsonl`，单独输出 `artifacts/p1_module_lab/module_lab_v1.json`。不改原 A0、Stage R、DEV0、在线策略，不仿真、不训练大模型。

## 从问题出发，不预设“视觉模块一定有用”

已验证的基线事实是历史 A0 同技能 FGONLY **代理**对照（来自服务器，206 nonterminal Picks），不是最终物体持握标签：

| 冻结原始工具 `success` | FGONLY POSITIVE | FGONLY NEGATIVE |
|---|---:|---:|
| True | 101 | 2 |
| False | 56 | 47 |

原 Tool 的 FGONLY proxy raw agreement = 148/206=71.84%，balanced accuracy ≈ 80.12%；Always-True 的 raw agreement=157/206=76.21%，但 balanced accuracy=50%。由此实验不能只看 raw accuracy，否则会偏向永远接受。

**实验假设**：工具对 FGONLY 的部分漏报，可能来自固定开度/提升规则的信息组合方式；调整合法信号的位置和 AND/OR 组合，能改善**同技能运动代理的一致性**，同时不明显增加在代理 NEGATIVE 上的接受数。这个结果即使成立，也**不意味着物体真实持握率或 Harness 恢复收益提高**。

## V1 一轮实验：真实运行后用结果淘汰模块

**固定 13 arms（先定义，不根据结果修改）**

| 模块变量 | 固定对照 |
|---|---|
| 基准与常数 | 原 `tool.success`、Always-False、Always-True |
| 单信号位置 | `min_gripper_opening` ≤ 0.060m、≤0.0035m；`final_gripper_opening` ≤ 0.0035m；`peak_lift_m` ≥ 0.050m |
| 加入位置与融合 | gap0.060 AND lift0.050；gap0.0035 AND lift0.050；gap0.0035 OR lift0.050 |
| 与工具反馈的先后关系 | flag OR gap0.0035；flag OR lift0.050；flag OR (gap0.0035 AND lift0.050) |

阈值来自历史冻结 D2 和 VE-v0.1 的**事先存在的规则**，不在这次评测结果上调参。另按事先编码的 6 gap × 4 lift × AND/OR = **48 个非选择性敏感性配置**生成参数表，记录失败区，不按“最高分”宣称获胜。原 EERD 的 audit-only `reference` **只进入评价/离线模型族选择**，`predict()` 只接收 A-online `tool_report` 真实决策字段，绝不引用物体 sim pos 或 audit 真值。

**直接给出科学反馈的读数：**

1. 所有 arms 输出 FGONLY proxy 2×2（TP, FP, FN, TN），balanced accuracy、proxy 误接受率、proxy 正例召回、abstention，以及相对原工具反馈的 ΔFP、ΔFN。
2. 按 3 个 LIBERO task 分层展示，避免只靠总体数掩盖方向反转；按原 episode 聚类对固定模块与原 flag 的 Δbalanced accuracy 做 1000 次配对 bootstrap 描述区间。另单列四种 flag×FGONLY 不一致/一致子群的 `min_gripper_opening/final_gripper_opening/peak_lift_m` 分位分布（只输聚合，无 episode ID），观察漏报为什么发生。
3. **Leave-One-Task-Out 模块搜索**：每次仅用另外两个 task 的**代理标签**在上述固定模块族中挑一项（train 内 balanced accuracy 最大、proxy false acceptance 次小、缺失次小），在未参与挑选的第 3 个 task 上评分。三个 held-out task 输出和 pooled 评价都单独列示。这是纯离线选择、不训练模型参数、不允许写回 Runtime；三个任务也不足以声称广义泛化。
4. 对原工具返回 False 的 103 条，给每一组模块计算实际 `FGONLY+ 漏报中被补救` 与 `FGONLY− 原正确拒绝中新增误接受`，避免用提升“召回”隐藏风险损失。
5. 对缺失/NaN 信号显式 `ABSTAIN`，汇总分母时默认映射到 RETRY（False），避免用“有输出的部分”美化准确率。

**评测边界**：FGONLY 是**技内某时刻物体抬升+跟随代理**，与 Tool 的 `peak_lift` 在运动构念上可能有重叠；所以再好的一致性也可能来自可见运动的重复测量，不是独立物理接触证据。历史数据为配额停止的 observational collection，跨 task 的标签分布/参考同源，留任务测试亦非未来控制因果结果。

## 运行 Gate 与研究策略

- **Baseline Integrity**：EERD A-online/A-audit/A-metadata 均235行、join 唯一、A 主 206、原 flag/reference 对照必须仍为 TP101/FP2/FN56/TN47；不一致 STOP，**不能修改旧数据凑指标**。
- **Required**：合成测试全部通过；原始源文件 SHA 保留；至少一个非 Tool 的固定模块在真实数据上有覆盖率/FP/FN/任务分层反馈。若模块性能不确定，照样报告失败。
- **保留模块的探索性参考（不构成 confirmatory GO）**：在 FGONLY proxy balanced accuracy 有正 Δ，误接受数没有显著膨胀；三个 task 不出现系统性反向；结果对阈值轻微扰动不完全崩溃。如果最佳模块的 FP 数变大，就单独保留 trade-off 曲线，**不要只引用召回上涨**。
- **STOP 的价值**：如果工具+gap/lift 组合无法显著减少 proxy 不一致、只有后验调阈值才见增益、或 leave-one-task-out 方向翻转，停止继续堆开度规则，下一科学问题变成**哪些额外可观测视觉证据实际包含独立信息**；再按独立同步目标持握标签合同设计新的有界 L2。
- **样本失败归因**：先看 flag=False 且 FGONLY+ 的 56 个在哪些 task、低开度/高 lift 区域聚集，和 flag=True/FGONLY− 的 2 个如何受规则影响。新工具只能输出**脱敏聚合统计**，不能外传私有轨迹/标签。
- **下一轮只根据实验结果提出一个最小改动**，不要无证据地新增多 Agent、世界模型或大视觉网络。

**状态**：`PROPOSED_L1_EXPERIMENT_IMPLEMENTED / SERVER_TESTS_UNRUN / P1_NEW_SIM_HOLD`。只有接到真实服务器读数之后才填写模块排名、残差失败组和具体下一次算法改造。
