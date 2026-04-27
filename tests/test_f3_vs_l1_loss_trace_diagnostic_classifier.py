from __future__ import annotations

from scripts.analyze_f3_vs_l1_loss_trace_diagnostic import classify_trace_failure


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
                {"depth": 2, "family_id": "fam_a"},
            ],
            "branches": [{"depth": 3}],
        }
    )
    assert cls.bucket == "continuation_focus_failure"
