#!/usr/bin/env bash
# ============================================================================
# RPent 租服务器一键部署脚本
#
# 在全新 GPU 服务器上：建 conda 环境 → 装依赖 → 下检查点 → 打补丁 → 复现
# 幂等：可重复执行，已完成的步骤自动跳过。
#
# 用法:
#   bash deploy.sh --deepseek-key sk-xxxx [--data-dir ~/rpent_data] \
#                  [--env-name vla] [--repo-dir ~/RPent]
#
# 可选项:
#   --deepseek-key sk-xxxx    DeepSeek API key（必填，也可在提示时输入）
#   --data-dir DIR            检查点/环境文件目录（默认 ~/rpent_data）
#   --env-name NAME           conda 环境名（默认 vla）
#   --repo-dir DIR            RPent 源码目录（默认 ~/RPent，自动 clone）
#   --hf-endpoint URL         HF 镜像（默认 https://hf-mirror.com，直连可改 https://huggingface.co）
#   --skip-checkpoints        跳过检查点下载（仅测试依赖时用）
# ============================================================================
set -euo pipefail

# 脚本所在目录（位置无关，可从仓库任意路径运行）。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEEPSEEK_KEY=""
DATA_DIR="${DATA_DIR:-$HOME/rpent_data}"
ENV_NAME="${ENV_NAME:-vla}"
REPO_DIR="${REPO_DIR:-$HOME/RPent}"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
# 已用该提交验证过复现链路；若想跟踪 fork 最新代码可改为空（用远端默认分支 HEAD）。
PINNED_COMMIT="97ad4ff6e922c9bfa258711b4be558a4cd7f6ecd"
SKIP_CHECKPOINTS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deepseek-key) DEEPSEEK_KEY="$2"; shift 2;;
    --data-dir) DATA_DIR="$2"; shift 2;;
    --env-name) ENV_NAME="$2"; shift 2;;
    --repo-dir) REPO_DIR="$2"; shift 2;;
    --hf-endpoint) HF_ENDPOINT="$2"; shift 2;;
    --skip-checkpoints) SKIP_CHECKPOINTS=1; shift;;
    *) echo "未知参数: $1"; exit 2;;
  esac
done

if [[ -z "$DEEPSEEK_KEY" ]]; then
  read -r -p "DeepSeek API key (sk-...): " DEEPSEEK_KEY
fi
[[ -z "$DEEPSEEK_KEY" ]] && { echo "错误: 缺少 DeepSeek API key（--deepseek-key）"; exit 1; }

step() { echo; echo "=================== $1 ==================="; }

# ---------------------------------------------------------------------------
# 0. 前置检查: NVIDIA 驱动
# ---------------------------------------------------------------------------
step "前置检查"
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "!! 未找到 nvidia-smi。请先安装 NVIDIA 驱动（sudo apt install nvidia-driver-550 或对应版本）并重启。"
  exit 1
fi
if ! nvidia-smi >/dev/null 2>&1; then
  echo "!! nvidia-smi 报错 —— CUDA 驱动不可用。"
  echo "   常见原因: 某张卡硬件故障 / 驱动未加载 / 需要重启。先在本机跑 nvidia-smi 排查。"
  exit 1
fi
echo "NVIDIA 驱动 OK:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null | head -20 || true

# ---------------------------------------------------------------------------
# 1. conda 环境
# ---------------------------------------------------------------------------
step "conda 环境 ($ENV_NAME)"
CONDA_SH=""
for cand in "$HOME/miniconda3/etc/profile.d/conda.sh" \
            "$HOME/anaconda3/etc/profile.d/conda.sh" \
            /opt/conda/etc/profile.d/conda.sh; do
  [[ -f "$cand" ]] && CONDA_SH="$cand" && break
done
if [[ -z "$CONDA_SH" ]]; then
  echo "!! 未找到 conda。先装 Miniconda: https://docs.conda.io/en/latest/miniconda.html"
  exit 1
fi
source "$CONDA_SH"
if conda env list | grep -qE "^\s*$ENV_NAME\s"; then
  echo "env $ENV_NAME 已存在，跳过创建"
else
  conda create -y -n "$ENV_NAME" python=3.11
fi
conda activate "$ENV_NAME"
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "python: $(python --version)   site-packages: $SITE_PACKAGES"

# ---------------------------------------------------------------------------
# 2. Python 依赖
# ---------------------------------------------------------------------------
step "Python 依赖 (torch cu126 + jax + lerobot + rpent)"
pip install -q -U pip
echo ">>> torch 2.7.1+cu126"
pip install -q torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
echo ">>> jax[cuda12]==0.5.3 (openpi 依赖)"
pip install -q "jax[cuda12]==0.5.3"
echo ">>> lerobot==0.3.3 (openpi data_loader 依赖)"
pip install -q lerobot==0.3.3

