#!/usr/bin/env python3
"""Stage H2 离线 router benchmark(stageH2_prereg.md §3/§4,冻结定义)。

四 phase 设计(不同 phase 在不同 conda env 里跑):
  --labels   (vla env)  148 点 -> active node / 合法边 / 冻结标签 / 四臂
                        prompt,写 analysis/stageH2_router_items.jsonl
                        并打印标签分布(先于任何模型调用,prereg §3);
  --local    (sglm env) S4-G / S4-NG / S9-G 批量生成(Qwen3.5 本地权重,
                        enable_thinking=False,temperature 0,16 token);
  --teacher  (vla env)  T 臂 = glm-5.3-flash(runtime 同一 anthropic 兼容
                        端点,ANTHROPIC_BASE_URL/KEY 由 env 提供);
  --report   (vla env)  解析 + 指标 + 离线门(prereg §4)。

执行纪律(prereg §6):H1 90 集完成前不跑任何模型调用 phase;
标签 phase 的产物(items.jsonl)是冻结件,模型 phase 只读。

用法:
  python scripts/bench_stageH2_router.py --labels
  /workspace/yjx/envs/sglm/bin/python scripts/bench_stageH2_router.py --local \
      [--model-dir /workspace/yjx/models/Qwen3.5-4B] [--gpus 6]
  python scripts/bench_stageH2_router.py --teacher
  python scripts/bench_stageH2_router.py --report
产物: analysis/stageH2_router_items.jsonl / _raw_<arm>.jsonl /
      stageH2_router_results.md / .json
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

ITEMS = REPO / "analysis/stageH2_router_items.jsonl"
RAW = REPO / "analysis/stageH2_router_raw_{arm}.jsonl"
OUT_MD = REPO / "analysis/stageH2_router_results.md"
OUT_JSON = REPO / "analysis/stageH2_router_results.json"

W = 5                 # §3 标签窗口(与 H1 §5 同)
MAX_NEW_TOKENS = 16   # §4 冻结解码
BANNED = ("fail", "error", "could not", "no object")
LOCAL_ARMS = ("S4G", "S4NG", "S9G")   # 4B+图 / 4B无图 / 9B+图
QWEN_DIR = {"S4G": "/workspace/yjx/models/Qwen3.5-4B",
            "S4NG": "/workspace/yjx/models/Qwen3.5-4B",
            "S9G": "/workspace/yjx/models/Qwen3.5-9B"}

# ---------------------------------------------------------------- 标签 phase


def _rpent_imports():
    from analyze_stageH1 import ACTION_FAMILY_PRIMS, LIFT_OK, MOVE_OK
    from rpent.graph.schema import load_graph
    from rpent.graph.state_interpreter import node_label
    from rpent.graph.retriever import legal_edges
    from rpent.graph.render import NODE_LABELS
    return ACTION_FAMILY_PRIMS, LIFT_OK, MOVE_OK, load_graph, \
        node_label, legal_edges, NODE_LABELS


def _inv_map(af_prims):
    inv = collections.defaultdict(set)
    for af, ps in af_prims.items():
        for p in ps:
            inv[p].add(af)
    return inv


def _lift_ok(r, lift_ok_th):
    return (r.get("success") is True
            and isinstance(r.get("peak_lift_m"), (int, float))
            and r["peak_lift_m"] >= lift_ok_th)


def _find_validating(node, win, lift_ok_th, move_ok_th):
    """§3 冻结规则:返回 (validated, validating_primitive)。"""
    for a, r, term in win:
        if term:
            return True, a
        if node == "FALSE_GRASP":
            if a == "pi0_pick" and _lift_ok(r, lift_ok_th):
                return True, a
        elif node == "MOVE_STALL":
            d = r.get("final_dist_m")
            if a in ("move_to", "move_pose") \
                    and isinstance(d, (int, float)) and d < move_ok_th:
                return True, a
        elif node == "CONTACT_STALL":
            if a == "pi0_doubled" and r.get("success") is True:
                return True, a
            if a == "pi0_pick" and _lift_ok(r, lift_ok_th):
                return True, a
        elif node == "RELEASE_PREDICATE_STALL":
            if a == "pi0_pick" and _lift_ok(r, lift_ok_th):
                return True, a
    return False, None


def _edge_menu_lines(edges):
    """菜单行,逐字复用 render_block 的边渲染词汇(prereg §4)。"""
    return [f"[{e.id}] {e.action_family}\n"
            f"   expected: {e.expected_transition}\n"
            f"   if expected change absent: {e.falsify}"
            for e in edges]


def cmd_labels():
    """148 点 -> 图上下文 + 冻结标签 + 四臂 prompt。"""
    ACTION_FAMILY_PRIMS, LIFT_OK, MOVE_OK, load_graph, node_label, \
        legal_edges, NODE_LABELS = _rpent_imports()
    g = load_graph()
    inv = _inv_map(ACTION_FAMILY_PRIMS)
    pts = [json.loads(l) for l in
           open(REPO / "analysis/stageH0_failure_states.jsonl")]

    ep_cache: dict[str, list] = {}
    lang_cache: dict[str, str] = {}

    def steps_of(path):
        if path not in ep_cache:
            ep_cache[path] = json.load(open(path + "/states.json"))
        return ep_cache[path]

    def task_lang_of(path):
        if path not in lang_cache:
            for s in steps_of(path):
                if s.get("task_language"):
                    lang_cache[path] = str(s["task_language"])
                    break
            else:
                lang_cache[path] = ""
        return lang_cache[path]

    items = []
    stat = collections.Counter()
    for idx, pt in enumerate(pts):
        obs = pt["runtime_view"]["observable_pre_state"]
        node = node_label(obs, obs.get("action", ""))
        edges = legal_edges(g, node, obs)
        src = pt["analysis_only"]["source_path"]
        steps = steps_of(src)
        i = pt["primitive_step"]
        win = []
        for s in steps[i + 1:]:
            a = (s.get("command") or {}).get("action")
            if a is None:
                continue
            win.append((a, s.get("result") or {},
                        bool(s.get("libero_terminated"))))
            if len(win) >= W:
                break
        validated, p = _find_validating(node, win, LIFT_OK, MOVE_OK)
        if not validated:
            label, correct, sub = "DEFER", None, "not_validated"
        else:
            fams = inv.get(p, set())
            corr = [e for e in edges if e.action_family in fams]
            if corr:
                label, correct, sub = "EDGE", [e.id for e in corr], \
                    f"validated:{p}"
            else:
                # out-of-menu 恢复:真实恢复动作不在合法边菜单内
                # -> 正确本地行为 = 升级(prereg §3)
                label, correct, sub = "DEFER", None, f"out_of_menu:{p}"
        stat[f"{label}/{sub.split(':')[0]}" if label == "EDGE" else sub] += 1

        task_lang = task_lang_of(src)
        obs_json = json.dumps(obs, ensure_ascii=False, sort_keys=True)
        pr_graph, defer_g = _prompt_graph(task_lang, node, obs_json,
                                          edges, NODE_LABELS)
        pr_nograph, defer_n = _prompt_nograph(task_lang, obs_json,
                                              list(g.edges))
        # 违禁词硬校验(与 render 同纪律;evidence_id 永不进 prompt)
        for name, pr in (("graph", pr_graph), ("nograph", pr_nograph)):
            low = pr.lower()
            hit = [b for b in BANNED if b in low]
            assert not hit, f"prompt({name}) contains banned {hit}"
        items.append({
            "idx": idx, "evidence_id": pt["evidence_id"],
            "family": pt["failure_family"], "task": pt["task"],
            "seed": pt["seed"], "split": pt["split"],
            "node": node, "legal_edges": [e.id for e in edges],
            "legal_edge_families": [e.action_family for e in edges],
            "label": label, "correct_set": correct, "label_sub": sub,
            "defer_letter_graph": defer_g,
            "defer_letter_nograph": defer_n,
            "prompt_graph": pr_graph, "prompt_nograph": pr_nograph,
            "task_language": task_lang,
        })

    with open(ITEMS, "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    h = hashlib.sha256(open(ITEMS, "rb").read()).hexdigest()
    print(f"wrote {len(items)} items -> {ITEMS}")
    print(f"sha256(items) = {h}")
    print("标签分布(冻结,先于任何模型调用):")
    for k, v in sorted(stat.items()):
        print(f"  {k}: {v}")
    n_edge = sum(1 for it in items if it["label"] == "EDGE")
    print(f"  EDGE {n_edge} / DEFER {len(items) - n_edge} "
          f"/ total {len(items)};全 DEFER 基线 acc = "
          f"{(len(items) - n_edge) / len(items):.1%}")


def _prompt_graph(task_lang, node, obs_json, edges, node_labels):
    """§4 冻结模板(带图臂:T / S4-G / S9-G)。"""
    defer = chr(65 + len(edges))
    lines = ["[EDGE-ROUTER] You route a robot to its next strategy.",
             f"Task: {task_lang}",
             f"active state: {node} — {node_labels.get(node, '')}",
             f"Observable pre-state: {obs_json}",
             "Edges (context, not an order):"]
    for lt, txt in zip((chr(65 + i) for i in range(len(edges))),
                       _edge_menu_lines(edges)):
        lines.append(f"{lt}. {txt}")
    lines.append(f"{defer}. DEFER_TO_TEACHER — escalate this decision "
                 f"to the remote teacher.")
    lines.append("Answer with one letter only.")
    return "\n".join(lines), defer


def _prompt_nograph(task_lang, obs_json, all_edges):
    """§4 冻结模板(S4-NG):无 active state 行,菜单 = 全图边原序。"""
    defer = chr(65 + len(all_edges))
    lines = ["[EDGE-ROUTER] You route a robot to its next strategy.",
             f"Task: {task_lang}",
             f"Observable pre-state: {obs_json}",
             "Edges (context, not an order):"]
    for lt, txt in zip((chr(65 + i) for i in range(len(all_edges))),
                       _edge_menu_lines(all_edges)):
        lines.append(f"{lt}. {txt}")
    lines.append(f"{defer}. DEFER_TO_TEACHER — escalate this decision "
                 f"to the remote teacher.")
    lines.append("Answer with one letter only.")
    return "\n".join(lines), defer


# ------------------------------------------------------------ 模型 phase

def _parse_choice(text, defer_letter):
    """§4 冻结解析:首个字母;= DEFER 位 → DEFER;< DEFER 位 → 该字母;
    超界/无字母 = ILLEGAL(文本以 DEFER 开头亦按 DEFER)。"""
    t = (text or "").strip()
    if t.upper().startswith("DEFER"):
        return "DEFER"
    m = re.search(r"[A-Za-z]", t)
    if not m:
        return "ILLEGAL"
    k = ord(m.group(0).upper()) - 65
    dk = ord(defer_letter) - 65
    if k == dk:
        return "DEFER"
    return m.group(0).upper() if k < dk else "ILLEGAL"


def cmd_local(model_dir, gpus, arms):
    """sglm env 本地推理(Qwen3.5;prereg §4 冻结解码)。"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    items = [json.loads(l) for l in open(ITEMS)]
    for arm in arms:
        if arm not in LOCAL_ARMS:
            raise ValueError(f"unknown local arm {arm}")
        d = QWEN_DIR[arm]
        if not Path(d).exists():
            print(f"[{arm}] weights missing: {d} — skip")
            continue
        with_graph = arm != "S4NG"
        print(f"[{arm}] loading {d} (gpus={gpus}) …")
        tok = AutoTokenizer.from_pretrained(d)
        model = AutoModelForCausalLM.from_pretrained(
            d, dtype=torch.bfloat16).to(f"cuda:{gpus}")
        model.eval()
        out_f = open(RAW.format(arm=arm), "w")
        t0 = time.time()
        for i, it in enumerate(items):
            pr = it["prompt_graph"] if with_graph else it["prompt_nograph"]
            defer = (it["defer_letter_graph"] if with_graph
                     else it["defer_letter_nograph"])
            text = tok.apply_chat_template(
                [{"role": "user", "content": pr}],
                add_generation_prompt=True, tokenize=False,
                enable_thinking=False)
            enc = tok(text, return_tensors="pt").to(f"cuda:{gpus}")
            with torch.no_grad():
                o = model.generate(enc["input_ids"],
                                   max_new_tokens=MAX_NEW_TOKENS,
                                   do_sample=False)
            raw = tok.decode(o[0][enc["input_ids"].shape[1]:],
                             skip_special_tokens=True)
            out_f.write(json.dumps({
                "idx": it["idx"], "arm": arm,
                "parsed": _parse_choice(raw, defer),
                "raw": raw[:64]}, ensure_ascii=False) + "\n")
            if (i + 1) % 25 == 0:
                print(f"[{arm}] {i + 1}/{len(items)} "
                      f"({time.time() - t0:.0f}s)")
        out_f.close()
        print(f"[{arm}] done {len(items)} pts in "
              f"{time.time() - t0:.0f}s -> {RAW.format(arm=arm)}")
        del model
        torch.cuda.empty_cache()


