# Stage R 终报 — Failure Persistence & Retryability Characterization

定稿:2026-10-08 | 预注册:analysis/stageR_prereg.md(冻结 2026-10-07,commit 7347a66)
窗口:2026-10-07 → 2026-10-08 | 分支 research/pre-ovpm-20260905
执行:R0 96 trials + R1 480 trials,全程 **0 infra、0 EXC**;统计单位 = event(24 cohort)。

核心问题(spec §1):**观测到一次 manipulation failure 后,我们实际拥有多少
"该失败会持续"的证据?** 一次 FALSE_GRASP 可能是 (A) 执行层偶然没抓中 /
(B) 该具体动作不好 / (C) policy 在该状态附近整体抓不中 / (D) 证据不足。
Stage R 只测量,不建任何 recovery method(§36 Hard STOP)。

---

## 1. 执行摘要(白话)

机器人第一次抓空后,我们把它"卡壳前一刻"的世界状态逐位重建出来,然后:

- **把当时失败的那个动作原样再执行 8 次**:24 个事件里 18 个(75%)至少
  一次成功抓稳,14 个(58%)成功 ≥2 次;
- **让 Pi0.5 在同一状态重新采样新动作 8 次**:19 个(79%)至少一次成功,
  但配对看**重采样相对原动作重放的平均增益只有 +2.1pp(中位 0)**;
- **真正"怎么试都不行"的**:5 个事件(21%,8+8=16 次全失败),
  **全部集中在最难的 t9 任务**;另有 6 个事件原动作 8 次全败,其中仅
  1 个(r129)重采样能救回(5/8);
- "抓到过"(acquisition)远多于"抓稳了"(stable):acquisition 率 ~65-70%,
  stable 率 ~30%,差距 ~35pp —— Stage Q 的 TRANSIENT_SUCCESS 在新队列
  **复现且更强**;
- 连续失败次数是强信号:连败 3 次后,17 个事件-臂的第 4 次尝试仅 1 次成功;连败 7 次后 0/11。

一句话:**单次 FALSE_GRASP 对"未来还会失败"的证据力很弱(多数事件换不来
几次就能成功);持续的 policy 级失败存在但集中(全部 t9),它们才是
recovery 方法该瞄准的 benchmark 底物。**

## 2. 设计要点(全部预注册冻结)

| 项 | 冻结值 |
|---|---|
| PRIMARY OUTCOME | STABLE_RECOVERY(Stage Q 冻结契约:首中后全测量点保持 ∧(任一点 check_success ∨ 保持点数 ≥4);ACQUISITION 仅 secondary)|
| 统计单位 | event(24 cohort;禁把 24×8 写成 N=192)|
| 重建方法 | R0 门后冻结 = PREFIX_REPLAY,禁按结果切换 |
| K_same / K_resample / K_nat | 8 / 8 / 4 |
| TYPE 规则(K=8) | E: same≥2;A: same=0∧policy≥2;P: 双 0;U: 其余 |
| infra 纪律 | trial ≤3 重试;event >50% infra 保留+flag;formal >2% 暂停解释 |
| bootstrap | by event,BOOT_N=10000,BOOT_SEED=20261007,Wilson CI |

措辞纪律:全文只写 persistent@8(0/8 是"8 次内未观察到稳定恢复",不是
"绝对不可恢复");重建状态写 task-equivalent / observably matched,不写
bit-exact identical(低维一致≠全状态一致;图像列 not_available,附录 A-1)。

## 3. 采集(collect)

- grid {t3,t5,t9} × seeds 121-190 = 210 格,collect 序扫描,187 个终态
  episode,32 个稳定 FG 事件进入配额(需求 32,容差 22-26 —— **恰好满额,
  无配额 deviation**);任务分布 t3:11 / t5:7 / t9:14(全部 32 事件,
  前 8 为 R0 DEV);
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

## 5. R1 双臂结果(24 cohort 事件 × 20 trials = 480,零 infra)

### 5.1 恢复概率分布

| 指标 | 值 |
|---|---|
| q_same(同动作重放 stable 率) | mean .302(boot95% [.193,.417]),median .250,q>0 = 18/24 |
| q_policy(重采样 stable 率) | mean .323(boot95% [.229,.422]),median .125,q>0 = 19/24 |
| 配对差 q_policy−q_same | mean +2.1pp,median 0.0pp;6/24 事件重采样反而更低 |
| q_same_acq / q_policy_acq | .646 / .698(acquisition 陪报) |
| NATURAL(S_post restore ×4,陪报) | q_nat mean .323,q_nat_acq .646 |

### 5.2 Retryability@8 与持续谱

| 指标 | 值 |
|---|---|
| SAME ≥1 / ≥2 | 18/24 / 14/24 |
| POLICY ≥1 / ≥2 | 19/24 / 16/24 |
| SAME_PERSISTENT(0/8) | 6/24 |
| POLICY_PERSISTENT(0/8) | 5/24 |
| **STRONG_PERSISTENT(双 0)** | **5/24 = 20.8%**(r143/r168/r171/r181/r185,**全 t9**)|

