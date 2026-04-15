#!/usr/bin/env python3
"""Bounded robustness sweep for lightweight stop-vs-act controller.

Runs a small matched grid over seeds, budgets, and uncertainty policies using the
existing simulation-only stop-vs-act pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.stop_vs_act_controller import (  # noqa: E402
    STOP_VS_ACT_FEATURE_NAMES,
    StopVsActLabelConfig,
    build_stop_vs_act_dataset,
    evaluate_binary_predictions,
    evaluate_controller_comparison,
    fit_stop_vs_act_model,
    write_json,
)


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / max(1, len(vals)))


def _std(vals: list[float]) -> float:
    if len(vals) <= 1:
        return 0.0
    return float(statistics.pstdev(vals))


def _win_loss_tie(margins: list[float], eps: float = 1e-12) -> dict[str, int]:
    wins = sum(1 for m in margins if m > eps)
    losses = sum(1 for m in margins if m < -eps)
    ties = len(margins) - wins - losses
    return {"wins": wins, "losses": losses, "ties": ties, "total": len(margins)}


def _csv_write(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded stop-vs-act robustness sweep")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_controller_robustness")
    p.add_argument("--seeds", default="31,32,33,34")
    p.add_argument("--budgets", default="10,14")
    p.add_argument("--uncertainty-policies", default="none,downweight,filter")
    p.add_argument("--episodes", type=int, default=900)
    p.add_argument("--eval-episodes", type=int, default=350)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--n-init-branches", type=int, default=5)
    p.add_argument("--max-depth", type=int, default=7)
    p.add_argument("--finish-prob-base", type=float, default=0.16)
    p.add_argument("--answer-noise", type=float, default=0.12)
    p.add_argument("--gain-margin", type=float, default=0.015)
    p.add_argument("--uncertainty-band", type=float, default=0.03)
    p.add_argument("--instability-std-threshold", type=float, default=0.045)
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument(
        "--note-path",
        default="experiments/stop_vs_act_controller_robustness_sweep_result_note.md",
    )
    return p.parse_args()


def _extract_policy_row(rows: list[dict[str, Any]], policy_name: str) -> dict[str, Any]:
    return next(r for r in rows if r["policy"] == policy_name)


def _policy_rankings(per_run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cell: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in per_run_rows:
        key = (int(row["seed"]), int(row["budget"]))
        by_cell.setdefault(key, []).append(row)

    win_counts = {"none": 0, "downweight": 0, "filter": 0}
    tie_cells = 0
    for _, rows in by_cell.items():
        rows_sorted = sorted(rows, key=lambda r: float(r["learned_accuracy"]), reverse=True)
        best = float(rows_sorted[0]["learned_accuracy"])
        winners = [r["uncertainty_policy"] for r in rows_sorted if math.isclose(float(r["learned_accuracy"]), best, abs_tol=1e-12)]
        if len(winners) > 1:
            tie_cells += 1
        for w in winners:
            win_counts[str(w)] += 1

    return {
        "cells": len(by_cell),
        "policy_top_counts": win_counts,
        "cells_with_top_tie": tie_cells,
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    uncertainty_policies = _parse_str_list(args.uncertainty_policies)

    label_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
    )

    per_run_rows: list[dict[str, Any]] = []

    for budget in budgets:
        for seed in seeds:
            dataset_rows = build_stop_vs_act_dataset(
                episodes=args.episodes,
                budget=budget,
                seed=seed,
                train_ratio=args.train_ratio,
                n_init_branches=args.n_init_branches,
                max_depth=args.max_depth,
                finish_prob_base=args.finish_prob_base,
                answer_noise=args.answer_noise,
                label_cfg=label_cfg,
            )
            train_rows = [r for r in dataset_rows if r["split"] == "train"]
            test_rows = [r for r in dataset_rows if r["split"] == "test"]
            uncertain_rate = _mean([float(r.get("is_uncertain", 0)) for r in dataset_rows])
            positive_rate = _mean([float(r.get("label_act", 0)) for r in dataset_rows])

            cell_dir = out_dir / f"seed_{seed}" / f"budget_{budget}"
            cell_dir.mkdir(parents=True, exist_ok=True)
            write_json(cell_dir / "dataset_meta.json", {
                "seed": seed,
                "budget": budget,
                "rows": len(dataset_rows),
                "train_rows": len(train_rows),
                "test_rows": len(test_rows),
                "uncertain_rate": uncertain_rate,
                "positive_rate": positive_rate,
                "feature_names": STOP_VS_ACT_FEATURE_NAMES,
            })

            for policy in uncertainty_policies:
                model = fit_stop_vs_act_model(
                    train_rows,
                    model_kind="logistic",
                    uncertain_policy=policy,
                    seed=seed,
                )
                cls = evaluate_binary_predictions(model, test_rows, threshold=args.decision_threshold)
                cmp = evaluate_controller_comparison(
                    model=model,
                    seed=seed,
                    episodes=args.eval_episodes,
                    budget=budget,
                    n_init_branches=args.n_init_branches,
                    max_depth=args.max_depth,
                    finish_prob_base=args.finish_prob_base,
                    answer_noise=args.answer_noise,
                    model_threshold=args.decision_threshold,
                    heuristic_margin=args.heuristic_margin,
                    entropy_threshold=args.entropy_threshold,
                )

                learned_row = _extract_policy_row(cmp.comparison_rows, "learned_stop_vs_act")
                heuristic_row = _extract_policy_row(cmp.comparison_rows, "heuristic_gain_gap")
                uncertainty_row = _extract_policy_row(cmp.comparison_rows, "uncertainty_entropy_only")

                row = {
                    "seed": seed,
                    "budget": budget,
                    "uncertainty_policy": policy,
                    "dataset_rows": len(dataset_rows),
                    "train_rows": len(train_rows),
                    "test_rows": len(test_rows),
                    "dataset_uncertain_rate": uncertain_rate,
                    "dataset_positive_rate": positive_rate,
                    "classification_accuracy": float(cls["accuracy"]),
                    "classification_roc_auc": float(cls["roc_auc"]),
                    "classification_brier": float(cls["brier"]),
                    "train_rows_used": int(model["train_rows_used"]),
                    "learned_accuracy": float(learned_row["accuracy"]),
                    "heuristic_accuracy": float(heuristic_row["accuracy"]),
                    "uncertainty_only_accuracy": float(uncertainty_row["accuracy"]),
                    "learned_avg_best_score": float(learned_row["avg_best_score"]),
                    "heuristic_avg_best_score": float(heuristic_row["avg_best_score"]),
                    "uncertainty_only_avg_best_score": float(uncertainty_row["avg_best_score"]),
                    "learned_vs_heuristic_accuracy_margin": float(cmp.metrics["learned_vs_heuristic_accuracy_margin"]),
                    "learned_vs_uncertainty_accuracy_margin": float(cmp.metrics["learned_vs_uncertainty_accuracy_margin"]),
                    "learned_vs_heuristic_best_score_margin": float(cmp.metrics["learned_vs_heuristic_best_score_margin"]),
                }
                per_run_rows.append(row)

                policy_dir = cell_dir / f"uncertainty_{policy}"
                write_json(
                    policy_dir / "stop_vs_act_train_eval.json",
                    {
                        "settings": {
                            "seed": seed,
                            "budget": budget,
                            "uncertainty_policy": policy,
                            "eval_episodes": args.eval_episodes,
                            "episodes": args.episodes,
                        },
                        "classification": cls,
                        "controller_comparison": {
                            "rows": cmp.comparison_rows,
                            "margins": cmp.metrics,
                        },
                        "model": {
                            k: v for k, v in model.items() if k != "estimator"
                        },
                    },
                )

    per_run_rows = sorted(per_run_rows, key=lambda r: (r["budget"], r["seed"], r["uncertainty_policy"]))
    per_run_csv = out_dir / "robustness_per_run_metrics.csv"
    _csv_write(per_run_csv, per_run_rows, fieldnames=list(per_run_rows[0].keys()))

    summary_policy_rows: list[dict[str, Any]] = []
    for policy in uncertainty_policies:
        rows = [r for r in per_run_rows if r["uncertainty_policy"] == policy]
        lvh = [float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows]
        lvu = [float(r["learned_vs_uncertainty_accuracy_margin"]) for r in rows]
        lvh_score = [float(r["learned_vs_heuristic_best_score_margin"]) for r in rows]
        summary_policy_rows.append(
            {
                "uncertainty_policy": policy,
                "runs": len(rows),
                "mean_learned_vs_heuristic_accuracy_margin": _mean(lvh),
                "std_learned_vs_heuristic_accuracy_margin": _std(lvh),
                "mean_learned_vs_uncertainty_accuracy_margin": _mean(lvu),
                "std_learned_vs_uncertainty_accuracy_margin": _std(lvu),
                "mean_learned_vs_heuristic_best_score_margin": _mean(lvh_score),
                "std_learned_vs_heuristic_best_score_margin": _std(lvh_score),
                "mean_classification_accuracy": _mean([float(r["classification_accuracy"]) for r in rows]),
                "mean_classification_auc": _mean([float(r["classification_roc_auc"]) for r in rows]),
                "mean_classification_brier": _mean([float(r["classification_brier"]) for r in rows]),
                "wins_vs_heuristic": _win_loss_tie(lvh)["wins"],
                "losses_vs_heuristic": _win_loss_tie(lvh)["losses"],
                "ties_vs_heuristic": _win_loss_tie(lvh)["ties"],
                "wins_vs_uncertainty": _win_loss_tie(lvu)["wins"],
                "losses_vs_uncertainty": _win_loss_tie(lvu)["losses"],
                "ties_vs_uncertainty": _win_loss_tie(lvu)["ties"],
            }
        )

    summary_policy_rows = sorted(summary_policy_rows, key=lambda r: r["uncertainty_policy"])
    summary_policy_csv = out_dir / "robustness_summary_by_uncertainty_policy.csv"
    _csv_write(summary_policy_csv, summary_policy_rows, fieldnames=list(summary_policy_rows[0].keys()))

    budget_policy_rows: list[dict[str, Any]] = []
    for budget in budgets:
        for policy in uncertainty_policies:
            rows = [r for r in per_run_rows if int(r["budget"]) == budget and r["uncertainty_policy"] == policy]
            lvh = [float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows]
            lvu = [float(r["learned_vs_uncertainty_accuracy_margin"]) for r in rows]
            budget_policy_rows.append(
                {
                    "budget": budget,
                    "uncertainty_policy": policy,
                    "runs": len(rows),
                    "mean_learned_accuracy": _mean([float(r["learned_accuracy"]) for r in rows]),
                    "mean_learned_vs_heuristic_accuracy_margin": _mean(lvh),
                    "std_learned_vs_heuristic_accuracy_margin": _std(lvh),
                    "mean_learned_vs_uncertainty_accuracy_margin": _mean(lvu),
                    "std_learned_vs_uncertainty_accuracy_margin": _std(lvu),
                    "wins_vs_heuristic": _win_loss_tie(lvh)["wins"],
                    "losses_vs_heuristic": _win_loss_tie(lvh)["losses"],
                    "wins_vs_uncertainty": _win_loss_tie(lvu)["wins"],
                    "losses_vs_uncertainty": _win_loss_tie(lvu)["losses"],
                }
            )

    budget_policy_rows = sorted(budget_policy_rows, key=lambda r: (int(r["budget"]), str(r["uncertainty_policy"])))
    budget_policy_csv = out_dir / "robustness_summary_by_budget_and_uncertainty_policy.csv"
    _csv_write(budget_policy_csv, budget_policy_rows, fieldnames=list(budget_policy_rows[0].keys()))

    top_counts = _policy_rankings(per_run_rows)

    all_lvh = [float(r["learned_vs_heuristic_accuracy_margin"]) for r in per_run_rows]
    all_lvu = [float(r["learned_vs_uncertainty_accuracy_margin"]) for r in per_run_rows]
    global_summary = {
        "settings": {
            "seeds": seeds,
            "budgets": budgets,
            "uncertainty_policies": uncertainty_policies,
            "episodes": args.episodes,
            "eval_episodes": args.eval_episodes,
            "model_kind": "logistic",
            "path": "simulation-only lightweight stop-vs-act",
        },
        "run_count": len(per_run_rows),
        "learned_vs_heuristic_win_loss": _win_loss_tie(all_lvh),
        "learned_vs_uncertainty_win_loss": _win_loss_tie(all_lvu),
        "policy_top_accuracy_counts": top_counts,
    }
    write_json(out_dir / "robustness_summary.json", global_summary)

    # Conservative markdown note answering the required questions.
    best_policy = max(
        summary_policy_rows,
        key=lambda r: float(r["mean_learned_vs_heuristic_accuracy_margin"]),
    )
    best_policy_name = str(best_policy["uncertainty_policy"])

    lines = [
        "# Stop-vs-act bounded robustness sweep result note",
        "",
        "Bounded robustness sweep over lightweight simulation-only stop-vs-act pipeline.",
        "",
        "## Matched sweep setup",
        f"- Seeds: `{','.join(str(s) for s in seeds)}`",
        f"- Budgets: `{','.join(str(b) for b in budgets)}`",
        f"- Uncertainty policies: `{','.join(uncertainty_policies)}`",
        f"- Dataset episodes per (seed,budget): `{args.episodes}`",
        f"- Eval episodes per run: `{args.eval_episodes}`",
        f"- Total runs: `{len(per_run_rows)}`",
        "",
        "## Artifacts",
        f"- Per-run metrics: `{per_run_csv}`",
        f"- Aggregate by uncertainty policy: `{summary_policy_csv}`",
        f"- Aggregate by budget+policy: `{budget_policy_csv}`",
        f"- Global summary JSON: `{out_dir / 'robustness_summary.json'}`",
        "",
        "## Required question answers",
        "",
        "### 1) Does learned stop-vs-act beat the heuristic baseline consistently?",
        f"- Overall win/loss/tie vs heuristic across all runs: `{global_summary['learned_vs_heuristic_win_loss']}`.",
        "- Interpretation: this is not treated as consistent unless wins clearly dominate losses across seeds and budgets.",
        "",
        "### 2) Does uncertainty-aware training help?",
        "- Compare `downweight` / `filter` against `none` by their mean learned-vs-heuristic accuracy margin and win/loss counts.",
    ]
    none_row = next(r for r in summary_policy_rows if r["uncertainty_policy"] == "none")
    for pol in ["downweight", "filter"]:
        pol_row = next(r for r in summary_policy_rows if r["uncertainty_policy"] == pol)
        delta = float(pol_row["mean_learned_vs_heuristic_accuracy_margin"]) - float(
            none_row["mean_learned_vs_heuristic_accuracy_margin"]
        )
        lines.append(
            f"- `{pol}` minus `none` mean learned-vs-heuristic margin: `{delta:+.4f}` "
            f"(policy mean={float(pol_row['mean_learned_vs_heuristic_accuracy_margin']):+.4f}, none mean={float(none_row['mean_learned_vs_heuristic_accuracy_margin']):+.4f})."
        )

    lines.extend(
        [
            "",
            "### 3) Is one uncertainty policy clearly better?",
            f"- Top-counts on learned accuracy across matched (seed,budget) cells: `{top_counts}`.",
            f"- Highest mean learned-vs-heuristic margin in this bounded sweep: `{best_policy_name}`.",
            "- Conservative rule: if top counts are split or margins are close, treat as mixed rather than clear winner.",
            "",
            "### 4) Do gains persist across multiple budgets?",
        ]
    )
    for budget in budgets:
        rows = [r for r in budget_policy_rows if int(r["budget"]) == budget]
        summary_bits = ", ".join(
            [
                f"{r['uncertainty_policy']}: mean_margin={float(r['mean_learned_vs_heuristic_accuracy_margin']):+.4f}, "
                f"W/L={int(r['wins_vs_heuristic'])}/{int(r['losses_vs_heuristic'])}"
                for r in rows
            ]
        )
        lines.append(f"- Budget `{budget}` -> {summary_bits}.")

    lines.extend(
        [
            "",
            "### 5) Are results promising, mixed, or weak?",
            "- Label as **promising** only if learned beats baselines with clear margin and low seed sensitivity.",
            "- Label as **mixed** if wins exist but losses/variance remain material.",
            "- Label as **weak** if losses dominate or effects are near-zero/noisy.",
            "",
            "## Failure slices / instability patterns",
        ]
    )

    bad_rows = [
        r
        for r in per_run_rows
        if float(r["learned_vs_heuristic_accuracy_margin"]) < 0.0
        or float(r["learned_vs_uncertainty_accuracy_margin"]) < 0.0
    ]
    if not bad_rows:
        lines.append("- No negative-margin runs found in this bounded grid.")
    else:
        for r in bad_rows[:12]:
            lines.append(
                "- "
                f"seed={r['seed']}, budget={r['budget']}, policy={r['uncertainty_policy']}, "
                f"margin_vs_heuristic={float(r['learned_vs_heuristic_accuracy_margin']):+.4f}, "
                f"margin_vs_uncertainty={float(r['learned_vs_uncertainty_accuracy_margin']):+.4f}."
            )
        if len(bad_rows) > 12:
            lines.append(f"- ... plus {len(bad_rows) - 12} additional negative-margin runs (see CSV).")

    lines.extend(
        [
            "",
            "## Conservative recommendation",
            "- Use aggregate + win/loss evidence as the deciding signal, not a single best run.",
            "- If mixed, keep this direction but avoid broad expansion until label/proxy robustness improves.",
            "- If weak, revise label/training setup before deeper integration.",
            "",
        ]
    )

    note_path = Path(args.note_path)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "note_path": str(note_path)}, indent=2))


if __name__ == "__main__":
    main()
