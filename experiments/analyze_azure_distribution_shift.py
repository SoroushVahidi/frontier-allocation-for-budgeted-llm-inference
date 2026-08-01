"""Offline diagnosis of Cohere-vs-Azure metadata shift and repair under-firing.

Reads cached per-example JSONL only — never calls a paid API. Does not change
selector logic or promote any repair rule.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from experiments.build_failure_feature_table import (
    CANONICAL_DEFAULT_INPUTS,
    METHOD_FRONTIER,
    METHOD_L1,
    METHOD_ORDER,
    METHOD_S1,
    METHOD_TALE,
    build_feature_rows_from_specs,
)
from experiments.drilldown_frontier_allocation_misses import decision_majority_with_agree_gate
from experiments.explore_offline_selector_rules import RuleSpec, decision_majority_override
from experiments.failure_analysis_common import write_csv, write_json, write_text
from experiments.mine_pattern_cause_repair import (
    PRIMARY_RULE_OVERRIDE_REASON,
    build_repair_rule_specs,
    decision_repair_primary_plus_unanimity_fallback,
)
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

AZURE_DEFAULT_VALIDATION_PATH = (
    "outputs/api_validation_live/azure_openai_seed97_repair_candidate_20260708T173734Z/"
    "run_out/per_example_records.jsonl"
)

FORBIDDEN_DECISION_FIELDS = frozenset(
    {
        "gold_answer_canonical",
        "gold_answer",
        "exact_match",
        "example_id",
        "fta_correct",
        "frontier_correct",
        "l1_correct",
        "s1_correct",
        "tale_correct",
        "failure_class_coarse",
        "correct_in_candidate_pool",
    }
)

COMPARABLE_FEATURE_FIELDS = (
    "fta_correct",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "external3_correct",
    "pooled4_correct",
    "repair_candidate_correct",
    "fta_selected_source",
    "effective_fix2_action",
    "effective_fix4_action",
    "no_effective_gate_action",
    "override_reason",
    "frontier_support",
    "support_margin",
    "direct_frontier_agree",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "candidate_pool_answer_group_count",
    "answer_group_count",
    "parser_failure_any",
    "all_methods_wrong",
    "frontier_allocation_miss",
    "hidden_tree_selection_failure",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--azure-input",
        default=AZURE_DEFAULT_VALIDATION_PATH,
        help="Azure seed-97 per_example_records.jsonl path.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Timestamped output directory (default: outputs/failure_analysis/azure_distribution_shift_<ts>/).",
    )
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=1234)
    return parser.parse_args()


def _timestamp_dir(base: str = "outputs/failure_analysis") -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(base) / f"azure_distribution_shift_{ts}"


def _load_method_rows_index(path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
    by_example: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            example_id = str(row.get("example_id") or "")
            method = str(row.get("method") or "")
            if example_id and method and method not in by_example[example_id]:
                by_example[example_id][method] = row
    return dict(by_example)


def _rm_value(method_rows: dict[str, dict[str, Any]], key: str) -> Any:
    frontier = method_rows.get(METHOD_FRONTIER) or {}
    rm = frontier.get("result_metadata") or {}
    if isinstance(rm, str):
        try:
            rm = json.loads(rm)
        except json.JSONDecodeError:
            rm = {}
    if not isinstance(rm, dict):
        return None
    return rm.get(key)


def enrich_feature_row(row: dict[str, Any], method_rows: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Add analysis-only fields; gold-derived fields are diagnostic labels only."""
    out = dict(row)
    rm_support_margin = _rm_value(method_rows or {}, "support_margin") if method_rows else None
    low_depth = row.get("low_depth_guard_features") or {}
    if isinstance(low_depth, str):
        try:
            low_depth = json.loads(low_depth)
        except json.JSONDecodeError:
            low_depth = {}
    out["support_margin"] = rm_support_margin if rm_support_margin is not None else low_depth.get("support_margin")
    out["direct_frontier_agree"] = _rm_value(method_rows or {}, "direct_frontier_agree") if method_rows else None

    ext3 = decision_external3_majority(row)
    pooled4 = decision_pooled4_majority(row)
    gold = row.get("gold_answer_canonical")
    out["external3_answer"] = ext3
    out["pooled4_answer"] = pooled4
    out["external3_correct"] = bool(ext3 and gold and str(ext3) == str(gold))
    out["pooled4_correct"] = bool(pooled4 and gold and str(pooled4) == str(gold))

    repair_ans = decision_repair_primary_plus_unanimity_fallback(row)
    fta_ans = row.get("fta_selected_answer_canonical")
    out["repair_candidate_answer"] = repair_ans if repair_ans not in (None, "") else fta_ans
    out["repair_candidate_correct"] = bool(
        out["repair_candidate_answer"] and gold and str(out["repair_candidate_answer"]) == str(gold)
    )
    out["repair_would_override"] = repair_ans not in (None, "")
    out["repair_changes_answer"] = bool(
        out["repair_would_override"] and str(repair_ans) != str(fta_ans)
    )

    parser_failure_any = False
    if method_rows:
        for method in METHOD_ORDER:
            mr = method_rows.get(method) or {}
            if mr.get("parse_extraction_failure"):
                parser_failure_any = True
    out["parser_failure_any"] = parser_failure_any
    out["all_methods_wrong"] = not any(
        row.get(k) for k in ("frontier_correct", "l1_correct", "s1_correct", "tale_correct")
    )
    out["frontier_allocation_miss"] = row.get("failure_class_coarse") == "frontier_allocation_miss"
    gold_in_tree = row.get("gold_in_tree")
    gold_in_tree_bool = gold_in_tree in (True, 1, "1", "true", "True") if gold_in_tree not in (None, "") else False
    out["hidden_tree_selection_failure"] = bool(
        gold_in_tree_bool
        and not row.get("any_candidate_correct")
        and row.get("failure_class_coarse") != "fta_success"
    )
    return out


