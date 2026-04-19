#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, evaluate_models, prepare_learning_tables, train_models
from experiments.bruteforce_branch_labels import (
    BruteForceLabelConfig,
    collect_frontier_states,
    config_to_dict,
    evaluate_state_candidates,
    load_dataset_examples,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded value-aware target regime comparison")
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="value_aware_target_regime_comparison_20260419")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--max-frontier-states", type=int, default=60)
    p.add_argument("--rollout-samples-per-candidate", type=int, default=10)
    p.add_argument("--max-allocation-samples", type=int, default=24)
    p.add_argument("--frontier-budget", type=int, default=7)
    p.add_argument("--target-estimation-repeats", type=int, default=2)
    p.add_argument("--paired-rollout-comparison", action="store_true", default=True)
    p.add_argument("--disable-paired-rollout-comparison", action="store_true")
    p.add_argument("--defer-threshold-selection", choices=["fixed", "val_defer_f1"], default="fixed")
    p.add_argument("--defer-eval-threshold-override", type=float, default=-1.0)
    return p.parse_args()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_labels(args: argparse.Namespace, out_dir: Path) -> dict[str, list[dict[str, Any]]]:
    cfg = BruteForceLabelConfig(
        seed=int(args.seed),
        max_frontier_states=int(args.max_frontier_states),
        rollout_samples_per_candidate=int(args.rollout_samples_per_candidate),
        max_allocation_samples=int(args.max_allocation_samples),
        frontier_budget=int(args.frontier_budget),
        target_estimation_repeats=int(args.target_estimation_repeats),
        paired_rollout_comparison=bool(args.paired_rollout_comparison and not args.disable_paired_rollout_comparison),
        min_remaining_budget=2,
        max_remaining_budget=5,
        episodes_per_example=2,
        exact_mode=True,
        allow_mock_data=True,
    )
    examples = load_dataset_examples(cfg)
    states = collect_frontier_states(examples, cfg)

    candidates: list[dict[str, Any]] = []
    pairwise: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    state_values: list[dict[str, Any]] = []

    for state in states:
        result = evaluate_state_candidates(state, cfg)
        ss = dict(result["state_summary"])
        ss["dataset_name"] = cfg.dataset_name
        summaries.append(ss)
        sv = dict(result["state_value_target"])
        sv["dataset_name"] = cfg.dataset_name
        state_values.append(sv)
        for row in result["candidate_labels"]:
            out = dict(row)
            out.update({"state_id": state.state_id, "example_id": state.example_id, "remaining_budget": state.remaining_budget, "dataset_name": cfg.dataset_name})
            candidates.append(out)
        for row in result["pairwise_labels"]:
            out = dict(row)
            out.update({"state_id": state.state_id, "example_id": state.example_id, "remaining_budget": state.remaining_budget, "dataset_name": cfg.dataset_name})
            pairwise.append(out)

    label_dir = out_dir / "labels"
    write_jsonl(label_dir / "candidate_labels.jsonl", candidates)
    write_jsonl(label_dir / "pairwise_labels.jsonl", pairwise)
    write_jsonl(label_dir / "state_summaries.jsonl", summaries)
    write_jsonl(label_dir / "state_value_targets.jsonl", state_values)

    _write_json(
        out_dir / "target_manifest.json",
        {
            "generator": "value_aware_target_regime_comparison_v1",
            "label_config": config_to_dict(cfg),
            "counts": {
                "states": len(summaries),
                "candidate_rows": len(candidates),
                "pairwise_rows": len(pairwise),
                "state_value_rows": len(state_values),
            },
            "artifacts": {
                "candidate_labels": str(label_dir / "candidate_labels.jsonl"),
                "pairwise_labels": str(label_dir / "pairwise_labels.jsonl"),
                "state_summaries": str(label_dir / "state_summaries.jsonl"),
                "state_value_targets": str(label_dir / "state_value_targets.jsonl"),
            },
        },
    )

    return {
        "candidate_labels": candidates,
        "pairwise_labels": pairwise,
        "state_summaries": summaries,
        "state_value_targets": state_values,
    }


