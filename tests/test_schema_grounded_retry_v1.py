from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import pytest

from experiments.schema_grounded_retry import (
    REQUIRED_SCHEMA_LABELS,
    case_has_minimum_probe_data,
    parse_schema_grounded_response,
    select_schema_for_problem_features,
    validate_schema_grounded_response,
)
from experiments.targeted_discovery_retry import (
    build_schema_grounded_average_total_count_prompt,
    build_schema_grounded_quantity_ledger_prompt,
    build_schema_grounded_rate_table_prompt,
    build_schema_grounded_ratio_equation_prompt,
    build_schema_grounded_state_transition_prompt,
    build_schema_grounded_target_difference_prompt,
)

REPO = Path(__file__).resolve().parents[1]


def _all_prompts(q: str) -> list[str]:
    return [
        build_schema_grounded_quantity_ledger_prompt(q),
        build_schema_grounded_rate_table_prompt(q),
        build_schema_grounded_state_transition_prompt(q),
        build_schema_grounded_ratio_equation_prompt(q),
        build_schema_grounded_target_difference_prompt(q),
        build_schema_grounded_average_total_count_prompt(q),
    ]


def test_schema_grounded_prompt_builders_include_required_labels() -> None:
    prompts = _all_prompts("A store sells 3 books at $4 each. How much total?")
    for p in prompts:
        for r in REQUIRED_SCHEMA_LABELS:
            assert r in p
        assert "FINAL_ANSWER: <number>" in p
        low = p.lower()
        assert "your entire response must be only the block below" in low
        assert "do not explain outside the block" in low
        assert "copy these exact labels" in low
        assert "do not put units or words" in low
        assert "do not give multiple final answers" in low
        assert "if uncertain, still output one best numeric" in low
        assert "discovery3" not in low


def test_schema_prompt_builders_signature_no_gold_or_prediction_args() -> None:
    for fn in [
        build_schema_grounded_quantity_ledger_prompt,
        build_schema_grounded_rate_table_prompt,
        build_schema_grounded_state_transition_prompt,
        build_schema_grounded_ratio_equation_prompt,
        build_schema_grounded_target_difference_prompt,
        build_schema_grounded_average_total_count_prompt,
    ]:
        params = inspect.signature(fn).parameters
        assert list(params.keys()) == ["problem_text"]


def test_parse_schema_grounded_response_accepts_valid() -> None:
    text = """SCHEMA_TYPE: rate_table_schema
TARGET_QUANTITY: total distance
GIVEN_QUANTITIES:
- speed: 30
- time: 2
EQUATIONS:
- distance = speed * time
COMPUTATION:
- distance = 30 * 2 = 60
FINAL_ANSWER: 60
"""
    parsed = parse_schema_grounded_response(text)
    assert parsed["parse_success"] is True
    validated = validate_schema_grounded_response(parsed)
    assert validated["validation_success"] is True


def test_parse_schema_grounded_response_rejects_missing_final() -> None:
    text = """SCHEMA_TYPE: quantity_ledger_schema
TARGET_QUANTITY: total
GIVEN_QUANTITIES:
- a: 1
EQUATIONS:
- t=a
COMPUTATION:
- t=1
"""
    parsed = parse_schema_grounded_response(text)
    assert parsed["parse_success"] is False
    assert "missing_final_answer" in parsed["parse_errors"]


def test_parse_schema_grounded_response_rejects_multiple_finals() -> None:
    text = """SCHEMA_TYPE: quantity_ledger_schema
TARGET_QUANTITY: total
GIVEN_QUANTITIES:
- a: 1
EQUATIONS:
- t=a
COMPUTATION:
- t=1
FINAL_ANSWER: 1
FINAL_ANSWER: 2
"""
    parsed = parse_schema_grounded_response(text)
    assert "multiple_final_answer_lines" in parsed["parse_errors"]


def test_validator_rejects_missing_equations_for_equation_schema() -> None:
    parsed = {
        "schema_type": "rate_table_schema",
        "target_quantity": "distance",
        "given_quantities": ["speed:30", "time:2"],
        "equations": [],
        "computation": ["distance=60"],
        "final_answer": "60",
        "parse_success": True,
        "parse_errors": [],
    }
    validated = validate_schema_grounded_response(parsed)
    assert validated["validation_success"] is False
    assert "missing_equations" in validated["validation_errors"]


def test_select_schema_for_problem_features_basic() -> None:
    assert select_schema_for_problem_features("What is the average score?") == "average_total_count_schema"
    assert select_schema_for_problem_features("A car moves at 30 mph for 2 hours.") == "rate_table_schema"
    assert select_schema_for_problem_features("After buying and then selling, how much remains?") == "before_after_state_schema"


def test_case_has_minimum_probe_data() -> None:
    ok, reason = case_has_minimum_probe_data({"problem_text if available": "A + B?", "gold_answer if available": "5"})
    assert ok is True
    assert reason == ""
    ok, reason = case_has_minimum_probe_data({"problem_text if available": "", "gold_answer if available": "5"})
    assert ok is False
    assert reason == "missing_problem_text"
    ok, reason = case_has_minimum_probe_data({"problem_text if available": "A + B?", "gold_answer if available": ""})
    assert ok is False
    assert reason == "missing_gold_answer"


def test_schema_grounded_dry_run_prompts_pass_leakage_checks() -> None:
    out_dirs = sorted(REPO.glob("outputs/schema_grounded_retry_v1_dry_run_*"))
    if not out_dirs:
        pytest.skip("schema-grounded dry-run not generated yet")
    out = out_dirs[-1]
    manifest = json.loads((out / "schema_grounded_manifest.json").read_text(encoding="utf-8"))
    assert manifest["no_api_calls"] is True
    assert manifest["no_gold_in_prompts_verified"] is True
    assert manifest["no_prediction_leakage_verified"] is True
    assert manifest["every_prompt_contains_final_answer_literal"] is True
    assert manifest["every_prompt_contains_schema_block_labels"] is True
    rows = list(csv.DictReader((out / "schema_grounded_call_plan.csv").open(encoding="utf-8")))
    assert rows
    for r in rows:
        txt = (REPO / r["prompt_path"]).read_text(encoding="utf-8")
        assert "FINAL_ANSWER: <number>" in txt
        assert "SCHEMA_TYPE:" in txt
