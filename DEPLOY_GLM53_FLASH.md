# DEPLOY_GLM53_FLASH.md — 本地 GLM-5.3-Flash Planner 部署

**状态: 已退役(2026-09-15 按用户指示停用:服务 + watchdog 已停,显存清零,/dev/shm JIT 缓存已清;模型权重与脚本保留在盘,重启 = `scripts/start_glm53_flash.sh` + `scripts/health_cron_glm53.sh start`。此前的交付状态:短 prompt 场景可用,episode 级被上游长 prompt bug 阻塞,见 §2.5/§4)** | 更新: 2026-09-15 | 目标: 用本地 GLM-5.3-Flash 替换远端 GLM planner
(实测 episode 97% 墙钟在等远端,账户级并发 ~8-9 是吞吐硬墙),质量对齐、延迟大降、
保留 Pi0.5/SAM3/LIBERO 的 GPU 空间。

## 1. 模型与环境事实

| 项 | 值(已核实) |
|---|---|
| 模型 | `ZhipuAI/GLM-5.3-Flash`(ModelScope;HF 被墙)321B MoE / 18B active / FP8 / 原生多模态 / 1M ctx |
| 架构名 | `Glm5NextForConditionalGeneration`(`config.json`,已下载并核对) |
| 本地路径 | `/workspace/yjx/models/GLM-5.3-Flash`(74 文件 328.4GB,ModelScope 下载,断点续传 = 重跑 `/workspace/yjx/tmp/dl_glm53.sh`) |
| 服务 env | `/workspace/yjx/envs/sglm`(Python 3.10.21) |
| GPU | 8×H100 80GB,driver 535.154.05 / CUDA 12.6(**大坑,见 §2**) |
| serving 框架 | **vLLM nightly cu129**(`0.1.1.dev50+geed1f3d0c.cu129`,09-12 构建;Glm5Next 支持自 PR #53906 / 2026-09-03。wheel 已存 `/workspace/yjx/tmp/wheels/`,旧版 dev580 同目录可回滚;升级原因见 §2.5) |
| 端点 | http://127.0.0.1:8000/v1(OpenAI-compatible;本容器调 loopback 必须 `no_proxy=127.0.0.1,localhost`) |

## 2. 关键坑与事实(排错先看这里)

### 2.1 sglang 不可用 → vLLM cu129 nightly(CUDA 13 vs driver 535)
- sglang ≥0.5.18(stable 0.5.19, 2026-09-04)到 nightly 0.5.20.dev20260909 **全部**
  要求 `torch==2.13.0 + flashinfer[cu13] + cuda-python>=13.0 + humming-kernels[cu13]`;
  PyPI 的 torch 2.13.0 本身就是 cu13 构建(nvidia-cudnn-cu13 等)。
- `docs.sglang.ai/whl/cu129/` 的 "cu129" 是**历史残留名**,内容已切 cu13;
  无 cu126/cu128/cu12 之外的 index(cu126/cu128/cu12/cu121/cu13 路径全 404)。
- 本机 driver 535.154.05(CUDA 12.6)= CUDA 13 内核无法运行(major version 门槛)。
- **且 cu13 切换(≤2026-07-25,0.5.16 起)早于 Glm5Next 支持(09-06,PR #36507)
  → 不存在任何 cu12 的 sglang 能跑这个模型。**
- **选定 vLLM nightly cu129**:`https://wheels.vllm.ai/nightly/cu129/vllm/`(根
  index 里看不见这个子目录但直接访问 200);Glm5Next 支持比 sglang 还早三天
  (09-03,PR #53906);cu129 wheel 依赖是 cu12 系(humming-kernels[cu12]、
  nvidia-cutlass-dsl 默认 flavor、flashinfer 0.6.18 纯 py)。
- **torch 陷阱**:cu129 wheel 的 `torch==2.13.0` 是裸 pin,必须先装
  `torch==2.13.0+cu129 --index-url https://download.pytorch.org/whl/cu129`,
  否则 pip 拉 PyPI cu13 flavor → CUDA init 失败。cp310 守卫:`cuda-tile==1.6.0rc5`
  (rc6 无 cp310)、`cuda-python<13`。
- 官方 docker 标签 `vllm/vllm-openai:glm53-flash-cu129`(issue #54059)存在,
  但本机无 docker 管理权,pip 路线自担。

### 2.2 运行期 JIT 需要 conda 版 CUDA 12.9 nvcc(2026-09-14 boot4-6 实测)
Glm5Next 的 MHC/tilelang 走 vLLM 内置 deep_gemm(vendored 2.6.1,`vllm/third_party/deep_gemm/`),
它在**运行期用 nvcc 现场 JIT 编 sm_90a kernel**。本机三个坑:

| 现象 | 根因 | 修复 |
|---|---|---|
| `NVCC compilation failed`(profile_run 阶段崩) | 生成的 kernel 用 PTX `'q'`(128-bit)内联汇编约束,nvcc **≥12.8** 前端才认识;系统 `/usr/local/cuda` 是 12.6 | conda 装 12.9 nvcc,`CUDA_HOME` 指过去 |
| CUDA 13 nvcc 编过但 `cuModuleLoadData` 报 `INVALID_IMAGE` | ptxas 13 产的 cubin 被 driver 535(CUDA 12.x)拒收 | **只能用 12.9,不能用 13** |
| flashinfer ninja 链接 `cannot find -lcudart` | conda 前缀只有 `lib/` 没有 `lib64/`,torch cpp_extension 找 `$CUDA_HOME/lib64` | 前缀里 `ln -s lib lib64` |
| flashinfer 编译 `cuda_fp16.h` / `cublasLt.h` / `curand_kernel.h` / `nvrtc.h` 逐个消失 | conda cudart-dev 只有 runtime 头;组件头文件要么在 `targets/x86_64-linux/include`(无顶层 `include/`),要么根本没有 |
  见下方 rsync 合并 |

12.9 nvcc 前缀(已装,`/workspace/yjx/envs/cuda129`,约 500MB):
```bash
/workspace/yjx/miniconda3/bin/conda create -y -p /workspace/yjx/envs/cuda129 \
  --override-channels -c nvidia -c conda-forge \
  cuda-nvcc_linux-64=12.9.86 cuda-cudart-dev=12.9.79 cuda-cccl
ln -sfn lib /workspace/yjx/envs/cuda129/lib64   # -lcudart 链接需要
ln -sfn targets/x86_64-linux/include /workspace/yjx/envs/cuda129/include  # 顶层 include/
# 组件头文件(cublas/curand/nvrtc/cudnn/nccl...)从 pip nvidia 12.9 包合并进来(同版本树,--ignore-existing 防覆盖):
for d in /workspace/yjx/envs/sglm/lib/python3.10/site-packages/nvidia/*/include; do
  rsync -a --ignore-existing "$d"/ /workspace/yjx/envs/cuda129/targets/x86_64-linux/include/
done
```
- pip 的 `nvidia-cuda-nvcc-cu12==12.9.86` **只有 ptxas,没有完整 nvcc**,别指望它;
  新命名 `nvidia-cuda-nvcc` 只剩 CUDA 13 版。
- deep_gemm JIT 缓存 = `DG_JIT_CACHE_DIR`(vLLM 自动设到 `$VLLM_CACHE_ROOT/deep_gemm`);
  另有 `DG_JIT_USE_NVRTC=1` 可走 NVRTC 进程内编译(默认 NVCC,未验证 NVRTC 路径)。
- flashinfer JIT 缓存变量名是 **`FLASHINFER_WORKSPACE_BASE`**(0.6.18;`_DIR` 不生效),
  实际落在 `$BASE/.cache/flashinfer/<ver>/<arch>/cached_ops/`。
- 以上缓存全部指向 `/dev/shm/jit_glm53`(tmpfs):**不要指 /workspace** —— yrfs 网络盘上
  并发 JIT 的文件锁失效,TP worker 会竞态崩溃(boot3 实测 FileNotFoundError + 卡死);
  代价是容器重启后重编 ~10min。

### 2.3 reasoning_effort 模板语义(离线验证,2026-09-09)
模板第 2 行:`reasoning_effort if in ['low','high'] else 'max'`。实测渲染:

| reasoning_effort | 渲染 |
|---|---|
| 未设 | **Max** |
| low | Low |
| high | High |
| max / medium / 非法值 | Max |

- assistant generation prompt 固定以 `<think>` 开头(推理默认开)。
- 推论:RPent 默认 `Thinking(high)` 是**主动降档**;本地部署 baseline 应显式 max。
- 工具:`RPENT_REASONING_EFFORT ∈ {low,high,max}` 环境变量(见 §5),非法值/误用于
  远端 anthropic 模型直接 ValueError(fail-fast,不静默)。

### 2.4 网络与代理
- 唯一出口 = `httpproxy.glm.ai:3128`;huggingface.co / hf-mirror.cn 被墙;
  ModelScope / pypi.org / api.github.com 通;GitHub release 大文件必须 `curl --http1.1`。
- pip/uv 走代理会间歇 503(自动重试可恢复);uv 解析 sglang nightly 元数据会僵死,
  用 pip + 精确版本 pin。
- 本容器调 127.0.0.1 服务必须显式 no_proxy(代理会劫持 loopback → 503)。

### 2.5 长生成触发 CUDA illegal memory access(2026-09-14,八崩 → 定位长 prompt prefill + 阈值随配置移动)
**症状**:引擎在特定 workload 下 8 个 TP rank 同时报 `CUDA error: an illegal memory
access` 死亡;浮出点在无关 sync 位置(`positions[:num_rows].cpu()`,MLA metadata
构建),典型"别处写坏、这里炸"异步签名。KV 占用极低、Running=1,与负载/并发无关。

**八连崩矩阵(同日)**:

| # | wheel | 前缀缓存 | CUDA graph | attention 后端 | 触发点 |
|---|---|---|---|---|---|
| 1 | dev580(旧) | ON | ON | flashinfer | 单集 smoke,~37K prompt |
| 2 | dev50(新) | ON | ON | flashinfer | smoke 第 6 次 tool call,in=28831 |
| 3 | dev50 | OFF | ON | flashinfer | smoke 同位置 → **排除 align/前缀缓存路径** |
| 4 | dev50 | OFF | OFF(eager) | flashinfer | smoke 第 9 次 tool call → **排除 graph 回放** |
| 5 | dev50 | OFF | OFF(eager) | flashinfer | **纯文本合成 prompt:8-24K 全过,~28K 一发致死** |
| 6 | dev50 | OFF | OFF(eager) | FA_SPARSE | 合成 28K 仍崩 → **排除 attention 后端选择** |
| 7 | dev50 | ON(全默认) | ON | flashinfer | 同一梯度复现 **16K 即死**(第 2 级) → 前缀缓存开时阈值更低;hit rate 显示 0%,机制待上游判定 |
| 8 | dev50 | OFF | ON | flashinfer | 梯度复现 **24K 死**(16K 过)→ 图捕获也压低阈值;**阈值全景:pc+graph 16K / pc off+graph 24K / pc off+eager 28K 死** |

- 附带教训(单块化尝试全部 boot 失败,不是 IMA 但同样不可用):
  - `--max-num-batched-tokens 65536`:`ValueError: No available memory for the
    cache blocks`(eager 和图捕获两种模式都在 KV 池分配前 OOM,0.75 util 下
    65536-token forward 激活即耗尽预算);
  - `--max-num-batched-tokens 32768`:profile 阶段
    `CUBLAS_STATUS_EXECUTION_FAILED`(cublasGemmStridedBatchedEx)。
- **结论(09-14 深夜)**:长 prompt 会确定性 IMA,且**阈值随配置移动**
  (见 crash 8 行的阈值全景:pc+graph 16K 死 / pc off+graph 24K 死 /
  pc off+eager 28K 死 —— 每关掉一个组件阈值抬高一档,但没有任何配置能过 28K)。
  **交付配置 = `--no-enable-prefix-caching` + 其余默认**:验证过通过区间 ≤16K,
  覆盖功能测试/基准/短调试;episode 级使用(RPent 对话第 5-8 轮即到 25K+)
  被阻塞,等上游修复。issue 草稿:
  `analysis/vllm_glm53flash_ima_issue_draft.md`(外发待用户确认)。

- **最小复现** `scripts/repro_glm53_ima.py`:无图、无 tool-call、无模板特殊结构,
  OpenAI 流式 + 合成英文填充,按 token 梯度探测;~28K 级直接 EngineCore 死。
- 真实会话解剖(transcript json):崩掉请求 = system 37K 字符 + 会话 65K 字符 ≈ 28K
  token 纯文本,**全对话无图片** → 排除视觉路径。基准 300 请求(短 prompt)无恙,
  唯一相关变量 = **长 prompt chunked prefill**(`max_num_batched_tokens=8192`,
  28K = 4 块;24K = 3 块整,过)。
- 上游查证(09-14):#54317(B200 同签名,根因 #50729 mamba 竞态)修复已在树内,
  非我们根因;#55924 kimi_k3 专属、#56037 ROCm/MTP 专属,不对口;#54331 指向
  graph × GDN,但 crash 4(eager)排除纯 graph 回放。
- **已证伪并还原的"缓解"(都只是抬高阈值,没有一个能过 28K)**:`--enforce-eager`
  (阈值 24K→28K)、关前缀缓存(16K→24K,已作为交付配置保留)、换
  `FLASH_ATTN_MLA_SPARSE` 后端(无效)、换 09-12 wheel(修了另一处长生成
  崩溃,但长 prompt 崩溃依旧)。单块化(65536/32768)boot 不起来,见上方教训。
- T6(长生成 16384 out)在 dev50 三连过 → 崩溃与生成长度无关,只与 prefill 长度有关。
  wheel 升级记录:dev580→dev50 消掉了 crash 1 的触发,但 2-5 证明长 prompt 崩溃与
  wheel 版本无关;旧 whl 留 `/workspace/yjx/tmp/wheels/` 可回滚。

**附带观察项(质量,非崩溃)**:#56605 报告 glm47 tool-call parser 在 reasoning→tool
切换时漏 token,长多轮 agentic 会话退化成复读机(BAD build 正是我们原来的 dev580;
day-0 vendor 分支反而干净)。修复 PR #56635(未合并,+182/-2,打在
`vllm/parser/glm47_moe.py`,我们树里该文件存在可打)。**对 RPent planner(27 轮/集
全 tool-call)是真实风险**:单集 smoke 若出现输出污染,先打 #56635 本地补丁再评估。

## 3. 服务生命周期(脚本)


| 脚本 | 作用 |
|---|---|
| `scripts/start_glm53_flash.sh` | 启动(preflight + 模型完整性 + 每卡 ≥68G 空闲检查;setsid + pidfile `/workspace/yjx/run/glm53_flash.pid`;日志 `logs/glm53_flash_server.log`) |
| `scripts/stop_glm53_flash.sh` | 按进程组停(TERM→120s→KILL) |
| `scripts/check_glm53_flash.sh` | pid/端口/`/health`/模型名/显存/日志尾 一览 |
| `scripts/health_cron_glm53.sh` | 健康自愈守护(5min 探活 + 连续 2 轮失败自动重启 + 30min 频率限制 + 日志 200MB 截断守卫)。`start/stop/once` 三态;本容器无 crond,用 setsid 循环实现,容器重启后需手工 `start` |

启动配方(核心段,脚本里有完整版):

```bash
/workspace/yjx/envs/sglm/bin/vllm serve /workspace/yjx/models/GLM-5.3-Flash \
  --tensor-parallel-size 8 \
  --served-model-name zai-org/GLM-5.3-Flash \
  --tool-call-parser glm47 --reasoning-parser glm45 --enable-auto-tool-choice \
  --max-model-len 262144 --max-num-seqs 16 \
  --gpu-memory-utilization 0.75 \
  --no-enable-prefix-caching \
  --host 127.0.0.1 --port 8000
```

- **不传 `--kv-cache-dtype`**(H100 必须 BF16 KV,官方 recipe 明说 Hopper
  不支持该模型的 FP8 KV;FP8 权重原生没问题);
- `--max-model-len 262144`(256K):64K 在真实 episode 不够 —— planner 每轮带
  1 图,turn 11 prompt 已 41K,+ max_tokens 24576 恰好 65537 > 65536 被 400 拒;
  模型上限 1M,KV 池 1.39M tokens,256K 不加显存;
- 0.75 显存预算 ≈60G/卡,给 Pi0.5/SAM3 worker 留 13-15G;
- MTP 投机解码(`--speculative-config '{"method":"mtp","num_speculative_tokens":5}'`)
  第二版再开:先验证质量基线,且投机解码会改并发行为;
- **已知限制**:`--no-enable-prefix-caching` 是唯一保留的缓解旗标(前缀缓存开
  时阈值更低,§2.5 crash 7);长 prompt(≥16-28K,随配置)确定性 CUDA IMA 是上游 bug,
  别再加其他"缓解"旗标 —— eager/换后端/换 wheel/单块化已全部证伪。

### 3.1 首启记录(2026-09-14,new wheel `0.1.1.dev50+geed1f3d0c`,总时长 ~25min)

| 阶段 | 耗时 | 备注 |
|---|---|---|
| 权重装载(yrfs 流式,8 rank 并行) | **~19min**(1118s) | 每卡 38.99 GiB;checkpoint 305.79 GiB |
| 图捕获 + KV 池 + warmup | ~2.3min(139s) | CUDA graph 0.95 GiB;attention block 640 = mamba page +20.75% padding;kpool block 64 |
| **可用 KV** | **16.48 GiB/卡 = 1,391,469 tokens** | 64K/req 下最大并发 21.2×(实际被 --max-num-seqs 16 钳住) |

实测每卡占用 ~61.7/81.5 GiB(与 0.75 预算一致),GPU1 与他人进程(4.5G)共存无冲突。
`/dev/shm` JIT 缓存跨启动保留(同版本),版本升级后部分失效自动重编。

## 4. 功能验证与基准

**功能验证结果(2026-09-14,7/7 PASS,`scripts/test_glm53_flash_local.py`)**:

| # | 项 | 结果 |
|---|---|---|
| T1 | 纯文本 echo | PASS |
| T2 | 视觉(真实 episode RGB→物体+空间关系) | PASS |
| T3 | JSON {phase,action,reason} ×10 | PASS 10/10 |
| T4 | harness 决策(grasped=true 不再抓) | PASS 5/5(见下方测试 bug 说明) |
| T5 | outcome verification(MATCHED/MISMATCHED/UNCERTAIN×COMMIT/OBSERVE/RECOVER) | PASS 3/3 |
| T6 | reasoning_effort low/high/max 端到端 | PASS(延迟单调 10/12/47s;旧 wheel 上此项触发引擎崩溃,换 wheel 后三连稳定) |
| T7 | tool calling(glm47 parser) | PASS(`get_grasp_pose` 参数正确) |

- **T4 曾连续三轮报 3/5、3/5、1/5,查明是测试自己的 bug**:旧判定用子串 `"grasp"`,
  把正确答案 "move the **grasped** red mug toward the plate" 里的 "grasped" 误判成
  重抓。三臂对照实测(/workspace/yjx/tmp/t4_probe.py):本地 temp=1.0、本地 temp=0、
  远端 glm-5.3-flash 同 prompt **全部 5/5 正确选择 transport** —— 本地与远端决策
  质量对齐,T4 修复判定正则后稳定 5/5。
- `scripts/test_glm53_flash_local.py`:Test 1-5 + effort 端到端 + tool calling(7 项,PASS/FAIL)
- `scripts/benchmark_glm53_flash.py`:c=1/2/4/8 × text/vision ×10,TTFT 双口径(首
  reasoning_content / 首 content)、p50/p90、tok/s、常驻 nvidia-smi 采样;远端 A/B 5 次
  → `analysis/glm53_flash_local_benchmark.md`
- 单集冒烟:`scripts/run_local_planner_smoke.sh`(t0 s1;osmesa 三件套 + loopback no_proxy
  + `--max-tokens 24576` 必带)
- **smoke 依赖的环境坑(2026-09-14 实测,容器重建后会复发)**:
  - `libosmesa6` 在系统 overlay 里(apt 装的),容器重建即丢 → 渲染报
    `'NoneType' object has no attribute 'glGetError'`。重装:
    `apt-get update && apt-get install -y --no-install-recommends libosmesa6`
    (deb 备份在 `/workspace/yjx/rpent_data/osmesa_debs/`,可 `dpkg -i` 直装)
  - Pi0.5 的 openpi tokenizer 默认写 `~/.cache/openpi`(overlay,且其 gs:// 下载器
    不走代理会永久卡死):smoke 脚本已设 `OPENPI_DATA_HOME=/workspace/yjx/rpent_data/openpi_cache`,
    `big_vision/paligemma_tokenizer.model` 已预放(curl 直连 storage.googleapis.com 可通)

**单集冒烟结果(2026-09-14,共 4 次尝试,未通过 —— 被上游长 prompt bug 阻塞)**:

- v1(64K 上下文时代):跑到 turn 11、11 次 tool call、planner→tool→VLA 执行
  循环已确认运转,死于 64K 上下文校验(已修:`--max-model-len 262144`);
- v2-v4(256K):每次都在 planner 读文件阶段进行到累计 in≈28.8K(第 6-9 次 tool
  call)时引擎 CUDA IMA 死亡(§2.5 矩阵 crash 2-4;随后的合成梯度复现证明
  触发条件就是 prompt 长度带 24.5K-28K,与 episode 内容无关);
- planner 端行为本身全部正常:pydantic-ai ↔ 本地端点连通、流式、glm47 tool-call
  解析、逐轮图像入会话前的文件读取轮全部工作,延迟量级 = 每请求秒级(远端
  同期约 15-60s);
- **解除阻塞的条件**:上游修复该 IMA(修复后直接重跑
  `scripts/run_local_planner_smoke.sh 0 1`,无需任何本地改动)。

## 5. RPent 接线(零研究逻辑改动)

- planner 切换:`--model openai-chat:zai-org/GLM-5.3-Flash --base-url http://127.0.0.1:8000/v1`
  (pydantic-ai `openai-chat:` 前缀必须;无 key,OpenAIProvider 自动占位)
- **effort 旋钮**(`rpent/planner/api_loop.py::_build_model_settings`,env 门控):
  `RPENT_REASONING_EFFORT ∈ {low,high,max}`;不设 = 原行为(远端 anthropic 路径完全不受影响)。
  单测:`tests/test_reasoning_effort_knob.py`(10 用例,2026-09-09 全过)
- 远端 `glm-5.3-flash` 配置原样保留(A/B 对比用)

## 6. 回滚

服务 stop 即回滚;RPent 侧唯一改动是 api_loop.py 的 env 门控分支(不设 env = 行为
bit 级不变),`git revert` 单 commit 即可。

## 7. 待办 / 未决

- [x] serving 框架定稿:vLLM nightly cu129(09-12 构建 `0.1.1.dev50+geed1f3d0c`;
      sglang 全线 cu13 不可用,见 §2.1)
- [x] 服务启动参数 + 首启记录(§3.1:~25min,KV 1.39M tokens,并发 21×被 max-num-seqs 16 钳住)
- [x] 功能验证 7/7(§4,T6 崩溃已随 wheel 升级解决,T4 为测试 bug 已修)
- [x] 健康自愈(health_cron_glm53.sh 守护,替代无 crond 的环境;容器重启后手工拉起)
- [x] benchmark(c=1/2/4/8 × text/vision ×10)+ 远端 A/B → analysis/glm53_flash_local_benchmark.md
- [x] RPent 接线验证:effort 旋钮(单测 10 用例)+ smoke 中 planner↔本地端点
      连通/流式/tool-call/多轮全部工作
- [ ] **RPent 单集 smoke 未通过** —— 被上游长 prompt CUDA IMA 阻塞(§2.5 六崩
      矩阵 + §4 结果记录),解除条件 = 上游修复;上游 issue 草稿已备
      (analysis/vllm_glm53flash_ima_issue_draft.md),**外发需用户确认**
- [x] git commit + 交付文档(本文件)+ session memory
- [ ] (上游修复后)重跑 repro_ima.py 梯度确认 + 重跑单集 smoke + 摘除文档中
      "已知限制"标记
