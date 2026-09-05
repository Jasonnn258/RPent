# Reasoning Timing 失败分析 — decision-point 级诊断

_2026-09-05。数据:ModelScope 归档拉回的 36G 原始轨迹(选择性解压 run.log/transcript/states),P0/P1 progress-gate 270 run + SM1 63 run,共 303 个 CSV 登记episode。方法:按里程碑(pick/release 结果)而非 turn 号对齐;per-run 决策流见 `decision_points.jsonl`,run 级证据行见 `reasoning_timing_cases.csv`。_

**一句话结论:这个系统的 timing 问题几乎全部发生在"抓住物体之后"(P_place 前后),而不是感知或抓取阶段——Q1(该 ACT 却继续 OBSERVE/REASON)的主形态是 place-stall, Q2(该 RECOVER 却继续执行)的主形态是 place-fail(重复 release 不换策略)。**

---

## 1. 失败机制分布(按里程碑分类,303 run)

分类器:`no_pick`(死在抓取前)/`grasp_fail`(所有 pick 都没抓住)/`place_stall`(抓住了但从未 release)/`place_fail`(release 了但谓词不触发)/`success`。

| cond | task | no_pick | grasp_fail | **place_stall** | **place_fail** | success |
|---|---|---|---|---|---|---|
| baseline | t0 | 4 | 0 | 4 | **9** | 14/31 |
| baseline | t7 | 0 | 0 | **13** | 5 | 13/31 |
| baseline | t9 | 0 | 0 | 7 | **7** | 17/31 |
| ours | t0 | 2 | 1 | 6 | 9 | 12/30 |
| ours | t7 | 1 | 6 | 7 | 6 | 10/30 |
| ours | t9 | 0 | 0 | 8 | 6 | 16/30 |
| hardcap | t0 | 1 | 0 | 5 | 8 | 16/30 |
| hardcap | t7 | 0 | 2 | **7** | 5 | 16/30 |
| hardcap | t9 | 0 | 0 | 7 | **13** | 10/30 |
| structured | t0 | 1 | 0 | 1 | 2 | 6/10 |
| structured | t7 | 0 | 1 | 0 | 3 | 6/10 |
| structured | t9 | 0 | 0 | 0 | 3 | 7/10 |

三个结构性事实:

1. **grasp 几乎从不失败**(baseline 三任务 0/93)。pi0_pick 一旦执行,首抓 hold 率极高。失败不是"抓不住"。
2. **t7 的失败主流是 place_stall(13/18)**:抓住碗之后,把剩余回合花在"确认拿着、确认位置、微调站位"上,直到预算耗尽,release 永未调用。
3. **t0/t9 的失败主流是 place_fail**(t0:9,t9:7):release 执行了但 `libero_terminated=false`,然后小步微调再 release,仍不收敛。

**同 seed 成败对(55 对)的首次分叉点全部落在第一个 pick 的结果处**(hold/succ/grip 不同或缺失)——但由于 grasp_fail≈0,大多数失败 run 最终也抓住了;真正的分水岭是**错过首抓后的响应**和**放置纪律**。Q1/Q2 的答案都在 P_place。

---

## 2. Q1:什么时候该 ACT 却在 OBSERVE/REASON?

### 2.1 place_stall —— 抓住后不放置(t7 主导,也占 t0/t9 各 ~1/4)

**Case A(教科书案例)** `20260814-18:33:48_libero_spatial_task_t7_s3`(baseline,t7,40 回合耗尽):
```
t23 pi0_pick(hold) → t24 read_image("pick result ambiguous... 0.029 holding something")
→ t25 set_gripper → t26-40: read_image×6 + back_project×4 + move_to×6
t27 think: "Lifted 8cm cleanly and gripper still clamped. Let me confirm the bowl
            is actually with us via the wrist cam before travelling"   ← 前提已满足仍要再验
t36 think: "Now over the plate. Let me check the wrist cam..."          ← 已到位仍要再验
t39 think: "Wrist-refined plate center (0.054,0.208), offset dy=+0.039, target eef_y=0.247"
t40 预算耗尽。release 从未调用。
```
诊断:从 t27 起,每个前置条件(grasp 稳固、目标坐标已知)都已满足,**此后每一次 read_image/back_project 的期望结果都是"确认已知"**——信息增量为零,正确决策是 release(ACT)。规划器把"验证已满足的前提"当成了任务。

stall 的量化签名(见 CSV `moves_after_hold`/`perc_after_hold`/`stall_span` 列):hold→(release 或终点)的间隔里 perc_after_hold≥4 且 moves_after_hold≥4 的 run 几乎全是失败。

### 2.2 no_pick —— 抓取前的感知/重定位循环(t0 独有,4/31)

t0 的双碗歧义导致 grounding 反复:baseline t0 失败 run 的感知链里近重复(同工具、同 step、像素距≤30px)只占 5-7%——**循环不是字面重复,而是"换个像素再试"的不确定性抖动**。此时该做的是"用当前最优估计直接 ACT"(t0 目标容差大,usually 够),而不是继续采样。

