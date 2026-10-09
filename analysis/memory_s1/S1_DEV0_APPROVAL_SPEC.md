# S1-DEV0 执行协议与审批规格(APPROVAL SPEC)

> 生成:2026-10-09 | 状态:**等待用户批准后才可执行**
> 上游:`S1_PREREG_FINAL_DRAFT.md`(v2)→ `S1_PROTOCOL_CORRECTIONS.md`
> (v2.1,本协议遵循其 §一.5 次序与全部修订条款)
> 性质:单 episode 级**仪器资格冒烟**——只产阈值建议与通过/停止
> 结论,**不产任何研究判定**(H0-H4 全部留待 TEST)。
> 运行纪律:开发机只做本冒烟(单 episode 级,符合铁律);
  `dev_preflight` + `.runlocks/s1_dev0.lock` + 并发 ≤8;
  `MUJOCO_GL=osmesa`;日志写 `/workspace/yjx/tmp/s1_dev0*.log`。

## 一、前置条件(本批准覆盖的一次性准备,未批不动)

| # | 事项 | 性质 | 先例/依据 |
|---|---|---|---|
| P-1 | 新建 2 个 DEV bddl 变体(S1_DEV_A1/A2,语言=历史指称,目标谓词=实例级 `On akita_black_bowl_1 plate_1`)+ LIBERO 包缓存内注册 | 一次性环境变更(备份先行) | t3/t7 修复先例,备份 `/workspace/yjx/rpent_data/init_state_backups`;**不动现有 10 任务** |
| P-2 | 每 (variant, arm) 录制前缀动作流:scripted 伺服(move_to/set_gripper/release,编排可用 sim 位置=任务构造,非 agent 观测) | 录制(录一次→PREFIX 逐位重放) | 可行性报告条件项 4;A=交换双碗、B=等长中立+统一 homing |
| P-3 | DEV0 专用 runner:拼装现成模块函数(bare boot → PREFIX 重放 → **擦工件+重 dump step 0(P1 修法)** → 冷启动 api planner),零库改动 | 代码拼装,不改库 | 审计一 §三交接清单 |

**显式不触碰**:现有 10 任务 bddl/init、Memory 卡片、检索器、
Stage R 冻结资产(PERSISTENT_EVENTS_INDEX 五事件)、Stage R 结论。

## 二、四项冒烟(最小运行次数已锁)

### 项 1:观测交接断言(P1 修法验收)

- **运行**:2 variants × 2 arms × 2 次重放 = **8 次重放 boot**
  (planner 不启动;PREFIX 重放 + 擦工件 + 重 dump)。
- **断言(全部必须过)**:
  a. 重放后 states.json **恰 1 条** step 0;EEF/夹爪/object_names
    与仪器侧 sim_measurement 同时刻读数一致(数值容差 = 浮点序列化
    精度);图像文件存在且非空;
  b. **重放确定性**:同 (variant, arm, seed) 两次重放的 env state
    sha16 相等(R0 32/32 先例在新 bddl/新前缀下复验);
  c. episode.mp4 不含 prefix 帧;planner 可读工件目录无历史残留
    (init_primitives_clean 清理段对照)。
- **通过条件**:8/8 断言全过。
- **失败处置**:断言失败 → 修 runner 拼装(不改库)重跑本项,
  **3 轮修不好 = 仪器 STOP**(基础设施缺陷,不涉任务判定)。

### 项 2:SAM3 跟踪断链率(离线)

- **运行**:对项 1 已录的 2 条 A 前缀帧流离线跑 SAM3 逐帧分割+
  IoU/最近邻关联(**零新增 env boot**;离线算力并入成本上限)。
- **度量**:断链率(需要重关联的帧占比)、重关联正确率(vs 编排
  真值——交换编排由构造已知,离线评估用合法)、遮挡段(pick 在爪
  中)的先验重关联成功率。
- **通过条件(建议起点,产阈值建议不产判定)**:断链率 ≤10% 且
  重关联正确率 ≥90%;两点式后备(首锚+末段锚)同步量化备案。
- **失败处置**:>30% 或两点式也不稳 → **C3 上界不可信 → 任务资格
  STOP 报告**(审计二 §三原文路径);10-30% → 降级两点式进 DEV,
  记 deviation。

### 项 3:A/B 物理残差量化

- **运行**:2 variants × 2 seeds × 2 arms = **8 个重放终点测量**
  (决策点 = homing 收敛后;不启动 planner;boot 数与项 1 复用
  4 个,新增 4 个)。
- **度量**:A/B 同 (variant, seed) 配对的 EEF 距离、双碗位姿差带
  (sim_measurement 离线)、settle 稳定性(homing 后静置 N 步内漂移)。
