#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
    resolve_api_key_for_provider,
)

METHODS = [
    "self_consistency_3",
    "adaptive_min_expand_1",
    "selective_sc_hybrid_v1",
    "broad_diversity_aggregation_v1",
    "broad_diversity_aggregation_strong_v1",
]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _slice_acc(aligned_rows: list[dict[str, dict[str, Any]]], method: str, cond_key: str) -> float:
    vals = [int(row[method]["is_correct"]) for row in aligned_rows if bool(row["selective_sc_hybrid_v1"].get(cond_key, False))]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _bool_rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return float(sum(int(bool(r.get(key, False))) for r in rows) / len(rows))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Real-model confirmation for broad diversity aggregation family")
    p.add_argument("--providers", default="openai,cohere")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=3)
    p.add_argument("--seeds", default="11")
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=200)
    p.add_argument("--timeout-seconds", type=int, default=60)
    p.add_argument("--output-dir", default="outputs/broad_diversity_aggregation_real_model_confirmation_20260418")
    p.add_argument("--command-provenance", default="")
    args = p.parse_args()

    providers = _parse_str_list(args.providers)
    datasets = _parse_str_list(args.datasets)
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    provider_models = {
        "openai": args.openai_model,
        "cohere": args.cohere_model,
    }

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    run_started = datetime.now(timezone.utc).isoformat()
    rng_master = random.Random(20260418)

    per_seed_method: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []

    for provider in providers:
        api_key = resolve_api_key_for_provider(provider)
        if not api_key:
            failed_runs.append(
                {
                    "provider": provider,
                    "dataset": None,
                    "seed": None,
                    "budget": None,
                    "reason": f"missing_{provider}_api_key",
                }
            )
            continue

        model_name = provider_models.get(provider, args.openai_model)
        for dataset in datasets:
            for seed in seeds:
                examples = load_pilot_examples(dataset, args.subset_size, seed)
                rng = random.Random(rng_master.randint(0, 10**9))
                factory = generator_factory_for_mode(
                    True,
                    rng,
                    model_name,
                    args.temperature,
                    args.max_output_tokens,
                    args.timeout_seconds,
                    api_provider=provider,
                )
                for budget in budgets:
                    try:
                        strategies = build_frontier_strategies(
                            factory,
                            budget,
                            adaptive_grid,
                            rng,
                            use_openai_api=True,
                            include_selective_sc_hybrid_methods=True,
                            include_broad_diversity_aggregation_methods=True,
                        )
                        strategies = {k: v for k, v in strategies.items() if k in METHODS}
                        metrics, rows = evaluate_strategies_on_examples(examples, strategies)
                    except Exception as exc:  # noqa: BLE001
                        failed_runs.append(
                            {
                                "provider": provider,
                                "provider_model": model_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "reason": type(exc).__name__,
                                "error": str(exc)[:500],
                            }
                        )
                        continue

                    for method, m in metrics.items():
                        per_seed_method.append(
                            {
                                "provider": provider,
                                "provider_model": model_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "method": method,
                                "accuracy": float(m["accuracy"]),
                                "avg_actions": float(m["avg_actions"]),
                                "avg_expansions": float(m["avg_expansions"]),
                                "avg_verifications": float(m["avg_verifications"]),
                                "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                                "n_eval_examples": int(m["n_examples"]),
                            }
                        )

                    for r in rows:
                        if r["strategy"] not in METHODS:
                            continue
                        meta = r.get("metadata") or {}
                        per_example_rows.append(
                            {
                                "provider": provider,
                                "provider_model": model_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "example_id": r["example_id"],
                                "method": r["strategy"],
                                "is_correct": bool(r["is_correct"]),
                                "actions_used": int(r["actions_used"]),
                                "near_tie": bool(meta.get("near_tie", False)),
                                "disagreement": bool(meta.get("continuation_completion_disagree", False)),
                                "hard_case_active": bool(meta.get("hard_case_active", False)),
                                "answer_support_entropy": float(meta.get("answer_support_entropy", 0.0)),
                                "unique_answer_groups_seen": int(meta.get("unique_answer_groups_seen", 0)),
                                "group_support_fraction": float(meta.get("group_support_fraction", 0.0)),
                                "aggregation_used": bool(meta.get("aggregation_used", False)),
                                "forced_explore_rate": float(meta.get("forced_explore_rate", 0.0)),
                                "duplicate_penalty_applied_rate": float(meta.get("duplicate_penalty_applied_rate", 0.0)),
                                "mean_diversity_bonus_on_expand": float(meta.get("mean_diversity_bonus_on_expand", 0.0)),
                                "predicted_answer": meta.get("final_prediction"),
                            }
                        )

    by_method = defaultdict(list)
    by_dataset_method = defaultdict(list)
    by_provider_method = defaultdict(list)
    for row in per_seed_method:
        by_method[row["method"]].append(row["accuracy"])
        by_dataset_method[(row["dataset"], row["method"])].append(row["accuracy"])
        by_provider_method[(row["provider"], row["method"])].append(row["accuracy"])

    overall = {m: {"mean_accuracy_over_budgets": _mean(v), "seed_stability_std": _std(v)} for m, v in by_method.items()}

    per_dataset: dict[str, dict[str, dict[str, float]]] = {}
    for (ds, m), vals in by_dataset_method.items():
        per_dataset.setdefault(ds, {})[m] = {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}

    per_provider: dict[str, dict[str, dict[str, float]]] = {}
    for (provider, method), vals in by_provider_method.items():
        per_provider.setdefault(provider, {})[method] = {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}

    ranked_methods = sorted(overall.items(), key=lambda kv: kv[1]["mean_accuracy_over_budgets"], reverse=True)

    aligned = defaultdict(dict)
    for r in per_example_rows:
        key = (r["provider"], r["dataset"], r["seed"], r["budget"], r["example_id"])
        aligned[key][r["method"]] = r
    aligned_rows = [row for row in aligned.values() if all(m in row for m in METHODS)]

    hard_slice = {
        "near_tie": {m: _slice_acc(aligned_rows, m, "near_tie") for m in METHODS},
        "disagreement": {m: _slice_acc(aligned_rows, m, "disagreement") for m in METHODS},
        "hard_case_active": {m: _slice_acc(aligned_rows, m, "hard_case_active") for m in METHODS},
    }

    sc = overall.get("self_consistency_3", {}).get("mean_accuracy_over_budgets", 0.0)
    strong = overall.get("broad_diversity_aggregation_strong_v1", {}).get("mean_accuracy_over_budgets", 0.0)

    gap_to_sc = {
        method: float(sc - vals["mean_accuracy_over_budgets"])
        for method, vals in overall.items()
    }

    broad_rows = [r for r in per_example_rows if r["method"] == "broad_diversity_aggregation_v1"]
    broad_strong_rows = [r for r in per_example_rows if r["method"] == "broad_diversity_aggregation_strong_v1"]

    def _div_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
        return {
            "n_examples": len(rows),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in rows]),
            "mean_answer_support_entropy": _mean([float(r["answer_support_entropy"]) for r in rows]),
            "aggregation_used_rate": _bool_rate(rows, "aggregation_used"),
            "mean_group_support_fraction": _mean([float(r["group_support_fraction"]) for r in rows]),
            "mean_forced_explore_rate": _mean([float(r["forced_explore_rate"]) for r in rows]),
            "mean_duplicate_penalty_applied_rate": _mean([float(r["duplicate_penalty_applied_rate"]) for r in rows]),
            "mean_diversity_bonus_on_expand": _mean([float(r["mean_diversity_bonus_on_expand"]) for r in rows]),
            "low_diversity_realization_rate": float(
                sum(int(float(r["unique_answer_groups_seen"]) <= 1.0) for r in rows) / max(1, len(rows))
            ),
        }

    diversity_audit = {
        "broad_diversity_aggregation_v1": _div_summary(broad_rows),
        "broad_diversity_aggregation_strong_v1": _div_summary(broad_strong_rows),
    }

    residual_counts = Counter()
    residual_cases: list[dict[str, Any]] = []
    for row in aligned_rows:
        sc_row = row["self_consistency_3"]
        strong_row = row["broad_diversity_aggregation_strong_v1"]
        if bool(sc_row["is_correct"]) and not bool(strong_row["is_correct"]):
            diversity_materialized = int(strong_row.get("unique_answer_groups_seen", 0)) >= 2
            ranking_failed = diversity_materialized and float(strong_row.get("group_support_fraction", 0.0)) < 0.5
            agg_concentrated_wrong = diversity_materialized and float(strong_row.get("group_support_fraction", 0.0)) >= 0.75
            if not diversity_materialized:
                category = "insufficient_diversity_realized"
            elif ranking_failed:
                category = "value_ranking_error_despite_diversity"
            elif agg_concentrated_wrong:
                category = "aggregation_concentration_failure"
            else:
                category = "commit_timing_or_other"
            residual_counts.update([category])
            residual_cases.append(
                {
                    "provider": strong_row["provider"],
                    "dataset": strong_row["dataset"],
                    "seed": strong_row["seed"],
                    "budget": strong_row["budget"],
                    "example_id": strong_row["example_id"],
                    "ground_truth": None,
                    "self_consistency_3_answer": sc_row.get("predicted_answer"),
                    "broad_diversity_aggregation_strong_v1_answer": strong_row.get("predicted_answer"),
                    "diversity_materialized": diversity_materialized,
                    "aggregation_concentrated_incorrectly": bool(agg_concentrated_wrong),
                    "ranking_failed_despite_diversity": bool(ranking_failed),
                    "target_completion_or_commit_timing_issue": bool(category == "commit_timing_or_other"),
                    "residual_category": category,
                    "strong_unique_answer_groups_seen": strong_row.get("unique_answer_groups_seen"),
                    "strong_group_support_fraction": strong_row.get("group_support_fraction"),
                    "strong_answer_support_entropy": strong_row.get("answer_support_entropy"),
                }
            )

    aggregate_summary = {
        "overall_method_summary": overall,
        "ranked_methods": [{"method": m, **vals} for m, vals in ranked_methods],
        "gap_to_self_consistency_3": gap_to_sc,
        "broad_strong_vs_self_consistency_3": {
            "strong_minus_sc": float(strong - sc),
            "strong_beats_sc": bool(strong > sc),
        },
        "hard_slice_summary": hard_slice,
        "per_provider_summary": per_provider,
        "failed_runs": failed_runs,
        "n_aligned_examples": len(aligned_rows),
    }

    methods_compared = {
        "frozen_method_set": METHODS,
        "new_method_families_added": False,
        "family_focus": "broad_diversity_aggregation",
    }

    providers_and_models = {
        "providers_requested": providers,
        "providers_executed": sorted({r["provider"] for r in per_seed_method}),
        "model_by_provider": {p: provider_models.get(p) for p in providers},
        "decoding": {
            "temperature": args.temperature,
            "max_output_tokens": args.max_output_tokens,
            "timeout_seconds": args.timeout_seconds,
            "response_format": "json_object prompts via APIBranchGenerator",
        },
        "retry_behavior": {
            "openai_like_responses_retry_attempts": 4,
            "cohere_retry_attempts": 4,
            "retryable_http_codes": [408, 429, 500, 502, 503, 504],
            "backoff_seconds": "1.25 * (attempt + 1)",
        },
    }

    datasets_compared = {
        "datasets_requested": datasets,
        "datasets_with_successful_rows": sorted({r["dataset"] for r in per_seed_method}),
        "subset_size_per_dataset": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "notes": "Bounded real-model slice for feasibility and cost control.",
    }

    residual_taxonomy = {
        "categories": dict(residual_counts),
        "definitions": {
            "insufficient_diversity_realized": "Strong variant produced <=1 answer group when SC was correct and strong was wrong.",
            "value_ranking_error_despite_diversity": "Diversity existed but selected group support remained weak (<0.5).",
            "aggregation_concentration_failure": "Diversity existed but support concentrated heavily (>=0.75) on wrong path.",
            "commit_timing_or_other": "Residual errors not mapped to the first three dominant categories.",
        },
    }

    manifest = {
        "run_name": "broad_diversity_aggregation_real_model_confirmation_20260418",
        "timestamp_utc": run_started,
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "files": [
            "manifest.json",
            "methods_compared.json",
            "providers_and_models.json",
            "datasets_compared.json",
            "aggregate_comparison_summary.json",
            "per_dataset_tables.json",
            "activation_behavior_summary.json",
            "diversity_mechanism_audit.json",
            "residual_loss_taxonomy.json",
            "residual_loss_cases.json",
            "commands_assumptions_caveats.md",
            "raw_per_seed_method_rows.json",
            "raw_per_example_rows.json",
        ],
    }

    commands_md = [
        "# Commands, assumptions, and caveats",
        "",
        "## Command provenance",
        f"- user_passed_command: `{args.command_provenance or 'not_provided'}`",
        "- script: `scripts/run_broad_diversity_aggregation_real_model_confirmation_20260418.py`",
        "",
        "## Evaluation framing",
        "- Fixed method set frozen to five methods requested by user.",
        "- Real model generations are used for branch expand/verify operations.",
        "- Same budget-aware controller framing as prior frontier-based comparisons.",
        "",
        "## Caveats",
        "- This is a bounded API run (small subset per dataset, limited budgets) to control latency/cost.",
        "- Per-provider model quality scales are not directly comparable in absolute terms.",
        "- `ground_truth` is not embedded in per-example method rows because evaluator returns only correctness booleans.",
        "- Partial failures may occur due to provider-side timeouts/rate-limits; see failed_runs in aggregate summary.",
    ]

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "methods_compared.json", methods_compared)
    _write_json(out_dir / "providers_and_models.json", providers_and_models)
    _write_json(out_dir / "datasets_compared.json", datasets_compared)
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_summary)
    _write_json(out_dir / "per_dataset_tables.json", per_dataset)
    _write_json(
        out_dir / "activation_behavior_summary.json",
        {
            "hard_slice_summary": hard_slice,
            "activation_signals_present": ["near_tie", "disagreement", "hard_case_active"],
            "aligned_example_count": len(aligned_rows),
        },
    )
    _write_json(out_dir / "diversity_mechanism_audit.json", diversity_audit)
    _write_json(out_dir / "residual_loss_taxonomy.json", residual_taxonomy)
    _write_json(out_dir / "residual_loss_cases.json", residual_cases)
    _write_json(out_dir / "raw_per_seed_method_rows.json", per_seed_method)
    _write_json(out_dir / "raw_per_example_rows.json", per_example_rows)
    (out_dir / "commands_assumptions_caveats.md").write_text("\n".join(commands_md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
