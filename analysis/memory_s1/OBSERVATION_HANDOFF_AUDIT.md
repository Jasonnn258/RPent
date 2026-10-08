# S1 预注册前审计一:Observation Handoff(重放后 Planner 读到什么)

> 生成:2026-10-08 | 性质:只读源码审计(未改源码/环境,未跑 rollout)
> 问题:Twin-Swap 任务里,PREFIX_REPLAY 完成后,Planner 实际读取的
> 图像、state、world_map 是否对应**重放后的状态**;toolkit 初始化的
> step 0、历史图像路径与缓存是否会污染 Current-only 对照。
> 标注约定:**[S] = 源码证明** / **[R] = 待运行验证** / **[X] = 尚不可行**。

## 一、Planner 观测的供给链(逐环 [S])

| 环 | 事实 | 证据 |
|---|---|---|
| 1. 首条消息 | planner 收到 system + user(含 suite/task/seed/output_dir/recipe_tag,**不含图像**)——图像必须由 planner 主动调 view_driver_state 获得 | `rpent/context/prompts/prompt.py:11-20`(USER 模板);`rpent/planner/base.py:62-98`(solve 接口);`rpent/cli/main.py:190-242` |
| 2. "当前"的定义 | `view_driver_state(step=null)` 返回 **states.json 最后一条** dump(_latest_step)——planner 的"现在"= 最近一次 dump | `robots/libero/tools.py:1604-1607,1546-1553` |
| 3. dump 的内容源 | `dump_state` 现场 `env.raw_obs()` 读低维状态 + `primitives._last_obs["main_images"]` 读图像;每步独立生成图像/深度/world_map 工件,**无跨步累积结构** | `tools.py:904-960`(world_map 逐步工件,929-932/1150-1153) |
| 4. state 隐私设计 | state 只含 EEF 位姿/姿态/夹爪 + **object_names(纯名字、无坐标)**;注释明示"never privileged object coordinates" | `tools.py:939-950` |
| 5. 重放后传观测 | PREFIX 重放末尾 `prims.set_obs(final_obs)`(设 _last_obs 与 EEF/夹爪缓存)→ 其后任何 `dump_state` 拿到的都是重放后状态 | `scripts/stageR_rt.py:184`;`tools.py:151-160` |

**结论([S])**:链条本身干净——planner 的"现在"由 states.json 最后一条决定,而 dump_state 忠实于重放后的 env。**问题不在机制,在初始化时序**(下节)。

## 二、污染通道逐项裁决

### P1【核心缺陷,已定位】step 0 = 交换前状态 [S]

- `LiberoToolkit.__init__` 无条件调用 `init_primitives_clean`
  (`robots/libero/toolkit.py:37`):清工件 → `primitives.reset()` →
  **`dump_state(step_idx=0)`(此时 env 在初始=交换前状态)** →
  发 dashboard 事件。
- 后果:bare boot(Stage R 复用路径,`stageR_rt.py:109-138`)→ PREFIX
  重放(绕过 toolkit)后,**states.json 里唯一的条目 step 0 是交换前
  的 obs+图像**。planner 首次 view_driver_state(null) 会把**交换前
  观察**当作"当前"——双向破坏:① Current-only 基线读到的是历史 B
  状态(污染);② 所有臂的"当前观测"都不是决策点状态(无效)。
- **修法([S],DEV runner 内实现,零库改动)**:重放完成后、planner
  启动前,runner 执行:
  1. 照 `init_primitives_clean` 的清理段(`toolkit.py:122-136`)擦除
     out_dir 工件(states.json/images/depths/world*/metadata/episode_video);
  2. 调 `libero_tools.dump_state(prims, out_dir, step_idx=0, log=None)`
     ——此时读 live env + set_obs 缓存 = **重放后状态成为唯一 step 0**。
  两个函数都是现成模块级工具,runner 拼装即可;不修改任何库文件。
  **[R]** 拼装后的冒烟(S1-DEV0 前置项 1):断言 states.json 仅一条、
  其 EEF/图像 = 重放后测量值。

### P2 图像路径/工件目录 [S]

- 图像路径(images/image_NN.png 等)全部由 dump_state 逐条生成
  (`tools.py:909-927` docstring 清单);P1 的擦除把它们一并清掉,
  planner 可读到的路径只剩重放后 step 0 与其自身动作产生的条目。
- 无"历史图像缓存目录"类额外通道。[S]

### P3 env 渲染缓存 [R]

- `env._cached_full_image` 为按需渲染缓存(env_server.py:322-327);
  重放后的首次感知调用(segment/render)会刷新。机制上无陈旧帧进入
  planner 的路径,但**首次调用确实落在重放后场景**这一点需 DEV0 冒烟
  确认(前置项 1 的附带断言)。**[R]**

### P4 录像与审计工件 [S]

- `start_recording` 的帧只在 `_step_env/_vlm_chunk` 里追加
  (`tools.py:176-199`);PREFIX 重放直连 `env.step` 不录帧 →
  episode.mp4 不含 prefix,无泄漏;rtrace/stageR 仪器工件与本审计
  无关(planner 不可见,输出目录不同段)。

### P5 planner 后端的记忆文件访问 [S,设计约束]

- 文件型后端(claude_code/codex)构造时挂 `extra_dirs=memory 目录`
  (`rpent/planner/base.py:178,198`)——**S1 各臂一律用 api 后端**
  (现行实验后端),该通道不存在;此为预注册排除条款而非待修项。

### P6 注入机制(卡片/进度触发) [S]

- DecisionMemory/PhaseTracker 注入由 `RPENT_MEMORY_TRIGGER` 门控
  (`api_loop.py:342-344`),fresh planner + 关门 = B0 无注入;
  记忆臂(C3/C4)走同一注入机制喂观测导出内容——机制复用、来源受控。

## 三、handoff 交接清单(DEV runner 规格,供预注册引用)

1. bare boot(现成)→ PREFIX 重放(现成,`stageR_rt.reconstruct_prefix`)
2. **[新增拼装]** 擦 out_dir 工件 + `dump_state(step_idx=0)`(P1 修法)
3. 冷启动 api planner(门控按臂配置)→ planner 自取 view_driver_state
4. 仪器侧同时记录:决策点 sim_measurement(EEF/物体位姿/成功态,
   A/B 等价性审计用)——只进离线分析,不进 planner

## 四、本审计判定

- 交接机制:**可行 [S]**;唯一实质缺陷 P1 已定位且有不改库的修法;
- 三个前置验证项全部属于 S1-DEV0 冒烟范围(单 episode 级),不阻塞
  预注册起草;
- 无 [X] 项。
