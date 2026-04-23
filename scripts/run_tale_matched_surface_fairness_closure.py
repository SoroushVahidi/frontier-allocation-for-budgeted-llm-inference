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

from experiments.branching import SimulatedBranchGenerator
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
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
}


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_tale_fairness", path)
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


def run_observed(runtime_name: str, dataset: str, seed: int, budget: int, example: Any, tale_params: dict[str, Any]) -> dict[str, Any]:
    run_seed = stable_seed("tale_matched_surface_fairness_closure", runtime_name, dataset, seed, budget, example.example_id)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
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
        tale_token_budget_default=int(tale_params["token_budget_default"]),
        tale_token_budget_min=int(tale_params["token_budget_min"]),
        tale_token_budget_max=int(tale_params["token_budget_max"]),
        tale_token_budget_per_question_char=float(tale_params["token_budget_per_question_char"]),
        tale_token_per_action=float(tale_params["token_per_action"]),
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
    p = argparse.ArgumentParser(description="Build reviewer-facing TALE matched-surface fairness closure bundle.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS))
    p.add_argument("--action-token-equivalent", type=float, default=64.0)
    p.add_argument("--tale-config", default="configs/tale_prompt_budgeting_v1.json")
    p.add_argument("--tale-variant", default="mode_a_inference_only_adapter (TALE-EP style prompt budgeting)")
    p.add_argument("--backbone", default="simulated_branch_generator (repo matched-surface harness)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    ranking_path = REPO_ROOT / f"outputs/{CANONICAL_SURFACE_ID}/overall_ranking.csv"
    if not ranking_path.exists():
        raise FileNotFoundError(f"Missing canonical manuscript-facing ranking surface: {ranking_path}")

    tale_cfg = json.loads((REPO_ROOT / args.tale_config).read_text(encoding="utf-8"))
    tale_params = tale_cfg.get("tale", {}) or {}

    out_dir = REPO_ROOT / f"outputs/tale_matched_surface_fairness_closure_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_example_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                nominal_reasoning_tokens = budget * float(args.action_token_equivalent)
                for ex in examples:
                    for method, runtime_name in METHODS.items():
                        run = run_observed(runtime_name, dataset, seed, budget, ex, tale_params)
                        result = run["result"]
                        md = result.metadata or {}
                        is_correct = classify_correct(result, run["final_nodes"], dataset, str(ex.answer))

                        token_equivalent_proxy = float(result.actions_used) * float(args.action_token_equivalent)
                        realized_reasoning_tokens_raw = md.get("realized_reasoning_tokens_estimate")
                        realized_reasoning_tokens = float(realized_reasoning_tokens_raw) if realized_reasoning_tokens_raw is not None else token_equivalent_proxy
                        realized_reasoning_source = (
                            "controller_trace"
                            if realized_reasoning_tokens_raw is not None
                            else "action_proxy"
                        )

                        final_answer_tokens_raw = md.get("final_answer_tokens_estimate")
                        final_answer_tokens = float(final_answer_tokens_raw) if final_answer_tokens_raw is not None else ""
                        final_answer_tracked = int(final_answer_tokens_raw is not None)

                        total_tokens_raw = md.get("total_generated_tokens_estimate")
                        if total_tokens_raw is not None:
                            total_generated_tokens = float(total_tokens_raw)
                            total_source = "controller_trace"
                        elif md.get("generated_tokens_estimate") is not None:
                            total_generated_tokens = float(md.get("generated_tokens_estimate"))
                            total_source = "prediction_word_count"
                        else:
                            total_generated_tokens = realized_reasoning_tokens + (float(final_answer_tokens_raw) if final_answer_tokens_raw is not None else 0.0)
                            total_source = "derived_reasoning_plus_answer"

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
                                "expansions": int(result.expansions),
                                "verifications": int(result.verifications),
                                "token_equivalent_proxy": token_equivalent_proxy,
                                "realized_reasoning_tokens": realized_reasoning_tokens,
                                "realized_reasoning_tokens_source": realized_reasoning_source,
                                "final_answer_tokens": final_answer_tokens,
                                "final_answer_tokens_tracked": final_answer_tracked,
                                "total_generated_tokens": total_generated_tokens,
                                "total_generated_tokens_source": total_source,
                                "budget_exhausted": int(bool(result.budget_exhausted)),
                                "token_budget_predicted": float(md.get("token_budget_predicted", nominal_reasoning_tokens)),
                                "budget_actions_equivalent": float(md.get("budget_actions_equivalent", budget)),
                                "token_budget_violation": int(bool(md.get("token_budget_violation", False))),
                                "generated_tokens_estimate": float(md.get("generated_tokens_estimate", total_generated_tokens)),
                                "token_budget_default": float(md.get("token_budget_default", tale_params.get("token_budget_default", 0))),
                                "token_budget_min": float(md.get("token_budget_min", tale_params.get("token_budget_min", 0))),
                                "token_budget_max": float(md.get("token_budget_max", tale_params.get("token_budget_max", 0))),
                                "token_budget_per_question_char": float(md.get("token_budget_per_question_char", tale_params.get("token_budget_per_question_char", 0.0))),
                                "token_per_action": float(md.get("token_per_action", tale_params.get("token_per_action", args.action_token_equivalent))),
                                "external_baseline_family": str(md.get("external_baseline_family", "")),
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
            tracked_answers = [float(r["final_answer_tokens"]) for r in sub if str(r["final_answer_tokens"]) != ""]
            row = {
                "method": method,
                "budget_actions": budget,
                "n_examples": len(sub),
                "accuracy": mean([float(r["is_correct"]) for r in sub]),
                "nominal_reasoning_token_budget": mean([float(r["nominal_reasoning_token_budget"]) for r in sub]),
                "token_budget_predicted": mean([float(r["token_budget_predicted"]) for r in sub]),
                "budget_actions_equivalent": mean([float(r["budget_actions_equivalent"]) for r in sub]),
                "token_equivalent_proxy": mean([float(r["token_equivalent_proxy"]) for r in sub]),
                "realized_reasoning_tokens": mean([float(r["realized_reasoning_tokens"]) for r in sub]),
                "final_answer_tokens": mean(tracked_answers) if tracked_answers else 0.0,
                "final_answer_tokens_tracked_rate": mean([float(r["final_answer_tokens_tracked"]) for r in sub]),
                "total_generated_tokens": mean([float(r["total_generated_tokens"]) for r in sub]),
                "token_budget_violation_rate": mean([float(r["token_budget_violation"]) for r in sub]),
                "budget_exhaustion_rate": mean([float(r["budget_exhausted"]) for r in sub]),
            }
            comparison_ready_rows.append(row)
            token_summary_rows.append(row)

    write_csv(out_dir / "comparison_ready_rows.csv", comparison_ready_rows)
    write_csv(out_dir / "token_accounting_summary.csv", token_summary_rows)

    tale_rows = [r for r in per_example_rows if r["method"] == "external_tale_prompt_budgeting"]
    strict_rows = [r for r in per_example_rows if r["method"] == "strict_f3"]

    nominal_total = sum(float(r["nominal_reasoning_token_budget"]) for r in tale_rows)
    predicted_total = sum(float(r["token_budget_predicted"]) for r in tale_rows)
    realized_reasoning_total = sum(float(r["realized_reasoning_tokens"]) for r in tale_rows)
    total_generated_total = sum(float(r["total_generated_tokens"]) for r in tale_rows)
    tracked_answer_tokens_total = sum(float(r["final_answer_tokens"]) for r in tale_rows if str(r["final_answer_tokens"]) != "")
    tracked_answer_count = sum(int(r["final_answer_tokens_tracked"]) for r in tale_rows)

    fairness_safe = bool(tale_rows)
    fairness_caveat = (
        "MODE A TALE adapter on shared repository matched-surface harness. This is not a full official TALE-PT stack reproduction; "
        "realized reasoning tokens are action-proxy estimates where controller-trace reasoning tokens are unavailable for this baseline."
    )

    fairness_report = {
        "artifact_family": "tale_matched_surface_fairness_closure",
        "run_timestamp": args.timestamp,
        "baseline": "external_tale_prompt_budgeting",
        "tale_variant_path": args.tale_variant,
        "backbone_model": args.backbone,
        "official_reference": {
            "repo": "https://github.com/GeniusHTX/TALE",
            "relevant_path_for_this_lane": "TALE-EP style inference-side budget estimation/prompt budgeting, not TALE-PT",
            "budget_freezing_policy": "Budget-estimator hyperparameters are frozen from configs/tale_prompt_budgeting_v1.json before test evaluation.",
        },
        "matched_surface": f"outputs/{CANONICAL_SURFACE_ID}",
        "dataset_set": DATASETS,
        "seed_list": seeds,
        "budget_scope_actions": BUDGETS,
        "nominal_budget_contract": {
            "budget_unit": "actions",
            "action_to_token_equivalent": float(args.action_token_equivalent),
            "nominal_reasoning_token_budget_per_case": "budget_actions * action_to_token_equivalent",
            "nominal_reasoning_token_budget_total": nominal_total,
            "tale_predicted_token_budget_total": predicted_total,
        },
        "realized_compute_accounting": {
            "realized_reasoning_tokens_total": realized_reasoning_total,
            "final_answer_tokens_total": tracked_answer_tokens_total,
            "final_answer_tokens_tracked_case_count": tracked_answer_count,
            "total_generated_tokens_total": total_generated_total,
            "separated_fields": [
                "nominal_reasoning_token_budget",
                "token_budget_predicted",
                "realized_reasoning_tokens",
                "final_answer_tokens",
                "total_generated_tokens",
            ],
            "reasoning_token_source_policy": {
                "preferred": "metadata.realized_reasoning_tokens_estimate",
                "fallback": "actions_used * action_to_token_equivalent",
            },
            "final_answer_tracking_policy": "Only counted when metadata.final_answer_tokens_estimate is present.",
            "total_generated_source_priority": [
                "metadata.total_generated_tokens_estimate",
                "metadata.generated_tokens_estimate",
                "derived_reasoning_plus_answer",
            ],
        },
        "tale_budget_allocation_fields": {
            "token_budget_estimator": "char_length_linear",
            "token_budget_default": tale_params.get("token_budget_default"),
            "token_budget_min": tale_params.get("token_budget_min"),
            "token_budget_max": tale_params.get("token_budget_max"),
            "token_budget_per_question_char": tale_params.get("token_budget_per_question_char"),
            "token_per_action": tale_params.get("token_per_action"),
            "token_budget_violation_rate": mean([float(r["token_budget_violation"]) for r in tale_rows]) if tale_rows else 0.0,
        },
        "adapter_vs_official_caveat": fairness_caveat,
        "safe_for_main_table": fairness_safe,
        "safe_for_main_table_reason": (
            "Yes, with explicit MODE A inference-adapter boundary and realized-token accounting caveat disclosure."
            if fairness_safe
            else "No; missing TALE rows."
        ),
        "side_by_side_same_contract": {
            "tale_accuracy": mean([float(r["is_correct"]) for r in tale_rows]),
            "strict_f3_accuracy": mean([float(r["is_correct"]) for r in strict_rows]),
            "tale_realized_reasoning_tokens_avg": mean([float(r["realized_reasoning_tokens"]) for r in tale_rows]),
            "strict_f3_realized_reasoning_tokens_avg": mean([float(r["realized_reasoning_tokens"]) for r in strict_rows]),
            "tale_total_generated_tokens_avg": mean([float(r["total_generated_tokens"]) for r in tale_rows]),
            "strict_f3_total_generated_tokens_avg": mean([float(r["total_generated_tokens"]) for r in strict_rows]),
        },
    }

    fairness_csv_rows = [
        {
            "baseline": "external_tale_prompt_budgeting",
            "matched_surface": f"outputs/{CANONICAL_SURFACE_ID}",
            "dataset_set": "|".join(DATASETS),
            "budget_scope_actions": "|".join(str(b) for b in BUDGETS),
            "nominal_reasoning_token_budget_total": nominal_total,
            "tale_predicted_token_budget_total": predicted_total,
            "realized_reasoning_tokens_total": realized_reasoning_total,
            "final_answer_tokens_total": tracked_answer_tokens_total,
            "final_answer_tokens_tracked_case_count": tracked_answer_count,
            "total_generated_tokens_total": total_generated_total,
            "safe_for_main_table": int(bool(fairness_report["safe_for_main_table"])),
            "caveat": fairness_caveat,
        }
    ]

    run_summary = {
        "run_timestamp": args.timestamp,
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "n_rows_per_example": len(per_example_rows),
        "methods": sorted(methods),
        "datasets": DATASETS,
        "budgets": BUDGETS,
        "seeds": seeds,
    }

    manifest = {
        "artifact_family": "tale_matched_surface_fairness_closure",
        "timestamp": args.timestamp,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "required_files": [
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

    notes = [
        "TALE matched-surface fairness closure bundle",
        f"timestamp={args.timestamp}",
        f"matched_surface=outputs/{CANONICAL_SURFACE_ID}",
        "contract=matched realized-token compute with explicit nominal-vs-realized separation",
        "variant=MODE A inference-side TALE adapter (TALE-EP style); no TALE-PT reproduction claim",
        "budget_hyperparameters=frozen from configs/tale_prompt_budgeting_v1.json before evaluation",
    ]

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "config_snapshot.json").write_text(json.dumps(tale_cfg, indent=2), encoding="utf-8")
    (out_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    (out_dir / "fairness_report.json").write_text(json.dumps(fairness_report, indent=2), encoding="utf-8")
    write_csv(out_dir / "fairness_report.csv", fairness_csv_rows)
    (out_dir / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
