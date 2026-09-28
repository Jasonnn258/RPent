# Stage H1 预注册 — Frozen Graph vs Flat Cards vs Generic Refresh(三臂在线实验)

_2026-09-28。本文档先于任何 H1 代码实现 commit 与任何在线运行(prereg 纪律,
同 G0.5/G0.6)。对象:§2 冻结的 graph v0(11 节点/25 边,analysis/graph_v0.yaml,
§3 audit ALL GATES PASS)× §1 基准定义的三失败家族。_

## 1. 研究问题与判定

**H1(表示层)**:在真实可观测物理失败状态上,冻结局部状态转移图提供的指导
是否 (a) 优于扁平 Top-3 记忆卡(表示对照),且 (b) 超出泛型重定向控制(下界对照)?

判定:REPRESENTATION: SUPPORTED / PARTIALLY SUPPORTED / NOT SUPPORTED
(按 §7 门组合;FAIL 即 STOP,不改图、不补跑)。

混淆控制:三臂共享同一触发器(graph 触发,见 §3)、同一冻结栈(GLM
glm-5.3-flash / Pi0.5 / SAM3 / primitives / turn budget 40 / temperature /
B2 verifier / SM1 tracker),唯一差异 = 触发后注入的**内容**。

## 2. 三臂定义(env 级,逐字节)

| 臂 | RPENT_MEMORY_TRIGGER | RPENT_MEMORY_INJECTION_MODE | 注入内容 |
|---|---|---|---|
| H1-P2 | `graph` | `generic_refresh` | F3 GENERIC_REFRESH_BLOCK 逐字节(= g05P2 内容) |
| H1-CARD | `graph` | `memory_only` | F4 中性头 + 冻结 Top-3 卡正文(= g05P3 内容;common query + Q0_FIXED 排序,reason 永不进 query/正文) |
| H1-GRAPH | `graph` | `graph_block` | render_block:active node + 合法出边(guard 过滤后;不塞整图) |

三臂共同 env(与 g05 系完全一致,除触发器外):
`RPENT_STRUCTURED_MEMORY=1, RPENT_MEMORY_ACCESS_FIX=1,
RPENT_MEMORY_QUERY_MODE=common, RPENT_MEMORY_RANK=Q0_FIXED,
RPENT_MEMORY_QUERY_REASON=0`。
调度:scripts/ovpm_exp.py 新 stage `h1`,conds `h1P2/h1C/h1G`,repeat r1。

## 3. graph 触发器(三臂同一代码路径)

- 逐结果评估:每条 primitive 结果到达时,用与 §1 基准抽取器**同语义**的
  计数器(consec_move_stall / release_open / actions_since_release /
  prior_pick_success;由 recall 内部维护的原语结果历史重算)构造白名单事实,
  过冻结 interpreter(rpent/graph/state_interpreter.interpret)得 active node。
- 触发条件:node ∈ {FALSE_GRASP, MOVE_STALL, CONTACT_STALL,
  RELEASE_PREDICATE_STALL}(四失败节点)且同**基准家族**非邻接 ——
  按家族键记 last_fam_step,`last >= i-1` 即延续(与基准抽取器
  "同家族紧邻步只保留首个"逐语句同构,含 skip-不更新的 quirk;step 序
  只计 actuation 原语,感知步不进序 —— states.json 词汇)。离开失败
  家族后复发可再次触发。〔修订 2026-09-28,先于任何运行:把
  "≠ 上次触发节点"精确为家族键邻接抑制,与基准抽取器逐语句一致,
  使 §3(b) 重放校验可逐点对齐。〕
- 冲刷/冷却/上限:走冻结的 per-result 冲刷路径(_flush_boundary 语义:
  冷却中丢弃、MAX_TRIGGERS_PER_EPISODE=6 到顶丢弃),与 v1_per_result/
  progress 完全同一实现。
- 事件日志:memory_events.jsonl(三臂同格式;graph_block 事件附
  graph_node / graph_legal_edges 字段)。

**运行前验证(必须全过才许跑在线)**:
- (a) 单测:graph 模式触发/冷却/上限;CARD 内容与 g05P3 渲染逐字节一致;
  P2 内容 = GENERIC_REFRESH_BLOCK;
