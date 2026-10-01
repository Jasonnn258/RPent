# N0 盲审卷宗:dossier_12(control-dependency audit)
- 失败族:RELEASE_PREDICATE_STALL(node RELEASE_PREDICATE_STALL)
- t0(窗口起始步)= step 9;tR(窗口结束步)= step 12
- task 5 / seed 2 / 长度层 M
- t0 eef ['0.016', '0.218', '0.980'] grip [0.039204040501607834, -0.039319740310319366]
- tR eef ['-0.002', '0.234', '0.953'] grip [0.020244863679438757, -0.0203996717808293]
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

### step 9
```json
{
 "action": "release",
 "max_steps": 25
}
```
```json
{
 "name": "release",
 "steps_used": 25,
 "start_gripper_opening": 0.0083,
 "peak_gripper_opening": 0.0785,
 "final_gripper_opening": 0.0785,
 "libero_terminated": false
}
```
### step 10
```json
{
 "action": "move_to",
 "gripper": -1,
 "step_clip": 0.012,
 "xyz": [
  0.016,
  0.218,
  1.06
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.01600000075995922,
  0.21799999475479126,
  1.059999942779541
 ],
 "final_eef_pos": [
  0.0156,
  0.2181,
  1.0509
 ],
 "final_dist_m": 0.0091,
 "steps_used": 24,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 11
```json
{
 "action": "move_to",
 "gripper": -1,
 "step_clip": 0.012,
 "xyz": [
  0.018,
  0.219,
  1.0
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.017999999225139618,
  0.21899999678134918,
  1.0
 ],
 "final_eef_pos": [
  0.0178,
  0.2187,
  1.0094
 ],
 "final_dist_m": 0.0094,
 "steps_used": 15,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 12
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.05,
 "max_chunks": 12,
 "prompt": "pick up the black patterned bowl"
}
```
```json
{
 "name": "pick",
 "instruction": "pick up the black patterned bowl",
 "success": true,
 "chunks_used": 10,
 "max_chunks": 12,
 "peak_lift_m": 0.027400732040405273,
 "min_gripper_opening": 0.029390327632427216,
 "final_gripper_opening": 0.040644533932209015,
 "libero_terminated": true,
 "diagnostics": {
  "start_eef_z": 1.0094,
  "peak_eef_z": 1.0094,
  "min_eef_z": 0.9251,
  "post_min_peak_z": 0.9525,
  "descent_m": 0.0843,
  "post_min_ascent_m": 0.0274,
  "descent_done": false,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg50 assistant 思考] Eef descended to z=0.9833, still holding. Now release. The release should be done with the bowl resting on the plate. Per memory: "descend until the bowl visibly contacts the plate before releasing" and "release low enough that the bowl rests on the plate".

z=0.983 — near the earlier stall height (0.986). Release now, then retreat straight up open, and check libero_terminated.
- [msg50 assistant 文本] Descended to z=0.983 with the bowl over the plate. Releasing now, then I'll retreat and verify.
- [msg50 assistant 调用 release] ```json
{"max_steps": 25}
```
- [msg51 tool 结果] {
  "step": 9,
  "task_language": "Pick the akita black bowl on the cookie box and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.016176833476281054,
      0.2181818481042224,
      0.9799214942349521
    ],
    "robot0_eef_quat": [
      0.9992588589984972,
      0.013344342525636543,
      -0.02378807443001,
      0.02716226703519197
    ],
    "robot0_gripper_qpos": [
      0.039204040501607834,
      -0.039319740310319366
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
  "world_map_hi": "world_
- [msg53 assistant 思考] Released (gripper fully open 0.0785) but libero_terminated still false. Per the global memory "predicate-fires-after-gripper-retreat" and "retreat-high-before-lateral": retreat straight up first, then judge.

Then if still false, apply the t5 recovery: short local repick from the low near-plate pose with "pick up the black patterned bowl", max_chunks=12.

Retreat up: move_to [0.016, 0.218, 1.05], 
- [msg53 assistant 文本] Released but not yet terminated. Retreating straight up with the gripper open — predicates often fire after the gripper clears the object.
- [msg53 assistant 调用 move_to] ```json
{"gripper": -1, "step_clip": 0.012, "xyz": [0.016, 0.218, 1.06]}
```
- [msg54 tool 结果] {
  "step": 10,
  "task_language": "Pick the akita black bowl on the cookie box and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.015648845969528025,
      0.21806199203061943,
      1.0508918138210743
    ],
    "robot0_eef_quat": [
      0.9992693249706384,
      0.013244713242434647,
      -0.02328586165098991,
      0.027261004952484173
    ],
    "robot0_gripper_qpos": [
      0.0396721411994781,
      -0.03978924630407951
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
  "world_map_hi": "wor
- [msg56 assistant 思考] Still not terminated after release + retreat. Per the t5 memory's exact recovery: "In this solved run, the first release placed the bowl on the plate but did not fire. A short local repick/contact from the low near-plate pose with `pick up the black patterned bowl`, `max_chunks=12`, triggered `terminated:true` while the bowl was already seated on the plate."

So: descend to the low near-plate pose
- [msg56 assistant 文本] Still not terminated — this matches the t5 memory's known failure mode: "release leaves bowl on plate but terminated:false → short local repick from the low near-plate pose triggers termination". Let me verify the bowl's position first with the agentview.
- [msg56 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260921-07:36:03_glm-5.3-flash_g05P1_libero_spatial_task_t5_s2_r1/images_cam_hi/image_cam_hi_10.png"}
```
- [msg57 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260921-07:36:03_glm-5.3-flash_g05P1_libero_spatial_task_t5_s2_r1/images_cam_hi/image_cam_hi_10.png
- [msg58 assistant 思考] The agentview shows the target bowl now sitting ON the plate (bowl at ~(row 665, col 765), plate beneath it — the red rings visible around the bowl). The cookie box is now empty at (row 750, col 560). The gripper is open, hovering above-right.

The bowl IS on the plate — visually seated, slightly right-of-center on the plate. But the predicate hasn't fired. Per the t5 memory recovery: descend to a
- [msg58 assistant 文本] The bowl is visibly seated on the plate, but the predicate hasn't fired — exactly the t5 failure mode A1. Applying the winning recovery: descend to a low near-plate pose, then a short local repick (max_chunks=12).
- [msg58 assistant 调用 move_to] ```json
{"gripper": -1, "step_clip": 0.012, "xyz": [0.018, 0.219, 1.0]}
```
- [msg59 tool 结果] {
  "step": 11,
  "task_language": "Pick the akita black bowl on the cookie box and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.01784912834473704,
      0.2187448340803478,
      1.009389589119654
    ],
    "robot0_eef_quat": [
      0.9992513194257459,
      0.01390019719605834,
      -0.02418620259111339,
      0.026806953352381268
    ],
    "robot0_gripper_qpos": [
      0.039797080303960584,
      -0.03991134817819037
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
  "world_map_hi": "world
- [msg61 assistant 思考] At the low near-plate pose (z=1.009, bowl directly below). Now the short local repick per the t5 memory: pi0_pick "pick up the black patterned bowl", max_chunks=12, lift_thresh 0.05, gripper_closed_thresh 0.06. This should re-engage the seated bowl and trigger termination.
- [msg61 assistant 文本] At the low near-plate pose directly over the seated bowl. Running the t5 recovery repick now.
- [msg61 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 12, "prompt": "pick up the black patterned bowl"}
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