### 2.3 冗余的边界:任务相关,不存在通用阈值

- t0/t7:近重复率 5-7%,失败/成功无差 → 长感知链基本是抖动,截断有益。
- **t9:近重复率 19-25%,且成功侧更高**(成功 25% vs 失败 19%)——同一像素反复 back_project 是**放置前的收敛校验**,是成功策略的组成部分。"重复=浪费"在 t9 不成立。

---

## 3. Q2:什么时候必须 RECOVER 却在继续执行?

### 3.1 place_fail —— release 不收敛仍继续微调释放(t9 主导)

**Case B** `20260814-23:39:57_baseline_libero_spatial_task_t9_s1_r2`(40 回合耗尽):
```
t18 pi0_pick(hold) → t29 release(FAIL, term=false)
t30 think: "Released but predicate not fired. Let me inspect where the bowl actually landed."
t36 think: "Gripping the rim. Now drag-shift −0.05 in y..."
t38 release(FAIL) → t40 耗尽
```
诊断:两次 release 失败后的响应(观察落点→小位移拖拽→再 release)方向正确但**幅度/原语错误**——对 t9(精确放置任务),单次 release+微调永远不收敛;失败一次后应升级策略(换 `pi0_doubled` 双段放置,或重新抓取再放)。这正是 R5 规则编码的决策,也是 structured 臂把 t9 place_fail 从 7 压到 3 的机制(§5-B)。

### 3.2 guard 强制的过早 ACT(hardcap 特有)

hardcap(6 连感知硬上限)在 73/90 run 触发 115 次拦截。拦截后规划器大多顺从(下一调用 move_to:t0 24/t7 24/t9 23 次)。但 115 次拦截里只有 7 次拦在"近重复"上,**71 次拦的是换像素/换视角的新查询**:

| 任务 | 拦"新视角"后 run 成败 | 拦"近重复"后 run 成败 |
|---|---|---|
| t0 | 11胜/14败 | — |
| t7 | 11胜/15败 | 1/1 |
| **t9** | **3胜/17败** | 2/3 |

t9 中被拦新视角的 run 83% 失败——强制 ACT 打断的正是放置精度的信息采集。两个 caveat:(a) 同 seed 对照里 t9 的 4 个 hardcap 变败 run **本身零拦截**(行为与 baseline 等价,差异来自采样随机性);(b) 反向因果(失败的 run 更容易感知成瘾→被拦)无法排除。所以"hardcap 直接导致 t9 放置失败"只有 arm 级相关性(place_fail 7→13)+机制旁证,没有同 seed 因果链。

### 3.3 路由器的 Q2(dual-route smoke,n=1)

SMOKE_t7s1:40 步里 fast 只触发 3 次(2×release、1×view_driver_state),都在终局。第一次 fast release 打在**未收敛的放置**上(term=false),随后 router 进入 `p_verify_unterminated` ×14 的 slow 循环直到预算耗尽——**该 RECOVER(重测/重放)时,路由器按既有流程继续 finish 链**。Fast-release 的前置条件("unambiguous")没有任何收敛校验。

---

## 4. 对照 A:hardcap 为何 t0/t7 有益、t9 有害

| 证据 | 支持方向 |
|---|---|
| 同 seed 翻转:t0 +3/−1,t7 +5/−2,t9 +0/−4 | t9 四次翻转全部变败且零拦截 → **t9 的 arm 级差异(53%→33%,z≈2.4)很可能一半是采样噪声** |
| 机制分布:t7 place_stall 13→7,success 13→16 | 强制 ACT 正好打断 t7 的"抓住后反复确认"——对症 ✓ |
| 机制分布:t9 place_fail 7→13 | 强制 ACT 打断 t9 的放置校验采集——误伤 ✓ |
| 拦截内容:71/115 拦的是新视角查询 | hardcap 的计数器无法区分"抖动"与"校验" ✓ |
| t9 近重复率成功侧更高(25% vs 19%) | "重复感知=浪费"的假设在 t9 反向 ✓ |

**结论:有益/有害由任务的失败主形态决定(stall 型→cap 有益;precision 型→cap 有害),而不是任务难度。** ours(progress_gate,按信息变化计)在 90 run 里零触发—— LIBERO 的 grounding 行为(换像素→xyz 必然 >1cm 移动)使"信息不变"条件几乎永不满足,该臂实为惰性,SR≈baseline 只是没起作用,不是"温和起作用"。

## 5. 对照 B:structured memory 改变了哪个决策

11 个同 seed 正向翻转(baseline 败→structured 胜)逐对定位:

