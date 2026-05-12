"""Tests for audit_cerebras_capabilities.py (no live API calls)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.audit_cerebras_capabilities import (
    CANDIDATE_MODELS,
    _audit_prompt_for_gold,
    _classify_error,
    _try_json_parse,
    _validate_project_response,
    generate_report,
    run_project_prompt_test,
)


# ---------------------------------------------------------------------------
# _try_json_parse
# ---------------------------------------------------------------------------

def test_parse_direct() -> None:
    obj, m = _try_json_parse('{"status":"ok"}')
    assert obj == {"status": "ok"}
    assert m == "direct"


def test_parse_fence_stripped() -> None:
    obj, m = _try_json_parse("```json\n{\"k\":1}\n```")
    assert obj == {"k": 1}
    assert m == "fence_stripped"


def test_parse_extracted() -> None:
    obj, m = _try_json_parse("preamble {\"k\":2} trailing")
    assert obj == {"k": 2}
    assert m == "extracted"


def test_parse_empty() -> None:
    obj, m = _try_json_parse("")
    assert obj is None
    assert m == "empty_response"


def test_parse_garbage() -> None:
    obj, m = _try_json_parse("not json at all")
    assert obj is None
    assert m == "parse_failed"


def test_parse_returns_none_for_list() -> None:
    # Top-level list should not be returned as dict
    obj, m = _try_json_parse("[1,2,3]")
    assert obj is None


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------

def test_classify_model_not_found() -> None:
    err = {"error": {"type": "model_not_found", "message": "Model not found"}}
    result = _classify_error(404, err, "")
    assert result["is_model_not_found"] is True
    assert result["is_cloudflare_403_1010"] is False


def test_classify_rate_limit_429() -> None:
    result = _classify_error(429, {}, "")
    assert result["is_rate_limit"] is True


def test_classify_cloudflare_403() -> None:
    result = _classify_error(403, {}, "Error 1010 Ray ID cloudflare")
    assert result["is_cloudflare_403_1010"] is True
    assert result["is_auth_error"] is True


def test_classify_clean_success() -> None:
    result = _classify_error(200, None, "")
    assert result["is_cloudflare_403_1010"] is False
    assert result["is_model_not_found"] is False
    assert result["is_rate_limit"] is False
    assert result["is_auth_error"] is False


def test_classify_error_message_extraction() -> None:
    err = {"type": "invalid_request", "message": "Bad request here"}
    result = _classify_error(400, err, "")
    assert result["error_type"] == "invalid_request"
    assert "Bad request" in result["error_message"]


def test_classify_nested_error() -> None:
    err = {"error": {"type": "model_not_found", "message": "no such model"}}
    result = _classify_error(404, err, "")
    assert result["is_model_not_found"] is True
    assert result["error_type"] == "model_not_found"


# ---------------------------------------------------------------------------
# _validate_project_response
# ---------------------------------------------------------------------------

def _valid_proj_response() -> dict:
    return {
        "problem_summary": "Test problem",
        "target_question": "What is x?",
        "target_variable_name": "total_cost",
        "target_unit": "dollars",
        "variables": [
            {"name": "price", "value": 10},
            {"name": "total_cost", "value": 50},
        ],
        "rejected_non_final_variables": ["price"],
        "answer_variable_name": "total_cost",
        "final_answer": 50,
    }


def test_validate_project_valid() -> None:
    result = _validate_project_response(_valid_proj_response())
    assert result["schema_ok"] is True
    assert result["fa_bare"] is True
    assert result["avn_in_vars"] is True
    assert result["names_match"] is True


def test_validate_project_missing_field() -> None:
    resp = _valid_proj_response()
    del resp["final_answer"]
    result = _validate_project_response(resp)
    assert result["schema_ok"] is False
    assert any("missing_fields" in i for i in result["issues"])


def test_validate_project_fa_not_bare_number() -> None:
    resp = _valid_proj_response()
    resp["final_answer"] = "$50"
    result = _validate_project_response(resp)
    assert result["fa_bare"] is False
    assert result["schema_ok"] is False


def test_validate_project_avn_not_in_vars() -> None:
    resp = _valid_proj_response()
    resp["answer_variable_name"] = "nonexistent_var"
    result = _validate_project_response(resp)
    assert result["avn_in_vars"] is False
    assert result["schema_ok"] is False


def test_validate_project_tvn_avn_mismatch() -> None:
    resp = _valid_proj_response()
    resp["target_variable_name"] = "profit"
    result = _validate_project_response(resp)
    assert result["names_match"] is False
    assert result["schema_ok"] is False


def test_validate_project_fa_float_ok() -> None:
    resp = _valid_proj_response()
    resp["final_answer"] = 3.14
    result = _validate_project_response(resp)
    assert result["fa_bare"] is True


# ---------------------------------------------------------------------------
# _audit_prompt_for_gold
# ---------------------------------------------------------------------------

def test_no_gold_in_normal_prompt() -> None:
    assert _audit_prompt_for_gold("question: how many apples?") is False


def test_gold_answer_detected() -> None:
    assert _audit_prompt_for_gold("gold_answer: 42") is True


def test_answer_key_detected() -> None:
    assert _audit_prompt_for_gold("answer_key: 55\ncase_id: x") is True


def test_correct_answer_detected() -> None:
    assert _audit_prompt_for_gold("correct_answer: 100") is True


# ---------------------------------------------------------------------------
# generate_report (smoke — no API needed)
# ---------------------------------------------------------------------------

def _make_call_result(model: str, test_type: str, ok: bool, **kwargs) -> dict:
    return {
        "model": model,
        "test_type": test_type,
        "http_status": 200 if ok else 400,
        "call_ok": ok,
        "api_calls_made": 1,
        "latency_ms": 100,
        "response_length": 10 if ok else 0,
        "content_present": ok,
        "json_parse_ok": ok if test_type != "A_plain_text" else None,
        "json_parse_method": "direct" if ok else "n/a",
        "schema_ok": ok if test_type != "A_plain_text" else None,
        "schema_missing_fields": [],
        "text_snippet": "ok" if ok else "",
        "is_cloudflare_403_1010": False,
        "is_model_not_found": not ok,
        "is_rate_limit": False,
        "is_auth_error": False,
        "error_type": "" if ok else "model_not_found",
        "error_message": "" if ok else "model not found",
        "error_raw": None,
        **kwargs,
    }


def test_generate_report_smoke() -> None:
    ts = "20260512T000000Z"
    models_result = {
        "ok": True,
        "http_status": 200,
        "latency_ms": 50,
        "model_ids": ["llama3.1-8b", "gpt-oss-120b"],
        "raw_response": {},
    }
    call_results = [
        _make_call_result("llama3.1-8b", "A_plain_text", True),
        _make_call_result("llama3.1-8b", "B_json_only", True),
        _make_call_result("llama3.1-8b", "C_json_reasoning", True),
        _make_call_result("gpt-oss-120b", "A_plain_text", False),
    ]
    report = generate_report(
        ts=ts,
        models_result=models_result,
        all_call_results=call_results,
        project_results=[],
        accessible_models=["llama3.1-8b"],
        json_reliable_models=["llama3.1-8b"],
        project_compatible_models=[],
        total_api_calls=5,
    )
    assert "llama3.1-8b" in report
    assert "gpt-oss-120b" in report
    assert "Recommended default" in report
    assert "Total API calls" in report


def test_generate_report_no_accessible_model() -> None:
    ts = "20260512T000000Z"
    models_result = {"ok": True, "http_status": 200, "latency_ms": 40,
                     "model_ids": ["llama3.1-8b"], "raw_response": {}}
    report = generate_report(
        ts=ts,
        models_result=models_result,
        all_call_results=[_make_call_result("llama3.1-8b", "A_plain_text", False)],
        project_results=[],
        accessible_models=[],
        json_reliable_models=[],
        project_compatible_models=[],
        total_api_calls=1,
    )
    assert "No accessible model" in report


def test_generate_report_cloudflare_flag() -> None:
    ts = "20260512T000000Z"
    models_result = {"ok": True, "http_status": 200, "latency_ms": 40,
                     "model_ids": ["llama3.1-8b"], "raw_response": {}}
    call_results = [
        _make_call_result("llama3.1-8b", "A_plain_text", False,
                          is_cloudflare_403_1010=True, http_status=403)
    ]
    report = generate_report(
        ts=ts,
        models_result=models_result,
        all_call_results=call_results,
        project_results=[],
        accessible_models=[],
        json_reliable_models=[],
        project_compatible_models=[],
        total_api_calls=1,
    )
    assert "YES" in report or "1010 DID occur" in report


# ---------------------------------------------------------------------------
# run_project_prompt_test (uses tmp_path, mocks session)
# ---------------------------------------------------------------------------

class _MockSession:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = iter(responses)

    def post(self, url: str, json: dict, timeout: int) -> "_MockResponse":
        try:
            r = next(self._responses)
        except StopIteration:
            r = {"ok": False, "status_code": 500, "json": {}, "text": ""}
        return _MockResponse(r)


class _MockResponse:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.ok = data.get("ok", True)
        self.status_code = data.get("status_code", 200)
        self.text = data.get("text", "")

    def json(self) -> dict:
        return self._data.get("json", {})


def _write_project_prompts(path: Path, prompts: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for p in prompts:
            f.write(json.dumps(p) + "\n")


def test_run_project_prompt_test_success(tmp_path: Path) -> None:
    good_response = {
        "problem_summary": "Test",
        "target_question": "What is cost?",
        "target_variable_name": "total_cost",
        "target_unit": "dollars",
        "variables": [{"name": "total_cost", "value": 50}],
        "rejected_non_final_variables": ["price"],
        "answer_variable_name": "total_cost",
        "final_answer": 50,
    }
    mock_resp = {
        "ok": True,
        "status_code": 200,
        "json": {
            "choices": [{"message": {"content": json.dumps(good_response)}}],
            "usage": {},
        },
        "text": "",
    }
    session = _MockSession([mock_resp])
    prompts_path = tmp_path / "prompts.jsonl"
    _write_project_prompts(prompts_path, [
        {"case_id": "openai_gsm8k_1", "prompt_text": "Solve: question text here."}
    ])

    results = run_project_prompt_test(session, "llama3.1-8b", prompts_path, max_prompts=1)  # type: ignore[arg-type]
    assert len(results) == 1
    assert results[0]["call_ok"] is True
    assert results[0]["parse_ok"] is True


def test_run_project_prompt_test_gold_audit(tmp_path: Path) -> None:
    prompts_path = tmp_path / "prompts.jsonl"
    _write_project_prompts(prompts_path, [
        {"case_id": "openai_gsm8k_2", "prompt_text": "gold_answer: 42\nquestion: ..."}
    ])
    mock_resp = {
        "ok": True,
        "status_code": 200,
        "json": {"choices": [{"message": {"content": "{}"}}], "usage": {}},
        "text": "",
    }
    session = _MockSession([mock_resp])
    results = run_project_prompt_test(session, "llama3.1-8b", prompts_path, max_prompts=1)  # type: ignore[arg-type]
    assert results[0]["gold_leak_in_prompt"] is True


# ---------------------------------------------------------------------------
# CANDIDATE_MODELS constant
# ---------------------------------------------------------------------------

def test_candidate_models_list() -> None:
    assert "llama3.1-8b" in CANDIDATE_MODELS
    assert "gpt-oss-120b" in CANDIDATE_MODELS
    assert len(CANDIDATE_MODELS) == 4
