from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.analyze_f3_vs_l1_loss_trace_diagnostic import analyze_input_dir, classify_trace_failure


def test_selector_failure_when_gold_group_present_but_not_selected() -> None:
    cls = classify_trace_failure(
        {
            "source_present_not_selected": 1,
            "source_absent_from_tree": 0,
            "gold_answer_canonical": "42",
            "selected_answer_group": "41",
            "answer_group_support_counts": {"42": 2, "41": 3},
            "action_trace": [],
            "branches": [],
        }
    )
    assert cls.bucket == "selector_failure"


def test_extraction_failure_on_parse_flag() -> None:
    cls = classify_trace_failure(
        {
            "source_present_not_selected": 0,
            "source_absent_from_tree": 1,
            "parse_extraction_failure": True,
            "gold_in_tree": True,
            "final_answer_raw": "",
            "final_answer_canonical": "",
            "action_trace": [],
            "branches": [],
        }
    )
    assert cls.bucket == "extraction_or_finalization_failure"


def test_root_diversity_failure_when_shallow_and_low_family_diversity() -> None:
    cls = classify_trace_failure(
        {
            "source_absent_from_tree": 1,
            "source_present_not_selected": 0,
            "action_trace": [{"depth": 0, "family_id": "fam_a"}],
            "branches": [{"depth": 0}],
        }
    )
    assert cls.bucket == "root_diversity_failure"


def test_continuation_focus_failure_when_deeper_but_single_root_family() -> None:
    cls = classify_trace_failure(
        {
            "source_absent_from_tree": 1,
            "source_present_not_selected": 0,
            "action_trace": [
                {"depth": 0, "family_id": "fam_a"},
                {"depth": 1, "family_id": "fam_a"},
            ],
            "branches": [{"depth": 3}],
        }
    )
    assert cls.bucket == "continuation_focus_failure"


def test_analyzer_uses_full_trace_key_with_budget_collision(tmp_path: Path) -> None:
    in_dir = tmp_path / "diag"
    traces = in_dir / "traces"
    traces.mkdir(parents=True)

    selected = [
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": "11",
            "budget": "4",
            "example_id": "same_ex",
            "source_absent_from_tree": "1",
            "source_present_not_selected": "0",
            "problem_type": "counting_combinatorics",
            "gold_answer_canonical": "10",
        },
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": "11",
            "budget": "8",
            "example_id": "same_ex",
            "source_absent_from_tree": "1",
            "source_present_not_selected": "0",
            "problem_type": "ratio_percent",
            "gold_answer_canonical": "10",
        },
    ]
    with (in_dir / "selected_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(selected[0].keys()))
        w.writeheader()
        w.writerows(selected)

    recs = [
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": 11,
            "budget": 4,
            "example_id": "same_ex",
            "method": "strict_f3",
            "status": "scored",
            "exact_match": 0,
            "gold_answer_canonical": "10",
            "result_metadata": {"action_trace": [{"depth": 0, "family_id": "f1"}]},
        },
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": 11,
            "budget": 4,
            "example_id": "same_ex",
            "method": "external_l1_max",
            "status": "scored",
            "exact_match": 1,
            "result_metadata": {},
        },
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": 11,
            "budget": 8,
            "example_id": "same_ex",
            "method": "strict_f3",
            "status": "scored",
            "exact_match": 0,
            "gold_answer_canonical": "10",
            "result_metadata": {"action_trace": [{"depth": 0, "family_id": "f1"}]},
        },
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": 11,
            "budget": 8,
            "example_id": "same_ex",
            "method": "external_l1_max",
            "status": "scored",
            "exact_match": 1,
            "result_metadata": {},
        },
    ]
    with (in_dir / "per_example_records.jsonl").open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    trace_low = {
        "top_level": {"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "same_ex", "method": "strict_f3"},
        "branches": [{"depth": 0}],
    }
    trace_high = {
        "top_level": {"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 8, "example_id": "same_ex", "method": "strict_f3"},
        "branches": [{"depth": 3}],
    }
    (traces / "a.json").write_text(json.dumps(trace_low), encoding="utf-8")
    (traces / "b.json").write_text(json.dumps(trace_high), encoding="utf-8")

    with (in_dir / "per_case_trace_index.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["provider", "dataset", "seed", "budget", "example_id", "method", "trace_path", "trace_available", "n_branches", "n_answer_groups"],
        )
        w.writeheader()
        w.writerow({"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "same_ex", "method": "strict_f3", "trace_path": "traces/a.json", "trace_available": 1, "n_branches": 1, "n_answer_groups": 0})
        w.writerow({"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 8, "example_id": "same_ex", "method": "strict_f3", "trace_path": "traces/b.json", "trace_available": 1, "n_branches": 1, "n_answer_groups": 0})

    report_path = tmp_path / "report.md"
    analyze_input_dir(in_dir, report_path=str(report_path))

    rows = list(csv.DictReader((in_dir / "per_case_trace_classification.csv").open("r", encoding="utf-8")))
    by_budget = {int(r["budget"]): r["primary_bucket"] for r in rows}
    assert by_budget[4] == "root_diversity_failure"
    assert by_budget[8] == "continuation_focus_failure"


def test_analyzer_io_outputs_exist(tmp_path: Path) -> None:
    in_dir = tmp_path / "io_diag"
    traces = in_dir / "traces"
    traces.mkdir(parents=True)

    with (in_dir / "selected_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["provider", "dataset", "seed", "budget", "example_id", "source_absent_from_tree", "source_present_not_selected", "problem_type", "gold_answer_canonical"],
        )
        w.writeheader()
        w.writerow({"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "ex1", "source_absent_from_tree": 1, "source_present_not_selected": 0, "problem_type": "counting_combinatorics", "gold_answer_canonical": "10"})

    with (in_dir / "per_example_records.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "ex1", "method": "strict_f3", "status": "scored", "exact_match": 0, "gold_answer_canonical": "10", "result_metadata": {"action_trace": [{"depth": 0, "family_id": "f"}]}}) + "\n")
        f.write(json.dumps({"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "ex1", "method": "external_l1_max", "status": "scored", "exact_match": 1, "result_metadata": {}}) + "\n")

    (traces / "t.json").write_text(json.dumps({"top_level": {"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "ex1", "method": "strict_f3"}, "branches": [{"depth": 0}]}), encoding="utf-8")

    with (in_dir / "per_case_trace_index.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "dataset", "seed", "budget", "example_id", "method", "trace_path", "trace_available", "n_branches", "n_answer_groups"])
        w.writeheader()
        w.writerow({"provider": "cohere", "dataset": "openai/gsm8k", "seed": 11, "budget": 4, "example_id": "ex1", "method": "strict_f3", "trace_path": "traces/t.json", "trace_available": 1, "n_branches": 1, "n_answer_groups": 0})

    report_path = tmp_path / "safe_report.md"
    analyze_input_dir(in_dir, report_path=str(report_path))

    required = [
        "manifest.json",
        "README.md",
        "per_case_trace_classification.csv",
        "aggregate_failure_breakdown.csv",
        "absent_from_tree_subtype_breakdown.csv",
        "present_not_selected_breakdown.csv",
        "per_budget_breakdown.csv",
        "per_problem_type_breakdown.csv",
        "recommended_algorithmic_repairs.md",
    ]
    for name in required:
        assert (in_dir / name).exists()
    assert report_path.exists()
