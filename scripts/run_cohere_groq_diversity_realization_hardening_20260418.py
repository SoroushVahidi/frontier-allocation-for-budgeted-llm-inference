#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
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
    "broad_diversity_aggregation_v1",
    "broad_diversity_aggregation_strong_v1",
    "marginal_coverage_diversity_v1",
    "answer_group_coverage_floor_v1",
]
BROAD_METHODS = [m for m in METHODS if m != "self_consistency_3"]
ALLOWED_PROVIDERS = ["cohere", "groq"]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _provider_preflight(provider: str, model: str, api_key: str, timeout_seconds: int) -> tuple[bool, str]:
    try:
        if provider == "cohere":
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Return JSON {\"ok\":true}"}],
                "max_tokens": 20,
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
            "model": model,
            "messages": [{"role": "user", "content": "Return JSON {\"ok\":true}"}],
            "temperature": 0.1,
            "max_tokens": 20,
        }
        req = request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
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


def _failure_stage(meta: dict[str, Any]) -> str:
    if int(meta.get("unique_answer_groups_seen", 0)) <= 1:
        return "expansion"
    if float(meta.get("answer_group_margin", 0.0)) >= 0.55 and not bool(meta.get("is_correct", False)):
        return "aggregation"
    if float(meta.get("group_support_fraction", 0.0)) > 0.75 and not bool(meta.get("is_correct", False)):
        return "commit"
    return "ranking"


