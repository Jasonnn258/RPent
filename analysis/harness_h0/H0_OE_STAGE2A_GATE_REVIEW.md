# H0 Direction 1 — Stage 2A Read-Only Field Audit & Prereg Draft Gate

> 2026-10-09 | 用户明确批准“只读字段审计与预注册草案，暂不冻结，不运行统计”。
> 依据：`H0_OE_STAGE2A_FIELD_PROVENANCE_AUDIT.md`、
> `H0_OE_STAGE2A_PREREG_DRAFT.md`、Stage 1 三件套、
> `DIRECTION1_PREAUTH_REVIEW.md` 与 Stage R 冻结代码/原预注册。
> **没有执行任何训练、推理/rollout、统计分析脚本、模型拟合、成功率复算、检验或数据修改**。结构记录数只是核对采样完整性，不能被引用为效果指标。

## 1. 裁决

**GO_FOR_NARROW_PREREG_REVIEW_ONLY**（研究性审计与预注册草案已完成）。

同时：
- **OE1a 同源嵌套契约分歧：结构／来源已通过审查**，可以作为下一阶段候选；
- **OE2a 冻结 S_pre 的重试条件风险：试次结构通过，时序因果不通过**，仅能候选描述/回顾性预测；
- **OE3a 前缀→未来 suffix：试次索引结构通过**，数据公开、24 事件且任务不平衡，不能伪称全新盲评；
- **OE1b 独立物理误接受率：NOT_IDENTIFIABLE ON AUDITED SOURCES**，不可直接冻结原 H-OE1 数值指标；
- **M2 真实连续失败时序因果：NOT_IDENTIFIED**，因各次回到 S_pre、三臂固定顺序、缺绝对时间、无随机顺序工具；
- **Runtime/Evolution 授权：HOLD**，本 trial `stable/acquisition` 使用仅科研的 sim measurement；
- **本地 checkpoint schema：NOT_VERIFIED（GitHub 忽略该文件），不推断服务器不存在**。

**正式预注册冻结与任何统计执行均未授权。** 下一次须单独批准，并根据本轮已证边界主动缩窄，不得将初始 H-OE1/2/3 原假设原样复活。

## 2. 已完成的审计验证

| Gate | 具体事实或检查 | 结果 |
|---|---|---|
| A-1 分析所需表是否存在 | SAME、RESAMPLE、manifest、failure_events、event_probabilities 文件远端可读 | PASS |
| A-2 event/arm/trial 唯一完整 | R1 24 cohort；SAME 192=24×8，RESAMPLE 192=24×8，NATURAL 96=24×4；无缺试次/重复键 | PASS（纯结构计数） |
| A-3 与冻结 manifest、事件 JSONL 联接 | 32 个 manifest/事件 JSONL 一致，8 DEV、24 R1；trial task/seed/t0 与 manifest 对齐，回顾报告记录不作重分析 | PASS |
| A-4 outcome 的代码来源 | 两标签都基于同一 cps 的 `stageQ_rt._confirms`；`stable→acquisition` 的源码逻辑蕴含 | PASS；非独立参照 |
| A-5 物理 outcome 的权限 | sim `check_success` 与 sim `pos/eef` 在 `stageO_rt.measure` 读取；Stage R CSV 无时间点级 visibility | PASS 作为**权限限制**：不合法上游代理 |
| A-6 实验顺序、时间戳 | 源码 arm 顺序固定 SAME→RESAMPLE→NATURAL；`trial` 递增；`wall_s` 是单试次时长 | PASS 记录性质；真实物理时间漂移不可识别 |
| A-7 snapshot/prefix 溯源 | cohort manifest method PREFIX，三 SHA16 格式齐；SAME/RESAMPLE recon 字段齐，NATURAL 自然无 recon_sha | PASS 仪器索引，不等于完美反事实 |
| A-8 checkpoint JSONL 全文件 schema | 用户本地扫描 **484 条记录、12,641 个 cps**；顶层/测量点一级键一致，`malformed=0`、`empty_cps=0`，未发现命名含 `time/stamp` 的字段路径（搜索深度有限） | **FULL_SCHEMA_PASS / NO_INDEPENDENT_REFERENCE_IDENTIFIED** |
| A-8b CSV ↔ checkpoint 逐试次键对账 | Stage R CSV 所含 SAME 192 + RESAMPLE 192 + NATURAL 96 = **480** 个逻辑 trial，checkpoint JSONL **484** 条；尚未做两侧 `(event_id,arm,trial)` Counter 差集 | **KEY_RECONCILIATION_PENDING**，必须排查 4 条数量差异的来源 |
| A-9 原始 trial outcome 的效果统计 | 未计算成功次数、区间、h(k)、性能差异或任何模型结果 | **NOT_RUN，符合本阶段限制** |
| A-10 Stage R §36 + S1 边界 | 没有修改 Stage R 任何代码/原始/冻结 prereg；E14/A1/P5/U4 仍引用原终报 | PASS |

