# P1 · 下一阶段 L2 预注册候选：同步物理标签与 Evidence-Action 对照

> **状态：DESIGN_ONLY / NOT_AUTHORIZED / NO_NEW_L2.** 2026-10-10，基于冻结 DEV0 的已回传计数与 RPent 源码做候选协议讨论。不得用本文件或已结束的 DEV0 授权启动仿真、收集新轨迹、改在线决策或训练。若有新授权，必须另行封版 manifest、预算、代码与停止门槛。
>
> **已由用户服务器核验**：Label-time v2 5/5 tests OK；24 allocated/21 event files/6 triggered/5 probed；5 个 probe JSONL 事件均符合原 schema，无未经审核字段；probe-time 目标接触/持握参考 0。五次 Probe 的未来审计严格晚于 Probe，且 4 次在 H 后技能边界、2 次提前终局。
>
> **源码级来源（非服务器新扫描）**：`rpent/utils/p1_dev0.py:_run_probe` 直接调用 `set_gripper(+1,10)`，只记录 post RGB/合法 proprio；`_take_audit` 后续才调用 sim `check_success/sim_measurement`。 `robots/libero/tools.py:dump_state` 依据 Toolkit 的 `step_idx` 写 `world_wrist/world_wrist_NN.npy`、`images_wrist_hi/image_wrist_hi_NN.png` 等；`segment` 将 `source_step`、`mask_shape`、`box`、`world_xyz` 和 overlay 持久化，**未持久化原始二值 mask**。因此历史 world map/segment 只能作为对应旧 step 的几何上下文；不能后验等价为 Probe 结束瞬间的持握/接触真值，也不能反映 Probe 后新的目标 instance mask。

## 唯一需要验证的研究问题

当 `pi0_pick` 返回 `success=false` 时，在**同一种物理探测动作**和可见信息边界下，Harness 增加合法视觉/接触候选 Evidence 是否改善随后 `CONTINUE / RETRY / ABSTAIN` 的决策及固定物理窗口的真实效果？

拆成两个必须分开的子问题：

1. **Construct Validity**：在准确的 Probe 结束时刻 `t_probe_end`，视觉和 proprio 的候选线索与独立 audit-only `target_contact/target_held` 有何关系，尤其在“空闭合、薄物体持握、邻接但未夹住”三类中能否区分？没有两种真实类别，不做 precision/recall。
2. **Policy Value**：在与 Probe 物理影响对齐的 arm 之间，合法 Evidence 的信息使用是否改善固定 H 的物理 outcome？仅 shadow policy 分歧不可估计此量。

## 必须补齐的数据合同：三个时点、两条防泄漏通道

| 时点 | decision-visible 仅合法 | **audit-only**（不进 Planner、特征、Evolution） |
|---|---|---|
| `t_trigger` 失败交付前 | Pick 返回与现存 RGB/depth/proprio；证据来源、原始 step/env steps、图像 SHA/相机坐标约定 | target instance ID、原始 sim 几何/接触结构，用于未来匹配 |
| `t_probe_end` 结束 10 env steps 的**同一个物理状态** | 刚采集的 RGB（两视角；可选 depth/分割须标记实时生成与成本）、开度/EEF pose、帧采集环境步号、证据合法性 | 同步零物理步读取：目标 ID、机器人左右指尖与目标 instance 接触（需双方 contact）；target pose 与 EEF pose；是否被桌面/其他物体支撑；probe-time held 的物理判定及 UNKNOWN 原因 |
| `t_lift_end` 受控提升后的稳定窗口；`t_H` 统一评价环境步 | 只当授权分支明确执行 lift 后才更新可见观测；按真实成本计入动作与信息 | 目标-EEF 相对位姿稳定度、双指持续接触/脱离、支撑面与目标分离；精确 H（统一物理时间点、记录 overshoot/early censor）与任务成功 |

**重要**：目标与双指几何实际接触需要结合对象 identity、接触双方的 body/geom ID、支撑面，以及机器人自己作为“最近深度表面”的污染。单独一个最小距离、小开度、`EEF_z` 变化、局部 RGB 差分、`check_success` 或模型猜测都不足以当 `held=true` 真值。方案允许 `UNKNOWN` 和多重真值状态（contact but not retained、retained during lift、held but not completed task）。

**对象识别与时间原则**：在线语义 mask 若由 SAM3 获得，也属于有成本、有误差的**候选 Evidence**；其生成必须针对 `t_probe_end` 的新帧且使用可验证源时间戳。其 mask 不得替代独立 audit 标签。不要把当前 `source_step=t_trigger` 的历史 world map 与 `t_probe_end` 混用。

## 对照设计：先可达性，再谈因果

- **A · 机械效应对照**：`NO_PROBE+fixed_retry` 对 `SAME_PROBE+BLIND_RETRY`，识别夹紧 10 步本身是否改变持握或结果。盲化必须检查**Probe 后整个 Planner 轨迹中**的可见差异，而不只第一条返回。
- **B · 证据使用对照**：`SAME_PROBE+BLIND`、`SAME_PROBE+PROPRIO_ONLY`、`SAME_PROBE+VISUAL_PLUS_PROPRIO` 的物理动作、信息时间点、probe 成本一致；实际评估 `CONTINUE/RETRY/ABSTAIN` 可达性，禁止用永不 CONTINUE 的硬编码 arm 冒充检出能力。
- **C · 额外 lift 测试单独成层**：`SAME_PROBE+OPTIONAL_LIFT` 会改变物体状态和物理成本；必须有 `SAME_LIFT+BLIND` 对照，不能用“视觉变准”解释 lift 的机械作用。若 lift 的时间和成本与另一 arm 不对齐，不合并报告。
- **先验门槛**：冻结任务/失败触发定义/种子/独立 episode 单位、动作和成本计费、盲态策略、正负接触样本是否真正可达；没有正负标签的样本，仅报告覆盖与 UNKNOWN。历史 DEV0 的 D2 生产触发为 0、t5 为 0/8，因此需要预注册触发率可行性 Gate，不能事后删除未触发样本。
- **评测指标按层隔离**：L1 源有效率、时间对齐率、证据覆盖/弃权、独立物理接触/持握判别率；L2 按随机分配 arm 的 intention-to-treat 结果、H 时点物理成功、动作成本、信息成本、真实执行分支分母及非触发率。不得把自然语言 Planner flag 或 shadow decision 作为确认性标签/效果。
- **预算与停止**：本文件**不批准任何资源**。新的上限、设备计费、允许 episode 数、正例可行性门槛和中断准则需要用户另行批准。实现时需使用“在飞 episode 全额预算预留 + 达上限立即停止/安全终止”的硬门，不能重复 DEV0 超 GPU 6h 的 615.37s overshoot。源字段/真值不合法则 STOP；不因结果不显著而后验调门槛。

## 现在允许的结论与停止位置

现有已识别 Probe JSONL 能评价的是**来源完整性、事件时间、策略分歧、原型保守性**；不是 probe-time held/contact 准确率。旧世界图与 `source_step` 的分割产物是否在五个触发上实际存在，**本轮没有访问私有服务器再扫描**；即使存在，也不等于同步真值。

**Gate：DESIGN_GO / NEW_SIM_HOLD。** 今后只在具体硬预算与对照经批准后，才允许把本候选改成可执行的冻结协议。未获批准时停止重复做不能提高标签效度的离线启发式“分类性能”实验。
