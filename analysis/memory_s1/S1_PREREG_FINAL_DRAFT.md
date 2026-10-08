# S1 预注册终版草案(v2):Historical Memory on Twin-Swap Tasks

> 生成:2026-10-08 | 状态:**v2 草案(经终审修订),取代 v1**
> (v1 = commit 0c171c4 `S1_PREREG_DRAFT.md`,归档不改原文)
> 上游:S0(NOT SUPPORTED,任务族属性)→ S1_FEASIBILITY_REVIEW
> (GO 有条件)→ 审计一/二(0c171c4)→ 终审意见书
> `S1_PREREG_REVIEW.md`(六项修订,本文件逐条落实)
> 本轮零 rollout、零源码/环境修改、零训练;Stage R 冻结判定未触碰。
> **冻结版定稿与 S1-DEV0 执行均需用户单独批准。**

## 0. 研究问题与假设(最小化)

**RQ**:在"当前观察不含解、合法历史含解"的反事实任务上,历史信息
对决策的因果效应多大(C3 上界),紧凑 typed-state 表示能兑现多少(C4)?

- **H0(能力资格,前置门)**:同场景位置消歧指令下(C0),Pi0.5+
  planner 链路能选对并抓对目标(L1 ≥ 门槛,起点 65%、分前缀集 ≥50%)。
  **不过 ⇒ 能力混入,S1 任务族资格 FAIL,STOP**(修任务/指令,
  不修结论,不涉历史必要性判定)。
- **H1(当前观察不可区分性)**:B0(C1)在 L1 上不高于机会水平
  (2 选 1 = 50%),且选择与前缀集正交(判据见 §4)。显著 >50% ⇒
  任务泄漏 ⇒ STOP。
- **H2(历史充分性/信息上界)**:C3−B0 on L1 ≥30pp 且 C3 L1 绝对值
  ≥85%(信息完备的 2 选 1 应接近全对)。
- **H3(表示可兑现性)**:C4−B0 on L1 ≥15pp(S0 §四传统)。
- **H4(负对照,重定义)**:
  - **H4a 格式安慰剂(门)**:|C2a−B0| on L1 ≤ ε(起点 10pp)。
    超限且 C2a 显著高于 B0 ⇒ 注入格式混杂,全部收益不可解释 ⇒ STOP。
  - **H4b 内容敏感性(方向性,非门)**:预期 C2b < B0(被反转历史
    主动误导)。C2b ≤ B0−δ(起点 10pp)⇒ 内容利用成立;C2b ≈ B0 ⇒
    "内容未被利用"如实报告(解释降级);C2b > B0 ⇒ 异常,按混杂排查。
- **H5(探索)**:B0 内部策略(EEF 残差投机)、C3−C4 差分解
  (跟踪/压缩/人工整理三成分)、L2/L3 诊断剖面。

## 1. 任务与历史构造(冻结要素)

- 基任务:libero_spatial t9 家族变体(新增 DEV bddl,注册走 t3/t7
  先例;不动现有 10 任务与 init states;TEST 用独立变体+独立 seed 批)。
  **语言必须全通道一致**(新 bddl 主路径;理由:runner 层覆盖指令时
  `view_driver_state` 仍透出 bddl 原文的位置消歧语言,构成泄漏,
  见 REVIEW §四 R5)。
- 历史指称指令(C0 除外,两前缀集同文):"Pick up the bowl that
  started on the wooden cabinet and place it on the plate."
- 历史对(A/B):同 task、同 seed、同语言;A 前缀 = 交换双碗动作流,
  B 前缀 = 等长中立动作流(接触台面不碰碗,伸至中立点→返回);两
  前缀末尾统一接同一段 homing 动作流收敛同目标。前缀 = 录一次 →
  PREFIX 逐位重放(Stage R 机制,R0 32/32 逐位一致背书)。
- 正确动作:A = 夹灶面碗,B = 夹柜顶碗;判分 = 实例级 bddl 目标
  (`On akita_black_bowl_1 plate_1`),check_success 自动判,仅仪器侧
  使用。
