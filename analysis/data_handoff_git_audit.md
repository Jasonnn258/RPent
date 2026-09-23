# Data Handoff — Git 状态审计(data_handoff_git_audit.md)

_生成于 2026-09-23(data handoff 轮 §1)。本文件记录 handoff 开始时的 git 状态,
以及 §3(commit CSV)/§4(push)的执行结果。只读审计,不改历史。_

## 1. 审计快照(§1,commit CSV 之前)

| 项 | 值 |
|---|---|
| 当前分支 | `research/pre-ovpm-20260905`(全程未 checkout 其它分支) |
| HEAD SHA | `c439c7af22c5dc6ea89ab140cfa5a53f92a313c9` |
| 相对 origin/main 领先 | **52 commits**(621 files,~49k 行;Stage A → G0.6 全弧) |
| 远端 | origin = Jasonnn258/RPent(fetch 走 gh-proxy,push 直连 github.com) |
| 远端已有分支 | 仅 `main`(d344c0e);research 分支此前从未 push |

**dirty files(1)**:`analysis/outcome_validation_runs.csv`(M)
= G0.6 重跑补齐 63 格后新增的最终 63 行,尚待 §3 commit。

**untracked(3,按仓库惯例不 track)**:
- `outcome_validation_runs.csv.bak-20260918-outage`(209K)
- `outcome_validation_runs.csv.bak2-20260918-postoutage`(210K)
- `outcome_validation_runs.csv.bak-20260922-quota429`(312K,429 事故手术前备份,
  被 stageG06_quota429_incident.md 引用为证据,保留本地)

**ignored raw-log roots(gitignore,永不入 git)**:
`logs/`(episode 原始输出,含本 handoff 的 180 个 final episode 目录)、
`.gap_run/`(调度器日志)、`/resources/`(Memory 卡与 task_only 数据)、
`checkpoints/`、`downloads/`、`rpent-logs*.tar.zst`、`archive` 类 tar 包。

## 2. §2 CSV 最终态核查(全过,无歧义)

对 `analysis/outcome_validation_runs.csv`(1019 行)按 G0.6 预注册网格过滤
(tier=glm-5.3-flash, r=1, suite=libero_spatial_task, t∈{3,5,9}, s1-s20,
P0=g05/g05P0, P2=g05/g05P2, P4=g0/g0D):

- **180 行 = 60/60/60** ✓(与 stageG06_runs.csv 及已发布数字一致)
- **全键重复 = 0**(整个 CSV 1019 行按 (stage,tier,suite,task,seed,cond,repeat)
  全键查重,零重复 → 无"重复追加"落盘错误)✓
- **infra 残留 = 0**(三臂 result 分布:success 160 / policy_fail 20,
  无任何 infra_*)✓
- **180/180 的 `dir` 列非空且目录存在** ✓

结论:该文件就是 G0.6 最终分析实际使用的版本,§3 直接 commit,无需修改。

## 3. §3 执行记录:commit 最终 CSV

- commit 内容:仅 `analysis/outcome_validation_runs.csv`(+63 行)。
- 不含:*.bak(3 个)、logs/、.gap_run/、resources/ 等一切 raw log。
- commit message:`finalize G0.6 outcome validation runs`
- commit 后复核:`git status` 确认无大文件被误 track(结果见 §5)。

## 4. §4 执行记录:push 分支

- 命令:`git push -u origin research/pre-ovpm-20260905`(普通 push,
  未用 --force / --force-with-lease;http.version=HTTP/1.1)
- **结果:成功。** 2026-09-23 首次将 research 分支推上 GitHub:
  - 远端分支:`refs/heads/research/pre-ovpm-20260905`
    (https://github.com/Jasonnn258/RPent/tree/research/pre-ovpm-20260905)
  - 远端 SHA:`afb7a89be4036bd18ced58192966af4bbd5aff65`(ls-remote 核对一致)
  - 本地分支已设 upstream 跟踪;远端此前仅有 main
  - 注:fetch 走的 gh-proxy 当时 503,但 push 直连 github.com 不受影响

## 5. commit 后 status 复核

`afb7a89` 只含 1 个文件(outcome_validation_runs.csv,+63 行),
无任何大文件 / raw log / *.bak 被误 track。工作区仅剩:
3 个 .bak(刻意不跟踪)+ 本审计文档(随 handoff 文档批次稍后 commit)。
