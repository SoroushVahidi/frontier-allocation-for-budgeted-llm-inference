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
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator, SimulatedBranchGenerator
from experiments.controllers import AdaptiveController, BeamController, BestOfNController, GreedyController
from experiments.data import PilotExample, extract_final_answer
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples
from experiments.scoring import ScoreConfig, SimpleBranchScorer


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
    p.add_argument("--output-dir", default="outputs/cross_strategy_frontier_allocation_controller")
    return p.parse_args()


def _parse_budgets(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _load_examples(dataset_name: str, subset_size: int, seed: int) -> list[PilotExample]:
    spec = resolve_dataset_spec(dataset_name)
    rows = sample_hf_examples(
        dataset_name=dataset_name,
        pilot_size=subset_size,
        seed=seed,
        split=spec.default_split,
        config_name=spec.default_config,
    )
    return [
        PilotExample(
            example_id=r["example_id"],
            question=r["question"],
            answer=extract_final_answer(r["answer"]),
        )
        for r in rows
    ]


def _generator_factory(args: argparse.Namespace, rng: random.Random) -> Callable[[], Any]:
    if args.use_openai_api:
        key = os.getenv("OPENAI_API_KEY")

        def factory() -> APIBranchGenerator:
            return APIBranchGenerator(
                provider="openai",
                api_key=key,
                model=args.openai_model,
                temperature=args.temperature,
                max_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
            )

        return factory

    def factory() -> SimulatedBranchGenerator:
        return SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)

    return factory


def _strategy_specs(generator_factory: Callable[[], Any], budget: int, adaptive_min_expand_grid: list[int]) -> dict[str, Any]:
    scorer = SimpleBranchScorer(ScoreConfig())
    specs: dict[str, Any] = {
        "reasoning_greedy": GreedyController(generator_factory(), scorer, budget),
        "self_consistency_3": BestOfNController(generator_factory(), scorer, budget, n_candidates=3),
        "reasoning_beam2": BeamController(generator_factory(), scorer, budget, width=2),
    }
    for min_expand in adaptive_min_expand_grid:
        specs[f"adaptive_min_expand_{min_expand}"] = AdaptiveController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=min_expand,
            method_name=f"adaptive_min_expand_{min_expand}",
        )
    return specs


def _evaluate_strategies(examples: list[PilotExample], strategies: dict[str, Any]) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    by_strategy: dict[str, list[dict[str, Any]]] = {k: [] for k in strategies}
    for ex in examples:
        for name, controller in strategies.items():
            r = controller.run(ex.question, ex.answer)
            row = {
                "example_id": ex.example_id,
                "strategy": name,
                "is_correct": r.is_correct,
                "actions_used": r.actions_used,
                "expansions": r.expansions,
                "verifications": r.verifications,
                "budget_exhausted": r.budget_exhausted,
            }
            rows.append(row)
            by_strategy[name].append(row)

    metrics: dict[str, dict[str, float]] = {}
    for name, srows in by_strategy.items():
        n = max(1, len(srows))
        metrics[name] = {
            "n_examples": n,
            "accuracy": sum(1 for r in srows if r["is_correct"]) / n,
            "avg_actions": sum(float(r["actions_used"]) for r in srows) / n,
            "avg_expansions": sum(float(r["expansions"]) for r in srows) / n,
            "avg_verifications": sum(float(r["verifications"]) for r in srows) / n,
            "budget_exhaustion_rate": sum(1 for r in srows if r["budget_exhausted"]) / n,
        }
    return metrics, rows


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    budgets = _parse_budgets(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)
    examples = _load_examples(args.dataset, args.subset_size, args.seed)
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
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    strategy_rows: list[dict[str, Any]] = []
    selector_rows: list[dict[str, Any]] = []

    for budget in budgets:
        calib_strategies = _strategy_specs(_generator_factory(args, rng), budget, adaptive_grid)
        calib_metrics, _ = _evaluate_strategies(calib_examples, calib_strategies)

        feasible = [s for s, m in calib_metrics.items() if m["avg_actions"] <= float(budget)]
        chosen = max(feasible, key=lambda s: calib_metrics[s]["accuracy"]) if feasible else max(
            calib_metrics, key=lambda s: calib_metrics[s]["accuracy"]
        )

        eval_strategies = _strategy_specs(_generator_factory(args, rng), budget, adaptive_grid)
        eval_metrics, eval_rows = _evaluate_strategies(eval_examples, eval_strategies)

        # Oracle upper bound over the available strategy frontier on eval split.
        eval_by_example: dict[str, list[dict[str, Any]]] = {}
        for row in eval_rows:
            eval_by_example.setdefault(str(row["example_id"]), []).append(row)
        oracle_correct = 0
        for per_ex in eval_by_example.values():
            oracle_correct += int(any(r["is_correct"] for r in per_ex))
        oracle_accuracy = oracle_correct / max(1, len(eval_by_example))

        chosen_eval = eval_metrics[chosen]
        selector_rows.append(
            {
                "budget": budget,
                "selected_strategy": chosen,
                "selected_strategy_calib_accuracy": calib_metrics[chosen]["accuracy"],
                "selected_strategy_eval_accuracy": chosen_eval["accuracy"],
                "selected_strategy_eval_avg_actions": chosen_eval["avg_actions"],
                "oracle_eval_accuracy_over_strategy_frontier": oracle_accuracy,
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
                "selected_strategy",
                "selected_strategy_calib_accuracy",
                "selected_strategy_eval_accuracy",
                "selected_strategy_eval_avg_actions",
                "oracle_eval_accuracy_over_strategy_frontier",
            ],
        )
        writer.writeheader()
        writer.writerows(selector_rows)

    note_lines = [
        "# Cross-strategy frontier allocation note",
        "",
        "This run evaluates a frontier of distinct existing strategy families and a simple budgeted selector.",
        "",
        "Strategies used:",
        "- reasoning_greedy (GreedyController)",
        "- self_consistency_3 (BestOfNController with n=3)",
        "- reasoning_beam2 (BeamController width=2)",
        f"- adaptive_min_expand_k (AdaptiveController variants for k in {adaptive_grid})",
        "",
        "## Budgeted selector results",
    ]
    for r in selector_rows:
        note_lines.append(
            f"- budget={r['budget']}: selected={r['selected_strategy']}, "
            f"selected_eval_acc={r['selected_strategy_eval_accuracy']:.3f}, "
            f"selected_eval_avg_actions={r['selected_strategy_eval_avg_actions']:.2f}, "
            f"oracle_eval_acc={r['oracle_eval_accuracy_over_strategy_frontier']:.3f}"
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
