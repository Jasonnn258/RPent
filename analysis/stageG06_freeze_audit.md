# Stage G0.6 — Freeze Audit(§2:P0/P2/P4 与 G0.5 完全兼容性证明)

_写于 2026-09-22,先于任何 G0.6 episode。基线提交 = 57428a5(G0.5 实现,
全部 120 集 and 30 复用行都在这个代码上跑成)。_

## 结论

**P0(g05P0)/ P2(g05P2)/ P4(g0D)三臂的运行时行为与 G0.5 完全一致。
自 57428a5 以来,实验面上唯一的变化是 rpent/memory 的注释汉化 —— 已用
AST 等价验证证明其零行为差异。调度器、planner、环境、Memory bank 一个
字节都没动。**

## 证据 1 — git 改动面审计(57428a5..HEAD)

`git log --oneline 57428a5..HEAD -- scripts/ovpm_exp.py rpent/memory/
rpent/planner/ rpent/envs/ resources/libero/` 只返回三个提交,全部是注释
汉化/文件跟踪,无一触碰逻辑:

| 提交 | 内容 | 行为影响 |
|---|---|---|
| bb1f1a9 | 跟踪 rpent/memory/av.py(B3 模块,从未被任何 G0.5 路径 import —— `grep from rpent.memory.av` 零命中) | 无 |
| 3ae9908 | retrieval.py 注释汉化 | 无(AST 证明,见证据 2) |
| c05a704 | 其余 7 个 memory 模块注释汉化 | 无(AST 证明,见证据 2) |

**未出现在改动清单里 = 零改动**:`scripts/ovpm_exp.py`(调度器 + 全部
COND_ENV)、`rpent/planner/`(api_loop/system prompt)、`rpent/envs/`、
`resources/libero/`(61 卡 bank + MEMORY.md 索引)。

## 证据 2 — AST 等价(注释之外的逐节点一致)

`scripts/verify_comment_only.py`:剥掉 docstring 后比较 `ast.dump` —
相等即证明改动只可能落在注释/docstring,所有代码、字符串字面量、冻结
文本、日志消息逐字节相同。

| 文件 | 对比基准 | 结果 |
|---|---|---|
| retrieval.py(触发/检索/注入全部所在) | **57428a5 版本**(= 跑 G0.5 的那一版) | OK |
| structured.py | 汉化前原版(bb1f1a9) | OK |
| stv.py | 汉化前原版 | OK |

api_loop 的 memory import 链(structured / ovpm / stv / dual_route /
retrieval)全部在上述已验证集合内;ovpm/dual_route/schema/__init__ 在
c05a704 提交时已逐一做过同一验证(commit message 记录 7/7)。

## 证据 3 — 三臂 COND_ENV 现值(= G0.5 运行值,一字未动)

| 旋钮 | P4 = g0D | P0 = g05P0 | P2 = g05P2 |
|---|---|---|---|
| RPENT_STRUCTURED_MEMORY | 1 | 1 | 1 |
| RPENT_MEMORY_ACCESS_FIX | 1 | 1 | 1 |
| RPENT_MEMORY_TRIGGER | v1_per_result | v1_per_result | v1_per_result |
| RPENT_MEMORY_QUERY_MODE | common | common | common |
| RPENT_MEMORY_RANK | Q0_FIXED | Q0_FIXED | Q0_FIXED |
| RPENT_MEMORY_QUERY_REASON | (默认,等价 0 语义) | 0 | 0 |
| RPENT_MEMORY_INJECTION_MODE | (默认 full) | none | generic_refresh |

P4 的 G0.6 新集(s11-s20)将以 **stage g0 + cond g0D 原样**运行 —— 与
G0.5 复用的 30 行同 cond 同 env,不存在重新定义。P0/P2 以 stage g05 +
原 cond 运行。**G0.6 不新增任何 cond、不改任何 env 值、不改调度器。**

## 证据 4 — 回归测试(2026-09-22 重跑)

- `scripts/test_stageG0_audit.py`:ALL SECTIONS PASS(v1/progress/
  motion_stuck/Q3/attempt-logging/namespaced-ids 语义未变)
- `scripts/test_stageG05_injection.py`:7/7 GREEN — 含 default==full
  逐字节、F2/F3/F4 逐字渲染、P0 事件 NOT_RUN、env 矛盾 fail-fast

## §2 冻结清单逐项核对

| 冻结项 | 状态 | 证据 |
|---|---|---|
| planner(api_loop + system prompt) | 未动 | 证据 1(git 零提交) |
| Pi0.5 / SAM3 / primitive library | 未动 | 同上(rpent/envs、模型配置无提交) |
| trigger policy(v1_per_result 规则 T1-T7) | 未动 | 证据 2+4 |
| event capture semantics / cooldown / max triggers | 未动 | 证据 2+4(同一段代码) |
| neutral retrieval query(common 组装) | 未动 | 证据 2+4 |
| Q0 检索(词面打分/tie-break) | 未动 | 证据 2+4 |
| Memory bank(61 卡 + MEMORY.md) | 未动 | 证据 1(resources/ 零提交) |
| P2 Generic Refresh 文本(F3) | 未动 | 证据 4(test 3 逐字断言) |
| P4 planner-visible block(_block 含 reason) | 未动 | 证据 4(test 1 逐字节断言) |
| temperature / timeout / turn budget / workers | 未动 | 证据 1 + 调度命令行沿用 G0.5 同值 |

**审计通过。可以进入 §4 seed 审计。**