- (b) 离线重放校验:把 G0.5/G0.6 180 集 states.json 逐 result 重放过运行时
  graph 触发逻辑(无 LLM、无 env),fire 点集合必须 = 基准 148 决策点
  (允许仅因冷却丢弃的差异,逐条列出并说明);
- (c) DEV 冒烟:每臂 1 集,rc=0 且 memory_events.jsonl 有合理事件、注入块
  无违禁词。〔口径澄清 2026-09-28,冒烟第三轮后、全量运行前:违禁词
  检查适用于**新内容臂**(H1-P2 的 F3 文本、H1-GRAPH 的图渲染)——
  两者冒烟全净;H1-CARD 注入的是 §8 冻结的 61 卡正文(= g05P3 内容,
  G0.5 时代同款注入),其中 2 张卡的 falsify/how_to 含 "fail" 子串,
  属冻结基线继承行为,如实报告、不改卡(§8 优先)。〕

## 4. 30 matched cells(确定性选取,已在 prereg 时锁定)

来源:H0 基准 148 点的 (task,seed) cells。规则(按 (task,seed) 升序):
REL 证据 cells 取前 10 → CONTACT 证据未选 cells 取至 10 → 仅 FG cells 补足 30。

```
(3,1)(3,2)(3,3)(3,4)(3,5)(3,6)(3,7)(3,8)(3,9)(3,10)
(3,11)(3,12)(3,13)(3,14)(3,15)(3,16)(3,18)
(5,1)(5,13)(5,18)
(9,2)(9,3)(9,5)(9,6)(9,8)(9,10)(9,12)(9,13)(9,15)(9,17)
```

家族覆盖(cell 数):FALSE_GRASP 23、RELEASE_PREDICATE_STALL 14、
MOVE_CONTACT_STALL 12。seeds 与 G0.5/G0.6 相同(1-20 内),init states
与历史一致 → 失败状态会自然复现。每 cell × 3 臂 = **90 episodes**。
(seed 显式传入;tier 启动 60 秒内核对 —— 历史教训。)

## 5. 指标(全部冻结定义)

设一次 fire 于第 t 个 primitive step(事件日志 + states.json 对齐)。

**validated_recovery(主指标)**:fire 后 W=5 个 primitive steps 窗口内,
该失败家族的物理证据被**观测性验证**清除:
- FALSE_GRASP:窗口内出现 pi0_pick success=True 且 peak_lift_m ≥ 0.005
  (真实握持),或 libero_terminated=True;
- MOVE_STALL:窗口内 move final_dist_m < 0.03(到位),或 libero_terminated;
- CONTACT_STALL:窗口内 pi0_doubled success=True,或 pi0_pick 成抓
  (success=True 且 lift ≥ 0.005),或 libero_terminated;
- RELEASE_PREDICATE_STALL:窗口内 libero_terminated=True,或重新成抓
  (pi0_pick success=True 且 lift ≥ 0.005,持物重试放置)。
episode 级:有 fire 的 episode 中 ≥1 次 fire 被验证的比例。分臂分家族报告;
分母(有 fire 的 episode 数)如实给出。

**post_intervention_progress@3(diagnostic,不作门)**:fire 后 3 步内
libero_terminated 或相位推进(旧"3 步恢复"口径,仅诊断)。

**wrong_phase_advice_rate**:fire 时注入块未提及 active node 任一合法边
action_family 映射的原语。冻结映射(action_family → 原语集):
perceive/perceive_hires→{segment,detect,back_project};
grasp/grasp_retry→{pi0_pick};
grasp_offset→{pi0_pick,move_pose,rotate_wrist,rotate_pitch};
verify_hold→{detect,segment};
transport/move_waypoint/retreat_reapproach/approach→{move_to,move_pose};
grip_adjust_retry→{set_gripper,pi0_pick};
contact_settling→{pi0_doubled,move_pose};
place→{release,move_to,move_pose};
micro_reposition→{move_to,move_pose,rotate_wrist};
repick_replace→{pi0_pick,move_to,release};
observe→{detect,segment,view_driver_state};
planner_judgment/finish→全原语集。
判定 = 注入块文本与匹配词表的词面交为空;匹配词表 = 上述映射原语集
**∪ 合法边 action_family 名本身**。〔修订 2026-09-28,先于任何 H1 在线
结果分析:graph v0 的渲染词汇是 action_family(如 grasp_offset)+现象
描述,不含原语名(pi0_pick 等);原字面口径会把语义上完全相位适配的
GRAPH 块全判 wrong——度量对象应是"建议是否指向该状态的合法行动",
不是建议用哪种词表书写。action_family 名加入匹配词表后,CARD/P2 的
判定不变(卡片/泛型文本不含 action_family 复合词)。guard_violation
不受影响(它评判 planner 的下一条**实际动作原语**,本就是原语词汇)。〕
图作为**评分器**评三臂(冻结,非_actor)。

