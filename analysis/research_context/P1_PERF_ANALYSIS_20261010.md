# P1 仿真性能分析与安全加速(2026-10-10)

**范围**:DEV1A 8 集 pilot 日志的只读拆解 + 隔离工程测量。零新 episode、
零 D-041 额度消耗(D-041 已 8/8 结清)。目的:找出不改变任何冻结行为
(物理步长/控制频率/Action Chunk/成功判据/种子/任务配额/接触标签定义/
评价时序)的工程加速点。

**数据源**:
- `artifacts/p1_perf/perf_breakdown.json`(run.log 秒级时间戳拆解,8 集)
- `artifacts/p1_perf/microbench.json`(osmesa CPU 微基准,t9 seed0 裸 env)
- `artifacts/p1_perf/vla_persist_check.json`(常驻服务隔离验证,GPU0)
- 原始依据:`artifacts/p1_dev1a/`(不提交,私有)

---

## 一、瓶颈占比(8 集聚合,总墙钟 5385.6s)

| 环节 | 总耗时 | 占比 | 可优化性 |
|---|---|---|---|
| Planner API(含等待/生成) | ~4100s | **76.1%** | 冻结(协议层),不动 |
| init(env 构建+**Pi0.5 加载**+sam3) | 729s | 13.5% | **Pi0.5 重复加载 9.8%** → 常驻服务 |
| 工具执行(pi0_pick 178s + move_to 163s + 其余) | 367s | 6.8% | 内含渲染/落盘 <1%,不动 |
| teardown(SIGTERM 宽限为主) | 189.6s | 3.5% | kill 宽限 30s → 可缩 |
| **其中 1024 hi-res 渲染+落盘** | ~2.4s/集 | **<1%** | 非瓶颈,不动 |

拆解说明:
- planner_api_est = 主循环 − Σtool(秒级时间戳,含少量日志间隙,已标注);
- init 每集平坦 ~90s,其中 **vla_server "model ready in 63.8-69.8s"** 是主体;
  env_server/sam3_server 并行 spawn,不构成关键路径;
- teardown:6 个被终止集各 ~31s(SIGTERM 30s 宽限被完整消耗后 SIGKILL),
  2 个自然退出集仅 1-2.5s;
- 微基准(osmesa CPU,单 worker):env step 162ms(含 256 obs 渲染)、
  1024 渲染 ~79ms/视角、**PNG 1024 写盘 156ms(dump 内最贵单项)**、
  npy float16 8.5ms、env 构建 6.5s、reset 13.9s。
  dump_state 每集 ~5 次(planner 调用,非高频),单次 ~0.5s → 不值得动。

## 二、只读环境检查结论

- **EGL 结构性不可用**:`/dev/dri` 在本容器不存在、EGL python 模块缺失。
  结论与既往一致:**继续 osmesa,绝不切换正式实验渲染路径**(GPU EGL
  前提不成立,未做任何渲染切换测试)。
- CPU 配额 28 核(cgroup 2800000/100000),负载 ~14;GPU0 空闲、GPU1-7
  他人占用。所有测量单 worker、GPU0、≤3 分钟,符合开发机纪律。

## 三、逐项评估与处置

### C1. 1024 高频渲染必要性 → **非瓶颈,保持原样**
- 事实核正:1024² RGB+depth 并非每步渲染,只在 planner 调 dump_state 时
  (~5 次/集),且自动删除 step_idx−4 之前的 hi-res 工件;每集总成本
  ~2.4s(<1% 墙钟)。
- 按需生成方案(评估后不实施):将 dump_state 的 hi 渲染改为 lazy——
  先落 256 + 元数据,审计重放时按需重渲染。**否决理由**:hi-res PNG 的
  sha 已进入同刻证据链(源 hash 记录),lazy 化会改变已冻结的工件指纹;
  收益 <1% 不抵风险。
- **处置:不动。**

### C2. Pi0.5 常驻服务 → **明确收益,已验证,接线为默认关**
- 现状:每集 spawn vla_server → 重复加载 63.8-69.8s × 8 集 ≈ 528s(9.8%)。
- 生产代码本就支持 `--vla-endpoint` 连外部常驻服务;缺的是 runner 侧
  生命周期管理。
- 隔离验证(见 D 节结果)。
- **处置:runner 增加 opt-in 常驻模式(默认关);启用预计每集省 ~65s。**

