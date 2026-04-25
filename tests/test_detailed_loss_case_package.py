from __future__ import annotations

import csv
from pathlib import Path

from scripts.build_detailed_loss_case_package import (
    build_rows,
    classify_problem_type,
    pair_rows,
    parse_openai_gsm8k_index,
    write_csv,
)


def test_gsm8k_example_id_recovery() -> None:
    assert parse_openai_gsm8k_index("openai_gsm8k_17") == 17
    assert parse_openai_gsm8k_index("openai_gsm8k_0") == 0
    assert parse_openai_gsm8k_index("bad_id") is None


def test_problem_type_classifier_synthetic() -> None:
    assert classify_problem_type("How many ways can we arrange 5 books?") == "counting_combinatorics"
    assert classify_problem_type("What percent of 40 is 10?") == "ratio_percent"
    assert classify_problem_type("A car travels 60 km in 2 hours.") == "unit_conversion"
    assert classify_problem_type("Solve for x in x + 2 = 7") == "algebra_like"


def test_pairing_logic() -> None:
    rows = [
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": "11",
            "budget": "4",
            "example_id": "openai_gsm8k_17",
            "method": "strict_f3",
            "is_correct": "0",
            "failure_type": "present_not_selected",
            "absent_from_tree": "0",
            "present_not_selected": "1",
            "output_layer_mismatch": "0",
            "actions_used": "4",
            "expansions": "4",
            "verifications": "0",
            "budget_exhausted": "0",
        },
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": "11",
            "budget": "4",
            "example_id": "openai_gsm8k_17",
            "method": "external_l1_max",
            "is_correct": "1",
            "failure_type": "correct",
            "actions_used": "1",
        },
    ]
    paired = pair_rows(rows)
    assert len(paired) == 1
    assert paired[0]["pair_type"] == "strict_f3_wrong_external_correct"


def test_output_csv_has_non_empty_header(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    write_csv(path, [{"a": 1, "b": 2}])
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header
    assert all(h.strip() for h in header)


def test_missing_answer_fields_reported() -> None:
    paired = [
        {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": 11,
            "budget": 4,
            "example_id": "openai_gsm8k_17",
            "strict_f3_correct": 0,
            "external_l1_max_correct": 1,
            "pair_type": "strict_f3_wrong_external_correct",
            "strict_f3_failure_type": "present_not_selected",
            "strict_f3_absent_from_tree": 0,
            "strict_f3_present_not_selected": 1,
            "strict_f3_output_layer_mismatch": 0,
            "strict_f3_actions_used": 4,
            "strict_f3_expansions": 4,
            "strict_f3_verifications": 0,
            "strict_f3_budget_exhausted": 0,
            "repeated_same_family_expansion_rate": "NA",
            "max_family_expansion_share": "NA",
            "strict_f3_oracle_gap": "NA",
            "strict_f3_oracle_regret": "NA",
            "external_actions_used": 1,
        }
    ]
    gsm_map = {17: {"question": "If Tom has 2 apples and buys 3, how many?", "gold_answer": "5", "gold_answer_raw": "#### 5"}}
    full_rows, missing_rows, _ = build_rows(paired, gsm_map, "test_mapping")
    assert full_rows[0]["our_final_answer"] == "NA"
    missing_fields = {r["field"] for r in missing_rows if r["missing_count"] > 0}
    assert "our_final_answer" in missing_fields

