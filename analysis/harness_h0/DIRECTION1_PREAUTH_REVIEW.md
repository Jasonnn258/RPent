# RPent H0 Direction 1 — Pre-Authorization Scientific Audit

> 2026-10-09 | **只读研究审查，不是实验预注册，也不是执行授权**。
> 基线：RPent `17a2991676c91be3fe608d08ac794985e46253f7`；依据 `analysis/harness_h0/HARNESS_OPPORTUNITY_REVIEW.md` §6、`analysis/harness_next/{METHOD_SPEC,METHOD_CONSISTENCY_REPORT,NOVELTY_REVIEW}.md` v0.2.1、`analysis/stageR_prereg.md` §8 和 `analysis/STAGE_R_FINAL_REPORT.md`。
> **边界**：不读取/重算原始 trial 数据，不写统计脚本，不写/冻结新预注册，不执行 H0 数据定标、rollout 或运行代码改动。Stage R §36 Hard STOP 生效，S1-DEV0 ON_HOLD。

## 1. 执行前的裁决

**METHOD v0.2.1 规范层：GO；原 H0 Direction 1 草案：REVISE BEFORE AUTHORIZATION。**

研究方向仍值得推进，且现有 Stage R 数据可望用于离线验证；但 H0 §6 的 H-OE1/2/3 还不能原样直接预注册并运行，原因是部分目标存在定义循环、标签泄漏或作用域越界。此裁决仅要求**重新界定科学对象**，不推翻原有 H0 总结、Stage R 冻结结论或 MCF 收官。

## 2. 四项主要科学风险

### G1 — H-OE1 的契约“假阳率”可能由定义自动得到

H0 §6.1 原话：
> “以 ACQ 契约单 episode 接受‘技能已修复/已掌握’时…瞬态假阳率 ≥30%… STABLE 契约将假阳率压到 <10%。”

如果“真值”本身使用与 STABLE 完全相同的稳定持有测量，那么以 `STABLE=1` 作为判定规则、再用 `STABLE=1` 作为正确性金标准，`P(truth=0 | STABLE=1)=0` 是**定义后果**，无法算作检测或契约的泛化性能。

- **必须先明确三个不同对象**：决策时可观察的 `acceptance_signal`；独立的 `reference_outcome`；预定的 `verification_horizon`。
- 若只有同源 ACQ/STABLE 判分：允许研究“宽/稳契约下的接受率、分歧率和未来状态差异”，但**不得宣称降低独立假阳率或能准确识别‘已修复/已掌握’**。
- 若独立的时间窗口/延后结果或合法证据代理在现有资产中并不存在：如实报告 `NOT_IDENTIFIABLE`，不能通过重复计算同一标签来制造检验结果。
- H0 引用的 ACQ−STABLE ~35pp 是数据中的已有差异，不能单凭重新命名为“假阳率”就当成新研究贡献。

### G2 — H-OE3 的 E/P 分流最小试数具有事后标签泄漏风险

Stage R 冻结定义：E = SAME≥2/8，A = SAME0/8 且 POLICY≥2/8，P = 双臂0/8，U 为一次成功边缘带。用**同一整段 8+8 重复结果**定义 E/P，再从其中抽前 k 次评估“预测 E/P 的最小 k”时，标签会以规则性方式包含预测证据本身。

- 完整 E/P 是 `ex-post descriptive label`，不是独立观测的 latent skill type，更不是永不恢复的 ground truth。
- 审批前须另行界定预测目标：有限重试后的**未来未观察结果**，或可清楚说明依赖结构的剩余片段预测；是否能构造干净的前缀/后缀评估，属于未来获批后的预注册事项。不能用已观察到的前缀当作“验证标签”的一部分而宣称独立性能。
- 只用 24 个精选失败事件、P=5 且全部 t9 的现有数据，可能不足以稳定识别最小试数或 ≥2× 的门槛。结果若宽或不可辨识，应明确 `INCONCLUSIVE`。
- 统计单位必须承认同一个 event 的重复尝试具有聚类相关性，不能把 24×16 记成 384 个独立 failure events。

### G3 — H-OE2 的 iid / sham 问题须与 M0/M1/M2 正确对齐

