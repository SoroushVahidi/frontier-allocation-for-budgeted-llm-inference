#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    generator_factory_for_mode,
    load_pilot_examples,
)

METHOD_BASE = "broad_diversity_aggregation_strong_v1"
METHOD_GATE = "broad_diversity_aggregation_strong_v1_diversity_needed_gate"
METHOD_HEUR = "broad_diversity_aggregation_strong_v1_heuristic_gate"


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _failure_group(row: dict[str, Any]) -> str:
    m = row.get("metadata") or {}
    if row.get("is_correct"):
        return "correct"
    unique_groups = int(m.get("unique_answer_groups_seen", 0))
    entropy = float(m.get("answer_support_entropy", 0.0))
    agg_used = bool(m.get("aggregation_used", False))
    commit_triggered = bool(m.get("commit_triggered", False))
    budget_exhausted = bool(row.get("budget_exhausted", False))
    if unique_groups <= 1 or entropy < 0.25:
        return "insufficient_diversity_realized"
    if unique_groups >= 3 and entropy > 0.9 and not agg_used:
        return "bad_diversity_realized"
    if agg_used and float(m.get("group_support_fraction", 0.0)) < 0.60:
        return "aggregation_instability"
    if budget_exhausted or (not commit_triggered and float(row.get("actions_used", 0)) >= 0.9 * float(row.get("budget", 0))):
        return "commit_timing"
    return "other"


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded diversity-needed gate comparison inside broad diversity method family")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024")
    p.add_argument("--subset-size", type=int, default=20)
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/diversity_needed_gate_bounded_comparison_20260419")
    p.add_argument("--skip-heuristic", action="store_true")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    methods = [METHOD_BASE, METHOD_GATE]
    if not args.skip_heuristic:
        methods.append(METHOD_HEUR)

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    method_metrics: list[dict[str, Any]] = []

    rng_master = random.Random(20260419)
    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            example_map = {e.example_id: e for e in examples}
            rng = random.Random(rng_master.randint(0, 10**9))
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
            for budget in budgets:
                specs = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_broad_diversity_aggregation_methods=True,
                )
                specs = {k: v for k, v in specs.items() if k in methods}
                per_method_rows = {k: [] for k in methods}
                for ex in examples:
                    for name, controller in specs.items():
                        res = controller.run(ex.question, ex.answer)
                        row = {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": ex.example_id,
                            "problem": ex.question,
                            "gold_answer": ex.answer,
                            "method": name,
                            "prediction": res.prediction,
                            "is_correct": bool(res.is_correct),
                            "actions_used": int(res.actions_used),
                            "budget_exhausted": bool(res.budget_exhausted),
                            "metadata": res.metadata,
                        }
                        row["failure_group"] = _failure_group(row)
                        all_rows.append(row)
                        per_method_rows[name].append(row)

                for name, rows in per_method_rows.items():
                    n = max(1, len(rows))
                    method_metrics.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": name,
                            "accuracy": sum(int(r["is_correct"]) for r in rows) / n,
                            "avg_actions": sum(float(r["actions_used"]) for r in rows) / n,
                            "budget_exhaustion_rate": sum(int(r["budget_exhausted"]) for r in rows) / n,
                            "n_examples": len(rows),
                        }
                    )

    # matched alignment by example key
    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in all_rows:
        key = (str(row["dataset"]), int(row["seed"]), int(row["budget"]), str(row["example_id"]))
        aligned[key][str(row["method"])] = row
    aligned_rows = [v for v in aligned.values() if METHOD_BASE in v and METHOD_GATE in v]

    improved: list[dict[str, Any]] = []
    harmed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    gate_changed_cases = 0
    gate_intervention_success = 0

    for pair in aligned_rows:
        b = pair[METHOD_BASE]
        g = pair[METHOD_GATE]
        gate_changed = bool(g.get("metadata", {}).get("gate_intervention_count", 0) > 0)
        if gate_changed:
            gate_changed_cases += 1
        if (not b["is_correct"]) and g["is_correct"]:
            improved.append(
                {
                    "dataset": g["dataset"],
                    "seed": g["seed"],
                    "budget": g["budget"],
                    "example_id": g["example_id"],
                    "problem_statement": g["problem"],
                    "gold_answer": g["gold_answer"],
                    "base_answer": b["prediction"],
                    "gated_answer": g["prediction"],
                    "gate_changed_frontier_decision": gate_changed,
                    "base_failure_group": b["failure_group"],
                    "gated_failure_group": g["failure_group"],
                    "note": "gate likely promoted diversity-seeking branch before commit" if gate_changed else "prediction changed without explicit gate intervention",
                }
            )
            if gate_changed:
                gate_intervention_success += 1
        elif b["is_correct"] and (not g["is_correct"]):
            harmed.append(
                {
                    "dataset": g["dataset"],
                    "seed": g["seed"],
                    "budget": g["budget"],
                    "example_id": g["example_id"],
                    "problem_statement": g["problem"],
                    "gold_answer": g["gold_answer"],
                    "base_answer": b["prediction"],
                    "gated_answer": g["prediction"],
                    "gate_changed_frontier_decision": gate_changed,
                    "base_failure_group": b["failure_group"],
                    "gated_failure_group": g["failure_group"],
                    "note": "gate likely suppressed useful exploration or over-diversified" if gate_changed else "non-gate stochastic variation",
                }
            )
        else:
            unchanged.append(
                {
                    "dataset": g["dataset"],
                    "seed": g["seed"],
                    "budget": g["budget"],
                    "example_id": g["example_id"],
                    "gate_changed_frontier_decision": gate_changed,
                    "both_correct": bool(g["is_correct"] and b["is_correct"]),
                }
            )

    by_method = defaultdict(list)
    for m in method_metrics:
        by_method[str(m["method"])].append(float(m["accuracy"]))
    overall = {
        m: {
            "mean_accuracy": _mean(v),
            "std_accuracy": _std(v),
            "n_cells": len(v),
        }
        for m, v in by_method.items()
    }

    near_tie_slice = {m: [] for m in methods}
    for row in all_rows:
        meta = row.get("metadata") or {}
        margin = float(meta.get("answer_group_margin", 0.0))
        if margin <= 0.20:
            near_tie_slice[row["method"]].append(int(row["is_correct"]))

    failure_counts: dict[str, dict[str, int]] = {}
    for method in [METHOD_BASE, METHOD_GATE]:
        counts = Counter()
        for row in all_rows:
            if row["method"] == method:
                counts[str(row["failure_group"])] += 1
        failure_counts[method] = dict(counts)

    gate_rows = [r for r in all_rows if r["method"] == METHOD_GATE]
    gate_positive = sum(
        1
        for r in gate_rows
        for a in (r.get("metadata", {}).get("action_trace") or [])
        if str(a.get("gate_decision")) == "favor_diversity"
    )
    gate_negative = sum(
        1
        for r in gate_rows
        for a in (r.get("metadata", {}).get("action_trace") or [])
        if str(a.get("gate_decision")) == "suppress_diversity_push"
    )
    gate_total_interventions = sum(int(r.get("metadata", {}).get("gate_intervention_count", 0)) for r in gate_rows)

    comparison = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "methods": methods,
        "overall": overall,
        "delta_gate_minus_base": float(overall.get(METHOD_GATE, {}).get("mean_accuracy", 0.0) - overall.get(METHOD_BASE, {}).get("mean_accuracy", 0.0)),
        "near_tie_accuracy": {m: _mean([float(x) for x in vals]) for m, vals in near_tie_slice.items()},
        "failure_counts": failure_counts,
        "gate_diagnostics": {
            "gate_positive_action_count": int(gate_positive),
            "gate_negative_action_count": int(gate_negative),
            "gate_intervention_count": int(gate_total_interventions),
            "cases_with_gate_intervention": int(gate_changed_cases),
            "gate_intervention_success_rate": float(gate_intervention_success / max(1, gate_changed_cases)),
        },
        "comparison_counts": {
            "n_improved": len(improved),
            "n_harmed": len(harmed),
            "n_unchanged": len(unchanged),
        },
        "is_serious_integration_candidate": bool(
            overall.get(METHOD_GATE, {}).get("mean_accuracy", 0.0) > overall.get(METHOD_BASE, {}).get("mean_accuracy", 0.0)
            and failure_counts.get(METHOD_GATE, {}).get("insufficient_diversity_realized", 0)
            <= failure_counts.get(METHOD_BASE, {}).get("insufficient_diversity_realized", 0)
            and len(improved) >= len(harmed)
        ),
    }

    (out_dir / "method_metrics.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in method_metrics) + "\n", encoding="utf-8")
    (out_dir / "per_example_rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n", encoding="utf-8")
    (out_dir / "comparison_summary.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    (out_dir / "improved_cases.json").write_text(json.dumps(improved, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "harmed_cases.json").write_text(json.dumps(harmed, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "unchanged_cases.json").write_text(json.dumps(unchanged, indent=2, ensure_ascii=False), encoding="utf-8")

    note_lines = [
        "# Diversity-needed gated broad-method bounded comparison (2026-04-19)",
        "",
        f"- Base method: `{METHOD_BASE}`",
        f"- Gated method: `{METHOD_GATE}`",
        f"- Heuristic gate baseline included: `{METHOD_HEUR in methods}`",
        f"- Datasets: {', '.join(datasets)}",
        f"- Seeds: {seeds}",
        f"- Budgets: {budgets}",
        "",
        "## Key outcomes",
        f"- Mean accuracy (base): {overall.get(METHOD_BASE, {}).get('mean_accuracy', 0.0):.4f}",
        f"- Mean accuracy (gated): {overall.get(METHOD_GATE, {}).get('mean_accuracy', 0.0):.4f}",
        f"- Delta gated-base: {comparison['delta_gate_minus_base']:+.4f}",
        f"- Improved / harmed / unchanged: {len(improved)} / {len(harmed)} / {len(unchanged)}",
        f"- Gate interventions: {gate_total_interventions} actions across {gate_changed_cases} matched cases",
        f"- Gate intervention success rate (improved among intervened cases): {comparison['gate_diagnostics']['gate_intervention_success_rate']:.3f}",
        "",
        "## Explicit status",
        f"- Useful enough for another pass? {'yes' if comparison['is_serious_integration_candidate'] else 'not yet'}.",
        f"- Diagnostic-only vs serious integration candidate: {'serious integration candidate (bounded)' if comparison['is_serious_integration_candidate'] else 'still mostly diagnostic'}.",
        "- Best next step: run one deeper bounded threshold/ablation pass focused on improved/harmed slices and insufficient_diversity_realized failures.",
    ]
    (out_dir / "STATUS_NOTE_diversity_needed_gate_20260419.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
