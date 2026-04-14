#!/usr/bin/env python3
"""Cross-strategy frontier allocation scaffold using existing controller families."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.frontier_router import (
    derive_oracle_labels,
    fit_lightweight_router,
    selector_accuracy_from_predictions,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run cross-strategy frontier allocation scaffold")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=8)
    p.add_argument("--seed", type=int, default=29)
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument(
        "--adaptive-min-expand-grid",
        default="1",
        help="Comma-separated adaptive min_expansions_before_prune values to include as strategy variants.",
    )
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/new_paper/paradigm_controller_router")
    p.add_argument(
        "--selector-mode",
        choices=["static_calib_best", "router", "both"],
        default="both",
        help="Optional selector integration for frontier allocation path.",
    )
    p.add_argument(
        "--vgs-candidates",
        type=int,
        default=3,
        help="Candidates for verifier_guided_search (best-of-N with verifier scoring).",
    )
    p.add_argument(
        "--vgs-min-expansions",
        type=int,
        default=1,
        help="Minimum expand steps per candidate before verifier scoring (anti-collapse).",
    )
    return p.parse_args()


def _parse_budgets(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    budgets = _parse_budgets(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)
    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    split_idx = max(1, min(len(examples) - 1, int(len(examples) * args.calibration_ratio)))
    calib_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "seed": args.seed,
        "budgets": budgets,
        "calibration_ratio": args.calibration_ratio,
        "n_calibration_examples": len(calib_examples),
        "n_eval_examples": len(eval_examples),
        "adaptive_min_expand_grid": adaptive_grid,
        "use_openai_api": args.use_openai_api,
        "openai_model": args.openai_model,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "vgs_candidates": args.vgs_candidates,
        "vgs_min_expansions": args.vgs_min_expansions,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    gen_factory = generator_factory_for_mode(
        args.use_openai_api,
        rng,
        args.openai_model,
        args.temperature,
        args.max_output_tokens,
        args.timeout_seconds,
    )

    strategy_rows: list[dict[str, Any]] = []
    selector_rows: list[dict[str, Any]] = []
    router_dataset_rows: list[dict[str, Any]] = []
    router_prediction_rows: list[dict[str, Any]] = []
    per_example_eval_rows: list[dict[str, Any]] = []
    family_order = [
        "reasoning_greedy",
        "self_consistency_3",
        "reasoning_beam2",
        "adaptive_min_expand_0",
        "adaptive_min_expand_1",
        "adaptive_min_expand_2",
        "verifier_guided_search",
        "program_of_thought",
    ]
    primary_method = "adaptive_min_expand_1"

    for budget in budgets:
        calib_strategies = build_frontier_strategies(
            gen_factory,
            budget,
            adaptive_grid,
            rng,
            use_openai_api=args.use_openai_api,
            vgs_candidates=args.vgs_candidates,
            vgs_min_expansions=args.vgs_min_expansions,
        )
        calib_metrics, calib_rows = evaluate_strategies_on_examples(calib_examples, calib_strategies)

        feasible = [s for s, m in calib_metrics.items() if m["avg_actions"] <= float(budget)]
        chosen = max(feasible, key=lambda s: calib_metrics[s]["accuracy"]) if feasible else max(
            calib_metrics, key=lambda s: calib_metrics[s]["accuracy"]
        )

        eval_strategies = build_frontier_strategies(
            gen_factory,
            budget,
            adaptive_grid,
            rng,
            use_openai_api=args.use_openai_api,
            vgs_candidates=args.vgs_candidates,
            vgs_min_expansions=args.vgs_min_expansions,
        )
        eval_metrics, eval_rows = evaluate_strategies_on_examples(eval_examples, eval_strategies)
        for row in eval_rows:
            per_example_eval_rows.append({**row, "budget": budget, "split_name": "eval"})

        eval_by_example: dict[str, list[dict[str, Any]]] = {}
        for row in eval_rows:
            eval_by_example.setdefault(str(row["example_id"]), []).append(row)
        oracle_correct = 0
        for per_ex in eval_by_example.values():
            oracle_correct += int(any(r["is_correct"] for r in per_ex))
        oracle_accuracy = oracle_correct / max(1, len(eval_by_example))

        chosen_eval = eval_metrics[chosen]
        base_row = {
            "budget": budget,
            "selector": "static_calib_best",
            "selected_strategy": chosen,
            "train_mode": "calibration_constant",
            "selected_strategy_calib_accuracy": calib_metrics[chosen]["accuracy"],
            "selected_strategy_eval_accuracy": chosen_eval["accuracy"],
            "selected_strategy_eval_avg_actions": chosen_eval["avg_actions"],
            "oracle_eval_accuracy_over_strategy_frontier": oracle_accuracy,
            "oracle_gap_recovered_vs_static": 0.0,
        }
        selector_rows.append(
            {
                **base_row,
            }
        )
        if primary_method in eval_metrics:
            p = eval_metrics[primary_method]
            selector_rows.append(
                {
                    "budget": budget,
                    "selector": "primary_method",
                    "selected_strategy": primary_method,
                    "train_mode": "fixed_primary",
                    "selected_strategy_calib_accuracy": "",
                    "selected_strategy_eval_accuracy": p["accuracy"],
                    "selected_strategy_eval_avg_actions": p["avg_actions"],
                    "oracle_eval_accuracy_over_strategy_frontier": oracle_accuracy,
                    "oracle_gap_recovered_vs_static": 0.0,
                }
            )

        calib_oracle = derive_oracle_labels(calib_rows, strategy_order=family_order)
        eval_oracle = derive_oracle_labels(eval_rows, strategy_order=family_order)
        ex_question = {str(ex.example_id): ex.question for ex in examples}
        for ex_id, label in calib_oracle.items():
            router_dataset_rows.append(
                {
                    "split": "calibration",
                    "budget": budget,
                    "example_id": ex_id,
                    "question": ex_question.get(ex_id, ""),
                    "oracle_best_strategy": label,
                }
            )
        for ex_id, label in eval_oracle.items():
            router_dataset_rows.append(
                {
                    "split": "eval",
                    "budget": budget,
                    "example_id": ex_id,
                    "question": ex_question.get(ex_id, ""),
                    "oracle_best_strategy": label,
                }
            )

        if args.selector_mode in {"router", "both"} and calib_oracle:
            train_pairs = [(ex_id, y) for ex_id, y in calib_oracle.items() if ex_id in ex_question]
            train_questions = [ex_question[ex_id] for ex_id, _ in train_pairs]
            train_labels = [y for _, y in train_pairs]
            fit = fit_lightweight_router(train_questions, train_labels, seed=args.seed + budget)

            eval_questions = {ex_id: ex_question.get(ex_id, "") for ex_id in eval_oracle}
            pred_labels = fit.model.predict(list(eval_questions.values()))
            pred_map = {
                ex_id: str(pred_labels[idx])
                for idx, ex_id in enumerate(eval_questions.keys())
            }
            pred_metrics = selector_accuracy_from_predictions(eval_rows, pred_map)
            static_acc = float(base_row["selected_strategy_eval_accuracy"])
            router_acc = float(pred_metrics["accuracy"])
            denom = max(1e-9, oracle_accuracy - static_acc)
            recovered = (router_acc - static_acc) / denom if oracle_accuracy > static_acc else 0.0
            selector_rows.append(
                {
                    "budget": budget,
                    "selector": "router",
                    "selected_strategy": "per_query_prediction",
                    "train_mode": fit.mode,
                    "selected_strategy_calib_accuracy": "",
                    "selected_strategy_eval_accuracy": router_acc,
                    "selected_strategy_eval_avg_actions": pred_metrics["avg_actions"],
                    "oracle_eval_accuracy_over_strategy_frontier": oracle_accuracy,
                    "oracle_gap_recovered_vs_static": recovered,
                }
            )
            for ex_id, pred in pred_map.items():
                router_prediction_rows.append(
                    {
                        "budget": budget,
                        "example_id": ex_id,
                        "predicted_strategy": pred,
                        "oracle_best_strategy": eval_oracle.get(ex_id, ""),
                        "is_oracle_match": int(pred == eval_oracle.get(ex_id, "")),
                    }
                )

        for split_name, metrics in (("calibration", calib_metrics), ("eval", eval_metrics)):
            for strategy, m in metrics.items():
                strategy_rows.append(
                    {
                        "budget": budget,
                        "split": split_name,
                        "strategy": strategy,
                        **m,
                    }
                )

    with (run_dir / "strategy_metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "budget",
                "split",
                "strategy",
                "n_examples",
                "accuracy",
                "avg_actions",
                "avg_expansions",
                "avg_verifications",
                "budget_exhaustion_rate",
            ],
        )
        writer.writeheader()
        writer.writerows(strategy_rows)

    with (run_dir / "selector_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "budget",
                "selector",
                "selected_strategy",
                "train_mode",
                "selected_strategy_calib_accuracy",
                "selected_strategy_eval_accuracy",
                "selected_strategy_eval_avg_actions",
                "oracle_eval_accuracy_over_strategy_frontier",
                "oracle_gap_recovered_vs_static",
            ],
        )
        writer.writeheader()
        writer.writerows(selector_rows)

    with (run_dir / "router_dataset.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["split", "budget", "example_id", "question", "oracle_best_strategy"],
        )
        writer.writeheader()
        writer.writerows(router_dataset_rows)

    with (run_dir / "router_predictions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["budget", "example_id", "predicted_strategy", "oracle_best_strategy", "is_oracle_match"],
        )
        writer.writeheader()
        writer.writerows(router_prediction_rows)

    with (run_dir / "per_example_eval.jsonl").open("w", encoding="utf-8") as f:
        for row in per_example_eval_rows:
            f.write(json.dumps(row, default=str) + "\n")

    note_lines = [
        "# Cross-strategy frontier allocation note",
        "",
        "This run evaluates a frontier of distinct existing strategy families and selectors under fixed budget.",
        "",
        "Strategies used:",
        "- reasoning_greedy (GreedyController)",
        "- self_consistency_3 (BestOfNController with n=3)",
        "- reasoning_beam2 (BeamController width=2)",
        f"- adaptive_min_expand_k (AdaptiveController variants for k in {adaptive_grid})",
        "- verifier_guided_search (VerifierGuidedSearchController: expand candidates, verifier-ranked selection)",
        "- program_of_thought (ProgramOfThoughtController: code generation + sandbox execution)",
        "",
        "## Label derivation from existing artifacts",
        "- `strategy_metrics.csv` stores per-family frontier aggregates.",
        "- `per_example_eval.jsonl` stores per-example x strategy outcomes used to derive oracle labels.",
        "- `router_dataset.csv` materializes query -> oracle best strategy labels for router training/eval.",
        "",
        "## Selector comparison results",
    ]
    for r in selector_rows:
        note_lines.append(
            f"- budget={r['budget']}, selector={r['selector']}: selected={r['selected_strategy']}, "
            f"selected_eval_acc={r['selected_strategy_eval_accuracy']:.3f}, "
            f"selected_eval_avg_actions={r['selected_strategy_eval_avg_actions']:.2f}, "
            f"oracle_eval_acc={r['oracle_eval_accuracy_over_strategy_frontier']:.3f}, "
            f"oracle_gap_recovered_vs_static={float(r['oracle_gap_recovered_vs_static']):.3f}"
        )

    if selector_rows:
        gap_values = [
            float(r["oracle_eval_accuracy_over_strategy_frontier"]) - float(r["selected_strategy_eval_accuracy"])
            for r in selector_rows
        ]
        note_lines.extend(
            [
                "",
                "## Frontier gap signal",
                f"- Mean oracle-minus-selected accuracy gap across budgets: {statistics.mean(gap_values):.3f}",
                "- Positive gap implies headroom for richer cross-strategy frontier controllers (dynamic per-example or per-step allocation).",
            ]
        )

    (run_dir / "note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")
    print(str(run_dir))


if __name__ == "__main__":
    main()
