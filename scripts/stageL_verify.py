#!/usr/bin/env python
"""Stage L §7-9 — L1 双验证 runner(DEV/HELDOUT × 冻结边+候选 × K=4)。

与 K 采集器(stagek_dataset_collect)同栈复用:env boot / prefix 重放 /
save_state-restore / readback 校验 / exec_edge(§7-B 冻结契约)/ 断点续采 /
预算闸;新增:
- 候选池:冻结合法边(detection)+ stageL_candidate_edges_v*.jsonl
  (族匹配适用);
- **Verifier A 录制**:包装 toolkit._step 记录全部实际调用(工具+解析后
  实参),离线按 prereg v1.1 前缀语义复核(声明序列前缀 ∧ 无未声明动作
  ∧ 字面参数精确/${} 参数后验重导 ≤1e-4 或串全等);
- source_excluded 标记(候选源 episode 与快照 episode 重合 → 统计时排除,
  运行照常,prereg §9"统计排除")。

用法:
  MUJOCO_GL=osmesa python scripts/stageL_verify.py --phase dev --round 1 \
      --gpu 0 [--max-rollouts N] [--snapshots id1,id2]
产物:logs/stageL_round{round}/rollouts.jsonl +
      analysis/stageL_round{round}_verification.csv
"""
from __future__ import annotations

# 代理防火墙先于任何 urllib/httpx 使用者(本机 http_proxy 劫持 loopback)
import os as _os

for _k in ("no_proxy", "NO_PROXY"):
    _v = _os.environ.get(_k)
    _loop = "127.0.0.1,localhost"
    _os.environ[_k] = (_v + "," + _loop) if _v else _loop

import argparse
import csv
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stagek_graph_executor import (  # noqa: E402
    OFFSET_SUFFIX, EdgeExecutor, _eval_expr, load_edges)
from stagek_dataset_collect import (  # noqa: E402
    _last_pick_prompt, _load_source_steps, _task_language)

MAX_RETRY = 3
BUDGET_CAP = 2400          # prereg §9/§16:DEV/HELDOUT 各 ≤2400 rollouts
K_ROLLOUT = 4              # prereg §8:沿用 K0 冻结


def load_candidates(path: Path) -> list[dict]:
    """v0/v1 候选文件 → 候选边列表(REJECT 记录跳过)。"""
    out = []
    for line in open(path):
        r = json.loads(line)
        if r.get("record_type") != "REJECT":
            out.append(r)
    return out


def verifier_a(edge: dict, ctx: dict, base: dict, rec: dict) -> dict:
    """prereg v1.1 前缀语义执行一致性复核(离线可重算)。

    rec["calls"] = [(tool, kwargs)](toolkit._step 包装录制);
    rec["chain"] = exec_edge 返回的执行链(result 子集)。
    判定:实际调用须为声明序列的前缀,参数字面量精确、${} 绑定后验重导
    数值 ≤1e-4 / 串全等;判定窗 set_gripper(0.0, steps=5) ≤4 次仅可
    出现在声明步之后;任何多余/失配动作 → FAIL。
    """
    declared = edge["executor"]
    calls = rec.get("calls") or []
    chain = rec.get("chain") or []
    problems = []

    # 链内感知产物(segment box / back_project center)供 ${} 后验重导
    names = {"eef": base["eef"], "obj": None}
    seg = next((c["result"] for c in chain if c["tool"] == "segment"), {})
    bp = next((c["result"] for c in chain if c["tool"] == "back_project"), {})
    if bp.get("center_xyz") is not None:
        names["obj"] = list(bp["center_xyz"])
    if seg.get("row_range"):
        names["mask_rows"] = list(seg["row_range"])
        names["mask_cols"] = list(seg["col_range"])

    def expected(v):
        """声明实参(${name} 或字面量)→ 后验期望值;不可导出返回 None。"""
        if not (isinstance(v, str) and v.startswith("${") and v.endswith("}")):
            return v
        name = v[2:-1]
        raw = edge["parameterizer"]["bindings"].get(name, name)
        if raw == "TASK_LANG":
            return ctx["task_lang"]
        if raw == "LAST_PICK_PROMPT":
            return ctx["last_pick"]
        if raw == "LAST_PICK_PROMPT + OFFSET_SUFFIX":
            return (ctx["last_pick"] or ctx["task_lang"]) + OFFSET_SUFFIX
        if raw == "LAST_PICK_PROMPT(无则 TASK_LANG)":
            return ctx["last_pick"] or ctx["task_lang"]
        if raw == "EEF":
            return list(names["eef"])
        if raw == "OBJ_XYZ":
            return names.get("obj")
        if raw in names:
            return names[raw]
        if isinstance(raw, str) and raw.strip().startswith("["):
            try:
                return _eval_expr(raw, names)
            except Exception:
                return None
        return None

    n_exec = 0
    window_started = False
    for tool, kwargs in calls:
        is_window = (tool == "set_gripper"
                     and abs(kwargs.get("gripper", 9)) <= 1e-9
                     and kwargs.get("steps") == 5)
        if not window_started and n_exec < len(declared) \
                and tool == declared[n_exec]["tool"]:
            d = declared[n_exec]
            for key, dv in d["args"].items():
                av = kwargs.get(key)
                ev = expected(dv)
                if isinstance(ev, (int, float)) and isinstance(av, (int, float)):
                    if abs(av - ev) > 1e-4:
                        problems.append(
                            f"step{n_exec}.{key}: {av} != 期望 {ev}")
                elif isinstance(ev, (list, tuple)):
                    if not isinstance(av, (list, tuple)) or len(av) != len(ev) \
                            or any(abs(a - e) > 1e-4 for a, e in zip(av, ev)):
                        problems.append(
                            f"step{n_exec}.{key}: {av} != 期望 {ev}")
                elif ev is not None and av != ev:
                    problems.append(f"step{n_exec}.{key}: 值不符声明绑定")
            n_exec += 1
        elif is_window:
            # 判定窗调用(声明链完成或中止后):允许,后续不再期待声明步
            window_started = True
        else:
            problems.append(f"多余/失序动作: {tool}"
                            f"({json.dumps(kwargs, default=str)[:80]})")

    return {
        "pass": not problems, "n_declared": len(declared),
        "n_executed": min(n_exec, len(declared)),
        "chain_abort": n_exec < len(declared),
        "problems": problems[:5],
    }


