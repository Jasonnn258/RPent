# P1 Label-blind Quota · 真实结果(2026-10-10)

> **状态**:EXECUTED(本机只读离线;冻结 A0/Stage R)。合成测试修复一处浮点严格相等
> 断言后 **6/6 PASS**;实跑资格门全过零 STOP(103/79/26/56、task 21/30/52)。
> 私有产物 `artifacts/p1_return_time_triage_lab/label_blind_quota_v1.json`(gitignored)。
> FGONLY 是同技能运动学弱代理;"复核优先级"≠ CONTINUE/持握/动作收益。

## 0. 本轮修复的工程问题(仅测试侧)

`test_p1_label_blind_quota_lab.py` 第 77 行对 RANDOM 权重和用严格 `assertEqual`
(103 个 21/103 浮点累加 = 21.000000000000014),与同文件第 48 行的容差断言不一致。
修为 `assertAlmostEqual(places=9)`,与实验代码 `|sum−k|≤1e-8` 合同对齐。
**关键性质测试原样通过:翻转 FGONLY 标签后五种方法的选择权重逐位不变**(标签只进评价)。

## 1. 核心对照表(真实 103 例;Top20%=21 席 / Top40%=42 席)

**退出时 FGONLY 参考**(26 正,基率 0.2524):

| 方法 | Top20 命中/误选 | precision | 富集 | Top40 命中 | precision |
|---|---|---|---|---|---|
| RANDOM | 5.30 / 15.70 | 0.252 | 1.00× | 10.60 | 0.252 |
| GATE_ONLY | 13.26 / 7.74 | 0.632 | 2.50× | 24.12 | 0.574 |
| TASK_EQUAL_GATE | 13.78 / 7.22 | 0.656 | 2.60× | **21.34** | 0.508 |
| TASK_PROP_GATE | 13.70 / 7.30 | 0.653 | 2.59× | 23.70 | 0.564 |
| LMG_FROZEN(参考上界) | **17.00 / 4.00** | **0.810** | 3.21× | **25.00** | 0.595 |

Top20 名额分布(t3/t5/t9):GATE_ONLY 自然涌现 5.53/4.97/10.50;EQUAL 7/7/7;
PROP 4/6/11;LMG 2/8/11。

**任意时刻参考**(56 正,基率 0.5437)Top20:GATE_ONLY 18.24(0.868)、
TASK_EQUAL **17.42(反而低于 GATE_ONLY)**、TASK_PROP 18.73、LMG 21/21(1.000)、
RANDOM 11.42。Top40:EQUAL 31.23 < GATE_ONLY 34.42。**方法优劣次序在两种参考下
一致:RANDOM ≪ GATE_ONLY ≈ TASK_* < LMG;结论不依赖参考时间**(TASK_EQUAL 在
any-time 与 Top40 两处变差,进一步支持降级)。

## 2. 五项核实(对应用户/预登记逐条)

1. **任务配额不是主要机制**:最好的任务配额(TASK_EQUAL 13.78)只比 GATE_ONLY(13.26)
   多 **0.52 个命中(+0.024 precision)**;Top40 两种配额**都更差**(EQUAL −2.78、
   PROP −0.42);any-time 下 EQUAL 反向。增益边际、预算敏感、方向不稳 →
   **撤回"按任务预算是主要算法机制"的表述;两种任务配额降级为探索性基线**。
2. **matched 14.48/21 不可独立达成(实证核实)**:任何标签盲分配器最高 13.78
   (还用了在线不合法的 task 元数据),全部低于事后 matched 14.48;差额 0.70 恰是
   D-039 指出的"LMG 事后配额红利"。**14.48 只是回顾性组成标准化,本轮实证确认
   它不是任何无标签策略的可达结果。**
3. **Task ID 在线合法性核查(源数据级)**:`task_id` 只存在于
   `EERD_A_reconstruction_metadata.jsonl`;`EERD_A_online_eligible.jsonl`
   无 task 字段。合法 `tool_report.instruction` → task **不唯一**
   ("pick up the black bowl" 同时出现于 t3/t5/t9;"pick up the patterned bowl"
   在 t3/t9)。批量待复核队列的存在性也未验证 → **TASK_* 标记
   `OFFLINE_BATCH_ONLY`,不得接线 Runtime**。
4. **GATE_ONLY 是唯一廉价合法候选**:只用决策可见的 D/L/Gfinal 门槛布尔,
   零拟合、零标签、在线合法,2.50× 富集(13.26/21)。LMG 连续分数(0.810)
   仍为最强参考,但属于连续合法数值排序,其增量价值已在第四轮分解
   (+0.120 匹配后)并被判"需独立 cohort 确认"。
5. **标签盲纪律**:所有方法选择权重在翻转标签后逐位不变(测试覆盖);
   名额取整用无标签最大残差法;tie 用均匀期望。

## 3. 最终科学裁决(预登记分支 2+3 双触发)

- **保留**:GATE_ONLY(=D-only 风险分层)作为 L1 唯一廉价合法复核分诊基线;
  LMG 连续分数保留为研究参考上界(独立 cohort + 持握真值前不谈部署)。
- **降级**:TASK_EQUAL_GATE / TASK_PROP_GATE → 探索性基线(OFFLINE_BATCH_ONLY,
  在线不合法、增益边际且不稳)。
- **撤回**:D-038 中"廉价任务+门槛组成分层零拟合即 0.69"的表述(0.69 是 LMG 事后
  配额的标准化期望;可执行对应物是 GATE_ONLY 0.632)。D-039 纠错被本轮实证坐实。
- **本轮后停止**:按预登记与用户指令,**不再在这 103 例上搜索任何新静态规则/
  固定臂/参数**。t9 子池静态阈值路线维持 STOP(第四轮)。

## 4. 不能推出什么

FGONLY 弱代理非持握真值;103 例回顾性数据多次复用,任何数字都不是泛化证明;
TASK_* 的名额分配依赖 reconstruction metadata,未证明在线可见;无新仿真/训练/
Runtime/L2;不因 LMG 数字最大而绕过"连续分数需独立 cohort"的第四轮裁决。

## 5. 下一阶段唯一实验建议

**同刻观测最小 L2 合同**(唯一方向,不再扩展静态面):分层采样含真实持握正例、
probe 改"闭合+受控提升 2-3cm"、以 GATE_ONLY 为免费分诊基线臂、按任务内排名分配
复核预算、独立 held-grasp 标签评价。用户已于同日委托 D-040/D-041 对更严的 DEV1A 上限
(≤8 新 episode、≤3 GPU·h、≤4h 墙钟、单 worker、每集一次 ≤2cm 受控提升、G1–G4
零新样本预检门)作出有条件授权;本报告的 2-3cm 提升建议以 D-041 的 2cm 为准。
冻结 A0/Stage R/DEV0 不动。
