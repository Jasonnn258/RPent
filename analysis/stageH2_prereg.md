# Stage H2 预注册 — 本地 edge router(离线门 + 在线 pilot)

_2026-09-28 起草。**状态:DRAFT — 生效条件 = H1 判定 REPRESENTATION SUPPORTED
(stageH1_prereg.md §7);H1 NOT SUPPORTED / PARTIALLY → 本文作废,Stage H 就地
STOP(§8 冻结规则不触发 H3)。** 起草时点声明:H1 90 集正在运行
(15:49 启动,尚未有任何 done 行),H2 的标签规则与门槛在看到任何 H1 在线
结果之前冻结 —— 早于常规时点,纪律只会更严。_

## 1. 研究问题与判定

**H2(本地策略层)**:图全冻结(§8 清单)下,Qwen3.5-4B 能否作为
graph-edge router 匹配远程 GLM teacher(glm-5.3-flash)的路由质量,同时把
决策点上的远程调用降 ≥70%?ceiling probe:Qwen3.5-9B。

判定:LOCAL ROUTER: SUPPORTED / CAPACITY-LIMITED / NOT SUPPORTED
(按 §6 门组合;离线门不过 → 不跑在线,如实报告即 STOP)。

架构立场(§0 审计已定):**local model 不当 planner**。router 是
graph_recall 内部的独立 OpenAI-client:输入 = task goal + active node +
evidence + 合法出边菜单,输出 = 选项字母 → edge_id;DEFER → 走 GLM teacher。
planner/Pi0.5/SAM3 全部不动。

## 2. 数据与图上下文(全部冻结)

- 数据:H0 基准 148 决策点(`analysis/stageH0_failure_states.jsonl`)。
  runtime_view 是 router 的唯一合法输入(observable_pre_state +
  recent_window + task_goal);`analysis_only.*` 由 loader 按字段名硬过滤,
  任何 prompt 不得读取。task_language 取自 source_path 的 states.json
  init 记录(planner 运行时可见,同词面)。
- 每点图上下文:冻结 interpreter(observable_pre_state + recent_window,
  与 §3 audit 同代码)→ active node → 冻结 retriever → 合法出边。
  §3 audit 已证 148/148 localization、0 零出边点、0 泄漏;H2 直接复用
  同一确定性计算,不重算不微调。
- 图 = graph v0(11 节点/25 边)逐字节冻结;ACTION_FAMILY_PRIMS 映射 =
  stageH1_prereg.md §5 冻结表。

## 3. 标签:recovery-consistent edge(冻结规则 + 冻结分布)

对每点,从 source episode 的 states.json 取该点后 **W=5 个 primitive
steps**(与 H1 §5 同窗口),用 H1 §5 冻结的家族物理证据规则判定:

- **validated**(窗口内该失败家族证据被清除):
  validating primitive p = 窗口中满足规则的那条原语(成抓/到位/doubled);
  若经 libero_terminated 清除,p = term 变 True 那步的原语。
  F(p) = {af : p ∈ ACTION_FAMILY_PRIMS[af]}(逆映射)。
  **correct_set = 该点合法出边中 action_family ∈ F(p) 的边**;
  - 非空 → **edge 标签**(correct_set,窗口物理证据指向这些边);
  - 空(**out-of-menu 恢复**:真实恢复动作不在该点合法边菜单内,如
    FG 点上任务径直 term 在 release 步 = 虚警自消)→ **DEFER 标签**
    (菜单无答案,正确本地行为 = 升级;子计数 out_of_menu 单列)。
- **not validated**(窗口内未清除):**DEFER 标签**(正确行为 = 升级)。
- 感知类边 FG-1/MS-1/CS-1 的原语不进 states.json,不会被窗口原语直接
  验证 —— 口径的已知性质,对所有臂一致,比较性门下无害。

