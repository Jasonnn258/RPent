# P1 · Visual Evidence v0.1 — 离线研究报告(2026-10-09/10)

> **协议**:VE-v0.1(夜间自主研究阶段,只读离线;禁止新仿真/补跑 DEV0/改在线 Runtime/训练)。
> **核心问题**:合法视觉信息能否区分「夹爪闭合」「物体贴近夹爪」与「真实可能持握」,
> 相对现有 proprio-only 判据(D2 gap<0.06 / D3 gap∧ΔEEF_z)有无增量信息价值?
> **数据**:5 个真实 probe 前后 RGB 对照板(`artifacts/p1_dev0/visual_review/`,私有不入 Git)
> + 本地 21 个 DEV0 episode 全量合法观测(states.json / recipe / run.log / world npy)。
> **纪律**:视觉判定(含模型视觉)一律标 MODEL_VISION 主观判断,绝不写成物理真值;
> 审计真值(check_success 等)不进任何决策臂特征;单帧与前后时序不混合统计。

---

## Phase 0 · 状态与数据盘点(完成)

- 研究上下文(CURRENT_STATE/DECISION_LOG/AGENTS/独立审计/执行报告)已读;当前 Gate
  `FIVE_PRIVATE_RGB_BOARDS_WRITTEN / PHYSICAL_GRASP_UNVERIFIED / NEXT_L2_HOLD`。
- 数据本地性:5 组对照板、5×2 probe 原始 PNG、21 episode 完整输出(含 **world/world_wrist
  逐像素 3D 坐标 npy**、wrist_meta 相机内外参、states.json 每 planner step 合法 proprio、
  run.log 含 planner 叙述)全部在本机;vanilla 187 集与 EERD-A 脱敏 jsonl 不适用(无图像)。
- 结论:Phase 3 底座 = 5 probe 案例 + 21 集合法逐 pick 对照表(见 §P3)。

## Phase 1 · 五组图像可辨识性分析(完成)

### 1.1 逐案例判读(MODEL_VISION,主观;对照板 = 3×2 网格)

| 案例(臂) | Agentview 判读 | Wrist 指间区判读 | 差分形态 | 视觉判定 | 主要阻碍 |
|---|---|---|---|---|---|
| t3_s1002 (D1) | 碗在夹爪下方偏右、静止;爪指张开,闭合角度不可见 | 碗内壁花纹充满画面,爪尖在底缘;前后近同 | 集中(夹爪+前景) | **UNCERTAIN**(倾向未夹持) | 近水平视角、爪尖分辨率、碗沿遮挡接触点 |
| t9_s1002 (D1) | 爪悬停深色抽屉面上方;碗在左侧台面;pre→post 指端并拢可见 | 深色抽屉质量主导,底缘暗色爪尖剪影;指间无可辨物体材料 | 集中(夹爪鬼影/棱线) | **UNKNOWN**(指间内容) | 暗对暗对比度、抽屉遮挡、分辨率 |
| t9_s1003 (D1) | 爪在红纹杯垫上方;碗在爪尖下方/旁侧,**未移动** | 碗在爪尖前下方,**不在指间**;前后近同 | 集中(臂轮廓) | **CONFIDENT 空闭合**(邻接非夹持) | — |
| t9_s1004 (D3) | 碗**像素级不动**;diff 仅臂缘亮线 | 整帧横向视差滑动(黄沿带位移),无夹持内容 | wrist 巨幅(mean 45.8)但为**纯相机运动** | **高置信 (B) 纯臂/相机运动、无物体接触** | 视差伪装(天然对抗样本) |
| t9_s1005 (D3) | 爪尖闭合;碗在爪尖下方偏侧、未动;碗区差分≈0 | 碗在爪前方下方,不在指间;无变化 | 全局低幅噪声 | **CONFIDENT 空闭合** | — |

配套客观差分统计(review_index.json):wrist absdiff mean =
9.08 / 5.24 / 4.26 / **45.83** / 7.55;t9_s1004 的最大差分恰是视差而非信息——
**差分幅值与证据量反相关**的最强实例。

### 1.2 合法 proprio 交叉分析(事件文件 pre/post_legal,客观)

