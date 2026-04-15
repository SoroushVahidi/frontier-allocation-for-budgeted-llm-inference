#!/usr/bin/env python3
"""Bounded policy-coupled STOP-baseline pass for stop-vs-act target."""

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
    p = argparse.ArgumentParser(description="Bounded policy-coupled STOP-baseline pass")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_policy_coupled_stop")
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
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--uncertainty-policy", default="downweight_nonpositive")
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_policy_coupled_stop_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_policy_coupled_stop_comparison_note.md")
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
    policy_coupled_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_policy_coupled_stop_reallocation",
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
                cfg=policy_coupled_cfg,
            )
            diag_rows.append({"seed": seed, "budget": budget, "setup": "default", **_dataset_stats(rows_old)})
            diag_rows.append({"seed": seed, "budget": budget, "setup": "policy_coupled_stop", **_dataset_stats(rows_new)})

    _write_csv(out_dir / "policy_coupled_stop_label_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    old_diag = [r for r in diag_rows if r["setup"] == "default"]
    new_diag = [r for r in diag_rows if r["setup"] == "policy_coupled_stop"]

    diagnosis_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "why_matched_rng_was_not_enough": (
            "Matched randomness reduces nuisance variance, but if STOP is still a weak proxy for natural reallocation, labels remain misaligned."
        ),
        "most_plausible_bottleneck": {
            "primary": "STOP baseline semantic mismatch: default subtracts best-other expected gain instead of simulating what policy would spend saved compute on.",
            "evidence": {
                "default_stop_reference_gain_mean": _mean([float(r["stop_reference_gain_mean"]) for r in old_diag]),
                "default_delta_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in old_diag]),
            },
        },
        "single_strategy": {
            "name": "proxy_policy_coupled_stop_reallocation",
            "definition": (
                "One-step ACT-vs-STOP comparator where ACT forces current-branch action now, while STOP forbids current branch at step 1 and lets the same downstream policy naturally reallocate that action elsewhere."
            ),
            "coupling_details": [
                "same initial active branch pool",
                "same one-step budget context",
                "same policy family for choosing alternative under STOP",
                "paired per-sample RNG seed between ACT and STOP one-step futures",
            ],
        },
        "old_vs_new_label_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in old_diag]),
            "policy_coupled_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in new_diag]),
            "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in old_diag]),
            "policy_coupled_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in new_diag]),
        },
    }
    write_json(out_dir / "policy_coupled_stop_diagnosis_summary.json", diagnosis_summary)

    diagnosis_note = [
        "# Stop-vs-act policy-coupled STOP baseline diagnosis note",
        "",
        "## 1) Why matched randomness likely did not improve controller outcomes",
        "- It addressed nuisance rollout noise, but not the semantic mismatch of STOP baseline itself.",
        "",
        "## 2) Most plausible STOP-baseline mismatch now",
        "- Default STOP reference is still a proxy subtraction, not an explicit policy-coupled reallocation of saved compute under same context.",
        f"- Default mean STOP reference gain: `{diagnosis_summary['most_plausible_bottleneck']['evidence']['default_stop_reference_gain_mean']:.4f}`.",
        f"- Default mean delta sign-flip rate: `{diagnosis_summary['most_plausible_bottleneck']['evidence']['default_delta_sign_flip_rate_mean']:.4f}`.",
        "",
        "## 3) Single lightweight strategy",
        "- One-step policy-coupled STOP reallocation comparator (`proxy_policy_coupled_stop_reallocation`).",
        "- ACT: act on current branch now. STOP: forbid current branch for first step and let same policy consume saved compute elsewhere.",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note) + "\n", encoding="utf-8")

    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
            for setup_name, cfg in [("default", default_cfg), ("policy_coupled_stop", policy_coupled_cfg)]:
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

    _write_csv(out_dir / "policy_coupled_stop_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    default_rows = [r for r in compare_rows if r["setup"] == "default"]
    new_rows = [r for r in compare_rows if r["setup"] == "policy_coupled_stop"]
    new_minus_old_acc = [
        float(n["learned_vs_heuristic_accuracy_margin"]) - float(o["learned_vs_heuristic_accuracy_margin"]) for o, n in zip(default_rows, new_rows)
    ]
    new_minus_old_score = [
        float(n["learned_vs_heuristic_score_margin"]) - float(o["learned_vs_heuristic_score_margin"]) for o, n in zip(default_rows, new_rows)
    ]

    summary = {
        "comparison_grid": {"seeds": compare_seeds, "budgets": compare_budgets, "episodes": args.episodes, "eval_episodes": args.eval_episodes},
        "stop_baseline_definitions": {
            "default": "proxy_best_other_gain: subtract static best-other expected next gain",
            "policy_coupled_stop": (
                "proxy_policy_coupled_stop_reallocation: STOP forbids current branch at step 1 and reallocates saved action via same policy"
            ),
        },
        "label_stats": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in default_rows]),
            "policy_coupled_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in new_rows]),
            "default_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in default_rows]),
            "policy_coupled_sign_flip_rate_mean": _mean([float(r["delta_sign_flip_rate_mean"]) for r in new_rows]),
            "default_stop_reference_gain_mean": _mean([float(r["stop_reference_gain_mean"]) for r in default_rows]),
            "policy_coupled_stop_reference_gain_mean": _mean([float(r["stop_reference_gain_mean"]) for r in new_rows]),
        },
        "controller_metrics": {
            "default_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "policy_coupled_mean_learned_vs_heuristic_accuracy_margin": _mean([float(r["learned_vs_heuristic_accuracy_margin"]) for r in new_rows]),
            "default_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in default_rows]),
            "policy_coupled_mean_learned_vs_heuristic_score_margin": _mean([float(r["learned_vs_heuristic_score_margin"]) for r in new_rows]),
        },
        "win_loss": {
            "default_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "policy_coupled_vs_heuristic_accuracy": _win_loss_tie([float(r["learned_vs_heuristic_accuracy_margin"]) for r in new_rows]),
            "policy_coupled_vs_default_accuracy": _win_loss_tie(new_minus_old_acc),
            "policy_coupled_vs_default_score": _win_loss_tie(new_minus_old_score),
        },
        "stability_signal": {
            "default_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in default_rows]),
            "policy_coupled_margin_std": _std([float(r["learned_vs_heuristic_accuracy_margin"]) for r in new_rows]),
        },
        "interpretation": {
            "conservative_read": "Small matched evidence only; do not promote replacement unless robustly positive.",
            "recommendation": "replace_default" if _mean(new_minus_old_acc) > 0.0 else "keep_current_default",
            "next_best_move": (
                "If mixed: keep this optional mode and next test a slightly longer-horizon policy-coupled reallocation baseline while preserving same downstream policy."
            ),
        },
    }
    write_json(out_dir / "policy_coupled_stop_comparison_summary.json", summary)

    comparison_note = [
        "# Stop-vs-act bounded policy-coupled STOP baseline comparison note",
        "",
        "## Setup",
        "- Anchor baseline: current default `proxy_best_other_gain`.",
        "- New mode: `proxy_policy_coupled_stop_reallocation`.",
        f"- Grid: seeds={compare_seeds}, budgets={compare_budgets}.",
        "",
        "## Results (bounded)",
        f"- Default vs heuristic W/L/T (accuracy): `{summary['win_loss']['default_vs_heuristic_accuracy']}`.",
        f"- Policy-coupled vs heuristic W/L/T (accuracy): `{summary['win_loss']['policy_coupled_vs_heuristic_accuracy']}`.",
        f"- Policy-coupled vs default W/L/T (accuracy): `{summary['win_loss']['policy_coupled_vs_default_accuracy']}`.",
        f"- Mean learned-vs-heuristic accuracy margin: default `{summary['controller_metrics']['default_mean_learned_vs_heuristic_accuracy_margin']:+.4f}` vs policy-coupled `{summary['controller_metrics']['policy_coupled_mean_learned_vs_heuristic_accuracy_margin']:+.4f}`.",
        f"- Mean label sign-flip-rate: default `{summary['label_stats']['default_sign_flip_rate_mean']:.4f}` vs policy-coupled `{summary['label_stats']['policy_coupled_sign_flip_rate_mean']:.4f}`.",
        "",
        "## Conservative interpretation",
        "- If comparator alignment improves but controller outcomes do not, do not replace current default.",
        f"- Current recommendation: `{summary['interpretation']['recommendation']}`.",
    ]
    Path(args.comparison_note_path).write_text("\n".join(comparison_note) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
