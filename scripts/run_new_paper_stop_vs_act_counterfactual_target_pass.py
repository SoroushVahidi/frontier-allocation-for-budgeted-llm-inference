#!/usr/bin/env python3
"""Bounded counterfactual local-target revision pass for stop-vs-act."""

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
        "delta_mean_mean": _mean([float(r["delta_mean"]) for r in rows]),
        "delta_std_mean": _mean([float(r["delta_std"]) for r in rows]),
        "delta_positive_share": _mean([1.0 if float(r["delta_mean"]) > 0.0 else 0.0 for r in rows]),
    }


def _pairwise_target_diff(old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> dict[str, float]:
    old_map = {
        (int(r["episode_id"]), int(r["decision_id"]), str(r["branch_id"])): r
        for r in old_rows
    }
    changed = 0
    old_act_new_stop = 0
    old_stop_new_act = 0
    delta_shift: list[float] = []
    overlap = 0
    for r in new_rows:
        key = (int(r["episode_id"]), int(r["decision_id"]), str(r["branch_id"]))
        old = old_map.get(key)
        if old is None:
            continue
        overlap += 1
        old_label = int(old["label_act"])
        new_label = int(r["label_act"])
        if old_label != new_label:
            changed += 1
            if old_label == 1 and new_label == 0:
                old_act_new_stop += 1
            if old_label == 0 and new_label == 1:
                old_stop_new_act += 1
        delta_shift.append(float(r["delta_mean"]) - float(old["delta_mean"]))
    return {
        "overlap_rows": float(overlap),
        "label_change_rate": float(changed / max(1, overlap)),
        "old_act_new_stop_rate": float(old_act_new_stop / max(1, overlap)),
        "old_stop_new_act_rate": float(old_stop_new_act / max(1, overlap)),
        "delta_shift_mean": _mean(delta_shift),
        "delta_shift_std": _std(delta_shift),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded counterfactual local-target revision pass")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_counterfactual_target")
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
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--uncertainty-policy", default="downweight_nonpositive")
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_counterfactual_target_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_counterfactual_target_comparison_note.md")
    return p.parse_args()


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
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
        target_mode="proxy_best_other_gain",
    )
    revised_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
        target_mode="counterfactual_here_vs_best_other",
    )

    # Phase 1: diagnosis of target weakness.
    diag_rows: list[dict[str, Any]] = []
    diag_pairwise_rows: list[dict[str, Any]] = []
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
                cfg=revised_cfg,
            )
            diag_rows.append({"seed": seed, "budget": budget, "target": "old_proxy", **_dataset_stats(rows_old)})
            diag_rows.append({"seed": seed, "budget": budget, "target": "revised_counterfactual", **_dataset_stats(rows_new)})
            diag_pairwise_rows.append({"seed": seed, "budget": budget, **_pairwise_target_diff(rows_old, rows_new)})

    _write_csv(out_dir / "target_label_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))
    _write_csv(out_dir / "target_pairwise_shift_stats.csv", diag_pairwise_rows, fieldnames=list(diag_pairwise_rows[0].keys()))

    old_diag = [r for r in diag_rows if r["target"] == "old_proxy"]
    new_diag = [r for r in diag_rows if r["target"] == "revised_counterfactual"]
    diagnosis_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "old_target": {
            "name": "proxy_best_other_gain",
            "definition": "delta = E[gain_after_act_here] - best_other_expected_next_gain",
        },
        "revised_target": {
            "name": "counterfactual_here_vs_best_other",
            "definition": "delta = E[gain_after_act_here - gain_after_one_step_best_other]",
        },
        "old_stats": {
            "mean_label_positive_rate": _mean([float(r["label_positive_rate"]) for r in old_diag]),
            "mean_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in old_diag]),
            "mean_delta_mean": _mean([float(r["delta_mean_mean"]) for r in old_diag]),
        },
        "revised_stats": {
            "mean_label_positive_rate": _mean([float(r["label_positive_rate"]) for r in new_diag]),
            "mean_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in new_diag]),
            "mean_delta_mean": _mean([float(r["delta_mean_mean"]) for r in new_diag]),
        },
        "pairwise_shift": {
            "mean_label_change_rate": _mean([float(r["label_change_rate"]) for r in diag_pairwise_rows]),
            "mean_old_act_new_stop_rate": _mean([float(r["old_act_new_stop_rate"]) for r in diag_pairwise_rows]),
            "mean_old_stop_new_act_rate": _mean([float(r["old_stop_new_act_rate"]) for r in diag_pairwise_rows]),
            "mean_delta_shift": _mean([float(r["delta_shift_mean"]) for r in diag_pairwise_rows]),
        },
        "diagnosis": {
            "weakness": "alternative-branch proxy mismatch: old target subtracts a static expected gain proxy for elsewhere compute instead of simulating the same one-step compute action on the best alternative branch.",
            "main_issue_class": "alternative-branch proxy mismatch (with some redundancy blindness), not primarily threshold-only tuning.",
            "single_revision": "replace the stop baseline term with an explicit one-step local counterfactual: ACT-here one-step gain minus best-alternative one-step gain from the same local state snapshot.",
        },
    }
    write_json(out_dir / "diagnosis_summary.json", diagnosis_summary)

    diagnosis_note = [
        "# Stop-vs-act local-target diagnosis note (counterfactual revision pass)",
        "",
        "## 1) Most likely weak aspect of the current local proxy",
        "- The current target uses `best_other_expected_next_gain` as a fixed subtraction term while the ACT side is sampled through local rollout.",
        "- This asymmetry likely misaligns labels when the best alternative branch's realized one-step gain differs from its expectation.",
        "",
        "## 2) Main issue class",
        "- Primary: **alternative-branch proxy mismatch** (and related redundancy blindness), not just threshold or uncertainty-band tuning.",
        f"- Pairwise old→new label change rate across diagnosis grid: `{diagnosis_summary['pairwise_shift']['mean_label_change_rate']:.4f}`.",
        f"- Mean old ACT→new STOP rate: `{diagnosis_summary['pairwise_shift']['mean_old_act_new_stop_rate']:.4f}`; old STOP→new ACT: `{diagnosis_summary['pairwise_shift']['mean_old_stop_new_act_rate']:.4f}`.",
        "",
        "## 3) One lightweight counterfactual target revision",
        "- **Revised target**: `delta = E[gain_after_one_step_here - gain_after_one_step_best_other]`.",
        "- This keeps the same one-step bounded simulation budget and infrastructure, but explicitly compares compute-here vs compute-elsewhere under matched local rollouts.",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note) + "\n", encoding="utf-8")

    # Phase 2+3: bounded matched controller comparison.
    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
            for setup_name, cfg in [("old_proxy_target", old_cfg), ("revised_counterfactual_target", revised_cfg)]:
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
                learned_row = next(r for r in cmp.comparison_rows if r["policy"] == "learned_stop_vs_act")
                heuristic_row = next(r for r in cmp.comparison_rows if r["policy"] == "heuristic_gain_gap")
                compare_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "setup": setup_name,
                        "target_mode": cfg.target_mode,
                        "label_positive_rate": _mean([float(r["label_act"]) for r in ds_rows]),
                        "uncertain_rate": _mean([float(r["is_uncertain"]) for r in ds_rows]),
                        "test_roc_auc": float(cls["roc_auc"]),
                        "test_brier": float(cls["brier"]),
                        "learned_accuracy": float(learned_row["accuracy"]),
                        "heuristic_accuracy": float(heuristic_row["accuracy"]),
                        "learned_vs_heuristic_margin": float(cmp.metrics["learned_vs_heuristic_accuracy_margin"]),
                        "learned_avg_primary_actions": float(learned_row["avg_primary_actions"]),
                        "learned_avg_routed_elsewhere": float(learned_row["avg_routed_elsewhere"]),
                    }
                )

    _write_csv(out_dir / "counterfactual_target_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    old_rows = [r for r in compare_rows if r["setup"] == "old_proxy_target"]
    new_rows = [r for r in compare_rows if r["setup"] == "revised_counterfactual_target"]
    old_by_cell = {(int(r["seed"]), int(r["budget"])): r for r in old_rows}
    new_by_cell = {(int(r["seed"]), int(r["budget"])): r for r in new_rows}
    matched_cells = sorted(set(old_by_cell.keys()) & set(new_by_cell.keys()))

    revised_minus_old_vs_heuristic = [
        float(new_by_cell[c]["learned_vs_heuristic_margin"]) - float(old_by_cell[c]["learned_vs_heuristic_margin"]) for c in matched_cells
    ]
    revised_minus_old_primary_actions = [
        float(new_by_cell[c]["learned_avg_primary_actions"]) - float(old_by_cell[c]["learned_avg_primary_actions"]) for c in matched_cells
    ]

    summary = {
        "comparison_grid": {"seeds": compare_seeds, "budgets": compare_budgets, "episodes": args.episodes, "eval_episodes": args.eval_episodes},
        "old_vs_heuristic": _win_loss_tie([float(r["learned_vs_heuristic_margin"]) for r in old_rows]),
        "revised_vs_heuristic": _win_loss_tie([float(r["learned_vs_heuristic_margin"]) for r in new_rows]),
        "revised_minus_old_vs_heuristic": {
            "mean": _mean(revised_minus_old_vs_heuristic),
            "std": _std(revised_minus_old_vs_heuristic),
            "win_loss_tie": _win_loss_tie(revised_minus_old_vs_heuristic),
        },
        "act_usefulness_signal": {
            "old_mean_primary_actions": _mean([float(r["learned_avg_primary_actions"]) for r in old_rows]),
            "revised_mean_primary_actions": _mean([float(r["learned_avg_primary_actions"]) for r in new_rows]),
            "revised_minus_old_primary_actions_mean": _mean(revised_minus_old_primary_actions),
            "revised_minus_old_primary_actions_std": _std(revised_minus_old_primary_actions),
        },
        "recommendation": "replace_old_target" if _mean(revised_minus_old_vs_heuristic) > 0.0 else "do_not_replace_yet",
        "conservative_interpretation": (
            "Small matched-grid evidence only. Treat positive mean as directional; if mixed or near-zero, retain old target and continue deeper target-quality work."
        ),
    }
    write_json(out_dir / "counterfactual_target_comparison_summary.json", summary)

    comparison_note = [
        "# Stop-vs-act bounded counterfactual-target comparison note",
        "",
        "## What changed",
        "- Single target revision: switch from `proxy_best_other_gain` to `counterfactual_here_vs_best_other`.",
        "- Old: `E[gain_here] - best_other_expected_next_gain`.",
        "- Revised: `E[gain_here - gain_best_other_one_step]` via bounded local rollouts.",
        "",
        "## Matched comparison setup",
        f"- Seeds: `{args.compare_seeds}`",
        f"- Budgets: `{args.compare_budgets}`",
        f"- Episodes per cell: `{args.episodes}`; eval episodes: `{args.eval_episodes}`",
        f"- Uncertainty policy fixed: `{args.uncertainty_policy}`",
        "",
        "## Results",
        f"- Old target vs heuristic W/L/T: `{summary['old_vs_heuristic']}`.",
        f"- Revised target vs heuristic W/L/T: `{summary['revised_vs_heuristic']}`.",
        f"- Revised-minus-old margin vs heuristic: mean `{summary['revised_minus_old_vs_heuristic']['mean']:.4f}`, std `{summary['revised_minus_old_vs_heuristic']['std']:.4f}`, W/L/T `{summary['revised_minus_old_vs_heuristic']['win_loss_tie']}`.",
        f"- Learned ACT usage (primary actions): old `{summary['act_usefulness_signal']['old_mean_primary_actions']:.3f}` vs revised `{summary['act_usefulness_signal']['revised_mean_primary_actions']:.3f}`.",
        "",
        "## Conservative recommendation",
        f"- `{summary['recommendation']}`.",
        "- Do not overclaim from this bounded pass; use as a target-quality signal only.",
    ]
    Path(args.comparison_note_path).write_text("\n".join(comparison_note) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
