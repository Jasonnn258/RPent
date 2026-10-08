# Stage R 终报 — Failure Persistence & Retryability Characterization

状态:**草稿(R1 执行中;【R2 待填】= 等 stageR2_analyze.py 产物)**
预注册:analysis/stageR_prereg.md(冻结 2026-10-07,commit 7347a66)
窗口:2026-10-07 → 2026-10-08 | 分支 research/pre-ovpm-20260905

核心问题(spec §1):**观测到一次 manipulation failure 后,我们实际拥有多少
"该失败会持续"的证据?** 一次 FALSE_GRASP 可能是 (A) 执行层偶然没抓中 /
(B) 该具体动作不好 / (C) policy 在该状态附近整体抓不中 / (D) 证据不足。
Stage R 只负责测量,不建任何 recovery method(§36 Hard STOP)。

---

## 1. 执行摘要(白话)

- 在 187 个全新 episode(seed 121-190,与历史池零交集)里筛出 32 个
  "稳定失败"的抓取失误事件:机器人第一次抓空后,整个失败技能期间连
  "抓到东西"的迹象都没有;
- 对每个事件,把机器人"卡壳前一刻"的世界状态用**逐条重放历史动作**的
  方式精确重建(R0 验证:32/32 次重建与原始状态哈希逐位一致),然后:
  - **A 臂**:把当时失败的那个动作原样再执行 8 次;
  - **B 臂**:让 Pi0.5 在同一状态重新采样新动作 8 次;
  - **NATURAL 臂**(陪报):从失败后的状态直接重发同一句命令 4 次;
- 看哪些失败"再试就好了"、哪些"怎么试都不行",把失败分成
  E(偶发)/ A(动作问题)/ P(policy 持续不会)/ U(证据不足)四类。

【R2 待填:总体结果一段】

## 2. 设计要点(全部预注册冻结)

| 项 | 冻结值 |
|---|---|
| PRIMARY OUTCOME | STABLE_RECOVERY(Stage Q 冻结契约:首中后全测量点保持 ∧(任一点 check_success ∨ 保持点数 ≥4);ACQUISITION 仅 secondary)|
| 统计单位 | event(24 cohort;禁把 24×8 写成 N=192)|
| 重建方法 | R0 门后冻结 = PREFIX_REPLAY,禁按结果切换 |
| K_same / K_resample / K_nat | 8 / 8 / 4 |
| TYPE 规则(K=8) | E: same≥2;A: same=0∧policy≥2;P: 双 0;U: 其余 |
| infra 纪律 | trial ≤3 重试;event >50% infra 保留+flag;formal >2% 暂停解释 |
| bootstrap | by event,BOOT_SEED=20261007,Wilson CI |

措辞纪律:全文只写 persistent@8(0/8 是"8 次内未观察到稳定恢复",
不是"绝对不可恢复");重建状态写 task-equivalent / observably matched,
不写 bit-exact identical(低维一致≠全状态一致,图像列 not_available)。

## 3. 采集(collect)

- grid {t3,t5,t9} × seeds 121-190 = 210 格,collect 序扫描,187 个终态
  episode,32 个稳定 FG 事件进入配额(需求 32,容差 22-26 —— **恰好满额,
  无 deviation**);任务分布 t3:11 / t5:7 / t9:14;
- 进入标准五条全部满足:首个失败=FALSE_GRASP@nominal pi0_pick(t0≥2)、
  稳定失败契约(失败技能全程无 acquisition 点 ∧ 非成功收尾)、S_pre
  provenance 完整、a_fail 首 chunk 完整落盘、重建方法可用;
- **零结果条件化**:重放即成功 / 8/8 全败等 case 一律保留(§27);
- 仪器:RPENT_STAGE_R_TRACE=1(技能边界 save_state 快照 + 动作流逐条
  base64 落盘),零语义改动,冒烟验证零干扰。

## 4. R0 重建资格门(DEV 8 事件 × 三臂 × 4 trials)

| 臂 | n | stable | rate |
|---|---|---|---|
| LIVE(fresh boot_to_pre) | 32 | 12 | .375 |
| SNAP(restore S_pre 字节) | 32 | 10 | .312 |
| PREFIX(reset+动作重放) | 32 | 12 | .375 |

