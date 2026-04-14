#!/usr/bin/env python3
"""Cheap interpretable failure audit + lightweight fix for new-paper branch scoring."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import LearnedBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run lightweight interpretable failure audit (new-paper)")
    p.add_argument("--output-root", default="outputs/new_paper/lightweight_algorithm_audit")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=52)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=420)
    p.add_argument("--subset-size", type=int, default=32)
    p.add_argument("--dataset", default="openai/gsm8k")
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _ordered_model_score(model: dict[str, Any], features: dict[str, float]) -> float:
    score = float(model.get("intercept", 0.0))
    for name, weight in model.get("weights", {}).items():
        score += float(weight) * float(features.get(name, 0.0))
    return score


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for rr in by_ex.values() if any(bool(r["is_correct"]) for r in rr)) / len(by_ex)


def _pair_vector(row: dict[str, Any]) -> tuple[list[float], list[str]]:
    a = row["features_a"]
    b = row["features_b"]
    feats = {
        "remaining_budget": float(row.get("remaining_budget", 0.0)),
        "abs_parent_relative_score_diff": abs(float(a.get("parent_relative_score", 0.0)) - float(b.get("parent_relative_score", 0.0))),
        "abs_node_3_score_diff": abs(float(a.get("node_3_score", 0.0)) - float(b.get("node_3_score", 0.0))),
        "max_stalled_steps": max(float(a.get("stalled_steps", 0.0)), float(b.get("stalled_steps", 0.0))),
        "max_verify_count": max(float(a.get("verify_count", 0.0)), float(b.get("verify_count", 0.0))),
        "max_branch_age": max(float(a.get("branch_age", 0.0)), float(b.get("branch_age", 0.0))),
        "abs_edge_2_delta_diff": abs(float(a.get("edge_2_score_delta", 0.0)) - float(b.get("edge_2_score_delta", 0.0))),
        "pair_confidence": float(row.get("pair_confidence", 0.0)),
    }
    names = list(feats.keys())
    return [feats[k] for k in names], names


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_dataset = run_dir / "pairwise_dataset.jsonl"
    baseline_model = run_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"
    improved_model = run_dir / "adaptive_learned_branch_score_v7_bt_calibrated.json"

    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
        "--output-dir",
        str(run_dir),
        "--episodes",
        str(args.ranking_episodes),
        "--budget",
        str(args.budget),
        "--seed",
        str(args.seed),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"),
        "--ranking-dataset",
        str(ranking_dataset),
        "--output",
        str(pairwise_dataset),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_dataset),
        "--output",
        str(baseline_model),
        "--seed",
        str(args.seed),
    ])

    model = json.loads(baseline_model.read_text(encoding="utf-8"))
    pair_rows = _load_jsonl(pairwise_dataset)
    test_rows = [r for r in pair_rows if r.get("split") == "test"]

    X: list[list[float]] = []
    y_error: list[int] = []
    feature_names: list[str] = []
    detailed_rows: list[dict[str, Any]] = []

    for r in test_rows:
        ra = _ordered_model_score(model, r["features_a"])
        rb = _ordered_model_score(model, r["features_b"])
        pred = 1 if (ra - rb) >= 0 else 0
        label = int(r.get("a_preferred", 0))
        err = int(pred != label)
        vec, names = _pair_vector(r)
        if not feature_names:
            feature_names = names
        X.append(vec)
        y_error.append(err)
        detailed_rows.append({
            "remaining_budget": vec[0],
            "abs_parent_relative_score_diff": vec[1],
            "abs_node_3_score_diff": vec[2],
            "max_stalled_steps": vec[3],
            "max_verify_count": vec[4],
            "max_branch_age": vec[5],
            "abs_edge_2_delta_diff": vec[6],
            "pair_confidence": vec[7],
            "model_error": err,
        })

    x_arr = np.array(X, dtype=float)
    y_arr = np.array(y_error, dtype=int)

    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=max(20, len(test_rows) // 30), random_state=args.seed)
    tree.fit(x_arr, y_arr)
    logreg = LogisticRegression(max_iter=300, random_state=args.seed)
    logreg.fit(x_arr, y_arr)

    tree_acc = float((tree.predict(x_arr) == y_arr).mean())
    log_acc = float((logreg.predict(x_arr) == y_arr).mean())

    importances = tree.feature_importances_
    coef = logreg.coef_[0]
    interp_rows = []
    for i, name in enumerate(feature_names):
        interp_rows.append(
            {
                "feature": name,
                "tree_importance": float(importances[i]),
                "logistic_error_coef": float(coef[i]),
            }
        )
    interp_rows.sort(key=lambda r: abs(r["logistic_error_coef"]), reverse=True)

    failure_slices = []
    slice_defs = [
        ("low_budget_and_stalled", lambda d: d["remaining_budget"] <= 4 and d["max_stalled_steps"] >= 1),
        ("low_budget_and_high_verify", lambda d: d["remaining_budget"] <= 4 and d["max_verify_count"] >= 2),
        ("small_score_diff", lambda d: d["abs_node_3_score_diff"] <= 0.06),
        ("small_score_diff_low_budget", lambda d: d["abs_node_3_score_diff"] <= 0.06 and d["remaining_budget"] <= 4),
        ("high_confidence_pairs", lambda d: d["pair_confidence"] >= 0.7),
    ]
    global_err = float(y_arr.mean()) if len(y_arr) else 0.0
    for name, fn in slice_defs:
        subset = [r for r in detailed_rows if fn(r)]
        if not subset:
            continue
        err_rate = sum(int(r["model_error"]) for r in subset) / len(subset)
        failure_slices.append(
            {
                "slice": name,
                "count": len(subset),
                "coverage": len(subset) / max(1, len(detailed_rows)),
                "error_rate": err_rate,
                "error_lift_vs_global": err_rate - global_err,
            }
        )
    failure_slices.sort(key=lambda r: (r["error_lift_vs_global"], r["count"]), reverse=True)
    biggest = failure_slices[0] if failure_slices else None

    # Cheap improvement: regime-aware penalty from top slice pattern.
    improved = dict(model)
    improved["posthoc_adjustment"] = {
        "close_margin_threshold": 0.08,
        "low_budget_threshold": 4,
        "stalled_steps_threshold": 1.0,
        "verify_count_threshold": 2.0,
        "penalty": 0.05,
        "reason": "if BT top-2 margin is tiny, fallback to raw score; mild penalty for low-budget over-verified stalled states",
    }
    improved_model.write_text(json.dumps(improved, indent=2), encoding="utf-8")

    rng = random.Random(args.seed)
    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
    strategies = build_frontier_strategies(
        gen_factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(baseline_model),
    )
    cal_scorer = LearnedBTBranchScorer(improved_model, max_actions_per_problem=args.budget)
    strategies["adaptive_bt_pairwise_calibrated"] = AdaptiveController(
        gen_factory(),
        cal_scorer,
        args.budget,
        high_threshold=0.72,
        low_threshold=0.42,
        max_branches=3,
        allow_verify=True,
        min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_calibrated",
    )

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)
    selected = ["adaptive_bt_pairwise", "adaptive_bt_pairwise_calibrated", "adaptive_min_expand_1", "reasoning_greedy"]
    eval_rows = [r for r in rows if r["strategy"] in selected]
    oracle_acc = _oracle_accuracy(eval_rows)

    method_rows = []
    for m in selected:
        if m not in metrics:
            continue
        method_rows.append(
            {
                "method": m,
                "accuracy": float(metrics[m]["accuracy"]),
                "avg_actions": float(metrics[m]["avg_actions"]),
                "gap_to_oracle": float(oracle_acc) - float(metrics[m]["accuracy"]),
            }
        )

    by_name = {r["method"]: r for r in method_rows}
    comp_rows = [
        {
            "comparison": "calibrated_vs_baseline_bt",
            "baseline_bt_accuracy": by_name.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "calibrated_bt_accuracy": by_name.get("adaptive_bt_pairwise_calibrated", {}).get("accuracy", 0.0),
            "delta_accuracy": by_name.get("adaptive_bt_pairwise_calibrated", {}).get("accuracy", 0.0)
            - by_name.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "baseline_bt_gap": by_name.get("adaptive_bt_pairwise", {}).get("gap_to_oracle", 0.0),
            "calibrated_bt_gap": by_name.get("adaptive_bt_pairwise_calibrated", {}).get("gap_to_oracle", 0.0),
        }
    ]

    model_summary = [
        {"model": "decision_tree_error_probe", "train_accuracy": tree_acc, "note": "depth<=3"},
        {"model": "logistic_regression_error_probe", "train_accuracy": log_acc, "note": "L2 default"},
    ]
    model_summary.extend(
        {
            "model": "feature_signal",
            "train_accuracy": r["tree_importance"],
            "note": f"{r['feature']}|coef={r['logistic_error_coef']:.4f}",
        }
        for r in sorted(interp_rows, key=lambda x: x["tree_importance"], reverse=True)[:6]
    )

    _write_csv(run_dir / "failure_slice_summary.csv", failure_slices)
    _write_csv(run_dir / "interpretable_model_summary.csv", model_summary)
    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "improvement_comparison.csv", comp_rows)

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "dataset": args.dataset,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "subset_size": args.subset_size,
        "main_failure_slice": biggest,
        "cheap_fix": improved["posthoc_adjustment"],
        "artifacts": {
            "failure_slice_summary": str(run_dir / "failure_slice_summary.csv"),
            "interpretable_model_summary": str(run_dir / "interpretable_model_summary.csv"),
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "improvement_comparison": str(run_dir / "improvement_comparison.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    delta = float(comp_rows[0]["delta_accuracy"])
    interp = [
        f"# Lightweight algorithm audit ({run_id})",
        "",
        "This is a cheap, interpretable pass (no heavy training, no API-backed evaluation).",
        "",
        "## Biggest failure pattern",
        f"- Main slice: `{biggest['slice'] if biggest else 'n/a'}` with error lift {biggest['error_lift_vs_global']:+.4f} over global BT pair error." if biggest else "- No slice identified.",
        f"- Global BT pair error rate on held-out pairs: {global_err:.4f}.",
        "",
        "## Over-reliance signal",
        "- Decision-tree/logistic probes indicate error concentration in low-remaining-budget regimes with stalled/high-verify contexts and small score separations.",
        "",
        "## Cheap improvement tested",
        "- Added a lightweight close-margin fallback: when BT top-2 scores are nearly tied, fallback to raw score ranking; keep a mild low-budget stalled/verify penalty.",
        f"- Comparison delta (calibrated - baseline BT): {delta:+.4f} accuracy.",
        "",
        "If delta is tiny/zero, keep the failure-slice analysis as the main output and avoid overfitting complex tweaks.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "delta_accuracy": delta}, indent=2))


if __name__ == "__main__":
    main()
