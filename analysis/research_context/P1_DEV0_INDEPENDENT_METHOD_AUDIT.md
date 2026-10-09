# P1-DEV0 · 独立方法与测量审计（后验，只审查已完成数据与源码）

> 2026-10-09。输入：`P1_DEV0_EXECUTION_REPORT.md`、`rpent/utils/p1_dev0.py`、`robots/libero/toolkit.py`、`scripts/p1_dev0_run.py`、`scripts/p1_dev0_analyze.py`、`p1_dev0_policy.py`，及本轮 GitHub 源码读取。**这里确认的是 GitHub 中已提交报告与代码的自洽性；本次审查尚未直接读取私有服务器事件文件。**
>
> 事后审计辅助工具：`scripts/p1_dev0_posthoc_audit.py`（只读），合成测试：`analysis/research_context/test_p1_dev0_posthoc_audit.py`。任何后验 shadow 比较不得用于反向修改冻结指标或冒充新实验。

## 2026-10-09 聚合诊断 v2 实际服务器回传：机制已定位

用户在同一服务器运行增强版 `scripts/p1_dev0_posthoc_audit.py` 和合成测试，**4/4 OK**，`policy_sha_match=true`、`science_gate=HOLD_NO_ARM_ACTION_CONTRAST`。冻结 manifest 24 条中 21 条有事件，6 个触发，其中 5 个 probe 后合法观测的**新增聚合实测**：

| 诊断字段 | 实际结果 | 解释 |
|---|---:|---|
| `finite_gripper_gap` | 5 | 均有效 |
| `post_gap_lt_0p06` | **5** | D2 静态闭合条件全满足 |
| `finite_eef_z_delta` | 5 | 均有效 |
| `eef_z_delta_ge_0p03` | **0** | D3 新增 EEF 高度条件全不满足 |
| `d2_continue_d3_retry` | **5** | 已观察合法输入上策略确有规则分歧 |
| `probe_vs_policy_input_mismatch` | **0** | 当前所核对的 `post_legal.gripper_gap/eef_z` 与真正策略输入相符 |
| `probe_legal_not_recorded` | **0** | probe 合法本体记录均存在 |

**裁决：原“夹爪全开”是报告解释错误；D2/D3 分歧是合法观测之上的冻结规则失配，非 probe→policy 字段传递错误。** 现有 D3 把维持 EEF 位姿的 probe 中 EEF 上升 3cm 当作正面验证必要条件，导致这五个样本全部 `RETRY`。但 `gap<0.06` 不能识别目标是否被真实夹持；因此 **D2=CONTINUE 和 D3=RETRY 都没有可信物理真值支持**，绝不后验将两者之一认作正确。

### 后续新增的源码级视觉证据边界

已核对 `rpent/utils/p1_dev0.py` 和 `robots/libero/tools.py:dump_state`：

- `trigger.pre_images` 有 `policy_image_agentview_low` 和 `image_wrist_low` 路径/哈希，`probe.post_frames` 有 `probe_agentview`、`probe_wrist`；旧 DEV0 已保存原始可见的图像**引用**，但文件在当前服务器是否仍存在尚需核验。
- `pre policy_image_agentview_low` 与 `post probe_agentview` 均由 `primitives._last_obs["main_images"]` 写出，具有相同的 policy image 存储约定；仍需考虑时刻/场景差异。
- **关键相机变换差异**：`dump_state` 将 `raw_obs()["robot0_eye_in_hand_image"][::-1]` 写为 `pre image_wrist_low`；`_run_probe` 将 `raw_obs()["robot0_eye_in_hand_image"]` **未经翻转**写为 `post probe_wrist`。未经纵向坐标翻转就做 wrist 图像差分会得到错误的“物体移动”信号。
- 已提交只读 `scripts/p1_dev0_visual_pair_preflight.py` 与合成测试（**提交时尚未执行实际服务器测试/图像扫描**），它验证 21/6/5 冻结事件数量、两视角 pre/post 产物哈希和 PNG 头尺寸，并提示 wrist 需上下对齐。输出仅汇总 Gate，不上传任何原图或私有路径。
- **图像资产齐全仍不等于具备可靠持握监督标签**：像素变化可能来自手爪运动/遮挡/镜头朝向，不得用裸差分直接作为 outcome；下一正式研究须独立验证真正的持握信号（RGB 物体相对 gripper 位移、遮挡/抓持姿态与合法状态）并严格隔离 audit truth。前瞻验证/动作收益需新的 L2。

