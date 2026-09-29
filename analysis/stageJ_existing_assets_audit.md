# Stage J §0 — 现有资产审计(只读,2026-09-29)

_对象:Stage H / I0 收口后的 RPent 栈。逐问给 file:line 证据;本审计零代码改动。_

## 结论先行

**七问全部有肯定或可实证答案,无 STOP 项。** 尤其:MuJoCo 级 exact
snapshot/restore **已内建于当前栈**(无需改冻结包,只差 3 个 facade
RPC 方法),H1 fire 与历史 148 点均可映射回完整轨迹且 prefix 全参数
在盘。J0 的剩余风险集中在 Pi0.5 推理与控制器积分的物理确定性 ——
这正是 J0 本身要度量的东西。

## Q1. Stage H fire event 能否映射回原始 trajectory?

**能,两级都是。**

- **h1(104 fire)**:`analysis/stageH_transition_dataset.jsonl` 每条
  src=h1 记录带 `episode_dir`(H1 90 集的日志目录,如
  `logs/ovpm_exp/20260929-04:23:24_..._h1C_..._t3_s1_r1/`)+
  `step_idx`(fire 时的 states.json 步号)+ `arm`。目录内
  `states.json` / `run.log` / `memory_events.jsonl` /
  `structured_metrics.json` 齐全(实测抽查)。
- **h0(148 点)**:每点 `analysis_only.source_path` 指向 G0.5/G0.6
  episode 目录,states.json 存在(实测抽查
  `20260921-03:37:56_..._g05P0_..._t3_s1_r1`)。

## Q2. failure point 前的完整 action/primitive prefix 是否保留?

**是,全参数。** `states.json` 每步记录:

```
{command: {action: <原语名>, **全部调用 kwargs},   # 例:pi0_pick 带
                                                  # prompt/max_chunks/
                                                  # lift_thresh/...
 result: <原语结果字段>, state: <步号>,
 task_language, libero_terminated, elapsed_s,
 world_map(_hi)/wrist_world_map(_hi): <artifact 路径>}
```

抽查实证:`move_to` 记录 xyz/gripper/max_steps/step_clip;`pi0_pick`
记录 prompt 全文 + 阈值参数。重放 = 按步序 `toolkit.execute_tool
(command)` 即可(prefix 物理重建的全部信息在盘)。H1 集步数
中位 11 / 最大 18(55 集实测),重放成本极低。

## Q3. 当前 simulator 是否支持 exact state get/set?

**支持,三层现成,零冻结包修改:**

| 层 | API | 位置 |
|---|---|---|
| robosuite/libero 封装 | `get_sim_state()`(flatten) / `set_state(flat)` / `regenerate_obs_from_state(flat)`(restore + forward + 重生成全部观测) | `libero/libero/envs/env_wrapper.py:121-139` |
| worker 子进程分发 | 命令 `get_sim_state` / `set_init_state` / 任意 `env_call`(target='robosuite' 可直达最底层 MujocoEnv 调任意方法) | `rlinf/envs/venv/venv.py:288-321` |
| parent 侧 | `SubprocEnvWorker.get_sim_state()/env_call()/set_init_state()`;`BaseVectorEnv` 亦转发 | `venv.py:378-427, 561-566` |

**缺口(唯一)**:`robots/libero/env_server.py` 的 RPC facade
(150-350 行)未暴露 state 方法 —— J0 需加 3 个 facade 方法
(save_state / restore_state / get 内部计数器),纯新增,不动
task dynamics。

## Q4. state 由哪些内容构成?

| 成分 | 在 MuJoCo flatten state 里? | 说明 |
|---|---|---|
| qpos(全部关节 + **物体位姿** + 自由体) | ✓ | `sim.get_state().flatten()` |
| qvel | ✓ | 同上 |
| act / time | ✓ | 同上 |
| EEF pose / gripper | ✓(派生) | 由 qpos 正运动学导出,restore 后 `sim.forward()` 即一致 |
| LIBERO 任务谓词 / termination | ✓(派生) | 每步从 qpos 重算(`_check_success`),无独立状态 |
| **OSC 控制器内部** | 部分 | 位置增益无状态;interpolator 若启用携带上一步目标 —— J0 直接度量其影响;分叉点选在**原语边界**(fire 发生在 tool result 边界)可避开原语中途的插值态 |
| **Pi0.5 chunk 内部游标** | ✗ | 原语边界分叉时 chunk 从头开始,天然对齐 |
| SAM3 / 渲染 | 无状态 | obs 是 sim state 的确定性函数(osmesa/egl 离屏渲染) |
| STV 计数器(consec_move_stall 等) | 派生 | 由 prefix 结果序列重放重算,两支一致 |

## Q5. 能否 deterministic replay 到历史 failure point?

**机制上可行,物理确定性待 J0 度量(这正是 J0 的设计目的):**

1. **init state 确定性**:`env_server.make_env`(env_server.py:100-112)
   `specific_reset_id = first_id + (seed % trials)` +
   `use_fixed_reset_state_ids=True` —— 同 (task,seed) 恒回同一
   init state(t3/t7 修复后 50 states 在
   `/workspace/yjx/rpent_data`,见 memory)。
