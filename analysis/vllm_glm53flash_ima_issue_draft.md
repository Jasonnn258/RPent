# vLLM upstream issue 草稿(未外发,待确认)

> 用途:GLM-5.3-Flash(Glm5Next)TP8 H100 长前缀确定性 CUDA IMA 的上报草稿。
> 外发前需用户确认(外部发布类操作)。英文版在确认后可直接粘贴 GitHub。

## 标题候选

Glm5Next TP8 H100: deterministic CUDA illegal memory access on long-prompt
prefill (~28K tokens with prefix caching off; ~16K with it on), independent
of CUDA graphs / attention backend / wheel version

## 环境

- vLLM: `0.1.1.dev50+geed1f3d0c.cu129` (nightly, 2026-09-12 build; commit
  eed1f3d0c6043bd494424a22443ee198dd56f657)
- Model: GLM-5.3-Flash (ZhipuAI, 321B MoE / 18B active, FP8, native MM,
  arch `Glm5NextForConditionalGeneration`)
- HW: 8×H100 80GB, driver 535.154.05 (CUDA 12.6), TP=8
- Serve flags:
  `--tensor-parallel-size 8 --tool-call-parser glm47 --reasoning-parser glm45
   --enable-auto-tool-choice --max-model-len 262144 --max-num-seqs 16
   --gpu-memory-utilization 0.75 --no-enable-prefix-caching --enforce-eager
   [--max-num-batched-tokens 65536]`

## 症状

Text-only chat completion with ~28K-token prompt → all 8 TP ranks die with
`CUDA error: an illegal memory access`; surfaces asynchronously at
`positions[:num_rows].cpu()` in MLA attention-metadata build
(`vllm/v1/attention/backends/mla/...`). KV usage minimal, Running=1,
deterministic (5/5 reproductions at the same size).

Token-count ladder (same request otherwise): 8K/12K/16K/20K/24K all pass,
~28K dies. With default `max_num_batched_tokens=8192`, 24K = exactly 3 full
chunks; 28K enters a 4th chunk.

## 已排除(每项单变量 A/B,均仍崩)

1. prefix caching ON vs OFF: OFF **raises** the threshold (shared-prefix
   ladder: dies at 16K with caching ON / everything default; passes to 24K
   and dies at ~28K with `--no-enable-prefix-caching`), but does not fix it
2. CUDA graphs ON vs `--enforce-eager`: graphs ON dies at 24K on the same
   ladder where eager passes 24K and dies at ~28K — each disabled component
   raises the threshold one notch (pc+graphs 16K / pc off+graphs 24K /
   pc off+eager 28K), but no configuration survives past ~28K
3. `VLLM_ATTENTION_BACKEND`: default `FLASHINFER_MLA_SPARSE_SM90` and
   `FLASH_ATTN_MLA_SPARSE` (crashes with both)
4. wheel version: `0.28.1rc1.dev580+g385dce36b` (09-09) and dev50 (09-12)
   (long-prompt crash on both; dev50 additionally fixed a separate
   long-generation crash we saw on dev580)
5. workload content: real agent conversations (tool calls, interleaved
   thinking) and synthetic filler text both trigger at the same size;
   no images involved

## 正在验证

- `--max-num-batched-tokens 32768` (single-chunk prefill for the 28K threshold):
  [结果待填] — 若 28K 通过则指向跨 chunk 状态传递;若仍崩则指向绝对长度。
- 65536 试过不可 boot(两种模式都在 KV 池分配前 OOM):
  `ValueError: No available memory for the cache blocks` — eager 与 CUDA
  graphs 下都一样,0.75 util 时 65536-token forward 的激活内存即耗尽预算。

## 最小复现

```python
# against the running server; ladder 8K→40K
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="EMPTY", max_retries=0)
WORD = "robotics grasp trajectory planning evaluation "
for k in (8, 12, 16, 20, 24, 28, 32, 40):
    prompt = "Summarize the following document in one sentence.\n\n" + WORD * (k * 1000 // 6)
    try:
        s = client.chat.completions.create(model="zai-org/GLM-5.3-Flash",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64, temperature=0, stream=True)
        for _ in s: pass
        print(k, "OK")
    except Exception as e:
        print(k, "FAIL", e); break
```

## 关联 issue(查证过,均非同根因)

- #54317 (B200 same signature; root cause #50729 mamba copy race — fix is
  already in the 09-12 wheel we run)
- #55924 kimi_k3-specific; #56037 ROCm/MTP; #54331 graph×GDN (we crash with
  enforce-eager too)
