#!/usr/bin/env python3
"""Train v1/v2/v3 branch-scorer models and export text artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import FEATURE_NAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train branch scorer models")
    parser.add_argument("--dataset", default="outputs/branch_scorer_v3/branch_scorer_v3_dataset.jsonl")
    parser.add_argument("--output-dir", default="outputs/branch_scorer_v3")
    return parser.parse_args()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _tree_to_dict(tree: Any, node_id: int = 0) -> dict[str, Any]:
    left = tree.children_left[node_id]
    right = tree.children_right[node_id]
    if left == right:
        value = tree.value[node_id][0]
        positive_prob = float(value[1] / max(1.0, value.sum()))
        return {"value": positive_prob}

    feature_idx = int(tree.feature[node_id])
    return {
        "feature": FEATURE_NAMES[feature_idx],
        "threshold": float(tree.threshold[node_id]),
        "left": _tree_to_dict(tree, int(left)),
        "right": _tree_to_dict(tree, int(right)),
    }


def _tree_regressor_to_dict(tree: Any, node_id: int = 0) -> dict[str, Any]:
    left = tree.children_left[node_id]
    right = tree.children_right[node_id]
    if left == right:
        return {"value": float(tree.value[node_id][0][0])}

    feature_idx = int(tree.feature[node_id])
    return {
        "feature": FEATURE_NAMES[feature_idx],
        "threshold": float(tree.threshold[node_id]),
        "left": _tree_regressor_to_dict(tree, int(left)),
        "right": _tree_regressor_to_dict(tree, int(right)),
    }


def _fit_and_export_model(train_rows: list[dict[str, Any]], label_key: str, model_kind: str) -> dict[str, Any]:
    import numpy as np  # type: ignore
    from sklearn.linear_model import LinearRegression  # type: ignore
    from sklearn.linear_model import LogisticRegression  # type: ignore
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor  # type: ignore

    x_train = np.array([[float(r[name]) for name in FEATURE_NAMES] for r in train_rows])
    y_train = np.array([float(r[label_key]) for r in train_rows])

    if model_kind == "logistic":
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
        model.fit(x_train, y_train)
        return {
            "model_type": "logistic",
            "label_key": label_key,
            "weights": {name: float(weight) for name, weight in zip(FEATURE_NAMES, model.coef_[0])},
            "intercept": float(model.intercept_[0]),
        }

    if model_kind == "decision_tree":
        model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, random_state=0)
        model.fit(x_train, y_train)
        return {
            "model_type": "decision_tree",
            "label_key": label_key,
            "tree": _tree_to_dict(model.tree_),
        }

    if model_kind == "linear_regression":
        reg = LinearRegression()
        reg.fit(x_train, y_train)
        return {
            "model_type": "linear_regression",
            "label_key": label_key,
            "weights": {name: float(weight) for name, weight in zip(FEATURE_NAMES, reg.coef_)},
            "intercept": float(reg.intercept_),
        }

    if model_kind == "decision_tree_regressor":
        reg = DecisionTreeRegressor(max_depth=5, min_samples_leaf=30, random_state=0)
        reg.fit(x_train, y_train)
        return {
            "model_type": "decision_tree_regressor",
            "label_key": label_key,
            "tree": _tree_regressor_to_dict(reg.tree_),
        }

    raise ValueError(f"Unsupported model_kind: {model_kind}")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_rows(Path(args.dataset))

    train_rows = [r for r in rows if r["split"] == "train"]
    test_rows = [r for r in rows if r["split"] == "test"]

    models = {
        "adaptive_learned_branch_score_v1": _fit_and_export_model(train_rows, "v1_label_quality", "logistic"),
        "adaptive_learned_branch_score_v2": _fit_and_export_model(train_rows, "v2_label_gain", "logistic"),
        # Preserve existing name used by controller-level comparisons.
        "adaptive_learned_branch_score": _fit_and_export_model(train_rows, "v2_label_gain", "logistic"),
        "adaptive_learned_branch_score_v3_linear": _fit_and_export_model(
            train_rows, "v3_target_progress_value", "linear_regression"
        ),
        "adaptive_learned_branch_score_v3": _fit_and_export_model(
            train_rows, "v3_target_progress_value", "decision_tree_regressor"
        ),
    }

    model_dir = out_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    for name, model_obj in models.items():
        (model_dir / f"{name}.json").write_text(json.dumps(model_obj, indent=2), encoding="utf-8")

    train_stats = {
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "models_written": sorted(models.keys()),
    }
    (out_dir / "training_meta.json").write_text(json.dumps(train_stats, indent=2), encoding="utf-8")
    print(json.dumps(train_stats, indent=2))


if __name__ == "__main__":
    main()
