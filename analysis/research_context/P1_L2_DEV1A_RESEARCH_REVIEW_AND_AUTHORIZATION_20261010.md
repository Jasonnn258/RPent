# RPent · Time-Aligned Evidence Acquisition × Budgeted Selective Verification：方法论评审与 DEV1A 有界授权

> **审查日期：2026-10-10；授权来源：用户明确委托助手代为研究审核、批准限定范围的下一阶段。**
>
> **决定：APPROVED_CONDITIONAL / DESIGN_AND_CODE_GO / SIM_AFTER_PRELAUNCH_GATES / POLICY_EFFECT_HOLD。** 仅对新独立仿真 DEV1A 的同步观测与物理标签可行性试验发放**一次性、有条件、不可自动扩容**的授权；旧 Stage R §36 冻结、旧 DEV0 与 S1 继续保持 HARD STOP。本授权不批准真实硬件、模型训练、生产动作政策、提前设定为正确的抓取标签或新 cohort 大样本确证。
>
> **禁止把这份审批文件本身当作设备可运行性验证、Budget Gate 已实现或物理标签已经存在的证据。** GitHub 仓库读写 ≠ 用户服务器终端权限；本次未运行任何 GPU/sim 试验。

## 1. 对现有材料的具体审查

### 本项目的实证来源

- 用户提供的《RPent 机器人记忆机制研究：阶段性总结报告》：Memory Access 修复有收益，但动态错误触发伤害执行；OVP-M 在开发任务局部有效、held-out 不稳定；G0/G0.5/G0.6 的 P4 完整 Memory 相比 P2 Generic Refresh 并无稳健最终效应。研究应把收益归因链拆成介入时刻→观察→决策采纳→物理动作→可核验结果。
- 仓库 A0：206 PRIMARY、103 Tool False，原 FGONLY `any-time` 导致56表观 proxy FN；重算 `final_meas` 后仅26末端 proxy 正，其余30瞬时，末端 proxy 不是独立 held 真值。
- `P1_TASK9_CONDITIONAL_RESULT_20261010.md`：task9 D-only n19（11末端正/8瞬时），连续分数Top4 3/4，置换p约0.42，可靠组内区分尚无；冻结全局 LMG 17/21中，task×gate 匹配随机期望14.48，由已有 LMG 选择产生配额，**不是单独可执行标签盲策略**。D-039 的最后 L1 label-blind quota 比较结果目前待服务器实测。
- 旧 P1-DEV0：21/24 episodes、6 triggers、5 probes、所有生产决策RETRY、无D2生产触发；probe在夹爪闭合时执行真实环境步但没有同刻独立接触或持握标签。历史 GPU·h 限额21600秒实际耗22215秒，超615秒；本轮需要**预留最坏在飞成本**，不能重用旧启动门做法。

### 外部研究锚点（文献主张不代表本项目已实现）

