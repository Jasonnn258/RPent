# P1 · Label-blind Quota：独立可执行基线 vs 事后 matched control

> 2026-10-10；**EXECUTED（同日只读离线实跑完成；测试修复一处浮点严格相等断言后 6/6 PASS）**。真实结果见 `P1_LABEL_BLIND_QUOTA_RESULT_20261010.md`：Top20 退出参考下 GATE_ONLY 13.26/0.632、TASK_EQUAL 13.78/0.656、TASK_PROP 13.70/0.653、LMG 17.00/0.810、RANDOM 5.30——任务配额仅 +0.02 边际且 Top40 反向；**matched 14.48 不可被任何标签盲分配器达成（最高 13.78）**；`task_id` 只在 metadata 视图且 instruction→task 不唯一 → TASK_* 判 `OFFLINE_BATCH_ONLY`。预登记分支 2+3 双触发：保留 GATE_ONLY 为唯一廉价合法候选，任务配额降级探索性基线，**本轮后停止在同 103 例搜索静态规则**。冻结 A0/Stage R 只读；旧 DEV0 CLOSED。执行后同日,用户委托的 D-040/D-041 已对 DEV1A(≤8 新 episode、≤3 GPU·h、≤4h 墙钟、G1–G4 预检门)作出有条件授权,本条目早先的"新 L2 HOLD"表述由 D-041 取代;因果臂 G3/真实机器人仍 HOLD。

## 研究上的关键纠正

第四轮 `P1_TASK9_CONDITIONAL_RESULT_20261010.md` 报告的 **Task×Gate matched random 14.48/21≈0.69**，是**先使用已冻结 LIFT_MINUS_GAP（LMG）得分得到选中样本，再固定这些样本在 task×gate 每个格子的真实配额**，最后用该格全体的 FGONLY audit 标签均值计算期望。它是合理的**离线组成效应分解**，但不能据此说“独立、零拟合的任务+门槛策略已经实际达到 0.69 Precision”。

LMG 全局命中 17/21=0.810，其中 matched composition 期望14.48，连续 score 增量仅2.52/21≈0.120，这个差分仍是合法的描述性研究结果。**它本身并未实现一个能事先生成14.48所需 task×gate 配额的策略**，也未证明任务 ID 处于 Harness pre-delivery 可见字段中。这是进行 L2 前的重要可执行性缺口。

## 一次真实L1对照：不要再拟合静态公式

数据：冻结 103 个 `tool.success=false`（79 episodes，task3/5/9=21/30/52），26例 exit-FGONLY 代理正/56例 any-time-FGONLY 代理正。严格复用之前已通过的源哈希与逐例 A0 join。

固定总预算：Top20%=`ceil(103*.2)=21`，Top40%=`ceil(103*.4)=42`。对每个方法仅用**合法门槛字段或任务分组/待复核池大小**生成选择权重。每种方法结果在同一 FGONLY audit-only 标签上统一评价：

| 方法 | 谁决定预算与优先级 | 在线可行性解释 |
|---|---|---|
| RANDOM | 全球全部103候选均匀抽样 | 可用随机门槛控制，但需采样规则；离线基准 |
| GATE_ONLY | 全球优先011，组内均匀 | 只需工具返回的 D/L/Gfinal；最接近可在线运行的独立基线 |
| TASK_EQUAL_GATE | 3个任务平均分21个名额(7/7/7)，每任务内优先011 | **仅批量场景可计算**；task ID和队列可见性尚未证实 |
| TASK_PROP_GATE | 按批次候选数比例分21个名额(4/6/11)，任务内优先011 | 同上；不是在线顺序决策 |
| LMG_FROZEN | 原 Lift/0.05 − FinalGap/0.06 得分全局排序 | 合法工具数值，研究用旧基准；无法证明held/truth |

名额取整：无标签的逐席赤字/公平水位法，容量不足则分配给有剩余的任务；同 gate cell 内采用均匀抽中期望。**不允许用任何 FGONLY 值确定 quota、priority、tie-break 或阈值。** 任务分组只来自 reconstruction metadata，在证据来源合法性核对之前绝不把任务 quota 方式接线到 Runtime。

结果：同一预算下每种方法的 proxy hits/误选、Precision、相对于整体随机基率富集、实际每个任务选中配额；同时换成 any-time 标签，只改变评价标准，用于检验时间敏感性。所有私有明细不上 Git，仅写 `artifacts/p1_return_time_triage_lab/label_blind_quota_v1.json`。

## GO / STOP 科研判定

1. **先比较独立 GATE_ONLY vs 独立 task-quota 设计**，并将已存在的 LMG 结果展示为候选上界式参考；如果 task quota 的确改善，仍需证明 task ID和批处理约束实际合法，并在独立 cohort 测持握真值，否则只是回顾性 cohort 特异性。
2. 如果 TASK_* 并未明显强于 GATE_ONLY（已知原 D-only Top20%=13.26/21≈0.632），则**撤回“按任务预算是主要算法机制”的强表述**；只保留 D-only 风险分层是合法的可表达候选，Task9 子池继续静态阈值的路线永久 STOP。
3. 如果均不优于 LMG，不要把 matched 14.48 当独立策略“反超”或“证明无需连续值”。过去控制分析仍有解释价值，但未产出足够可靠的无标签部署策略。
4. **当前 L1 数据已经被多次用于方向选择**，本轮后除非出现实质性有效性漏洞，不再在同103条上搜索新公式、额外固定臂或调参。下一阶段只有在用户独立授权和真物理标签合同就绪后才进行 bounded L2。

**当前阶段**：`LABEL_BLIND_QUOTA_L1_6_OF_6_SERVER_PASS_GATE_ONLY_RETAINED / PREVIOUS_MATCHED_0P69_EMPIRICALLY_UNREACHABLE / STATIC_RULE_SEARCH_ON_103_CLOSED / D041_DEV1A_CONDITIONAL_GO_G1_G4_PENDING / G3_CAUSAL_HOLD`。
