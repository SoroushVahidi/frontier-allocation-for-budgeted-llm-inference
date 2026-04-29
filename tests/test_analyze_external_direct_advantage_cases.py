from scripts.analyze_external_direct_advantage_cases import classify_case


def test_true_direct_advantage() -> None:
    row = {"trace_available": "1", "internal_exact": "0", "external_exact": "1"}
    assert classify_case(row) == "true_direct_advantage_likely"


def test_missing_trace() -> None:
    row = {"trace_available": "0", "internal_exact": "0", "external_exact": "1"}
    assert classify_case(row) == "missing_trace_relabel_needed"


def test_present_not_selected() -> None:
    row = {"trace_available": "1", "internal_exact": "0", "external_exact": "1", "metadata_hint": "present not selected"}
    assert classify_case(row) == "possible_present_not_selected"


def test_extraction_issue() -> None:
    row = {"trace_available": "1", "internal_exact": "0", "external_exact": "1", "metadata_hint": "normalization mismatch"}
    assert classify_case(row) == "possible_extraction_issue"


def test_over_explore() -> None:
    row = {
        "trace_available": "1", "internal_exact": "0", "external_exact": "1",
        "internal_total_tokens": "900", "external_total_tokens": "200"
    }
    assert classify_case(row) == "possible_over_exploration_commit_issue"
