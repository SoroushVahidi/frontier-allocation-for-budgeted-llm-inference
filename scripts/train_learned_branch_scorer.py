#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
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
    p.add_argument("--enable-loocv", action="store_true", default=False)
    p.add_argument("--split", default="grouped_problem_holdout", choices=["grouped_problem_holdout", "seed_holdout", "budget_holdout", "joint_holdout"]) 
    p.add_argument("--train-ratio", type=float, default=0.6)
    p.add_argument("--dev-ratio", type=float, default=0.2)
    p.add_argument("--test-ratio", type=float, default=0.2)
    p.add_argument("--split-seed", type=int, default=13)
    p.add_argument("--leave-one-problem-out", action="store_true")
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
    return {"top1": top1 / max(1, n_cases), "top2": top2 / max(1, n_cases), "top3": top3 / max(1, n_cases)}


def _learned_picks(rows: list[dict[str, Any]], score_key: str = "score") -> dict[tuple[str, int, int, str, str], dict[str, Any]]:
    out = {}
    for case_key, cell in group_by_case(rows).items():
        if cell:
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
    gold_present_cases = learned_gold = strict_gold = degradation = 0
    for case_key, cell in grouped.items():
        gp = any(as_int(r.get("label"), 0) == 1 for r in cell)
        if not gp:
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
        "present_not_selected_reduction": (learned_gold - strict_gold) / max(1, gold_present_cases),
        "degradation_case_rate": degradation / max(1, gold_present_cases),
    }


def grouped_problem_split_assignments(
    rows: list[dict[str, Any]],
    train_ratio: float,
    dev_ratio: float,
    split_seed: int,
    leave_one_problem_out: bool,
) -> list[dict[str, Any]]:
    problems = sorted(set(str(r.get("example_id", "")) for r in rows))
    if not problems:
        return []
    if leave_one_problem_out or len(problems) <= 4:
        assigns = []
        for problem in problems:
            for r in rows:
                split_id = f"leave_one_problem_out::{problem}"
                assigned = "test" if str(r.get("example_id", "")) == problem else "train"
                assigns.append({"split": split_id, "example_id": r.get("example_id", ""), "assigned_partition": assigned})
        return assigns

    rng = random.Random(split_seed)
    shuffled = list(problems)
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = max(1, int(round(n * train_ratio)))
    n_dev = max(0, int(round(n * dev_ratio)))
    if n_train + n_dev >= n:
        n_dev = max(0, n - n_train - 1)
    train_set = set(shuffled[:n_train])
    dev_set = set(shuffled[n_train : n_train + n_dev])

    assigns = []
    for r in rows:
        ex = str(r.get("example_id", ""))
        if ex in train_set:
            part = "train"
        elif ex in dev_set:
            part = "dev"
        else:
            part = "test"
        assigns.append({"split": "grouped_problem_holdout", "example_id": ex, "assigned_partition": part})
    return assigns


def _split_masks(rows: list[dict[str, Any]], args: argparse.Namespace) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], list[dict[str, Any]]]:
    seeds = np.array([as_int(r.get("seed"), -1) for r in rows])
    budgets = np.array([as_int(r.get("budget"), -1) for r in rows])

    assignments: list[dict[str, Any]] = []
    masks: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if args.split == "grouped_problem_holdout":
        assignments = grouped_problem_split_assignments(
            rows,
            train_ratio=args.train_ratio,
            dev_ratio=args.dev_ratio,
            split_seed=args.split_seed,
            leave_one_problem_out=args.leave_one_problem_out,
        )
        by_split: dict[str, dict[str, str]] = defaultdict(dict)
        for a in assignments:
            by_split[str(a["split"])][str(a["example_id"])] = str(a["assigned_partition"])
        for split_name, mapping in by_split.items():
            train_mask = np.array([mapping.get(str(r.get("example_id", "")), "test") == "train" for r in rows])
            test_mask = np.array([mapping.get(str(r.get("example_id", "")), "test") == "test" for r in rows])
            if train_mask.any() and test_mask.any():
                masks[split_name] = (train_mask, test_mask)
    else:
        base_masks = {
            "seed_holdout": (seeds == 11, seeds == 23),
            "budget_holdout": (np.isin(budgets, [4, 6]), budgets == 8),
            "joint_holdout": ((seeds == 11) & (np.isin(budgets, [4, 6])), (seeds == 23) & (budgets == 8)),
        }
        masks[args.split] = base_masks[args.split]
        for r in rows:
            assignments.append({"split": args.split, "example_id": str(r.get("example_id", "")), "assigned_partition": "train"})
    if args.enable_loocv:
        examples = sorted(set(str(r.get("example_id", "")) for r in rows))
        for ex in examples:
            masks[f"leave_one_example_out::{ex}"] = (
                np.array([str(r.get("example_id", "")) != ex for r in rows]),
                np.array([str(r.get("example_id", "")) == ex for r in rows]),
            )
    return masks, assignments


