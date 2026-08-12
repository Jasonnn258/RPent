# LIBERO Failure Analysis: t0 / t7 / t9

诊断性分析（不改模型 / Prompt / 实验配置）。样本取自现有 logs（4 个 suite：spatial、goal_task、goal_swap、spatial_task），t7 为 easy control，t0 / t9 为 hard。每类各抽样 ~5 成功 + ~5 失败，共 29 run。原始 turn 级数据见 `failure_analysis_t0_t7_t9.csv`，解析脚本 `analyze_turns.py`。

---

## 1. t7 / t0 / t9 对比表

| 维度 | t7 (easy) | t0 (hard A) | t9 (hard B) |
|---|---|---|---|
| 整体成功率 | ~71%（最高） | ~29%（最低） | ~29%（最低） |
| 成功 run 感知占比 | 0.29–0.45 | **0.56–0.64** | 0.40–0.49 |
| 成功 run 动作数 | **2**（1-shot 抓放） | 7–9 | 5–12 |
| 失败 run 感知占比 | 0.45–0.68 | 0.49–0.67 | 0.28–0.55 |
| 失败 max_redundant | 7–15 | 5–13 | **16–22** |
| 失败动作模式 | **move_to 循环**（7–10 次） | move_to 循环 / **pi0_doubled×12** | **pi0_pick×2–4** + move_to |
| 失败终点 | max_turns | max_turns / finish_no_success | max_turns / infra_timeout |

**关键观察**：
- **成功 t0 的感知占比反而最高**（0.6）——充分感知是 t0 成功的前提，不是失败源。
- **t9 失败的重叠感知（redundant）最严重**（max_redundant 16–22），且 pi0 反复重试。
- **t7 失败是 move_to 重定位循环**（easy 任务也会因重新定位耗尽回合）。

---

## 2. 典型失败链（每类 2–3 条）

### t7 失败 — 重定位循环
```
6×back_project → move_to → move_to → read_image → back_project → pi0_pick  (max_turns=40, move_to×10)
感知充分但 move_to 反复 repositioning，pi0_pick 仅 1 次 → 执行不足，回合耗尽
```

### t0 失败 — 执行后 recovery 循环 / 过度阅读
```
t0 A (move_to×17): 4×back_project → move_to×2 → pi0_pick → read_image → set_gripper → back_project → move_to×2 ...
  执行后反复回感知重新定位 → 动作未收敛
t0 B (pi0_doubled×12): 20+×read_text_file(memory) → 3×back_project → 后续 12×pi0_doubled
  前期过度阅读 memory，后期放置反复失败重试
```

### t9 失败 — 感知循环 + 抓取重试
```
6×back_project + 3×segment + read_image → 后续 pi0_pick×4
  max_redundant=22：连续感知不行动；pi0_pick 反复 = 单次抓取/放置精度不足
```

### 对照成功链
```
t7 OK (1-shot): 3×back_project → move_to → pi0_pick → finish        (act=2, 极简)
t9 OK (pi0_doubled): 3×segment + 4×back_project → move_to → pi0_pick → set_gripper → pi0_doubled
  t9 成功靠“双段放置”补精度；失败者单次 release 精度不足
```

---

## 3. Failure Taxonomy（当前最可信）

| # | 类型 | 判据 | 主要出现 |
|---|---|---|---|
| F1 | **感知循环** redundant perception | 连续感知无动作 ≥ 10 | t9 fail (16–22), t0 fail |
| F2 | **重定位循环** move_to loop | move_to ≥ 7 次，执行后反复重定位 | t7 fail, t0 fail |
| F3 | **执行精度重试** grasp/place retry | pi0_pick / pi0_doubled ≥ 3 次 | t9 fail, t0 fail (pi0_doubled×12) |
| F4 | **过度阅读** over-reading memory | read_text_file ≥ 10 次 | t0 fail |
| F5 | infra（超时/崩溃） | API timeout / 无 states | 偶发 |

失败 run 通常是 **F1/F2/F3 组合**：感知循环 → 执行失败 → 重定位循环 → 回合耗尽。

---

## 4. 两个 Hypothesis 的验证结论

### H1：t0 = spatial grounding / object disambiguation 瓶颈 → **部分支持，但需修正**
- **支持面**：t0 场景含两个相似对象（如两个黑碗），需空间关系区分（plate 与 ramekin 之间的那个）；成功者感知充分（perc_ratio 0.6）、ground_seg_hits > 0。
- **修正面**：失败 t0 的模式主要是**执行后 recovery 循环**（move_to×17 重定位 / pi0_doubled×12 放置重试），而非初始定位失败。区分后的执行失败（选错/放置失败）驱动后续循环。
- **结论**：t0 瓶颈 = **disambiguation 后的执行/放置收敛问题**，不纯是 grounding。

### H2：t9 = precision / execution 瓶颈 → **强支持**
- 失败 t9：pi0_pick×2–4（抓取反复）、move_to 重试、max_redundant 16–22。
- 成功 t9 依赖 **pi0_doubled（双段放置）** 补精度；单次 release 精度不足。
- **结论**：t9 核心瓶颈是**精细操作执行精度**（抓取 + 放置），感知循环是执行失败后的症状。

### "perception 占比高是根因还是症状" → **是症状，不是根因**
- 成功 run 的感知占比也高（t0 success 0.6）——感知本身不是失败原因。
- 真正的区分信号是 **redundant 感知**（连续不行动）与 **执行重试模式**（move_to / pi0 重复），二者都是**执行失败后的 recovery 行为**。
- 结论：**高感知占比是 grounding 不确定 + recovery 失败的症状**，根因在执行精度（t9）与区分后收敛（t0）。

---

## 5. 最小 Ablation 建议（不实现）

| 方向 | 假设 | 最小改动 | 验证 |
|---|---|---|---|
| **A. t9 强制双段放置** | precision 是根因 | Prompt 引导 place 阶段用 `pi0_doubled`（而非单次 release） | 若 t9 成功率↑ → precision 假设成立 |
| **B. t0 强制对象区分流程** | disambiguation 是前提 | Prompt 要求"先 segment 两个候选，再按 spatial relation 选择" | 若 t0 选错率↓ → grounding 假设 |
| **C. 收紧感知预算** | redundant 感知是浪费 | Rule 2e 从 8 次降到 5 次 back_project | 若 max_redundant↓ 且成功率不变/↑ |
| **D. 执行重试上限** | recovery 循环耗回合 | 对 move_to/pi0 失败后最多 N 次重试，之后诚实上报 | 若回合利用↑ |

**建议优先级**：A（t9，假设最明确）> B（t0）> C/D（通用健壮性）。