- **通过条件(建议起点)**:EEF 残差 ≤1cm;碗位姿差带记录为
  L1 位移阈值的噪声底输入(阈值 = max(1cm, 3×噪声底) 建议)。
- **失败处置**:超 1cm → 审计二 §三后备(对称化加强:两次对称
  move_to 往返 / 静置段);后备后仍超 → **物理残差 STOP 报告**。

### 项 4:L1 仪器化预演(planner 上线,唯一用 LLM 的项)

- **运行**:2 variants × 1 seed × 2 arms × C1(B0)配置 = **4 个
  完整 episodes**(fresh api planner,RPENT_MEMORY_TRIGGER=off,
  turn 预算与 v2 同)。
- **度量**:位移归因成功率(UNATTRIBUTABLE 占比)、NO_EFFECTIVE_
  PICK 占比、L1 判定时机可行性(首次达阈值位移可否程序化定位)、
  位移阈值建议值(结合项 3 噪声底)。
- **通过条件(建议起点)**:UNATTRIBUTABLE ≤20%(v2.1 §一.1 的
  质量门同款);归因脚本与 sim_measurement 工件齐备可复核。
- **失败处置**:归因逻辑可修则修(3 轮上限);属物理不可分(两碗
  同动高发)→ 记录并在 DEV 提案中预登记 L1b 的解释边界(不修门)。

## 三、成本上限(总账,超限即停报)

| 维度 | 上限 | 说明 |
|---|---|---|
| env boot 总数 | **≤24**(项 1 复用 8 + 项 3 新增 4 + 项 4 的 4 + 前缀录制/补试 ≤8) | 含录制尝试;重放 boot 秒级 |
| planner episodes | **≤4**(仅项 4) | 唯一 LLM 调用源;40 turns/ep 预算 |
| 墙钟 | **≤4 小时**(含离线 SAM3) | 超限 → 停,报告剩余项,等指示 |
| 并发 | ≤8(实际串行为主) | 铁律 |
| 写盘 | 全部工件进 repo `analysis/memory_s1/dev0/` + 日志 `/workspace/yjx/tmp/` | 不碰 /tmp 系统段 |

预计实际:~1-2 小时墙钟(重放为主,4 个 planner episodes 各约
10-20 分钟)——开发机单 episode 冒烟属允许用途;若实测节奏预示
超限,立即停(不硬跑)。

## 四、通过/停止总表

| 项 | 通过 | 边界(进 DEV 前须裁决) | 停止 |
|---|---|---|---|
| 1 交接断言 | 8/8 全过 | — | 3 轮修复不过 → **仪器 STOP** |
| 2 SAM3 | 断链≤10% ∧ 重关联≥90% | 10-30% 或需两点式 → DEV 降级+deviation | >30% 且两点式不稳 → **C3 上界 STOP** |
| 3 物理残差 | EEF≤1cm | 1-2cm → 后备重测一次 | 后备仍 >1cm → **残差 STOP** |
| 4 L1 仪器化 | UNATTRIBUTABLE≤20% | 20-35% → DEV 预登记解释边界 | 归因不可程序化 → **测量 STOP** |

**DEV0 全过 → 产出 DEV 提案(SD_d 估计计划 + v2.1 ★项定稿清单)
交用户;任一 STOP → 终止并出 DEV0_REPORT(如实,不硬凑)。**

## 五、证据记录方式(可审计)

- 逐项工件:`analysis/memory_s1/dev0/item{1..4}/`(JSON 断言结果、
  state sha16、SAM3 逐帧表、残差测量 CSV、4 episodes 的归因明细),
  每文件带生成时间与输入哈希;
- 汇总:`analysis/memory_s1/dev0/DEV0_REPORT.md`——四项结果 vs
  本规格门、deviation 清单、infra 账(指纹/重试/补采)、DEV 提案
  草案或 STOP 报告;
- 运行侧:nohup 日志 `/workspace/yjx/tmp/s1_dev0.log`(持久卷);
  锁 `.runlocks/s1_dev0.lock`;preflight 输出贴进报告头;
- 提交纪律:工件+报告一次 commit(RPent,分支同);**不 push 除非
  用户要求**;research-sync 记录状态。

## 六、等待审批事项(全清单,批后即执行)

1. **本 DEV0 执行批准**(含 §一 前置 P-1 包缓存注册/P-2 前缀录制/
   P-3 runner 拼装——同一批准覆盖);
2. (DEV0 过后)DEV 校准执行批准 + v2.1 ★数值定稿(含 §一.2 的
   n 决策:SD_d>0.30 时提 cells 至 34-44 或复议 H3 门);
3. (DEV 过后)冻结版 TEST 预注册批准(数值+分析脚本哈希冻结);
4. (冻结后)TEST 一次跑批准。