| 案例 | pre_gap | post_gap | Δ(闭合进度) | ΔEEF_z | 闭合结局 |
|---|---|---|---|---|---|
| t3_s1002 | 20.41mm | **2.48mm** | −88% | −3.4mm | 闭到机械地板 |
| t9_s1002 | 69.26mm | **2.67mm** | −96% | +1.8mm | 闭到机械地板 |
| t9_s1004 | 53.72mm | **3.07mm** | −94% | −2.8mm | 闭到机械地板 |
| t9_s1003 | 7.31mm | **6.96mm** | −5% | +0.7mm | **停住在地板之上** |
| t9_s1005 | 4.53mm | **4.53mm** | 0% | −1.2mm | **完全未动** |

关键推理:69mm→2.67mm 证明 10 步闭合指令的行程能力;7.31→6.96 与 4.53→4.53
**不是控制节奏问题,是物理阻挡**(指端已压在物体/环境上)。视觉对这两个停住案例的
判读恰为「碗在爪尖下方/前方、不在指间」——**proprio 的 stall 检出接触,vision 裁决接
触方位**,这是 D2(只看 gap<0.06 → 5/5 CONTINUE)与 D3(dz 门槛 → 5/5 RETRY)都不
具备的区分维度。

### 1.3 21 集逐 pick 合法对照(scripts/p1_ve01_legal_extract.py;22/29 有旗标)

- flag=T 末端 gap:**1.8–17.6mm**(med 5.0mm);flag=F 末端 gap:**2.2–79.3mm**(med 29.4mm)。
- **重叠区不可分**:gap∈[2.2,4.7]mm 同时含 6 个 T 与 2 个 F;薄沿持握(1.8mm/4.9mm T)
  与空闭合(2.2mm F)在 gap 轴上同带。
- planner 自己在 run.log 承认同一歧义:"success:false but the fingers read 0.0022 —
  ambiguous (could be squeezing the thin rim)" / "gripper closed to 0.0049 (small gap →
  holding something)"——**运行时决策层确实缺乏持握证据原语,研究问题成立**。
- 附:触发集的 run.log `tool<` 行实为 **retry 的返回**(原始失败被 pre-delivery hook
  消费),与 C1 拦截语义一致。

### 1.4 失败类型分类(视觉可辨识性的失效模式)

1. **指间内容不可分辨**(5/5):256px wrist 下爪尖间物体材料无法可靠识别——分辨率+视角为主因;
2. **暗对暗对比度**(t9_s1002):深色物体×深色支承面,无纹理可用;
3. **支承面/容器壁遮挡**(t3_s1002, t9_s1002):接触点恰被碗沿/抽屉挡住;
4. **相机-机器人运动伪装**(t9_s1004):整帧视差产生巨幅差分但零信息——任何基于
   裸差分幅值的判据在此必假阳;
5. **邻接-夹持歧义**(t9_s1003, t9_s1005):碗贴近爪尖但(视觉判)不在指间,与 gap 停住
   信号需要联合解读,单模态均不足。

### 1.5 Phase 1 结论(证据可靠性)

- **Agentview 可靠提供**:夹爪存在/位姿(5/5)、闭合可见性(4/5)、**碗是否移动**(5/5
  判未移动)——"probe 未造成物体位移"是可用的(负向)证据。
- **Wrist 不可靠提供指间内容**(0/5 可辨);其差分幅值在视差下完全失效。
- **无任何模态能在 probe 时刻(无提升动作)直接证明持握**;lift(垂直搬运)是工具/
  planner 事实上的持握证据,而 probe 恰无 lift——这正是证据缺口的形式化描述。
- 主观视觉标签效度:2/5 CONFIDENT 判定与 proprio stall 信号**相互独立地一致**,
  但样本 5、无持握真值,不可量化准确率。


---

## Phase 2 · Visual Evidence Prototype(完成)

**交付**:`analysis/research_context/p1_ve01_evidence.py`(确定性模块:numpy+PIL,
无网络/无 GPU/无训练)+ `test_p1_ve01_evidence.py`(**19/19 合成测试通过**)+
`scripts/p1_ve01_run.py`(5 真实案例 → `evidence_claims.json`)。

