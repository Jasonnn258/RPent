# Stage B1 结果:decision-point memory 在线四臂实验(2026-09-17/18)

100 集(glm-5.3-flash,t3/t5/t9 × s1-10):memB1/B2/B3 各 30 新集 + B0
(t3/t5 复用 09-15/16 armA 严格可比批 + t9 补跑 10 集)。设计与 B0 审计见
`memory_stageB_design.md`;机器可读全量 `memory_stageB_results.json`。

## 一句话结论

**NEITHER SUPPORTED;EXECUTABLE MEMORY NEXT: NO。** 修 access 有真实在线收益
(t9 5/10→9/10),但 decision-time trigger 净伤害(precision 27%),Q3 结构化排序
相对词面零增益(SR 还更低、每次检索 +7.6s)。当前形态的长期 memory,开局浏览
(browse-once)优于关键时刻重检索。

## Task 层(配对,n=30/对)

| 臂 | SR | 均时 s | 配对 | W/L | 读法 |
|---|---|---|---|---|---|
| B0 历史行为 | .733 | 2570 | — | — | t9 仅 5/10 |
| B1 +access fix | .833 | 2489 | B0→B1 | **5W/2L** | 收益全在 t9(4W/0L);t3/t5 持平 |
| B2 +trigger+lexical | .733 | 2465 | B1→B2 | **2W/5L** | t9 0W/3L;t3/t5 持平 |
| B3 +trigger+Q3 | .633 | 2368 | B2→B3 | **4W/7L** | t3 1W/4L;t9 3W/3L |

t5 全臂 10/10(天花板,无分辨力);信号集中在 t3/t9。单格 n=10,方向性证据,
不单独声明显著。

## Trigger 层(45 个 SHOULD 时刻 vs 94 次火)

- 覆盖率 0.533(24/45 时刻在 0-3 turn 窗口内被同族火覆盖)
- **precision 0.266**:94 火中 69 次无对齐信号(unnecessary)
- 火源分布:T4 repeated_no_progress 73/94(waypoint 式连续 move_to/move_pose
  是正常运输行为,正是设计文档预记的 over-fire 对象)、T3 predicate_stalled 19、
  T7 phase_stalled 2
- 每集触发 2.0-2.1 次(cap 6 / cooldown 2 从未打满——火自己就稀疏)

## Ranking 层(仅对齐火,gold=Stage A class→cards 冻结映射)

- gold 事件 14:relevant@1 = relevant@3 = **0.571**(命中时正确卡必在 Top-1)
- **B2 = B3 = 4/7**:结构化排序在合法决策时刻没有任何在线排序优势
- 11 个对齐到 hard-negative 时刻(集失败 → retreat 卡族按 Stage A 规则被证伪,
  正确行为是不取卡)
- 词面 1ms vs Q3 **7578ms/次**(冷启与暖态同价——CPU bge query embedding;
  每集 ~2 次 → ~15s 开销);注入块 ~350 tokens/次,两臂相当

## Adoption 层(keyword proxy,偏高估,只作上界)

followed_top1 58/94、any_top3 76/94、ignored 18。RETREAT/OBSERVE 动词与常规
move/observe 行为重叠 → 真实 adoption 无法用此代理断言;集级分解中 **0 集**
RETRIEVED_BUT_IGNORED(凡 gold 命中的失败集,proxy 都判"已跟随")。
"正确卡进 Top-3 但 Planner 不用"在本轮**不成立为主要瓶颈**。

## Outcome 代理(半自动,候选计数)

helped_c 8 / harmful_c 20(=跟随后 3 turn 内同类再火)/ neutral 66 / refire 20。
仅方向参考。

## Failure decomposition(60 集,B2+B3)

