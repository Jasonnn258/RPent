# Stage O 终报 — Recovery Source Audit(2026-10-03)

**研究问题**:同类 failure state 下局部 recovery controller(N1 宏)几乎无法恢复,
但 Full Planner 往往最终能恢复——这份能力到底来自哪里?

预注册:`analysis/stageO_prereg.md`(冻结 commit 4eb3de5;calibration 附录 B
K_ROLLOUT=8)。规范 39 节原文 `/workspace/yjx/tmp/stageO_spec_full.txt`。
本报告只使用 confirmatory 数据(O-B 12 快照 ladder,516 行),O-A 离线审计
(commit 63041e5)仅作背景。

---

## 0. 一段话结论

**Full Planner 的恢复能力主要不来自"规划",而来自两件更便宜的事:**
在抓空族(FALSE_GRASP)来自 **Pi0.5 采样本身的重试支撑**(同一条命令重发,
36.7% 单次命中率、5/12 快照达标,H_A SUPPORTED);在放置卡住族
(RELEASE_PREDICATE_STALL)其实**根本不需要 planner——N1 局部宏就能救回
84.4%**。换 prompt(O2 oracle conditioning)零命中;冻结成功序列(O3)个别
快照完美但泛化差;让 planner 自由续跑(O4)不优于 O3、贵 30 倍墙钟、且 72 次
rollout 里 69 次一次技能都不调用(预算全部耗在感知/读记忆上)。

## 1. 测量设置(全部冻结件,零事后改动)

- 12 个新 failure 快照(8 FG + 4 RPS),fresh env 重放 prefix → restore 校验
  (boot 内读回逐位 ==0)+ dev-O5 事件复现守卫(重放必须仍是失败态)。
- 5 臂:O0 = N1 局部宏逐字移植;O1 = 最后一条 Pi0.5 命令逐字重采 ×16;
  O2 = 同 O1 但 prompt 换成 reference 成功轨迹同族调用;O3 = 逐字回放 reference
  冻结动作序列;O4 = Full Planner 续跑(会 replan)。K_ROLLOUT=8,O1/O2 各 16。
- reference trace(K_REF=3,成功即停):7/12 可用;UNAVAILABLE 2(04/06 三次
  全败);INFRA_ABORT 3(01/03 事件不可复现、11 重放提前终止)。
- 结局双契约:TASK_RECOVERY(族特定物理契约)与 POLICY_REENTRY(可观测
  重入契约),RECOVERY_PRESENT := successes ≥ max(2, ceil(0.25n)) 且 ≥25%。
- 墙钟:2026-10-02 13:59 – 22:23(主跑 480 行)+ 2026-10-03 09:49 – 10:07
  (dev-O6 补测 36 行)。全程并发 ≤2,开发机无事故。

## 2. 主表:族 × 臂 任务恢复率(successes/valid)

| 族 | O0 N1宏 | O1 重采 | O2 换prompt | O3 冻结序列 | O4 planner续跑 |
|---|---|---|---|---|---|
| FALSE_GRASP(8 快照) | **0/64** | **47/128(36.7%)** | 0/16 | 11/32(34.4%) | 7/56(12.5%) |
| RELEASE_PREDICATE_STALL(4 快照†) | **27/32(84.4%)** | 21/64(32.8%) | 0/16 | 0/8 | 1/16(6.3%) |

† RPS 族 n=4 **低于预注册族下限 5** → §3 INSUFFICIENT_SNAPSHOTS(RPS)已于
manifest 冻结时上报(commit c57ebbc,grid 扫尽、不补采);RPS 侧全部结论按
受限证据处理。

**族分裂是本次最清晰的结构性发现**:FG 上局部宏完全无效而采样是主力;
RPS 上局部宏几乎全解而 planner 系的一切(O3/O4)无增益。Δ01 配对从主跑的
+0.263(8正/1负)在补测 RPS 缺格后回落到 **+0.073(8正/3负,3 个负值全是
RPS)**——"O1 优于 O0"是 FG 侧陈述,不是全域陈述。

## 3. First-source 分布(§28;主判 = TASK_RECOVERY 契约版)

| 标签 | task 版 | reentry 版 | 并集版 |
|---|---|---|---|
| O1_POLICY_SUPPORT | **5**(00,01,06,08,10) | 1(02) | 6 |
| O3_FIXED_SEQUENCE | 1(07) | 0 | 1 |
| O4_REPLANNING | 1(02) | 0 | 1(09) |
| O4_REPLANNING_BELOW_UNTESTED | 1(03) | 1(03) | 1 |
| NO_SOURCE_FOUND | 2(05,09) | 6 | 1 |
| REFERENCE_UNAVAILABLE | 2(04,06) | 4 | 2 |

