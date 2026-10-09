# RPent · 阶段级研究授权（Research Package A）

> 用户于 2026-10-09 在对话中明确同意“阶段级授权，执行 Research Package”。这是用户对当前 Research Package A 的**具体研究工作范围授权**，不代表工具/服务器账号许可的替代，不构成生产部署许可，不授权无边界的未来任务。
>
> 目标：一次性完成 EERD v0.1 内部构建与 Stage2J v2 A0 工具反馈离线普查，省去按字段逐项请示。研究结果以实际运行回传为准。

## L1 · 本阶段已授权的离线研究

可在已有 RPent / Stage R collect / R1 冻结资产上：
1. 读取现有私有轨迹的原始 `pi0_pick.result.success`、sim 测量等 audit-only outcome；执行字段资格检查、三值 FGONLY 标签、A0 六件套描述性普查、episode 级聚类区间和敏感性分析（必须严格依照 Stage2J v2，发现无法满足的资格/估计条件则 STOP）。
2. 为 EERD v0.1 建立**内部**分离的 online_eligible / audit_only / reconstruction_metadata 导出、假名化、跨子集分组与数据质量验收；保留 source hash/provenance。
3. 运行本阶段分析脚本的离线测试、完成只读 QA、输出本地审计结果和研究报告；维护研究文档、Git 提交**代码和不含私人原始内容的摘要**。
4. 允许为修正已发现的程序错误改离线分析代码，但不得据 outcome 后验改变阈值、主构念、选择规则；遇到实质问题停止受影响步骤并说明。

**L1 的一次授权涵盖上列步骤**：检查 B 不再单独请求一次许可，随后允许一次性 outcome 分析。A0 原候选为 `DRAFT_NOT_FROZEN`，本阶段代码必须明确实现/保留其版本，原始冻结协议不回写；如果候选规定的对象不可辨识，报告阻断而非重写结果对象。

## L2 · 未在本阶段获得授权

新仿真/rollout、前瞻 C cohort、策略干预、在线 verifier/recovery/Planner 接线、新模型训练、写回 Evolution Gate。未来可按整阶段（协议、预算、对照、停止条件）一次申请，不能以 L1 代替。

## L3 · 始终需要单独批准

真实机器人动作、生产部署、不可逆或大规模数据删除、公开或对外转移用户私有数据、超预算大规模训练/实验。

## 安全不变量

- `Stage R §36 HARD STOP` 与 `S1-DEV0 ON_HOLD` 继续约束 L2/L3；本授权仅新增**只读现有数据的 L1 分析**。
- 原始 Stage R/Q 数据、快照、冻结 prereg/results 只读；输入绝不覆盖。审计真值 **只进 audit-only**，不得进入在线可消费数据、训练特征或外部 API。
- 阶段报告包含：脚本/源代码版本、文件哈希、样本计数、UNKNOWN/缺失账本、Gate、局限和 commit；**没访问服务器就不得声称实际实验已跑**。
- 若当前执行环境没有服务器私有数据，可以交付可复现代码并提供**一条服务器命令**完成后续步骤；把状态标记为 `AWAITING_SERVER_EXECUTION`，不冒充完成。

## 授权记录

- Research Package A：**APPROVED_L1_SCOPE**（2026-10-09，用户会话授权）。
- 单次授权涵盖 QA → A0 → 内部 EERD 物化 → 基线研究报告。
- L2 C cohort/P1 干预：**NOT_AUTHORIZED**。
- L3：**NOT_AUTHORIZED**。
