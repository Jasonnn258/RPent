# Stage C2 结果:Progress-Aware Trigger 离线 benchmark(2026-09-18)

设计(预注册 labeler + T1 规则)见 `memory_stageC2_design.md`;机器可读
`memory_stageC2_results.json`。官方 60 集(memB2/B3,CSV repeat=1),修正 GT
98 个 SHOULD 时刻(grasp 37 / pick_verify 11 / predicate_open 25 /
recovery_transport 24 / perception 1)。

## 一句话判定

**PROGRESS TRIGGER SUPPORTED(离线,过预注册门槛)**:T1 precision 0.986 /
recall 0.776 / F1 0.868,对 T0 的 0.266 / 0.245 / 0.255;#49 的 69 个误报
**69/69 同类消除**,T4 里 65/73 实锤是"全 PROGRESSING 的 waypoint 链"。
**但 precision 有构造性循环**(见下),真正的仲裁在 C3 在线。

## 先报一个勘误:Stage B 的 SHOULD 时刻 GT 漏了全部 pick 类

`analyze_memory_stageB.should_retrieve_moments` 检查 result name == "pi0_pick",
而 states.json 里 pick 结果名为 **"pick"** → 60 集里 48 个 pick 类事件
(37 grasp + 11 pick_verify)全部漏计。修正后(同 45 个有火集):

| | 旧(Stage B 报告) | 修正 |
|---|---|---|
| SHOULD 时刻 | 45 | **84**(+30 grasp +9 pick_verify) |
| T0 coverage | 24/45 = .533 | **24/84 = .286** |
| T0 precision | 25/94 = .266 | .266(不变;T0 本就没有 pick 规则火) |

Stage B 的判定(coverage、precision 双低 → trigger 不支持)**不变且加强**;
task/ranking 层不受影响。`memory_stageB_results.md` 已追加勘误节。

## 主表(同分母 98 时刻,官方 60 集)

| 臂 | fires | aligned | precision | covered | recall | F1 | fires/ep |
|---|---|---|---|---|---|---|---|
| T0(#49 落盘火,不改) | 94 | 25 | .266 | 24/98 | .245 | .255 | 1.57 |
| T1(progress-aware,冻结) | 70 | 69 | **.986** | 76/98 | **.776** | **.868** | 1.17 |

T1 火构成:R2 move-no-progress、R5 release-谓词未置、R3 pick 链/假成功、
R1 perception、R4 doubled-无变化;infra 同 #49(cap 6、cooldown 2 turn)。

## T0 为什么这么差:两个结构性机制(非平凡发现)

1. **boundary 只评估"最后一个结果"**:move-stopped-short(final_dist>0.03)
   与 pick failure 规则在线 **0 火**——短 move / 失败 pick 之后 planner 常立刻
   调 segment 等,结果在 boundary 被覆盖,信号根本没被评估。24 个 transport +
   37 个 grasp 时刻全靠 T4 的"重复计数"碰运气覆盖(实际只盖住 6)。
   T1 逐结果评估(修复信号丢失,部署上等价:火挂到下一 boundary 注入)。
2. **T4 重复计数把正常运输当卡住**:73 个 T4 火,65 个落在"链上每个 move 都
   在前进/到达"的 PROGRESSING 链(labeler 用 eef-target 距离独立判定);
   T1 在 PROGRESSING 事件上 **0 火**(53 STALLED + 17 AMBIGUOUS)。

## 69 个 T0 误报消除 + recall 缺口(如实)

- T0 未对齐火 69 个:T1 同类消除 **69/69**;any-class 口径 55/69(其余 14 个
  turn±1 内有别的 T1 火,多为真时刻附近)。
- T1 漏的 22 个时刻 = grasp 19 + transport 2 + predicate 1。grasp 缺口是
  **规格要求的代价**:"primitive_result=false 不自动等于 STALLED"——37 个失败
  pick 中 28 个在连续失败链(第 2+ 个才火),9 个孤立失败 + 14 个链首失败
  按 AMBIGUOUS 不火。这是设计选择不是 bug;在线若要补,靠 pick_verify 的
  "reported-success-but-no-lift"(R3 已覆盖,9/11)与 cooldown 让位。

## 循环性声明(诚实边界)

T1 的火规则与 SHOULD 时刻定义**同源**(都读 result 字段 + pre/post state:
final_dist / libero_terminated / ascent / found)。因此 0.986 的 precision 部分
是构造性的——T1 在"post-hoc SHOULD 定义认为该火的地方"火。非循环的证据是:
①T0 与 T1 用同一 GT,T0 只有 .245/.266(差异来自评估时机与规则形态,真实);
②waypoint 误报消除用的是独立物理量(eef-目标距离变化),65/73 实锤;
③AMBIGUOUS/PROGRESSING 不火的性质独立于时刻定义。**最终裁决权交给 C3 在线
O0 vs O2。**

## 门槛(预注册)

- T1 precision 0.986 ≥ 0.50 ✓;recall 相比 T0 下降 −53pp(上升)≤10pp ✓
- **→ PASS,PROGRESS TRIGGER SUPPORTED(离线)。T1 规则冻结进 C3。**

## C2 必答问题(用户 10 问的 C2 子集)

1. precision/recall?→ T0 .266/.245;T1 **.986/.776**(循环性 caveat 见上)。
2. 69 个 false trigger 消掉多少?→ 同类 69/69,any-class 55/69。
3. 正常连续 move 还会被误判吗?→ 不会:PROGRESSING move 上 T1 0 火
   (T0 是 65/73 的 T4 火源)。
4. AMBIGUOUS 多少?→ 全部 634 个已标事件中 119 个(18.8%);T1 在 17 个
   AMBIGUOUS 事件上火(release 后 post state 缺失、以谓词预期为准,rule R5)。

## C3 推论(合并 C1 判定)

C1 NOT SUPPORTED + C2 PASS → **在线只跑单变量 O0 vs O2**
(OLD_TRIGGER+POOR_QUERY vs PROGRESS_TRIGGER+POOR_QUERY,全 soft、词面、
access fix)。O0 ≡ #49 memB2 → compatibility audit 通过则复用其 30 集,
新增仅 O2 的 30 集(3 任务 × 10 seeds)。
