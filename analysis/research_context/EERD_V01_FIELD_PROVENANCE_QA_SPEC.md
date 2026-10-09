# EERD v0.1 — 字段级来源、证据权限、样本分组与数据质量验收规范

> 2026-10-09 | **DRAFT / SCHEMA-ONLY / ZERO DATA EXPORT / NO OUTCOME READ**。
> 本文是 `EERD_V01_DATA_CONTRACT_DRAFT.md`(commit `70d57ba`)的**配套规范**,落实其 §6 验收条款 1-4 的字段级细节;不修改原契约草案。
> 源码行号在基线 `4d155b9` 复核:`robots/libero/tools.py:1144-1162,1604-1646,228-272`、`robots/libero/toolkit.py:41-110`、`rpent/utils/rtrace.py`、`scripts/stageR_collect.py:112-167`、`scripts/stageR1_run.py:137-157`。
> 状态:文档设计 GO(Stage2K §4);**物化/导出/打标签仍 HOLD**(DECISION_LOG D-008)。

## 0. 定位

回答四个问题,使 EERD v0.1 从"有 schema"到"可验收物化":

1. A/B 子集每个字段从哪个文件哪条路径来、由哪行代码产生(§1-§2);
2. 每个字段归哪个证据权限视图、能否进任何在线/进化消费(§3);
3. 样本按什么键分组切分、跨子集怎么防泄漏(§4);
4. 物化前必须过哪些数据质量验收门(§5)。

可见性五层沿用 PAEG §5.6:`observed_execution_prefix` / `cross_episode_history` / `offline_replay_cohort` / `research_audit_truth` / `reconstruction_metadata`。

## 1. A 子集(Vanilla Skill Evidence)字段级来源表

原始资产:187 episode 目录,每个含 `states.json`、`stageR_trace.jsonl`、图像工件;外加 collect ledger(CSV)。join 键:`(episode_id, step_idx)`。

| 导出字段 | 来源文件→路径 | 产码(基线行号) | 语义 | 可见性/权限视图 | 质量规则 |
|---|---|---|---|---|---|
| `episode_id / suite / task_id / seed_id` | ledger 行 + 目录名→稳定假名 | stageR_collect ledger | 采集单元标识 | reconstruction_metadata | 唯一、与目录一一对应;假名映射不外发 |
| `step_idx` | states.json 条目 / trace `step_idx` | dump_state / rtrace | 原语步索引 | (键) | states↔trace 100% 对齐 |
| `command` | states 条目 `command` | toolkit._step→dump_state | 该步原语调用 | online_eligible(view_driver_state `log.command` 投影,:1627) | step-0 初始 dump 无 command[S1 P1 已知],标记 `INIT_DUMP` |
| `result.*`(success/diagnostics/chunks_used/libero_terminated…) | states 条目 `result` | tools.py:254-272 构造、:1159 合并 | **D2 工具返回原件** | online_eligible(`log.result` 投影,:1628) | 与 trace step_end.success 一致(断言);**outcome 值在获批前保持 NOT_EVALUATED** |
| `libero_terminated / episode_truncated`(步级) | states 条目顶层 | tools.py:1146-1147 | 步末环境终局/截断旗 | online_eligible(view 投影 :1620-1621) | 与 result.libero_terminated 断言一致(A1,Stage2J-v2 §3.2) |
| `state.robot0_eef_pos/quat, robot0_gripper_qpos, object_names` | states 条目 `state` | toolkit dump | 本体感知状态 | online_eligible(`state` 投影,:1619) | 有限性检查;**grip 双通道陷阱申报**(states[6,7] 展平 ≠ qpos,Stage2E) |
| `world_map / wrist_world_map(+_hi)` | states 条目 | tools.py:1150-1153 | 场景占用图 | online_eligible(投影 :1622-1625) | 存在性/尺寸稳定 |
| `task_language` | states 条目 | tools.py:1148 | 任务指令文本 | online_eligible(:1615) | 逐 episode 恒定 |
| `elapsed_s` | states 条目 | _step 计时 | 步耗时 | online_eligible(log 投影) | 非负 |
| `image_path / image_cam_path / …_hi_path` | 图像工件 | view_driver_state :1631-1645 | 边界可见图像 | online_eligible | 存在性;引用不内嵌 |
| `rtrace.ev/kind/chunk_idx` | trace 记录 | rtrace | 测量点骨架 | reconstruction_metadata | chunk_idx 连续(Stage2I PASS) |
| `meas.obs[f"{target}_pos"]` | trace action/step_end 记录 | rtrace `_meas_now` | **特权物体位姿** | research_audit_truth(audit_only) | 逐点三态 VALID/MISSING/NONFINITE(Stage2J-v2 §2.2) |
| `meas.obs["robot0_eef_pos"]` | 同上 | 同上 | 研究测量 EEF | research_audit_truth(audit_only) | 同上;共享通道申报 |
| `meas.check_success` | 同上 | rtrace | 仿真任务谓词 | research_audit_truth(audit_only) | 仅标签版本引用,禁入在线视图 |
| `meas.obj_of_interest` | 同上 | rtrace | 目标实例清单 | research_audit_truth(audit_only) | 基点非空检查 |
| `t`(每记录绝对时间戳) | trace | rtrace `_emit` | 仪器时钟 | reconstruction_metadata | 非递减(Stage2I PASS) |
| `ledger.classify`(episode 级) | ledger | stageR_collect | 终局失败/成功分类 | audit_only | episode 级,禁当 pick 级资格条件 |

