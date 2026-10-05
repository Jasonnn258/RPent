# Stage P1 Results — Candidate Support Geometry

生成:2026-10-04T16:00:41.707981 | runner:scripts/stageP_geometry.py
| prereg §7 | manifest:stageP_split_manifest.csv(24 可用:DEV 13/TEST 11)

## TEST(12 预定,实测 11,confirmatory)

| 指标 | 值 | Wilson 95% CI |
|---|---|---|
| Oracle@1 | 0.900 | [0.596, 0.982] |
| Oracle@2 | 0.900 | [0.596, 0.982] |
| Oracle@4 | 1.000 | [0.722, 1.000] |
| Oracle@8 | 1.000 | [0.722, 1.000] |
| SUPPORTED_RATE | 1.000 | [0.722, 1.000] |
| MIXED_RATE | 0.600 | [0.313, 0.832] |

**Oracle@8 − Oracle@1 = 0.100**(gate ≥15%)

## DEV(13,sanity/特征理解,不进判定)

| Oracle@1 | Oracle@2 | Oracle@4 | Oracle@8 | SUPPORTED | MIXED |
|---|---|---|---|---|---|
| 0.750 | 0.833 | 0.917 | 1.000 | 1.000 | 0.500 |

## Per-snapshot 明细

| snapshot | split | n_cand | O@1 | O@2 | O@4 | O@8 | mixed | n_rec_cand | first_rec_idx |
|---|---|---|---|---|---|---|---|---|---|
| psnap_05 | TEST | 8 | 1 | 1 | 1 | 1 | 1 | 7 | 1 |
| psnap_07 | TEST | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_09 | TEST | 8 | 1 | 1 | 1 | 1 | 1 | 7 | 1 |
| psnap_11 | TEST | 8 | 1 | 1 | 1 | 1 | 1 | 5 | 1 |
| psnap_13 | TEST | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_15 | TEST | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_19 | TEST | 8 | 1 | 1 | 1 | 1 | 1 | 7 | 1 |
| psnap_21 | TEST | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_25 | TEST | 8 | 0 | 0 | 1 | 1 | 1 | 1 | 3 |
| psnap_27 | TEST | 8 | 1 | 1 | 1 | 1 | 1 | 5 | 1 |
| psnap_00 | DEV | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_02 | DEV | 8 | 0 | 1 | 1 | 1 | 1 | 1 | 2 |
| psnap_04 | DEV | 8 | 1 | 1 | 1 | 1 | 1 | 5 | 1 |
| psnap_06 | DEV | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_08 | DEV | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_10 | DEV | 8 | 1 | 1 | 1 | 1 | 1 | 7 | 1 |
| psnap_12 | DEV | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_14 | DEV | 8 | 0 | 0 | 1 | 1 | 1 | 6 | 3 |
| psnap_16 | DEV | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_20 | DEV | 8 | 1 | 1 | 1 | 1 | 0 | 8 | 1 |
| psnap_24 | DEV | 8 | 1 | 1 | 1 | 1 | 1 | 7 | 1 |
| psnap_26 | DEV | 8 | 0 | 0 | 0 | 1 | 1 | 2 | 5 |