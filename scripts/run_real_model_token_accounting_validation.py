#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples, resolve_api_key_for_provider
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

STRICT_F3 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
STRICT_GATE1_CAP_K6 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control"

METHODS: dict[str, dict[str, Any]] = {
    "strict_f3": {"runtime": STRICT_F3, "enable_output_repair": True},
    "strict_gate1_cap_k6": {"runtime": STRICT_GATE1_CAP_K6, "enable_output_repair": True},
    "external_l1_max": {"runtime": "external_l1_max", "enable_output_repair": True},
}
SUPPORTED_PROVIDERS = {"openai", "cohere"}


@dataclass(frozen=True)
class CaseKey:
    provider: str
    dataset: str
    seed: int
    budget: int
    example_id: str
    method: str


class ObservedGenerator:
    def __init__(self, base: APIBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, Any] = {}

    def init_branch(self, branch_id: str) -> Any:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        return b

    def expand(self, branch: Any, question: str, gold_answer: str) -> Any:
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: Any, question: str) -> Any:
        return self.base.verify(branch, question)

    def prune(self, branch: Any) -> Any:
        return self.base.prune(branch)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Appendix real-model token-accounting validation package (single or cross-provider)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--providers", default="openai", help="Comma-separated providers, e.g. openai,cohere")
    p.add_argument("--provider", default="", help="Backward-compatible single-provider alias.")
    p.add_argument("--model", default="", help="Optional global model override for all providers.")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--subset-size", type=int, default=5)
    p.add_argument("--methods", default="strict_f3,strict_gate1_cap_k6,external_l1_max")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--input-cost-per-1k", type=float, default=-1.0)
    p.add_argument("--output-cost-per-1k", type=float, default=-1.0)
    p.add_argument("--skip-doc-write", action="store_true")
    return p.parse_args()


