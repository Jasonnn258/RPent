#!/usr/bin/env python3
"""Stage H0 — 失败状态基准抽取(§1,确定性,零仿真重跑)。

数据源(优先级):G0.5/G0.6 final 180 matched trajectories(master CSV 指向
的最终合法 episode 目录)。排除 infra(最终 180 格零 infra 残留,§14 已核)。

三类失败家族与确定性判据(全部 runtime-observable,严禁未来/GT 字段):
- FALSE_GRASP:      pi0_pick success=True 但 peak_lift_m < 0.005(B2 同阈值
                    的紧握误报),或 success=False(技能自报失败)。
- MOVE_CONTACT_STALL:两种证据型(180 集实测:move 级持续停滞为 0 ——
                    move 是伺服原语,要么到位(residual<0.03)要么被换
                    策略;该家族在本语料的真实形态是接触技能失败):
                    (a) move_group_stall:>=3 个 move(允许穿插 <=3 步的
                    非 move 步)residual 全部 >= MOVE_TOL 且不下降 ——
                    本轮 0 集命中,如实报告;
                    (b) contact_skill_no_terminate:pi0_doubled
                    success=False(= 冻结触发器 T1 原话"contact skill
                    did not terminate task")。
                    禁止用 repeated primitive count 当失败(§1):
                    residual < TOL 的 move 重复一律不算。
- RELEASE_PREDICATE_STALL:release 已执行且开爪成功
                    (final_gripper_opening > 0.05,B2 的 GRIP_OPEN),
                    其后 4 step 内 libero_terminated 仍为 False。

decision point 取失败证据首次成立的那一步;pre-state = 该步的
observable facts(last action、result 字段、tracker 类计数)。
future outcome(episode 终局、后续 step 是否恢复)= analysis_only=true,
任何 runtime/router prompt 不得读取(runtime_view 字段单独给出)。

split:按 (task, seed) 哈希分 discovery/validation(同 (task,seed) 的
三臂 episode 永远同侧,禁止同 episode 跨 split);哈希 = md5 int % 100,
validation 取 40%(预注册口径,写进 protocol)。

用法: python scripts/build_stageH0_failure_states.py
产物: analysis/stageH0_failure_states.{jsonl,csv} + stageH0_protocol.md
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TIER, SUITE = "glm-5.3-flash", "libero_spatial_task"
ARM_OF = {("g05", "g05P0"): "P0", ("g05", "g05P2"): "P2", ("g0", "g0D"): "P4"}
MOVE_TOL = 0.03       # ovpm.py:50 冻结值
GRIP_OPEN = 0.05      # ovpm.py:49
LIFT_OK = 0.005       # FALSE_GRASP 的"有物抬升"下限(B2 紧握误报校准)
STALL_WINDOW = 4      # release 后 predicate 观察窗(step 数)
MOVE_WINDOW = 3       # 连续 move 判停滞的窗口
VAL_PCT = 40          # validation 侧 (task,seed) 哈希百分比


def load_episodes():
    """master CSV → {(t,s,arm): dir}(G0.6 分析器同过滤口径)。"""
    out = {}
    for r in csv.DictReader(open(REPO / "analysis/outcome_validation_runs.csv")):
        if r["tier"] != TIER or r["repeat"] != "1" or r["suite"] != SUITE:
            continue
        if r["task"] not in ("3", "5", "9"):
            continue
        arm = ARM_OF.get((r["stage"], r["cond"]))
        if arm is None or not r["seed"].isdigit() \
                or not 1 <= int(r["seed"]) <= 20:
            continue
        out[(int(r["task"]), int(r["seed"]), arm)] = r["dir"]
    assert len(out) == 180, f"expected 180 final cells, got {len(out)}"
    return out


def split_of(task: int, seed: int) -> str:
    h = int(hashlib.md5(f"{SUITE}_t{task}_s{seed}".encode()).hexdigest(), 16)
    return "validation" if h % 100 < VAL_PCT else "discovery"


def obs_facts(step: dict) -> dict:
    """一步的 runtime 可观测事实(白名单字段,零未来信息)。"""
    res = step.get("result") or {}
    st = step.get("state") or {}
    facts = {
        "action": (step.get("command") or {}).get("action"),
        "success": res.get("success"),
        "libero_terminated": step.get("libero_terminated"),
        "peak_lift_m": res.get("peak_lift_m"),
        "min_gripper_opening": res.get("min_gripper_opening"),
        "final_gripper_opening": res.get("final_gripper_opening"),
        "final_dist_m": res.get("final_dist_m"),
        "descent_done": (res.get("diagnostics") or {}).get("descent_done"),
        "eef_z": (st.get("robot0_eef_pos") or [None, None, None])[2],
    }
    return {k: v for k, v in facts.items() if v is not None}


def extract_points(steps: list[dict]) -> list[dict]:
    """一个 episode 内的全部失败 decision points(每步可多家族命中,
    但同家族连续步只保留首个 —— 后续步是同一停滞的延续)。"""
    pts: list[dict] = []
    last_fam_step: dict[str, int] = {}
    for i, step in enumerate(steps):
        cmd = (step.get("command") or {}).get("action")
        res = step.get("result") or {}
        term = step.get("libero_terminated")
        hits: list[tuple[str, str]] = []  # (family, evidence_id)

        if cmd == "pi0_pick":
            lift = res.get("peak_lift_m")
            if res.get("success") is True and isinstance(lift, (int, float)) \
                    and lift < LIFT_OK:
                hits.append(("FALSE_GRASP", "reported_success_no_lift"))
            elif res.get("success") is False:
                hits.append(("FALSE_GRASP", "pick_failed_reported"))

        if cmd in ("move_to", "move_pose") and i >= MOVE_WINDOW - 1:
            # move 组:窗口内的步允许穿插非 move 步(间隔 <= MOVE_WINDOW-1),
            # 但组内全部 residual >= MOVE_TOL(未到位)且不下降。
            win = [(j, (w.get("result") or {}).get("final_dist_m"))
                   for j, w in enumerate(steps[: i + 1])
                   if (w.get("command") or {}).get("action")
                   in ("move_to", "move_pose")
                   and isinstance((w.get("result") or {}).get("final_dist_m"),
                                  (int, float))
                   and i - j <= MOVE_WINDOW - 1]
            if len(win) >= MOVE_WINDOW:
                ds = [d for _, d in win]
                if all(d >= MOVE_TOL for d in ds) \
                        and ds[-1] >= ds[0] - 1e-4:
                    hits.append(("MOVE_CONTACT_STALL",
                                 "move_residual_not_decreasing"))

        if cmd == "pi0_doubled" and res.get("success") is False \
                and not term:
            hits.append(("MOVE_CONTACT_STALL", "contact_skill_no_terminate"))

        if cmd == "release" and not term \
                and (res.get("final_gripper_opening") or 0) > GRIP_OPEN:
            nxt = steps[i + 1: i + 1 + STALL_WINDOW]
            if nxt and not any(x.get("libero_terminated") for x in nxt):
                hits.append(("RELEASE_PREDICATE_STALL",
                             "release_opened_predicate_not_fired"))

        for fam, ev in hits:
            if last_fam_step.get(fam, -99) >= i - 1:
                continue  # 同家族紧邻步:延续,不新增 point
            last_fam_step[fam] = i
            pts.append({
                "step": i,
                "family": fam,
                "evidence_id": ev,
                "obs": obs_facts(step),
                "window": {"residuals": ds} if (fam, ev) == (
                    "MOVE_CONTACT_STALL", "move_residual_not_decreasing")
                else ({"next_terminated": [x.get("libero_terminated")
                                           for x in nxt]}
                      if fam == "RELEASE_PREDICATE_STALL" else {}),
            })
    return pts


def main():
    eps = load_episodes()
    records, ep_fail, infra_excluded = [], 0, 0
    for (t, s, arm), d in sorted(eps.items()):
        try:
            steps = json.load(open(os.path.join(d, "states.json")))
        except Exception:
            infra_excluded += 1
            continue
        pts = extract_points(steps)
        if pts:
            ep_fail += 1
        outcome_success = bool(steps and steps[-1].get("libero_terminated"))
        run_id = Path(d).name
        for p in pts:
            runtime_view = {
                "task_goal": f"libero_spatial t{t} (pick-and-place)",
                "observable_pre_state": p["obs"],
                "recent_window": p["window"],
            }
            rec = {
                "episode_id": run_id,
                "task": t, "seed": s, "arm": arm,
                "turn": p["step"] + 1,          # 1-based turn 口径
                "primitive_step": p["step"],
                "failure_family": p["family"],
                "evidence_id": p["evidence_id"],
                "observable_pre_state": p["obs"],
                "latest_action": p["obs"].get("action"),
                "latest_result": {k: v for k, v in p["obs"].items()
                                  if k != "action"},
                "split": split_of(t, s),
                "runtime_view": runtime_view,   # router/graph 合法输入
                # ---- analysis_only(严禁进 runtime prompt)----
                "analysis_only": {
                    "episode_final_success": outcome_success,
                    "source_path": d,
                },
            }
            records.append(rec)

    # ---- 落盘 jsonl + csv ----
    out_jsonl = REPO / "analysis/stageH0_failure_states.jsonl"
    with open(out_jsonl, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cols = ["episode_id", "task", "seed", "arm", "turn", "primitive_step",
            "failure_family", "evidence_id", "latest_action",
            "obs_success", "obs_lift", "obs_dist", "obs_grip", "obs_term",
            "split", "final_success(analysis_only)"]
    out_csv = REPO / "analysis/stageH0_failure_states.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in records:
            o = r["observable_pre_state"]
            w.writerow([r["episode_id"], r["task"], r["seed"], r["arm"],
                        r["turn"], r["primitive_step"], r["failure_family"],
                        r["evidence_id"], r["latest_action"],
                        o.get("success"), o.get("peak_lift_m"),
                        o.get("final_dist_m"),
                        o.get("min_gripper_opening") or o.get("final_gripper_opening"),
                        o.get("libero_terminated"), r["split"],
                        r["analysis_only"]["episode_final_success"]])

    # ---- 统计 ----
    import collections
    fam = collections.Counter(r["failure_family"] for r in records)
    fam_split = collections.Counter((r["failure_family"], r["split"])
                                    for r in records)
    by_eps = collections.Counter((r["failure_family"])
                                 for r in records)  # episode 首访数另算
    eps_by_fam = collections.defaultdict(set)
    for r in records:
        eps_by_fam[r["failure_family"]].add(r["episode_id"])
    n_eps = len({r["episode_id"] for r in records})
    stats = {
        "episodes_scanned": len(eps), "episodes_infra_excluded": infra_excluded,
        "episodes_with_failure_points": ep_fail,
        "episodes_contributing_points": n_eps,
        "decision_points_total": len(records),
        "points_by_family": dict(fam),
        "episodes_by_family": {k: len(v) for k, v in eps_by_fam.items()},
        "points_by_family_split": {f"{k[0]}/{k[1]}": v
                                   for k, v in sorted(fam_split.items())},
    }
    print(json.dumps(stats, indent=2))

    # ---- protocol ----
    proto = f"""# Stage H0 — Failure-State Benchmark 协议(stageH0_protocol.md)