### C3. teardown kill 宽限 → **小收益,改为可配置(默认不变)**
- 6 个被终止集 × 30s SIGTERM 宽限 ≈ 186s(3.5%):宽限被完整消耗,说明
  agent 组内成员(vla/env/sam3 daemons)不响应 SIGTERM,最终都吃 SIGKILL。
- 证据安全:D-041 G4 账本 fsync 原子、probe 后逐步落 steps 事件,
  早 SIGKILL 不损失审计(EP1 事故后已把 finalize 前移)。
- **处置:`P1_KILL_GRACE_S` 环境变量化(默认 30s 不变);未来批次可设
  5s,预计每个被终止集省 ~25s。**

### C4. Manifest 停止条件 → **已满足,无需改**
- 预注册 `TERMINATE_AFTER_PROBE`:6 触发集全部在取得 t_lift_end 证据后
  由 runner 立即终止(`terminated_by=probe_done(terminate_after_probe)`),
  评价时序未动;2 无触发集自然退出。**不存在"证据取完后继续空转"浪费。**

## 四、验证结果(工程测量,零 D-041 额度)

### D. Pi0.5 常驻服务验证(隔离,GPU0,~4min)— **PASS**

`scripts/p1_perf_vla_persist_check.py` → `artifacts/p1_perf/vla_persist_check.json`
(原始动作存 `vla_persist_actions.npz`,均私有不提交):

- 生产入口 `vla_server.py` 起一次(加载 78s),A/B 两条指令交错各调
  6-7 次真 obs(DEV1A s2002 真实 256 帧 + 生产口径 8 维 state),全程无崩溃。
- **任务隔离 PASS**:22/35 个动作维 Welch z>3(max z=13.25)——指令变化
  系统性驱动输出变化,服务不缓存任务;组内包络(单对 max|Δ|=0.46)=
  该模型自身非确定幅度(Stage J 口径 ~0.23-0.38 的同族量级)。
- **无漂移 PASS**:A 首 4 次与末 3 次均值差 0.153 ≤ 包络 0.458——跨调用
  无污染(与代码互证:vla_server 每请求新建 obs,无实例级任务状态)。
- 首调 1.34s,后续亚秒——常驻模式下不存在每集冷启动推理惩罚。
- 判据演化说明(如实记录):首版"单对调用 10×分离"与"max-dim 2×包络"
  两版判据均被模型非确定性淹没(分离 0.63-0.78 vs 包络 0.40,只 1.6-2×),
  最终采用逐维 Welch z 计数——这是判据设计修正,不是数据挑选;三版运行
  的完整输出均保留在任务输出中。

## 五、实施清单(排序:收益/风险/有效性)

| # | 优化 | 预计节省 | 风险 | 状态 |
|---|---|---|---|---|
| 1 | Pi0.5 常驻服务 opt-in | ~65s/集(9.8%) | 推断非确定本就存在(Stage J),常驻不扩大包络(§四已验证) | **已实现,默认关** |
| 2 | kill 宽限可配置 | ~25s/被终止集(~2.8%) | 审计已 fsync 前移,无证据风险 | **已实现,默认 30s 不变** |
| 3 | 1024 按需渲染 | <1% | 改变冻结工件指纹 | **不实施** |
| 4 | PNG 写盘优化 | <0.5% | sha 变化 | **不实施** |
| 5 | EGL 渲染 | — | 结构性不可用 | **不可行** |

实现落点(均为增量,默认行为零变化):

- `scripts/p1_dev1a_run.py`
  - `--vla-endpoint URL`:透传给 agent(生产 CLI 本就支持,连外部常驻服务);
  - `--persistent-vla`:runner 自起整批共用 vla_server(healthz 就绪后逐集
    传 endpoint,finally 回收);二者互斥;
  - `P1_KILL_GRACE_S` 环境变量(默认 30 与 D-041 冻结口径一致)。
- 等价性验证:`--selftest` G4 全 PASS;`--dry-run` manifest sha 仍为
  b57ce6c9(与 D-041 封版一致);无旗标时 agent cmd 逐字节不变(23 参数
  前缀断言)。未来批次启用方式与预期收益见 §七。

## 六、影响的数据字段(逐项)

