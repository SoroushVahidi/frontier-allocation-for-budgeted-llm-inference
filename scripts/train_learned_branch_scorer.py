#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_int, group_by_case, read_csv, write_csv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train lightweight diagnostic learned branch scorer models.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--dataset-examples", required=True)
    p.add_argument("--save-model-text", action="store_true", default=True)
    return p.parse_args()


def _safe_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    uniq = np.unique(y_true)
    if uniq.size < 2:
        return float("nan")
    return float(roc_auc_score(y_true, y_score))


def _to_feature_dict(row: dict[str, Any], feature_names: list[str], categorical: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in feature_names:
        value = row.get(key, "")
        if key in categorical:
            out[key] = str(value or "")
        else:
            out[key] = float(value) if str(value).strip() not in {"", "nan", "None"} else 0.0
    return out


def _top1_group_accuracy(rows: list[dict[str, Any]], score_key: str = "score") -> float:
    grouped = group_by_case(rows)
    wins = 0
    total = 0
    for _, cell in grouped.items():
        if not cell:
            continue
        best = max(cell, key=lambda r: float(r.get(score_key, 0.0)))
        wins += as_int(best.get("label"), 0)
        total += 1
    return wins / max(1, total)


def _pns_rate(rows: list[dict[str, Any]], score_key: str) -> float:
    grouped = group_by_case(rows)
    miss = 0
    denom = 0
    for _, cell in grouped.items():
        gold_present = any(as_int(r.get("label"), 0) == 1 for r in cell)
        if not gold_present:
            continue
        denom += 1
        best = max(cell, key=lambda r: float(r.get(score_key, 0.0)))
        if as_int(best.get("label"), 0) == 0:
            miss += 1
    return miss / max(1, denom)


def _strict_f3_pns_rate(rows: list[dict[str, Any]]) -> float:
    grouped = group_by_case(rows)
    miss = 0
    denom = 0
    for _, cell in grouped.items():
        gold_present = any(as_int(r.get("label"), 0) == 1 for r in cell)
        strict = next((r for r in cell if str(r.get("method")) == "strict_f3"), None)
        if not gold_present or strict is None:
            continue
        denom += 1
        if as_int(strict.get("label"), 0) == 0:
            miss += 1
    return miss / max(1, denom)


def _split_masks(rows: list[dict[str, Any]]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    seeds = np.array([as_int(r.get("seed"), -1) for r in rows])
    budgets = np.array([as_int(r.get("budget"), -1) for r in rows])
    return {
        "seed_holdout": (seeds == 11, seeds == 23),
        "budget_holdout": (np.isin(budgets, [4, 6]), budgets == 8),
        "joint_holdout": ((seeds == 11) & (np.isin(budgets, [4, 6])), (seeds == 23) & (budgets == 8)),
    }


def main() -> None:
    args = parse_args()
    rows = read_csv(REPO_ROOT / args.dataset_examples)
    if not rows:
        raise SystemExit("No rows found in dataset examples csv.")

    label_key = "label"
    feature_drop = {"label", "case_id", "example_id", "label_semantics", "candidate_answer_normalized"}
    feature_names = [k for k in rows[0].keys() if k not in feature_drop]
    categorical = {
        "provider",
        "model",
        "dataset",
        "method",
        "runtime_method",
        "group",
        "failure_type",
        "selected_answer_group",
        "top_answer_group",
    }

    X = [_to_feature_dict(r, feature_names, categorical) for r in rows]
    y = np.array([as_int(r.get(label_key), 0) for r in rows])

    vectorizer = DictVectorizer(sparse=False)
    X_mat = vectorizer.fit_transform(X)
    models = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=0),
        "random_forest": RandomForestClassifier(n_estimators=120, random_state=0, min_samples_leaf=2),
        "gradient_boosting": GradientBoostingClassifier(random_state=0),
    }

    splits = _split_masks(rows)
    split_metrics: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    model_comparison: list[dict[str, Any]] = []

    for split_name, (train_mask, test_mask) in splits.items():
        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        if train_idx.size == 0 or test_idx.size == 0:
            continue

        X_train = X_mat[train_idx]
        y_train = y[train_idx]
        X_test = X_mat[test_idx]
        y_test = y[test_idx]

        for model_name, model in models.items():
            model.fit(X_train, y_train)
            y_score = model.predict_proba(X_test)[:, 1]
            y_pred = (y_score >= 0.5).astype(int)

            pred_rows: list[dict[str, Any]] = []
            for local_i, global_i in enumerate(test_idx):
                row = dict(rows[int(global_i)])
                row.update({"split": split_name, "model": model_name, "score": float(y_score[local_i]), "pred": int(y_pred[local_i])})
                pred_rows.append(row)
                all_predictions.append(row)

            strict_pns = _strict_f3_pns_rate(pred_rows)
            learned_pns = _pns_rate(pred_rows, "score")
            top1 = _top1_group_accuracy(pred_rows, "score")
            metrics_row = {
                "split": split_name,
                "model": model_name,
                "n_train": int(train_idx.size),
                "n_test": int(test_idx.size),
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                "auc": _safe_auc(y_test, y_score),
                "top1_group_selection_accuracy": float(top1),
                "strict_f3_present_not_selected_rate": float(strict_pns),
                "learned_present_not_selected_rate": float(learned_pns),
                "present_not_selected_reduction_potential": float(strict_pns - learned_pns),
                "score_mean": float(np.mean(y_score)),
                "score_std": float(np.std(y_score)),
            }
            split_metrics.append(metrics_row)

    if not split_metrics:
        n = len(rows)
        cut = max(1, int(0.8 * n))
        train_idx = np.arange(0, cut)
        test_idx = np.arange(cut, n)
        if test_idx.size == 0:
            test_idx = train_idx
        X_train = X_mat[train_idx]
        y_train = y[train_idx]
        X_test = X_mat[test_idx]
        y_test = y[test_idx]
        for model_name, model in models.items():
            model.fit(X_train, y_train)
            y_score = model.predict_proba(X_test)[:, 1]
            y_pred = (y_score >= 0.5).astype(int)
            pred_rows: list[dict[str, Any]] = []
            for local_i, global_i in enumerate(test_idx):
                row = dict(rows[int(global_i)])
                row.update({"split": "fallback_random", "model": model_name, "score": float(y_score[local_i]), "pred": int(y_pred[local_i])})
                pred_rows.append(row)
                all_predictions.append(row)
            split_metrics.append(
                {
                    "split": "fallback_random",
                    "model": model_name,
                    "n_train": int(train_idx.size),
                    "n_test": int(test_idx.size),
                    "accuracy": float(accuracy_score(y_test, y_pred)),
                    "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                    "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                    "auc": _safe_auc(y_test, y_score),
                    "top1_group_selection_accuracy": float(_top1_group_accuracy(pred_rows, "score")),
                    "strict_f3_present_not_selected_rate": float(_strict_f3_pns_rate(pred_rows)),
                    "learned_present_not_selected_rate": float(_pns_rate(pred_rows, "score")),
                    "present_not_selected_reduction_potential": float(_strict_f3_pns_rate(pred_rows) - _pns_rate(pred_rows, "score")),
                    "score_mean": float(np.mean(y_score)),
                    "score_std": float(np.std(y_score)),
                }
            )

    # choose selected model from joint_holdout by top1 then accuracy
    joint_rows = [r for r in split_metrics if r.get("split") == "joint_holdout"]
    if not joint_rows:
        joint_rows = split_metrics
    selected = sorted(joint_rows, key=lambda r: (float(r.get("top1_group_selection_accuracy", 0.0)), float(r.get("accuracy", 0.0))), reverse=True)[0]

    model_comparison = sorted(split_metrics, key=lambda r: (str(r["split"]), -float(r["top1_group_selection_accuracy"]), -float(r["accuracy"])))
    metrics_agg: list[dict[str, Any]] = []
    for model_name in models:
        rows_m = [r for r in split_metrics if r["model"] == model_name]
        if not rows_m:
            continue
        metrics_agg.append(
            {
                "model": model_name,
                "mean_accuracy": float(np.mean([float(r["accuracy"]) for r in rows_m])),
                "mean_auc": float(np.nanmean([float(r["auc"]) for r in rows_m])) if rows_m else float("nan"),
                "mean_top1_group_selection_accuracy": float(np.mean([float(r["top1_group_selection_accuracy"]) for r in rows_m])),
                "mean_present_not_selected_reduction_potential": float(
                    np.mean([float(r["present_not_selected_reduction_potential"]) for r in rows_m])
                ),
            }
        )

    out_dir = REPO_ROOT / "outputs" / f"learned_branch_scorer_train_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "split_metrics.csv", split_metrics)
    write_csv(out_dir / "predictions.csv", all_predictions)
    write_csv(out_dir / "model_comparison.csv", model_comparison)
    write_csv(out_dir / "metrics.csv", metrics_agg)

    selected_text = {
        "selected_model": selected["model"],
        "selected_split": selected["split"],
        "selection_basis": "max top1_group_selection_accuracy then accuracy",
        "diagnostic_only": True,
    }
    (out_dir / "selected_model.joblib").write_text(json.dumps(selected_text, indent=2) + "\n", encoding="utf-8")

    readme = "\n".join(
        [
            f"# Learned branch scorer training ({args.timestamp})",
            "",
            "Diagnostic-only lightweight training run.",
            "",
            "Splits:",
            "- seed_holdout: train seed=11, test seed=23",
            "- budget_holdout: train budget in {4,6}, test budget=8",
            "- joint_holdout: train seed=11 and budget in {4,6}; test seed=23 and budget=8",
            "",
            f"Selected model: {selected['model']} on split {selected['split']}.",
            "",
            "Note: `selected_model.joblib` is a small text manifest for reproducibility in this diagnostic pass.",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
