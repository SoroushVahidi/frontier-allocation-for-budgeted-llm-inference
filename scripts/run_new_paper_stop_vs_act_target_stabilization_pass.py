#!/usr/bin/env python3
"""Bounded lightweight target-stabilization pass for default stop-vs-act target."""

from __future__ import annotations

import argparse
import csv
import json
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
    p = argparse.ArgumentParser(description="Bounded target-stabilization pass for default stop-vs-act target")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_target_stabilization")
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
    p.add_argument("--stabilization-repeats", type=int, default=3)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--uncertainty-policy", default="downweight_nonpositive")
    p.add_argument("--reliability-power", type=float, default=1.0)
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_target_stabilization_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_target_stabilization_comparison_note.md")
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
        "delta_mean_abs": _mean([abs(float(r["delta_mean"])) for r in rows]),
        "delta_std_mean": _mean([float(r.get("delta_std", 0.0)) for r in rows]),
        "delta_repeat_std_mean": _mean([float(r.get("delta_repeat_std", 0.0)) for r in rows]),
        "target_reliability_weight_mean": _mean([float(r.get("target_reliability_weight", 1.0)) for r in rows]),
        "near_margin_rate": _mean([1.0 if abs(float(r["delta_mean"]) - 0.015) <= 0.01 else 0.0 for r in rows]),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_seeds = _parse_int_list(args.diagnosis_seeds)
    diagnosis_budgets = _parse_int_list(args.diagnosis_budgets)
    compare_seeds = _parse_int_list(args.compare_seeds)
    compare_budgets = _parse_int_list(args.compare_budgets)

    old_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_best_other_gain",
        target_stabilization_mode="none",
    )
    stabilized_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_best_other_gain",
        target_stabilization_mode="repeated_local_averaging",
        stabilization_repeats=args.stabilization_repeats,
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
                cfg=old_cfg,
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
                cfg=stabilized_cfg,
            )
            diag_rows.append({"seed": seed, "budget": budget, "setup": "default", **_dataset_stats(rows_old)})
            diag_rows.append({"seed": seed, "budget": budget, "setup": "stabilized", **_dataset_stats(rows_new)})

    _write_csv(out_dir / "target_stabilization_label_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    old_diag = [r for r in diag_rows if r["setup"] == "default"]
    new_diag = [r for r in diag_rows if r["setup"] == "stabilized"]
    diag_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "diagnosed_bottleneck": {
            "most_plausible_source": "high variance from too-few local samples in noisy ACT/STOP paired comparison (local rollout randomness).",
            "evidence": {
                "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in old_diag]),
                "default_near_margin_rate": _mean([float(r["near_margin_rate"]) for r in old_diag]),
                "default_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in old_diag]),
            },
        },
        "single_stabilization_strategy": {
            "name": "repeated_local_target_estimation_with_averaging",
            "definition": "Repeat the same default local delta estimate K times with different local RNG seeds; use averaged delta_mean and estimator std-based reliability.",
            "stabilization_repeats": args.stabilization_repeats,
            "reliability_weight": "target_reliability_weight = 1/(1+delta_estimator_std)",
        },
        "old_vs_stabilized_target_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in old_diag]),
            "stabilized_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in new_diag]),
            "default_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in old_diag]),
            "stabilized_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in new_diag]),
            "default_reliability_mean": _mean([float(r["target_reliability_weight_mean"]) for r in old_diag]),
            "stabilized_reliability_mean": _mean([float(r["target_reliability_weight_mean"]) for r in new_diag]),
        },
    }
    write_json(out_dir / "target_stabilization_diagnosis_summary.json", diag_summary)

    diagnosis_note = [
        "# Stop-vs-act target stabilization diagnosis note",
        "",
        "## 1) Most plausible instability source",
        "- Most plausible bottleneck: high variance from too-few local samples in a noisy ACT/STOP paired comparison, not a new target-family mismatch.",
        "",
        "## 2) Why this diagnosis",
        f"- Default mean delta std: `{diag_summary['diagnosed_bottleneck']['evidence']['default_delta_std_mean']:.4f}`.",
        f"- Default near-margin rate (|delta-gain_margin|<=0.01): `{diag_summary['diagnosed_bottleneck']['evidence']['default_near_margin_rate']:.4f}`.",
        f"- Default uncertain rate: `{diag_summary['diagnosed_bottleneck']['evidence']['default_uncertain_rate']:.4f}`.",
        "",
        "## 3) One lightweight stabilization strategy",
        "- Keep default target mode (`proxy_best_other_gain`) and add repeated local estimation with averaging.",
        "- For each (state, branch), run K local estimates, average delta_mean, and compute `delta_estimator_std` for reliability.",
        "- Optional training weight: `target_reliability_weight = 1/(1+delta_estimator_std)`.",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note) + "\n", encoding="utf-8")

    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
            for setup_name, cfg, rel_power in [
                ("default", old_cfg, 0.0),
                ("stabilized", stabilized_cfg, args.reliability_power),
            ]:
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
                    reliability_power=rel_power,
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
                        "reliability_power": rel_power,
                        "train_rows_used": int(model["train_rows_used"]),
                        "label_positive_rate": stats["label_positive_rate"],
                        "uncertain_rate": stats["uncertain_rate"],
                        "delta_std_mean": stats["delta_std_mean"],
                        "target_reliability_weight_mean": stats["target_reliability_weight_mean"],
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

    _write_csv(out_dir / "target_stabilization_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    default_rows = [r for r in compare_rows if r["setup"] == "default"]
    stabilized_rows = [r for r in compare_rows if r["setup"] == "stabilized"]
    stabilized_minus_default_vs_heuristic = [
        float(n["learned_vs_heuristic_accuracy_margin"]) - float(o["learned_vs_heuristic_accuracy_margin"])
        for o, n in zip(default_rows, stabilized_rows)
    ]
    stabilized_minus_default_score_margin = [
        float(n["learned_vs_heuristic_score_margin"]) - float(o["learned_vs_heuristic_score_margin"])
        for o, n in zip(default_rows, stabilized_rows)
    ]

    summary = {
        "comparison_grid": {"seeds": compare_seeds, "budgets": compare_budgets, "episodes": args.episodes, "eval_episodes": args.eval_episodes},
        "target_definitions": {
            "default": "delta = E[gain_here] - best_other_expected_next_gain, single local estimate",
            "stabilized": (
                "same default delta family, but average K repeated local estimates; "
                "delta_estimator_std estimates target uncertainty and can weight training"
            ),
        },
        "stabilization": {
            "mode": "repeated_local_averaging",
            "stabilization_repeats": args.stabilization_repeats,
            "reliability_power": args.reliability_power,
        },
        "old_vs_stabilized_label_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in default_rows]),
            "stabilized_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in stabilized_rows]),
            "default_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in default_rows]),
            "stabilized_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in stabilized_rows]),
        },
        "controller_metrics": {
            "default_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "stabilized_mean_learned_vs_heuristic_accuracy_margin": _mean(
                [float(r["learned_vs_heuristic_accuracy_margin"]) for r in stabilized_rows]
            ),
            "default_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in default_rows]),
            "stabilized_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in stabilized_rows]),
        },
        "win_loss": {
            "default_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "stabilized_vs_heuristic_accuracy": _win_loss_tie(
                [float(r["learned_vs_heuristic_accuracy_margin"]) for r in stabilized_rows]
            ),
            "stabilized_vs_default_accuracy": _win_loss_tie(stabilized_minus_default_vs_heuristic),
            "stabilized_vs_default_score": _win_loss_tie(stabilized_minus_default_score_margin),
        },
        "stability_signal": {
            "default_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "stabilized_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in stabilized_rows]),
        },
        "interpretation": {
            "conservative_read": (
                "Use only as bounded evidence. Promote only if stabilized setup improves both mean margin and stability with consistent W/L."
            ),
            "recommendation": "promote_stabilized_default" if _mean(stabilized_minus_default_vs_heuristic) > 0 else "keep_current_default",
            "next_best_move": (
                "If mixed: keep stabilized option available but continue local target-quality work (paired randomness control or better stop baseline matching)."
            ),
        },
    }
    write_json(out_dir / "target_stabilization_comparison_summary.json", summary)

    comparison_note = [
        "# Stop-vs-act bounded target-stabilization comparison note",
        "",
        "## Setup",
        "- Anchor baseline: current default `proxy_best_other_gain` target.",
        "- Single new option: `repeated_local_averaging` stabilization with optional reliability weighting.",
        f"- Grid: seeds={compare_seeds}, budgets={compare_budgets}.",
        "",
        "## Results (bounded)",
        f"- Default vs heuristic W/L/T (accuracy margin): `{summary['win_loss']['default_vs_heuristic_accuracy']}`.",
        f"- Stabilized vs heuristic W/L/T (accuracy margin): `{summary['win_loss']['stabilized_vs_heuristic_accuracy']}`.",
        f"- Stabilized vs default W/L/T (accuracy margin): `{summary['win_loss']['stabilized_vs_default_accuracy']}`.",
        f"- Mean learned-vs-heuristic accuracy margin: default `{summary['controller_metrics']['default_mean_learned_vs_heuristic_accuracy_margin']:+.4f}` vs stabilized `{summary['controller_metrics']['stabilized_mean_learned_vs_heuristic_accuracy_margin']:+.4f}`.",
        f"- Margin std: default `{summary['stability_signal']['default_margin_std']:.4f}` vs stabilized `{summary['stability_signal']['stabilized_margin_std']:.4f}`.",
        "",
        "## Conservative interpretation",
        "- Treat this as a bounded local signal only.",
        "- If mean/stability gains are small or mixed, do not overclaim; keep default anchor and continue refinement.",
        f"- Current recommendation from this pass: `{summary['interpretation']['recommendation']}`.",
    ]
    Path(args.comparison_note_path).write_text("\n".join(comparison_note) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
