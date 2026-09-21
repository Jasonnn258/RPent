# Stage G0.5 — 方向判定(stageG05_direction_decision.md)

_生成于 2026-09-21 21:3x。数据:120/120 新集全部落地(P0-P3 各 30)+ P4 复用
g0D 30 行;零 infra 残留(36 次 API 整段卡死全部按 ≤3 重试纪律消化,详见文末)。
分析器 = scripts/analyze_memory_stageG05.py;臂定义/六对比/判定规则全部来自
预注册文档(e613a41/57428a5),零事后修改。_

**一句话结论:在 DEV 网格上,"什么都不注入"的 P0 已有 .867 成功率;没有任何
单一因素达到 CLEAR POSITIVE 门槛;top-2 为 P2(通用重定向)与 P4(完整栈),
并列 +3.3pp —— 按 §13 判 MIXED/INTERACTION,按 §14 落 CASE E(效应小且
不稳,G0-D 的 .900 大部分可由基线解释)。预注册允许的唯一后续 = 只扩
P0+P2+P4 到 60 matched cells。本文档按 §23 停在这里,等用户定方向。**

## 表 1 — 五臂总览(n=30/臂,全部 v1_per_result 触发,P3/P4 共用 neutral query)

| 臂 | 注入内容 | SR | fires/ep | 注入/ep | tok/ep | rec@3 | stalled@3 | wall(s) |
|---|---|---|---|---|---|---|---|---|
| P0 | 无(只记日志) | .867 | 1.97 | 0 | 0 | — | — | 2426 |
| P1 | F2 reason 文本 | .833 | 1.70 | 1.7 | 34 | .706 | 0.29 | 2382 |
| P2 | F3 通用重定向 | .900 | 2.00 | 2.0 | 112 | .733 | 0.20 | 2345 |
| P3 | F4 + 卡片(无 reason) | .833 | 2.27 | 2.3 | 737 | .735 | 0.31 | 2251 |
| P4 | 完整栈(reason+卡片,=G0-D) | .900 | 2.20 | 2.2 | 765 | **.818** | **0.21** | 2403 |

分任务 SR:t3 = P0 .7 / P1 .7 / **P2 .9** / P3 .7 / **P4 .9**;t5 全臂 ≥.9
(P0-P2 1.0 封顶);t9 = P0 .9,各注入臂 .8-.9。**全部净差异集中在 t3**
(基线 3 个失败格,被 P2 和 P4 各翻转 2 个);t5/t9 封顶无分辨力。

## 表 2 — 六个预注册对比(paired,McNemar exact,bootstrap 10k seed 20260920)

| 对比 | diff | net wins | p | CI95(micro) | CI95(macro) | nonneg tasks |
|---|---|---|---|---|---|---|
| P1−P0(reason effect) | −.033 | −1 | 1.0 | [−.20,.13] | [−.1,0] | 2/3 |
| P2−P0(generic effect) | +.033 | +1 | 1.0 | [−.10,.17] | [−.1,.2] | 2/3 |
| P3−P0(memory effect) | −.033 | −1 | 1.0 | [−.20,.13] | [−.1,0] | 2/3 |
| P4−P3(reason given memory) | +.067 | +2 | .6875 | [−.10,.23] | [−.1,.2] | 2/3 |
| P4−P1(memory given reason) | +.067 | +2 | .625 | [−.07,.20] | **[0,.2]** | **3/3** |
| 交互 (P4−P3)−(P1−P0) | +.100 | — | — | — | [−.1,.3] | — |

三个方向一致但全部不显著的正信号:P4−P1(唯一 macro CI 不含 0 下界)、
P4−P3、交互项(+10pp)。所有单因素对 P0 的效应均在噪声内。

## §13/§14 的机械套用(不做任何即兴解释)

- **CLEAR POSITIVE FACTOR(需 SR≥+8pp ∧ ≥+3 net wins ∧ ≥2/3 任务非负):四臂全部不满足**(最大 +3.3pp / +1 net)。
- **top-2 门槛:P2 与 P4 并列 +3.3pp,差距 0 ≤ 5pp → 判 MIXED/INTERACTION,不选 winner。**
- **CASE 匹配**:A 要求 P2≈P3/P4 同时走高 —— P3(.833)不在高处,不符;B 要求 P3/P4≫P2/P1 —— 不符;C 要求 P1≈P4 —— 不符(P1 最低);D 要求 P4≫全部单因素 —— 不符(P2 与 P4 打平)。**剩下 CASE E:"所有 arm 差异很小或结果高度不稳定 → G0-D .900 可能主要是小样本波动;先扩大样本;不要建立新 claim。"** §13 的 MIXED 规则给出的动作与 CASE E 收敛:只扩 P0 + top-2(P2、P4)到 60 matched cells,不全量重跑。

## §22 十问逐条回答

**1. D 臂为什么成功?**
主要因为基线本身高:P0(同触发器、零注入).867。D 的 .900 中,超出基线的
部分在本样本下与波动不可分(+3.3pp,p=1.0)。有意义的差异全部集中在 t3:
基线 7/10,P2/P4 各 9/10 —— 即"在真正会失败的任务上,一次决策点重定向
(无论带不带卡片)翻转了约 2/3 的失败"。G0 观察到的 D-臂悖论(低检索精度
+高 SR)现在有了直接解释:**D 的收益形态是重定向,不是记忆命中。**

**2. trigger reason 单独有没有作用?**
没有。P1−P0 = −3.3pp(−1 net)。34 token 的执行诊断文本本身不产生增益。

