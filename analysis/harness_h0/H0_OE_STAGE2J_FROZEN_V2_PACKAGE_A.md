# H0 · Stage2J FROZEN-V2 — Research Package A L1 授权执行锁

> 2026-10-09｜研究用户已批准 **Research Package A 的阶段级 L1 离线分析**。本文件为 Stage2J v2 的独立冻结执行映射，不修改原 `DRAFT_NOT_FROZEN` 候选、Stage R §36 冻结文件或历史试验数据。**本次冻结发生于首次服务器 outcome 分析之前**；GitHub/本会话不能访问服务器原始私有日志，尚无新实测结果。

- 原方法定义：`analysis/harness_h0/H0_OE_STAGE2J_V2_A0_PREREG_CANDIDATE.md`（v2, `DRAFT_NOT_FROZEN`，保留历史）。
- 授权：`analysis/research_context/RESEARCH_AUTHORIZATION.md`（L1 APPROVED；L2/L3 HOLD）。
- 执行代码：`analysis/research_context/research_package_a.py`；执行入口 `analysis/research_context/run_package_a.sh`；回归测试 `analysis/research_context/test_research_package_a.py`。
- 协议 ID：`RPENT-PACKAGE-A-STAGE2J-V2-EERD-V01-20261009`；代码锁使用每次 schema seal 中的 `analysis_script_sha256` 和每个输入文件的 SHA256；若代码/输入修改，第二阶段必须停止并重新进行 schema/审查。
- 禁止默许更改：主体估计对象、数据样本框、FG 阈值（dz≥0.03, dxy≤0.10）、主 PRIMARY 子集（eligible pick 且原始 `libero_terminated=False`）、缺失状态机、E1–E3 可估性门、episode 聚类单位、评价语言。

## 授权范围内的一次性流程

1. **Schema Seal**：原 Stage2I V1 结构验收复跑；ledger 187、pick 235、chunk 2859、一一对齐及参考内层字段有效性、A1–A3；先发布 `schema_qa.json`。这一阶段禁止基于 outcome 取值作分层或选择。
2. **A0 Outcome Census**：只在 schema PASS 且源文件及分析脚本哈希未变化时，读取原始 `result.success` 和 audit-only 测量；按 `IN_SKILL_ACQ_FGONLY_V1` 三值 POSITIVE/NEGATIVE/UNKNOWN 构造标签。POSITIVE 需任一有效确认；NEGATIVE 需全部应测点有效且无确认；其余 UNKNOWN；缺失不插补。
3. **Shortcut Audit**：仅伴报 `check_success` 旁路对标签的影响，不能混入主 FGONLY 参考。工具 terminal 镜像样本不进 PRIMARY；`episode_truncated` 来自 states step 顶层，PRIMARY_UNTRUNCATED 敏感性单列。
4. **A0 固定报告包**：类别结构；flag × reference 2×2 + UNKNOWN；接受风险/漏报风险及含 UNKNOWN 的下界；一致率 + 两常数基线 + κ；10000 次 seed 20261009 的 episode-cluster bootstrap 95% 描述区间；敏感性和物理构念限制。按任务、首/重试标记报告描述。
5. **EERD v0.1 内部物化**：A 原工具返回合法可消费视图与 research_audit_truth 标签视图物理分文件；B 已冻结 trial 的 audit-only 与 reconstruction_metadata 分文件，并按源 episode 关联；所有输出限 `artifacts/research_package_a/`（gitignored, 内部私有），不公开、不向任何在线模型注入。
6. **Gate 与报告**：E1 合格 pick<100 停；E2 PRIMARY<30 或 flag 某类<10 主量不可估；E3 可判定子类<10 降级指标；schema/trace/来源不一致直接 STOP。任何未通过都保留其原因和计数，禁止后验更换主指标。

## 预注册所支持的最大结论

仅 RPent 单策略、3 LIBERO Spatial 任务、配额停止样本框内的**同技能工具 flag 与物理位姿取得代理的一致性**。FGONLY 不是夹爪真实接触、Planner 返回后的未来持握、任务级 oracle；A0 不能证明 P1 控制收益，也不能凭其数值直接给 P1 episode 错误完成率做功效先验。

Stage R §36 **HARD STOP** 不改；S1-DEV0 **ON_HOLD**；新的 C cohort、Runtime 验证器/恢复或模型训练 **NOT AUTHORIZED**。

**冻结状态：`PACKAGE_A_L1_A0_V2_PROTOCOL_LOCKED_BEFORE_OUTCOMES / SERVER_EXECUTION_PENDING`。**
