#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage O §6/§10 — O-B confirmatory 能力阶梯(O0-O4,唯一 confirmatory runner)。

规范:analysis/stageO_prereg.md §5(双契约)/§6(arms)/§7(预算)/§9
(RECOVERY_PRESENT)/§10(sequential ladder)/§11(REALIGNMENT_FIRST)。

执行序(每 snapshot,冻结):
  O0(N1 O-policy 逐字移植,K_ROLLOUT 次)→ O1(最后一条 Pi0.5 命令逐字重采,
  16 次)→ [O1 达标且不在 25% sanity 子集 → 停,标签已定] →
  O2(oracle conditioning,reference 可用时)→ O3(frozen sequence,同)→
  O4(planner 续跑;boot-per-rollout 保证 states.json 只含本 rollout 重放步)。

产物:analysis/stageO_rollouts.csv / stageO_reentry_results.csv /
stageO_arm_transitions.jsonl(§22 turn 记录 + 相对 O3 序列首次偏离)。

infra 纪律(§12):boot 级重试 ≤3 → INFRA_ABORT 行;rollout 级原语异常
重试该 rollout ≤3 → INFRA_ABORT 行(保留在 CSV,分析层过滤)。

用法:
  nohup python scripts/stageO_ladder.py --gpu 0 --workers 2 \
      >> /workspace/yjx/tmp/stageO_ladder.log 2>&1 &
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import stageO_rt as rt          # 共享运行时/契约/守卫
import stageN1_runner as n1     # O0:N1 O-policy 逐字移植(只复用定义,零改动)
import ovpm_exp as ox           # 只用 pg.preflight(锁 + 资源检查)

MANI = REPO / "analysis/stageO_split_manifest.csv"
REFJ = REPO / "analysis/stageO_reference_traces.jsonl"
CALIB = REPO / "analysis/stageO_calibration.md"
ROLL_CSV = REPO / "analysis/stageO_rollouts.csv"
REENT_CSV = REPO / "analysis/stageO_reentry_results.csv"
TRANS_JL = REPO / "analysis/stageO_arm_transitions.jsonl"
LOG_ROOT = REPO / "logs/stageO_ladder"

SANITY_SEED = 20261002       # §10:O1 达标后 25% sanity 子集的冻结 seed
O12_SAMPLES = 16             # §6:O1/O2 N_MAX
O0_WALL_MAX = 600.0          # §7 表
O12_WALL_MAX = 300.0
MAX_INFRA_RETRY = 3

ROLL_COLS = [
    "snapshot_id", "family", "procedure", "task", "seed", "t0", "arm",
    "rollout_idx", "k_rollout", "n_expected", "contract_met",
    "contract_at_step", "check_success", "terminated", "n_prims", "n_pi05",
    "n_turns", "wall_s", "budget_exhausted", "agent_error", "end_reason",
    "first_action", "realignment_first", "oracle_source_step", "seq_len",
    "diverged_at", "infra_abort", "note",
]
REENT_COLS = [
    "snapshot_id", "arm", "rollout_idx", "re1_found", "re1_score",
    "re2_pose_legal", "re3_config_valid", "static_pass", "probe_ran",
    "probe_skill", "probe_verified", "reentry", "note",
]

WRITE_LOCK = threading.Lock()


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] {msg}", flush=True)


# ---- 输入装载 ---------------------------------------------------------------
def read_manifest() -> list[dict]:
    lines = [l for l in open(MANI, encoding="utf-8") if not l.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("".join(lines))))
    assert rows, "stageO_split_manifest.csv 无数据行"
    return rows


def read_k_rollout() -> int:
    m = re.search(r"K_ROLLOUT\s*=\s*(\d+)", CALIB.read_text(encoding="utf-8"))
    assert m, f"{CALIB} 缺 K_ROLLOUT 冻结行(附录 B 未回填?)"
    return int(m.group(1))


