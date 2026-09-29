# Stage K §0 — 已有资产 / 媒体审计(只读,2026-09-29)

_对象:Stage H / I0 / J0 收口后的 RPent 栈。目的:判定 K(分布式图世界模型)
所需的媒体/数据/执行基建是否成立。本审计零代码改动、零模型训练。_

## 结论先行

**不触发 STOP。** 七问均有肯定或可实证答案,但有一条结构性事实必须先说清:

> **历史语料里不存在任何一次"图边被物理执行"的 transition。**
> Stage H 的图是纯建议(90% violation,边从未被执行);J1 被取消。
> 因此 (snapshot, graph_edge, rollout) 三元组**只能靠 K 自己生成** ——
> 而生成它所需的全部仪器(snapshot/restore 逐位精确、确定性渲染、
> 逐物体位姿测量、12 条可执行边、20 fork 参考成本)已在 J0 全部就位。

即:K 的数据集是"采集型"而非"考古型";历史媒体的作用是**选点与
provenance**,不是训练对本身。伪 frame / future summary 一律不用。

三条量化约束(详见 Q4/Q6/Q7):
1. 家族覆盖不均:FG 富(80 h1 fire / 113 h0 点)、RPS 中(18/18)、
   **MCS 薄(6/17),其中 MOVE_STALL 历史上只有 2 个点、h1 为 0**;
2. family × task 强耦合(FG≈t3、MCS≈t9、RPS≈t9 为主),按 task×seed
   切分时 TEST 集的家族覆盖必须先验算再冻结;
3. 重放态 ≈ 历史态但**不等于**(J0 实测中位差 1.7cm)—— WM 输入必须
   取自 snapshot 本身再生成的帧,禁止混用历史 png(Q7 纪律 2)。

---

## Q1. 每个 physical transition 能否对齐全链七元组?

分两层回答:

**历史层(planner 实际动作的 transition)——能,逐字段有证据:**

`toolkit._step`(robots/libero/toolkit.py:59-104)的时序是
**先执行命令、后 dump**:`dump_state`(robots/libero/tools.py:904-989)
把 `command`(action + 全部 kwargs)、`result`、`elapsed_s` 合并进步记录,
并从同一次 raw obs 快照写全部媒体。因此 states.json 第 N 条记录 =

```
(command_N 已执行, result_N, state_after_N)  +  image_NN / depth_NN / wrist / world
```

失败态 T(step_idx = T,fire 由 result_T 触发,如 pi0_pick success=false)
的七元组对齐关系:

| 七元组 | 来源 | 存在性 |
|---|---|---|
| frame_before | `images/image_T.png`(Pi0 帧 256)+ `images_cam/image_T.png`(标定帧)+ wrist | 每步必写,实测 148/148 h1 集 states==images==depths |
| structured_state_before | 记录 T `state`(eef_pos/quat/gripper_qpos/object_names)+ `result_T` + transition dataset `runtime_view` | 有,但**刻意不含物体坐标**(tools.py:935-946 白名单) |
| action + parameters | 记录 T+1 `command`(action + 全 kwargs,prompt 全文) | 有 |
| frame_after / option-terminal frame | 记录 T+k 的 image(动作终点的下一个 dump) | 有(planner 动作) |
| structured_state_after | 同上记录 state + result | 有 |
| verifier outcome | **无图边版本**;历史只有 `validated_w5`(planner 后续 5 步窗口代理,非边结局) | 缺 → K 自产 |

