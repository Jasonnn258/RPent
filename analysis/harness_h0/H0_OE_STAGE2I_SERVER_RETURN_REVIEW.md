# H0 · Stage2I 服务器结构扫描回传审查

> 2026-10-09 | 追加审查；基线 `86e863d16d56e0e304664db854c890b754ff616d`。  
> 数据来源：用户在本轮对话中提供的、在服务器执行 `h0_oe_stage2i_structure_scan.py` 后的完整 JSON stdout（protocol `H0-STAGE2I-STRUCTURE-ONLY-V1`）。**此处仅登记用户回传；审查方不能直接访问或独立复扫服务器私有目录。**  
> GitHub 源码复核：`analysis/harness_h0/h0_oe_stage2i_structure_scan.py` 与 `H0_OE_STAGE2I_ALL_CORPUS_ELIGIBILITY_GATE.md`。  
> 零 outcome 值访问；未运行新数值审计、rollout、训练，未修改冻结的 Stage R/Stage2C 资产。

## 0. 结果与裁决

**`SERVER_RETURNED_SCHEMA_PASS / PAIRED_PICK_CALLS_235 / CLASS_ELIGIBILITY_PENDING / A0_OUTCOME_ANALYSIS_NOT_AUTHORIZED`**

| 字段 | 服务器回传 |
|---|---:|
| ledger_rows | 187 |
| ledger_rows_with_episode_dir | 187 |
| unique_episode_dirs | 187 |
| duplicate_episode_dir_rows | 0 |
| episodes_with_both_files | 187 |
| episodes_with_pick | 186 |
| episodes_without_pick | 1 |
| pi0_pick_calls | 235 |
| pick_calls_with_trace_boundary_and_action | 235 |
| pick_chunk_actions | 2859 |
| complete_paired_pi0_pick_calls | 235 |
| examples | 空数组 |
| gate | `STRUCTURE_ONLY_PASS_PENDING_CLASS_ELIGIBILITY` |

结构上，这意味着服务器回传显示：**所有 235 个观察到的 `pi0_pick` 都有脚本要求的 result/diagnostics 键、对齐的 step_begin/step_end、连续的 chunk_idx、各 chunk 的测量键、末端测量键和非递减时间戳**。该结论的精确含义仅为“通过当前 V1 检查器的字段和时间结构规则”。

有 186 个 episode 含 pick，但总计 235 次 pick，故同一 episode 可以贡献多次相关调用。未来任何数值评价的主要独立采样单位至少应考虑 **episode 聚类**，不得把 235 次调用当 235 个独立 episode。另 1 个无 pick 的 episode，不可无故标记为 infra 失败或将其偷偷计入 pick 统计分母。

## 1. 验收范围与尚未覆盖的语义 Gate

### PASS：当前 V1 结构 Gate

- 存在性：ledger 187 个目录、双文件结构均通过，目录无重复。
- 逐技能配对：235 次 pick 的结构要求全部通过；无缺失或不匹配样例。
- 采样时序：逐 chunk_idx 连续，按 `step_begin → pre-chunk action/meas → step_end/final_meas` 的顺序记录。

### 未通过、也未失败：V1 尚未测量

1. **成功类别支持性**：V1 只检验 `result.success` 键存在，不读取布尔值。235 个 pick 是否包含足够正负两类、类别在 episode 间如何分布，仍是 `NOT_VERIFIED`。
2. **物理参考构造性**：`is_meas_schema()` 验证的是 `meas` 外层 `obs` 为 dict，以及 `check_success/obj_of_interest` 等键存在，**没有验证目标物体 `{target}_pos`、`robot0_eef_pos` 等用于 FG 参考的内部字段覆盖/数值有效性**。因此不能自动宣称 235 个样本均具备可计算的合法物理参考。
3. **时间后果**：同技能的 `final_meas` 发生于工具反馈交付 Planner 之前，且无新的动作；不是 D2 返回后未来保持标签。Stage2H 的 `A0_CONCORDANCE_ONLY` 判决保持。
4. **来源循环风险**：`pi0_pick` 的终局镜像与 `ACQ` 的 `check_success` shortcut 可能共享任务成功谓词。正向契合不等于独立物理校验；如果将来设计 A0，须明确标出“物体位姿确认”与“官方终局 shortcut”两种证据来源，且事先冻结。
5. **V1 PASS 的程序边界**：扫描器的最终 `gate` 断言只覆盖代码显式判定的子集；非结果值字段的内部物理语义与跨 episode 独立性没有纳入。因此 `STRUCTURE_ONLY_PASS` 不能升级为 `A0_DATA_QUALITY_FULLY_VERIFIED`。

## 2. 对 A0 的科学价值判断

当前可行的假设性对象：**在既有 vanilla collect 样本框内，原始 `pi0_pick.result.success` 与同一技能期间 `IN_SKILL_ACQ_AUDIT` 的回顾性判据一致性**。

它可能形成一个有用的 **Harness 工具反馈可信度工程基线**，但价值上限明确：

- A0 是 retrospective/concurrent criterion audit，而非未来抓握持久性预测；
- 原始 episode 的收集任务、seed、配额与调用次数相关性限制外推；
- 当前样本类别支持性和内部 FG 参考覆盖尚未审查；
- 即使 A0 定标信号很强，也不建立新方法、干预收益、Runtime/Evolution Gate 或因果修复性。

**立项判断：`SCHEMA_PASS_BUT_NO_AUTOMATIC_SCIENTIFIC_GO`。** 下一步不宜再次围绕 235 样本重新定义大量代理或拟合模型。若用户需要真实 tool-verdict 的工程可靠性报告，先冻结 A0 数据资格/操作化协议，再另行授权 outcome 值核查及分析；若目标是新 Embodied Harness 方法，**可以合理地直接关闭 H0 A0 实验支线**。

## 3. 下一步选择（当前均未执行）

**选项 A：一次性 A0 预注册草案（纯文档）**。固定 eligible pick、两类工具返回的资格边界、物理 reference 的内部字段与 FG 判据、terminal shortcut 的来源剥离、重复 pick 的 episode 聚类、缺失/删失、评价表与止损规则；不得读取 outcome 值或产出预注册后验结果。

**选项 B：用户显式批准后，执行单次结果值资格检查**。仅检验真实 `result.success` 二元类别支持与 `IN_SKILL_ACQ_AUDIT` 可构造性；预先冻结分析范围与阈值，并把类别存在性与任何性能统计区分。该选项**尚未授权**，不可由本轮结构 PASS 推定授权。

**选项 C：H0 A0 收官**。保留既有负面创新性证据和这次 235/235 结构资格证明，将研究资源转向具有新的、可证伪的 Harness 决策机制和独立未来评价的数据问题。

## 4. 不变量与可追溯性

- 来源：用户粘贴的服务器 stdout；本报告没有访问服务器私有 CPS/episode/raw measurement。
- 未重写 `H0_OE_STAGE2I_ALL_CORPUS_ELIGIBILITY_GATE.md`，其 `SERVER_SCAN_NOT_RUN` 语句是当时历史状态，本追加报告记录服务器**随后完成**扫描并回传。
- Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、Stage2C frozen v1、Stage2D 回顾性结果与运行时授权全部原样保持。

**最终：`H0_STAGE2I_SERVER_RETURN_REVIEW_COMPLETE / STRUCTURE_PASS / CLASS_AND_PHYSICAL_REFERENCE_ELIGIBILITY_UNVERIFIED / NOVEL_ALGORITHM_NOT_ESTABLISHED / NO_NEW_EXECUTION_AUTHORIZED`。**
