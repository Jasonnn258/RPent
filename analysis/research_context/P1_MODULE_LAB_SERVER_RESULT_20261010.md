# P1 Module Lab v1 · 真实服务器结果与下一轮可证伪假设（2026-10-10）

> **来源**：用户在远程服务器完成 `git pull` 至 `889cc3e`，运行 `test_p1_offline_module_lab.py` **7/7 PASS**，实际 206 个 A0 PRIMARY 上执行 `p1_offline_module_lab.py`；本文全部数值取自用户粘贴的终端 JSON，**本 ChatGPT 未直接运行私有服务器**。私有 `module_lab_v1.json`、完整48格敏感性图和群组细节没有在聊天中回传，不能臆造。
>
> **解释合同**：所有 TP/FP/FN/TN 均相对于同技能 `IN_SKILL_ACQ_FGONLY_V1` **弱代理**，不是物理持握的真实正负例、后续恢复成功率或前瞻控制收益。该代理与 EEF 运动学特征相关，存在参考同源性。

## 真实结果：13 固定模块全面负增益

A0 原 baseline `F0_tool_flag`：206 PRIMARY、175 episodes、task 3/5/9 分别 71/77/58；TP=101、FP=2、FN=56、TN=47，balanced accuracy 0.801248、raw agreement 0.718447，proxy FP rate 0.040816。

| 固定 Arm | BAcc | ΔBAcc vs Tool | TP / FP / FN / TN |
|---|---:|---:|---|
| 原 Tool flag | **0.801248** | 0 | 101 / 2 / 56 / 47 |
| Gap min≤0.060m | 0.591837 | −0.209411 | 157 / 40 / 0 / 9 |
| Gap min≤0.0035m | 0.271611 | −0.529637 | 18 / 28 / 139 / 21 |
| Gap final≤0.0035m | 0.500000 | −0.301248 | 0 / 0 / 157 / 49 |
| Peak lift≥0.050m | 0.728389 | −0.072859 | 139 / 21 / 18 / 28 |
| Gap0.060 AND Lift | 0.769206 | −0.032042 | 139 / 17 / 18 / 32 |
| Gap0.0035 AND Lift | 0.438711 | −0.362537 | 16 / 11 / 141 / 38 |
| Gap0.0035 OR Lift | 0.561289 | −0.239959 | 141 / 38 / 16 / 11 |
| Flag OR minGap0.0035 | 0.563954 | −0.237294 | 113 / 29 / 44 / 20 |
| Flag OR Lift | 0.728389 | −0.072859 | 139 / 21 / 18 / 28 |
| Flag OR (Gap0.0035 AND Lift) | 0.731054 | −0.070194 | 111 / 12 / 46 / 37 |
| Always False / Always True | 0.500000 | −0.301248 | 常数对照，参考原始 JSON |

**实证研究判断**：在这组固定候选中，`success` flag 比单独 gap/lift、AND/OR、简单 fail→continue 补救在 FGONLY proxy **balanced accuracy** 更强。虽然 `Gap0.060 AND Lift` raw agreement=83.01% 高于 Tool 的71.84%，但 proxy FP 从2→17、specificity 下降，说明 **只追求 raw agreement 会误导模块选择**。

原 flag=False 的103次，`Gap0.060 AND Lift` 可以在代理意义上“补救”38个原 FN，但新增15个原 TN 上的错误接受；`Gap0.060` 补救56个也新增38个错误接受。`Flag OR Lift` 补救38个、新增19个错误接受。**这些是 proxy tradeoff，不意味着应该真正执行 CONTINUE。**

## 三任务反差：最值得研究的是 Task 9 的失败条件

用户终端 Leave-One-Task-Out 的原 Tool flag baseline：

| task | n | proxy TP | proxy FP | proxy FN | proxy TN | proxy positive recall | baseline BAcc |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3 | 71 | 50 | 0 | 9 | 12 | 50/59=0.8475 | 0.923729 |
| 5 | 77 | 45 | 2 | 17 | 13 | 45/62=0.7258 | 0.796237 |
| 9 | 58 | 6 | 0 | **30** | 22 | **6/36=0.1667** | **0.583333** |

**30/56=53.6% 的工具 flag=False / FGONLY+ 错配集中于 Task 9**，尽管 Task 9 仅58/206=28.2% 样本；这是失败分布的真实 task 异质性，不等同“Task9 的 30 个物体实际已抓住”。

Leave-One-Task-Out 的“训练两任务选固定模块族→第三任务评估”实际选择：
- 留 Task3：选 `A0_gap060_AND_lift050`，test BAcc=0.699859 vs Tool=0.923729，Δ=−0.223870；
- 留 Task5：同上，test=0.668817 vs Tool=0.796237，Δ=−0.127420；
- 留 Task9：选原 Tool，test=0.583333 vs Tool=0.583333，Δ=0；
- 合并 test BAcc=0.722735 vs Tool=0.801248，**Δ=−0.078513**，proxy FP=15 vs Tool=2。

**裁决：STOP 继续在这13种简单 gap/lift 组合上盲目调阈值**。任务异质性、是否缺了 Tool 原有成功条件，优先于再加一个静态 OR。

## 源码复盘得出的下一轮实验假设（新实验结果尚未运行）

查 `robots/libero/tools.py:pi0_pick` 实现：原始工具成功实际上检查 **下降幅度≥0.10m（D）+ 后最低点提升≥0.05m（L）+ 当前最终夹爪开度<0.06m（Gfinal）**，并逐 chunk 判断提前退出。

然而 Module Lab 中最接近原 Tool 的 `A0_gap060_AND_lift050` **漏掉了 D 门槛，而且使用 `min_gripper_opening` 代替 `final_gripper_opening`**。这可能解释其相对 Tool 新增15个 proxy FP，必须实际测量，不能把“缺 D”单因归咎当既成事实；两个修改需分开消融。

因此下一轮**更聚焦的实证消融**已经独立提交：
- `analysis/research_context/p1_pick_gate_lab.py`：固定 11 arms，分别保留/删除 D、L、Gfinal，min↔final 替换；按 Task3/5/9 与三个 gate 的布尔组合报告 proxy confusion 与原 flag mismatch，真实弱标签只在 scoring 中读取。
- `analysis/research_context/test_p1_pick_gate_lab.py`：合成验证三个门槛、遗漏 D、新旧开度位置、无效字段 abstain 和终态 gate 与工具 flag 不一致的案例。
- **重要可证伪点**：若 D∧L∧Gfinal 在 206 个真实样本上仍不能逐项重建原 flag，就检查逐 chunk 的提前退出条件与末端摘要信息不完全等价；不能强行改标签或调整阈值直到匹配。
- 用户可用**一个 Coding Agent Prompt 自主拉库、执行两个实验、诊断、修复非科学意义的 bug、提交研究报告**，无需再人工多轮粘贴 SSH 命令。

**当前阶段**：`MODULE_LAB_V1_SERVER_7_7_PASS_ALL_FIXED_ARMS_BELOW_FLAG_BACC / TASK9_MISMATCH_CONCENTRATION / GATE_ABLATION_L1_CODE_COMMITTED_TESTS_UNRUN / NEW_L2_HOLD`。