- #1 常驻服务:不改任何字段;`vla_server.log` 由每集一份变为批次一份;
  actions 数值在模型非确定包络内(与 fresh-load 同分布,Stage J 口径)。
- #2 kill 宽限:不改任何字段;`episode_killed.how` 可能从
  `SIGTERM_then_SIGKILL` 变为更早的 SIGKILL(记录语义不变)。
- #3/#4 若实施会改 hi-res PNG sha → **因此不实施**。

## 七、尚未验证项(如实标注)

- 常驻模式的**整批端到端**收益(~65s/集)为日志推算 + 隔离验证,未跑
  完整 episode 对照(那需要新 episode,违反本轮约束)。
- 微基准绝对值来自共享机器单次运行,±20% 噪声(已在 caveats 标注)。
- kill 宽限 5s 的实际节省未实测(只测到现状 30s 全额消耗)。
- 常驻模式下 gpu_s 账户口径:仍按 episode 窗口采样,集间空转的常驻权重
  显存不计入(与现口径一致,但需在 DEV1B manifest 预注册时明示)。
- 未来批次启用示例:
  `python scripts/p1_dev1a_run.py --persistent-vla`(runner 全托管)或
  自起服务后 `--vla-endpoint http://127.0.0.1:<port>`;
  `P1_KILL_GRACE_S=5 python scripts/p1_dev1a_run.py --persistent-vla`。

## 八、Planner API 精细测量（2026-10-10 后续补充，未新跑 Episode）

**核心修正**：上一轮按总耗时减去已记录工具执行时间得到的 `Planner API≈76.1%` 是**残差估计**，并非逐次模型请求的精确 API 服务端延迟；其中可能含 Python Agent 图运行、工具事件记录、网络往返、远端排队和生成。不能以这个残差直接宣称 GLM 服务端推理占 76%。

已独立提交 **默认关闭、opt-in** 的私有性能记录器：

- `rpent/utils/api_latency_probe.py`：使用 monotonic 时钟，仅记录模型请求图节点持续时间、响应类型、单次模型响应 RequestUsage 的输入/输出与缓存 token 计数；从不保存原始 Prompt、模型响应、API Key、图片、工具参数或任务明细。
- `rpent/planner/api_loop.py`：在 Pydantic-AI `ModelRequestNode → CallToolsNode/End` 的既有流程旁路测量，只有环境变量 `RPENT_API_LATENCY_LOG` 明确指向仓库 `artifacts/` 下的 .jsonl 文件才生效。未配置时默认工具/模型请求语义不变；测量出错只禁用 profiler，不中断模型与机器人物理动作。
- `analysis/research_context/test_p1_api_latency_probe.py`：纯合成测试覆盖无环境变量、非法路径拒绝、原始载荷不落盘、连续请求计时、请求未开始、重复开始和异常耗时。
- **本次未连接私有实验服务器执行这些测试，也没有以本 profiler 运行新的模型 API 请求或仿真 Episode**。需要服务器 Agent 后续 `unittest` 和现有日志核验后才能判定具体耗时。

待获得真实逐请求计时后，应先按 model request 数量、各请求 p50/p90/max、累计 model-node 等待占比、单请求输入/输出 token 与 prompt-cache 用量、timeout/error 频率归因。客户端图节点总时间仍**无法**单独分出网络时延 / 模型服务端排队 / 首 token 延迟，若提供方有相应指标才能进一步拆分。任何 Prompt 压缩、换模型/推理档位、截短 Planner 轮次或工具集合均可能改变物理行动轨迹；必须在 DEV1B 新 cohort 单独预注册、同预算对照，不能静默修改 D-041 已封版 DEV1A。

**额外预算风险**：上一轮报告提到持久 VLA 在 Episode 间的常驻 GPU 占用未包含在旧 `gpu_s` 口径里；因此 `--persistent-vla` 不能仅以旧 Episode 窗口 GPU 账本宣称遵守全生命周期预算。未来启用之前应按 GPU 资源占用时间的实际计费合同，明确持久服务冷启动、空闲和共享 GPU 是否计入，实施不重复也不漏算的资源时间核算，重新进行 G4 验收。

**状态**：`API_NODE_PROFILER_CODE_COMMITTED_DEFAULT_OFF / SYNTHETIC_TEST_SERVER_UNRUN / NO_NEW_EPISODE / DEV1B_STILL_HOLD`。
