# Stage K1 模型规格(草稿)—— B0/B1/B2/B3 四臂

_状态:**FINAL(定稿于任何正式训练之前)** —— 数据集 manifest 已冻结
(commit e6e4b48:312 样本),λ 网格已在 VAL 上跑毕并冻结(本文件 §7)。
规格依据:Stage K spec §4-§6;数据集 = analysis/stageK_dataset_selection.json
+ analysis/stageK_transition_dataset_manifest.csv。_

## 0. 任务定义

每个样本 = (snapshot, edge, rollout):

- 输入(runtime 可见):快照观测特征 + 边 id(图合法结构);
- 监督(来自已采集 rollout 的 verifier 通道,**只作训练目标**,
  永不作 runtime 输入 / 永不被 WM 预测值替代 —— spec 核心红线):
  结局类 {VERIFIED_RECOVERY, NO_EFFECT, HARM} + 物理量
  (Δeef_z, Δgrip, Δooi_z, 残差变化)+ 后置帧 DINOv2 特征(z_post)。

## 1. 冻结特征(§4)

- encoder:facebook/dinov2-base(ViT-B/14,输入 224²,patch 16×16=256 + CLS,
  dim 768),本地快照 commit `f9e44c814b77`(指纹文件
  analysis/stageK1_encoder_fingerprint.json,probe [1,257,768]),
  **全程冻结不训练**;
- 帧选择(装配脚本 stagek1_build_dataset.py 实况):每相机一帧,
  patch-token 均值池化 ⊕ CLS(各 768)→ 1536/帧,agentview⊕wrist → z ∈ R^3072;
- z_pre = 快照 hi-res 拷出帧(images_cam_hi / images_wrist_hi,
  采集时即时拷出以躲 5 步 GC 窗口);z_post = rollout 终帧低清
  (images/image_{final_step}.png + images_wrist/image_wrist_{final_step}.png,
  final_step 由 states.json 对齐重建,34/34 零违例);
- mask pooling:仅当该 rollout 感知步 found=True 时另记 box 内 patch
  均值(诊断用);**主特征不用 mask**(h1 语料分割稀疏,28/148)。

## 2. 低维状态(runtime 可见的本体/夹爪通道)

s = [eef_xyz(3), gripper_opening(1), one-hot(task 3: t3/t5/t9),
one-hot(family 2), one-hot(edge_id 5)] = 14 维 —— **GT 物体位姿不进 s**
(graph spec §5.4 红线;物体位姿只出现在训练目标里)。

## 3. 四臂

| 臂 | 输入 | 结构 | 用途 |
|---|---|---|---|
| B0 STATE_ONLY | s | MLP 2×256 | 基线 |
| B1 STATIC_VISUAL | s + z_pre(降维 512) | MLP 2×512 | 静态基线 |
| B2 GRAPH_WORLD_MODEL | s + z_pre + edge embedding | 见 §4 | 主检验 |
| B3 ORACLE_FUTURE | s + z_pre + **z_post** | 同 B1 | analysis only |

- B3 只进 K1 分析(上界参照),**永不进 runtime/K2**(spec §5);
- 所有臂共享训练协议(§5),只差输入。

## 4. B2 结构(action-conditioned latent 预测,distributional)

```
z_pre(3072)+s → proj → h0(512)
edge_emb = nn.Embedding(5)(数据集实际边词表,见 §7)
h1 = GRUCell(h0, edge_emb)            # action-conditioned latent 转移
Δ̂ 分布:MDN(2 分量高斯混合)over 物理量向量
p(outcome) = softmax(head(h0 ⊕ h1))   # 3 类 + 温度缩放(calibration)
ẑ_post = pred_head(h1)                # 与 DINOv2(z_post) 余弦+MSE 监督
```

- 参数量 < 2M(轻量,匹配数据规模 ~10³ rollouts);
- 不复制 LaDi-WM / 不做像素视频生成(spec §5 明令);
- 不确定性 U = 3-seed 集成熵(K2 复用,spec §10)。

## 5. 损失(§6 冻结式)

L = L_latent + λ_state·L_physical_state + λ_transition·L_verified_transition
+ λ_harm·L_harm

- L_latent = 1 − cos(ẑ_post, z_post) + ‖·‖²(z_post 停梯度);
- L_physical_state = MDN NLL(Δeef_z, Δgrip, Δooi_z);
- L_verified_transition = CE(3 类结局);
- L_harm = CE(HARM 二分类);
- λ 网格 {0.1,0.3,1.0}×{0.3,1.0,3.0}×{0.1,0.5,1.0} 已在 VAL 上跑毕
  (B2 seed 0,27 组,stagek1_lambda_grid.py → stageK1_lambda_grid.csv),
  **冻结值 state=0.1 / transition=3.0 / harm=0.1**(VAL CE 0.3018,无平手),
  对四臂统一使用;温度缩放为可学 log_T,随主损失共同优化,不设单独校验集;
- 禁:final episode success / planner 决策 / 任何 hidden GT 作 runtime 输入。

## 6. 训练协议

- 3 seeds {0,1,2};AdamW lr 1e-4,wd 1e-4;batch 64;≤80 epochs,
  VAL early-stop(patience 10);
- 只用 TRAIN;λ/温度/early-stop 只看 VAL;TEST 只在最终评测触一次;
- checkpoint 记录 git commit / config hash / split hash / encoder 指纹 /
  seed(spec §15)。

## 7. 定稿槽位(已填,冻结)

- K_ROLLOUT = 4(stageK0_decision.md);数据集 312 rollouts;
- 每 split 样本数(TRAIN/VAL/TEST):FG 112/40/40(14/5/5 快照 × 8),
  RPS 60/24/36(5/2/3 快照 × 12);合计 172/64/76;
- edge_id 词表(5):FG-1, FG-3, RS-1, RS-2, RS-3;
- λ 冻结值:state=0.1 / transition=3.0 / harm=0.1(§5);
- 结局分布(全数据集):NO_EFFECT 248 / VERIFIED_RECOVERY 48(全在
  FG-3)/ HARM 16(FG-3 9 + RS-2 7)—— VERIFIED 只由 FG-3 产生,
  §9 门在此分布上评判,不作任何事后调整。
