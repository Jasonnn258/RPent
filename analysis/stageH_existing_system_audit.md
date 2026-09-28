# Stage H — 现有系统审计(stageH_existing_system_audit.md)

_2026-09-28。§0 只读审计,零代码改动。全部结论经本机代码/数据直接验证
(文件:行号可点);无任何猜测项,不触发 STOP 条款。_

## 1. state/result 能观察到哪些字段(runtime 工具结果层)

primitive 结果 JSON(经 `ovpm._fields_from_payload` 规范化,
rpent/memory/ovpm.py:157-186;states.json 逐 step 同源):

| 字段 | 出处 | 含义 |
|---|---|---|
| `success` | pi0_pick / pi0_doubled | 技能层自报成功 |
| `peak_lift_m` / `post_min_ascent_m` | pi0_pick(diagnostics) | 实际抬升量 —— 抓取的物理证据 |
| `min_gripper_opening` / `final_gripper_opening` / `start/peak_gripper_opening` | pi0_pick / release | 手爪开合(B2:GRIP_TIGHT=0.03 / GRIP_OPEN=0.05,ovpm.py:48-49) |
| `final_dist_m` / `target_xyz` / `final_eef_pos` | move_to / move_pose | 残余距离 / 目标 / 终点(MOVE_TOL=0.03,ovpm.py:50) |
| `libero_terminated` | 所有 primitive | **任务谓词**(env 官方终止标志,success 判定权威,见 data_handoff_mismatch_report.md) |
| `found` / `world_error` | segment / back_project | 感知是否可用 |
| `chunks_used` / `elapsed_s` / `command{action,prompt,...}` | 全部 | 执行元数据 |
| 机体状态 `robot0_eef_pos/quat/gripper_qpos`、`object_names` | states.json 逐 step `state` 字段 | 本体感知 + 场景物体名单 |

## 2. 哪些字段可 runtime 使用

上表全部 —— 它们就是 planner 当 turn 看到的工具结果本体。现有消费方:
- v1 触发器 T1-T7(rpent/memory/retrieval.py:469-527);
- C2 进度规则 R1-R5(retrieval.py:386-441);
- B2 STV 的 CONFIRMED 三向裁决(rpent/memory/stv.py:576/589/626/679);
- B1 OVP-M outcome 检查(rpent/memory/ovpm.py)。

**runtime 可观测输入面(Stage H graph guard 的合法词汇)** =
上述工具结果字段 + SM1 PhaseTracker 计数器(phase、recent_primitives、
phase_steps、picks_failed、release_open,structured.py:252-256 `_value_for`)
+ 手爪/EEF 本体感知。**不含**:benchmark GT 物体坐标、隐藏 sim 状态。

## 3. 哪些是未来/后验信息,严禁 runtime 使用

| 字段 | 现状 |
|---|---|
| `episode_result` / `verification_result` / `planner_followed_top1` / `planner_followed_any_top3` / `planner_next_action` | memory event 里的占位 None,由**离线分析**回填(retrieval.py:595-599 注释"事后字段") |
| episode 级 success / CSV 的 result 列 | 终局判定,只能做 analysis_only 标签 |
| benchmark GT(success label、物体真值) | 只在分析器;stageC1_queries 等 gold 文件按 Stage D 先例永不进 runtime 路径 |
| 未来的 libero_terminated / 未来 step 的任何字段 | 对当前 decision point 而言是未来信息;H0 基准里标 analysis_only=true |

## 4. trigger / STV / Memory injection 的真实调用路径

单一汇合点 = `rpent/planner/api_loop.py:543-602`(每个 turn boundary):

```
observer 工具结果到达
  ├─ tracker.on_tool_result        # SM1 PhaseTracker(rpent/memory/structured.py:172)
  ├─ outcome_validator.observe     # B1 OVP-M
  ├─ b2_verifier.observe           # B2 STV → b2_events.jsonl(stv.py:294)
  └─ memory_recall.on_tool_result  # 触发器评估(retrieval.py:356)
       v1_per_result: T1-T7 逐结果评估 → _queued_fire(443-459)
turn boundary(api_loop.py:547-602):
  block = tracker.current_block(steps)         # SM1 规则块
       += outcome_validator.turn_boundary_hint()  # B1 提示
       += b2_verifier.turn_boundary_hint()        # B2 提示
       += memory_recall.turn_boundary(steps)      # 触发冲刷+检索+注入块
  → run.enqueue(block) + messages.append       # 唯一注入通道
```

- 触发模式 env:`RPENT_MEMORY_TRIGGER ∈ {1/v1, v1_per_result, progress,
  periodic, motion_stuck}`;G0.5/G0.6 全部用 `v1_per_result`;
- 注入模式 env:`RPENT_MEMORY_INJECTION_MODE ∈ {full, memory_only,
  reason_only, generic_refresh, none}`(retrieval.py:98-100);
  H1 三臂分别对应:generic_refresh(F3 块,103-112)/ full(`_block()`
  卡片渲染,980-996)/ 新增 graph 注入;
