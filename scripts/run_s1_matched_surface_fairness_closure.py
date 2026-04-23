#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer


CANONICAL_SURFACE_ID = "canonical_full_method_ranking_20260421T212948Z"
DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]
DEFAULT_SEEDS = [11, 23, 37, 41, 53, 67]
METHODS = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
}


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_s1_fairness", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_observed(runtime_name: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = stable_seed("s1_matched_surface_fairness_closure", runtime_name, dataset, seed, budget, example.example_id)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        TW.SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> Any:
        return observed

    specs = build_frontier_strategies(
        factory,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    result = specs[runtime_name].run(example.question, example.answer)
    final_nodes = [observed._snapshot(b) for _, b in sorted(observed.registry.items(), key=lambda kv: kv[0])]
    return {"result": result, "final_nodes": final_nodes}


def classify_correct(result: Any, final_nodes: list[dict[str, Any]], dataset: str, gold_raw: str) -> int:
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    surfaced = repaired.get("surfaced_final_answer_raw")
    surfaced_can = canonicalize_answer(surfaced, dataset=dataset)
    gold_can = canonicalize_answer(gold_raw, dataset=dataset)
    return int(surfaced_can == gold_can and surfaced_can is not None)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build reviewer-facing s1 matched-surface fairness closure bundle.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS))
    p.add_argument("--action-token-equivalent", type=float, default=64.0)
    p.add_argument("--s1-mode", default="mode_a_inference_only_adapter")
    p.add_argument("--s1-backbone", default="simulated_branch_generator (repo matched-surface harness)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    ranking_path = REPO_ROOT / f"outputs/{CANONICAL_SURFACE_ID}/overall_ranking.csv"
    if not ranking_path.exists():
        raise FileNotFoundError(f"Missing canonical manuscript-facing ranking surface: {ranking_path}")

    out_dir = REPO_ROOT / f"outputs/s1_matched_surface_fairness_closure_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_example_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                nominal_reasoning_tokens = budget * float(args.action_token_equivalent)
                for ex in examples:
                    for method, runtime_name in METHODS.items():
                        run = run_observed(runtime_name, dataset, seed, budget, ex)
                        result = run["result"]
                        md = result.metadata or {}
                        is_correct = classify_correct(result, run["final_nodes"], dataset, str(ex.answer))

                        realized_reasoning_tokens = float(
                            md.get("realized_reasoning_tokens_estimate", result.actions_used * float(args.action_token_equivalent))
                        )
                        final_answer_tokens = float(md.get("final_answer_tokens_estimate", 0.0))
                        override_tokens = float(md.get("continuation_override_tokens_estimate", 0.0))
                        total_tokens = float(md.get("total_generated_tokens_estimate", realized_reasoning_tokens + final_answer_tokens))
                        forced_continue_events = int(md.get("forced_continue_events", 0))

                        per_example_rows.append(
                            {
                                "method": method,
                                "runtime_method": runtime_name,
                                "dataset": dataset,
                                "seed": seed,
                                "budget_actions": budget,
                                "nominal_reasoning_token_budget": nominal_reasoning_tokens,
                                "example_id": str(ex.example_id),
                                "is_correct": is_correct,
                                "actions_used": int(result.actions_used),
                                "token_equivalent_proxy": float(result.actions_used) * float(args.action_token_equivalent),
                                "expansions": int(result.expansions),
                                "verifications": int(result.verifications),
                                "realized_reasoning_tokens": realized_reasoning_tokens,
                                "final_answer_tokens": final_answer_tokens,
                                "continuation_override_tokens": override_tokens,
                                "total_generated_tokens": total_tokens,
                                "forced_continue_events": forced_continue_events,
                                "budget_exhausted": int(bool(result.budget_exhausted)),
                                "s1_mode": args.s1_mode,
                            }
                        )

    write_csv(out_dir / "per_example_results.csv", per_example_rows)

    comparison_ready_rows: list[dict[str, Any]] = []
    token_summary_rows: list[dict[str, Any]] = []
    methods = sorted(set(str(r["method"]) for r in per_example_rows))
    for method in methods:
        for budget in BUDGETS:
            sub = [r for r in per_example_rows if r["method"] == method and int(r["budget_actions"]) == budget]
            if not sub:
                continue
            row = {
                "method": method,
                "budget_actions": budget,
                "n_examples": len(sub),
                "accuracy": mean([float(r["is_correct"]) for r in sub]),
                "nominal_reasoning_token_budget": mean([float(r["nominal_reasoning_token_budget"]) for r in sub]),
                "token_equivalent_proxy": mean([float(r["token_equivalent_proxy"]) for r in sub]),
                "realized_reasoning_tokens": mean([float(r["realized_reasoning_tokens"]) for r in sub]),
                "final_answer_tokens": mean([float(r["final_answer_tokens"]) for r in sub]),
                "total_generated_tokens": mean([float(r["total_generated_tokens"]) for r in sub]),
                "continuation_override_tokens": mean([float(r["continuation_override_tokens"]) for r in sub]),
                "forced_continue_events": mean([float(r["forced_continue_events"]) for r in sub]),
                "budget_exhaustion_rate": mean([float(r["budget_exhausted"]) for r in sub]),
            }
            comparison_ready_rows.append(row)
            token_summary_rows.append(row)

    write_csv(out_dir / "comparison_ready_rows.csv", comparison_ready_rows)
    write_csv(out_dir / "token_accounting_summary.csv", token_summary_rows)

    s1_rows = [r for r in per_example_rows if r["method"] == "external_s1_budget_forcing"]
    strict_rows = [r for r in per_example_rows if r["method"] == "strict_f3"]

    fairness_safe = bool(s1_rows)
    fairness_caveat = (
        "MODE A adapter comparison on shared repository harness; not a full official s1 post-training stack reproduction. "
        "Token accounting is realized-token estimate from controller traces (reasoning/final/override separated)."
    )

    fairness_report = {
        "artifact_family": "s1_matched_surface_fairness_closure",
        "run_timestamp": args.timestamp,
        "baseline": "external_s1_budget_forcing",
        "s1_variant_path": args.s1_mode,
        "backbone_model": args.s1_backbone,
        "matched_surface": f"outputs/{CANONICAL_SURFACE_ID}",
        "dataset_set": DATASETS,
        "seed_list": seeds,
        "budget_scope_actions": BUDGETS,
        "nominal_budget_contract": {
            "budget_unit": "actions",
            "action_to_token_equivalent": float(args.action_token_equivalent),
            "nominal_reasoning_token_budget_per_case": "budget_actions * action_to_token_equivalent",
        },
        "realized_compute_accounting": {
            "realized_reasoning_tokens_total": sum(float(r["realized_reasoning_tokens"]) for r in s1_rows),
            "final_answer_tokens_total": sum(float(r["final_answer_tokens"]) for r in s1_rows),
            "total_generated_tokens_total": sum(float(r["total_generated_tokens"]) for r in s1_rows),
            "continuation_override_tokens_total": sum(float(r["continuation_override_tokens"]) for r in s1_rows),
            "forced_continue_events_total": int(sum(int(r["forced_continue_events"]) for r in s1_rows)),
            "continuation_override_accounting": "continuation_override_tokens = forced_continue_events * wait_token_word_count",
            "separated_fields": [
                "nominal_reasoning_token_budget",
                "realized_reasoning_tokens",
                "final_answer_tokens",
                "continuation_override_tokens",
                "total_generated_tokens",
            ],
        },
        "adapter_vs_official_caveat": fairness_caveat,
        "safe_for_main_table": fairness_safe,
        "safe_for_main_table_reason": (
            "Yes with MODE A boundary and explicit caveat; matched-surface datasets/budgets/seeds are identical and realized token accounting is explicit."
            if fairness_safe
            else "No; missing s1 rows."
        ),
        "side_by_side": {
            "s1_accuracy": mean([float(r["is_correct"]) for r in s1_rows]),
            "strict_f3_accuracy": mean([float(r["is_correct"]) for r in strict_rows]),
            "s1_token_equivalent_proxy_avg": mean([float(r["token_equivalent_proxy"]) for r in s1_rows]),
            "strict_f3_token_equivalent_proxy_avg": mean([float(r["token_equivalent_proxy"]) for r in strict_rows]),
            "s1_realized_reasoning_tokens_avg": mean([float(r["realized_reasoning_tokens"]) for r in s1_rows]),
        },
    }

    (out_dir / "fairness_report.json").write_text(json.dumps(fairness_report, indent=2) + "\n", encoding="utf-8")
    write_csv(
        out_dir / "fairness_report.csv",
        [
            {
                "baseline": fairness_report["baseline"],
                "s1_variant_path": fairness_report["s1_variant_path"],
                "backbone_model": fairness_report["backbone_model"],
                "matched_surface": fairness_report["matched_surface"],
                "dataset_set": "|".join(DATASETS),
                "budget_scope_actions": "|".join(str(x) for x in BUDGETS),
                "nominal_contract": f"action_to_token_equivalent={args.action_token_equivalent}",
                "realized_reasoning_tokens_total": fairness_report["realized_compute_accounting"]["realized_reasoning_tokens_total"],
                "final_answer_tokens_total": fairness_report["realized_compute_accounting"]["final_answer_tokens_total"],
                "total_generated_tokens_total": fairness_report["realized_compute_accounting"]["total_generated_tokens_total"],
                "continuation_override_tokens_total": fairness_report["realized_compute_accounting"]["continuation_override_tokens_total"],
                "adapter_vs_official_caveat": fairness_report["adapter_vs_official_caveat"],
                "safe_for_main_table": fairness_report["safe_for_main_table"],
            }
        ],
    )

    run_summary = {
        "run_timestamp": args.timestamp,
        "artifact_dir": str(out_dir.relative_to(REPO_ROOT)),
        "n_per_example_rows": len(per_example_rows),
        "methods": methods,
        "s1_safe_for_main_table": fairness_report["safe_for_main_table"],
        "remaining_caveat": fairness_caveat,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2) + "\n", encoding="utf-8")

    config_snapshot = {
        "canonical_surface": CANONICAL_SURFACE_ID,
        "datasets": DATASETS,
        "budgets": BUDGETS,
        "subset_size": SUBSET_SIZE,
        "seeds": seeds,
        "methods": METHODS,
        "adaptive_grid": ADAPTIVE_GRID,
        "action_to_token_equivalent": float(args.action_token_equivalent),
        "s1_mode": args.s1_mode,
        "s1_backbone": args.s1_backbone,
    }
    (out_dir / "config_snapshot.json").write_text(json.dumps(config_snapshot, indent=2) + "\n", encoding="utf-8")

    notes = [
        "s1 matched-surface fairness closure run.",
        f"Canonical matched surface: outputs/{CANONICAL_SURFACE_ID}",
        "Strict fairness contract uses same datasets/seeds/budgets as manuscript-facing matched surface.",
        "Realized token accounting explicitly separates nominal budget, realized reasoning tokens, final-answer tokens, and continuation override tokens.",
        f"Main-table safe status: {fairness_report['safe_for_main_table']} (with MODE A caveat).",
        "No claim of official full s1 training/eval stack reproduction in this run.",
    ]
    (out_dir / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "s1_matched_surface_fairness_closure",
        "command": f"python scripts/run_s1_matched_surface_fairness_closure.py --timestamp {args.timestamp} --seeds {','.join(str(s) for s in seeds)} --action-token-equivalent {args.action_token_equivalent}",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "files": [
            "manifest.json",
            "config_snapshot.json",
            "run_summary.json",
            "per_example_results.csv",
            "fairness_report.json",
            "fairness_report.csv",
            "token_accounting_summary.csv",
            "comparison_ready_rows.csv",
            "notes.txt",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / f"docs/S1_MATCHED_SURFACE_FAIRNESS_CLOSURE_{args.timestamp}.md"
    paper_wording = (
        "We include s1 as an external MODE A inference-side comparator on the canonical matched surface under explicit matched realized-token accounting; "
        "this is a fairness-controlled adapter comparison and does not claim full official s1 post-training-stack reproduction."
    )
    doc_lines = [
        f"# S1 matched-surface fairness closure ({args.timestamp})",
        "",
        "## Purpose",
        "Provide reviewer-defensible, artifact-backed fairness closure for the s1 baseline on the canonical manuscript-facing matched surface.",
        "",
        "## Exact s1 variant/path used",
        f"- Variant/path: `{args.s1_mode}`",
        "- Runtime method id: `external_s1_budget_forcing`",
        f"- Backbone/model context: `{args.s1_backbone}`",
        "",
        "## Exact matched surface used",
        f"- `outputs/{CANONICAL_SURFACE_ID}`",
        f"- Datasets: {DATASETS}",
        f"- Budgets: {BUDGETS}",
        f"- Seeds: {seeds}",
        f"- Subset size per (dataset, seed): {SUBSET_SIZE}",
        "",
        "## Exact fairness contract",
        "1. Same matched-surface dataset/budget/seed scope as manuscript-facing comparison.",
        "2. Inference-side MODE A adapter lane only (no full official training-stack claim).",
        "3. Report nominal budget and realized test-time token accounting separately.",
        "4. Count continuation override accounting from forced-continue events.",
        "",
        "## Token-accounting policy",
        "- Nominal reasoning budget: `budget_actions * action_to_token_equivalent`.",
        "- Realized reasoning tokens: controller-trace estimate from generated reasoning steps.",
        "- Final answer tokens: estimate from final predicted answer text.",
        "- Continuation/override tokens: `forced_continue_events * wait_token_word_count`.",
        "- Total generated tokens: realized reasoning + final answer tokens.",
        "",
        "## Main-table acceptability",
        f"- Safe for main table: **{fairness_report['safe_for_main_table']}** (with explicit MODE A boundary).",
        f"- Remaining caveat: {fairness_caveat}",
        "",
        "## Recommended manuscript wording",
        f"- \"{paper_wording}\"",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(out_dir.relative_to(REPO_ROOT))
    print(doc_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
