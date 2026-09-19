# Memory Study 总结报告:Stage A → B1 → C 全弧(2026-09-17 ~ 09-18)

一句话结论:**动态长期记忆对在线机器人规划要产生净收益,瓶颈不在"查什么/
怎么排"(检索侧),而在"什么时候查"(触发侧)——把触发时刻从重复计数
启发式换成物理进展偏离判定后,同一套冻结的廉价词面检索从净伤害变成了
净收益。**

研究主旨(用户原题):机器人调用长期经验之前,是否必须先形成由真实执行
状态支撑的"我现在发生了什么"的表示?是否只有物理进展偏离预期时才该触发
长期经验检索?——三阶段证据整体回答:**是,且是。**

## 0. 起点(Q0 审计,2026-09-17 前)

Stage A 之前的现状审计发现三断:memory 文件路径 100% 不可达(工具从没
真正读到过卡)、卡片触达率 16%、决策时刻回查 0 次。即"带记忆的系统"
实际上从未用过记忆——一切从修通路径(access fix)开始。

## 1. Stage A(离线诊断,commit d5cb9df/3738b53)

240 个决策点(120 YES/120 NO)离线基准,冻结五条件 Q0-observed/Q0-fixed/
Q1/Q2/Q3:

- **TRIGGER 精度 0/120**:现有触发规则在真决策点上一次都不该火的时刻全火/
  该火的时刻全漏——触发是第一瓶颈;
- 检索侧最好条件 Q3-structured R@3 = 0.592(比 Q0-fixed 的 0.400 高 19pp)
  ——离线看,"换个好的排序"似乎有戏(后来证明是幻觉,见 B1/C1);
- perception 类 0/17 全条件:感知类卡片在任何 query 下都检索不到。

## 2. Stage B1(在线 2×2,commit cfda224)

t3/t5/t9 × 10 seeds,B0/B1/B2/B3 四臂阶梯(修路径 / +旧触发+词面排序 /
+旧触发+Q3):

| 臂 | SR | 配对 | 读法 |
|---|---|---|---|
| B0 历史行为 | .733 | — | 基线 |
| B1 +access fix | **.833** | 5W/2L | **唯一真收益,全在 t9(+4)**:让记忆"能被读到"就值 10pp |
| B2 +旧触发+lexical | .733 | 2W/5L | 触发噪声把 B1 的收益全部吐回 |
| B3 +旧触发+Q3 | .633 | 4W/7L | 离线 +19pp 的排序在线再跌 10pp |

判定 NEITHER SUPPORTED / EXECUTABLE MEMORY NEXT: NO。两个诊断:
①误触发 73%(连续 3 个相同动作分不开真卡住与正常运输);②离线检索
+19pp 不迁移(在线 query 文本贫瘠)。这两个诊断直接生成 Stage C 的
两个假设。

## 3. Stage C(三段门控,commit eec5477/7e5f276/36dcda7/332ffa7)

**C1 — Query Sufficiency(离线,NOT SUPPORTED)**:把在线真实可得的
状态词汇全部塞进 query(phase/last primitive/result fields/pre-post
state/failure_locus),词面 R@3 仅 +1.7pp,perception 仍 0/17,硬负例
不动。机制:query 侧状态词与卡侧索引词表**不相交**——query 丰富度只有
落在卡词表内才变成信号,坐标数字、LOCUS 枚举都不在。query 侧此路不通。

**C2 — Progress-Aware Trigger(离线,SUPPORTED)**:按 primitive 家族
定义物理进展(MOVE 残距/前进量、PICK 假成功/二次失败、RELEASE 谓词、
PERCEPTION 观测有效性、RECOVERY 前后变化),R1-R5 冻结规则重放:
precision .986、误报 69→0、recall .776。顺带修出 Stage B GT 的
pick-name bug(48 个时刻漏计,moments 45→84,判定不变且加强)。

**C3 — 在线单变量 O0 vs O2**(O0 = #49 memB2 原行复用,audit 通过;
O2 唯一差异 = progress 触发;27 有效格 + 3 格网络事故 infra-missing):

| 指标 | O0 | O2 |
|---|---|---|
| 触发 precision | .265 | **1.00**(13/13) |
| 无关注入/集 | 1.2 | **0** |
| relevant@1/@3 | .571 | **.889** |
| SR | .733 | **.852**(配对 +5/−2;vs B1 +4/−2) |
| t3 SR | .60 | **.86** |
| turns / wall | 29.8 / 2465s | 28.5 / 2141s |

