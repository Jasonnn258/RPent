# Stage I0 预注册 — Local Model Qualification(spec §1,冻结)

_2026-09-29 起草并 commit,**先于任何 I0 模型调用**。I0 不运行机器人环境。_

## 1. 研究问题与判定

哪一个本地模型(Qwen3.5-4B / Qwen3.5-9B)有资格承担 RPent 的
高频 decision / routing?判定输出 `PRIMARY_LOCAL_MODEL =
Qwen3.5-4B / Qwen3.5-9B / NONE`(§1.4 门,全部预注册)。
远程 GLM 不参评(H2 已作废,不存在历史 GLM router decisions 可引;
不新增任何 API 调用)。

## 2. 数据(冻结)

- 底料 `analysis/stageH_transition_dataset.jsonl`(sha256
  **44cd2e87**;2026-09-29 修复 h0↔H2 标签 join 的 evidence_id
  塌缩 bug 后重建,h0 标签分布已回到 H2 冻结值 EDGE 33 / DEFER 115)。
- 基准 `analysis/stageI0_router_benchmark.jsonl`,**252 样本,
  sha256 9b153e22**,由 `scripts/build_stageI0_benchmark.py` 确定性生成。
- CLEAR/AMBIGUOUS 规则(先于任何模型调用冻结):
  h0:label=EDGE → CLEAR(correct_set[0],基数全 1);label=DEFER →
  AMBIGUOUS。h1:validated_w5 且 validating_prim 逆映射(ACTION_
  FAMILY_PRIMS,H1 §5 冻结表)恰好命中 1 条合法边 → CLEAR;
  命中 >1(multi_match)或 0(out_of_menu)或 not validated →
  AMBIGUOUS。**实测分布:CLEAR 62(h0 33 + h1 29)/ AMBIGUOUS 190;
  CLEAR 按家族 FG 44 / MCS 6 / RPS 12(三家族全覆盖)。**
- 禁止(已内建):终局 success 反推标签;未验证点强行造 label;
  runtime_input 与 analysis_only 物理分离(sample 内嵌套结构)。

## 3. Router 任务与 prompt(冻结)

- prompt 模板 = build_stageI0_benchmark._prompt 逐字节(TASK /
  CURRENT STATE + family / Observable evidence / Recent transitions /
  Legal recovery options(冻结图边:action_family + expected +
  falsify,render 同源词汇)/ DEFER_TO_PLANNER / JSON 输出指令)。
- **违禁词纪律**:prompt 禁含 fail/error/could not/no object 子串
  (构建器硬 assert;曾逮住模板自身 "CURRENT FAILURE:" 头,已改
  "CURRENT STATE: + family:",信息等价)。理由:router 输出摘要
  会回灌 planner 对话,stv/B2 红线优先于示例措辞。
- 菜单字母 = 合法边原序 A.. + DEFER 末位;同一样本两模型逐字节同 prompt。

## 4. 解码与解析(冻结)

- vLLM OpenAI-compatible server(sglm env),chat template 服务端固化
  enable_thinking=False;temperature 0;max_tokens 32;单次生成;
  无 few-shot。
- 解析:取输出中第一个 `{...}` JSON 块的 `choice` 字段(字母);
  无 JSON 块则回退首个 A-Z 字母;字母 ∈ 菜单范围或 = DEFER 位 →
  合法;超界 / 无可解析 token → ILLEGAL(进 illegal_output_rate,
  accuracy 记 miss)。原始输出截断 64 字符落盘,不留 CoT。

## 5. 指标(冻结;overall + 三家族 breakdown)

legal_choice_rate;clear_state_accuracy(分母 = CLEAR 62);
family_accuracy(CLEAR 内按家族);DEFER_rate;DEFER_on_ambiguous_rate;
illegal_output_rate;latency_p50/p95;tokens_per_decision;
throughput(qps);GPU_memory(峰值)。附:T-S9 一致率(诊断,不作门)。

## 6. 资格门(spec §1.4 逐条,预注册)

1. **4B 直接当选** iff:legal_choice_rate(4B) ≥ 98% 且
   clear_state_accuracy(4B) ≥ 90% 且 clear_acc(4B) ≥
   clear_acc(9B) − 5pp 且 三家族中 ≥2/3 的 family_acc(4B) ≥
   family_acc(9B) − 5pp。
2. 否则若 legal_choice_rate(9B) ≥ 98% 且 clear_acc(9B) ≥ 90%
   → **PRIMARY = 9B**。
3. 9B 也不满足 → **I0 FAIL**:不跑 online;诊断 state representation
   / edge semantics / prompt ambiguity / label quality;不下载更大模型。
4. 35B-A3B:仅当 9B 接近门而未过、且失败疑似 capacity bottleneck 时,
   允许**小规模** offline upper-bound 测试(不做完整 campaign)。

## 7. 运行纪律

- 基准与预注册先 commit,后起服务、后跑模型(本文档所属 commit 即时序证据);
- 两模型同一 server 配置(除权重),逐样本同序;
- 权重不进 repo(/workspace/yjx/models);日志落 repo/持久卷;
- dev_preflight 先行;sglm env 零安装,vla env 不动;
- latency/吞吐在空载 GPU 上测,记录 batch=1 串行口径。

## 8. STOP 边界

- I0 FAIL → 不做任何 I1 步骤,输出诊断报告后停;
- 门过 → 只宣布 PRIMARY_LOCAL_MODEL 并进 §2 基建;
- 任何样本/prompt/解析规则改动 = 换实验,须重预注册。