H0 §6.1 草案 H-OE2 仍以“`h(k)` 显著低于 iid binomial(`q_hat`)”为候选核心，并尝试将其解释成连败独立信息。

MCF v0.2.1 已确定：
- M0 同质 iid：观察性偏离不能当作已拒绝；
- M1 事件间异质、给定事件 iid：`h(k)` 随选择下降是合理预期；统计充分性由成功/失败计数表达；
- M2 顺序存在额外信息：不能由对比池化边际率得出。

因此：
- 在**科学主张层**，M0 与 pooled q 的差距不足以证明“连败顺序的新信息”；要避免把 M1 的混合选择效应当作新机制。
- H0 提议的 event 内 sham 顺序置换属于未来可考察 M2 的对照；但事件若只有每臂 8 次，M2 可能不可辨识/低功效。不能据 `sham≈observed` 宣称 M2 不存在。
- Stage R 的 SAME/POLICY 尝试每次重建 `S_pre`，不是自然连续重试产生的物理状态演化；顺序效应若出现还须审视时间漂移、执行环境和动作采样。
- H-OE2 需区分**描述性混合风险**与**真实非可交换时序机制**两个待检验对象。正式统计建模与门槛设定须另行授权。

### G4 — 离线重建下的证据不能直接支持在线止损或 Skill 缺陷断言

- Stage R 分母是以**一次 FALSE_GRASP 已发生**为前置的 24 个事件；初次失败不计入独立重试证据，也不能直接外推到新 episode。
- SAME/POLICY 两臂在冻结 `S_pre` 的离线重复尝试，和运行时从 `S_post` 直接继续是不同分布/不同干预。离线“再尝试是否成功”的结论不能自动授权在线 `REPORT_FAILURE` 或 `CONTINUE`。
- 数据也不能直接支持“改变 Skill 后能否修复”，因为该反事实动作空间未观测。候选审查资格与技能晋升必须继续分离。
- MCF `METHOD_SPEC §5.6` 的 `observed_execution_prefix` / `offline_replay_cohort` / `cross_episode_history` 分层必须贯穿未来任何离线校准；privileged 仿真真值仅用于离线科学审计，不可泄漏为将来在线模型/Controller 的输入。

## 3. 方法学预审核对项（不得当作已批准的预注册）

1. 定义问题：`estimand` 是物理 outcome 合同不一致、未来失败预测、还是 persistent 分流？每个研究问题是否有与预测输入**相互独立或明确依赖**的判分对象？
2. 数据可辨识：现有 CSV 能否独立支持 H-OE1 的参考真值、H-OE3 的未来验证片段？若不能，是否主动缩减研究问题？
3. 比较基线：任何主张都要区分 pooled constant-q、event-heterogeneous exchangeable-q、真正顺序依赖，而不重复 v0.1 的 M0 错误。
4. 决策后果：测试假设与后续 Runtime/Evolution 权限分离，离线结果不是自动在线授权。
5. Novelty：任何 Beta-Binomial、可靠性估计、sequential stop 或统计阈值属于可复用经典工具；独立贡献候选是**物理证据可比性、重建不确定性、双合同与决定类型的共同约束**，要接受可能仅为系统化应用的负面结论。
6. S1-S3 停规 / 样本量、簇单位、独立验证与外推条件须在**将来获明确批准后**才做正式预注册，不能在本文件中产生冻结协议。

## 4. 接下来怎么做

**当前获准**：保留 MCF 方法稿，归档本科学预审，用此文识别未来 H0 Direction 1 的资格条件，更新 research-sync 中的待决策事项。

**当前未获准**：H0 Direction 1 预注册冻结、离线拟合/检验、实际数据分析、脚本创建、rollout、在线系统接线、S1-DEV0。

**等待用户的独立授权语句示例**：
> “批准 RPent H0 方向 1 的纯离线研究：先依据 DIRECTION1_PREAUTH_REVIEW.md 修订并冻结预注册，审查通过后只用 Stage R 现有数据做统计定标（0 env boot，无新 rollout）；保持 Stage R §36 Hard STOP 与 S1-DEV0 暂停，完成后报告 GO/REVISE/STOP。”

如果用户暂未明确放行，此项目后续可继续相关论文全文核验、机制比较与研究路线论证，但不得将那类工作写作已完成的新实验。
