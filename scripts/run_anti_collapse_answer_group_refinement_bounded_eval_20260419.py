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


def _harmed_subtype(
    *,
    baseline_row: dict[str, Any],
    candidate_row: dict[str, Any],
) -> str:
    md = candidate_row.get("metadata") or {}
    bmd = baseline_row.get("metadata") or {}
    action_trace = md.get("action_trace") or []
    avg_repeat_pressure = _mean(
        [
            _safe_float(t.get("anti_collapse_repeat_penalty", 0.0))
            + _safe_float(t.get("anti_collapse_cap_guard_penalty", 0.0))
            for t in action_trace
        ]
    )
    repeat_rate = _safe_float(md.get("repeated_same_branch_expansion_rate", 0.0))
    early_div = str(md.get("early_divergence_failure_category", ""))
    regime = str(md.get("regime_failure_category", ""))

    if (
        early_div == "generated_but_committed_away_from_later"
        or regime == "final_commit_lost_despite_viable_alternative"
        or bool(md.get("unstable_commit_flag", False))
        or _safe_int(md.get("late_commit_after_selector_count", 0)) > 0
    ):
        return "residual_late_commit_problem_after_improved_tree_growth"
    if early_div == "generated_but_underweighted" or regime == "correct_answer_group_present_but_underweighted":
        return "aggregation_still_underweighted_right_answer_group"
    if _safe_int(md.get("early_answer_group_preservation_forced_steps", 0)) > 0 and not bool(md.get("gold_group_present_final", False)):
        return "alternative_preserved_but_wrong"
    if _safe_int(md.get("matured_alternative_count", 0)) > 0 and not bool(md.get("gold_group_present_final", False)):
        return "alternative_matured_but_still_low_value"
    if repeat_rate >= 0.65 or bool(md.get("repeated_same_branch_expansion_dominated_budget", False)):
        return "repeat_or_cap_threshold_too_weak"
    if avg_repeat_pressure >= 0.08 and _safe_float(md.get("top_branch_expand_share", 0.0)) < _safe_float(
        bmd.get("top_branch_expand_share", 0.0)
    ):
        return "repeat_penalty_too_strong"
    if (
        avg_repeat_pressure >= 0.06
        and _safe_float(md.get("answer_group_diversity_realized", 0.0)) > _safe_float(bmd.get("answer_group_diversity_realized", 0.0))
        and not bool(md.get("gold_group_ever_present", False))
        and bool(bmd.get("gold_group_ever_present", False))
    ):
        return "anti_collapse_blocked_good_incumbent_continuation"
    return "anti_collapse_blocked_good_incumbent_continuation" if repeat_rate <= 0.50 else "repeat_or_cap_threshold_too_weak"


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
                            "repeated_same_family_expansion_rate": _mean(
                                [_safe_float((r.get("metadata") or {}).get("repeated_same_family_expansion_rate", 0.0)) for r in rows]
                            ),
                            "repeated_same_family_expansion_count": sum(
                                _safe_int((r.get("metadata") or {}).get("repeated_same_family_expansion_count", 0)) for r in rows
                            ),
                            "max_consecutive_same_branch": _mean(
                                [_safe_float((r.get("metadata") or {}).get("max_consecutive_same_branch", 0.0)) for r in rows]
                            ),
                            "max_consecutive_same_family": _mean(
                                [_safe_float((r.get("metadata") or {}).get("max_consecutive_same_family", 0.0)) for r in rows]
                            ),
                            "repeat_penalty_trigger_count": sum(
                                _safe_int((r.get("metadata") or {}).get("repeat_penalty_trigger_count", 0)) for r in rows
                            ),
                            "repeat_penalty_override_count": sum(
                                _safe_int((r.get("metadata") or {}).get("repeat_penalty_override_count", 0)) for r in rows
                            ),
                            "repeat_penalty_alternative_selected_count": sum(
                                _safe_int((r.get("metadata") or {}).get("repeat_penalty_alternative_selected_count", 0)) for r in rows
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

    pairwise_vs_baseline: dict[str, dict[str, Any]] = {}
    for alias in methods:
        if alias == "baseline_broad":
            continue
        outcomes = {"improved": 0, "harmed": 0, "unchanged": 0}
        repeat_attr = {"improved": 0, "harmed": 0}
        harmed_rows: list[dict[str, Any]] = []
        subtypes: Counter[str] = Counter()
        for key, pair in aligned.items():
            b = pair.get("baseline_broad")
            c = pair.get(alias)
            if not b or not c:
                continue
            if (not b["is_correct"]) and c["is_correct"]:
                outcomes["improved"] += 1
                if _safe_int((c.get("metadata") or {}).get("repeat_penalty_alternative_selected_count", 0)) > 0:
                    repeat_attr["improved"] += 1
            elif b["is_correct"] and (not c["is_correct"]):
                outcomes["harmed"] += 1
                if _safe_int((c.get("metadata") or {}).get("repeat_penalty_alternative_selected_count", 0)) > 0:
                    repeat_attr["harmed"] += 1
                subtype = _harmed_subtype(baseline_row=b, candidate_row=c)
                subtypes[subtype] += 1
                harmed_rows.append(
                    {
                        "dataset": key[0],
                        "seed": key[1],
                        "budget": key[2],
                        "example_id": key[3],
                        "gold_answer": b.get("gold_answer"),
                        "baseline_prediction": b.get("prediction"),
                        "candidate_prediction": c.get("prediction"),
                        "candidate_method_alias": alias,
                        "harmed_subtype": subtype,
                        "candidate_regime_failure_category": str((c.get("metadata") or {}).get("regime_failure_category", "")),
                        "candidate_early_divergence_failure_category": str(
                            (c.get("metadata") or {}).get("early_divergence_failure_category", "")
                        ),
                    }
                )
            else:
                outcomes["unchanged"] += 1
        pairwise_vs_baseline[alias] = {
            "improved_harmed_unchanged": outcomes,
            "repeat_penalty_attributable_improved_harmed": repeat_attr,
            "harmed_case_subtype_breakdown": dict(sorted(subtypes.items(), key=lambda kv: (-kv[1], kv[0]))),
            "harmed_cases_count": len(harmed_rows),
            "harmed_cases": harmed_rows,
        }

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
            "mean_repeated_same_family_expansion_rate": _mean(
                [_safe_float(r["repeated_same_family_expansion_rate"]) for r in rows]
            ),
            "total_repeated_same_family_expansion_count": int(
                sum(_safe_int(r["repeated_same_family_expansion_count"]) for r in rows)
            ),
            "mean_max_consecutive_same_branch": _mean([_safe_float(r["max_consecutive_same_branch"]) for r in rows]),
            "mean_max_consecutive_same_family": _mean([_safe_float(r["max_consecutive_same_family"]) for r in rows]),
            "total_repeat_penalty_trigger_count": int(sum(_safe_int(r["repeat_penalty_trigger_count"]) for r in rows)),
            "total_repeat_penalty_override_count": int(sum(_safe_int(r["repeat_penalty_override_count"]) for r in rows)),
            "total_repeat_penalty_alternative_selected_count": int(
                sum(_safe_int(r["repeat_penalty_alternative_selected_count"]) for r in rows)
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
        "pairwise_vs_baseline": {
            alias: {
                "improved_harmed_unchanged": data["improved_harmed_unchanged"],
                "repeat_penalty_attributable_improved_harmed": data["repeat_penalty_attributable_improved_harmed"],
                "harmed_case_subtype_breakdown": data["harmed_case_subtype_breakdown"],
            }
            for alias, data in pairwise_vs_baseline.items()
        },
        "primary_question_answer": {
            "accuracy_delta_refinement_vs_baseline": _safe_float(overall.get("anti_collapse_refinement", {}).get("mean_accuracy", 0.0))
            - _safe_float(overall.get("baseline_broad", {}).get("mean_accuracy", 0.0)),
            "accuracy_delta_repeat_fine_vs_baseline": _safe_float(
                overall.get("anti_collapse_repeat_fine", {}).get("mean_accuracy", 0.0)
            )
            - _safe_float(overall.get("baseline_broad", {}).get("mean_accuracy", 0.0)),
            "accuracy_delta_repeat_fine_vs_refinement": _safe_float(
                overall.get("anti_collapse_repeat_fine", {}).get("mean_accuracy", 0.0)
            )
            - _safe_float(overall.get("anti_collapse_refinement", {}).get("mean_accuracy", 0.0)),
            "repeated_same_branch_expansion_rate_delta_repeat_fine_vs_refinement": _safe_float(
                overall.get("anti_collapse_repeat_fine", {}).get("mean_repeated_same_branch_expansion_rate", 0.0)
            )
            - _safe_float(overall.get("anti_collapse_refinement", {}).get("mean_repeated_same_branch_expansion_rate", 0.0)),
            "repeated_same_branch_expansion_rate_delta_vs_baseline": _safe_float(
                overall.get("anti_collapse_refinement", {}).get("mean_repeated_same_branch_expansion_rate", 0.0)
            )
            - _safe_float(overall.get("baseline_broad", {}).get("mean_repeated_same_branch_expansion_rate", 0.0)),
            "matured_alternative_count_delta_vs_baseline": _safe_int(
                overall.get("anti_collapse_refinement", {}).get("total_matured_alternative_count", 0)
            )
            - _safe_int(overall.get("baseline_broad", {}).get("total_matured_alternative_count", 0)),
            "repeated_same_family_expansion_rate_delta_repeat_fine_vs_refinement": _safe_float(
                overall.get("anti_collapse_repeat_fine", {}).get("mean_repeated_same_family_expansion_rate", 0.0)
            )
            - _safe_float(overall.get("anti_collapse_refinement", {}).get("mean_repeated_same_family_expansion_rate", 0.0)),
        },
    }

    (out_dir / "per_example_rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n", encoding="utf-8")
    (out_dir / "method_metrics.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in metric_rows) + "\n", encoding="utf-8")
    (out_dir / "comparison_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "pairwise_vs_baseline_harmed_cases.json").write_text(
        json.dumps(pairwise_vs_baseline, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
