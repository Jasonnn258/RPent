# N0 盲审卷宗:dossier_29(control-dependency audit)
- 失败族:FALSE_GRASP(node FALSE_GRASP)
- t0(窗口起始步)= step 4;tR(窗口结束步)= step 6
- task 3 / seed 6 / 长度层 S
- t0 eef ['0.015', '-0.226', '1.174'] grip [0.036406310117728734, -0.03691518688057538]
- tR eef ['0.046', '0.232', '0.933'] grip [0.002306561630847223, -0.0032286566528260613]
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
 "peak_lift_m": 0.0451890230178833,
 "min_gripper_opening": 0.004855042789131403,
 "final_gripper_opening": 0.07332149147987366,
 "libero_terminated": false,
 "diagnostics": {
  "start_eef_z": 1.1704,
  "peak_eef_z": 1.1957,
  "min_eef_z": 1.1484,
  "post_min_peak_z": 1.1936,
  "descent_m": 0.022,
  "post_min_ascent_m": 0.0452,
  "descent_done": false,
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
 "max_steps": 60,
 "step_clip": 0.01,
 "xyz": [
  0.02,
  -0.308,
  1.16
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.019999999552965164,
  -0.30799999833106995,
  1.159999966621399
 ],
 "final_eef_pos": [
  0.0207,
  -0.2963,
  1.1608
 ],
 "final_dist_m": 0.0118,
 "steps_used": 31,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 6
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
 "success": true,
 "chunks_used": 20,
 "max_chunks": 20,
 "peak_lift_m": 0.0,
 "min_gripper_opening": 0.004930539056658745,
 "final_gripper_opening": 0.005535218399018049,
 "libero_terminated": true,
 "diagnostics": {
  "start_eef_z": 1.1608,
  "peak_eef_z": 1.3362,
  "min_eef_z": 0.9327,
  "post_min_peak_z": 0.9327,
  "descent_m": 0.2281,
  "post_min_ascent_m": 0.0,
  "descent_done": true,
  "lift_thresh": 0.05,
  "gripper_closed_thresh": 0.06
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg35 assistant 思考] EEF at (0.0022, -0.3045, 1.1704) — x came 1.2cm short of 0.014 (tolerance) but y reached -0.3045. Good enough: the bowl center is at (0.014, -0.304); the eef is within ~1.2cm in x. That's within Pi0's grasp tolerance. Bowl surface z=1.134, eef at 1.170 → 3.6cm above bowl top. Good pre-grasp height.

Now pi0_pick with prompt "pick up the black patterned bowl on top of the cabinet", max_chunks=14. P
- [msg35 assistant 文本] Pre-grasp pose set (eef 3.6cm above bowl top, centered within ~1cm). Now the grasp — prompt with spatial qualifier per the suite memory, capped chunks.
- [msg35 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 14, "prompt": "pick up the black patterned bowl on top of the cabinet"}
```
- [msg36 tool 结果] {
  "step": 4,
  "task_language": "Pick the akita black bowl on the top of the cabinet and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.014563190890969949,
      -0.22622828673442005,
      1.173890675399236
    ],
    "robot0_eef_quat": [
      0.9894948606922624,
      0.020003931735938396,
      -0.06271238219658001,
      0.12871254988513273
    ],
    "robot0_gripper_qpos": [
      0.036406310117728734,
      -0.03691518688057538
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
  "world_map_h
- [msg38 assistant 思考] pi0_pick reports success:false: peak_lift 0.045 < 0.05 threshold, descent_done false, min_gripper_opening 0.0049 (it DID close tight at some point — 4.9mm opening!), but final_gripper_opening 0.073 (opened back up — the "fail by reopening" failure mode from memory!).

The eef moved from (0.0022, -0.3045, 1.1704) to (0.0146, -0.2262, 1.1739). The eef drifted +y by 8cm — possibly Pi0 grabbed then dr
- [msg38 assistant 文本] The pick closed to 4.9mm (touched the rim) but then reopened to 73mm — the exact "fail by reopening" mode from memory. Let me check the wrist view to see whether the bowl is still on the cabinet and how the scene now looks.
- [msg38 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260929-03:06:38_glm-5.3-flash_h1G_libero_spatial_task_t3_s6_r1/images_wrist_hi/image_wrist_hi_04.png"}
```
- [msg39 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260929-03:06:38_glm-5.3-flash_h1G_libero_spatial_task_t3_s6_r1/images_wrist_hi/image_wrist_hi_04.png
- [msg40 assistant 思考] The bowl is STILL on the cabinet (visible in the wrist view, lower-right), NOT held. The gripper drifted +y 8cm so now the bowl appears at the lower-right of the wrist image. The bowl is intact, upright, on the cabinet. Good — no damage.

The bowl in the wrist image: spans roughly cols 520-1024 (clipped at right edge), rows 360-860. Center ≈ (row 620, col 800)? It's clipped by the image edge. The 
- [msg40 assistant 文本] The bowl is still on the cabinet, upright, unharmed — the grasp failed by reopening exactly as the memory warned. I'll re-localize the bowl in this new wrist view, then re-position lower and retry with the full task language (memory's A1 fix).
- [msg40 assistant 调用 back_project] ```json
{"camera": "wrist", "col": 865, "resolution": "high", "row": 610, "step": 4}
```
- [msg41 tool 结果] {
  "camera": "wrist",
  "resolution": "high",
  "pixel": [
    610,
    865
  ],
  "world_xyz": [
    0.0409,
    -0.314,
    1.1416
  ],
  "step": 4,
  "image_size": [
    1024,
    1024
  ],
  "source_artifact": "world_wrist_hi/world_wrist_hi_04.npy"
}
- [msg42 assistant 思考] Hmm — the back-projected point is (0.041, -0.314, 1.142). But wait: the pixel (610, 865) is near the right edge of the bowl, which may be clipped. The bowl center should still be near (0.014, -0.304) as before, unless the pick nudged it. The z=1.1416 is consistent with the bowl top (~1.134-1.143). The x=0.041 vs earlier 0.014 — a 2.7cm difference. The pixel I picked might be off-center (right-of-c
- [msg42 assistant 文本] Bowl still at ≈(0.02, -0.31, top z≈1.134), unmoved and upright. Applying the memory's A1 fix: re-pre-position lower and slightly deeper, then retry with the full task-language prompt (which the memory says may even carry the bowl toward the plate — I'll take over after lift).
- [msg42 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.01, "xyz": [0.02, -0.308, 1.16]}
```
- [msg43 tool 结果] {
  "step": 5,
  "task_language": "Pick the akita black bowl on the top of the cabinet and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.020682794696575718,
      -0.2962746955241185,
      1.1608252545277302
    ],
    "robot0_eef_quat": [
      0.9886288007410436,
      0.021645254533098734,
      -0.06120958293260603,
      0.13563909561309345
    ],
    "robot0_gripper_qpos": [
      0.03922439732691097,
      -0.03990728543770743
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
  "world_map_hi
- [msg44 assistant 思考] EEF at (0.0207, -0.2963, 1.1608). Note: y stopped at -0.2963 despite target -0.308 — the y wall is real around -0.296/-0.30. Fine — 1cm from ideal. Now retry pi0_pick with the full task language, max_chunks=20.
- [msg44 assistant 文本] Lower pre-grasp set (y-wall stops it at -0.296, ~1cm shy — acceptable). Retry grasp with the full task-language prompt, extended chunks.
- [msg44 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 20, "prompt": "Pick the akita black bowl on the top of the cabinet and place it on the plate"}
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