**3. generic replanning cue 单独有没有作用?**
统计上无显著(+3.3pp,+1 net,p=1.0),但方向为正、与 P4 并列 top-1,
且 t3 上 +20pp。它是扩展阶段要验证的头号候选 —— 112 token 对 765 token
(§16:若 P2≈P4 成立,同效果 1/7 成本是重要结果)。

**4. actual long-term Memory 是否提供独立增益?**
没有。P3−P0 = −3.3pp(−1 net)。737 token/ep 的卡片单独不产生 SR 增益;
P3 的 rec@3(.735)与 P2 的纯文本重定向(.733)相同。

**5. Reason 与 Memory 是否存在 interaction?**
方向上是的,但不显著:P4−P3 +6.7、P4−P1 +6.7(3/3 任务非负,macro CI
[0,.2])、交互项 +10pp(CI [−10,+30])。三个量一致指向"reason 与卡片
合用比任何单因素好";n=30 无法把它与小样本波动区分。

**6. 哪个 arm 的 recovery@3 最高?**
**P4 .818**(P3 .735 / P2 .733 / P1 .706;P0 无注入无此指标)。P4 同时
stalled@3 最低(.21)。次级机制指标一致偏向完整栈 —— 这是目前支持
"记忆有贡献"的最强(仍非显著)证据,与第 5 问的交互信号同源。

**7. 哪个因素对 SR 的解释力最大?**
当前数据下:**基线(触发器计时的重定向机会本身)解释了绝大部分方差**。
在注入内容之间,无单因素达标;t3 上的翻转由"通用重定向"与"完整栈"
同等实现。诚实的排序:基线 ≫ {P2 ≈ P4} > {P1 ≈ P3}。

**8. Memory relevance@3 与实际 success 是否仍然脱钩?**
仍然脱钩,且比 G0 更干净:P3 的 rel@3 = .6 **高于** P4 的 .4,但 P4 的
SR(.9 ≥ .833)和 rec@3(.818 > .735)都**高于** P3。检索更准的臂表现
更差;hardneg retreat 5/5、3/3(硬负例全部进了 top3)也不妨碍成功。
相关性在本范式里既不必要也不充分 —— 第三次独立确认。

**9. 下一阶段应该研究什么?**
按预注册,唯一被许可的动作 = **e(扩大样本)**,且只扩 **P0+P2+P4**
到 60 matched cells(每臂新增 s11-s20 共 30 集,总 90 新集,8 workers
预计 ~10h)。60 格后的分流(预注册 CASE 规则,届时机械套用):
- 若 P2≈P4 且都显著 > P0 → **CASE A 方向**:主增益 = decision-point
  context refresh;下一阶段比较 Periodic / Motion-Stuck / Progress 触发
  器在**同一个 F3 generic block** 下的表现(= G2 重设计版);论文方向
  "Decision-Point Context Intervention"。
- 若 P4 显著 > P2 → **CASE D 方向**:reason×memory 接口是主增益;
  研究 trigger-conditioned memory/context interface(WHEN 与 WHAT
  不能独立设计)。
- 若仍然全部模糊 → CASE E 定格:不建 claim,转向(候选:把网格换成
  更低基线的任务/suite,制造分辨力)。

**10. G1-G4 campaign 哪些应该恢复、取消或重设计?**(建议,最终由用户定)
- **G1(跨 suite 泛化,3 臂 × 435 格/臂)**:推迟。归因未定前扩 suite
  是在放大一个尚未解释的效应;且 G1 的 memB1 臂是 full 注入,如果主增益
  是 generic refresh,G1 测的不是它声称的东西。
- **G2(触发器基线 T2/T3)**:重设计后保留 —— 它正是 CASE A 方向的
  下一阶段载体,但 block 应换成 F3(当前 G2 用 full block)。
- **G3(Timing×Ranking 2×2)**:暂停。G0 已证 WHEN≯WHAT;本轮 rel@3
  再次与 SR 脱钩,ranking 维度当前无主效应可解释。
- **G4(bank 规模压力)**:取消或降级为附录实验。检索质量与 SR 三次
  脱钩后,"加更多卡"不是当前瓶颈。
- G-final:顺延至方向确定。

## 运行完整性记录

- 120 新集 + 30 复用全部收敛为策略判定,**零 infra 残留行**(分析器
  公开计数:五臂均 0)。
- 过程中共 36 次 `infra_timeout`,指纹全部为"首次 planner 调用挂死、
  零回合、白等 3600s、无 usage 返回"(服务端接入型挂起,非限流:期间
  两次 3×小请求 + 1×50k token 探针全部 200/零 429)。全部按 ≤3 重试
  纪律自动消化,无一格耗尽。
- 按 §20:这些是 service failure,从未计为 policy fail,也未 rerun 任何
  真实策略失败(全 run 仅调度器层面重试 infra 格)。
- P4 复用合规性:预注册 §0 已逐字段核对(g0D = v1_per_result + common
  query + reason-in-block + cards),30 行原样读入,未重跑。

## 产物清单(§21)

stageG05_campaign_pause.md ✓ · stageG05_reason_flow_audit.md ✓ ·
stageG05_preregistration.md ✓ · stageG05_regression_audit.md ✓ ·
stageG05_runs.csv ✓ · stageG05_events.jsonl(304 events)✓ ·
stageG05_results.{json,md} ✓ · 本文 ✓

**§23 STOP:不自动恢复 G1-G4,不自动启动扩展。等你确认方向。**
