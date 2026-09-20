# Stage G — 冻结清单(Freeze Manifest,2026-09-20,任何 G 运行之前)

基础 commit:`b8fc2f2`(Stage F0 收口)。本清单连同 suite audit / trigger
baseline config / subset manifest 一起 **commit 先于任何 Stage G episode**
(含 DEV 冒烟)。§25 禁止事项全程适用。

## 1. 方法冻结

### 1.1 Progress Trigger(论文方法,T4/M2)
- 实现:`rpent/memory/retrieval.py` `DecisionMemory` mode `"progress"`
  (per-result 评估 :249-304,边界 flush :433-488,planner 接线
  `rpent/planner/api_loop.py:1044-1062)。
- 规则 R1-R5(冻结于 Stage C2,`analysis/memory_stageC2_design.md`):
  R1 perception 观测不可用;R2 move 未到达且 EEF 无进展;R3 pick 报成功
  无抬升 / 连续 2 次失败 pick;R4 contact-skill 失败叠加;R5 release 后
  predicate 未触发。
- 阈值:`MOVE_EPS=0.005`,`MOVE_ARRIVED=0.03`,`LIFT_OK=0.05`
  (retrieval.py:180-182);cooldown `COOLDOWN_BOUNDARIES=2`,上限
  `MAX_TRIGGERS_PER_EPISODE=6`(retrieval.py:60-61)。**一字不改。**
- 选择 env:`RPENT_MEMORY_TRIGGER=progress` + `RPENT_STRUCTURED_MEMORY=1`。

### 1.2 对照触发器
- M1/T1 旧启发式(v1,Stage B 冻结):`RPENT_MEMORY_TRIGGER=1`,
  规则 T1-T7(retrieval.py:307-359),其 73% 误触发路径 = T4 重复规则。
- T2_PERIODIC / T3_MOTION_STUCK:新增 **baseline**,配置见
  `stageG_trigger_baseline_config.md`;实现只增不改(不动 1.1 代码路径)。

## 2. 检索冻结
- Q0 词面(部署版):`_q0_fixed`(retrieval.py:518-526),token 集重排 +
  >0 截断 + top-3,`RPENT_MEMORY_RANK=Q0_FIXED`。
- Q3 强检索(Stage A/B 冻结版,不许调):`_q3`(retrieval.py:528-552),
  bge-small-en-v1.5 语义召回 top-20 + 冻结结构重排权重
  W_SEMANTIC=2.0 / W_APPLIES=0.6 / W_SYMPTOM=0.4 / W_ACTION=0.5 /
  W_PHASE=0.4,`RPENT_MEMORY_RANK=Q3`。已知 ~7.6s/次 CPU 开销,保持一致。
- Episode-起点记忆访问:`RPENT_MEMORY_ACCESS_FIX=1`(system prompt 路径
  重写,`robots/libero/prompts/system.py:404-462`);三臂全部开启。

## 3. Memory bank 冻结
- 运行时 bank = `resources/libero/global/` 61 张卡 + 索引
  `resources/libero/MEMORY.md`(`load_cards`/`load_index`,
  retrieval.py:76-112)。**内容零修改、不加 alias、不动正文。**
- G4 压力 bank:只以"额外真实页面目录"方式追加
  `resources/libero/suite/` 的**其它 suite** 页面(真实库内容,规则见
  subset manifest §3);61 张 global 卡与索引不动。

## 4. 模型与执行参数冻结
- Planner:GLM `anthropic:glm-5.3-flash`,remote API
  `https://open.bigmodel.cn/api/anthropic`(key 来自
  `/workspace/yjx/rpent_data/rpent_env.sh`);sampling = API 默认
  (代码无显式 temperature,历阶段未动)。
- VLA:Pi0.5,`PI05_CHECKPOINT_PATH=/workspace/yjx/rpent_data/checkpoints/pi05`。
- 感知:SAM3,`/workspace/yjx/rpent_data/checkpoints/sam3/sam3.pt`。
- 原语库 / turn budget 40(`EVAL_TURNS`,ovpm_exp.py:55)/
  `PLANNER_TIMEOUT_S=3600`(:61)/ `RUNTIME_S=4500`(:75)/
  渲染 osmesa / spawn 语义:全部沿用,不改。

## 5. 编排(只增不改)
- 调度器 `scripts/ovpm_exp.py`:新增 G 阶段/cond(suite 参数化从单一
  `P0_SUITE` 扩为 per-stage suite 列表——纯编排);既有 cond
  `memB1`(=M0/T0)、`memB2`(=M1/T1/A)、`memB3`(=B)、`memO2`(=M2/T4/C)
  原样复用;新增 `memO3`(=D:progress+Q3,两 env 正交)与 G4 bank cond。
- 基础设施纪律沿用:preflight + `.runlocks/ovpm.lock` 防重、
  `completed_keys` 断点续跑、infra 重试 ≤3、`infra_missing` 单列、
  **不允许 rerun-until-success**。

## 6. 已知风险(预先声明,不构成事后自由度)
- GLM 远程 API:2026-09-18 曾发生代理事故(Stage C outage ledger);
  G 批量若再遇,按既有 ≤3 重试 + infra_missing 定型流程处理,不换端点。
- `libero_10_task` t0 init states 为 0(注册表级空洞)→ 机械排除,
  见 suite audit;非挑选。
