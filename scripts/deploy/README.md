# RPent 租服务器一键部署包

在全新 GPU 服务器上完成 RPent 复现所需的一切。租到机器后 10–20 分钟出结果。

> **租什么配置、拿到机器先验什么 → 看 `rental_guide.md`**

本目录内容已随仓库版本化。在租的服务器上直接 clone 仓库即可使用：

```bash
git clone https://github.com/Jasonnn258/RPent.git
cd RPent/scripts/deploy
bash deploy.sh --deepseek-key sk-你的key   # 一键部署
source ~/rpent_data/rpent_env.sh
bash run_repro.sh --cuda-device 0          # 复现
```

## deploy.sh 做了什么

| 步骤 | 说明 |
|------|------|
| 前置检查 | 确认 `nvidia-smi` 可用（驱动正常，无故障 GPU 阻塞） |
| conda 环境 | 创建 `vla`（Python 3.11） |
| 依赖 | torch 2.7.1+cu126 → jax[cuda12] 0.5.3 → lerobot 0.3.3 → RPent `[full]`（rlinf+openpi+libero-pro+sam3） |
| LIBERO-PRO 资产 | 从 `RLinf/LIBERO-PRO-assets` 下载 865 文件（默认 hf-mirror 镜像） |
| Pi0.5 检查点 | `RLinf/RLinf-Pi05-LIBERO-130-fullshot-SFT`，只下 model.safetensors+metadata+norm_stats（跳过 13.5GB 训练用 optimizer.pt） |
| SAM3 | ModelScope 镜像，可续传，校验字节数 3,450,062,241 |
| lerobot 补丁 | openpi 用的旧 API `lerobot.common.datasets...` 在 0.3.3 已改名 → 改为新路径 |
| 环境文件 | `rpent_env.sh`（DeepSeek key + 检查点路径 + LIBERO_TYPE=pro） |
| CUDA 验证 | 确认 torch 能看到 GPU |

幂等：重复执行会跳过已完成步骤。

## 关键细节

- **锁定提交**：deploy.sh 默认 `PINNED_COMMIT=97ad4ff`（已验证的复现版本）；
  想跟踪 fork 最新代码可置空该变量。
- **HF 镜像**：默认 `https://hf-mirror.com`；境外机器加
  `--hf-endpoint https://huggingface.co`。
- **检查点路径**：默认 `~/rpent_data/checkpoints/`，可 `--data-dir` 修改。
- **GPU 选择**：`--cuda-device N`。先 `nvidia-smi` 看空闲卡。

## 已知行为（无需处理）

- **DeepSeek 可能一次发多个并行工具调用**。RPent 的 toolkit 设计上只允许
  串行物理操作（技能不能同时跑），后到的调用会返回
  `"another tool operation is still active"`。模型看到后 1–2 轮内会自愈为
  逐个调用，不影响最终成功，只是多耗几轮 token。`--max-turns` 给足即可。

## 如果 CUDA 验证失败

```bash
nvidia-smi            # 驱动是否正常、有无报错
ls /dev/nvidia*       # 设备节点
dmesg | grep -i nvidia
```
常见情形：**某张卡硬件故障会污染整机 cuInit**（任何新进程 CUDA 都返回 999，
`CUDA_VISIBLE_DEVICES` 无法绕过）。此时需管理员把故障卡从总线摘掉：
```bash
sudo sh -c 'echo 1 > /sys/bus/pci/devices/0000:XX:00.0/remove'
```
（`XX` 用 `nvidia-smi` 里报 `Unknown Error` 那张卡的总线号替换）
或重启 / 换一台机器。
