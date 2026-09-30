# STAGE K FINAL REPORT — Predict-Then-Verify Distributional Graph

_生成:2026-09-30 | 判定依据:用户冻结 spec §0-§17 + stageK0_prereg.md +
stageK1_model_spec.md(FINAL,先于训练 commit 8b4d143)_
_数据集 commit e6e4b48(312 rollouts,manifest 冻结先于训练)_

## 总判定

**K1 资格门 FAIL → WORLD MODEL NOT JUSTIFIED → STOP(禁入 K2,未进入)。**

§9 门操作化结果(TEST 单触,3-seed 集成,n=76):

| 门 | 判据 | 实测 | 结果 |
|---|---|---|---|
| g1 WM vs 静态视觉 | Brier 相对降 ≥10% ∧(排序 +8pp ∨ regret −20%) | +6.6% / −21.4pp / 0% | **FAIL** |
| g2 HARM AUROC | ≥0.75 | 0.446(低于随机) | **FAIL** |
| g3 Oracle 须胜静态视觉 | Brier ≤0.9×B1 或 pairwise +8pp | 0.092 ≤ 0.100(仅 Brier 过) | PASS |
| 族非负(FG/RPS) | B2 族 Brier ≤ B1+0.05 | FG 0.197≤0.211 / RPS ≈0 | PASS |
| **总门** | 全部 | g1 ∧ g2 假 | **FAIL** |

四臂主表(TEST,AUROC/AUPRC/Brier/ECE/pairwise):

| 臂 | 输入 | AUROC | AUPRC | Brier | ECE | harm AUROC | pairwise |
|---|---|---|---|---|---|---|---|
| B0 STATE_ONLY | s | **0.889** | **0.521** | **0.069** | **0.054** | 0.662 | 0.500 |
| B1 STATIC_VISUAL | s+z_pre | 0.823 | 0.293 | 0.111 | 0.175 | 0.176 | **0.714** |
| B2 GRAPH_WORLD_MODEL | s+z_pre+edge(动态) | 0.823 | 0.293 | 0.104 | 0.167 | 0.446 | 0.500 |
| B3 ORACLE_FUTURE | s+z_pre+z_post | 0.826 | 0.280 | 0.092 | 0.088 | 0.628 | 0.571 |

## §16 九问直答

**Q1. 当前视觉 latent 是否包含可用于判断真实 physical transition 的信息?**
**INCONCLUSIVE** —— Oracle(B3,看得到真实后置帧)仅在 Brier 上胜静态视觉
(0.092 vs 0.111,g3 过),AUROC/AUPRC 无增益(0.826/0.280 vs 0.823/0.293);
且全部视觉臂全面弱于不看图的 B0。"latent 含判别信息"既未被证实也未被证伪,
上限极低是确定的。

**Q2. Structured state alone 是否已经足够?**
**SUPPORTED** —— B0(EEF+夹爪+task/family/edge one-hot,14 维)在
Brier/NLL/ECE/AUROC/AUPRC 五项全部最优。注意边界:VERIFIED 48 条全部来自
FG-3 一条边,edge one-hot 即可承载大部分信号,"state 足够"成立于当前
5 边词表与该结局分布下,不外推到通用 WM 主张。

**Q3. Static current observation 是否已经足够,还是 action-conditioned
future dynamics 确实提供额外信息?**
**NOT SUPPORTED**(额外信息部分)—— B2 相对 B1:Brier 仅 +6.6%(<10% 门),
pairwise 反降 21.4pp(0.714→0.500),regret 零变化。action-conditioned
latent 动态没有提供超出静态观测的可判别增量。

**Q4. World Model 能否校准地预测 recovery / no-effect / harm?**
**NOT SUPPORTED** —— B2 结局 ECE 0.167(B0 为 0.054);HARM AUROC 0.446,
低于随机(g2 门 0.75)。HARM 样本仅 16 条(FG-3 9 + RS-2 7),分布上
几乎不可学,但预注册门按原分布判定,不做事后豁免。

**Q5. World Model 是否真正改善 Graph Edge ranking?**
**NOT SUPPORTED** —— 快照内合法边排序:pairwise 0.500(等于抛硬币),
top-1 best-edge recall 四臂同 0.250;regret_verified 全臂为 0
(经验最优边在 FG 族恒为 FG-3,排序任务在该图上近退化)。

