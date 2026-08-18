# RPent 研究分析：扰动难度 + 重复感知阻断（2026-08-14）

## 1. spatial_task t3/t7 数据修复验证

**背景**：spatial_task 的 t3（cookie）和 t7（stove）数据文件损坏
（`.pruned_init` 截断为 364B → 0 init states；`.bddl` goal 缺 `And`、括号不配对）。
此前用 spatial_swap 同名文件替换修复。

**验证结论：该替换改变了任务定义，不是忠实修复。**

证据链：
1. 损坏 BDDL 备份（`.gap_run/broken_init_backup/*.broken.bddl`）显示原版 spatial_task
   t3/t7 的目标物体是 **akita_black_bowl_2**（在 cabinet 顶上），语言为
   "Pick the akita black bowl **on the top of the cabinet** and place it on the plate"，
   布局为 **base 式**（plate 在 plate_region，未 swap）。
2. spatial_task 套件其余 8 个任务全部遵循同一 P1 扰动模式：目标 bowl_2 + base 布局 +
   混乱语言标签（例如 wooden_cabinet 任务的 :language 竟是 "on the stove"）。
3. spatial_swap 的 t3/t7 是 **bowl_1**（cookie box / stove 上）目标 + **swap 式**布局
   （plate↔cabinet / plate↔ramekin）。与 spatial_task 意图不同。
4. 因此旧修复把 spatial_task t3/t7 变成了 swap 变体任务，此前 3/10、7/10 数字作废。

**正确重建**（已验证 make_env(3,0)/(7,0) 构建+reset 成功）：
- init_states ← base `libero_spatial` 的同名 `.pruned_init`（场景与损坏原版一致，50 states）
- bddl ← 损坏原版仅修复 goal 为 `(And (On akita_black_bowl_2 plate_1))`
- 指令 = "Pick the akita black bowl on the top of the cabinet and place it on the plate"

**当前状态**：已应用正确重建，`rerun_t37.sh` 重跑 t3/t7（bootstrap + 10 evals）。

---

## 2. 扰动类型对比：task(P1) vs swap(P2)

方法：对相同 (task, seed)，取各 suite 最新 run，比较成功率 / 感知次数 / 动作次数 /
turns / 失败原因。数据 = 原规则（无 guard）批次。

### 2.1 总体成功率（相同 task/seed 配对）

| 对比 | task(P1) | swap(P2) | 结论 |
|---|---|---|---|
| spatial（78 对，排除 t3/t7）| 58% (45/78) | 56% (44/78) | **接近**，swap 略难 |
| goal（70 对）| 61% (43/70) | 50% (35/70) | **swap 明显更难** |

> 注意：spatial_task 的语言标签本身混乱（generator 缺陷），task 变体的语言常描述
> 另一任务；尽管如此 SR 仍 ≥ swap，说明 swap（初始位置互换）对 agent 的扰动更大。
> t3/t7 重跑完成后 spatial 数字将更新。

### 2.2 感知/动作行为（均值）

| 指标 | spatial task | spatial swap | goal task | goal swap |
|---|---|---|---|---|
| turns | 36.7 | 35.7 | 35.8 | 32.2 |
| 感知调用 | 21.9 | 20.7 | 20.1 | 17.4 |
| 动作调用 | 9.7 | 9.6 | 8.2 | 7.6 |
| 最长连续感知 | 8.8 | 8.9 | 9.3 | 8.2 |
| env steps | ~10 | ~10 | ~8 | ~7.5 |

**两套扰动都出现严重重复感知**（最长连续感知 8-9 次），支撑重复感知阻断实验。

### 2.3 主要失败原因（配对 run 分布）

- **spatial task**：placement_fail 28%（主导）、grasp_fail 10%、perception_loop 4%
- **spatial swap**：placement_fail 21%、grasp_fail 17%、early_stop 4%、perception_loop 3%
- **goal task**：grasp_fail 20%、placement_fail 17%
- **goal swap**：grasp_fail 17%、placement_fail 16%、early_stop 9%、perception_loop 7%

**主失败模式**：spatial 系列以 **placement_fail**（成功抓取但 release 未触发谓词，
即放错/没对准目标面）为主；goal 系列 grasp_fail 占比更高。swap 变体比 task 变体
grasp_fail 相对更突出（spatial 17% vs 10%），goal swap 的 early_stop/感知循环更多。

### 2.4 逐任务成功率（原始数据，t3/t7 为旧数据）

spatial: t0 5/11 vs 6/11, t1 4/11 vs 7/11, t2 6/11 vs 10/11, t3 3/11 vs 2/11(旧),
t5 8/11 vs 9/11, t6 4/11 vs 1/11, t7 7/11 vs 4/11(旧), t8 10/11 vs 6/11, t9 7/11 vs 5/11

goal: t1 7/11 vs 4/11, t2 4/11 vs 3/11, t4 5/11 vs 10/11, t7 11/11 vs 11/11,
t8 8/11 vs 5/11, t9 7/11 vs 1/11

---

## 3. 重复感知阻断（guard）最小实验

**实现**（`rpent/planner/api_loop.py`，`RPENT_BLOCK_REPEATED_PERCEPTION=1` 启用，
`RPENT_PERCEPTION_STREAK=3` 阈值）：
- 对 segment / back_project / view_driver_state / read_image，若**连续相同查询**超过
  阈值（第 4 次起），阻断该工具调用，返回提示：要么执行动作、要么获取真正新信息、
  要么 finish。
- 查询签名不同（不同 pixel/prompt/camera/step）或任意动作调用都会重置计数。
- 默认关闭（env 变量控制），保证原版 A/B。

**单元测试**：identical-query 阻断、changed-pixel 重置、action 重置、
changed-prompt 重置、env 关闭均通过。

**A/B 实验**（#35）：`run_guard_exp.sh` 在 spatial_task t0/t7/t9 × seeds1-10 上
用 guard 重跑 eval（输出到独立目录 `.gap_run/guard_exp/`，不污染原 logs/），
与同 (task,seed) 的原版 run 对比：成功率、重复感知次数、动作次数、turns、失败原因。

> 状态：等待 t3/t7 重跑完成释放 GPU 后启动 guard 实验。

---
_数据文件：analysis/suite_comparison.csv（配对明细）、analysis/guard_ab.csv（A/B）_
