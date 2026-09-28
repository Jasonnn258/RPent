# Stage H1 — graph 触发器离线重放校验(§3(b))

_2026-09-28 by scripts/replay_stageH1_trigger.py。180 集真实
 states.json 逐 result 过**运行时** DecisionMemory(graph+
graph_block)路径,与基准 148 点逐点比对。_

## 结果

| 类 | 数量 | 说明 |
|---|---|---|
| 基准点 ↔ 重放 fire 逐一匹配(节点一致) | 145 | |
| 基准点被冷却/上限丢弃 | 3 | 合法(冻结冲刷语义) |
| 重放多出:REL 未来窗类 | 42 | 合法(runtime 不可
知未来;基准事后排除) |
| 基准点缺失(非冷却) | 0 | **必须为 0** |
| 重放多出(非 REL 未来窗) | 0 | **必须为 0** |
| 节点不一致 | 0 | **必须为 0** |

## 判定
**REPLAY VALIDATION PASS** — 运行时触发器与基准决策点一致,可以进入在线实验。

### 冷却/上限丢弃(前 15)
| episode | step | family |
|---|---|---|
| `8_glm-5.3-flash_g05P2_libero_spatial_task_t3_s9_r1` | 6 | RELEASE_PREDICATE_STALL |
| `_glm-5.3-flash_g05P0_libero_spatial_task_t3_s11_r1` | 8 | RELEASE_PREDICATE_STALL |
| `_glm-5.3-flash_g05P2_libero_spatial_task_t9_s13_r1` | 11 | MOVE_CONTACT_STALL |

### REL 未来窗多出(前 15)
| episode | step |
|---|---|
| `_glm-5.3-flash_g05P0_libero_spatial_task_t3_s11_r1` | 12 |
| `_glm-5.3-flash_g05P0_libero_spatial_task_t3_s18_r1` | 14 |
| `_glm-5.3-flash_g05P2_libero_spatial_task_t3_s20_r1` | 8 |
| `5_glm-5.3-flash_g05P2_libero_spatial_task_t5_s1_r1` | 12 |
| `1_glm-5.3-flash_g05P2_libero_spatial_task_t5_s3_r1` | 6 |
| `3_glm-5.3-flash_g05P0_libero_spatial_task_t5_s4_r1` | 11 |
| `4_glm-5.3-flash_g05P2_libero_spatial_task_t5_s4_r1` | 7 |
| `1_glm-5.3-flash_g05P0_libero_spatial_task_t5_s5_r1` | 7 |
| `:20_glm-5.3-flash_g0D_libero_spatial_task_t5_s5_r1` | 7 |
| `6_glm-5.3-flash_g05P0_libero_spatial_task_t5_s7_r1` | 9 |
| `:11_glm-5.3-flash_g0D_libero_spatial_task_t5_s7_r1` | 7 |
| `8_glm-5.3-flash_g05P2_libero_spatial_task_t5_s9_r1` | 7 |
| `_glm-5.3-flash_g05P0_libero_spatial_task_t5_s12_r1` | 8 |
| `_glm-5.3-flash_g05P2_libero_spatial_task_t5_s12_r1` | 6 |
| `29_glm-5.3-flash_g0D_libero_spatial_task_t5_s12_r1` | 7 |