#!/usr/bin/env python3
"""Bounded ACT-vs-STOP small-horizon target revision pass for stop-vs-act."""

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


def _build_dataset(seed: int, budget: int, episodes: int, args: argparse.Namespace, cfg: StopVsActLabelConfig) -> list[dict[str, Any]]:
    return build_stop_vs_act_dataset(
        episodes=episodes,
        budget=budget,
        seed=seed,
        train_ratio=args.train_ratio,
        n_init_branches=args.n_init_branches,
        max_depth=args.max_depth,
        finish_prob_base=args.finish_prob_base,
        answer_noise=args.answer_noise,
        label_cfg=cfg,
    )


def _dataset_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "rows": float(len(rows)),
        "label_positive_rate": _mean([float(r["label_act"]) for r in rows]),
        "uncertain_rate": _mean([float(r["is_uncertain"]) for r in rows]),
        "delta_mean_mean": _mean([float(r["delta_mean"]) for r in rows]),
        "delta_std_mean": _mean([float(r["delta_std"]) for r in rows]),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded ACT-vs-STOP small-horizon target pass")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_small_horizon_target")
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
    p.add_argument("--instability-guard-band", type=float, default=0.15)
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--small-horizon-steps", type=int, default=2)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--uncertainty-policy", default="downweight_nonpositive")
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_small_horizon_target_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_small_horizon_target_comparison_note.md")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_seeds = _parse_int_list(args.diagnosis_seeds)
    diagnosis_budgets = _parse_int_list(args.diagnosis_budgets)
    compare_seeds = _parse_int_list(args.compare_seeds)
    compare_budgets = _parse_int_list(args.compare_budgets)

    cfg_default = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_best_other_gain",
    )
    cfg_failed_best_other = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
        target_mode="counterfactual_here_vs_best_other",
    )
    cfg_small_horizon = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
        target_mode="counterfactual_act_vs_stop_h2",
        small_horizon_steps=args.small_horizon_steps,
    )

    # Phase 1: diagnosis
    diag_rows: list[dict[str, Any]] = []
    for budget in diagnosis_budgets:
        for seed in diagnosis_seeds:
            old_rows = _build_dataset(seed, budget, args.episodes, args, cfg_default)
            failed_rows = _build_dataset(seed, budget, args.episodes, args, cfg_failed_best_other)
            new_rows = _build_dataset(seed, budget, args.episodes, args, cfg_small_horizon)
            diag_rows.extend(
                [
                    {"seed": seed, "budget": budget, "setup": "default_proxy", **_dataset_stats(old_rows)},
                    {"seed": seed, "budget": budget, "setup": "failed_here_vs_best_other", **_dataset_stats(failed_rows)},
                    {"seed": seed, "budget": budget, "setup": "new_act_vs_stop_small_horizon", **_dataset_stats(new_rows)},
                ]
            )

    _write_csv(out_dir / "small_horizon_target_label_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    old_diag = [r for r in diag_rows if r["setup"] == "default_proxy"]
    failed_diag = [r for r in diag_rows if r["setup"] == "failed_here_vs_best_other"]
    new_diag = [r for r in diag_rows if r["setup"] == "new_act_vs_stop_small_horizon"]

    diagnosis_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "why_next_target": (
            "Default proxy is a one-step static subtraction and failed here-vs-best-other still depends on best-alternative matching; "
            "small-horizon ACT-vs-STOP directly compares whether acting here now improves short-horizon local trajectory value versus skipping here now."
        ),
        "target_definition": {
            "name": "counterfactual_act_vs_stop_h2",
            "small_horizon_steps": args.small_horizon_steps,
            "delta": "E[value_after_h_steps(force_first_action_on_current_branch) - value_after_h_steps(skip_current_branch_on_first_step)]",
            "value": "max snapshot utility across active branches at horizon end",
        },
        "label_stats": {
            "default_proxy": {
                "positive_rate": _mean([float(r["label_positive_rate"]) for r in old_diag]),
                "uncertain_rate": _mean([float(r["uncertain_rate"]) for r in old_diag]),
                "delta_std_mean": _mean([float(r["delta_std_mean"]) for r in old_diag]),
            },
            "failed_here_vs_best_other": {
                "positive_rate": _mean([float(r["label_positive_rate"]) for r in failed_diag]),
                "uncertain_rate": _mean([float(r["uncertain_rate"]) for r in failed_diag]),
                "delta_std_mean": _mean([float(r["delta_std_mean"]) for r in failed_diag]),
            },
            "new_act_vs_stop_small_horizon": {
                "positive_rate": _mean([float(r["label_positive_rate"]) for r in new_diag]),
                "uncertain_rate": _mean([float(r["uncertain_rate"]) for r in new_diag]),
                "delta_std_mean": _mean([float(r["delta_std_mean"]) for r in new_diag]),
            },
        },
    }
    write_json(out_dir / "small_horizon_target_diagnosis_summary.json", diagnosis_summary)

    diagnosis_note_lines = [
        "# Stop-vs-act small-horizon ACT-vs-STOP diagnosis note",
        "",
        "## 1) Why this is the best next target",
        "- Default target is still a one-step proxy subtraction, and the failed here-vs-best-other target still hinges on alternative-branch matching.",
        "- A small-horizon ACT-vs-STOP target is a cleaner local decision objective: does acting here now improve short-horizon trajectory value vs skipping here now?",
        "",
        "## 2) What issue it is intended to fix",
        "- Versus default proxy: reduce static stop-baseline mismatch by simulating both ACT and STOP trajectories.",
        "- Versus failed here-vs-best-other: avoid over-committing to best-other one-step matching and directly model ACT-vs-STOP under same context.",
        "",
        "## 3) Exact target used",
        f"- Mode: `counterfactual_act_vs_stop_h2` with `small_horizon_steps={args.small_horizon_steps}`.",
        "- `delta = E[value_h(force first action on current branch) - value_h(skip current branch on first step)]`.",
        "- Horizon-end value is max snapshot utility over active branches.",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note_lines) + "\n", encoding="utf-8")

    # Phase 3: matched comparison
    compare_rows: list[dict[str, Any]] = []
    setups = [
        ("default_proxy", cfg_default),
        ("failed_here_vs_best_other", cfg_failed_best_other),
        ("new_act_vs_stop_small_horizon", cfg_small_horizon),
    ]
    for budget in compare_budgets:
        for seed in compare_seeds:
            for setup_name, cfg in setups:
                ds_rows = _build_dataset(seed, budget, args.episodes, args, cfg)
                train_rows = [r for r in ds_rows if r["split"] == "train"]
                test_rows = [r for r in ds_rows if r["split"] == "test"]

                model = fit_stop_vs_act_model(train_rows, model_kind="logistic", uncertain_policy=args.uncertainty_policy, seed=seed)
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
                learned_row = next(r for r in cmp.comparison_rows if r["policy"] == "learned_stop_vs_act")
                compare_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "setup": setup_name,
                        "target_mode": cfg.target_mode,
                        "label_positive_rate": _mean([float(r["label_act"]) for r in ds_rows]),
                        "uncertain_rate": _mean([float(r["is_uncertain"]) for r in ds_rows]),
                        "delta_std_mean": _mean([float(r["delta_std"]) for r in ds_rows]),
                        "test_roc_auc": float(cls["roc_auc"]),
                        "learned_vs_heuristic_margin": float(cmp.metrics["learned_vs_heuristic_accuracy_margin"]),
                        "learned_avg_primary_actions": float(learned_row["avg_primary_actions"]),
                    }
                )

    _write_csv(out_dir / "small_horizon_target_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    rows_by_setup = {name: [r for r in compare_rows if r["setup"] == name] for name, _ in setups}
    cell_map = {
        name: {(int(r["seed"]), int(r["budget"])): r for r in rows}
        for name, rows in rows_by_setup.items()
    }
    cells = sorted(set(cell_map["default_proxy"].keys()) & set(cell_map["new_act_vs_stop_small_horizon"].keys()))

    new_minus_default = [
        float(cell_map["new_act_vs_stop_small_horizon"][c]["learned_vs_heuristic_margin"]) - float(cell_map["default_proxy"][c]["learned_vs_heuristic_margin"])
        for c in cells
    ]
    new_minus_failed = [
        float(cell_map["new_act_vs_stop_small_horizon"][c]["learned_vs_heuristic_margin"]) - float(cell_map["failed_here_vs_best_other"][c]["learned_vs_heuristic_margin"])
        for c in cells
    ]

    summary = {
        "comparison_grid": {"seeds": compare_seeds, "budgets": compare_budgets, "episodes": args.episodes, "eval_episodes": args.eval_episodes},
        "default_vs_heuristic": _win_loss_tie([float(r["learned_vs_heuristic_margin"]) for r in rows_by_setup["default_proxy"]]),
        "failed_here_vs_best_other_vs_heuristic": _win_loss_tie([float(r["learned_vs_heuristic_margin"]) for r in rows_by_setup["failed_here_vs_best_other"]]),
        "new_small_horizon_vs_heuristic": _win_loss_tie([float(r["learned_vs_heuristic_margin"]) for r in rows_by_setup["new_act_vs_stop_small_horizon"]]),
        "new_minus_default": {
            "mean": _mean(new_minus_default),
            "std": _std(new_minus_default),
            "win_loss_tie": _win_loss_tie(new_minus_default),
        },
        "new_minus_failed_here_vs_best_other": {
            "mean": _mean(new_minus_failed),
            "std": _std(new_minus_failed),
            "win_loss_tie": _win_loss_tie(new_minus_failed),
        },
        "instability_signal": {
            "default_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in rows_by_setup["default_proxy"]]),
            "new_delta_std_mean": _mean([float(r["delta_std_mean"]) for r in rows_by_setup["new_act_vs_stop_small_horizon"]]),
        },
        "recommendation": "replace_default" if _mean(new_minus_default) > 0.0 else "keep_default",
        "conservative_interpretation": "Small matched grid only; treat as directional evidence, not a final replacement claim.",
    }
    write_json(out_dir / "small_horizon_target_comparison_summary.json", summary)

    comparison_lines = [
        "# Stop-vs-act bounded small-horizon ACT-vs-STOP comparison note",
        "",
        "## What changed",
        "- New target mode: `counterfactual_act_vs_stop_h2` (small-horizon ACT-vs-STOP).",
        "- Compare horizon value after forcing ACT-here first vs skipping this branch first under the same local context.",
        "",
        "## Matched setup",
        f"- Seeds: `{args.compare_seeds}`; budgets: `{args.compare_budgets}`; episodes/cell: `{args.episodes}`; eval episodes: `{args.eval_episodes}`.",
        f"- Small horizon steps: `{args.small_horizon_steps}`.",
        "",
        "## Results",
        f"- Default vs heuristic W/L/T: `{summary['default_vs_heuristic']}`.",
        f"- Failed here-vs-best-other vs heuristic W/L/T: `{summary['failed_here_vs_best_other_vs_heuristic']}`.",
        f"- New small-horizon vs heuristic W/L/T: `{summary['new_small_horizon_vs_heuristic']}`.",
        f"- New minus default margin mean/std: `{summary['new_minus_default']['mean']:.4f}` / `{summary['new_minus_default']['std']:.4f}`, W/L/T `{summary['new_minus_default']['win_loss_tie']}`.",
        f"- New minus failed-here-vs-best-other margin mean/std: `{summary['new_minus_failed_here_vs_best_other']['mean']:.4f}` / `{summary['new_minus_failed_here_vs_best_other']['std']:.4f}`, W/L/T `{summary['new_minus_failed_here_vs_best_other']['win_loss_tie']}`.",
        "",
        "## Conservative recommendation",
        f"- `{summary['recommendation']}`.",
        "- Do not overclaim from this small pass.",
    ]
    Path(args.comparison_note_path).write_text("\n".join(comparison_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
