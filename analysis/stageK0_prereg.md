# Stage K0 预注册 — 分布真值标定(K_ROLLOUT 冻结)

_2026-09-29 冻结,先于任何 K0 运行。依据:Stage K spec §2;
资产审计 `stageK_existing_assets_audit.md`(commit f7ce911);
边语义 = `executable_graph_v1.yaml` + `stageJ_graph_spec.md`(§1 复用,零改动)。_

## 0. 目的

Stage J0 证明:同 snapshot + 同 VLA option 存在**真实执行分布**
(pick 双跑支末 EEF 中位差 5.1cm),单次 rollout 不可作反事实。K0 不消除
stochasticity,而是**标定**它:对每个 (calibration snapshot × candidate
edge),restore exact snapshot 后重复执行同一条边,估计

```
P(VERIFIED_RECOVERY), P(NO_EFFECT), P(HARM) | snapshot, edge
```

并**在 K1/K2 正式数据不可见之前**(它们尚不存在)冻结最终 K_ROLLOUT。

## 1. 冻结输入

| 件 | 值 |
|---|---|
| 图 | `resources/libero/executable_graph_v1.yaml`(12 边,sha256 0b840b1a,零改动) |
| 结局公式 | `stageJ_graph_spec.md` §5(三族 + HARMFUL 统一式 + 判定窗口) |
| 快照集 | `analysis/stageK0_snapshot_selection.json`(6 快照,discovery split,**机制上排除于 K1/K2 任何 split**) |
| 执行仪器 | J0 同款:共享 vla/sam3,每快照独立 env_server(同 task/seed),`toolkit._step` 全参数重放 prefix 1..T → `env.save_state()` |
| horizon | `max_episode_steps=200000`(J0 用 10000;K0 单 env 连跑 ≤48 rollouts ≈ >10k env-step,只抬 truncation 天花板,零 task dynamics 变化;server/client 同值,env_meta 一致) |
| 随机性 | Pi0.5 无 seed 旋钮(J0 实证:eval 模式同 obs 推断非确定)→ **common random numbers 不可用**,rollout 独立同分布采样 |

## 2. Rollout 协议(每条 rollout)

1. `env.restore_state(S)` + `prims.set_obs(obs)`;读回 `save_state()` 与 S
   逐元素比对(必须 ==0,否则记 infra_error 该条作废);
2. 解析并执行边链(§3);
3. **判定窗口**:链后 4 × `set_gripper(gripper=0.0, steps=5)`(保持开度
   20 env-step);每 5 步后采一次测量 + `check_success`,谓词触发即提前
   结束窗口;ERROR 支不跑窗口,NO_EFFECT(感知中止)支**照跑**窗口
   (部分链也可能造成物理伤害,统一协议);
4. 记录:链内每原语步后的测量 + 窗口 4 采样 + snapshot 基线测量。

测量通道(J0 冻结):`sim_measurement()` 的 EEF/夹爪/逐物体命名位姿 +
`check_success`;**GT 物体位姿只进 verifier/analysis,不进任何 runtime 输入**
(graph spec §5.4 红线,K 全程沿用)。

## 3. 边链执行语义(实现级冻结)

- 绑定解析:`${prompt}`/`${TASK_LANG}`/`${waypoint}` 等;表达式
  (`[obj.x, obj.y, max(eef.z, obj.z+0.06)]` 等)在 `{obj, eef}` 名空间
  安全求值(ast 白名单:下标/属性/二元运算/max/min);
- `LAST_PICK_PROMPT` = prefix 内最后一条 pi0_pick/pi0_doubled 的 prompt
  全文(J0 同款函数);缺失 → 回退 `TASK_LANG`(CS-2/CS-3 显式注明);
- `FG-3` prompt = `LAST_PICK_PROMPT + OFFSET_SUFFIX`(冻结常量);
- **`OBJ_XYZ` := 链内 back_project(region) 的 `center_xyz`**;
  `mask_rows`/`mask_cols` := segment `box`(1024 标定帧)取整
  `[y0,y1]`/`[x0,x1]`;
- **感知无果**(segment `found=False` 或 back_project error)→ 链中止,
  结局 NO_EFFECT(§2 冻结语义);其余原语 error/异常 → ERROR;
- `move_to` 未显式给 `gripper` → 默认 -1.0(开爪)——冻结行为照跑,
  不为语义好看改参数(边是 7e7528e 冻结件);
