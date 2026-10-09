# P1-DEV0 执行与独立验证报告(2026-10-09)

> **后验勘误（2026-10-09，原始 DEV0 文件/策略冻结不变）**：随后由用户在私有服务器上运行 `scripts/p1_dev0_posthoc_audit.py`（4/4 synthetic tests OK，`policy_sha_match=true`），确认 5 个已实际执行 probe 的合法观测上，冻结策略的**离线影子决策** `D2=CONTINUE_CAUTION` **5/5**、`D3=RETRY` **5/5**；实际生产 6 次决定仍全部为 RETRY，D2 没有生产触发。故本文 §5.1 中“5 次 probe 后 `post_gap≥0.06`、物理上确实没抓住”的原断言**与冻结 D2 规则不相容，应撤回**；本文 §6 样例中 `post_gap=0.0025` 也直接与上述全称断言矛盾。按冻结 D2 规则，若 shadow 推演输入/路径一致，则五次 `D2=CONTINUE` 均要求 `post_gap<0.06`。**夹爪闭合代理不能证明物体被抓住**。此外，`D3=RETRY` 可能由 EEF z 增量未达规则阈值（或非有限数引起），旧版报告未提供逐样本合法观测值，需用新增只读聚合诊断确认，不能先宣称已经验证每条原始记录。更正只影响**解释**，不更改运行数据、冻结策略或正式 outcome。

> **增强版诊断实际回传（2026-10-09）**：4/4 测试通过，冻结 Policy SHA 一致；5/5 `post_gap<0.06`，5/5 EEF dz 数值有效，**0/5 `ΔEEF_z>=0.03`**，probe→policy `gripper_gap/eef_z` 传值不一致 **0**。因此之前的 `post_gap>=0.06` 全称断言确已推翻，D2 静态规则在五个输入上选择 CONTINUE、D3 由于额外高度门槛选择 RETRY。**这既不证明物理抓住，也不证明哪种动作更有效。** 详见 `P1_DEV0_INDEPENDENT_METHOD_AUDIT.md` 最新顶部回执。历史运行报告的原始表格不回写。

协议:P1-DEV0-L2-24EP-4ARM-20261009 | 授权:D-017(`P1_DEV0_AUTHORIZATION_AND_LOCK.md`)
代码:冻结于 commit `62701a0`(hook+接线+runner v1);本次提交补 runner 两处启动修复 + 分析器 + 本报告。
数据:`/workspace/yjx/rpent_data/p1_dev0/`(run_20261009_095754;不入 Git)

**判定:GO(仅工程可行性维度)/ HOLD(任何确认性扩展)** —— DEV0 第一终点
(接线可行、隔离成立、成本可记、审计可测)已达成;触发率与臂覆盖不足以支持
任何效应结论,扩展到正式 P1 需新预注册 + 新授权。

---

## 1. 交付四件套对照

| 交付物 | 位置 | 验证 |
|---|---|---|
| 可复现代码 | `rpent/utils/p1_dev0.py`、`robots/libero/toolkit.py`、`robots/libero/env_client.py`、`scripts/p1_dev0_run.py`、`scripts/p1_dev0_analyze.py`、`analysis/research_context/test_p1_dev0_hook.py` | 22/22 hook 单测 + 31/31 全套;manifest sha256 seal 启动时强制复核 |
| 实际运行结果 | 21/24 episode 执行,6 触发,6 审计,0 hook_error | 本文 §4-§6;事件文件逐条可复核 |
| 四臂成本与触发统计 | `scripts/p1_dev0_analyze.py` M1-M7 | 本文 §5 |
| 独立验证报告 | 本文 + `artifacts/p1_dev0_analysis_local.json`(本地,不入 Git) | 分析器只读事件文件,与 runner 记账独立 |

## 2. 预注册与冻结(运行前)

- manifest:24 cells(task{3,5,9} × seed{1001..1008},arm×task=2),sha256
  `839bc0d1b392806553fd2e6a5338a4f8a6f9c47e6a77957ec95dbc29a21b9132`,write-once,
  runner 启动时 seal 不符即拒绝。
- 决策策略:`analysis/research_context/p1_dev0_policy.py`,sha256
  `15d58071cea670039b00a264f1486ed7f8571b7d448b99af60035ce801a50630`;
  运行时按路径动态加载(不复制实现),6 次触发全部命中同一 sha。
