"""Deterministic offline sub-pattern miner over the failure feature table."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.failure_analysis_common import (
    answer_group_signature,
    as_bool,
    as_int,
    compute_group_stats,
    group_rows_by_source_seed,
    load_feature_rows,
    summarize_representatives,
    write_csv,
    write_json,
    write_text,
)

TARGET_CLASSES = (
    "frontier_allocation_miss",
    "hard_all_methods_wrong_or_pool_miss",
    "fta_success",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="outputs/failure_analysis/failure_feature_table.jsonl",
        help="Failure feature table JSONL.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Non-destructive output directory.",
    )
    return parser.parse_args()


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("source_id")),
            int(row.get("seed") or 0),
            str(row.get("example_id")),
        ),
    )


def _external_correct_count(row: dict[str, Any]) -> int:
    return sum(
        1
        for key in ("l1_correct", "s1_correct", "tale_correct")
        if as_bool(row.get(key))
    )


def classify_frontier_allocation_miss(row: dict[str, Any]) -> str:
    gold_norm = row.get("normalized_gold_answer")
    if as_bool(row.get("correct_in_candidate_pool")) and not as_bool(row.get("any_candidate_correct")):
        return "possible_tree_coverage_signal_if_gold_in_tree"
    if (
        as_bool(row.get("external_answers_unanimous"))
        and row.get("external_majority_answer")
        and row.get("external_majority_answer") == gold_norm
    ):
        return "external_unanimous_correct_but_fta_not"
    if (
        as_int(row.get("external_majority_count")) or 0
    ) >= 2 and row.get("external_majority_answer") == gold_norm:
        return "external_majority_correct_but_fta_not"
    external_correct_count = _external_correct_count(row)
    if external_correct_count >= 2:
        return "correct_in_multiple_externals"
    if as_bool(row.get("l1_correct")) and not any(
        as_bool(row.get(key)) for key in ("s1_correct", "tale_correct", "frontier_correct")
    ):
        return "correct_only_in_l1"
    if as_bool(row.get("s1_correct")) and not any(
        as_bool(row.get(key)) for key in ("l1_correct", "tale_correct", "frontier_correct")
    ):
        return "correct_only_in_s1"
    if as_bool(row.get("tale_correct")) and not any(
        as_bool(row.get(key)) for key in ("l1_correct", "s1_correct", "frontier_correct")
    ):
        return "correct_only_in_tale"
    if not as_bool(row.get("frontier_correct")) and (as_int(row.get("external_majority_count")) or 0) < 2:
        return "frontier_wrong_external_split"
    return "unknown_selection_miss"


def classify_hard_failure(row: dict[str, Any]) -> str:
    if as_bool(row.get("correct_in_candidate_pool")) and not as_bool(row.get("any_candidate_correct")):
        return "no_candidate_correct_but_gold_in_tree_if_available"
    if (as_int(row.get("answer_group_count")) or 0) == 1 and not as_bool(row.get("frontier_correct")):
        return "all_four_same_wrong_answer"
    if as_bool(row.get("external_answers_unanimous")) and not as_bool(row.get("any_external_correct")):
        return "external_unanimous_wrong"
    if (as_int(row.get("answer_group_count")) or 0) >= 4:
        return "all_answers_different_wrong"
    if as_bool(row.get("frontier_matches_any_external")) and not as_bool(row.get("frontier_correct")):
        return "frontier_matches_some_external_wrong"
    if not as_bool(row.get("correct_in_candidate_pool")):
        return "no_candidate_correct_no_tree_signal"
    return "unknown_pool_miss"


def classify_success_mechanism(row: dict[str, Any]) -> str:
    if as_bool(row.get("effective_fix4_action")):
        if not as_bool(row.get("frontier_correct")):
            return "external_consensus_rescue"
        return "effective_fix4_success"
    if as_bool(row.get("effective_fix2_action")):
        if not as_bool(row.get("frontier_correct")):
            return "external_majority_rescue"
        return "effective_fix2_success"
    return "original_frontier_success"


def assign_subpattern_label(row: dict[str, Any]) -> str:
    failure_class = str(row.get("failure_class_coarse") or "")
    if failure_class == "frontier_allocation_miss":
        return classify_frontier_allocation_miss(row)
    if failure_class == "hard_all_methods_wrong_or_pool_miss":
        return classify_hard_failure(row)
    if failure_class == "fta_success":
        return classify_success_mechanism(row)
    return "not_target_class"


def annotate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for row in _sorted_rows(rows):
        out = dict(row)
        out["subpattern_label"] = assign_subpattern_label(row)
        out["normalized_answer_groups"] = answer_group_signature(row)
        annotated.append(out)
    return annotated


def build_summary(annotated_rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall_counts = Counter()
    reps_by_label: dict[str, list[dict[str, Any]]] = {}
    rows_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_failure_class: dict[str, Counter[str]] = defaultdict(Counter)
    for row in annotated_rows:
        label = str(row["subpattern_label"])
        rows_by_label[label].append(row)
        if row.get("failure_class_coarse") in TARGET_CLASSES:
            overall_counts[label] += 1
            by_failure_class[str(row.get("failure_class_coarse"))][label] += 1
    for label, rows in rows_by_label.items():
        if label == "not_target_class":
            continue
        reps_by_label[label] = summarize_representatives(rows)

    group_breakdowns: list[dict[str, Any]] = []
    for (source_id, seed), group_rows in sorted(group_rows_by_source_seed(annotated_rows).items()):
        stats = compute_group_stats(group_rows)
        stats.update(
            {
                "source_id": source_id,
                "seed": seed,
                "subpattern_counts": dict(Counter(str(row["subpattern_label"]) for row in group_rows)),
            }
        )
        group_breakdowns.append(stats)

    summary_rows = []
    target_total = sum(overall_counts.values()) or 1
    for failure_class in TARGET_CLASSES:
        class_total = sum(by_failure_class[failure_class].values()) or 1
        for label, count in sorted(by_failure_class[failure_class].items()):
            summary_rows.append(
                {
                    "failure_class_coarse": failure_class,
                    "subpattern_label": label,
                    "row_count": count,
                    "share_of_target_rows": round(count / target_total, 6),
                    "share_within_failure_class": round(count / class_total, 6),
                }
            )

    return {
        "rows_written": len(annotated_rows),
        "subpattern_counts": dict(sorted(overall_counts.items())),
        "subpattern_summary_rows": summary_rows,
        "representative_examples": reps_by_label,
        "per_source_seed": group_breakdowns,
    }


def _case_export_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row.get("row_id"),
        "example_id": row.get("example_id"),
        "source_id": row.get("source_id"),
        "seed": row.get("seed"),
        "failure_class_coarse": row.get("failure_class_coarse"),
        "subpattern_label": row.get("subpattern_label"),
        "problem_text": row.get("problem_text"),
        "gold_answer_canonical": row.get("gold_answer_canonical"),
        "frontier_answer": row.get("frontier_answer"),
        "l1_answer": row.get("l1_answer"),
        "s1_answer": row.get("s1_answer"),
        "tale_answer": row.get("tale_answer"),
        "fta_selected_answer": row.get("fta_selected_answer"),
        "effective_policy_label": row.get("effective_policy_label"),
        "frontier_correct": row.get("frontier_correct"),
        "l1_correct": row.get("l1_correct"),
        "s1_correct": row.get("s1_correct"),
        "tale_correct": row.get("tale_correct"),
        "fta_correct": row.get("fta_correct"),
        "external_majority_answer": row.get("external_majority_answer"),
        "external_majority_count": row.get("external_majority_count"),
        "normalized_answer_groups": row.get("normalized_answer_groups"),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Failure Sub-Pattern Report",
        "",
        "Offline diagnostic report over the canonical failure feature table.",
        "",
        "## Overall sub-pattern counts",
        "",
    ]
    for label, count in summary["subpattern_counts"].items():
        lines.append(f"- `{label}`: {count}")
    lines.extend(["", "## Per source/seed", ""])
    for item in summary["per_source_seed"]:
        lines.append(
            f"- `{item['source_id']}` seed={item['seed']}: rows={item['row_count']}, "
            f"fta_accuracy={item['fta_accuracy']:.4f}, fix2={item['effective_fix2_action_count']}, "
            f"fix4={item['effective_fix4_action_count']}, no_gate={item['no_effective_gate_action_count']}"
        )
    lines.extend(["", "## Representative examples", ""])
    for label, rows in sorted(summary["representative_examples"].items()):
        lines.append(f"### {label}")
        for row in rows:
            lines.append(
                "- "
                f"{row['example_id']} | {row['source_id']} | seed={row['seed']} | "
                f"gold={row['gold_answer_canonical']} | frontier={row['frontier_answer']} | "
                f"l1={row['l1_answer']} | s1={row['s1_answer']} | tale={row['tale_answer']} | "
                f"fta={row['fta_selected_answer']} | action={row['effective_policy_label']} | "
                f"groups={row['answer_group_signature']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    rows = load_feature_rows(args.input)
    annotated_rows = annotate_rows(rows)
    summary = build_summary(annotated_rows)

    output_dir = Path(args.output_dir)
    miss_rows = [row for row in annotated_rows if row.get("failure_class_coarse") == "frontier_allocation_miss"]
    hard_rows = [
        row for row in annotated_rows if row.get("failure_class_coarse") == "hard_all_methods_wrong_or_pool_miss"
    ]
    success_rows = [row for row in annotated_rows if row.get("failure_class_coarse") == "fta_success"]

    write_json(output_dir / "subpattern_summary.json", summary)
    write_csv(
        output_dir / "subpattern_summary.csv",
        summary["subpattern_summary_rows"],
        [
            "failure_class_coarse",
            "subpattern_label",
            "row_count",
            "share_of_target_rows",
            "share_within_failure_class",
        ],
    )
    write_text(output_dir / "subpattern_report.md", render_report(summary))
    write_csv(
        output_dir / "frontier_allocation_miss_cases.csv",
        [_case_export_row(row) for row in miss_rows],
        list(_case_export_row(miss_rows[0]).keys()) if miss_rows else list(_case_export_row({}).keys()),
    )
    write_csv(
        output_dir / "hard_all_methods_wrong_or_pool_miss_cases.csv",
        [_case_export_row(row) for row in hard_rows],
        list(_case_export_row(hard_rows[0]).keys()) if hard_rows else list(_case_export_row({}).keys()),
    )
    write_csv(
        output_dir / "fta_success_gate_actions.csv",
        [_case_export_row(row) for row in success_rows],
        list(_case_export_row(success_rows[0]).keys()) if success_rows else list(_case_export_row({}).keys()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