- 冷却 COOLDOWN_BOUNDARIES、上限 MAX_TRIGGERS_PER_EPISODE、
  EMPTY 不注入只记事件(603-607)、P0/P1/P2 走 `_fire_without_retrieval`
  (1015-;retrieval_status=NOT_RUN);
- **臂定义先例**:scripts/ovpm_exp.py COND_ENV 字典逐 env 组装
  (g05P0/P2 = SM1+access_fix+v1_per_result+Q0_FIXED+none/generic_refresh;
  g0D = full)。H1 三臂 = 复制该模式,只改 injection_mode。

## 5. Graph 最小接入点

**新模块旁路,零改动冻结路径**。三处最小改动:
1. `rpent/graph/` 新包:schema.py(YAML 加载+校验)、
   state_interpreter.py(可观测事实→active node,**确定性规则**)、
   retriever.py(active node→合法出边)、render.py(node+edges→注入块);
2. 接线点:api_loop.py:570 附近,与 memory_recall 完全同构的新对象
   `graph_recall.turn_boundary(total_steps) -> (block, event)` ——
   同一冷却/上限语义、同一事件 jsonl 格式(active_node/candidate_edges/
   chosen_edge 留待 H2);
3. 调度臂:ovpm_exp.py 新 cond(如 h1GRAPH),COND_ENV 加
   `RPENT_GRAPH=1` + `RPENT_GRAPH_FILE=resources/libero/graph_v0.yaml`;
   H1-CARD 臂 = g0D 等价 env(g05 底座 + full),H1-P2 = g05P2 原样。
   interpreter 输入 = tracker 计数器 + 最近一条 primitive 结果 ——
   已在 api_loop 现场可得,不需要新工具调用。

## 6. Local model 最小接入点

- **全 planner 替换路线**(H2 online 若需要):`--planner api --model
  openai-chat:<model> --base-url http://127.0.0.1:<port>/v1`
  (cli/main.py:93-108 + planner/base.py:120-135 的 provider 前缀机制,
  openai-chat 已在支持列);vLLM 起 OpenAI-compatible server 即插即用,
  权重不进 repo(config/env 传地址)。
- **H2 主路线(edge router)**:local model 不当 planner ——
  `rpent/graph/router.py` 新增独立 OpenAI-client,输入 = task goal +
  active node + evidence + 合法出边的 A/B/C/.../DEFER 选择菜单,
  输出 = 选项字母 → 映射回 edge_id;DEFER → 走 GLM teacher。
  挂在 graph_recall 内部(arm 决定 local/teacher),决策全部落事件流。
  离线评测脚本直接读 H0 基准 + graph_v0 构造 prompt,不需要起仿真。

## 7. H0 抽取可行性(已验证,含样本量预览)

对 180 集全集(states.json 逐 step)跑确定性抽取原型,三类失败全部
有真实物理证据可判:

| 家族 | 确定性判据(全部 runtime 可观测) | 命中 episode 数(首访) |
|---|---|---|
| FALSE_GRASP | pi0_pick success=True 但 peak_lift<5mm(B2 同阈值),或 success=False | 78 |
| MOVE_CONTACT_STALL | 连续 3 个 move 且 residual 不下降(ds[2]≥ds[0]-1e-4,**非纯重复计数**) | 101 |
| RELEASE_PREDICATE_STALL | release 已执行、其后 4 step 内 libero_terminated 仍 False | 17 |

- RELEASE_PREDICATE_STALL 样本偏少(17 集);按 §1 纪律不放宽定义,
  正式抽取时扩到 episode 内多 decision point + memB/memC/OVP-M heldout
  历史轨迹补充,仍不足则如实报告。
- T4 型 `repeated_no_progress: x3`(232/366 事件)是纯重复计数,
  **不**用作 MOVE_STALL 判据(§1 明令禁止),只作候选点筛查。
- primitive 词表(180 集实测):move_to 801 / pi0_pick 286 / move_pose 286 /
  set_gripper 154 / release 146 / rotate_wrist 65 / pi0_doubled 27 /
  rotate_pitch 3 —— graph 节点/边覆盖此词表即可。

## 8. 风险与既有锚点

- **注入行禁忌**:PhaseTracker pick 启发式会 grep "fail/error/no object"
  等词(B2 先例,stv.py 模块注释)—— graph 渲染块必须遵守同一禁词表;
- **占位与事件格式**:graph 事件沿用 memory_events.jsonl 的字段风格
  (episode 占位、finalize 回填),分析器 join 口径不变;
- **G0.6 教训直接可用**:63 格 429 手术 + tier 键绑定 + ≤3 重试纪律
  (rpent-memory-stageg06-conclusion);H1 在线跑沿用同一调度器,
  零新 infra 代码;
- success 判定权威 = states.json 末项 libero_terminated(classify_dir
  同源);12 个 success 无 planner FINISH 属合法,勿用 FINISH 当 ground
  truth(data_handoff_mismatch_report.md);
- validated_recovery 新指标所需全部输入(recovery edge 的
  expected_transition + 干预后逐 step states.json)在现有事件流+
  states.json 中齐备,离线可判,无需新 runtime 字段。

**结论:全部 provenance 确认,§0 通过,可以进入 §1。**