- 观测交接:审计一 P1 修法逐字保留(重放后擦 out_dir 工件 +
  `dump_state(step_idx=0)` 重 dump,零库改动;DEV0 断言验收)。

## 2. 六臂对照与构造纪律

| 臂 | 指令 | 注入内容 | 构造纪律 |
|---|---|---|---|
| **C0 能力锚** | **位置消歧**(随前缀集换位:A 集"the bowl on the stove"、B 集"the bowl on the wooden cabinet") | 无(fresh planner) | 消歧只走指令语言→观察接地(pi0_pick 为 prompt 驱动闭环原语,无像素目标参数);验证链路能力,非历史 |
| **C1 B0 Current-only** | 历史指称(同文) | 无(RPENT_MEMORY_TRIGGER=off) | fresh planner,重放后启动 |
| **C2a Format-only** | 历史指称(同文) | 与 C4 同格式、交换事实槽位中性化(仅中性动作条目) | 检验格式安慰剂 |
| **C2b Swapped-history** | 历史指称(同文) | 事实反转的历史(A 集注 B 事实、B 集注 A 事实),格式与 C4 全同 | 检验内容敏感性 |
| **C3 Oracle-history(上界)** | 历史指称(同文) | 首帧空间锚+全程轨迹叙述 | 只基于**合法视觉历史**(重放帧 SAM3 导出);**允许人工核验**但仅限合法来源可导出事实,**每处修订留痕**(diff+溯源,支撑 C3−C4 差分解) |
| **C4 Typed-state(可实现)** | 历史指称(同文) | 紧凑 typed 关系(如 `moved(bowl_from_cabinet, to=stove)`) | **全自动管线**:SAM3 跟踪→状态更新→压缩,离线一次生成**冻结**,零人工触碰(Stage D sidecar 纪律) |

**全臂共同条款**:
- 一律 **api planner**(排除文件后端 extra_dirs 通道,审计一 P5);
  同 prompt 模板、同 turn 预算、同温度、同注入机制(RPENT_MEMORY_TRIGGER
  门控,仅内容来源按臂受控)。
- **C3/C4 共同排除条款**:禁止读取 sim 隐藏真值、BDDL 实例 ID、
  obj_of_interest、check_success 真值;合法来源 = 重放帧(SAM3
  分割)、dump_state 级 state(EEF/夹爪/名字)、前缀动作流元数据。
  typed/叙述谓词一律用**空间起点标签**(bowl_from_cabinet),全程
  不需要实例 ID(指令+真历史联合决定正确动作)。
- C0 与 C1 唯一差异 = 指令指称方式(位置 vs 历史);C2a/C2b/C3/C4
  与 C1 唯一差异 = 注入内容。

## 3. 指标(三级;H0-H4 主判一律绑 L1)

### L1 首次目标选择正确率(主指标)

- 定义:episode 内**首次使任一孪生碗产生 ≥ 位移阈值**(起点 1cm,
  DEV0 噪声底定稿)位移的 pick 尝试,其移动实例是否 == 该前缀集+
  指令下的正确实例。**仪器侧判定**(sim_measurement 离线归因,
  planner 不可见);不依赖任务完成,隔离执行噪声;不使用 pi0_pick
  自报 success(本体感受判据与"抓对碗"不等价,REVIEW R2)。
- **undecidable 三类分桶**:
  (a) `L1_NO_EFFECTIVE_PICK`——至 episode 终无任何碗达到位移阈值;
  (b) `L1_PROTOCOL_ANOMALY`——单 pick 窗口内两碗同时位移,按 infra
    纪律 ≤3 重试,仍现则该 episode 作废入 infra 账;
  (c) `L1_UNATTRIBUTABLE`——归因证据不足唯一实例。
  (a)(c) 不计分子分母、单独报告占比;(b) 作废重试。
  **测量质量门**:undecidable 率 >20%(起点)⇒ 仪器化不合格,修仪器
  先于任何判定(DEV0/DEV 处理)。

### L2 实例级 BDDL 任务完成率

