# METHOD_V02_REVIEW — v0.2 方法论修订审查与判定

> 2026-10-09 | 审查对象:`METHOD_SPEC.md` v0.2 + `NOVELTY_REVIEW.md` v0.2
> (v0.1 均见 git 历史 commit `adf5d18`)。
> 输入:用户 v0.2 指令(六项方法论阻断问题)+ Stage R 预注册/终报口径
> (`analysis/stageR_prereg.md`、`analysis/STAGE_R_FINAL_REPORT.md`,
> 本轮全文复读)+ Zetta main 分支源码核验([S-ext],六项机制,行号级)。
> 输出:逐项修复对照、连带一致性修订、剩余问题、**GO/REVISE/STOP 判定**。
>
> 边界:本轮零实验、零 rollout、零代码改动;Stage R §36 Hard STOP 与
> S1-DEV0 暂停继续生效;v0.1 旧版经 git 历史完整可追溯。

---

## 1. 六项阻断问题 → 修复对照(总表)

| # | 用户指出的阻断问题 | v0.1 错误位置 | v0.2 修复 | 状态 |
|---|---|---|---|---|
| 1 | 单次失败被错误归类为 E(事后标签与在线判断混用) | METHOD_SPEC §5.3(E: ∃y_i=1 单证据即可,"最保守归类")+ §9.1 场景 A(n=1→E) | §5.0 新增判断对象二分(事后标签 vs 在线持续性判断,含在线三档);§5.3 类集扩为五类,新增 **DETERMINING**(默认态),E 需序列内出现过成功;R1 拆 R1a(有成功→E)/R1b(n=1→DETERMINING);§9.1 场景 A 重推演;与 Stage R 预注册口径对齐(E=`same≥2/8`,预注册本有"禁据单次成功赋 latent type"纪律,v0.1 反比预注册宽松——错误根源之一) | ✅ 已修 |
| 2 | 缺 heterogeneous iid / 样本异质性 / 连败选择效应分析;连败记录何时提供额外信息不明 | §5.2("h(k) 远低于 iid 边际 → 连败史携带超信息",混淆同质/异质 iid) | §5.5 新增三层框架:M0 同质 iid(连败无信息)/ M1 异质 iid(可交换混合,连败=低 p 的后验证据,选择效应,不需要时序依赖)/ M2 非可交换(真时序,sham 检验);三结论:①相对 M0 有信息 ⟺ F 非退化;②相对 M1 有信息 ⟺ M2 成立;③止损判定的证据基础在 M1 层即成立。§5.2/§9.3 锚点措辞同步修正;h(k) 的跨事件池化分母结构(17 个事件-臂)正是 M1 选择效应的典型载体 | ✅ 已修 |
| 3 | PA-Attr 未区分统计关联/失败持续性/因果归因/可修复性;重复失败可滑向 Skill Defect | §7.1(单字段 failure_class 混 L1/L2;causal_grade 隐含 L1→L3 通道) | §7.1 输出改四层显式结构(L1 association / L2 persistence / L3 attribution / L4 repairability,各层独立证据独立语义);§7.5 新增**层间推导白名单**(D1/D2 允许,X1-X4 禁止);P 语义收窄为 PERSISTS_UNDER_TESTED_POLICY_SPACE(SAME/POLICY 双臂只覆盖已测动作分布);X1 显式禁止 P→Skill Defect(需跨策略族证据+修复反事实,均在可观测范围外) | ✅ 已修 |
| 4 | Runtime/Evolution Gate 全局授权单调性错误(被自身授权矩阵违反) | §0 公理 A2 + §6.4("Evolution 门 ≥ 一切 Runtime 门")+ §8.2(ARCHIVE 零门槛 vs REPORT_FAILURE 高门槛的自相矛盾) | 公理 A2 改**代价对齐授权**;§6.4 重写:反例显式化(零门槛 Evolution 决策 < 高门槛 Runtime 决策),替换为 A2a(局部代价对齐:门槛随错误代价非递减,代价可比对上)+ A2b(不可逆性约束:不可逆决策 ≥ 一切可逆决策——v0.1 直觉的正确形式);§8.2 矩阵新增六决策的错误代价轴(假阳代价/可逆性/影响半径)并做代价对齐检验 | ✅ 已修 |
| 5 | Temporal Evidence Claim 时间逻辑错误(历史已确认状态被未来事件否定) | §4.3(CONTRADICTED 无时间窗约束)+ §4.4(仅三律)+ §9.2 场景 B(`Held[o,[t1,t2]]` CONFIRMED 后被 t3 滑落改成 CONTRADICTED) | §4.1 claim 结构新增 `window_type`(RETROSPECTIVE 闭窗 / PROSPECTIVE 开窗);§4.3 转换表按闭窗/开窗分列 CONTRADICTED 触发条件 + 终态行(闭窗终态无转换);§4.4 增第四律"闭窗终态不可否定";§9.2 场景 B 重推演:t3 滑落作用于开窗 `Maintained(o,t2→)`,闭窗 `Held[o,[t1,t2]]` 保持 CONFIRMED | ✅ 已修 |
| 6 | Zetta 事实错误:已具备 inconclusive diagnosis / unresolved group,v0.1 判"归因克制空白" | NOVELTY_REVIEW §1.2("归因克制/UNKNOWN:无,空白✓";"重建保真降级:无")+ §1.3/§7 | Zetta main 分支源码级核验([S-ext],本轮):unresolved group(stages.py:92)、inconclusive 终态(lifecycle.py:3456)、no_actionable_cluster_diagnosis、inconclusive gate(models.py:731)、provisional authorization、shadow replay 不完整→inconclusive 保留、以及关键自证"Confidence ranks hypotheses but is not evidence from a live intervention"(默认不作授权门)。NOVELTY_REVIEW §1/§6/§7 全面更正:"允许 abstain 的立场"让渡(●),"不完整重放不作对照"让渡(●);N1 再收缩为"abstain 的**统计学判据**"(C2-b:证据量函数/异质性后验/连败信息价值 + C2-d);撞车矩阵 Zetta 列 C2-a/C2-c ○→◐ | ✅ 已修 |