def _method_cfg(base: LearningConfig, method: str, args: argparse.Namespace) -> LearningConfig:
    if method == "baseline_default":
        return base
    if method == "value_aware":
        return replace(base, pointwise_target_field="Q_expand", pairwise_target_mode="value_gap")
    if method == "value_aware_ambiguity":
        return replace(
            base,
            pointwise_target_field="Q_expand",
            pairwise_target_mode="value_gap",
            pairwise_near_tie_action="downweight",
            pairwise_near_tie_downweight=0.2,
            uncertainty_weighting=True,
            feature_set="v3",
        )
    if method == "value_aware_ambiguity_decomposed":
        return replace(
            base,
            pointwise_target_field="Q_expand",
            pairwise_target_mode="value_gap",
            pairwise_near_tie_action="downweight",
            pairwise_near_tie_downweight=0.2,
            uncertainty_weighting=True,
            feature_set="v3",
            train_pairwise_defer_classifier=True,
            defer_target_mode="value_aware",
            defer_calibration="none",
            defer_threshold_selection=str(args.defer_threshold_selection),
            defer_eval_threshold_override=float(args.defer_eval_threshold_override),
            train_state_commit_value_model=True,
            state_commit_alpha=0.75,
        )
    if method == "value_aware_ambiguity_decomposed_stabilized":
        return replace(
            base,
            pointwise_target_field="A_expand_minus_commit",
            pointwise_weight_mode="regret_gap_x_reliability",
            pairwise_target_mode="value_gap",
            pairwise_near_tie_action="downweight",
            pairwise_near_tie_downweight=0.15,
            uncertainty_weighting=True,
            feature_set="v3",
            train_pairwise_defer_classifier=True,
            defer_target_mode="value_aware",
            defer_calibration="none",
            defer_threshold_selection=str(args.defer_threshold_selection),
            defer_eval_threshold_override=float(args.defer_eval_threshold_override),
            train_state_commit_value_model=True,
            state_commit_alpha=0.75,
        )
    raise ValueError(method)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    artifacts = _build_labels(args, out_dir)
    methods = [
        "baseline_default",
        "value_aware",
        "value_aware_ambiguity",
        "value_aware_ambiguity_decomposed",
        "value_aware_ambiguity_decomposed_stabilized",
    ]

    base_cfg = LearningConfig(
        seed=int(args.seed),
        feature_set="v1",
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
        train_pairwise_svm=False,
    )

    per_method_metrics: dict[str, Any] = {}
    hard_slice: dict[str, Any] = {}
    ambiguity_diag: dict[str, Any] = {}

    for method in methods:
        cfg = _method_cfg(base_cfg, method, args)
        tables = prepare_learning_tables(artifacts, cfg)
        models = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts" / method)
        eval_summary = evaluate_models(models, tables, cfg)
        per_method_metrics[method] = {
            "config": cfg.__dict__,
            "evaluation": eval_summary,
        }

        main_pairwise = eval_summary.get("pairwise", {})
        hard_slice[method] = {
            "near_tie_pairwise_accuracy_test": main_pairwise.get("near_tie_pairwise_accuracy_test"),
            "adjacent_rank_pairwise_accuracy_test": main_pairwise.get("adjacent_rank_pairwise_accuracy_test"),
            "exact_promoted_hard_region_pairwise_accuracy_test": main_pairwise.get("exact_promoted_hard_region_pairwise_accuracy_test"),
        }
        ambiguity_diag[method] = {
            "pairwise_accuracy_by_mode": main_pairwise.get("pairwise_accuracy_by_mode", {}),
            "pairwise_accuracy_by_pair_type": main_pairwise.get("pairwise_accuracy_by_pair_type", {}),
            "defer_metrics": eval_summary.get("pairwise_defer_classifier", {}),
            "defer_label_audit": eval_summary.get("_defer_label_audit", {}),
        }

    def _m(method: str, model_name: str, key: str) -> float | None:
        v = per_method_metrics.get(method, {}).get("evaluation", {}).get(model_name, {}).get(key)
        return float(v) if isinstance(v, (float, int)) else None

    aggregate = {
        "methods": methods,
        "matched_setup": {
            "seed": int(args.seed),
            "max_frontier_states": int(args.max_frontier_states),
            "same_labels_across_methods": True,
        },
        "summary": {
            m: {
                "pairwise_accuracy_test": _m(m, "pairwise", "pairwise_accuracy_test"),
                "near_tie_pairwise_accuracy_test": _m(m, "pairwise", "near_tie_pairwise_accuracy_test"),
                "ranking_top1_accuracy_test": _m(m, "pairwise", "ranking_top1_accuracy_test"),
                "defer_three_way_accuracy_test": _m(m, "pairwise_defer_classifier", "three_way_accuracy_test"),
                "defer_coverage_test": _m(m, "pairwise_defer_classifier", "coverage_test"),
                "defer_accepted_only_accuracy_test": _m(m, "pairwise_defer_classifier", "accepted_only_accuracy_test"),
                "expand_vs_commit_accuracy_test": _m(m, "pointwise", "expand_vs_commit_accuracy_test"),
                "expand_vs_commit_mean_regret_test": _m(m, "pointwise", "expand_vs_commit_mean_regret_test"),
                "far_margin_pairwise_accuracy_test": _m(m, "pairwise", "far_margin_pairwise_accuracy_test"),
            }
            for m in methods
        },
    }

    _write_json(out_dir / "per_method_metrics.json", per_method_metrics)
    _write_json(out_dir / "hard_slice_diagnostics.json", hard_slice)
    _write_json(out_dir / "ambiguity_bucket_diagnostics.json", ambiguity_diag)
    _write_json(
        out_dir / "defer_label_audit.json",
        {
            m: per_method_metrics[m]["evaluation"].get("_defer_label_audit", {})
            for m in methods
        },
    )
    _write_json(
        out_dir / "defer_score_audit.json",
        {
            m: {
                "defer_score_distribution_test": per_method_metrics[m]["evaluation"].get("pairwise_defer_classifier", {}).get("defer_score_distribution_test", {}),
                "threshold_trace_test": per_method_metrics[m]["evaluation"].get("pairwise_defer_classifier", {}).get("threshold_trace_test", []),
                "threshold_selection": per_method_metrics[m]["evaluation"].get("pairwise_defer_classifier", {}).get("threshold_selection", {}),
            }
            for m in methods
        },
    )
    decomposed_scores = per_method_metrics.get("value_aware_ambiguity_decomposed", {}).get("evaluation", {}).get("pairwise_defer_classifier", {}).get("per_example_defer_scores_test", [])
    _write_json(out_dir / "defer_per_example_scores_decomposed.json", {"rows": decomposed_scores})
    _write_json(out_dir / "aggregate_comparison.json", aggregate)
    _write_json(
        out_dir / "run_manifest.json",
        {
            "run_id": args.run_id,
            "script": "scripts/run_value_aware_target_regime_comparison.py",
            "elapsed_sec": time.time() - t0,
            "outputs": [
                "target_manifest.json",
                "per_method_metrics.json",
                "hard_slice_diagnostics.json",
                "ambiguity_bucket_diagnostics.json",
                "defer_label_audit.json",
                "defer_score_audit.json",
                "defer_per_example_scores_decomposed.json",
                "aggregate_comparison.json",
            ],
        },
    )

    note = REPO_ROOT / "experiments" / "value_aware_target_regime_status_note_2026_04_19.md"
    note.write_text(
        "\n".join(
            [
                "# Value-aware target regime bounded comparison (2026-04-19)",
                "",
                "Implemented a budget-conditioned target layer with Q_commit/Q_expand plus regret/gap fields,",
                "ambiguity buckets, and a value-aware defer option; then ran matched comparisons across 4 methods.",
                "",
                "Key artifacts:",
                f"- {out_dir / 'aggregate_comparison.json'}",
                f"- {out_dir / 'per_method_metrics.json'}",
                f"- {out_dir / 'hard_slice_diagnostics.json'}",
                f"- {out_dir / 'ambiguity_bucket_diagnostics.json'}",
                f"- {out_dir / 'defer_label_audit.json'}",
                f"- {out_dir / 'defer_score_audit.json'}",
                f"- {out_dir / 'defer_per_example_scores_decomposed.json'}",
                "",
                "Interpretation discipline:",
                "- This is a bounded mock-permitted run for pipeline hardening and supervision semantics checks.",
                "- Treat gains/losses as directional until replayed on larger exact-heavy state sets.",
                "",
                "Status answers (bounded evidence, no broad claims):",
                "- Did continuation-minus-commit reduce supervision bottleneck? Partially: richer value targets, gap/regret/reliability fields, and ambiguity buckets are now directly supervised.",
                "- Improve expand-vs-commit? Check aggregate_comparison expand_vs_commit_accuracy_test and regret fields vs baseline.",
                "- Improve branch ranking? Check ranking_top1_accuracy_test and pairwise_accuracy_test by method/slice.",
                "- Improve hard ambiguous states? Check near_tie_* and ambiguity_bucket_diagnostics.json; report mixed if unstable.",
                "- Is target variance unresolved? Reduced via paired rollouts + repeated estimation + reliability weighting, but still a tracked risk.",
                "- Best next step: run the same matched protocol on larger exact-heavy state sets and tune ambiguity-band weighting per regime.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_dir": str(out_dir), "note": str(note)}, indent=2))


if __name__ == "__main__":
    main()