- **t9(3 对:全部命中 R5)**:baseline 死于单次 release 精度不足;structured 在 P_place 注入"用 pi0_doubled 双段放置",t9s6 甚至只触发了 R5 一条规则就赢。**改变的是放置原语选择,不碰感知/抓取。**
- **t0/t7(8 对:全部命中 R1,4 对加 R9)**:structured 用更少 move(6/5/4 vs 8/9/6)更少回合(22-35 vs 40)直达放置——R1"连续感知≥7 就 commit"把 P_look/P_transport 的抖动剪掉,R9(剩≤5 回合时最后一搏)把部分 place_stall 变成"放手一 release"。**改变的是 commit 时机,即 Q1。**

规则恢复率(structured_metrics.recovery_success):**R1 29/29(满分)**、R4 2/2、R8 2/2、R7 6/10、R9 9/17、R5 5/10。R1 是全系统最可靠的单一干预;R5/R9 只有五成,但 t9 的 3 个翻转全靠 R5——**没有 R5 时 t9 place_fail 无人能救**。

## 6. 对照 C:dual route(仅 smoke,结论是设计诊断不是性能结论)

- Fast 集合太窄:`{view_driver_state, release, finish}` 全是零参终局动作,21/37 步 `not_fast_eligible` → 全程只省 3 次 LLM 调用(8%)。**真正可省的是中段的机械状态核查**(每次动作后例行的 view_driver_state),它们全走了 Slow。
- Fast 过早案例:终局 release 无收敛校验即触发(§3.3)。
- 有同 seed 对照支持的部分:仅"路由逻辑存在上述两类缺陷"这一静态事实;任何性能论断 n=1,不可用。

---

## 7. Reasoning Timing Taxonomy

按"当前状态 → 应选动作"归纳(判据全部可从 transcript/states 机判):

| 状态签名 | 应选 | 判据(机判) | 违反时的事件名 |
|---|---|---|---|
| P_look/P_transport,同工具连续感知≥5 且近重复率>30% | **ACT**(用当前最优估计 move_to/pick) | t0/t7 失败链;R1 29/29 | F1 抖动(no_pick 的前身) |
| P_look,已获得 ≥2 个一致的 back_project(同目标 xyz 距离<2cm) | **ACT** | 成功 run 平均 3-4 次 back_project 即 commit | 感知过采样 |
| 已 hold,目标坐标已知,无失败信号 | **ACT**(release/搬运) | place_stall 全部违反;t27+ Case A | **Q1 主形态** |
| 已 hold,剩余回合<10,未放置 | **ACT**(立即放置,哪怕粗糙) | R9 9/17 恢复 | 预算尾部 stall |
| pick 返回 miss(未 hold) | **RECOVER**:一次 back_project 修正 + 重 pick(≤2 次),仍败→finish | grasp_fail≈0 说明响应普遍正确 | 少数 loop |
| release 后 term=false(第一次) | **RECOVER**:read_image 定位落点 + 升级原语(t9→pi0_doubled),禁第三次同类 release | Case B;t9 place_fail | **Q2 主形态** |
| release 后 term=false(第二次) | **REASON**:停下重新估计(目标估计错 or 抓取姿态错),换策略而非微调 | Case B t38 | 微调循环 |
| 观察结果与预期一致 | **ACT**(下一个任务步骤) | Case A t27-t36 全违反 | 冗余验证 |
| 观察结果与预期不一致(任何一次) | **OBSERVE/RECOVER**(先诊断后动) | 正常 | — |

**根本问题(证据版)**:规划器没有"期望结果→校验→提交"的闭环。它把每个决策都当成开放的推理题(于是已满足前提仍反复验证=Q1),把失败信号当成噪声(于是 release 失败仍按原策略微调=Q2)。正确结构是每个动作携带 expected_result,结果一致→提交下一个,不一致→触发分级恢复(修正→换原语→放弃)。R1 之所以 29/29,本质是它外部强制执行了"提交"这一步。

## 8. 哪些结论有什么级别的证据

**同 seed 对照支持(强)**:
- t7 失败主形态=place_stall、t9=place_fail(机制表 + 55 对分叉全部在 pick1 之后才定性)
- structured 的增益来源:R1 剪 P_look/P_transport 抖动(t0/t7),R5 换放置原语(t9)——11 个翻转逐对可指认
- hardcap 在 t7 打断 stall、t9 放大 place_fail(机制分布 13→7 / 7→13)
- R1 恢复率 29/29;ours(progress_gate)是惰性臂(90 run 零触发,机制级证据)

**仅 arm 级相关(弱,受采样随机性混杂)**:
- hardcap t9 53%→33% 的量化幅度(同 seed 翻转 0/4 全变败但 4 个败 run 自身零拦截;z≈2.4 边缘显著)
- 拦"新视角"→t9 失败(17/20;反向因果不可排除)
- 记忆/指南读取与 SR 的关系(读取率≈100%,无区分度)

**n=1,仅设计诊断**:dual route fast/slow 的全部性能论断。

**相关工具**:`decision_points.py`(解析)、`pairing_analysis.py`(里程碑配对)、`timing_analysis.py`(粗检测,已被前者取代)、输出 `reasoning_timing_cases.csv`(303 行 run 级证据)、`decision_points.jsonl`。
