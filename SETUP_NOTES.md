# RPent Setup Notes (glibc 2.27 host, verified 2026-08-07)

This file records a working install of the **full** RPent stack
(`rlinf` + `openpi` Pi0.5 VLA + LIBERO-PRO + SAM 3.0) on a host running
**Ubuntu 18.04 / glibc 2.27**, plus every pitfall hit and how it was
resolved. It complements the official
[installation docs](docs/source-en/rst_source/installation.rst).

> **Short version for a modern host (glibc >= 2.28):** ignore the override
> hacks below and just `pip install -e ".[full]"`. Everything in this file
> exists because this host cannot install `manylinux_2_28` wheels.

---

## 1. The core problem: torch 2.7.1 needs glibc 2.28

`rlinf-openpi` pins `torch==2.7.1`, but torch **2.7.0+** wheels on PyPI are
`manylinux_2_28` only. On glibc 2.27 they are rejected by pip, and pip falls
back to building from sdist (which fails without a full CUDA toolchain).

**Resolution — override the torch stack to the last glibc-2.17 builds:**

```text
torch==2.6.0            # last manylinux1 build (torch <= 2.6.0 is manylinux1)
torchvision==0.21.0     # matches torch 2.6.0
h5py==3.9.0             # last manylinux2014 build (3.16+ is 2_28-only)
numpydantic<1.8         # 1.8+ requires numpy>=2
numpy>=1.26,<2.0        # libero/openpi both require numpy<2
tqdm>=4.66,<4.68        # sam3 requires <4.68
ray>=2.47.0             # rlinf.models -> scheduler -> ray (runtime required)
```

Verified wheels on this host (glibc 2.27):
`torch 2.6.0` (manylinux1), its `nvidia-*`/`triton` deps (manylinux2014 /
`2_17` / `2_18` / dual `2_27`-tagged), `mujoco 3.8.1` (dual `2_27` tag),
`opencv-python 4.10+` (abi3 `2_17`), `polars` (pure python).

## 2. Install recipe

pip has **no** `--override` flag in 26.x, so the strict `torch==2.7.1` pin
cannot be relaxed at resolution time. Use `--no-deps` for the rlinf packages,
then install the dependency tree explicitly:

```bash
VLA=/hw-tbo/yjx/miniconda3/envs/vla
PIP="$VLA/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/"

# 1) the 5 rlinf/sam3 packages WITHOUT deps
$PIP --no-deps \
  rpent-rlinf==0.3.0 rlinf-openpi==0.1.1 rlinf-libero==0.1.1 \
  rpent-liberopro==0.1.1 sam3==0.1.4

# 2) the runtime dependency tree (see /tmp/rpent_full_runtime.txt for the full
#    pinned list — torch/torchvision/h5py/numpy/numpydantic pinned as above)
$PIP -r /tmp/rpent_full_runtime.txt

# 3) runtime-only extras that the rlinf metadata does not pull transitively
$PIP ray>=2.47.0 psutil beartype==0.19.0 gcsfs tqdm_loggable \
     augmax "numpydantic<1.8" "numpy<2" "tqdm<4.68"
```

Caveat: installing packages individually afterwards **silently bumps numpy
back to 2.2.6** — re-pin `numpy<2` last, and check `pip list | grep numpy`.

## 3. Downloads (weights / assets / tokenizers)

All big artifacts were reachable only through specific mirrors:

| Artifact | Source | Note |
|---|---|---|
| Pi0.5 VLA | `hf-mirror.com` repo `RLinf/RLinf-Pi05-LIBERO-130-fullshot-SFT` | set `HF_HUB_DISABLE_XET=1` (xet CDN `cas-server.xethub.hf.co` unreachable). Inference only needs `model.safetensors` + `metadata.pt` + `physical-intelligence/libero/norm_stats.json`; skip `optimizer.pt` (~13 GB, training-only) with `allow_patterns`. |
| SAM3 | **ModelScope** `https://modelscope.cn/models/facebook/sam3/resolve/master/sam3.pt` | `facebook/sam3` is **gated** on HF. Only `sam3.pt` (3.4 GB) is needed. |
| LIBERO-PRO assets | `git clone https://github.com/RLinf/LIBERO-PRO` → copy `liberopro/liberopro/assets/` (618 MB) into the installed package's `assets/` | hf-mirror 429-rate-limits the 1000-file dataset mid-download; the assets are committed directly in the GitHub repo. |
| paligemma tokenizer | **ModelScope** `google/paligemma-3b-pt-224` `tokenizer.model` → place at `~/.cache/openpi/big_vision/paligemma_tokenizer.model` | openpi hardcodes `gs://big_vision/paligemma_tokenizer.model` (GCS unreachable); the HF paligemma repos are gated, ModelScope is not. |
| SAM3 BPE vocab | `raw.githubusercontent.com/openai/CLIP/main/clip/bpe_simple_vocab_16e6.txt.gz` → place at **`<site-packages>/assets/`** (one level above `sam3/`) | default path is `<pkg>/.. /assets`, not `sam3/assets`. |

