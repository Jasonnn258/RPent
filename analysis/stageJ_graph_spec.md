# Stage J §1 — Executable Graph v1 规格(2026-09-29 冻结)

_载体:`resources/libero/executable_graph_v1.yaml`(12 边,3 失败家族)。
node/state 语义 = Stage H graph_v0 + `rpent/graph/state_interpreter`(不变);
本文件冻结边的选择规则、参数化绑定、executor 链、verifier 公式。_

## 1. 设计约束(全部来自 Stage J spec §1)

- 不重造知识图:v0 的节点判定、guard 词汇、OBSERVABLE_FACT_KEYS 白名单原样复用。
- 只覆盖三个失败家族:FALSE_GRASP(FG)/ MOVE_CONTACT_STALL(MCS,
  MOVE_STALL+CONTACT_STALL 两节点)/ RELEASE_PREDICATE_STALL(RPS)。
- executor 只允许已注册原语(`robots/libero/tools.py`);链内每步的
  参数在 parameterizer 里冻结;**零 LLM**(无 GLM、无本地模型、无
  prompt 生成——唯一的"prompt"来自 runtime 可观测绑定,见 §2)。
- 纯自然语言动作不入图;无法编译的边不进入(实测 12/12 全部可编译,
  无剔除)。
- 同状态多条边 guard 同时满足 → 冻结 priority(§3);仍无法唯一决定
  → DEFER(实际不会发生:每节点 priority 两两不同,且存在无 guard 边)。

## 2. runtime 绑定(parameterizer 的全部自由度)

| 绑定 | 定义 | 来源 |
|---|---|---|
| `TASK_LANG` | 任务语言 | `env.get_task_language()` |
| `LAST_PICK_PROMPT` | snapshot 前 prefix 中**最后一条**带 prompt 的抓取/接触原语(pi0_pick / pi0_doubled)的 prompt 全文;prefix 无 → 回退 `TASK_LANG` | states.json 已发生命令(runtime 可观测,非 GT/未来;J1 双支取同一值) |
| `EEF` | snapshot 时刻 EEF 位置 | obs `robot0_eef_pos` |
| `OBJ_XYZ` | 边内感知步骤(segment→back_project)输出;感知无果 → 该边链中止,记 NO_EFFECT | 边内自产 |
| `OFFSET_SUFFIX` | 冻结常量:`" — grasp at a slightly offset point, about two centimeters to the side of the previous attempt"` | 本文冻结 |
| 数值常量 | waypoint 抬升 +0.06 / 退避 +0.06 / 沉降 −0.02 / 深放 −0.03 / 微移 +0.02y / max_chunks 14(pick)/ 20(doubled)/ 其余原语默认 | 本文冻结(v0 证据与 H1 观测使用值) |

冻结常量取值依据:H1/G0.5 轨迹中 planner 实际使用的 pick max_chunks
中位数(14)、v0 边语义描述的偏移量级(±1-2cm)与 settling 方向(低位)。

## 3. 边选择(确定性,预注册)

```
legal(node) = {e ∈ edges : e.source_state == node ∧ guard_passes(e, facts)}
selected(node) = argmin_{e ∈ legal} e.priority    # priority 无并列
guard_passes: guard 键逐条对照 interpreter facts;事实缺失 → False
DEFER 当且仅当 legal = ∅(每节点均含无 guard 边,预计不触发)
```

**priority 冻结规则**(只允许 J1 之前的信息,防循环):

1. 主序:h1 transition dataset(冻结资产,commit 22aca81)中该边的
   **unique validated hits**(I0 同判据:validated_w5 且 validating_prim
   家族逆映射唯一命中该边),降序;
2. 平分(0=0):非感知边 > 感知边(全家族感知边 validated 均为 0 的
   结构性先验);
3. 仍平:v0 fallback 链序。

| 节点 | priority 序(小者先) | 证据(unique hits) |
|---|---|---|
| FALSE_GRASP | FG-3 → FG-2 → FG-1 | 19 / 0 / 0 |
| MOVE_STALL | MS-2 → MS-3 → MS-1 | 0 / 0 / 0(H1 无 fire,纯结构序) |
| CONTACT_STALL | CS-2 → CS-3 → CS-1 | 2 / 0 / 0 |
| RELEASE_PREDICATE_STALL | RS-2 → RS-3 → RS-1 | 6 / 2 / 0 |

