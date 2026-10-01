# N0 盲审卷宗:dossier_14(control-dependency audit)
- 失败族:RELEASE_PREDICATE_STALL(node RELEASE_PREDICATE_STALL)
- t0(窗口起始步)= step 10;tR(窗口结束步)= step 13
- task 9 / seed 18 / 长度层 M
- t0 eef ['-0.017', '0.206', '1.010'] grip [0.03965498950451851, -0.04000661276252692]
- tR eef ['0.106', '0.145', '0.975'] grip [0.03964338352612664, -0.040016700691538315]
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

### step 10
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
 "start_gripper_opening": 0.0043,
 "peak_gripper_opening": 0.0797,
 "final_gripper_opening": 0.0797,
 "libero_terminated": false
}
```
### step 11
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 40,
 "step_clip": 0.02,
 "xyz": [
  -0.017,
  0.206,
  1.12
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.017000000923871994,
  0.20600000023841858,
  1.1200000047683716
 ],
 "final_eef_pos": [
  -0.0177,
  0.2056,
  1.1117
 ],
 "final_dist_m": 0.0084,
 "steps_used": 22,
 "max_steps": 40,
 "libero_terminated": false
}
```
### step 12
```json
{
 "action": "move_to",
 "gripper": -1,
 "max_steps": 60,
 "step_clip": 0.02,
 "xyz": [
  -0.02,
  0.05,
  1.14
 ]
}
```
```json
{
 "name": "move_to",
 "target_xyz": [
  -0.019999999552965164,
  0.05000000074505806,
  1.1399999856948853
 ],
 "final_eef_pos": [
  -0.0202,
  0.0589,
  1.1399
 ],
 "final_dist_m": 0.0089,
 "steps_used": 31,
 "max_steps": 60,
 "libero_terminated": false
}
```
### step 13
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
 "chunks_used": 12,
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

- [msg49 assistant 思考] Correction applied: eef at [-0.0173, 0.2056, 1.0097] — bowl should now be over the plate center. Release with a long settle: release(max_steps=60).
- [msg49 assistant 文本] Bowl now over the plate center. Releasing with a long settle:
- [msg49 assistant 调用 release] ```json
{"max_steps": 60}
```
- [msg50 tool 结果] {
  "step": 10,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.017430300147568883,
      0.20649145962361093,
      1.0096412464799565
    ],
    "robot0_eef_quat": [
      0.697353259741101,
      0.7066617098216854,
      0.0037697715325596473,
      0.11963882239032474
    ],
    "robot0_gripper_qpos": [
      0.03965498950451851,
      -0.04000661276252692
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
- [msg52 assistant 思考] Release done (gripper opened to 0.0797), libero_terminated still false. R5 wants pi0_doubled for the final placement. But first, per recall cards: retreat the eef straight up and laterally clear, then re-check the predicate — the release may already be correct and just gated by eef proximity.

Then if still false, use pi0_doubled ("place the bowl on the plate") as the learned contact/finish skill 
- [msg52 assistant 文本] Released (gripper open, 0.0797) but predicate not yet fired. Per the retreat-clear rule: backing the eef straight up before judging:
- [msg52 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 40, "step_clip": 0.02, "xyz": [-0.017, 0.206, 1.12]}
```
- [msg53 tool 结果] {
  "step": 11,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.017685993270020253,
      0.20564010574244518,
      1.1116610697463454
    ],
    "robot0_eef_quat": [
      0.6974116898892255,
      0.706547669642787,
      0.00506606036820733,
      0.11992356048978212
    ],
    "robot0_gripper_qpos": [
      0.03974808594010336,
      -0.04000720137734969
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
  "world_map_hi": "world_hi/wo
- [msg54 assistant 思考] Still false after retreat. Let me look at the agentview hi-res to see where the bowl actually landed relative to the plate — maybe it fell beside the plate or is perched. Then decide: pi0_doubled finish (per R5) or low corrective push.
- [msg54 assistant 文本] Still false after retreat. Checking where the bowl actually landed:
- [msg54 assistant 调用 read_image] ```json
{"path": "/workspace/yjx/workspace/RPent/logs/ovpm_exp/20260923-01:17:44_glm-5.3-flash_g0D_libero_spatial_task_t9_s18_r1/images_cam_hi/image_cam_hi_11.png"}
```
- [msg55 tool 结果] /workspace/yjx/workspace/RPent/logs/ovpm_exp/20260923-01:17:44_glm-5.3-flash_g0D_libero_spatial_task_t9_s18_r1/images_cam_hi/image_cam_hi_11.png
- [msg56 assistant 思考] The bowl IS on the plate — visually it sits right on the red-ringed plate (bowl base on the plate, well centered; the plate's red rings visible around the bowl). The stove is empty (black burner disc visible). The cabinet bowl remains the distractor. The gripper has retreated up.

But libero_terminated is still false. Why? Possibilities:
1. The predicate requires the eef further away (card 1: retr
- [msg56 assistant 文本] The bowl is visually seated on the plate — but the predicate hasn't fired. Retreating laterally clear of the placement before concluding anything:
- [msg56 assistant 调用 move_to] ```json
{"gripper": -1, "max_steps": 60, "step_clip": 0.02, "xyz": [-0.02, 0.05, 1.14]}
```
- [msg57 tool 结果] {
  "step": 12,
  "task_language": "Pick the akita black bowl on the stove and place it on the plate",
  "state": {
    "robot0_eef_pos": [
      -0.02021817221036776,
      0.058884440433727744,
      1.1398690765859114
    ],
    "robot0_eef_quat": [
      0.6974716010181321,
      0.7065194273836659,
      0.0040368176220886495,
      0.11978050177781514
    ],
    "robot0_gripper_qpos": [
      0.039797531514287214,
      -0.04000721587115039
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
  "world_map_hi": "world_h
- [msg59 assistant 思考] Predicate still false even after full retreat (up + lateral). The bowl looks visually ON the plate. Per R5, the sanctioned recovery chain ends with pi0_doubled — a learned contact placement that has solved this exact stall in the s0 recipe era ("Use learned contact to finish near placements" / "low-pose-settle-regrasp" patterns). The RULE R5 recovery says: use pi0_doubled for the final placement i
- [msg59 assistant 文本] Predicate still false despite full retreat — the bowl looks seated but likely isn't satisfying the On() geometry. Executing the R5-prescribed finisher: `pi0_doubled` learned placement on the plate:
- [msg59 assistant 调用 pi0_doubled] ```json
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
