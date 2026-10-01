# Stage N 最终报告 — 因果控制依赖资格认证 + 闭环反馈验证

日期:2026-10-01 | 判定链:N0(测量资格)→ N1(闭环反馈)| Stage N 完成后强制 STOP(§23)

## 0. 一句话结论

**N0 = PASS(测量可靠)**;**N1 = CLOSED-LOOP FEEDBACK NOT SUPPORTED**:
把中间信息接入控制(65.3% 的 rollout 真实改变了控制流)在匹配预算下
**不产生任何任务级恢复收益**(Δrecovery +0.0pp,0/144),机制门
(realized 与 not-realized 无差)同样失败。信息→控制的通路存在,
控制→结局的通路在宏预算内不存在。

## 1. Stage N 回答的问题(规范 §14)

前置各阶段的负结果链条:H(建议无动作级杠杆)、L(recovery 复现不转化)、
M(盲审测量无效)。Stage N 拆成两问:

- **N0**:轨迹级 control-dependency(观测/ grounding / verifier 结果
  改变下游控制)能否被可靠测量?
- **N1(条件解锁)**:允许这些信息改变控制(闭环 Option),相对冻结宏
  是否带来 validated recovery?

## 2. N0 — 测量资格(§6-§12)

- analyzer v2:确定性零 LLM,≥6 检测器(A′-F′),DEVELOPMENT 失败模式
  开发后冻结;全池 165 RESOLVED 段。
- 45 卷盲审(seed=20261002,卷宗 sha256=2390cf39…,先落盘后比对,
  人工作答 commit 61f968f 先于比对):
  **overall agreement 45/45 = 100%,false_independent 0/45,resolved 45**
  → 双门 PASS。
