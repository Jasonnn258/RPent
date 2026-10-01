# N0 盲审卷宗:dossier_20(control-dependency audit)
- 失败族:RELEASE_PREDICATE_STALL(node RELEASE_PREDICATE_STALL)
- t0(窗口起始步)= step 8;tR(窗口结束步)= step 15
- task 9 / seed 10 / 长度层 L
- t0 eef ['0.007', '0.181', '1.026'] grip [0.039448273948595576, -0.03978668454708826]
- tR eef ['0.085', '0.216', '0.944'] grip [0.03339958670572838, -0.03694802562814747]
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
 "start_gripper_opening": 0.0049,
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
 "step_clip": 0.02,
 "xyz": [
  -0.05,
  0.13,
  1.13
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.05000000074505806,
  0.12999999523162842,
  1.1299999952316284
 ],
 "final_eef_pos": [
  -0.0548,
  0.1265,
  1.1199
 ],
 "final_dist_m": 0.0117,
 "steps_used": 20,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 10
```json
{
 "action": "pi0_doubled",
 "max_chunks": 20,
 "prompt": "put the bowl on the plate"
}
```
```json
{
 "name": "pi0_doubled",
 "instruction": "put the bowl on the plate",
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
 "step_clip": 0.02,
 "xyz": [
  -0.12,
  0.1,
  1.14
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.11999999731779099,
  0.10000000149011612,
  1.1399999856948853
 ],
 "final_eef_pos": [
  -0.1239,
  0.0992,
  1.1306
 ],
 "final_dist_m": 0.0102,
 "steps_used": 31,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 12
```json
{
 "action": "pi0_doubled",
 "max_chunks": 16,
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
 "chunks_used": 16,
 "max_chunks": 16,
 "libero_terminated": false,
 "diagnostics": {
  "mode": "contact_skill_success_by_libero_terminated",
  "success_meaning": "`success` mirrors official LIBERO task termination only; for intermediate contact skills, inspect image/state evidence."
 }
}
```
### step 13
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 60,
 "step_clip": 0.02,
 "xyz": [
  -0.1,
  0.05,
  1.16
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.10000000149011612,
  0.05000000074505806,
  1.159999966621399
 ],
 "final_eef_pos": [
  -0.1006,
  0.0497,
  1.1499
 ],
 "final_dist_m": 0.0101,
 "steps_used": 44,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 14
```json
{
 "action": "move_pose",
 "gripper": -1,
 "max_steps": 120,
 "step_clip": 0.015,
 "target_yaw": 1.57,
 "xyz": [
  0.045,
  0.2,
  1.1
 ]
}
```
```json
{
 "name": "move_pose",
 "final_eef_pos": [
  0.0398,
  0.1903,
  1.099
 ],
 "final_dist_m": 0.0111,
 "final_pitch": -0.1143,
 "steps_used": 37,
 "libero_terminated": false
}
```
### step 15
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.05,
 "max_chunks": 16,
 "prompt": "pick up the bowl"
}
```
```json
{
 "name": "pick",
 "instruction": "pick up the bowl",
 "success": true,
 "chunks_used": 7,
 "max_chunks": 16,
 "peak_lift_m": 0.0,
 "min_gripper_opening": 0.0703476071357727,
 "final_gripper_opening": 0.0703476071357727,
 "libero_terminated": true,
 "diagnostics": {
  "start_eef_z": 1.099,
  "peak_eef_z": 1.099,
  "min_eef_z": 0.9441,
  "post_min_peak_z": 0.9441,
  "descent_m": 0.1549,
  "post_min_ascent_m": 0.0,
  "descent_done": true,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg58 assistant 思考] The eef stalled at z=1.0269 (target 1.015, dist 0.0119 — the stall wall the memory mentioned: "OSC stalls ~... band 1.012-1.026"). Fine — 1.027 is within the winning band (1.012-1.026, just 1mm above).

Bowl center now ≈ [0.0071+0.054, 0.1809+0.034] = [0.061, 0.215] — dead on plate center. Now release with a long settle. Per the memory: "release with a long settle", avoid post-release pushes. rele
- [msg58 assistant 文本] At the release pose (eef z stalled at 1.027, within the winning band; bowl center ≈ plate center). Releasing with a long settle.
- [msg58 assistant 调用 release] ```json
{"max_steps": 40}
```
- [msg59 tool 结果] {
  "step": 8,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.007179953755165584,
      0.18087226150182295,
      1.0263456405259532
    ],
    "robot0_eef_quat": [
      0.6988536949996327,
      0.706753405220765,
      0.002210931065890341,
      0.10999204052127902
    ],
    "robot0_gripper_qpos": [
      0.039448273948595576,
      -0.03978668454708826
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
  "world_map_hi": "world_hi/wo
- [msg61 assistant 思考] The release happened, gripper opened (0.079), but libero_terminated is still false. The phase tracker suggests pi0_doubled for the final placement, and memory cards suggest: retreat the eef clear before judging; the predicate may fire after the gripper retreats.

Plan:
1. Check the wrist/agentview image to see where the bowl landed relative to the plate.
2. Retreat straight up + laterally away, re
- [msg61 assistant 文本] Release executed but predicate not yet fired. Before any correction, let me see where the bowl landed.
- [msg61 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-09:27:49_glm-5.3-flash_memO2_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_08.png"}
```
- [msg62 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-09:27:49_glm-5.3-flash_memO2_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_08.png
- [msg63 assistant 思考] Excellent view! The bowl is now ON the plate — it sits on the plate's left/upper portion, tilted slightly? Let me look: the bowl (patterned, yellow rim) is sitting at the upper-left edge of the red-ring plate, appears to rest on the plate (its base covers the plate's upper-left quadrant, overlapping the plate's rim?). The plate is at lower-right; the bowl occupies the upper-left portion of the pla
- [msg63 assistant 文本] The bowl is ON the plate (overlapping its upper-left area, slightly tilted) but the predicate hasn't fired — the gripper is still hovering right above it. Retreating straight up then laterally clear before judging.
- [msg63 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.02, "xyz": [-0.05, 0.13, 1.13]}
```
- [msg64 tool 结果] {
  "step": 9,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.05477332269249992,
      0.1265036596938327,
      1.1199237078689055
    ],
    "robot0_eef_quat": [
      0.6976938207855233,
      0.7072234162580445,
      0.012687476905834064,
      0.11356671987761774
    ],
    "robot0_gripper_qpos": [
      0.03966777724545716,
      -0.039999523937395386
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
- [msg65 assistant 思考] Retreated up and back (-x, -y), eef now at [-0.055, 0.127, 1.120] — clearly clear of the bowl/plate. libero_terminated still false.

So the bowl is on the plate but the predicate doesn't fire. The bowl looked TILTED and off-center — sitting on the plate's upper-left rim, not seated flat in the center. Maybe the predicate requires the bowl base properly on the plate.

Per R5 recovery: use pi0_doubl
- [msg65 assistant 文本] EEF is now fully clear and the predicate is still false — the bowl is perched/tilted on the plate's rim edge, not seated. Applying the R5 recovery: pi0_doubled as the final placement/seat stage.
- [msg65 assistant 调用 pi0_doubled] ```json
{"max_chunks": 20, "prompt": "put the bowl on the plate"}
```
- [msg66 tool 结果] {
  "step": 10,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.004530519139259899,
      0.17271859391030353,
      0.9958532829011928
    ],
    "robot0_eef_quat": [
      0.5744584938867481,
      0.7781608742132239,
      0.06676957733340526,
      0.2449590091990849
    ],
    "robot0_gripper_qpos": [
      0.03954276592555789,
      -0.04001609617176299
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
  "world_map_hi": "world_hi/wo
- [msg68 assistant 思考] pi0_doubled used 20 chunks; the eef moved down to z 0.996 near the bowl/plate and gripper is open. But libero_terminated is still false. It may have nudged the bowl. Let me look at the current image to see the final state — one look (P_verify phase says confirm final placement; R7 says don't re-open perception... but I must verify whether the placement is now correct or whether pi0_doubled messed 
- [msg68 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-09:27:49_glm-5.3-flash_memO2_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_10.png"}
```
- [msg69 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-09:27:49_glm-5.3-flash_memO2_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_10.png
- [msg70 assistant 思考] The bowl now sits much better on the plate — it looks properly seated in the plate's center (the bowl is upright, its base on the plate, red rings visible around it on the right/bottom edges). Pi0's double-stage nudge settled it. But libero_terminated is STILL false.

Hmm. Why wouldn't it fire? The bowl appears ON the plate now. Possibilities:
1. The predicate needs the exact akita_black_bowl that
- [msg70 assistant 文本] Pi0's seat actually landed the bowl nicely centered on the plate — but the eef is hovering right above it again (z 0.996). Retreating fully clear and re-checking the predicate.
- [msg70 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.02, "xyz": [-0.12, 0.1, 1.14]}
```
- [msg71 tool 结果] {
  "step": 11,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.12385203459515466,
      0.09924478261133282,
      1.13059621647598
    ],
    "robot0_eef_quat": [
      0.5764445209752311,
      0.7740533612309763,
      0.0704042849358796,
      0.2521831573823483
    ],
    "robot0_gripper_qpos": [
      0.039569904426438526,
      -0.040017060182513546
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
- [msg72 assistant 思考] Still false even with the eef fully retreated ([-0.124, 0.099, 1.131] — clearly away from the plate at [0.06, 0.21]).

The bowl looks visually ON the plate. Why isn't the predicate firing?

Consider Rule 2b-style disambiguation: "the akita black bowl ON THE STOVE" — I picked the bowl from the stove square... wait, DID I? Let me re-examine. At step 0, the scene had:
- Bowl A on the dark cabinet (to
- [msg72 assistant 文本] EEF fully clear, predicate still false — the bowl is visually on the plate but likely 1–2cm off the checked center. Per the memory's near-goal pattern, one corrective contact attempt: pi0_doubled again with the placement phrasing.
- [msg72 assistant 调用 pi0_doubled] ```json
{"max_chunks": 16, "prompt": "place the bowl on the plate"}
```
- [msg73 tool 结果] {
  "step": 12,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.04011357145922015,
      0.0568910454387516,
      0.93409021864026
    ],
    "robot0_eef_quat": [
      0.8423594119641692,
      0.4720350970627093,
      0.036797425722347094,
      0.2574090862354808
    ],
    "robot0_gripper_qpos": [
      0.03949557957426371,
      -0.04053697823809986
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
  "world_map_hi": "world_hi/world_
- [msg74 assistant 思考] pi0_doubled ran again; the eef went down to [0.040, 0.057, 0.934] — that's between the cookies box and the plate, quite low (0.934 is 2.7cm above table 0.907). It may have nudged the bowl or knocked things. Let me check the final image to see the scene state.
- [msg74 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-09:27:49_glm-5.3-flash_memO2_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_12.png"}
```
- [msg75 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-09:27:49_glm-5.3-flash_memO2_libero_spatial_task_t9_s10_r1/images_cam_hi/image_cam_hi_12.png
- [msg76 assistant 思考] The bowl remains ON the plate (seated, upright, red rings visible around it — looks properly on the plate). The second pi0_doubled didn't disturb it (the eef hovered near the cookies box). libero_terminated still false.

Status: bowl visually ON plate, gripper open and clear-ish (eef at [0.040, 0.057, 0.934] — that's low, near the cookies box, ~16cm from the plate center; the gripper body may stil
- [msg76 assistant 文本] The bowl is seated on the plate; the second contact pass didn't disturb it. The eef is still low near the plate — one final clean retreat, then I judge and write the audit.
- [msg76 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.02, "xyz": [-0.1, 0.05, 1.16]}
```
- [msg77 tool 结果] {
  "step": 13,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.10059600425877005,
      0.04968654467184554,
      1.1499456722154857
    ],
    "robot0_eef_quat": [
      0.8437762820123806,
      0.4685230058299133,
      0.043274319758773605,
      0.25817651359269717
    ],
    "robot0_gripper_qpos": [
      0.03948022835782965,
      -0.04002002023067943
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
  "world_map_hi": "world_hi/w
- [msg78 assistant 思考] Still libero_terminated: false with the eef fully retreated to [-0.10, 0.05, 1.15].

The bowl is visually on the plate but the predicate won't fire. I've made: 1 release + 2 pi0_doubled + 2 retreat-rechecks. Per the rules and memory ("if it fails again, stop and report honestly"), I should stop.

But hold on — before writing the failure audit, let me reconsider the one lever I haven't tried from t
- [msg78 assistant 文本] Still non-terminating with the eef fully clear. The bowl is visually on the plate but evidently a hair outside the checked region — my release left it on the plate's left rim area. Best remaining lever per the memory (A1: change release pose, near-target-repick): regrasp from directly above and re-place dead-center with a lower release. Pre-positioning over the bowl with yaw restored.
- [msg78 assistant 调用 move_pose] ```json
{"gripper": -1, "max_steps": 120, "step_clip": 0.015, "target_yaw": 1.57, "xyz": [0.045, 0.2, 1.1]}
```
- [msg79 tool 结果] {
  "step": 14,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.03975749911128854,
      0.19030520152409403,
      1.0990168083275473
    ],
    "robot0_eef_quat": [
      0.6711071229229848,
      0.691521467079566,
      0.1460284710074624,
      0.223805665221816
    ],
    "robot0_gripper_qpos": [
      0.039463219639315324,
      -0.0400208467261371
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
  "world_map": "world/world_14.npy",
  "wrist_world_map": "world_wrist/world_wrist_14.npy",
  "world_map_hi": "world_hi/world_h
- [msg81 assistant 思考] Budget is nearly exhausted (≤5 turns left). I'm hovering over the bowl at [0.040, 0.190, 1.099]. One final decisive attempt: regrasp with pi0_pick from here, then place dead-center with a low release. If the pick fails or the re-place doesn't terminate, I write the audit and finish.

pi0_pick "pick up the bowl" max_chunks=16, lift 0.05, closed_thresh 0.06.
- [msg81 assistant 文本] Budget is nearly exhausted — one decisive regrasp attempt from this hover.
- [msg81 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 16, "prompt": "pick up the bowl"}
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
