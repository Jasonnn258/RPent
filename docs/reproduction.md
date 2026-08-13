# RPent 复现指南

从零复现 RPent 的 LIBERO 技能执行（LLM 规划 + Pi0.5 VLA + SAM3 感知）。
核心方法：**租一台 GPU 服务器 → 一键部署 → 运行**。

配套脚本在 [`scripts/deploy/`](../scripts/deploy/)（deploy.sh / download_sam3.py /
run_repro.sh / rental_guide.md），随仓库版本化。

## 1. 硬件与系统要求

| 项 | 要求 |
|----|------|
| GPU | 1× RTX 3090/4090/A5000（≥24GB） |
| 内存 | ≥32GB |
| 磁盘 | ≥80GB SSD（检查点 11GB + conda 环境 ~15GB） |
| 系统 | Ubuntu 20.04/22.04 x86_64 |
| NVIDIA 驱动 | ≥535，`nvidia-smi` 正常 |

> **最重要的预检**：`nvidia-smi` 必须**没有** `Unknown Error`。某张卡硬件故障会
> 污染整机 cuInit（任何新进程 CUDA 都返回 999，`CUDA_VISIBLE_DEVICES` 无法绕过），
> 遇到就换机器/让平台换卡，别在故障机上耗时间。

## 2. 一键部署

```bash
git clone https://github.com/Jasonnn258/RPent.git
cd RPent/scripts/deploy
bash deploy.sh --deepseek-key sk-你的DeepSeekKey
```

deploy.sh 自动完成（幂等，可重跑）：
- 建 `vla` conda 环境（Python 3.11）
- 装 torch 2.7.1+cu126、jax[cuda12]、lerobot 0.3.3、RPent `[full]`
- 下载 LIBERO-PRO 模拟器资产（865 文件）
- 下载 Pi0.5 检查点（跳过 13.5GB 训练用 optimizer.pt）
- 下载 SAM3 检查点（ModelScope 镜像，可续传）
- 打 lerobot 兼容补丁（openpi 旧 API → lerobot 0.3.3 新路径）
- 写 `~/rpent_data/rpent_env.sh`（含 DeepSeek key，0600 权限）
- 验证 CUDA

境外机器下载慢就加：`--hf-endpoint https://huggingface.co`。

## 3. 运行复现

```bash
source ~/rpent_data/rpent_env.sh
bash run_repro.sh --cuda-device 0
```

- 默认任务：`libero_object_swap` task 2（物体交换），seed 0
- `run_repro.sh` 会先列出各 GPU 占用，避免踩到别人在用的卡
- 输出：LLM 生成的命令序列 + episode 视频 + recipe 记录，在 `--output-dir`
  指定的目录（默认运行目录下）

## 4. 已知问题与排查

| 现象 | 说明 / 处理 |
|------|-------------|
| `another tool operation is still active` | DeepSeek 可能一次发多个并行工具调用；toolkit 设计上只允许串行物理操作，后到调用被拒。模型 1-2 轮内自愈为逐个调用，**无需处理**，`--max-turns` 给足即可 |
| lerobot `ModuleNotFoundError` | openpi `data_loader.py` 用旧导入 `lerobot.common.datasets`；deploy.sh 已自动打补丁为 `lerobot.datasets`。若重装 `rlinf-transformer-openpi` 需重打 |
| CUDA 验证失败 | `nvidia-smi` 排查驱动；确认无故障 GPU；torch cu126 需驱动 ≥535 |
| SAM3 下载 403 | facebook/sam3 在 HF 是 gated；download_sam3.py 走 ModelScope 镜像无需鉴权 |

## 5. 本地开发机（无 GPU 时的备选验证）

开发机 CUDA 不可用时，仍可本地验证 LLM 规划器（纯 API，无需 GPU）：
```bash
python - <<'EOF'
# 复用 rpent 的 planner 构建（空 Toolkit，不连 server）
# 参考 scripts/deploy/../tests 或直接跑：
#   source rpent_env.sh && python -c "from rpent.cli.main import ... "
EOF
```
规划器验证通过即说明 DeepSeek 多轮循环 + thinking 块处理正常；
GPU 就绪后按第 3 步直接复现即可。
