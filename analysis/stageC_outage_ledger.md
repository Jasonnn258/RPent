# Stage C3 网络中断事故账(2026-09-18)

## 事件

memC 批(06:17 启动,29 集 + 1 smoke)在 07:15-07:48 期间遭遇出口代理故障:

- **~07:15 起网络劣化**:首批 3 集(t3 s2/s6/s7,06:17-06:24 启动)各跑满
  3600s planner 超时(`infra_timeout`,07:18-07:26 判定)——GLM 调用挂起/极慢。
- **07:26-07:48 硬中断**:代理 CONNECT 隧道无法建立
  (`httpcore2.ConnectTimeout`,traceback 落在
  `httpcore2/_async/http_proxy.py` 的 connect 阶段)。期间所有新启动 episode
  在首个模型请求上死亡(0 turns,elapsed ≈19s);
  5 个在跑 episode 中途被杀(13-32 turns)。
- **07:48 恢复**:无 key POST 探针返回 401(可达),15.7s RTT。

## 误分类机制

episode 侧 rc=0、无 finish → `classify_dir` 判 `policy_fail`;调度器只自动重试
`infra_*`,因此 22 条假 `policy_fail` 被当作最终结果写入 CSV。逐集审计
(2026-09-18 07:50,脚本内联运行):**22/22 全部死于 `ModelAPIError:
Request timed out or interrupted`,0 个真实策略失败。**

| 类别 | 数量 | 明细 |
|---|---|---|
| 首请求被杀(0 turns) | 17 | t5 s7-s10、t9 s1-s10、t3 s2/s6/s7(重试轮) |
| 中途被杀 | 5 | t3 s10(32 turns)、t5 s3(27)、t5 s4(18)、t5 s5(13)、t5 s6(14) |
| 未受影响 | 8 | 7 success + smoke 1 success(t5 s2 于 07:32:31 完成,最后调用赶在中断前) |

## 重试账(纪律:每 key infra 重试 ≤3,不 rerun-until-success)

- t3 s2/s6/s7:attempt 1 = infra_timeout(3600s),attempt 2 = ConnectTimeout 杀
  → 本次重跑为 **attempt 3(上限,再 infra 失败即定型为 infra_timeout 收档)**。
- 其余 19 key:attempt 1 = ConnectTimeout 杀 → 本次重跑为 attempt 2。

## 处置(2026-09-18 07:5x)

1. CSV 备份至 `analysis/outcome_validation_runs.csv.bak-20260918-outage`;
   删除上述 22 行(episode 目录全部保留在 logs/ovpm_exp/ 作证据,不删)。
2. 调度器重启(`--stage memC --tier glm-5.3-flash`,resume-safe,只补 22 格)。
3. 重跑产生的任何结果(含失败)按纪律收档,不再重试 t3 s2/s6/s7。

## 第二波(2026-09-18 08:13-08:21,残余抖动)

08:13 重启后,出口代理在 ~08:21 前仍间歇性失败:最早启动的 6 集
(t3 s2/s6/s7/s10、t5 s3/s4,首个模型请求落在 08:15-08:18)再次死于
同一 `ModelAPIError`(ConnectTimeout);08:22 后启动的 16 集全部正常
流式推进。逐集审计同上(0 turns / 19s / api_err=1 ×6)。

**修订后的尝试账:**

| key | infra 尝试历史 | 状态 |
|---|---|---|
| t3 s2/s6/s7 | ①infra_timeout(06:17 批)②ConnectTimeout(07:3x)③ConnectTimeout(08:15) | **3 次耗尽 → 定型 infra-missing,不再重试,SR/turns 层剔除** |
| t3 s10、t5 s3、t5 s4 | ①ConnectTimeout 中途杀(07:3x)②ConnectTimeout(08:1x) | 剩 1 次,本 pass 结束后单独补跑 |
| 其余 16 key | ①ConnectTimeout(07:3x)②08:13 pass 在跑 | 正常路径 |

处置:6 行再次从 CSV 移除(同备份口径),t3 s2/s6/s7 以 infra-missing
收档(分析中单列,不进 SR 分母),t3 s10/t5 s3/t5 s4 待本 pass 结束后
第三次(最终次)补跑。

## 第二波尾(08:26 / 08:37)

抖动尾巴再杀 2 集(均 `ModelAPIError` 中途杀、无 finish):
t5 s7(6 turns,08:26)= 该 key infra#2;t9 s1(7 turns,08:37)= infra#2。
08:37 后无新失败,存活 episode 请求连续成功(08:49 快照:5 集在 08:25 后
各新增 8-14 turns),判定网络恢复稳定、仅延迟偏高(~3 min/turn,晨间模式)。
两 key 均剩最后 1 次额度,并入 pass 后补跑清单。

## 分析口径提醒

- O2 在线指标只使用重跑后的行;本账附于 stageC 结果报告中。
- 中断前后 GLM 延迟波动属已知晨间模式(2026-09-08 事故同类),wall/turns
  对比时注意 t3 s2/s6/s7 若最终为 infra_timeout,其在线触发指标以事件文件
  为准(memory_events.jsonl 在 episode 被杀前已存在的部分仍然有效,但该集
  无 finish 结果,不计入 SR/turns 层,只作 trigger 层敏感性检查)。
