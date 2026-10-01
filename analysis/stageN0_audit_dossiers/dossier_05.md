# N0 盲审卷宗:dossier_05(control-dependency audit)
- 失败族:RELEASE_PREDICATE_STALL(node RELEASE_PREDICATE_STALL)
- t0(窗口起始步)= step 12;tR(窗口结束步)= step 14
- task 9 / seed 16 / 长度层 S
- t0 eef ['0.108', '0.230', '1.025'] grip [0.03956923676625428, -0.039665525304017714]
- tR eef ['0.062', '0.220', '0.942'] grip [0.03983243352292514, -0.0400108648357673]
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

### step 12
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
 "start_gripper_opening": 0.001,
 "peak_gripper_opening": 0.0792,
 "final_gripper_opening": 0.0792,
 "libero_terminated": false
}
```
### step 13
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 40,
 "step_clip": 0.012,
 "xyz": [
  0.108,
  0.23,
  1.16
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.1080000028014183,
  0.23000000417232513,
  1.159999966621399
 ],
 "final_eef_pos": [
  0.1063,
  0.2296,
  1.1425
 ],
 "final_dist_m": 0.0176,
 "steps_used": 40,
 "max_steps": 40,
 "libero_terminated": false
}
```
### step 14
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
 "success": true,
 "task_success": true,
 "contact_skill_executed": true,
 "chunks_used": 7,
 "max_chunks": 20,
 "libero_terminated": true,
 "diagnostics": {
  "mode": "contact_skill_success_by_libero_terminated",
  "success_meaning": "`success` mirrors official LIBERO task termination only; for intermediate contact skills, inspect image/state evidence."
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg73 assistant 思考] The wrist view at step 11: the bowl is LOW now — its rim nearly at the bottom of the frame, and the red-ringed plate is visible BEHIND/AROUND the bowl (red rings visible to the right of the bowl, and the plate's rings wrap around). The bowl sits with the plate's red rings visible on its right side. The bowl appears to be resting at plate level — the red plate rings show around the bowl's right rim
- [msg73 assistant 文本] The bowl is seated low with the plate's red rings visible right around it — contact made (descent stalled at the OSC wall). Releasing with a long settle.
- [msg73 assistant 调用 release] ```json
{"max_steps": 40}
```
- [msg74 tool 结果] {
  "step": 12,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.10770150916860177,
      0.2301089322003571,
      1.0254508380509466
    ],
    "robot0_eef_quat": [
      0.7073752822033076,
      0.7060644996602508,
      0.03303170584794585,
      -0.0014278851791742538
    ],
    "robot0_gripper_qpos": [
      0.03956923676625428,
      -0.039665525304017714
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
  "world_map_hi": "world_hi/
- [msg76 assistant 思考] Release done (gripper fully opened, 40 steps) but libero_terminated is still FALSE. The bowl was released at eef [0.108, 0.230, 1.025].

The phase note says RULE R5 fired: t9 placement precision — use pi0_doubled for the final placement. The recovery: "t9 placement precision: use pi0_doubled (double-stage placement) for the final placement — the successful t9 chain is segment→back_project→move_to→
- [msg76 assistant 文本] Released but not yet terminated. Let me check where the bowl actually landed relative to the plate.
- [msg76 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260922-21:32:26_glm-5.3-flash_g05P2_libero_spatial_task_t9_s16_r1/images_cam_hi/image_cam_hi_12.png"}
```
- [msg77 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260922-21:32:26_glm-5.3-flash_g05P2_libero_spatial_task_t9_s16_r1/images_cam_hi/image_cam_hi_12.png
- [msg78 assistant 思考] The bowl IS ON THE PLATE — clearly seated within the red rings, though shifted toward the upper-right of the plate (the plate's rings show more on the lower-left). The gripper is open, hovering right above it. The stove is empty; cabinet bowl (distractor) untouched.

libero_terminated is still false. Likely causes:
1. The predicate is gated by eef proximity — the gripper hovers directly over the b
- [msg78 assistant 文本] The bowl IS on the plate (red rings around it) — but the predicate hasn't fired, likely gated by the gripper hovering directly over it. Retreating straight up to clear, then re-checking.
- [msg78 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 40, "step_clip": 0.012, "xyz": [0.108, 0.23, 1.16]}
```
- [msg79 tool 结果] {
  "step": 13,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.10633105449966875,
      0.22964498766438463,
      1.1424927027908347
    ],
    "robot0_eef_quat": [
      0.7074297951295022,
      0.7058307854258163,
      0.036678865674067855,
      0.0008050596670809984
    ],
    "robot0_gripper_qpos": [
      0.03988164215913116,
      -0.03998584190934325
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
  "world_map": "world/world_13.npy",
  "wrist_world_map": "world_wrist/world_wrist_13.npy",
  "world_map_hi": "world_hi/
- [msg81 assistant 思考] Retreated to z=1.142, still libero_terminated=false. The bowl is visibly on the plate. The predicate isn't firing.

Possibilities:
1. The bowl is on the plate but its position is judged "not on" — e.g. the In/On predicate checks the bowl's center against the plate's region and the bowl is offset toward the plate's upper-right edge. Looking at image_12: the bowl sat shifted toward the upper-right o
- [msg81 assistant 文本] Retreated clear; still not terminated. Per the R5 recovery, invoking `pi0_doubled` as the final placement skill to seat the bowl properly.
- [msg81 assistant 调用 pi0_doubled] ```json
{"max_chunks": 20, "prompt": "place the bowl on the plate"}
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
