#!/usr/bin/env python
"""Stage K §4 — 冻结 DINOv2 patch-level encoder 获取(只下载,不训练)。

纪律:在 K0 decision 落盘后才允许运行(K0 阶段零模型下载);
版本 + commit hash 记录进 stageK1_model_spec.md,训练全程冻结。

- 模型:facebook/dinov2-base(ViT-B/14,224 输入 → 16×16=256 patch
  tokens + CLS,dim 768);经由 hf-mirror(HF_ENDPOINT)拉取;
- 缓存:OPENPI_DATA_HOME 同卷(rpent_data/.cache,持久卷纪律);
- 产物:本地快照路径 + torch.load 校验 + 版本指纹打印。

用法:HF_HUB_OFFLINE=0 python scripts/stagek_fetch_dinov2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_ID = "facebook/dinov2-base"
SPEC_OUT = REPO / "analysis/stageK1_encoder_fingerprint.json"


def main() -> int:
    import os
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    # 走持久卷缓存(CLAUDE.md 铁律 3:不写 /root、系统盘)
    hub_cache = Path("/workspace/yjx/rpent_data/.cache/huggingface")
    hub_cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(hub_cache)

    # K0 门禁:decision 未落盘 → 拒绝(预注册 §8 零下载纪律)
    decision = REPO / "analysis/stageK0_decision.md"
    if not decision.exists():
        print("[enc] 拒绝:analysis/stageK0_decision.md 不存在 —— "
              "K0 未收口,零模型下载纪律生效", flush=True)
        return 1

    from huggingface_hub import snapshot_download
    path = snapshot_download(
        MODEL_ID, cache_dir=str(hub_cache / "hub"),
        allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model"],
    )
    import torch
    from transformers import AutoImageProcessor, AutoModel
    proc = AutoImageProcessor.from_pretrained(MODEL_ID)
    enc = AutoModel.from_pretrained(MODEL_ID)
    enc.eval()
    with torch.no_grad():
        x = proc(images=torch.rand(3, 224, 224), return_tensors="pt")
        out = enc(**x)
    n_patch = out.last_hidden_state.shape[1] - 1  # 去 CLS
    fp = {
        "model_id": MODEL_ID, "local_snapshot": str(path),
        "patch_tokens": int(n_patch),
        "hidden_dim": int(out.last_hidden_state.shape[-1]),
        "processor_size": proc.size,
        "probe_output_shape": list(out.last_hidden_state.shape),
    }
    SPEC_OUT.write_text(json.dumps(fp, ensure_ascii=False, indent=1))
    print(json.dumps(fp, ensure_ascii=False, indent=1))
    print(f"-> {SPEC_OUT}(版本指纹并入 stageK1_model_spec.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