注:O0 不在标签集内(§10 冻结阶梯从 O1 起标);RPS 4/4 快照 O0 达标这一事实
由 §2 主表与 Δ 配对承载,不进 first-source 标签。

## 4. 五假设独立判定(§38;判定代码 = 冻结 analyzer,零 LLM)

| 假设 | 判定 | 依据 |
|---|---|---|
| **H_A POLICY SUPPORT** | **SUPPORTED** | O1 达标 5 快照(≥3);Δ01 正 8 / 负 3(负全在 RPS,见 §2) |
| H_B CONDITIONING | NOT SUPPORTED | O1 未达标而 O2 达标:0 个;O2 合计 0/32 |
| H_C FIXED SEQUENCE | INCONCLUSIVE | O2 不足而 O3 达标:2 个(00:8/8、07:2/8),差 1 到门槛;09 补测 O3=0/8 |
| H_D REPLANNING | INCONCLUSIVE | O3 不足而 O4 达标:2 个(02、03),03 的 O3 因 ref 不可得未测;Δ34=−0.125(2正3负) |
| H_E SKILL DEFICIT | NOT WRITABLE | O1/O2/O3 均有达标快照,§30 限定条件不满足;禁写"Pi0.5 缺 recovery skill" |

## 5. 必答 Q1–Q10(§37)

**Q1 recovery 最常首次来自哪一层?**
采样层。task 版 5/12 快照首现在 O1(FG 3 + RPS 2);若把 O0 计入"现有系统
已有能力",RPS 4/4 其实被局部宏解决。planner 独有的贡献(replanning)只在
1–2 个快照上可归因。

**Q2 仅靠 repeated sampling 是否已存在 recovery behavior?**
是(H_A SUPPORTED)。68/192 次单技能重采命中;best_of_N checkpoints
1/4/8/16 = 0.455/0.386/0.364/0.375——第一次采样就中的均值 45.5%,命中
不随 N 衰减说明是真实成功率而非尾部运气。异质:4 个快照 O1≈0(02–05、07、09)。

**Q3 correct grounding / immediate subgoal 能否把 0 拉起?**
不能(在测到的范围内)。O2(oracle conditioning)0/32,两个可测快照(07、09)
均零。H_B NOT SUPPORTED。限定:O2 只在"O1 失败且 ref 可用"的 2 个快照上有
定义,证据面窄。

**Q4 正确的 frozen long-horizon sequence 是否已经足够?**
个别快照足够(00:8/8 完美复刻;07:2/8),但 5 个可测快照里只 2 个达标
(<3)→ 不足以判 SUPPORTED(H_C INCONCLUSIVE)。序列能力真实存在但稀疏,
且 09 上同一序列 0/8。

**Q5 Full Planner 是否真正依赖 state-dependent replanning?**
无证据支持。Δ34 = −0.125(O4 不优于 O3);O4 仅 2 个快照"O3 不足而 O4 达标"
(02、03),其中 03 的 O3 未测(ref 不可得)。**机制侧写**:72 次 O4 rollout
中 69 次零 Pi0.5 调用、平均 15.4/16 turns——planner 把预算耗在感知与记忆
阅读上,失败模式是"不动手"而非"规划错"。H_D INCONCLUSIVE。

**Q6 policy reentry 是否比 immediate task recovery 更容易?**
否,方向相反。reentry 命中远低于 task(全臂最高 RPS O0 25%;FG O1 仅
7/128=5.5%);reentry 版 first-source 以 NO_SOURCE(6/12)为主;仅 2 个
(snapshot,arm)对 reentry 早于 task(均在 osnap_02)。§31 的"recovery
target 是否应为 reentry"讨论:不需要——task 契约更早达成。

**Q7 是否经常先 reset / realign 再继续 nominal task?**
采样恢复路径上不是。成功 rollout 内 REALIGNMENT_FIRST:O1 0/68、O4 0/8、
O3 3/11;O0 27/27 是宏定义使然(策略本身 realign 起手)。reference 自然续跑
3/7(43%)先 realign。→ 直接重试(direct completion)是采样恢复的主路径,
"先复位再继续"更多是 planner 的自然语言偏好而非必要条件。

**Q8 各 failure family 主要属于哪类来源?**
- **FALSE_GRASP:sampling**(O1 36.7%,3/8 快照有采样支撑;O3 次之 34.4% 但
  集中在单个快照;conditioning 零)。