**生成层(图边的 transition)——由 K0/K1 采集,仪器全部 J0 验证过:**
restore_state 返回 wrapped obs(含 main_images,**逐位可复现**,机制探针
T2/T3 全 0);边链执行后同样可 dump / sim_measurement;结局分类公式
已在 `stageJ_graph_spec.md` §5 冻结(FG/RPS/MCS 三族 + HARMFUL 统一式 +
20 步判定窗口),**但 §5 verifier 的可执行实现尚未写**(原是 J1 差距件
#6)——K0 采集器要先落地它。

## Q2. 原始 RGB / depth / segmentation 是否仍存在?

**存在,且远超预期**(实测 `logs/ovpm_exp/20260929-04:23:24_..._h1C_t3_s1_r1`):
154G 媒体全在盘(logs/ovpm_exp,1810 个 episode 目录)。

| 媒体 | 路径模板 | 粒度 | 备注 |
|---|---|---|---|
| RGB 主视角(Pi0 帧,180° 旋转) | `images/image_NN.png` | 每步 | 256px |
| RGB 标定帧(与 depth/K 同帧) | `images_cam/image_cam_NN.png` | 每步 | 像素→深度→回投影直接可用 |
| RGB wrist | `images_wrist/…` | 每步 | |
| RGB 高清 | `images_cam_hi / images_wrist_hi` | 仅感知步(1024) | 例:7 步集里 5 个 hi 文件 |
| depth | `depths/depth_NN.npy` + `depths_wrist/` | 每步 | **公制米**;camera_meta.json 带深度范围 |
| 世界坐标 xyz map | `world / world_hi / world_wrist(_hi)` | 每步(低清)/感知步(高清) | |
| segmentation | `segments/segment_NN_ii.json` + overlay png | **稀疏:仅 segment 工具被调的步** | h1 148 集中 28 集有,共 39 文件;json 含 box/centroid/score/mask_shape/world_xyz |
| 整集视频 | `episode.mp4` | 全集 | 20fps 渲染,定位用 |
| 相机内外参 | `camera_meta.json` / `wrist_meta_NN.json` | 静态/每步 | |

注意:`videos/` 848 mp4 的旧 bundle 本地已不在(原始 36G 在旧服务器/
HF;logs-index.jsonl 1018 行在 repo 根)。**真正的 per-step 媒体在
episode 目录内,不受影响。** segmentation 不是每步通道 → §4 的
"已有可靠 target mask 做 pooling"前提**不成立**,默认走 DINOv2
patch 特征,mask 只在有感知步的样本上作可选附加。

## Q3. episode/task/seed/step 与主实验表能否一一对应?

**能,三路都有硬键:**
- **h1(104 fire)**:transition dataset 每行带 `episode_dir`(绝对路径)
  + `step_idx` + `arm` + `task/seed`;episode 目录名编码
  `{ts}_{tier}_{arm}_{suite}_t{task}_s{seed}_r{rep}` → 直连
  `analysis/outcome_validation_runs.csv`(1113 行,stage/cond/result/dir)。
- **h0(148 点)**:`stageH0_failure_states.jsonl` 每行带 `episode_id` +
  `primitive_step` + `turn`;实测 148/148 目录存在,且
  `images/image_{step}.png` + `depths/depth_{step}.npy` 在位。
- 老语料:repo 根 `logs-index.jsonl`(1018 行)索引 2026-08 批次。

## Q4. 哪些 Graph states 至少存在 2 条 executable candidate edges?

按 `resources/libero/executable_graph_v1.yaml`(12 边 active,冻结于
7e7528e,sha256 0b840b1a)+ h0/h1 实际 legal_edges 统计:

| state | 合法边(实测) | n_h1 / n_h0 | ≥2? |
|---|---|---|---|
| FALSE_GRASP | FG-1(perceive)/ FG-3(offset regrasp);FG-2 guard `target_localized ∧ fails<3` 在 80 次 fire 全未过 | 80 / 113 | ✓(恰 2) |
| RELEASE_PREDICATE_STALL | RS-1 / RS-2 / RS-3 | 18 / 18 | ✓(3) |
| CONTACT_STALL | CS-1 / CS-2 / CS-3 | 6 / 15 | ✓(3) |
| MOVE_STALL | MS-1 / MS-2 / MS-3(结构上) | **0 / 2** | 结构 ✓ 但无样本 |

四个状态全部满足 ≥2;FG 是"恰好 2"的硬下限(K2 该状态的选择题只有
两个选项,FG-1 是感知边、FG-3 是 VLA 边,对比反而干净)。

## Q5. 每条 candidate edge 是否真的可执行?

- **编译层**:12/12 全字段编译通过,零剔除(Stage J §1);executor
  只用已注册原语,零 LLM:pi0_pick(tools.py:202)/ pi0_doubled(:277)/
  move_to(:318)/ release(:606)/ set_gripper(:646)/ segment(:670)/
  back_project(:1773)。
- **物理层证据**:pi0_pick 在 J0 的 20 个 fork 上端到端执行 40 支,零
  infra abort;其余 6 个原语均被线上 planner 大规模使用过。**边"链"作为
  整体(如 RS-2 的 pick→move→release)从未一次跑过** —— 这正是 K0
  采集要做的事,不是障碍。
- **参数化**:binding 全部 runtime 可观测(TASK_LANG / LAST_PICK_PROMPT /
  EEF / OBJ_XYZ / 冻结常量);OBJ_XYZ 由链内 segment→back_project 自产,
  感知无果 → 链中止记 NO_EFFECT(yaml 头部已写死该语义)。
- **未执行过的边要注意**:MS-*/CS-2/CS-3 依赖 pi0_doubled(max_chunks=20,
  单支成本高于 J0 的 pick 支);RS-1 的 guard(actions_since_release≤6)
  在快照点能否满足需在采集时逐点机检。

## Q6. genuine physical failure states 够不够?

| family | h1 fire(集数) | h0 点(集数) | 评估 |
|---|---|---|---|
| FALSE_GRASP | 80(44 集) | 113(71 集) | 富足 |
| RELEASE_PREDICATE_STALL | 18(18 集) | 18(17 集) | 中等 |
| MOVE_CONTACT_STALL | 6(6 集,全 CONTACT_STALL) | 17(16 集:CS 15 + **MS 2**) | **薄**;MOVE_STALL≈不存在 |

family × task 耦合(h1):FG 75/80 在 t3;MCS 6/6 在 t9;RPS 11 t9 + 5 t3
+ 2 t5。含义:
- 三族同表的 K1/K2 可行,但 **MCS 家族的每格 n 很小**,K1 门里
  "≥2/3 families 非负"实际上大概率由 FG+RPS 承担,MCS 只求方向;
- 按照规范要求的 task×seed 切分后,**每个 split 内 MCS 样本可能掉到个
  位数** → 冻结 TEST 前必须先跑家族×split 可行性计数(见 K 差距件 #3)。

## Q7. data provenance / hidden-state leakage 风险?

七条,前四条是硬纪律:

1. **特权物体位姿**:`sim_measurement()` 的逐物体 GT 位姿(J0 冻结通道)
   只许进 **verifier / analysis_only**,禁止进入 WM 的 structured state
   或任何 runtime 输入(stageJ_graph_spec.md §5.4 已写死该边界,K 沿用)。
   运行时可见的物体定位只有 segment→back_project(OBJ_XYZ)。
2. **重放态 ≠ 历史态**:J0 实测 prefix 重放落点与历史 step T 差中位
   1.7cm / 最大 11.4cm(Pi0.5 推断非确定)。K 的每个 snapshot 是
   **自洽的独立物理状态**:WM 的 RGB / structured_state 必须取自
   snapshot 时刻再生成(restore → obs,逐位可复现),**禁止**把历史
   `image_T.png` 当作该 snapshot 的 frame 混入训练。历史媒体只用于
   选点 / provenance / analysis_only。
3. **同 snapshot 的所有 rollout 必须同 split**(规范已令);同 episode
   的多 fire 共享 prefix,亦不可跨 split(spec 的 task×seed/episode 切分
   已覆盖,执行时按 episode_dir 分组)。
4. **K0 calibration 快照禁入最终 TEST**:需要 snapshot registry
   (episode_dir, T, replay 元数据, 用途标签)在选点时一并落盘。
5. analysis_only 字段(episode_sr / validated_w5 / 后续轨迹)与 runtime
   输入分文件存放(沿用 I0 嵌套 schema 实践)。
6. **Pi0.5 采样 seed 不可控**:J0 证明 eval 模式下同 obs 推断本身非确定
   (maxdiff 0.235),且 vla_server 无已知 seed 旋钮 → 规范里的
   common random numbers 大概率**不可用**,K0 只能靠 K 次重复 + CI;
   不得为此改 Pi0.5 语义(规范红线)。
7. media 索引噪声:hi-res 媒体只存在于感知步(不是每步);segments
   稀疏 —— 构造 §3 数据集时这两类字段按"存在才填"处理,不得当作
   全量通道。

## 附 1:K 直接可复用资产清单

| 资产 | 位置 | 状态 |
|---|---|---|
| executable graph v1(12 边全字段) | resources/libero/executable_graph_v1.yaml + analysis/stageJ_graph_spec.md | 冻结,直接用 |
| snapshot/restore/check_success/sim_measurement RPC | robots/libero/env_server.py(:raw_obs 后新增)+ env_client.py | J0 验证(restore 60/60 bitwise) |
| 逐物体命名位姿测量(14 维块) | 同上 sim_measurement | J0 布局断言通过 |
| 重放/分叉 runner | scripts/stagej0_fork_validation.py | 直接改造成 K0 采集器 |
| 结局分类公式 | stageJ_graph_spec.md §5(三族 + HARMFUL + 20 步窗口) | **公式冻结,实现待写** |
| 失败态选点池 | stageH_transition_dataset.jsonl(104 h1 fire,episode_dir+step_idx)+ stageH0_failure_states.jsonl(148 点) | 冻结 |
| J0 20 fork 基准 + 机制探针 | analysis/stageJ0_*.jsonl/json | 分布噪声的先验 |
| 主实验表 | outcome_validation_runs.csv + stageH1_results.json | 冻结 |
| 视觉 encoder(§4 DINOv2) | — | **未下载**;transformers+timm 在 vla 环境在位,按 hf-mirror 经验可取;训练前须冻结版本+哈希 |

## 附 2:成本算术(J0 实测外推,单 GPU 顺序)

- 单支执行:vla 支(pick 14 chunk)中位 **14.4s**;脚本支中位 **5.2s**;
  整 fork(prefix 重放 + 4 支 + 3 次 restore)中位 **112s**。
- K0 校准量级:6 快照 × 2.5 边 × K=16 ≈ 240 支 × ~35s ≈ **2.5h**
  (含 restore/判窗),开发机纪律内(单 worker + .runlocks + preflight)。
- K1 数据集:快照数 × 边数 × K_ROLLOUT —— 规模由 K0 冻结的 K 决定,
  属 K0 预注册内容;若预算超 ~1h 级,按机器规则转 Training Task 评估。

## §0 裁定

**媒体对齐成立,不 STOP。** 进入 §1/§2 前置条件核对:graph 边语义
复用 v1 冻结件(§1 零改动);K0 需先落地 §5 verifier 实现 + snapshot
registry + split 可行性计数(差距件),再写 stageK0_prereg.md。
