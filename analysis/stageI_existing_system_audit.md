# Stage I §0 — 现有系统审计(只读,2026-09-29)

_对象:Stage H 收口后的 RPent 栈。全部结论给 file:line 证据;本阶段零代码改动。_

## Q1. Main Planner 的真实输入输出接口

- **构造**:`rpent/planner/base.py:102 build_planner(planner_type="api", model, base_url,
  max_tokens, planner_timeout_s)` → `ApiAgentLoop`(rpent/planner/api_loop.py:263)。
  底层 = **pydantic-ai 2.38**(vla env,`pydantic-ai-slim 2.38.0` + `openai 3.7.0` +
  `anthropic 1.3.0`),model 串带 provider 前缀(`anthropic:glm-5.3-flash`)。
- **输入**:① system prompt = `robots/libero/prompts/system.py` 十段拼接
  (GOAL/RULES/PROVEN_LEVERS/PERCEPTION_ALGORITHM/RUNTIME/LOCALIZATION/…,
  合计 ~26K chars ≈ 6-7K token);② 初始 user message = 任务描述;
  ③ tools spec = `toolkit.get_tools_spec()`(rpent/tools/toolkit.py:150);
  ④ 运行中:工具结果回流 + turn-boundary 注入块(见 Q4/§5)+ 可选图片
  (api_loop 图像预算剪枝 `ProcessHistory(processor=_prune_history_images)`,
  api_loop.py:811;`--no-images` 开关存在,GLM 路径常规开图)。
- **循环**:model turn → tool calls → `toolkit.execute_tool(name,args)`
  (api_loop.py:453)→ 结果以消息回流;turn 上限 40(ovpm_exp.py:55
  `EVAL_TURNS=40`);每 turn 预算 `PLANNER_TIMEOUT_S=3600`、
  `PLANNER_MAX_TOKENS=24576`(ovpm_exp.py:61/69;24576 是 GLM thinking
  budget 16384 + headroom 的产物 —— 本地模型需另行定值,入 I1 预注册)。
- **输出**:`PlannerResult{finish_result{status,summary}, messages, stats
  {tokens, turns_used, tool_calls}, error}`(base.py:35)。

## Q2. 哪些逻辑强依赖远程 GLM

**只有一处**:planner 的 LLM 调用本身。证据链:
- `scripts/ovpm_exp.py:95-99`:`TIERS = {"glm-5.3": "anthropic:…",
  "glm-5.3-flash": "anthropic:glm-5.3-flash"}` + `GLM_BASE_URL =
  "https://open.bigmodel.cn/api/anthropic"`;
- `run_episode`(ovpm_exp.py:400-410)把 `--model`/`--base-url` 传给
  `rpent` CLI;API key 从 `/workspace/yjx/rpent_data/rpent_env.sh` 的
  `GLM_API_KEY=` 注入 env(ovpm_exp.py:352-361,永不落日志);
- 其余全部本地:Pi0.5/SAM3/8 原语(robot GPU 推理)、interpreter/graph/
  memory、调度器、states.json/memory_events.jsonl 落盘。
- 附带远程痕迹:pydantic-ai `ANTHROPIC_THINKING_BUDGET_MAP`(仅影响
  anthropic provider;openai-chat provider 不走该路径)。

## Q3. 哪些地方可直接替换为 OpenAI-compatible local server

**最小接入点 = `build_planner` 的 `(model, base_url)` 两个参数,零业务代码改动**:
- model 串换 `openai-chat:<served-name>`(base.py:120 注释明示该形态);
- `base_url` 传 `http://127.0.0.1:<port>/v1` → base.py:135-150
  `_provider_factory` 已实现"base_url 覆盖 provider 端点"的通用逻辑
  (OpenAIChatProvider 接受 base_url);
- `OPENAI_API_KEY=<dummy>` 由 env 提供。
- api_loop 的会话/工具/注入逻辑全部 provider 无关(node.stream /
  run.enqueue / execute_tool)。
- 需要新增的只有:TIERS 加一个本地 tier + base_url 分流 + Qwen3.5
  thinking 关闭(建议 vLLM 启动时 `--chat-template` 固化
  enable_thinking=False,服务端解决,客户端零 patch)。

## Q4. Stage H Graph 的 state/edge/guard/verifier 现在实际如何工作

- **state**:逐工具结果 → `DecisionMemory._graph_observe`(retrieval.py:412,
  envelope 解包后)维护白名单计数器 → `rpent/graph/state_interpreter.
  node_label(obs,last)` → active node ∈ 11 节点(4 失败节点 +
  正常相位节点)。
- **edge**:`rpent/graph/retriever.py legal_edges(graph,node,facts)`
  按 guard 过滤合法出边;图本体 `analysis/graph_v0.yaml`(11 节点/25 边)。
- **guard**:目前只是**边级过滤谓词**(决定哪些边进菜单),不是动作级
  约束 —— 这正是 H1 M2 90% violation 的结构原因。
- **verifier**:边上的**文本字段**("expected 物理变化"的描述),
  从未在线执行过;在线判定一直靠离线分析器的家族物理证据规则
  (analyze_stageH1.fire_validated)。→ I1 §4 的 verifier 必须落成
  机器可判的物理判据(复用 H1 §5 冻结规则的字段:success/
  peak_lift_m/final_dist_m/libero_terminated)。