- check_success(实例级目标谓词)自动判;**单独报告,不绑任何门**。
- 次级:L2 | L1-correct 条件成功率(执行环节纯度,与 C0 锚互证)。

### L3 Stage Q 稳定抓取契约(仅诊断)

- `stageQ_prereg.md` §2 双契约公式**逐字复用**:ACQUISITION = 任一
  测量点 check_success ∨ FG 契约(dz≥+0.03 ∧ dxy(obj,EEF)≤0.10,
  基准 = 该 rollout 自己 pick 后测量);STABLE = i*(首个 ACQUISITION
  点)存在 ∧ i* 至终点全测量点满足(check_success ∨ FG 契约)∧
  终点满足 ∧(任一点 check_success ∨ i* 后测量点数 ≥
  HOLD_MIN_POINTS=4)。阈值复用 Stage P verifier 参数,不重定义。
- 用途:区分"决策对但抓取不稳"与"决策错";**不设门,不进判定**。

### 过程指标

EEF 残差(A/B 决策点)、物体位姿差带、注入次数/token、turns、
undecidable 分桶占比、infra 错误分类(C3 事故账纪律)。

## 4. 统计设计(单位/配对/区间/泄漏 STOP)

- **独立样本单位 = cell = (任务变体, seed)**。同 cell 内各 episode
  共享同一次 PREFIX 重放 ⇒ 不独立;**跨臂比较一律同 cell 配对**,
  差值的 CI 用 **cluster bootstrap over cells**(Stage R 先例)。
  配对差符号约定(臂顺序、方向)写入分析脚本注释,防符号坑。
- **A/B 配对平衡**:每 cell × 每臂恰好 A-前缀集、B-前缀集各 1
  episode(C1 指令跨集同文;C0 指令随集换位)。缺失 episode 只能因
  infra 作废且须补跑至平衡,不平衡 cell 剔除并报告。
- **CI**:比例用 Wilson score 95%(单侧用于 H1);配对差用 cluster
  bootstrap 95%(cells 重抽样,≥10000 次)。
- **H1 判据(两条同时)**:① B0 L1 点估计 ≤50% 且单侧 95% Wilson
  CI 上界 ≤60%(起点);② B0 选择与前缀集正交:A/B 两集上 L1 分别
  ≤ 50%+10pp(起点)。
- **泄漏 STOP(三条,重申)**:(i) B0 显著 >50%(单侧精确二项
  p<0.05)⇒ 任务语言/结构泄漏 STOP;(ii) 某前缀集上 B0 系统性超
  阈 ⇒ 物理残差通道泄漏 ⇒ 转审计二 §三后备(对称化加强/静置段),
  仍不过 STOP;(iii) C2a 显著 >B0(超 ε)⇒ 格式安慰剂 STOP。
- **n**:DEV 权力分析定 cell 数后冻结;起点 = 2 任务变体 × ≥12
  seed = 24 cells/臂(每臂 48 episodes);TEST 用独立 seed 批 + ≥2
  套指令措辞变体,一次跑。总量超开发机 ~1h 高负载即按铁律转
  Training Task(与用户确认)。

## 5. 数值门槛汇总(全部 = 建议起点,DEV 定稿后进冻结版)

| 门 | 起点 | 绑定 |
|---|---|---|
| H0 C0 能力资格 | 池化 L1 ≥65%,分前缀集各 ≥50% | FAIL → STOP |
| H1 ① CI 上界 | 单侧 95% Wilson ≤60% | 违 → 视显著性 STOP |
| H1 ② 正交 | 各集 ≤50%+10pp | 违 → 后备/STOP |
| H2 | C3−B0(L1)≥30pp ∧ C3 L1 ≥85% | 主判 |
| H3 | C4−B0(L1)≥15pp | 主判 |
| H4a ε | 10pp | 超限 STOP |
| H4b δ | 10pp(方向性) | 解释性 |
| L1 位移阈值 | 1cm | DEV0 |
| undecidable 上限 | 20% | 测量质量门 |
| EEF 残差 | ≤1cm | DEV0 |
| cells/臂 | 24 起 | DEV 权力分析 |