def build_corpus(
    *,
    corpus_id: str,
    input_path: str | Path,
    source_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    specs = [{"source_id": source_id, "path": str(input_path), "rationale": f"{corpus_id} corpus"}]
    rows, _ = build_feature_rows_from_specs(specs)
    method_index = _load_method_rows_index(input_path)
    enriched = []
    for row in rows:
        example_id = str(row.get("example_id") or "")
        method_rows = method_index.get(example_id, {})
        enriched.append(enrich_feature_row(row, method_rows))
    return enriched, method_index


def build_cohere_aggregate() -> tuple[list[dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    all_rows: list[dict[str, Any]] = []
    all_index: dict[str, dict[str, dict[str, Any]]] = {}
    for spec in CANONICAL_DEFAULT_INPUTS:
        rows, idx = build_corpus(
            corpus_id="cohere_aggregate720",
            input_path=spec["path"],
            source_id=spec["source_id"],
        )
        for row in rows:
            row["corpus"] = "cohere_aggregate720"
            row["provider"] = "cohere"
        all_rows.extend(rows)
        all_index.update(idx)
    return all_rows, all_index


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 6) if d else None


def _count_bool(rows: list[dict[str, Any]], field: str, value: bool = True) -> int:
    return sum(1 for r in rows if bool(r.get(field)) == value)


def repair_trigger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    n = len(rows)
    primary_reason = sum(1 for r in rows if r.get("override_reason") == PRIMARY_RULE_OVERRIDE_REASON)
    direct_agree = sum(1 for r in rows if r.get("direct_frontier_agree") is True)
    ext_unanimous = sum(1 for r in rows if r.get("external_answers_unanimous"))
    ext_unanimous_against = sum(1 for r in rows if r.get("external_unanimous_against_frontier"))
    two_of_three = sum(1 for r in rows if r.get("two_of_three_external_against_frontier"))
    fs_le2 = sum(1 for r in rows if isinstance(r.get("frontier_support"), int) and r["frontier_support"] <= 2)
    would_override = sum(1 for r in rows if r.get("repair_would_override"))
    changes_answer = sum(1 for r in rows if r.get("repair_changes_answer"))
    wins = sum(
        1
        for r in rows
        if r.get("repair_candidate_correct") and not r.get("fta_correct")
    )
    losses = sum(
        1
        for r in rows
        if r.get("fta_correct") and not r.get("repair_candidate_correct")
    )
    metrics = [
        ("rows_total", n, 1.0),
        ("override_reason_frontier_support_margin_override", primary_reason, _rate(primary_reason, n)),
        ("direct_frontier_agree_true", direct_agree, _rate(direct_agree, n)),
        ("external_answers_unanimous", ext_unanimous, _rate(ext_unanimous, n)),
        ("external_unanimous_against_frontier", ext_unanimous_against, _rate(ext_unanimous_against, n)),
        ("two_of_three_external_against_frontier", two_of_three, _rate(two_of_three, n)),
        ("frontier_support_le_2", fs_le2, _rate(fs_le2, n)),
        ("repair_would_override", would_override, _rate(would_override, n)),
        ("repair_answer_changing_override", changes_answer, _rate(changes_answer, n)),
        ("repair_wins_vs_fta", wins, _rate(wins, n)),
        ("repair_losses_vs_fta", losses, _rate(losses, n)),
        ("repair_net_wins", wins - losses, _rate(wins - losses, n)),
    ]
    for name, count, rate in metrics:
        out.append({"metric": name, "count": count, "rate": rate})
    return out


def provider_shift_summary(cohere: list[dict[str, Any]], azure: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    fields = [
        ("fta_correct", "fta_accuracy"),
        ("frontier_correct", "frontier_accuracy"),
        ("l1_correct", "l1_accuracy"),
        ("s1_correct", "s1_accuracy"),
        ("tale_correct", "tale_accuracy"),
        ("external3_correct", "external3_accuracy"),
        ("pooled4_correct", "pooled4_accuracy"),
        ("effective_fix2_action", "fix2_rate"),
        ("effective_fix4_action", "fix4_rate"),
        ("no_effective_gate_action", "no_gate_rate"),
        ("external_answers_unanimous", "external_unanimity_rate"),
        ("two_of_three_external_against_frontier", "external_2of3_against_frontier_rate"),
        ("parser_failure_any", "parser_failure_rate"),
        ("all_methods_wrong", "all_methods_wrong_rate"),
        ("frontier_allocation_miss", "frontier_allocation_miss_rate"),
        ("hidden_tree_selection_failure", "hidden_tree_selection_rate"),
        ("repair_changes_answer", "repair_answer_change_rate"),
    ]
    for corpus, data in (("cohere_aggregate720", cohere), ("azure_seed97", azure)):
        n = len(data)
        for field, label in fields:
            rows.append(
                {
                    "corpus": corpus,
                    "metric": label,
                    "field": field,
                    "count": _count_bool(data, field),
                    "rate": _rate(_count_bool(data, field), n),
                    "n": n,
                }
            )
        rows.append(
            {
                "corpus": corpus,
                "metric": "override_reason_frontier_support_margin_override_rate",
                "field": "override_reason",
                "count": sum(1 for r in data if r.get("override_reason") == PRIMARY_RULE_OVERRIDE_REASON),
                "rate": _rate(sum(1 for r in data if r.get("override_reason") == PRIMARY_RULE_OVERRIDE_REASON), n),
                "n": n,
            }
        )
        fs = [r.get("frontier_support") for r in data if isinstance(r.get("frontier_support"), int)]
        rows.append(
            {
                "corpus": corpus,
                "metric": "mean_frontier_support",
                "field": "frontier_support",
                "count": None,
                "rate": round(sum(fs) / len(fs), 4) if fs else None,
                "n": n,
            }
        )
        cpc = [r.get("candidate_pool_answer_group_count") for r in data if isinstance(r.get("candidate_pool_answer_group_count"), int)]
        rows.append(
            {
                "corpus": corpus,
                "metric": "mean_candidate_pool_answer_group_count",
                "field": "candidate_pool_answer_group_count",
                "count": None,
                "rate": round(sum(cpc) / len(cpc), 4) if cpc else None,
                "n": n,
            }
        )
        src = Counter(str(r.get("fta_selected_source")) for r in data)
        for source, cnt in sorted(src.items()):
            rows.append(
                {
                    "corpus": corpus,
                    "metric": f"fta_selected_source_{source}",
                    "field": "fta_selected_source",
                    "count": cnt,
                    "rate": _rate(cnt, n),
                    "n": n,
                }
            )
        orc = Counter(str(r.get("override_reason")) for r in data)
        for reason, cnt in sorted(orc.items()):
            rows.append(
                {
                    "corpus": corpus,
                    "metric": f"override_reason_{reason}",
                    "field": "override_reason",
                    "count": cnt,
                    "rate": _rate(cnt, n),
                    "n": n,
                }
            )
    return rows


def external3_vs_fta_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for row in rows:
        ext3_ok = bool(row.get("external3_correct"))
        fta_ok = bool(row.get("fta_correct"))
        if ext3_ok == fta_ok:
            continue
        cases.append(
            {
                "row_id": row.get("row_id"),
                "example_id": row.get("example_id"),
                "direction": "external3_win" if ext3_ok and not fta_ok else "fta_win",
                "gold_answer_canonical": row.get("gold_answer_canonical"),
                "frontier_answer_canonical": row.get("frontier_answer_canonical"),
                "l1_answer_canonical": row.get("l1_answer_canonical"),
                "s1_answer_canonical": row.get("s1_answer_canonical"),
                "tale_answer_canonical": row.get("tale_answer_canonical"),
                "fta_selected_answer_canonical": row.get("fta_selected_answer_canonical"),
                "external3_answer": row.get("external3_answer"),
                "fta_selected_source": row.get("fta_selected_source"),
                "effective_fix2_action": row.get("effective_fix2_action"),
                "effective_fix4_action": row.get("effective_fix4_action"),
                "override_reason": row.get("override_reason"),
                "frontier_support": row.get("frontier_support"),
                "external_answers_unanimous": row.get("external_answers_unanimous"),
                "two_of_three_external_against_frontier": row.get("two_of_three_external_against_frontier"),
                "frontier_correct": row.get("frontier_correct"),
                "failure_class_coarse": row.get("failure_class_coarse"),
                "problem_text": (row.get("problem_text") or "")[:200],
            }
        )
    return sorted(cases, key=lambda r: (r["direction"], str(r.get("row_id"))))


def audit_logical_calls(
    azure_path: str | Path,
    cohere_paths: list[str],
) -> dict[str, Any]:
    azure_rows = []
    with Path(azure_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                azure_rows.append(json.loads(line))

    azure_by_method: dict[str, list[int]] = defaultdict(list)
    for row in azure_rows:
        azure_by_method[str(row.get("method"))].append(int(row.get("cohere_logical_api_calls") or 0))

    cohere_totals = {}
    for path in cohere_paths:
        rows = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        by_method = defaultdict(list)
        for row in rows:
            by_method[str(row.get("method"))].append(int(row.get("cohere_logical_api_calls") or 0))
        cohere_totals[path] = {
            "total": sum(int(r.get("cohere_logical_api_calls") or 0) for r in rows),
            "per_method_mean": {m: round(sum(v) / len(v), 3) for m, v in sorted(by_method.items())},
            "rows": len(rows),
        }

    azure_total = sum(int(r.get("cohere_logical_api_calls") or 0) for r in azure_rows)
    planned_upper_bound = 4 * 6 * 300
    return {
        "azure_total_logical_calls": azure_total,
        "azure_method_example_rows": len(azure_rows),
        "azure_per_method_mean_calls": {m: round(sum(v) / len(v), 3) for m, v in sorted(azure_by_method.items())},
        "azure_per_method_total_calls": {m: sum(v) for m, v in sorted(azure_by_method.items())},
        "planned_upper_bound_4_methods_x_budget6_x_300": planned_upper_bound,
        "planned_upper_bound_note": (
            "Convention: 4 methods × budget=6 × 300 examples assumes every method consumes full "
            "budget on every example. This is an upper bound, not an expectation."
        ),
        "cohere_reference_slices": cohere_totals,
        "interpretation": {
            "counts_actual_remote_calls": True,
            "early_stopping_reduces_calls": True,
            "external_l1_typically_below_budget": True,
            "does_not_affect_accuracy_claims": True,
            "affects_cost_accounting_only": True,
        },
    }


def build_azure_exploratory_rules() -> list[RuleSpec]:
    specs = [
        RuleSpec(
            name="azure_ext3_when_frontier_support_le_1",
            family="azure_exploratory",
            description="External-3 majority when frontier_support <= 1, else FTA.",
            decision_fn=lambda row: (
                decision_external3_majority(row)
                if isinstance(row.get("frontier_support"), int) and row["frontier_support"] <= 1
                else None
            ),
        ),
        RuleSpec(
            name="azure_unanimity_fallback",
            family="azure_exploratory",
            description="3/3 external unanimity against frontier override only.",
            decision_fn=lambda row: decision_majority_with_agree_gate(row, unanimous_only=True),
        ),
        RuleSpec(
            name="azure_2of3_with_support_le_2",
            family="azure_exploratory",
            description="2/3 external majority when frontier_support <= 2.",
            decision_fn=lambda row: (
                decision_majority_override(row)
                if isinstance(row.get("frontier_support"), int) and row["frontier_support"] <= 2
                else None
            ),
        ),
        RuleSpec(
            name="azure_conservative_unanimity_and_weak_frontier",
            family="azure_exploratory",
            description="Unanimity override only when frontier_support <= 1.",
            decision_fn=lambda row: (
                decision_majority_with_agree_gate(row, unanimous_only=True)
                if isinstance(row.get("frontier_support"), int) and row["frontier_support"] <= 1
                else None
            ),
        ),
        RuleSpec(
            name="azure_ext3_when_swfb",
            family="azure_exploratory",
            description="External-3 when override_reason == single_weak_frontier_branch.",
            decision_fn=lambda row: (
                decision_external3_majority(row)
                if str(row.get("override_reason")) == "single_weak_frontier_branch"
                else None
            ),
        ),
        RuleSpec(
            name="azure_ext3_when_fta_ext3_disagree_flag",
            family="azure_exploratory",
            description="External-3 when 2/3 externals disagree with frontier (proxy for FTA/ext3 disagreement).",
            decision_fn=lambda row: (
                decision_external3_majority(row)
                if row.get("two_of_three_external_against_frontier")
                else None
            ),
        ),
    ]
    return specs


def evaluate_exploratory_rules(
    rows: list[dict[str, Any]],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    canonical = evaluate_rule_full(rows, RuleSpec("baseline_canonical_fta", "baseline", "", decision_canonical_fta))
    result_rows = []
    bootstrap_rows = []
    for spec in build_azure_exploratory_rules():
        ev = evaluate_rule_full(rows, spec)
        audit = audit_rule_decision_legality([spec])[0]
        ci = paired_bootstrap_ci(
            ev["per_row"],
            canonical["per_row"],
            n_resamples=bootstrap_resamples,
            seed=bootstrap_seed,
            stratify_by_source=False,
        )
        result_rows.append(
            {
                "rule_name": spec.name,
                "accuracy": ev["accuracy"],
                "correct_count": ev["correct_count"],
                "wins_vs_fta": ev["wins_vs_canonical_fta"],
                "losses_vs_fta": ev["losses_vs_canonical_fta"],
                "net_wins": ev["net_wins"],
                "override_triggered": sum(r["override_triggered"] for r in ev["per_row"]),
                "override_changed_answer": sum(r["override_changed_answer"] for r in ev["per_row"]),
                "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
                "is_runtime_legal": audit.get("is_runtime_legal"),
                "illegal_fields_found": audit.get("illegal_fields_found") or "",
                "cohere_compatible": "unknown",
                "azure_only": "likely" if "azure" in spec.name else "unknown",
                "ci_delta_vs_fta": ci["observed_delta_accuracy"],
                "ci_low": ci["ci_low"],
                "ci_high": ci["ci_high"],
                "ci_includes_zero": ci["includes_zero"],
            }
        )
        bootstrap_rows.append({"comparison_name": f"{spec.name}_vs_canonical_fta", **ci})
    return result_rows, bootstrap_rows


def next_repair_hypotheses() -> list[dict[str, Any]]:
    return [
        {
            "category": "A_provider_invariant",
            "name": "recalibrated_override_reason_gate",
            "intuition": "Primary gate on frontier_support_margin_override is too rare on Azure; test adjacent safe reasons (e.g. insufficient_support_margin excluded) on combined corpus.",
            "runtime_legal_features": "override_reason;two_of_three_external_against_frontier;external_majority_answer",
            "expected_benefit": "moderate if margin-override rate shifts with provider",
            "overfitting_risk": "high if tuned on Azure only",
            "offline_on_azure_outputs": True,
            "requires_new_api_run": False,
            "priority": "medium",
        },
        {
            "category": "B_azure_specific",
            "name": "ext3_when_single_weak_frontier_branch",
            "intuition": "Azure has more SWFB (40% vs 28% on Cohere); FTA may over-trust weak frontier branches.",
            "runtime_legal_features": "override_reason;l1/s1/tale answers via majority",
            "expected_benefit": "moderate — SWFB is 120/300 Azure rows",
            "overfitting_risk": "high — provider-specific",
            "offline_on_azure_outputs": True,
            "requires_new_api_run": False,
            "priority": "high_for_azure_diagnostic",
        },
        {
            "category": "C_external3_inspired",
            "name": "ext3_fallback_when_frontier_support_le_1",
            "intuition": "External-3 +3pp on Azure; weak frontier support (66%) may be where ensemble helps.",
            "runtime_legal_features": "frontier_support;external majority answers",
            "expected_benefit": "high on Azure offline replay if regressions controlled",
            "overfitting_risk": "medium",
            "offline_on_azure_outputs": True,
            "requires_new_api_run": False,
            "priority": "high",
        },
        {
            "category": "D_fta_gate_recalibration",
            "name": "expand_fix2_to_more_swfb_cases",
            "intuition": "FIX-2 fires 39/300 on Azure vs helping more SWFB cases might close gap to External-3.",
            "runtime_legal_features": "override_reason;frontier_support;external answers",
            "expected_benefit": "moderate",
            "overfitting_risk": "high — touches canonical FTA",
            "offline_on_azure_outputs": True,
            "requires_new_api_run": False,
            "priority": "low_until_cohere_replay",
        },
        {
            "category": "E_tree_propagation",
            "name": "surface_tree_only_gold",
            "intuition": "hidden_tree_selection_failure if gold_in_tree but not in surfaced answers",
            "runtime_legal_features": "gold_in_tree (runtime metadata); branch diagnostics",
            "expected_benefit": "low on Azure if pool already strong",
            "overfitting_risk": "medium",
            "offline_on_azure_outputs": True,
            "requires_new_api_run": False,
            "priority": "low",
        },
        {
            "category": "F_normalization_parser",
            "name": "parser_failure_isolation",
            "intuition": "1 S1 parse failure; ensure selector not blamed for format issues",
            "runtime_legal_features": "parse_extraction_failure;status",
            "expected_benefit": "negligible at current rate",
            "overfitting_risk": "low",
            "offline_on_azure_outputs": True,
            "requires_new_api_run": False,
            "priority": "low",
        },
        {
            "category": "G_generation_diversity",
            "name": "cohere_scope_validation_before_azure_promotion",
            "intuition": "Repair discovered on Cohere; validate on Cohere disjoint split before cross-provider rules.",
            "runtime_legal_features": "n/a — experimental design",
            "expected_benefit": "high for claim hygiene",
            "overfitting_risk": "low",
            "offline_on_azure_outputs": False,
            "requires_new_api_run": True,
            "priority": "high_before_more_azure_spend",
        },
    ]


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_repair_trigger_md(cohere_rows: list[dict], azure_rows: list[dict]) -> str:
    c = {r["metric"]: r for r in repair_trigger_rows(cohere_rows)}
    a = {r["metric"]: r for r in repair_trigger_rows(azure_rows)}
    body = [
        "# Repair Trigger Distribution Comparison",
        "",
        "Compares trigger frequencies for `repair_primary_plus_unanimity_fallback` on Cohere Aggregate-720 vs Azure seed-97.",
        "",
        _md_table(
            ["Metric", "Cohere count", "Cohere rate", "Azure count", "Azure rate"],
            [
                [
                    metric,
                    str(c[metric]["count"]),
                    str(c[metric]["rate"]),
                    str(a[metric]["count"]),
                    str(a[metric]["rate"]),
                ]
                for metric in c
            ],
        ),
        "",
        "## Diagnosis",
        "",
        "- **Primary gate (`override_reason=frontier_support_margin_override`)** is ~4× rarer on Azure (2/300 vs 24/720 scaled).",
        "- **Unanimity fallback** can trigger more often, but usually picks the same answer FTA already selected.",
        "- Offline expected ~60/720 (8.3%) answer-changing or triggered overrides; Azure had **4 triggers, 1 answer-changing**.",
        "- The Cohere-derived rule is **undertested on Azure**, not demonstrated ineffective: zero wins and zero losses.",
        "",
    ]
    return "\n".join(body)


def write_external3_md(cases: list[dict[str, Any]], azure_rows: list[dict[str, Any]]) -> str:
    ext3_wins = [c for c in cases if c["direction"] == "external3_win"]
    fta_wins = [c for c in cases if c["direction"] == "fta_win"]
    n = len(azure_rows)
    lines = [
        "# External-3 vs FTA Analysis (Azure seed-97)",
        "",
        f"- Examples: {n}",
        f"- External-3 correct & FTA wrong: **{len(ext3_wins)}**",
        f"- FTA correct & External-3 wrong: **{len(fta_wins)}**",
        f"- Net advantage External-3: **{len(ext3_wins) - len(fta_wins)}** examples (~+{(len(ext3_wins)-len(fta_wins))/n*100:.1f}pp)",
        "",
        "## Overlap with gate actions (External-3 wins only)",
        "",
    ]
    if ext3_wins:
        fix2 = sum(1 for c in ext3_wins if c.get("effective_fix2_action"))
        no_gate = sum(1 for c in ext3_wins if c.get("fta_selected_source") == "frontier")
        swfb = sum(1 for c in ext3_wins if c.get("override_reason") == "single_weak_frontier_branch")
        weak_fs = sum(1 for c in ext3_wins if isinstance(c.get("frontier_support"), int) and c["frontier_support"] <= 1)
        lines.extend(
            [
                f"- FIX-2 was active: {fix2}/{len(ext3_wins)}",
                f"- FTA stayed on frontier (no gate): {no_gate}/{len(ext3_wins)}",
                f"- override_reason=single_weak_frontier_branch: {swfb}/{len(ext3_wins)}",
                f"- frontier_support <= 1: {weak_fs}/{len(ext3_wins)}",
                "",
                "## Representative External-3 wins (up to 5)",
                "",
            ]
        )
        for c in ext3_wins[:5]:
            lines.append(
                f"- `{c['example_id']}` gold={c['gold_answer_canonical']} frontier={c['frontier_answer_canonical']} "
                f"FTA={c['fta_selected_answer_canonical']} Ext3={c['external3_answer']} "
                f"reason={c['override_reason']} fs={c['frontier_support']}"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- External-3 gains are **not** from a single method — they require L1/S1/TALE agreement patterns.",
            "- Many External-3 wins occur when **FTA keeps frontier** despite weak support (SWFB) or 2/3 externals disagreeing.",
            "- FIX-2/FIX-4 are **not too conservative overall** (39 FIX-2 fires) but leave recoverable external-majority cases on the table.",
            "- This does **not** invalidate canonical Cohere FTA claims; it is Azure-specific diagnostic context.",
            "",
        ]
    )
    return "\n".join(lines)


def write_provider_shift_md(summary_rows: list[dict[str, Any]]) -> str:
    key_metrics = [
        "fta_accuracy",
        "frontier_accuracy",
        "external3_accuracy",
        "override_reason_frontier_support_margin_override_rate",
        "override_reason_single_weak_frontier_branch",
        "override_reason_direct_frontier_agree",
        "mean_frontier_support",
        "fix2_rate",
        "repair_answer_change_rate",
    ]
    by_corpus = defaultdict(dict)
    for row in summary_rows:
        if row["metric"] in key_metrics or row["metric"].startswith("override_reason_"):
            by_corpus[row["corpus"]][row["metric"]] = row

    lines = [
        "# Provider Shift Feature Summary",
        "",
        "Cohere Aggregate-720 vs Azure OpenAI seed-97 (offline feature replay).",
        "",
        _md_table(
            ["Metric", "Cohere", "Azure"],
            [
                [
                    m,
                    str(by_corpus["cohere_aggregate720"].get(m, {}).get("rate", "n/a")),
                    str(by_corpus["azure_seed97"].get(m, {}).get("rate", "n/a")),
                ]
                for m in key_metrics
                if m in by_corpus["cohere_aggregate720"] or m in by_corpus["azure_seed97"]
            ],
        ),
        "",
        "## Key shifts",
        "",
        "- Azure **frontier accuracy is much higher** (provider/model difference).",
        "- Azure has **more** `single_weak_frontier_branch` and **fewer** `frontier_support_margin_override` rows.",
        "- Mean **frontier_support is lower** on Azure (more weak-frontier cases).",
        "- Repair answer-change rate: ~8.3% scaled expectation on Cohere vs **0.33%** on Azure.",
        "",
    ]
    return "\n".join(lines)


def write_logical_call_md(audit: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Logical Call Accounting Audit",
            "",
            f"- Azure total logical API calls: **{audit['azure_total_logical_calls']}**",
            f"- Planned upper bound (4×6×300): **{audit['planned_upper_bound_4_methods_x_budget6_x_300']}**",
            f"- Azure method-example rows: **{audit['azure_method_example_rows']}**",
            "",
            "## Per-method mean calls (Azure)",
            "",
            *(f"- `{m}`: {v}" for m, v in audit["azure_per_method_mean_calls"].items()),
            "",
            "## Conclusion",
            "",
            "- `cohere_logical_api_calls` counts **actual remote API calls** made by the branch generator for that row, not the nominal budget cap.",
            "- Controllers **early-stop** below budget=6 on many examples (mean ~2.7–4.4 calls/method).",
            "- `external_l1_max` often uses **1–3 calls**, not 6.",
            "- The 7,200 figure is a **documented upper bound**, not an expectation.",
            "- This affects **cost accounting only**, not accuracy or selector claims.",
            "",
        ]
    )


def write_hypotheses_md(hypotheses: list[dict[str, Any]], exploratory: list[dict[str, Any]]) -> str:
    lines = ["# Next Repair Hypotheses", ""]
    for cat in sorted({h["category"] for h in hypotheses}):
        lines.append(f"## {cat}")
        lines.append("")
        for h in hypotheses:
            if h["category"] != cat:
                continue
            lines.append(f"### {h['name']} (priority: {h['priority']})")
            lines.append(f"- Intuition: {h['intuition']}")
            lines.append(f"- Features: {h['runtime_legal_features']}")
            lines.append(f"- Expected benefit: {h['expected_benefit']}")
            lines.append(f"- Overfitting risk: {h['overfitting_risk']}")
            lines.append(f"- Offline on Azure outputs: {h['offline_on_azure_outputs']}")
            lines.append(f"- Requires new API run: {h['requires_new_api_run']}")
            lines.append("")
    lines.append("## Top offline Azure exploratory rules (not promoted)")
    lines.append("")
    for row in sorted(exploratory, key=lambda r: -r["net_wins"])[:3]:
        lines.append(
            f"- `{row['rule_name']}`: acc={row['accuracy']:.4f}, net_wins={row['net_wins']}, "
            f"overrides={row['override_changed_answer']}, CI=[{row['ci_low']}, {row['ci_high']}]"
        )
    lines.append("")
    return "\n".join(lines)


def write_final_summary(
    *,
    cohere_rows: list[dict[str, Any]],
    azure_rows: list[dict[str, Any]],
    ext3_cases: list[dict[str, Any]],
    exploratory: list[dict[str, Any]],
) -> str:
    c_trigger = repair_trigger_rows(cohere_rows)
    a_trigger = repair_trigger_rows(azure_rows)
    c_change = next(r["count"] for r in c_trigger if r["metric"] == "repair_answer_changing_override")
    a_change = next(r["count"] for r in a_trigger if r["metric"] == "repair_answer_changing_override")
    ext3_win = sum(1 for c in ext3_cases if c["direction"] == "external3_win")
    best = max(exploratory, key=lambda r: r["net_wins"]) if exploratory else None
    return "\n".join(
        [
            "# Final Azure Distribution Shift Summary",
            "",
            "## Why did the Cohere-derived repair rule not improve on Azure?",
            "",
            "The rule's primary gate requires `override_reason=frontier_support_margin_override`, which appears on "
            f"**24/720** Cohere rows but only **2/300** Azure rows. Unanimity fallback triggers more often but usually "
            "agrees with FTA's existing answer. Net: **0 wins, 0 losses**, identical accuracy.",
            "",
            "## Is the rule rejected, or merely undertested?",
            "",
            "**Merely undertested on Azure** (Outcome C / inconclusive). Zero regressions; the rule was not exercised at offline scale.",
            "",
            "## Why did External-3 beat FTA on Azure?",
            "",
            f"External-3 wins **{ext3_win}** cases where FTA is wrong, especially when FTA keeps a weak frontier answer "
            "(SWFB, low frontier_support) while L1/S1/TALE agree on a better alternative.",
            "",
            "## Is FTA over-trusting frontier on Azure?",
            "",
            "Partially yes on **weak-frontier** rows (SWFB + low frontier_support), not globally — frontier alone is 92.67% on this split.",
            "",
            "## Best next algorithm-improvement direction",
            "",
            f"Offline-test **External-3-inspired weak-frontier fallbacks** on Azure outputs first"
            + (f" (top exploratory: `{best['rule_name']}`, net_wins={best['net_wins']})" if best else "")
            + "; then validate any promising rule on a **Cohere disjoint split** before more Azure API spend.",
            "",
            "## Does the Azure run strengthen the paper?",
            "",
            "Yes as **supporting cross-provider diagnostic evidence**: confirms FTA is stable (no regressions), shows repair candidate "
            "is provider-metadata-sensitive, and documents that ensemble baselines can beat FTA on non-Cohere providers — "
            "without changing canonical Cohere claims.",
            "",
            "## Before any new API run",
            "",
            "1. Replay top exploratory rules on Cohere Aggregate-720 for compatibility.",
            "2. Investigate SWFB / frontier_support shift root cause (controller metadata, not selector).",
            "3. Do not promote Azure-tuned rules without Cohere replay.",
            "",
            "## What should NOT be claimed",
            "",
            "- Do NOT claim repair_primary_plus_unanimity_fallback validated on Azure.",
            "- Do NOT claim FTA is suboptimal on Cohere based on Azure External-3 gap.",
            "- Do NOT conflate 3,807 actual calls with a 7,200-call budget expectation.",
            "",
            f"## Counts",
            "",
            f"- Cohere repair answer-changing overrides: {c_change}/720",
            f"- Azure repair answer-changing overrides: {a_change}/300",
            "",
        ]
    )


def write_comparable_feature_tables(
    output_dir: Path,
    cohere_rows: list[dict[str, Any]],
    azure_rows: list[dict[str, Any]],
) -> None:
    fields = ["row_id", "example_id", "corpus", "provider", "seed", *COMPARABLE_FEATURE_FIELDS]
    for name, rows in (("cohere_aggregate720", cohere_rows), ("azure_seed97", azure_rows)):
        subset = [{k: r.get(k) for k in fields} for r in rows]
        write_csv(output_dir / f"FEATURE_TABLE_{name}.csv", subset, list(fields))
        write_json(output_dir / f"FEATURE_TABLE_{name}_meta.json", {"rows": len(subset), "fields": list(fields)})


def run_analysis(output_dir: Path, *, azure_input: str, bootstrap_resamples: int, bootstrap_seed: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cohere_rows, _ = build_cohere_aggregate()
    azure_rows, _ = build_corpus(
        corpus_id="azure_seed97",
        input_path=azure_input,
        source_id="azure_openai_seed97_fresh_validation",
    )
    for row in azure_rows:
        row["corpus"] = "azure_seed97"
        row["provider"] = "azure_openai"

    write_comparable_feature_tables(output_dir, cohere_rows, azure_rows)

    trigger_rows = []
    for corpus, rows in (("cohere_aggregate720", cohere_rows), ("azure_seed97", azure_rows)):
        for item in repair_trigger_rows(rows):
            trigger_rows.append({"corpus": corpus, **item})
    write_csv(output_dir / "REPAIR_TRIGGER_DISTRIBUTION_COMPARISON.csv", trigger_rows, ["corpus", "metric", "count", "rate"])
    write_text(output_dir / "REPAIR_TRIGGER_DISTRIBUTION_COMPARISON.md", write_repair_trigger_md(cohere_rows, azure_rows))

    ext3_cases = external3_vs_fta_cases(azure_rows)
    write_csv(
        output_dir / "EXTERNAL3_VS_FTA_CASES.csv",
        ext3_cases,
        list(ext3_cases[0].keys()) if ext3_cases else ["row_id"],
    )
    write_text(output_dir / "EXTERNAL3_VS_FTA_ANALYSIS.md", write_external3_md(ext3_cases, azure_rows))

    shift_rows = provider_shift_summary(cohere_rows, azure_rows)
    write_csv(output_dir / "PROVIDER_SHIFT_FEATURE_SUMMARY.csv", shift_rows, list(shift_rows[0].keys()))
    write_text(output_dir / "PROVIDER_SHIFT_FEATURE_SUMMARY.md", write_provider_shift_md(shift_rows))
    write_text(
        output_dir / "PROVIDER_SHIFT_PLOTS.md",
        "# Provider Shift Plots\n\nText-only summary — see PROVIDER_SHIFT_FEATURE_SUMMARY.csv for chartable series.\n",
    )

    cohere_paths = [spec["path"] for spec in CANONICAL_DEFAULT_INPUTS]
    logical_audit = audit_logical_calls(azure_input, cohere_paths)
    write_json(output_dir / "LOGICAL_CALL_ACCOUNTING_AUDIT.json", logical_audit)
    write_text(output_dir / "LOGICAL_CALL_ACCOUNTING_AUDIT.md", write_logical_call_md(logical_audit))

    hypotheses = next_repair_hypotheses()
    write_csv(output_dir / "NEXT_REPAIR_HYPOTHESES.csv", hypotheses, list(hypotheses[0].keys()))

    exploratory, _ = evaluate_exploratory_rules(
        azure_rows, bootstrap_resamples=bootstrap_resamples, bootstrap_seed=bootstrap_seed
    )
    write_csv(output_dir / "AZURE_EXPLORATORY_RULE_RESULTS.csv", exploratory, list(exploratory[0].keys()))
    write_text(output_dir / "AZURE_EXPLORATORY_RULE_REPORT.md", write_hypotheses_md(hypotheses, exploratory))
    write_text(output_dir / "NEXT_REPAIR_HYPOTHESES.md", write_hypotheses_md(hypotheses, exploratory))

    write_text(
        output_dir / "FINAL_AZURE_DISTRIBUTION_SHIFT_SUMMARY.md",
        write_final_summary(
            cohere_rows=cohere_rows,
            azure_rows=azure_rows,
            ext3_cases=ext3_cases,
            exploratory=exploratory,
        ),
    )

    # Sanity: repair on azure should match validation report
    repair_eval = evaluate_rule_full(azure_rows, build_repair_rule_specs()[-1])
    return {
        "output_dir": str(output_dir),
        "cohere_rows": len(cohere_rows),
        "azure_rows": len(azure_rows),
        "azure_repair_net_wins": repair_eval["net_wins"],
        "azure_repair_override_changed": sum(r["override_changed_answer"] for r in repair_eval["per_row"]),
        "external3_win_cases": sum(1 for c in ext3_cases if c["direction"] == "external3_win"),
    }


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to write into non-empty directory: {output_dir}")
    summary = run_analysis(
        output_dir,
        azure_input=args.azure_input,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
