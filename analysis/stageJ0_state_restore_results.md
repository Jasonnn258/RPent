# Stage J0 结果 — simulator 状态分叉验证(2026-09-29)

_预注册:`stageJ0_prereg.md`(commit c2c8d12,先于运行);数据:
`stageJ0_fork_results.jsonl`(20 fork × 4 支)+ `stageJ0_mechanism_probe.json`;
运行日志 `logs/stageJ0/`(共享 vla/sam3 单实例,每 fork 独立 env_server)。_

## 判定:**J0 FAIL → Stage J STOP**(spec §2)

| 门 | 定义(预注册 §5) | 实测 | 门阈 | 结果 |
|---|---|---|---|---|
| G1 restore 精确性 | restore 后读回 state 逐元素 == S | 60/60 = **100%** | 100% | **PASS** |
| G2 可观测一致(hist) | A_hist 支对全通道 ≤2mm | 18/20 = **90%** | ≥95% | FAIL |
| G2 可观测一致(vla) | A_vla 支对全通道 ≤5mm | **0/20 = 0%** | ≥95% | **FAIL** |
| G3 STV 类一致 | 40 支对类相等 | 34/40 = **85%**(6 个全在 vla 支) | ≥95% | FAIL |
| G4 成败旗标一致 | (success, check_success) 相等 | 40/40 = **100%** | ≥95% | PASS |

有效 fork 20/20(infra_abort 0,≥16 要求满足)。三 FAIL → J0 FAIL,
按 spec §2:**Stage J 在此停止,不启动 J1 / §3 snapshot set**。

## 执行情况

- 20 fork(冻结 manifest FG10/RPS10/MCS0)全部完成;单 fork 墙钟
  92–158s;共享 Pi0.5(vla_server,gpu0,~12G)+ SAM3,每 fork 新起
  env_server(同 task/seed,`LIBERO_TYPE=pro`,osmesa)。
- A_hist 20/20 = `move_to`(planner 在 fire 后的撤退动作,与 Stage H
  "violation 90% = 不重抓"结论一致);A_vla 20/20 = `pi0_pick`
  (LAST_PICK_PROMPT;FG 加 OFFSET_SUFFIX)。

## 分支对差值分布(A1 vs A2,同快照同动作)

| 通道 | hist(median / p90 / max) | vla(median / p90 / max) |
|---|---|---|
| EEF L2 | 0.00013 / 0.00079 / 0.00093 | **0.051 / 0.280 / 0.311** |
| 物体位姿 L2(逐物体最大) | 0.00000 / 0.00272 / 0.02359 | **0.036 / 0.209 / 0.356** |
| 夹爪开度 | 0.00000 / 0.00010 / 0.00018 | 0.003 / 0.072 / 0.078 |
| 标量(final_dist / peak_lift) | 0.0001 / 0.0004 / 0.0006 | 0.023 / 0.103 / 0.169 |

G3 的 6 个类不一致全部是 vla 支对里 LIFT↔MOVE 翻转(同一快照,一次
支末抬升过 1cm、另一次没有)。G4 100% 的含义要如实读:两支的 pick
success 几乎都是 False,旗标一致大部分是"一致地失败",不是测量灵敏
的证据。

## 机制归因(探针 `stageJ0_mechanism_probe.json`,判定后归因用)

三层分解,噪声定位在**最内层(策略推断)**:

1. **sim 快照/恢复:精确**。G1 全部 bitwise 0;探针 T2:同快照两次
   restore,regenerate 的 obs(states / main_images / wrist_images)
   逐位相等(maxdiff=0.0);T3:同状态连续渲染逐位相等(osmesa
   确定性渲染)。
2. **控制器残差:亚毫米**。OSC interpolator 内部态不在 MuJoCo flatten
   state 里(§0 审计预告),hist 支对 EEF 差 median 0.13mm —— 但经
   接触动力学放大,1 例物体位移 2.4cm(t3s1h1GT3)→ G2_hist 90% 的
   两个越限 fork 之一即此类;另一个 t3s2h1CT2 是 2.7mm 边缘越限。
3. **Pi0.5 推断本身非确定性:主导项**。探针 T1:**同一 obs 连续
   predict 三次,动作值 maxdiff 0.235 / 0.131**(7 维动作,5 步
   chunk)。闭环 14 chunk 逐块重查询,该量级噪声被接触混沌放大为
   支末中位 5.1cm EEF / 3.6cm 物体位移。恢复机制无责 —— 输入逐位
   相同,输出不同。

**附:重放保真度**(非门控,如实记录)。J0 重放 prefix 末的 EEF 与源
episode step T 的 EEF 距离:median 1.7cm / max 11.4cm,仅 10/20 <5mm。
原因同上:prefix 内含 pi0_pick 步,重放≠复现历史。J1 的配对设计本来
就不要求复现历史(双支从同一重放态分叉),但这一条进一步说明轨迹层
在厘米尺度本来就是随机的。

## 测量通道冻结记录(spec §5.4 要求,J0 定案)

物体位姿通道**存在且质量超预期**:`sim_measurement()` 返回逐物体命名键
(`<obj>_pos/_quat/_to_robot0_eef_pos/_to_eef_quat`)+ `object-state`
(每物体 14 维块,布局断言通过)+ `obj_of_interest` 任务关注对象名。
**无需降级判据**。该通道零冻结包修改(facade 纯新增 RPC),供未来任何
重开直接使用。

## 结论

- 分叉仪器本身(快照/恢复/渲染/测量通道)是**完美**的;
- 可测的是脚本原语动作(亚毫米);**不可测的是 VLA 技能动作** ——
  而图 v1 的最高优先边(FG-3/FG-2/RS-2/CS-2)全部以 pi0_pick /
  pi0_doubled 开头;
- 因此"在同一物理失败态上单次执行 HIST vs GRAPH 比较 15pp 量级效应"
  的测量噪声底(cm 级)≫ 预期效应,J1 的预注册门在本冻结栈上不可判。
  J0 FAIL,Stage J STOP。
