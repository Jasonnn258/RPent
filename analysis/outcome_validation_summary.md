# OVP-M 实验总结(Outcome-Validated Procedural Memory)

**日期**: 2026-09-08 | **结论一句话**: B 臂(判定注入)在开发任务上按预注册判据成立
(t7 stall 治愈、t9 升级生效、轮数变省),但 **held-out 上不迁移**:A 96.7% vs B 83.3%,
配对 4:0 全是回退,机制是 OC-PICK 契约"紧握即通过"旁路在 heldout 几何上误报;
C 臂(事件触发双模式)在 dev 上双判据失败,**不成立**(详见 `reasoning_timing_summary.md`)。

## 实验设置

- **假设**: 记忆条目在线激活 `Action → Expected Outcome → Verify → Commit/Recover`,
  能修复决策 timing 病(该 commit 不 commit / 该 recover 不 recover)。
- **三臂**: A = SM1 结构记忆(对照) | B = A + OVP-M 判定注入(契约 v2,零额外轮数) |
  C = B + 事件触发 COMMIT/REASON 双模式(仅 B 成立后跑,后判不成立)。
- **配对**: 同 (task, seed, repeat),planner = glm-5.3-flash(§1 sanity 预注册选档:
  glm-5.3 9/30=30% vs flash 16/30=53%,flash 失败形态保真且 SR 在可用区间)。
  VLA = Pi0.5 + SAM3(已验证 checkpoint)。verification 只用合法 observation/termination,
  **无 benchmark GT**。禁 rerun-until-success(基建重试 ≤3,全记录)。
- **网格**: dev t0/t7/t9 × s1-10 × r1-3(每臂 90);heldout t1/t4/t8 × s1-10 × r1(每臂 30)。

## 四阶段结果总表

| 阶段 | 网格 | A (SM1) | B (A+OVP-M) | C (B+双模式) | 配对翻转 |
|---|---|---|---|---|---|
| §1 sanity vanilla | t0/t7/t9 × s1-10 | glm-5.3: 9/30 (30%) | flash: 16/30 (53%) | — | 选档 flash |
| §2/3 dev | 90/臂 | 72/90 (80.0%) | **77/90 (85.6%)** | — | B 救 15 / 回退 10 |
| §2/3 devC | 90 | — | 77/90 (85.6%) | 34/90 (37.8%) | C 败 48 / 赢 5 |
| §6 heldout | 30/臂 | **29/30 (96.7%)** | 25/30 (83.3%) | (C 依预注册门淘汰,未跑) | B 回退 4 / 救 0 |

## B 臂:dev 成立 → heldout 反转

**dev(契约的来源任务,t0/t7/t9)**: 增益集中在预注册的两个机制上——
- t7 23/30→27/30:place_stall(结果已满足仍反复验证)被 MATCHED→commit 提示治愈;
- t9 21/30→23/30:release 不达标 → MISMATCH 升级建议(pi0_doubled)生效;
- t0 28/30→27/30(持平,本就近天花板)。
- 效率: B 决策轮数中位更少(commit discipline 生效)。
- **统计诚实**: 15:10 翻转的符号检验 p≈0.42,单看 SR 差(+5.6pp)不显著;
  成立判定靠的是预注册复合判据(机制改善 + 无系统性恶化),不是 SR 单指标。

**heldout(未见任务 t1/t4/t8)**: 全面回退。
- 每任务: t1 90%→80%,t4 **100%→70%**,t8 100%=100%。A 在 heldout 近天花板(96.7%),
  B 无增益空间,任何误判只减分。
- 4 个回退逐例核验(`structured_metrics.json` ovpm.verdicts):
  - **3/4 命中同一误报**: OC-PICK 契约的"紧握即通过"旁路 —— `success=false`、
    夹爪紧(min_gripper_opening<0.03)但 `peak_lift≈0`(对象被夹住却没抬起)被判
    **MATCHED**(虚假安心)。heldout 几何(碗靠饼干盒/柜顶)下"夹得紧"≠"抓得起",
    虚假 MATCHED 把 agent 锁进重抓循环,2 个烧完 40 轮、1 个诚实认输。
  - 1/4(t4 s3): release MATCHED 但环境谓词不触发,反复修正后诚实 finish(failure)——
    契约没给错信号,是执行落点差半步的普通失败(A 同 seed 一次成功)。