| 类 | 集数 | 说明 |
|---|---|---|
| SUCCESS | 41 | — |
| NO_RELEVANT_MEMORY | 9 | 火对了时刻,但该时刻按结局无适用卡(hard-negative 族) |
| EXECUTION_FAIL | 5 | states.json 全程无失败信号却失败(打满 turn/主动放弃) |
| RETRIEVAL_WRONG | 4 | 时刻对、卡全错:两排序器同样收敛到 pick 准备卡 |
| TRIGGER_MISS | 1 | 时刻存在,火全未对齐 |
| ACCESS_FAIL / RETRIEVED_BUT_IGNORED / MEMORY_WRONG | 0 | — |

RETRIEVAL_WRONG 的机制与 Stage A 结论一致:真 near-miss 恢复时刻
(gold=corrective-pick/settle-regrasp),query 只有"repeated move_to x3"这类
症状文本,无法表达"物体差几厘米没进"的物理状态 → 症状文本检索结构性不可分。

## 8 个必答问题

1. **修 access 有在线影响吗?** 有,且只在 t9:5/10→9/10(配对 4W/0L)。t3/t5
   planner 开局自己浏览已够(或在天花板)。
2. **decision-time trigger 比开局浏览一次强吗?** 否。B1→B2 配对 2W/5L,t9
   0W/3L;precision 27%,73% 的火是 waypoint 噪声。
3. **同 trigger 下 Q3 比 lexical 有真实收益吗?** 否。在线排序 4/7 = 4/7,SR
   B2>B3(t3 1W/4L),延迟 1ms→7.6s。结构化 rerank 的离线优势(Stage A
   R@3 0.592)不迁移到在线(在线 query 更贫瘠、合法时刻更少)。
4. **正确卡进 Top-1/3 但 Planner 未采用的量?** 未观察到集级该瓶颈(proxy
   偏高但方向一致:gold 命中的失败集全部"已跟随")。adoption 不是当前约束。
5. **Trigger 何时误报?** 正常多 waypoint 运输(连续 3 个同 primitive)。
   这是 T4 按冻结规格的实现;信号无 progress 维度,无法区分"重复因为卡住"
   与"重复因为分步移动"。
6. **检索错误时 Planner 行为?** 多数忽略错误卡继续自身计划(soft 模式的
   益处:坏建议不强制);未观察到错误卡直接导致失败的行为链。
7. **helped/harmful 计数?** 代理:helped 8 / harmful 20 / neutral 66。harmful
   以"同类再火"定义,与 trigger 精度问题纠缠,只作候选。
8. **executable memory 下一步?** **NO。** 门槛要求"gold 常进 Top-1/3 +
   adoption 显著偏低 + 被忽略卡事后确认适用"。前两条均不满足(合法时刻仅
   25/94 火;adoption 无瓶颈),强执行只会放大 73% 的噪声火。

## 判定

**NEITHER SUPPORTED**(trigger precision 0.266 且净 SR 为负;structured-vs-lexical
零增益)。**EXECUTABLE MEMORY NEXT: NO。**

建设性结论:三层里只有工程层(access)兑现了在线收益;算法层(trigger 语义、
symptom-text 排序)在在线贫瘠 query 下不成立。若继续,前提是 trigger 获得
progress/物理状态感知(T4 需要"无进展"证据而非"重复"计数),而不是加强排序
或强制执行。

## 仪器记录(不影响判定,后续修复)

- T4 reason 字符串把"当前工具名"当"重复 primitive 名"(如 back_project 到达
  时 reason 写 "back_project x3",实际重复的是前面 3 个 move_to)→ 污染了该
  子集的检索 query 文本。数据照报,代码待修(只影响未来运行)。
- adoption keyword proxy 偏高(RETREAT/OBSERVE 动词重叠常规动作);本轮
  判定不依赖其绝对值。
- smoke attempt 1(仪器 bug,事件丢失)已记 design 文档;该格用修复后代码重跑。
- infra_timeout 共 5 次(GLM 晨间延迟),全部自动重试成功,未入结果行。