## 6. 三段执行(纪律不变,逐字保留 + 扩充)

- **S1-DEV0(冒烟,单 episode 级,硬前置)**:①交接补丁断言
  (states.json 仅重放后 step 0,EEF/图像与仪器测量一致);②SAM3
  跟踪断链率与重关联正确率;③A/B 物理残差量化(EEF、位姿差带,
  定 §5 两阈值);④L1 仪器化预演(位移归因可判定率,校 20% 门)。
  任一不可修 → 按审计二 §三后备或 STOP。
- **DEV(定参,不产生判定)**:2 变体 × seed 若干 × 6 臂;用途 =
  §5 全部数值定稿 + 权力分析 + C0 资格预检(C0 明显不达即早停,
  修任务/指令后再入 TEST 流程)。**DEV 数据永不进判定**。
- **TEST(一次跑)**:独立 seed 批 + ≥2 套指令措辞变体(DEV 后
  冻结);预注册冻结版发布后一次性执行;判定只看 TEST(Stage G0.6
  heldout 先例)。
- infra 纪律:错误 ≤3 重试、rc=0 指纹按 C3 事故账;undecidable(b)
  桶同纪律。

## 7. 判定矩阵

| 结果 | 判定 |
|---|---|
| C0 不达(H0 FAIL) | 能力混入,任务族资格 FAIL → STOP(与历史必要性无关) |
| B0>50% 显著(H1 违 i) | 任务泄漏 → STOP(修任务不修结论) |
| B0 分集不对称(H1 违 ii) | 物理残差泄漏 → 后备;仍不过 STOP |
| C2a 显著 >B0(H4a 违) | 注入格式混杂 → 全部无效 STOP |
| H0∧H1 过 ∧ H2∧H3 过 | Memory 因果效应成立:SUPPORTED(表示层兑现) |
| H0∧H1 过 ∧ H2 过 ∧ H3 不过 | 历史必要但 typed 表示不足(表示瓶颈;报 C3−C4 差分解) |
| H0∧H1 过 ∧ H2 不过 | 历史不充分(跟踪/构造问题)→ 审计二 §三 STOP |
| H4b:C2b ≤ B0−δ | 内容利用成立(强化上述解释) |
| H4b:C2b ≈ B0 | 内容未利用,如实降级报告(不自动 STOP) |

## 8. 合法性与排除条款(冻结)

- 三禁令延续;所有历史输入冻结后不得回看 TEST 调整(Stage D 防火墙);
- 记忆臂输入 = 合法视觉历史导出,禁 sim 真值/BDDL 实例 ID/
  obj_of_interest/check_success(§2);
- S1 不重新解释、不修订 Stage R 六判定与 §36 Hard STOP;
  PERSISTENT_EVENTS_INDEX 五事件资产不动;
- 结论边界 = 本任务族(t9 家族孪生碗),不外推(S0 边界纪律)。

## 9. 资产与上下游

- 新增:DEV bddl(包内注册,先例 t3/t7+备份)、前缀动作流录制件、
  C2a/C2b 注入内容生成件、C3 留痕版人工核验记录、C4 typed sidecar
  (冻结)、S1 专用 runner(拼装现有模块函数,零库改动)。
- 不触碰:既有 10 任务 bddl/init、Memory 卡片、检索器、Stage R
  冻结资产与既往判定。
- 交付链:本 v2 批准 → DEV 校准 → 冻结版 prereg(数值定稿)→
  DEV0 → DEV → TEST → 终报。**每步启动均需用户单独批准。**

## 10. 版本与取代关系

- v1(0c171c4 `S1_PREREG_DRAFT.md`)被本文件取代,原文归档不改;
- v1→v2 差异 = 终审意见书六项(C0 臂/H4 拆分重定义/C3-C4 构造
  纪律/L1-L2-L3 指标/H1 判据细化/保留项确认)+ 两处更正记录
  (pi0_pick 语义、22/22→10/10 延续挂账);
- v2 仍为草案;冻结前任何修改记 deviation,冻结后不得改。
