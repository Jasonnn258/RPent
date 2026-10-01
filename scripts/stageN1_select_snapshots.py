#!/usr/bin/env python
"""Stage N1 §3 — held-out 快照抽样(manifest + SHA256 冻结)。

资格框(与 stageN0_audit_sample.py 一致):eligible = RESOLVED − 旧33 −
SPOT3 − dev_viewed;再按 **episode 级**排除 45 卷 N0 audit 的全部 episode。
前置条件逐段核验 states.json:P1 要求 t0=release 且 terminated=False;
P2 要求 t0=pi0_pick 且 success=False;并要求 1..t0 每步有 command。
task×seed 唯一;每 procedure 12 快照;层内字典序 + RandomState(20261003)。
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SEED = 20261003
N_PER_PROC = 12
FAM2PROC = {
    "RELEASE_PREDICATE_STALL": "P1_RPS_REPICK",
    "FALSE_GRASP": "P2_FG_RETRY",
}
SPOT_CHECKED = {
    "20260915-18:12:26_glm-5.3-flash_armA_libero_spatial_task_t5_s4_r1#f1",
    "20260907-18:29:08_glm-5.3-flash_armC_libero_spatial_task_t9_s10_r2#f1",
    "20260915-18:12:26_glm-5.3-flash_armA_libero_spatial_task_t5_s4_r1#f0",
}


def episode_of(segment_id: str) -> str:
    return segment_id.split("#")[0]


def read_rows(path: Path) -> list[dict]:
    """读 CSV(dict);跳过 # 注释行(N0/N1 manifest 头部)。"""
    import io
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def verify_precondition(episode_dir: Path, family: str, t0: int) -> str | None:
    """核验快照前置条件;返回失败原因(None = 通过)。"""
    try:
        steps = json.load(open(episode_dir / "states.json"))
    except Exception as exc:
        return f"states.json unreadable: {exc}"
    steps = sorted(steps, key=lambda s: s.get("step_idx", 0))
    by_idx = {s.get("step_idx"): s for s in steps}
    # 重放完整性:1..t0 每步有 command
    missing = [i for i in range(1, t0 + 1)
               if not (by_idx.get(i) or {}).get("command")]
    if missing:
        return f"commands missing at steps {missing[:5]}"
    s0 = by_idx.get(t0) or {}
    cmd, res = s0.get("command") or {}, s0.get("result") or {}
    if family == "RELEASE_PREDICATE_STALL":
        if cmd.get("action") != "release":
            return f"t0 action={cmd.get('action')} != release"
        if res.get("libero_terminated") is not False:
            return f"t0 terminated={res.get('libero_terminated')} != False"
    elif family == "FALSE_GRASP":
        if cmd.get("action") != "pi0_pick":
            return f"t0 action={cmd.get('action')} != pi0_pick"
        if res.get("success") is not False:
            return f"t0 success={res.get('success')} != False"
    return None


def main() -> int:
    rows = read_rows(REPO / "analysis/stageN0_control_labels.csv")
    old33 = {r["segment_id"] for r in
             read_rows(REPO / "analysis/stageM0_audit_sample.csv")}
    devv = {r["segment_id"] for r in
            read_rows(REPO / "analysis/stageN0_dev_viewed.csv")}
    audit_eps = {episode_of(r["segment_id"]) for r in
                 read_rows(REPO / "analysis/stageN0_audit_manifest.csv")}

    resolved = [r for r in rows if r["segment_label"] in ("DEPENDENT", "INDEPENDENT")]
    base = [r for r in resolved
            if r["segment_id"] not in (old33 | SPOT_CHECKED | devv)]
    heldout = [r for r in base if episode_of(r["segment_id"]) not in audit_eps]
    print(f"RESOLVED {len(resolved)} → N0-eligible {len(base)} → "
          f"episode 级排除 45 卷后 {len(heldout)}")

    # 前置条件核验 + episode 目录定位
    ok, rejected = [], defaultdict(int)
    for r in heldout:
        fam = r["family"]
        if fam not in FAM2PROC:
            rejected[fam] += 1
            continue
        ep = episode_of(r["segment_id"])
        edir = None
        for cand in (REPO / "logs/ovpm_exp").glob(f"*{ep}*"):
            edir = cand
            break
        # N0 池的 episode_dir 与 stageL_pool_inventory 一致;直接按名拼
        if edir is None:
            edir = REPO / "logs/ovpm_exp" / ep
        if not (edir / "states.json").exists():
            rejected["no_states"] += 1
            continue
        why = verify_precondition(edir, fam, int(r["t0"]))
        if why:
            rejected[f"precond:{why[:40]}"] += 1
            continue
        ok.append({**r, "episode_dir": str(edir), "procedure": FAM2PROC[fam]})
    print(f"前置核验通过 {len(ok)};拒绝分布 {dict(rejected)}")

    # task×seed 唯一(贪心:字典序小的段优先保留)
    seen_ts, uniq = set(), []
    for r in sorted(ok, key=lambda x: x["segment_id"]):
        ts = (r["task"], r["seed"])
        if ts in seen_ts:
            continue
        seen_ts.add(ts)
        uniq.append(r)
    print(f"task×seed 唯一后 {len(uniq)}")

    # 长度三分位(S/M/L 均分)+ 层内随机抽取
    manifest = []
    for proc in ("P1_RPS_REPICK", "P2_FG_RETRY"):
        pool = [r for r in uniq if r["procedure"] == proc]
        pool.sort(key=lambda r: int(r["primitive_count"]))
        n = len(pool)
        thirds = [pool[: n // 3], pool[n // 3: 2 * n // 3], pool[2 * n // 3:]]
        rng = np.random.RandomState(SEED)
        quota = {"S": N_PER_PROC // 3, "M": N_PER_PROC // 3,
                 "L": N_PER_PROC - 2 * (N_PER_PROC // 3)}
        for ter, members in zip(("S", "M", "L"), thirds):
            ids = sorted(r["segment_id"] for r in members)
            k = min(quota[ter], len(ids))
            pick = set(rng.choice(ids, size=k, replace=False)) if k else set()
            for r in members:
                if r["segment_id"] in pick:
                    manifest.append({**r, "tercile": ter})

    cols = ["snapshot_id", "procedure", "segment_id", "episode_dir", "family",
            "task", "seed", "t0", "tR", "tercile", "primitive_count"]
    body = ",".join(cols) + "\n"
    for i, r in enumerate(sorted(manifest, key=lambda x: x["segment_id"])):
        r["snapshot_id"] = f"snap_{i:02d}"
        body += ",".join(json.dumps(v, ensure_ascii=False) for v in
                         [r["snapshot_id"], r["procedure"], r["segment_id"],
                          r["episode_dir"], r["family"], r["task"], r["seed"],
                          r["t0"], r["tR"], r["tercile"],
                          r["primitive_count"]]) + "\n"

    sha = hashlib.sha256(body.encode()).hexdigest()
    out = REPO / "analysis/stageN1_split_manifest.csv"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# stageN1_split_manifest | seed={SEED} | "
                f"N={len(manifest)} | P1={sum(1 for m in manifest if m['procedure']=='P1_RPS_REPICK')} "
                f"P2={sum(1 for m in manifest if m['procedure']=='P2_FG_RETRY')}\n")
        f.write(f"# sha256(以下全部字节)={sha}\n")
        f.write(body)
    print(f"manifest N={len(manifest)};sha256={sha}")
    by = defaultdict(list)
    for m in manifest:
        by[(m["procedure"], m["tercile"])].append(m["task"])
    for k in sorted(by):
        print(k, "tasks:", sorted(by[k]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