**Q6. WM 选择的 Edge 经真实 repeated physical execution 后,是否获得
更高 verified recovery?**
**INCONCLUSIVE** —— 按预注册 §9,K1 FAIL 禁入 K2,该问题无数据
(负结果保留,K2 未跑)。

**Q7. 收益集中在哪个 failure family?**
**INCONCLUSIVE** —— K1 层面无 WM 收益存在,谈不上集中;经验分布上
可恢复性本身高度家族集中:VERIFIED 100% 在 FALSE_GRASP 的 FG-3,
RELEASE_PREDICATE_STALL 三边零 VERIFIED(RS-2 另贡献 7 条 HARM)。

**Q8. 当前瓶颈是 representation、dynamics prediction、Graph candidate
quality,还是 VLA execution stochasticity?**
**INCONCLUSIVE(证据指向:representation + Graph candidate quality)**
—— (a) representation:冻结 DINOv2 latent 全程负贡献,连 oracle 后置帧
都追不上 14 维结构化状态;(b) candidate quality:5 条合法边中仅 1 条
(FG-3)产生 VERIFIED,结局 248/48/16 严重不平衡,排序任务退化;
(c) dynamics:B2 无任何增量(Q3);(d) VLA 随机性:K0 已用 K_ROLLOUT=4
吸收进经验分布估计,不是本轮可测瓶颈。

**Q9. 是否有足够证据进入新的 full-episode Predict-Then-Verify Graph Study?**
**NOT SUPPORTED** —— K1 门 FAIL,WM 未被证明 justified;按 §9/§17,
full-episode campaign 与 K2 一并禁止,负结果保留。

## 数据与执行账目

- **K0**(stageK0_decision.md):主跑 256 槽 ok=224 / infra=96;两执行器 bug
  (RS-1 嵌套 ${eef}、CS-1 mask_rows 运行期名)修复 + --only 定点补采 64/64;
  readback 全 0.0(J0 逐位恢复语义成立);K_ROLLOUT 冻结 = 4(ladder 最小
  达标档;CI_harm 0.245 贴 0.25 边界,机械执行不做酌情调整);
- **§3 数据集**:34 快照(FG 14/5/5、RPS 5/2/3 = TRAIN/VAL/TEST)× 合法边
  × K=4 = 312 rollouts;采集全程 attempt=1、零 infra、readback 全 0.0;
  final_step 由 states.json 对齐重建(跳过 step_idx≤T 重放 prefix + chain
  严格 + n_win 逐条吻合,dry-run 34/34 零违例);
- **K1 训练**:λ 网格 27 组(B2 seed0,VAL-only)冻结 state=0.1 /
  transition=3.0 / harm=0.1(VAL CE 0.3018 无平手);12 模型
  (4 臂 × seeds{0,1,2}),minibatch 64 + VAL early-stop;
  checkpoint meta 含 git commit/config hash/split hash/encoder/seed(§15);
- **过程缺陷(全部修于 TEST 触碰之前)**:B2 GRUCell input/hidden 反置、
  MDN 头输出布局错、B0 误并入 z_proj(致 B0≡B1,由 VAL 同分暴露)、
  vla 环境无 sklearn(换本地实现;首次 eval 启动在 import 处崩溃,
  未产出任何指标,TEST 的指标性触碰仍仅一次);
- **偏离记录**:MCS 族结构缺位(K0 决策文档三证据:标定池耗尽/h0 无
  episode_dir/1018 路径不存在),§9 族条款按 FG/RPS 两族解读。

## §15 工件清单

已产出并 commit:stageK0_distribution_calibration.csv、
stageK_transition_dataset_manifest.csv、stageK1_train_config.json、
stageK1_model_spec.md(FINAL)、stageK1_metrics.csv、stageK1_results.md、
本报告;另:stageK_transition_rollouts.jsonl、stageK1_feature_store.npz、
stageK1_lambda_grid.csv、stageK1_encoder_fingerprint.json、
stageK1_training_hist/(12 曲线)。
**未产出:stageK2_*.csv/md —— K2 被资格门禁止,非缺失。**

## §17 STOP

Stage K 到此 STOP。未启动:full-episode WM Graph campaign、Graph evolution、
new edges、new encoder、larger world model、SFT、OPD、RL、local LLM router。
负结果(本报告全部)保留。
