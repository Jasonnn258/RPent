# RPent 租服务器配置指南

本指南回答：**租什么配置？拿到机器后先干什么？**

## 1. 租什么

| 项 | 推荐 | 说明 |
|----|------|------|
| GPU | 1× RTX 3090/4090/A5000（24GB） | Pi0.5(3.6B bf16≈7GB) + SAM3 同驻一个卡，24GB 够用 |
| 显存 | 24GB 起步；预算够就 48GB(A6000/A100-40G) | 更从容，不卡换页 |
| 内存 | ≥32GB | LIBERO 仿真 + 数据加载都在 CPU 侧 |
| 磁盘 | ≥80GB SSD | 检查点 11GB + conda 环境 ~15GB + 运行产物 |
| 系统 | Ubuntu 20.04/22.04 x86_64 | 最稳，驱动好装 |
| 驱动 | 预装或能装 NVIDIA 驱动（≥535） | torch 2.7.1+cu126 需要 |

**平台提示**：AutoDL / 恒源云 / 阿里云 PAI 等常见。选"预装 CUDA 驱动"的镜像；
国内节点用默认 hf-mirror，境外节点部署时加 `--hf-endpoint https://huggingface.co`。

## 2. 拿到机器后 5 分钟预检

```bash
# ① 驱动正常？应列出 GPU 且无 "Unknown Error"
nvidia-smi

# ② 磁盘空间够？
df -h /root

# ③ conda 在吗？不在就装（deploy.sh 会自动找，找不到会提示）
command -v conda || echo "需要装 Miniconda"
# Miniconda 安装（若没有）:
#   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
#   bash Miniconda3-latest-Linux-x86_64.sh -b && ~/miniconda3/bin/conda init bash

# ④ 网络：能访问镜像？（可选，测速）
curl -sI https://hf-mirror.com | head -1
```

**⚠️ 最重要：确认没有故障 GPU 污染 CUDA**。`nvidia-smi` 若报
`Unable to determine the device handle for GPUx: Unknown Error`，说明某张卡
故障，会阻塞整机新进程 CUDA（本项目开发机就是这问题）。此时换一台 / 让平台换卡。

## 3. 部署 + 复现

```bash
# 直接从 GitHub clone（部署包已在 scripts/deploy/）
git clone https://github.com/Jasonnn258/RPent.git
cd RPent/scripts/deploy

# 一键部署（10-20 分钟，幂等可重跑）
bash deploy.sh --deepseek-key sk-你的key

# 复现
source ~/rpent_data/rpent_env.sh && bash run_repro.sh --cuda-device 0
```

`run_repro.sh` 会先打印各 GPU 占用，避免踩到别人在用的卡（多卡机器）。

## 4. 常见坑

| 现象 | 原因/处理 |
|------|-----------|
| `nvidia-smi` 报某卡 Unknown Error | 该卡故障污染 cuInit，换台机器或让平台处理 |
| `deploy.sh` 找不到 conda | 先装 Miniconda（上面②） |
| 下载很慢 | 境外机器加 `--hf-endpoint https://huggingface.co`；境内保持 hf-mirror |
| 部署完 CUDA 验证失败 | `nvidia-smi` 排查驱动；torch cu126 需要驱动 ≥535 |
| 运行时 `another tool operation is still active` | 已知行为，模型 1-2 轮自愈，无需处理 |
| OOM（显存不足） | 关掉其他进程；或换 48GB 卡 |