---

## 2. 修复的验证方式(本审查执行的核对)

1. **自洽性核对(问题 4)**:新 A2a/A2b 对照 §8.2 全部 48 格逐一检查——
   ARCHIVE/QUARANTINE 零门槛↔代价近零;REPORT_COMPLETION 需 L2+↔信用损耗;
   PROPOSE_REVIEW 四重条件↔难逆跨 episode。无违反对。v0.1 全局命题在
   v0.2 矩阵下的反例(ARCHIVE<REPORT_FAILURE)已作为设计依据显式登记。
2. **时间逻辑核对(问题 5)**:对 §4.3 转换表穷举"未来事件 × 三种 claim 状态"
   组合——闭窗终态(CONFIRMED/DISMISSED)无任何出边;开窗 claim 的
   CONTRADICTED 仅由 now 之前的证据链断裂触发;新 claim 生成不受限。
   v0.1 场景 B 的非法转换(`Held` CONFIRMED→CONTRADICTED 跨窗)已删。
3. **口径对齐核对(问题 1)**:Stage R 预注册 §8(E:same≥2/8;U:恰 1 次
   成功边缘带;"禁据单次成功赋 latent type")与 v0.2 规则映射检查——
   v0.2 语义下限(∃y_i=1 ∧ n≥κ_min)与预注册(≥2 成功)的差距收敛到
   κ_E 定标槽位;Stage R U4 在 v0.2 语义下属"E-证据不足边缘带"而非
   "证据矛盾",该重分类列为未来数据分析项(§4 剩余问题 P3)。
4. **统计语义核对(问题 2)**:h(k) 表(STAGE_R_FINAL_REPORT §5.3)的
   分母结构(跨事件-臂池化:连败 3 次的 17 个事件-臂)与 M1 框架的
   预言结构一致(池化条件率随 k 下降可由异质混合+选择效应产生);
   终报 Q6 措辞("连击数才是强预测子")未声称时序依赖——v0.2 的 M0/M1/M2
   分层与既有报告措辞兼容,且把 H-OE2(sham)定位为 M2 的正式检验。
5. **外部事实核对(问题 6)**:Zetta 六项机制全部取得源码行号级证据
   (tarball 解压于 /workspace/yjx/tmp/zetta_v02check/,main 分支,
   2026-10-09 下载);NOVELTY_REVIEW 的每处更正均标注 [S-ext]。

## 3. 连带一致性修订(非用户点名,为保持规范内部一致)

| 项 | 位置 | 内容 |
|---|---|---|
| 演化门伪代码注释 | METHOD_SPEC §6.3 | `∉{P,A}` 注释更新为 DETERMINING/E/U 类 |
| N2 表述 | NOVELTY_REVIEW §0/§7 | "授权单调偏序"→"代价对齐偏序+不可逆性约束"(随问题 4) |
| 术语表 | METHOD_SPEC 附录 A | 新增闭窗/开窗、事后标签/在线判断、M0/M1/M2、四层结论、代价对齐;E/A/P/U 行更新 |
| 局限清单 | METHOD_SPEC §10.4 | 新增三条:M1 未定标、Zetta 论文未读、U4 待重分类 |
| 风险登记 | NOVELTY_REVIEW §9 | 新增 R4(N1 判据无实质内容则退化)、R5(Zetta 论文数学化表述) |
| 文档头 | 两文件 | 版本 v0.2 + 变更日志(§0.1);v0.1 经 git adf5d18 可追溯 |

---

## 4. 剩余问题(如实登记,均不阻断概念评审)

