from __future__ import annotations

from experiments.targeted_discovery_retry import build_prompt, choose_scaffold_v2, validate_prompt_no_gold


def test_routing_v2_maps_top_cases_to_non_unknown_scaffold() -> None:
    rows = [
        {"case_id": "openai_gsm8k_683", "proposed_problem_family_v2": "percent_base_denominator", "problem_text": "losing 9% then 7% each hour"},
        {"case_id": "openai_gsm8k_752", "proposed_problem_family_v2": "combinatorics_counting", "problem_text": "split class into 3 groups"},
        {"case_id": "openai_gsm8k_758", "proposed_problem_family_v2": "average_target_score", "problem_text": "average of six tests"},
        {"case_id": "openai_gsm8k_769", "proposed_problem_family_v2": "ratio_partition", "problem_text": "adult gets twice kid share"},
        {"case_id": "openai_gsm8k_695", "proposed_problem_family_v2": "state_composition", "problem_text": "day 1 and day 2 fill tank"},
    ]
    for row in rows:
        scaffold = choose_scaffold_v2(row)
        assert scaffold not in {"", "unknown"}


def test_new_scaffold_prompts_contain_expected_structure() -> None:
    sample_problem = "A class has scores and needs an average of 93."
    scaffolds = [
        "percent_base_denominator",
        "average_target_score",
        "combinatorics_counting",
        "ratio_partition",
        "state_composition",
    ]
    for scaffold in scaffolds:
        prompt = build_prompt(sample_problem, scaffold)
        assert "final answer" in prompt.lower()
        assert len(prompt.strip()) > 50


def test_new_scaffold_prompt_no_gold_leakage_helper() -> None:
    prompt = build_prompt("Find the missing test score.", "average_target_score")
    assert validate_prompt_no_gold(prompt, "98")
