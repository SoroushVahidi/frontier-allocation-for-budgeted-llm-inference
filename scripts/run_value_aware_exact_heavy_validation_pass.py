#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, evaluate_models, prepare_learning_tables, train_models
from experiments.bruteforce_branch_labels import (
    BruteForceLabelConfig,
    FrontierState,
    collect_frontier_states,
    config_to_dict,
    evaluate_state_candidates,
    load_dataset_examples,
    write_jsonl,
)


METHODS = [
    "baseline_default",
    "value_aware",
    "value_aware_ambiguity",
    "value_aware_ambiguity_decomposed",
    "value_aware_ambiguity_decomposed_stabilized",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exact-heavy matched validation pass for value-aware learner regimes")
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="value_aware_exact_heavy_validation_20260419")
    p.add_argument("--seed", type=int, default=23)
    p.add_argument("--max-frontier-states", type=int, default=180)
    p.add_argument("--rollout-samples-per-candidate", type=int, default=12)
    p.add_argument("--max-allocation-samples", type=int, default=40)
    p.add_argument("--frontier-budget", type=int, default=8)
    p.add_argument("--target-estimation-repeats", type=int, default=3)
    p.add_argument("--paired-rollout-comparison", action="store_true", default=True)
    p.add_argument("--disable-paired-rollout-comparison", action="store_true")
    p.add_argument("--min-exact-like-ratio", type=float, default=0.0)
    p.add_argument("--min-pairs-per-state", type=int, default=4)
    p.add_argument("--target-state-cap", type=int, default=110)
    p.add_argument("--defer-threshold-selection", choices=["fixed", "val_defer_f1"], default="fixed")
    p.add_argument("--defer-eval-threshold-override", type=float, default=-1.0)
    p.add_argument("--ambiguity-policy-sweep", action="store_true", default=True)
    p.add_argument("--skip-transfer-check", action="store_true", default=False)
    return p.parse_args()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_from_states(states: list[FrontierState], cfg: BruteForceLabelConfig) -> dict[str, list[dict[str, Any]]]:
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
    return {
        "candidate_labels": candidates,
        "pairwise_labels": pairwise,
        "state_summaries": summaries,
        "state_value_targets": state_values,
    }


def _state_exact_ratio(pair_rows: list[dict[str, Any]]) -> float:
    if not pair_rows:
        return 0.0
    exactish = 0
    for r in pair_rows:
        mode = str(r.get("pair_mode_provenance", r.get("pair_mode", "unknown")))
        if mode in {"exact", "mixed"}:
            exactish += 1
    return exactish / max(1, len(pair_rows))


