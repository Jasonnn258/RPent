# Stage J0 决定 — 分叉可测性门

_2026-09-29,依据 `stageJ0_prereg.md` §5 预注册门与
`stageJ0_state_restore_results.md` 冻结数字。_

## 决定

**J0 FAIL → Stage J STOP(spec §2)。**

- G2_vla = 0%(门 ≥95%):同快照同 prompt 的两次 pi0_pick,支末 EEF
  差中位 5.1cm / 最大 31cm;
- G3 = 85%(门 ≥95%),6 个不一致全在 VLA 支;
- G2_hist = 90%(门 ≥95%),脚本支残差来自 OSC interpolator(亚毫米)
  经接触放大;
- G1/G4 通过,但 G4 的旗标一致主要是"一致地失败",不构成灵敏度证据。

**后果:§3 snapshot set、J1 counterfactual、§7-§10 全部不启动。**
不补 fork、不调容差、不换 fork 点重跑(预注册纪律);spec §2 的
"deterministic replay 同门兜底"不适用 —— exact snapshot 机制本身已
实现且精确(机制探针 T2/T3 全零),失败原因不在仪器。

## 根因(三层,全部有实测)

1. sim 快照/恢复/渲染/观测再生成:逐位精确(G1 100%,探针 0.0);
2. OSC 控制器内部态:亚毫米 EEF 残差,偶发接触放大到 2.4cm;
3. **Pi0.5 推断非确定性(主导)**:同一 obs 连续三次 predict 动作值
   maxdiff 0.235 / 0.131 —— mode="eval" 下服务端推断仍不可复现,
   闭环逐 chunk 重查询将其放大为厘米级轨迹分叉。

## 这一结果证明 / 不证明什么(如实边界)

- 证明:在本冻结栈上,**以 VLA 技能为执行器的图边,其单次执行的
  物理结局不可作为反事实测量**(噪声底 cm 级 ≫ 门效应 15pp 对应的
  物理量级);脚本原语边(move_to/set_gripper/release 组合)可测
  (亚毫米)。
- 不证明:图的恢复边**好坏**(J1 未跑,无任何 efficacy 证据);
  不涉及 Stage H/I0 已冻结论的任何改写。

## 若未来重开(属用户决策,须新预注册)

按根因三条路,成本与约束各不同:

1. **确定性 VLA 推断**:修复 vla_server 推断复现(采样温度/内核
   确定性)。涉及 Pi0.5 服务端,当前在 Stage J 禁改清单内;
2. **多样本轮设计**:每支执行 k 次取分布比较(配对 Mann-Whitney /
   平均效应),测量成本 ×k,是新实验设计、新预注册;
3. **纯脚本边子图**:只保留非 VLA 边(MS-*/RS-1/RS-3 等)做
   counterfactual —— 但 v1 最高优先边(FG-3/RS-2/CS-2)均被剔除,
   已是另一张图,须重新走 §1 冻结。

已沉淀可复用资产:save_state/restore_state/check_success/sim_measurement
facade RPC(零冻结包修改)、逐物体命名位姿测量通道、J0 runner/分析/
探针脚本、20 fork 基准数据。

## 时序证据链

| 步骤 | commit |
|---|---|
| §0 审计 / §1 graph v1 | 84ee5f1 / 7e7528e |
| J0 预注册 + manifest + 代码(先于运行) | c2c8d12 |
| J0 运行(20 fork)+ 分析 + 探针 + 本决定 | (本次) |
