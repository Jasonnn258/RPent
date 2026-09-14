#!/usr/bin/env python3
"""benchmark_glm53_flash.py — 本地 GLM-5.3-Flash serving 基准(延迟/吞吐/显存)。

设计(对齐 DEPLOY_GLM53_FLASH.md 的 benchmark 章节):
  - client: openai SDK + httpx.Client(trust_env=False) — 本容器全局代理会劫持
    loopback,必须显式禁用环境代理;retries=0,测的是裸延迟;
  - 流式测 TTFT 两次:首 reasoning_content delta(思考首字)和首 content delta
    (正文首字)——GLM 是 thinking-first 模型,这两个点对 planner 轮延迟的含义不同;
  - 网格: concurrency {1,2,4,8} x {text, vision} x N 次,每配置 1 次 warmup,
    配置之间 POST /flush_cache 排掉 KV 池影响;
  - GPU 采样:常驻 nvidia-smi Popen 子进程(绝不在延迟循环里起子进程),
    事后取每卡 mem 峰值 + util 分布;
  - 远端 A/B:同 prompt 走 open.bigmodel.cn anthropic 端点 raw HTTP 流式,
    key 从 /workspace/yjx/rpent_data/rpent_env.sh 读,绝不打印;
  - 输出: analysis/glm53_flash_local_benchmark.md + 同名 .csv。

用法(sglm/vla 均可,需 openai+httpx):
  python scripts/benchmark_glm53_flash.py [--base-url http://127.0.0.1:8000/v1] \
      [--reps 10] [--concurrency 1,2,4,8] [--skip-remote] [--skip-local]
"""
import argparse
import base64
import csv
import datetime
import os
import statistics
import subprocess
import sys
import threading
import time

ROOT = "/workspace/yjx/workspace/RPent"
OUT_MD = os.path.join(ROOT, "analysis", "glm53_flash_local_benchmark.md")
OUT_CSV = os.path.join(ROOT, "analysis", "glm53_flash_local_benchmark.csv")
DEFAULT_IMG = os.path.join(
    ROOT, "logs/ovpm_exp/20260905-21:11:09_glm-5.3-flash_vanilla_libero_spatial_task_t9_s3_r1/images/image_04.png")
ENV_FILE = "/workspace/yjx/rpent_data/rpent_env.sh"
REMOTE_BASE = "https://open.bigmodel.cn/api/anthropic"
REMOTE_MODEL = "glm-5.3-flash"

# 模拟 planner 决策轮的固定 prompt(有上下文、有图像输入位、要求结构化输出)
TEXT_PROMPT = """You are the task planner of a robot manipulator. Current scene:
a tabletop with a red mug near the table center, a white plate at the right edge,
and a panda-shaped bowl upside down on the left. The robot gripper is open and
positioned above the table. Previous action: move_to(red_mug). Observation:
gripper is 15cm above the red mug, mug handle faces left.

Decide the next action. Reply with JSON: {"phase": str, "action": str,
"reason": str}. Be concise but concrete; mention distances and directions."""


def pct(xs, p):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))
    return xs[i]