def cmd_teacher():
    """T 臂 = glm-5.3-flash(runtime 同一 anthropic 兼容端点)。"""
    import anthropic
    items = [json.loads(l) for l in open(ITEMS)]
    client = anthropic.Anthropic()   # ANTHROPIC_BASE_URL/KEY 由 env 提供
    model = os.environ.get("STAGEH2_TEACHER_MODEL", "glm-5.3-flash")
    out_f = open(RAW.format(arm="T"), "w")
    t0 = time.time()
    for i, it in enumerate(items):
        raw, err = "", 0
        for attempt in range(3):   # §6:infra ≤3 次重试
            try:
                r = client.messages.create(
                    model=model, max_tokens=MAX_NEW_TOKENS,
                    temperature=0,
                    messages=[{"role": "user",
                               "content": it["prompt_graph"]}])
                raw = "".join(c.text for c in r.content
                              if getattr(c, "type", "") == "text")
                break
            except Exception as ex:  # noqa: BLE001
                err += 1
                print(f"[T] idx={it['idx']} attempt{attempt} error: {ex}")
                time.sleep(3 * (attempt + 1))
        out_f.write(json.dumps({
            "idx": it["idx"], "arm": "T", "retries": err,
            "parsed": _parse_choice(raw, it["defer_letter_graph"]),
            "raw": raw[:64]}, ensure_ascii=False) + "\n")
        if (i + 1) % 25 == 0:
            print(f"[T] {i + 1}/{len(items)} ({time.time() - t0:.0f}s)")
    out_f.close()
    print(f"[T] done in {time.time() - t0:.0f}s")


