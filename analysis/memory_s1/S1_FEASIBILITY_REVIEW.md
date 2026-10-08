# S1 任务可行性检查:历史反事实任务能否在当前 Harness 上合法构造

> 生成:2026-10-08 | 性质:**只读检查**(未改环境、未构造测试集、未跑
> rollout、未训练、未触碰 Stage R 结论与预注册)
> 输入:research-sync 最新状态(RPent HEAD=fa8bfd2,已推送,与远端一致)
> + `analysis/memory_s0/` 四份报告 + 本地源码核查(引用处标 file:line)
> 问题:S0 判定 NOT SUPPORTED(任务族无历史依赖决策点)后,若走选项 A
> (S1 任务资格门),当前 LIBERO + Pi0.5 + SAM3 Harness **能否支持合法的
> 历史反事实任务** —— 即 S0 必要性三条件的可构造版本:
> ① 当前可见观察相同;② 合法历史不同;③ 正确动作不同。

## 结论先行

**GO(有条件)** —— 五项检查四项无障碍、一项需操作性定义。
核心依据:① 全套件天然自带**外观完全相同的孪生物体**(libero_spatial
22/22 任务都是双 akita_black_bowl),当前靠位置区分 —— 把"位置区分"
换成"历史区分"即得反事实任务;② Stage R 已验证的 PREFIX 动作重放机制
恰好就是"合法历史注入器"(绕过一切 planner 可见通道);③ bddl 目标谓词
按**实例**判定(`On akita_black_bowl_1 plate_1`),环境能在 planner
看不见身份的地方给身份级判分。

## 检查一:反事实任务对能否构造 —— 能(孪生资产 + 两种设计)

### 1.1 孪生资产清单(源码证据)

| 资产 | 实例数 | 任务数 | 证据 |
|---|---|---|---|
| akita_black_bowl | 2 | libero_spatial 全 22 任务 | t9 bddl `:objects` 段:`akita_black_bowl_1 akita_black_bowl_2 - akita_black_bowl` |
| butter / moka_pot / plate / yellow_book | 2 | libero_10/90 共 18 任务 | 同法扫描 |

t9 现状:bowl_1 在木柜顶、bowl_2 在灶面,任务语言靠**位置**消歧
("the akita black bowl on the wooden cabinet")。目标谓词是实例级的:
`(On akita_black_bowl_1 plate_1)` —— 环境知道"哪只碗"是对的,而
两只碗在 planner 可见图像中**不可分**。

### 1.2 DEV-A 设计(首选):孪生交换(twin-swap)

- **历史注入**(scripted,非 planner):交换两只碗 —— pick 灶面碗 →
  place 柜顶,pick 柜顶碗 → place 灶面。
- **历史 A(交换)/ 历史 B(不交换)**:决策点当前可见观察同构
  (一只黑碗在柜顶、一只在灶面;差异仅为放置噪声,量级见检查一之 1.4)。
- **指令**(两条历史同文):"pick up the bowl that started on the
  wooden cabinet and place it on the plate"。
- **正确动作不同**:A → 夹灶面那只;B → 夹柜顶那只。
- **判分**:bddl 目标写实例(`On akita_black_bowl_1 plate_1`),
  check_success 自动判身份级对错 —— 抓错孪生体即 FAIL,无需人工评分。
- 对应 SimpleARM 的 **relation 类**状态("哪个物体经历过什么")。

### 1.3 DEV-B 设计(次选,降级理由见检查四):抽屉遮蔽

套件内存在抽屉任务(`..._in_the_top_drawer_of_the_wooden_cabinet_...bddl`),
可构造"放入抽屉→关闭→决策"的 reference 类遮蔽设计。但工具层无抽屉
原语且本 harness 从未跑过抽屉任务(实验只用 t3/t5/t9 开放台面),
动作能力未证明 —— **列为次选,S1 DEV 先不做**。

### 1.4 "当前可见观察相同"的物理边界(必须操作化的条件)

