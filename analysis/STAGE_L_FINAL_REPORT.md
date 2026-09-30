# Stage L 最终报告 — Verify-to-Evolve Executable Graph(2026-09-30)

- split_hash `77695bed7074` | graph_hash(终图)`59fc95a753ac3628`
- 预注册:analysis/stageL_prereg.md(v1.1 含 §17 偏差 1–9,全部先于对应运行)
- 预算:DEV 624 rollouts(≤2400 ✓)| HELDOUT 0(见 §Gate A)| infra 0

## 判定(仅三档)

> ## GRAPH EVOLUTION NOT SUPPORTED
> 执行反馈未能把退化恢复图进化成任何物理验证成立的新边:两轮
> generate-verify-promote,5 候选全 REJECT,零晋升;终图 ≡ 冻结图。

三个假设:

| 假设 | 判定 | 一句话证据 |
|---|---|---|
| H_L1 挖掘恢复前缀 → 更好候选 | **NOT SUPPORTED** | 63 前缀 → 5 条词表内可编译候选 → 312 候选 rollout 中 **0 VERIFIED** |
| H_L2 双验证过滤四类失败 | **INCONCLUSIVE(仪器成立,过滤单边)** | A 侧 624 rollout 0 违规(候选全部如实执行,过滤量 0);B 侧完成 100% 拒绝(效力/伤害) |
| H_L3 条件特化(状态→不同最优边) | **NOT REACHABLE** | 零晋升 ⇒ Gate B 前置 Gate A 即 FAIL;DEV 内 FG 恰 1 条有效边、RPS 0 条,无第二条边可特化 |

## 过程数字

- **Round 1(DEV,34 快照 × 冻结 5 边 + 4 候选,K=4)**:584 rollouts,
  0 infra,0 A-FAIL。LC-FG-1/2 全 NO_EFFECT(SAM3 分数 0.009–0.059 ≪
  阈值 0.2,感知死);LC-RS-1 doubled 40/40 烧满 20 chunks 且 d_ooi_z≡0;
  LC-RS-2 harm 0.143(prompt 指向原抓取位置,横扫)。
- **Round 2(最小修复,§11)**:取证驱动仅 1 条修复 LC-RS-1R(插入
  `move_to(${eef}, gripper=1)` 下降步,证据 = 挖矿唯一 TASK_LANG-doubled
  成功 t9s6 的结构);40 rollouts:仍 0 VERIFIED,harm 恶化到 0.208
  (开爪下压扫动物体)→ REJECT。LC-FG-1/2、LC-RS-2 无词表内修复,
  REJECTED 终态(理由+数据锚见 stageL_candidate_edges_v1.jsonl)。
- **冻结基线同批复现 K 结构**:FG-3 P̂_v 0.552(P̂_h 0.031)是全部
  12 边中唯一物理验证成立的恢复边;FG-1/FG-2、RS-1/RS-2/RS-3 全 0
  (RS-2 另有 P̂_h 0.15)。

## Gate A(formation):FAIL(恒等式,HELDOUT 未动)

进化图 = 冻结图 + ∅ 晋升 ⇒ 两图边集恒等 ⇒ COV 差与 BEST 差在任何
评测集上恒为 0,不可能 ≥ +0.15 / +0.10。此为数学恒等而非统计估计,
无需 rollout 即可判定(偏离记录 §17-8)。按 §16:Gate A FAIL → STOP,
HELDOUT 24 快照保持原封(未被挖掘/评测/任何策略接触)。

## 机制层发现(对后续最有信息量的部分)

1. **失败状态上感知是死的**:FG 快照态下 SAM3 以 TASK_LANG grounding
   分数 0.009–0.059(阈值 0.2)—— 不是阈值过严,是任务语言在这些
   状态分割不出目标。一切"先感知再定位"的恢复结构(冻结 FG-1、
   候选 LC-FG-1/2)在此域结构性不可行;唯一可行机制是不依赖感知的
   盲修正重抓(FG-3,偏移 ~2cm 重试,0.552)。
