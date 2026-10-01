# Stage M0 判定文档 — Recovery Abstraction Audit(2026-10-01)

## 判定(一句话)

**M0 MEASUREMENT INVALID → Stage M STOP(§7 冻结条款)。**
人工盲审 agreement:label 29/33 = **87.9%** < 90%,FID 29/33 = **87.9%** < 90%,
双项未达标 → analyzer 的标签测量被裁定无效,§9 Gate 不可评估,M1 不启动。

## §7 盲审执行记录

- 抽样:n_audit = ⌈0.2×165⌉ = 33,按 family 分层(FG 14 / RPS 17 / MCS 2),
  seed=20261001,排除 3 条开发期抽查段(SPOT_CHECKED);
- 材料:`analysis/stageM0_audit_dossiers/dossier_00–32.md`,仅含 states.json 原文
  + transcript 窗口消息原文(thinking 截 400 字 / tool 结果截 800 字),
  不含任何 analyzer 事件标注、标签、FID 或聚合结论;
- 人工作答:33/33 逐份仅凭材料给 label+FID,先落盘
  `analysis/stageM0_manual_audit.csv` 后比对;
- 人工分布:**32×OPTION_REQUIRED/FID=true + 1×MACRO/false**
  (dossier_21:窗口内零观察,纯按 memory 配方执行,与 dossier_22 构成同任务
  同种子的 observe/no-observe 对照对)。

## agreement 计算

经 `stageM0_audit_sample.csv`(audit_id→segment_id)join
`stageM0_abstraction_labels.csv`:

| 项 | 一致 | 比率 | 门槛 | 结果 |
|---|---|---|---|---|
| label | 29/33 | 87.9% | ≥90% | **FAIL** |
| FID | 29/33 | 87.9% | ≥90% | **FAIL** |

(过线需 ≥30/33;差 1 条。)

### 分歧明细(4 条,全部同向:人工 OPTION/true vs 机械 MACRO/false)

| audit_id | family | 模式 |
|---|---|---|
| dossier_23 | RPS | 撤退→read_image 确认碗坐盘→**move_to 低位**→repick(prompt 复用) |
| dossier_26 | RPS | 同上 |
| dossier_28 | RPS | 同上 |
| dossier_31 | RPS | 撤退→侧清(同族 move)→read_image 揭穿碗倾斜→move→repick(prompt 复用) |

### 根因(analyzer 两处冻结严格性)

1. **A 条件**(`scripts/stageM0_analyze.py:284-291`):要求**相邻**物理动作对
   **换族**(`af(a)!=af(b)`)且发射之间有 OBSERVE/GROUND。上述 4 例中
   read_image 夹在 `move_to(撤退)→move_to(低位预定位)` 两个同族 MOVE 之间,
   随后的 pick 与前一个 move 之间又无观察 → A 不触发;
2. **E 条件**(`scripts/stageM0_analyze.py:329-340`):pick prompt 需 ∉ t0 前
   prompt 集。4 例的 repick prompt 与 t0 前完全相同(memory 配方复用)→ E 不触发。

即机械判据系统性漏判"**观察门控决策 → 同族重定位 → 复用 prompt 重抓**"模式;
人工判 OPTION 的依据是该分支确由 t0 后观察决定(若图像显示碗不在盘上会走别的路)。

### 池级诊断(仅注记,不改标签、不进任何 gate)

27 个机械 MACRO 段中 **24 个窗口含观察且含 pick**(RPS 23 / FG 1)→
漏判模式的池内规模与盲审比例吻合。误差方向**保守**:真实 OPTION 率应
**高于**机械测得的 83.0%,绝不会更低。但 §7 为测量有效性门,方向性
不能替代一致性 —— 不得据此改判 PASS,亦不得在 Stage M 内修 A/E 再重审
(即 prereg 禁止的"看分歧→回去改判据→重测"循环)。

## §8 指标(上下文引用;因测量无效不作为判定依据)

- 四比率(分母 RESOLVED=165):OPTION 83.0% / MACRO 16.4% / EDGE 0.6% /
  UNRESOLVED(总池 187)= 22;
- FID rate(RESOLVED)= 83.6%;
- 分族:FG 71 段(O 69/M 1/E 1,FID 97%)、MCS 9 段(O 8/M 1,FID 89%)、
  RPS 85 段(O 60/M 25,FID 72%);
- 首次可局部验证位置:tR_reason = terminated 152 / pick_lift 11 / move_ok 2
  (UNRESOLVED 22 无 tR)→ **92.1% 的成功恢复只有集终止这一个可验证时刻**,
  中途验证证据仅 7.9%(与 Stage L "term 型"机制发现同向);
- 分布明细见 `stageM0_abstraction_labels.csv` /
  `stageM0_recovery_segments.jsonl`(analyzer 输出,#135 已 commit 5e44d3f)。

## §9 Gate(冻结数字)

**NOT EVALUATED — 测量无效。** 若仅看机械数字(OPTION 83.0%≥60%、
EDGE 0.6%≤25%、FID 83.6%≥50%、FG/RPS 两族 RESOLVED≥15 且方向一致)
形式上会过门,但该测量已被 §7 裁定无效,此段仅作记录,不构成判定。

## 后果

- **Stage M STOP(§7)**;M1(§10-17 三臂 matched 验证)取消,不编译 options;
- Stage L 结论(§0)不受影响:GRAPH EVOLUTION NOT SUPPORTED 等判定
  建立在 L 自己的门上,与 M0 测量无关;
- 对后续最有信息量的两条:(1)"短边是错误复用抽象"的**方向性证据增强**
  (人工盲审 32/33 OPTION、漏判方向保守、92% term-only 验证);
  (2)任何复活实验须**另立预注册**:修订 A′(允许同族对+观察、后继异族
  动作依赖该观察时计入)与新抽样盲审,不得复用本轮 33 份样本。

## 工件

- 盲审卷宗:`analysis/stageM0_audit_dossiers/`(生成器
  `scripts/stageM0_audit_dossiers.py`,seed=20261001)
- 抽样映射:`analysis/stageM0_audit_sample.csv`
- 人工作答:`analysis/stageM0_manual_audit.csv`(先落盘后比对)
- 机械标签:`analysis/stageM0_abstraction_labels.csv`(+#136/#135 的
  `stageM0_recovery_segments.jsonl` / `stageM0_event_annotations.jsonl`)
- 本判定:`analysis/stageM0_decision.md`