echo ">>> RPent 源码 ($REPO_DIR)"
if [[ ! -d "$REPO_DIR/.git" ]]; then
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone https://github.com/Jasonnn258/RPent.git "$REPO_DIR"
  if [[ -n "$PINNED_COMMIT" ]]; then
    ( cd "$REPO_DIR" && git checkout "$PINNED_COMMIT" )
    echo "已 clone 并锁定提交 $PINNED_COMMIT"
  fi
else
  echo "$REPO_DIR 已存在，复用（若需锁定提交可手动 checkout）"
fi
echo ">>> pip install -e '$REPO_DIR[full]'  (rlinf+openpi+libero-pro+sam3)"
pip install -q -e "$REPO_DIR[full]"

# ---------------------------------------------------------------------------
# 3. 检查点下载
# ---------------------------------------------------------------------------
if [[ "$SKIP_CHECKPOINTS" == "1" ]]; then
  echo ">>> --skip-checkpoints：跳过检查点下载"
else
  step "LIBERO-PRO 模拟器资产"
  export HF_ENDPOINT="$HF_ENDPOINT"
  python - <<'PYEOF'
from liberopro.liberopro.utils.download_utils import libero_assets_download
try:
    libero_assets_download(check_overwrite=False)
    print("LIBERO-PRO assets OK")
except Exception as e:
    print("LIBERO-PRO assets 下载失败:", e)
    raise SystemExit(1)
PYEOF

  step "Pi0.5 VLA 检查点 (7.5GB, 跳过 optimizer.pt)"
  mkdir -p "$DATA_DIR/checkpoints"
  python - <<PYEOF
from huggingface_hub import snapshot_download
p = snapshot_download(
    "RLinf/RLinf-Pi05-LIBERO-130-fullshot-SFT",
    local_dir="$DATA_DIR/checkpoints/pi05",
    allow_patterns=[
        "model.safetensors",
        "metadata.pt",
        "physical-intelligence/libero/norm_stats.json",
    ],
)
print("Pi0.5 OK at", p)
PYEOF

  step "SAM3 检查点 (3.45GB, ModelScope 可续传)"
  python "$SCRIPT_DIR/download_sam3.py" --target "$DATA_DIR/checkpoints/sam3/sam3.pt"
fi

# ---------------------------------------------------------------------------
# 4. lerobot 兼容补丁 (openpi 用旧 API，lerobot 0.3.3 是新路径)
# ---------------------------------------------------------------------------
step "lerobot 兼容补丁"
DATA_LOADER="$SITE_PACKAGES/openpi/training/data_loader.py"
if grep -q "import lerobot.datasets.lerobot_dataset" "$DATA_LOADER"; then
  echo ">>> 补丁已应用，跳过"
else
  sed -i 's/import lerobot\.common\.datasets\.lerobot_dataset as lerobot_dataset/import lerobot.datasets.lerobot_dataset as lerobot_dataset/' "$DATA_LOADER"
  if grep -q "import lerobot.datasets.lerobot_dataset" "$DATA_LOADER"; then
    echo ">>> 补丁已应用: $DATA_LOADER"
  else
    echo "!! 补丁失败，请手动检查: $DATA_LOADER 第 10 行"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 5. 写入环境变量文件 (含 DeepSeek key, 0600 权限)
# ---------------------------------------------------------------------------
step "环境变量文件"
ENV_FILE="$DATA_DIR/rpent_env.sh"
cat > "$ENV_FILE" <<EOF
#!/usr/bin/env bash
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_KEY"
export ANTHROPIC_API_KEY="$DEEPSEEK_KEY"
export ANTHROPIC_MODEL="deepseek-v4-flash"
export PI05_CHECKPOINT_PATH="$DATA_DIR/checkpoints/pi05"
export SAM3_CHECKPOINT_PATH="$DATA_DIR/checkpoints/sam3/sam3.pt"
export LIBERO_TYPE="pro"
EOF
chmod 600 "$ENV_FILE"
echo ">>> 已写入 $ENV_FILE (含 key，注意权限)"

# ---------------------------------------------------------------------------
# 6. CUDA 验证 + 模型加载验证
# ---------------------------------------------------------------------------
step "CUDA 验证"
python - <<'PYEOF'
import torch
if not torch.cuda.is_available():
    print("!! CUDA 不可用。torch.cuda.is_available()=False")
    print("   排查: nvidia-smi 是否正常? 是否有故障 GPU 阻塞 cuInit?")
    raise SystemExit(1)
print(f"CUDA OK: {torch.cuda.device_count()} devices")
PYEOF

echo
echo "================================================================"
echo " 部署完成 ✅"
echo "================================================================"
echo " 运行复现（默认 GPU 0，可改 --cuda-device）:"
echo
echo "   source $DATA_DIR/rpent_env.sh"
echo "   rpent --env libero --suite libero_object_swap --task 2 \\"
echo "         --seed 0 --cuda-device 0 --planner api \\"
echo "         --model anthropic:deepseek-v4-flash --max-turns 10"
echo
echo " 输出在 ./outputs 或 --output-dir 指定目录。"
echo "================================================================"
