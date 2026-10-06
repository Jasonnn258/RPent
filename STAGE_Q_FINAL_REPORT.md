# STAGE Q FINAL REPORT — Why Does Retry Work?

生成:2026-10-06 | 阶段:Stage Q(Q0 + Q1;Q2 未触发) | 规范:用户
2026-10-05 32 节 spec | 预注册:`analysis/stageQ_prereg.md`(commit a894653,
deviation 见附录 C:dev-Q1/Q2/Q3)

**一句话主输出(§19)**:Retry gain 主要来自 **A. resampling from the same
original state**(PP stable 0.391、8/8 事件出现、占最优 cell 的 76%),
**B/C/D(state change / post-conditioned action / interaction)全部低于 15pp
门**;同时 **E. transient acquisition 机制性重大**(四 cell ACQ−STABLE gap
+17pp~+30pp,acquisition 只有 ~70% 能保住)。**MIXED:以 A 为主、叠加大量
瞬时成分;失败态改变带来小幅(+7.8pp)但未过门的余量。**

---

## 0. 数据流与样本(全链留痕)

| 阶段 | 规模 | 损耗 |
|---|---|---|
| collect(t3/t5/t9 × s76-120) | 92 episodes,FG 22 | 配额截断 22→20(collect 序) |
| freeze(同 boot 成对 S_pre/S_post) | manifest n=20 | 2 事件(qsnap_12/15)t0 重放三次皆成功 → INFRA_ABORT(dev-Q2) |
| factorial(16 cell × R_Q=2) | **13 完整(DEV 5 / TEST 8)** | 5 事件(qsnap_04/07/10/16/18)同因弃用 |

判定全部基于 **TEST n=8**(§18 逐快照表见 §5)。统计单位 = failure
event;candidate/replicate 为嵌重复(禁 N 膨胀);CI = bootstrap by
snapshot 10k。**所有 restored-state 因果拆分结论标 APPROXIMATE**(Q0 gate
已判 RESTORE-SENSITIVE DYNAMICS,§2)。

**全阶段 t0 重执行成功清单(H_QA 技能级证据,descriptive)**:守卫共
36 次记录"replayed t0 pick succeeded"(freeze 14 + factorial 22),分布在
**14/22 个事件**(合并两阶段计数:04×5、10×4、18×4、07×3、09×3、12×3、
15×3、16×3、08×2、11×2、03×1、06×1、14×1、17×1)。即:同 prompt、同
pre-state、Pi0.5 重采样重执行原失败技能即成功——这些从未进入任何 cell,
但构成"相当一部分失败只是坏样本"的最直接证据(64% 的事件至少出现过一次
翻转;其中 7 个事件在 3 次尝试内复现了失败而存活进 final 13,另 7 个
未能复现被弃)。

## 1. Q0 摘要(资格与审计)

- **Q0-A/B 状态审计**(11 好事件):失败痕迹是连续谱——tgt_dxy 中位
  0.035m、最大 0.426m(把物体推飞),|dz|>3cm 4/11;EEF 位移 2.9-44.7cm
  (Q1 manifest 同量级)。不存在"统一的失败态"。
- **Q0-C restore gate**:LIVE vs RESTORED 恢复率无偏(ACQ Δ=0.036、
  STABLE Δ=0.036,均 ≤10pp),但 transition-class 配对一致率
  **10/14 = 0.769 < 0.90** → **RESTORE-SENSITIVE DYNAMICS**
  (`stageQ0_decision.md`)。后果:Q1 拆分只能标 APPROXIMATE;不可解释
  部分按 §12 记 UNOBSERVED / CONTACT-HISTORY DYNAMICS MAY CONTRIBUTE。
- TRANSIENT 现象在 Q0 已现(psnap_12:acq 2/2 stable 0/2),Q1 TEST 证实。

## 2. 四 cell 与三效应(TEST n=8)