**TYPE 谱:E=14(58.3%) A=1(4.2%) P=5(20.8%) U=4(16.7%)**

分任务(事件数小,只作稳定性旁证):

| task | n | E/A/P/U | mean q_same | mean q_policy |
|---|---|---|---|---|
| t3 | 3 | 1/0/0/2 | .417 | .458 |
| t5 | 7 | 5/1/0/1 | .339 | .482 |
| t9 | 14 | 8/0/5/1 | .259 | **.214(低于 same)** |

t5 重采样 +14pp 最受益;t9 重采样反而 −4.5pp 且全部 P 型都在 t9 ——
持续失败呈任务集中性,非均匀分布。

### 5.3 retry 曲线 C(k)/h(k)

| k | C_same | C_pol | h_same(n) | h_pol(n) |
|---|---|---|---|---|
| 1 | .250 | .167 | .250(24) | .167(24) |
| 2 | .500 | .458 | .333(18) | .350(20) |
| 4 | .625 | .708 | .100(10) | **.000(7)** |
| 8 | .750 | .792 | .000(6) | **.000(5)** |

增益:POLICY +29.2 / +25.0 / +8.3pp(1→2/2→4/4→8);SAME +25.0 / +12.5 / +12.5pp。

h(k) 两个非单调点:h(1)→h(2) 微升(same .25→.33,pol .17→.35;首试失败
事件里含一部分后续易成功者);**k≥4 后接近坍零:连败 3 次的 17 个
事件-臂第 4 次尝试合计 1/17 成功(POLICY 0/7、SAME 1/10);连败 7 次
后 0/11(POLICY 0/5、SAME 0/6)。**

### 5.4 NATURAL 臂(描述性)

从原始 S_post 直接重发同命令,q_nat .323 ≈ 重建臂水平 —— 在本栈
post-state 重建(descriptive,只能 approximate)下自然重试与重建重试
可观成功率同量级;按 §6 纪律不入 persistence 因果证据。

## 6. 六假设判定(prereg §10 门)

| 假设 | 判定 | 依据 |
|---|---|---|
| EPHEMERAL_FAILURES_EXIST | **SUPPORTED** | TYPE E = 14/24 ≥ 2 |
| ACTION_SPECIFIC_FAILURES_EXIST | INCONCLUSIVE | TYPE A = 1(门:≥2 支持/0 不支持)|
| POLICY_PERSISTENT_FAILURES_EXIST | **SUPPORTED** | TYPE P = 5/24 ≥ 2 |
| ONE_SHOT_FAILURE_IS_INFORMATIVE | INCONCLUSIVE | median q_policy=.125 ≤.25 但 STRONG@8 占比 20.8% < 25%(两条须同时满足)|
| RETRY_GAIN_SATURATES_EARLY | INCONCLUSIVE | C_pol(8)−C_pol(4) = 8.3pp 落 5-10pp 中间带 |
| TRANSIENT_SUCCESS_REPLICATES | **SUPPORTED** | pooled ACQ−STABLE gap:SAME +34.4pp / POLICY +37.5pp(≥15pp)|

3 SUPPORTED / 3 INCONCLUSIVE / 0 NOT_SUPPORTED。不设总判定;全部指标
under FALSE_GRASP and current Pi0.5/runtime。

## 7. 必答 Q1-Q10(spec §35)

**Q1 一个第一次出现的 stable FALSE_GRASP 有多大概率无法再次复现?**
分三个口径:同一 frozen action 单次重放的 stable 成功率 = mean q_same
.302;8 次同动作重放内至少一次成功(= 失败未复现)18/24 = 75%;
8 次内从未复现失败(q_same = 8/8 全成)为少数,6/24 事件 0/8 全败
(SAME_PERSISTENT)。即:**单次观测的 stable 失败,四分之三的事件在
重复执行下会至少一次"翻案"。**

**Q2 刚失败的同一个 frozen action 重新执行,stable recovery probability?**
mean .302(boot95% [.193,.417]),median .250;per-trial pooled 同水平。
注意臂内不独立(同一事件 8 次共享状态),此为 event-level 分布的均值。

**Q3 重新 sample Pi0.5 相比 same-action replay 增加多少 recovery?**
配对 mean +2.1pp / median 0.0pp;≥1 成功事件数 +1(19 vs 18);
C_pol(8)−C_same(8) = +4.2pp。**总体接近零增益**;方向上重采样把
"至少一次成功"的概率推得略高,但把单事件集中成功率(q 中位数)拉低
(.125 vs .250)—— 重采样换来覆盖面,不换来深度。分任务异质:
t5 +14.3pp,t9 −4.5pp。

**Q4 E/A/P 各占多少?**
E(execution-ephemeral)= 14(58.3%);A(action-specific)= 1(4.2%);
P(policy-persistent)= 5(20.8%);U(unresolved)= 4(16.7%)。
主谱 = 偶发执行失败;policy 持续失败为第二大簇且全在 t9。