class GpuSampler:
    """常驻 nvidia-smi 采样器(1Hz),事后汇总。"""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["nvidia-smi",
             "--query-gpu=timestamp,index,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits", "-l", "1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.samples = []

    def stop(self):
        self.proc.terminate()
        try:
            out, _ = self.proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, _ = self.proc.communicate()
        self.samples = out.strip().splitlines()

    def summary(self):
        per = {}
        for line in self.samples:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            idx, mem, util = parts[1], float(parts[2]), float(parts[3])
            d = per.setdefault(idx, {"mem": [], "util": []})
            d["mem"].append(mem)
            d["util"].append(util)
        lines = []
        for idx in sorted(per):
            d = per[idx]
            lines.append(
                f"| gpu{idx} | {max(d['mem']):.0f} | "
                f"{statistics.median(d['util']):.0f} | {pct(d['util'], 90):.0f} |")
        return lines


def make_client(base_url):
    import httpx
    from openai import OpenAI
    return OpenAI(
        base_url=base_url,
        api_key="EMPTY",
        http_client=httpx.Client(trust_env=False, timeout=600.0),
        max_retries=0)


def one_request(client, model, vision, img_b64, effort):
    """单次流式请求,返回 dict(ttft/content_ttft/latency/tokens)。"""
    content = [{"type": "text", "text": TEXT_PROMPT}]
    if vision:
        content.append({"type": "image_url", "image_url": {
            "url": f"data:image/png;base64,{img_b64}"}})
    t0 = time.perf_counter()
    stream = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": content}],
        stream=True, stream_options={"include_usage": True},
        max_completion_tokens=24576, reasoning_effort=effort)
    ttft_think = ttft_content = None
    usage = {}
    for ev in stream:
        now = time.perf_counter()
        if not ev.choices and not getattr(ev, "usage", None):
            continue
        if getattr(ev, "usage", None):
            usage = {"prompt": ev.usage.prompt_tokens or 0,
                     "completion": ev.usage.completion_tokens or 0}
        if not ev.choices:
            continue
        delta = ev.choices[0].delta
        # vllm 新 parser 引擎流式字段名是 delta.reasoning(旧版 reasoning_content),
        # 两者都抓
        rc = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if rc and ttft_think is None:
            ttft_think = now - t0
        c = getattr(delta, "content", None)
        if c and ttft_content is None:
            ttft_content = now - t0
    return {"ttft_think": ttft_think, "ttft_content": ttft_content,
            "latency": time.perf_counter() - t0,
            "prompt_tokens": usage.get("prompt", 0),
            "completion_tokens": usage.get("completion", 0)}