**A 子集标签状态机**:沿用 Stage2J-v2 §2.3 三值(POSITIVE/NEGATIVE/UNKNOWN)+ NOT_EVALUATED 默认;`IN_SKILL_ACQ_FGONLY_V1` 版本化;truncation 用 states 步级顶层字段。

## 2. B 子集(Frozen Failure Persistence)字段级来源表

原始资产:冻结 manifest(32 事件:8 R0_DEV + 24 R1)、`stageR_trial_checkpoints.jsonl`(484 行)、SAME/RESAMPLE/NATURAL CSV(192/192/96)、stageR_snapshots、冻结源码契约。join 键:`(event_id, arm, trial)`。

| 导出字段 | 来源→路径 | 产码 | 语义 | 可见性/权限 | 质量规则 |
|---|---|---|---|---|---|
| `event_id / ord / role` | manifest | 冻结 manifest | 事件标识与角色 | (键) | role=R1_COHORT 才进分析行;4 条 DEV CPS 索引排除(Stage2A 对账) |
| `task / seed / t0` | manifest | 同上 | 事件来源 | reconstruction_metadata | 与源 episode join 用 |
| `arm / trial` | CSV + checkpoint | stageR1_run | 臂与试次 | (键) | 唯一无缺(480/480 已对账[F]) |
| `stable / acquisition` | CSV | stageQ_rt 契约 | 续作协议下研究 outcome | research_audit_truth(audit_only) | 冻结标签版本;**非在线合法证据**(D-003) |
| `cps[*]`(check_success/eef/grip/obj/obs/pos/meas/terminated) | checkpoints.jsonl | stageR1_run 落盘 | 重建轨迹检查点 | research_audit_truth(audit_only) | 8 键 schema 全扫已过[F];无时间字段(`time_field_paths=[]`) |
| `wall_s` | CSV | stageR1_run | 试次耗时 | reconstruction_metadata | 耗时非绝对钟(Stage2A 定案) |
| `reconstruction_method / quality` | 派生自 Q0 决策 | stageQ0_decision | PREFIX/SNAP 等重建方式与保真 | reconstruction_metadata | **APPROXIMATE 上限**(restore 类一致率 10/14<0.90,禁称精确反事实) |
| `parent_failure_event_id` | manifest | — | **聚类键** | (键) | 同事件 8+8+4 全归一 cluster;独立事件数=24 |
| `source_episode_ref` | manifest→episode 假名 | — | A↔B 溯源 | reconstruction_metadata | 进 `cross_dataset_provenance_group`(§4) |

**B 子集边界重申**:SAME/RESAMPLE/NATURAL 是独立重建试验,非真实连续 retry;E/A/P/U 为离线事后标签,不构成 Evolution 写回许可(D-003);Stage2D 回顾性结果只作已发布描述,不改算。

## 3. 证据权限矩阵(三操作视图)

| 视图 | 允许内容 | 允许消费者 | 禁止 |
|---|---|---|---|
| `online_eligible` | §1 表中标 online_eligible 的字段(= view_driver_state 实际投影集 + 图像引用),取值须为**该决策边界真实交付值** | 未来任何 D2 决策研究/复现 Planner 信息集(P1 对照的"合法输入"列) | 含任何 `meas.*` 特权字段;含 check_success/物体坐标;校验器从标签表反拼 |
| `audit_only` | + meas/check_success/三值参考/stable-acquisition/ledger.classify | 研究评价、标签审计、EERD 参考表 | 进 Runtime/Evolution 任何门(PAEG I1/I4);作为训练目标在线泄漏 |
| `reconstruction_metadata` | + 重建方式/保真/时钟/假名映射/源哈希 | 数据溯源、split 审计 | 参与任何评分或模型输入 |

