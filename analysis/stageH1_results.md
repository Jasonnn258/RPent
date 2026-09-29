# Stage H1 结果 — Frozen Graph vs Flat Cards vs Generic Refresh

_2026-09-28 by scripts/analyze_stageH1.py(指标/门 = analysis/stageH1_prereg.md §5/§7 冻结定义)。_

- 冻结 30 格 × 3 臂 = 90;有效集 90(infra 缺失 0);冒烟/格 外行 3(已排除)
- **INCONCLUSIVE-VR 降级**:某臂有 fire 的 episode < 20(prereg §6)— VR 面如实降级,SR 面照判
- **触发重放交叉核对不一致 13 集**(已从 fire 类指标剔除,SR 保留):[('h1C', 3, 3, 4, 3), ('h1C', 3, 6, 0, 3), ('h1C', 3, 9, 3, 2), ('h1C', 3, 12, 3, 2), ('h1C', 3, 18, 0, 3), ('h1C', 5, 1, 0, 1), ('h1G', 3, 2, 2, 1), ('h1G', 3, 11, 5, 4), ('h1G', 3, 13, 4, 3), ('h1P2', 3, 1, 3, 2)]

## 主表(per arm)

| 指标 | P2(泛型) | CARD(扁平卡) | GRAPH(冻结图) |
|---|---|---|---|
| n(有效集) | 30 | 30 | 30 |
| SR | 25/30 (83.3%) CI[66.4%,92.7%] | 20/30 (66.7%) CI[48.8%,80.8%] | 23/30 (76.7%) CI[59.1%,88.2%] |
| fires 总数(均/集) | 38 (1.3) | 34 (1.1) | 32 (1.1) |
| 有 fire 的 episode | 20 | 17 | 18 |
| validated_recovery(episode 级) | 15/20 (75.0%) CI[53.1%,88.8%] | 7/17 (41.2%) CI[21.6%,64.0%] | 13/18 (72.2%) CI[49.1%,87.5%] |
| wrong_phase_advice_rate(fire 级) | 38/38 (100.0%) CI[90.8%,100.0%] | 0/34 (0.0%) CI[0.0%,10.2%] | 0/32 (0.0%) CI[0.0%,10.7%] |
| post_intervention_progress@3(诊断) | 15/38 (39.5%) CI[25.6%,55.3%] | 7/34 (20.6%) CI[10.3%,36.8%] | 12/32 (37.5%) CI[22.9%,54.7%] |
| guard_violation_rate(GRAPH 专属) | — | — | 27/30 (90.0%) CI[74.4%,96.5%] |

### VR per family(episode 级;分母 = 该家族有 fire 的集数)

| 家族 | P2 | CARD | GRAPH |
|---|---|---|---|
| FALSE_GRASP | 11/15 (73.3%) CI[48.0%,89.1%] | 7/13 (53.8%) CI[29.1%,76.8%] | 11/16 (68.8%) CI[44.4%,85.8%] |
| MOVE_CONTACT_STALL | 2/3 (66.7%) CI[20.8%,93.9%] | 0/3 (0.0%) CI[0.0%,56.2%] | 0/0 |
| RELEASE_PREDICATE_STALL | 5/9 (55.6%) CI[26.7%,81.1%] | 0/5 (0.0%) CI[0.0%,43.4%] | 3/4 (75.0%) CI[30.1%,95.4%] |

## 门槛(prereg §7)

| 门 | 定义 | 实测 | 判定 |
|---|---|---|---|
| M1 wrong_phase | GRAPH ≤ 0.5×CARD | 0.0% vs ≤0.0% | PASS |
| M2 guard_violation | GRAPH ≤ 2% | 90.0% (27/30) | FAIL |
| 行为门 A | VR_G ≥ max(VR_ctrl)+10pp 且 SR_G ≥ max(SR_ctrl)−3pp | VR 72.2% vs 75.0%+10pp;SR 76.7% vs 83.3%−3pp | FAIL |
| 行为门 B | SR_G ≥ max(SR_ctrl)+8pp 且 VR_G ≥ max(VR_ctrl) | SR 76.7% vs 83.3%+8pp;VR 72.2% vs 75.0% | FAIL |
| 家族门 FALSE_GRASP | GRAPH−P2 配对差 ≥ 0 (全 30 格) | Σdiff=+0(matched 13 格 Σ=False) | PASS |
| 家族门 MOVE_CONTACT_STALL | GRAPH−P2 配对差 ≥ 0 (全 30 格) | Σdiff=-2(matched 13 格 Σ=False) | FAIL |
| 家族门 RELEASE_PREDICATE_STALL | GRAPH−P2 配对差 ≥ 0 (全 30 格) | Σdiff=-2(matched 13 格 Σ=True) | FAIL |
| 家族门合计 | ≥2/3 | 1/3 | FAIL |

## 判定
**REPRESENTATION NOT SUPPORTED**

## 口径备注(操作化声明)
- fire 步位 = 运行时同一触发代码对该集 states.json 的重放(replay 校验已证一致),并与 memory_events.jsonl 逐点交叉核对;
- wrong_phase:CARD 检索为 EMPTY(无注入)的 fire 不进分母(保守口径,利于对照);P2 恒为泛型文本(预期全 wrong);匹配词表 = 映射原语集 ∪ 合法边 action_family 名(prereg §5 2026-09-28 修订,数据前冻结);
- guard_violation 分母 = fire 后存在下一条动作原语的 fire(感知步天然不进 states.json;无后续动作原语 = 豁免);
- PIP@3 为诊断项:相位推进以家族物理证据(§5 验证规则)在 3 步窗内成立为代理(SM1 逐步相位不在 states.json);
- 家族门主口径 = 全 30 格 cell 级指示差(含 fire 覆盖);matched(两臂均有该家族 fire)子集附报。

**注入块违禁词命中 34**:口径(prereg §3(c) 2026-09-28 澄清)——新内容臂(P2/GRAPH)应为 0;CARD 命中为冻结 61 卡正文继承(2 张卡 falsify/how_to 含 'fail',G0.5 同款注入),如实报告、不改卡:[('h1C', 3, 1, 3, ['fail']), ('h1C', 3, 1, 5, ['fail']), ('h1C', 3, 2, 2, ['fail']), ('h1C', 3, 2, 4, ['fail']), ('h1C', 3, 4, 3, ['fail']), ('h1C', 3, 4, 5, ['fail']), ('h1C', 3, 5, 4, ['fail']), ('h1C', 3, 5, 6, ['fail']), ('h1C', 3, 7, 4, ['fail']), ('h1C', 3, 7, 7, ['fail'])]