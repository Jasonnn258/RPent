# N0 盲审卷宗:dossier_16(control-dependency audit)
- 失败族:RELEASE_PREDICATE_STALL(node RELEASE_PREDICATE_STALL)
- t0(窗口起始步)= step 9;tR(窗口结束步)= step 14
- task 9 / seed 1 / 长度层 L
- t0 eef ['0.007', '0.184', '1.018'] grip [0.03977733166083673, -0.03990430821902222]
- tR eef ['-0.011', '0.177', '0.941'] grip [0.0003690248299917952, -0.0006305306220727886]
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
 "max_steps": 60
}
```
```json
{
 "name": "release",
 "steps_used": 60,
 "start_gripper_opening": 0.0048,
 "peak_gripper_opening": 0.0797,
 "final_gripper_opening": 0.0797,
 "libero_terminated": false
}
```
### step 10
```json
{
 "action": "move_to",
 "gripper": -1,
 "step_clip": 0.01,
 "xyz": [
  0.007,
  0.184,
  1.12
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.007000000216066837,
  0.18400000035762787,
  1.1200000047683716
 ],
 "final_eef_pos": [
  0.0064,
  0.184,
  1.1086
 ],
 "final_dist_m": 0.0114,
 "steps_used": 37,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 11
```json
{
 "action": "move_to",
 "gripper": 1,
 "step_clip": 0.01,
 "xyz": [
  -0.037,
  0.153,
  1.0
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.03700000047683716,
  0.15299999713897705,
  1.0
 ],
 "final_eef_pos": [
  -0.0364,
  0.153,
  1.0107
 ],
 "final_dist_m": 0.0107,
 "steps_used": 41,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 12
```json
{
 "action": "move_to",
 "gripper": 1,
 "step_clip": 0.004,
 "xyz": [
  -0.037,
  0.153,
  0.93
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.03700000047683716,
  0.15299999713897705,
  0.9300000071525574
 ],
 "final_eef_pos": [
  -0.0369,
  0.1528,
  0.9418
 ],
 "final_dist_m": 0.0118,
 "steps_used": 68,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 13
```json
{
 "action": "move_to",
 "gripper": 1,
 "step_clip": 0.005,
 "xyz": [
  -0.005,
  0.172,
  0.9418
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.004999999888241291,
  0.1720000058412552,
  0.9417999982833862
 ],
 "final_eef_pos": [
  -0.017,
  0.1716,
  0.9416
 ],
 "final_dist_m": 0.012,
 "steps_used": 20,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 14
```json
{
 "action": "move_to",
 "gripper": 1,
 "step_clip": 0.004,
 "xyz": [
  0.012,
  0.188,
  0.9416
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.012000000104308128,
  0.18799999356269836,
  0.9416000247001648
 ],
 "final_eef_pos": [
  -0.011,
  0.1771,
  0.9414
 ],
 "final_dist_m": 0.0254,
 "steps_used": 6,
 "max_steps": 80,
 "libero_terminated": true
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg59 assistant 思考] Only 2 steps used, barely moved (final_dist 0.0115 — it's already within tolerance of the target). EEF at (0.0078, 0.185, 1.0197). The move didn't actually push deeper (OSC likely at contact/desk stall — the bowl may be touching the plate already, resisting further descent).

The bowl is held over the plate with ~1cm bias. Time to release with a long settle per the recipe: release(max_steps=60).
- [msg59 assistant 文本] Good — the servo barely moved (OSC resistance suggests the bowl is already near contact). Releasing now with a long settle.
- [msg59 assistant 调用 release] ```json
{"max_steps": 60}
```
- [msg60 tool 结果] {
  "step": 9,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.006658631549080948,
      0.18355800203270525,
      1.0184306058946129
    ],
    "robot0_eef_quat": [
      0.705900908217347,
      0.7063730023505154,
      -0.009824249886918945,
      0.05142541630752223
    ],
    "robot0_gripper_qpos": [
      0.03977733166083673,
      -0.03990430821902222
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
- [msg62 assistant 思考] The release completed (gripper fully opened 0.0797) but libero_terminated is still false. R5 suggests using pi0_doubled for the final placement. The memory `near-goal-contact-regrasp` / `learned-contact-after-near-placement` also supports: "A scripted release leaves the correct object visibly near or partly on the target surface but the predicate remains false" → use a short learned contact.

Firs
- [msg62 assistant 文本] Release done (gripper fully open) but predicate not yet fired. The EEF is still hovering at the bowl — per the retreat-clear memory, I'll retreat straight up first, then re-evaluate.
- [msg62 assistant 调用 move_to] ```json
{"gripper": -1, "step_clip": 0.01, "xyz": [0.007, 0.184, 1.12]}
```
- [msg63 tool 结果] {
  "step": 10,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.006436628435129004,
      0.183985583902508,
      1.1086249439692095
    ],
    "robot0_eef_quat": [
      0.7058457874156625,
      0.7063822702432708,
      -0.009157834397920827,
      0.05217227944670578
    ],
    "robot0_gripper_qpos": [
      0.03990246681807693,
      -0.04000253667173334
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
- [msg64 assistant 思考] EEF retreated up; still not terminated. Now check where the bowl actually landed — agentview hi-res at step 10.
- [msg64 assistant 文本] Retreated clear, still not terminated. Checking the agentview to see exactly where the bowl landed.
- [msg64 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260907-03:59:25_glm-5.3-flash_armA_libero_spatial_task_t9_s1_r2/images_cam_hi/image_cam_hi_10.png"}
```
- [msg65 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260907-03:59:25_glm-5.3-flash_armA_libero_spatial_task_t9_s1_r2/images_cam_hi/image_cam_hi_10.png
- [msg66 assistant 思考] The agentview shows the bowl sitting on the plate — its base is on the plate's interior/rim area, but the bowl sits mostly on the UPPER-LEFT portion of the plate, with a good part of its base possibly extending beyond the plate's upper-left rim toward the cookies side. Looking closely: the plate spans cols ~695-880, rows ~675-815; the bowl (cols ~675-825, rows ~615-760) sits with its center ≈ (row
- [msg66 assistant 文本] The bowl landed ON the plate but biased ~6cm toward (−x,−y) — its base likely hangs over the rim, which is why the predicate hasn't fired. This matches the `low-contact-seat-after-release` pattern: a short, gentle closed-gripper slide to center the bowl on the plate. Approaching the bowl's upper-left wall from above, fingers closed.
- [msg66 assistant 调用 move_to] ```json
{"gripper": 1, "step_clip": 0.01, "xyz": [-0.037, 0.153, 1.0]}
```
- [msg67 tool 结果] {
  "step": 11,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.03641663296200889,
      0.1530448678997755,
      1.0107023263036945
    ],
    "robot0_eef_quat": [
      0.7054916491097958,
      0.7068203437686773,
      -0.011095536237633694,
      0.05063026512540175
    ],
    "robot0_gripper_qpos": [
      0.00044081923942650684,
      -0.0005587716393486879
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
- [msg68 assistant 思考] In position above the bowl's (−x,−y) wall at z≈1.011, fingers closed. Now descend beside the bowl wall to z≈0.930 with small step clip, then push.
- [msg68 assistant 文本] Hovering above the bowl's offset-side wall. Descending to wall-contact height (z≈0.930), fingers closed.
- [msg68 assistant 调用 move_to] ```json
{"gripper": 1, "step_clip": 0.004, "xyz": [-0.037, 0.153, 0.93]}
```
- [msg69 tool 结果] {
  "step": 12,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.036875460627487394,
      0.1527612206428031,
      0.9418311372784409
    ],
    "robot0_eef_quat": [
      0.7054653582327252,
      0.7068357349743841,
      -0.01023733239143633,
      0.05096144741175411
    ],
    "robot0_gripper_qpos": [
      0.00043793053775831786,
      -0.000561653954233422
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
  "world_map_hi": "world_
- [msg70 assistant 思考] Descend stalled at z=0.9418 (target 0.930) — the gripper is already touching something (likely the bowl rim/wall — good, contact established). Now the gentle push toward (+x,+y): target (−0.005, 0.172, 0.9418→keep same z). Δ = (+0.032, +0.019). Use step_clip 0.005, gripper=+1.
- [msg70 assistant 文本] Contact established (descent stalled at z=0.942 — the fingers are against the bowl wall). Now the gentle centering push toward (+x,+y).
- [msg70 assistant 调用 move_to] ```json
{"gripper": 1, "step_clip": 0.005, "xyz": [-0.005, 0.172, 0.9418]}
```
- [msg71 tool 结果] {
  "step": 13,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.01698673650881167,
      0.17155111378677115,
      0.9415749717527133
    ],
    "robot0_eef_quat": [
      0.7056540933262572,
      0.7065793220856111,
      -0.009615289271422568,
      0.05201450168137327
    ],
    "robot0_gripper_qpos": [
      0.0003718643208589968,
      -0.0006275290416224943
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
  "world_map_hi": "world
- [msg72 assistant 思考] The push moved the EEF from (−0.0369, 0.1528) to (−0.017, 0.1716) — 2.2cm in x, 1.9cm in y before stalling (final_dist 0.012 — it stalled pushing against the bowl+friction). The bowl should have moved similarly (+~2cm, +2cm), putting its center at ≈ (0.02, 0.193). That's ~3.7cm from plate center — base edge at ~6.7cm, within the ~9cm plate radius. Check termination: still false after this move.

H
- [msg72 assistant 文本] The push moved ~2.2cm before stalling. The bowl should now be ~3-4cm off-center — continuing one more short push, then verifying with the camera.
- [msg72 assistant 调用 move_to] ```json
{"gripper": 1, "step_clip": 0.004, "xyz": [0.012, 0.188, 0.9416]}
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