**acc = 全 148 点正确决策率**(edge 标签点选 ∈ correct_set 记 hit;
DEFER 标签点选 DEFER 记 hit);附报:active-accuracy(仅 edge 标签点)、
各臂 DEFER 率、per-family / per-split 分解。"怂狗路由"(全 DEFER)的
离线 acc 上界 = DEFER 标签占比,由 §5 在线门(≥70% local)兜底,
不在离线侧加防。

**标签分布(2026-09-28 16:30 计算,先于任何 router 模型调用、先于
H1 任何 done 行,冻结)**:

| 类别 | n | 说明 |
|---|---|---|
| edge 标签 | 33 | correct_set 基数全部 = 1(FG-3×25、CS-2×3、CS-3×1、RS-2×4) |
| DEFER(not validated) | 83 | W=5 内失败未清除 |
| DEFER(out-of-menu) | 32 | 29 FG(term 于 release/move_to/set_gripper = 虚警自消)+ 3 CS(move_to 化解) |
| 合计 | 148 | 全 DEFER 基线 acc = 115/148 = 77.7% |

之后不得以任何理由改标签规则(改了 = 换实验,须重预注册)。

## 4. 离线 benchmark(§5,四臂)

| 臂 | 模型 | 菜单 | 上下文 |
|---|---|---|---|
| T | glm-5.3-flash(runtime API) | 该点合法出边 + DEFER | task + node + facts + 证据 |
| S4-G | Qwen3.5-4B(本地,sglm env 推理) | 同 T | 同 T |
| S4-NG | Qwen3.5-4B | **全图 25 边 + DEFER(固定 id 序)** | task + 证据,**无 node、无 facts、无合法性过滤** |
| S9-G | Qwen3.5-9B | 同 T | 同 T |

- S4-NG 的存在意义:隔离"图定位+合法性压缩"本身的贡献 —— 输出空间
  同为字母菜单,差别只在图是否告诉模型"你在哪个状态、哪些边合法"。
- prompt 模板(冻结;菜单行逐字复用 render_block 的边渲染词汇
  `[{id}] {action_family} / expected / falsify`,节点行用 render.py
  NODE_LABELS —— router 与 planner 看同一套冻结渲染):
  ```
  [EDGE-ROUTER] You route a robot to its next strategy.
  Task: {task_language}
  active state: {node} — {NODE_LABELS[node]}
  Observable pre-state: {observable_pre_state JSON}
  Edges (context, not an order):
  A. [{edge_id}] {action_family}
     expected: {expected_transition}
     if expected change absent: {falsify}
  B. …
  X. DEFER_TO_TEACHER — escalate this decision to the remote teacher.
  Answer with one letter only.
  ```
  S4-NG:无 active state 行;菜单 = 全图 25 边(graph.edges 原序)。
  违禁词纪律与 render 相同(banned substring 硬校验进 harness)。
- 解码(冻结):temperature 0,max_new_tokens 16,单次生成,
  **enable_thinking=False**(Qwen3.5 chat template 开关,空 think 块;
  2026-09-28 冒烟验证:不开则模型先吐长 CoT,16 token 内无字母)。
  无 few-shot、无样本外描述;原始输出截断 64 字符落盘(no long CoT)。
  T 臂(GLM)同一 template 与解码参数;GLM 非 thinking 模型,模板开关
  对其无效,如实记录。
- 解析(冻结):输出中**第一个** `A`-`Z` 字母或 `DEFER` 词;字母超界或
  无可解析 token = 非法选择(计入 legal_choice_rate 分母,accuracy 记 miss)。
- 指标:legal_choice_rate(选择 ∈ 菜单或 DEFER 的比例)、acc
  (§3 冻结定义 = 全 148 点正确决策率)、active-accuracy / DEFER 率 /
  per-family / per-split(discovery vs validation)附报、T 与 S4-G 的
  逐点选择一致率附报(诊断,不作门)。

### 离线门(全过才进 §6 在线)

1. legal_choice_rate(S4-G) ≥ 90%;
2. acc(S4-G) ≥ acc(T) − 5pp;
3. acc(S4-G) ≥ acc(S4-NG) + 8pp。

