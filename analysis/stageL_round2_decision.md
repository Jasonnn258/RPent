# Stage L Round 2 决策(DEV,prereg §10 一次性判定)

- rollouts: 352(A-FAIL 0 条不计效力,单列)
- split_hash 77695bed7074 | K_ROLLOUT=4 | λ_harm=1.0

## LC-RS-1R(RELEASE_PREDICATE_STALL,源 4 集)
- elig = 6(min-N 3 → ✓)| exec_consistency 1.0 (✓)| harm 0.208 (✗)
- f* = RS-1(elig 上 P̂_v 均值 0.0)| mean_adv 0.0| adv>0 占比 0.0 → Path A ✗
- 冻结全零快照 |U| = 6 | cover 0.0 → Path B ✗
- pair 级排除敏感性:elig(pair) = 3(episode 级 6)
- **判定:REJECT**

## 冻结边基线(同批 DEV 重跑,快照级 P̂_v)

- FG-1:n_snap=24 mean P̂_v=0.0 mean P̂_h=0.0
- FG-3:n_snap=24 mean P̂_v=0.552 mean P̂_h=0.031
- RS-1:n_snap=10 mean P̂_v=0.0 mean P̂_h=0.0
- RS-2:n_snap=10 mean P̂_v=0.0 mean P̂_h=0.15
- RS-3:n_snap=10 mean P̂_v=0.0 mean P̂_h=0.0

## 判定汇总

| 候选 | 判定 |
|---|---|
| LC-RS-1R | REJECT |