def main() -> None:
    p = argparse.ArgumentParser(description="Cohere/Groq real diversity hardening pass for broad family")
    p.add_argument("--providers", default="cohere,groq")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--groq-model", default="llama-3.3-70b-versatile")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,olympiadbench")
    p.add_argument("--subset-size", type=int, default=2)
    p.add_argument("--seeds", default="11")
    p.add_argument("--budgets", default="6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/cohere_groq_diversity_realization_hardening_20260418")
    args = p.parse_args()

    providers = _parse_str_list(args.providers)
    illegal = [p for p in providers if p not in ALLOWED_PROVIDERS]
    if illegal:
        raise ValueError(f"Only Cohere/Groq are allowed for this pass. Illegal providers={illegal}")
    datasets = _parse_str_list(args.datasets)
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    provider_models = {"cohere": args.cohere_model, "groq": args.groq_model}

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    run_started = datetime.now(timezone.utc).isoformat()
    rng_master = random.Random(20260418)

    per_seed_method: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for provider in providers:
        api_key = resolve_api_key_for_provider(provider)
        if not api_key:
            failures.append({"provider": provider, "reason": f"missing_{provider}_api_key"})
            continue

        model_name = provider_models[provider]
        ok, reason = _provider_preflight(provider, model_name, api_key, args.timeout_seconds)
        if not ok:
            failures.append({"provider": provider, "provider_model": model_name, "reason": "preflight_failed", "error": reason})
            continue

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
                            include_broad_diversity_aggregation_methods=True,
                            include_marginal_coverage_diversity_methods=True,
                        )
                        strategies = {k: v for k, v in strategies.items() if k in METHODS}
                        metrics, rows = evaluate_strategies_on_examples(examples, strategies)
                    except Exception as exc:  # noqa: BLE001
                        failures.append(
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
                                "n_eval_examples": int(m["n_examples"]),
                            }
                        )

                    for r in rows:
                        if r["strategy"] not in METHODS:
                            continue
                        meta = dict(r.get("metadata") or {})
                        meta["is_correct"] = bool(r["is_correct"])
                        per_example_rows.append(
                            {
                                "provider": provider,
                                "provider_model": model_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "example_id": str(r["example_id"]),
                                "method": r["strategy"],
                                "is_correct": bool(r["is_correct"]),
                                "prediction": r.get("metadata", {}).get("final_prediction"),
                                "ground_truth": next((ex.answer for ex in examples if str(ex.example_id) == str(r["example_id"])), None),
                                "unique_answer_groups_seen": int(meta.get("unique_answer_groups_seen", 0)),
                                "answer_support_entropy": float(meta.get("answer_support_entropy", 0.0)),
                                "group_support_fraction": float(meta.get("group_support_fraction", 0.0)),
                                "coverage_floor_forced_steps": int(meta.get("coverage_floor_forced_steps", 0)),
                                "coverage_floor_forced_rate": float(meta.get("coverage_floor_forced_rate", 0.0)),
                                "coverage_floor_enabled": bool(meta.get("coverage_floor_enabled", False)),
                                "forced_explore_rate": float(meta.get("forced_explore_rate", 0.0)),
                                "aggregation_used": bool(meta.get("aggregation_used", False)),
                                "answer_group_margin": float(meta.get("answer_group_margin", 0.0)),
                            }
                        )

    if not per_seed_method:
        raise RuntimeError(f"No successful evaluations. failures={failures}")

    by_method = defaultdict(list)
    by_dataset_method = defaultdict(list)
    by_provider_method = defaultdict(list)
    for row in per_seed_method:
        by_method[row["method"]].append(row["accuracy"])
        by_dataset_method[(row["dataset"], row["method"])].append(row["accuracy"])
        by_provider_method[(row["provider"], row["method"])].append(row["accuracy"])

    overall = {m: {"mean_accuracy": _mean(v), "seed_stability_std": _std(v)} for m, v in by_method.items()}
    best_broad_method = max(BROAD_METHODS, key=lambda m: overall.get(m, {}).get("mean_accuracy", -1.0))

    per_dataset = {
        ds: {m: {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)} for (d, m), vals in by_dataset_method.items() if d == ds}
        for ds in datasets
    }
    per_provider = {
        provider: {m: {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)} for (p, m), vals in by_provider_method.items() if p == provider}
        for provider in providers
    }

    per_example_by_method = defaultdict(list)
    for row in per_example_rows:
        per_example_by_method[row["method"]].append(row)

    diversity_diag: dict[str, dict[str, float]] = {}
    for method in METHODS:
        rows = per_example_by_method.get(method, [])
        diversity_diag[method] = {
            "realized_diversity_rate": _mean([1.0 if r["unique_answer_groups_seen"] >= 2 else 0.0 for r in rows]),
            "useful_answer_distinct_branch_rate": _mean([1.0 if r["unique_answer_groups_seen"] >= 2 and r["answer_support_entropy"] >= 0.25 else 0.0 for r in rows]),
            "low_diversity_realization_rate": _mean([1.0 if r["unique_answer_groups_seen"] <= 1 else 0.0 for r in rows]),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in rows]),
        }

    coverage_rows = per_example_by_method.get("answer_group_coverage_floor_v1", [])
    coverage_floor_summary = {
        "activation_rate_examples": _mean([1.0 if r["coverage_floor_forced_steps"] > 0 else 0.0 for r in coverage_rows]),
        "mean_forced_steps": _mean([float(r["coverage_floor_forced_steps"]) for r in coverage_rows]),
        "mean_forced_rate": _mean([float(r["coverage_floor_forced_rate"]) for r in coverage_rows]),
        "enabled_examples": int(sum(1 for r in coverage_rows if r["coverage_floor_enabled"])),
        "n_examples": int(len(coverage_rows)),
    }

    aligned = defaultdict(dict)
    for row in per_example_rows:
        k = (row["provider"], row["provider_model"], row["dataset"], row["seed"], row["budget"], row["example_id"])
        aligned[k][row["method"]] = row

    residual_cases: list[dict[str, Any]] = []
    residual_taxonomy = defaultdict(int)
    for k, pack in aligned.items():
        if "self_consistency_3" not in pack or best_broad_method not in pack:
            continue
        sc = pack["self_consistency_3"]
        ours = pack[best_broad_method]
        if sc["is_correct"] and not ours["is_correct"]:
            concentrated_early = bool(ours["group_support_fraction"] > 0.75 and ours["unique_answer_groups_seen"] <= 1)
            stage = _failure_stage(ours)
            residual_taxonomy[stage] += 1
            residual_cases.append(
                {
                    "dataset": ours["dataset"],
                    "provider": ours["provider"],
                    "provider_model": ours["provider_model"],
                    "example_id": ours["example_id"],
                    "ground_truth": ours["ground_truth"],
                    "sc_answer": sc["prediction"],
                    "our_answer": ours["prediction"],
                    "diversity_materialized": bool(ours["unique_answer_groups_seen"] >= 2),
                    "coverage_floor_activated": bool(ours.get("coverage_floor_forced_steps", 0) > 0),
                    "aggregation_concentrated_too_early": concentrated_early,
                    "failure_stage": stage,
                }
            )

    aggregate_summary = {
        "overall_mean_accuracy": overall,
        "best_broad_method": best_broad_method,
        "gap_to_self_consistency_3": float(overall[best_broad_method]["mean_accuracy"] - overall["self_consistency_3"]["mean_accuracy"]),
        "gap_vs_broad_diversity_aggregation_v1": float(overall[best_broad_method]["mean_accuracy"] - overall["broad_diversity_aggregation_v1"]["mean_accuracy"]),
        "realized_diversity_delta_vs_v1": float(
            diversity_diag["answer_group_coverage_floor_v1"]["realized_diversity_rate"] - diversity_diag["broad_diversity_aggregation_v1"]["realized_diversity_rate"]
        ),
        "useful_branch_rate_delta_vs_v1": float(
            diversity_diag["answer_group_coverage_floor_v1"]["useful_answer_distinct_branch_rate"]
            - diversity_diag["broad_diversity_aggregation_v1"]["useful_answer_distinct_branch_rate"]
        ),
    }

    run_finished = datetime.now(timezone.utc).isoformat()
    run_scale_summary = {
        "datasets": datasets,
        "providers": providers,
        "models": provider_models,
        "subset_size_per_dataset": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "successful_seed_level_rows": len(per_seed_method),
        "successful_example_level_rows": len(per_example_rows),
        "failed_runs": failures,
    }

    method_definition = {
        "method_name": "answer_group_coverage_floor_v1",
        "family": "broad_diversity_aggregation",
        "rule": "plausibility_gated_undercovered_group_forcing",
        "description": "Before concentration, force up to a bounded number of expansions toward plausible undercovered answer groups until minimum answer-group coverage is met.",
        "parameters": {
            "min_answer_groups_before_concentration": 2,
            "coverage_floor_min_actions": 2,
            "coverage_floor_max_actions": 7,
            "coverage_floor_plausibility_threshold": 0.46,
            "coverage_floor_max_forced_steps": 2,
        },
        "difference_vs_marginal_coverage": "Marginal-coverage reweights all priorities by profile novelty/overlap continuously; coverage-floor adds a bounded early-stage intervention that can override top priority only for plausible undercovered groups.",
    }

    manifest = {
        "run_name": "cohere_groq_diversity_realization_hardening_20260418",
        "run_started_utc": run_started,
        "run_finished_utc": run_finished,
        "required_outputs": [
            "manifest.json",
            "methods_compared.json",
            "providers_and_models.json",
            "datasets_compared.json",
            "method_definition.json",
            "run_scale_summary.json",
            "aggregate_comparison_summary.json",
            "per_dataset_tables.json",
            "per_provider_tables.json",
            "diversity_realization_diagnostics.json",
            "coverage_floor_activation_summary.json",
            "residual_loss_taxonomy.json",
            "residual_loss_cases.json",
            "commands_assumptions_caveats.md",
        ],
    }

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "methods_compared.json", {"methods": METHODS, "best_broad_method": best_broad_method})
    _write_json(
        out_dir / "providers_and_models.json",
        {
            "allowed_providers": ALLOWED_PROVIDERS,
            "providers_used": providers,
            "models": provider_models,
                "api_settings": {
                "temperature": args.temperature,
                "max_output_tokens": args.max_output_tokens,
                "timeout_seconds": args.timeout_seconds,
                "retry_policy": "No explicit retry loop in current APIBranchGenerator calls; failures are surfaced and recorded.",
                "failure_handling": "Per-provider preflight; run-level failures captured in failed_runs; continue on failure.",
            },
        },
    )
    _write_json(out_dir / "datasets_compared.json", {"datasets": datasets, "subset_size": args.subset_size})
    _write_json(out_dir / "method_definition.json", method_definition)
    _write_json(out_dir / "run_scale_summary.json", run_scale_summary)
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_summary)
    _write_json(out_dir / "per_dataset_tables.json", per_dataset)
    _write_json(out_dir / "per_provider_tables.json", per_provider)
    _write_json(out_dir / "diversity_realization_diagnostics.json", diversity_diag)
    _write_json(out_dir / "coverage_floor_activation_summary.json", coverage_floor_summary)
    _write_json(out_dir / "residual_loss_taxonomy.json", dict(residual_taxonomy))
    _write_json(out_dir / "residual_loss_cases.json", residual_cases)

    (out_dir / "commands_assumptions_caveats.md").write_text(
        "\n".join(
            [
                "# Commands, assumptions, caveats",
                "",
                "## Command run",
                f"- python scripts/run_cohere_groq_diversity_realization_hardening_20260418.py --providers {args.providers} --datasets {args.datasets} --subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}",
                "",
                "## Assumptions",
                "- Fresh real-model checks are restricted to Cohere and Groq only.",
                "- Evaluation slice is bounded; conclusions are directional but stronger than single-point smoke tests.",
                "",
                "## Caveats",
                "- Small subset and single seed limit certainty.",
                "- API provider noise and transient errors can alter tiny-slice rankings.",
                f"- Failed runs captured: {len(failures)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote outputs to {out_dir}")


if __name__ == "__main__":
    main()