def parse_csv_list(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_csv_ints(text: str) -> list[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def provider_model(provider: str, args: argparse.Namespace) -> str:
    if args.model:
        return args.model
    if provider == "openai":
        return args.openai_model
    if provider == "cohere":
        return args.cohere_model
    raise ValueError(f"Unsupported provider: {provider}")


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return len([tok for tok in str(text).strip().split() if tok])


def mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if fieldnames is None:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def classify(result: Any, final_nodes: list[dict[str, Any]], dataset: str, gold_raw: str, enable_output_repair: bool) -> dict[str, Any]:
    md = result.metadata or {}
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=md.get("selected_group"),
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    surfaced_can = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset=dataset)
    gold_can = canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(surfaced_can == gold_can and surfaced_can is not None)
    return {"exact_match": int(correct)}


def row_key(row: dict[str, Any]) -> CaseKey:
    return CaseKey(
        provider=str(row["provider"]),
        dataset=str(row["dataset"]),
        seed=int(row["seed"]),
        budget=int(row["budget"]),
        example_id=str(row["example_id"]),
        method=str(row["method"]),
    )


def summarize(rows: list[dict[str, Any]], group_keys: list[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        buckets[tuple(r[k] for k in group_keys)].append(r)
    out: list[dict[str, Any]] = []
    for key, grp in sorted(buckets.items(), key=lambda kv: kv[0]):
        prefix = {group_keys[i]: key[i] for i in range(len(group_keys))}
        valid_costs = [float(x.get("estimated_api_cost_usd", 0)) for x in grp if x.get("estimated_api_cost_usd") not in ("NA", None, "")]
        out.append(
            {
                **prefix,
                "n": len(grp),
                "accuracy": mean([float(x.get("exact_match", 0)) for x in grp]),
                "mean_actions": mean([float(x.get("actions_used", 0)) for x in grp]),
                "mean_expansions": mean([float(x.get("expansions", 0)) for x in grp]),
                "mean_estimated_input_tokens": mean([float(x.get("estimated_input_tokens", 0)) for x in grp]),
                "mean_estimated_output_tokens": mean([float(x.get("estimated_output_tokens", 0)) for x in grp]),
                "mean_estimated_total_tokens": mean([float(x.get("estimated_total_tokens", 0)) for x in grp]),
                "mean_latency_seconds": mean([float(x.get("latency_seconds", 0)) for x in grp]),
                "mean_estimated_api_cost_usd": mean(valid_costs) if valid_costs else "NA",
                "cost_reporting": "configured" if valid_costs else "NA",
            }
        )
    return out


def build_rows_for_provider(
    *,
    provider: str,
    model: str,
    datasets: list[str],
    budgets: list[int],
    seeds: list[int],
    methods: list[str],
    subset_size: int,
    execute_real: bool,
    args: argparse.Namespace,
    done: set[CaseKey],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    api_key = resolve_api_key_for_provider(provider)

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, subset_size, seed)
            for budget in budgets:
                rng = random.Random(1000003 * seed + 97 * budget + len(dataset) + len(provider))

                def factory() -> Any:
                    return ObservedGenerator(
                        APIBranchGenerator(
                            provider=provider,
                            api_key=api_key,
                            model=model,
                            temperature=args.temperature,
                            max_tokens=args.max_output_tokens,
                            timeout_seconds=args.timeout_seconds,
                        )
                    )

                specs = build_frontier_strategies(
                    factory,
                    budget,
                    [1],
                    rng,
                    use_openai_api=execute_real,
                    include_broad_diversity_aggregation_methods=True,
                    include_external_l1_baseline=True,
                    include_external_s1_baseline=True,
                )

                for ex in examples:
                    for method in methods:
                        case = CaseKey(provider=provider, dataset=dataset, seed=seed, budget=budget, example_id=str(ex.example_id), method=method)
                        if case in done:
                            continue
                        cfg = METHODS[method]
                        runtime = str(cfg["runtime"])
                        runtime_present = runtime in specs
                        base_row = {
                            "provider": provider,
                            "model": model,
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": str(ex.example_id),
                            "method": method,
                            "runtime_method": runtime,
                            "mode": "real_api" if execute_real else "dry_run",
                            "status": "ok" if (execute_real and runtime_present) else "dry_run_skipped",
                        }
                        if not runtime_present:
                            rows.append({**base_row, "status": "runtime_missing", "error": "runtime_missing_in_specs"})
                            continue
                        if not execute_real:
                            q_tokens = estimate_tokens(ex.question)
                            est_in = (budget + 1) * (q_tokens + 40)
                            est_out = max(1, budget) * 24
                            rows.append(
                                {
                                    **base_row,
                                    "exact_match": "NA",
                                    "actions_used": budget,
                                    "expansions": "NA",
                                    "estimated_input_tokens": est_in,
                                    "estimated_output_tokens": est_out,
                                    "estimated_total_tokens": est_in + est_out,
                                    "latency_seconds": "NA",
                                    "estimated_api_cost_usd": "NA",
                                }
                            )
                            continue

                        t0 = time.perf_counter()
                        result = specs[runtime].run(ex.question, ex.answer)
                        latency = time.perf_counter() - t0
                        obs = specs[runtime].generator
                        final_nodes = []
                        if hasattr(obs, "registry"):
                            for _, branch in sorted(obs.registry.items(), key=lambda kv: kv[0]):
                                reasoning_text = "\n".join(str(x) for x in getattr(branch, "steps", [])) if getattr(branch, "steps", None) else ""
                                pred = branch.predicted_answer
                                pred_norm = normalize_answer_text(str(pred) if pred is not None else None).get("normalized_answer")
                                final_nodes.append(
                                    {
                                        "branch_id": branch.branch_id,
                                        "reasoning_text": reasoning_text,
                                        "predicted_answer": pred,
                                        "predicted_answer_normalized": pred_norm,
                                    }
                                )
                        cls = classify(result, final_nodes, dataset, str(ex.answer), bool(cfg["enable_output_repair"]))
                        md = result.metadata or {}
                        q_tokens = estimate_tokens(ex.question)
                        est_input_tokens = int((int(result.expansions) + int(result.verifications) + 1) * (q_tokens + 40))
                        est_output_tokens = int(
                            md.get(
                                "total_generated_tokens_estimate",
                                sum(estimate_tokens(n.get("reasoning_text")) + estimate_tokens(n.get("predicted_answer")) for n in final_nodes),
                            )
                        )
                        est_total = est_input_tokens + est_output_tokens
                        if args.input_cost_per_1k > 0 and args.output_cost_per_1k > 0:
                            est_cost = (est_input_tokens / 1000.0) * args.input_cost_per_1k + (est_output_tokens / 1000.0) * args.output_cost_per_1k
                        else:
                            est_cost = "NA"
                        rows.append(
                            {
                                **base_row,
                                "exact_match": int(cls["exact_match"]),
                                "actions_used": int(result.actions_used),
                                "expansions": int(result.expansions),
                                "estimated_input_tokens": est_input_tokens,
                                "estimated_output_tokens": est_output_tokens,
                                "estimated_total_tokens": est_total,
                                "latency_seconds": round(float(latency), 6),
                                "estimated_api_cost_usd": est_cost,
                            }
                        )
    return rows


def main() -> None:
    args = parse_args()
    providers = parse_csv_list(args.providers)
    if args.provider:
        providers = [args.provider.strip()]
    providers = [p.lower() for p in providers]
    invalid_providers = [p for p in providers if p not in SUPPORTED_PROVIDERS]
    if invalid_providers:
        raise ValueError(f"Unsupported provider(s): {invalid_providers}. Supported={sorted(SUPPORTED_PROVIDERS)}")

    datasets = parse_csv_list(args.datasets)
    budgets = parse_csv_ints(args.budgets)
    seeds = parse_csv_ints(args.seeds)
    methods = parse_csv_list(args.methods)
    invalid_methods = [m for m in methods if m not in METHODS]
    if invalid_methods:
        raise ValueError(f"Unknown methods: {invalid_methods}. Allowed: {sorted(METHODS)}")

    is_cross_provider = len(providers) > 1
    artifact_family = "cross_provider_real_model_token_accounting_validation" if is_cross_provider else "real_model_token_accounting_validation"
    out_dir = REPO_ROOT / args.output_root / f"{artifact_family}_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    per_case_path = out_dir / "per_case_results.csv"

    existing_rows = read_csv(per_case_path) if args.resume else []
    done = {row_key(r) for r in existing_rows}
    all_rows: list[dict[str, Any]] = [dict(r) for r in existing_rows]

    provider_status: list[dict[str, Any]] = []
    provider_models: dict[str, str] = {}
    for provider in providers:
        model = provider_model(provider, args)
        provider_models[provider] = model
        api_key_present = bool(resolve_api_key_for_provider(provider))
        execute_real = api_key_present and (not args.dry_run)
        new_rows = build_rows_for_provider(
            provider=provider,
            model=model,
            datasets=datasets,
            budgets=budgets,
            seeds=seeds,
            methods=methods,
            subset_size=args.subset_size,
            execute_real=execute_real,
            args=args,
            done=done,
        )
        all_rows.extend(new_rows)
        provider_status.append(
            {
                "provider": provider,
                "model": model,
                "api_key_present": api_key_present,
                "mode": "real_api" if execute_real else "dry_run",
                "new_rows": len(new_rows),
            }
        )

    all_rows = sorted(
        all_rows,
        key=lambda r: (
            str(r.get("provider")),
            str(r.get("dataset")),
            str(r.get("seed")),
            str(r.get("budget")),
            str(r.get("example_id")),
            str(r.get("method")),
        ),
    )

    fieldnames = [
        "provider",
        "model",
        "dataset",
        "seed",
        "budget",
        "example_id",
        "method",
        "runtime_method",
        "mode",
        "status",
        "error",
        "exact_match",
        "actions_used",
        "expansions",
        "estimated_input_tokens",
        "estimated_output_tokens",
        "estimated_total_tokens",
        "latency_seconds",
        "estimated_api_cost_usd",
    ]
    write_csv(per_case_path, all_rows, fieldnames=fieldnames)

    valid_rows = [r for r in all_rows if str(r.get("status")) == "ok" and str(r.get("exact_match")) not in {"NA", "", "None"}]
    summary_pb = summarize(valid_rows, ["provider", "method", "budget"])
    summary_pm = summarize(valid_rows, ["provider", "method"])

    if is_cross_provider:
        summary_budget_name = "summary_by_provider_method_budget.csv"
        summary_method_name = "summary_by_provider_method.csv"
    else:
        summary_budget_name = "summary_by_method_budget.csv"
        summary_method_name = "summary_by_method.csv"

    write_csv(out_dir / summary_budget_name, summary_pb)
    write_csv(out_dir / summary_method_name, summary_pm)

    subset_note = "subset_size=5 requested" if args.subset_size >= 5 else "subset_size fallback used (<5)"
    status_lines = [
        f"# {artifact_family} status",
        "",
        f"- Timestamp: `{args.timestamp}`",
        f"- Providers: `{providers}`",
        f"- Provider models: `{provider_models}`",
        f"- Datasets: `{datasets}`",
        f"- Budgets: `{budgets}`",
        f"- Seeds: `{seeds}`",
        f"- Methods: `{methods}`",
        f"- Sample policy: `{subset_note}`",
        "",
        "## Provider execution mode",
    ]
    for row in provider_status:
        status_lines.append(
            f"- {row['provider']}: mode={row['mode']}, api_key_present={row['api_key_present']}, model={row['model']}, new_rows={row['new_rows']}"
        )
    status_lines.extend(
        [
            "",
            "## Scope and caveats",
            "- This package is appendix/supporting evidence and does not replace primary matched-surface simulation evidence.",
            "- The comparison contract remains primarily action-budget matched.",
            "- Token/latency/cost diagnostics are included to address reviewer accounting concerns.",
            "- Cost is NA unless explicit per-1K token prices are configured.",
            "- Strict-F3 vs Strict-Gate1-Cap-K6 should not be overclaimed unless larger-sample evidence is strong and stable.",
        ]
    )
    (out_dir / "STATUS.md").write_text("\n".join(status_lines) + "\n", encoding="utf-8")

    outputs = {
        "manifest": "manifest.json",
        "per_case_results": "per_case_results.csv",
        "status": "STATUS.md",
    }
    outputs["summary_by_provider_method_budget" if is_cross_provider else "summary_by_method_budget"] = summary_budget_name
    outputs["summary_by_provider_method" if is_cross_provider else "summary_by_method"] = summary_method_name

    manifest = {
        "artifact_family": artifact_family,
        "timestamp": args.timestamp,
        "providers": providers,
        "provider_models": provider_models,
        "datasets": datasets,
        "budgets": budgets,
        "seeds": seeds,
        "subset_size": args.subset_size,
        "methods": methods,
        "dry_run_requested": bool(args.dry_run),
        "resume": bool(args.resume),
        "provider_status": provider_status,
        "cost_pricing": {
            "input_cost_per_1k": args.input_cost_per_1k if args.input_cost_per_1k > 0 else "NA",
            "output_cost_per_1k": args.output_cost_per_1k if args.output_cost_per_1k > 0 else "NA",
        },
        "rows_total": len(all_rows),
        "rows_scored": len(valid_rows),
        "outputs": outputs,
        "notes": [
            "Appendix/supporting evidence only.",
            "Action budget remains the matched contract; token/latency/cost are diagnostics.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if not args.skip_doc_write:
        if is_cross_provider:
            doc_path = REPO_ROOT / f"docs/CROSS_PROVIDER_REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_{args.timestamp}.md"
            title = "# CROSS_PROVIDER_REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION"
            artifact_path = f"outputs/cross_provider_real_model_token_accounting_validation_{args.timestamp}/"
        else:
            doc_path = REPO_ROOT / f"docs/REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_{args.timestamp}.md"
            title = "# REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION"
            artifact_path = f"outputs/real_model_token_accounting_validation_{args.timestamp}/"

        doc_lines = [
            title,
            "",
            f"Timestamp: `{args.timestamp}`.",
            f"Artifact package: `{artifact_path}`.",
            "",
            "- This pass is appendix/supporting evidence and not a replacement for primary matched-surface simulation results.",
            "- It addresses provider-robustness and token/latency/cost-accounting visibility concerns.",
            "- It does not convert the paper into a systems-cost paper.",
            "- Action-budget matching remains the primary comparison contract.",
            "- Strict-F3 vs Strict-Gate1-Cap-K6 should remain non-decisive unless stronger, larger-sample evidence appears.",
            "",
            "## Contract",
            f"- Providers: {providers}",
            f"- Provider models: {provider_models}",
            f"- Datasets: {datasets}",
            f"- Budgets: {budgets}",
            f"- Seeds: {seeds}",
            f"- Subset size: {args.subset_size}",
            f"- Methods: {methods}",
            "",
            "## Files",
            "- `manifest.json`",
            "- `per_case_results.csv`",
            f"- `{summary_budget_name}`",
            f"- `{summary_method_name}`",
            "- `STATUS.md`",
        ]
        doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
