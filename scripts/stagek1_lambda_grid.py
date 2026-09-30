#!/usr/bin/env python
"""Stage K1 λ 网格 —— spec §5 冻结式:VAL 上选一次,全程不触 TEST。

- 网格:{λ_state, λ_trans, λ_harm} = {0.1,0.3,1.0}×{0.3,1.0,3.0}×{0.1,0.5,1.0}
  共 27 组,主检验臂 B2、seed 0、与正式训练同一 run_training 入口
  (minibatch 64 + VAL early-stop);
- 选择准则:VAL 结局 CE 最低(平手取 Brier 低者 —— 网格内同分即按
  参数字典序,记录平手组);
- 产物:analysis/stageK1_lambda_grid.csv(全 27 组)+ 冻结值打印;
  冻结值由人工/后续脚本写回 stageK1_model_spec.md §7(定稿先于正式训练)。

用法:CUDA_VISIBLE_DEVICES=0 python scripts/stagek1_lambda_grid.py
"""
from __future__ import annotations

import csv
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stagek1_train import run_training  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT_CSV = REPO / "analysis/stageK1_lambda_grid.csv"

GRID = {"lambda_state": (0.1, 0.3, 1.0),
        "lambda_transition": (0.3, 1.0, 3.0),
        "lambda_harm": (0.1, 0.5, 1.0)}


def main() -> int:
    rows = []
    for ls, lt, lh in itertools.product(GRID["lambda_state"],
                                        GRID["lambda_transition"],
                                        GRID["lambda_harm"]):
        r = run_training("B2", 0, lam_state=ls, lam_trans=lt, lam_harm=lh,
                         save=False)
        rows.append(r)
        print(f"[grid] λs={ls} λt={lt} λh={lh} -> val_ce="
              f"{r['best_val_ce']:.5f} ({r['epochs_run']} epochs)", flush=True)

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    best = min(rows, key=lambda r: r["best_val_ce"])
    ties = [r for r in rows if abs(r["best_val_ce"] - best["best_val_ce"]) < 1e-6]
    frozen = {"lambda_state": best["lambda_state"],
              "lambda_transition": best["lambda_transition"],
              "lambda_harm": best["lambda_harm"],
              "criterion": "VAL 结局 CE 最低(B2, seed 0)",
              "n_grid": len(rows), "n_ties": len(ties),
              "best_val_ce": best["best_val_ce"]}
    print("\n冻结 λ = " + json.dumps(frozen, ensure_ascii=False), flush=True)
    print(f"-> {OUT_CSV}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