三判定:QUERY **NOT SUPPORTED** / PROGRESS TRIGGER **SUPPORTED**
(在线 precision 完全兑现;recall 保守化 .302,人群更健康 + cooldown
drop 语义,如实记录)/ ONLINE COMBINATION **SUPPORTED**。

## 4. 核心论点:时机 > 丰富度(三条独立证据)

1. **C1(离线)**:query 侧加尽真实状态词汇,R@3 纹丝不动(+1.7pp),
   perception 0/17 不动——丰富度不是杠杆;
2. **B1(在线)**:排序侧 Q3 离线 +19pp,在线反而 −10pp——触发噪声
   在,再好的排序也只是把噪声排得更靠前;
3. **C3(在线)**:触发侧换成进展判定,**同一个** .400 离线 R@3 的廉价
   词面检索,在线 relevant@3 直接到 .889、SR 超过无触发基线——时机对了,
   廉价检索就够用。

附带一致性证据:O2 唯一的检索错误事件是 QUERY_INSUFFICIENT(gold 完全
不在词面序里)而非 RANK_WRONG——与 C1 的词表不相交机制完全吻合。

## 5. 负结果与边界(同样重要)

- **t9 perception 词面缺口是结构性的**:C1 判不可修(卡侧词表没有
  perception 现象词),C3 在线复现(3 个 40 轮耗尽失败全在 t9,O2 落后
  B1 两格)。要修只能动卡侧(本轮全冻结,未做);
- **recall/precision 取舍**:O2 recall .302,漏查不伤 SR、误注伤 SR
  (O0 即证明),方向正确但保守程度未调优(cooldown/boundary 语义);
- **硬负例行为未变**:失败集上 retreat 卡进 top3(O2 4/4),只是被
  低频触发兜住;
- **SR 归因谨慎**:O2 相对 B1 的 +2 配对净胜在噪声量级,主收益
  (t3 +26pp)归因于"不再在错误时刻打扰 planner"+"精准时刻的卡片注入"
  的合并效应,soft 注入下无法精确拆分。

## 6. 工程与纪律教训

- **冻结纪律全程有效**:卡库、Q0_FIXED 权重、R1-R5 阈值、B2 verifier
  从 A 到 C 零改动;O0 直接复用 #49 行(compatibility audit);
- **基础设施事故的标准处置**(2026-09-18 代理中断):逐集审计 run.log
  区分真假失败 → 网络 kill 按 ≤3 infra 纪律清账重跑 → 3 格耗尽定型
  infra-missing 不进分母 → 4 个真失败验证保留(38-40 轮、无 API 错)。
  事故特征指纹:0 turns / elapsed≈19s / wall≈100s / rc=0 → classify 误判
  policy_fail,调度器不自动重试——未来批次可加自动识别;
- **离线→在线迁移的三个坑**:①离线人群与在线人群健康度不同(C2 R .776
  vs C3 R .302);②离线指标好不等于在线有收益(A 的 Q3 vs B1 的 B3);
 ③GT 本身会有 bug(pick-name),交叉验证救了一命。

## 7. 产物地图

| 阶段 | 报告 | 数据 | commit |
|---|---|---|---|
| A | analysis/memory_stageA_results.md | memory_stageA_results.json | d5cb9df, 3738b53 |
| B1 | analysis/memory_stageB_results.md(含勘误节) | outcome_validation_runs.csv(memB 行) | cfda224 |
| C1 | analysis/memory_stageC1_results.md | 同名 .json/.jsonl | eec5477 |
| C2 | analysis/memory_stageC2_results.md | 同名 .json | 7e5f276 |
| C3 | analysis/memory_stageC_results.md | 同名 .json + stageC_outage_ledger.md | 332ffa7 |
| 代码 | retrieval.py(progress 分支,v1 冻结)/ api_loop.py / ovpm_exp.py(memC) | smoke+29 集目录 logs/ovpm_exp/ | 36dcda7 |

全部 commit 未 push(用户纪律)。

## 8. 未决与可能方向(不构成承诺)

1. 卡侧词表扩充(perception 现象词)——C1 判定的缺口在卡不在 query,
   是 t9 剩余失败的唯一词面解法;
2. 触发保守度调优(cooldown/boundary-drop 语义消融)——recall .302 的
   上移空间,但每一步都要防误注回潮;
3. executable memory / controller 强制执行——用户 Stage C 规格明确
   暂停项,O2 的 soft 注入已证明无害,为未来对照留了基线;
4. av.py(B3 Active Verification 模块)——研究转向时暂停的休眠代码,
   未跟踪未接线,留待 B 线若复活时用。