- 每原语经 `toolkit._step`(states.json 照常落盘,result 从尾记录读回)。

## 4. 结局分类(§5 公式的实现口径)

样本序列 = snapshot 基线 + 链内每原语后 + 窗口 4 点。记
`Δobj_z = obj_z(last) − obj_z(snapshot)`,`Δxy` 同理;
`obj_of_interest` 取 sim_measurement 返回的第一个。

- **FG**:VERIFIED ⟺ (Δobj_z ≥ +0.01 **且** 跟随 EEF)或
  (pick 结果 `peak_lift_m ≥ 0.005` 且 `final_gripper_opening ≤ 0.06`);
  跟随 EEF := 样本序列上 corr(Δeef_z, Δobj_z) > 0 且 max Δobj_z ≥ 0.01。
- **RPS**:VERIFIED ⟺ 窗口或链内任一采样 `check_success() == True`。
- **MCS**:VERIFIED ⟺ 目标残差下降 ≥ 5mm
  (`‖eef−obj‖(snapshot) − ‖eef−obj‖(last) ≥ 0.005`)或 check_success。
- **HARM**(族统一,优先级 VERIFIED > HARM > NO_EFFECT):
  ① snapshot 时握持(min 链内夹爪开度 ≤ 0.06 且其后有抬升证据:
  max Δeef_z ≥ 0.01 或 pick `peak_lift_m ≥ 0.005`)→ `Δobj_z ≤ −0.02`
  (脱手坠落,判 obj_of_interest);或 ② 任一命名物体
  `‖Δxy‖ ≥ 0.05` 且未 VERIFIED(扫飞/撞离)。
- **NO_EFFECT**:非 ERROR 且 VERIFIED/HARM 均不满足。
- **ERROR**:原语/环境/服务异常(≠ 感知空结果)。
- **感知边**(FG-1/MS-1/CS-1):结局类**只按物理口径**判(预期绝大多数
  NO_EFFECT —— 这正是 K2 要让 WM 学到的);segment `found` 另记
  `perception_found` 字段,不并入 VERIFIED。

## 5. K 阶梯与 K_ROLLOUT 冻结标准

- 每组合顺序执行 K_max = **16** 次 rollout(第 1..16 条按序入档);
- 阶梯 K ∈ {2, 4, 8, 12, 16};对每个 K 用前 K 条重算:
  三类概率 + Wilson 95% CI + 同快照内边对排序(p̂_verified 为主序,
  平分用 p̂_harm 升序);
- **K_ROLLOUT 取满足全部三条的最小 K**:
  1. 全组合 p_verified CI 半宽中位数 ≤ 0.30;
  2. 排序稳定:K 与下一阶梯的边对符号一致率 ≥ 80%
     (存在下一阶梯时);
  3. p_harm CI 半宽中位数 ≤ 0.25。
- 若 K=16 仍不满足 → 追加到 **20**(仅一次);仍不满足 →
  **Stage K STOP**(spec §2:"合理 rollout budget 下分布无法稳定估计")。
- 禁止为凑显著性事后加 K;禁止看 K1/K2 结果调 K(它们未运行)。

## 6. 预算

16 组合 × 16 = **256 rollouts** + 6 次 env boot/prefix 重放;
按 J0 实测(vla 支 14.4s / 脚本支 5.2s / fork 墙钟 112s)外推
≈ 3–4.5h,单 GPU 顺序,`/workspace/yjx/.runlocks/stagek0.lock` 防重,
nohup 日志 `logs/stageK0/`。开发机纪律:单 worker、共享 vla/sam3 单实例。

## 7. 产物

- `analysis/stageK0_rollouts.jsonl`(逐 rollout 一行:快照/边/k/结局/
  物理量样本/readback/耗时)
- `analysis/stageK0_distribution_calibration.csv`(组合 × K 阶梯表)
- `analysis/stageK0_decision.md`(K_ROLLOUT 冻结值 + 依据 + 是否 STOP)

## 8. 纪律

- 单遍执行,预注册外不调容差/不换快照/不重跑;infra_error 条目按
  ≤3 次重试同 k 补采(J0 纪律),重试本身入档;
- 本阶段零训练、零模型下载、零图改动、零 planner/GLM 调用;
- 校准快照永久排除于 K1/K2 数据集(manifest 双向登记);
- 若 restore 读回非 0 → 该 rollout 作废重试(仪器红线,J0 G1=100% 基准)。
