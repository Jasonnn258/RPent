# Stage F — Typed Routing 兼容规则(2026-09-20,F0 前 FROZEN)

消费对象:F0 四臂 benchmark(`scripts/memory_stageF0_benchmark.py`)。
本文在运行任何 F0 打分之前冻结;此后不改。

## 1. 地址侧(oracle,来自冻结的 Stage E 提取器输出)

每决策点地址 = `(origin, prereq, phase, action)`,全部取自
`analysis/stageE_origin_dump.jsonl`(134 点,已冻结):

| 字段 | 来源字段 | canonical 化(本体 §3) |
|---|---|---|
| origin | `origin` | 原样(PERCEPTION/GRASP/PLACE/NONE/UNKNOWN) |
| prereq | `missing` | VTL→PREREQ_1;OMWG→PREREQ_2;CSSTR→PREREQ_4;OBJECT_HELD*/空→∅(UNKNOWN) |
| phase | `phase` | 原样(P_grasp/P_transport/P_place/P_verify) |
| action | `action` | 原样(release/pi0_pick/pi0_doubled/move_to) |

地址 origin×prereq 实际联合分布(134 点):(GRASP,P2) 69、(PLACE,P4) 29、
(PERCEPTION,P1) 24、UNKNOWN/NONE 9、(GRASP,∅) 3。

## 2. 卡侧

`analysis/memory_activation_signatures_v1.json`(审计通过冻结,
`stageF_signature_audit.md`):每卡 `failure_origin[] /
missing_prerequisites[] / failure_surface[] / phase[] / action_family[]`,
**空 = 未指明(通配),不是排除**。

## 3. 四臂

| 臂 | 候选集 | 桶内排序 |
|---|---|---|
| A0_LEXICAL | 全库 61 卡(回归锚,逐位复现 C1/E0) | 冻结词面(raw overlap,>0 截断,同分 id 降序) |
| A1_ORIGIN | origin 兼容:`addr.origin ∈ c.failure_origin ∨ c.origin=∅` | 同上,仅在桶内 |
| A2_ORIGIN_PREREQ | A1 ∧ prereq 兼容:`addr.prereq ∈ c.prereqs ∨ c.prereqs=∅`(PREREQ_2↔3 视为同一) | 同上 |
| A3_TYPED_FULL | A2 ∧ phase 兼容(`addr.phase ∈ c.phase ∨ c.phase=∅`)∧ action 兼容(`addr.action ∈ c.action_family ∨ 空`) | 同上 |

降级规则:`addr.origin ∈ {NONE,UNKNOWN}` → A1≡A0;`addr.prereq=∅` →
A2≡A1;phase/action 无一兼容(A3)→ 回落 A2 桶(不因过约束空手)。
**NO_MATCH 语义**:桶内词面 >0 序为空 → 该臂返回 NO_MATCH(部署语义 =
不注入),计入指标,不回退全库。

## 4. 指标与门槛(预注册)

指标:per-arm × per-class R@1/R@3/R@5/MRR/irr@3、perception17 单列、
hardneg 14 单列;**路由指标**:gold routing recall(gold ∈ 路由后候选集)、
平均候选集大小、NO_MATCH 率(按 gold/hardneg 分列)。

| # | 门槛 | 判 |
|---|---|---|
| G0 | A0 逐位复现 C1 锚(R@1 .233/R@3 .575/R@5 .592/MRR .418) | 必须过,不过即停查实现 |
| G1 | A1/A2/A3 任一臂 perception R@3 ≥ 10/17 | 主门 |
| G2 | 该臂 overall R@3 ≥ A0 −3pp 且 non-perception 降幅 ≤3pp | 主门 |
| G3 | A2 或 A3 的 perception gold routing recall ≥ 15/17 | 寻址质量门 |
| G4 | hardneg irrelevant@3 相对 A0 恶化 ≤5pp | 安全门 |

判定树:G1∧G2 过 → 进 F1(automatic router);G1 挂但 G3 过 →
**TYPED ADDRESS UPPER BOUND INSUFFICIENT(IN_BUCKET_RANK_FAIL 归因)**
按协议 STOP;G3 挂 → signature 不足,同样 STOP。预注册机制预期
(signature audit §6):perception 桶内词面对 gold 全 0 分 → G1 预期挂、
G3 预期过,最终读数以实测为准。

## 5. 纪律

- benchmark 只读:sidecar、E dump、C1 queries、retrieval 冻结件;不写回。
- 无任何"看结果→改签名/改规则→重跑"循环;F0 跑完即出报告。
