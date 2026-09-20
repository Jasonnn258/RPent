# Stage G — Subset 与选格规则(预注册,看结果之前定死)

## 1. G1/G2 网格(全量,无选择)

- G1 三臂(M0=memB1,M1=memB2,M2=memO2):3 final suites × 29 tasks
  (object_task 10 + goal_task 10 + 10_task 9,t0 空洞机械排除)×
  seeds s1-s5 × r1 = 145 格/臂,435 episodes。
- G2:T2_PERIODIC、T3_MOTION_STUCK 两新 baseline 跑**同一 145 格**
  (=290 新增);T0/T1/T4 直接复用 G1 对应臂,不重跑。
- task/seed 零选择:整 suite 全 task、seeds 前 5(s1-s5 与 G1 严格
  matched,配对统计的前提)。

## 2. G3(Timing × Ranking 2×2)subset

- 臂:A=NAIVE+LEXICAL(memB2,复用 G1)、B=NAIVE+Q3(memB3,新增)、
  C=PROGRESS+LEXICAL(memO2,复用 G1)、D=PROGRESS+Q3(**新增 cond
  memO3** = memO2 换 `RPENT_MEMORY_RANK=Q3`,两 env 正交,无新方法)。
- 选格规则(机械):每 suite 取 task indices **[0, 3, 7]**;若某 index
  不可运行(0 init states)则**顺延取下一个 index**——
  libero_10_task t0 空洞 → 该 suite 实取 **[1, 3, 7]**。即 9 tasks
  (object[0,3,7] + goal[0,3,7] + 10[1,3,7])× s1-s5 = **45 格/臂**。
- seeds 取 s1-s5 而非 s1-s10:**偏差声明**——§14 的 90 格/臂按 10 seeds
  定义,但 G1 只跑 s1-s5;为满足 §14 自己的"A/C 直接复用 G1、只新增
  B/D"条款,冻结为 s1-s5(45 格/臂,B/D 新增 90 episodes)。若 G3 事后
  功率不足,补充 s6-s10 需四臂同补(保持配对),不得只补单臂。
- 不按历史成绩挑 task;indices 在看任何 final suite 结果前写死。

## 3. G4(Memory 规模压力)bank 构造规则

- 网格:与 G3 同 45 格;臂 = {NAIVE(memB2), PROGRESS(memO2)} ×
  {BANK_2X, BANK_MAX}(4 新臂 = 180 episodes);**BANK_1X 直接复用
  G1** 同格结果。
- bank 内容(全部真实库内容,禁止 fake、禁止删 relevant 卡、禁止
  改 61 张 global 卡):
  - BANK_1X = 61 global 卡(现状)。
  - Distractor 池 = `resources/libero/suite/` 中 **suite ≠ 运行 suite**
    的全部页面(object_task run:66 页;goal_task:65;10_task:65)。
  - BANK_2X = 61 + 池内**按文件名排序的前 61 页** = 122 张。
  - BANK_MAX = 61 + 全池(126-127 张)。
  - 选择只按排序,不看内容、不挑"更像 distractor"的页。
- 追加机制(编排,不改方法):`RPENT_MEMORY_EXTRA_BANK=<dir list>` 旁路
  加载,suite 页作为 bank 条目(id=页名,词面 token = 正文+task_language,
  注入块 = 通用渲染:task_language 标题 + 正文摘录,与 global 卡同
  token 上限)。Q0/Q3 打分路径不变。
- 预期读数:SR、False Recall/Ep、Irrelevant/Ep、Relevant@3、
  retrieval latency、planner turns;主图为 bank size × {SR, noise}。

## 4. 运行纪律(重申 §25)

- 顺序:DEV 冒烟(每新臂 ≤2 集,libero_spatial_task)→ G1 → G2 →
  G3 → G4;单阶段内 `completed_keys` 断点续跑,infra ≤3 重试,
  `infra_missing` 单列,不 rerun-until-success,不挑结果好的 task,
  不看 final suite 失败轨迹改方法/阈值/bank。
- 统计(预注册):配对 (suite,task,seed);McNemar exact p;
  paired bootstrap 95% CI(10,000 重抽);macro(按 task 平均)与
  micro(汇总)都报。
- 预算:新增合计 435+290+90+180 = **995 episodes**(≈ 3 天 @ 8 workers,
  依据 DEV 每集 wall 中位 ~32 min);若 GLM API 限流/事故导致严重
  拖延,优先保 G1→G2→G3 顺序,G4 可缩减到 BANK_2X 两臂(记录偏差)。
