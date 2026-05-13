"""Tests for run_cerebras_failure_pattern_pilot.py (no API calls)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.run_cerebras_failure_pattern_pilot import (
    VALID_SUBTYPES,
    VALID_NEXT_EDGES,
    REQUIRED_RESPONSE_FIELDS,
    audit_prompt_for_gold,
    build_case_prompt,
    compute_agreement,
    load_missing_edge_recs,
    load_replay_casebook,
    load_trace_packets,
    parse_gold_pool_split,
    select_cases,
    validate_response,
    _try_json_parse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_case(case_id: str = "openai_gsm8k_1") -> dict:
    return {
        "case_id": case_id,
        "question": f"Question for {case_id}",
        "model_final_prediction": "42",
        "selector_metadata": {"selected_answer": "42", "selected_source": "repair_layer"},
        "action_trace_summary": {
            "short_diagnosis": "collapsed to single answer",
            "selection_reason": "single_weak_frontier_branch",
            "failure_family": "unknown",
            "likely_mismatch_subtype": "",
        },
        "pal_exec_summary": {
            "pal_exec_ok": "0",
            "pal_answer": "",
            "pal_error_type": "seed_empty",
        },
        "structural_fields": {"candidate_rows": []},
        "selector_candidate_pool": ["42", "42"],
    }


def _valid_response(case_id: str = "openai_gsm8k_1") -> dict:
    return {
        "case_id": case_id,
        "primary_failure_mechanism": "wrong_target_binding",
        "secondary_failure_mechanisms": [],
        "is_final_target_binding_failure": True,
        "is_candidate_absence_failure": True,
        "is_selector_failure": False,
        "is_repair_collapse": False,
        "wrong_target_subtype": "profit_vs_sale_price",
        "evidence_summary": "Model solved for sale price not profit.",
        "computed_nearby_quantity": "100",
        "missing_candidate_hypothesis": "Profit = revenue - cost not explored.",
        "recommended_next_edge": "backward_from_target_check",
        "confidence": 0.85,
    }


# ---------------------------------------------------------------------------
# _try_json_parse
# ---------------------------------------------------------------------------

def test_try_json_parse_direct() -> None:
    obj, method = _try_json_parse('{"k": 1}')
    assert obj == {"k": 1}
    assert method == "direct"


def test_try_json_parse_fence_stripped() -> None:
    obj, method = _try_json_parse("```json\n{\"k\": 2}\n```")
    assert obj == {"k": 2}
    assert method == "fence_stripped"


def test_try_json_parse_extracted() -> None:
    text = 'Some preamble\n{"k": 3}\nsome trailing text'
    obj, method = _try_json_parse(text)
    assert obj == {"k": 3}
    assert method == "extracted"


def test_try_json_parse_fails_on_empty() -> None:
    obj, method = _try_json_parse("")
    assert obj is None
    assert method == "empty_response"


def test_try_json_parse_fails_on_garbage() -> None:
    obj, method = _try_json_parse("this is not json at all")
    assert obj is None
    assert method == "parse_failed"


# ---------------------------------------------------------------------------
# validate_response
# ---------------------------------------------------------------------------

def test_validate_response_valid() -> None:
    result = validate_response(_valid_response())
    assert result["schema_ok"] is True
    assert result["issues"] == []


def test_validate_response_missing_field() -> None:
    resp = _valid_response()
    del resp["case_id"]
    result = validate_response(resp)
    assert result["schema_ok"] is False
    assert any("missing_fields" in i for i in result["issues"])


def test_validate_response_invalid_subtype() -> None:
    resp = _valid_response()
    resp["wrong_target_subtype"] = "not_a_valid_subtype"
    result = validate_response(resp)
    assert result["schema_ok"] is False
    assert any("invalid_wrong_target_subtype" in i for i in result["issues"])


def test_validate_response_invalid_next_edge() -> None:
    resp = _valid_response()
    resp["recommended_next_edge"] = "not_a_valid_edge"
    result = validate_response(resp)
    assert result["schema_ok"] is False
    assert any("invalid_recommended_next_edge" in i for i in result["issues"])


def test_validate_response_confidence_out_of_range() -> None:
    resp = _valid_response()
    resp["confidence"] = 1.5
    result = validate_response(resp)
    assert result["schema_ok"] is False
    assert any("confidence_out_of_range" in i for i in result["issues"])


def test_validate_response_bool_field_as_string() -> None:
    resp = _valid_response()
    resp["is_final_target_binding_failure"] = "true"  # string, not bool
    result = validate_response(resp)
    assert result["schema_ok"] is False
    assert any("not_bool" in i for i in result["issues"])


def test_validate_response_secondary_not_list() -> None:
    resp = _valid_response()
    resp["secondary_failure_mechanisms"] = "string_not_list"
    result = validate_response(resp)
    assert result["schema_ok"] is False
    assert any("not_list" in i for i in result["issues"])


def test_valid_subtypes_and_edges_constants() -> None:
    assert "profit_vs_sale_price" in VALID_SUBTYPES
    assert "none" in VALID_SUBTYPES
    assert "backward_from_target_check" in VALID_NEXT_EDGES
    assert "none" in VALID_NEXT_EDGES


# ---------------------------------------------------------------------------
# audit_prompt_for_gold
# ---------------------------------------------------------------------------

def test_audit_prompt_no_gold() -> None:
    prompt = "Question: how much? selected_answer: 42"
    assert audit_prompt_for_gold(prompt) is False


def test_audit_prompt_detects_gold_answer() -> None:
    prompt = "gold_answer: 55\nquestion: ..."
    assert audit_prompt_for_gold(prompt) is True


def test_audit_prompt_detects_answer_key() -> None:
    prompt = "answer_key: 55\ncase_id: ..."
    assert audit_prompt_for_gold(prompt) is True


# ---------------------------------------------------------------------------
# build_case_prompt
# ---------------------------------------------------------------------------

def test_build_case_prompt_no_gold_leak() -> None:
    case = _minimal_case("openai_gsm8k_99")
    prompt = build_case_prompt(case, None)
    assert audit_prompt_for_gold(prompt) is False


def test_build_case_prompt_contains_case_id() -> None:
    case = _minimal_case("openai_gsm8k_77")
    prompt = build_case_prompt(case, None)
    assert "openai_gsm8k_77" in prompt


def test_build_case_prompt_includes_recommendation() -> None:
    case = _minimal_case("openai_gsm8k_50")
    rec = {
        "primary_recommendation": "backward_from_target_check",
        "recommended_next_edges": '["backward_from_target_check"]',
        "recommendation_reasons": "PAL code present but no verifier_check",
    }
    prompt = build_case_prompt(case, rec)
    assert "backward_from_target_check" in prompt


def test_build_case_prompt_no_gold_answer_field() -> None:
    case = _minimal_case()
    prompt = build_case_prompt(case, None)
    assert "gold" not in prompt.lower() or "gold_free" not in prompt.lower()
    # More specific: the forbidden patterns should not appear
    assert "gold_answer:" not in prompt.lower()
    assert "answer_key:" not in prompt.lower()


# ---------------------------------------------------------------------------
# select_cases
# ---------------------------------------------------------------------------

def _make_cases(n: int) -> list[dict]:
    return [{"case_id": f"openai_gsm8k_{i}", "question": f"q{i}"} for i in range(n)]


def test_select_cases_respects_limit() -> None:
    cases = _make_cases(50)
    gpns = [f"openai_gsm8k_{i}" for i in range(0, 10)]
    ga = [f"openai_gsm8k_{i}" for i in range(10, 40)]
    replay_cb = {f"openai_gsm8k_{i}": {"repair_layer_collapse_to_1": "True"} for i in range(40, 50)}
    missing_recs = {f"openai_gsm8k_{i}": {"primary_recommendation": "backward_from_target_check"} for i in range(0, 10)}
    selected = select_cases(cases, gpns, ga, replay_cb, missing_recs, limit=24)
    assert len(selected) <= 24


def test_select_cases_no_duplicates() -> None:
    cases = _make_cases(50)
    gpns = [f"openai_gsm8k_{i}" for i in range(0, 15)]
    ga = [f"openai_gsm8k_{i}" for i in range(0, 20)]  # overlaps with gpns
    replay_cb = {f"openai_gsm8k_{i}": {"repair_layer_collapse_to_1": "True"} for i in range(5, 15)}
    missing_recs = {f"openai_gsm8k_{i}": {"primary_recommendation": "backward_from_target_check"} for i in range(8, 18)}
    selected = select_cases(cases, gpns, ga, replay_cb, missing_recs, limit=24)
    ids = [c["case_id"] for c in selected]
    assert len(ids) == len(set(ids)), "Duplicates detected"


def test_select_cases_strata_labels() -> None:
    cases = _make_cases(30)
    gpns = [f"openai_gsm8k_{i}" for i in range(0, 5)]
    ga = [f"openai_gsm8k_{i}" for i in range(10, 20)]
    replay_cb = {f"openai_gsm8k_{i}": {"repair_layer_collapse_to_1": "True"} for i in range(20, 25)}
    missing_recs = {f"openai_gsm8k_{i}": {"primary_recommendation": "backward_from_target_check"} for i in range(25, 30)}
    selected = select_cases(cases, gpns, ga, replay_cb, missing_recs, limit=24)
    strata = {c["_stratum"] for c in selected}
    assert "gold_present_not_selected" in strata
    assert "gold_absent" in strata


def test_select_cases_empty_inputs() -> None:
    selected = select_cases([], [], [], {}, {}, limit=24)
    assert selected == []


# ---------------------------------------------------------------------------
# compute_agreement
# ---------------------------------------------------------------------------

def test_compute_agreement_full_agreement() -> None:
    labels = [
        {
            "case_id": "openai_gsm8k_1",
            "parse_ok": True,
            "parsed_obj": {
                "is_final_target_binding_failure": True,
                "is_candidate_absence_failure": True,
                "recommended_next_edge": "backward_from_target_check",
            },
        }
    ]
    result = compute_agreement(labels)
    assert result["hypothesis_agreement_rate"] == 1.0
    assert result["agrees_count"] == 1


def test_compute_agreement_no_agreement() -> None:
    labels = [
        {
            "case_id": "openai_gsm8k_2",
            "parse_ok": True,
            "parsed_obj": {
                "is_final_target_binding_failure": False,
                "is_candidate_absence_failure": False,
                "recommended_next_edge": "none",
            },
        }
    ]
    result = compute_agreement(labels)
    assert result["hypothesis_agreement_rate"] == 0.0


def test_compute_agreement_empty() -> None:
    result = compute_agreement([])
    assert result["n"] == 0
    assert result["hypothesis_agreement_rate"] == 0.0


def test_compute_agreement_partial() -> None:
    labels = [
        {
            "case_id": "openai_gsm8k_1",
            "parse_ok": True,
            "parsed_obj": {
                "is_final_target_binding_failure": True,
                "is_candidate_absence_failure": True,
                "recommended_next_edge": "backward_from_target_check",
            },
        },
        {
            "case_id": "openai_gsm8k_2",
            "parse_ok": True,
            "parsed_obj": {
                "is_final_target_binding_failure": False,
                "is_candidate_absence_failure": False,
                "recommended_next_edge": "none",
            },
        },
    ]
    result = compute_agreement(labels)
    assert result["hypothesis_agreement_rate"] == 0.5


# ---------------------------------------------------------------------------
# Data loaders (using tmp_path)
# ---------------------------------------------------------------------------

def test_load_trace_packets_bundle(tmp_path: Path) -> None:
    bundle = {
        "batch_id": "test",
        "cases": [
            {"case_id": "openai_gsm8k_1", "question": "q1"},
            {"case_id": "openai_gsm8k_2", "question": "q2"},
        ],
    }
    p = tmp_path / "trace_packets.jsonl"
    p.write_text(json.dumps(bundle), encoding="utf-8")
    cases = load_trace_packets(p)
    assert len(cases) == 2
    assert cases[0]["case_id"] == "openai_gsm8k_1"


def test_parse_gold_pool_split(tmp_path: Path) -> None:
    content = """# Report