**更新 Gate：`V2_DIAGNOSTIC_CONFIRMED / RULE_SEMANTIC_MISMATCH_IDENTIFIED / VISUAL_PAIR_DATA_AVAILABILITY_UNTESTED / NO_NEW_ROLLOUT_AUTHORIZED`**。

---

## 2026-10-09 服务器事后审计回传：重大解释勘误（优先于本文旧推断）

用户在原服务器上执行 `test_p1_dev0_posthoc_audit.py`：**4/4 synthetic tests OK**；然后运行 `scripts/p1_dev0_posthoc_audit.py`，回传 `science_gate=HOLD_NO_ARM_ACTION_CONTRAST`，`policy_sha_match=true`。数据级汇总：manifest 24、事件文件 21、触发 6、未触发 15、无事件 3（t9_s1006/s1007/s1008，Runner 报告为预算跳过；不能由 event 缺失本身推断原因）。六个真实动作均为 RETRY。4 次 FIXED_HORIZON overshoot [3,23,8,18]，2 次 EPISODE_END shortfall [120,70]；GPU 22215.374972105026 s，超过原 21600 s 硬额度 **615.3749721050262 s**，`hard_budget_pass=false`。

**关键新结果：**5 个真实 probe 后合法输入的离线 shadow 在冻结策略下得出 `D2=CONTINUE_CAUTION` 5/5、`D3=RETRY` 5/5，**规则分歧=5/5**，但**没有执行 D2 counterfactual action**。本文下方旧文字引用原执行报告称“5 次 `post_gap>=0.06`”，**现已撤回该断言**：按冻结 `p1_dev0_policy.py`，D2 仅在 `post_gap<0.06` 时才 `CONTINUE_CAUTION`，且原报告已有一例 `post_gap=0.0025`。这些数据至多说明 grip-gap **代理达到静态阈值**，绝不意味着夹住物体；静态 D2 在空夹爪被主动闭合时存在“把机械闭合误认为成功”的方法风险。D3 额外要求 hold-gripper probe 的 `post_eef_z-pre_eef_z>=0.03`，可能因 **EEF 本来应保持位置**而机械性退回 RETRY。这是待用聚合合法观测确认的机制解释，不得用 outcome 事后调整阈值。

已补充后验只读工具对 probe 事件 `post_legal` 与 `decision.policy_input` 的传值一致性、gripper-gap 阈值、EEF dz 数值有效性/阈值做**聚合审计**。此增强版尚未由用户运行；原 4/4 通过属于此前版本，不能前移宣称增强版通过。

**研究判定仍为** `DEV0_ENGINEERING_PARTIAL_GO / POLICY_DISAGREEMENT_DIAGNOSTIC_POSITIVE / CAUSAL_OUTCOME_UNOBSERVED / FORMAL_P1_HOLD`。新方法应先保证合法证据可区分“真实持握 vs 单纯夹爪闭合”，然后在一个独立、预注册且预算硬停止的新 L2 阶段评估未来任务收益。

---

## 一、收官级别：ENGINEERING_PARTIAL_GO / HYPOTHESIS_UNTESTED / NO_NEW_L2_EXECUTION

**原报告的“ENGINEERING_GO”只能解释为：本 Pilot 部分实现了触发、5 次实物探测、6 次动作和 6 次审计的端到端运行。** 在科学方法意义上，尚未形成可检验 Evidence Gate 增益的决策对照：

