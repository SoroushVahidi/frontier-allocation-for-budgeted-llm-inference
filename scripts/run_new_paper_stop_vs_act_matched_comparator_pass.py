#!/usr/bin/env python3
"""Bounded matched-randomness ACT-vs-STOP comparator pass for stop-vs-act."""

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
    write_json,
)


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / max(1, len(xs)))


def _std(xs: list[float]) -> float:
    if len(xs) <= 1:
        return 0.0
    return float(statistics.pstdev(xs))


def _win_loss_tie(vals: list[float], eps: float = 1e-12) -> dict[str, int]:
    wins = sum(1 for x in vals if x > eps)
    losses = sum(1 for x in vals if x < -eps)
    ties = len(vals) - wins - losses
    return {"wins": wins, "losses": losses, "ties": ties, "total": len(vals)}


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded matched ACT-vs-STOP comparator pass")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_matched_comparator")
    p.add_argument("--diagnosis-seeds", default="31,32,33")
    p.add_argument("--diagnosis-budgets", default="10,14")
    p.add_argument("--compare-seeds", default="31,32,33")
    p.add_argument("--compare-budgets", default="10,14")
    p.add_argument("--episodes", type=int, default=700)
    p.add_argument("--eval-episodes", type=int, default=280)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--n-init-branches", type=int, default=5)
    p.add_argument("--max-depth", type=int, default=7)
    p.add_argument("--finish-prob-base", type=float, default=0.16)
    p.add_argument("--answer-noise", type=float, default=0.12)
    p.add_argument("--gain-margin", type=float, default=0.015)
    p.add_argument("--uncertainty-band", type=float, default=0.03)
    p.add_argument("--instability-std-threshold", type=float, default=0.045)
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--small-horizon-steps", type=int, default=2)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--uncertainty-policy", default="downweight_nonpositive")
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_matched_comparator_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_matched_comparator_comparison_note.md")
    return p.parse_args()


def _build_dataset(
    *,
    seed: int,
    budget: int,
    episodes: int,
    train_ratio: float,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
    cfg: StopVsActLabelConfig,
) -> list[dict[str, Any]]:
    return build_stop_vs_act_dataset(
        episodes=episodes,
        budget=budget,
        seed=seed,
        train_ratio=train_ratio,
        n_init_branches=n_init_branches,
        max_depth=max_depth,
        finish_prob_base=finish_prob_base,
        answer_noise=answer_noise,
        label_cfg=cfg,
    )


