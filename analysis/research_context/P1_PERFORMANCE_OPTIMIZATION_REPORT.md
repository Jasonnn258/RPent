# P1 性能优化轮报告(2026-10-10)

**目标**:在不改变 RPent 冻结物理行为、科研结论与实验设置的前提下,系统性
减少未来 Embodied Harness 实验的运行成本,并交付可复用的工程改进。

**执行边界遵守情况**:零新物理仿真 Episode(D-041 8/8 已结清不补跑)、
零新付费 Planner API 调用、零训练、零冻结数据/协议改动、未干扰他人 GPU
进程;全部新测量 = 既有日志离线解析 + FunctionModel/MockHTTP/合成子进程
的离线基准。

---

## 一、实测瓶颈(区分三类证据)

### 1.1 新测量(本轮产出,可复现)

| 项 | 数值 | 来源 |
|---|---|---|
| 模型请求墙钟(客户端观测) | **276 请求 / 4040.0s,占 8 集总墙钟 75.0%** | `p1_perf_planner_requests.py` 从 DEV1A run.log 秒级时间戳重建,口径 = ApiLatencyProbe(model-node wall) |
| 每请求 wall 分布 | p50=8s / p90=33s / p95=56s / max=141s | 同上,首轮锚点噪声单独留档 |
| 客户端份额(图推进+请求构造+ProcessHistory) | **~1.1-1.3 ms/请求,平坦** | `p1_perf_client_overhead.py`(FunctionModel sleep=0 上界法) |
| 隐藏重试 | 0(requests delta>1 的轮次 = 0) | run.log [usage] delta 审计 |
| Prompt cache 真实命中 | request-2 输入 14499 中 cache_read=14336(**98.9%**) | run.log;GLM openai 兼容端点真回报 cached_tokens |
| kill 宽限实际消耗 | grace=2s→kill wall 2.0s;grace=6s→6.0s(3 个 SIGTERM 忽略 daemon,SIGKILL 升级即时生效) | `p1_perf_benchmark.py` kill_grace |

**核心结论**:上一轮"Planner API ≈76.1%"的残差估计,现已逐请求坐实为
**模型请求墙钟 75.0%**(4040s/5385.6s)。该墙钟含网络+服务端排队+生成+
客户端开销;其中客户端开销被独立测出 ≤1.3ms/请求(占比 ~0.016%),
**即 ≥99.98% 的请求墙钟在网络与服务端**。Planner 侧客户端软件优化空间
≈0(B4 排除),收益杠杆全部在:①减少请求数(研究问题,见 §四);
②减少每请求等待(服务端/协议层,超出本轮可动范围)。

### 1.2 历史估计(沿承上轮,本轮未重测)

- init 13.5%(729s,其中 Pi0.5 重复加载 63.8-69.8s/集 ≈ 9.8%);
- 工具执行 6.8%(内含渲染 <1%);teardown 3.5%(6 个被终止集 × ~30s
  SIGTERM 宽限全额消耗)。

### 1.3 未验证推断 / 不可测项

- **稳态 prompt-cache 命中率 UNMEASURABLE_FROM_EXISTING_LOGS**:历史
  [usage] 从每集第 2 个请求起冻结(见 §二.1),只有 request-1/2 可信;
- TTFT / 服务端排队 / 生成各占多少:客户端不可分,需服务端指标;
- 逐请求 token 分布(第 3 个请求起):同上冻结,不可恢复。

---

## 二、实际优化(改动文件 + 前后结果 + 收益/副作用)

### 2.1 [计账 bug 修复] api_loop [usage]/stats 冻结(生产级,影响所有历史 api-planner 运行)

- **现象**:DEV1A 8/8 集 run.log 的 `[usage]` 行从第 2 个请求起逐字冻结
  (in=28849 out=159 requests=2 持续 33+ 轮),而轮次/工具一直在推进。
- **根因**:`_ApiRunObserver.observe_response` 把 `run.usage`(图状态里
  的**活对象引用**)存为基线;库原地递增该对象 → 下一轮
  `delta(自己,自己)≡0` → 累计从第 2 个观测点起冻结。修复 = `copy.copy`
  快照(rpent/planner/api_loop.py)。
- **影响面**:所有走该路径的历史运行的 token/request 统计(日志行、
  PlannerResult.stats、CLI 末尾打印)都止于前 2 个请求;
  `scripts/ovpm_exp.py` 调度指标读 structured_metrics.json,**不受影响**;
  物理行为/轨迹/成功判据零影响(纯遥测)。修复后回归锚:requests ==
  脚本请求数、tokens == 逐请求和(tests/test_api_usage_accounting.py 3/3)。
- **勘误**:任何引用历史 api-planner token 总量的报告段落应视为
  低估;墙钟与工具计数不受影响。

### 2.2 [致命 bug 修复] --persistent-vla 从未能启动

- `cli.healthz(...)` 在 HttpRpcClient 上不存在(AttributeError),被
  `except Exception` 吞成"恒未就绪" → 启动必然 240s 超时 FATAL。
  该 opt-in 特性(上轮交付)从未真实可用;修正为 `call("healthz")`。
  mock HTTP server 回归测试锁定(tests/test_p1_runner_lifecycle.py)。