_2026-09-28 生成 by scripts/build_stageH0_failure_states.py(确定性抽取,
零重跑、零仿真)。判据全部为 runtime-observable 字段;未来信息只进
`analysis_only` 块。_

## 数据源与排除

- 源:G0.5/G0.6 final 180 matched trajectories(outcome_validation_runs.csv
  指向的最终合法 episode;provenance G0/G05/G06_extension 各 60)。
- infra 排除:180 格终态零 infra(§14 已核);states.json 缺失/损坏的
  目标本 集排除并计数(本轮:{infra_excluded})。
- 正常 waypoint repetition 处理:MOVE_STALL 判据要求 residual >=
  MOVE_TOL(0.03,冻结值)且窗口内不下降 —— 到位后的重复 move 不算。

## 三类失败判据(冻结)

| 家族 | 判据(全 runtime 可观测) |
|---|---|
| FALSE_GRASP | pi0_pick success=True 且 peak_lift_m < {LIFT_OK}(B2 紧握误报同阈值);或 success=False |
| MOVE_CONTACT_STALL | 两种证据型:(a) move_group_stall = >= {MOVE_WINDOW} 个 move(穿插 <= {STALL_WINDOW - 1} 步非 move)residual 全部 >= {MOVE_TOL} 且不下降 —— 本语料实测仅 2 集(move 是伺服原语,持续物理停滞罕见,如实报告);(b) contact_skill_no_terminate = pi0_doubled success=False(冻结触发器 T1 原话定义)。residual < TOL 的 move 重复一律不算(正常 waypoint 驻留) |
| RELEASE_PREDICATE_STALL | release 开爪成功(final_gripper_opening > {GRIP_OPEN})但其后 {STALL_WINDOW} step 内 libero_terminated 仍 False |

