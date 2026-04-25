#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
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
    p = argparse.ArgumentParser(description="Train lightweight learned branch scorer models.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--dataset-examples", required=True)
    p.add_argument("--output-prefix", default="")
    p.add_argument("--enable-loocv", action="store_true", default=True)
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
            if str(value).strip() in {"", "nan", "None"}:
                out[key] = 0.0
            else:
                try:
                    out[key] = float(value)
                except Exception:
                    out[key] = 0.0
    return out


def _topk_case_metrics(rows: list[dict[str, Any]], score_key: str = "score") -> dict[str, float]:
    grouped = group_by_case(rows)
    top1 = top2 = top3 = 0
    n_cases = 0
    for _, cell in grouped.items():
        if not cell:
            continue
        n_cases += 1
        ranked = sorted(cell, key=lambda r: float(r.get(score_key, 0.0)), reverse=True)
        if as_int(ranked[0].get("label"), 0) == 1:
            top1 += 1
        if any(as_int(r.get("label"), 0) == 1 for r in ranked[:2]):
            top2 += 1
        if any(as_int(r.get("label"), 0) == 1 for r in ranked[:3]):
            top3 += 1
    return {
        "top1": top1 / max(1, n_cases),
        "top2": top2 / max(1, n_cases),
        "top3": top3 / max(1, n_cases),
    }


def _learned_picks(rows: list[dict[str, Any]], score_key: str = "score") -> dict[tuple[str, int, int, str, str], dict[str, Any]]:
    out = {}
    for case_key, cell in group_by_case(rows).items():
        if not cell:
            continue
        out[case_key] = max(cell, key=lambda r: float(r.get(score_key, 0.0)))
    return out


def _baseline_picks(rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, int, int, str, str], dict[str, Any]], dict[tuple[str, int, int, str, str], dict[str, Any]]]:
    strict, support = {}, {}
    for case_key, cell in group_by_case(rows).items():
        s = next((r for r in cell if str(r.get("method")) == "strict_f3" and as_int(r.get("was_selected_by_current_controller"), 0) == 1), None)
        if s is None:
            s = next((r for r in cell if str(r.get("method")) == "strict_f3"), None)
        if s is None and cell:
            s = max(cell, key=lambda r: as_int(r.get("was_selected_by_current_controller"), 0))
        if s is not None:
            strict[case_key] = s
        if cell:
            support[case_key] = max(cell, key=lambda r: float(r.get("answer_group_support", 0.0)))
    return strict, support


def _selection_metrics(rows: list[dict[str, Any]], score_key: str = "score") -> dict[str, float]:
    grouped = group_by_case(rows)
    learned = _learned_picks(rows, score_key)
    strict, _ = _baseline_picks(rows)

    gold_present_cases = 0
    learned_gold = 0
    strict_gold = 0
    degradation = 0
    for case_key, cell in grouped.items():
        gold_present = any(as_int(r.get("label"), 0) == 1 for r in cell)
        if not gold_present:
            continue
        gold_present_cases += 1
        learned_ok = as_int(learned.get(case_key, {}).get("label"), 0)
        strict_ok = as_int(strict.get(case_key, {}).get("label"), 0)
        learned_gold += learned_ok
        strict_gold += strict_ok
        if strict_ok == 1 and learned_ok == 0:
            degradation += 1

    return {
        "gold_present_cases": float(gold_present_cases),
        "current_controller_selected_gold_rate": strict_gold / max(1, gold_present_cases),
        "learned_selected_gold_rate": learned_gold / max(1, gold_present_cases),
        "present_not_selected_reduction": (strict_gold - learned_gold) * -1.0 / max(1, gold_present_cases),
        "degradation_case_rate": degradation / max(1, gold_present_cases),
    }


def _split_masks(rows: list[dict[str, Any]], enable_loocv: bool = True) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    seeds = np.array([as_int(r.get("seed"), -1) for r in rows])
    budgets = np.array([as_int(r.get("budget"), -1) for r in rows])
    example_ids = np.array([str(r.get("example_id", "")) for r in rows])
    masks: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "seed_holdout": (seeds == 11, seeds == 23),
        "budget_holdout": (np.isin(budgets, [4, 6]), budgets == 8),
        "joint_holdout": ((seeds == 11) & (np.isin(budgets, [4, 6])), (seeds == 23) & (budgets == 8)),
    }
    if enable_loocv:
        for ex in sorted(set(example_ids.tolist())):
            masks[f"leave_one_example_out::{ex}"] = (example_ids != ex, example_ids == ex)
    return masks


