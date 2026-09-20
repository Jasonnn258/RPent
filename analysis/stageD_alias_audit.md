# Stage D Alias Audit(2026-09-20,benchmark 前置门)

对象:`analysis/retrieval_aliases_v1.json`(由 `scripts/build_retrieval_aliases.py`
生成,468 条 alias,61/61 卡覆盖)。本报告是 D1 离线 benchmark 的前置门:audit
通过 → sidecar 冻结 → benchmark 只读。

## 1. 生成策略与防火墙(过程声明)

- **三层确定性收割,无人工短语语法**:
  - **R1 symptom**(292 条,62.4%):卡 frontmatter 的 symptom bullet 逐字
    取用(≤6 条/卡)。symptom 本来就是作者写下的 observable 现象短语,
    但线上词面索引只用 MEMORY.md 行+文件名,**symptom 从未进过检索 token 集**
    ——这是 V1 最大的结构性修正;
  - **R3a task_only 字段收割**(167 条,35.7%):对每卡 evidence.cells 对应的
    `task_only/{cell}.json`,按固定字段优先级(pick_result→localization→
    failure_history→perception*→contact_result→final_state.note→notes→
    strategy_notes)取 verbatim 短语;≤90 字符整取,长文本按冻结 marker 词表
    句滤(词表全部是通用机器人运行时词汇,15 类,写在脚本里);
  - **R5 recipe prompt**(9 条,1.9%):仅 perception kind 卡,取
    `{cell}_recipe.jsonl` 里实际发出的 segment/back_project prompt
    (`segmentation prompt: …`,≤2 条/卡)。
- 每条 alias 归一为 ≤12 token 短语,带 `{source_cell, source_field,
  source_excerpt}` 三重溯源;token 子集去重;上限 8 条/卡;数字残渣卫生
  规则(必须含 ≥3 字母词)。
- **防火墙**:提取器代码只打开 `resources/libero/{global,task_only}` 下文件,
  不 import 不读取任何 Stage A/C1/C3 查询/失败工件(代码结构强制)。本 audit
  是流水线中第一个、也是唯一一个读测试集的环节(泄露检查是其职责)。
  生成期间的迭代(缩进解析 bug、R5 槽位预留、卫生规则)全部发生在读任何
  测试数据**之前**,且均与测试内容无关。

## 2. 覆盖与分布

| 量 | 值 |
|---|---|
| 卡总数 / 有 alias 的卡 | 61 / 61(0 空) |
| alias 总数 | 468 |
| 每卡条数 min/mean/max | 5 / 7.67 / 8 |
| alias token 长度 min/mean/max | 1 / 5.41 / 12 |
| 层分布 | R1 292 / R3a 167 / R5 9 |
| 来源字段分布 | symptom 292 / pick_result 74 / strategy_notes 46 / localization 41 / recipe 9 / final_state 3 / perception 2 / contact_result 1 |
| 按 Stage A 类族(卡数 / alias 数) | recovery 23/174、predicate_timing 18/138、grasp 9/71、perception 7/53、pick_verify 4/32(注:类族按卡 id 归属报告;perception 类族 7 张指 Stage A gold MAP 的核心 perception 卡,kind:perception 共 13 张) |
| 61 卡 evidence.cells 引用的 49 个 cell | 全部有本地 task_only JSON + recipe(0 缺失) |

## 3. 跨卡碰撞预检

alias 中出现于 ≥8 张卡的 token(前列):gripper 34、pick 30、object 28、
false 25、release 24、pi0 23、wrist 22、rim 22、held 20、basket 19、
target/grasp/opening 17、bowl 16、plate 15、prompt 14……

判读:这正是"机器人运行时通用词汇"——它们同时存在于在线 query 的状态字段
里,是 Stage D 想建立的词汇通道;代价是跨卡区分度下降。这些 token 对所有卡
近似均匀加分,真正破坏排序的是"少数卡共享的非 gold 泛化 alias",由 D1 的
alias collision rate、hardneg irrelevant@3 与 non-perception 降幅三个门槛
量化兜底,audit 不预先剔除(剔除即引入第二次人工自由度)。

## 4. 泄露检查(关键节)

方法:每条 alias 的连续 3-gram 与 134 条 C1 冻结 query 全文(三臂拼接+task
language)比对。**28 行命中,去重后 17 条唯一 alias(占 468 的 3.6%)**。
逐类裁决:

| 类别 | 条数(唯一 alias) | 例 | 裁决 |
|---|---|---|---|
| 任务语言引用 | 10 | `pick the akita black bowl on the ramekin and place it on`(verify-duplicate-semantics,源=task_only 记录的该 episode 任务指令) | **非泄露**。alias 引用的是卡自己 evidence 里记录的任务指令原文;query 侧含同一 task_language 是在线查询的固有构成。任务名词通道对 gold/非 gold 卡对称开放,碰撞由门槛管 |
| 状态字段短语 | 4 | `min gripper opening 0.063 can`(pick_result 原文)、`libero terminated false`、`gripper opening 0.078` | **非泄露,且是核心机制**——query 的 result fields 终于在卡侧有了对应词 |
| 感知拒斥记录 | 2 | `text prompt the patterned black bowl at the table center selected the…`(rejected_segment_prompts 原文) | **非泄露**。这是 perception 卡最想要的 observable 签名(文本提示选错实例) |
| symptom 现象短语 | 1 | `release did not terminate` | 非泄露(卡自有 symptom) |

**无一条是配对定制**:所有命中的 3-gram 都同时出现在 ≥3 条跨类别的测试
query 中(最多 x134),没有任何 alias 只与某一条测试点独占重叠。过程性
结论:alias 内容 100% 可溯源到卡自有字段,不存在"看测试补词"通道。

## 5. 冻结声明

- `analysis/retrieval_aliases_v1.json` 自本报告起**冻结**:D1 benchmark 及
  之后一切阶段只读;禁止根据任何测试命中情况回改。
- 提取脚本 `scripts/build_retrieval_aliases.py` 同步冻结(重跑应逐字节再生
  sidecar,策略常量已写入 sidecar `policy` 节)。
- audit 结论:**通过**,无泄露需修数据;碰撞风险移交 D1 门槛量化。

## 6. 已知限制(如实)

- 468 条中 R1 占 62%——sidecar 的主体其实是"symptom 终于进索引";
  R3a/R5 是少数派。若 D2 成立,主贡献预计来自 R1;层的单独消融未预注册,
  机制日志按 alias 逐条记录来源层,事后可拆。
- 1-token alias 31 条(basket/rim/caddy 等名词)区分度弱,保留(它们是
  symptom 原文的一部分,剔除即编辑)。
- alias 长度效应(卡侧 token 变多)由 D_SHAM 置换对照隔离,不在本 audit
  处理。
