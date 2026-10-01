# N0 盲审卷宗:dossier_31(control-dependency audit)
- 失败族:FALSE_GRASP(node FALSE_GRASP)
- t0(窗口起始步)= step 7;tR(窗口结束步)= step 11
- task 9 / seed 10 / 长度层 M
- t0 eef ['-0.010', '-0.059', '1.261'] grip [0.0022776604180407365, -0.002654537975161528]
- tR eef ['0.035', '0.205', '0.956'] grip [0.0039007138256470157, -0.0038893310747992174]
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

### step 7
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.05,
 "max_chunks": 16,
 "prompt": "pick up the bowl on the stove"
}
```
```json
{
 "name": "pick",
 "instruction": "pick up the bowl on the stove",
 "success": false,
 "chunks_used": 16,
 "max_chunks": 16,
 "peak_lift_m": 0.31015175580978394,
 "min_gripper_opening": 0.004928278736770153,
 "final_gripper_opening": 0.00493219867348671,
 "libero_terminated": false,
 "diagnostics": {
  "start_eef_z": 0.9951,
  "peak_eef_z": 1.2612,
  "min_eef_z": 0.951,
  "post_min_peak_z": 1.2612,
  "descent_m": 0.0441,
  "post_min_ascent_m": 0.3102,
  "descent_done": false,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```
### step 8
```json
{
 "action": "move_pose",
 "gripper": 1,
 "step_clip": 0.01,
 "target_yaw": 1.57,
 "xyz": [
  0.039,
  0.224,
  1.1
 ]
}
```
```json
{
 "name": "move_pose",
 "final_eef_pos": [
  0.0384,
  0.2145,
  1.0994
 ],
 "final_dist_m": 0.0095,
 "final_pitch": -0.1067,
 "steps_used": 110,
 "libero_terminated": false
}
```
### step 9
```json
{
 "action": "move_to",
 "gripper": 1,
 "step_clip": 0.005,
 "xyz": [
  0.039,
  0.224,
  0.955
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.039000000804662704,
  0.2240000069141388,
  0.9549999833106995
 ],
 "final_eef_pos": [
  0.0387,
  0.2237,
  0.9991
 ],
 "final_dist_m": 0.0441,
 "steps_used": 80,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 10
```json
{
 "action": "move_pose",
 "gripper": 1,
 "max_steps": 150,
 "pitch_step": 0.01,
 "step_clip": 0.005,
 "target_pitch": -0.3,
 "target_yaw": 1.57,
 "xyz": [
  0.035,
  0.205,
  0.945
 ]
}
```
```json
{
 "name": "move_pose",
 "final_eef_pos": [
  0.0353,
  0.2052,
  0.957
 ],
 "final_dist_m": 0.012,
 "final_pitch": -0.3,
 "steps_used": 31,
 "libero_terminated": false
}
```
### step 11
```json
{
 "action": "release",
 "max_steps": 25
}
```
```json
{
 "name": "release",
 "steps_used": 2,
 "start_gripper_opening": 0.0049,
 "peak_gripper_opening": 0.0078,
 "final_gripper_opening": 0.0078,
 "libero_terminated": true
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg52 assistant 思考] EEF is at [-0.277, -0.113, 0.995], gripper open (0.039 separation), yaw 1.57 held. Bowl below at [-0.270, -0.117]. Nicely centered this time (eef within 1cm of bowl center xy).

Now re-grasp: pi0_pick, same winning prompt. The descent will be short (bowl top 0.959, eef 0.995 — only 3.6cm). Pi0 will descend ~5cm and close. Fingers should land deeper inside/around the bowl.
- [msg52 assistant 文本] Centered over the bowl (Δ<1cm) with the gripper open at yaw 1.57. Re-grasping:
- [msg52 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 16, "prompt": "pick up the bowl on the stove"}
```
- [msg53 tool 结果] {
  "step": 7,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.009646514165872113,
      -0.058673744740981984,
      1.2611997598287055
    ],
    "robot0_eef_quat": [
      0.6911359144827325,
      0.7187479443868262,
      -0.034001111673704454,
      0.06764957174129417
    ],
    "robot0_gripper_qpos": [
      0.0022776604180407365,
      -0.002654537975161528
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
  "world_map": "world/world_07.npy",
  "wrist_world_map": "world_wrist/world_wrist_07.npy",
  "world_map_hi": "worl
- [msg54 assistant 思考] WHOA. pi0_pick went ROGUE: it lifted the eef all the way to z=1.261 (peak_lift 0.310!) and moved to [-0.010, -0.059, 1.261] — that's Pi0's trained pick-and-CARRY behavior (it carried the grasp toward its trained place pose, +y direction). The gripper separation is now 0.0049 — nearly fully closed.

Did it carry the BOWL? peak_lift 0.31m with descent only 0.044m. If the bowl is held, it's now somew
- [msg54 assistant 文本] Pi0 went rogue — it lifted to z=1.26 with fingers fully closed (0.0049 = air) and drifted toward its trained carry pose. The grasp missed. Verifying the scene state:
- [msg54 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260920-11:31:18_glm-5.3-flash_g0B_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_07.png"}
```
- [msg55 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260920-11:31:18_glm-5.3-flash_g0B_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_07.png
- [msg56 assistant 思考] PLOT TWIST — the bowl IS in the gripper! The image shows the patterned bowl (blue/white pattern, yellow rim) held IN the gripper, suspended high above the (empty) stove. The stove cook region is empty. The bowl is held upright, deep in the gripper — the gripper went INSIDE the bowl (fingers inside the bowl, gripping the inner walls from inside?? or the fingers are inside the bowl cavity and the bo
- [msg56 assistant 文本] Excellent — **the bowl IS held!** Pi0's aggressive trajectory speared the fingers INSIDE the bowl cavity; the bowl hangs on the fingers high above the now-empty stove. This deep grasp is actually squeeze-proof (closing wedges it onto the walls). The "fully closed" fingers are closed *inside the cavity*.

Measuring the new held-bowl offset from this agentview view:
- [msg56 assistant 调用 back_project] ```json
{"col_range": [320, 460], "resolution": "high", "row_range": [235, 325], "step": 7}
```
- [msg57 tool 结果] {
  "camera": "agentview",
  "resolution": "high",
  "mode": "region",
  "row_range": [
    235,
    325
  ],
  "col_range": [
    320,
    460
  ],
  "z_band": [
    null,
    null
  ],
  "center_xyz": [
    -0.9512,
    -0.249,
    1.2676
  ],
  "median_xyz": [
    0.0191,
    -0.0673,
    1.2676
  ],
  "n_valid": 12600,
  "step": 7,
  "image_size": [
    1024,
    1024
  ],
  "source_artifact": "world_hi/world_hi_07.npy"
}
- [msg58 assistant 思考] The median [-0.9512...] vs center [0.0191, -0.0673, 1.2676] — the median x is polluted by bad pixels (n_valid 12600 but median -0.95?? That's off-table). The center_xyz [0.0191, -0.0673, 1.2676] looks plausible (near the eef [-0.010, -0.059]). But median vs center disagree wildly on x — the window caught bad depth pixels (maybe the robot arm background). The z=1.2676 ≈ eef z (1.261) — so this capt
- [msg58 assistant 文本] Median polluted by background depth outliers (robot arm). Re-sampling tighter on the bowl interior only:
- [msg58 assistant 调用 back_project] ```json
{"col_range": [345, 445], "resolution": "high", "row_range": [255, 310], "step": 7}
```
- [msg59 tool 结果] {
  "camera": "agentview",
  "resolution": "high",
  "mode": "region",
  "row_range": [
    255,
    310
  ],
  "col_range": [
    345,
    445
  ],
  "z_band": [
    null,
    null
  ],
  "center_xyz": [
    0.0435,
    -0.0657,
    1.2617
  ],
  "median_xyz": [
    0.0112,
    -0.0646,
    1.2617
  ],
  "n_valid": 5500,
  "step": 7,
  "image_size": [
    1024,
    1024
  ],
  "source_artifact": "world_hi/world_hi_07.npy"
}
- [msg60 assistant 思考] Tighter window: median [0.0112, -0.0646, 1.2617], center [0.0435, -0.0657]. Median now sane and close to the first center estimate. Take bowl center ≈ [0.011, -0.065] (median of the tighter window; the two samples' centers straddle it).

Held offset = bowl_center − eef = [0.011 − (−0.0096), −0.065 − (−0.0587)] = [+0.021, −0.006]. So the bowl hangs ~2.1cm +x, 0.6cm −y of the eef. Nearly centered un
- [msg60 assistant 文本] **New held offset**: bowl center ≈ [+0.011, −0.065] → offset = [+0.021, −0.006] from eef (nearly centered — much better than the first pinch). Rim at eef_z, base ≈ eef_z−0.04. 

Placement target: eef_xy = [0.060−0.021, 0.218+0.006] = **[0.039, 0.224]**, release z ≈ 0.95. Δxy = 0.287 < 0.30 → single carry waypoint at z=1.10:
- [msg60 assistant 调用 move_pose] ```json
{"gripper": 1, "step_clip": 0.01, "target_yaw": 1.57, "xyz": [0.039, 0.224, 1.1]}
```
- [msg61 tool 结果] {
  "step": 8,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.038376945247450035,
      0.21450594302304254,
      1.0993794783020565
    ],
    "robot0_eef_quat": [
      0.7066230549388608,
      0.7055297751997263,
      -0.04345384483917228,
      0.0319899656796798
    ],
    "robot0_gripper_qpos": [
      0.0024954131947520163,
      -0.0024354548200490947
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
  "world_map_hi": "world_hi
- [msg62 assistant 思考] The carry succeeded — eef at [0.0384, 0.2145, 1.0994], over the plate region, gripper still holding (sep 0.0049 — fingers inside bowl). The bowl survived the carry (110 steps under +1 squeeze — the inside-wedge grasp held!).

Now descend over the plate: target [0.039, 0.224, 0.95], step_clip 0.005 (slow, gentle). Then verify, then release.

Descent Δz = 1.10 → 0.95 = 0.15. At 0.005/step = 30 steps
- [msg62 assistant 文本] Carry successful — the deep inside-grasp survived 110 steps of squeeze. EEF is over the plate at z=1.10. Descending slowly toward release z≈0.955 (base ≈ plate surface):
- [msg62 assistant 调用 move_to] ```json
{"gripper": 1, "step_clip": 0.005, "xyz": [0.039, 0.224, 0.955]}
```
- [msg63 tool 结果] {
  "step": 9,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.03873176795728051,
      0.2236813589456147,
      0.9991098840984823
    ],
    "robot0_eef_quat": [
      0.706602486118874,
      0.7055658804969085,
      -0.04343349996120381,
      0.03167405831855988
    ],
    "robot0_gripper_qpos": [
      0.0024631769273985283,
      -0.0024240031958420853
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
  "world_map_hi": "world_hi/w
- [msg64 assistant 思考] The descent STALLED: final eef z = 0.9991 vs target 0.955 — final_dist 0.0441 after using all 80 steps. The eef walls at z≈0.999 (OSC singularity / joint limit at this stretched-forward +y pose). The bowl base is at ~0.999−0.04 = 0.959 — that's 5cm ABOVE the plate surface (0.908). Releasing now would drop the bowl 5cm — it would land on the plate but with a drop-bounce risk (could bounce off).

Th
- [msg64 assistant 文本] The descent stalled at eef z=0.999 (target 0.955) — 80 steps exhausted, final_dist 0.044. The bowl base is ~5cm above the plate. Before forcing deeper, let me check the wrist view to see the actual bowl-to-plate geometry:
- [msg64 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260920-11:31:18_glm-5.3-flash_g0B_libero_spatial_task_t9_s10_r1/images_wrist_hi/image_wrist_hi_09.png"}
```
- [msg65 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260920-11:31:18_glm-5.3-flash_g0B_libero_spatial_task_t9_s10_r1/images_wrist_hi/image_wrist_hi_09.png
- [msg66 assistant 思考] Very informative! The wrist view shows:
- The RED-RING PLATE clearly visible (left-center), lying flat on the table.
- The HELD BOWL (right side, patterned with yellow rim) hanging, tilted, next to/above the plate.
- The plate's center is to the LEFT of the bowl in this view.

The bowl is NOT over the plate center — the bowl hangs to the RIGHT of the plate in the wrist view, and the plate center i
- [msg66 assistant 文本] The wrist view confirms the plate is right below (bowl center ≈ plate center per back-projection). The eef walls at z=0.999 — a yawed-reach wall. Applying the memory lever: co-vary pitch while descending, and pull y slightly back to shorten the reach:
- [msg66 assistant 调用 move_pose] ```json
{"gripper": 1, "max_steps": 150, "pitch_step": 0.01, "step_clip": 0.005, "target_pitch": -0.3, "target_yaw": 1.57, "xyz": [0.035, 0.205, 0.945]}
```
- [msg67 tool 结果] {
  "step": 10,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.03525254648362809,
      0.2052127215060341,
      0.9569632984377682
    ],
    "robot0_eef_quat": [
      0.6995440869887344,
      0.6987834451514019,
      -0.10709147677937608,
      0.10426496411856928
    ],
    "robot0_gripper_qpos": [
      0.0024472849066395556,
      -0.002427979226522938
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
  "world_map_hi": "world_hi/
- [msg68 assistant 思考] The pitch co-variation WORKED: eef descended to z=0.957 (from the 0.999 wall), final_dist 0.012, pitch reached −0.3. The eef is at [0.0353, 0.2052, 0.957].

Bowl base ≈ 0.957 − 0.04 = 0.917 — plate at 0.908 → base ~9mm above the plate. Wait, but the pitch is now −0.3 (17° tilt): the bowl hangs TILTED by ~17°. A tilted bowl with its base 9mm above the plate — when released, it drops and settles. Wi
- [msg68 assistant 文本] The pitch lever worked — eef descended to z=0.957 (broke the 0.999 wall). Bowl center ≈ [0.056, 0.199] — 1.9cm off plate center, well within the rim. With the 17° tilt, the low rim edge is likely already at/near the plate surface. Releasing now to let it settle:
- [msg68 assistant 调用 release] ```json
{"max_steps": 25}
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