1. SAFE (NeurIPS 2025; https://arxiv.org/abs/2506.09937)：用VLA内部特征做跨任务失败检测，使用conformal等风险/延迟权衡。**差异**：RPent 针对失败后按动作代价选择主动观测/验证，不仅是 failure score。
2. ActFovea (arXiv 2026; https://arxiv.org/abs/2607.29169)：基于行动条件的关注区域与视-动作时空一致性做无需重训的runtime safeguarding。**差异**：需要定量区分追加物理观测动作的机械效应与其带来的信息效应，并引入真实预算。
3. FRAMES (arXiv 2026; https://arxiv.org/abs/2609.22538)：时序多视角/结构化接触监控、Planner/Monitor/Recovery模块，报告的94%主要来自100个模拟监控试次，端到端恢复评测仍在进行。**差异**：RPent更强调同刻物理标签、有限预算采样机制和严格执行分支对照。
4. TemporalFlow-VLA (arXiv 2026; https://arxiv.org/abs/2608.26821)：执行历史的时序几何监督，表明简单附加历史帧难表示真实状态变化。**启发**：短时序比单帧静态数值有价值，但其模型训练和结果不是RPent本轮的直接baseline。
5. FailureSpot (arXiv 2026; https://arxiv.org/abs/2609.04277)：指出trajectory级标签标注每个时间点会引入时间定位噪声，并通过选择性标注降低时间点标注成本。**启发**：物理标签必须和tool-return/probe-end时间点严格同步。
6. ReCoVERR (ACL Findings 2024; https://aclanthology.org/2024.findings-acl.767/)：低置信时主动获取补充证据以降低不必要弃权。**启发**：证据获取要比较新增可决策的信息，不能仅比较“多看一眼”的模态数。
7. Selective Classification (NeurIPS 2017; https://papers.nips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html)：覆盖率与风险约束，不能用100%弃权虚报零误报。
8. POMDP Robotics survey (Annual Reviews 2022; https://doi.org/10.1146/annurev-control-042920-092451)：部分可观测下的行动—信息决策框架，支持以信念更新后的**决策价值**而非传感器熵下降作为核心评价。
9. FLARE (CVPR 2026; https://openaccess.thecvf.com/content/CVPR2026/html/Zhao_FLARE_A_Failure-Aware_Framework_for_Autonomous_Correction_and_Recovery_in_CVPR_2026_paper.html)：学习 Retry/Reset 恢复策略并通过在线 MLLM 监控路由；RPent应避免仅以“Monitor+Recovery”组合宣称新颖性。

**可能的真实方法创新**：在机器人拥有不确定结果和严格验证预算时，选择 **感知行动 q**（如立即双视角无动作观测、固定闭合、受控上提），使预期后续最优动作价值增量超过感知成本与机械扰动风险；同时给出可追溯的同物理时刻审计标签与风险覆盖统计。这需要真实前瞻实验才可证明。

## 2. 研究核心：同时估计三个不同效应

`s_t` 为不可直接观测的持握状态，`b_t` 为基于合法 RGB/proprio/历史动作的 belief，`q` 为验证动作，`o_{t+}` 为新观察，`a` 是 CONTINUE/RETRY/ABSTAIN。

形式化提议（**未训练未标定**）：

`VOI(q|b_t) = E_o[max_a E(U|b_{t+},a)] - max_a E(U|b_t,a) - C_observe(q) - C_motion(q)`

但真实物理 probe 会改变 `s_t`，因此不能把所有差额称作纯信息增益；需要三层识别：

- **机械效应**：NO_PROBE+BLIND_RETRY 与 SAME_PROBE+BLIND_RETRY（完全同一后续盲化动作合同、同样评价窗口）。
- **证据效应**：SAME_PROBE+BLIND 与 SAME_PROBE+PROPRIO / SAME_PROBE+RGB+PROPRIO（同一物理动作与采集时刻，差异只有合法观察是否供决策消费）。
- **观测层级/成本效应**：零动作重拍、定点闭合、受控提升分别记录成本与视角增益；含额外提升的臂必须用 SAME_LIFT+BLIND 对照，禁止将提升造成的物理保持改善算作多模态感知收益。

> 三层实验不可能在8个试点episode内都得出可信统计效应。DEV1A 的唯一主终点是可行性/标签独立性；因果策略价值留给另行审批的 DEV1B 或确证阶段。

## 3. 我替用户批准的有界 DEV1A

### 授权范围与不可超越资源上限

- **环境**：已有 LIBERO/MuJoCo 仿真配置；**独立新 seeds**，不复跑 Stage R / S1 / DEV0 封版资产。严格限于原研究分支下新隔离的 `p1_dev1a` 入口、私有输出目录、只读审计和合成测试。不得修改 frozen Stage R /旧 DEV0 工具运行结果；不得自动复用其审批。
- **至多8个新 episode**，分配 **t9×4、t3×2、t5×2**，入场前先封版具体 seeds 与分配顺序；最多**1 worker**，每个 episode **≤1500个环境步**，每 episode 最多一次失败触发观测；若真实触发稀少或全同类，按计划结束如实报告，不补跑。
- **同时双硬帽**：`GPU·time ≤3 GPU·h`（10800秒）且墙钟 `≤4h`。任何首先达到即 STOP，不补差额；还有可运行 episode 时，必须按**实测最坏 episode 时长上界 + 安全余量**预留完整在飞成本，无法满足就不得启动。硬上限与脚本计量均需测试失败路径、SIGTERM/异常与断点恢复。GPU成本口径记录GPU个数×占用时间及来源，额外独立进程也纳入；不因首尾转换或新 worker 偷跑而超帽。
- **触发**：仅原工具 `pi0_pick.success=False`，样本抽样规则和触发前合法字段固定。无触发以 `NOT_TRIGGERED` 纳入 intention-to-treat / allocation 分母；不以无触发为借口追加 seeds。
- **准许的物理 probe**：先在**无GPU的已封版复制状态**中验证几何范围/控制指令可达，之后于仿真最多一次固定夹爪关闭（≤10 env steps）+最多 **0.02m（2cm）受控垂直提升**，禁止闭环搜索抓取和横向移动。不安全高度、碰撞、超额物理步或对象不可辨时跳过提升并标记 UNKNOWN，绝不硬判成功。提升具体控制周期/总步数需在运行前锁定并计入每集1500步和成本，不能运行后调节。
- **决策/策略**：DEV1A 阶段 probe 可影响模拟物理状态，但**所有臂禁止利用新证据驱动 CONTINUE/RETRY 的生产动作**，执行统一 blind continuation 或在探测后立即终止并审计（必须在 manifest 预注册二选一）。新的证据策略可在离线 shadow 评估，但只作为 feasibility，不可宣称行动增益。
- **提交范围**：仅代码、单测、协议、脱敏汇总和 source hashes；私有 RGB、原始 sim pose/contact、轨迹 JSONL 与目标 instance 明细仅保存于已有 gitignored 私有目录。无需付费API、不得上传私人像素到云端 VLM。

### 先满足以下四项 Gate，才算允许消耗第一 GPU 秒

1. **G1 场景能力**：脚本可以从 sim 获取目标 object/body/geom ID、两指接触 geom、桌面支撑 geom 和足以定义稳定相对位姿的物体坐标。接触事件中能实际区分 finger↔target 与 finger↔robot-self/support；否则 `HOLD_NO_INDEPENDENT_LABEL`，停止运行。
2. **G2 同时刻**：`t_trigger`、`t_close_end`、`t_lift_end` 每个时点记录统一 `env_step`，在不推进额外 env step 的前提下采合法 RGB/proprio 与独立 audit-only sim 参考。Wrist 全程统一翻转朝向/内外参，记录源 hash、step 与 fresh 状态。不能在 t_trigger 使用旧分割伪装 post probe 的 mask。
3. **G3 防泄漏**：Audit-only 目标 ID、contact、obj_pos、support/held 物理参考严格旁路写入不可见容器；审计用随机重排/插入禁止字段做污染对抗测试。任何审计字段进入 online observation、工具返回、模型 Prompt、Memory 更新或策略 feature 立即 STOP。
4. **G4 预算和执行时序**：模拟计时、资源预留、双硬帽、8×task seeds、单worker、额外env steps完整计费均通过零仿真/单测与受限本地验证；不允许后验修改已封版动作参数、seed、失败判据、评价口径。实现无法证明不会越限则保持 HOLD。

### 独立 audit-only 物理参考的**操作性定义**

- `target_contact_t`：目标 instance 特定 geom 与左/右指接触双方均在 **同一 sim tick** 观测到，分类 `BILATERAL / SINGLE / NONE / UNKNOWN`；若 engine 只有近距离而无已解析 geom pairs，必须 UNKNOWN，不使用“小gap≈接触”替代。
- `target_retained_t`：固定闭合与受控提升后，目标离开支撑面并与夹爪/EEF 维持有限时间窗内相对运动/接触一致性；记录 `RETAINED / NOT_RETAINED / UNKNOWN` 并拆开接触与离台判断。物体局部摇晃、仅一指接触或不可见/不可追踪应允许 UNKNOWN。**此为仿真操作性弱物理标签，仍不是现实抓持真值。**
- 时间分离：`t_lift_end` 的 retained 参考不许重标成 `t_close_end` 的接触，更不许映射回原 Stage R `final_meas` 真值；后续固定H任务成功另列。测试要包含“空闭合、双指接触但仍受桌面支持、提升后脱落、稳定持握、目标遮挡/缺失”五类反例。

### DEV1A 验收与升级/停止门槛

- 首要输出：已封版分母、触发数、合法实时帧时间一致率、每种物理标签的 `POS/NEG/UNKNOWN` 覆盖、同一tick来源合格率、接触和retained能否合理分离、物理动作扰动量与资源消耗、异常/安全终止计数。
- **只有至少2个 `RETAINED` 与2个 `NOT_RETAINED` 的独立已验证标签、全部目标 geom可溯源、零泄漏、零时点错位、零预算越限**，才可建议后续独立 cohort；否则停在 DEV1A，明确标签稀缺或模型不可辨识，不自动扩大 N。
- 即使覆盖合格，8 episode也仅是工程与构念可行性证据：**禁止准确率、统计显著性、策略因果收益、跨任务泛化等主张**。进入可检验 `Budgeted Selective Verification` 的 online policy-value 对照必须另立 DEV1B 多臂随机化、同probe blind 对照、固定H评价及成本/弃权约束；不能由本次自动延续。

## 4. 真正的研究贡献需要哪些对照结果

建议最终论文结构是以下层层可证伪的主张，而非一开始堆“大模型验证器”：

1. **Synchronization improves construct validity**：相对旧 any-time label，严格同刻观测是否减少 reference-time 误差；需同tick audit支撑。
2. **Active sensing produces useful *new* evidence**：在相同机械 probe 下，time-aligned RGB/proprio 是否增量降低 held/contact 的 selective risk；必须和既有合法工具状态、单模态、不行动重拍比较，保证成本一致。
3. **Budgeted acquisition improves utility**：在相同验证次数/物理步/时间/失败风险约束下，任务分层+验证优先级是否提升独立真值的核验覆盖，并最终改善真实继续/重试决定的固定H效用。
4. **Mechanical effect disentangled**：`NO_PROBE+BLIND` vs `SAME_PROBE+BLIND`；`SAME_PROBE+BLIND` vs `SAME_PROBE+EVIDENCE`。非执行/shadow动作分歧不具此归因资格。
5. **Cost/frontier trade-off**：绘制验证成本→物理参考覆盖/弃权→决策风险/最终物理成功的 Pareto 曲线；不允许100%弃权、永不CONTINUE或纯 Tool check_success 获得虚假安全。

## 5. 授权登记与执行边界

- **研究者用户已在聊天明确委托助手审查授权**；本决定允许新阶段开发和**满足全部G1–G4后最多8个新仿真episode**，限定在 DEV1A。任何真实硬件、付费API、扩大episode/预算、SFT/RL、生产策略与 DEV1B 均无授权。
- **服务器运行权前提**：只有处于用户私有服务器并拥有对应终端权限的 Agent 才能实际执行；若发现 Git 工作区未保存修改、模型/接触 API 不可得、实验上限不受控，必须先 STOP 并提交非执行审查报告。不能仅凭本授权文档声称已经执行或已满足 Gate。
- **授权码/状态**：`P1_L2_DEV1A_CONDITIONAL_APPROVAL_20261010 / SIM_NOT_STARTED / MAX_8_EP / MAX_3_GPUH / MAX_4_WALLH / NO_POLICY_ACTION_DIVERGENCE / G1_G4_REQUIRED / NEW_L2_DEV1B_HOLD`。

**下一动作**：远端 Coding Agent 在单一任务中先核对源代码/物理API，完成G1–G4的单测和新阶段冻结manifest；若均证据化PASS，则依本次一次性有限授权可以自动启动DEV1A并执行到预定终止；任何Gate失败即时STOP，绝不替换无效物理标签或放宽预算。
