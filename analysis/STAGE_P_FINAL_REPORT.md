# STAGE_P_FINAL_REPORT — Sample, Identify, Select, Abstain(FALSE_GRASP)

生成:2026-10-05 | 分支:research/pre-ovpm-20260905
预注册:analysis/stageP_prereg.md(confirmatory 运行前冻结并 commit;
偏离只追加,dev-P1/dev-P2 见 prereg 附录 C)
数据:stageP_split_manifest.csv(24 可用,sha256=851ded14…)及 §13 产物清单全件

---

## 0. 判定总览(§38,四项独立,禁模糊总结)

| 判定 | 结论 | 依据 |
|---|---|---|
| CANDIDATE_INTERFACE | **QUALIFIED** | P0 PASS:transition-class agreement 48/48=1.0000、success/failure flags 46/48=0.9583(≥95% 双门,16 candidate ≥12) |
| SUPPORT_DIVERSITY | **NOT_SUPPORTED** | P1 FAIL:TEST Oracle@8−Oracle@1 = 0.100 < 0.15(另两门 sup=1.000、mixed=0.600 均过) |
| PRE_EXECUTION_SELECTION | **NOT_TESTED** | P1 FAIL 门禁封死,禁训 verifier(P2 未运行) |
| SELECTIVE_EXECUTION | **NOT_TESTED** | 同上(P3 未运行) |

**§39 Hard STOP(触发分支:P1 FAIL)**:

> REPEATED ROLLOUT SUPPORT EXISTS, BUT WITHIN-STATE CANDIDATE DIVERSITY IS
> INSUFFICIENT FOR SELECTION STUDY。

Stage P 到此 STOP。按 §39 禁止自动开展:verifier scaling / VLM verifier /
temporal transformer / World Model / negative prompting / Pi0.5 training / SFT /
OPD / RL / fallback Planner / Graph / recovery skill learning。下一条研究线
由用户决定,本报告不附建议性自动续跑。

---

## 1. P0 — Candidate Interface Qualification(PASS)

- **接口定义(冻结)**:candidate = Pi0.5 在失败态观测(`_vlm_chunk` 同款
  prompt 覆盖 + `extra_view_images=None`)上、`predict_action_batch(mode="eval")`
  采出的**首个 [5,7] action chunk**;纯推理、执行前可冻结为 JSON、
  `env.chunk_step` 可重放、执行 chunk 本身零模型调用。
- **一致性(8 Stage-O FG 快照 × 2 candidate × 3 replay)**:transition-class
  48/48 = 1.0000;success/failure flags 46/48 = 0.9583;0 infra。
- **P0 门**:双 agreement ≥95% ∧ n_cand ≥12 → PASS(2026-10-03,
  commit 4ca5f03)。
- **重要发现( dev-P1,指纹证伪)**:同一 frozen chunk 同一 restore 态重放
  **非逐位** —— 轨迹呈 ≤7.8e-4 m 的系统性单调漂移(89/90 增量同号)。
  机制假说:flat state 不含 MuJoCo warm-start/接触历史,J0 的"restore 逐位
  精确"只覆盖读回校验,不覆盖重执行动力学。由此追加冻结约束:**P2 特征
  禁依赖 ~1e-3 m 邻域内的单一阈值 flag**(该约束随 P1 FAIL 未被消费)。
- **gate 公式修正(dev-P1,commit c311e18)**:runner 曾把指纹折进 pass,
  严于预注册文本;按 prereg §5 修正为"双 agreement 定 pass、指纹另报",
  FAIL→PASS 重裁全过程留痕,CSV 零改动。

## 2. P1 — Candidate Support Geometry(FAIL)

### 2.1 数据集(§6,dev-P2 扩格后)

- 采集:{t3,t5,t9} × seeds 29-75 = 141 格,顺序扫到 28 FG 上限停止;
  实跑 102 集(8.2h),出 30 FG(29.4%;t3 21% / t5 30% / t9 6/8),
  零 infra 零 EXC;RPS 一律 logged-excluded。
- 配额纪律:3-worker 并发窗口在途全中致 30>28,按冻结上限确定性截断
  collect 序前 28(丢 t9s35/t9s36,行留 ledger;拒绝事后回填)。
