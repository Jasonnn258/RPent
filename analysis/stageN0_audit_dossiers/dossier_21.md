# N0 盲审卷宗:dossier_21(control-dependency audit)
- 失败族:RELEASE_PREDICATE_STALL(node RELEASE_PREDICATE_STALL)
- t0(窗口起始步)= step 8;tR(窗口结束步)= step 13
- task 9 / seed 3 / 长度层 L
- t0 eef ['0.055', '0.190', '1.026'] grip [0.039454851536222156, -0.03978007754408507]
- tR eef ['0.024', '0.240', '0.934'] grip [0.014290245580580008, -0.015377612708965227]
- t0 物体 ['akita_black_bowl_1', 'akita_black_bowl_2', 'cookies_1', 'glazed_rim_porcelain_ramekin_1', 'plate_1']

## 事件边界契约(审计与测量共享的定义;只对 qualifying 事件作答)

窗口 = (t0, tR],即 t0 结果到达之后、tR 发射为止。**qualifying information
event** 限以下四类:

1. **OBSERVE**:read_image / view_driver_state 的结果到达;
2. **GROUNDING**:back_project / segment 的结果到达;
3. **VERIFIER**:pi0_pick / pi0_doubled / move_to / move_pose / set_gripper
   的 result 到达(t0 与 tR 自身的 result 是窗口边界,不计入);
4. **STATE_UPDATE**:libero_terminated 实际翻转(True↔False)。

排除(不构成新信息):
- 每个动作 result 都携带的 libero_terminated **取值与 t0 相同的复读**
  (否则任何动作结果都是事件,问题退化为平凡);
- VERIFIER **正结果**(动作如预期成功)若 planner 仅叙述数值、全文无任何
  条件反应,视为预期内复读;**负结果**(失败/未达)恒为新信息;
- t0 自身 result 属 initiation(恢复被触发的依据),不是窗口内新信息。

反事实问题(对每个 qualifying event e):
> If the newly acquired observation at e had been **different but still
> physically plausible**, would the downstream recovery control (action,
> parameter, continuation, retry, fallback, or termination) have changed?

## 窗口内命令与结果(states.json 原文,step t0 至 tR)

### step 8
```json
{
 "action": "release",
 "max_steps": 40
}
```
```json
{
 "name": "release",
 "steps_used": 40,
 "start_gripper_opening": 0.0044,
 "peak_gripper_opening": 0.0792,
 "final_gripper_opening": 0.0792,
 "libero_terminated": false
}
```
### step 9
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 60,
 "step_clip": 0.012,
 "xyz": [
  0.055,
  0.19,
  1.1
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.054999999701976776,
  0.1899999976158142,
  1.100000023841858
 ],
 "final_eef_pos": [
  0.0545,
  0.19,
  1.0886
 ],
 "final_dist_m": 0.0114,
 "steps_used": 22,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 10
