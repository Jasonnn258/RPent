# Stage L §0 — 资产审计:快照池盘点 + HELDOUT 可行性

_生成:2026-09-30 | 扫描器:scripts/stageL_pool_scan.py →
analysis/stageL_pool_inventory.jsonl(696 行)_
_fire 检测 = analyze_stageH1.replay_fires(与 Stage H/K 同一离线代码路径);
老集无 memory 事件可交叉核对(H1 特有过滤),prereg 记录此差异。_

## 1. 判定:HELDOUT_TEST 可行 —— 无需新采

**32 个池外全新 (task,seed) 对、486 集、364 fire,与 Stage K/L 开发侧
零交集**(构造即隔离:扫描器排除 h1 池对 + K 全部已用对)。

| HELDOUT 候选(只检测,未看任何恢复结果) | 对 | 有 fire 集 | fire |
|---|---|---|---|
| FALSE_GRASP | 19 | 90 | 126 |
| RELEASE_PREDICATE_STALL | 26 | 173 | 190 |
| MOVE_CONTACT_STALL(不纳入,见 §4) | — | — | 48 |

覆盖 t3/t5/t9;老 campaign(20260905/20260915)与 H1 集(20260928)
states.json schema 逐字段一致(pi0_pick result 键同构),replay_fires
三个年代全通,零 scan_error。

## 2. K 已消耗侧(L 的 DISCOVERY/DEV/CAL 素材)

K 数据集 34 集 + K0 标定 6 集,fire 级清单(role×族,行 = fire):

| role | FG | RPS | MCS | 合计 |
|---|---|---|---|---|
| K_TRAIN | 27 | 5 | 2 | 34 |
| K_VAL | 10 | 4 | 2 | 16 |
| K_TEST | 10 | 3 | 0 | 13 |
| K0 标定(CAL) | 7 | 4 | 2 | 13 |

**挖掘产量预报**(fire 级 first_validating 在位 = 正例 prefix 源,
H 冻结契约:FG/RPS = pi0_pick 真实 lift≥5mm 或集终止成功):

- FG 正例 33(TRAIN 22 + VAL 5 + TEST 3 + CAL 3);负例 fire ~21;
- RPS 正例 8(TRAIN 4 + VAL 2 + TEST 2);负例 fire ~9;
- 恢复动作分布:release 20 / pi0_pick 19 / move_to 2 / pi0_doubled 2;
  term 型(集终止)95.3% —— 多数 prefix 终于"任务成功步",
  GRASP_CONFIRMED 型(pi0_pick+lift)19 条,两类都算 recovery-completing。

## 3. 重放/执行基建就绪度

- 快照重放 = K 采集器同款(episode_dir/states.json 逐命令重放 →
  save_state 快照 → 逐边执行),J0 已证逐位精确;老集 schema 兼容(§1);
- 边执行器 = stagek_graph_executor(Verifier B 物理契约复用 K §5 冻结式:
  FG = obj lift≥0.01∧follows-EEF 或 pick 证据;RPS = check_success 窗;
  HARM = held-drop / 无 VERIFIED 位移≥5cm;precedence V>H>N);
- Pi0.5 sampling seed 不可控(k=1..K 重复执行,K0 同款)→ 配对方差
  按重复数吸收,prereg 记录。

## 4. Family inclusion(看 HELDOUT 前冻结)

- **纳入:FALSE_GRASP、RELEASE_PREDICATE_STALL**(正例源 33/8,
  K 侧 DEV 快照 24/10,HELDOUT 深度 90/173 集);
- **不纳入:MOVE_CONTACT_STALL** —— K 侧正例源仅 2(不足以形成
  candidate),DEV 侧无既控 MCS 快照;HELDOUT 虽有 48 fire 但
  开发侧无法形成/验证 candidate,"凑三类"违反 spec §3;
- MCS 不纳入与 Stage K 决策一致(结构性缺位)。

## 5. 预算量级(供 prereg 冻结具体清单)

按 K 实测 ~10.5s/rollout、快照 boot ~40s:
- DEV 侧(候选验证):~34 快照 × (~10 候选) × K=4 ≈ 1300 rollouts ≈ 4h;
- HELDOUT 侧(frozen + evolved + raw 池):~24 快照 × (~19 边) × 4
  ≈ 1800 rollouts ≈ 5.5h。
prereg 将冻结精确快照/候选清单与预算上限;总量 ≈ 10h GPU,
分批执行(锁 + 断点续采,超预算即停)。

## 6. 数据纪律核对(spec §3)

- K-TEST 对子不入 L-HELDOUT ✓(HELDOUT 候选 = 池外对,构造隔离);
- 同快照重复 rollout 同 split ✓(快照整体归属唯一 split);
- HELDOUT 扫描只记 detection(fire 步/族/合法边),不记任何
  恢复/验证状态 ✓(扫描器刻意省略 first_validating/episode_sr);
- family inclusion 于看 HELDOUT 前冻结 ✓(本文 §4)。
