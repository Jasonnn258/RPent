# P1-DEV1A Feasibility Pilot 结果(2026-10-10 · 协议 D-041)

> 脱敏汇总:只含聚合指标与工程结论。逐集审计明细(接触 geom 对、位姿、
> 原始事件流)在 `artifacts/p1_dev1a/runs/`(git-ignore,不入库)。
> Gate 证据:`artifacts/p1_dev1a/gate_evidence.json`(GO_PILOT);
> 汇总数据:`artifacts/p1_dev1a/pilot_summary.json`。

## 一句话结论

**同步物理标签可用、便宜、且对 Planner 零污染**:6 次真实失败触发全部
成功采到同刻接触真值,无一 UNKNOWN;其中 4 次"报失败但其实抓着"
(RETAINED)、2 次"真没抓着"(NOT_RETAINED);每次接触快照 ~12ms、
零 env step;probe 物理成本 19-32 步、垂直提升实测 16.1-16.6mm(帽 20mm)。

## 执行账本(真实数字)

| 项 | 值 | D-041 上限 |
|---|---|---|
| 真实新 episode | 8(t9×4 / t3×2 / t5×2,种子 2001-2008) | 8 |
| 墙钟合计 | 5385.6s ≈ 89.8 min | 4 h |
| GPU 合计 | 5190.0s ≈ 86.5 min(单卡,单 worker) | 3 GPU·h |
| 每集 env steps | 153-329(总 1678,含 probe 成本) | 1500/集 |
| probe 次数 | 6(6 集 × 各 1 次;触发即首个非终态 false-pick) | 1/集 |

## 触发与标签分布(6 触发 / 2 无触发)

| episode | 触发步 | probe 步 | CONTACT@close | RETENTION | eef_dz |
|---|---|---|---|---|---|
| t9_s2001 | 142 | 32* | BILATERAL | RETAINED | 16.6mm |
| t9_s2002 | 166 | 24 | BILATERAL | RETAINED | 16.4mm |
| t9_s2003 | 254 前 | 25 | NONE | NOT_RETAINED | 16.1mm |
| t9_s2004 | 199 前 | 24 | BILATERAL | RETAINED | 16.2mm |
| t5_s2007 | 153 前 | 19 | BILATERAL | RETAINED | 16.3mm |
| t5_s2008 | 170 前 | 24 | NONE | NOT_RETAINED | 16.3mm |
| t3_s2005 / t3_s2006 | 未触发(pi0_pick 无 false) | — | — | — | — |

分布:CONTACT BILATERAL 4 / SINGLE 0 / NONE 2 / UNKNOWN 0;
RETENTION RETAINED 4 / NOT_RETAINED 2 / UNKNOWN 0。

\* s2001 的 32 含 lift 步双重计数勘误(见下),真实物理成本 21。

**科研读数(白话)**:在 pi0_pick 亲手报"失败"的瞬间,三分之二的
失败其实是**假阴性**——夹爪两侧指面与目标真实接触、提起 1.6cm 仍保持
(RETAINED);其余两次是真空闭合(NONE,真失败)。t9(4 集里 3 集
RETAINED)与既往 Gate-Lab"t9 绝对门槛漏报"、时间持续性"D-only 持续率
72.7%"的线索相互印证;t5 在新种子网格下也出现同类假阴性(DEV0 中 t5
从未触发)。标签不是常数:s2003/s2008 给出 NONE/NOT_RETAINED,证明
判据有区分度、不是恒真输出。

## G1-G4 证据(全部真实运行,非模拟输入)

- **G1 场景能力 PASS**:三任务冻结 geom 名/int-id 表
  (`analysis/research_context/p1_dev1a_geom_spec_t{9,3,5}.json`,已入库);
  生产 worker RPC 正对照(碗↔柜面 True、↔地板 False、指↔目标 False);
  封版彩排产出真实 finger↔target 对(t9 BILATERAL / t3 BILATERAL+真实
  提起 14.9mm / t5 单侧)。
- **G2 同刻 PASS**:36/36 快照 same_tick(state sha 前后相等、服务器步数
  不变);A/B 世界 20 步终态逐位一致(读取不扰动物理轨迹);快照均值
  ~12.2ms、69 查询。
- **G3 防泄漏 PASS**:5 类特权字段注入 legal 信封全部拒收;种子化随机
  改写审计真值,信封字节不变;maybe_probe AST 级断言只 return None;
  8 集 Planner 全程盲(返回 None = vanilla 失败视图)。
- **G4 预算 PASS**:DurableBudgetLedger 崩溃/超限/禁 resume 真实文件
  往返;runner selftest 真子进程组 SIGTERM→SIGKILL;整集最坏预留
  (2400s 起,观测驱动上调);GPU 核算 8×H100 单卡占用;最终
  8/8 结账、零在飞。

## 工程勘误(如实记录)

1. **ep1 测量通道事故**:首版 runner 在 probe_done 后立即 killpg,子进程
   来不及 finalize → episode_end 缺失 → 步数不可测 → 按预注册 fail-close
   STOP(0 越帽,方向正确)。修复:probe 后每物理步落 `steps` 事件,
   测量回退到全事件最大 env_steps;ep1 按真实观测值回补结账
   (`scripts/p1_dev1a_reconcile.py`,174 步为含双计的保守值;不重跑,
   NO_DEV1A_EPISODE_RERUN 由 runner skip-done + 终止性事件保证)。
2. **lift 步双重计数**:probe 提升步在 env_client 钩子与 hook 手动 +1
   重复(s2001 成本 32,真实 21)。已修;s2002 起成本=真实物理步。
3. **冒烟断言过严**:dz 阈值停止时末采样与 t_lift_end 同刻,合法;
   改为整体非递减 + 阶段边界严格递增。

## 判定与下一步

- **DEV1A 判定:FEASIBILITY CONFIRMED**(标签可用性 + 采样成本两个
  评价维度均过)。**DEV1B(把此类标签交给 Planner 的因果实验)维持
  HOLD,等待用户新授权**——D-041 明确本轮不启动 DEV1B。
- 旧 Stage R / DEV0 / A0 冻结件零改动;所有钩子默认关闭,未启用时对
  vanilla 路径逐字节无差。