- 物化:28 → **24 可用**(4 个被 dev-O5 守卫拒绝:重放时 t0 pick 成功,
  事件不可复现;psnap_03/17/22/23 记 INFRA_ABORT);DEV 13 / TEST 11
  (collect 序奇偶划分,SPLIT_SEED=20261003 仅记录未消费);manifest 头
  sha256 冻结。
- 执行:22 快照各连续采 8 candidate(同一 failure-state obs、执行前落盘
  冻结、断点只复用不补采)→ 每 candidate restore(S)→chunk→S_j→
  3 次独立 restore(S_j)+ 续跑(R_CONT=3,预算 24 chunk 含 candidate)。
  boot infra ×3:psnap_01(TEST)、psnap_18(DEV)→ 实测 TEST n=10、DEV n=12,
  176 条 valid outcome + 2 条 boot infra 行。

### 2.2 结果(TEST = confirmatory)

| 指标 | TEST(n=10) | Wilson 95% CI | DEV(n=12,sanity) |
|---|---|---|---|
| Oracle@1 | 0.900 | [0.596, 0.982] | 0.750 |
| Oracle@2 | 0.900 | [0.596, 0.982] | 0.833 |
| Oracle@4 | 1.000 | [0.722, 1.000] | 0.917 |
| Oracle@8 | 1.000 | [0.722, 1.000] | 1.000 |
| SUPPORTED(K=8) | 1.000 | [0.722, 1.000] | 1.000 |
| MIXED | 0.600 | [0.313, 0.832] | 0.500 |

标签分布(176 valid candidate):RECOVERY 140(79.5%)/ NO_EFFECT 26
(14.8%)/ HARM 10(5.7%)。

门判定(§7/§15):Δ = 0.100 < 0.15 → **FAIL**;SUPPORTED = 1.000 ≥ 0.50 →
PASS;MIXED = 0.600 ≥ 0.30 → PASS。一项未过即 P1 FAIL。

### 2.3 机制:天花板效应

- TEST 10 个快照中 **9 个首候选即恢复**(first_rec_idx=1);唯一例外
  psnap_25:n_rec=1/8、first_rec=3 —— TEST 侧唯一实质多样性证据。
- 即 TEST Oracle 增益全部来自这 1 个快照(+10pp);DEV 同构(O@1=.750,
  3 个非首中:psnap_02 first_rec=2/n_rec=1、psnap_14 first_rec=3/n_rec=6、
  psnap_26 first_rec=5/n_rec=2)。
- 4/10 TEST 快照 8/8 全 RECOVERY(mixed=0 的另一面):状态不是
  "需要挑出好候选",而是"几乎任何候选都行"。

---

## 3. §37 必答 Q1-Q13

**Q1. Stage O 的"重复采样恢复"能否表示成 pre-execution candidate
selection 问题?**
接口层面能(P0 PASS:candidate 可定义、可冻结、outcome 类可复现);
实质层面**不能**——P1 显示失败态支持过于普遍(首候选恢复率 90% TEST),
"选择"在该测量粒度上近乎不存在。Stage O 的 stochastic recovery 更像
"重试即中"而非"挑出好的"。

**Q2. 当前 Pi0.5 的 candidate 到底是什么粒度?**
首个 [5,7] action chunk(≈0.5s 动作段,执行前一次推理产出);
不是完整 trajectory,也不是单步。

**Q3. 同一个 frozen candidate 是否具有稳定的 physical outcome?**
类级稳定:transition-class 100%、flags 95.8%。数值级不逐位:亚毫米
(≤7.8e-4 m)单调漂移,机制 = restore 不携带 warm-start(dev-P1)。

**Q4. 多采样是否真的提高 same-state Oracle@K?**
提高,但天花板:TEST .900→1.000(+10pp,门需 +15pp);DEV .750→1.000。
增益全部来自 1/10(TEST)~ 3/12(DEV)个非 easy 快照。

**Q5. sampling gain 来自普遍的 within-state diversity,还是仅来自少数
easy snapshots?**
都不准确——正确读法是**支持本身普遍、多样性稀缺**:SUPPORTED=100%
(普遍),但 within-state 差异只在 psnap_25 一类快照上存在(TEST 1/10)。
门设计针对的正是后者,故 FAIL。

