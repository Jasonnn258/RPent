# N0 盲审卷宗:dossier_43(control-dependency audit)
- 失败族:MOVE_CONTACT_STALL(node CONTACT_STALL)
- t0(窗口起始步)= step 12;tR(窗口结束步)= step 14
- task 9 / seed 1 / 长度层 S
- t0 eef ['0.002', '0.038', '0.942'] grip [0.02399291764476254, -0.024384758807385203]
- tR eef ['0.025', '0.205', '0.930'] grip [0.01646258515130579, -0.016742805525980953]
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
### step 13
```json
{
 "action": "move_to",
 "gripper": -1,
 "step_clip": 0.02,
 "xyz": [
  0.058,
  0.199,
  1.03
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  0.057999998331069946,
  0.19900000095367432,
  1.0299999713897705
 ],
 "final_eef_pos": [
  0.0573,
  0.1898,
  1.0294
 ],
 "final_dist_m": 0.0092,
 "steps_used": 32,
 "max_steps": 80,
 "libero_terminated": false
}
```
### step 14
```json
{
 "action": "pi0_pick",
 "gripper_closed_thresh": 0.06,
 "lift_thresh": 0.03,
 "max_chunks": 8,
 "prompt": "pick up the bowl on the plate"
}
```
```json
{
 "name": "pick",
 "instruction": "pick up the bowl on the plate",
 "success": true,
 "chunks_used": 4,
 "max_chunks": 8,
 "peak_lift_m": 0.0033375024795532227,
 "min_gripper_opening": 0.033205389976501465,
 "final_gripper_opening": 0.033205389976501465,
 "libero_terminated": true,
 "diagnostics": {
  "start_eef_z": 1.0294,
  "peak_eef_z": 1.0294,
  "min_eef_z": 0.9268,
  "post_min_peak_z": 0.9302,
  "descent_m": 0.1025,
  "post_min_ascent_m": 0.0033,
  "descent_done": true,
  "lift_thresh": 0.03,
  "gripper_closed_thresh": 0.06
 }
}
```

## 窗口内 transcript 消息原文(发射 t0 的消息至发射 tR 的消息)
(思考块截 400 字,其余原文;tool 结果截 800 字;tR 自身 result 不在窗口内)

- [msg59 assistant 思考] EEF is now clear ([-0.054, 0.059, 1.096] — well away from the plate). Still libero_terminated: false. So the placement, while visually good, hasn't fired.

Now per R5: use pi0_doubled for the final placement — the double-stage learned contact. Prompt: "place the bowl on the plate". This will run Pi0 closed-loop; if it regrasps and re-places the bowl properly (or nudges it into the predicate zone),
- [msg59 assistant 文本] EEF is fully clear and the predicate is still false — the visual placement isn't satisfying the checker. Per the R5 recovery for t9, invoking `pi0_doubled` as the double-stage placement skill:
- [msg59 assistant 调用 pi0_doubled] ```json
{"max_chunks": 20, "prompt": "place the bowl on the plate"}
```
- [msg60 tool 结果] {
  "step": 12,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.0018308679710430861,
      0.03845728779186099,
      0.9422284556261817
    ],
    "robot0_eef_quat": [
      0.6910841127363406,
      0.6985863377784257,
      -0.04328600928144291,
      0.18029475642191603
    ],
    "robot0_gripper_qpos": [
      0.02399291764476254,
      -0.024384758807385203
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
  "world_map_hi": "world_hi
- [msg62 assistant 思考] pi0_doubled ran 20 chunks and did NOT terminate. The eef moved to [0.002, 0.038, 0.942] — it descended toward the bowl area (z 0.942, near the cookies box region x~0.0, y~0.04?? that's near the COOKIES box, not the plate!). The gripper qpos is 0.024 (partially open, mid-closure?). It may have nudged something.

Wait — eef at [0.002, 0.038, 0.942]: the cookies box is around [0.0, 0.05]. Hmm, Pi0 ma
- [msg62 assistant 文本] pi0_doubled didn't terminate and the eef ended near the cookies box area — I need to check whether the bowl on the plate survived this intervention:
- [msg62 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-11:06:19_glm-5.3-flash_memO2_libero_spatial_task_t9_s1_r1/images_cam_hi/image_cam_hi_12.png"}
```
- [msg63 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260918-11:06:19_glm-5.3-flash_memO2_libero_spatial_task_t9_s1_r1/images_cam_hi/image_cam_hi_12.png
- [msg64 assistant 思考] Interesting! The image shows:
- The bowl is STILL ON THE PLATE (bottom right) — it survived pi0_doubled, looks well-seated, plate red ring visible around it.
- The gripper is now hovering near the cookies box (it descended toward the cookies box, gripper partially open at 0.024), as if trying to grasp the cookies box — Pi0 misgrounded ("the bowl" → it went for... hmm, or it tried to regrasp the bo
- [msg64 assistant 文本] The bowl survived pi0_doubled and still sits on the plate — but the predicate won't fire on a gentle perch. Key insight from the s0 winning recipe: their release happened at eef z≈1.015-1.026 (~5-6cm above the plate surface), i.e. they released **high and let the bowl drop-settle** onto the plate, whereas I released at a soft stall (z=0.967). The checker likely needs firm settled contact. I'll regrasp briefly and re-release from height — the s0-proven geometry.

Step 1 — reposition over the bowl:
- [msg64 assistant 调用 move_to] ```json
{"gripper": -1, "step_clip": 0.02, "xyz": [0.058, 0.199, 1.03]}
```
- [msg65 tool 结果] {
  "step": 13,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      0.05726631046193157,
      0.18983834075126066,
      1.0293835196075287
    ],
    "robot0_eef_quat": [
      0.6922610087418972,
      0.697151313292544,
      -0.039815064214303156,
      0.18212496482289867
    ],
    "robot0_gripper_qpos": [
      0.03934874797539714,
      -0.03981520714189346
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
  "world_map_hi": "world_hi/wo
- [msg66 assistant 思考] Positioned over the bowl at z=1.03 (bowl center at plate ≈ [0.058, 0.199]). Now the short regrasp: pi0_pick "pick up the bowl on the plate", max_chunks 8, lift_thresh 0.03, gripper_closed_thresh 0.06. Note the current yaw drifted (quat suggests yaw ~0.36 rad now after pi0_doubled, not 1.57) — Pi0 will handle its own approach; fine for a regrasp.
- [msg66 assistant 文本] Step 2 — short regrasp of the bowl on the plate:
- [msg66 assistant 调用 pi0_pick] ```json
{"gripper_closed_thresh": 0.06, "lift_thresh": 0.03, "max_chunks": 8, "prompt": "pick up the bowl on the plate"}
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
