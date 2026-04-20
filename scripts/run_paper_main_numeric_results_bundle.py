#!/usr/bin/env python3
"""Run the paper-facing matched-budget numeric results bundle.

This script is a thin wrapper over the canonical frontier evaluation components
in `experiments/frontier_matrix_core.py`, with added:
- strict method filtering for manuscript-facing comparisons,
- multi-seed aggregation with uncertainty,
- resume-safe checkpoints,
- machine-readable manifest/config outputs,
- markdown summary suitable for docs.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import PilotExample, extract_final_answer
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
    resolve_api_key_for_provider,
)
from experiments.hf_datasets import check_git_dataset_access, sample_git_dataset_examples


DEFAULT_DATASETS = [
    "openai/gsm8k",
    "EleutherAI/hendrycks_math",
    "HuggingFaceH4/MATH-500",
    "Idavidrein/gpqa",
    "Hothan/OlympiadBench",
    "meituan-longcat/AMO-Bench",
]
DEFAULT_BUDGETS = [6, 8, 10]
DEFAULT_SEEDS = [42, 43, 44]
DEFAULT_METHODS = [
    "strict_coupled_tie_aware_promoted",
    "adaptive_budget_guarded",
    "reasoning_beam2",
    "self_consistency_3",
    "reasoning_greedy",
    "verifier_guided_search",
]


def parse_args() -> argparse.Namespace:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    p = argparse.ArgumentParser(description="Run paper main numeric results bundle (matched budgets)")
    p.add_argument("--datasets", default=",".join(DEFAULT_DATASETS))
    p.add_argument("--include-natural-plan", action="store_true")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    p.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_SEEDS))
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    p.add_argument("--promoted-controller-name", default="strict_coupled_tie_aware_promoted")
    p.add_argument("--promoted-controller-source", default="adaptive_budget_guarded")
    p.add_argument("--api-backend", choices=("simulator", "openai", "groq", "gemini"), default="simulator")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=60)
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--output-dir", default=f"outputs/paper_main_numeric_results_bundle_{today}")
    p.add_argument("--resume", action="store_true")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _stdev(vals: list[float]) -> float:
    n = len(vals)
    if n <= 1:
        return 0.0
    mu = _mean(vals)
    return math.sqrt(sum((x - mu) ** 2 for x in vals) / (n - 1))


def _stderr(vals: list[float]) -> float:
    n = len(vals)
    if n <= 1:
        return 0.0
    return _stdev(vals) / math.sqrt(n)


def _load_examples_for_dataset(dataset: str, subset_size: int, seed: int) -> tuple[list[PilotExample], str]:
    if dataset == "google-deepmind/natural-plan":
        rows = sample_git_dataset_examples(dataset, pilot_size=subset_size, seed=seed)
        examples = [
            PilotExample(
                example_id=r["example_id"],
                question=r["question"],
                answer=extract_final_answer(r["answer"]),
            )
            for r in rows
        ]
        return examples, "git_clone"
    examples = load_pilot_examples(dataset, subset_size, seed)
    return examples, "huggingface"


def _select_eval_rows(
    rows: list[dict[str, Any]],
    selected_methods: list[str],
    promoted_name: str,
    promoted_source: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_strategy = {str(r["strategy"]): [] for r in rows}
    for row in rows:
        by_strategy[str(row["strategy"])].append(row)

    missing: list[str] = []
    selected_rows: list[dict[str, Any]] = []
    for method in selected_methods:
        if method in by_strategy:
            selected_rows.extend(by_strategy[method])
            continue
        if method == promoted_name and promoted_source in by_strategy:
            promoted_alias = []
            for r in by_strategy[promoted_source]:
                rr = dict(r)
                rr["strategy"] = promoted_name
                rr["source_controller"] = promoted_source
                rr["promotion_mode"] = "alias_bridge"
                promoted_alias.append(rr)
            selected_rows.extend(promoted_alias)
            continue
        missing.append(method)
    return selected_rows, missing


def _build_metrics_rows(
    dataset: str,
    seed: int,
    budget: int,
    n_eval_examples: int,
    method_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in method_rows:
        by_method.setdefault(str(row["strategy"]), []).append(row)
    for method, rows in sorted(by_method.items()):
        n = max(1, len(rows))
        out.append(
            {
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "method": method,
                "n_eval_examples": n_eval_examples,
                "accuracy": sum(1 for r in rows if bool(r["is_correct"])) / n,
                "avg_actions": sum(float(r["actions_used"]) for r in rows) / n,
                "avg_expansions": sum(float(r["expansions"]) for r in rows) / n,
                "avg_verifications": sum(float(r["verifications"]) for r in rows) / n,
                "budget_exhaustion_rate": sum(1 for r in rows if bool(r["budget_exhausted"])) / n,
            }
        )
    return out


def _aggregate(
    rows: list[dict[str, Any]],
    group_keys: list[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        grouped.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for key, vals in sorted(grouped.items()):
        acc = [float(v["accuracy"]) for v in vals]
        acts = [float(v["avg_actions"]) for v in vals]
        ex = [float(v["avg_expansions"]) for v in vals]
        ver = [float(v["avg_verifications"]) for v in vals]
        bex = [float(v["budget_exhaustion_rate"]) for v in vals]
        row: dict[str, Any] = {k: v for k, v in zip(group_keys, key)}
        row.update(
            {
                "n_rows": len(vals),
                "mean_accuracy": _mean(acc),
                "std_accuracy": _stdev(acc),
                "stderr_accuracy": _stderr(acc),
                "mean_avg_actions": _mean(acts),
                "std_avg_actions": _stdev(acts),
                "stderr_avg_actions": _stderr(acts),
                "mean_avg_expansions": _mean(ex),
                "mean_avg_verifications": _mean(ver),
                "mean_budget_exhaustion_rate": _mean(bex),
            }
        )
        out.append(row)
    return out


def main() -> None:
    args = parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    use_remote_api = args.api_backend != "simulator"
    if use_remote_api and not resolve_api_key_for_provider(args.api_backend):
        raise SystemExit(
            f"Missing API key for backend '{args.api_backend}'. "
            "Set environment key or run with --api-backend simulator."
        )

    datasets = _parse_list(args.datasets)
    if args.include_natural_plan and "google-deepmind/natural-plan" not in datasets:
        datasets.append("google-deepmind/natural-plan")
    budgets = sorted(set(_parse_int_list(args.budgets)))
    seeds = sorted(set(_parse_int_list(args.seeds)))
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)
    selected_methods = _parse_list(args.methods)

    skipped_datasets: list[dict[str, str]] = []
    if "google-deepmind/natural-plan" in datasets:
        np_status = check_git_dataset_access("google-deepmind/natural-plan")
        if not np_status.get("ok", False):
            datasets = [d for d in datasets if d != "google-deepmind/natural-plan"]
            skipped_datasets.append(
                {
                    "dataset": "google-deepmind/natural-plan",
                    "reason": "local clone missing/incomplete; skipping",
                    "details": json.dumps(np_status, sort_keys=True),
                }
            )

    checkpoint_path = output_dir / "resume_state.json"
    per_seed_csv = output_dir / "per_seed_method_metrics.csv"
    skipped_csv = output_dir / "skipped_items.csv"

    completed_blocks: set[tuple[str, int, int]] = set()
    all_rows: list[dict[str, Any]] = []
    skipped_items: list[dict[str, str]] = []
    if args.resume:
        if checkpoint_path.exists():
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            completed_blocks = {
                (str(x["dataset"]), int(x["seed"]), int(x["budget"]))
                for x in payload.get("completed_blocks", [])
            }
        all_rows = [dict(r) for r in _read_csv(per_seed_csv)]
        skipped_items = [dict(r) for r in _read_csv(skipped_csv)]

    skipped_items.extend(skipped_datasets)

    for dataset in datasets:
        for seed in seeds:
            examples, data_source = _load_examples_for_dataset(dataset, args.subset_size, seed)
            split_idx = max(1, min(len(examples) - 1, int(len(examples) * args.calibration_ratio)))
            eval_examples = examples[split_idx:]
            for budget in budgets:
                block_key = (dataset, seed, budget)
                if block_key in completed_blocks:
                    continue
                rng = random.Random(seed * 1009 + budget * 17 + abs(hash(dataset)) % 100000)
                gen_factory = generator_factory_for_mode(
                    use_openai_api=use_remote_api,
                    rng=rng,
                    openai_model=args.model,
                    temperature=args.temperature,
                    max_output_tokens=args.max_output_tokens,
                    timeout_seconds=args.timeout_seconds,
                    api_provider=(args.api_backend if use_remote_api else None),
                )
                strategies = build_frontier_strategies(
                    gen_factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=use_remote_api,
                    vgs_candidates=args.vgs_candidates,
                    vgs_min_expansions=args.vgs_min_expansions,
                    include_budget_guarded_adaptive=True,
                )
                _, eval_rows = evaluate_strategies_on_examples(eval_examples, strategies)
                selected_rows, missing_methods = _select_eval_rows(
                    eval_rows,
                    selected_methods,
                    promoted_name=args.promoted_controller_name,
                    promoted_source=args.promoted_controller_source,
                )
                for method in missing_methods:
                    skipped_items.append(
                        {
                            "dataset": dataset,
                            "seed": str(seed),
                            "budget": str(budget),
                            "item_type": "method",
                            "item": method,
                            "reason": "method unavailable in built strategy set",
                        }
                    )
                block_rows = _build_metrics_rows(
                    dataset=dataset,
                    seed=seed,
                    budget=budget,
                    n_eval_examples=len(eval_examples),
                    method_rows=selected_rows,
                )
                for row in block_rows:
                    row["data_source"] = data_source
                    all_rows.append(row)
                completed_blocks.add(block_key)

                # Resume checkpoint updated after each completed block.
                _write_csv(per_seed_csv, all_rows)
                _write_csv(skipped_csv, skipped_items)
                checkpoint_path.write_text(
                    json.dumps(
                        {
                            "completed_blocks": [
                                {"dataset": d, "seed": s, "budget": b}
                                for (d, s, b) in sorted(completed_blocks)
                            ]
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

    per_dataset_budget_method = _aggregate(all_rows, ["dataset", "budget", "method"])
    aggregate_method_summary = _aggregate(all_rows, ["method"])
    aggregate_dataset_summary = _aggregate(all_rows, ["dataset", "method"])

    _write_csv(output_dir / "per_dataset_budget_method_metrics.csv", per_dataset_budget_method)
    _write_csv(output_dir / "aggregate_method_summary.csv", aggregate_method_summary)
    _write_csv(output_dir / "aggregate_dataset_summary.csv", aggregate_dataset_summary)

    manifest = {
        "name": "paper_main_numeric_results_bundle",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_paper_main_numeric_results_bundle.py",
        "command": " ".join(sys.argv),
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "config": {
            "datasets": datasets,
            "subset_size": args.subset_size,
            "calibration_ratio": args.calibration_ratio,
            "budgets": budgets,
            "seeds": seeds,
            "adaptive_min_expand_grid": adaptive_grid,
            "methods": selected_methods,
            "promoted_controller_name": args.promoted_controller_name,
            "promoted_controller_source": args.promoted_controller_source,
            "api_backend": args.api_backend,
            "model": args.model,
            "temperature": args.temperature,
            "max_output_tokens": args.max_output_tokens,
            "timeout_seconds": args.timeout_seconds,
            "vgs_candidates": args.vgs_candidates,
            "vgs_min_expansions": args.vgs_min_expansions,
            "resume": args.resume,
        },
        "files": {
            "per_seed_method_metrics_csv": str((output_dir / "per_seed_method_metrics.csv").relative_to(REPO_ROOT)),
            "per_dataset_budget_method_metrics_csv": str(
                (output_dir / "per_dataset_budget_method_metrics.csv").relative_to(REPO_ROOT)
            ),
            "aggregate_method_summary_csv": str((output_dir / "aggregate_method_summary.csv").relative_to(REPO_ROOT)),
            "aggregate_dataset_summary_csv": str((output_dir / "aggregate_dataset_summary.csv").relative_to(REPO_ROOT)),
            "skipped_items_csv": str((output_dir / "skipped_items.csv").relative_to(REPO_ROOT)),
            "resume_state_json": str((output_dir / "resume_state.json").relative_to(REPO_ROOT)),
        },
        "counts": {
            "completed_blocks": len(completed_blocks),
            "metric_rows_per_seed": len(all_rows),
            "skipped_items": len(skipped_items),
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "config.json").write_text(json.dumps(manifest["config"], indent=2), encoding="utf-8")

    summary_lines = [
        "# Paper main numeric results bundle",
        "",
        f"- created_utc: `{manifest['created_utc']}`",
        f"- output_dir: `{manifest['output_dir']}`",
        f"- datasets: `{', '.join(datasets)}`",
        f"- budgets: `{', '.join(str(x) for x in budgets)}`",
        f"- seeds: `{', '.join(str(x) for x in seeds)}`",
        f"- methods: `{', '.join(selected_methods)}`",
        f"- api_backend/model: `{args.api_backend}` / `{args.model}`",
        "",
        "## Key outputs",
        f"- `{manifest['files']['per_dataset_budget_method_metrics_csv']}`",
        f"- `{manifest['files']['aggregate_method_summary_csv']}`",
        f"- `{manifest['files']['aggregate_dataset_summary_csv']}`",
        f"- `{manifest['files']['per_seed_method_metrics_csv']}`",
        f"- `{manifest['files']['skipped_items_csv']}`",
        "",
        "## Notes",
        "- This bundle reports matched-budget numeric comparisons only (no figure generation).",
        "- `strict_coupled_tie_aware_promoted` is currently bridged to an in-repo adaptive controller row when native strategy wiring is unavailable.",
    ]
    (output_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": manifest["output_dir"]}, indent=2))


if __name__ == "__main__":
    main()
