# Stage G0.6 — 配额 429 事故与恢复(2026-09-22)

_发生于 06:06-06:12 巡检取证期间。本文 = 完整事故账 + 恢复动作记录。
预注册依据:§16(429 ≠ policy failure)与 §15(严重 infra failure
是唯一允许的中断情形)。_

## 1. 事故

G0.6 的 90 个新集于 02:17-06:12 全部落行,但 **05:52 起 GLM key 撞上
429 code 1310:"已达到 7 天使用上限,2026-09-22 17:39:59 后可继续使用"**。

配额死后的 episode:首次 planner 调用被秒拒 → 零回合 → wall≈87s →
agent 把异常记为 `policy_fail`。**调度器的 infra 分类器只认
`infra_crash`/`infra_timeout` 两种 result 字符串,这个新指纹漏接**,
于是 63 个纯基础设施故障格被当成真实策略失败落进了 CSV。

## 2. 取证(逐格证据,可复查)

判定法:对 s11-s20 的每个 episode 目录 `run.log` 全文搜配额签名串。
两次独立扫描交叉验证(wall<150s 初筛 + 全量签名扫描):

| 类别 | 格数 | 指纹 |
|---|---|---|
| 秒死格(wall≈87s,零回合) | 55 | run.log 含配额串(P0=6, P2=19, P4=30) |
| 中途死格(跑了 862-3370s 后下一次 planner 调用被拒) | 8 | 同上(全为 P2 t3/t5) |
| **污染合计** | **63** | P0=6 / P2=27 / P4=30 |
| 有效格 | 27 | 无配额串(P0=24 / P2=3 / P4=0) |

P4 整臂(最后跑)全灭;P2 有效仅 3 格;P0 有效 24 格。s1-s10 的
G0.5 原行 90 格完全未受影响(与已发布数字逐格一致)。

## 3. 恢复动作(全部已执行)

1. **分类器补丁**(scripts/ovpm_exp.py,镜像既有 `_TOKEN_LIMIT_FATAL`
   先例):run.log 含 `_QUOTA_LIMIT_FATAL = "已达到 7 天使用上限"` 时
   重分类为 `infra_crash` → 走 ≤3 重试纪律,不再伪装 policy_fail。
   功能验证:死目录 → infra_crash ✓;存活目录不受影响 ✓。这是
   运维层修复,不触碰任何实验语义(prompt/trigger/memory/指标零变化)。
2. **CSV 手术**:备份 `outcome_validation_runs.csv.bak-20260922-quota429`
   → 删除 63 个污染行(判定标准 = run.log 签名,非 wall 启发式)→
   留存 956 行。删除行逐格清单:`stageG06_quota429_deleted_rows.json`。
3. **重跑计划**:配额重置(17:39:59)后以原命令、原 tier
   (`glm-5.3-flash`)resume —— done-keys 重建缺口 63 格
   (g05 阶段 33:P0 6 + P2 27;g0 阶段 30:g0D)。
   这些格是 §16 意义上的 infra,不属"重跑 genuine policy failure"禁令范围。

## 4. 风险与守则

- **R22 并发**:attributeAgent 的 r22 RL 管线(另一 key 文件
  `/workspace/yjx/glm_api.md`)正在跑。两 key 文件内容不同,但是否
  同一账户配额池无法从侧判断。若重置后配额再次快速耗尽,补丁会把
  后续格记为 infra_crash(而非假 policy_fail),可再次 resume。
- 期间所有"成功率"数字(尤其 P2/P4 新段)无效,不进入任何分析;
  §15 的"全部完成后再分析"以 90 个**有效**新集为准。

## 5. 教训(已入长期记忆)

quota 型 429 是一种此前从未出现过的 infra 指纹(历史只有 3600s
挂起型);任何"result=policy_fail 但 wall 异常短/零回合"的行都要先
怀疑 infra,再谈策略。
