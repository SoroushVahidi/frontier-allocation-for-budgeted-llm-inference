#!/usr/bin/env python3
"""Lightweight matched-coverage filtering evaluation for stop-vs-act.

Compares three training-data variants on the same generated state pool:
- default (all training rows),
- selective filter (quality-oriented subset),
- random filter baseline with matched retained coverage.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.stop_vs_act_controller import (  # noqa: E402
    StopVsActLabelConfig,
    build_stop_vs_act_dataset,
    evaluate_binary_predictions,
    evaluate_controller_comparison,
    fit_stop_vs_act_model,
    stop_vs_act_probability,
    write_json,
)


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return float(sum(xs) / len(xs))


def _std(xs: list[float]) -> float:
    if len(xs) <= 1:
        return 0.0
    return float(statistics.pstdev(xs))


def _selective_subset(train_rows: list[dict[str, Any]], retained_count: int) -> list[dict[str, Any]]:
    ordered = sorted(
        train_rows,
        key=lambda r: (
            int(r.get("is_uncertain", 0)),
            -float(r.get("target_reliability_weight", 1.0)),
            -abs(float(r.get("delta_mean", 0.0))),
        ),
    )
    return ordered[:retained_count]


def _random_subset(train_rows: list[dict[str, Any]], retained_count: int, seed: int) -> list[dict[str, Any]]:
    import random

    rng = random.Random(seed)
    idxs = list(range(len(train_rows)))
    rng.shuffle(idxs)
    keep = set(idxs[:retained_count])
    return [r for i, r in enumerate(train_rows) if i in keep]


def _slice_uncertainty_metrics(model: dict[str, Any], rows: list[dict[str, Any]], threshold: float) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for name, flag in (("certain", 0), ("uncertain", 1)):
        sub = [r for r in rows if int(r.get("is_uncertain", 0)) == flag]
        if not sub:
            out[name] = {"rows": 0.0, "accuracy": 0.0, "pred_act_rate": 0.0}
            continue
        cls = evaluate_binary_predictions(model, sub, threshold=threshold)
        act_rate = _mean(
            [1.0 if stop_vs_act_probability(model, {k: float(r[k]) for k in model["feature_names"]}) >= threshold else 0.0 for r in sub]
        )
        out[name] = {
            "rows": float(len(sub)),
            "accuracy": float(cls["accuracy"]),
            "pred_act_rate": float(act_rate),
        }
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run matched-coverage filtering eval on lightweight stop-vs-act data")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_matched_coverage_filtering")
    p.add_argument("--note-path", default="experiments/stop_vs_act_matched_coverage_filtering_result_note.md")
    p.add_argument("--seeds", default="31,32,33")
    p.add_argument("--budgets", default="10,14")
    p.add_argument("--episodes", type=int, default=520)
    p.add_argument("--eval-episodes", type=int, default=220)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--retain-frac", type=float, default=0.7)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--n-init-branches", type=int, default=5)
    p.add_argument("--max-depth", type=int, default=7)
    p.add_argument("--finish-prob-base", type=float, default=0.16)
    p.add_argument("--answer-noise", type=float, default=0.12)
    p.add_argument("--gain-margin", type=float, default=0.015)
    p.add_argument("--uncertainty-band", type=float, default=0.03)
    p.add_argument("--instability-std-threshold", type=float, default=0.045)
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)

    label_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_best_other_gain",
        target_stabilization_mode="none",
    )

    rows_csv: list[dict[str, Any]] = []
    detail_runs: list[dict[str, Any]] = []

    for budget in budgets:
        for seed in seeds:
            dataset = build_stop_vs_act_dataset(
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
            train_rows = [r for r in dataset if r["split"] == "train"]
            test_rows = [r for r in dataset if r["split"] == "test"]
            retained_count = max(1, min(len(train_rows), int(round(len(train_rows) * args.retain_frac))))

            variants: dict[str, list[dict[str, Any]]] = {
                "default": train_rows,
                "selective_filtered": _selective_subset(train_rows, retained_count),
                "random_filtered_matched": _random_subset(train_rows, retained_count, seed=seed + budget * 1009),
            }

            for variant_name, variant_train in variants.items():
                model = fit_stop_vs_act_model(
                    variant_train,
                    model_kind="logistic",
                    uncertain_policy="none",
                    seed=seed,
                    reliability_power=0.0,
                )
                cls = evaluate_binary_predictions(model, test_rows, threshold=args.decision_threshold)
                test_pred_act_rate = _mean(
                    [
                        1.0
                        if stop_vs_act_probability(model, {k: float(r[k]) for k in model["feature_names"]})
                        >= args.decision_threshold
                        else 0.0
                        for r in test_rows
                    ]
                )

                cmp = evaluate_controller_comparison(
                    model=model,
                    seed=seed + 50_000,
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
                learned = next(row for row in cmp.comparison_rows if row["policy"] == "learned_stop_vs_act")
                uncertainty_slice = _slice_uncertainty_metrics(model, test_rows, threshold=args.decision_threshold)

                result_row = {
                    "seed": seed,
                    "budget": budget,
                    "variant": variant_name,
                    "train_rows_used": len(variant_train),
                    "train_rows_total": len(train_rows),
                    "retained_coverage": float(len(variant_train)) / max(1, len(train_rows)),
                    "test_accuracy": float(cls["accuracy"]),
                    "test_roc_auc": float(cls["roc_auc"]),
                    "test_brier": float(cls["brier"]),
                    "test_pred_act_rate": float(test_pred_act_rate),
                    "controller_accuracy": float(learned["accuracy"]),
                    "controller_solve_rate": float(learned["solve_rate"]),
                    "controller_avg_actions": float(learned["avg_actions"]),
                    "controller_avg_best_score": float(learned["avg_best_score"]),
                    "certain_slice_accuracy": float(uncertainty_slice["certain"]["accuracy"]),
                    "uncertain_slice_accuracy": float(uncertainty_slice["uncertain"]["accuracy"]),
                }
                rows_csv.append(result_row)
                detail_runs.append(
                    {
                        "run_key": {"seed": seed, "budget": budget, "variant": variant_name},
                        "result": result_row,
                        "uncertainty_slice": uncertainty_slice,
                        "controller_rows": cmp.comparison_rows,
                    }
                )

    csv_path = out_dir / "matched_coverage_filtering_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
        writer.writeheader()
        for row in rows_csv:
            writer.writerow(row)

    summary: dict[str, Any] = {
        "settings": {
            "seeds": seeds,
            "budgets": budgets,
            "episodes": args.episodes,
            "eval_episodes": args.eval_episodes,
            "retain_frac": args.retain_frac,
            "decision_threshold": args.decision_threshold,
            "label_target_mode": "proxy_best_other_gain",
            "label_stabilization": "none",
        },
        "per_run": detail_runs,
    }

    by_variant: dict[str, list[dict[str, Any]]] = {}
    for r in rows_csv:
        by_variant.setdefault(str(r["variant"]), []).append(r)

    aggregate: dict[str, Any] = {}
    for variant, vals in by_variant.items():
        aggregate[variant] = {
            "retained_coverage_mean": _mean([float(v["retained_coverage"]) for v in vals]),
            "controller_avg_best_score_mean": _mean([float(v["controller_avg_best_score"]) for v in vals]),
            "controller_avg_best_score_std": _std([float(v["controller_avg_best_score"]) for v in vals]),
            "controller_accuracy_mean": _mean([float(v["controller_accuracy"]) for v in vals]),
            "controller_avg_actions_mean": _mean([float(v["controller_avg_actions"]) for v in vals]),
            "test_roc_auc_mean": _mean([float(v["test_roc_auc"]) for v in vals]),
            "test_pred_act_rate_mean": _mean([float(v["test_pred_act_rate"]) for v in vals]),
            "uncertain_slice_accuracy_mean": _mean([float(v["uncertain_slice_accuracy"]) for v in vals]),
            "certain_slice_accuracy_mean": _mean([float(v["certain_slice_accuracy"]) for v in vals]),
        }

    sel = aggregate.get("selective_filtered", {})
    rnd = aggregate.get("random_filtered_matched", {})
    dft = aggregate.get("default", {})
    comparisons = {
        "selective_minus_random": {
            "controller_avg_best_score": float(sel.get("controller_avg_best_score_mean", 0.0) - rnd.get("controller_avg_best_score_mean", 0.0)),
            "controller_accuracy": float(sel.get("controller_accuracy_mean", 0.0) - rnd.get("controller_accuracy_mean", 0.0)),
            "controller_avg_actions": float(sel.get("controller_avg_actions_mean", 0.0) - rnd.get("controller_avg_actions_mean", 0.0)),
            "test_roc_auc": float(sel.get("test_roc_auc_mean", 0.0) - rnd.get("test_roc_auc_mean", 0.0)),
            "uncertain_slice_accuracy": float(sel.get("uncertain_slice_accuracy_mean", 0.0) - rnd.get("uncertain_slice_accuracy_mean", 0.0)),
        },
        "selective_minus_default": {
            "controller_avg_best_score": float(sel.get("controller_avg_best_score_mean", 0.0) - dft.get("controller_avg_best_score_mean", 0.0)),
            "controller_accuracy": float(sel.get("controller_accuracy_mean", 0.0) - dft.get("controller_accuracy_mean", 0.0)),
            "controller_avg_actions": float(sel.get("controller_avg_actions_mean", 0.0) - dft.get("controller_avg_actions_mean", 0.0)),
            "test_roc_auc": float(sel.get("test_roc_auc_mean", 0.0) - dft.get("test_roc_auc_mean", 0.0)),
        },
    }

    summary["aggregate_by_variant"] = aggregate
    summary["comparisons"] = comparisons
    write_json(out_dir / "matched_coverage_filtering_summary.json", summary)

    lines = [
        "# Matched-coverage filtering result note (lightweight, pre-oracle)",
        "",
        "## Setup",
        "- Anchor kept fixed: current default stop-vs-act label path (`proxy_best_other_gain`, no stabilization).",
        "- Three train-set variants on matched state pools per seed/budget: default, selective filtered, random filtered with matched retained coverage.",
        f"- Retained coverage for filtered variants: {args.retain_frac:.2f} of train rows (rounded per run).",
        f"- Grid: seeds={seeds}, budgets={budgets}, train episodes={args.episodes}, controller eval episodes={args.eval_episodes}.",
        "",
        "## Aggregate highlights",
        f"- Selective vs matched-random: Δ controller avg_best_score = {comparisons['selective_minus_random']['controller_avg_best_score']:+.4f}.",
        f"- Selective vs matched-random: Δ controller accuracy = {comparisons['selective_minus_random']['controller_accuracy']:+.4f}.",
        f"- Selective vs matched-random: Δ controller avg_actions = {comparisons['selective_minus_random']['controller_avg_actions']:+.4f}.",
        f"- Selective vs matched-random: Δ test ROC-AUC = {comparisons['selective_minus_random']['test_roc_auc']:+.4f}.",
        f"- Uncertainty slice (test labels): selective minus random uncertain-slice accuracy = {comparisons['selective_minus_random']['uncertain_slice_accuracy']:+.4f}.",
        "",
        "## Conservative interpretation",
        "- This is a low-compute proxy-label study only; it is not oracle evidence.",
        "- If selective > random at matched coverage, that is consistent with supervision-quality signal beyond pure data reduction.",
        "- If selective gains also come with large action-rate shifts, matched-rate follow-up is still needed before causal claims about quality-only improvements.",
        "- Use this as design input for later oracle-distillation: preserve matched-coverage random baselines and add matched-rate checks.",
    ]
    Path(args.note_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