- 固定参数:TURNS=100、planner timeout 2400s、audit horizon H=200 env steps、
  episode step cap 1500、PROBE= set_gripper(+1, 10 steps)。
- 恢复规则(运行前冻结):episode_end→COMPLETED 不重跑;触发无结束→
  CENSORED_NO_RERUN;纯 infra→允许一次重跑。本次运行未用到任何恢复分支。

## 3. Gate 执行记录

1. **无 GPU 单测**:22/22(`test_p1_dev0_hook.py`:默认关闭零副作用、四臂、
   触发严格性、固定 horizon 审计、信息隔离、成本记账)+ 全套 31/31。
2. **集成验证**:dry-run 打印命令与 env;attempt-1 启动级崩溃(见 §7)零数据
   消耗后修复重启;attempt-2 全程 preflight 通过、`.runlocks/p1_dev0.lock` 防重。
3. **Gate 全过才开仿真**:attempt-2 21 个新 episode 均在上述 Gate 之后启动。

## 4. 运行账目(attempt-2,2026-10-09)

| 项 | 值 | 上限 | 状态 |
|---|---|---|---|
| 新 episode | 21 | 24 | 3 个 SKIPPED_GPU_BUDGET(§7) |
| wall | 11336 s = 3.15 h | 8 h | OK |
| GPU·time | 22215 s = 6.17 h | 6.0 h | 超出 0.17 h(§7 偏差,launch-gate 语义) |
| worker | 2 | 2 | OK |
| hook_error / censored / infra | 0 / 0 / 0 | — | OK |

分母(ITT):21 有事件 = 6 触发 + 15 未触发;未触发者全部保留在分母。

## 5. 四臂触发与成本统计

### 5.1 触发层(每 episode 至多一次,首个非终局非截断的失败 pi0_pick)

| 臂 | 执行 n | 触发 | 触发格 | 决策(rationale) | 动作 |
|---|---|---|---|---|---|
| D0 盲重试 | 5(t3×2 t5×2 t9×1) | 1 | t9_s1001 | RETRY(BLIND_RETRY_FIXED) | RETRY |
| D1 probe-blind | 6(t3×2 t5×2 t9×2) | 3 | t3_s1002, t9_s1002, t9_s1003 | RETRY(BLIND_RETRY_FIXED)×3 | RETRY |
| D2 静态阈值 | 4(t3×2 t5×2;**t9×2 被 budget 跳过**) | 0 | — | — | — |
| D3 Evidence Claim | 6(t3×2 t5×2 t9×2) | 2 | t9_s1004, t9_s1005 | RETRY(LEGAL_EVIDENCE_NOT_ENOUGH)×2 | RETRY |

按任务:t3 1/8、t5 0/8、t9 5/5。全部 6 次决策均为 RETRY,无一 CONTINUE_CAUTION:
5 次 probe 后夹爪仍开(post_gap≥0.06,物理上确实没抓住),D3 的两条判据
(grip<0.06 ∧ lift≥0.03)不满足 → LEGAL_EVIDENCE_NOT_ENOUGH。ABSTAIN 回落
分支未在生产触发(仅在单测覆盖)。

### 5.2 成本层(env steps 为物理步,墙钟为真实耗时)

| 成本项 | 值 |
|---|---|
| probe(D1/D3 共 5 次) | 恰好 10 env steps/次;墙钟 1.59-1.69 s |
| 重试 pick(6 次) | 45-80 env steps/次(中位 60) |
| probe 对比 | ≈ 一次重试 pick 的 1/6-1/8 成本 |
| 未触发 episode 平均 | 216.8 env steps/集 |

### 5.3 outcome 可测性(audit-only,6/6 触发全覆盖)

- 4/6 在 FIXED_HORIZON 取样,overshoot 3/8/18/23 env steps(首个技能边界
  ≥ target 的定义内);2/6 在 EPISODE_END 兜底(episode 提前结束,overshoot
  记为 −120/−70)。
- 全部 6 条含 check_success + sim_measurement(真值通道只落外部事件文件)。
- 描述性交叉(n≤3,不作任何推断):RETRY 后 D0 0/1 真、D1 1/3 真、D3 1/2 真;
  重试 pick 自身成功 3/6。

## 6. 隔离与完整性核验(独立验证)

