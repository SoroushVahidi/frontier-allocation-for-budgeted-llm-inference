"""Offline drilldown on frontier_allocation_miss cases.

This script is diagnostic infrastructure only. It performs a deeper offline
read of the `frontier_allocation_miss` failure class produced by
`experiments/build_failure_feature_table.py`, joined against the branch/tree
diagnostics produced by `experiments/extract_branch_diagnostics.py`, to answer
questions about which misses look recoverable via runtime-legal signals and
which look risky.

Guardrails (see AGENTS.md / docs/FAILURE_FEATURE_TABLE.md):

- This script never calls a paid API.
- It never changes FTA / FIX-2+FIX-4 selector logic (support_aware_selector.py
  is imported only indirectly, through the frozen feature-table fields and the
  frozen decision helpers in experiments/explore_offline_selector_rules.py).
- `gold_in_tree` and all gold-derived fields are offline diagnostic labels
  only. They are used here to classify already-computed failure rows and to
  score exploratory rule candidates after the fact; they are never read by a
  `decision_fn` that would stand in for a runtime selector.
- Nothing here is a promoted method. Rule candidates are exploratory only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.explore_offline_selector_rules import (
    RuleSpec,
    decision_majority_override,
    evaluate_rule,
)
from experiments.failure_analysis_common import (
    as_bool,
    as_int,
    load_feature_rows,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)

TARGET_FAILURE_CLASS = "frontier_allocation_miss"

SUBTYPES = (
    "gold_in_external_unanimity",
    "gold_in_external_majority",
    "gold_in_tree_and_external",
    "gold_in_single_external_only",
    "gold_in_tree_only_not_external",
    "gold_in_tree_but_not_surfaced",
    "gold_absent_from_visible_candidates_but_tree_signal",
    "no_tree_signal_unknown",
)

SEED_ORDER = (41, 61, 71)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feature-table",
        default=None,
        help=(
            "Failure feature table JSONL. Defaults to the canonical_feature_table/ "
            "output of the latest outputs/failure_analysis/overnight_* run, which is "
            "guaranteed to be schema-consistent with --branch-diagnostics. "
            "docs/FAILURE_FEATURE_TABLE.md recommends preferring a fresh canonical "
            "rebuild over the legacy top-level outputs/failure_analysis/failure_feature_table.jsonl."
        ),
    )
    parser.add_argument(
        "--branch-diagnostics",
        default=None,
        help=(
            "branch_diagnostics_table.jsonl from experiments/extract_branch_diagnostics.py. "
            "Defaults to the branch_diagnostics/ output of the latest overnight_* run."
        ),
    )
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    return parser.parse_args()


def _latest_overnight_dir() -> Path:
    root = Path("outputs/failure_analysis")
    candidates = sorted(p for p in root.glob("overnight_*") if p.is_dir())
    if not candidates:
        raise FileNotFoundError("no outputs/failure_analysis/overnight_* directory found")
    return candidates[-1]


def resolve_input_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.feature_table and args.branch_diagnostics:
        return Path(args.feature_table), Path(args.branch_diagnostics)
    overnight_dir = _latest_overnight_dir()
    feature_table = Path(args.feature_table) if args.feature_table else (
        overnight_dir / "canonical_feature_table" / "failure_feature_table.jsonl"
    )
    branch_diagnostics = Path(args.branch_diagnostics) if args.branch_diagnostics else (
        overnight_dir / "branch_diagnostics" / "branch_diagnostics_table.jsonl"
    )
    return feature_table, branch_diagnostics


# ---------------------------------------------------------------------------
# Join feature table + branch diagnostics
# ---------------------------------------------------------------------------

BRANCH_FIELDS_TO_MERGE = (
    "result_metadata_present",
    "final_nodes_present",
    "direct_reserve_attempts_present",
    "direct_frontier_agree",
    "support_margin",
    "direct_reserve_confidence_proxy",
    "direct_reserve_source_method",
    "direct_reserve_answer",
    "frontier_candidate_answer",
    "gold_in_tree",
    "gold_in_final_nodes",
    "gold_in_direct_reserve_attempts",
    "any_tree_signal_for_gold",
    "final_nodes_count",
    "direct_reserve_attempts_count",
    "action_trace_count",
    "max_branch_depth",
    "branch_answer_group_count",
    "final_node_answer_count",
    "attempt_answer_count",
    "final_node_answers",
    "attempt_answers",
)


def join_rows(
    feature_rows: list[dict[str, Any]],
    branch_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    branch_by_row_id = {str(row.get("row_id")): row for row in branch_rows}
    joined: list[dict[str, Any]] = []
    missing_branch_rows: list[str] = []
    for row in feature_rows:
        row_id = str(row.get("row_id"))
        merged = dict(row)
        branch_row = branch_by_row_id.get(row_id)
        if branch_row is None:
            missing_branch_rows.append(row_id)
        else:
            for field in BRANCH_FIELDS_TO_MERGE:
                merged[field] = branch_row.get(field)
        joined.append(merged)
    join_stats = {
        "feature_rows": len(feature_rows),
        "branch_rows": len(branch_rows),
        "joined_rows": len(joined),
        "missing_branch_rows_count": len(missing_branch_rows),
        "missing_branch_rows": missing_branch_rows[:20],
    }
    return joined, join_stats


# ---------------------------------------------------------------------------
# Subtype classification (offline diagnostic labels only)
# ---------------------------------------------------------------------------


def classify_frontier_miss_subtype(row: dict[str, Any]) -> str:
    """Assign one of SUBTYPES to a frontier_allocation_miss row.

    This function is an offline diagnostic classifier over an already-known
    failure row (gold-derived fields included). It is never wired into a
    runtime decision path -- see decision_* functions below, which only read
    runtime-legal fields.
    """
    gold_norm = row.get("normalized_gold_answer") or row.get("gold_answer_canonical")
    external_majority_count = as_int(row.get("external_majority_count")) or 0
    external_majority_answer = row.get("external_majority_answer")
    external_unanimous = as_bool(row.get("external_answers_unanimous"))
    majority_matches_gold = (
        external_majority_answer not in (None, "")
        and gold_norm not in (None, "")
        and str(external_majority_answer) == str(gold_norm)
    )

    gold_in_tree = as_bool(row.get("gold_in_tree"))
    gold_in_final_nodes = as_bool(row.get("gold_in_final_nodes"))
    gold_in_attempts = as_bool(row.get("gold_in_direct_reserve_attempts"))
    any_candidate_correct = as_bool(row.get("any_candidate_correct"))

    if external_unanimous and majority_matches_gold and external_majority_count == 3:
        return "gold_in_external_unanimity"
    if majority_matches_gold and external_majority_count == 2:
        return "gold_in_external_majority"
    if any_candidate_correct and gold_in_tree:
        return "gold_in_tree_and_external"
    if any_candidate_correct:
        return "gold_in_single_external_only"
    if gold_in_final_nodes:
        return "gold_in_tree_only_not_external"
    if gold_in_attempts:
        return "gold_in_tree_but_not_surfaced"
    if gold_in_tree:
        return "gold_absent_from_visible_candidates_but_tree_signal"
    return "no_tree_signal_unknown"


def build_drilldown_row(row: dict[str, Any]) -> dict[str, Any]:
    gold_in_tree = as_bool(row.get("gold_in_tree"))
    gold_in_final_nodes = as_bool(row.get("gold_in_final_nodes"))
    gold_in_attempts = as_bool(row.get("gold_in_direct_reserve_attempts"))
    any_external_correct = as_bool(row.get("any_external_correct"))
    any_candidate_correct = as_bool(row.get("any_candidate_correct"))
    subtype = classify_frontier_miss_subtype(row)

    return {
        # Identity
        "row_id": row.get("row_id"),
        "example_id": row.get("example_id"),
        "source_id": row.get("source_id"),
        "seed": row.get("seed"),
        "problem_text": row.get("problem_text"),
        # Answers
        "gold_answer_canonical": row.get("gold_answer_canonical"),
        "frontier_answer": row.get("frontier_answer"),
        "l1_answer": row.get("l1_answer"),
        "s1_answer": row.get("s1_answer"),
        "tale_answer": row.get("tale_answer"),
        "fta_selected_answer": row.get("fta_selected_answer"),
        "normalized_gold_answer": row.get("normalized_gold_answer"),
        "normalized_frontier_answer": row.get("normalized_frontier_answer"),
        "normalized_l1_answer": row.get("normalized_l1_answer"),
        "normalized_s1_answer": row.get("normalized_s1_answer"),
        "normalized_tale_answer": row.get("normalized_tale_answer"),
        "normalized_fta_selected_answer": row.get("normalized_fta_selected_answer"),
        "answer_group_count": row.get("answer_group_count"),
        "answer_group_sizes": row.get("answer_group_sizes"),
        "external_majority_answer": row.get("external_majority_answer"),
        "external_majority_count": row.get("external_majority_count"),
        "external_answers_unanimous": row.get("external_answers_unanimous"),
        "frontier_correct": row.get("frontier_correct"),
        "l1_correct": row.get("l1_correct"),
        "s1_correct": row.get("s1_correct"),
        "tale_correct": row.get("tale_correct"),
        "any_external_correct": any_external_correct,
        "any_candidate_correct": any_candidate_correct,
        # Tree / metadata
        "gold_in_tree": gold_in_tree,
        "final_nodes_count": row.get("final_nodes_count"),
        "branch_count": row.get("final_nodes_count"),
        "final_node_answers": row.get("final_node_answers"),
        "direct_reserve_attempts_count": row.get("direct_reserve_attempts_count"),
        "attempt_answers": row.get("attempt_answers"),
        "frontier_support": row.get("frontier_support"),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "override_reason": row.get("override_reason"),
        "direct_frontier_agree": row.get("direct_frontier_agree"),
        "branch_answer_group_count": row.get("branch_answer_group_count"),
        "distinct_tree_answer_group_count": row.get("branch_answer_group_count"),
        "gold_in_final_nodes": gold_in_final_nodes,
        "gold_only_in_nonsurfaced_tree": bool(gold_in_attempts and not gold_in_final_nodes),
        "gold_in_direct_reserve_attempts": gold_in_attempts,
        "gold_in_external_baseline": any_external_correct,
        "gold_in_tree_and_external_baseline": bool(gold_in_tree and any_external_correct),
        "any_tree_signal_for_gold": row.get("any_tree_signal_for_gold"),
        "visible_candidate_correct": any_candidate_correct,
        # Classification
        "frontier_miss_subtype": subtype,
    }


def build_drilldown_table(joined_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    misses = [row for row in joined_rows if str(row.get("failure_class_coarse")) == TARGET_FAILURE_CLASS]
    ordered = sorted(
        misses,
        key=lambda row: (str(row.get("source_id")), int(row.get("seed") or 0), str(row.get("example_id"))),
    )
    return [build_drilldown_row(row) for row in ordered]


# ---------------------------------------------------------------------------
# Exploratory rule candidates (runtime-legal fields only)
# ---------------------------------------------------------------------------


def decision_majority_with_agree_gate(
    row: dict[str, Any],
    *,
    unanimous_only: bool = False,
    max_frontier_support: int | None = None,
    min_cpc: int | None = None,
    require_override_reason: str | None = None,
    require_direct_frontier_agree: bool | None = None,
) -> str | None:
    """Wraps the frozen decision_majority_override with a direct_frontier_agree gate.

    direct_frontier_agree is a runtime-legal result_metadata field (see
    branch_diagnostics_table.jsonl). No gold-derived or tree-signal offline
    label is read by this function.
    """
    if require_direct_frontier_agree is not None:
        if as_bool(row.get("direct_frontier_agree")) != require_direct_frontier_agree:
            return None
    return decision_majority_override(
        row,
        unanimous_only=unanimous_only,
        max_frontier_support=max_frontier_support,
        min_cpc=min_cpc,
        require_override_reason=require_override_reason,
    )


OVERRIDE_REASON_VALUES = (
    "direct_frontier_agree",
    "frontier_not_run_or_budget_exhausted",
    "frontier_support_margin_override",
    "insufficient_support_margin",
    "single_weak_frontier_branch",
)


def build_rule_specs() -> list[RuleSpec]:
    specs: list[RuleSpec] = []

    # Family 1: 2-of-3 external majority override, various runtime-legal gates.
    for threshold in (0, 1, 2, 3):
        specs.append(
            RuleSpec(
                name=f"drilldown_majority2of3_support_le_{threshold}",
                family="majority_override_support_gate",
                description=f"2/3 external majority override gated by frontier_support <= {threshold}.",
                decision_fn=lambda row, threshold=threshold: decision_majority_with_agree_gate(
                    row, max_frontier_support=threshold
                ),
            )
        )
    for threshold in (2, 3, 4):
        specs.append(
            RuleSpec(
                name=f"drilldown_majority2of3_cpc_ge_{threshold}",
                family="majority_override_cpc_gate",
                description=(
                    f"2/3 external majority override gated by candidate_pool_answer_group_count >= {threshold}."
                ),
                decision_fn=lambda row, threshold=threshold: decision_majority_with_agree_gate(
                    row, min_cpc=threshold
                ),
            )
        )
    for reason in OVERRIDE_REASON_VALUES:
        specs.append(
            RuleSpec(
                name=f"drilldown_majority2of3_reason_{reason}",
                family="majority_override_reason_gate",
                description=f"2/3 external majority override gated by override_reason == {reason}.",
                decision_fn=lambda row, reason=reason: decision_majority_with_agree_gate(
                    row, require_override_reason=reason
                ),
            )
        )
    for agree in (True, False):
        specs.append(
            RuleSpec(
                name=f"drilldown_majority2of3_direct_frontier_agree_{agree}",
                family="majority_override_agree_gate",
                description=f"2/3 external majority override gated by direct_frontier_agree == {agree}.",
                decision_fn=lambda row, agree=agree: decision_majority_with_agree_gate(
                    row, require_direct_frontier_agree=agree
                ),
            )
        )

    # Family 2: external unanimity override, various runtime-legal gates.
    for threshold in (0, 1, 2):
        specs.append(
            RuleSpec(
                name=f"drilldown_unanimous_support_le_{threshold}",
                family="unanimity_override_support_gate",
                description=f"3/3 external unanimity override gated by frontier_support <= {threshold}.",
                decision_fn=lambda row, threshold=threshold: decision_majority_with_agree_gate(
                    row, unanimous_only=True, max_frontier_support=threshold
                ),
            )
        )
    for agree in (True, False):
        specs.append(
            RuleSpec(
                name=f"drilldown_unanimous_direct_frontier_agree_{agree}",
                family="unanimity_override_agree_gate",
                description=f"3/3 external unanimity override gated by direct_frontier_agree == {agree}.",
                decision_fn=lambda row, agree=agree: decision_majority_with_agree_gate(
                    row, unanimous_only=True, require_direct_frontier_agree=agree
                ),
            )
        )
    for threshold in (2, 3, 4):
        specs.append(
            RuleSpec(
                name=f"drilldown_unanimous_cpc_ge_{threshold}",
                family="unanimity_override_cpc_gate",
                description=(
                    f"3/3 external unanimity override gated by candidate_pool_answer_group_count >= {threshold}."
                ),
                decision_fn=lambda row, threshold=threshold: decision_majority_with_agree_gate(
                    row, unanimous_only=True, min_cpc=threshold
                ),
            )
        )

    return specs


def _seed_for_source(rows: list[dict[str, Any]], source_id: str) -> int | None:
    for row in rows:
        if str(row.get("source_id")) == source_id:
            return as_int(row.get("seed"))
    return None


def evaluate_rule_with_diagnostics(
    rows: list[dict[str, Any]],
    spec: RuleSpec,
    *,
    source_to_seed: dict[str, int | None],
) -> dict[str, Any]:
    base = evaluate_rule(rows, spec)

    loso_folds: dict[str, dict[str, Any]] = {}
    for holdout_source in sorted(source_to_seed):
        test_rows = [row for row in rows if str(row.get("source_id")) == holdout_source]
        if not test_rows:
            continue
        fold_eval = evaluate_rule(test_rows, spec)
        loso_folds[holdout_source] = {
            "seed": source_to_seed.get(holdout_source),
            "row_count": fold_eval["row_count"],
            "accuracy": fold_eval["accuracy"],
            "net_wins": fold_eval["net_wins"],
            "wins": fold_eval["wins_vs_canonical_fta"],
            "losses": fold_eval["losses_vs_canonical_fta"],
        }

    robust_under_loso = bool(loso_folds) and all(
        fold["net_wins"] >= 0 for fold in loso_folds.values()
    )

    seed61_source = next(
        (source for source, seed in source_to_seed.items() if seed == 61),
        None,
    )
    especially_fails_on_seed_61 = False
    seed61_delta = None
    if seed61_source is not None:
        seed61_metrics = base["per_source_metrics"].get(seed61_source)
        if seed61_metrics is not None:
            seed61_delta = seed61_metrics["delta"]
            other_deltas = [
                item["delta"]
                for source, item in base["per_source_metrics"].items()
                if source != seed61_source
            ]
            worse_than_others = (not other_deltas) or (seed61_delta < min(other_deltas))
            especially_fails_on_seed_61 = seed61_delta < 0 and worse_than_others

    frontier_allocation_miss_wins = base["target_class_wins"]
    fta_success_regressions = base["target_class_losses"]

    return {
        **base,
        "loso_folds": loso_folds,
        "robust_under_leave_one_source_out": robust_under_loso,
        "seed61_delta": seed61_delta,
        "especially_fails_on_seed_61": especially_fails_on_seed_61,
        "frontier_allocation_miss_wins": frontier_allocation_miss_wins,
        "fta_success_regressions": fta_success_regressions,
        "runtime_legal_fields_only": base["runtime_legal_fields_only"],
    }


# ---------------------------------------------------------------------------
# Research-question diagnostics (tree signal correlation, seed 61)
# ---------------------------------------------------------------------------


def support_bucket_breakdown(miss_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    breakdown: list[dict[str, Any]] = []
    for threshold in (0, 1, 2, 3, None):
        if threshold is None:
            subset = miss_rows
            label = "all"
        else:
            subset = [
                row
                for row in miss_rows
                if (as_int(row.get("frontier_support")) is not None and as_int(row.get("frontier_support")) <= threshold)
            ]
            label = f"frontier_support_le_{threshold}"
        n = len(subset)
        recoverable = sum(
            1
            for row in subset
            if row.get("frontier_miss_subtype")
            in ("gold_in_external_unanimity", "gold_in_external_majority", "gold_in_tree_and_external")
        )
        breakdown.append(
            {
                "bucket": label,
                "row_count": n,
                "recoverable_via_external_signal_count": recoverable,
                "share_of_all_misses": round(n / len(miss_rows), 6) if miss_rows else None,
                "recoverable_share_within_bucket": round(recoverable / n, 6) if n else None,
            }
        )
    return breakdown


def candidate_pool_group_count_breakdown(miss_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    breakdown: list[dict[str, Any]] = []
    for threshold in (2, 3, 4):
        subset = [
            row
            for row in miss_rows
            if (as_int(row.get("candidate_pool_answer_group_count")) or 0) >= threshold
        ]
        n = len(subset)
        recoverable = sum(
            1
            for row in subset
            if row.get("frontier_miss_subtype")
            in ("gold_in_external_unanimity", "gold_in_external_majority", "gold_in_tree_and_external")
        )
        breakdown.append(
            {
                "bucket": f"candidate_pool_answer_group_count_ge_{threshold}",
                "row_count": n,
                "recoverable_via_external_signal_count": recoverable,
                "recoverable_share_within_bucket": round(recoverable / n, 6) if n else None,
            }
        )
    return breakdown


def unanimity_vs_majority_safety(rule_evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    unanimity_rules = [item for item in rule_evaluations if item["family"].startswith("unanimity_override")]
    majority_rules = [item for item in rule_evaluations if item["family"].startswith("majority_override")]

    def _avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 6) if values else None

    return {
        "unanimity_rule_count": len(unanimity_rules),
        "majority_rule_count": len(majority_rules),
        "unanimity_avg_losses_vs_canonical_fta": _avg([item["losses_vs_canonical_fta"] for item in unanimity_rules]),
        "majority_avg_losses_vs_canonical_fta": _avg([item["losses_vs_canonical_fta"] for item in majority_rules]),
        "unanimity_avg_net_wins": _avg([item["net_wins"] for item in unanimity_rules]),
        "majority_avg_net_wins": _avg([item["net_wins"] for item in majority_rules]),
    }


def seed61_regression_breakdown(rows: list[dict[str, Any]], source_to_seed: dict[str, int | None]) -> dict[str, Any]:
    seed61_source = next((source for source, seed in source_to_seed.items() if seed == 61), None)
    if seed61_source is None:
        return {"seed61_source": None}
    seed61_rows = [row for row in rows if str(row.get("source_id")) == seed61_source]
    seed61_misses = [row for row in seed61_rows if str(row.get("failure_class_coarse")) == TARGET_FAILURE_CLASS]
    gold_letter_rows = [
        row for row in seed61_misses if str(row.get("gold_answer_canonical") or "").strip().upper() in {"A", "B", "C", "D", "E"}
    ]
    override_reason_counts = Counter(str(row.get("override_reason")) for row in seed61_misses)
    return {
        "seed61_source": seed61_source,
        "seed61_row_count": len(seed61_rows),
        "seed61_frontier_allocation_miss_count": len(seed61_misses),
        "seed61_mcq_letter_gold_miss_count": len(gold_letter_rows),
        "seed61_mcq_letter_gold_miss_share_of_misses": (
            round(len(gold_letter_rows) / len(seed61_misses), 6) if seed61_misses else None
        ),
        "seed61_override_reason_counts": dict(override_reason_counts),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def build_summary(
    *,
    join_stats: dict[str, Any],
    all_rows: list[dict[str, Any]],
    drilldown_rows: list[dict[str, Any]],
    rule_evaluations: list[dict[str, Any]],
    source_to_seed: dict[str, int | None],
) -> dict[str, Any]:
    subtype_counts = Counter(row["frontier_miss_subtype"] for row in drilldown_rows)
    for subtype in SUBTYPES:
        subtype_counts.setdefault(subtype, 0)

    any_tree_signal_count = sum(1 for row in drilldown_rows if as_bool(row.get("any_tree_signal_for_gold")))
    hidden_tree_signal_count = sum(
        1
        for row in drilldown_rows
        if as_bool(row.get("any_tree_signal_for_gold")) and not as_bool(row.get("visible_candidate_correct"))
    )

    per_source_seed = []
    for source_id in sorted(source_to_seed):
        subset = [row for row in drilldown_rows if str(row.get("source_id")) == source_id]
        per_source_seed.append(
            {
                "source_id": source_id,
                "seed": source_to_seed[source_id],
                "frontier_allocation_miss_count": len(subset),
                "subtype_counts": dict(Counter(row["frontier_miss_subtype"] for row in subset)),
            }
        )

    top_rules = sorted(
        rule_evaluations,
        key=lambda item: (item["accuracy"], item["net_wins"], -item["losses_vs_canonical_fta"], item["rule_name"]),
        reverse=True,
    )[:10]

    return {
        "join_stats": join_stats,
        "row_count_all": len(all_rows),
        "frontier_allocation_miss_row_count": len(drilldown_rows),
        "any_tree_signal_for_gold_count": any_tree_signal_count,
        "hidden_tree_signal_without_visible_candidate_count": hidden_tree_signal_count,
        "subtype_counts": dict(subtype_counts),
        "per_source_seed": per_source_seed,
        "frontier_support_breakdown": support_bucket_breakdown(drilldown_rows),
        "candidate_pool_group_count_breakdown": candidate_pool_group_count_breakdown(drilldown_rows),
        "unanimity_vs_majority_safety": unanimity_vs_majority_safety(rule_evaluations),
        "seed61_regression_breakdown": seed61_regression_breakdown(all_rows, source_to_seed),
        "top_rule_candidates": [
            {
                "rule_name": item["rule_name"],
                "family": item["family"],
                "accuracy": item["accuracy"],
                "net_wins": item["net_wins"],
                "wins_vs_canonical_fta": item["wins_vs_canonical_fta"],
                "losses_vs_canonical_fta": item["losses_vs_canonical_fta"],
                "frontier_allocation_miss_wins": item["frontier_allocation_miss_wins"],
                "fta_success_regressions": item["fta_success_regressions"],
                "robust_under_leave_one_source_out": item["robust_under_leave_one_source_out"],
                "especially_fails_on_seed_61": item["especially_fails_on_seed_61"],
            }
            for item in top_rules
        ],
        "rule_candidate_count": len(rule_evaluations),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Frontier Allocation Miss Drilldown Report",
        "",
        "Offline diagnostic drilldown over `frontier_allocation_miss` rows. Exploratory only;",
        "does not change canonical FTA/FIX-2+FIX-4 selector logic or manuscript claims.",
        "",
        "## Join stats",
        "",
    ]
    for key, value in summary["join_stats"].items():
        if key == "missing_branch_rows":
            continue
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- rows (all classes, joined): {summary['row_count_all']}",
            f"- frontier_allocation_miss rows: {summary['frontier_allocation_miss_row_count']}",
            f"- any_tree_signal_for_gold: {summary['any_tree_signal_for_gold_count']}",
            (
                "- hidden_tree_signal_without_visible_candidate: "
                f"{summary['hidden_tree_signal_without_visible_candidate_count']}"
            ),
            "",
            "## Subtype counts",
            "",
        ]
    )
    for subtype in SUBTYPES:
        lines.append(f"- `{subtype}`: {summary['subtype_counts'].get(subtype, 0)}")
    lines.extend(["", "## Per source/seed", ""])
    for item in summary["per_source_seed"]:
        lines.append(
            f"- `{item['source_id']}` seed={item['seed']}: "
            f"frontier_allocation_miss={item['frontier_allocation_miss_count']}, "
            f"subtypes={item['subtype_counts']}"
        )
    lines.extend(["", "## frontier_support breakdown (research question 2)", ""])
    for item in summary["frontier_support_breakdown"]:
        lines.append(
            f"- `{item['bucket']}`: rows={item['row_count']}, "
            f"recoverable_via_external_signal={item['recoverable_via_external_signal_count']}, "
            f"recoverable_share_within_bucket={item['recoverable_share_within_bucket']}"
        )
    lines.extend(["", "## candidate_pool_answer_group_count breakdown (research question 3)", ""])
    for item in summary["candidate_pool_group_count_breakdown"]:
        lines.append(
            f"- `{item['bucket']}`: rows={item['row_count']}, "
            f"recoverable_via_external_signal={item['recoverable_via_external_signal_count']}, "
            f"recoverable_share_within_bucket={item['recoverable_share_within_bucket']}"
        )
    safety = summary["unanimity_vs_majority_safety"]
    lines.extend(
        [
            "",
            "## Unanimity vs 2-of-3 majority safety (research question 4)",
            "",
            f"- unanimity rules: n={safety['unanimity_rule_count']}, "
            f"avg_losses_vs_canonical_fta={safety['unanimity_avg_losses_vs_canonical_fta']}, "
            f"avg_net_wins={safety['unanimity_avg_net_wins']}",
            f"- majority rules: n={safety['majority_rule_count']}, "
            f"avg_losses_vs_canonical_fta={safety['majority_avg_losses_vs_canonical_fta']}, "
            f"avg_net_wins={safety['majority_avg_net_wins']}",
        ]
    )
    seed61 = summary["seed61_regression_breakdown"]
    lines.extend(
        [
            "",
            "## seed 61 breakdown (research question 5)",
            "",
            f"- source: `{seed61.get('seed61_source')}`",
            f"- rows: {seed61.get('seed61_row_count')}",
            f"- frontier_allocation_miss rows: {seed61.get('seed61_frontier_allocation_miss_count')}",
            (
                "- misses with MCQ-letter gold answer: "
                f"{seed61.get('seed61_mcq_letter_gold_miss_count')} "
                f"(share={seed61.get('seed61_mcq_letter_gold_miss_share_of_misses')})"
            ),
            f"- override_reason counts: {seed61.get('seed61_override_reason_counts')}",
            "",
            "## Top exploratory rule candidates",
            "",
        ]
    )
    for item in summary["top_rule_candidates"]:
        lines.append(
            f"- `{item['rule_name']}` ({item['family']}): accuracy={item['accuracy']:.4f}, "
            f"net_wins={item['net_wins']}, wins={item['wins_vs_canonical_fta']}, "
            f"losses={item['losses_vs_canonical_fta']}, "
            f"frontier_allocation_miss_wins={item['frontier_allocation_miss_wins']}, "
            f"fta_success_regressions={item['fta_success_regressions']}, "
            f"robust_under_loso={item['robust_under_leave_one_source_out']}, "
            f"especially_fails_on_seed_61={item['especially_fails_on_seed_61']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_representative_cases(drilldown_rows: list[dict[str, Any]], *, limit: int = 5) -> str:
    lines = ["# Representative frontier_allocation_miss Cases by Subtype", ""]
    by_subtype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in drilldown_rows:
        by_subtype[row["frontier_miss_subtype"]].append(row)
    for subtype in SUBTYPES:
        rows = by_subtype.get(subtype, [])
        lines.append(f"## {subtype} ({len(rows)})")
        lines.append("")
        if not rows:
            lines.append("_no cases_")
            lines.append("")
            continue
        for row in rows[:limit]:
            lines.append(
                f"- {row['example_id']} | {row['source_id']} | seed={row['seed']} | "
                f"gold={row['gold_answer_canonical']} | frontier={row['frontier_answer']} | "
                f"l1={row['l1_answer']} | s1={row['s1_answer']} | tale={row['tale_answer']} | "
                f"fta={row['fta_selected_answer']} | frontier_support={row['frontier_support']} | "
                f"cpc={row['candidate_pool_answer_group_count']} | override_reason={row['override_reason']} | "
                f"direct_frontier_agree={row['direct_frontier_agree']} | gold_in_tree={row['gold_in_tree']} | "
                f"gold_in_final_nodes={row['gold_in_final_nodes']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_rule_candidate_csv_rows(rule_evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    csv_rows = []
    for item in rule_evaluations:
        csv_rows.append(
            {
                "rule_name": item["rule_name"],
                "family": item["family"],
                "description": item["description"],
                "row_count": item["row_count"],
                "accuracy": item["accuracy"],
                "canonical_fta_accuracy": item["canonical_fta_accuracy"],
                "wins_vs_canonical_fta": item["wins_vs_canonical_fta"],
                "losses_vs_canonical_fta": item["losses_vs_canonical_fta"],
                "net_wins": item["net_wins"],
                "frontier_allocation_miss_wins": item["frontier_allocation_miss_wins"],
                "fta_success_regressions": item["fta_success_regressions"],
                "runtime_legal_fields_only": item["runtime_legal_fields_only"],
                "robust_under_leave_one_source_out": item["robust_under_leave_one_source_out"],
                "especially_fails_on_seed_61": item["especially_fails_on_seed_61"],
                "seed61_delta": item["seed61_delta"],
                "per_source_metrics": json.dumps(item["per_source_metrics"], sort_keys=True),
                "loso_folds": json.dumps(item["loso_folds"], sort_keys=True),
            }
        )
    return csv_rows


def run_drilldown(
    feature_table_path: Path,
    branch_diagnostics_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    feature_rows = load_feature_rows(feature_table_path)
    branch_rows = load_feature_rows(branch_diagnostics_path)
    all_rows, join_stats = join_rows(feature_rows, branch_rows)

    drilldown_rows = build_drilldown_table(all_rows)

    source_to_seed: dict[str, int | None] = {}
    for row in all_rows:
        source_to_seed[str(row.get("source_id"))] = as_int(row.get("seed"))

    specs = build_rule_specs()
    rule_evaluations = [
        evaluate_rule_with_diagnostics(all_rows, spec, source_to_seed=source_to_seed) for spec in specs
    ]

    summary = build_summary(
        join_stats=join_stats,
        all_rows=all_rows,
        drilldown_rows=drilldown_rows,
        rule_evaluations=rule_evaluations,
        source_to_seed=source_to_seed,
    )
    return all_rows, drilldown_rows, rule_evaluations, summary, join_stats


def main() -> int:
    args = parse_args()
    feature_table_path, branch_diagnostics_path = resolve_input_paths(args)

    all_rows, drilldown_rows, rule_evaluations, summary, _join_stats = run_drilldown(
        feature_table_path, branch_diagnostics_path
    )

    output_dir = Path(args.output_dir)
    write_csv(
        output_dir / "frontier_miss_drilldown_table.csv",
        [
            {
                key: (json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value)
                for key, value in row.items()
            }
            for row in drilldown_rows
        ],
        list(drilldown_rows[0].keys()) if drilldown_rows else ["row_id"],
    )
    write_jsonl(output_dir / "frontier_miss_drilldown_table.jsonl", drilldown_rows)
    write_json(output_dir / "frontier_miss_drilldown_summary.json", summary)
    write_text(output_dir / "frontier_miss_drilldown_report.md", render_report(summary))

    rule_csv_rows = build_rule_candidate_csv_rows(rule_evaluations)
    write_csv(
        output_dir / "recoverable_vs_risky_rule_candidates.csv",
        rule_csv_rows,
        list(rule_csv_rows[0].keys()) if rule_csv_rows else ["rule_name"],
    )
    write_text(
        output_dir / "representative_cases.md",
        render_representative_cases(drilldown_rows),
    )

    print(
        json.dumps(
            {
                "feature_table": str(feature_table_path),
                "branch_diagnostics": str(branch_diagnostics_path),
                "output_dir": str(output_dir),
                "frontier_allocation_miss_rows": len(drilldown_rows),
                "rule_candidates_evaluated": len(rule_evaluations),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
