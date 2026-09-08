# Reasoning Timing Summary — Event-Triggered Reasoning (Arm C) Verdict

**日期**: 2026-09-08 | **判定**: C 臂**不成立**(预注册判据 ① 与 ④ 双失败)
**数据**: devC 90 ep(glm-5.3-flash,t0/t7/t9 × s1-10 × r1-3,与 armB 严格同配对),
max_tokens=24576 修复后跑(见 §"管线事故与修复")

## 预注册判据逐条

| 判据 | 结果 | 数据 |
|---|---|---|
| ① SR 不低于 B | **FAIL** | C 34/90 (37.8%) vs B 77/90 (85.6%);配对翻转:B 成→C 败 48,C 败→B 成 5(McNemar p≈1e-10) |
| ② commit 模式被采纳 | PASS(机制确实启动) | 88/90 集出现 ≥1 个 commit turn,均值 1.66 turn/ep |
| ③ token/延迟改善 | 名义成立但无意义 | commit turn 平均 14.5k in / 2.9k out,远低于 reason turn(~28k in/turn);但 episode 大量早死,总 token 的比较失效 |
| ④ 无 premature-commit 损伤 | **FAIL(致命)** | 56 个失败中 **26 个为"假成功收尾"**(finish(success) 而环境未终止):19 个死于 P_place、7 个死于 P_grasp(抓完没放就宣布成功)。armB 的 13 个失败中同类为 **0** |

分任务 SR:C 在 t0 12/30、t7 11/30、t9 11/30 —— 崩塌不分任务。
C 还复活了 B 已治愈的 verify 阶段 stall(13 个 max_turns 烧穿 vs B 的 1)。

## 机制(逐例轨迹核验)

**主导机制(25/56 失败直接命中)**:release 或 pi0_doubled 结果 MATCHED →
`Commit: proceed to P_verify` → commit executor(只有动作工具,**没有任何感知工具**,
无法执行"验证"这个认知动作)读着剪枝后的 8 条历史,合理地推断任务已完成 →
`finish(status=success)` → 环境未终止 → policy_fail。

典型案例 t0 s1 r1:pick MATCHED → commit turn 正确 move_to 放置点(这部分工作良好)→
release MATCHED → commit turn(目标 P_verify)→ 无 view_driver_state 可用 →
直接 `finish(success)`,bowl 离 plate 还差半步。

**次级机制**:两模式提示(refer "已验证 → 直接执行")泄漏进 REASON turn 的行为 ——
7 个失败在 P_grasp 就 finish(success),连放置都没开始。flash 把"验证通过 licenses
收工"过度泛化成"抓到 = 成功"。

## 结论

1. **事件触发式 commit executor(无感知版)不成立**:当"已知的下一步"是**认知性动作**
   (验证结果)而非**物理性动作**(移动到已知坐标)时,把它委托给看不见环境的执行体,
   会把"去确认"系统性地翻译成"宣布完成"。物理目标的 commit turn(pick→move_to)
   行为正常——损害集中在 P_verify/finish 目标。
2. 负结果的价值:OVP-M 的 verdict 注入(arm B)之所以有效,正因为它把判断**留给**
   完整推理上下文;把执行从推理里剥离的省钱路径,在验证环节丢掉了"知道自己不知道什么"。
3. 修订方向(未实施,记录备查):commit 资格应限定 next_phase ∈ {物理动作目标},
   P_verify 类目标永不进 commit 模式;或 commit executor 保留最小感知集
   (view_driver_state)。本实验按预注册协议停止迭代 C,数据留作证据。

## 管线事故与修复(诚实记录)

- **v1 运行(09:17-12:40,已废弃)**:`Thinking(high)`→budget 16384 > max_tokens 8192,
  GLM 端点不校验 → 零内容截断 → 41%(13/32)episode 死于该异常,误判 policy_fail。
  B 臂同配置仅 3.3%(连续运行 vs C 每回合冷启动深思)。修复:max_tokens→24576,
  该异常改判 infra_crash。90 行污染数据已删(目录留盘:`logs/ovpm_exp/20260907-{09,10,11,12}*,14:4*` 之前的时间戳)。
- **v2 运行(14:47-19:19,本判定数据)**:0/90 token-limit;判定不受该事故影响。
- **跨臂公平脚注**:B 臂带着 3/90 同类死亡跑了全程(约 -3pp 影响);C 在 24576 下跑。
  即使给 B 扣满 3pp,C 的差距(48pp)远超该混杂。
