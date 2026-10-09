# H0 Direction 1 · Stage 2C Frozen Release Manifest

> **RELEASE STATUS: FROZEN / READBACK VERIFIED / RESULTS NOT RUN / EXECUTION HOLD**
> Freeze ID: `H0-OE-STAGE2C-20261009-V1` · recorded 2026-10-09.
>
> 用户在本对话明确批准：**“Stage 2C：正式预注册审查与冻结，不运行统计或实验”**。
> “正式冻结”定义为：下面所指定的协议**内容地址 + 首次创建提交 + 数据版本清单**成为此后唯一可引用的 v1 规范，未经新用户授权不得直接改写/替换。**这是已采集且已有终报数据的 retrospective analysis freeze，而非先验盲预注册。**

## 1. 唯一冻结协议身份

| Attribute | Locked value |
|---|---|
| Protocol path | `analysis/harness_h0/H0_OE_STAGE2C_FROZEN_PREREG.md` |
| Protocol ID | `H0-OE-STAGE2C-20261009-V1` |
| Creation commit SHA | `118d98ccc774ba63f6ad06ab6cd69df8697195b3` |
| Frozen protocol Git blob SHA-1 | `97dc0bc93bae857620554a7c2571c5b0b55b5528` |
| Initial creation API readback | `MATCH` (full text compared; no edits to v1 after creation) |
| Freeze QA path | `analysis/harness_h0/H0_OE_STAGE2C_FREEZE_QA.md` |
| Freeze QA creation commit | `b4869f1824ca15c3816a9f54515ab72c7edd7f07` |
| Data/code input base commit | `10f158b7f6b8bf562b22e8b813b65fb70cb7ac8a` |
| Research branch | `research/pre-ovpm-20260905` |
| Additional status | `PROTOCOL_FROZEN_FOR_RETROSPECTIVE_INTERNAL_ANALYSIS` |

**Read-only frozen permalink**：
https://github.com/Jasonnn258/RPent/blob/118d98ccc774ba63f6ad06ab6cd69df8697195b3/analysis/harness_h0/H0_OE_STAGE2C_FROZEN_PREREG.md

以后必须引用**这个 commit/blob**，不能仅使用会移动的 branch 链接。Git blob SHA-1 是 Git 内容地址标识，**不是** Python/本地输出的 `sha256sum`；本次未建立或声称任何数字签名/分支保护。

## 2. 冻结的相关数据 Git 对象

全部对应**同一** `10f158b...` source commit：

| Item | Git blob SHA-1 |
|---|---|
| `analysis/stageR_manifest.csv` | `3972e58f5b356f141fc46c4c9e7da600eb723cfe` |
| `analysis/stageR_same_action_rollouts.csv` | `966dced03ba26f3357bbc7d7f2f1c31e547e162c` |
| `analysis/stageR_resample_rollouts.csv` | `919906ce8f6c7db38dbf226f41210793a6b9e351` |
| `analysis/stageR_failure_events.jsonl` | `74e15deb7c42ce8306d4752c7d4401b7954d824e` |
| `analysis/stageR_event_probabilities.csv` (research-only, model-input forbidden) | `5ec8a3c0a9044410ebc25cc36b60af1b4f4a069e` |
| `analysis/stageR_prereg.md` | `0eba5d6098bbd61703d59451311525ebe947d6f1` |
| `analysis/STAGE_R_FINAL_REPORT.md` | `96f58e0c40982780d41c8593bbbab9c865ea1375` |
| `scripts/stageR1_run.py` | `3afb9c8334c130d4f3866f1dfcd972b0ec0e6c2f` |
| `scripts/stageR_rt.py` | `526f3aaff8623c737dc8e8675ec583eaadc0c3aa` |
| `scripts/stageQ_rt.py` | `356901453e0d4715196424709c617927e7088875` |

`stageR_trial_checkpoints.jsonl`：服务器本地已完成 484 记录/12,641 cps 的字段与键对账；其中四条额外键属于 `R0_DEV` 的 `dev-r1-fix` 审计记录，**不是模型输入**，没有本次 Git Blob 哈希。R1 480/480 的结构键此前核验通过。服务器**当前**各文件字节与冻结 Git commit 的一致性未在本轮做本地 SHA256 校验，未来要先验证才能运行。

**新结果分析器**：不存在，`analysis_script_sha=NOT_CREATED`、`environment_lock=NOT_RECORDED`、`rng_implementation=NOT_SPECIFIED`。这不使协议本身失去“文档冻结”身份，但意味着**任何模型拟合/统计均未具备执行资格**；未来若批准实施，必须先审查与 v1 的一致性并建立运行清单，不得反向修订 v1 的 primary/statistical claims。

## 3. 非代码冻结验收与需要单独授权的工作

- **核心对象冻结**：OE2a SAME k=2→Y3、R1 24 event、独立事件 LOEO、M0 Beta(1,1) 公平前缀更新、M1 固定 `mu/tau` 网格 Beta-Binomial、单一平均 Brier delta。
- **不确定性定位冻结**：固定 OOF 的简单 event bootstrap 只作描述，**无严格检验**；样本不足/异常需输出 INCONCLUSIVE/STOP；OE1a/OE3a secondary/exploratory、OE1b 独立假阳率不可识别、M2 物理时序因果不可识别。
- **科学创新边界冻结**：Beta-Binomial 是已有统计工具，可能的回顾性预测改善**不能**自动证明 PAEG/N1 新算法。
- **原始资产**：本轮对原始 CSV、checkpoint、代码、Stage R 冻结文档均为只读；唯一新文件为 `analysis/harness_h0/` 下的冻结协议、协议 QA 与本 lockfile。
- **下次任务**：`Stage 2D` 必须**用户另行明确批准**；如批准，先做输入字节校验/分析器实现审查与脚本/环境 SHA，再按独立批准范围决定是否运行纯离线模型/统计。本文件自身不授权 Stage2D。
- **永久约束**：Stage R §36 Hard STOP、S1-DEV0 ON_HOLD、生效的原 E14/A1/P5/U4 分类、禁止 rollout/新 VLA env boot/模型训练/Recovery/Controller 等均保持。

## 4. 变更控制（无需信任移动分支）

1. 即使后续 `research/pre-ovpm-20260905` 增加记录，**原始冻结 v1 的引用不变**，GitHub immutable commit permalink 优先。
2. 任何必要文字更正只能追加新的 `FREEZE_DEVIATIONS.md` 或新版本文档，不得覆盖 `H0_OE_STAGE2C_FROZEN_PREREG.md`；**实质方法变更必须另获用户批准**。
3. GitHub SHA 由工具远端对象读回核对，而非从文件名推测；若未来 commit/blob 无法读取或校验不一致，停止任何结果分析并先解决 provenance。
4. 本次没有运行结果统计、功效估计、模拟、拟合、bootstrap 或 env/rollout。

**FINAL：`STAGE_2C_FREEZE_COMPLETED / STAGE_2D_NOT_AUTHORIZED`。**