真实物理下像素级相同不可能(pick-place 往返有 settle 噪声;basket 卡片
描述过 retreat-settle 现象;Stage P 量过 restore 重执行漂移 ≤7.8e-4m
同向单调)。**操作性定义建议**(留给 S1 预注册,本检查不冻结):
决策点两条历史的 planner 可见通道(图像 + world_map)差异 ≤ 噪声带,
且 **B0(无历史)在决策点正确率不高于机会水平(2 选 1 = 50%)** ——
用行为定义观察等价,比像素定义更贴研究问题。

## 检查二:历史事实能否从 Planner 可见通道获得 —— 能

- 交换过程本身在 planner 可见传感器覆盖内:柜顶/灶面/台面均在
  agentview 视野(`robots/libero/tools.py:1195-1197` 工具描述:agentview
  用于全局桌面布局与物体位置;wrist 用于近距离细节),碗被夹起移动的
  全程可被相机看见。
- **oracle 历史的合法来源** = prefix 回放时录下的帧流(agentview/wrist)
  离线导出(如 SAM3 跟踪两只碗的轨迹),**不是 sim 真值** —— 与
  sim_measurement 防火墙(`robots/libero/env_server.py:282-301`)一致:
  记忆侧信息只能来自 planner 本可看见的东西。scripted prefix 的**编排**
  允许用 sim 位置(那是任务构造,不是 agent 观测),但喂给记忆臂的
  内容必须观测导出 —— 两者分开记录。
- 结论:历史事实"曾经可见、现在不可见",恰是 S0 三条件的教科书形态。

## 检查三:无历史基线的泄漏通道 —— 四条逐一裁决,全堵

| 通道 | 风险 | 裁决 | 证据 |
|---|---|---|---|
| ① planner message_history | episode 内 LLM 对话保留全部既往轮(`api_loop.py:1233` `message_history=list(self._history)`),若 prefix 由 planner 执行,B0 靠上下文就能解题 | **不泄漏(prefix 绕过 planner)**:DEV 流程 = 裸起 env(`scripts/stageR_rt.py:109` bare boot)→ PREFIX 重放 → **重放后才启动 planner**(fresh,历史为空)。planner 从未"经历"prefix,其 in-context 历史干净 | stageR_rt.py:162-186(重放期间零模型调用)+ Stage O 先例(失败后从中间状态发 recovery command 的 planner-at-mid-episode 机制已存在) |
| ② view_driver_state(step) 主动查历史 | 工具描述明示可读任意过去 step 的状态+图像(`tools.py:1182-1196`) | **不泄漏(prefix 不入 states.json)**:toolkit._step 才写 states.json(`robots/libero/toolkit.py:60-113`),PREFIX 重放走 `env.step`/`env.chunk_step` 直连(`stageR_rt.py:169-177`),states.json 从决策点才开始记 → B0 查不到 prefix | toolkit.py dump 链 vs stageR_rt 重放链,互不相交 |
| ③ PhaseTracker / DecisionMemory | episode 内历史字段(last_pick_success/moves_since_pick,`structured.py:120-127`)与卡片注入可能携带线索 | **不泄漏**:PhaseTracker 挂在 planner 工具流上,fresh planner 从零开始;prefix 不经 planner;卡片注入由 `RPENT_MEMORY_TRIGGER` env 门控(`api_loop.py:342-344`),B0 臂关掉即可(现成机制) | structured.py:145(on_tool_call 只接 planner 流)|
| ④ obj_of_interest / sim 真值 | 环境知道目标实例身份,若泄给 planner 则反事实失效 | **不泄漏**:obj_of_interest 仅存在于 sim_measurement(`env_server.py:299`),全仓 grep 仅 rtrace(离线仪器)与 env_server 两处;planner 可见通道(view_driver_state/工具结果)不含 | 全仓 grep 证据(本次检查) |

附带红利:PREFIX 重放还有 (task,seed) reset 确定性 + R0 32/32 逐位一致
的背书(`analysis/stageR_reconstruction_decision.md`)—— 两条历史可
逐位复现,实验重复性有仪器级保障。

## 检查四:Pi0.5 与工具层能否执行两种正确动作 —— 能(且与 Pi0.5 无关)

