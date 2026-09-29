# Stage H 最终报告 — Frozen Embodied State-Transition Graph + Local Policy Router

_2026-09-29 收口。全弧:§0 现有系统审计 → §1 H0 失败状态基准(148 决策点)
→ §2 graph v0(11 节点/25 边)→ §3 离线审计门 → §4 H1 三臂在线实验 →
(§5/6 H2 按 §8 作废)→ §7 transition dataset → 本报告。_

## 判定(全部按预注册冻结门,无事后调整)

**H1(REPRESENTATION):NOT SUPPORTED → Stage H 就地 STOP。**
**H2(LOCAL ROUTER):预注册生效条件未满足,自动作废,零模型调用。**

## H1 结果(analysis/stageH1_results.md,90/90 集全落地,infra 缺失 0)

| 指标 | P2(泛型) | CARD(扁平卡) | GRAPH(冻结图) |
|---|---|---|---|
| SR | **25/30 (83.3%)** | 20/30 (66.7%) | 23/30 (76.7%) |
| validated_recovery | 15/20 (75.0%) | 7/17 (41.2%) | 13/18 (72.2%) |
| wrong_phase | 38/38 (100%) | 0/34 | 0/32 |
| guard_violation | — | — | **27/30 (90.0%)** |

门:M1 PASS(双方都触底 0%,零区分度,空过);**M2 FAIL**(90% ≫ 2%);
行为门 A/B 双 FAIL(GRAPH 全面低于 P2);家族门 1/3(仅 FALSE_GRASP 过)。
VR 面降级 INCONCLUSIVE(CARD 17 / GRAPH 18 个有 fire 集 < 20)。

## 机制解读(报告性,不改判定)

1. **建议通道压不过 planner 默认策略 —— M2 是最硬的证据。** FALSE_GRASP
   fire 后,planner 下一条动作几乎全是 `move_to`(惯常撤退-再接近)或
   `set_gripper`,而图菜单在该节点只提供"重新感知/偏移抓取"两类;
   90% 的下一步在菜单外。图块被读了,但不约束行为。这与 B2 的
   "裁决不驱动行为"、G0.5/G0.6 的全线零效应同构 —— 本 stage 把该结论
   从"注入文本无用"细化到"动作级 guard 90% 不被遵守"。
2. **泛型对照组最强(83.3%),CARD 有害(66.7%)。** P2 ≈ G0.5 无干预
   基线水平(0.867),说明三臂中任何"内容注入"都没带来 SR 收益;
   扁平卡是唯一显著掉分的臂。GRAPH 居中:图不救也不害,但作为
   **advisor** 无行为杠杆。
3. **CARD 的 VR 崩(41.2%)与 SR 掉分方向一致**,false-grasp 家族尤甚
   (53.8% vs P2 73.3%):冻结 61 卡的词面建议在该家族系统性误导。
4. **触发基建成立**:三臂 fire 率一致(38/34/32,均 ~1.2/集),说明
   2026-09-28 envelope 修复后的 graph 触发器在线上稳定工作 ——
   失败的不是触发,是注入内容的作用通道。

## 口径事故与如实记录(不改变判定)

- **事件↔重放不一致 13/90 集**(从 fire 类指标剔除,SR 保留):根因是
  冷却按 boundary 计数,runtime 每个 planner turn(含感知 turn)都推进,
  重放只数动作步 → 重放 fire ≤ runtime。已知口径,prereg 冻结处理。
- **infra 事故账**:139 次 episode 运行落地 90 格(49 次 infra_timeout
  ≈ 35%,全部 3600s API 预算超时,≤3 重试纪律内消化;1 次 worker
  连续 3 infra 触发 600s 暂停后自愈)。墙钟 15:49→06:20(14.5h)。
  无 429 配额事件。

## H2 作废说明(stageH2_prereg.md §8 自动生效)

H1 判定非 SUPPORTED → H2 预注册作废。**未做任何 H2 模型调用**:
glm teacher 臂未跑、Qwen3.5 未做任何推理调用、9B 未下载。归档件:
stageH2_router_items.jsonl(148 点冻结标签,sha256 8100f892…)与
预注册文档保留在 repo,供未来重预注册时引用。已下载的
Qwen3.5-4B(8.8G)留在 /workspace/yjx/models,未产生其他成本。

## §7 transition dataset(只建不训)

analysis/stageH_transition_dataset.jsonl(sha256 28d569f…):
h0 148 点(含 H2 冻结标签)+ h1 104 fire(P2 38 / C 34 / G 32),
每条 = (node, 合法边菜单, 注入块, next_prim, guard_ok, validated@5,
episode SR)。fire 级 validated:P2 21/38、G 16/32、C 11/34 —— 与
episode 级 VR 同序。**未做任何训练;H3 不自动开启**(若未来重启,
首要设计变化 = 给 router/guard 执行权而非建议权,本 stage M2 即动机)。

## 冻结清单完整性

graph v0、interpreter/retriever/render、61 卡、Q0_FIXED、Planner/
Pi0.5/SAM3/primitives/turn budget 40、B2 verifier、SM1 全程未动;
H1 三臂差异仅为两个 env 取值(prereg §2)。无图编辑、无补跑、
无看结果调参循环。

## 产出物索引

- 判定与主表:analysis/stageH1_results.{md,json}(scripts/analyze_stageH1.py)
- 数据集:analysis/stageH_transition_dataset.{jsonl,md}
- 预注册:analysis/stageH1_prereg.md / stageH2_prereg.md(已盖作废戳)
- 基准与审计:analysis/stageH0_{protocol,failure_states,graph_audit}.*
- 运行日志:.gap_run/h1_super.log(15:49 09-28 → 06:20 09-29)