## A. gold_present_not_selected
| case_id | q |
|---------|---|
| openai_gsm8k_10 | x |
| openai_gsm8k_20 | y |

## B. gold_absent_from_pool
### profit (2)
| case_id | q |
|---------|---|
| openai_gsm8k_30 | x |
| openai_gsm8k_40 | y |
"""
    p = tmp_path / "report.md"
    p.write_text(content, encoding="utf-8")
    gpns, ga = parse_gold_pool_split(p)
    assert gpns == ["openai_gsm8k_10", "openai_gsm8k_20"]
    assert ga == ["openai_gsm8k_30", "openai_gsm8k_40"]


def test_load_replay_casebook(tmp_path: Path) -> None:
    p = tmp_path / "casebook.csv"
    p.write_text(
        "case_id,repair_layer_collapse_to_1\nopenai_gsm8k_1,True\nopenai_gsm8k_2,False\n",
        encoding="utf-8",
    )
    cb = load_replay_casebook(p)
    assert "openai_gsm8k_1" in cb
    assert cb["openai_gsm8k_1"]["repair_layer_collapse_to_1"] == "True"


def test_load_missing_edge_recs(tmp_path: Path) -> None:
    p = tmp_path / "recs.csv"
    p.write_text(
        "case_id,primary_recommendation\nopenai_gsm8k_1,backward_from_target_check\n",
        encoding="utf-8",
    )
    recs = load_missing_edge_recs(p)
    assert "openai_gsm8k_1" in recs
    assert recs["openai_gsm8k_1"]["primary_recommendation"] == "backward_from_target_check"


# ---------------------------------------------------------------------------
# required_response_fields constant
# ---------------------------------------------------------------------------

def test_required_response_fields_complete() -> None:
    assert "case_id" in REQUIRED_RESPONSE_FIELDS
    assert "primary_failure_mechanism" in REQUIRED_RESPONSE_FIELDS
    assert "confidence" in REQUIRED_RESPONSE_FIELDS
    assert "recommended_next_edge" in REQUIRED_RESPONSE_FIELDS
    assert len(REQUIRED_RESPONSE_FIELDS) == 13