|SNAP−LIVE| = 6.2pp ≤ 10pp;|PREFIX−LIVE| = 0.0pp ≤ 10pp → **QUALIFIED**。
PREFIX 重建 sha 逐位一致率 **32/32 = 1.000**,flatten Δmax 中位 **0.0**
(重放数学上精确)。选择规则 → **R1 冻结 PREFIX_REPLAY**。

含义:本栈 (task,seed) reset 为确定性 init,且动作流逐位保真,故
PREFIX_REPLAY 到达的 S_pre 与原始 live 状态**哈希级一致**。这比 Stage Q
restore(transition-class 一致率 77%)更强,是 Stage R 因果解释力的地基。

## 5. R1 双臂结果(24 cohort 事件)

【R2 待填:q_same/q_policy 分布(mean/median/fraction q>0/boot CI)、
Retryability@8 四指标、STRONG_PERSISTENT 占比、NATURAL 陪报】

### 5.1 持续谱(TYPE)

【R2 待填:E/A/P/U 计数 + stageR_persistence_map 引用】

### 5.2 retry 曲线

【R2 待填:C(k)/h(k) 两臂 + Gain 1→2/2→4/4→8】

## 6. 六假设判定(prereg §10 门)

【R2 待填:stageR_hypothesis_results.md 表】

## 7. 必答 Q1-Q10(spec §35)

【R2 待填:逐答】

## 8. Relation to Recovery Literature

定位原则(spec §3):Stage R 提供的是 **complementary measurement axis**,
不称绝对 novelty。

- **RoboRecover**(temporary vs stable deviation 分类 + 恢复策略):其
  分类学的实证地基正是"失败持续性测量";Stage R 给出该分类在
  FALSE_GRASP 族上的可复现量化(E/A/P/U 谱),为其 deviation 判别提供
  先验,不替代其恢复方法;
- **Kintsugi-VLA**(repeated interventions + Wilson CI 报告):其统计纪律
  (重复干预、区间报告)与本 stage 一致;Stage R 补充的是"同一状态重建 +
  双臂对照"的受控版本(intervention 的 persistence 归因而非累积修复);
- **FLARE**(failure-language 条件恢复训练)/ **FAR**(偏好式失败适配):
  两者的训练信号都预设"失败后重试/适配有 headroom";Stage R 的
  POLICY_PERSISTENT@K 事件集正是这类方法**有/无 headroom 的直接度量**——
  persistent@8 状态是它们的真 benchmark 候选(Q10);
- **ReTVL**(恢复型 VLA 评测):Stage R 的 q 概率 + retry 曲线可作为其
  评测的分层数据源。

以上均为互补关系陈述;Stage R 不训练、不适配、不建库。

## 9. Deviation 记录(prereg 附录 B 原文照录)

- **dev-r1-fix(2026-10-08 05:59)**:R1 首启(04:58)队列切分 bug ——
  `load_events` 的 `ord` 误用 ledger 行号(切分依据 included 序号),
  manifest 32 事件全标 R1_COHORT、8 个 DEV 事件误入队列。05:01 停止,
  多跑 4 trial(全在 DEV 事件上,不在最终 cohort)。处置:修 ord、
  manifest/rollouts 重新冻结、CPS 日志保留越轨 trial 作审计。cohort 24
  事件全部从零执行,判定不受影响。

## 10. Hard STOP(spec §36)

Stage R 完成后 STOP。禁止自动:recovery method / classifier / escalation
policy / adaptive retry controller / FAR-style preference adaptation /
FLARE-style recovery training / Graph / World Model / verifier / Planner
redesign / SFT / OPD / RL。Stage R 只负责 MEASURE FAILURE PERSISTENCE;
下一步研究线等用户决定。

## 产物清单(prereg §14)

stageR_prereg.md / stageR_collect_ledger.csv / stageR0_probes.jsonl /
stageR_reconstruction_dev.csv / stageR_reconstruction_decision.md /
stageR_manifest.csv / stageR_failure_events.jsonl /
stageR_same_action_rollouts.csv / stageR_resample_rollouts.csv /
stageR_trial_checkpoints.jsonl(审计)/ stageR_event_probabilities.csv /
stageR_persistence_map.csv / stageR_retry_curves.csv /
stageR_hypothesis_results.md / 本报告。
