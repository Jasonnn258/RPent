# Stage G0.6 — Seed Manifest(§4:新 seed 机械选择,先 commit 再运行)

_审计时间 2026-09-22。数据源 = analysis/outcome_validation_runs.csv 全量 +
liberopro benchmark 实测。不假设编号,以下全部为实测结果。_

## 1. 现有占用审计(三臂,libero_spatial_task,repeat=1)

| 臂(stage, cond) | t3 | t5 | t9 | 小计 |
|---|---|---|---|---|
| P0(g05, g05P0) | s1-s10 | s1-s10 | s1-s10 | 30 |
| P2(g05, g05P2) | s1-s10 | s1-s10 | s1-s10 | 30 |
| P4(g0, g0D) | s1-s10 | s1-s10 | s1-s10 | 30 |

三臂现有 30 matched cells 逐格确认存在、编号连续 1-10、无缺口。

## 2. 全局占用(防撞)

对该 suite 三个任务的**整份 CSV**(任何 stage/cond)查询:t3/t5/t9 各自
只出现过 s1-s10。s11+ 从未被任何实验使用。

## 3. seed 合法性与初始状态 disjointness(实测)

env 语义(`robots/libero/env_server.py:make_env`):
`rid = first_id + (seed % trials)`,`trials = len(get_task_init_states(t))`。

实测(vla env,benchmark 初始化日志确认 permutation=[0..9] 恒等):

| task | init-state 池 | s1-s10 → rid | s11-s20 → rid |
|---|---|---|---|
| t3 | 50 | 1-10 | **11-20(不相交)** |
| t5 | 50 | 1-10 | **11-20(不相交)** |
| t9 | 50 | 1-10 | **11-20(不相交)** |

即新 seed 对应**全新初始状态**,不是旧状态的换名重放。

## 4. 选定(机械规则:每任务下一个 10 个未使用合法 seed)

**新 seed = 11,12,…,20;任务 = t3/t5/t9;三臂使用完全相同的新 seed。**

- P0_NO_INTERVENTION:t3/t5/t9 × s11-s20 = 30 集
- P2_GENERIC_REFRESH:同 = 30 集
- P4_FULL:同 = 30 集
- 合计 90 新集;每臂最终 60 matched cells(s1-s10 复用 G0.5 原行,
  保留原始判定,不重跑 genuine policy failure,不重新采样)。

## 5. 执行映射(零代码改动)

| 臂 | 调度命令 | 落行位置 |
|---|---|---|
| P0/P2 | `--stage g05 --seeds 20 --conds g05P0,g05P2` | stage=g05(done-keys 自动跳过 s1-s10) |
| P4 | `--stage g0 --seeds 20 --conds g0D` | stage=g0(同上) |

P4 沿用 g0D 原 cond 原环境运行 —— "Full" 不被重新定义(§5)。
分析器按 (stage,cond) 映射统一读 60 cells。