解读矩阵(预注册):S4-G 不过门而 S9-G 过 = **capacity bottleneck**
(→ 报告 CAPACITY-LIMITED,不自动换 9B 上线,如实记录);两者都不过 =
**表示问题不是模型问题**(→ LOCAL ROUTER NOT SUPPORTED,STOP,不训练
不调 prompt —— 那是 H3 的事,而 H3 不自动开启)。

## 5. 在线 pilot(§6,仅离线门全过后)

- 臂:h2T(teacher 路由:fire 时调 glm-5.3-flash 选边)vs
  h2L(local 路由:fire 时 Qwen3.5-4B 选边,DEFER → teacher)。
  每 fire 注入 render_block(active node, [chosen edge])(单边版渲染,
  模板冻结);h2T 中 teacher 也选 DEFER → 回落注入全部合法边
  (= H1-GRAPH 行为,冻结 fallback)。
- 调度:ovpm_exp.py 新 stage `h2`,H1 的 30 冻结格 × 2 臂 = 60 集
  (fire 覆盖已被 H1 证实);tier glm-5.3-flash;并发 cap 8;
  除路由器外全部 env 与 h1G 逐字节一致(§8 清单)。
- 服务:Qwen3.5-4B 由 sglm env 的 vLLM 起 OpenAI-compatible server
  (单卡,权重不进 repo;server 只在实验期间存在)。
- 指标:SR、VR(H1 §5 同口径)、fire 级路由来源占比(local/teacher/
  fallback)、远程调用数(planner 调用 + 路由调用分开计)。

### 在线门(全过 = LOCAL ROUTER SUPPORTED)

1. |SR(h2L) − SR(h2T)| ≤ 5pp 且 |VR(h2L) − VR(h2T)| ≤ 5pp;
2. h2L 的 fire 决策 ≥70% 由 local 完成(DEFER 率 ≤30%);
3. h2L 相对 h2T 的远程调用降幅 ≥70%(路由调用面;planner 调用两臂
   同栈,如实在附报中给出总量对比)。

任一不过 → 如实判定并 STOP;不改 prompt、不改图、不改 router 温度
重跑(无"看完结果再调"循环,与 H1 §10 同纪律)。

## 6. 运行纪律(与 H1 §9 同)

- H2 全部离线模型调用在 H1 90 集完成之后进行(不与在线 run 抢 API
  配额与 GPU;429 签名按事故账流程);
- T 臂 148 次调用走 runtime 同一 endpoint/tier,一次跑完落盘;
  失败 ≤3 次重试,超过 = infra 事故账;
- 本地推理在 sglm env(vla env 不装任何新包 —— 冻结栈零风险);
  模型权重已在 /workspace/yjx/models/Qwen3.5-4B(SHA 于结果文件记录);
- dev_preflight 先行;日志落 repo 与持久卷;不碰他人进程。

## 7. 冻结清单(H2 全程不动)

graph v0 全部、interpreter/retriever/render、H1 §5 全部指标定义与
ACTION_FAMILY_PRIMS、标签规则 §3、prompt 模板 §4、解码与解析参数、
Planner/Pi0.5/SAM3/primitives/turn budget 40/B2 verifier/SM1、
61 卡与 MEMORY.md、Q0_FIXED、OVP-M 关闭态。两臂在线差异仅 §5 表中
路由来源;离线四臂差异仅 §4 表中模型与菜单。

## 8. STOP 边界

- H1 判定非 SUPPORTED → 本预注册作废,不跑任何 H2 步骤;
- 标签分布打印后任何规则改动 → 实验作废重预注册;
- 在线过程发现 router prompt 混入 analysis_only / GT / 未来字段 →
  立即停,按泄露事故处理;
- 任一门 FAIL → STOP;不调参不补跑;9B 仅作 ceiling probe,失败结论
  同样如实报告。
