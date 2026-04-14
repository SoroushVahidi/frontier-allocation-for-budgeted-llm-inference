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
    p.add_argument(
        "--objective",
        choices=["bt", "davidson", "raokupper"],
        default="bt",
        help="Pairwise objective. Tie-aware variants use explicit tie probability.",
    )
    p.add_argument(
        "--tie-supervision",
        choices=["none", "tie_or_uncertain", "strict_tie"],
        default="none",
        help="How to derive tie labels for tie-aware objectives.",
    )
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


def _softplus(x: float) -> float:
    if x > 40:
        return x
    if x < -40:
        return math.exp(x)
    return math.log1p(math.exp(x))


def _as_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(k, 0.0)) for k in V7_FEATURE_NAMES]


def _safe_log(x: float) -> float:
    return math.log(max(1e-12, min(1.0, x)))


def _class_targets(row: dict[str, Any], soft_uncertain_target: bool, tie_supervision: str) -> tuple[float, float, float]:
    tie_flag = int(row.get("tie", 0)) == 1
    uncertain_flag = int(row.get("tie_or_uncertain", 0)) == 1
    label = float(row.get("preference_label", row.get("a_preferred", 0.0)))
    if tie_supervision == "strict_tie" and tie_flag:
        return 0.0, 0.0, 1.0
    if tie_supervision == "tie_or_uncertain" and (tie_flag or uncertain_flag):
        return 0.0, 0.0, 1.0
    if soft_uncertain_target and uncertain_flag:
        return 0.5, 0.5, 0.0
    if label >= 0.5:
        return 1.0, 0.0, 0.0
    return 0.0, 1.0, 0.0


def _tie_probs(objective: str, delta: float, tie_raw: float) -> tuple[float, float, float]:
    if objective == "bt":
        pa = _sigmoid(delta)
        return pa, 1.0 - pa, 0.0
    if objective == "davidson":
        nu = max(1e-6, math.exp(tie_raw))
        a = math.exp(max(-40.0, min(40.0, delta / 2.0)))
        b = math.exp(max(-40.0, min(40.0, -delta / 2.0)))
        denom = a + b + nu
        return a / denom, b / denom, nu / denom
    # Rao-Kupper tie-aware extension with eta > 1.
    eta = 1.0 + _softplus(tie_raw)
    ed = math.exp(max(-40.0, min(40.0, delta)))
    pa = ed / (ed + eta)
    pb = 1.0 / (1.0 + eta * ed)
    pt = max(1e-12, 1.0 - pa - pb)
    z = pa + pb + pt
    return pa / z, pb / z, pt / z


def _loss_for_row(objective: str, delta: float, tie_raw: float, y_a: float, y_b: float, y_t: float) -> float:
    p_a, p_b, p_t = _tie_probs(objective, delta, tie_raw)
    return -(y_a * _safe_log(p_a) + y_b * _safe_log(p_b) + y_t * _safe_log(max(1e-12, p_t)))


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    rows = _load(Path(args.dataset))
    train_all = [r for r in rows if r.get("split") == "train"]
    test = [r for r in rows if r.get("split") == "test"]

    train: list[dict[str, Any]] = []
    dropped_low_conf = 0
    dropped_uncertain = 0
    for r in train_all:
        confidence = float(r.get("pair_confidence", 1.0))
        tie_or_uncertain = int(r.get("tie_or_uncertain", 0)) == 1
        if confidence < float(args.min_confidence):
            dropped_low_conf += 1
            continue
        if args.drop_uncertain and tie_or_uncertain:
            dropped_uncertain += 1
            continue
        train.append(r)

    w = [0.0 for _ in V7_FEATURE_NAMES]
    b = 0.0
    tie_raw = -2.0

    for _ in range(args.epochs):
        random.shuffle(train)
        for r in train:
            confidence = float(r.get("pair_confidence", 1.0))
            tie_or_uncertain = int(r.get("tie_or_uncertain", 0)) == 1
            xa = _as_vector(r["features_a"])
            xb = _as_vector(r["features_b"])
            y_a, y_b, y_t = _class_targets(r, args.soft_uncertain_target, args.tie_supervision)
            sample_weight = confidence if args.weighting == "confidence" else 1.0
            ra = _dot(w, xa) + b
            rb = _dot(w, xb) + b
            z = ra - rb
            if args.objective == "bt":
                p = _sigmoid(z)
                grad_delta = p - y_a  # d/d(delta) of BT logistic loss.
                grad_tie_raw = 0.0
            else:
                eps = 1e-4
                base_loss = _loss_for_row(args.objective, z, tie_raw, y_a, y_b, y_t)
                grad_delta = (_loss_for_row(args.objective, z + eps, tie_raw, y_a, y_b, y_t) - base_loss) / eps
                grad_tie_raw = (_loss_for_row(args.objective, z, tie_raw + eps, y_a, y_b, y_t) - base_loss) / eps
            for i in range(len(w)):
                w[i] -= args.lr * (sample_weight * grad_delta * (xa[i] - xb[i]) + args.l2 * w[i])
            tie_raw -= args.lr * (sample_weight * grad_tie_raw)
            # shared intercept cancels in z, keep for explicit scalar form.

    def pair_acc(eval_rows: list[dict[str, Any]]) -> float:
        if not eval_rows:
            return 0.0
        ok = 0
        for r in eval_rows:
            xa = _as_vector(r["features_a"])
            xb = _as_vector(r["features_b"])
            z = (_dot(w, xa) + b) - (_dot(w, xb) + b)
            p_a, p_b, _ = _tie_probs(args.objective, z, tie_raw)
            pred = 1 if p_a >= p_b else 0
            if pred == int(r["a_preferred"]):
                ok += 1
        return ok / len(eval_rows)

    def pair_acc_in_bin(eval_rows: list[dict[str, Any]], low: float, high: float) -> float:
        subset = [r for r in eval_rows if low <= float(r.get("pair_confidence", 0.0)) < high]
        return pair_acc(subset)

    model = {
        "model_type": "linear_regression",
        "label_key": "bt_pairwise_a_preferred",
        "training_objective": str(args.objective),
        "tie_supervision": str(args.tie_supervision),
        "inference_mode": "scalar_once_per_branch_argmax",
        "feature_family": "v7_ordered_history",
        "weighting": args.weighting,
        "min_confidence": float(args.min_confidence),
        "drop_uncertain": bool(args.drop_uncertain),
        "soft_uncertain_target": bool(args.soft_uncertain_target),
        "weights": {k: float(v) for k, v in zip(V7_FEATURE_NAMES, w)},
        "intercept": b,
        "tie_raw_parameter": float(tie_raw),
        "tie_parameter_value": (
            float(math.exp(tie_raw))
            if args.objective == "davidson"
            else (float(1.0 + _softplus(tie_raw)) if args.objective == "raokupper" else 0.0)
        ),
        "train_pair_accuracy": pair_acc(train),
        "test_pair_accuracy": pair_acc(test),
        "test_pair_accuracy_low_conf_lt_0.2": pair_acc_in_bin(test, 0.0, 0.2),
        "test_pair_accuracy_mid_conf_0.2_0.5": pair_acc_in_bin(test, 0.2, 0.5),
        "test_pair_accuracy_high_conf_ge_0.5": pair_acc_in_bin(test, 0.5, 1.01),
        "n_train_total": len(train_all),
        "n_train_used": len(train),
        "n_train_dropped_low_conf": dropped_low_conf,
        "n_train_dropped_uncertain": dropped_uncertain,
        "n_train": len(train),
        "n_test": len(test),
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "test_pair_accuracy": model["test_pair_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
