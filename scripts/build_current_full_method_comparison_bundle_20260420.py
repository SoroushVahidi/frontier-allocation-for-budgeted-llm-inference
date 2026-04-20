#!/usr/bin/env python3
"""Build current full method comparison bundle (2026-04-20) with smart reuse.

Policy:
- Reuse valid prior rows from full_method_comparison_bundle/20260419T214335Z.
- Run only missing method rows needed for current broad-family full integrated line.
- Emit machine-readable ranking + fairness/reuse manifests.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.output_layer_repair import canonicalize_answer  # noqa: E402

PREV_RUN_DIR = REPO_ROOT / "outputs/full_method_comparison_bundle/20260419T214335Z"
OUT_DIR = REPO_ROOT / "outputs/current_full_method_comparison_bundle_20260420"

DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
SEEDS = [11, 23]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]

LATEST_FULL_BASE_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1"
)
LATEST_FULL_METHOD = f"{LATEST_FULL_BASE_METHOD}__deterministic_output_layer_repair_v1"

NEW_METHODS_TO_RUN = [
    "broad_diversity_aggregation_strong_v1",
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1",
    LATEST_FULL_BASE_METHOD,
]

EXCLUDED_METHODS = [
    {
        "method": "best_route",
        "reason": "import_validated_only",
        "detail": "adjacent import-validated path only; no direct matched rows in canonical in-repo run",
    },
    {
        "method": "when_solve_when_verify",
        "reason": "import_validated_only",
        "detail": "adjacent import-validated path only; no direct matched rows in canonical in-repo run",
    },
    {
        "method": "cascade_routing",
        "reason": "import_validated_only",
        "detail": "adjacent import-validated path only; no direct matched rows in canonical in-repo run",
    },
    {
        "method": "mob_majority_of_bests",
        "reason": "import_validated_only",
        "detail": "adjacent import-validated path only; no direct matched rows in canonical in-repo run",
    },
    {
        "method": "rest_mcts",
        "reason": "import_validated_only",
        "detail": "adjacent import-validated path only; no direct matched rows in canonical in-repo run",
    },
    {
        "method": "openr",
        "reason": "import_validated_only",
        "detail": "adjacent import-validated path only; no direct matched rows in canonical in-repo run",
    },
    {
        "method": "compute_optimal_tts",
        "reason": "blocked",
        "detail": "blocked in canonical baseline completeness status",
    },
]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _to_int(v: Any) -> int:
    return int(float(v))


def _to_float(v: Any) -> float:
    return float(v)


def _safe_mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda r: (
            -float(r["mean_accuracy"]),
            float(r["mean_avg_actions"]),
            -float(r["mean_coverage"]),
            str(r["method"]),
        ),
    )
    out: list[dict[str, Any]] = []
    for i, r in enumerate(ranked, start=1):
        out.append({**r, "rank": i})
    return out


def _method_family(method: str) -> tuple[str, str, str]:
    if method == LATEST_FULL_METHOD:
        return ("our_latest_full_integrated", "direct_plus_output_layer_repair", "new_run")
    if method in {
        "broad_diversity_aggregation_strong_v1",
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1",
        LATEST_FULL_BASE_METHOD,
    }:
        return ("our_broad_family_variant", "direct", "new_run")
    if method.startswith("external_"):
        return ("external_baseline", "adapter_mode_a", "reused")
    if method in {"adaptive_min_expand_0", "adaptive_min_expand_1", "adaptive_min_expand_2"}:
        return ("earlier_repo_line", "direct", "reused")
    return ("internal_baseline", "direct", "reused")


def _is_correct_with_repair(prediction: str | None, gold_answer: str, dataset: str) -> bool:
    if prediction is None:
        return False
    pred_raw = str(prediction)
    repaired_pred = canonicalize_answer(pred_raw, dataset=dataset)
    repaired_gold = canonicalize_answer(str(gold_answer), dataset=dataset)
    if repaired_pred is not None and repaired_gold is not None:
        return repaired_pred == repaired_gold
    # conservative fallback to shared normalization
    return normalize_answer_text(pred_raw).get("normalized_answer") == normalize_answer_text(str(gold_answer)).get("normalized_answer")


def build_bundle() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prev_method_rows = _read_csv(PREV_RUN_DIR / "per_seed_method_metrics.csv")
    prev_example_rows = _read_csv(PREV_RUN_DIR / "per_example_outcomes.csv")

    # Build lookup for question/ground_truth so we can enrich new rows.
    ex_lookup: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    for r in prev_example_rows:
        key = (str(r["dataset"]), _to_int(r["seed"]), _to_int(r["budget"]), str(r["example_id"]))
        ex_lookup[key] = r

    new_method_rows: list[dict[str, Any]] = []
    new_example_rows: list[dict[str, Any]] = []

    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            example_lookup = {ex.example_id: asdict(ex) for ex in examples}
            rng = random.Random(1000003 * seed + 17)
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
            for budget in BUDGETS:
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    ADAPTIVE_GRID,
                    rng,
                    use_openai_api=False,
                    vgs_candidates=3,
                    vgs_min_expansions=1,
                    include_external_s1_baseline=False,
                    include_external_tale_baseline=False,
                    include_external_l1_baseline=False,
                    include_broad_diversity_aggregation_methods=True,
                )
                target_strats = {m: strategies[m] for m in NEW_METHODS_TO_RUN}
                metrics, rows = evaluate_strategies_on_examples(examples, target_strats)

                for method, metric in metrics.items():
                    family, comparability, source = _method_family(method)
                    new_method_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": method,
                            "family": family,
                            "comparability": comparability,
                            "status": "runnable_direct",
                            "n_eval_examples": int(metric["n_examples"]),
                            "accuracy": float(metric["accuracy"]),
                            "avg_actions": float(metric["avg_actions"]),
                            "avg_expansions": float(metric["avg_expansions"]),
                            "avg_verifications": float(metric["avg_verifications"]),
                            "coverage": 1.0,
                            "defer_rate": 0.0,
                            "abstention_rate": 0.0,
                            "budget_exhaustion_rate": float(metric["budget_exhaustion_rate"]),
                            "underspend_rate": float(max(0.0, 1.0 - (float(metric["avg_actions"]) / float(budget)))),
                            "result_origin": source,
                        }
                    )

                for row in rows:
                    ex = example_lookup[row["example_id"]]
                    metadata = row.get("metadata", {}) or {}
                    pred = row.get("prediction")
                    if pred is None and metadata.get("final_prediction") is not None:
                        pred = metadata.get("final_prediction")
                    base_method = str(row["strategy"])
                    is_correct = bool(row["is_correct"])
                    out_method = base_method

                    if base_method == LATEST_FULL_BASE_METHOD:
                        repaired_correct = bool(row["is_correct"])
                        if pred is not None:
                            repaired_correct = _is_correct_with_repair(pred, str(ex["answer"]), dataset)
                        out_method = LATEST_FULL_METHOD
                        is_correct = bool(repaired_correct)

                    family, comparability, source = _method_family(out_method)
                    new_example_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": row["example_id"],
                            "question": ex["question"],
                            "ground_truth": ex["answer"],
                            "method": out_method,
                            "is_correct": bool(is_correct),
                            "prediction": "" if pred is None else str(pred),
                            "actions_used": int(row["actions_used"]),
                            "expansions": int(row["expansions"]),
                            "verifications": int(row["verifications"]),
                            "budget_exhausted": bool(row["budget_exhausted"]),
                            "gold_group_ever_present": bool(metadata.get("gold_group_ever_present", False)),
                            "metadata_json": json.dumps(metadata, sort_keys=True),
                            "result_origin": source,
                            "family": family,
                            "comparability": comparability,
                        }
                    )

    # Add metric rows for repaired latest full method alias from per-example rows.
    combo_rows = [
        r
        for r in new_example_rows
        if str(r["method"]) == LATEST_FULL_METHOD
    ]
    grouped_alias: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    for r in combo_rows:
        k = (str(r["dataset"]), _to_int(r["seed"]), _to_int(r["budget"]))
        grouped_alias.setdefault(k, []).append(r)
    for (dataset, seed, budget), rows in grouped_alias.items():
        family, comparability, source = _method_family(LATEST_FULL_METHOD)
        n = len(rows)
        acc = _safe_mean([1.0 if bool(x["is_correct"]) else 0.0 for x in rows])
        avg_actions = _safe_mean([float(x["actions_used"]) for x in rows])
        avg_expansions = _safe_mean([float(x["expansions"]) for x in rows])
        avg_verifications = _safe_mean([float(x["verifications"]) for x in rows])
        budget_exhaustion_rate = _safe_mean([1.0 if bool(x["budget_exhausted"]) else 0.0 for x in rows])
        new_method_rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "method": LATEST_FULL_METHOD,
                "family": family,
                "comparability": comparability,
                "status": "runnable_direct",
                "n_eval_examples": n,
                "accuracy": acc,
                "avg_actions": avg_actions,
                "avg_expansions": avg_expansions,
                "avg_verifications": avg_verifications,
                "coverage": 1.0,
                "defer_rate": 0.0,
                "abstention_rate": 0.0,
                "budget_exhaustion_rate": budget_exhaustion_rate,
                "underspend_rate": float(max(0.0, 1.0 - (avg_actions / float(budget)))),
                "result_origin": source,
            }
        )

    # Reuse rows from prior bundle.
    reused_method_rows: list[dict[str, Any]] = []
    for r in prev_method_rows:
        method = str(r["method"])
        family, comparability, _ = _method_family(method)
        reused_method_rows.append(
            {
                **r,
                "family": family,
                "comparability": comparability,
                "status": "runnable_direct",
                "result_origin": "reused",
            }
        )

    reused_example_rows: list[dict[str, Any]] = []
    for r in prev_example_rows:
        method = str(r["method"])
        family, comparability, _ = _method_family(method)
        reused_example_rows.append(
            {
                **r,
                "prediction": "",
                "gold_group_ever_present": "",
                "family": family,
                "comparability": comparability,
                "result_origin": "reused",
            }
        )

    all_method_rows = reused_method_rows + new_method_rows
    all_example_rows = reused_example_rows + new_example_rows

    # Aggregate method metrics from per-seed rows (for harmonized columns).
    by_method: dict[str, list[dict[str, Any]]] = {}
    for r in all_method_rows:
        by_method.setdefault(str(r["method"]), []).append(r)

    per_method: list[dict[str, Any]] = []
    for method, rows in sorted(by_method.items()):
        per_method.append(
            {
                "method": method,
                "family": rows[0]["family"],
                "comparability": rows[0]["comparability"],
                "status": rows[0].get("status", "runnable_direct"),
                "result_origin": (
                    "new_run" if any(str(x.get("result_origin", "")) == "new_run" for x in rows) else "reused"
                ),
                "mean_accuracy": _safe_mean([_to_float(x["accuracy"]) for x in rows]),
                "mean_avg_actions": _safe_mean([_to_float(x["avg_actions"]) for x in rows]),
                "mean_coverage": _safe_mean([_to_float(x["coverage"]) for x in rows]),
                "mean_budget_exhaustion_rate": _safe_mean([_to_float(x["budget_exhaustion_rate"]) for x in rows]),
                "n_rows": len(rows),
            }
        )

    ranking = _rank(per_method)

    # per-dataset / per-budget ranking
    per_dataset: list[dict[str, Any]] = []
    for dataset in DATASETS:
        rows = [r for r in all_method_rows if str(r["dataset"]) == dataset]
        methods = sorted(set(str(r["method"]) for r in rows))
        compact: list[dict[str, Any]] = []
        for m in methods:
            mr = [x for x in rows if str(x["method"]) == m]
            compact.append(
                {
                    "dataset": dataset,
                    "method": m,
                    "family": mr[0]["family"],
                    "result_origin": "new_run" if any(str(x.get("result_origin", "")) == "new_run" for x in mr) else "reused",
                    "mean_accuracy": _safe_mean([_to_float(x["accuracy"]) for x in mr]),
                    "mean_avg_actions": _safe_mean([_to_float(x["avg_actions"]) for x in mr]),
                    "mean_coverage": _safe_mean([_to_float(x["coverage"]) for x in mr]),
                }
            )
        per_dataset.extend(_rank(compact))

    per_budget: list[dict[str, Any]] = []
    for budget in BUDGETS:
        rows = [r for r in all_method_rows if _to_int(r["budget"]) == budget]
        methods = sorted(set(str(r["method"]) for r in rows))
        compact: list[dict[str, Any]] = []
        for m in methods:
            mr = [x for x in rows if str(x["method"]) == m]
            compact.append(
                {
                    "budget": budget,
                    "method": m,
                    "family": mr[0]["family"],
                    "result_origin": "new_run" if any(str(x.get("result_origin", "")) == "new_run" for x in mr) else "reused",
                    "mean_accuracy": _safe_mean([_to_float(x["accuracy"]) for x in mr]),
                    "mean_avg_actions": _safe_mean([_to_float(x["avg_actions"]) for x in mr]),
                    "mean_coverage": _safe_mean([_to_float(x["coverage"]) for x in mr]),
                }
            )
        per_budget.extend(_rank(compact))

    # Win/loss vs latest full method.
    index_by_key: dict[tuple[str, int, int, str, str], dict[str, Any]] = {}
    for r in all_example_rows:
        key = (str(r["dataset"]), _to_int(r["seed"]), _to_int(r["budget"]), str(r["example_id"]), str(r["method"]))
        index_by_key[key] = r

    methods = sorted(set(str(r["method"]) for r in all_method_rows if str(r["method"]) != LATEST_FULL_METHOD))
    win_loss: list[dict[str, Any]] = []
    for m in methods:
        ours_wins = 0
        other_wins = 0
        ties = 0
        for dataset in DATASETS:
            for seed in SEEDS:
                for budget in BUDGETS:
                    ours_rows = [
                        x
                        for x in all_example_rows
                        if str(x["dataset"]) == dataset
                        and _to_int(x["seed"]) == seed
                        and _to_int(x["budget"]) == budget
                        and str(x["method"]) == LATEST_FULL_METHOD
                    ]
                    for ours in ours_rows:
                        ex_id = str(ours["example_id"])
                        other = index_by_key.get((dataset, seed, budget, ex_id, m))
                        if ours is None:
                            continue
                        if other is None:
                            continue
                        o = bool(ours["is_correct"])
                        b = bool(other["is_correct"])
                        if o and (not b):
                            ours_wins += 1
                        elif (not o) and b:
                            other_wins += 1
                        else:
                            ties += 1
        win_loss.append(
            {
                "our_method": LATEST_FULL_METHOD,
                "other_method": m,
                "ours_wins": ours_wins,
                "other_wins": other_wins,
                "ties": ties,
                "total_compared": ours_wins + other_wins + ties,
                "net_margin_other_minus_ours": other_wins - ours_wins,
            }
        )

    # determine top competitor by ranking.
    top_competitor = next((r["method"] for r in ranking if r["method"] != LATEST_FULL_METHOD), None)
    top2 = [r["method"] for r in ranking if r["method"] != LATEST_FULL_METHOD][:2]

    # Targeted rerun only for top competitors to get prediction strings.
    top_comp_predictions: dict[tuple[str, int, int, str, str], str] = {}
    if top2:
        for dataset in DATASETS:
            for seed in SEEDS:
                examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
                rng = random.Random(1000003 * seed + 17)
                factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
                for budget in BUDGETS:
                    strats = build_frontier_strategies(
                        factory,
                        budget,
                        ADAPTIVE_GRID,
                        rng,
                        use_openai_api=False,
                        include_external_s1_baseline=True,
                        include_external_tale_baseline=True,
                        include_external_l1_baseline=True,
                        include_broad_diversity_aggregation_methods=any(m.startswith("broad_diversity_aggregation") for m in top2),
                    )
                    chosen = {m: strats[m] for m in top2 if m in strats}
                    if not chosen:
                        continue
                    _, rows = evaluate_strategies_on_examples(examples, chosen)
                    for row in rows:
                        md = row.get("metadata", {}) or {}
                        pred = row.get("prediction")
                        if pred is None and md.get("final_prediction") is not None:
                            pred = md.get("final_prediction")
                        key = (dataset, seed, budget, str(row["example_id"]), str(row["strategy"]))
                        top_comp_predictions[key] = "" if pred is None else str(pred)

    defeat_rows: list[dict[str, Any]] = []
    if top_competitor is not None:
        for r in all_example_rows:
            if str(r["method"]) != LATEST_FULL_METHOD:
                continue
            dataset = str(r["dataset"])
            seed = _to_int(r["seed"])
            budget = _to_int(r["budget"])
            exid = str(r["example_id"])
            other = index_by_key.get((dataset, seed, budget, exid, top_competitor))
            if other is None:
                continue
            if bool(r["is_correct"]) or (not bool(other["is_correct"])):
                continue
            winner_pred = top_comp_predictions.get((dataset, seed, budget, exid, top_competitor), "")
            fail_subtype = "tree_missing_gold"
            if bool(r.get("gold_group_ever_present", False)):
                fail_subtype = "tree_contains_gold_but_final_selection_or_output_layer"
            defeat_rows.append(
                {
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": exid,
                    "our_method": LATEST_FULL_METHOD,
                    "competitor_method": top_competitor,
                    "our_answer": str(r.get("prediction", "")),
                    "winner_answer": winner_pred,
                    "ground_truth": str(r.get("ground_truth", "")),
                    "correct_answer_was_in_our_tree": bool(r.get("gold_group_ever_present", False)),
                    "brief_failure_subtype": fail_subtype,
                }
            )
    defeat_rows = sorted(defeat_rows, key=lambda x: (x["dataset"], x["seed"], x["budget"], x["example_id"]))[:80]

    method_status_table: list[dict[str, Any]] = []
    for r in ranking:
        method_status_table.append(
            {
                "method": r["method"],
                "family": r["family"],
                "comparability": r["comparability"],
                "status": "included_in_ranking",
                "result_origin": r["result_origin"],
                "exclusion_reason": "",
            }
        )
    for ex in EXCLUDED_METHODS:
        method_status_table.append(
            {
                "method": ex["method"],
                "family": "external_baseline",
                "comparability": "adjacent_or_blocked",
                "status": "excluded",
                "result_origin": "n/a",
                "exclusion_reason": f"{ex['reason']}: {ex['detail']}",
            }
        )

    summary = {
        "bundle_id": "current_full_method_comparison_bundle_20260420",
        "latest_full_base_method": LATEST_FULL_BASE_METHOD,
        "latest_full_method_evaluated": LATEST_FULL_METHOD,
        "datasets": DATASETS,
        "seeds": SEEDS,
        "budgets": BUDGETS,
        "subset_size": SUBSET_SIZE,
        "ranking_rule": {
            "primary": "mean_accuracy on matched dataset x seed x budget rows",
            "tie_break_1": "lower mean_avg_actions",
            "tie_break_2": "higher mean_coverage",
            "tie_break_3": "lexical method name",
        },
        "top_method": ranking[0]["method"] if ranking else None,
        "our_method_rank": next((r for r in ranking if r["method"] == LATEST_FULL_METHOD), None),
        "top_competitor_for_defeat_registry": top_competitor,
    }

    reuse_manifest = {
        "reused_artifact_root": str(PREV_RUN_DIR.relative_to(REPO_ROOT)),
        "reused_methods": sorted(set(str(r["method"]) for r in reused_method_rows)),
        "newly_run_methods": NEW_METHODS_TO_RUN + [LATEST_FULL_METHOD],
        "reused_row_counts": {
            "per_seed_method_metrics_rows": len(reused_method_rows),
            "per_example_outcomes_rows": len(reused_example_rows),
        },
        "new_row_counts": {
            "per_seed_method_metrics_rows": len(new_method_rows),
            "per_example_outcomes_rows": len(new_example_rows),
        },
        "targeted_prediction_reruns": {
            "methods": top2,
            "purpose": "obtain winner answers for compact defeat registry",
        },
    }

    fairness_notes = {
        "matched_surface": {
            "datasets": DATASETS,
            "seeds": SEEDS,
            "budgets": BUDGETS,
            "subset_size": SUBSET_SIZE,
        },
        "omissions": [
            {
                "dataset": "olympiadbench",
                "reason": "not in prior canonical reusable artifact surface; adding it would force broad baseline reruns",
            }
        ],
        "output_layer_repair_application": {
            "applied_to": LATEST_FULL_METHOD,
            "policy": "deterministic canonicalized final-answer evaluation",
            "note": "conservative deterministic repair on output answer; does not alter search trajectory",
        },
    }

    assumptions = {
        "assumptions": [
            "prior 2026-04-19 bundle rows are valid and comparable on the same dataset/seed/budget surface",
            "simulator mode determinism follows repository defaults for this bounded comparison",
            "deterministic output-layer repair is represented as canonicalized exact-answer evaluation for latest full method",
        ],
        "caveats": [
            "older reused per-example rows do not carry prediction strings; winner answers come from targeted reruns for top competitors only",
            "olympiadbench excluded in this canonical current bundle to avoid non-essential full recomputation",
            "this is bounded subset evaluation (20 examples per dataset/seed), not paper-scale final evidence",
        ],
    }

    # Output writes.
    _write_csv(OUT_DIR / "per_dataset_ranking.csv", per_dataset)
    _write_csv(OUT_DIR / "per_budget_ranking.csv", per_budget)
    _write_csv(OUT_DIR / "method_status_table.csv", method_status_table)
    _write_csv(OUT_DIR / "headline_ranking.csv", ranking)

    (OUT_DIR / "aggregate_comparison_summary.json").write_text(json.dumps({"ranking": ranking, "summary": summary}, indent=2), encoding="utf-8")
    (OUT_DIR / "ranking_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "reuse_vs_new_run_manifest.json").write_text(json.dumps(reuse_manifest, indent=2), encoding="utf-8")
    (OUT_DIR / "fairness_and_coverage_notes.json").write_text(json.dumps(fairness_notes, indent=2), encoding="utf-8")
    (OUT_DIR / "win_loss_registry.json").write_text(json.dumps(win_loss, indent=2), encoding="utf-8")
    (OUT_DIR / "assumptions_and_caveats.json").write_text(json.dumps(assumptions, indent=2), encoding="utf-8")

    (OUT_DIR / "_debug_per_seed_method_metrics_merged.csv").write_text("", encoding="utf-8")
    _write_csv(OUT_DIR / "_debug_per_seed_method_metrics_merged.csv", all_method_rows)
    _write_csv(OUT_DIR / "_debug_per_example_outcomes_merged.csv", all_example_rows)

    (OUT_DIR / "defeat_registry_latest_full_vs_top_competitor.csv").write_text("", encoding="utf-8")
    _write_csv(OUT_DIR / "defeat_registry_latest_full_vs_top_competitor.csv", defeat_rows)

    return {
        "summary": summary,
        "ranking": ranking,
        "top_competitor": top_competitor,
        "defeat_count": len(defeat_rows),
        "reuse_manifest": reuse_manifest,
    }


def write_status_note(bundle: dict[str, Any]) -> None:
    summary = bundle["summary"]
    ranking = bundle["ranking"]
    our_row = summary.get("our_method_rank") or {}
    top = ranking[0] if ranking else {}
    our_rank = our_row.get("rank")
    top_comp = bundle.get("top_competitor")

    # Win/loss highlights.
    win_loss = json.loads((OUT_DIR / "win_loss_registry.json").read_text(encoding="utf-8"))
    wl_sorted_loss = sorted(win_loss, key=lambda r: int(r["net_margin_other_minus_ours"]), reverse=True)
    wl_sorted_win = sorted(
        [r for r in win_loss if int(r["net_margin_other_minus_ours"]) < 0],
        key=lambda r: int(r["net_margin_other_minus_ours"]),
    )

    lines = [
        "# Current full method comparison bundle status (2026-04-20)",
        "",
        "## 1) Exact current full method name",
        f"- Base integrated controller: `{LATEST_FULL_BASE_METHOD}`.",
        f"- Current full method evaluated in this bundle: `{LATEST_FULL_METHOD}` (base controller + deterministic output-layer repair evaluation).",
        "",
        "## 2) Comparison methods included",
    ]
    for r in ranking:
        lines.append(f"- `{r['method']}` ({r['family']}; origin={r['result_origin']}).")

    lines += [
        "",
        "## 3) Datasets included",
        f"- {', '.join(DATASETS)}.",
        f"- Matched seeds: {SEEDS}; matched budgets: {BUDGETS}; subset size per dataset-seed: {SUBSET_SIZE}.",
        "",
        "## 4) Reused vs newly run",
        f"- Reused prior artifact: `outputs/full_method_comparison_bundle/20260419T214335Z/`.",
        f"- Newly run methods: {', '.join(NEW_METHODS_TO_RUN)} plus repaired-view method alias `{LATEST_FULL_METHOD}`.",
        "",
        "## 5) #1 overall under current bundle",
        f"- Rank #1: `{top.get('method')}` with mean accuracy {top.get('mean_accuracy'):.4f}.",
        "",
        "## 6) Our current full method overall rank",
        f"- `{LATEST_FULL_METHOD}` rank: #{our_rank} with mean accuracy {float(our_row.get('mean_accuracy', 0.0)):.4f}.",
        "",
        "## 7) Where our method wins",
    ]
    if wl_sorted_win:
        for row in wl_sorted_win[:5]:
            lines.append(
                f"- vs `{row['other_method']}`: net margin (other-ours) = {row['net_margin_other_minus_ours']} "
                f"(ours_wins={row['ours_wins']}, other_wins={row['other_wins']})."
            )
    else:
        lines.append("- No net-positive pairwise wins under this bounded matched surface.")

    lines += [
        "",
        "## 8) Where our method loses",
    ]
    for row in wl_sorted_loss[:5]:
        lines.append(
            f"- vs `{row['other_method']}`: net margin (other-ours) = {row['net_margin_other_minus_ours']} "
            f"(other_wins={row['other_wins']}, ours_wins={row['ours_wins']})."
        )

    lines += [
        "",
        "## 9) Remaining reviewer-defensibility gaps",
        "- External adjacent baselines remain excluded from numeric ranking without direct import package runs.",
        "- This bundle is bounded (3 datasets, 2 seeds, budgets 4/6/8, subset size 20).",
        "- Only top competitors were rerun for prediction-string defeat registry; older reused rows lack prediction fields.",
        "",
        "## Defeat registry note",
        f"- Top competitor used for compact defeat registry: `{top_comp}`.",
        "- See `outputs/current_full_method_comparison_bundle_20260420/defeat_registry_latest_full_vs_top_competitor.csv`.",
    ]

    (REPO_ROOT / "docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    bundle_data = build_bundle()
    write_status_note(bundle_data)
    print(json.dumps({"status": "ok", "out_dir": str(OUT_DIR.relative_to(REPO_ROOT)), "top": bundle_data["summary"]["top_method"]}, indent=2))
