#!/usr/bin/env python
# repro_ima.py — GLM-5.3-Flash 本地 vLLM IMA 最小复现(纯文本,无图)
#
# 背景:4 次引擎死亡都在真实 episode 的长文本 prompt(~28K token,chunked
# prefill 切 4 块)上;基准短 prompt 300 请求无恙。本脚本用合成文本按
# token 梯度探测崩溃阈值,不依赖 RPent。
#
# 用法: python repro_ima.py [起始K] [步进K] [上限K]   (默认 8 4 40)
# 退出码:0 = 全梯度存活;2 = 某级触发 500/断连(引擎大概率已死)

import sys
import time

from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="EMPTY",
                max_retries=0)

# ~4 chars/token 的英文填充词,内容无意义(排除语义因素)
WORD = "robotics grasp trajectory planning evaluation "


def probe(k_tokens: int) -> bool:
    prompt = ("Summarize the following document in one sentence.\n\n"
              + WORD * (k_tokens * 1000 // 6))
    t0 = time.time()
    try:
        s = client.chat.completions.create(
            model="zai-org/GLM-5.3-Flash",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64, temperature=0, stream=True,
        )
        n = 0
        for _ in s:
            n += 1
        print(f"  {k_tokens}K: OK  ({time.time()-t0:.1f}s, {n} chunks)", flush=True)
        return True
    except Exception as e:
        print(f"  {k_tokens}K: FAIL {type(e).__name__}: {str(e)[:120]}", flush=True)
        return False


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    k = start
    while k <= top:
        print(f"[repro] probing ~{k}K tokens ...", flush=True)
        if not probe(k):
            print(f"[repro] TRIGGERED at ~{k}K tokens — engine dead or 500",
                  flush=True)
            sys.exit(2)
        k += step
    print("[repro] all levels survived", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