| # | 问题 | 性质 | 处置建议 |
|---|---|---|---|
| P1 | **M1 框架未定标**:异质性分布 F 拟合、sham(M2)对照、κ_info 后验定标均未执行 | 数据分析缺口(非规范缺陷) | H0 方向 1(H-OE2/H-OE3)获批后执行;此前 N1 的统计学内容保持"待检验"措辞 |
| P2 | **Zetta 论文全文未读**:本轮 [S-ext] 仅源码级;论文若含 unresolved 判据的数学化,R5 触发 | 核验深度限制 | 获论文后补核;NOVELTY_REVIEW 已标注 |
| P3 | **Stage R U4 重分类未做**:v0.2 语义下 U4 属"E-证据不足边缘带" | 既有标签的口径迁移 | 与 P1 同批离线处理(读 stageR_event_probabilities.csv 即可,零 rollout) |
| P4 | **N1 内容对定标工作的依存**:Zetta 让渡克制立场后,N1 完全落在统计判据上;若 P1 不执行,N1 退化为对 Zetta 工程出口的重述(NOVELTY_REVIEW R4) | 战略风险 | 概念评审时用户应把"是否批准方向 1 定标"与"是否接受 N1 为主线"作为联动决策 |
| P5 | **在线三档判断与 Runtime 门的接线未细化**:§5.0 三档(NO_INFORMATION 等)与 §6.2 门的接口只给了语义,无规则表 | 规范完成度 | 实现阶段细化(须另立授权);当前规范层语义自洽 |

---

## 5. 判定

### 5.1 逐项验收

| 验收项 | 结果 |
|---|---|
| 六项阻断问题全部修复且修复位置可定位 | ✅(§1 表;METHOD_SPEC §0.1/NOVELTY_REVIEW §0.1 变更日志) |
| 修复后规范内部自洽(无已知内在矛盾) | ✅(§2 核对;v0.1 的五处内在错误全部消除) |
| 与 Stage R 预注册/终报口径对齐 | ✅(E 规则、h(k) 措辞、U 语义差异已显式登记) |
| 创新声明与外部事实一致(Zetta 更正落地) | ✅(N1 再收缩;两条 ● 级让渡;矩阵更新) |
| 旧版可追溯性 | ✅(v0.1 = commit adf5d18;文档内变更日志) |
| 边界纪律(零实验/零代码/§36/DEV0 暂停) | ✅(本轮仅文档 + 外部源码只读核验) |

### 5.2 总判定:**GO(有条件)**

**GO 的根据**:

1. 用户指出的六项方法论阻断问题**全部修复**,且每项修复都顺带消除了
   v0.1 的一处内在矛盾(自洽性恢复:方法现在是"统计上自洽"的——
   证据语义分层明确、时间逻辑无非法转换、门槛公理与矩阵一致);
2. 修复后的方法**保持独立研究价值**(用户目标第二半):N1 收缩为
   "失败持续性与弃权的统计学判据"后仍有无 ● 级撞车的空间,且 Zetta
   源码自证其置信度非证据、默认不作授权门([S-ext]),反而强化了
   "证据力统计定标"空白的可信度;
3. Persistence-Aware Attribution 作为核心方法的地位经三层加固:
   四层输出结构(语义清晰)+ 层间白名单(类型纪律)+ M0/M1/M2 框架
   (统计解释地基)。

**条件(与 NOVELTY_REVIEW R4/R5、本文件 P1-P5 对应)**:

- **C1**:N1 的"统计学判据"必须最终获得实质内容(P1 定标工作,即 H0
  方向 1)——在此之前 N1 的一切表述维持"待概念评审,非实测";
- **C2**:Zetta 论文全文(P2)与 RegenHarness/VASO 全文(R1)任一后续
  核验若发现统计判据层表述,按预设收缩条款执行再收缩,不硬撑;
- **C3**:任何实现、在线接线、常数定标、实验设计仍需另立阶段另行授权
  (§36 与提案 §7 程序不变;S1-DEV0 维持用户暂停)。

**不判 REVISE 的理由**:本轮六项修复互相独立且已闭环,无已知的规范层
遗留缺陷(P1-P5 均为数据/核验/实现层面的后续工作,不是规范错误)。
**不判 STOP 的理由**:核心创新空间(N1 收缩后)经源码级核验仍然成立,
且方法的统计自洽性经本轮修复后反而强于 v0.1。

### 5.3 下一步(供用户决策,非本轮执行)

1. **概念评审**:是否接受 v0.2 收缩后的 N1(统计学判据)为研究主线,
   以及 P4 的联动决策(N1 主线 ⟺ 批准方向 1 定标);
2. 若接受:H0 方向 1(H-OE1/2/3)预注册冻结 → 离线定标(纯离线 0 boot,
   既有数据)——它同时是 P1/P3 的处置路径;
3. 若不接受:方法线收官归档(v0.2 文档已是自洽的负资产记录),
   不影响 Stage R/Q 既有结论。