EvidenceClaim 结构:source(路径+SHA256)/validity(缺失·**同字节复用帧**·泄漏键
自检)/proprio_closure(**闭合结局三态**)/visual_camera_motion(视差护栏)/
visual_change(变化集中区,无语义)/geometric_context(腕视世界图近场几何)/
inter_finger_content(**一律 ABSTAIN**,Phase 1 实证 0/5)/model_vision_external
(主观参考,显式标注)/state_class/sufficiency/suggested_action。

标定常数(全部来自 21 集合法观测,非拍脑袋):机械地板带 FLOOR_MAX=3.5mm
(3 例空闭合 2.48/2.67/3.07mm);模糊带 0.8mm;近场半径 20mm;整帧变化阈 40%。

关键方法点:
- **闭合结局三态**:CLOSED_TO_FLOOR(闭合行程无阻挡)/ STALLED_ABOVE_FLOOR
  (命令闭合但停住 = 物理阻挡;以 69mm→2.67mm/10步 的实测行程能力排除"控制
  节奏不足"解释)/ AMBIGUOUS。
- **视差护栏两条独立判据**:(a) 相位相关全局平移 + 对齐后残差显著下降;
  (b) 整帧变化占比 >40%(深度相关视差下各深度位移不同,单一平移原理上对不齐,
  残差不降≠无相机运动;t9_s1004 实测对齐残差 50.0 > 原始 45.8)。
- **几何近场**:腕视世界图(epoch 自有 SAM3/深度管线合法产物)→ 距 EEF 最近表面
  距离 + 近场质心像点。5/5 案例近场质心稳定落在归一化 (0.78-0.79, 0.49-0.50)
  = 腕视**中下=指间投影带**,验证几何层的稳定性。

5 案例输出(节选):

| 案例 | 闭合结局 | dist_min | 视差旗 | 状态分类 |
|---|---|---|---|---|
| t3_s1002 | CLOSED_TO_FLOOR | 10.4mm | 无 | CLOSURE_UNOBSTRUCTED |
| t9_s1002 | CLOSED_TO_FLOOR | 19.0mm | 无 | CLOSURE_UNOBSTRUCTED |
| t9_s1003 | STALLED_ABOVE_FLOOR | **0.5mm @(213,128)=指间带中心** | 无 | CLOSURE_OBSTRUCTED_LOCATION_UNRESOLVED |
| t9_s1004 | CLOSED_TO_FLOOR | 11.5mm | **整帧视差** | CLOSURE_UNOBSTRUCTED |
| t9_s1005 | STALLED_ABOVE_FLOOR | 9.9mm | 无 | CLOSURE_OBSTRUCTED_LOCATION_UNRESOLVED |

帧新鲜度:5/5 frame_age=1.7-1.8s(probe 墙钟−trigger 墙钟),全部新鲜。

## Phase 3 · 六臂离线对照(完成)

`scripts/p1_ve01_arms.py` → `arms_comparison.json`。臂:B0(工具旗标)/B1(冻结
D2 gap<0.06)/B2(冻结 D3 gap∧Δdz)/B1′(本轮新增 stall 三态)/B3(纯视觉:
护栏+几何,设计上永不授权 CONTINUE)/B4(B1′⊕B3 联合)。

| 案例 | B0 | B1(D2) | B2(D3) | B1′ | B3 | B4 | retry成功(评) |
|---|---|---|---|---|---|---|---|
| t3_s1002 | RETRY | **CONTINUE** | RETRY | RETRY | RETRY | RETRY | T |
| t9_s1002 | RETRY | **CONTINUE** | RETRY | RETRY | RETRY | RETRY | F |
| t9_s1003 | RETRY | **CONTINUE** | RETRY | RETRY+ESCALATE | RETRY+ESCALATE | RETRY+ESCALATE(指间平面接触) | F |
| t9_s1004 | RETRY | **CONTINUE** | RETRY | RETRY | RETRY(图像无效) | RETRY | F |
| t9_s1005 | RETRY | **CONTINUE** | RETRY | RETRY+ESCALATE | RETRY | RETRY+ESCALATE(指下接触) | T |

**决策相关状态区分度**:B0=1,B1=1,B2=1,**B1′=2,B3=4,B4=4**。

- 可辨识率(指间内容):0/5 → 结构性弃权;覆盖率(能给出有效证据主张):5/5(B1′/B4);
  不确定率:B1/B2 把 5 个不同物理状态映射到同一决策,不确定性被**掩盖**而非报告。
- **策略分歧**:D2 与其余所有臂在 5/5 上分歧;且 D2 的 CONTINUE 恰好落在 2 个
  "闭合受阻"案例上——D-020 预警的"把机械闭合误认成功"在逐案例层面坐实。
- **不可估计量(如实)**:持握检出率/准确率——5 案例无持握正例、无 probe 时刻
  物理真值;audit 真值是 retry 的结局,不是 probe 状态的标签。
- 探索性(EXPLORATORY,n=5):**pre_gap 预测 stall**——stall 案例 pre_gap ≤7.3mm,
  闭合到底案例 pre_gap ≥20.4mm。失败时爪已近闭 → probe 前即可预判"接触型失败",
  或可直接跳过 probe(证据分诊的零成本前缀)。

## Phase 4 · 对抗性反例测试(完成,10/10 PASS)

`scripts/p1_ve01_adversarial.py` → `adversarial_results.json`:

| 场景 | 输入 | 观察结果 | 机制 | 判定 |
|---|---|---|---|---|
| ADV1 空夹爪完全闭合 ×3 | 真实 t3_s1002/t9_s1002/t9_s1004 | 闭合结局=无阻挡;B1′/B3/B4 零 CONTINUE,指间弃权 | 无阻挡闭合认证+弃权,附薄沿 caveat | PASS |
| ADV2 物体被遮挡/暗对暗 | 真实 t9_s1002 | 指间 ABSTAIN;B3 无材料主张 | 只断言可复核事实 | PASS |
| ADV3 wrist 前后未对齐 | 真实 t9_s1005 关掉翻转校正 | frac_changed=0.694 → 图像隔离 | 整帧变化护栏 | PASS |
| ADV4 相机-臂运动 | 真实 t9_s1004 | raw=45.8 但 WHOLE_FRAME_DEPTH_PARALLAX → 隔离 | 深度视差判据 | PASS |
| ADV5a 帧复用(过期) | post=pre 同字节 | INVALID_STALE_FRAME → 默认 RETRY | SHA256 字节级检测 | PASS |
| ADV5b 帧缺失 | ghost 路径 | INVALID_SOURCE_MISSING | 缺文件护栏 | PASS |
| ADV6 证据矛盾 | 无阻挡闭合+爪平面近场材料(构造) | B4=TENSION → ESCALATE,不消解为强主张 | 张力态升级 | PASS |
| ADV7 全局性质 | 全部 7 个 claim 输入 | CONTINUE 输出数=0 | 性质:新臂无持握证据不得 CONTINUE | PASS |

## Phase 5 · 五问作答与判定

**Q1 现有图像是否提供可辨识的目标-夹爪关系?**
- Agentview:**部分可辨识**(Verified):夹爪存在/位姿 5/5、闭合可见 4/5、
  "碗未移动" 5/5(MODEL_VISION 主观 + 差分客观佐证)。
- Wrist 指间内容:**不可辨识**(Verified,0/5,256px 结构性不足)。
- 腕视世界图几何:**可辨识且可量化**(Verified,合法资产,近场质心 5/5 稳定)。

**Q2 视觉相对 gripper-gap/EEF 增加什么信息?**(核心增量,Verified 于本 5 例)
1. **图像有效性裁决**:视差/误对齐/过期/复用/缺失的隔离——proprio 完全没有的维度;
   裸差分在 t9_s1004(最大差分)必假阳。
2. **接触方位**:stall(proprio)只说"有阻挡",几何近场说"在爪平面(指间投影带)
   还是指下"——t9_s1003 的 0.5mm@指间带中心是两模态互相印证的联合证据,
   任一单独给不出。
3. gap **静态阈值**在重叠区原理上无分离力(flag=T 1.8-17.6mm vs F 2.2-79mm,
   薄沿持握 1.8mm T ≈ 空闭合 2.2mm F);**主动闭合结局(stall-band)**才有
   "接触存在性"信息。ΔEEF_z 在 pose-hold probe 下机械性不可满足(0/5),信息≈0。
4. 状态区分度:1/1/1(B0/B1/B2)→ 2/4/4(B1′/B3/B4)。

**Q3 哪些情况必须 abstain?**(全部已实现为机制,非口头原则)
指间内容(256px 一律);暗对暗/遮挡;视差污染;帧同字节复用/缺失/龄>120s;
证据张力(无阻挡闭合∧爪平面材料);**probe 无 lift 时的一切"已持握"结论**。

**Q4 是否存在信息充分样本支持与 D2/D3 不同的候选决策?**
- **不同的动作:不存在**(本 5 例无一有持握支持证据,正确动作都是 RETRY);
- **不同的决策理由结构:存在**(Verified):3 例"闭合无阻挡→重试且**无需更多
  证据**"vs 2 例"受阻→重试但**升级标记**(hi-res/lift-test 有信息价值)"。
  D2 对 5/5 一律 CONTINUE(含 2 个接触案例=系统性假继续风险坐实);D3 对 5/5
  一律 RETRY 但理由(dz)与状态无关。B1′/B4 首次在本数据上把"证据值不值得再买"
  变成可判定的三/四态问题——这正是 P1 "何时值得追加证据"的决策原语。

**Q5 是否值得新前瞻 L2?最小验证什么?**
**值得,但必须是修正设计后的最小 L2**(GO-设计/HOLD-执行,需用户新授权):
- 最小验证集(建议 12-24 episode,任务分层配额防 t9 集中):
  (a) probe 改"闭合+受控提升 2-3cm"组合,使 lift/dz 类判据重新可用并与
      stall-band 联合(本轮已证 pose-hold 下 dz 恒不可满足);
  (b) 触发时刻 hi-res wrist 可用性(现存 5 帧/集,覆盖未验证);
  (c) stall×几何方位联合对"接触"的检出与误报(需含真实持握正例——本轮 0 正例
      是最大空白);
  (d) 两分支可达的 pre-delivery 消费者接线(CONTINUE 路径真实执行)。

**最有价值的三个研究发现**:
1. **probe-stall 三态信号**:以 69mm→2.67mm/10步 实测行程能力为对照,7.0/4.5mm
   停住=物理阻挡;把 D2"gap<0.06"的系统性假继续问题转化为可分诊证据
   (3 无阻挡 vs 2 受阻,并含零成本前缀预测器 pre_gap≤7.3mm)。
2. **薄沿持握与空闭合在 gap 轴上原理不可分**(1.8mm 真 vs 2.2mm 假 + planner
   自述歧义):lift 才是运行时事实持握证据;probe 时刻无 lift → **任何模态都不
   可能断言持握**,视觉的真实增量在"有效性裁决+接触方位",不在"看见夹住"。
3. **视差伪装的实证与护栏**:最大 wrist 差分(45.8,63.5% 像素)恰是零信息的
   纯相机运动;整帧占比+SHA 新鲜度+翻转对齐构成可复现护栏,10/10 对抗通过。

**未解决问题**:5 例无持握正例与 probe 时刻物理真值(检出率不可估);stall 的
阻挡物在指间还是指外只有主观视觉+几何间接佐证;MODEL_VISION 判读不可复现
(商用模型无固定种子);hi-res 触发时刻覆盖未验证;单任务族(t3/t9)、n=5。

**分级**:可辨识性/区分度/对抗护栏 = **Verified**(本数据);pre_gap 预测器、
B4 联合状态的信息价值 = **Exploratory**;"修正 L2 可改善结局" = **Hypothesis**;
"D2 阈值在重叠区可调好"/"裸差分可判持握" = **Unsupported**。

**判定:GO(离线证据原语层,已达成)/ 下一阶段 HOLD(最小 L2 需新独立授权+
设计修正:lift-probe+正例采集+任务分层)**。不补跑 DEV0;不改在线 Runtime;
私有图像与产物留 artifacts/,不入 Git。

