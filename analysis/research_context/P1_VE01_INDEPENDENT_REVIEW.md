# P1 Visual Evidence v0.1 · 独立源码复审（2026-10-10）

> **审查对象**：`32af61b` 已提交的 `P1_VE01_VISUAL_EVIDENCE_REPORT.md`、`p1_ve01_evidence.py`、`p1_ve01_legal_extract.py`、`p1_ve01_run.py`、`p1_ve01_arms.py`、`p1_ve01_adversarial.py` 与测试。**本审查读取 GitHub 提交的源码及其报告，没有直接运行用户服务器上私有图像/事件，也没有独立核对昨晚 19/19 或 10/10 的运行日志。** 原报告数据、冻结 DEV0/A0/Stage R 不改。
>
> 新增 `scripts/p1_ve01_safe_arms.py`（**VE-v0.1.1 保守独立审计层**）和 `test_p1_ve01_safe_arms.py`。这两项尚需服务器运行，无新仿真、训练或 Runtime 接线。

## 科学判定

- **KEEP / 可归档为已有代码和报告观察**：存在 5 对时序 RGB+合法 proprio，Wrist 源需纵向对齐；5 例静态 D2=CONTINUE、原 D3=RETRY 的决策分歧；VE-v0.1 设计了闭合轨迹分箱、图像质量护栏、深度几何和安全弃权的离线原型；夜间报告称 19 项合成测试和 10 项对抗均通过。真实前瞻 action effect 没有产生。
- **DOWNGRADE / 本组探索性信号**：5 个 `post_gap` 样本可分为“接近观察到的最小开度区”3 个，以及“较大开度且短时变化很小”2 个。后者**可能**是接触、非目标物体碰撞、机械/控制约束、测量误差或闭合速度/动作饱和；只凭两端点+单个 69mm→2.67mm 例子，不能**排除**控制节奏/servo 差异并证明两个样本物理受阻。
- **BLOCK / 证据不支持**：`world_wrist/world_wrist_NN.npy` 是合法深度投影的可见表面世界图，`nearest_surface_metrics` 只计算到 EEF 的最近表面，**无机械手自身分割或目标 instance mask**，所以 0.5mm 不是“目标物体接触”“指间有物体”，也不能据此断言物体在指间平面。
- **BLOCK / 不支持的效应或正确性**：B1′/B3/B4 都在代码中固定不允许 CONTINUE，故 ADV7 的零 CONTINUE 是**输出约束/性质测试**，不是持握检出率、低假阳率或相比旧臂的性能收益。5 例全 RETRY 的主张也未由 probe-time 独立物理标签确证；旧 D2 五次 CONTINUE 更准确的称谓是“**unsupported continue risk**”，而非“已确证物理假继续”。
- **NON-ISOLATED / 模态和数据切点**：自称 B3“视觉-only”，但使用 `dist_min=||world_wrist-EEF_pos||`，其中 EEF 坐标来自 proprio；它是**RGB/Depth+robot proprio 几何融合**。另外 `world_wrist` 与 EEF 使用触发前 step 快照，不能直接称为 probe 后接触位置。图像像素改变量大、整帧占比大可以是相机/机器人运动、光照/物体运动等，单靠该标量无法鉴定“纯深度视差”。
- **REFERENCE / 弱标记**：`p1_ve01_legal_extract.py` 通过正则扫描 **Planner 的自然语言 think** 判断部分 pick success，并与 states 的 gripper 值配对。这个 `flag=T/F` 不是独立 held-grasp 真值，且可能有 run.log 关联误差；“薄沿持握 1.8mm 真 vs 空闭合 2.2mm 假”的**物理真伪**目前无独立证据，仅可写“日志内 flag 分组的开度范围有重叠（待字段级对齐核查）”。
- **CALIBRATION LEAKAGE / 强性能声明不可取**：FLOOR_MAX=3.5mm、AMBIGUOUS=0.8mm、近场阈值及整帧变化阈值均在这一极小、全失败案例集合上形成/检验；同一 5 个样本上的“3/2、四种状态、10/10 对抗”是 **开发集自洽性**，不是独立 test 的泛化能力。
- **VALIDITY CONTRACT / 新缺陷**：原 `arm_b3/arm_b4` 无先验源有效性 Gate，可能在缺图、超时、缺几何或被判 `INVALID_FORBIDDEN_KEY` 时仍读取内部字段甚至报错。原 `build_evidence_claim` 对同 SHA 视图判 `INVALID_STALE_FRAME`，但同字节不等于“拍摄时间不新”；相反像素不同也无法证明时间新鲜。以后要用**相机/环境实际时间戳**判断时效。

## v0.1.1 本轮已实施的保守离线纠偏

新 `scripts/p1_ve01_safe_arms.py` **不覆盖、修改或重新定义 VE-v0.1 历史文件**，且：
1. 非 `VALID`、标记 `STALE`、指间内容却宣称已证明抓持、缺失/无穷 proprio、gripper 数值与原分箱不一致、相机有效性无证据：全部返回 `RETRY+ABSTAIN`；
2. 合法 `CLOSED_TO_FLOOR` 只写 `NEAR_MIN_GAP_OBJECT_PRESENCE_UNKNOWN`（薄物体仍可能夹持）；`STALLED_ABOVE_FLOOR` 只写 `GAP_PLATEAU_CAUSE_UNKNOWN`；
3. 近 EEF 最近表面只写 `SURFACE_NEAR_EEF_IDENTITY_UNKNOWN`，机器人自身/台面/目标/深度噪声身份均未知；不再写“目标接触”；
4. 所有输出 `object_contact=UNKNOWN`、`held_grasp=UNKNOWN`，按原 5 例汇总；这是**保守解释与失效保护演示**，不能拿“0 误报”当检出性能；
5. 合成测试覆盖异常/过期、类别与数值冲突、近场表面身份不可辨、薄物体无法排除、完整分母检查。**提交不等于测试 PASS，服务器运行后再认定**。

## 下一科研门槛：究竟如何证明“接触位置”和“后续持握”？

优先利用已有数据**只读**检查：

- 有关 robot self mask / 目标 instance mask 的真实可用性，特别是最近表面像素究竟是爪指、物体还是支承面；如果没有就输出 UNKNOWN；
- 时序帧的实际采集时点、触发事件步号与物理 probe 的 step；视觉有效性先做独立校准，不以同组 5 条案例拟合阈值再评价；
- 需要**独立于 Planner 描述/工具 flag 的物理真值**与目标在 probe 后固定窗口的归属，才谈得上“假继续”“接触检出率”和控制收益。优先制定离线可审核标签合同；不自动开始新仿真。

**当前判定**：`VE01_REPORTED_OFFLINE_PROTOTYPE / SCIENCE_CLAIMS_PARTIALLY_DOWNGRADED / V011_SAFE_GATE_CODE_COMMITTED_TESTS_UNRUN / NEW_L2_HOLD`。
