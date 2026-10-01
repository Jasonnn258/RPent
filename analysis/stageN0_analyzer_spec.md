# Stage N0 Analyzer v2 操作化规格 — Control-Dependency Measurement

冻结:2026-10-01(与 `stageN_prereg.md` 同 commit)。本文件是 prereg §5 的
操作化组成部分:六判据族、证据通道、事件级判定顺序、段级聚合、输出
schema、开发与冻结流程、抽样分配算法、盲审卷宗渲染规格。实现脚本
`scripts/stageN0_analyze.py` 必须与本文件一致;不一致处一律记入 prereg
偏离记录。

## §1 输入与基建复用(全部只读)

| 复用项 | 来源 |
|---|---|
| 池 inventory(696 行,−24 L_HELDOUT_TEST = 502 集) | `analysis/stageL_pool_inventory.jsonl` |
| fire 行(genuine failure t0)+ replay_fires | `scripts/stageM0_analyze.py` 同码路径 |
| tR = t0 后首个 fire_validated 步(H 冻结契约) | 同上 |
| transcript ↔ steps 两段式区间对齐(498/502) | 同上 |
| 工具/动作分类 | OBSERVE_TOOLS={read_image, view_driver_state};GROUND_TOOLS={back_project, segment};PHYS = {move_to, move_pose, rotate_wrist, set_gripper, pi0_pick, pi0_doubled, release} |

与 Stage M analyzer 的关系:**复用其数据通路(加载/对齐/窗口构造),
完全替换其标注逻辑**(M 的 A–E 判据废弃,不得在 v2 中引用 M 标签)。
M 的 187 段切分与 segment_id **保留沿用**(便于排除旧样本),但 v2 对
每段重新抽取信息事件并给出事件级+段级新标签。

## §2 信息事件本体(information events)

窗口 [t0+1, tR] 内(transcript 消息序)逐个抽取:

| kind | 触发 | usable_fields(决定哪些探测器可用) |
|---|---|---|
| OBSERVE | read_image / view_driver_state 工具调用完成 | tool_result 文本;planner 前后文本 |
| GROUNDING | back_project / segment 调用完成 | world_xyz(强)/ center_xyz,median_xyz(弱)/ 对象名词 / region 描述 |
| VERIFIER | pi0_pick / pi0_doubled / move_to / move_pose / set_gripper 的 result 到达 | success / peak_lift_m / final_dist_m / min_gripper_opening / final_gripper_opening |
| STATE_UPDATE | libero_terminated 置位(仅当 ≤ tR) | 布尔 |

事件 id:`{segment_id}/ev{k}`(按 transcript 序递增)。每个 PHYSICAL_ACTION
同时登记其发射 turn 与参数(action/xyz/prompt/args)。

**VERIFIER 的双重身份**:一个 pi0_pick 既是 PHYSICAL_ACTION 又在其 result
到达时产生 VERIFIER 事件;控制依赖问的是 result 对**其后**控制的因果。

## §3 证据通道(evidence channels;判据只能引用这些)

- **EC1 parameter source link**:动作参数与 grounding 数值的确定性数值匹配
  (§4-B′ 容差)或 planner 文本中显式引用 grounding 坐标值;
- **EC2 grounding update**:t0 后 grounding/segment 的目标对象名词与
  t0 前最近一次不同,或引入 t0 前未出现的新目标名词;
- **EC3 branch condition**:planner assistant 文本(thinking/text,窗口内,
  事件之后、下一 PHYSICAL_ACTION 之前)中的显式条件构造(§4-A′/F′ 正则族);
- **EC4 verifier outcome**:VERIFIER 事件的数值/布尔结果(正/负判定阈值
  同 H 契约:pick 负 = success=False ∨ peak_lift<0.005;move 负 =
  final_dist≥0.05;doubled 正 = success=True);
- **EC5 pre-commitment**:OBSERVE **之前**的 planner 文本已枚举其后实际
  执行的 ≥2 个动作的 family 签名 ∧ 关键参数(xyz 差 ≤0.01 或 prompt 全等);
- **EC6 paired trace**:同 (family, task, pre_sig) 分组内其他轨迹的执行
  对照(仅用于开发期机制分析与 contrast pair,不单独构成 DEPENDENT 证据);
- **EC7 explicit planner statement**:planner 文本中"因 X(信息)故 Y(控制)"
  的显式因果陈述(正则族,归入对应判据)。

**禁止**:仅凭 "OBSERVE 之后有 ACTION" 判 DEPENDENT;引用 reward /
ground-truth 成功 / hidden simulator state / 事后人工归因。

## §4 六判据族(事件级;逐事件评估,任一命中 → 该事件 DEPENDENT)

### A′ observation-gated execution(`observation_gate`)