def _pairwise_train_predict(X_train: np.ndarray, y_train: np.ndarray, train_rows: list[dict[str, Any]], X_test: np.ndarray) -> np.ndarray:
    train_grouped = group_by_case(train_rows)
    pair_X: list[np.ndarray] = []
    pair_y: list[int] = []
    for _, cell in train_grouped.items():
        pos = [i for i, r in enumerate(cell) if as_int(r.get("label"), 0) == 1]
        neg = [i for i, r in enumerate(cell) if as_int(r.get("label"), 0) == 0]
        if not pos or not neg:
            continue
        mat = np.array([X_train[i] for i in range(len(train_rows))])
        idx_lookup = {id(r): i for i, r in enumerate(train_rows)}
        for pi in pos:
            for ni in neg:
                rp, rn = cell[pi], cell[ni]
                gp = idx_lookup.get(id(rp))
                gn = idx_lookup.get(id(rn))
                if gp is None or gn is None:
                    continue
                diff = mat[gp] - mat[gn]
                pair_X.append(diff)
                pair_y.append(1)
                pair_X.append(-diff)
                pair_y.append(0)
    if not pair_X:
        return np.zeros(X_test.shape[0], dtype=float)
    model = LogisticRegression(max_iter=1200, random_state=0)
    pair_matrix = np.vstack(pair_X)
    pair_labels = np.array(pair_y)
    if np.unique(pair_labels).size < 2:
        return np.zeros(X_test.shape[0], dtype=float)
    model.fit(pair_matrix, pair_labels)
    w = model.coef_[0]
    return np.dot(X_test, w)


def _subset_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        buckets[(str(r.get("split", "")), str(r.get("model", "")), str(r.get("stratum", "unknown")))].append(r)
    for (split_name, model_name, stratum), cell in buckets.items():
        tk = _topk_case_metrics(cell)
        sm = _selection_metrics(cell)
        out.append(
            {
                "split": split_name,
                "model": model_name,
                "stratum": stratum,
                "n_rows": len(cell),
                "n_cases": len(group_by_case(cell)),
                "top1_candidate_selection_accuracy": tk["top1"],
                "top2_recall": tk["top2"],
                "top3_recall": tk["top3"],
                "learned_selected_gold_rate": sm["learned_selected_gold_rate"],
                "current_controller_selected_gold_rate": sm["current_controller_selected_gold_rate"],
                "present_not_selected_reduction": sm["present_not_selected_reduction"],
                "degradation_case_rate": sm["degradation_case_rate"],
            }
        )
    return out


