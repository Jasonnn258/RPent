# Stage I0 结果 — Local Model Qualification(冻结口径)

_2026-09-29。预注册 `stageI0_prereg.md`(commit 2963343)**先于**全部模型调用;
基准 sha256 9b153e22 硬校验通过。判定:**I0 FAIL,PRIMARY_LOCAL_MODEL = NONE**。_

## 1. 运行配置(两模型完全一致)

| 项 | 值 |
|---|---|
| server | vLLM 0.1.1.dev(sglm env),单卡 GPU7,bf16,max_model_len 32768,util 0.90 |
| 模板 | chat_template_nothink.jinja(服务端固化 enable_thinking=False,diff 仅 1 行) |
| 解码 | temperature 0,max_tokens 32,单请求串行 batch=1 |
| 冒烟 | 四项 S1-S4 双模型各 4/4 PASS(health/simple/structured/最长 prompt 985 chars) |
| 基准 | 252 样本逐字节同 prompt,逐样本单请求 |

## 2. 冻结口径主结果(prereg §4)

| 指标 | Qwen3.5-4B | Qwen3.5-9B | 门 |
|---|---|---|---|
| legal_choice_rate | **100.0** | **100.0** | ≥98% ✓ |
| clear_state_accuracy | **1.61** (1/62) | **11.29** (7/62) | ≥90% ✗✗ |
| family acc FG / MCS / RPS | 0.0 / 16.7 / 0.0 | 4.5 / 83.3 / 0.0 | — |
| DEFER_rate | 0.0 | 0.0 | — |
| illegal_output_rate | 0.0 | 0.0 | — |
| latency p50 / p95 (s) | 0.051 / 0.059 | 0.069 / 0.069 | 记录 |
| tokens/decision | 7.0 | 7.0 | 记录 |
| throughput (qps) | 17.6 | 13.3 | 记录 |
| GPU 峰值 (MB) | 72,273 | 71,955 | 记录 |

逐文件:`stageI0_metrics_qwen4b.json` / `_qwen9b.json`;逐样本
`stageI0_run_qwen4b.jsonl` / `_qwen9b.jsonl`(raw 截 64 字符,无 CoT)。

## 3. 资格门判定(prereg §6 逐条)

- **门 1(4B 直接当选)**:clear_acc 1.61 < 90 → **不满足**。
- **门 2(9B 兜底)**:clear_acc 11.29 < 90 → **不满足**。
- **门 3(I0 FAIL)**:触发。不跑 online;进入诊断;不下载更大模型。
- **门 4(35B 条件上限)**:不适用 —— 条件是"9B 接近门而未过",11.29%
  距 90% 门 78.7pp,非 capacity 边缘问题(且 35B 同为 thinking 家族,
  冻结解码下只会同样塌缩)。

## 4. 诊断(prereg §6.3 四选一归因)

### 4.1 直接原因:thinking 家族 × nothink+32token 解码契约 → 位置塌缩

- 4B 选择分布:**A 231 / C 20 / B 1**;9B:**A 227 / B 25**。3 选项
  菜单上 A 占比 4B 192/193、9B 189/193 —— 两模型在冻结解码下都是
  "选第一项"的位置机器人,证据字段(float 们)未进入决策。
- legal 100% + 平均 7 token 恰好一格 JSON:输出格式完全合规、内容
  完全退化。这是 Qwen3.5(thinking 模型)关掉思考后的已知形态,
  不是服务/模板故障(冒烟 4/4、原生模板 diff 仅 1 行条件)。

### 4.2 结构性混杂:基准的"正确答案"是家族级常量,prompt 内无决策规则

- CLEAR 62 的参考边分布:FG 家族 44/44 全是 FG-3(grasp_offset);
  RPS 10×RS-2 + 2×RS-3;MCS 5×CS-2 + 1×CS-3。
- **"恒选 B"位置基线 = 59/62 = 95.2%**;家族常量查表 = (44+10+5)/62
  = 95.2%。菜单构成全数据集仅 4 种(FG-1/FG-3、RS-1/2/3、CS-1/2/3、
  MS-1/2/3),且**参考字母从不是 A**(2 边菜单 44/44 是 B)。