对 OBSERVE 事件 e,若存在其后首个 PHYSICAL_ACTION(或继续/终止决策)a,
且 e 与 a 之间的 planner 文本命中下列**条件构造正则族之一**,且条件主语
与被观察实体共指、后件引用 a 的执行/继续/参数:

- G1:`(如果|若|一旦|只有|当)[^。]{0,40}(才|则|再|就|继续|执行)`
- G2:`(确认|验证|检查|看到|显示)[^。]{0,30}(后|之后)[^。]{0,20}(再|才|然后|执行|继续|开始)`
- G3:`(否则|不然|如果没有|若非)[^。]{0,30}(换|改|放弃|终止|重试|改抓)`(否定分支存在性)
- G4:`(已|已成功|无误|正常)[^。]{0,15}(无需|不再|可以终止|直接)`(正验证终止门)

共指判定:条件 span(匹配行)内出现被观察对象名词(来自该 OBSERVE 的
tool_result 文本或紧邻提问中的名词,取最长公共名词 ≥2 字符)∧ 后件 span
出现动作动词或"继续/执行/终止"。G3/G4 命中即视为门控存在(无论正负支)。

### B′ target/pose dependency(`pose_update` / `target_grounding`)

对 GROUNDING 事件 g(usable_fields 含数值),若其后 PHYSICAL_ACTION a 满足:

- 数值链接:`dist_xy(a.xyz, g.xyz) ≤ 0.025 ∧ |a.z − g.z| ≤ 0.20`
  (world_xyz 直配;center/median_xyz 命中则记 `weak=True`);或
- 文本数值链接:g 与 a 之间 planner 文本显式引用 g 输出的 ≥2 个坐标数值
  (打印值四舍五入到 3 位小数后字符串匹配),且 a 参数含同值;

且 a 的目标名词与 g 的目标名词一致(或 a 无名词型参数)。
数值链接命中 → `pose_update`;g 导致 a 的目标名词属 t0 前未见新实体 →
`target_grounding`。

### C′ parameter dependency(`parameter_update`)

action family 不变,但 waypoint/offset/grasp pose 来自新 OBSERVE:OBSERVE e
与同族动作对 (a_prev → a) 满足 e 介于两者之间,且 e 与 a 之间 planner 文本
含偏移量表达(`(偏|差|移|offset)[^。]{0,15}?(\d+(\.\d+)?)\s*(cm|mm|米)` 或
`±?\d+(\.\d+)?\s*cm`),且该数值(k_mm 换算)与
`|a.xyz − a_prev.xyz|` 的某分量差 ≤ 0.002,或与 a.xyz 某分量尾数一致
(±0.002)。记录数值链(mm→m 换算轨迹)。

### D′ verification dependency(`verifier_branch` / `retry_fallback` / `termination`)

对 VERIFIER 事件 v(按 EC4 判定正/负),其后(transcript 序)控制变更:

- 负验证 → (同族重试 ∧ 参数/prompt 改变) ∨ 换族 ∨ fallback(目标实体
  改变)→ `retry_fallback`;负验证 → 终止决策(EC3 G4 型文本或无后续
  PHYSICAL_ACTION 而窗口终止)→ `termination`;
- **正验证门控继续**:v 为正 ∧ 其后文本命中 G1/G2/G4 型条件(以验证值
  为条件主语)∧ 后续动作/终止为后件 → `verifier_branch`;
- 仅"负验证后有动作"而无参数变更/换族/fallback/终止 → 不判(证据不足)。

### E′ grounding-reference dependency(`target_grounding`)

t0 后首个针对新目标实体的 GROUNDING/OBSERVE(EC2),其后续 PHYSICAL_ACTION
的 prompt/args 引用该新实体:后续 pick/move prompt 的对象名词 ∉ t0 前
prompt 集 ∧ ∈ t0 后 tool_result/grounding 文本。与 M 的 E 区别:**复用
相同 prompt 不触发 E′;换了 prompt 还必须溯源到 t0 后信息**。

### F′ explicit branch dependency(`retry_fallback` / `termination`)

runtime 条件直接决定下游路径:planner 文本在信息事件后呈现 ≥2 个具名
替代路径并择一(「不可达 → 改抓 X」「X 则 A,否则 B」「已达成 → 终止」型:
`(不可达|无法|够不到|太高|掉落)[^。]{0,30}(改|换|放弃|改抓|转)` /
`已[^。]{0,10}(成功|到位|安全)[^。]{0,15}(终止|结束|不再)`)。

## §5 事件级判定顺序(冻结)

1. 逐事件评估 A′/B′/C′/D′/E′/F′;任一命中 → `DEPENDENT`,
   `dependency_types` = 命中判据的类型列表(按 A′,B′,C′,D′,E′,F′ 序),
   `evidence` = {detector, channel, span/数值链};
