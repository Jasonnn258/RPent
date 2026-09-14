# GLM-5.3-Flash 本地 serving 基准

_run 2026-09-14T16:21:47, effort=max, reps=10+1 warmup/配置, model=zai-org/GLM-5.3-Flash_

## 本地(grid)

| config | ok | wall | TTFT-think p50/p90 | TTFT-content p50 | lat p50/p90 | tok/s p50 | out tok mean |
|---|---|---|---|---|---|---|---|
| c=1/text | 10/10 | 56.1s | 0.211/0.239s | 4.021s | 4.86/8.1s | 111.8 | 625.0 |
| c=1/vision | 10/10 | 59.3s | 0.237/0.248s | 4.27s | 5.09/7.51s | 112.2 | 669.0 |
| c=2/text | 20/20 | 105.0s | 0.231/0.256s | 6.546s | 7.68/13.46s | 101.9 | 974.0 |
| c=2/vision | 20/20 | 72.1s | 0.234/0.251s | 5.818s | 6.85/10.28s | 100.5 | 724.0 |
| c=4/text | 40/40 | 156.2s | 0.235/0.267s | 7.046s | 8.03/13.16s | 92.0 | 1138.0 |
| c=4/vision | 40/40 | 85.8s | 0.243/0.262s | 6.874s | 7.92/10.88s | 90.7 | 732.0 |
| c=8/text | 80/80 | 129.4s | 0.238/0.271s | 7.434s | 8.79/15.6s | 73.6 | 814.0 |
| c=8/vision | 80/80 | 113.8s | 0.247/0.421s | 8.452s | 10.04/14.17s | 73.6 | 769.0 |

## 远端 A/B(open.bigmodel.cn,同 prompt,完整流式到 message_stop)

- 首 thinking token p50: 1.36s
- **整轮延迟 p50: 15.48s** (max_tokens=24576,与本地同参数)
- 远端为同账户生产端点,只读测试,配置未动

## GPU(采样期均值)

| gpu | mem peak MiB | util med | util p90 |
|---|---|---|---|
| gpu0 | 62037 | 84 | 90 |
| gpu1 | 62037 | 82 | 90 |
| gpu2 | 62037 | 80 | 90 |
| gpu3 | 62037 | 82 | 90 |
| gpu4 | 62037 | 82 | 90 |
| gpu5 | 62037 | 82 | 90 |
| gpu6 | 62037 | 81 | 89 |
| gpu7 | 62037 | 80 | 88 |

_方法:httpx trust_env=False(绕过容器代理),openai SDK 流式,usage 由 stream_options.include_usage 提供;每配置 1 次 warmup + /flush_cache;并发由 barrier 对齐。_