**Q6. 有效 recovery candidate 执行前是否可识别?**
NOT TESTED(P1 FAIL 禁训 verifier)。描述性旁证:非 RECOVERY 候选
20.5%(NO_EFFECT 14.8% + HARM 5.7%),若可识别其增益上限 ≤ Oracle 增益
= 10pp(TEST),低于门值——即使完美 verifier 也无法把本门做过门。

**Q7. 哪类信息最有用(candidate-only / state+candidate /
history+state+candidate)?**
NOT TESTED(P2 三特征集未运行)。

**Q8. Verifier 能捕获多少 Oracle sampling gain?**
NOT TESTED。理论上限 = 10pp(TEST)。

**Q9. Verifier 是否会把 HARM candidate 排到前面?**
NOT TESTED。HARM 基率 5.7%(10/176)是 P2 原计划的安全检查点。

**Q10. 强制 Best-of-K 是否会出现 best of bad options?**
NOT TESTED(P3 未运行)。P1 侧无此形态:K=8 内 SUPPORTED=100%,
不存在全坏快照。

**Q11. Abstention 能否减少 forced bad execution?**
NOT TESTED(P3 未运行)。

**Q12. Sequential sampling 平均需要多少 candidate 才能得到可执行动作?**
描述性(P1 数据,无 verifier 参与):TEST first_rec_idx 均值 = 1.2
(9×1 + 1×3);DEV = 1.583(9×1 + 2 + 3 + 5)。K=8 内 100% 命中 →
顺序采样的期望代价极低,与"重试即中"画像一致。

**Q13. 当前证据支持哪条线:test-time sampling / +verifier /
select-or-abstain / policy support exists but cannot yet be exploited?**
**支持 plain test-time sampling**:单次采样恢复率已达 90%(TEST 首候选),
与 Stage O 的 H_A(sampling support)一致且更强 —— 在本测量契约下,
sampling 几乎免费拿到全部可用增益。"+verifier" 与 "select-or-abstain"
无增量空间(Oracle 上限 +10pp)也未测试;不是 "cannot yet be exploited",
而是**无可 exploit 的头寸**。

---

## 4. 局限(诚实记录,不改判定)

1. **RECOVERY 契约敏感**:P1 标签为"任一测量点达标"(prereg §4 冻结,
   比 Stage O 的仅终态更敏感)。Stage O 单次重试的终态恢复率 ≈36.7%,
   本 Stage 首候选任一点恢复率 90% —— 天花板部分由契约宽度贡献。
   契约在 confirmatory 前冻结,事后更换即 post-hoc,故判定维持 FAIL;
   若未来用户另立阶段改用终态契约重估 headroom,属新预注册决策,本
   Stage 不自动执行。
2. **boot infra 2 例**(psnap_01 TEST / psnap_18 DEV,各重试 3 次):
   按 §35 记 infra 不入指标;TEST n=10 略低于预定 11。方向上 psnap_01
   缺席只会让 Δ 更难过门(若其也是首中,Δ 恒 0.100;若非首中,Δ 更高)
   —— 不构成 FAIL 的反向风险。
3. **单一平台/单一 policy**(libero_spatial 3 task × Pi0.5 + Full Planner
   失败态):结论外推以同分布为限。

## 5. 偏离与 infra 总账

| 编号 | 内容 | 处置 |
|---|---|---|
| dev-P1 | 指纹证伪(亚毫米单调漂移)+ P0 gate 公式修正 + P2 特征冻结约束 | c311e18,prereg 附录 C |
| dev-P2 | grid 54→141 格(用户 2026-10-04 批准)、28 FG 停止规则、预算勘误、t9 勘误 | ca03df8 起,prereg 附录 C |
| infra | 采物化 4×dev-O5 拒绝、P1 执行 2×boot infra、采集 0 | 全记 manifest/CSV,不入指标 |

## 6. 产物与 commit

代码:e8a118f(stageP_rt + P0 replay)、c311e18(P0 gate 修正)、ca03df8
(collect)、4b224b0(freeze)、db1a932(配额截断)、5d65763(manifest 冻结)、
661283a(geometry runner);数据与裁决:b610210(P1 五件套);本报告
commit 见 git log。全部**未 push**(待用户指示)。
审计明细 logs/stageP_geometry/checkpoints.jsonl 不随 commit(原始日志纪律)。
