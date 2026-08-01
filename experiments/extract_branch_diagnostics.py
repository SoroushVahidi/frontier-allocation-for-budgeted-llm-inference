"""Extract branch-level offline diagnostics from canonical frontier raw rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.build_failure_feature_table import normalize_answer
from experiments.failure_analysis_common import (
    as_bool,
    as_int,
    group_rows_by_source_seed,
    load_canonical_raw_grouped,
    load_feature_rows,
    maybe_json_dict,
    maybe_json_list,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)

REQUESTED_FIELDS = {
    "result_metadata": "frontier row result_metadata",
    "final_nodes": "frontier row final_nodes list",
    "direct_reserve_attempts": "result_metadata.direct_reserve_attempts",
    "frontier_support": "result_metadata.frontier_support",
    "candidate_pool_answer_group_count": "result_metadata.candidate_pool_answer_group_count",
    "override_reason": "result_metadata.override_reason",
    "direct_frontier_agree": "result_metadata.direct_frontier_agree",
    "gold_in_tree": "frontier row gold_in_tree",
    "branch_answer_groups": "result_metadata.answer_group_best_branch_scores or support counts",
    "tree_depth": "branch_depth in result_metadata.action_trace",
    "branch_count": "count of final_nodes",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="outputs/failure_analysis/failure_feature_table.jsonl",
        help="Failure feature table JSONL.",
    )
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    return parser.parse_args()


def _normalized_set(values: list[Any]) -> list[str]:
    out = sorted({norm for norm in (normalize_answer(value) for value in values) if norm})
    return out


def _max_branch_depth(action_trace: list[dict[str, Any]]) -> int | None:
    depths = [as_int(item.get("branch_depth")) for item in action_trace if isinstance(item, dict)]
    clean = [depth for depth in depths if depth is not None]
    return max(clean) if clean else None


def build_branch_row(feature_row: dict[str, Any], frontier_raw: dict[str, Any]) -> dict[str, Any]:
    rm = maybe_json_dict(frontier_raw.get("result_metadata"))
    final_nodes = maybe_json_list(frontier_raw.get("final_nodes"))
    action_trace = maybe_json_list(rm.get("action_trace"))
    direct_reserve_attempts = maybe_json_list(rm.get("direct_reserve_attempts"))
    answer_group_scores = maybe_json_dict(rm.get("answer_group_best_branch_scores"))
    answer_group_supports = maybe_json_dict(rm.get("answer_group_support_counts"))

    final_node_answers = _normalized_set(
        [node.get("predicted_answer_normalized") or node.get("predicted_answer") for node in final_nodes if isinstance(node, dict)]
    )
    attempt_answers = _normalized_set(
        [attempt.get("extracted_answer") for attempt in direct_reserve_attempts if isinstance(attempt, dict)]
    )
    gold_norm = normalize_answer(feature_row.get("gold_answer_canonical"))
    gold_in_tree = as_bool(frontier_raw.get("gold_in_tree"))
    gold_in_final_nodes = gold_norm in final_node_answers if gold_norm else False
    gold_in_attempts = gold_norm in attempt_answers if gold_norm else False
    any_tree_signal_for_gold = gold_in_tree or gold_in_final_nodes or gold_in_attempts

    return {
        "row_id": feature_row.get("row_id"),
        "example_id": feature_row.get("example_id"),
        "source_id": feature_row.get("source_id"),
        "seed": feature_row.get("seed"),
        "failure_class_coarse": feature_row.get("failure_class_coarse"),
        "fta_correct": feature_row.get("fta_correct"),
        "effective_policy_label": feature_row.get("effective_policy_label"),
        "result_metadata_present": bool(rm),
        "final_nodes_present": bool(final_nodes),
        "direct_reserve_attempts_present": bool(direct_reserve_attempts),
        "frontier_support": rm.get("frontier_support"),
        "candidate_pool_answer_group_count": rm.get("candidate_pool_answer_group_count"),
        "override_reason": rm.get("override_reason"),
        "direct_frontier_agree": rm.get("direct_frontier_agree"),
        "support_margin": rm.get("support_margin"),
        "direct_reserve_confidence_proxy": rm.get("direct_reserve_confidence_proxy"),
        "direct_reserve_source_method": rm.get("direct_reserve_source_method"),
        "direct_reserve_answer": rm.get("direct_reserve_answer"),
        "frontier_candidate_answer": rm.get("frontier_candidate_answer"),
        "gold_in_tree": gold_in_tree,
        "gold_in_final_nodes": gold_in_final_nodes,
        "gold_in_direct_reserve_attempts": gold_in_attempts,
        "any_tree_signal_for_gold": any_tree_signal_for_gold,
        "visible_candidate_correct": feature_row.get("any_candidate_correct"),
        "correct_in_candidate_pool": feature_row.get("correct_in_candidate_pool"),
        "final_nodes_count": len(final_nodes),
        "direct_reserve_attempts_count": len(direct_reserve_attempts),
        "action_trace_count": len(action_trace),
        "max_branch_depth": _max_branch_depth([item for item in action_trace if isinstance(item, dict)]),
        "branch_answer_group_count": len(answer_group_scores) or len(answer_group_supports),
        "final_node_answer_count": len(final_node_answers),
        "attempt_answer_count": len(attempt_answers),
        "final_node_answers": final_node_answers,
        "attempt_answers": attempt_answers,
    }


def build_branch_rows(feature_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_grouped = load_canonical_raw_grouped()
    rows: list[dict[str, Any]] = []
    missing_sources = Counter()
    missing_examples = Counter()
    availability = Counter()

    for feature_row in sorted(feature_rows, key=lambda row: str(row.get("row_id"))):
        source_id = str(feature_row.get("source_id"))
        example_id = str(feature_row.get("example_id"))
        source_rows = raw_grouped.get(source_id)
        if source_rows is None:
            missing_sources[source_id] += 1
            continue
        method_rows = source_rows.get(example_id)
        if method_rows is None:
            missing_examples[source_id] += 1
            continue
        frontier_raw = method_rows["direct_reserve_semantic_frontier_v2"]
        row = build_branch_row(feature_row, frontier_raw)
        rows.append(row)
        if row["result_metadata_present"]:
            availability["result_metadata"] += 1
        if row["final_nodes_present"]:
            availability["final_nodes"] += 1
        if row["direct_reserve_attempts_present"]:
            availability["direct_reserve_attempts"] += 1
        if row.get("frontier_support") not in (None, ""):
            availability["frontier_support"] += 1
        if row.get("candidate_pool_answer_group_count") not in (None, ""):
            availability["candidate_pool_answer_group_count"] += 1
        if row.get("override_reason") not in (None, ""):
            availability["override_reason"] += 1
        if row.get("direct_frontier_agree") not in (None, ""):
            availability["direct_frontier_agree"] += 1
        if frontier_raw.get("gold_in_tree") not in (None, ""):
            availability["gold_in_tree"] += 1
        if row.get("branch_answer_group_count"):
            availability["branch_answer_groups"] += 1
        if row.get("max_branch_depth") is not None:
            availability["tree_depth"] += 1
        if row.get("final_nodes_count") is not None:
            availability["branch_count"] += 1

    grouped = group_rows_by_source_seed(rows)
    per_group = []
    for (source_id, seed), group in sorted(grouped.items()):
        per_group.append(
            {
                "source_id": source_id,
                "seed": seed,
                "row_count": len(group),
                "fta_accuracy": round(sum(as_bool(row.get("fta_correct")) for row in group) / len(group), 6) if group else None,
                "tree_signal_rate": round(sum(as_bool(row.get("any_tree_signal_for_gold")) for row in group) / len(group), 6) if group else None,
                "override_reason_counts": dict(Counter(str(row.get("override_reason")) for row in group)),
            }
        )

    class_summary = {}
    for failure_class in sorted({str(row.get("failure_class_coarse")) for row in rows}):
        subset = [row for row in rows if row.get("failure_class_coarse") == failure_class]
        if not subset:
            continue
        class_summary[failure_class] = {
            "row_count": len(subset),
            "gold_in_tree_count": sum(as_bool(row.get("gold_in_tree")) for row in subset),
            "any_tree_signal_for_gold_count": sum(as_bool(row.get("any_tree_signal_for_gold")) for row in subset),
            "visible_candidate_correct_count": sum(as_bool(row.get("visible_candidate_correct")) for row in subset),
            "hidden_tree_signal_without_visible_candidate_count": sum(
                as_bool(row.get("any_tree_signal_for_gold")) and not as_bool(row.get("visible_candidate_correct"))
                for row in subset
            ),
        }

    override_reason_summary = {}
    for override_reason in sorted({str(row.get("override_reason")) for row in rows}):
        subset = [row for row in rows if str(row.get("override_reason")) == override_reason]
        override_reason_summary[override_reason] = {
            "row_count": len(subset),
            "fta_accuracy": round(sum(as_bool(row.get("fta_correct")) for row in subset) / len(subset), 6) if subset else None,
            "failure_class_counts": dict(Counter(str(row.get("failure_class_coarse")) for row in subset)),
        }

    summary = {
        "rows_written": len(rows),
        "missing_sources": dict(missing_sources),
        "missing_examples": dict(missing_examples),
        "requested_field_availability": {
            field: {
                "description": description,
                "present_count": availability.get(field, 0),
                "absent_count": len(rows) - availability.get(field, 0),
            }
            for field, description in REQUESTED_FIELDS.items()
        },
        "fully_absent_fields": [field for field in REQUESTED_FIELDS if availability.get(field, 0) == 0],
        "per_source_seed": per_group,
        "failure_class_tree_signal_summary": class_summary,
        "override_reason_summary": override_reason_summary,
    }
    return rows, summary


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Branch Diagnostics Report",
        "",
        "Offline branch diagnostics joined from the canonical replay table and canonical raw frontier rows.",
        "",
        "## Requested field availability",
        "",
    ]
    for field, item in summary["requested_field_availability"].items():
        lines.append(
            f"- `{field}`: present={item['present_count']}, absent={item['absent_count']}"
        )
    if summary["fully_absent_fields"]:
        lines.extend(["", "## Fully absent fields", ""])
        for field in summary["fully_absent_fields"]:
            lines.append(f"- `{field}`")
    lines.extend(["", "## Failure-class tree signal summary", ""])
    for failure_class, item in summary["failure_class_tree_signal_summary"].items():
        lines.append(
            f"- `{failure_class}`: rows={item['row_count']}, gold_in_tree={item['gold_in_tree_count']}, "
            f"any_tree_signal={item['any_tree_signal_for_gold_count']}, "
            f"hidden_tree_signal_without_visible_candidate={item['hidden_tree_signal_without_visible_candidate_count']}"
        )
    lines.extend(["", "## Override-reason summary", ""])
    for override_reason, item in summary["override_reason_summary"].items():
        lines.append(
            f"- `{override_reason}`: rows={item['row_count']}, fta_accuracy={item['fta_accuracy']:.4f}"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    feature_rows = load_feature_rows(args.input)
    rows, summary = build_branch_rows(feature_rows)
    output_dir = Path(args.output_dir)
    write_csv(
        output_dir / "branch_diagnostics_table.csv",
        rows,
        list(rows[0].keys()) if rows else ["row_id"],
    )
    write_jsonl(output_dir / "branch_diagnostics_table.jsonl", rows)
    write_json(output_dir / "branch_diagnostics_summary.json", summary)
    write_text(output_dir / "branch_diagnostics_report.md", render_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
