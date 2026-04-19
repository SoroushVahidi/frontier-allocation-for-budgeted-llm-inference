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

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _safe_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _failure_group(row: dict[str, Any]) -> str:
    if bool(row.get("is_correct", False)):
        return "correct"
    m = row.get("metadata") or {}
    cat = str(m.get("early_divergence_failure_category", ""))
    if cat in {
        "not_generated",
        "generated_but_underweighted",
        "collapsed_early",
        "generated_but_committed_away_from_later",
    }:
        return cat
    if row.get("budget_exhausted") or (
        not bool(m.get("commit_triggered", False))
        and int(row.get("actions_used", 0)) >= int(row.get("budget", 0)) - 1
    ):
        return "wrong_commit_timing"
    return "other"


def _load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded comparison for early useful-diversity / answer-group preservation")
    p.add_argument("--config", default="configs/early_answer_group_preservation_bounded_eval_20260419.json")
    args = p.parse_args()

    cfg = _load_config(REPO_ROOT / args.config)
    datasets = [str(x) for x in cfg["datasets"]]
    seeds = [int(x) for x in cfg["seeds"]]
    budgets = [int(x) for x in cfg["budgets"]]
    adaptive_grid = [int(x) for x in cfg.get("adaptive_grid", [1])]
    subset_size = int(cfg["subset_size"])
    methods = dict(cfg["methods"])
    method_names = list(methods.values())

    out_dir = REPO_ROOT / str(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []

    rng_master = random.Random(20260419)
    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, subset_size, seed)
            for budget in budgets:
                rng = random.Random(rng_master.randint(0, 10**9))
                factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
                specs = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_broad_diversity_aggregation_methods=True,
                )
                selected = {alias: specs[name] for alias, name in methods.items()}
                per_method_rows: dict[str, list[dict[str, Any]]] = {k: [] for k in selected}

                for ex in examples:
                    for alias, ctrl in selected.items():
                        r = ctrl.run(ex.question, ex.answer)
                        row = {
                            "dataset": dataset,
                            "seed": int(seed),
                            "budget": int(budget),
                            "example_id": ex.example_id,
                            "problem_statement": ex.question,
                            "gold_answer": ex.answer,
                            "method_alias": alias,
                            "method": methods[alias],
                            "prediction": r.prediction,
                            "is_correct": bool(r.is_correct),
                            "actions_used": int(r.actions_used),
                            "budget_exhausted": bool(r.budget_exhausted),
                            "metadata": r.metadata,
                        }
                        row["failure_group"] = _failure_group(row)
                        all_rows.append(row)
                        per_method_rows[alias].append(row)

                for alias, rows in per_method_rows.items():
                    n = max(1, len(rows))
                    metric_rows.append(
                        {
                            "dataset": dataset,
                            "seed": int(seed),
                            "budget": int(budget),
                            "method_alias": alias,
                            "method": methods[alias],
                            "accuracy": sum(int(r["is_correct"]) for r in rows) / n,
                            "wrong_commit_timing_count": sum(1 for r in rows if r["failure_group"] == "wrong_commit_timing"),
                            "survival_after_first_split": sum(
                                1 for r in rows if bool((r.get("metadata") or {}).get("gold_group_present_after_first_split", False))
                            )
                            / n,
                            "survival_after_second_split": sum(
                                1 for r in rows if bool((r.get("metadata") or {}).get("gold_group_present_after_second_split", False))
                            )
                            / n,
                            "n_examples": len(rows),
                        }
                    )

    by_alias = defaultdict(list)
    for m in metric_rows:
        by_alias[m["method_alias"]].append(float(m["accuracy"]))

    overall = {
        alias: {
            "method": methods[alias],
            "mean_accuracy": _mean(vals),
            "std_accuracy": _std(vals),
            "n_cells": len(vals),
        }
        for alias, vals in by_alias.items()
    }

    grouped_metric = defaultdict(lambda: defaultdict(list))
    for r in metric_rows:
        grouped_metric[(r["dataset"], r["budget"])][r["method_alias"]].append(float(r["accuracy"]))
    mean_accuracy_by_dataset_budget = {
        f"{k[0]}|budget_{k[1]}": {alias: _mean(v) for alias, v in vv.items()} for k, vv in grouped_metric.items()
    }

    failure_counts = {alias: Counter() for alias in methods}
    for r in all_rows:
        failure_counts[str(r["method_alias"])] [str(r["failure_group"])] += 1

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in all_rows:
        key = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        aligned[key][str(r["method_alias"])] = r

    improved_vs_base: list[dict[str, Any]] = []
    harmed_vs_base: list[dict[str, Any]] = []
    unchanged_vs_base: list[dict[str, Any]] = []
    compact_casebook: list[dict[str, Any]] = []

    for pair in aligned.values():
        if "baseline_broad" not in pair or "early_preservation" not in pair:
            continue
        b = pair["baseline_broad"]
        e = pair["early_preservation"]
        if (not b["is_correct"]) and e["is_correct"]:
            improved_vs_base.append({"dataset": e["dataset"], "seed": e["seed"], "budget": e["budget"], "example_id": e["example_id"]})
        elif b["is_correct"] and (not e["is_correct"]):
            harmed_vs_base.append({"dataset": e["dataset"], "seed": e["seed"], "budget": e["budget"], "example_id": e["example_id"]})
        else:
            unchanged_vs_base.append({"dataset": e["dataset"], "seed": e["seed"], "budget": e["budget"], "example_id": e["example_id"]})

        bm = b.get("metadata") or {}
        em = e.get("metadata") or {}
        base_absent = not bool(bm.get("gold_group_present_after_first_split", False))
        base_collapsed = bool(bm.get("gold_group_present_after_first_split", False)) and (not bool(bm.get("gold_group_present_final", False)))
        if base_absent or base_collapsed:
            compact_casebook.append(
                {
                    "dataset": e["dataset"],
                    "seed": e["seed"],
                    "budget": e["budget"],
                    "example_id": e["example_id"],
                    "base_case_type": "absent_after_first_split" if base_absent else "present_then_collapsed",
                    "base_failure_category": bm.get("early_divergence_failure_category"),
                    "base_correct": bool(b["is_correct"]),
                    "early_preservation_correct": bool(e["is_correct"]),
                    "early_preservation_after_first_split": bool(em.get("gold_group_present_after_first_split", False)),
                    "early_preservation_after_second_split": bool(em.get("gold_group_present_after_second_split", False)),
                    "base_prediction": b.get("prediction"),
                    "early_preservation_prediction": e.get("prediction"),
                    "gold_answer": e.get("gold_answer"),
                }
            )

    def _agg(alias: str, key: str) -> float:
        rows = [r for r in all_rows if r["method_alias"] == alias]
        return sum(_safe_float((r.get("metadata") or {}).get(key, 0.0)) for r in rows) / max(1, len(rows))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": args.config,
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": subset_size,
        "methods": methods,
        "overall": overall,
        "mean_accuracy_by_dataset_budget": mean_accuracy_by_dataset_budget,
        "wrong_commit_timing_count": {alias: int(failure_counts[alias].get("wrong_commit_timing", 0)) for alias in methods},
        "answer_group_survival": {
            alias: {
                "after_first_split": _agg(alias, "gold_group_present_after_first_split"),
                "after_second_split": _agg(alias, "gold_group_present_after_second_split"),
            }
            for alias in methods
        },
        "failure_category_counts": {
            alias: {
                "not_generated": int(failure_counts[alias].get("not_generated", 0)),
                "generated_but_underweighted": int(failure_counts[alias].get("generated_but_underweighted", 0)),
                "collapsed_early": int(failure_counts[alias].get("collapsed_early", 0)),
                "committed_away_from_later": int(failure_counts[alias].get("generated_but_committed_away_from_later", 0)),
            }
            for alias in methods
        },
        "improved_harmed_vs_baseline_broad": {
            "improved_count": len(improved_vs_base),
            "harmed_count": len(harmed_vs_base),
            "unchanged_count": len(unchanged_vs_base),
        },
        "primary_question_answer": {
            "survival_after_first_split_delta_vs_base": _agg("early_preservation", "gold_group_present_after_first_split")
            - _agg("baseline_broad", "gold_group_present_after_first_split"),
            "survival_after_second_split_delta_vs_base": _agg("early_preservation", "gold_group_present_after_second_split")
            - _agg("baseline_broad", "gold_group_present_after_second_split"),
            "accuracy_delta_vs_base": overall.get("early_preservation", {}).get("mean_accuracy", 0.0)
            - overall.get("baseline_broad", {}).get("mean_accuracy", 0.0),
        },
    }

    (out_dir / "per_example_rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n", encoding="utf-8")
    (out_dir / "method_metrics.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in metric_rows) + "\n", encoding="utf-8")
    (out_dir / "comparison_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "improved_cases_vs_baseline.json").write_text(json.dumps(improved_vs_base, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "harmed_cases_vs_baseline.json").write_text(json.dumps(harmed_vs_base, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "compact_casebook_early_divergence.json").write_text(json.dumps(compact_casebook, indent=2, ensure_ascii=False), encoding="utf-8")

    status_lines = [
        "# Early answer-group preservation bounded status (2026-04-19)",
        "",
        "## What changed",
        "- Added an early useful-diversity mechanism that protects one plausible challenger answer-group during the first split window.",
        "- Added early target-variable alignment scoring and attached it to branch-level action traces.",
        "- Added per-example early divergence diagnostics for first/second split survival and disappearance timing.",
        "",
        "## Bounded comparison headline",
        f"- Base broad mean accuracy: {summary['overall'].get('baseline_broad', {}).get('mean_accuracy', 0.0):.4f}",
        f"- Early-preservation mean accuracy: {summary['overall'].get('early_preservation', {}).get('mean_accuracy', 0.0):.4f}",
        f"- Delta (early-preservation - base): {summary['primary_question_answer']['accuracy_delta_vs_base']:+.4f}",
        f"- Survival after first split delta vs base: {summary['primary_question_answer']['survival_after_first_split_delta_vs_base']:+.4f}",
        f"- Survival after second split delta vs base: {summary['primary_question_answer']['survival_after_second_split_delta_vs_base']:+.4f}",
        f"- Improved / harmed / unchanged vs base: {len(improved_vs_base)} / {len(harmed_vs_base)} / {len(unchanged_vs_base)}",
        "",
        "## Conservative conclusion",
        "- Treat as active promoted line only if both survival and accuracy improve with harmed cases controlled.",
        "- If survival improves but accuracy does not, keep as diagnostic and refine preservation selectivity before promotion.",
    ]
    (out_dir / "STATUS_NOTE_early_answer_group_preservation_20260419.md").write_text("\n".join(status_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