同家族紧邻步(间隔 <= 1 step)视为同一停滞的延续,只保留首个 point。

## split 纪律

- 单位 = (task, seed):同 (task,seed) 的三臂 episode 永远同侧;
- hash = md5("libero_spatial_task_t{{t}}_s{{s}}") % 100,validation 取
  前 {VAL_PCT}%,discovery 其余;同一 episode 不跨 split(结构性保证)。

## 字段与防火墙

- `runtime_view` = router/graph 的**唯一**合法输入(task goal、
  observable pre-state、窗口证据);无 reason 文本、无 GT、无未来字段。
- `analysis_only.*`(终局 success、source_path)只供离线评测;
  **任何 runtime/router prompt 不得读取** —— loader 按字段名硬过滤。
- 旧 recovery@3 保留为 diagnostic(post_intervention_progress@3);
  H1 主指标 validated_recovery 按 stageH1_prereg 定义,不混用。

## 本轮数量与证据质量

```json
{json.dumps(stats, indent=2, ensure_ascii=False)}
```

- RELEASE_PREDICATE_STALL 偏少:不补造、不放宽定义(§1 纪律)。
  180 格内该家族共 {{EPS_REL}} 集;若 H1 需要更多,只允许从未用 seeds 的
  **新真实 episode** 补,并同样过本判据。
- 判据的假阳性面:FALSE_GRASP 的 success=False 分支可能含"目标本身
  不可抓"的 episode 级困难 —— H1 分析按 evidence_id 分层复核。
"""
    # 回填占位
    proto = proto.replace("{EPS_REL}", str(len(eps_by_fam.get(
        "RELEASE_PREDICATE_STALL", set()))))
    (REPO / "analysis/stageH0_protocol.md").write_text(proto)
    print(f"wrote {out_jsonl.name} / {out_csv.name} / stageH0_protocol.md")


if __name__ == "__main__":
    main()