注:该序与 Stage H 的 GLM 菜单选择、I0 基准字母菜单**无关**(J1 不用
字母菜单);与 HIST 支的实际动作(planner 事后行为)无关 —— priority
只由上表冻结证据决定。

## 4. executor 链(逐边)

见 yaml。链式语义:逐步执行,任一步异常 → 边执行 ERROR;感知步无果
→ 链中止记 NO_EFFECT;其余情况链走完后进入 §5 判定。
`pi0_pick` / `pi0_doubled` 是闭环 VLA 技能(prompt 为唯一高层参数),
`move_to` / `set_gripper` / `release` 是解析原语 —— 与线上 planner
可用的原语集合完全一致,无新增能力。

## 5. Transition 结局分类(§5 判据公式,J1 评测用)

每支执行完(或中止)后,在**判定窗口**内分类:
`VERIFIED_RECOVERY / NO_EFFECT / HARMFUL_TRANSITION / DEFER / ERROR`。

**判定窗口** = executor 链完成后的 20 env-step 定持窗口
(`set_gripper(保持当前开度, steps=20)` 实现,期间 `check_success`
随时触发即停)。链内任一时刻谓词触发同样计入。

### 5.1 VERIFIED_RECOVERY(家族独立,全部 runtime-observable + sim 测量)

- **FG**(spec 原文:object leaves support AND object follows EEF):
  - 物体离开支撑:`obj_z(post) − obj_z(snapshot) ≥ +0.01`(物体抬升),且
  - 跟随 EEF:判定窗口内 `corr(Δeef_z, Δobj_z) > 0` 且
    `max(Δobj_z) ≥ 0.01`,或 pick 结果 `peak_lift_m ≥ 0.005` 且
    `final_gripper_opening ≤ 0.06`(握持物证,运行时代理)。
- **RPS**(predicate satisfied):判定窗口内 `check_success() == True`
  (即 `libero_terminated`)。
- **MCS**(target-relative progress 或 contact-resolution):
  `final_dist_m` 相对 snapshot 目标残差下降 ≥ 5mm(`delta ≤ −0.005`,
  v0 verifier 同款),或判定窗口内 `check_success() == True`
  (contact-resolution)。

### 5.2 HARMFUL_TRANSITION(家族统一公式)

满足任一:
- snapshot 时握持(`min_gripper_opening ≤ 0.06` 且其后有抬升证据)→
  post 物体下落 `Δobj_z ≤ −0.02`(脱手坠落);
- 物体水平位移 `‖xy(post) − xy(snapshot)‖ ≥ 0.05` 且未达成
  VERIFIED_RECOVERY(扫飞/撞离)。

### 5.3 其余

- **NO_EFFECT**:链正常走完,VERIFIED 与 HARMFUL 均不满足
  (含感知无果中止、无物理变化的微动)。
- **DEFER**:图选择层返回 DEFER(§3,预计 0)。
- **ERROR**:原语/环境/服务异常(区别于感知空结果:后者是 NO_EFFECT)。

### 5.4 物体位姿测量通道(待 J0 冻结实现,J1 前定案)

`obj_z / xy` 通过 env worker 的 `env_call` 读物体位姿(robosuite
observation 或 sim 派生量;零冻结包修改,J0 §探测)。**该测量只用于
离线结局分类(科学测量仪器),不进入任何 planner/router 可见文本**
(Stage J 无 planner 参与;此边界写死以防未来复用越界)。若 J0 发现
无干净通道 → 回退判据:FG 用 `peak_lift_m` 物证,位移类 HARMFUL 用
EEF 位移 + 谓词联合代理,并在 J1 prereg 声明降级(仍在 J1 之前)。

## 6. 纪律

- 违禁词红线:任何会进入 planner 对话的渲染文本不含违禁子串
  (Stage J 无 planner 参与循环,图文本零注入;字段名
  `failure_family`/`failure_state` 为 Stage J schema 强制命名、
  `consec_pick_fails` 为 v0 冻结事实键 —— 标识符豁免,逐字扫出
  的子串命中仅此三类);
- runtime 数据与 analysis-only 物理分离(J1 产物 schema 沿用 I0 嵌套
  结构);
- J1 全量完成前禁改本图与 priority;INCONCLUSIVE 分支也只允许加
  snapshot,不动图(spec §7);
- fallback / max_attempts 字段为未来在线 runtime 预留,J1 单边
  counterfactual 不触发;
- 图版本:executable_graph_v1,yaml 内 `meta.version`;J1 prereg 引用
  其 sha256。
