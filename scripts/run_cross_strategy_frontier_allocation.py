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
    per_example_eval_rows: list[dict[str, Any]] = []

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
        calib_metrics, _ = evaluate_strategies_on_examples(calib_examples, calib_strategies)

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

    with (run_dir / "per_example_eval.jsonl").open("w", encoding="utf-8") as f:
        for row in per_example_eval_rows:
            f.write(json.dumps(row, default=str) + "\n")

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
        "- verifier_guided_search (VerifierGuidedSearchController: expand candidates, verifier-ranked selection)",
        "- program_of_thought (ProgramOfThoughtController: code generation + sandbox execution)",
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