def run_snapshot(snap: dict, frozen: dict, cands: list[dict], gpu: int,
                 shared_kwargs: dict, log_root: Path, round_no: int,
                 emit, done: set) -> int:
    """快照 × (冻结合法边 + 族匹配候选) × k=1..K_ROLLOUT。"""
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec, get_toolkit
    from rpent.utils.logging import init_output_dir

    sid = snap["snapshot_id"]
    outdir = log_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{sid}"
    outdir.mkdir(parents=True, exist_ok=True)
    init_output_dir(outdir)

    env_spec = get_env_spec("libero")
    args = argparse.Namespace(
        suite="libero_spatial", task=snap["task"], seed=snap["seed"],
        max_episode_steps=200000, cuda_device=gpu,
        env_endpoint=None, vla_endpoint=None, sam3_endpoint=None,
        libero_type=None,
    )
    daemons, n_new = [], 0
    toolkit = None
    try:
        env_daemons, env_kwargs = env_spec.init_task_runtime(
            args, outdir, NullDashboardEventSink())
        daemons.extend(env_daemons)
        primitives_kwargs = dict(env_kwargs)
        primitives_kwargs.update(shared_kwargs)
        toolkit = get_toolkit(
            "libero", primitives_kwargs=primitives_kwargs,
            video_path=str(outdir / "episode.mp4"),
            dashboard_events=NullDashboardEventSink())
        prims = toolkit._primitives
        env = prims.env

        steps = _load_source_steps(snap["episode_dir"])
        T = snap["T"]
        t0 = time.time()
        for s in steps:
            idx, cmd = s.get("step_idx"), s.get("command")
            if idx is None or not cmd or not (1 <= idx <= T):
                continue
            toolkit._step(cmd["action"], **{k: v for k, v in cmd.items()
                                            if k != "action"})
        replay_s = round(time.time() - t0, 1)
        S = env.save_state()
        ex = EdgeExecutor(toolkit, env, prims, outdir)
        base = ex.measure()
        ctx = {"task_lang": _task_language(steps),
               "last_pick": _last_pick_prompt(steps, T)}

        # 边池:冻结合法边 + 族匹配候选;候选标 source_excluded
        pool = []
        for eid in snap["legal_edges"]:
            if eid in frozen:      # --no-frozen(Round 2)时词表为空 → 跳过
                pool.append((frozen[eid], False))
        for c in cands:
            if c["failure_family"] == snap["family"]:
                pool.append((c, snap["episode_dir"] in
                             c["source_evidence"]["episodes"]))
        print(f"[LV] {sid} replay={replay_s}s ooi={base['ooi']} "
              f"pool={len(pool)} ({len(snap['legal_edges'])} 冻结 + "
              f"{len(pool) - len(snap['legal_edges'])} 候选)", flush=True)

        # Verifier A 录制:包装 toolkit._step
        orig_step = toolkit._step
        calls: list = []

        def rec_step(tool, **kw):
            calls.append((tool, kw))
            return orig_step(tool, **kw)
        toolkit._step = rec_step

        for edge, src_excl in pool:
            for k in range(1, K_ROLLOUT + 1):
                if (sid, edge["id"], k) in done:
                    continue
                for attempt in range(1, MAX_RETRY + 1):
                    rec = {
                        "snapshot_id": sid, "edge_id": edge["id"],
                        "family": edge["failure_family"], "k": k,
                        "attempt": attempt, "round": round_no,
                        "phase": snap.get("phase"),
                        "task": snap["task"], "seed": snap["seed"], "T": T,
                        "is_candidate": edge["id"].startswith("LC-"),
                        "source_excluded": src_excl,
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                    ok = False
                    try:
                        calls.clear()
                        obs = env.restore_state(S)
                        prims.set_obs(obs)
                        readback = env.save_state()
                        diff = float(abs(readback - S).max()) \
                            if len(readback) == len(S) else -1.0
                        rec["readback_max_abs_diff"] = diff
                        if diff != 0.0:
                            rec["infra_error"] = f"restore readback {diff}"
                        else:
                            r = ex.exec_edge(edge, ctx)
                            rec.update(r)
                            rec["calls"] = [list(c) for c in calls]
                            rec["verifier_a"] = verifier_a(
                                edge, ctx, base, rec)
                            ok = True
                    except Exception as exc:
                        rec["infra_error"] = (
                            f"{type(exc).__name__}: {exc}"[:300])
                    emit(rec)
                    if ok:
                        n_new += 1
                        break
                print(f"[LV]   {edge['id']} k={k} -> "
                      f"{rec.get('outcome') or str(rec.get('infra_error', '?'))[:60]}"
                      f" A={'PASS' if rec.get('verifier_a', {}).get('pass') else '?'}"
                      f" ({rec.get('elapsed_s', '?')}s)", flush=True)
    finally:
        try:
            if toolkit is not None:
                toolkit.close()
        except Exception:
            pass
        for d in daemons:
            try:
                d.stop()
            except Exception:
                pass
    return n_new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", choices=["dev", "heldout"], default="dev")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--candidates",
                    default="analysis/stageL_candidate_edges_v0.jsonl")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--max-rollouts", type=int, default=BUDGET_CAP)
    ap.add_argument("--snapshots", default=None)
    # Round 2:冻结边 P̂ 复用 Round 1 同快照测量(确定性 restore,readback
    # 逐位校验),只跑新候选 —— 省预算且避免重复测量同一量
    ap.add_argument("--no-frozen", action="store_true")
    args = ap.parse_args()
    args.max_rollouts = min(args.max_rollouts, BUDGET_CAP)

    # 防重锁(CLAUDE.md 纪律)
    lock = Path(f"/workspace/yjx/.runlocks/stageL_verify_"
                f"{args.phase}_r{args.round}.lock")
    try:
        lock.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"[LV] 拒绝启动:锁已存在 {lock}", flush=True)
        return 1
    import atexit
    atexit.register(lambda: lock.rmdir() if lock.exists() else None)

    # ---- 快照清单(manifest → 运行结构)------------------------------------
    role = "L_DISCOVERY_DEV" if args.phase == "dev" else "L_HELDOUT_TEST"
    snaps = []
    for r in csv.DictReader(open(REPO / "analysis/stageL_split_manifest.csv")):
        if r["role"] != role:
            continue
        # id 唯一性:同 (task,seed,T) 可能对应不同 episode(r 不同),
        # 追加 episode_dir 哈希防撞车(done-set 断点键依赖唯一性)
        import hashlib
        snaps.append({
            "snapshot_id": f"L{args.round}r_t{r['task']}s{r['seed']}T{r['anchor_fire_step']}_"
                           f"{hashlib.md5(r['episode_dir'].encode()).hexdigest()[:6]}",
            "episode_dir": r["episode_dir"], "task": int(r["task"]),
            "seed": int(r["seed"]), "T": int(r["anchor_fire_step"]),
            "family": r["anchor_family"],
            "legal_edges": r["legal_edges"].split("|"),
            "phase": args.phase,
        })
    if args.snapshots:
        keep = set(args.snapshots.split(","))
        snaps = [s for s in snaps if s["snapshot_id"] in keep]

    frozen = {} if args.no_frozen else load_edges()
    cands = load_candidates(REPO / args.candidates)
    log_root = REPO / f"logs/stageL_round{args.round}"
    log_root.mkdir(parents=True, exist_ok=True)
    out_path = log_root / "rollouts.jsonl"

    done: set = set()
    if out_path.exists():
        for line in open(out_path):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("outcome") and not r.get("infra_error"):
                done.add((r.get("snapshot_id"), r.get("edge_id"), r.get("k")))
        print(f"[LV] resume:{len(done)} 条已有有效记录,跳过", flush=True)

    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.envs import get_env_spec
    from rpent.utils.logging import init_output_dir
    from rpent.utils.resources import ensure_resources

    ensure_resources("libero")
    shared_root = log_root / "_shared_runtime"
    shared_root.mkdir(parents=True, exist_ok=True)
    init_output_dir(shared_root)
    env_spec = get_env_spec("libero")
    ns = argparse.Namespace(
        suite="libero_spatial", task=0, seed=0, max_episode_steps=200000,
        cuda_device=args.gpu, env_endpoint=None, vla_endpoint=None,
        sam3_endpoint=None, libero_type=None,
    )
    print(f"[LV] boot shared vla+sam3 on gpu{args.gpu} ...", flush=True)
    shared_daemons, shared_kwargs = env_spec.init_shared_runtime(
        ns, shared_root, NullDashboardEventSink())
    print(f"[LV] phase={args.phase} round={args.round} | K_ROLLOUT={K_ROLLOUT} | "
          f"snapshots={len(snaps)} | frozen_edges={sum(len(s['legal_edges']) for s in snaps)} "
          f"| candidates={len(cands)} | cap={args.max_rollouts}", flush=True)

    n_out = n_infra = 0
    fout = open(out_path, "a")

    def emit(r: dict) -> None:
        nonlocal n_out, n_infra
        try:
            line = json.dumps(r, ensure_ascii=False, default=str)
        except Exception as exc:
            line = json.dumps({
                "snapshot_id": r.get("snapshot_id"),
                "edge_id": r.get("edge_id"), "k": r.get("k"),
                "infra_error": f"serialize: {exc}"}, ensure_ascii=False)
        fout.write(line + "\n")
        fout.flush()
        if json.loads(line).get("infra_error"):
            n_infra += 1
        else:
            n_out += 1

    try:
        for snap in snaps:
            if n_out >= args.max_rollouts:
                print(f"[LV] 预算闸到量(n_out={n_out}),停止排新快照",
                      flush=True)
                break
            t0 = time.time()
            try:
                new = run_snapshot(snap, frozen, cands, args.gpu,
                                   shared_kwargs, log_root, args.round,
                                   emit, done)
            except Exception as exc:  # 快照级 infra(boot/重放失败)
                emit({"snapshot_id": snap["snapshot_id"], "edge_id": None,
                      "family": snap["family"], "k": None, "attempt": 1,
                      "round": args.round, "phase": args.phase,
                      "task": snap["task"], "seed": snap["seed"],
                      "ts": datetime.now().isoformat(timespec="seconds"),
                      "infra_error": f"{type(exc).__name__}: {exc}"[:300],
                      "traceback": traceback.format_exc()[-1200:]})
                new = 0
            print(f"[LV] {snap['snapshot_id']} done: +{new} "
                  f"({round(time.time() - t0, 1)}s) "
                  f"cumulative ok={n_out} infra={n_infra}", flush=True)
    finally:
        fout.close()
        for d in shared_daemons:
            try:
                d.stop()
            except Exception:
                pass
    print(f"[LV] done: ok={n_out} infra={n_infra} -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    # GL 环境纪律(CLAUDE.md):本容器必须 osmesa。注意
    # robots/libero/env_server.py 对 PYOPENGL_PLATFORM 做 setdefault("egl"),
    # 父进程只 unset 会被填回 egl → 必须显式 =osmesa 覆盖
    _e = __import__("os").environ
    _e["MUJOCO_GL"] = "osmesa"
    _e["PYOPENGL_PLATFORM"] = "osmesa"
    for _bad in ("MUJOCO_EGL_DEVICE_ID", "LIBGL_ALWAYS_SOFTWARE"):
        _e.pop(_bad, None)
    _e.setdefault("OPENPI_DATA_HOME",
                  "/workspace/yjx/rpent_data/.cache/openpi")
    raise SystemExit(main())
