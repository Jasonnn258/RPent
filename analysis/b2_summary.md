# B2 最终汇报 — Evidence-Sufficient State-Transition Verification

更新: 2026-09-16 | 全部 180 集(90 dev + 90 stage1)完成,tier = glm-5.3-flash
三臂严格配对(同任务/种子/重复):A = 结构化记忆 baseline,B1 = A + 二值结果判断,
B2 = A + 状态迁移验证(pre-state + action + post-state 三段式,三值裁决,
UNCERTAIN → 有界 OBSERVE ≤2 轮 → REASON)。B2 于 dev2 后冻结(commit 3edd0bd),
stage1 前零改动。裁决事件归档:`analysis/b2_verification_events.jsonl`(1341 条)。

## 判定:PARTIALLY SUPPORTED

**成立的部分**:B2 作为安全层成立——不伤成功率、不引死循环、commit 延迟大降。
**不成立的部分**:核心收益主张(新任务 SR 提升、假成功下降)未被数据支持——
现象本身在这些任务/规模上没有出现,无可减之物;SR 与 B1 持平。

## 9 项数字

| # | 指标 | dev(t0/t7/t9, n=90/臂) | stage1 新任务(t2/t3/t5, n=30/臂) |
|---|---|---|---|
| 1 | SR | A 72(80.0%)/ B1 77(85.6%)/ **B2 74(82.2%)**;McNemar p=0.678 | A 27(90%)/ B1 26(86.7%)/ **B2 26(86.7%)**;vs B1 翻转 1W/1L |
| 2 | 配对翻转 | vs B1:10W/13L;vs A:15W/13L(净+2) | vs B1:1W/1L;vs A:2W/3L |
| 3 | 假成功 episode(finish 声称 success 但分类失败) | 三臂均 0 | 三臂均 0 |
| 4 | 假阳性捕获(fp_caught) | 0(观察确认失败仅 1 次) | 0(resolved_failure=0) |
| 5 | Commit 延迟(步,配对) | B1 7.81 → **B2 2.99**(60/62 更快) | B1 5.17 → **B2 2.44**(25/26 更快) |
| 6 | Recovery 延迟(步,配对) | B1 1.90 → B2 2.40(7快/2慢,n=10,不显著) | 1.33 → 1.43(n=3) |
| 7 | UNCERTAIN 去向 | 134 个:overtaken 100 / REASON 30 / 解决 3 / 挂起 1 | 46 个:overtaken 35 / REASON 8 / 解决 1 / 挂起 2 |
| 8 | 观察指令服从率 | 98/199(49%) | 24/61(39%) |
| 9 | 重复行为 | same_tool_repeated 0;冗余观察 0;1.46 picks/集 | 同左;1.6 picks/集 |

## 逐条对照预登记成功标准

1. **dev SR 不明显低于 B1** ✅ p=0.678,噪声范围(输的 13 集里 11 个验证器静默)
2. **新任务 SR ≥ A、最好 > B1** ⚠️ 未达:B2 26 = B1 26,< A 27(差 1 集,p≈1.0,
   纯噪声,但按字面标准"≥A"不成立)
3. **false success 明显下降** ❌ 无法检验:两个网格、三臂的假成功 episode 全为 0
   ——现象没出现。OVP-M 时代的 OC-PICK 紧握误报出现在 t1/t4/t8 heldout,
   t2/t3/t5 上不存在此压力
4. **UNCERTAIN 不死循环** ✅ 全部有界(≤2 轮 + stall 守卫),0 冗余观察,
   REASON 0.33/集(dev)/0.27/集(stage1)
5. **latency 至少一项改善且另一项不显著恶化** ✅ commit 大幅改善(2.5-2.6x),
   recovery 不显著恶化

## 机制层面的发现

- **裁决几乎不驱动行为**:75%(dev)/76%(stage1)的 UNCERTAIN 被 planner 直接推进
  消化(overtaken),服从率 49%/39%。B2 实际运行形态 = 诚实的旁路记账器 +
  低成本 commit 信号,而非主动纠偏器
- **观察解析的天花板**:服从的观察轮大多落在真实两可带(物体没动+夹爪还在旁边,
  69/136)或 SAM 未找到目标(29/136)——失败确认需要夹爪离开后才能成立,
  这是时序上难满足的条件
- **裁决质量**:所有抽查的 CONFIRMED_FAILURE 均与物理事实一致;没有一个失利集
  被错误裁决带偏(dev 13 失利:11 静默 + 2 裁决正确;stage1 t3 s1 唯一独有失利:
  3 次抓取确实都没闭合)
- **commit 延迟改善是真实的**:B1 的 matched 事件平均 7.8 步才关闭,
  B2 的 confirmed 2.99 步——因为 B2 不等 phase 推进,动作一确认就发信号

## 结论

B2 假设的"证据充分的状态迁移验证"在此 planner/任务族上**不能证明有 SR 收益**,
但也**证明无害且更便宜**(commit 快 2.5x,无循环,无误导)。若继续这条线,
方向不是加规则,而是解决"证据时序"问题(失败确认需要夹爪离开原位后复查)
和"指令服从"问题(planner 一半时间不理会观察指令)。

## 产物清单

- `analysis/b2_runs.csv` — 120 行逐集 B2 指标(90 dev2 + 30 stage1)
- `analysis/b2_pairs.csv` — 两网格配对翻转
- `analysis/b2_verification_events.jsonl` — 1341 条裁决事件(全字段)
- `analysis/b2_stats.json` — 聚合数字
- `analysis/b2_failure_analysis.md` — 失败/获利集逐集分类
- 代码:commit 3edd0bd(实现+修复)、0650d56(分析工具链)
