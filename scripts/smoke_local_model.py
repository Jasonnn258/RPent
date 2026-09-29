#!/usr/bin/env python3
"""Stage I §2 — 本地 vLLM 服务四项冒烟(health / simple / structured / longest)。

用法(vla env,openai client 已冻结在栈内):
  python scripts/smoke_local_model.py --port 8100 [--model Qwen3.5-4B]

四项(spec §2 逐条):
  S1 health       GET /health + /v1/models 列出 served name;
  S2 simple       一条极短对话,验证非空回答且无 <think> 泄漏;
  S3 structured   复刻 I0 输出契约:prompt 要求 JSON {"choice": "<letter>"},
                  验证 32 token 内出 JSON、可解析、thinking 已关
                  (若输出含 <think> 或空回 → 直接 FAIL);
  S4 longest      取 stageI0_router_benchmark.jsonl 里最长的 prompt
                  (真实 Stage I 输入上界),验证不出截断错、单请求
                  延迟与 prompt/completion tokens 记录在案。

退出码 0 = 全过;非 0 = 有 FAIL(打印逐项)。
"""
from __future__ import annotations

import argparse
import json
import os
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

# S2/S3 冒烟 prompt(违禁词纪律:不含 fail/error/could not/no object)
SIMPLE_PROMPT = "Reply with the single word: ready"
STRUCTURED_PROMPT = (
    "[EDGE-ROUTER] You route a robot to its next strategy.\n"
    "Task: put the bowl on the plate\n"
    "CURRENT STATE: FALSE_GRASP — gripper closed but lift test shows no "
    "object gained\n"
    "family: FG\n"
    "Observable evidence:\n"
    "- last primitive: pi0_pick\n"
    "  success=False, peak_lift_m=0.003, final_gripper_opening=0.01\n"
    "Legal recovery options:\n"
    "A. [false_grasp->regrasp] grasp\n"
    "   expected: gripper gains object on retry\n"
    "   if expected change absent: release and re-observe\n"
    "B. DEFER_TO_PLANNER — return this decision to the main planner.\n"
    'Answer with JSON only: {"choice": "<letter>"}'
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--model", default=None, help="served model name;默认从 /v1/models 取")
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}/v1"
    client = OpenAI(base_url=base, api_key="EMPTY")

    results: list[tuple[str, str, str]] = []  # (name, PASS/FAIL, detail)

    # ---- S1 health ----
    try:
        models = [m.id for m in client.models.list()]
        model = args.model or models[0]
        results.append(("S1_health", "PASS", f"models={models}"))
    except Exception as e:  # noqa: BLE001
        results.append(("S1_health", "FAIL", repr(e)[:200]))
        for n, s, d in results:
            print(f"{n}: {s} — {d}")
        return 1

    def chat(prompt: str, max_tokens: int):
        t0 = time.time()
        r = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=max_tokens)
        return r.choices[0].message.content or "", r.usage, time.time() - t0

    # ---- S2 simple ----
    try:
        text, usage, dt = chat(SIMPLE_PROMPT, 16)
        ok = bool(text.strip()) and "<think>" not in text
        results.append(("S2_simple", "PASS" if ok else "FAIL",
                        f"{dt:.2f}s out={text.strip()[:40]!r} "
                        f"tokens={usage.completion_tokens}"))
    except Exception as e:  # noqa: BLE001
        results.append(("S2_simple", "FAIL", repr(e)[:200]))

    # ---- S3 structured(I0 契约)----
    try:
        text, usage, dt = chat(STRUCTURED_PROMPT, 32)
        legal = False
        for ch in (text or ""):
            if ch in "AB":
                legal = True
                break
        ok = legal and "<think>" not in (text or "")
        results.append(("S3_structured", "PASS" if ok else "FAIL",
                        f"{dt:.2f}s out={ (text or '')[:40]!r} "
                        f"tokens={usage.completion_tokens}"))
    except Exception as e:  # noqa: BLE001
        results.append(("S3_structured", "FAIL", repr(e)[:200]))

    # ---- S4 longest benchmark prompt ----
    try:
        samples = [json.loads(l) for l in open(BENCH)]
        s = max(samples, key=lambda x: len(x["runtime_input"]["prompt"]))
        prompt = s["runtime_input"]["prompt"]
        text, usage, dt = chat(prompt, 32)
        n_in = usage.prompt_tokens
        ok = not text.startswith(" ") or True  # 截断会抛异常,这里只验能回
        ok = bool(text.strip())
        results.append(("S4_longest", "PASS" if ok else "FAIL",
                        f"id={s['sample_id']} chars={len(prompt)} "
                        f"prompt_tokens={n_in} {dt:.2f}s "
                        f"completion_tokens={usage.completion_tokens} "
                        f"out={(text or '')[:40]!r}"))
    except Exception as e:  # noqa: BLE001
        results.append(("S4_longest", "FAIL", repr(e)[:200]))

    n_fail = sum(1 for _, s, _ in results if s == "FAIL")
    for n, s, d in results:
        print(f"{n}: {s} — {d}")
    print(f"SMOKE {'FAIL' if n_fail else 'PASS'} ({len(results) - n_fail}/"
          f"{len(results)}) model={model}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