- 效率面保留: both-success 25 对里 B 轮数更少 15/25(中位 −3 轮);墙钟被 API 延迟波
  混杂,不比较。
- 符号检验 4:0,p=0.125——方向一致且机制可溯,但 n 小,单独看不结论。

## 跨阶段机理画像

1. **契约阈值是从 t0/t7/t9 的失败诊断里标定的**,在这三个任务上方向正确;
   唯一被任务限定过的契约(OC-RELEASE-T9,只对 t9 生效)从未误报——
   **误报的全部是未限定的一般契约(OC-PICK)**。
2. 一般化失败模式:"紧握⇒已抓稳"在自由 standing 物体上近似成立,在贴靠/嵌套几何上
   不成立。判定注入把一个"开发集上的相关"当成了"物理因果"注入,放大了错误。
3. B 在 dev 上的两类增益(stall→commit、mismatch→升级)在 heldout 上没有对应病症
   可治(A 的 stall 率在 t1/t4/t8 上本来就低),只有副作用暴露。
4. C 臂的教训同源: 把判断从完整推理上下文剥离(交给无感知的 commit executor),
   会系统性丢掉"知道自己不知道什么"。

## 管线事故与基建变更(诚实记录)

- **devC v1(已废弃)**: `Thinking(high)`→budget 16384 > max_tokens 8192,GLM 端点不校验
  → 零内容截断 → 41% episode 误判 policy_fail。修复:max_tokens→24576 + 改判 infra_crash;
  90 行污染数据已删(目录留盘作审计)。
- **heldout 中途(2026-09-08 10:52)**: GLM 上午延迟 ~87-150s/轮(校准时 ~40-60s),
  2400s planner 时钟杀死健康慢速 episode(median 87s/轮的那集死时正在跑第 26 轮)。
  修复:PLANNER_TIMEOUT_S 2400→3600 + 重启调度器(重试计数清零,13 集重跑)。
  科学对照变量(40 轮上限/提示/方法)未动;两臂在变更前后各有分布,无单臂偏置。
  最终 60 行全部是自然结束(2 个 policy_fail 之前、4 个之后的慢波窗口内两臂均有成功)。
- **infra 重试**: heldout 全程 20+ 次 infra_timeout 均自动重试后自然结束;
  最终 CSV 零 infra 行,零 token-limit 行。

## 结论与下一步方向(未实施,记录备查)

1. **B 的当前形态(general 契约 + 阈值判定)不迁移**。改进方向:
   - OC-PICK 判定加必要条件 `peak_lift_m > 阈值`(夹紧且抬起才算 MATCHED),
     "紧握"只作 UNCERTAIN;
   - 契约按几何先验分类(自由物体 vs 贴靠/嵌套)或任务限定,像 OC-RELEASE-T9 一样;
   - heldout 上 A 近天花板 → 未来 heldout 网格应选基线非饱和的任务。
2. **C 的修订方向**见 `reasoning_timing_summary.md`(commit 资格排除认知性目标;
   或 commit executor 保留最小感知集)。
3. 效率收益(B 中位 −3 轮)与 t7/t9 机制增益是本实验的正结果,值得在修契约后复测。

## 数据索引

- 明细: `analysis/outcome_validation_runs.csv`(60+180+90+60 行,37 列)
- 配对: `analysis/outcome_validation_pairs.csv`(dev 80 对)/ `analysis/outcome_validation_pairs_heldout.csv`(30 对)
- C 判定: `analysis/reasoning_timing_summary.md`
- 每 episode: `logs/ovpm_exp/<ts>_<tier>_<cond>_*`(`run.log`/`structured_metrics.json`/`states.json`)