**Q5 这些比例在不同 task/seed 是否稳定?**
不稳。P 型 5/5 全在 t9;t5 零 P 且重采样最受益(+14pp);t9 重采样为负
贡献。seed 维度(每格 1-2 事件)无足够重复,不作结论。**持续谱是任务
依赖的**,跨任务外推需另测(呼应 §28 不跨 failure family 原则)。

**Q6 一次 failure 对未来 failure 的预测性多强?**
中等偏弱、且随连续失败次数急剧增强:单次失败后,下一次同动作尝试成功
率 h(2)=.33(高于无条件 q_same .30 一点点);但连续 3 次失败后第 4 次
合计 1/17,连续 7 次后 0/11。**一次失败本身信息量有限;失败
"连击数"才是强预测子。** 正式门下 ONE_SHOT 判 INCONCLUSIVE(median
q_policy .125 达标但 STRONG 占比 20.8%<25%,两条件缺一)。

**Q7 连续失败 1/2/4/8 次后,未来仍能 retry success 的概率?**
POLICY 臂:h(1)=.167 → h(2)=.350 → h(4)=.000(n=7)→ h(8)=.000(n=5)。
SAME 臂:.250 → .333 → .100(n=10)→ .000(n=6)。POLICY 臂 k≥4 全零;
SAME 臂 k=4 尚有 1/10,k=8 归零;两臂合并:第 4 次尝试 1/17,第 8 次 0/11。

**Q8 retry gain 第几次开始明显饱和?**
POLICY 增益 +29.2 / +25.0 / +8.3pp:第 4 次之后增益降一个量级,
但 8.3pp 落在预注册中间带(5-10pp)→ 正式判 INCONCLUSIVE;定性看
**主要收益在 k≤4 内兑现**(C_pol(4)=.708 已拿到 C_pol(8) 的 89%)。
SAME 臂增益不单调递减(+25/+12.5/+12.5),同样未过门。

**Q9 Stage Q 的 TRANSIENT_SUCCESS 是否复现?**
复现且幅度更大:pooled ACQ−STABLE gap SAME +34.4pp / POLICY +37.5pp
(Stage Q 为 +17~30pp;门 ≥15pp)。acquisition 层 ~65-70% 成功、
stable 层 ~30% —— "抓到过但没抓稳/没保住"是本 cohort 失败重试的主导
形态。

**Q10 复杂 recovery benchmark 是否应优先 POLICY_PERSISTENT@K failure states?**
是,且本 stage 已把它量出来:5 个 STRONG_PERSISTENT@8 事件(r143/r168/
r171/r181/r185,全 t9)= 16 次异同尝试全败、且重采样无增益(t9 q_pol
< q_same)。它们的 S_pre 已随 manifest 冻结、可 PREFIX_REPLAY 哈希级
重建 —— 是干净的可复现 benchmark 底物。对照:E 型 14 个事件对
simple retry 已足够友好,不宜作复杂 recovery 的区分性底物。
按 §36,本 stage 不构建该 benchmark,只交名单。

## 8. Relation to Recovery Literature

定位原则(spec §3):Stage R 提供的是 **complementary measurement axis**,
不称绝对 novelty。

- **RoboRecover**(temporary vs stable deviation 分类 + 恢复策略):其
  分类学的实证地基正是"失败持续性测量";Stage R 给出该分类在
  FALSE_GRASP 族上的受控量化(E/A/P/U 谱 + q 概率),为其 deviation
  判别提供先验,不替代其恢复方法;
- **Kintsugi-VLA**(repeated interventions + Wilson CI 报告):统计纪律
  一致(重复干预、区间报告);Stage R 补充"同状态哈希级重建 + 双臂
  对照"的 persistence 归因版本,而非其累积修复视角;
- **FLARE**(failure-language 条件恢复训练)/ **FAR**(偏好式失败适配):
  两者预设"失败后重试/适配有 headroom";Stage R 的 POLICY_PERSISTENT@8
  事件集正是 headroom 的直接度量 —— t9 上 5 个 16 试全败状态是这类方法
  的真 benchmark 候选(Q10),而 E 型事件(simple retry 已可解)区分度低;
- **ReTVL**(恢复型 VLA 评测):Stage R 的 q 分布 + h(k) 条件概率可作
  其评测的分层数据源(按 persistence 档位分层报告)。

以上均为互补关系陈述;Stage R 不训练、不适配、不建库。

## 9. Deviation 记录(prereg 附录 B 原文照录)

- **dev-r1-fix(2026-10-08 05:59)**:R1 首启(04:58)队列切分 bug ——
  `load_events` 的 `ord` 误用 ledger 行号(切分依据 included 序号),
  manifest 32 事件全标 R1_COHORT、8 个 DEV 事件误入队列。05:01 停止,
  多跑 4 trial(全在 DEV 事件上,不在最终 cohort)。处置:修 ord、
  manifest/rollouts 重新冻结、CPS 日志保留越轨 trial 作审计。cohort 24
  事件全部从零执行,判定不受影响。

除上述执行层 bug 外:配额恰好 32 无 deviation;R1 零 infra(远低于 §11
的 2% 暂停线);无事件触发 >50% infra flag。

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
