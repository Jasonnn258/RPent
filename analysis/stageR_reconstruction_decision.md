# Stage R R0 — 重建资格判定(DEV pilot 8 事件)

生成:2026-10-08T04:34:31

| 臂 | n | stable | rate |
|---|---|---|---|
| LIVE | 32 | 12 | 0.375 |
| SNAP | 32 | 10 | 0.312 |
| PREFIX | 32 | 12 | 0.375 |

|SNAP−LIVE| = 0.062;|PREFIX−LIVE| = 0.000(门 ≤0.10)

PREFIX sha 逐位一致率:1.000;flatten Δmax 中位:0.0

## 判定:QUALIFIED;R1 重建方法冻结 = PREFIX

选择规则:|PREFIX−LIVE| ≤ |SNAP−LIVE|+5pp → PREFIX_REPLAY, 否则 DIRECT_SNAPSHOT。R1 全程使用该方法,禁切换。