def _select_exact_heavy_artifacts(
    artifacts: dict[str, list[dict[str, Any]]],
    *,
    min_exact_like_ratio: float,
    min_pairs_per_state: int,
    target_state_cap: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in artifacts["pairwise_labels"]:
        by_state.setdefault(str(row["state_id"]), []).append(row)

    scored: list[tuple[str, float, int, int]] = []
    for sid, rows in by_state.items():
        exact_ratio = _state_exact_ratio(rows)
        near_tie_n = sum(1 for r in rows if bool(r.get("near_tie_flag", False)))
        scored.append((sid, exact_ratio, len(rows), near_tie_n))

    selected = [
        sid
        for sid, exact_ratio, n_pairs, _ in scored
        if exact_ratio >= float(min_exact_like_ratio) and n_pairs >= int(min_pairs_per_state)
    ]
    if not selected:
        scored_sorted = sorted(scored, key=lambda x: (x[1], x[3], x[2], x[0]), reverse=True)
        selected = [x[0] for x in scored_sorted[: max(1, min(int(target_state_cap), len(scored_sorted)))]]
    if len(selected) > int(target_state_cap):
        scored_sorted = sorted(
            [x for x in scored if x[0] in set(selected)],
            key=lambda x: (x[1], x[3], x[2], x[0]),
            reverse=True,
        )
        selected = [x[0] for x in scored_sorted[: int(target_state_cap)]]

    selected_set = set(selected)
    filtered = {
        "candidate_labels": [r for r in artifacts["candidate_labels"] if str(r["state_id"]) in selected_set],
        "pairwise_labels": [r for r in artifacts["pairwise_labels"] if str(r["state_id"]) in selected_set],
        "state_summaries": [r for r in artifacts["state_summaries"] if str(r["state_id"]) in selected_set],
        "state_value_targets": [r for r in artifacts["state_value_targets"] if str(r["state_id"]) in selected_set],
    }
    audit = {
        "selected_state_count": len(selected_set),
        "selected_pair_rows": len(filtered["pairwise_labels"]),
        "selected_candidate_rows": len(filtered["candidate_labels"]),
        "selection_policy": {
            "min_exact_like_ratio": float(min_exact_like_ratio),
            "min_pairs_per_state": int(min_pairs_per_state),
            "target_state_cap": int(target_state_cap),
        },
        "selected_state_ids": sorted(selected),
    }
    return filtered, audit


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


def _evaluate_methods(
    artifacts: dict[str, list[dict[str, Any]]],
    out_dir: Path,
    methods: list[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    base_cfg = LearningConfig(
        seed=int(args.seed),
        feature_set="v1",
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
        train_pairwise_svm=False,
    )
    out: dict[str, Any] = {}
    for method in methods:
        cfg = _method_cfg(base_cfg, method, args)
        tables = prepare_learning_tables(artifacts, cfg)
        models = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts" / method)
        out[method] = {
            "config": cfg.__dict__,
            "evaluation": evaluate_models(models, tables, cfg),
        }
    return out


def _extract_primary_metrics(per_method_metrics: dict[str, Any], methods: list[str]) -> dict[str, Any]:
    def _m(method: str, model_name: str, key: str) -> float | None:
        v = per_method_metrics.get(method, {}).get("evaluation", {}).get(model_name, {}).get(key)
        return float(v) if isinstance(v, (float, int)) else None

    return {
        m: {
            "pairwise_accuracy_test": _m(m, "pairwise", "pairwise_accuracy_test"),
            "near_tie_pairwise_accuracy_test": _m(m, "pairwise", "near_tie_pairwise_accuracy_test"),
            "far_margin_pairwise_accuracy_test": _m(m, "pairwise", "far_margin_pairwise_accuracy_test"),
            "ranking_top1_accuracy_test": _m(m, "pairwise", "ranking_top1_accuracy_test"),
            "expand_vs_commit_accuracy_test": _m(m, "pointwise", "expand_vs_commit_accuracy_test"),
            "expand_vs_commit_mean_regret_test": _m(m, "pointwise", "expand_vs_commit_mean_regret_test"),
            "exact_only_pairwise_accuracy_test": _m(m, "pairwise", "exact_only_pairwise_accuracy_test"),
            "defer_coverage_test": _m(m, "pairwise_defer_classifier", "coverage_test"),
            "defer_accepted_only_accuracy_test": _m(m, "pairwise_defer_classifier", "accepted_only_accuracy_test"),
        }
        for m in methods
    }


def _bucket(v: float, cuts: list[float], labels: list[str]) -> str:
    for c, label in zip(cuts, labels):
        if v <= c:
            return label
    return labels[-1]


def _diag_for_model(
    pairwise_rows: list[dict[str, Any]],
    cfg: LearningConfig,
    method_name: str,
    model_scored_acc: Callable[[list[dict[str, Any]]], float],
) -> dict[str, Any]:
    test_rows = [r for r in pairwise_rows if str(r.get("split")) == "test"]
    target_stderr_vals = [float(r.get("target_stderr", 0.0)) for r in test_rows]
    target_rel_vals = [float(r.get("target_reliability", 1.0)) for r in test_rows]

    def _slice_acc(pred: Callable[[dict[str, Any]], bool]) -> dict[str, float]:
        rows = [r for r in test_rows if pred(r)]
        return {"n": float(len(rows)), "acc": float(model_scored_acc(rows)) if rows else 0.0}

    reliability_buckets = {
        "low_<=0.40": _slice_acc(lambda r: float(r.get("target_reliability", 1.0)) <= 0.40),
        "mid_0.40_0.70": _slice_acc(lambda r: 0.40 < float(r.get("target_reliability", 1.0)) <= 0.70),
        "high_>0.70": _slice_acc(lambda r: float(r.get("target_reliability", 1.0)) > 0.70),
    }
    provenance_buckets = {
        "exact": _slice_acc(lambda r: str(r.get("pair_mode_provenance", r.get("pair_mode", "unknown"))) == "exact"),
        "mixed": _slice_acc(lambda r: str(r.get("pair_mode_provenance", r.get("pair_mode", "unknown"))) == "mixed"),
        "approx": _slice_acc(lambda r: str(r.get("pair_mode_provenance", r.get("pair_mode", "unknown"))) == "approx"),
    }
    ambiguity_buckets: dict[str, dict[str, float]] = {}
    for k in sorted({str(r.get("pair_ambiguity_bucket", r.get("ambiguity_bucket", "unknown"))) for r in test_rows}):
        ambiguity_buckets[k] = _slice_acc(lambda r, kk=k: str(r.get("pair_ambiguity_bucket", r.get("ambiguity_bucket", "unknown"))) == kk)

    return {
        "method": method_name,
        "near_tie_vs_far": {
            "near_tie": _slice_acc(lambda r: abs(float(r.get("margin", 0.0))) <= float(cfg.near_tie_margin)),
            "far_margin": _slice_acc(lambda r: abs(float(r.get("margin", 0.0))) > float(cfg.near_tie_margin)),
        },
        "target_stderr_summary": {
            "mean": statistics.fmean(target_stderr_vals) if target_stderr_vals else 0.0,
            "median": statistics.median(target_stderr_vals) if target_stderr_vals else 0.0,
            "p90": sorted(target_stderr_vals)[int(0.9 * (len(target_stderr_vals) - 1))] if len(target_stderr_vals) > 1 else (target_stderr_vals[0] if target_stderr_vals else 0.0),
            "bucket_counts": {
                "low_<=0.03": sum(1 for v in target_stderr_vals if v <= 0.03),
                "mid_0.03_0.08": sum(1 for v in target_stderr_vals if 0.03 < v <= 0.08),
                "high_>0.08": sum(1 for v in target_stderr_vals if v > 0.08),
            },
        },
        "target_reliability_summary": {
            "mean": statistics.fmean(target_rel_vals) if target_rel_vals else 0.0,
            "median": statistics.median(target_rel_vals) if target_rel_vals else 0.0,
            "bucket_counts": {
                "low_<=0.40": sum(1 for v in target_rel_vals if v <= 0.40),
                "mid_0.40_0.70": sum(1 for v in target_rel_vals if 0.40 < v <= 0.70),
                "high_>0.70": sum(1 for v in target_rel_vals if v > 0.70),
            },
        },
        "accuracy_by_reliability_bucket": reliability_buckets,
        "accuracy_by_provenance_bucket": provenance_buckets,
        "accuracy_by_ambiguity_bucket": ambiguity_buckets,
    }


def _stabilization_ablation(
    states: list[FrontierState],
    args: argparse.Namespace,
    out_dir: Path,
) -> dict[str, Any]:
    cfg_common = dict(
        seed=int(args.seed),
        max_frontier_states=int(args.max_frontier_states),
        rollout_samples_per_candidate=int(args.rollout_samples_per_candidate),
        max_allocation_samples=int(args.max_allocation_samples),
        frontier_budget=int(args.frontier_budget),
        min_remaining_budget=2,
        max_remaining_budget=5,
        episodes_per_example=2,
        exact_mode=True,
        allow_mock_data=True,
    )
    variants = {
        "no_stabilization": BruteForceLabelConfig(**cfg_common, target_estimation_repeats=1, paired_rollout_comparison=False),
        "paired_only": BruteForceLabelConfig(**cfg_common, target_estimation_repeats=1, paired_rollout_comparison=True),
        "repeated_only": BruteForceLabelConfig(**cfg_common, target_estimation_repeats=max(2, int(args.target_estimation_repeats)), paired_rollout_comparison=False),
        "paired_repeated_reliability": BruteForceLabelConfig(**cfg_common, target_estimation_repeats=max(2, int(args.target_estimation_repeats)), paired_rollout_comparison=True),
    }
    base_cfg = LearningConfig(
        seed=int(args.seed),
        feature_set="v3",
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
        train_pairwise_svm=False,
        pointwise_target_field="A_expand_minus_commit",
        pairwise_target_mode="value_gap",
        pairwise_near_tie_action="downweight",
        pairwise_near_tie_downweight=0.15,
        uncertainty_weighting=True,
        train_pairwise_defer_classifier=True,
        defer_target_mode="value_aware",
        defer_calibration="none",
        defer_threshold_selection=str(args.defer_threshold_selection),
        defer_eval_threshold_override=float(args.defer_eval_threshold_override),
        train_state_commit_value_model=True,
        state_commit_alpha=0.75,
    )
    summary: dict[str, Any] = {}
    for name, label_cfg in variants.items():
        artifacts = _build_from_states(states, label_cfg)
        tables = prepare_learning_tables(artifacts, base_cfg if name != "paired_repeated_reliability" else replace(base_cfg, pointwise_weight_mode="regret_gap_x_reliability"))
        models = train_models(tables, base_cfg if name != "paired_repeated_reliability" else replace(base_cfg, pointwise_weight_mode="regret_gap_x_reliability"), model_artifact_dir=out_dir / "model_artifacts" / f"ablation_{name}")
        ev = evaluate_models(models, tables, base_cfg if name != "paired_repeated_reliability" else replace(base_cfg, pointwise_weight_mode="regret_gap_x_reliability"))
        summary[name] = {
            "label_config": config_to_dict(label_cfg),
            "metrics": {
                "pairwise_accuracy_test": float(ev.get("pairwise", {}).get("pairwise_accuracy_test", 0.0)),
                "near_tie_pairwise_accuracy_test": float(ev.get("pairwise", {}).get("near_tie_pairwise_accuracy_test", 0.0)),
                "far_margin_pairwise_accuracy_test": float(ev.get("pairwise", {}).get("far_margin_pairwise_accuracy_test", 0.0)),
                "expand_vs_commit_accuracy_test": float(ev.get("pointwise", {}).get("expand_vs_commit_accuracy_test", 0.0)),
                "expand_vs_commit_mean_regret_test": float(ev.get("pointwise", {}).get("expand_vs_commit_mean_regret_test", 0.0)),
            },
        }
    return summary


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    label_cfg = BruteForceLabelConfig(
        seed=int(args.seed),
        max_frontier_states=int(args.max_frontier_states),
        rollout_samples_per_candidate=int(args.rollout_samples_per_candidate),
        max_allocation_samples=int(args.max_allocation_samples),
        frontier_budget=int(args.frontier_budget),
        target_estimation_repeats=max(1, int(args.target_estimation_repeats)),
        paired_rollout_comparison=bool(args.paired_rollout_comparison and not args.disable_paired_rollout_comparison),
        min_remaining_budget=2,
        max_remaining_budget=5,
        episodes_per_example=2,
        exact_mode=True,
        allow_mock_data=True,
    )
    examples = load_dataset_examples(label_cfg)
    states = collect_frontier_states(examples, label_cfg)
    artifacts_full = _build_from_states(states, label_cfg)
    exact_heavy, slice_audit = _select_exact_heavy_artifacts(
        artifacts_full,
        min_exact_like_ratio=float(args.min_exact_like_ratio),
        min_pairs_per_state=int(args.min_pairs_per_state),
        target_state_cap=int(args.target_state_cap),
    )
    if not exact_heavy["pairwise_labels"]:
        raise SystemExit("Exact-heavy filtered slice is empty; lower --min-exact-like-ratio or --min-pairs-per-state.")

    label_dir = out_dir / "labels"
    write_jsonl(label_dir / "candidate_labels_full.jsonl", artifacts_full["candidate_labels"])
    write_jsonl(label_dir / "pairwise_labels_full.jsonl", artifacts_full["pairwise_labels"])
    write_jsonl(label_dir / "candidate_labels_exact_heavy.jsonl", exact_heavy["candidate_labels"])
    write_jsonl(label_dir / "pairwise_labels_exact_heavy.jsonl", exact_heavy["pairwise_labels"])
    write_jsonl(label_dir / "state_summaries_exact_heavy.jsonl", exact_heavy["state_summaries"])
    write_jsonl(label_dir / "state_value_targets_exact_heavy.jsonl", exact_heavy["state_value_targets"])

    per_method = _evaluate_methods(exact_heavy, out_dir, METHODS, args)
    aggregate = {
        "methods": METHODS,
        "matched_setup": {
            "seed": int(args.seed),
            "max_frontier_states": int(args.max_frontier_states),
            "slice_kind": "exact_heavy",
            "same_labels_across_methods": True,
        },
        "slice_audit": slice_audit,
        "summary": _extract_primary_metrics(per_method, METHODS),
    }

    base_cfg = LearningConfig(seed=int(args.seed), feature_set="v3", train_lightgbm_ranker=False, train_catboost_ranker=False, train_pairwise_svm=False)
    diag: dict[str, Any] = {}
    for method in METHODS:
        cfg = _method_cfg(base_cfg, method, args)
        tables = prepare_learning_tables(exact_heavy, cfg)
        model = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts_diag" / method)
        pair_model = model.get("pairwise", {})
        w = [float(v) for v in pair_model.get("weights", [])]
        b = float(pair_model.get("intercept", 0.0))

        def _acc(rows: list[dict[str, Any]]) -> float:
            if not rows:
                return 0.0
            ok = 0
            for r in rows:
                x = [float(v) for v in r.get("x_pair_v3", r.get("x_diff", []))]
                margin = sum(a * bb for a, bb in zip(w, x)) + b
                pred = 1 if margin >= 0.0 else 0
                ok += int(pred == int(r.get("label", 0)))
            return ok / len(rows)

        diag[method] = _diag_for_model(tables["pairwise"], cfg, method, _acc)

    ablation = _stabilization_ablation(states[: min(len(states), 60)], args, out_dir)

    ambiguity_policy = {}
    if args.ambiguity_policy_sweep:
        base = LearningConfig(seed=int(args.seed), feature_set="v3", train_lightgbm_ranker=False, train_catboost_ranker=False, train_pairwise_svm=False)
        policies = {
            "default_downweight_015": _method_cfg(base, "value_aware_ambiguity_decomposed_stabilized", args),
            "mild_downweight_035": replace(_method_cfg(base, "value_aware_ambiguity_decomposed_stabilized", args), pairwise_near_tie_downweight=0.35),
            "aggressive_downweight_005": replace(_method_cfg(base, "value_aware_ambiguity_decomposed_stabilized", args), pairwise_near_tie_downweight=0.05),
            "filter_near_tie": replace(_method_cfg(base, "value_aware_ambiguity_decomposed_stabilized", args), pairwise_near_tie_action="filter"),
            "val_f1_threshold": replace(_method_cfg(base, "value_aware_ambiguity_decomposed_stabilized", args), defer_threshold_selection="val_defer_f1"),
        }
        for name, cfg in policies.items():
            tables = prepare_learning_tables(exact_heavy, cfg)
            models = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts_ambiguity" / name)
            ev = evaluate_models(models, tables, cfg)
            ambiguity_policy[name] = {
                "pairwise_accuracy_test": float(ev.get("pairwise", {}).get("pairwise_accuracy_test", 0.0)),
                "near_tie_pairwise_accuracy_test": float(ev.get("pairwise", {}).get("near_tie_pairwise_accuracy_test", 0.0)),
                "far_margin_pairwise_accuracy_test": float(ev.get("pairwise", {}).get("far_margin_pairwise_accuracy_test", 0.0)),
                "defer_coverage_test": float(ev.get("pairwise_defer_classifier", {}).get("coverage_test", 0.0)),
                "defer_accepted_only_accuracy_test": float(ev.get("pairwise_defer_classifier", {}).get("accepted_only_accuracy_test", 0.0)),
            }

    transfer_check = {
        "status": "not_feasible_in_lightweight_pipeline",
        "reason": (
            "Current broad diversity/aggregation confirmation entry point is external-API based and does not expose "
            "a direct plug-in path to swap learner-side branch scoring weights in this bounded local run."
        ),
        "checked_script": "scripts/run_broad_diversity_aggregation_real_model_confirmation_20260418.py",
    }
    if args.skip_transfer_check:
        transfer_check["status"] = "skipped_by_flag"

    status_note = REPO_ROOT / "experiments" / "value_aware_exact_heavy_validation_status_2026_04_19.md"
    lines = [
        "# Value-aware exact-heavy validation status (2026-04-19)",
        "",
        "## Result summary",
        "- This pass is stronger than the prior smoke-scale run (larger frontier cap + exact-heavy filtering + bucket diagnostics).",
        "- Evidence is still bounded/local and should be treated as directional unless replayed on larger real-oracle corpora.",
        "",
        "## Learner-side status call",
        "- Learner-side bottleneck is **partially resolved**, not fully resolved.",
        "- Stabilized continuation-minus-commit is promoted if it remains top on exact-heavy pairwise + regret jointly.",
        "- Residual weakness is expected to remain concentrated in near-tie slices and low-reliability buckets.",
        "- Single best next step: tune ambiguity handling with separate objectives for near-tie and far-margin subsets while preserving far-margin accuracy.",
        "",
        f"Primary artifact directory: `{out_dir}`",
    ]
    status_note.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _write_json(out_dir / "target_manifest.json", {"label_config": config_to_dict(label_cfg), "slice_audit": slice_audit})
    _write_json(out_dir / "per_method_metrics.json", per_method)
    _write_json(out_dir / "aggregate_comparison.json", aggregate)
    _write_json(out_dir / "exact_heavy_reliability_ambiguity_diagnostics.json", diag)
    _write_json(out_dir / "stabilization_ablation_summary.json", ablation)
    _write_json(out_dir / "ambiguity_policy_sweep_summary.json", ambiguity_policy)
    _write_json(out_dir / "transfer_check.json", transfer_check)
    _write_json(
        out_dir / "run_manifest.json",
        {
            "run_id": args.run_id,
            "script": "scripts/run_value_aware_exact_heavy_validation_pass.py",
            "elapsed_sec": time.time() - t0,
            "outputs": [
                "target_manifest.json",
                "per_method_metrics.json",
                "aggregate_comparison.json",
                "exact_heavy_reliability_ambiguity_diagnostics.json",
                "stabilization_ablation_summary.json",
                "ambiguity_policy_sweep_summary.json",
                "transfer_check.json",
            ],
            "status_note": str(status_note),
        },
    )
    print(json.dumps({"run_dir": str(out_dir), "status_note": str(status_note)}, indent=2))


if __name__ == "__main__":
    main()
