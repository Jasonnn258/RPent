# Stage K0 决策文档 — K_ROLLOUT 冻结

_2026-09-30。预注册:`stageK0_prereg.md`(先于运行冻结,commit c5cb86a);
数据:`stageK0_rollouts.jsonl`(384 行)/ `stageK0_distribution_calibration.csv`;
运行日志:`logs/stageK0/full_run.log` + `repair_run.log`。_

## 判定

**K_ROLLOUT = 4**(满足预注册 §5 三门的最小阶梯)。**Stage K 不 STOP**,
进入 §3 数据集构建。

| K | CI_verif 中位 ≤0.30 | 排序一致(vs 下一级)≥0.80 | CI_harm 中位 ≤0.25 | 过门 |
|---|---|---|---|---|
| 2 | 0.329 ✗ | 1.000 ✓ | 0.329 ✗ | ✗ |
| **4** | **0.245 ✓** | **1.000 ✓** | **0.245 ✓** | **✓** |
| 8 | 0.162 ✓ | 1.000 ✓ | 0.162 ✓ | ✓ |
| 12 | 0.121 ✓ | 1.000 ✓ | 0.121 ✓ | ✓ |
| 16 | 0.097 ✓ | —(无下一级) | 0.097 ✓ | ✓ |

注:K=4 的 CI_harm 中位 0.245 恰在门(0.25)内侧 —— 按预注册机械取最小
过门 K,不做酌情上浮;完整阶梯表在 CSV,读者可自检 K=8 的更宽裕裕度。

## 运行账(含两处执行器 bug 与补采,全部留档)

- 主跑:6 快照 × 16 组合 × k=1..16 = 256 组合槽,ok=224 / infra=96;
- **bug 1**(RS-1):binding 嵌套 `${}`(RS-1 `home='${eef}'`,全图唯一
  实例)只展开一层 → 第二步 move_to 收到字面 `"${eef}"` 报 ERROR,
  t3s5/t3s7 RS-1 ×32 条无效(fix commit 223ad2a);
- **bug 2**(CS-1):运行期绑定 `${mask_rows}/${mask_cols}`(segment box
  取整)不在解析名字空间 → back_project 报未绑定 ×96 infra 行;FG 快照
  segment 恒 found=False 早退掩盖了此路,CS 快照感知命中才触发
  (fix commit de2a64b,含 1024 坐标系一致性核对);
- 补采:`--only` 定向 4 组合 ×16 = 64 rollouts,64/64 ok、0 infra;
  分析器按 (snapshot,edge,k) 后写覆盖,bug 期记录与新记录均保留在 jsonl;
- **偏离声明**:预注册 §8"单遍执行"被 2 次 infra 级修复+定向补采打破;
  判定依据是修复后的完整 16×16 数据,修复先于 K_ROLLOUT 判定与任何
  K1/K2 数据存在 —— 无结果侧泄露通道;
- 仪器红线:全部 288 条有效行 restore 读回 ==0.0(J0 基准保持)。

## 分布事实(K=16 终值,平话)

- 同一快照同一边重复 16 次,结局**确实是一个分布而非定值**:
  FG-3 在两个 FG 快照上 12/16 成功、带 2/16 与 0/16 伤害;CS-2 在
  t9s8 上 9/16 成功 7/16 无效果 —— J0 的"单次 rollout 不可作反事实"
  在 16 组合上全部成立;
- 感知边(FG-1/CS-1/RS-1 nudge 类)16/16 全 NO_EFFECT:纯感知/微动
  链物理上无效果,符合预期 —— 这正是 K2 要 WM 学会避开的"零杠杆"边;
- 快照间异质性极大:t3s7 RS-2 16/16 HARM(拿物体下探 3cm 再释放必
  坠落)vs t3s5 RS-2 16/16 NO_EFFECT —— 边的好坏取决于快照状态,
  静态优先级(图 priority)不可能捕捉,这是 K1/K2 的核心动机;
- 三族(FG/RPS/MCS)在 K0 校准集内全覆盖;MCS 校准快照感知命中
  (CS-1 补采后 back_project 正常走通)。

## 对 §3 的直接指令

- 数据集每 (snapshot, edge) 采 **K_ROLLOUT=4** 条 rollout;
- 预算:FG cap 24 + RPS 10 = 78 组合 × 4 = **312 rollouts ≈ 55 分钟**
  (10.5s/rollout 实测);
- 校准快照(6)永久排除于数据集(manifest 双向登记,prereg §8);
- 采集执行器 = 修复后版本(223ad2a + de2a64b)。