- **RELEASE_PREDICATE_STALL(受限,n=4):现有局部宏即足够**(O0 84.4%;
  sampling 次之 32.8%;sequence/replanning 无证据)。工程含义:RPS 类失败
  挂 N1 宏即可,不需要 planner。
- skill deficit:两族均无可写证据(H_E NOT WRITABLE)。

**Q9 当前是否已有足够证据支持 recovery skill training?**
没有,且方向相反。O1 的大量成功说明策略本身已具备恢复行为(重试即中),
训练缺口未被证明;真正缺的是"何时该重试、何时该换法"的 test-time 判据。

**Q10 下一阶段最值得研究什么?(证据排序,决定权在用户)**
1. **test-time sampling / verification**——证据最直接:16.2s/样本换 36.7%
   单次命中率,best_of_1 已 45.5%;缺的是验证器(何时停、何时升级策略)。
2. long-horizon program execution——O3 在个别快照完美但泛化差,值得理解
   为什么(00 的序列为何可迁移、09 的为何不可)。
3. grounding / goal reformulation——O2 无正面证据,不优先。
4. receding-horizon planning——O4 最贵(475.9s vs O1 的 16.2s)且不优于
   O3;当前形态(预算耗在感知/记忆)下不优先。

## 6. 预算与混杂账(§20/§33)

| 臂 | n | prims 均值[p90] | pi05 | turns | wall_s |
|---|---|---|---|---|---|
| O0 | 84 | 4.1[5.0] | 1.2 | — | 40.0[52.6] |
| O1 | 176 | 1.0 | 1.0 | — | **16.2**[22.4] |
| O2 | 32 | 1.0 | 1.0 | — | 18.9[21.3] |
| O3 | 32 | 2.8[4.0] | 0.2 | — | 14.7[27.8] |
| O4 | 72 | 1.0[3.0] | 0.0 | 15.4[16.0] | **475.9**[704.0] |

混杂方向检查:表现最好的臂(O1)预算最小,故"O1 赢"不受预算混杂的反解释
(不存在"O1 只是预算不够"的方向性风险);O4 预算内自身行为(零技能调用、
turns 耗尽)如实计入 end_reason。无强机制结论依赖跨臂预算精确匹配。

## 7. Infra 账与 deviation 全记录(§12/§35)

- **Infra 率 36/516 = 7.0%,超 §12 的 2% 门** → 按规程暂停并报告用户,
  用户裁定补测(dev-O6)。36 行全部 RPS 族、全部 dev-O5 事件复现守卫拒绝型
  (boot 32 + rollout 4),零 GLM API / vla 故障;分析层 valid_row 过滤。
- 补测(dev-O6,`--fill --max-retries 8`):4 个缺格全部补齐、**零新增
  infra**;关键判定落地:09 O3 = 0/8(H_C 维持 2/3,由缺口变为真测量)、
  11 O1 = 2/16(不达标,标签不变)、09 O0 = 8/8、08 O0 补满 6/8。
- deviation 编号:dev-O1(grid 枚举勘误)/ dev-O2(O3 序列域含达成动作)/
  dev-O3(全臂采集范围)/ dev-O4(独立 boot)/ dev-O5(重放有效性与 hash
  断言修正)/ dev-O6(infra 缺口补测模式)。全部只追加记录,未改写冻结条目;
  详情见 prereg 附录 C/C-2/C-3。
- 采样纪律:采集判定规则先于运行冻结(附录 A),零结果筛选;sequential
  gate(O1 达标非 sanity 即停)按 §10 冻结执行,sanity 子集 = 00/02/06。

## 8. 产物与 commit

`analysis/` 下:stageO_prereg.md(4eb3de5 + 附录)、stageO_offline_recovery_
audit.csv/.md(O-A)、stageO_split_manifest.csv + collect_ledger(c57ebbc)、
stageO_reference_traces.jsonl(c80ed34)、stageO_rollouts.csv /
stageO_reentry_results.csv / stageO_arm_transitions.jsonl(ladder 落盘)、
stageO_first_source.csv + stageO_hypothesis_results.md(analyzer,幂等)、
本报告。脚本:stageO_collect / reference / ladder / calibrate / analyze /
init_check / freeze_manifest。OX 未运行(§6 限定条件不满足,无需人工)。

## 9. Hard STOP(§39)

Stage O 到此停止。按预注册:**不自动启动任何 recovery VLA / SFT / OPD /
RL / World Model / Graph evolution / LLM Router / verifier / 新感知模型 /
reset policy / planner redesign**。上述 Q10 排序仅为证据陈述,下一条研究线
由用户决定。
