#!/usr/bin/env python3
"""Bounded label-construction refinement pass for stop-vs-act."""

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
    p = argparse.ArgumentParser(description="Bounded label-construction refinement pass")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_controller_label_refinement")
    p.add_argument("--diagnosis-seeds", default="31,32,33,34")
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
    p.add_argument("--diagnosis-note-path", default="experiments/stop_vs_act_controller_label_refinement_diagnosis_note.md")
    p.add_argument("--comparison-note-path", default="experiments/stop_vs_act_controller_label_refinement_comparison_note.md")
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


def _dataset_stats(rows: list[dict[str, Any]], guard_band: float) -> dict[str, float]:
    unstable = [r for r in rows if float(r["delta_std"]) >= 0.045]
    unstable_far = [r for r in unstable if abs(float(r["delta_mean"])) > guard_band]
    return {
        "rows": float(len(rows)),
        "label_positive_rate": _mean([float(r["label_act"]) for r in rows]),
        "uncertain_rate": _mean([float(r["is_uncertain"]) for r in rows]),
        "unstable_rate": _mean([1.0 if float(r["delta_std"]) >= 0.045 else 0.0 for r in rows]),
        "near_zero_rate": _mean([1.0 if abs(float(r["delta_mean"])) <= 0.03 else 0.0 for r in rows]),
        "uncertain_rate_act": _mean([float(r["is_uncertain"]) for r in rows if int(r["label_act"]) == 1]),
        "uncertain_rate_stop": _mean([float(r["is_uncertain"]) for r in rows if int(r["label_act"]) == 0]),
        "unstable_far_share": float(len(unstable_far) / max(1, len(unstable))),
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
        instability_guard_band=None,
        rollout_samples=args.rollout_samples,
    )
    revised_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
    )

    # Phase 1: deeper label-rule diagnosis.
    diag_rows: list[dict[str, Any]] = []
    for budget in diagnosis_budgets:
        for seed in diagnosis_seeds:
            old_rows = _build_dataset(
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
            s = _dataset_stats(old_rows, args.instability_guard_band)
            diag_rows.append({"seed": seed, "budget": budget, **s})

    _write_csv(out_dir / "label_rule_diagnosis_per_cell.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    diag_summary = {
        "diagnosis_grid": {"seeds": diagnosis_seeds, "budgets": diagnosis_budgets, "episodes": args.episodes},
        "old_label_rule": {
            "gain_margin": args.gain_margin,
            "uncertainty_band": args.uncertainty_band,
            "instability_std_threshold": args.instability_std_threshold,
            "instability_guard_band": None,
        },
        "proposed_refinement": {
            "instability_guard_band": args.instability_guard_band,
            "description": "Mark instability as uncertain only when |delta_mean| is within a bounded ambiguity band.",
        },
        "evidence": {
            "mean_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in diag_rows]),
            "mean_unstable_rate": _mean([float(r["unstable_rate"]) for r in diag_rows]),
            "mean_unstable_far_share": _mean([float(r["unstable_far_share"]) for r in diag_rows]),
            "mean_uncertain_rate_act": _mean([float(r["uncertain_rate_act"]) for r in diag_rows]),
            "mean_label_positive_rate": _mean([float(r["label_positive_rate"]) for r in diag_rows]),
        },
        "bottleneck": "Instability-only uncertainty criterion is over-broad; many unstable examples are far from near-zero delta and still flagged uncertain.",
    }
    write_json(out_dir / "label_rule_diagnosis_summary.json", diag_summary)

    diagnosis_note = [
        "# Stop-vs-act label-construction diagnosis note",
        "",
        "## 1) Most likely label bottleneck",
        "- Current uncertainty labeling treats any high rollout instability as uncertain, regardless of whether delta_mean is far from decision boundary.",
        "- This likely over-marks uncertain examples and weakens label usefulness for training.",
        "",
        "## 2) Evidence",
        f"- Mean uncertain rate (old rule): `{diag_summary['evidence']['mean_uncertain_rate']:.4f}`.",
        f"- Mean unstable rate: `{diag_summary['evidence']['mean_unstable_rate']:.4f}`.",
        f"- Mean share of unstable examples with |delta_mean| > {args.instability_guard_band:.3f}: `{diag_summary['evidence']['mean_unstable_far_share']:.4f}`.",
        f"- Mean uncertain rate among ACT labels: `{diag_summary['evidence']['mean_uncertain_rate_act']:.4f}`.",
        f"- Mean ACT label rate: `{diag_summary['evidence']['mean_label_positive_rate']:.4f}`.",
        "",
        "## 3) One refinement to try",
        f"- Add an instability guard band (`instability_guard_band={args.instability_guard_band:.3f}`): instability marks uncertainty only when `|delta_mean| <= guard_band`.",
        "- Keep all other label/model components fixed.",
    ]
    Path(args.diagnosis_note_path).write_text("\n".join(diagnosis_note) + "\n", encoding="utf-8")

    # Phase 2/3: matched old-vs-revised label comparison.
    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
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

            for label_version, ds_rows in [("old_label_rule", rows_old), ("revised_label_rule", rows_new)]:
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
                by_policy = {r["policy"]: r for r in cmp.comparison_rows}
                stats = _dataset_stats(ds_rows, args.instability_guard_band)
                compare_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "label_version": label_version,
                        "uncertainty_policy": args.uncertainty_policy,
                        "train_rows_used": int(model["train_rows_used"]),
                        "label_positive_rate": stats["label_positive_rate"],
                        "uncertain_rate": stats["uncertain_rate"],
                        "unstable_far_share": stats["unstable_far_share"],
                        "classification_accuracy": float(cls["accuracy"]),
                        "classification_auc": float(cls["roc_auc"]),
                        "learned_accuracy": float(by_policy["learned_stop_vs_act"]["accuracy"]),
                        "heuristic_accuracy": float(by_policy["heuristic_gain_gap"]["accuracy"]),
                        "learned_vs_heuristic_accuracy_margin": float(cmp.metrics["learned_vs_heuristic_accuracy_margin"]),
                        "learned_vs_uncertainty_accuracy_margin": float(cmp.metrics["learned_vs_uncertainty_accuracy_margin"]),
                    }
                )

    compare_rows = sorted(compare_rows, key=lambda r: (int(r["budget"]), int(r["seed"]), str(r["label_version"])))
    _write_csv(out_dir / "label_refinement_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    old_rows = [r for r in compare_rows if r["label_version"] == "old_label_rule"]
    new_rows = [r for r in compare_rows if r["label_version"] == "revised_label_rule"]

    paired_rows: list[dict[str, Any]] = []
    for o in old_rows:
        key = (int(o["seed"]), int(o["budget"]))
        n = next(r for r in new_rows if (int(r["seed"]), int(r["budget"])) == key)
        paired_rows.append(
            {
                "seed": key[0],
                "budget": key[1],
                "old_margin_vs_heuristic": float(o["learned_vs_heuristic_accuracy_margin"]),
                "new_margin_vs_heuristic": float(n["learned_vs_heuristic_accuracy_margin"]),
                "delta_margin_vs_heuristic": float(n["learned_vs_heuristic_accuracy_margin"]) - float(o["learned_vs_heuristic_accuracy_margin"]),
                "old_uncertain_rate": float(o["uncertain_rate"]),
                "new_uncertain_rate": float(n["uncertain_rate"]),
                "delta_uncertain_rate": float(n["uncertain_rate"]) - float(o["uncertain_rate"]),
                "old_label_positive_rate": float(o["label_positive_rate"]),
                "new_label_positive_rate": float(n["label_positive_rate"]),
                "delta_label_positive_rate": float(n["label_positive_rate"]) - float(o["label_positive_rate"]),
            }
        )

    _write_csv(out_dir / "label_refinement_comparison_paired.csv", paired_rows, fieldnames=list(paired_rows[0].keys()))

    old_m = [float(r["old_margin_vs_heuristic"]) for r in paired_rows]
    new_m = [float(r["new_margin_vs_heuristic"]) for r in paired_rows]
    delta_m = [float(r["delta_margin_vs_heuristic"]) for r in paired_rows]

    summary = {
        "grid": {"seeds": compare_seeds, "budgets": compare_budgets, "episodes": args.episodes, "eval_episodes": args.eval_episodes},
        "old_label_rule": {"instability_guard_band": None},
        "revised_label_rule": {"instability_guard_band": args.instability_guard_band},
        "old_vs_heuristic_win_loss": _win_loss_tie(old_m),
        "revised_vs_heuristic_win_loss": _win_loss_tie(new_m),
        "revised_minus_old_margin_vs_heuristic": {
            "mean": _mean(delta_m),
            "std": _std(delta_m),
            "win_loss": _win_loss_tie(delta_m),
        },
        "mean_old_uncertain_rate": _mean([float(r["old_uncertain_rate"]) for r in paired_rows]),
        "mean_new_uncertain_rate": _mean([float(r["new_uncertain_rate"]) for r in paired_rows]),
        "mean_old_label_positive_rate": _mean([float(r["old_label_positive_rate"]) for r in paired_rows]),
        "mean_new_label_positive_rate": _mean([float(r["new_label_positive_rate"]) for r in paired_rows]),
    }
    write_json(out_dir / "label_refinement_comparison_summary.json", summary)

    next_move = (
        "continue with stop-vs-act using revised label setup, but keep claims bounded and prioritize validating the delta proxy"
        if summary["revised_minus_old_margin_vs_heuristic"]["mean"] > 0
        else "keep stop-vs-act mixed and focus next on the local delta proxy, not further threshold tweaking"
    )

    note_lines = [
        "# Stop-vs-act bounded label-refinement comparison note",
        "",
        "## What changed",
        f"- Single refinement: instability guard band in uncertainty labeling (`instability_guard_band={args.instability_guard_band:.3f}`).",
        "- Unstable examples are marked uncertain only when their `|delta_mean|` is within the guard band.",
        "",
        "## Matched comparison setup",
        f"- Seeds: `{','.join(str(s) for s in compare_seeds)}`",
        f"- Budgets: `{','.join(str(b) for b in compare_budgets)}`",
        f"- Uncertainty policy fixed: `{args.uncertainty_policy}`",
        f"- Episodes per cell: `{args.episodes}`; eval episodes per run: `{args.eval_episodes}`",
        "",
        "## Results",
        f"- Old label rule vs heuristic: `{summary['old_vs_heuristic_win_loss']}`.",
        f"- Revised label rule vs heuristic: `{summary['revised_vs_heuristic_win_loss']}`.",
        f"- Revised minus old margin vs heuristic: mean `{summary['revised_minus_old_margin_vs_heuristic']['mean']:+.4f}`, std `{summary['revised_minus_old_margin_vs_heuristic']['std']:.4f}`, W/L/T `{summary['revised_minus_old_margin_vs_heuristic']['win_loss']}`.",
        f"- Mean uncertain-rate change: `{summary['mean_old_uncertain_rate']:.4f} -> {summary['mean_new_uncertain_rate']:.4f}`.",
        f"- Mean ACT-label-rate change: `{summary['mean_old_label_positive_rate']:.4f} -> {summary['mean_new_label_positive_rate']:.4f}`.",
        "",
        "## Conservative interpretation",
        "- This is a bounded small-grid result only.",
        "- If gain is small/noisy, treat the direction as promising-but-mixed rather than solved.",
        "- If gains plateau, the next bottleneck is likely the local delta proxy quality rather than simple thresholding.",
        "",
        "## Recommendation",
        f"- **{next_move}**.",
    ]
    Path(args.comparison_note_path).write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