| 必要条件 | 由原报告/源码确认 | 独立审查 |
|---|---|---|
| 新环境真实 D2 失败触发 | 6/21 episodes，t9 5/5、t3 1/8、t5 0/8 | **仅小样本可行性**，成功触发高度集中 |
| 四臂生产决策覆盖 | D0=1，D1=3，D2=0，D3=2 | **D2 未在生产测试；四臂验证不能记全过** |
| 策略是否产生行为差异 | 6/6 actual decision=RETRY，6/6 action=RETRY | **零真实分支行动对照**，即使 outcome 有差异也不能证明选择性验证价值 |
| 物理 probe 与首决策遮蔽 | D1 probe 后第一次 choose 不读结果；返回重试视图 | **首决策层遮蔽成立**，不是整个 Planner 后续信息轨迹的完全等价 |
| 额外视觉信息是否进入决策 | `visual_frame_available` 只检查是否有图像文件 SHA256 | **没有对新图像像素做识别/确认**；不能称视觉验证器已测试 |
| 未来标签统一固定 H=200 | 4 次 `FIXED_HORIZON`，在 H 后的技能边界 +3/+8/+18/+23 步；2 次 `EPISODE_END` 低于 H 70/120 步 | **4 次允许 overshoot 的 H 后审计 + 2 次提前结束/删失**，不能叫 6/6 相同 horizon |
| GPU 使用预算 | 6.17 GPU·hour / 上限 6.00 | **超约 0.17 GPU·hour**；launch-gate 不是 hard STOP |
| 工程日志分母 | 分配 24、运行 21、3 未启动 | 现有 analyzer 的 `no_events_infra` 把无事件全算 infra，**错误地吞并 budget-skipped** |

**核心裁决**：`PARTIAL_ENGINEERING_GO` 可以保留（有真实新执行证明钩子和审计基础）；`P1_METHOD_GAIN_NOT_IDENTIFIED` 是必须明确的科学状态。**不继续追加 DEV0 episode**，不因为 D2 缺产线暴露就回头补跑已经超预算的冻结 manifest。

## 二、需要纠正的三个语义边界

### C1：P1 Hook 实际是 pre-delivery interceptor，未把原始失败交给 Planner

`LiberoToolkit._step` 的真实顺序：执行 `pi0_pick`，`dump_state(...success=False)`，然后在 `view_driver_state(step_idx)` 返回给 Planner **之前**进入 `p1_dev0.maybe_intervene`。D0/D1 触发后直接调用 `toolkit._step("pi0_pick", ...)` 并把重试结果视图返回 Planner。因此 **第一次失败 flag 被 Harness/Tool Adapter 消费，但未作为独立失败消息送达 Planner**。

这可以成为合法的 **Tool-Return Gate / Pre-delivery Harness** 研究，但应明确 consumer = Harness Adapter，decision boundary = 完整技能结束后、Planner tool-return 交付前。不能把这一实验描述为“Planner 收到 failure 再选择是否验证”的因果实验。D2/D3 的 continue branch 仍返回旧 step 的 `view_driver_state`，真实 probe 后的状态并不在这一 view 中更新；如果需要 Planner 自己依据新观察采取行动，未来必须显式给它新的合法观测且各臂信息集经过定义。

### C2：D3 决策规则与 physical probe 的操作方向相冲突

`set_gripper(+1,steps=10)` 目的是维持 EEF 位置并夹紧；D3 的 continue 条件是 `post_gap<0.06 AND (post_eef_z-pre_eef_z)>=0.03 AND fresh_frame_exists`。当前 EEF 的 **z 变化是探测过程中 EEF 的变化，不是物体相对 EEF 的真实抬升**；固定位姿夹紧 probe 通常不会带来显著 EEF z 变化。因此 D3 即使夹爪夹住对象，也可能因“没有 EEF 上升 3cm”而机械地重试。不能把这个条件称为“多源物理证据验证”或机器人视觉确认。