**视图物理分离**:三视图各自独立文件;`online_eligible` 导出必须通过 G-QA-4 的字节级黑名单检查。数值恰同不继承权限(仅投影路径上真实交付过的字段获得 online 资格——EERD 草案 §1 防火墙 1 的操作化)。

## 4. 样本分组与防泄漏

1. **A 子集**:split 键 = `episode_id`(同 episode 全部 pick/步/图像同侧);时间特征只取决策边界前合法可得字段。
2. **B 子集**:split 键 = `parent_failure_event_id`(同事件全臂全试次 + 源 episode 同侧)。
3. **跨子集**:24 个 R1 事件的源 episode 均在 187 语料内 → 定义 `cross_dataset_provenance_group` = {episode_id} ∪ {event_id} 的连通分量;split 以该组为原子单位,杜绝"A 侧训练、B 侧评测"的同源泄漏。
4. **任务层**:仅 3 任务(t3/t5/t9);task-held-out 只作压力测试,不作跨任务族泛化证明;独立 prospective C 子集才具备独立验证资格(草案 §4)。

## 5. 数据质量验收门(物化前置,全过才允许导出)

| 门 | 内容 | 失败处置 |
|---|---|---|
| G-QA-1 join 完整性 | ledger 187↔目录 187↔双文件;186+1 pick 计数;states↔trace 步对齐 100%;B 侧 480 键唯一、4 DEV 排除在册 | FAIL → 物化停止,出差异清单 |
| G-QA-2 对齐断言 | 每 pick 过 A1-A3(result↔states 终局旗一致 / join 完整 / \|Q\|=chunks_used+1);B 侧 checkpoint 数与冻结试次数一致 | 任一不符 → 该样本 OUT + 索引,超 5% → 停 |
| G-QA-3 完整性账本（双阶段） | **先**在零 outcome 读取阶段仅发布字段存在性、数值有限性与测量点可用率（MISSING/NONFINITE 分列）；**后**仅在明确批准标签读数的独立阶段发布 UNKNOWN 率、按 flag 分层及 2×2 表。前一阶段不得生成 UNKNOWN/按 flag 统计 | schema 账本未发布不得启动结果分析；未获 outcome 授权的第二阶段保持 HOLD |
| G-QA-4 视图隔离 | online 视图黑名单扫描(特权字段名 + 物体坐标值抽样)+ 三视图物理分文件 | 泄漏 → 整批重导 |
| G-QA-5 假名化 | 无绝对路径/主机名/时间戳指纹;假名映射仅存 reconstruction 私档 | 泄漏 → 重导 |
| G-QA-6 源哈希钉死 | 导出 manifest 列 source→git blob SHA(或本地 SHA256)→行区间;输入只读 | 哈希不匹配 → 停 |
| G-QA-7 schema 阶段零 outcome 读 | 验证代码白名单:只读键存在性/有限性/计数;禁读 success/check_success/stable/acquisition **取值**;阶段日志留痕 | 越界读 → 该次验证作废重来 |
| G-QA-8 标签纪律 | 所有 outcome 字段默认 NOT_EVALUATED;任何衍生标签必须新版本号;冻结标签不可回写 | 违规 → 版本作废 |

**八门中的 schema-only 部分可在不读取 outcome 值的条件下设计和验收；任何涉及 UNKNOWN / 按 flag 分层 / 标签值的验收，须进入独立获批的 outcome 阶段。** 全套验收通过后才可称“可物化”；物化、对外发布和 benchmark 计算仍各自需用户授权(D-008)。

## 6. 与 Stage2J-v2 / P1 的接口

- Stage2J-v2 的检查 B + 断言 A1-A3 = G-QA-1/2 在 A 子集 pick 粒度的实例化;A0 若获批执行,其资格计数表可直接作为 EERD-A 的 G-QA-3 首块;
- `online_eligible` 视图 = P1 对照实验中"合法输入"列的定义来源;`audit_only` 三值参考 = P1 评价用的独立审计真值来源(仅评价,不进策略输入);
- P1 需要的 C 子集字段(草案 §5)在本规范中不加定义——C 的字段来源只能是未来新采集,不得从 A/B 派生。

状态:`EERD_V01_FIELD_PROVENANCE_SPECIFIED / QA_GATES_G1_G8_DEFINED / NOT_MATERIALIZED / EXPORT_AND_LABELS_HOLD`。