- **soft 注入**:api_loop.py:544-605 —— 每 turn 流结束后
  `memory_recall.turn_boundary()` fire → block 以 user message 注入
  (`run.enqueue(block, priority="asap")` / pending_block 合并)。
  **这就是 SOFT→HARD 的换装点**。
- **绕过 LLM 直接执行工具的现成先例**:Dual-route Fast 分支
  (api_loop.py:441-487):`router.decide() → toolkit.execute_tool() →
  messages.append({"role":"user","content":action_summary})`。
  Authority runtime 镜像该分支即可(HARD 臂:fire 时执行选中边、
  把执行摘要回灌对话、planner 不得覆盖)。

## Q5. 148 decision points / 104 fire records 的 provenance

- **148 点**:`analysis/stageH0_failure_states.jsonl`,源自 G0.5/G0.6
  final 180 matched trajectories(outcome_validation_runs.csv 指向),
  确定性抽取器 `scripts/build_stageH0_failure_states.py`,三家族判据
  全 runtime 可观测、协议 `analysis/stageH0_protocol.md`(含 split 纪律
  md5(task,seed)%100<40→validation)。每点字段 runtime_view /
  analysis_only 硬分离。
- **104 fire**:`analysis/stageH_transition_dataset.jsonl` src=h1 部分,
  源自 H1 90 集(30 冻结格×3 臂,CSV 全行 infra=0),重放触发 +
  memory_events.jsonl 逐点交叉核对(不一致 13 集按冻结口径剔除并
  列明);sha256 = 28d569f…(commit 22aca81)。
- **结论:provenance 完整,可作 I0 底料。**

## Q6. 当前哪些状态字段可以 runtime 使用

- 原语结果字段(运行时 planner/触发器真实看到的):`success`,
  `peak_lift_m`, `min_gripper_opening`, `final_gripper_opening`,
  `final_dist_m`, `chunks_used`, `libero_terminated`, `instruction`,
  各 diagnostics(z/descent/ascent 等);
- 顶层 envelope:`task_language`, `state` 步号, 图片 artifact 路径;
- 由结果历史**在线重算**的计数器:consec_move_stall / release_open /
  actions_since_release / prior_pick_success(white-list facts);
- 相位(phase tracker)、turn 数、注入块文本。

## Q7. 哪些 future/hidden/outcome 字段禁止 runtime 使用

- `analysis_only.*`(episode_final_success、source_path、split)——
  loader 按字段名硬过滤,router/planner prompt 永不读取;
- 基准标签与 correct_set(H2 items / 未来 I0 标签)只在离线评测侧;
- W=5 未来窗口的验证结果、episode 终局、GT success、隐藏仿真器状态
  (物体真实位姿/接触表)、benchmark hidden info。
- B2 遗留红线:注入块违禁词表("fail"/"error"/"could not"/"no object")
  同样适用于 I1 的 router/authority 文本。

## Q8. Local model 最小接入点

1. **Planner 主通道**:`build_planner(model="openai-chat:…",
   base_url="http://127.0.0.1:PORT/v1")` —— 纯配置,见 Q3;
2. **Router 通道**(I-HARD-LOCAL):独立 OpenAI client 直连同一 vLLM
   server(与 H2 预注册架构一致:输入=task goal+node+证据+合法边,
   输出=edge_id/DEFER,单次短生成);
3. **服务**:`sglm` env(/workspace/yjx/envs/sglm,vLLM 0.1.1.dev,
  transformers 5.17,已验证支持 Qwen3_5ForConditionalGeneration)
  起 OpenAI-compatible server;vla env 冻结栈零安装;
4. **权重**(不进 repo):Qwen3.5-4B 已在 /workspace/yjx/models
  (8.8G);Qwen3.5-9B 下载中(hf-mirror,~20G);
5. **执行通道**:`toolkit.execute_tool`(8 原语全可编程调用:
  pi0_pick(prompt)/pi0_doubled(prompt)/move_to(xyz)/move_pose/
   release()/set_gripper(gripper)/rotate_wrist/rotate_pitch/
  segment(prompt)/detect/back_project —— robots/libero/tools.py:202-804)。

## 差距清单(Stage I 需要新建的件,全部待预注册后实现)

| # | 缺口 | 位置(计划) |
|---|---|---|
| 1 | 本地 tier + base_url 分流 + start_local_model.sh | ovpm_exp TIERS / scripts/ |
| 2 | Qwen3.5 thinking 服务端关闭(chat template 固化) | vLLM 启动参数 |
| 3 | executable edge 编译(option/executor/verifier/max_attempts) | rpent/graph/exec.py + analysis/graph_v0_exec.yaml |
| 4 | Authority runtime(fire→router→guard→execute→verify→return) | api_loop 注入接缝 + 镜像 Fast 分支 |
| 5 | 双层日志(planner decisions + authority events) | 新 jsonl writer |
| 6 | 本地 planner 的 max_tokens/temperature/上下文纪律定值 | stageI_prereg |

**§0 结论:全部接口与 provenance 确认,无 STOP 项,可进 I0。**
