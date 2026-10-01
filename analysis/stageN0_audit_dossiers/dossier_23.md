# N0 盲审卷宗:dossier_23(control-dependency audit)
- 失败族:FALSE_GRASP(node FALSE_GRASP)
- t0(窗口起始步)= step 4;tR(窗口结束步)= step 6
- task 9 / seed 4 / 长度层 S
- t0 eef ['-0.345', '-0.225', '0.977'] grip [0.03928119077292448, -0.039680815273559815]
- tR eef ['-0.228', '-0.085', '1.005'] grip [0.005247248867853045, -0.0023164267882650213]
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

### step 4
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
 "peak_lift_m": 0.033682823181152344,
 "min_gripper_opening": 0.0009995566215366125,
 "final_gripper_opening": 0.07896200567483902,
 "libero_terminated": false,
 "diagnostics": {
  "start_eef_z": 1.1198,
  "peak_eef_z": 1.1198,
  "min_eef_z": 0.9698,
  "post_min_peak_z": 1.0035,
  "descent_m": 0.1499,
  "post_min_ascent_m": 0.0337,
  "descent_done": true,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```
### step 5
```json
{
 "action": "move_to",
 "gripper": -1,
 "step_clip": 0.015,
 "xyz": [
  -0.263,
  -0.158,
  1.06
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.2630000114440918,
  -0.15800000727176666,
  1.059999942779541
 ],
 "final_eef_pos": [
  -0.2711,
  -0.1575,
  1.0578
 ],
 "final_dist_m": 0.0084,
 "steps_used": 36,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 6
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
 "success": true,
 "chunks_used": 13,
 "max_chunks": 16,
 "peak_lift_m": 0.054769039154052734,
 "min_gripper_opening": 0.007563675753772259,
 "final_gripper_opening": 0.007563675753772259,
 "libero_terminated": false,
 "diagnostics": {
  "start_eef_z": 1.0578,
  "peak_eef_z": 1.0578,
  "min_eef_z": 0.9503,
  "post_min_peak_z": 1.0051,
  "descent_m": 0.1075,
  "post_min_ascent_m": 0.0548,
  "descent_done": true,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg62 assistant 思考] EEF at (-0.272, -0.150, 1.120) with yaw 1.57, gripper open. Bowl centered below. Now the grasp — per the suite memory: `pi0_pick("pick up the bowl on the stove", max_chunks=16, lift_thresh=0.05, gripper_closed_thresh=0.06)`.
- [msg62 assistant 文本] Centered over the bowl with +1.57 yaw. Invoking Pi0 grasp per the winning recipe:
- [msg62 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 16, "prompt": "pick up the bowl on the stove"}
```
- [msg63 tool 结果] {
  "step": 4,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.34480803460480375,
      -0.2254330225894474,
      0.97653586226001
    ],
    "robot0_eef_quat": [
      0.5584511803098969,
      0.8200428479662786,
      0.006500974472696007,
      0.12497897439466507
    ],
    "robot0_gripper_qpos": [
      0.03928119077292448,
      -0.039680815273559815
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
  "world_map_hi": "world_hi/wor
- [msg64 assistant 思考] pi0_pick reports success:false:
- EEF descended to min z 0.9698 (from 1.1198), then rose to 1.0035 (peak lift only 0.034m < 0.05 threshold).
- final_gripper_opening 0.079 — quite open, min_gripper_opening 0.001 (it fully closed at some point — grabbed air or pressed).
- EEF pos now (-0.345, -0.225, 0.977) — drifted -x,-y from the pick point.

The heuristic says fail, but per the memory ("do not di
- [msg64 assistant 文本] Pi0 reports failure (lift 0.034 < 0.05) and gripper ended open (0.079). Checking the wrist cam to see what actually happened:
- [msg64 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260905-21:10:40_glm-5.3-flash_vanilla_libero_spatial_task_t9_s4_r1/images_wrist_hi/image_wrist_hi_04.png"}
```
- [msg65 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260905-21:10:40_glm-5.3-flash_vanilla_libero_spatial_task_t9_s4_r1/images_wrist_hi/image_wrist_hi_04.png
- [msg66 assistant 思考] The wrist view after the pick attempt: the bowl (patterned, yellow rim) is at the RIGHT EDGE of the frame, still sitting on the stove slab (visible with its yellow rim and pattern). The EEF drifted to the LEFT of the bowl — the black round thing top-left is the stove knob; the bowl is at right, NOT in the gripper. The gripper is NOT holding the bowl. The pick descended to the left of the bowl (pro
- [msg66 assistant 文本] Grasp missed — the bowl is still on the stove (right edge of wrist view); Pi0 descended left of it and grabbed air. In-episode recovery: re-localize the bowl from this wrist view, re-preposition lower/closer, re-pick.
- [msg66 assistant 调用 back_project] ```json
{"camera": "wrist", "col": 950, "row": 550, "step": 4}
```
- [msg67 tool 结果] {
  "camera": "wrist",
  "resolution": "high",
  "pixel": [
    550,
    950
  ],
  "world_xyz": [
    -0.2627,
    -0.1576,
    0.937
  ],
  "step": 4,
  "image_size": [
    1024,
    1024
  ],
  "source_artifact": "world_wrist_hi/world_wrist_hi_04.npy"
}
- [msg68 assistant 思考] Bowl still at (-0.263, -0.158, 0.937) — unmoved (matches previous localization (-0.271, -0.158)). Good, the bowl wasn't displaced by the failed grasp.

Now re-preposition lower and closer: move to (-0.263, -0.158, 1.06) — 12cm above the bowl rim (0.94). Slightly lower than the previous 1.12 pre-pick. Keep yaw 1.57 (move_to holds orientation... actually move_to holds the current orientation, yaw st
- [msg68 assistant 文本] Bowl unmoved at (-0.263, -0.158, 0.937). Re-prepositioning lower (z=1.06, 12cm above rim) with the same yaw:
- [msg68 assistant 调用 move_to] ```json
{"gripper": -1, "step_clip": 0.015, "xyz": [-0.263, -0.158, 1.06]}
```
- [msg69 tool 结果] {
  "step": 5,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.27111671681340815,
      -0.15747723688358717,
      1.057800490129741
    ],
    "robot0_eef_quat": [
      0.5546854343850953,
      0.822833464321568,
      -0.00288993083795637,
      0.12353463956856742
    ],
    "robot0_gripper_qpos": [
      0.03971139366649526,
      -0.04000662186306917
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
  "world_map": "world/world_05.npy",
  "wrist_world_map": "world_wrist/world_wrist_05.npy",
  "world_map_hi": "world_hi/wor
- [msg70 assistant 思考] EEF at (-0.271, -0.157, 1.058), yaw preserved, gripper open. Now re-issue pi0_pick. The memory says: "if +yaw grasp is not visually held, try the same yaw with a slightly lower/closer re-preposition rather than changing the plate placement first." Also prompt ladder: next rung could be the full task_language or a spatial qualifier. The first prompt "pick up the bowl on the stove" made Pi0 descend 
- [msg70 assistant 文本] Re-issuing the grasp from the lower, closer pre-position (same prompt per memory):
- [msg70 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 16, "prompt": "pick up the bowl on the stove"}
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
