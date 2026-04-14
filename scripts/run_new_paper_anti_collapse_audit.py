#!/usr/bin/env python3
"""Audit anti-collapse behavior for adaptive_min_expand variants (new-paper track)."""

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

from experiments.frontier_matrix_core import (
    adaptive_anti_collapse_stats,
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

METHODS = [
    "adaptive_min_expand_0",
    "adaptive_min_expand_1",
    "adaptive_min_expand_2",
    "adaptive_budget_guarded",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run anti-collapse audit for adaptive frontier controllers")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=18)
    p.add_argument("--seed", type=int, default=29)
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/new_paper/anti_collapse_audit")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(int(any(r["is_correct"] for r in rr)) for rr in by_ex.values()) / len(by_ex)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        all_fields: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    all_fields.append(k)
        w = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)

    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
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
        "adaptive_min_expand_grid": adaptive_grid,
        "new_variant": "adaptive_budget_guarded",
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    gen_factory = generator_factory_for_mode(
        args.use_openai_api,
        rng,
        args.openai_model,
        args.temperature,
        args.max_output_tokens,
        args.timeout_seconds,
    )

    method_rows: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []

    for budget in budgets:
        strategies = build_frontier_strategies(
            gen_factory,
            budget,
            adaptive_grid,
            rng,
            use_openai_api=args.use_openai_api,
            include_budget_guarded_adaptive=True,
        )
        metrics, rows = evaluate_strategies_on_examples(examples, strategies)
        oracle_acc = _oracle_accuracy(rows)

        anti_stats = adaptive_anti_collapse_stats(rows)
        guarded_rows = [r for r in rows if r["strategy"] == "adaptive_budget_guarded"]
        guarded_trace_n = sum(1 for r in guarded_rows if (r.get("metadata") or {}).get("action_trace"))
        forced_budget_guard = 0
        forced_total = 0
        for r in guarded_rows:
            trace = (r.get("metadata") or {}).get("action_trace") or []
            for t in trace:
                if t.get("forced_expand"):
                    forced_total += 1
                    if t.get("forced_expand_reason") == "budget_guard":
                        forced_budget_guard += 1

        for method in METHODS:
            if method not in metrics:
                continue
            m = metrics[method]
            method_rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "method": method,
                    "accuracy": m["accuracy"],
                    "avg_actions": m["avg_actions"],
                    "budget_exhaustion_rate": m["budget_exhaustion_rate"],
                    "oracle_accuracy": oracle_acc,
                    "oracle_gap": oracle_acc - float(m["accuracy"]),
                }
            )

        for k, stats in anti_stats.items():
            anti_rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "method": f"adaptive_min_expand_{k}",
                    "mean_prune_share_of_actions": stats["mean_prune_share_of_actions"],
                    "mean_forced_expand_share": stats["mean_forced_expand_share"],
                    "mean_action_trace_length": stats["mean_action_trace_length"],
                    "examples_with_trace": stats["examples_with_trace"],
                }
            )

        if "adaptive_budget_guarded" in metrics:
            prune_fracs: list[float] = []
            forced_fracs: list[float] = []
            budget_guard_share: list[float] = []
            for row in guarded_rows:
                trace = (row.get("metadata") or {}).get("action_trace") or []
                if not trace:
                    continue
                n = len(trace)
                n_prune = sum(1 for t in trace if t.get("action") == "prune")
                n_forced = sum(1 for t in trace if t.get("forced_expand"))
                n_bg = sum(1 for t in trace if t.get("forced_expand_reason") == "budget_guard")
                prune_fracs.append(n_prune / n)
                forced_fracs.append(n_forced / n)
                budget_guard_share.append(n_bg / n)
            anti_rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "method": "adaptive_budget_guarded",
                    "mean_prune_share_of_actions": sum(prune_fracs) / max(1, len(prune_fracs)),
                    "mean_forced_expand_share": sum(forced_fracs) / max(1, len(forced_fracs)),
                    "mean_action_trace_length": statistics.mean([len((r.get("metadata") or {}).get("action_trace") or []) for r in guarded_rows]) if guarded_rows else 0.0,
                    "examples_with_trace": float(guarded_trace_n),
                    "mean_budget_guard_forced_share": sum(budget_guard_share) / max(1, len(budget_guard_share)),
                    "forced_expand_budget_guard_count": forced_budget_guard,
                    "forced_expand_total_count": forced_total,
                }
            )

    _write_csv(run_dir / "anti_collapse_method_metrics.csv", method_rows)
    _write_csv(run_dir / "anti_collapse_behavior.csv", anti_rows)

    lines = [
        "# New-paper anti-collapse audit note",
        "",
        "Compared methods:",
        "- adaptive_min_expand_0",
        "- adaptive_min_expand_1",
        "- adaptive_min_expand_2",
        "- adaptive_budget_guarded (new)",
        "",
        "The new variant adds: adaptive min-expand (+1 while >=50% budget remains), verification exploration floor, and budget-aware prune guard.",
        "",
        "## Results summary",
    ]

    by_budget: dict[int, list[dict[str, Any]]] = {}
    for r in method_rows:
        by_budget.setdefault(int(r["budget"]), []).append(r)

    for b in sorted(by_budget):
        lines.append(f"### Budget {b}")
        for r in sorted(by_budget[b], key=lambda x: x["method"]):
            lines.append(
                f"- {r['method']}: acc={float(r['accuracy']):.3f}, avg_actions={float(r['avg_actions']):.2f}, "
                f"oracle_gap={float(r['oracle_gap']):.3f}, budget_exhaustion={float(r['budget_exhaustion_rate']):.3f}"
            )
        behavior = [x for x in anti_rows if int(x["budget"]) == b and x["method"] == "adaptive_budget_guarded"]
        if behavior:
            rr = behavior[0]
            lines.append(
                f"- adaptive_budget_guarded behavior: prune_share={float(rr['mean_prune_share_of_actions']):.3f}, "
                f"forced_expand_share={float(rr['mean_forced_expand_share']):.3f}, "
                f"budget_guard_forced_share={float(rr.get('mean_budget_guard_forced_share', 0.0)):.3f}"
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "- Focus on whether prune share decreases and realized actions increase without harming accuracy.",
            "- If accuracy/usage do not improve, treat this as a negative anti-collapse result and keep the mechanism as a diagnostic baseline.",
        ]
    )
    (run_dir / "anti_collapse_interpretation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(run_dir))


if __name__ == "__main__":
    main()