```json
{
 "action": "pi0_doubled",
 "max_chunks": 20,
 "prompt": "place the bowl on the plate"
}
```
```json
{
 "name": "pi0_doubled",
 "instruction": "place the bowl on the plate",
 "success": false,
 "task_success": false,
 "contact_skill_executed": true,
 "chunks_used": 20,
 "max_chunks": 20,
 "libero_terminated": false,
 "diagnostics": {
  "mode": "contact_skill_success_by_libero_terminated",
  "success_meaning": "`success` mirrors official LIBERO task termination only; for intermediate contact skills, inspect image/state evidence."
 }
}
```
### step 11
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 60,
 "step_clip": 0.012,
 "xyz": [
  0.1,
  0.05,
  1.1
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.10000000149011612,
  0.05000000074505806,
  1.100000023841858
 ],
 "final_eef_pos": [
  0.1001,
  0.0618,
  1.1001
 ],
 "final_dist_m": 0.0118,
 "steps_used": 55,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 12
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 80,
 "step_clip": 0.012,
 "xyz": [
  0.066,
  0.208,
  1.07
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.06599999964237213,
  0.20800000429153442,
  1.0700000524520874
 ],
 "final_eef_pos": [
  0.0657,
  0.1963,
  1.0696
 ],
 "final_dist_m": 0.0117,
 "steps_used": 49,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 13
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.04,
 "max_chunks": 12,
 "prompt": "pick up the bowl on the plate"
}
```
```json
{
 "name": "pick",
 "instruction": "pick up the bowl on the plate",
 "success": true,
 "chunks_used": 12,
 "max_chunks": 12,
 "peak_lift_m": 0.022284328937530518,
 "min_gripper_opening": 0.004859196022152901,
 "final_gripper_opening": 0.02966785803437233,
 "libero_terminated": true,
 "diagnostics": {
  "start_eef_z": 1.0696,
  "peak_eef_z": 1.0696,
  "min_eef_z": 0.9339,
  "post_min_peak_z": 0.9562,
  "descent_m": 0.1357,
  "post_min_ascent_m": 0.0223,
  "descent_done": true,
  "lift_thresh": 0.04,
  "gripper_closed_thresh": 0.06
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg60 assistant 思考] The agentview shows the gripper holding the bowl directly over the plate. The bowl is tilted and its lower edge is touching/nearly touching the plate — the bowl's rim-bottom edge is right at the plate's surface (the bowl overlaps the plate's upper-right quadrant; the plate's red rings visible below-left of the bowl). The bowl looks like it's resting its base edge on the plate.

The bowl base conta
- [msg60 assistant 文本] The bowl is held directly over the plate, its base edge seated at the plate surface (red rings visible around it). Per the memory: my placement is already centered (~1.2cm), so I skip extra corrections that risk unseating it and go straight to **release with a long settle**:
- [msg60 assistant 调用 release] ```json
{"max_steps": 40}
```
- [msg61 tool 结果] {
  "step": 8,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.05497773340169566,
      0.18962680599253928,
      1.0256196258235453
    ],
    "robot0_eef_quat": [
      0.7009533433880506,
      0.7066598896863052,
      0.011723366042277993,
      0.0957014806065721
    ],
    "robot0_gripper_qpos": [
      0.039454851536222156,
      -0.03978007754408507
    ],
    "object_names": [
      "akita_black_bowl_1",
      "akita_black_bowl_2",
      "cookies_1",
      "glazed_rim_porcelain_ramekin_1",
      "plate_1"
    ]
  },
  "libero_terminated": false,
  "episode_truncated": false,
  "world_map": "world/world_08.npy",
  "wrist_world_map": "world_wrist/world_wrist_08.npy",
  "world_map_hi": "world_hi/wor
- [msg63 assistant 思考] The release opened the gripper (peak opening 0.079) but libero_terminated is still FALSE. The rule R5 suggests using pi0_doubled for the final placement.

Wait — first, let me check the current state: did the bowl land on the plate? The gripper opened fully (0.0792) and the eef stayed at [0.055, 0.190, 1.026]. Per global memory "predicate-gated by eef proximity — retreat clear" and "predicate fire
- [msg63 assistant 文本] Release executed (gripper fully opened, 0.079), but `libero_terminated` is still false. Before applying any recovery, let me look at the actual scene state — is the bowl seated on the plate, or did something go wrong?
- [msg63 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-17:42:51_glm-5.3-flash_h1P2_libero_spatial_task_t9_s3_r1/images_cam_hi/image_cam_hi_08.png"}
```
- [msg64 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-17:42:51_glm-5.3-flash_h1P2_libero_spatial_task_t9_s3_r1/images_cam_hi/image_cam_hi_08.png
- [msg65 assistant 思考] Excellent! The bowl is now sitting ON THE PLATE — clearly seated, upright, with the plate's red rings visible around it. The gripper has opened and is retreating upward (still slightly above the bowl).

The bowl looks properly placed on the plate. But libero_terminated is still false. Per global memories:
- "predicate-gated by eef proximity — retreat clear": after a geometrically-correct place, th
- [msg65 assistant 文本] The bowl is **seated upright on the plate** — red rings visible around its base, gripper open above. The predicate is likely gated on EEF proximity (per memory: predicate fires after gripper retreat). Retreating straight up, avoiding the ramekin behind:
- [msg65 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.012, "xyz": [0.055, 0.19, 1.1]}
```
- [msg66 tool 结果] {
  "step": 9,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.054496106270876164,
      0.19000155910631913,
      1.0886151163961697
    ],
    "robot0_eef_quat": [
      0.701203711907351,
      0.7062912030451428,
      0.012599285534980124,
      0.09647460242159214
    ],
    "robot0_gripper_qpos": [
      0.03968366118280708,
      -0.040004601756630356
    ],
    "object_names": [
      "akita_black_bowl_1",
      "akita_black_bowl_2",
      "cookies_1",
      "glazed_rim_porcelain_ramekin_1",
      "plate_1"
    ]
  },
  "libero_terminated": false,
  "episode_truncated": false,
  "world_map": "world/world_09.npy",
  "wrist_world_map": "world_wrist/world_wrist_09.npy",
  "world_map_hi": "world_hi/wo
