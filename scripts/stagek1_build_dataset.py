#!/usr/bin/env python
"""Stage K1 — 训练数据装配(rollouts jsonl → 特征/标签存储 + split manifest)。

职责(全部离线、确定性):
- final_step 重建:采集记录未存该字段(采集器补丁晚于启动),按
  states.json 条目顺序与记录内 chain 工具序列 + 窗口步数逐条对齐重建
  (对不齐即报错,不留静默近似);
- 特征:冻结 DINOv2(stagek_fetch_dinov2.py 已拉取)对每快照 z_pre
  (hi-res 拷出帧,agentview+wrist)与每 rollout z_post(低清终帧)前向,
  patch-token 均值 + CLS 拼接 → 特征存储 npz;
- 标签:outcome 3 类 / harm / 物理量(Δeef_z, Δgrip, Δooi_z, 残差降)
  —— 全部来自采集时 verifier 通道,只作训练目标;
- 切分:selection json 的 split 逐快照透传(同快照全部 rollout 同 split,
  spec §3);
- 产物:analysis/stageK1_feature_store.npz +
  analysis/stageK_transition_dataset_manifest.csv(spec §15,TEST 于此冻结)。

用法:python scripts/stagek1_build_dataset.py [--rollouts ...jsonl]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENCODER_FP = REPO / "analysis/stageK1_encoder_fingerprint.json"


# ---------------------------------------------------------------------------
# final_step 重建
# ---------------------------------------------------------------------------

def rebuild_final_steps(states_path: Path, recs: list[dict]) -> list[int]:
    """按 states.json 条目顺序给每个 rollout 记录定位终帧 step。

    每条 rollout 消费 len(chain) + n_window 个带 command 的条目
    (chain 工具序列必须逐一吻合;n_window = samples 里 win* 条数);
    command 为 None 的条目(快照 dump)跳过。返回与 recs 对齐的 final_step。
    """
    entries = json.load(open(states_path))
    i = 0
    finals = []
    for r in recs:
        chain_tools = [c["tool"] for c in (r.get("chain") or [])]
        n_win = sum(1 for t, _ in (r.get("samples") or []) if t.startswith("win"))
        expect = chain_tools + ["set_gripper"] * n_win
        consumed = 0
        last_step = None
        while consumed < len(expect):
            if i >= len(entries):
                raise RuntimeError(
                    f"{states_path}: 条目耗尽于 rollout "
                    f"{r['edge_id']} k={r['k']}(期望 {expect})")
            e = entries[i]
            i += 1
            cmd = e.get("command") or {}
            if not cmd:
                continue  # 快照 dump / inspection 条目
            act = cmd.get("action")
            if act != expect[consumed]:
                raise RuntimeError(
                    f"{states_path}: rollout {r['edge_id']} k={r['k']} 第 "
                    f"{consumed} 步期望 {expect[consumed]} 实得 {act}(idx {i})")
            consumed += 1
            last_step = e.get("step_idx")
        if last_step is None:
            raise RuntimeError(f"{states_path}: rollout 无终帧 step")
        finals.append(int(last_step))
    return finals


# ---------------------------------------------------------------------------
# DINOv2 特征
# ---------------------------------------------------------------------------

def load_encoder():
    import os
    fp = json.load(open(ENCODER_FP))
    os.environ.setdefault("HF_HOME", "/workspace/yjx/rpent_data/.cache/huggingface")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import torch
    from transformers import AutoImageProcessor, AutoModel
    proc = AutoImageProcessor.from_pretrained(fp["model_id"])
    enc = AutoModel.from_pretrained(fp["model_id"]).eval()
    assert fp["probe_output_shape"][1] == 257  # 256 patch + CLS,冻结指纹校验
    return proc, enc, fp


def embed_frames(proc, enc, paths: list[Path]) -> dict[str, list]:
    """每帧 → [patch_mean(768) ⊕ CLS(768)] = 1536 维;返回按输入序的数组。"""
    import numpy as np
    import torch
    from PIL import Image
    feats = []
    for p in paths:
        img = Image.open(p).convert("RGB")
        x = proc(images=img, return_tensors="pt")
        with torch.no_grad():
            out = enc(**x).last_hidden_state[0]  # [257, 768]
        patch, cls = out[:-1].mean(0), out[-1]
        feats.append(torch.cat([patch, cls]).numpy())
    return {"features": feats}


# ---------------------------------------------------------------------------
# 装配
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rollouts",
                    default="analysis/stageK_transition_rollouts.jsonl")
    ap.add_argument("--selection",
                    default="analysis/stageK_dataset_selection.json")
    ap.add_argument("--log-root", default="logs/stageK_dataset")
    ap.add_argument("--store", default="analysis/stageK1_feature_store.npz")
    ap.add_argument("--manifest",
                    default="analysis/stageK_transition_dataset_manifest.csv")
    args = ap.parse_args()

    recs = [json.loads(l) for l in open(REPO / args.rollouts)]
    recs = [r for r in recs if r.get("outcome") and not r.get("infra_error")]
    selection = json.load(open(REPO / args.selection))
    split_by_snap = {s["snapshot_id"]: s["split"] for s in selection["snapshots"]}
    cal_snaps = {s["snapshot_id"] for s in json.load(
        open(REPO / "analysis/stageK0_snapshot_selection.json"))["snapshots"]}
    leaked = cal_snaps & split_by_snap.keys()
    assert not leaked, f"校准快照泄入数据集: {leaked}"

    # 按快照分组(保持采集顺序 = legal_edges × k 升序)
    by_snap: dict[str, list] = defaultdict(list)
    for r in recs:
        by_snap[r["snapshot_id"]].append(r)

    proc, enc, fp = load_encoder()
    import numpy as np

    store: dict[str, np.ndarray] = {}
    rows = []
    n_rgb_missing = 0
    for snap_id, rs in by_snap.items():
        rgb = rs[0].get("snapshot_rgb") or {}
        outdir = Path(args.log_root) / rgb.get("outdir", "")
        # final_step 重建(该快照所有 rollout 一次走完)
        finals = rebuild_final_steps(outdir / "states.json", rs)
        # z_pre:hi-res 拷出帧中**仅 RGB**(world npy 是深度/世界坐标,
        # 不进 encoder,留 analysis_only);z_post:低清终帧
        z_pre_paths = [outdir / c for c in rgb.get("copied", [])]
        z_pre_paths = [p for p in z_pre_paths
                       if p.exists() and p.suffix == ".png"]
        for r, fin in zip(rs, finals):
            rid = f"{snap_id}|{r['edge_id']}|k{r['k']}"
            post = outdir / "images" / f"image_{fin:02d}.png"
            post_w = outdir / "images_wrist" / f"image_wrist_{fin:02d}.png"
            if not (post.exists() and post_w.exists()) or not z_pre_paths:
                n_rgb_missing += 1
                continue
            paths = z_pre_paths + [post, post_w]
            emb = embed_frames(proc, enc, paths)
            for j, arr in enumerate(emb["features"]):
                store[f"{rid}|f{j}"] = arr
            v = r.get("verify") or {}
            base = (r.get("samples") or [({}, None)])[0][1] or {}
            rows.append({
                "sample_id": rid, "snapshot_id": snap_id,
                "edge_id": r["edge_id"], "family": r["family"],
                "k": r["k"], "split": split_by_snap[snap_id],
                "outcome": r["outcome"], "perception_found": r.get("perception_found"),
                "final_step": fin,
                # s 向量原始量(runtime 可见本体通道;GT 物体位姿不进)
                "eef_x": base.get("eef", [None]*3)[0],
                "eef_y": base.get("eef", [None]*3)[1],
                "eef_z": base.get("eef", [None]*3)[2],
                "grip": base.get("grip"),
                "d_ooi_z": v.get("d_ooi_z"), "max_d_eef_z": v.get("max_d_eef_z"),
                "resid_drop": (v.get("resid_0") - v.get("resid_T"))
                if v.get("resid_0") is not None and v.get("resid_T") is not None else None,
                "delta_grip": v.get("min_grip"),
                "n_frames": len(paths), "rgb_dir": rgb.get("outdir", ""),
            })

    np.savez_compressed(REPO / args.store, **store)
    with open(REPO / args.manifest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    import collections
    print(f"样本 {len(rows)}(RGB 缺失跳过 {n_rgb_missing})| 特征 {len(store)} 条")
    print("split×family:", dict(collections.Counter(
        (r["split"], r["family"]) for r in rows)))
    print("outcome:", dict(collections.Counter(r["outcome"] for r in rows)))
    print(f"-> {args.store} / {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
