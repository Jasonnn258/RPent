# Stage M 最终报告 — Recovery Abstraction Study(2026-10-01)

研究问题:"对具身恢复来说,短可执行边是不是错误的复用控制抽象?"
(M0 离线 Recovery Abstraction Audit → 仅 M0 PASS 才跑 M1 三臂验证)

## 判定

**M0 MEASUREMENT INVALID → Stage M STOP(§7)。**
人工盲审 agreement:label 29/33=87.9% <90%,FID 29/33=87.9% <90%。
三档判定(§9)不可达;M1 未运行、未编译任何 option。

## 过程数字

- 池:696 行 inventory − 24 L_HELDOUT_TEST = 502 集;fires FG 162/RPS 192/MCS 53;
- analyzer(确定性,零 LLM):187 段 = OPTION 137 / MACRO 27 / EDGE 1 / UNRESOLVED 22;
  RESOLVED 165:OPTION 83.0% / MACRO 16.4% / EDGE 0.6% / FID 83.6%;
- 盲审:33 份卷宗(分层 FG 14/RPS 17/MCS 2,seed 20261001,排除 3 条抽查段),
  人工 32×OPTION/true + 1×MACRO/false;
- agreement:29/33 / 29/33(双 FAIL,差 1 条过线)。

## 机制层发现(对后续最有信息量)

1. **机械判据的系统性盲区**:4/33 分歧全部同向(人工 OPTION vs 机械 MACRO),
   全部 RPS,全部同一模式 —— "read_image 确认后分支 → move_to 低位(同族)
   → 复用 prompt repick"。根因:A 条件要求相邻动作对**换族**
   (`stageM0_analyze.py:284-291`),观察夹在同族 MOVE 对之间不计;
   E 条件要求 prompt 新颖(`:329-340`),配方复用不计。
   池内 27 个机械 MACRO 中 24 个含观察+pick(RPS 23)→ 漏判规模吻合。
2. **误差方向保守**:漏判只会把 OPTION 错标成 MACRO,不会反向 →
   真实 OPTION 率 ≥ 机械 83.0%。方向性支持"短边不是正确抽象",
   但 §7 是测量有效性门,方向不能替代一致性,不据此判 PASS。
3. **term-only 验证占 92.1%**(152/165;中途 pick_lift 11 + move_ok 2):
   绝大多数"成功恢复"只有集终止一个可验证时刻 —— 与 Stage L 的
   term 型机制发现同向;任何中途 branching 契约在 RPS 上离线近乎不可评。
4. **观察门控在事件层不可辨,在 transcript 层可辨**:dossier_21(零观察,
   纯配方,人工 MACRO/false)与 dossier_22/23/26/28(先看图再套同一配方,
   人工 OPTION/true)是同任务同种子的天然对照 —— 决定抽象层级的是
   "分支是否依赖 t0 后信息",而这恰是冻结事件判据测不到的维度。
5. 分族结构:FG FID 97% / MCS 89% / RPS 72%;RPS 既是漏判集中地,
   也是验证最难地(谓词只在集终止可评)。

## 十问直答

| # | 问 | 答 |
|---|---|---|
| Q1 | 成功恢复的最小可复用单位? | **方向性=closed-loop option**(人工 32/33 OPTION、漏判保守),但机械测量无效,不构成正式判定 |
| Q2 | 若需 option,必要的是 longer horizon 还是中间反馈? | 人工证据一致指向**中间观察/grounding/验证/分支**;每一例 OPTION 的分支点都在 t0 后观察上;longer horizon 无独立证据(唯一 MACRO 例是配方复用,非长序列规划) |
| Q3 | edge→option 升级是否真正提高物理 recovery? | **n/a**(M1 未运行,§7 STOP) |
| Q4 | analyzer 测量工具有效吗? | **FAIL**(label/FID 双 87.9%<90%)|
| Q5 | 分歧的机制? | A 同族括号 + E prompt 复用,单一模式、单向、集中 RPS(4/33)|
| Q6 | 中途可验证性? | 92.1% term-only;中途验证证据仅 7.9% |
| Q7 | 分族差异? | FG 97%/MCS 89%/RPS 72% FID;RPS 同时是漏判与验证双难地 |
| Q8 | memory 配方复用意味着 MACRO 吗? | **不**:配方本身 open-loop 可表达,但是否**启用**取决于观察门控(21 vs 22 对照);事件层判据测不到这一层 |
| Q9 | 偏离与局限? | 6 条偏离记录(prereg 末节)+ §17' 五条已知局限 |
| Q10 | 资格重启(修判据重审)? | **须另立预注册**:A′(同族对+观察、后继异族动作依赖该观察时计入)+ 全新抽样盲审;禁止本轮内修补重审,禁止复用 33 份样本 |

## STOP(§7/§18)

- Stage M 就此结束:不跑 M1、不编译 options、不做 full-episode campaign;
- Stage L 冻结结论不受影响(其判定建立在 L 自己的门上);
- 一切恢复类后续实验(含判据修订重审)须另立预注册。

## 工件索引

| 文件 | 内容 |
|---|---|
| `analysis/stageM_prereg.md` | 预注册(3a1a6a1)+ 运行后偏离记录 6 条 |
| `analysis/stageL_pool_inventory.jsonl` | 池 inventory(Stage L §0) |
| `analysis/stageM0_recovery_segments.jsonl` / `stageM0_event_annotations.jsonl` / `stageM0_abstraction_labels.csv` | analyzer 输出(5e44d3f) |
| `scripts/stageM0_analyze.py` | 确定性 analyzer(5e44d3f) |
| `scripts/stageM0_audit_dossiers.py` | 盲审卷宗生成器(seed=20261001) |
| `analysis/stageM0_audit_dossiers/dossier_00–32.md` | 33 份盲审卷宗(仅原始工件) |
| `analysis/stageM0_audit_sample.csv` | audit_id→segment_id 分层抽样映射 |
| `analysis/stageM0_manual_audit.csv` | 人工作答(先落盘后比对) |
| `analysis/stageM0_decision.md` | M0 判定:agreement FAIL → STOP + 根因 + 池级诊断 |