| cell(源|执行态) | ACQUISITION | STABLE | ACQ−STABLE |
|---|---|---|---|
| PP(pre@S_pre) | 0.688 | **0.391** | +0.297 |
| PO(pre@S_post) | 0.750 | **0.578**(最高) | +0.172 |
| OP(post@S_pre) | 0.828 | 0.547 | +0.281 |
| OO(post@S_post) | 0.766 | 0.516 | +0.250 |

| 效应 | STABLE(TEST) | CI | LOO | ACQ(陪报) | 门 | 判定 |
|---|---|---|---|---|---|---|
| EXECUTION-STATE(H_QB) | +0.078 | [−0.062,+0.227] | +0.036 | +0.000 | ≥15pp 且 LOO≥15pp | 未过 |
| CANDIDATE-SOURCE(H_QC) | +0.047 | [−0.070,+0.164] | +0.009 | +0.078 | 同上 | 未过 |
| INTERACTION(H_QD) | **−0.219** | [−0.484,+0.062] | −0.321 | −0.125 | ≥15pp 且 LOO>0 | 未过(方向为负) |

DEV 陪报(n=5):exec +0.325 / cand +0.125 / int −0.300——方差大、与
TEST 不同号,小样本不解释。

## 3. §30 Q1-Q10 逐答

**Q1. Stage P 的 retry success 有多少在 STABLE 契约下仍成立?**
约 2/3:TEST 四 cell 合并的 acquisition→stable 保持率 ≈0.70(13 事件全
cell 同口径),即宽契约下的"恢复"约 1/3 是瞬时抓取(抓起又掉/松)。
PP 口径:0.688 acquisition 中能保住 0.391(57%)。

**Q2. 不经历失败态、仅重采 Pi0.5,能否稳定恢复?**
能。PP cell(restore 到 S_pre,只用 S_pre obs 采的候选)= ACQ 0.688 /
STABLE 0.391,且 stable>0 在 **8/8** TEST 事件出现(prereg 出现率门
≥70% 以 1.000 通过)。失败态改变不是 retry success 的必要条件。

**Q3. 同一 frozen candidate 在 S_post 是否更易成功?**
小幅、未过门:exec-state effect STABLE +7.8pp(CI 含 0,LOO +3.6pp<
15pp);ACQ 口径 +0.0pp。方向一致(PO 0.578 为四 cell 最高)但证据不足
以声称。**APPROXIMATE**(restore-sensitive)。

**Q4. S_post 生成的 candidate 是否系统性更优?**
否。cand-source effect STABLE +4.7pp(CI 含 0)。值得注意的是 OO(0.516)
< PO(0.578):post 态生成的候选在 post 态执行反而不如 pre 态生成的候选
(负交互的来源)。

**Q5. 是否存在显著 state×candidate interaction?**
形式检验:不显著且**方向为负**(−21.9pp,LOO −32.1pp)。机制上:A_post
偏向"从失败后姿态补救",在 S_pre 上执行(OP 0.547)并不差,但在 S_post
上(OO 0.516)没有叠加优势——两因素不互补,近似可加甚至互斥。

**Q6. 第一次失败有没有把物理世界变成更易恢复的状态?**
没有可声称的证据:+7.8pp(STABLE)未过 15pp 门,ACQ 口径 0.0pp;且
按 §12 措辞,即便为真也只能归因 observable state(APPROXIMATE)+
unobserved/contact-history dynamics may contribute。逐事件看,EEF 位移
最大的事件(qsnap_19,44.7cm)post 态反而 PO=0.00 stable——失败痕迹
不是单向"变好"。

**Q7. 优势来自 robot pose / object pose / interaction / hidden dynamics?**
**NOT TESTED**:Q2 robot-vs-object 分解的触发条件(exec-state ≥15pp 或
H_QB SUPPORTED)未满足 → 按预注册 Q2 不运行。hidden dynamics:rate 级
LIVE≈RESTORED(Δ≤3.6pp)不支持;class 级 77% 一致率不足仅作为测量保真
度限制(APPROXIMATE 标签的依据),不构成机制证据。

