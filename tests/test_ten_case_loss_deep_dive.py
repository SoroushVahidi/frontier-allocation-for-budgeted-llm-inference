from __future__ import annotations

from scripts.build_10_case_loss_deep_dive import classify_problem_type, keyword_tags, parse_openai_gsm8k_index


def test_parse_openai_gsm8k_index_valid_and_invalid() -> None:
    assert parse_openai_gsm8k_index("openai_gsm8k_42") == 42
    assert parse_openai_gsm8k_index("gsm8k_42") is None


def test_classify_problem_type_combinatorics_and_ratio() -> None:
    assert classify_problem_type("How many ways can 5 students be arranged?") == "counting_combinatorics"
    assert classify_problem_type("What percent of 40 is 10?") == "ratio_percent"


def test_keyword_tags_detect_expected_signals() -> None:
    tags = keyword_tags("How many ways to choose 2 students in 1 hour?")
    assert tags["contains_how_many"] == 1
    assert tags["contains_ways_choose_arrange"] == 1
    assert tags["contains_time"] == 1
