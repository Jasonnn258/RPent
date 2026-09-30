#!/usr/bin/env python
"""Stage K1 训练 —— B0/B1/B2/B3 四臂(spec:stageK1_model_spec.md,先冻结后训)。

样本 = (snapshot, edge, rollout);特征来自 stageK1_feature_store.npz
(冻结 DINOv2,不训练),标签来自 verifier 通道(只作训练目标)。

- B0 STATE_ONLY:s → MLP
- B1 STATIC_VISUAL:s + z_pre → MLP
- B2 GRAPH_WORLD_MODEL:s + z_pre + edge_emb → GRUCell latent 转移 +
  MDN 物理量分布头 + 温度缩放结局头(分布头,主检验臂)
- B3 ORACLE_FUTURE:s + z_pre + z_post → MLP(analysis only,永不进 K2)

用法:python scripts/stagek1_train.py --arm B2 --seed 0 [--epochs 80]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "analysis/stageK1_feature_store.npz"
MANIFEST = REPO / "analysis/stageK_transition_dataset_manifest.csv"
OUTDIR = REPO / "logs/stageK1"

TASKS = [3, 5, 9]          # 数据集实际出现的 task
FAMS = ["FALSE_GRASP", "RELEASE_PREDICATE_STALL"]


# ---------------------------------------------------------------------------
# 数据
# ---------------------------------------------------------------------------

def load_samples() -> tuple[list[dict], list[str]]:
    import csv
    store = np.load(STORE)
    rows = list(csv.DictReader(open(MANIFEST)))
    edges = sorted({r["edge_id"] for r in rows})
    samples = []
    for r in rows:
        rid = r["sample_id"]
        z_pre = np.concatenate([store[f"{rid}|f0"], store[f"{rid}|f1"]])
        z_post = np.concatenate([store[f"{rid}|f2"], store[f"{rid}|f3"]])
        task = int(r["snapshot_id"][1])  # t3/t5/t9 → 3/5/9
        s = np.zeros(3 + 1 + len(TASKS) + len(FAMS) + len(edges))
        s[0:3] = [float(r["eef_x"]), float(r["eef_y"]), float(r["eef_z"])]
        s[3] = float(r["grip"] or 0.0)
        s[4 + TASKS.index(task)] = 1.0
        s[4 + len(TASKS) + FAMS.index(r["family"])] = 1.0
        s[4 + len(TASKS) + len(FAMS) + edges.index(r["edge_id"])] = 1.0
        y = {"VERIFIED_RECOVERY": 0, "NO_EFFECT": 1, "HARM": 2}[r["outcome"]]
        phys = np.array([
            float(r["max_d_eef_z"] or 0.0),
            float(r["d_ooi_z"] or 0.0),
            float(r["resid_drop"] or 0.0),
        ])
        samples.append({
            "rid": rid, "split": r["split"], "snapshot": r["snapshot_id"],
            "edge": r["edge_id"], "family": r["family"], "s": s,
            "z_pre": z_pre, "z_post": z_post, "y": y,
            "harm": float(y == 2), "phys": phys,
        })
    return samples, edges


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------

class MDNHead(nn.Module):
    """2 分量高斯混合(dim 维物理量)—— 分布头,不确定性走集成。"""

    def __init__(self, dim_in: int, dim_out: int = 3, k: int = 2):
        super().__init__()
        self.k = k
        self.net = nn.Linear(dim_in, k * (2 + dim_out))

    def loss(self, h, target):
        o = self.net(h).view(-1, self.k, 2 + target.shape[-1])
        pi, mu, logvar = o[..., 0], o[..., 1], o[..., 2]
        logvar = logvar.clamp(-6, 6)
        norm = torch.distributions.Normal(mu, logvar.exp())
        ll = norm.log_prob(target.unsqueeze(1)).sum(-1)  # [B,k]
        log_pi = torch.log_softmax(pi, -1)
        return -torch.logsumexp(log_pi + ll, -1).mean()


class OutcomeHead(nn.Module):
    """3 类结局 + 温度缩放(可学 T,Brier/NLL 校准)。"""

    def __init__(self, dim_in: int):
        super().__init__()
        self.net = nn.Linear(dim_in, 3)
        self.log_T = nn.Parameter(torch.zeros(1))

    def logits(self, h):
        return self.net(h) / self.log_T.exp()


class Arm(nn.Module):
    """四臂统一外壳;差异只在 encode()。"""

    def __init__(self, arm: str, s_dim: int, z_dim: int = 3072,
                 n_edges: int = 8, h: int = 512):
        super().__init__()
        self.arm = arm
        self.edge_emb = nn.Embedding(n_edges, 64)
        in_z = z_dim * (2 if arm == "B3" else 1)
        self.z_proj = nn.Sequential(nn.Linear(in_z, h), nn.GELU())
        self.state_proj = nn.Sequential(nn.Linear(s_dim, h), nn.GELU())
        if arm == "B2":
            self.cell = nn.GRUCell(h, h)
            self.zpost_head = nn.Linear(h, z_dim)
        fuse = h * (2 if arm == "B2" else 1)
        self.trunk = nn.Sequential(nn.Linear(fuse, h), nn.GELU(),
                                   nn.Linear(h, h), nn.GELU())
        self.outcome = OutcomeHead(h)
        self.harm = nn.Linear(h, 1)
        self.mdn = MDNHead(h, 3)

    def encode(self, batch, edge_idx):
        h0 = self.state_proj(batch["s"]) + self.z_proj(batch["z"])
        if self.arm == "B0":
            return h0, None
        if self.arm in ("B1", "B3"):
            return h0, None
        h1 = self.cell(h0, self.edge_emb(edge_idx))
        return h0, h1

    def forward(self, batch, edge_idx):
        h0, h1 = self.encode(batch, edge_idx)
        fused = torch.cat([h0, h1], -1) if h1 is not None else h0
        h = self.trunk(fused)
        return {"logits": self.outcome.logits(h),
                "harm": self.harm(h).squeeze(-1),
                "mdn_h": h, "h1": h1}


# ---------------------------------------------------------------------------
# 训练
# ---------------------------------------------------------------------------

def batchify(samples, device):
    return {
        "s": torch.tensor(np.stack([x["s"] for x in samples]), dtype=torch.float32, device=device),
        "z": torch.tensor(np.stack([x["z_pre"] for x in samples]), dtype=torch.float32, device=device),
        "z_post": torch.tensor(np.stack([x["z_post"] for x in samples]), dtype=torch.float32, device=device),
        "y": torch.tensor([x["y"] for x in samples], device=device),
        "harm": torch.tensor([x["harm"] for x in samples], dtype=torch.float32, device=device),
        "phys": torch.tensor(np.stack([x["phys"] for x in samples]), dtype=torch.float32, device=device),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", required=True, choices=["B0", "B1", "B2", "B3"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--lambda-state", type=float, default=0.3)
    ap.add_argument("--lambda-transition", type=float, default=1.0)
    ap.add_argument("--lambda-harm", type=float, default=0.5)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    samples, edges = load_samples()
    edge_ix = {e: i for i, e in enumerate(edges)}
    tr = [x for x in samples if x["split"] == "TRAIN"]
    va = [x for x in samples if x["split"] == "VAL"]
    if not tr or not va:
        raise SystemExit("TRAIN/VAL 为空 —— 检查 manifest")
    print(f"[{args.arm}s{args.seed}] TRAIN {len(tr)} VAL {len(va)} "
          f"edges {edges}", flush=True)

    model = Arm(args.arm, s_dim=len(tr[0]["s"]), n_edges=len(edges)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    bt, bv = batchify(tr, device), batchify(va, device)
    if args.arm == "B3":  # oracle 输入 = z_pre ⊕ z_post
        bt["z"] = torch.cat([bt["z"], bt["z_post"]], -1)
        bv["z"] = torch.cat([bv["z"], bv["z_post"]], -1)
    et = torch.tensor([edge_ix[x["edge"]] for x in tr], device=device)
    ev = torch.tensor([edge_ix[x["edge"]] for x in va], device=device)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    ckpt = OUTDIR / f"ckpt_{args.arm}_s{args.seed}.pt"
    hist_path = OUTDIR / f"hist_{args.arm}_s{args.seed}.jsonl"
    best, best_state, best_epoch, hist = 1e9, None, -1, []
    ce = nn.CrossEntropyLoss()
    bce = nn.BCEWithLogitsLoss()
    cos = nn.CosineSimilarity(dim=-1)

    for epoch in range(args.epochs):
        model.train()
        opt.zero_grad()
        out = model(bt, et)
        l_trans = ce(out["logits"], bt["y"])
        l_harm = bce(out["harm"], bt["harm"])
        l_state = model.mdn.loss(out["mdn_h"], bt["phys"])
        loss = args.lambda_transition * l_trans + args.lambda_harm * l_harm \
            + args.lambda_state * l_state
        if args.arm == "B2":  # L_latent:ẑ_post vs 冻结 DINOv2 z_post
            z_hat = model.zpost_head(out["h1"])
            l_lat = (1 - cos(z_hat, bt["z_post"]).mean()) \
                + (z_hat - bt["z_post"]).pow(2).mean()
            loss = loss + l_lat
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            ov = model(bv, ev)
            vl = ce(ov["logits"], bv["y"]).item()
        hist.append({"epoch": epoch, "train_loss": round(loss.item(), 5),
                     "val_ce": round(vl, 5)})
        if vl < best - 1e-5:
            best, best_state, best_epoch = vl, \
                {k: v.detach().clone() for k, v in model.state_dict().items()}, epoch
        elif epoch - best_epoch > 10:  # early stop patience 10
            break

    model.load_state_dict(best_state)
    meta = {
        "arm": args.arm, "seed": args.seed,
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO,
            capture_output=True, text=True).stdout.strip(),
        "config": vars(args),
        "config_hash": hashlib.md5(json.dumps(vars(args)).encode()).hexdigest()[:12],
        "split_hash": hashlib.md5("".join(
            sorted(f"{x['rid']}:{x['split']}" for x in samples)).encode()).hexdigest()[:12],
        "encoder": json.load(open(REPO / "analysis/stageK1_encoder_fingerprint.json")),
        "edge_vocab": edges, "best_val_ce": best, "epochs_run": len(hist),
    }
    torch.save({"state_dict": model.state_dict(), "meta": meta}, ckpt)
    hist_path.write_text("\n".join(json.dumps(h) for h in hist))
    print(f"[{args.arm}s{args.seed}] done: best_val_ce={best:.5f} "
          f"({len(hist)} epochs) -> {ckpt.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
