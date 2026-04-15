#!/usr/bin/env python3
"""Run a lightweight matched comparison between repo anchor and external s1 baseline adapter."""

from __future__ import annotations

import argparse
import csv
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

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

METHOD_SPECS: list[dict[str, str]] = [
    {
        "method": "adaptive_min_expand_1",
        "family": "internal_anchor",
        "style": "repo_default_stop_vs_act_anchor",
        "description": "Current default adaptive min-expand controller (anchor baseline).",
    },
    {
        "method": "external_s1_budget_forcing",
        "family": "external_published_baseline",
        "style": "s1_simple_test_time_scaling_budget_forcing",
        "description": "External baseline adapter: s1 inference-time budget forcing behavior.",
    },
]


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Light anchor vs s1 baseline comparison")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--s1-num-ignore-think-end", type=int, default=1)
    p.add_argument("--s1-min-thinking-steps", type=int, default=0)
    p.add_argument("--output-dir", default="outputs/light_anchor_vs_s1_comparison")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    method_catalog = {m["method"]: m for m in METHOD_SPECS}
    method_names = [m["method"] for m in METHOD_SPECS]
    rng_master = random.Random(120413)

    per_seed_rows: list[dict[str, Any]] = []

    for seed in seeds:
        examples = load_pilot_examples(args.dataset, args.subset_size, seed)
        rng = random.Random(rng_master.randint(0, 10**9))
        gen_factory = generator_factory_for_mode(
            False,
            rng,
            "gpt-4.1-mini",
            0.2,
            180,
            45,
        )

        for budget in budgets:
            strategies = build_frontier_strategies(
                gen_factory,
                budget,
                adaptive_grid,
                rng,
                use_openai_api=False,
                include_external_s1_baseline=True,
                s1_num_ignore_think_end=args.s1_num_ignore_think_end,
                s1_min_thinking_steps=args.s1_min_thinking_steps,
            )
            eval_metrics, _ = evaluate_strategies_on_examples(examples, strategies)

            for method in method_names:
                m = eval_metrics.get(method)
                if m is None:
                    continue
                spec = method_catalog[method]
                per_seed_rows.append(
                    {
                        "dataset": args.dataset,
                        "seed": seed,
                        "budget": budget,
                        "method": method,
                        "family": spec["family"],
                        "style": spec["style"],
                        "n_eval_examples": int(m["n_examples"]),
                        "accuracy": float(m["accuracy"]),
                        "avg_actions": float(m["avg_actions"]),
                        "avg_expansions": float(m["avg_expansions"]),
                        "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                    }
                )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in per_seed_rows:
        grouped.setdefault((int(row["budget"]), str(row["method"])), []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for (budget, method), rows in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        acc = [float(r["accuracy"]) for r in rows]
        acts = [float(r["avg_actions"]) for r in rows]
        summary_rows.append(
            {
                "dataset": args.dataset,
                "budget": budget,
                "method": method,
                "family": method_catalog[method]["family"],
                "style": method_catalog[method]["style"],
                "num_seeds": len(rows),
                "mean_accuracy": float(sum(acc) / len(acc)),
                "std_accuracy": float(statistics.pstdev(acc)) if len(acc) > 1 else 0.0,
                "mean_avg_actions": float(sum(acts) / len(acts)),
            }
        )

    by_budget_method = {(int(r["budget"]), str(r["method"])): r for r in summary_rows}
    pairwise_rows: list[dict[str, Any]] = []
    for budget in sorted(set(int(r["budget"]) for r in summary_rows)):
        anchor = by_budget_method.get((budget, "adaptive_min_expand_1"))
        s1 = by_budget_method.get((budget, "external_s1_budget_forcing"))
        if anchor is None or s1 is None:
            continue
        pairwise_rows.append(
            {
                "dataset": args.dataset,
                "budget": budget,
                "anchor_method": "adaptive_min_expand_1",
                "baseline_method": "external_s1_budget_forcing",
                "delta_accuracy_s1_minus_anchor": float(s1["mean_accuracy"] - anchor["mean_accuracy"]),
                "delta_avg_actions_s1_minus_anchor": float(s1["mean_avg_actions"] - anchor["mean_avg_actions"]),
            }
        )

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "method_catalog": METHOD_SPECS,
        "s1_adapter_config": {
            "num_ignore_think_end": args.s1_num_ignore_think_end,
            "min_thinking_steps": args.s1_min_thinking_steps,
            "wait_token": "Wait",
        },
        "note": (
            "This evaluates only an in-repo adapter of s1 budget forcing behavior, not full s1 training/data stack."
        ),
    }

    _write_csv(run_dir / "method_metrics_per_seed.csv", per_seed_rows)
    _write_csv(run_dir / "method_summary.csv", summary_rows)
    _write_csv(run_dir / "pairwise_anchor_vs_s1.csv", pairwise_rows)
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"status": "ok", "run_dir": str(run_dir)}, indent=2))


if __name__ == "__main__":
    main()