def _dataset_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "rows": float(len(rows)),
        "label_positive_rate": _mean([float(r["label_act"]) for r in rows]),
        "uncertain_rate": _mean([float(r["is_uncertain"]) for r in rows]),
        "delta_std_mean": _mean([float(r["delta_std"]) for r in rows]),
        "delta_sign_flip_rate_mean": _mean([float(r.get("delta_sign_flip_rate", 0.0)) for r in rows]),
        "target_reliability_weight_mean": _mean([float(r.get("target_reliability_weight", 1.0)) for r in rows]),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_seeds = _parse_int_list(args.diagnosis_seeds)
    diagnosis_budgets = _parse_int_list(args.diagnosis_budgets)
    compare_seeds = _parse_int_list(args.compare_seeds)
    compare_budgets = _parse_int_list(args.compare_budgets)

    default_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_best_other_gain",
        target_stabilization_mode="none",
    )
    matched_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="counterfactual_act_vs_stop_h2_matched",
        small_horizon_steps=args.small_horizon_steps,
        target_stabilization_mode="none",
    )

    diag_rows: list[dict[str, Any]] = []
    for budget in diagnosis_budgets:
        for seed in diagnosis_seeds:
            rows_old = _build_dataset(
                seed=seed,
                budget=budget,
                episodes=args.episodes,
                train_ratio=args.train_ratio,
                n_init_branches=args.n_init_branches,
                max_depth=args.max_depth,
                finish_prob_base=args.finish_prob_base,
                answer_noise=args.answer_noise,
                cfg=default_cfg,
            )
            rows_new = _build_dataset(
                seed=seed,
                budget=budget,
                episodes=args.episodes,
                train_ratio=args.train_ratio,
                n_init_branches=args.n_init_branches,
                max_depth=args.max_depth,
                finish_prob_base=args.finish_prob_base,
                answer_noise=args.answer_noise,
                cfg=matched_cfg,
            )
            diag_rows.append({"seed": seed, "budget": budget, "setup": "default", **_dataset_stats(rows_old)})
            diag_rows.append({"seed": seed, "budget": budget, "setup": "matched_comparator", **_dataset_stats(rows_new)})

    _write_csv(out_dir / "matched_comparator_label_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    old_diag = [r for r in diag_rows if r["setup"] == "default"]
    new_diag = [r for r in diag_rows if r["setup"] == "matched_comparator"]
    diagnosis_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "why_stabilization_was_not_enough": (
            "Repeated averaging reduced estimator variance, but preserved comparator mismatch: default target still uses proxy best-other stop baseline and non-paired ACT/STOP futures."
        ),
        "most_plausible_mismatch": {
            "primary": "stop-baseline mismatch plus downstream randomness mismatch between ACT and STOP futures",
            "evidence": {
                "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in old_diag]),
                "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in old_diag]),
            },
        },
        "single_strategy": {
            "name": "matched_act_vs_stop_h2_paired_rng",
            "definition": (
                "Use ACT-vs-STOP horizon-2 local comparator with paired common-random-number rollouts; "
                "ACT and STOP share the same per-sample RNG seed and differ only in first-step action constraint (act-here vs skip-here)."
            ),
            "shared_between_act_and_stop": [
                "same initial active snapshot",
                "same horizon and remaining-budget context",
                "same per-sample RNG seed",
                "same downstream policy after first-step intervention",
            ],
        },
        "old_vs_new_target_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in old_diag]),
            "matched_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in new_diag]),
            "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in old_diag]),
            "matched_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in new_diag]),
        },
    }
    write_json(out_dir / "matched_comparator_diagnosis_summary.json", diagnosis_summary)

    diagnosis_note = [
        "# Stop-vs-act matched-comparator diagnosis note",
        "",
        "## 1) Why stabilization likely failed to move controller outcomes",
        "- Repeated averaging reduced target noise but kept the same local comparison object; it did not fix ACT-vs-STOP comparator mismatch.",
        "",
        "## 2) Most plausible mismatch bottleneck now",
        "- Primary mismatch: stop-baseline mismatch + downstream randomness mismatch between ACT and STOP futures.",
        f"- Default sign-flip-rate mean: `{diagnosis_summary['most_plausible_mismatch']['evidence']['default_sign_flip_rate_mean']:.4f}`.",
        f"- Default delta-std mean: `{diagnosis_summary['most_plausible_mismatch']['evidence']['default_delta_std_mean']:.4f}`.",
        "",
        "## 3) Single lightweight next strategy",
        "- Use matched ACT-vs-STOP horizon-2 local comparator with paired RNG seeds.",
        "- Keep ACT and STOP futures identical except for the first-step intervention (ACT-here vs skip-here).",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note) + "\n", encoding="utf-8")

    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
            for setup_name, cfg in [("default", default_cfg), ("matched_comparator", matched_cfg)]:
                ds_rows = _build_dataset(
                    seed=seed,
                    budget=budget,
                    episodes=args.episodes,
                    train_ratio=args.train_ratio,
                    n_init_branches=args.n_init_branches,
                    max_depth=args.max_depth,
                    finish_prob_base=args.finish_prob_base,
                    answer_noise=args.answer_noise,
                    cfg=cfg,
                )
                train_rows = [r for r in ds_rows if r["split"] == "train"]
                test_rows = [r for r in ds_rows if r["split"] == "test"]
                model = fit_stop_vs_act_model(
                    train_rows,
                    model_kind="logistic",
                    uncertain_policy=args.uncertainty_policy,
                    seed=seed,
                    reliability_power=0.0,
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
                by_policy = {r["policy"]: r for r in cmp.comparison_rows}
                stats = _dataset_stats(ds_rows)
                compare_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "setup": setup_name,
                        "target_mode": cfg.target_mode,
                        "train_rows_used": int(model["train_rows_used"]),
                        "label_positive_rate": stats["label_positive_rate"],
                        "uncertain_rate": stats["uncertain_rate"],
                        "delta_std_mean": stats["delta_std_mean"],
                        "delta_sign_flip_rate_mean": stats["delta_sign_flip_rate_mean"],
                        "classification_accuracy": float(cls["accuracy"]),
                        "classification_auc": float(cls["roc_auc"]),
                        "learned_accuracy": float(by_policy["learned_stop_vs_act"]["accuracy"]),
                        "heuristic_accuracy": float(by_policy["heuristic_gain_gap"]["accuracy"]),
                        "learned_vs_heuristic_accuracy_margin": float(cmp.metrics["learned_vs_heuristic_accuracy_margin"]),
                        "learned_vs_uncertainty_accuracy_margin": float(cmp.metrics["learned_vs_uncertainty_accuracy_margin"]),
                        "learned_avg_best_score": float(by_policy["learned_stop_vs_act"]["avg_best_score"]),
                        "heuristic_avg_best_score": float(by_policy["heuristic_gain_gap"]["avg_best_score"]),
                        "learned_vs_heuristic_score_margin": float(
                            by_policy["learned_stop_vs_act"]["avg_best_score"] - by_policy["heuristic_gain_gap"]["avg_best_score"]
                        ),
                    }
                )

    _write_csv(out_dir / "matched_comparator_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    default_rows = [r for r in compare_rows if r["setup"] == "default"]
    new_rows = [r for r in compare_rows if r["setup"] == "matched_comparator"]
    new_minus_old_acc = [
        float(n["learned_vs_heuristic_accuracy_margin"]) - float(o["learned_vs_heuristic_accuracy_margin"]) for o, n in zip(default_rows, new_rows)
    ]
    new_minus_old_score = [
        float(n["learned_vs_heuristic_score_margin"]) - float(o["learned_vs_heuristic_score_margin"]) for o, n in zip(default_rows, new_rows)
    ]

    summary = {
        "comparison_grid": {"seeds": compare_seeds, "budgets": compare_budgets, "episodes": args.episodes, "eval_episodes": args.eval_episodes},
        "comparator_definitions": {
            "default": "proxy_best_other_gain: E[gain_here] - best_other_expected_next_gain",
            "matched_comparator": (
                "counterfactual_act_vs_stop_h2_matched: E[value_h2(force_act_here) - value_h2(skip_here_first)] with paired per-sample RNG seeds"
            ),
        },
        "old_vs_new_comparator_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in default_rows]),
            "matched_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in new_rows]),
            "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in default_rows]),
            "matched_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in new_rows]),
        },
        "controller_metrics": {
            "default_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "matched_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in new_rows]),
            "default_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in default_rows]),
            "matched_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in new_rows]),
        },
        "win_loss": {
            "default_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "matched_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in new_rows]),
            "matched_vs_default_accuracy": _win_loss_tie(new_minus_old_acc),
            "matched_vs_default_score": _win_loss_tie(new_minus_old_score),
        },
        "stability_signal": {
            "default_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "matched_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in new_rows]),
        },
        "interpretation": {
            "conservative_read": "Bounded evidence only; if mixed, do not replace default.",
            "recommendation": "replace_default" if _mean(new_minus_old_acc) > 0.0 else "keep_current_default",
            "next_best_move": (
                "If mixed or negative, keep this as optional comparator mode and next test tighter policy-coupled stop baseline under identical future branch-selection context."
            ),
        },
    }
    write_json(out_dir / "matched_comparator_comparison_summary.json", summary)

    comparison_note = [
        "# Stop-vs-act bounded matched-comparator comparison note",
        "",
        "## Setup",
        "- Anchor baseline: current default `proxy_best_other_gain`.",
        "- New mode: `counterfactual_act_vs_stop_h2_matched` with paired RNG ACT/STOP rollouts.",
        f"- Grid: seeds={compare_seeds}, budgets={compare_budgets}.",
        "",
        "## Results (bounded)",
        f"- Default vs heuristic W/L/T (accuracy): `{summary['win_loss']['default_vs_heuristic_accuracy']}`.",
        f"- Matched comparator vs heuristic W/L/T (accuracy): `{summary['win_loss']['matched_vs_heuristic_accuracy']}`.",
        f"- Matched comparator vs default W/L/T (accuracy): `{summary['win_loss']['matched_vs_default_accuracy']}`.",
        f"- Mean learned-vs-heuristic accuracy margin: default `{summary['controller_metrics']['default_mean_learned_vs_heuristic_accuracy_margin']:+.4f}` vs matched `{summary['controller_metrics']['matched_mean_learned_vs_heuristic_accuracy_margin']:+.4f}`.",
        f"- Mean sign-flip-rate: default `{summary['old_vs_new_comparator_stats']['default_sign_flip_rate_mean']:.4f}` vs matched `{summary['old_vs_new_comparator_stats']['matched_sign_flip_rate_mean']:.4f}`.",
        "",
        "## Conservative interpretation",
        "- Treat this as a small matched signal only.",
        "- If local comparator stability improves but controller metrics do not, do not promote replacement.",
        f"- Current recommendation: `{summary['interpretation']['recommendation']}`.",
    ]
    Path(args.comparison_note_path).write_text("\n".join(comparison_note) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