def run_config(client, model, concurrency, vision, img_b64, reps, effort):
    """一次配置:barrier 同步并发发 reps 轮,返回逐请求结果列表。"""
    results = [None] * (concurrency * reps)
    barrier = threading.Barrier(concurrency)

    def work(wid):
        barrier.wait()
        for r in range(reps):
            results[wid * reps + r] = one_request(
                client, model, vision, img_b64, effort)

    threads = [threading.Thread(target=work, args=(i,))
               for i in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def remote_ab(reps):
    """远端 glm-5.3-flash(anthropic 兼容端点)同 prompt A/B;只读,不改配置。"""
    import httpx
    key = ""
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith("GLM_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        print("WARN: GLM_API_KEY missing, remote A/B skipped")
        return []
    out = []
    for i in range(reps):
        t0 = time.perf_counter()
        ttft = None
        n_events = 0
        try:
            with httpx.Client(trust_env=True, timeout=600.0) as hc:
                with hc.stream(
                    "POST", f"{REMOTE_BASE}/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": REMOTE_MODEL, "max_tokens": 24576,
                          "stream": True,
                          "messages": [{"role": "user",
                                        "content": TEXT_PROMPT}]}) as resp:
                    for line in resp.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        if '"thinking"' in line or '"text"' in line:
                            n_events += 1
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                        # 跑到流自然结束:message_stop 才是整轮延迟
                        if '"type":"message_stop"' in line:
                            break
            out.append({"ttft_think": ttft,
                        "latency": time.perf_counter() - t0,
                        "n_events": n_events})
        except Exception as ex:
            print(f"WARN remote rep {i}: {type(ex).__name__} {ex}")
        time.sleep(1)
    return out


def fmt(v, unit="s", nd=2):
    if v is None:
        return "-"
    try:
        return f"{float(v):.{nd}f}{unit}"
    except (TypeError, ValueError):
        return "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="zai-org/GLM-5.3-Flash")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--concurrency", default="1,2,4,8")
    ap.add_argument("--effort", default="max", choices=["low", "high", "max"])
    ap.add_argument("--image", default=DEFAULT_IMG)
    ap.add_argument("--skip-remote", action="store_true")
    ap.add_argument("--skip-local", action="store_true")
    args = ap.parse_args()

    img_b64 = ""
    if os.path.exists(args.image):
        with open(args.image, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        print(f"vision image: {args.image} ({len(img_b64) // 1024} KiB b64)")
    else:
        print("WARN: no episode image found, vision mode disabled")

    sampler = GpuSampler()
    rows = []
    md = ["# GLM-5.3-Flash 本地 serving 基准",
          f"\n_run {datetime.datetime.now().isoformat(timespec='seconds')}, "
          f"effort={args.effort}, reps={args.reps}+1 warmup/配置, "
          f"model={args.model}_\n"]

    try:
        if not args.skip_local:
            client = make_client(args.base_url)
            modes = ["text"] + (["vision"] if img_b64 else [])
            for conc in [int(c) for c in args.concurrency.split(",")]:
                for mode in modes:
                    vision = mode == "vision"
                    # warmup(不计分)+ 清 KV 前缀缓存(sglang /flush_cache,
                    # vLLM /reset_prefix_cache — 裸 httpx 都试,失败不致命)
                    one_request(client, args.model, vision, img_b64, args.effort)
                    import httpx as _hx
                    base = args.base_url.rstrip("/").removesuffix("/v1")
                    for ep in ("/flush_cache", "/reset_prefix_cache"):
                        try:
                            _hx.post(f"{base}{ep}", trust_env=False, timeout=30)
                        except Exception:
                            pass
                    t0 = time.time()
                    res = run_config(client, args.model, conc, vision,
                                     img_b64, args.reps, args.effort)
                    wall = time.time() - t0
                    ok = [r for r in res if r and r["completion_tokens"]]
                    lats = sorted(r["latency"] for r in ok)
                    tt = [r["ttft_think"] for r in ok if r["ttft_think"]]
                    tc = [r["ttft_content"] for r in ok if r["ttft_content"]]
                    toks = [r["completion_tokens"] / r["latency"] for r in ok]
                    row = {
                        "config": f"c={conc}/{mode}", "n_ok": len(ok),
                        "n_total": len(res),
                        "wall_s": round(wall, 1),
                        "ttft_think_p50": round(statistics.median(tt), 3) if tt else "",
                        "ttft_think_p90": round(pct(tt, 90), 3) if tt else "",
                        "ttft_content_p50": round(statistics.median(tc), 3) if tc else "",
                        "lat_p50": round(statistics.median(lats), 2) if lats else "",
                        "lat_p90": round(pct(lats, 90), 2) if lats else "",
                        "tok_s_p50": round(statistics.median(toks), 1) if toks else "",
                        "out_tokens_mean": round(statistics.mean(
                            [r["completion_tokens"] for r in ok]), 0) if ok else "",
                    }
                    rows.append(row)
                    print(f"{row['config']}: ok={row['n_ok']}/{row['n_total']} "
                          f"lat_p50={row['lat_p50']}s ttft_think_p50={row['ttft_think_p50']}s")
        remote = [] if args.skip_remote else remote_ab(5)
    finally:
        sampler.stop()

    md += ["## 本地(grid)\n",
           "| config | ok | wall | TTFT-think p50/p90 | TTFT-content p50 | "
           "lat p50/p90 | tok/s p50 | out tok mean |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(
            f"| {r['config']} | {r['n_ok']}/{r['n_total']} | {r['wall_s']}s "
            f"| {r['ttft_think_p50']}/{r['ttft_think_p90']}s "
            f"| {r['ttft_content_p50']}s | {r['lat_p50']}/{r['lat_p90']}s "
            f"| {r['tok_s_p50']} | {r['out_tokens_mean']} |")
    if remote:
        rtt = [r["ttft_think"] for r in remote if r.get("ttft_think")]
        rlat = [r["latency"] for r in remote]
        md += ["\n## 远端 A/B(open.bigmodel.cn,同 prompt,完整流式到 message_stop)\n",
               f"- 首 thinking token p50: {fmt(statistics.median(rtt)) if rtt else '-'}",
               f"- **整轮延迟 p50: {fmt(statistics.median(rlat)) if rlat else '-'}**"
               " (max_tokens=24576,与本地同参数)",
               "- 远端为同账户生产端点,只读测试,配置未动"]
    md += ["\n## GPU(采样期均值)\n",
           "| gpu | mem peak MiB | util med | util p90 |", "|---|---|---|---|"]
    md += sampler.summary()
    md += ["\n_方法:httpx trust_env=False(绕过容器代理),openai SDK 流式,"
           "usage 由 stream_options.include_usage 提供;每配置 1 次 warmup +"
           " /flush_cache;并发由 barrier 对齐。_"]

    with open(OUT_MD, "w") as f:
        f.write("\n".join(md) + "\n")
    if rows:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"written: {OUT_MD}")


if __name__ == "__main__":
    main()
