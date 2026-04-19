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
from urllib import error, request

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
BROAD_VARIANTS = ["broad_diversity_aggregation_v1", "broad_diversity_aggregation_strong_v1"]
ALLOWED_PROVIDERS = ["cohere", "gemini"]


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


def _provider_preflight(provider: str, model: str, api_key: str, timeout_seconds: int) -> tuple[bool, str]:
    try:
        if provider == "cohere":
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Return JSON {\"ok\":true}"}],
                "max_tokens": 24,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
            req = request.Request(
                "https://api.cohere.com/v2/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                _ = resp.read()
            return True, "ok"

        payload = {
            "contents": [{"parts": [{"text": "Return JSON {\"ok\": true}"}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 24, "responseMimeType": "application/json"},
        }
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            _ = resp.read()
        return True, "ok"
    except error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        return False, f"http_{exc.code}:{err_body[:300]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}:{str(exc)[:300]}"


def main() -> None:
    p = argparse.ArgumentParser(description="Cohere+Gemini real-model confirmation for broad diversity aggregation family")
    p.add_argument("--providers", default="cohere,gemini")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--gemini-model", default="gemini-2.0-flash")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=2)
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=160)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418")
    p.add_argument("--command-provenance", default="")
    args = p.parse_args()

    providers = _parse_str_list(args.providers)
    if not providers:
        raise ValueError("No providers configured.")
    illegal = [p for p in providers if p not in ALLOWED_PROVIDERS]
    if illegal:
        raise ValueError(f"Only Cohere/Gemini providers are allowed for this pass. Illegal providers: {illegal}")

    datasets = _parse_str_list(args.datasets)
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    provider_models = {"cohere": args.cohere_model, "gemini": args.gemini_model}

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    run_started = datetime.now(timezone.utc).isoformat()
    rng_master = random.Random(20260418)

    per_seed_method: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []

    ground_truth: dict[tuple[str, int, str], str] = {}

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

        model_name = provider_models[provider]
        ok, preflight_reason = _provider_preflight(provider, model_name, api_key, args.timeout_seconds)
        if not ok:
            failed_runs.append(
                {
                    "provider": provider,
                    "provider_model": model_name,
                    "dataset": None,
                    "seed": None,
                    "budget": None,
                    "reason": "preflight_failed",
                    "error": preflight_reason,
                }
            )
            continue

        for dataset in datasets:
            for seed in seeds:
                examples = load_pilot_examples(dataset, args.subset_size, seed)
                for ex in examples:
                    ground_truth[(dataset, seed, str(ex.example_id))] = str(ex.answer)

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
                        ex_id = str(r["example_id"])
                        gt = ground_truth.get((dataset, seed, ex_id))
                        per_example_rows.append(
                            {
                                "provider": provider,
                                "provider_model": model_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "example_id": ex_id,
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
                                "ground_truth": gt,
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
    ranked_methods = sorted(overall.items(), key=lambda kv: kv[1]["mean_accuracy_over_budgets"], reverse=True)

    per_dataset: dict[str, dict[str, dict[str, float]]] = {}
    for (dataset, method), vals in by_dataset_method.items():
        per_dataset.setdefault(dataset, {})[method] = {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}

    per_provider: dict[str, dict[str, dict[str, float]]] = {}
    for (provider, method), vals in by_provider_method.items():
        per_provider.setdefault(provider, {})[method] = {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}

    if any(m not in overall for m in METHODS):
        missing_methods = [m for m in METHODS if m not in overall]
        raise RuntimeError(f"Incomplete run: missing methods in output summary: {missing_methods}")

    # Best broad-variant selection (explicit, no ambiguity)
    v1_stats = overall["broad_diversity_aggregation_v1"]
    strong_stats = overall["broad_diversity_aggregation_strong_v1"]
    if v1_stats["mean_accuracy_over_budgets"] > strong_stats["mean_accuracy_over_budgets"]:
        main_variant = "broad_diversity_aggregation_v1"
        ablation_variant = "broad_diversity_aggregation_strong_v1"
        reason = "higher overall mean accuracy"
    elif strong_stats["mean_accuracy_over_budgets"] > v1_stats["mean_accuracy_over_budgets"]:
        main_variant = "broad_diversity_aggregation_strong_v1"
        ablation_variant = "broad_diversity_aggregation_v1"
        reason = "higher overall mean accuracy"
    elif v1_stats["seed_stability_std"] <= strong_stats["seed_stability_std"]:
        main_variant = "broad_diversity_aggregation_v1"
        ablation_variant = "broad_diversity_aggregation_strong_v1"
        reason = "tie on mean accuracy; selected lower seed_stability_std"
    else:
        main_variant = "broad_diversity_aggregation_strong_v1"
        ablation_variant = "broad_diversity_aggregation_v1"
        reason = "tie on mean accuracy; selected lower seed_stability_std"

    sc_acc = overall["self_consistency_3"]["mean_accuracy_over_budgets"]
    main_acc = overall[main_variant]["mean_accuracy_over_budgets"]

    aligned = defaultdict(dict)
    for r in per_example_rows:
        k = (r["provider"], r["dataset"], r["seed"], r["budget"], r["example_id"])
        aligned[k][r["method"]] = r
    aligned_rows = [row for row in aligned.values() if all(m in row for m in METHODS)]

    def _slice_acc(method: str, cond_key: str) -> float:
        vals = [int(row[method]["is_correct"]) for row in aligned_rows if bool(row[main_variant].get(cond_key, False))]
        return float(sum(vals) / len(vals)) if vals else 0.0

    hard_slice = {
        "near_tie": {m: _slice_acc(m, "near_tie") for m in METHODS},
        "disagreement": {m: _slice_acc(m, "disagreement") for m in METHODS},
        "hard_case_active": {m: _slice_acc(m, "hard_case_active") for m in METHODS},
    }

    def _div_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
        return {
            "n_examples": len(rows),
            "diversity_materialized_rate": float(sum(int(r["unique_answer_groups_seen"] >= 2) for r in rows) / max(1, len(rows))),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in rows]),
            "mean_answer_support_entropy": _mean([float(r["answer_support_entropy"]) for r in rows]),
            "aggregation_used_rate": _bool_rate(rows, "aggregation_used"),
            "mean_group_support_fraction": _mean([float(r["group_support_fraction"]) for r in rows]),
            "high_support_concentration_rate": float(
                sum(int(float(r["group_support_fraction"]) >= 0.75) for r in rows) / max(1, len(rows))
            ),
            "mean_forced_explore_rate": _mean([float(r["forced_explore_rate"]) for r in rows]),
            "forced_explore_active_rate": float(sum(int(float(r["forced_explore_rate"]) > 0.0) for r in rows) / max(1, len(rows))),
            "mean_duplicate_penalty_applied_rate": _mean([float(r["duplicate_penalty_applied_rate"]) for r in rows]),
            "duplicate_suppression_active_rate": float(
                sum(int(float(r["duplicate_penalty_applied_rate"]) > 0.0) for r in rows) / max(1, len(rows))
            ),
            "mean_diversity_bonus_on_expand": _mean([float(r["mean_diversity_bonus_on_expand"]) for r in rows]),
            "low_diversity_realization_rate": float(
                sum(int(float(r["unique_answer_groups_seen"]) <= 1.0) for r in rows) / max(1, len(rows))
            ),
        }

    diversity_by_method = {}
    for method in BROAD_VARIANTS:
        method_rows = [r for r in per_example_rows if r["method"] == method]
        diversity_by_method[method] = _div_summary(method_rows)

    diversity_by_provider = {}
    for provider in providers:
        p_rows = [r for r in per_example_rows if r["provider"] == provider and r["method"] == main_variant]
        diversity_by_provider[provider] = _div_summary(p_rows)

    # Residual-loss taxonomy: where SC beats best broad variant
    residual_counts = Counter()
    residual_cases = []
    for row in aligned_rows:
        sc_row = row["self_consistency_3"]
        main_row = row[main_variant]
        if bool(sc_row["is_correct"]) and not bool(main_row["is_correct"]):
            diversity_materialized = bool(main_row["unique_answer_groups_seen"] >= 2)
            commit_unstable = bool(0.45 <= float(main_row.get("group_support_fraction", 0.0)) <= 0.65)
            aggregation_wrong = bool(diversity_materialized and float(main_row.get("group_support_fraction", 0.0)) >= 0.75)
            ranking_failed = bool(diversity_materialized and float(main_row.get("group_support_fraction", 0.0)) < 0.5)
            if not diversity_materialized:
                category = "insufficient_diversity_realized"
            elif ranking_failed:
                category = "value_ranking_error_despite_diversity"
            elif aggregation_wrong:
                category = "aggregation_concentration_failure"
            elif commit_unstable:
                category = "commit_selection_instability"
            else:
                category = "other_or_mixed"
            residual_counts.update([category])
            residual_cases.append(
                {
                    "dataset": main_row["dataset"],
                    "example_id": main_row["example_id"],
                    "provider": main_row["provider"],
                    "provider_model": main_row["provider_model"],
                    "seed": main_row["seed"],
                    "budget": main_row["budget"],
                    "ground_truth": main_row.get("ground_truth"),
                    "self_consistency_3_answer": sc_row.get("predicted_answer"),
                    "broad_candidate": main_variant,
                    "broad_candidate_answer": main_row.get("predicted_answer"),
                    "diversity_materialized": diversity_materialized,
                    "commit_unstable": commit_unstable,
                    "aggregation_concentrated_on_wrong_answer": aggregation_wrong,
                    "ranking_failed_despite_diversity": ranking_failed,
                    "residual_category": category,
                }
            )

    # Family leadership stability
    provider_variant_winners = {}
    for provider, tbl in per_provider.items():
        v1 = tbl.get("broad_diversity_aggregation_v1", {}).get("mean_accuracy", 0.0)
        st = tbl.get("broad_diversity_aggregation_strong_v1", {}).get("mean_accuracy", 0.0)
        provider_variant_winners[provider] = (
            "broad_diversity_aggregation_v1"
            if v1 >= st
            else "broad_diversity_aggregation_strong_v1"
        )

    unique_winners = sorted(set(provider_variant_winners.values()))
    leadership_stable = len(unique_winners) == 1 and unique_winners[0] == main_variant

    aggregate_summary = {
        "overall_method_summary": overall,
        "method_ranking": [{"method": m, **vals} for m, vals in ranked_methods],
        "gap_to_self_consistency_3": {
            method: float(overall[method]["mean_accuracy_over_budgets"] - sc_acc)
            for method in METHODS
        },
        "gap_between_broad_variants": {
            "strong_minus_v1": float(strong_stats["mean_accuracy_over_budgets"] - v1_stats["mean_accuracy_over_budgets"]),
            "v1_minus_strong": float(v1_stats["mean_accuracy_over_budgets"] - strong_stats["mean_accuracy_over_budgets"]),
        },
        "main_broad_candidate_vs_sc": {
            "main_candidate": main_variant,
            "main_minus_sc": float(main_acc - sc_acc),
            "materially_challenges_sc_flag": bool(main_acc >= sc_acc - 0.01),
        },
        "family_leadership_stability": {
            "stable_across_providers": leadership_stable,
            "provider_variant_winners": provider_variant_winners,
            "note": "Leadership is marked unstable when provider-level winner disagrees with global winner.",
        },
        "hard_slice_summary": hard_slice,
        "n_aligned_examples": len(aligned_rows),
        "failed_runs": failed_runs,
    }

    variant_selection_summary = {
        "selected_main_candidate": main_variant,
        "ablation_variant": ablation_variant,
        "selection_rule": "higher overall mean accuracy over budgets; tie-break lower seed_stability_std",
        "selection_reason": reason,
        "overall_stats": {
            "broad_diversity_aggregation_v1": v1_stats,
            "broad_diversity_aggregation_strong_v1": strong_stats,
        },
        "leadership_stability": aggregate_summary["family_leadership_stability"],
    }

    run_scale_summary = {
        "providers_requested": providers,
        "providers_executed": sorted({r["provider"] for r in per_seed_method}),
        "models": {p: provider_models[p] for p in providers},
        "datasets": datasets,
        "subset_size_per_dataset": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "targeted_run_cells": len(providers) * len(datasets) * len(seeds) * len(budgets),
        "successful_run_cells": len({(r["provider"], r["dataset"], r["seed"], r["budget"]) for r in per_seed_method}),
        "total_per_seed_method_rows": len(per_seed_method),
        "total_per_example_rows": len(per_example_rows),
        "aligned_example_rows": len(aligned_rows),
    }

    providers_and_models = {
        "allowed_providers": ALLOWED_PROVIDERS,
        "providers_requested": providers,
        "providers_executed": run_scale_summary["providers_executed"],
        "model_by_provider": {p: provider_models.get(p) for p in providers},
        "explicit_exclusion": ["openai"],
        "decoding": {
            "temperature": args.temperature,
            "max_output_tokens": args.max_output_tokens,
            "timeout_seconds": args.timeout_seconds,
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
        "subset_size_per_dataset": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
    }

    methods_compared = {
        "frozen_method_set": METHODS,
        "new_method_families_added": False,
        "family_focus": "broad_diversity_aggregation",
    }

    residual_taxonomy = {
        "comparison_rule": f"Case included when self_consistency_3 is correct and {main_variant} is incorrect on aligned example.",
        "categories": dict(residual_counts),
        "definitions": {
            "insufficient_diversity_realized": "<=1 answer group realized for broad candidate.",
            "value_ranking_error_despite_diversity": "Diversity materialized but support fraction < 0.5.",
            "aggregation_concentration_failure": "Diversity materialized and support fraction >= 0.75 but still wrong.",
            "commit_selection_instability": "Support concentration in unstable mid-band (0.45..0.65).",
            "other_or_mixed": "Residual cases not mapped cleanly to dominant buckets.",
        },
    }

    diversity_mechanism_audit = {
        "method_level": diversity_by_method,
        "provider_level_for_selected_main_variant": {
            "main_variant": main_variant,
            "providers": diversity_by_provider,
        },
        "simulator_comparison_note": {
            "status": "qualitative_only",
            "statement": "Real-model diversity behavior should be interpreted against prior simulator confirmation as directional due bounded real scale.",
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
            "raw_per_seed_method_rows.json",
            "raw_per_example_rows.json",
        ],
    }

    commands_md = [
        "# Commands, assumptions, and caveats",
        "",
        "## Command provenance",
        f"- user_passed_command: `{args.command_provenance or 'not_provided'}`",
        "- script: `scripts/run_broad_diversity_aggregation_cohere_gemini_confirmation_20260418.py`",
        "",
        "## Explicit provider policy",
        "- OpenAI API was not used in this pass.",
        "- Providers are restricted to Cohere and Gemini only.",
        "",
        "## Caveats",
        "- This is bounded real-model evidence: larger than the tiny one-example pass, but still not paper-grade scale.",
        "- Provider-level behaviors are not directly comparable as a pure model-quality ranking.",
        "- Residual categories use deterministic heuristics from saved metadata; they are diagnostic rather than causal proof.",
        "",
        "## Retry/timeout behavior",
        "- Both Cohere and Gemini calls use timeout control and 4-attempt retry for transient HTTP/network failures.",
    ]

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "methods_compared.json", methods_compared)
    _write_json(out_dir / "providers_and_models.json", providers_and_models)
    _write_json(out_dir / "datasets_compared.json", datasets_compared)
    _write_json(out_dir / "run_scale_summary.json", run_scale_summary)
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_summary)
    _write_json(out_dir / "per_dataset_tables.json", per_dataset)
    _write_json(out_dir / "per_provider_tables.json", per_provider)
    _write_json(out_dir / "variant_selection_summary.json", variant_selection_summary)
    _write_json(out_dir / "diversity_mechanism_audit.json", diversity_mechanism_audit)
    _write_json(out_dir / "residual_loss_taxonomy.json", residual_taxonomy)
    _write_json(out_dir / "residual_loss_cases.json", residual_cases)
    _write_json(out_dir / "raw_per_seed_method_rows.json", per_seed_method)
    _write_json(out_dir / "raw_per_example_rows.json", per_example_rows)
    (out_dir / "commands_assumptions_caveats.md").write_text("\n".join(commands_md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