- 冻结 prompt 给了证据数值与边语义,但**没有任何"证据→选边"的决策
  规则**(例:peak_lift=0 该选感知还是偏移重抓?prompt 内无答案)。
  参考答案由历史验证轨迹的家族级惯例决定,单发无示例模型原则上
  只能靠机器人学先验猜中。→ clear_acc<90% 不能读作纯能力结论,
  同时是 **prompt 不可判定(ambiguity)问题**。
- 标签质量(四选一里的"label quality"):无嫌疑 —— H2 冻结标签、
  家族内自洽、可复现。

### 4.3 容量存在但代价不可用:think-on 9B 诊断(30 样本子集,非资格口径)

| 项 | 值(tag qwen9b_think_diag,原生 thinking 模板,max_tokens 4096) |
|---|---|
| 截断率 | **24/30 = 80%**(4096 打满仍未收尾;mean 3926 tok/decision) |
| 合法收尾 | 6/30;其中唯一收尾 CLEAR(i0-002)**答对 B**,推理真实读了数值("peak lift already >= 5mm… A (Perceive) is more expensive. So B is preferred.") |
| DEFER(收尾 AMBIGUOUS 5 条) | 0/5 |
| latency p50 | **28.6 s/decision**(143 tok/s 生成) |
| 收尾需要的预算 | 单探针 3541 token;多数 >4096 → 需 ≥8K 预算 ≈ 60s+/decision |

结论:9B 在原生思考模式下有读证据、比代价、选中参考边的能力,但
单决策 4K-8K token / 30-60s,与在线 router 契约(episode 中段 fire,
H1 每臂 30+ 次 fire)不兼容 —— 相当于每集额外 +15-30 分钟纯 router
时延。**容量在,契约不容纳。**

### 4.4 归因裁定(spec 要求区分的三类)

| 假设 | 裁定 | 证据 |
|---|---|---|
| MODEL CAPACITY(冻结契约下) | **成立(直接)** | §4.1 位置塌缩;nothink 32token 内无任何 Qwen3.5 规模能做证据路由 |
| STATE REPRESENTATION / PROMPT AMBIGUITY | **同时成立(结构性)** | §4.2 参考为家族常量+无决策规则+位置混杂,95.2% 可由查表拿到 |
| AUTHORITY DESIGN | 未及检验 | I0 不跑 online;该假设在 I1,已被 FAIL 阻断 |

## 5. 事故与修复账(基建,不影响判定)

1. **proxy 劫持 127.0.0.1**:本机 http_proxy 环境把 localhost 请求送进
   代理 → 503,健康检查假超时、openai client 同样中招。修复:curl
   --noproxy + 客户端注入 NO_PROXY(commit 2c9f2c7)。
2. **后台任务连坐**:外层 shell 任务被停时 nohup 子进程被进程组杀。
   修复:vllm `setsid` 脱离进程组 + pidfile pgrep 兜底。
3. runner 首跑 `is_def` 变量名 NameError(未写盘任何结果即崩,重跑
   无双计);family 短码映射(FG/MCS/RPS)首版用长名致 breakdown
   全 null,已修并离线重算(逐样本结果不变,温度 0 确定性)。

## 6. 结论

- **资格门:I0 FAIL。PRIMARY_LOCAL_MODEL = NONE(见 stageI0_decision.md)。**
- I1(Verified Recovery Authority)按预注册 §8 与 spec §1("only if
  I0 PASS")**不启动**:本地 planner/router 通道不存在合格模型。
- 附带产出:本地 vLLM 服务链路(启动/停止/四项冒烟/基准 runner)
  已验证可用 —— 4B/9B 均能稳定服务 OpenAI-compatible 请求
  (0.05-0.07s 单请求、72G 显存、thinking 可服务端固化),基建本身
  不构成 Stage I 阻塞;阻塞 purely 在资格门。