**Q8. Stage P 宽 recovery 有多少只是 transient acquisition?**
机制性重大:TRANSIENT_GAP(ACQ−STABLE)四 cell 全部 ≥ +17pp(PP +29.7、
PO +17.2、OP +28.1、OO +25.0,门 ≥15pp)。Stage P 的 retry ceiling 里
相当一部分(约 1/3)是"抓起但保不住"。

**Q9. "retry works" 最简单、最有证据的机制解释?**
**重采样主导 + 高瞬时率**(MIXED):失败多为坏样本——同状态重采候选就有
39% stable 恢复(PP,8/8 事件);技能级更极端(36 次同命令重执行成功)。
失败态改变(+7.8pp)与 post 条件生成(+4.7pp)为小幅未过门余量;瞬时
成分说明"成功"需要用 hold-through 契约重新审视。所有 restored 拆分
APPROXIMATE。

**Q10. 是否有必要增加更复杂的 recovery intelligence?**
现有证据链不支持:重采样本身已拿到大部分收益(本阶段 + Stage O
H_A、Stage P P1 selection FAIL、P2 天花板);state/action 条件化增益
低于门;瞬时问题的对策是测量契约(已在本阶段建立)而非 intelligence。
按 §32 Hard STOP,不启动任何 recovery redesign。

## 4. 六判定(§31,独立输出;TEST n=8,门均为冻结值)

| 判定 | 结论 |
|---|---|
| **STOCHASTIC_RESAMPLING** | **NOT_SUPPORTED**(按冻结合取门:出现率 1.000 通过,但 \|OO−PP\|=0.125 > 0.10 等价边际差 2.5pp 未过;注意:PP 8/8 出现 + 36 次技能级重执行成功构成强机制证据,仅"完全等价"形式未获支持——按门如实判,不作 PARTIAL 变通) |
| **PHYSICAL_PRECONDITIONING** | **NOT_SUPPORTED**(+0.078 [−0.062,+0.227],LOO +0.036;ACQ +0.000) |
| **POST_STATE_CONDITIONING** | **NOT_SUPPORTED**(+0.047 [−0.070,+0.164];ACQ +0.078 同样未过) |
| **STATE_ACTION_INTERACTION** | **NOT_SUPPORTED**(−0.219 [−0.484,+0.062],LOO −0.321;方向为负) |
| **TRANSIENT_SUCCESS** | **SUPPORTED**(四 cell gap +17~+30pp 全部 ≥15pp;hold ratio ≈0.70) |
| **HIDDEN_DYNAMICS_EFFECT** | **NOT_SUPPORTED**(rate 级 LIVE≈RESTORED,Δ≤3.6pp≤10pp 门;class 级 77%<90% 仅作为 APPROXIMATE 措辞依据,非机制证据) |

## 5. 逐快照表(§18;PP/PO/OP/OO = acq/stable;cand-var = cell 内 4 候选
stable 率极差均值;eefΔ = 失败 pick 造成的 EEF 位移 cm)

