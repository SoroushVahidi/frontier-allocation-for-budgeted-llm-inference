"""Strictly offline exploratory rule search over runtime-legal FTA diagnostics."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from experiments.build_failure_feature_table import normalize_answer
from experiments.failure_analysis_common import as_bool, as_int, load_feature_rows, write_csv, write_json, write_text


@dataclass(frozen=True)
class RuleSpec:
    name: str
    family: str
    description: str
    decision_fn: Callable[[dict[str, Any]], str | None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="outputs/failure_analysis/failure_feature_table.jsonl",
        help="Failure feature table JSONL.",
    )
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    return parser.parse_args()


def _canonical_accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(as_bool(row.get("fta_correct")) for row in rows) / len(rows)


def _candidate_correct(row: dict[str, Any], answer: str | None) -> bool:
    gold = row.get("gold_answer_canonical")
    if answer in (None, "") or gold in (None, ""):
        return False
    return str(answer) == str(gold)


def _preferred_external(row: dict[str, Any], order: tuple[str, ...]) -> str | None:
    for field in order:
        answer = normalize_answer(row.get(field))
        if answer:
            return answer
    return None


def decision_majority_override(
    row: dict[str, Any],
    *,
    unanimous_only: bool = False,
    max_frontier_support: int | None = None,
    min_cpc: int | None = None,
    require_override_reason: str | None = None,
) -> str | None:
    if require_override_reason and str(row.get("override_reason")) != require_override_reason:
        return None
    if unanimous_only:
        if not as_bool(row.get("external_unanimous_against_frontier")):
            return None
    else:
        if not as_bool(row.get("two_of_three_external_against_frontier")):
            return None
    frontier_support = as_int(row.get("frontier_support"))
    if max_frontier_support is not None and frontier_support is not None and frontier_support > max_frontier_support:
        return None
    cpc = as_int(row.get("candidate_pool_answer_group_count"))
    if min_cpc is not None and (cpc is None or cpc < min_cpc):
        return None
    answer = row.get("external_majority_answer")
    return str(answer) if answer not in (None, "") else None


def decision_low_depth_variant(
    row: dict[str, Any],
    *,
    frontier_support_le: int | None = None,
    require_swfb: bool = False,
    min_cpc: int | None = None,
) -> str | None:
    if require_swfb and str(row.get("override_reason")) != "single_weak_frontier_branch":
        return None
    frontier_support = as_int(row.get("frontier_support"))
    if frontier_support_le is not None and (frontier_support is None or frontier_support > frontier_support_le):
        return None
    cpc = as_int(row.get("candidate_pool_answer_group_count"))
    if min_cpc is not None and (cpc is None or cpc < min_cpc):
        return None
    answer = row.get("external_majority_answer")
    return str(answer) if answer not in (None, "") else None


def decision_tie_order(row: dict[str, Any], order: tuple[str, ...]) -> str | None:
    if as_int(row.get("external_majority_count")) not in (0, 1, None):
        return None
    if as_bool(row.get("external_answers_unanimous")):
        return None
    return _preferred_external(row, order)


def build_rule_specs() -> list[RuleSpec]:
    specs: list[RuleSpec] = [
        RuleSpec(
            name="majority_2of3_against_frontier",
            family="external_majority_override",
            description="Override when 2/3 external majority disagrees with frontier.",
            decision_fn=lambda row: decision_majority_override(row),
        ),
        RuleSpec(
            name="unanimous_3of3_against_frontier",
            family="external_majority_override",
            description="Override only on 3/3 external unanimity against frontier.",
            decision_fn=lambda row: decision_majority_override(row, unanimous_only=True),
        ),
    ]
    for threshold in (0, 1, 2):
        specs.append(
            RuleSpec(
                name=f"majority_2of3_low_support_le_{threshold}",
                family="external_majority_override",
                description=f"2/3 majority override only when frontier_support <= {threshold}.",
                decision_fn=lambda row, threshold=threshold: decision_majority_override(
                    row,
                    max_frontier_support=threshold,
                ),
            )
        )
    for threshold in (2, 3, 4):
        specs.append(
            RuleSpec(
                name=f"majority_2of3_cpc_ge_{threshold}",
                family="external_majority_override",
                description=f"2/3 majority override only when candidate pool groups >= {threshold}.",
                decision_fn=lambda row, threshold=threshold: decision_majority_override(
                    row,
                    min_cpc=threshold,
                ),
            )
        )
    specs.extend(
        [
            RuleSpec(
                name="eco_unanimous_direct_frontier_agree",
                family="conservative_eco_variant",
                description="Unanimous external override only under direct_frontier_agree.",
                decision_fn=lambda row: decision_majority_override(
                    row,
                    unanimous_only=True,
                    require_override_reason="direct_frontier_agree",
                ),
            ),
            RuleSpec(
                name="eco_unanimous_low_support_le_1",
                family="conservative_eco_variant",
                description="Unanimous external override only with low frontier support.",
                decision_fn=lambda row: decision_majority_override(
                    row,
                    unanimous_only=True,
                    max_frontier_support=1,
                ),
            ),
            RuleSpec(
                name="eco_unanimous_answer_groups_ge_3",
                family="conservative_eco_variant",
                description="Unanimous external override only with at least three answer groups.",
                decision_fn=lambda row: decision_majority_override(
                    row,
                    unanimous_only=True,
                    min_cpc=3,
                ),
            ),
            RuleSpec(
                name="ldg_swfb_majority",
                family="ldg_variant",
                description="SWFB rows use external majority.",
                decision_fn=lambda row: decision_low_depth_variant(row, require_swfb=True),
            ),
            RuleSpec(
                name="ldg_frontier_support_eq_0",
                family="ldg_variant",
                description="Use external majority when frontier_support == 0.",
                decision_fn=lambda row: decision_low_depth_variant(row, frontier_support_le=0, min_cpc=2),
            ),
            RuleSpec(
                name="ldg_frontier_support_le_1",
                family="ldg_variant",
                description="Use external majority when frontier_support <= 1.",
                decision_fn=lambda row: decision_low_depth_variant(row, frontier_support_le=1, min_cpc=2),
            ),
        ]
    )
    for threshold in (2, 3, 4):
        specs.append(
            RuleSpec(
                name=f"ldg_swfb_cpc_ge_{threshold}",
                family="ldg_variant",
                description=f"SWFB rows with CPC >= {threshold} use external majority.",
                decision_fn=lambda row, threshold=threshold: decision_low_depth_variant(
                    row,
                    require_swfb=True,
                    min_cpc=threshold,
                ),
            )
        )
    specs.extend(
        [
            RuleSpec(
                name="tie_order_tale_s1_l1",
                family="tie_order_variant",
                description="On external three-way ties, prefer TALE then S1 then L1.",
                decision_fn=lambda row: decision_tie_order(
                    row,
                    ("tale_answer_canonical", "s1_answer_canonical", "l1_answer_canonical"),
                ),
            ),
            RuleSpec(
                name="tie_order_s1_tale_l1",
                family="tie_order_variant",
                description="On external three-way ties, prefer S1 then TALE then L1.",
                decision_fn=lambda row: decision_tie_order(
                    row,
                    ("s1_answer_canonical", "tale_answer_canonical", "l1_answer_canonical"),
                ),
            ),
            RuleSpec(
                name="tie_order_l1_s1_tale",
                family="tie_order_variant",
                description="On external three-way ties, prefer L1 then S1 then TALE.",
                decision_fn=lambda row: decision_tie_order(
                    row,
                    ("l1_answer_canonical", "s1_answer_canonical", "tale_answer_canonical"),
                ),
            ),
        ]
    )
    return specs


def evaluate_rule(rows: list[dict[str, Any]], spec: RuleSpec) -> dict[str, Any]:
    selections = []
    wins = losses = ties = 0
    target_wins = target_losses = 0
    per_source = {}
    per_source_rows: dict[str, list[tuple[bool, bool]]] = {}
    for row in rows:
        proposal = spec.decision_fn(row)
        selected_answer = proposal or row.get("fta_selected_answer_canonical")
        selected_correct = _candidate_correct(row, selected_answer)
        fta_correct = as_bool(row.get("fta_correct"))
        if selected_correct and not fta_correct:
            wins += 1
        elif fta_correct and not selected_correct:
            losses += 1
        else:
            ties += 1
        if str(row.get("failure_class_coarse")) == "frontier_allocation_miss" and selected_correct and not fta_correct:
            target_wins += 1
        if str(row.get("failure_class_coarse")) == "fta_success" and fta_correct and not selected_correct:
            target_losses += 1
        source_id = str(row.get("source_id"))
        per_source_rows.setdefault(source_id, []).append((selected_correct, fta_correct))
        selections.append(
            {
                "row_id": row.get("row_id"),
                "selected_answer": selected_answer,
                "selected_correct": selected_correct,
                "fta_correct": fta_correct,
            }
        )
    for source_id, pairs in sorted(per_source_rows.items()):
        total = len(pairs)
        candidate_acc = sum(candidate for candidate, _ in pairs) / total if total else 0.0
        fta_acc = sum(fta for _, fta in pairs) / total if total else 0.0
        per_source[source_id] = {
            "row_count": total,
            "candidate_accuracy": round(candidate_acc, 6),
            "canonical_fta_accuracy": round(fta_acc, 6),
            "delta": round(candidate_acc - fta_acc, 6),
            "wins": sum(candidate and not fta for candidate, fta in pairs),
            "losses": sum(fta and not candidate for candidate, fta in pairs),
        }
    accuracy = sum(item["selected_correct"] for item in selections) / len(selections) if selections else 0.0
    source_deltas = [item["delta"] for item in per_source.values()]
    unsafe = bool(source_deltas and min(source_deltas) <= -0.02 and max(source_deltas) >= 0.02)
    dominant_source = None
    overfits_single_source = False
    if wins:
        win_by_source = {
            source_id: item["wins"]
            for source_id, item in per_source.items()
            if item["wins"]
        }
        if win_by_source:
            dominant_source, dominant_wins = max(win_by_source.items(), key=lambda item: item[1])
            if dominant_wins / wins >= 0.8:
                unsafe = True
                overfits_single_source = True
    return {
        "rule_name": spec.name,
        "family": spec.family,
        "description": spec.description,
        "row_count": len(rows),
        "accuracy": round(accuracy, 6),
        "canonical_fta_accuracy": round(_canonical_accuracy(rows), 6),
        "wins_vs_canonical_fta": wins,
        "losses_vs_canonical_fta": losses,
        "ties_vs_canonical_fta": ties,
        "net_wins": wins - losses,
        "target_class_wins": target_wins,
        "target_class_losses": target_losses,
        "runtime_legal_fields_only": True,
        "uses_gold_at_decision_time": False,
        "unsafe": unsafe,
        "overfits_single_source": overfits_single_source,
        "dominant_win_source": dominant_source,
        "per_source_metrics": per_source,
    }


def _split_rows(rows: list[dict[str, Any]], *, include_sources: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("source_id")) in include_sources]


def choose_best_rule(rows: list[dict[str, Any]], specs: list[RuleSpec]) -> dict[str, Any]:
    evaluations = [evaluate_rule(rows, spec) for spec in specs]
    return max(
        evaluations,
        key=lambda item: (item["accuracy"], item["net_wins"], -item["losses_vs_canonical_fta"], item["rule_name"]),
    )


def build_split_diagnostics(rows: list[dict[str, Any]], specs: list[RuleSpec]) -> list[dict[str, Any]]:
    source_ids = sorted({str(row.get("source_id")) for row in rows})
    by_seed = {int(row.get("seed")): str(row.get("source_id")) for row in rows if row.get("seed") is not None}
    splits = [
        (
            "dev_seed41_test_61_71",
            "dev_single_source",
            {by_seed[41]},
            set(source_ids) - {by_seed[41]},
        ),
        (
            "dev_seed71_test_41_61",
            "dev_single_source",
            {by_seed[71]},
            set(source_ids) - {by_seed[71]},
        ),
        (
            "dev_seed61_failure_enriched_diagnostic",
            "diagnostic_single_source",
            {by_seed[61]},
            set(source_ids) - {by_seed[61]},
        ),
    ]
    for holdout in source_ids:
        splits.append(
            (
                f"leave_one_source_out_holdout_{holdout}",
                "leave_one_source_out",
                set(source_ids) - {holdout},
                {holdout},
            )
        )

    split_rows = []
    for split_name, split_type, dev_sources, test_sources in splits:
        dev_rows = _split_rows(rows, include_sources=dev_sources)
        test_rows = _split_rows(rows, include_sources=test_sources)
        best = choose_best_rule(dev_rows, specs)
        test_eval = evaluate_rule(test_rows, next(spec for spec in specs if spec.name == best["rule_name"]))
        split_rows.append(
            {
                "split_name": split_name,
                "split_type": split_type,
                "dev_sources": json.dumps(sorted(dev_sources)),
                "test_sources": json.dumps(sorted(test_sources)),
                "selected_rule": best["rule_name"],
                "dev_accuracy": best["accuracy"],
                "dev_net_wins": best["net_wins"],
                "test_accuracy": test_eval["accuracy"],
                "test_net_wins": test_eval["net_wins"],
                "test_wins": test_eval["wins_vs_canonical_fta"],
                "test_losses": test_eval["losses_vs_canonical_fta"],
                "unsafe": test_eval["unsafe"],
            }
        )
    return split_rows


def build_regression_table(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for evaluation in evaluations:
        for source_id, item in sorted(evaluation["per_source_metrics"].items()):
            rows.append(
                {
                    "rule_name": evaluation["rule_name"],
                    "family": evaluation["family"],
                    "source_id": source_id,
                    "row_count": item["row_count"],
                    "candidate_accuracy": item["candidate_accuracy"],
                    "canonical_fta_accuracy": item["canonical_fta_accuracy"],
                    "delta": item["delta"],
                    "wins": item["wins"],
                    "losses": item["losses"],
                }
            )
    return rows


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Offline Selector Rule Search",
        "",
        "Exploratory offline replay only. This does not change canonical FTA/FIX-2+FIX-4.",
        "",
        "## Top rules overall",
        "",
    ]
    for item in summary["top_rules_overall"]:
        lines.append(
            f"- `{item['rule_name']}` ({item['family']}): accuracy={item['accuracy']:.4f}, "
            f"net_wins={item['net_wins']}, wins={item['wins_vs_canonical_fta']}, "
            f"losses={item['losses_vs_canonical_fta']}, unsafe={item['unsafe']}"
        )
    lines.extend(["", "## Best rules by split", ""])
    for item in summary["best_rules_by_split"]:
        lines.append(
            f"- `{item['split_name']}` -> `{item['selected_rule']}`: dev_acc={item['dev_accuracy']:.4f}, "
            f"test_acc={item['test_accuracy']:.4f}, test_net_wins={item['test_net_wins']}, unsafe={item['unsafe']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    rows = load_feature_rows(args.input)
    specs = build_rule_specs()
    evaluations = [evaluate_rule(rows, spec) for spec in specs]
    evaluations = sorted(
        evaluations,
        key=lambda item: (item["accuracy"], item["net_wins"], -item["losses_vs_canonical_fta"], item["rule_name"]),
        reverse=True,
    )
    split_rows = build_split_diagnostics(rows, specs)
    regression_rows = build_regression_table(evaluations)

    summary = {
        "row_count": len(rows),
        "canonical_fta_accuracy": round(_canonical_accuracy(rows), 6),
        "rule_count": len(specs),
        "top_rules_overall": evaluations[:10],
        "best_rules_by_split": split_rows,
        "unsafe_rule_count": sum(1 for item in evaluations if item["unsafe"]),
    }

    output_dir = Path(args.output_dir)
    csv_rows = []
    for item in evaluations:
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
                "ties_vs_canonical_fta": item["ties_vs_canonical_fta"],
                "net_wins": item["net_wins"],
                "target_class_wins": item["target_class_wins"],
                "target_class_losses": item["target_class_losses"],
                "runtime_legal_fields_only": item["runtime_legal_fields_only"],
                "uses_gold_at_decision_time": item["uses_gold_at_decision_time"],
                "unsafe": item["unsafe"],
                "overfits_single_source": item["overfits_single_source"],
                "dominant_win_source": item["dominant_win_source"],
                "per_source_metrics": json.dumps(item["per_source_metrics"], sort_keys=True),
            }
        )
    write_csv(output_dir / "rule_search_results.csv", csv_rows, list(csv_rows[0].keys()) if csv_rows else ["rule_name"])
    write_json(output_dir / "rule_search_summary.json", summary)
    write_text(output_dir / "rule_search_report.md", render_report(summary))
    write_csv(output_dir / "best_rules_by_split.csv", split_rows, list(split_rows[0].keys()) if split_rows else ["split_name"])
    write_csv(output_dir / "regression_table.csv", regression_rows, list(regression_rows[0].keys()) if regression_rows else ["rule_name"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
