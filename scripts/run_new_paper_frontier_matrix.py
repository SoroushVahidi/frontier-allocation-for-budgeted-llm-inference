#!/usr/bin/env python3
"""Multi-dataset, multi-budget frontier matrix for the new-paper (cross-controller allocation) track.

Produces manuscript-style tables under outputs/new_paper_frontier_matrix/<run_id>/:
  frontier_allocation_execution_report.json
  frontier_budget_dataset_summary.csv
  frontier_allocation_oracle_gap.csv
  frontier_allocation_controller_selector.csv
  anti_collapse_min_expand_comparison.csv
  new_paper_frontier_interpretation.md
"""

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
import traceback
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    adaptive_anti_collapse_stats,
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)


def _parse_budgets(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_datasets(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def run_single_dataset_frontier(
    dataset: str,
    *,
    subset_size: int,
    seed: int,
    budgets: list[int],
    calibration_ratio: float,
    adaptive_grid: list[int],
    use_openai_api: bool,
    openai_model: str,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
    vgs_candidates: int,
    vgs_min_expansions: int,
    rng: random.Random,
) -> dict[str, Any]:
    examples = load_pilot_examples(dataset, subset_size, seed)
    split_idx = max(1, min(len(examples) - 1, int(len(examples) * calibration_ratio)))
    calib_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]

    gen_factory = generator_factory_for_mode(
        use_openai_api,
        rng,
        openai_model,
        temperature,
        max_output_tokens,
        timeout_seconds,
    )

    strategy_rows: list[dict[str, Any]] = []
    selector_rows: list[dict[str, Any]] = []
    per_example_eval_rows: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []

    for budget in budgets:
        calib_strategies = build_frontier_strategies(
            gen_factory,
            budget,
            adaptive_grid,
            rng,
            use_openai_api=use_openai_api,
            vgs_candidates=vgs_candidates,
            vgs_min_expansions=vgs_min_expansions,
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
            use_openai_api=use_openai_api,
            vgs_candidates=vgs_candidates,
            vgs_min_expansions=vgs_min_expansions,
        )
        eval_metrics, eval_rows = evaluate_strategies_on_examples(eval_examples, eval_strategies)

        for row in eval_rows:
            per_example_eval_rows.append(
                {**row, "budget": budget, "split_name": "eval", "dataset": dataset}
            )

        eval_by_example: dict[str, list[dict[str, Any]]] = {}
        for row in eval_rows:
            eval_by_example.setdefault(str(row["example_id"]), []).append(row)
        oracle_correct = sum(1 for per_ex in eval_by_example.values() if any(r["is_correct"] for r in per_ex))
        oracle_accuracy = oracle_correct / max(1, len(eval_by_example))

        chosen_eval = eval_metrics[chosen]
        oracle_gap = float(oracle_accuracy) - float(chosen_eval["accuracy"])
        selector_rows.append(
            {
                "dataset": dataset,
                "budget": budget,
                "selected_strategy": chosen,
                "selected_strategy_calib_accuracy": calib_metrics[chosen]["accuracy"],
                "selected_strategy_eval_accuracy": chosen_eval["accuracy"],
                "selected_strategy_eval_avg_actions": chosen_eval["avg_actions"],
                "oracle_eval_accuracy_over_strategy_frontier": oracle_accuracy,
                "oracle_gap_accuracy": oracle_gap,
            }
        )

        for split_name, metrics in (("calibration", calib_metrics), ("eval", eval_metrics)):
            for strategy, m in metrics.items():
                strategy_rows.append(
                    {
                        "dataset": dataset,
                        "budget": budget,
                        "split": split_name,
                        "strategy": strategy,
                        **m,
                    }
                )

        ac_stats = adaptive_anti_collapse_stats(eval_rows)
        for k, st in ac_stats.items():
            mname = f"adaptive_min_expand_{k}"
            met = eval_metrics.get(mname, {})
            anti_rows.append(
                {
                    "dataset": dataset,
                    "budget": budget,
                    "min_expand_k": int(k),
                    "accuracy": met.get("accuracy", 0.0),
                    "avg_actions": met.get("avg_actions", 0.0),
                    "avg_expansions": met.get("avg_expansions", 0.0),
                    "avg_verifications": met.get("avg_verifications", 0.0),
                    "mean_prune_share_of_actions": st["mean_prune_share_of_actions"],
                    "mean_forced_expand_share": st["mean_forced_expand_share"],
                    "mean_action_trace_length": st["mean_action_trace_length"],
                    "examples_with_action_trace": int(st["examples_with_trace"]),
                }
            )

    return {
        "dataset": dataset,
        "n_total_examples": len(examples),
        "n_calib": len(calib_examples),
        "n_eval": len(eval_examples),
        "strategy_rows": strategy_rows,
        "selector_rows": selector_rows,
        "per_example_eval_rows": per_example_eval_rows,
        "anti_collapse_rows": anti_rows,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="New-paper multi-dataset frontier allocation matrix")
    p.add_argument(
        "--datasets",
        default="openai/gsm8k,EleutherAI/hendrycks_math",
        help="Comma-separated HF dataset keys (registry in experiments/hf_datasets.py).",
    )
    p.add_argument("--try-gpqa", action="store_true", help="Append Idavidrein/gpqa (gated); skip on load failure.")
    p.add_argument("--subset-size", type=int, default=48)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--budgets", default="6,8,10,12")
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/new_paper_frontier_matrix")
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    return p.parse_args()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _interpretation_md(
    run_id: str,
    completed: list[str],
    failed: list[dict[str, str]],
    gaps: list[float],
    selector_rows: list[dict[str, Any]],
) -> str:
    lines = [
        f"# New-paper frontier matrix — interpretation ({run_id})",
        "",
        "## What this run measures",
        "",
        "- **Strategy frontier**: fixed controller families (greedy, self-consistency, beam, adaptive min-expand variants, verifier-guided search, program-of-thought) evaluated under a shared action budget.",
        "- **Simple calib→eval selector**: picks the strategy with highest calibration accuracy subject to average-actions feasibility; reports **oracle** accuracy (best per-example strategy on eval) minus selected accuracy (**oracle gap**).",
        "- **Anti-collapse**: for `adaptive_min_expand_k`, tracks forced expands before prune vs prune share in the adaptive action trace (simulator uses stochastic scores).",
        "",
        "## Completed datasets",
        "",
    ]
    for d in completed:
        lines.append(f"- `{d}`")
    if failed:
        lines.extend(["", "## Blocked or failed datasets", ""])
        for item in failed:
            lines.append(f"- **{item.get('dataset', '?')}**: {item.get('error', 'unknown')}")
    lines.extend(
        [
            "",
            "## Oracle gap (headroom)",
            "",
        ]
    )
    if gaps:
        lines.append(
            f"- Mean oracle-minus-selected gap across (dataset, budget) cells: **{statistics.mean(gaps):.4f}** "
            f"(std **{statistics.stdev(gaps) if len(gaps) > 1 else 0.0:.4f}**)."
        )
    else:
        lines.append("- No gap values computed.")
    lines.extend(
        [
            "",
            "## Selector choices",
            "",
            "The budgeted selector frequency is in `frontier_allocation_controller_selector.csv` (one row per dataset × budget).",
            "",
            "## Honest limits",
            "",
            "- **Simulator mode** (default): HF examples provide questions/gold answers; branch generation is **not** a real LLM—accuracy is a **process proxy** for allocation dynamics and oracle gaps, not benchmark SOTA.",
            "- **OpenAI mode** (`--use-openai-api`): real generations; requires `OPENAI_API_KEY` and is rate/cost limited.",
            "- **Verifier-guided search** uses `SimulatedScorerVerifier` in simulation or `LLMVerifyProxyVerifier` with API—neither is a trained PRM.",
            "- **GPQA Diamond** (`Idavidrein/gpqa`): often gated on the Hub. Use `--try-gpqa` to include it after `huggingface-cli login` and accepting dataset terms; failures are recorded in `frontier_allocation_execution_report.json` and the run continues for other datasets.",
            "- In **simulation**, per-example **oracle** accuracy over eight families can be very high (often 1.0 on small eval splits) because at least one stochastic path may hit the gold answer—report **oracle gap** and **anti-collapse** mechanics, not benchmark SOTA.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    budgets = _parse_budgets(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)
    datasets = _parse_datasets(args.datasets)
    if args.try_gpqa and "Idavidrein/gpqa" not in datasets:
        datasets.append("Idavidrein/gpqa")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    completed: list[str] = []
    failed: list[dict[str, str]] = []
    all_strategy: list[dict[str, Any]] = []
    all_selector: list[dict[str, Any]] = []
    all_per_ex: list[dict[str, Any]] = []
    all_anti: list[dict[str, Any]] = []

    for i, ds in enumerate(datasets):
        ds_seed = args.seed + i * 9973
        rng = random.Random(ds_seed)
        try:
            block = run_single_dataset_frontier(
                ds,
                subset_size=args.subset_size,
                seed=ds_seed,
                budgets=budgets,
                calibration_ratio=args.calibration_ratio,
                adaptive_grid=adaptive_grid,
                use_openai_api=args.use_openai_api,
                openai_model=args.openai_model,
                temperature=args.temperature,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
                vgs_candidates=args.vgs_candidates,
                vgs_min_expansions=args.vgs_min_expansions,
                rng=rng,
            )
        except Exception as exc:  # noqa: BLE001 — record and continue for optional datasets
            failed.append({"dataset": ds, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
            continue

        completed.append(ds)
        all_strategy.extend(block["strategy_rows"])
        all_selector.extend(block["selector_rows"])
        all_per_ex.extend(block["per_example_eval_rows"])
        all_anti.extend(block["anti_collapse_rows"])

        with (run_dir / f"per_example_eval__{ds.replace('/', '_')}.jsonl").open("w", encoding="utf-8") as f:
            for row in block["per_example_eval_rows"]:
                f.write(json.dumps(row, default=str) + "\n")

    gaps = [float(r["oracle_gap_accuracy"]) for r in all_selector]

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "datasets_requested": datasets,
        "datasets_completed": completed,
        "datasets_failed": failed,
        "subset_size": args.subset_size,
        "seed": args.seed,
        "budgets": budgets,
        "calibration_ratio": args.calibration_ratio,
        "adaptive_min_expand_grid": adaptive_grid,
        "use_openai_api": args.use_openai_api,
        "openai_model": args.openai_model,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "vgs_candidates": args.vgs_candidates,
        "vgs_min_expansions": args.vgs_min_expansions,
        "mean_oracle_gap": statistics.mean(gaps) if gaps else None,
    }
    (run_dir / "frontier_allocation_execution_report.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    eval_only = [r for r in all_strategy if r.get("split") == "eval"]
    _write_csv(
        run_dir / "frontier_budget_dataset_summary.csv",
        [
            "dataset",
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
        eval_only,
    )
    _write_csv(
        run_dir / "frontier_allocation_oracle_gap.csv",
        [
            "dataset",
            "budget",
            "selected_strategy",
            "selected_strategy_eval_accuracy",
            "oracle_eval_accuracy_over_strategy_frontier",
            "oracle_gap_accuracy",
            "selected_strategy_eval_avg_actions",
        ],
        all_selector,
    )
    _write_csv(
        run_dir / "frontier_allocation_controller_selector.csv",
        ["dataset", "budget", "selected_strategy", "selected_strategy_calib_accuracy", "selected_strategy_eval_accuracy"],
        all_selector,
    )
    _write_csv(
        run_dir / "anti_collapse_min_expand_comparison.csv",
        [
            "dataset",
            "budget",
            "min_expand_k",
            "accuracy",
            "avg_actions",
            "avg_expansions",
            "avg_verifications",
            "mean_prune_share_of_actions",
            "mean_forced_expand_share",
            "mean_action_trace_length",
            "examples_with_action_trace",
        ],
        all_anti,
    )

    (run_dir / "new_paper_frontier_interpretation.md").write_text(
        _interpretation_md(run_id, completed, failed, gaps, all_selector),
        encoding="utf-8",
    )

    print(str(run_dir))
    if failed:
        print("WARN: some datasets failed:", file=sys.stderr)
        for item in failed:
            print(f"  {item['dataset']}: {item['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