def main() -> None:
    args = parse_args()
    rows = read_csv(REPO_ROOT / args.dataset_examples)
    if not rows:
        raise SystemExit("No rows found in dataset examples csv.")

    feature_drop = {
        "label",
        "case_id",
        "example_id",
        "split_id",
        "candidate_answer_normalized",
        "raw_candidate_answer",
        "selected_answer",
        "gold_answer",
        "normalized_gold_answer",
        "normalized_answer",
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
        "candidate_id",
        "parent_id",
        "answer_group_id",
        "stratum",
        "termination_reason",
        "data_quality_flags",
    }

    X = [_to_feature_dict(r, feature_names, categorical) for r in rows]
    y = np.array([as_int(r.get("label"), 0) for r in rows])

    vectorizer = DictVectorizer(sparse=False)
    X_mat = vectorizer.fit_transform(X)

    models = {
        "logistic_regression": LogisticRegression(max_iter=2000, random_state=0),
        "random_forest": RandomForestClassifier(n_estimators=120, random_state=0, min_samples_leaf=1),
        "gradient_boosting": GradientBoostingClassifier(random_state=0),
        "hist_gradient_boosting": HistGradientBoostingClassifier(random_state=0),
    }

    splits, assignments = _split_masks(rows, args)
    split_metrics: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []

    for split_name, (train_mask, test_mask) in splits.items():
        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        if train_idx.size == 0 or test_idx.size == 0:
            continue
        X_train, y_train = X_mat[train_idx], y[train_idx]
        X_test, y_test = X_mat[test_idx], y[test_idx]
        if np.unique(y_train).size < 2:
            continue

        for model_name, model in models.items():
            model.fit(X_train, y_train)
            y_score = model.predict_proba(X_test)[:, 1]
            y_pred = (y_score >= 0.5).astype(int)
            pred_rows = []
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
                    "top1_candidate_selection_accuracy": tk["top1"],
                    "top2_recall": tk["top2"],
                    "top3_recall": tk["top3"],
                    "current_controller_selected_gold_rate": sm["current_controller_selected_gold_rate"],
                    "learned_selected_gold_rate": sm["learned_selected_gold_rate"],
                    "improvement_gold_present": sm["learned_selected_gold_rate"] - sm["current_controller_selected_gold_rate"],
                    "present_not_selected_reduction": sm["present_not_selected_reduction"],
                    "degradation_case_rate": sm["degradation_case_rate"],
                }
            )

        # Pairwise/BT-style model
        train_rows = [rows[int(i)] for i in train_idx]
        pairwise_score = _pairwise_train_predict(X_train, y_train, train_rows, X_test)
        pair_pred = (pairwise_score >= 0.0).astype(int)
        pair_rows = []
        for local_i, global_i in enumerate(test_idx):
            row = dict(rows[int(global_i)])
            row.update({"split": split_name, "model": "pairwise_logistic", "score": float(pairwise_score[local_i]), "pred": int(pair_pred[local_i])})
            pair_rows.append(row)
            all_predictions.append(row)
        tk = _topk_case_metrics(pair_rows)
        sm = _selection_metrics(pair_rows)
        split_metrics.append(
            {
                "split": split_name,
                "model": "pairwise_logistic",
                "n_train": int(train_idx.size),
                "n_test": int(test_idx.size),
                "accuracy": float(accuracy_score(y_test, pair_pred)),
                "precision": float(precision_score(y_test, pair_pred, zero_division=0)),
                "recall": float(recall_score(y_test, pair_pred, zero_division=0)),
                "auc": _safe_auc(y_test, pairwise_score),
                "top1_candidate_selection_accuracy": tk["top1"],
                "top2_recall": tk["top2"],
                "top3_recall": tk["top3"],
                "current_controller_selected_gold_rate": sm["current_controller_selected_gold_rate"],
                "learned_selected_gold_rate": sm["learned_selected_gold_rate"],
                "improvement_gold_present": sm["learned_selected_gold_rate"] - sm["current_controller_selected_gold_rate"],
                "present_not_selected_reduction": sm["present_not_selected_reduction"],
                "degradation_case_rate": sm["degradation_case_rate"],
            }
        )

    if not split_metrics:
        pseudo_rows = []
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
                "top1_candidate_selection_accuracy": tk["top1"],
                "top2_recall": tk["top2"],
                "top3_recall": tk["top3"],
                "current_controller_selected_gold_rate": sm["current_controller_selected_gold_rate"],
                "learned_selected_gold_rate": sm["learned_selected_gold_rate"],
                "improvement_gold_present": sm["learned_selected_gold_rate"] - sm["current_controller_selected_gold_rate"],
                "present_not_selected_reduction": sm["present_not_selected_reduction"],
                "degradation_case_rate": sm["degradation_case_rate"],
            }
        )

    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in split_metrics:
        by_model[str(r["model"])].append(r)

    metrics_agg = []
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

    best = sorted(split_metrics, key=lambda r: (float(r.get("improvement_gold_present", 0.0)), float(r.get("top1_candidate_selection_accuracy", 0.0)), float(r.get("accuracy", 0.0))), reverse=True)[0]

    is_trace_dataset = "trace_level_" in str(args.dataset_examples)
    prefix = args.output_prefix or ("trace_level_learned_branch_scorer_train" if is_trace_dataset else "learned_branch_scorer_train")
    out_dir = REPO_ROOT / "outputs" / f"{prefix}_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    case_level_selection_metrics: list[dict[str, Any]] = []
    grouped_pred = defaultdict(list)
    for row in all_predictions:
        grouped_pred[(str(row.get("split", "")), str(row.get("model", "")))].append(row)
    for (split_name, model_name), subset in grouped_pred.items():
        learned = _learned_picks(subset)
        strict, support = _baseline_picks(subset)
        grouped_case = group_by_case(subset)
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
                    "gold_present": int(any(as_int(r.get("label"), 0) == 1 for r in grouped_case.get(case_key, []))),
                    "learned_selected_answer": pick.get("candidate_answer_normalized", ""),
                    "learned_selected_gold": as_int(pick.get("label"), 0),
                    "current_selected_answer": strict.get(case_key, {}).get("candidate_answer_normalized", ""),
                    "current_selected_gold": as_int(strict.get(case_key, {}).get("label"), 0),
                    "support_selected_answer": support.get(case_key, {}).get("candidate_answer_normalized", ""),
                    "support_selected_gold": as_int(support.get(case_key, {}).get("label"), 0),
                }
            )
    write_csv(out_dir / "split_metrics.csv", split_metrics)
    write_csv(out_dir / "predictions.csv", all_predictions)
    write_csv(out_dir / "model_comparison.csv", sorted(split_metrics, key=lambda r: (str(r["split"]), -float(r["improvement_gold_present"]))))
    write_csv(out_dir / "metrics.csv", metrics_agg)
    write_csv(out_dir / "case_level_selection_metrics.csv", case_level_selection_metrics)
    write_csv(out_dir / "split_assignments.csv", assignments)
    write_csv(out_dir / "per_stratum_metrics.csv", _subset_metrics(all_predictions))

    by_budget_seed: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in all_predictions:
        by_budget_seed[
            (
                str(row.get("split", "")),
                str(row.get("model", "")),
                as_int(row.get("budget"), -1),
                as_int(row.get("seed"), -1),
            )
        ].append(row)
    write_csv(
        out_dir / "per_budget_seed_metrics.csv",
        [
            {
                "split": split,
                "model": model,
                "budget": budget,
                "seed": seed,
                "n_rows": len(cell),
                "top1_candidate_selection_accuracy": _topk_case_metrics(cell)["top1"],
                "learned_selected_gold_rate": _selection_metrics(cell)["learned_selected_gold_rate"],
                "current_controller_selected_gold_rate": _selection_metrics(cell)["current_controller_selected_gold_rate"],
            }
            for (split, model, budget, seed), cell in sorted(by_budget_seed.items())
        ],
    )

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
            f"Split policy: `{args.split}`",
            "Grouped split keeps each problem in exactly one partition.",
            "Models: logistic_regression, random_forest, gradient_boosting, hist_gradient_boosting, pairwise_logistic.",
            "",
            "Files:",
            "- split_metrics.csv",
            "- metrics.csv",
            "- model_comparison.csv",
            "- predictions.csv",
            "- split_assignments.csv",
            "- per_stratum_metrics.csv",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")

    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