# ------------------------------------------------------------ 报告 phase

def cmd_report():
    items = [json.loads(l) for l in open(ITEMS)]
    n = len(items)
    preds = {}
    for arm in ("T",) + LOCAL_ARMS:
        p = RAW.format(arm=arm)
        if p.exists():
            preds[arm] = {json.loads(l)["idx"]: json.loads(l)
                          for l in open(p)}
    from rpent.graph.schema import load_graph
    g = load_graph()

    def chosen_edge(arm, it):
        """parsed -> edge_id | DEFER | ILLEGAL(字母映射回菜单)。"""
        pr = preds[arm][it["idx"]]["parsed"]
        if pr in ("DEFER", "ILLEGAL"):
            return pr
        ids = ([e.id for e in g.edges] if arm == "S4NG"
               else list(it["legal_edges"]))
        k = ord(pr) - 65
        return ids[k] if k < len(ids) else "ILLEGAL"

    def acc_of(arm):
        if arm not in preds:
            return None
        hit = legal = 0
        act_hit = act_n = defer_n = 0
        for it in items:
            ch = chosen_edge(arm, it)
            if ch not in ("ILLEGAL",):
                legal += 1
            if it["label"] == "EDGE":
                act_n += 1
                if ch in it["correct_set"]:
                    act_hit += 1
                    hit += 1
            else:
                if ch == "DEFER":
                    hit += 1
                defer_n += 1
        return {"n": n, "legal": legal,
                "legal_rate": legal / n,
                "acc": hit / n, "active_acc": act_hit / act_n,
                "active_n": act_n, "defer_rate": defer_n / n}

    res = {a: acc_of(a) for a in ("T",) + LOCAL_ARMS if a in preds}
    agree = None
    if "T" in preds and "S4G" in preds:
        same = sum(1 for it in items
                   if chosen_edge("T", it) == chosen_edge("S4G", it))
        agree = same / n

    # 离线门(prereg §4)
    g1 = res.get("S4G") and res["S4G"]["legal_rate"] >= 0.90
    g2 = (res.get("S4G") and res.get("T")
          and res["S4G"]["acc"] >= res["T"]["acc"] - 0.05)
    g3 = (res.get("S4G") and res.get("S4NG")
          and res["S4G"]["acc"] >= res["S4NG"]["acc"] + 0.08)
    s9 = res.get("S9G")
    verdict = None
    if res.get("S4G"):
        s4_pass = g1 and g2 and g3
        if s4_pass:
            verdict = "OFFLINE GATE PASS(4B)"
        elif s9 and s9["legal_rate"] >= 0.90 \
                and s9["acc"] >= (res["T"]["acc"] if res.get("T") else 1) - 0.05 \
                and s9["acc"] >= (res["S4NG"]["acc"]
                                  if res.get("S4NG") else 0) + 0.08:
            verdict = "4B FAIL + 9B PASS = CAPACITY BOTTLENECK"
        else:
            verdict = "BOTH FAIL(或 9B 缺失)= REPRESENTATION PROBLEM"

    L = []
    A = L.append
    A("# Stage H2 离线 router benchmark 结果\n")
    A("_由 scripts/bench_stageH2_router.py 生成;定义 = "
      "analysis/stageH2_prereg.md §3/§4(冻结)。_\n")
    A(f"- items: {n} 点;EDGE 标签 "
      f"{sum(1 for i in items if i['label'] == 'EDGE')} / DEFER "
      f"{sum(1 for i in items if i['label'] == 'DEFER')}")
    A(f"- T-S4G 逐点一致率: {agree if agree is None else f'{agree:.1%}'}"
      if agree is not None else "- T-S4G 一致率: N/A")
    A("\n| 臂 | legal_rate | acc(全点) | active_acc | defer_rate |")
    A("|---|---|---|---|---|")
    for a, r in res.items():
        A(f"| {a} | {r['legal_rate']:.1%} | {r['acc']:.1%} | "
          f"{r['active_acc']:.1%} ({r['active_n']}) | "
          f"{r['defer_rate']:.1%} |")
    A("\n## 离线门\n| 门 | 定义 | 实测 | 判定 |\n|---|---|---|---|")
    A(f"| 1 legal | S4-G ≥ 90% | "
      f"{res['S4G']['legal_rate']:.1%} | "
      f"{'PASS' if g1 else 'FAIL'} |" if res.get("S4G") else
      "| 1 legal | S4-G ≥ 90% | 缺 | N/A |")
    A(f"| 2 acc | S4-G ≥ T−5pp | "
      f"{res['S4G']['acc']:.1%} vs "
      f"{res['T']['acc']:.1%} | {'PASS' if g2 else 'FAIL'} |"
      if res.get("S4G") and res.get("T") else
      "| 2 acc | S4-G ≥ T−5pp | 缺 | N/A |")
    A(f"| 3 graph | S4-G ≥ S4-NG+8pp | "
      f"{res['S4G']['acc']:.1%} vs "
      f"{res['S4NG']['acc']:.1%} | {'PASS' if g3 else 'FAIL'} |"
      if res.get("S4G") and res.get("S4NG") else
      "| 3 graph | S4-G ≥ S4-NG+8pp | 缺 | N/A |")
    A(f"\n## 判定\n**{verdict}**\n")
    OUT_MD.write_text("\n".join(L))
    payload = {"arms": res, "agreement_T_S4G": agree,
               "gates": {"legal": g1, "acc": g2, "graph": g3},
               "verdict": verdict,
               "items_sha256": hashlib.sha256(
                   open(ITEMS, "rb").read()).hexdigest()}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--teacher", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--model-dir", default=None,
                    help="覆盖 S4G/S4NG 模型目录(默认 QWEN_DIR)")
    ap.add_argument("--gpus", type=int, default=6,
                    help="本地推理用的单卡 index(默认 6)")
    ap.add_argument("--arms", default=",".join(LOCAL_ARMS),
                    help="本地臂子集,如 S4G,S4NG")
    args = ap.parse_args()
    if args.model_dir:
        QWEN_DIR["S4G"] = QWEN_DIR["S4NG"] = args.model_dir
    if args.labels:
        cmd_labels()
    elif args.local:
        cmd_local(args.model_dir, args.gpus,
                  [a for a in args.arms.split(",") if a])
    elif args.teacher:
        cmd_teacher()
    elif args.report:
        cmd_report()
    else:
        ap.error("选一个 phase:--labels / --local / --teacher / --report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