| 检查 | 结果 |
|---|---|
| D1 遮蔽结构性 | 6/6 retry_step = trigger_step+1(probe 走 primitives 直调不占步号);t3_s1002 transcript 全文 grep 无任何 probe 痕迹(匹配到的 5 处均为静态资源文本/planner 自身思考) |
| D0/D1 信息集同构 | 单测逐字段结构相同 + 生产步号一致 |
| 特权键泄漏 | 0(非 audit 事件全量扫描 FORBIDDEN_KEYS) |
| 审计真值位置 | 21/21 事件文件均在 episode output_dir 之外 |
| probe 物理安全性 | 5/5 probe 后 episode_terminated=False(probe 从未终结 episode) |
| policy 一致性 | 6 次决策 policy_sha256 唯一(冻结值) |
| 事件链完整 | 6/6 触发 episode 均有 episode_end 事件,无缺失 |

**事件链样例(t3_s1002,D1,首次真实干预)**:trigger(step 4,env 145,pre_gap
0.0204)→ probe(10 步,post_gap 0.0025 — probe 物理上夹紧了夹爪)→
decision(RETRY/BLIND_RETRY_FIXED,probe 观测被遮蔽不进决策)→ action(RETRY,
70 步,重试成功)→ episode 在 225 步任务完成 → EPISODE_END 审计
check_success=True。 Planner 全程只看到"step 4 失败 → step 5 重试视图",
与 D0 同构。

## 7. 偏差与事故记录(如实)

1. **attempt-1 启动级崩溃(零数据)**:10 个 episode 约 9 s 即死,根因
   env_server.py 对 `PYOPENGL_PLATFORM` 的 setdefault 把 egl 恢复(本容器
   EGL 设备数 0)。修复:BASE_ENV 显式 `PYOPENGL_PLATFORM=osmesa` +
   runs 目录预建 + 连续 4 次 NO_EVENTS_FILE 的 infra-storm 中止阀。崩溃目录
   归档至 `p1_dev0_crashed_attempt1/`;0 个事件文件产生 → 未消耗 episode/
   预算,不属于换样本。
2. **GPU 6.17 h vs 6.0 h 名义上限**:预算门在**启动时**检查(900 s 裕量);
   最后一集 t9_s1005 启动时 5.2 GPU·h,完成后越限。选择不杀在飞 episode
   (杀掉浪费已耗 GPU 且造成无收益 censor),之后零新启动。最终超出 0.17 h。
3. **3 个 cell 未执行**:t9_s1006(D2)、t9_s1007(D2)、t9_s1008(D0)被
   GPU 预算门 SKIPPED。未补跑(不为补触发样本加跑,预注册纪律)。
4. **SKIPPED 状态未逐条落 run log**:`_run_one` 预算短路路径直接 return,
   未写 episode_done 事件(3 个跳过集只能由 manifest−事件文件差集还原)。
   runner 已知缺陷,DEV0 内不影响数据有效性,正式 P1 前修复。

## 8. 局限(结论边界)

- **D2 臂生产路径零执行**:0/4 触发(其 t9 两格恰被 budget 跳过,t3/t5 又
  未失败)。D2 决策分支只有单测覆盖,无生产数据 → "四臂均可运行"对 D2 仅
  代码级成立。
- **触发率 6/21≈29%,任务高度集中(t9 5/5,t5 0/8)**:与 preflight 的历史
  失败分布(t9 89.7%)方向一致,但本批 seed 下 t5 全程无失败 pick。任何臂间
  比较在本样本下无功效;n≤3 的 audit 交叉表仅描述。
- **CONTINUE_CAUTION / ABSTAIN 分支未在生产暴露**:全部决策 RETRY。
- **audit check_success 是描述性真值**,不构成任何臂的效应声明。
- 单栈(LIBERO spatial t3/t5/t9)、单 planner 模型、probe 仅夹紧式一种。

## 9. 判定

**GO(工程可行性)**:
1. 真实 D2 钩子在默认关闭路径外运行成功,vanilla 与 Stage R 零接触
   (RPENT_STAGE_R_TRACE 全程未设);
2. D1 遮蔽在结构上成立且生产数据验证;
3. 合法观测通道(proprio 白名单 + 新鲜帧)在 5/5 probe 上工作;
4. 成本、固定 horizon 审计、事件日志全部可记且被独立分析器复核;
5. 预算/锁/恢复纪律执行,偏差如实记录。

**HOLD(确认性扩展)**:正式 P1 需要新预注册 + 新授权,且设计必须先解决
触发率与任务集中问题(按任务分层定样本量;t5 类任务要么换触发定义要么
不纳入)。本报告任何数字不得引用为"P1 优于基线"的证据。
