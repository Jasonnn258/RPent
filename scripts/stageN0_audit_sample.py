#!/usr/bin/env python
"""Stage N §8 — N0 资格盲审抽样(manifest + SHA256 冻结)。

逐字实现 spec §8:eligible = RESOLVED 165 − 旧33 − 3 SPOT_CHECKED −
dev_viewed;族×机器类×长度三分位分层;q_U=min(8,|U|), q_I=min(12,|I|),
q_D=45−q_U−q_I;族内配额比例 round+最大余数;层内 S/M/L 均分;
每层 segment_id 字典序 + np.random.RandomState(20261002).choice。

抽取序(= audit_id 编号序,冻结):族 [RPS,FG,MCS] × 类
[DEPENDENT,INDEPENDENT,UNRESOLVED] × 三分位 [S,M,L] 依序抽取追加。

manifest 首行注释写 sha256(本行以下全部字节)——自引用无解,故哈希
只覆盖数据行;commit 先于人工盲审即冻结。

spec §8 对 I/U 的跨族配额未逐字定义(q_U/q_I 很小);实现取与 D 相同的
比例+最大余数规则,平手 RPS>FG>MCS —— 已写入 manifest 头部注释备查。
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

SEED = 20261002
N_AUDIT = 45
# 平手优先序 RPS>FG>MCS(spec §8);CSV family 列是全名
FAM_ORDER = ["RELEASE_PREDICATE_STALL", "FALSE_GRASP", "MOVE_CONTACT_STALL"]
CLS_ORDER = ["DEPENDENT", "INDEPENDENT", "UNRESOLVED"]
TER_ORDER = ["S", "M", "L"]

# M 期带标签抽查过的 3 条(stageM0_audit_dossiers.py 同集,仅迁移定义)
SPOT_CHECKED = {
    "20260915-18:12:26_glm-5.3-flash_armA_libero_spatial_task_t5_s4_r1#f1",
    "20260907-18:29:08_glm-5.3-flash_armC_libero_spatial_task_t9_s10_r2#f1",
    "20260915-18:12:26_glm-5.3-flash_armA_libero_spatial_task_t5_s4_r1#f0",
}


def fam_quota(total: int, members: dict) -> dict:
    """族间比例分配:round + 最大余数;平手 RPS>FG>MCS。"""
    tot_pool = sum(len(v) for v in members.values())
    if total <= 0 or tot_pool == 0:
        return {f: 0 for f in members}
    raw = {f: total * len(members[f]) / tot_pool for f in members}
    q = {f: int(round(raw[f])) for f in members}
    # round 可能超 total;先截断到池大小并回收
    for f in q:
        q[f] = min(q[f], len(members[f]))
    rema = total - sum(q.values())
    while rema != 0:
        key = lambda f: (raw[f] - q[f]) * (1 if rema > 0 else -1)
        order = sorted([f for f in members if members[f]],
                       key=lambda f: (-key(f),
                                      FAM_ORDER.index(f) if f in FAM_ORDER
                                      else 99))
        step = 1 if rema > 0 else -1
        moved = False
        for f in order:
            if rema > 0 or q[f] > 0:
                q[f] += step
                rema -= step
                moved = True
                break
        if not moved:
            break
    return q


def main() -> int:
    # ---- 资格框 ------------------------------------------------------------
    rows = list(csv.DictReader(open(REPO / "analysis/stageN0_control_labels.csv")))
    old33 = {r["segment_id"] for r in
             csv.DictReader(open(REPO / "analysis/stageM0_audit_sample.csv"))}
    devv = {r["segment_id"] for r in
            csv.DictReader(open(REPO / "analysis/stageN0_dev_viewed.csv"))}
    resolved = [r for r in rows if r["segment_label"] in ("DEPENDENT",
                                                          "INDEPENDENT")]
    excl = old33 | SPOT_CHECKED | devv
    eligible = [r for r in resolved if r["segment_id"] not in excl]
    print(f"RESOLVED {len(resolved)} | 排除 旧33 {len(old33)} ∪ spot3 "
          f"{len(SPOT_CHECKED)} ∪ dev_viewed {len(devv)} | "
          f"eligible {len(eligible)}")
    by_cls = defaultdict(list)
    for r in eligible:
        by_cls[r["machine_class"]].append(r)
    for c in CLS_ORDER:
        print(f"  eligible∩{c}: {len(by_cls[c])}")

    # ---- 长度三分位(eligible 全体,冻结)-----------------------------------
    ps = sorted(int(r["primitive_count"]) for r in eligible)
    p33 = ps[int(len(ps) * 33 // 100)]
    p66 = ps[int(len(ps) * 66 // 100)]

    def tercile(p):
        return "S" if p <= p33 else ("M" if p <= p66 else "L")

    # ---- 类配额 -------------------------------------------------------------
    q_U = min(8, len(by_cls["UNRESOLVED"]))
    q_I = min(12, len(by_cls["INDEPENDENT"]))
    q_D = N_AUDIT - q_U - q_I
    print(f"tercile p33={p33} p66={p66} | q_U={q_U} q_I={q_I} q_D={q_D}")

    # 族间分配(D 按比例;I/U 同规则——spec 未逐字定义小配额的跨族分配)
    members_f = {c: {f: [r for r in by_cls[c] if r["family"] == f]
                     for f in {r["family"] for r in by_cls[c]}}
                 for c in CLS_ORDER}
    fam_q = {c: fam_quota(n, members_f[c])
             for c, n in [("UNRESOLVED", q_U), ("INDEPENDENT", q_I),
                          ("DEPENDENT", q_D)]}
    for c in CLS_ORDER:
        print(f"  {c} 族配额: {fam_q[c]} "
              f"(池 {[f + ':' + str(len(v)) for f, v in members_f[c].items()]})")

    # ---- 层构造与抽取 -------------------------------------------------------
    rng = np.random.RandomState(SEED)
    picked = []          # (audit 序, row, tercile)
    shortfall_D = 0      # 空层缺口 → 补给同族 DEPENDENT

    def draw(rows_in, n):
        ids = sorted(r["segment_id"] for r in rows_in)
        take = set(rng.choice(ids, size=n, replace=False).tolist()) \
            if n else set()
        return [r for r in rows_in if r["segment_id"] in take]

    for c in CLS_ORDER:
        for f in FAM_ORDER + [x for x in members_f[c] if x not in FAM_ORDER]:
            pool_f = members_f[c].get(f, [])
            quota = fam_q[c].get(f, 0)
            if not pool_f or quota <= 0:
                continue
            by_t = {t: [r for r in pool_f
                        if tercile(int(r["primitive_count"])) == t]
                    for t in TER_ORDER}
            base, rema = divmod(quota, 3)
            q_t = {t: base for t in TER_ORDER}
            # 余数给计数最多的 tercile,平手给 S
            for t in sorted(TER_ORDER,
                            key=lambda t: (-len(by_t[t]), TER_ORDER.index(t))):
                if rema <= 0:
                    break
                q_t[t] += 1
                rema -= 1
            for t in TER_ORDER:
                need = q_t[t]
                have = by_t[t]
                if need > len(have):           # 空层:取整层,记缺口
                    picked += [(r, t) for r in have]
                    if c == "DEPENDENT":
                        shortfall_D += need - len(have)
                    else:
                        shortfall_D += need - len(have)   # 并入 D 补足
                    need = 0
                else:
                    picked += [(r, t) for r in draw(have, need)]
    # 缺口补给:同族 DEPENDENT(RPS>FG>MCS)仍未抽的段,再不足给最大族
    if shortfall_D:
        taken = {r["segment_id"] for r, _ in picked}
        rest = [r for r in by_cls["DEPENDENT"]
                if r["segment_id"] not in taken]
        rest.sort(key=lambda r: (FAM_ORDER.index(r["family"])
                                 if r["family"] in FAM_ORDER else 99,
                                 r["segment_id"]))
        picked += [(r, tercile(int(r["primitive_count"])))
                   for r in rest[:shortfall_D]]
        print(f"空层缺口补给 {min(shortfall_D, len(rest))} 条 → DEPENDENT")

    picked = picked[:N_AUDIT]
    assert len(picked) == N_AUDIT, f"抽样数 {len(picked)} != {N_AUDIT}"

    # ---- manifest 落盘(哈希覆盖注释行以下字节)----------------------------
    fields = ["audit_id", "segment_id", "family", "machine_class",
              "length_tercile", "primitive_count", "task", "seed",
              "node", "t0", "tR"]
    body = ",".join(fields) + "\n"
    for i, (r, t) in enumerate(picked):
        row = {"audit_id": f"dossier_{i:02d}", "segment_id": r["segment_id"],
               "family": r["family"], "machine_class": r["machine_class"],
               "length_tercile": t, "primitive_count": r["primitive_count"],
               "task": r["task"], "seed": r["seed"], "node": r["node"],
               "t0": r["t0"], "tR": r["tR"]}
        body += ",".join(json.dumps(row[k], ensure_ascii=False)
                         for k in fields) + "\n"
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    head = (f"# stageN0_audit_manifest | seed={SEED} | N={N_AUDIT} | "
            f"p33={p33} p66={p66} | q_U={q_U} q_I={q_I} q_D={q_D} | "
            f"eligible={len(eligible)}\n"
            f"# 抽取序=audit_id 序:族{FAM_ORDER}×类{CLS_ORDER}×三分位{TER_ORDER};"
            f"I/U 跨族配额同 D 规则(比例+最大余数,平手 RPS>FG>MCS)\n"
            f"# sha256(以下全部字节)={sha}\n")
    out = REPO / "analysis/stageN0_audit_manifest.csv"
    out.write_text(head + body, encoding="utf-8")
    print(f"-> {out} (sha256={sha})")

    # 抽查分布
    from collections import Counter
    print("family:", dict(Counter(r["family"] for r, _ in picked)))
    print("class:", dict(Counter(r["machine_class"] for r, _ in picked)))
    print("tercile:", dict(Counter(t for _, t in picked)))
    print("task:", dict(Counter(r["task"] for r, _ in picked)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
