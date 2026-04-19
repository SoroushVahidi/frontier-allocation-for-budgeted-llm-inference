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


def _safe_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def _safe_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded evaluation for anti-collapse + answer-group-aware allocation refinement")
    p.add_argument("--config", default="configs/anti_collapse_answer_group_refinement_bounded_eval_20260419.json")
    args = p.parse_args()

    cfg = _load_config(REPO_ROOT / args.config)
    datasets = [str(x) for x in cfg["datasets"]]
    seeds = [int(x) for x in cfg["seeds"]]
    budgets = [int(x) for x in cfg["budgets"]]
    subset_size = int(cfg["subset_size"])
    adaptive_grid = [int(x) for x in cfg.get("adaptive_grid", [1])]
    methods = dict(cfg["methods"])

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
                            "seed": seed,
                            "budget": budget,
                            "example_id": ex.example_id,
                            "gold_answer": ex.answer,
                            "prediction": r.prediction,
                            "is_correct": bool(r.is_correct),
                            "method_alias": alias,
                            "method": methods[alias],
                            "actions_used": int(r.actions_used),
                            "expansions": int(r.expansions),
                            "verifications": int(r.verifications),
                            "metadata": r.metadata,
                        }
                        all_rows.append(row)
                        per_method_rows[alias].append(row)

                for alias, rows in per_method_rows.items():
                    n = max(1, len(rows))
                    metric_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method_alias": alias,
                            "method": methods[alias],
                            "n_examples": len(rows),
                            "accuracy": sum(int(r["is_correct"]) for r in rows) / n,
                            "first_split_survival": sum(
                                int(bool((r.get("metadata") or {}).get("gold_group_present_after_first_split", False))) for r in rows
                            )
                            / n,
                            "second_split_survival": sum(
                                int(bool((r.get("metadata") or {}).get("gold_group_present_after_second_split", False))) for r in rows
                            )
                            / n,
                            "not_generated": sum(
                                int(str((r.get("metadata") or {}).get("early_divergence_failure_category", "")) == "not_generated") for r in rows
                            ),
                            "generated_but_underweighted": sum(
                                int(str((r.get("metadata") or {}).get("early_divergence_failure_category", "")) == "generated_but_underweighted")
                                for r in rows
                            ),
                            "collapsed_early": sum(
                                int(str((r.get("metadata") or {}).get("early_divergence_failure_category", "")) == "collapsed_early") for r in rows
                            ),
                            "generated_but_committed_away_from_later": sum(
                                int(
                                    str((r.get("metadata") or {}).get("early_divergence_failure_category", ""))
                                    == "generated_but_committed_away_from_later"
                                )
                                for r in rows
                            ),
                            "repeated_same_branch_expansion_rate": _mean(
                                [_safe_float((r.get("metadata") or {}).get("repeated_same_branch_expansion_rate", 0.0)) for r in rows]
                            ),
                            "repeated_same_branch_expansion_count": sum(
                                _safe_int((r.get("metadata") or {}).get("repeated_same_branch_expansion_count", 0)) for r in rows
                            ),
                            "shallow_preserved_alternative_count": sum(
                                _safe_int((r.get("metadata") or {}).get("shallow_preserved_alternative_count", 0)) for r in rows
                            ),
                            "matured_alternative_count": sum(
                                _safe_int((r.get("metadata") or {}).get("matured_alternative_count", 0)) for r in rows
                            ),
                            "answer_group_diversity_realized": _mean(
                                [_safe_float((r.get("metadata") or {}).get("answer_group_diversity_realized", 0.0)) for r in rows]
                            ),
                            "branch_creation_count": _mean(
                                [_safe_float((r.get("metadata") or {}).get("branch_creation_count", 0.0)) for r in rows]
                            ),
                            "expand_count": _mean([_safe_float(r.get("expansions", 0.0)) for r in rows]),
                            "verify_count": _mean([_safe_float(r.get("verifications", 0.0)) for r in rows]),
                            "regime_correct_absent": sum(
                                int(str((r.get("metadata") or {}).get("regime_failure_category", "")) == "correct_answer_group_absent")
                                for r in rows
                            ),
                            "regime_present_underweighted": sum(
                                int(
                                    str((r.get("metadata") or {}).get("regime_failure_category", ""))
                                    == "correct_answer_group_present_but_underweighted"
                                )
                                for r in rows
                            ),
                            "regime_preserved_insufficiently_matured": sum(
                                int(
                                    str((r.get("metadata") or {}).get("regime_failure_category", ""))
                                    == "correct_group_preserved_but_insufficiently_matured"
                                )
                                for r in rows
                            ),
                            "regime_repeated_same_branch_dominated": sum(
                                int(
                                    str((r.get("metadata") or {}).get("regime_failure_category", ""))
                                    == "repeated_same_branch_expansion_dominated_budget"
                                )
                                for r in rows
                            ),
                            "regime_commit_lost_viable_alt": sum(
                                int(
                                    str((r.get("metadata") or {}).get("regime_failure_category", ""))
                                    == "final_commit_lost_despite_viable_alternative"
                                )
                                for r in rows
                            ),
                        }
                    )

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in all_rows:
        key = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        aligned[key][str(r["method_alias"])] = r

    improved_harmed_unchanged = {"improved": 0, "harmed": 0, "unchanged": 0}
    for pair in aligned.values():
        b = pair.get("baseline_broad")
        c = pair.get("anti_collapse_refinement")
        if not b or not c:
            continue
        if (not b["is_correct"]) and c["is_correct"]:
            improved_harmed_unchanged["improved"] += 1
        elif b["is_correct"] and (not c["is_correct"]):
            improved_harmed_unchanged["harmed"] += 1
        else:
            improved_harmed_unchanged["unchanged"] += 1

    overall: dict[str, dict[str, float | int | str]] = {}
    by_alias = defaultdict(list)
    for row in metric_rows:
        by_alias[str(row["method_alias"])].append(row)

    for alias, rows in by_alias.items():
        overall[alias] = {
            "method": methods[alias],
            "mean_accuracy": _mean([_safe_float(r["accuracy"]) for r in rows]),
            "mean_first_split_survival": _mean([_safe_float(r["first_split_survival"]) for r in rows]),
            "mean_second_split_survival": _mean([_safe_float(r["second_split_survival"]) for r in rows]),
            "mean_repeated_same_branch_expansion_rate": _mean(
                [_safe_float(r["repeated_same_branch_expansion_rate"]) for r in rows]
            ),
            "total_repeated_same_branch_expansion_count": int(
                sum(_safe_int(r["repeated_same_branch_expansion_count"]) for r in rows)
            ),
            "total_shallow_preserved_alternative_count": int(
                sum(_safe_int(r["shallow_preserved_alternative_count"]) for r in rows)
            ),
            "total_matured_alternative_count": int(sum(_safe_int(r["matured_alternative_count"]) for r in rows)),
            "mean_answer_group_diversity_realized": _mean(
                [_safe_float(r["answer_group_diversity_realized"]) for r in rows]
            ),
            "mean_branch_creation_count": _mean([_safe_float(r["branch_creation_count"]) for r in rows]),
            "mean_expand_count": _mean([_safe_float(r["expand_count"]) for r in rows]),
            "mean_verify_count": _mean([_safe_float(r["verify_count"]) for r in rows]),
            "failure_counts": {
                "not_generated": int(sum(_safe_int(r["not_generated"]) for r in rows)),
                "generated_but_underweighted": int(sum(_safe_int(r["generated_but_underweighted"]) for r in rows)),
                "collapsed_early": int(sum(_safe_int(r["collapsed_early"]) for r in rows)),
                "generated_but_committed_away_from_later": int(
                    sum(_safe_int(r["generated_but_committed_away_from_later"]) for r in rows)
                ),
            },
            "regime_failure_counts": {
                "correct_answer_group_absent": int(sum(_safe_int(r["regime_correct_absent"]) for r in rows)),
                "correct_answer_group_present_but_underweighted": int(
                    sum(_safe_int(r["regime_present_underweighted"]) for r in rows)
                ),
                "correct_group_preserved_but_insufficiently_matured": int(
                    sum(_safe_int(r["regime_preserved_insufficiently_matured"]) for r in rows)
                ),
                "repeated_same_branch_expansion_dominated_budget": int(
                    sum(_safe_int(r["regime_repeated_same_branch_dominated"]) for r in rows)
                ),
                "final_commit_lost_despite_viable_alternative": int(sum(_safe_int(r["regime_commit_lost_viable_alt"]) for r in rows)),
            },
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": args.config,
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": subset_size,
        "methods": methods,
        "overall": overall,
        "improved_harmed_unchanged_vs_baseline": improved_harmed_unchanged,
        "primary_question_answer": {
            "accuracy_delta_refinement_vs_baseline": _safe_float(overall.get("anti_collapse_refinement", {}).get("mean_accuracy", 0.0))
            - _safe_float(overall.get("baseline_broad", {}).get("mean_accuracy", 0.0)),
            "accuracy_delta_refinement_vs_early_preservation": _safe_float(
                overall.get("anti_collapse_refinement", {}).get("mean_accuracy", 0.0)
            )
            - _safe_float(overall.get("early_preservation", {}).get("mean_accuracy", 0.0)),
            "repeated_same_branch_expansion_rate_delta_vs_baseline": _safe_float(
                overall.get("anti_collapse_refinement", {}).get("mean_repeated_same_branch_expansion_rate", 0.0)
            )
            - _safe_float(overall.get("baseline_broad", {}).get("mean_repeated_same_branch_expansion_rate", 0.0)),
            "matured_alternative_count_delta_vs_baseline": _safe_int(
                overall.get("anti_collapse_refinement", {}).get("total_matured_alternative_count", 0)
            )
            - _safe_int(overall.get("baseline_broad", {}).get("total_matured_alternative_count", 0)),
        },
    }

    (out_dir / "per_example_rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n", encoding="utf-8")
    (out_dir / "method_metrics.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in metric_rows) + "\n", encoding="utf-8")
    (out_dir / "comparison_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
