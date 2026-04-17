#!/usr/bin/env python3
"""Bounded methodology-integration evaluation for fixed-budget frontier allocation.

This script adapts evaluation/reporting patterns from the historical
`-adaptive-llm-inference` repository to the current branch-allocation setting.

Adapted ideas:
- matched comparisons on identical eval examples
- fixed vs adaptive vs oracle summaries
- oracle headroom / gap-to-oracle accounting
- budget-aware frontier summaries
- signal-separation summaries on hard vs easy slices
- manuscript-facing machine-readable artifacts
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
    p = argparse.ArgumentParser(description="Run imported-methodology frontier evaluation (new-paper track)")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument("--budgets", default="8,10,12")
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
    p.add_argument("--output-root", default="outputs/imported_methodology_frontier_eval")
    p.add_argument("--run-id", default="")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _row_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        out[(str(row["example_id"]), str(row["strategy"]))] = row
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _oracle_row_for_example(rows: list[dict[str, Any]], strategies: set[str]) -> dict[str, Any]:
    usable = [r for r in rows if str(r["strategy"]) in strategies]
    if not usable:
        return min(rows, key=lambda r: (float(r["actions_used"]), str(r["strategy"])))
    return min(
        usable,
        key=lambda r: (
            0 if bool(r["is_correct"]) else 1,
            float(r["actions_used"]),
            float(r["expansions"]),
            float(r["verifications"]),
            str(r["strategy"]),
        ),
    )


def _method_metrics(rows: list[dict[str, Any]], method: str, budget: int, oracle_acc: float) -> dict[str, Any]:
    n = max(1, len(rows))
    acc = sum(1 for r in rows if bool(r["is_correct"])) / n
    avg_actions = sum(float(r["actions_used"]) for r in rows) / n
    avg_exp = sum(float(r["expansions"]) for r in rows) / n
    avg_ver = sum(float(r["verifications"]) for r in rows) / n
    exhausted = sum(1 for r in rows if bool(r["budget_exhausted"])) / n
    return {
        "budget": budget,
        "method": method,
        "n_examples": n,
        "accuracy": acc,
        "avg_actions": avg_actions,
        "avg_expansions": avg_exp,
        "avg_verifications": avg_ver,
        "budget_exhaustion_rate": exhausted,
        "oracle_accuracy": oracle_acc,
        "gap_to_oracle": oracle_acc - acc,
    }


def _slice_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {"n": 0.0, "accuracy": 0.0, "avg_actions": 0.0}
    return {
        "n": float(n),
        "accuracy": sum(1 for r in rows if bool(r["is_correct"])) / n,
        "avg_actions": sum(float(r["actions_used"]) for r in rows) / n,
    }


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
class BudgetEval:
    budget: int
    method_rows: list[dict[str, Any]]
    oracle_rows: list[dict[str, Any]]
    matched_rows: list[dict[str, Any]]
    slice_rows: list[dict[str, Any]]


def run_budget_eval(
    *,
    budget: int,
    calib_examples: list[Any],
    eval_examples: list[Any],
    rng: random.Random,
    args: argparse.Namespace,
    adaptive_grid: list[int],
) -> BudgetEval:
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

    fixed_baselines = [
        "reasoning_greedy",
        "self_consistency_3",
        "reasoning_beam2",
        "verifier_guided_search",
        "program_of_thought",
    ]

    _, calib_rows = evaluate_strategies_on_examples(calib_examples, strategies)
    _, eval_rows = evaluate_strategies_on_examples(eval_examples, strategies)

    eval_by_example: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        eval_by_example.setdefault(str(row["example_id"]), []).append(row)

    available = {str(k) for k in strategies.keys()}
    adaptive_method = _resolve_adaptive_method(available)

    comparable_methods = [m for m in fixed_baselines if m in available]
    if adaptive_method and adaptive_method not in comparable_methods:
        comparable_methods.append(adaptive_method)
    if "adaptive_budget_guarded" in available and "adaptive_budget_guarded" not in comparable_methods:
        comparable_methods.append("adaptive_budget_guarded")

    oracle_best: dict[str, dict[str, Any]] = {}
    oracle_strats = set(comparable_methods)
    for ex_id, rows in eval_by_example.items():
        oracle_best[ex_id] = _oracle_row_for_example(rows, oracle_strats)
    oracle_acc = sum(1 for r in oracle_best.values() if bool(r["is_correct"])) / max(1, len(oracle_best))

    eval_index = _row_index(eval_rows)
    method_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []

    for method in comparable_methods:
        selected = [eval_index[(ex_id, method)] for ex_id in sorted(eval_by_example)]
        mm = _method_metrics(selected, method, budget, oracle_acc)
        method_rows.append(mm)
        oracle_rows.append(
            {
                "budget": budget,
                "method": method,
                "method_accuracy": mm["accuracy"],
                "oracle_accuracy": oracle_acc,
                "gap_to_oracle": mm["gap_to_oracle"],
            }
        )

    method_rows.append(
        {
            "budget": budget,
            "method": "oracle_frontier_upper_bound",
            "n_examples": len(eval_by_example),
            "accuracy": oracle_acc,
            "avg_actions": statistics.mean(float(r["actions_used"]) for r in oracle_best.values()),
            "avg_expansions": statistics.mean(float(r["expansions"]) for r in oracle_best.values()),
            "avg_verifications": statistics.mean(float(r["verifications"]) for r in oracle_best.values()),
            "budget_exhaustion_rate": statistics.mean(1.0 if bool(r["budget_exhausted"]) else 0.0 for r in oracle_best.values()),
            "oracle_accuracy": oracle_acc,
            "gap_to_oracle": 0.0,
        }
    )

    matched_rows: list[dict[str, Any]] = []
    if adaptive_method:
        for baseline in fixed_baselines:
            if baseline not in available:
                continue
            wins = losses = ties = 0
            for ex_id in sorted(eval_by_example):
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
            matched_rows.append(
                {
                    "budget": budget,
                    "adaptive_method": adaptive_method,
                    "baseline_method": baseline,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "n": wins + losses + ties,
                    "win_rate": wins / max(1, wins + losses + ties),
                    "net_win_rate": (wins - losses) / max(1, wins + losses + ties),
                }
            )

    # Signal-separation: hard/easy slices derived on calibration from adaptive method outcome.
    calib_index = _row_index(calib_rows)
    hard_ids: set[str] = set()
    if adaptive_method:
        for ex in calib_examples:
            ex_id = str(ex.example_id)
            r = calib_index.get((ex_id, adaptive_method))
            if not r:
                continue
            if (not bool(r["is_correct"])) or bool(r["budget_exhausted"]):
                hard_ids.add(ex_id)

    # transfer the hardness rule to eval through lexical nearest-neighbor proxy (question length threshold)
    calib_q_lens = {str(ex.example_id): len(str(ex.question).split()) for ex in calib_examples}
    eval_q_lens = {str(ex.example_id): len(str(ex.question).split()) for ex in eval_examples}
    hard_threshold = statistics.median(calib_q_lens.values()) if calib_q_lens else 0.0
    if hard_ids and calib_q_lens:
        hard_threshold = statistics.mean(calib_q_lens[eid] for eid in hard_ids if eid in calib_q_lens) if any(eid in calib_q_lens for eid in hard_ids) else hard_threshold

    eval_hard_ids = {eid for eid, ql in eval_q_lens.items() if float(ql) >= float(hard_threshold)}

    slice_rows: list[dict[str, Any]] = []
    for method in comparable_methods + ["oracle_frontier_upper_bound"]:
        if method == "oracle_frontier_upper_bound":
            m_by_ex = {eid: row for eid, row in oracle_best.items()}
            hard_rows = [m_by_ex[eid] for eid in sorted(eval_hard_ids) if eid in m_by_ex]
            easy_rows = [m_by_ex[eid] for eid in sorted(m_by_ex) if eid not in eval_hard_ids]
        else:
            m_by_ex = {eid: eval_index[(eid, method)] for eid in sorted(eval_by_example)}
            hard_rows = [m_by_ex[eid] for eid in sorted(eval_hard_ids) if eid in m_by_ex]
            easy_rows = [m_by_ex[eid] for eid in sorted(m_by_ex) if eid not in eval_hard_ids]

        hm = _slice_metrics(hard_rows)
        em = _slice_metrics(easy_rows)
        slice_rows.append(
            {
                "budget": budget,
                "method": method,
                "hard_n": int(hm["n"]),
                "hard_accuracy": hm["accuracy"],
                "easy_n": int(em["n"]),
                "easy_accuracy": em["accuracy"],
                "hard_minus_easy_accuracy": hm["accuracy"] - em["accuracy"],
                "hard_avg_actions": hm["avg_actions"],
                "easy_avg_actions": em["avg_actions"],
            }
        )

    return BudgetEval(
        budget=budget,
        method_rows=method_rows,
        oracle_rows=oracle_rows,
        matched_rows=matched_rows,
        slice_rows=slice_rows,
    )


def main() -> None:
    args = parse_args()
    budgets = sorted(set(_parse_int_list(args.budgets)))
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)
    rng = random.Random(args.seed)

    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    split_idx = max(1, min(len(examples) - 1, int(len(examples) * args.calibration_ratio)))
    calib_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]

    run_id = args.run_id.strip() if args.run_id.strip() else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    all_methods: list[dict[str, Any]] = []
    all_oracle: list[dict[str, Any]] = []
    all_matched: list[dict[str, Any]] = []
    all_slices: list[dict[str, Any]] = []

    for b in budgets:
        out = run_budget_eval(
            budget=b,
            calib_examples=calib_examples,
            eval_examples=eval_examples,
            rng=random.Random(args.seed + b * 17),
            args=args,
            adaptive_grid=adaptive_grid,
        )
        all_methods.extend(out.method_rows)
        all_oracle.extend(out.oracle_rows)
        all_matched.extend(out.matched_rows)
        all_slices.extend(out.slice_rows)

    # Frontier view across budgets.
    frontier_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in all_methods:
        grouped.setdefault(str(row["method"]), []).append(row)
    for method, rows in grouped.items():
        for row in sorted(rows, key=lambda r: int(r["budget"])):
            frontier_rows.append(
                {
                    "method": method,
                    "budget": int(row["budget"]),
                    "accuracy": float(row["accuracy"]),
                    "avg_actions": float(row["avg_actions"]),
                    "gap_to_oracle": float(row["gap_to_oracle"]),
                }
            )

    _write_csv(run_dir / "method_metrics.csv", all_methods)
    _write_csv(run_dir / "oracle_gap_summary.csv", all_oracle)
    _write_csv(run_dir / "matched_comparison_summary.csv", all_matched)
    _write_csv(run_dir / "budget_frontier_summary.csv", frontier_rows)
    _write_csv(run_dir / "signal_slice_summary.csv", all_slices)

    summary = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "track": "new-paper-fixed-budget-frontier",
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "n_calibration": len(calib_examples),
        "n_eval": len(eval_examples),
        "seed": args.seed,
        "budgets": budgets,
        "adaptive_min_expand_grid": adaptive_grid,
        "api_backend": args.api_backend,
        "model": args.model,
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
