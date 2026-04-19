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


def _bool_rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return float(sum(int(bool(r.get(key, False))) for r in rows) / len(rows))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _slice_acc(aligned_rows: list[dict[str, dict[str, Any]]], method: str, cond_key: str) -> float:
    vals = [
        int(row[method]["is_correct"])
        for row in aligned_rows
        if bool(row["selective_sc_hybrid_v1"].get(cond_key, False))
    ]
    return float(sum(vals) / len(vals)) if vals else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description="Real-model confirmation for broad diversity aggregation family (Cohere+Gemini)")
    p.add_argument("--providers", default="cohere,gemini")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--gemini-model", default="gemini-2.0-flash")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=2)
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418")
    p.add_argument("--command-provenance", default="")
    args = p.parse_args()

    providers = _parse_str_list(args.providers)
    banned = {p for p in providers if p == "openai"}
    if banned:
        raise ValueError("OpenAI provider is not allowed for this sweep.")

    datasets = _parse_str_list(args.datasets)
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    provider_models = {
        "cohere": args.cohere_model,
        "gemini": args.gemini_model,
    }

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    run_started = datetime.now(timezone.utc).isoformat()
    rng_master = random.Random(20260418)

    per_seed_method: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []
    run_events: list[dict[str, Any]] = []

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

        model_name = provider_models.get(provider)
        if not model_name:
            failed_runs.append(
                {
                    "provider": provider,
                    "dataset": None,
                    "seed": None,
                    "budget": None,
                    "reason": "missing_model_for_provider",
                }
            )
            continue

        for dataset in datasets:
            for seed in seeds:
                examples = load_pilot_examples(dataset, args.subset_size, seed)
                answer_by_example = {ex.example_id: ex.answer for ex in examples}
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
                    run_events.append(
                        {
                            "provider": provider,
                            "provider_model": model_name,
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "subset_size": len(examples),
                        }
                    )
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
                        ex_id = r["example_id"]
                        per_example_rows.append(
                            {
                                "provider": provider,
                                "provider_model": model_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "example_id": ex_id,
                                "ground_truth": answer_by_example.get(ex_id),
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
    by_provider_dataset_method = defaultdict(list)

    for row in per_seed_method:
        by_method[row["method"]].append(row["accuracy"])
        by_dataset_method[(row["dataset"], row["method"])].append(row["accuracy"])
        by_provider_method[(row["provider"], row["method"])].append(row["accuracy"])
        by_provider_dataset_method[(row["provider"], row["dataset"], row["method"])].append(row["accuracy"])

    overall = {m: {"mean_accuracy_over_budgets": _mean(v), "seed_stability_std": _std(v)} for m, v in by_method.items()}
    ranked_methods = sorted(overall.items(), key=lambda kv: kv[1]["mean_accuracy_over_budgets"], reverse=True)

    per_dataset: dict[str, dict[str, dict[str, float]]] = {}
    for (ds, m), vals in by_dataset_method.items():
        per_dataset.setdefault(ds, {})[m] = {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}

    per_provider: dict[str, dict[str, dict[str, float]]] = {}
    for (provider, method), vals in by_provider_method.items():
        per_provider.setdefault(provider, {})[method] = {
            "mean_accuracy": _mean(vals),
            "seed_stability_std": _std(vals),
        }

    per_provider_dataset: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for (provider, dataset, method), vals in by_provider_dataset_method.items():
        per_provider_dataset.setdefault(provider, {}).setdefault(dataset, {})[method] = {
            "mean_accuracy": _mean(vals),
            "seed_stability_std": _std(vals),
        }

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
    v1 = overall.get("broad_diversity_aggregation_v1", {}).get("mean_accuracy_over_budgets", 0.0)
    strong = overall.get("broad_diversity_aggregation_strong_v1", {}).get("mean_accuracy_over_budgets", 0.0)
    best_broad = "broad_diversity_aggregation_strong_v1" if strong > v1 else "broad_diversity_aggregation_v1"

    gap_to_sc = {method: float(vals["mean_accuracy_over_budgets"] - sc) for method, vals in overall.items()}

    broad_rows = [r for r in per_example_rows if r["method"] == "broad_diversity_aggregation_v1"]
    broad_strong_rows = [r for r in per_example_rows if r["method"] == "broad_diversity_aggregation_strong_v1"]

    def _div_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
        n = len(rows)
        return {
            "n_examples": n,
            "diversity_materialized_rate": float(sum(int(r["unique_answer_groups_seen"] >= 2) for r in rows) / max(1, n)),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in rows]),
            "mean_answer_support_entropy": _mean([float(r["answer_support_entropy"]) for r in rows]),
            "aggregation_used_rate": _bool_rate(rows, "aggregation_used"),
            "mean_group_support_fraction": _mean([float(r["group_support_fraction"]) for r in rows]),
            "support_concentration_high_rate": float(sum(int(float(r["group_support_fraction"]) >= 0.75) for r in rows) / max(1, n)),
            "mean_forced_explore_rate": _mean([float(r["forced_explore_rate"]) for r in rows]),
            "mean_duplicate_penalty_applied_rate": _mean([float(r["duplicate_penalty_applied_rate"]) for r in rows]),
            "mean_diversity_bonus_on_expand": _mean([float(r["mean_diversity_bonus_on_expand"]) for r in rows]),
            "low_diversity_realization_rate": float(
                sum(int(float(r["unique_answer_groups_seen"]) <= 1.0) for r in rows) / max(1, n)
            ),
        }

    diversity_audit = {
        "broad_diversity_aggregation_v1": _div_summary(broad_rows),
        "broad_diversity_aggregation_strong_v1": _div_summary(broad_strong_rows),
    }

    provider_diversity: dict[str, dict[str, dict[str, float]]] = {}
    for provider in sorted({r["provider"] for r in per_example_rows}):
        provider_diversity[provider] = {
            "broad_diversity_aggregation_v1": _div_summary(
                [r for r in broad_rows if r["provider"] == provider]
            ),
            "broad_diversity_aggregation_strong_v1": _div_summary(
                [r for r in broad_strong_rows if r["provider"] == provider]
            ),
        }

    residual_counts = Counter()
    residual_cases: list[dict[str, Any]] = []
    for row in aligned_rows:
        sc_row = row["self_consistency_3"]
        best_row = row[best_broad]
        if bool(sc_row["is_correct"]) and not bool(best_row["is_correct"]):
            diversity_materialized = int(best_row.get("unique_answer_groups_seen", 0)) >= 2
            ranking_failed = diversity_materialized and float(best_row.get("group_support_fraction", 0.0)) < 0.5
            agg_concentrated_wrong = diversity_materialized and float(best_row.get("group_support_fraction", 0.0)) >= 0.75
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
                    "dataset": best_row["dataset"],
                    "example_id": best_row["example_id"],
                    "provider": best_row["provider"],
                    "provider_model": best_row["provider_model"],
                    "ground_truth": best_row.get("ground_truth"),
                    "self_consistency_3_answer": sc_row.get("predicted_answer"),
                    "broad_candidate_method": best_broad,
                    "broad_candidate_answer": best_row.get("predicted_answer"),
                    "diversity_materialized": diversity_materialized,
                    "commit_unstable": bool(category == "commit_timing_or_other"),
                    "aggregation_concentrated_on_wrong_answer": bool(agg_concentrated_wrong),
                    "ranking_failed_despite_diversity": bool(ranking_failed),
                    "residual_category": category,
                    "unique_answer_groups_seen": best_row.get("unique_answer_groups_seen"),
                    "group_support_fraction": best_row.get("group_support_fraction"),
                    "answer_support_entropy": best_row.get("answer_support_entropy"),
                }
            )

    variant_margin = float(strong - v1)
    variant_wins = {
        "broad_diversity_aggregation_v1": 0,
        "broad_diversity_aggregation_strong_v1": 0,
        "ties": 0,
    }
    for row in aligned_rows:
        v1_correct = bool(row["broad_diversity_aggregation_v1"]["is_correct"])
        strong_correct = bool(row["broad_diversity_aggregation_strong_v1"]["is_correct"])
        if v1_correct and not strong_correct:
            variant_wins["broad_diversity_aggregation_v1"] += 1
        elif strong_correct and not v1_correct:
            variant_wins["broad_diversity_aggregation_strong_v1"] += 1
        else:
            variant_wins["ties"] += 1

    variant_selection_summary = {
        "main_candidate": best_broad,
        "ablation_variant": "broad_diversity_aggregation_strong_v1" if best_broad.endswith("_v1") else "broad_diversity_aggregation_v1",
        "selection_basis": "higher overall mean accuracy over budgets; tie-break by lower seed_stability_std",
        "overall_mean_accuracy": {
            "broad_diversity_aggregation_v1": v1,
            "broad_diversity_aggregation_strong_v1": strong,
        },
        "mean_accuracy_margin_strong_minus_v1": variant_margin,
        "variant_head_to_head_counts": variant_wins,
        "leadership_stability": "stable" if abs(variant_margin) >= 0.03 else "variant_unstable",
    }

    aggregate_summary = {
        "overall_method_summary": overall,
        "ranked_methods": [{"method": m, **vals} for m, vals in ranked_methods],
        "gap_to_self_consistency_3": gap_to_sc,
        "broad_best_candidate": best_broad,
        "broad_best_candidate_minus_sc": float(overall.get(best_broad, {}).get("mean_accuracy_over_budgets", 0.0) - sc),
        "v1_minus_strong": float(v1 - strong),
        "hard_slice_summary": hard_slice,
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
            "cohere_retry_attempts": 4,
            "gemini_retry_attempts": 4,
            "retryable_http_codes": [408, 429, 500, 502, 503, 504],
            "backoff_seconds": "1.25 * (attempt + 1)",
        },
    }

    datasets_compared = {
        "datasets_requested": datasets,
        "datasets_with_successful_rows": sorted({r["dataset"] for r in per_seed_method}),
    }

    run_scale_summary = {
        "subset_size_per_dataset": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "providers": providers,
        "methods": METHODS,
        "planned_provider_dataset_seed_budget_cells": len(providers) * len(datasets) * len(seeds) * len(budgets),
        "executed_provider_dataset_seed_budget_cells": len(run_events),
        "successful_method_metric_rows": len(per_seed_method),
        "successful_example_method_rows": len(per_example_rows),
        "aligned_example_count": len(aligned_rows),
        "failed_cells": len(failed_runs),
    }

    per_provider_tables = {
        "per_provider_method": per_provider,
        "per_provider_dataset_method": per_provider_dataset,
    }

    residual_taxonomy = {
        "categories": dict(residual_counts),
        "definitions": {
            "insufficient_diversity_realized": "Best broad candidate produced <=1 answer group when SC was correct and broad candidate was wrong.",
            "value_ranking_error_despite_diversity": "Diversity existed but selected group support remained weak (<0.5).",
            "aggregation_concentration_failure": "Diversity existed but support concentrated heavily (>=0.75) on wrong path.",
            "commit_timing_or_other": "Residual errors not mapped to the first three dominant categories.",
        },
    }

    manifest = {
        "run_name": "broad_diversity_aggregation_cohere_gemini_confirmation_20260418",
        "timestamp_utc": run_started,
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "files": [
            "manifest.json",
            "methods_compared.json",
            "providers_and_models.json",
            "datasets_compared.json",
            "run_scale_summary.json",
            "aggregate_comparison_summary.json",
            "per_dataset_tables.json",
            "per_provider_tables.json",
            "variant_selection_summary.json",
            "diversity_mechanism_audit.json",
            "residual_loss_taxonomy.json",
            "residual_loss_cases.json",
            "commands_assumptions_caveats.md",
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
        "- Real-model generations are used for branch expand/verify operations.",
        "- Providers restricted to Cohere and Gemini only; OpenAI explicitly excluded.",
        "",
        "## Caveats",
        "- This is a bounded API run (small subset per dataset, limited budgets) to control latency/cost.",
        "- Gemini wrapper now uses 4-attempt retry behavior aligned with the same retryable HTTP status set.",
        "- Partial failures may occur due to provider-side timeouts/rate-limits; see failed_runs in aggregate summary.",
    ]

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "methods_compared.json", methods_compared)
    _write_json(out_dir / "providers_and_models.json", providers_and_models)
    _write_json(out_dir / "datasets_compared.json", datasets_compared)
    _write_json(out_dir / "run_scale_summary.json", run_scale_summary)
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_summary)
    _write_json(out_dir / "per_dataset_tables.json", per_dataset)
    _write_json(out_dir / "per_provider_tables.json", per_provider_tables)
    _write_json(out_dir / "variant_selection_summary.json", variant_selection_summary)
    _write_json(
        out_dir / "diversity_mechanism_audit.json",
        {
            "overall": diversity_audit,
            "by_provider": provider_diversity,
            "simulator_comparison_note": "Real-model diversity stability should be compared against prior simulator confirmation artifacts manually.",
        },
    )
    _write_json(out_dir / "residual_loss_taxonomy.json", residual_taxonomy)
    _write_json(out_dir / "residual_loss_cases.json", residual_cases)
    (out_dir / "commands_assumptions_caveats.md").write_text("\n".join(commands_md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
