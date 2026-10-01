# N0 盲审卷宗:dossier_35(control-dependency audit)
- 失败族:FALSE_GRASP(node FALSE_GRASP)
- t0(窗口起始步)= step 2;tR(窗口结束步)= step 5
- task 3 / seed 2 / 长度层 M
- t0 eef ['0.047', '-0.243', '1.236'] grip [0.03844306792854021, -0.03893128122268577]
- tR eef ['0.077', '0.246', '0.939'] grip [0.003158666445793941, -0.00390815903559756]
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

### step 2
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.05,
 "max_chunks": 14,
 "prompt": "pick up the black patterned bowl on top of the cabinet"
}
```
```json
{
 "name": "pick",
 "instruction": "pick up the black patterned bowl on top of the cabinet",
 "success": false,
 "chunks_used": 14,
 "max_chunks": 14,
 "peak_lift_m": 0.09632325172424316,
 "min_gripper_opening": 0.0018378947861492634,
 "final_gripper_opening": 0.07737434655427933,
 "libero_terminated": false,
 "diagnostics": {
  "start_eef_z": 1.1815,
  "peak_eef_z": 1.2362,
  "min_eef_z": 1.1399,
  "post_min_peak_z": 1.2362,
  "descent_m": 0.0416,
  "post_min_ascent_m": 0.0963,
  "descent_done": false,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```
### step 3
```json
{
 "action": "move_to",
 "gripper": -1,
 "step_clip": 0.012,
 "tol": 0.012,
 "xyz": [
  0.083,
  -0.295,
  1.165
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.08299999684095383,
  -0.29499998688697815,
  1.1649999618530273
 ],
 "final_eef_pos": [
  0.0868,
  -0.2955,
  1.1752
 ],
 "final_dist_m": 0.0109,
 "steps_used": 23,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 4
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.05,
 "max_chunks": 20,
 "prompt": "Pick the akita black bowl on the top of the cabinet and place it on the plate"
}
```
```json
{
 "name": "pick",
 "instruction": "Pick the akita black bowl on the top of the cabinet and place it on the plate",
 "success": false,
 "chunks_used": 20,
 "max_chunks": 20,
 "peak_lift_m": 0.0,
 "min_gripper_opening": 0.0037158788181841373,
 "final_gripper_opening": 0.003734294790774584,
 "libero_terminated": false,
 "diagnostics": {
  "start_eef_z": 1.1752,
  "peak_eef_z": 1.3202,
  "min_eef_z": 0.9395,
  "post_min_peak_z": 0.9395,
  "descent_m": 0.2357,
  "post_min_ascent_m": 0.0,
  "descent_done": true,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```
### step 5
```json
{
 "action": "release",
 "max_steps": 20
}
```
```json
{
 "name": "release",
 "steps_used": 2,
 "start_gripper_opening": 0.0037,
 "peak_gripper_opening": 0.0071,
 "final_gripper_opening": 0.0071,
 "libero_terminated": true
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg34 assistant 思考] Wrist says the bowl (visible part) is at world (0.0475, -0.321, 1.1348).

Hmm — that differs from the agentview anchor (-0.0136, -0.289, 1.1416) by Δx=+0.06, Δy=-0.032 — about 7cm in x. That's beyond the 3-5cm acceptance window in x.

But wait: the pixel I picked (450, 870) is on the visible portion of the bowl near the image edge — the bowl is partially clipped at the right edge of the wrist view
- [msg34 assistant 文本] Wrist geometry interpreted: the wrist map confirms the bowl center sits ~4cm -y of the eef (visible-fragment pixels hit the inner wall, explaining the x bias) — meaning the current eef pose (y=-0.2455 = bowl_y + 0.045) is already correctly positioned over the bowl's +y rim for a rim-hook grasp. 

**Localization table:**
| entity | evidence | final_xyz | status |
|---|---|---|---|
| target: cabinet-top bowl | agentview (-0.014,-0.289,1.14), wrist y=-0.32 rim band, same bowl in wrist view | anchor confirmed; eef pre-pos done | ready |
| distractor: cookie-box bowl | table-level twin, rejected by support relation | — | avoided |
| plate (red rings) | image right, to localize mid-carry | TBD | pending |

Now Pi0 grasp, rung 1 per the suite memory: short grasp-only prompt, 14 chunks.
- [msg34 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 14, "prompt": "pick up the black patterned bowl on top of the cabinet"}
```
- [msg35 tool 结果] {
  "step": 2,
  "task_language": "Pick the akita black bowl on the top of the cabinet and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.04717419256813606,
      -0.24301827326656414,
      1.2362200861801522
    ],
    "robot0_eef_quat": [
      0.9920063622570415,
      -0.00451793755697133,
      -0.004224429556849915,
      0.12603618399769423
    ],
    "robot0_gripper_qpos": [
      0.03844306792854021,
      -0.03893128122268577
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
  "world_map": "world/world_02.npy",
  "wrist_world_map": "world_wrist/world_wrist_02.npy",
  "world_map_h
- [msg37 assistant 思考] The pick: success=false, but peak_lift_m=0.096 (lifted 9.6cm above min), min_gripper_opening=0.0018 (fully closed at some point), final_gripper_opening=0.0774 — the gripper is now mostly open (0.077). And eef is now at (0.047, -0.243, 1.236). The eef drifted +x significantly (from -0.013 to +0.047) and rose to z=1.236.

Per the suite memory failure mode A1: "First cabinet-top pick lifts then opens
- [msg37 assistant 文本] The pick lifted (peak 9.6cm) but reopened (final gripper 0.077 = wide) — the suite memory's exact A1 failure mode. The eef drifted to (0.047, -0.243, 1.236). Let me check where the bowl is now before re-pre-positioning.
- [msg37 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-18:44:49_glm-5.3-flash_h1C_libero_spatial_task_t3_s2_r1/images_wrist_hi/image_wrist_hi_02.png"}
```
- [msg38 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-18:44:49_glm-5.3-flash_h1C_libero_spatial_task_t3_s2_r1/images_wrist_hi/image_wrist_hi_02.png
- [msg39 assistant 思考] The wrist view now shows the bowl FULLY visible in the frame, well below the gripper (gripper fingers visible at the bottom corners). The bowl sits on the cabinet (dark surface), intact, upright, at roughly (row 550, col 720) in the wrist image. The gripper is high above it (eef z=1.236) and the bowl is NOT held — it stayed on the cabinet.

The bowl in this wrist view is fully in frame, center aro
- [msg39 assistant 文本] The bowl is still on the cabinet, intact and upright, now fully visible in the wrist frame (not held — gripper opened and retreated high). Back-projecting its center from this wrist view for the precise re-pre-position.
- [msg39 assistant 调用 back_project] ```json
{"camera": "wrist", "col": 720, "row": 550, "step": 2}
```
- [msg40 tool 结果] {
  "camera": "wrist",
  "resolution": "high",
  "pixel": [
    550,
    720
  ],
  "world_xyz": [
    0.0833,
    -0.3398,
    1.1357
  ],
  "step": 2,
  "image_size": [
    1024,
    1024
  ],
  "source_artifact": "world_wrist_hi/world_wrist_hi_02.npy"
}
- [msg41 assistant 思考] The bowl center (fully visible now) is at world (0.0833, -0.3398, 1.1357) — z=1.1357 confirms it's still on the cabinet (top z ~1.14), and xy: (0.083, -0.34).

This is in the s0 winning band (x 0.07-0.10, y -0.30..-0.33)! The wrist refinement is trustworthy here: the bowl is fully visible, not clipped, and the pixel was firmly on the bowl's interior. Both my wrist samples converge: y ≈ -0.32..-0.3
- [msg41 assistant 文本] Both wrist samples now agree: bowl center at **(0.083, -0.34, top z≈1.135)** — fully visible, unclipped, in the s0 winning band (x 0.07–0.10, y -0.30..-0.33). The agentview anchor was edge-biased (bowl clipped at image edge); the wrist metric wins. Re-pre-positioning lower and deeper per the A1 fix: eef_y = bowl_y + 0.045 = -0.295, z=1.165.
- [msg41 assistant 调用 move_to] ```json
{"gripper": -1, "step_clip": 0.012, "tol": 0.012, "xyz": [0.083, -0.295, 1.165]}
```
- [msg42 tool 结果] {
  "step": 3,
  "task_language": "Pick the akita black bowl on the top of the cabinet and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.08675267053611471,
      -0.29553631275878967,
      1.1752286109350296
    ],
    "robot0_eef_quat": [
      0.9909843330819132,
      -0.0053646818350309156,
      -0.019505977141697252,
      0.13244164235900685
    ],
    "robot0_gripper_qpos": [
      0.039256702563394544,
      -0.03983197761305708
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
  "world_map": "world/world_03.npy",
  "wrist_world_map": "world_wrist/world_wrist_03.npy",
  "world_ma
- [msg43 assistant 思考] Pre-position reached (0.0868, -0.2955, 1.1752), final_dist 1.1cm — good. Now the second pi0_pick with the FULL task language, max_chunks=20, from this lower/closer pose per the suite memory's winning technique.
- [msg43 assistant 文本] Pre-position achieved (dist 1.1cm). Now the second grasp per the winning technique: full task-language prompt from this lower/closer pose, 20 chunks — the memory says this run can carry the bowl toward the plate despite `success:false`; I'll judge by image and gripper.
- [msg43 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 20, "prompt": "Pick the akita black bowl on the top of the cabinet and place it on the plate"}
```
- [msg44 tool 结果] {
  "step": 4,
  "task_language": "Pick the akita black bowl on the top of the cabinet and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.07807091992040688,
      0.24457575311125485,
      0.9395183918056255
    ],
    "robot0_eef_quat": [
      0.9783393513842815,
      -0.05245091669124452,
      0.038106783846045045,
      0.19659320409449932
    ],
    "robot0_gripper_qpos": [
      0.0015633307439087652,
      -0.0021709638993147387
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
  "world_map": "world/world_04.npy",
  "wrist_world_map": "world_wrist/world_wrist_04.npy",
  "world_map
- [msg46 assistant 思考] Interesting state after the second pick:
- eef now at (0.078, +0.2446, 0.9395) — it traveled from the cabinet (+0.083, -0.295, 1.175) all the way to +y=0.2446 at z=0.9395. That's near TABLE level (table z≈0.90), on the +y side — where the PLATE is (plate at +y≈0.21 per s0 memory)!
- gripper qpos: (0.00156, -0.00217) — fingers FULLY closed (~0.0). Hmm, that indicates grasped AIR per Rule 1b... but 
- [msg46 assistant 文本] The full-task-language pick carried the eef from the cabinet all the way to the plate region (+y=0.245, z=0.94 — table level) with fingers nearly fully closed. Checking the agentview to see where the bowl actually is now.
- [msg46 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-18:44:49_glm-5.3-flash_h1C_libero_spatial_task_t3_s2_r1/images_cam_hi/image_cam_hi_04.png"}
```
- [msg47 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260928-18:44:49_glm-5.3-flash_h1C_libero_spatial_task_t3_s2_r1/images_cam_hi/image_cam_hi_04.png
- [msg48 assistant 思考] HUGE progress! The agentview shows:
- The cabinet top is now EMPTY (the target bowl left the cabinet ✓)
- The cookie-box bowl (distractor) remains in place on its box
- The TARGET bowl is now at the PLATE — sitting on/near the red-ring plate, gripper fingers still engaged with it from the right side. The bowl is ON the plate (overlapping the plate's white center), gripper nearly closed (0.0037 ope
- [msg48 assistant 文本] The target bowl has LEFT the cabinet and is now sitting ON the red-ring plate with the gripper rim-hooked and nearly closed — exactly the s0 winning state. The cabinet is empty, the distractor untouched. Releasing low at the plate now.
- [msg48 assistant 调用 release] ```json
{"max_steps": 20}
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
