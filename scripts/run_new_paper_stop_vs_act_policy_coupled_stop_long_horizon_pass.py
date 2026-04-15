#!/usr/bin/env python3
"""Bounded longer-horizon policy-coupled STOP baseline pass for stop-vs-act."""

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
    p = argparse.ArgumentParser(description="Bounded longer-horizon policy-coupled STOP pass")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_policy_coupled_stop_long_horizon")
    p.add_argument("--diagnosis-seeds", default="41,42")
    p.add_argument("--diagnosis-budgets", default="10,14")
    p.add_argument("--compare-seeds", default="41,42")
    p.add_argument("--compare-budgets", default="10,14")
    p.add_argument("--episodes", type=int, default=520)
    p.add_argument("--eval-episodes", type=int, default=220)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--n-init-branches", type=int, default=5)
    p.add_argument("--max-depth", type=int, default=7)
    p.add_argument("--finish-prob-base", type=float, default=0.16)
    p.add_argument("--answer-noise", type=float, default=0.12)
    p.add_argument("--gain-margin", type=float, default=0.015)
    p.add_argument("--uncertainty-band", type=float, default=0.03)
    p.add_argument("--instability-std-threshold", type=float, default=0.045)
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--small-horizon-steps", type=int, default=3)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--uncertainty-policy", default="downweight_nonpositive")
    p.add_argument("--include-one-step-context", action="store_true")
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_policy_coupled_stop_long_horizon_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_policy_coupled_stop_long_horizon_comparison_note.md")
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
        "delta_std_mean": _mean([float(r.get("delta_std", 0.0)) for r in rows]),
        "delta_sign_flip_rate_mean": _mean([float(r.get("delta_sign_flip_rate", 0.0)) for r in rows]),
        "stop_reference_gain_mean": _mean([float(r.get("stop_reference_gain", 0.0)) for r in rows]),
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
    )
    one_step_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_policy_coupled_stop_reallocation",
    )
    long_horizon_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_policy_coupled_stop_reallocation_horizon",
        small_horizon_steps=args.small_horizon_steps,
    )

    compare_setups: list[tuple[str, StopVsActLabelConfig]] = [("default", default_cfg), ("long_horizon_policy_coupled_stop", long_horizon_cfg)]
    if args.include_one_step_context:
        compare_setups.append(("one_step_policy_coupled_stop", one_step_cfg))

    diag_rows: list[dict[str, Any]] = []
    for budget in diagnosis_budgets:
        for seed in diagnosis_seeds:
            for setup_name, cfg in compare_setups:
                rows = _build_dataset(
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
                diag_rows.append({"seed": seed, "budget": budget, "setup": setup_name, **_dataset_stats(rows)})

    _write_csv(out_dir / "long_horizon_policy_coupled_stop_label_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    by_setup = {name: [r for r in diag_rows if r["setup"] == name] for name, _ in compare_setups}
    diagnosis_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "diagnosis": {
            "why_one_step_likely_failed": (
                "One-step policy-coupled STOP changes only the immediate action destination; it can miss opportunity-cost effects that appear after allocator adaptation over additional steps."
            ),
            "most_plausible_bottleneck": (
                "STOP baseline remains too myopic: preserved compute is represented at t+1 but not through a short downstream reuse horizon under the same policy context."
            ),
            "why_longer_horizon_is_next": (
                "A small bounded horizon (h=2 or h=3) is the minimal extension that keeps simulation lightweight while better matching natural reallocation dynamics."
            ),
            "target_definition": (
                f"ACT: force current-branch action at step 1 then continue same policy for h={max(2, args.small_horizon_steps)}; "
                "STOP: skip current branch at step 1, preserve compute, and let same policy reuse it over the same horizon with paired per-sample RNG."
            ),
        },
        "label_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in by_setup["default"]]),
            "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in by_setup["default"]]),
            "long_horizon_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in by_setup["long_horizon_policy_coupled_stop"]]),
            "long_horizon_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in by_setup["long_horizon_policy_coupled_stop"]]),
        },
    }
    if "one_step_policy_coupled_stop" in by_setup:
        diagnosis_summary["label_stats"]["one_step_delta_std_mean"] = _mean([float(r["delta_std_mean"]) for r in by_setup["one_step_policy_coupled_stop"]])
        diagnosis_summary["label_stats"]["one_step_sign_flip_rate_mean"] = _mean([float(r["delta_sign_flip_rate_mean"]) for r in by_setup["one_step_policy_coupled_stop"]])

    write_json(out_dir / "long_horizon_policy_coupled_stop_diagnosis_summary.json", diagnosis_summary)

    diagnosis_note = [
        "# Stop-vs-act slightly longer-horizon policy-coupled STOP diagnosis note",
        "",
        "## 1) Why one-step policy-coupled STOP likely failed to improve outcomes",
        "- One-step coupling improved immediate comparator realism but stayed shallow: it did not capture allocator adaptation over subsequent steps.",
        "",
        "## 2) Most plausible STOP-baseline bottleneck",
        "- STOP meaning is still too local; preserved compute is represented mostly as immediate diversion, not bounded downstream reuse under the same policy context.",
        "",
        "## 3) Why slightly longer-horizon reallocation-aware STOP is next",
        f"- Minimal bounded extension to h={max(2, args.small_horizon_steps)} keeps the pass lightweight while making opportunity cost more faithful.",
        "",
        "## 4) Exact target definition used",
        f"- ACT path: force one action on current branch now, then run same policy for h={max(2, args.small_horizon_steps)} steps.",
        f"- STOP path: skip current branch now, preserve that action, then run same policy for h={max(2, args.small_horizon_steps)} steps so compute is naturally reallocated.",
        "- ACT and STOP use paired per-sample RNG seeds and the same active snapshot.",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note) + "\n", encoding="utf-8")

    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
            for setup_name, cfg in compare_setups:
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
                        "horizon_steps": cfg.small_horizon_steps,
                        "train_rows_used": int(model["train_rows_used"]),
                        "label_positive_rate": stats["label_positive_rate"],
                        "uncertain_rate": stats["uncertain_rate"],
                        "delta_std_mean": stats["delta_std_mean"],
                        "delta_sign_flip_rate_mean": stats["delta_sign_flip_rate_mean"],
                        "stop_reference_gain_mean": stats["stop_reference_gain_mean"],
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

    _write_csv(out_dir / "long_horizon_policy_coupled_stop_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    rows_default = [r for r in compare_rows if r["setup"] == "default"]
    rows_long = [r for r in compare_rows if r["setup"] == "long_horizon_policy_coupled_stop"]

    long_minus_default_acc = [
        float(n["learned_vs_heuristic_accuracy_margin"]) - float(o["learned_vs_heuristic_accuracy_margin"]) for o, n in zip(rows_default, rows_long)
    ]
    long_minus_default_score = [
        float(n["learned_vs_heuristic_score_margin"]) - float(o["learned_vs_heuristic_score_margin"]) for o, n in zip(rows_default, rows_long)
    ]

    summary: dict[str, Any] = {
        "comparison_grid": {
            "seeds": compare_seeds,
            "budgets": compare_budgets,
            "episodes": args.episodes,
            "eval_episodes": args.eval_episodes,
        },
        "stop_baseline_definitions": {
            "default": "proxy_best_other_gain: subtract static best-other expected next gain",
            "long_horizon_policy_coupled_stop": (
                f"proxy_policy_coupled_stop_reallocation_horizon: ACT acts here now, STOP skips here now, then both continue same policy for h={max(2, args.small_horizon_steps)} with paired RNG"
            ),
        },
        "label_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in rows_default]),
            "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in rows_default]),
            "long_horizon_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in rows_long]),
            "long_horizon_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in rows_long]),
        },
        "controller_metrics": {
            "default_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_default]),
            "long_horizon_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_long]),
            "default_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in rows_default]),
            "long_horizon_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in rows_long]),
        },
        "win_loss": {
            "default_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_default]),
            "long_horizon_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_long]),
            "long_horizon_vs_default_accuracy": _win_loss_tie(long_minus_default_acc),
            "long_horizon_vs_default_score": _win_loss_tie(long_minus_default_score),
        },
        "stability_signal": {
            "default_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_default]),
            "long_horizon_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_long]),
        },
    }

    if args.include_one_step_context:
        rows_one_step = [r for r in compare_rows if r["setup"] == "one_step_policy_coupled_stop"]
        summary["stop_baseline_definitions"]["one_step_policy_coupled_stop"] = (
            "proxy_policy_coupled_stop_reallocation: ACT acts here now, STOP skips here now for one step only"
        )
        summary["label_stats"]["one_step_delta_std_mean"] = _mean([float(r["delta_std_mean"]) for r in rows_one_step])
        summary["label_stats"]["one_step_sign_flip_rate_mean"] = _mean([float(r["delta_sign_flip_rate_mean"]) for r in rows_one_step])
        summary["controller_metrics"]["one_step_mean_learned_vs_heuristic_accuracy_margin"] = _mean(
            [float(r["learned_vs_heuristic_accuracy_margin"]) for r in rows_one_step]
        )

    mean_long_minus_default_acc = _mean(long_minus_default_acc)
    summary["interpretation"] = {
        "conservative_read": "Small matched evidence only; effect may be noisy and should not be overclaimed.",
        "did_it_help": "yes" if mean_long_minus_default_acc > 0.0 else "no_or_mixed",
        "recommendation": "replace_default" if mean_long_minus_default_acc > 0.01 else "keep_current_default",
        "next_best_move": (
            "If outcomes remain mixed, keep this mode optional and test a budget-aware horizon gate (e.g., h=2 for tight budgets, h=3 otherwise) without changing controller family."
        ),
    }

    write_json(out_dir / "long_horizon_policy_coupled_stop_comparison_summary.json", summary)

    comparison_note = [
        "# Stop-vs-act bounded slightly longer-horizon policy-coupled STOP comparison note",
        "",
        "## Setup",
        "- Anchor baseline: current default `proxy_best_other_gain`.",
        f"- New mode: `proxy_policy_coupled_stop_reallocation_horizon` with h={max(2, args.small_horizon_steps)}.",
        f"- Grid: seeds={compare_seeds}, budgets={compare_budgets}.",
        "",
        "## Results (bounded)",
        f"- Default vs heuristic W/L/T (accuracy): `{summary['win_loss']['default_vs_heuristic_accuracy']}`.",
        f"- Long-horizon vs heuristic W/L/T (accuracy): `{summary['win_loss']['long_horizon_vs_heuristic_accuracy']}`.",
        f"- Long-horizon vs default W/L/T (accuracy): `{summary['win_loss']['long_horizon_vs_default_accuracy']}`.",
        f"- Mean learned-vs-heuristic accuracy margin: default `{summary['controller_metrics']['default_mean_learned_vs_heuristic_accuracy_margin']:+.4f}` vs long-horizon `{summary['controller_metrics']['long_horizon_mean_learned_vs_heuristic_accuracy_margin']:+.4f}`.",
        f"- Mean label sign-flip-rate: default `{summary['label_stats']['default_sign_flip_rate_mean']:.4f}` vs long-horizon `{summary['label_stats']['long_horizon_sign_flip_rate_mean']:.4f}`.",
    ]
    if args.include_one_step_context:
        comparison_note.append(
            f"- Context only: one-step policy-coupled mean learned-vs-heuristic accuracy margin `{summary['controller_metrics']['one_step_mean_learned_vs_heuristic_accuracy_margin']:+.4f}`."
        )

    comparison_note.extend(
        [
            "",
            "## Conservative interpretation",
            "- Slight gains are not enough to replace default unless they are robust.",
            f"- Current recommendation: `{summary['interpretation']['recommendation']}`.",
        ]
    )
    Path(args.comparison_note_path).write_text("\n".join(comparison_note) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
