#!/usr/bin/env python3
"""Bounded diagnosis + single-revision pass for stop-vs-act controller."""

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


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / max(1, len(vals)))


def _std(vals: list[float]) -> float:
    if len(vals) <= 1:
        return 0.0
    return float(statistics.pstdev(vals))


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
    p = argparse.ArgumentParser(description="Diagnose mixed stop-vs-act performance and test one revision")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_controller_revision_pass")
    p.add_argument(
        "--prior-robustness-dir",
        default="outputs/stop_vs_act_controller_robustness/20260415T000000Z",
        help="Path to the completed bounded robustness sweep outputs",
    )
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
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument("--entropy-threshold", type=float, default=0.62)
    p.add_argument("--baseline-policy", default="downweight", choices=["none", "downweight", "filter"])
    p.add_argument("--revised-policy", default="downweight_nonpositive")
    p.add_argument(
        "--diagnosis-note-path",
        default="experiments/stop_vs_act_controller_diagnosis_note.md",
    )
    p.add_argument(
        "--comparison-note-path",
        default="experiments/stop_vs_act_controller_revision_comparison_note.md",
    )
    return p.parse_args()


def _dataset_diagnostics(
    *,
    seeds: list[int],
    budgets: list[int],
    episodes: int,
    train_ratio: float,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
    label_cfg: StopVsActLabelConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for budget in budgets:
        for seed in seeds:
            ds = build_stop_vs_act_dataset(
                episodes=episodes,
                budget=budget,
                seed=seed,
                train_ratio=train_ratio,
                n_init_branches=n_init_branches,
                max_depth=max_depth,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                label_cfg=label_cfg,
            )
            label_pos = _mean([float(r["label_act"]) for r in ds])
            uncertain_rate = _mean([float(r["is_uncertain"]) for r in ds])
            unstable_rate = _mean([1.0 if float(r["delta_std"]) >= label_cfg.instability_std_threshold else 0.0 for r in ds])
            near_zero_rate = _mean([1.0 if abs(float(r["delta_mean"])) <= label_cfg.uncertainty_band else 0.0 for r in ds])
            heuristic_agreement = _mean(
                [
                    1.0
                    if (1 if float(r["gap_to_best_other_gain"]) > 0.01 else 0) == int(r["label_act"])
                    else 0.0
                    for r in ds
                ]
            )
            uncertain_pos = _mean([float(r["is_uncertain"]) for r in ds if int(r["label_act"]) == 1])
            uncertain_neg = _mean([float(r["is_uncertain"]) for r in ds if int(r["label_act"]) == 0])
            rows.append(
                {
                    "seed": seed,
                    "budget": budget,
                    "rows": len(ds),
                    "label_positive_rate": label_pos,
                    "uncertain_rate": uncertain_rate,
                    "unstable_rate": unstable_rate,
                    "near_zero_rate": near_zero_rate,
                    "heuristic_label_agreement": heuristic_agreement,
                    "uncertain_rate_if_label_act_1": uncertain_pos,
                    "uncertain_rate_if_label_act_0": uncertain_neg,
                }
            )
    return rows


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_seeds = _parse_int_list(args.diagnosis_seeds)
    diagnosis_budgets = _parse_int_list(args.diagnosis_budgets)
    compare_seeds = _parse_int_list(args.compare_seeds)
    compare_budgets = _parse_int_list(args.compare_budgets)

    label_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        rollout_samples=args.rollout_samples,
    )

    # ---- Phase 1: diagnosis using prior sweep outputs + bounded dataset diagnostics.
    prior_dir = Path(args.prior_robustness_dir)
    prior_summary = json.loads((prior_dir / "robustness_summary.json").read_text(encoding="utf-8"))
    prior_policy_rows: list[dict[str, Any]] = []
    with (prior_dir / "robustness_summary_by_uncertainty_policy.csv").open("r", encoding="utf-8") as f:
        prior_policy_rows = list(csv.DictReader(f))

    diag_rows = _dataset_diagnostics(
        seeds=diagnosis_seeds,
        budgets=diagnosis_budgets,
        episodes=args.episodes,
        train_ratio=args.train_ratio,
        n_init_branches=args.n_init_branches,
        max_depth=args.max_depth,
        finish_prob_base=args.finish_prob_base,
        answer_noise=args.answer_noise,
        label_cfg=label_cfg,
    )
    _write_csv(out_dir / "diagnosis_dataset_stats.csv", diag_rows, fieldnames=list(diag_rows[0].keys()))

    diag_summary = {
        "prior_run_count": int(prior_summary["run_count"]),
        "prior_learned_vs_heuristic_win_loss": prior_summary["learned_vs_heuristic_win_loss"],
        "prior_learned_vs_uncertainty_win_loss": prior_summary["learned_vs_uncertainty_win_loss"],
        "diagnosis_grid": {
            "seeds": diagnosis_seeds,
            "budgets": diagnosis_budgets,
            "episodes": args.episodes,
        },
        "dataset_signal": {
            "mean_label_positive_rate": _mean([float(r["label_positive_rate"]) for r in diag_rows]),
            "mean_uncertain_rate": _mean([float(r["uncertain_rate"]) for r in diag_rows]),
            "mean_unstable_rate": _mean([float(r["unstable_rate"]) for r in diag_rows]),
            "mean_near_zero_rate": _mean([float(r["near_zero_rate"]) for r in diag_rows]),
            "mean_heuristic_label_agreement": _mean([float(r["heuristic_label_agreement"]) for r in diag_rows]),
            "mean_uncertain_rate_if_label_act_1": _mean([float(r["uncertain_rate_if_label_act_1"]) for r in diag_rows]),
            "mean_uncertain_rate_if_label_act_0": _mean([float(r["uncertain_rate_if_label_act_0"]) for r in diag_rows]),
        },
        "bottleneck_hypothesis": (
            "High uncertainty coverage is dominated by rollout-instability, and ACT-positive labels are both rare and overwhelmingly marked uncertain; "
            "generic uncertainty downweight/filter thus suppresses critical positive signal and can make the learned gate under-act versus heuristic."
        ),
        "targeted_revision": {
            "name": "downweight_nonpositive",
            "description": "Apply uncertainty downweighting only to uncertain STOP labels; keep uncertain ACT labels at full weight.",
            "rationale": "Preserve scarce ACT signal while still damping noisy uncertain negatives.",
        },
        "prior_policy_snapshot": prior_policy_rows,
    }
    write_json(out_dir / "diagnosis_summary.json", diag_summary)

    diagnosis_lines = [
        "# Stop-vs-act mixed-performance diagnosis note",
        "",
        "## 1) Most likely bottleneck",
        "- The dominant bottleneck is **uncertainty handling interacting with rare ACT labels**.",
        "- Most examples are marked uncertain (mostly due to high delta instability), and ACT labels are very sparse.",
        "- This makes generic uncertainty suppression (especially filtering) prone to removing/downweighting too much useful ACT signal.",
        "",
        "## 2) Evidence",
        f"- Prior sweep learned-vs-heuristic was mixed: `{prior_summary['learned_vs_heuristic_win_loss']}`.",
        f"- Mean label positive rate across bounded diagnosis grid: `{diag_summary['dataset_signal']['mean_label_positive_rate']:.4f}`.",
        f"- Mean uncertain rate: `{diag_summary['dataset_signal']['mean_uncertain_rate']:.4f}`.",
        f"- Mean unstable-rate component: `{diag_summary['dataset_signal']['mean_unstable_rate']:.4f}`.",
        f"- Mean uncertain rate among ACT-positive labels: `{diag_summary['dataset_signal']['mean_uncertain_rate_if_label_act_1']:.4f}`.",
        f"- Mean uncertain rate among STOP labels: `{diag_summary['dataset_signal']['mean_uncertain_rate_if_label_act_0']:.4f}`.",
        f"- Mean heuristic-label agreement: `{diag_summary['dataset_signal']['mean_heuristic_label_agreement']:.4f}` (suggesting limited room unless label signal is preserved better).",
        "",
        "## 3) Single best lightweight revision to try next",
        "- Add one training policy: **`downweight_nonpositive`**.",
        "- Rule: only downweight uncertain examples when label is STOP(0); retain full weight for ACT(1) even if uncertain.",
        "- Goal: reduce instability from uncertain negatives without suppressing scarce ACT supervision.",
    ]
    diagnosis_note_path = Path(args.diagnosis_note_path)
    diagnosis_note_path.write_text("\n".join(diagnosis_lines) + "\n", encoding="utf-8")

    # ---- Phase 2+3: bounded comparison baseline vs revised setup.
    compare_rows: list[dict[str, Any]] = []
    for budget in compare_budgets:
        for seed in compare_seeds:
            ds = build_stop_vs_act_dataset(
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
            train_rows = [r for r in ds if r["split"] == "train"]
            test_rows = [r for r in ds if r["split"] == "test"]

            for tag, policy in [("baseline", args.baseline_policy), ("revised", args.revised_policy)]:
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
                crows = {r["policy"]: r for r in cmp.comparison_rows}
                compare_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "setup_tag": tag,
                        "uncertainty_policy": policy,
                        "train_rows_used": int(model["train_rows_used"]),
                        "classification_accuracy": float(cls["accuracy"]),
                        "classification_auc": float(cls["roc_auc"]),
                        "learned_accuracy": float(crows["learned_stop_vs_act"]["accuracy"]),
                        "heuristic_accuracy": float(crows["heuristic_gain_gap"]["accuracy"]),
                        "uncertainty_only_accuracy": float(crows["uncertainty_entropy_only"]["accuracy"]),
                        "learned_avg_primary_actions": float(crows["learned_stop_vs_act"]["avg_primary_actions"]),
                        "heuristic_avg_primary_actions": float(crows["heuristic_gain_gap"]["avg_primary_actions"]),
                        "learned_vs_heuristic_accuracy_margin": float(cmp.metrics["learned_vs_heuristic_accuracy_margin"]),
                        "learned_vs_uncertainty_accuracy_margin": float(cmp.metrics["learned_vs_uncertainty_accuracy_margin"]),
                    }
                )

    compare_rows = sorted(compare_rows, key=lambda r: (int(r["budget"]), int(r["seed"]), str(r["setup_tag"])))
    _write_csv(out_dir / "revision_bounded_comparison_per_run.csv", compare_rows, fieldnames=list(compare_rows[0].keys()))

    baseline_rows = [r for r in compare_rows if r["setup_tag"] == "baseline"]
    revised_rows = [r for r in compare_rows if r["setup_tag"] == "revised"]
    paired_rows: list[dict[str, Any]] = []
    for b in baseline_rows:
        key = (int(b["seed"]), int(b["budget"]))
        rr = next(r for r in revised_rows if (int(r["seed"]), int(r["budget"])) == key)
        paired_rows.append(
            {
                "seed": key[0],
                "budget": key[1],
                "baseline_policy": b["uncertainty_policy"],
                "revised_policy": rr["uncertainty_policy"],
                "baseline_margin_vs_heuristic": float(b["learned_vs_heuristic_accuracy_margin"]),
                "revised_margin_vs_heuristic": float(rr["learned_vs_heuristic_accuracy_margin"]),
                "delta_margin_vs_heuristic": float(rr["learned_vs_heuristic_accuracy_margin"]) - float(b["learned_vs_heuristic_accuracy_margin"]),
                "baseline_margin_vs_uncertainty": float(b["learned_vs_uncertainty_accuracy_margin"]),
                "revised_margin_vs_uncertainty": float(rr["learned_vs_uncertainty_accuracy_margin"]),
                "delta_margin_vs_uncertainty": float(rr["learned_vs_uncertainty_accuracy_margin"]) - float(b["learned_vs_uncertainty_accuracy_margin"]),
                "delta_learned_accuracy": float(rr["learned_accuracy"]) - float(b["learned_accuracy"]),
            }
        )

    _write_csv(out_dir / "revision_bounded_comparison_paired.csv", paired_rows, fieldnames=list(paired_rows[0].keys()))

    base_margins = [float(r["baseline_margin_vs_heuristic"]) for r in paired_rows]
    rev_margins = [float(r["revised_margin_vs_heuristic"]) for r in paired_rows]
    delta_margins = [float(r["delta_margin_vs_heuristic"]) for r in paired_rows]

    comparison_summary = {
        "grid": {
            "seeds": compare_seeds,
            "budgets": compare_budgets,
            "episodes": args.episodes,
            "eval_episodes": args.eval_episodes,
        },
        "baseline_policy": args.baseline_policy,
        "revised_policy": args.revised_policy,
        "baseline_vs_heuristic_win_loss": _win_loss_tie(base_margins),
        "revised_vs_heuristic_win_loss": _win_loss_tie(rev_margins),
        "revised_minus_baseline_delta_vs_heuristic": {
            "mean": _mean(delta_margins),
            "std": _std(delta_margins),
            "win_loss": _win_loss_tie(delta_margins),
        },
        "mean_baseline_margin_vs_heuristic": _mean(base_margins),
        "mean_revised_margin_vs_heuristic": _mean(rev_margins),
    }
    write_json(out_dir / "revision_bounded_comparison_summary.json", comparison_summary)

    rec = "keep but focus next on label construction" if comparison_summary["revised_minus_baseline_delta_vs_heuristic"]["mean"] > 0 else "pause and rethink the target/feature design"

    comparison_lines = [
        "# Stop-vs-act targeted revision bounded comparison note",
        "",
        "## Revision tested",
        f"- Baseline setup: `{args.baseline_policy}`",
        f"- Revised setup: `{args.revised_policy}` (uncertain STOP downweight only; uncertain ACT kept at full weight)",
        f"- Grid: seeds `{','.join(str(s) for s in compare_seeds)}`, budgets `{','.join(str(b) for b in compare_budgets)}`",
        f"- Episodes per cell: `{args.episodes}`, eval episodes per run: `{args.eval_episodes}`",
        "",
        "## Bounded result summary",
        f"- Baseline vs heuristic win/loss/tie: `{comparison_summary['baseline_vs_heuristic_win_loss']}`.",
        f"- Revised vs heuristic win/loss/tie: `{comparison_summary['revised_vs_heuristic_win_loss']}`.",
        f"- Mean margin vs heuristic: baseline `{comparison_summary['mean_baseline_margin_vs_heuristic']:+.4f}`, revised `{comparison_summary['mean_revised_margin_vs_heuristic']:+.4f}`.",
        f"- Revised minus baseline delta on margin vs heuristic: mean `{comparison_summary['revised_minus_baseline_delta_vs_heuristic']['mean']:+.4f}`, std `{comparison_summary['revised_minus_baseline_delta_vs_heuristic']['std']:.4f}`, W/L/T `{comparison_summary['revised_minus_baseline_delta_vs_heuristic']['win_loss']}`.",
        "",
        "## Conservative interpretation",
        "- Treat this as bounded evidence only.",
        "- If revised beats baseline in both mean and win/loss counts with reduced failures, it is a lightweight improvement worth carrying forward.",
        "- If not, keep current direction mixed and prioritize label-quality revisions.",
        "",
        "## Recommendation",
        f"- **{rec}**.",
    ]
    comparison_note_path = Path(args.comparison_note_path)
    comparison_note_path.write_text("\n".join(comparison_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_dir": str(out_dir),
                "diagnosis_note": str(diagnosis_note_path),
                "comparison_note": str(comparison_note_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
