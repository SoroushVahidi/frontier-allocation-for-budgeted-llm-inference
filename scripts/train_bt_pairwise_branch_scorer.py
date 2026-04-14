#!/usr/bin/env python3
"""Train scalar branch utility model with Bradley-Terry pairwise objective.

Training supervision is pairwise, but inference is scalar: r(branch)=w·x+b.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import V7_FEATURE_NAMES


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train BT pairwise scalar scorer")
    p.add_argument("--dataset", default="outputs/branch_scorer_v3/bt_pairwise_dataset.jsonl")
    p.add_argument("--output", default="outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v7_bt.json")
    p.add_argument("--epochs", type=int, default=35)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--l2", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--weighting", choices=["none", "confidence"], default="none")
    p.add_argument("--min-confidence", type=float, default=0.0, help="Drop training pairs below this pair_confidence.")
    p.add_argument("--drop-uncertain", action="store_true")
    p.add_argument("--soft-uncertain-target", action="store_true")
    return p.parse_args()


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _dot(weights: list[float], x: list[float]) -> float:
    return sum(w * v for w, v in zip(weights, x))


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _as_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(k, 0.0)) for k in V7_FEATURE_NAMES]


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    rows = _load(Path(args.dataset))
    train = [r for r in rows if r.get("split") == "train"]
    test = [r for r in rows if r.get("split") == "test"]

    w = [0.0 for _ in V7_FEATURE_NAMES]
    b = 0.0

    for _ in range(args.epochs):
        random.shuffle(train)
        for r in train:
            confidence = float(r.get("pair_confidence", 1.0))
            tie_or_uncertain = int(r.get("tie_or_uncertain", 0)) == 1
            if confidence < float(args.min_confidence):
                continue
            if args.drop_uncertain and tie_or_uncertain:
                continue
            xa = _as_vector(r["features_a"])
            xb = _as_vector(r["features_b"])
            if args.soft_uncertain_target and tie_or_uncertain:
                y = 0.5
            else:
                y = float(r.get("preference_label", r.get("a_preferred", 0.0)))
            sample_weight = confidence if args.weighting == "confidence" else 1.0
            ra = _dot(w, xa) + b
            rb = _dot(w, xb) + b
            z = ra - rb
            p = _sigmoid(z)
            grad = p - y  # d/dz of BT logistic loss
            for i in range(len(w)):
                w[i] -= args.lr * (sample_weight * grad * (xa[i] - xb[i]) + args.l2 * w[i])
            # shared intercept cancels in z, keep for explicit scalar form.

    def pair_acc(eval_rows: list[dict[str, Any]]) -> float:
        if not eval_rows:
            return 0.0
        ok = 0
        for r in eval_rows:
            xa = _as_vector(r["features_a"])
            xb = _as_vector(r["features_b"])
            z = (_dot(w, xa) + b) - (_dot(w, xb) + b)
            pred = 1 if z >= 0 else 0
            if pred == int(r["a_preferred"]):
                ok += 1
        return ok / len(eval_rows)

    model = {
        "model_type": "linear_regression",
        "label_key": "bt_pairwise_a_preferred",
        "training_objective": "Bradley-Terry pairwise logistic on scalar utility differences",
        "inference_mode": "scalar_once_per_branch_argmax",
        "feature_family": "v7_ordered_history",
        "weighting": args.weighting,
        "min_confidence": float(args.min_confidence),
        "drop_uncertain": bool(args.drop_uncertain),
        "soft_uncertain_target": bool(args.soft_uncertain_target),
        "weights": {k: float(v) for k, v in zip(V7_FEATURE_NAMES, w)},
        "intercept": b,
        "train_pair_accuracy": pair_acc(train),
        "test_pair_accuracy": pair_acc(test),
        "n_train": len(train),
        "n_test": len(test),
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "test_pair_accuracy": model["test_pair_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
