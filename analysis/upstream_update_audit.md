# Upstream 更新审计 — §0 决策报告

_2026-09-05,Outcome-Validated Memory 实验前置审计。全程只读(未 pull/fetch/push,未改任何 ref;远程信息来自 `git ls-remote` 与 GitHub API,promisor 按需取对象不改 ref/工作区/配置)。_

**决策:保持当前版本 `d344c0e`(现锚点 `0a9f132`,分支 `research/pre-ovpm-20260905`),不合并上游,不 fetch/pull/overwrite。全程禁 `reset --hard` / `clean`。**

---

## 1. 仓库状态快照

| 项 | 值 |
|---|---|
| 本地分支 | `main`(审计时)→ 已切 `research/pre-ovpm-20260905` |
| HEAD | `d344c0e`("chore: ignore rpent-logs*.tar.zst",2026-08-19) |
| vs origin(Jasonnn258 fork) | **0/0 完全同步**(rev-list ahead/behind) |
| 工作区(审计时) | 24 个已跟踪文件脏(+118/−111)+ 15 个未跟踪 analysis 产物;**已全部提交为 `0a9f132`** |
| stash / skip-worktree / assume-unchanged | 空 / 空 / 空 |
| 克隆来源 | `gh-proxy.com/.../Jasonnn258/RPent.git`,2026-09-01,partial clone(blob:none);此后零 fetch(无 FETCH_HEAD) |
| 真上游 | **`RLinf/RPent`** main @ `d4e9b3a`(2026-09-04,"docs(robotwin): clarify reproduction branches (#149)") |

脏文件逐个核对:全部为 `/hw-tbo/yjx → /vla_test/yjx` 路径迁移与 planner 默认值切 GLM(`run_rpent.sh`、`scripts/*_exp.py`、若干 shell 脚本),**无核心算法逻辑改动**;15 个未跟踪文件全部是上阶段轨迹诊断交付物。

## 2. 与上游的关系

- fork 点 = merge-base `97ad4ff`(2026-08-07,"fix(api): handle read_image file errors (#74)")。
- ahead 18 / **behind 49**(上游 2026-08-09~09-04,#75~#150)。
- 字面 diff:上游侧新增代码 216 files +28,081/−4,279。

## 3. 重点路径逐项判定(用户 §0 清单)

| 检查项 | 上游是否有实质变化 | 内容 | 对本实验的影响 |
|---|---|---|---|
| planner loop | **有** | `api_loop.py` +128(可配置 reasoning_effort none~xhigh,**仅传 Codex turns**;跨后端串行化并发工具调用 #150) | reasoning_effort 对 GLM anthropic 端点无效(端点无逐请求 effort 参数),本实验用不到;串行化本地 toolkit 已有单飞行锁。**不采用** |
| LIBERO prompt/workflow | **有,大规模** | `prompts/system.py` 重写;新增 `prompts/explore.py`(451 行,exploration→distill→consolidation 工作流)与 `local_eval.py`;`tools.py` 1210 行重排(primitive 语义大改);`robot_spec.py` 替代 `spec.py` | 本实验必须在 sm_exp/pg_exp 所用的同一套 prompt/tool 语义上跑(与诊断期数据、冻结规则 v1/v2 兼容)。换上游 prompt 等于换实验对象。**不采用** |
| memory manager / exploration / consolidation | **有(最大冲突点)** | 新增 `rpent/memory/manager.py`(MemoryManager,419 行)、`memory/tools.py`;#142 unify cross-robot memory | 与本地 `rpent/memory/{structured,schema,dual_route}.py` 同名目录不同实现,合并必冲突;且自动 consolidation 在本实验研究边界内明确**不做**。**不采用** |
| global/suite/task_only memory | **有(仅上游)** | MemoryManager `SCOPES={global,suite}` + 文档三层 corpus `/{MEMORY.md,global/,suite/,task_only/}` | 本实验的 memory = 冻结规则集(structured_rules v1→v2)+ expected_outcome/verify_check 契约,不引入新 memory 架构。**不采用** |
| non-reasoning mode | 无字面实现 | 上游最接近物 = reasoning_effort="none"(Codex-only);本地对应物 = dual-route Fast 零参路径 | C 臂 COMMIT/REASON 双模式基于本地实现,不依赖上游。**不采用** |
| toolkit 语义 | **有** | `rpent/tools/toolkit.py` +233;`robots/libero/toolkit.py` 265(attempts-per-session 预算、未用完 attempts 拒绝 finish) | attempts 预算会改变 turn budget 语义,破坏与诊断期/taxonomy 的可比性。**不采用** |
| evaluation / turn budget | **有** | 新增 `rpent/evaluation/`(result.py);explore prompt 内 attempt budget | 本实验评估 = states.json `libero_terminated` + structured_metrics,工具链已就位。**不采用** |

上游其余大项(RoboTwin/RoboCasa365 集成、RPC 架构重构、CI/契约测试、`envs→robots` 改名)与本实验无关。

## 4. 保持当前版本的三个理由

1. **正交的研究线**:上游 49 提交的主线是 MemoryManager/exploration/consolidation + 多机器人平台扩张;本实验验证的是 expected-outcome 契约如何连接既有 Global Memory(冻结规则)与 reasoning timing,假设不同,不需要上游能力。
2. **所需能力本地全有**:`rpent/memory/schema.py` 的 `expected_result`/`success_check` 字段已存在(历史遗留,从不在在线消费——正是 B 臂要激活的);api_loop 全部挂点(事件流 :750/:766、轮边界注入 :477-498、工具结果钩子 `_make_tool_function` :1188-1221)齐备。
3. **可比性**:合并会在 `api_loop.py`(双方各 +300 行级重写)、`rpent/memory/`、`robots/libero/` 三处正面冲突,并使 sm_exp/pg_exp 历史结果与冻结规则 v1 失效;已验证的 Pi0.5/SAM3 checkpoint 冒烟环境也随之作废。风险全在收益侧为零。

## 5. 合规声明

- 未执行任何 pull/fetch/push/覆盖;未拿旧结果伪装新 baseline(换 planner 后所有臂 fresh 重跑,旧 SR 仅历史参考)。
- 旧结果与新实验的数据均保留在 `logs/`(pg_exp/sm_exp/dr_exp)与本仓库;安全锚点 `0a9f132` 可随时回滚。
- 若未来需要上游某单项能力(如离线契约测试),路径:从 upstream/main 建新分支、只 cherry-pick/迁移所需文件,不动本实验线。