2. 无命中 ∧ EC5 命中(pre-commitment)→ `INDEPENDENT`;
3. 其余(有信息事件但无证据)→ `UNRESOLVED`;
4. 段级:任一 DEPENDENT → DEPENDENT;否则任一 UNRESOLVED → UNRESOLVED;
   否则(全 INDEPENDENT 或零信息事件)→ INDEPENDENT。

detector 命中的文本 span(行号+原文)与数值链全部落盘,供审计回放。

## §6 输出 schema

- `analysis/stageN0_information_events.jsonl`:逐段
  `{segment_id, family, task, seed, node, t0, tR, tR_reason, pre_sig,
    events:[{event_id, kind, seq, tool, args_summary, result_summary,
             usable_fields, label, dependency_types, evidence:[…]}],
    phys:[{step, action, xyz, prompt, out}], segment_label,
    n_dependent, n_unresolved, n_independent}`;
- `analysis/stageN0_control_labels.csv`:段级一行(segment_id, task, seed,
  family, node, t0, tR, tR_reason, tR_offset, pre_sig, primitive_count,
  n_information_events, n_observe, n_grounding, n_verifier, n_dependent,
  n_unresolved, n_independent, segment_label, dependency_types,
  fired_detectors, machine_class(=segment_label), unknown_rate)。

## §7 开发流程与冻结(污染控制操作规程)

1. 实现后**先在旧 33 + 3 spot-checked 段上跑**(M 期间已人工看过的材料):
   逐段比对 v2 事件标签与当时人工作答(M 的 OPTION/MACRO 判断 + 分歧
   4 例的已知真相)→ 修 detector(此为允许的失败模式发现);
2. 全池运行只看**聚合计数**;若需逐段阅读非旧样本 → 登记
   `analysis/stageN0_dev_viewed.csv` 并从抽样框排除(目标 ≤10);
3. contrast pair 分析(dossier_21/22/23 型:同配方×有无观察)验证 A′
   方向性:预期 21 → INDEPENDENT(零事件),22/23 → DEPENDENT(A′);
4. v2 代码 commit(**先于抽样**);此后判据改动 = 偏离 = 本轮测量作废;
5. 全部正则族与容差常量写死在脚本顶部(CONSTANTS 区),禁运行时配置。

## §8 抽样分配算法(逐字冻结;实现于 sampler 脚本)

```
输入: eligible = {RESOLVED 165} − {旧33 audit segment_id} − {3 SPOT_CHECKED}
              − {dev_viewed}
每段:family f∈{FG,RPS,MCS},machine_class c∈{DEPENDENT,INDEPENDENT,UNRESOLVED},
     primitive_count p
三分位:以 eligible 全体的 p33/p66(frozen,输出到 manifest 头)分 S/M/L

q_U  = min(8,  |eligible ∩ U|)
q_I  = min(12, |eligible ∩ I|)
q_D  = 45 − q_U − q_I
q_{D,f} = round(q_D·|eligible ∩ D ∩ f| / |eligible ∩ D|);余数给最大族,
          平手按 RPS>FG>MCS
层内:q_{(f,c)} 再按 S/M/L 均分;余数给计数最多的 tercile,平手给 S
抽取:每层按 segment_id 字典序排序,np.random.RandomState(20261002)
     .choice(层成员, size=层配额, replace=False)
空层:配额>层规模 → 取整层,缺口按 RPS>FG>MCS 补给同族 DEPENDENT,
     仍不足补给最大族 DEPENDENT
输出:analysis/stageN0_audit_manifest.csv(audit_id=dossier_%02d 按抽取序)
     + sha256(文件字节)写入 manifest 首行注释,commit 先于人工盲审
```

## §9 盲审卷宗渲染规格(结构盲,沿用 M 生成器骨架)

- 头部:family / task / seed / node / t0 步 / tR 步(+tR_reason **不写**
  ——改写为中性"窗口结束步";tR_reason 泄漏验证语义);
  eef/物体名词仅 t0 与窗口末两帧;
- 正文:窗口内逐步 command+result 原文 + transcript 窗口消息原文
  (thinking 截 400 字 / tool_result 截 800 字,与 M 一致);
- **禁**:v2 任何输出(事件/标签/正则命中)、M 标签、聚合率、tR 之后的
  集结局、memory 卡内容(避免诱导);
- 生成脚本 `scripts/stageN0_audit_dossiers.py`(seed 只用于排序稳定,
  不用于选择)。

## §10 一致性计算与门(实现于 `scripts/stageN0_agreement.py`)

- join key:manifest.segment_id ↔ manual.audit_id ↔ control_labels;
- 人工三态 {DEPENDENT, INDEPENDENT, UNRESOLVED};human-resolved =
  DEPENDENT∪INDEPENDENT;
