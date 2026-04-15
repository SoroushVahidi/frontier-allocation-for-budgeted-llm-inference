#!/usr/bin/env python3
"""Train/evaluate a lightweight stop-vs-act controller and emit compact notes."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.stop_vs_act_controller import (
    STOP_VS_ACT_FEATURE_NAMES,
    evaluate_binary_predictions,
    evaluate_controller_comparison,
    fit_stop_vs_act_model,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train/evaluate stop-vs-act controller")
    parser.add_argument("--dataset", default="outputs/stop_vs_act_controller/stop_vs_act_dataset.jsonl")
    parser.add_argument("--output-dir", default="outputs/stop_vs_act_controller")
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--model-kind", choices=["logistic", "gbdt"], default="logistic")
    parser.add_argument("--uncertain-policy", choices=["none", "filter", "downweight"], default="downweight")
    parser.add_argument("--decision-threshold", type=float, default=0.5)
    parser.add_argument("--eval-episodes", type=int, default=500)
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--n-init-branches", type=int, default=5)
    parser.add_argument("--max-depth", type=int, default=7)
    parser.add_argument("--finish-prob-base", type=float, default=0.16)
    parser.add_argument("--answer-noise", type=float, default=0.12)
    parser.add_argument("--heuristic-margin", type=float, default=0.01)
    parser.add_argument("--entropy-threshold", type=float, default=0.62)
    return parser.parse_args()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _write_run_note(path: Path, payload: dict[str, Any]) -> None:
    cls = payload["classification"]
    cmp_rows = payload["controller_comparison"]["rows"]
    cmp = {row["policy"]: row for row in cmp_rows}
    margins = payload["controller_comparison"]["margins"]

    lines = [
        "# Stop-vs-act lightweight controller result note",
        "",
        "This run is a bounded first-pass experiment for fixed-budget branch/controller allocation.",
        "",
        "## Label construction rule",
        "- Binary target: ACT if estimated +1 action gain on this branch beats the best alternative branch gain by `gain_margin`; else STOP.",
        "- Estimation: small bounded one-step rollout (`expand` then optional `verify`) over a few local samples.",
        "- Delta proxy: `delta = E[act_gain_here] - best_other_expected_next_gain`.",
        "",
        "## Uncertainty filtering/weighting rule",
        "- Mark example uncertain if delta is near zero or rollout delta variance is high.",
        "- Training policy in this run: uncertain examples are retained with reduced sample weight (downweight mode).",
        "",
        "## Compact output summary",
        f"- Classification: accuracy={cls['accuracy']:.4f}, ROC-AUC={cls['roc_auc']:.4f}, Brier={cls['brier']:.4f}.",
        f"- Learned controller: accuracy={cmp['learned_stop_vs_act']['accuracy']:.4f}, avg_best_score={cmp['learned_stop_vs_act']['avg_best_score']:.4f}.",
        f"- Heuristic baseline: accuracy={cmp['heuristic_gain_gap']['accuracy']:.4f}, avg_best_score={cmp['heuristic_gain_gap']['avg_best_score']:.4f}.",
        f"- Uncertainty-threshold-only baseline: accuracy={cmp['uncertainty_entropy_only']['accuracy']:.4f}, avg_best_score={cmp['uncertainty_entropy_only']['avg_best_score']:.4f}.",
        f"- Margin learned vs heuristic (accuracy): {margins['learned_vs_heuristic_accuracy_margin']:+.4f}.",
        f"- Margin learned vs uncertainty-only (accuracy): {margins['learned_vs_uncertainty_accuracy_margin']:+.4f}.",
        "",
        "## Conservative interpretation",
        "- This is promising only if the learned controller is consistently better than both baselines across seeds/budgets.",
        "- Treat this as a lightweight feasibility check; no claim of final superiority.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(Path(args.dataset))
    train_rows = [r for r in rows if r["split"] == "train"]
    test_rows = [r for r in rows if r["split"] == "test"]

    model = fit_stop_vs_act_model(
        train_rows,
        model_kind=args.model_kind,
        uncertain_policy=args.uncertain_policy,
        seed=args.seed,
    )

    cls_metrics = evaluate_binary_predictions(model, test_rows, threshold=args.decision_threshold)
    cmp_artifacts = evaluate_controller_comparison(
        model=model,
        seed=args.seed,
        episodes=args.eval_episodes,
        budget=args.budget,
        n_init_branches=args.n_init_branches,
        max_depth=args.max_depth,
        finish_prob_base=args.finish_prob_base,
        answer_noise=args.answer_noise,
        model_threshold=args.decision_threshold,
        heuristic_margin=args.heuristic_margin,
        entropy_threshold=args.entropy_threshold,
    )

    model_export = dict(model)
    if model_export.get("model_type") == "gbdt":
        # Avoid binary/pickle export for reproducibility constraints.
        est = model_export.pop("estimator", None)
        if est is not None:
            model_export["export_note"] = "GBDT trained in-memory; estimator omitted from JSON export by design"

    run_summary = {
        "dataset": str(args.dataset),
        "feature_names": STOP_VS_ACT_FEATURE_NAMES,
        "model": model_export,
        "classification": cls_metrics,
        "controller_comparison": {
            "rows": cmp_artifacts.comparison_rows,
            "margins": cmp_artifacts.metrics,
        },
        "settings": {
            "model_kind": args.model_kind,
            "uncertain_policy": args.uncertain_policy,
            "decision_threshold": args.decision_threshold,
            "eval_episodes": args.eval_episodes,
            "budget": args.budget,
        },
    }

    write_json(out_dir / "stop_vs_act_train_eval.json", run_summary)
    if model_export.get("model_type") == "logistic":
        write_json(out_dir / "models" / "stop_vs_act_logistic_v1.json", model_export)

    csv_path = out_dir / "stop_vs_act_controller_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "policy",
                "accuracy",
                "solve_rate",
                "avg_actions",
                "avg_best_score",
                "avg_primary_actions",
                "avg_routed_elsewhere",
            ],
        )
        writer.writeheader()
        for row in cmp_artifacts.comparison_rows:
            writer.writerow(row)

    _write_run_note(Path("experiments/stop_vs_act_controller_result_note.md"), run_summary)
    print(json.dumps(run_summary, indent=2))


if __name__ == "__main__":
    main()