## 3. 上一阶段四项风险现在怎样？

- **G1 同源真值循环 → 科学问题已收缩**。冻结源码证实两标签共享 checkpoints 与 `check_success`；OE1a 可以测合同分歧，OE1b 的独立误接受**在现有远端证据下不具资格**。
- **G2 事后标签泄漏 → 研究目标已替换**。E/A/P/U 仍是 8+8 的 ex-post 描述。OE3 若以后获批，严格以 trial 1..k 为输入、k+1..k+m 为 held suffix，训练/评估按整个 event 分组。
- **G3 异质性选择 → 模型解释已对齐**。M0 仅弱参照，M1 必需，M2 仅作为有时间/顺序混杂的探索问题；没有重新拟合或宣告任何假设被拒绝。
- **G4 S_pre→S_post 外推 → 严格限定**。NATURAL 始于 S_post 只描述；所有科研合同/预测都限定于冻结 S_pre 重建实验，不能直接支持在线止损或 Skill 修复。

## 4. 待用户授权的下一动作

推荐 **Stage 2B：正式预注册审阅与冻结准备**（仍不含统计执行）。该阶段的首要任务必须是：

1. 审阅和确定只保留可识别的 **OE1a、OE2a、OE3a**；OE1b、M2 真实因果和“latent E/P 分类最小试数”保留 STOP/探索性降级；
2. **用户已完成全文件只读 schema 检查**：484 条记录/12,641 个 checkpoint 字段集合一致、零解析错误，`meas/obs` 键名已扫描、未发现 `time/stamp` 命名字段；但 CSV 仅有 480 个已审计逻辑 trial。**当前的主要待办是在已有 Stage 2A 权限内做全文件 `(event_id,arm,trial)` 键对账，不运行结果统计**。不能把 FULL_SCHEMA_PASS 误作 FULL_KEY_JOIN_PASS；
3. 明确事件整体切分、候选 k/m、主要评价量、M0/M1 基线、功效/不确定性、缺失和停止准则；审核已有结果披露导致的回顾性偏差；
4. 创建单独正式冻结文件，并要求**另一次明确用户批准**后才可冻结。Stage 2A draft 永不作为冻结文件；
5. 未来真实统计运行须第三次独立授权，任何 rollout/训练/Controller 仍在 Stage R §36 禁区。

**服务器本地只读 schema 补查可按已批准 Stage 2A 立即开展；Stage 2B 仍需单独批准，否则保持 HOLD。** 此文和本次审计结果可直接提供给 Codex 做下一阶段的研究协议检查，不能据此启动分析。

## 5. 交付边界与诚实声明

本次仅新增 Stage 2A Markdown：
- `H0_OE_STAGE2A_FIELD_PROVENANCE_AUDIT.md`
- `H0_OE_STAGE2A_PREREG_DRAFT.md`（显式 DRAFT_NOT_FROZEN）
- `H0_OE_STAGE2A_GATE_REVIEW.md`

未变动先前 Stage 1 文件、冻结 Stage R prereg、原 trial CSV、脚本或模型。所有结构数量来自字段完整性/事件 join 检查，不是任何新效果统计。没有访问或修改服务器原始运行环境。

**最终：Stage 2A 全文件 checkpoint 字段结构已核验，新增 484 vs 480 条记录的键级差异，故 `FULL_SCHEMA_PASS / KEY_RECONCILIATION_PENDING`。仅允继续 Stage 2A 的只读键对账；Stage 2B、正式冻结、统计/在线实施继续 HOLD。**