- [msg67 assistant 思考] Retreated to z=1.089, eef clear of the bowl. Still libero_terminated: false.

The bowl LOOKS seated on the plate from the last image. But the predicate hasn't fired. Possible causes:
1. The bowl isn't actually ON the plate per the predicate's In/On region (maybe it's perched on the plate rim/edge — the bowl was tilted slightly when released, one edge might be off-center enough).
2. The predicate r
- [msg67 assistant 文本] Retreated clear (z=1.089), still not terminated. Let me look at the exact final geometry before choosing the settle strategy:
- [msg67 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-17:42:51_glm-5.3-flash_h1P2_libero_spatial_task_t9_s3_r1/images_cam_hi/image_cam_hi_09.png"}
```
- [msg68 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-17:42:51_glm-5.3-flash_h1P2_libero_spatial_task_t9_s3_r1/images_cam_hi/image_cam_hi_09.png
- [msg69 assistant 思考] The scene: the bowl is ON the plate — but looking closely, the bowl appears to sit slightly toward the -x (left/toward robot) edge of the plate; the plate's red rings are visible on the right side of the bowl. The bowl looks upright and resting. The eef is clear (up at 1.089, near the ramekin — careful!).

Still libero_terminated: false. The predicate might require:
- The bowl to be fully within t
- [msg69 assistant 文本] The bowl is on the plate but sits slightly toward the plate's −x edge — the predicate likely wants it seated more centrally (base fully in the plate region). Per the R5 recovery (the proven t9 chain finisher), invoking **pi0_doubled** as the double-stage placement contact — the bowl is directly under the gripper, so grounding is local:
- [msg69 assistant 调用 pi0_doubled] ```json
{"max_chunks": 20, "prompt": "place the bowl on the plate"}
```
- [msg70 tool 结果] {
  "step": 10,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.08072151494833417,
      0.2209731957110907,
      1.0464953447367218
    ],
    "robot0_eef_quat": [
      0.728265275175359,
      0.6481382992925286,
      0.12193592615859378,
      0.18622047115124607
    ],
    "robot0_gripper_qpos": [
      0.03959304877158697,
      -0.04001773677855097
    ],
    "object_names": [
      "akita_black_bowl_1",
      "akita_black_bowl_2",
      "cookies_1",
      "glazed_rim_porcelain_ramekin_1",
      "plate_1"
    ]
  },
  "libero_terminated": false,
  "episode_truncated": false,
  "world_map": "world/world_10.npy",
  "wrist_world_map": "world_wrist/world_wrist_10.npy",
  "world_map_hi": "world_hi/world
- [msg72 assistant 思考] The pi0_doubled ran its 20 chunks (contact_skill_executed: true) but success=false (libero_terminated still false). The eef moved to [0.0807, 0.2210, 1.0465] — it nudged +x/+y and descended slightly (z 1.046). The gripper is open (0.0396).

Concerning: the eef moved toward the ramekin direction? The ramekin was at approximately... the ramekin was near the plate, at around [0.06-0.08, 0.25+]? Actua
- [msg72 assistant 文本] pi0_doubled executed its contact chunks but `libero_terminated` is still false; the EEF moved to [0.081, 0.221, 1.046] — it nudged toward plate center (+x/+y from the −x edge). Checking what it actually did to the scene:
- [msg72 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-17:42:51_glm-5.3-flash_h1P2_libero_spatial_task_t9_s3_r1/images_cam_hi/image_cam_hi_10.png"}
```
- [msg73 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-17:42:51_glm-5.3-flash_h1P2_libero_spatial_task_t9_s3_r1/images_cam_hi/image_cam_hi_10.png
- [msg74 assistant 思考] The scene after pi0_doubled: the bowl remains on the plate (upright, seated — looks very similar to before, maybe nudged slightly +x). The gripper retreated up-right, near the ramekin but not touching it. Everything looks clean: bowl ON plate, upright, gripper clear.

Yet libero_terminated remains FALSE.

Let me think hard about why the predicate won't fire. The task: "Pick the akita black bowl on
- [msg74 assistant 文本] The bowl is seated upright on the plate, gripper clear — visually the language is satisfied, yet the predicate hasn't fired. Per memory ("predicate-gated by EEF proximity — retreat fully clear"), my last two poses stayed close over the plate. One zero-risk move first: retreat well away (toward +x/−y, away from the ramekin) and re-check:
- [msg74 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.012, "xyz": [0.1, 0.05, 1.1]}
```
- [msg75 tool 结果] {
  "step": 11,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.10006665538560075,
      0.06183287649801603,
      1.1000914196600482
    ],
    "robot0_eef_quat": [
      0.7274472968889653,
      0.6476447625413917,
      0.12569381515754507,
      0.1886206686256372
    ],
    "robot0_gripper_qpos": [
      0.03953368007434953,
      -0.04001820990254842
    ],
    "object_names": [
      "akita_black_bowl_1",
      "akita_black_bowl_2",
      "cookies_1",
      "glazed_rim_porcelain_ramekin_1",
      "plate_1"
    ]
  },
  "libero_terminated": false,
  "episode_truncated": false,
  "world_map": "world/world_11.npy",
  "wrist_world_map": "world_wrist/world_wrist_11.npy",
  "world_map_hi": "world_hi/worl
- [msg76 assistant 思考] Retreated to [0.100, 0.062, 1.100] — far from the plate (12cm away horizontally, 19cm above the plate top). Still libero_terminated: false.

So EEF proximity is not the gate. The bowl is visibly on the plate but the predicate won't fire. Per the seed-0 A1 failure mode: "Visibly on/near plate but predicate false — bowl base stayed outside predicate." The fix was changing the release pose — i.e., th
- [msg76 assistant 文本] Far retreat didn't fire it either — EEF proximity is not the gate. The bowl is on the plate but per the seed-0 A1 failure mode its base likely sits outside the predicate region (off-center on the plate). Final placement play: **low regrasp-settle** — re-grasp the seated bowl, then re-place it dead-center at the plate anchor [0.070, 0.202]. Pre-positioning over the bowl:
- [msg76 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 80, "step_clip": 0.012, "xyz": [0.066, 0.208, 1.07]}
```
- [msg77 tool 结果] {
  "step": 12,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.06573504079307299,
      0.1962957295010529,
      1.0696329851607402
    ],
    "robot0_eef_quat": [
      0.7267439748457016,
      0.6481968714409692,
      0.12736205914172377,
      0.18831600242886662
    ],
    "robot0_gripper_qpos": [
      0.03952955650013581,
      -0.04001829405939235
    ],
    "object_names": [
      "akita_black_bowl_1",
      "akita_black_bowl_2",
      "cookies_1",
      "glazed_rim_porcelain_ramekin_1",
      "plate_1"
    ]
  },
  "libero_terminated": false,
  "episode_truncated": false,
  "world_map": "world/world_12.npy",
  "wrist_world_map": "world_wrist/world_wrist_12.npy",
  "world_map_hi": "world_hi/worl
- [msg78 assistant 思考] Pre-positioned over the bowl at [0.066, 0.196, 1.070] (final y settled at 0.196, a bit -y of target 0.208 — the OSC wall again; fine, within 2cm of the bowl). Gripper open.

Now the re-pick: pi0_pick("pick up the bowl on the plate", max_chunks=12, lift_thresh=0.04, gripper_closed_thresh=0.06). Short local prompt; bowl directly below.
- [msg78 assistant 文本] Over the bowl at [0.066, 0.196, 1.070]. Re-grasping with a short local prompt:
- [msg78 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.04, "max_chunks": 12, "prompt": "pick up the bowl on the plate"}
```

## 请作答(仅凭以上材料;不看任何分析输出)

段级三选一(聚合规则:任一事件 YES → DEPENDENT;全部事件 NO 且观察前
序列+关键参数已固定 → INDEPENDENT;无法证明任一方 → UNRESOLVED,禁止猜测):

1. **label**:DEPENDENT / INDEPENDENT / UNRESOLVED
2. **evidence_event**:支撑判定的关键事件定位(引用 step 编号或
   [msgN] 编号,如 "step 8 move_to 结果" / "[msg54] 看图后";无事件写 none)
3. **dependency_type**(八选一):observation_gate / target_grounding /
   pose_update / parameter_update / verifier_branch / retry_fallback /
   termination / none
