# Stage J0 预注册 — simulator 状态分叉验证(2026-09-29 冻结,先 commit 再跑)

_依据:Stage J spec §2。问题:在真实 H1 失败点上,sim exact snapshot/restore 之后,
同一动作执行两次(A1/A2),物理可观测轨道是否一致到足以支撑 J1 的
HIST-vs-GRAPH 配对比较。J0 FAIL → **Stage J STOP**,不启动任何 efficacy 实验。_

## 1. 底座与选样(冻结)

- **池**:`analysis/stageH_transition_dataset.jsonl`(commit 22aca81)全部
  `src=h1` 行(104 fire,55 集)。
- **选样算法**(确定性,2026-09-29 执行,产物
  `analysis/stageJ0_fork_selection.json` 随本预注册一并冻结):
  1. 每集只取一个 fork 点:该集 `step_idx` 最小(平手取 `fire_k` 最小)的行;
  2. 过滤:`episode_dir/states.json` 可解析、step `T` 与 `T+1` 的 command 均在
     (1 集被剔:t3 s4 h1G,T=5 为末步,无 A);
  3. 排序 `(task, seed, arm, episode_dir, step_idx)` 升序;
  4. 家族轮转 `FALSE_GRASP → RELEASE_PREDICATE_STALL → MOVE_CONTACT_STALL`
     各取所需至 20。
- **实得 20 点:FG 10 / RPS 10 / MCS 0**(如实记录:6 条 MCS 行所在集的
  最早 fire 均为 FG/RPS,一集一点规则下 MCS 池为空;J0 是机制验证,
  不依赖家族覆盖,J1 §3 再补 MCS snapshot)。
- 任务覆盖 t3/t5/t9(即 H1 的三任务集),seed 与 arm 见 manifest。

## 2. 分叉协议(每 fork 点)

1. **boot**:共享一个 vla_server + sam3_server(同 GPU);每集新起
   env_server(`--suite libero_spatial --task t --seed s`,与源 episode 同参,
   init state 由 (task,seed) 确定性决定)。`MUJOCO_GL=osmesa`。
2. **重放**:按源 states.json 的 `step_idx=1..T` 逐条
   `toolkit._step(action, **kwargs)`(全参数原文;segment/back_project 等
   inspection 调用不进 states.json、不影响物理,跳过即与源物理一致)。
   重放中 episode 提前终止 / 原语异常 → 该 fork 记 `infra_abort` 剔除并计数。
3. **快照**:`S = env.save_state()`(MuJoCo flatten)。
4. **四支执行**(顺序冻结,除首支外每支先 `restore_state(S)` +
   `primitives.set_obs(restore_obs)`):
   - `A_hist #1` → `A_hist #2`(HIST 支噪声)
   - `A_vla #1` → `A_vla #2`(GRAPH 支噪声,VLA 技能)
   每支后立即 `save_state()` 读回 + `sim_measurement()` + `check_success()`,
   并记录原语 result 字段。
5. **A 的定义**:
   - `A_hist` = 源 states.json 中 `step_idx=T+1` 的 command 全参数原文
     (20/20 实得均为 `move_to`,即 planner 事后撤退动作——与 Stage H
     "90% violation = 不重抓"结论同源,如实记录);
   - `A_vla` = `pi0_pick(prompt=P, max_chunks=14, lift_thresh=0.05,
     gripper_closed_thresh=0.06)`,其中
     `P = LAST_PICK_PROMPT`(prefix 1..T 中最后一条 pi0_pick / pi0_doubled
     的 prompt 全文;无则回退 task_language),家族为 FG 时
     `P = LAST_PICK_PROMPT + OFFSET_SUFFIX`
     (OFFSET_SUFFIX = `" — grasp at a slightly offset point, about two
     centimeters to the side of the previous attempt"`,graph v1 FG-3 冻结值)。
     RPS 不加后缀(对应 RS-2 首步)。此即 J1 GRAPH 支的主执行原语形态。