本次 5 次 probe 的策略观测据报告均 `post_gap>=0.06`，当前策略对这些具体输入有很高概率输出 RETRY；却不能推断所有将来的持握状态如何。需要 **从真正合法的视觉差分/可观测夹持证据中选取能区分状态的变量**，再申请下一项前瞻研究，而不是只调整阈值去追回本批试验。

### C3：审计样本并非一个共同比较的未来物理窗口

`_maybe_audit` 在技能返回的首个 `env_steps>=target` 边界取样，即真正的 time-after-trigger 可能晚于 200 步。提前结束时 `finalize` 以 `EPISODE_END` 直接审计，因此两个早退样本是**不同的观察时刻**，应标记“未达到 H 的 terminal/early-end”，并检查是任务完成、Planner 提前停止还是 infra；不能与 H≥200 的 outcome 直接混合为同一个 fixed-horizon rate。已有报告显式记录 overshoot 与短缺，这一点透明，但“6/6 固定 horizon 真值可测”表述过强。

## 三、后验工具可以验证什么

`scripts/p1_dev0_posthoc_audit.py` 在原始事件文件上**只读**复核：

1. 先验 manifest 24 / 实际有事件 / 有触发 / 未触发 / 无事件，`no_events` 不自动等于 infra；
2. D0/D1/D2/D3 task×arm 是否有真实覆盖，多少 `RETRY`/`CONTINUE_CAUTION`/`ABSTAIN`；
3. `FIXED_HORIZON` 的正 overshoot 与 `EPISODE_END` 的提前观察分别列账；
4. 读 Runner 已有 run summary 的 GPU 秒数，**显式判预算 hard-stop 是否通过**；
5. 只在当前 policy SHA256 等于已报告冻结哈希时，把已记录合法 `policy_input` 中 probe 后字段用于**离线 shadow** D2/D3，检查是否有可能提出不同决策；这只是已观察状态上的可判别性和策略覆盖性，无未执行动作的 future counterfactual。

它不读/改真值标签、不运行仿真、不启动 VLA/GLM，不根据本批结果更改原决策规则。

## 四、下一阶段新的主问题（需要新协议和新 L2 阶段）

先固定 consumer 为 **Pre-delivery Harness Adapter**，然后独立验证：

> 在工具负反馈交付 Planner 前，额外物理验证所得到的**新鲜、可区分且合法的证据**，是否使 Adapter 更好地选择直接重试或继续？这部分提升在扣除探测对夹持的机械效应后是否仍成立？

核心要求：确定真实可区别抓取状态的合法证据（如明确读取新图像视觉内容、抓爪力/本体数据可信分类，避免用审计物体坐标冒充在线信号）；保留无探测与 probe-blind 对照；**提前确认两种决策均在 DEV 可达**（且不以已测 outcome 反向调阈值），再提出具有完整冻结样本/功效与 hard-budget watchdog 的新 L2 计划。真值窗口采用定义好的固定物理步与提前结束删失建模；按任务分层并记录未触发的 ITT 分母。

下一次正式 P1 阶段**不得**继承旧 P1-DEV0 的 6.17h 消耗额度为“免费历史”，不得以新授权补跑旧冻结 3 个 skipped cell，亦不借“go on”默认解冻确认性 rollout。待研究设计有显式预算与权限，再执行。

## 五、停止规则与当前判定

- **GO（已有证据）**：P0 EERD 内部数据基线；P1 真实 hook、工具返回前拦截、合法本体观测和审计事件文件的技术可用性（生产 6 个触发）。
- **HOLD（尚无实证）**：D2 静态策略生产分支；D3 真正图像理解；主动证据选择相对于 probe 机械作用的独立收益；无偏任务泛化。
- **STOP（本阶段）**：P1-DEV0 已达预算，不能再启动任何一个该协议的补采 episode；任何参数后验改动须视为新探索版本，不能重写历史。
- **总体**：`P1_DEV0_POSTHOC_METHOD_AUDIT_READY / NEW_OUTCOMES_NOT_COLLECTED / NEXT_L2_PROTOCOL_REQUIRED`。