def main() -> None:
    args = parse_args()
    rows = read_csv(REPO_ROOT / args.dataset_examples)
    if not rows:
        raise SystemExit("No rows found in dataset examples csv.")

    label_key = "label"
    feature_drop = {
        "label",
        "case_id",
        "example_id",
        "candidate_answer_normalized",
        "raw_candidate_answer",
        "selected_answer",
        "gold_answer",
        "normalized_gold_answer",
    }
    feature_names = [k for k in rows[0].keys() if k not in feature_drop]
    categorical = {
        "provider",
        "model",
        "dataset",
        "method",
        "runtime_method",
        "group",
        "failure_type",
        "source_type",
        "reasoning_role",
        "operation_sequence",
        "selected_answer_group",
        "top_answer_group",
        "branch_id",
        "parent_branch_id",
    }

    X = [_to_feature_dict(r, feature_names, categorical) for r in rows]
    y = np.array([as_int(r.get(label_key), 0) for r in rows])

    vectorizer = DictVectorizer(sparse=False)
    X_mat = vectorizer.fit_transform(X)

    models = {
        "logistic_regression": LogisticRegression(max_iter=2000, random_state=0),
        "random_forest": RandomForestClassifier(n_estimators=120, random_state=0, min_samples_leaf=1),
        "gradient_boosting": GradientBoostingClassifier(random_state=0),
    }

    splits = _split_masks(rows, enable_loocv=args.enable_loocv)
    split_metrics: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []

    for split_name, (train_mask, test_mask) in splits.items():
        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        if train_idx.size == 0 or test_idx.size == 0:
            continue

        X_train = X_mat[train_idx]
        y_train = y[train_idx]
        X_test = X_mat[test_idx]
        y_test = y[test_idx]

        if np.unique(y_train).size < 2:
            continue

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

            tk = _topk_case_metrics(pred_rows)
            sm = _selection_metrics(pred_rows)
            split_metrics.append(
                {
                    "split": split_name,
                    "model": model_name,
                    "n_train": int(train_idx.size),
                    "n_test": int(test_idx.size),
                    "accuracy": float(accuracy_score(y_test, y_pred)),
                    "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                    "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                    "auc": _safe_auc(y_test, y_score),
                    "top1_candidate_selection_accuracy": float(tk["top1"]),
                    "top2_recall": float(tk["top2"]),
                    "top3_recall": float(tk["top3"]),
                    "current_controller_selected_gold_rate": float(sm["current_controller_selected_gold_rate"]),
                    "learned_selected_gold_rate": float(sm["learned_selected_gold_rate"]),
                    "improvement_gold_present": float(sm["learned_selected_gold_rate"] - sm["current_controller_selected_gold_rate"]),
                    "present_not_selected_reduction": float(sm["present_not_selected_reduction"]),
                    "degradation_case_rate": float(sm["degradation_case_rate"]),
                }
            )

    if not split_metrics:
        # Graceful structural fallback for dry-run trace packages where all labels can be identical.
        pseudo_rows: list[dict[str, Any]] = []
        for r in rows:
            score = float(r.get("answer_group_support", 0.0))
            row = dict(r)
            row.update({"split": "fallback_support_proxy", "model": "support_proxy_ranker", "score": score, "pred": int(score > 0)})
            pseudo_rows.append(row)
            all_predictions.append(row)
        tk = _topk_case_metrics(pseudo_rows)
        sm = _selection_metrics(pseudo_rows)
        split_metrics.append(
            {
                "split": "fallback_support_proxy",
                "model": "support_proxy_ranker",
                "n_train": 0,
                "n_test": len(rows),
                "accuracy": float(np.mean([as_int(r.get("label"), 0) == as_int(r.get("pred"), 0) for r in pseudo_rows])),
                "precision": 0.0,
                "recall": 0.0,
                "auc": float("nan"),
                "top1_candidate_selection_accuracy": float(tk["top1"]),
                "top2_recall": float(tk["top2"]),
                "top3_recall": float(tk["top3"]),
                "current_controller_selected_gold_rate": float(sm["current_controller_selected_gold_rate"]),
                "learned_selected_gold_rate": float(sm["learned_selected_gold_rate"]),
                "improvement_gold_present": float(sm["learned_selected_gold_rate"] - sm["current_controller_selected_gold_rate"]),
                "present_not_selected_reduction": float(sm["present_not_selected_reduction"]),
                "degradation_case_rate": float(sm["degradation_case_rate"]),
            }
        )

    # Model comparison and selection.
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in split_metrics:
        by_model[str(r["model"])].append(r)

    metrics_agg: list[dict[str, Any]] = []
    for model_name, rows_m in by_model.items():
        metrics_agg.append(
            {
                "model": model_name,
                "mean_accuracy": float(np.mean([float(r["accuracy"]) for r in rows_m])),
                "mean_auc": float(np.nanmean([float(r["auc"]) for r in rows_m])),
                "mean_top1_candidate_selection_accuracy": float(np.mean([float(r["top1_candidate_selection_accuracy"]) for r in rows_m])),
                "mean_top2_recall": float(np.mean([float(r["top2_recall"]) for r in rows_m])),
                "mean_top3_recall": float(np.mean([float(r["top3_recall"]) for r in rows_m])),
                "mean_improvement_gold_present": float(np.mean([float(r["improvement_gold_present"]) for r in rows_m])),
                "mean_present_not_selected_reduction": float(np.mean([float(r["present_not_selected_reduction"]) for r in rows_m])),
                "mean_degradation_case_rate": float(np.mean([float(r["degradation_case_rate"]) for r in rows_m])),
            }
        )

    best = sorted(
        split_metrics,
        key=lambda r: (float(r.get("improvement_gold_present", 0.0)), float(r.get("top1_candidate_selection_accuracy", 0.0)), float(r.get("accuracy", 0.0))),
        reverse=True,
    )[0]

    case_level_selection_metrics: list[dict[str, Any]] = []
    for split_name in sorted(set(str(r.get("split", "")) for r in all_predictions)):
        for model_name in sorted(set(str(r.get("model", "")) for r in all_predictions)):
            subset = [r for r in all_predictions if str(r.get("split")) == split_name and str(r.get("model")) == model_name]
            if not subset:
                continue
            learned = _learned_picks(subset)
            strict, support = _baseline_picks(subset)
            for case_key, pick in learned.items():
                case_level_selection_metrics.append(
                    {
                        "split": split_name,
                        "model": model_name,
                        "provider": case_key[0],
                        "seed": case_key[1],
                        "budget": case_key[2],
                        "dataset": case_key[3],
                        "example_id": case_key[4],
                        "gold_present": int(any(as_int(r.get("label"), 0) == 1 for r in group_by_case(subset).get(case_key, []))),
                        "learned_selected_answer": pick.get("candidate_answer_normalized", ""),
                        "learned_selected_gold": as_int(pick.get("label"), 0),
                        "current_selected_answer": strict.get(case_key, {}).get("candidate_answer_normalized", ""),
                        "current_selected_gold": as_int(strict.get(case_key, {}).get("label"), 0),
                        "support_selected_answer": support.get(case_key, {}).get("candidate_answer_normalized", ""),
                        "support_selected_gold": as_int(support.get(case_key, {}).get("label"), 0),
                    }
                )

    is_trace_dataset = "trace_level_" in str(args.dataset_examples)
    prefix = args.output_prefix or ("trace_level_learned_branch_scorer_train" if is_trace_dataset else "learned_branch_scorer_train")
    out_dir = REPO_ROOT / "outputs" / f"{prefix}_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "split_metrics.csv", split_metrics)
    write_csv(out_dir / "predictions.csv", all_predictions)
    write_csv(out_dir / "model_comparison.csv", sorted(split_metrics, key=lambda r: (str(r["split"]), -float(r["improvement_gold_present"]))))
    write_csv(out_dir / "metrics.csv", metrics_agg)
    write_csv(out_dir / "case_level_selection_metrics.csv", case_level_selection_metrics)

    selected_text = {
        "selected_model": best["model"],
        "selected_split": best["split"],
        "selection_basis": "max improvement on gold-present cases, then top1, then accuracy",
        "diagnostic_only": True,
    }
    (out_dir / "selected_model.joblib").write_text(json.dumps(selected_text, indent=2) + "\n", encoding="utf-8")

    readme = "\n".join(
        [
            f"# Learned branch scorer training ({args.timestamp})",
            "",
            "Leakage-aware splits:",
            "- leave_one_example_out::<example_id> when enabled",
            "- seed_holdout (11->23) when available",
            "- budget_holdout (4/6->8) when available",
            "- joint_holdout when available",
            "",
            f"Selected model: {best['model']} on split {best['split']}.",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")

    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