2. **RPS 的根本缺口 = "物体现在在哪"不可观测**:释放后物体在盘边,
   而冻结绑定词表全部 prompt(TASK_LANG / LAST_PICK_PROMPT)都指向
   原抓取位置;挖矿成功案例 10/11 用短单一意图 prompt("pick up the
   bowl on the plate"),冻结词表无此变换。pi0_doubled 从高处以长
   prompt 出发 40/40 烧满 chunk 预算、从未接触物体。修复 RPS 需要
   "当前位置"类新观测源 —— 属 §0 禁区(新感知模块)。
3. **历史成功 ≠ 边可承载**:挖矿 63 前缀中验证转移 95% 是 term 型
   (回合终局成功),由 planner 多步策略+字面路点(非 eef/obj 可导)
   实现;单边物理契约(窗口内可判)只能承载其中极小且恰已存在于
   冻结图的部分。这是 verify-to-evolve 在本域失败的核心结构性原因。
4. **跨进程快照复现性**:重放前缀含 pi0 原语 → 推理非确定性使跨进程
   快照态漂移 ~2.5e-4m(同进程 restore 逐位精确,readback=0)。跨轮
   配对比较在此精度下成立;分析层曾因用错轮次 base 产生 96 条假
   A-FAIL,已修(§17-9),运行期判定不受影响。

## §15 十问直答

| # | 问 | 答 |
|---|---|---|
| Q1 | prefix→有价值候选? | **NO**:63→5 可编译→0 有用;成功模式结构上在词表外(字面路点/短 prompt/term 型) |
| Q2 | generate-verify-promote 精度? | 生成侧 0/5;晋升门没有误放行(精度门真实拦住全部),但无真阳性可检出 |
| Q3 | 执行一致性过滤量? | **0**(624 rollout 0 A-FAIL;候选全部如声明执行 —— 失败在物理效力,不在执行漂移) |
| Q4 | 物理验证过滤量? | **100%**(5/5 候选由 B 侧效力/伤害拒掉;A 侧未过滤任何东西) |
| Q5 | 进化图 coverage > 冻结图? | **NO(恒等)**:Gate A FAIL,两图同边集 |
| Q6 | promoted 跨任务/seed 复现? | n/a(零晋升) |
| Q7 | 同族多条有效边? | **NO**:FG 恰 1 条(FG-3),RPS 0 条 |
| Q8 | 不同状态最优边不同? | **无证据**:FG-3 在其有效处全面占优,无逐状态分化 |
| Q9 | 特化增益够大? | **不可评**(Gate B 前置失败;无第二条边可特化) |
| Q10 | 资格重启 Rule/学习打分器/WM/Router? | **NO**:瓶颈在边层之下(感知死/位置不可观测),选择器无物理有效的边可选,硬 STOP(§0/§18) |

## STOP(§16/§18)

按预注册:Gate A FAIL → 停止图进化线;Stage L 后硬 STOP —— 不重启
Router 训练、WM、新编码器、SFT/OPD/RL、加进化轮、full-episode Graph
campaign。冻结图(FG-3 唯一有效恢复边)与 HELDOUT split 保持原封。

## 工件索引(§14)

| 工件 | 状态 |
|---|---|
| stageL_split_manifest.csv / stageL_prereg.md(v1.1) | 冻结(commit 7e3c327/4fd8866) |
| stageL_recovery_prefixes.jsonl(63) | commit 4fd8866 |
| stageL_candidate_edges_v0.jsonl(4+5 REJECT) | commit 99323a4 |
| stageL_round1_verification.csv / decision.md / decisions.json | commit da0d8de(+回归重发) |
| stageL_candidate_edges_v1.jsonl(1 修复+3 终态 REJECT) | commit da0d8de |
| stageL_round2_verification.csv / decision.md / decisions.json | 本 commit |
| resources/libero/executable_graph_stageL_final.yaml(graph_hash 59fc95a753ac3628) | 本 commit |
| stageL_heldout_edge_utility.csv / stageL_specialization.csv | **不生成**(Gate A 恒等 FAIL,HELDOUT 未执行,§17-8) |
| logs/stageL_round{1,2}/rollouts.jsonl | 工作产物(gitignore),汇总入 CSV |