Model artifacts land under `/hw-tbo/yjx/checkpoints/`; set:

```bash
export PI05_CHECKPOINT_PATH=/hw-tbo/yjx/checkpoints/RLinf-Pi05-LIBERO-130-fullshot-SFT
export SAM3_CHECKPOINT_PATH=/hw-tbo/yjx/checkpoints/sam3/sam3.pt
```

## 4. Pitfalls and fixes

- **EGL / rendering.** This is a *compute-only* container: `libEGL.so.1`,
  `libEGL_nvidia.so.0`, `libGLX_nvidia.so.0` … are **0-byte stubs** (host bind
  mounts CUDA compute libs only). Installing mesa
  (`libegl1 libegl-mesa0 libgles2 libgl1-mesa-dri`) restores `import robosuite`
  (PyOpenGL finds a real `libEGL.so.1`) but **software EGL/OSMesa rendering is
  all-black**, so the LIBERO camera loop cannot run *in this container*.
  Running the simulator needs a host/container with a full NVIDIA graphics
  stack (nvidia-container-toolkit mounting the GL libs, or a physical host).
  VLA/SAM3 GPU inference is unaffected.
- **missing hidden deps** (not in the rlinf Requires-Dist): `psutil` (sam3),
  `ray` (rlinf scheduler), `beartype`, `tqdm_loggable` (openpi), `gcsfs`
  (openpi download; GCS itself unreachable).
- **numpy drift**: individual `pip install`s re-resolve numpy to 2.2.6, which
  then violates `numpy<2` for libero/openpi. Re-pin afterwards.
- **hf-mirror rate limiting**: large multi-file datasets 429 on per-file
  requests. Prefer GitHub/ModelScope for those (see table above).

## 5. VLA inference verification (this host)

`scripts/vla_inference_check.py` reproduces the exact `vla_server` path
(`predict_action_batch(env_obs, mode="eval")`) with synthetic LIBERO-like
observations (224×224 RGB, 32-dim state, text instruction) and checks:

```
[PASS] env actions shape [B,5,7]        [PASS] batch shape [4,5,7]
[PASS] no NaN/Inf                       [PASS] finite everywhere
[PASS] actions vary with image          [PASS] actions vary with grasp
[PASS] stochastic but stable (same-obs) [PASS] denorm != model_action
[PASS] actions physically plausible
VLA SIDE READY: True
```

Key observations:
- The Pi0.5 model loads on GPU in ~65 s (7.5 GB, `OpenPi0ForRLActionPrediction`).
- `sample_actions` emits `[B, 10, 32]` flow outputs (range ≈ `[-1, +2.6]`);
  `output_transform` denormalizes via the checkpoint quantile stats and slices
  to `[B, 5, 7]` (env action chunk × 7 joint dims).
- Actions are **stochastic** (flow sampling noise) — repeated identical
  observations give different samples by design; this is expected.
- Env actions land within the training `[q01, q99]` envelope ~86% of the time
  and are always within ±4 rad (physically plausible).

## 6. Migration / upload

`scripts/migrate.sh` exports the environment manifests (`manifest`), conda-packs
the env (`pack`), and pushes data to **ModelScope** (`push-ms`, reachable in CN)
or a **GitHub release** (`push-gh`). `huggingface.co` is unreachable from this
host. See the script header for usage.

> License note: check redistribution rights before uploading weights — SAM3 is
> Meta's SAM License, the Pi0.5 checkpoint is RLinf/Physical Intelligence
> (Apache 2.0).
