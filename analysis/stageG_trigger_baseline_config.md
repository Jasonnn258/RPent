# Stage G — Trigger Baseline 冻结配置(2026-09-20,只在 DEV suite 定一次)

T2/T3 是**新增 baseline 实现**,不触碰 §1.1 冻结的 Progress Trigger;
两者的 retrieval(Q0)、注入路径、cooldown(`COOLDOWN_BOUNDARIES=2`)与
episode 上限(`MAX_TRIGGERS_PER_EPISODE=6`)与 T4 完全一致——唯一变量
= **何时触发**。参数来自 DEV suite 历史数据(Stage B/C 冻结运行:
libero_spatial_task 上 57 个 memB2/memO2 episodes),一次定死,禁止在
final suites 调整。

## T2_PERIODIC(定时器)

- 规则:每 N 个**有效 planner turn**(turn boundary 计数,含工具调用轮)
  触发一次 retrieval,无论状态。实现:`RPENT_MEMORY_TRIGGER=periodic`
  + `RPENT_MEMORY_PERIODIC_N`。
- **N = 6**。推导(机械,DEV 数据):DEV episodes planner turns 中位数
  = 29(memB2 30 集 median 31,memO2 27 集 median 28,合并 57 集
  median 29);目标"每个典型 episode 检查 ~5 次"= 29/5 ≈ 5.8 → 取整 6。
  参考:DEV 上 v1 平均 1.8 次/集、progress 0.5 次/集;T2 的 ~5 次/集
  即"高频盲查"基线,是设计意图。
- 选择 env:`RPENT_MEMORY_TRIGGER=periodic`(+`RPENT_STRUCTURED_MEMORY=1`
  + access fix,与 T4 相同)。

## T3_MOTION_STUCK(通用运动卡死检测器)

- **只用**两类允许观测量:相邻 move 结果的 EEF 位移、以及(可得的)
  目标距离改善。**禁止** primitive 专属 PICK/PLACE/PERCEPTION 判断。
- 评估点:仅在 `move_to` / `move_pose` **结果到达时**评估(无 move
  结果的时间段不评估——运动检测器天然只看运动,感知/谓词时刻的缺席
  正是 G2 要展示的覆盖差)。
- 规则:维护最近 move 结果的 `final_eef_pos` 序列;若**连续 k=3 个**
  move 结果满足 (a) 相邻位移 |Δeef| < **M=0.01 m**,且 (b) 无一次
  目标距离改善 ≥ **P=0.01 m**(相邻 `final_dist_m` 差 d_prev−d_now,
  跨目标比较时自然 ≈0,即该条件只在真有接近进展时豁免)→ 触发一次,
  随后滑动窗重置。
- 参数推导(机械,DEV 45 个**成功** episodes,230 个相邻 move 对):
  - |Δeef| 分布:p10=0.0181,p25=0.0386,median=0.0816(m)——健康
    episode 相邻 move 通常大幅移动;取 **M = p10/2 ≈ 0.01**(健康最小
   十分位的一半,2x 安全边际)。
  - 距离改善分布 median≈0(相邻 move 常是不同 waypoint,无共同距离
    标尺);P 取 0.01 m(1 cm 级真实接近才算进展)。
  - 特异性核验(冻结前一次性):该规则在 DEV 成功集上 45 集仅 1 集误触
    (fires=1),满足"健康运动不误报";敏感性交给 final suites 实测,
    **不调参**。
- 选择 env:`RPENT_MEMORY_TRIGGER=motion_stuck` + 参数 env
  `RPENT_MSTUCK_K=3` `RPENT_MSTUCK_MOVE_M=0.01` `RPENT_MSTUCK_PROG_M=0.01`
  (调度 cond 里显式写死,防漂移)。

## 记录

两 baseline 的触发事件写入与 T4 相同的 `memory_events.jsonl`
(`trigger_mode` = `periodic` / `motion_stuck`,reason 字符串
`periodic_tick:N` / `motion_stuck:k=3 disp<0.010 prog<0.010`),
供 G2 的 precision/recall/分相位分析离线计算。