6. **restore 后读回校验**:每次 restore 后 `save_state()` 与 S 逐元素比对。

## 3. 可观测通道与容差(冻结)

| 通道 | 来源 | 门控容差(A_hist / A_vla) |
|---|---|---|
| EEF 位置 L2(支末 vs 支末) | sim_measurement obs | ≤ 0.002 m / ≤ 0.005 m |
| 物体位姿 L2(逐物体最大,若 object-state 通道存在) | 同上 | ≤ 0.002 m / ≤ 0.005 m |
| 夹爪开度 | 同上 | ≤ 0.004 / ≤ 0.004 |
| peak_lift_m(pi0_pick)| 原语 result | ≤ 0.002 / ≤ 0.005 |
| final_dist_m(move_to)| 原语 result | ≤ 0.002 / — |
| 工具 success 旗标 / check_success | result + 谓词 | **精确相等** |
| chunks_used / steps_used | result | 记录,不门控 |

(容差依据:脚本原语应近乎精确;VLA 支给 CUDA 非确定性 5mm 量级余量,
该余量本身即 J0 要测的量,如实报告原始差值分布。)

**物体位姿通道探测**:J0 首个 fork 记录 `sim_measurement()` 全部低维键;
若存在 `object-state` 类向量 → 冻结为 J1 测量通道;否则 J1 降级判据
(spec §5.4 回退:FG 用 peak_lift_m 物证 + EEF-谓词联合代理),降级决定
写入 J0 结果文档,仍属 J1 prereg 之前的合法时点。

## 4. STV 类代理(冻结;J0 判定用,非在线 STV 系统)

支末相对 snapshot 的类:
```
Δobj_z := max_objects(obj_z(post) − obj_z(S));Δeef := ‖eef(post) − eef(S)‖
TERMINAL  若 check_success(post)
LIFT      若 Δobj_z ≥ +0.01
DROP      若 Δobj_z ≤ −0.01
MOVE      若 Δeef ≥ 0.03
STALL     其余
```
优先级 TERMINAL > LIFT > DROP > MOVE > STALL。A1/A2 类不一致 → 该支对
STV 不一致。(object 通道缺失时 LIFT/DROP 退化为不触发,只比
TERMINAL/MOVE/STALL —— 在结果中声明。)

## 5. 四门(冻结;任何一门不过 → J0 FAIL → Stage J STOP)

1. **G1 restore 精确性**:全部 restore 事件中,读回 state 与 S 逐元素相等
   (max |diff| == 0)的比例 = **100%**;
2. **G2 可观测一致**:A_hist 对与 A_vla 对分别统计"全部门控通道在容差内"
   的比例,各 ≥ **95%**;
3. **G3 STV 类一致**:全部支对(A_hist 20 + A_vla 20)类一致比例 ≥ **95%**;
4. **G4 成败一致**:全部支对 (工具 success 旗标, check_success) 二元组
   相等比例 ≥ **95%**。

**有效样本规则**:infra_abort 剔除且如实计数;有效 fork < 16 →
按证据不足判 FAIL(不补样重跑——补样属 INCONCLUSIVE 类决策,需用户裁定)。

## 6. 纪律

- 本预注册 + `stageJ0_fork_selection.json` + facade/client 代码先 commit,
  之后才允许跑;单遍执行,不为过门重跑/换 fork 点/调容差;
- 运行锁 `.runlocks/stagej0.lock`;preflight 通过后才启动;并发 = 1
  (共享 VLA/SAM3,每集串行);
- J0 全部产物:`analysis/stageJ0_fork_results.jsonl`(逐支嵌套记录)+
  `analysis/stageJ0_state_restore_results.md` + `analysis/stageJ0_decision.md`;
- 渲染违禁词红线:J0 无 planner 参与循环,记录文本不进任何 planner 对话;
- J0 FAIL → Stage J STOP(spec §2),不做 "deterministic replay 同门兜底"
  之外的解释性续跑;该兜底仅在 exact snapshot 机制不可实现时适用
  (本栈已实现,故不适用)。
