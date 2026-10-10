# P1 L1 · 分离排序增益与数据组成效应：Matched Triage Information Experiment

> **日期/状态**：2026-10-10；研究分支已提交可执行代码 `p1_triage_incremental_lab.py` 和合成单测 `test_p1_triage_incremental_lab.py`；**真实冻结数据新实验尚未在服务器运行**。不允许修改原排序、阈值、封版来源、Runtime，也不运行 L2/新 sim。
>
> **来源**：最新真实 `P1_RETURN_TIME_TRIAGE_RESULT_20261010.md`，103次 Tool False（79 episodes），26退出时代理正、77代理负。固定 Lift−Gap 全局Top20%=**17正/4负**，Random=5.30正，D-only门槛优先=**13.26正**；Top20 全部来自 `011` 模式，Task3/5/9 分别获得 **2/8/11** 个复核席位。t9 D-only 子池 Top4=3个代理正，池内正例11/19。以上是**已经执行的实证**，不是本新实验结果。

## 为什么要继续做这一轮，而不能先声称排序器有 3.21 倍算法收益？

3.21倍 = 17/21 ÷ 26/103，是相对于**全局随机抽取**的富集。它同时包含至少三种来源：

1. 门槛粗筛：`011` 模式本身的代理正例占比更高，所以选中 `011` 就能超过全局随机；
2. 任务组成：相同 `011` 内各 Task 的成功先验可能不同，LMG 的 Top20 只给 Task3 两个席位；
3. 连续分数增量：在**相同 Task、相同 `D/L/G` 模式**的候选之间，高 lift、低 final gap 是否还含有额外信息？

论文方法上的真正新信息应尽量衡量 (3)。如果 (1)+(2) 已解释全部17个命中，继续在这103条上试不同公式也只是重排已知子群，无新增因果或感知能力。

## 固定实验与比较方式

**排序算法保持冻结不变**：LMG=`peak_lift_m/0.05 − final_gripper_opening/0.06`，保持 `p1_return_time_triage_lab.priority` 原实现与 Top20%、40% 预算。它只能使用合法 Tool Return 字段。

**事后匹配随机基线只用于离线评估，不是部署算法。** 先按原冻结 LMG 分数选出每条样本的选择权重 `w_i∈[0,1]`；同分值按比例抽取，确保权重和正好为 `K=ceil(budget*n)`。对一个控制分组 `g` 定义

[
E[mathrm{matched selected positive}]=
sum_g left(sum_{iin g}w_iight)
rac{sum_{iin g} y_i}{n_g}.
]

`y_i` 为仅在离线评估读到的 exit-time FGONLY 代理。定义 **Δ@budget=(actual_selected_positive−matched_random_expected_positive)/K**，分别在四类基线下计算：

| 控制 | 固定了什么 | 剩余能解释什么 |
|---|---|---|
| Global | 总 K | 门槛+任务+连续分数混合增益 |
| Gate-matched | 每个 `D/L/G` 组合的选中配额 | 任务组成 + 组内连续分数 |
| Task-matched | 每个 Task 的选中配额 | 门槛组成 + 组内连续分数 |
| **Task×Gate-matched** | **每个 Task×D/L/G 子群的实际选中配额** | **子群内连续分数增量** |

同时固定参照 `D_ONLY_PATTERN`、`PEAK_LIFT`，检查任意时刻 vs 退出时刻两类弱代理的 Δ 是否同向；Task3/5/9 自身预算 Top20% 与 t9 `011` 19条子组独立列出。描述性 episode-cluster bootstrap 500 次，不能解释成确认性p值/因果显著性。

**必须理解**：Task×Gate 对照的预期正例率是从**这批样本的 audit-only 标签**离线算出的，只用于研究标准化；其正例率不能流入在线排序策略，更不能作为真实持握标签或“任务先验可部署模型”。LMG 的四个控制并非独立的真正新数据集。

## 结果解释（预先写下，不挑有利数字）

- 如果 **Task×Gate 匹配后的 Δ@20 仍正且聚类Bootstrap区间较稳定**：可说连续工具返回特征包含额外的**同技能退出运动代理排序信息**；接下来只应在新 cohort 用独立持握参考检验可推广性，不能直接推荐 CONTINUE。
- 如果全局 3.21× 富集可观，但 **Task×Gate 匹配后 Δ≈0 或区间跨0**：说明主要杠杆是合法门槛模式与任务配额。下一方向改为 **simple risk strata + budget allocation**，停止升级连续排序为核心算法。
- 如果 t9 `011` 内不稳定且成本高：优先设计一项与 Tool 返回同刻的**真正新增感知**（目标实例、相对位置/跟随或受控提升），而不是继续改形状相近的 Gap/Lift 公式。
- 如果本实验无法通过冻源哈希/206 join/103 failures/26 terminal/56 any/19 t9`011`/11 terminal-positive，立即 STOP，**不允许重写冻结数据或偷偷放宽 Gate**。

## 执行与隐私验收

`python3 -m unittest discover -s analysis/research_context -p 'test_p1_triage_incremental_lab.py' -v` 后运行 `python3 analysis/research_context/p1_triage_incremental_lab.py`。命令应由**服务器 Coding Agent 自主执行**，不需用户逐条复制。只读使用既有 `build_rows()`（内部 SHA、schema、原 A0 逐例对齐）；结果写 gitignored `artifacts/p1_return_time_triage_lab/incremental_v1.json`，只输出聚合计数、bootstrap；禁止 case ID、对象坐标、图片和audit数组提交Git。

**科研结论目前 HOLD**：代码及测试已提交，服务器尚未运行本轮真实数据。已完成的上一轮 81%/3.21× 是已证实的**回顾性代理富集**，但并未检验组成控制后的增量。新 L2 永远需要另行明示授权。