- 夹哪只碗的**选择**发生在 planner 层(选像素/选目标),Pi0.5 只按
  参数执行 —— t9 基础任务本身就是"孪生中按指令夹指定只"的日常
  (22 个 spatial 任务天天在跑),动作层对两种正确动作零新增要求。
- pick 为像素参数化原语(tools.py 工具族:segment → back_project →
  pick 链路),对任意一只孪生碗同等可用;place 到 plate 同 t9 原目标。
- Pi0.5 推断非确定性(Stage J:同 obs 动作差 0.23)不影响**能力**,
  只影响测量噪声 —— DEV 阶段用多种子(先例:t3/t5/t9 × s1-10)。
- 唯一动作层保留:DEV-B 抽屉(无原语、零先例)→ 降级次选(1.3)。

## 检查五:DEV/TEST 隔离 —— 能

- 新任务 = 新 bddl + 新 init states,**不动** t3/t5/t9 现有 TEST 与
  Stage R 冻结资产(PERSISTENT_EVENTS_INDEX 五事件全在原任务目录)。
- 先例:t3/t7 bddl 修复 + 50 states 重建,备份在
  `/workspace/yjx/rpent_data/init_state_backups`(已验证的存在)。
- 约束(如实记录):任务注册发生在 **LIBERO 包缓存目录**(suite 按
  task_id 枚举,`env_server.py:96-97` `suite.get_task_init_states`),
  t3/t7 先例同路径 —— 属一次性环境变更,S1 获批后才做,本检查未动。
- 预注册、Stage R 结论、Memory 卡片、检索器:全部不在本检查触碰范围。

## 无法满足 / 有条件的项(如实清单)

1. **像素级观察相同**:物理不可能(1.4)→ 以"B0 不高于机会水平 +
   噪声带上限"的行为学定义替代,门槛值留给 S1 预注册。
2. **任务注册动 LIBERO 包缓存**:有 t3/t7 先例与备份纪律,但属于环境
   变更,需获批后执行;若坚持零包改动,备选 = 只用现有 22 个 spatial
   任务的 bddl 做**指令改写**(不动 bddl 只改语言指令与判分口径)——
   但实例级判分仍需 bddl 目标谓词,故包内新增任务仍是主路径。
3. **抽屉遮蔽设计**:动作能力未证明(检查四),S1 DEV 首期不做。
4. **scripted prefix 的录制**:交换动作需先成功执行一次以录制动作流
   (工具链成熟;t9 每天在跑),录制失败率未知 —— DEV 阶段第一批
   工作就是它,属正常工程风险非阻塞。
5. **oracle 历史导出**:需从回放帧做 SAM3 跟踪离线导出 —— 工具存在
   (SAM3 服务器现成),导出精度是 DEV 验证项。

## GO / NO-GO

**GO(有条件)** —— DEV-A(孪生交换)设计满足 S0 三条件的可构造版本,
泄漏通道全堵,动作能力零新增,DEV/TEST 可隔离。建议 S1 预注册(若用户
选 A)采用 S0_RESEARCH_DECISION §四的对照集:B0(无记忆,fresh planner)
vs B0+oracle 历史(回放帧导出,上界)vs B0+typed state(可实观位),
外加 sham 记忆对照与 B0≤chance 资格门。五个条件项如上,逐条进预注册
的 gate 而非自由参数。

## 附:本检查的证据文件清单(全部只读)

- bddl:`.cache/.../libero_spatial/pick_up_the_black_bowl_on_the_wooden_cabinet_*.bddl`(孪生/实例级目标/位置消歧)+ 全套件孪生扫描
- `scripts/stageR_rt.py:109-219`(bare boot / PREFIX 重放 / exec)
- `robots/libero/toolkit.py:60-113`(_step 与 states.json 写入链)
- `robots/libero/tools.py:1182-1196`(view_driver_state 语义)、`:1604`(实现)
- `robots/libero/env_server.py:96-97,282-301,299`(任务枚举/防火墙/obj_of_interest)
- `rpent/planner/api_loop.py:342-344,1233`(注入门控/会话历史)
- `rpent/memory/structured.py:97-190`(PhaseTracker 挂接点)
- Stage R/O/P 既往结论(reconstruction_decision / 终报 / init_state_backups)
