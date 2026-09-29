# Stage I0 决定 — PRIMARY_LOCAL_MODEL

_2026-09-29,依据 `stageI0_prereg.md` §6 预注册门与 `stageI0_results.md` 冻结数字。_

## 决定

**PRIMARY_LOCAL_MODEL = NONE。**

- 门 1(4B):clear_state_accuracy 1.61% < 90% → FAIL
- 门 2(9B):clear_state_accuracy 11.29% < 90% → FAIL
- 门 3:触发 → **I0 FAIL**
- 门 4(35B-A3B 条件测试):条件不满足("9B 接近门而未过"为假;
  11.29% 距门 78.7pp),且同家族解码问题不改规模不解决 → 不启动

## 后果(spec/prereg 联合)

1. **I1 全部不启动**(预注册 §8;spec "only if I0 PASS"):
   §2 本地推理基建(在线部分)、§4 executable graph、§5 authority
   runtime、§6 四臂、§11-19 全部冻结在未启动状态。
2. 已完成且保留:I0 数据集/预注册/结果(负结果保留,spec §19);
   §0 审计;离线基建四件套(start/stop/smoke/runner,双模型验证可用)。
3. **不做**(§19 Hard STOP + prereg §8):不为过门改解码/换模板/
   加 few-shot 后重跑同一基准(= 换实验,须显式重预注册且属用户决策);
   不下载 35B;不重开 GLM API 通道。

## 给后续的归因备忘(若用户决定重开,属新预注册)

- 若改 **think-mode router 契约**(预算 ≥8K tok、~30-60s/decision、
  解析截 `</think>`):需重新冻结合法率/截断率/时延门,并回答
  在线 fire 频率(H1 每臂 30+ 次/30 集)下时延是否可承受。
- 若改 **prompt(内嵌决策规则/家族惯例 few-shot)**:先解决位置混杂
  与"参考=家族常量"的循环 —— 学习式 router 会退化为查表,恰是
  spec §15 Intelligence Gate(learned vs HARD-RULE)要对照的东西;
  菜单字母随机化是必要对照件。
- STATE REPRESENTATION 侧:证据字段本身 think 模式读得懂,不是瓶颈;
  瓶颈在"证据→边"的规则不在 prompt 里。

## 时序证据链

| 步骤 | commit |
|---|---|
| 预注册 + 基准冻结 | 2963343 |
| 服务/冒烟/runner 基建 | 9e1e853, 2c9f2c7 |
| family 映射修复 + think 诊断支持 | 0bf8019 |
| 本决定 + 结果文档 | (本次) |