- 结构性限制(如实记录):审计池 45/45 为 machine-DEPENDENT
  (eligible∩INDEPENDENT=∅,deviation #5),机器-I 方向仅有 dev 阶段
  5 段 census 旁证,未经 45 卷级正式审计。
- commits:0a2f0bd(N0 判定 + 解锁 N1)。

## 3. N1 — 预注册设计(§14-§20,commit 062532a 先于 runner 75c9858)

- **M = FIXED_MACRO**:t0 冻结序列+参数;中间信息只落盘不进控制。
- **O = CLOSED_LOOP_OPTION**:同骨架 + 显式信息状态(§16 七字段)+
  规则集(R1 termination / R2 pose_update+carry / R3 retry),
  每次控制改变记 realized(与同快照 M 冻结决策比对)。
- 两 procedure(45 卷证据最集中两族):P1_RPS_REPICK(release 谓词未触发,
  12 快照)/ P2_FG_RETRY(pi0_pick 失败,12 快照)。
- 快照:held-out(episode 级排除 45 卷 audit)、前置核验 70 →
  task×seed 唯一 31 → 层内随机 24,sha256=3a4fcff4…(manifest 已冻结)。
- 匹配维度:同初始状态(restore 读回全 0.0)、同原语集、同 prompt
  模板、同 5 动作 / pick≤2 预算、同感知(SAM3 segment 双臂同感,
  M 的结果仅落盘);M,O 交错 × R=3 重复(对冲 Pi0.5 非确定性);
  全程不调 planner / GLM。
- 运行:144/144 rollouts 落地,0 infra abort(1 次 term/trunc 中断
  按 §7 重试成功);产物 stageN1_rollouts.csv +
  stageN1_information_provenance.jsonl(324 条信息事件)。

## 4. N1 结果(§4-§5 五门,全 144 rollouts)

| 指标 | M | O | Δ |
|---|---|---|---|
| validated_recovery | 0/72 | 0/72 | **+0.0pp** |
| harm | 1.4% | 2.8% | +1.4pp |

| 门(§5 逐字) | 实测 | 判定 |
|---|---|---|
| 1 Δrecovery ≥ 15pp | +0.0pp | **FAIL** |
| 2 Δharm ≤ 3pp | +1.4pp | PASS |
| 3 rescue_rate ≥ 10% | 0%(0/24) | **FAIL** |
| 4 realization_rate ≥ 20% | **65.3%**(47/72) | PASS |
| 5 delta_realized ≥ delta_not + 10pp | +0.0pp(0% vs 0%) | **FAIL** |

**判定:CLOSED-LOOP FEEDBACK NOT SUPPORTED。**

O 臂控制改变确实大规模发生(65.3%;rule 分布 R2_pose_update=36 /
R3_retry=36 / R3_retry_end=11),但这些改变的 rollout 与未改变的
rollout 结局完全相同(0% vs 0%),也未产生一次快照级 rescue。

## 5. 机制解读(描述性,证据指向)

1. **快照态可恢复性成立**:23/24 源 episode 在完整 planner 预算
   (40 turn,含感知-决策循环)下最终成功。0/144 不是测量通道损坏
   (check_success 在源 episode 可为 True),也不是状态不可救。
2. **瓶颈在动作侧,不在信息侧**:信息可用(N0 证明依赖存在)、
   控制可改(N1 65.3% realized),但 5 动作 / pick≤2 的预算内,
   无论冻结还是闭环,重抓/搬运宏都完不成恢复。P1 两次 pick 全空手
   (目标位移 0),P2 搬运落点偏差大(snap_01 O r1 释放跌落 dz=-23cm)。
3. **闭环还略有害**(Δharm +1.4pp;feedback_harm 快照 snap_01/snap_15):
   R3 重试路径的额外动作在抓不稳时把目标物推得更远。
4. 与 H/L/M 的负结果闭环一致:advice/predicate/graph/candidate 各层
   都给不出动作级杠杆;Stage N 把杠杆直接接到控制流上,仍不转化为结局。

## 6. 偏差与完整性账

- 冒烟 snap_00 与全量同代码路径(committed runner),计入 144。
- 分析器初版 realized join 键型 bug(int/str)在终报前发现并修复,
  以 runner 落盘的 CSV 列为准重算;判定不变(门 1/3/5 的失败与
  realized 口径无关)。
- 预注册 deviation:#5(N0 审计池全 D,见 §2)沿用;N1 无新 deviation。
- 环境事故账:vla_server 卡 gs:// tokenizer 下载 → 300s 超时一次,
  按 stageL_verify 先例补 OPENPI_DATA_HOME + PYOPENGL_PLATFORM=osmesa
  后零复发(已写入 runner __main__ 注释)。
- 未跑:MCS 族(45 卷仅 2 卷,证据不足,如实记录不追补)。

## 7. 产物与 commits

| 产物 | 位置 |
|---|---|
| N0 analyzer v2 + 全池标签 | scripts/stageN0_analyzer_v2.py → analysis/stageN0_control_labels.csv |
| N0 盲审三件 + agreement | stageN0_audit_manifest / manual_audit / measurement_results(.md/.csv) |
| N1 预注册冻结 | analysis/stageN1_option_spec.md + resources/libero/options_stageN.yaml + stageN1_split_manifest.csv(062532a) |
| N1 runner / analyzer | scripts/stageN1_runner.py / stageN1_analyze.py(75c9858 + 本次) |
| N1 数据 | analysis/stageN1_rollouts.csv(144)+ stageN1_information_provenance.jsonl(324) |
| N1 结果 + 判定 | analysis/stageN1_results.md |

commits:140 系列预注册 → 61f968f 盲审 → 0a2f0bd N0 PASS →
062532a N1 冻结 → 75c9858 runner → 本报告(均未 push)。

## 8. STOP(§23)

按预注册强制停止:**不进入** Option Graph 自动构建 / evolution /
LLM Router / World Model / perception replacement / SFT / OPD / RL。
Stage N 为该研究线(H→L→M→N)的终止符:四阶段在信息、图、候选、
控制四个层面均未找到可转化为任务结局的动作级杠杆,且每一层的
负结果都带有明确的机制定位。
