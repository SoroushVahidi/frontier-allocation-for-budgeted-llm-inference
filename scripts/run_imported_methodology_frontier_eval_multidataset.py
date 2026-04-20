#!/usr/bin/env python3
"""Multi-dataset imported-methodology frontier evaluation.

Produces the same artifact family as `run_imported_methodology_frontier_eval.py`,
with an added `dataset` column and merged summary across datasets.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
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
    p = argparse.ArgumentParser(description="Run multi-dataset imported-methodology frontier evaluation")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,Idavidrein/gpqa")
    p.add_argument("--subset-size", type=int, default=30)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument("--budgets", default="8,10")
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--api-backend", choices=("simulator", "openai", "groq", "gemini"), default="simulator")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--bt-pairwise-model-path", default="")
    p.add_argument("--bt-pairwise-reliability-model-path", default="")
    p.add_argument("--promoted-controller-name", default="strict_coupled_tie_aware_promoted")
    p.add_argument("--output-root", default="outputs/imported_methodology_frontier_eval")
    p.add_argument("--run-id", default="")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _row_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(str(r["example_id"]), str(r["strategy"])): r for r in rows}


def _resolve_adaptive_method(available: set[str]) -> str:
    priority = [
        "adaptive_bt_pairwise_reliability",
        "adaptive_bt_pairwise",
        "adaptive_budget_guarded",
        "adaptive_min_expand_1",
    ]
    for m in priority:
        if m in available:
            return m
    return sorted(available)[0] if available else ""


@dataclass
class EvalBlock:
    dataset: str
    budget: int
    method_rows: list[dict[str, Any]]
    oracle_rows: list[dict[str, Any]]
    matched_rows: list[dict[str, Any]]
    slice_rows: list[dict[str, Any]]


def run_budget_eval(dataset: str, budget: int, calib_examples: list[Any], eval_examples: list[Any], args: argparse.Namespace, adaptive_grid: list[int], rng: random.Random) -> EvalBlock:
    use_remote = args.api_backend != "simulator"
    gen_factory = generator_factory_for_mode(
        use_openai_api=use_remote,
        rng=rng,
        openai_model=args.model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        api_provider=(None if not use_remote else args.api_backend),
    )

    strategies = build_frontier_strategies(
        gen_factory,
        budget,
        adaptive_grid,
        rng,
        use_openai_api=use_remote,
        vgs_candidates=args.vgs_candidates,
        vgs_min_expansions=args.vgs_min_expansions,
        include_budget_guarded_adaptive=True,
        bt_pairwise_model_path=(args.bt_pairwise_model_path or None),
        bt_pairwise_reliability_model_path=(args.bt_pairwise_reliability_model_path or None),
    )

    fixed_baselines = ["reasoning_greedy", "self_consistency_3", "reasoning_beam2", "verifier_guided_search", "program_of_thought"]

    _, calib_rows = evaluate_strategies_on_examples(calib_examples, strategies)
    _, eval_rows = evaluate_strategies_on_examples(eval_examples, strategies)
    eval_index = _row_index(eval_rows)
    eval_by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        eval_by_ex.setdefault(str(row["example_id"]), []).append(row)

    available = set(str(k) for k in strategies)
    adaptive_method = _resolve_adaptive_method(available)
    comparable = [m for m in fixed_baselines if m in available]
    if adaptive_method and adaptive_method not in comparable:
        comparable.append(adaptive_method)

    oracle_best: dict[str, dict[str, Any]] = {}
    for ex_id, rows in eval_by_ex.items():
        usable = [r for r in rows if str(r["strategy"]) in set(comparable)]
        oracle_best[ex_id] = min(
            usable,
            key=lambda r: (
                0 if bool(r["is_correct"]) else 1,
                float(r["actions_used"]),
                float(r["expansions"]),
                float(r["verifications"]),
                str(r["strategy"]),
            ),
        )
    oracle_acc = sum(1 for r in oracle_best.values() if bool(r["is_correct"])) / max(1, len(oracle_best))

    method_rows = []
    oracle_rows = []
    for method in comparable:
        selected = [eval_index[(ex, method)] for ex in sorted(eval_by_ex)]
        n = max(1, len(selected))
        acc = sum(1 for r in selected if bool(r["is_correct"])) / n
        row = {
            "dataset": dataset,
            "budget": budget,
            "method": method,
            "n_examples": n,
            "accuracy": acc,
            "avg_actions": sum(float(r["actions_used"]) for r in selected) / n,
            "avg_expansions": sum(float(r["expansions"]) for r in selected) / n,
            "avg_verifications": sum(float(r["verifications"]) for r in selected) / n,
            "budget_exhaustion_rate": sum(1 for r in selected if bool(r["budget_exhausted"])) / n,
            "oracle_accuracy": oracle_acc,
            "gap_to_oracle": oracle_acc - acc,
        }
        method_rows.append(row)
        oracle_rows.append({
            "dataset": dataset,
            "budget": budget,
            "method": method,
            "method_accuracy": acc,
            "oracle_accuracy": oracle_acc,
            "gap_to_oracle": oracle_acc - acc,
        })

    method_rows.append({
        "dataset": dataset,
        "budget": budget,
        "method": "oracle_frontier_upper_bound",
        "n_examples": len(eval_by_ex),
        "accuracy": oracle_acc,
        "avg_actions": statistics.mean(float(r["actions_used"]) for r in oracle_best.values()),
        "avg_expansions": statistics.mean(float(r["expansions"]) for r in oracle_best.values()),
        "avg_verifications": statistics.mean(float(r["verifications"]) for r in oracle_best.values()),
        "budget_exhaustion_rate": statistics.mean(1.0 if bool(r["budget_exhausted"]) else 0.0 for r in oracle_best.values()),
        "oracle_accuracy": oracle_acc,
        "gap_to_oracle": 0.0,
    })

    # expose promoted name if strict-coupled/tie-aware is not wired into frontier controllers.
    if adaptive_method:
        promoted_row = next((r for r in method_rows if r["method"] == adaptive_method), None)
        if promoted_row is not None and args.promoted_controller_name and args.promoted_controller_name != adaptive_method:
            promoted_alias = dict(promoted_row)
            promoted_alias["method"] = args.promoted_controller_name
            promoted_alias["source_controller"] = adaptive_method
            promoted_alias["promotion_mode"] = "alias_bridge"
            method_rows.append(promoted_alias)
            oracle_rows.append({
                "dataset": dataset,
                "budget": budget,
                "method": args.promoted_controller_name,
                "method_accuracy": promoted_alias["accuracy"],
                "oracle_accuracy": oracle_acc,
                "gap_to_oracle": promoted_alias["gap_to_oracle"],
            })

    matched_rows = []
    if adaptive_method:
        for baseline in fixed_baselines:
            if baseline not in available:
                continue
            wins = losses = ties = 0
            for ex_id in sorted(eval_by_ex):
                a = eval_index[(ex_id, adaptive_method)]
                b = eval_index[(ex_id, baseline)]
                av = 1 if bool(a["is_correct"]) else 0
                bv = 1 if bool(b["is_correct"]) else 0
                if av > bv:
                    wins += 1
                elif av < bv:
                    losses += 1
                else:
                    ties += 1
            matched_rows.append({
                "dataset": dataset,
                "budget": budget,
                "adaptive_method": adaptive_method,
                "baseline_method": baseline,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "n": wins + losses + ties,
                "win_rate": wins / max(1, wins + losses + ties),
                "net_win_rate": (wins - losses) / max(1, wins + losses + ties),
            })

    # same hard/easy proxy as single-dataset evaluator
    calib_index = _row_index(calib_rows)
    hard_ids = set()
    if adaptive_method:
        for ex in calib_examples:
            ex_id = str(ex.example_id)
            r = calib_index.get((ex_id, adaptive_method))
            if r and ((not bool(r["is_correct"])) or bool(r["budget_exhausted"])):
                hard_ids.add(ex_id)

    calib_lens = {str(ex.example_id): len(str(ex.question).split()) for ex in calib_examples}
    eval_lens = {str(ex.example_id): len(str(ex.question).split()) for ex in eval_examples}
    hard_threshold = statistics.median(calib_lens.values()) if calib_lens else 0.0
    if hard_ids and any(eid in calib_lens for eid in hard_ids):
        hard_threshold = statistics.mean(calib_lens[eid] for eid in hard_ids if eid in calib_lens)
    eval_hard = {eid for eid, ql in eval_lens.items() if float(ql) >= float(hard_threshold)}

    slice_rows = []
    for method in comparable + ["oracle_frontier_upper_bound"]:
        if method == "oracle_frontier_upper_bound":
            by_ex = {eid: row for eid, row in oracle_best.items()}
        else:
            by_ex = {eid: eval_index[(eid, method)] for eid in sorted(eval_by_ex)}
        hard_rows = [by_ex[eid] for eid in sorted(eval_hard) if eid in by_ex]
        easy_rows = [by_ex[eid] for eid in sorted(by_ex) if eid not in eval_hard]
        hard_n = len(hard_rows)
        easy_n = len(easy_rows)
        hard_acc = sum(1 for r in hard_rows if bool(r["is_correct"])) / max(1, hard_n)
        easy_acc = sum(1 for r in easy_rows if bool(r["is_correct"])) / max(1, easy_n)
        hard_actions = sum(float(r["actions_used"]) for r in hard_rows) / max(1, hard_n)
        easy_actions = sum(float(r["actions_used"]) for r in easy_rows) / max(1, easy_n)
        slice_rows.append({
            "dataset": dataset,
            "budget": budget,
            "method": method,
            "hard_n": hard_n,
            "hard_accuracy": hard_acc,
            "easy_n": easy_n,
            "easy_accuracy": easy_acc,
            "hard_minus_easy_accuracy": hard_acc - easy_acc,
            "hard_avg_actions": hard_actions,
            "easy_avg_actions": easy_actions,
        })

    return EvalBlock(dataset=dataset, budget=budget, method_rows=method_rows, oracle_rows=oracle_rows, matched_rows=matched_rows, slice_rows=slice_rows)


def main() -> None:
    args = parse_args()
    budgets = sorted(set(_parse_int_list(args.budgets)))
    datasets = _parse_list(args.datasets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)

    run_id = args.run_id.strip() if args.run_id.strip() else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    all_methods: list[dict[str, Any]] = []
    all_oracle: list[dict[str, Any]] = []
    all_matched: list[dict[str, Any]] = []
    all_slices: list[dict[str, Any]] = []

    dataset_blocks = []
    for d_idx, dataset in enumerate(datasets):
        examples = load_pilot_examples(dataset, args.subset_size, args.seed + d_idx * 1009)
        split_idx = max(1, min(len(examples) - 1, int(len(examples) * args.calibration_ratio)))
        calib_examples = examples[:split_idx]
        eval_examples = examples[split_idx:]
        dataset_blocks.append({
            "dataset": dataset,
            "subset_size": args.subset_size,
            "n_calibration": len(calib_examples),
            "n_eval": len(eval_examples),
            "seed": args.seed + d_idx * 1009,
        })

        for budget in budgets:
            out = run_budget_eval(
                dataset=dataset,
                budget=budget,
                calib_examples=calib_examples,
                eval_examples=eval_examples,
                args=args,
                adaptive_grid=adaptive_grid,
                rng=random.Random(args.seed + d_idx * 1009 + budget * 17),
            )
            all_methods.extend(out.method_rows)
            all_oracle.extend(out.oracle_rows)
            all_matched.extend(out.matched_rows)
            all_slices.extend(out.slice_rows)

    frontier_rows = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in all_methods:
        grouped.setdefault((str(row["dataset"]), str(row["method"])), []).append(row)
    for (dataset, method), rows in grouped.items():
        for row in sorted(rows, key=lambda r: int(r["budget"])):
            frontier_rows.append({
                "dataset": dataset,
                "method": method,
                "budget": int(row["budget"]),
                "accuracy": float(row["accuracy"]),
                "avg_actions": float(row["avg_actions"]),
                "gap_to_oracle": float(row["gap_to_oracle"]),
            })

    _write_csv(run_dir / "method_metrics.csv", all_methods)
    _write_csv(run_dir / "oracle_gap_summary.csv", all_oracle)
    _write_csv(run_dir / "matched_comparison_summary.csv", all_matched)
    _write_csv(run_dir / "budget_frontier_summary.csv", frontier_rows)
    _write_csv(run_dir / "signal_slice_summary.csv", all_slices)

    summary = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "track": "new-paper-fixed-budget-frontier-multidataset",
        "datasets": dataset_blocks,
        "budgets": budgets,
        "adaptive_min_expand_grid": adaptive_grid,
        "api_backend": args.api_backend,
        "model": args.model,
        "promoted_controller_name": args.promoted_controller_name,
        "promoted_controller_bridge": {
            "mode": "alias_bridge",
            "note": "Strict-coupled/tie-aware controller is not yet a native frontier_matrix_core strategy; alias currently points to selected adaptive method row per dataset-budget.",
        },
        "candidate_method_pool": sorted({str(r["method"]) for r in all_methods}),
        "files": {
            "method_metrics_csv": str(run_dir / "method_metrics.csv"),
            "oracle_gap_csv": str(run_dir / "oracle_gap_summary.csv"),
            "matched_comparison_csv": str(run_dir / "matched_comparison_summary.csv"),
            "budget_frontier_csv": str(run_dir / "budget_frontier_summary.csv"),
            "signal_slice_csv": str(run_dir / "signal_slice_summary.csv"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