**guard_violation_rate(仅 H1-GRAPH,安全门)**:fire 后 planner 的下一条
**动作**原语(pi0_pick/pi0_doubled/move_to/move_pose/release/set_gripper/
rotate_wrist/rotate_pitch)不在 active node 合法边映射原语集内(感知类
segment/detect/back_project/view_driver_state 与 finish 不计 —— 信息获取
不违反物理 guard)。

**SR**:episode 成功 = states.json 末条 libero_terminated(冻结口径)。

## 6. 对照与统计口径

- 主对照:GRAPH vs CARD(表示问题);GRAPH vs P2(超出泛型下界)。
- 配对:同 cell 三臂配对;报告比例、配对差、cell 级翻转计数;
  n=30 下绝对 pp 门为主判(§7),二项 95% CI 附报(诚实呈现小样本)。
- 有 fire 才进 validated_recovery 分母;无 fire episode 计入 SR 与
  no-harm 面但不进 VR。若某臂 fire 覆盖 < 20 episodes → 如实降级为
  INCONCLUSIVE-VR,SR 面照判。

## 7. 门(preregistered,全打印)

**机制门(必须双过)**:
- M1 wrong_phase_advice_rate(GRAPH)≤ 0.5 × wrong_phase_advice_rate(CARD);
- M2 guard_violation_rate(GRAPH) ≤ 2%。

**行为门(A 或 B 过其一)**:
- A:validated_recovery(GRAPH) ≥ max(VR_CARD, VR_P2) + 10pp
  且 SR(GRAPH) ≥ max(SR_CARD, SR_P2) − 3pp;
- B:SR(GRAPH) ≥ max(SR_CARD, SR_P2) + 8pp
  且 VR(GRAPH) ≥ max(VR_CARD, VR_P2)(不降)。

**家族门**:三失败家族中 ≥2 个 GRAPH − 对照(取 CARD/P2 中 VR 较高者)
配对差 ≥ 0。

**判定**:机制门 + 行为门 + 家族门全过 = REPRESENTATION SUPPORTED
(→ 冻结并扩展 60 cells:本 30 + 新 seed(21-40)30,新真实 episode);
任一门不过 = NOT SUPPORTED → **STOP,不改图不补跑**;机制门过但行为门
差 ≤3pp(边界)= PARTIALLY SUPPORTED,如实记录并 STOP(不自动扩量)。

## 8. 冻结清单(H1 全程不动)

graph v0(节点/边/guard/verifier/文本)、interpreter 规则与阈值、
render 文本、F3/F4 文本、61 张全局卡与 MEMORY.md、Q0_FIXED 排序、
common query 模式、SM1 tracker 及其注入块、B2 verifier、OVP-M 关闭态
(同 g05)、Planner/Pi0.5/SAM3/primitives/turn budget 40、model
temperature、触发冷却/上限常数。三臂差异仅 §2 表中两个 env 的取值。

## 9. 运行纪律

- dev_preflight 先行;调度器 ovpm_exp.py 自带锁与并发 cap(≤8);
- infra 错误 ≤3 次重试,429 配额签名按事故账流程;rc=0+0turns 按 infra 处理;
- 日志全部落 repo logs/ 与持久卷;不碰他人进程;
- 90 episodes 预计墙钟 ~4-6h(调度器串行池 ≤8 并发,单集 ~8-15min)。

## 10. STOP 边界

- §3 运行前验证任一不过 → 修基建(不算改冻结件)直至通过,不通过不跑;
- 在线过程中发现注入块混入 analysis_only 信息(审 memory_events.jsonl
  注入文本)→ 立即停,按泄露事故处理;
- 门 FAIL → STOP;无任何"看完结果再调图/调阈值"的循环。