2. **prefix 全参数在盘**(Q2)。
3. **原语执行**:脚本原语(move_to 等)是当前 obs 的确定函数;
   策略原语(pi0_pick/pi0_doubled)是 VLA 对当前 obs 的函数 ——
   greedy 推理,但 CUDA 核非确定性未排除。
4. J0 的 A1-vs-A2 分叉即度量 (3) 的残差;若超容差,J0 兜底方案是
   deterministic trajectory replay(同门)。

## Q6. 哪些历史 failure point 可以可靠 reconstruct?

可重建判据(全部可机检):episode 目录存在 states.json + run.log;
行在 outcome_validation_runs.csv 非 infra;`libero_terminated` 可为
False(失败点本身);命令序列完整(每步 command.action 非空)。

- **H1 90 集**:CSV 全行 infra=0(Stage H §7 已核);104 fire 中
  91 进 transition dataset(13 事件↔重放不一致已按冻结口径剔除,
  那是触发器计数问题,不影响物理重建)。
- **h0 148 点**(G0.5/G0.6 180 matched 轨迹):provenance 完整
  (Stage H §0/Q5 审计过,H0 协议确定性抽取)。
- memB / memC / OVP-M heldout:同架构目录,判据同上,数量待 §3 实点。

## Q7. Graph edge 当前哪些可直接映射为真实 executable option?

三家族 12 条边(graph_v0.yaml,全部 status=frozen),对照
ACTION_FAMILY_PRIMS(analyze_stageH1.py:44-61)与原语真实签名
(tools.py:202-804),**逐边编译可行性**:

| edge | action_family | 可编译 executor(现有原语链) | 可行性 |
|---|---|---|---|
| FG-1 perceive_hires | perceive_hires | `segment(prompt,camera,point,min_score)` → `back_project(row_range/col_range,resolution=high)` | ✓ 现成 |
| FG-2 grasp_retry | grasp_retry | `pi0_pick(prompt)`(guard: localized ∧ fails<3) | ✓ |
| FG-3 grasp_offset | grasp_offset | `pi0_pick(prompt 改写偏移/yaw 语义)`(parameterizer 冻结模板) | ✓ prompt 参数化 |
| MS-1 perceive | perceive | 同 FG-1 | ✓ |
| MS-2 move_waypoint | move_waypoint | `move_to(中点 xyz=max(当前,目标)+z 抬升)`(解析参数化) | ✓ |
| MS-3 retreat_reapproach | retreat_reapproach | `move_to(当前+z)` → `move_to(目标)` | ✓ |
| CS-1 perceive | perceive | 同 FG-1 | ✓ |
| CS-2 grip_adjust_retry | grip_adjust_retry | `set_gripper(gripper)` → `pi0_doubled(prompt)` | ✓ |
| CS-3 contact_settling | contact_settling | `move_to(当前-z 小步)` → `pi0_doubled(prompt)` 或 `set_gripper(低位)` | ✓ |
| RS-1 micro_reposition | micro_reposition | `move_to(当前+小 y 偏移)`(guard: actions_since_release≤6) | ✓ |
| RS-2 repick_replace | repick_replace | `pi0_pick(prompt)` → `move_to(低位)` → `release()` | ✓ |
| RS-3 contact_settling | contact_settling | `set_gripper(低开爪)` → `move_to(-z 沉降)` | ✓ |

**结论:12/12 可编译,无纯自然语言 executor 残留**;parameterizer
所需的"当前 EEF/目标坐标"在 runtime 均可观测(view_driver_state /
obs state / segment+back_project)。抓取偏移类需要冻结 prompt 改写
模板(§1 落地时逐边写死参数,不引入 LLM)。

## 附:其他被审计件的位置

- **STV**(B2 状态转移验证 / PhaseTracker):`rpent/memory/`
  (phase tracker + 违禁词红线);在线分叉两支复用同一 tracker 逻辑。
- **OVP-M**:调度器 `scripts/ovpm_exp.py`(RUNS_CSV=
  `analysis/outcome_validation_runs.csv`,行含 stage/cond/task/seed/
  result/dir);J0/J1 的轨迹选样直接读该 CSV。
- **环境 wrapper 全链**:agent 进程 toolkit(robots/libero/toolkit.py
  :26-80,execute_tool 分发)→ RPC client(env_client.py)→
  env_server.py facade → rlinf LiberoEnv → SubprocVectorEnv worker →
  libero OffScreenRenderEnv(robosuite)。VLA(Pi0.5)/ SAM3 各自
  常驻 server(toolkit init_primitives_clean 管理)。

## 差距清单(Stage J 需要新建的件)

| # | 件 | 说明 |
|---|---|---|
| 1 | env_server facade 加 `save_state/restore_state` RPC | 3 个方法,包 worker.get_sim_state / env_call(regenerate_obs_from_state);零冻结包修改 |
| 2 | 脚本化 replay runner | 读 states.json prefix 逐原语执行到 step T(不经 planner,零 GLM) |
| 3 | J0 fork runner | snapshot → A → A1 → restore → A → A2 → 差分报告 |
| 4 | executable_graph_v1.yaml + spec | §1(12 边全字段编译) |
| 5 | snapshot dataset builder + J1 双支 runner | §3/§4 |
| 6 | 家族 verifier 实现 | §5 三套物理判据(全部 runtime-observable 字段) |

**§0 裁定:provenance 完整、exact snapshot 通道现成、12/12 边可编译 —— 不触发 STOP,进 §1。**