def load_references() -> dict[str, dict | None]:
    """{snapshot_id: 成功 attempt 记录 | None(REFERENCE_UNAVAILABLE)}。

    行序即写入序;快照以最后一个 attempt_idx==1 起的段为准(reference
    原子写盘,正常不会出现多段;防御式取末段成功行)。
    """
    refs: dict[str, dict | None] = {}
    if not REFJ.exists():
        return refs
    for line in open(REFJ, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        sid = d.get("snapshot_id")
        if sid is None:
            continue
        if d.get("attempt_idx") == 1:
            refs[sid] = None          # 新段开始,先置空
        if (d.get("contract_met") or d.get("check_success")) \
                and not d.get("infra_attempt"):
            if refs.get(sid) is None:
                refs[sid] = d         # 段内首个成功 attempt = oracle
    return refs


# ---- reference 抽取(O2 conditioning / O3 序列)-----------------------------
def ref_domain(rec: dict) -> list[dict]:
    """成功点(含达成动作)之前的动作步域:steps[:contract_at_step] 或全量。"""
    k = rec.get("contract_at_step")
    steps = rec.get("steps") or []
    return steps[:k] if k else steps


def ref_action_seq(rec: dict) -> list[tuple[str, dict]]:
    """O3 冻结序列 = 域内全部动作步 (action, kwargs) 原文(含 error 结果步;
    skipped 只出现在 latch 之后,域内天然不含)。"""
    return [(e["action"], e["kwargs"]) for e in ref_domain(rec)
            if e.get("action") and not (e.get("result") or {}).get("skipped")]


def ref_oracle_conditioning(rec: dict, fam_action: str) -> dict | None:
    """O2 oracle:域内第一条同族 pi0 调用;无同族 → 第一条 pi0(记 fallback)。"""
    dom = ref_domain(rec)
    for e in dom:
        if e.get("action") == fam_action:
            return {"action": e["action"], "kwargs": e["kwargs"],
                    "step": dom.index(e) + 1, "fallback": False}
    for i, e in enumerate(dom):
        if e.get("action") in rt.PI05_TOOLS:
            return {"action": e["action"], "kwargs": e["kwargs"],
                    "step": i + 1, "fallback": True}
    return None


def oracle_first_turn(rec: dict, action: str, prompt: str | None):
    """oracle 信息在 reference transcript 中的首次出现 turn(§6 O2 记录项)。"""
    if not prompt:
        return None
    for t in rec.get("turns") or []:
        if t.get("next_skill") != action:
            continue
        p = str((t.get("skill_args_excerpt") or {}).get("prompt", ""))
        if prompt[:40] in p or p[:40] in prompt:
            return t.get("turn_idx")
    return None


# ---- §11 REALIGNMENT_FIRST ---------------------------------------------------
def fail_target_of(steps: list[dict], t0: int, eef0: list[float]) -> list[float]:
    """失败技能目标:t0 命令 xyz → t0 result.target_xyz → eef0(冻结操作化)。"""
    by = {s.get("step_idx"): s for s in steps}
    s0 = by.get(t0) or {}
    cmd = s0.get("command") or {}
    xyz = cmd.get("xyz") or cmd.get("target_xyz")
    if isinstance(xyz, (list, tuple)) and len(xyz) == 3:
        return [float(c) for c in xyz]
    rxyz = (s0.get("result") or {}).get("target_xyz")
    if isinstance(rxyz, (list, tuple)) and len(rxyz) == 3:
        return [float(c) for c in rxyz]
    return list(eef0)


def realignment_first(first_action: str | None, first_kwargs: dict | None,
                      fail_target: list[float], eef0: list[float]) -> str:
    if first_action in ("rotate_wrist", "rotate_pitch"):
        return "REALIGNMENT_FIRST"
    if first_action == "move_to":
        xyz = (first_kwargs or {}).get("xyz")
        if isinstance(xyz, (list, tuple)) and len(xyz) == 3:
            d3 = math.dist([float(c) for c in xyz], fail_target)
            if d3 >= 0.05 or float(xyz[2]) >= eef0[2] + 0.05:
                return "REALIGNMENT_FIRST"
    return "DIRECT_COMPLETION"


# ---- REENTRY 测量(§5.2)------------------------------------------------------
def reentry_row(ctx: dict, snap: dict, steps: list[dict],
                final: dict, arm: str, ri: int) -> dict:
    """rollout 终态(RE1/RE2/RE3)→ 全过才跑动态 probe;返回 REENT 行。"""
    family = snap["family"]
    t0i = int(snap["t0"])
    prompt = rt.t0_prompt(family, steps, t0i)
    row = dict.fromkeys(REENT_COLS, "")
    row.update({"snapshot_id": snap["snapshot_id"], "arm": arm,
                "rollout_idx": ri, "probe_ran": False,
                "probe_verified": False, "reentry": False})
    if not prompt:
        row["note"] = "no_target_prompt"
        row.update({"static_pass": False})
        return row
    seg = rt.seg_probe(ctx["prims"], prompt)
    st = rt.reentry_static(final, ctx["base"], ctx["target"])
    row.update({"re1_found": seg["found"], "re1_score": seg["score"],
                "re2_pose_legal": st["RE2_pose_legal"],
                "re3_config_valid": st["RE3_config_valid"]})
    row["static_pass"] = bool(seg["usable"] and st["RE2_pose_legal"]
                              and st["RE3_config_valid"])
    if not row["static_pass"]:
        return row
    # 动态层:固定 nominal probe(episode 自身 prefix 条件,≤3 原语 = 单技能)
    skill = "pi0_pick" if family == "FALSE_GRASP" else "pi0_doubled"
    row["probe_ran"] = True
    row["probe_skill"] = skill
    try:
        ctx["toolkit"]._step(skill, prompt=prompt)
        ares = tail_result(ctx)
        cur = rt.measure(ctx["env"])
        ok = rt.task_recovery(family, cur, ctx["base"], ctx["target"],
                              action_result=ares)
        row["probe_verified"] = bool(ok)
    except Exception as exc:
        row["note"] = f"probe_exc {type(exc).__name__}"
        return row
    row["reentry"] = bool(row["probe_verified"])
    return row


def tail_result(ctx: dict) -> dict:
    sj = json.load(open(ctx["outdir"] / "states.json"))
    return (sj[-1] or {}).get("result") or {}


# ---- 写盘 -------------------------------------------------------------------
class Sink:
    """三产物文件的线程安全追加(CSV 头自动补;断点续跑读已有行)。"""

    def __init__(self):
        new = not ROLL_CSV.exists()
        self.f1 = open(ROLL_CSV, "a", newline="", encoding="utf-8")
        self.w1 = csv.DictWriter(self.f1, fieldnames=ROLL_COLS)
        self.f2 = open(REENT_CSV, "a", newline="", encoding="utf-8")
        self.w2 = csv.DictWriter(self.f2, fieldnames=REENT_COLS)
        if new:
            self.w1.writeheader()
            self.w2.writeheader()
        self.f3 = open(TRANS_JL, "a", encoding="utf-8")

    def rollout(self, row: dict):
        with WRITE_LOCK:
            self.w1.writerow(row)
            self.f1.flush()

    def reentry(self, row: dict):
        with WRITE_LOCK:
            self.w2.writerow(row)
            self.f2.flush()

    def transition(self, obj: dict):
        with WRITE_LOCK:
            self.f3.write(json.dumps(obj, ensure_ascii=False, default=str)
                          + "\n")
            self.f3.flush()


def done_rollouts() -> dict[tuple[str, str], set[int]]:
    """已落盘 (snapshot, arm) → rollout_idx 集合(INFRA_ABORT 行视为已终态)。"""
    out: dict[tuple[str, str], set[int]] = {}
    if not ROLL_CSV.exists():
        return out
    lines = [l for l in open(ROLL_CSV, encoding="utf-8") if not l.startswith("#")]
    for r in csv.DictReader(io.StringIO("".join(lines))):
        key = (r["snapshot_id"], r["arm"])
        try:
            out.setdefault(key, set()).add(int(r["rollout_idx"]))
        except (TypeError, ValueError):
            continue
    return out


def recovery_present(flags: list[bool]) -> bool:
    """§9 冻结:successes ≥ max(2, ceil(0.25×n)) 且 rate ≥ 25%。"""
    n = len(flags)
    s = sum(1 for f in flags if f)
    return n > 0 and s >= max(2, math.ceil(0.25 * n)) and s / n >= 0.25


# ---- 各臂执行器 --------------------------------------------------------------
def boot_arm(snap: dict, gpu: int, shared_kwargs: dict, tag: str):
    """boot + manifest hash 断言;≤3 次重试,败则 None。"""
    for attempt in range(1, MAX_INFRA_RETRY + 1):
        try:
            outdir = LOG_ROOT / (
                f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{tag}")
            ctx = rt.boot_snapshot(snap, gpu, shared_kwargs, outdir,
                                   note=tag)
            if snap.get("state_sha16") and \
                    ctx["state_hash"] != snap["state_sha16"]:
                raise rt.InfraError(
                    f"state hash mismatch {ctx['state_hash']} != "
                    f"{snap['state_sha16']}")
            return ctx
        except Exception as exc:
            log(f"    boot INFRA({attempt}/{MAX_INFRA_RETRY}) {tag}: "
                f"{type(exc).__name__}: {str(exc)[:120]}")
    return None


def stop_ctx(ctx):
    for d in (ctx.get("daemons") or []):
        try:
            d.stop()
        except Exception:
            pass


def base_row(snap: dict, arm: str, ri: int, K: int, n_exp: int) -> dict:
    row = dict.fromkeys(ROLL_COLS, "")
    row.update({"snapshot_id": snap["snapshot_id"], "family": snap["family"],
                "procedure": snap["procedure"], "task": snap["task"],
                "seed": snap["seed"], "t0": snap["t0"], "arm": arm,
                "rollout_idx": ri, "k_rollout": K, "n_expected": n_exp})
    return row


def finish_rollout(sink: Sink, ctx: dict, snap: dict, steps: list[dict],
                   arm: str, ri: int, K: int, n_exp: int, *, first_action,
                   first_kwargs, contract: bool, contract_at_step, final: dict,
                   n_prims: int, n_pi05: int, n_turns, wall_s: float,
                   budget_exhausted, agent_error, end_reason, note="",
                   seq_len=None, oracle_source_step=None, diverged_at=None):
    eef0 = ctx["base"]["eef"]
    ftarget = fail_target_of(steps, int(snap["t0"]), eef0)
    rf = realignment_first(first_action, first_kwargs, ftarget, eef0) \
        if contract else ""      # §11:仅成功 rollout 记
    row = base_row(snap, arm, ri, K, n_exp)
    row.update({
        "contract_met": bool(contract),
        "contract_at_step": contract_at_step if contract_at_step is not None
        else "",
        "check_success": final["check_success"],
        "terminated": final["terminated"],
        "n_prims": n_prims, "n_pi05": n_pi05, "n_turns": n_turns or "",
        "wall_s": round(wall_s, 1),
        "budget_exhausted": bool(budget_exhausted),
        "agent_error": agent_error or "",
        "end_reason": end_reason or "", "first_action": first_action or "",
        "realignment_first": rf, "note": note,
    })
    if seq_len is not None:
        row["seq_len"] = seq_len
    if oracle_source_step is not None:
        row["oracle_source_step"] = oracle_source_step
    if diverged_at is not None:
        row["diverged_at"] = diverged_at
    sink.rollout(row)
    # REENTRY(§5.2):rollout 全部测量完成后;probe 后状态废弃
    sink.reentry(reentry_row(ctx, snap, steps, final, arm, ri))
    return contract


def run_with_retry(fn, ri: int, max_tries: int = MAX_INFRA_RETRY):
    """rollout 级 infra 重试:返回 (result | None, n_tries)。"""
    for attempt in range(1, max_tries + 1):
        try:
            return fn(), attempt
        except (rt.InfraError, n1.InfraError) as exc:
            log(f"    rollout r{ri} INFRA({attempt}/{max_tries}): "
                f"{type(exc).__name__}: {str(exc)[:140]}")
        except Exception as exc:   # 意外异常同按 infra(§12)
            log(f"    rollout r{ri} UNEXPECTED({attempt}/{max_tries}): "
                f"{type(exc).__name__}: {str(exc)[:140]}\n"
                f"{traceback.format_exc()[-400:]}")
    return None, max_tries


# -- O0:N1 O-policy 逐字移植 --------------------------------------------------
def arm_O0(sink: Sink, snap: dict, gpu: int, shared_kwargs, steps, K: int,
           done: set[int]):
    n_exp = K
    ctx = boot_arm(snap, gpu, shared_kwargs,
                   f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}_O0")
    if ctx is None:
        for ri in range(n_exp):
            if ri in done:
                continue
            r = base_row(snap, "O0", ri, K, n_exp)
            r["infra_abort"] = "boot_3attempts"
            sink.rollout(r)
        return None
    snapc = {**snap, "segment_id": "", "tercile": ""}   # N1 Arm 兼容键
    task_lang = n1._task_language(steps)
    eef0 = ctx["base"]["eef"]
    # P2:t0 基线双 anchor(快照级冻结,N1 逐字)
    bowl = plate = None
    if snap["procedure"] == "P2_FG_RETRY":
        sb = ctx["prims"].segment(prompt=n1.P2_SEG_BOWL, camera="agentview",
                                  min_score=n1.SEG_MIN_SCORE)
        sp = ctx["prims"].segment(prompt=n1.P2_SEG_PLATE, camera="agentview",
                                  min_score=n1.SEG_MIN_SCORE)
        ub, xb = n1._seg_usable(sb)
        up, xp = n1._seg_usable(sp)
        bowl = [xb[0], xb[1]] if ub else [eef0[0], eef0[1]]
        plate = [xp[0], xp[1]] if up else [eef0[0], eef0[1]]
    flags = []
    try:
        for ri in range(n_exp):
            if ri in done:
                continue

            def once(ri=ri):
                rt.restore_checked(ctx, f"{snap['snapshot_id']} O0 r{ri}")
                t1 = time.time()
                a = n1.Arm(snapc, "O", ri, ctx["toolkit"], ctx["prims"],
                           ctx["env"], ctx["outdir"], [])
                if snap["procedure"] == "P1_RPS_REPICK":
                    end = n1.policy_P1(a, eef0)
                else:
                    end = n1.policy_P2(a, task_lang, bowl, plate)
                final = rt.measure(ctx["env"])
                last_res = next((s["result"] for s in reversed(a.steps)
                                 if s.get("kind") == "action"), {})
                contract = rt.task_recovery(snap["family"], final,
                                            ctx["base"], ctx["target"],
                                            action_result=last_res)
                first = next((s for s in a.steps if s.get("kind") == "action"),
                             None)
                return (end, final, contract, a, first,
                        round(time.time() - t1, 1))

            res, tries = run_with_retry(once, ri)
            if res is None:
                r = base_row(snap, "O0", ri, K, n_exp)
                r["infra_abort"] = f"{tries}_attempts"
                sink.rollout(r)
                continue
            end, final, contract, a, first, wall = res
            finish_rollout(
                sink, ctx, snap, steps, "O0", ri, K, n_exp,
                first_action=(first or {}).get("action"),
                first_kwargs=(first or {}).get("kwargs"),
                contract=contract, contract_at_step=None, final=final,
                n_prims=a.n_actions, n_pi05=a.n_picks, n_turns=None,
                wall_s=wall, budget_exhausted=wall > O0_WALL_MAX,
                agent_error=None, end_reason=end,
                note=f"n_prov={len(a.prov)}")
            flags.append(contract)
            log(f"    O0 r{ri} {end} met={contract} wall={wall}s")
    finally:
        stop_ctx(ctx)
    return flags


# -- O1/O2:单技能逐字重采(O2 换 oracle conditioning)-------------------------
def arm_sample(sink: Sink, snap: dict, gpu: int, shared_kwargs, steps, K: int,
               done: set[int], arm: str, ref_rec: dict | None):
    n_exp = O12_SAMPLES
    ctx = boot_arm(snap, gpu, shared_kwargs,
                   f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}_{arm}")
    if ctx is None:
        for ri in range(n_exp):
            if ri in done:
                continue
            r = base_row(snap, arm, ri, K, n_exp)
            r["infra_abort"] = "boot_3attempts"
            sink.rollout(r)
        return None
    family = snap["family"]
    t0i = int(snap["t0"])
    cmd = rt.last_pi05_cmd(steps, t0i)
    if cmd is None:
        for ri in range(n_exp):
            if ri in done:
                continue
            r = base_row(snap, arm, ri, K, n_exp)
            r["note"] = "no_pi05_cmd_in_prefix"
            sink.rollout(r)
        stop_ctx(ctx)
        return None
    action, kwargs = cmd
    note = ""
    oracle_step = None
    if arm == "O2":
        orc = ref_oracle_conditioning(ref_rec, action)
        if orc is None:
            for ri in range(n_exp):
                if ri in done:
                    continue
                r = base_row(snap, arm, ri, K, n_exp)
                r["note"] = "no_pi05_in_ref_domain"
                sink.rollout(r)
            stop_ctx(ctx)
            return None
        # 唯一差异 = conditioning:pi05 族换 prompt,move_to 类换 xyz(prereg §6)
        kwargs = dict(kwargs)
        if action in rt.PI05_TOOLS:
            kwargs["prompt"] = orc["kwargs"].get("prompt")
        elif action == "move_to":
            kwargs["xyz"] = orc["kwargs"].get("xyz")
        oracle_step = orc["step"]
        turn = oracle_first_turn(ref_rec, orc["action"],
                                 orc["kwargs"].get("prompt"))
        note = (f"oracle_ref_step={oracle_step} fallback={orc['fallback']} "
                f"oracle_turn={turn}")
        log(f"    O2 oracle: ref_step={oracle_step} fallback={orc['fallback']}"
            f" turn={turn} prompt={str(kwargs.get('prompt'))[:48]!r}")
    flags = []
    try:
        for ri in range(n_exp):
            if ri in done:
                continue

            def once(ri=ri, action=action, kwargs=kwargs):
                rt.restore_checked(ctx, f"{snap['snapshot_id']} {arm} s{ri}")
                t1 = time.time()
                ctx["toolkit"]._step(action, **kwargs)
                ares = tail_result(ctx)
                final = rt.measure(ctx["env"])
                contract = rt.task_recovery(family, final, ctx["base"],
                                            ctx["target"], action_result=ares)
                return (final, contract, ares,
                        round(time.time() - t1, 1))

            res, tries = run_with_retry(once, ri)
            if res is None:
                r = base_row(snap, arm, ri, K, n_exp)
                r["infra_abort"] = f"{tries}_attempts"
                sink.rollout(r)
                continue
            final, contract, ares, wall = res
            finish_rollout(
                sink, ctx, snap, steps, arm, ri, K, n_exp,
                first_action=action, first_kwargs=kwargs, contract=contract,
                contract_at_step=1 if contract else None, final=final,
                n_prims=1, n_pi05=1 if action in rt.PI05_TOOLS else 0,
                n_turns=None, wall_s=wall,
                budget_exhausted=wall > O12_WALL_MAX, agent_error=None,
                end_reason="SAMPLE_DONE", note=note,
                oracle_source_step=oracle_step)
            flags.append(contract)
            log(f"    {arm} s{ri} met={contract} wall={wall}s")
    finally:
        stop_ctx(ctx)
    return flags


# -- O3:冻结 oracle 序列执行器 -------------------------------------------------
def arm_O3(sink: Sink, snap: dict, gpu: int, shared_kwargs, steps, K: int,
           done: set[int], ref_rec: dict):
    n_exp = K
    seq = ref_action_seq(ref_rec)
    ctx = boot_arm(snap, gpu, shared_kwargs,
                   f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}_O3")
    if ctx is None:
        for ri in range(n_exp):
            if ri in done:
                continue
            r = base_row(snap, "O3", ri, K, n_exp)
            r["infra_abort"] = "boot_3attempts"
            sink.rollout(r)
        return seq, None
    family = snap["family"]
    bud = rt.BUDGET_LADDER
    flags = []
    try:
        for ri in range(n_exp):
            if ri in done:
                continue

            def once(ri=ri):
                rt.restore_checked(ctx, f"{snap['snapshot_id']} O3 r{ri}")
                t1 = time.time()
                n_prims = n_pi05 = 0
                contract = False
                at = None
                end = "SEQ_EXHAUSTED"
                first_action = first_kwargs = None
                for i, (act, kw) in enumerate(seq, start=1):
                    if time.time() - t1 > bud["wall_s"]:
                        end = f"BUDGET_wall"
                        break
                    if n_prims >= bud["max_primitives"]:
                        end = "BUDGET_prims"
                        break
                    if act in rt.PI05_TOOLS and n_pi05 >= bud["max_pi05"]:
                        end = "BUDGET_pi05"
                        break
                    if first_action is None:
                        first_action, first_kwargs = act, kw
                    ctx["toolkit"]._step(act, **kw)
                    ares = tail_result(ctx)
                    n_prims += 1
                    if act in rt.PI05_TOOLS:
                        n_pi05 += 1
                    cur = rt.measure(ctx["env"])
                    if rt.task_recovery(family, cur, ctx["base"],
                                        ctx["target"], action_result=ares):
                        contract, at, end = True, i, "CONTRACT_MET"
                        break
                    if cur["terminated"] or cur["check_success"]:
                        end = "ENV_TERMINATED"
                        break
                final = rt.measure(ctx["env"])
                return (final, contract, at, end, n_prims, n_pi05,
                        first_action, first_kwargs,
                        round(time.time() - t1, 1))

            res, tries = run_with_retry(once, ri)
            if res is None:
                r = base_row(snap, "O3", ri, K, n_exp)
                r["infra_abort"] = f"{tries}_attempts"
                r["seq_len"] = len(seq)
                sink.rollout(r)
                continue
            (final, contract, at, end, n_prims, n_pi05, fa, fkw,
             wall) = res
            finish_rollout(
                sink, ctx, snap, steps, "O3", ri, K, n_exp,
                first_action=fa, first_kwargs=fkw, contract=contract,
                contract_at_step=at, final=final, n_prims=n_prims,
                n_pi05=n_pi05, n_turns=None, wall_s=wall,
                budget_exhausted=end.startswith("BUDGET"), agent_error=None,
                end_reason=end, seq_len=len(seq))
            flags.append(contract)
            log(f"    O3 r{ri} {end} met={contract} wall={wall}s")
    finally:
        stop_ctx(ctx)
    return seq, flags


# -- O4:planner 续跑(boot-per-rollout)+ §22 记录 -----------------------------
def arm_O4(sink: Sink, snap: dict, gpu: int, shared_kwargs, steps, K: int,
           done: set[int], o3_fams: list[str] | None):
    n_exp = K
    family = snap["family"]
    flags = []
    for ri in range(n_exp):
        if ri in done:
            continue
        # 每次 rollout 独立 boot:planner 可读 states.json,必须只含本
        # rollout 的重放步(与 reference 同构,§32-33 干净比较)
        res, tries = None, MAX_INFRA_RETRY

        def once(ri=ri):
            ctx = boot_arm(
                snap, gpu, shared_kwargs,
                f"{snap['snapshot_id']}_t{snap['task']}s{snap['seed']}_"
                f"O4r{ri}")
            if ctx is None:
                raise rt.InfraError("O4 boot failed 3 attempts")
            try:
                rec = rt.run_planner_continuation(ctx, snap, family)
                # REENTRY 在 ctx 存活期内测(用 rec 的 final 测量)
                return ctx, rec
            except Exception:
                stop_ctx(ctx)
                raise

        res, tries = run_with_retry(once, ri)
        if res is None:
            r = base_row(snap, "O4", ri, K, n_exp)
            r["infra_abort"] = f"{tries}_attempts"
            sink.rollout(r)
            continue
        ctx, rec = res
        try:
            acts = [e for e in (rec.get("steps") or [])
                    if not (e.get("result") or {}).get("skipped")]
            o4_fams = [e["action"] for e in acts]
            # 相对 O3 冻结序列的首次偏离(§6 O4;REFERENCE_UNAVAILABLE→null)
            div_at = div_o4 = div_o3 = None
            if o3_fams is not None:
                for i in range(max(len(o4_fams), len(o3_fams))):
                    a4 = o4_fams[i] if i < len(o4_fams) else "<end>"
                    a3 = o3_fams[i] if i < len(o3_fams) else "<end>"
                    if a4 != a3:
                        div_at, div_o4, div_o3 = i, a4, a3
                        break
            # §22 turn 记录 + subgoal 变化(t0 命令为 turn1 的 previous)
            by = {s.get("step_idx"): s for s in steps}
            t0_cmd = (by.get(int(snap["t0"])) or {}).get("command") or {}
            prev_sig = (t0_cmd.get("action"),
                        str(t0_cmd.get("prompt") or t0_cmd.get("xyz") or ""))
            turns_out = []
            for t in rec.get("turns") or []:
                sig = (t.get("next_skill"),
                       str((t.get("skill_args_excerpt") or {}).get("prompt")
                           or (t.get("skill_args_excerpt") or {}).get("xyz")
                           or ""))
                turns_out.append({**t,
                                  "prev_skill": prev_sig[0],
                                  "subgoal_changed": sig != prev_sig})
                prev_sig = sig
            sink.transition({
                "snapshot_id": snap["snapshot_id"],
                "rollout_idx": ri, "arm": "O4",
                "turns": turns_out,
                "o4_action_families": o4_fams,
                "o3_action_families": o3_fams,
                "first_divergence": (None if div_at is None else
                                     {"at_index": div_at, "o4": div_o4,
                                      "o3": div_o3}),
                "contract_met": rec["contract_met"],
                "agent_error": rec.get("agent_error"),
            })
            fa = acts[0] if acts else None
            finish_rollout(
                sink, ctx, snap, steps, "O4", ri, K, n_exp,
                first_action=fa, first_kwargs=(acts[0]["kwargs"] if acts
                                               else None),
                contract=rec["contract_met"],
                contract_at_step=rec.get("contract_at_step"),
                final=rec["final"], n_prims=rec["n_prims"],
                n_pi05=rec["n_pi05"], n_turns=len(rec.get("turns") or []),
                wall_s=rec["wall_s"], budget_exhausted=rec["budget_exhausted"],
                agent_error=rec.get("agent_error"),
                end_reason=(rec.get("finish") or {}).get("status"),
                diverged_at=div_at,
                note=("no_o3_ref" if o3_fams is None else ""))
            flags.append(rec["contract_met"])
            log(f"    O4 r{ri} met={rec['contract_met']} "
                f"succ={rec['check_success']} prims={rec['n_prims']} "
                f"turns={len(rec.get('turns') or [])} wall={rec['wall_s']}s "
                f"div={div_at}")
        finally:
            stop_ctx(ctx)
    return flags


# ---- 快照级 ladder 编排 -------------------------------------------------------
def process_snapshot(snap: dict, gpu: int, shared_kwargs, sink: Sink, K: int,
                     refs: dict, done: dict[tuple[str, str], set[int]],
                     sanity: set[str]):
    sid = snap["snapshot_id"]
    log(f"{sid} {snap['family']} t{snap['task']}s{snap['seed']} T{snap['t0']}")
    steps = rt.load_steps(snap["episode_dir"])

    def complete(arm: str, n: int) -> bool:
        d = done.get((sid, arm), set())
        return all(i in d for i in range(n))

    if not complete("O0", K):
        arm_O0(sink, snap, gpu, shared_kwargs, steps, K,
               done.get((sid, "O0"), set()))
    else:
        log("    O0 已完成(resume)")

    if not complete("O1", O12_SAMPLES):
        arm_sample(sink, snap, gpu, shared_kwargs, steps, K,
                   done.get((sid, "O1"), set()), "O1", None)
    else:
        log("    O1 已完成(resume)")

    # O1 gate(§10):成功标志从已落盘行重读(覆盖 resume 路径)
    def o1_flags() -> list[bool]:
        lines = [l for l in open(ROLL_CSV, encoding="utf-8")
                 if not l.startswith("#")]
        out = []
        for r in csv.DictReader(io.StringIO("".join(lines))):
            if r["snapshot_id"] == sid and r["arm"] == "O1" \
                    and not r["infra_abort"] and r["note"] != (
                        "no_pi05_cmd_in_prefix"):
                out.append(r["contract_met"] == "True")
        return out

    o1_present = recovery_present(o1_flags())
    ref_rec = refs.get(sid) if sid in refs else None
    ref_ok = ref_rec is not None
    if o1_present:
        if sid not in sanity:
            log("    O1 RECOVERY_PRESENT 且非 sanity 子集 → 停(标签 O1)")
            return
        log("    O1 RECOVERY_PRESENT,sanity 子集 → 继续 O2-O4")
    if not ref_ok:
        log("    REFERENCE_UNAVAILABLE → 跳 O2/O3,仍跑 O4(§10)")
    seq = None
    if ref_ok:
        if not complete("O2", O12_SAMPLES):
            arm_sample(sink, snap, gpu, shared_kwargs, steps, K,
                       done.get((sid, "O2"), set()), "O2", ref_rec)
        else:
            log("    O2 已完成(resume)")
        if not complete("O3", K):
            seq, _ = arm_O3(sink, snap, gpu, shared_kwargs, steps, K,
                            done.get((sid, "O3"), set()), ref_rec)
        else:
            log("    O3 已完成(resume)")
            seq = ref_action_seq(ref_rec)
    if not complete("O4", K):
        arm_O4(sink, snap, gpu, shared_kwargs, steps, K,
               done.get((sid, "O4"), set()),
               [a for a, _ in seq] if seq is not None else None)
    else:
        log("    O4 已完成(resume)")


# ---- 主入口 ------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default=None,
                    help="只跑指定 snapshot_id(调试)")
    args = ap.parse_args()

    rt.apply_env_overrides()
    ox.pg.preflight(label="stageO_ladder", lock_name="stageO_ladder.lock")

    snaps = read_manifest()
    K = read_k_rollout()
    refs = load_references()
    # 25% sanity 子集(冻结 seed,§10;对全 manifest 一次性抽取)
    import numpy as np
    ids = sorted(s["snapshot_id"] for s in snaps)
    rng = np.random.RandomState(SANITY_SEED)
    sanity = set(rng.choice(ids, size=max(1, round(0.25 * len(ids))),
                            replace=False))
    log(f"manifest {len(snaps)} | K_ROLLOUT={K} | "
        f"reference OK={sum(1 for v in refs.values() if v)}/"
        f"{len(refs)} | sanity25%={sorted(sanity)}")
    if args.only:
        snaps = [s for s in snaps if s["snapshot_id"] == args.only]

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = LOG_ROOT / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)
    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=10000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    log(f"boot shared vla+sam3 on gpu{args.gpu} ...")
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())

    sink = Sink()

    def needs_work(s: dict) -> bool:
        sid = s["snapshot_id"]
        checks = [("O0", K), ("O1", O12_SAMPLES), ("O4", K)]
        if refs.get(sid) is not None:
            checks += [("O2", O12_SAMPLES), ("O3", K)]
        return any(any(i not in done_rollouts().get((sid, a), set())
                       for i in range(n)) for a, n in checks)

    todo = [s for s in snaps if needs_work(s)]
    log(f"todo {len(todo)}/{len(snaps)} snapshots(workers={args.workers})")

    try:
        if args.workers <= 1 or len(todo) <= 1:
            for s in todo:
                try:
                    process_snapshot(s, args.gpu, shared_kwargs, sink, K,
                                     refs, done_rollouts(), sanity)
                except Exception as exc:
                    log(f"{s['snapshot_id']} SNAPSHOT EXC "
                        f"{type(exc).__name__}: {exc}\n"
                        f"{traceback.format_exc()[-600:]}")
        else:
            from collections import deque
            pending = deque(todo)
            plock = threading.Lock()

            def worker():
                while True:
                    with plock:
                        if not pending:
                            return
                        s = pending.popleft()
                    try:
                        process_snapshot(s, args.gpu, shared_kwargs, sink, K,
                                         refs, done_rollouts(), sanity)
                    except Exception as exc:
                        log(f"{s['snapshot_id']} SNAPSHOT EXC "
                            f"{type(exc).__name__}: {exc}\n"
                            f"{traceback.format_exc()[-600:]}")

            threads = [threading.Thread(target=worker, daemon=True)
                       for _ in range(args.workers)]
            for t in threads:
                t.start()
                time.sleep(ox.STAGGER_S)
            for t in threads:
                t.join()
    finally:
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass

    # infra 率(§12:confirmatory batch <2%)
    lines = [l for l in open(ROLL_CSV, encoding="utf-8")
             if not l.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("".join(lines))))
    n_ab = sum(1 for r in rows if r["infra_abort"])
    log(f"ladder 完成:rows={len(rows)} infra_abort={n_ab}"
        f"({(n_ab / len(rows) * 100) if rows else 0:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