| sid | split | t0 | eefΔ | PP | PO | OP | OO | cand-var |
|---|---|---|---|---|---|---|---|---|
| qsnap_00 | DEV | 3 | 5.4 | .38/.25 | .62/.50 | .25/.12 | .62/.25 | .62 |
| qsnap_01 | TEST | 3 | 19.0 | .38/.25 | .88/.88 | .88/.88 | .75/.75 | .50 |
| qsnap_02 | DEV | 3 | 3.1 | .25/.25 | 1.0/.88 | 1.0/1.0 | 1.0/1.0 | .38 |
| qsnap_03 | TEST | 6 | 20.9 | .50/.38 | .75/.75 | 1.0/.75 | 1.0/1.0 | .50 |
| qsnap_05 | TEST | 3 | 9.3 | .75/.62 | 1.0/.88 | 1.0/.88 | 1.0/.88 | .50 |
| qsnap_06 | DEV | 3 | 2.9 | .50/.50 | .88/.88 | 1.0/1.0 | 1.0/1.0 | .38 |
| qsnap_08 | DEV | 4 | 7.8 | .88/.38 | .75/.75 | .88/.62 | 1.0/1.0 | .75 |
| qsnap_09 | TEST | 3 | 13.1 | .62/.25 | 1.0/.50 | .88/.38 | .75/.00 | .62 |
| qsnap_11 | TEST | 2 | 41.1 | 1.0/.50 | 1.0/1.0 | 1.0/.75 | 1.0/1.0 | .38 |
| qsnap_13 | TEST | 3 | 10.8 | .25/.25 | .50/.12 | .38/.12 | .75/.25 | .50 |
| qsnap_14 | DEV | 3 | 25.6 | .88/.25 | 1.0/1.0 | .88/.25 | .62/.62 | .50 |
| qsnap_17 | TEST | 3 | 11.7 | 1.0/.38 | .75/.50 | .62/.50 | .62/.12 | .88 |
| qsnap_19 | TEST | 5 | 44.7 | 1.0/.50 | .12/.00 | .88/.12 | .25/.12 | .50 |

候选内方差大(cand-var 0.38-0.88):同一状态下采的 4 个候选 stable 率
极差常达 0.5-0.88——重采样既有高产出也有废样本,这与"重采样主导"
一致(也再次印证 Stage P P1:within-state candidate diversity 对
selection 不足,但对 retry 本身足够)。

## 6. 限制(dev-Q2 全文见 prereg 附录 C)

1. **存活偏差朝 H_QA 不利方向**:14/22 事件出现过至少一次 t0 重执行成功
   (§0 清单),其中 7 个在 3 次尝试内未能复现失败而被弃用;最终 13 事件
   = "失败可在 boot 级大致复现"的子群。H_QA 的 candidate 级估计(PP 等)
   只在该子群内解释;技能级 36 次成功在全群观测、不受此限。
2. **TEST n=8**(规划 ~10):CI 宽,±10-25pp 的差异不可分辨——等价边际
   差 2.5pp 的判定对此敏感,已如实标注。
3. **APPROXIMATE 措辞约束**(restore-sensitive):禁称精确 physics
   counterfactual。
4. §14 infra 门(>2% 暂停解释):5/18 弃用为事件级随机性(守卫按 §3
   冻结逻辑工作),非 instrumentation 失败;判定前无协议改动。

## 7. 产物(§29)

- 预注册/deviation:`analysis/stageQ_prereg.md`
- Q0:`stageQ_state_delta_audit.csv`、`stageQ_live_restore_audit.csv`、
  `stageQ0_decision.md`
- Q1:`stageQ_collect_ledger.csv`、`stageQ_split_manifest.csv`、
  `stageQ_candidates.jsonl`、`stageQ_factorial_rollouts.csv`、
  `stageQ_acquisition_stable.csv`、`stageQ_factorial_effects.csv`、
  `stageQ1_results.md`、`stageQ1_decision.md`
- 代码:`scripts/stageQ_collect.py`、`stageQ_freeze.py`、
  `stageQ_rt.py`、`stageQ0.py`、`stageQ1_factorial.py`
- 本报告:`STAGE_Q_FINAL_REPORT.md`

## 8. Hard STOP(§32 逐字执行)

Stage Q 到此停止。不启动:retry controller redesign / adaptive retry
count / verifier / Best-of-K / Planner fallback / Graph / World Model /
new perception / SFT / OPD / RL / simulator snapshot redesign。Q2 未
触发不运行。如需改动上述任何一项,另立阶段、另行预注册。
