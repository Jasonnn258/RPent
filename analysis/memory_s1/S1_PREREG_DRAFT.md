# S1 预注册草案:Historical Memory on Twin-Swap Tasks

> 生成:2026-10-08 | 状态:**草案,待用户/网页端审批后才可冻结与执行**
> 上游:MEMORY_NECESSITY_AUDIT(NOT SUPPORTED,任务族属性)→
> S1_FEASIBILITY_REVIEW(GO 有条件)→ 本草案。
> 本轮只读审计与草案撰写:未改源码/环境,未跑 rollout,未触碰
> Stage R 冻结资产与既往判定。

## 0. 研究问题(最小化)

**RQ**:在当前观测不含解、合法历史含解的反事实任务上,历史信息
(memory)对决策与终局的因果效应多大,紧凑 typed-state 表示能兑现
其中多少?

- 主判定 **H1(任务资格)**:Current-only(B0)在双碗决策上不高于
  机会水平(2 选 1 = 50%)。B0 显著 >50% ⇒ 任务泄漏,一切失效,STOP。
- **H2(历史充分性)**:Oracle 历史(C3)显著高于 B0(建议门 ≥30pp,
  绝对值 ≥85%——2 选 1 且 oracle 信息完备时应接近全对)。
- **H3(表示可兑现性)**:typed-state(C4)−B0 ≥15pp(S0 §四传统)。
- 探索性:H4 sham(C2)≈B0(排除"注入文本安慰剂");H5 B0 内部
  策略分析(是否用 EEF 残差等物理线索投机)。

## 1. 任务与历史构造(冻结要素)

- 基任务:libero_spatial t9 家族变体(新增 DEV bddl,注册走 t3/t7
  先例;**不改动现有 10 任务与 init states**;TEST 用独立变体)。
- 语言(两臂同文):"Pick up the bowl that started on the wooden
  cabinet and place it on the plate."
- 历史对(A/B):同 task、同 seed、同语言;A 前缀=交换双碗动作流,
  B 前缀=等长中立动作流(不碰碗);两前缀末尾统一 homing 至同目标。
  前缀=录一次→PREFIX 逐位重放(Stage R 机制,R0 已证 32/32 逐位一致)。
- 正确动作:A=夹灶面碗,B=夹柜顶碗;判分=实例级 bddl 目标
  (`On akita_black_bowl_1 plate_1`),check_success 自动判。

## 2. 对照集(最小四臂)

| 臂 | 注入内容 | 来源合法性 |
|---|---|---|
| C1 B0 Current-only | 无(fresh planner;RPENT_MEMORY_TRIGGER=off) | — |
| C2 Sham | 置换历史卡(A↔B 交换的假关系,格式同 C4) | 安慰剂对照,Stage D D_SHAM 先例 |
| C3 Oracle-history | 首帧锚+全程轨迹文本(上界) | 仅重放帧 SAM3 导出(审计二 §2.3 排除条款) |
| C4 Typed-state | 紧凑 relation 状态(如 moved(bowl_cabinet→stove)) | 同上,离线一次生成冻结 |

所有臂:api planner(排除文件后端 extra_dirs 通道)、同 prompt、
同 turn 预算、同温度;观测交接按审计一 §四清单(擦工件+重放后
step 0 重 dump)。

## 3. 指标(两级)

- **L1 Decision Accuracy(决策级,主指标)**:首次 pick 的双碗选择
  对错。仪器侧判定:pick 后 sim_measurement 物体位姿变化归属到
  实例(离线,planner 不可见)。不依赖任务完成,隔离执行噪声。
- **L2 Stable Success(终局级)**:Stage Q 冻结双契约(首中后全测量
  点保持 ∧ (任一点 check_success ∨ 保持点数 ≥4))。直接复用,
  不重新定义。
- 过程指标:EEF 残差(A/B 决策点)、物体位姿差带、注入次数/token、
  turns、infra 错误分类(C3 事故账纪律)。

## 4. DEV/TEST 划分

- **S1-DEV0(冒烟,资格仪器化,单 episode 级)**:审计一/二列出的
  前置项 —— ①交接补丁断言(states.json 仅重放后 step 0,EEF/图像
  与仪器测量一致);②SAM3 跟踪断链率;③A/B 物理残差量化
  (EEF ≤ 阈值起点 1cm、位姿差带)。任一不过:修前置(不改判定)
  或按审计二 §三后备/STOP。
- **DEV(调参/权力分析)**:2 任务变体 × seed 若干(建议 4)× 4 臂;
  只用于样本量估计与阈值定稿,**不产生判定**。
- **TEST(一次跑)**:独立 seed 批 + 独立指令措辞变体,预注册冻结后
  一次性执行(Stage G0.6 heldout 先例);判定只看 TEST。

## 5. 判定矩阵

| 结果 | 判定 |
|---|---|
| B0>50% 显著 | 任务泄漏 → STOP(修任务,不修结论) |
| H1∧H2∧H3 全过 | Memory 因果效应成立:MEMORY NECESSITY 在新任务族 **SUPPORTED(表示层兑现)** |
| H1∧H2 过、H3 不过 | 历史必要但 typed-state 表示不足(表示瓶颈,报 SimpleARM 四类状态对照) |
| H1 过、H2 不过 | 历史不充分(跟踪/构造问题)→ 按审计二 §三 STOP |
| H4 失败(sham 也涨) | 注入效应混杂,全部无效 → STOP |

## 6. 边界与纪律(延续既有约束)

- 禁令三延续:不得以"任务长/失败/记忆被读取"论证必要性;
- 所有历史输入冻结后不得回看 TEST 调整(Stage D 防火墙纪律);
- infra 错误 ≤3 重试、rc=0 指纹按 C3 事故账处理;
- 本草案数值门(30pp/15pp/1cm/85%)为**建议起点**,DEV 后定稿,
  定稿进冻结版预注册;TEST 不得再动。
- 运行环境:开发机单 episode 冒烟 + DEV;若 DEV/TEST 总量超
  ~1h 高负载,按铁律转 Training Task(与用户确认)。

## 7. 上下游与资产

- 不触碰:Stage R 冻结资产(PERSISTENT_EVENTS_INDEX 五事件)、
  既有 10 任务 bddl/init、Memory 卡片、检索器、Stage R 结论。
- 新增资产:DEV bddl(包内注册,先例 t3/t7+备份)、前缀动作流
  录制件、typed-state sidecar(冻结)、S1 专用 runner(拼装现有
  模块函数,不改库)。
- 交付链:本草案批准 → 冻结版 prereg(数值定稿)→ DEV0 → DEV →
  TEST → 终报。

## 8. 审计三份文件的状态标注汇总

| 审计项 | 状态 |
|---|---|
| 观测交接机制(view_driver_state=dump 链) | [S] 可行 |
| step 0 污染 | [S] 已定位+不改库修法;[R] DEV0 断言 |
| env 渲染缓存/录像/注入门控/文件后端排除 | [S] 无泄漏/可排除 |
| A/B 语言/名字/步数/真值/会话通道 | [S] 无差异 |
| EEF 残差与 settle 噪声 | [R] 对称化设计+阈值门(DEV0 量化) |
| SAM3 身份连续性跟踪 | [R] DEV0 断链率;后备+两点式 |
| 记忆输入合法性框架(锚点/排除条款) | [S] |

**总建议:GO(有条件)**——预注册可进入审批;启动执行前的硬前置
= S1-DEV0 三项冒烟全过(交接断言/跟踪/物理残差),任何一项不可修
复才降级 HOLD/STOP。无 [X] 项。
