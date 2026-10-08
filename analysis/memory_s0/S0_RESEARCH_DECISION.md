# S0 研究决策:Memory 必要性判定与下一步最小研究问题

> 生成:2026-10-08 | 性质:审计决策文档(无新实验)
> 输入:REFERENCE_CODE_AUDIT.md(任务一)/ RPENT_CAPABILITY_AUDIT.md
> (任务二)/ MEMORY_NECESSITY_AUDIT.md(任务三)
> 状态:**等待用户/网页端研究决策**(本文件不启动任何后续阶段)

## 一、正式判定

# MEMORY NECESSITY: NOT SUPPORTED
## (限定:当前 HarnessVLA + LIBERO spatial t3/t5/t9 任务族 + 现有观测防火墙设计)

**白话**:我们把系统里所有"要做决定的地方"挨个数了一遍(9 类),
没有找到任何一个"光看当前画面和任务指令做不对、必须靠回忆之前发生
过什么才能做对"的决策点。具体分三种情况:
1. 六类决策(选技能、先感知还是直接抓、选哪个物体、什么时候收尾等)
   —— 当前画面 + 指令就够,而且之前 Stage H 的在线对照实验里,
   "不带记忆内容"的组成功率反而最高(83.3% vs 带记忆的 66.7%);
2. 两类决策(失败后重试几次、什么时候放弃)—— 需要的只是"这一局
   已经连败几次"的计数,episode 内就能算,现有代码已实现,
   不需要跨局记忆;Stage R 还证明了失败大多是瞬态的(14/24),
   换个随机数重试就过,跟记忆无关;
3. 一类决策(物体被遮挡后重新找)—— 看起来最像需要记忆,但
   Stage K/L/N 三个阶段的证据显示:那些位置信息**从来没进过
   系统的可见观测通道**,历史里同样没有,记忆补不了从未看见的东西
   —— 这是传感器/感知问题,不是记忆问题。

同时如实记录:记忆线历史上唯一一次正收益(Stage C,成功率
.733→.852)经后续内容侧对照(Stage D/E/F0/H)分解,收益来自
"触发的时机"(进度信号),不是记忆内容本身。

**边界声明(防止过度推论)**:该判定是**任务族属性**,不是对
"机器人需要记忆"这个概念的一般否定。参考系统里,SimpleARM 在
专门构造了历史依赖的 16 个任务上比最强无记忆基线高 22.7 个百分点,
BATON 高 11.6 个百分点。我们当前的任务族(单指令、40 步内、指令
自带区分词)恰好没有构造这类依赖 —— 这是"考卷没出这道题",
不是"这道题做不出来"。

## 二、判定依据索引(全部只读,已存在)

| 依据 | 位置 |
|---|---|
| 决策点级审计(9 点逐项) | `analysis/memory_s0/MEMORY_NECESSITY_AUDIT.md` |
| 六系统机制对照 | `analysis/memory_s0/REFERENCE_CODE_AUDIT.md` |
| RPent 能力清单与四类信息判定 | `analysis/memory_s0/RPENT_CAPABILITY_AUDIT.md` |
| Stage H 无内容对照最优 | DECISIONS(Stage H,commit 22aca81) |
| Stage R 失败谱/重试曲线 | `analysis/STAGE_R_FINAL_REPORT.md`(76570cf) |
| Q0 决策时刻回查 0 | `analysis/memory_q0_audit.md` |
| Stage C 收益与归因 | `analysis/memory_stageC_results.md` 等 |
| Stage K/L/N 观测通道证据 | 各 stage 终报(bfc2aac/e42ddb3/369220e) |

## 三、下一阶段最小研究问题(不展开实现)

如果研究目标仍是"让 Memory 的作用可测量",S0 的结论指出:
**第一步不是建记忆系统,而是先让任务族获得"记忆资格"** ——
沿用本 repo 的阶段资格门传统(R0 重建资格、I0/K1 门先例)。

**RQ1(任务资格门,最优先)**:能否在现有 LIBERO harness 上构造
≥3 个任务,使其中存在决策点满足三条件(当前观测+指令不可解 /
历史可观测过 / 无替代来源)?构造方向已有先例:t3/t7 的 bddl
修改先例(rpent_data/init_state_backups)、SimpleARM RoboMME 的
四类依赖(relation/reference/progress/route)中,与现有 toolkit
观测能力匹配的是 **reference 类**(物体移出视野后按最后所见寻回)
和 **relation 类**(指令指涉"刚才移动的那个")。
判据建议:该任务上 B0(无记忆)失败必须系统性且失败点正是历史
依赖决策点(不是传感盲区 —— 需 Stage K 型对照排除)。

**RQ2(表示资格)**:在 RQ1 任务上,episode 内 typed state
(SimpleARM 四类分法)能否用现有 planner 可见通道(图像+SAM3+
back_project 工具流)在线维护?这是记忆表示的**上界测试**:
若 typed state 都维护不出来,任何检索机制都无米下锅(对应
Stage F0 "寻址成立但上界不足"的教训 —— 这次先测上界)。

**RQ3(条件触发资格)**:决策点条件检索("仅当提议子目标依赖历史时")
能否用比 R1-R5 进度阈值更语义化的条件实现,且在非依赖决策点上
零误触发?(对应 Q0 审计"路径 100% 断"的根因:触发条件与
"需要历史"语义无关。)

## 四、必要对照(任何后续 Memory 实验的最低对照集)

1. **B0 无记忆 vs B0+oracle 历史 vs B0+typed state** 三层夹逼:
   oracle(离线全知历史,如 rtrace/task_only 数据回放)定上界,
   typed state 定可实现位;B0 与 oracle 差距 <10pp 则任务资格不足,
   STOP(沿用 15pp 门量级的保守传统,具体数值留给预注册)。
2. **sham/置换记忆对照**(Stage D D_SHAM 先例):排除"注入任何
   文本都有安慰剂效应"。
3. **传感盲区对照**(Stage K 教训):历史依赖任务上的失败必须
   与"感知死"失败分类分开(FG/RPS 族分裂先例,Stage O/N)。
4. **episode 内计数器 vs 跨 episode 持久记忆对照**:排除 DP-4/5 型
   伪需求(计数可解的问题不许记到持久记忆头上)。
5. **瞬态/持久失败分流**(Stage R E/P 谱先例):瞬态失败上的
   "记忆收益"一律不计入(重采样可解,禁令二)。

## 五、决策请求(等待批准,不自行启动)

- 选项 A:批准 RQ1 任务资格门 → 进入 S1(预注册:任务构造 + B0/oracle
  资格测量;只测量,不建记忆系统)。
- 选项 B:不构造新任务,接受 NOT SUPPORTED 为 Memory 线终局,
  转向其他研究方向。
- 选项 C:先补 S0 缺口(SimpleARM/Ledger/BATON 代码发布后的源码级
  复核)再决策。
- 本审计已同步 research-sync(NEXT_TASK/DECISIONS 更新 + 发布),
  详情见同步仓 commit。