- overall = #(machine == human) / #human-resolved(仅对 human-resolved 计);
- false_independent = #(H=D ∧ Mach=I)/#(H=D);
- false_dependent = #(H=I ∧ Mach=D)/#(H=I);
- machine_unresolved_rate = #(Mach=U)/45;human_unresolved_rate = #(H=U)/45;
- 3×3 混淆矩阵 + 逐分歧段清单(span/数值链回放)全部落
  `stageN0_measurement_results.md`;
- 门:§11(prereg)——overall ≥90% ∧ false_independent ≤5% ∧
  human-resolved ≥30,三者缺一即 MEASUREMENT NOT QUALIFIED。

## 附录 A — VERIFIER 资格测试与聚合细则(开发期定稿,冻结于 v2 代码 commit)

§2/§5 的事件边界在开发期(旧 33 失败模式发现)细化如下;实现见
`scripts/stageN0_analyze.py`。本附录与 v2 代码同 commit 冻结,此后修改即偏离。

### A.1 t0-uncertainty 资格测试(VERIFIER 正结果)

一个 VERIFIER 事件(动作级验证结果到达)只有当其取值在 t0 未定时有信息资格:

- **负结果**(pick success=False ∨ peak_lift 不足;move final_dist≥0.05)→
  恒具资格(失败在 t0 未定),走 D′(负验证 → 控制变更 + pre-commitment 否决);
- **正结果** → 仅当决策 span 内存在**同句**的
  `动作级验证量断言(RE_VERIFY_ASSERT)∧ 配对条件(RE_VC_A:条件词…验证量 /
  RE_VC_B:验证量…顺序词)` 且执行决定成立(RE_DECIDE 或同消息发射下一动作)
  时才具资格(判 DEPENDENT,记 `verifier_branch`);否则标
  `NONINFORMATIVE`。
- 理由:预期成功的叙述性复读在 t0 已被恢复决策预设,不构成新信息;
  同句配对要求防跨段巧合配对(开发期 dossier_21 型假阳性的根因)。
- 已知风险:会把"预期成功但若失败会反应"的潜在门控压成 NONINFORMATIVE
  ——该方向的漏检由 §3 人工盲审度量,false_independent 门兜底。

### A.2 libero_terminated 不变复读不构成事件

所有 PHYSICAL_ACTION result 都携带 libero_terminated;值与 t0 相同的复读
不是独立信息事件(否则 control-dependency 问题退化为平凡:每个动作结果
都成事件、一切皆 DEPENDENT)。flag 信道由 **STATE_UPDATE(实际翻转)**测量;
窗口内翻 True 且其后无 PHYSICAL_ACTION → `termination`(DEPENDENT)。
RE_VC_A/B 与 RE_VERIFY_ASSERT 的词表刻意排除 terminated/predicate/
still false 族词汇。

### A.3 NONINFORMATIVE 与段级聚合

- NONINFORMATIVE 事件**不参与**段级聚合(既非 DEPENDENT 亦非 UNRESOLVED
  证据);`n_noninformative` 单列落盘供审计;
- 段内全部事件为 NONINFORMATIVE 或窗口零事件 → 段 = INDEPENDENT
  (等价于"零 qualifying information event",§4-prereg 第 3 条)。

### A.4 EC5 适用范围收紧

EC5(pre-commitment → INDEPENDENT)仅对 OBSERVE/GROUNDING 事件可用;
VERIFIER 事件不得用 EC5 判 INDEPENDENT(预印参数不证明结果无关,见 A.1
风险)。必要否决:pre 段有观察目的表达(RE_PURPOSE)或 post 段有观察
内容断言(RE_ASSERT)→ 不得判 INDEPENDENT。

### A.5 盲审卷宗头部契约(事件边界共享)

每份卷宗头部必须写明 qualifying information event 定义:本体 4 类
(OBSERVE / GROUNDING / VERIFIER(仅 pick/doubled/move_to/move_pose/
set_gripper 五族,按 A.1 资格测试)/ STATE_UPDATE(实际翻转))+ A.2
排除(flag 不变复读),并注明 t0 自身结果属 initiation、不计窗口信息。
审计人只对 qualifying 事件回答 §3 反事实问题。不写 v2 标签/聚合。

### A.6 已知未覆盖信道(记 prereg 局限 #6)

PHYSICAL_ACTION result 中的 **eef 位置状态**(尤其 rotate_wrist——无
VERIFIER 事件)被 planner 用于重算下游 waypoint 的信道不在 §2 本体内。
开发期观察到 1 例(`20260907-18:29:08…#f1`:rotate_wrist 后 TCP 落点被
显式用于拆分两跳 traverse;人工判 DEPENDENT、机器 INDEPENDENT)。该段
已 dev-viewed 排除;本信道本轮不测量。机器-I 资格池因开发抽查缩至
约 1 条,false_independent 门的统计功效受此限制(prereg 偏离记录同步
登记)。
