# Stage G — Suite 审计(从代码枚举,2026-09-20)

权威来源:pip 安装的 `liberopro` 注册表
`.../site-packages/liberopro/liberopro/benchmark/__init__.py`
(`BENCHMARK_MAPPING` :15-27;Pro 扰动 suite 动态注册 :774-789);
任务名 = 基础 suite 任务表别名(`benchmark/libero_suite_task_map.py`
:1156-1169,每 suite 10 个 task)。RPent 侧 `robots/libero/spec.py:3-21`
只是 dashboard 建议名,不做校验,不作为枚举依据。
bddl:`<liberopro>/bddl_files/<suite>/<task>.bddl`;init states:
`<liberopro>/init_files/<suite>/<task>.pruned_init`(每 task 50 个,
seed→state 映射 `robots/libero/env_server.py:90-98`)。

## 1. 注册表中全部 16 个 LIBERO-Pro suite

`{libero_spatial, libero_object, libero_goal, libero_10} ×
{_task, _swap, _lan, _object}`,各 10 tasks。init states 全量核对
(torch 逐文件加载):**除 `libero_10_task` t0(0 states,任务级空洞)外
全部 50/50 可用**。基础 suite(libero_spatial 等)与 `libero_90`、
`with_*` 系列存在但不在本轮范围。

## 2. 角色划分(冻结)

| suite | 角色 | 理由 |
|---|---|---|
| `libero_spatial_task` | **DEVELOPMENT**(不称 unseen,不入主表) | 全部历史观察/调试/trigger 设计(Stage A-F)发生于此 |
| `libero_object_task` | FINAL TEST #1 | 非空间家族、同扰动轴(_task) |
| `libero_goal_task` | FINAL TEST #2 | 同上 |
| `libero_10_task` | FINAL TEST #3(10 tasks 中 t0 机械排除) | 同上 |

选择规则(预注册):取与 DEV suite **同扰动轴(_task/P1)** 的其余三个
基础家族 —— 泛化主张只跨"基础家族"单轴,不混入 _swap/_lan/_object
第二轴(否则跨 suite 泛化与跨扰动泛化混杂);预算允许 3 suite。
其余 12 个 Pro suite(`_swap/_lan/_object` 变体)在本轮不跑、不看不挑。

`libero_10_task` t0(KITCHEN_SCENE3_turn_on_the_stove…)= 注册表级
init 空洞(0 states,`make_env` 会 ZeroDivisionError)→ **机械排除**,
规则"不可运行即排除",非按成绩挑选;该 suite 实际 9 tasks。

## 3. 规模(按真实 benchmark 数量)

- G1 主实验:3 suites × (10+10+9=29) tasks × seeds s1-s5 × r1 × 3 臂
  = **435 episodes**(每臂 145)。
- G2 新增基线:T2/T3 × 同 145 格 = **290 episodes**(T0/T1/T4 复用 G1)。
- G3/G4 subset:见 `stageG_subset_manifest.md`。
- DEV 冒烟:libero_spatial_task 上每新臂 ≤2 episodes(允许,DEV 用途)。

## 4. Suite 页面素材(G4 用,真实库内容)

`resources/libero/suite/` 75 页(8 个 grid:spatial/object/goal/10 ×
task/swap;每 grid 8-10 页),frontmatter(id/scope/suite/regime/
task_id/task_language/evidence)+ 正文(Applicable pattern / Winning
technique)。运行时检索器当前只读 `global/`(61 卡);G4 以旁路目录
追加**非运行 suite** 的页面作为真实 distractor(不改 global 卡)。
池大小(object_task run:75−9=66;goal_task:75−10=65;10_task:75−10=65)。
