#!/usr/bin/env python3
"""Stage I0 — router 资格基准运行器(prereg §4 解码/解析、§5 指标,冻结)。

对 analysis/stageI0_router_benchmark.jsonl(252 样本,sha256 9b153e22)逐条
单请求调本地 vLLM(batch=1 串行,latency 口径 = prereg §7):

  temperature 0,max_tokens 32,无 few-shot,prompt = runtime_input.prompt
  解析:第一个 {...} JSON 块的 choice 字段 → 回退首个 A-Z 字母 → ILLEGAL
  合法:字母 ∈ 菜单(合法边原序)或 = DEFER 位

产物:
  analysis/stageI0_run_<tag>.jsonl     逐样本原始记录(raw 截 64 字符)
  analysis/stageI0_metrics_<tag>.json  指标(overall + 三家族)
tag = qwen4b / qwen9b(本脚本 --tag 指定)。

用法(vla env,服务已就绪):
  python scripts/run_stageI0_benchmark.py --port 8100 --tag qwen4b
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# 本机 http_proxy 会劫持 127.0.0.1 请求(openai→httpx 读 proxy env);
# 本地服务必须直连,先改 env 再 import OpenAI
for _v in ("NO_PROXY", "no_proxy"):
    _cur = os.environ.get(_v, "")
    if "127.0.0.1" not in _cur:
        os.environ[_v] = (_cur + "," if _cur else "") + "127.0.0.1,localhost"

from openai import OpenAI  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "analysis/stageI0_router_benchmark.jsonl"
JSON_RE = re.compile(r"\{[^{}]*\}")
LETTER_RE = re.compile(r"[A-Z]")

# 三失败家族长名 → 预注册短码(prereg §2: CLEAR FG 44 / MCS 6 / RPS 12)
FAMILY_CODE = {"FALSE_GRASP": "FG", "MOVE_CONTACT_STALL": "MCS",
               "RELEASE_PREDICATE_STALL": "RPS"}


def parse_choice(text: str, think: bool = False):
    """prereg §4 冻结解析:首个 JSON 块 choice → 首个 A-Z → None。

    think=True(诊断模式,不进资格门):截掉 </think> 前的推理段再解析,
    防止 think 内容里的字母/JSON 污染 choice。"""
    if think and "</think>" in (text or ""):
        text = text.split("</think>")[-1]
    m = JSON_RE.search(text or "")
    if m:
        try:
            c = json.loads(m.group(0)).get("choice")
            if isinstance(c, str) and c:
                mm = LETTER_RE.search(c)
                if mm:
                    return mm.group(0), "json"
        except Exception:  # noqa: BLE001
            pass
    mm = LETTER_RE.search(text or "")
    return (mm.group(0), "letter") if mm else (None, "none")


def gpu_mem_mb(gpu: int) -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits", "-i", str(gpu)],
            capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return -1


def pct(x, y):
    return round(100.0 * x / y, 2) if y else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--tag", required=True, help="qwen4b / qwen9b")
    ap.add_argument("--gpu", type=int, default=7, help="显存采样用")
    ap.add_argument("--max-tokens", type=int, default=32,
                    help="冻结口径 32;--think 诊断时建议 512")
    ap.add_argument("--think", action="store_true",
                    help="诊断模式:服务端 thinking 开启时,截 </think> 后解析;"
                         "结果只作归因,不进资格门")
    args = ap.parse_args()

    samples = [json.loads(l) for l in open(BENCH)]
    bench_sha = hashlib.sha256(open(BENCH, "rb").read()).hexdigest()[:8]
    assert bench_sha == "9b153e22", f"基准被改动: sha {bench_sha}"

    client = OpenAI(base_url=f"http://127.0.0.1:{args.port}/v1",
                    api_key="EMPTY")
    model = client.models.list().data[0].id
    print(f"running {len(samples)} samples vs {model} (tag={args.tag})")

    run_path = REPO / f"analysis/stageI0_run_{args.tag}.jsonl"
    records = []
    t_start = time.time()
    mem_peak = gpu_mem_mb(args.gpu)
    with open(run_path, "w") as f:
        for i, s in enumerate(samples):
            ri = s["runtime_input"]
            t0 = time.time()
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": ri["prompt"]}],
                    temperature=0.0, max_tokens=args.max_tokens)
                text = r.choices[0].message.content or ""
                usage = r.usage
                err = None
            except Exception as e:  # noqa: BLE001
                text, usage, err = "", None, repr(e)[:200]
            dt = time.time() - t0
            letter, how = parse_choice(text, think=args.think)
            n_edges = len(ri["legal_edges"])
            legal_letters = {chr(65 + k) for k in range(n_edges)}
            legal_letters.add(ri["defer_letter"])
            is_defer = letter == ri["defer_letter"]
            rec = {
                "sample_id": s["sample_id"], "cls": s["cls"],
                "family": FAMILY_CODE.get(s["failure_family"],
                                          s["failure_family"]),
                "n_options": n_edges + 1,
                "reference_letter": s["reference_letter"],
                "letter": letter, "parse_how": how,
                "legal": letter in legal_letters if letter else False,
                "is_defer": is_defer, "raw64": (text or "")[:64],
                "tail64": (text or "")[-64:],
                "latency_s": round(dt, 4),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "api_error": err,
            }
            records.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(samples)} "
                      f"({time.time() - t_start:.0f}s)")
                mem_peak = max(mem_peak, gpu_mem_mb(args.gpu))
    wall = time.time() - t_start
    mem_peak = max(mem_peak, gpu_mem_mb(args.gpu))

    # ---- 指标(prereg §5)----
    n = len(records)
    legal_n = sum(r["legal"] for r in records)
    clear = [r for r in records if r["cls"] == "CLEAR"]
    clear_hit = sum(r["legal"] and r["letter"] == r["reference_letter"]
                    for r in clear)
    amb = [r for r in records if r["cls"] == "AMBIGUOUS"]
    fam_acc = {}
    for fam in ("FG", "MCS", "RPS"):
        fr = [r for r in clear if r["family"] == fam]
        fam_acc[fam] = {
            "n": len(fr),
            "acc": pct(sum(r["legal"] and r["letter"] == r["reference_letter"]
                           for r in fr), len(fr))}
    lats = sorted(r["latency_s"] for r in records)
    toks = [r["completion_tokens"] for r in records
            if r["completion_tokens"] is not None]
    api_err_n = sum(bool(r["api_error"]) for r in records)
    metrics = {
        "tag": args.tag, "model": model, "n_samples": n,
        "bench_sha8": bench_sha,
        "legal_choice_rate": pct(legal_n, n),
        "clear_state_accuracy": pct(clear_hit, len(clear)),
        "clear_n": len(clear),
        "family_accuracy": fam_acc,
        "defer_rate": pct(sum(r["is_defer"] for r in records), n),
        "defer_on_ambiguous_rate": pct(
            sum(r["is_defer"] for r in amb), len(amb)),
        "illegal_output_rate": pct(
            sum((not r["legal"]) and (not r["api_error"]) for r in records), n),
        "api_error_rate": pct(api_err_n, n),
        "latency_p50_s": round(lats[n // 2], 4),
        "latency_p95_s": round(lats[int(n * 0.95)], 4),
        "mean_completion_tokens": round(sum(toks) / len(toks), 2) if toks else None,
        "wall_s": round(wall, 1),
        "throughput_qps": round(n / wall, 4),
        "gpu_mem_peak_mb": mem_peak,
    }
    out = REPO / f"analysis/stageI0_metrics_{args.tag}.json"
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\nwrote {out} and {run_path}")
    if api_err_n:
        print(f"WARNING: {api_err_n} api errors — 视为非法输出前先查服务日志")
    return 0


if __name__ == "__main__":
    sys.exit(main())