### 2.3 [B2] 常驻 vla_server 集间探活守卫

- server 中途死亡后,旧逻辑会继续启动注定失败的集、白烧整集
  worst_wall(最坏 2400s/集);现集边界 healthz 探活,死亡即
  `stop(persistent_vla_dead)` 止损,finally 回收不变。

### 2.4 [B3] 子进程崩溃孤儿清扫

- 旧逻辑 `proc.poll()≠None` 一律按 natural_exit 跳过 killpg;子进程
  rc≠0 崩溃时组内孤儿 daemon(vla/env/sam3)泄漏,持续占 GPU/内存。
  现 `_sweep_if_crashed`:rc≠0 → killpg(5s 宽限);rc=0 零影响。
  对抗测试:SIGTERM 忽略孤儿被 SIGKILL 清扫、干净退出不清扫。

### 2.5 [B1] ApiLatencyProbe 补齐 dashboard 路径

- `_solve_dashboard`/`_ApiDashboardSession` 接入与终端路径同款的
  旁路遥测;文本收尾响应同样流经 CallToolsNode,每请求恰一条记录。

### 2.6 [B4] Planner 客户端软件开销:排除(负结果交付)

- 上界法测量(FunctionModel sleep=0):轮次 4→48、每轮图片 0→1MB、
  thinking 0→4KB、工具结果文本 0→64KB/轮(≈1MB 累积历史)全部
  ~1.06-1.3ms/请求,无随历史增长趋势 → 无无效序列化/重复构造级问题,
  **不值得优化**。

### 2.7 分析工具修正

- `p1_perf_breakdown.py` planner_usage 原实现把逐行累计快照求和
  (双重口径错误),改取末行累计 + 冻结告警;
- `p1_perf_planner_requests.py` 新增冻结检测(8/8 集 frozen_from=2),
  token 分布只保留可用窗口并标注 UNMEASURABLE。

---

## 三、成本模型(每有效验证样本)

DEV1A 8 集(既有,不重跑):总墙钟 5385.6s,GPU 账本 5190 gpu_s,
env 步 1678,证据集(6 触发集全部取得 t_lift_end 证据)。

| 成本项 | 现状 | 常驻+短宽限启用后(估计) |
|---|---|---|
| 每集墙钟 | 673s(p50 同量级) | ~608s(−65s Pi0.5 加载,**估计值,未整批复测**) |
| 其中模型请求 | ~505s/集(75%) | 不变(协议层冻结) |
| 每被终止集 teardown | ~31s | ~6s(P1_KILL_GRACE_S=5;基准实测 grace 即 wall,见 benchmark.json) |
| 每集 GPU 账面 | 649 gpu_s | 同口径不变;**常驻服务集间空闲权重不计入,DEV1B manifest 必须预注册新口径** |

**每有效验证样本综合成本**(6 个触发集口径):墙钟 5385.6/6 ≈ 898s/样本;
若启用常驻+短宽限:约 (5385.6−8×65−6×25)/6 ≈ 756s/样本(**估计**,
−16%)。真实环境物理步与证据时点密度不变(未动)。

---

## 四、下一阶段研究方向(只选最有价值的 1-2 个)

**唯一首选:减少 Planner 无效请求(研究问题,独立实验候选,不接入 DEV1A/DEV1B 冻结路径)。**
依据:p50=8s/p95=56s 的 276 请求是成本主体;若能把每集 34.5 个请求的
分布尾部(p90 后 33-141s 的长请求)或重复感知类请求压缩 20-30%,
收益直接落在 75% 的大头,超过其余全部工程杠杆之和。候选机制(全部
需要新 cohort 预注册):感知去重阈值化(P1 既有 perception-guard 的
研究化扩展)、长尾请求的预算内重试/降档、COMMIT/REASON 分流的
请求预算再分配。

次选(工程,DEV1B 即可直接用):常驻 Pi0.5 + P1_KILL_GRACE_S=5 组合,
预注册 GPU 口径修正后整批对照。

---

## 五、验证与资产清单

- 测试:本轮新增 9 个(test_api_usage_accounting 3 + test_api_dashboard_probe 1
  + test_p1_runner_lifecycle 5)全过;目标批 15/15;runner --selftest
  PASS;--dry-run manifest sha b57ce6c9 与 D-041 封版一致。
- 基准:`artifacts/p1_perf/{planner_requests,breakdown,client_overhead,
  benchmark}.json`(私有,不提交)。
- 代码:rpent/planner/api_loop.py、scripts/p1_dev1a_run.py、
  scripts/p1_perf_*.py、tests/*(见 git log)。

## 六、GO-HOLD-STOP

**GO(工程交付)/ HOLD(新物理实验)**:全部交付为默认关/opt-in,冻结
路径零变化;DEV1B 仍 HOLD 待人工授权,启用常驻模式前必须先预注册
GPU·hour 全生命周期核算口径(§三)。
