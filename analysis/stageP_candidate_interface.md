# Stage P P0 — Candidate Interface Qualification(接口审计)

日期:2026-10-03 | 规范:Stage P §3-§8(用户 spec) | 本文只陈述实现事实 + 冻结定义,
不做任何判定(判定在 stageP0_decision.md,replay 资格在 stageP_replay_qualification.csv)。

## 1. 审计问题

"Pi0.5 在每次 physical execution 前实际产生什么?"——single action /
fixed action chunk / full trajectory / recurrent closed-loop skill 中的哪一种,
以及它是否满足 §4 的 candidate 四条件(A 执行前完整产生 / B 可序列化 /
C 可从相同 snapshot exactly replay / D 执行期不自改写)。

## 2. 实现事实(file:line 证据)

### 2.1 模型侧输出粒度 = 固定 5 步 × 7 维 action chunk

- `robots/libero/vla_server.py:44-45`:`num_action_chunks: 5`, `action_dim: 7`
  (openpi 段 `:55` `action_chunk: 5` 同值);
- `rpent/utils/vla_client.py:100-102`:RPC 返回 `[B=1, chunk, action_dim]`,
  client 剥掉 B 维 → **`[5, 7] float32`**;
- 采样:`vla_server.py:53-59` flow-matching SDE(`noise_method: "flow_sde"`,
  `noise_level: 0.5`, `num_steps: 5`)——**eval 模式下同样随机**,且 vla_server
  RPC 面无 seed 注入口(J0 经验冻结:同 obs 推断非确定)。

### 2.2 技能侧结构 = recurrent closed-loop(chunk 为最小可冻结单元)

- `robots/libero/tools.py:202-275` `pi0_pick`:循环 ≤ `max_chunks=24` 次,
  每轮 = 一次 forward(`_vlm_chunk`,:175-200)+ `env.chunk_step(actions)`
  执行 + 重观测;早停条件:(下降 ≥0.10 m)∧(post-min 回升 ≥0.05 m)∧
  (夹爪开口 <0.06)或 libero 终止。
- `_vlm_chunk`(:183)每次调用 `predict_action_batch(obs, mode="eval")` →
  采样新 chunk → 立即执行。**整段 pick 不是执行前可得的对象;只有单次
  forward 的 chunk 是。**

### 2.3 chunk 的 candidate 能力

| 条件 | 事实 | 证据 |
|---|---|---|
| A 执行前完整产生 | `predict_action_batch` 是纯推理 RPC(图像+状态→动作),不触碰 env | `vla_client.py:56-102` |
| B 可序列化 | RPC 以 JSON float 列表往返;`[5,7] float32` 可无损落盘 | `vla_server.py:150-157` |
| C 可 exactly replay | `env.chunk_step(actions)` 接受任意给定 chunk 执行;物理在 state+actions 下确定(J0:restore 读回逐位 ==0) | `env_server.py:214-244` |
| D 执行期不自改写 | 执行一个已保存 chunk 全程零模型调用 | 同上 |

## 3. 冻结定义(prereg §4/§7 的操作化)

- **candidate := 从 failure state 的观测(以 `_vlm_chunk` 同款 prompt 覆盖 +
  `extra_view_images=None`)采出的第一个 action chunk `[5,7]`**。
  禁止把未来依赖观测的整个 closed-loop grasp attempt 事后称为 candidate。
- **continuation contract(所有 candidate 同一语义)**:
  candidate chunk(计为第 1 个 chunk)→ 冻结标准 Pi0.5 续跑(与 `pi0_pick`
  完全同构的 closed-loop:同 prompt、总 chunk 预算 24(含 candidate)、同
  早停阈值 descent 0.10 / lift 0.05 / closed 0.06、同 libero 终止语义)
  → physical verifier(见下)。
- **Stage P 检验的命题(§5 原文操作化)**:"Can selecting the initial
  sampled action/chunk change downstream recovery probability?"——不是
  "rank complete future trajectories"。
- **continuation 随机性处理(§7)**:seed 不可控(J0/vla_server 无注入口,
  上述 2.1)→ repeated continuation,**R_CONT = 3** 次/prereg 冻结(编号见
  prereg §F),candidate 级结论按 3 次 continuation 聚合。
- **physical verifier / 标签**(P1 §12 操作化,与 Stage O §5.1-FG 同源):
  测量点 = candidate chunk 后 + 每 continuation chunk 后 + 终态,每次
  `sim_measurement` + `check_success`。判定优先级 RECOVERY > HARM > NO_EFFECT:
  - **RECOVERY**:任一测量点满足 FG 契约(目标物 z − z(t0) ≥ +0.03 m 且
    xy 距 EEF ≤ 0.10 m)或 `check_success() == True`;
  - **HARM**(非 RECOVERY 时):终态或任一测量点出现——目标物 dz < −0.03 m
    或 dxy > 0.08 m(N1 harm 反向口径,Stage O RE3 同源),或任一物体
    z < 0.80 m(离桌/压入),或 EEF 出合法包络 x(−0.60,0.35) y(−0.45,0.50)
    z(0.80,1.35)(Stage O RE2 同源);
  - **NO_EFFECT**:其余;
  - **INFRA_FAILURE**:restore 读回 ≠0 / vla 崩溃 / chunk_step RPC 异常 /
    重放异常——不进 policy denominator(§35)。

## 4. 结论(接口层面,非 gate 判定)

当前栈下 candidate 的唯一合法粒度 = **初始 action chunk(H=5 × 7 维)**;
它满足 §4 四条件中的 A/B/D,C(重放稳定性)是经验问题,由
`stageP_replay_qualification.csv` 的 ≥12 candidate × ≥3 replay 测量回答;
P0 gate 判定见 `stageP0_decision.md`。
