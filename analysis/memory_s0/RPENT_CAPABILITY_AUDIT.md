# S0 任务二:RPent 当前 Memory / 决策 / 观测能力审计

> 生成:2026-10-08 | 性质:只读审计(未改任何源码)
> 范围:rpent/memory/*、rpent/planner/*、rpent/tools/*、robots/libero/*
> 核心问题:①已实现/部分/缺失的能力清单;②现有结构化状态能否记录
> **对象身份、历史位置、状态变化、任务进度**四类信息。

## 一、总体架构(决策环与信息流)

```
Planner(LLM, rpent/planner/api_loop.py)
  ├─ 可见观测:当前图像(256/1024 agentview + wrist)
  │            + view_driver_state(robots/libero/tools.py:1604)
  │              〔机器人状态 / libero_terminated / command log / result〕
  ├─ 感知工具:SAM3 segment / back_project(像素→世界坐标)
  ├─ 动作原语:pick / place / move_to / finish 等(robots/libero/toolkit.py:60 _step)
  ├─ Memory 注入:api_loop.py:342-344,568-578 turn_boundary 节流软注入
  │              (RPENT_MEMORY_TRIGGER 门控;DecisionMemory)
  └─ [防火墙] sim_measurement(env_server.py:282-301)── 绝不进入
              planner/router 可见文本(注释原文),只作离线科学仪器
```

关键结构性事实:**planner 的世界知识 = 图像 + 工具结果 + 注入的记忆**。
object-state 物体位姿真值、obj_of_interest、check_success 都在防火墙外
(离线分类/仪器专用)。这既是历史污染防护,也意味着 planner 侧任何
"记忆"都无法与真值对账 —— 记忆的写入源头只能是 planner 可见的工具流。

## 二、能力清单(已实现 / 部分 / 缺失)

| # | 能力 | 状态 | 证据位置 | 说明 |
|---|---|---|---|---|
| 1 | 持久记忆内容(卡片) | **已实现** | `resources/libero/global/*.md`(61 张:strategy 43 / perception 13 / primitive 4 / failure 1) | 人工/离线蒸馏生成,带 evidence.cells 溯源 |
| 2 | 记忆检索(词面) | **已实现** | `rpent/memory/retrieval.py:141-184`(toks/load_cards/load_index) | Q0 lexical:token = MEMORY.md 行 ∪ 文件名拆词;symptom/how_to/falsify 不在索引 |
| 3 | 记忆检索(语义) | **已实现(可选)** | `retrieval.py:192-234` _Embedder | 默认关,主线实验用词面 |
| 4 | 决策点触发注入 | **已实现** | `retrieval.py:519-676`(_trigger_reason/turn_boundary);`api_loop.py:568-578` | R1-R5 进度信号驱动 + thresholds + cooldown;软注入,Planner 可忽略 |
| 5 | episode 内结构化状态 | **已实现** | `rpent/memory/structured.py:97-140`(PhaseTracker) | phase P_init..P_verify、last_pick_success、moves_since_pick、consecutive_perception、turns_used |
| 6 | episode 内规则引擎 | **已实现** | `rpent/memory/schema.py:67-93`(Rule:trigger/precondition/success_check/recovery/next_phase) | GLOBAL/task<N> 作用域;PhaseTracker 驱动 |
| 7 | 物理验证(终局) | **已实现** | `env_server.py:280-281` check_success;Stage Q STABLE_RECOVERY 冻结契约 | 仪器层,不进 planner |
| 8 | B2 verifier(过程裁决) | **已实现** | `rpent/memory/stv.py`(1374 行) | B2 结论:裁决不驱动行为(无动作级杠杆) |
| 9 | 快慢路由 | **已实现** | `rpent/memory/dual_route.py`;`api_loop.py:385-401` | DualRouter 叠加在结构化记忆上 |
| 10 | Outcome validation | **已实现** | `rpent/memory/av.py`(458 行) | turn_boundary_hint 注入路径 |
| 11 | 仪器级状态测量 | **已实现** | `env_server.py:282-301` sim_measurement;`rpent/utils/rtrace.py:76-91` | obs 低维向量(EEF/夹爪/object-state)+ obj_of_interest + check_success;Stage R 快照/trace 同族 |
| 12 | 离线丰富记录 | **已实现** | `resources/libero/task_only/{cell}.json` + `{cell}_recipe.jsonl` | strategy_notes / pick_result / localization* / failure_history / final_state.note / contact_result / perception* |
| 13 | **记忆写入环(集后自动更新)** | **缺失** | 无对应模块 | 卡片是人工/离线蒸馏;无 Zetta orchestrator / SkillOpt Evaluate gate 型自动环;无版本化哈希链 |
| 14 | **对象中心跨时程账本** | **缺失** | 无对应模块 | 无 Ledger 型"对象 X 现在在哪/经历过什么"的在线可查询结构 |
| 15 | **按历史依赖性定义的触发** | **缺失** | `retrieval.py:519-524` | 触发=进度信号阈值,不是"该决策需要历史"的语义判断(SimpleARM 型) |
| 16 | 记忆内容与真值对账 | **结构性不可能** | 防火墙注释 | planner 侧写入源只见工具流;sim 真值只在离线 |

## 三、四类信息记录能力逐项回答(任务二核心问题)

### 3.1 对象身份(object identity)—— **部分**

- **有**:obj_of_interest(仪器层,当前任务关注对象名列表,
  `env_server.py:299`);planner 层靠 prompt 语言指涉 + SAM3 mask
  ID(`tools.py` segment/back_project 工具族);task_only JSON 离线
  记录了 pick/segment 的对象级结果。
- **无**:跨 episode 的稳定对象身份账本(对象 ↔ 历史交互的映射)。
  SAM3 mask 是 episode 内瞬态的;卡片里的对象指涉是文字,无结构化键。
- 结论:**能感知当前对象,不能积累对象历史**。

### 3.2 历史位置(object position history)—— **部分(离线)/ 缺失(在线)**

- **有(离线)**:object-state 位姿向量全量进了 rtrace/task_only
  (localization* 字段);Stage R 的 pre/post 快照是位姿级状态哈希源。
- **无(在线)**:planner 每轮只见当前帧;无"对象 X 上一时刻在哪/
  被谁移动过"的查询接口。PhaseTracker 只跟踪机器人侧进度,不跟踪对象。
- 结论:**历史位置被仪器记录了,但没有任何决策点能消费它**(且按
  防火墙设计,sim 级位置本就不许进 planner;planner 侧可用的是
  back_project 得到的世界坐标,亦无历史化结构)。

### 3.3 状态变化(state changes)—— **部分(episode 内)**

- **有**:PhaseTracker 的 episode 内事件序(last_pick_success、
  moves_since_pick、consecutive_perception、错误计数);
  规则引擎可对 precondition→expected_result 的状态转移做检查。
- **无**:跨 episode 的状态变化流(对象状态机、环境变化日志)。
- 结论:episode 内状态变化**已实现且可用**;跨时程状态变化缺失。

### 3.4 任务进度(task progress)—— **已实现(episode 内)**

- PhaseTracker phase 机(P_init..P_verify)+ R1-R5 进度触发器
  (retrieval.py:442-498 _progress_observe)+ turns_used 预算。
- Stage C 实证:PROGRESS 触发是 Memory 线唯一拿到正收益的杠杆
  (SR .733→.852),且该收益的机制归因是**触发时机**(episode 内
  进度信号),不是记忆内容本身。
- 结论:episode 内任务进度是**当前系统最成熟的结构化状态**。

## 四、能力审计结论

1. RPent 是一个 **episode 内状态强、跨时程记忆弱** 的系统:
   - episode 内:进度/相位/近因事件/规则引擎全部就位(能力 #4-#6);
   - 跨时程:有内容(61 卡)有检索(词面/语义),但**无写入环、
     无对象账本、无历史依赖触发**(缺失 #13-#15)。
2. 四类信息中,任务进度(episode 内)已实现;对象身份/历史位置/
   跨时程状态变化均为"离线记录了、在线无消费者"或干脆缺失。
3. 防火墙(sim_measurement 不进 planner)决定了:任何未来记忆系统
   的写入源只能是 planner 可见的图像+工具流 —— 这与六参考系统
   (任务一)的"从交互历史导出记忆"约束一致,不是缺陷,是正确设计。
4. 因此,**能力缺口是否是瓶颈,取决于任务族是否存在历史依赖决策点**
   —— 这正是任务三要回答的问题。
